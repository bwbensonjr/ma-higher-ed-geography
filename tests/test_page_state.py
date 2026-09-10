"""Selection and URL state (tasks 7.1 - 7.7)."""

SUFFOLK = "25025"
MIDDLESEX = "25017"


# --- 7.1 parsing and normalization -----------------------------------------

def test_a_valid_state_round_trips(blank):
    result = blank.page.evaluate(
        """async () => {
            const m = await import('./modules/state.js');
            const index = { county: { '25025': {} }, municipality: {}, cbsa: {} };
            const cases = [
                { layer: 'none', areaId: null },
                { layer: 'county', areaId: null },
                { layer: 'county', areaId: '25025' },
            ];
            return cases.map((state) => m.normalizeState(m.parseHash(m.encodeState(state)), index));
        }"""
    )
    assert result == [
        {"layer": "none", "areaId": None, "population": "degree_granting"},
        {"layer": "county", "areaId": None, "population": "degree_granting"},
        {"layer": "county", "areaId": "25025", "population": "degree_granting"},
    ]


def test_unrecognized_addresses_normalize_to_the_default_view(blank):
    outcomes = blank.page.evaluate(
        """async () => {
            const m = await import('./modules/state.js');
            const index = { county: { '25025': {} }, municipality: { '35': {} }, cbsa: {} };
            const hashes = [
                '#layer=galaxy',                  // a layer that does not exist
                '#layer=county&area=99999',       // an area absent from the data
                '#layer=municipality&area=25025', // a county id under the municipality layer
                '#area=25025',                    // an area with no layer
                '#layer=&area=',
                '',
                '#nonsense',
            ];
            return hashes.map((hash) => m.normalizeState(m.parseHash(hash), index));
        }"""
    )
    assert all(
        state == {"layer": "none", "areaId": None, "population": "degree_granting"}
        for state in outcomes
    ), outcomes


def test_the_default_view_has_no_hash(blank):
    assert blank.eval_module(
        "state", "m.encodeState({layer:'none',areaId:null,population:'degree_granting'})"
    ) == ""


def test_an_unrecognized_address_still_renders_the_default_view(driver):
    driver.open("/index.html#layer=galaxy&area=nowhere")
    assert driver.state() == {
        "layer": "none", "areaId": None, "population": "degree_granting",
    }
    assert driver.marker_count() == 150
    assert driver.rows().count() == 150
    assert driver.page.locator("#error").is_hidden()


# --- 7.2 one render path ----------------------------------------------------

def test_setting_the_hash_renders_the_same_view_as_clicking(driver):
    driver.open()
    driver.page.evaluate(
        f"() => {{ window.location.hash = 'layer=county&area={SUFFOLK}'; return null; }}"
    )
    driver.settle(700)
    from_hash = {
        "state": driver.state(),
        "markers": driver.marker_count(),
        "rows": driver.rows().count(),
        "status": driver.text("#table-status"),
    }

    driver.open()
    driver.page.evaluate(
        f"() => {{ window.maGeo.map.map.fire; return null; }}"
    )
    # Click Suffolk through the same control a visitor uses: a table row link.
    driver.select_layer("county")
    driver.settle(500)
    driver.page.evaluate(
        """() => {
            const heading = [...document.querySelectorAll('.group-heading button')]
                .find(button => button.textContent.trim() === 'Suffolk');
            heading.click();
            return null;
        }"""
    )
    driver.settle(700)
    from_click = {
        "state": driver.state(),
        "markers": driver.marker_count(),
        "rows": driver.rows().count(),
        "status": driver.text("#table-status"),
    }
    assert from_hash == from_click


# --- 7.3 and 7.4 selecting and clearing ------------------------------------

def test_selecting_a_county_restricts_the_map_and_the_table(driver):
    driver.open(f"/index.html#layer=county&area={SUFFOLK}")
    driver.settle(600)
    counts = driver.page.evaluate(
        f"() => window.maGeo.indexes.assignments.county['{SUFFOLK}']"
    )
    # The default population, so the degree-granting counts are the ones shown.
    assert driver.marker_count() == counts["degree_granting_campus_count"]
    assert driver.rows().count() == counts["degree_granting_campus_count"]
    assert "Suffolk" in driver.text("#selection-status")
    assert "Suffolk" in driver.text("#table-status")


