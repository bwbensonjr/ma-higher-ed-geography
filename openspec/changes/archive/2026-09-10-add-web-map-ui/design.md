## Context

See proposal.md - Why. The data side is done and archived: `docs/data/` holds 206 campus points, three nesting area layers, an assignment keyed by area, and a provenance record. `docs/` holds nothing else. The relevant constraints come from that data and from the hosting:

- **Sizes.** `campus.geojson` 174 KB, `assignments.json` 101 KB, `provenance.json` 4 KB, `county.geojson` 414 KB, `municipality.geojson` 782 KB, `cbsa.geojson` 390 KB. The three area layers together are 1.6 MB, six times the rest.
- **Where names live.** An area's display name is published only inside its layer's geometry file, so naming a campus's county on the first view would have meant fetching all 1.6 MB of geometry. The campus `city` attribute is not a substitute: it is the mailing city, and it names a different place than the assigned municipality for 18 of the 206 campuses. Hence `area.json` below.
- **Shapes.** Campus properties are already page-ready: display fields plus `campus_id`, `institution_id`, and the three area ids (`county_id`, `municipality_id`, `cbsa_id`, the last possibly absent). Area features carry `area_id`, `layer`, `name`, and municipalities also carry `county_id`. `assignments.json` is `{layer: {area_id: {campus_ids, institution_ids, campus_count, institution_count}}}`. Every join the page needs is a lookup on data already published; no spatial work is left.
- **Counts.** 206 campuses, 160 institutions. Per-area institution counts are non-additive and `provenance.json` carries the statewide 160.
- **Hosting.** GitHub Pages serving `docs/` on the default branch. Static files only, no server, no build step at serve time, and this is a Python repository with no Node toolchain.
- **Base map.** The page draws third-party tiles. That is a deliberate reversal of an earlier draft of this design, which had the page contact no host but its own origin and use the published geometry as its cartographic base; the cost was that a visitor zoomed into Boston saw a marker with no streets around it. Tiles buy that detail back, and the constraint that replaces the old one is narrower: the page's *data* still comes only from the repository, so tiles affect the backdrop and nothing the page reports.
- **Keyless tiles only.** A public static page has nowhere to keep an API key, which decides the provider question before cartography does. See the basemap decision below, and the way the first choice failed.

## Goals / Non-Goals

**Goals:**

- One page whose entire visible state is a function of a small explicit state value, so map and table can never disagree about what is selected.
- A first view that costs about 306 KB of the repository's own data, with the 1.6 MB of area geometry fetched only as layers are actually drawn.
- Real geographic context at every zoom, from the whole state down to the street a campus sits on.
- Behavior that is verifiable by automated test, not only by looking at it, and testable without reaching a tile host.
- No Node toolchain and no bundler.

**Non-Goals:**

- Any spatial computation in the browser, and any per-area field the data does not already publish (bounds are derived from geometry at draw time).
- Client-side routing beyond layer and geography, a permalink to an individual campus, or map state (zoom, center) in the URL.
- Self-hosting or caching tiles, offline use, and any tile provider requiring an API key.
- Virtualized or paginated table rendering; the table is at most 206 rows.
- Marker clustering, printing, and data export.

## Decisions

### Static page, no build step, Leaflet vendored into the repository

Chosen with the user. `docs/index.html` plus a stylesheet and hand-written ES modules; Leaflet's `leaflet.js` and `leaflet.css` are committed under `docs/vendor/leaflet/<version>/` with the version in the path and recorded alongside its upstream URL and checksum, so what is served is reviewable and pinned.

Vendoring is still worth it now that the page calls a tile host anyway: the tile dependency is a backdrop that degrades to a grey rectangle, while a CDN failure for `leaflet.js` is a blank page. Pinning by checksum also means the code under review is the code served.

*Alternatives:* Leaflet from a pinned CDN URL - less committed code, but it turns a third-party outage into a total failure rather than a cosmetic one. A bundled front end (Vite) - more capable, but it adds an npm toolchain and a build artifact to a Python repository for a page of this size.

