# CivicLens Rebuild — Priority Model, Routing, and Legitimacy

**Written:** 15 September 2026
**Companion to:** `REBUILD_00_HANDOFF_AND_SCOPE.md`, `REBUILD_01_PROBLEM_REGISTER.md`, `REBUILD_02_DATA_PIPELINE_AND_PRIORITY.md`, `REBUILD_03_UI_DESIGN_BLUEPRINT.md`
**Status:** Authoritative. Where this document and `REBUILD_02`/`REBUILD_03` disagree, **this document wins.** Those two carry pointer banners rather than edits, so the reasoning history stays visible; §11 lists exactly what is overridden.

> ⚠️ **Amended by `REBUILD_05_LOCATION_ABUSE_AND_CLOSURE.md`** (15 September 2026), which resolves location intake and hardens four things this document specified too loosely:
> - **§8.1 dedup geometry** — radial distance is replaced by per-category geometry with OSM road-segment snapping. A 150 m circle wrongly merges complaints across parallel streets in JP Nagar-style layouts: `REBUILD_05 §2`.
> - **§5.5 `CS`** — saturates at 8 weighted reporters and is velocity-limited, because as originally written it was Sybil-attackable: `REBUILD_05 §4`.
> - **§8.3 closure loop** — `Resolved` is no longer terminal; a 48-hour citizen verification window sits after it, and the SLA clock resumes rather than restarts on reopen: `REBUILD_05 §5`.
> - **§10.1 data plan** — PostGIS is now mandatory; the `osmium` pipeline also produces the `.pmtiles` basemap and a way-node table: `REBUILD_05 §1.3`, `§2.3`.
> - **§12 schema** is extended by `REBUILD_05 §9`; **§13 build order is superseded** by `REBUILD_05 §10`.

**Decided with the project owner on 15 September 2026.** Scope, agency set, SLA source and documentation plan were all confirmed by them before this was written.

---

## 0. Rules for any AI agent picking this up

1. **Read §1 before touching the priority code.** If you cannot explain why weighting a hospital is not favouritism, you will build the wrong thing and it will be indefensible under questioning.
2. **AI never assigns a score.** AI reads language. Rules do arithmetic. Humans decide. If you find yourself prompting a model for a priority number, stop.
3. **Three lanes, not one queue.** Safety, statutory, discretionary. Do not merge them.
4. **Scope is Bengaluru South City Corporation.** Do not silently expand it.
5. **Do not write new stage documents.** Update this one in place.
6. Everything in §3–§6 is a **published table**, not a heuristic buried in code. If a number is not in `config/rules/`, it is a bug.

---

## 1. Legitimacy — why this is policy, not favouritism

The owner asked, correctly, whether weighting a hospital higher than a private house is **ಪಕ್ಷಪಾತ** (partiality). This section is the answer, and it is the intellectual foundation of the project. It belongs in the pitch.

### 1.1 There is no neutral ordering

Every possible ordering encodes a value judgment:

| Ordering | The judgment it makes |
|---|---|
| Report count | The neighbourhood that complains loudest wins |
| Date received (FIFO) | A blocked drain at a hospital waits behind last week's noise complaint |
| Random | Nothing matters more than anything |
| No ordering (flat list) | The officer's gut decides, invisibly, unrecorded |

The choice is not *judgment vs. neutrality*. It is *stated judgment vs. hidden judgment*.

### 1.2 Ranking by report volume alone is the more biased design

Established finding in urban informatics — complaint volume tracks **income, education, language fluency, smartphone access and civic confidence**, not the actual severity of infrastructure failure. Better-off neighbourhoods file more complaints *per real problem*.

> Key literature: Kontokosta & Hong, *Bias in smart city governance: how socio-spatial disparities in 311 complaint behavior impact the fairness of data-driven decisions* (Sustainable Cities and Society, 2021); Minkoff, *NYC 311: A Tract-Level Analysis of Citizen-Government Contacting* (Urban Affairs Review, 2016).
> **Provenance note:** these are cited from prior knowledge. The publisher page returned HTTP 403 during this session and was not read. **Verify before quoting specific figures in any submission.**

This is not abstract for Bengaluru. From BWSSB's own published figures: the city averages **100–125 litres per person per day, but poorer areas receive only 40–45 litres**. Those are precisely the areas least likely to generate twenty complaints about it.

**Therefore: weighting exposure and vulnerability is a correction to a documented bias, not the introduction of one.** A volume-only ranking is the version that should worry us.

### 1.3 The four legitimacy tests

A weighting is favouritism if it fails any of these, and policy if it passes all four:

| Test | How CivicLens satisfies it |
|---|---|
| **Stated** | Published at `/how-ranking-works`; versioned in `config/rules/triage-v3.json` |
| **Consistent** | The same table applies to every ward, every category, no exceptions, no manual overrides of the number |
| **Reviewable** | A human can override the *rank*; the override and its reason are recorded append-only |
| **Contestable** | Any citizen or councillor can read the rule and argue with it |

### 1.4 Language discipline

The component is **not** "importance." It is **consequence of failure**.

| | Water fails at one house | Water fails at a hospital |
|---|---|---|
| People affected | ~4 | ~400, including inpatients |
| Alternatives available | Neighbour, tanker, can leave | Dialysis stops. Surgery stops. Patients cannot leave. |

