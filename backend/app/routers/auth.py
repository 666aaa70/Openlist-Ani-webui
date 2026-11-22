"""Authentication endpoints: login (rate-limited), logout, and current session inspection."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from ..config import AppConfig
from ..dependencies import (
    get_client_ip,
    get_config,
    get_rate_limiter,
    get_store,
    require_csrf,
    require_session,
)
from ..schemas import AuthUserResponse, LoginRequest, LogoutResponse
from ..security import (
    LoginRateLimiter,
    is_secure_request,
    validate_request_origin,
    verify_password,
    verify_username,
)
from ..storage import SessionRecord, StateStore

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=AuthUserResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    config: AppConfig = Depends(get_config),
    store: StateStore = Depends(get_store),
    limiter: LoginRateLimiter = Depends(get_rate_limiter),
    client_ip: str = Depends(get_client_ip),
) -> AuthUserResponse:
    if not validate_request_origin(request, config):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "invalid_origin", "message": "请求来源校验失败"},
        )

    allowed, retry_after = limiter.check(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "rate_limited",
                "message": f"登录尝试过于频繁，请在 {retry_after} 秒后重试",
                "details": {"retry_after": retry_after},
            },
            headers={"Retry-After": str(retry_after)},
        )

    username_ok = verify_username(payload.username, config.webui_username)
    password_ok = verify_password(
        payload.password,
        configured_password=config.webui_password,
        configured_hash=config.webui_password_hash,
    )

    if not (username_ok and password_ok):
        still_allowed, lock_retry = limiter.record_failure(client_ip)
        if not still_allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "rate_limited",
                    "message": f"连续登录失败次数过多，请在 {lock_retry} 秒后重试",
                    "details": {"retry_after": lock_retry},
                },
                headers={"Retry-After": str(lock_retry)},
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials", "message": "用户名或密码错误"},
        )

    limiter.reset(client_ip)

    # Rotate any previous session cookie to prevent session fixation
    old_cookie = request.cookies.get(config.webui_session_cookie_name)
    if old_cookie:
        store.delete_session(old_cookie)

    raw_token, session = store.create_session(
        username=config.webui_username,
        ttl_seconds=config.webui_session_ttl_seconds,
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent", ""),
    )

    response.set_cookie(
        key=config.webui_session_cookie_name,
        value=raw_token,
        max_age=config.webui_session_ttl_seconds,
        httponly=True,
        secure=is_secure_request(request, config),
        samesite="lax",
        path="/",
    )

    return AuthUserResponse(
        authenticated=True,
        username=session.username,
        csrf_token=session.csrf_token,
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    response: Response,
    _session: SessionRecord = Depends(require_csrf),
    config: AppConfig = Depends(get_config),
    store: StateStore = Depends(get_store),
) -> LogoutResponse:
    raw_token = request.cookies.get(config.webui_session_cookie_name)
    if raw_token:
        store.delete_session(raw_token)
    response.delete_cookie(
        key=config.webui_session_cookie_name,
        path="/",
        httponly=True,
        samesite="lax",
    )
    return LogoutResponse(success=True, message="已安全退出登录")


@router.get("/me", response_model=AuthUserResponse)
async def me(
    session: SessionRecord = Depends(require_session),
) -> AuthUserResponse:
    return AuthUserResponse(
        authenticated=True,
        username=session.username,
        csrf_token=session.csrf_token,
    )
