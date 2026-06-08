"""Chapter 4 — growth/gentrification check (exploratory, NOT shipped).

Tests the hypothesis that neighborhood *growth* (often gentrification)
explains low childcare sufficiency — i.e. fast-growing districts have
demand outrunning childcare supply. Verdict: it does NOT hold (see
METHODOLOGY.md §6c). Kept as a reproducible record of a rejected
hypothesis; not wired into the chapter notebook or facts.json.

Method (consistent across both vintages to avoid assignment bias):
  - Population + children under 5 per census tract, 2010 (dec/sf1 P12)
    and 2020 (dec/dhc P12), five NYC counties.
  - Each year's tracts assigned to CDs by their own cartographic-boundary
    centroid (same method both years), so 2010↔2020 boundary changes
    don't bias the CD-level change.
  - Per-CD % change in population and in under-5, correlated (Spearman)
    with childcare sufficiency from rankings.csv.

Run:  CENSUS_API_KEY=... python analyses/chapter-04/growth_check.py
"""

from __future__ import annotations

import os
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(REPO_ROOT))

NYC_COUNTIES = "005,047,061,081,085"
CB_2010 = "https://www2.census.gov/geo/tiger/GENZ2010/gz_2010_36_140_00_500k.zip"
CB_2020 = "https://www2.census.gov/geo/tiger/GENZ2020/shp/cb_2020_36_tract_500k.zip"


def _fetch_census(url: str, variables: str) -> "pd.DataFrame":
    import pandas as pd
    import requests

    key = os.environ["CENSUS_API_KEY"]
    r = requests.get(url, params={"get": variables, "for": "tract:*",
                                  "in": f"state:36 county:{NYC_COUNTIES}", "key": key},
                     timeout=120)
    r.raise_for_status()
    rows = r.json()
    df = pd.DataFrame(rows[1:], columns=rows[0])
    df["geoid"] = df["state"] + df["county"] + df["tract"]
    return df


def _tract_to_cd(cb_url: str) -> "pd.Series":
    """Assign one vintage's cartographic-boundary tracts to CDs by centroid."""
    import geopandas as gpd
    from shared import basemap
    from shared.zip_to_cd import is_real_cd

    cb = gpd.read_file(cb_url)
    # 2010 file has STATE/COUNTY/TRACT; 2020 file has STATEFP/COUNTYFP/TRACTCE.
    cols = {c.upper(): c for c in cb.columns}
    s = cols.get("STATE") or cols.get("STATEFP")
    c = cols.get("COUNTY") or cols.get("COUNTYFP")
    t = cols.get("TRACT") or cols.get("TRACTCE")
    cb["geoid"] = cb[s].astype(str) + cb[c].astype(str) + cb[t].astype(str)
    cds = basemap.load("cd")
    cds = cds[cds["boro_cd"].apply(is_real_cd)].to_crs(2263)
    cent = gpd.GeoDataFrame(cb[["geoid"]],
                            geometry=cb.to_crs(2263).geometry.representative_point(),
                            crs="EPSG:2263")
    j = gpd.sjoin(cent, cds[["boro_cd", "geometry"]], how="left", predicate="within")
    return j.set_index("geoid")["boro_cd"]


def main() -> int:
    import pandas as pd

    d20 = _fetch_census("https://api.census.gov/data/2020/dec/dhc",
                        "P12_001N,P12_003N,P12_027N")
    d20["pop"] = pd.to_numeric(d20["P12_001N"])
    d20["u5"] = pd.to_numeric(d20["P12_003N"]) + pd.to_numeric(d20["P12_027N"])
    d20["cd"] = d20["geoid"].map(_tract_to_cd(CB_2020))

    d10 = _fetch_census("https://api.census.gov/data/2010/dec/sf1",
                        "P012001,P012003,P012027")
    d10["pop"] = pd.to_numeric(d10["P012001"])
    d10["u5"] = pd.to_numeric(d10["P012003"]) + pd.to_numeric(d10["P012027"])
    d10["cd"] = d10["geoid"].map(_tract_to_cd(CB_2010))

    g20 = d20.dropna(subset=["cd"]).groupby("cd").agg(pop20=("pop", "sum"), u5_20=("u5", "sum"))
    g10 = d10.dropna(subset=["cd"]).groupby("cd").agg(pop10=("pop", "sum"), u5_10=("u5", "sum"))
    m = g20.join(g10)
    m["pop_chg"] = (100 * (m.pop20 - m.pop10) / m.pop10).round(1)
    m["u5_chg"] = (100 * (m.u5_20 - m.u5_10) / m.u5_10).round(1)

    rk = pd.read_csv(HERE / "out" / "rankings.csv")
    rk["borocd"] = rk["borocd"].astype(str)
    m = m.join(rk.set_index("borocd")[["cd_name", "childcare_slots_per_100_u5"]])

    def rho(a, b):
        return round(m[a].rank().corr(m[b].rank()), 3)

    cw = round(100 * (m.pop20.sum() - m.pop10.sum()) / m.pop10.sum(), 1)
    print(f"citywide population change 2010->2020: {cw}%  (census actual ~ +7.7%)")
    print(f"Spearman  pop_chg ~ childcare sufficiency : {rho('pop_chg', 'childcare_slots_per_100_u5'):+}")
    print(f"Spearman  u5_chg  ~ childcare sufficiency : {rho('u5_chg', 'childcare_slots_per_100_u5'):+}")
    print("\nstarved/demoted CDs — growth vs sufficiency:")
    for cd in ["110", "111", "314", "405", "404"]:
        if cd in m.index:
            r = m.loc[cd]
            print(f"  {cd} {str(r.cd_name)[:24]:24} pop {r.pop_chg:+6.1f}%  u5 {r.u5_chg:+6.1f}%  suff {r.childcare_slots_per_100_u5}")
    print("\nfastest-growing CDs — growth vs sufficiency:")
    for cd, r in m.sort_values("pop_chg", ascending=False).head(5).iterrows():
        print(f"  {cd} {str(r.cd_name)[:24]:24} pop {r.pop_chg:+6.1f}%  suff {r.childcare_slots_per_100_u5}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
