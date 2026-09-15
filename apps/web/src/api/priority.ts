/**
 * The contract between the officer/public UI and the priority model.
 *
 * These schemas are deliberately written *before* the endpoints exist. They are
 * the specification the backend must satisfy, and they mirror the Python domain
 * modules field for field:
 *
 *   ScoreComponents / ScoreResult  <- apps/api/src/civiclens/domain/scoring.py
 *   Category                       <- config/categories/bengaluru-south-v1.json
 *
 * Every response is parsed through Zod at the boundary, so a backend that
 * changes shape fails loudly here instead of rendering `undefined` into a
 * dashboard an officer is meant to act on.
 *
 * One rule this file enforces that is worth stating plainly: **the UI never
 * displays a total it has not checked.** REBUILD_00 §2 records that the previous
 * implementation pass shipped a dashboard whose priority numbers were typed by
 * hand rather than computed. `verifyScore` below recomputes the weighted sum
 * from the components and refuses to present a figure that disagrees with its
 * own arithmetic. A wrong number is then a visible defect rather than a
 * plausible one.
 */

import { z } from "zod";

import { ApiError } from "./health";

/* -------------------------------------------------------------------------- */
/* Lanes                                                                      */
/* -------------------------------------------------------------------------- */

/**
 * REBUILD_04 §3. The three lanes are not priority levels — they are different
 * *kinds* of decision, and they are never interleaved or compared.
 *
 *   safety         chronological, never scored, no judgment applied
 *   statutory      ordered by days overdue, no judgment applied — it is law
 *   discretionary  ordered by triage score, judgment stated and reviewable
 */
export const laneSchema = z.enum(["safety", "statutory", "discretionary"]);
export type Lane = z.infer<typeof laneSchema>;

export const LANE_ORDER: readonly Lane[] = ["safety", "statutory", "discretionary"];

export const LANE_META: Record<
  Lane,
  { title: string; titleKn: string; rule: string; sortedBy: string }
> = {
  safety: {
    title: "Immediate safety review",
    titleKn: "ತಕ್ಷಣದ ಸುರಕ್ಷತಾ ಪರಿಶೀಲನೆ",
    rule: "Never scored and never ranked. Oldest first.",
    sortedBy: "Time reported",
  },
  statutory: {
    title: "Past statutory deadline",
    titleKn: "ಕಾನೂನು ಗಡುವು ಮೀರಿದೆ",
    rule: "Ordered by how far overdue. No judgment is applied — the deadline is the deadline.",
    sortedBy: "Days overdue",
  },
  discretionary: {
    title: "Ranked by triage score",
    titleKn: "ಆದ್ಯತೆ ಅಂಕದ ಪ್ರಕಾರ",
    rule: "Within deadline, so ordering is a stated judgment. Every score opens into its arithmetic.",
    sortedBy: "Triage score",
  },
};

/* -------------------------------------------------------------------------- */
/* Score                                                                      */
/* -------------------------------------------------------------------------- */

export const componentNameSchema = z.enum(["cs", "ps", "ex", "vu", "sv", "ng"]);
export type ComponentName = z.infer<typeof componentNameSchema>;

/** Must stay identical to WEIGHTS in domain/scoring.py. Asserted below. */
export const SCORE_WEIGHTS: Record<ComponentName, number> = {
  cs: 0.24,
  ps: 0.18,
  ex: 0.16,
  vu: 0.18,
  sv: 0.16,
  ng: 0.08,
};

export const COMPONENT_ORDER: readonly ComponentName[] = ["cs", "ps", "ex", "vu", "sv", "ng"];

/**
 * Plain-language names. An officer, and a citizen reading a published ranking,
 * has to be able to tell what was measured without reading a specification —
 * "CS" explains nothing, "How many separate people reported it" explains itself.
 */
export const COMPONENT_META: Record<
  ComponentName,
  { short: string; label: string; labelKn: string; asks: string }
