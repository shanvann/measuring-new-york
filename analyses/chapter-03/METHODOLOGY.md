# Chapter 3 — *Breathing Room* · Methodology

Full per-metric reference for the chapter. The published chapter
(`personal-website/content/posts/measuring-new-york-03-environment.mdx`)
is the curated narrative; this file is the source-of-truth for every
number that appears there, with the exact dataset filters, geographic
aggregation rules, and known limitations.

Every number in the chapter reproduces from
`analyses/chapter-03/notebook.py` against the pinned `MANIFEST.json`.
This document describes the *what* and *why*; the notebook is the
*how*.

---

## 1. Spine + kill test

The chapter measures three semi-independent dimensions of environmental
experience and applies the series-wide kill test (|ρ| ≥ 0.75 between
any pair collapses the dimension).

| Pair | Spearman ρ | Fires kill? |
|---|---:|---|
| Air ↔ Park access | +0.432 | no |
| Air ↔ Env-311 | +0.625 | no |
| Park access ↔ Env-311 | +0.174 | no |

Spine survives → chapter ships as 3-dimensional.

The kill test runs on one representative column per dimension:
- **Air** → `pm25_annual` (PM 2.5 µg/m³, annual mean). PM 2.5 ↔ NO2
  intra-dimension ρ = +0.840, so the chapter treats them as one
  dimension and uses PM 2.5 as the chronic-exposure canonical metric.
- **Park access** → `green_10min_pct`
- **Env-311** → `env311_addrs_per_1k_pop_per_yr` (distinct complaining
  addresses, see §4 below).

---

## 2. Air quality

