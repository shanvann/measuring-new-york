# Chapter 6 — Safety

Working plan + session status for Phase 3f. Lives alongside the chapter
notebook so the spec, the in-flight work, and the punch list are all in
one place. Authoritative chapter spec is `MEASURING_NEW_YORK_PLAN.md`
§10 in the website repo; this file is the data-repo working copy and
gets archived/promoted at the end of Phase 3f.

**Status of this file:** *pre-flight spec.* No data has been run yet —
like the Ch. 4 / Ch. 5 PLANs at their kickoff, the numbers below are
targets and design decisions, not results. The spine test has NOT been
run. Decisions marked **(open)** still need the user's call before the
notebook locks.

## The angle

> **Safety is broader than crime statistics.**
> (`measuring_livability.md` §4)

Every prior chapter found that the metric everyone reaches for points
*away* from the thing it claims to measure: median rent points away from
housing stress (Ch. 2), proximity points away from sufficiency (Ch. 4),
density points away from restorative space (Ch. 5). Chapter 6 makes the
same move on the most emotionally loaded metric in the whole series — and
on the gap between what we *fear* and what actually *harms* us.

The chapter's spine is a tension: **the danger you feel vs. the danger that
is measured.** The places New Yorkers rate as unsafe and the places where
people are actually hurt are **not the same map.** Fear is tuned to visible
street crime — a mugging is vivid, narratable, the thing you picture when
someone says "bad neighborhood." Traffic violence is ambient and ignored,
yet across much of the city it is the larger threat to life and limb, and it
peaks in exactly the quiet, car-dependent, low-crime places that *feel*
safest. The chapter's claim is that **perceived safety is well-calibrated to
crime and nearly blind to cars** — so "safe," the way people mean it, is
measuring the wrong risk.

The framing device: **the map of fear vs. the map of harm.**

## Spec

**Architecture = HYBRID (LOCKED 2026-07-11, user call, after source
research).** No current per-CD perceived-safety survey exists publicly
(see Datasets / research finding), so perceived danger cannot carry a
headline axis on current CD-native data. Resolution:

- **Measured spine (current, CD-native, rigorous) = three kinds of harm.**
  This carries the headline.
- **Perceived danger = a clearly-caveated SUPPORTING overlay** (CHS 2016 at
  UHF42, crosswalked to CD), brought in to test *fear calibration*, not to
  anchor a headline axis.

**Measured-spine hypothesis.** Objective bodily/property harm splits into
**three semi-independent axes**, each per 1,000 residents, each driven by a
*different* generative force:

  1. **Violent crime** — person-directed major felonies (murder, rape,
     robbery, felony assault). Force: concentrated disadvantage. The harm
     fear is *about*.
  2. **Traffic violence** — pedestrians + cyclists killed or severely
     injured (KSI). Force: road design + car dependence. The harm fear
     *ignores*. The axis that inverts the crime map and carries the chapter.
  3. **Property crime** — burglary + grand larceny + GLA. Force:
     opportunity / affluence / foot traffic. The "crime rate" the reader
     expects, shown to diverge from the bodily-harm story.

**Kill criterion (standard, mirrors Ch. 2–5).** |ρ| ≥ 0.75 (Spearman,
n = 59) on any pair collapses the spine. **At-risk pair = violent ↔
property** (they share the NYPD reporting/recording pipeline and a general
"crime" factor; CD-level ρ ≈ 0.5–0.7 in the literature). If they merge, the
chapter becomes a clean **2-axis reported-crime vs. traffic** story — an
*acceptable* outcome, since that is exactly the crime-map ≠ danger-map
headline. **Traffic KSI is expected to stay orthogonal to (or invert) both
crime axes** — that independence is what the chapter is built on, so the
spine is robust to the one kill it's exposed to.

**Fear-calibration overlay (the supporting analysis).** Bring in CHS 2016
`safeneighborhood16` (perceived safety), crosswalked UHF42 → CD, and
correlate perceived danger against each objective axis:
  - **Expected:** ρ(perceived, violent) **high** (fear is calibrated to
    crime); ρ(perceived, traffic) **low / ~zero** (fear is blind to cars) —
    even though traffic KSI is a large share of bodily harm. *That gap is
    the chapter's emotional payload.* Target contrast ρ(perceived, violent)
    − ρ(perceived, traffic) ≥ ~0.3.
  - Reported as a **supporting** result with the vintage + geography caveats
    stated loudly (2016; UHF42 ≈ 1–2 CDs; rank-based, so robust to the
    stale absolute levels only insofar as perceived-safety *rankings* are
    geographically persistent — stated as an assumption, not a fact).
  - If the overlay's correlations come out flat/noisy (plausible, given the
    crosswalk degradation), it is dropped to a single honest sentence
    ("perception data too coarse to adjudicate") and the chapter stands on
    the three-harm spine alone. The headline never depends on it.

