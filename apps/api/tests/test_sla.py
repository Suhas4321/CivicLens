from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from civiclens.domain.sla import (
    PausedInterval,
    compensation_rupees,
    due_at,
    resume_after_pause,
    sla_state,
)

KOLKATA = ZoneInfo("Asia/Kolkata")
FIRST_REPORTED_AT = datetime(2026, 9, 1, 10, 30, tzinfo=KOLKATA)


def end_of(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, 23, 59, 59, tzinfo=KOLKATA)


@pytest.mark.parametrize(
    ("service_code", "sla_days"),
    [
        ("ELECTRICAL_HAZARD", 1),
        ("WATER_CONTAMINATION", 1),
        ("SEWAGE_OVERFLOW", 2),
        ("TREE_HAZARD", 2),
        ("WATER_SUPPLY", 3),
        ("WATERLOGGING", 3),
        ("GARBAGE", 3),
        ("STREET_LIGHT", 7),
        ("STRAY_ANIMALS", 7),
        ("BUS_STOP", 10),
        ("ROAD_DAMAGE", 15),
    ],
)
def test_due_at_falls_at_the_end_of_the_nth_calendar_day(service_code: str, sla_days: int) -> None:
    deadline = due_at(service_code, FIRST_REPORTED_AT)

    assert deadline.date() == (FIRST_REPORTED_AT + timedelta(days=sla_days)).date()
    assert deadline.timetz() == end_of(2026, 1, 1).timetz()


def test_deadline_does_not_depend_on_the_hour_the_first_report_arrived() -> None:
    """Two reports on the same date share a deadline.

    The group's clock is set by whichever neighbour happened to report first. If
    the hour leaked into the deadline, a report at ten past midnight and one at
    ten to midnight on the same date would owe different amounts on the same day.
    """
    just_after_midnight = due_at("GARBAGE", datetime(2026, 9, 1, 0, 10, tzinfo=KOLKATA))
    just_before_midnight = due_at("GARBAGE", datetime(2026, 9, 1, 23, 50, tzinfo=KOLKATA))

    assert just_after_midnight == just_before_midnight == end_of(2026, 9, 4)


def test_deadline_is_computed_in_kolkata_not_utc() -> None:
    """22:00 UTC is already the next date in Bengaluru.

    A one-day deadline on a report stamped 2026-09-01T22:00Z is due at the end of
    the 3rd locally, not the 2nd: the report itself landed on the 2nd in IST.
    Getting this wrong shifts every late-evening report's deadline by a full day.
    """
    assert due_at("ELECTRICAL_HAZARD", datetime(2026, 9, 1, 22, 0, tzinfo=UTC)) == end_of(
        2026, 9, 3
    )


def test_naive_timestamps_are_refused() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        due_at("GARBAGE", datetime(2026, 9, 1, 10, 30))  # noqa: DTZ001


def test_other_has_no_deadline_until_classified() -> None:
    with pytest.raises(ValueError, match="until it is classified"):
        due_at("OTHER", FIRST_REPORTED_AT)


def test_unknown_code_is_not_silently_given_a_deadline() -> None:
    with pytest.raises(KeyError):
        due_at("POTHOLE", FIRST_REPORTED_AT)


def test_the_whole_deadline_day_is_still_due_today() -> None:
    deadline = due_at("GARBAGE", FIRST_REPORTED_AT)

    for moment in (
        datetime(2026, 9, 4, 0, 0, tzinfo=KOLKATA),
        datetime(2026, 9, 4, 12, 0, tzinfo=KOLKATA),
        deadline,
    ):
        result = sla_state(deadline, moment)
        assert result.state == "due_today"
        assert result.days_overdue == 0


def test_before_the_deadline_day_is_within() -> None:
    deadline = due_at("GARBAGE", FIRST_REPORTED_AT)

    result = sla_state(deadline, datetime(2026, 9, 3, 23, 0, tzinfo=KOLKATA))

    assert result.state == "within"
    assert result.days_overdue == 0