This is an estimate of **how many people are harmed, how badly, and whether they can avoid it**. It is not a ranking of human worth. Never use the words "important," "priority people," or "VIP" in code, UI copy, or documentation.

### 1.5 Precedent

Criticality weighting is standard, legal, and uncontroversial:

- Ambulances have statutory right of way
- **BESCOM, like every utility, restores hospital feeders before residential feeders**
- Fire codes mandate more egress capacity in schools than warehouses
- Medical triage treats the critical patient before the one who arrived first

None of this is called partiality. Refusing to consider criticality is not neutrality — it is negligence.

### 1.6 The pitch sentence

> **CivicLens does not add judgment to civic triage. It replaces invisible judgment with three visible lanes — life safety, statutory deadline, and a published score — and a human decides in every one.**

---

## 2. Scope (decided)

| | |
|---|---|
| **Corporation** | **Bengaluru South City Corporation (BSCC)** — 72 wards, 147 km², HQ Jayanagara |
| **Why** | The owner lived in JP Nagar / Banashankari. Local knowledge is a verification asset: they can tell instantly whether generated data is plausible. Nobody can validate synthetic data for 368 wards they have never walked. |
| **Demo deep-dive wards** | JP Nagar, Banashankari, Jayanagar — real places the owner can discuss under questioning |
| **Agencies** | 4 — BSCC, BWSSB, BESCOM, BMTC |
| **Categories** | 11 + `OTHER` (§4) |
| **Target corpus** | ~50,000 synthetic reports over 12 months |
| **Schema** | `corporation_id` column present from day one |

### 2.1 Why one corporation and not five — the honest engineering answer

**Almost nothing technical changes.** The schema takes one extra column. Geohash bucketing is O(N), so 5× the reports is 5× the buckets, not 25× the work. Scoring, API and frontend are identical. The OSM download covers the whole Bengaluru bounding box regardless.

What actually changes is **human**:

| | 1 corporation | 5 corporations |
|---|---|---|
| Ward polygons to source | 72 | 368 |
| Can the owner eyeball whether the demo is *right*? | Yes | No |

Adding the other four corporations later is a **data load, not a rewrite**. Build the code corporation-agnostic; scope the data.

### 2.2 Geography data — risk and fallback

⚠️ The 368-ward boundaries for the five new corporations were notified in **July 2025**. Public GeoJSON may not exist yet. **Verify before depending on it.**

**Fallback, which is arguably better:** use OSM locality boundaries (`place=suburb`) — JP Nagar, Banashankari, Jayanagar are all present. **Citizens say "JP Nagar," not "Ward 178."** More available *and* more usable. Wards become a secondary layer when boundaries can be sourced.

---

## 3. The three-lane priority model

This replaces the single ranked queue in `REBUILD_02`.

```
                    incoming problem group
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
      ┌───────────────┐ ┌───────────┐ ┌────────────────┐
      │ LANE 1        │ │ LANE 2    │ │ LANE 3         │
      │ SAFETY        │ │ STATUTORY │ │ DISCRETIONARY  │
      ├───────────────┤ ├───────────┤ ├────────────────┤
      │ hazard signal │ │ at/past   │ │ everything     │
      │ fires         │ │ SLA       │ │ inside its SLA │
      │               │ │ deadline  │ │                │
      │ chronological │ │ sorted by │ │ sorted by      │
      │ NEVER scored  │ │ days      │ │ triage score   │
      │               │ │ overdue   │ │                │
      │ JUDGMENT:     │ │ JUDGMENT: │ │ JUDGMENT:      │
      │ none          │ │ none —    │ │ stated,        │
      │ (life safety) │ │ it's law  │ │ published,     │
      │               │ │           │ │ reviewable     │
      └───────────────┘ └───────────┘ └────────────────┘
              │               │               │
              └───────────────┼───────────────┘
                              ▼
                    officer decides — always
```

**Two of the three lanes contain no discretionary judgment at all.** The score orders only what remains inside its statutory window — exactly where an officer would otherwise use unrecorded gut feel.

**UI rule:** the three lanes are visually distinct and never interleaved. Lane 1 is a red strip pinned at the top. Lane 2 is an amber section below it. Lane 3 is the main ranked table.

---

## 4. Categories, agencies, and statutory deadlines

### 4.1 Why a closed category list is mandatory

The owner asked whether a fixed topic list is wrong, since problems are unbounded. It is not wrong — it is required, and it is universal practice.

Open311 GeoReport v2 (Chicago, Toronto, San Francisco, Boston, Helsinki, Bonn, Washington DC) defines exactly this: `service_code`, `service_name`, `group`, `keywords`, `agency_responsible`. NYC runs ~200 complaint types under ~20 groups. Every city on earth uses a closed list.

Structurally, **an open list breaks ranking**: the severity prior is per-category. Unknown category → no severity value → nothing to rank. The closed list is load-bearing, not a limitation.

The infinite tail is handled honestly by `OTHER` → an unranked *"needs classification"* list that is visible and counted.

### 4.2 The table

Adopt Open311-shaped codes. **SLA days are set by the project owner, modelled on the structure of the Karnataka Sakala Services Act. They are NOT the Act's notified limits.** This must be stated in the UI wherever an SLA appears.