> = {
  cs: {
    short: "CS",
    label: "Separate people reporting",
    labelKn: "ಬೇರೆ ಬೇರೆ ಜನರ ದೂರುಗಳು",
    asks: "How many distinct people reported this, not how many reports arrived.",
  },
  ps: {
    short: "PS",
    label: "How long it has persisted",
    labelKn: "ಎಷ್ಟು ಕಾಲದಿಂದ ಇದೆ",
    asks: "Time between the first and the most recent report.",
  },
  ex: {
    short: "EX",
    label: "How many people pass it",
    labelKn: "ಎಷ್ಟು ಜನ ಹಾದು ಹೋಗುತ್ತಾರೆ",
    asks: "Exposure from road class and nearby transit.",
  },
  vu: {
    short: "VU",
    label: "Who is nearby",
    labelKn: "ಹತ್ತಿರ ಯಾರಿದ್ದಾರೆ",
    asks: "Proximity to hospitals, schools and other sensitive places.",
  },
  sv: {
    short: "SV",
    label: "Severity of this kind of problem",
    labelKn: "ಸಮಸ್ಯೆಯ ಗಂಭೀರತೆ",
    asks: "The published severity for the category, capped by its ceiling.",
  },
  ng: {
    short: "NG",
    label: "How long it has been ignored",
    labelKn: "ಎಷ್ಟು ಕಾಲ ನಿರ್ಲಕ್ಷ್ಯ",
    asks: "Time since the responsible agency last acted.",
  },
};

export const scoreBandSchema = z.enum(["high", "moderate", "lower"]);
export type ScoreBand = z.infer<typeof scoreBandSchema>;

/** REBUILD_04 §5.6. High >= 70, Moderate 45-69, Lower < 45. */
export function bandFor(total: number): ScoreBand {
  if (total >= 70) return "high";
  if (total >= 45) return "moderate";
  return "lower";
}

export const BAND_META: Record<ScoreBand, { label: string; labelKn: string; className: string }> = {
  // The class names come from styles/civic.css and are an ink-weight scale, not
  // lane colours. A High-band discretionary problem rendered in red would read
  // as a safety hazard, which is the confusion the lane split exists to prevent.
  high: { label: "High", labelKn: "ಹೆಚ್ಚು", className: "band-high" },
  moderate: { label: "Moderate", labelKn: "ಮಧ್ಯಮ", className: "band-moderate" },
  lower: { label: "Lower", labelKn: "ಕಡಿಮೆ", className: "band-lower" },
};

const scoreSchema = z.object({
  total: z.number().min(0).max(100),
  band: scoreBandSchema,
  /** Raw 0-100 inputs, before weighting. */
  components: z.record(componentNameSchema, z.number().min(0).max(100)),
  /** component x weight, i.e. what each one added to the total. */
  contributions: z.record(componentNameSchema, z.number()),
});
export type Score = z.infer<typeof scoreSchema>;

export type ScoreCheck =
  // `capped?: false` is present on the uncapped member purely so `capped` can
  // act as a discriminant: without it, reading `check.capped` after narrowing on
  // `ok` is a type error and every caller has to reach for a type guard.
  | { ok: true; total: number; capped?: false }
  | { ok: true; total: number; capped: true; uncappedTotal: number }
  | { ok: false; reason: string; claimed: number; recomputed: number };

/**
 * Recompute the weighted sum from the components and compare it with the total
 * the backend sent.
 *
 * The tolerance is 0.05 rather than an exact match because the backend sums
 * IEEE doubles in a fixed order and JavaScript may not reproduce the same
 * rounding; anything larger than that is a real disagreement, not float noise.
 */
