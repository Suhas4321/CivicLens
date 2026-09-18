# CivicLens Rebuild — Handoff, Scope Reset and Reading Order

**Written:** 15 September 2026
**Status:** Authoritative. This document and the five `REBUILD_*` documents beside it **supersede** the Stage 1–6 documents wherever they disagree.
**Reading order:** `REBUILD_00` → `REBUILD_01` → `REBUILD_04` → `REBUILD_05` → `REBUILD_02` → `REBUILD_03`. Where `REBUILD_04` and `REBUILD_05` disagree with `REBUILD_02`/`REBUILD_03`, the later document wins; each carries an explicit supersession table.
**Audience:** The product owner (a solo beginner developer) and any AI coding agent picking up this work.

---

## 0. If you are an AI agent reading this, read this section first

You are joining a project that has already been through six planning stages and one implementation pass. **The implementation pass produced a demo that does not work the way the documents claim.** Do not assume the code matches the docs. Do not assume the docs are wrong either — the truth is more specific than that, and is written out in §2.

**Rules for this rebuild:**

1. **Do not write more stage-planning documents.** There are already ~4,600 lines of them against ~3,500 lines of code. That imbalance is the root cause of the current state. Write code, or write nothing.
2. **The Stage 1–6 documents now live in `docs/archive/`.** They are a historical record only. **Do not read them for guidance and do not implement anything found in them** — several of their instructions are the direct cause of the defects in §2. `docs/archive/README.md` records what is salvageable in each and what is wrong. When they conflict with a `REBUILD_*` document, the `REBUILD_*` document wins, always.
3. **Do not fabricate progress.** If a module has no caller, say so. The previous pass shipped a fully tested decision engine that nothing calls, and a dashboard that reads hand-typed JSON, while reporting both as complete. That is the single failure mode to avoid.
4. **Every feature must be reachable end-to-end from the browser before it is called done.** "Tests pass" is not done. "Type-check passes" is not done. Done = a user action in the UI causes the intended change in the database and the intended change on screen.
5. **The scope has changed.** This is no longer a hackathon submission. See §3.

---

## 1. What the project is, in one paragraph

Citizens report everyday civic problems (no water, broken road, garbage, exposed wire) in plain language from a phone. CivicLens groups reports that are about **the same physical problem in the same place**, so that 30 complaints about one road become **one problem with 30 pieces of evidence** instead of 30 separate tickets. It then **ranks those grouped problems** by a transparent, published formula — how many distinct people, how long it has persisted, how exposed the location is (hospital, school, major road), how severe the category is — and shows a municipal officer a ranked worklist where every rank can be explained by pointing at the evidence. Dangerous hazards skip the ranking entirely and go to an immediate-review lane. A human always makes the final call, and every decision is recorded append-only against the exact evidence that was on screen.

**The problem being solved:** existing Indian grievance portals (Sahaaya, Swachhata, CPGRAMS) treat every complaint as an independent ticket — as does the Open311 standard itself, which defines no deduplication mechanism at all. There is no notion of *"these are all one problem"* and no notion of *"this problem matters more than that one."* Volume becomes noise, and the loudest area wins instead of the worst problem.

---

## 2. The true current state of the code (verified 15 Sep 2026)

### 2.1 The core finding: the decision engine has no callers

| Function | File | Production callers |
|---|---|---|
| `evaluate_priority` | `modules/priority/evaluator.py` | **0** — tests only |
| `evaluate_same_incident` | `modules/relationships/evaluator.py` | **0** — tests only |
| `evaluate_recurrence` | `modules/relationships/evaluator.py` | **0** — tests only |
| `generate_candidate` | `modules/catalogue/evaluator.py` | **0** — tests only |

The officer dashboard is served by `GoldenDemoReadService` (`modules/planning/read_service.py`), which reads `data/demo/v1/ground_truth.json`. In that file, priority is **hand-typed**:

```json
"priority": { "band": "high", "components": {
    "persistence_spread":   { "rating": 3 },
    "service_disadvantage": { "rating": 3 } } }
```

**There is no prioritisation happening. A human typed `"high"` into a JSON file.** The 30 passing backend tests test an engine that is not wired into the application.

### 2.2 A freshly submitted report is a dead end

Submit → intake → keyword matcher → safety check → appears in the officer "operational" lane as *"Fresh report awaiting relationship review: unknown"* → **stops permanently.** It can never join a group (nothing calls the grouping evaluator) and can never be ranked (nothing calls the priority evaluator).

