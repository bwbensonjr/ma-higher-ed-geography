## 1. Pipeline additions the page depends on

- [x] 1.6 Publish `docs/data/area.json` from `build`: for every area of all three layers its `area_id`, display `name`, and for a municipality its `county_id`; verify it names all 14 counties, 351 municipalities, and 10 statistical areas, that every name is identical to the name in that layer's geometry file, that areas with no campuses are named too, and that the file is under a tenth of the smallest area layer (measured at 27 KB against 390 KB).
- [x] 1.7 Record `area.json` in `provenance.json` and confirm the existing outputs are untouched; verify the provenance lists its byte size and that `campus.geojson`, the three area layers, and `assignments.json` remain byte-identical to the committed versions.
- [x] 1.8 Extend the consumer-contract check to `area.json`; verify a missing layer, a missing `name`, a municipality without its `county_id`, an area absent from the index, and an index entry naming no published area each fail and name the field and file.

- [x] 1.1 Implement the consumer-contract check in `validate`: assert every campus feature carries `campus_id`, `institution_id`, `institution`, the displayed attributes, and the three area id fields; that every area feature carries `area_id`, `layer`, and a non-empty `name`; and that `assignments.json` carries `campus_ids`, `institution_ids`, `campus_count`, and `institution_count` for every area of all three layers. Verify a fixture with a renamed field fails and names the field and file.
- [x] 1.2 Extend the contract check to referential integrity; verify a campus referencing an unknown `county_id` fails, an assignment listing an unknown `campus_id` fails, and each failure reports the dangling identifier and both files.
- [x] 1.3 Assert in the contract check that optional attributes may be empty; verify a campus with no `campus`, no `telephone`, and no `cbsa_id` passes while a campus missing `institution` fails.
- [x] 1.4 Assert the provenance figures the page displays are present; verify the check fails when `generated` or `institution_count` is removed, and that `uv run ma-geo validate` passes against the committed data.
- [x] 1.5 Confirm `build` is untouched by this change; verify a re-run leaves `campus.geojson`, the three area layers, `assignments.json`, and `provenance.json` byte-identical to the committed versions, producing no git diff.

## 2. Page scaffolding and vendored Leaflet

- [x] 2.1 Vendor Leaflet into `docs/vendor/leaflet/<version>/` with its JS, CSS, and marker assets, plus a short `SOURCE.md` naming the upstream URL, version, and checksum; verify the checksum matches the upstream release and that the vendored CSS resolves its own assets locally rather than fetching them from a remote host.
- [x] 2.2 Create `docs/index.html`, `docs/style.css`, and the ES module entry point, loading Leaflet and the page's modules by relative path only; verify the page opens from a plain static file server, the browser console reports no error, and every request except base map tiles is same-origin.
- [x] 2.3 Lay out the page shell: header with the statewide summary, layer selector, map region, and table region; verify the shell renders with placeholder content before any data is wired in.

## 3. Test harness

- [x] 3.1 Add Playwright as a dev-only dependency and a pytest fixture that serves `docs/` over a local static server and opens the page with the tile host blocked by default, so no test outcome depends on a third party; verify a smoke test asserts the page title and the presence of the map region, and that the test is skipped with a clear message when the browser binary is absent.
- [x] 3.2 Add a module-level fixture that imports the page's dependency-free modules into a blank page and calls them directly; verify a trivial round-trip through the harness passes, so later logic tasks can be tested without driving the UI.
- [x] 3.3 Add a network-recording helper that reports the URLs a page load requested and can allow or block the tile host per test; verify it reports the four eager files on a default load, distinguishes tile requests from same-origin ones, and is used by the lazy-loading tests later.

## 4. Data loading and indexes

- [x] 4.1 Implement the eager load of `campus.geojson`, `assignments.json`, `area.json`, and `provenance.json` in parallel; verify the recording helper shows exactly those four same-origin data requests on a default load and no area geometry.
- [x] 4.2 Implement `loadLayer(name)` with a memoized in-flight promise; verify drawing municipalities, switching to counties, and switching back requests `municipality.geojson` exactly once, and that two rapid switches to the same layer do not start two requests.
- [x] 4.3 Build the indexes: `campusById`, per-layer `campusesByArea` read from the assignment, per-layer area names read from `area.json`, and the campus list pre-sorted by institution name; verify the sorted list holds 206 entries, that Boston's municipality membership resolves to 38 campuses, that every campus resolves a name for its county, municipality, and statistical area with no geometry fetched, and that membership is read from the assignment rather than recomputed from coordinates.

## 5. Map: base map, markers, and campus detail

