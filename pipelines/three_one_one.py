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


# ---------- env-bucket counts-by-zip (Ch. 3) ----------

# Each bucket is a SoQL WHERE fragment matched against `complaint_type`.
# Verified against the full 2024-01-01..2026-06-01 window (Bucket totals
# probe, 2026-05-30 worklog): noise 1.86M, dirty 239k, rodent 80k,
# idair 22k. ``idair`` deliberately couples with the ambient-air axis
# (idling -> NO2); the chapter spine test will flag it if rho >= 0.75.
ENV_BUCKETS = {
    "noise":  "complaint_type like 'Noise%'",
    "rodent": "complaint_type = 'Rodent'",
    "dirty":  "complaint_type in('Dirty Condition','Illegal Dumping','Sanitation Condition')",
    "idair":  "complaint_type in('Air Quality','Illegal Idling','Idling')",
}


def fetch_env_counts_by_zip(
    *,
    start_date: str,
    end_date: str,
    snapshot: str = "2026-06-01",
) -> Path:
    """Aggregated 311 env-complaint counts per (bucket, incident_zip) in a window.

    Issues one Socrata GROUP-BY-incident_zip request per bucket in
    ``ENV_BUCKETS`` and unions the results into a single cached JSON
    payload (``[{bucket, zip, n}, ...]``). The full-window aggregate
    for the chapter spec (2024-01-01..2026-06-01) completes in ~30-90s
    per bucket; the per-row Socrata cap doesn't bind because each
    aggregate returns ~200 zips × 1 bucket = ~200 rows.
    """
    import requests

    cache_name = (
        f"three_one_one/env-counts-by-zip-{start_date}_{end_date}-{snapshot}.json"
    )
    path = cache.path_for(cache_name)
    if cache.is_cached(cache_name):
        print(f"[cache hit] {cache_name}")
        return path

    window = (
        f"created_date >= '{start_date}T00:00:00.000' AND "
        f"created_date <= '{end_date}T23:59:59.999' AND "
        f"created_date <= '{snapshot}T00:00:00.000'"
    )
    all_rows: list[dict] = []
    for bucket, type_clause in ENV_BUCKETS.items():
        params = {
            "$select": "incident_zip, count(*) AS n",
            "$where": f"{window} AND ({type_clause})",
            "$group": "incident_zip",
            "$limit": "5000",
        }
        print(f"[fetch] 311 env counts-by-zip  bucket={bucket}  window {start_date}..{end_date}")
        r = requests.get(ENDPOINT, params=params, timeout=300)
        r.raise_for_status()
        rows = r.json()
        for row in rows:
            row["bucket"] = bucket
            row["zip"] = row.pop("incident_zip", "") or ""
        all_rows.extend(rows)
        print(f"  -> {len(rows)} zip rows for {bucket}")

    path.write_text(json.dumps(all_rows))
    # Each per-bucket query has its own URL; record the cache_name
    # against the dataset endpoint so MANIFEST is searchable by source.
    cache.record(cache_name, f"{ENDPOINT} (4 GROUP BY incident_zip aggregates)")
    print(f"  -> {path}  ({path.stat().st_size:,} bytes; {len(all_rows)} rows total)")
    return path


def load_env_counts_by_zip(*, start_date: str, end_date: str, snapshot: str = "2026-06-01"):
    """Return a DataFrame with columns ``bucket, zip, n``."""
    import pandas as pd

    path = fetch_env_counts_by_zip(
        start_date=start_date, end_date=end_date, snapshot=snapshot
    )
    return pd.read_json(path, dtype={"zip": str, "bucket": str, "n": "Int64"})


# ---------- distinct-address aggregate (Ch. 3, super-caller-robust) ----------
#
# Why a parallel aggregate instead of replacing the raw count: 311 noise
# data has a well-documented "super-caller" / chronic-address pattern
# (see Ch. 3 PLAN's CD 212 / zip 10466 finding — 1 address generates
# ~13% of zip 10466's noise volume, 97% of which is "Loud Music/Party").
# A volume-based rate (calls per 1k pop / yr) lets a single chronic
# address dominate an entire CD's score. Counting distinct addresses
# that generated >=1 complaint in the window measures *how widespread*
# the complaint behavior is, not how loudly a few addresses are
# calling. Both aggregates are retained: the count is preserved for
# reproducibility + per-bucket totals; the distinct-address aggregate
# is the chapter's primary "env-311 burden" metric.