**Anchor CDs.** Not picked yet. Following Ch. 2/3/4/5, anchors get chosen
*after* the spine test runs. Target shape: 5 anchors, one per borough,
including:
  - a **"feels unsafe, bodily-harm moderate"** anchor — high perceived
    danger + high violent crime but low traffic KSI (dense, poor,
    transit-dependent; few residents drive). Likely South Bronx /
    Brownsville.
  - a **"feels safe, actually deadly"** surprise anchor — low perceived
    danger + low violent crime but high traffic KSI (car-dependent, wide
    arterials). Likely southeast Queens or Staten Island. The headline
    anchor: the map of fear says "fine," the map of harm says "deadly."
  - a **"property-crime magnet"** anchor — high property crime, low violent,
    commercial core; also stress-tests the daytime-population caveat. Likely
    Midtown / Lower Manhattan.
  - reuse a prior-chapter anchor to tie the series (e.g. Brownsville **CD
    316** from Ch. 2, or a Ch. 4 errand-desert CD) if it also anchors a
    safety extreme.

**Headline visual — decide after spine test.** Two candidates:
  - the **fear-vs-harm scatter** — one dot per CD, x = perceived danger,
    y = objective bodily-harm per 1k, anchors labelled, quadrants named
    ("feared & harmful" / "feared, not harmful" / **"safe-feeling &
    deadly"** / "calm"). The single sharpest image of the map-of-fear ≠
    map-of-harm thesis. Preferred lead.
  - a paired **small-multiple choropleth** — *map of fear* beside *map of
    traffic death* — the two-maps-don't-match reveal at a glance; the
    interactive `<NycMap>` ships the objective side with a violent/traffic
    toggle so readers see fear track one layer and not the other. (Ch. 5
    shipped a multi-axis `<NycMap>` toggle — reuse it.)
Render following Ch. 2/3/4/5 `render_headline_choropleth` (sequential ramp,
5–95th pctile clip, 50-ft polygon simplification, display-CRS geojson
sibling for `<NycMap>`).

## Datasets

| Axis | Signal | Source (Socrata id) | Pipeline status |
|------|--------|---------------------|-----------------|
| Objective — Violent + Property | complaint-level felonies | NYPD Complaint Data **Historic** `qgea-i56i` + **YTD** `5uac-w243` (verify ids on Socrata before pinning — do NOT guess) | ❌ **new pipeline** `pipelines/nypd_complaints.py` — filter major-felony `KY_CD`/`LAW_CAT_CD='FELONY'`, split violent vs property by `OFNS_DESC`, point-in-polygon to CD via `Latitude`/`Longitude` |
| Objective — Traffic KSI | crash → person injuries/deaths | NYPD **Motor Vehicle Collisions – Crashes** `h9gi-nx95` (+ **Person** table `f55k-p6yu` for ped/cyclist role & severity — verify id) | ❌ **new pipeline** `pipelines/nypd_collisions.py` — derive ped+cyclist KSI, point-in-polygon to CD |
| Overlay — Perceived safety | resident-rated "how safe from crime is your neighborhood" | **DOHMH Community Health Survey `safeneighborhood16` (2016), UHF42** — public-use file at UHF34; CD-level needs a DUA. `https://www.nyc.gov/site/doh/data/data-sets/community-health-survey-public-use-data.page` | ⚠ overlay only — download 2016 PUF + codebook, crosswalk UHF→CD (areal, each UHF ≈ 1–2 CDs). NOT a headline axis. |
| (all) | total pop | ACS B01003 | ✅ `acs_census` (Ch. 3/4/5) |
| traffic denom (cross-check) | street centerline miles | NYC **LION** / DCP Street Centerline `CSCL` | ❌ add only if the KSI-per-mile cross-check is kept |

**Research finding (2026-07-11, verified vs. primary sources).** No current,
publicly-downloadable *per-CD* perceived-safety survey exists. NYCHVS 2023
has a real safety item (`SAFETY_RATE`) but only at **borough** geography.
NYPD's Elucd "Sentiment Meter" (2017–2020) was ideal but **never released**
below the agency (FOIL-only). DOHMH CHS `safeneighborhood16` is the only
downloadable genuine perception measure — **2016 vintage, UHF42 geography**.
311 `Street Light Condition` (`erm2-nwe9`, `descriptor='Street Light Out'`,
aggregate by `community_board`) is current + CD-native but a reporting-biased
*environmental* proxy, not perception. → **Hybrid decision:** three-harm
objective spine leads; CHS 2016 is a caveated fear-calibration overlay.

Reusable infra already in place: EPSG:2263 projection convention, the
per-CD point-in-polygon assignment used by Ch. 4's FacDB pipeline (crime /
crash geocoding is the *same* operation — points → CD), `tract_to_cd` /
`per_cd_population` (denominators; **promote to `shared/access.py` this
chapter — see Punch list**), `render_headline_choropleth` from Ch. 2/3/4/5,
`shared/cd_names.py`, `shared/palette.py`.

