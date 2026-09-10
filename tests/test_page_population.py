"""The degree-granting default and its control (tasks 4.3 - 7.3)."""

import json
import re
from pathlib import Path

import pytest

from ma_geo.paths import OUT_DIR, REPO_ROOT

DOCS = REPO_ROOT / "docs"
SUFFOLK = "25025"
BOSTON = "35"


@pytest.fixture(scope="module")
def published():
    return {
        name: json.loads((OUT_DIR / name).read_text())
        for name in ("assignments.json", "area.json", "provenance.json")
    }


def area_id(published, layer, name):
    return next(
        a for a, entry in published["area.json"][layer].items() if entry["name"] == name
    )


# --- 4.3 one filter point ---------------------------------------------------

def test_only_the_index_filters_on_the_published_flag():
    """The population is applied in one place, so nothing can disagree.

    counts.js names the published count *fields* and state.js names the
    population, which is not the same as filtering campuses on the flag.
    """
    offenders = []
    for path in [*(DOCS / "modules").glob("*.js"), DOCS / "app.js"]:
        if path.name == "indexes.js":
            continue
        for match in re.finditer(r"\.degree_granting\b(?!_)", path.read_text()):
            offenders.append((path.name, match.group(0)))
    assert offenders == [], offenders


def test_the_index_exposes_the_population_through_two_functions(driver):
    driver.open()
    api = driver.page.evaluate(
        """() => {
            const index = window.maGeo.indexes;
            return {
                defaultCount: index.campusesFor({population: 'degree_granting'}).length,
                allCount: index.campusesFor({population: 'all'}).length,
                suffolkDefault: index.campusesIn('county', '25025',
                    {population: 'degree_granting'}).length,
                suffolkAll: index.campusesIn('county', '25025',
                    {population: 'all'}).length,
                published: index.allCampusesIn('county', '25025').length,
            };
        }"""
    )
    assert api == {
        "defaultCount": 150, "allCount": 206,
        "suffolkDefault": 38, "suffolkAll": 40, "published": 40,
    }


# --- 5.1 to 5.3 the control ------------------------------------------------

def test_the_control_is_off_by_default_and_named_recognizably(driver):
    driver.open()
    assert driver.page.is_checked("#population-toggle") is False
    label = driver.page.locator("label[for='population-toggle']").inner_text().lower()
    for word in ("vocational", "cosmetology", "adult-education"):
        assert word in label, word
    assert "sub-associate" not in label
    assert "2-year" not in label


def test_the_control_writes_the_hash_rather_than_rendering_directly(driver):
    driver.open()
    assert driver.page.evaluate("() => window.location.hash") == ""
    driver.include_all_schools()
    assert "population=all" in driver.page.evaluate("() => window.location.hash")
    driver.include_all_schools(False)
    assert driver.page.evaluate("() => window.location.hash") == ""


def test_the_control_is_keyboard_operable(driver):
    driver.open()
    pointer_rows = None
    driver.include_all_schools()
    pointer_rows = driver.rows().count()
    driver.include_all_schools(False)

    driver.page.focus("#population-toggle")
    driver.page.keyboard.press("Space")
    driver.settle(500)
    assert driver.state()["population"] == "all"
    assert driver.rows().count() == pointer_rows == 206


def test_the_population_is_stated_as_text(driver):
    driver.open()
    assert "degree-granting" in driver.summary().lower()
    assert "degree-granting" in driver.text("#selection-status").lower()
    assert "degree-granting" in driver.text("#table-status").lower()

    driver.include_all_schools()
    text = f"{driver.summary()} {driver.text('#selection-status')} {driver.text('#table-status')}".lower()
    assert "vocational" in text or "adult education" in text


# --- 6.1 to 6.3 markers, rows, counts --------------------------------------

def test_the_markers_follow_the_population(driver):
    driver.open()
    assert driver.marker_count() == 150
    excluded = driver.page.evaluate(
        """() => {
            const drawn = [];
            window.maGeo.map.map.eachLayer((layer) => {
                if (layer.campusId) drawn.push(layer.campusId);
            });
            const index = window.maGeo.indexes;
            return drawn.filter((id) => !index.campusById.get(id).degree_granting);
        }"""
    )
    assert excluded == []
    driver.include_all_schools()
    assert driver.marker_count() == 206


