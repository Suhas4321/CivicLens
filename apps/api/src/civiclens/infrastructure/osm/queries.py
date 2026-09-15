"""The spatial questions CivicLens asks of the OSM reference data.

These four queries are the whole reason the reference tables exist:

* ``snap_to_road`` — which street is this report on, and how far along it?
  Replaces the geohash bucketing in the archived Stage 4 design. Snapping first
  is what stops two potholes on parallel streets 40 m apart from merging into one
  problem, which was the single worst defect in the old grouping design
  (``docs/REBUILD_05_LOCATION_ABUSE_AND_CLOSURE.md`` §2.3).
* ``resolve_locality`` — which neighbourhood is this, for the ward-first
  dashboard and for areal grouping.
* ``nearby_pois`` — the vulnerability context behind the VU component of the
  priority score.
* ``connected_road_ids`` — the 1-hop way set, so reports either side of a
  junction group together and reports on a different street do not.

The point argument is written out at each use rather than hoisted into a CTE.
Joining against a single-row CTE can make the planner treat the point as a join
input instead of a constant and skip the GiST index, and losing the index turns a
sub-millisecond lookup into a full table scan. Verbosity is the cheaper cost.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import Connection, text

_POINT = "ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography"

DEFAULT_ROAD_SNAP_RADIUS_M = 25.0
"""Matches REBUILD_05 §2.3. Wide enough for GPS scatter and a road centreline
offset from the kerb the reporter is standing on; narrow enough that it does not
reach across a divided carriageway to the opposite service road.
"""

DEFAULT_LOCALITY_RADIUS_M = 3000.0
"""Only used for the nearest-centroid fallback. Bengaluru suburb nodes are dense
enough that a match is normally within a kilometre; 3 km stops a point in an
unmapped pocket from being labelled with a suburb on the other side of the city.
"""


@dataclass(frozen=True, slots=True)
class RoadSnap:
    osm_id: int
    highway: str
    name: str | None
    name_kn: str | None
    length_m: float
    distance_m: float
    # Fractional position along the way, 0.0 at the first node and 1.0 at the
    # last. Stored on a report so two reports on the same long road can be told
    # apart by position rather than only by straight-line distance.
    offset_fraction: float

    @property
    def offset_m(self) -> float:
        return self.offset_fraction * self.length_m


@dataclass(frozen=True, slots=True)
class LocalityMatch:
    osm_type: str
    osm_id: int
    name: str
    name_kn: str | None
    place: str
    centroid_distance_m: float
    # True when the point falls inside a mapped boundary polygon, which is an
    # exact answer. False means this is the nearest centroid, which is a guess —
    # callers that display the locality to an officer should be able to say which.
    inside_boundary: bool


@dataclass(frozen=True, slots=True)
class NearbyPoi:
    osm_type: str
    osm_id: int
    category: str
    name: str | None
    distance_m: float


_SNAP_TO_ROAD = text(
    f"""
    SELECT osm_id,
           highway,
           name,
           name_kn,
           length_m,
           ST_Distance(geom, {_POINT})                    AS distance_m,
           ST_LineLocatePoint(geom::geometry, {_POINT}::geometry) AS offset_fraction
    FROM   osm_road
    WHERE  ST_DWithin(geom, {_POINT}, :radius_m)
    ORDER  BY ST_Distance(geom, {_POINT})
    LIMIT  1
    """
)

_RESOLVE_LOCALITY = text(
    f"""
    SELECT osm_type,
           osm_id,
           name,
           name_kn,
           place,
           ST_Distance(centroid, {_POINT}) AS centroid_distance_m,
           (boundary IS NOT NULL AND ST_Covers(boundary, {_POINT})) AS inside_boundary
    FROM   locality
    WHERE  (boundary IS NOT NULL AND ST_Covers(boundary, {_POINT}))
       OR  ST_DWithin(centroid, {_POINT}, :radius_m)
    ORDER  BY inside_boundary DESC, centroid_distance_m ASC
    LIMIT  1
    """
)

_NEARBY_POIS = text(
    f"""
    SELECT osm_type,
           osm_id,
           category,
           name,
           ST_Distance(geom, {_POINT}) AS distance_m
    FROM   osm_poi
    WHERE  ST_DWithin(geom, {_POINT}, :radius_m)
      AND  (:all_categories OR category = ANY(:categories))
    ORDER  BY distance_m ASC
    LIMIT  :limit
    """
)

# Two ways are 1-hop neighbours exactly when they share a node. The result
# includes the input way, because the caller wants "this road and its immediate
# continuations" as one set.
_CONNECTED_ROADS = text(
    """
    SELECT DISTINCT neighbour.way_osm_id
    FROM   osm_way_node AS origin
    JOIN   osm_way_node AS neighbour
           ON neighbour.node_osm_id = origin.node_osm_id
    WHERE  origin.way_osm_id = :osm_id
    """
)

_POSTGIS_VERSION = text("SELECT extversion FROM pg_extension WHERE extname = 'postgis'")

_ROW_COUNTS = text(
    """
    SELECT 'osm_road' AS table_name, count(*) AS rows FROM osm_road
    UNION ALL SELECT 'osm_way_node', count(*) FROM osm_way_node
    UNION ALL SELECT 'locality', count(*) FROM locality
    UNION ALL SELECT 'osm_poi', count(*) FROM osm_poi
    """
)


def postgis_version(connection: Connection) -> str | None:
    return connection.execute(_POSTGIS_VERSION).scalar_one_or_none()


def reference_row_counts(connection: Connection) -> dict[str, int]:
    return {row.table_name: row.rows for row in connection.execute(_ROW_COUNTS)}


def snap_to_road(
    connection: Connection,
    lon: float,
    lat: float,
    *,
    radius_m: float = DEFAULT_ROAD_SNAP_RADIUS_M,
) -> RoadSnap | None:
    """The nearest road within ``radius_m``, or None if the point is not on one.

    None is a legitimate and common answer — a report from inside a park, a large
    campus or an unmapped lane. Callers must handle it rather than widening the
    radius, because a road found 200 m away is not the road the reporter meant.
    """
    row = connection.execute(
        _SNAP_TO_ROAD, {"lon": lon, "lat": lat, "radius_m": radius_m}
    ).one_or_none()
    if row is None:
        return None
    return RoadSnap(
        osm_id=row.osm_id,
        highway=row.highway,
        name=row.name,
        name_kn=row.name_kn,
        length_m=row.length_m,
        distance_m=row.distance_m,
        offset_fraction=row.offset_fraction,
    )


def resolve_locality(
    connection: Connection,
    lon: float,
    lat: float,
    *,
    radius_m: float = DEFAULT_LOCALITY_RADIUS_M,
) -> LocalityMatch | None:
    row = connection.execute(
        _RESOLVE_LOCALITY, {"lon": lon, "lat": lat, "radius_m": radius_m}
    ).one_or_none()
    if row is None:
        return None
    return LocalityMatch(
        osm_type=row.osm_type,
        osm_id=row.osm_id,
        name=row.name,
        name_kn=row.name_kn,
        place=row.place,
        centroid_distance_m=row.centroid_distance_m,
        inside_boundary=row.inside_boundary,
    )


def nearby_pois(
    connection: Connection,
    lon: float,
    lat: float,
    *,
    radius_m: float,
    categories: Sequence[str] | None = None,
    limit: int = 50,
) -> tuple[NearbyPoi, ...]:
    rows = connection.execute(
        _NEARBY_POIS,
        {
            "lon": lon,
            "lat": lat,
            "radius_m": radius_m,
            "all_categories": categories is None,
            "categories": list(categories) if categories is not None else [],
            "limit": limit,
        },
    )
    return tuple(
        NearbyPoi(
            osm_type=row.osm_type,
            osm_id=row.osm_id,
            category=row.category,
            name=row.name,
            distance_m=row.distance_m,
        )
        for row in rows
    )


def connected_road_ids(connection: Connection, osm_id: int) -> frozenset[int]:
    rows = connection.execute(_CONNECTED_ROADS, {"osm_id": osm_id})
    return frozenset(row.way_osm_id for row in rows)