def fetch_env_distinct_addrs_by_zip(
    *,
    start_date: str,
    end_date: str,
    snapshot: str = "2026-06-01",
) -> Path:
    """Aggregated distinct ``incident_address`` count per (bucket, incident_zip).

    Same windowing + bucket clauses as ``fetch_env_counts_by_zip`` but
    selects ``count(distinct incident_address)`` instead of ``count(*)``.
    One Socrata GROUP-BY-incident_zip request per bucket; cached as a
    single union JSON ``[{bucket, zip, addrs}, ...]``.
    """
    import requests

    cache_name = (
        f"three_one_one/env-distinct-addrs-by-zip-{start_date}_{end_date}-{snapshot}.json"
    )
    path = cache.path_for(cache_name)
    if cache.is_cached(cache_name):
        print(f"[cache hit] {cache_name}")
        return path

    window = (
        f"created_date >= '{start_date}T00:00:00.000' AND "
        f"created_date <= '{end_date}T23:59:59.999' AND "
        f"created_date <= '{snapshot}T00:00:00.000'"
    )
    all_rows: list[dict] = []
    for bucket, type_clause in ENV_BUCKETS.items():
        params = {
            "$select": "incident_zip, count(distinct incident_address) AS addrs",
            "$where": f"{window} AND ({type_clause}) AND incident_address IS NOT NULL",
            "$group": "incident_zip",
            "$limit": "5000",
        }
        print(f"[fetch] 311 env distinct-addrs-by-zip  bucket={bucket}  window {start_date}..{end_date}")
        r = requests.get(ENDPOINT, params=params, timeout=300)
        r.raise_for_status()
        rows = r.json()
        for row in rows:
            row["bucket"] = bucket
            row["zip"] = row.pop("incident_zip", "") or ""
        all_rows.extend(rows)
        print(f"  -> {len(rows)} zip rows for {bucket}")

    path.write_text(json.dumps(all_rows))
    cache.record(
        cache_name,
        f"{ENDPOINT} (4 GROUP BY incident_zip aggregates, count(distinct incident_address))",
    )
    print(f"  -> {path}  ({path.stat().st_size:,} bytes; {len(all_rows)} rows total)")
    return path


def load_env_distinct_addrs_by_zip(
    *, start_date: str, end_date: str, snapshot: str = "2026-06-01",
):
    """Return a DataFrame with columns ``bucket, zip, addrs``."""
    import pandas as pd

    path = fetch_env_distinct_addrs_by_zip(
        start_date=start_date, end_date=end_date, snapshot=snapshot
    )
    return pd.read_json(path, dtype={"zip": str, "bucket": str, "addrs": "Int64"})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cd", help="BoroCD like '301' (Brooklyn CD 1)")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--snapshot", default="2026-06-01")
    ap.add_argument("--env-window", nargs=2, metavar=("START", "END"),
                    help="Fetch env-bucket counts-by-zip for the window (YYYY-MM-DD YYYY-MM-DD)")
    ap.add_argument("--env-distinct-addrs", nargs=2, metavar=("START", "END"),
                    help="Fetch env-bucket distinct-address counts-by-zip for the window")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if args.env_window:
        if args.dry_run:
            print(f"[dry-run] env counts-by-zip  {args.env_window[0]} .. {args.env_window[1]}")
            for b, w in ENV_BUCKETS.items():
                print(f"  bucket {b}: {w}")
            return 0
        fetch_env_counts_by_zip(
            start_date=args.env_window[0], end_date=args.env_window[1],
            snapshot=args.snapshot,
        )
        return 0

    if args.env_distinct_addrs:
        if args.dry_run:
            print(f"[dry-run] env distinct-addrs-by-zip  "
                  f"{args.env_distinct_addrs[0]} .. {args.env_distinct_addrs[1]}")
            return 0
        fetch_env_distinct_addrs_by_zip(
            start_date=args.env_distinct_addrs[0],
            end_date=args.env_distinct_addrs[1],
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
