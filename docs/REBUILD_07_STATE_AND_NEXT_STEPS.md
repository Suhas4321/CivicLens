# REBUILD 07 — Where the build actually is, and what is left

**Written:** 2026-09-19
**Branch this describes:** `feat/web-two-surface-redesign` (tip of a 7-branch stack onto `master`)
**Purpose:** this file is the handoff. It is written so that a new chat session, with
no memory of any previous one, can read this file alone and carry on correctly. Where
it disagrees with `REBUILD_00`–`REBUILD_06`, **this file wins** — those describe the
plan, this describes the code.

---

## 1. What CivicLens is, in one screen

A civic-complaint system for **Bengaluru South (BSCC)** — JP Nagar / Banashankari.
Residents report a problem; officers see **problems, not complaints**.

The whole point is the middle step: **forty reports of one flooded junction must
become one item on an officer's screen, not forty.** Everything else in the codebase
serves that.

### The three lanes (never mix them)

| Lane | What it holds | How it is ordered |
|---|---|---|
| **1. Safety** | Anything that can hurt someone today | **Chronological. Never scored.** A hazard does not queue behind arithmetic. |
| **2. Statutory** | Has a legal service deadline (Sakala) | By how overdue it is |
| **3. Discretionary** | Everything else | By priority score |

The SLA clock starts at the **group's** `first_reported_at`, never at the newest
report. Otherwise every duplicate complaint would push the deadline further away —
rewarding the backlog for growing. (`domain/sla.py`, and the test
`test_the_clock_starts_at_the_first_report_not_the_newest`.)

### The priority score (Lane 3 only)

Six components, each 0–100, weighted to sum to 1.0 (`domain/scoring.py`):

`cs` 0.24 · `ps` 0.18 · `ex` 0.16 · `vu` 0.18 · `sv` 0.16 · `ng` 0.08

Bands: ≥70 high, ≥45 moderate, else lower. **The web app re-computes this total
client-side and shows a warning if the API's number disagrees by more than 0.05**
(`apps/web/src/api/priority.ts`, `verifyScore`). That is deliberate: the officer is
never asked to trust a number they cannot check. If you change the weights in
`domain/scoring.py` you must change `SCORE_WEIGHTS` in `priority.ts` in the same
commit.

### How grouping decides (Suhas's own design, implemented)

1. **Geometry first** — same category, within 1.5 km, within the time window.
2. **Then intent** — a language model reads the two descriptions and says
   same/different/abstain. *Not yet wired* (see §4). Until it is, the payload says
   `intent_verdict: "abstain"` and the group is labelled **"proposed as one problem"**
   rather than asserted as one.
3. **Photo hash corroborates only** — a matching `dhash` (distance ≤ 12) strengthens a
   grouping geometry already allowed. It can never create one. **No vision model.**
4. **Leader clustering, never transitive.** A joins B, B joins C does not make A join C.
5. `uncertainty_favors_separation: true` — when unsure, two problems, not one. Two
   items an officer merges is a nuisance; one item hiding a second pothole is a pothole
   nobody fixes.
6. **Safety never groups with non-safety.**

---

## 2. What works right now, verified

Verified against a real PostgreSQL 18 + PostGIS database, CI's exact sequence, from
empty: `alembic upgrade head` → `downgrade base` → `upgrade head` → `seed
--confirm-demo` → `ruff check` → `ruff format --check` → `pyright` (0 errors) →
`export_openapi.py --check` → `pytest`: **192 passed, 1 skipped**, twice consecutively.

### Working, end to end
- **Report submission** with text, optional photo, optional voice, optional
  coordinates. Photo EXIF location is extracted and the EXIF itself is then discarded.
- **Grouping on live submissions** — three people reporting one pothole produce one
  officer item showing `report_count: 3`.
- **Officer board** (`GET /api/v1/officer/overview`) merges freshly submitted grouped
  reports ahead of the seeded demo lanes.
