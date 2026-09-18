/**
 * Development fixtures for endpoints that do not exist yet.
 *
 * ------------------------------------------------------------------------
 * READ THIS BEFORE ADDING ANYTHING HERE.
 *
 * The previous implementation pass shipped `src/data/mockData.ts`: hand-typed
 * priority figures rendered as though the model had computed them. REBUILD_00 §2
 * records that as the central dishonesty of that pass — priority was not
 * computed, it was typed.
 *
 * This file is allowed to exist only because of three constraints that
 * `mockData.ts` did not have:
 *
 *   1. `loadOfficerBoard` and friends try the real endpoint FIRST and only fall
 *      back on a 404. The moment the backend ships, this file stops being used
 *      without a single page changing.
 *   2. Every loader returns `source: "api" | "fixture"`, and the pages render a
 *      visible banner when it is `"fixture"`. A reader of the screen is told.
 *   3. Scores here are computed by `computeFixtureScore` from their components
 *      using the real weights, never typed. `verifyScore` therefore passes on
 *      fixture data for the same reason it passes on real data.
 *
 * Delete this file when /api/v1/officer/board and /api/v1/categories exist.
 * ------------------------------------------------------------------------
 *
 * The geography is real: road and locality names below are what the
 * 2026-09-15 OSM ingest actually resolved for JP Nagar and Banashankari.
 * The reports are synthetic.
 */

import categoryConfigJson from "@config/categories/bengaluru-south-v1.json";

import { ApiError } from "./health";
import {
  COMPONENT_ORDER,
  SCORE_WEIGHTS,
  bandFor,
  categoryConfigSchema,
  fetchCategories,
  fetchOfficerBoard,
  fetchProblemGroup,
  fetchPublicWardBoard,
  fetchWardSummary,
  officerBoardSchema,
  publicWardBoardSchema,
  wardPublicSummarySchema,
  type CategoryConfig,
  type ComponentName,
  type OfficerBoard,
  type ProblemGroup,
  type PublicWardBoard,
  type Score,
  type WardPublicSummary,
  type WardRef,
} from "./priority";

export type Sourced<T> = { data: T; source: "api" | "fixture" };

/** Weighted sum from real weights, so a fixture score is arithmetic, not a guess. */
function computeFixtureScore(components: Record<ComponentName, number>): Score {
  const contributions = {} as Record<ComponentName, number>;
  let total = 0;
  for (const name of COMPONENT_ORDER) {
    const contribution = components[name] * SCORE_WEIGHTS[name];
    contributions[name] = contribution;
    total += contribution;
  }
  return { total, band: bandFor(total), components, contributions };
}

const WARDS = {
  sarakki: {
    id: "loc-sarakki",
    name: "Sarakki",
    provenance: "derived_public" as const,
    // Low, and it must stay low: BSCC's 72 wards have no public boundary set, so
    // these units are derived from OSM localities and are not real wards.
    confidence: "low" as const,
  },
  ittamadu: {
    id: "loc-ittamadu",
    name: "Ittamadu",
    provenance: "derived_public" as const,
    confidence: "low" as const,
  },
  jayanagar: {
    id: "loc-jayanagar-2",
    name: "Jayanagar 2nd Block",
    provenance: "derived_public" as const,
    confidence: "low" as const,
  },
};

type Draft = {
  id: string;
  ref: string;
  code: string;
  lane: ProblemGroup["lane"];
  status: ProblemGroup["status"];
  agency: ProblemGroup["agency"];
  ward: ProblemGroup["ward"];
  road: string | null;
  roadDistance: number | null;
  locality: string;
  first: string;
  last: string;
  /** When an officer claimed it fixed. Null unless `status` is `resolved`. */
  resolvedAt: string | null;
  due: string;
  overdue: number;
  components: Record<ComponentName, number> | null;
  photos: number;
  reporters: number;
  reports: number;
  verified: boolean;
  provisional: boolean;
  gaps: ProblemGroup["evidence"]["gaps"];
  flags: ProblemGroup["flags"];
  summary: string;
};

