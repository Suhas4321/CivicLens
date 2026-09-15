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
from pydantic import ValidationError

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
    # Every field the client may send has to be declared here. FastAPI silently
    # drops multipart fields it was not told about, so an undeclared field means
    # the request still succeeds, the citizen is shown a receipt, and their data
    # is thrown away with nobody told. `latitude` and `longitude` were exactly
    # that: `ReportCreateRequest` has validated them and `SqlAlchemyIntakeRepository`
    # has persisted them since the first migration, but the endpoint never
    # accepted them, so every coordinate a reporter's phone produced was
    # discarded here.
    description: Annotated[str, Form(min_length=4, max_length=2000)],
    language_hint: Annotated[Literal["en", "kn", "hi", "mixed"], Form()],
    locality_label: Annotated[str, Form(min_length=3, max_length=160)],
    consent: Annotated[bool, Form()],
    synthetic_demo_confirmation: Annotated[bool, Form()],
    latitude: Annotated[float | None, Form(ge=-90, le=90)] = None,
    longitude: Annotated[float | None, Form(ge=-180, le=180)] = None,
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
        try:
            payload = ReportCreateRequest.model_validate(
                {
                    "description": description,
                    "language_hint": language_hint,
                    "locality_label": locality_label,
                    "consent": consent,
                    "synthetic_demo_confirmation": synthetic_demo_confirmation,
                    "latitude": latitude,
                    "longitude": longitude,
                }
            )
        except ValidationError as exc:
            # Model-level rules — currently only `coordinates_are_a_pair` — reach
            # here as a plain pydantic error, which FastAPI would turn into a 500
            # because it is raised inside the handler rather than while parsing the
            # request. A malformed submission is the client's fault, so it gets a
            # 422. The pydantic message is not forwarded: it embeds the offending
            # values, and report text must never leave the process in an error.
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "code": "REPORT_FIELDS_INVALID",
                    "message": "Latitude and longitude must be supplied together.",
                },
            ) from exc
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
