# Archived planning documents — salvage index

**Archived:** 15 September 2026.
**These seven documents are a historical record. Do not implement from them.**

They describe a product that CivicLens is no longer trying to be, and three of their explicit instructions caused the defects the rebuild is fixing. They are kept because roughly 40% of their content is genuinely good engineering work that the rebuild reuses, and because the reasoning history matters when someone asks "why was it built this way."

**Authority lives in `docs/REBUILD_00` through `docs/REBUILD_05`.** If anything here conflicts with those, those win, without exception.

---

## Why these were archived rather than followed

Three instructions in this set are the direct cause of the biggest product gaps:

| Instruction | Where | Consequence |
|---|---|---|
| "Do not add Maps, image upload, embeddings … to v1" | `AGENTS.md` line 21 (now rewritten), traced from `STAGE_6 §4` | Photo upload and any map were **forbidden in writing** in the file every agent read first. The owner's most-wanted feature was blocked by policy, not oversight. |
| "No PostGIS: … lat/lon plus Haversine calculations are sufficient" | `STAGE_4 §45`, `STAGE_6 §9` | Forced a bespoke geohash + union-find design where an indexed `ST_DWithin` was exact and simpler. PostGIS *is* a supported Cloud SQL extension; the exclusion was a complexity judgement, not an availability constraint. |
| "CivicLens is a planning decision-support product, not primarily a grievance tracker" | `STAGE_2_PRODUCT_DESIGN §13`, originating in `STAGE_1 §4.3` | Inverted the hero object from *complaint* to *need / project candidate*. That inversion is why the shipped demo feels artificial: it ranks things no citizen ever submitted. |

### The full inversion chain, for the record

`STAGE_1 §4.3` pivots the hero object to a "Suspected Civic Need / Project Candidate" (a differentiation argument) → `STAGE_2_PRODUCT_DESIGN §13` states it outright, while Screen 2 of the same document *still had* image upload → `STAGE_2_INDEPENDENT_REVIEW_REVISION` removes acute urgency from ranking and installs the `30/25/25/20` ordinal components → `STAGE_4` still lists images and maps as **Must Have** → **`STAGE_6 §4` removes them** → `IMPLEMENTATION_DECISIONS.md` locks the removal → `AGENTS.md` encodes it as a prohibition.

Stage 1's *diagnosis* was fair: a plain complaint tracker is not differentiated. Its *prescription* was wrong. The rebuild keeps the diagnosis and answers it differently — automatic deduplication (Open311 defines no dedup mechanism at all), recurrence-after-closure detection, the 48-hour citizen verification window, the ward recurrence scorecard, and the jurisdiction dispute flag. All of those are differentiators *inside* complaint prioritisation.

---

## Per-document salvage

### `STAGE_1_RESEARCH_AND_PRODUCT_DISCOVERY.md`

**Keep:** §2 comparable-systems research. §2.3 failure evidence. **§11 "mistakes to avoid"** — still the sharpest list in the archive. The 32-source bibliography.
**Reject:** §4.3, the need/project pivot. §1 and §7 hackathon framing (the timeline is stale; the current deadline is in `REBUILD_00`).

### `STAGE_2_PRODUCT_DESIGN.md`

**Keep:** §5 citizen journey. §7 Screen 3 **"Review understanding"** — a confirmation step that never got built and should be. The "Citizen UX decisions" list. The failure-paths table. The **five provenance labels** (Real Public / Derived Public / Synthetic Demo / User Submitted / AI Derived) — used verbatim by the rebuild. The fourteen acceptance criteria.
**Reject:** §13's "not primarily a grievance tracker."
**Note:** §7 Screen 2 specified photo upload and §8 specified a map pin. Both were correct and both were later removed. `REBUILD_03` and `REBUILD_05 §1` restore them.

### `STAGE_2_INDEPENDENT_REVIEW_REVISION.md`

**Keep:** §B's two-lane split — the ancestor of the three-lane model in `REBUILD_04 §3`, and a good instinct.
**Reject:** the `30/25/25/20` ordinal components and the three sensitivity profiles (`30/25/25/20`, `45/20/20/15`, `20/45/20/15`). Superseded by `REBUILD_04 §5.6`. Removing acute urgency from ranking was the wrong call.

### `STAGE_3_SYSTEM_DESIGN.md`

The best-engineered document in the archive. **Follow its architecture; ignore its priority model.**

**Keep:** §2 trust-boundary table. §6 AI may / may-not lists and the structured response contract. §10 the three-relationship separation (same-incident / recurrence / candidate) — an important distinction. §16 storage design. §17 security and privacy. §18 threat model. §19 failure handling, including *"Map unavailable → list/locality view remains functional"*, which is exactly the Tier 5 fallback in `REBUILD_05 §1.2`. §20 observability. §12's seven gates with abstention codes (`INTERPRETATION_UNCERTAIN`, `GROUPING_UNRESOLVED`, `GEOGRAPHY_INCOMPATIBLE`, `REQUIRED_CONTEXT_MISSING`, `CONTRADICTORY_EVIDENCE`, `NO_APPLICABLE_CANDIDATE`) — these explain why the shipped demo abstains on everything, and the codes themselves are worth keeping.

