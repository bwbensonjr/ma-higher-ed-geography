# Massachusetts College and University Geography 

Look at Massachusetts institutions of higher education by geographic area

## Features 

- An interactive map with placemarks for each college and university
- The ability to select a geographic layer like *Counties*, *Municipalities*, or *Municipal Areas*
- A table below the map with several modes
  - When no specific geographic layer (like *Municipality*) or geography (like *Boston*) is selected, show the full list of colleges and universities sorted alphabetically with details and columns for the geographies that can be clicked to select that particular geography in the map.
  - When a geographic layer like *Counties* is selected the list should be grouped by layer members (like *Suffolk*) and the group should contain the colleges and universities that are in or overlap with that group's geography.
  - When a specific geography (like *Boston*) the table should be restricted to the colleges and univerisities that are in or overlap with that geography.
- The web page is hosted in the GitHub repository in Pages. 

## Geographic Resources 

- [MassGIS Colleges and Universities](https://www.mass.gov/info-details/massgis-data-colleges-and-universities)
- Geographic Areas
  - [State Outline](https://www.mass.gov/info-details/massgis-data-state-outlines)
  - [Counties](https://www.mass.gov/info-details/massgis-data-counties)
  - [Cities and Towns](https://www.mass.gov/info-details/massgis-data-municipalities)
  - [Core Based Statistical Areas](https://www2.census.gov/geo/tiger/TIGER2025/CBSA/tl_2025_us_cbsa.zip) (restricted to MA)

## Data Pipeline

The map's data is prepared by a Python pipeline and committed to `docs/data/`, which GitHub Pages serves as static files. Nothing is fetched from upstream at page load.

```sh
uv run ma-geo fetch      # download the sources into data/raw/ (gitignored, cached)
uv run ma-geo build      # transform them into docs/data/
uv run ma-geo validate   # check the published outputs
uv run pytest            # run the verification suite
```

`fetch` reuses a cached download, so re-running `build` while iterating costs no network traffic. Both steps are idempotent: given the same upstream data, `build` writes byte-identical files, so a re-run produces no git diff unless something upstream actually changed.

### Published files

| File | Contents |
| --- | --- |
| `campus.geojson` | 206 campus points, EPSG:4326, each with `campus_id`, `institution_id`, and its `county_id`, `municipality_id`, and `cbsa_id` |
| `county.geojson` | 14 counties |
| `municipality.geojson` | 351 cities and towns |
| `cbsa.geojson` | the 10 statistical areas covering Massachusetts |
| `assignments.json` | per area: `campus_ids`, `institution_ids`, `campus_count`, `institution_count` |
| `provenance.json` | each source, its vintage, the fetch date, feature counts, and the simplification tolerance |

Every area carries a stable `area_id` (county and municipality use MassGIS/FIPS codes, statistical areas use the Census `CBSAFP`) plus a display `name`.

### Two things to know about the data

**Campuses and institutions are different counts.** The 206 campus records belong to 160 institutions. 24 institutions have several campuses and 21 of those cross municipal lines, so Boston holds 38 campuses but 35 institutions. Each campus has exactly one municipality and one county, so campus counts add up; an institution is counted in every area it has a campus in, so *institution counts do not add up*. Harvard counts in both Suffolk and Middlesex. Summing `institution_count` across a layer exceeds the 160 in the state, and should never be shown as a total — `provenance.json` carries the statewide figure.

**The statistical-area layer follows county lines.** In New England a Core Based Statistical Area is defined as a union of whole counties, and the Census discontinued the town-based NECTA series, so no town-level equivalent is published any more. Outside Greater Boston, which spans five counties, most of these areas are a single county, and the layer will look much like the county layer. All three area layers are derived from the municipality polygons, so they share one outline exactly and nest without gaps.
