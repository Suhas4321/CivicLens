import { TriangleAlert } from "lucide-react";

import {
  BAND_META,
  COMPONENT_META,
  COMPONENT_ORDER,
  SCORE_WEIGHTS,
  formatScore,
  verifyScore,
  type Score,
} from "@/api/priority";
import { cn } from "@/lib/utils";

/**
 * Score display.
 *
 * The rule this file exists to enforce: **the UI never shows a total it has not
 * checked.** `verifyScore` recomputes the weighted sum from the components the
 * backend sent. If the arithmetic does not reproduce the claimed total, the
 * number is not rendered at all — a warning is rendered instead. A wrong
 * priority figure shown confidently is worse than a visible failure, because an
 * officer cannot tell the difference between a correct 82 and a corrupted one.
 *
 * The score is also not a lane. The band styling is an ink-weight scale from
 * `styles/civic.css`, not the red/amber/teal lane palette, so a High-band
 * discretionary score can never be mistaken for a safety hazard.
 */

export function ScoreBadge({
  score,
  provisional,
}: {
  score: Score | null;
  provisional?: boolean;
}) {
  if (!score) {
    // Safety and statutory lanes are never scored. Saying so is more useful
    // than an empty cell, which reads as missing data.
    return <span className="text-xs text-slate-400">Not scored</span>;
  }

  // A provisional group is ranked but held below the High band until minimum
  // evidence exists, so the cap has to be part of the check, not applied after.
  const check = verifyScore(score, provisional ? { provisionalCap: 69 } : undefined);

  if (!check.ok) {
    return (
      <span
        className="inline-flex items-center gap-1.5 rounded-md bg-lane-safety-surface px-2 py-1 text-xs font-semibold text-lane-safety"
        title={`Claimed ${check.claimed}, recomputed ${check.recomputed.toFixed(2)}: ${check.reason}`}
      >
        <TriangleAlert className="size-3.5" aria-hidden />
        Score failed check
      </span>
    );
  }

  const band = BAND_META[score.band];
  return (
    <span className="inline-flex items-center gap-2">
      <span
        className={cn(
          "numeric rounded-md px-2 py-1 text-sm font-semibold tabular-nums",
          band.className,
        )}
      >
        {formatScore(check.total)}
      </span>
      <span className="text-xs font-medium text-slate-600">{band.label}</span>
      {check.capped ? (
        <span
          className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-600"
          title={`Weighted total is ${check.uncappedTotal.toFixed(2)}, held below High until minimum evidence exists.`}
        >
          Provisional
        </span>
      ) : null}
    </span>
  );
}

/**
 * The score, opened up.
 *
 * Every row is component × weight = contribution, and the column sums to the
 * total displayed above it. An officer who disagrees with a ranking can see
 * precisely which input caused it and challenge that input rather than the
 * ranking, which is the only way a judgment stays reviewable.
 */
export function ScoreArithmetic({
  score,
  provisional,
}: {
  score: Score;
  provisional?: boolean;
}) {
  const check = verifyScore(score, provisional ? { provisionalCap: 69 } : undefined);

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <table className="w-full text-sm">
        <caption className="sr-only">How the triage score was calculated</caption>
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-[0.06em] text-slate-500">
            <th scope="col" className="px-3 py-2 font-semibold">
              What it measures
            </th>
            <th scope="col" className="px-3 py-2 text-right font-semibold">
              Value
            </th>
            <th scope="col" className="px-3 py-2 text-right font-semibold">
              Weight
            </th>
            <th scope="col" className="px-3 py-2 text-right font-semibold">
              Adds
            </th>
          </tr>
        </thead>
        <tbody>
          {COMPONENT_ORDER.map((name) => {
            const meta = COMPONENT_META[name];
            const value = score.components[name] ?? 0;
            const contribution = score.contributions[name] ?? 0;
            return (
              <tr key={name} className="border-b border-slate-100 last:border-0">
                <th scope="row" className="px-3 py-2.5 text-left font-normal">
                  <span className="block font-medium text-slate-950">{meta.label}</span>
                  <span className="mt-0.5 block text-xs leading-5 text-slate-500">
                    {meta.asks}
                  </span>
                </th>
                <td className="numeric px-3 py-2.5 text-right align-top font-medium text-slate-950">
                  {Math.round(value)}
                </td>
                <td className="numeric px-3 py-2.5 text-right align-top text-slate-500">
                  ×{SCORE_WEIGHTS[name].toFixed(2)}
                </td>
                <td className="numeric px-3 py-2.5 text-right align-top font-semibold text-slate-950">
                  {contribution.toFixed(2)}
                </td>
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          <tr className="border-t-2 border-slate-300 bg-slate-50">
            <th scope="row" className="px-3 py-2.5 text-left font-semibold text-slate-950">
              Total
            </th>
            <td colSpan={2} className="px-3 py-2.5 text-right text-xs text-slate-500">
              {check.ok ? "sum of the column" : "does not match the claimed total"}
            </td>
            <td className="numeric px-3 py-2.5 text-right font-semibold text-slate-950">
              {check.ok ? check.total.toFixed(2) : "—"}
            </td>
          </tr>
        </tfoot>
      </table>

      {!check.ok ? (
        <p className="flex items-start gap-2 border-t border-lane-safety-border bg-lane-safety-surface px-3 py-2.5 text-xs leading-5 text-lane-safety-ink">
          <TriangleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          <span>
            The backend claimed {check.claimed} but these components add to{" "}
            {check.recomputed.toFixed(2)}. The total is withheld rather than shown, because a
            priority figure that does not match its own inputs cannot be relied on.
          </span>
        </p>
      ) : check.capped ? (
        <p className="border-t border-slate-200 bg-slate-50 px-3 py-2.5 text-xs leading-5 text-slate-600">
          The weighted total is {check.uncappedTotal.toFixed(2)}, but this group is held below the
          High band because its evidence is still thin. Adding a photo, a second independent
          reporter, or an officer verification lifts the cap.
        </p>
      ) : null}
    </div>
  );
}
