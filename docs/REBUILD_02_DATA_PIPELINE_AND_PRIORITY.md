# CivicLens Rebuild — Data Pipeline and Prioritisation

**Written:** 15 September 2026
**Companion to:** `REBUILD_00_HANDOFF_AND_SCOPE.md`, `REBUILD_01_PROBLEM_REGISTER.md`
**Status:** Authoritative for the pipeline shape, but **partly superseded on specifics.** It supersedes the priority design in `archive/STAGE_4_IMPLEMENTATION_DESIGN.md` and `archive/STAGE_6_FINAL_DESIGN_REVIEW.md`, and the deferrals in `IMPLEMENTATION_DECISIONS.md`.

> ⚠️ **Read `REBUILD_04` and `REBUILD_05` before implementing anything from this document.**
> - **§3.3 (geohash bucketing + union-find) is replaced** by PostGIS `ST_DWithin` + per-category road-snapped geometry — `REBUILD_05 §2`.
> - **§3.5 tuning constants are replaced** by the per-category table in `REBUILD_05 §2.4`.
> - **§4 (the five-component score) is replaced** by the six-component model in `REBUILD_04 §5`.
> - **§4.1 `CS` is amended** — saturates at 8 weighted reporters, velocity-limited: `REBUILD_05 §4`.
> - **§6 is corrected: photo EXIF GPS is NOT the location source.** Device geolocation plus a confirmed map pin is: `REBUILD_05 §1` and `§3`.
> - **§8 is extended** by `REBUILD_05 §9`; **§9 build order is superseded** by `REBUILD_05 §10`.

---

## 1. The one-paragraph version

Citizens send in messy, duplicated, single-sentence complaints. CivicLens (a) reads each one and pulls out four facts — *what kind of problem, where, when, how bad it sounds*; (b) groups reports that are about **the same physical thing in the same place** so ten complaints about one road become one problem with ten pieces of evidence; (c) scores each **group** — never an individual report — on five measurable factors, producing a number and a band any human can re-derive by hand; (d) shows officers a ranked worklist where every rank opens into the arithmetic behind it; and (e) sends anything dangerous straight to a human, bypassing ranking entirely. Humans make every decision. The system only orders the queue and shows its work.

---

## 2. The pipeline, stage by stage

```
   CITIZEN                    MACHINE                          HUMAN
   ───────                    ───────                          ─────

 1 Submit report
   photo + category  ──►  2 Accept & receipt
   + location             (public_id issued,
   + optional note         nothing analysed yet)
                                 │
                                 ▼
                          3 Extract facts
                          (EXIF GPS, category,
                           safety keywords,
                           free text → structured)
                                 │
                        ┌────────┴────────┐
                        ▼                 ▼
              4a SAFETY LANE       4b Assign to group
              (hazard detected)    (cluster by place,
                        │           category, time)
                        │                 │
                        │                 ▼
                        │          5 Score the group
                        │          (5 components → 0-100
                        │           → band)
                        │                 │
                        │                 ▼
                        │          6 Capital-referral gate
                        │          (Tier 2 — usually
                        │           abstains, that's fine)
                        │                 │
                        └────────┬────────┘
                                 ▼
                          7 Officer worklist  ──────►  8 Officer decides
                          (ranked, explainable)        (append-only,
                                 │                      reason required)
                                 ▼                            │
                          9 Public /nearby  ◄─────────────────┘
                          + citizen receipt updated
```

### Stage 1 — Submit
Four taps, not a form. Category icon → photo → confirm the pin on a map → optional one-line note. See `REBUILD_03` §4.

**What we capture:** `category`, `latitude`, `longitude`, `location_quality`, `photo_ids`, `note_text`, `language`, `submitted_at`, `reporter_token` (an anonymous stable per-device hash — needed for distinct-reporter counting, see §4.1).

### Stage 2 — Accept and receipt
Write the report row, write a job row in the **same transaction**, commit, then enqueue. Return the `public_id` immediately. The citizen never waits for analysis. (Fixes P-07.)

### Stage 3 — Extract facts
Runs in the worker.

