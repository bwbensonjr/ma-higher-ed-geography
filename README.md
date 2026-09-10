# Massachusetts College and University Geography 

Look at Massachusetts institutions of higher education by geographic area

## Features

- An interactive map with a placemark for each of the 206 campuses over a light base map, so a campus reads in real geographic context at every zoom
- A geographic layer selector over *Counties*, *Municipalities*, and *Statistical Areas*, each area shaded by how many campuses it holds
- A table below the map with three modes
  - Nothing selected: every campus, alphabetical by institution, with its geographies as clickable links into the map
  - A layer selected: grouped by that layer's areas, each heading carrying the area's campus and institution counts
  - One geography selected: only that geography's campuses, with the map brought to it
- One row is one campus, not one institution, so a row's address, municipality, county, and statistical area are all single-valued and each row is exactly one marker. Harvard therefore appears on seven rows
- The selected layer and geography live in the URL, so any view is a shareable link and the browser's back button steps through selections
- Hosted from `docs/` by GitHub Pages, with no server and no build step

## Viewing the page

Any static file server works, because that is all Pages is:

```sh
uv run python -m http.server -d docs 8000   # then open http://localhost:8000
```

The page fetches about 306 KB at load (the campus points, the assignment, the area names, the provenance) and reaches for an area layer's geometry only when you first draw that layer, which is why the initial view does not pay for all 1.6 MB of polygons.

### The base map

Tiles come from [CARTO](https://carto.com/attributions) (their Positron style, over OpenStreetMap data), which is the page's one external dependency. Everything the page *reports* comes from this repository, so if the tile host is slow or blocked the map loses its backdrop and nothing else: markers, layers, selection, and the table all keep working. The test suite runs with the tile host blocked for exactly that reason.

Worth knowing: requesting tiles discloses each visitor's network address and the area they are looking at to CARTO. That is inherent to any hosted base map, and it is named in the page footer rather than left implicit. Leaflet itself is vendored into `docs/vendor/leaflet/` and pinned by checksum, so no third party serves the page's own code.

## Geographic Resources 

- [MassGIS Colleges and Universities](https://www.mass.gov/info-details/massgis-data-colleges-and-universities)
- Geographic Areas
  - [State Outline](https://www.mass.gov/info-details/massgis-data-state-outlines)
  - [Counties](https://www.mass.gov/info-details/massgis-data-counties)
  - [Cities and Towns](https://www.mass.gov/info-details/massgis-data-municipalities)
  - [Core Based Statistical Areas](https://www2.census.gov/geo/tiger/TIGER2025/CBSA/tl_2025_us_cbsa.zip) (restricted to MA)

## Data Pipeline

The map's data is prepared by a Python pipeline and committed to `docs/data/`, which GitHub Pages serves as static files. No upstream data source is contacted at page load; the only external request the page makes is for base map tiles.

```sh
uv run ma-geo fetch      # download the sources into data/raw/ (gitignored, cached)
uv run ma-geo build      # transform them into docs/data/
uv run ma-geo validate   # check the published outputs
uv run pytest            # run the verification suite (pipeline and page)
```

The page's own behavior is verified in a real browser: `pytest` serves `docs/` over a static server and drives Chromium through Playwright. Install the browser once with `uv run playwright install chromium`; without it those tests skip and the pipeline tests still run.

`fetch` reuses a cached download, so re-running `build` while iterating costs no network traffic. Both steps are idempotent: given the same upstream data, `build` writes byte-identical files, so a re-run produces no git diff unless something upstream actually changed.

### Published files

| File | Contents |
| --- | --- |
| `campus.geojson` | 206 campus points, EPSG:4326, each with `campus_id`, `institution_id`, and its `county_id`, `municipality_id`, and `cbsa_id` |
| `county.geojson` | 14 counties |
| `municipality.geojson` | 351 cities and towns |
| `cbsa.geojson` | the 10 statistical areas covering Massachusetts |
| `assignments.json` | per area: `campus_ids`, `institution_ids`, `campus_count`, `institution_count` |
| `area.json` | per area: its display `name`, plus `county_id` for a municipality |
| `provenance.json` | each source, its vintage, the fetch date, feature counts, and the simplification tolerance |

`area.json` exists so the table can name a campus's county, municipality, and statistical area on the first view: those names are otherwise published only inside the layer geometry files, and the campus `city` attribute is the mailing city, which names a different place for 18 of the 206 campuses -- Boston College's main campus is addressed Chestnut Hill and sits in Newton.

Every area carries a stable `area_id` (county and municipality use MassGIS/FIPS codes, statistical areas use the Census `CBSAFP`) plus a display `name`.

### Two things to know about the data

**Campuses and institutions are different counts.** The 206 campus records belong to 160 institutions. 24 institutions have several campuses and 21 of those cross municipal lines, so Boston holds 38 campuses but 35 institutions. Each campus has exactly one municipality and one county, so campus counts add up; an institution is counted in every area it has a campus in, so *institution counts do not add up*. Harvard counts in both Suffolk and Middlesex. Summing `institution_count` across a layer exceeds the 160 in the state, and should never be shown as a total — `provenance.json` carries the statewide figure.

**The statistical-area layer follows county lines.** In New England a Core Based Statistical Area is defined as a union of whole counties, and the Census discontinued the town-based NECTA series, so no town-level equivalent is published any more. Outside Greater Boston, which spans five counties, most of these areas are a single county, and the layer will look much like the county layer. All three area layers are derived from the municipality polygons, so they share one outline exactly and nest without gaps.
