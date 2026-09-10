## 1. Classify campuses in the pipeline

- [x] 1.1 Implement the award-tier normalization from the source's NCES type attribute to `sub_associate`, `two_year`, or `four_year`; verify all 206 records classify, that the three tiers hold 56 sub-associate, 38 two-year, and 112 four-year campuses, and that `4-year, primarily associate's, Public` normalizes to `four_year` rather than being treated as a separate tier.
- [x] 1.2 Raise on a campus whose tier is empty or unrecognized; verify a fixture with a blank and a fixture with an unknown tier each fail naming the campus, and that the previously published outputs are left in place.
- [x] 1.3 Publish `award_tier` and `degree_granting` on every campus feature in `docs/data/campus.geojson`; verify all 206 features carry both, that `degree_granting` is true exactly for `two_year` and `four_year`, and that 150 campuses at 116 distinct institutions are degree-granting.
- [x] 1.4 Pin the classification against known institutions; verify all 22 beauty, nail, hairdressing, barbering, esthetics, and electrology campuses are `sub_associate`, that Harvard, Williams, and the community colleges are degree-granting, and that Urban College of Boston, Bard College's Holyoke Microcollege, Springfield College's continuing-education campus, FINE Mortuary College, North Bennet Street School, National Aviation Academy of New England, and Signature Healthcare Brockton Hospital School of Nursing are all degree-granting despite their category or certificate-only awards.
- [x] 1.5 Confirm nothing is filtered out of the published data; verify `campus.geojson` still holds all 206 features and that the campus-to-area assignment's memberships are unchanged from the committed version.

## 2. Publish both populations' counts

- [x] 2.1 Add `degree_granting_campus_count` and `degree_granting_institution_count` to every area entry of all three layers in `docs/data/assignments.json`, including areas where they are zero; verify all 14 counties, 351 municipalities, and 10 statistical areas carry both, and that the existing counts and id arrays are unchanged.
- [x] 2.2 Verify the published counts agree with the campus flags for every area of every layer: the campus count equals the number of member campuses flagged degree-granting, and the institution count equals the number of distinct institutions among them.
- [x] 2.3 Verify known figures: Middlesex reports 45 campuses at 38 institutions and 28 degree-granting campuses at 22 degree-granting institutions; Worcester 23 and 23, then 13 and 13; Boston's municipality entry reports its two populations correctly.
- [x] 2.4 Publish the statewide distinct degree-granting institution count in `docs/data/provenance.json` alongside the existing figure; verify it reads 116 next to 160, and that summing the per-area degree-granting institution counts across a layer exceeds 116, with a test documenting that the sum is not a statewide total.
- [x] 2.5 Verify the untouched outputs stay untouched; verify `county.geojson`, `municipality.geojson`, `cbsa.geojson`, and `area.json` are byte-identical after a re-run, and that `build` remains idempotent for the three files that do change.
- [x] 2.6 Record the payload change; verify `assignments.json` is about 134 KB, that provenance reports its new size, and that the page's four eager files total under 350 KB.

## 3. Extend the consumer contract check

- [x] 3.1 Require `award_tier` and `degree_granting` on every campus in the contract check; verify a campus missing either fails naming the field and the file, and that an `award_tier` outside the three known values fails.
- [x] 3.2 Require both degree-granting counts on every area entry; verify a missing count fails naming the field and the file, and that a count published as text rather than a whole number fails.
- [x] 3.3 Cross-check the published counts against the flags inside the contract check; verify an area whose `degree_granting_campus_count` disagrees with its members' flags fails, reporting the area, the published count, and the count the flags imply.
- [x] 3.4 Require the statewide degree-granting institution figure in provenance; verify its removal fails the check, and that `uv run ma-geo validate` passes against the freshly built data.

## 4. The population in the page's state

- [x] 4.1 Add the population to the page's state and hash encoding as `population=all`, with degree-granting as the value an absent key produces; verify a round-trip preserves both values, that the default state still encodes to an empty hash, and that an unrecognized population value normalizes to degree-granting.
- [x] 4.2 Verify existing links keep working: an address carrying only `layer` and `area` opens on the degree-granting population with that layer and geography selected, and renders no error.
- [x] 4.3 Apply the population in one place, the function that produces the campus list for a state, and have the map, the table model, and the count helpers all draw from it; verify by test that no other module filters on `degree_granting`, so the three cannot disagree.
- [x] 4.4 Verify the population survives layer and geography changes: including the sub-associate schools, then selecting a layer and a geography, leaves the wider population in force and in the hash.
- [x] 4.5 Verify history and sharing: including the sub-associate schools then going back returns to the degree-granting population, and an address copied from a wider-population view opens on that population in a fresh page.

## 5. The control and what it says

- [x] 5.1 Add the control that includes the sub-associate campuses, defaulting to off, labeled in terms a visitor recognizes rather than by the source's tier vocabulary; verify the label names vocational, trade, cosmetology, or adult-education schools and never only "sub-associate", and that operating it writes the hash rather than rendering directly.
- [x] 5.2 Make the control keyboard reachable and operable, and state the current population as text; verify a keyboard-only pass switches population, that the resulting view matches the pointer-driven result exactly, and that the population is readable as text with map colors ignored.
- [x] 5.3 State the population in the statewide summary and in the table's status line; verify the default view says it is showing degree-granting institutions and the widened view says the sub-associate schools are included.

## 6. Every part of the view follows the population

- [x] 6.1 Draw only the current population's markers; verify the default view renders 150 markers, the widened view 206, and that no cosmetology, barbering, trade, or adult-education campus is drawn by default.
- [x] 6.2 List only the current population's rows in all three table modes; verify the default unrestricted table holds 150 rows, that grouped mode by county holds 150 rows across its groups, and that a selected geography's rows match its published degree-granting campus count.
- [x] 6.3 Take every count from the published counts for the current population; verify the statewide summary states 150 campuses at 116 institutions by default and 206 at 160 when widened, that each figure is read from the published data rather than computed by subtraction, and that no helper derives one population's counts from the other's.
- [x] 6.4 Verify group headings follow the population: with the default population the county layer's headings state each county's degree-granting counts, and the omitted-group count reported beside the table rises from 268 to 285 municipalities.
- [x] 6.5 Verify markers, rows, and the stated count agree in both populations, for the unrestricted view, a layer view, and a geography selection, so the page can never show one population's markers beside another's counts.
- [x] 6.6 Verify the shading and the legend follow the population: an area is shaded by its current population's campus count, and a county that drops a shading class when the filter is applied is shaded by the lower class.

## 7. Areas the filter empties

- [x] 7.1 Distinguish an area emptied by the population from one holding no campuses at all; verify a municipality whose only campuses are sub-associate states that it holds no degree-granting campuses, not that it holds none, and that it offers the way to see what it does hold.
- [x] 7.2 Verify the count that matters: 17 municipalities hold campuses but no degree-granting campus, and each of them takes the emptied-by-filter message rather than the empty message.
- [x] 7.3 Verify a genuinely empty area is unchanged: a municipality with no campuses in either population still states that it contains no campuses, stays selected, and stays in view, with no error styling.

## 8. Verification and publication

- [x] 8.1 Run the full suite; verify `uv run ma-geo build`, `uv run ma-geo validate`, and `uv run pytest` all succeed, that the only published files whose content changes are `campus.geojson`, `assignments.json`, and `provenance.json`, and that a second `build` produces no further diff.
- [x] 8.2 Verify the page end to end in both populations with the tile host blocked: the default and widened views each render their markers, table, counts, and summary consistently, and switching between them needs no reload.
- [x] 8.3 Update the README with the two populations, the default, the NCES award tier the classification comes from, and why the tier rather than the source's category or its award types decides it; verify the published file table and the payload figures match what `build` actually writes.
- [x] 8.4 Publish and verify live: push to the default branch, then confirm the published page opens on the degree-granting population, that a shared link carrying `population=all` restores the wider view from a cold load, and that the page logs no console error and makes no cross-origin request other than tiles.