## Decision log

- **Architecture = HYBRID (LOCKED 2026-07-11, user call).** Three-harm
  objective spine (violent / traffic / property, current CD-native) carries
  the headline; the fear ≠ harm story is delivered via a caveated CHS-2016
  perceived-safety *overlay*, not a headline axis — because no current per-CD
  perceived survey exists (research finding above). The originally-considered
  perceived-as-co-lead framing was set aside once the data proved too
  stale/coarse to headline.
- **Normalization = per-1,000-residents spine + per-street-mile traffic
  cross-check + daytime-population caveat for commercial cores (LOCKED
  2026-07-11, user call).** Per-resident keeps cross-axis comparability and
  series consistency; traffic KSI also reported per street-mile so the
  arterial story isn't a resident-count artifact; Midtown / Lower-Manhattan
  daytime-population distortion disclosed in the footer for affected anchors.
- **Perceived-safety overlay DROPPED — data not accessible (RESOLVED
  2026-07-11).** Second research pass confirmed the CHS 2016 public-use file
  **omits the neighborhood geography variable** (`uhf34` is DUA-restricted,
  absent from the 10k-row public microdata), so no per-CD/per-UHF perceived
  rate is computable without a DOHMH Data Use Agreement. Only a **citywide**
  2016 figure exists: **14.5% rated their neighborhood unsafe from crime**
  (weighted). The chapter therefore makes the fear-vs-harm argument from
  *where the objective harm lands* (violent crime in the feared districts,
  traffic in the calm ones), not from a measured fear axis, and says so.
  A UHF34→CD crosswalk is prepped (`scratchpad/uhf_cd_crosswalk.csv`) if the
  DUA microdata is ever obtained.
- **Crime window / vintage.** NYPD complaint + collision data are event
  streams — pull a **fixed 3-year window** (target **2022-01-01 →
  2024-12-31**) so per-CD rates are stable, not single-year noise;
  annualized. Pin exact window in `MANIFEST.json` when fetched. No pre/post
  policy-shock split. (open — confirm 3-yr window when building.)
- **Traffic severity threshold = KSI** (killed or severe injury, Vision Zero
  standard), not all injuries — avoids drowning the signal in fender-benders.
  Confirm the Person-table severity coding supports a clean KSI cut; else
  fall back to "ped/cyclist killed or injured" and disclose. (open)
- **First checkpoint = spine verdict. (LOCKED — house discipline)** Build
  env + the perceived axis + the two crime/collision pipelines + run the
  correlation test, then PAUSE and report: ρ(perceived, violent),
  ρ(perceived, traffic), ρ(perceived, objective-composite), and whether the
  fear-vs-harm gap holds — before picking anchors, building visuals, or
  writing prose.
- **Spec scope.** Data-repo notebook docstring + this PLAN.md for now;
  promote to website-repo §10 once the spine test runs (and fix the §10
  drift — it still shows Ch. 2 — in the same edit).

## Status

### Done
- **Spec + this PLAN drafted.** Chapter folder + `out/` scaffolded. Spine
  locked (hybrid: three-harm objective spine + CHS-2016 perceived overlay).
  Normalization locked. Perceived-source research completed.
