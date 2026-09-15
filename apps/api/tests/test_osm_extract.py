"""Extraction tests that need neither PostGIS nor a 128 MB download.

Everything decided during extraction — which objects count, how a footprint
becomes a point, what happens to a way whose nodes fall outside the extract — is
exercised against a hand-written fixture small enough to read in one screen. That
is the only way these decisions stay checkable: against the real Karnataka extract
a dropped category looks identical to a sparsely mapped neighbourhood.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from civiclens.infrastructure.osm.config import load_geography_config
from civiclens.infrastructure.osm.extract import (
    ExtractStats,
    LocalityRecord,
    PoiRecord,
    Record,
    RoadRecord,
    iter_records,
    polygon_centroid,
    read_osm_data_timestamp,
)

CONFIG_VERSION = "bengaluru-south-v1"

# Inside the configured bbox (77.50..77.65, 12.85..12.98) unless a comment says
# otherwise. Latitudes near 12.91 put the fixture in JP Nagar, the target area.
FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="civiclens-test">
  <node id="1" lat="12.9100" lon="77.5800" version="1"/>
  <node id="2" lat="12.9100" lon="77.5810" version="1"/>
  <node id="3" lat="12.9100" lon="77.5820" version="1"/>

  <node id="20" lat="12.9105" lon="77.5810" version="1">
    <tag k="place" v="suburb"/>
    <tag k="name" v="J. P. Nagar"/>
    <tag k="name:kn" v="ಜೆ. ಪಿ. ನಗರ"/>
  </node>
  <node id="21" lat="12.9106" lon="77.5811" version="1">
    <tag k="place" v="suburb"/>
  </node>
  <node id="22" lat="12.9107" lon="77.7500" version="1">
    <tag k="place" v="suburb"/>
    <tag k="name" v="Outside The Box"/>
  </node>

  <node id="30" lat="12.9101" lon="77.5806" version="1">
    <tag k="amenity" v="clinic"/>
    <tag k="healthcare" v="hospital"/>
    <tag k="name" v="Priority Test Hospital"/>
  </node>
  <node id="31" lat="12.9102" lon="77.5807" version="1">
    <tag k="highway" v="bus_stop"/>
    <tag k="name" v="Sarakki Stop"/>
  </node>
  <node id="32" lat="12.9103" lon="77.5808" version="1">
    <tag k="shop" v="bakery"/>
    <tag k="name" v="Not A Civic Asset"/>
  </node>

  <node id="40" lat="12.9110" lon="77.5800" version="1"/>
  <node id="41" lat="12.9110" lon="77.5804" version="1"/>
  <node id="42" lat="12.9112" lon="77.5804" version="1"/>
  <node id="43" lat="12.9112" lon="77.5800" version="1"/>

  <node id="50" lat="12.9120" lon="77.5800" version="1"/>
  <node id="51" lat="12.9120" lon="77.5840" version="1"/>
  <node id="52" lat="12.9140" lon="77.5840" version="1"/>
  <node id="53" lat="12.9140" lon="77.5800" version="1"/>

  <way id="100" version="1">
    <nd ref="1"/><nd ref="2"/><nd ref="3"/>
    <tag k="highway" v="residential"/>
    <tag k="name" v="Test Main Road"/>
    <tag k="name:kn" v="ಟೆಸ್ಟ್ ಮುಖ್ಯ ರಸ್ತೆ"/>
  </way>
  <way id="101" version="1">
    <nd ref="1"/><nd ref="2"/>
    <tag k="highway" v="track"/>
    <tag k="name" v="Farm Track"/>
  </way>
  <way id="102" version="1">
    <nd ref="1"/><nd ref="9999"/>
    <tag k="highway" v="residential"/>
    <tag k="name" v="Road Off The Edge"/>
  </way>

  <way id="110" version="1">
    <nd ref="40"/><nd ref="41"/><nd ref="42"/><nd ref="43"/><nd ref="40"/>
    <tag k="amenity" v="hospital"/>
    <tag k="name" v="Footprint Hospital"/>
  </way>

  <way id="120" version="1">
    <nd ref="50"/><nd ref="51"/><nd ref="52"/><nd ref="53"/><nd ref="50"/>
    <tag k="place" v="neighbourhood"/>
    <tag k="name" v="Mapped Boundary Layout"/>
  </way>
</osm>
"""


