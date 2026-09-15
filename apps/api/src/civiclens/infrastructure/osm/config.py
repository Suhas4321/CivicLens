"""Typed loader for ``config/geography/<version>.json``.

The bounding box, the set of road classes we keep and the OSM-tag-to-category
mapping are all *policy decisions* about what counts as civic infrastructure in
Bengaluru South. They are versioned configuration rather than constants in code
so that a mapping mistake is fixed by editing a reviewed JSON file and re-running
the ingest, and so that every ingest run can record which version produced its
data.

The models forbid unknown keys, including the human-readable ``why_*`` and
``notes`` fields, which are declared explicitly. A typo in a config key is then a
load-time failure rather than a silently ignored setting.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from civiclens.bootstrap.policy import repository_root
from civiclens.shared.errors import ConfigurationError

ANY_VALUE = "*"
"""Sentinel in a tag rule meaning "any value for this key"."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BoundingBox(StrictModel):
    min_lon: float = Field(ge=-180.0, le=180.0)
    min_lat: float = Field(ge=-90.0, le=90.0)
    max_lon: float = Field(ge=-180.0, le=180.0)
    max_lat: float = Field(ge=-90.0, le=90.0)
    covers: str = ""

    @model_validator(mode="after")
    def validate_ordering(self) -> BoundingBox:
        if self.min_lon >= self.max_lon or self.min_lat >= self.max_lat:
            raise ValueError("bbox minimums must be strictly less than maximums")
        return self

    def contains(self, lon: float, lat: float) -> bool:
        return (
            self.min_lon <= lon <= self.max_lon  #
            and self.min_lat <= lat <= self.max_lat
        )

    def as_string(self) -> str:
        """The ``minlon,minlat,maxlon,maxlat`` form recorded against an ingest run."""
        return f"{self.min_lon},{self.min_lat},{self.max_lon},{self.max_lat}"


class SourceConfig(StrictModel):
    primary_url: str
    primary_bytes_approx: int = Field(gt=0)
    fallback_url: str
    fallback_bytes_approx: int = Field(gt=0)
    local_filename: str
    why_primary: str = ""


class RoadsConfig(StrictModel):
    highway_values: tuple[str, ...] = Field(min_length=1)
    why_these: str = ""


class LocalitiesConfig(StrictModel):
    place_values: tuple[str, ...] = Field(min_length=1)
    require_name: bool = True


class PoiCategoryRule(StrictModel):
    category: str = Field(min_length=1)
    priority: int
    tags: Mapping[str, tuple[str, ...]] = Field(min_length=1)

    def matches(self, tags: Mapping[str, str]) -> bool:
        """True when any one key/value pair in the rule is present on the object.

        Rules are disjunctive because OSM tagging is redundant rather than
        canonical: a hospital may carry ``amenity=hospital``, ``healthcare=hospital``
        or both, and requiring all of them would silently drop most of them.
        """
        for key, accepted in self.tags.items():
            value = tags.get(key)
            if value is None:
                continue
            if ANY_VALUE in accepted or value in accepted:
                return True
        return False


class VerificationPoint(StrictModel):
    label: str
    lon: float
    lat: float
    expected_locality_contains: str | None = None
    expected_road_name_contains: str | None = None
    # What the 2026-09-15 ingest actually resolved, recorded even where it is not
    # asserted. A point left unasserted because the real answer was imprecise is a
    # known limitation, and the limitation is worth keeping visible in the config
    # rather than losing it in a commit message.
    observed: str = ""


class GeographyConfig(StrictModel):
    version: str
    corporation: str
    corporation_code: str
    attribution: str
    license: str
    notes: tuple[str, ...] = ()
    source: SourceConfig
    bbox: BoundingBox
    roads: RoadsConfig
    localities: LocalitiesConfig
    poi_categories: tuple[PoiCategoryRule, ...] = Field(min_length=1)
    verification_points: tuple[VerificationPoint, ...] = ()

    @model_validator(mode="after")
    def validate_categories(self) -> GeographyConfig:
        categories = [rule.category for rule in self.poi_categories]
        if len(set(categories)) != len(categories):
            raise ValueError("poi_categories contains a duplicate category")
        priorities = [rule.priority for rule in self.poi_categories]
        if len(set(priorities)) != len(priorities):
            # Equal priorities would make category assignment depend on file
            # order, so two ingests of the same extract could disagree.
            raise ValueError("poi_categories priorities must be unique to keep matching stable")
        for point in self.verification_points:
            if not self.bbox.contains(point.lon, point.lat):
                raise ValueError(f"verification point {point.label!r} is outside the bbox")
        return self

    @property
    def highway_values(self) -> frozenset[str]:
        return frozenset(self.roads.highway_values)

    @property
    def place_values(self) -> frozenset[str]:
        return frozenset(self.localities.place_values)

    @property
    def poi_rules_by_priority(self) -> tuple[PoiCategoryRule, ...]:
        """Highest priority first, so the first match wins deterministically."""
        return tuple(sorted(self.poi_categories, key=lambda rule: -rule.priority))

    @property
    def interesting_tag_keys(self) -> frozenset[str]:
        """Every tag key that can make an object relevant.

        Handed to osmium's C++-side key filter so the overwhelming majority of
        objects in the extract are rejected before they ever reach Python.
        """
        keys = {"highway", "place"}
        for rule in self.poi_categories:
            keys.update(rule.tags)
        return frozenset(keys)


def geography_config_path(version: str, root: Path | None = None) -> Path:
    return (root or repository_root()) / "config" / "geography" / f"{version}.json"


def load_geography_config(version: str, root: Path | None = None) -> GeographyConfig:
    path = geography_config_path(version, root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"Cannot load geography configuration: {path.name}") from exc
    try:
        config = GeographyConfig.model_validate(payload)
    except ValidationError as exc:
        raise ConfigurationError(f"Invalid geography configuration in {path.name}: {exc}") from exc
    if config.version != version:
        raise ConfigurationError(
            f"Geography configuration {path.name} declares version {config.version!r}"
        )
    return config
