## ADDED Requirements

### Requirement: The page shows a population, degree-granting by default

The published campuses include institutions that are not colleges or universities in any ordinary sense: cosmetology, barbering, trade, and adult-education schools, which the published data classifies as sub-associate. The page SHALL therefore show one of two populations at a time, and SHALL open on the degree-granting one.

The system SHALL offer a control that includes the sub-associate campuses, and the choice SHALL persist as the visitor changes layers and selections until they change it back. Whichever population is current SHALL govern every part of the view together: the markers drawn, the rows and groups in the table, every count shown, and the statewide summary. The page SHALL never show one population's markers beside another population's counts.

The system SHALL state which population is being shown, in text, wherever it could otherwise be mistaken, so that a figure on screen is never ambiguous about what it counted. It SHALL name the excluded population in terms a visitor recognizes rather than by the source's tier vocabulary alone.

#### Scenario: The default view is degree-granting only

- **WHEN** the page is opened with no address beyond the page itself
- **THEN** 150 campuses at 116 institutions are shown, the published degree-granting figures
- **AND** no cosmetology, barbering, trade, or adult-education campus is drawn or listed
- **AND** the page states that it is showing degree-granting institutions

#### Scenario: Including the rest restores every campus

- **WHEN** a visitor operates the control that includes sub-associate schools
- **THEN** all 206 campuses at 160 institutions are shown
- **AND** the statewide summary, the markers, and the table all change together

#### Scenario: The population survives layer and geography changes

- **WHEN** a visitor includes the sub-associate schools and then selects a layer and a geography
- **THEN** the wider population is still shown
- **AND** the counts for the selected geography are that population's counts

#### Scenario: Markers and counts never disagree about the population

- **WHEN** either population is current and a geography is selected
- **THEN** the number of markers drawn equals the number of rows in the table, and both equal the count the page states for that geography in that population

#### Scenario: The excluded population is described recognizably

- **WHEN** the page names what the default view leaves out
- **THEN** it describes them as vocational, trade, cosmetology, or adult-education schools rather than only as a source tier

### Requirement: The population is part of the shared view

Which population is shown changes what every figure on the page means, so it is part of the view rather than a local preference. The system SHALL reflect it in the page's address, so that a copied link shows its recipient the same population its sender saw, and the browser's back control SHALL step through population changes as it does through selections.

The default population SHALL be the one an address that says nothing about it produces, so that links made before this distinction existed still open on a coherent view.

#### Scenario: A shared link carries the population

- **WHEN** a visitor includes the sub-associate schools, selects a county, and sends the resulting address to someone else
- **THEN** the recipient sees that county with the wider population, matching what the sender saw

#### Scenario: An address that says nothing shows the default

- **WHEN** an address names a layer and a geography but nothing about the population
- **THEN** the page shows the degree-granting population

#### Scenario: Back steps through a population change

- **WHEN** a visitor includes the sub-associate schools and then activates the browser's back control
- **THEN** the page returns to the degree-granting population

#### Scenario: An unrecognized population value degrades to the default

- **WHEN** the page is opened with an address whose population value is not one the page knows
- **THEN** it shows the degree-granting population and renders normally, presenting no error

## MODIFIED Requirements

### Requirement: Campus and institution counts are presented honestly

Campus counts and institution counts differ, and institution counts are not additive across a layer. Wherever the system states a count, it SHALL make clear which of the two it is stating, and SHALL take per-area counts from the published assignment rather than deriving them. Because the published assignment carries counts for both populations, the system SHALL read the counts belonging to the population currently shown, and SHALL NOT compute one population's counts by subtracting or summing the other's.

The system SHALL NOT display a sum of per-area institution counts as a statewide or layer-wide total, because an institution with campuses in two areas is counted in both. This holds for both populations. Where a statewide institution figure is shown, it SHALL be the published statewide count for the population currently shown.

#### Scenario: Both counts shown for an area

- **WHEN** an area holding 38 campuses belonging to 35 distinct institutions is summarized with the wider population shown
- **THEN** both figures are shown and each is labeled as campuses or as institutions
- **AND** the two are never presented as one interchangeable number

#### Scenario: No summed institution total

- **WHEN** a layer view summarizes the whole layer
- **THEN** any total shown for institutions is the published statewide distinct-institution count for the population shown, not the sum of the layer's per-area institution counts
- **AND** a campus total, which is additive, may be shown as a sum

#### Scenario: Statewide summary

- **WHEN** the page summarizes the state with no selection
- **THEN** it states 150 campuses and 116 institutions in the default population, or 206 campuses and 160 institutions with the sub-associate schools included, in both cases the published figures

#### Scenario: An area's counts follow the population

- **WHEN** the same county is summarized in each population
- **THEN** each figure is the count published for that population, not one derived from the other

### Requirement: Loading, failure, and empty states

The system SHALL communicate what is happening while data is arriving and when it cannot arrive. While a fetch is in progress, the system SHALL indicate that the view is still loading rather than presenting an empty map or table as though complete. If a required file cannot be fetched, the system SHALL state plainly that the data could not be loaded and what is unavailable, rather than failing silently or presenting a partial view as complete. An area legitimately containing no campuses SHALL be presented as empty, which is a valid answer and not an error.

An area emptied by the population currently shown SHALL be distinguished from one that holds no campuses at all, because 17 municipalities hold campuses of which none are degree-granting, and reporting those as simply empty would misrepresent the data as much as an error would.

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

- **WHEN** a visitor selects a municipality that contains no campuses in either population
- **THEN** the table states that the geography contains no campuses
- **AND** the geography remains selected and the map keeps it in view

#### Scenario: An area emptied by the filter says so

- **WHEN** a visitor selects a municipality whose only campuses are sub-associate, with the default population shown
- **THEN** the page states that it holds no degree-granting campuses rather than that it holds none
- **AND** it offers the visitor the way to see the campuses it does hold
