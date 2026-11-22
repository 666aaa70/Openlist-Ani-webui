"""Server-persisted settings endpoints (upstream URL is stored server-side and masked to browsers)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import get_store, get_upstream, require_csrf, require_session
from ..schemas import ServiceHealthResponse, SettingsResponse, UpdateSettingsRequest
from ..security import mask_upstream_url
from ..storage import SessionRecord, StateStore, StoredSettings
from ..upstream import OpenlistAniClient

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


def _to_response(settings: StoredSettings) -> SettingsResponse:
    return SettingsResponse(
        upstream_configured=bool(settings.upstream_url),
        upstream_masked=mask_upstream_url(settings.upstream_url),
        api_timeout_seconds=settings.api_timeout_seconds,
        poll_interval_seconds=settings.poll_interval_seconds,
        theme=settings.theme,
        language=settings.language,
    )


@router.get("", response_model=SettingsResponse)
async def get_settings(
    _session: SessionRecord = Depends(require_session),
    store: StateStore = Depends(get_store),
) -> SettingsResponse:
    return _to_response(store.get_settings())


@router.put("", response_model=SettingsResponse)
async def update_settings(
    payload: UpdateSettingsRequest,
    _session: SessionRecord = Depends(require_csrf),
    store: StateStore = Depends(get_store),
) -> SettingsResponse:
    try:
        updated = store.update_settings(
            upstream_url=payload.upstream_url,
            api_timeout_seconds=payload.api_timeout_seconds,
            poll_interval_seconds=payload.poll_interval_seconds,
            theme=payload.theme,
            language=payload.language,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_setting", "message": str(exc)},
        ) from exc
    return _to_response(updated)


@router.post("/test-connection", response_model=ServiceHealthResponse)
async def test_connection(
    _session: SessionRecord = Depends(require_csrf),
    upstream: OpenlistAniClient = Depends(get_upstream),
) -> ServiceHealthResponse:
    """Test connectivity against the currently saved server-side Openlist-Ani URL only."""
    return await upstream.check_health()
