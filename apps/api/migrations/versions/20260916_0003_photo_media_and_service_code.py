"""Allow photo media alongside voice, and record the reporter's chosen category.

Revision ID: 20260916_0003
Revises: 20260915_0002

``report_media`` was built for voice alone: ``media_type`` was pinned to
``'voice'`` by a CHECK constraint, ``duration_seconds`` was NOT NULL, and
``byte_size`` was capped at the 6 MB voice limit. A photo satisfies none of those.
This revision widens the table to hold either medium, adds the perceptual hash
that lets two photos of the same problem be recognised as the same problem, and
adds ``report.service_code`` for the category the reporter picked.

**Every step here is written to be safe to run against a database that already has
the new shape**, and that is not defensive habit -- it is required by how
``20260912_0001`` is written. That revision creates the schema with
``Base.metadata.create_all``, which reflects whatever the model classes say *at the
moment it runs*, not what they said in September. So a database created from
scratch today gets the relaxed ``report_media`` and the ``service_code`` column
directly out of 0001, and this revision then finds its work already done. An
existing database migrated in sequence finds the old shape and needs every step.
Both must succeed, so each step checks the catalogue first.

(That property of 0001 is worth fixing on its own -- a migration whose output
depends on code written after it is not really a migration -- but doing so here
would mean rewriting the initial revision as explicit DDL, which is a change to
already-deployed history and belongs in its own change.)
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text
from sqlalchemy.engine import Connection

revision = "20260916_0003"
down_revision = "20260915_0002"
branch_labels = None
depends_on = None

_MEDIA_TABLE = "report_media"


def upgrade() -> None:
    """Widen report_media to accept photos and add report.service_code."""

    bind = op.get_bind()

    # Dropped before the column changes below, because the old constraints
    # contradict them: `voice_only` would reject every photo row, and `duration_limit`
    # requires a value the photo branch must leave NULL.
    for name in ("voice_only", "byte_size_limit", "duration_limit"):
        _drop_constraint_if_exists(bind, _MEDIA_TABLE, name)

    if _has_column(bind, _MEDIA_TABLE, "duration_seconds"):
        op.alter_column(_MEDIA_TABLE, "duration_seconds", nullable=True)

    if not _has_column(bind, _MEDIA_TABLE, "perceptual_hash"):
        op.execute(f"ALTER TABLE {_MEDIA_TABLE} ADD COLUMN perceptual_hash VARCHAR(16)")

    # Coarse EXIF conclusions for officers. Never the EXIF itself -- see the column
    # comment in `ReportMediaModel`.
    if not _has_column(bind, _MEDIA_TABLE, "integrity_flags"):
        op.execute(f"ALTER TABLE {_MEDIA_TABLE} ADD COLUMN integrity_flags JSONB")

    if not _has_column(bind, "report", "service_code"):
        op.execute("ALTER TABLE report ADD COLUMN service_code VARCHAR(48)")

    # Added last, so they are checked against a table that can already satisfy
    # them. Each is created only if absent, because create_all may have supplied it.
    _add_check_if_absent(
        bind,
        _MEDIA_TABLE,
        "media_type_allowed",
        "media_type IN ('voice', 'photo')",
    )
    _add_check_if_absent(
        bind,
        _MEDIA_TABLE,
        "byte_size_limit",
        "byte_size BETWEEN 1 AND 12582912",
    )
    _add_check_if_absent(
        bind,
        _MEDIA_TABLE,
        "duration_matches_media_type",
        "(media_type = 'voice' AND duration_seconds BETWEEN 0 AND 30) "
        "OR (media_type = 'photo' AND duration_seconds IS NULL)",
    )
    _add_check_if_absent(
        bind,
        _MEDIA_TABLE,
        "perceptual_hash_matches_media_type",
        "(media_type = 'photo' AND perceptual_hash IS NOT NULL) "
        "OR (media_type = 'voice' AND perceptual_hash IS NULL)",
    )

    # One row per medium per report. The read paths in the intake repository look up
    # a single media row per type; without this, a partially retried submission
    # could leave two and those lookups would silently return an arbitrary one.
    if not _has_constraint(bind, _MEDIA_TABLE, "uq_report_media_one_per_type"):
        op.create_unique_constraint(
            "uq_report_media_one_per_type", _MEDIA_TABLE, ["report_id", "media_type"]
        )


def downgrade() -> None:
    """Restore the voice-only shape, refusing to run if photos exist.

    Not reversible once photos are stored, and that is stated rather than worked
    around. Reversing would mean deleting the photo rows -- evidence a citizen
    submitted -- to satisfy the old NOT NULL on ``duration_seconds``. A migration
    must never be the thing that silently discards evidence, so it stops and makes
    the operator decide.
    """

    bind = op.get_bind()

    photo_rows = bind.execute(
        text(f"SELECT count(*) FROM {_MEDIA_TABLE} WHERE media_type = 'photo'")
    ).scalar_one()
    if photo_rows:
        raise RuntimeError(
            f"Cannot downgrade: {photo_rows} photo row(s) exist in {_MEDIA_TABLE}. "
            "The voice-only schema has no place to put them, and this migration will "
            "not delete citizen-submitted evidence to make the schema fit. Export or "
            "remove those rows deliberately, then downgrade."
        )

    for name in (
        "uq_report_media_one_per_type",
        "media_type_allowed",
        "byte_size_limit",
        "duration_matches_media_type",
        "perceptual_hash_matches_media_type",
    ):
        _drop_constraint_if_exists(bind, _MEDIA_TABLE, name)

    if _has_column(bind, _MEDIA_TABLE, "integrity_flags"):
        op.drop_column(_MEDIA_TABLE, "integrity_flags")
    if _has_column(bind, _MEDIA_TABLE, "perceptual_hash"):
        op.drop_column(_MEDIA_TABLE, "perceptual_hash")
    if _has_column(bind, "report", "service_code"):
        op.drop_column("report", "service_code")

    # Safe only because the check above proved there are no photo rows, and voice
    # rows have always carried a duration.
    op.alter_column(_MEDIA_TABLE, "duration_seconds", nullable=False)
    _add_check_if_absent(bind, _MEDIA_TABLE, "voice_only", "media_type = 'voice'")
    _add_check_if_absent(bind, _MEDIA_TABLE, "byte_size_limit", "byte_size BETWEEN 1 AND 6291456")
    _add_check_if_absent(bind, _MEDIA_TABLE, "duration_limit", "duration_seconds BETWEEN 0 AND 30")


def _has_column(bind: Connection, table: str, column: str) -> bool:
    return (
        bind.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :table AND column_name = :column"
            ),
            {"table": table, "column": column},
        ).scalar_one_or_none()
        is not None
    )


def _has_constraint(bind: Connection, table: str, name: str) -> bool:
    return (
        bind.execute(
            text(
                "SELECT 1 FROM pg_constraint c "
                "JOIN pg_class t ON t.oid = c.conrelid "
                "WHERE t.relname = :table AND c.conname = :name"
            ),
            {"table": table, "name": name},
        ).scalar_one_or_none()
        is not None
    )


def _check_constraint_names(bind: Connection, table: str, name: str) -> list[str]:
    """Every name this CHECK could be stored under, as PostgreSQL actually holds it.

    ``Base.metadata`` carries the convention ``ck_%(table_name)s_%(constraint_name)s``,
    and because that template contains ``%(constraint_name)s``, SQLAlchemy applies it
    even to a constraint that was given a name -- so the model's
    ``name="media_type_allowed"`` reaches the database as
    ``ck_report_media_media_type_allowed``. Alembic applies the same convention to the
    DDL it emits, since ``env.py`` hands it ``target_metadata``.

    Asking the catalogue for the short name therefore always missed, and every "if
    absent" guard in this revision was unconditionally true. The first CHECK it tried
    to add already existed and the upgrade died -- on precisely the database shape the
    module docstring says it must tolerate. Both spellings are looked up rather than
    only the long one, because a database whose constraints predate the convention
    would hold the short form.
    """

    rows = bind.execute(
        text(
            "SELECT c.conname FROM pg_constraint c "
            "JOIN pg_class t ON t.oid = c.conrelid "
            "WHERE t.relname = :table AND c.conname IN (:short, :conventional)"
        ),
        {"table": table, "short": name, "conventional": f"ck_{table}_{name}"},
    )
    return list(rows.scalars().all())


def _drop_constraint_if_exists(bind: Connection, table: str, name: str) -> None:
    if name.startswith("uq_"):
        # Unique constraints are unaffected: the ``uq`` template has no
        # ``%(constraint_name)s`` in it, so a name that was supplied survives verbatim.
        if _has_constraint(bind, table, name):
            op.drop_constraint(name, table, type_="unique")
        return
    for existing in _check_constraint_names(bind, table, name):
        # Raw DDL against the name the catalogue returned. `op.drop_constraint` would
        # re-apply the naming convention to whatever it is handed, which is the same
        # mismatch that broke the guards above.
        op.execute(f'ALTER TABLE {table} DROP CONSTRAINT "{existing}"')


def _add_check_if_absent(bind: Connection, table: str, name: str, condition: str) -> None:
    if _check_constraint_names(bind, table, name):
        return
    # Named here the way the convention would name it, so this revision and
    # ``create_all`` produce one constraint and not two spellings of it.
    op.execute(f'ALTER TABLE {table} ADD CONSTRAINT "ck_{table}_{name}" CHECK ({condition})')