def test_no_cosmetology_campus_is_listed_by_default(driver):
    driver.open()
    names = driver.page.evaluate(
        """() => [...document.querySelectorAll(
            '#campus-table tbody tr:not(.group-heading)')]
            .map(tr => tr.querySelectorAll('td')[0].innerText.toLowerCase())"""
    )
    for word in ("beauty", "nail", "hairdressing", "barbering", "cosmetology"):
        assert not [n for n in names if word in n], word
    driver.include_all_schools()
    widened = driver.page.evaluate(
        """() => [...document.querySelectorAll(
            '#campus-table tbody tr:not(.group-heading)')]
            .map(tr => tr.querySelectorAll('td')[0].innerText.toLowerCase())"""
    )
    assert [n for n in widened if "beauty" in n]


def test_the_rows_follow_the_population_in_all_three_modes(driver, published):
    driver.open()
    assert driver.rows().count() == 150

    driver.select_layer("county")
    driver.settle(700)
    assert driver.rows().count() == 150

    driver.open(f"/index.html#layer=county&area={SUFFOLK}")
    driver.settle(700)
    entry = published["assignments.json"]["county"][SUFFOLK]
    assert driver.rows().count() == entry["degree_granting_campus_count"] == 38


def test_the_summary_states_each_population_from_published_figures(driver, published):
    driver.open()
    summary = driver.summary()
    assert "150 campuses" in summary
    assert "116 institutions" in summary
    assert published["provenance.json"]["degree_granting_institution_count"] == 116

    driver.include_all_schools()
    widened = driver.summary()
    assert "206 campuses" in widened
    assert "160 institutions" in widened


def test_no_count_is_derived_by_subtraction(driver, published):
    """Each population's figures come from its own published fields."""
    driver.open()
    for layer in ("county", "municipality", "cbsa"):
        checked = driver.page.evaluate(
            f"""async () => {{
                const m = await import('./modules/counts.js');
                const index = window.maGeo.indexes;
                const out = [];
                for (const areaId of Object.keys(index.assignments['{layer}'])) {{
                    const entry = index.assignments['{layer}'][areaId];
                    const dg = m.areaCounts(index.assignments, '{layer}', areaId,
                        {{population: 'degree_granting'}});
                    const all = m.areaCounts(index.assignments, '{layer}', areaId,
                        {{population: 'all'}});
                    out.push(
                        dg.campuses === entry.degree_granting_campus_count &&
                        dg.institutions === entry.degree_granting_institution_count &&
                        all.campuses === entry.campus_count &&
                        all.institutions === entry.institution_count
                    );
                }}
                return out.every(Boolean);
            }}"""
        )
        assert checked is True, layer


# --- 6.4 group headings ----------------------------------------------------

def test_group_headings_follow_the_population(driver, published):
    driver.open()
    driver.select_layer("county")
    driver.settle(800)
    headings = driver.page.evaluate(
        """() => [...document.querySelectorAll('.group-heading th')]
            .map(th => th.innerText.trim())"""
    )
    assert len(headings) == 14
    for heading in headings:
        name = heading.split("—")[0].strip()
        entry = published["assignments.json"]["county"][
            area_id(published, "county", name)
        ]
        assert str(entry["degree_granting_campus_count"]) in heading
        assert str(entry["degree_granting_institution_count"]) in heading


def test_the_omitted_group_count_follows_the_population(driver):
    driver.open()
    driver.select_layer("municipality")
    driver.settle(1000)
    status = driver.text("#table-status")
    assert "285" in status  # municipalities with no degree-granting campus
    assert driver.page.locator("#campus-table tbody").count() == 66

    driver.include_all_schools()
    driver.settle(600)
    widened = driver.text("#table-status")
    assert "268" in widened
    assert driver.page.locator("#campus-table tbody").count() == 83


# --- 6.5 and 6.6 nothing disagrees -----------------------------------------

