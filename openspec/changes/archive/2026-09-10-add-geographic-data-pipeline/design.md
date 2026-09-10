## Context

See `proposal.md` — Why. The repository is greenfield: a README, this OpenSpec change, and nothing else. There is no existing code, no dependency file, and no published data, so this design also establishes the conventions the map work will inherit.

What the upstream sources actually look like, confirmed against the live services while writing this design:

| Source | Access | Geometry | Count | Key fields |
| --- | --- | --- | --- | --- |
| MassGIS Colleges and Universities | ArcGIS feature service, `Colleges_and_Universities/FeatureServer/0` | Point, EPSG:26986 | 206 | `COLLEGE`, `CAMPUS`, `GEOG_TOWN`, `NCES_ID`, `TYPE`, `CATEGORY`, `DEGREEOFFR`, address/phone/URL |
| MassGIS Counties (generalized coast) | `Massachusetts_Counties_with_Generalized_Coastline/FeatureServer/1` | Polygon | 14 | `COUNTY`, `FIPS_STCO` |
| MassGIS Municipalities (generalized coast) | `TownSurveyGenCoast_gdb/FeatureServer/1` | Polygon | 351 | `TOWN`, `TOWN_ID`, `COUNTY`, `FIPS_STCO`, `TYPE` |
| Census TIGER 2025 CBSA | `www2.census.gov/geo/tiger/TIGER2025/CBSA/tl_2025_us_cbsa.zip`, 35 MB | Polygon, EPSG:4269 | national | `CBSAFP`, `NAME`, `NAMELSAD`, `LSAD`, `MEMI` |

Constraints that shape the approach:

- The colleges source is **point-only**. There is no campus-boundary polygon layer, so the README's "in or overlap with" reduces to point-in-polygon. A campus point falls in exactly one municipality and one county.
- Every MassGIS layer reports `maxRecordCount: 2000` and supports `f=geoJSON`, so each fetch is a single unpaged request.
- TIGER 2025 has no `NECTA` directory. The Census discontinued the town-based New England City and Town Areas, so the county-based CBSA file named in the README is the only available option for the third layer. In New England the CBSA is a union of whole counties, which means the third layer's boundaries follow county lines.
- GitHub Pages serves static files only. Nothing can run at request time.

## Goals / Non-Goals

**Goals:**

- One command reproduces every published output from the upstream sources.
- The published file layout and field names are a deliberate contract, since the map and table will be written against them.
- Validation is part of the pipeline, not a separate manual review step.

**Non-Goals:**

- No map, table, page, or styling. This change stops at the published data files.
- No scheduled or automated refresh. The pipeline is run by hand when a source is revised.
- No campus polygons, enrollment figures, or IPEDS joins.
- No tiling or vector-tile server. Plain GeoJSON only.

## Decisions

### Fetch from the ArcGIS feature services, not the shapefile downloads

MassGIS publishes both downloadable shapefiles and hosted feature services. The pipeline queries the feature services with `f=geoJSON&outFields=<explicit list>&outSR=4326`.

*Why:* the service returns exactly the fields we ask for, already reprojected, in the format we publish, with a documented feature count we can assert against — no zip handling, no `.dbf` field-name truncation, no separate reprojection step. Each layer is one HTTP request.

*Alternative considered:* downloading the shapefile archives. Rejected for the MassGIS layers because it adds unzip and reprojection work for no benefit. **Kept for TIGER**, which is only offered as a 35 MB national zip.

*Trade-off:* the services are revised in place and have no version parameter. The provenance record therefore captures fetch date and feature count, which is what makes a revision visible.

### Campus key is a slug of institution plus campus name

`NCES_ID` looks like the natural key and is not one: 22 of the 206 records have no value at all, and the 184 that do carry only 139 distinct values because satellite campuses repeat their parent institution's ID. `(COLLEGE, CAMPUS)` is exactly 206 distinct — the 206 records cover 160 distinct institutions.

*Decision:* `campus_id` is a deterministic slug of `COLLEGE` plus `CAMPUS` (for example `northeastern-university--burlington`). `NCES_ID` is still published as an attribute for anyone wanting to join to IPEDS, but is never used as an identity.

