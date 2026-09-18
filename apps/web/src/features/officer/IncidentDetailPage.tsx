import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CalendarDays, CheckCircle2, FileText, GitMerge, MapPin, ShieldCheck, UsersRound } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ProvenanceBadge } from "@/components/civic/ProvenanceBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { fetchIncidentDetail } from "../../api/officer";
import {
  fetchWorkflowReviews,
  recordWorkflowReview,
  type ReviewAction,
} from "../../api/workflowReviews";
import { ErrorState, LoadingState } from "./QueryState";

export function IncidentDetailPage() {
  const { id = "" } = useParams();
  const queryClient = useQueryClient();
  const [action, setAction] = useState<ReviewAction>("keep_separate");
  const [reason, setReason] = useState("Available evidence does not yet support a broader relationship.");
  const query = useQuery({ queryKey: ["officer", "incident", id], queryFn: ({ signal }) => fetchIncidentDetail(id, signal), enabled: Boolean(id) });
  const isFresh = query.data?.data_version === "fresh-analysis-v1";
  const isSafety = query.data?.incident.relationship_state === "pending_safety_verification";
  const reviewQuery = useQuery({
    queryKey: ["officer", "report-review", id],
    queryFn: () => fetchWorkflowReviews(id),
    enabled: Boolean(id && isFresh),
  });
  const reviewMutation = useMutation({
    mutationFn: () => recordWorkflowReview(id, {
      action,
      reason,
      expected_version: reviewQuery.data?.at(-1)?.entity_version_after ?? 1,
    }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["officer", "report-review", id] });
    },
  });

  useEffect(() => {
    if (isSafety) {
      setAction("verify_safety");
      setReason("The count-independent safety signal requires human verification.");
    }
  }, [isSafety]);

  function submitReview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    reviewMutation.mutate();
  }

  if (query.isPending) return <LoadingState label="Loading incident evidence…" />;
  if (query.isError) return <ErrorState error={query.error} />;

  const { incident, reports, relationship_explanation: gates, decision_boundary: boundary } = query.data;

  return (
    <div className="mx-auto w-full max-w-[1500px] px-4 py-7 sm:px-6 lg:px-8 lg:py-9">
      <Button asChild variant="ghost" className="-ml-2 mb-5 text-slate-600"><Link to="/officer"><ArrowLeft /> Back to queues</Link></Button>
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-3xl">
          <div className="flex flex-wrap items-center gap-2"><ProvenanceBadge classification="synthetic_demo" /><Badge variant="outline" className="rounded-full capitalize">{incident.relationship_state.replaceAll("_", " ")}</Badge></div>
          <p className="mt-5 text-xs font-bold uppercase tracking-[0.14em] text-teal-700">Incident cluster</p>
          <h1 className="mt-2 text-balance text-3xl font-semibold tracking-[-0.045em] text-slate-950 sm:text-4xl">{incident.title}</h1>
          <p className="mt-3 text-sm leading-6 text-slate-600">{boundary}</p>
        </div>
        <div className="grid grid-cols-3 gap-2 sm:gap-3">
          <div className="min-w-24 rounded-xl bg-white p-3 ring-1 ring-slate-200"><UsersRound className="size-4 text-teal-700" /><strong className="mt-3 block text-xl text-slate-950">{incident.report_count}</strong><span className="text-[11px] text-slate-500">reports</span></div>
          <div className="min-w-24 rounded-xl bg-white p-3 ring-1 ring-slate-200"><CalendarDays className="size-4 text-teal-700" /><strong className="mt-3 block text-sm text-slate-950">{new Date(incident.event_start).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</strong><span className="text-[11px] text-slate-500">event start</span></div>
          <div className="min-w-24 rounded-xl bg-white p-3 ring-1 ring-slate-200"><MapPin className="size-4 text-teal-700" /><strong className="mt-3 block max-w-28 truncate text-sm text-slate-950">{incident.locality}</strong><span className="text-[11px] text-slate-500">locality</span></div>
        </div>
      </div>

      <div className="mt-8 grid gap-6 xl:grid-cols-[340px_minmax(0,1fr)] xl:items-start">
        <div className="space-y-6 xl:sticky xl:top-24">
        <Card className="gap-0 border-0 bg-white py-0 shadow-sm ring-slate-200">
          <CardHeader className="border-b border-slate-200 p-5"><div className="flex items-center gap-3"><span className="grid size-9 place-items-center rounded-lg bg-teal-50 text-teal-700"><GitMerge className="size-4" /></span><div><CardTitle>Grouping evidence</CardTitle><p className="mt-0.5 text-xs text-slate-500">Rules used to suggest this cluster</p></div></div></CardHeader>
          <CardContent className="p-5"><dl className="space-y-4">{Object.entries(gates).map(([key, value], index) => <div key={key}>{index ? <Separator className="mb-4" /> : null}<dt className="text-xs font-medium capitalize text-slate-500">{key.replaceAll("_", " ")}</dt><dd className="mt-1 text-left text-sm font-semibold text-slate-900">{String(value)}</dd></div>)}</dl></CardContent>
        </Card>
        {isFresh ? (
          <Card className="gap-0 border-0 bg-white py-0 shadow-sm ring-slate-200">
            <CardHeader className="border-b border-slate-200 p-5"><div className="flex items-center gap-3"><span className="grid size-9 place-items-center rounded-lg bg-teal-50 text-teal-700"><ShieldCheck className="size-4" /></span><div><CardTitle>Human review</CardTitle><p className="mt-0.5 text-xs text-slate-500">Append-only demo action</p></div></div></CardHeader>
            <CardContent className="p-5">
              <form className="space-y-4" onSubmit={submitReview}>
                <div className="space-y-2">
                  <Label htmlFor="workflow-action">Review outcome</Label>
                  <select id="workflow-action" value={action} onChange={(event) => setAction(event.target.value as ReviewAction)} className="h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm">
                    {isSafety ? <><option value="verify_safety">Verification required</option><option value="refer_safety">Refer safety signal</option><option value="dismiss_safety">Dismiss unsupported signal</option></> : <><option value="keep_separate">Keep as separate report</option><option value="confirm_bounded_incident">Confirm bounded incident</option></>}
                  </select>
                </div>
                <div className="space-y-2"><Label htmlFor="workflow-reason">Reason</Label><Textarea id="workflow-reason" required minLength={8} maxLength={600} value={reason} onChange={(event) => setReason(event.target.value)} /></div>
                <Button type="submit" className="w-full" disabled={reviewMutation.isPending}>{reviewMutation.isPending ? "Recording…" : "Record review"}</Button>
                {reviewMutation.isError ? <p className="text-xs font-medium text-rose-700">The review was not recorded. Refresh and try again.</p> : null}
                {reviewMutation.isSuccess ? <p className="flex items-center gap-2 text-xs font-medium text-emerald-700"><CheckCircle2 className="size-4" /> Review recorded.</p> : null}
              </form>
              {reviewQuery.data?.length ? <div className="mt-5 border-t border-slate-200 pt-4"><p className="text-xs font-semibold text-slate-700">History</p><div className="mt-2 space-y-2">{reviewQuery.data.map((review) => <div key={review.id} className="rounded-lg bg-slate-50 p-3"><p className="text-xs font-semibold capitalize text-slate-900">{review.action.replaceAll("_", " ")}</p><p className="mt-1 text-xs leading-5 text-slate-600">{review.reason}</p></div>)}</div></div> : null}
            </CardContent>
          </Card>
        ) : null}
        </div>

        <Card className="gap-0 border-0 bg-white py-0 shadow-sm ring-slate-200">
          <CardHeader className="border-b border-slate-200 p-5 sm:p-6"><div className="flex items-center justify-between gap-4"><div><CardTitle className="text-lg">Underlying reports</CardTitle><p className="mt-1 text-sm text-slate-500">Citizen claims included in this reviewable cluster.</p></div><Badge variant="secondary" className="rounded-full">{reports.length} total</Badge></div></CardHeader>
          <CardContent className="p-0">
            <div className="divide-y divide-slate-200">
              {reports.map((report) => (
                <article key={report.id} className="p-5 sm:p-6">
                  <div className="flex flex-wrap items-center justify-between gap-3"><div className="flex flex-wrap items-center gap-2"><ProvenanceBadge classification="synthetic_demo" /><Badge variant="outline" className="rounded-full uppercase">{report.language}</Badge></div><time className="text-xs text-slate-500">{new Date(report.accepted_at).toLocaleString()}</time></div>
                  <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_280px]">
                    <div className="flex gap-3"><FileText className="mt-1 size-4 shrink-0 text-slate-400" /><blockquote lang={report.language} className="text-[15px] leading-7 text-slate-800">“{report.original_text}”</blockquote></div>
                    <div className="rounded-xl bg-violet-50 p-4"><div className="flex items-center justify-between gap-2"><p className="text-xs font-semibold text-violet-900">Interpreted summary</p><ProvenanceBadge classification="ai_derived" /></div><p className="mt-2 text-xs leading-5 text-violet-800">{report.interpretation_summary}</p></div>
                  </div>
                </article>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
