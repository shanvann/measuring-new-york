# Chapter 5 — Public Space & Urban Experience

Working plan + session status for Phase 3e. Lives alongside the chapter
notebook so the spec, the in-flight work, and the punch list are all in
one place. Authoritative chapter spec is `MEASURING_NEW_YORK_PLAN.md`
§10 in the website repo; this file is the data-repo working copy and
gets archived/promoted at the end of Phase 3e.

**Status of this file:** *pre-flight spec.* No data has been run yet —
like the Ch. 4 PLAN at its kickoff, the numbers below are targets and
design decisions, not results. The spine test has NOT been run.
Decisions marked **(open)** still need the user's call before the
notebook locks.

## The angle

> **Cities are lived in public.**
> (`measuring_livability.md` §6)

The prior chapters measure whether you can *get to* things — move (Ch. 1),
afford to stay (Ch. 2), breathe (Ch. 3), run the household errands
(Ch. 4). Chapter 5 measures the *quality of being out in the city itself*:
the parks and plazas you linger in, the street life you walk past, the
pedestrian realm you move through. The argument is that **public-realm
quality is unequally distributed** — some CDs are rich in places to *be*,
others are pass-through zones — and that this gap shapes the softer
livability themes the series has been building toward: spontaneity,
social cohesion, urban vitality, loneliness vs. community.

The framing device is **the public realm as a third place** — the space
that is neither home nor work where city life actually happens.

## Spec

