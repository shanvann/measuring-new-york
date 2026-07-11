"""Chapter 6 — Safety · fatalities companion analysis.

The main notebook measures *harm* (violent felonies; pedestrian/cyclist
killed-or-injured) as per-CD rates. This companion answers a sharper,
citywide question raised in review: **compare deaths to deaths.** Murder is
mostly a *count of the dead*; the traffic axis is dominated by injuries. So
here we pull the actual body counts and the victim demographics, to show two
things the rate maps can't:

  1. On deaths alone, murder (~394/yr) outnumbers *all* road deaths
     (~279/yr) and far outnumbers pedestrian+cyclist deaths (~147/yr).
  2. Murder deaths are demographically *concentrated* (young men — the
     fingerprint of dispute/network violence), while traffic deaths are
     *spread* across the population and skew elderly. The dataset carries no
     gang / victim-offender-relationship flag, so demographics are the only
     in-data proxy for "targeted vs. random" — stated as a proxy, not proof.

Writes out/fatalities.json. Small fetches (murders ~1.2k rows; killed
persons ~0.8k rows), cached under cache/.

Run::

    python analyses/chapter-06/fatalities.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(REPO_ROOT))

from shared import cache  # noqa: E402

OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

WINDOW_START = "2022-01-01"
WINDOW_END = "2024-12-31"
YEARS = 3.0

COMPLAINTS_ID = "qgea-i56i"
PERSONS_ID = "f55k-p6yu"


def _fetch(cache_name: str, url: str) -> list:
    import requests

    path = cache.path_for(cache_name)
    if cache.is_cached(cache_name):
        return json.loads(path.read_text())
    print(f"[fetch] {cache_name}")
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    rows = r.json()
    path.write_text(json.dumps(rows))
    cache.record(cache_name, r.url)
    return rows


def murders() -> list:
    where = (
        f"cmplnt_fr_dt between '{WINDOW_START}T00:00:00' and '{WINDOW_END}T23:59:59' "
        f"and ky_cd='101'"
    )
    url = (
        f"https://data.cityofnewyork.us/resource/{COMPLAINTS_ID}.json"
        f"?$select=cmplnt_num,vic_sex,vic_age_group&$where={where}&$limit=50000"
    )
    return _fetch(f"nypd_complaints/murders-demo-{WINDOW_START}_{WINDOW_END}.json", url)


def killed_persons() -> list:
    where = (
        f"crash_date between '{WINDOW_START}T00:00:00' and '{WINDOW_END}T23:59:59' "
        f"and person_injury='Killed'"
    )
    url = (
        f"https://data.cityofnewyork.us/resource/{PERSONS_ID}.json"
        f"?$select=collision_id,person_type,person_sex,person_age&$where={where}&$limit=50000"
    )
    return _fetch(f"nypd_collisions/killed-persons-{WINDOW_START}_{WINDOW_END}.json", url)


def _pct(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


def _age_bucket(age) -> str:
    try:
        a = int(age)
    except (TypeError, ValueError):
        return "unknown"
    if a <= 0 or a > 120:
        return "unknown"
    if a < 18:
        return "<18"
    if a < 45:
        return "18-44"
    if a < 65:
        return "45-64"
    return "65+"


def main() -> int:
    import pandas as pd

    # ---- murders (victim demographics) ----
    m = pd.DataFrame(murders())
    n_murder = len(m)
    m_sex = m["vic_sex"].value_counts()
    m_male = int(m_sex.get("M", 0))
    m_age = m["vic_age_group"].value_counts()
    m_young = int(m_age.get("<18", 0) + m_age.get("18-24", 0) + m_age.get("25-44", 0))
    m_elder = int(m_age.get("65+", 0))

    # ---- traffic deaths (mode + victim demographics) ----
    k = pd.DataFrame(killed_persons())
    k["bucket"] = k["person_age"].map(_age_bucket)
    ped_cyc = k[k["person_type"].isin(["Pedestrian", "Bicyclist"])]
    n_all_road = len(k)
    n_ped = int((k["person_type"] == "Pedestrian").sum())
    n_cyc = int((k["person_type"] == "Bicyclist").sum())
    n_pc = len(ped_cyc)
    pc_male = int((ped_cyc["person_sex"] == "M").sum())
    pc_elder = int((ped_cyc["bucket"] == "65+").sum())
    pc_young = int(ped_cyc["bucket"].isin(["<18", "18-44"]).sum())

    facts = {
        "window": [WINDOW_START, WINDOW_END],
        "annualized": True,
        "deaths_per_year": {
            "murder": round(n_murder / YEARS),
            "all_road": round(n_all_road / YEARS),
            "pedestrian": round(n_ped / YEARS),
            "cyclist": round(n_cyc / YEARS),
            "ped_plus_cyclist": round(n_pc / YEARS),
        },
        "totals_over_window": {
            "murder": n_murder,
            "all_road": n_all_road,
            "ped_plus_cyclist": n_pc,
        },
        "murder_victims": {
            "n": n_murder,
            "pct_male": _pct(m_male, n_murder),
            "pct_under_45": _pct(m_young, n_murder),
            "pct_65_plus": _pct(m_elder, n_murder),
        },
        "traffic_victims_ped_cyc": {
            "n": n_pc,
            "pct_male": _pct(pc_male, n_pc),
            "pct_under_45": _pct(pc_young, n_pc),
            "pct_65_plus": _pct(pc_elder, n_pc),
        },
        "concentration_note": (
            "Murder deaths concentrate in young men (dispute/network "
            "violence signature); traffic deaths spread across the population "
            "and skew elderly. The NYPD open data has NO gang or victim-"
            "offender-relationship field — demographics are an in-data PROXY "
            "for targeted-vs-random, not proof of gang involvement."
        ),
    }
    (OUT / "fatalities.json").write_text(json.dumps(facts, indent=2) + "\n")
    d = facts["deaths_per_year"]
    print(f"[fatalities] deaths/yr — murder {d['murder']}, all road {d['all_road']}, "
          f"ped+cyc {d['ped_plus_cyclist']}")
    print(f"[fatalities] murder victims: {facts['murder_victims']['pct_male']}% male, "
          f"{facts['murder_victims']['pct_under_45']}% under 45, "
          f"{facts['murder_victims']['pct_65_plus']}% 65+")
    print(f"[fatalities] traffic victims: {facts['traffic_victims_ped_cyc']['pct_male']}% male, "
          f"{facts['traffic_victims_ped_cyc']['pct_under_45']}% under 45, "
          f"{facts['traffic_victims_ped_cyc']['pct_65_plus']}% 65+")
    print(f"[fatalities] wrote {OUT/'fatalities.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
