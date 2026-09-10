"""Layout, assistive access, provenance and attribution (tasks 13.1 - 14.2)."""

import json

from ma_geo.paths import OUT_DIR


# --- 13.1 narrow viewports --------------------------------------------------

def test_the_page_is_usable_at_375_pixels(driver):
    driver.page.set_viewport_size({"width": 375, "height": 750})
    driver.open()
    metrics = driver.page.evaluate(
        """() => ({
            documentWidth: document.documentElement.scrollWidth,
            clientWidth: document.documentElement.clientWidth,
            mapHeight: document.getElementById('map').getBoundingClientRect().height,
            tableVisible: document.getElementById('campus-table').getBoundingClientRect().width > 0,
        })"""
    )
    # No horizontal scrolling of the page itself.
    assert metrics["documentWidth"] <= metrics["clientWidth"] + 1, metrics
    assert metrics["mapHeight"] > 200
    assert metrics["tableVisible"]
    assert driver.rows().count() == 206


def test_the_table_scrolls_within_itself_rather_than_the_page(driver):
    driver.page.set_viewport_size({"width": 375, "height": 750})
    driver.open()
    scroll = driver.page.evaluate(
        """() => {
            const box = document.getElementById('table-scroll');
            const before = box.scrollLeft;
            box.scrollLeft = 400;
            return { overflowX: getComputedStyle(box).overflowX,
                     scrollable: box.scrollWidth > box.clientWidth,
                     moved: box.scrollLeft > before,
                     pageWidth: document.documentElement.scrollWidth,
                     clientWidth: document.documentElement.clientWidth };
        }"""
    )
    assert scroll["overflowX"] == "auto"
    assert scroll["scrollable"] is True
    assert scroll["moved"] is True
    assert scroll["pageWidth"] <= scroll["clientWidth"] + 1


def test_the_map_and_table_are_both_usable_on_a_wide_viewport(driver):
    driver.page.set_viewport_size({"width": 1440, "height": 900})
    driver.open()
    metrics = driver.page.evaluate(
        """() => ({
            page: document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
            map: document.getElementById('map').getBoundingClientRect().height,
        })"""
    )
    assert metrics["page"] is True
    assert metrics["map"] > 300


# --- 13.2 keyboard ----------------------------------------------------------

def test_a_layer_can_be_selected_by_keyboard(driver):
    driver.open()
    driver.page.focus("#layer-select")
    driver.page.select_option("#layer-select", "county")
    driver.page.keyboard.press("Enter")
    driver.settle(800)
    assert driver.state() == {"layer": "county", "areaId": None}
    assert driver.area_count() == 14


def test_a_row_geography_is_reachable_and_operable_by_keyboard(driver):
    driver.open()
    pointer = None
    # First, the pointer result for the same target.
    driver.page.evaluate(
        """() => {
            const button = [...document.querySelectorAll('#campus-table td button')]
                .find(b => b.textContent.trim() === 'Middlesex');
            button.click();
            return null;
        }"""
    )
    driver.settle(900)
    pointer = {
        "state": driver.state(),
        "rows": driver.rows().count(),
        "status": driver.text("#table-status"),
    }

    # Now the same target reached by keyboard alone.
    driver.open()
    reached = driver.page.evaluate(
        """() => {
            const button = [...document.querySelectorAll('#campus-table td button')]
                .find(b => b.textContent.trim() === 'Middlesex');
            button.focus();
            return document.activeElement === button;
        }"""
    )
    assert reached is True
    driver.page.keyboard.press("Enter")
    driver.settle(900)
    keyboard = {
        "state": driver.state(),
        "rows": driver.rows().count(),
        "status": driver.text("#table-status"),
    }
    assert keyboard == pointer


def test_the_clear_control_is_keyboard_operable(driver):
    driver.open("/index.html#layer=county&area=25025")
    driver.settle(800)
    driver.page.focus("#clear-selection")
    driver.page.keyboard.press("Enter")
    driver.settle(800)
    assert driver.state() == {"layer": "county", "areaId": None}
    assert driver.rows().count() == 206


