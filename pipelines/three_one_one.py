"""NYC 311 service requests (Socrata dataset erm2-nwe9).

Reused by Chapters 0, 5, 6, 8. Volume is huge — never fetch the whole
corpus; always filter by date window + a small column projection.

Usage::

    python -m pipelines.three_one_one --cd 301 --days 7
    python -m pipelines.three_one_one --cd 301 --days 1 --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from shared import cache  # noqa: E402

DATASET_ID = "erm2-nwe9"
DOMAIN = "data.cityofnewyork.us"
ENDPOINT = f"https://{DOMAIN}/resource/{DATASET_ID}.json"

# Project to the columns we actually use across chapters.
COLUMNS = [
    "unique_key",
    "created_date",
    "closed_date",
    "complaint_type",
    "descriptor",
    "agency",
    "status",
    "community_board",
    "borough",
    "latitude",
    "longitude",
]


def _vintage_clause(snapshot: str = "2026-06-01") -> str:
    return f"created_date <= '{snapshot}T00:00:00.000'"


def build_query(*, cd: str | None, days: int, snapshot: str = "2026-06-01") -> dict:
    """Build the Socrata SoQL query (does not fire).

    Returns a dict suitable for ``requests.get(..., params=...)``.
    """
    where = [_vintage_clause(snapshot)]
    if days:
        end = datetime.fromisoformat(f"{snapshot}T00:00:00+00:00")
        start = end - timedelta(days=days)
        where.append(f"created_date >= '{start.strftime('%Y-%m-%dT%H:%M:%S.000')}'")
    if cd:
        # 311 stores CDs as e.g. "01 BROOKLYN". Match by suffix on the formatted code.
        boro_to_name = {"1": "MANHATTAN", "2": "BRONX", "3": "BROOKLYN", "4": "QUEENS", "5": "STATEN ISLAND"}
        cd_num = int(cd[-2:])
        boro_name = boro_to_name[cd[0]]
        where.append(f"community_board = '{cd_num:02d} {boro_name}'")
    return {
        "$select": ", ".join(COLUMNS),
        "$where": " AND ".join(where),
        "$limit": "50000",
        "$order": "created_date DESC",
    }


def fetch(*, cd: str | None = None, days: int = 7, snapshot: str = "2026-06-01") -> Path:
    """Fetch 311 records into the cache and return the cached path."""
    import requests

    params = build_query(cd=cd, days=days, snapshot=snapshot)
    cache_name = f"three_one_one/cd-{cd or 'all'}-{snapshot}-last{days}d.json"
    path = cache.path_for(cache_name)
    if cache.is_cached(cache_name):
        print(f"[cache hit] {cache_name}")
        return path
    print(f"[fetch] 311  cd={cd}  days={days}  snapshot={snapshot}")
    r = requests.get(ENDPOINT, params=params, timeout=120)
    r.raise_for_status()
    rows = r.json()
    path.write_text(json.dumps(rows))
    cache.record(cache_name, r.url)
    print(f"  -> {len(rows)} rows  ({path.stat().st_size} bytes)")
    return path


def load(*, cd: str | None = None, days: int = 7, snapshot: str = "2026-06-01"):
    import pandas as pd

    path = fetch(cd=cd, days=days, snapshot=snapshot)
    return pd.read_json(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cd", help="BoroCD like '301' (Brooklyn CD 1)")
    ap.add_argument("--days", type=int, default=7)
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
