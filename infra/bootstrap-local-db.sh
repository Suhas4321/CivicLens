#!/usr/bin/env bash
# Prepare a local PostgreSQL server for CivicLens development.
#
# Two things in this script need root, which is why it is separate from `make`:
#   1. installing the PostGIS extension package
#   2. creating the civiclens role/database and enabling the extension (superuser-only)
#
# Everything else in the project runs as an unprivileged user.
# The script is idempotent: running it twice is safe and changes nothing the second time.
#
# Usage:  sudo infra/bootstrap-local-db.sh
#
# If you use Docker instead, you do not need this script — `make dev-db` starts a
# postgis/postgis container that already has everything below.

set -euo pipefail

DB_NAME="${DB_NAME:-civiclens}"
DB_USER="${DB_USER:-civiclens}"
DB_PASSWORD="${DB_PASSWORD:-civiclens}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "error: run with sudo — this script installs a package and creates a database role" >&2
  exit 1
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "error: PostgreSQL client not found. Install postgresql first." >&2
  exit 1
fi

# Detect the running server's major version rather than assuming one.
PG_MAJOR="$(su postgres -c "psql -tAc 'SHOW server_version_num'" | cut -c1-2)"
echo "==> PostgreSQL major version: ${PG_MAJOR}"

# 1. PostGIS ------------------------------------------------------------------
if [[ -f "/usr/share/postgresql/${PG_MAJOR}/extension/postgis.control" ]]; then
  echo "==> PostGIS package already installed"
else
  echo "==> Installing postgresql-${PG_MAJOR}-postgis-3"
  apt-get update -qq
  apt-get install -y "postgresql-${PG_MAJOR}-postgis-3"
fi

# 2. Role ---------------------------------------------------------------------
if su postgres -c "psql -tAc \"SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'\"" | grep -q 1; then
  echo "==> Role '${DB_USER}' already exists"
else
  echo "==> Creating role '${DB_USER}'"
  su postgres -c "psql -q -c \"CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASSWORD}'\""
fi

# 3. Database -----------------------------------------------------------------
if su postgres -c "psql -tAc \"SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'\"" | grep -q 1; then
  echo "==> Database '${DB_NAME}' already exists"
else
  echo "==> Creating database '${DB_NAME}' owned by '${DB_USER}'"
  su postgres -c "psql -q -c \"CREATE DATABASE ${DB_NAME} OWNER ${DB_USER}\""
fi

# 4. Extension ----------------------------------------------------------------
# CREATE EXTENSION requires superuser, so it happens here rather than in the Alembic
# migration. On Cloud SQL the equivalent step is run by the cloudsqlsuperuser role.
# The migration only verifies the extension is present.
echo "==> Enabling PostGIS in '${DB_NAME}'"
su postgres -c "psql -q -d ${DB_NAME} -c 'CREATE EXTENSION IF NOT EXISTS postgis'"

INSTALLED="$(su postgres -c "psql -tAd ${DB_NAME} -c \"SELECT extversion FROM pg_extension WHERE extname='postgis'\"")"
echo "==> PostGIS ${INSTALLED} active in ${DB_NAME}"

echo
echo "Done. Verify with:"
echo "  psql \"postgresql://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}\" -c 'SELECT postgis_full_version()'"
