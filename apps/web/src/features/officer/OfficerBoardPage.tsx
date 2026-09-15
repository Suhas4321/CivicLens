import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Clock, FlaskConical, Info, MapPinned, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { loadCategories, loadOfficerBoard } from "@/api/pendingBackend";
import {
  LANE_ORDER,
  groupsInLane,
  resolvedGroups,
  type Category,
  type OfficerBoard,
  type WardBoardEntry,
} from "@/api/priority";
import { formatDateTime, relativeTime } from "@/lib/time";
import { cn } from "@/lib/utils";
import { LaneSection } from "./LaneSection";
import { ErrorState, LoadingState } from "./QueryState";

/**
 * The officer board: wards first, then three separate lanes.
 *
 * Why wards first. The previous version was one flat list of every problem in
 * Bengaluru South. That is not how the work is owned — a ward engineer is
 * accountable for their ward, and a list where their four problems are scattered
 * among two hundred others cannot be acted on. Choosing a ward is therefore the
 * first interaction, and the ward strip is ordered so that the ward needing
 * attention is first: any safety case outranks everything, then days overdue,
 * then the highest triage score.
 *
 * Ward units here are honest about what they are. BSCC was created in September
 * 2025 and public boundary data for its 72 wards may not exist, so these are
 * derived from OpenStreetMap localities and every one of them carries its
 * confidence. An officer is told they are working with a derived approximation
 * rather than being shown a ward name in the same typeface as a legal fact.
 */