- **Officer reviews** (`POST /api/v1/officer/reports/{id}/reviews`) — recorded,
  append-only.
- **Photo serving** (`GET /api/v1/officer/reports/{id}/photo`) — gated on
  `demo_mode_enabled`, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`.
- **Ward geography from OpenStreetMap, offline.** No Google Maps, no API key, no calls
  to the public OSM tile servers.
- **Demo seed** — 60 reports, 8 incidents, 2 needs, 9 public evidence rows. Idempotent.

### The 13 endpoints that exist (`contracts/openapi.json`)
```
POST /api/v1/reports                              GET  /api/v1/receipts/{public_id}
GET  /api/v1/officer/overview                     GET  /api/v1/officer/needs
GET  /api/v1/officer/needs/{need_id}              GET/POST .../needs/{id}/decisions
GET  /api/v1/officer/incidents/{incident_id}      GET  .../reports/{id}/photo
GET/POST /api/v1/officer/reports/{id}/reviews     POST /api/v1/demo-sessions
GET  /api/v1/health/{live,ready,version}
```

### Three CI bugs found and fixed (2026-09-18/19)
Recorded because each has a lesson that will otherwise be re-learned the hard way.

1. **The photo migration collided with its own constraints.** Its "add only if absent"
   guards queried `pg_constraint` for `media_type_allowed`, but the naming convention
   on `Base.metadata` stores it as `ck_report_media_media_type_allowed` — so every
   guard was unconditionally true and the first `ADD CONSTRAINT` died on a duplicate.
   *Lesson: a convention template containing `%(constraint_name)s` is applied even to a
   constraint you named yourself.*
2. **The seed inserted child rows before parent rows.** SQLAlchemy orders a flush only
   by dependencies it learns from `relationship()` declarations; these models declare
   none, so it fell back to alphabetical-by-class-name and handed
   `incident_report_link` to PostgreSQL before `report`. Fixed once, centrally, in
   `DependencyOrderedSession` (`infrastructure/db/session.py`) — read the docstring
   there before touching it.
3. **The same bug in the live submission path** (`modules/intake/repository.py`) —
   found only because fixing #2 made that code execute for the first time.

**Why all three hid for weeks: SQLite does not enforce foreign keys unless you set
`PRAGMA foreign_keys=ON`, and SQLite is the local default.** 192 local tests were blind
to it by construction. The new test
`test_seeding_an_empty_database_writes_every_table_in_foreign_key_order` closes that
hole — it seeds into a throwaway PostgreSQL schema inside a transaction that is always
rolled back, so it costs nothing to run every time.

---

## 3. What is left — the gap list, in the order I recommend

### 3.1 Six endpoints the web app already calls and the API does not have

`apps/web/src/api/priority.ts` is the **contract**. It is 628 lines of zod schemas that
already define exactly what each response must contain. Build the API to match it, not
the reverse.

| # | Endpoint | Feeds | Notes |
|---|---|---|---|
| 1 | `GET /api/v1/officer/board` | the real officer board | Must satisfy `officerBoardSchema`: `{generated_at, config_version, reference_data_as_of, disclosure, wards[], groups[]}`. Ward-first, not a flat list. |
| 2 | `GET /api/v1/problems/{id}` | problem detail page | Returns a **bare** `ProblemGroup` (not wrapped). |
| 3 | `GET /api/v1/categories` | the category grid on the report form | Must mirror `config/categories/bengaluru-south-v1.json` exactly. |
| 4 | `GET /api/v1/public/wards` | public homepage backlog | `{window_days, generated_at, disclosure, wards[]}` |
| 5 | `GET /api/v1/wards/{id}/summary` | one ward's public page | `{ward, reported, resolved, past_deadline, window_days, generated_at}` |
| 6 | `POST /api/v1/problems/{id}/status` | **the closure loop** | Does not exist, so the "mark solved" button in `ProblemDetailPage.tsx` is disabled. Statuses: `open, acknowledged, in_progress, resolved, disputed, reopened`. |

Most of the domain logic these need is **already written** and just needs assembling
behind a router: `domain/scoring.py`, `domain/sla.py`, `domain/categories.py`,
`domain/photo_integrity.py`, `modules/priority/evaluator.py`,
`infrastructure/db/geography.py`, `modules/relationships/grouping.py`.

Until #1 and #3 land, the board renders from a local stub:
`apps/web/src/api/pendingBackend.ts` (570 lines). Its own header says *"Delete this
file when /api/v1/officer/board and /api/v1/categories exist."* Delete it then.

### 3.2 The photo is never shown to an officer
`GET /api/v1/officer/reports/{id}/photo` works. **Nothing in the officer surface points
an `<img>` at it.** The only live `<img>` is in `PhotoCapture.tsx` — the citizen's own
preview of the file they just picked, from a local blob URL, before it is even
uploaded. (`pages/ReportPage.tsx` has two more, but that file is dead — see §4.1.)

So the photo is captured, EXIF-parsed, stored, and servable — and no officer can see
it. Suhas's stated reason for wanting photo upload was *"so officers can judge severity
from their desk"*, which is not true yet. Small change, large share of the actual
purpose behind it.

### 3.3 The web client silently drops fields the API already sends
The zod schemas in `apps/web/src/api/officer.ts` do not include `has_photo`,
`service_code`, `grouping_confidence`, `photo_integrity_flags`, or `joined_by` — so zod
strips them and the UI cannot show them even though the API returns them. `joined_by`
is the "why were these grouped" evidence (distance, hours apart, category match), which
is the thing that lets an officer argue with a bad grouping instead of just overriding
it.

### 3.4 The closure loop is unproven end to end
No test traces: officer marks resolved → citizen sees it on their receipt. Until that
exists, the loop is an intention.

### 3.5 Gemini intent check (step 2 of grouping) is not wired
Needs `GEMINI_API_KEY` in `apps/api/.env`. **Suhas's call, and Suhas's hands only —
put it in the file directly, never in a chat message.** Until then grouping is geometry
only and honestly labelled as such.

### 3.6 No frontend tests at all
`apps/web` has **no test runner** — no vitest, no Playwright. The API has 192 tests.

### 3.7 Language and polish
- `@fontsource/noto-sans-kannada` is not installed; Kannada will render in a fallback font.
- ~20 Kannada strings were written by an AI and **need a native speaker's eye** before
  anyone relies on them.

### 3.8 Deployment (approval-gated, not started)
`PHOTO_BACKEND=gcs` plus bucket provisioning. From `infra/README.md`: *"Do not create
service-account JSON keys; use authenticated developer tooling and least-privilege
service identities."*

---

## 4. Decisions only Suhas can make

These are blocking nothing today, but each one changes what gets built.

1. **Delete the dead Codex frontend files?** They are untracked and nothing imports
   them, but I have not deleted them without a yes. The list:
   `apps/web/postcss.config.js`, `tailwind.config.js`, `src/App.tsx`, `src/index.css`,
   `src/data/`, `src/pages/` (5 files), and `src/components/{Button,Input,
   ProvenanceBadge,StatusPill,VoiceRecorder,index}.tsx`.
   *(Note: `src/components/civic/ProvenanceBadge.tsx` is the live one — keep it.)*
2. **Is `TREE_HAZARD` Lane 1 (safety) eligible?** A leaning tree in monsoon is a
   genuine hazard; a fallen branch on a footpath is not. The rule needs a human's
   judgement, not mine.
3. **Keep or bin the OpenAI Sites scaffold?** `stash@{0}`, plus untracked
   `apps/web/.openai/`, `apps/web/src/server/`, `docs/CODEX_FULL_REVIEW.md`,
   `docs/FRONTEND_DESIGN_REVIEW_2026-09-18.md`.
4. **Narrow the 1.5 km grouping gate for point-located reports?** 1.5 km is right for
   "this locality has no water". It is far too generous for "there is a pothole here"
   when we have a GPS fix accurate to 10 m.
5. **Rebase the stack so every PR goes green?** Only PR #10 passes CI. #9 and below
   stay red because the seed bug predates them and `pull_request` checks are evaluated
   from the merge commit. Fixing it means rewriting 8 commits and force-pushing 7 open
   branches. **My recommendation: don't.** Merge the stack and the problem evaporates.

---

## 5. Running it locally (no GPT / Codex needed)

```bash
make install        # npm install + uv sync
make dev-db         # PostgreSQL + PostGIS in docker
make migrate        # alembic upgrade head
make seed           # 60 demo reports, 8 incidents, 2 needs
make api            # http://localhost:8000  (docs at /docs)
make web            # http://localhost:5173
```

The full CI gate in one command — run this before any push:

```bash
make check
```

That runs, in order: web typecheck → `ruff check` → `pyright` → OpenAPI contract check
→ `pytest` → web build. **The OpenAPI check is the one that catches you out:** change a
route or a response model and you must regenerate the contract, or CI fails.

```bash
cd apps/api && uv run python scripts/export_openapi.py
```

Pages to look at once it is up: `/` (public home), `/report` (the intake form),
`/officer` (the board), `/officer/problems/:id` (problem detail).

---

## 6. Standing constraints — carry these into every session

**Privacy and data**
- Only synthetic citizen data in this prototype.
- **Never log** report content, media, precise coordinates, IP addresses, receipt
  capabilities, or credentials. Store only the HMAC of a reporter key.
- `apps/api/.env` contains a real `GEMINI_API_KEY`. **Never read or print that file.**
  Use targeted `grep`/`sed` on specific lines if you must touch it. It is gitignored
  and untracked — verified.

**Infrastructure**
- No Google Maps API. No mapping API key. Do not call `tile.openstreetmap.org`.
- No service-account JSON keys. Provisioning is explicit and approval-gated.

**Working style Suhas has asked for**
- He is a **beginner solo developer**. Explain the *why*, not just the *what*. Code that
  works but that he cannot understand has failed.
- Act as principal engineer **and** principal designer. Think independently; do not
  just follow these documents.
- **Never claim something works without a number or a command output behind it.** He
  has been burned by confident-sounding hallucination and says so.
- Do not inspect screens or take screenshots — he will supply them if needed.
- Narrate progress as "did this, now doing this", with an **overall** time estimate.

**Design direction**
- The public surface and the officer portal must **look and feel different**. They are
  for different people with different jobs.
- Must work for educated *and* uneducated users. Icons and photos carry meaning that
  text cannot.
- **Do not copy the drab minimal design of Indian government websites.** That look
  signals "this will not help you", which is the opposite of the point.
- Earlier verdict on the UI, in his words: *"looks shit", "looks like it is under
  repair."* Gaps left and right; no differentiation between the two surfaces.

---

## 7. Honest assessment

The **engine works**. Grouping, the three lanes, the SLA clock, scoring, ward
geography, photo intake with EXIF, append-only audit — those are real, tested, and
correct on the things that matter (the clock starting at the first report; unknown
categories never grouping; safety never mixing with operations).

The **skin does not**. Six endpoints the frontend already calls do not exist, so the
officer board renders from a 570-line local stub. The photo is uploaded, stored, served
— and displayed nowhere. The closure loop stops at a disabled button.

**The gap is narrower than it looks.** The domain logic behind all six endpoints is
already written. What is missing is the assembly: pydantic response models, six route
handlers, tests, a regenerated contract, and deleting the stub. `priority.ts` already
specifies every field. That is a focused session's work, not a rebuild.

**Start with §3.1 items 1 and 2, then §3.2.** That sequence gets a real board with real
photographs on screen fastest — which is the first point at which this stops being a
codebase and starts being something you can show someone.
