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

from pipelines import acs_census, doh_air, nyc_parks, three_one_one  # noqa: E402
from shared.cd_names import name_for  # noqa: E402
from shared.zip_to_cd import is_real_cd  # noqa: E402

OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

# DOHMH dataset uses these labels in `name`.
POLLUTANTS = {
    "pm25": "Fine particles (PM 2.5)",
    "no2": "Nitrogen dioxide (NO2)",
}

# Env-311 window. Post-pandemic baseline; the 2020-2022 era is distorted
# by lockdown noise patterns (filings up, dumping up) and isn't a fair
# steady-state rate.
ENV_WINDOW_START = "2024-01-01"
ENV_WINDOW_END = "2026-06-01"  # = pinned snapshot

# Anchor CDs per PLAN's Decision log (locked 2026-05-30, n=5 across all
# 5 boroughs). Names are pulled at render time from shared.cd_names so
# prose / table / geojson / explorer can never drift.
#   112 - cold open (In the Heights / "96,000" — lived-experience inversion)
#   105 - stacked-burden peak (PM2.5 #1, env-311 #2)
#   206 - surprise-finding anchor (Bronx-isn't-the-worst post metric-switch)
#   311 - green-poor contrast (green #3 worst)
#   503 - low-burden contrast (PM2.5 cleanest, env-311 near bottom)
ANCHOR_CDS = ("112", "105", "206", "311", "503")


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


# ---------- shared: tract -> CD + CD population ----------

def tract_to_cd() -> "pd.Series":
    """Return a Series keyed by tract GEOID (11-char), value = boro_cd.

    Same centroid-sjoin pattern Ch. 2 uses. Tracts (~4k residents) nest
    mostly inside CDs (~150k residents), so a centroid join is
    well-behaved.
    """
    import geopandas as gpd
    from shared import basemap

    tracts = basemap.load("tract")
    cds = basemap.load("cd")
    cds = cds[cds["boro_cd"].apply(is_real_cd)].copy()

    centroids = gpd.GeoDataFrame(
        {"geoid": tracts["geoid"]},
        geometry=tracts.geometry.representative_point(),
        crs=tracts.crs,
    )
    joined = gpd.sjoin(
        centroids,
        cds[["boro_cd", "geometry"]],
        how="left",
        predicate="within",
    )
    s = joined.set_index("geoid")["boro_cd"]
    n_unassigned = s.isna().sum()
    print(f"  tract->CD: {len(s)} tracts, {n_unassigned} unassigned (water/airport)")
    return s


def _acs_tract_df(table: str) -> "pd.DataFrame":
    """Load a cached ACS tract-level table; return DataFrame indexed by GEOID."""
    import pandas as pd

    raw = json.loads((acs_census.fetch(table, "tract")).read_text())
    df = pd.DataFrame(raw[1:], columns=raw[0])
    df["geoid"] = df["GEO_ID"].str[-11:]
    return df.set_index("geoid")


def per_cd_population(t2c: "pd.Series") -> "pd.Series":
    """Total population per CD (sum of B01003_001E across tracts in the CD)."""
    import pandas as pd

    df = _acs_tract_df("B01003")
    pop = pd.to_numeric(df["B01003_001E"], errors="coerce")
    out = pd.DataFrame({"pop": pop})
    out["borocd"] = t2c.reindex(out.index)
    series = (
        out.dropna(subset=["borocd", "pop"])
        .groupby("borocd")["pop"]
        .sum()
        .round(0)
        .astype(int)
    )
    series.name = "pop"
    return series


# Sq ft per square mile (constant). NYC State Plane (EPSG:2263) is in
# feet, so polygon areas come out as sqft.
_SQFT_PER_SQMI = 27_878_400


