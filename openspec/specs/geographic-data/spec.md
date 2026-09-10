# geographic-data Specification

## Purpose

Acquires the published college, county, municipality, and statistical-area sources for Massachusetts and prepares them into web-ready map layers plus a campus-to-geography assignment, so the interactive map and its table can answer which institutions sit in any given geography without doing spatial work in the browser.

## Requirements

### Requirement: Campus point layer

The system SHALL publish a point layer of Massachusetts higher-education campuses derived from the MassGIS Colleges and Universities source. Each source record SHALL become exactly one published campus feature; records that share an institution name but differ by campus SHALL remain separate features. Each feature SHALL carry a stable campus identifier, a stable institution identifier, the institution name, the campus name where the source provides one, and the descriptive attributes the table displays: street address, city, ZIP code, telephone, website, institution type, category, and degrees offered.

#### Scenario: Every source record is published

- **WHEN** the campus layer is produced from a source containing 206 records
- **THEN** the published layer contains 206 point features
- **AND** no feature is dropped, merged, or duplicated

#### Scenario: Multi-campus institution keeps one feature per campus

- **WHEN** an institution appears in the source as two records with the same institution name and different campus names in different municipalities
- **THEN** the published layer contains two distinct features, each with its own identifier and its own municipality assignment

#### Scenario: Campus identifier is stable across runs

- **WHEN** the pipeline is run twice against the same source vintage
- **THEN** each campus receives the same identifier in both runs
- **AND** the identifier does not depend on the order in which source records were read

### Requirement: Geographic area layers

The system SHALL publish three geographic area layers: counties, municipalities, and Core Based Statistical Areas. Each area feature SHALL carry a stable area identifier, a display name suitable for a map label and a table group heading, and the identifier of the layer it belongs to. The counties layer SHALL contain the 14 Massachusetts counties and the municipalities layer SHALL contain the 351 Massachusetts municipalities.

The three layers SHALL share one outer boundary and SHALL nest exactly: every municipality lies wholly within one county, and every county lies wholly within one statistical area. A map may therefore switch layers without the state's outline shifting, and no gap or overlap may appear where a boundary is shared.

#### Scenario: County and municipality layers are complete

- **WHEN** the area layers are produced
- **THEN** the counties layer contains 14 features and the municipalities layer contains 351 features
- **AND** every feature has a non-empty display name that is unique within its layer

#### Scenario: Municipality carries its county

- **WHEN** a municipality feature is published
- **THEN** it also carries the identifier of the county that contains it, so the table can relate the two layers without a spatial operation

#### Scenario: The layers share one outer boundary

- **WHEN** the outer boundary of each published area layer is compared with the others
- **THEN** all three are the same boundary, agreeing to within the precision the published coordinates can express, rather than being separately drawn boundaries that merely resemble one another
- **AND** switching the displayed layer does not move the state's outline

#### Scenario: The layers nest without gaps or overlaps

- **WHEN** the areas of a finer layer that fall inside one area of a coarser layer are combined
- **THEN** they reproduce that coarser area exactly, leaving no sliver of the coarser area uncovered and no part extending beyond it

### Requirement: Statistical areas restricted to Massachusetts

Core Based Statistical Areas cross state lines. The system SHALL publish only those statistical areas that include at least one Massachusetts county, and SHALL restrict each published area's geometry to that area's Massachusetts extent, so that no part of the layer renders outside the state. Each published area SHALL retain its full official name, including the state suffix that names the other states it reaches.

#### Scenario: Multi-state area is restricted to Massachusetts but keeps its name

- **WHEN** a statistical area extends from Massachusetts into New Hampshire
- **THEN** the published geometry covers only its Massachusetts portion
- **AND** its display name remains the full official name, such as `Boston-Cambridge-Newton, MA-NH`

#### Scenario: Out-of-state areas are excluded

- **WHEN** the national statistical-area source is processed
- **THEN** an area that contains no Massachusetts county is absent from the published layer, even where the published boundaries of the two sources overlap slightly along the state line

#### Scenario: Every Massachusetts county belongs to exactly one published area

- **WHEN** the statistical-area layer is built
- **THEN** each of the 14 counties belongs to exactly one published statistical area
- **AND** the published areas together cover the whole state

### Requirement: Campus-to-geography assignment

The system SHALL publish an assignment relating every campus to the geographic areas that contain it, covering all three layers. Each campus SHALL be assigned exactly one county and exactly one municipality. Because the statistical-area layer does not cover all of Massachusetts, a campus SHALL be assigned either one statistical area or none. The assignment SHALL be derivable in both directions: given a campus, its areas; and given an area, its campuses and the distinct institutions those campuses belong to.

#### Scenario: Campus is assigned in every covering layer

- **WHEN** the assignment is produced for a campus located in Boston
- **THEN** the campus is assigned the municipality Boston, the county Suffolk, and the statistical area whose clipped geometry contains it