@pytest.fixture(scope="module")
def fixture_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("osm") / "fixture.osm"
    path.write_text(FIXTURE, encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def extracted(fixture_path: Path) -> tuple[list[Record], ExtractStats]:
    config = load_geography_config(CONFIG_VERSION)
    stats = ExtractStats()
    return list(iter_records(fixture_path, config, stats)), stats


def _roads(records: list[Record]) -> dict[int, RoadRecord]:
    return {r.osm_id: r for r in records if isinstance(r, RoadRecord)}


def _localities(records: list[Record]) -> dict[tuple[str, int], LocalityRecord]:
    return {(r.osm_type, r.osm_id): r for r in records if isinstance(r, LocalityRecord)}


def _pois(records: list[Record]) -> dict[tuple[str, int], PoiRecord]:
    return {(r.osm_type, r.osm_id): r for r in records if isinstance(r, PoiRecord)}


def test_geography_config_loads_and_derives_filter_keys() -> None:
    config = load_geography_config(CONFIG_VERSION)

    assert config.corporation_code == "BSCC"
    assert config.attribution == "© OpenStreetMap contributors"
    assert "residential" in config.highway_values
    # track and cycleway are not municipal complaint surfaces and must not be kept.
    assert "track" not in config.highway_values
    assert "suburb" in config.place_values
    # Every key the tag rules mention has to reach the osmium filter, or the C++
    # side would silently discard objects Python was about to match.
    assert {"highway", "place", "amenity", "healthcare", "railway"} <= (config.interesting_tag_keys)
    priorities = [rule.priority for rule in config.poi_rules_by_priority]
    assert priorities == sorted(priorities, reverse=True)


def test_road_is_extracted_with_geometry_length_and_node_incidence(
    extracted: tuple[list[Record], ExtractStats],
) -> None:
    records, _ = extracted
    road = _roads(records)[100]

    assert road.highway == "residential"
    assert road.name == "Test Main Road"
    assert road.name_kn == "ಟೆಸ್ಟ್ ಮುಖ್ಯ ರಸ್ತೆ"
    # 0.002 degrees of longitude at 12.91 N is about 217 m.
    assert 210.0 < road.length_m < 225.0
    # WKB type 2 is LineString, little-endian: "01" + "02000000".
    assert road.geom_wkb_hex.startswith("0102000000")
    # Node ids in order, which is what makes junction adjacency computable.
    assert road.node_ids == (1, 2, 3)


def test_road_classes_outside_the_configured_set_are_dropped(
    extracted: tuple[list[Record], ExtractStats],
) -> None:
    records, _ = extracted
    assert 101 not in _roads(records)


def test_way_with_a_node_outside_the_extract_is_dropped_not_truncated(
    extracted: tuple[list[Record], ExtractStats],
) -> None:
    records, stats = extracted
    # Way 102 references node 9999, which is not in the file. A truncated
    # centreline would snap reports to the wrong place, so the whole way goes.
    assert 102 not in _roads(records)
    assert stats.skipped_missing_location >= 1


def test_named_place_node_becomes_a_locality_with_no_boundary(
    extracted: tuple[list[Record], ExtractStats],
) -> None:
    records, _ = extracted
    locality = _localities(records)[("n", 20)]

    assert locality.name == "J. P. Nagar"
    assert locality.name_kn == "ಜೆ. ಪಿ. ನಗರ"
    assert locality.place == "suburb"
    assert locality.boundary_ring_wkb_hex is None
    assert locality.centroid_wkb_hex.startswith("0101000000")


def test_unnamed_place_node_is_dropped_and_counted(
    extracted: tuple[list[Record], ExtractStats],
) -> None:
    records, stats = extracted
    assert ("n", 21) not in _localities(records)
    assert stats.skipped_unnamed_locality >= 1


def test_objects_outside_the_bbox_are_dropped_and_counted(
    extracted: tuple[list[Record], ExtractStats],
) -> None:
    records, stats = extracted
    assert ("n", 22) not in _localities(records)
    assert stats.skipped_outside_bbox >= 1


def test_poi_category_is_chosen_by_configured_priority(
    extracted: tuple[list[Record], ExtractStats],
) -> None:
    records, _ = extracted
    # The node carries amenity=clinic and healthcare=hospital. hospital has the
    # higher configured priority, so the answer must be hospital regardless of
    # which tag OSM happened to list first.
    assert _pois(records)[("n", 30)].category == "hospital"
    assert _pois(records)[("n", 31)].category == "bus_stop"


def test_untagged_and_irrelevant_objects_are_not_kept(
    extracted: tuple[list[Record], ExtractStats],
) -> None:
    records, _ = extracted
    assert ("n", 32) not in _pois(records)


def test_poi_mapped_as_a_building_footprint_becomes_a_point_inside_it(
    extracted: tuple[list[Record], ExtractStats],
) -> None:
    records, _ = extracted
    poi = _pois(records)[("w", 110)]

    assert poi.category == "hospital"
    assert poi.name == "Footprint Hospital"
    # A point, not a polygon: proximity is the only question asked of a POI.
    assert poi.geom_wkb_hex.startswith("0101000000")


def test_locality_mapped_as_a_closed_way_carries_a_boundary_ring(
    extracted: tuple[list[Record], ExtractStats],
) -> None:
    records, stats = extracted
    locality = _localities(records)[("w", 120)]

    assert locality.name == "Mapped Boundary Layout"
    assert locality.place == "neighbourhood"
    assert locality.boundary_ring_wkb_hex is not None
    assert locality.boundary_ring_wkb_hex.startswith("0102000000")
    assert stats.boundaries_extracted == 1


def test_stats_are_complete_enough_to_audit_a_run(
    extracted: tuple[list[Record], ExtractStats],
) -> None:
    _, stats = extracted
    payload = stats.as_dict()

    assert payload["roads"] == 1
    assert payload["localities"] == 2
    assert payload["pois"] == 3
    assert payload["counts_by_poi_category"] == {"hospital": 2, "bus_stop": 1}


def test_fixture_without_a_replication_timestamp_reports_unknown(fixture_path: Path) -> None:
    # A hand-written XML file has no replication timestamp. Reporting None rather
    # than the download date keeps us from dating the data more precisely than we
    # actually know it.
    assert read_osm_data_timestamp(fixture_path) is None


def test_polygon_centroid_is_area_weighted_not_the_vertex_mean() -> None:
    # A unit square: both methods agree, so this pins the basic case.
    square = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.0, 0.0)]
    lon, lat = polygon_centroid(square)
    assert lon == pytest.approx(0.5)
    assert lat == pytest.approx(0.5)

    # The same square with extra vertices traced along one edge. The vertex mean
    # is dragged towards that edge; the area-weighted centroid is not. This is the
    # real-world case of a mapper tracing one side of a suburb in detail.
    detailed = [
        (0.0, 0.0),
        (0.25, 0.0),
        (0.5, 0.0),
        (0.75, 0.0),
        (1.0, 0.0),
        (1.0, 1.0),
        (0.0, 1.0),
        (0.0, 0.0),
    ]
    vertex_mean_lat = sum(lat for _, lat in detailed[:-1]) / len(detailed[:-1])
    _, weighted_lat = polygon_centroid(detailed)
    assert vertex_mean_lat == pytest.approx(0.2857, abs=1e-3)
    assert weighted_lat == pytest.approx(0.5)


def test_polygon_centroid_falls_back_to_the_mean_for_degenerate_input() -> None:
    # Three collinear points enclose no area, so there is no area-weighted answer.
    collinear = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)]
    assert polygon_centroid(collinear) == pytest.approx((1.0, 0.0))

    assert polygon_centroid([(77.58, 12.91)]) == pytest.approx((77.58, 12.91))

    with pytest.raises(ValueError, match="empty ring"):
        polygon_centroid([])
