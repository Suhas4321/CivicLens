import type { LucideIcon } from "lucide-react"

import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"

const tones = {
  danger: "bg-rose-50 text-rose-700 ring-rose-100",
  neutral: "bg-slate-100 text-slate-700 ring-slate-200",
  primary: "bg-teal-50 text-teal-700 ring-teal-100",
}

export function MetricCard({ label, value, helper, icon: Icon, tone = "neutral" }: { label: string; value: number | string; helper: string; icon: LucideIcon; tone?: keyof typeof tones }) {
  return (
    <Card className="gap-0 border-0 bg-white py-0 shadow-[0_1px_2px_rgba(15,23,42,.04)] ring-1 ring-slate-200/80">
      <CardContent className="flex items-center gap-4 p-5">
        <span className={cn("grid size-11 shrink-0 place-items-center rounded-xl ring-1", tones[tone])}>
          <Icon className="size-5" aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <div className="flex items-baseline gap-2">
            <strong className="text-2xl font-semibold tracking-[-0.04em] text-slate-950">{value}</strong>
            <span className="text-sm font-medium text-slate-800">{label}</span>
          </div>
          <p className="mt-0.5 truncate text-xs text-slate-500">{helper}</p>
        </div>
      </CardContent>
    </Card>
  )
}