### 2.3 The "AI" is keyword matching

`infrastructure/ai/fake.py` is the active interpreter:

```python
road  = any(token in text for token in ("pothole", "road broken", "ಗುಂಡಿ", "सड़क"))
water = any(token in text for token in ("water", "ನೀರು", "पानी"))
```

The Gemini adapter (`infrastructure/ai/google_genai.py`) exists but has never been executed with a key.

### 2.4 Two complete frontends coexist in one repo

| | Live | Dead (excluded in `tsconfig.app.json`) |
|---|---|---|
| Entry | `src/main.tsx` → `src/app/router.tsx` | `src/App.tsx` |
| Pages | `src/features/**` | `src/pages/**` |
| CSS | `src/styles/global.css` — **Tailwind v4**, oklch, teal | `src/index.css` — **Tailwind v3** syntax |
| Theme | oklch tokens in `global.css` | `tailwind.config.js` — blue `#0066ff` |
| Components | `components/ui/**` (shadcn) + `components/civic/**` | `components/{Button,Input,StatusPill,ProvenanceBadge,VoiceRecorder}.tsx` |

`src/App.tsx` imports `./pages/CivicNeedWorkspace`, **which does not exist**. `tsconfig.app.json` carries an 11-entry `exclude` list to hide the dead tree from the compiler. Two Tailwind major versions, two colour systems and two button components are simultaneously present. This is why the site visually reads as "under repair."

**Note:** the *dead* `src/pages/ReportPage.tsx` contains a complete, working 3-photo uploader with previews and object-URL cleanup. It must be salvaged before that tree is deleted.

### 2.5 Other verified defects

| Area | Defect |
|---|---|
| Jobs | `modules/intake/api.py` triggers analysis only when `intake_backend == "memory"`. **In Postgres mode no report is ever analysed.** There is no job queue at all. |
| Persistence | `HumanDecisionService` and `WorkflowReviewService` store to in-process `dict`s. Restart = all officer decisions lost. Two instances = decisions randomly visible. |
| Auth | `/officer/overview`, `/officer/needs/{id}`, `/officer/incidents/{id}` have **no authentication**. Only write endpoints check a demo-session bearer. |
| Location | The report form collects a **free-text** locality string. `evaluate_same_incident` requires coordinates to reach `high` confidence; without them, identical locality text yields only `"review"` and differing text yields `"not_eligible"`. **Grouping is therefore mathematically impossible with the data currently collected.** |
| Grouping | Only a pairwise predicate exists. There is no clustering pass, no report→group assignment, no batching. At 50k reports pairwise is 1.25 billion comparisons. |
| Photos | Zero support in the API, the DB models or `contracts/openapi.json`. |
| Cost control | `DailyCallBudget` is an in-memory integer. Resets on restart, per-process. Not a budget guard. |
| Layout | Page containers are `max-w-[1440px]` (home, chrome), `1500px` (incident), `1600px` (officer). Nothing aligns across navigation, and on a 1920px display the content leaves ~280px of dead gutter per side. |
| Demo scale | The corpus is **60 reports**. Nothing about grouping or ranking is demonstrable at 60. |

### 2.6 What is genuinely good and must be preserved

Do not throw these away during the rebuild. They are the strongest parts of the project.

- Clean backend module boundaries (`intake` / `analysis` / `relationships` / `priority` / `catalogue` / `decisions`).
- Pydantic models with `extra="forbid"` throughout — strict, disciplined.
- Rules externalised to versioned JSON in `config/rules/` with a `policy_version` stamped onto every output. Keep this pattern; it is what makes the ranking defensible.
- Receipt lookup is an HMAC capability check where a wrong capability returns 404, indistinguishable from an unknown ID. Thoughtful.
- Idempotency keys plus optimistic-concurrency `expected_version` on writes.
- Append-only decision history with `supersedes_id` and a frozen evidence digest. The audit story is legitimately good.
- Prompt-injection quarantine in the interpreter (instruction-like text → `category: unknown`).
- The **separation of a safety lane from a ranked planning lane** is correct product design and should survive verbatim.

---

## 3. Scope reset

### 3.1 The old scope and why it failed

The project was designed for a hackathon with a Google/Gemini track, and Stage 6 froze it into a *narrated demo* rather than a working system. The promise was: **"identify capital planning needs from citizen reports."** That promise requires verified engineering evidence per complaint, authoritative ward polygons, and a legal basis to influence municipal budgets. None of those were obtainable, so the eligibility gates in `config/rules/priority-v1.json` (`unknown_prevents_comparison: true`) meant nothing could ever rank — and the demo had to hard-code the ranking to have anything to show.

