## Why

The map presents all 206 published campuses as "colleges and universities", but 56 of them are not institutions of higher education in any ordinary sense: beauty, nail, and hairdressing academies, barbering and esthetics schools, truck-driving and electrical schools, and the practical-nursing and adult-evening divisions of regional vocational high schools. All 22 cosmetology-family campuses sit in that group. A visitor looking for the state's colleges currently has to know which names to ignore, and Middlesex County reports 45 campuses at 38 institutions when 28 campuses at 22 institutions are degree-granting.

The MassGIS source already carries the distinction. Its `nces_type` attribute, taken from NCES/IPEDS, opens with an award tier -- `< 2-year`, `2-year`, or `4-year` -- and every one of the 206 records has one. The sub-associate tier is exactly the set in question.

## What Changes

- Classify every campus in the pipeline by its NCES award tier and publish an explicit `degree_granting` flag, so the page does not parse a source string to decide what a campus is. A campus is degree-granting when its tier is `2-year` or `4-year`.
- Publish a second pair of per-area counts in the assignment -- degree-granting campuses and degree-granting distinct institutions -- so that a filtered view still reads its counts from published data rather than deriving them in the browser. Statewide the filter keeps 150 campuses at 116 institutions.
- Publish the statewide degree-granting institution count in the provenance record, alongside the existing figure of 160, since institution counts are not additive and cannot be summed from the per-area figures.
- Default the page to degree-granting institutions only, and add a control that includes the rest. The population is part of the shared view, so it belongs in the URL: a link to a county shows the same population to whoever opens it.
- Make every count, group heading, table row, marker, and summary follow the current population, and say which population is being shown, so a figure on screen is never ambiguous about what it counted.
- Handle the areas the filter empties. 17 municipalities hold campuses but no degree-granting campus, so by default they read as empty; the page must say that they hold no *degree-granting* campuses rather than presenting them as holding nothing, which would look like a data error.
- Leave every published campus in place. The pipeline keeps publishing all 206 records and the visitor can still see them; the change is which population the page shows first.

## Capabilities

### New Capabilities

None. Both affected capabilities already exist.

### Modified Capabilities

- `geographic-data`: Add the award-tier classification and the degree-granting per-area counts, and widen the consumer-contract validation to cover them. The existing requirement that every source record is published is unaffected and deliberately preserved: nothing is filtered out of the published data.
- `web-map-ui`: The page now shows a population, not simply "every campus". Adds the filter and its control, and modifies the requirements for counts, for shareable view state, and for how an empty area is explained.

## Impact

- **Pipeline**: one derived field per campus, two counts per area, one statewide figure in provenance. `assignments.json` grows from 101 KB to about 134 KB, so the page's first view goes from 306 KB to about 339 KB.
- **Published outputs**: `campus.geojson`, `assignments.json`, and `provenance.json` all change content. The three area layers and `area.json` are untouched.
- **Page**: the default view changes what a visitor sees first, and every count on the page becomes population-dependent. Existing shared links keep working and show the new default population.
- **Verification**: the page's counts, table modes, grouping, and summary all need cases for both populations, and the pipeline needs the classification pinned against known institutions so an upstream re-tiering is visible in review.
- **Judgment being encoded**: three 2-year institutions award only certificates -- National Aviation Academy of New England, North Bennet Street School, and Signature Healthcare Brockton Hospital School of Nursing -- and are kept, because the award tier rather than the award type is what this filter is built on. Four institutions that MassGIS files under vocational or adult-education categories are also kept for the same reason: Urban College of Boston, Bard College's Holyoke Microcollege, Springfield College's continuing-education campus, and FINE Mortuary College are all 2-year or 4-year by tier.