export function OfficerBoardPage() {
  const boardQuery = useQuery({
    queryKey: ["officer-board"],
    queryFn: ({ signal }) => loadOfficerBoard(signal),
  });
  const categoriesQuery = useQuery({
    queryKey: ["categories"],
    queryFn: ({ signal }) => loadCategories(signal),
    staleTime: 60 * 60 * 1000,
  });

  const [wardId, setWardId] = useState<string | null>(null);

  if (boardQuery.isPending || categoriesQuery.isPending) {
    return <LoadingState label="Loading the ward board…" />;
  }
  if (boardQuery.isError) return <ErrorState error={boardQuery.error} />;
  if (categoriesQuery.isError) return <ErrorState error={categoriesQuery.error} />;

  const board = boardQuery.data.data;
  const categories = categoriesQuery.data.data.categories;
  const usingFixture = boardQuery.data.source === "fixture";

  const wards = [...board.wards].sort(rankWards);
  const selected = wardId ? wards.find((entry) => entry.ward.id === wardId) : undefined;

  const totals = {
    open: wards.reduce((sum, entry) => sum + entry.open_count, 0),
    safety: wards.reduce((sum, entry) => sum + entry.safety_count, 0),
    overdue: wards.reduce((sum, entry) => sum + entry.overdue_count, 0),
    resolved: wards.reduce((sum, entry) => sum + entry.resolved_7d, 0),
  };

  return (
    <div className="page-shell py-6">
      <header>
        <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
          <div>
            <h1 className="text-2xl font-semibold tracking-[-0.02em] text-slate-950">
              Ward board · Bengaluru South
            </h1>
            <p className="mt-1 text-sm text-slate-600">
              Three lanes, never mixed. Safety is never scored, statutory order is the law, and
              every discretionary rank opens into its arithmetic.
            </p>
          </div>
          <dl className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-slate-500">
            <Stat label="Generated" value={formatDateTime(board.generated_at)} />
            <Stat label="Policy" value={board.config_version} />
            {board.reference_data_as_of ? (
              <Stat label="Map data" value={formatDateTime(board.reference_data_as_of)} />
            ) : null}
          </dl>
        </div>

        {/* Where the numbers came from. This is a standing disclosure, not an
          * error state, and it is deliberately above the data rather than in a
          * footer nobody reads. */}
        {usingFixture ? (
          <p className="mt-4 flex items-start gap-2 rounded-lg border border-lane-statutory-border bg-lane-statutory-surface px-3 py-2.5 text-xs leading-5 text-lane-statutory-ink">
            <FlaskConical className="mt-0.5 size-4 shrink-0" aria-hidden />
            <span>
              <strong className="font-semibold">
                /api/v1/officer/board does not exist yet, so this board is local development
                fixture data.
              </strong>{" "}
              Scores below are computed from their components using the real weights, not typed in
              — but the problems themselves are invented. This banner disappears by itself the
              moment the endpoint responds.
            </span>
          </p>
        ) : null}

        <p className="mt-2 flex items-start gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs leading-5 text-slate-600">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>{board.disclosure}</span>
        </p>
      </header>

      <section aria-label="Wards" className="mt-6">
        <div className="flex items-center justify-between gap-4">
          <h2 className="text-sm font-semibold uppercase tracking-[0.08em] text-slate-500">
            Wards
          </h2>
          <p className="text-xs text-slate-500">
            Ordered by safety cases, then days overdue, then top score
          </p>
        </div>

        <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <button
            type="button"
            onClick={() => setWardId(null)}
            aria-pressed={wardId === null}
            className={cn(
              "rounded-xl border-2 bg-white p-3.5 text-left transition hover:border-slate-300",
              wardId === null ? "border-slate-900" : "border-slate-200",
            )}
          >
            <p className="flex items-center gap-1.5 text-sm font-semibold text-slate-950">
              <MapPinned className="size-4 text-slate-500" aria-hidden />
              All wards
            </p>
            <p className="numeric mt-2 text-2xl font-semibold text-slate-950">{totals.open}</p>
            <p className="text-xs text-slate-500">open problems</p>
            <WardCounts
              safety={totals.safety}
              overdue={totals.overdue}
              resolved={totals.resolved}
            />
          </button>

          {wards.map((entry) => {
            const active = wardId === entry.ward.id;
            return (
              <button
                key={entry.ward.id}
                type="button"
                onClick={() => setWardId(active ? null : entry.ward.id)}
                aria-pressed={active}
                className={cn(
                  "rounded-xl border-2 bg-white p-3.5 text-left transition hover:border-slate-300",
                  active ? "border-slate-900" : "border-slate-200",
                  entry.safety_count > 0 && !active && "border-lane-safety-border",
                )}
              >
                <p className="flex items-center justify-between gap-2 text-sm font-semibold text-slate-950">
                  <span className="truncate">{entry.ward.name}</span>
                  <span
                    className="shrink-0 rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-500"
                    title={`Ward geography is ${entry.ward.provenance.replaceAll("_", " ")} with ${entry.ward.confidence} confidence. These are OSM localities, not official BSCC wards.`}
                  >
                    {entry.ward.confidence} conf.
                  </span>
                </p>
                <p className="numeric mt-2 text-2xl font-semibold text-slate-950">
                  {entry.open_count}
                </p>
                <p className="text-xs text-slate-500">open problems</p>
                <WardCounts
                  safety={entry.safety_count}
                  overdue={entry.overdue_count}
                  resolved={entry.resolved_7d}
                />
              </button>
            );
          })}
        </div>
      </section>

      <div className="mt-7 space-y-5">
        {selected ? (
          <p className="text-sm text-slate-600">
            Showing <strong className="font-semibold text-slate-950">{selected.ward.name}</strong>{" "}
            only.{" "}
            <button
              type="button"
              onClick={() => setWardId(null)}
              className="font-medium text-lane-discretionary underline"
            >
              Show all wards
            </button>
          </p>
        ) : null}

        {LANE_ORDER.map((lane) => (
          <LaneSection
            key={lane}
            lane={lane}
            groups={groupsInLane(board, lane, wardId ?? undefined)}
            categories={categories}
          />
        ))}

        <ResolvedList board={board} wardId={wardId} categories={categories} />
      </div>
    </div>
  );
}

/**
 * Closed work, kept visible.
 *
 * Resolved groups are out of the lanes — a work queue containing finished work is
 * just a longer queue. But they are not hidden either: a closure is a claim that
 * citizens can dispute, so an officer needs to see what has been claimed as fixed
 * in their ward, and a portal that quietly deletes its completed work cannot
 * credibly publish a "fixed this week" number.
 */
