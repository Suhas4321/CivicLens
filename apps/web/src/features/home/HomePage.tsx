import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Camera,
  CheckCircle2,
  Clock,
  FlaskConical,
  Layers,
  MapPin,
  ReceiptText,
  ShieldOff,
  TriangleAlert,
} from "lucide-react";
import { Link } from "react-router-dom";

import { loadCategories, loadPublicWardBoard } from "@/api/pendingBackend";
import { AGENCY_META, type Category, type WardBacklog } from "@/api/priority";
import { Button } from "@/components/ui/button";
import { formatDateTime } from "@/lib/time";
import { ApiError, fetchVersion } from "../../api/health";

/**
 * The public front page.
 *
 * What it used to be: a five-step diagram — Reports → Incidents → Civic need →
 * Project candidate → Human decision — over a marketing hero. REBUILD_00 §2
 * records why that had to go. None of those five stages existed in the running
 * system, the vocabulary was invented for the diagram rather than taken from the
 * work, and a resident reading it learned nothing they could act on or check.
 *
 * What it is now: the backlog. Three numbers per area, each labelled with the
 * period it covers, plus the one thing a resident is actually owed — the legal
 * deadline for their category and the compensation if it is missed. If those
 * numbers are bad, the page shows them as bad. A civic site whose front page can
 * only ever look good is not reporting on anything.
 *
 * Two deliberate omissions. There is no score, band or lane here: ranking is an
 * officer's judgment and a resident has no way to argue with a number on a
 * homepage. And there is no map, for the reason given in LocationPicker.
 *
 * Sizing and touch targets come from `[data-surface="public"]` in styles/civic.css
 * — 18px body text and a 48px minimum on anything tappable — so this page does not
 * set its own type scale. The officer surface sets the opposite, which is what
 * makes the two feel like different tools rather than one half-finished one.
 */

export function HomePage() {
  const boardQuery = useQuery({
    queryKey: ["public-ward-board"],
    queryFn: ({ signal }) => loadPublicWardBoard(signal),
  });

  return (
    <div className="page-shell pb-14 pt-8 sm:pt-12">
      <Hero />
      <WardBacklog
        wards={boardQuery.data?.data.wards}
        windowDays={boardQuery.data?.data.window_days ?? 7}
        generatedAt={boardQuery.data?.data.generated_at}
        disclosure={boardQuery.data?.data.disclosure}
        isFixture={boardQuery.data?.source === "fixture"}
        isPending={boardQuery.isPending}
        error={boardQuery.error}
      />
      <AfterYouReport />
      <Deadlines />
      <SystemStrip />
    </div>
  );
}

/* -------------------------------------------------------------------------- */

function Hero() {
  return (
    <section className="max-w-3xl">
      <h1 className="text-balance text-[clamp(2.1rem,5vw,3.4rem)] font-semibold leading-[1.08] tracking-[-0.03em] text-slate-950">
        Report a problem on your street.
      </h1>
      <p className="mt-2 text-[clamp(1.25rem,3vw,1.75rem)] font-medium leading-snug text-slate-700">
        ನಿಮ್ಮ ಬೀದಿಯ ಸಮಸ್ಯೆಯನ್ನು ವರದಿ ಮಾಡಿ.
      </p>
      <p className="mt-5 max-w-2xl text-pretty leading-relaxed text-slate-700">
        A photo and the name of the road are enough. Your report is grouped with everyone else who
        reported the same thing, sent to the department responsible for it, and given a deadline set
        by law — not by us.
      </p>

      <div className="mt-7 flex flex-col gap-3 sm:flex-row sm:items-center">
        <Button asChild size="lg" className="h-14 rounded-xl px-7 text-lg">
          <Link to="/report">
            Report a problem
            <ArrowRight aria-hidden />
          </Link>
        </Button>
        <p className="text-base text-slate-600">
          ಸಮಸ್ಯೆಯನ್ನು ವರದಿ ಮಾಡಿ · takes about a minute
        </p>
      </div>

      <ul className="mt-7 flex flex-wrap gap-x-7 gap-y-2.5 border-t border-slate-200 pt-5 text-base text-slate-600">
        <li className="flex items-center gap-2">
          <Camera className="size-5 shrink-0 text-slate-500" aria-hidden />
          A photo helps, and is not required
        </li>
        <li className="flex items-center gap-2">
          <ShieldOff className="size-5 shrink-0 text-slate-500" aria-hidden />
          No name, no phone number, no house number
        </li>
        <li className="flex items-center gap-2">
          <ReceiptText className="size-5 shrink-0 text-slate-500" aria-hidden />
          You get a reference number to check later
        </li>
      </ul>
    </section>
  );
}

