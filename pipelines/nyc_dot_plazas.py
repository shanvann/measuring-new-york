"""NYC DOT Pedestrian Plazas (Socrata dataset k5k6-6jex).

Used by Chapter 5 (Public Space & Urban Experience) for the open-space
axis (parks + plazas as *gathering* space) and the pedestrian-realm axis
(plazas as pedestrianized street space). The DOT plaza program converts
underused roadbed into public plazas; this is the authoritative mapped
layer.

Each record is a ``MultiPolygon`` plaza footprint carrying ``plazaname``,
``borocd`` (the 3-digit BoroCD — so plazas can be assigned to a community
district WITHOUT a spatial join), ``shape_area`` (sq ft, native State
Plane), and the on/from/to street descriptors. Small layer (~70 plazas)
so we pull the whole thing in one shot.

Vintage pin: 2026-06-01. Snapshot pinning is implicit in the cache key +
manifest entry (no reliable created/modified field on this dataset).

Usage::

    python -m pipelines.nyc_dot_plazas --dry-run
    python -m pipelines.nyc_dot_plazas
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from shared import cache  # noqa: E402

DATASET_ID = "k5k6-6jex"
ENDPOINT = f"https://data.cityofnewyork.us/resource/{DATASET_ID}.geojson"


def build_query(snapshot: str = "2026-06-01") -> dict:
    del snapshot  # snapshot pinning is implicit in the cache key
    return {
        "$select": (
            "plazaname, borocd, boroname, onstreet, fromstreet, tostreet, "
            "shape_area, the_geom"
        ),
        "$limit": "5000",
    }


def fetch(*, snapshot: str = "2026-06-01") -> Path:
    """Fetch the full Pedestrian Plazas GeoJSON; return the cached path."""
    import requests

    cache_name = f"nyc_dot_plazas/plazas-{snapshot}.geojson"
    path = cache.path_for(cache_name)
    if cache.is_cached(cache_name):
        print(f"[cache hit] {cache_name}")
        return path

    params = build_query(snapshot=snapshot)
    print(f"[fetch] NYC DOT Pedestrian Plazas  snapshot={snapshot}")
    r = requests.get(ENDPOINT, params=params, timeout=120)
    r.raise_for_status()
    payload = r.json()
    path.write_text(json.dumps(payload))
    cache.record(cache_name, r.url)
    n = len(payload.get("features", []))
    print(f"  -> {n} features  ({path.stat().st_size:,} bytes)")
    return path


def load(*, snapshot: str = "2026-06-01"):
    """Return a GeoDataFrame of plazas (EPSG:2263, feet).

    ``shape_area`` is coerced to numeric (sq ft) for the per-capita
    open-space supply metric used by the chapter's path-B fallback.
    """
    import geopandas as gpd
    import pandas as pd

    path = fetch(snapshot=snapshot)
    gdf = gpd.read_file(path)
    if "shape_area" in gdf.columns:
        gdf["shape_area"] = pd.to_numeric(gdf["shape_area"], errors="coerce")
    return gdf.to_crs(epsg=2263)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--snapshot", default="2026-06-01")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if args.dry_run:
        print(f"[dry-run] GET {ENDPOINT}")
        for k, v in build_query(snapshot=args.snapshot).items():
            print(f"  {k} = {v}")
        return 0
    fetch(snapshot=args.snapshot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
