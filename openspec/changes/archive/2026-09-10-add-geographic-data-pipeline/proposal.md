## Why

The project has a README describing an interactive map and table, but no data. Every feature in that README depends on one thing first: knowing which colleges and universities fall inside which counties, municipalities, and Core Based Statistical Areas. That relationship does not exist in any single published dataset, so it has to be computed from the four upstream sources and published as web-ready files the Leaflet page can fetch directly from GitHub Pages.

This change acquires and prepares that data. It stops at the data boundary: no map, no table.

## What Changes

- Add a reproducible Python data pipeline (`uv`, `pyproject.toml`) that fetches the four upstream sources and writes web-ready outputs.
- Fetch the source layers:
  - MassGIS Colleges and Universities, a point layer of 206 campus records (EPSG:26986).
  - MassGIS Massachusetts Counties, 14 polygons.
  - MassGIS Massachusetts Municipalities, 351 polygons carrying `TOWN`, `TOWN_ID`, and `COUNTY`.
  - Census TIGER 2025 national CBSA shapefile, filtered to the areas that intersect Massachusetts.
- Build all three area layers from one geometry source: simplify the 351 municipality polygons, dissolve them into the 14 counties, then dissolve those into the statistical areas. The layers therefore share one outer boundary exactly and nest without slivers, which clipping three independently-drawn coastlines cannot achieve.
- Use TIGER for CBSA membership and official names rather than geometry, so the third layer covers only Massachusetts while keeping each area's full official name (`Boston-Cambridge-Newton, MA-NH`). In New England a CBSA is a union of whole counties, and the data confirms it exactly.
- Compute the campus-to-geography assignment by point-in-polygon: each of the 206 campus records is assigned its county, its municipality, and its CBSA (which may be absent).
- Carry an explicit institution identity on every campus record, so a geography can report both its campus count and its distinct-institution count. The 206 campuses belong to 160 institutions; 24 institutions have several campuses and 21 of those cross municipal lines, so the two counts genuinely differ — Boston holds 38 campuses but 35 institutions.
- Publish four GeoJSON layers in EPSG:4326 plus one assignment table carrying campus IDs, institution IDs, and both counts per area, simplified and small enough to fetch over Pages.
- Validate the result: every campus lands in exactly one county and one municipality, counts match the source layers, and any campus outside every CBSA is reported rather than silently dropped.
- Commit the derived outputs (GitHub Pages serves them statically) and gitignore the raw downloads, which the pipeline can re-fetch.

## Capabilities

### New Capabilities

- `geographic-data`: Acquiring the upstream college, county, municipality, and CBSA sources and preparing them into web-ready map layers plus a campus-to-geography assignment table, with the correctness guarantees the map and table will rely on.

### Modified Capabilities

None. This is the project's first capability.

## Impact

- **New dependencies**: Python with `uv` and a `pyproject.toml`; a geospatial stack for reading shapefiles, reprojecting, and point-in-polygon joins.
- **New code**: a data pipeline package plus its entry point, run on demand rather than on every page load.
- **New committed data**: the derived GeoJSON layers and assignment table, served by GitHub Pages.
- **Repository**: adds an ignored raw-download directory and the pipeline's project files at the repository root.
- **Downstream**: the published file layout and field names become the contract the future Leaflet map and table are built against. No existing code is affected, because there is none yet.
- **Upstream risk**: the MassGIS layers are hosted ArcGIS feature services that are revised in place and the TIGER file is vintage-stamped, so the pipeline records what it fetched and when.
