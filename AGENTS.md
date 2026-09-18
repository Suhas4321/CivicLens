# CivicLens implementation contract

**Last revised:** 15 September 2026. This replaces an earlier version whose reading order pointed at `docs/STAGE_*` and which explicitly forbade image upload and maps. Both are now **required features**. If you are working from a cached memory of this file, discard it.

## What CivicLens is

Citizens report everyday civic problems — no water, broken road, garbage, exposed wire — in plain language from a phone, in English, Kannada, or code-mixed Kanglish. CivicLens groups reports that describe **the same physical problem in the same place**, so 30 complaints about one road become **one problem with 30 pieces of evidence** rather than 30 tickets. It ranks those grouped problems by a published, re-derivable formula, routes each to the responsible agency, and shows a municipal officer a worklist where every rank can be explained by pointing at the evidence. Dangerous hazards skip ranking entirely. When a problem is closed, the original reporters get 48 hours to say whether it was actually fixed.

**It is a complaint prioritisation system.** Earlier planning documents drifted into calling it a "needs-to-project decision-intelligence" planning tool. That drift is rejected — see `docs/REBUILD_00_HANDOFF_AND_SCOPE.md §5`.

## Reading order

1. `docs/REBUILD_00_HANDOFF_AND_SCOPE.md` — scope, the true state of the code, work order
2. `docs/REBUILD_01_PROBLEM_REGISTER.md` — every known defect and its fix
3. `docs/REBUILD_04_PRIORITY_MODEL_AND_ROUTING.md` — the score, the three lanes, agency routing, legitimacy
4. `docs/REBUILD_05_LOCATION_ABUSE_AND_CLOSURE.md` — location intake, spatial grouping, abuse resistance, closure integrity, **the build order**
5. `docs/REBUILD_02_DATA_PIPELINE_AND_PRIORITY.md` — pipeline stages (partly superseded; read its banner)
6. `docs/REBUILD_03_UI_DESIGN_BLUEPRINT.md` — screens and design tokens (partly superseded; read its banner)

Later documents win over earlier ones. Each carries an explicit supersession table.

**`docs/archive/` is a historical record. Do not implement from it.** It contains the seven Stage 1–6 planning documents. Parts of them are genuinely good and `docs/archive/README.md` says exactly which parts — but several of their instructions caused the defects we are now fixing. Never treat an archived document as authority.

## Non-negotiable rules

- **AI interprets evidence; deterministic rules evaluate it; humans decide.** If you find yourself prompting a model for a priority number, a merge decision, or a policy, stop. The interpretation schema has no priority field, deliberately.
- **Missing or incompatible evidence is `unknown`, never zero.** A missing value must never be silently defaulted into a score.
- **Report counts never represent unique citizens or affected population.** Community Signal counts *weighted distinct reporters* and saturates at 8. Say so wherever a count is displayed.
- **Safety review never competes numerically with ranking.** Lane 1 is unscored. Lanes never interleave in one response or one list.
- **Every public, derived, synthetic and AI-derived value keeps its provenance label.**
- **Only synthetic citizen data in this prototype.** No real complaint text, ever.
- **Never log report content, media, precise coordinates, IP addresses, receipt capabilities or credentials.** Store the HMAC of a reporter key, never the address it came from.
- **Never claim verification you do not have.** `Verified (unconfirmed)` and `Verified (citizen-confirmed)` are different states and must look different. We check that resolution evidence is fresh, unique and geographically plausible; we do **not** verify that a repair happened, and must not say we do.
- **Uncertainty favours separation.** A false merge silently destroys a real problem's signal. An extra group is visible noise an officer fixes in one click.
- **Nothing is done until it is reachable end-to-end from the browser.** "Tests pass" is not done. "Type-check passes" is not done. Done = a user action in the UI causes the intended database change and the intended change on screen.
- **Do not fabricate progress.** If a module has no caller, say so. The previous pass shipped a fully tested decision engine that nothing calls, and reported it as complete. That is the one failure mode to avoid above all others.
- Run the smallest relevant checks after each change; expand testing at release gates. Keep the default branch runnable.

## Required features (previously forbidden — this is the correction)

- **Image upload.** Up to 3 photos, 8 MB each, 12 MP cap, magic-byte validation, Pillow decode/re-encode, HEIC accepted and converted. Read EXIF GPS → persist to the row → **then** strip all metadata → store. Officers judge severity from these photos; that is the whole point.
- **Maps.** MapLibre GL JS with a self-hosted Protomaps `.pmtiles` extract of Bengaluru South, served as a static asset. **No Google Maps API, no billing-enabled key, and no use of the public `tile.openstreetmap.org` servers.** Attribution `© OpenStreetMap contributors` must be visible on every map.
- **PostGIS.** Mandatory. `geography(Point,4326)` + GiST + `ST_DWithin`. Grouping, road snapping and locality resolution all depend on it. Do not hand-roll geohash bucketing or Haversine in Python.

Still out of scope for v1: embeddings and vector search (flag exists, disabled), microservices, budget/procurement modelling, live public-data feeds, vision models, phone/OTP verification, and any WhatsApp integration.

## Geography

**Bengaluru South City Corporation**, HQ Jayanagara, 72 wards, ~147 km², focused on the JP Nagar / Banashankari area. Agencies: BSCC, BWSSB, BESCOM, BMTC.

BBMP was **dissolved on 2 September 2025** and replaced by five corporations under the Greater Bengaluru Authority. Do not write new code or copy that refers to BBMP as the current body.
