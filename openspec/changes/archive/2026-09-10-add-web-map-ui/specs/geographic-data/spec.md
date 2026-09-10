## ADDED Requirements

### Requirement: Area name index

An area's display name is published only inside its layer's geometry file, and a consumer that shows an area's name alongside a campus would have to fetch every layer's geometry to do it. The system SHALL therefore also publish an index of area display names, covering every area of all three layers, small enough that a consumer can fetch it with its first view.

For each area the index SHALL carry the same display name the area's geometry file carries, and for a municipality it SHALL also carry the identifier of its county, so a consumer can name a campus's county and municipality from the index alone. The index SHALL be a separate file, leaving the existing published outputs unchanged.

#### Scenario: Every area of every layer is named

- **WHEN** the index is published
- **THEN** it names all 14 counties, all 351 municipalities, and all 10 statistical areas
- **AND** an area with no campuses is named like any other

#### Scenario: Names agree with the geometry files

- **WHEN** an area's name in the index is compared with that area's name in its layer's geometry file
- **THEN** the two are identical for every area of every layer

#### Scenario: A municipality carries its county in the index

- **WHEN** a municipality's index entry is read
- **THEN** it carries the identifier of the county that contains it, matching the geometry file

#### Scenario: The index is small enough to fetch eagerly

- **WHEN** the index is published
- **THEN** its file is smaller than a tenth of the smallest area geometry layer
- **AND** the existing published outputs are byte-identical to what the same source vintage produced before

#### Scenario: The index appears in the provenance record

- **WHEN** the provenance record is written
- **THEN** it records the index's byte size alongside the other published files

### Requirement: Published consumer contract validation

The published field names, identifiers, and structure are what a consumer reads directly; a rename or a dropped field breaks that consumer at page load with no other warning. The pipeline SHALL validate that every published file carries the fields consumers depend on, with values of the expected kind, and SHALL fail rather than publish outputs that violate that contract.

The validation SHALL cover the campus features' identifying and displayed attributes, each area feature's identifier, layer, and display name, the assignment's per-area membership arrays and counts, and the provenance figures a consumer displays. It SHALL check that every area identifier referenced by a campus resolves to a published area of that layer, and that every identifier in the assignment resolves to a published campus or institution.

#### Scenario: A renamed field fails the run

- **WHEN** a published campus feature omits a field the contract names, or carries it under a different name
- **THEN** validation fails, names the field and the affected file, and the previously published outputs are not overwritten

#### Scenario: A dangling reference fails the run

- **WHEN** a campus feature references an area identifier that no published area of that layer carries, or the assignment lists a campus identifier that no published campus carries
- **THEN** validation fails and reports the dangling identifier and both files involved

#### Scenario: Displayed provenance figures are present

- **WHEN** validation runs
- **THEN** it confirms the provenance record carries the preparation date, the statewide distinct-institution count, and the per-file feature counts that a consumer displays

#### Scenario: Optional attributes are allowed to be empty

- **WHEN** a campus publishes no campus name, no telephone, or no statistical-area assignment
- **THEN** validation accepts the empty value, because the contract distinguishes an attribute that may be empty from one that must be present
