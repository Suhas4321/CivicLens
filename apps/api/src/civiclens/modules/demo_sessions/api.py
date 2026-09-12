from __future__ import annotations

from fastapi import APIRouter, status

from civiclens.modules.demo_sessions.schemas import DemoSessionCreated
from civiclens.modules.demo_sessions.service import get_demo_session_service

router = APIRouter(prefix="/demo-sessions", tags=["demo-sessions"])


@router.post("", response_model=DemoSessionCreated, status_code=status.HTTP_201_CREATED)
async def create_demo_session() -> DemoSessionCreated:
    created = get_demo_session_service().create()
    return DemoSessionCreated(
        session_id=created.session.id,
        access_token=created.access_token,
        expires_at=created.session.expires_at,
    )
