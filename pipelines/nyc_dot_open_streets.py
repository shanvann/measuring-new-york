"""NYC DOT Open Streets Locations (Socrata dataset uiay-nctu).

Used by Chapter 5 (Public Space & Urban Experience) for the pedestrian-realm
axis (pedestrianization = Open Streets + DOT plazas). The Open Streets
program closes or limits vehicle traffic on selected street segments to
give them back to pedestrians; this is the authoritative mapped layer.

Dataset id confirmed via the Socrata catalog API (do NOT guess): the DOT
"Open Streets Locations" dataset is ``uiay-nctu`` (the sibling ``6vys-sfk5``
is the map view, ``uiay-nctu`` is the tabular/data resource). 379 records
at the 2026-06-01 snapshot.

Each record is a ``MultiLineString`` street-segment geometry carrying
``orgname`` (the partner running the Open Street), ``boroughname``,
``appronstre``/``apprfromst``/``apprtostre`` (on/from/to street),
``reviewstat`` (closure type — "Full Closure", "Full Closure: Schools",
"Limited Local Access"), per-day open/close hours, and approval dates.
All three closure types are part of the active program, so we keep them
all as pedestrianized segments (the chapter treats Open Streets as a
*stock* of pedestrianized locations at the snapshot, per PLAN).

Small layer (~379 segments) so we pull the whole thing in one shot.

Vintage pin: 2026-06-01. Snapshot pinning is implicit in the cache key +
manifest entry.

Usage::

    python -m pipelines.nyc_dot_open_streets --dry-run
    python -m pipelines.nyc_dot_open_streets
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from shared import cache  # noqa: E402

DATASET_ID = "uiay-nctu"
ENDPOINT = f"https://data.cityofnewyork.us/resource/{DATASET_ID}.geojson"


def build_query(snapshot: str = "2026-06-01") -> dict:
    del snapshot  # snapshot pinning is implicit in the cache key
    return {
        "$select": (
            "orgname, boroughname, appronstre, apprfromst, apprtostre, "
            "reviewstat, apprstartd, apprenddat, segmentidf, segmentidt, "
            "the_geom"
        ),
        "$limit": "5000",
    }


def fetch(*, snapshot: str = "2026-06-01") -> Path:
    """Fetch the full Open Streets Locations GeoJSON; return the cached path."""
    import requests

    cache_name = f"nyc_dot_open_streets/open_streets-{snapshot}.geojson"
    path = cache.path_for(cache_name)
    if cache.is_cached(cache_name):
        print(f"[cache hit] {cache_name}")
        return path

    params = build_query(snapshot=snapshot)
    print(f"[fetch] NYC DOT Open Streets Locations  snapshot={snapshot}")
    r = requests.get(ENDPOINT, params=params, timeout=120)
    r.raise_for_status()
    payload = r.json()
    path.write_text(json.dumps(payload))
    cache.record(cache_name, r.url)
    n = len(payload.get("features", []))
    print(f"  -> {n} features  ({path.stat().st_size:,} bytes)")
    return path


def load(*, snapshot: str = "2026-06-01"):
    """Return a GeoDataFrame of Open Streets segments (EPSG:2263, feet)."""
    import geopandas as gpd

    path = fetch(snapshot=snapshot)
    gdf = gpd.read_file(path)
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
