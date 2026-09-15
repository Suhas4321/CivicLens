"""A minimal typed PostGIS ``geography`` column type.

Why this exists instead of GeoAlchemy2: the only thing the ORM layer needs from
PostGIS is correct DDL. Every spatial *operation* in CivicLens (``ST_DWithin``
membership, ``ST_LineLocatePoint`` linear referencing, ``<->`` nearest-neighbour
road snapping) is expressed as explicit SQL in
``civiclens.infrastructure.osm.queries``, because those queries are the product
logic and must stay readable and reviewable. Pulling in a full spatial ORM to
generate two words of DDL would add a runtime dependency, a second type
hierarchy and a layer of implicit query rewriting for no benefit.

``geography`` rather than ``geometry`` is deliberate: distances in
``geography(*, 4326)`` come back in metres on the WGS84 spheroid, so the 25 m
road-snap radius and the 120-400 m locality radii in
``docs/REBUILD_05_LOCATION_ABUSE_AND_CLOSURE.md`` are expressed in the same unit
the policy documents use. With ``geometry(*, 4326)`` those numbers would be
degrees and every call site would need a projection step it could get wrong.

The type is DDL-only on purpose. It declares no bind or result processor, so a
plain SELECT of a geography column returns the hex EWKB string PostGIS emits.
Read paths therefore always project geography columns through ``ST_AsGeoJSON``,
``ST_X``/``ST_Y`` or a distance function rather than fetching raw geometry.
"""

from __future__ import annotations

from typing import Any, Literal

from sqlalchemy.types import UserDefinedType

GeographyKind = Literal["Point", "LineString", "MultiPolygon"]
"""The geography subtypes CivicLens stores.

Constrained to the three shapes the reference data actually uses so that a typo
in a column definition is a type error rather than a runtime PostGIS error:
POIs and locality centroids are points, roads are linestrings, locality
boundaries are multipolygons.
"""

WGS84 = 4326


class Geography(UserDefinedType[str]):
    """Emits ``geography(<Kind>,<srid>)`` in ``CREATE TABLE``.

    Constrain the subtype at the column rather than using a bare ``geography``:
    PostGIS will then reject a polygon written into a point column at insert
    time, which turns a silent data defect into a failed ingest.
    """

    cache_ok = True

    def __init__(self, kind: GeographyKind, srid: int = WGS84) -> None:
        self.kind: GeographyKind = kind
        self.srid: int = srid

    def get_col_spec(self, **kw: Any) -> str:
        return f"geography({self.kind},{self.srid})"

    @property
    def python_type(self) -> type[str]:
        return str

    def __repr__(self) -> str:
        return f"Geography({self.kind!r}, srid={self.srid})"
