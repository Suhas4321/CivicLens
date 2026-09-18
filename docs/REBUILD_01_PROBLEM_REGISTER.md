# CivicLens Rebuild — Problem Register

**Written:** 15 September 2026
**Companion to:** `REBUILD_00_HANDOFF_AND_SCOPE.md`
**Purpose:** Every problem found in the 15 Sep 2026 code review, each with evidence and a concrete fix. IDs are stable — refer to them (`P-03`) in commits and conversation.

**Severity key**

| Level | Meaning |
|---|---|
| **BLOCKER** | The product does not do what it claims until this is fixed. Nothing else matters more. |
| **HIGH** | Ships broken, insecure, or unusable for real users. |
| **MEDIUM** | Real defect, but the product functions. |
| **LOW** | Quality, consistency, hygiene. |

---

## Category 1 — The engine (BLOCKERS)

### P-01 — The decision engine has zero production callers
**Severity:** BLOCKER
**Evidence:** `evaluate_priority`, `evaluate_same_incident`, `evaluate_recurrence` and `generate_candidate` are imported only by `tests/test_decision_rules.py`. Nothing in `src/` calls them.
**Impact:** There is no prioritisation and no grouping in the running application. 30 backend tests validate an engine that is not connected to anything.
**Fix:** Build a real pipeline stage that runs after interpretation: assign the report to a problem group (P-03), then score the group (P-04), then persist both. Call it from the job worker (P-07). The evaluators keep their current signatures where sensible — they are not the problem, their disconnection is.
**Verify:** Submit a report through the UI; observe a new row in `problem_group` and a non-null score, without any developer touching a JSON file.

---

### P-02 — The officer dashboard reads hand-typed JSON
**Severity:** BLOCKER
**Evidence:** `modules/planning/read_service.py` → `GoldenDemoReadService` reads `data/demo/v1/ground_truth.json`, where `"priority": {"band": "high", ...}` and every component rating is a literal.
**Impact:** The ranked queue — the entire point of the product — is a stage prop. Any reviewer who opens the repo sees this within a minute, and it invalidates every claim the demo makes.
**Fix:** Rewire `/officer/overview`, `/officer/needs/{id}` and `/officer/incidents/{id}` to read computed `problem_group` rows. Keep `GoldenDemoReadService` alive **only** as the fixture behind a regression test that asserts the computed pipeline reproduces the 60-report curated scenario. That converts it from a lie into a test oracle, which is a legitimate use.
**Verify:** Delete a need from `ground_truth.json`; the dashboard is unaffected.

---

### P-03 — Grouping is impossible with the data collected
**Severity:** BLOCKER
**Evidence:** The report form collects `locality_label` as **free text** (`min_length=3, max_length=160`). `evaluate_same_incident` reaches `confidence: "high"` only when both reports carry coordinates; with identical locality text it returns `"review"`, and with differing text it appends `LOCATION_NOT_SUPPORTED` and abstains. `IMPLEMENTATION_DECISIONS.md` decision 2 deliberately removed the map.
**Impact:** "Mahadevapura", "mahadevpura" and "near Chinnappa circle" never match. In production, no two reports ever group. The 1.5 km distance gate is unreachable.
**Fix:**
1. Collect real coordinates — EXIF GPS from photos (P-05), a map pin, or geolocation, in that order of preference; ward + landmark as the last resort, flagged `location_quality: 'coarse'`.
2. Replace the pairwise predicate with a clustering pass keyed on `(category, geohash-7 cell, 30-day window)`, checking the 8 neighbouring cells. See `REBUILD_02` §3.
**Verify:** Two reports 100 m apart, same category, 3 days apart, land in one group. Two reports 5 km apart do not.

---

