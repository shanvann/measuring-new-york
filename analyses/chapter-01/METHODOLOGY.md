# Chapter 1 — Mobility & Access · Methodology

Full per-metric reference for the chapter. The published chapter
(`personal-website/content/posts/measuring-new-york-01-mobility.mdx`)
is the curated narrative; this file is the source-of-truth for every
number that appears there, with the exact dataset filters, algorithmic
choices, and known limitations.

Every number in the chapter reproduces from
`analyses/chapter-01/notebook.py` against the pinned `MANIFEST.json`.
This document describes the *what* and *why*; the notebook is the
*how*.

---

## 1. Why 45 minutes?

**45 min is the headline cutoff for transit-access analysis.** Three reasons:

1. **Convention.** Academic transit-accessibility research (the U. Minnesota
   Accessibility Observatory's national accessibility reports, the
   Brookings Metropolitan Policy Program's job-access work) standardizes
   on 30 / 45 / 60-minute isochrones. 45 is the most commonly published
   "tolerable daily commute" cutoff. The Census ACS B08303 table itself
   uses a 45-min category break (35–44 vs 45–59).
2. **Empirical fit for NYC.** The NYC median commute is about 40 minutes
   one-way (ACS 2019–2023). 45 minutes captures the median commuter and
   the longer half of the distribution without extending so far that
   almost every CD reaches most of the city.
3. **Sweet spot for differentiation.** At 30 minutes, even Midtown can't
   reach outer Brooklyn — every CD looks small, the comparisons flatten.
   At 60 minutes, most of NYC is reachable from most of Manhattan — the
   comparisons flatten the other way. 45 sits in the band where Midtown
   reaches ~70% of NYC jobs and Rockaway reaches ~0.4%, which is the
   variance the chapter is built to surface.

Future chapters that revisit mobility (Ch. 8 on time-and-stress, Ch. 9 on
synthesis) will compute alternate cutoffs (30 / 60 / off-peak) for
comparison. The 45 isn't load-bearing in any one direction; it's a
defensible default.

---

## 2. Per-tract aggregation

Each NYC tract gets its own 45-minute isochrone, computed from the tract's
representative point. CD-level numbers are the **median** across the
tracts within that CD. Quartiles (Q1, Q3) are also reported per CD so
within-CD spread is visible.

This replaces a single-origin-per-CD approach (the obvious first try)
that produced misleading numbers for large CDs whose population centroid
lands far from the actual subway lines. Flushing's geographic centroid
is 0.81 miles from the 7 train terminal at Main St, even though Main St
itself is right there. Per-tract aggregation captures the lived
geography: some Flushing residents are right on the subway and have
great access; others are in Whitestone and have almost none.

NYC tracts are designed for roughly equal population (~4,000 residents
each), so an unweighted aggregation across tracts approximates a
population-weighted measure without needing explicit population weights.

---

## 3. The algorithm

Time-dependent Dijkstra over the GTFS schedule, with three edge kinds:

1. **Ride edges:** if you're on a trip at stop S sequence N, the next
   reachable node is the same trip at stop S' sequence N+1, with cost
   equal to scheduled ride time.
2. **Board edges:** at any stop visit at time T, you may board any trip
   departing within the next **20 minutes**. The next reachable stop on
   that boarded trip is added with cost = (wait + ride time).
3. **Walk-transfer edges:** walk between nearby stops (≤ 1,500 ft
   straight-line, with the standard ×1.4 detour factor at 3 mph, plus a
   0.5-min platform-change buffer).

Origin walks are handled separately: from each tract's centroid, all
subway stops within **1.0 mile** straight-line (the TCRP Synthesis 95
upper-bound subway-stop catchment) seed the priority queue with cost =
walk time.

The isochrone polygon is the union of walk-buffers around each reachable
stop, sized by the *remaining* minutes after arrival (so a stop
arrived-at with 30 of 45 min left contributes a 30-min walk circle),
plus an origin walk-circle sized by the full budget.

Implementation in `shared/isochrone.py` (~280 lines). Per-feed
precomputation runs in ~0.7 s; one isochrone runs in ~0.05 s; all 2,303
NYC tracts run in ~2 minutes on a laptop.

---

## 4. Mobility Access Score

**Definition.** A community district's Mobility Access Score is the
percentage of NYC's payroll jobs that the median tract in that CD can
reach in 45 minutes by subway and walking, departing Tuesday at 8 AM.

**Formula.**

```
For each tract t in CD c:
  jobs_reachable(t) = sum over NYC tracts u of:
                        area(isochrone(t) intersect u) / area(u)  *  LODES_jobs(u)

mobility_access_score(c) = round(
    median(jobs_reachable(t) for t in c) / TOTAL_NYC_JOBS * 100,
    1 decimal place
)
```

with `TOTAL_NYC_JOBS = 4,466,975` (LEHD LODES 2022 NY Workplace Area
Characteristics, sum of column C000 across the 25,279 NYC blocks with at
least one job).

**Variance qualifier.**

```
spread(c) = Q3(jobs_reachable(t) for t in c) / Q1(...)

variance_class(c) =
  "uniform"  if spread < 1.5
  "moderate" if 1.5 <= spread < 3
  "uneven"   if spread >= 3
```

**Worked example — South Ozone Park (CD 410):**

- 38 tracts in the CD
- For each: compute the 45-min isochrone, intersect with NYC tracts, sum
  LODES jobs (area-weighted)
- Sort the 38 values:
  - Q1 = 40,145
  - Median = 62,697
  - Q3 = 192,522
- Score: `62,697 / 4,466,975 × 100 = 1.4`
- Q3/Q1: `192,522 / 40,145 = 4.8` → ≥ 3 → **uneven**
- Final: **1 · uneven**

**Per-tier scores (computed but not surfaced in Chapter 1).** LODES
splits jobs into three earnings tiers — CE01 (monthly earnings ≤ $1,250),
CE02 ($1,251–$3,333), CE03 (≥ $3,334) — and the same algorithm above is
run per tier and stored on every CD feature in `job-access.geojson`
under `ce01_score`, `ce02_score`, `ce03_score` (normalized to NYC tier
totals: CE01 = 644,071; CE02 = 1,012,180; CE03 = 2,810,724). They're
shipped for the synthesis chapter (Ch. 9) to consume; Chapter 1 itself
doesn't surface them because LODES's top tier (`≥ $40K/yr`) is too
coarse to support a meaningful wage analysis for NYC. Finer-grained
wage resolution requires a BLS Occupational Employment Statistics
cross-walk and belongs in Chapter 7 (Economic Opportunity).

**Design choices and why.**

| Choice | Reason |
|---|---|
| Median across tracts (not mean) | Mean is pulled by the subway-rich corner of a CD; median is robust and describes the typical resident. |
| Q3/Q1 ratio for variance | Robust to tail outliers in either direction; symmetric multiplicative bands map naturally onto "almost flat" / "noticeably different" / "very different." |
| Thresholds 1.5 / 3 | Defensible breakpoints (≤50% spread / up to 3× spread / ≥3× spread). Produced a 18 / 25 / 16 distribution across 59 CDs — meaning the qualifier carries information rather than mostly bucketing everyone the same way. |
| % of all NYC jobs (not percentile rank) | Preserves absolute magnitude. A 33 in Williamsburg is *much* better than a 33 in a different metro would be; percentile rank would hide that. |
| Single dimension only | Series rule: no composite scores before Chapter 9. This is just mobility, clearly labeled, and Ch. 9 will combine it with seven other dimensions. |

**Distribution across all 59 CDs:** 18 uniform, 25 moderate, 16 uneven.
Best score: 68 (Midtown East, uniform). Worst score: 0.3 (Tottenville,
moderate).

---

## 5. Full caveats

The chapter's main text lists the three caveats that most materially
change how to read the headline numbers. The complete list:

1. **Buses are not in the model.** Roughly half of NYC transit trips
   include a bus leg. Adding the local + express bus network is the
   single most impactful improvement to make next. Current numbers
   should be read as "what does the subway alone offer," not "what does
   NYC transit offer."
2. **Schedule, not reality.** Scheduled GTFS doesn't capture delays,
   reroutes, planned-work closures, or service gaps. Chronically-delayed
   lines effectively narrow residents' real reach. Reliability variance
   gets a separate treatment in Chapter 8.
3. **One departure time, one day.** Tuesday 8 AM weekday only.
   Off-peak / weekend / late-night service runs differently — frequencies
   drop, some lines run shorter trains, some skip stops. A resident's
   *actual* week-spanning reach is a probability distribution, not a
   single number.
4. **No commuter rail (LIRR / Metro-North) and no Access-A-Ride.** The
   commuter rails are competitive with subway for some Queens and Bronx
   residents but require a different (and more expensive) fare structure.
   Access-A-Ride is a paratransit service with a fundamentally different
   access geometry.
5. **Walking is straight-line × 1.4.** A real OpenStreetMap walk graph
   would catch dead-end streets and missing bridges. In most NYC
   neighborhoods this approximation is within ±10% of the true network
   distance.
6. **The Staten Island Railway *is* in the feed**, but most SI residents
   live > 1 mile from any SIR stop, so SI numbers in this model are
   bleaker than the residents-within-the-railway's-catchment lived
   experience.
7. **A median is a median.** CD-level aggregation hides intra-CD
   variance, which is precisely the most-interesting-shaped artifact in
   the data. The variance qualifier (uniform/moderate/uneven) on the
   Mobility Access Score is the partial answer.
8. **A reachable job is not a take-able job, and not all reachable jobs
   are the same kind of job.** LODES counts every payroll job equally —
   a $40K teacher position equals a $400K hedge-fund seat in the shed
   total. LODES's three earnings tiers (CE01 ≤ $15K, CE02 $15–40K, CE03
   ≥ $40K) help at the bottom but the top tier is too coarse for NYC,
   where most jobs sit above $40K and the relevant variance is between,
   say, $60K and $200K. Finer-grained wage resolution requires a BLS
   Occupational Employment Statistics cross-walk against the LODES NAICS
   sector columns; that work belongs in Chapter 7 (Economic Opportunity).

---

## 6. Sources

- MTA GTFS Subway feed (snapshot 2026-06-01) — [new.mta.info/developers](https://new.mta.info/developers)
- LEHD LODES 8.0 NY Workplace Area Characteristics, 2022 — [lehd.ces.census.gov](https://lehd.ces.census.gov/data/lodes/LODES8/ny/)
- ACS 2019–2023 5-year tables B19013, B08303 — [census.gov](https://www.census.gov/data/developers/data-sets/acs-5year.html)
- NYC DCP Community Districts (`5crt-au7u`, version 26a) — [data.cityofnewyork.us](https://data.cityofnewyork.us/City-Government/Community-Districts/5crt-au7u)
- 2020 Census Tracts via NYC Open Data (`63ge-mke6`) — [data.cityofnewyork.us](https://data.cityofnewyork.us/City-Government/2020-Census-Tracts/63ge-mke6)

Notebook: [analyses/chapter-01](https://github.com/shanvann/measuring-new-york/tree/main/analyses/chapter-01).