*Why:* it satisfies the spec's stability requirement, is independent of read order and of the volatile `OBJECTID`, and is human-readable in a URL fragment when the map later wants to deep-link a campus.

*Trade-off:* renaming an institution upstream changes its ID. Acceptable — the alternative, a positional or hash-of-row ID, is stable against renames but breaks on any attribute edit and is unreadable.

*Note:* 114 of the 206 records have an empty `CAMPUS`, so for those the slug reduces to the institution name alone and `campus_id` equals `institution_id`. That is collision-free — a single-campus institution has exactly one of each — but it means the two fields cannot be told apart by inspection, so consumers must read the field they mean rather than pattern-matching the value.

### Institution is a first-class identity, not a display string

A geography's campus count and its institution count are different numbers, and the table needs both. Boston holds 38 campuses belonging to 35 institutions; Cambridge holds 9 campuses belonging to 6. Across the state, 24 institutions have more than one campus, covering 70 of the 206 records, and 21 of those span more than one municipality — Harvard has 7 campuses across Boston and Cambridge, Cape Cod Community College has 4 across Barnstable, Bridgewater, and Plymouth.

*Decision:* `institution_id` is a deterministic slug of `COLLEGE` alone, published on every campus feature beside the `institution` display name. All campuses of one institution carry the same value.

*Why `COLLEGE` is trustworthy as a key:* it yields exactly 160 distinct values across the 206 records, and normalizing aggressively — lowercasing and stripping every non-alphanumeric character — produces no collisions at all. There are no near-duplicate spellings of the same institution to reconcile, so no fuzzy matching or hand-maintained alias table is needed.

*Why an ID rather than counting the name:* the count would work today by deduplicating the display string, but that silently makes a display field load-bearing. A future change that normalizes capitalization, appends a campus qualifier, or fixes a typo in one of two records would split one institution into two without any validation noticing. An explicit identifier makes that a spec violation the pipeline can check.

*Consequence — institution counts do not sum:* Harvard is counted in both Suffolk and Middlesex, so adding up per-area institution counts across a layer overshoots the 160 statewide total. Campus counts do sum, because a campus has exactly one municipality and one county. The spec states this, and the map and table must not present a summed institution figure as a total.

*Alternative considered:* deriving institutions from `NCES_ID`. Rejected for the same reason it fails as a campus key — 22 records have no value, so 22 campuses would fall out of the institution dimension entirely.

### Area IDs come from the published FIPS and MassGIS codes

`county` uses the 5-digit state-county FIPS from `FIPS_STCO` (Suffolk is `25025`), `municipality` uses MassGIS `TOWN_ID` (1–351), `cbsa` uses the Census `CBSAFP`.

*Why:* all three are externally defined and stable, so the assignment survives a source revision and can be joined against outside data. Names are for display only and never for identity — municipality names collide with county names in Massachusetts (Barnstable, Nantucket, Plymouth, and Franklin are each both).

### Use the generalized-coast variants of both polygon layers

MassGIS offers each boundary layer twice: extending into the ocean to the state's legal water boundary, or clipped to a generalized coastline.

*Decision:* use the generalized-coast variants for counties and municipalities alike.

*Why:* a map that shades open ocean looks wrong, and the files are smaller. Since the published county geometry is dissolved from the municipalities, this choice is what keeps the ocean out of every layer at once. The counties layer is fetched in the same treatment so that the cross-check compares like with like.

*No campus is lost:* campuses are buildings on land, so clipping to the coastline cannot drop a point.

### All three area layers are derived from one geometry source

The spec requires the three area layers to share one outer boundary and to nest exactly. Clipping cannot deliver that, and the reason is worth recording so it is not retried:

- The MassGIS county layer and the MassGIS municipality layer do not render the coastline identically. Their unions differ by 1.99e-4 square degrees, roughly 1.8 sq km, at full resolution.
- Clipping the county layer to the municipality-derived mask does not fix it. The clipped union still differs from the mask by 1.0e-4 square degrees, because a GEOS intersection along two near-coincident boundaries emits slightly different vertices rather than reusing one.
- Because the inputs are not identical, `topojson` cannot recognise the coastline as one shared arc, so simplification moves it differently in each layer. A single shared topology with coordinate quantization was tried and left the layers 1e-4 to 3e-4 apart, marginally worse.