| Fact | Source (in order of preference) |
|---|---|
| Location | EXIF GPS from the photo → map pin the citizen confirmed → ward centroid (marked `coarse`) |
| Category | Citizen's tap (authoritative) → AI cross-check (logged as a disagreement, never overrides) |
| Safety signal | Rule keywords + AI signal, from `config/rules/safety-v1.json` |
| Structured summary | Gemini, schema-constrained, validated by Pydantic, quarantined for injection |

**Critical implementation note:** EXIF GPS must be read **before** the image is re-encoded. `STAGE_4_IMPLEMENTATION_DESIGN.md §8` says metadata is removed on re-encode — correct for privacy, but the order matters. Read GPS → persist lat/lon to the report row → strip → store. Get this backwards and P-03 is never actually fixed.

### Stage 4a — Safety lane
If a safety signal fires (exposed live wire, sewage in drinking water, structural collapse, gas smell), the report goes to a **separate list pinned above the ranked queue** and is **never scored**. Rationale: a single credible report of a live wire outranks any statistical argument. Ranking a hazard against a pothole by score is the wrong model. This lane is already implemented and is one of the project's genuinely good ideas — keep it.

### Stage 4b — Assign to a group
See §3.

### Stage 5 — Score the group
See §4. This is the heart of the product.

### Stage 6 — Capital-referral gate (Tier 2)
The existing `priority-v1.json` rubric. It requires verified field evidence and abstains without it. That is now **correct behaviour**, not a bug, because it no longer blocks the worklist — it only answers the narrower question *"is there enough evidence to recommend spending capital money?"* Most groups will show *"Not eligible — field verification required"* with named abstention codes. That is an honest answer and a defensible design.

### Stage 7–9 — Worklist, decision, publication
Officer sees the ranked table, opens a group, sees the arithmetic, records a decision with a reason. The decision is append-only, persisted to Postgres, and surfaces on the public `/nearby` page and on the citizen's receipt.

---

## 3. Grouping (deduplication)

### 3.1 The rule in one sentence
> Two reports belong to the same problem if they are the **same category**, within **150 metres**, and within **30 days** of each other — and grouping is transitive, so A–B and B–C makes one group of three.

### 3.2 Why the current design cannot work
`evaluate_same_incident(left, right)` compares two reports and requires coordinates for confidence `high`. The form collects free-text locality only, so it always returns `review` or abstains. And pairwise comparison over 50,000 reports is 1.25 billion calls. (P-03, P-12.)

### 3.3 The algorithm — geohash bucketing, O(N)

A **geohash** is a short string encoding a rectangle on Earth. Precision 7 ≈ 153 m × 153 m. Nearby points share a prefix, which turns "find nearby reports" into a dictionary lookup.

```
for each unprocessed report r:
    cell   = geohash(r.lat, r.lon, precision=7)
    bucket = (r.category, cell)

    # A point near a cell edge has close neighbours in the adjacent cell,
    # so always check the 3x3 block, not just the home cell.
    candidates = reports in (r.category, c) for c in [cell] + neighbours8(cell)
                 where |c.submitted_at - r.submitted_at| <= 30 days

    for c in candidates:
        if haversine_km(r, c) <= 0.15:
            union(r, c)          # union-find

groups = connected components of union-find
```

Cost: one dictionary lookup plus a handful of distance checks per report. Linear.

**Coarse locations** (`location_quality = 'coarse'`, i.e. ward centroid only) are grouped by `(category, ward, 30 days)` into a separate *"needs location review"* bucket. They are counted but **not scored**, and they are shown to officers as a distinct list. Never silently mix a ward-centroid report into a precise cluster — that would fake precision, which is exactly the failure this rebuild is correcting.

### 3.4 Recurrence
A group that has been quiet for **≥14 days** and then receives new reports is marked `recurring`, and `reopen_count` is incremented. Recurrence is a strong signal that a previous fix failed, and it feeds the persistence component (§4.2). This is the single most valuable thing the system can tell an officer that a spreadsheet cannot.

### 3.5 Tuning constants
All in `config/rules/grouping-v2.json`, versioned, stamped onto output as `grouping_policy_version`:
```json
{
  "policy_version": "grouping-v2",
  "geohash_precision": 7,
  "max_distance_km": 0.15,
  "window_days": 30,
  "recurrence_quiet_days": 14,
  "coarse_location_grouping": "ward"
}
```

