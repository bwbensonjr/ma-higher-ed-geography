## Context

See proposal.md - Why. What shapes the approach:

- **The source already decides this.** `nces_type` opens with an award tier and all 206 records have one. Only three distinct tiers appear: `< 2-year` (56 campuses), `2-year` (38), `4-year` (112, including the three records the source qualifies as primarily associate's). No record is blank or malformed today, which is what makes failing on an unrecognized tier a safe rule rather than a trap.
- **The alternatives are worse, measurably.** MassGIS's own `category` field misses 13 vocational schools filed under other categories, and wrongly excludes four real colleges: Urban College of Boston, Bard College's Holyoke Microcollege, Springfield College's continuing-education campus, and FINE Mortuary College. Filtering on certificate-only awards (`degrees_offered == "C"`) is the tier's 56 plus three 2-year institutions -- National Aviation Academy of New England, North Bennet Street School, Signature Healthcare Brockton Hospital School of Nursing -- which read as colleges.
- **Two existing requirements constrain the shape.** `geographic-data` requires every source record to be published, so the pipeline must classify rather than filter. `web-map-ui` requires per-area counts to come from the published assignment rather than being derived in the browser, so the filtered view needs its own published counts.
- **Institution counts are not additive**, so a filtered institution count cannot be obtained by subtracting the sub-associate count from the total. Both populations must be counted where the data is prepared.
- **Sizes.** Adding two counts per area takes `assignments.json` from 101 KB to 134 KB, so the page's first view goes from 306 KB to about 339 KB. The area layers, which dominate the payload at 1.6 MB, are untouched.
- **The filter empties some areas.** 17 municipalities hold campuses of which none are degree-granting. Grouped mode currently omits areas with no campuses and reports the number omitted; under the default population that number goes from 268 to 285.

## Goals / Non-Goals

**Goals:**

- One classification, derived from the source in the pipeline, that the page reads rather than infers.
- A population that governs the whole view at once, so markers, rows, groups, counts, and the summary can never disagree about what they are describing.
- Both populations' counts published, so no count on the page is ever computed by subtraction.
- Existing shared links keep working.

**Non-Goals:**

- Dropping any campus from the published data, or from the page when the visitor asks to see everything.
- Classifying by institution name, by a curated list, or by MassGIS's `category`.
- A finer classification than two populations: no per-tier facets, no filtering by award type, control, or category.
- Any change to the area layers, `area.json`, or the campus-to-area assignment itself.

## Decisions

### The tier is parsed once, in the pipeline, and published as two fields

Every campus gains `award_tier` (`sub_associate`, `two_year`, `four_year`) and `degree_granting` (boolean, true for the latter two). The tier is normalized from the source's leading token, so `4-year, primarily associate's, Public` is `four_year` like any other four-year record.

Both fields are published even though one is derivable from the other: the boolean is what almost every consumer wants, and the tier is what makes a filtered figure explicable without going back to the source string. Neither is expensive.

*Alternatives:* publish only the boolean - smaller, but a visitor asking "what exactly was left out" has nothing to read; leave the page to parse `nces_type` - the page would own a source-format assumption, and a re-worded upstream string would silently reclassify institutions with nothing failing.

### An unrecognized tier fails the build

A campus that cannot be classified would land in one population or the other and quietly misstate every count it contributes to. The pipeline raises instead, naming the campus. Today nothing triggers this; it exists because the alternative failure is invisible.

### Both populations' counts are published per area

Each area entry in the assignment gains `degree_granting_campus_count` and `degree_granting_institution_count`. The provenance record gains the statewide distinct degree-granting institution count, 116, next to the existing 160.

No second set of id arrays is published. The page filters an area's existing `campus_ids` by each campus's published flag to decide what to draw and list, and reads the published counts for what to state. Filtering a membership list it already holds is not deriving a count.

*Alternatives:* a parallel `degree_granting_campus_ids` per area - redundant with the flag and another 30 KB; publish only totals and let the page count - conflicts with the requirement that per-area counts come from the published assignment, and would make the honest-counts rule unenforceable.

### The population lives in the URL, unlike sort order and the text filter

`#population=all` alongside the existing `layer` and `area`. Absent means degree-granting, so the default view still has an empty hash and every link made before this change opens on a coherent view.

This is a departure from how sort order and the text filter are treated, and the line is: sort and filter change what a visitor is looking at within a fixed set of facts, while the population changes which facts the page is reporting. A link that says "Middlesex has 22 institutions" has to carry the population or it is misleading.

### The default is degree-granting, and the page says so

Chosen with the user. The risk of a filtered default is a visitor drawing a conclusion from a subset without noticing, so the wording carries the weight: the summary line names the population, and the control that widens it names what it would add in recognizable terms -- vocational, trade, cosmetology, and adult-education schools -- rather than "sub-associate", which means nothing outside IPEDS.

An area emptied by the filter is the sharp case. A town whose only school is a nail academy would otherwise read "contains no campuses", which is false. It gets its own message naming the population and pointing at the control.

*Alternative:* default to everything with the filter available - no risk of a silently narrowed view, but it leaves the page misrepresenting what it is a map of, which is the problem being fixed.

### The filter is applied in one place

The page has a single function producing the campus list for a state; the population is applied there, and the map, the table model, and the counts all draw from it. Nothing downstream re-filters. This keeps the "markers and counts never disagree" requirement true by construction rather than by three consistent implementations.

## Risks / Trade-offs

- **A filtered default can mislead.** Someone screenshots the map and reports 116 institutions as the state's total. Mitigation: the population is named in the summary, in the table's status line, and in the URL, and the count helpers refuse to state a figure without its population.
- **The classification is upstream's judgment, not ours.** NCES tiers are occasionally revised, and a re-tiered institution moves populations with no code change - which is the intent, but it means a count can change without the repository changing. Mitigation: provenance already records the fetch, and the classification counts are pinned in tests, so a re-tiering shows up as a failing expectation in review rather than as a silent drift.
- **Practical-nursing programs are excluded.** Several are run by regional vocational high schools and are sub-associate, so the default view omits real nursing training. Mitigation: it is one control away, and the tier is a defensible line to draw; drawing it by hand per institution is worse.
- **Every count on the page becomes population-dependent**, which doubles the states worth testing and is easy to half-implement. Mitigation: the single filter point above, and tests that assert marker, row, and stated count agree in both populations.
- **`assignments.json` grows by a third.** Mitigation: 33 KB against an existing 306 KB first view and 1.6 MB of geometry; the file is still a twelfth of the municipality layer.

## Migration Plan

`uv run ma-geo build` republishes `campus.geojson`, `assignments.json`, and `provenance.json`; the area layers and `area.json` are byte-identical. Then commit the page, push, and Pages redeploys.

Rollback is reverting the commit and re-running `build`, which reproduces the previous outputs exactly, since the classification is derived rather than stored. Existing links keep working across both directions: they carry no population, and an unrecognized `population` value degrades to the default.

## Open Questions

- Whether the control should read as a checkbox ("Include vocational and adult-education schools") or as a two-way choice of populations. A wording and control decision, best judged on screen, and it changes no requirement.
