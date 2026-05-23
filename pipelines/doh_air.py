"""NYC DOHMH air quality (PM2.5, NO2, ozone) from the EH Data Portal.

Reused by Chapter 3 (Environmental Quality) and Chapter 8 (Time & Stress).
The portal exposes a Socrata-style dataset for annual neighborhood-level
PM2.5 (dataset id ``c3uy-2p5r``: Air Quality).

Usage::

    python -m pipelines.doh_air --pollutant PM2.5 --dry-run
    python -m pipelines.doh_air --pollutant PM2.5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from shared import cache  # noqa: E402

DATASET_ID = "c3uy-2p5r"
ENDPOINT = f"https://data.cityofnewyork.us/resource/{DATASET_ID}.json"


def build_query(*, pollutant: str = "Fine particles (PM 2.5)", snapshot: str = "2026-06-01") -> dict:
    return {
        "$select": "indicator_id, name, measure, measure_info, geo_type_name, geo_join_id, geo_place_name, time_period, start_date, data_value",
        "$where": f"name = '{pollutant}' AND start_date <= '{snapshot}T00:00:00.000'",
        "$limit": "50000",
        "$order": "start_date DESC, geo_place_name",
    }


def fetch(*, pollutant: str = "Fine particles (PM 2.5)", snapshot: str = "2026-06-01") -> Path:
    import requests

    params = build_query(pollutant=pollutant, snapshot=snapshot)
    slug = pollutant.split()[0].lower().replace("(", "").replace(")", "")
    cache_name = f"doh_air/{slug}-{snapshot}.json"
    path = cache.path_for(cache_name)
    if cache.is_cached(cache_name):
        print(f"[cache hit] {cache_name}")
        return path
    print(f"[fetch] DOHMH air  pollutant={pollutant}  snapshot={snapshot}")
    r = requests.get(ENDPOINT, params=params, timeout=120)
    r.raise_for_status()
    rows = r.json()
    path.write_text(json.dumps(rows))
    cache.record(cache_name, r.url)
    print(f"  -> {len(rows)} rows")
    return path


def load(*, pollutant: str = "Fine particles (PM 2.5)", snapshot: str = "2026-06-01"):
    import pandas as pd

    return pd.read_json(fetch(pollutant=pollutant, snapshot=snapshot))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pollutant", default="Fine particles (PM 2.5)")
    ap.add_argument("--snapshot", default="2026-06-01")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    params = build_query(pollutant=args.pollutant, snapshot=args.snapshot)
    if args.dry_run:
        print(f"[dry-run] GET {ENDPOINT}")
        for k, v in params.items():
            print(f"  {k} = {v}")
        return 0
    fetch(pollutant=args.pollutant, snapshot=args.snapshot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