/* -------------------------------------------------------------------------- */

/**
 * The backlog, per area.
 *
 * This section fails on its own. If the query is pending or broken the heading
 * and the report button above are already usable, because the page's job is to
 * let someone report a problem and that must never depend on a dashboard query
 * succeeding.
 *
 * Each figure carries its own period in words. `reported` and `fixed` cover the
 * window; `past deadline` is a count of right now, because restricting it to the
 * window would hide the problems that have been overdue longest.
 */
function WardBacklog({
  wards,
  windowDays,
  generatedAt,
  disclosure,
  isFixture,
  isPending,
  error,
}: {
  wards: readonly WardBacklog[] | undefined;
  windowDays: number;
  generatedAt: string | undefined;
  disclosure: string | undefined;
  isFixture: boolean;
  isPending: boolean;
  error: unknown;
}) {
  return (
    <section aria-labelledby="backlog" className="mt-14">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
        <div>
          <h2 id="backlog" className="text-2xl font-semibold tracking-[-0.02em] text-slate-950">
            What is happening in your area
          </h2>
          <p className="mt-1 text-lg text-slate-600">ನಿಮ್ಮ ಪ್ರದೇಶದಲ್ಲಿ ಏನಾಗುತ್ತಿದೆ</p>
        </div>
        {generatedAt ? (
          <p className="numeric text-sm text-slate-500">Counted {formatDateTime(generatedAt)}</p>
        ) : null}
      </div>

      {isFixture ? (
        <p className="mt-4 flex items-start gap-2.5 rounded-xl border border-lane-statutory-border bg-lane-statutory-surface px-4 py-3 text-base leading-relaxed text-lane-statutory-ink">
          <FlaskConical className="mt-1 size-5 shrink-0" aria-hidden />
          <span>
            <strong className="font-semibold">These are made-up numbers.</strong> The endpoint that
            returns the real backlog has not been built yet, so this is local demonstration data.
            This notice removes itself the moment there is something real to show.
          </span>
        </p>
      ) : null}

      {isPending ? (
        <p className="mt-5 text-base text-slate-500" aria-live="polite">
          Counting…
        </p>
      ) : error ? (
        <p className="mt-5 flex items-start gap-2.5 rounded-xl border border-slate-300 bg-white px-4 py-3 text-base leading-relaxed text-slate-700">
          <TriangleAlert className="mt-1 size-5 shrink-0 text-slate-500" aria-hidden />
          <span>
            The area counts could not be loaded
            {error instanceof ApiError ? ` (${error.status})` : ""}. Reporting a problem still works
            — the button above does not depend on this.
          </span>
        </p>
      ) : (
        <>
          <div className="mt-5 grid gap-4 md:grid-cols-3">
            {wards?.map((entry) => (
              <article
                key={entry.ward.id}
                className="rounded-2xl border border-slate-200 bg-white p-5"
              >
                <h3 className="flex items-center gap-2 text-xl font-semibold text-slate-950">
                  <MapPin className="size-5 shrink-0 text-slate-400" aria-hidden />
                  {entry.ward.name}
                </h3>
                <dl className="mt-4 space-y-3">
                  <Figure
                    value={entry.reported}
                    label="reported"
                    labelKn="ವರದಿಯಾಗಿದೆ"
                    period={`in the last ${windowDays} days`}
                  />
                  <Figure
                    value={entry.resolved}
                    label="marked fixed"
                    labelKn="ಪರಿಹಾರವಾಗಿದೆ"
                    period={`in the last ${windowDays} days`}
                    tone="good"
                    icon={CheckCircle2}
                  />
                  <Figure
                    value={entry.past_deadline}
                    label="past the legal deadline"
                    labelKn="ಗಡುವು ಮೀರಿದೆ"
                    period="right now"
                    tone={entry.past_deadline > 0 ? "bad" : "neutral"}
                    icon={Clock}
                  />
                </dl>
              </article>
            ))}
          </div>

          {/* Said once, in the words a resident would use, rather than the
            * provenance vocabulary the officer surface uses. */}
          <p className="mt-4 text-sm leading-relaxed text-slate-500">
            These areas are taken from a public map, not from the corporation's own ward list.
            Bengaluru South City Corporation was created in September 2025 and the boundaries of its
            72 wards are not published in a form this system can use, so an area here may not match
            your ward exactly.
            {disclosure ? ` ${disclosure}` : ""}
          </p>
        </>
      )}
    </section>
  );
}