*Decision:* build every area layer from the municipality polygons. Simplify the 351 municipalities once, dissolve them on `county_id` to get the 14 counties, then dissolve the counties on CBSA membership to get the statistical areas. Measured symmetric difference between each layer's outline and the municipality union: 2.3e-16, which is floating-point zero.

*Why this is sound rather than a shortcut:* in New England a CBSA is defined as a union of whole counties, and the data bears that out exactly. Each of the 10 Massachusetts CBSAs covers its member counties at a fraction of 0.9997 to 1.0000, and all 14 counties are accounted for exactly once, Boston-Cambridge-Newton taking five. The sub-unity fractions are the TIGER-versus-MassGIS coastline disagreement, not real geography. So the county union *is* the statistical area, restricted to Massachusetts, by definition.

*What TIGER is still used for:* membership and official names. `CBSAFP` gives the identifier, `NAMELSAD` the full multi-state name, `MEMI` the metropolitan or micropolitan kind, and the county overlap gives membership. Its geometry is not published.

*Consequences:*

- Counties end up 0.22 percent different in area from the MassGIS county polygons, being consistent with the towns instead. The MassGIS county layer is still fetched and used as a cross-check: a large divergence would mean a `county_id` attribute error in the municipality layer.
- The nine out-of-state areas that grazed the state line disappear on their own, because none contains a Massachusetts county. No area threshold is needed to filter them, and no sliver fragments are produced to drop.
- Simplification happens once, on one layer, before the dissolves, so the shared arcs are shared by construction.

*Alternative considered:* clipping, with the "share one outer boundary" scenario weakened to a tolerance. Rejected: the guarantee is what lets the map switch layers without the coast jumping, and it is achievable exactly.

### The MassGIS State Outline layer, evaluated and not used

An earlier draft of this design claimed MassGIS publishes no standalone state-outline layer. That was wrong: `outline25k.zip` in the MassGIS download bucket holds `OUTLINE25K_POLY`. It is not usable as a clip mask here:

- It is dated 2006, while the town survey layer this pipeline uses was revised in 2022. Their unions differ by 1.5e-2 square degrees, about 137 sq km, or 0.65 percent of the state, concentrated along the coast where most campuses are.
- It is 918 separate polygons, the mainland plus every island, so it clips differently around islands than the town layer does.

Using it as the mask would make the statistical-area layer visibly disagree with the county and municipality boundaries along the shoreline. The dissolve decision above removes the need for any external mask, so the layer is left unused. It remains a reasonable source for a decorative state border should the map want one.

### Topology-preserving simplification via `topojson`

The spec forbids visible gaps between adjacent areas. Ordinary Douglas-Peucker simplification, applied polygon by polygon, moves a shared border differently for each of the two polygons that share it and tears the layer apart.

*Decision:* simplify the polygon layers through the `topojson` package, which decomposes the layer into shared arcs, simplifies each arc once, and reassembles — so a shared border stays shared. Output is converted back to GeoJSON for publication.

*Alternatives considered:* `shapely.simplify` per polygon, rejected for exactly the tearing above; `mapshaper`, which does this well but adds a Node toolchain to an otherwise pure-Python project; publishing unsimplified geometry, rejected because the full-resolution municipalities layer is far too large to fetch as one file.

*Where it runs:* on the municipality layer only, before the dissolves. The counties and statistical areas inherit the simplified boundaries, so every layer keeps the same arcs.

*Guard:* after simplification, re-run the point-in-polygon assignment against the simplified geometry and assert it matches the assignment computed against full resolution. That is what the spec's "does not move any campus point across an area boundary" scenario tests, and it catches an over-aggressive tolerance automatically. Simplify the **published** geometry; compute the **authoritative** assignment from full resolution. Measured: the default tolerance moves no campus, and the first tolerance that does is 0.005, twenty-five times coarser.

### Assignment is published both denormalized and as an index

The three area IDs, the `campus_id`, and the `institution_id` are written directly into each campus feature's properties. A separate `assignments.json` carries the reverse direction: for each area ID in each layer, the campus IDs it contains, the distinct institution IDs those campuses belong to, and both counts — including areas whose memberships are empty.

