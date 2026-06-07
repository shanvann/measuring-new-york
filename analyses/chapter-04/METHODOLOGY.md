# Chapter 4 — *Within Reach* · Methodology

Full per-metric reference for the chapter. The
[published chapter](https://www.shanitvannala.org/blog/measuring-new-york-04-daily-needs/)
is the curated narrative; this file is the source-of-truth for every
number that appears there, with the exact dataset filters, geographic
aggregation rules, and known limitations.

Every number in the chapter reproduces from
`analyses/chapter-04/notebook.py` against the pinned `MANIFEST.json`.
This document describes the *what* and *why*; the notebook is the *how*.

---

## 1. The chapter's two questions: proximity vs sufficiency

Unlike Chapters 1–3, this chapter does **not** ship as N independent
dimensions. It measures two different things:

- **Proximity** — how close residents live to daily-needs amenities,
  measured as three pop-weighted walk-access baskets (food, care,
  civic).
- **Sufficiency** — whether what's nearby is *enough*, measured on
  childcare (the daily need with a capacity number attached): licensed
  slots per 100 children under 5.

### Why proximity is not shipped as three independent axes

The three proximity baskets were run through the series-wide kill test
(|ρ| ≥ 0.75 between any pair collapses the dimension):

| Pair | Spearman ρ | Fires kill? |
|---|---:|---|
| Food ↔ Care | +0.733 | no (barely) |
| Care ↔ Civic | +0.743 | no (barely) |
| Food ↔ Civic | +0.647 | no |

The spine formally survives, but two of three pairs land within 0.02 of
the threshold. All three baskets are walk-access measures, and walk-access
is largely a restatement of population density — so the baskets are nearly
collinear. Rather than overstate their independence, the chapter treats
proximity as **one** signal (density) and pivots to sufficiency, which is
where the real inequality lives.

The pivot is validated by the key statistic: childcare **proximity** ↔
**sufficiency** ρ = **+0.369**. Being near childcare barely predicts
having enough of it.

Spearman ρ is computed as the Pearson correlation of ranks (avoids a
scipy dependency).

---

## 2. The walk-access primitive (shared by all proximity baskets)

For each amenity type:

1. Take each NYC census tract's representative point as a proxy centroid.
2. Find the straight-line distance to the nearest amenity
   (`gpd.sjoin_nearest`, EPSG:2263 feet).
3. A tract is "covered" iff that distance ≤ **2,640 ft** (≈ 10-min walk
   @ 3 mph) — the same cutoff as Chapter 3's park-access metric.
4. CD-level value = population-weighted mean of the tract coverage
   indicator (ACS B01003 total population as the weight). Range [0, 1].

A basket that bundles multiple amenity types takes the equal-weight mean
of its per-type coverage shares (weights stated per plan §9).

**On the threshold.** The chapter is framed around a **"10-minute city"**
— every daily need within a **10-minute, half-mile (2,640 ft) walk**.
This is deliberately a stricter cousin of the popular "15-minute city"
(≈3,960 ft / closer to a mile), and is the same cutoff Chapter 3 used
for park access, kept for cross-chapter consistency. Reporting
near-universal coverage at this tougher bar makes the "proximity is
already solved" finding stronger, not weaker; a 15-minute cutoff would
push coverage even higher and saturate the proximity maps further.

`proximity_mean` (the combined daily-needs score on the map) is the
equal-weight mean of the three basket values.

---

## 3. Food access basket

### Source
NYS Retail Food Stores (`9a8c-vfzj`, data.ny.gov), NYC counties only
(NEW YORK, KINGS, QUEENS, BRONX, RICHMOND). 11,472 stores at the
2026-06-01 snapshot.

### Filter
`square_footage ≥ 5,000 sq ft` → **1,367** full-service groceries. The
cutoff sits between a bodega and the NYC FRESH program's ~10k benchmark;
it is a coarse proxy for "full-service," not a measure of what's stocked.

### Cross-check
OSM `shop=supermarket` returns 1,347 — within ~1.5% of the NYS count,
which validates the source. OSM is a completeness check only; it is not
in the spine.

### Caveats
- ~23% of NYS rows have a null `square_footage` and are dropped from the
  supermarket set — a modest undercount.
- Square footage ≠ produce quality, price, or whether the store is open.

### Food *quality*: supermarket share ("a store is not a supermarket")
Proximity to a food store is not proximity to fresh produce. Per CD we
also compute the **share of food stores that are full-service groceries**
(≥ 5,000 sq ft) among stores with a reported size — `supermarket_share_pct`
in `facts.json` / the geojson. Citywide **15.9%** (≈ 5.3 small stores per
supermarket; 84% bodegas/corner stores). Most bodega-dominated CDs are
dense, lower-income inner neighborhoods — South Crown Heights (5.6%, 17:1),
**Belmont/East Tremont (7.0%, 13:1 — the chapter's best-childcare anchor)**,
Flatbush, Morrisania, Borough Park — *not* the outer-borough proximity
deserts, which skew toward supermarkets. External corroboration: NYS 2016
data aggregated by NYC DOHMH put the bodega-to-supermarket ratio at ~18:1
in the poorest neighborhoods vs ~3:1 on the Upper West Side (via Gothamist);
USDA's Food Access Research Atlas defines urban low access as > ½ mile to a
supermarket. This is the same proximity ≠ sufficiency gap, on food.

---

## 4. Care access basket

Equal-weight mean of three pop-weighted walk-access shares:

- **Pharmacies** — OSM `amenity=pharmacy` (1,260).
- **Childcare** — FacDB (`ji82-xba5`) `DAY CARE AND PRE-KINDERGARTEN`
  facility group (4,296 points: day care + DOE UPK + preschools).
- **Healthcare** — FacDB `HOSPITALS AND CLINICS` (1,280).

This basket is **proximity only**. The intended sufficiency component
(childcare slots per child) is *not* in it: FacDB's `capacity` column is
all-zero for the day-care group. Sufficiency is measured separately in
§6 from a different source.

---

## 5. Civic / learning basket

Equal-weight mean of three pop-weighted walk-access shares:

- **Schools** — OSM `amenity=school` (2,767).
- **Public libraries** — FacDB `PUBLIC LIBRARIES` (228 branches, all
  three systems: NYPL, BPL, QPL).
- **Parks ≥ 1 acre** — NYC Parks Properties (`enfh-gkve`), 867 parks
  (reused from Chapter 3).

---

## 6. Childcare sufficiency (the chapter's spine)

### The two-regulator problem
NYC childcare is split across two regulators, and a single source always
undercounts:

- **DOHMH** (NYC Health Code) regulates center-based care — dataset
  `gy3q-4tzp`. 2,726 centers, all under-5 (PRESCHOOL + INFANT TODDLER),
  **148,647 slots**.
- **OCFS** (NYS) regulates home-based family & group family day care —
  dataset `cb42-qumz`. Critically, OCFS lists **zero** day-care centers
  (DCC) in the five boroughs (they're DOHMH's), so OCFS contributes the
  home-based slots only: FDC + GFDC, active status (License /
  Registration), **98,244 slots** across 6,736 sites.

The two sets are disjoint → summing them does not double-count. Combined:
**246,851 licensed slots**.

### Denominator
Children under 5 per CD = ACS 2019–2023 table B01001, `B01001_003E`
(male under 5) + `B01001_027E` (female under 5), tract → CD via the
centroid join. Citywide: **498,130** children under 5.

### Metric
`childcare_slots_per_100_u5` = 100 × slots / children-under-5, per CD.
Slots are summed to CD by point-in-polygon (EPSG:2263). Citywide:
**49.6** slots per 100. Per-CD range **23.1 → 90.5** (≈ 3.9× spread);
median 47.1.

### Caveats
- **Slots are licensed capacity, not enrollment or affordability.** The
  ratio says nothing about open seats, cost, subsidy eligibility, hours,
  or quality.
- **OCFS home-based `total_capacity` includes some school-age care.** The
  under-5 age-breakdown columns are unusable in NYC (~1,468 slots
  populated citywide), so home-based capacity modestly overcounts true
  under-5 supply in home-based-heavy CDs.
- **Sufficiency is not a clean income story.** Brownsville (one of the
  poorest CDs) is starved (33/100); the equally low-income central Bronx
  is best-supplied (~90/100). The chapter measures the geography without
  claiming its mechanism.

---

## 6b. Combined daily-needs score (`daily_needs_score`)

A single within-chapter composite that requires *both* halves (per plan
§9: components named, equal weights stated, rationale structural).

- Rank all 59 CDs into a percentile on **proximity** (`proximity_mean`)
  and on **sufficiency**, where sufficiency = the percentile of
  (`childcare_slots_per_100_u5` rank + `supermarket_share_pct` rank).
- Score = **geometric mean** of the two percentiles × 100.

**Why multiplicative, not additive.** Additive (a weighted average) lets
high proximity compensate for a childcare desert — exactly the substitution
the chapter argues against. The geometric mean (like `min()`) gates access
on whichever half is scarcer, so a low mark on either drags the score down.
This *reinforces* the thesis: it demotes the "walkable but starved" CDs that
a proximity-only ranking flatters — Central Harlem 1 → 24, East Harlem
11 → 44, Flatbush 30 → 57. Top: Upper West Side, Lower East Side, Fort
Greene (high on both). Bottom: Tottenville, Ridgewood (low on both / starved).

**Caveat.** "Sufficiency" here is only childcare seats + supermarket share —
the two capacity/quality measures the chapter has. Care and civic have no
sufficiency measure, so the score leans on childcare and food. Shipped as a
*secondary* view; the quadrant map stays the headline because it preserves
*which* half fails. A cross-chapter livability score is reserved for Ch. 9.

---

## 6c. Growth / gentrification — tested, rejected

Hypothesis: low childcare sufficiency is driven by neighborhood **growth**
(often gentrification) — new young-family demand outrunning a slow-growing
seat supply. Tested, does not hold. Not wired into the chapter; documented
here because a rejected hypothesis is worth recording.

**Method.** Population + children under 5 per census tract, **2010**
(`dec/sf1`, table P12) and **2020** (`dec/dhc`, table P12), five NYC
counties. Each year's tracts assigned to CDs by their own
cartographic-boundary centroid — the *same* method both vintages, so
2010↔2020 tract-boundary changes don't bias the CD-level change.
Calibration: citywide +8.3% (census actual ≈ +7.7%). Reproduce:
`analyses/chapter-04/growth_check.py` (needs `CENSUS_API_KEY`).

**Result (Spearman, n = 59):**

| pair | ρ |
|------|---:|
| population change 2010→2020 ↔ childcare sufficiency | **−0.09** |
| under-5 change 2010→2020 ↔ childcare sufficiency | **−0.24** |

Population growth is unrelated to sufficiency; under-5 growth shows only a
weak negative tilt — and that tilt is partly *definitional* (sufficiency is
seats per child, so a growing child population mechanically lowers it). Two
facts kill the causal story:

- **The fastest-growing districts are well-supplied, not starved.** FiDi /
  Battery Park (+90% population, 79 seats/100), Chelsea / Hell's Kitchen
  (+35%, 75), Fort Greene (+33%, 53). Growth coincided with *more* childcare.
- **The starved districts are mostly losing young children, not gaining
  them.** Ridgewood −17% under-5, Flatbush −17%, East Harlem −16%, Central
  Harlem −13%, Elmhurst −9% — falling under-5 counts yet still few seats.
  Their shortfall is a *supply* story (seats never built / shrinking), not a
  demand surge.

So growth *demotes* these districts on the combined score (§6b) but doesn't
*cause* the childcare gap. Combined with §6's income finding, this is why the
chapter stays agnostic on mechanism: sufficiency is its own geography, and the
two obvious explanations — income and growth — both fail to predict it.

---

## 7. Anchor CDs

| CD | Neighborhood | Boro | Role | Proximity rank | Slots/100 u5 |
|---|---|---|---|---:|---:|
| 405 | Ridgewood / Maspeth | QN | cold open — close but starved | 48 | 23.1 (worst) |
| 316 | Brownsville | BK | kills the income explanation | 16 | 32.8 |
| 112 | Washington Heights / Inwood | MN | close & sufficient | 17 | 80.7 |
| 206 | Belmont / East Tremont | BX | best-supplied (series surprise) | 25 | 89.8 |
| 503 | Tottenville / Great Kills | SI | the genuine errand desert | 59 (worst) | 23.9 |

---

## 8. Data vintages + reproducibility

| Source | Dataset | Vintage |
|---|---|---|
| NYS Retail Food Stores | 9a8c-vfzj | 2026-06-01 snapshot |
| DOHMH childcare centers | gy3q-4tzp | 2026-06-01 snapshot |
| OCFS childcare | cb42-qumz | 2026-06-01 snapshot |
| NYC Facilities Database | ji82-xba5 | 2026-06-01 snapshot |
| OSM (supermarkets/pharmacies/schools) | Overpass | 2026-06-01 snapshot |
| NYC Parks Properties | enfh-gkve | 2026-06-01 snapshot |
| ACS (B01003 pop, B01001 under-5) | 2019–2023 5-yr | — |
| Community Districts | 5crt-au7u v26a | — |

Every cached file has a `cache/MANIFEST.json` entry (source URL, fetch
timestamp, SHA-256, byte size).

---

## 9. Pipeline modules

- `pipelines/nys_food_stores.py` — NYS Retail Food Stores, NYC slice.
- `pipelines/nyc_facdb.py` — FacDB, by `facsubgrp` or `facgroup`.
- `pipelines/nyc_childcare.py` — DOHMH centers + OCFS home-based.
- `pipelines/osm_overpass.py` — supermarkets / pharmacies / schools.
- `pipelines/nyc_parks.py` — NYC Parks Properties (Ch. 3).
- `pipelines/acs_census.py` — B01003, B01001.

---

## 10. Changelog

- 2026-06-06 — Three proximity baskets + childcare sufficiency built;
  proximity ≠ sufficiency framing locked; headline geojson + SVG
  rendered.
