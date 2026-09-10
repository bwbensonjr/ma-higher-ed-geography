# web-map-ui Specification

## Purpose

Presents the published campus points, area layers, and campus-to-geography assignment as an interactive map with a table beneath it, so a visitor can see where Massachusetts colleges and universities are and explore them by county, municipality, or statistical area without any server doing work on their behalf.

## Requirements

### Requirement: Statically served page with no application server

The system SHALL present a single web page served as static files from the repository, requiring no application server, no build step at serve time, and no API. Every campus and geography fact the page renders SHALL come from the published data files in the same repository, so no upstream data service outage can change what the page reports.

The page's only permitted external requests SHALL be the base map tiles it displays. It SHALL NOT send requests to an analytics, tracking, or telemetry endpoint, and SHALL NOT depend on a third-party host for its own code, styles, or data.

#### Scenario: All content comes from the serving origin

- **WHEN** the page is loaded and the requests it makes are examined
- **THEN** every request for the page, its code, its styles, and its data is to the serving origin
- **AND** the only requests to another host are for base map tiles

#### Scenario: No analytics or telemetry

- **WHEN** the page is used through a full session of layer and geography selections
- **THEN** no request is made to any analytics, tracking, or telemetry endpoint

#### Scenario: No spatial computation in the browser

- **WHEN** a visitor selects a geography and the table restricts itself to that geography's campuses
- **THEN** the membership shown is read from the published assignment rather than computed by testing campus coordinates against area geometry

### Requirement: Campus markers and campus detail

The system SHALL render every published campus as its own marker at its published coordinates, so the number of markers equals the number of published campuses and a multi-campus institution shows one marker per campus. Selecting a marker SHALL reveal that campus's identifying and descriptive detail: the institution name, the campus name where one is published, street address, municipality, ZIP code, telephone, institution type, category, and degrees offered, plus its website as a followable link where one is published. Detail that the source leaves empty SHALL be omitted rather than shown as a blank or placeholder value.

#### Scenario: One marker per published campus

- **WHEN** the campus layer publishes 206 campus features
- **THEN** the map renders 206 markers
- **AND** an institution with seven campuses contributes seven distinct markers rather than one

#### Scenario: Campus detail is revealed on selection

- **WHEN** a visitor selects a campus marker
- **THEN** that campus's institution name, address, municipality, telephone, type, category, and degrees offered are shown
- **AND** its website is presented as a followable link

#### Scenario: Missing attribute is omitted

- **WHEN** a selected campus publishes no campus name and no telephone
- **THEN** neither field appears in the detail
- **AND** no empty label, `null`, or placeholder text is rendered in their place

### Requirement: Geographic layer selection

The system SHALL let a visitor choose which geographic layer the map draws: counties, municipalities, or statistical areas. Exactly one layer SHALL be drawn at a time, and the visitor SHALL also be able to view the campuses with no area layer drawn. Each layer's areas SHALL be shaded according to the number of campuses they contain and SHALL reveal the area's name and its campus and institution counts when pointed at, so a layer view conveys where campuses concentrate before anything is selected. A legend SHALL explain what the shading means.

#### Scenario: Switching layers replaces the drawn areas

- **WHEN** a visitor switches the layer from counties to municipalities
- **THEN** the 351 municipalities are drawn and the 14 counties are no longer drawn
- **AND** the campus markers remain visible and unchanged

#### Scenario: No layer selected

- **WHEN** a visitor chooses to view no area layer
- **THEN** no area boundaries are drawn and all campus markers remain visible

#### Scenario: Areas are shaded by campus count

- **WHEN** the county layer is drawn
- **THEN** a county holding many campuses is shaded more intensely than a county holding few
- **AND** an area holding no campuses is visibly distinguished from areas that hold campuses
- **AND** a legend states the count ranges the shading represents

#### Scenario: Area identity is revealed on hover

- **WHEN** a visitor points at an area in the drawn layer
- **THEN** the area's display name, its campus count, and its institution count are shown

### Requirement: Geography selection and clearing

The system SHALL let a visitor select one geography within the drawn layer, and SHALL make that selection the shared state of the map and the table. On selection, the map SHALL bring the selected geography into view, distinguish it from the unselected areas of its layer, and restrict the visible campus markers to the campuses assigned to it. The system SHALL always offer a way to clear the selection and return to the whole state, and clearing SHALL restore all campus markers and the unrestricted table.

