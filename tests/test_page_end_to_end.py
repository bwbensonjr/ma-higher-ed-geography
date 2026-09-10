"""The page, end to end (tasks 15.1 - 15.2).

One test that exercises the whole page the way a visitor would, and one that
pins down what the page asks the network for. Everything the page reports
comes from this repository; the only third party is the base map.
"""

import pytest

SUFFOLK = "25025"


def test_the_whole_page_works_with_the_tile_host_blocked(driver):
    driver.open()

    # The first view: the degree-granting population, summary, full table.
    assert driver.marker_count() == 150
    assert driver.rows().count() == 150
    assert "150 campuses" in driver.text("#summary")
    assert "116 institutions" in driver.text("#summary")

    driver.include_all_schools()
    assert driver.marker_count() == 206
    assert driver.rows().count() == 206
    assert "206 campuses" in driver.text("#summary")
    assert "160 institutions" in driver.text("#summary")

    # Every layer draws.
    for layer, areas in (("county", 14), ("municipality", 351), ("cbsa", 10)):
        driver.select_layer(layer)
        driver.settle(900)
        assert driver.area_count() == areas, layer
        assert driver.rows().count() == 206, layer

    # Selection restricts map and table together, and clearing restores both.
    driver.select_layer("county")
    driver.settle(800)
    driver.page.evaluate(
        """() => {
            const heading = [...document.querySelectorAll('.group-heading button')]
                .find(button => button.textContent.trim() === 'Suffolk');
            heading.click();
            return null;
        }"""
    )
    driver.settle(900)
    counts = driver.page.evaluate(
        f"() => window.maGeo.indexes.assignments.county['{SUFFOLK}']"
    )
    assert driver.rows().count() == counts["campus_count"]
    assert driver.marker_count() == counts["campus_count"]
    driver.page.click("#clear-selection")
    driver.settle(800)
    assert driver.rows().count() == 206

    # And none of it reported a failure.
    assert driver.page.locator("#error").is_hidden()


def test_the_only_foreign_requests_are_tiles(tiled_driver):
    """With tiles allowed, nothing else leaves the origin."""
    driver = tiled_driver
    driver.open()
    driver.settle(1200)
    driver.select_layer("county")
    driver.settle(900)

    foreign = [url for url in driver.foreign_requests() if "arcgisonline.com" not in url]
    assert foreign == [], foreign
    assert len(driver.tile_requests()) > 0

    # Every one of the page's own files came from the serving origin.
    own = [url for url in driver.same_origin_requests()]
    assert any(url.endswith("/app.js") for url in own)
    assert any("vendor/leaflet" in url for url in own)
    assert any(url.endswith("/data/campus.geojson") for url in own)


def test_the_page_makes_no_analytics_or_telemetry_request(driver):
    driver.open()
    driver.select_layer("municipality")
    driver.settle(900)
    driver.open("/index.html#layer=county&area=25025")
    driver.settle(900)
    suspicious = [
        url
        for url in driver.requests
        if any(
            token in url.lower()
            for token in ("analytics", "telemetry", "collect", "beacon", "gtag", "sentry")
        )
    ]
    assert suspicious == [], suspicious
