import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, CircleAlert, ClipboardList, Info, Search, Waves } from "lucide-react";
import { Link } from "react-router-dom";

import { MetricCard } from "@/components/civic/MetricCard";
import { ProvenanceBadge } from "@/components/civic/ProvenanceBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { fetchOfficerOverview, type OfficerOverview } from "../../api/officer";
import { ErrorState, LoadingState } from "./QueryState";

type Lane = OfficerOverview["safety_review"];

function QueueTable({ items, kind }: { items: Lane; kind: "safety" | "operational" | "planning" }) {
  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <div className="overflow-x-auto">
        <Table>
          <TableHeader className="bg-slate-50">
            <TableRow className="hover:bg-transparent">
              <TableHead className="min-w-[300px] px-5">Issue</TableHead>
              <TableHead>Locality</TableHead>
              <TableHead>Category</TableHead>
              <TableHead>Reports</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-24"><span className="sr-only">Action</span></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item) => (
              <TableRow key={item.id} className="group">
                <TableCell className="px-5 py-4 align-top">
                  <div className="flex items-start gap-3">
                    <span className={`mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg ${kind === "safety" ? "bg-rose-50 text-rose-700" : kind === "planning" ? "bg-teal-50 text-teal-700" : "bg-slate-100 text-slate-600"}`}>
                      {kind === "safety" ? <CircleAlert className="size-4" /> : kind === "planning" ? <Waves className="size-4" /> : <ClipboardList className="size-4" />}
                    </span>
                    <div><p className="font-semibold leading-5 text-slate-950">{item.title}</p><p className="mt-1 line-clamp-2 max-w-md text-xs leading-5 text-slate-500">{item.explanation}</p><div className="mt-2"><ProvenanceBadge classification={item.classification} /></div></div>
                  </div>
                </TableCell>
                <TableCell className="whitespace-nowrap text-sm text-slate-700">{item.locality}</TableCell>
                <TableCell className="whitespace-nowrap text-sm capitalize text-slate-600">{item.category.replaceAll("_", " ")}</TableCell>
                <TableCell><span className="font-semibold text-slate-900">{item.report_count}</span><span className="block text-[10px] text-slate-400">not unique people</span></TableCell>
                <TableCell><span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${kind === "safety" ? "bg-rose-50 text-rose-700" : kind === "planning" ? "bg-teal-50 text-teal-700" : "bg-slate-100 text-slate-700"}`}>{item.status.replaceAll("_", " ")}</span></TableCell>
                <TableCell className="pr-5 text-right">
                  {kind === "safety" ? <span className="text-xs font-medium text-rose-700">Verify</span> : <Button asChild size="icon-sm" variant="ghost" aria-label={kind === "planning" ? "Review suspected need" : "Inspect incident"}><Link to={kind === "planning" ? `/officer/needs/${item.id}` : `/officer/incidents/${item.id}`}><ArrowUpRight /></Link></Button>}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {items.length === 0 ? <div className="p-10 text-center text-sm text-slate-500">No items in this queue.</div> : null}
    </div>
  );
}

export function OfficerOverviewPage() {
  const query = useQuery({ queryKey: ["officer", "overview"], queryFn: ({ signal }) => fetchOfficerOverview(signal) });
  if (query.isPending) return <LoadingState label="Preparing decision queues…" />;
  if (query.isError) return <ErrorState error={query.error} />;

  const data = query.data;
  const total = data.safety_review.length + data.operational_incidents.length + data.planning_needs.length;

  return (
    <div className="mx-auto w-full max-w-[1600px] px-4 py-7 sm:px-6 lg:px-8 lg:py-9">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-teal-700">Officer command center</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-[-0.045em] text-slate-950 sm:text-4xl">Decision queues</h1>
          <p className="mt-2 text-sm leading-6 text-slate-600">Review urgent signals, operational incidents and suspected planning needs in separate lanes.</p>
        </div>
        <div className="relative w-full max-w-sm"><Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" /><Input aria-label="Search queues" placeholder="Search this demo workspace" className="h-10 rounded-xl bg-white pl-9 shadow-none" /></div>
      </div>

      <div className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Safety review" value={data.safety_review.length} helper="Immediate human verification" icon={CircleAlert} tone="danger" />
        <MetricCard label="Operational incidents" value={data.operational_incidents.length} helper="Bounded service events" icon={ClipboardList} />
        <MetricCard label="Planning needs" value={data.planning_needs.length} helper="Recurring patterns" icon={Waves} tone="primary" />
        <MetricCard label="Total in view" value={total} helper={`Dataset ${data.data_version}`} icon={Info} />
      </div>

      <Card className="mt-6 gap-0 border-0 bg-sky-50 py-0 ring-sky-200">
        <CardContent className="flex items-start gap-3 p-4 text-sm text-sky-900"><Info className="mt-0.5 size-4 shrink-0 text-sky-700" /><p className="leading-5"><strong>Demo data only.</strong> {data.disclosure}</p></CardContent>
      </Card>

      <Tabs defaultValue="safety" className="mt-7 gap-5">
        <TabsList className="h-11 w-full justify-start gap-1 overflow-x-auto rounded-xl bg-white p-1 ring-1 ring-slate-200 sm:w-fit">
          <TabsTrigger value="safety" className="h-9 min-w-fit px-3"><span className="size-2 rounded-full bg-rose-500" /> Safety <span className="rounded bg-slate-100 px-1.5 text-[10px]">{data.safety_review.length}</span></TabsTrigger>
          <TabsTrigger value="operational" className="h-9 min-w-fit px-3">Operational <span className="rounded bg-slate-100 px-1.5 text-[10px]">{data.operational_incidents.length}</span></TabsTrigger>
          <TabsTrigger value="planning" className="h-9 min-w-fit px-3">Planning <span className="rounded bg-slate-100 px-1.5 text-[10px]">{data.planning_needs.length}</span></TabsTrigger>
        </TabsList>

        <TabsContent value="safety" className="space-y-4">
          <div><h2 className="text-lg font-semibold text-slate-950">Safety review</h2><p className="mt-1 text-sm text-slate-500">Count-independent signals. These are never ranked against planning needs.</p></div>
          <QueueTable items={data.safety_review} kind="safety" />
        </TabsContent>
        <TabsContent value="operational" className="space-y-4">
          <div><h2 className="text-lg font-semibold text-slate-950">Operational incidents</h2><p className="mt-1 text-sm text-slate-500">Bounded events for operational handling, not assumed systemic problems.</p></div>
          <QueueTable items={data.operational_incidents} kind="operational" />
        </TabsContent>
        <TabsContent value="planning" className="space-y-4">
          <div><h2 className="text-lg font-semibold text-slate-950">Suspected planning needs</h2><p className="mt-1 text-sm text-slate-500">Recurring patterns with public context and conditional next steps.</p></div>
          <QueueTable items={data.planning_needs} kind="planning" />
        </TabsContent>
      </Tabs>
    </div>
  );
}
