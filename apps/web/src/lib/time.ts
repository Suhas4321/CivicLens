/**
 * Time formatting, fixed to Asia/Kolkata.
 *
 * Statutory deadlines are counted in calendar days in Asia/Kolkata — that is a
 * decision recorded in the SLA module, and the UI has to agree with it or an
 * officer in a different timezone would see a different number of days overdue
 * than the one the law is being applied on. So the zone is pinned here rather
 * than taken from the browser.
 */

const ZONE = "Asia/Kolkata";

const dateTime = new Intl.DateTimeFormat("en-IN", {
  timeZone: ZONE,
  day: "numeric",
  month: "short",
  hour: "numeric",
  minute: "2-digit",
  hour12: true,
});

const dateOnly = new Intl.DateTimeFormat("en-IN", {
  timeZone: ZONE,
  day: "numeric",
  month: "short",
  year: "numeric",
});

export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "—" : dateTime.format(date);
}

export function formatDate(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "—" : dateOnly.format(date);
}

/**
 * "3h ago", "2d ago". Deliberately terse: it sits in a dense table where the
 * exact instant is one hover away and the useful fact is the order of magnitude.
 */
export function relativeTime(iso: string, now: number = Date.now()): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";

  const minutes = Math.round((now - then) / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;

  return formatDate(iso);
}

/** Hours elapsed, used by the safety lane where minutes still matter. */
export function hoursSince(iso: string, now: number = Date.now()): number | null {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return null;
  return (now - then) / 3_600_000;
}
