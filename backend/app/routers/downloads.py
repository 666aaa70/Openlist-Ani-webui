"""Whitelisted download & resource resolution endpoints backed by Openlist-Ani."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import get_store, get_upstream, require_csrf, require_session
from ..schemas import (
    CreateDownloadRequest,
    CreateDownloadResponse,
    DownloadListResponse,
    DownloadPreflightRequest,
    DownloadPreflightResponse,
    DownloadTaskResponse,
    ResolveMagnetRequest,
    ResolveResourceResponse,
    ResolveTorrentRequest,
)
from ..security import validate_task_id
from ..storage import SessionRecord, StateStore
from ..upstream import OpenlistAniClient, UpstreamError

router = APIRouter(prefix="/api/v1", tags=["downloads"])


@router.post("/resolve/magnet", response_model=ResolveResourceResponse)
async def resolve_magnet(
    payload: ResolveMagnetRequest,
    _session: SessionRecord = Depends(require_csrf),
    upstream: OpenlistAniClient = Depends(get_upstream),
) -> ResolveResourceResponse:
    return await upstream.resolve_magnet(
        magnet=payload.magnet,
        metadata_timeout=payload.metadata_timeout,
    )


@router.post("/resolve/torrent", response_model=ResolveResourceResponse)
async def resolve_torrent(
    payload: ResolveTorrentRequest,
    _session: SessionRecord = Depends(require_csrf),
    upstream: OpenlistAniClient = Depends(get_upstream),
) -> ResolveResourceResponse:
    return await upstream.resolve_torrent(url=payload.url)


@router.post("/downloads/preflight", response_model=DownloadPreflightResponse)
async def preflight_download(
    payload: DownloadPreflightRequest,
    _session: SessionRecord = Depends(require_csrf),
    upstream: OpenlistAniClient = Depends(get_upstream),
) -> DownloadPreflightResponse:
    return await upstream.preflight_download(payload)


IMMUTABLE_TERMINAL_STATES = frozenset({"completed", "cancelled"})


def _snapshot_for_storage(task: DownloadTaskResponse) -> str | None:
    if task.state in IMMUTABLE_TERMINAL_STATES:
        return task.model_dump_json()
    return None


@router.post("/downloads", response_model=CreateDownloadResponse)
async def create_download(
    payload: CreateDownloadRequest,
    _session: SessionRecord = Depends(require_csrf),
    upstream: OpenlistAniClient = Depends(get_upstream),
    store: StateStore = Depends(get_store),
) -> CreateDownloadResponse:
    result = await upstream.create_download(payload)
    if result.success and result.task is not None:
        store.record_tasks(
            [(result.task.id, result.task.state, _snapshot_for_storage(result.task))]
        )
    return result


@router.get("/downloads", response_model=DownloadListResponse)
async def list_downloads(
    _session: SessionRecord = Depends(require_session),
    upstream: OpenlistAniClient = Depends(get_upstream),
    store: StateStore = Depends(get_store),
) -> DownloadListResponse:
    live_tasks = await upstream.list_downloads()
    by_id: dict[str, DownloadTaskResponse] = {task.id: task for task in live_tasks}

    # Record all currently listed real task IDs so we can verify their final state
    # via GET /api/downloads/{task_id} once they complete and leave GET /api/downloads.
    store.record_tasks(
        [(task.id, task.state, _snapshot_for_storage(task)) for task in live_tasks]
    )

    tracked_records = store.list_tracked_task_ids(limit=100)
    missing_to_fetch: list[str] = []
    for rec in tracked_records:
        if rec.task_id in by_id:
            continue
        if rec.last_state in IMMUTABLE_TERMINAL_STATES and rec.payload_json:
            try:
                by_id[rec.task_id] = DownloadTaskResponse.model_validate_json(rec.payload_json)
                continue
            except Exception:
                pass
        missing_to_fetch.append(rec.task_id)

    if missing_to_fetch:
        semaphore = asyncio.Semaphore(6)

        async def _fetch_tracked(task_id: str) -> tuple[str, DownloadTaskResponse | None, bool]:
            async with semaphore:
                try:
                    item = await upstream.get_download(task_id)
                    return task_id, item, False
                except (UpstreamError, ValueError):
                    return task_id, None, True

        fetched = await asyncio.gather(*(_fetch_tracked(tid) for tid in missing_to_fetch))
        updated_entries: list[tuple[str, str, str | None]] = []
        for task_id, item, had_error in fetched:
            if item is not None:
                by_id[item.id] = item
                updated_entries.append((item.id, item.state, _snapshot_for_storage(item)))
            elif not had_error:
                # 404 from Openlist-Ani -> task no longer exists upstream
                store.remove_tracked_task(task_id)
        if updated_entries:
            store.record_tasks(updated_entries)

    merged = sorted(by_id.values(), key=lambda t: t.created_at, reverse=True)
    completed_count = sum(1 for t in merged if t.state == "completed")
    failed_count = sum(1 for t in merged if t.state == "failed")
    cancelled_count = sum(1 for t in merged if t.state == "cancelled")
    active_count = len(merged) - completed_count - failed_count - cancelled_count

    return DownloadListResponse(
        tasks=merged,
        total=len(merged),
        active_count=active_count,
        completed_count=completed_count,
        failed_count=failed_count,
        cancelled_count=cancelled_count,
        synced_at=datetime.now(UTC).isoformat(),
    )


@router.get("/downloads/{task_id}", response_model=DownloadTaskResponse)
async def get_download(
    task_id: str,
    _session: SessionRecord = Depends(require_session),
    upstream: OpenlistAniClient = Depends(get_upstream),
    store: StateStore = Depends(get_store),
) -> DownloadTaskResponse:
    try:
        safe_id = validate_task_id(task_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_task_id", "message": str(exc)},
        ) from exc

    task = await upstream.get_download(safe_id)
    if task is None:
        store.remove_tracked_task(safe_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "task_not_found", "message": f"未找到任务: {safe_id}"},
        )
    store.record_tasks([(task.id, task.state, _snapshot_for_storage(task))])
    return task