def test_overdue_counts_dates_and_does_not_move_during_the_day() -> None:
    """The morning figure and the evening figure must agree.

    This is the property that lets the same number appear on the officer board
    and on the citizen's receipt: one date past the deadline is one day overdue
    all day, so the ₹20 beside it does not change while nothing has happened.
    """
    deadline = due_at("GARBAGE", FIRST_REPORTED_AT)

    morning = sla_state(deadline, datetime(2026, 9, 5, 6, 0, tzinfo=KOLKATA))
    evening = sla_state(deadline, datetime(2026, 9, 5, 22, 0, tzinfo=KOLKATA))

    assert morning == evening
    assert morning.state == "overdue"
    assert morning.days_overdue == 1


def test_overdue_grows_by_one_per_date() -> None:
    deadline = due_at("GARBAGE", FIRST_REPORTED_AT)

    assert sla_state(deadline, datetime(2026, 9, 10, 9, 0, tzinfo=KOLKATA)).days_overdue == 6
    assert sla_state(deadline, datetime(2026, 9, 15, 9, 30, tzinfo=KOLKATA)).days_overdue == 11


def test_closure_freezes_the_count_at_the_closure_date() -> None:
    """A late closure keeps the days it was late by.

    Passing the closure time rather than the present is what stops the number
    climbing after the work is done, and what stops the compensation being
    erased by finishing the job: two days late stays two days late.
    """
    deadline = due_at("STREET_LIGHT", datetime(2026, 9, 3, 19, 45, tzinfo=KOLKATA))
    closed_at = datetime(2026, 9, 12, 11, 5, tzinfo=KOLKATA)

    at_closure = sla_state(deadline, closed_at)

    assert deadline == end_of(2026, 9, 10)
    assert at_closure.days_overdue == 2
    assert compensation_rupees(at_closure.days_overdue) == 40


def test_compensation_is_twenty_rupees_per_day_with_five_hundred_cap() -> None:
    assert compensation_rupees(0) == 0
    assert compensation_rupees(1) == 20
    assert compensation_rupees(25) == 500
    assert compensation_rupees(26) == 500


def test_resume_after_pause_preserves_the_remaining_time() -> None:
    """A disputed closure returns the days that were left, not a new deadline."""
    deadline = due_at("ROAD_DAMAGE", FIRST_REPORTED_AT)
    paused_at = datetime(2026, 9, 13, 10, 0, tzinfo=KOLKATA)
    resumed_at = datetime(2026, 9, 18, 15, 0, tzinfo=KOLKATA)

    resumed_deadline = resume_after_pause(
        deadline, PausedInterval(paused_at=paused_at, resumed_at=resumed_at)
    )

    assert deadline == end_of(2026, 9, 16)
    assert resumed_deadline == end_of(2026, 9, 21)
    # Three dates remained when the clock stopped; three remain now.
    assert (deadline.date() - paused_at.date()).days == 3
    assert (resumed_deadline.date() - resumed_at.date()).days == 3


def test_a_same_day_dispute_does_not_extend_the_deadline() -> None:
    deadline = due_at("GARBAGE", FIRST_REPORTED_AT)
    claimed_at = datetime(2026, 9, 3, 9, 0, tzinfo=KOLKATA)

    resumed = resume_after_pause(
        deadline,
        PausedInterval(paused_at=claimed_at, resumed_at=claimed_at + timedelta(hours=6)),
    )

    assert resumed == deadline


def test_a_pause_that_starts_after_the_deadline_still_only_adds_its_own_days() -> None:
    """Pausing while already overdue cannot retire the delay already accrued."""
    deadline = due_at("GARBAGE", FIRST_REPORTED_AT)
    paused_at = datetime(2026, 9, 8, 10, 0, tzinfo=KOLKATA)
    resumed_at = datetime(2026, 9, 10, 10, 0, tzinfo=KOLKATA)

    resumed = resume_after_pause(
        deadline, PausedInterval(paused_at=paused_at, resumed_at=resumed_at)
    )

    assert resumed == end_of(2026, 9, 6)
    assert sla_state(resumed, resumed_at).days_overdue == 4


def test_a_pause_cannot_run_backwards() -> None:
    with pytest.raises(ValueError, match="must not be before"):
        PausedInterval(
            paused_at=datetime(2026, 9, 10, 10, 0, tzinfo=KOLKATA),
            resumed_at=datetime(2026, 9, 9, 10, 0, tzinfo=KOLKATA),
        )
