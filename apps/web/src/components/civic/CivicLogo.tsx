import { Aperture } from "lucide-react"
import { Link } from "react-router-dom"

export function CivicLogo({ compact = false }: { compact?: boolean }) {
  return (
    <Link to="/" className="inline-flex items-center gap-2.5 text-slate-950 no-underline" aria-label="CivicLens home">
      <span className="grid size-9 place-items-center rounded-xl bg-teal-700 text-white shadow-sm">
        <Aperture className="size-5" strokeWidth={2.25} aria-hidden="true" />
      </span>
      {!compact ? (
        <span className="flex items-baseline gap-1.5">
          <span className="text-[17px] font-semibold tracking-[-0.035em]">CivicLens</span>
          <span className="rounded bg-teal-50 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-[0.12em] text-teal-800">Pilot</span>
        </span>
      ) : null}
    </Link>
  )
}