#### Scenario: Selecting a geography restricts the view

- **WHEN** a visitor selects Suffolk County in the county layer
- **THEN** the map brings Suffolk into view and distinguishes it from the other counties
- **AND** only the campuses assigned to Suffolk are shown as markers
- **AND** the table shows only those campuses

#### Scenario: Clearing the selection restores the whole state

- **WHEN** a geography is selected and the visitor clears the selection
- **THEN** every campus marker is shown again
- **AND** the table returns to its unrestricted content for the current layer

#### Scenario: Switching layers resolves the stale selection

- **WHEN** Suffolk County is selected and the visitor switches to the municipality layer
- **THEN** the page does not continue to present a county as the selection of the municipality layer
- **AND** the resulting state is a valid one: either no geography selected, or a geography that belongs to the newly drawn layer

### Requirement: One table row per campus

The table SHALL present one row per campus rather than one row per institution, so that each row's address, municipality, county, and statistical area are single-valued and each row corresponds to exactly one map marker. An institution with campuses in several places SHALL therefore appear on several rows, each identified by its campus. Each row SHALL carry the institution name, the campus name where one is published, and the campus's municipality, county, and statistical area, alongside the descriptive attributes the table displays. A row's geography names SHALL be the published display names of the areas the campus is assigned to, not the mailing city on its address, which names a different place for 18 of the 206 campuses. The visitor SHALL be able to reorder the rows by a column and to narrow the rows by typing text matched against institution and campus names.

#### Scenario: A multi-campus institution occupies several rows

- **WHEN** the unrestricted table is shown for an institution with seven published campuses
- **THEN** that institution occupies seven rows
- **AND** each row names its own campus and shows that campus's own municipality and county

#### Scenario: Row corresponds to a marker

- **WHEN** the table shows a set of rows
- **THEN** each row corresponds to exactly one campus marker currently shown on the map, and each shown marker corresponds to exactly one row

#### Scenario: Rows can be reordered and narrowed

- **WHEN** a visitor orders the table by municipality and then types part of an institution's name
- **THEN** the rows are ordered by municipality and restricted to those matching the typed text
- **AND** the count shown alongside the table reflects the narrowed rows rather than the full set

### Requirement: Table content follows the selection

The table SHALL have three modes determined by what is selected, and switching between them SHALL require no page reload.

When no area layer and no geography is selected, the table SHALL list every published campus in alphabetical order by institution name, showing each campus's detail and its geographies.

When an area layer is selected but no single geography is, the table SHALL group the rows by the areas of that layer, ordering the groups by area name, with each group heading naming the area and carrying its campus and institution counts, and each group containing the campuses assigned to that area.

When a single geography is selected, the table SHALL contain only the campuses assigned to that geography and SHALL state which geography it is restricted to.

#### Scenario: Unrestricted alphabetical list

- **WHEN** neither a layer nor a geography is selected
- **THEN** the table lists all 206 campuses ordered alphabetically by institution name
- **AND** each row shows the campus's municipality, county, and statistical area

#### Scenario: Grouped by the selected layer

- **WHEN** the county layer is selected and no single county is
- **THEN** the table presents 14 groups ordered by county name
- **AND** each group heading names its county and states its campus count and its institution count
- **AND** the campuses within each group are the campuses assigned to that county

#### Scenario: Restricted to one geography

- **WHEN** the municipality Boston is selected
- **THEN** the table contains exactly the 38 campuses assigned to Boston
- **AND** the table states that it is restricted to Boston

#### Scenario: A campus appears once per grouped view

- **WHEN** the table is grouped by the municipality layer
- **THEN** each campus appears in exactly one group, because each campus is assigned exactly one municipality

### Requirement: Table rows navigate to a geography

Each table row's geography values SHALL be actionable: acting on a row's county, municipality, or statistical area SHALL select that layer and that geography, updating the map and the table together. This SHALL work from any table mode, so a visitor who finds an institution in the alphabetical list can reach its geography without first finding it on the map.

#### Scenario: Selecting a geography from a row

- **WHEN** a visitor acts on the county value `Middlesex` in a row of the unrestricted table
- **THEN** the county layer becomes the drawn layer and Middlesex becomes the selected geography
- **AND** the map brings Middlesex into view and the table restricts itself to Middlesex's campuses

#### Scenario: A campus without a statistical area

- **WHEN** a row's campus has no statistical area assigned
- **THEN** that row presents no statistical-area action rather than an action that selects nothing