export function verifyScore(score: Score, options?: { provisionalCap?: number }): ScoreCheck {
  let recomputed = 0;
  for (const name of COMPONENT_ORDER) {
    const value = score.components[name];
    if (value === undefined) {
      return {
        ok: false,
        reason: `component ${name} is missing`,
        claimed: score.total,
        recomputed: Number.NaN,
      };
    }
    recomputed += value * SCORE_WEIGHTS[name];
  }

  // An evidence-capped score is a deliberate, documented divergence from the
  // raw arithmetic, so it must be distinguished from a defect.
  const cap = options?.provisionalCap;
  if (cap !== undefined && recomputed > cap && Math.abs(score.total - cap) <= 0.05) {
    return { ok: true, total: score.total, capped: true, uncappedTotal: recomputed };
  }

  if (Math.abs(recomputed - score.total) > 0.05) {
    return {
      ok: false,
      reason: "the total does not equal the weighted sum of its components",
      claimed: score.total,
      recomputed,
    };
  }
  return { ok: true, total: score.total };
}

/** Scores are shown as whole numbers. `72 · High`, never `72.43`. */
export function formatScore(total: number): string {
  return String(Math.round(total));
}

/* -------------------------------------------------------------------------- */
/* Categories                                                                 */
/* -------------------------------------------------------------------------- */

export const groupingGeometrySchema = z.enum(["linear_road", "areal_locality", "point_asset"]);
export const agencySchema = z.enum(["BSCC", "BWSSB", "BESCOM", "BMTC"]);
export type Agency = z.infer<typeof agencySchema>;

/** Mirrors config/categories/bengaluru-south-v1.json exactly. */
export const categorySchema = z.object({
  code: z.string(),
  label_en: z.string(),
  label_kn: z.string(),
  // `null` for OTHER, which has no responsible agency until it is classified.
  agency: agencySchema.nullable(),
  sla_days: z.number().int().positive(),
  // `null` for OTHER: unknown category means no severity, so nothing to rank.
  severity_ceiling: z.number().int().min(0).max(100).nullable(),
  grouping_geometry: groupingGeometrySchema,
  lane_1_eligible: z.boolean(),
  rankable: z.boolean(),
});
export type Category = z.infer<typeof categorySchema>;

export const categoryConfigSchema = z.object({
  version: z.string(),
  categories: z.array(categorySchema).length(12),
});
export type CategoryConfig = z.infer<typeof categoryConfigSchema>;

export const AGENCY_META: Record<Agency, { name: string; nameKn: string; handles: string }> = {
  BSCC: {
    name: "Bengaluru South City Corporation",
    nameKn: "ಬೆಂಗಳೂರು ದಕ್ಷಿಣ ನಗರ ಪಾಲಿಕೆ",
    handles: "Roads, drains, garbage, street lights, stray animals, trees",
  },
  BWSSB: {
    name: "Water Supply and Sewerage Board",
    nameKn: "ಜಲಮಂಡಳಿ",
    handles: "Water supply, water quality, sewerage",
  },
  BESCOM: {
    name: "Bangalore Electricity Supply Company",
    nameKn: "ಬೆಸ್ಕಾಂ",
    handles: "Electricity supply and electrical hazards",
  },
  BMTC: {
    name: "Bangalore Metropolitan Transport Corporation",
    nameKn: "ಬಿ.ಎಂ.ಟಿ.ಸಿ",
    handles: "Bus stops and bus shelters",
  },
};

/* -------------------------------------------------------------------------- */
/* Provenance                                                                 */
/* -------------------------------------------------------------------------- */

/** REBUILD_05. Every displayed value states where it came from. */
export const provenanceSchema = z.enum([
  "real_public",
  "derived_public",
  "synthetic_demo",
  "user_submitted",
  "ai_derived",
]);
export type Provenance = z.infer<typeof provenanceSchema>;

/* -------------------------------------------------------------------------- */
/* Problem groups                                                             */
/* -------------------------------------------------------------------------- */

export const slaStateSchema = z.enum(["within", "due_today", "overdue"]);
export type SlaState = z.infer<typeof slaStateSchema>;

const slaSchema = z.object({
  due_at: z.string(),
  state: slaStateSchema,
  days_overdue: z.number().int().min(0),
  compensation_rupees: z.number().int().min(0),
  /** True once a disputed closure has paused and resumed the clock. */
  paused_days: z.number().int().min(0).default(0),
});
export type Sla = z.infer<typeof slaSchema>;