def per_cd_density(cd_pop: "pd.Series") -> "pd.DataFrame":
    """Residential density (residents / sq mi) per CD.

    Chapter 3's "aliveness" proxy: how many people live in a square mile
    of the CD. Captures the residential floor of occupancy; the daytime
    population (workers + visitors) would lift the ceiling but isn't in
    this chapter's spine (see Midtown caveat in the prose). CD area is
    computed from the EPSG:2263 polygon (NY State Plane feet) and
    converted to square miles.
    """
    import pandas as pd
    from shared import basemap

    cds = basemap.load("cd")
    cds = cds[cds["boro_cd"].apply(is_real_cd)].copy()
    area_sqmi = (cds.geometry.area / _SQFT_PER_SQMI).round(3)
    area_sqmi.index = cds["boro_cd"].values

    out = pd.DataFrame({"area_sqmi": area_sqmi.reindex(cd_pop.index)})
    out["pop_per_sqmi"] = (cd_pop / out["area_sqmi"]).round(0).astype(int)
    return out


# ---------- axis 2: green-space access ----------

# 10-min walk @ 3 mph = 0.5 mi = 2640 ft straight-line. This is the
# conservative (under-counting) approximation noted in the chapter
# MethodologyFooter: an actual walking-network distance would be ~1.3x
# longer for a given straight-line span, so this cutoff slightly
# under-counts coverage. Acceptable for the spine test; revisit before
# the headline visual if the spine survives.
WALK_RADIUS_FT = 2640.0
MIN_PARK_ACRES = 1.0


def per_cd_green(t2c: "pd.Series") -> "pd.Series":
    """% residents within ~10-min walk of a 1+ acre park, per CD.

    Method:
      - Filter NYC Parks Properties (``enfh-gkve``) to ``acres >= 1``.
      - For each NYC census tract, take its representative point as a
        proxy centroid and find the straight-line distance to the
        nearest qualifying park polygon (``sjoin_nearest`` in
        EPSG:2263). Distance = 0 if the centroid is inside a park.
      - A tract is "covered" iff its centroid is within
        ``WALK_RADIUS_FT`` of a qualifying park.
      - CD-level metric: population-weighted mean of the tract
        coverage indicator (B01003 total pop as the weight). Returns
        a value in [0, 1].
    """
    import geopandas as gpd
    import pandas as pd
    from shared import basemap

    parks = nyc_parks.load(min_acres=MIN_PARK_ACRES)
    parks = parks[parks.geometry.notna() & ~parks.geometry.is_empty].copy()
    print(f"  parks: {len(parks)} polygons >= {MIN_PARK_ACRES} acre "
          f"(total acres {parks['acres'].sum():,.0f})")

    tracts = basemap.load("tract")
    centroids = gpd.GeoDataFrame(
        {"geoid": tracts["geoid"]},
        geometry=tracts.geometry.representative_point(),
        crs=tracts.crs,
    )
    nearest = gpd.sjoin_nearest(
        centroids,
        parks[["gispropnum", "geometry"]],
        how="left",
        distance_col="dist_ft",
    )
    # sjoin_nearest returns multiple rows on ties; keep the closest.
    nearest = (
        nearest.sort_values("dist_ft")
        .drop_duplicates(subset=["geoid"], keep="first")
        .set_index("geoid")
    )

    pop = pd.to_numeric(_acs_tract_df("B01003")["B01003_001E"], errors="coerce")
    df = pd.DataFrame({
        "dist_ft": nearest["dist_ft"],
        "borocd": t2c.reindex(nearest.index),
        "pop": pop.reindex(nearest.index),
    }).dropna(subset=["borocd", "dist_ft", "pop"])

    df["within"] = (df["dist_ft"] <= WALK_RADIUS_FT).astype(int)
    df["within_pop"] = df["within"] * df["pop"]
    agg = df.groupby("borocd").agg(num=("within_pop", "sum"), denom=("pop", "sum"))
    series = (agg["num"] / agg["denom"]).round(4)
    series.name = "green_10min_pct"
    return series


# ---------- axis 3: nuisance / env-311 ----------

def _allocate_zip_to_cd(zip_values: "pd.DataFrame", value_col: str) -> "pd.DataFrame":
    """Allocate a per-(bucket, zip) value to CDs via the area-weighted crosswalk.

    ``zip_values`` must have columns ``bucket``, ``modzcta``, ``value_col``.
    Returns a wide DataFrame indexed by ``borocd`` with one column per
    bucket. Drops the per-zip rows for ZIPs that don't appear in the
    NYC crosswalk (non-NYC / invalid).
    """
    import pandas as pd

    xwalk = pd.read_csv(
        REPO_ROOT / "geographies" / "zip_cd_crosswalk.csv",
        dtype={"modzcta": str, "borocd": str},
    )
    merged = xwalk.merge(zip_values, on="modzcta", how="inner")
    merged["allocated"] = merged[value_col] * merged["area_weight"]
    return (
        merged.groupby(["borocd", "bucket"])["allocated"].sum()
        .unstack("bucket", fill_value=0.0)
        .reindex(columns=list(three_one_one.ENV_BUCKETS.keys()), fill_value=0.0)
    )