| `service_code` | Citizen label | Agency | Group | SLA (days) | Severity prior |
|---|---|---|---|---|---|
| `ELECTRICAL_HAZARD` | Exposed wire / shock risk | BESCOM | Electricity | **1** | 95 |
| `WATER_CONTAMINATION` | Dirty or smelly water | BWSSB | Water | **1** | 90 |
| `SEWAGE_OVERFLOW` | Sewage overflowing | BWSSB | Water | **2** | 90 |
| `TREE_HAZARD` | Dangerous / fallen tree | BSCC | Roads | **2** | 80 |
| `WATER_SUPPLY` | No water supply | BWSSB | Water | **3** | 75 |
| `WATERLOGGING` | Flooding / stagnant water | BSCC | Drains | **3** | 70 |
| `GARBAGE` | Garbage not cleared | BSCC | Sanitation | **3** | 55 |
| `STREET_LIGHT` | Street light not working | BSCC | Lighting | **7** | 45 |
| `STRAY_ANIMALS` | Stray animal problem | BSCC | Animal control | **7** | 50 |
| `BUS_STOP` | Bus stop damaged / missing | BMTC | Transport | **10** | 40 |
| `ROAD_DAMAGE` | Pothole / broken road | BSCC | Roads | **15** | 65 |
| `OTHER` | Something else | *unassigned* | — | **7** (to classify) | — |

Two notes:
- `ELECTRICAL_HAZARD`, `WATER_CONTAMINATION` and `SEWAGE_OVERFLOW` also trigger Lane 1 and normally leave the scoring path entirely. Their severity priors remain so that non-hazardous instances still rank sensibly.
- SLA runs from `first_reported_at` of the **group**, not of the individual report.

### 4.3 The Sakala grounding (why Lane 2 is legitimate)

Verified from the Karnataka Sakala Services Act, 2011:

| | |
|---|---|
| **478 services** across **47 departments**, each with a notified statutory time limit | |
| Every request issues a **15-digit GSC number** for tracking | |
| Missed deadline → appeal to a competent officer, who must resolve within a set time | |
| **₹20/day compensation, maximum ₹500, recovered from the responsible official's salary** | |
| ~46 million applications filed by April 2014 | |
| Monitored by an NIC-built online system; District Magistrate is Chief Nodal Officer in all 30 districts | |

And nationally: **22 states and UTs** have Right to Public Services legislation, with First and Second Appellate Authorities and penalties of ₹500–₹5,000 for deficiency of service, plus quasi-judicial powers under the CPC 1908.

**Honesty requirement:** Sakala's 478 services are largely certificates and licences, not pothole repair. So CivicLens is *modelled on* the Sakala mechanism, not implementing it. Say so plainly in the UI and in any submission. Claiming statutory backing you do not have would destroy the credibility this whole document is built on.

---

## 5. The revised triage score (Lane 3)

### 5.1 What changed and why

`REBUILD_02` used a single `PE — Public Exposure` component with a MAX over one table. **The owner identified a real flaw:** that table conflates two different facts.

| | Metro station | Hospital |
|---|---|---|
| People passing through | Very high | Moderate |
| Can they avoid or cope? | Yes — healthy, mobile | No — sick, captive, dependent |

One axis cannot represent both. **Split into two components.**

### 5.2 EX — Exposure (how many people encounter this)

Take the **maximum** applicable.

| Context | Source | EX |
|---|---|---|
| Arterial road | OSM `highway=trunk` or `primary` | 90 |
| Transit stop within 150 m | `highway=bus_stop`, `railway=station`, `amenity=bus_station` | 80 |
| Market within 150 m | `amenity=marketplace` | 75 |
| Secondary road | `highway=secondary` or `tertiary` | 60 |
| Residential street | `highway=residential` | 35 |
| Interior / service lane | `highway=service` or `unclassified` | 15 |

### 5.3 VU — Vulnerability (can the affected people avoid or cope)

Take the **maximum** applicable.

| Context | Source | VU |
|---|---|---|
| Hospital or clinic within 150 m | `amenity=hospital`, `amenity=clinic` (+ `emergency=*` notes an ER) | 100 |
| Care facility within 150 m | `amenity=social_facility` + `social_facility=nursing_home`, disability facilities | 90 |
| School or college within 150 m | `amenity=school`, `college`, `university` | 85 |
| None of the above | — | **35 baseline** |

The 35 baseline matters: ordinary residents are also people. A baseline of 20 punished every problem without a sensitive POI too harshly.

> **Known equity gap:** dense low-income settlements should raise VU (fewer alternatives, less ability to complain — see §1.2). OSM does not tag this reliably. Recorded as future work; do **not** proxy it with anything unverified.

### 5.4 Category × context relevance — the fix the owner asked for

The owner's objection: *"if there's a bus stand nearby people travel more, so priority. But what if it's some other case? Then the hospital thing won't work."*

Correct. **Context relevance depends on the category.** A hospital matters enormously for water supply and barely at all for a street light. So each context value is multiplied by a relevance factor ∈ {0, 0.5, 1.0} before the MAX.