@pytest.mark.parametrize("population", ["degree_granting", "all"])
def test_markers_rows_and_the_stated_count_agree(driver, published, population):
    suffix = "" if population == "degree_granting" else "&population=all"
    field = (
        "degree_granting_campus_count"
        if population == "degree_granting"
        else "campus_count"
    )

    driver.open(f"/index.html{'#population=all' if suffix else ''}")
    driver.settle(500)
    assert driver.rows().count() == driver.marker_count()

    driver.open(f"/index.html#layer=county{suffix}")
    driver.settle(800)
    assert driver.rows().count() == driver.marker_count()

    driver.open(f"/index.html#layer=county&area={SUFFOLK}{suffix}")
    driver.settle(800)
    expected = published["assignments.json"]["county"][SUFFOLK][field]
    assert driver.rows().count() == expected
    assert driver.marker_count() == expected
    assert str(expected) in driver.text("#table-status")


def test_the_shading_follows_the_population(driver, published):
    """Middlesex drops from the top class when the filter is applied."""
    mid = area_id(published, "county", "Middlesex")
    driver.open(f"/index.html#layer=county")
    driver.settle(800)
    default_fill = driver.page.evaluate(
        f"""() => {{
            let fill = null;
            window.maGeo.map.map.eachLayer((layer) => {{
                if (layer.feature && String(layer.feature.properties.area_id) === '{mid}') {{
                    fill = layer.options.fillColor;
                }}
            }});
            return fill;
        }}"""
    )
    driver.include_all_schools()
    driver.settle(800)
    widened_fill = driver.page.evaluate(
        f"""() => {{
            let fill = null;
            window.maGeo.map.map.eachLayer((layer) => {{
                if (layer.feature && String(layer.feature.properties.area_id) === '{mid}') {{
                    fill = layer.options.fillColor;
                }}
            }});
            return fill;
        }}"""
    )
    entry = published["assignments.json"]["county"][mid]
    assert entry["degree_granting_campus_count"] == 28 and entry["campus_count"] == 45
    assert default_fill != widened_fill


# --- 7.1 to 7.3 areas the filter empties -----------------------------------

def emptied_municipalities(published):
    return [
        a for a, e in published["assignments.json"]["municipality"].items()
        if e["campus_count"] and not e["degree_granting_campus_count"]
    ]


def test_seventeen_municipalities_are_emptied_by_the_filter(published):
    assert len(emptied_municipalities(published)) == 17


def test_an_emptied_area_says_so_rather_than_reporting_nothing(driver, published):
    target = emptied_municipalities(published)[0]
    name = published["area.json"]["municipality"][target]["name"]
    held = published["assignments.json"]["municipality"][target]["campus_count"]

    driver.open(f"/index.html#layer=municipality&area={target}")
    driver.settle(1000)
    status = driver.text("#table-status")
    note = driver.page.locator(".empty-note").inner_text()

    assert "no degree-granting campuses" in status
    assert "contains no campuses" not in status
    assert name in note
    assert "no degree-granting campuses" in note
    assert str(held) in note or ("one campus" in note and held == 1)
    # It points at the way to see what the area does hold.
    assert "control above" in note
    assert driver.page.locator("#error").is_hidden()

    # And the campuses are there when asked for.
    driver.include_all_schools()
    driver.settle(600)
    assert driver.rows().count() == held


def test_every_emptied_municipality_takes_that_message(driver, published):
    for target in emptied_municipalities(published):
        driver.open(f"/index.html#layer=municipality&area={target}")
        driver.settle(700)
        status = driver.text("#table-status")
        assert "no degree-granting campuses" in status, target


def test_a_genuinely_empty_area_is_unchanged(driver, published):
    empty = next(
        a for a, e in published["assignments.json"]["municipality"].items()
        if e["campus_count"] == 0
    )
    name = published["area.json"]["municipality"][empty]["name"]
    driver.open(f"/index.html#layer=municipality&area={empty}")
    driver.settle(900)
    status = driver.text("#table-status")
    assert f"{name} contains no campuses" in status
    assert "degree-granting" not in status
    assert driver.rows().count() == 0
    assert driver.page.locator("#error").is_hidden()
    assert driver.state()["areaId"] == empty