def per_cd_env311(cd_pop: "pd.Series") -> "pd.DataFrame":
    """Per-CD env-311 burden, expressed as distinct complaining addresses.

    **Primary metric: ``env311_addrs_per_1k_pop_per_yr``** — the number
    of distinct ``incident_address`` values that filed at least one env-
    bucket complaint in the window, allocated zip->CD via the area-
    weighted crosswalk, normalized by CD population and window-years.

    Why distinct addresses and not raw call counts: 311 has a well-known
    super-caller / chronic-address pattern (PLAN.md decision log,
    2026-05-30). In the raw-count metric, CD 212 (Williamsbridge / Bx)
    came in at 572 calls / 1k / yr — ~3x the next CD — and 97% of that
    volume was zip 10466 "Loud Music/Party" calls, with one address
    generating ~13% of the zip's complaint volume on its own. Counting
    distinct complaining addresses instead of total complaints measures
    *how widespread* the complaint behavior is, not how loudly a few
    addresses are calling. This neutralizes the super-caller effect
    structurally rather than by ad-hoc capping.

    Buckets (see ``pipelines.three_one_one.ENV_BUCKETS``):
      - noise   (any 'Noise%' complaint_type)
      - rodent  (Rodent)
      - dirty   (Dirty Condition + Illegal Dumping + Sanitation Condition)
      - idair   (Air Quality + Illegal Idling + Idling)

    Raw call counts are still emitted (``env311_<bucket>_calls_total``)
    so the chapter can also report total volume for context, and so
    downstream consumers can reconstruct the rate-per-call metric
    without re-fetching.
    """
    import pandas as pd

    counts = three_one_one.load_env_counts_by_zip(
        start_date=ENV_WINDOW_START, end_date=ENV_WINDOW_END,
    )
    counts["n"] = pd.to_numeric(counts["n"], errors="coerce").fillna(0).astype(int)
    counts["modzcta"] = counts["zip"].astype(str).str[:5]
    counts_by_zip = counts.groupby(["bucket", "modzcta"])["n"].sum().reset_index()

    addrs = three_one_one.load_env_distinct_addrs_by_zip(
        start_date=ENV_WINDOW_START, end_date=ENV_WINDOW_END,
    )
    addrs["addrs"] = pd.to_numeric(addrs["addrs"], errors="coerce").fillna(0).astype(int)
    addrs["modzcta"] = addrs["zip"].astype(str).str[:5]
    addrs_by_zip = addrs.groupby(["bucket", "modzcta"])["addrs"].sum().reset_index()

    per_cd_calls = _allocate_zip_to_cd(counts_by_zip, "n")
    per_cd_addrs = _allocate_zip_to_cd(addrs_by_zip, "addrs")

    print(
        f"  env-311: {int(counts['n'].sum()):,} complaints from "
        f"{int(addrs['addrs'].sum()):,} distinct addresses in window"
    )

    years = (pd.Timestamp(ENV_WINDOW_END) - pd.Timestamp(ENV_WINDOW_START)).days / 365.25
    out = pd.DataFrame(index=per_cd_calls.index)
    for bucket in three_one_one.ENV_BUCKETS:
        out[f"env311_{bucket}_calls_total"] = per_cd_calls[bucket].round(0).astype(int)
        out[f"env311_{bucket}_addrs_total"] = per_cd_addrs[bucket].round(0).astype(int)
    out["env311_calls_total"] = per_cd_calls.sum(axis=1).round(0).astype(int)
    out["env311_addrs_total"] = per_cd_addrs.sum(axis=1).round(0).astype(int)

    pop = cd_pop.reindex(out.index)
    # Primary metric: distinct complaining addresses per 1k pop per yr.
    out["env311_addrs_per_1k_pop_per_yr"] = (
        out["env311_addrs_total"] / pop * 1000 / years
    ).round(2)
    # Retained for reproducibility / per-bucket inspection.
    out["env311_calls_per_1k_pop_per_yr"] = (
        out["env311_calls_total"] / pop * 1000 / years
    ).round(2)
    for bucket in three_one_one.ENV_BUCKETS:
        out[f"env311_{bucket}_addrs_per_1k_pop_per_yr"] = (
            out[f"env311_{bucket}_addrs_total"] / pop * 1000 / years
        ).round(2)
    return out


