"""Chapter 3 — Environmental Quality (first-pass scaffold).

Goal of this first pass (mirrors Ch. 2): validate the chapter's spine
hypothesis BEFORE investing in any visual artifacts. The hypothesis is
that a New Yorker's environmental experience splits into **three
semi-independent axes**:

  1. Ambient air quality            (DOHMH PM2.5 + NO2, CD-level annual)
  2. Green-space access             (% residents within 10-min walk of
                                     a 1+ acre park — pop-weighted)
  3. Local nuisance burden          (env-related 311 complaints per 1k
                                     residents per year)

If any pair of axes co-ranks tightly (|rho| >= 0.75, matching Ch. 2's
kill criterion), the spine collapses and the chapter gets re-spec'd.
Ch. 2's kill criterion fired (filings <-> HPD at +0.82) and that
collapse is *why* it shipped as a 2-axis story. Same playbook here.

Run with::

    python analyses/chapter-03/notebook.py

Status (2026-05-30):
  axis 1 (air)         — wired end-to-end (DOHMH c3uy-2p5r, geo=CD)
  axis 2 (green-space) — TODO: NYC Parks Properties + Ch. 1 isochrones
  axis 3 (env-311)     — TODO: extend pipelines.three_one_one with a
                         counts-by-zip-and-complaint Socrata aggregate,
                         then allocate via the existing zip->CD crosswalk

Outputs (out/ inside this dir):
  facts.json    Per-CD: pm25_annual, no2_annual, (later) green-coverage,
                env_311_per_1k_pop_per_yr.
  rankings.csv  Long-form per-CD per-axis rankings (sortable for QA).

Datasets:
  DOHMH air     c3uy-2p5r (CD-level data already exposed: 2,655 CD rows
                across PM2.5 + NO2 at the pinned 2026-06-01 snapshot).
                We pick "Annual Average <latest year>" for both
                pollutants. No UHF42 crosswalk needed.

Methodology notes pinned here for the chapter MethodologyFooter:
  - DOHMH publishes PM2.5 and NO2 at CD geography directly via the EH
    Data Portal indicator dataset. `geo_join_id` == `boro_cd`. We do
    not aggregate from UHF42.
  - Annual mean is the canonical EPA metric for chronic exposure;
    seasonal numbers (Summer/Winter) are noted in the dataset but not
    used in the spine.
  - Pollutant year may differ across PM2.5 vs NO2 — the program picks
    each pollutant's latest "Annual Average YYYY" period independently
    and records the chosen year alongside the value.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(REPO_ROOT))

from pipelines import doh_air  # noqa: E402
from shared.cd_names import name_for  # noqa: E402
from shared.zip_to_cd import is_real_cd  # noqa: E402

OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

# DOHMH dataset uses these labels in `name`.
POLLUTANTS = {
    "pm25": "Fine particles (PM 2.5)",
    "no2": "Nitrogen dioxide (NO2)",
}


# ---------- axis 1: ambient air quality ----------

def per_cd_air(pollutant_key: str) -> tuple["pd.Series", int]:
    """Latest Annual-Average per-CD value for the given pollutant.

    Returns (series indexed by boro_cd, year_used). The DOHMH dataset
    publishes CD-level data directly; we filter to ``geo_type_name ==
    'CD'`` and the most recent ``Annual Average YYYY`` period.
    """
    import pandas as pd

    rows = json.loads(doh_air.fetch(pollutant=POLLUTANTS[pollutant_key]).read_text())
    df = pd.DataFrame(rows)
    df = df[df["geo_type_name"] == "CD"].copy()
    df["data_value"] = pd.to_numeric(df["data_value"], errors="coerce")

    annual = df[df["time_period"].str.startswith("Annual Average ", na=False)].copy()
    annual["year"] = annual["time_period"].str[-4:].astype(int)
    latest_year = int(annual["year"].max())
    latest = annual[annual["year"] == latest_year].copy()

    latest["borocd"] = latest["geo_join_id"].astype(str).str.zfill(3)
    latest = latest[latest["borocd"].apply(is_real_cd)]

    series = latest.groupby("borocd")["data_value"].mean().round(3)
    series.name = f"{pollutant_key}_annual"
    return series, latest_year


# ---------- axis 2: green-space access (STUB) ----------

def per_cd_green() -> "pd.Series | None":
    """% residents within 10-min walk of a 1+ acre park, per CD.

    TODO (next session):
      - Replace OSM `parks` query with NYC Parks Properties dataset
        (NYC Open Data, dataset enfh-gkve) for authoritative polygons
        + official acreage. The OSM `out center tags` query we already
        have is not enough for a polygon-based metric.
      - Filter parks to >= 1 acre.
      - For each NYC tract centroid, compute walking distance to
        nearest qualifying park (reuse osmnx walk-network code from
        Ch. 1 or a simple haversine + 10-min cutoff at 3 mph).
      - Aggregate to CD via tract pop weights (B01003).
    """
    return None


# ---------- axis 3: nuisance / env-311 (STUB) ----------

def per_cd_env311() -> "pd.DataFrame | None":
    """Env-related 311 complaints per 1k residents per year, per CD.

    Complaint types (per session 2026-05-30):
      - Noise (all 'Noise - *' descriptors)
      - Rat / Rodent
      - Illegal Dumping + Dirty Conditions
      - Idling vehicle + Air Quality  (flagged: may couple with axis 1)

    TODO (next session):
      - Extend pipelines.three_one_one with
        `fetch_counts_by_zip_complaint(window, types)`, mirroring the
        server-side aggregated pattern in pipelines.hpd_violations
        (`fetch_counts_by_zip`). The full row pull won't fit in 50k.
      - Window: 2024-01-01 .. 2026-06-01 (post-pandemic baseline).
      - Allocate zip-level counts to CDs via the existing area-weighted
        geographies/zip_cd_crosswalk.csv.
      - Denominator: B01003_001E (total pop) per CD, via the existing
        ACS pipeline.
    """
    return None


# ---------- spine test ----------

def spearman_matrix(df: "pd.DataFrame") -> "pd.DataFrame":
    """Pairwise Spearman rho across all numeric columns, rounded."""
    return df.corr(method="spearman").round(3)


def run_spine_test(facts: "pd.DataFrame", kill_threshold: float = 0.75) -> dict:
    """Report Spearman correlations + flag pairs that fire the kill criterion."""
    cols = [c for c in facts.columns if facts[c].dtype.kind in "fi"]
    if len(cols) < 2:
        return {"status": "deferred", "reason": "need >=2 axes"}
    rho = spearman_matrix(facts[cols])

    pairs = []
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            r = float(rho.loc[a, b])
            pairs.append({"a": a, "b": b, "rho": r, "fires_kill": abs(r) >= kill_threshold})
    return {
        "status": "ran",
        "kill_threshold": kill_threshold,
        "axes": cols,
        "pairs": pairs,
        "matrix": rho.to_dict(),
    }


# ---------- driver ----------

def main() -> int:
    import pandas as pd

    print("[ch.3] axis 1: air quality (PM2.5 + NO2, CD-direct)")
    pm25, pm25_year = per_cd_air("pm25")
    no2, no2_year = per_cd_air("no2")
    print(f"  pm25: {len(pm25)} CDs, Annual Average {pm25_year}, "
          f"range {pm25.min():.2f}–{pm25.max():.2f} mcg/m3")
    print(f"  no2:  {len(no2)} CDs, Annual Average {no2_year},  "
          f"range {no2.min():.2f}–{no2.max():.2f} ppb")

    facts = pd.DataFrame({pm25.name: pm25, no2.name: no2})
    facts.index.name = "borocd"

    print("[ch.3] axis 2: green-space — STUB (see TODO in per_cd_green)")
    green = per_cd_green()
    if green is not None:
        facts["green_10min_pct"] = green

    print("[ch.3] axis 3: env-311 — STUB (see TODO in per_cd_env311)")
    env311 = per_cd_env311()
    if env311 is not None:
        facts = facts.join(env311)

    facts["name"] = facts.index.to_series().map(name_for)
    print(f"[ch.3] {len(facts)} CDs with at least the air axis populated.")

    # Spine test on whatever's wired up
    spine = run_spine_test(facts)
    if spine["status"] == "ran":
        print("[ch.3] spine test:")
        for p in spine["pairs"]:
            tag = " [KILL]" if p["fires_kill"] else ""
            print(f"  {p['a']:>22} <-> {p['b']:<22} rho = {p['rho']:+.3f}{tag}")
    else:
        print(f"[ch.3] spine test: deferred ({spine.get('reason')})")

    # Outputs
    out_facts = OUT / "facts.json"
    payload = {
        "vintage": {
            "pm25": f"DOHMH c3uy-2p5r, Annual Average {pm25_year}",
            "no2": f"DOHMH c3uy-2p5r, Annual Average {no2_year}",
        },
        "axes_status": {
            "air": "wired",
            "green_space": "stub",
            "env_311": "stub",
        },
        "spine_test": spine,
        "per_cd": json.loads(facts.reset_index().to_json(orient="records")),
    }
    out_facts.write_text(json.dumps(payload, indent=2))
    print(f"  -> {out_facts}  ({out_facts.stat().st_size:,} bytes)")

    rankings = []
    for col in [c for c in facts.columns if c.endswith("_annual")]:
        ranked = facts[[col, "name"]].dropna().sort_values(col, ascending=False)
        ranked["rank"] = range(1, len(ranked) + 1)
        ranked["axis"] = col
        rankings.append(ranked.reset_index().rename(columns={col: "value"}))
    if rankings:
        long = pd.concat(rankings, ignore_index=True)[
            ["axis", "rank", "borocd", "name", "value"]
        ]
        out_rankings = OUT / "rankings.csv"
        long.to_csv(out_rankings, index=False)
        print(f"  -> {out_rankings}  ({out_rankings.stat().st_size:,} bytes)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
