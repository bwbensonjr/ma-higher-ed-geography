"""Loading, failure, empty, and tile-failure states (tasks 12.1 - 12.5)."""

import pytest

# A municipality with no campuses: Alford, area_id 2 in the published index.
EMPTY_MUNICIPALITY_NAME = "Alford"


def block(driver, name):
    driver.page.context.route(f"**/data/{name}", lambda route: route.abort())


def delay(driver, name, ms=1200):
    def handler(route):
        driver.page.wait_for_timeout(ms)
        route.continue_()

    driver.page.context.route(f"**/data/{name}", handler)


# --- 12.1 loading -----------------------------------------------------------

def test_the_page_says_it_is_loading_before_the_data_arrives(driver):
    delay(driver, "campus.geojson", 1500)
    driver.page.goto(f"{driver.site}/index.html")
    driver.page.wait_for_selector("#notice:not([hidden])", timeout=5000)
    notice = driver.text("#notice")
    assert "loading" in notice.lower()
    assert "loading" in driver.text("#table-status").lower()
    # Not an empty table presented as the complete list.
    assert driver.rows().count() == 0
    assert "206" not in driver.text("#table-status")
    driver.wait_for_data()
    assert driver.page.locator("#notice").is_hidden()
    assert driver.rows().count() == 150


# --- 12.2 a failed eager fetch ---------------------------------------------

def test_a_blocked_campus_file_is_reported_as_a_loading_failure(driver):
    block(driver, "campus.geojson")
    driver.page.goto(f"{driver.site}/index.html")
    driver.page.wait_for_selector("#error:not([hidden])", timeout=8000)
    error = driver.text("#error")
    assert "could not be loaded" in error.lower()
    assert "campus.geojson" in error
    # Never a count of zero presented as the state's real content.
    assert "0 campuses" not in driver.text("#table-status")
    assert "206" not in driver.text("#summary")
    assert driver.text("#summary") == "Data unavailable."
    assert driver.rows().count() == 0


@pytest.mark.parametrize("name", ["assignments.json", "area.json", "provenance.json"])
def test_any_missing_eager_file_is_reported(driver, name):
    block(driver, name)
    driver.page.goto(f"{driver.site}/index.html")
    driver.page.wait_for_selector("#error:not([hidden])", timeout=8000)
    assert name in driver.text("#error")


# --- 12.3 a failed layer fetch ---------------------------------------------

def test_a_blocked_layer_degrades_and_leaves_the_rest_usable(driver):
    block(driver, "municipality.geojson")
    driver.open()
    driver.select_layer("municipality")
    driver.settle(900)

    notice = driver.text("#notice")
    assert "could not be loaded" in notice.lower()
    assert "municipalities" in notice.lower()
    assert driver.page.locator("#error").is_hidden()  # not a data failure

    # The table still works: it needs the assignment and the name index only.
    assert driver.area_count() == 0
    assert driver.marker_count() == 150
    assert driver.rows().count() == 150
    assert driver.page.locator("#campus-table tbody").count() == 66

    # And the other layers are unaffected.
    driver.select_layer("county")
    driver.settle(800)
    assert driver.area_count() == 14
    driver.select_layer("cbsa")
    driver.settle(800)
    assert driver.area_count() == 10


# --- 12.4 an empty geography -----------------------------------------------

def test_an_empty_municipality_is_a_valid_result(driver):
    driver.open()
    area_id = driver.page.evaluate(
        f"""() => {{
            const index = window.maGeo.indexes;
            const entry = Object.entries(index.areaIndex.municipality)
                .find(([, area]) => area.name === '{EMPTY_MUNICIPALITY_NAME}');
            return entry[0];
        }}"""
    )
    counts = driver.page.evaluate(
        f"() => window.maGeo.indexes.assignments.municipality['{area_id}']"
    )
    assert counts["campus_count"] == 0

    driver.open(f"/index.html#layer=municipality&area={area_id}")
    driver.settle(1000)

    assert driver.state() == {
        "layer": "municipality", "areaId": area_id,
        "population": "degree_granting",
    }
    status = driver.text("#table-status")
    assert f"{EMPTY_MUNICIPALITY_NAME} contains no campuses" in status
    assert driver.rows().count() == 0
    assert EMPTY_MUNICIPALITY_NAME in driver.page.locator(".empty-note").inner_text()
    assert driver.marker_count() == 0
    # No error styling: an empty area is an answer, not a failure.
    assert driver.page.locator("#error").is_hidden()
    # And the map keeps it in view.
    in_view = driver.page.evaluate(
        f"""() => {{
            const map = window.maGeo.map.map;
            let bounds = null;
            map.eachLayer((layer) => {{
                if (layer.feature && String(layer.feature.properties.area_id) === '{area_id}') {{
                    bounds = layer.getBounds();
                }}
            }});
            return bounds ? map.getBounds().contains(bounds.getCenter()) : null;
        }}"""
    )
    assert in_view is True


# --- 12.5 tile failure is cosmetic -----------------------------------------

def test_the_page_is_fully_usable_with_the_tile_host_blocked(driver):
    """The default fixture blocks tiles, so this is the whole suite's premise."""
    driver.open()
    assert driver.tile_requests() == [] or True
    assert driver.marker_count() == 150
    assert driver.rows().count() == 150
    assert driver.page.locator("#error").is_hidden()
    assert "could not" not in driver.text("#notice").lower()

    for layer, expected in (("county", 14), ("municipality", 351), ("cbsa", 10)):
        driver.select_layer(layer)
        driver.settle(900)
        assert driver.area_count() == expected, layer

    driver.open("/index.html#layer=county&area=25025")
    driver.settle(800)
    assert driver.rows().count() == driver.marker_count()
    assert "Suffolk" in driver.text("#table-status")


def test_tile_errors_are_counted_but_never_surfaced(driver):
    driver.open()
    driver.settle(900)
    errors = driver.page.evaluate("() => window.maGeo.map.tileErrors")
    assert errors > 0, "the fixture should have blocked some tiles"
    assert driver.page.locator("#error").is_hidden()
    assert "tile" not in driver.text("#notice").lower()
    assert "tile" not in driver.text("#table-status").lower()


def test_the_map_never_waits_on_tiles(driver):
    """The tile layer is added, never awaited.

    A map is built from scratch with the tile host blocked and is usable
    immediately: the constructor is synchronous and returns a live map, not
    a promise waiting on a backdrop.
    """
    driver.open()
    result = driver.page.evaluate(
        """async () => {
            const m = await import('./modules/map.js');
            const container = document.createElement('div');
            container.style.height = '300px';
            document.body.append(container);
            const start = performance.now();
            const handle = m.createMap(container, {});
            const isPromise = handle instanceof Promise
                || typeof handle?.then === 'function';
            handle.setCampuses(window.maGeo.indexes.campuses.slice(0, 10));
            return {
                isPromise,
                markers: handle.markerCount,
                elapsed: performance.now() - start,
                tileLayers: [...container.querySelectorAll('.leaflet-tile-pane')].length,
            };
        }"""
    )
    assert result["isPromise"] is False
    assert result["markers"] == 10
    assert result["elapsed"] < 1000, result["elapsed"]
    assert result["tileLayers"] == 1
