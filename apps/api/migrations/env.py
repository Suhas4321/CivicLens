from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from civiclens.bootstrap.settings import get_settings
from civiclens.infrastructure.db import models as _models  # noqa: F401
from civiclens.infrastructure.db.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = get_settings().database_url
if not database_url.startswith("postgresql"):
    # The core schema uses JSONB and the spatial schema uses PostGIS geography
    # columns, neither of which SQLite can render. Without this guard the failure
    # surfaces as a SQLAlchemy CompileError deep inside create_all, which reads
    # like a code defect rather than a misconfigured DATABASE_URL.
    raise RuntimeError(
        "Migrations require PostgreSQL, but DATABASE_URL is "
        f"{database_url.split(':', 1)[0]!r}.\n"
        "Set DATABASE_URL in apps/api/.env to:\n"
        "  postgresql+psycopg://civiclens:civiclens@localhost:5432/civiclens\n"
        "Then ensure PostGIS is available: sudo infra/bootstrap-local-db.sh"
    )

config.set_main_option("sqlalchemy.url", database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
