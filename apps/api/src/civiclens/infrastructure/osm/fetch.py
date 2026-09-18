"""Download the OSM extract named in the geography configuration.

A Python module rather than a curl line in the Makefile so the URL stays in one
place — ``config/geography/<version>.json`` — and so the digest that gets recorded
against an ingest run is computed by the same code that fetched the file.

Run with:

    uv run python -m civiclens.infrastructure.osm.fetch
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import urllib.request
from pathlib import Path

from civiclens.bootstrap.policy import repository_root
from civiclens.infrastructure.osm.config import GeographyConfig, load_geography_config

DEFAULT_CONFIG_VERSION = "bengaluru-south-v1"
_CHUNK = 1024 * 1024
_USER_AGENT = "CivicLens/dev (offline OSM ingest; contact via repository)"


def osm_data_dir(root: Path | None = None) -> Path:
    """Where extracts live. Git-ignored: these are large, reproducible downloads."""
    return (root or repository_root()) / "data" / "osm"


def sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path) -> Path:
    """Stream ``url`` to ``destination`` via a ``.part`` file.

    The rename is the commit: an interrupted download leaves a ``.part`` behind
    rather than a truncated file that a later ingest would happily read as a
    complete extract.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})  # noqa: S310
    with urllib.request.urlopen(request) as response, partial.open("wb") as handle:  # noqa: S310
        shutil.copyfileobj(response, handle, _CHUNK)
    partial.replace(destination)
    return destination


def fetch_extract(
    config: GeographyConfig,
    *,
    root: Path | None = None,
    use_fallback: bool = False,
    force: bool = False,
) -> Path:
    destination = osm_data_dir(root) / config.source.local_filename
    if destination.exists() and not force:
        return destination
    url = config.source.fallback_url if use_fallback else config.source.primary_url
    return download(url, destination)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download the OSM extract for ingestion")
    parser.add_argument("--config-version", default=DEFAULT_CONFIG_VERSION)
    parser.add_argument(
        "--fallback",
        action="store_true",
        help="use the Geofabrik Southern Zone mirror instead of the primary extract",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="re-download even if the file is already present",
    )
    arguments = parser.parse_args()

    config = load_geography_config(arguments.config_version)
    expected = (
        config.source.fallback_bytes_approx
        if arguments.fallback
        else config.source.primary_bytes_approx
    )
    mirror = "fallback" if arguments.fallback else "primary"
    print(f"source: {mirror} (~{expected // 1_000_000} MB)")
    path = fetch_extract(config, use_fallback=arguments.fallback, force=arguments.force)
    size = path.stat().st_size
    print(f"file:   {path}")
    print(f"bytes:  {size:,}")
    print(f"sha256: {sha256_of_file(path)}")
    if size < expected // 2:
        # Not a checksum failure — the upstream extract legitimately changes every
        # few days — but a file less than half the documented size is almost
        # certainly a truncated download or an error page.
        print("WARNING: file is far smaller than expected; re-run with --force")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