### Source
NYC DOHMH Environmental Health Indicators dataset
([`c3uy-2p5r`](https://data.cityofnewyork.us/Environment/Air-Quality/c3uy-2p5r)),
snapshot 2026-06-01.

### Filter
`name IN ('Fine particles (PM 2.5)', 'Nitrogen dioxide (NO2)')`
AND `geo_type_name = 'CD'`
AND `time_period LIKE 'Annual Average %'`

For each pollutant, the chapter picks the latest Annual Average year
independently. Both PM 2.5 and NO2 land on **Annual Average 2023**.

### CD-level value
The DOHMH dataset publishes per-CD values directly (`geo_join_id` =
borocd). 2,655 CD-level rows total in the dataset across both
pollutants. No UHF42 → CD crosswalk needed; no spatial join needed.

### Reference
WHO 2021 annual-mean guideline: 5 µg/m³. Every NYC CD sits above it.

### Caveats
- **CD-level smoothing.** DOHMH interpolates a sparser sensor network
  with traffic-and-land-use covariates. A household within a
  quarter-mile of a truck route sees something different from the CD
  average.
- **PM 2.5 / NO2 collinearity.** ρ = +0.840 — the chapter treats them
  as one dimension. NO2 still appears in the data for reproducibility
  but isn't a separate spine column.

---

## 3. Park access (green-space)

### Source
NYC Parks Properties dataset
([`enfh-gkve`](https://data.cityofnewyork.us/City-Government/NYC-Parks-Properties/enfh-gkve)),
snapshot 2026-06-01. 2,058 polygons total at snapshot; every record
has `class = PARK`.

### Filter
`acres >= 1` (official acreage as published by NYC Parks, not derived
from polygon area).
Filter cuts the layer to **867 polygons totaling ~30,000 acres**.

### What's in vs. out

**In:** Central Park, Prospect Park, Inwood Hill, Fort Tryon,
Highbridge, the Riverside Park stretch, every neighborhood / community
/ flagship park ≥ 1 acre, larger playgrounds, nature areas. The High
Line counts (6.7 acres, DPR-mapped). A handful of DPR-managed
cemeteries (12 records) and historic-house grounds count.

**Out (size cutoff):** Triangles, plazas, and most community gardens
(typically sub-acre); narrow strip parks; small lots.

**Out (data scope):** Private parks (Stuyvesant Town's interior
courtyards); schoolyards outside the DPR system; NYCHA-managed open
space.

### Distance metric

**Straight-line, 2,640 ft** (= 0.5 mi = ~10 min @ 3 mph), measured in
EPSG:2263 (NY State Plane, feet).

For each NYC census tract, take its representative point (geographic
point guaranteed to lie within the tract polygon) and find the
distance to the nearest qualifying park polygon via
`geopandas.sjoin_nearest`. Distance = 0 if the centroid is inside a
park.

A tract is "covered" iff distance ≤ 2,640 ft.

### CD aggregation

Population-weighted mean of the binary tract coverage indicator,
weighted by ACS B01003 (Total Population) at the tract level. So
**Midtown (CD 105) reads 100%** because Central Park is within
half a mile of every Midtown-tract centroid, even though Midtown
itself doesn't contain a 1-acre park.

### Caveats
- **Conservative — under-counts.** A real walking-network distance
  (osmnx-routed around buildings) would be ~30% longer than straight-
  line, so this cutoff slightly under-counts coverage. Under-count is
  consistent across CDs so rankings hold; absolute levels read low.
- **Coarse tract weighting.** Within a tract some blocks are closer
  to parks than others; we treat the whole tract uniformly. A
  block-group or block-level pass would discriminate more, especially
  at CD edges.
- **Compressed at the ceiling.** 0.74 ≤ green_10min_pct ≤ 1.00 across
  the 59 CDs, mean 0.98. The metric discriminates clearly at the
  green-poor end (south Brooklyn, southeast Queens) but flattens near
  the top. A tighter cutoff (5 acres, or a network-walk isochrone)
  would spread the upper distribution further. The bottom-of-the-
  distribution finding is robust to either change.
- **The 1-acre cutoff is editorial.** A no-cutoff version would push
  citywide coverage even higher; a 5-acre version would discriminate
  more in dense neighborhoods. The 1-acre choice maps to "a real
  park, not a triangle" without being so strict it kills small but
  meaningful neighborhood parks.

---

## 4. Civic noise / env-311

### Source
NYC 311 Service Requests
([`erm2-nwe9`](https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2010-to-Present/erm2-nwe9)),
snapshot 2026-06-01.

### Window
**2024-01-01 to 2026-06-01** (28 months). Post-pandemic baseline;
2020–2022 is excluded because lockdown noise patterns distorted both
the residential-complaint volume and the dirty-conditions baseline
relative to steady-state.

### Buckets

Server-side aggregated per zip code via Socrata GROUP BY:

| Bucket | SoQL filter |
|---|---|
| noise | `complaint_type LIKE 'Noise%'` |
| rodent | `complaint_type = 'Rodent'` |
| dirty | `complaint_type IN ('Dirty Condition', 'Illegal Dumping', 'Sanitation Condition')` |
| idair | `complaint_type IN ('Air Quality', 'Illegal Idling', 'Idling')` |

The `idair` bucket is included deliberately despite the coupling risk
with the air dimension. The kill test confirmed it didn't fire.

### **Primary metric: distinct complaining addresses per 1k pop per yr**

This is the chapter's central methodological move. **Counting calls,
not blocks, lets a small number of chronic-caller addresses dominate
the ranking** — the worked example is zip 10466 (Wakefield, Bronx),
which alone accounts for ~11% of NYC's noise-complaint volume,
97% of it the descriptor *Loud Music/Party*, with a single address
inside the zip responsible for about 13% of the zip's calls
([Haejin Son's independent analysis](https://medium.com/@haejinson0704/the-hidden-patterns-in-ny-311-noise-complaints-4efdbc0ed6e3)
documents the same pattern from a different angle).

Under the call-rate metric, CD 212 Williamsbridge would land at 572
calls / 1k / yr — ~3× the next CD. Under the distinct-address rate,
CD 212 drops to 18.0 addrs / 1k / yr, rank 37/59 — below the city
median. The South Bronx ranking dissolves.

The metric switch was *structural*, not ad-hoc capping:
`SELECT incident_zip, count(distinct incident_address) AS addrs`,
one GROUP BY per bucket. Raw call counts are kept alongside in
`facts.json` for reproducibility.

### CD aggregation

Zip-level distinct-address counts are allocated to CDs through the
**area-weighted zip → CD crosswalk** (`geographies/zip_cd_crosswalk.csv`,
introduced in Chapter 2). Each zip's allocated value to a CD =
zip-total × overlap-area-share.

Rate per 1k pop per yr = (allocated addresses) ÷ (CD pop) × 1000 ÷
(window-years), where window-years = (end - start days) / 365.25.

### Caveats

- **Behavior, not exposure.** The metric counts how many addresses on
  a block bother to call 311 about environmental conditions, *not*
  how loud the block actually is or how dirty its sidewalks are. A
  neighborhood with many lightly-annoyed neighbors reads higher than
  a neighborhood with one chronic acoustic problem. This is the
  chapter's central editorial framing on the third dimension.
- **Allocation is area-weighted, not population-weighted.** Where a
  zip straddles a residential CD and a non-residential one (parks,
  industrial waterfront), allocated values can over-credit the
  non-residential side. The chapter footnotes this in the broader
  zip-CD crosswalk methodology. Magnitude of the effect at the CD
  level: typically < 5% of allocated volume.
- **`idair` bucket is collinear with the air dimension** by construction.
  Volume is small (~10k complaints / 28 months citywide) so it
  doesn't move the spine even at full inclusion; kill test confirms.
- **Window excludes pre-2024.** Steady-state rate is intended. A
  before / after 2020 comparison is a sibling analysis, not in this
  chapter.

---

## 5. Residential density (aliveness floor)

### Source
ACS 2019–2023 5-year, table
[B01003](https://www.census.gov/data/developers/data-sets/acs-5year.html)
(Total Population), retrieved at tract level for NYC's five counties
(Bronx, Kings, NewYork, Queens, Richmond).

NYC DCP Community Districts geometry
([`5crt-au7u`](https://data.cityofnewyork.us/City-Government/Community-Districts/5crt-au7u),
version 26a).

### CD pop
Sum of tract-level B01003_001E across tracts assigned to each CD via
centroid sjoin (`tract_to_cd()` in the notebook). 22 of NYC's 2,325
tracts are unassigned (water / airport / JIA) and drop out — the
remainder cover all 59 residential CDs.

### CD area
Polygon area in EPSG:2263 (sqft) ÷ 27,878,400 → square miles.

### Density
`pop_per_sqmi = pop / area_sqmi`, rounded to nearest integer.

### Caveats
- **Residential only.** This is the *floor* of aliveness — the
  always-there baseline. The *ceiling* is daytime population
  (residents + workers + visitors), unmeasured in this chapter.
  Where the gap matters most is Midtown: its residential density
  is rank 28/59 (~45,500 / sq mi), but its daytime population is
  several times that. A proper daytime measure would pull worker
  counts from LEHD LODES Workplace Area Characteristics; deferred
  to Chapter 4 / Ch. 9 synthesis.
- **Aliveness ≠ burden ≠ livability.** The chapter argues these
  three are distinct: burden is exposure to environmental conditions;
  aliveness is occupancy; livability is whether the place sustains
  households. Density at +0.49 vs PM 2.5 confirms burden and
  aliveness travel together moderately, but the chapter treats them
  as separate concepts.

---

## 6. Anchor CDs

Five anchors, one per corner of the chapter's measurement space,
spanning all five boroughs (per STYLE_GUIDE §4):

| CD | Borough | Anchor role |
|---|---|---|
| 105 | MN | Stacked-burden peak (PM 2.5 #1, env-311 #2) |
| 112 | MN | Cold open + central inversion (lived experience) |
| 206 | BX | Surprise-finding anchor (metric switch dissolved its top-5 rank) |
| 311 | BK | Green-poor contrast (3rd-worst park access at 84%) |
| 503 | SI | Low-burden contrast (cleanest air, max parks, low complaints) |

Each anchor is selected against the data, not picked from a
provisional spec — see `PLAN.md` decision log for the rationale of
each (and the swap that didn't happen for CD 206 once the metric
switched).

---

## 7. Data vintages + reproducibility

| Source | Vintage | Notes |
|---|---|---|
| DOHMH air (PM 2.5, NO2) | Annual Average 2023 | Latest annual at 2026-06-01 snapshot |
| NYC Parks Properties | 2026-06-01 | 2,058 polygons, 867 ≥ 1 acre |
| NYC 311 | 2024-01-01 to 2026-06-01 | Post-pandemic baseline window |
| ACS B01003 | 2019–2023 5-yr | Per series freeze |
| NYC DCP CDs | Version 26a | NYC Open Data 5crt-au7u |
| Zip → CD crosswalk | Shipped Ch. 2 | Area-weighted, see Ch. 2 methodology |

Series freeze: `2026-06-01`. Every fetch filters
`<= '2026-06-01T00:00:00.000'` where applicable.

Run `python analyses/chapter-03/notebook.py` against the pinned
`cache/MANIFEST.json` to reproduce `out/facts.json`, `out/rankings.csv`,
and `out/pm25-annual.{svg,geojson}`.

---

## 8. Pipeline modules

| Module | Purpose |
|---|---|
| `pipelines/doh_air.py` | DOHMH air pollutant fetch |
| `pipelines/nyc_parks.py` | Parks Properties polygon fetch (new for Ch. 3) |
| `pipelines/three_one_one.py` | 311 fetch + env-bucket counts-by-zip + **distinct-addresses-by-zip** (the structural fix) |
| `pipelines/acs_census.py` | ACS table fetch (B01003 added for Ch. 3) |
| `shared/zip_to_cd.py` | Area-weighted ZIP → CD crosswalk (built in Ch. 2) |
| `shared/basemap.py` | CD / tract / NTA / MODZCTA geometry loader |

---

## 9. Changelog

| Date | Change |
|---|---|
| 2026-05-30 | Initial scaffold. Air dimension wired. |
| 2026-05-30 | NYC Parks pipeline built. Park-access dimension wired. |
| 2026-05-30 | Env-311 pipeline built. Initial metric = calls/1k pop/yr. |
| 2026-05-30 | Diagnosed CD 212 outlier — traced to zip 10466 chronic-caller pattern. |
| 2026-05-30 | **Metric switch.** Env-311 primary metric changed to distinct complaining addresses per 1k pop per yr. Raw call rate retained for reproducibility. CD 212 dropped from rank 1/59 to 37/59. Spine survived re-test. |
| 2026-05-31 | Residential density added as the chapter's aliveness floor (B01003 / CD area). |
