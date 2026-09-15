import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  Camera,
  CheckCircle2,
  Clock,
  Info,
  MapPin,
  ShieldAlert,
  TriangleAlert,
  Users,
} from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { loadCategories, loadProblemGroup } from "@/api/pendingBackend";
import {
  AGENCY_META,
  INTEGRITY_FLAG_META,
  LANE_META,
  STATUS_META,
  type Evidence,
  type ProblemGroup,
} from "@/api/priority";
import { Button } from "@/components/ui/button";
import { formatDateTime, relativeTime } from "@/lib/time";
import { cn } from "@/lib/utils";
import { ErrorState, LoadingState } from "./QueryState";
import { ScoreArithmetic, ScoreBadge } from "./Score";

/**
 * One problem group, in full.
 *
 * This page has one job: make a ranking arguable. An officer should be able to
 * read it and either agree, or point at the exact input they think is wrong.
 * So it shows, in order: which lane this is in and why that lane's ordering rule
 * applies; the statutory clock; the evidence actually held; every integrity flag
 * with what it means; and — only for the discretionary lane — the score opened
 * up into component × weight = contribution.
 *
 * Safety and statutory groups show no score at all, because they have none.
 * Inventing one for display would imply these lanes are ranked, which is exactly
 * the claim the three-lane design refuses to make.
 */

const EVIDENCE_GAP_TEXT: Record<Evidence["gaps"][number], string> = {
  no_photo: "No photo, so severity cannot be judged from the desk.",
  single_reporter: "One reporter only, so corroboration is absent.",
  location_unconfirmed: "The location has not been confirmed against a road or asset.",
  category_unconfirmed: "The category is the reporter's own choice and has not been reviewed.",
};