const DRAFTS: Draft[] = [
  {
    id: "grp-0001",
    ref: "BSC-4821",
    code: "ELECTRICAL_HAZARD",
    lane: "safety",
    status: "open",
    agency: "BESCOM",
    ward: WARDS.sarakki,
    road: "11th Cross Road",
    roadDistance: 4.4,
    locality: "Sarakki",
    first: "2026-09-15T07:42:00+05:30",
    last: "2026-09-15T09:10:00+05:30",
    resolvedAt: null,
    due: "2026-09-16T07:42:00+05:30",
    overdue: 0,
    components: null,
    photos: 2,
    reporters: 2,
    reports: 3,
    verified: false,
    provisional: false,
    gaps: [],
    flags: [],
    summary: "A live wire is hanging low across the footpath near the school gate.",
  },
  {
    id: "grp-0002",
    ref: "BSC-4788",
    code: "SEWAGE_OVERFLOW",
    lane: "safety",
    status: "acknowledged",
    agency: "BWSSB",
    ward: WARDS.ittamadu,
    road: null,
    roadDistance: 14.3,
    locality: "Ittamadu",
    first: "2026-09-14T18:05:00+05:30",
    last: "2026-09-15T06:20:00+05:30",
    resolvedAt: null,
    due: "2026-09-16T18:05:00+05:30",
    overdue: 0,
    components: null,
    photos: 1,
    reporters: 4,
    reports: 6,
    verified: true,
    provisional: false,
    gaps: [],
    flags: ["exif_absent"],
    summary: "Sewage has been overflowing onto the lane for two days.",
  },
  {
    id: "grp-0003",
    ref: "BSC-4612",
    code: "WATER_SUPPLY",
    lane: "statutory",
    status: "in_progress",
    agency: "BWSSB",
    ward: WARDS.sarakki,
    road: "7th Main Road",
    roadDistance: 16.0,
    locality: "Sarakki",
    first: "2026-09-02T08:00:00+05:30",
    last: "2026-09-13T07:30:00+05:30",
    resolvedAt: null,
    due: "2026-09-05T08:00:00+05:30",
    overdue: 10,
    components: null,
    photos: 0,
    reporters: 9,
    reports: 14,
    verified: true,
    provisional: false,
    gaps: ["no_photo"],
    flags: [],
    summary: "No water supply in the lane for eleven mornings.",
  },
  {
    id: "grp-0004",
    ref: "BSC-4655",
    code: "GARBAGE",
    lane: "statutory",
    status: "open",
    agency: "BSCC",
    ward: WARDS.jayanagar,
    road: "30th Main Road",
    roadDistance: 8.1,
    locality: "Jayanagar 2nd Block",
    first: "2026-09-06T07:15:00+05:30",
    last: "2026-09-14T19:40:00+05:30",
    resolvedAt: null,
    due: "2026-09-09T07:15:00+05:30",
    overdue: 6,
    components: null,
    photos: 3,
    reporters: 5,
    reports: 8,
    verified: false,
    provisional: false,
    gaps: [],
    flags: ["photo_reused"],
    summary: "Garbage has not been cleared from the corner for over a week.",
  },
  {
    id: "grp-0005",
    ref: "BSC-4901",
    code: "GARBAGE",
    lane: "discretionary",
    status: "open",
    agency: "BSCC",
    ward: WARDS.sarakki,
    road: "11th Cross Road",
    roadDistance: 6.2,
    locality: "Sarakki",
    first: "2026-09-13T08:30:00+05:30",
    last: "2026-09-15T08:05:00+05:30",
    resolvedAt: null,
    due: "2026-09-16T08:30:00+05:30",
    overdue: 0,
    // The worked example from REBUILD_04 §5.6: garbage beside a hospital.
    // 7.20 + 9.90 + 11.20 + 15.30 + 8.80 + 4.80 = 57.20, Moderate.
    // The severity ceiling of 55 for GARBAGE is what stops hospital proximity
    // promoting a minor category into the High band.
    components: { cs: 30, ps: 55, ex: 70, vu: 85, sv: 55, ng: 60 },
    photos: 2,
    reporters: 3,
    reports: 4,
    verified: false,
    provisional: false,
    gaps: [],
    flags: [],
    summary: "Garbage piling up at the hospital gate on 11th Cross Road.",
  },
  {
    id: "grp-0006",
    ref: "BSC-4877",
    code: "ROAD_DAMAGE",
    lane: "discretionary",
    status: "open",
    agency: "BSCC",
    ward: WARDS.jayanagar,
    road: "30th Main Road",
    roadDistance: 3.5,
    locality: "Jayanagar 2nd Block",
    first: "2026-09-08T17:20:00+05:30",
    last: "2026-09-15T07:55:00+05:30",
    resolvedAt: null,
    due: "2026-09-23T17:20:00+05:30",
    overdue: 0,
    components: { cs: 80, ps: 70, ex: 85, vu: 40, sv: 65, ng: 45 },
    photos: 5,
    reporters: 6,
    reports: 11,
    verified: true,
    provisional: false,
    gaps: [],
    flags: [],
    summary: "A deep pothole on the main road is forcing two-wheelers into oncoming traffic.",
  },
  {
    id: "grp-0007",
    ref: "BSC-4912",
    code: "STREET_LIGHT",
    lane: "discretionary",
    status: "open",
    agency: "BSCC",
    ward: WARDS.ittamadu,
    road: null,
    roadDistance: 11.7,
    locality: "Ittamadu",
    first: "2026-09-14T20:10:00+05:30",
    last: "2026-09-14T20:10:00+05:30",
    resolvedAt: null,
    due: "2026-09-21T20:10:00+05:30",
    overdue: 0,
    // Deliberately thin: one reporter, no photo. Ranked, but capped below High.
    components: { cs: 0, ps: 10, ex: 60, vu: 55, sv: 45, ng: 15 },
    photos: 0,
    reporters: 1,
    reports: 1,
    verified: false,
    provisional: true,
    gaps: ["no_photo", "single_reporter"],
    flags: ["exif_absent"],
    summary: "The street light at the end of the lane has not worked for a few nights.",
  },
  {
    id: "grp-0008",
    ref: "BSC-4703",
    code: "BUS_STOP",
    lane: "discretionary",
    status: "resolved",
    agency: "BMTC",
    ward: WARDS.jayanagar,
    road: "30th Main Road",
    roadDistance: 2.2,
    locality: "Jayanagar 2nd Block",
    first: "2026-09-01T09:00:00+05:30",
    last: "2026-09-04T10:30:00+05:30",
    resolvedAt: "2026-09-10T16:20:00+05:30",
    due: "2026-09-11T09:00:00+05:30",
    overdue: 0,
    components: { cs: 55, ps: 30, ex: 70, vu: 35, sv: 40, ng: 10 },
    photos: 1,
    reporters: 2,
    reports: 2,
    verified: true,
    provisional: false,
    gaps: [],
    flags: [],
    summary: "The bus shelter roof was torn off and has since been replaced.",
  },
  {
    // Closed late. `overdue` stays at 2 and the compensation stays owed, because
    // the work being finished does not undo the fact that the statutory deadline
    // passed first. A prototype that zeroed this on closure would quietly erase
    // the only number a citizen can hold the body to.
    id: "grp-0009",
    ref: "BSC-4590",
    code: "STREET_LIGHT",
    lane: "discretionary",
    status: "resolved",
    agency: "BSCC",
    ward: WARDS.sarakki,
    road: "7th Main Road",
    roadDistance: 9.8,
    locality: "Sarakki",
    first: "2026-09-03T19:45:00+05:30",
    last: "2026-09-05T20:15:00+05:30",
    resolvedAt: "2026-09-12T11:05:00+05:30",
    due: "2026-09-10T19:45:00+05:30",
    overdue: 2,
    components: { cs: 45, ps: 25, ex: 55, vu: 50, sv: 45, ng: 30 },
    photos: 1,
    reporters: 3,
    reports: 4,
    verified: true,
    provisional: false,
    gaps: [],
    flags: [],
    summary: "Three street lights on the stretch were dark; the line has been repaired.",
  },
];

