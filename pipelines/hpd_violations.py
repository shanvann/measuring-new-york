"""HPD housing maintenance code violations (Socrata dataset wvxf-dwi5).

Reused by Chapter 2 (Housing). Volume is enormous historically; we filter
by inspection date window to keep payloads small.

Two fetch modes:

  ``fetch(cd=..., days=...)`` — single-CD, single-request fetch.
  Capped at the Socrata $limit of 50,000 rows; will silently truncate
  if a CD/window exceeds that. Originally used in Ch. 0 pilot.

  ``fetch_counts_by_zip(start_date, end_date)`` — server-side aggregated
  count per (zip, class) for a window across all of NYC. Single request,
  small response. Used in Ch. 2 to compute per-CD violations density
  (apply the zip→CD crosswalk in the notebook).

Usage::

    python -m pipelines.hpd_violations --cd 301 --days 30 --dry-run
    python -m pipelines.hpd_violations --cd 301 --days 30
    python -m pipelines.hpd_violations --window 2024-01-01 2026-05-10
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

# Socrata caps a single response at 50,000 rows. Pagination uses
# $offset; new offset = old offset + actual returned count.
PAGE_SIZE = 50_000

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


def fetch_counts_by_zip(
    *,
    start_date: str,
    end_date: str,
    snapshot: str = "2026-06-01",
) -> Path:
    """Aggregated count of HPD violations per (zip, class) in a window.

    Uses Socrata ``GROUP BY zip, class`` so the response is small
    (≈ 200 ZIPs × 3 classes = ~600 rows) — one request, no pagination,
    no 2 M-row payload. Cached as JSON for reproducibility.

    HPD violation classes:
      A — non-hazardous (peeling paint, leaks, broken plaster)
      B — hazardous (rodent infestation, mold, no heat <3 days)
      C — immediately hazardous (lead, no heat ≥3 days, fire risk)
    """
    import requests

    cache_name = (
        f"hpd_violations/counts-by-zip-{start_date}_{end_date}-{snapshot}.json"
    )
    path = cache.path_for(cache_name)
    if cache.is_cached(cache_name):
        print(f"[cache hit] {cache_name}")
        return path

    where = (
        f"inspectiondate >= '{start_date}T00:00:00.000' AND "
        f"inspectiondate <= '{end_date}T23:59:59.999' AND "
        f"inspectiondate <= '{snapshot}T00:00:00.000'"
    )
    params = {
        "$select": "zip, class, count(*) AS n",
        "$where": where,
        "$group": "zip, class",
        "$limit": "10000",
    }
    print(f"[fetch] HPD counts-by-zip  window {start_date}..{end_date}")
    r = requests.get(ENDPOINT, params=params, timeout=300)
    r.raise_for_status()
    rows = r.json()
    path.write_text(json.dumps(rows))
    cache.record(cache_name, r.url)
    print(f"  -> {len(rows)} (zip, class) rows  ({path.stat().st_size:,} bytes)")
    return path


def load_counts_by_zip(*, start_date: str, end_date: str, snapshot: str = "2026-06-01"):
    """Return a pandas DataFrame with columns ``zip, class, n``."""
    import pandas as pd

    path = fetch_counts_by_zip(
        start_date=start_date, end_date=end_date, snapshot=snapshot
    )
    df = pd.read_json(path, dtype={"zip": str, "class": str, "n": "Int64"})
    return df


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cd", help="BoroCD like '301'")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--window", nargs=2, metavar=("START", "END"),
                    help="Full-NYC counts-by-zip fetch for the window (YYYY-MM-DD YYYY-MM-DD)")
    ap.add_argument("--snapshot", default="2026-06-01")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if args.window:
        if args.dry_run:
            print(f"[dry-run] counts-by-zip  {args.window[0]} .. {args.window[1]}")
            return 0
        fetch_counts_by_zip(
            start_date=args.window[0], end_date=args.window[1],
            snapshot=args.snapshot,
        )
        return 0

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