- **Pipelines built + fetched:** `pipelines/nypd_complaints.py` (375,823
  seven-major-felony complaints, 2022-2024) and `pipelines/nypd_collisions.py`
  (39,550 ped/cyclist harm-crashes; 40,318 casualties, 379 killed). Both
  cached + pinned in `MANIFEST.json`.
- **Notebook + spine test run** (`analyses/chapter-06/notebook.py`) →
  `out/facts.json` + `out/rankings.csv`.

### Spine test result (2026-07-11) — SPINE SURVIVES
n = 59 CDs, Spearman ρ, per-1,000-residents, annualized 2022-2024:

| pair | ρ | verdict |
|------|---|---------|
| violent ~ traffic KI | **+0.478** | ok (the crime map and the traffic map genuinely differ) |
| violent ~ property   | **+0.610** | ok (the at-risk pair — stays two distinct axes, does NOT merge) |
| traffic KI ~ property| **+0.447** | ok |

No pair ≥ 0.75 → **three-harm spine holds**; all three axes ship. Citywide
medians/1k: violent 4.84, traffic KI 1.52, property 8.34.

**Headline evidence — the biggest crime-rank vs. traffic-rank flips:**
- **BX 209 Soundview/Parkchester** — violent #14, traffic #50 (high crime,
  safe roads). **BX 207 Kingsbridge Hts/Bedford Park** — violent #11,
  traffic #41. The "feared, not deadly" South-Bronx pattern.
- **MN 106 Stuyvesant Town/Turtle Bay** — violent #43, traffic **#5**;
  **BK 301 Williamsburg/Greenpoint** — violent #40, traffic #9; **BK 307
  Sunset Park** — violent #37, traffic #8. The "calm-feeling, deadly-street"
  pattern — but note these are dense, high-*throughput* areas, so the traffic
  toll is partly **pedestrian-exposure / ambient-population**, not the "quiet
  car-dependent arterial" I hypothesized. The per-street-mile cross-check +
  daytime-pop caveat matter here (see below).
- **BK 312 Borough Park** — violent #55 (near-safest), traffic #19.

