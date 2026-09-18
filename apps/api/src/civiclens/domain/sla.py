"""Pure SLA deadline, state, compensation and pause calculations.

CivicLens uses calendar days, not working days, in ``Asia/Kolkata``. Civic
problems continue through weekends and holidays, so the clock must not quietly
extend for either. The initial clock always starts at the problem group's
``first_reported_at``, never at an individual report's timestamp
(``REBUILD_04`` §4.2).

**A day here is a date, not twenty-four hours.** A three-day deadline on a
problem first reported at 23:50 on 1 September falls at the end of 4 September,
not at 23:50 on the 4th. Three consequences, and each is the reason for the
choice:

* It is the reading a resident can check. "Reported on the 1st, three-day
  service, so it was due on the 4th" is countable on a wall calendar. "Due at
  23:50 on the 4th" is not, and the resident cannot even explain where 23:50
  came from — it is the hour a neighbour they never met happened to report.
* ``days_overdue`` stops moving during the day. Under 24-hour blocks the number
  ticks over at whatever hour the group was first reported, so the officer
  board at 09:00 and the citizen's receipt at 21:00 would print different
  figures for the same unchanged problem, and so would the rupee amount beside
  them.
* It is how the statute is written. Sakala expresses limits in days from the
  date of receipt, and the ₹20-per-day compensation this models is a per-day
  entitlement, so counting in days is what makes the figure arguable.

The cost is that service time is no longer uniform: a problem reported just
after midnight gets almost a full extra day compared with one reported just
before it. That is accepted deliberately. Uniform service time benefits nobody
who can observe it; a deadline the reporter can verify benefits the person the
deadline exists for.

The versioned category catalogue is loaded once as immutable module policy.
The calculation functions themselves perform no database access or I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Final, Literal
from zoneinfo import ZoneInfo

from civiclens.domain.categories import CategoryConfig, load_category_config

SlaStateName = Literal["within", "due_today", "overdue"]

_CATEGORY_CONFIG_VERSION: Final = "bengaluru-south-v1"
_KOLKATA: Final = ZoneInfo("Asia/Kolkata")
_CATEGORY_CONFIG: Final[CategoryConfig] = load_category_config(_CATEGORY_CONFIG_VERSION)

# The last second of the deadline day. Every comparison below is made on dates,
# so this time is not load-bearing arithmetic — it exists so that a rendered
# deadline reads "10 Sep 2026, 11:59 pm", which a reporter understands as the end
# of the 10th. The alternative exact boundary, midnight on the 11th, is the same
# instant and displays as the wrong date.
_END_OF_DAY: Final = time(23, 59, 59)


@dataclass(frozen=True)
class SlaState:
    state: SlaStateName
    days_overdue: int


@dataclass(frozen=True)
class PausedInterval:
    """A stretch during which the clock did not run.

    Raised by a claimed closure that the reporter later disputes: between those
    two events the body believed the work was finished, so the days do not count
    against it. The dispute resumes the clock where it paused rather than
    restarting it — a closure claim cannot be used to buy a fresh deadline.
    """

    paused_at: datetime
    resumed_at: datetime

    def __post_init__(self) -> None:
        if _in_kolkata(self.resumed_at) < _in_kolkata(self.paused_at):
            raise ValueError("resumed_at must not be before paused_at")

    @property
    def paused_days(self) -> int:
        """Whole dates the clock skipped.

        Days, not hours, because the deadline is a date: a clock that only
        advances at day granularity can only be paused at day granularity. A
        closure claimed and disputed on the same date returns 0 — nothing was
        skipped, because the day in question had not finished either way.
        """
        return (_in_kolkata(self.resumed_at).date() - _in_kolkata(self.paused_at).date()).days


def due_at(service_code: str, first_reported_at: datetime) -> datetime:
    """Return the end of the deadline day for a problem group's first report."""
    category = _CATEGORY_CONFIG.by_code(service_code)
    if category.code == "OTHER":
        # Not a default of seven days. An unclassified report has no agency to
        # hold to a deadline, and inventing one would put a number on the
        # citizen's receipt that no department has accepted.
        raise ValueError("OTHER has no SLA deadline until it is classified")
    deadline_date = _in_kolkata(first_reported_at).date() + timedelta(days=category.sla_days)
    return datetime.combine(deadline_date, _END_OF_DAY, tzinfo=_KOLKATA)


def sla_state(deadline: datetime, now: datetime) -> SlaState:
    """Classify a deadline and count whole dates elapsed past it.

    ``now`` is the moment being asked about, which for a closed problem is the
    closure time, not the present. An overdue count that kept climbing after the
    work was done would misstate both the record and the compensation.
    """
    due_date = _in_kolkata(deadline).date()
    asked_date = _in_kolkata(now).date()

    if asked_date > due_date:
        return SlaState(state="overdue", days_overdue=(asked_date - due_date).days)
    if asked_date == due_date:
        return SlaState(state="due_today", days_overdue=0)
    return SlaState(state="within", days_overdue=0)


def compensation_rupees(days_overdue: int) -> int:
    """Return ₹20 per complete overdue day, capped at ₹500."""
    if days_overdue < 1:
        return 0
    return min(days_overdue * 20, 500)


def resume_after_pause(deadline: datetime, interval: PausedInterval) -> datetime:
    """Push a deadline out by the dates the clock was paused for."""
    local = _in_kolkata(deadline)
    # Recombined rather than offset, so the result is still the end of a day. A
    # deadline that drifted to 02:59:59 after a pause would be unreadable, and
    # every comparison downstream reads its date anyway.
    return datetime.combine(
        local.date() + timedelta(days=interval.paused_days), _END_OF_DAY, tzinfo=_KOLKATA
    )


def _in_kolkata(value: datetime) -> datetime:
    if value.tzinfo is None:
        # Deliberately a failure, not an assumption. Everything upstream produces
        # aware UTC timestamps (`datetime.now(UTC)`), so a naive value arriving
        # here is a bug in the caller — and reading a naive UTC timestamp as IST
        # would shift it 5h30m, which is enough to move a deadline across a date
        # boundary and change what the citizen is owed. Better to stop.
        raise ValueError("SLA calculations require timezone-aware datetimes")
    return value.astimezone(_KOLKATA)
