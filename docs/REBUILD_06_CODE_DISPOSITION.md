# REBUILD_06 — Code Disposition

**Status:** proposal awaiting approval. **Nothing in this document has been deleted.**

This document exists because `apps/web/src` currently contains **two complete, parallel
user interfaces**, and no amount of restyling fixes a codebase where a reader cannot tell
which screen the browser actually renders. Before any redesign, the tree has to have one
answer to "where does the report page live".

Every verdict below is `KEEP`, `REWRITE`, or `DELETE`, with the evidence for it. Deletion
happens only on Suhas's explicit approval of this list.

---

## 1. How live code was distinguished from dead code

Three independent checks, all agreeing:

1. **Entry point.** `apps/web/index.html` loads `src/main.tsx`. `main.tsx` imports
   `./app/router` and `./styles/global.css` — and nothing else from `src/`. So the live
   tree is `app/router.tsx` and everything it transitively imports.
2. **`App.tsx` is unreachable.** No file imports `src/App.tsx`. It is not referenced by
   `main.tsx`, the router, or `index.html`. Furthermore it imports
   `./pages/CivicNeedWorkspace`, **which does not exist in the tree** — so even if it were
   wired up, it could not compile. This is decisive: `App.tsx` and the `pages/*` tree it
   points at have never run.
3. **Version control agrees.** Running `git ls-files apps/web` against
   `git ls-files --others --exclude-standard apps/web` shows the split is exact:

   > **Every untracked file under `apps/web/src` belongs to the dead second UI.
   > Every tracked file under `apps/web/src` belongs to the live UI.**

   The one exception is `src/api/workflowReviews.ts`, which is untracked but pairs with
   Codex's untracked backend module `modules/workflow_reviews/` — handled separately in §5.

Check 3 is worth stating plainly because it means the disposition is mechanically
verifiable, not a matter of taste. The second UI was added on top of the first and never
committed.

### The Tailwind evidence

`apps/web/package.json` depends on `tailwindcss ^4.3.3` and `@tailwindcss/vite ^4.3.3`,
and `src/styles/global.css` opens with `@import "tailwindcss"` plus `@theme inline { … }` —
this is Tailwind **v4**, configured in CSS.

The untracked `tailwind.config.js` and `postcss.config.js` are **Tailwind v3 files**. With
the v4 Vite plugin they are never read (v4 only loads a JS config via an explicit
`@config` directive, which no stylesheet issues). So the palette defined in
`tailwind.config.js` — `primary: '#0066ff'`, `danger: '#dc3545'`, and the rest — has
**never been applied to a rendered pixel**. It is not a competing design system. It is
inert.

This matters for one specific reason: `#0066ff` / `#dc3545` are Bootstrap's default
palette. Had it been live, it would explain the "looks like any SaaS site" complaint. It
isn't live, so the real cause is elsewhere — see §4.

---

## 2. Frontend disposition

### 2.1 DELETE — the dead second UI

All untracked, all unreachable from `main.tsx`. 1,712 lines.

| File | Lines | Why it goes |
|---|---:|---|
| `src/App.tsx` | 23 | Unreachable entry point; imports a nonexistent module. |
| `src/pages/Home.tsx` | 145 | Duplicate of `features/home/HomePage.tsx`. |
| `src/pages/ReportPage.tsx` | 677 | Duplicate of `features/report-intake/ReportPage.tsx`. Longest file in the frontend and it has never executed. |
| `src/pages/OfficerDashboard.tsx` | 174 | Duplicate of `features/officer/OfficerOverviewPage.tsx`. |
| `src/pages/IncidentWorkspace.tsx` | 172 | Duplicate of `features/officer/IncidentDetailPage.tsx`. |
| `src/pages/ReceiptPage.tsx` | 139 | Duplicate of `features/report-intake/ReceiptPage.tsx`. |
| `src/data/mockData.ts` | 284 | Hand-typed fixtures rendered as if computed. This is the specific pattern REBUILD_00 §2 identifies as the previous pass's central dishonesty: **priority was not computed, it was typed.** It must not survive into the rebuild. |
| `src/index.css` | 22 | Second stylesheet, competing with `styles/global.css`. |
| `tailwind.config.js` | 28 | Tailwind v3 config in a Tailwind v4 project. Inert (§1). |
| `postcss.config.js` | — | Same; v4 needs no PostCSS config. |
| `src/components/Button.tsx` | 73 | Duplicates `components/ui/button.tsx`, which is what the live tree imports. |
| `src/components/Input.tsx` | 52 | Duplicates `components/ui/input.tsx`. |
| `src/components/ProvenanceBadge.tsx` | 21 | Duplicates `components/civic/ProvenanceBadge.tsx`. |
| `src/components/StatusPill.tsx` | 33 | No live importer. Superseded by the lane vocabulary in REBUILD_04 §3. |
| `src/components/index.ts` | 7 | Barrel file exporting only the above. |
| `src/tsconfig.tsbuildinfo` | — | Build cache; should be git-ignored, never committed. |