function Figure({
  value,
  label,
  labelKn,
  period,
  tone = "neutral",
  icon: Icon,
}: {
  value: number;
  label: string;
  labelKn: string;
  period: string;
  tone?: "neutral" | "good" | "bad";
  icon?: typeof Clock;
}) {
  return (
    <div className="flex items-baseline gap-3">
      <dd
        className={
          "numeric w-12 shrink-0 text-right text-3xl font-semibold " +
          (tone === "bad"
            ? "text-lane-statutory-ink"
            : tone === "good"
              ? "text-emerald-700"
              : "text-slate-950")
        }
      >
        {value}
      </dd>
      <dt className="min-w-0">
        <span className="flex items-center gap-1.5 font-medium text-slate-800">
          {Icon ? <Icon className="size-4 shrink-0 text-slate-400" aria-hidden /> : null}
          {label}
        </span>
        <span className="mt-0.5 block text-sm text-slate-500">
          {labelKn} · {period}
        </span>
      </dt>
    </div>
  );
}

/* -------------------------------------------------------------------------- */

const STEPS = [
  {
    icon: ReceiptText,
    title: "You get a reference number",
    titleKn: "ನಿಮಗೆ ಒಂದು ಸಂಖ್ಯೆ ಸಿಗುತ್ತದೆ",
    body: "Write it down or keep the page. It is the only way to check your own report, because we do not ask for your name or your phone number.",
  },
  {
    icon: Layers,
    title: "Your report joins the others",
    titleKn: "ನಿಮ್ಮ ವರದಿ ಇತರರೊಂದಿಗೆ ಸೇರುತ್ತದೆ",
    body: "If four people report the same broken pipe, that is one problem with four reporters — not four problems. Separate reporters are what make a problem harder to ignore, so reporting something a neighbour already reported is still worth doing.",
  },
  {
    icon: Clock,
    title: "A deadline starts, set by law",
    titleKn: "ಕಾನೂನಿನ ಗಡುವು ಶುರುವಾಗುತ್ತದೆ",
    body: "The clock runs from the first report about that problem, not from when your report arrived. Miss it and the Karnataka Guarantee of Services to Citizens Act entitles you to ₹20 for each day late, up to ₹500.",
  },
  {
    icon: CheckCircle2,
    title: "Someone says it is fixed — and you can disagree",
    titleKn: "ಪರಿಹಾರವಾಗಿದೆ ಎಂದರೆ ನೀವು ಒಪ್ಪದಿರಬಹುದು",
    body: "A closure is a claim, not proof. If you say it is not fixed, the deadline picks up where it stopped instead of starting again.",
  },
];