### Requirement: Campus and institution counts are presented honestly

Campus counts and institution counts differ, and institution counts are not additive across a layer. Wherever the system states a count, it SHALL make clear which of the two it is stating, and SHALL take per-area counts from the published assignment rather than deriving them. The system SHALL NOT display a sum of per-area institution counts as a statewide or layer-wide total, because an institution with campuses in two areas is counted in both. Where a statewide institution figure is shown, it SHALL be the published statewide count.

#### Scenario: Both counts shown for an area

- **WHEN** an area holding 38 campuses belonging to 35 distinct institutions is summarized
- **THEN** both figures are shown and each is labeled as campuses or as institutions
- **AND** the two are never presented as one interchangeable number

#### Scenario: No summed institution total

- **WHEN** a layer view summarizes the whole layer
- **THEN** any total shown for institutions is the published statewide distinct-institution count, not the sum of the layer's per-area institution counts
- **AND** a campus total, which is additive, may be shown as a sum

#### Scenario: Statewide summary

- **WHEN** the page summarizes the state with no selection
- **THEN** it states 206 campuses and 160 institutions, the published figures

### Requirement: The current view is shareable and navigable

The system SHALL reflect the selected layer and the selected geography in the page's address, so a view can be copied, shared, and bookmarked, and opening such an address SHALL restore that view. The browser's back and forward controls SHALL step through the views the visitor produced. An address naming a layer or geography that does not exist SHALL fall back to the default unselected view rather than failing to render.

#### Scenario: A shared address restores the view

- **WHEN** a visitor selects Suffolk County and a second visitor opens the resulting address
- **THEN** the second visitor sees the county layer drawn with Suffolk selected, the map brought to Suffolk, and the table restricted to Suffolk's campuses

#### Scenario: Back steps through selections

- **WHEN** a visitor selects the county layer, then selects Suffolk, then activates the browser's back control
- **THEN** the page returns to the county layer with no geography selected

#### Scenario: An unrecognized address degrades to the default view

- **WHEN** the page is opened with an address naming a layer that does not exist or an area identifier absent from the published data
- **THEN** the page renders the default unselected view of all campuses
- **AND** no error is presented as though the page itself had failed

### Requirement: Progressive loading within a payload budget

The published area geometry is far larger than the campus and assignment data, and most visits will not view all three layers. The system SHALL render its first meaningful view -- the campus markers, the statewide summary, and the full table with every row's geographies named -- from the small published files alone, and SHALL fetch an area layer's geometry only when that layer is first drawn. Naming a campus's county, municipality, and statistical area SHALL therefore require no geometry. Geometry once fetched SHALL be reused for the rest of the visit rather than re-fetched when the visitor returns to that layer.

#### Scenario: First view does not fetch area geometry

- **WHEN** the page is opened at the default view
- **THEN** the campus points, the assignment, the area name index, and the provenance are fetched, and the markers, the summary, and the table are rendered
- **AND** no area layer geometry has been fetched
- **AND** every table row names its county, municipality, and statistical area

#### Scenario: Layer geometry is fetched on first use only

- **WHEN** a visitor draws the municipality layer, switches to counties, and switches back to municipalities
- **THEN** the municipality geometry is fetched once
- **AND** the return to municipalities draws from what was already fetched

#### Scenario: A shared address fetches only what it needs

- **WHEN** the page is opened at an address selecting a county
- **THEN** the county geometry is fetched
- **AND** the municipality and statistical-area geometry is not

### Requirement: Loading, failure, and empty states

The system SHALL communicate what is happening while data is arriving and when it cannot arrive. While a fetch is in progress, the system SHALL indicate that the view is still loading rather than presenting an empty map or table as though complete. If a required file cannot be fetched, the system SHALL state plainly that the data could not be loaded and what is unavailable, rather than failing silently or presenting a partial view as complete. An area legitimately containing no campuses SHALL be presented as empty, which is a valid answer and not an error.

#### Scenario: Loading is visible

- **WHEN** the page is opened and the published files have not yet arrived
- **THEN** the page indicates that it is loading
- **AND** it does not present an empty table as the complete list of campuses

#### Scenario: A failed fetch is reported

- **WHEN** the campus data cannot be fetched
- **THEN** the page states that the data could not be loaded
- **AND** it does not display a count of zero campuses as though the state contained none

#### Scenario: A failed layer fetch leaves the rest usable