### A light grey tile base map (Esri light gray canvas), drawn beneath everything

The map draws Esri's World Light Gray Base: muted cartography by design, keyless, attributed to Esri and OpenStreetMap. Chosen because this page's subject is shaded polygons with markers on top, and a colourful base map fights both. A grey canvas keeps the choropleth classes distinguishable and leaves the campus markers the brightest thing on screen. Note Esri's `{z}/{y}/{x}` tile order, which is not the usual one.

It renders only through zoom 16, so `maxNativeZoom` lets Leaflet upscale to the map's zoom 19 rather than leave the closest zooms blank. Past 16 the backdrop is therefore soft rather than sharp; street geometry and names are still legible, which is what a marker needs for context.

The base map is required to be subordinate, not merely present, which is a real constraint on the polygon styling: area fills need enough opacity to read as classes over grey tiles without hiding the streets that justify having them.

**This decision was made twice.** The page first used CARTO Positron, which is the conventional choice for exactly this job. CARTO now stamps `API KEY REQUIRED` across keyless tiles and serves them with HTTP 200, so no tile error fires, no test fails, and the map looks broken only to a human looking at it. It was caught by opening the published page and looking. Two consequences worth keeping:

- The suite now has a test that fetches tiles over three different cities and asserts they differ, because a watermark or placeholder is byte-identical everywhere. That is the shape of assertion a keyless third-party raster dependency needs; HTTP status is not enough.
- A provider that needs an API key is not merely inconvenient for a public static page, it is unusable: there is nowhere to put the key. That rules out Stadia, Mapbox, and MapTiler as well, and it is why the keyless field is small.

*Alternatives:* OpenStreetMap standard tiles, desaturated in CSS with a `grayscale` filter on the tile pane - keyless and sharp all the way to zoom 19, but the filter greys the labels too and the result is muddier than cartography drawn grey on purpose; OSM's tile usage policy also asks that sites of any real traffic not point at `tile.openstreetmap.org` directly. Full-colour OSM tiles undesaturated - the sharpest option, rejected because the colour competes with both the shading and the markers. Providers requiring an API key - see above. Self-hosted or vendored tiles - defeats the purpose; the whole point is detail the repository is not going to carry.

### Tile failure degrades the backdrop and nothing else

Everything the page reports is read from `docs/data/`, so the tile layer is the one part of the map that can fail on its own. The design keeps that failure cosmetic: tiles are added as a layer and never awaited, no interaction waits on them, and the error path for a failed tile is silence rather than the page's data-failure state. The page must not tell a visitor its data could not be loaded because a tile 404'd.

This also keeps the test suite honest: the browser tests block the tile host by default, so a test can never pass or fail because of a third party, and one test asserts that the page is fully usable in exactly that condition.

### No state outline file

An earlier draft had the pipeline publish a coarsely simplified state outline so the first view was not markers on an empty background. Tiles fill that role, so the outline is dropped: the pipeline publishes no new file, the first view drops from about 335 KB to 279 KB, and the `geographic-data` delta reduces to the consumer-contract validation alone.

*Alternative considered:* keep the outline as an emphasis layer drawn over the tiles so Massachusetts reads as the subject rather than as part of the basemap. Rejected for now because the county layer already does this job whenever a visitor wants a boundary, at no extra cost when they do not.

### A published `area.json` carries the display names, so the table needs no geometry

The pipeline publishes one more file: `{layer: {area_id: {name, county_id?}}}` for all 375 areas, 27 KB written pretty-printed like its siblings (6.7 KB of actual content; the repository writes indented JSON so a diff stays legible, and the file still costs a fourteenth of the smallest area layer). The page fetches it eagerly and renders every geography column from it, which is what lets the default table be complete at first paint while the geometry stays lazy.

