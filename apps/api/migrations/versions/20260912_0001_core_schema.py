"""Create the CivicLens v1 auditable core schema.

Revision ID: 20260912_0001
Revises: None
"""

from __future__ import annotations

from alembic import op

from civiclens.infrastructure.db import models as _models  # noqa: F401
from civiclens.infrastructure.db.base import Base

revision = "20260912_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the frozen v1 table set and append-only decision guard."""

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    op.execute(
        """
        CREATE FUNCTION civiclens_reject_human_decision_mutation()
        RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'human_decision is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER human_decision_append_only
        BEFORE UPDATE OR DELETE ON human_decision
        FOR EACH ROW EXECUTE FUNCTION civiclens_reject_human_decision_mutation()
        """
    )


def downgrade() -> None:
    """Remove only schema objects introduced by this revision."""

    op.execute("DROP TRIGGER IF EXISTS human_decision_append_only ON human_decision")
    op.execute("DROP FUNCTION IF EXISTS civiclens_reject_human_decision_mutation()")
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
