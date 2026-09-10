## Why

The data pipeline publishes 206 campus points, three nesting area layers, and a campus-to-geography assignment to `docs/data/`, but `docs/` has no page that reads them. Every feature the README promises -- the interactive map, the layer selector, and the three-mode table -- is still unbuilt, so the published data currently has no consumer and the repository serves nothing at its Pages URL.

This change builds that page. It consumes the `geographic-data` contract exactly as published and adds no spatial computation in the browser.

## What Changes

- Add a static single-page site at `docs/index.html` with its stylesheet and ES modules, served directly by GitHub Pages with no build step and no request to any host but the repository's own.
- Vendor Leaflet's JavaScript and CSS into the repository, pinned by version and checksum, so the library the page runs is reviewable in the repository rather than whatever a CDN serves that day.
- Draw a light grey base map of tiles beneath the page's own content, so a campus marker sits in real geographic context and a visitor who zooms in sees the streets around it. The base map is the page's one external dependency, and it is deliberately subordinate: the area shading and the campus markers have to stay legible over it. It must also be keyless, since a public static page has nowhere to keep an API key.
- Render the 206 campus points as markers over the base map and the selected area layer, each with a popup carrying the descriptive attributes the campus features already publish (address, telephone, website, type, category, degrees offered).
- Add a geographic layer selector over the three published layers: Counties (14), Municipalities (351), and Statistical Areas (10). The README calls the third one *Municipal Areas*; the published layer is the Core Based Statistical Area layer, and the page will label it *Statistical Areas* to match the official names the data carries, such as `Boston-Cambridge-Newton, MA-NH`.
- Shade each area by its campus count from `assignments.json` and label it on hover, so a layer view answers "where are the campuses" before anything is clicked.
- Make a geography selectable, by clicking it on the map or by clicking it in a table row's geography column, which restricts the map and the table to that geography and offers a way back to the unselected view.
- Add the table below the map with the three modes the README describes: the full alphabetical list when nothing is selected, grouped by area member when a layer is selected, and restricted to one geography's campuses when a geography is selected.
- Make each table row one campus rather than one institution, so a row's address, municipality, county, and statistical area are all single-valued and each row corresponds to exactly one map marker. Harvard therefore appears on several rows.
- Report both counts wherever a count is shown, and never present a summed institution figure as a statewide total, because institution counts are per-area and non-additive. The statewide figure of 160 comes from `provenance.json`.
- Reflect the selected layer and geography in the URL, so a view of Suffolk County is a shareable link and the browser's back button steps back through selections.
- Fetch the small files (`campus.geojson`, `assignments.json`, `area.json`, `provenance.json`) at load and each area layer's geometry only when that layer is first shown, so the initial view does not pay for all 1.6 MB of polygons.
- Extend the pipeline to publish `area.json`, a 27 KB index of area display names for all 375 areas, because those names live only inside the layer geometry files today. The table's geography columns need them on the first view, and the campus `city` attribute cannot stand in: it is the mailing city, which names a different place than the assigned municipality for 18 of the 206 campuses (Boston College's main campus is addressed Chestnut Hill but sits in Newton).
- Show the data's provenance and upstream attribution on the page, including the base map's required attribution, and handle the states a static page can still land in: still loading, a file that failed to fetch, a tile host that is unreachable, and a geography that contains no campuses. Because every fact the page reports comes from the repository's own data, losing the tiles costs the map its backdrop and nothing else.
- Add a verification suite for the page's data-dependent behavior, and extend the existing pipeline validation so a future data run cannot silently break the field names and identifiers the page reads.

## Capabilities

### New Capabilities

- `web-map-ui`: The browser-facing map and table -- how the published layers are rendered, how a layer and a geography are selected, what the table shows in each of its three modes, how campus and institution counts are presented, and how the page behaves while loading, when a fetch fails, and when a geography is empty.

### Modified Capabilities

- `geographic-data`: Two additions, no change to existing requirements. First, publish `area.json`, an index of area display names covering all 375 areas, so a consumer can name a campus's geographies without fetching any layer geometry. Second, validate the published field names and identifiers that the page reads, so a future data run fails rather than publishing outputs that would silently break the page.

The existing outputs are unchanged in content. The area layers, the campus layer, and the assignment keep their current requirements and stay byte-identical, and zoom-to-fit bounds are derived in the browser from geometry already published, so no new per-feature field is required.

## Impact

- **New code**: a static front end under `docs/` (page, stylesheet, ES modules) plus vendored Leaflet assets. No Node toolchain and no bundler is added to this Python repository.
- **Existing code**: the pipeline keeps writing `docs/data/` and its existing outputs stay byte-identical. It gains one published file, `area.json`, and one validation check asserting the field names and identifiers the page depends on, so a data change that would break the page fails the pipeline instead.
- **Repository layout**: `docs/` becomes the Pages document root holding both the site and its `data/` subdirectory, which is how the pipeline already writes.
- **Contract dependency**: the page reads `campus_id`, `institution_id`, `institution`, the descriptive campus attributes, `area_id`, `layer`, `name`, `county_id`, `municipality_id`, `cbsa_id`, and the four `assignments.json` fields. These field names become a two-way contract rather than a one-way output.
- **Payload**: about 306 KB of the repository's own data fetched at load (campus points, assignment, area names, provenance), and up to 1.6 MB more if a visitor views all three area layers in one session. Municipality geometry alone is 782 KB. Base map tiles are additional and are fetched as the visitor pans and zooms.
- **Deployment**: requires GitHub Pages to serve the repository's `docs/` directory on the default branch. Publishing the page makes the repository's Pages URL a public site.
- **New external dependency**: a third-party tile provider, which the page requires at load for its backdrop but not for any fact it reports. This carries an attribution obligation, a dependency on that provider's availability and terms, and the disclosure to that provider of each visitor's address and the area they are looking at.
- **Non-goals**: no server, no API, no client-side spatial computation, no self-hosted tile service, and no change to which geographies or institutions the data covers.