```json
{
  "county": {
    "25025": {
      "campus_ids": ["..."],
      "institution_ids": ["..."],
      "campus_count": 38,
      "institution_count": 35
    }
  }
}
```

*Why:* the map's default view needs campus points with their geographies in one fetch, and the table's grouped-by-layer mode needs the reverse lookup without scanning all 206 campuses per group. Both are small; the duplication costs a few kilobytes and saves the browser from building an index on load. The pipeline writes both from one in-memory relation, so they cannot disagree.

*Why the counts are stored and not just the array lengths:* the grouped table renders "35 institutions, 38 campuses" in every group heading, and a future summary view may want counts without the memberships. Storing them costs a few bytes per area. Because they are redundant, validation asserts each count equals the length of its array, so a stale count cannot survive a run.

### Published layout: `docs/data/`

```
docs/data/
  campus.geojson        # 206 points, EPSG:4326, campus/institution/area IDs in properties
  county.geojson        # 14 polygons
  municipality.geojson  # 351 polygons
  cbsa.geojson          # CBSAs intersecting MA, clipped to the mask
  assignments.json      # area ID -> campus IDs, institution IDs, and both counts
  provenance.json       # source, version/vintage, fetch date, feature count
```

*Why `docs/`:* GitHub Pages can serve from `main`'s `docs/` folder with no branch juggling and no build step, and the future map page lands beside its data as `docs/index.html` fetching `./data/`. Relative paths mean the site works identically on Pages and from a local static server.

*Alternative considered:* a `gh-pages` branch. Rejected as needless ceremony for a static site with no build.

### Raw downloads are ignored; derived outputs are committed

`data/raw/` is gitignored and holds the fetched GeoJSON responses and the TIGER zip. `docs/data/` is committed.

*Why:* Pages can only serve what is committed, so the derived files must be in git. The raw inputs are tens of megabytes, re-fetchable by the pipeline, and would otherwise sit in history forever. Caching them locally does mean iterating on the transform costs no repeated downloads.

### Tooling

Python with `uv` and a `pyproject.toml`, per the project guidelines. `geopandas` (with `shapely` and `pyogrio`) for the read, dissolve, clip, and spatial join; `topojson` for simplification; `httpx` or `requests` for the fetches. A single `uv run` entry point with `fetch`, `build`, and `validate` steps so a source can be re-fetched without rebuilding, and the transform re-run without re-fetching.

## Risks / Trade-offs

- **MassGIS revises layers in place, with no version handle** → provenance records fetch date and feature count, and the count assertions in validation fail loudly on a schema or population change rather than publishing quietly-different data.
- **A campus point may sit within metres of a municipal boundary, so simplification could reassign it** → the assignment is computed at full resolution and re-checked against the simplified geometry; a mismatch fails the run.
- **`TYPE` means different things in different layers** (institution type on campuses, `C`/`T` city-or-town on municipalities) → published property names are explicit (`institution_type`, `municipality_type`) rather than passing the source names through.
- **In New England, CBSA boundaries follow county lines**, so the third layer is coarser than "Municipal Areas" in the README suggests, and its groupings will look much like the county layer's outside Greater Boston → this is a property of the discontinued NECTA series, not something the pipeline can fix; worth noting in the README when the map ships.
- **Simplification tolerance is a judgement call** → pick it against a stated per-file size budget and record the chosen tolerance in provenance, so a later change can revisit it with the numbers visible.
- **Published counties differ from the MassGIS county polygons by 0.22 percent** in area, being dissolved from the towns rather than taken from that layer → the MassGIS layer is fetched and compared on every run, so a real divergence, such as a mislabelled `county_id`, fails the build rather than reshaping a county silently.
- **Institution counts are per-area and non-additive**, so a table that sums them across a layer will report more than the 160 institutions in the state → the spec forbids presenting a summed institution figure as a total, and the provenance record carries the statewide distinct institution count so the correct number is always available without summing.
- **Nantucket and other outlying areas may fall outside every CBSA** → the spec already makes an absent CBSA assignment legitimate and reported, so this surfaces as an informational count instead of a failure.

## Open Questions

- The exact simplification tolerance and per-file size budget. Deferrable: it is a number tuned during implementation against the guard described above, and it changes no requirement, no interface, and no task.
