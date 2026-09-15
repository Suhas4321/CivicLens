import {
  Bus,
  CloudRain,
  Construction,
  Dog,
  Droplets,
  GlassWater,
  Info,
  Lightbulb,
  Trash2,
  Trees,
  Waves,
  Zap,
  type LucideIcon,
} from "lucide-react";

import { AGENCY_META, type Category } from "@/api/priority";
import { cn } from "@/lib/utils";

/**
 * The closed list of 12 categories, as a picker.
 *
 * Three deliberate choices here:
 *
 *   1. **Kannada is the primary label, English the secondary.** The target area
 *      is JP Nagar and Banashankari, where Kannada is the more comfortable
 *      reading language for a large share of residents. Putting English first
 *      would be a default inherited from the tooling, not a decision about
 *      these users.
 *   2. **Every tile carries an icon.** A reporter who reads neither label
 *      fluently can still pick "burst pipe" from a picture. Colour alone is
 *      never the differentiator — icon, Kannada, English and agency all vary.
 *   3. **The responsible agency and its deadline are shown on the tile.** No
 *      Indian civic portal tells you who is accountable and by when *before* you
 *      file. It costs nothing here and it is the clearest legitimacy signal the
 *      form can give.
 */

const ICONS: Record<string, LucideIcon> = {
  ELECTRICAL_HAZARD: Zap,
  WATER_CONTAMINATION: Droplets,
  SEWAGE_OVERFLOW: Waves,
  TREE_HAZARD: Trees,
  WATER_SUPPLY: GlassWater,
  WATERLOGGING: CloudRain,
  GARBAGE: Trash2,
  STREET_LIGHT: Lightbulb,
  STRAY_ANIMALS: Dog,
  BUS_STOP: Bus,
  ROAD_DAMAGE: Construction,
  OTHER: Info,
};

export function CategoryGrid({
  categories,
  value,
  onChange,
}: {
  categories: readonly Category[];
  value: string | null;
  onChange: (code: string) => void;
}) {
  return (
    <div
      role="radiogroup"
      aria-label="What kind of problem is it?"
      className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4"
    >
      {categories.map((category) => {
        const Icon = ICONS[category.code] ?? Info;
        const selected = value === category.code;
        const hazard = category.lane_1_eligible;

        return (
          <button
            key={category.code}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(category.code)}
            className={cn(
              "group flex flex-col items-start gap-3 rounded-2xl border-2 bg-white p-4 text-left transition",
              "hover:border-lane-discretionary/50 hover:shadow-sm",
              selected
                ? "border-lane-discretionary shadow-md ring-4 ring-lane-discretionary/15"
                : "border-slate-200",
            )}
          >
            <span
              className={cn(
                "grid size-12 shrink-0 place-items-center rounded-xl transition",
                selected
                  ? "bg-lane-discretionary text-white"
                  : hazard
                    ? "bg-lane-safety-surface text-lane-safety"
                    : "bg-slate-100 text-slate-600 group-hover:bg-lane-discretionary-surface group-hover:text-lane-discretionary-ink",
              )}
            >
              <Icon className="size-6" strokeWidth={2} aria-hidden />
            </span>

            <span className="min-w-0">
              {/* Kannada first, at full body size. */}
              <span className="block text-[1.0625rem] font-semibold leading-6 text-slate-950">
                {category.label_kn}
              </span>
              <span className="mt-0.5 block text-sm leading-5 text-slate-600">
                {category.label_en}
              </span>
            </span>

            <span className="mt-auto flex flex-wrap items-center gap-1.5 pt-1 text-xs">
              {category.agency ? (
                <span
                  className="rounded-md bg-slate-100 px-1.5 py-0.5 font-semibold text-slate-700"
                  title={AGENCY_META[category.agency].name}
                >
                  {category.agency}
                </span>
              ) : (
                <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-slate-600">
                  We will decide
                </span>
              )}
              <span className="numeric text-slate-500">
                {category.sla_days === 1 ? "1 day" : `${category.sla_days} days`}
              </span>
            </span>
          </button>
        );
      })}
    </div>
  );
}

/** Shown once a category is chosen, so the reporter sees what they committed to. */
export function CategorySummary({ category }: { category: Category }) {
  const Icon = ICONS[category.code] ?? Info;
  return (
    <div className="flex items-center gap-3">
      <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-lane-discretionary text-white">
        <Icon className="size-5" aria-hidden />
      </span>
      <div className="min-w-0">
        <p className="truncate font-semibold text-slate-950">{category.label_kn}</p>
        <p className="truncate text-sm text-slate-600">{category.label_en}</p>
      </div>
    </div>
  );
}
