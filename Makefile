.PHONY: install dev-db dev-db-down migrate seed api web check test build

install:
	npm install
	cd apps/api && uv sync

dev-db:
	docker compose up -d postgres

dev-db-down:
	docker compose down

migrate:
	cd apps/api && uv run alembic upgrade head

seed:
	cd apps/api && uv run python -m civiclens.infrastructure.db.seed --confirm-demo

api:
	cd apps/api && uv run uvicorn civiclens.main:app --reload --port 8000

web:
	npm run web:dev

test:
	cd apps/api && uv run pytest

build:
	npm run web:build

check:
	npm run web:typecheck
	cd apps/api && uv run ruff check .
	cd apps/api && uv run pyright
	cd apps/api && uv run python scripts/export_openapi.py --check
	cd apps/api && uv run pytest
	npm run web:build
