"""Shared fixtures including a stateful mock Openlist-Ani HTTP backend."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.config import AppConfig
from app.main import create_app
from app.security import hash_password


class MockOpenlistAni:
    """Faithful mock of TwooSix/Openlist-Ani HTTP API for deterministic testing."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Any]] = []
        self.ready: bool = True
        self.health_status: str = "ready"
        self.degraded: dict[str, str] = {}
        self.raise_error: Exception | None = None
        self.tasks: dict[str, dict[str, Any]] = {}
        self.preflight_conflicts: list[dict[str, Any]] = []
        self.preflight_warnings: list[str] = []
        self.preflight_blocked_message: str | None = None
        self.resolve_magnet_override: dict[str, Any] | None = None
        self.resolve_torrent_override: dict[str, Any] | None = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        body: Any = None
        if request.content:
            try:
                body = json.loads(request.content.decode("utf-8"))
            except ValueError:
                body = request.content.decode("utf-8", errors="replace")
        self.calls.append((request.method, request.url.path, body))

        if self.raise_error is not None:
            raise self.raise_error

        path = request.url.path
        method = request.method

        if method == "GET" and path == "/health/live":
            return httpx.Response(200, json={"status": "live"})

        if method == "GET" and path == "/health/ready":
            payload = {
                "status": self.health_status,
                "ready": self.ready,
                "degraded": self.degraded,
                "workers": {"running": 3 if self.ready else 2, "expected": 3},
            }
            return httpx.Response(200 if self.ready else 503, json=payload)

        if method == "POST" and path == "/api/resolve_magnet":
            if self.resolve_magnet_override is not None:
                return httpx.Response(200, json=self.resolve_magnet_override)
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "message": "Resolved magnet metadata",
                    "title": "[LoliHouse] Sousou no Frieren - 01 [WebRip 1080p HEVC-10bit AAC SRTx2]",
                    "source": "metadata",
                    "error_code": None,
                    "file_count": 2,
                    "files": [
                        {
                            "name": "[LoliHouse] Sousou no Frieren - 01 [WebRip 1080p].mkv",
                            "size": 734_003_200,
                        },
                        {
                            "name": "[LoliHouse] Sousou no Frieren - 01 [WebRip 1080p].ass",
                            "size": 124_500,
                        },
                    ],
                },
            )

        if method == "POST" and path == "/api/resolve_torrent":
            if self.resolve_torrent_override is not None:
                return httpx.Response(200, json=self.resolve_torrent_override)
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "message": "Resolved torrent metadata",
                    "title": "[ANi] Dungeon Meshi - 01-24 [BDRip 1080p]",
                    "source": "torrent_file",
                    "error_code": None,
                    "file_count": 3,
                    "files": [
                        {"name": "Dungeon Meshi/01.mkv", "size": 524_288_000},
                        {"name": "Dungeon Meshi/02.mkv", "size": 530_000_000},
                        {"name": "Dungeon Meshi/readme.txt", "size": 1024},
                    ],
                },
            )

        if method == "POST" and path == "/api/downloads/preflight":
            if self.preflight_blocked_message:
                return httpx.Response(
                    200,
                    json={
                        "success": False,
                        "message": self.preflight_blocked_message,
                        "confirmation_required": False,
                        "policy_conflicts": [],
                        "policy_warnings": [],
                        "policy_review_token": None,
                    },
                )
            if self.preflight_conflicts:
                return httpx.Response(
                    200,
                    json={
                        "success": True,
                        "message": "Manual download requires confirmation for automatic policy conflicts.",
                        "confirmation_required": True,
                        "policy_conflicts": self.preflight_conflicts,
                        "policy_warnings": self.preflight_warnings,
                        "policy_review_token": "tok_review_123456",
                    },
                )
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "message": "Manual download passed automatic policy review.",
                    "confirmation_required": False,
                    "policy_conflicts": [],
                    "policy_warnings": self.preflight_warnings,
                    "policy_review_token": None,
                },
            )

        if method == "POST" and path == "/api/downloads":
            if self.preflight_conflicts:
                acked = set(body.get("acknowledged_conflicts") or [])
                needed = {item["key"] for item in self.preflight_conflicts}
                if (
                    not body.get("override_policy")
                    or not needed.issubset(acked)
                    or body.get("policy_review_token") != "tok_review_123456"
                ):
                    return httpx.Response(
                        200,
                        json={
                            "success": False,
                            "message": "Manual download requires policy confirmation.",
                            "task": None,
                            "confirmation_required": True,
                            "policy_conflicts": self.preflight_conflicts,
                            "policy_warnings": self.preflight_warnings,
                            "policy_review_token": "tok_review_123456",
                        },
                    )
            task_id = f"task-{len(self.tasks) + 1:04d}"
            task = {
                "id": task_id,
                "title": body["title"],
                "download_url": body["download_url"],
                "state": "downloading",
                "anime_name": "葬送的芙莉莲",
                "season": 1,
                "episode": None if body.get("collection_hint") else 1,
                "fansub": "LoliHouse",
                "quality": "1080p",
                "error_message": None,
                "retry_count": 0,
                "created_at": "2026-11-21T10:00:00+00:00",
                "updated_at": "2026-11-21T10:00:05+00:00",
                "started_at": "2026-11-21T10:00:01+00:00",
                "completed_at": None,
                "save_path": "/PikPak/Anime",
                "final_path": None,
                "final_paths": [],
                "warning_count": 0,
                "items": [],
            }
            self.tasks[task_id] = task
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "message": f"Manual download queued: {body['title']}",
                    "task": task,
                    "confirmation_required": False,
                    "policy_conflicts": [],
                    "policy_warnings": [],
                    "policy_review_token": None,
                },
            )

        if method == "GET" and path == "/api/downloads":
            # Faithfully mirror Openlist-Ani: exclude completed & cancelled tasks from GET /api/downloads
            visible = [
                t
                for t in self.tasks.values()
                if t["state"] not in {"completed", "cancelled"}
            ]
            return httpx.Response(200, json={"tasks": visible, "total": len(visible)})

        if method == "GET" and path.startswith("/api/downloads/"):
            task_id = path.split("/api/downloads/", 1)[1]
            task = self.tasks.get(task_id)
            if task is None:
                return httpx.Response(404, json={"detail": f"Task not found: {task_id}"})
            return httpx.Response(200, json=task)

        return httpx.Response(404, json={"detail": "Not Found"})


@pytest.fixture
def mock_upstream() -> MockOpenlistAni:
    return MockOpenlistAni()


@pytest.fixture
def test_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        openlist_ani_url="http://openlist-ani.internal:26666",
        openlist_ani_timeout=15.0,
        webui_username="admin",
        webui_password="",
        webui_password_hash=hash_password("SuperSecret#2026"),
        webui_data_dir=tmp_path / "data",
        webui_cookie_secure="false",
        webui_login_rate_limit_max=3,
        webui_login_rate_limit_window_seconds=60,
    )


@pytest.fixture
def app(test_config: AppConfig, mock_upstream: MockOpenlistAni):
    transport = httpx.MockTransport(mock_upstream.handler)
    return create_app(test_config, upstream_transport=transport)


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.fixture
async def authed_client(client: httpx.AsyncClient) -> tuple[httpx.AsyncClient, str]:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "SuperSecret#2026"},
    )
    assert resp.status_code == 200
    csrf_token = resp.json()["csrf_token"]
    return client, csrf_token