**§17 says: "EXIF is not used for silent geolocation; the reporter confirms map location."** Stage 3 got this exactly right, a year before we rediscovered it. It is now `REBUILD_05 §1.2`.

**Reject:** the "Suspected Civic Need / Project Candidate" hero object. §13's four 0–3 components and weightings. §11's JICA/Mahadevapura geography. §16's "vector storage remains conditional" framing.

### `STAGE_4_IMPLEMENTATION_DESIGN.md`

**Keep:** §3 technology baseline. §4 repository structure. §5 module template and the eight infrastructure ports. **§8 media handling** — JPEG/PNG/WebP, 8 MB, 12 MP, re-encode with metadata removed; written, then deferred away, now re-activated. §11 config/secrets env-var table. §12 deployment and service-account matrix. §13 cost plan. §14 testing pyramid and the 20-scenario suite. §16 observability. §17 local dev modes. §19 risk review and kill criteria. §20 research evidence table.
**Reject:** §1's Google Maps JavaScript API (→ MapLibre + self-hosted `.pmtiles`, `REBUILD_05 §1.3`). §45's "No PostGIS" (→ PostGIS is mandatory, `REBUILD_05 §2.1`). The 30-second voice attachment as a headline feature — it stays as a small accessibility affordance, not a pillar.
**Worth knowing:** §18 classified "one short voice and one image" as **Must Have**. Images were not forgotten at design time. They were designed in, then removed by Stage 6.

### `STAGE_5_BUILD_PLAN.md`

Excellent process scaffolding attached to the wrong target.

**Keep:** §3 Definition of Done and the stop-the-line conditions. §16 cross-milestone test matrix. §17 the 26-slice PR plan as a granularity model. §19 scope-cut order. §20 release scorecard. §15's submission-package checklist (video, deck, evaluation report, incognito check) is directly useful.
**Reject:** the M0–M9 milestone content and the `R→D→S→G→I→J→A→C→N→E→P→H→X→Q→U` critical path — both assume the Golden-Demo read path being replaced. §2's "BWSSB/JICA 110-village project area … Mahadevapura 23-village project zone" is the wrong geography; we are in Bengaluru **South**. §20's *"an unfamiliar reviewer understands that needs/projects — not complaints — are prioritised"* is the inversion stated as a release criterion.
**Build order now comes from `REBUILD_05 §10`.**

### `STAGE_6_FINAL_DESIGN_REVIEW.md`

Labelled authoritative for the original build, and the proximate cause of the two feature removals.

**Keep:** §14 security risk table and release blockers. §3 anticipated-challenges list. Its warning against pseudo-precision in published metrics is right and is honoured by the `n < 5` suppression rule in `REBUILD_05 §7.3`.
**Reject:** §4 "Deferred from v1" (removed images and maps). §7's Mahadevapura geography. §9's PostGIS exclusion. §12 intake. §13 priority policy. §13's route `/officer/needs/:id` → now `/officer/problem/:id`. Its 60-report corpus → now 20k–50k on real OSM geometry.

---

## Conflicts resolved against this archive

| Conflict | Resolution |
|---|---|
| PostGIS banned (`STAGE_4 §45`, `STAGE_6 §9`) vs required (`REBUILD_04 §10.1`) | **PostGIS.** Supported on Cloud SQL; load-bearing for grouping and OSM. |
| Google Maps (`STAGE_4 §1`) vs no maps (`STAGE_6 §4`) vs maps required (owner) | **MapLibre GL + self-hosted Protomaps `.pmtiles`.** Free, keyless, cardless, offline-capable. |
| Mahadevapura / Bengaluru East (`STAGE_5 §2`, `STAGE_6 §7`) vs Bengaluru South (owner) | **Bengaluru South**, JP Nagar / Banashankari. Owner's decision. |
| `/officer/needs/:id` (`STAGE_6`) vs `/officer/problem/:id` (`REBUILD_04`) | **`/officer/problem/:id`.** The object is a problem, not a need. |
| 60 curated reports (`IMPLEMENTATION_DECISIONS.md`) vs 20k–50k (`REBUILD_04 §10.2`) | **20k–50k generated on real OSM geometry.** Grouping cannot be demonstrated at n=60. |
| EXIF as location source (`REBUILD_02 §6`) vs reporter-confirmed pin (`STAGE_3 §17`) | **Stage 3 was right.** Confirmed pin is primary; EXIF corroborates. |
| BBMP as the current municipal body (all seven documents) | BBMP was **dissolved 2 September 2025.** Use the corporation name or "GBA". |