function toGroup(draft: Draft): ProblemGroup {
  return {
    id: draft.id,
    public_ref: draft.ref,
    service_code: draft.code,
    lane: draft.lane,
    status: draft.status,
    agency: draft.agency,
    ward: draft.ward,
    location: {
      road_name: draft.road,
      locality_name: draft.locality,
      road_distance_m: draft.roadDistance,
      provenance: "real_public",
    },
    first_reported_at: draft.first,
    last_reported_at: draft.last,
    resolved_at: draft.resolvedAt,
    score: draft.components ? computeFixtureScore(draft.components) : null,
    sla: {
      due_at: draft.due,
      state: draft.overdue > 0 ? "overdue" : "within",
      days_overdue: draft.overdue,
      // Rs 20 per day overdue, capped at Rs 500.
      compensation_rupees: Math.min(500, draft.overdue * 20),
      paused_days: 0,
    },
    evidence: {
      photo_count: draft.photos,
      distinct_reporter_count: draft.reporters,
      report_count: draft.reports,
      officer_verified: draft.verified,
      provisional: draft.provisional,
      gaps: draft.gaps,
    },
    flags: draft.flags,
    summary: draft.summary,
  };
}

/**
 * The board's own clock.
 *
 * Fixed rather than `Date.now()` so the fixture is deterministic: `10 days
 * overdue` on grp-0003 must stay 10 days overdue, and "fixed in the last 7 days"
 * must keep meaning the same set, whatever day the app is opened. The moment the
 * real endpoint answers, all of this is the server's arithmetic instead.
 */