# ---------- spine test ----------

# The spine test runs on one representative column per axis (not on every
# numeric column we've cached). PM2.5 stands in for the ambient-air axis
# (PM2.5 <-> NO2 intra-axis rho = +0.84; we treat them as one axis per
# the 2026-05-30 decision log). env-311 uses the distinct-complaining-
# address rate (super-caller-robust), not the raw call rate — see
# per_cd_env311 for rationale.
SPINE_AXES = {
    "air_pm25": "pm25_annual",
    "green_10min": "green_10min_pct",
    "env311_addrs": "env311_addrs_per_1k_pop_per_yr",
}


def spearman_matrix(df: "pd.DataFrame") -> "pd.DataFrame":
    """Pairwise Spearman rho across all numeric columns, rounded."""
    return df.corr(method="spearman").round(3)


def run_spine_test(facts: "pd.DataFrame", kill_threshold: float = 0.75) -> dict:
    """Report Spearman correlations + flag pairs that fire the kill criterion.

    Only the SPINE_AXES columns that are actually populated in ``facts``
    participate; axes still stubbed get ``status='partial'`` in the report.
    """
    populated = {k: v for k, v in SPINE_AXES.items() if v in facts.columns}
    missing = [k for k in SPINE_AXES if k not in populated]
    if len(populated) < 2:
        return {"status": "deferred", "reason": "need >=2 axes", "missing": missing}

    cols = list(populated.values())
    sub = facts[cols].dropna(how="any")
    rho = spearman_matrix(sub)

    pairs = []
    items = list(populated.items())
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a_key, a_col = items[i]
            b_key, b_col = items[j]
            r = float(rho.loc[a_col, b_col])
            pairs.append({
                "a": a_key, "b": b_key,
                "a_col": a_col, "b_col": b_col,
                "rho": r,
                "fires_kill": abs(r) >= kill_threshold,
            })
    return {
        "status": "ran" if not missing else "partial",
        "kill_threshold": kill_threshold,
        "axes": list(populated.keys()),
        "missing": missing,
        "n_cds": int(len(sub)),
        "pairs": pairs,
        "matrix": rho.to_dict(),
    }


# ---------- visuals ----------

