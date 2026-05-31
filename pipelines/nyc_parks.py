"""NYC Parks Properties (Socrata dataset enfh-gkve).

Used by Chapter 3 (Environmental Quality) for the green-space-access
axis. This is the authoritative DPR-mapped parks layer: 2,058 records
at the 2026-06-01 snapshot, every record ``class == 'PARK'`` (the
dataset is parks-only; playgrounds-only / community-gardens lookups
live in sibling datasets that we don't pull). Each record carries
``acres`` (official acreage, not derived from polygon area) and a
``multipolygon`` geometry.

Vintage pin: 2026-06-01. The dataset is small (~6 MB GeoJSON) so we
pull the whole layer in one shot — no windowing, no pagination — and
the chapter filters in-memory.

Usage::

    python -m pipelines.nyc_parks --dry-run
    python -m pipelines.nyc_parks
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from shared import cache  # noqa: E402

DATASET_ID = "enfh-gkve"
ENDPOINT = f"https://data.cityofnewyork.us/resource/{DATASET_ID}.geojson"


def build_query(snapshot: str = "2026-06-01") -> dict:
    # No created/modified field is reliably populated on this dataset;
    # snapshot pinning is implicit in the cache key + manifest entry.
    del snapshot
    return {
        "$select": (
            "gispropnum, signname, name311, class, typecategory, subcategory, "
            "borough, communityboard, acres, multipolygon"
        ),
        "$limit": "10000",
    }


def fetch(*, snapshot: str = "2026-06-01") -> Path:
    """Fetch the full Parks Properties GeoJSON; return the cached path."""
    import requests

    cache_name = f"nyc_parks/properties-{snapshot}.geojson"
    path = cache.path_for(cache_name)
    if cache.is_cached(cache_name):
        print(f"[cache hit] {cache_name}")
        return path

    params = build_query(snapshot=snapshot)
    print(f"[fetch] NYC Parks Properties  snapshot={snapshot}")
    r = requests.get(ENDPOINT, params=params, timeout=300)
    r.raise_for_status()
    payload = r.json()
    path.write_text(json.dumps(payload))
    cache.record(cache_name, r.url)
    n = len(payload.get("features", []))
    print(f"  -> {n} features  ({path.stat().st_size:,} bytes)")
    return path


def load(*, snapshot: str = "2026-06-01", min_acres: float | None = None):
    """Return a GeoDataFrame of parks (EPSG:2263, feet).

    If ``min_acres`` is set, filter to parks with ``acres >= min_acres``
    before returning. Empty / null acreage rows are dropped when the
    filter is active.
    """
    import geopandas as gpd
    import pandas as pd

    path = fetch(snapshot=snapshot)
    gdf = gpd.read_file(path)
    gdf["acres"] = pd.to_numeric(gdf["acres"], errors="coerce")
    if min_acres is not None:
        gdf = gdf[gdf["acres"] >= min_acres].copy()
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
