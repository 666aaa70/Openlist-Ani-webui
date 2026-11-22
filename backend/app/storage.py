"""SQLite persistence for server-side sessions, runtime settings, and observed task IDs."""

from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .config import AppConfig
from .security import generate_token, hash_session_token, validate_upstream_url


@dataclass(frozen=True)
class SessionRecord:
    token_hash: str
    username: str
    csrf_token: str
    created_at: int
    expires_at: int
    last_seen_at: int


@dataclass(frozen=True)
class StoredSettings:
    upstream_url: str
    api_timeout_seconds: float
    poll_interval_seconds: int
    theme: Literal["dark", "light"]
    language: Literal["zh-CN", "en-US"]


@dataclass(frozen=True)
class TrackedTaskRecord:
    task_id: str
    last_state: str
    first_seen_at: int
    last_seen_at: int
    payload_json: str = ""


class StateStore:
    """Thread-safe SQLite store for WebUI server state."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._db_path: Path = config.db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    csrf_token TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    last_seen_at INTEGER NOT NULL,
                    ip_address TEXT NOT NULL DEFAULT '',
                    user_agent TEXT NOT NULL DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_sessions_expires_at
                    ON sessions(expires_at);

                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tracked_tasks (
                    task_id TEXT PRIMARY KEY,
                    last_state TEXT NOT NULL DEFAULT 'pending',
                    first_seen_at INTEGER NOT NULL,
                    last_seen_at INTEGER NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_tracked_tasks_last_seen
                    ON tracked_tasks(last_seen_at DESC);
                """
            )
            # Safe schema migration for existing DBs created before payload_json existed
            columns = {
                str(row["name"])
                for row in conn.execute("PRAGMA table_info(tracked_tasks)").fetchall()
            }
            if "payload_json" not in columns:
                conn.execute(
                    "ALTER TABLE tracked_tasks ADD COLUMN payload_json TEXT NOT NULL DEFAULT ''"
                )

    # ── Sessions ──────────────────────────────────────────────────────

    def create_session(
        self,
        *,
        username: str,
        ttl_seconds: int,
        ip_address: str = "",
        user_agent: str = "",
    ) -> tuple[str, SessionRecord]:
        now = int(time.time())
        raw_token = generate_token(32)
        token_hash = hash_session_token(raw_token)
        csrf_token = generate_token(32)
        expires_at = now + ttl_seconds

        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
            conn.execute(
                """
                INSERT INTO sessions (
                    token_hash, username, csrf_token,
                    created_at, expires_at, last_seen_at,
                    ip_address, user_agent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    token_hash,
                    username,
                    csrf_token,
                    now,
                    expires_at,
                    now,
                    ip_address[:128],
                    user_agent[:256],
                ),
            )

        return raw_token, SessionRecord(
            token_hash=token_hash,
            username=username,
            csrf_token=csrf_token,
            created_at=now,
            expires_at=expires_at,
            last_seen_at=now,
        )

    def get_session(self, raw_token: str) -> SessionRecord | None:
        if not raw_token:
            return None
        token_hash = hash_session_token(raw_token)
        now = int(time.time())
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT token_hash, username, csrf_token, created_at, expires_at, last_seen_at
                FROM sessions
                WHERE token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
            if row is None:
                return None
            if int(row["expires_at"]) <= now:
                conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
                return None
            prev_seen = int(row["last_seen_at"])
            effective_seen = prev_seen
            # Throttle SQLite write amplification during 5s polling
            if now - prev_seen >= 60:
                conn.execute(
                    "UPDATE sessions SET last_seen_at = ? WHERE token_hash = ?",
                    (now, token_hash),
                )
                effective_seen = now
            return SessionRecord(
                token_hash=str(row["token_hash"]),
                username=str(row["username"]),
                csrf_token=str(row["csrf_token"]),
                created_at=int(row["created_at"]),
                expires_at=int(row["expires_at"]),
                last_seen_at=effective_seen,
            )

    def delete_session(self, raw_token: str) -> None:
        if not raw_token:
            return
        token_hash = hash_session_token(raw_token)
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))

    # ── Runtime Settings ──────────────────────────────────────────────

    def get_settings(self) -> StoredSettings:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
        raw = {str(row["key"]): str(row["value"]) for row in rows}

        upstream_url = raw.get("upstream_url") or self._config.openlist_ani_url
        try:
            upstream_url = validate_upstream_url(
                upstream_url,
                allowed_hosts=self._config.allowed_upstream_hosts_set,
            )
        except ValueError:
            upstream_url = self._config.openlist_ani_url.rstrip("/")

        try:
            timeout = float(raw.get("api_timeout_seconds", self._config.openlist_ani_timeout))
            timeout = max(3.0, min(300.0, timeout))
        except ValueError:
            timeout = self._config.openlist_ani_timeout

        try:
            poll_interval = int(
                raw.get("poll_interval_seconds", self._config.webui_default_poll_interval)
            )
            poll_interval = max(2, min(120, poll_interval))
        except ValueError:
            poll_interval = self._config.webui_default_poll_interval

        theme_raw = raw.get("theme", self._config.webui_default_theme)
        theme: Literal["dark", "light"] = "light" if theme_raw == "light" else "dark"

        lang_raw = raw.get("language", self._config.webui_default_language)
        language: Literal["zh-CN", "en-US"] = "en-US" if lang_raw == "en-US" else "zh-CN"

        return StoredSettings(
            upstream_url=upstream_url,
            api_timeout_seconds=timeout,
            poll_interval_seconds=poll_interval,
            theme=theme,
            language=language,
        )

    def update_settings(
        self,
        *,
        upstream_url: str | None = None,
        api_timeout_seconds: float | None = None,
        poll_interval_seconds: int | None = None,
        theme: Literal["dark", "light"] | None = None,
        language: Literal["zh-CN", "en-US"] | None = None,
    ) -> StoredSettings:
        updates: dict[str, str] = {}
        if upstream_url is not None:
            normalized = validate_upstream_url(
                upstream_url,
                allowed_hosts=self._config.allowed_upstream_hosts_set,
            )
            updates["upstream_url"] = normalized
        if api_timeout_seconds is not None:
            updates["api_timeout_seconds"] = str(round(float(api_timeout_seconds), 1))
        if poll_interval_seconds is not None:
            updates["poll_interval_seconds"] = str(int(poll_interval_seconds))
        if theme is not None:
            updates["theme"] = theme
        if language is not None:
            updates["language"] = language

        if updates:
            now = int(time.time())
            with self._lock, self._connect() as conn:
                for key, value in updates.items():
                    conn.execute(
                        """
                        INSERT INTO app_settings (key, value, updated_at)
                        VALUES (?, ?, ?)
                        ON CONFLICT(key) DO UPDATE SET
                            value = excluded.value,
                            updated_at = excluded.updated_at
                        """,
                        (key, value, now),
                    )
        return self.get_settings()

    # ── Observed Task Tracking ────────────────────────────────────────
    # Openlist-Ani's GET /api/downloads intentionally excludes completed/cancelled
    # tasks, whereas GET /api/downloads/{task_id} still serves them. Recording real
    # task IDs observed by WebUI lets us fetch genuine completed/cancelled status
    # strictly from Openlist-Ani's official GET /api/downloads/{task_id} endpoint.

    def record_tasks(self, entries: list[tuple[str, str, str | None]]) -> None:
        if not entries:
            return
        now = int(time.time())
        with self._lock, self._connect() as conn:
            for task_id, state, payload_json in entries:
                payload = payload_json or ""
                conn.execute(
                    """
                    INSERT INTO tracked_tasks (
                        task_id, last_state, first_seen_at, last_seen_at, payload_json
                    )
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(task_id) DO UPDATE SET
                        last_state = excluded.last_state,
                        last_seen_at = excluded.last_seen_at,
                        payload_json = CASE
                            WHEN excluded.payload_json != '' THEN excluded.payload_json
                            ELSE tracked_tasks.payload_json
                        END
                    """,
                    (task_id, state, now, now, payload),
                )
            # Keep bounded history (most recent 200 observed tasks)
            conn.execute(
                """
                DELETE FROM tracked_tasks
                WHERE task_id NOT IN (
                    SELECT task_id FROM tracked_tasks
                    ORDER BY last_seen_at DESC
                    LIMIT 200
                )
                """
            )

    def list_tracked_task_ids(self, limit: int = 100) -> list[TrackedTaskRecord]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT task_id, last_state, first_seen_at, last_seen_at, payload_json
                FROM tracked_tasks
                ORDER BY last_seen_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            TrackedTaskRecord(
                task_id=str(row["task_id"]),
                last_state=str(row["last_state"]),
                first_seen_at=int(row["first_seen_at"]),
                last_seen_at=int(row["last_seen_at"]),
                payload_json=str(row["payload_json"] or ""),
            )
            for row in rows
        ]

    def remove_tracked_task(self, task_id: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM tracked_tasks WHERE task_id = ?", (task_id,))
