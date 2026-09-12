import { ArrowUpRight, Building2, ClipboardList, Home, ShieldCheck } from "lucide-react";
import { Link, Outlet, useLocation } from "react-router-dom";

import { CivicLogo } from "@/components/civic/CivicLogo";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

function PublicShell() {
  return (
    <div className="min-h-screen bg-[#f7f9f8] text-slate-950">
      <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/90 backdrop-blur-xl">
        <div className="mx-auto flex h-16 w-full max-w-[1440px] items-center justify-between px-4 sm:px-6 lg:px-10">
          <CivicLogo />
          <nav className="flex items-center gap-2" aria-label="Primary navigation">
            <Button asChild variant="ghost" className="hidden sm:inline-flex">
              <Link to="/officer"><Building2 data-icon="inline-start" /> Officer workspace</Link>
            </Button>
            <Button asChild>
              <Link to="/report">Report an issue <ArrowUpRight data-icon="inline-end" /></Link>
            </Button>
          </nav>
        </div>
      </header>
      <main><Outlet /></main>
      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex max-w-[1440px] flex-col gap-2 px-4 py-7 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-10">
          <span>© CivicLens · Bengaluru synthetic pilot</span>
          <span>Decision support only · Human review required</span>
        </div>
      </footer>
    </div>
  );
}

function OfficerShell() {
  return (
    <div className="min-h-screen bg-[#f5f7f9] text-slate-950 lg:grid lg:grid-cols-[248px_minmax(0,1fr)]">
      <aside className="hidden border-r border-slate-200 bg-[#0c2528] text-white lg:sticky lg:top-0 lg:flex lg:h-screen lg:flex-col">
        <div className="border-b border-white/10 px-6 py-5 [&_a]:text-white [&_span:last-child_span:last-child]:bg-white/10 [&_span:last-child_span:last-child]:text-teal-100">
          <CivicLogo />
        </div>
        <div className="px-4 py-5">
          <p className="px-3 text-[10px] font-bold uppercase tracking-[0.16em] text-teal-200/70">Planning console</p>
          <nav className="mt-3 grid gap-1" aria-label="Officer navigation">
            <Link to="/officer" className="flex items-center gap-3 rounded-lg bg-white/10 px-3 py-2.5 text-sm font-medium text-white no-underline">
              <ClipboardList className="size-4" /> Decision queues
            </Link>
            <Link to="/" className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-slate-300 no-underline transition hover:bg-white/5 hover:text-white">
              <Home className="size-4" /> Public portal
            </Link>
          </nav>
        </div>
        <div className="mt-auto p-4">
          <div className="rounded-xl border border-white/10 bg-white/5 p-4">
            <div className="flex items-center gap-2 text-xs font-semibold text-teal-100"><ShieldCheck className="size-4" /> Synthetic environment</div>
            <p className="mt-2 text-xs leading-5 text-slate-400">No live civic records or official actions.</p>
          </div>
        </div>
      </aside>
      <div className="min-w-0">
        <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur-xl">
          <div className="flex h-16 items-center justify-between px-4 sm:px-6 lg:px-8">
            <div className="lg:hidden"><CivicLogo /></div>
            <div className="hidden lg:block">
              <p className="text-sm font-semibold text-slate-900">Decision Intelligence</p>
              <p className="text-xs text-slate-500">Officer review workspace</p>
            </div>
            <Badge variant="outline" className="rounded-full border-teal-200 bg-teal-50 text-teal-800">Demo officer</Badge>
          </div>
        </header>
        <main><Outlet /></main>
      </div>
    </div>
  );
}

export function AppLayout() {
  const { pathname } = useLocation();
  return pathname.startsWith("/officer") ? <OfficerShell /> : <PublicShell />;
}