| Category | EX relevance | VU relevance | Reasoning |
|---|---|---|---|
| `ROAD_DAMAGE` | 1.0 | 1.0 | Traffic volume is the point; ambulance access, children crossing |
| `WATERLOGGING` | 1.0 | 1.0 | Blocks the road *and* traps vulnerable people |
| `SEWAGE_OVERFLOW` | 1.0 | 1.0 | Infection risk plus obstruction |
| `ELECTRICAL_HAZARD` | 1.0 | 1.0 | Footfall = exposure; children and patients cannot judge risk |
| `GARBAGE` | 1.0 | hospital 1.0, school 0.5 | Infection near patients; nuisance near schools |
| `STREET_LIGHT` | 1.0 | **0.5** | Footfall at night matters; a hospital has its own lighting |
| `TREE_HAZARD` | 1.0 | school 1.0, hospital 0.5 | Children in open ground |
| `BUS_STOP` | 1.0 | school 1.0, care 1.0, hospital 0.5 | Students and elderly depend on the bus |
| `WATER_SUPPLY` | **0.5** | 1.0 | Road class barely matters; dialysis and sterilisation matter enormously |
| `WATER_CONTAMINATION` | **0.5** | 1.0 | Same |
| `STRAY_ANIMALS` | **0.5** | school 1.0, care 1.0, hospital 0.5 | Risk to children and the elderly |

~80 cells, each justifiable in one sentence. That is what makes *"why did water at a hospital score high but a street light at a hospital score low?"* answerable instead of a shrug.

### 5.5 The other four components (unchanged from `REBUILD_02`)

**CS — Community Signal.** Count **distinct reporters**, never reports. One person submitting 20 times is one voice; without this the ranking is gamed in ten minutes.

| Distinct reporters | CS |
|---|---|
| 1 | 10 |
| 2–3 | 25 |
| 4–7 | 45 |
| 8–15 | 65 |
| 16–30 | 80 |
| 31+ | 95 |

**PS — Persistence.** Distinct days with at least one report. **+15 if `recurring`** (reopened after closure), capped at 100.

| Distinct days | PS |
|---|---|
| 1 | 10 |
| 2–3 | 30 |
| 4–7 | 50 |
| 8–14 | 70 |
| 15+ | 85 |

**SV — Severity prior.** Per category, from the §4.2 table. **Human-set, never AI-generated** — a language model's sense of severity is unstable and unauditable, which would make the ranking indefensible.

**NG — Neglect.** Age of the oldest unresolved report.

| Age | NG |
|---|---|
| 0–3 d | 0 |
| 4–7 d | 20 |
| 8–14 d | 40 |
| 15–30 d | 65 |
| 31+ d | 90 |

### 5.6 The formula

```
Score = 0.24·CS + 0.18·PS + 0.16·EX + 0.18·VU + 0.16·SV + 0.08·NG
```

| Band | Score |
|---|---|
| **High** | ≥ 70 |
| **Moderate** | 45 – 69 |
| **Lower** | < 45 |

`CS` carries the largest weight, so report volume remains the strongest single signal — which respects the owner's first intuition. `VU` is weighted above `EX` because vulnerability is the harder-to-see factor and the deliberate bias correction from §1.2.

Weights and every table live in `config/rules/triage-v3.json`, stamped onto output as `triage_policy_version`. Changing a weight creates a new version; never silently recompute.

### 5.7 Worked examples — these become the unit tests

**Road A** — 1 reporter, residential lane, 2 distinct days, 2 days old
```
CS   1 reporter        →  10 × 0.24 =  2.40
PS   2 days            →  30 × 0.18 =  5.40
EX   residential       →  35 × 0.16 =  5.60
VU   nothing nearby    →  35 × 0.18 =  6.30
SV   road damage       →  65 × 0.16 = 10.40
NG   2 days            →   0 × 0.08 =  0.00
                                      ─────
                              Score =  30.10   Lower
```

**Road B** — 12 reports from 9 people, arterial road, 11 distinct days, 12 days old
```
CS   9 reporters       →  65 × 0.24 = 15.60
PS   11 days           →  70 × 0.18 = 12.60
EX   arterial road     →  90 × 0.16 = 14.40
VU   nothing nearby    →  35 × 0.18 =  6.30
SV   road damage       →  65 × 0.16 = 10.40
NG   12 days           →  40 × 0.08 =  3.20
                                      ─────
                              Score =  62.50   Moderate
```
→ **Intuition (a): volume and persistence.** 30.1 vs 62.5, same category.

**Metro-station pothole** — 5 people, 6 distinct days, transit stop within 150 m, 7 days old
```
CS   5 reporters       →  45 × 0.24 = 10.80
PS   6 days            →  50 × 0.18 =  9.00
EX   transit stop      →  80 × 0.16 = 12.80
VU   nothing nearby    →  35 × 0.18 =  6.30
SV   road damage       →  65 × 0.16 = 10.40
NG   7 days            →  20 × 0.08 =  1.60
                                      ─────
                              Score =  50.90   Moderate  (high EX, low VU)
```

**Hospital-access pothole** — 3 people, 5 distinct days, hospital within 150 m, secondary road, 6 days old
```
CS   3 reporters       →  25 × 0.24 =  6.00
PS   5 days            →  50 × 0.18 =  9.00
EX   secondary road    →  60 × 0.16 =  9.60
VU   hospital ≤150 m   → 100 × 0.18 = 18.00
SV   road damage       →  65 × 0.16 = 10.40
NG   6 days            →  20 × 0.08 =  1.60
                                      ─────
                              Score =  54.60   Moderate  (moderate EX, max VU)
```
→ **This pair is the whole point of the EX/VU split.** 50.90 vs 54.60 — both rank in the same region, for *different and separately visible reasons*. The metro is busy; the hospital is fragile. One blended number could not have said that.
→ **Intuitions (b) and (c):** 3 people at a hospital (54.60) beat 1 person on a lane (30.10), on location alone.

