"""Tests for end-to-end download flow: resolve -> preflight -> confirm conflicts -> create -> track completion."""

from __future__ import annotations

import httpx

from tests.conftest import MockOpenlistAni


async def test_magnet_resolve_preflight_create_and_completed_tracking(
    authed_client: tuple[httpx.AsyncClient, str],
    mock_upstream: MockOpenlistAni,
) -> None:
    client, csrf = authed_client
    headers = {"X-CSRF-Token": csrf}
    magnet = "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&dn=Frieren"

    # 1. Resolve magnet
    resolve_resp = await client.post(
        "/api/v1/resolve/magnet",
        json={"magnet": magnet, "metadata_timeout": 30},
        headers=headers,
    )
    assert resolve_resp.status_code == 200
    resolved = resolve_resp.json()
    assert resolved["success"] is True
    assert resolved["title"].startswith("[LoliHouse] Sousou no Frieren")
    assert resolved["video_file_count"] == 1
    assert resolved["collection_hint"] is False
    assert resolved["files"][0]["is_video"] is True
    assert resolved["files"][1]["is_video"] is False

    # 2. Preflight (clean)
    preflight_resp = await client.post(
        "/api/v1/downloads/preflight",
        json={
            "download_url": magnet,
            "title": resolved["title"],
            "collection_hint": resolved["collection_hint"],
        },
        headers=headers,
    )
    assert preflight_resp.status_code == 200
    preflight = preflight_resp.json()
    assert preflight["success"] is True
    assert preflight["confirmation_required"] is False

    # 3. Create download
    create_resp = await client.post(
        "/api/v1/downloads",
        json={
            "download_url": magnet,
            "title": resolved["title"],
            "collection_hint": False,
        },
        headers=headers,
    )
    assert create_resp.status_code == 200
    created = create_resp.json()
    assert created["success"] is True
    task_id = created["task"]["id"]
    assert created["task"]["state"] == "downloading"

    # 4. List downloads shows active task
    list_resp = await client.get("/api/v1/downloads")
    assert list_resp.status_code == 200
    listed = list_resp.json()
    assert listed["active_count"] == 1
    assert listed["completed_count"] == 0
    assert listed["tasks"][0]["id"] == task_id

    # 5. Simulate Openlist-Ani completing the task (drops off GET /api/downloads, remains on GET /api/downloads/{id})
    mock_upstream.tasks[task_id]["state"] = "completed"
    mock_upstream.tasks[task_id]["completed_at"] = "2026-11-21T10:05:00+00:00"
    mock_upstream.tasks[task_id]["final_path"] = "/PikPak/Anime/葬送的芙莉莲/Season 01/葬送的芙莉莲 S01E01.mkv"
    mock_upstream.tasks[task_id]["final_paths"] = [
        "/PikPak/Anime/葬送的芙莉莲/Season 01/葬送的芙莉莲 S01E01.mkv"
    ]

    list_after = await client.get("/api/v1/downloads")
    assert list_after.status_code == 200
    listed_after = list_after.json()
    assert listed_after["active_count"] == 0
    assert listed_after["completed_count"] == 1
    assert listed_after["tasks"][0]["state"] == "completed"
    assert listed_after["tasks"][0]["final_path"] == "/PikPak/Anime/葬送的芙莉莲/Season 01/葬送的芙莉莲 S01E01.mkv"

    # 6. Subsequent poll reuses verified terminal snapshot instead of hammering GET /api/downloads/{id}
    detail_calls_before = sum(
        1 for method, path, _ in mock_upstream.calls if method == "GET" and path == f"/api/downloads/{task_id}"
    )
    list_cached = await client.get("/api/v1/downloads")
    assert list_cached.status_code == 200
    assert list_cached.json()["completed_count"] == 1
    detail_calls_after = sum(
        1 for method, path, _ in mock_upstream.calls if method == "GET" and path == f"/api/downloads/{task_id}"
    )
    assert detail_calls_after == detail_calls_before


async def test_torrent_collection_hint_and_policy_conflict_confirmation(
    authed_client: tuple[httpx.AsyncClient, str],
    mock_upstream: MockOpenlistAni,
) -> None:
    client, csrf = authed_client
    headers = {"X-CSRF-Token": csrf}
    torrent_url = "https://example.org/releases/dungeon-meshi.torrent"

    # 1. Resolve torrent with 2 video files -> collection_hint = True
    resolve_resp = await client.post(
        "/api/v1/resolve/torrent",
        json={"url": torrent_url},
        headers=headers,
    )
    assert resolve_resp.status_code == 200
    resolved = resolve_resp.json()
    assert resolved["video_file_count"] == 2
    assert resolved["collection_hint"] is True

    # 2. Configure upstream policy conflict
    mock_upstream.preflight_conflicts = [
        {
            "key": "collection:manual",
            "code": "collection_override",
            "reason": "该资源包含多个视频文件，将继续作为合集下载并绕过自动 RSS 策略筛选。",
            "matched": "collection_hint=true",
            "details": {},
        }
    ]
    mock_upstream.preflight_warnings = ["合集内每集将在下载完成后逐一解析。"]

    preflight_resp = await client.post(
        "/api/v1/downloads/preflight",
        json={
            "download_url": torrent_url,
            "title": resolved["title"],
            "collection_hint": True,
        },
        headers=headers,
    )
    assert preflight_resp.status_code == 200
    pre = preflight_resp.json()
    assert pre["confirmation_required"] is True
    assert pre["policy_review_token"] == "tok_review_123456"
    assert pre["policy_conflicts"][0]["key"] == "collection:manual"

    # 3. Submitting WITHOUT confirmation is rejected by upstream policy
    unconfirmed = await client.post(
        "/api/v1/downloads",
        json={
            "download_url": torrent_url,
            "title": resolved["title"],
            "collection_hint": True,
        },
        headers=headers,
    )
    assert unconfirmed.status_code == 200
    assert unconfirmed.json()["success"] is False
    assert unconfirmed.json()["confirmation_required"] is True

    # 4. Submitting WITH explicit confirmation & token succeeds
    confirmed = await client.post(
        "/api/v1/downloads",
        json={
            "download_url": torrent_url,
            "title": resolved["title"],
            "collection_hint": True,
            "override_policy": True,
            "acknowledged_conflicts": ["collection:manual"],
            "policy_review_token": pre["policy_review_token"],
        },
        headers=headers,
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["success"] is True
    assert confirmed.json()["task"] is not None


async def test_incomplete_magnet_inspection_sets_conservative_collection_hint(
    authed_client: tuple[httpx.AsyncClient, str],
    mock_upstream: MockOpenlistAni,
) -> None:
    client, csrf = authed_client
    mock_upstream.resolve_magnet_override = {
        "success": True,
        "message": "Metadata timed out; using dn= title",
        "title": "[Sub] Example Anime - 01",
        "source": "dn",
        "error_code": "metadata_timeout",
        "file_count": None,
        "files": [],
    }
    resp = await client.post(
        "/api/v1/resolve/magnet",
        json={"magnet": "magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&dn=Example"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["inspection_incomplete"] is True
    assert data["collection_hint"] is True


async def test_empty_title_rejected_no_fabrication(
    authed_client: tuple[httpx.AsyncClient, str],
) -> None:
    client, csrf = authed_client
    resp = await client.post(
        "/api/v1/downloads",
        json={
            "download_url": "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567",
            "title": "   ",
            "collection_hint": False,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "validation_error"