export function ProblemDetailPage() {
  const { id = "" } = useParams();

  const groupQuery = useQuery({
    queryKey: ["problem-group", id],
    queryFn: ({ signal }) => loadProblemGroup(id, signal),
    enabled: id.length > 0,
  });
  const categoriesQuery = useQuery({
    queryKey: ["categories"],
    queryFn: ({ signal }) => loadCategories(signal),
    staleTime: 60 * 60 * 1000,
  });

  if (groupQuery.isPending || categoriesQuery.isPending) {
    return <LoadingState label="Opening the problem…" />;
  }
  if (groupQuery.isError) return <ErrorState error={groupQuery.error} />;
  if (categoriesQuery.isError) return <ErrorState error={categoriesQuery.error} />;

  const group = groupQuery.data.data;
  const category = categoriesQuery.data.data.categories.find(
    (item) => item.code === group.service_code,
  );
  const lane = LANE_META[group.lane];

  return (
    <div className="page-shell py-6">
      <Link
        to="/officer"
        className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 no-underline hover:text-slate-950"
      >
        <ArrowLeft className="size-4" aria-hidden /> Ward board
      </Link>

      <header className="mt-4 flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <p className="numeric text-xs font-semibold uppercase tracking-[0.1em] text-slate-500">
            {group.public_ref}
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-[-0.02em] text-slate-950">
            {category?.label_en ?? group.service_code}
          </h1>
          <p className="mt-0.5 text-base text-slate-600">{category?.label_kn}</p>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-700">{group.summary}</p>
        </div>
        <div className="flex flex-col items-start gap-2 sm:items-end">
          <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">
            {STATUS_META[group.status].label} · {STATUS_META[group.status].labelKn}
          </span>
          <ScoreBadge score={group.score} provisional={group.evidence.provisional} />
        </div>
      </header>

      {/* Why this sits where it sits in the queue. */}
      <p
        className={cn(
          "mt-5 flex items-start gap-2 rounded-lg border px-3 py-2.5 text-sm leading-6",
          group.lane === "safety" &&
            "border-lane-safety-border bg-lane-safety-surface text-lane-safety-ink",
          group.lane === "statutory" &&
            "border-lane-statutory-border bg-lane-statutory-surface text-lane-statutory-ink",
          group.lane === "discretionary" &&
            "border-lane-discretionary-border bg-lane-discretionary-surface text-lane-discretionary-ink",
        )}
      >
        {group.lane === "safety" ? (
          <ShieldAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
        ) : group.lane === "statutory" ? (
          <Clock className="mt-0.5 size-4 shrink-0" aria-hidden />
        ) : (
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
        )}
        <span>
          <strong className="font-semibold">{lane.title}.</strong> {lane.rule}
        </span>
      </p>

      <div className="mt-6 grid gap-5 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-start">
        <div className="min-w-0 space-y-5">
          <Panel title="Where">
            <dl className="space-y-3 text-sm">
              <Field label="Road">
                <span className="font-medium text-slate-950">
                  {group.location.road_name ?? "Not identified"}
                </span>
                {group.location.road_distance_m !== null ? (
                  <span className="numeric mt-0.5 block text-xs text-slate-500">
                    {group.location.road_distance_m.toFixed(1)} m from the reported point
                  </span>
                ) : null}
              </Field>
              <Field label="Locality">
                <span className="text-slate-950">{group.location.locality_name ?? "—"}</span>
                {/* Stated once, plainly, at the point of use. */}
                <span className="mt-0.5 block text-xs text-slate-500">
                  OpenStreetMap resolves localities only to the adjacent suburb, so treat the road
                  as the reliable anchor.
                </span>
              </Field>
              <Field label="Ward">
                <span className="text-slate-950">{group.ward.name}</span>
                <span className="mt-0.5 block text-xs text-slate-500">
                  {group.ward.provenance.replaceAll("_", " ")} · {group.ward.confidence} confidence
                  · derived from OSM localities, not an official BSCC ward
                </span>
              </Field>
            </dl>
          </Panel>

          <Panel title="Evidence held">
            <div className="grid grid-cols-3 gap-3">
              <Metric
                icon={Users}
                value={group.evidence.distinct_reporter_count}
                label="separate reporters"
              />
              <Metric icon={Camera} value={group.evidence.photo_count} label="photos" />
              <Metric icon={Info} value={group.evidence.report_count} label="reports received" />
            </div>

            <p className="mt-3 text-xs leading-5 text-slate-500">
              Separate reporters, not reports. Ten reports from one person are one voice, and a
              photo already seen elsewhere does not add a reporter.
            </p>

            {group.evidence.officer_verified ? (
              <p className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-lane-discretionary-ink">
                <CheckCircle2 className="size-4" aria-hidden /> Verified by an officer
              </p>
            ) : null}

            {group.evidence.gaps.length > 0 ? (
              <ul className="mt-3 space-y-1.5 border-t border-slate-200 pt-3">
                {group.evidence.gaps.map((gap) => (
                  <li key={gap} className="flex items-start gap-2 text-xs leading-5 text-slate-600">
                    <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-slate-400" />
                    {EVIDENCE_GAP_TEXT[gap]}
                  </li>
                ))}
              </ul>
            ) : null}

            {group.evidence.provisional ? (
              <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-600">
                Labelled <strong className="font-semibold">Provisional</strong>. It is still
                ranked — thin evidence is not a reason to ignore a problem — but it is held below
                the High band until there is a photo, a second independent reporter, or an officer
                verification.
              </p>
            ) : null}
          </Panel>

          {group.score ? (
            <Panel title="How this rank was reached">
              <ScoreArithmetic score={group.score} provisional={group.evidence.provisional} />
              {category?.severity_ceiling !== null && category?.severity_ceiling !== undefined ? (
                <p className="mt-3 text-xs leading-5 text-slate-600">
                  The severity input for {category.label_en} is capped at{" "}
                  <span className="numeric font-semibold">{category.severity_ceiling}</span>. That
                  is what stops a minor category next to a hospital from outranking a genuinely
                  severe problem elsewhere.
                </p>
              ) : null}
            </Panel>
          ) : (
            <Panel title="How this rank was reached">
              <p className="text-sm leading-6 text-slate-600">
                This group is not scored, and that is deliberate.{" "}
                {group.lane === "safety"
                  ? "Life-safety problems are handled oldest-first and are never ranked against each other — a scoring model has no business deciding which live wire waits."
                  : "Once a statutory deadline has passed, the ordering is how far overdue it is. That is a legal fact, not a judgment, so no score is applied."}
              </p>
            </Panel>
          )}
        </div>

        <aside className="space-y-5">
          <Panel title="Statutory clock">
            <dl className="space-y-3 text-sm">
              <Field label="First reported">
                <span className="numeric text-slate-950">
                  {formatDateTime(group.first_reported_at)}
                </span>
                <span className="mt-0.5 block text-xs text-slate-500">
                  {relativeTime(group.first_reported_at)} · the clock runs from the group's first
                  report, not from when it was noticed here
                </span>
              </Field>
              <Field label="Latest report">
                <span className="numeric text-slate-950">
                  {formatDateTime(group.last_reported_at)}
                </span>
              </Field>
              <Field label="Due">
                <span className="numeric text-slate-950">{formatDateTime(group.sla.due_at)}</span>
                {category ? (
                  <span className="numeric mt-0.5 block text-xs text-slate-500">
                    {category.sla_days} calendar {category.sla_days === 1 ? "day" : "days"}, Asia/Kolkata
                  </span>
                ) : null}
              </Field>
              {group.sla.days_overdue > 0 ? (
                <Field label="Overdue">
                  <span className="numeric font-semibold text-lane-statutory-ink">
                    {group.sla.days_overdue} {group.sla.days_overdue === 1 ? "day" : "days"}
                  </span>
                  <span className="numeric mt-0.5 block text-xs text-slate-500">
                    ₹{group.sla.compensation_rupees} compensation accrued at ₹20/day, capped at ₹500
                  </span>
                </Field>
              ) : null}
              {group.sla.paused_days > 0 ? (
                <Field label="Paused">
                  <span className="numeric text-slate-950">{group.sla.paused_days} days</span>
                  <span className="mt-0.5 block text-xs text-slate-500">
                    A disputed closure resumes the clock where it paused; it does not restart it.
                  </span>
                </Field>
              ) : null}
              {group.resolved_at ? (
                <Field label="Closed">
                  <span className="numeric text-slate-950">
                    {formatDateTime(group.resolved_at)}
                  </span>
                  <span className="mt-0.5 block text-xs text-slate-500">
                    {group.sla.days_overdue > 0
                      ? "Closed after the deadline had passed. The compensation above stays owed — finishing the work does not undo the delay."
                      : "Closed within the deadline."}
                  </span>
                </Field>
              ) : null}
            </dl>
          </Panel>

          <Panel title="Routing">
            {group.agency ? (
              <>
                <p className="font-medium text-slate-950">{AGENCY_META[group.agency].name}</p>
                <p className="mt-0.5 text-sm text-slate-600">
                  {AGENCY_META[group.agency].nameKn}
                </p>
                <p className="mt-2 text-xs leading-5 text-slate-500">
                  {AGENCY_META[group.agency].handles}
                </p>
              </>
            ) : (
              <p className="text-sm leading-6 text-slate-600">
                Not routed. This category has no fixed agency, so an officer has to assign it.
              </p>
            )}
          </Panel>

          <Panel title="Integrity checks">
            {group.flags.length === 0 ? (
              <p className="text-sm text-slate-600">Nothing flagged.</p>
            ) : (
              <ul className="space-y-2.5">
                {group.flags.map((flag) => {
                  const meta = INTEGRITY_FLAG_META[flag];
                  return (
                    <li key={flag} className="text-sm">
                      <p
                        className={cn(
                          "inline-flex items-center gap-1.5 font-medium",
                          meta.severity === "warn"
                            ? "text-lane-statutory-ink"
                            : "text-slate-700",
                        )}
                      >
                        {meta.severity === "warn" ? (
                          <TriangleAlert className="size-3.5" aria-hidden />
                        ) : (
                          <Info className="size-3.5" aria-hidden />
                        )}
                        {meta.label}
                      </p>
                      <p className="mt-0.5 text-xs leading-5 text-slate-600">{meta.means}</p>
                    </li>
                  );
                })}
              </ul>
            )}
            <p className="mt-3 border-t border-slate-200 pt-3 text-xs leading-5 text-slate-500">
              These are notes for a human, never automatic rejection. A flagged report can still be
              entirely genuine.
            </p>
          </Panel>

          <ClosurePanel group={group} />
        </aside>
      </div>
    </div>
  );
}

