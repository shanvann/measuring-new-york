"""NYPD Complaint Data — the seven major felonies (Socrata dataset qgea-i56i).

Chapter 6 (Safety). NYPD's complaint-level record of every reported crime,
one row per complaint with an offense category (``ky_cd`` / ``ofns_desc``),
a legal severity (``law_cat_cd``), and State-Plane coordinates
(``x_coord_cd`` / ``y_coord_cd``, EPSG:2263 — the repo's analysis CRS, so no
reprojection is needed). Precinct is given but Community District is not, so
CDs are assigned by point-in-polygon downstream.

We keep only the **seven major felonies** — NYPD's own headline index — and
split them into the chapter's two crime axes:

  VIOLENT  (person-directed)   ky_cd 101 murder, 104 rape, 105 robbery,
                               106 felony assault
  PROPERTY (opportunity-driven) ky_cd 107 burglary, 109 grand larceny,
                               110 grand larceny of a motor vehicle

Window: a fixed 3-year span (default 2022-01-01 .. 2024-12-31) so per-CD
rates are stable, not single-year noise. Rows without coordinates are
dropped (they can't be assigned to a CD); the dropped share is reported.

Usage::

    python -m pipelines.nypd_complaints --dry-run
    python -m pipelines.nypd_complaints            # fetch + cache
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from shared import cache  # noqa: E402

DATASET_ID = "qgea-i56i"
ENDPOINT = f"https://data.cityofnewyork.us/resource/{DATASET_ID}.json"

# Seven major felonies, split into the two chapter axes.
VIOLENT_KY = {"101": "murder", "104": "rape", "105": "robbery",
              "106": "felony assault"}
PROPERTY_KY = {"107": "burglary", "109": "grand larceny",
               "110": "grand larceny motor vehicle"}
MAJOR_KY = {**VIOLENT_KY, **PROPERTY_KY}

WINDOW_START = "2022-01-01"
WINDOW_END = "2024-12-31"
PAGE = 50000


def _where(start: str, end: str) -> str:
    ky_list = ",".join(f"'{k}'" for k in MAJOR_KY)
    return (
        f"cmplnt_fr_dt between '{start}T00:00:00' and '{end}T23:59:59' "
        f"and law_cat_cd='FELONY' and ky_cd in ({ky_list}) "
        f"and x_coord_cd IS NOT NULL"
    )


def build_query(start: str, end: str, offset: int = 0) -> dict:
    return {
        "$select": "cmplnt_num,ky_cd,x_coord_cd,y_coord_cd",
        "$where": _where(start, end),
        "$order": "cmplnt_num",
        "$limit": str(PAGE),
        "$offset": str(offset),
    }


def _cache_name(start: str, end: str) -> str:
    return f"nypd_complaints/major-felonies-{start}_{end}.json"


def fetch(start: str = WINDOW_START, end: str = WINDOW_END) -> Path:
    """Fetch all seven-major-felony complaints in the window (paginated)."""
    import requests

    cache_name = _cache_name(start, end)
    path = cache.path_for(cache_name)
    if cache.is_cached(cache_name):
        print(f"[cache hit] {cache_name}")
        return path

    rows: list[dict] = []
    offset = 0
    while True:
        params = build_query(start, end, offset)
        print(f"[fetch] complaints  offset={offset:,}")
        r = requests.get(ENDPOINT, params=params, timeout=300)
        r.raise_for_status()
        page = r.json()
        rows.extend(page)
        if len(page) < PAGE:
            break
        offset += PAGE
    path.write_text(json.dumps(rows))
    cache.record(cache_name, f"{ENDPOINT}?$where={_where(start, end)}")
    print(f"  -> {len(rows):,} complaints  ({path.stat().st_size:,} bytes)")
    return path


def load(start: str = WINDOW_START, end: str = WINDOW_END):
    """GeoDataFrame of major-felony complaints (EPSG:2263) with an ``axis``
    column ('violent' | 'property') and an ``offense`` label."""
    import geopandas as gpd
    import pandas as pd

    path = fetch(start, end)
    df = pd.DataFrame(json.loads(path.read_text()))
    df["x_coord_cd"] = pd.to_numeric(df["x_coord_cd"], errors="coerce")
    df["y_coord_cd"] = pd.to_numeric(df["y_coord_cd"], errors="coerce")
    df = df.dropna(subset=["x_coord_cd", "y_coord_cd"]).copy()
    df["axis"] = df["ky_cd"].map(
        lambda k: "violent" if k in VIOLENT_KY else "property"
    )
    df["offense"] = df["ky_cd"].map(MAJOR_KY)
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["x_coord_cd"], df["y_coord_cd"]),
        crs="EPSG:2263",
    )
    return gdf


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default=WINDOW_START)
    ap.add_argument("--end", default=WINDOW_END)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if args.dry_run:
        print(f"[dry-run] GET {ENDPOINT}")
        for k, v in build_query(args.start, args.end).items():
            print(f"  {k} = {v}")
        return 0
    fetch(args.start, args.end)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
