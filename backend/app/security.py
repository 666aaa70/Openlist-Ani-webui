"""Security primitives: password hashing, CSRF, URL validation, and login rate limiting."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import sys
import threading
import time
from collections import defaultdict, deque
from urllib.parse import urlparse

from fastapi import Request

from .config import AppConfig

_TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def hash_password(password: str) -> str:
    """Hash a password using Python's stdlib scrypt (zero native build dependencies)."""
    salt = secrets.token_bytes(16)
    n, r, p = 2**14, 8, 1
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=32,
    )
    salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii")
    digest_b64 = base64.urlsafe_b64encode(digest).decode("ascii")
    return f"scrypt${n}${r}${p}${salt_b64}${digest_b64}"


def verify_password(plain_password: str, *, configured_password: str, configured_hash: str) -> bool:
    """Verify password in constant time against either a stored hash or env plaintext."""
    if configured_hash:
        return _verify_password_hash(plain_password, configured_hash)
    if configured_password:
        # Compare SHA-256 digests so lengths are never leaked by timing.
        a = hashlib.sha256(plain_password.encode("utf-8")).digest()
        b = hashlib.sha256(configured_password.encode("utf-8")).digest()
        return hmac.compare_digest(a, b)
    return False


def _verify_password_hash(plain_password: str, encoded: str) -> bool:
    parts = encoded.split("$")
    try:
        if len(parts) == 6 and parts[0] == "scrypt":
            n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
            salt = base64.urlsafe_b64decode(parts[4].encode("ascii"))
            expected = base64.urlsafe_b64decode(parts[5].encode("ascii"))
            actual = hashlib.scrypt(
                plain_password.encode("utf-8"),
                salt=salt,
                n=n,
                r=r,
                p=p,
                dklen=len(expected),
            )
            return hmac.compare_digest(actual, expected)
        if len(parts) == 4 and parts[0] == "pbkdf2_sha256":
            iterations = int(parts[1])
            salt = base64.urlsafe_b64decode(parts[2].encode("ascii"))
            expected = base64.urlsafe_b64decode(parts[3].encode("ascii"))
            actual = hashlib.pbkdf2_hmac(
                "sha256",
                plain_password.encode("utf-8"),
                salt,
                iterations,
                dklen=len(expected),
            )
            return hmac.compare_digest(actual, expected)
    except Exception:
        return False
    return False


def verify_username(provided: str, expected: str) -> bool:
    a = hashlib.sha256(provided.strip().encode("utf-8")).digest()
    b = hashlib.sha256(expected.strip().encode("utf-8")).digest()
    return hmac.compare_digest(a, b)


def generate_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_session_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def verify_csrf_token(provided: str | None, expected: str) -> bool:
    if not provided or not expected:
        return False
    return hmac.compare_digest(provided, expected)


def validate_task_id(task_id: str) -> str:
    """Strictly validate task_id to prevent SSRF / path traversal."""
    if not _TASK_ID_PATTERN.fullmatch(task_id):
        raise ValueError("无效的任务 ID 格式")
    return task_id


def validate_upstream_url(
    raw_url: str,
    *,
    allowed_hosts: frozenset[str] = frozenset(),
) -> str:
    """Validate and normalize the internal Openlist-Ani base URL."""
    url = raw_url.strip().rstrip("/")
    if not url:
        raise ValueError("Openlist-Ani 服务地址不能为空")
    if any(ch.isspace() for ch in url):
        raise ValueError("Openlist-Ani 服务地址不能包含空白字符")

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Openlist-Ani 服务地址仅支持 http:// 或 https:// 协议")
    if not parsed.hostname:
        raise ValueError("Openlist-Ani 服务地址缺少有效主机名")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Openlist-Ani 服务地址不允许内嵌认证凭据")
    if parsed.query or parsed.fragment:
        raise ValueError("Openlist-Ani 服务地址不能包含查询参数或锚点")
    if parsed.path not in {"", "/"}:
        # Allow a clean sub-path prefix only if no dot-segments exist
        segments = [seg for seg in parsed.path.split("/") if seg]
        if any(seg in {".", ".."} for seg in segments):
            raise ValueError("Openlist-Ani 服务地址路径不合法")

    try:
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("Openlist-Ani 服务地址端口号无效") from exc

    host_lower = parsed.hostname.lower()
    if allowed_hosts and host_lower not in allowed_hosts:
        raise ValueError("该主机不在服务端允许的 Openlist-Ani 上游白名单中")

    return url


