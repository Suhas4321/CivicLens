import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CircleAlert, ClipboardList, Info, Search, Waves } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { ProvenanceBadge } from "@/components/civic/ProvenanceBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { fetchOfficerOverview, type OfficerOverview } from "../../api/officer";
import { ErrorState, LoadingState } from "./QueryState";

type Lane = OfficerOverview["safety_review"];
type LaneKind = "safety" | "operational" | "planning";

const laneConfig = {
  safety: {
    title: "Safety review",
    description: "Potential hazards that require immediate human verification.",
    icon: CircleAlert,
    iconClass: "bg-rose-100 text-rose-700",
    accentClass: "bg-rose-500",
    statusClass: "bg-rose-50 text-rose-700",
  },
  operational: {
    title: "Operational incidents",
    description: "Bounded service events for operational handling.",
    icon: ClipboardList,
    iconClass: "bg-amber-100 text-amber-800",
    accentClass: "bg-amber-500",
    statusClass: "bg-amber-50 text-amber-800",
  },
  planning: {
    title: "Planning needs",
    description: "Recurring patterns ready for structured evidence review.",
    icon: Waves,
    iconClass: "bg-teal-100 text-teal-800",
    accentClass: "bg-teal-600",
    statusClass: "bg-teal-50 text-teal-800",
  },
} satisfies Record<LaneKind, object>;

function QueueRow({ item, kind }: { item: Lane[number]; kind: LaneKind }) {
  const config = laneConfig[kind];
  const target = kind === "planning" ? `/officer/needs/${item.id}` : `/officer/incidents/${item.id}`;

  return (
    <article className="group relative border-t border-slate-200 px-5 py-5 first:border-t-0 sm:px-6">
      <span className={`absolute inset-y-5 left-0 w-1 rounded-r-full ${config.accentClass}`} />
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <ProvenanceBadge classification={item.classification} />
            <span className={`rounded-md px-2 py-1 text-[10px] font-bold uppercase tracking-[0.06em] ${config.statusClass}`}>{item.status.replaceAll("_", " ")}</span>
          </div>
          <h3 className="mt-3 text-base font-semibold leading-6 text-slate-950">{item.title}</h3>
          <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{item.explanation}</p>
        </div>
        {kind === "safety" ? (
          <Button asChild variant="outline" size="sm" className="shrink-0 border-rose-200 bg-rose-50 text-rose-800 hover:bg-rose-100 hover:text-rose-900">
            <Link to={target}>Verify now <ArrowRight /></Link>
          </Button>
        ) : (
          <Button asChild variant="ghost" size="icon" className="shrink-0 rounded-full border border-slate-200 bg-white text-slate-500 group-hover:border-teal-300 group-hover:text-teal-800" aria-label={`Review ${item.title}`}>
            <Link to={target}><ArrowRight /></Link>
          </Button>
        )}
      </div>
      <div className="mt-4 grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-4 rounded-lg bg-slate-50 px-3 py-2.5 text-xs">
        <div className="min-w-0"><span className="text-slate-400">Locality</span><p className="mt-0.5 truncate font-medium text-slate-800">{item.locality}</p></div>
        <div><span className="text-slate-400">Category</span><p className="mt-0.5 font-medium capitalize text-slate-800">{item.category.replaceAll("_", " ")}</p></div>
        <div className="text-right"><span className="text-slate-400">Reports</span><p className="mt-0.5 font-semibold text-slate-900">{item.report_count}</p></div>
      </div>
      <p className="mt-2 text-right text-[10px] text-slate-400">Report count is not unique people</p>
    </article>
  );
}

function QueuePanel({ items, kind }: { items: Lane; kind: LaneKind }) {
  const config = laneConfig[kind];
  const Icon = config.icon;

  return (
    <Card className="gap-0 overflow-hidden border-0 bg-white py-0 shadow-sm ring-slate-200">
      <CardHeader className="border-b border-slate-200 p-5 sm:p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <span className={`grid size-10 shrink-0 place-items-center rounded-xl ${config.iconClass}`}><Icon className="size-5" /></span>
            <div><h2 className="text-lg font-semibold tracking-tight text-slate-950">{config.title}</h2><p className="mt-1 max-w-md text-xs leading-5 text-slate-500">{config.description}</p></div>
          </div>
          <span className="grid min-w-10 place-items-center rounded-lg bg-slate-950 px-2 py-1.5 text-sm font-semibold text-white">{items.length}</span>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {items.length ? items.map((item) => <QueueRow key={item.id} item={item} kind={kind} />) : <div className="p-10 text-center text-sm text-slate-500">No matching items.</div>}
      </CardContent>
    </Card>
  );
}

