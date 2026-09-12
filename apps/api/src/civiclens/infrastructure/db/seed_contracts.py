from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from civiclens.shared.errors import ConfigurationError


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExpectedReportOutcome(StrictModel):
    category: str | None
    incident_key: str | None
    outcome: str
    safety_signal: str | None


class SeedReport(StrictModel):
    logical_id: UUID
    public_id: str
    receipt_seed: str
    story: str
    language: Literal["kn", "en", "hi", "mixed"]
    text: str = Field(min_length=4)
    event_at: datetime
    accepted_at: datetime
    locality_label: str
    geography_kind: Literal["synthetic_locality"]
    geography_source: Literal["declared_seed_metadata"]
    project_zone_label: str
    latitude: float | None
    longitude: float | None
    location_precision: str
    expected: ExpectedReportOutcome
    classification: Literal["synthetic_demo"]


class PublicObservation(StrictModel):
    evidence_key: str
    evidence_class: Literal["real_public", "derived_public", "synthetic_demo"]
    kind: Literal["observation", "work", "context"]
    label: str
    value_numeric: float | None
    value_text: str | None
    unit: str | None
    geography_label: str
    geography_kind: str
    geography_vintage: str | None
    period_start: date | None
    period_end: date | None
    semantics: Literal[
        "observed", "projected", "plan", "administrative_status", "synthetic_verification"
    ]
    source_url: str
    transformation: str | None
    supported_inferences: list[str] = Field(min_length=1)
    prohibited_inferences: list[str] = Field(min_length=1)


class PublicManifest(StrictModel):
    version: str
    publisher: str
    primary_source_url: str
    publication_date: date | None
    reference_date: date | None
    retrieved_at: date
    normalized_file: str
    normalized_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_format: str
    license_status: str
    review_status: Literal["reviewed", "limited_reuse", "unverified"]
    geography: dict[str, Any]
    sources: list[dict[str, Any]] = Field(min_length=1)
    global_prohibited_inferences: list[str] = Field(min_length=1)


class DemoManifest(StrictModel):
    version: Literal["demo-seed-v1"]
    classification: Literal["synthetic_demo"]
    contains_real_citizen_data: Literal[False]
    report_count: Literal[60]
    tuning_count: int
    held_out_count: int
    reports_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    ground_truth_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    language_mix: dict[str, int]

    @model_validator(mode="after")
    def validate_partitions(self) -> DemoManifest:
        if self.tuning_count + self.held_out_count != self.report_count:
            raise ValueError("tuning and held-out partitions must cover the demo corpus")
        if self.language_mix != {"kn": 24, "en": 21, "hi": 12, "mixed": 3}:
            raise ValueError("language mix does not match the frozen Stage 6 decision")
        return self


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"Cannot load seed asset: {path}") from exc


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_demo_assets(root: Path) -> tuple[list[SeedReport], dict[str, Any], DemoManifest]:
    demo_root = root / "data" / "demo" / "v1"
    reports_path = demo_root / "reports.json"
    truth_path = demo_root / "ground_truth.json"
    manifest = DemoManifest.model_validate(load_json(demo_root / "manifest.json"))
    reports = [SeedReport.model_validate(item) for item in load_json(reports_path)]
    truth = load_json(truth_path)

    if len(reports) != manifest.report_count:
        raise ConfigurationError("Demo report count does not match its manifest")
    if sha256_file(reports_path) != manifest.reports_sha256:
        raise ConfigurationError("Demo reports checksum mismatch")
    if sha256_file(truth_path) != manifest.ground_truth_sha256:
        raise ConfigurationError("Demo ground-truth checksum mismatch")
    if not isinstance(truth, dict):
        raise ConfigurationError("Demo ground truth must be an object")
    return reports, cast(dict[str, Any], truth), manifest


def validate_public_assets(root: Path) -> tuple[PublicManifest, list[PublicObservation]]:
    public_root = root / "data" / "public" / "bengaluru-water-v1"
    manifest = PublicManifest.model_validate(load_json(public_root / "manifest.json"))
    normalized_path = public_root / manifest.normalized_file
    if sha256_file(normalized_path) != manifest.normalized_sha256:
        raise ConfigurationError("Public snapshot checksum mismatch")
    observations = [PublicObservation.model_validate(item) for item in load_json(normalized_path)]
    return manifest, observations
