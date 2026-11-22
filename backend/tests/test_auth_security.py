"""Tests for authentication, HttpOnly cookies, CSRF protection, and login rate limiting."""

from __future__ import annotations

import httpx
import pytest


async def test_unauthenticated_requests_rejected(client: httpx.AsyncClient) -> None:
    for path in ("/api/v1/auth/me", "/api/v1/health", "/api/v1/downloads", "/api/v1/settings"):
        resp = await client.get(path)
        assert resp.status_code == 401
        assert resp.json()["code"] == "unauthenticated"

    # Public container liveness probe stays accessible without leaking upstream info
    live = await client.get("/api/v1/health/live")
    assert live.status_code == 200
    assert live.json() == {"status": "live"}


async def test_login_sets_httponly_cookie_and_csrf_enforced(client: httpx.AsyncClient) -> None:
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "SuperSecret#2026"},
    )
    assert login.status_code == 200
    body = login.json()
    assert body["authenticated"] is True
    assert body["username"] == "admin"
    csrf_token = body["csrf_token"]
    assert len(csrf_token) >= 32

    set_cookie = login.headers.get("set-cookie", "").lower()
    assert "oani_session=" in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie

    # Security headers present
    assert login.headers.get("x-content-type-options") == "nosniff"
    assert login.headers.get("x-frame-options") == "DENY"
    assert login.headers.get("cache-control") == "no-store"

    # Mutating request WITHOUT CSRF token must be blocked (403)
    no_csrf = await client.post(
        "/api/v1/resolve/magnet",
        json={"magnet": "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567"},
    )
    assert no_csrf.status_code == 403
    assert no_csrf.json()["code"] == "invalid_csrf"

    # Mutating request WITH mismatched Origin must be blocked (403)
    bad_origin = await client.post(
        "/api/v1/resolve/magnet",
        json={"magnet": "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567"},
        headers={"X-CSRF-Token": csrf_token, "Origin": "https://evil.example.com"},
    )
    assert bad_origin.status_code == 403
    assert bad_origin.json()["code"] == "invalid_origin"

    # Logout with valid CSRF destroys server-side session
    logout = await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf_token})
    assert logout.status_code == 200
    me_after = await client.get("/api/v1/auth/me")
    assert me_after.status_code == 401


async def test_login_rate_limiting(client: httpx.AsyncClient) -> None:
    # Configured limit in conftest is 3 failures
    r1 = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong1"})
    assert r1.status_code == 401
    r2 = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong2"})
    assert r2.status_code == 401
    r3 = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong3"})
    assert r3.status_code == 429
    assert r3.json()["code"] == "rate_limited"
    assert int(r3.headers["retry-after"]) >= 1

    # Even valid password is blocked while rate-limited
    r4 = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "SuperSecret#2026"},
    )
    assert r4.status_code == 429


async def test_startup_rejects_missing_password(tmp_path) -> None:
    from app.config import AppConfig
    from app.main import create_app

    cfg = AppConfig(
        webui_username="admin",
        webui_password="",
        webui_password_hash="",
        webui_data_dir=tmp_path / "data",
    )
    with pytest.raises(RuntimeError, match="WEBUI_PASSWORD"):
        create_app(cfg)
