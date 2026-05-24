"""Area-weighted MODZCTA → Community District crosswalk.

Some NYC ZIPs straddle multiple CDs (e.g. 10025 spans CDs 107 and 109;
11216 spans 308 and 309). A centroid-only join mis-allocates ~10% of
records in the affected ZIPs. This module produces an area-weighted
crosswalk: for each (modzcta, borocd) pair where the two polygons
overlap, it records ``area_weight = overlap_area / zip_total_area``
so a chapter notebook can distribute zip-level counts to CDs
proportionally.

Outputs::

    geographies/zip_cd_crosswalk.csv
      modzcta, borocd, overlap_sqft, zip_total_sqft, area_weight

The weights for a given zip sum to ≤ 1.0; the remainder corresponds
to area outside NYC's 59 CDs (e.g. waterways, JIAs like parks). That
slack is reported per-zip in the run summary so callers can see how
much of each zip's footprint is "outside CDs."

Caveat: this is **area** weighted, not **population** weighted.
Population-weighted would need block-group population to redistribute
within a zip; for housing filings (which originate at addresses
roughly proportional to housing units, not raw area), area-weighting
is the defensible-but-simple default. For ZIPs that span a CD and a
non-residential area (e.g. a park or industrial waterfront), area
weighting may slightly over-allocate to the non-residential CD;
flag in the chapter MethodologyFooter.

Usage::

    python -m shared.zip_to_cd --dry-run
    python -m shared.zip_to_cd
    python -m shared.zip_to_cd --force   # rebuild even if cached
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from shared import basemap  # noqa: E402

OUTPUT_PATH = REPO_ROOT / "geographies" / "zip_cd_crosswalk.csv"

# NYC's 59 real Community Districts. The DCP geometry file also contains
# 12 Joint Interest Areas (JIAs) — large parks, airports, cemeteries —
# coded with the same ``boro_cd`` format but using numbers outside each
# borough's CD range. The list of valid (borough_prefix, max_cd_num)
# pairs is the canonical filter.
BOROUGH_CD_RANGE = {
    "1": 12,  # Manhattan: 101..112
    "2": 12,  # Bronx:     201..212
    "3": 18,  # Brooklyn:  301..318
    "4": 14,  # Queens:    401..414
    "5": 3,   # SI:        501..503
}


def is_real_cd(borocd: str) -> bool:
    """True iff ``borocd`` is one of the 59 NYC Community Districts."""
    if len(borocd) != 3 or not borocd.isdigit():
        return False
    prefix, num = borocd[0], int(borocd[1:])
    max_num = BOROUGH_CD_RANGE.get(prefix)
    return max_num is not None and 1 <= num <= max_num


def build() -> "pd.DataFrame":
    """Build the (modzcta, borocd, area_weight) crosswalk in memory."""
    import pandas as pd

    cds = basemap.load("cd")          # EPSG:2263 (feet) per basemap.load default
    zips = basemap.load("modzcta")    # EPSG:2263

    # Restrict CDs to the 59 real ones.
    cds = cds[cds["boro_cd"].apply(is_real_cd)].copy()

    # Sanity: each side should be valid geometry. Buffer(0) cleans common
    # self-intersection / orientation oddities in city-published polygons.
    cds["geometry"] = cds["geometry"].buffer(0)
    zips["geometry"] = zips["geometry"].buffer(0)

    # Compute each zip's total area before overlay (in EPSG:2263 = sqft).
    zip_areas = zips.assign(zip_total_sqft=zips.geometry.area)[
        ["modzcta", "zip_total_sqft"]
    ]

    # Overlay = pairwise intersection of overlapping polygons.
    # Result: one row per (modzcta, boro_cd) overlap with its own geometry.
    overlay = zips[["modzcta", "geometry"]].overlay(
        cds[["boro_cd", "geometry"]], how="intersection"
    )
    overlay["overlap_sqft"] = overlay.geometry.area

    out = (
        overlay[["modzcta", "boro_cd", "overlap_sqft"]]
        .rename(columns={"boro_cd": "borocd"})
        .merge(zip_areas, on="modzcta", how="left")
    )
    out["area_weight"] = out["overlap_sqft"] / out["zip_total_sqft"]

    # Drop slivers from imprecise polygon edges (< 1% of zip area AND
    # < 50,000 sqft). Keeps the crosswalk small without losing real
    # multi-CD ZIPs.
    sliver = (out["area_weight"] < 0.01) & (out["overlap_sqft"] < 50_000)
    out = out[~sliver].copy()

    return out.sort_values(["modzcta", "area_weight"], ascending=[True, False]).reset_index(drop=True)


def summarize(df: "pd.DataFrame") -> None:
    """Print a quick QA summary."""
    import pandas as pd

    n_pairs = len(df)
    n_zips = df["modzcta"].nunique()
    n_cds = df["borocd"].nunique()
    coverage = df.groupby("modzcta")["area_weight"].sum()
    multi_cd = (df.groupby("modzcta").size() > 1).sum()
    print(f"  pairs:                  {n_pairs}")
    print(f"  unique ZIPs:            {n_zips} (NYC has ~178 MODZCTAs)")
    print(f"  unique CDs covered:     {n_cds} of 59")
    print(f"  ZIPs spanning 2+ CDs:   {multi_cd} ({multi_cd / n_zips:.0%})")
    print(f"  weight sum stats:")
    print(f"    min  = {coverage.min():.3f}")
    print(f"    p10  = {coverage.quantile(0.1):.3f}")
    print(f"    median = {coverage.median():.3f}")
    print(f"    mean = {coverage.mean():.3f}")
    print(f"    max  = {coverage.max():.3f}")
    leaky = coverage[coverage < 0.5]
    if len(leaky):
        print(f"  ZIPs <50% CD-covered (mostly water/JIA): {len(leaky)}")
        print(f"    e.g. {', '.join(leaky.head(5).index.tolist())}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="Build the crosswalk and print a summary; don't write the CSV.")
    ap.add_argument("--force", action="store_true",
                    help="Rebuild even if the CSV already exists.")
    args = ap.parse_args(argv)

    if OUTPUT_PATH.exists() and not args.force and not args.dry_run:
        print(f"[skip] {OUTPUT_PATH} already exists. Pass --force to rebuild.")
        return 0

    print("[build] zip→CD area-weighted crosswalk")
    df = build()
    summarize(df)

    if args.dry_run:
        print("[dry-run] not writing CSV.")
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"[wrote] {OUTPUT_PATH}  ({OUTPUT_PATH.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