- **WHEN** the campus data loads but one area layer's geometry cannot be fetched
- **THEN** the page reports that the layer is unavailable
- **AND** the campus markers, the table, and the other layers remain usable

#### Scenario: An empty geography is a valid result

- **WHEN** a visitor selects a municipality that contains no campuses
- **THEN** the table states that the geography contains no campuses
- **AND** the geography remains selected and the map keeps it in view

### Requirement: Layout and assistive access

The map and the table SHALL both be usable on a small screen and on a wide one, with the table's columns remaining readable rather than overflowing the viewport. The table SHALL be presented as tabular content with header cells that name the columns, so it can be read by assistive technology and by a visitor who does not use the map. Every control that selects a layer or a geography, including the geography actions in table rows, SHALL be reachable and operable by keyboard, and the current layer and geography SHALL be discoverable as text rather than by map color alone.

#### Scenario: Usable on a narrow viewport

- **WHEN** the page is viewed on a narrow screen
- **THEN** the map and the table are both usable and the table does not overflow the viewport horizontally without a way to reach the hidden columns

#### Scenario: Selection is operable by keyboard

- **WHEN** a visitor navigates by keyboard alone
- **THEN** the layer selector, the clear-selection control, and each row's geography actions can all be reached and operated
- **AND** the resulting selection changes the table exactly as it does when operated by pointer

#### Scenario: Selection is stated as text

- **WHEN** a geography is selected
- **THEN** the page names the selected layer and geography as text
- **AND** a visitor who cannot distinguish the map's highlight can still tell what is selected

### Requirement: Base map tiles

The map SHALL draw a base map of tiles beneath everything else it renders, so that a campus marker sits in real geographic context: coastline and state borders at a statewide view, and streets and place names when zoomed in far enough to see where a campus actually is.

The base map SHALL be visually subordinate to the page's own content. Area shading SHALL remain distinguishable from the tiles beneath it, and campus markers SHALL remain the most prominent thing on the map, so the base map informs the view without competing with what the page is about.

The map SHALL offer a zoom range from the whole state down to street level, and the base map SHALL render tiles across that whole range rather than going blank at the closest zooms.

#### Scenario: Street-level detail when zoomed in

- **WHEN** a visitor zooms to a single campus at the closest zoom the map offers
- **THEN** the base map shows the streets and place names around it
- **AND** the campus marker remains visible and distinguishable against them

#### Scenario: Statewide view is legible

- **WHEN** the whole state is in view with an area layer drawn and shaded
- **THEN** the shading classes remain distinguishable from one another over the tiles
- **AND** the campus markers remain the most prominent feature on the map

### Requirement: The page remains usable when the base map does not load

The base map comes from a third-party host, which may be slow, blocked, or unavailable. A visitor SHALL still be able to use the page in that case: every fact the page reports comes from the repository's own data, so tile failure SHALL degrade the map's backdrop and nothing else.

#### Scenario: Tiles unavailable

- **WHEN** the tile host is unreachable and the page is loaded
- **THEN** the campus markers, the area layers, the selection behavior, and the table all work completely
- **AND** the counts, groupings, and campus detail are unaffected

#### Scenario: Tile failure is not reported as a data failure

- **WHEN** tiles fail to load but the published data loads
- **THEN** the page does not present the failure as an inability to load its data
- **AND** it does not block interaction while waiting for tiles

### Requirement: Provenance and attribution are shown

The published data carries a record of its upstream sources and when they were fetched, and both those sources and the base map require attribution. The system SHALL show, from that published record, which sources the data came from and when it was prepared, so a visitor can tell how current the map is, and SHALL attribute the upstream providers of the geography and campus data as well as the base map it displays.

#### Scenario: Provenance is displayed from the published record

- **WHEN** a visitor looks for the origin of the data
- **THEN** the page names the upstream sources and the date the data was prepared, taken from the published provenance record rather than written into the page by hand

#### Scenario: Provenance follows a new data run

- **WHEN** the data pipeline is re-run and publishes a later preparation date
- **THEN** the page shows the later date without any edit to the page itself

#### Scenario: Attribution is present

- **WHEN** the map is displayed
- **THEN** the attribution required by the upstream geography and campus sources is visible on the page
- **AND** the attribution required by the base map's tile provider and its underlying map data is visible on the map

#### Scenario: Base map attribution survives tile failure

- **WHEN** the tile host is unreachable
- **THEN** the data sources' attribution remains visible
