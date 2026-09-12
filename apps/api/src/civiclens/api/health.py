from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from civiclens.bootstrap.settings import Settings, get_settings

router = APIRouter(prefix="/health", tags=["health"])
SettingsDependency = Annotated[Settings, Depends(get_settings)]


class LiveResponse(BaseModel):
    status: Literal["alive"] = "alive"


class ReadyResponse(BaseModel):
    status: Literal["ready"] = "ready"


class VersionResponse(BaseModel):
    application: Literal["civiclens-api"] = "civiclens-api"
    version: str
    environment: str
    schema_version: str
    prompt_version: str
    rules_version: str
    catalogue_version: str
    seed_version: str
    public_snapshot_version: str


@router.get("/live", response_model=LiveResponse)
async def live() -> LiveResponse:
    return LiveResponse()


@router.get(
    "/ready",
    response_model=ReadyResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Configuration incomplete"}},
)
async def ready(settings: SettingsDependency) -> ReadyResponse:
    missing = settings.validate_deployed_environment()
    if missing:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "CONFIGURATION_INCOMPLETE"},
        )
    return ReadyResponse()


@router.get("/version", response_model=VersionResponse)
async def version(settings: SettingsDependency) -> VersionResponse:
    return VersionResponse(
        version=settings.app_version,
        environment=settings.app_env,
        schema_version=settings.schema_version,
        prompt_version=settings.prompt_version,
        rules_version=settings.rules_version,
        catalogue_version=settings.catalogue_version,
        seed_version=settings.demo_seed_version,
        public_snapshot_version=settings.public_snapshot_version,
    )
