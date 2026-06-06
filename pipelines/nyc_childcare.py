"""NYC childcare capacity — two disjoint regulators, combined.

Chapter 4's *sufficiency* axis needs childcare **slots**, not facility
points. NYC childcare is split across two regulators and two datasets,
which is why a single source always undercounts:

  - **DOHMH** (NYC Health Code) regulates center-based care — the
    Article 47 day-care centers. Dataset ``gy3q-4tzp`` ("Active NYC
    Health Code Regulated Child Care Programs"): ~2,700 centers, all
    under-5 (PRESCHOOL + INFANT TODDLER), with a numeric ``capacity``.
    This is the bulk of formal under-5 slots in the city.
  - **OCFS** (NYS) regulates everything else — family & group family
    day care (home-based) and school-age care. Dataset ``cb42-qumz``.
    Critically, OCFS carries **zero** day-care *centers* (DCC) in the
    five boroughs (count = 0) because those are DOHMH's. So OCFS
    contributes the home-based slots (FDC + GFDC) only.

We deliberately take **center capacity from DOHMH** and **home-based
capacity from OCFS** — the two sets are disjoint, so summing them does
not double-count. We exclude OCFS SACC (school-age) from the under-5
slot count. The OCFS age-breakdown columns are unusable in NYC (~1,468
slots populated citywide), so home-based capacity is ``total_capacity``
with a noted school-age caveat.

Both loaders return point GeoDataFrames (EPSG:2263) with a numeric
``slots`` column; the chapter sjoins them to CDs. Vintage pin 2026-06-01.

Usage::

    python -m pipelines.nyc_childcare --source dohmh --dry-run
    python -m pipelines.nyc_childcare --source ocfs
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from shared import cache  # noqa: E402

DOHMH_ID = "gy3q-4tzp"
DOHMH_ENDPOINT = f"https://data.cityofnewyork.us/resource/{DOHMH_ID}.json"

OCFS_ID = "cb42-qumz"
OCFS_ENDPOINT = f"https://data.ny.gov/resource/{OCFS_ID}.json"
OCFS_NYC_BOROUGHS = ["Bronx", "Brooklyn", "Queens", "Manhattan", "Staten Island"]
OCFS_ACTIVE = ["License", "Registration"]
OCFS_HOME_BASED = ["FDC", "GFDC"]  # family + group family day care; excludes SACC


def _dohmh_query() -> dict:
    return {
        "$select": "dcid, program_name, program_type, age_range, capacity, "
                   "borough, latitude, longitude",
        "$limit": "20000",
    }


def _ocfs_query() -> dict:
    boros = ", ".join(f"'{b}'" for b in OCFS_NYC_BOROUGHS)
    statuses = ", ".join(f"'{s}'" for s in OCFS_ACTIVE)
    types = ", ".join(f"'{t}'" for t in OCFS_HOME_BASED)
    return {
        "$select": "facility_id, program_type, facility_status, county, "
                   "total_capacity, latitude, longitude",
        "$where": (f"county in ({boros}) AND facility_status in ({statuses}) "
                   f"AND program_type in ({types})"),
        "$limit": "20000",
    }


def fetch(source: str, *, snapshot: str = "2026-06-01") -> Path:
    """Fetch one childcare source (``dohmh`` or ``ocfs``); return cached path."""
    import requests

    if source == "dohmh":
        endpoint, params = DOHMH_ENDPOINT, _dohmh_query()
    elif source == "ocfs":
        endpoint, params = OCFS_ENDPOINT, _ocfs_query()
    else:
        raise ValueError(f"unknown source {source!r}; expected dohmh|ocfs")

    cache_name = f"nyc_childcare/{source}-{snapshot}.json"
    path = cache.path_for(cache_name)
    if cache.is_cached(cache_name):
        print(f"[cache hit] {cache_name}")
        return path

    print(f"[fetch] childcare {source}  snapshot={snapshot}")
    r = requests.get(endpoint, params=params, timeout=300)
    r.raise_for_status()
    payload = r.json()
    path.write_text(json.dumps(payload))
    cache.record(cache_name, r.url)
    print(f"  -> {len(payload)} rows  ({path.stat().st_size:,} bytes)")
    return path


def _to_points(df, slots_col: str):
    """Build a points GeoDataFrame (EPSG:2263) with a numeric ``slots`` column."""
    import geopandas as gpd
    import pandas as pd

    df = df.copy()
    df["latitude"] = pd.to_numeric(df.get("latitude"), errors="coerce")
    df["longitude"] = pd.to_numeric(df.get("longitude"), errors="coerce")
    df["slots"] = pd.to_numeric(df.get(slots_col), errors="coerce")
    df = df.dropna(subset=["latitude", "longitude"]).copy()
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["longitude"], df["latitude"]),
        crs="EPSG:4326",
    )
    return gdf.to_crs(epsg=2263)


def load(source: str, *, snapshot: str = "2026-06-01"):
    """Return a points GeoDataFrame (EPSG:2263) with a ``slots`` column."""
    import pandas as pd

    path = fetch(source, snapshot=snapshot)
    df = pd.DataFrame(json.loads(path.read_text()))
    slots_col = "capacity" if source == "dohmh" else "total_capacity"
    return _to_points(df, slots_col)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", required=True, choices=["dohmh", "ocfs"])
    ap.add_argument("--snapshot", default="2026-06-01")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if args.dry_run:
        endpoint = DOHMH_ENDPOINT if args.source == "dohmh" else OCFS_ENDPOINT
        params = _dohmh_query() if args.source == "dohmh" else _ocfs_query()
        print(f"[dry-run] GET {endpoint}")
        for k, v in params.items():
            print(f"  {k} = {v}")
        return 0
    fetch(args.source, snapshot=args.snapshot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
