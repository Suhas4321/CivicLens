# CivicLens Rebuild — UI/UX Design Blueprint

**Written:** 15 September 2026
**Companion to:** `REBUILD_00_HANDOFF_AND_SCOPE.md`, `REBUILD_01_PROBLEM_REGISTER.md`, `REBUILD_02_DATA_PIPELINE_AND_PRIORITY.md`
**Status:** Authoritative. Supersedes the UI guidance in `archive/STAGE_2_PRODUCT_DESIGN.md §7` and `archive/STAGE_6_FINAL_DESIGN_REVIEW.md §13`.
**Constraint in force:** no code until the owner grants permission. This document is the thing to build *from*.

> ⚠️ **Amended by `REBUILD_05`:**
> - **§4.2 `/report`** — the location block is replaced by the four-state GPS + draggable-pin flow in `REBUILD_05 §1.2`, including the no-map "choose area from a list" fallback.
> - **§4.3 `/receipt/:publicId`** — gains the 48-hour **"Fixed" / "Not fixed"** verification control: `REBUILD_05 §5.2`.
> - **§6.1 / §6.2 officer surfaces** — add the signal-integrity display (`REBUILD_05 §4.6`) and the ward recurrence scorecard (`REBUILD_05 §7`).
> - **Map library is now fixed: MapLibre GL JS + a self-hosted Protomaps `.pmtiles` extract. No Google Maps, no public OSM tile servers.** See `REBUILD_05 §1.3`.
> - **A correction the owner made to this document:** it leaned too hard on GOV.UK and over-corrected from SaaS into drab. Indian government portals are the *anti-*pattern, not the target. See `REBUILD_04 §11`.

---

## 1. The design problem, stated honestly

The current frontend is competently built and aimed at the wrong audience. Geist Variable, oklch teal, masked gradient grids, `backdrop-blur-xl`, `tracking-[-0.06em]` on a 5.4rem headline, `rounded-2xl` with 70px shadows — that is the visual language of Linear, Vercel and Stripe. It is *designed for people who buy software*.

CivicLens is for a person standing next to a flooded street on a ₹8,000 Android phone, possibly reading Kannada rather than English, who has never used a SaaS dashboard and has no reason to trust a website. For that person, trust comes from a completely different set of signals:

| SaaS register (current) | Public-service register (target) |
|---|---|
| Aspirational imagery, big claims | Immediate action, no marketing |
| Tight tracking, display type | Plain type, generous size |
| Gradients, glass, glow | Flat surfaces, 1px borders |
| Subtle low-contrast greys | High contrast, near-black on white |
| Clever labels | Literal labels |
| English | Their language, switchable in the header |
| Delight | Legibility and predictability |

Reference points to study: **UMANG**, **DigiLocker**, **Bengaluru One**, **GOV.UK Design System**, and the GIGW 3.0 guidelines. GOV.UK is the strongest model — it is deliberately plain, and it is plain because plain is measurably more usable for people under stress.

