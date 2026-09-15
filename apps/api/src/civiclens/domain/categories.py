"""Typed loader for ``config/categories/<version>.json``.

Category routing, service targets, severity ceilings and grouping geometry are
policy decisions. They are versioned configuration rather than constants in
code so that every derived problem can retain the exact policy that produced it.

The models forbid unknown keys and are frozen. A typo or attempted runtime
mutation is therefore a failure rather than a silent policy change.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from civiclens.bootstrap.policy import repository_root
from civiclens.shared.errors import ConfigurationError

ALLOWED_AGENCIES = frozenset({"BSCC", "BWSSB", "BESCOM", "BMTC"})
OTHER_CODE = "OTHER"

GroupingGeometry = Literal["linear_road", "areal_locality", "point_asset"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CategoryRule(StrictModel):
    code: str = Field(min_length=1)
    label_en: str = Field(min_length=1)
    label_kn: str = Field(min_length=1)
    agency: str | None
    sla_days: int = Field(gt=0)
    severity_ceiling: int | None = Field(ge=0, le=100)
    grouping_geometry: GroupingGeometry
    lane_1_eligible: bool
    rankable: bool


class CategoryConfig(StrictModel):
    version: str
    categories: tuple[CategoryRule, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_categories(self) -> CategoryConfig:
        codes = [rule.code for rule in self.categories]
        if len(set(codes)) != len(codes):
            raise ValueError("categories contains a duplicate code")

        for rule in self.categories:
            if rule.code == OTHER_CODE:
                if rule.agency is not None:
                    raise ValueError("OTHER must not declare an agency")
                if rule.severity_ceiling is not None:
                    raise ValueError("OTHER must not declare a severity ceiling")
                if rule.rankable:
                    raise ValueError("OTHER must not be rankable")
                continue

            if rule.agency not in ALLOWED_AGENCIES:
                raise ValueError(f"category {rule.code!r} has an unknown agency")
            if rule.severity_ceiling is None:
                raise ValueError(f"category {rule.code!r} requires a severity ceiling")
            if not rule.rankable:
                raise ValueError(f"category {rule.code!r} must be rankable")
        return self

    def by_code(self, code: str) -> CategoryRule:
        for rule in self.categories:
            if rule.code == code:
                return rule
        raise KeyError(f"Unknown category code: {code}")

    @property
    def codes(self) -> frozenset[str]:
        return frozenset(rule.code for rule in self.categories)


def category_config_path(version: str, root: Path | None = None) -> Path:
    return (root or repository_root()) / "config" / "categories" / f"{version}.json"


def load_category_config(version: str, root: Path | None = None) -> CategoryConfig:
    path = category_config_path(version, root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"Cannot load category configuration: {path.name}") from exc
    try:
        config = CategoryConfig.model_validate(payload)
    except ValidationError as exc:
        raise ConfigurationError(f"Invalid category configuration in {path.name}: {exc}") from exc
    if config.version != version:
        raise ConfigurationError(
            f"Category configuration {path.name} declares version {config.version!r}"
        )
    return config