**Sewage near a school** — 22 people, 20 distinct days, school within 150 m, secondary road, 25 days old
```
CS   22 reporters      →  80 × 0.24 = 19.20
PS   20 days           →  85 × 0.18 = 15.30
EX   secondary road    →  60 × 0.16 =  9.60
VU   school ≤150 m     →  85 × 0.18 = 15.30
SV   sewage            →  90 × 0.16 = 14.40
NG   25 days           →  65 × 0.08 =  5.20
                                      ─────
                              Score =  79.00   High
```

**Hospital water contamination** — 2 reporters, 3 days
```
Lane 1 — SAFETY. Not scored. Pinned above the entire queue.
Had it been scored it would have reached ~57 — which is exactly why
scoring a contamination hazard would have been the wrong model.
```

All six become unit tests with these exact expected values. **They are the specification.**

### 5.8 Ranking is comparative — rank within a comparable set

Do **not** rank globally. A water outage and a broken bus shelter share no meaningful scale, and an officer cannot act on a mixed list.

> **Rank within `(ward × department)`.** Aggregate upward for overview counts, never for ordering.

---

## 6. Department routing

### 6.1 It is not AI — it is two lookups

From the Open311 spec: every service request carries an **`agency_responsible`** field, and each `service_code` sits in a `group`. It is a table. Chicago, Toronto, Boston, San Francisco and Helsinki all work this way.

```
category   →  agency + department     (table, §4.2)
lat/lon    →  corporation → ward      (point-in-polygon)
                                      → ward officer
```

**AI's only routing job is getting from messy Kannada/Hindi/English text to the right `service_code`.** After that, lookups. This is precisely what Traffy Fondue does — *"AI to automatically classify user-submitted issues and direct them to the correct government department"* — across 17,000 organisations and 1.37 million reports.

### 6.2 The Bengaluru agency map (verified)

| Problem area | Agency | Verified detail |
|---|---|---|
| Roads, footpaths, drains, garbage, parks, street lights | **5 City Corporations** (Central 63 / North 72 / South 72 / East 50 / West 111 wards) under the **Greater Bengaluru Authority** | **BBMP was dissolved 2 September 2025.** GBA came into being 15 May 2025, fully operational 2 September 2025. Law permits up to seven corporations. |
| Water supply, sewerage | **BWSSB** (est. 1964) | 900 MLD supplied against ~1,300 MLD demand; 80% Cauvery. **100–125 L/person/day average, 40–45 L in poorer areas.** |
| Electricity | **BESCOM** (under KPTCL) | Helpline **1912**, publicly criticised during outages, supplemented with region-wise mobile numbers |
| City buses, bus stations | **BMTC** | 50 depots, 6,955+ vehicles, ~4.8 M passengers/day. **Bus shelter provision involves other civic agencies.** |
| Metro | **BMRCL** | Out of scope for the demo |
| Traffic signals, enforcement | **Bengaluru Traffic Police** | 48 stations, 3 zones. Out of scope. |
| Layouts, planning | **BDA** (1976) / **BMRDA** (1985) | Out of scope |

⚠️ **Every "BBMP" string in the repository and the Stage 1–6 documents is out of date.** Replace with the corporation name or "GBA" as appropriate.

### 6.3 ⭐ Jurisdiction dispute flag — the headline feature

Two verified facts:
1. BMTC bus shelter provision **involves other civic agencies**
2. **BMLTA**, the unified transport authority proposed in 2022, **was still not operational as of late 2024**

Inter-agency coordination in Bengaluru is a documented, named, current failure. Because CivicLens clusters by **location regardless of category**, it can see what no single-agency system can:

> **"This location has 14 reports across 2 agencies — BWSSB (pipe repair) and Bengaluru South Corporation (road surface). Neither has acted in 34 days."**

This is the classic Bengaluru death-loop: the water board digs the road, the corporation says the damage is not theirs, nobody fixes it for a year.

**Implementation:** after clustering, for each geohash-7 cell, if groups exist with ≥2 distinct `agency_responsible` values and any is open past its SLA, emit a `jurisdiction_dispute` flag. Surface it as its own section in the officer console and on `/nearby`.

**No system in the reference set (§9) does this.** Cheap to build, highly quotable, and grounded in a documented governance gap.

---

## 7. Dashboard structure — ward-first, four levels

A flat city-wide list of 340 problems matches **nobody's job.** A ward engineer owns one ward; a BWSSB officer owns water across many wards. Nobody is employed as "person responsible for all of Bengaluru." That is why the current card dashboard feels useless — it has no owner.

```
L1  CITY / CORPORATION      Bengaluru South · 72 wards · 4 agencies
                            map + counters + which ward and which
                            department is worst
                                    │
        ┌───────────────────────────┴───────────────────────────┐
        ▼                                                       ▼
L2  GEOGRAPHIC                                          L2  FUNCTIONAL
    wards ranked                                            one agency
    (JP Nagar, Banashankari, …)                             (all BWSSB items),
        │                                                   wards ranked
        └───────────────────────────┬───────────────────────────┘
                                    ▼
L3  WARD                    JP Nagar · problems ranked
                            grouped by department
                            Lane 1 pinned · Lane 2 next · Lane 3 ranked
                                    │
                                    ▼
L4  PROBLEM                 score breakdown · photos · cluster map
                            · timeline · decision panel
```

