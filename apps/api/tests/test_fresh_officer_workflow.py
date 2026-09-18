import asyncio

from civiclens.infrastructure.ai.fake import FixtureInterpreter
from civiclens.modules.analysis.service import ReportAnalysisService
from civiclens.modules.intake.repository import MemoryIntakeRepository
from civiclens.modules.intake.schemas import ReportCreateRequest
from civiclens.modules.intake.service import IntakeService
from civiclens.modules.planning.api import incident_detail, overview
from civiclens.modules.planning.read_service import get_golden_demo_read_service


def _submit(repository: MemoryIntakeRepository, description: str, locality: str) -> str:
    accepted = IntakeService(repository).submit(
        ReportCreateRequest(
            description=description,
            language_hint="en",
            locality_label=locality,
            consent=True,
            synthetic_demo_confirmation=True,
        ),
        idempotency_key=f"fresh-officer-{len(repository.list_fresh()):04d}",
        receipt_capability=f"fresh-officer-capability-{len(repository.list_fresh()):04d}-secret",
    )
    ReportAnalysisService(repository, FixtureInterpreter()).process(accepted.public_id)
    return accepted.public_id


def test_fresh_report_appears_for_relationship_review_and_remains_non_planning() -> None:
    repository = MemoryIntakeRepository()
    public_id = _submit(
        repository,
        "Synthetic water pressure has been low in this lane for three mornings.",
        "Synthetic fresh locality",
    )

    result = asyncio.run(overview(get_golden_demo_read_service(), repository))
    fresh = next(item for item in result.operational_incidents if "Fresh report" in item.title)
    detail = asyncio.run(incident_detail(fresh.id, get_golden_demo_read_service(), repository))

    assert fresh.status == "relationship_review"
    assert fresh.report_count == 1
    assert all(item.id != fresh.id for item in result.planning_needs)
    assert detail.reports[0].public_id == public_id
    assert detail.relationship_explanation["state"] == "human_review_required"


def test_fresh_safety_signal_is_count_independent_and_never_ranked() -> None:
    repository = MemoryIntakeRepository()
    _submit(
        repository,
        "Synthetic hospital water smells chemical and may be contaminated.",
        "Synthetic hospital locality",
    )

    result = asyncio.run(overview(get_golden_demo_read_service(), repository))
    fresh = result.safety_review[0]

    assert fresh.status == "pending_human_verification"
    assert fresh.report_count == 1
    assert all(item.id != fresh.id for item in result.planning_needs)
