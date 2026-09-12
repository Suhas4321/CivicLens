from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from threading import Lock
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select

from civiclens.bootstrap.settings import get_settings
from civiclens.infrastructure.db.models import DemoSessionModel
from civiclens.infrastructure.db.session import build_engine, build_session_factory
from civiclens.shared.errors import NotFoundError


@dataclass(frozen=True)
class DemoSession:
    id: UUID
    subject_hash: str
    created_at: datetime
    expires_at: datetime
    status: str = "active"


@dataclass(frozen=True)
class NewDemoSession:
    session: DemoSession
    access_token: str


class DemoSessionPort(Protocol):
    def create(self) -> NewDemoSession: ...

    def authenticate(self, session_id: UUID, access_token: str) -> DemoSession: ...


class DemoSessionService:
    """Memory adapter for judge preview; PostgreSQL/Firebase replaces it for deployment."""

    def __init__(self, ttl_minutes: int) -> None:
        self._ttl = timedelta(minutes=ttl_minutes)
        self._sessions: dict[UUID, DemoSession] = {}
        self._lock = Lock()

    def create(self) -> NewDemoSession:
        token = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        session = DemoSession(
            id=uuid4(),
            subject_hash=_hash_token(token),
            created_at=now,
            expires_at=now + self._ttl,
        )
        with self._lock:
            self._sessions[session.id] = session
        return NewDemoSession(session=session, access_token=token)

    def authenticate(self, session_id: UUID, access_token: str) -> DemoSession:
        with self._lock:
            session = self._sessions.get(session_id)
        if (
            session is None
            or session.status != "active"
            or session.expires_at <= datetime.now(UTC)
            or not hmac.compare_digest(session.subject_hash, _hash_token(access_token))
        ):
            raise NotFoundError("Demo session not found")
        return session


class SqlDemoSessionService:
    def __init__(self, ttl_minutes: int) -> None:
        settings = get_settings()
        self._ttl = timedelta(minutes=ttl_minutes)
        self._session_factory = build_session_factory(build_engine(settings))

    def create(self) -> NewDemoSession:
        token = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        session = DemoSession(
            id=uuid4(),
            subject_hash=_hash_token(token),
            created_at=now,
            expires_at=now + self._ttl,
        )
        with self._session_factory.begin() as database:
            database.add(
                DemoSessionModel(
                    id=session.id,
                    external_subject_hash=session.subject_hash,
                    status=session.status,
                    created_at=session.created_at,
                    expires_at=session.expires_at,
                )
            )
        return NewDemoSession(session=session, access_token=token)

    def authenticate(self, session_id: UUID, access_token: str) -> DemoSession:
        with self._session_factory() as database:
            model = database.scalar(
                select(DemoSessionModel).where(DemoSessionModel.id == session_id)
            )
            if model is None:
                raise NotFoundError("Demo session not found")
            session = DemoSession(
                id=model.id,
                subject_hash=model.external_subject_hash,
                created_at=model.created_at,
                expires_at=model.expires_at,
                status=model.status,
            )
        if (
            session.status != "active"
            or session.expires_at <= datetime.now(UTC)
            or not hmac.compare_digest(session.subject_hash, _hash_token(access_token))
        ):
            raise NotFoundError("Demo session not found")
        return session


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@lru_cache
def get_demo_session_service() -> DemoSessionPort:
    settings = get_settings()
    if settings.session_backend == "postgres":
        return SqlDemoSessionService(settings.demo_session_ttl_minutes)
    return DemoSessionService(settings.demo_session_ttl_minutes)