**Refinement CONFIRMED (empirical, overturns the kickoff hypothesis):** I
guessed traffic danger would hide in *quiet car-dependent outer-borough
arterials*. The data says the opposite. Traffic casualties concentrate in
**dense Manhattan** (Midtown, Chelsea, Village, Stuy Town, Harlem, LES) — a
**pedestrian-exposure** story, not car-dependence — while the car-dependent
outer edges (Tottenville, Bayside, Throgs Neck, Forest Hills) are the
**safest** per capita: few people on foot, few people hit. The per-street-
mile cross-check (`pipelines/nyc_street_centerline.py`, CSCL `inkn-q76z`)
gives **traffic per-1k ~ per-mile ρ = +0.713** → the dense-core toll is NOT a
resident-denominator artifact; it survives an exposure denominator (Midtown
is #1 on both). Violent crime, meanwhile, concentrates in the **South Bronx**
(Mott Haven, Kingsbridge, Soundview) + Brownsville. Different maps → thesis
holds, mechanism is exposure. **Midtown (105) is the ambient-population
caveat** — tiny residential denominator inflates all three per-resident
rates (V#3, T#1, P#1); discuss in prose, not anchored.

**Anchors (locked, 1/borough, span the quadrants):** 209 Soundview (BX,
feared-not-deadly) · 106 Stuyvesant Town/Turtle Bay (MN, calm-but-deadly) ·
316 Brownsville (BK, the feared archetype, Ch.2 tie) · 411 Bayside (QN, safe,
Ch.2 tie) · 503 Tottenville (SI, safest CD citywide). Quadrant spread: 20
feared+deadly / 19 safe / 10 calm-but-deadly / 10 feared-not-deadly.

**Headline shipped:** `out/crime-vs-danger.svg` (violent×traffic scatter,
fallback) + `out/safety.geojson` (per-CD axes+ranks+quadrant for `<NycMap>`).

### Next session (build order)
1. **Lock the perceived-safety source** from the research verdict; record id
   + geography + crosswalk-to-CD + vintage in `MANIFEST.json`.
2. **Promote shared access helpers** (`tract_to_cd`, `per_cd_population`,
   `_acs_tract_df`, point-in-polygon `points_to_cd`) from the Ch. 4/5
   notebooks into `shared/access.py` as its own commit — 4th reuse; stop
   copy-pasting (Ch. 5 punch-list carryover).
3. **NYPD complaints pipeline** (`pipelines/nypd_complaints.py`) — verify
   ids, pull the window, split violent vs property, point-in-polygon to CD,
   per-1k rates.
4. **NYPD collisions pipeline** (`pipelines/nypd_collisions.py`) — crashes +
   person tables → ped/cyclist KSI per CD; per-1k + per-street-mile.
5. **Perceived-safety pipeline** — from the locked source; crosswalk to CD.
6. **Run the spine test.** Record ρ(perceived, violent / traffic /
   objective) + the fear-vs-harm verdict in a "Spine test result" block here
   (mirror Ch. 3/4/5). Branch per the Decision log (hold objective-vs-
   perceived, or fall back to kinds-of-harm).
7. **Pick 5 anchors** (1/borough; include the "feels safe, actually deadly"
   surprise + a "property-crime magnet").
8. **Render headline visual** (fear-vs-harm scatter or paired choropleth +
   `<NycMap>` toggle) + sibling CD-level geojson.
9. **Promote spec** to website-repo §10 (fix the Ch. 2 → Ch. 6 drift).
10. **Draft chapter MDX**, 11-section template per STYLE_GUIDE §2, with a
    `<MethodologyFooter>` carrying the "what this measure misses" notes; add
    `analyses/chapter-06/METHODOLOGY.md`.

## Punch list — housekeeping
- **Promote shared helpers (now overdue).** `tract_to_cd`,
  `per_cd_population`, `_acs_tract_df`, point-in-polygon assignment are
  copy-pasted across Ch. 3/4/5 notebooks. Ch. 6 is the 4th reuse — do the
  `shared/access.py` extraction as an early step, its own commit, and import
  going forward.
- `MANIFEST.json` + `cache/MANIFEST.json` entries (URL, fetch timestamp,
  SHA-256, size) for every new dataset, per repo convention.
- Confirm every NYPD dataset id on Socrata before pinning — **do not guess
  ids** (same rule Ch. 5 applied to the Open Streets id).

## What this measure misses (for the MethodologyFooter)
- **Perceived safety is coarse and partly borrowed.** If the perceived axis
  comes from a survey at sub-borough / UHF scale, it is crosswalked to CDs
  and cannot resolve block-level fear; if it comes from 311, it measures
  *who complains* as much as *what's wrong* (the Ch. 0 reporting-bias
  lesson). Either way it is a proxy for a genuinely subjective, hard-to-
  measure thing.
- **Reported ≠ occurred.** NYPD complaint data is *reported* crime;
  under-reporting varies by crime type and by community trust in police, so
  a low violent-crime rate can partly reflect low reporting. (Traffic KSI is
  far less prone to this — a hospitalization or death is recorded
  regardless of trust.)
- **Resident denominator ≠ exposed population.** Per-resident rates overstate
  risk in commercial cores (Midtown's daytime population dwarfs its
  residents) and understate it where commuters and visitors are the victims.
  Flagged for affected anchors; traffic cross-checked per street-mile.
- **CD geography hides the intersection.** Traffic danger is a *corridor*
  phenomenon — one arterial, a few intersections — that a CD average blurs
  (same intra-CD caveat Ch. 1 surfaced with per-tract isochrones).
- **Harm is a stock of events, not of fear's daily cost.** The chapter
  measures harm that *happened* and fear as *rated*; it cannot capture the
  behavioral tax of feeling unsafe — who stops walking, when, and where —
  which reshapes lives without ever appearing in a crime or crash record.
- **Three years is a window, not a trend.** A fixed multi-year window
  stabilizes rates but says nothing about whether a place is getting safer;
  no trend claim is made from it.

## Vintage pins (target — confirm in `MANIFEST.json` when fetched)

| Source | Vintage | Notes |
|--------|---------|-------|
| NYPD Complaint Data (Historic + YTD) | 2022-01-01 → 2024-12-31 window | `qgea-i56i` / `5uac-w243` — verify ids; major-felony subset |
| NYPD Motor Vehicle Collisions | 2022-01-01 → 2024-12-31 window | `h9gi-nx95` (+ person `f55k-p6yu`) — verify ids; ped/cyclist KSI |
| Perceived safety (survey or 311) | TBD — set when source locked | NYCHVS / DOHMH CHS / 311 lighting; record crosswalk-to-CD |
| NYC LION / CSCL centerline | latest at snapshot | traffic per-mile cross-check only |
| ACS | 2019–2023 5-year | B01003 population denominators |
