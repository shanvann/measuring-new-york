# Chapter 2 — Housing Stability & Affordability · Methodology

Full per-metric reference for the chapter. The published chapter
(`personal-website/content/posts/measuring-new-york-02-housing.mdx`)
is the curated narrative; this file is the source-of-truth for every
number that appears there, with the exact dataset filters, aggregation
rules, scoring formula, and known limitations.

Every number in the chapter reproduces from
`analyses/chapter-02/notebook.py` against the pinned `MANIFEST.json`.
This document describes the *what* and *why*; the notebook is the
*how*.

---

## 1. Datasets

- **ACS 2019–2023 5-year** — pulled at tract level via the Census API.
  - Table **B25070** *Gross Rent as a Percentage of Household Income.*
    Nine income-share brackets, plus a "Not computed" bracket
    (B25070_011E, used when a household pays no cash rent or reports
    zero income); excluded from the rent-burden denominator.
  - Table **B25064** *Median Gross Rent.* Used for the per-CD median
    rent (renter-HH-weighted mean of tract medians, suppressed tracts
    dropped).
  - Table **B25003** *Tenure (Owner / Renter).* Used as the renter-
    household denominator (`B25003_003E`) for the per-1,000 rate
    normalizations.
  - Table **B19013** *Median Household Income.* Used for the median-
    income contrast in the cold open and the burden-vs-rent narrative.
