from uuid import uuid4

import pytest

from civiclens.infrastructure.ai.fake import FixtureInterpreter
from civiclens.modules.analysis.schemas import InterpretationEnvelope, InterpretationRequest
from civiclens.modules.analysis.service import ReportAnalysisService
from civiclens.modules.intake.repository import MemoryIntakeRepository
from civiclens.modules.intake.schemas import ReportCreateRequest
from civiclens.modules.intake.service import IntakeService
from civiclens.shared.errors import AIProviderError, ConflictError, NotFoundError


class FailingInterpreter:
    def interpret(self, request: InterpretationRequest) -> InterpretationEnvelope:
        del request
        raise AIProviderError("RATE_LIMITED")


def test_report_submission_is_idempotent_and_receipt_is_capability_protected() -> None:
    repository = MemoryIntakeRepository()
    service = IntakeService(repository)
    capability = "demo-receipt-capability-0123456789abcdef"
    idempotency_key = str(uuid4())
    payload = ReportCreateRequest(
        description="Water has not arrived in our lane for the past three mornings.",
        language_hint="en",
        locality_label="Mahadevapura demo zone",
        consent=True,
        synthetic_demo_confirmation=True,
    )

    accepted = service.submit(
        payload,
        idempotency_key=idempotency_key,
        receipt_capability=capability,
    )
    retried = service.submit(
        payload,
        idempotency_key=idempotency_key,
        receipt_capability=capability,
    )
    receipt = service.receipt(accepted.public_id, receipt_capability=capability)

    assert retried.public_id == accepted.public_id
    assert capability not in accepted.model_dump_json()
    assert receipt.evidence_class == "synthetic_demo"
    assert receipt.analysis_class == "pending"

    ReportAnalysisService(repository, FixtureInterpreter()).process(accepted.public_id)
    processed = service.receipt(accepted.public_id, receipt_capability=capability)
    assert processed.status == "processed"
    assert processed.analysis_class == "fresh_fixture"

    with pytest.raises(NotFoundError):
        service.receipt(
            accepted.public_id,
            receipt_capability="wrong-capability-0123456789abcdef",
        )

    changed = payload.model_copy(update={"locality_label": "Different demo zone"})
    with pytest.raises(ConflictError):
        service.submit(
            changed,
            idempotency_key=idempotency_key,
            receipt_capability=capability,
        )


def test_ai_failure_keeps_the_accepted_report_and_routes_it_to_review() -> None:
    repository = MemoryIntakeRepository()
    intake = IntakeService(repository)
    capability = "failure-receipt-capability-0123456789abcdef"
    accepted = intake.submit(
        ReportCreateRequest(
            description="Synthetic water pressure issue reported for three mornings in a row.",
            language_hint="en",
            locality_label="Synthetic failure locality",
            consent=True,
            synthetic_demo_confirmation=True,
        ),
        idempotency_key="failure-idempotency-0001",
        receipt_capability=capability,
    )

    result = ReportAnalysisService(repository, FailingInterpreter()).process(accepted.public_id)
    receipt = intake.receipt(accepted.public_id, receipt_capability=capability)

    assert result.report.processing_state == "needs_review"
    assert receipt.status == "needs_review"
    assert receipt.analysis_class == "pending"
