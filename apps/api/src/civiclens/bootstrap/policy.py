from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from civiclens.shared.errors import ConfigurationError

COMPONENT_CODES = {
    "scale_exposure",
    "persistence_spread",
    "service_disadvantage",
    "consequence_if_unaddressed",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PriorityProfile(StrictModel):
    key: str
    weights: dict[str, int]

    @model_validator(mode="after")
    def validate_weights(self) -> PriorityProfile:
        if set(self.weights) != COMPONENT_CODES:
            raise ValueError("priority profile must define every component exactly once")
        if any(weight < 0 for weight in self.weights.values()) or sum(self.weights.values()) != 100:
            raise ValueError("priority profile weights must be non-negative and total 100")
        return self


class PriorityBands(StrictModel):
    high_minimum: float = Field(ge=0, le=3)
    moderate_minimum: float = Field(ge=0, le=3)

    @model_validator(mode="after")
    def validate_order(self) -> PriorityBands:
        if self.high_minimum <= self.moderate_minimum:
            raise ValueError("high threshold must exceed moderate threshold")
        return self


class PriorityPolicy(StrictModel):
    version: str
    rating_min: int
    rating_max: int
    unknown_prevents_comparison: bool
    components: list[str]
    profiles: list[PriorityProfile]
    bands: PriorityBands
    tie_breakers: list[str]

    @model_validator(mode="after")
    def validate_policy(self) -> PriorityPolicy:
        if set(self.components) != COMPONENT_CODES:
            raise ValueError("priority policy has an unexpected component set")
        if (self.rating_min, self.rating_max) != (0, 3):
            raise ValueError("priority ratings must remain 0–3")
        if not self.unknown_prevents_comparison:
            raise ValueError("unknown evidence must prevent comparison")
        if {profile.key for profile in self.profiles} != {
            "balanced",
            "exposure_emphasis",
            "persistence_emphasis",
        }:
            raise ValueError("all three sensitivity profiles are required")
        return self


class CatalogueItem(StrictModel):
    key: str
    candidate_type: Literal["assessment", "operational_review", "feasibility"]
    categories: list[str] = Field(min_length=1)
    requires_verified_cause: bool
    wording: str = Field(min_length=20)
    prerequisites: list[str] = Field(min_length=1)


class Catalogue(StrictModel):
    version: str
    items: list[CatalogueItem]

    @model_validator(mode="after")
    def validate_catalogue(self) -> Catalogue:
        if len(self.items) != 3 or len({item.key for item in self.items}) != 3:
            raise ValueError("v1 catalogue must contain exactly three uniquely keyed items")
        capital = next(
            (item for item in self.items if item.key == "capital_feasibility_referral"), None
        )
        if capital is None or not capital.requires_verified_cause:
            raise ValueError("capital feasibility must require a verified cause")
        return self


class PromptManifest(StrictModel):
    version: Literal["report-interpretation-v1"]
    schema_version: Literal["report-interpretation-schema-v1"]
    provider_family: str
    evaluation_set_version: str
    tools_enabled: Literal[False]
    policy_fields_allowed: Literal[False]
    content_classification: Literal["synthetic_demo_only"]
    files_sha256: dict[str, str]

    @model_validator(mode="after")
    def validate_files(self) -> PromptManifest:
        expected = {
            "system.md",
            "task.md",
            "response-schema.json",
            "controlled-vocabulary.json",
            "examples.json",
        }
        if set(self.files_sha256) != expected:
            raise ValueError("prompt manifest must checksum every frozen prompt asset")
        if any(len(value) != 64 for value in self.files_sha256.values()):
            raise ValueError("prompt asset checksum must be SHA-256")
        return self


class SafetySignalPolicy(StrictModel):
    code: str
    categories: list[str]
    high_consequence_contexts: list[str]
    action: Literal["human_verification"]


class SafetyPolicy(StrictModel):
    version: Literal["safety-v1"]
    uncertain_means_review: bool
    signals: list[SafetySignalPolicy]


class SameIncidentPolicy(StrictModel):
    max_hours: int = Field(gt=0)
    max_distance_km: float = Field(gt=0)
    requires_category_match: bool
    project_zone_alone_is_insufficient: bool


class RecurrencePolicy(StrictModel):
    max_days: int = Field(gt=0)
    minimum_distinct_incidents: int = Field(ge=2)
    requires_confirmed_links: bool
    requires_alternative_hypothesis_review: bool


class GroupingPolicy(StrictModel):
    version: Literal["grouping-v1"]
    uncertainty_favors_separation: Literal[True]
    same_incident: SameIncidentPolicy
    recurrence: RecurrencePolicy


class PolicyBundle(StrictModel):
    priority: PriorityPolicy
    catalogue: Catalogue
    safety: SafetyPolicy
    grouping: GroupingPolicy
    prompt_manifest: PromptManifest


def repository_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"Cannot load configuration: {path.name}") from exc
    if not isinstance(value, dict):
        raise ConfigurationError(f"Configuration root must be an object: {path.name}")
    return cast(dict[str, object], value)


def load_policy_bundle(root: Path | None = None) -> PolicyBundle:
    config_root = (root or repository_root()) / "config"
    prompt_root = config_root / "prompts" / "report-interpretation-v1"
    bundle = PolicyBundle(
        priority=PriorityPolicy.model_validate(
            _read_json(config_root / "rules" / "priority-v1.json")
        ),
        catalogue=Catalogue.model_validate(
            _read_json(config_root / "catalogue" / "assessment-catalogue-v1.json")
        ),
        safety=SafetyPolicy.model_validate(_read_json(config_root / "rules" / "safety-v1.json")),
        grouping=GroupingPolicy.model_validate(
            _read_json(config_root / "rules" / "grouping-v1.json")
        ),
        prompt_manifest=PromptManifest.model_validate(_read_json(prompt_root / "manifest.json")),
    )
    for filename, expected_digest in bundle.prompt_manifest.files_sha256.items():
        try:
            actual_digest = hashlib.sha256((prompt_root / filename).read_bytes()).hexdigest()
        except OSError as exc:
            raise ConfigurationError(f"Cannot load prompt asset: {filename}") from exc
        if actual_digest != expected_digest:
            raise ConfigurationError(f"Prompt asset checksum mismatch: {filename}")
    return bundle