> **Why 150 m and not the old 1.5 km?** 1.5 km in Bengaluru spans several distinct roads and neighbourhoods; it would merge unrelated potholes into one giant blob. 150 m is roughly "the same stretch of the same road." Start here, then tune against `data/held-out/v1/` (P-31).

---

## 4. The Tier-1 triage score

**Scored on groups, never on single reports.** Five components, each 0–100, combined with fixed published weights.

Design principle: **band lookup tables, not continuous maths.** A step table can be printed on one page, explained to a citizen, and audited by a councillor. A logarithm cannot. Precision we do not have is precision we should not fake.

### 4.1 CS — Community Signal (weight 0.25)
*How many different people reported this?*

| Distinct reporters | CS |
|---|---|
| 1 | 10 |
| 2–3 | 25 |
| 4–7 | 45 |
| 8–15 | 65 |
| 16–30 | 80 |
| 31+ | 95 |

**Count distinct reporters, not reports.** One person submitting 20 times is one voice. Without this, the ranking is trivially gamed and the number is a lie (P-29). Use the anonymous `reporter_token`; if absent, fall back to distinct IP-day, and mark the group `signal_quality: 'weak'`.

This is intuition (a) — *ten complaints about one road should outrank one isolated complaint* — and it is the largest single weight.

### 4.2 PS — Persistence (weight 0.20)
*How long has this kept coming back?*

| Distinct days with at least one report | PS |
|---|---|
| 1 | 10 |
| 2–3 | 30 |
| 4–7 | 50 |
| 8–14 | 70 |
| 15+ | 85 |

**+15 if `recurring` (reopened after a closure), capped at 100.** A problem that was marked fixed and returned is worse than one reported continuously, because a resource was already spent on it.

Distinct *days*, not reports — otherwise a single angry afternoon looks like a month-long problem.

### 4.3 PE — Public Exposure (weight 0.25)
*How many people, and which people, does this affect?*

Take the **single highest** applicable value. Do **not** sum.

| Context | PE |
|---|---|
| Hospital or clinic within 150 m | 100 |
| School or college within 150 m | 90 |
| Major road — OSM `highway=trunk` or `primary` | 85 |
| Bus stop, metro station, or market within 150 m | 75 |
| Secondary road — `highway=secondary` or `tertiary` | 60 |
| Residential street — `highway=residential` | 35 |
| Private property or interior lane — `highway=service`/`unclassified` | 20 |

**Why MAX and not SUM:** a school next to a hospital on a main road is not three times worse than a hospital alone. Summing would let a cluster of mid-weight contexts beat a hospital, which contradicts human judgement. MAX answers *"what is the most important thing affected here?"*

This single table encodes **both** of the owner's remaining intuitions:
- (b) *a water problem at a hospital outranks one at a private residence* → 100 vs 20
- (c) *damage on an arterial road affects thousands, an alleyway does not* → 85 vs 20

Derived from OpenStreetMap, offline, no API key, no per-call cost. See §6.

### 4.4 SV — Severity Prior (weight 0.20)
*How bad is this kind of problem, inherently?*

Fixed, human-set, published, versioned. Not AI-generated, not per-report — a property of the **category**.

| Category | SV |
|---|---|
| Exposed electrical wire | 95 |
| Sewage or water contamination | 90 |
| Water supply outage | 75 |
| Waterlogging / flooding | 70 |
| Large pothole on carriageway | 65 |
| Garbage accumulation | 55 |
| Street light not working | 45 |
| Noise complaint | 25 |

Note the top two also trigger the safety lane (§4a) and therefore usually leave the score path entirely. They stay in the table so that non-hazardous instances of the same category still rank sensibly.

**Do not let the AI set this number.** A language model's sense of "severity" is unstable, unauditable, and would make the ranking impossible to defend. A published table set by a human is a policy, and policies can be argued with — which is the point.

### 4.5 NG — Neglect (weight 0.10)
*How long has this been sitting unresolved?*

| Age of oldest unresolved report | NG |
|---|---|
| 0–3 days | 0 |
| 4–7 days | 20 |
| 8–14 days | 40 |
| 15–30 days | 65 |
| 31+ days | 90 |

