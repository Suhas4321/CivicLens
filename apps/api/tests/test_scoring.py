from __future__ import annotations

from collections.abc import Mapping

import pytest

from civiclens.domain.scoring import (
    COMPONENT_NAMES,
    WEIGHTS,
    ComponentName,
    ScoreBand,
    ScoreComponents,
    compute_score,
)

ROAD_A = ScoreComponents(cs=10.0, ps=30.0, ex=35.0, vu=35.0, sv=65.0, ng=0.0)
ROAD_B = ScoreComponents(cs=65.0, ps=70.0, ex=90.0, vu=35.0, sv=65.0, ng=40.0)
METRO_POTHOLE = ScoreComponents(cs=45.0, ps=50.0, ex=80.0, vu=35.0, sv=65.0, ng=20.0)
HOSPITAL_POTHOLE = ScoreComponents(
    cs=25.0,
    ps=50.0,
    ex=60.0,
    vu=100.0,
    sv=65.0,
    ng=20.0,
)
SEWAGE_NEAR_SCHOOL = ScoreComponents(
    cs=80.0,
    ps=85.0,
    ex=60.0,
    vu=85.0,
    sv=90.0,
    ng=65.0,
)

WORKED_EXAMPLES: tuple[tuple[str, ScoreComponents, float, ScoreBand], ...] = (
    ("Road A", ROAD_A, 30.10, "lower"),
    ("Road B", ROAD_B, 62.50, "moderate"),
    ("Metro-station pothole", METRO_POTHOLE, 50.90, "moderate"),
    ("Hospital-access pothole", HOSPITAL_POTHOLE, 54.60, "moderate"),
    ("Sewage near a school", SEWAGE_NEAR_SCHOOL, 79.00, "high"),
)


def test_road_a_score() -> None:
    result = compute_score(ROAD_A)

    assert result.total == 30.10
    assert result.band == "lower"


def test_road_b_score() -> None:
    result = compute_score(ROAD_B)

    assert result.total == 62.50
    assert result.band == "moderate"


def test_metro_station_pothole_score() -> None:
    result = compute_score(METRO_POTHOLE)

    assert result.total == 50.90
    assert result.band == "moderate"


def test_hospital_access_pothole_score() -> None:
    result = compute_score(HOSPITAL_POTHOLE)

    assert result.total == 54.60
    assert result.band == "moderate"


def test_sewage_near_school_score() -> None:
    result = compute_score(SEWAGE_NEAR_SCHOOL)

    assert result.total == 79.00
    assert result.band == "high"


def test_weights_sum_to_one() -> None:
    assert sum(WEIGHTS.values()) == 1.0


@pytest.mark.parametrize("invalid_value", [101.0, -1.0])
def test_component_outside_range_raises(invalid_value: float) -> None:
    with pytest.raises(ValueError, match="between 0 and 100"):
        ScoreComponents(
            cs=invalid_value,
            ps=0.0,
            ex=0.0,
            vu=0.0,
            sv=0.0,
            ng=0.0,
        )


def _perturbed_weights(component: ComponentName, delta: float) -> Mapping[ComponentName, float]:
    changed_weight = WEIGHTS[component] + delta
    remaining_scale = (1.0 - changed_weight) / (1.0 - WEIGHTS[component])
    return {
        name: changed_weight if name == component else WEIGHTS[name] * remaining_scale
        for name in COMPONENT_NAMES
    }


def _band_with_weights(
    components: ScoreComponents,
    weights: Mapping[ComponentName, float],
) -> ScoreBand:
    values = components.as_mapping()
    total = sum(values[name] * weights[name] for name in COMPONENT_NAMES)
    if total >= 70.0:
        return "high"
    if total >= 45.0:
        return "moderate"
    return "lower"


@pytest.mark.parametrize(("name", "components", "expected_total", "expected_band"), WORKED_EXAMPLES)
def test_worked_example_band_is_stable_under_weight_perturbation(
    name: str,
    components: ScoreComponents,
    expected_total: float,
    expected_band: ScoreBand,
) -> None:
    assert compute_score(components).total == expected_total

    for component in COMPONENT_NAMES:
        for delta in (-0.03, 0.03):
            weights = _perturbed_weights(component, delta)
            assert sum(weights.values()) == pytest.approx(1.0)
            actual_band = _band_with_weights(components, weights)
            assert actual_band == expected_band, (
                f"{name} changes from {expected_band} to {actual_band} when "
                f"{component} is perturbed by {delta:+.2f}"
            )
