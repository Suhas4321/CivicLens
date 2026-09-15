import { ArrowUpRight, Building2, ClipboardList, Home, ShieldCheck } from "lucide-react";
import { Link, Outlet, useLocation } from "react-router-dom";

import { CivicLogo } from "@/components/civic/CivicLogo";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

/**
 * Two surfaces, one app.
 *
 * `data-surface` is what makes them feel different, and it is set here rather
 * than page by page so no page can forget. `styles/civic.css` hangs the base type
 * scale, the canvas colour and the minimum touch-target size off that attribute:
 * the public surface is 18px with 48px targets because it is used once, on a
 * phone, by someone who may be standing in the street; the officer surface is
 * 14px and dense because it is read for hours and compared row against row.
 *
 * Both shells use the `page-shell` utility for their container. Previously the
 * shell capped at 1440px, the officer page at 1600px and the report page at
 * `max-w-5xl`, so content jumped width as you navigated and the gaps at the left
 * and right changed on every route. One utility, one number, no drift.
 */

function PublicShell() {
  return (
    <div data-surface="public" className="min-h-screen text-slate-950">
      <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/90 backdrop-blur-xl">
        <div className="page-shell flex h-16 items-center justify-between">
          <CivicLogo />
          {/* One action, and it is the citizen's. Staff get a text link, not a
            * second button: offering "officer workspace" as a co-equal choice is
            * part of what made the two surfaces read as one undifferentiated
            * site, and a resident has no use for it. */}
          <nav className="flex items-center gap-4" aria-label="Primary navigation">
            <Link
              to="/officer"
              className="hidden text-sm font-medium text-slate-500 no-underline hover:text-slate-800 sm:inline-flex sm:items-center sm:gap-1.5"
            >
              <Building2 className="size-4" aria-hidden /> Staff
            </Link>
            <Button asChild>
              <Link to="/report">
                Report a problem <ArrowUpRight data-icon="inline-end" />
              </Link>
            </Button>
          </nav>
        </div>
      </header>
      <main>
        <Outlet />
      </main>
      <footer className="border-t border-slate-200 bg-white">
        <div className="page-shell flex flex-col gap-2 py-7 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between">
          <span>CivicLens · Bengaluru South · ಬೆಂಗಳೂರು ದಕ್ಷಿಣ</span>
          {/* Was "Decision support only · Human review required", which is a
            * sentence written for a procurement document. A resident cannot act
            * on it. What they need to know is that nothing here is real yet. */}
          <span>A prototype. Every report shown is test data, not a real complaint.</span>
        </div>
      </footer>
    </div>
  );
}

function OfficerShell() {
  return (
    <div
      data-surface="officer"
      className="min-h-screen text-slate-950 lg:grid lg:grid-cols-[248px_minmax(0,1fr)]"
    >
      <aside className="hidden border-r border-slate-200 bg-officer-chrome text-white lg:sticky lg:top-0 lg:flex lg:h-screen lg:flex-col">
        <div className="border-b border-white/10 px-6 py-5 [&_a]:text-white [&_span:last-child_span:last-child]:bg-white/10 [&_span:last-child_span:last-child]:text-teal-100">
          <CivicLogo />
        </div>
        <div className="px-4 py-5">
          <p className="px-3 text-[10px] font-bold uppercase tracking-[0.16em] text-teal-200/70">
            Bengaluru South
          </p>
          <nav className="mt-3 grid gap-1" aria-label="Officer navigation">
            {/* Named after what the page is, not after a concept. The old label
              * was "Decision queues", which matched no heading in the app. */}
            <Link
              to="/officer"
              className="flex items-center gap-3 rounded-lg bg-white/10 px-3 py-2.5 text-sm font-medium text-white no-underline"
            >
              <ClipboardList className="size-4" /> Ward board
            </Link>
            <Link
              to="/"
              className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-slate-300 no-underline transition hover:bg-white/5 hover:text-white"
            >
              <Home className="size-4" /> Public portal
            </Link>
          </nav>
        </div>
        <div className="mt-auto p-4">
          <div className="rounded-xl border border-white/10 bg-white/5 p-4">
            <div className="flex items-center gap-2 text-xs font-semibold text-teal-100">
              <ShieldCheck className="size-4" /> Synthetic environment
            </div>
            <p className="mt-2 text-xs leading-5 text-slate-400">
              No live civic records or official actions.
            </p>
          </div>
        </div>
      </aside>
      <div className="min-w-0">
        <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur-xl">
          <div className="flex h-16 items-center justify-between px-4 sm:px-6 lg:px-8">
            <div className="lg:hidden">
              <CivicLogo />
            </div>
            <div className="hidden lg:block">
              <p className="text-sm font-semibold text-slate-900">Bengaluru South · Ward board</p>
              <p className="text-xs text-slate-500">Officer review workspace</p>
            </div>
            <Badge
              variant="outline"
              className="rounded-full border-teal-200 bg-teal-50 text-teal-800"
            >
              Demo officer
            </Badge>
          </div>
        </header>
        <main>
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export function AppLayout() {
  const { pathname } = useLocation();
  return pathname.startsWith("/officer") ? <OfficerShell /> : <PublicShell />;
}
