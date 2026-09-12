import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

const styles: Record<string, string> = {
  synthetic_demo: "border-amber-200 bg-amber-50 text-amber-800",
  ai_derived: "border-violet-200 bg-violet-50 text-violet-800",
  real_public: "border-sky-200 bg-sky-50 text-sky-800",
  derived_public: "border-cyan-200 bg-cyan-50 text-cyan-800",
}

const labels: Record<string, string> = {
  synthetic_demo: "Synthetic",
  ai_derived: "AI derived",
  real_public: "Public data",
  derived_public: "Derived public",
}

export function ProvenanceBadge({ classification, className }: { classification: string; className?: string }) {
  return (
    <Badge variant="outline" className={cn("h-6 rounded-full px-2.5 font-semibold", styles[classification], className)}>
      {labels[classification] ?? classification.replaceAll("_", " ")}
    </Badge>
  )
}