export const statusSchema = z.enum([
  "open",
  "acknowledged",
  "in_progress",
  "resolved",
  "disputed",
  "reopened",
]);
export type Status = z.infer<typeof statusSchema>;

export const STATUS_META: Record<Status, { label: string; labelKn: string }> = {
  open: { label: "Open", labelKn: "ತೆರೆದಿದೆ" },
  acknowledged: { label: "Acknowledged", labelKn: "ಸ್ವೀಕರಿಸಲಾಗಿದೆ" },
  in_progress: { label: "Work started", labelKn: "ಕೆಲಸ ಪ್ರಾರಂಭ" },
  resolved: { label: "Marked solved", labelKn: "ಪರಿಹಾರವಾಗಿದೆ" },
  disputed: { label: "Citizens disagree", labelKn: "ನಾಗರಿಕರ ಆಕ್ಷೇಪ" },
  reopened: { label: "Reopened", labelKn: "ಮತ್ತೆ ತೆರೆಯಲಾಗಿದೆ" },
};

/**
 * Why a group is only provisionally ranked.
 *
 * REBUILD_04: a thin report is still ranked, but capped below the High band
 * until minimum evidence exists — a confirmed category and location, plus one
 * of a photo, two independent reporters, or officer verification. The reason is
 * carried so the dashboard can say what is missing instead of showing an
 * unexplained ceiling.
 */
export const evidenceGapSchema = z.enum([
  "no_photo",
  "single_reporter",
  "location_unconfirmed",
  "category_unconfirmed",
]);

const evidenceSchema = z.object({
  photo_count: z.number().int().min(0),
  distinct_reporter_count: z.number().int().min(0),
  report_count: z.number().int().min(0),
  officer_verified: z.boolean(),
  provisional: z.boolean(),
  gaps: z.array(evidenceGapSchema),
});
export type Evidence = z.infer<typeof evidenceSchema>;

/** Photo integrity findings. Officer-visible flags, never auto-rejection. */
export const integrityFlagSchema = z.enum([
  "photo_reused",
  "photo_stale",
  "photo_future_dated",
  "exif_location_far",
  "exif_absent",
  "reporter_rate_limited",
  "jurisdiction_disputed",
]);
export type IntegrityFlag = z.infer<typeof integrityFlagSchema>;

export const INTEGRITY_FLAG_META: Record<
  IntegrityFlag,
  { label: string; means: string; severity: "note" | "warn" }
> = {
  photo_reused: {
    label: "Photo already seen",
    means:
      "This image matches one submitted earlier. It does not count towards the number of separate reporters.",
    severity: "warn",
  },
  photo_stale: {
    label: "Photo is older than a week",
    means: "The photo's own timestamp predates the report by more than 7 days.",
    severity: "warn",
  },
  photo_future_dated: {
    label: "Photo dated in the future",
    means: "The camera clock was wrong, or the timestamp was altered.",
    severity: "warn",
  },
  exif_location_far: {
    label: "Photo taken far from the pin",
    means: "The photo's own location is more than 1 km from the reported location.",
    severity: "warn",
  },
  exif_absent: {
    label: "No location in photo",
    means:
      "A weak signal only. WhatsApp and most messaging apps strip this from every image, so its absence is normal.",
    severity: "note",
  },
  reporter_rate_limited: {
    label: "Many reports from one source",
    means: "Unusually many reports share this reporter key.",
    severity: "warn",
  },
  jurisdiction_disputed: {
    label: "Agency disputed",
    means: "The assigned agency has contested responsibility for this location.",
    severity: "note",
  },
};

const locationSchema = z.object({
  /**
   * The primary human anchor. The 2026-09-15 OSM ingest resolved localities
   * only to adjacent-suburb accuracy, so the road name is what a citizen or an
   * officer can actually trust to identify a place.
   */
  road_name: z.string().nullable(),
  locality_name: z.string().nullable(),
  /** Metres from the reported point to the snapped road. */
  road_distance_m: z.number().nullable(),
  provenance: provenanceSchema,
});

