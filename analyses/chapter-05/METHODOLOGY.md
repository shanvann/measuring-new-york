# Chapter 5 — Public Space & Urban Experience · Methodology

Working title: **"Pay to Belong."** Every number in the published chapter
reproduces from `analyses/chapter-05/notebook.py` against the pinned
`MANIFEST.json` (`make chapter-5`). This file is the full per-chapter
reference; the chapter prose is a renderer of `out/facts.json`.

## The headline question

How much of a neighborhood's public life is **free** versus **paid**, per
resident — and do the two go together? Answer: they don't. Across the 59
residential community districts, paid social space and free public space
rank-correlate at **Spearman ρ = −0.21** — all but independent (weak, slightly negative).

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
sufficiency* move applied to public space):

- **Paid sociability** = (eateries + cultural venues) ÷ population × 1,000
  — paid third *places* per 1,000 residents.
- **Free open space** = (park + plaza **acres**) ÷ population × 1,000 — with
  **big parks (≥ 40 acres) credited to every residential CD they border**
  (full acreage, an *access* measure; ~100 ft buffer catches across-the-
  street adjacency). Small parks and plazas are assigned to the CD
  containing their representative point.

Each district is placed in a 2×2 split at the **citywide medians**
(paid 0.84 places/1k; free 6.10 acres/1k): *pay to belong* (high paid, low
free), *free to be* (low paid, high free), *rich in both*, *thin on both*.
Distribution: 16 / 16 / 14 / 13.

## Why acreage (and adjacency), not a place-count

An earlier draft counted free *places* per resident. It failed the reality
test: crediting Central Park to the Upper East Side as one more "place"
barely moved a district of 200,000+ people, leaving the UES looking
free-poor when residents are a five-minute walk from a world-class park.
Acreage fixes that — Central Park's ~840 acres, shared across the UES, is a
real (if below-median) amount of free space. And because big parks serve
the neighborhoods *around* them (Central Park is its own non-residential
district, 164, and otherwise credits to no one), each is credited to every
bordering CD. **Libraries** have no acreage and can't move a dense
district's per-capita supply, so they are reported separately
(`headline.free.libraries_per1k_range`) and carry the chapter's "free but
restricted" thread rather than entering the headline axis.

## Spine history (why this framing)

Following the series kill test (|ρ| ≥ 0.75 collapses an axis): the original
**three-basket walk-access spine** (open space / street vitality /
pedestrian realm, each a 10-min-walk %) **fired** — vitality ~ pedestrian
realm at **ρ = +0.79** — because every walk-access metric restates
population density. Re-spec'd to per-capita supply; the **paid-vs-free**
split survives at ρ = −0.21.

## What the measure misses (chapter caveats; full list in Ch. 10)

- **Adjacency ≠ access.** Crediting a big park to every bordering district
  is closer to reality than one-CD assignment, but a park across a six-lane
  arterial or behind a highway isn't truly usable; the measure rewards being
  *next to* a big park, not being able to safely walk into it.
- **Acres ≠ hours or welcome.** A park counts the same open-late or fenced
  at dusk; the *restriction* story (library hours, park curfews ~1 a.m.,
  POPS hostile design / anti-vagrancy enforcement) is real and **unmeasured**
  here. Libraries sit outside the acreage entirely.
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
