"""NYC Street Centerline (CSCL) — street mileage by ZIP (Socrata inkn-q76z).

Chapter 6 (Safety), traffic cross-check. The traffic-violence axis is
normalized per resident for cross-axis comparability, but per-resident
overstates dense high-throughput cores (a Midtown crash toll is driven by
pedestrian *exposure*, not by residents). The standard Vision-Zero exposure
denominator is **centerline street-miles**. This module pulls total street
(``rw_type='1'``) ``segmentlength`` aggregated by ZIP — a tiny server-side
rollup, so we never download the 122k-segment geometry — which a notebook
then distributes to Community Districts via the area-weighted
``geographies/zip_cd_crosswalk.csv`` (the same crosswalk Ch. 2 used for the
ZIP-only eviction data).

The ZIP→CD area crosswalk is an approximation (ZIPs straddle CDs); it is
adequate for a *denominator cross-check*, not a headline metric. Citywide
total ≈ 5,878 street-miles (matches DCP's ~6,000-mile network).

Usage::

    python -m pipelines.nyc_street_centerline --dry-run
    python -m pipelines.nyc_street_centerline
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from shared import cache  # noqa: E402

DATASET_ID = "inkn-q76z"
ENDPOINT = f"https://data.cityofnewyork.us/resource/{DATASET_ID}.json"
SNAPSHOT = "2026-06-01"


def build_query() -> dict:
    return {
        "$select": "l_zip,sum(segmentlength) as ft",
        "$where": "rw_type='1' and l_zip IS NOT NULL",
        "$group": "l_zip",
        "$limit": "5000",
    }


def _cache_name() -> str:
    return f"nyc_street_centerline/street-miles-by-zip-{SNAPSHOT}.json"


def fetch() -> Path:
    """Fetch street centerline feet aggregated by ZIP."""
    import requests

    cache_name = _cache_name()
    path = cache.path_for(cache_name)
    if cache.is_cached(cache_name):
        print(f"[cache hit] {cache_name}")
        return path

    params = build_query()
    print(f"[fetch] CSCL street miles by ZIP  snapshot={SNAPSHOT}")
    r = requests.get(ENDPOINT, params=params, timeout=120)
    r.raise_for_status()
    rows = r.json()
    path.write_text(json.dumps(rows))
    cache.record(cache_name, r.url)
    print(f"  -> {len(rows)} ZIPs  ({path.stat().st_size:,} bytes)")
    return path


def load() -> "pd.Series":
    """Series keyed by ZIP (str), value = street centerline miles."""
    import pandas as pd

    path = fetch()
    rows = json.loads(path.read_text())
    df = pd.DataFrame(rows)
    df["miles"] = pd.to_numeric(df["ft"], errors="coerce") / 5280.0
    return df.set_index("l_zip")["miles"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if args.dry_run:
        print(f"[dry-run] GET {ENDPOINT}")
        for k, v in build_query().items():
            print(f"  {k} = {v}")
        return 0
    fetch()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