**Three surfaces, three distinct treatments.** The current build has two shells that look nearly identical, which is why nobody can tell the public site from the officer portal (owner's original complaint). The fix:

| Surface | Who | Visual signature |
|---|---|---|
| **Citizen** (`/`, `/report`, `/receipt/:id`) | The public, on a phone | White, large type, big tap targets, blue accents, almost no chrome |
| **Public transparency** (`/nearby`) | Anyone curious | Same palette, but map- and data-led, light grey page background |
| **Officer console** (`/officer/*`) | Internal staff, on a desktop | Dark slate top bar, dense tables, small type, full-bleed, tool-like |

They must be *unmistakable* from a single glance at a screenshot.

---

## 2. Design tokens

Replace the token block in `apps/web/src/styles/global.css`. Delete `tailwind.config.js` and `postcss.config.js` (P-14).

### 2.1 Typography

```css
/* Noto Sans covers Latin, Kannada and Devanagari with harmonised metrics.
   This single change does more to fix the "wrong kind of website" problem
   than any other, and it is also the only way to render ಕನ್ನಡ properly. */
--font-sans:      "Noto Sans", system-ui, sans-serif;
--font-kannada:   "Noto Sans Kannada", "Noto Sans", sans-serif;
--font-devanagari:"Noto Sans Devanagari", "Noto Sans", sans-serif;
--font-mono:      "Noto Sans Mono", ui-monospace, monospace;  /* IDs, codes, scores */
```

Self-host the WOFF2 subsets. Do not use a font CDN — an Indian civic site should not have a third-party font request on the critical path.

| Token | Size / line-height | Use |
|---|---|---|
| `--text-display` | 32/40 mobile, 40/48 desktop | Page title only |
| `--text-h2` | 24/32 | Section heading |
| `--text-h3` | 19/28 | Card heading |
| `--text-body` | **17/26 mobile**, 16/26 desktop | Everything |
| `--text-small` | 15/22 | Metadata, help text |
| `--text-micro` | 13/18 | Legal, timestamps |

Rules: **letter-spacing 0 everywhere** (no `tracking-[-0.06em]`). No `clamp()` display type. Weights 400 / 600 / 700 only. 17px body on mobile, not 16 — measurably better for outdoor reading and for older users.

### 2.2 Colour

```css
/* Institutional blue. Sober, unmistakably governmental, WCAG AA on white. */
--blue-900: #0B2E59;   /* officer top bar, footer */
--blue-700: #14498C;   /* primary buttons, links */
--blue-600: #1A5AAB;   /* hover */
--blue-50:  #EAF1F9;   /* selected rows, info panels */

--ink-900:  #14181F;   /* body text — near-black, 15.8:1 on white */
--ink-700:  #3A424E;   /* secondary text — 9.2:1 */
--ink-500:  #6B7480;   /* tertiary — 4.6:1, minimum allowed */
--line:     #D4D9E0;   /* 1px borders */
--surface:  #FFFFFF;
--canvas:   #F4F6F8;   /* page background behind cards */

/* Status. Never colour-only — always paired with an icon and a word. */
--red-700:    #A3231C;  --red-50:    #FBEBEA;   /* safety / high */
--amber-700:  #8A5A00;  --amber-50:  #FDF3E2;   /* moderate */
--green-700:  #1E6B3A;  --green-50:  #E9F5EC;   /* resolved / lower */
--slate-700:  #4A5462;  --slate-50:  #EFF1F4;   /* not comparable / pending */
```

Delete both existing palettes: the oklch teal in `global.css` and the `#0066ff` blue in `tailwind.config.js`.

### 2.3 Space, radius, elevation

```css
--space: 4px base → 4 8 12 16 24 32 48 64
--radius-sm: 4px;   --radius-md: 6px;   --radius-full: 999px;  /* pills only */
--border: 1px solid var(--line);
--shadow-1: 0 1px 2px rgba(20,24,31,0.08);   /* the only shadow */
--shadow-2: 0 4px 12px rgba(20,24,31,0.12);  /* modals only */
```

**Banned:** `rounded-2xl`+, `backdrop-blur-*`, `mask-image` gradient grids, any gradient background, shadows over 12px blur, glass surfaces, decorative blur orbs. All are present today and all must go.

### 2.4 Layout

```css
--container-reading: 1120px;   /* citizen + public pages, centred */
--container-console: 100%;     /* officer: full-bleed */
--gutter-mobile: 16px;
--gutter-desktop: 24px;
```

Exactly two widths. No page declares its own. This fixes the 1440/1500/1600 inconsistency and the dead 280px gutters on a 1920px screen (P-19). Officer console goes **full-bleed** — a data tool should use the whole monitor.

### 2.5 Controls

| Element | Spec |
|---|---|
| Primary button | `--blue-700` bg, white text, 6px radius, 48px min height mobile / 40px desktop, 16px text, 600 weight |
| Secondary button | white bg, 1px `--blue-700` border, `--blue-700` text |
| Destructive | white bg, 1px `--red-700` border, `--red-700` text — never a solid red button |
| Text input | white, 1px `--line`, 6px radius, 48px height, 17px text, label **above** (never a placeholder as label) |
| Focus ring | `3px solid #F5A623` offset 2px — thick and amber so it is visible outdoors on a cheap screen |
| Tap target | **48×48 px minimum**, 8px minimum gap |
| Error | Red text + icon **below** the field, plus a summary at the top of the form linking to each field |

---

## 3. Global chrome

### 3.1 Utility strip (all surfaces, 32px, `--canvas`, 13px text)
```
┌──────────────────────────────────────────────────────────────────────────┐
│ Demonstration system · synthetic data · not an official government service │
│                                     Emergency? Call 112   EN ｜ ಕನ್ನಡ ｜ हिंदी │
└──────────────────────────────────────────────────────────────────────────┘
```
This is the **only** place the demo disclaimer and the emergency notice appear. Today those warnings are repeated on nearly every card, which makes the product look like it is apologising for existing (P-20). One strip, always visible, done.

### 3.2 Citizen header (64px, white, 1px bottom border)
```
┌──────────────────────────────────────────────────────────────────────────┐
│  [◈] CivicLens          Report a problem   Problems near me   Officer login│
│      Bengaluru civic reporting                                            │
└──────────────────────────────────────────────────────────────────────────┘
```
Wordmark + a one-line descriptor in `--ink-700`. Three links, plain words. On mobile: wordmark left, hamburger right, and a persistent bottom bar with **Report** / **Near me**.

### 3.3 Officer header (56px, `--blue-900`, white text)
```
┌──────────────────────────────────────────────────────────────────────────┐
│  CivicLens Console      Worklist  Safety(3)  Decisions      A. Kumar ▾   │
└──────────────────────────────────────────────────────────────────────────┘
```
The dark bar is the primary signal that you have left the public site. Do it in one solid colour — no gradient, no blur.

### 3.4 Footer
Citizen: four link columns (About / How ranking works / Privacy / Contact) + a licence line. The **"How ranking works"** page is important — it publishes the weights and the tables from `REBUILD_02 §4`. Publishing your own algorithm is the strongest possible trust signal and costs almost nothing to build.
Officer: single line — build hash, policy versions (`triage-v2`, `grouping-v2`), data-as-of timestamp.

---

## 4. Surface 1 — Citizen

### 4.1 `/` — Home
Action-first. The current hero is 5.4rem of aspirational copy above the fold; nobody arriving with a flooded street needs a value proposition.

```
┌────────────────────────────────────────────────────────────────────┐
│ Demonstration system · synthetic data     Emergency? 112   EN|ಕನ್ನಡ|हिंदी│
├────────────────────────────────────────────────────────────────────┤
│ [◈] CivicLens                Report   Near me   Officer login      │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│   Report a civic problem in Bengaluru                    32/40     │
│   Take a photo. We group it with other reports about     17/26     │
│   the same place and show officers what needs attention  --ink-700 │
│   most.                                                            │
│                                                                    │
│   What is the problem?                                             │
│   ┌──────────┬──────────┬──────────┐                               │
│   │   🕳     │   💧     │   🗑     │   3 columns mobile             │
│   │  Road    │  Water   │ Garbage  │   6 columns desktop           │
│   │  damage  │          │          │   each tile ≥104px square     │
│   ├──────────┼──────────┼──────────┤   icon + word, both           │
│   │   💡     │   🌊     │   ⚡     │   1px border, 6px radius      │
│   │  Street  │  Water   │Electrical│   tapping = step 1 done       │
│   │  light   │  logging │  hazard  │                               │
│   └──────────┴──────────┴──────────┘                               │
│                                                                    │
│   ─────────────────────────────────────────────────────            │
│                                                                    │
│   In Bengaluru this month                                          │
│   ┌───────────────┬───────────────┬───────────────┐                │
│   │    24,318     │      847      │      112      │  mono, 32px    │
│   │ reports       │ grouped       │ decisions     │                │
│   │ received      │ problems      │ recorded      │                │
│   └───────────────┴───────────────┴───────────────┘                │
│                            [ See problems near me → ]              │
│                                                                    │
│   ─────────────────────────────────────────────────────            │
│   How this works                                                   │
│   1  You report a problem with a photo.                            │
│   2  We group reports about the same place together.               │
│   3  Problems are ranked by how many people are affected,          │
│      how long it has lasted, and what is nearby — a hospital       │
│      or a main road counts for more.                               │
│   4  An officer reviews and decides. Their reason is published.    │
│   [ See exactly how ranking works → ]                              │
└────────────────────────────────────────────────────────────────────┘
```

The category grid **is** the primary call to action — tapping a tile starts a report with step 1 pre-filled. Icon *and* word, always; icon-only fails for unfamiliar users, word-only fails for low literacy.

### 4.2 `/report` — Four steps

Replace the single dense form (2000-char textarea, free-text locality, prominent voice card, two legal checkboxes, disabled submit — P-18) with a stepper. Stage 2 §5 specified this; it was never built.

```
Step 1 of 4 ████░░░░░░░░
```

**Step 1 — What?** The same 6-tile grid. One tap. If it came from the home page, this step is already complete and is shown collapsed as `Road damage ✎ change`.

**Step 2 — Photo.** *The most important screen in the product.*
```
┌────────────────────────────────────────────┐
│  Step 2 of 4  ████████░░░░                 │
│                                            │
│  Add a photo                        32/40  │
│  A photo helps us find the exact place     │
│  and shows the officer the problem.        │
│                                            │
│  ┌──────────────────────────────────────┐  │
│  │                                      │  │
│  │              📷                      │  │
│  │      Take a photo                    │  │  full-width, 200px tall
│  │      (opens your camera)             │  │  capture="environment"
│  │                                      │  │
│  └──────────────────────────────────────┘  │
│           Choose from gallery              │  secondary, small
│                                            │
│  ┌────────┬────────┬────────┐              │
│  │ [img]✕ │ [img]✕ │   +    │  up to 3     │
│  └────────┴────────┴────────┘              │
│                                            │
│  ✓ Location found in your photo            │  green, only if EXIF GPS
│                                            │
│  [ Skip — no photo ]        [ Continue → ] │
└────────────────────────────────────────────┘
```
Camera-first (`capture="environment"`), gallery secondary. Skipping is allowed but visibly the lesser path. Salvage `PhotoPreview` / `MAX_PHOTOS` / `ACCEPT_TYPES` / `URL.revokeObjectURL` cleanup from the dead `src/pages/ReportPage.tsx` before deleting that tree (P-13).

**Step 3 — Where?**
```
┌────────────────────────────────────────────┐
│  Where is it?                              │
│  ┌──────────────────────────────────────┐  │
│  │                                      │  │
│  │        [ map, 280px tall,            │  │  OSM / MapLibre
│  │          draggable pin ]             │  │  pin pre-set from
│  │                                      │  │  EXIF GPS, else
│  └──────────────────────────────────────┘  │  device location
│  Drag the pin if it is not exact.          │
│                                            │
│  Near: 80 Feet Road, Mahadevapura          │  reverse geocoded
│  Ward:  Mahadevapura (Ward 84)             │
│                                            │
│  Map not loading?  Pick your ward ▾        │  fallback → 'coarse'
│  [ ← Back ]                 [ Continue → ] │
└────────────────────────────────────────────┘
```
Confirming a pin is one drag. Typing "near Chinnappa circle" is a sentence that no machine can group (P-03). The ward dropdown fallback sets `location_quality: 'coarse'` and the report is honestly labelled as such.

**Step 4 — Confirm.** Restores Stage 2's **"Review understanding"** screen — designed, never built.
```
┌────────────────────────────────────────────┐
│  Check your report                         │
│                                            │
│  ┌──────────────────────────────────────┐  │
│  │ We understood:                       │  │
│  │                                      │  │
│  │ Problem   Road damage         ✎      │  │
│  │ Place     80 Feet Road,       ✎      │  │
│  │           Mahadevapura               │  │
│  │ Photos    2 attached          ✎      │  │
│  │                                      │  │
│  │ Anything to add? (optional)          │  │
│  │ ┌──────────────────────────────────┐ │  │
│  │ │ e.g. large hole near the bus stop│ │  │
│  │ └──────────────────────────────────┘ │  │
│  │            🎤 Speak instead of typing│  │  small link, not a card
│  └──────────────────────────────────────┘  │
│                                            │
│  ☐ I agree this report may be shown        │  ONE checkbox
│    publicly without my name.               │
│    Privacy details →                       │
│                                            │
│  [        Submit report        ]           │  full-width, 56px
└────────────────────────────────────────────┘
```
Every field editable inline. **One** consent checkbox — the current two-checkbox legal block is a wall. Voice demoted to a text link (P-22): it produces no location, no verification and no literacy advantage over tapping an icon, and costs more to process.

### 4.3 `/receipt/:publicId` — The closure loop

Currently a dead end (P-06). This is where the product either earns a returning citizen or loses them.

```
┌────────────────────────────────────────────────────────┐
│  ✓  Report received                                    │
│                                                        │
│     Reference   CL-8F3K-22Q1        [ Copy ]           │  mono, 24px
│     Save this to check back later.                     │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Your report joined 11 other reports              │  │  ← the payoff
│  │ about this road.                                 │  │
│  │                                                  │  │
│  │ Currently ranked 12th of 340 open problems        │  │
│  │ in Mahadevapura.                                 │  │
│  │                                                  │  │
│  │ [ small map showing all 12 pins ]                │  │
│  └──────────────────────────────────────────────────┘  │
│                                                        │
│  What happens next                                     │
│  ● 15 Sep  Report received                             │
│  ○         Officer review                              │
│  ○         Decision published                          │
│                                                        │
│  [ See all problems near me → ]                        │
└────────────────────────────────────────────────────────┘
```

If it is the first report about that place: *"This is the first report about this location. If others report it too, it will rise in priority."* — honest, and it teaches how the system works.
If it went to the safety lane: *"This looks like a safety hazard. It has been sent for immediate review and is not waiting in the normal queue."*

---

## 5. Surface 2 — Public transparency (`/nearby`)

New route (P-17). This is the differentiator over every existing complaint portal: those take your complaint and go silent. This one shows the whole picture.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Demonstration system · synthetic data     Emergency? 112   EN|ಕನ್ನಡ|हिंदी │
├──────────────────────────────────────────────────────────────────────────┤
│ [◈] CivicLens                        Report   Near me   Officer login    │
├──────────────────────────────────────────────────────────────────────────┤
│  Problems near you                                              32/40    │
│  Ward: [ Mahadevapura ▾ ]   Category: [ All ▾ ]   Time: [ 30 days ▾ ]    │
│                                                                          │
│  ┌────────────────────────┬──────────────────────────────────────────┐   │
│  │  1,284    340     47   │                                          │   │
│  │  reports  grouped decided│      [ map, clustered pins,            │   │
│  │                        │        colour = band,                    │   │
│  │  Top problems          │        size = report count ]             │   │
│  │  ─────────────────     │                                          │   │
│  │  1 Road damage    HIGH │      Hovering a pin highlights           │   │
│  │    80 Feet Rd · 12     │      its row, and vice versa.            │   │
│  │  2 Waterlogging   HIGH │                                          │   │
│  │    Kundalahalli · 9    │                                          │   │
│  │  3 Garbage       MOD   │                                          │   │
│  │    ITPL Road · 7       │                                          │   │
│  └────────────────────────┴──────────────────────────────────────────┘   │
│                                                                          │
│  Recent decisions                                                        │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │ 14 Sep  Road damage, 80 Feet Road      → Referred for repair       │  │
│  │         "12 reports over 11 days on a main road; verified 13 Sep." │  │
│  │ 13 Sep  Street light, Brookefield      → Verification requested    │  │
│  │         "3 reports; unable to confirm the exact pole."             │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  How problems are ranked  →   Download this ward's data (CSV)  →         │
└──────────────────────────────────────────────────────────────────────────┘
```

Never published here: reporter identity, exact coordinates of a single report (snap to the group centroid), raw photos before moderation, individual report text. Only aggregates, bands, and officer decisions with their stated reasons.

Bands shown as words (`HIGH` / `MODERATE` / `LOWER`), not scores. Numeric scores are an officer tool; a bare `68.5` on a public page invites misreading. The **"How problems are ranked"** page carries the full arithmetic for anyone who wants it.

---

## 6. Surface 3 — Officer console

A tool, not a page. Dense, keyboard-driven, full-bleed. The current version renders 6 cards with a text filter (P-21).

### 6.1 `/officer` — Worklist
```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ CivicLens Console        Worklist   Safety(3)   Decisions          A. Kumar ▾    │  --blue-900
├──────────────────────────────────────────────────────────────────────────────────┤
│ ⚠  3 safety reports awaiting review — not ranked          [ Review now → ]       │  --red-50, pinned
├────────────┬─────────────────────────────────────────────────────────────────────┤
│ FILTERS    │  340 problems · 24,318 reports          [ ▤ Table ] [ ⬛ Map ]       │
│ 240px      │                                                                     │
│            │  # │Band│Problem          │Ward      │People│Days│Score│Last  │      │
│ Ward       │ ───┼────┼─────────────────┼──────────┼──────┼────┼─────┼──────┤      │
│ ☑ All      │  1 │HIGH│Waterlogging     │Kundala…  │  23  │ 18 │82.4 │2h    │      │
│ ☐ Mahade…  │  2 │HIGH│Road damage      │Mahade…   │  19  │ 14 │73.5 │5h    │      │
│ ☐ Kundal…  │  3 │HIGH│Sewage overflow  │Whitefld  │  14  │ 22 │74.6 │1d    │      │
│            │  4 │MOD │Road damage ↺    │Marathal… │  11  │  9 │69.2 │3h    │      │
│ Category   │  5 │MOD │Garbage          │ITPL Rd   │   9  │ 12 │61.0 │6h    │      │
│ ☑ All      │ ...                                                                 │
│            │                                        rows 40px, 15px text         │
│ Band       │  ↺ = recurring after closure                                        │
│ ☑ High     │  Every column sortable. j/k to move, Enter to open, / to search.    │
│ ☑ Moderate │                                                                     │
│ ☐ Lower    │  ─────────────────────────────────────────────────────────────      │
│            │  ⓘ 14 problems need location review and are not ranked. [ View ]     │
│ Status     │                                                                     │
│ ☑ Open     │                                                                     │
│ ☐ Referred │                                                                     │
│ ☐ Closed   │                                                                     │
│            │                                                                     │
│ Age        │                                                                     │
│ ○ Any      │                                                                     │
│ ○ 30d+     │                                                                     │
├────────────┴─────────────────────────────────────────────────────────────────────┤
│ triage-v2 · grouping-v2 · data as of 15 Sep 2026 14:22 IST · build a3f91c        │
└──────────────────────────────────────────────────────────────────────────────────┘
```

Non-negotiables: the safety strip is **pinned above the ranked list and never sorted into it**; the "needs location review" count is **always visible** so abstentions are not hidden; policy versions are in the footer on every screen; **People** is distinct reporters, not report count, with a tooltip saying so.

Map view: the same data, synced selection, clustered pins coloured by band.

### 6.2 `/officer/problem/:id` — Detail

Replaces `/officer/needs/:id` and `/officer/incidents/:id`. One entity — the problem group — instead of two overlapping ones.

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ ← Worklist    Road damage — 80 Feet Road, Mahadevapura        #2 of 340   HIGH   │
├───────────────────────────────────────────┬──────────────────────────────────────┤
│  WHY THIS RANK                     Score  │  DECISION                            │
│                                    73.5   │                                      │
│  19 different people               65     │  ( ) Refer for repair                │
│  reported it     ████████░░  ×0.25 =16.25 │  ( ) Request field verification      │
│                                           │  ( ) Merge with another problem      │
│  over 14 distinct days             70     │  ( ) Not a problem / duplicate       │
│                  ███████░░░  ×0.20 =14.00 │                                      │
│                                           │  Reason (required, published)        │
│  on a major road                  85      │  ┌────────────────────────────────┐  │
│  (OSM: primary)  ████████▌░  ×0.25 =21.25 │  │                                │  │
│                                           │  └────────────────────────────────┘  │
│  road damage severity             65      │                                      │
│                  ██████▌░░░  ×0.20 =13.00 │  Before deciding, confirm:           │
│                                           │  ☐ I reviewed the photo evidence     │
│  oldest report 34 days ago        90      │  ☐ I considered that these may be    │
│                  █████████░  ×0.10 = 9.00 │    separate nearby problems          │
│                                  ───────  │  ☐ I checked for an existing         │
│                            Total   73.50  │    referral for this location        │
│                                           │                                      │
│  policy triage-v2 · computed 14:22 IST    │  [ Record decision ]                 │
│  Was MODERATE (61.2) on 8 Sep ↗           │  Appended to history. Cannot be      │
│                                           │  deleted. Published on /nearby.      │
│  ─────────────────────────────────────    │                                      │
│  CAPITAL REFERRAL (Tier 2)                │  ────────────────────────────────    │
│  Not eligible — field verification        │  HISTORY                             │
│  required.                                │  14 Sep  A.Kumar  verification req.  │
│  MISSING_SERVICE_DISADVANTAGE_EVIDENCE    │          "cannot confirm extent"     │
│  MISSING_SCALE_EXPOSURE_EVIDENCE          │  09 Sep  system  grouped 3 reports   │
│  [ What would make this eligible? ]       │                                      │
├───────────────────────────────────────────┴──────────────────────────────────────┤
│  EVIDENCE   [ 19 reports ]  [ 14 photos ]  [ Map ]  [ Timeline ]                 │
│  ┌───────┬───────┬───────┬───────┬───────┬───────┐  ┌──────────────────────────┐ │
│  │[photo]│[photo]│[photo]│[photo]│[photo]│  +9   │  │ [ map: 19 pins, 150m     │ │
│  │12 Sep │12 Sep │10 Sep │08 Sep │05 Sep │       │  │   radius, centroid ]     │ │
│  └───────┴───────┴───────┴───────┴───────┴───────┘  └──────────────────────────┘ │
│  Photos are citizen-submitted evidence, not verified facts.                       │
└──────────────────────────────────────────────────────────────────────────────────┘
```

The five-bar breakdown is the single most important component in the entire product. It converts "the computer said 78" into "19 people, 14 days, main road, here is the multiplication." Build it early and well.

The **"Was MODERATE (61.2) on 8 Sep ↗"** line comes free from the append-only `group_score` table (`REBUILD_02 §8`) and is genuinely useful — it shows a problem getting worse.

The three confirmation checkboxes preserve the existing alternative-hypothesis discipline, which is one of the project's real strengths. Keep them.

### 6.3 `/officer/safety` — Safety lane
Separate list, `--red-50` background, chronological (never scored), single action per item: **Escalate** / **Confirm not a hazard**, reason required. Zero ranking language on this screen.

---

## 7. Language switching

| Aspect | Decision |
|---|---|
| Languages | English, ಕನ್ನಡ (Kannada), हिंदी (Hindi) |
| Scope | **All citizen and public surfaces.** Officer console stays English-only — internal users, and it keeps the work finite. |
| Placement | Utility strip, top-right, on every page. Never buried in a settings menu. |
| Storage | `localStorage`, defaulting from `navigator.language` |
| Implementation | Three flat JSON files, one `useTranslation()` hook. No i18n framework — the string count does not justify it. |
| Markup | `lang="kn"` / `lang="hi"` on translated regions so screen readers and font fallbacks behave |
| Line height | Kannada and Devanagari need extra leading — use `1.7` where Latin uses `1.5` |
| Not translated | Reference codes, ward names, timestamps, officer names |

A Bengaluru civic platform with an English-only interface cannot honestly claim to serve Bengaluru. This is the largest single gap between the pitch and the artefact (P-16), and it is also cheap to close.

---

## 8. Accessibility (GIGW 3.0 / WCAG 2.1 AA)

| Requirement | Target |
|---|---|
| Text contrast | ≥ 4.5:1 (tokens in §2.2 are all compliant) |
| Tap targets | ≥ 48×48 px, ≥ 8px apart |
| Focus | 3px amber ring, logical DOM order, skip-to-content link |
| Forms | Visible `<label>` above every input, never placeholder-as-label, errors linked and summarised |
| Colour | Never the sole carrier of meaning — icon + word always accompany band colours |
| Motion | Honour `prefers-reduced-motion` (the dead `index.css` did this correctly — carry it forward) |
| Images | Meaningful `alt`; photo thumbnails describe category + date |
| Zoom | Usable at 200% without horizontal scroll |
| Screen reader | Full keyboard pass on the report flow before any release |

---

## 9. Dead code to purge

**Do not run this until the owner confirms the demo no longer needs the second frontend.**

**Step 1 — Salvage first.** From `apps/web/src/pages/ReportPage.tsx`, extract into `src/features/report-intake/PhotoInput.tsx`: the `PhotoPreview` interface, `MAX_PHOTOS = 3`, `ACCEPT_TYPES`, the `photosRef` + `URL.revokeObjectURL` cleanup, and `removePhoto(id)`. This is the only genuinely valuable code in the dead tree.

**Step 2 — Delete.**
```
apps/web/src/App.tsx                      # imports pages/CivicNeedWorkspace, which does not exist
apps/web/src/pages/                       # Home, IncidentWorkspace, OfficerDashboard, ReceiptPage, ReportPage
apps/web/src/data/mockData.ts             # hard-coded fixtures
apps/web/src/index.css                    # Tailwind v3 entry point
apps/web/tailwind.config.js               # v3 config, #0066ff palette
apps/web/postcss.config.js                # v3 pipeline
apps/web/src/components/Button.tsx
apps/web/src/components/Input.tsx
apps/web/src/components/StatusPill.tsx
apps/web/src/components/ProvenanceBadge.tsx
apps/web/src/components/VoiceRecorder.tsx  # after voice is rebuilt as a small affordance
apps/web/src/components/index.ts
apps/web/tsconfig.tsbuildinfo              # build artefact, should be gitignored
```

**Step 3 — Empty the `exclude` array** in `apps/web/tsconfig.app.json`. Its 11 entries exist only to hide this tree from the type-checker. An empty `exclude` with a passing build is the proof the purge is complete.

**Step 4 — Verify:** `npm run build` passes, `npx tsc --noEmit` passes, no file imports anything deleted, no `tailwind.config.js` exists, one CSS entry point.

---

## 10. Route changes

| Route | Now | After |
|---|---|---|
| `/` | Hero-led marketing | Action-led, category grid |
| `/report` | One dense form | Four-step flow |
| `/receipt/:publicId` | Reference code only | Grouping outcome + rank + timeline |
| `/nearby` | — | **New** — public transparency |
| `/how-ranking-works` | — | **New** — published weights and tables |
| `/officer` | 6 cards + text filter | Filter rail + dense table + map |
| `/officer/safety` | Merged into overview | **New** — separate lane |
| `/officer/problem/:id` | — | **New** — replaces the two below |
| `/officer/needs/:id` | Exists | Redirect to `/officer/problem/:id` |
| `/officer/incidents/:id` | Exists | Redirect to `/officer/problem/:id` |
| `/demo` | Redirects to `/officer` | Remove |

Collapsing "needs" and "incidents" into one **problem** is worth doing for its own sake. The current three-name vocabulary (report → incident → civic need) is intellectually defensible but nobody using the product can hold it in their head — and the code has separate pages for two things that render nearly identically.

---

## 11. Build order

| # | Work | Done when |
|---|---|---|
| 1 | Tokens: fonts, colours, spacing in `global.css` | No gradient, no blur, no oklch teal anywhere; Noto Sans rendering |
| 2 | Purge dead tree (§9) after salvage | `exclude: []` and the build passes |
| 3 | Chrome: utility strip, two headers, footers | Public and officer surfaces are unmistakable in a screenshot |
| 4 | Container tokens (§2.4) | No page sets its own max-width; officer is full-bleed |
| 5 | Language switcher + string extraction | Switching to Kannada changes every citizen-facing string |
| 6 | `/report` four-step flow with photos | A report is submitted on a phone in under 60 seconds without typing |
| 7 | `/receipt/:id` with grouping outcome | The receipt names how many reports it joined |
| 8 | Officer worklist table + filters + keyboard | Sort by score, `j`/`k`, Enter to open |
| 9 | `/officer/problem/:id` score breakdown | An officer hand-verifies a rank with a calculator |
| 10 | `/nearby` | A citizen sees ward problems and officer reasons without logging in |
| 11 | `/how-ranking-works` | The weights and all five tables are published |
| 12 | Accessibility pass + Playwright (2 flows) | Contrast, focus, 48px targets verified; both flows green |

Steps 1–4 alone will remove most of the "under repair" impression, and they touch no backend code. They are the right thing to do first while the pipeline work in `REBUILD_02` proceeds in parallel.

---

## 12. Corrections to existing UI documents

| Document | What is wrong | Correct position |
|---|---|---|
| `STAGE_2 §7 Screen 3` | "Review understanding" screen specified | Good design, never built. Restored as step 4 (§4.2). |
| `STAGE_2 §5` | Image attach, GPS, language override specified | All correct, all dropped in the build. Reinstated. |
| `STAGE_6 §13` | "Never show a headline score" | Overridden. Show the score **with its arithmetic** (§6.2). An unexplained number is untrustworthy; an explained one is the product. |
| `STAGE_6 §4` | Voice as a P0 citizen capability | Demoted to a text link. Photos are P0. |
| `STAGE_6` | Kannada/Hindi interface localisation deferred | Reinstated as P0 for citizen surfaces. |
| Any doc implying two frontends are acceptable | — | One frontend. `features/**` is the survivor. |
| `IMPLEMENTATION_DECISIONS.md #2` | No map | Use OSM/MapLibre. Free. Coordinates are mandatory (P-03). |
