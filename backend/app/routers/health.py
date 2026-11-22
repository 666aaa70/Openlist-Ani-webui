"""Health endpoints for container probes and authenticated upstream status checks."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..dependencies import get_upstream, require_session
from ..schemas import ServiceHealthResponse
from ..storage import SessionRecord
from ..upstream import OpenlistAniClient

router = APIRouter(prefix="/api/v1/health", tags=["health"])


@router.get("/live")
async def webui_live() -> dict[str, str]:
    """Unauthenticated liveness probe for Docker / 1Panel healthchecks (leaks zero internal data)."""
    return {"status": "live"}


@router.get("", response_model=ServiceHealthResponse)
async def service_health(
    _session: SessionRecord = Depends(require_session),
    upstream: OpenlistAniClient = Depends(get_upstream),
) -> ServiceHealthResponse:
    """Return real Openlist-Ani live/ready/worker health status."""
    return await upstream.check_health()
