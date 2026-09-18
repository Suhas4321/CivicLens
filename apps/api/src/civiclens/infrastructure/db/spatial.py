"""Schema for the offline OpenStreetMap reference data.

These tables hold *reference* data, not domain entities: they are derived
wholesale from an OSM extract, they are replaced as a unit by a re-ingest, and
no citizen or officer record points at them. They are therefore declared as
``Table`` objects rather than ORM classes, and every read is explicit SQL in
``civiclens.infrastructure.osm.queries``.

They live in their own ``MetaData`` for a concrete reason. Migration
``20260912_0001`` builds the core schema with
``Base.metadata.create_all(bind)`` — an unscoped call that creates *every* table
registered on ``Base``. Registering geography columns there would make the very
first migration depend on the PostGIS extension already existing, which on a
fresh Cloud SQL instance it does not. Keeping this metadata separate means
migration ``0001`` is unchanged and untouched, and migration ``0002`` can check
for PostGIS and fail with an actionable message before creating anything.

Attribution obligation: this data is OpenStreetMap, licensed ODbL 1.0. Any
surface that renders it must carry "© OpenStreetMap contributors".
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from civiclens.infrastructure.db.base import NAMING_CONVENTION
from civiclens.infrastructure.db.geography import Geography

SPATIAL_METADATA = MetaData(naming_convention=NAMING_CONVENTION)

OSM_TYPE_CHECK = "osm_type IN ('n', 'w', 'r')"
"""OSM ids are only unique *within* a type: node 123 and way 123 are unrelated
objects. Every table keyed by an OSM id therefore carries the type alongside it.
"""


osm_ingest_run = Table(
    "osm_ingest_run",
    SPATIAL_METADATA,
    Column("id", PGUUID(as_uuid=True), primary_key=True),
    # Provenance. A priority score derived from OSM context is only defensible if
    # we can say exactly which extract produced that context, so the source file
    # is recorded by digest, not just by name.
    Column("source_url", Text, nullable=False),
    Column("source_sha256", String(64), nullable=False),
    Column("source_bytes", BigInteger, nullable=False),
    # The extract's own replication timestamp from the PBF header: the real
    # "as of" date of the map data, which is not the date we downloaded it.
    Column("osm_data_timestamp", Text),
    Column("bbox", Text, nullable=False),
    Column("config_version", Text, nullable=False),
    Column("osmium_version", Text, nullable=False),
    Column(
        "started_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    ),
    Column("finished_at", DateTime(timezone=True)),
    Column("counts", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    CheckConstraint("length(source_sha256) = 64", name="source_sha256_length"),
)


osm_road = Table(
    "osm_road",
    SPATIAL_METADATA,
    # The OSM way id is the natural key and is what a snapped report stores, so
    # it is the primary key. autoincrement=False keeps SQLAlchemy from turning a
    # BigInteger primary key into an identity column.
    Column("osm_id", BigInteger, primary_key=True, autoincrement=False),
    Column("highway", Text, nullable=False),
    Column("name", Text),
    # Kannada name, kept so officer and public surfaces can show the road name a
    # reporter would actually recognise on a signboard.
    Column("name_kn", Text),
    # Double[float]() rather than a bare Double: SQLAlchemy's Double inherits
    # Float's overloaded __init__, which binds to Float rather than Double, so the
    # element type is otherwise Unknown under pyright strict.
    Column("length_m", Double[float](), nullable=False),
    Column("geom", Geography("LineString"), nullable=False),
    Index("ix_osm_road_geom", "geom", postgresql_using="gist"),
    Index("ix_osm_road_highway", "highway"),
    CheckConstraint("length_m > 0", name="length_positive"),
)


osm_way_node = Table(
    "osm_way_node",
    SPATIAL_METADATA,
    # Way/node incidence, kept solely to answer "are these two roads connected?"
    # REBUILD_05 §2.4 groups linear-asset reports across the *same or a 1-hop*
    # way, so two potholes either side of a junction group together while two on
    # parallel streets 40 m apart do not. Two ways are 1-hop neighbours exactly
    # when they share a node, which is a self-join on this table.
    Column(
        "way_osm_id",
        BigInteger,
        ForeignKey("osm_road.osm_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("seq", Integer, nullable=False),
    Column("node_osm_id", BigInteger, nullable=False),
    PrimaryKeyConstraint("way_osm_id", "seq"),
    Index("ix_osm_way_node_node_osm_id", "node_osm_id"),
    CheckConstraint("seq >= 0", name="seq_non_negative"),
)


locality = Table(
    "locality",
    SPATIAL_METADATA,
    Column("osm_type", String(1), nullable=False),
    Column("osm_id", BigInteger, nullable=False),
    Column("name", Text, nullable=False),
    Column("name_kn", Text),
    Column("place", Text, nullable=False),
    # Always present, and the only column the locality lookup requires.
    Column("centroid", Geography("Point"), nullable=False),
    # Present only where OSM maps the suburb as a closed way. In Bengaluru most
    # place=suburb objects are bare nodes, so this is legitimately sparse and the
    # lookup falls back to nearest-centroid. Populating it where it exists still
    # gives an exact containment answer for the localities that have one.
    Column("boundary", Geography("MultiPolygon")),
    PrimaryKeyConstraint("osm_type", "osm_id"),
    Index("ix_locality_centroid", "centroid", postgresql_using="gist"),
    Index("ix_locality_boundary", "boundary", postgresql_using="gist"),
    Index("ix_locality_name", "name"),
    CheckConstraint(OSM_TYPE_CHECK, name="osm_type_allowed"),
)


osm_poi = Table(
    "osm_poi",
    SPATIAL_METADATA,
    Column("osm_type", String(1), nullable=False),
    Column("osm_id", BigInteger, nullable=False),
    # Our normalised category, not the raw OSM tag. The tag-to-category mapping
    # is policy and lives in config/geography/, so the ingest can be re-run with
    # a corrected mapping without a schema change.
    Column("category", Text, nullable=False),
    Column("name", Text),
    Column("name_kn", Text),
    # A point even for POIs that OSM maps as a building outline: proximity is
    # the only question we ask of a POI, so a centroid is sufficient and a
    # polygon would cost storage and index time for no gain in answer quality.
    Column("geom", Geography("Point"), nullable=False),
    PrimaryKeyConstraint("osm_type", "osm_id"),
    Index("ix_osm_poi_geom", "geom", postgresql_using="gist"),
    Index("ix_osm_poi_category", "category"),
    CheckConstraint(OSM_TYPE_CHECK, name="osm_type_allowed"),
)


SPATIAL_TABLES: tuple[Table, ...] = (
    osm_ingest_run,
    osm_road,
    osm_way_node,
    locality,
    osm_poi,
)
"""Creation order. ``osm_way_node`` references ``osm_road``, so the tuple is
also the order a truncate must be reversed in.
"""