const GENERATED_AT = "2026-09-15T09:30:00+05:30";
const PUBLIC_WINDOW_DAYS = 7;

const DISCLOSURE =
  "Reports shown here are synthetic. Road and locality names come from OpenStreetMap. Ward units are derived from OSM localities and are not official BSCC wards.";

/** Inclusive lower bound of the public reporting window. */
function windowStart(): number {
  return new Date(GENERATED_AT).getTime() - PUBLIC_WINDOW_DAYS * 86_400_000;
}

/**
 * A ward's backlog over the window.
 *
 * `reported` and `resolved` are windowed; `past_deadline` is not, and that
 * difference is deliberate. Windowing the overdue count would hide the problems
 * that have been overdue longest — exactly the ones a resident most needs to see
 * — so it counts every live problem in the ward whose deadline has passed. The
 * homepage labels each figure with its own period rather than implying one.
 */
function wardBacklog(groups: readonly ProblemGroup[], ward: WardRef) {
  const since = windowStart();
  const inWard = groups.filter((group) => group.ward.id === ward.id);
  const within = (iso: string | null) => iso !== null && new Date(iso).getTime() >= since;
  return {
    ward,
    reported: inWard.filter((group) => within(group.first_reported_at)).length,
    resolved: inWard.filter((group) => within(group.resolved_at)).length,
    past_deadline: inWard.filter(
      (group) => group.status !== "resolved" && group.sla.days_overdue > 0,
    ).length,
  };
}