### 2.2 DELETE — with a design decision behind it

| File | Lines | Why it goes |
|---|---:|---|
| `src/components/VoiceRecorder.tsx` | 52 | See below. |

Voice recording also exists inline in the **live** `features/report-intake/ReportPage.tsx`
(lines 26–78, 127–139) — roughly 65 lines of `MediaRecorder` plumbing, a 30-second timer,
stream teardown, and three failure branches.

**Recommendation: remove voice capture from the intake flow entirely.** Suhas's assessment
was *"there is an audio option. I don't know what is the use of that"* — and it is
correct, for a reason worth recording:

- The blob is uploaded and **never transcribed, never read by the AI interpreter, and never
  shown to an officer.** It cannot influence a category, a score, or a lane. It is write-only.
- It fails on iOS Safari (no `audio/webm;codecs=opus`), so the accessibility argument it
  appears to serve does not hold on a large share of phones.
- It requests microphone permission on a government-facing form, which is a real trust
  cost for zero delivered function.

The genuine accessibility need it gestures at — a user who cannot comfortably type Kannada
— is better served by the icon-and-Kannada category grid in §4, which needs **no typing at
all** for the required fields. If voice returns later it should return as
speech-to-text feeding the interpreter, which is a different feature with a different design.

### 2.3 REWRITE — live files whose structure is wrong

These render today. They are being rewritten because the information architecture is
wrong, not because the CSS is ugly.

| File | Lines | What is wrong |
|---|---:|---|
| `features/officer/OfficerOverviewPage.tsx` | 168 | **Flat list, no wards.** REBUILD_04 §7 requires ward-first. Also uses the superseded vocabulary "Safety review / Operational incidents / Planning needs" instead of the three lanes of §3, and displays **no score, no score components, no SLA deadline, and no agency** — so the priority model is invisible in the one screen that exists to show it. |
| `features/report-intake/ReportPage.tsx` | 163 | **No photo upload** (required); **no category selection** (free text only, so the 12-code closed list of §4.2 is unreachable); **no map or pin** (locality is a text box, placeholder `"e.g. Mahadevapura demo zone"` — not even the JP Nagar / Banashankari target area). Carries the voice recorder from §2.2. **And a real defect:** the submit button is disabled until the `consent` and `synthetic` checkboxes are ticked, but line 85 hardcodes `consent: true, synthetic_demo_confirmation: true` in the payload regardless of that state. The form gates on values it then ignores. |
| `features/home/HomePage.tsx` | 137 | Marketing copy where the ward's actual state should be. See §4. |
| `features/officer/IncidentDetailPage.tsx` | 126 | Must become the group detail view: evidence list, score arithmetic, photo integrity flags, closure action. |
| `features/officer/NeedWorkspacePage.tsx` | 131 | Folds into the group detail view above; the "need" concept does not survive REBUILD_04 §3. |
| `src/styles/global.css` | 106 | Tokens are kept and extended, not discarded (§3). |

### 2.4 KEEP — unchanged

| File / group | Why |
|---|---|
| `src/main.tsx`, `src/app/router.tsx` | Correct entry point and routing. Router gains routes; shape is right. |
| `src/app/shell/AppLayout.tsx` | Already splits public and officer shells at `pathname.startsWith("/officer")`. Extended, not replaced. |
| `src/app/shell/RouteErrorPage.tsx` | Fine. |
| `src/components/ui/*` (15 files) | shadcn/ui primitives on Radix. Sound foundation; no reason to rebuild buttons by hand. |
| `src/components/civic/*` (4 files) | `CivicLogo`, `MetricCard`, `ProvenanceBadge`, `SectionHeading` — the provenance badge in particular is load-bearing for the labelling rule in REBUILD_05. |
| `src/api/health.ts`, `reports.ts`, `officer.ts`, `decisions.ts` | Zod-validated at the boundary, which is the right pattern. `reports.ts` and `officer.ts` extend as the contract grows. |
| `src/features/officer/QueryState.tsx` | Shared loading/error states. |
| `src/features/report-intake/ReceiptPage.tsx` | Restyled only. |
| `src/lib/utils.ts` | The `cn` helper. |

