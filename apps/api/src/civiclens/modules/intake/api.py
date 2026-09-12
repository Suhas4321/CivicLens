from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    UploadFile,
    status,
)

from civiclens.bootstrap.settings import get_settings
from civiclens.infrastructure.media.voice_storage import get_voice_storage
from civiclens.modules.analysis.service import get_report_analysis_service
from civiclens.modules.intake.schemas import ReceiptStatus, ReportAccepted, ReportCreateRequest
from civiclens.modules.intake.service import IntakeService, get_intake_service
from civiclens.modules.intake.voice import MAX_VOICE_BYTES, validate_voice
from civiclens.shared.errors import ConflictError, MediaValidationError, NotFoundError

router = APIRouter(tags=["report-intake"])
Service = Annotated[IntakeService, Depends(get_intake_service)]
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=16, max_length=128),
]
ReceiptCapability = Annotated[
    str,
    Header(alias="X-Receipt-Capability", min_length=32, max_length=256),
]


@router.post(
    "/reports",
    response_model=ReportAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_report(
    background_tasks: BackgroundTasks,
    service: Service,
    idempotency_key: IdempotencyKey,
    receipt_capability: ReceiptCapability,
    description: Annotated[str, Form(min_length=20, max_length=2000)],
    language_hint: Annotated[Literal["en", "kn", "hi", "mixed"], Form()],
    locality_label: Annotated[str, Form(min_length=3, max_length=160)],
    consent: Annotated[bool, Form()],
    synthetic_demo_confirmation: Annotated[bool, Form()],
    voice: Annotated[UploadFile | None, File()] = None,
) -> ReportAccepted:
    try:
        if not consent or not synthetic_demo_confirmation:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "code": "DEMO_CONFIRMATION_REQUIRED",
                    "message": "Synthetic-data confirmation and consent are required.",
                },
            )
        payload = ReportCreateRequest.model_validate(
            {
                "description": description,
                "language_hint": language_hint,
                "locality_label": locality_label,
                "consent": consent,
                "synthetic_demo_confirmation": synthetic_demo_confirmation,
            }
        )
        stored_voice = None
        if voice is not None:
            voice_bytes = await voice.read(MAX_VOICE_BYTES + 1)
            await voice.close()
            validated = validate_voice(voice_bytes, voice.content_type)
            settings = get_settings()
            stored_voice = get_voice_storage().put(
                validated,
                idempotency_key=idempotency_key,
                retain_until=datetime.now(UTC) + timedelta(days=settings.report_retention_days),
            )
        accepted = service.submit(
            payload,
            idempotency_key=idempotency_key,
            receipt_capability=receipt_capability,
            voice=stored_voice,
        )
        if get_settings().intake_backend == "memory":
            background_tasks.add_task(get_report_analysis_service().process, accepted.public_id)
        return accepted
    except MediaValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    except ConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc


@router.get("/receipts/{public_id}", response_model=ReceiptStatus)
async def receipt_status(
    public_id: str,
    service: Service,
    receipt_capability: ReceiptCapability,
) -> ReceiptStatus:
    try:
        return service.receipt(public_id, receipt_capability=receipt_capability)
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": exc.code, "message": "Receipt not found"},
        ) from exc
