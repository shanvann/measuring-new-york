"""NYS Retail Food Stores (Socrata dataset 9a8c-vfzj, data.ny.gov).

Authoritative source for Chapter 4 (Access to Daily Needs), food-access
axis. Every retail food store licensed by the NYS Dept. of Agriculture &
Markets, statewide. We pull the five NYC counties only. Each record
carries ``square_footage`` (self-reported license footprint) and a point
``georeference`` — square footage is what lets us separate a full-service
supermarket from a bodega, which is central to the chapter's "can you buy
fresh food without a car" claim.

NYC county names in this dataset (uppercase):
  NEW YORK (MN), KINGS (BK), QUEENS (QN), BRONX (BX), RICHMOND (SI).
  ~11,472 NYC stores at the 2026-06-01 snapshot; ~77% carry a non-null
  ``square_footage`` (stores with null footage are dropped from the
  supermarket set — a known undercount, noted in the chapter footer).

Vintage pin: 2026-06-01 (implicit in the cache key + manifest entry; the
dataset has no reliable per-row modified date). Small enough to pull the
whole NYC slice in one request — no pagination.

Usage::

    python -m pipelines.nys_food_stores --dry-run
    python -m pipelines.nys_food_stores
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from shared import cache  # noqa: E402

DATASET_ID = "9a8c-vfzj"
ENDPOINT = f"https://data.ny.gov/resource/{DATASET_ID}.geojson"

NYC_COUNTIES = ["NEW YORK", "KINGS", "QUEENS", "BRONX", "RICHMOND"]

# First-pass "full-service grocery / supermarket" cut-off. Between a
# bodega and the NYC FRESH program's ~10k sq ft benchmark. Recorded in
# the chapter MethodologyFooter; revisit if it over/under-counts.
SUPERMARKET_MIN_SQFT = 5000.0


def build_query(snapshot: str = "2026-06-01") -> dict:
    del snapshot  # snapshot pinning is implicit in the cache key
    counties = ", ".join(f"'{c}'" for c in NYC_COUNTIES)
    return {
        "$select": (
            "license_number, operation_type, estab_type, entity_name, "
            "dba_name, county, city, zip_code, square_footage, georeference"
        ),
        "$where": f"county in ({counties})",
        "$limit": "50000",
    }


def fetch(*, snapshot: str = "2026-06-01") -> Path:
    """Fetch the NYC slice of NYS Retail Food Stores; return cached path."""
    import requests

    cache_name = f"nys_food_stores/nyc-{snapshot}.geojson"
    path = cache.path_for(cache_name)
    if cache.is_cached(cache_name):
        print(f"[cache hit] {cache_name}")
        return path

    params = build_query(snapshot=snapshot)
    print(f"[fetch] NYS Retail Food Stores (NYC)  snapshot={snapshot}")
    r = requests.get(ENDPOINT, params=params, timeout=300)
    r.raise_for_status()
    payload = r.json()
    path.write_text(json.dumps(payload))
    cache.record(cache_name, r.url)
    n = len(payload.get("features", []))
    print(f"  -> {n} features  ({path.stat().st_size:,} bytes)")
    return path


def load(*, snapshot: str = "2026-06-01", min_sqft: float | None = None):
    """Return a GeoDataFrame of NYC food stores (EPSG:2263, feet).

    ``square_footage`` is coerced to numeric. If ``min_sqft`` is set,
    filter to stores at or above that footprint (full-service grocery
    proxy) and drop rows with missing footage. Rows without a point
    geometry are always dropped.
    """
    import geopandas as gpd
    import pandas as pd

    path = fetch(snapshot=snapshot)
    gdf = gpd.read_file(path)
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    gdf["square_footage"] = pd.to_numeric(gdf.get("square_footage"), errors="coerce")
    if min_sqft is not None:
        gdf = gdf[gdf["square_footage"] >= min_sqft].copy()
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