function ResolvedList({
  board,
  wardId,
  categories,
}: {
  board: OfficerBoard;
  wardId: string | null;
  categories: readonly Category[];
}) {
  const resolved = resolvedGroups(board, wardId ?? undefined);
  if (resolved.length === 0) return null;

  return (
    <section aria-labelledby="lane-resolved">
      <div className="rounded-t-xl border border-b-0 border-slate-200 bg-slate-50 px-4 py-3">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h2 id="lane-resolved" className="text-base font-semibold text-slate-700">
            Marked resolved
            <span className="ml-2 font-normal text-slate-500">ಪರಿಹಾರವಾಗಿದೆ</span>
          </h2>
          <p className="numeric text-sm font-medium text-slate-500">
            {resolved.length} {resolved.length === 1 ? "problem" : "problems"}
          </p>
        </div>
        <p className="mt-1 text-xs leading-5 text-slate-500">
          Out of the lanes, not out of the record. Reporters can dispute a closure, which resumes
          the statutory clock where it paused.
        </p>
      </div>
      <ul className="divide-y divide-slate-200 rounded-b-xl border border-slate-200 bg-white">
        {resolved.map((group) => {
          const category = categories.find((item) => item.code === group.service_code);
          return (
            <li key={group.id}>
              <Link
                to={`/officer/problems/${group.id}`}
                className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2.5 text-sm no-underline transition hover:bg-slate-50"
              >
                <CheckCircle2 className="size-4 shrink-0 text-slate-400" aria-hidden />
                <span className="numeric text-xs font-semibold text-slate-500">
                  {group.public_ref}
                </span>
                <span className="font-medium text-slate-950">
                  {category?.label_en ?? group.service_code}
                </span>
                <span className="truncate text-slate-500">
                  {group.location.road_name ?? group.location.locality_name ?? "—"}
                </span>
                {/* When it was closed, not when it was last reported — the
                  * closure is the event this list is about. */}
                <span className="ml-auto text-xs text-slate-500">
                  {group.resolved_at
                    ? `closed ${relativeTime(group.resolved_at)}`
                    : "closure date missing"}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/**
 * Ward ordering.
 *
 * Safety first, unconditionally — a ward with a live hazard is the ward to look
 * at regardless of how tidy its other numbers are. Then statutory overdue count,
 * because that is a legal obligation rather than a judgment. Only then the
 * highest triage score, which is the only term here that is discretionary.
 */
function rankWards(a: WardBoardEntry, b: WardBoardEntry): number {
  if (a.safety_count !== b.safety_count) return b.safety_count - a.safety_count;
  if (a.overdue_count !== b.overdue_count) return b.overdue_count - a.overdue_count;
  return (b.top_score ?? -1) - (a.top_score ?? -1);
}

function WardCounts({
  safety,
  overdue,
  resolved,
}: {
  safety: number;
  overdue: number;
  resolved: number;
}) {
  return (
    <ul className="mt-2.5 flex flex-wrap gap-x-3 gap-y-1 text-xs">
      <li
        className={cn(
          "inline-flex items-center gap-1",
          safety > 0 ? "font-semibold text-lane-safety" : "text-slate-400",
        )}
      >
        <TriangleAlert className="size-3.5" aria-hidden />
        <span className="numeric">{safety}</span> safety
      </li>
      <li
        className={cn(
          "inline-flex items-center gap-1",
          overdue > 0 ? "font-semibold text-lane-statutory-ink" : "text-slate-400",
        )}
      >
        <Clock className="size-3.5" aria-hidden />
        <span className="numeric">{overdue}</span> overdue
      </li>
      <li className="inline-flex items-center gap-1 text-slate-500">
        <CheckCircle2 className="size-3.5" aria-hidden />
        <span className="numeric">{resolved}</span> fixed
      </li>
    </ul>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="uppercase tracking-[0.08em] text-slate-400">{label}</dt>
      <dd className="numeric mt-0.5 font-medium text-slate-700">{value}</dd>
    </div>
  );
}