Prevents starvation: a quiet-but-old problem eventually surfaces above a loud-but-new one. Smallest weight on purpose — age alone is not importance.

### 4.6 The formula

```
Score = 0.25·CS + 0.20·PS + 0.25·PE + 0.20·SV + 0.10·NG
```

| Band | Score |
|---|---|
| **High** | ≥ 70 |
| **Moderate** | 45 – 69 |
| **Lower** | < 45 |

Weights and every table live in `config/rules/triage-v2.json`, and `triage_policy_version` is stamped on every stored score. Changing a weight must produce a new version — never a silent recompute. This pattern already exists in the codebase and works well; reuse it.

### 4.7 Two hard overrides that bypass scoring
1. **Safety lane** — a credible hazard is pinned above the queue, unranked. Not comparable to a pothole by arithmetic.
2. **Not comparable** — a group whose location cannot be established is labelled *"Needs location review"* and excluded from the ranking. Never guessed at. This preserves the existing (and good) abstention discipline.

### 4.8 Worked examples

**Road A** — 1 report, 1 person, residential lane, 2 days old, large pothole
```
CS  1 reporter        → 10  × 0.25 =  2.50
PS  2 distinct days   → 30  × 0.20 =  6.00
PE  residential       → 35  × 0.25 =  8.75
SV  pothole           → 65  × 0.20 = 13.00
NG  2 days            →  0  × 0.10 =  0.00
                                     ──────
                              Score = 30.25   Lower
```

**Road B** — 12 reports from 9 people, primary road, 11 distinct days, large pothole
```
CS  9 reporters       → 65  × 0.25 = 16.25
PS  11 days           → 70  × 0.20 = 14.00
PE  primary road      → 85  × 0.25 = 21.25
SV  pothole           → 65  × 0.20 = 13.00
NG  ~12 days          → 40  × 0.10 =  4.00
                                     ──────
                              Score = 68.50   Moderate, ranked well above Road A
```
→ **Intuition (a) confirmed.** Same category, same city, 30 vs 69. Volume and persistence do the work.

**Hospital road damage** — 3 reports from 3 people, hospital within 150 m, 5 distinct days
```
CS  3 reporters       → 25  × 0.25 =  6.25
PS  5 days            → 50  × 0.20 = 10.00
PE  hospital ≤150 m   → 100 × 0.25 = 25.00
SV  pothole           → 65  × 0.20 = 13.00
NG  6 days            → 20  × 0.10 =  2.00
                                     ──────
                              Score = 56.25   Moderate — beats Road A's 30.25 with 1/4 the reports
```
→ **Intuitions (b) and (c) confirmed.** Three people at a hospital outrank one person on a lane, because of *where*, not *how many*.

**Hospital water contamination** — 2 reporters, 3 days
```
Safety signal: sewage/water contamination → SAFETY LANE.
Not scored. Pinned above the entire queue for immediate human review.
(Its score, had it been computed, would be 55.25 — which is exactly why
 scoring it would have been wrong.)
```

These four cases must exist as unit tests with these exact expected numbers. They are the specification.

---

## 5. What the officer sees (the "stats" question, answered)

**Not** a mysterious `87/100`. Every number is walkable:

```
┌──────────────────────────────────────────────────────────────────┐
│  Road damage — Mahadevapura, 80 Feet Road          Score 68.5    │
│                                                    MODERATE      │
├──────────────────────────────────────────────────────────────────┤
│  Why this rank                                                   │
│                                                                  │
│  9 different people          ████████░░  65 × 0.25 = 16.25       │
│  reported over 11 days       ███████░░░  70 × 0.20 = 14.00       │
│  on a major road             ████████▌░  85 × 0.25 = 21.25       │
│  road damage severity        ██████▌░░░  65 × 0.20 = 13.00       │
│  oldest report 12 days ago   ████░░░░░░  40 × 0.10 =  4.00       │
│                                          ─────────────────       │
│                                          Total       68.50       │
│                                                                  │
│  policy: triage-v2 · grouping: grouping-v2                       │
│                                                                  │
│  Evidence   12 reports · 8 photos · map of all 12 pins           │
│  Capital referral   Not eligible — field verification required   │
│                     (MISSING_SERVICE_DISADVANTAGE_EVIDENCE)      │
│                                                                  │
│  [ Refer for repair ]  [ Request verification ]  [ Not a problem ]│
│  A reason is required and is published.                          │
└──────────────────────────────────────────────────────────────────┘
```

