"""Pure Lane 3 triage scoring from already-derived policy components."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

ComponentName = Literal["cs", "ps", "ex", "vu", "sv", "ng"]
ScoreBand = Literal["high", "moderate", "lower"]

COMPONENT_NAMES: tuple[ComponentName, ...] = ("cs", "ps", "ex", "vu", "sv", "ng")
WEIGHTS: Mapping[ComponentName, float] = MappingProxyType(
    {
        "cs": 0.24,
        "ps": 0.18,
        "ex": 0.16,
        "vu": 0.18,
        "sv": 0.16,
        "ng": 0.08,
    }
)

assert sum(WEIGHTS.values()) == 1.0


@dataclass(frozen=True)
class ScoreComponents:
    cs: float
    ps: float
    ex: float
    vu: float
    sv: float
    ng: float

    def __post_init__(self) -> None:
        values = {
            "cs": self.cs,
            "ps": self.ps,
            "ex": self.ex,
            "vu": self.vu,
            "sv": self.sv,
            "ng": self.ng,
        }
        for name, value in values.items():
            if not 0.0 <= value <= 100.0:
                raise ValueError(f"score component {name} must be between 0 and 100")

    def as_mapping(self) -> Mapping[ComponentName, float]:
        return MappingProxyType(
            {
                "cs": self.cs,
                "ps": self.ps,
                "ex": self.ex,
                "vu": self.vu,
                "sv": self.sv,
                "ng": self.ng,
            }
        )


@dataclass(frozen=True)
class ScoreResult:
    total: float
    band: ScoreBand
    contributions: Mapping[ComponentName, float]


def compute_score(components: ScoreComponents) -> ScoreResult:
    values = components.as_mapping()
    contributions: dict[ComponentName, float] = {
        name: values[name] * WEIGHTS[name] for name in COMPONENT_NAMES
    }
    total = sum(contributions.values())

    band: ScoreBand
    if total >= 70.0:
        band = "high"
    elif total >= 45.0:
        band = "moderate"
    else:
        band = "lower"

    return ScoreResult(
        total=total,
        band=band,
        contributions=MappingProxyType(contributions),
    )