- **OCA Housing Court filings** distributed by the
  [Housing Data Coalition](https://github.com/housing-data-coalition/oca).
  Snapshot **2026-05-10** (explicit exception to the 2026-06-01 series
  vintage freeze — the HDC ETL runs roughly monthly off a NYS OCA SFTP
  feed; no fresher snapshot was available at the time of writing).
  Filtered to: the five NYC civil courts (Bronx / Kings / New York /
  Queens / Richmond County Civil), `propertytype = 'Residential'`,
  `classification IN ('Non-Payment', 'Holdover')`, `fileddate BETWEEN
  '2024-01-01' AND '2026-05-10'`. The 2024-onward window deliberately
  excludes the eviction-moratorium and backlog-clearance distortions of
  2020–2023.
- **HPD Housing Maintenance Code Violations** from NYC Open Data dataset
  [`wvxf-dwi5`](https://data.cityofnewyork.us/Housing-Development/Housing-Maintenance-Code-Violations/wvxf-dwi5).
  Snapshot **2026-06-01**. Filtered to `inspectiondate BETWEEN
  '2024-01-01' AND '2026-05-10'`, all violation classes (A/B/C).
  Aggregated server-side via Socrata `GROUP BY zip, class` so the
  request returns ~600 rows instead of 2.27M.

---

## 2. Geographic aggregation

- **ACS → CD:** tract-centroid spatial join. NYC has 2,303 tracts ~4,000
  residents each; CDs are ~150,000 residents each. Tracts nest mostly
  inside CDs (some bisection at the edges; 22 of 2,303 tracts are
  unassigned by the centroid join — mostly water, airport, or cemetery
  tracts with no residential population — and dropped).
- **OCA + HPD → CD via ZIP:** records carry only ZIP-level geography
  (no BBL/BIN). 108 of NYC's 178 MODZCTA ZIPs (61%) span more than one
  community district, so a centroid-only join would mis-allocate roughly
  one in ten records in the affected ZIPs. The chapter uses an
  **area-weighted MODZCTA → CD crosswalk** built in `shared/zip_to_cd.py`:
  each (ZIP, CD) pair carries `area_weight = overlap_area / zip_total_area`,
  computed in EPSG:2263 (NY Long Island State Plane, feet). 349 (ZIP, CD)
  pairs across the 59 CDs; the slivers with `area_weight < 0.01` AND
  `overlap < 50,000 sqft` are dropped. ZIPs that don't appear in the
  crosswalk (non-NYC, the '00000' placeholder) are dropped at allocation
  time; the count of dropped records is reported in the chapter run
  summary.

---

## 3. Rent-burden bracket aggregation

B25070 publishes counts of renter households in each of nine gross-rent-
as-share-of-income brackets. The chapter's two summary numbers:

```
rent_burden_30 = sum(B25070_007E + B25070_008E + B25070_009E + B25070_010E)
                 / (sum(B25070_001E) - sum(B25070_011E))      # exclude "Not computed"

rent_burden_50 = sum(B25070_010E)
                 / (sum(B25070_001E) - sum(B25070_011E))
```

Bracket cutoffs: _007E = 30.0–34.9%, _008E = 35.0–39.9%, _009E =
40.0–49.9%, _010E = ≥50%. Denominator excludes _011E because those
households' burden is undefined.

---

## 4. Housing-stress score

A within-chapter composite that combines Ch. 2's two genuinely-
independent dimensions:

```
housing_stress_score = 0.7 × rank(rent_burden_30)
                     + 0.3 × mean(rank(filings_per_1k_renter_hh_per_yr),
                                  rank(hpd_per_1k_renter_hh_per_yr))
```

All ranks are 1–59 within NYC; lower means more stressed. Filings and
HPD are combined into a single "structural distress" rank because at the
CD level they are collinear (Spearman ρ = +0.82); treating them as two
independent components would double-count the same downstream effect of
burden.

The **70/30 burden-dominant** weighting is grounded in HUD's
[2025 *Worst Case Housing Needs* Report to Congress](https://www.huduser.gov/portal/publications/Worst-Case-Housing-Needs-2025-Report-to-Congress.html),
which finds that **97.2% (8.29M of 8.53M)** of worst-case-need
households qualify through severe rent burden, not inadequate housing
condition. Affordability is the empirically dominant dimension of
household-level housing crisis by roughly 30×; weighting it more heavily
than the distress signals matches the federal framework's revealed
prior.

The score is a chapter-specific roll-up of housing's two dimensions; it
is *not* a cross-chapter livability score (that's Chapter 9's job).

---

## 5. Caveats (full list)

1. **Rent-stabilized stock is opaque per-unit.** The city publishes
   per-building stabilized-unit counts derived from tax records, but
   tenants don't get a published list of which apartments are stabilized.
   In CDs with deep rent-stab penetration (Washington Heights / Inwood,
   Manhattanville / Hamilton Heights), measured median rent can drift
   from effective market rent, and the burden number absorbs both kinds
   of households without distinguishing them.
2. **Eviction filings are not evictions executed.** A filing is the
   landlord moving the process forward; most settle, are withdrawn, or
   are dismissed before becoming marshal-executed evictions. The
   narrower "who got physically removed" question needs NYC Open Data's
   `6z8x-wfk4` (DOI marshal evictions), a different and smaller number.
3. **HPD violations are reported conditions, not lived conditions.** A
   violation requires a complaint or an inspection. CDs with high
   counts may have the worst conditions *or* the most effective tenant
   organizing. The data can't separate the two; the gradient may be
   steeper than the raw numbers imply.
4. **OCA vintage exception.** Series vintage is 2026-06-01, but the
   HDC publish at time of writing is 2026-05-10. Re-pin in
   `MANIFEST.json` and rerun when a 2026-06-01-or-later snapshot is
   available.
5. **OCA filings window deliberately starts 2024-01-01** to skip the
   moratorium and backlog-clearance distortion of 2020–2023. A pre-/
   post-comparison is its own analysis.
6. **NYCHA buildings are present in HPD's dataset but the operator is
   the housing authority itself.** The eviction-and-violation machinery
   measured here works differently in NYCHA stock than in the private
   market — a plausible reason CD 313 (Coney Island / Brighton Beach,
   NYCHA-heavy) has top-5 rent burden but middling filings and HPD
   rates.
7. **ACS 5-year smoothing.** B25070 / B25064 / B25003 / B19013 are
   2019–2023 5-year estimates, smoothing across the pre-pandemic /
   pandemic / post-pandemic period. Fast-moving rent markets in 2023–
   2025 are partly absorbed into the smoothed estimate.
8. **Area-weighted ZIP→CD crosswalk over-allocates non-residential
   area.** For ZIPs that span a CD and a park or industrial waterfront,
   area weighting may slightly over-allocate filings/violations to the
   non-residential CD. Population-weighted would need block-group
   population to redistribute; deferred to Chapter 9 if it becomes
   load-bearing.

---

## 6. Sources

- ACS 2019–2023 5-year tables B25070, B25064, B25003, B19013 — [census.gov](https://www.census.gov/data/developers/data-sets/acs-5year.html)
- OCA Housing Court filings (Housing Data Coalition, snapshot 2026-05-10) — [github.com/housing-data-coalition/oca](https://github.com/housing-data-coalition/oca)
- NYC Open Data: HPD Housing Maintenance Code Violations (`wvxf-dwi5`) — [data.cityofnewyork.us](https://data.cityofnewyork.us/Housing-Development/Housing-Maintenance-Code-Violations/wvxf-dwi5)
- NYC DCP Community Districts (`5crt-au7u`, version 26a) — [data.cityofnewyork.us](https://data.cityofnewyork.us/City-Government/Community-Districts/5crt-au7u)
- NYC Open Data: Modified ZCTAs (`pri4-ifjk`) — [data.cityofnewyork.us](https://data.cityofnewyork.us/Health/Modified-Zip-Code-Tabulation-Areas-MODZCTA-/pri4-ifjk)

Notebook: [analyses/chapter-02](https://github.com/shanvann/measuring-new-york/tree/main/analyses/chapter-02).