def test_the_selected_area_is_distinguished_from_its_siblings(driver):
    driver.open(f"/index.html#layer=county&area={SUFFOLK}")
    driver.settle(700)
    styles = driver.page.evaluate(
        f"""() => {{
            const map = window.maGeo.map.map;
            const out = {{ selected: null, others: [] }};
            map.eachLayer((layer) => {{
                if (!layer.feature || !layer.feature.properties.area_id) return;
                const style = {{ weight: layer.options.weight, color: layer.options.color,
                                fillOpacity: layer.options.fillOpacity }};
                if (String(layer.feature.properties.area_id) === '{SUFFOLK}') out.selected = style;
                else out.others.push(style);
            }});
            return out;
        }}"""
    )
    assert styles["selected"]["weight"] > styles["others"][0]["weight"]
    assert styles["selected"]["color"] != styles["others"][0]["color"]
    assert all(
        other["fillOpacity"] < styles["selected"]["fillOpacity"]
        for other in styles["others"]
    )


def test_the_map_is_brought_to_the_selected_area(driver):
    driver.open()
    statewide = driver.page.evaluate("() => window.maGeo.map.map.getZoom()")
    driver.open(f"/index.html#layer=county&area={SUFFOLK}")
    driver.settle(700)
    zoomed = driver.page.evaluate(
        """() => {
            const map = window.maGeo.map.map;
            const centre = map.getCenter();
            return { zoom: map.getZoom(), lat: centre.lat, lon: centre.lng };
        }"""
    )
    assert zoomed["zoom"] > statewide
    assert 42.2 < zoomed["lat"] < 42.5
    assert -71.2 < zoomed["lon"] < -70.9


def test_clearing_the_selection_restores_everything(driver):
    driver.open(f"/index.html#layer=county&area={SUFFOLK}")
    driver.settle(600)
    assert driver.page.locator("#clear-selection").is_visible()
    driver.page.click("#clear-selection")
    driver.settle(600)
    assert driver.state() == {
        "layer": "county", "areaId": None, "population": "degree_granting",
    }
    assert driver.marker_count() == 150
    assert driver.rows().count() == 150
    assert driver.page.locator("#clear-selection").is_hidden()
    assert driver.area_count() == 14


def test_the_clear_control_is_absent_with_no_selection(driver):
    driver.open()
    assert driver.page.locator("#clear-selection").is_hidden()
    driver.select_layer("county")
    driver.settle(500)
    assert driver.page.locator("#clear-selection").is_hidden()


# --- 7.5 switching layers clears the geography -----------------------------

def test_switching_layers_clears_the_selection(driver):
    driver.open(f"/index.html#layer=county&area={SUFFOLK}")
    driver.settle(600)
    driver.select_layer("municipality")
    driver.settle(900)
    assert driver.state() == {
        "layer": "municipality", "areaId": None, "population": "degree_granting",
    }
    assert SUFFOLK not in driver.page.evaluate("() => window.location.hash")
    assert driver.marker_count() == 150
    assert "No municipality selected" in driver.text("#selection-status")


# --- 7.6 history ------------------------------------------------------------

def test_back_steps_through_the_selections(driver):
    driver.open()
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
    dg = "degree_granting"
    assert driver.state() == {"layer": "county", "areaId": SUFFOLK, "population": dg}

    driver.page.go_back()
    driver.settle(700)
    assert driver.state() == {"layer": "county", "areaId": None, "population": dg}

    driver.page.go_back()
    driver.settle(700)
    assert driver.state() == {"layer": "none", "areaId": None, "population": dg}

    driver.page.go_forward()
    driver.settle(700)
    assert driver.state() == {"layer": "county", "areaId": None, "population": dg}


def test_a_shared_address_restores_the_whole_view(driver):
    driver.open(f"/index.html#layer=municipality&area=35")
    driver.settle(900)
    state = driver.state()
    assert state["layer"] == "municipality"
    assert state["areaId"] == "35"
    name = driver.page.evaluate(
        "() => window.maGeo.indexes.areaName('municipality', '35')"
    )
    assert name in driver.text("#selection-status")
    assert name in driver.text("#table-status")
    counts = driver.page.evaluate("() => window.maGeo.indexes.assignments.municipality['35']")
    assert driver.rows().count() == counts["degree_granting_campus_count"]
    assert driver.marker_count() == counts["degree_granting_campus_count"]
    assert driver.area_count() == 351


# --- 7.7 a shared address fetches only what it needs -----------------------

def test_a_shared_county_address_fetches_only_the_county_layer(driver):
    driver.open(f"/index.html#layer=county&area={MIDDLESEX}")
    driver.settle(800)
    assert len(driver.requested("county.geojson")) == 1
    assert driver.requested("municipality.geojson") == []
    assert driver.requested("cbsa.geojson") == []
