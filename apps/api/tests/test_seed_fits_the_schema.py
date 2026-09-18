"""Check every string the demo seed inserts against the column it goes into.

This file exists because of a bug that reached CI: the demo manifest's
``source_format`` is 50 characters and the column is ``VARCHAR(48)``, so seeding
died with ``value too long for type character varying(48)``. Nothing local caught
it. The seed only runs against PostgreSQL, the PostgreSQL tests skip unless
``RUN_POSTGRES_TESTS`` is set, and SQLite -- which is what a developer has by
default -- ignores ``VARCHAR`` lengths entirely.

The narrow fix would have been to widen that one column. This instead walks every
model instance the seed builds and compares every string against its own column's
declared length, so the next field somebody edits past its limit fails here, in a
second, without a database.

It works by handing ``seed_database`` a stand-in that records what it is asked to
persist rather than persisting it. The seed only ever calls ``add``, ``scalar`` and
``flush``, which makes that cheap -- and if it grows a call this stand-in does not
implement, this test fails loudly rather than silently skipping the new rows.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import String, inspect
from sqlalchemy.orm import DeclarativeBase

from civiclens.bootstrap.policy import repository_root
from civiclens.infrastructure.db.seed import seed_database


class _RecordingSession:
    """Collects what the seed would persist, and answers its two queries.

    ``scalar`` returns None and 0, which is what an empty database would say: no
    existing snapshot, no existing rows. That drives the seed down its insert path,
    which is the path with the values worth checking.
    """

    def __init__(self) -> None:
        self.added: list[DeclarativeBase] = []

    def add(self, instance: DeclarativeBase) -> None:
        self.added.append(instance)

    def scalar(self, statement: Any) -> Any:
        # The seed asks for an existing snapshot first, then for row counts. Both
        # answers here mean "nothing is loaded yet".
        del statement
        return None

    def flush(self) -> None:
        return None


def _collected() -> list[DeclarativeBase]:
    session = _RecordingSession()
    result = seed_database(session, repository_root())  # pyright: ignore[reportArgumentType]
    assert result.inserted, "the recording session should have driven the insert path"
    return session.added


def _string_columns(instance: DeclarativeBase) -> list[tuple[str, int, str]]:
    """Every (column, limit, value) triple on this row that has a length to exceed.

    Columns are read off the mapper rather than from a hand-written list, so a new
    column is covered the moment it is declared -- which is the only way a guard
    like this stays true a year from now.
    """
    mapper = inspect(type(instance))
    found: list[tuple[str, int, str]] = []
    for column in mapper.columns:
        if not isinstance(column.type, String) or column.type.length is None:
            continue
        value = getattr(instance, column.key, None)
        if isinstance(value, str):
            found.append((f"{instance.__tablename__}.{column.key}", column.type.length, value))
    return found


def test_every_seeded_string_fits_its_column() -> None:
    overflows = [
        f"{name} is VARCHAR({limit}) but the seed supplies {len(value)} characters"
        for instance in _collected()
        for name, limit, value in _string_columns(instance)
        if len(value) > limit
    ]

    # Reported all at once rather than failing on the first. A width mismatch is
    # usually a batch of them -- one edited manifest, several fields -- and fixing
    # them one CI run at a time wastes a quarter of an hour each.
    assert not overflows, "Seed values exceed their column widths:\n  " + "\n  ".join(overflows)


def test_the_guard_is_actually_inspecting_rows() -> None:
    """Guard the guard.

    If ``seed_database`` ever stops calling ``add`` -- switched to a bulk insert,
    say -- the test above would collect nothing and pass while checking nothing.
    That is a worse failure than the bug it is here to catch, because it looks like
    success.
    """
    collected = _collected()

    assert len(collected) > 60, f"expected the full demo seed, collected {len(collected)} rows"
    checked = [triple for instance in collected for triple in _string_columns(instance)]
    assert len(checked) > 100, f"expected many string columns to check, found {len(checked)}"


@pytest.mark.parametrize("table", ["dataset_snapshot", "report", "incident"])
def test_the_seed_populates_the_tables_this_demo_is_about(table: str) -> None:
    """A row count of zero for any of these means the seed silently stopped early."""
    assert any(instance.__tablename__ == table for instance in _collected())