### P-04 — The priority rubric abstains on everything real
**Severity:** BLOCKER
**Evidence:** `config/rules/priority-v1.json` sets `unknown_prevents_comparison: true`, and `ComponentRating` requires `evidence_refs` for any known rating. The four components (`scale_exposure`, `persistence_spread`, `service_disadvantage`, `consequence_if_unaddressed`) all require verified evidence that no citizen report supplies.
**Impact:** Honestly implemented, this ranks nothing, ever. The demo hides that by hard-coding ratings (P-02).
**Fix:** Two tiers.
- **Tier 1 (new, always computable):** the five-component triage score in `REBUILD_02` §4, from `config/rules/triage-v2.json`. Drives the officer worklist order.
- **Tier 2 (existing, unchanged):** keep `priority-v1.json` and its gates for *capital-referral eligibility only*. It abstains most of the time — which is correct and now harmless.
**Verify:** Every group has a Tier-1 band. Most groups show Tier 2 as "Not eligible for capital referral — verification required," with named abstention codes.

---

### P-05 — No photo support anywhere
**Severity:** BLOCKER (it is the prerequisite for P-03)
**Evidence:** Zero references to images in `apps/api/src`, the DB models, or `contracts/openapi.json`. `IMPLEMENTATION_DECISIONS.md` decision 1 deferred it. A complete 3-photo uploader exists in the **dead** `src/pages/ReportPage.tsx` (`MAX_PHOTOS = 3`, JPEG/PNG/WebP).
**Impact:** No machine-readable location, no verification against fabricated reports, and no evidence for the visual problem categories (roads, garbage, waterlogging) that dominate real usage.
**Fix:** Re-activate `STAGE_4 §8` for images: up to 3 files, JPEG/PNG/WebP, 8 MB each, magic-byte validation, Pillow decode check and re-encode. **Extract EXIF GPS server-side before stripping metadata**, persist the coordinates to the report row, then store the sanitised image. Salvage the dead uploader component first.
**Scope note:** Upload, preview and EXIF only. **No vision model, no automatic severity detection, no custom ML.** Photos are evidence for humans and a location source for the machine. That is enough.
**Verify:** A geotagged phone photo produces `latitude`/`longitude` on the report row, and the stored image contains no EXIF.

---

### P-06 — A submitted report is a dead end
**Severity:** BLOCKER
**Evidence:** `modules/planning/api.py::overview` appends fresh reports into a lane labelled *"Fresh report awaiting relationship review: unknown"*. No code path advances them further.
**Impact:** The live demo's own submission flow visibly terminates in a status that never changes. This is the most damaging thing a reviewer can be shown.
**Fix:** Falls out of P-01 + P-03 + P-04. After clustering, a fresh report either joins an existing group (receipt says *"joined 11 other reports"*) or starts a new one (*"first report about this — we will watch for more"*).
**Verify:** Submit two similar nearby reports; the second receipt says it joined the first.

---

## Category 2 — Runtime and data integrity (HIGH)

### P-07 — No report is analysed in Postgres mode
**Severity:** HIGH
**Evidence:** `modules/intake/api.py:90` — `if get_settings().intake_backend == "memory": background_tasks.add_task(...)`.
**Impact:** In any real deployment, reports are accepted and never processed. The production path has no analysis trigger at all.
**Fix:** A durable job table with `claim`/`retry`/`lease`/`dead-letter`, plus a worker command. Insert report and job in one transaction; enqueue after commit. `STAGE_6 §12` already specifies this correctly — implement it.
**Verify:** With `intake_backend=postgres`, a submitted report reaches `processed` with the worker running, and stays `queued` with it stopped.

---

### P-08 — Officer decisions live in process memory
**Severity:** HIGH
**Evidence:** `HumanDecisionService.__init__` → `self._by_session_need: dict[...]`; `WorkflowReviewService` identical. Both are behind `@lru_cache` factory functions.
**Impact:** API restart destroys every decision. On more than one instance, decisions appear and vanish depending on which container serves the request. This is a hard deployment blocker, and it silently destroys the append-only audit trail that is the project's best feature.
**Fix:** Persist to Postgres, append-only, preserving `expected_version`, `supersedes_id` and the evidence digest exactly as they are now. Remove `@lru_cache` from every service factory that holds mutable state or a DB session.
**Verify:** Record a decision, restart the API, the decision is still in the history.

---