export function OfficerOverviewPage() {
  const [search, setSearch] = useState("");
  const query = useQuery({
    queryKey: ["officer", "overview"],
    queryFn: ({ signal }) => fetchOfficerOverview(signal),
  });

  if (query.isPending) return <LoadingState label="Preparing decision queues…" />;
  if (query.isError) return <ErrorState error={query.error} />;

  const data = query.data;
  const filterLane = (items: Lane) => {
    const term = search.trim().toLowerCase();
    if (!term) return items;
    return items.filter((item) =>
      [item.title, item.locality, item.category, item.status].some((value) => value.toLowerCase().includes(term)),
    );
  };
  const safety = filterLane(data.safety_review);
  const operational = filterLane(data.operational_incidents);
  const planning = filterLane(data.planning_needs);

  return (
    <div className="mx-auto w-full max-w-[1600px] px-4 py-7 sm:px-6 lg:px-8 lg:py-9">
      <div className="grid gap-5 lg:grid-cols-[1fr_360px] lg:items-end">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-teal-700">Officer command center</p>
            <Badge variant="outline" className="rounded-md border-slate-200 bg-white text-[10px] text-slate-500">{data.data_version}</Badge>
          </div>
          <h1 className="mt-2 text-3xl font-semibold tracking-[-0.045em] text-slate-950 sm:text-4xl">What needs attention?</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">Three queues, separated by purpose. Safety is never ranked against planning priority.</p>
        </div>
        <div className="relative"><Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" /><Input aria-label="Search queues" placeholder="Search locality, category or status" value={search} onChange={(event) => setSearch(event.target.value)} className="h-11 rounded-xl border-slate-300 bg-white pl-10 shadow-none" /></div>
      </div>

      <div className="mt-7 grid overflow-hidden rounded-xl border border-slate-200 bg-white sm:grid-cols-3">
        {[
          { label: "Safety review", value: data.safety_review.length, note: "Human verification", icon: CircleAlert, style: "text-rose-700 bg-rose-50" },
          { label: "Operational", value: data.operational_incidents.length, note: "Bounded incidents", icon: ClipboardList, style: "text-amber-800 bg-amber-50" },
          { label: "Planning needs", value: data.planning_needs.length, note: "Recurring patterns", icon: Waves, style: "text-teal-800 bg-teal-50" },
        ].map(({ label, value, note, icon: Icon, style }, index) => (
          <div key={label} className={`flex items-center gap-4 p-4 sm:p-5 ${index ? "border-t border-slate-200 sm:border-l sm:border-t-0" : ""}`}>
            <span className={`grid size-10 place-items-center rounded-lg ${style}`}><Icon className="size-5" /></span>
            <div><p className="text-2xl font-semibold tracking-tight text-slate-950">{value}</p><p className="text-xs font-semibold text-slate-800">{label}</p><p className="mt-0.5 text-[10px] text-slate-400">{note}</p></div>
          </div>
        ))}
      </div>

      <div className="mt-5 flex items-start gap-2 rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-xs leading-5 text-sky-900">
        <Info className="mt-0.5 size-4 shrink-0 text-sky-700" /><p><strong>Demo environment.</strong> {data.disclosure}</p>
      </div>

      <section className="mt-6" aria-labelledby="safety-queue-title">
        <div className="mb-3 flex items-center justify-between"><div><p className="text-[10px] font-bold uppercase tracking-[0.14em] text-rose-700">Immediate attention</p><h2 id="safety-queue-title" className="mt-1 text-xl font-semibold tracking-tight text-slate-950">Safety review</h2></div><span className="text-xs text-slate-500">Count-independent · never ranked</span></div>
        <div className="overflow-hidden rounded-xl border border-rose-200 bg-white shadow-sm">
          {safety.length ? safety.map((item) => <QueueRow key={item.id} item={item} kind="safety" />) : <div className="p-8 text-center text-sm text-slate-500">No matching safety signals.</div>}
        </div>
      </section>

      <div className="mt-6 grid gap-6 xl:grid-cols-2 xl:items-start">
        <QueuePanel items={operational} kind="operational" />
        <QueuePanel items={planning} kind="planning" />
      </div>
    </div>
  );
}
