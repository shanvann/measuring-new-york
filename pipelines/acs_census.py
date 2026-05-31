"""ACS 5-year tables (Census Bureau).

Pinned vintage: 2019-2023 5-year release. Uses the Census API directly so
we don't need ``cenpy`` (which requires Python ≥3.10). Wrap rather than
re-export the raw Census API.

NYC FIPS reference: state=36; counties Bronx=005, Kings=047, NY=061,
Queens=081, Richmond=085.

Set ``CENSUS_API_KEY`` in the environment before any real fetch
(https://api.census.gov/data/key_signup.html).

Usage::

    python -m pipelines.acs_census --table B25070 --geo cd --dry-run
    python -m pipelines.acs_census --table B25070 --geo tract
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from shared import cache  # noqa: E402

YEAR = 2023  # end year of the 2019-2023 5-year release
DATASET = "acs/acs5"

NYC_COUNTIES = {
    "Bronx": "005",
    "Kings": "047",      # Brooklyn
    "NewYork": "061",    # Manhattan
    "Queens": "081",
    "Richmond": "085",   # Staten Island
}

# Headline tables we know we'll want across chapters. Extend over time.
TABLES = {
    "B01003": "Total Population",
    "B25070": "Gross Rent as % of Household Income (rent burden)",
    "B25064": "Median Gross Rent",
    "B19013": "Median Household Income",
    "B08303": "Travel Time to Work",
    "B08301": "Means of Transportation to Work",
}

GeoLevel = Literal["tract", "borough", "cd"]


def build_url(table: str, geo: GeoLevel) -> tuple[str, dict]:
    """Build the Census API URL + params (no key — added at fetch time)."""
    if geo == "tract":
        for_clause = "tract:*"
        in_clause = "state:36 county:" + ",".join(NYC_COUNTIES.values())
    elif geo == "borough":
        for_clause = "county:" + ",".join(NYC_COUNTIES.values())
        in_clause = "state:36"
    elif geo == "cd":
        # CDs aren't a Census geography. The pipeline returns PUMA-level data
        # which a downstream notebook crosswalks to CDs (PUMA <-> CD mapping
        # lives in geographies/puma_cd_crosswalk.csv — to be added in Ch. 2).
        for_clause = "public use microdata area:*"
        in_clause = "state:36"
    else:
        raise ValueError(f"unknown geo: {geo}")

    url = f"https://api.census.gov/data/{YEAR}/{DATASET}"
    params = {
        "get": f"NAME,group({table})",
        "for": for_clause,
        "in": in_clause,
    }
    return url, params


def fetch(table: str, geo: GeoLevel, *, snapshot: str = "2026-06-01") -> Path:
    import requests

    cache_name = f"acs/{table}-{geo}-{YEAR}-{snapshot}.json"
    path = cache.path_for(cache_name)
    if cache.is_cached(cache_name):
        print(f"[cache hit] {cache_name}")
        return path

    url, params = build_url(table, geo)
    key = os.environ.get("CENSUS_API_KEY")
    if not key:
        raise RuntimeError(
            "CENSUS_API_KEY env var not set. Sign up at "
            "https://api.census.gov/data/key_signup.html"
        )
    params["key"] = key
    print(f"[fetch] ACS {table}  geo={geo}  year={YEAR}")
    r = requests.get(url, params=params, timeout=120)
    r.raise_for_status()
    data = r.json()
    path.write_text(json.dumps(data))
    # don't record the key in the manifest source_url
    cache.record(cache_name, f"{url}?{','.join(k+'='+v for k,v in params.items() if k != 'key')}")
    print(f"  -> {len(data) - 1} rows")
    return path


def load(table: str, geo: GeoLevel, *, snapshot: str = "2026-06-01"):
    import pandas as pd

    path = fetch(table, geo, snapshot=snapshot)
    raw = json.loads(path.read_text())
    return pd.DataFrame(raw[1:], columns=raw[0])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--table", required=True, help="e.g. B25070")
    ap.add_argument("--geo", required=True, choices=["tract", "borough", "cd"])
    ap.add_argument("--snapshot", default="2026-06-01")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--list-tables", action="store_true")
    args = ap.parse_args(argv)

    if args.list_tables:
        for k, v in TABLES.items():
            print(f"{k}\t{v}")
        return 0

    url, params = build_url(args.table, args.geo)
    if args.dry_run:
        print(f"[dry-run] GET {url}")
        for k, v in params.items():
            print(f"  {k} = {v}")
        print("(would also append key=<CENSUS_API_KEY>)")
        return 0
    fetch(args.table, args.geo, snapshot=args.snapshot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
