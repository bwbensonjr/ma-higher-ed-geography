## 1. Project scaffolding

- [x] 1.1 Create `pyproject.toml` for a `ma-higher-ed-geography` package with `geopandas`, `shapely`, `pyogrio`, `topojson`, and an HTTP client; verify `uv sync` resolves and `uv run python -c "import geopandas, topojson"` succeeds.
- [x] 1.2 Create the pipeline package with a `fetch` / `build` / `validate` entry point; verify `uv run ma-geo --help` lists all three subcommands.
- [x] 1.3 Add `data/raw/` to `.gitignore` and create `docs/data/`; verify `git status --ignored` shows `data/raw/` ignored and `git check-ignore docs/data` reports nothing.

## 2. Fetch the sources

- [x] 2.1 Implement the ArcGIS fetch helper (`f=geoJSON`, `outSR=4326`, explicit `outFields`, count assertion against `returnCountOnly`); verify a single-layer fetch writes valid GeoJSON to `data/raw/` and raises when the returned feature count differs from the reported count.
- [x] 2.2 Fetch the colleges point layer from `Colleges_and_Universities/FeatureServer/0`; verify the raw file holds 206 point features carrying `COLLEGE`, `CAMPUS`, `GEOG_TOWN`, `NCES_ID`, `TYPE`, `CATEGORY`, `DEGREEOFFR`, address, phone, and URL.
- [x] 2.3 Fetch the generalized-coast counties layer from `Massachusetts_Counties_with_Generalized_Coastline/FeatureServer/1`; verify 14 polygon features with `COUNTY` and `FIPS_STCO`.
- [x] 2.4 Fetch the generalized-coast municipalities layer from `TownSurveyGenCoast_gdb/FeatureServer/1`; verify 351 polygon features with `TOWN`, `TOWN_ID`, `COUNTY`, `FIPS_STCO`, and `TYPE`.
- [x] 2.5 Download and cache the TIGER 2025 national CBSA zip, skipping the download when the cached file is already present and complete; verify the archive reads as a polygon layer and a re-run makes no second HTTP request.

## 3. Build the area layers

- [x] 3.1 Transform municipalities into `docs/data/municipality.geojson` with `area_id` from `TOWN_ID`, display `name`, `layer: "municipality"`, `municipality_type` from `TYPE`, and the containing `county_id`; verify 351 features and that every `name` is non-empty and unique.
- [x] 3.2 Derive `docs/data/county.geojson` by dissolving the municipality polygons on `county_id`, taking `area_id` from `FIPS_STCO`, a display `name`, and `layer: "county"`; verify 14 features, unique names, and that the dissolved union equals the municipality union to floating-point tolerance.
- [x] 3.3 Cross-check the dissolved counties against the fetched MassGIS county layer; verify every county matches its MassGIS polygon in area within 1 percent and that a deliberately corrupted `county_id` fails the check.
- [x] 3.4 Determine CBSA membership from TIGER by county overlap and derive `docs/data/cbsa.geojson` by dissolving counties, keeping the full `NAMELSAD` as the display name; verify all 14 counties are assigned to exactly one area, that `Boston-Cambridge-Newton, MA-NH` covers its five counties and keeps its full name, and that the published union equals the municipality union.
- [x] 3.5 Confirm the out-of-state areas need no area threshold; verify that the 9 areas which merely graze the state line (Manchester-Nashua, Keene, Brattleboro, Bennington, Hudson, Torrington, Hartford, Albany, Putnam) are absent because they contain no Massachusetts county.
- [x] 3.6 Write `docs/data/cbsa.geojson` with `area_id` from `CBSAFP`, display `name`, `layer: "cbsa"`, and metro-or-micro from `MEMI`; verify each `area_id` is a distinct 5-digit code.
- [x] 3.7 Verify the three layers nest exactly: every municipality lies within its county, every county within its statistical area, and each coarser area is reproduced exactly by the finer areas inside it.

## 4. Build the campus layer and the assignment

