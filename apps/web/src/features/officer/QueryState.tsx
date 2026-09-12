import { AlertCircle, LoaderCircle } from "lucide-react";

import { ApiError } from "../../api/health";

export function LoadingState({ label }: { label: string }) {
  return (
    <section className="grid min-h-[60vh] place-items-center px-4" aria-live="polite">
      <div className="text-center">
        <LoaderCircle className="mx-auto size-7 animate-spin text-teal-700" aria-hidden="true" />
        <h1 className="mt-4 text-lg font-semibold text-slate-900">{label}</h1>
      </div>
    </section>
  );
}

export function ErrorState({ error }: { error: unknown }) {
  const reference = error instanceof ApiError ? error.correlationId : null;
  return (
    <section className="grid min-h-[60vh] place-items-center px-4" role="alert">
      <div className="max-w-md rounded-2xl border border-rose-200 bg-white p-8 text-center shadow-sm">
        <span className="mx-auto grid size-12 place-items-center rounded-xl bg-rose-50 text-rose-700"><AlertCircle aria-hidden="true" /></span>
        <h1 className="mt-5 text-xl font-semibold text-slate-950">This view is unavailable</h1>
        <p className="mt-2 text-sm leading-6 text-slate-600">No data or decision was changed. Check the API and try again.</p>
        {reference ? <p className="mt-4 font-mono text-xs text-slate-400">Reference: {reference}</p> : null}
      </div>
    </section>
  );
}
