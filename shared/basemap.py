"""Projection + geography loading helpers.

Plan §5.2: spatial math in EPSG:2263 (NY Long Island State Plane, feet);
reproject to EPSG:4326 only for output.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parents[1]
GEO_DIR = REPO_ROOT / "geographies"

EPSG_ANALYSIS = 2263  # NY Long Island State Plane (feet)
EPSG_DISPLAY = 4326   # WGS84 lat/lon


GeographyKind = Literal["cd", "nta", "tract", "modzcta"]

_GEO_FILES = {
    "cd": "community_districts_59.geojson",
    "nta": "nta_2020.geojson",
    "tract": "census_tracts_2020.geojson",
    "modzcta": "modzcta.geojson",
}


def geo_path(kind: GeographyKind) -> Path:
    """Resolve the on-disk path for a canonical geography file."""
    if kind not in _GEO_FILES:
        raise ValueError(f"unknown geography: {kind!r}. expected one of {list(_GEO_FILES)}")
    return GEO_DIR / _GEO_FILES[kind]


def load(kind: GeographyKind, project: bool = True):
    """Load a canonical NYC geography file.

    Imports geopandas lazily so callers that only need the path don't pay
    the import cost.
    """
    import geopandas as gpd

    path = geo_path(kind)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. run `make geographies` (or "
            f"`python scripts/download_geographies.py`) first."
        )
    gdf = gpd.read_file(path)
    if project:
        gdf = gdf.to_crs(epsg=EPSG_ANALYSIS)
    return gdf


def to_display(gdf):
    """Reproject a GeoDataFrame back to WGS84 for output / web display."""
    return gdf.to_crs(epsg=EPSG_DISPLAY)


def cd_code(borough: str, number: int) -> str:
    """Canonical 3-digit CD code (e.g. ``cd_code('BK', 1) == '301'``).

    NYC convention: Manhattan=1, Bronx=2, Brooklyn=3, Queens=4, Staten Island=5.
    """
    borough_to_prefix = {
        "MN": "1", "MANHATTAN": "1",
        "BX": "2", "BRONX": "2",
        "BK": "3", "BROOKLYN": "3",
        "QN": "4", "QUEENS": "4",
        "SI": "5", "STATEN ISLAND": "5",
    }
    prefix = borough_to_prefix.get(borough.upper())
    if prefix is None:
        raise ValueError(f"unknown borough {borough!r}")
    if not 1 <= number <= 18:
        raise ValueError(f"cd number out of range: {number}")
    return f"{prefix}{number:02d}"
