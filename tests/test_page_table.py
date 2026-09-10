"""The table: rows, ordering, modes, and navigation (tasks 8.1 - 10.3)."""

SUFFOLK = "25025"
BOSTON = "35"

EXPECTED_COLUMNS = [
    "Institution",
    "Campus",
    "Address",
    "Municipality",
    "County",
    "Statistical area",
    "Type",
    "Category",
    "Degrees",
]


def header_labels(driver):
    return driver.page.evaluate(
        """() => [...document.querySelectorAll('#table-head-row th')]
            .map(th => th.innerText.replace(/[↑↓]/g, '').trim())"""
    )


def row_cells(driver, index=0):
    return driver.page.evaluate(
        f"""() => [...document.querySelectorAll(
            '#campus-table tbody tr:not(.group-heading)')][{index}]
            .querySelectorAll('td')"""
        .replace("\n", " ")
    ) if False else driver.page.evaluate(
        f"""() => {{
            const row = [...document.querySelectorAll(
                '#campus-table tbody tr:not(.group-heading)')][{index}];
            return [...row.querySelectorAll('td')].map(td => td.innerText.trim());
        }}"""
    )


# --- 8.1 one row per campus, with real header cells ------------------------

def test_the_table_is_a_real_table_with_named_columns(driver):
    driver.open()
    assert header_labels(driver) == EXPECTED_COLUMNS
    scopes = driver.page.evaluate(
        "() => [...document.querySelectorAll('#table-head-row th')].map(th => th.scope)"
    )
    assert set(scopes) == {"col"}


def test_the_default_view_renders_a_row_per_campus(driver):
    driver.open()
    assert driver.rows().count() == 150  # the default population
    driver.include_all_schools()
    assert driver.rows().count() == 206


def test_a_seven_campus_institution_occupies_seven_rows(driver):
    driver.open()
    driver.include_all_schools()
    rows = driver.page.evaluate(
        """() => [...document.querySelectorAll('#campus-table tbody tr')]
            .map(tr => [...tr.querySelectorAll('td')].map(td => td.innerText.trim()))
            .filter(cells => cells.length && cells[0] === 'Harvard University')"""
    )
    assert len(rows) == 7
    campus_names = [cells[1] for cells in rows]
    municipalities = {cells[3] for cells in rows}
    assert all(name for name in campus_names), campus_names
    assert len(set(campus_names)) == 7
    assert len(municipalities) >= 2, municipalities


def test_geography_names_come_from_the_index_not_the_mailing_city(driver):
    """Boston College's main campus is addressed Chestnut Hill, sited in Newton."""
    driver.open()
    cells = driver.page.evaluate(
        """() => {
            const row = [...document.querySelectorAll('#campus-table tbody tr')]
                .find(tr => {
                    const tds = tr.querySelectorAll('td');
                    return tds.length && tds[0].innerText.trim() === 'Boston College'
                        && tds[1].innerText.trim() === 'Main Campus';
                });
            return [...row.querySelectorAll('td')].map(td => td.innerText.trim());
        }"""
    )
    published = driver.page.evaluate(
        "() => window.maGeo.indexes.campusById.get('boston-college--main-campus')"
    )
    assert published["city"] == "Chestnut Hill"  # what the mailing city says
    assert cells[3] == "Newton"  # what the assignment says, and what is shown
    assert cells[4] == "Middlesex"
    assert cells[2] == published["address"].strip()


# --- 8.2 rows correspond to markers ----------------------------------------

def test_rows_and_markers_correspond_in_every_mode(driver):
    driver.open()
    driver.include_all_schools()
    assert driver.rows().count() == driver.marker_count() == 206

    driver.select_layer("county")
    driver.settle(600)
    assert driver.rows().count() == driver.marker_count() == 206

    driver.open(f"/index.html#layer=county&area={SUFFOLK}&population=all")
    driver.settle(700)
    assert driver.rows().count() == driver.marker_count()

    ids = driver.page.evaluate(
        """() => {
            const rows = [...document.querySelectorAll(
                '#campus-table tbody tr:not(.group-heading)')]
                .map(tr => tr.dataset.campusId);
            const markers = [];
            window.maGeo.map.map.eachLayer((layer) => {
                if (layer.campusId) markers.push(layer.campusId);
            });
            return { rows: rows.sort(), markers: markers.sort() };
        }"""
    )
    assert ids["rows"] == ids["markers"]


# --- 8.3 and 8.4 ordering and narrowing ------------------------------------

def test_ordering_by_a_column_reorders_the_rows(driver):
    driver.open()
    before = row_cells(driver)[0]
    driver.page.evaluate(
        """() => {
            const th = [...document.querySelectorAll('#table-head-row th')]
                .find(th => th.innerText.includes('Municipality'));
            th.querySelector('button').click();
            return null;
        }"""
    )
    driver.settle(300)
    municipalities = driver.page.evaluate(
        """() => [...document.querySelectorAll(
            '#campus-table tbody tr:not(.group-heading)')]
            .map(tr => tr.querySelectorAll('td')[3].innerText.trim())"""
    )
    assert municipalities == sorted(municipalities, key=lambda name: name.casefold())
    assert row_cells(driver)[0] != before
    assert driver.page.evaluate(
        "() => document.querySelector('#table-head-row th:nth-child(4)').getAttribute('aria-sort')"
    ) == "ascending"