#### Scenario: Campus outside every statistical area

- **WHEN** a campus falls in a part of Massachusetts that no statistical area covers
- **THEN** its statistical-area assignment is empty rather than guessed or omitted from the assignment
- **AND** the campus is still assigned its county and municipality

#### Scenario: Area membership is retrievable by area

- **WHEN** a consumer asks which campuses belong to a given area identifier
- **THEN** the assignment yields every campus contained by that area, and an area containing no campuses is represented as an empty membership rather than being absent

#### Scenario: Assignment agrees with the source municipality attribute

- **WHEN** a campus's computed municipality differs from the municipality named in the source record's own attribute
- **THEN** the discrepancy is reported as a data-quality finding identifying the campus and both municipality values

### Requirement: Institution identity and counts

Campuses belong to institutions, and a geography's institution count differs from its campus count. Every campus feature SHALL carry a stable institution identifier alongside the institution name, and all campuses of one institution SHALL share that identifier. For each area in every layer, the system SHALL publish both the number of campuses and the number of distinct institutions it contains.

#### Scenario: Institution identifier is shared across campuses

- **WHEN** an institution has seven campuses spread across two municipalities
- **THEN** all seven campus features carry the same institution identifier
- **AND** that identifier is distinct from every campus identifier in the layer

#### Scenario: Both counts are published per area

- **WHEN** the assignment is produced for a municipality holding 38 campuses belonging to 35 distinct institutions
- **THEN** that area reports a campus count of 38 and an institution count of 35

#### Scenario: Institution counts are not additive across a layer

- **WHEN** an institution has campuses in two different counties
- **THEN** it is counted in the institution count of both counties
- **AND** the sum of institution counts across the layer therefore exceeds the number of distinct institutions in the state, which consumers MUST NOT treat as a statewide total

#### Scenario: Identifier is derived from a verified-unique institution name

- **WHEN** institution identifiers are derived for all 206 campus records
- **THEN** exactly 160 distinct identifiers result
- **AND** no two different institution names collide on the same identifier

#### Scenario: Institution membership is retrievable by area

- **WHEN** a consumer asks which institutions belong to a given area identifier
- **THEN** the assignment yields each distinct institution once, however many campuses it has in that area

### Requirement: Web-ready published outputs

All published layers SHALL be GeoJSON in WGS 84 (EPSG:4326) with longitude-latitude coordinate order, so a browser map can consume them directly. The published files SHALL be served as static files from the repository with no runtime call to any upstream service, and SHALL be small enough to fetch over a normal connection without a tiling server.

#### Scenario: Reprojection to web coordinates

- **WHEN** a source layer in the Massachusetts State Plane projection is published
- **THEN** the output geometry is in EPSG:4326
- **AND** coordinates are ordered longitude first, latitude second

#### Scenario: Static hosting with no upstream dependency

- **WHEN** the published outputs are served as static files and every upstream source is unreachable
- **THEN** all layers and the assignment still load and are complete

#### Scenario: Geometry simplified within a size budget

- **WHEN** the municipalities layer is published
- **THEN** its geometry is simplified enough to meet the project's per-file size budget
- **AND** simplification does not move any campus point across an area boundary it was assigned to, nor open a visible gap between adjacent areas

### Requirement: Provenance record

Each published dataset SHALL be accompanied by a record of where it came from: the upstream source of each layer, the identifier or vintage of the version fetched, the date it was fetched, and the feature count published. The upstream MassGIS layers are revised in place, so this record is what makes a given set of outputs interpretable and reproducible later.

#### Scenario: Provenance is written with the outputs

- **WHEN** the pipeline completes
- **THEN** the provenance record names every upstream source, its version or vintage, the fetch date, and the published feature count for each layer

#### Scenario: Upstream revision is detectable

- **WHEN** the pipeline is re-run after an upstream layer has been revised
- **THEN** the new provenance record differs from the previous one in that layer's version or feature count, making the change visible in review

### Requirement: Integrity validation

The pipeline SHALL validate its own output and SHALL fail rather than publish data that violates the assignment guarantees. Conditions that are legitimate but noteworthy SHALL be reported without failing.

#### Scenario: Missing required assignment fails the run

- **WHEN** any campus cannot be assigned a county or cannot be assigned a municipality
- **THEN** the pipeline fails, identifies the affected campuses, and does not overwrite the previously published outputs

#### Scenario: Ambiguous assignment fails the run

- **WHEN** a campus is found to fall within two features of the same area layer
- **THEN** the pipeline fails and reports the campus and the conflicting areas

#### Scenario: Count mismatch fails the run

- **WHEN** a published layer's feature count does not match the count read from its source, after documented filtering
- **THEN** the pipeline fails and reports the expected and actual counts

#### Scenario: Legitimate gaps are reported, not fatal

- **WHEN** the run finds campuses in no statistical area, or areas with no campuses
- **THEN** these are reported as informational counts and the run succeeds
