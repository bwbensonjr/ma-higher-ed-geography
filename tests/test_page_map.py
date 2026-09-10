"""The map: base tiles, markers, campus detail (tasks 5.1 - 5.5)."""

import pytest


# --- 5.1 the base map -------------------------------------------------------

@pytest.mark.tiles
def test_tiles_load_and_render_at_the_closest_zoom(tiled_driver):
    driver = tiled_driver
    driver.open()
    driver.settle(1200)
    assert len(driver.tile_requests()) > 0, "no tiles were requested"

    loaded = driver.page.evaluate(
        """() => {
            const tiles = [...document.querySelectorAll('.leaflet-tile')];
            return tiles.filter(t => t.complete && t.naturalWidth > 0).length;
        }"""
    )
    assert loaded > 0, "tiles were requested but none decoded"

    # Street level: the closest zoom the map offers must still have tiles.
    driver.page.evaluate(
        "() => { window.maGeo.map.map.setView([42.3736, -71.1097], 19); return null; }"
    )
    driver.settle(1500)
    deep = driver.page.evaluate(
        """() => {
            const tiles = [...document.querySelectorAll('.leaflet-tile')];
            return tiles.filter(t => t.complete && t.naturalWidth > 0).length;
        }"""
    )
    assert deep > 0, "the closest zoom rendered no tiles"


def test_the_tile_layer_is_configured_keyless_to_street_level(driver):
    driver.open()
    config = driver.page.evaluate(
        """async () => {
            const m = await import('./modules/map.js');
            return { url: m.TILE_URL, attribution: m.TILE_ATTRIBUTION,
                     maxZoom: window.maGeo.map.map.getMaxZoom(),
                     minZoom: window.maGeo.map.map.getMinZoom() };
        }"""
    )
    assert "server.arcgisonline.com" in config["url"]
    assert "World_Light_Gray_Base" in config["url"]
    # No API key, no token, no account parameter: a public static page
    # cannot keep a secret, and a keyed provider serves placeholder tiles.
    assert "key" not in config["url"].lower()
    assert "token" not in config["url"].lower()
    assert "Esri" in config["attribution"]
    assert "OpenStreetMap" in config["attribution"]
    assert config["maxZoom"] >= 19
    assert config["minZoom"] <= 8


def test_the_tiles_sit_beneath_the_areas_and_the_markers(driver):
    driver.open()
    driver.select_layer("county")
    driver.settle(400)
    order = driver.page.evaluate(
        """() => {
            const style = (name) => {
                const pane = document.querySelector('.leaflet-' + name + '-pane')
                    || document.querySelector('.leaflet-pane.leaflet-' + name + '-pane');
                return pane ? Number(getComputedStyle(pane).zIndex) : null;
            };
            const map = window.maGeo.map.map;
            return {
                tiles: Number(getComputedStyle(map.getPane('tilePane')).zIndex),
                areas: Number(getComputedStyle(map.getPane('areas')).zIndex),
                markers: Number(getComputedStyle(map.getPane('markers')).zIndex),
            };
        }"""
    )
    assert order["tiles"] < order["areas"] < order["markers"], order


# --- 5.2 markers ------------------------------------------------------------

def test_the_map_renders_one_marker_per_campus(driver):
    driver.open()
    assert driver.marker_count() == 150  # the default population
    driver.include_all_schools()
    assert driver.marker_count() == 206


def test_a_seven_campus_institution_contributes_seven_markers(driver):
    driver.open()
    harvard = driver.page.evaluate(
        """() => {
            const campuses = window.maGeo.indexes.campuses
                .filter(c => c.institution_id === 'harvard-university');
            return { count: campuses.length,
                     places: [...new Set(campuses.map(c => c.municipality_id))].length };
        }"""
    )
    assert harvard["count"] == 7
    assert harvard["places"] >= 2