**The design was not stupid; it was self-blocking, and fixtures hid the block.**

### 3.2 The new scope

> **CivicLens turns thousands of messy citizen complaints into a deduplicated, ranked, evidence-linked worklist — where every rank can be explained, dangerous hazards bypass ranking, and a human makes every decision.**

This is buildable by one beginner developer, is demonstrable, solves a real problem, and does not require data nobody will give you.

**Explicitly still in scope:** grouping, ranking, safety lane, evidence view, append-only human decisions, public transparency view, multilingual citizen UI, photo upload with EXIF location.

**Explicitly out of scope (and to be stated openly in the UI and README):** approving budgets, naming departments, claiming affected-population figures, integration with any real corporation system, live public data feeds, custom-trained ML models, vision models.

### 3.3 The two-tier design that unblocks everything

The old design had one ranking mechanism with strict gates, so it abstained on everything. Replace it with **two tiers**:

| Tier | Name | Gates | Always produces an answer? |
|---|---|---|---|
| **1** | **Triage rank** — orders the officer's daily worklist | Needs only a usable location and a category | **Yes** |
| **2** | **Capital-referral eligibility** — the strict old gates, kept intact | Verified root cause, confirmed recurrence, alternatives reviewed, compatible evidence | **No — abstains most of the time, and that is correct** |

Tier 1 makes the product useful. Tier 2 preserves the intellectual honesty that made the original design good. Abstaining in Tier 2 now looks rigorous instead of broken, because Tier 1 is still doing visible work.

Full specification: **`REBUILD_02_DATA_PIPELINE_AND_PRIORITY.md`**.

---

## 4. Superseded decisions

`IMPLEMENTATION_DECISIONS.md` (approved 12 Sep 2026) froze five choices. **Four of them are the direct cause of the problems in §2.** They are hereby superseded. Do not revert to them.

| # | Old decision (12 Sep 2026) | New decision (15 Sep 2026) | Why |
|---|---|---|---|
| 1 | "v1 citizen input is text plus one short voice attachment; **image upload is deferred**." | **Image upload is now P0.** Up to 3 photos. Voice is demoted to an accessibility fallback. | Photos are the only cheap source of machine-comparable location (EXIF GPS) and the only defence against fabricated reports. Deferring images is what made grouping impossible. Voice provides no location, costs more, and adds latency. |
| 2 | "v1 has **no Google Map dependency**; it uses honest locality and coordinate summaries." | **A map and coordinates are now P0.** Use a free tile provider (OpenStreetMap / MapLibre) — no Google Maps key needed. | Free-text locality cannot be compared by machine. Without coordinates, the grouping rules can never fire. This decision is what broke the core of the product. |
| 3 | "the demo corpus contains **60 curated synthetic reports**." | **Generate 20,000–50,000 synthetic reports** across wards, categories and 12 months. Keep the 60 curated ones as a named regression scenario. | Grouping and ranking are not demonstrable at 60. The small corpus is a large part of why the demo reads as fake. |
| 4 | "the four prototype priority components retain the `30/25/25/20` profile with visible sensitivity and abstention." | **Keep it as Tier 2 only.** Tier 1 uses the five-component triage score in `REBUILD_02`. | The four components require verified evidence that does not exist, so they abstain on everything real. |
| 5 | "public judge access uses anonymous Firebase identity, immutable shared seed data and session-scoped action overlays." | **Retained, but decisions must persist to Postgres**, not to in-process dicts. | Current in-memory storage loses every decision on restart and is incorrect on more than one instance. |

**One Stage 6 UI rule is also overridden.** Stage 6 §13 says the UI must "never [show] an `87/100` headline." The Tier-1 triage score *is* a number, because a worklist needs an order. Resolution: **show the band prominently, the rank position, and the score with its five-component breakdown always one click away.** The number is never presented as precision or as a measure of citizen suffering — it is labelled *"triage score — how this queue is ordered."* This is a deliberate, recorded override, not an oversight.

---

## 5. Status of the existing documents

Nothing has been deleted. All seven Stage documents were **moved to `docs/archive/`** on 15 September 2026. This table tells you what to trust; `docs/archive/README.md` carries the detailed salvage index.