- [x] 5.1 Initialize the map with the canvas renderer, fitted to the state, and add a keyless light grey tile layer beneath every other layer with its required attribution and a zoom range from statewide to street level; verify with the tile host allowed that tiles load, that they render at the closest zoom rather than going blank, and that the tile layer sits beneath both the area layer and the markers. Esri's light gray canvas is the provider, with `maxNativeZoom` past its zoom-16 ceiling; CARTO Positron was tried first and serves an `API KEY REQUIRED` watermark with HTTP 200.
- [x] 5.6 Assert the tile provider serves real tiles rather than a watermark or placeholder: fetch tiles over three different cities and verify they differ from one another, since a placeholder is byte-identical everywhere and arrives with HTTP 200, which is how the first provider's failure escaped both the error handler and the suite.
- [x] 5.2 Render the 206 campuses as circle markers from the published coordinates; verify the map reports 206 markers and that an institution with seven campuses contributes seven of them.
- [x] 5.3 Implement the campus popup with institution, campus, address, municipality, ZIP, telephone, type, category, degrees offered, and the website as a link; verify a known campus renders every field correctly.
- [x] 5.4 Omit empty attributes from the popup; verify a campus with no campus name and no telephone renders neither label, and that no `null`, `undefined`, or empty-value placeholder appears anywhere in the popup markup.
- [x] 5.5 Tune the marker styling so campus markers stay the most prominent feature over the grey tiles; verify at both a statewide view and a street-level zoom that a marker is distinguishable from the basemap's own points of interest and labels.

## 6. Area layers, shading, and legend

- [x] 6.1 Draw the selected area layer from its fetched geometry with exactly one layer drawn at a time; verify switching counties to municipalities draws 351 areas, removes the 14, and leaves the campus markers untouched.
- [x] 6.2 Support the no-layer view; verify choosing it removes all area boundaries, leaves the base map and every campus marker visible, and clears the legend.
- [x] 6.3 Shade each area by its campus count using per-layer fixed breaks with an open-ended top class, styling zero distinctly from the lightest populated class, and choose the fill opacity against the real basemap; verify a county with many campuses is shaded more intensely than one with few, that an area with no campuses is visibly distinguished rather than shaded as "few", that the classes remain distinguishable from one another over the tiles, and that the streets beneath remain visible.
- [x] 6.4 Render a legend that re-renders with the layer and states its count ranges; verify the legend's ranges change when switching from counties to municipalities and that they match the breaks actually used to shade.
- [x] 6.5 Reveal an area's name, campus count, and institution count on hover; verify pointing at Suffolk shows its name and both counts taken from the assignment.

## 7. Selection and URL state

- [x] 7.1 Implement hash encoding, parsing, and normalization for `{layer, areaId}`; verify a round-trip through the parser preserves valid values, and that an unknown layer name, an area id absent from the data, and an area id belonging to a different layer all normalize to the default view.
- [x] 7.2 Render the whole page from parsed state through a single `hashchange` handler, with every control writing the hash rather than rendering directly; verify setting the hash programmatically to a county selection renders the same view as clicking that county.
- [x] 7.3 Implement geography selection: bring the area into view, distinguish it from its unselected siblings, and restrict the markers to its campuses; verify selecting Suffolk brings it into view, shows only Suffolk's campuses as markers, and restricts the table to the same set.
- [x] 7.4 Implement clearing the selection; verify clearing restores all 206 markers and the unrestricted table for the current layer, and that the control is present whenever a geography is selected.
- [x] 7.5 Clear the geography when the layer changes; verify selecting Suffolk then switching to municipalities leaves a valid state with no geography selected and no county presented as a municipality selection.
- [x] 7.6 Verify history navigation: selecting the county layer, then Suffolk, then going back returns to the county layer with nothing selected, and that a copied address opened in a fresh page restores the layer, the selection, the map view, and the table.
- [x] 7.7 Verify a shared address fetches only what it needs: opening a county selection requests `county.geojson` and neither the municipality nor the statistical-area geometry.

## 8. Table: campus rows, ordering, and narrowing

- [x] 8.1 Render the table as a real table with header cells, one row per campus, carrying institution, campus, address, municipality, county, statistical area, type, category, and degrees offered, taking every geography name from `area.json` rather than the campus's mailing city; verify the default view renders 206 rows, that a seven-campus institution occupies seven rows each naming its own campus and municipality, and that Boston College's main campus shows Newton, its assigned municipality, rather than its Chestnut Hill mailing city.
- [x] 8.2 Verify row-to-marker correspondence: for the default view, a layer view, and a geography selection, every rendered row corresponds to exactly one visible marker and every visible marker to exactly one row.
- [x] 8.3 Implement column ordering and a text filter matched against institution and campus names; verify ordering by municipality reorders the rows, that typing part of an institution's name restricts them, and that the count shown beside the table reflects the narrowed rows.
- [x] 8.4 Keep ordering and filter out of the hash and preserved across selection changes; verify the hash is unchanged by typing in the filter and that the filter survives a layer switch.

## 9. Table modes

