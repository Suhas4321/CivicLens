# CivicLens

**Civic complaint prioritisation for Bengaluru South.**

Citizens report everyday civic problems — no water, broken road, garbage, an exposed wire — in plain language from a phone, in English, Kannada, or the code-mixed Kanglish people actually type. CivicLens does four things with them:

1. **Groups** reports that describe the same physical problem in the same place, so 30 complaints about one road become **one problem with 30 pieces of evidence** instead of 30 tickets.
2. **Ranks** those grouped problems by a published formula — how many distinct people, how long it has persisted, how exposed the location is, how vulnerable the people nearby are, how severe the category is, how long it has been ignored — where every rank opens into the arithmetic behind it.
3. **Routes** each problem to the responsible agency (BSCC, BWSSB, BESCOM, BMTC) with a statutory deadline attached.
4. **Closes the loop.** When an officer marks a problem resolved, the original reporters get 48 hours to say whether it was actually fixed. A disputed closure reopens the problem, and the SLA clock resumes where it paused rather than restarting.

Dangerous hazards — a live wire, contaminated water near a hospital — skip ranking entirely and go to an immediate-review lane. A human makes every decision. The system orders the queue and shows its work.

**What existing portals don't do:** Sahaaya, Swachhata, CPGRAMS and the Open311 standard itself all treat every complaint as an independent ticket. Open311 defines no deduplication mechanism at all — cities type "Duplicate request." into a notes field. None of them report whether a closed complaint stayed closed. Both of those gaps are where this project is aimed.

## Status

**Rebuild in progress.** The previous implementation pass produced a demo whose decision engine has zero production callers and whose officer dashboard reads a hand-typed JSON file. Priority was not computed; it was typed. See `docs/REBUILD_00_HANDOFF_AND_SCOPE.md §2` for the verified state of the code and `docs/REBUILD_01_PROBLEM_REGISTER.md` for every known defect.

Do not trust the previous status claims in this file's history, or in `docs/archive/`.

## Documentation

Read in this order:

| # | Document | Covers |
|---|---|---|
| 1 | [REBUILD_00 — Handoff and Scope](docs/REBUILD_00_HANDOFF_AND_SCOPE.md) | Scope, true state of the code, work order |
| 2 | [REBUILD_01 — Problem Register](docs/REBUILD_01_PROBLEM_REGISTER.md) | Every known defect and its fix |
| 3 | [REBUILD_04 — Priority Model and Routing](docs/REBUILD_04_PRIORITY_MODEL_AND_ROUTING.md) | The score, three lanes, agency routing, why it is legitimate |
| 4 | [REBUILD_05 — Location, Abuse and Closure](docs/REBUILD_05_LOCATION_ABUSE_AND_CLOSURE.md) | Location intake, spatial grouping, Sybil resistance, closure integrity, **build order** |
| 5 | [REBUILD_02 — Data Pipeline](docs/REBUILD_02_DATA_PIPELINE_AND_PRIORITY.md) | Pipeline stages *(partly superseded — read its banner)* |
| 6 | [REBUILD_03 — UI Blueprint](docs/REBUILD_03_UI_DESIGN_BLUEPRINT.md) | Screens, design tokens *(partly superseded — read its banner)* |

[AGENTS.md](AGENTS.md) holds the non-negotiable engineering rules. [docs/archive/](docs/archive/README.md) holds the seven superseded Stage 1–6 planning documents and a salvage index — **historical only, do not implement from it.**

## Local prerequisites

- Node.js 24 LTS
- Python 3.12 managed by `uv`
- Docker with Compose, for PostgreSQL 17 **with PostGIS**

## Common commands

```bash
make install
```

```bash
make dev-db
```

```bash
make migrate
```

```bash
make seed
```

```bash
make api
```

```bash
make web
```

```bash
make check
```

Web runs on `http://localhost:5173`, API on `http://localhost:8000`.

### OpenStreetMap reference data

Location context — which road a report is on, which locality it falls in, what hospitals are nearby — comes from an OSM extract ingested **once, offline**, into PostGIS. There is no runtime call to any mapping service.

Download the extract (~128 MB, into the git-ignored `data/osm/`):

```bash
make osm-fetch
```

Parse it and print counts without touching the database:

```bash
make osm-dry-run
```

Load it, replacing the previous reference data in one transaction:

```bash
make osm-ingest
```

`make osm-ingest` needs PostGIS and migration `20260915_0002`. With Docker, `make dev-db` already provides it (the Compose image is `postgis/postgis:17-3.5`). On a local PostgreSQL install, run `sudo infra/bootstrap-local-db.sh` once.

What is kept, which OSM tags map to which category, and the bounding box are all policy in [config/geography/bengaluru-south-v1.json](config/geography/bengaluru-south-v1.json), so a mapping correction is a re-ingest rather than a code change. Each run records the source URL, its SHA-256, the extract's own replication timestamp, and per-category counts in `osm_ingest_run`.

The spatial tests are gated because they need a live database:

```bash
cd apps/api && RUN_POSTGRES_TESTS=1 uv run pytest tests/test_spatial_reference.py -v
```

Extraction itself has no database dependency and is covered by `tests/test_osm_extract.py`, which runs in the default suite.

## Modes

Local mode uses a deterministic fixture interpreter and in-memory session overlays, so the whole app runs with no cloud account and no API key. For durable mode, start PostgreSQL, migrate and seed, then set `INTAKE_BACKEND=postgres`, `SESSION_BACKEND=postgres`, `DECISION_BACKEND=postgres`.

Gemini is opt-in: `AI_BACKEND=developer` with a developer key, for synthetic local data only, or `AI_BACKEND=vertex` in deployment. No test calls a live model.

The basemap is a self-hosted Protomaps `.pmtiles` extract of Bengaluru South served as a static asset — **no Google Maps API, no key, no billing account, and no use of the public OpenStreetMap tile servers.** Maps display `© OpenStreetMap contributors`; the underlying data is ODbL-licensed.

## Data

All bundled citizen reports are **synthetic**. Real data in this repository is limited to OpenStreetMap geometry for Bengaluru South (roads, localities, hospitals, schools, transit stops) and a published SLA table modelled on the Karnataka Sakala Services Act. Every value carries a provenance label: Real Public, Derived Public, Synthetic Demo, User Submitted, or AI Derived.

Note: BBMP was dissolved on 2 September 2025 and replaced by five corporations under the Greater Bengaluru Authority. This project targets **Bengaluru South City Corporation** (HQ Jayanagara, 72 wards).
