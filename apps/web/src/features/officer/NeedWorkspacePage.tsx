import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Check, CheckCircle2, CircleHelp, ClipboardCheck, ExternalLink, FileSearch, GitBranch, History, Info, Layers3, Scale } from "lucide-react";
import { type FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ProvenanceBadge } from "@/components/civic/ProvenanceBadge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { fetchDecisionHistory, recordDecision, type DecisionPayload } from "../../api/decisions";
import { fetchNeedWorkspace } from "../../api/officer";
import { ErrorState, LoadingState } from "./QueryState";

export function NeedWorkspacePage() {
  const { id = "" } = useParams();
  const queryClient = useQueryClient();
  const [disposition, setDisposition] = useState<DecisionPayload["disposition"]>("refer");
  const [reasonText, setReasonText] = useState("");
  const [nextStep, setNextStep] = useState("Refer for focused field and service verification; record findings and works overlap.");
  const [nextReviewDate, setNextReviewDate] = useState("");
  const query = useQuery({ queryKey: ["officer", "need", id], queryFn: ({ signal }) => fetchNeedWorkspace(id, signal), enabled: Boolean(id) });
  const historyQuery = useQuery({ queryKey: ["officer", "need", id, "decisions"], queryFn: () => fetchDecisionHistory(id), enabled: Boolean(id), retry: false });
  const mutation = useMutation({ mutationFn: (payload: DecisionPayload) => recordDecision(id, payload), onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["officer", "need", id, "decisions"] }) });

  if (query.isPending) return <LoadingState label="Assembling need evidence…" />;
  if (query.isError) return <ErrorState error={query.error} />;

  const workspace = query.data;
  const history = historyQuery.data ?? [];
  const expectedVersion = history.at(-1)?.entity_version_after ?? 1;

  function submitDecision(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const reasonCode: DecisionPayload["reason_code"] = disposition === "refer" ? "FIELD_VERIFICATION" : disposition === "defer" ? "EVIDENCE_GAP" : "NOT_SUPPORTED";
    mutation.mutate({ disposition, reason_code: reasonCode, reason_text: reasonText || null, next_step: disposition === "refer" ? nextStep : null, next_review_date: disposition === "defer" ? nextReviewDate : null, expected_entity_version: expectedVersion });
  }

  return (
    <div className="mx-auto w-full max-w-[1600px] px-4 py-7 sm:px-6 lg:px-8 lg:py-9">
      <Button asChild variant="ghost" className="-ml-2 mb-5 text-slate-600"><Link to="/officer"><ArrowLeft /> Back to queues</Link></Button>

      <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-4xl">
          <div className="flex flex-wrap items-center gap-2"><Badge className="rounded-full bg-amber-100 text-amber-900 hover:bg-amber-100">{workspace.hypothesis_label}</Badge><ProvenanceBadge classification="synthetic_demo" /><span className="text-xs text-slate-500">{workspace.need.geography}</span></div>
          <h1 className="mt-4 text-balance text-3xl font-semibold tracking-[-0.045em] text-slate-950 sm:text-4xl lg:text-5xl">{workspace.need.title}</h1>
          <p className="mt-4 max-w-3xl text-base leading-7 text-slate-600">{workspace.hypothesis}</p>
        </div>
        <Card className="w-full gap-0 border-0 bg-[#12363a] py-0 text-white ring-0 lg:w-72">
          <CardContent className="flex items-center justify-between p-5 lg:block">
            <div><p className="text-xs font-semibold uppercase tracking-[0.12em] text-teal-200">Planning priority</p><strong className="mt-2 block text-3xl capitalize tracking-tight">{workspace.priority.band}</strong></div>
            <div className="text-right lg:mt-5 lg:text-left"><p className="text-xs text-slate-300">Sensitivity</p><p className="mt-1 text-sm font-medium capitalize text-white">{workspace.priority.sensitivity_status}</p></div>
          </CardContent>
        </Card>
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px] lg:items-start">
        <div className="min-w-0 space-y-6">
          <Card className="gap-0 border-0 bg-gradient-to-br from-teal-700 to-[#12363a] py-0 text-white shadow-lg shadow-teal-950/10 ring-0">
            <CardContent className="grid gap-6 p-6 sm:p-7 2xl:grid-cols-[1fr_280px]">
              <div><p className="text-xs font-semibold uppercase tracking-[0.14em] text-teal-200">Conditional project candidate</p><h2 className="mt-3 text-balance text-2xl font-semibold tracking-[-0.035em] sm:text-3xl">{workspace.candidate.conditional_wording}</h2><p className="mt-3 max-w-2xl text-sm leading-6 text-teal-50/80">{workspace.candidate.decision_boundary}</p></div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-4"><p className="text-xs font-semibold text-teal-100">Readiness checks</p><div className="mt-3 space-y-2.5">{workspace.candidate.prerequisites.map((item) => <div key={item.code} className="flex items-center gap-2 text-xs"><span className={`grid size-5 place-items-center rounded-full ${item.state === "satisfied" ? "bg-emerald-300/20 text-emerald-200" : "bg-white/10 text-slate-300"}`}>{item.state === "satisfied" ? <Check className="size-3" /> : <CircleHelp className="size-3" />}</span><span className="flex-1 capitalize text-slate-200">{item.code.replaceAll("_", " ")}</span><span className="capitalize text-slate-400">{item.state}</span></div>)}</div><Separator className="my-3 bg-white/10" /><p className="text-xs text-slate-300">Works overlap: <strong className="capitalize text-white">{workspace.candidate.works_overlap_outcome}</strong></p></div>
            </CardContent>
          </Card>

          <Tabs defaultValue="evidence" className="gap-5">
            <TabsList className="h-10 w-full justify-start overflow-x-auto rounded-xl border border-slate-200 bg-white p-1 sm:w-fit">
              <TabsTrigger value="evidence" className="px-3"><FileSearch /> Evidence</TabsTrigger>
              <TabsTrigger value="priority" className="px-3"><Scale /> Priority</TabsTrigger>
              <TabsTrigger value="incidents" className="px-3"><GitBranch /> Incidents</TabsTrigger>
            </TabsList>

            <TabsContent value="evidence">
              <Card className="gap-0 border-0 bg-white py-0 shadow-sm ring-slate-200">
                <CardHeader className="border-b border-slate-200 p-5 sm:p-6"><CardTitle className="text-lg">Public-data context</CardTitle><p className="mt-1 text-sm text-slate-500">Each source is labelled by provenance and geographic use.</p></CardHeader>
                <CardContent className="p-0"><div className="divide-y divide-slate-200">{workspace.evidence.map((item) => <details key={item.key} className="group"><summary className="flex cursor-pointer list-none items-start justify-between gap-4 p-5 sm:p-6"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><ProvenanceBadge classification={item.classification} /><span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${item.contributes_to_rating ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>{item.contributes_to_rating ? "Used locally" : "Context only"}</span></div><h3 className="mt-3 font-semibold text-slate-950">{item.label}</h3><p className="mt-1 text-xs text-slate-500">{item.geography} · {item.reference_period ?? "Reference date unavailable"}</p></div><span className="text-2xl font-light text-slate-400 transition group-open:rotate-45">+</span></summary><div className="grid gap-5 bg-slate-50 px-5 py-5 sm:grid-cols-[180px_1fr] sm:px-6"><div><p className="text-xs font-medium text-slate-500">Observed value</p><p className="mt-1 text-xl font-semibold text-slate-950">{item.value ?? "Unknown"} {item.unit}</p></div><div className="space-y-3 text-xs leading-5 text-slate-600"><p><strong className="text-slate-900">Supports:</strong> {item.supported_inferences.join(" ")}</p><p><strong className="text-slate-900">Does not prove:</strong> {item.prohibited_inferences.join(", ")}</p><a href={item.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 font-semibold text-sky-700">Open cited source <ExternalLink className="size-3.5" /></a></div></div></details>)}</div></CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="priority">
              <Card className="gap-0 border-0 bg-white py-0 shadow-sm ring-slate-200">
                <CardHeader className="border-b border-slate-200 p-5 sm:p-6"><CardTitle className="text-lg">Transparent priority components</CardTitle><p className="mt-1 text-sm text-slate-500">Deterministic ratings based on compatible evidence—not an AI score.</p></CardHeader>
                <CardContent className="p-5 sm:p-6"><div className="grid gap-4 sm:grid-cols-2">{workspace.priority.components.map((component) => <article key={component.code} className="rounded-xl border border-slate-200 p-5"><div className="flex items-start justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{component.code.replaceAll("_", " ")}</p><h3 className="mt-2 font-semibold text-slate-950">{component.label}</h3></div><span className="grid min-w-11 place-items-center rounded-lg bg-teal-50 px-2 py-1.5 text-lg font-semibold text-teal-800">{component.rating ?? "—"}</span></div><p className="mt-4 text-xs leading-5 text-slate-600">{component.rationale}</p></article>)}</div><Alert className="mt-5 border-amber-200 bg-amber-50 text-amber-900"><Info /><AlertDescription>{workspace.priority.policy_notice}</AlertDescription></Alert></CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="incidents">
              <Card className="gap-0 border-0 bg-white py-0 shadow-sm ring-slate-200">
                <CardHeader className="border-b border-slate-200 p-5 sm:p-6"><CardTitle className="text-lg">Linked incident pattern</CardTitle><p className="mt-1 text-sm text-slate-500">{workspace.need.incident_count} distinct incidents across the review period.</p></CardHeader>
                <CardContent className="p-3"><div className="space-y-2">{workspace.incidents.map((incident, index) => <Link key={incident.id} to={`/officer/incidents/${incident.id}`} className="flex items-center gap-4 rounded-xl p-3 no-underline transition hover:bg-slate-50"><span className="grid size-9 shrink-0 place-items-center rounded-lg bg-teal-50 text-sm font-semibold text-teal-800">{index + 1}</span><div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-slate-950">{incident.title}</p><p className="mt-1 text-xs text-slate-500">{incident.locality} · {new Date(incident.event_start).toLocaleDateString()} · {incident.report_count} reports</p></div><ArrowRight className="size-4 text-slate-400" /></Link>)}</div><details className="mt-3 rounded-xl bg-slate-50 p-4"><summary className="cursor-pointer text-sm font-semibold text-slate-800">Alternative explanations</summary><ul className="mt-3 space-y-2 pl-5 text-xs leading-5 text-slate-600">{workspace.alternative_hypotheses.map((item) => <li key={item}>{item}</li>)}</ul></details></CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>

        <aside className="space-y-5 lg:sticky lg:top-24">
          <Card className="gap-0 border-0 bg-white py-0 shadow-sm ring-slate-200">
            <CardHeader className="border-b border-slate-200 p-5"><div className="flex items-center gap-3"><span className="grid size-9 place-items-center rounded-lg bg-teal-50 text-teal-700"><ClipboardCheck className="size-4" /></span><div><CardTitle>Record decision</CardTitle><p className="mt-0.5 text-xs text-slate-500">Human disposition required</p></div></div></CardHeader>
            <CardContent className="p-5">
              <form onSubmit={submitDecision} className="space-y-5">
                <div className="space-y-2"><Label>Disposition</Label><Select value={disposition} onValueChange={(value) => setDisposition(value as DecisionPayload["disposition"])}><SelectTrigger className="h-10 w-full"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="refer">Refer for verification</SelectItem><SelectItem value="defer">Defer for evidence</SelectItem><SelectItem value="reject">Reject candidate</SelectItem></SelectContent></Select></div>
                <div className="space-y-2"><Label htmlFor="decision-reason">Officer note <span className="font-normal text-slate-400">optional</span></Label><Textarea id="decision-reason" maxLength={600} placeholder="Evidence or uncertainty considered…" value={reasonText} onChange={(event) => setReasonText(event.target.value)} className="min-h-24 resize-y" /></div>
                {disposition === "refer" ? <div className="space-y-2"><Label htmlFor="decision-next-step">Required next step</Label><Textarea id="decision-next-step" maxLength={300} required value={nextStep} onChange={(event) => setNextStep(event.target.value)} className="min-h-24 resize-y" /></div> : null}
                {disposition === "defer" ? <div className="space-y-2"><Label htmlFor="decision-review-date">Review again on</Label><Input id="decision-review-date" type="date" required value={nextReviewDate} onChange={(event) => setNextReviewDate(event.target.value)} /></div> : null}
                {mutation.isError ? <Alert variant="destructive"><Info /><AlertDescription>The record was not written. Refresh before retrying.</AlertDescription></Alert> : null}
                {mutation.isSuccess ? <Alert className="border-emerald-200 bg-emerald-50 text-emerald-900"><CheckCircle2 /><AlertDescription>Decision recorded in this demo session.</AlertDescription></Alert> : null}
                <Button className="w-full" size="lg" disabled={mutation.isPending} type="submit">{mutation.isPending ? "Recording…" : "Record disposition"}</Button>
              </form>
            </CardContent>
          </Card>

          <Card className="gap-0 border-0 bg-white py-0 shadow-sm ring-slate-200">
            <CardHeader className="border-b border-slate-200 p-5"><div className="flex items-center gap-2"><History className="size-4 text-slate-500" /><CardTitle className="text-sm">Decision history</CardTitle></div></CardHeader>
            <CardContent className="p-4">
              {historyQuery.isPending ? <p className="p-2 text-xs text-slate-500">Opening demo officer session…</p> : null}
              {historyQuery.isError ? <p className="p-2 text-xs text-rose-700">History is temporarily unavailable.</p> : null}
              {history.length === 0 && historyQuery.isSuccess ? <p className="p-2 text-xs leading-5 text-slate-500">No disposition recorded in this session.</p> : null}
              <div className="space-y-3">{history.map((decision) => <article key={decision.id} className="rounded-xl bg-slate-50 p-3"><div className="flex items-center justify-between gap-2"><Badge variant="outline" className="rounded-full capitalize">{decision.disposition}</Badge><span className="text-[10px] text-slate-400">v{decision.entity_version_after}</span></div><p className="mt-3 text-xs font-semibold text-slate-800">{decision.reason_code.replaceAll("_", " ")}</p><p className="mt-1 line-clamp-3 text-xs leading-5 text-slate-500">{decision.next_step ?? decision.reason_text ?? decision.record_notice}</p></article>)}</div>
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}