| Document | Status | Notes |
|---|---|---|
| `archive/STAGE_1_RESEARCH_AND_PRODUCT_DISCOVERY.md` | **Historical — still useful** | The comparable-systems research (§2), failure evidence (§2.3) and "mistakes to avoid" (§11) remain good. Ignore all hackathon timeline/judging content (§1, §7). **§4.3 pivots the hero object from "complaint" to "need/project candidate" — that pivot is rejected. It is the origin of the product inversion.** |
| `archive/STAGE_2_PRODUCT_DESIGN.md` | **Partly authoritative — better than the code** | §5 (citizen journey), §7 Screens 1–4 and §8 (map) specify photos, GPS/map-pin, auto language detection and a "review understanding" confirmation screen. **The build silently dropped all four.** `REBUILD_03` restores them. Its "Citizen UX decisions" list and five provenance labels are good — keep them. §13's "not primarily a grievance tracker" is rejected. |
| `archive/STAGE_2_INDEPENDENT_REVIEW_REVISION.md` | **Historical** | The two-lane split (§B) survives. The planning-priority rule and the `30/25/25/20` ordinal components are superseded by `REBUILD_04 §5`. |
| `archive/STAGE_3_SYSTEM_DESIGN.md` | **Mostly authoritative** | Architecture (§2), AI may/may-not contract (§6), the three-relationship separation (§10), storage (§16), security/privacy (§17), threat model (§18), failure handling (§19) and observability (§20) are sound and should be followed. §17's "EXIF is not used for silent geolocation; the reporter confirms map location" is **exactly right** — see `REBUILD_05 §1.2`. §13's priority design is superseded. |
| `archive/STAGE_4_IMPLEMENTATION_DESIGN.md` | **Authoritative on stack; §8 re-activated** | §3 stack, §5 module template + ports, §11 config/secrets, §12 deployment, §13 cost, §14 testing pyramid, §17 local dev, §19 risk review all stand. §8 (media limits, sanitise-on-upload, Pillow re-encode, magic-byte validation) was written then deferred away — **re-activated for images**; note the ordering caveat in `REBUILD_05 §3.2`. **§1's Google Maps and §45's "No PostGIS" are both rejected** — see `REBUILD_05 §1.3` and `§2.1`. |
| `archive/STAGE_5_BUILD_PLAN.md` | **Obsolete as a plan; useful as process** | Milestones assume the Golden-Demo read path that is being replaced, and §2's JICA/Mahadevapura geography is wrong (we are in Bengaluru **South**). But §3's Definition of Done + stop-the-line conditions, §16's test matrix and §19's scope-cut order are good practice worth reusing. Build order comes from `REBUILD_05 §10`. |
| `archive/STAGE_6_FINAL_DESIGN_REVIEW.md` | **Partly obsolete** | §14 security review and the anticipated-challenges list (§3) are still valuable. §4 "Deferred from v1" (which killed images and maps), §7's Mahadevapura geography, §9's PostGIS exclusion, §12 intake and §13 priority policy are all superseded. |
| `IMPLEMENTATION_DECISIONS.md` | **Superseded in full** | All five approved defaults are overridden — images are in, maps are in (MapLibre, not Google), the corpus is 20k–50k not 60, and the `30/25/25/20` profile is replaced by `REBUILD_04 §5.6`. |

---

## 6. Work order

Do these in order. Do not start a later item to avoid a harder earlier one.

### Phase A — Clear the ground (about a day)

| # | Task | Done when |
|---|---|---|
| A1 | Salvage the photo uploader out of `src/pages/ReportPage.tsx` into a reusable `PhotoInput` component under the live tree | Component renders in the live app |
| A2 | Delete the dead frontend: `src/App.tsx`, `src/pages/**`, `src/index.css`, `src/data/mockData.ts`, `tailwind.config.js`, `postcss.config.js`, `src/components/{Button,Input,StatusPill,ProvenanceBadge,VoiceRecorder,index}.tsx` | The `exclude` array in `tsconfig.app.json` is empty and the build passes |
| A3 | Adopt one design-token file and one container width | `REBUILD_03` §2 tokens are the only source of colour, type and spacing |

### Phase B — Make the pipeline real (the heart of the rebuild)