function AfterYouReport() {
  return (
    <section aria-labelledby="after" className="mt-14">
      <h2 id="after" className="text-2xl font-semibold tracking-[-0.02em] text-slate-950">
        What happens after you report
      </h2>
      <p className="mt-1 text-lg text-slate-600">ವರದಿ ಮಾಡಿದ ನಂತರ ಏನಾಗುತ್ತದೆ</p>

      <ol className="mt-5 grid gap-4 sm:grid-cols-2">
        {STEPS.map(({ icon: Icon, title, titleKn, body }, index) => (
          <li key={title} className="rounded-2xl border border-slate-200 bg-white p-5">
            <div className="flex items-center gap-3">
              <span className="numeric grid size-9 shrink-0 place-items-center rounded-full bg-slate-900 text-base font-semibold text-white">
                {index + 1}
              </span>
              <Icon className="size-5 text-slate-400" aria-hidden />
            </div>
            <h3 className="mt-3.5 text-lg font-semibold leading-snug text-slate-950">{title}</h3>
            <p className="mt-1 text-base text-slate-600">{titleKn}</p>
            <p className="mt-2.5 text-base leading-relaxed text-slate-700">{body}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}

/* -------------------------------------------------------------------------- */

/**
 * The deadlines, published.
 *
 * This is the most useful thing on the page and it is not a design flourish: a
 * resident who knows garbage carries a three-day deadline can hold someone to it,
 * and one who does not, cannot. The figures come from
 * `config/categories/bengaluru-south-v1.json` — the same file the backend scores
 * from — so this table cannot drift from what the system actually enforces.
 */
function Deadlines() {
  const query = useQuery({
    queryKey: ["categories"],
    queryFn: ({ signal }) => loadCategories(signal),
    staleTime: 60 * 60 * 1000,
  });

  if (query.isPending || query.isError) return null;

  const categories = [...query.data.data.categories].sort(
    (a, b) => a.sla_days - b.sla_days || a.label_en.localeCompare(b.label_en),
  );

  return (
    <section aria-labelledby="deadlines" className="mt-14">
      <h2 id="deadlines" className="text-2xl font-semibold tracking-[-0.02em] text-slate-950">
        How long they have
      </h2>
      <p className="mt-1 text-lg text-slate-600">ಎಷ್ಟು ದಿನಗಳ ಗಡುವು</p>
      <p className="mt-3 max-w-2xl text-base leading-relaxed text-slate-700">
        Counted in calendar days from the first report, including Sundays and holidays.
      </p>

      <ul className="mt-5 grid gap-x-6 gap-y-0 sm:grid-cols-2">
        {categories.map((category) => (
          <li
            key={category.code}
            className="flex items-baseline justify-between gap-4 border-b border-slate-200 py-3.5"
          >
            <span className="min-w-0">
              <span className="block font-medium text-slate-950">{category.label_en}</span>
              <span className="block text-base text-slate-600">{category.label_kn}</span>
              <span className="mt-0.5 block text-sm text-slate-500">
                {agencyLabel(category)}
              </span>
            </span>
            <span className="numeric shrink-0 whitespace-nowrap text-lg font-semibold text-slate-950">
              {category.sla_days} {category.sla_days === 1 ? "day" : "days"}
            </span>
          </li>
        ))}
      </ul>

      <p className="mt-4 text-sm leading-relaxed text-slate-500">
        A live electrical hazard, contaminated water or sewage in the street is not put in a queue
        behind anything. Those are handled in the order they arrive, and nothing about them is
        ranked or scored.
      </p>
    </section>
  );
}

function agencyLabel(category: Category): string {
  if (!category.agency) return "Assigned by an officer once the category is confirmed";
  const meta = AGENCY_META[category.agency];
  return `${meta.name} · ${meta.nameKn}`;
}

/* -------------------------------------------------------------------------- */

/**
 * System status and the way in for staff.
 *
 * The officer portal is linked from down here rather than beside the report
 * button. A resident arriving on this page has one job, and offering them a
 * "decision console" as a co-equal choice was part of why the two surfaces read
 * as one undifferentiated site.
 */
function SystemStrip() {
  const versionQuery = useQuery({
    queryKey: ["health", "version"],
    queryFn: ({ signal }) => fetchVersion(signal),
  });

  const label = versionQuery.isPending
    ? "Checking the connection…"
    : versionQuery.data
      ? "Connected to the pilot system"
      : versionQuery.error instanceof ApiError
        ? `The pilot system is not responding (${versionQuery.error.status})`
        : "Running without a backend connection";

  return (
    <footer className="mt-14 flex flex-wrap items-center justify-between gap-x-6 gap-y-3 border-t border-slate-200 pt-5 text-sm text-slate-500">
      <p className="flex items-center gap-2" aria-live="polite">
        <span
          className={
            "size-2 rounded-full " +
            (versionQuery.data
              ? "bg-emerald-500"
              : versionQuery.isPending
                ? "bg-amber-400"
                : "bg-slate-400")
          }
        />
        {label}
        <span className="text-slate-400">· every report here is synthetic test data</span>
      </p>
      <Link to="/officer" className="font-medium text-slate-600 underline">
        Council staff sign-in
      </Link>
    </footer>
  );
}
