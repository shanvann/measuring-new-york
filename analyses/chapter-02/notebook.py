"""Chapter 2 — Housing Stability & Affordability (first-pass).

Goal of this first pass: validate the chapter's spine hypothesis BEFORE
investing in any visual artifacts. The hypothesis (plan §10) is that
**rent burden, median rent, and eviction-filing rate are three
independent axes of housing stress** — the CDs at the top of one
ranking aren't the same CDs at the top of the others. If the three
axes co-rank tightly, the spine collapses and Ch. 2 needs to be
re-spec'd.

Run with::

    python analyses/chapter-02/notebook.py

Outputs (out/ inside this dir):
  facts.json    Per-CD: rent_burden_30, rent_burden_50, median_rent,
                median_income, renter_hh, filings_2yr,
                filings_per_1k_renter_hh_per_yr.
  rankings.csv  Long-form per-CD per-axis rankings (sortable for QA).

Datasets (all already cached at series vintage):
  ACS B25070   Gross Rent as % of HH Income (tract)
  ACS B25064   Median Gross Rent (tract)
  ACS B25003   Tenure (tract) — renter-HH denominator
  ACS B19013   Median Household Income (tract)
  OCA filings  HDC bundle snapshot 2026-05-10, NYC courts only
  zip→CD       geographies/zip_cd_crosswalk.csv (area-weighted)

Methodology notes pinned here for the chapter MethodologyFooter:
  - Tract→CD aggregation uses tract centroid sjoin (Ch. 1 pattern).
    Tracts (~4k residents) nest mostly inside CDs (~150k residents)
    so a centroid join is well-behaved.
  - Rent burden numerator excludes B25070_011E ("Not computed",
    i.e. no cash rent or zero income).
  - CD median rent is approximated by the renter-HH-weighted mean of
    tract median rents within the CD. A true CD-level median would
    require redistributing B25063 (rent in brackets) — left for the
    final-pass refinement.
  - OCA window: 2024-01-01 to 2026-05-10 (~2.4 yr post-moratorium).
    The pre-pandemic baseline is in a separate notebook pass.
  - OCA→CD allocation uses the area-weighted zip→CD crosswalk; for
    ZIPs straddling multiple CDs, filings split by area share.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(REPO_ROOT))

from pipelines import acs_census, hpd_violations, oca_evictions  # noqa: E402
from shared import basemap  # noqa: E402
from shared.cd_names import name_for  # noqa: E402

OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

# Anchor CDs per plan §10 (finalized 2026-05-24 against first-pass data).
# Each anchors a distinct (burden, structural-distress) position.
# Names are pulled from shared/cd_names.py so the chapter prose can't
# drift away from the canonical labels (an earlier draft mislabelled
# CD 313 as "Brownsville" — Brownsville is CD 316; CD 313 is
# Coney Island / Brighton Beach).
ANCHOR_NAMES = {cd: name_for(cd) for cd in ("206", "313", "109", "108", "411")}

# OCA filings window. The 2020-2022 era is heavily distorted by the
# state eviction moratorium + court backlog clearance; restrict to
# post-2023 so the rate reflects steady-state filings behavior.
OCA_WINDOW_START = "2024-01-01"
OCA_WINDOW_END = "2026-05-10"  # = OCA snapshot date


# ---------- tract → CD ----------

def tract_to_cd() -> "pd.Series":
    """Return a Series keyed by tract GEOID (11-char), value = boro_cd."""
    import geopandas as gpd

    tracts = basemap.load("tract")
    cds = basemap.load("cd")
    # Restrict to the 59 real CDs (drops JIAs like parks/airports).
    from shared.zip_to_cd import is_real_cd
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
    print(f"  tract→CD: {len(s)} tracts, {n_unassigned} unassigned (water/airport)")
    return s


# ---------- ACS loaders ----------

def _acs_tract_df(table: str) -> "pd.DataFrame":
    """Load a cached ACS tract-level table; return DataFrame indexed by GEOID."""
    import pandas as pd

    raw = json.loads((acs_census.fetch(table, "tract")).read_text())
    df = pd.DataFrame(raw[1:], columns=raw[0])
    # GEO_ID is like '1400000US36005000100'; last 11 chars match tract geoid.
    df["geoid"] = df["GEO_ID"].str[-11:]
    return df.set_index("geoid")


# ---------- per-CD metrics ----------

def per_cd_rent_burden(t2c: "pd.Series") -> "pd.DataFrame":
    """Aggregate B25070 brackets to CD level; compute %≥30 and %≥50."""
    import pandas as pd

    df = _acs_tract_df("B25070")
    cols = ["B25070_001E", "B25070_007E", "B25070_008E",
            "B25070_009E", "B25070_010E", "B25070_011E"]
    df[cols] = df[cols].astype(float)
    df["borocd"] = t2c.reindex(df.index)
    agg = df.dropna(subset=["borocd"]).groupby("borocd")[cols].sum()

    # Denominator: total minus "Not computed"
    denom = agg["B25070_001E"] - agg["B25070_011E"]
    burdened_30 = agg["B25070_007E"] + agg["B25070_008E"] + agg["B25070_009E"] + agg["B25070_010E"]
    burdened_50 = agg["B25070_010E"]

    out = pd.DataFrame({
        "rent_burden_30": (burdened_30 / denom).round(4),
        "rent_burden_50": (burdened_50 / denom).round(4),
        "rent_eligible_hh": denom.round(0).astype(int),
    })
    return out


def per_cd_renter_hh(t2c: "pd.Series") -> "pd.Series":
    """B25003_003E (renter-occupied) summed per CD."""
    df = _acs_tract_df("B25003")
    df["B25003_003E"] = df["B25003_003E"].astype(float)
    df["borocd"] = t2c.reindex(df.index)
    return df.dropna(subset=["borocd"]).groupby("borocd")["B25003_003E"].sum().round(0).astype(int)


def per_cd_median_rent(t2c: "pd.Series", renter_hh: "pd.Series") -> "pd.Series":
    """Renter-HH-weighted mean of tract median gross rents.

    B25064 is suppressed (-666666666 or NaN) for tracts with too few
    renter HH; those drop out of the weighted mean.
    """
    import pandas as pd

    df = _acs_tract_df("B25064")
    rent = pd.to_numeric(df["B25064_001E"], errors="coerce")
    # ACS suppression sentinel
    rent = rent.where(rent > 0)

    renters = _acs_tract_df("B25003")["B25003_003E"].astype(float)
    df = pd.DataFrame({"rent": rent, "renters": renters})
    df["borocd"] = t2c.reindex(df.index)
    df = df.dropna(subset=["borocd", "rent", "renters"])
    df = df[df["renters"] > 0]

    def wmean(g):
        return (g["rent"] * g["renters"]).sum() / g["renters"].sum()

    return df.groupby("borocd").apply(wmean).round(0).astype(int)


def per_cd_median_income(t2c: "pd.Series") -> "pd.Series":
    """Tract-count mean of B19013 medians, dropping suppressed tracts."""
    import pandas as pd

    df = _acs_tract_df("B19013")
    inc = pd.to_numeric(df["B19013_001E"], errors="coerce")
    inc = inc.where(inc > 0)
    df = pd.DataFrame({"inc": inc})
    df["borocd"] = t2c.reindex(df.index)
    df = df.dropna(subset=["borocd", "inc"])
    return df.groupby("borocd")["inc"].median().round(0).astype(int)


def per_cd_hpd(renter_hh: "pd.Series") -> "pd.DataFrame":
    """HPD violations per CD over the post-moratorium window.

    Allocates ZIP-level counts (per class) to CDs via the area-weighted
    zip→CD crosswalk. Returns total per CD plus a class-C-only series
    (immediately hazardous — the most consequential).
    """
    import pandas as pd

    df = hpd_violations.load_counts_by_zip(
        start_date=OCA_WINDOW_START, end_date=OCA_WINDOW_END,
    )
    df["n"] = pd.to_numeric(df["n"], errors="coerce").fillna(0).astype(int)
    df["zip5"] = df["zip"].str[:5]

    xwalk = pd.read_csv(REPO_ROOT / "geographies" / "zip_cd_crosswalk.csv",
                        dtype={"modzcta": str, "borocd": str})

    # Total (all classes) per zip
    by_zip_all = df.groupby("zip5")["n"].sum().rename("count_all")
    by_zip_c = df[df["class"] == "C"].groupby("zip5")["n"].sum().rename("count_c")

    def allocate(by_zip: "pd.Series") -> "pd.Series":
        x = xwalk.merge(by_zip, left_on="modzcta", right_index=True, how="inner")
        x["allocated"] = x["count_all" if by_zip.name == "count_all" else "count_c"] * x["area_weight"]
        return x.groupby("borocd")["allocated"].sum().round(0).astype(int)

    by_cd_all = allocate(by_zip_all)
    by_cd_c = allocate(by_zip_c)

    matched_zips = set(xwalk["modzcta"])
    lost = by_zip_all.loc[~by_zip_all.index.isin(matched_zips)].sum()
    print(f"  hpd: {by_zip_all.sum():,} violations in window; "
          f"{int(lost):,} dropped from non-NYC/invalid ZIPs")

    years = (pd.Timestamp(OCA_WINDOW_END) - pd.Timestamp(OCA_WINDOW_START)).days / 365.25
    return pd.DataFrame({
        "hpd_window_total": by_cd_all,
        "hpd_class_c_total": by_cd_c,
        "hpd_per_1k_renter_hh_per_yr": (by_cd_all / renter_hh * 1000 / years).round(2),
        "hpd_class_c_per_1k_renter_hh_per_yr": (by_cd_c / renter_hh * 1000 / years).round(2),
    })


def per_cd_filings(renter_hh: "pd.Series") -> "pd.DataFrame":
    """OCA filings per CD over the post-moratorium window.

    Loads filings via ``oca_evictions.load_nyc_filings``, allocates each
    filing's zip count to CDs via the area-weighted crosswalk, then
    normalizes to filings per 1,000 renter HH per year.
    """
    import pandas as pd

    filings = oca_evictions.load_nyc_filings(
        start_date=OCA_WINDOW_START, end_date=OCA_WINDOW_END,
    )
    # Postcodes may be 5- or 10-digit (zip+4). Trim to 5.
    filings["zip5"] = filings["postalcode"].str[:5]
    by_zip = filings.groupby("zip5").size().rename("count")

    xwalk = pd.read_csv(REPO_ROOT / "geographies" / "zip_cd_crosswalk.csv",
                        dtype={"modzcta": str, "borocd": str})
    xwalk = xwalk.merge(by_zip, left_on="modzcta", right_index=True, how="inner")
    xwalk["allocated"] = xwalk["count"] * xwalk["area_weight"]
    by_cd = xwalk.groupby("borocd")["allocated"].sum().round(0).astype(int)

    # ZIPs that don't appear in the crosswalk (non-NYC, '00000', etc.)
    # are dropped; report how many filings we lost so the chapter
    # caveat is honest.
    matched_zips = set(xwalk["modzcta"])
    lost = filings.loc[~filings["zip5"].isin(matched_zips), "zip5"].nunique()
    lost_rows = len(filings) - filings["zip5"].isin(matched_zips).sum()
    print(f"  filings: {len(filings):,} in window; {lost_rows:,} dropped from {lost} non-NYC/invalid ZIPs")

    years = (pd.Timestamp(OCA_WINDOW_END) - pd.Timestamp(OCA_WINDOW_START)).days / 365.25
    rate = (by_cd / renter_hh * 1000 / years).round(2)

    return pd.DataFrame({
        "filings_window_total": by_cd,
        "filings_per_1k_renter_hh_per_yr": rate,
    })


# ---------- visuals ----------

def render_headline_choropleth(facts: "pd.DataFrame") -> Path:
    """Static SVG of the Ch. 2 headline choropleth: rent burden ≥30% per CD.

    Series palette sequential ramp, 5–95th pctile clip, 50-ft polygon
    simplification (matching Ch. 1's _write_chapter_png treatment).
    Also writes an out/rent-burden.geojson with the per-CD value for
    reproducibility.
    """
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    from matplotlib.colors import LinearSegmentedColormap
    from shared import palette
    from shared.zip_to_cd import is_real_cd

    palette.for_matplotlib()

    cds = basemap.load("cd")
    cds = cds[cds["boro_cd"].apply(is_real_cd)].copy()
    cds = cds.merge(
        facts[["rent_burden_30"]].reset_index().rename(columns={"borocd": "boro_cd"}),
        on="boro_cd", how="left",
    )
    cds["geometry"] = cds.geometry.simplify(50.0, preserve_topology=True)

    # Per-CD geojson for reproducibility (display CRS = WGS84).
    # ``rent_burden_30_pct`` (×100, rounded) is the field consumed by the
    # interactive ``<NycMap>`` tooltip — the raw proportion ``rent_burden_30``
    # is preserved alongside for reproducibility / non-display callers.
    # ``name`` carries the canonical neighborhood label (shared/cd_names.py)
    # so the map tooltip shows "CD 206 · Belmont / East Tremont", matching
    # Ch. 1's convention.
    geo_cds = cds[["boro_cd", "rent_burden_30", "geometry"]].copy()
    geo_cds["rent_burden_30_pct"] = (geo_cds["rent_burden_30"] * 100).round(1)
    geo_cds["name"] = geo_cds["boro_cd"].map(name_for)
    basemap.to_display(geo_cds).to_file(OUT / "rent-burden.geojson", driver="GeoJSON")

    values = cds["rent_burden_30"].astype(float)
    vmin = float(values.quantile(0.05))
    vmax = float(values.quantile(0.95))
    cmap = LinearSegmentedColormap.from_list("mny_seq", palette.RAMP_SEQUENTIAL, N=256)

    fig, ax = plt.subplots(figsize=(8.5, 9.5))
    cds.plot(
        column="rent_burden_30",
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
        if cd_row.boro_cd not in ANCHOR_NAMES:
            continue
        p = cd_row.geometry.representative_point()
        ax.annotate(
            f"CD {cd_row.boro_cd}\n{int(cd_row.rent_burden_30 * 100)}%",
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
        "Rent burden by community district",
        fontsize=14,
        color=palette.TEXT,
        pad=10,
        loc="left",
    )
    ax.text(
        0.0, 1.005,
        "Share of renter households spending ≥30% of household income on gross rent · ACS 2019–2023 5-yr",
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
        format=lambda x, _pos: f"{int(x * 100)}%",
    )
    cbar.outline.set_visible(False)
    cbar.ax.tick_params(labelsize=8, colors=palette.TEXT_SECONDARY)
    cbar.set_label(
        "rent-burdened share (5th–95th pct clip)",
        fontsize=9,
        color=palette.TEXT_SECONDARY,
    )

    path = OUT / "rent-burden-cd.svg"
    fig.savefig(path, format="svg")
    plt.close(fig)
    print(f"[wrote] {path}  ({path.stat().st_size:,} bytes)")
    return path


# ---------- correlations + summary ----------

def axis_correlations(facts: "pd.DataFrame") -> dict:
    """Spearman rank correlation matrix across the four housing-stress axes.

    Plan §10 kill criterion: any pair with |ρ|>0.8 means that axis is
    redundant. The "three independent axes" claim becomes "axes A and B
    are independent of each other but C duplicates A" — the chapter's
    spine has to be reframed.
    """
    cols = [
        "rent_burden_30",
        "median_rent",
        "filings_per_1k_renter_hh_per_yr",
        "hpd_per_1k_renter_hh_per_yr",
    ]
    rho = facts[cols].corr(method="spearman").round(3)
    return rho.to_dict()


def summarize(facts: "pd.DataFrame", rho: dict) -> None:
    print()
    print("=" * 72)
    print("CH. 2 FIRST-PASS · per-CD housing stress")
    print("=" * 72)
    for axis, label in [
        ("rent_burden_30", "Rent burden ≥30% (top 5)"),
        ("rent_burden_50", "Severe rent burden ≥50% (top 5)"),
        ("median_rent", "Median rent $ (top 5)"),
        ("filings_per_1k_renter_hh_per_yr", "Eviction filings per 1k renter HH / yr (top 5)"),
        ("hpd_per_1k_renter_hh_per_yr", "HPD violations per 1k renter HH / yr (top 5)"),
        ("hpd_class_c_per_1k_renter_hh_per_yr", "HPD class-C (severe) per 1k renter HH / yr (top 5)"),
    ]:
        print(f"\n{label}")
        top = facts.sort_values(axis, ascending=False).head(5)
        for borocd, row in top.iterrows():
            anchor = " ⭐" if borocd in ANCHOR_NAMES else ""
            print(f"  CD {borocd}  {row[axis]:>10}{anchor}")

    print("\nSpearman rank correlation between axes")
    axes = [
        ("burden_30", "rent_burden_30"),
        ("median_rent", "median_rent"),
        ("filings", "filings_per_1k_renter_hh_per_yr"),
        ("hpd", "hpd_per_1k_renter_hh_per_yr"),
    ]
    for i in range(len(axes)):
        for j in range(i + 1, len(axes)):
            a_label, a_col = axes[i]
            b_label, b_col = axes[j]
            r = rho[a_col][b_col]
            mark = "  ⚠ collinear" if abs(r) > 0.8 else ""
            print(f"  {a_label:<12} ↔ {b_label:<12}  ρ = {r:+.3f}{mark}")
    print()
    print("Kill criterion (plan §10): any |ρ|>0.8 collapses that axis.")

    print("\nAnchor CDs (plan §10) · where do they actually rank?")
    n = len(facts)
    for borocd, name in ANCHOR_NAMES.items():
        if borocd not in facts.index:
            print(f"  CD {borocd} {name}: MISSING from per-CD output")
            continue
        ranks = {a: int(facts[a].rank(ascending=False)[borocd]) for a in [
            "rent_burden_30", "rent_burden_50", "median_rent",
            "filings_per_1k_renter_hh_per_yr",
            "hpd_per_1k_renter_hh_per_yr",
        ]}
        print(
            f"  CD {borocd} {name:<32}"
            f"  burden30 #{ranks['rent_burden_30']:>2}/{n}"
            f"  burden50 #{ranks['rent_burden_50']:>2}/{n}"
            f"  rent #{ranks['median_rent']:>2}/{n}"
            f"  filings #{ranks['filings_per_1k_renter_hh_per_yr']:>2}/{n}"
            f"  hpd #{ranks['hpd_per_1k_renter_hh_per_yr']:>2}/{n}"
        )


# ---------- main ----------

def main() -> int:
    import pandas as pd

    print("[load] geographies + tract→CD")
    t2c = tract_to_cd()

    print("[compute] rent burden brackets (B25070 → CD)")
    burden = per_cd_rent_burden(t2c)

    print("[compute] renter households (B25003 → CD)")
    renter_hh = per_cd_renter_hh(t2c)

    print("[compute] median rent (B25064, renter-HH-weighted → CD)")
    med_rent = per_cd_median_rent(t2c, renter_hh)

    print("[compute] median household income (B19013 → CD)")
    med_inc = per_cd_median_income(t2c)

    print("[load] OCA filings")
    filings = per_cd_filings(renter_hh)

    print("[load] HPD violations")
    hpd = per_cd_hpd(renter_hh)

    facts = pd.concat([
        burden,
        renter_hh.rename("renter_hh"),
        med_rent.rename("median_rent"),
        med_inc.rename("median_income"),
        filings,
        hpd,
    ], axis=1).sort_index()

    rho = axis_correlations(facts)

    out_facts = {
        "snapshot": "2026-05-10",
        "oca_window": [OCA_WINDOW_START, OCA_WINDOW_END],
        "n_cds": int(facts.shape[0]),
        "spearman": rho,
        "per_cd": {
            cd: {k: (None if pd.isna(v) else (float(v) if isinstance(v, float) else int(v)))
                 for k, v in row.items()}
            for cd, row in facts.iterrows()
        },
    }
    (OUT / "facts.json").write_text(json.dumps(out_facts, indent=2))
    facts.to_csv(OUT / "rankings.csv")
    print(f"\n[wrote] {OUT / 'facts.json'}")
    print(f"[wrote] {OUT / 'rankings.csv'}")

    print("[render] headline choropleth (static SVG)")
    render_headline_choropleth(facts)

    summarize(facts, rho)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