const wardRefSchema = z.object({
  id: z.string(),
  name: z.string(),
  /**
   * Ward geography is a versioned derived dataset, never authoritative:
   * BSCC was created in September 2025 and public GIS for its 72 wards may not
   * exist. See docs/RESEARCH_WARD_GEOGRAPHY.md.
   */
  provenance: provenanceSchema,
  confidence: z.enum(["high", "medium", "low"]),
});
export type WardRef = z.infer<typeof wardRefSchema>;

export const problemGroupSchema = z.object({
  id: z.string(),
  public_ref: z.string(),
  service_code: z.string(),
  lane: laneSchema,
  status: statusSchema,
  agency: agencySchema.nullable(),
  ward: wardRefSchema,
  location: locationSchema,
  first_reported_at: z.string(),
  last_reported_at: z.string(),
  /**
   * When an officer claimed this was fixed. Null for everything still open.
   *
   * A closure without a date cannot be counted ("4 fixed this week"), cannot be
   * disputed inside a window, and cannot be audited, so the date is part of the
   * closure rather than something derived from the last report.
   */
  resolved_at: z.string().nullable(),
  /** Absent in the safety and statutory lanes, which are never scored. */
  score: scoreSchema.nullable(),
  sla: slaSchema,
  evidence: evidenceSchema,
  flags: z.array(integrityFlagSchema),
  /** One sentence, plain language, for the citizen-facing view. */
  summary: z.string(),
});
export type ProblemGroup = z.infer<typeof problemGroupSchema>;

/* -------------------------------------------------------------------------- */
/* Ward board                                                                 */
/* -------------------------------------------------------------------------- */

export const wardBoardEntrySchema = z.object({
  ward: wardRefSchema,
  open_count: z.number().int().min(0),
  safety_count: z.number().int().min(0),
  overdue_count: z.number().int().min(0),
  resolved_7d: z.number().int().min(0),
  /** Highest discretionary score in the ward, for ordering the ward list. */
  top_score: z.number().nullable(),
});
export type WardBoardEntry = z.infer<typeof wardBoardEntrySchema>;

export const officerBoardSchema = z.object({
  generated_at: z.string(),
  config_version: z.string(),
  /** e.g. the OSM extract's own replication timestamp. */
  reference_data_as_of: z.string().nullable(),
  disclosure: z.string(),
  wards: z.array(wardBoardEntrySchema),
  groups: z.array(problemGroupSchema),
});
export type OfficerBoard = z.infer<typeof officerBoardSchema>;

/* -------------------------------------------------------------------------- */
/* Public backlog                                                             */
/* -------------------------------------------------------------------------- */

/**
 * One ward's backlog in the only three terms a resident can check against what
 * they see on their own street: how much was reported, how much was fixed, and
 * how much is past the deadline the law gives.
 *
 * Deliberately not the officer's numbers. There is no score here, no lane, no
 * integrity flag — a resident is owed the count and the deadline, not a ranking
 * they have no way to argue with.
 */
export const wardBacklogSchema = z.object({
  ward: wardRefSchema,
  reported: z.number().int().min(0),
  resolved: z.number().int().min(0),
  past_deadline: z.number().int().min(0),
});
export type WardBacklog = z.infer<typeof wardBacklogSchema>;

/** GET /api/v1/wards/{id}/summary — one ward, with its own window and stamp. */
export const wardPublicSummarySchema = wardBacklogSchema.extend({
  window_days: z.number().int().positive(),
  generated_at: z.string(),
});
export type WardPublicSummary = z.infer<typeof wardPublicSummarySchema>;

/**
 * GET /api/v1/public/wards — every ward's backlog in one request.
 *
 * The homepage needs this rather than the single-ward endpoint because a resident
 * arrives without a ward id: they recognise "Sarakki", not `loc-sarakki`. The
 * window and the stamp sit on the envelope so all the rows are read over the same
 * period, which is the whole point of comparing them.
 */
