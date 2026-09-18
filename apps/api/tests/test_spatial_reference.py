"""Spatial schema and query tests against a real PostGIS database.

Gated on ``RUN_POSTGRES_TESTS=1`` like the other integration suite, because these
need PostGIS and migration ``20260915_0002`` applied.

Almost everything here runs on a synthetic seven-object fixture built with
``ST_GeogFromText`` rather than on an ingested extract. That is deliberate: the
questions being asked — does snapping prefer the nearer of two parallel streets,
does boundary containment beat a nearer centroid — need geometry whose distances
are known exactly, which real OSM data cannot give. The one test that does need
real data skips itself when none has been ingested.

Every test runs inside a transaction that is rolled back, so a developer's
ingested reference data survives the suite untouched.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import Connection, text

from civiclens.bootstrap.settings import get_settings
from civiclens.infrastructure.db.session import build_engine
from civiclens.infrastructure.osm.config import load_geography_config
from civiclens.infrastructure.osm.extract import ExtractStats
from civiclens.infrastructure.osm.load import (
    LoadStats,
    finish_ingest_run,
    start_ingest_run,
    truncate_reference_data,
)
from civiclens.infrastructure.osm.queries import (
    connected_road_ids,
    nearby_pois,
    postgis_version,
    reference_row_counts,
    resolve_locality,
    snap_to_road,
)

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1",
    reason="requires the dedicated PostgreSQL integration database with PostGIS",
)

CONFIG_VERSION = "bengaluru-south-v1"

# A hand-built street grid in JP Nagar. Roads A and B are one street split at a
# shared node; road C is a parallel street 20 m to the south — the case that used
# to merge wrongly under geohash bucketing.
ROAD_A, ROAD_B, ROAD_C = 1, 2, 3
_ROADS = (
    (ROAD_A, "residential", "Test Main Road", "LINESTRING(77.5800 12.9100, 77.5810 12.9100)"),
    (ROAD_B, "residential", "Test Main Road", "LINESTRING(77.5810 12.9100, 77.5820 12.9100)"),
    (ROAD_C, "residential", "Parallel Cross", "LINESTRING(77.5800 12.90982, 77.5810 12.90982)"),
)
# Road A and road B share node 2, which is what makes them 1-hop neighbours.
_WAY_NODES = (
    (ROAD_A, 0, 1),
    (ROAD_A, 1, 2),
    (ROAD_B, 0, 2),
    (ROAD_B, 1, 3),
    (ROAD_C, 0, 4),
    (ROAD_C, 1, 5),
)

# 0.001 degrees of longitude at 12.91 N.
ROAD_LENGTH_M = 108.4

# Midway along road A, about 2 m north of it and about 18 m from road C.
POINT_LON, POINT_LAT = 77.5805, 12.90998
# About 1.1 km north of everything, so nothing is within any snap radius.
FAR_LON, FAR_LAT = 77.5805, 12.9200


@pytest.fixture
def connection() -> Iterator[Connection]:
    engine = build_engine(get_settings())
    conn = engine.connect()
    transaction = conn.begin()
    try:
        yield conn
    finally:
        transaction.rollback()
        conn.close()
        engine.dispose()


@pytest.fixture
def seeded(connection: Connection) -> Connection:
    """Replace the reference tables with the synthetic grid, inside the rollback."""
    truncate_reference_data(connection)

    for osm_id, highway, name, wkt in _ROADS:
        connection.execute(
            text(
                """
                INSERT INTO osm_road (osm_id, highway, name, length_m, geom)
                VALUES (:osm_id, :highway, :name, :length_m, ST_GeogFromText(:wkt))
                """
            ),
            {
                "osm_id": osm_id,
                "highway": highway,
                "name": name,
                "length_m": ROAD_LENGTH_M,
                "wkt": wkt,
            },
        )
    connection.execute(
        text(
            """
            INSERT INTO osm_way_node (way_osm_id, seq, node_osm_id)
            VALUES (:way_osm_id, :seq, :node_osm_id)
            """
        ),
        [{"way_osm_id": way, "seq": seq, "node_osm_id": node} for way, seq, node in _WAY_NODES],
    )

    connection.execute(
        text(
            """
            INSERT INTO locality (osm_type, osm_id, name, place, centroid, boundary)
            VALUES ('w', 1000, 'Boundary Layout', 'neighbourhood',
                    ST_GeogFromText('POINT(77.5810 12.9130)'),
                    ST_GeogFromText('MULTIPOLYGON(((77.5790 12.9090, 77.5830 12.9090,
                                                    77.5830 12.9120, 77.5790 12.9120,
                                                    77.5790 12.9090)))'))
            """
        )
    )
    connection.execute(
        text(
            """
            INSERT INTO locality (osm_type, osm_id, name, place, centroid)
            VALUES ('n', 1001, 'Nearest Centroid Nagar', 'suburb',
                    ST_GeogFromText('POINT(77.5805 12.90999)'))
            """
        )
    )

    connection.execute(
        text(
            """
            INSERT INTO osm_poi (osm_type, osm_id, category, name, geom)
            VALUES (:osm_type, :osm_id, :category, :name, ST_GeogFromText(:wkt))
            """
        ),
        [
            {
                "osm_type": "n",
                "osm_id": 2000,
                "category": "hospital",
                "name": "Near Hospital",
                "wkt": "POINT(77.5806 12.9101)",
            },
            {
                "osm_type": "n",
                "osm_id": 2001,
                "category": "school",
                "name": "Mid School",
                "wkt": "POINT(77.5850 12.9100)",
            },
            {
                "osm_type": "n",
                "osm_id": 2002,
                "category": "bus_stop",
                "name": "Far Stop",
                "wkt": "POINT(77.5900 12.9100)",
            },
        ],
    )
    return connection


def test_postgis_is_enabled(connection: Connection) -> None:
    assert postgis_version(connection) is not None


def test_geography_columns_have_the_declared_subtype_and_srid(connection: Connection) -> None:
    rows = connection.execute(
        text(
            """
            SELECT f_table_name, f_geography_column, type, srid
            FROM   geography_columns
            WHERE  f_table_name IN ('osm_road', 'locality', 'osm_poi')
            """
        )
    )
    declared = {(row.f_table_name, row.f_geography_column): (row.type, row.srid) for row in rows}

    # Constrained subtypes, not a bare geography: PostGIS then rejects a polygon
    # written into a point column instead of storing it and confusing later maths.
    assert declared[("osm_road", "geom")] == ("LineString", 4326)
    assert declared[("locality", "centroid")] == ("Point", 4326)
    assert declared[("locality", "boundary")] == ("MultiPolygon", 4326)
    assert declared[("osm_poi", "geom")] == ("Point", 4326)


def test_every_geography_column_has_a_gist_index(connection: Connection) -> None:
    rows = connection.execute(
        text(
            """
            SELECT tablename, indexdef
            FROM   pg_indexes
            WHERE  tablename IN ('osm_road', 'locality', 'osm_poi')
              AND  indexdef ILIKE '%USING gist%'
            """
        )
    )
    indexed = {(row.tablename, row.indexdef.split("(")[-1].rstrip(")")) for row in rows}

    # Without these every proximity query degrades to a sequential scan, which on a
    # full extract is the difference between a millisecond and a minute.
    assert ("osm_road", "geom") in indexed
    assert ("locality", "centroid") in indexed
    assert ("locality", "boundary") in indexed
    assert ("osm_poi", "geom") in indexed


def test_snap_prefers_the_nearer_of_two_parallel_streets(seeded: Connection) -> None:
    snap = snap_to_road(seeded, POINT_LON, POINT_LAT)

    assert snap is not None
    # Road C is 18 m away and therefore inside the 25 m radius. Returning the
    # nearest rather than the first match is what keeps a pothole on this street
    # from being grouped with one on the street behind it.
    assert snap.osm_id == ROAD_A
    assert snap.name == "Test Main Road"
    assert snap.distance_m < 5.0


def test_snap_locates_the_point_along_the_way(seeded: Connection) -> None:
    snap = snap_to_road(seeded, POINT_LON, POINT_LAT)

    assert snap is not None
    assert snap.offset_fraction == pytest.approx(0.5, abs=0.02)
    assert snap.offset_m == pytest.approx(ROAD_LENGTH_M / 2, abs=3.0)


def test_snap_returns_none_rather_than_a_distant_road(seeded: Connection) -> None:
    # A report from inside a park or an unmapped lane has no road. None is the
    # honest answer; widening the radius would attach it to a road the reporter
    # never meant.
    assert snap_to_road(seeded, FAR_LON, FAR_LAT) is None


def test_connected_roads_are_one_hop_neighbours_not_parallel_streets(
    seeded: Connection,
) -> None:
    connected = connected_road_ids(seeded, ROAD_A)

    # Roads A and B are one street split at a shared node, so reports either side
    # of that junction belong together.
    assert connected == {ROAD_A, ROAD_B}
    # Road C runs parallel 20 m away and shares no node, so it must stay separate.
    assert connected_road_ids(seeded, ROAD_C) == {ROAD_C}


def test_boundary_containment_beats_a_nearer_centroid(seeded: Connection) -> None:
    match = resolve_locality(seeded, POINT_LON, POINT_LAT)

    assert match is not None
    # 'Nearest Centroid Nagar' has a centroid about a metre away, but the point
    # falls inside 'Boundary Layout'. An exact containment answer must win over a
    # nearer guess.
    assert match.name == "Boundary Layout"
    assert match.inside_boundary is True


def test_locality_falls_back_to_the_nearest_centroid_outside_any_boundary(
    seeded: Connection,
) -> None:
    # North of the boundary polygon, so only centroid distance can decide.
    match = resolve_locality(seeded, 77.5810, 12.9125)

    assert match is not None
    assert match.name == "Boundary Layout"
    assert match.inside_boundary is False
    assert match.centroid_distance_m > 0.0


def test_locality_returns_none_when_nothing_is_within_the_radius(seeded: Connection) -> None:
    # Must be outside every boundary, because containment deliberately ignores the
    # radius: a point inside a polygon is inside it however small the radius is.
    assert resolve_locality(seeded, 77.6000, 12.9500, radius_m=1.0) is None


def test_containment_ignores_the_centroid_radius(seeded: Connection) -> None:
    # The converse of the test above, stated as its own assertion so the intent is
    # not something a future reader has to infer. 'Boundary Layout' has its
    # centroid 338 m away, yet a 1 m radius still resolves it, because the point
    # falls inside its polygon.
    match = resolve_locality(seeded, POINT_LON, POINT_LAT, radius_m=1.0)

    assert match is not None
    assert match.name == "Boundary Layout"
    assert match.inside_boundary is True


def test_nearby_pois_respects_radius_and_orders_by_distance(seeded: Connection) -> None:
    found = nearby_pois(seeded, POINT_LON, POINT_LAT, radius_m=500.0)

    # The bus stop is about 1 km away and must not appear.
    assert [poi.name for poi in found] == ["Near Hospital", "Mid School"]
    assert found[0].distance_m < found[1].distance_m


def test_nearby_pois_can_be_restricted_to_categories(seeded: Connection) -> None:
    found = nearby_pois(seeded, POINT_LON, POINT_LAT, radius_m=500.0, categories=["hospital"])

    assert [poi.category for poi in found] == ["hospital"]


def test_ingest_run_records_provenance(seeded: Connection) -> None:
    run_id = start_ingest_run(
        seeded,
        source_url="https://example.invalid/karnataka.osm.pbf",
        source_sha256="a" * 64,
        source_bytes=123,
        osm_data_timestamp="2026-09-14T20:21:22Z",
        bbox="77.5,12.85,77.65,12.98",
        config_version=CONFIG_VERSION,
        osmium_version="4.3.1",
    )
    counts = finish_ingest_run(seeded, run_id, ExtractStats(roads=7), LoadStats(roads_inserted=7))

    row = seeded.execute(
        text(
            """
            SELECT osm_data_timestamp, config_version, counts, finished_at
            FROM   osm_ingest_run WHERE id = :id
            """
        ),
        {"id": run_id},
    ).one()
    assert row.osm_data_timestamp == "2026-09-14T20:21:22Z"
    assert row.config_version == CONFIG_VERSION
    assert row.finished_at is not None
    assert row.counts == counts


def test_configured_verification_points_resolve_against_ingested_data(
    connection: Connection,
) -> None:
    """The acceptance criterion for the OSM ingest, run against real data.

    Skipped until an extract has been ingested. The structural assertions always
    apply; the name assertions apply only once someone has confirmed them and
    filled them into config/geography/. Until then the resolved names are printed
    so they can be checked by eye and written back into the config.
    """
    counts = reference_row_counts(connection)
    if counts.get("osm_road", 0) == 0:
        pytest.skip("no ingested OSM data — run: make osm-fetch && make osm-ingest")

    config = load_geography_config(CONFIG_VERSION)
    assert config.verification_points, "config declares no verification points"

    for point in config.verification_points:
        snap = snap_to_road(connection, point.lon, point.lat)
        locality = resolve_locality(connection, point.lon, point.lat)
        hospitals = nearby_pois(
            connection, point.lon, point.lat, radius_m=2000.0, categories=["hospital"]
        )
        if snap is None:
            road_name, distance = "NO ROAD WITHIN 25 m", "-"
        else:
            # An unnamed road is normal in OSM and is still a valid snap target;
            # printing it as None alongside a distance reads like a contradiction.
            road_name = snap.name if snap.name is not None else f"unnamed {snap.highway}"
            distance = f"{snap.distance_m:.1f} m"
        locality_name = locality.name if locality is not None else None
        print(
            f"{point.label}: road={road_name!r} ({distance}) "
            f"locality={locality_name!r} hospitals_within_2km={len(hospitals)}"
        )

        assert snap is not None, f"{point.label}: no road within 25 m"
        assert 0.0 <= snap.offset_fraction <= 1.0
        assert locality is not None, f"{point.label}: no locality within 3 km"
        assert hospitals, f"{point.label}: no hospital within 2 km of dense South Bengaluru"

        if point.expected_road_name_contains is not None:
            assert snap.name is not None
            assert point.expected_road_name_contains.lower() in snap.name.lower()
        if point.expected_locality_contains is not None:
            assert point.expected_locality_contains.lower() in locality.name.lower()
