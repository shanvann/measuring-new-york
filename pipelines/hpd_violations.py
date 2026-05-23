"""HPD housing maintenance code violations (Socrata dataset wvxf-dwi5).

Reused by Chapter 2 (Housing). Volume is enormous historically; we filter
by inspection date window to keep payloads small.

Usage::

    python -m pipelines.hpd_violations --cd 301 --days 30 --dry-run
    python -m pipelines.hpd_violations --cd 301 --days 30
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from shared import cache  # noqa: E402

DATASET_ID = "wvxf-dwi5"
ENDPOINT = f"https://data.cityofnewyork.us/resource/{DATASET_ID}.json"

COLUMNS = [
    "violationid",
    "buildingid",
    "inspectiondate",
    "currentstatusdate",
    "currentstatus",
    "class",
    "boroid",
    "communityboard",
    "postcode",
    "latitude",
    "longitude",
]


def build_query(*, cd: str | None, days: int, snapshot: str = "2026-06-01") -> dict:
    where = [f"inspectiondate <= '{snapshot}T00:00:00.000'"]
    if days:
        end = datetime.fromisoformat(f"{snapshot}T00:00:00")
        start = end - timedelta(days=days)
        where.append(f"inspectiondate >= '{start.strftime('%Y-%m-%dT%H:%M:%S.000')}'")
    if cd:
        # HPD encodes CD as a single integer ('1'..'18'); borough lives separately.
        boro_to_id = {"1": "1", "2": "2", "3": "3", "4": "4", "5": "5"}
        where.append(f"boroid = '{boro_to_id[cd[0]]}'")
        where.append(f"communityboard = '{int(cd[-2:])}'")
    return {
        "$select": ", ".join(COLUMNS),
        "$where": " AND ".join(where),
        "$limit": "50000",
        "$order": "inspectiondate DESC",
    }


def fetch(*, cd: str | None = None, days: int = 30, snapshot: str = "2026-06-01") -> Path:
    import requests

    params = build_query(cd=cd, days=days, snapshot=snapshot)
    cache_name = f"hpd_violations/cd-{cd or 'all'}-{snapshot}-last{days}d.json"
    path = cache.path_for(cache_name)
    if cache.is_cached(cache_name):
        print(f"[cache hit] {cache_name}")
        return path
    print(f"[fetch] HPD violations  cd={cd}  days={days}")
    r = requests.get(ENDPOINT, params=params, timeout=120)
    r.raise_for_status()
    rows = r.json()
    path.write_text(json.dumps(rows))
    cache.record(cache_name, r.url)
    print(f"  -> {len(rows)} rows")
    return path


def load(*, cd: str | None = None, days: int = 30, snapshot: str = "2026-06-01"):
    import pandas as pd

    return pd.read_json(fetch(cd=cd, days=days, snapshot=snapshot))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cd", help="BoroCD like '301'")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--snapshot", default="2026-06-01")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    params = build_query(cd=args.cd, days=args.days, snapshot=args.snapshot)
    if args.dry_run:
        print(f"[dry-run] GET {ENDPOINT}")
        for k, v in params.items():
            print(f"  {k} = {v}")
        return 0
    fetch(cd=args.cd, days=args.days, snapshot=args.snapshot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
