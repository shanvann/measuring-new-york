# Chapter 4 — Access to Daily Needs

Working plan + session status for Phase 3d. Lives alongside the chapter
notebook so the spec, the in-flight work, and the punch list are all in
one place. Authoritative chapter spec is `MEASURING_NEW_YORK_PLAN.md`
§10 in the website repo; this file is the data-repo working copy and
gets archived/promoted at the end of Phase 3d.

**Status of this file:** *pre-flight spec.* No data has been run yet —
unlike the Ch. 3 PLAN, the numbers below are targets and design
decisions, not results. The spine test has NOT been run. Decisions
marked **(open)** still need the user's call before the notebook locks.

## The angle

> **Livability is partly the absence of logistical friction.**
> (`measuring_livability.md` §5)

Every other chapter measures a *quality* of place — can you move (Ch. 1),
can you afford to stay (Ch. 2), is the air clean (Ch. 3). Chapter 4 flips
to **everyday logistics**: how much effort the ordinary errands of a
household take. Groceries, a pharmacy, a doctor, a school, childcare, a
park — within a short walk, or one car trip / long transit chain away?

The framing device is the **15-minute neighborhood**. The argument is
that the friction is *unequally distributed* — some CDs are amenity-dense
and some are "errand deserts" — and that the burden lands hardest on
**families** (childcare + schools + pediatric care stack on the same
household). Central question the chapter tests: **does proximity equal
sufficiency?** A dense, walkable CD can still be chronically under-supplied
(oversubscribed childcare, one pharmacy for the whole block).

## Spec

**Hypothesis (working).** A New Yorker's access to daily needs splits
into three semi-independent axes:

1. **Food access** — % residents within a 10-min walk of a full-service
   grocery / supermarket, pop-weighted. The "can you buy fresh food
   without a car" axis. Retail-economics + zoning driven.
2. **Care access** — pharmacies + childcare + healthcare. The "family /
   health logistics" axis. Licensing + health-system-siting + family-
   demand driven. Within-axis composite (components named + weighted in
   the decision log, per §9 of the plan).
3. **Civic / learning access** — schools + libraries + parks within a
   10-min walk, pop-weighted. The "public daily-life infrastructure"
   axis. Municipal-planning driven.

All three use the same access primitive: **% residents within a 10-min
walk (2,640 ft straight-line, ~3 mph) of the relevant amenity,
population-weighted to CD level** — reusing Ch. 3's green-space method
(`gpd.sjoin_nearest` in EPSG:2263 feet, B01003 pop weights). Where an
axis bundles multiple amenity types, each type gets its own walk-access
%, then the axis is the stated weighted mean.

**Kill criterion (mirrors Ch. 2 / Ch. 3).** If any pair of axes co-ranks
with |ρ| ≥ 0.75 (Spearman, n = 59 CDs), the spine collapses and the
chapter gets re-spec'd. Ch. 2's kill fired (filings↔HPD +0.82 → 2-axis);
Ch. 3's survived (max pair +0.625).

⚠ **Known kill risk — the density confound.** All three axes are
walk-access metrics, and walk-access correlates with built density
*everywhere*. There is a real chance two or three axes co-rank above
0.75 simply because dense CDs have more of everything within a 10-min
walk. **This is the analytic risk of the chapter and must be tested
first, before any visual work** (same discipline as Ch. 2/3). Fallback
re-spec if the basket axes collapse: switch the spine from *category
baskets* to *dimensions of access* —
  (a) **proximity** — walk-completeness across the full daily-needs
      basket;
  (b) **sufficiency** — supply per capita (childcare slots per child,
      stores per 1k residents), which a dense walkable CD can still fail;
  (c) **car-reliance** — the gap proximity leaves, proxied by % zero-
      vehicle households (ACS B08201/B25044) against errand-walkability.
This fallback measures *different forces* rather than three flavors of
the same density signal, so it is far more likely to survive the kill
test. Decide which spine ships only after running the test on real data.