Three properties this must always have:
1. **Every component states its input in words** ("9 different people"), not just a rating.
2. **The arithmetic is shown.** An officer can check it with a calculator. This is what makes the system defensible in a meeting.
3. **The abstention is visible, not hidden.** "Not eligible for capital referral" with a named code is more trustworthy than a confident guess.

And on the citizen's receipt, in their own language:
> *Your report joined **11 other reports** about this road. It is currently ranked **12th of 340** open problems in Mahadevapura. Last update: officer requested field verification on 14 September.*

That single sentence is the closure loop the current build is missing entirely, and it is the difference between a complaint box and a civic platform.

---

## 6. Data sources

| Data | Source | Cost | Notes |
|---|---|---|---|
| Reports | Citizens | — | EXIF GPS → map pin → ward centroid |
| Road class (PE) | OpenStreetMap Bengaluru extract, Geofabrik `.osm.pbf` | Free, no key | Filter `highway=*`, load into PostGIS or a local spatial index. Nearest road within 30 m → its class. |
| Sensitive POIs (PE) | Same extract — `amenity=hospital\|clinic\|school\|college`, `highway=bus_stop`, `railway=station`, `amenity=marketplace` | Free, no key | Precompute a spatial index once at build time; lookups are then local and instant. |
| Ward / locality boundaries | ~~BBMP ward GeoJSON~~ → **OpenStreetMap `place` polygons** via `osmium`, loaded into PostGIS | Free | Superseded: BBMP was dissolved 2 Sep 2025, so its ward file no longer describes the current body. OSM is ODbL — attribution `© OpenStreetMap contributors` is required and must be visible. See `REBUILD_05 §10` step 1. |
| Map tiles | OpenStreetMap raster or MapLibre + a free vector tile provider | Free tier | This is why `IMPLEMENTATION_DECISIONS.md` decision 2 ("no map, to avoid Google Maps cost") is obsolete — a map costs nothing here. |
| Weights, SV and PE tables | Set by the developer | — | Published in-app, versioned in `config/rules/triage-v2.json` |

Everything above is free and offline after a one-time download. There is no recurring cost and no API key in the ranking path — worth stating explicitly, because cost avoidance is what drove the original bad decisions.

---

## 7. `config/rules/triage-v2.json` shape

```json
{
  "policy_version": "triage-v2",
  "effective_from": "2026-09-15",
  "weights": {
    "community_signal": 0.25,
    "persistence": 0.20,
    "public_exposure": 0.25,
    "severity_prior": 0.20,
    "neglect": 0.10
  },
  "community_signal_bands": [
    { "max_distinct_reporters": 1,  "value": 10 },
    { "max_distinct_reporters": 3,  "value": 25 },
    { "max_distinct_reporters": 7,  "value": 45 },
    { "max_distinct_reporters": 15, "value": 65 },
    { "max_distinct_reporters": 30, "value": 80 },
    { "max_distinct_reporters": null, "value": 95 }
  ],
  "persistence_bands": [
    { "max_distinct_days": 1,  "value": 10 },
    { "max_distinct_days": 3,  "value": 30 },
    { "max_distinct_days": 7,  "value": 50 },
    { "max_distinct_days": 14, "value": 70 },
    { "max_distinct_days": null, "value": 85 }
  ],
  "recurrence_bonus": 15,
  "public_exposure_contexts": [
    { "code": "hospital_within_150m",   "value": 100 },
    { "code": "school_within_150m",     "value": 90 },
    { "code": "major_road",             "value": 85 },
    { "code": "transit_or_market_150m", "value": 75 },
    { "code": "secondary_road",         "value": 60 },
    { "code": "residential_street",     "value": 35 },
    { "code": "private_or_interior",    "value": 20 }
  ],
  "public_exposure_combination": "max",
  "severity_priors": {
    "electrical_hazard": 95,
    "water_contamination": 90,
    "water_supply_outage": 75,
    "waterlogging": 70,
    "road_damage": 65,
    "garbage": 55,
    "street_light": 45,
    "noise": 25
  },
  "neglect_bands": [
    { "max_age_days": 3,  "value": 0 },
    { "max_age_days": 7,  "value": 20 },
    { "max_age_days": 14, "value": 40 },
    { "max_age_days": 30, "value": 65 },
    { "max_age_days": null, "value": 90 }
  ],
  "bands": { "high": 70, "moderate": 45 },
  "overrides": {
    "safety_lane_bypasses_scoring": true,
    "unusable_location_not_comparable": true
  }
}
```

