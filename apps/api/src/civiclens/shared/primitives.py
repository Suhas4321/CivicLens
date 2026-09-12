from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdGenerator(Protocol):
    def new(self) -> UUID: ...


@dataclass(frozen=True)
class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass(frozen=True)
class FixedClock:
    value: datetime

    def now(self) -> datetime:
        if self.value.tzinfo is None:
            raise ValueError("FixedClock requires a timezone-aware datetime")
        return self.value


@dataclass(frozen=True)
class RandomIdGenerator:
    def new(self) -> UUID:
        return uuid4()


def stable_id(kind: str, logical_key: str) -> UUID:
    """Produce stable seed IDs without using them as public capabilities."""

    return uuid5(NAMESPACE_URL, f"https://civiclens.local/{kind}/{logical_key}")
