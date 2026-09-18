"""The officer board, end to end, once grouping runs on live submissions.

``test_report_grouping.py`` proves the policy. This proves it is actually wired into
what an officer sees: reports submitted through the public form, interpreted by the
fixture interpreter, and read back off ``/officer/overview`` as problems rather than
as a list of complaints.

The load-bearing one is
``test_three_people_reporting_one_pothole_make_one_item_not_three``. Before this, a
morning with forty reports of one flooded junction produced forty items, and the
officer did the deduplication by eye -- which is the work this system exists to do.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from civiclens.infrastructure.ai.fake import FixtureInterpreter
from civiclens.main import app
from civiclens.modules.analysis.service import ReportAnalysisService
from civiclens.modules.intake import api as intake_api
from civiclens.modules.intake.repository import MemoryIntakeRepository
from civiclens.modules.intake.service import (
    IntakeService,
    get_intake_repository,
    get_intake_service,
)

# One junction in JP Nagar, and a second point about 3 km away -- outside the 1.5 km
# gate, so the two cannot be one problem however similar the words are.
JUNCTION = (12.9081, 77.5831)
ACROSS_THE_WARD = (12.9351, 77.5831)

# Chosen for what the fixture interpreter makes of them, which is the same thing the
# real interpreter would: "pothole" is an operational road complaint with no safety
# signal, and chemical-smelling hospital water is a safety signal. Neither text
# mentions water alongside the pothole, because that combination is deliberately read
# as "unknown" and an unknown category never groups.
POTHOLE = "There is a deep pothole at the junction and two-wheelers keep falling in it."
ANOTHER_POTHOLE = "Big pothole on this corner, autos swerve around it all morning."
A_THIRD_POTHOLE = "The pothole near the bus stop has grown since the rain stopped."
HOSPITAL_WATER = "The hospital water smells chemical and people are afraid to drink it."
MORE_HOSPITAL_WATER = "Water at the hospital tap smells of chemical again this morning."


@pytest.fixture
def repository() -> Iterator[MemoryIntakeRepository]:
    store = MemoryIntakeRepository()
    app.dependency_overrides[get_intake_service] = lambda: IntakeService(store)
    app.dependency_overrides[get_intake_repository] = lambda: store
    yield store
    app.dependency_overrides.pop(get_intake_service, None)
    app.dependency_overrides.pop(get_intake_repository, None)


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch, repository: MemoryIntakeRepository
) -> Iterator[TestClient]:
    # The real interpreter, on the test's own store. Grouping needs an interpreted
    # category to work with -- with analysis stubbed out every report is "unknown" and
    # nothing groups, so a stub here would make every test below pass for the wrong
    # reason. The module attribute is patched rather than the dependency because
    # `get_report_analysis_service` reaches for the cached repository directly and
    # would otherwise write interpretations into a store no test is reading.
    monkeypatch.setattr(
        intake_api,
        "get_report_analysis_service",
        lambda: ReportAnalysisService(repository, FixtureInterpreter()),
    )
    with TestClient(app) as test_client:
        yield test_client


def _jpeg() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (640, 480), (90, 110, 130)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _submit(
    client: TestClient,
    text: str,
    *,
    at: tuple[float, float] | None = JUNCTION,
    photo: bytes | None = None,
    locality: str = "Sarakki demo locality",
) -> str:
    data: dict[str, object] = {
        "description": text,
        "language_hint": "en",
        "locality_label": locality,
        "consent": "true",
        "synthetic_demo_confirmation": "true",
    }
    if at is not None:
        data["latitude"] = str(at[0])
        data["longitude"] = str(at[1])
    response = client.post(
        "/api/v1/reports",
        data=data,
        files={"photo": ("street.jpg", photo, "image/jpeg")} if photo is not None else None,
        headers={
            "Idempotency-Key": str(uuid4()),
            "X-Receipt-Capability": f"grouped-board-capability-{uuid4().hex}",
        },
    )
    assert response.status_code == 202, response.text
    return str(response.json()["public_id"])


def _fresh_items(client: TestClient, repository: MemoryIntakeRepository) -> list[dict[str, object]]:
    """The board's items that belong to reports this test submitted.

    The seeded demo incidents share the board, so they are filtered out by id rather
    than by counting: a test that asserted on the total would break every time the
    golden demo fixture gained an incident.
    """
    fresh = {str(record.id) for record in repository.list_fresh()}
    board = client.get("/api/v1/officer/overview").json()
    lanes = board["safety_review"] + board["operational_incidents"] + board["planning_needs"]
    return [item for item in lanes if item["id"] in fresh]


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _detail(client: TestClient, item_id: str) -> dict[str, object]:
    response = client.get(f"/api/v1/officer/incidents/{item_id}")
    assert response.status_code == 200, response.text
    return response.json()


def test_three_people_reporting_one_pothole_make_one_item_not_three(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    for text in (POTHOLE, ANOTHER_POTHOLE, A_THIRD_POTHOLE):
        _submit(client, text)

    items = _fresh_items(client, repository)

    assert len(items) == 1
    assert items[0]["report_count"] == 3
    # Said out loud on the item, not left for the officer to infer from the count.
    # Geometry accepted these three and nothing has read the three descriptions
    # against each other, so the honest word is "proposed".
    assert items[0]["grouping_confidence"] == "review"
    assert "proposed as one problem" in str(items[0]["title"])


def test_the_clock_starts_at_the_first_report_not_the_newest(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    """Otherwise every duplicate complaint would push the statutory deadline back.

    Reporting a problem again is the strongest signal a citizen can send that it is
    still there. A system that read it as "this arrived just now" would reward the
    backlog for growing.
    """
    first = _submit(client, POTHOLE)
    _submit(client, ANOTHER_POTHOLE)
    first_accepted = repository.get_by_public_id(first).accepted_at

    item = _fresh_items(client, repository)[0]
    detail = _detail(client, str(item["id"]))

    assert item["id"] == str(repository.get_by_public_id(first).id)
    # Parsed, not string-compared: the payload writes UTC as "Z" and the record holds
    # "+00:00", which is the same instant and not what this test is about.
    assert _instant(str(detail["incident"]["event_start"])) == first_accepted


def test_opening_any_of_the_grouped_reports_shows_the_one_problem(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    """A member is not a page of its own.

    An officer arriving from a link, a search or a phone call quoting one complaint
    number has to land on the problem it belongs to, with every report that was
    counted into it. Landing on a page that says "1 report" would have them dispatch a
    crew against a third of the evidence.
    """
    lead = _submit(client, POTHOLE)
    second = _submit(client, ANOTHER_POTHOLE)
    second_id = str(repository.get_by_public_id(second).id)

    detail = _detail(client, second_id)

    assert detail["incident"]["id"] == str(repository.get_by_public_id(lead).id)
    assert detail["incident"]["report_count"] == 2
    assert [report["public_id"] for report in detail["reports"]] == [lead, second]
    assert detail["relationship_explanation"]["grouped"] is True
    assert detail["relationship_explanation"]["state"] == "human_review_required"


def test_the_officer_is_shown_the_numbers_that_merged_the_reports(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    """So a disputed grouping can be argued with instead of only overridden.

    "The system grouped these" is the answer that makes a person stop trusting the
    count. The distance, the hours and the category match are checkable, and an
    officer who can check them can also tell you when they are wrong.
    """
    _submit(client, POTHOLE)
    _submit(client, ANOTHER_POTHOLE)

    detail = _detail(client, str(_fresh_items(client, repository)[0]["id"]))
    lead, joined = detail["reports"]

    assert lead["joined_by"]["reason"] == "lead"
    assert joined["joined_by"]["reason"] == "geometry_only"
    assert joined["joined_by"]["same_category"] is True
    assert joined["joined_by"]["distance_km"] == 0.0
    # Not an equality on zero: these were submitted in the same second, but the number
    # published is a real elapsed time and a slow machine is not a bug.
    assert float(joined["joined_by"]["hours_apart"]) < 0.1
    # No model has read the two descriptions yet, and the payload says so rather than
    # implying a judgement nobody made.
    assert joined["joined_by"]["intent_verdict"] == "abstain"
    assert joined["joined_by"]["photo_hash_distance"] is None
    assert "rule_version" in detail["relationship_explanation"]


def test_the_same_complaint_from_across_the_ward_is_a_second_problem(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    """The coordinates from the form have to reach the grouping, and this is the proof.

    Identical wording, one junction apart by 3 km. If the coordinates were dropped
    anywhere between the form and the board -- as they once were -- these two would
    merge on their matching locality label and one of the two potholes would never be
    dispatched.
    """
    _submit(client, POTHOLE, at=JUNCTION)
    _submit(client, POTHOLE, at=ACROSS_THE_WARD)

    items = _fresh_items(client, repository)

    assert len(items) == 2
    assert [item["report_count"] for item in items] == [1, 1]


def test_a_safety_signal_is_grouped_in_its_own_lane_and_never_scored(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    """Grouping happens inside the safety lane, not across it.

    Two reports of the same hazard are one hazard and one crew, so they group. What
    they must never do is land in the operational lane, where a hazard is counted
    among things that wait for a priority score.
    """
    _submit(client, HOSPITAL_WATER)
    _submit(client, MORE_HOSPITAL_WATER)

    fresh = {str(record.id) for record in repository.list_fresh()}
    board = client.get("/api/v1/officer/overview").json()
    in_safety = [item for item in board["safety_review"] if item["id"] in fresh]
    elsewhere = [
        item
        for item in board["operational_incidents"] + board["planning_needs"]
        if item["id"] in fresh
    ]

    assert len(in_safety) == 1
    assert in_safety[0]["report_count"] == 2
    assert in_safety[0]["status"] == "pending_human_verification"
    assert elsewhere == []


def test_one_photograph_makes_the_whole_group_judgeable_from_a_desk(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    """Which is the only question ``has_photo`` on a lane item is answering.

    Two people reported the pothole and one of them sent a picture. That is enough for
    the officer to decide severity without a site visit, so the item says so -- and the
    detail still shows which of the two reports the picture came from.
    """
    _submit(client, POTHOLE)
    _submit(client, ANOTHER_POTHOLE, photo=_jpeg())

    item = _fresh_items(client, repository)[0]
    detail = _detail(client, str(item["id"]))

    assert item["report_count"] == 2
    assert item["has_photo"] is True
    assert [report["has_photo"] for report in detail["reports"]] == [False, True]


def test_every_report_is_counted_on_the_board_exactly_once(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    """A dropped report is a citizen who was told their complaint was received and
    whose complaint no officer ever sees. A double-counted one inflates the number
    that decides what gets fixed first. Both are silent, so they are asserted."""
    for text, at in (
        (POTHOLE, JUNCTION),
        (ANOTHER_POTHOLE, JUNCTION),
        (POTHOLE, ACROSS_THE_WARD),
        (HOSPITAL_WATER, JUNCTION),
        (A_THIRD_POTHOLE, None),
    ):
        _submit(client, text, at=at)

    items = _fresh_items(client, repository)

    assert sum(int(item["report_count"]) for item in items) == 5