Two entry points at L2 because there are two kinds of officer — **geographic** and **functional**. Both must work. This also enforces §5.8: ranking happens at L3, inside a comparable set.

---

## 8. Deduplication and the closure loop

### 8.1 Deduplication — geometry proposes, AI adjudicates, photos are for humans

This architecture was arrived at independently by the project owner and is correct.

```
1  GEOMETRY    same category + within 150 m + within 30 days, transitive
               cheap, deterministic, runs over all 50,000 reports
               → confident groups + a set of "maybe" pairs

2  AI INTENT   only on the "maybe" pairs — read the TEXT of both:
               "same physical problem, or two different ones?"
               → hundreds of calls, not 1.25 billion

3  PHOTOS      for the officer's eyes only. No model touches them.
```

**Why not vision for dedup:** the same pothole photographed from two angles in different light looks like two problems, and two different potholes look identical. Text intent is far more reliable. Every system in §9 — FixMyStreet, SeeClickFix, Traffy Fondue — treats photos as *human* evidence.

**Why photos still matter** (the owner's reasoning, which is right): the officer sits at a desk and gets a sense of severity before deciding whether to dispatch a crew. That saves a site visit and needs no ML whatsoever.

**Cost control:** AI is invoked only where geometry is uncertain. Budget accordingly and cap per day (see `P-10`).

### 8.2 A gap in the international standard

From the Open311 GeoReport v2 spec, verbatim conclusion:

> The specification does not define any deduplication mechanism, parent/child linking, or "related request" field. There is no API method for merging reports… Clients wanting to detect likely duplicates would have to do so themselves.

What real cities do: a human notices, closes the report, and types **"Duplicate request."** into `status_notes`. That is the state of the art in Chicago.

**Automatic deduplication is therefore not a feature added to a solved problem. It is the unsolved part, and it is CivicLens's primary contribution.**

### 8.3 The closure loop

```
Received → Acknowledged → Assigned (agency) → In progress → Resolved → Verified
                                                     │
                                    ⚠ Resolved REQUIRES a photo
```

Two features that follow almost free:

| Feature | Why it matters |
|---|---|
| **Resolution photo mandatory** | Combined with recurrence detection, false closures become auditable: *"marked resolved 3 times, reports keep arriving — here are the 3 closure photos."* Nothing in §9 does this. |
| **Citizen can dispute a resolution** | The group reopens, `reopen_count` increments, and it feeds `PS` (+15). Closes the loop with the person who reported. |

Reference practice: Open311 has `status`, `status_notes`, `expected_datetime`. Traffy Fondue publishes a **77% resolution rate** with 700,000+ cases closed in Bangkok. Sakala issues the GSC number and an appeal route.

### 8.4 Recurrence is the strongest single output

A group quiet ≥14 days that receives new reports is marked `recurring`. This is the killer insight: *"this road has been marked fixed three times in six months."* It means the previous repairs failed or the root cause lies elsewhere. It is cheap to compute, impossible to see in a spreadsheet, and no system in §9 surfaces it.

---

## 9. Reference systems (verified this session)

| System | What it is | What it does about our problem |
|---|---|---|
| **Open311 / GeoReport v2** | The open standard — Chicago, Toronto, SF, Boston, DC, Baltimore, Helsinki, Bonn, Lamía, Bloomington, New Haven | `service_code` + `agency_responsible` + `group` + `keywords`. **No dedup. No ranking.** |
| **FixMyStreet Platform** | mySociety, UK. **Open source (AGPL).** Züri wie neu, Fixa min gata, AduanKu.my | Photos, map, categories, many languages, brandable. **Read the code.** |
| **SeeClickFix** | US, ~300 municipalities (2017), acquired by CivicPlus 2019 | Map, photos, video, comments, subscribe by area/keyword. Criticised for enabling reporting on marginalised residents — a real design caution. |
| **NYC 311** | Largest deployment; 50 millionth call June 2007 | Massive open dataset — free validation data |
| **Traffy Fondue** 🇹🇭 | NECTEC, Thailand, 2022 | ⭐ **Closest to our intent.** AI classifies and routes to the correct department. 1.37 M reports, 17,000 organisations, 77% resolution, ~865,000 reports in Bangkok, runs on LINE. |
| **CPGRAMS** | India, DARPG, since 2007, pgportal.gov.in | Central/state grievance routing with tracking IDs |
| **Sakala** | Karnataka, 2011 | 478 services, 47 departments, statutory time limits, ₹20/day compensation |

**Nothing in this table does automatic clustering with explainable ranking.** That is the gap CivicLens occupies.

### 9.1 What to reuse rather than build

| Reuse | How |
|---|---|
| **Open311 GeoReport v2** | Adopt the service-code shape and `agency_responsible`. Free credibility; real interoperability. |
| **FixMyStreet source** | Read it for category structure, moderation and report flow. Do not fork (Perl). |
| **Chicago / NYC 311 open data** | **Validate the clustering algorithm on real municipal data** before any Bengaluru data exists. |
| **OSM + osmium** | Hospitals, schools, road classes, localities. Free, offline, ODbL. |
| **MapLibre GL + OSM tiles** | Maps at zero cost |

---

## 10. Data plan

### 10.1 Scoring and geography data

```bash
# one-time, ~531 MB
wget https://download.geofabrik.de/asia/india/southern-zone-latest.osm.pbf

# Bengaluru South bounding box
osmium extract --bbox 77.50,12.85,77.65,12.98 southern-zone-latest.osm.pbf -o blr-south.pbf

# only what scoring needs
osmium tags-filter blr-south.pbf \
  a/amenity=hospital,clinic,doctors,school,college,university,marketplace,bus_station,social_facility \
  n/highway=bus_stop n/railway=station w/highway \
  r/place=suburb \
  -o blr-south-scoring.pbf
```

Load into Postgres (PostGIS preferred; a Python KD-tree is acceptable). Nearest-road-within-30 m gives the road class; POI-within-150 m gives EX and VU contexts.

**Use the download, not the live Overpass API.** Overpass's own guidance for a regularly-running application is **under 100 queries and 10 MB per day** — fine for a toy, useless for 50,000 reports.

**Licence:** ODbL. Print *"© OpenStreetMap contributors"* in the footer. Free for portfolio and commercial use.

### 10.2 Demo corpus — never hand-made

The same OSM extract does double duty. Generate reports **anchored to real geometry**:

- Sample real road segments and real localities from the extract
- Place clusters along them with realistic burst patterns
- Deliberately include: a high-volume-but-trivial case, a low-volume-but-critical case, one genuine recurrence-after-closure, one jurisdiction dispute (two agencies, one location)
- Distribute across 12 months and all 11 categories
- Assign distinct `reporter_token`s with a realistic power-law (a few heavy reporters, a long tail of one-time reporters)

**Real road names, real coordinates, real hospitals + synthetic complaints reads as real.** The current 60-report corpus looks fake mainly because the geography is invented.

Keep the existing 60 curated reports as a named regression scenario.

### 10.3 Validation on real data

Run the clustering algorithm over a real 311 export (Chicago or NYC — complaint type + lat/long + timestamps + status) and report grouping precision/recall.

Claim to make: *"the clustering algorithm is validated against N real municipal complaints; the Bengaluru demo uses synthetic data because no open Bengaluru complaint feed exists."* Checkable, honest, and the difference between "I built a system" and "I built a system that works."

---

## 11. What this document overrides

`REBUILD_02` and `REBUILD_03` are deliberately left unedited. Where they conflict with this document, **this document wins.**

| Source | Superseded | Replacement |
|---|---|---|
| `REBUILD_02 §4.3` | Single `PE — Public Exposure` component | Split into `EX` (§5.2) and `VU` (§5.3) |
| `REBUILD_02 §4.6` | `0.25·CS + 0.20·PS + 0.25·PE + 0.20·SV + 0.10·NG`, `triage-v2` | `0.24·CS + 0.18·PS + 0.16·EX + 0.18·VU + 0.16·SV + 0.08·NG`, **`triage-v3`** |
| `REBUILD_02 §4.8` | Worked examples (30.25 / 68.50 / 56.25) | Recomputed in §5.7 (30.10 / 62.50 / 50.90 / 54.60 / 79.00) |
| `REBUILD_02 §2` | Two-lane model (safety + score) | **Three lanes** (§3) — statutory SLA lane added |
| `REBUILD_02 §4` | No category-context interaction | Category × context relevance table (§5.4) |
| `REBUILD_02` | Global ranking | Rank within `(ward × department)` (§5.8) |
| `REBUILD_02 §6` | "BBMP ward GeoJSON" | BBMP dissolved 2 Sep 2025. Use corporation/locality geography (§2.2, §6.2) |
| `REBUILD_02` | Categories unspecified | 11 + `OTHER`, Open311-shaped, with agency and SLA (§4.2) |
| `REBUILD_03 §1` | GOV.UK-style plainness as the aesthetic target | **Over-corrected.** Keep the structural rules (contrast, 48 px targets, 17 px body, Noto Sans for Kannada/Devanagari, one container width). Drop the austere look. Better references: Singapore **OneService**, **Traffy Fondue**, Google/Apple **Maps** for map UX. Allow a real colour identity, map-forward layouts, real Bengaluru photography, a display face for headings, and subtle depth. What was banned is *gradients as decoration* and *glass as texture* — not all visual interest. |
| `REBUILD_03 §6.1` | Flat officer worklist as the entry point | Four-level ward-first structure (§7) |
| `REBUILD_03 §10` | `/officer/problem/:id` reached from a flat list | Reached via L1 → L2 → L3 → L4 |
| `REBUILD_00`, `REBUILD_01`, all Stage docs | "BBMP" | The five corporations / GBA (§6.2) |

Also carried forward unchanged and still in force: `REBUILD_01`'s 31 problems, `REBUILD_02 §3` clustering (geohash-7, 150 m, 30 days, transitive), `REBUILD_02 §8` schema plus the additions in §12 below, and the EXIF-before-strip requirement.

---

## 12. Schema additions beyond `REBUILD_02 §8`

```
problem_group        + corporation_id, locality_id, agency_responsible,
                       service_code, sla_days, sla_due_at, sla_breached,
                       lane ('safety' | 'statutory' | 'discretionary')

group_score          + exposure, vulnerability          (PE split in two)
                     + exposure_context, vulnerability_context   (the winning
                       context codes, so the UI can say WHY in words)
                     + triage_policy_version = 'triage-v3'

jurisdiction_flag      id, geohash7, agency_ids[], group_ids[],
                       oldest_open_at, created_at

resolution_evidence    id, group_id, decision_id, photo_id,
                       resolved_by, resolved_at
                       -- mandatory photo on 'Resolved'

service_catalogue      service_code, service_name_en/kn/hi, group,
                       agency_responsible, sla_days, severity_prior
                       -- Open311-shaped; source of truth for §4.2
```

---

## 13. Build order (revised)

| # | Work | Done when |
|---|---|---|
| 1 | `service_catalogue` + agency routing table | A category resolves to an agency and an SLA |
| 2 | Photo upload + **EXIF GPS read before stripping** | A geotagged photo puts real lat/lon on the report row |
| 3 | Map pin confirmation in the form | Every report has usable coordinates or is explicitly `coarse` |
| 4 | `problem_group` + clustering (geohash-7, 150 m, 30 d) | Two nearby same-category reports become one group; the second receipt says so |
| 5 | Durable job queue + worker | A report in Postgres mode reaches `processed` unaided |
| 6 | OSM import → roads, POIs, localities | Any lat/lon returns road class + nearby POIs offline |
| 7 | `triage-v3.json` + scorer + the six §5.7 tests | All six numbers reproduce exactly |
| 8 | Three-lane assignment + SLA computation | Lanes are visually separate and correctly populated |
| 9 | Rewire officer reads to computed data | Deleting `ground_truth.json` changes nothing |
| 10 | 50k generator anchored to real South Bengaluru geometry | Tens of thousands of reports collapse into hundreds of groups |
| 11 | Four-level dashboard (L1→L4) | An officer enters by ward *or* by agency |
| 12 | Score breakdown UI with EX/VU shown separately | An officer hand-verifies a rank with a calculator |
| 13 | Jurisdiction dispute flag | At least one flag fires in the demo corpus |
| 14 | Closure loop + mandatory resolution photo | A resolution cannot be recorded without a photo |
| 15 | Recurrence detection | The demo can name a problem "resolved" 3 times |
| 16 | Validation on real 311 data | One defensible precision/recall number |

Steps 2–4 remain the project in miniature. Nothing after step 4 matters until a submitted report visibly joins a group.

---

## 14. Open risks

| Risk | Mitigation |
|---|---|
| 368-ward boundaries notified July 2025 may have no public GeoJSON | Use OSM `place=suburb` localities (§2.2). Citizens say "JP Nagar," not "Ward 178" — more available *and* more usable. |
| Sakala's 478 services are mostly certificates, not repairs | State plainly that SLAs are *modelled on* the Sakala mechanism, not its notified limits (§4.3). |
| Equity literature cited from knowledge, not fetched (403) | **Verify before quoting figures in any submission** (§1.2). |
| Sahaaya's current design unverified | Not required for the build. Install and screenshot it if a comparison is wanted. |
| OSM POI coverage may be uneven across South Bengaluru wards | Measure coverage per ward and disclose it. Low-coverage wards get `VU = baseline` and are flagged, not silently scored. |
| `reporter_token` is spoofable | Rate-limit per IP and per session; mark `signal_quality: 'weak'` when tokens are absent (`P-29`). |
| AI misclassifies category → wrong agency | The citizen's tapped category is authoritative; AI disagreement is logged, never an override. `OTHER` goes to an unranked classification queue. |

---

## 15. Sources

Fetched and read on 15 September 2026:

- Open311 — https://www.open311.org/learn/
- Open311 GeoReport v2 — https://wiki.open311.org/GeoReport_v2/
- FixMyStreet Platform — https://fixmystreet.org/
- Traffy Fondue — https://en.wikipedia.org/wiki/Traffy_Fondue
- SeeClickFix — https://en.wikipedia.org/wiki/SeeClickFix
- 3-1-1 systems — https://en.wikipedia.org/wiki/3-1-1
- Greater Bengaluru Authority — https://en.wikipedia.org/wiki/Greater_Bengaluru_Authority
- BBMP — https://en.wikipedia.org/wiki/Bruhat_Bengaluru_Mahanagara_Palike
- Bangalore civic administration — https://en.wikipedia.org/wiki/Bangalore
- Karnataka Sakala Services Act — https://en.wikipedia.org/wiki/Karnataka_Sakala_Services_Act
- Right to Public Services legislation — https://en.wikipedia.org/wiki/Right_to_Public_Services_legislation
- BWSSB — https://en.wikipedia.org/wiki/Bangalore_Water_Supply_and_Sewerage_Board
- BESCOM / KPTCL — https://en.wikipedia.org/wiki/Bangalore_Electricity_Supply_Company
- BMTC — https://en.wikipedia.org/wiki/Bangalore_Metropolitan_Transport_Corporation
- CPGRAMS — https://en.wikipedia.org/wiki/Centralized_Public_Grievance_Redress_and_Monitoring_System
- OSM amenity tags — https://wiki.openstreetmap.org/wiki/Key:amenity
- Overpass API — https://wiki.openstreetmap.org/wiki/Overpass_API
- Geofabrik India — https://download.geofabrik.de/asia/india.html
- OpenStreetMap licence (ODbL) — https://en.wikipedia.org/wiki/OpenStreetMap

**Not obtained:** the 311 equity papers (publisher returned 403 — §1.2 provenance note) and the Sahaaya app listing (404).
