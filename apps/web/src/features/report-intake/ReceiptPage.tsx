import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Check, Clock3, FileCheck2, LockKeyhole, MapPin } from "lucide-react";
import { Link, useLocation, useParams } from "react-router-dom";

import { ProvenanceBadge } from "@/components/civic/ProvenanceBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { fetchReceipt } from "../../api/reports";
import { ErrorState, LoadingState } from "../officer/QueryState";

type ReceiptNavigationState = { capability?: string };

export function ReceiptPage() {
  const { publicId = "" } = useParams();
  const location = useLocation();
  const capability = (location.state as ReceiptNavigationState | null)?.capability;
  const query = useQuery({ queryKey: ["receipt", publicId], queryFn: ({ signal }) => fetchReceipt(publicId, capability ?? "", signal), enabled: Boolean(publicId && capability), retry: false });

  if (!capability) {
    return (
      <section className="mx-auto flex min-h-[70vh] max-w-2xl items-center px-4 py-14 sm:px-6">
        <Card className="w-full gap-0 border-0 bg-white py-0 text-center shadow-sm ring-slate-200">
          <CardContent className="p-7 sm:p-10">
            <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-slate-100 text-slate-600"><LockKeyhole className="size-6" /></span>
            <h1 className="mt-6 text-3xl font-semibold tracking-[-0.04em] text-slate-950">This receipt has expired</h1>
            <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-slate-600">For privacy, demo receipts are available only immediately after submission.</p>
            <Button asChild className="mt-7"><Link to="/report">Create another report <ArrowRight /></Link></Button>
          </CardContent>
        </Card>
      </section>
    );
  }
  if (query.isPending) return <LoadingState label="Opening your receipt…" />;
  if (query.isError) return <ErrorState error={query.error} />;

  const receipt = query.data;
  return (
    <section className="mx-auto flex min-h-[75vh] max-w-3xl items-center px-4 py-12 sm:px-6">
      <Card className="w-full gap-0 border-0 bg-white py-0 shadow-xl shadow-slate-900/5 ring-slate-200">
        <CardContent className="p-6 sm:p-10">
          <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <span className="grid size-14 place-items-center rounded-2xl bg-emerald-100 text-emerald-700"><Check className="size-7" strokeWidth={2.5} /></span>
              <p className="mt-6 text-xs font-bold uppercase tracking-[0.14em] text-emerald-700">Report received</p>
              <h1 className="mt-2 text-balance text-3xl font-semibold tracking-[-0.045em] text-slate-950 sm:text-4xl">Thank you for sharing what you noticed.</h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-slate-600">{receipt.message}</p>
            </div>
            <Badge variant="outline" className="w-fit rounded-full border-emerald-200 bg-emerald-50 px-3 text-emerald-800">{receipt.status}</Badge>
          </div>

          <div className="mt-8 grid gap-3 rounded-2xl bg-slate-50 p-4 sm:grid-cols-2 sm:p-5">
            <div className="rounded-xl bg-white p-4 ring-1 ring-slate-200"><div className="flex items-center gap-2 text-xs font-medium text-slate-500"><FileCheck2 className="size-4 text-teal-700" /> Receipt number</div><p className="mt-2 break-all font-mono text-sm font-semibold text-slate-900">{receipt.public_id}</p></div>
            <div className="rounded-xl bg-white p-4 ring-1 ring-slate-200"><div className="flex items-center gap-2 text-xs font-medium text-slate-500"><MapPin className="size-4 text-teal-700" /> General locality</div><p className="mt-2 text-sm font-semibold text-slate-900">{receipt.generalized_area}</p></div>
          </div>

          <div className="mt-5 flex items-start gap-3 rounded-xl border border-sky-200 bg-sky-50 p-4">
            <Clock3 className="mt-0.5 size-5 shrink-0 text-sky-700" />
            <div><p className="text-sm font-semibold text-sky-950">{receipt.analysis_state}</p><p className="mt-1 text-xs leading-5 text-sky-800">Your report may be compared with related synthetic reports before officer review.</p></div>
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-2"><ProvenanceBadge classification="synthetic_demo" /><ProvenanceBadge classification={receipt.analysis_class === "pending" ? "ai_derived" : "ai_derived"} /><span className="text-xs text-slate-500">Analysis: {receipt.analysis_class.replaceAll("_", " ")}</span></div>

          <div className="mt-8 flex flex-col-reverse gap-3 border-t border-slate-200 pt-6 sm:flex-row sm:items-center sm:justify-between">
            <Button asChild variant="ghost"><Link to="/report">Submit another report</Link></Button>
            <Button asChild><Link to="/officer">See how officers review it <ArrowRight /></Link></Button>
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