def render_headline_pm25_choropleth(facts: "pd.DataFrame", year: int) -> Path:
    """Static SVG + display-CRS geojson for the PM2.5 headline choropleth.

    Mirrors ``analyses/chapter-02/notebook.py`` `render_headline_choropleth`:
    sequential ramp from ``shared.palette``, 5-95th percentile color clip
    (so two Manhattan-core outliers don't flatten the gradient), 50-ft
    polygon simplification in EPSG:2263 (preserves topology), display-CRS
    geojson sibling for the interactive ``<NycMap>``.

    Writes both:
      out/pm25-annual.svg       static visual (chapter MDX img + fallback)
      out/pm25-annual.geojson   per-CD geometry + tooltip fields for <NycMap>
    """
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    from matplotlib.colors import LinearSegmentedColormap
    from shared import basemap, palette
    from shared.zip_to_cd import is_real_cd

    palette.for_matplotlib()

    cds = basemap.load("cd")
    cds = cds[cds["boro_cd"].apply(is_real_cd)].copy()
    cds = cds.merge(
        facts[["pm25_annual"]].reset_index().rename(columns={"borocd": "boro_cd"}),
        on="boro_cd", how="left",
    )
    cds["geometry"] = cds.geometry.simplify(50.0, preserve_topology=True)

    # Per-CD geojson for the interactive map. We bake all three chapter
    # axes into the same geojson so the <NycMap> axis-toggle can switch
    # between them without re-fetching:
    #   pm25_annual                       µg/m³, 2 decimals (lower = better)
    #   green_10min_pct                   %, 1 decimal (higher = better access)
    #   env311_addrs_per_1k_pop_per_yr    distinct addresses calling per 1k pop / yr
    #                                     (higher = more widespread complaint behavior)
    # ``rank_*`` fields are 1-based ranks for each axis (1 = highest value
    # on that axis), so the tooltip can show "#4 of 59" without client
    # recomputing.
    geo_cds = cds[["boro_cd", "geometry"]].copy()
    geo_cds["name"] = geo_cds["boro_cd"].map(name_for)
    geo_cds["pm25_annual"] = cds["pm25_annual"].round(2)
    # Green is stored 0..1 in facts; tooltip displays % so write ×100.
    geo_cds["green_10min_pct"] = (
        facts["green_10min_pct"].reindex(cds["boro_cd"].values).values * 100
    ).round(1)
    geo_cds["env311_addrs_per_1k_pop_per_yr"] = (
        facts["env311_addrs_per_1k_pop_per_yr"].reindex(cds["boro_cd"].values).values
    ).round(2)
    geo_cds["rank_pm25"] = (
        geo_cds["pm25_annual"].rank(ascending=False, method="min").astype("Int64")
    )
    geo_cds["rank_green"] = (
        geo_cds["green_10min_pct"].rank(ascending=False, method="min").astype("Int64")
    )
    geo_cds["rank_env311"] = (
        geo_cds["env311_addrs_per_1k_pop_per_yr"].rank(ascending=False, method="min").astype("Int64")
    )
    geojson_path = OUT / "pm25-annual.geojson"
    basemap.to_display(geo_cds).to_file(geojson_path, driver="GeoJSON")

    values = cds["pm25_annual"].astype(float)
    vmin = float(values.quantile(0.05))
    vmax = float(values.quantile(0.95))
    cmap = LinearSegmentedColormap.from_list("mny_seq", palette.RAMP_SEQUENTIAL, N=256)

    fig, ax = plt.subplots(figsize=(8.5, 9.5))
    cds.plot(
        column="pm25_annual",
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        ax=ax,
        edgecolor=palette.BORDER,
        linewidth=0.4,
        missing_kwds={"color": palette.SURFACE, "edgecolor": palette.BORDER},
    )

    # Anchor labels — small text at each anchor CD's representative point.
    for cd_row in cds.itertuples(index=False):
        if cd_row.boro_cd not in ANCHOR_CDS:
            continue
        p = cd_row.geometry.representative_point()
        ax.annotate(
            f"CD {cd_row.boro_cd}\n{cd_row.pm25_annual:.1f} µg/m³",
            xy=(p.x, p.y),
            ha="center",
            va="center",
            fontsize=8,
            color=palette.TEXT,
            bbox=dict(boxstyle="round,pad=0.25", facecolor=palette.BG,
                      edgecolor=palette.BORDER, linewidth=0.5),
        )

    ax.set_axis_off()
    ax.set_title(
        "Fine particulate matter by community district",
        fontsize=14,
        color=palette.TEXT,
        pad=10,
        loc="left",
    )
    ax.text(
        0.0, 1.005,
        f"PM 2.5 annual mean concentration · DOHMH {year}",
        transform=ax.transAxes,
        fontsize=9,
        color=palette.TEXT_SECONDARY,
        ha="left",
        va="bottom",
    )

    sm = plt.cm.ScalarMappable(
        cmap=cmap, norm=mcolors.Normalize(vmin=vmin, vmax=vmax),
    )
    sm.set_array([])
    cbar = fig.colorbar(
        sm, ax=ax, orientation="horizontal",
        fraction=0.035, pad=0.02, shrink=0.55,
        format=lambda x, _pos: f"{x:.1f}",
    )
    cbar.outline.set_visible(False)
    cbar.ax.tick_params(labelsize=8, colors=palette.TEXT_SECONDARY)
    cbar.set_label(
        "PM 2.5 (µg/m³, 5th–95th pct clip)",
        fontsize=9,
        color=palette.TEXT_SECONDARY,
    )

    svg_path = OUT / "pm25-annual.svg"
    fig.savefig(svg_path, format="svg")
    plt.close(fig)
    print(f"[wrote] {svg_path}      ({svg_path.stat().st_size:,} bytes)")
    print(f"[wrote] {geojson_path}  ({geojson_path.stat().st_size:,} bytes)")
    return svg_path


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

    print("[ch.3] tract->CD + CD population (ACS B01003)")
    t2c = tract_to_cd()
    cd_pop = per_cd_population(t2c)
    facts = facts.join(cd_pop.rename("pop"))
    print(f"  CD pop: {len(cd_pop)} CDs, total {int(cd_pop.sum()):,}, "
          f"range {int(cd_pop.min()):,}-{int(cd_pop.max()):,}")

    print("[ch.3] residential density (aliveness floor)")
    density = per_cd_density(cd_pop)
    facts = facts.join(density)
    print(f"  pop_per_sqmi: range {int(density['pop_per_sqmi'].min()):,}-"
          f"{int(density['pop_per_sqmi'].max()):,}, "
          f"median {int(density['pop_per_sqmi'].median()):,}")

    print(f"[ch.3] axis 2: green-space (~10-min walk @ 3 mph, >= {MIN_PARK_ACRES} acre)")
    green = per_cd_green(t2c)
    if green is not None:
        facts["green_10min_pct"] = green
        print(f"  green: {len(green)} CDs, "
              f"range {green.min():.2f}-{green.max():.2f}, mean {green.mean():.2f}")

    print(f"[ch.3] axis 3: env-311 (window {ENV_WINDOW_START}..{ENV_WINDOW_END})")
    env311 = per_cd_env311(cd_pop)
    if env311 is not None:
        facts = facts.join(env311)

    facts["name"] = facts.index.to_series().map(name_for)
    print(f"[ch.3] {len(facts)} CDs with at least the air axis populated.")

    # Spine test on whichever SPINE_AXES columns are wired up
    spine = run_spine_test(facts)
    if spine["status"] in ("ran", "partial"):
        tag_status = "" if spine["status"] == "ran" else f"  (partial; missing {spine['missing']})"
        print(f"[ch.3] spine test (n={spine['n_cds']}){tag_status}")
        for p in spine["pairs"]:
            tag = " [KILL]" if p["fires_kill"] else ""
            print(f"  {p['a']:>14} <-> {p['b']:<14} rho = {p['rho']:+.3f}{tag}")
    else:
        print(f"[ch.3] spine test: deferred ({spine.get('reason')})")

    # Outputs
    out_facts = OUT / "facts.json"
    payload = {
        "vintage": {
            "pm25": f"DOHMH c3uy-2p5r, Annual Average {pm25_year}",
            "no2": f"DOHMH c3uy-2p5r, Annual Average {no2_year}",
            "env_311": f"NYC 311 erm2-nwe9, window {ENV_WINDOW_START}..{ENV_WINDOW_END}",
            "green_space": (
                f"NYC Parks Properties enfh-gkve, snapshot 2026-06-01; "
                f">= {MIN_PARK_ACRES} acre; ~10-min walk = "
                f"{WALK_RADIUS_FT:.0f} ft straight-line"
            ),
            "population": "ACS B01003, 2019-2023 5-yr",
        },
        "axes_status": {
            "air": "wired",
            "green_space": "wired" if green is not None else "stub",
            "env_311": "wired" if env311 is not None else "stub",
        },
        "spine_test": spine,
        "per_cd": json.loads(facts.reset_index().to_json(orient="records")),
    }
    out_facts.write_text(json.dumps(payload, indent=2))
    print(f"  -> {out_facts}  ({out_facts.stat().st_size:,} bytes)")

    print("[ch.3] render headline: PM 2.5 choropleth + geojson")
    render_headline_pm25_choropleth(facts, year=pm25_year)

    rank_cols = (
        [c for c in facts.columns if c.endswith("_annual")]
        + [c for c in ("green_10min_pct",
                       "env311_addrs_per_1k_pop_per_yr",
                       "env311_calls_per_1k_pop_per_yr") if c in facts.columns]
    )
    rankings = []
    for col in rank_cols:
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