def test_markers_are_drawn_from_the_published_coordinates(driver):
    driver.open()
    matches = driver.page.evaluate(
        """() => {
            const campus = window.maGeo.indexes.campusById.get('harvard-university--main-campus')
                || window.maGeo.indexes.campuses[0];
            return { lat: campus.lat, lon: campus.lon };
        }"""
    )
    assert 41 < matches["lat"] < 43.5
    assert -74 < matches["lon"] < -69


# --- 5.3 and 5.4 the campus popup ------------------------------------------

def test_the_popup_shows_every_published_field(driver):
    driver.open()
    popup = driver.page.evaluate(
        """async () => {
            const m = await import('./modules/map.js');
            const campus = window.maGeo.indexes.campusById.get('williams-college');
            const node = m.campusPopup(campus);
            const link = node.querySelector('a');
            return { text: node.innerText, href: link ? link.href : null, campus };
        }"""
    )
    campus = popup["campus"]
    for field in ("institution", "address", "city", "zip_code", "telephone",
                  "category", "degrees_offered"):
        value = str(campus[field]).strip()
        assert value in popup["text"].replace("\n", " "), field
    # The source publishes the type as a code; the page labels it.
    assert campus["institution_type"] in ("PUB", "PRI")
    label = "Public" if campus["institution_type"] == "PUB" else "Private"
    assert label in popup["text"]
    assert popup["href"].startswith("http")


def test_the_popup_omits_empty_attributes(driver):
    driver.open()
    popup = driver.page.evaluate(
        """async () => {
            const m = await import('./modules/map.js');
            const campus = { ...window.maGeo.indexes.campuses[0],
                             campus: null, telephone: '', website: null };
            const node = m.campusPopup(campus);
            return { html: node.innerHTML, text: node.innerText };
        }"""
    )
    assert "Telephone" not in popup["text"]
    assert "Website" not in popup["text"]
    assert "campus-name" not in popup["html"]
    for placeholder in ("null", "undefined", "None", "NaN"):
        assert placeholder not in popup["html"], placeholder


def test_a_real_campus_with_no_campus_name_omits_it(driver):
    driver.open()
    result = driver.page.evaluate(
        """async () => {
            const m = await import('./modules/map.js');
            const campus = window.maGeo.indexes.campuses.find(c => !c.campus);
            const node = m.campusPopup(campus);
            return { id: campus.id, html: node.innerHTML };
        }"""
    )
    assert "campus-name" not in result["html"]
    assert "null" not in result["html"]


def test_clicking_a_marker_opens_its_popup(driver):
    driver.open()
    driver.page.evaluate("() => window.maGeo.map.openCampus('williams-college')")
    driver.settle(300)
    popup = driver.page.locator(".leaflet-popup-content")
    assert popup.count() == 1
    assert "Williams College" in popup.inner_text()


# --- 5.5 markers stay prominent --------------------------------------------

def test_markers_are_styled_to_stay_prominent_over_grey_tiles(driver):
    driver.open()
    style = driver.page.evaluate(
        """() => {
            const map = window.maGeo.map.map;
            let found = null;
            map.eachLayer((layer) => {
                if (layer.campusId && !found) found = layer.options;
            });
            return found;
        }"""
    )
    assert style["fillOpacity"] >= 0.9
    assert style["radius"] >= 4
    assert style["weight"] >= 1
    assert style["fillColor"].lower() == "#e8442a"


@pytest.mark.tiles
def test_a_marker_is_distinguishable_at_both_zooms(tiled_driver):
    """The marker's own pixels survive over the basemap, statewide and close in."""
    driver = tiled_driver
    driver.open()
    driver.settle(1200)

    def marker_pixels():
        return driver.page.evaluate(
            """() => {
                const canvases = [...document.querySelectorAll('.leaflet-pane canvas')];
                let hits = 0;
                for (const canvas of canvases) {
                    const context = canvas.getContext('2d');
                    if (!context) continue;
                    const { width, height } = canvas;
                    if (!width || !height) continue;
                    const data = context.getImageData(0, 0, width, height).data;
                    for (let i = 0; i < data.length; i += 4) {
                        const [r, g, b, a] = [data[i], data[i+1], data[i+2], data[i+3]];
                        if (a > 200 && r > 190 && g < 110 && b < 90) hits += 1;
                    }
                }
                return hits;
            }"""
        )

    statewide = marker_pixels()
    assert statewide > 0, "no marker pixels at the statewide view"

    # Centre on an actual campus, so street zoom has a marker to show.
    driver.page.evaluate(
        """() => {
            const campus = window.maGeo.indexes.campusById.get('williams-college');
            window.maGeo.map.map.setView([campus.lat, campus.lon], 18);
            return null;
        }"""
    )
    driver.settle(1500)
    assert marker_pixels() > 0, "no marker pixels at street zoom"


