"""Create the PostGIS reference tables for offline OpenStreetMap data.

Revision ID: 20260915_0002
Revises: 20260912_0001
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

from civiclens.infrastructure.db.spatial import SPATIAL_METADATA

revision = "20260915_0002"
down_revision = "20260912_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Verify PostGIS, then create the spatial reference tables and GiST indexes."""

    bind = op.get_bind()

    # CREATE EXTENSION needs superuser, which the application role deliberately is
    # not. It is done once by infra/bootstrap-local-db.sh locally and by the
    # cloudsqlsuperuser role on Cloud SQL. Checking here rather than assuming turns
    # a confusing "type geography does not exist" into an actionable message.
    installed = bind.execute(
        text("SELECT extversion FROM pg_extension WHERE extname = 'postgis'")
    ).scalar_one_or_none()
    if installed is None:
        raise RuntimeError(
            "PostGIS is not enabled in this database. Enable it before migrating:\n"
            "  local PostgreSQL:  sudo infra/bootstrap-local-db.sh\n"
            "  Docker:            make dev-db\n"
            "  Cloud SQL:         CREATE EXTENSION postgis; as cloudsqlsuperuser"
        )

    # SPATIAL_METADATA holds only the tables introduced by this revision, so this
    # create_all cannot touch anything from 20260912_0001. See the module docstring
    # in civiclens.infrastructure.db.spatial for why the metadata is separate.
    SPATIAL_METADATA.create_all(bind=bind)


def downgrade() -> None:
    """Remove only schema objects introduced by this revision."""

    SPATIAL_METADATA.drop_all(bind=op.get_bind())