- [x] 4.1 Implement the `campus_id` slug from `COLLEGE` plus `CAMPUS`; verify all 206 records produce distinct IDs, that the IDs are unchanged when the input rows are shuffled, and that `NCES_ID` is published as a plain attribute and used nowhere as identity.
- [x] 4.2 Implement the `institution_id` slug from `COLLEGE` alone; verify exactly 160 distinct IDs across the 206 records, that aggressive normalization of the institution names produces no collisions, that all 7 Harvard campus features share one `institution_id`, and that the 114 records with an empty `CAMPUS` have `campus_id` equal to `institution_id`.
- [x] 4.3 Compute the authoritative point-in-polygon assignment against full-resolution geometry for all three layers; verify each of the 206 campuses gets exactly one county and one municipality, and zero or one CBSA.
- [x] 4.4 Write `docs/data/campus.geojson` in EPSG:4326 with `campus_id`, `institution_id`, the `institution` display name, and the three area IDs in each feature's properties, using explicit property names (`institution_type`, not the source `TYPE`); verify 206 features, longitude-first coordinates, that every feature carries both identifiers, and that a sample campus reads correctly end to end.
- [x] 4.5 Write `docs/data/assignments.json` with `campus_ids`, `institution_ids`, `campus_count`, and `institution_count` for every area in all three layers, including areas whose memberships are empty; verify the reverse index round-trips against the campus properties, that all 14 counties and 351 municipalities are present as keys, that each count equals the length of its array, and that each `institution_ids` list holds no duplicates.
- [x] 4.6 Verify the institution dimension against known figures: Boston reports 38 campuses and 35 institutions, Cambridge reports 9 and 6, Worcester reports 14 and 14; and confirm Harvard appears in the `institution_ids` of both Suffolk and Middlesex counties.
- [x] 4.7 Assert that summed per-area institution counts exceed the 160 statewide distinct institutions while summed campus counts equal exactly 206; verify the test documents the non-additivity so a later change cannot present a summed institution figure as a total.
- [x] 4.8 Compare each computed municipality against the source `GEOG_TOWN` attribute and report every discrepancy with the campus and both values; verify the report is emitted and that a deliberately altered fixture row is flagged.

## 5. Simplify for the web

- [x] 5.1 Simplify the municipality layer through `topojson` before the dissolves so shared borders simplify once and the derived layers inherit them; verify no gap appears between a known adjacent municipality pair (for example Boston and Brookline), that all three layers still share one outer boundary, and that each published file meets the chosen size budget.
- [x] 5.2 Re-run the point-in-polygon assignment against the simplified geometry and assert it matches the full-resolution assignment; verify the check fails when the tolerance is deliberately set far too coarse.
- [x] 5.3 Record the chosen tolerance and the resulting file sizes; verify both appear in the provenance output.

## 6. Provenance and validation

- [x] 6.1 Write `docs/data/provenance.json` naming each source, its service URL or TIGER vintage, the fetch date, the published feature count per layer, and the statewide distinct institution count; verify every published layer has an entry whose count matches the file and that the institution count reads 160.
- [x] 6.2 Implement the failing validations: a campus missing a county or municipality, a campus in two features of one layer, and a layer whose count disagrees with its source; verify each raises on a purpose-built fixture and that a failing run leaves the previously published outputs untouched.
- [x] 6.3 Implement the informational reports: campuses in no CBSA, areas with no campuses, and municipality discrepancies; verify these print counts and the run still exits zero.
- [x] 6.4 Run `uv run ma-geo validate` against the real published outputs; verify it passes and the informational counts are plausible for Massachusetts.

## 7. Wrap up

- [x] 7.1 Run the full pipeline from an empty `data/raw/` and confirm it reproduces byte-identical committed outputs on a second run; verify `git status` is clean after the re-run.
- [x] 7.2 Document the pipeline commands, the `docs/data/` file contract, and the note that New England CBSAs follow county lines in the README; verify a reader can regenerate the data from the README alone.
- [x] 7.3 Commit the derived outputs and confirm no raw download was staged; verify `git show --stat HEAD` lists only `docs/data/` and the project files.
