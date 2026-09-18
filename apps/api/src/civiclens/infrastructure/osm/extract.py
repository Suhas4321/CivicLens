"""Turn an OSM extract into CivicLens reference records.

Deliberately free of any database dependency. Extraction is the part with all the
fiddly decisions — which objects count, how a building footprint becomes a point,
what to do about a way whose nodes fall outside the extract — so it is the part
that needs to be testable against a hand-written five-node fixture rather than a
128 MB download and a live PostGIS instance.

The osmium pipeline is ordered on purpose:

    FileProcessor(source, NODE | WAY).with_locations().with_filter(KeyFilter(...))

``with_locations()`` is always applied before user filters, so untagged nodes
still populate the location index that gives ways their geometry even though the
key filter stops them from reaching Python. Restricting to ``NODE | WAY`` skips
relations entirely, which is what lets this run without osmium's area assembler.
The consequence is stated plainly: a locality mapped as a multipolygon relation
gets no boundary. In Bengaluru almost every ``place=suburb`` is a bare node, so
this costs very little and saves a second pass over the file.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import osmium
import osmium.filter
import osmium.geom
import osmium.io
import osmium.osm

from civiclens.infrastructure.osm.config import GeographyConfig

NODE = "n"
WAY = "w"

_MIN_RING_POINTS = 4
"""A closed ring needs three distinct corners plus the repeated first point."""


@dataclass(frozen=True, slots=True)
class RoadRecord:
    osm_id: int
    highway: str
    name: str | None
    name_kn: str | None
    length_m: float
    geom_wkb_hex: str
    # Carried on the road rather than emitted as separate records so the loader
    # can insert a road and its node incidences in one batch and never violate
    # the foreign key.
    node_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class LocalityRecord:
    osm_type: str
    osm_id: int
    name: str
    name_kn: str | None
    place: str
    centroid_wkb_hex: str
    # A *closed linestring*, not a polygon: osmium can only emit a ring here, and
    # PostGIS turns it into a validated multipolygon on the way in. None for
    # place nodes, which is the common case.
    boundary_ring_wkb_hex: str | None


@dataclass(frozen=True, slots=True)
class PoiRecord:
    osm_type: str
    osm_id: int
    category: str
    name: str | None
    name_kn: str | None
    geom_wkb_hex: str


Record = RoadRecord | LocalityRecord | PoiRecord


@dataclass(slots=True)
class ExtractStats:
    """Counters, including every reason an object was dropped.

    Silent skips are how a spatial ingest goes subtly wrong: half the roads
    missing looks exactly like a sparsely mapped area. Every drop is counted and
    the counts are persisted against the ingest run.
    """

    nodes_seen: int = 0
    ways_seen: int = 0
    roads: int = 0
    localities: int = 0
    pois: int = 0
    skipped_outside_bbox: int = 0
    skipped_missing_location: int = 0
    skipped_unnamed_locality: int = 0
    skipped_degenerate_geometry: int = 0
    skipped_unmatched_tags: int = 0
    boundaries_extracted: int = 0
    counts_by_poi_category: dict[str, int] = field(default_factory=dict[str, int])

    def as_dict(self) -> dict[str, object]:
        return {
            "nodes_seen": self.nodes_seen,
            "ways_seen": self.ways_seen,
            "roads": self.roads,
            "localities": self.localities,
            "pois": self.pois,
            "skipped_outside_bbox": self.skipped_outside_bbox,
            "skipped_missing_location": self.skipped_missing_location,
            "skipped_unnamed_locality": self.skipped_unnamed_locality,
            "skipped_degenerate_geometry": self.skipped_degenerate_geometry,
            "skipped_unmatched_tags": self.skipped_unmatched_tags,
            "boundaries_extracted": self.boundaries_extracted,
            "counts_by_poi_category": dict(self.counts_by_poi_category),
        }


def read_osm_data_timestamp(source: Path) -> str | None:
    """The extract's own replication timestamp, which is its true "as of" date.

    Not the download date: an extract mirror can serve a file that is days old.
    Recorded against the ingest run so a score derived from this data can be
    dated honestly.
    """
    # osmium.io.Reader with NOTHING reads the header and stops, so this does not
    # touch the body of a 128 MB file.
    reader = osmium.io.Reader(source, osmium.osm.NOTHING)
    try:
        stamp = reader.header().get("osmosis_replication_timestamp", "")
    finally:
        reader.close()
    return stamp or None


def polygon_centroid(points: Sequence[tuple[float, float]]) -> tuple[float, float]:
    """Area-weighted centroid of a ring given as ``(lon, lat)`` pairs.

    Computed in degrees rather than a projected CRS. That is a real
    approximation, and it is fine here: the result is a proximity anchor for a
    suburb or a building, the shape spans at most a couple of kilometres, and
    lon/lat distortion at 13°N shifts the answer by well under the 120-400 m
    grouping radii it feeds. It is still meaningfully better than the mean of the
    vertices, which is pulled towards whichever edge a mapper traced in most
    detail.

    Falls back to the vertex mean for a degenerate ring, which is the only
    defined answer when the enclosed area is zero.
    """
    ring = list(points)
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring = ring[:-1]
    if not ring:
        raise ValueError("cannot take the centroid of an empty ring")
    mean_lon = sum(lon for lon, _ in ring) / len(ring)
    mean_lat = sum(lat for _, lat in ring) / len(ring)
    if len(ring) < 3:
        return mean_lon, mean_lat

    twice_area = 0.0
    weighted_lon = 0.0
    weighted_lat = 0.0
    for index, (lon0, lat0) in enumerate(ring):
        lon1, lat1 = ring[(index + 1) % len(ring)]
        cross = lon0 * lat1 - lon1 * lat0
        twice_area += cross
        weighted_lon += (lon0 + lon1) * cross
        weighted_lat += (lat0 + lat1) * cross
    if abs(twice_area) < 1e-12:
        return mean_lon, mean_lat
    return weighted_lon / (3.0 * twice_area), weighted_lat / (3.0 * twice_area)


def _tags_of(obj: osmium.osm.Node | osmium.osm.Way) -> dict[str, str]:
    return {tag.k: tag.v for tag in obj.tags}


def _way_coordinates(way: osmium.osm.Way) -> list[tuple[float, float]] | None:
    """``(lon, lat)`` for every node of a way, or None if any location is missing.

    A way can reference nodes that fall outside the extract. Returning None
    rather than a partial line is the safe choice: a truncated road would snap
    reports to the wrong segment and silently corrupt grouping.
    """
    coordinates: list[tuple[float, float]] = []
    for node_ref in way.nodes:
        if not node_ref.location.valid():
            return None
        coordinates.append((node_ref.location.lon, node_ref.location.lat))
    return coordinates


def _first_matching_category(config: GeographyConfig, tags: Mapping[str, str]) -> str | None:
    for rule in config.poi_rules_by_priority:
        if rule.matches(tags):
            return rule.category
    return None


def iter_records(
    source: Path,
    config: GeographyConfig,
    stats: ExtractStats | None = None,
) -> Iterator[Record]:
    """Stream reference records out of an OSM file.

    Streaming rather than accumulating: the loader batches as records arrive, so
    peak memory does not scale with the size of the extract even though only a
    small bounding box is retained.
    """
    counters = stats if stats is not None else ExtractStats()
    wkb = osmium.geom.WKBFactory()
    processor = (
        osmium.FileProcessor(source, osmium.osm.NODE | osmium.osm.WAY)
        .with_locations()
        .with_filter(osmium.filter.KeyFilter(*sorted(config.interesting_tag_keys)))
    )

    for entity in processor:
        if isinstance(entity, osmium.osm.Node):
            counters.nodes_seen += 1
            record = _node_record(entity, config, counters, wkb)
            if record is not None:
                yield record
        elif isinstance(entity, osmium.osm.Way):
            counters.ways_seen += 1
            yield from _way_records(entity, config, counters, wkb)


def _node_record(
    node: osmium.osm.Node,
    config: GeographyConfig,
    counters: ExtractStats,
    wkb: osmium.geom.WKBFactory,
) -> Record | None:
    if not node.location.valid():
        counters.skipped_missing_location += 1
        return None
    if not config.bbox.contains(node.location.lon, node.location.lat):
        counters.skipped_outside_bbox += 1
        return None

    tags = _tags_of(node)
    place = tags.get("place")
    if place in config.place_values:
        name = tags.get("name")
        if name is None:
            # An unnamed suburb node cannot be shown to a citizen or an officer,
            # and cannot be used as a grouping key, so it is worthless to us.
            counters.skipped_unnamed_locality += 1
            return None
        counters.localities += 1
        return LocalityRecord(
            osm_type=NODE,
            osm_id=node.id,
            name=name,
            name_kn=tags.get("name:kn"),
            place=place,
            centroid_wkb_hex=wkb.create_point(node.location),
            boundary_ring_wkb_hex=None,
        )

    category = _first_matching_category(config, tags)
    if category is None:
        counters.skipped_unmatched_tags += 1
        return None
    counters.pois += 1
    counters.counts_by_poi_category[category] = counters.counts_by_poi_category.get(category, 0) + 1
    return PoiRecord(
        osm_type=NODE,
        osm_id=node.id,
        category=category,
        name=tags.get("name"),
        name_kn=tags.get("name:kn"),
        geom_wkb_hex=wkb.create_point(node.location),
    )


def _way_records(
    way: osmium.osm.Way,
    config: GeographyConfig,
    counters: ExtractStats,
    wkb: osmium.geom.WKBFactory,
) -> Iterator[Record]:
    tags = _tags_of(way)
    highway = tags.get("highway")
    place = tags.get("place")
    category = None if highway in config.highway_values else _first_matching_category(config, tags)
    relevant = (
        highway in config.highway_values or place in config.place_values or category is not None
    )
    if not relevant:
        counters.skipped_unmatched_tags += 1
        return

    coordinates = _way_coordinates(way)
    if coordinates is None:
        counters.skipped_missing_location += 1
        return
    # A way is kept whole if *any* node is inside the box, so a road crossing the
    # boundary keeps its full geometry. Linear referencing along a truncated road
    # would otherwise report the wrong offset.
    if not any(config.bbox.contains(lon, lat) for lon, lat in coordinates):
        counters.skipped_outside_bbox += 1
        return

    if highway in config.highway_values:
        road = _road_record(way, tags, coordinates, highway, counters, wkb)
        if road is not None:
            counters.roads += 1
            yield road
        return

    if place in config.place_values:
        name = tags.get("name")
        if name is None:
            counters.skipped_unnamed_locality += 1
            return
        centroid_lon, centroid_lat = polygon_centroid(coordinates)
        ring: str | None = None
        if way.is_closed() and len(coordinates) >= _MIN_RING_POINTS:
            ring = wkb.create_linestring(way)
            counters.boundaries_extracted += 1
        counters.localities += 1
        yield LocalityRecord(
            osm_type=WAY,
            osm_id=way.id,
            name=name,
            name_kn=tags.get("name:kn"),
            place=place,
            centroid_wkb_hex=wkb.create_point(
                osmium.osm.Location(centroid_lon, centroid_lat),
            ),
            boundary_ring_wkb_hex=ring,
        )
        return

    if category is not None:
        centroid_lon, centroid_lat = polygon_centroid(coordinates)
        counters.pois += 1
        counters.counts_by_poi_category[category] = (
            counters.counts_by_poi_category.get(category, 0) + 1
        )
        yield PoiRecord(
            osm_type=WAY,
            osm_id=way.id,
            category=category,
            name=tags.get("name"),
            name_kn=tags.get("name:kn"),
            geom_wkb_hex=wkb.create_point(
                osmium.osm.Location(centroid_lon, centroid_lat),
            ),
        )


def _road_record(
    way: osmium.osm.Way,
    tags: Mapping[str, str],
    coordinates: Sequence[tuple[float, float]],
    highway: str,
    counters: ExtractStats,
    wkb: osmium.geom.WKBFactory,
) -> RoadRecord | None:
    if len(set(coordinates)) < 2:
        # A "road" that is one point repeated cannot be snapped to or measured
        # along, and would violate the length_m > 0 constraint.
        counters.skipped_degenerate_geometry += 1
        return None
    length_m = osmium.geom.haversine_distance(way.nodes)
    if length_m <= 0.0:
        counters.skipped_degenerate_geometry += 1
        return None
    return RoadRecord(
        osm_id=way.id,
        highway=highway,
        name=tags.get("name"),
        name_kn=tags.get("name:kn"),
        length_m=length_m,
        geom_wkb_hex=wkb.create_linestring(way, use_nodes=osmium.geom.use_nodes.UNIQUE),
        node_ids=tuple(node_ref.ref for node_ref in way.nodes),
    )