def test_the_filter_narrows_the_rows_and_the_count(driver):
    driver.open()
    driver.include_all_schools()
    driver.page.fill("#filter-input", "harvard")
    driver.settle(300)
    institutions = driver.page.evaluate(
        """() => [...document.querySelectorAll(
            '#campus-table tbody tr:not(.group-heading)')]
            .map(tr => tr.querySelectorAll('td')[0].innerText.trim())"""
    )
    assert institutions and all("harvard" in name.lower() for name in institutions)
    status = driver.text("#table-status")
    assert str(len(institutions)) in status
    assert "206" in status  # still says what it is a subset of


def test_the_filter_stays_out_of_the_hash_and_survives_a_layer_switch(driver):
    driver.open()
    driver.page.fill("#filter-input", "college")
    driver.settle(300)
    assert driver.page.evaluate("() => window.location.hash") == ""
    filtered = driver.rows().count()
    assert 0 < filtered < 150

    driver.select_layer("county")
    driver.settle(700)
    assert driver.page.input_value("#filter-input") == "college"
    assert driver.rows().count() == filtered


# --- 9.1 to 9.5 the three modes -------------------------------------------

def test_the_unrestricted_mode_is_alphabetical_with_all_geographies(driver):
    driver.open()
    driver.include_all_schools()
    assert "All campuses, alphabetical by institution" in driver.text("#table-caption")
    institutions = driver.page.evaluate(
        """() => [...document.querySelectorAll(
            '#campus-table tbody tr:not(.group-heading)')]
            .map(tr => tr.querySelectorAll('td')[0].innerText.trim())"""
    )
    assert institutions == sorted(institutions, key=lambda name: name.casefold())
    cells = row_cells(driver)
    assert cells[3] and cells[4]  # municipality and county named
    assert len(cells) == len(EXPECTED_COLUMNS)


def test_the_grouped_mode_renders_one_body_per_county(driver):
    driver.open()
    driver.include_all_schools()
    driver.select_layer("county")
    driver.settle(700)
    groups = driver.page.evaluate(
        """() => [...document.querySelectorAll('#campus-table tbody')].map(body => {
            const heading = body.querySelector('.group-heading th');
            return {
                name: heading.querySelector('button').innerText.trim(),
                counts: heading.querySelector('.group-counts').innerText.trim(),
                rows: body.querySelectorAll('tr:not(.group-heading)').length,
            };
        })"""
    )
    assert len(groups) == 14
    assert [group["name"] for group in groups] == sorted(
        group["name"] for group in groups
    )
    assert sum(group["rows"] for group in groups) == 206
    for group in groups:
        # Both figures, each labeled. Dukes county holds one, so the label
        # is legitimately singular there.
        assert "campus" in group["counts"] and "institution" in group["counts"]

    published = driver.page.evaluate(
        """() => {
            const index = window.maGeo.indexes;
            const out = {};
            for (const [areaId, area] of Object.entries(index.areaIndex.county)) {
                out[area.name] = index.assignments.county[areaId];
            }
            return out;
        }"""
    )
    for group in groups:
        entry = published[group["name"]]
        assert str(entry["campus_count"]) in group["counts"]
        assert str(entry["institution_count"]) in group["counts"]
        assert group["rows"] == entry["campus_count"]


def test_grouping_by_municipality_places_each_campus_once(driver):
    driver.open()
    driver.include_all_schools()
    driver.select_layer("municipality")
    driver.settle(1000)
    result = driver.page.evaluate(
        """() => {
            const bodies = [...document.querySelectorAll('#campus-table tbody')];
            const ids = [];
            for (const body of bodies) {
                for (const tr of body.querySelectorAll('tr:not(.group-heading)')) {
                    ids.push(tr.dataset.campusId);
                }
            }
            return { groups: bodies.length, ids, unique: new Set(ids).size };
        }"""
    )
    assert len(result["ids"]) == 206
    assert result["unique"] == 206
    assert result["groups"] == 83  # the municipalities that hold a campus
    assert "268" in driver.text("#table-status")  # the empty ones are reported


def test_the_single_geography_mode_names_its_restriction(driver):
    driver.open(f"/index.html#layer=municipality&area={BOSTON}&population=all")
    driver.settle(900)
    assert driver.rows().count() == 38
    assert "Boston" in driver.text("#table-caption")
    status = driver.text("#table-status")
    assert "Restricted to Boston" in status
    assert "38 campuses" in status
    assert "35 institutions" in status


