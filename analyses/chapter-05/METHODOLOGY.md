# Chapter 5 — Public Space & Urban Experience · Methodology

Working title: **"Pay to Belong."** Every number in the published chapter
reproduces from `analyses/chapter-05/notebook.py` against the pinned
`MANIFEST.json` (`make chapter-5`). This file is the full per-chapter
reference; the chapter prose is a renderer of `out/facts.json`.

## The headline question

How much of a neighborhood's public life is **free** versus **paid**, per
resident — and do the two go together? Answer: they don't. Across the 59
residential community districts, paid social space and free public space
rank-correlate at **Spearman ρ = +0.05** — statistically independent.

## Datasets (snapshot 2026-06-01)

| Role | Source | Dataset / query | Filter |
|------|--------|-----------------|--------|
| Paid — eateries | OpenStreetMap (Overpass) | `amenity in (restaurant, cafe, bar)` | NYC bbox; **`fast_food` excluded** |
| Paid — cultural | OpenStreetMap (Overpass) | `amenity in (theatre, arts_centre)`, `tourism in (museum, gallery)` | NYC bbox |
| Free — parks | NYC Parks Properties | Socrata `enfh-gkve` | official `acres ≥ 1` |
| Free — plazas | NYC DOT Pedestrian Plazas | Socrata `k5k6-6jex` | all (93) |
| Free — libraries | NYC Facilities Database (FacDB) | Socrata `ji82-xba5`, `facsubgrp = 'PUBLIC LIBRARIES'` | all (228 branches) |
| Population | ACS 2019–2023 5-year | `B01003` (tract) | NYC counties |
| Geography | NYC DCP Community Districts | `5crt-au7u` (59 residential CDs) | drop JIAs/parks-as-CD |

Counts at this snapshot: 13,846 eateries + 1,032 cultural venues (paid);
867 parks ≥ 1 acre + 93 plazas + 228 libraries (free).

## Geography & population

- Spatial math in **EPSG:2263** (NY Long Island State Plane, feet); output
  reprojected to **EPSG:4326**.
- Each amenity is assigned to the CD that contains its representative point
  (`geopandas.sjoin`, `within`).
- CD population = sum of tract `B01003_001E` over tracts whose
  representative point falls in the CD (22 of 2,325 tracts are water/edge
  and unassigned).

## Metrics

Both axes are **per-capita supply** measures (the Ch. 4 *proximity ≠
sufficiency* move applied to public space), counted as **places per 1,000
residents** so the two are directly comparable:

- **Paid sociability** = (eateries + cultural venues) ÷ population × 1,000.
- **Free public space** = (parks ≥ 1 acre + plazas + libraries) ÷
  population × 1,000.

Each district is placed in a 2×2 split at the **citywide medians**
(paid 0.84/1k; free 0.126/1k): *pay to belong* (high paid, low free),
*free to be* (low paid, high free), *rich in both*, *thin on both*.
Distribution: 15 / 15 / 15 / 14.

## Why a place-count, not acreage

Free space mixes outdoor area (parks, plazas) with an indoor amenity that
has no meaningful acreage in the data (libraries). Counting discrete
**places** keeps the unit consistent and parallel to the paid axis
("for every place you pay to be in, how many are free?"). Trade-off: a
500-acre park and a pocket plaza each count once, so the measure rewards
*number of free places*, not room. An acreage-weighted view is retained in
`facts.json` (`headline.restorative_acres_footnote`).

## Spine history (why this framing)

Following the series kill test (|ρ| ≥ 0.75 collapses an axis): the original
**three-basket walk-access spine** (open space / street vitality /
pedestrian realm, each a 10-min-walk %) **fired** — vitality ~ pedestrian
realm at **ρ = +0.79** — because every walk-access metric restates
population density. Re-spec'd to per-capita supply; the **paid-vs-free**
split survives at ρ = +0.05.

## What the measure misses (chapter caveats; full list in Ch. 10)

- **Counts doors, not hours or welcome.** A library open till 9 and one
  closing at 5 each count once; the *restriction* story (library hours,
  park curfews ~1 a.m., POPS hostile design / anti-vagrancy enforcement)
  is real and **unmeasured** here — the count is a ceiling on free access.
- **Place-count flattens size** (see above).
- **Per resident, not per visitor** — flatters near-empty Midtown,
  is hard on dense districts.
- **OSM completeness varies** by neighborhood; free places come from
  authoritative city layers. Sub-1-acre parks and POPS outside the plaza
  dataset are undercounted. Pedestrianized streets (Open Streets,
  `uiay-nctu`) are noted but not folded into the free count.
- **Straight CD aggregation** hides block-scale variation.

## Reproduce

```bash
make venv && make geographies         # one-time (CENSUS_API_KEY in .env)
python analyses/chapter-05/notebook.py
make publish CHAPTER=5                 # -> personal-website/public/.../chapter-05/
```