### P-09 — Officer read endpoints are unauthenticated
**Severity:** HIGH
**Evidence:** `modules/planning/api.py` declares no auth dependency. Only `decisions/api.py` and `workflow_reviews/api.py` call `authenticate_demo_session`.
**Impact:** Anyone with the URL reads the whole officer console. For a product whose pitch is governance and accountability, this is the easiest possible criticism.
**Fix:** One auth dependency applied to the `/officer` router, covering reads and writes.
**Verify:** `curl /api/v1/officer/overview` without a token returns 401.

---

### P-10 — Cost control is a non-durable in-memory counter
**Severity:** HIGH
**Evidence:** `DailyCallBudget` holds `self._used = 0` in the process, reset on restart, per-process.
**Impact:** With a real Gemini key, spend is unbounded. Restart the API and the day's cap resets.
**Fix:** Persist the counter (Postgres row or Redis) keyed by UTC date. Add a per-session cap as well as a daily cap. Fail closed — when the cap is hit, queue the report and label it *"analysis pending,"* never drop it.
**Verify:** Restart mid-day; the consumed count is retained.

---

### P-11 — 60-report corpus makes the product unprovable
**Severity:** HIGH
**Evidence:** `data/demo/v1/reports.json` contains 60 records; `IMPLEMENTATION_DECISIONS.md` decision 3 chose 60 over 120.
**Impact:** Deduplication and ranking are meaningless at this scale — a human eyeballs 60 rows faster than any algorithm. The small corpus is a major reason the demo reads as artificial.
**Fix:** Extend `scripts/generate_demo_data.py` to emit 20k–50k reports across ~30 wards, 8 categories and 12 months, with deliberate duplicate bursts, one genuine recurrence-after-closure case, one high-volume-but-trivial case and one low-volume-but-critical case. Keep the 60 curated reports as a named regression scenario.
**Verify:** The dashboard shows tens of thousands of reports collapsed into hundreds of ranked groups.

---

### P-12 — Grouping has no algorithm, only a predicate
**Severity:** HIGH
**Evidence:** `evaluate_same_incident(left, right)` compares exactly two reports. No caller, no clustering pass, no assignment logic.
**Impact:** Even wired up, pairwise comparison at 50k reports is ~1.25 billion calls.
**Fix:** Bucket by `(category, geohash-7)`, check the 8 neighbouring cells, apply the distance and time gates only inside a bucket. O(N). Keep `evaluate_same_incident` as the in-bucket verification step so its tests remain meaningful.
**Verify:** Clustering 50k reports completes in seconds, not hours.

---

## Category 3 — Frontend structure (HIGH)

### P-13 — Two complete frontends in one repository
**Severity:** HIGH
**Evidence:** Live `main.tsx → app/router.tsx → features/**` versus dead `App.tsx → pages/**`. `src/App.tsx` imports `./pages/CivicNeedWorkspace`, which does not exist. `tsconfig.app.json` carries an 11-entry `exclude` list to hide the dead tree.
**Impact:** Every visual change risks editing the wrong file. This is the direct cause of the "under repair" impression.
**Fix:** Salvage `PhotoInput` from `pages/ReportPage.tsx`, then delete `src/App.tsx`, `src/pages/**`, `src/index.css`, `src/data/mockData.ts`, and `src/components/{Button,Input,StatusPill,ProvenanceBadge,VoiceRecorder,index}.tsx`. Empty the `exclude` array.
**Verify:** `exclude: []` and the build passes.

---

### P-14 — Two Tailwind versions and two colour systems
**Severity:** HIGH
**Evidence:** `src/styles/global.css` uses Tailwind v4 (`@import "tailwindcss"`) with oklch teal tokens. `src/index.css` uses v3 directives (`@tailwind base`) against `tailwind.config.js`, which defines an unrelated blue palette (`primary: #0066ff`). `postcss.config.js` belongs to the v3 setup; `@tailwindcss/vite` to the v4 setup.
**Impact:** Two design languages fight in one tree. Colours are unpredictable.
**Fix:** Keep Tailwind v4 and `@tailwindcss/vite`. Delete `tailwind.config.js` and `postcss.config.js`. Replace the token block in `global.css` with the palette in `REBUILD_03` §2.
**Verify:** One CSS entry point, one token source, no `tailwind.config.js`.

