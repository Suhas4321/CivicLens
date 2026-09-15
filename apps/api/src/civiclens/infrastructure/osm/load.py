"""Write extracted OSM records into the PostGIS reference tables.

Every geometry crosses the boundary as hex WKB, which is what osmium produces,
and is turned into a ``geography`` by PostGIS on the way in. Nothing here parses
WKB in Python: the database is the only component that needs to understand the
bytes.

Loading is a full replace inside one transaction. Reference data has no partial
state worth keeping — a half-loaded road network would snap reports to the wrong
segments — so either the whole extract lands or the previous one stays.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Connection, text
from sqlalchemy.exc import DatabaseError

from civiclens.infrastructure.osm.extract import (
    ExtractStats,
    LocalityRecord,
    Record,
    RoadRecord,
)

DEFAULT_BATCH_SIZE = 2_000

_GEOM_FROM_HEX = "ST_SetSRID(ST_GeomFromWKB(decode(:{param}, 'hex')), 4326)::geography"

_INSERT_ROAD = text(
    f"""
    INSERT INTO osm_road (osm_id, highway, name, name_kn, length_m, geom)
    VALUES (:osm_id, :highway, :name, :name_kn, :length_m,
            {_GEOM_FROM_HEX.format(param="geom_wkb_hex")})
    ON CONFLICT (osm_id) DO NOTHING
    """
)

_INSERT_WAY_NODE = text(
    """
    INSERT INTO osm_way_node (way_osm_id, seq, node_osm_id)
    VALUES (:way_osm_id, :seq, :node_osm_id)
    ON CONFLICT (way_osm_id, seq) DO NOTHING
    """
)

_INSERT_LOCALITY = text(
    f"""
    INSERT INTO locality (osm_type, osm_id, name, name_kn, place, centroid)
    VALUES (:osm_type, :osm_id, :name, :name_kn, :place,
            {_GEOM_FROM_HEX.format(param="centroid_wkb_hex")})
    ON CONFLICT (osm_type, osm_id) DO NOTHING
    """
)

# A ring traced by a mapper can self-intersect. ST_MakeValid repairs it, and
# ST_CollectionExtract(..., 3) guarantees the result is a MultiPolygon rather
# than the GeometryCollection a repair can produce — which the geography column
# would reject. An empty result is stored as NULL, because "no boundary" is the
# honest answer for a ring we could not repair.
_UPDATE_BOUNDARY = text(
    """
    UPDATE locality
    SET    boundary = CASE WHEN ST_IsEmpty(repaired.geom) THEN NULL
                          ELSE repaired.geom::geography END
    FROM  (SELECT ST_CollectionExtract(
                    ST_MakeValid(
                      ST_MakePolygon(
                        ST_SetSRID(ST_GeomFromWKB(decode(:ring_wkb_hex, 'hex')), 4326))), 3)
                  AS geom) AS repaired
    WHERE  osm_type = :osm_type AND osm_id = :osm_id
    """
)

_INSERT_POI = text(
    f"""
    INSERT INTO osm_poi (osm_type, osm_id, category, name, name_kn, geom)
    VALUES (:osm_type, :osm_id, :category, :name, :name_kn,
            {_GEOM_FROM_HEX.format(param="geom_wkb_hex")})
    ON CONFLICT (osm_type, osm_id) DO NOTHING
    """
)

_INSERT_RUN = text(
    """
    INSERT INTO osm_ingest_run (
        id, source_url, source_sha256, source_bytes, osm_data_timestamp,
        bbox, config_version, osmium_version, counts)
    VALUES (:id, :source_url, :source_sha256, :source_bytes, :osm_data_timestamp,
            :bbox, :config_version, :osmium_version, CAST(:counts AS jsonb))
    """
)

_FINISH_RUN = text(
    """
    UPDATE osm_ingest_run
    SET    finished_at = CURRENT_TIMESTAMP, counts = CAST(:counts AS jsonb)
    WHERE  id = :id
    """
)

# Reverse dependency order: osm_way_node references osm_road.
_TRUNCATE = text("TRUNCATE osm_way_node, osm_road, locality, osm_poi")


@dataclass(slots=True)
class LoadStats:
    roads_inserted: int = 0
    way_nodes_inserted: int = 0
    localities_inserted: int = 0
    pois_inserted: int = 0
    boundaries_stored: int = 0
    boundaries_rejected: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "roads_inserted": self.roads_inserted,
            "way_nodes_inserted": self.way_nodes_inserted,
            "localities_inserted": self.localities_inserted,
            "pois_inserted": self.pois_inserted,
            "boundaries_stored": self.boundaries_stored,
            "boundaries_rejected": self.boundaries_rejected,
        }


Parameters = dict[str, Any]


@dataclass(slots=True)
class _Buffers:
    roads: list[Parameters] = field(default_factory=list[Parameters])
    way_nodes: list[Parameters] = field(default_factory=list[Parameters])
    localities: list[Parameters] = field(default_factory=list[Parameters])
    boundaries: list[Parameters] = field(default_factory=list[Parameters])
    pois: list[Parameters] = field(default_factory=list[Parameters])

    def pending(self) -> int:
        return len(self.roads) + len(self.localities) + len(self.pois)

    def clear(self) -> None:
        self.roads.clear()
        self.way_nodes.clear()
        self.localities.clear()
        self.pois.clear()


def truncate_reference_data(connection: Connection) -> None:
    connection.execute(_TRUNCATE)


def load_records(
    connection: Connection,
    records: Iterable[Record],
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> LoadStats:
    """Insert every record, batching by parent object.

    Roads and their node incidences are flushed together in that order, so the
    ``osm_way_node`` foreign key is satisfied without deferring it.
    """
    stats = LoadStats()
    buffers = _Buffers()

    for record in records:
        if isinstance(record, RoadRecord):
            buffers.roads.append(
                {
                    "osm_id": record.osm_id,
                    "highway": record.highway,
                    "name": record.name,
                    "name_kn": record.name_kn,
                    "length_m": record.length_m,
                    "geom_wkb_hex": record.geom_wkb_hex,
                }
            )
            buffers.way_nodes.extend(
                {"way_osm_id": record.osm_id, "seq": seq, "node_osm_id": node_id}
                for seq, node_id in enumerate(record.node_ids)
            )
        elif isinstance(record, LocalityRecord):
            buffers.localities.append(
                {
                    "osm_type": record.osm_type,
                    "osm_id": record.osm_id,
                    "name": record.name,
                    "name_kn": record.name_kn,
                    "place": record.place,
                    "centroid_wkb_hex": record.centroid_wkb_hex,
                }
            )
            if record.boundary_ring_wkb_hex is not None:
                buffers.boundaries.append(
                    {
                        "osm_type": record.osm_type,
                        "osm_id": record.osm_id,
                        "ring_wkb_hex": record.boundary_ring_wkb_hex,
                    }
                )
        else:
            # Narrowed to PoiRecord by exhaustion of the Record union. Adding a
            # fourth record type without a branch here becomes a pyright error on
            # the attribute accesses below rather than a silent misload.
            buffers.pois.append(
                {
                    "osm_type": record.osm_type,
                    "osm_id": record.osm_id,
                    "category": record.category,
                    "name": record.name,
                    "name_kn": record.name_kn,
                    "geom_wkb_hex": record.geom_wkb_hex,
                }
            )

        if buffers.pending() >= batch_size:
            _flush(connection, buffers, stats)

    _flush(connection, buffers, stats)
    _load_boundaries(connection, buffers, stats)
    return stats


def _flush(connection: Connection, buffers: _Buffers, stats: LoadStats) -> None:
    if buffers.roads:
        connection.execute(_INSERT_ROAD, buffers.roads)
        stats.roads_inserted += len(buffers.roads)
    if buffers.way_nodes:
        connection.execute(_INSERT_WAY_NODE, buffers.way_nodes)
        stats.way_nodes_inserted += len(buffers.way_nodes)
    if buffers.localities:
        connection.execute(_INSERT_LOCALITY, buffers.localities)
        stats.localities_inserted += len(buffers.localities)
    if buffers.pois:
        connection.execute(_INSERT_POI, buffers.pois)
        stats.pois_inserted += len(buffers.pois)
    buffers.clear()


def _load_boundaries(connection: Connection, buffers: _Buffers, stats: LoadStats) -> None:
    """Attach boundary polygons one at a time, each in its own savepoint.

    Per-row rather than batched because a single unrepairable ring must not lose
    the other boundaries, and because there are tens of these rather than tens of
    thousands, so the cost of a savepoint per row is irrelevant. A locality with a
    rejected boundary keeps its centroid and is still fully usable.
    """
    for parameters in buffers.boundaries:
        try:
            with connection.begin_nested():
                connection.execute(_UPDATE_BOUNDARY, parameters)
        except DatabaseError:
            stats.boundaries_rejected += 1
        else:
            stats.boundaries_stored += 1
    buffers.boundaries.clear()


def start_ingest_run(
    connection: Connection,
    *,
    source_url: str,
    source_sha256: str,
    source_bytes: int,
    osm_data_timestamp: str | None,
    bbox: str,
    config_version: str,
    osmium_version: str,
) -> UUID:
    run_id = uuid4()
    connection.execute(
        _INSERT_RUN,
        {
            "id": run_id,
            "source_url": source_url,
            "source_sha256": source_sha256,
            "source_bytes": source_bytes,
            "osm_data_timestamp": osm_data_timestamp,
            "bbox": bbox,
            "config_version": config_version,
            "osmium_version": osmium_version,
            "counts": "{}",
        },
    )
    return run_id


def finish_ingest_run(
    connection: Connection,
    run_id: UUID,
    extract_stats: ExtractStats,
    load_stats: LoadStats,
) -> dict[str, object]:
    counts: dict[str, object] = {
        "extract": extract_stats.as_dict(),
        "load": load_stats.as_dict(),
    }
    connection.execute(_FINISH_RUN, {"id": run_id, "counts": json.dumps(counts)})
    return counts
