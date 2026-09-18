"""Tests for ``civiclens.modules.relationships.grouping``.

This is the answer to the only question a ward officer really has: of everything
reported overnight, how many problems are there? So the tests are written as that
question, not as assertions about a data structure.

Two of them are here to stop a specific kind of quiet damage.
``test_matching_does_not_chain_across_a_ward`` guards against transitive clustering,
where a 1.5 km gate becomes a five-kilometre group and the output still looks like a
plausible number. ``test_a_live_hazard_never_disappears_into_an_operational_group``
guards the safety lane, where a wrong grouping is not a counting error but a hazard
nobody is sent to.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from civiclens.modules.relationships.evaluator import ReportFeatures
from civiclens.modules.relationships.grouping import (
    GroupingCandidate,
    GroupMember,
    IntentVerdict,
    group_reports,
)

# A junction in JP Nagar, and the times three people might report the same flood.
BASE_LAT = 12.9081
BASE_LON = 77.5831
MORNING = datetime(2026, 9, 15, 7, 30, tzinfo=UTC)

# About 1.1 km north at this latitude: inside the 1.5 km gate, so geometry accepts
# it, which is exactly the pair that needs something beyond geometry to settle.
ONE_KM = 0.0100


def _candidate(
    *,
    category: str = "WATERLOGGING",
    at: datetime = MORNING,
    lat: float | None = BASE_LAT,
    lon: float | None = BASE_LON,
    locality: str = "Sarakki junction",
    safety: bool = False,
    photo_hash: str | None = None,
) -> GroupingCandidate:
    return GroupingCandidate(
        features=ReportFeatures(
            report_id=uuid4(),
            category=category,
            event_at=at,
            locality_label=locality,
            latitude=lat,
            longitude=lon,
        ),
        safety_signalled=safety,
        photo_hash=photo_hash,
    )


def _ids(members: tuple[GroupMember, ...]) -> set[UUID]:
    return {member.report_id for member in members}


# --- the counting question -------------------------------------------------


def test_three_reports_of_one_flooded_junction_are_one_problem() -> None:
    reports = [
        _candidate(at=MORNING),
        _candidate(at=MORNING + timedelta(minutes=40)),
        _candidate(at=MORNING + timedelta(hours=3)),
    ]

    groups = group_reports(reports)

    assert len(groups) == 1
    assert groups[0].report_count == 3
    # The clock starts when the first person reported it. If the newest duplicate led
    # the group, every fresh complaint would reset the statutory deadline -- which is
    # the opposite of what repeated reporting should do.
    assert groups[0].first_reported_at == MORNING
    assert groups[0].lead_report_id == reports[0].features.report_id


def test_a_single_report_stays_a_single_report_and_claims_nothing() -> None:
    groups = group_reports([_candidate()])

    assert len(groups) == 1
    assert groups[0].report_count == 1
    assert groups[0].is_grouped is False
    # Not "review", not "not_eligible" -- absent. A lone report makes no claim about
    # being the same as anything, so there is no confidence in it to report.
    assert groups[0].confidence_band is None
    assert "not yet evidence" in groups[0].explanation


def test_different_categories_at_one_junction_stay_separate() -> None:
    """A pothole and a broken street light on one corner are two jobs, two crews."""
    groups = group_reports(
        [_candidate(category="ROAD_DAMAGE"), _candidate(category="STREET_LIGHT")]
    )

    assert len(groups) == 2
    assert all(group.report_count == 1 for group in groups)


def test_the_same_problem_reported_a_month_apart_is_not_one_report_twice() -> None:
    """Outside the 72-hour window. It may well be a recurrence, which is a different
    question, decided elsewhere, and never by merging the two into one count."""
    groups = group_reports([_candidate(at=MORNING), _candidate(at=MORNING + timedelta(days=30))])

    assert len(groups) == 2


# --- the guards ------------------------------------------------------------


def test_matching_does_not_chain_across_a_ward() -> None:
    """A matches B and B matches C must not put A with C.

    Every member is compared against the lead, so a group can never be wider than the
    gate. Without that rule a line of reports each 1 km from the last would collapse
    into one group spanning the whole road, and the only visible symptom would be a
    report count that looked slightly high.
    """
    lead = _candidate(at=MORNING, lat=BASE_LAT)
    middle = _candidate(at=MORNING + timedelta(hours=1), lat=BASE_LAT + ONE_KM)
    far = _candidate(at=MORNING + timedelta(hours=2), lat=BASE_LAT + 2 * ONE_KM)

    groups = group_reports([lead, middle, far])

    joined = next(group for group in groups if lead.features.report_id in _ids(group.members))
    assert middle.features.report_id in _ids(joined.members)
    # ~2.2 km from the lead: outside the gate, so it starts its own group rather than
    # riding in on its proximity to the middle report.
    assert far.features.report_id not in _ids(joined.members)
    assert len(groups) == 2


def test_a_live_hazard_never_disappears_into_an_operational_group() -> None:
    """Safety partitions before anything else runs.

    Same category, same junction, same hour -- and still separate, because one of them
    tripped a safety rule. Grouped, the hazard would be counted inside an operational
    item and its own lane would never show it.
    """
    hazard = _candidate(safety=True)
    ordinary = _candidate(at=MORNING + timedelta(minutes=10))

    groups = group_reports([hazard, ordinary])

    assert len(groups) == 2
    hazard_group = next(group for group in groups if group.safety_signalled)
    assert hazard_group.report_count == 1


def test_reports_still_awaiting_interpretation_are_never_grouped() -> None:
    """Category "unknown" means the interpreter has not run or could not answer.

    Grouping on an unknown category would merge whatever happened to be nearby, and
    the merge would be invisible once a category arrived later.
    """
    groups = group_reports([_candidate(category="unknown"), _candidate(category="unknown")])

    assert len(groups) == 2


# --- geometry first, then intent -------------------------------------------


def test_geometry_alone_proposes_but_never_claims_high_confidence() -> None:
    """The intent question is unanswered here, and the band has to say so.

    ``grouping-v1`` sets ``uncertainty_favors_separation``. Two reports 1 km apart
    pass a 1.5 km gate on coordinates alone, and coordinates cannot tell one flooded
    junction from two -- so this is a proposal at "review", not a finding.
    """
    groups = group_reports(
        [
            _candidate(at=MORNING),
            _candidate(at=MORNING + timedelta(hours=1), lat=BASE_LAT + ONE_KM),
        ]
    )

    assert len(groups) == 1
    assert groups[0].confidence_band == "review"
    assert "an officer confirms or separates" in groups[0].explanation


def test_a_reading_of_the_two_descriptions_can_split_what_geometry_joined() -> None:
    """Two potholes at one junction. This is the case geometry cannot solve.

    Same category, same coordinates, an hour apart: every deterministic gate says
    "one problem", and says it with the most confidence it has. Only something that
    reads the two descriptions can say they are two separate holes, and when it does,
    its answer wins over the geometry.
    """
    first = _candidate(category="ROAD_DAMAGE", at=MORNING)
    second = _candidate(category="ROAD_DAMAGE", at=MORNING + timedelta(hours=1))

    together = group_reports([first, second])
    apart = group_reports([first, second], intent_check=lambda lead, other: "disagree")

    assert len(together) == 1
    assert len(apart) == 2


def test_agreement_on_intent_earns_the_confidence_geometry_could_not() -> None:
    def agrees(lead: UUID, other: UUID) -> IntentVerdict:
        del lead, other
        return "agree"

    groups = group_reports(
        [_candidate(), _candidate(at=MORNING + timedelta(hours=1))], intent_check=agrees
    )

    assert len(groups) == 1
    assert groups[0].confidence_band == "high"
    assert "read as the same problem" in groups[0].explanation


def test_two_photos_of_the_same_thing_corroborate_without_any_model_looking() -> None:
    """The cheap version of the intent check, and it needs no AI at all.

    Difference hashes are already computed at upload for every photo. Two photographs
    of one flooded junction produce near-identical ones, and that is direct evidence
    about the subject rather than about the location -- which is the thing geometry was
    missing.
    """
    groups = group_reports(
        [
            _candidate(photo_hash="ffee00112233aabb"),
            _candidate(at=MORNING + timedelta(hours=1), photo_hash="ffee00112233aab3"),
        ]
    )

    assert len(groups) == 1
    assert groups[0].confidence_band == "high"
    assert "photos match" in groups[0].explanation


def test_photos_of_different_things_do_not_break_a_grouping() -> None:
    """Used in one direction only, on purpose.

    A difference hash moves with the light, the angle and the camera. Distant hashes
    are far too weak to separate two reports that every other gate accepted, so they
    leave the proposal standing at "review" for an officer to settle.
    """
    groups = group_reports(
        [
            _candidate(photo_hash="0000000000000000"),
            _candidate(at=MORNING + timedelta(hours=1), photo_hash="ffffffffffffffff"),
        ]
    )

    assert len(groups) == 1
    assert groups[0].confidence_band == "review"


def test_a_malformed_stored_hash_degrades_instead_of_breaking_the_board() -> None:
    """It comes out of a database column, so it can be anything.

    A row written by an older version, or by hand during an incident, must cost the
    photo evidence and nothing else -- an officer's morning board is not worth a 500.
    """
    groups = group_reports(
        [
            _candidate(photo_hash="not-a-hash"),
            _candidate(at=MORNING + timedelta(hours=1), photo_hash="ffee00112233aabb"),
        ]
    )

    assert len(groups) == 1
    assert groups[0].confidence_band == "review"


# --- properties ------------------------------------------------------------


def test_a_group_is_only_as_certain_as_its_weakest_member() -> None:
    """One shaky link caps the whole group.

    Reporting the group at the confidence of its best pair would let a photo-matched
    pair carry a third report that nothing corroborated, and the count an officer
    trusts would be built on the member nobody checked.
    """
    photo = "ffee00112233aabb"
    groups = group_reports(
        [
            _candidate(photo_hash=photo),
            _candidate(at=MORNING + timedelta(hours=1), photo_hash=photo),
            _candidate(at=MORNING + timedelta(hours=2)),
        ]
    )

    assert len(groups) == 1
    assert groups[0].report_count == 3
    assert groups[0].confidence_band == "review"


def test_the_order_reports_arrive_in_does_not_change_the_answer() -> None:
    """Otherwise the officer board would differ between two page loads."""
    reports = [
        _candidate(at=MORNING),
        _candidate(at=MORNING + timedelta(hours=1)),
        _candidate(category="ROAD_DAMAGE", at=MORNING + timedelta(hours=2)),
    ]

    forward = group_reports(reports)
    backward = group_reports(list(reversed(reports)))

    assert [group.lead_report_id for group in forward] == [
        group.lead_report_id for group in backward
    ]
    assert [group.report_count for group in forward] == [group.report_count for group in backward]


def test_every_report_lands_in_exactly_one_group() -> None:
    """No report is dropped and none is counted twice.

    The failure this catches is silent in both directions: a dropped report is a
    citizen who was told their complaint was received and whose complaint no officer
    ever sees, and a duplicated one inflates the count that decides what gets fixed.
    """
    reports = [
        _candidate(),
        _candidate(at=MORNING + timedelta(hours=1)),
        _candidate(category="ROAD_DAMAGE"),
        _candidate(safety=True),
        _candidate(category="unknown"),
        _candidate(at=MORNING + timedelta(days=40)),
    ]

    groups = group_reports(reports)

    placed = [member.report_id for group in groups for member in group.members]
    assert sorted(placed, key=str) == sorted(
        (report.features.report_id for report in reports), key=str
    )


def test_the_pairwise_evidence_survives_into_the_group() -> None:
    """So a disputed grouping can be shown the actual numbers, not a summary.

    An officer who thinks two reports were wrongly merged is owed the distance, the
    hours and the category match that merged them. A confidence band alone is not
    something anybody can argue with.
    """
    groups = group_reports(
        [_candidate(), _candidate(at=MORNING + timedelta(hours=1), lat=BASE_LAT + ONE_KM)]
    )

    joined = next(member for member in groups[0].members if member.joined_by != "lead")
    assert joined.evidence["category_match"] is True
    assert isinstance(joined.evidence["distance_km"], float)
    assert joined.evidence["hours_apart"] == 1.0
    assert joined.evidence["intent_verdict"] == "abstain"