- [x] 9.1 Implement the unrestricted mode; verify with no layer and no geography selected the table lists all 206 campuses ordered alphabetically by institution name with each row's three geographies shown.
- [x] 9.2 Implement the grouped mode as one `<tbody>` per area with a spanning group heading; verify the county layer with nothing selected renders 14 groups ordered by county name, each heading naming its county with its campus and institution counts, and each group holding that county's campuses.
- [x] 9.3 Verify grouped membership is exact: grouping by the municipality layer places each campus in exactly one group, and the campus counts across the groups sum to 206.
- [x] 9.4 Implement the single-geography mode with a statement of what it is restricted to; verify selecting Boston renders exactly its 38 campuses and names Boston as the restriction.
- [x] 9.5 Verify mode switching needs no reload: moving between the three modes updates the table in place with no navigation away from the page.

## 10. Table rows navigate to a geography

- [x] 10.1 Make each row's county, municipality, and statistical-area value a control that selects that layer and geography; verify acting on `Middlesex` in the unrestricted table draws the county layer, selects Middlesex, brings it into view, and restricts the table to its campuses.
- [x] 10.2 Verify the action works from every table mode, including from within a group in the grouped mode and from a row in a single-geography view.
- [x] 10.3 Render no action for an absent statistical area; verify a row whose campus has no `cbsa_id` presents plain text rather than a control that would select nothing.

## 11. Counts presented honestly

- [x] 11.1 Implement the count helpers, taking per-area counts from the assignment and the statewide institution figure from provenance only; verify an area with 38 campuses and 35 institutions reports both, each labeled, and that no helper exists that sums institution counts across a layer.
- [x] 11.2 Render the statewide summary; verify the default view states 206 campuses and 160 institutions, both read from the published data rather than written into the page.
- [x] 11.3 Verify no summed institution total is rendered anywhere: any layer-wide institution figure equals the published 160 rather than the sum of per-area counts, and a campus total may be shown as a sum.

## 12. Loading, failure, and empty states

- [x] 12.1 Show a loading state until the eager files have arrived; verify with a delayed response that the page indicates loading and never presents an empty table as the complete list of campuses.
- [x] 12.2 Report a failed eager fetch; verify with a blocked `campus.geojson` that the page states the data could not be loaded and does not display a count of zero campuses as though the state contained none.
- [x] 12.3 Degrade a failed layer fetch; verify with a blocked `municipality.geojson` that the page reports that layer unavailable while the markers, the table, and the other two layers stay usable.
- [x] 12.4 Present an empty geography as a valid result; verify selecting a municipality with no campuses states that it contains no campuses, keeps it selected, and keeps it in view, with no error styling.
- [x] 12.5 Keep tile failure cosmetic: add the tile layer without awaiting it and swallow tile errors rather than routing them to the page's data-failure state; verify with the tile host blocked that the markers, all three layers, selection, and the table work completely, that the page reports no data failure, and that no interaction waits on tiles.

## 13. Layout and assistive access

- [x] 13.1 Implement the responsive layout with the map above the table on narrow viewports; verify at a 375 px viewport that both are usable and the page does not scroll horizontally, with the table's hidden columns reachable by scrolling the table itself.
- [x] 13.2 Make the layer selector, the clear-selection control, and every row geography action reachable and operable by keyboard; verify a keyboard-only pass selects a layer and a geography from a table row, and that the resulting table matches the pointer-driven result exactly.
- [x] 13.3 State the current layer and geography as text and give the table's header cells and group headings their proper roles; verify the selected layer and geography are readable as text with map colors ignored, and that the accessibility tree exposes the table as a table with named columns.

## 14. Provenance and attribution

- [x] 14.1 Render the sources and the preparation date from `provenance.json`; verify the displayed date and source titles match the file and that editing the file's `generated` date changes the page with no edit to the page.
- [x] 14.2 Render the upstream attribution for the geography and campus sources alongside the base map's required Esri and OpenStreetMap attribution; verify both are visible on the page, that the tile provider is named so its involvement is evident to a visitor, and that the data sources' attribution remains visible when the tile host is blocked.

## 15. Verification and publication

- [x] 15.1 Run the full suite; verify `uv run ma-geo build`, `uv run ma-geo validate`, and `uv run pytest` all succeed, that `build` produces no git diff beyond `area.json` and its provenance entry, and that the browser tests skip cleanly when the Playwright browser is absent.
- [x] 15.2 Verify the page's data independence end to end: with the tile host blocked, the campus markers, all three layers, the selection behavior, and the table render completely, and the only non-same-origin requests the page makes when tiles are allowed are tile requests.
- [x] 15.3 Update the README with how to view the page locally, `area.json` in the published file table, the campus-row decision, the base map and its attribution, and the note that tile requests disclose a visitor's address and viewed area to the tile provider; verify the published file table still matches what `build` actually writes.
- [ ] 15.4 Publish: enable GitHub Pages on `docs/` of the default branch and verify the live URL loads the map with its tiles over HTTPS, that a shared geography link works from a cold load, and that the published page logs no console error and makes no cross-origin request other than tiles.
