"""Tests for strict API proxy whitelist, SSRF blocking, and upstream error handling."""

from __future__ import annotations

import httpx

from app.security import validate_upstream_url
from tests.conftest import MockOpenlistAni


async def test_admin_restart_endpoint_is_not_proxied(
    authed_client: tuple[httpx.AsyncClient, str],
    mock_upstream: MockOpenlistAni,
) -> None:
    client, csrf = authed_client
    for forbidden in ("/api/restart", "/api/v1/restart", "/api/rss", "/api/parse_rss"):
        resp = await client.post(forbidden, headers={"X-CSRF-Token": csrf})
        assert resp.status_code == 404
    assert all(path != "/api/restart" for _, path, _ in mock_upstream.calls)


async def test_task_id_path_traversal_blocked(
    authed_client: tuple[httpx.AsyncClient, str],
    mock_upstream: MockOpenlistAni,
) -> None:
    client, _ = authed_client

    # Encoded slash traversal never reaches upstream
    resp_slash = await client.get("/api/v1/downloads/..%2Frestart")
    assert resp_slash.status_code in {400, 404}

    # Malformed characters in task_id are explicitly rejected with 400
    resp_bad = await client.get("/api/v1/downloads/bad..id$foo")
    assert resp_bad.status_code == 400
    assert resp_bad.json()["code"] == "invalid_task_id"
    assert mock_upstream.calls == []


async def test_upstream_unreachable_and_timeout_unified_errors(
    authed_client: tuple[httpx.AsyncClient, str],
    mock_upstream: MockOpenlistAni,
) -> None:
    client, _ = authed_client

    mock_upstream.raise_error = httpx.ConnectError("connection refused")
    r_conn = await client.get("/api/v1/downloads")
    assert r_conn.status_code == 502
    assert r_conn.json()["code"] == "upstream_unreachable"

    mock_upstream.raise_error = httpx.ReadTimeout("timed out")
    r_timeout = await client.get("/api/v1/downloads")
    assert r_timeout.status_code == 504
    assert r_timeout.json()["code"] == "upstream_timeout"


def test_ssrf_url_validation() -> None:
    assert validate_upstream_url("http://127.0.0.1:26666/") == "http://127.0.0.1:26666"
    assert validate_upstream_url("https://oani.internal:8443") == "https://oani.internal:8443"

    for bad in (
        "file:///etc/passwd",
        "gopher://127.0.0.1:6379/_INFO",
        "http://user:pass@127.0.0.1:26666",
        "http://127.0.0.1:26666?foo=bar",
        "http://127.0.0.1:26666/../secret",
        "not-a-url",
    ):
        try:
            validate_upstream_url(bad)
            raise AssertionError(f"Expected ValueError for {bad}")
        except ValueError:
            pass

    # Allowed hosts whitelist check
    try:
        validate_upstream_url(
            "http://169.254.169.254",
            allowed_hosts=frozenset({"127.0.0.1", "openlist-ani"}),
        )
        raise AssertionError("Expected host whitelist rejection")
    except ValueError:
        pass


async def test_spa_static_fallback_isolates_api_routes(tmp_path) -> None:
    from app.config import AppConfig
    from app.main import create_app
    from app.security import hash_password

    static_dir = tmp_path / "dist"
    (static_dir / "assets").mkdir(parents=True)
    (static_dir / "index.html").write_text("<html><body>SPA_OK</body></html>", encoding="utf-8")
    (static_dir / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")

    cfg = AppConfig(
        webui_username="admin",
        webui_password_hash=hash_password("Pass#123456"),
        webui_data_dir=tmp_path / "data",
        webui_static_dir=static_dir,
    )
    app = create_app(cfg)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        spa = await c.get("/downloads")
        assert spa.status_code == 200
        assert "SPA_OK" in spa.text

        asset = await c.get("/assets/app.js")
        assert asset.status_code == 200
        assert "console.log" in asset.text

        unknown_api = await c.get("/api/restart")
        assert unknown_api.status_code == 404
        assert unknown_api.json()["code"] == "not_found"
