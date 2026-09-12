import type { ReactNode } from "react"

export function SectionHeading({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="max-w-2xl">
        {eyebrow ? <p className="mb-2 text-xs font-bold uppercase tracking-[0.14em] text-teal-700">{eyebrow}</p> : null}
        <h2 className="text-balance text-2xl font-semibold tracking-[-0.035em] text-slate-950 sm:text-3xl">{title}</h2>
        {description ? <p className="mt-2 max-w-xl text-sm leading-6 text-slate-600">{description}</p> : null}
      </div>
      {action}
    </div>
  )
}