function buildBoard(): OfficerBoard {
  const groups = DRAFTS.map(toGroup);
  const wards = Object.values(WARDS).map((ward) => {
    const inWard = groups.filter((group) => group.ward.id === ward.id);
    const live = inWard.filter((group) => group.status !== "resolved");
    const scores = live
      .map((group) => group.score?.total)
      .filter((total): total is number => total !== undefined && total !== null);
    const backlog = wardBacklog(groups, ward);
    return {
      ward,
      open_count: live.length,
      safety_count: live.filter((group) => group.lane === "safety").length,
      overdue_count: backlog.past_deadline,
      // The same windowed count the public page shows, from the same helper, so
      // the two surfaces cannot disagree about how much got fixed this week.
      resolved_7d: backlog.resolved,
      top_score: scores.length ? Math.max(...scores) : null,
    };
  });

  return officerBoardSchema.parse({
    generated_at: GENERATED_AT,
    config_version: "bengaluru-south-v1",
    reference_data_as_of: "2026-09-15T00:57:21Z",
    disclosure: DISCLOSURE,
    wards,
    groups,
  });
}

/**
 * Try the real endpoint, fall back to the fixture only on 404.
 *
 * A 500 or a schema mismatch is re-thrown: the point is to work before an
 * endpoint exists, never to paper over one that exists and is broken.
 */
async function withFallback<T>(load: () => Promise<T>, fixture: () => T): Promise<Sourced<T>> {
  try {
    return { data: await load(), source: "api" };
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return { data: fixture(), source: "fixture" };
    }
    throw error;
  }
}

export async function loadOfficerBoard(signal?: AbortSignal): Promise<Sourced<OfficerBoard>> {
  return withFallback(() => fetchOfficerBoard(signal), buildBoard);
}

/**
 * The category fallback is not a fixture in the same sense as the board above:
 * it is the *real* `config/categories/bengaluru-south-v1.json`, the same file
 * `domain/categories.py` loads, imported through the `@config` alias. So the 12
 * codes, their Kannada labels, SLA days and severity ceilings have exactly one
 * definition in this repository. Parsing it through the schema means a change on
 * the backend that the UI cannot handle fails here, loudly.
 */
export async function loadCategories(signal?: AbortSignal): Promise<Sourced<CategoryConfig>> {
  return withFallback(
    () => fetchCategories(signal),
    () => categoryConfigSchema.parse(categoryConfigJson),
  );
}

export async function loadProblemGroup(
  id: string,
  signal?: AbortSignal,
): Promise<Sourced<ProblemGroup>> {
  return withFallback(
    () => fetchProblemGroup(id, signal),
    () => {
      const group = buildBoard().groups.find((item) => item.id === id);
      // A missing id in the fixture is a genuine 404, so it is raised as one
      // rather than substituted with some other group's data.
      if (!group) throw new ApiError(`No problem group ${id}`, 404, null);
      return group;
    },
  );
}

/** Every ward's backlog, for the public homepage. */
export async function loadPublicWardBoard(signal?: AbortSignal): Promise<Sourced<PublicWardBoard>> {
  return withFallback(
    () => fetchPublicWardBoard(signal),
    () => {
      const groups = DRAFTS.map(toGroup);
      return publicWardBoardSchema.parse({
        window_days: PUBLIC_WINDOW_DAYS,
        generated_at: GENERATED_AT,
        disclosure: DISCLOSURE,
        wards: Object.values(WARDS).map((ward) => wardBacklog(groups, ward)),
      });
    },
  );
}

export async function loadWardSummary(
  wardId: string,
  signal?: AbortSignal,
): Promise<Sourced<WardPublicSummary>> {
  return withFallback(
    () => fetchWardSummary(wardId, signal),
    () => {
      const ward = Object.values(WARDS).find((item) => item.id === wardId);
      // Not substituted with another ward's numbers: a resident being shown
      // Ittamadu's backlog under Sarakki's name is worse than an error page.
      if (!ward) throw new ApiError(`No ward ${wardId}`, 404, null);
      return wardPublicSummarySchema.parse({
        ...wardBacklog(DRAFTS.map(toGroup), ward),
        window_days: PUBLIC_WINDOW_DAYS,
        generated_at: GENERATED_AT,
      });
    },
  );
}

export { buildBoard as fixtureOfficerBoard };