**Hypothesis (working).** A New Yorker's public-realm experience splits
into **three semi-independent axes** (the "three baskets of public
life"):

1. **Open space** — % residents within a 10-min walk of a park (≥ 1 acre)
   or a public plaza, pop-weighted. The "places to gather / rest" axis.
   Parks-siting + DOT-plaza-program driven.
2. **Street vitality** — eateries (restaurants/cafés/bars) + cultural
   venues, as a pop-weighted walk-access composite. The "street life /
   things to do" axis. Retail-economics + cultural-siting driven.
3. **Pedestrian realm** — sidewalk generosity + pedestrianization
   (Open Streets + pedestrian plazas/streets) within a 10-min walk,
   pop-weighted. The "quality of the walking environment" axis.
   DOT-program + street-design driven.

All three reuse Ch. 3/4's access primitive: **% residents within a
10-min walk (2,640 ft straight-line, ~3 mph) of the relevant amenity,
population-weighted to CD level** (`pct_within_walk` in EPSG:2263 feet,
B01003 pop weights). Where an axis bundles multiple amenity types, each
type gets its own walk-access %, then the axis is the stated weighted
mean (within-chapter composite per plan §9).

**Boundary with prior chapters (important — parks were already used).**
Parks appeared as Ch. 3's green-space axis and inside Ch. 4's civic
basket. Chapter 5 is *not* re-telling the green-space story. Parks here
are one input to **open space** (paired with plazas), framed as
*gathering* space, not environmental/green benefit. The chapter's center
of gravity is the two genuinely new lenses — **street vitality** and the
**pedestrian realm** — which no prior chapter measured. If review finds
axis 1 is just Ch. 3 green-space again, drop bare parks and lead open
space with plazas + park *entrances within walkable street network*.

**Kill criterion (mirrors Ch. 2/3/4).** If any pair of axes co-ranks
with |ρ| ≥ 0.75 (Spearman, n = 59 CDs), the spine collapses and the
chapter gets re-spec'd. Ch. 2's kill fired (filings↔HPD +0.82 → 2-axis);
Ch. 3's survived (max +0.625); Ch. 4's *barely* survived (+0.733 /
+0.743) and got reframed to proximity ≠ sufficiency anyway.

⚠ **Known kill risk — the density confound (acute here).** Every axis is
a walk-access metric, and walk-access tracks built density *everywhere*.
This is the SAME risk that nearly killed Ch. 4 (ρ ≈ 0.74) — and it is
**worse** for Chapter 5, because public space, eateries, cultural venues,
*and* generous sidewalks all concentrate in the same dense, high-foot-
traffic cores. There is a real chance two or three axes co-rank above
0.75 purely on density. **This must be tested first, before any visual
work** (same discipline as Ch. 2/3/4).

**Fallback re-spec if the basket axes collapse (path B).** Switch the
spine from *category baskets* to a **vitality vs. comfort** tension —
the move the user flagged as the chapter's likely real story:
  - (a) **vibrancy** — commercial/social street life (eateries +
        cultural venues + retail density per 1,000 residents);
  - (b) **restorative space** — park + plaza *acreage per capita* (a
        supply measure, not a 0/1 walk indicator — density does not
        guarantee it; mirrors Ch. 4's proximity ≠ sufficiency pivot);
  - (c) **pedestrian comfort** — sidewalk generosity + pedestrianized
        street-miles, the dimension that is *designed in*, not market-
        driven.
This fallback measures *different forces* (market vibrancy vs. public-
investment comfort vs. per-capita supply) rather than three flavors of
one density signal, so it is far likelier to survive — and the
**vibrancy-vs-restorative-space scatter** is a sharper headline than a
third near-collinear choropleth. Decide which spine ships only after
running the test on real data.

**Anchor CDs.** Not picked yet. Following Ch. 2/3/4, anchors get chosen
after the spine test runs. Target shape: 5 anchors, one per borough,
including a **"vibrant but no room to breathe"** surprise anchor (a dense
CD saturated with street life but starved of per-capita open space) and a
**"quiet residential comfort"** anchor (low vibrancy, high restorative
space). Reuse a prior-chapter anchor where it ties the series together
(e.g. a Ch. 4 errand-desert CD that is also a public-realm desert).

**Headline visual — decide after spine test.** Two candidates, choose
once we see how the axes spread (watch for the Ch. 3/4 compression-near-
1.00 pattern — walk-access saturates in Manhattan):
  - a **public-realm completeness score** choropleth — within-chapter
    composite of the three axes (allowed under §9: components named,
    weights stated, grounded in the public-space / third-place
    literature). Most legible as the "public life" headline IF the
    spine survives.
  - the **vibrancy-vs-restorative-space scatter** (path B headline) —
    which CDs are both lively *and* have room to breathe, vs. lively but
    starved (the surprise quadrant). Preferred IF the basket spine fires
    or compresses, matching Ch. 4's scatter-led resolution.
Render following Ch. 2/3/4 `render_headline_choropleth` (sequential ramp,
5–95th pctile clip, 50-ft polygon simplification, display-CRS geojson
sibling for `<NycMap>`).

## Datasets

| Axis | Amenity | Source | Pipeline status |
|------|---------|--------|-----------------|
| Open space | parks ≥ 1 acre | NYC Parks Properties `enfh-gkve` | ✅ `pipelines/nyc_parks.py` (Ch. 3) |
| Open space | public plazas | NYC DOT Pedestrian Plazas `k5k6-6jex` | ❌ **new pipeline** — point/poly set, ~70 plazas |
| Vitality | eateries (restaurant/café/bar) | OSM `amenity=restaurant\|cafe\|bar\|fast_food` | ❌ extend `osm_overpass.QUERIES` (new `eateries` query) |
| Vitality | eateries (authoritative cross-check) | DOHMH Restaurant Inspection Results `43nn-pn8j` | ❌ optional cross-check pipeline (count-delta footer note) |
| Vitality | cultural venues | NYC DCLA Cultural Institutions / OSM `amenity=theatre\|arts_centre`, `tourism=museum\|gallery` | ❌ **new pipeline or OSM query** (confirm source) |
| Ped realm | sidewalk width | NYC Planimetric Sidewalk `vfx9-tbb6` (polygons; derive width) | ❌ **new pipeline** — heavy layer; derive per-CD mean width or reuse sidewalkwidths.nyc method |
| Ped realm | Open Streets | NYC DOT Open Streets Locations (`socrata id` **TBC**) | ❌ **new pipeline** — line/segment set |
| Ped realm | pedestrian plazas (shared w/ open space) | `k5k6-6jex` | ❌ same pull as above |
| (all) | total pop | ACS B01003 | ✅ `acs_census` (Ch. 3/4) |
| fallback | retail/business density | NYC DCA Legally Operating Businesses `w7w3-xahh` (or OSM) | ❌ add if path-B vibrancy axis uses it |
| fallback | open-space acreage per capita | `enfh-gkve` acres + `k5k6-6jex` area + B01003 | ❌ derived; add if fallback spine ships |

Reusable infra already in place: `shared/zip_to_cd.py`, the EPSG:2263
projection convention, `pct_within_walk` / `tract_to_cd` /
`per_cd_population` (copied from Ch. 4's notebook — candidates to promote
into `shared/` if a 4th chapter reuses them; see Punch list),
`render_headline_choropleth` from Ch. 2/3/4, `shared/cd_names.py`.

## Decision log

- **Walk-access primitive = 10-min straight-line (2,640 ft), pop-
  weighted.** Reuse Ch. 3/4's exact method for cross-chapter consistency.
  Upgrade to `shared/isochrone` walk-network distance only if a draft
  needs it (Ch. 3/4 both noted the upgrade path and shipped straight-line).
- **Parks reframed as gathering space, not green space. (open)** Confirm
  the boundary with Ch. 3 holds up — see "Boundary with prior chapters."
- **Eatery source = OSM primary, DOHMH cross-check. (LOCKED 2026-06-13)**
  OSM `amenity=restaurant|cafe|bar` is the spine source for street
  vitality (consistent with prior chapters' OSM use); cultural venues =
  OSM `theatre|arts_centre|museum|gallery`. DOHMH `43nn-pn8j` (active
  permits, dedup to one row per CAMIS) is the authoritative cross-check,
  count-delta reported in the footer. **`fast_food` EXCLUDED** — it
  dilutes the "lively street life" meaning the axis is after.
- **Sidewalk-width metric = polygon-area approximation. (LOCKED 2026-06-13)**
  The planimetric `vfx9-tbb6` layer is polygons, not widths. Per-CD mean
  width ≈ sidewalk-polygon area ÷ street-segment length per CD — a cheap,
  good-enough proxy that keeps axis 3 fully populated; the approximation
  is disclosed in the footer. (Rejected: sidewalkwidths.nyc centerline-
  buffer method — higher fidelity but too much engineering for one input
  to one axis; and drop-width-entirely — narrows axis 3 unnecessarily.)
- **First checkpoint = spine verdict. (LOCKED 2026-06-13)** Build env +
  pipelines + run the spine test, then PAUSE and report the verdict +
  which framing won (three-basket vs path-B vibrancy-vs-comfort) before
  picking anchors, building visuals, or writing prose. Lowest wasted
  work if the basket spine fires (likely, given the density confound).
- **Window / vintage.** Point/line datasets (OSM, plazas, Open Streets,
  cultural, sidewalk planimetric) pinned at the series snapshot
  2026-06-01. ACS 2019–2023 5-year. No time-series — public-realm
  provision is a stock, not a flow.
- **Open Streets dataset id — TBC.** The DOT "Open Streets Locations"
  dataset id was not pinned during spec drafting; confirm + record in
  `MANIFEST.json` when the pipeline is built (do NOT guess the id).
- **Spec scope.** Data-repo notebook docstring + this PLAN.md for now;
  promote to website-repo §10 once the spine test runs on all three axes
  (and demote Ch. 4, which §10 was never advanced to — that drift gets
  fixed in the same edit).

## Status

### Done
- **Spec + this PLAN drafted.** Chapter folder + `out/` scaffolded.
  Spine chosen (three baskets) with the path-B vitality-vs-comfort
  fallback specified up front, given the acute density-confound risk.
- **Notebook scaffold + spine-test harness** (`analyses/chapter-05/notebook.py`).
  Reuses Ch. 4's `pct_within_walk` access primitive verbatim; axis 1
  (open space) partially wired on parks (the one dataset already
  pipelined); plazas + axes 2/3 are typed stubs returning `None` so the
  harness reports partial coverage and defers the kill test until ≥ 2
  axes are wired.

### Next session (build order)
1. **Plazas pipeline** (`pipelines/nyc_dot_plazas.py`, `k5k6-6jex`) —
   small point/poly set; finishes axis 1 (open space = parks + plazas).
2. **Axis 1 end-to-end first** — get one axis ranking 59 CDs before
   building the others, to de-risk the method (Ch. 4 discipline).
3. **Axis 2 (vitality)** — `osm_overpass` `eateries` query + cultural
   venues; DOHMH `43nn-pn8j` cross-check.
4. **Axis 3 (pedestrian realm)** — resolve the sidewalk-width decision
   first (see Decision log), then Open Streets + plazas pedestrianization.
5. **Run the spine test.** Record the 3×3 Spearman matrix + verdict in a
   "Spine test result" block here (mirror Ch. 3/4). If it survives → pick
   anchors, build the completeness-score headline. If it fires/compresses
   → switch to the path-B vibrancy-vs-restorative-space scatter and
   re-run before any visual work.
6. **Pick 5 anchors** (1/borough; include the "vibrant but no room to
   breathe" surprise anchor + a "quiet residential comfort" anchor).
7. **Render headline visual** + sibling CD-level geojson for `<NycMap>`.
8. **Promote spec** to website-repo §10 (demote Ch. 4 → archived).
9. **Draft chapter MDX**, 11-section template per STYLE_GUIDE §2, with a
   `<MethodologyFooter>` carrying the "what this measure misses" notes.

## Punch list — housekeeping
- **Promote shared helpers.** `tract_to_cd`, `per_cd_population`,
  `pct_within_walk`, `_acs_tract_df`, `_osm_points` are now copy-pasted
  across Ch. 3/4/5 notebooks. Chapter 5 is the 3rd reuse — promote them
  into `shared/access.py` and import, instead of re-copying a 4th time.
  (Done conservatively as a copy in this scaffold to avoid touching Ch.
  3/4 mid-kickoff; do the extraction as its own commit.)
- `MANIFEST.json` + `cache/MANIFEST.json` entries (URL, fetch timestamp,
  SHA-256, size) for every new dataset, per repo convention.

## What this measure misses (for the MethodologyFooter)
- **Presence ≠ quality or use.** A plaza within 10 min says nothing about
  whether it's pleasant, safe, programmed, or actually used; a
  restaurant count says nothing about whether the street *feels* alive.
- **Straight-line ≠ walk-network.** 2,640 ft as the crow flies ignores
  rivers, highways, and dead-ends (same caveat as Ch. 3/4).
- **OSM completeness varies** by borough and amenity type; cross-checked
  against authoritative city datasets where one exists (DOHMH eateries).
- **Sidewalk width ≠ pedestrian experience.** A wide sidewalk next to a
  6-lane arterial is not a good place to be; width is a coarse proxy.
- **Public-realm quality is partly seasonal / temporal** — Open Streets
  and plazas are far more active in summer and on weekends; a stock
  count of locations misses when the space is actually open to people.
- **CD geography hides intra-CD variation** — a CD can score "lively" on
  average while its residential edges are pass-through dead zones (same
  intra-CD caveat Ch. 1 surfaced with per-tract isochrones).

## Vintage pins (target — confirm in `MANIFEST.json` when fetched)

| Source | Vintage | Notes |
|--------|---------|-------|
| OSM POIs (eateries, cultural) | 2026-06-01 snapshot | via `osm_overpass` |
| NYC Parks | 2026-06-01 | `enfh-gkve` (reused from Ch. 3) |
| NYC DOT Pedestrian Plazas | latest at snapshot | `k5k6-6jex` |
| NYC DOT Open Streets | latest at snapshot | id **TBC** — do not guess |
| NYC Planimetric Sidewalk | latest at snapshot | `vfx9-tbb6`; width derived, not native |
| DOHMH Restaurant Inspections | latest at snapshot | `43nn-pn8j`; dedup to active permits |
| ACS | 2019–2023 5-year | B01003; + business density `w7w3-xahh` if path-B |
