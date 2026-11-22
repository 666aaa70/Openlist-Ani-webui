"""Tests for server-side settings persistence, upstream URL masking, and health reporting."""

from __future__ import annotations

import httpx

from tests.conftest import MockOpenlistAni


async def test_settings_mask_internal_upstream_url_and_persist(
    authed_client: tuple[httpx.AsyncClient, str],
) -> None:
    client, csrf = authed_client

    get_resp = await client.get("/api/v1/settings")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["upstream_configured"] is True
    assert "openlist-ani.internal" not in data["upstream_masked"]
    assert data["upstream_masked"] == "http://••••:26666"
    assert data["language"] == "zh-CN"
    assert data["theme"] == "dark"

    put_resp = await client.put(
        "/api/v1/settings",
        json={
            "upstream_url": "http://192.168.1.50:26667",
            "api_timeout_seconds": 45,
            "poll_interval_seconds": 10,
            "theme": "light",
            "language": "zh-CN",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert put_resp.status_code == 200
    updated = put_resp.json()
    assert "192.168.1.50" not in updated["upstream_masked"]
    assert updated["upstream_masked"] == "http://••••:26667"
    assert updated["api_timeout_seconds"] == 45.0
    assert updated["poll_interval_seconds"] == 10
    assert updated["theme"] == "light"

    # Reject invalid scheme in settings
    bad_resp = await client.put(
        "/api/v1/settings",
        json={"upstream_url": "ftp://evil.local:21"},
        headers={"X-CSRF-Token": csrf},
    )
    assert bad_resp.status_code == 400
    assert bad_resp.json()["code"] == "invalid_setting"


async def test_health_ready_degraded_and_unreachable(
    authed_client: tuple[httpx.AsyncClient, str],
    mock_upstream: MockOpenlistAni,
) -> None:
    client, csrf = authed_client

    ok = await client.get("/api/v1/health")
    assert ok.status_code == 200
    assert ok.json()["upstream_reachable"] is True
    assert ok.json()["upstream_ready"] is True
    assert ok.json()["workers"] == {"running": 3, "expected": 3}

    mock_upstream.ready = False
    mock_upstream.health_status = "degraded"
    mock_upstream.degraded = {"download_worker": "worker exited unexpectedly"}
    deg = await client.post("/api/v1/settings/test-connection", headers={"X-CSRF-Token": csrf})
    assert deg.status_code == 200
    assert deg.json()["upstream_reachable"] is True
    assert deg.json()["upstream_ready"] is False
    assert deg.json()["upstream_status"] == "degraded"

    mock_upstream.raise_error = httpx.ConnectError("connection refused")
    down = await client.get("/api/v1/health")
    assert down.status_code == 200
    assert down.json()["upstream_reachable"] is False
    assert down.json()["error_code"] == "upstream_unreachable"
