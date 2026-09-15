"""Ingest an OSM extract into the PostGIS reference tables.

    uv run python -m civiclens.infrastructure.osm.ingest --dry-run   # parse only
    uv run python -m civiclens.infrastructure.osm.ingest             # parse and load

``--dry-run`` needs no database and no PostGIS. It is the fast way to check a
change to the tag mapping in ``config/geography/`` before spending a full load on
it, and it prints exactly the same counters the loaded run records.

The load is one transaction: truncate, insert, record the run. There is no
partially-ingested state, because a half-loaded road network snaps reports to the
wrong segments while looking perfectly healthy.
"""

from __future__ import annotations

import argparse
import importlib.metadata
from pathlib import Path

from sqlalchemy import Engine

from civiclens.bootstrap.settings import Settings, get_settings
from civiclens.infrastructure.db.session import build_engine
from civiclens.infrastructure.osm.config import GeographyConfig, load_geography_config
from civiclens.infrastructure.osm.extract import (
    ExtractStats,
    iter_records,
    read_osm_data_timestamp,
)
from civiclens.infrastructure.osm.fetch import (
    DEFAULT_CONFIG_VERSION,
    osm_data_dir,
    sha256_of_file,
)
from civiclens.infrastructure.osm.load import (
    DEFAULT_BATCH_SIZE,
    finish_ingest_run,
    load_records,
    start_ingest_run,
    truncate_reference_data,
)
from civiclens.infrastructure.osm.queries import postgis_version, reference_row_counts


def osmium_version() -> str:
    # osmium 4.x exposes no __version__ attribute, so the installed distribution
    # metadata is the only reliable source.
    return importlib.metadata.version("osmium")


def _resolve_source(config: GeographyConfig, explicit: str | None) -> Path:
    path = Path(explicit) if explicit else osm_data_dir() / config.source.local_filename
    if not path.exists():
        raise SystemExit(f"OSM extract not found at {path}\nDownload it first:  make osm-fetch")
    return path


def _require_postgis(engine: Engine) -> str:
    with engine.connect() as connection:
        version = postgis_version(connection)
    if version is None:
        raise SystemExit(
            "PostGIS is not enabled in this database.\n"
            "Local PostgreSQL:  sudo infra/bootstrap-local-db.sh\n"
            "Docker:            make dev-db  (the compose image ships PostGIS)"
        )
    return version


def _print_stats(stats: ExtractStats) -> None:
    print(
        f"  parsed   nodes={stats.nodes_seen:,} ways={stats.ways_seen:,}\n"
        f"  kept     roads={stats.roads:,} localities={stats.localities:,} "
        f"pois={stats.pois:,} boundaries={stats.boundaries_extracted:,}"
    )
    print(
        f"  skipped  outside_bbox={stats.skipped_outside_bbox:,} "
        f"missing_location={stats.skipped_missing_location:,} "
        f"unnamed_locality={stats.skipped_unnamed_locality:,} "
        f"degenerate={stats.skipped_degenerate_geometry:,}"
    )
    for category, count in sorted(stats.counts_by_poi_category.items()):
        print(f"  poi      {category}={count:,}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest OSM reference data into PostGIS")
    parser.add_argument("--config-version", default=DEFAULT_CONFIG_VERSION)
    parser.add_argument("--source", default=None, help="path to an .osm.pbf or .osm file")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="parse and report counts without touching the database",
    )
    arguments = parser.parse_args()

    config = load_geography_config(arguments.config_version)
    source = _resolve_source(config, arguments.source)
    stats = ExtractStats()

    print(f"config:  {config.version} ({config.corporation_code})")
    print(f"bbox:    {config.bbox.as_string()}")
    print(f"source:  {source.name} ({source.stat().st_size:,} bytes)")

    if arguments.dry_run:
        for _ in iter_records(source, config, stats):
            pass
        print("dry run — nothing written")
        _print_stats(stats)
        return 0

    settings: Settings = get_settings()
    engine = build_engine(settings)
    try:
        print(f"postgis: {_require_postgis(engine)}")
        # Hashing the file is a separate full read of ~128 MB. It happens before
        # the transaction opens so the write transaction stays as short as the
        # parse itself.
        digest = sha256_of_file(source)
        timestamp = read_osm_data_timestamp(source)
        print(f"osm data as of: {timestamp or 'unknown'}")

        with engine.begin() as connection:
            truncate_reference_data(connection)
            run_id = start_ingest_run(
                connection,
                source_url=config.source.primary_url,
                source_sha256=digest,
                source_bytes=source.stat().st_size,
                osm_data_timestamp=timestamp,
                bbox=config.bbox.as_string(),
                config_version=config.version,
                osmium_version=osmium_version(),
            )
            load_stats = load_records(
                connection,
                iter_records(source, config, stats),
                batch_size=arguments.batch_size,
            )
            finish_ingest_run(connection, run_id, stats, load_stats)

        _print_stats(stats)
        print(
            f"  stored   boundaries={load_stats.boundaries_stored:,} "
            f"rejected={load_stats.boundaries_rejected:,}"
        )
        with engine.connect() as connection:
            for table, rows in sorted(reference_row_counts(connection).items()):
                print(f"  table    {table}={rows:,}")
        print(f"ingest run: {run_id}")
    finally:
        engine.dispose()

    if stats.roads == 0:
        print("ERROR: no roads were kept — check the bbox and the extract coverage")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