---

### P-15 — The UI reads as a SaaS product, not a public service
**Severity:** HIGH
**Evidence:** Geist Variable font; oklch teal; masked gradient grid background; `text-[clamp(2.8rem,6vw,5.4rem)]` with `tracking-[-0.06em]`; `backdrop-blur-xl`; `rounded-2xl` with `shadow-[0_28px_70px_...]`.
**Impact:** That is Linear/Vercel visual language. An Indian civic user does not read it as a trustworthy public service; they read it as a startup. Trust signals here are density, high contrast, official identity, large type, large tap targets, and their own language visible immediately.
**Fix:** `REBUILD_03` §2–§3 — Noto Sans family (harmonised with Noto Sans Kannada and Devanagari), institutional blue, 4–6px radii, 1px borders, no gradients, no glass, minimal shadow, near-black on white.
**Verify:** Screenshot next to DigiLocker/UMANG and next to Linear — it should look like the former.

---

### P-16 — No language switcher in the interface
**Severity:** HIGH
**Evidence:** A `language_hint` dropdown exists **inside the report form**; all site chrome is hard-coded English. Stage 6 explicitly deferred "full Kannada/Hindi interface localization."
**Impact:** A Bengaluru civic platform whose interface is English-only is not usable by a large share of its intended users, and cannot honestly claim to be an Indian public-service product. This is the single largest gap between the pitch and the artefact.
**Fix:** EN / ಕನ್ನಡ / हिंदी switcher persistent in the header, choice stored in `localStorage`, default from `navigator.language`. Extract every citizen-facing string into three JSON files. **The officer console may stay English-only** — officers are internal users, and that keeps the work finite.
**Verify:** Switching to Kannada changes every string on `/`, `/report`, `/receipt/:id` and `/nearby`.

---

### P-17 — No public transparency surface
**Severity:** HIGH
**Evidence:** Routes are `/`, `/report`, `/receipt/:publicId`, `/officer/*`. There is no aggregate public view.
**Impact:** A citizen submits into a black box, receives a reference code, and has no reason to return. This is also the unresolved question *"should the public see the analysis?"* — the answer is yes, in aggregate, and it is the clearest differentiator over every existing complaint portal.
**Fix:** New route `/nearby` — map of grouped problems, ward filter, three counters (reports / grouped problems / referred), top problems this month with bands, and recent officer decisions with reasons. No personal data, no precise coordinates, no reporter identity.
**Verify:** A citizen can see grouped problems and decisions for their ward without logging in.

---

### P-18 — The report form is a wall
**Severity:** HIGH
**Evidence:** `features/report-intake/ReportPage.tsx` — a 2000-character textarea, free-text locality, a language dropdown, a prominent voice card, two consent checkboxes with legal copy, and a submit button that starts disabled.
**Impact:** For a low-literacy user on a low-end phone this is unusable. Stage 2 §5 specified a four-step mobile stepper with photo, GPS and a confirmation card; the build shipped a single dense form instead.
**Fix:** `REBUILD_03` §4 — icon category grid → photo/camera → confirm location on a map → optional one-line note → submit. Four taps. Restore Stage 2's Screen 3 "this is how we understood your report" confirmation card, which was never built.
**Verify:** A report is submitted on a phone in under 60 seconds without typing a sentence.

---

## Category 4 — Layout and consistency (MEDIUM)

### P-19 — Inconsistent container widths and large dead gutters
**Severity:** MEDIUM
**Evidence:** `max-w-[1440px]` (home, header, footer), `max-w-[1500px]` (incident detail), `max-w-[1600px]` (officer overview, need workspace), plus `lg:px-10`.
**Impact:** Content jumps horizontally on every navigation, and on a 1920px display roughly 280px per side is empty while the officer sidebar is dark — the combination reads as unfinished. This is the "gap on the left and right" the owner noticed.
**Fix:** Two tokens only — `--container-reading: 1120px` for citizen pages, and full-bleed with a 24px gutter for the officer console. No page sets its own width.
**Verify:** Navigating between any two pages does not shift the content edge.