*Alternatives:* add a `name` to each `assignments.json` entry - half again as large because it duplicates the file's nesting, and it churns an existing published file that the archived spec and current tests describe; fetch all three layers eagerly - 1.86 MB on every visit, which is the cost the lazy loading exists to avoid; fill the geography columns in only once a layer loads - leaves three columns blank in the view every visitor sees first; use the campus `city` attribute - wrong for 18 campuses, and wrong in exactly the cases a reader would notice, since the row's own link would target a different municipality than the text beside it.

### The URL hash is the single source of truth for selection

State is `{layer, areaId}` encoded as `#layer=county&area=25025`. Every control writes the hash; one `hashchange` handler reads it, normalizes it, and renders. Nothing renders from a click handler directly.

This buys three of the spec's requirements from one mechanism: shareable views, browser back and forward stepping through selections, and the impossibility of map and table drifting out of sync. Unrecognized values normalize to the default view, so a stale link degrades rather than errors.

Sort order and the text filter are deliberately *not* in the hash: they are view preferences rather than the thing being shared, and putting them there would fill a visitor's history with keystrokes. They live in memory and survive layer changes.

*Alternative:* an in-memory state object with the hash written as a side effect - equivalent in the happy path, but it invites a second code path where a click updates state without updating the hash, which is exactly the drift this avoids.

### Switching layers clears the geography selection

The spec permits either resolution. Clearing is chosen because the alternative, mapping a selection into the new layer, has no single correct answer: Suffolk County maps to one CBSA going up but to four municipalities going down. Silently picking one of four would misrepresent the visitor's selection. Clearing is honest and immediately reversible.

### Data loading: three small files eagerly, area geometry lazily, cached by layer

At load, fetch `campus.geojson`, `assignments.json`, `area.json`, and `provenance.json` in parallel, build the indexes, render. Area geometry is fetched by a `loadLayer(name)` that memoizes its in-flight promise, so a first draw fetches, a return draws from memory, and rapid layer switching cannot start two fetches for the same layer. A shared address selecting a county fetches only the county layer.

If one of the four eager files fails, the page reports what is unavailable; a layer geometry failure disables that layer and leaves everything else working; a tile failure reports nothing.

### Indexes are built once at load

`campusById`, `campusesByLayerAndArea` (from the assignment, so membership is read and never recomputed), `areaNameById` per layer from `area.json` at load, geometry-backed `areaById` per layer once that layer is loaded, and a campus list pre-sorted by institution name for the default view. All lookups after that are O(1) or a filter over 206 items.

### Rendering: canvas renderer, and full re-render of the table

Leaflet's canvas renderer for both the polygon layers and the campus markers, drawn as circle markers. 351 polygons and 206 markers as individual SVG nodes is where a page like this becomes slow to pan on a phone; on canvas it is one surface.

The table is rebuilt from state into a detached fragment and swapped in. At 206 rows this is well under a frame, and it keeps the three table modes as one pure function of state rather than three incremental update paths. Grouped mode renders one `<tbody>` per area with the group heading in a spanning header row, which keeps it a single real table for assistive technology.

### Choropleth breaks are per-layer and stated in the legend

The distributions differ by an order of magnitude - a county holds up to 38 campuses, most of the 351 municipalities hold none - so one set of breaks across all three layers would put nearly every county in the top class. Each layer declares its own fixed breaks with an open-ended top class, and the legend re-renders with the layer so the shading is always self-describing. Zero is rendered as a distinct empty style rather than as the lightest shade, so "no campuses" is not read as "few campuses". Fixed breaks are preferred over quantiles because quantile classes shift meaning as data changes and cannot be compared between layers.

### Verification: page logic tested through a real browser, driven from pytest

The page's testable substance is data shaping, not pixels: indexing, the three table modes, count presentation, hash parsing and normalization, and lazy-load behavior. Those live in dependency-free ES modules with no DOM or Leaflet imports, exercised in a real browser via Playwright's Python package as a dev-only dependency, driven from the existing `pytest` suite. A handful of end-to-end checks cover the wiring the modules cannot: markers render, selecting an area restricts map and table together, and a shared address restores the view.