def test_mode_switching_needs_no_reload(driver):
    driver.open()
    driver.page.evaluate("() => { window.__stayed = true; return null; }")
    driver.select_layer("county")
    driver.settle(600)
    driver.page.evaluate(
        """() => {
            const heading = [...document.querySelectorAll('.group-heading button')]
                .find(button => button.textContent.trim() === 'Suffolk');
            heading.click();
            return null;
        }"""
    )
    driver.settle(700)
    driver.page.click("#clear-selection")
    driver.settle(600)
    driver.select_layer("none")
    driver.settle(400)
    assert driver.page.evaluate("() => window.__stayed === true")
    assert driver.rows().count() == 150


# --- 10.1 to 10.3 rows navigate to a geography -----------------------------

def test_a_row_county_selects_that_county(driver):
    driver.open()
    driver.page.evaluate(
        """() => {
            const button = [...document.querySelectorAll('#campus-table td button')]
                .find(b => b.textContent.trim() === 'Middlesex');
            button.click();
            return null;
        }"""
    )
    driver.settle(900)
    assert driver.state()["layer"] == "county"
    name = driver.page.evaluate(
        "() => window.maGeo.indexes.areaName('county', window.maGeo.state.areaId)"
    )
    assert name == "Middlesex"
    counts = driver.page.evaluate(
        "() => window.maGeo.indexes.assignments.county[window.maGeo.state.areaId]"
    )
    assert driver.rows().count() == counts["degree_granting_campus_count"]
    assert driver.marker_count() == counts["degree_granting_campus_count"]


def test_the_action_works_from_a_group_and_from_a_restricted_view(driver):
    driver.open()
    driver.select_layer("county")
    driver.settle(700)
    driver.page.evaluate(
        """() => {
            const body = [...document.querySelectorAll('#campus-table tbody')]
                .find(b => b.querySelector('.group-heading button').textContent.trim() === 'Suffolk');
            const button = [...body.querySelectorAll('td button')]
                .find(b => b.textContent.trim() === 'Boston');
            button.click();
            return null;
        }"""
    )
    driver.settle(1000)
    assert driver.state()["layer"] == "municipality"
    assert driver.page.evaluate(
        "() => window.maGeo.indexes.areaName('municipality', window.maGeo.state.areaId)"
    ) == "Boston"

    # And from within a restricted view, on to another geography.
    driver.page.evaluate(
        """() => {
            const button = [...document.querySelectorAll('#campus-table td button')]
                .find(b => b.textContent.trim() === 'Suffolk');
            button.click();
            return null;
        }"""
    )
    driver.settle(900)
    assert driver.state()["layer"] == "county"
    assert driver.page.evaluate(
        "() => window.maGeo.indexes.areaName('county', window.maGeo.state.areaId)"
    ) == "Suffolk"


def test_a_campus_with_no_statistical_area_gets_plain_text(driver):
    driver.open()
    result = driver.page.evaluate(
        """async () => {
            const rowsModule = await import('./modules/rows.js');
            const tableModule = await import('./modules/table.js');
            const index = window.maGeo.indexes;
            const campus = { ...index.campuses[0], cbsa_id: null,
                             areaIds: { ...index.campuses[0].areaIds, cbsa: null } };
            const row = rowsModule.buildRow(campus, index);
            const table = document.createElement('table');
            tableModule.renderTable(table, {
                mode: 'all', rows: [row], groups: [], rowCount: 1, totalCount: 1,
                filtering: false, caption: '', restriction: null, empty: false,
                emptyNote: '', omittedGroups: 0,
            }, { onSelectArea: () => {}, onSelectCampus: () => {} });
            const cells = [...table.querySelectorAll('td')];
            const cbsaCell = cells[5];
            return { buttons: cbsaCell.querySelectorAll('button').length,
                     text: cbsaCell.innerText.trim(),
                     label: cbsaCell.getAttribute('aria-label') };
        }"""
    )
    assert result["buttons"] == 0
    assert result["text"] == "—"
    assert result["label"] == "no statistical area"


def test_every_published_campus_does_have_a_statistical_area(driver):
    """The plain-text path is defensive: today all 206 are assigned one."""
    driver.open()
    without = driver.page.evaluate(
        "() => window.maGeo.indexes.campuses.filter(c => !c.areaIds.cbsa).length"
    )
    assert without == 0


def test_the_type_code_is_labeled_for_the_reader(driver):
    """The source publishes PUB/PRI; the table says what they mean."""
    driver.open()
    driver.include_all_schools()
    types = driver.page.evaluate(
        """() => [...new Set([...document.querySelectorAll(
            '#campus-table tbody tr:not(.group-heading)')]
            .map(tr => tr.querySelectorAll('td')[6].innerText.trim()))]"""
    )
    assert sorted(types) == ["Private", "Public"]
    published = driver.page.evaluate(
        "() => [...new Set(window.maGeo.indexes.campuses.map(c => c.institution_type))].sort()"
    )
    assert published == ["PRI", "PUB"]
