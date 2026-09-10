## ADDED Requirements

### Requirement: Award-tier classification

The source classifies each institution by the highest award it offers, opening its NCES type attribute with an award tier: sub-associate, two-year, or four-year. The system SHALL publish that tier on every campus feature as an explicit field, and SHALL publish alongside it a flag stating whether the campus is degree-granting, meaning its tier is two-year or four-year.

A consumer SHALL NOT have to parse the source's type string to learn either value. The classification SHALL be derived from the source rather than from a list of institution names, so that an institution re-tiered upstream is re-classified without a code change.

The pipeline SHALL fail rather than guess when a campus carries no recognizable tier, because a campus silently defaulted into either population would misstate every count it contributes to.

#### Scenario: Every campus carries its tier and its flag

- **WHEN** the campus layer is published
- **THEN** every feature carries an award tier drawn from the source and a degree-granting flag
- **AND** the flag is true exactly when the tier is two-year or four-year

#### Scenario: The cosmetology family is classified sub-associate

- **WHEN** the 22 campuses whose names identify them as beauty, nail, hairdressing, barbering, esthetics, or electrology schools are classified
- **THEN** every one of them is sub-associate and not degree-granting

#### Scenario: Counts of each population

- **WHEN** all 206 campuses are classified
- **THEN** 150 campuses at 116 distinct institutions are degree-granting
- **AND** the remaining 56 campuses at 44 distinct institutions are sub-associate

#### Scenario: Tier governs, not the source's own category

- **WHEN** an institution the source files under a vocational or adult-education category has a two-year or four-year tier
- **THEN** it is published as degree-granting, because the tier is what this classification is built on
- **AND** a two-year institution awarding only certificates is likewise degree-granting

#### Scenario: An unrecognized tier fails the run

- **WHEN** a campus record carries an empty or unrecognized award tier
- **THEN** the pipeline fails, identifies the campus, and does not overwrite the previously published outputs

#### Scenario: Every source record is still published

- **WHEN** the campus layer is published
- **THEN** all 206 records are present, classified rather than filtered
- **AND** no record is dropped for being sub-associate

### Requirement: Degree-granting counts per area

A consumer showing only degree-granting institutions needs that population's counts for every area, and cannot compute the institution figure by summing or subtracting because institution counts are not additive. For each area of every layer, the system SHALL therefore publish the number of degree-granting campuses and the number of distinct degree-granting institutions it contains, alongside the existing counts for all campuses.

The system SHALL also publish the statewide number of distinct degree-granting institutions, for the same reason the statewide figure for all institutions is published: neither can be derived from the per-area figures.

#### Scenario: Both populations counted for every area

- **WHEN** the assignment is published
- **THEN** every area of all three layers carries a degree-granting campus count and a degree-granting institution count as well as its existing counts
- **AND** an area with no degree-granting campuses reports zero rather than omitting the fields

#### Scenario: A known area reports both populations

- **WHEN** the county holding 45 campuses at 38 institutions is published
- **THEN** it also reports 28 degree-granting campuses at 22 degree-granting institutions

#### Scenario: The statewide degree-granting figure is published

- **WHEN** the provenance record is written
- **THEN** it carries the statewide count of distinct degree-granting institutions alongside the existing statewide institution count

#### Scenario: Degree-granting counts agree with the campus flags

- **WHEN** an area's degree-granting counts are compared with its member campuses' published flags
- **THEN** the campus count equals the number of members flagged degree-granting
- **AND** the institution count equals the number of distinct institutions among them

#### Scenario: Degree-granting institution counts are not additive either

- **WHEN** the degree-granting institution counts across a layer are summed
- **THEN** the sum exceeds the statewide degree-granting institution count, because an institution with campuses in two areas is counted in both
- **AND** consumers MUST NOT present that sum as a statewide total

## MODIFIED Requirements

### Requirement: Published consumer contract validation

The published field names, identifiers, and structure are what a consumer reads directly; a rename or a dropped field breaks that consumer at page load with no other warning. The pipeline SHALL validate that every published file carries the fields consumers depend on, with values of the expected kind, and SHALL fail rather than publish outputs that violate that contract.

The validation SHALL cover the campus features' identifying and displayed attributes, their award tier and degree-granting flag, each area feature's identifier, layer, and display name, the assignment's per-area membership arrays and counts for both populations, and the provenance figures a consumer displays. It SHALL check that every area identifier referenced by a campus resolves to a published area of that layer, and that every identifier in the assignment resolves to a published campus or institution.

#### Scenario: A renamed field fails the run

- **WHEN** a published campus feature omits a field the contract names, or carries it under a different name
- **THEN** validation fails, names the field and the affected file, and the previously published outputs are not overwritten

#### Scenario: A dangling reference fails the run

- **WHEN** a campus feature references an area identifier that no published area of that layer carries, or the assignment lists a campus identifier that no published campus carries
- **THEN** validation fails and reports the dangling identifier and both files involved

#### Scenario: Displayed provenance figures are present

- **WHEN** validation runs
- **THEN** it confirms the provenance record carries the preparation date, the statewide distinct-institution count, the statewide distinct degree-granting institution count, and the per-file feature counts that a consumer displays

#### Scenario: Optional attributes are allowed to be empty

- **WHEN** a campus publishes no campus name, no telephone, or no statistical-area assignment
- **THEN** validation accepts the empty value, because the contract distinguishes an attribute that may be empty from one that must be present

#### Scenario: A missing population count fails the run

- **WHEN** an area entry omits either of its degree-granting counts, or a campus omits its award tier or its degree-granting flag
- **THEN** validation fails and names the field and the affected file

#### Scenario: A count that disagrees with the flags fails the run

- **WHEN** an area's degree-granting campus count does not equal the number of its member campuses flagged degree-granting
- **THEN** validation fails and reports the area, the published count, and the count the flags imply