def mask_upstream_url(url: str) -> str:
    """Return a redacted display string so internal addresses are not exposed to browsers."""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.hostname:
        return "未配置"
    port = parsed.port
    default_port = 443 if parsed.scheme == "https" else 80
    port_part = f":{port}" if port is not None else f":{default_port}"
    return f"{parsed.scheme}://••••{port_part}"


def extract_client_ip(request: Request, *, trust_proxy: bool) -> str:
    if trust_proxy:
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            first = xff.split(",")[0].strip()
            if first:
                return first
        real_ip = request.headers.get("x-real-ip", "").strip()
        if real_ip:
            return real_ip
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def is_secure_request(request: Request, config: AppConfig) -> bool:
    if config.webui_cookie_secure == "true":
        return True
    if config.webui_cookie_secure == "false":
        return False
    if config.webui_trust_proxy:
        proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
        if proto:
            return proto == "https"
    return request.url.scheme == "https"


def validate_request_origin(request: Request, config: AppConfig) -> bool:
    """Verify Origin/Referer matches request host or explicit allowed origins."""
    origin = request.headers.get("origin")
    if not origin:
        return True
    origin_normalized = origin.strip().rstrip("/").lower()
    if origin_normalized in config.allowed_origins_set:
        return True

    parsed_origin = urlparse(origin_normalized)
    if not parsed_origin.netloc:
        return False

    host_header = (
        request.headers.get("x-forwarded-host", "").split(",")[0].strip().lower()
        if config.webui_trust_proxy
        else ""
    ) or request.headers.get("host", "").strip().lower()

    if not host_header:
        return False

    return parsed_origin.netloc.lower() == host_header


class LoginRateLimiter:
    """In-memory sliding-window login failure limiter keyed by client IP."""

    def __init__(self, *, max_attempts: int = 5, window_seconds: int = 300) -> None:
        self._max_attempts = max(1, max_attempts)
        self._window_seconds = max(1, window_seconds)
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, *, now: float | None = None) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        current = time.monotonic() if now is None else now
        with self._lock:
            bucket = self._prune(key, current)
            if len(bucket) >= self._max_attempts:
                retry_after = max(1, int(self._window_seconds - (current - bucket[0])) + 1)
                return False, retry_after
            return True, 0

    def record_failure(self, key: str, *, now: float | None = None) -> tuple[bool, int]:
        """Record a failed login attempt and return (still_allowed, retry_after_seconds)."""
        current = time.monotonic() if now is None else now
        with self._lock:
            bucket = self._prune(key, current)
            bucket.append(current)
            if len(bucket) >= self._max_attempts:
                retry_after = max(1, int(self._window_seconds - (current - bucket[0])) + 1)
                return False, retry_after
            return True, 0

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def _prune(self, key: str, current: float) -> deque[float]:
        bucket = self._failures[key]
        cutoff = current - self._window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if not bucket and len(self._failures) > 4096:
            # Bound memory under spoofed-IP storms
            stale_keys = [
                k for k, v in self._failures.items() if not v or v[-1] <= cutoff
            ]
            for stale_key in stale_keys:
                self._failures.pop(stale_key, None)
            bucket = self._failures[key]
        return bucket


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "hash-password":
        print(hash_password(sys.argv[2]))
    else:
        print("Usage: python -m app.security hash-password <PASSWORD>", file=sys.stderr)
        sys.exit(1)