**Anchor CDs.** Not picked yet. Following Ch. 2/3, anchors get chosen
after the spine test runs. Target shape: 5 anchors, one per borough,
including a "proximity ≠ sufficiency" surprise anchor (a dense CD that
looks walkable but is supply-starved) and a family-livability anchor.

**Headline visual — decide after spine test (LOCKED 2026-06-06).** Two
candidates, choose once we see how the axes spread (Ch. 3's green metric
compressed near 1.00 — watch for the same):
  - a **15-minute completeness score** choropleth — a within-chapter
    composite of the three axes (allowed under §9: components named,
    weights stated, grounded in the 15-min-city literature). Most
    legible as the "daily-needs access" headline.
  - the single **food-access** axis choropleth, if the composite
    compresses badly (Ch. 3's green metric clustered near 1.00 — watch
    for the same here).
Render following Ch. 2/3 `render_headline_choropleth` (sequential ramp,
5–95th pctile clip, 50-ft polygon simplification, display-CRS geojson
sibling for `<NycMap>`).

## Datasets

| Axis | Amenity | Source | Pipeline status |
|------|---------|--------|-----------------|
| Food | supermarkets/grocery | OSM `shop=supermarket` | ✅ `osm_overpass.QUERIES["supermarkets"]` wired |
| Food | grocery (authoritative) | NYS Retail Food Stores (`9a8c-vfzj`) | ❌ **new pipeline** — license data, store sq_ft, est. type; cross-check vs OSM |
| Care | pharmacies | OSM `amenity=pharmacy` | ✅ `osm_overpass.QUERIES["pharmacies"]` wired |
| Care | childcare | DOHMH Child Care / DOE pre-K, or NYS OCFS facilities | ❌ **new pipeline** — need slot counts for the sufficiency angle, not just sites |
| Care | healthcare | NYS Health Facility (`vn5v-hh5r`) / NYC clinics | ❌ **new pipeline** |
| Civic | schools | OSM `amenity=school` | ✅ `osm_overpass.QUERIES["schools"]` wired |
| Civic | libraries | NYPL/BPL/QPL branch locations (NYC Open Data) | ❌ **new pipeline** (small, static point set) |
| Civic | parks | NYC Parks Properties `enfh-gkve` | ✅ `pipelines/nyc_parks.py` (shipped Ch. 3) |
| (all) | total pop | ACS B01003 | ✅ `acs_census` (shipped Ch. 3) |
| fallback | zero-vehicle HHs | ACS B08201 / B25044 | ❌ add to `acs_census.TABLES` if fallback spine is used |
| fallback | children under 5 / school-age | ACS B01001 | ❌ add if childcare-per-child sufficiency metric is used |

Reusable infra already in place: `shared/isochrone.py` (Ch. 1 walk-
network walk-sheds — an upgrade path from straight-line if a draft wants
true network distance), `shared/zip_to_cd.py`, the EPSG:2263 projection
convention, `render_headline_choropleth` from Ch. 2/3.

## Decision log

- **Walk-access primitive = 10-min straight-line (2,640 ft), pop-
  weighted.** Reuse Ch. 3's exact method for cross-chapter consistency.
  Upgrade to `shared/isochrone` walk-network distance only if a draft
  needs it (Ch. 3 noted the same upgrade path and shipped straight-line).
- **Grocery: NYS license primary + OSM cross-check. (LOCKED 2026-06-06)**
  NYS Retail Food Stores (`9a8c-vfzj`, data.ny.gov) is authoritative and
  carries square-footage — lets us distinguish a full-service supermarket
  from a corner store, central to the "fresh food" claim. NYS is the
  spine source; OSM `shop=supermarket` is the completeness cross-check
  (report the count delta in the footer). Supermarket cut-off:
  **square_footage ≥ 5,000 sq ft** (first pass) — between a bodega and
  the city FRESH program's ~10k benchmark; revisit if it over/under-counts.
  New pipeline `pipelines/nys_food_stores.py`.