---

### P-20 — Disclaimers dominate every surface
**Severity:** MEDIUM
**Evidence:** *"Synthetic demonstration"*, *"This is not an emergency service"*, *"Submitted as evidence, not a verified fact"*, *"Report count is not unique people"*, *"Decision support only · Human review required"*, *"AI interprets evidence. Rules evaluate it. People decide."*, *"No live civic records or official actions."* — present on nearly every screen, sometimes twice on one card.
**Impact:** The intent is admirable and the epistemics are genuinely a strength. The cumulative effect is a product that apologises for existing, and it crowds out the actual task.
**Fix:** One slim persistent top strip carrying the demo disclosure and the emergency-services notice. Move epistemic caveats (*"report count is evidence volume, not people"*) into the officer console **beside the number they qualify**, where they change a decision. Remove them from citizen surfaces entirely except the emergency notice.
**Verify:** The citizen home page contains exactly one disclosure strip.

---

### P-21 — The officer console has no tools
**Severity:** MEDIUM
**Evidence:** `OfficerOverviewPage.tsx` renders 6 items as cards, with a client-side text filter over `title`/`locality`/`category`/`status` and nothing else. No map, no sort, no assignment, no age, no bulk action, no score explanation.
**Impact:** It is a marketing layout wearing a console's name. An officer's tool is a dense sortable table plus a map.
**Fix:** `REBUILD_03` §6 — filter rail, dense sortable table, synced map, score-breakdown side panel, keyboard navigation. Safety lane pinned above as a red strip.
**Verify:** Sort by score descending, click row 1, see the five components with their numbers and evidence links.

---

### P-22 — Voice is over-promoted relative to its value
**Severity:** MEDIUM
**Evidence:** A dedicated "Prefer to speak?" card with a Record button sits in the form; photos have no presence at all. `STAGE_6 §12` makes 30-second voice a P0 capability, and audio bytes are passed synchronously into the interpretation call (up to 6 MB).
**Impact:** Voice yields no location, no verification and no literacy advantage over tapping an icon, while costing more, adding latency and being hard to moderate. Most users will not record audio about a pothole.
**Fix:** Demote voice to a small "Speak instead of typing" affordance inside the note step. Promote photos to their own step. Move audio out of the request path into the job worker.
**Verify:** The photo step is more prominent than the voice affordance.

---

## Category 5 — Hygiene (LOW / MEDIUM)

### P-23 — `@lru_cache` used for stateful singletons
**Severity:** MEDIUM
**Evidence:** `get_intake_repository`, `get_intake_service`, `get_report_analysis_service`, `get_golden_demo_read_service`, `get_workflow_review_service` are all `@lru_cache`.
**Impact:** Hidden global mutable state holding DB sessions. Works in a single-process demo; causes cross-test leakage and concurrency bugs at scale.
**Fix:** Cache only immutable, config-derived objects (the policy bundle is a legitimate case). Use FastAPI lifespan state for connection pools and request-scoped dependencies for services.

### P-24 — "AI" is substring matching
**Severity:** MEDIUM (HIGH for credibility)
**Evidence:** `infrastructure/ai/fake.py` — `road = any(token in text for token in ("pothole", "road broken", ...))`.
**Impact:** Legitimate as a *deterministic test fixture*, and it is honestly named `FixtureInterpreter`. The risk is presentational: if the demo runs on the fixture while the pitch says "Gemini," that is indefensible under questioning.
**Fix:** Get `GoogleGenAIInterpreter` actually working with a key. Keep the fixture as the offline/test path and label the active backend in the UI (`fresh_ai` vs `fresh_fixture` — the field already exists in `InterpretationEnvelope.result_class`; surface it).

### P-25 — Voice audio in the synchronous request path
**Severity:** MEDIUM
**Evidence:** `InterpretationRequest.audio_data` accepts up to 6 MB and `ReportAnalysisService.process` reads storage inline.
**Fix:** Job worker only; never in the HTTP request.

