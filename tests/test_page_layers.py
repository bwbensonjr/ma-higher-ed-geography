"""Area layers, shading, and the legend (tasks 6.1 - 6.5)."""

import pytest


# --- 6.1 and 6.2 one layer at a time ---------------------------------------

def test_switching_layers_replaces_the_drawn_areas(driver):
    driver.open()
    driver.select_layer("county")
    driver.settle(500)
    assert driver.area_count() == 14
    markers_before = driver.marker_count()

    driver.select_layer("municipality")
    driver.settle(800)
    assert driver.area_count() == 351
    assert driver.marker_count() == markers_before == 206


def test_the_no_layer_view_draws_no_areas_and_keeps_the_markers(driver):
    driver.open()
    driver.select_layer("county")
    driver.settle(500)
    driver.select_layer("none")
    driver.settle(400)
    assert driver.area_count() == 0
    assert driver.marker_count() == 206
    assert driver.page.locator(".legend").count() == 0


def test_each_layer_draws_its_own_feature_count(driver):
    driver.open()
    for layer, expected in (("county", 14), ("municipality", 351), ("cbsa", 10)):
        driver.select_layer(layer)
        driver.settle(700)
        assert driver.area_count() == expected, layer


# --- 6.3 shading ------------------------------------------------------------

def test_a_busy_county_is_shaded_more_intensely_than_a_quiet_one(driver):
    driver.open()
    shades = driver.page.evaluate(
        """async () => {
            const m = await import('./modules/shading.js');
            const index = window.maGeo.indexes;
            const counts = (name) => {
                const entry = Object.entries(index.areaIndex.county)
                    .find(([, area]) => area.name === name);
                return index.assignments.county[entry[0]].campus_count;
            };
            const middlesex = counts('Middlesex');
            const nantucket = counts('Nantucket');
            return {
                middlesex,
                nantucket,
                middlesexClass: m.classIndex('county', middlesex),
                nantucketClass: m.classIndex('county', nantucket),
            };
        }"""
    )
    assert shades["middlesex"] > shades["nantucket"]
    assert shades["middlesexClass"] > shades["nantucketClass"]


def test_an_area_with_no_campuses_is_styled_distinctly_from_the_lightest_class(driver):
    driver.open()
    styles = driver.page.evaluate(
        """async () => {
            const m = await import('./modules/shading.js');
            return {
                empty: m.areaStyle('municipality', 0),
                fewest: m.areaStyle('municipality', 1),
                emptyClass: m.classIndex('municipality', 0),
            };
        }"""
    )
    assert styles["emptyClass"] == -1
    assert styles["empty"]["fillColor"] != styles["fewest"]["fillColor"]
    assert styles["empty"]["fillOpacity"] < styles["fewest"]["fillOpacity"]


def test_the_classes_are_distinguishable_and_let_the_basemap_through(driver):
    driver.open()
    palette = driver.page.evaluate(
        """async () => {
            const m = await import('./modules/shading.js');
            return { colors: m.COLORS, opacity: m.FILL_OPACITY,
                     empty: m.EMPTY_FILL_OPACITY };
        }"""
    )
    colors = palette["colors"]
    assert len(set(colors)) == len(colors)

    def luminance(hex_colour):
        r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    steps = [luminance(colour) for colour in colors]
    assert steps == sorted(steps, reverse=True), steps
    gaps = [round(steps[i] - steps[i + 1], 1) for i in range(len(steps) - 1)]
    assert min(gaps) > 20, gaps
    # Sheer enough that the streets beneath remain visible.
    assert 0.4 <= palette["opacity"] <= 0.75


def test_the_drawn_areas_use_those_styles(driver):
    driver.open()
    driver.select_layer("county")
    driver.settle(600)
    fills = driver.page.evaluate(
        """async () => {
            const m = await import('./modules/shading.js');
            const index = window.maGeo.indexes;
            const map = window.maGeo.map.map;
            const seen = [];
            map.eachLayer((layer) => {
                if (!layer.feature || !layer.feature.properties.area_id) return;
                const areaId = String(layer.feature.properties.area_id);
                const count = index.assignments.county[areaId].campus_count;
                seen.push({
                    actual: layer.options.fillColor,
                    expected: m.colorFor('county', count),
                });
            });
            return seen;
        }"""
    )
    assert len(fills) == 14
    assert all(entry["actual"] == entry["expected"] for entry in fills)


# --- 6.4 the legend ---------------------------------------------------------

def test_the_legend_states_the_ranges_and_changes_with_the_layer(driver):
    driver.open()
    driver.select_layer("county")
    driver.settle(500)
    county_legend = driver.text(".legend")
    assert "Campuses per area" in county_legend
    assert "No campuses" in county_legend

    driver.select_layer("municipality")
    driver.settle(800)
    municipality_legend = driver.text(".legend")
    assert municipality_legend != county_legend


def test_the_legend_matches_the_breaks_used_to_shade(driver):
    driver.open()
    for layer in ("county", "municipality", "cbsa"):
        driver.select_layer(layer)
        driver.settle(700)
        expected = driver.page.evaluate(
            f"""async () => {{
                const m = await import('./modules/shading.js');
                return m.legendEntries('{layer}').map(e => e.label);
            }}"""
        )
        shown = driver.page.evaluate(
            "() => [...document.querySelectorAll('.legend li')].map(li => li.innerText.trim())"
        )
        assert shown == expected, (layer, shown, expected)
        breaks = driver.page.evaluate(
            f"""async () => {{
                const m = await import('./modules/shading.js');
                return m.BREAKS['{layer}'];
            }}"""
        )
        assert expected[-1] == "No campuses"
        assert expected[0] == f"{breaks[-1]}+"


# --- 6.5 hover --------------------------------------------------------------

def test_hovering_an_area_reveals_its_name_and_both_counts(driver):
    driver.open()
    driver.select_layer("county")
    driver.settle(600)
    tooltip = driver.page.evaluate(
        """() => {
            const index = window.maGeo.indexes;
            const map = window.maGeo.map.map;
            let text = null;
            map.eachLayer((layer) => {
                if (!layer.feature || text) return;
                if (layer.feature.properties.name !== 'Suffolk') return;
                text = layer.getTooltip().getContent();
            });
            const entry = Object.entries(index.areaIndex.county)
                .find(([, area]) => area.name === 'Suffolk');
            const counts = index.assignments.county[entry[0]];
            return { text, counts };
        }"""
    )
    assert "Suffolk" in tooltip["text"]
    assert str(tooltip["counts"]["campus_count"]) in tooltip["text"]
    assert str(tooltip["counts"]["institution_count"]) in tooltip["text"]
    assert "campuses" in tooltip["text"] and "institution" in tooltip["text"]