---

## 8. New database tables

```
problem_group
  id, category, centroid_lat, centroid_lon, geohash7, ward_id,
  location_quality, first_reported_at, last_reported_at,
  distinct_reporter_count, distinct_day_count, report_count,
  is_recurring, reopen_count, status, created_at, updated_at, version

group_report            (group_id, report_id)  -- many-to-many, append-only

group_score
  id, group_id, computed_at, triage_policy_version,
  community_signal, persistence, public_exposure, severity_prior, neglect,
  score, band, component_inputs (jsonb — the words shown in the UI)
  -- append-only: keep every historical score, never UPDATE

report_photo
  id, report_id, storage_key, mime_type, byte_size,
  exif_latitude, exif_longitude, exif_captured_at, created_at

road_segment / poi      -- OSM-derived, spatially indexed, rebuilt from the extract
```

`group_score` being append-only means you can show *"this was Moderate last week and is High today"* — a genuinely valuable signal, and nearly free once the table never updates in place.

---

## 9. Build order

| Step | Deliverable | Done when |
|---|---|---|
| 1 | Photo upload + EXIF GPS extraction | A geotagged phone photo puts real lat/lon on the report row; stored image has no EXIF |
| 2 | Map pin confirmation in the form | Every new report has usable coordinates or is explicitly `coarse` |
| 3 | `problem_group` + clustering pass | Two nearby same-category reports become one group; the second receipt says so |
| 4 | Durable job queue + worker | A report submitted in Postgres mode reaches `processed` without a developer intervening |
| 5 | OSM import → `road_segment`, `poi` | Any lat/lon returns a road class and nearby POIs offline |
| 6 | `triage-v2.json` + scorer + the four worked-example tests | The four §4.8 numbers reproduce exactly |
| 7 | Rewire officer reads to computed data | Deleting `ground_truth.json` does not change the dashboard |
| 8 | 20k–50k report generator | Tens of thousands of reports collapse into hundreds of ranked groups |
| 9 | Score breakdown UI | An officer can hand-verify a rank with a calculator |
| 10 | Held-out evaluation script | One defensible precision/recall number for grouping |

Steps 1–3 are the whole project in miniature. Nothing else matters until a submitted report visibly joins a group.

---

## 10. Corrections to existing documents

| Document | What is wrong | Correct position |
|---|---|---|
| `IMPLEMENTATION_DECISIONS.md` #1 | "Image upload is deferred" | Images are **P0**. They are the location source. |
| `IMPLEMENTATION_DECISIONS.md` #2 | "No Google Map dependency" | Correct about Google, wrong conclusion. Use OSM/MapLibre — free. Coordinates are mandatory. |
| `IMPLEMENTATION_DECISIONS.md` #3 | "60 curated reports" | 20k–50k. Dedup and ranking are unprovable at 60. |
| `IMPLEMENTATION_DECISIONS.md` #4 | 30/25/25/20 as *the* priority policy | Demoted to Tier 2 (capital referral only). Tier 1 is `triage-v2`. |
| `STAGE_4 §8` | "Metadata removed" on image re-encode | Right, but read EXIF GPS **first**, persist it, then strip. |
| `STAGE_6 §4` | Priority = the four-component rubric | That rubric abstains on real data. It is now the referral gate, not the worklist order. |
| `STAGE_6 §13` | "Never show a headline score" | Overridden. Show the score **with its full arithmetic**. An unexplained number is untrustworthy; an explained one is the product. |
| `STAGE_6 §12` | Voice as P0 | Demoted. Photos are P0. Voice is a small affordance. |
| `config/rules/grouping-v1.json` | 1.5 km radius | 150 m. 1.5 km merges unrelated roads across a Bengaluru neighbourhood. |