| # | Task | Done when |
|---|---|---|
| B1 | Add photos + coordinates to intake: DB columns, storage, EXIF GPS extraction, map-pin fallback, ward fallback | A submitted report has usable `latitude`/`longitude` in the database |
| B2 | Load the static geo layer (OpenStreetMap Bengaluru extract → roads with class, sensitive POIs, ward polygons) | `SELECT` returns road class and nearest sensitive POI for a given point |
| B3 | Build the clustering pass: `(category, geohash cell, 30-day window)` → problem groups | Two reports 100 m apart in the same category land in one group |
| B4 | Build the Tier-1 triage scorer from `REBUILD_02` §4, driven by `config/rules/triage-v2.json` | Every group has a score, band and a stored five-component breakdown |
| B5 | Rewire `/officer/*` to read the computed groups. Retire `GoldenDemoReadService` as the primary source | The dashboard shows computed ranks; `ground_truth.json` is used only by the regression test |
| B6 | Generate 20k–50k synthetic reports and run the whole pipeline over them | The dashboard shows thousands of reports collapsed into hundreds of ranked groups |
| B7 | Move `HumanDecisionService` and `WorkflowReviewService` to Postgres; remove the `lru_cache` singletons | Decisions survive an API restart |
| B8 | Add a real job queue with claim / retry / lease-recovery / dead-letter; trigger it in Postgres mode | A report submitted in Postgres mode reaches `processed` |

### Phase C — Make it look and feel right

| # | Task | Done when |
|---|---|---|
| C1 | Rebuild the citizen surface per `REBUILD_03` §4 | Report submitted in ≤4 taps on a phone |
| C2 | Build the public transparency surface `/nearby` per `REBUILD_03` §5 | A citizen can see grouped problems and decisions in their ward |
| C3 | Rebuild the officer console per `REBUILD_03` §6 (table + map + score breakdown) | An officer can sort by score and see why #1 is #1 |
| C4 | Language switcher (EN / ಕನ್ನಡ / हिंदी) in the header, persisted | All citizen-facing strings switch language |

### Phase D — Harden

| # | Task |
|---|---|
| D1 | Authentication on every `/officer/*` route, read included |
| D2 | Real Gemini integration for text interpretation, replacing keyword matching; persisted daily cap |
| D3 | Rate limiting, spam/moderation queue, voice-retention cleanup |
| D4 | Playwright E2E on the two critical flows; accessibility pass (contrast, focus order, labels, 48px targets) |
| D5 | Fix the suspicious Postgres constraint in the public-evidence model; run migrations against real PostgreSQL 17 |
| D6 | Deploy |

---

## 7. What we are still missing (not covered elsewhere)

Raised here so it is not forgotten. None of it is Phase A or B work.

1. **The closure loop.** There is no way to mark a problem *fixed*, which means "recurrence after closure" — the strongest signal that something is structural rather than operational — cannot be computed. Needs a `resolved` state with a timestamp and a reopen counter.
2. **Telling the citizen they were a duplicate.** The receipt currently cannot say *"your report joined 11 others."* That message is the single best trust-builder in the whole product, and the data for it exists the moment B3 lands.
3. **Spam and abuse.** No rate limit, no moderation queue, no image moderation. One malicious user can currently manufacture a fake #1 priority.
4. **Notifications.** Optional phone/email for "your problem was referred" was specified in Stage 2 and never built. Without it, citizens never come back.
5. **Ward mapping is ~~unsolved~~ resolved.** Use OpenStreetMap `place` polygons for Bengaluru South localities, ingested via `osmium` into PostGIS. ODbL, attribution required, no licence ambiguity. See `REBUILD_04 §2.2` and `REBUILD_05 §10` step 1. BBMP ward GeoJSON is not used — BBMP was dissolved 2 September 2025 and its ward boundaries no longer describe the current body.
6. **No admin surface for the weights.** The triage weights live in JSON that only a developer can edit. A published, read-only "how ranking works" page is the minimum; an admin editor is better.
7. **No evaluation harness.** There is no measurement of whether grouping is *correct* — no precision/recall against the labelled corpus. Without it you cannot claim the system works, only that it runs. `data/held-out/` exists for exactly this and is unused.
8. **Accessibility has never been tested.** For a public-service product aimed at low-literacy users this is a correctness issue, not a polish issue.
9. **No operational visibility.** No error tracking, no dashboards, no alerting. Structured logging exists (`infrastructure/telemetry/logging.py`) and nothing consumes it.

---

## 8. Reading order

1. **This document** — state of reality, scope, work order.
2. **`REBUILD_01_PROBLEM_REGISTER.md`** — every identified problem with its fix, numbered for tracking.
3. **`REBUILD_02_DATA_PIPELINE_AND_PRIORITY.md`** — how data flows and exactly how ranking is computed, with worked examples.
4. **`REBUILD_03_UI_DESIGN_BLUEPRINT.md`** — the design system and every screen for all three surfaces.
