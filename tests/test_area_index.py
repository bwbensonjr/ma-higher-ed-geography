"""The published area name index (tasks 1.6 - 1.8)."""

import copy
import json

import pytest

from ma_geo import contract as C
from ma_geo import validate as V
from ma_geo.paths import OUT_DIR

LAYER_COUNTS = {"county": 14, "municipality": 351, "cbsa": 10}


@pytest.fixture
def published():
    if not (OUT_DIR / "area.json").exists():
        pytest.skip("outputs not built; run `uv run ma-geo build`")
    return V.load_published()


# --- 1.6 the index is complete, correct, and small --------------------------

def test_every_area_of_every_layer_is_named(published):
    index = published["area.json"]
    for layer, expected in LAYER_COUNTS.items():
        assert len(index[layer]) == expected, layer
        assert set(index[layer]) == {
            str(f["properties"]["area_id"])
            for f in published[f"{layer}.geojson"]["features"]
        }


def test_names_are_identical_to_the_geometry_files(published):
    for layer in LAYER_COUNTS:
        geometry_names = {
            str(f["properties"]["area_id"]): f["properties"]["name"]
            for f in published[f"{layer}.geojson"]["features"]
        }
        index_names = {a: e["name"] for a, e in published["area.json"][layer].items()}
        assert index_names == geometry_names, layer


def test_a_municipality_carries_its_county(published):
    index = published["area.json"]["municipality"]
    geometry = {
        str(f["properties"]["area_id"]): f["properties"]["county_id"]
        for f in published["municipality.geojson"]["features"]
    }
    for area_id, entry in index.items():
        assert entry["county_id"] == geometry[area_id]


def test_areas_with_no_campuses_are_named_too(published):
    """268 municipalities hold no campus and still need a display name."""
    assignments = published["assignments.json"]["municipality"]
    empty = [a for a, e in assignments.items() if e["campus_count"] == 0]
    assert len(empty) == 268
    for area_id in empty:
        assert published["area.json"]["municipality"][area_id]["name"]


def test_the_index_is_small_enough_to_fetch_eagerly(published):
    size = (OUT_DIR / "area.json").stat().st_size
    smallest_layer = min(
        (OUT_DIR / f"{layer}.geojson").stat().st_size for layer in LAYER_COUNTS
    )
    assert size < smallest_layer / 10, (size, smallest_layer)


def test_the_eager_payload_stays_modest(published):
    """What a first view costs, in the repository's own data."""
    eager = sum(
        (OUT_DIR / name).stat().st_size
        for name in ("campus.geojson", "assignments.json", "area.json", "provenance.json")
    )
    assert eager < 350_000, eager


def test_the_index_answers_what_the_mailing_city_cannot(published):
    """Boston College's main campus is addressed Chestnut Hill, sited in Newton."""
    campus = next(
        f["properties"]
        for f in published["campus.geojson"]["features"]
        if f["properties"]["campus_id"] == "boston-college--main-campus"
    )
    assert campus["city"] == "Chestnut Hill"
    index = published["area.json"]
    assert index["municipality"][str(campus["municipality_id"])]["name"] == "Newton"
    assert index["county"][str(campus["county_id"])]["name"] == "Middlesex"


def test_the_mailing_city_disagrees_for_eighteen_campuses(published):
    """Why the index exists rather than reusing the campus `city` attribute."""
    names = {
        area_id: entry["name"]
        for area_id, entry in published["area.json"]["municipality"].items()
    }
    disagreeing = [
        f["properties"]["campus_id"]
        for f in published["campus.geojson"]["features"]
        if f["properties"]["city"].strip().casefold()
        != names[str(f["properties"]["municipality_id"])].strip().casefold()
    ]
    assert len(disagreeing) == 18


# --- 1.7 provenance and the untouched outputs -------------------------------

def test_provenance_records_the_index(published):
    entry = published["provenance.json"]["published"]["area.json"]
    assert entry["bytes"] == (OUT_DIR / "area.json").stat().st_size


def test_the_index_is_valid_json_the_page_can_fetch():
    C.check_page_can_fetch_what_it_reads()
    json.loads((OUT_DIR / "area.json").read_text())


# --- 1.8 the contract check covers the index --------------------------------

def test_the_committed_index_satisfies_the_contract(published):
    C.check_area_index(published)


def test_a_missing_layer_fails(published):
    broken = copy.deepcopy(published)
    broken["area.json"].pop("cbsa")
    with pytest.raises(C.ContractError, match="cbsa"):
        C.check_area_index(broken)


def test_a_missing_name_fails_and_names_the_field_and_file(published):
    broken = copy.deepcopy(published)
    layer = broken["area.json"]["county"]
    layer[next(iter(layer))].pop("name")
    with pytest.raises(C.ContractError) as error:
        C.check_area_index(broken)
    assert "name" in str(error.value)
    assert "area.json" in str(error.value)


def test_a_municipality_without_its_county_id_fails(published):
    broken = copy.deepcopy(published)
    layer = broken["area.json"]["municipality"]
    layer[next(iter(layer))].pop("county_id")
    with pytest.raises(C.ContractError, match="county_id"):
        C.check_area_index(broken)


def test_an_area_absent_from_the_index_fails(published):
    broken = copy.deepcopy(published)
    layer = broken["area.json"]["municipality"]
    layer.pop(next(iter(layer)))
    with pytest.raises(C.ContractError, match="absent from the index"):
        C.check_area_index(broken)


def test_an_index_entry_naming_no_published_area_fails(published):
    broken = copy.deepcopy(published)
    broken["area.json"]["county"]["25999"] = {"name": "Nowhere"}
    with pytest.raises(C.ContractError, match="names no area"):
        C.check_area_index(broken)


def test_a_name_disagreeing_with_the_geometry_file_fails(published):
    broken = copy.deepcopy(published)
    layer = broken["area.json"]["county"]
    area_id = next(iter(layer))
    layer[area_id]["name"] = "Renamed"
    with pytest.raises(C.ContractError, match="but county.geojson names it"):
        C.check_area_index(broken)


def test_provenance_missing_the_index_fails(published):
    broken = copy.deepcopy(published)
    broken["provenance.json"]["published"].pop("area.json")
    with pytest.raises(C.ContractError, match="area.json"):
        C.check_provenance_fields(broken)