### P-26 — Suspicious constraint in the public-evidence model
**Severity:** MEDIUM
**Evidence:** Flagged by the previous agent as unresolved; not yet verified against a real database.
**Fix:** Review `infrastructure/db/models.py` public-evidence constraints and fix before running Postgres integration tests.

### P-27 — No frontend or end-to-end tests
**Severity:** MEDIUM
**Fix:** Playwright covering exactly two flows: citizen submit → receipt shows grouping outcome; officer login → sort → open → decide → decision appears in history after reload. Two tests are worth more than a coverage target.

### P-28 — No accessibility verification
**Severity:** MEDIUM
**Fix:** Contrast ≥4.5:1, visible focus order, labelled inputs, 48×48 tap targets, screen-reader pass on the report flow, and correct `lang` attributes for Kannada and Devanagari text.

### P-29 — No rate limiting, moderation or retention cleanup
**Severity:** MEDIUM
**Impact:** One user can manufacture a fake top-priority problem by submitting 50 reports. Directly attacks the credibility of the ranking.
**Fix:** Per-IP and per-session rate limits, a moderation queue for flagged content, scheduled voice/image retention cleanup, and — importantly — count **distinct reporters**, not reports, in the score (see `REBUILD_02` §4.1).

### P-30 — Documentation outweighs implementation
**Severity:** LOW (but it is the root cause)
**Evidence:** ~4,600 lines across six stage documents versus ~3,500 lines of application code, and the most heavily documented subsystem has no callers.
**Fix:** Write no further stage documents. The four `REBUILD_*` files are the last planning artefacts. Update them in place rather than adding new ones.

### P-31 — No evaluation of correctness
**Severity:** MEDIUM
**Evidence:** `data/held-out/v1/` and `data/tuning/v1/` exist and are referenced by no measurement code.
**Impact:** There is no way to state whether grouping is *right*, only that it runs. This is the difference between "I built a system" and "I built a system that works."
**Fix:** A script that runs the pipeline over the held-out set and reports grouping precision/recall plus rank correlation against the labelled expectations. One number you can defend.

---

## Summary table

| ID | Severity | One-line |
|---|---|---|
| P-01 | BLOCKER | Decision engine has no callers |
| P-02 | BLOCKER | Dashboard reads hand-typed JSON |
| P-03 | BLOCKER | No coordinates, so grouping cannot work |
| P-04 | BLOCKER | Priority rubric abstains on everything real |
| P-05 | BLOCKER | No photo support |
| P-06 | BLOCKER | Submitted reports dead-end |
| P-07 | HIGH | No analysis in Postgres mode |
| P-08 | HIGH | Decisions in process memory |
| P-09 | HIGH | Officer reads unauthenticated |
| P-10 | HIGH | Non-durable AI cost cap |
| P-11 | HIGH | 60-report corpus |
| P-12 | HIGH | Grouping has no algorithm |
| P-13 | HIGH | Two frontends |
| P-14 | HIGH | Two Tailwind versions |
| P-15 | HIGH | Looks like SaaS, not public service |
| P-16 | HIGH | No language switcher |
| P-17 | HIGH | No public transparency surface |
| P-18 | HIGH | Report form is a wall |
| P-19 | MEDIUM | Inconsistent widths, dead gutters |
| P-20 | MEDIUM | Disclaimers dominate |
| P-21 | MEDIUM | Officer console has no tools |
| P-22 | MEDIUM | Voice over-promoted |
| P-23 | MEDIUM | `lru_cache` singletons |
| P-24 | MEDIUM | "AI" is substring matching |
| P-25 | MEDIUM | Audio in request path |
| P-26 | MEDIUM | Suspicious DB constraint |
| P-27 | MEDIUM | No frontend/E2E tests |
| P-28 | MEDIUM | No accessibility pass |
| P-29 | MEDIUM | No rate limiting or moderation |
| P-30 | LOW | Docs outweigh code |
| P-31 | MEDIUM | No correctness evaluation |
