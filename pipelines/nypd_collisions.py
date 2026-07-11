"""NYPD Motor Vehicle Collisions — Crashes (Socrata dataset h9gi-nx95).

Chapter 6 (Safety). One row per reported crash, with per-crash casualty
counts (``number_of_pedestrians_injured`` / ``_killed`` and the cyclist
equivalents) and a ``latitude`` / ``longitude`` point. We keep only crashes
that hurt a **pedestrian or cyclist** — the road users the chapter's
traffic-violence axis is about — within a fixed window (default 2022-2024).

Metric note: neither the Crashes table nor the companion Person table
(f55k-p6yu) exposes an injury *severity* grade in the public export, so a
strict Vision-Zero "KSI" (killed or **severe** injury) cut is not possible
here. The axis is therefore **pedestrian + cyclist casualties = killed OR
injured (KI)**; fatalities are also carried separately so a killed-weighted
sensitivity check is available. This limitation is disclosed in the chapter
methodology.

Crashes are point-located; Community District is assigned by point-in-polygon
downstream. Rows without coordinates are dropped (they can't be placed).

Usage::

    python -m pipelines.nypd_collisions --dry-run
    python -m pipelines.nypd_collisions            # fetch + cache
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from shared import cache  # noqa: E402

DATASET_ID = "h9gi-nx95"
ENDPOINT = f"https://data.cityofnewyork.us/resource/{DATASET_ID}.json"

CASUALTY_COLS = [
    "number_of_pedestrians_injured", "number_of_pedestrians_killed",
    "number_of_cyclist_injured", "number_of_cyclist_killed",
]

WINDOW_START = "2022-01-01"
WINDOW_END = "2024-12-31"
PAGE = 50000


def _where(start: str, end: str) -> str:
    return (
        f"crash_date between '{start}T00:00:00' and '{end}T23:59:59' "
        f"and latitude IS NOT NULL "
        f"and (number_of_pedestrians_injured>0 or number_of_pedestrians_killed>0 "
        f"or number_of_cyclist_injured>0 or number_of_cyclist_killed>0)"
    )


def build_query(start: str, end: str, offset: int = 0) -> dict:
    return {
        "$select": "collision_id,latitude,longitude," + ",".join(CASUALTY_COLS),
        "$where": _where(start, end),
        "$order": "collision_id",
        "$limit": str(PAGE),
        "$offset": str(offset),
    }


def _cache_name(start: str, end: str) -> str:
    return f"nypd_collisions/ped-cyc-casualties-{start}_{end}.json"


def fetch(start: str = WINDOW_START, end: str = WINDOW_END) -> Path:
    """Fetch all ped/cyclist-casualty crashes in the window (paginated)."""
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
        print(f"[fetch] collisions  offset={offset:,}")
        r = requests.get(ENDPOINT, params=params, timeout=300)
        r.raise_for_status()
        page = r.json()
        rows.extend(page)
        if len(page) < PAGE:
            break
        offset += PAGE
    path.write_text(json.dumps(rows))
    cache.record(cache_name, f"{ENDPOINT}?$where={_where(start, end)}")
    print(f"  -> {len(rows):,} crashes  ({path.stat().st_size:,} bytes)")
    return path


def load(start: str = WINDOW_START, end: str = WINDOW_END):
    """GeoDataFrame of ped/cyclist-casualty crashes (EPSG:2263).

    Adds ``ped_cas`` / ``cyc_cas`` (killed+injured) and ``killed`` /
    ``casualties`` (ped+cyclist) integer columns per crash.
    """
    import geopandas as gpd
    import pandas as pd

    path = fetch(start, end)
    df = pd.DataFrame(json.loads(path.read_text()))
    for c in CASUALTY_COLS + ["latitude", "longitude"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["latitude", "longitude"]).copy()
    # drop the null-island (0,0) coordinates the dataset is known to carry
    df = df[(df["latitude"] != 0) & (df["longitude"] != 0)].copy()
    df["ped_cas"] = df["number_of_pedestrians_injured"] + df["number_of_pedestrians_killed"]
    df["cyc_cas"] = df["number_of_cyclist_injured"] + df["number_of_cyclist_killed"]
    df["killed"] = df["number_of_pedestrians_killed"] + df["number_of_cyclist_killed"]
    df["casualties"] = df["ped_cas"] + df["cyc_cas"]
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["longitude"], df["latitude"]),
        crs="EPSG:4326",
    )
    return gdf.to_crs(epsg=2263)


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
