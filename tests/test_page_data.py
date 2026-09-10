"""Loading and indexing the published data (tasks 4.1 - 4.3)."""

import json

import pytest

from ma_geo.paths import OUT_DIR


@pytest.fixture(scope="module")
def campus_count():
    return len(json.loads((OUT_DIR / "campus.geojson").read_text())["features"])


# --- 4.1 the eager load -----------------------------------------------------

def test_the_default_load_fetches_exactly_the_four_small_files(driver):
    driver.open()
    names = sorted(url.rsplit("/", 1)[-1] for url in driver.data_requests())
    assert names == ["area.json", "assignments.json", "campus.geojson", "provenance.json"]


def test_the_default_load_fetches_no_area_geometry(driver):
    driver.open()
    for layer in ("county", "municipality", "cbsa"):
        assert driver.requested(f"{layer}.geojson") == [], layer


def test_the_eager_files_are_fetched_in_parallel(blank):
    """All four are in flight together, not chained."""
    overlapped = blank.page.evaluate(
        """async () => {
            const m = await import('./modules/data.js');
            let inFlight = 0, peak = 0;
            const fetchImpl = async (url, options) => {
                inFlight += 1; peak = Math.max(peak, inFlight);
                const response = await fetch(url, options);
                inFlight -= 1;
                return response;
            };
            await m.loadEager({ fetchImpl });
            return peak;
        }"""
    )
    assert overlapped == 4, overlapped


# --- 4.2 lazy, memoized layer loading --------------------------------------

def test_a_layer_is_fetched_once_however_often_it_is_drawn(driver):
    driver.open()
    driver.select_layer("municipality")
    driver.select_layer("county")
    driver.select_layer("municipality")
    driver.settle(400)
    assert len(driver.requested("municipality.geojson")) == 1
    assert len(driver.requested("county.geojson")) == 1


def test_two_rapid_switches_to_one_layer_start_one_request(blank):
    requests = blank.page.evaluate(
        """async () => {
            const m = await import('./modules/data.js');
            const urls = [];
            const fetchImpl = (url, options) => { urls.push(url); return fetch(url, options); };
            const loader = m.createLayerLoader({ fetchImpl });
            await Promise.all([loader.load('county'), loader.load('county')]);
            await loader.load('county');
            return urls;
        }"""
    )
    assert requests == ["data/county.geojson"], requests


def test_a_failed_layer_load_is_not_cached_as_a_failure(blank):
    outcome = blank.page.evaluate(
        """async () => {
            const m = await import('./modules/data.js');
            let calls = 0;
            const fetchImpl = (url, options) => {
                calls += 1;
                if (calls === 1) return Promise.reject(new Error('offline'));
                return fetch(url, options);
            };
            const loader = m.createLayerLoader({ fetchImpl });
            let failed = false;
            try { await loader.load('cbsa'); } catch { failed = true; }
            const collection = await loader.load('cbsa');
            return { failed, calls, features: collection.features.length };
        }"""
    )
    assert outcome == {"failed": True, "calls": 2, "features": 10}


# --- 4.3 the indexes --------------------------------------------------------

def test_the_sorted_campus_list_holds_every_campus(driver, campus_count):
    """The index holds every campus; the population is applied on read."""
    driver.open()
    assert driver.page.evaluate("() => window.maGeo.indexes.sortedCampuses.length") == campus_count
    assert campus_count == 206
    assert driver.page.evaluate(
        "() => window.maGeo.indexes.campusesFor({population:'degree_granting'}).length"
    ) == 150
    assert driver.page.evaluate(
        "() => window.maGeo.indexes.campusesFor({population:'all'}).length"
    ) == 206


def test_the_sorted_list_is_alphabetical_by_institution(driver):
    driver.open()
    names = driver.page.evaluate(
        "() => window.maGeo.indexes.sortedCampuses.map(c => c.institution)"
    )
    assert names == sorted(names, key=lambda name: name.casefold())


def test_boston_resolves_to_its_thirty_eight_campuses(driver):
    """Membership is the published one, before any population is applied."""
    driver.open()
    boston = driver.page.evaluate(
        """() => {
            const index = window.maGeo.indexes;
            const entry = Object.entries(index.areaIndex.municipality)
                .find(([, area]) => area.name === 'Boston');
            const campuses = index.allCampusesIn('municipality', entry[0]);
            return {
                areaId: entry[0],
                campuses: campuses.length,
                institutions: new Set(campuses.map(c => c.institution_id)).size,
            };
        }"""
    )
    assert boston["campuses"] == 38
    assert boston["institutions"] == 35


def test_membership_is_read_from_the_assignment_not_recomputed(driver):
    """The index reproduces the published campus_ids exactly, in order."""
    driver.open()
    same = driver.page.evaluate(
        """() => {
            const index = window.maGeo.indexes;
            for (const layer of ['county', 'municipality', 'cbsa']) {
                for (const [areaId, entry] of Object.entries(index.assignments[layer])) {
                    const ids = index.allCampusesIn(layer, areaId).map(c => c.id);
                    if (JSON.stringify(ids) !== JSON.stringify(entry.campus_ids)) {
                        return { layer, areaId, ids, expected: entry.campus_ids };
                    }
                }
            }
            return true;
        }"""
    )
    assert same is True, same


def test_every_campus_resolves_all_three_geography_names_with_no_geometry(driver):
    driver.open()
    unresolved = driver.page.evaluate(
        """() => {
            const index = window.maGeo.indexes;
            const missing = [];
            for (const campus of index.campuses) {
                for (const layer of ['county', 'municipality']) {
                    if (!index.areaName(layer, campus.areaIds[layer])) {
                        missing.push([campus.id, layer]);
                    }
                }
                if (campus.areaIds.cbsa && !index.areaName('cbsa', campus.areaIds.cbsa)) {
                    missing.push([campus.id, 'cbsa']);
                }
            }
            return missing;
        }"""
    )
    assert unresolved == []
    for layer in ("county", "municipality", "cbsa"):
        assert driver.requested(f"{layer}.geojson") == []


def test_the_statewide_totals_come_from_the_published_data(driver):
    driver.open()
    totals = driver.page.evaluate("() => window.maGeo.indexes.totals")
    assert totals == {"campuses": 206, "institutions": 160}
