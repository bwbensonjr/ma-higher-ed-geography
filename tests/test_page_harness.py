"""The harness itself works (tasks 3.1 - 3.3)."""


def test_the_page_loads_with_its_title_and_map(driver):
    driver.open()
    assert "Massachusetts College and University Geography" in driver.page.title()
    assert driver.page.locator("#map").is_visible()
    assert driver.page.locator(".leaflet-container").count() == 1


def test_no_console_errors_on_load(driver):
    """Blocked tile requests are the one expected resource failure.

    They are logged by the browser, not by the page, and the tile host is
    blocked by this very fixture -- which is the cosmetic degradation the
    design intends. Anything else is a real error.
    """
    errors = []

    def on_console(message):
        if message.type != "error":
            return
        origin = (message.location or {}).get("url", "")
        if "arcgisonline.com" in origin:
            return
        errors.append(f"{message.text} @ {origin}")

    driver.page.on("console", on_console)
    driver.page.on("pageerror", lambda error: errors.append(f"pageerror: {error}"))
    driver.open()
    driver.select_layer("county")
    assert errors == [], errors


def test_modules_can_be_called_directly(blank):
    """A trivial round-trip, so later logic tests need no UI."""
    parsed = blank.eval_module("state", "m.parseHash('#layer=county&area=25025')")
    assert parsed == {"layer": "county", "areaId": "25025"}
    assert blank.eval_module("state", "m.encodeState({layer:'county',areaId:'25025'})") == (
        "#layer=county&area=25025"
    )


def test_the_recorder_reports_the_eager_files_and_separates_tiles(driver):
    driver.open()
    names = [url.rsplit("/", 1)[-1] for url in driver.data_requests()]
    assert sorted(names) == [
        "area.json",
        "assignments.json",
        "campus.geojson",
        "provenance.json",
    ]
    assert all("arcgisonline.com" in url for url in driver.tile_requests())
    assert all(url.startswith(driver.site) for url in driver.same_origin_requests())


def test_every_request_but_tiles_is_same_origin(driver):
    driver.open()
    driver.select_layer("county")
    foreign = [url for url in driver.foreign_requests() if "arcgisonline.com" not in url]
    assert foreign == [], foreign