### 2.5 Untracked build artifacts

`apps/web/tsconfig.app.tsbuildinfo`, `tsconfig.node.tsbuildinfo` and
`src/tsconfig.tsbuildinfo` are TypeScript incremental caches. Two of them are **tracked**,
which is why they appear as modified on every build and add noise to every diff. They
should be removed from version control and added to `.gitignore`.

---

## 3. What replaces it

### 3.1 The real cause of "looks like it is under repair"

Worth stating precisely, because the wrong diagnosis leads to the wrong fix. It is not the
colour palette — the live teal/oklch system in `styles/global.css` is defensible and is
being kept. Three concrete causes:

1. **Inconsistent container widths.** The shell uses `max-w-[1440px]`, the officer overview
   `max-w-[1600px]`, the report page `max-w-5xl` (1024px). Header, content, and footer
   therefore do not share an edge, and the content column visibly shifts between routes.
   This is the "gap in left and right" complaint, and it is a three-line fix: one container
   token, used everywhere.
2. **Empty density.** Screens present three or four cards of chrome around very little
   data, because the data the model produces (scores, lanes, wards, deadlines) is not
   surfaced. A page that has nothing to say looks unfinished no matter how it is styled.
3. **Placeholder text in production paths.** `"e.g. Mahadevapura demo zone"` is the wrong
   city area for a Bengaluru South build, and reads as an unfinished form.

### 3.2 Design direction

**Two visual identities, one system.** The shell split already exists; it becomes explicit.

- **Public surface** — built for a citizen in JP Nagar on an inexpensive Android in
  daylight, who may read Kannada more comfortably than English. Base type 18px, minimum
  48px touch targets, WCAG AA contrast throughout, **every category shown as icon +
  Kannada + English**, and no meaning ever carried by colour alone. The required path
  through the form involves no typing.
- **Officer surface** — an instrument, not a brochure. Dark chrome, dense tabular data,
  14px base, numbers right-aligned and tabular-figured, every score expanded into its six
  components on demand.

**Lane colour is reserved.** Red is Lane 1 safety, amber is Lane 2 statutory overdue, teal
is Lane 3 discretionary — and those three colours appear nowhere decoratively. When an
officer sees red, it means one thing.

**Deliberately not the drab-minimal Indian government template, and deliberately not a
generic SaaS dashboard.** The distinguishing move is that the public surface shows the
ward's real state rather than marketing copy: *"Sarakki this week — 12 reported, 4 fixed,
3 past deadline."* No existing Indian civic portal publishes its own backlog. That single
choice does more for legitimacy than any amount of styling, and it is what the priority
model is for.

### 3.3 Order of work

| # | Work | Depends on |
|---|---|---|
| 1 | Container/type/lane tokens in `styles/global.css` | — |
| 2 | `src/api/priority.ts` — Zod contract for groups, scores, lanes, wards | REBUILD_04 §5.6 |
| 3 | Public report page: photo + preview, category grid, location confirm | 1, 2 |
| 4 | Ward-first officer dashboard, three lanes visually separate | 1, 2 |
| 5 | Group detail: evidence, score arithmetic, integrity flags, closure | 4 |
| 6 | Delete everything in §2.1–2.2 | approval of this document |

Step 2 is written **schema-first**: the Zod schemas are the contract the backend must
satisfy, with a single fixture-backed swap point while the endpoints are still being
built. The fixtures live behind that one boundary and are labelled at the point of use, so
they cannot repeat the `mockData.ts` failure of presenting typed numbers as computed ones.

---

## 4. Backend disposition

Out of scope for this pass and listed only so the register is complete. `REBUILD_01`
already covers the decision engine having zero production callers and the officer
dashboard reading a hand-typed JSON file.

| Item | Verdict | Note |
|---|---|---|
| `modules/workflow_reviews/` (untracked) + `src/api/workflowReviews.ts` | **DEFER** | Codex's in-flight work. Not evaluated here; do not delete. |
| `apps/api/.env.backup-before-postgres` | **DELETE** | Local backup from the 2026-09-15 PostgreSQL switch. Git-ignored, but it should not linger on disk — it is a copy of a file holding `GEMINI_API_KEY`. |
| `infra/bootstrap-local-db.sh` | **KEEP** | Untracked; commit it, with its `+x` mode bit. |

---

## 5. Approval

Nothing in §2.1, §2.2, or §4 is removed without Suhas approving this list. The rewrite
work in §3.3 steps 1–5 proceeds first and does not depend on deletion, so the dead files
can sit untouched until then — they are unreachable and cannot affect the running app.
