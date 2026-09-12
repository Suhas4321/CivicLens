import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Building2, CheckCircle2, ClipboardCheck, GitMerge, Languages, MessageSquareText, ShieldAlert, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { ApiError, fetchVersion } from "../../api/health";

const steps = [
  { icon: MessageSquareText, label: "Citizen reports", helper: "Text or short voice" },
  { icon: GitMerge, label: "Patterns emerge", helper: "Related incidents grouped" },
  { icon: ClipboardCheck, label: "Officer decides", helper: "Evidence stays visible" },
];

export function HomePage() {
  const versionQuery = useQuery({ queryKey: ["health", "version"], queryFn: ({ signal }) => fetchVersion(signal) });
  const apiLabel = versionQuery.isPending ? "Connecting…" : versionQuery.data ? "Demo system online" : versionQuery.error instanceof ApiError ? "Demo API unavailable" : "Web preview ready";

  return (
    <>
      <section className="relative overflow-hidden border-b border-slate-200 bg-white">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_82%_12%,rgba(13,148,136,0.13),transparent_30rem)]" />
        <div className="relative mx-auto grid min-h-[620px] max-w-[1440px] items-center gap-12 px-4 py-16 sm:px-6 lg:grid-cols-[1.1fr_0.9fr] lg:px-10 lg:py-20">
          <div className="max-w-3xl">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-teal-200 bg-teal-50 px-3 py-1.5 text-xs font-semibold text-teal-800">
              <Sparkles className="size-3.5" /> Bengaluru civic planning pilot
            </div>
            <h1 className="text-balance text-[clamp(3rem,7vw,6.7rem)] font-semibold leading-[0.92] tracking-[-0.065em] text-slate-950">See the need behind the noise.</h1>
            <p className="mt-7 max-w-2xl text-pretty text-lg leading-8 text-slate-600 sm:text-xl">CivicLens turns recurring public reports into clear, reviewable priorities—so planning teams can focus on what needs investigation first.</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button asChild size="lg" className="h-12 rounded-xl px-5 text-[15px] shadow-lg shadow-teal-900/10"><Link to="/report">Report an issue <ArrowRight data-icon="inline-end" /></Link></Button>
              <Button asChild size="lg" variant="outline" className="h-12 rounded-xl px-5 text-[15px]"><Link to="/officer">Explore officer workspace</Link></Button>
            </div>
            <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-slate-500">
              <span className="flex items-center gap-2"><Languages className="size-4 text-teal-700" /> Multilingual input</span>
              <span className="flex items-center gap-2"><ShieldAlert className="size-4 text-teal-700" /> Safety routed separately</span>
            </div>
          </div>

          <div className="relative">
            <div className="absolute -inset-5 rounded-[2rem] bg-gradient-to-br from-teal-100/80 to-sky-100/40 blur-2xl" />
            <Card className="relative gap-0 border-0 bg-[#102f33] py-0 text-white shadow-2xl shadow-slate-900/20 ring-0">
              <CardHeader className="border-b border-white/10 p-6 sm:p-7">
                <div className="flex items-center justify-between gap-4">
                  <div><p className="text-xs font-semibold uppercase tracking-[0.14em] text-teal-200">Decision snapshot</p><p className="mt-2 text-xl font-semibold tracking-tight">Water reliability pattern</p></div>
                  <span className="rounded-full bg-amber-300/15 px-2.5 py-1 text-xs font-medium text-amber-200">Suspected need</span>
                </div>
              </CardHeader>
              <CardContent className="p-6 sm:p-7">
                <div className="grid grid-cols-3 gap-3">
                  {[['12','reports'],['3','incidents'],['2','localities']].map(([value,label]) => <div key={label} className="rounded-xl border border-white/10 bg-white/5 p-4"><strong className="block text-2xl tracking-tight">{value}</strong><span className="mt-1 block text-xs text-slate-300">{label}</span></div>)}
                </div>
                <div className="mt-6 space-y-3">
                  {["Repeated across separate service events", "Local public indicator available", "Ready for human feasibility review"].map((item) => <div key={item} className="flex items-center gap-3 text-sm text-slate-200"><CheckCircle2 className="size-4 text-teal-300" /> {item}</div>)}
                </div>
                <div className="mt-7 rounded-xl bg-white p-4 text-slate-900"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Recommended next step</p><p className="mt-1.5 text-sm font-medium">Verify service conditions and existing works overlap.</p></div>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-[1440px] px-4 py-16 sm:px-6 lg:px-10 lg:py-20">
        <div className="mx-auto max-w-3xl text-center"><p className="text-xs font-bold uppercase tracking-[0.14em] text-teal-700">How it works</p><h2 className="mt-3 text-3xl font-semibold tracking-[-0.04em] text-slate-950 sm:text-4xl">One clear path from report to review</h2><p className="mt-4 text-base leading-7 text-slate-600">Citizen input starts the process. Transparent evidence and a human decision finish it.</p></div>
        <div className="mt-10 grid gap-4 md:grid-cols-3">
          {steps.map(({ icon: Icon, label, helper }, index) => <Card key={label} className="gap-0 border-0 bg-white py-0 shadow-sm ring-slate-200"><CardContent className="flex items-center gap-4 p-5 sm:p-6"><span className="grid size-12 shrink-0 place-items-center rounded-xl bg-teal-50 text-teal-700"><Icon className="size-5" /></span><div><p className="text-xs font-semibold text-slate-400">0{index + 1}</p><h3 className="mt-0.5 font-semibold text-slate-950">{label}</h3><p className="mt-1 text-sm text-slate-500">{helper}</p></div></CardContent></Card>)}
        </div>
      </section>

      <section className="border-t border-slate-200 bg-white">
        <div className="mx-auto grid max-w-[1440px] gap-5 px-4 py-12 sm:px-6 md:grid-cols-2 lg:px-10">
          <Card className="gap-0 border-0 bg-teal-700 py-0 text-white ring-0"><CardContent className="flex h-full flex-col p-7 sm:p-8"><MessageSquareText className="size-6 text-teal-100" /><h2 className="mt-10 text-2xl font-semibold tracking-tight">I’m reporting a local issue</h2><p className="mt-2 max-w-lg text-sm leading-6 text-teal-50/80">Share a simple description and general locality. No account is required.</p><Button asChild variant="secondary" className="mt-6 w-fit"><Link to="/report">Start a report <ArrowRight /></Link></Button></CardContent></Card>
          <Card className="gap-0 border-0 bg-slate-950 py-0 text-white ring-0"><CardContent className="flex h-full flex-col p-7 sm:p-8"><Building2 className="size-6 text-sky-200" /><h2 className="mt-10 text-2xl font-semibold tracking-tight">I’m reviewing civic priorities</h2><p className="mt-2 max-w-lg text-sm leading-6 text-slate-300">Open the structured safety, operations and planning queues.</p><Button asChild variant="secondary" className="mt-6 w-fit"><Link to="/officer">Open workspace <ArrowRight /></Link></Button></CardContent></Card>
        </div>
      </section>

      <div className="mx-auto flex max-w-[1440px] items-center gap-2 px-4 py-4 text-xs text-slate-500 sm:px-6 lg:px-10" aria-live="polite"><span className={`size-2 rounded-full ${versionQuery.data ? "bg-emerald-500" : versionQuery.isPending ? "bg-amber-400" : "bg-slate-400"}`} />{apiLabel}</div>
    </>
  );
}
