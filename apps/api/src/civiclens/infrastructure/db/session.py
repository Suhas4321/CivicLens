from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, Table, create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from civiclens.bootstrap.settings import Settings


class DependencyOrderedSession(Session):
    """A session that inserts referenced rows before the rows that reference them.

    This exists because SQLAlchemy cannot work that order out for this schema, and the
    reason is invisible in the code that looks wrong. The unit of work orders INSERTs
    by the dependencies it learns from ``relationship()`` declarations. These models
    declare none -- deliberately: it is an append-only audit layout whose readers join
    explicitly, and ORM relationships would bring lazy loads and cascades that have no
    business in it. Table-level ``ForeignKey`` declarations do not inform the flush.
    With nothing to sort by, SQLAlchemy falls back to the mappers' own sort keys, which
    are alphabetical by class name -- so ``ProcessingJobModel`` and
    ``IncidentReportLinkModel`` rows were handed to PostgreSQL before the
    ``ReportModel`` rows they point at, and every write path that touched more than one
    table died on a foreign key.

    It went unnoticed for so long because SQLite does not enforce foreign keys unless
    asked to, and SQLite is what a developer has by default here. The failure only
    appeared against PostgreSQL, which is only reached in CI.

    Fixed in the session rather than at each call site on purpose. The per-call-site
    version had already been written twice -- once in the seed and once, missing, in
    the intake repository -- which is the shape of a fix that will be forgotten by
    whoever adds the third write path.

    Only INSERT ordering is corrected. Deletes would need the reverse order, and are
    left alone because nothing in this application deletes a row through the ORM; an
    append-only schema supersedes rows instead. If that changes, this is where it has
    to be handled.
    """

    def flush(self, objects: Sequence[Any] | None = None) -> None:
        if objects is not None:
            # An explicit subset is the caller stating an order of their own.
            super().flush(objects)
            return

        for batch in self._pending_in_dependency_order():
            super().flush(batch)

        # Updates, and anything the staging above could not place. A no-op when the
        # session is already clean, which it usually is by this point -- but a silent
        # skip here would be a row the caller believes was written and never was.
        super().flush()

    def _pending_in_dependency_order(self) -> list[list[Any]]:
        """The rows waiting to be inserted, grouped by table, referenced tables first.

        The order comes from ``MetaData.sorted_tables``: SQLAlchemy's own topological
        sort of the tables by their foreign keys, and the same order ``create_all``
        uses to decide what to create first. Deriving it from the keys rather than from
        a hand-written list means a table added to the schema later is ordered
        correctly here without anyone remembering to come back.

        The metadata is reached through the pending objects' own tables rather than
        through ``Base``, so this holds for any mapped class and needs no import that
        would only be correct as long as every model lives in one place.
        """

        by_table: dict[Table, list[Any]] = defaultdict(list)
        for instance in self.new:
            by_table[inspect(instance).mapper.local_table].append(instance)
        if len(by_table) < 2:
            # One table cannot be out of order with itself, and the empty case is the
            # common one -- a flush that only updates.
            return list(by_table.values())

        batches: list[list[Any]] = []
        for metadata in dict.fromkeys(table.metadata for table in by_table):
            batches.extend(by_table[table] for table in metadata.sorted_tables if table in by_table)
        return batches


def build_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=2,
        pool_recycle=1800,
    )


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(
        bind=engine,
        class_=DependencyOrderedSession,
        autoflush=False,
        expire_on_commit=False,
    )


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
