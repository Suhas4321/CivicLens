import { ArrowRight, Camera, Clock, TriangleAlert, Users } from "lucide-react";
import { Link } from "react-router-dom";

import {
  AGENCY_META,
  INTEGRITY_FLAG_META,
  LANE_META,
  STATUS_META,
  type Category,
  type Lane,
  type ProblemGroup,
} from "@/api/priority";
import { formatDateTime, relativeTime } from "@/lib/time";
import { cn } from "@/lib/utils";
import { ScoreBadge } from "./Score";

/**
 * One lane, rendered as its own block.
 *
 * The three lanes are never interleaved and never sorted by a shared key. That
 * is the central design commitment of this product, so it is expressed
 * structurally: each lane is a separate section with its own heading, its own
 * stated ordering rule, and its own right-hand column showing the fact it is
 * actually ordered by — time for safety, days overdue for statutory, the triage
 * score for discretionary.
 *
 * A flat list sorted by one number would let a scored judgment outrank a live
 * electrical hazard, or let a hazard appear to have been "ranked" at all. Neither
 * is allowed to be expressible here.
 */

const LANE_RAIL: Record<Lane, string> = {
  safety: "text-lane-safety",
  statutory: "text-lane-statutory",
  discretionary: "text-lane-discretionary",
};

const LANE_HEADER: Record<Lane, string> = {
  safety: "border-lane-safety-border bg-lane-safety-surface text-lane-safety-ink",
  statutory: "border-lane-statutory-border bg-lane-statutory-surface text-lane-statutory-ink",
  discretionary:
    "border-lane-discretionary-border bg-lane-discretionary-surface text-lane-discretionary-ink",
};

export function LaneSection({
  lane,
  groups,
  categories,
}: {
  lane: Lane;
  groups: readonly ProblemGroup[];
  categories: readonly Category[];
}) {
  const meta = LANE_META[lane];

  return (
    <section aria-labelledby={`lane-${lane}`}>
      <div className={cn("rounded-t-xl border border-b-0 px-4 py-3", LANE_HEADER[lane])}>
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h2 id={`lane-${lane}`} className="text-base font-semibold">
            {meta.title}
            <span className="ml-2 font-normal opacity-70">{meta.titleKn}</span>
          </h2>
          <p className="numeric text-sm font-medium">
            {groups.length} {groups.length === 1 ? "problem" : "problems"} · ordered by{" "}
            {meta.sortedBy.toLowerCase()}
          </p>
        </div>
        <p className="mt-1 text-xs leading-5 opacity-90">{meta.rule}</p>
      </div>

      {groups.length === 0 ? (
        <p className="rounded-b-xl border border-slate-200 bg-white px-4 py-6 text-center text-sm text-slate-500">
          Nothing in this lane.
        </p>
      ) : (
        <ul className="divide-y divide-slate-200 rounded-b-xl border border-slate-200 bg-white">
          {groups.map((group) => (
            <li key={group.id}>
              <GroupRow lane={lane} group={group} categories={categories} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function GroupRow({
  lane,
  group,
  categories,
}: {
  lane: Lane;
  group: ProblemGroup;
  categories: readonly Category[];
}) {
  const category = categories.find((item) => item.code === group.service_code);
  const warnFlags = group.flags.filter((flag) => INTEGRITY_FLAG_META[flag].severity === "warn");

  return (
    <Link
      to={`/officer/problems/${group.id}`}
      className={cn(
        "lane-rail grid gap-x-4 gap-y-2 px-4 py-3 no-underline transition hover:bg-slate-50",
        "md:grid-cols-[minmax(0,1fr)_11rem_9rem]",
        LANE_RAIL[lane],
      )}
    >
      <div className="min-w-0 text-slate-950">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="numeric text-xs font-semibold text-slate-500">{group.public_ref}</span>
          <span className="text-sm font-semibold">
            {category?.label_en ?? group.service_code}
          </span>
          {category ? (
            <span className="text-xs text-slate-500">{category.label_kn}</span>
          ) : null}
          <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-600">
            {STATUS_META[group.status].label}
          </span>
        </div>

        {/* Road name first: OSM locality resolution is only accurate to the
          * adjacent suburb, so the road is the anchor an officer can trust. */}
        <p className="mt-1 truncate text-sm text-slate-700">
          {group.location.road_name ?? "Road not identified"}
          {group.location.locality_name ? (
            <span className="text-slate-500"> · {group.location.locality_name}</span>
          ) : null}
        </p>

        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
          <span className="inline-flex items-center gap-1">
            <Users className="size-3.5" aria-hidden />
            <span className="numeric">{group.evidence.distinct_reporter_count}</span>
            {group.evidence.distinct_reporter_count === 1 ? "reporter" : "reporters"}
          </span>
          <span className="inline-flex items-center gap-1">
            <Camera className="size-3.5" aria-hidden />
            <span className="numeric">{group.evidence.photo_count}</span>
            {group.evidence.photo_count === 1 ? "photo" : "photos"}
          </span>
          {group.agency ? (
            <span title={AGENCY_META[group.agency].name} className="font-medium text-slate-600">
              {group.agency}
            </span>
          ) : (
            <span className="font-medium text-slate-600">Unrouted</span>
          )}
          {warnFlags.length > 0 ? (
            <span
              className="inline-flex items-center gap-1 font-medium text-lane-statutory-ink"
              title={warnFlags.map((flag) => INTEGRITY_FLAG_META[flag].label).join(" · ")}
            >
              <TriangleAlert className="size-3.5" aria-hidden />
              {warnFlags.length} {warnFlags.length === 1 ? "flag" : "flags"}
            </span>
          ) : null}
        </div>
      </div>

      <div className="text-sm text-slate-700 md:text-right">
        <LaneFact lane={lane} group={group} />
      </div>

      <div className="flex items-center justify-between gap-2 md:justify-end">
        <ScoreBadge score={group.score} provisional={group.evidence.provisional} />
        <ArrowRight className="hidden size-4 shrink-0 text-slate-400 md:block" aria-hidden />
      </div>
    </Link>
  );
}

/** The fact the lane is ordered by, shown in the lane it orders. */
function LaneFact({ lane, group }: { lane: Lane; group: ProblemGroup }) {
  if (lane === "safety") {
    return (
      <span className="inline-flex items-center gap-1.5">
        <Clock className="size-3.5 text-slate-400" aria-hidden />
        <span title={formatDateTime(group.first_reported_at)}>
          reported {relativeTime(group.first_reported_at)}
        </span>
      </span>
    );
  }

  if (lane === "statutory") {
    return (
      <span>
        <span className="numeric block font-semibold text-lane-statutory-ink">
          {group.sla.days_overdue} {group.sla.days_overdue === 1 ? "day" : "days"} overdue
        </span>
        <span className="numeric mt-0.5 block text-xs text-slate-500">
          ₹{group.sla.compensation_rupees} owed
          {group.sla.paused_days > 0 ? ` · ${group.sla.paused_days}d paused` : ""}
        </span>
      </span>
    );
  }

  return (
    <span>
      <span className="block text-xs text-slate-500">due</span>
      <span className="numeric block">{formatDateTime(group.sla.due_at)}</span>
    </span>
  );
}