This keeps one test runner and one language for the repository's tooling.

*Alternatives:* `node:test` or Vitest - the natural fit for JS, but adds a Node toolchain the no-build decision exists to avoid; jsdom via Python - no real browser, so it cannot exercise Leaflet at all; manual verification only - rejected, the spec's scenarios are exactly the things that break silently.

### The pipeline additions stay inside the existing commands

`build` gains the `area.json` output; `validate` gains the consumer-contract check. No new entry point, and the existing published outputs stay byte-identical for a given source vintage.

## Risks / Trade-offs

- **The base map is a third party the page depends on at load, and its terms can change under the page.** That is not hypothetical here: CARTO started requiring an account and the page's basemap silently became a watermark. Mitigation: swapping providers is a URL and an attribution string, because nothing else depends on which tiles arrive; tile failure is cosmetic by design; and the suite asserts the tiles are real rather than trusting HTTP 200. Anyone re-reading this should expect to do it again.
- **Tile requests disclose each visitor's address and the area they are viewing to Esri.** This is inherent to any third-party base map and is the concrete privacy cost of this decision. Mitigation: name the provider in the attribution so the disclosure is visible rather than hidden, and keep the page free of any other external request, so tiles remain the only thing a visitor's browser tells anyone else about.
- **The backdrop is soft past zoom 16.** Esri's grey canvas has no tiles beyond it, so the closest zooms are upscaled. Mitigation: `maxNativeZoom`, which keeps streets and names legible instead of blank; if sharpness at 19 ever matters more than a grey canvas, undesaturated OSM tiles are the trade.
- **Shading over tiles can end up illegible.** Fill opacity that reads clearly on white can mud together over grey streets. Mitigation: the classes are chosen and checked against the actual basemap rather than on a blank background, and the spec requires the classes to stay distinguishable over the tiles.
- **351 polygons plus 206 markers on a phone.** Mitigation: canvas renderer, already-simplified geometry, and the municipality layer fetched only on demand. If panning still stutters, the fallback is to draw only the areas intersecting the viewport, which needs no data change.
- **The field names are now a two-way contract.** A rename in the pipeline breaks the page at load, and the page is not exercised by the pipeline's tests. Mitigation: this change's consumer-contract validation, which fails the run rather than publishing outputs the page cannot read.
- **Playwright needs a browser download.** A first-time `pytest` run must install its browser, which is a slow step and needs network. Mitigation: the browser-driven tests are marked and skipped with a clear message when the browser is absent, so the pipeline tests still run offline.
- **Publishing makes the repository's Pages URL a public site.** Enabling Pages on `docs/` is a repository setting outside this change's files and must be done deliberately by the owner.
- **Institution counts invite a wrong total.** Any later contributor adding a summary row can sum the wrong column. Mitigation: the count helpers expose a statewide institution figure only from provenance, and a test asserts no summed institution total is ever rendered.

## Migration Plan

No data migration and no existing consumers. Deployment is: run `uv run ma-geo build` to publish `area.json` alongside the unchanged existing outputs, commit the page and vendored Leaflet, merge to the default branch, then set Pages to serve `docs/` on that branch.

Rollback is reverting the commit; the data files are unaffected by the page, and disabling Pages takes the site down without touching the repository.

## Open Questions

- The exact choropleth break values per layer, and the fill opacity that keeps them legible over grey tiles, are worth tuning once the shading is on screen over the real basemap. This changes constants and a legend label, not the approach.
- Whether to offer a second, sharper basemap for the closest zooms, given Esri's zoom-16 ceiling. Additive, and better judged after using the grey one.
- Whether to give the site a friendlier Pages domain than the default `*.github.io` URL. Independent of everything here and decidable after the page is live.