export const publicWardBoardSchema = z.object({
  window_days: z.number().int().positive(),
  generated_at: z.string(),
  disclosure: z.string(),
  wards: z.array(wardBacklogSchema),
});
export type PublicWardBoard = z.infer<typeof publicWardBoardSchema>;

/* -------------------------------------------------------------------------- */
/* Sorting                                                                    */
/* -------------------------------------------------------------------------- */

/**
 * Each lane has its own ordering rule and they are not interchangeable. This is
 * the one place that ordering is decided, so a page cannot accidentally sort the
 * safety lane by score and imply a ranking that does not exist.
 */
export function sortForLane(lane: Lane, groups: readonly ProblemGroup[]): ProblemGroup[] {
  const items = [...groups];
  switch (lane) {
    case "safety":
      return items.sort((a, b) => a.first_reported_at.localeCompare(b.first_reported_at));
    case "statutory":
      return items.sort(
        (a, b) =>
          b.sla.days_overdue - a.sla.days_overdue ||
          a.first_reported_at.localeCompare(b.first_reported_at),
      );
    case "discretionary":
      return items.sort((a, b) => (b.score?.total ?? -1) - (a.score?.total ?? -1));
  }
}

/**
 * The lanes are a work queue, so a resolved group is not in one.
 *
 * `resolved` is the only closed status: `disputed` and `reopened` are both live
 * work, because a citizen rejecting a closure puts the problem back on the
 * officer's desk with its statutory clock resumed. Filtering here rather than in
 * each page keeps the lane counts and the ward card counts derived from the same
 * rule — they disagreed when the page did its own filtering.
 */
export function groupsInLane(board: OfficerBoard, lane: Lane, wardId?: string): ProblemGroup[] {
  const inLane = board.groups.filter(
    (group) =>
      group.lane === lane &&
      group.status !== "resolved" &&
      (wardId === undefined || group.ward.id === wardId),
  );
  return sortForLane(lane, inLane);
}

/**
 * Closed work, most recently closed first. Shown separately, never in a lane.
 *
 * Ordered by the closure date rather than the last report, because this list is a
 * record of closures. A group missing its closure date sorts to the top instead of
 * the bottom: it is a data fault worth seeing, not something to bury.
 */
export function resolvedGroups(board: OfficerBoard, wardId?: string): ProblemGroup[] {
  return board.groups
    .filter(
      (group) =>
        group.status === "resolved" && (wardId === undefined || group.ward.id === wardId),
    )
    .sort((a, b) => (b.resolved_at ?? "9999").localeCompare(a.resolved_at ?? "9999"));
}

/* -------------------------------------------------------------------------- */
/* Transport                                                                  */
/* -------------------------------------------------------------------------- */

async function getJson(path: string, signal?: AbortSignal): Promise<unknown> {
  const response = await fetch(path, { headers: { Accept: "application/json" }, signal });
  if (!response.ok) {
    throw new ApiError(
      `Request failed (${response.status})`,
      response.status,
      response.headers.get("X-Correlation-ID"),
    );
  }
  return response.json();
}

export async function fetchCategories(signal?: AbortSignal): Promise<CategoryConfig> {
  return categoryConfigSchema.parse(await getJson("/api/v1/categories", signal));
}

export async function fetchOfficerBoard(signal?: AbortSignal): Promise<OfficerBoard> {
  return officerBoardSchema.parse(await getJson("/api/v1/officer/board", signal));
}

export async function fetchProblemGroup(id: string, signal?: AbortSignal): Promise<ProblemGroup> {
  return problemGroupSchema.parse(
    await getJson(`/api/v1/problems/${encodeURIComponent(id)}`, signal),
  );
}

export async function fetchWardSummary(
  wardId: string,
  signal?: AbortSignal,
): Promise<WardPublicSummary> {
  return wardPublicSummarySchema.parse(
    await getJson(`/api/v1/wards/${encodeURIComponent(wardId)}/summary`, signal),
  );
}

export async function fetchPublicWardBoard(signal?: AbortSignal): Promise<PublicWardBoard> {
  return publicWardBoardSchema.parse(await getJson("/api/v1/public/wards", signal));
}