@pytest.mark.tiles
def test_the_tile_provider_serves_real_tiles_not_a_placeholder():
    """The regression this suite missed once.

    A provider that has started requiring an account answers every tile
    request with HTTP 200 and the same "API KEY REQUIRED" watermark, so
    nothing errors and the map looks broken only to a human -- which is how
    CARTO Positron, this page's first basemap, failed. Tiles over three
    different cities must therefore differ from one another.
    """
    import math
    import urllib.request

    from conftest import TILE_URL_TEMPLATE

    def fetch(lat, lon, zoom=10):
        n = 2 ** zoom
        x = int((lon + 180.0) / 360.0 * n)
        y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)
        request = urllib.request.Request(
            TILE_URL_TEMPLATE.format(z=zoom, x=x, y=y),
            headers={"User-Agent": "ma-higher-ed-geography verification suite"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            assert response.status == 200
            return response.read()

    # Built-up ground, where a real basemap has plenty to draw. Ocean tiles
    # are legitimately identical, so they would prove nothing.
    tiles = [
        fetch(42.3601, -71.0589),  # Boston
        fetch(42.2626, -71.8023),  # Worcester
        fetch(42.1015, -72.5898),  # Springfield
    ]
    assert len({bytes(tile) for tile in tiles}) == 3, (
        "tiles over three different cities came back identical, which is "
        "what a placeholder or watermark tile looks like"
    )
    assert all(len(tile) > 3000 for tile in tiles), [len(t) for t in tiles]


@pytest.mark.tiles
def test_the_basemap_is_grey_and_upscales_past_its_native_ceiling(tiled_driver):
    """Esri's light gray canvas stops at zoom 16; the map still reaches 19."""
    driver = tiled_driver
    driver.open()
    driver.settle(1500)
    config = driver.page.evaluate(
        """async () => {
            const m = await import('./modules/map.js');
            let layer = null;
            window.maGeo.map.map.eachLayer((candidate) => {
                if (candidate._url && !layer) layer = candidate;
            });
            return { native: m.TILE_MAX_NATIVE_ZOOM,
                     layerNative: layer.options.maxNativeZoom,
                     layerMax: layer.options.maxZoom,
                     mapMax: window.maGeo.map.map.getMaxZoom() };
        }"""
    )
    assert config["native"] == 16
    assert config["layerNative"] == 16
    assert config["mapMax"] >= 19

    # Past the ceiling the basemap upscales rather than going blank.
    driver.page.evaluate(
        """() => {
            const campus = window.maGeo.indexes.campusById.get('williams-college');
            window.maGeo.map.map.setView([campus.lat, campus.lon], 19);
            return null;
        }"""
    )
    driver.settle(2000)
    decoded = driver.page.evaluate(
        """() => [...document.querySelectorAll('.leaflet-tile')]
            .filter(t => t.complete && t.naturalWidth > 0).length"""
    )
    assert decoded > 0, "the closest zoom rendered no tiles"

    # And the markers keep their own colour over it.
    colour = driver.page.evaluate(
        """() => {
            let found = null;
            window.maGeo.map.map.eachLayer((layer) => {
                if (layer.campusId && !found) found = layer.options.fillColor;
            });
            return found;
        }"""
    )
    assert colour.lower() == "#e8442a"
