"""NYC eviction filings — OCA Housing Court bulk data.

True filings (cases initiated in housing court), not marshal-executed
evictions. Distributed as deidentified CSV bundles on a public S3 bucket
by the Housing Data Coalition's OCA ETL pipeline (see
https://github.com/housing-data-coalition/oca). Same source the
Furman Center, Right to Counsel NYC, and the Cornell ILR eviction-
filings dashboard use.

Ch. 2 uses the ``oca_index`` table (case-level: court, filed date,
classification, status) joined to ``oca_addresses`` (zip-level
geography per case). There are 9 other tables in the bundle
(causes / parties / events / appearances / appearance_outcomes /
motions / decisions / judgments / warrants); none are needed for the
chapter's headline rate, so this module only handles the two we use.
Add more if a future chapter needs them.

Vintage note (plan §5.3): the series vintage freeze is 2026-06-01,
but the latest S3 publish at time of writing is 2026-05-10 (HDC ETL
runs ~monthly off an OCA SFTP feed). Ch. 2 uses the 2026-05-10
snapshot as a documented vintage exception — same handling Ch. 0
used for its 2026-05-01 snapshot. The actual snapshot date is
fetched from ``last-updated-date.txt`` and persisted in cache filenames
so the chapter's numbers stay reproducible.

Geography note: OCA addresses carry only ``city`` + ``state`` +
``postalcode``. There is no BBL/BIN. CD aggregation is done via a
zip→CD spatial crosswalk (see ``shared/zip_to_cd.py``, to be added in
the Ch. 2 notebook).

Usage::

    python -m pipelines.oca_evictions --snapshot-info
    python -m pipelines.oca_evictions --table index --dry-run
    python -m pipelines.oca_evictions --table index
    python -m pipelines.oca_evictions --table addresses
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterator, Literal

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from shared import cache  # noqa: E402

S3_BASE = "https://oca-2-dev.s3.amazonaws.com/public"
LAST_UPDATED_URL = f"{S3_BASE}/last-updated-date.txt"

TableName = Literal["index", "addresses"]

# Only the two we actually use. The full bundle has 11 CSVs (see module
# docstring). Adding a new table = one entry here + an optional
# columns-of-interest tuple.
TABLES: dict[TableName, str] = {
    "index": "oca_index.csv",
    "addresses": "oca_addresses.csv",
}

# Schema observed in the 2026-05-10 snapshot. Kept here so callers can
# pass usecols= without re-checking the file. If a future HDC release
# changes the schema, update here and bump the snapshot in the
# chapter notebook.
INDEX_COLUMNS = (
    "indexnumberid",
    "court",
    "fileddate",
    "propertytype",
    "classification",
    "specialtydesignationtypes",
    "status",
    "disposeddate",
    "disposedreason",
    "firstpaper",
    "primaryclaimtotal",
    "dateofjurydemand",
)

ADDRESSES_COLUMNS = (
    "indexnumberid",
    "city",
    "state",
    "postalcode",
)

# The 5 NYC housing courts in the ``court`` field. Use these to filter
# the (statewide) index down to NYC cases without depending on the
# noisy address table.
NYC_COURTS = (
    "Bronx County Civil Court",
    "Kings County Civil Court",        # Brooklyn
    "New York County Civil Court",     # Manhattan
    "Queens County Civil Court",
    "Richmond County Civil Court",     # Staten Island
)


def snapshot_date() -> str:
    """Fetch the current S3 publish date (``YYYY-MM-DD``)."""
    import requests

    r = requests.get(LAST_UPDATED_URL, timeout=30)
    r.raise_for_status()
    return r.text.strip()


def _cache_name(table: TableName, snapshot: str) -> str:
    return f"oca/{TABLES[table].replace('.csv', '')}-{snapshot}.csv"


def fetch(table: TableName, *, snapshot: str | None = None) -> Path:
    """Download ``table`` once into the cache; return the cached path.

    If ``snapshot`` is None, the S3 ``last-updated-date.txt`` is consulted
    so the cache filename pins the actual data vintage.
    """
    import requests

    snap = snapshot or snapshot_date()
    name = _cache_name(table, snap)
    path = cache.path_for(name)
    if cache.is_cached(name):
        print(f"[cache hit] {name}")
        return path

    url = f"{S3_BASE}/{TABLES[table]}"
    print(f"[fetch] OCA {table}  snapshot={snap}  url={url}")
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        written = 0
        with path.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                if not chunk:
                    continue
                f.write(chunk)
                written += len(chunk)
                if total:
                    pct = 100 * written / total
                    print(f"  ... {written/1e6:.1f} / {total/1e6:.1f} MB  ({pct:.0f}%)", end="\r")
        print()
    cache.record(name, url)
    print(f"  -> {path.stat().st_size:,} bytes")
    return path


def iter_chunks(
    table: TableName,
    *,
    snapshot: str | None = None,
    chunksize: int = 250_000,
    usecols: tuple[str, ...] | None = None,
):
    """Yield pandas DataFrames over the cached CSV in chunks.

    The index table is ~500 MB; loading the whole thing into memory
    is wasteful for any single chapter. Filter inside the loop.
    """
    import pandas as pd

    path = fetch(table, snapshot=snapshot)
    cols = list(usecols) if usecols else None
    yield from pd.read_csv(
        path,
        chunksize=chunksize,
        usecols=cols,
        dtype=str,
        low_memory=True,
    )


def load_nyc_filings(
    *,
    snapshot: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    classifications: tuple[str, ...] | None = ("Non-Payment", "Holdover"),
    property_types: tuple[str, ...] | None = ("Residential",),
):
    """Load NYC filings joined to zip-level addresses, filtered to a window.

    Returns a single ``pd.DataFrame`` with columns:
    ``indexnumberid, court, fileddate, classification, propertytype,
    status, disposeddate, primaryclaimtotal, postalcode, city, state``.

    Filters applied:
      - ``court in NYC_COURTS`` — the canonical NYC filter
      - ``fileddate`` within ``[start_date, end_date]`` if given
      - ``classification`` restricted to non-payment + holdover by default
        (the two cases that map to "displacement filing"; small claims
        and other categories are noise for this chapter)
      - ``propertytype == 'Residential'`` by default

    The address join is an inner join on ``indexnumberid``; rows in the
    index without an address are dropped (they can't be geocoded anyway).
    """
    import pandas as pd

    snap = snapshot or snapshot_date()

    keep = []
    for chunk in iter_chunks("index", snapshot=snap, usecols=INDEX_COLUMNS):
        m = chunk["court"].isin(NYC_COURTS)
        if classifications:
            m &= chunk["classification"].isin(classifications)
        if property_types:
            m &= chunk["propertytype"].isin(property_types)
        if start_date:
            m &= chunk["fileddate"] >= start_date
        if end_date:
            m &= chunk["fileddate"] <= end_date
        keep.append(chunk[m])
    idx = pd.concat(keep, ignore_index=True)
    print(f"[load] NYC index rows after filter: {len(idx):,}")

    addr_path = fetch("addresses", snapshot=snap)
    addr = pd.read_csv(addr_path, usecols=ADDRESSES_COLUMNS, dtype=str)
    joined = idx.merge(addr, on="indexnumberid", how="inner")
    print(f"[load] joined to addresses: {len(joined):,}  (dropped {len(idx) - len(joined):,} without address)")
    return joined


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--table", choices=list(TABLES.keys()), help="Which CSV to fetch")
    ap.add_argument("--snapshot", help="Override S3 last-updated-date (YYYY-MM-DD)")
    ap.add_argument("--snapshot-info", action="store_true",
                    help="Print the current S3 publish date and exit")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if args.snapshot_info:
        print(snapshot_date())
        return 0

    if not args.table:
        ap.error("--table required (unless --snapshot-info)")

    snap = args.snapshot or snapshot_date()
    if args.dry_run:
        print(f"[dry-run] GET {S3_BASE}/{TABLES[args.table]}")
        print(f"  cache key = {_cache_name(args.table, snap)}")
        return 0
    fetch(args.table, snapshot=snap)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
