# Implementation decisions

**Revised:** 15 September 2026. **The five decisions previously recorded in this file are all superseded.** The file is kept because other documents reference the path.

## What this file used to say, and why it changed

Approved 12 September 2026, five defaults were locked here. Four of them became blockers:

| Original decision | Status | Replacement |
|---|---|---|
| "Image upload is deferred" | **Reversed** | Images are required. Up to 3 photos, 8 MB, 12 MP, EXIF GPS read → persist → strip → store. `REBUILD_05 §3`, `archive/STAGE_4 §8`. Officers judge severity from photos; without them the officer surface has nothing to look at. |
| "No Google Map dependency" | **Reversed in effect** | Correct to avoid *Google* Maps — for billing and key-exposure reasons, not complexity. But a map is required. **MapLibre GL JS + a self-hosted Protomaps `.pmtiles` extract.** `REBUILD_05 §1.3`. |
| "60 curated synthetic reports rather than 120" | **Reversed** | 20,000–50,000 generated on real OSM geometry. Grouping, recurrence and the ward scorecard cannot be demonstrated — or tested — at n=60. `REBUILD_04 §10.2`. |
| "The four prototype priority components retain the `30/25/25/20` profile" | **Superseded** | Six components: `0.24·CS + 0.18·PS + 0.16·EX + 0.18·VU + 0.16·SV + 0.08·NG`. `REBUILD_04 §5.6`, with `CS` amended by `REBUILD_05 §4`. |
| (fifth default — fixture interpreter as local default) | **Retained** | `FixtureInterpreter` remains the default. No test calls a live model. |

**The lesson worth recording:** each of the four reversals was defensible as a scope cut in isolation. Together they removed everything the product's core mechanism depends on — coordinates, photos, and enough data to group anything — while the documents continued to describe grouping and ranking as delivered. Scope cuts need to be checked against the mechanism they serve, not just against the calendar.

## Decisions currently in force

Nothing is decided in this file any more. Authority is:

- **Scope, geography, agencies** → `REBUILD_00 §3`, `REBUILD_04 §2`
- **Score, lanes, routing** → `REBUILD_04 §3`–`§6`
- **Location, grouping geometry, abuse resistance, closure** → `REBUILD_05`
- **Build order** → `REBUILD_05 §10`
- **Non-negotiable engineering rules** → `AGENTS.md`
