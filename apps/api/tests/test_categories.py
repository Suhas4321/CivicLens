from __future__ import annotations

import json
from pathlib import Path

import pytest

from civiclens.domain.categories import load_category_config
from civiclens.shared.errors import ConfigurationError

CONFIG_VERSION = "bengaluru-south-v1"


def _rule(
    *,
    code: str = "ROAD_DAMAGE",
    agency: str | None = "BSCC",
    severity_ceiling: int | None = 65,
) -> dict[str, object]:
    return {
        "code": code,
        "label_en": "Pothole / broken road",
        "label_kn": "ಗುಂಡಿ / ಹಾಳಾದ ರಸ್ತೆ",
        "agency": agency,
        "sla_days": 15,
        "severity_ceiling": severity_ceiling,
        "grouping_geometry": "linear_road",
        "lane_1_eligible": False,
        "rankable": True,
    }


def _write_config(tmp_path: Path, categories: list[dict[str, object]]) -> None:
    path = tmp_path / "config" / "categories" / f"{CONFIG_VERSION}.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"version": CONFIG_VERSION, "categories": categories}),
        encoding="utf-8",
    )


def test_category_config_loads_electrical_hazard_rule() -> None:
    config = load_category_config(CONFIG_VERSION)
    electrical = config.by_code("ELECTRICAL_HAZARD")

    assert electrical.agency == "BESCOM"
    assert electrical.sla_days == 1
    assert electrical.severity_ceiling == 95
    assert electrical.grouping_geometry == "point_asset"
    assert "OTHER" in config.codes


def test_category_config_rejects_duplicate_code(tmp_path: Path) -> None:
    _write_config(tmp_path, [_rule(), _rule()])

    with pytest.raises(ConfigurationError, match="duplicate code"):
        load_category_config(CONFIG_VERSION, tmp_path)


def test_category_config_rejects_unknown_agency(tmp_path: Path) -> None:
    _write_config(tmp_path, [_rule(agency="UNKNOWN")])

    with pytest.raises(ConfigurationError, match="unknown agency"):
        load_category_config(CONFIG_VERSION, tmp_path)


def test_category_config_rejects_severity_above_100(tmp_path: Path) -> None:
    _write_config(tmp_path, [_rule(severity_ceiling=101)])

    with pytest.raises(ConfigurationError, match="less than or equal to 100"):
        load_category_config(CONFIG_VERSION, tmp_path)