/**
 * The closure loop.
 *
 * The actions are laid out and disabled, with the reason stated, because
 * `POST /api/v1/problems/:id/status` does not exist yet. A button that looks
 * live and silently does nothing is the failure mode this rebuild exists to
 * remove, so the control is honest about being inert instead.
 */
function ClosurePanel({ group }: { group: ProblemGroup }) {
  const [note, setNote] = useState("");

  if (group.status === "resolved") {
    return (
      <Panel title="Close the loop">
        <p className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-800">
          <CheckCircle2 className="size-4 text-emerald-600" aria-hidden /> Claimed fixed
          {group.resolved_at ? ` on ${formatDateTime(group.resolved_at)}` : ""}
        </p>
        <p className="mt-2 text-xs leading-5 text-slate-600">
          The reporters can still dispute this. A dispute is raised from the citizen's receipt, not
          from here, and it resumes the statutory clock where it paused.
        </p>
      </Panel>
    );
  }

  return (
    <Panel title="Close the loop">
      <p className="text-xs leading-5 text-slate-600">
        A closure is a claim, and the citizens who reported it can dispute it. If they do, the
        statutory clock resumes where it paused rather than starting again.
      </p>

      <label className="mt-3 block">
        <span className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
          What was done
        </span>
        <textarea
          value={note}
          onChange={(event) => setNote(event.target.value)}
          rows={3}
          maxLength={600}
          placeholder="e.g. Pole replaced and line re-tensioned; site cleared."
          className="mt-1.5 w-full resize-y rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm leading-6 focus-visible:border-lane-discretionary focus-visible:outline-none"
        />
      </label>

      <div className="mt-3 flex flex-wrap gap-2">
        <Button type="button" disabled className="text-sm">
          Mark resolved
        </Button>
        <Button type="button" variant="outline" disabled className="text-sm">
          Acknowledge
        </Button>
      </div>

      <p className="mt-2.5 flex items-start gap-2 text-xs leading-5 text-slate-500">
        <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
        <span>
          Disabled because <code className="font-mono">POST /api/v1/problems/{group.id}/status</code>{" "}
          is not implemented. Nothing here writes anything yet, and it says so rather than
          pretending.
        </span>
      </p>
    </Panel>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <h2 className="text-sm font-semibold uppercase tracking-[0.08em] text-slate-500">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-0.5 sm:grid-cols-[7rem_minmax(0,1fr)] sm:gap-3">
      <dt className="text-xs font-medium uppercase tracking-[0.06em] text-slate-400">{label}</dt>
      <dd className="min-w-0">{children}</dd>
    </div>
  );
}

function Metric({
  icon: Icon,
  value,
  label,
}: {
  icon: typeof Users;
  value: number;
  label: string;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
      <Icon className="size-4 text-slate-400" aria-hidden />
      <p className="numeric mt-1.5 text-xl font-semibold text-slate-950">{value}</p>
      <p className="text-xs leading-4 text-slate-500">{label}</p>
    </div>
  );
}