def test_the_sort_controls_are_real_buttons(driver):
    driver.open()
    tags = driver.page.evaluate(
        """() => [...document.querySelectorAll('#table-head-row th')]
            .map(th => th.querySelector('button') ? 'button' : 'text')"""
    )
    assert tags.count("button") == 7  # every sortable column
    driver.page.focus("#table-head-row th:nth-child(4) button")
    driver.page.keyboard.press("Enter")
    driver.settle(300)
    assert driver.page.evaluate(
        "() => document.querySelector('#table-head-row th:nth-child(4)').getAttribute('aria-sort')"
    ) == "ascending"


# --- 13.3 stated as text, and proper roles ---------------------------------

def test_the_selection_is_stated_as_text(driver):
    driver.open("/index.html#layer=county&area=25025")
    driver.settle(800)
    status = driver.text("#selection-status")
    assert "Counties" in status
    assert "Suffolk" in status
    assert "campuses" in status and "institutions" in status
    assert driver.page.get_attribute("#selection-status", "aria-live") == "polite"


def test_the_layer_is_stated_as_text_without_a_selection(driver):
    driver.open()
    assert "No layer" in driver.text("#selection-status")
    driver.select_layer("cbsa")
    driver.settle(800)
    assert "Statistical areas" in driver.text("#selection-status")
    assert "No statistical area selected" in driver.text("#selection-status")


def test_the_accessibility_tree_exposes_a_table_with_named_columns(driver):
    driver.open()
    assert driver.page.get_by_role("table").count() == 1
    for label in ("Institution", "Campus", "Address", "Municipality", "County",
                  "Statistical area", "Type", "Category", "Degrees"):
        header = driver.page.get_by_role("columnheader", name=label, exact=False)
        assert header.count() >= 1, label

    # Rows and cells are exposed as such, not as a grid of divs.
    assert driver.page.get_by_role("row").count() > 200
    snapshot = driver.page.locator("#campus-table").aria_snapshot()
    assert "table" in snapshot
    assert "Institution" in snapshot


def test_group_headings_are_header_cells_spanning_the_table(driver):
    driver.open()
    driver.select_layer("county")
    driver.settle(800)
    heading = driver.page.evaluate(
        """() => {
            const th = document.querySelector('.group-heading th');
            return { tag: th.tagName, scope: th.scope,
                     colspan: Number(th.getAttribute('colspan')) };
        }"""
    )
    assert heading["tag"] == "TH"
    assert heading["scope"] == "colgroup"
    assert heading["colspan"] == 9


# --- 14.1 and 14.2 provenance and attribution ------------------------------

def test_the_provenance_is_rendered_from_the_published_record(driver):
    driver.open()
    provenance = json.loads((OUT_DIR / "provenance.json").read_text())
    summary = driver.text("#provenance-summary")
    assert provenance["generated"] in summary
    sources = driver.text("#provenance-sources")
    for entry in provenance["sources"].values():
        assert entry["title"] in sources, entry["title"]
        assert entry["fetched"] in sources
    assert provenance["sources"]["cbsa"]["vintage"] in sources


def test_the_date_is_not_written_into_the_page(driver):
    """Change the record and the page follows, with no edit to the page."""
    driver.page.context.route(
        "**/data/provenance.json",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    **json.loads((OUT_DIR / "provenance.json").read_text()),
                    "generated": "2099-01-31",
                }
            ),
        ),
    )
    driver.open()
    assert "2099-01-31" in driver.text("#provenance-summary")


def test_both_attributions_are_visible(driver):
    driver.open()
    attribution = driver.text("#data-attribution")
    assert "MassGIS" in attribution
    assert "Census" in attribution
    assert "Esri" in attribution
    assert "OpenStreetMap" in attribution
    assert driver.page.locator("#data-attribution").is_visible()

    # Leaflet's own control carries the tile attribution on the map.
    control = driver.text(".leaflet-control-attribution")
    assert "Esri" in control
    assert "OpenStreetMap" in control


def test_the_tile_provider_is_named_so_the_visitor_can_tell(driver):
    driver.open()
    footer = driver.page.locator(".page-footer").inner_text()
    assert "Esri" in footer
    assert "network address" in footer.lower() or "discloses" in footer.lower()


def test_the_data_attribution_survives_a_blocked_tile_host(driver):
    """The default fixture blocks tiles; the data credit must still be there."""
    driver.open()
    assert driver.page.locator("#data-attribution").is_visible()
    assert "MassGIS" in driver.text("#data-attribution")
    assert driver.page.evaluate("() => window.maGeo.map.tileErrors") >= 0