- **Care axis = equal-weight walk-access composite. (LOCKED 2026-06-06)**
  Mean of {pharmacy, childcare, healthcare} pop-weighted walk-access.
  Shipped proximity-only — the slot-sufficiency component was dropped
  from the axis because FacDB capacity is all-zero (see below); it
  becomes its own metric under the fallback spine instead.
- **Childcare = slots, not sites. (BLOCKED 2026-06-06)** FacDB
  (`ji82-xba5`) carries a `capacity` column but it is **all-zero for the
  day-care group** — usable as a facility count only. The
  proximity ≠ sufficiency thesis needs an OCFS (or DOE) slot source;
  not yet wired. This is the gating dependency for spine framing path (B).
- **Window / vintage.** Point datasets (OSM, NYS food, childcare,
  libraries, healthcare) pinned at the series snapshot 2026-06-01. ACS
  2019–2023 5-year. No time-series — daily-needs access is a stock, not
  a flow.
- **Spec scope.** Data-repo notebook docstring + this PLAN.md for now;
  promote to website-repo §10 once the spine test runs on all three axes
  (demote Ch. 3 spec — currently §10 is still pinned to **Ch. 2** and
  was never advanced for Ch. 3; that drift gets fixed in the same edit).

## Status

### Done
- **Spec + this PLAN drafted.** Chapter folder + `out/` scaffolded.
- **Notebook scaffold + spine-test harness** (`analyses/chapter-04/notebook.py`).
  Shared `pct_within_walk()` access primitive (reuses Ch. 3's method);
  axes 2/3 are typed stubs returning `None` so the harness reports
  partial coverage and defers the kill test until ≥2 axes are wired.
- **`pipelines/nys_food_stores.py`** — NYS Retail Food Stores
  (`9a8c-vfzj`, data.ny.gov), NYC slice. 11,472 NYC stores cached at
  2026-06-01 (3.9 MB, manifested). Fields corrected vs first draft:
  county is UPPERCASE, type field is `estab_type`, `square_footage`
  present on ~77% of rows.
- **Axis 1 (food) end-to-end.** % residents within 2,640 ft of a NYS
  grocery ≥ 5,000 sqft, pop-weighted. **1,367** qualifying groceries.
  Per-CD range **0.64–1.00**. Top (1.00): dense cores — CD 101 FiDi/BPC,
  209 Soundview, 302 Bklyn Heights, 303 Bed-Stuy, 305 East NY. Bottom:
  CD 502 South Beach/Willowbrook **0.64**, 503 Tottenville 0.66, 413
  Queens Village 0.69, 210 Co-op City/Throgs Neck 0.75, 501 St. George
  0.76 — the predicted outer-borough "errand deserts."
  - **OSM cross-check validates the source:** NYS 1,367 vs OSM
    `shop=supermarket` 1,347 — within ~1.5%.
  - ⚠ **Compression watch (as in Ch. 3 green):** many CDs sit at 1.00;
    the bottom ~10 carry the signal. Fine for the spine; revisit before
    a food-axis choropleth (tighter sqft cut, or count/­density instead
    of a 0/1 coverage indicator).
  - ⚠ **Null-footage undercount:** ~23% of NYS rows have null
    `square_footage` and are dropped from the supermarket set — footer note.

- **Axis 3 (civic/learning) end-to-end.** Equal-weight (1/3 each) mean
  of pop-weighted walk-access to **schools** (OSM `amenity=school`,
  2,767), **public libraries** (FacDB `PUBLIC LIBRARIES`, all 3 systems,
  228), and **parks ≥ 1 acre** (`nyc_parks`, 867 — reused from Ch. 3).
  Per-CD range **0.64–1.00**. Top: Manhattan CDs (109, 107, 110, 105,
  103) at 1.00. Bottom: SI 503 **0.64**, SI 502 0.65, Queens 410 South
  Ozone Park 0.75, SI 501 0.75. New pipeline `pipelines/nyc_facdb.py`
  (parameterized by `facsubgrp` — reusable for axis-2 childcare/health).
- **New pipeline `pipelines/nyc_facdb.py`.** FacDB `ji82-xba5`,
  parameterized by `facsubgrp`. Note: FacDB's GeoJSON export ships a
  null `geometry` member, so the loader builds points from the
  `latitude`/`longitude` property columns. Carries `capacity` (the
  hook for axis-2 sufficiency metrics).

- **Axis 2 (care) end-to-end.** Equal-weight mean of pop-weighted walk-
  access to **pharmacies** (OSM `amenity=pharmacy`, 1,260), **childcare**
  (FacDB DAY CARE AND PRE-KINDERGARTEN group — day care + DOE UPK +
  preschools, 4,296), and **hospitals & clinics** (FacDB, 1,280). Per-CD
  range **0.47–1.00** — the widest-spread axis. Worst: SI 503
  Tottenville **0.47** (a genuine care desert), Queens 413 0.62, Queens
  411 Bayside 0.66.
  - ⚠ **Proximity only.** The intended *sufficiency* metric (childcare
    slots per child under 5) is NOT in this axis: FacDB `capacity` is
    **all-zero** for the day-care group, so we can count facilities but
    not slots. Slot-sufficiency is deferred to an **OCFS source** and
    feeds the dimensions-of-access fallback spine, not this axis.
  - FacDB pipeline generalized to fetch by `facgroup` (childcare spans
    3 subgroups) as well as `facsubgrp`.

### Full spine test (2026-06-06, n = 59, all 3 axes)

Spearman ρ (computed as Pearson-of-ranks — no scipy dependency):

| pair | ρ | fires kill? |
|------|---|-------------|
| `food_10min_pct` ↔ `care_10min_pct`  | **+0.733** | no (barely) |
| `care_10min_pct` ↔ `civic_10min_pct` | **+0.743** | no (barely) |
| `food_10min_pct` ↔ `civic_10min_pct` | +0.647 | no |

**Spine survives — but it is fragile.** Two of three pairs sit within
0.02 of the 0.75 kill threshold. This is the density confound nearly
firing: all three baskets are walk-access metrics and dense CDs have
more of everything nearby, so the axes are *nearly collinear*. They
clear the formal bar but they are not telling three independent stories.

**Editorial implication (proposed).** Don't sell the chapter as "three
independent axes of daily-needs access" — at ρ ≈ 0.74 that overstates
their independence. Lead instead with the chapter's real tension,
**proximity ≠ sufficiency**: proximity is largely one density signal
(this spine), and the *interesting* variation is in supply-per-resident,
which density does NOT guarantee. That reframing turns the borderline
spine result into the chapter's argument instead of a footnote — and it
makes building the OCFS childcare-slot sufficiency metric the headline
work, not optional. **Decision for the user** (see Open section).

Both proximity axes also **compress near 1.00** (Manhattan saturates),
same as Ch. 3 green — the bottom ~10 CDs carry the signal.

Worst overall daily-needs access (mean of 3 axes): SI 503 Tottenville
0.59, SI 502 South Beach 0.68, Queens 413 Queens Village 0.69, Bronx
210 Co-op City 0.76, SI 501 St. George 0.77 — a clean outer-borough
errand-desert story, candidate anchors.

### Next session (build order)
1. **Notebook scaffold** (`analyses/chapter-04/notebook.py`) following
   Ch. 3: full spec docstring, three axes wired to stubs, spine test
   harness that prints the 3×3 Spearman matrix + kill verdict.
2. **Axis 1 (food)** end-to-end first — it reuses the most existing
   infra (OSM supermarkets + Ch. 3 walk method). Get one axis ranking
   59 CDs before building the others, to de-risk the method.
3. **NYS Retail Food Stores pipeline** + grocery cross-check.
4. **Axis 3 (civic)** — schools (OSM) + parks (`nyc_parks`, reused) +
   libraries (new small pipeline).
5. **Axis 2 (care)** — the heaviest lift (childcare slots + healthcare
   pipelines). Build last; it's where the new-data risk concentrates.
6. **Run the spine test.** If it survives → pick anchors, build headline.
   If it fires → switch to the dimensions-of-access fallback spine and
   re-run before any visual work.

### Framing decision — PROXIMITY ≠ SUFFICIENCY (LOCKED 2026-06-06)

The chapter re-centers on **proximity vs sufficiency** (path B), not on
three independent baskets. Rationale: the basket spine is nearly
collinear via density (ρ ≈ 0.74), so presenting it as three independent
axes would overstate. Instead:

- **Proximity** = the 3-basket walk-access composite already built
  (food + care + civic). Disclosed as largely *one density signal*.
- **Sufficiency** = supply per resident, which density does NOT
  guarantee: childcare **slots per child under 5** (OCFS), hospital
  **beds / clinic capacity per capita**, grocery **sqft per capita**.
- **Headline visual** = a **proximity-vs-sufficiency scatter** — which
  CDs are both walkable *and* well-supplied, and which are walkable but
  starved (the chapter's surprise quadrant).

### Open / needs user decision
- **Childcare sufficiency source (gating).** FacDB capacity is all-zero;
  need NYS OCFS (or DOE) slot/capacity data. This is the next build and
  the gating dependency for the locked framing.
- Sufficiency denominators: confirm ACS tables — children under 5
  (B01001), and whether to add a beds/capacity source for healthcare.
- Anchors: confirm the outer-borough errand-desert set + at least one
  "walkable but supply-starved" surprise anchor once sufficiency lands.

## Punch list — next session(s)
1. Write `notebook.py` scaffold + spine-test harness.
2. Wire axis 1 (food) end-to-end; sanity-check the 59-CD ranking.
3. Build NYS food / childcare / healthcare / libraries pipelines (+
   `MANIFEST.json` entries, SHA-256 + fetch timestamps per repo convention).
4. Run spine test; record the 3×3 matrix + verdict here (mirror Ch. 3's
   "Spine test result" block).
5. Pick 5 anchors (1/borough; include a proximity≠sufficiency surprise
   anchor + a family-livability anchor).
6. Render headline visual + sibling CD-level geojson for `<NycMap>`.
7. Promote spec to website-repo §10 (demote Ch. 2 → archived; Ch. 3 too).
8. Draft chapter MDX, 11-section template per STYLE_GUIDE §2, with a
   `<MethodologyFooter>` carrying the "what this measure misses" notes.

## What this measure misses (for the MethodologyFooter)
- **Proximity ≠ quality or affordability.** A supermarket within 10 min
  says nothing about its prices or produce; a bodega is not a grocery.
  The NYS sqft cut-off is a coarse proxy, not a quality measure.
- **Straight-line ≠ walk-network.** 2,640 ft as the crow flies ignores
  rivers, highways, and dead-ends (same caveat as Ch. 3 green-space).
- **OSM completeness varies** by borough and amenity type; cross-checked
  against authoritative city/state datasets where one exists.
- **Sites ≠ capacity.** A childcare center near you may have a 2-year
  waitlist; the sufficiency axis tries to capture this but slot data is
  imperfect.
- **CD geography hides intra-CD deserts** — a CD can score "accessible"
  on average while a corner of it is a true desert (the same intra-CD
  variance Ch. 1 surfaced with per-tract isochrones).

## Vintage pins (target — confirm in `MANIFEST.json` when fetched)

| Source | Vintage | Notes |
|--------|---------|-------|
| OSM POIs | 2026-06-01 snapshot | supermarkets/pharmacies/schools/parks |
| NYS Retail Food Stores | latest at snapshot | `9a8c-vfzj`; carries est. sqft |
| Childcare (OCFS/DOHMH) | latest at snapshot | needs slot/capacity counts |
| Healthcare facilities | latest at snapshot | NYS `vn5v-hh5r` or NYC equivalent |
| Libraries | latest at snapshot | NYPL/BPL/QPL branches |
| NYC Parks | 2026-06-01 | `enfh-gkve` (reused from Ch. 3) |
| ACS | 2019–2023 5-year | B01003; +B01001/B08201 if fallback spine used |
