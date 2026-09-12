# CivicLens AI

CivicLens is an explainable civic needs-to-project decision-intelligence prototype. It converts multilingual citizen signals into reviewable incidents and suspected needs, combines them with honestly scoped public context, proposes a conditional assessment, and records a human feasibility decision.

## Current implementation status

The complete Golden Demo lifecycle is implemented: secure synthetic report intake, private receipt, bounded AI/fixture interpretation, separate operational safety review, deterministic grouping and priority rules, constrained candidates, and isolated append-only human decisions. Production adapters and deployment verification remain.

## Planned local prerequisites

- Node.js 24 LTS
- Python 3.12 managed by `uv`
- Docker with Compose for PostgreSQL 17

Local mode intentionally uses a deterministic fixture interpreter and in-memory session overlays. To exercise durable mode, start PostgreSQL, migrate and seed, then set `INTAKE_BACKEND=postgres`, `SESSION_BACKEND=postgres`, and `DECISION_BACKEND=postgres`. Gemini is opt-in: use `AI_BACKEND=developer` with a developer key only for synthetic local data, or `AI_BACKEND=vertex` in production.

## Common commands

```bash
make install
make dev-db
make migrate
make seed
make api
make web
make check
```

The web application uses `http://localhost:5173`; the API uses `http://localhost:8000`.

All bundled citizen reports and local service findings are synthetic. The public snapshot contains only dated, cited JICA facts and normalized extracts; its manifest explicitly records prohibited inferences.

## Product documentation

The authoritative implementation scope is [Stage 6 Final Design Review](docs/STAGE_6_FINAL_DESIGN_REVIEW.md). The dependency-ordered build sequence is [Stage 5 Build Plan](docs/STAGE_5_BUILD_PLAN.md).
