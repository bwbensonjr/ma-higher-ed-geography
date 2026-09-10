"""The contract the page reads the published outputs through (tasks 1.1 - 1.4)."""

import copy
import json

import pytest

from ma_geo import contract as C
from ma_geo import validate as V
from ma_geo.paths import OUT_DIR


@pytest.fixture
def published():
    if not (OUT_DIR / "campus.geojson").exists():
        pytest.skip("outputs not built; run `uv run ma-geo build`")
    return V.load_published()


# --- 1.1 the fields the page reads are present ------------------------------

def test_the_committed_outputs_satisfy_the_contract(published):
    C.check_contract(published)


def test_a_renamed_campus_field_fails_and_names_the_field_and_file(published):
    broken = copy.deepcopy(published)
    properties = broken["campus.geojson"]["features"][0]["properties"]
    properties["college"] = properties.pop("institution")
    with pytest.raises(C.ContractError) as error:
        C.check_campus_fields(broken)
    assert "institution" in str(error.value)
    assert "campus.geojson" in str(error.value)


@pytest.mark.parametrize("field", C.CAMPUS_REQUIRED)
def test_every_required_campus_field_is_required(published, field):
    broken = copy.deepcopy(published)
    broken["campus.geojson"]["features"][0]["properties"].pop(field)
    with pytest.raises(C.ContractError, match=field):
        C.check_campus_fields(broken)


def test_an_area_missing_its_display_name_fails(published):
    broken = copy.deepcopy(published)
    broken["county.geojson"]["features"][2]["properties"].pop("name")
    with pytest.raises(C.ContractError) as error:
        C.check_area_fields(broken)
    assert "name" in str(error.value)
    assert "county.geojson" in str(error.value)


def test_a_municipality_missing_its_county_id_fails(published):
    broken = copy.deepcopy(published)
    broken["municipality.geojson"]["features"][0]["properties"].pop("county_id")
    with pytest.raises(C.ContractError, match="county_id"):
        C.check_area_fields(broken)


def test_an_area_published_in_the_wrong_layer_file_fails(published):
    broken = copy.deepcopy(published)
    broken["county.geojson"]["features"][0]["properties"]["layer"] = "municipality"
    with pytest.raises(C.ContractError, match="declares layer"):
        C.check_area_fields(broken)


@pytest.mark.parametrize(
    "field", C.ASSIGNMENT_LIST_FIELDS + C.ASSIGNMENT_COUNT_FIELDS
)
def test_every_assignment_field_is_required(published, field):
    broken = copy.deepcopy(published)
    layer = broken["assignments.json"]["county"]
    layer[next(iter(layer))].pop(field)
    with pytest.raises(C.ContractError, match=field):
        C.check_assignment_fields(broken)


def test_a_missing_assignment_layer_fails(published):
    broken = copy.deepcopy(published)
    broken["assignments.json"].pop("cbsa")
    with pytest.raises(C.ContractError, match="cbsa"):
        C.check_assignment_fields(broken)


def test_a_count_published_as_text_fails(published):
    broken = copy.deepcopy(published)
    layer = broken["assignments.json"]["county"]
    area_id = next(iter(layer))
    layer[area_id]["campus_count"] = str(layer[area_id]["campus_count"])
    with pytest.raises(C.ContractError, match="not a whole number"):
        C.check_assignment_fields(broken)


def test_every_area_of_every_layer_is_present_with_both_counts(published):
    index = published["assignments.json"]
    for layer in C.LAYERS:
        areas = {
            str(f["properties"]["area_id"])
            for f in published[f"{layer}.geojson"]["features"]
        }
        assert set(index[layer]) == areas
        for entry in index[layer].values():
            assert isinstance(entry["campus_count"], int)
            assert isinstance(entry["institution_count"], int)


# --- 1.2 referential integrity ----------------------------------------------

def test_a_campus_referencing_an_unknown_county_fails(published):
    broken = copy.deepcopy(published)
    broken["campus.geojson"]["features"][0]["properties"]["county_id"] = "25999"
    with pytest.raises(C.ContractError) as error:
        C.check_references(broken)
    message = str(error.value)
    assert "25999" in message
    assert "campus.geojson" in message
    assert "county.geojson" in message


def test_an_assignment_listing_an_unknown_campus_fails(published):
    broken = copy.deepcopy(published)
    layer = broken["assignments.json"]["county"]
    area_id = next(iter(layer))
    layer[area_id]["campus_ids"] = [*layer[area_id]["campus_ids"], "no-such-campus"]
    with pytest.raises(C.ContractError) as error:
        C.check_references(broken)
    message = str(error.value)
    assert "no-such-campus" in message
    assert "assignments.json" in message
    assert "campus.geojson" in message


def test_an_assignment_listing_an_unknown_institution_fails(published):
    broken = copy.deepcopy(published)
    layer = broken["assignments.json"]["municipality"]
    area_id = next(iter(layer))
    layer[area_id]["institution_ids"] = [
        *layer[area_id]["institution_ids"],
        "no-such-institution",
    ]
    with pytest.raises(C.ContractError) as error:
        C.check_references(broken)
    assert "no-such-institution" in str(error.value)


def test_an_assignment_key_that_is_not_an_area_fails(published):
    broken = copy.deepcopy(published)
    broken["assignments.json"]["county"]["99999"] = {
        "campus_ids": [],
        "institution_ids": [],
        "campus_count": 0,
        "institution_count": 0,
    }
    with pytest.raises(C.ContractError, match="99999"):
        C.check_references(broken)


def test_every_published_reference_resolves(published):
    C.check_references(published)


# --- 1.3 optional attributes may be empty -----------------------------------

def test_a_campus_with_no_campus_name_no_telephone_and_no_cbsa_passes(published):
    relaxed = copy.deepcopy(published)
    properties = relaxed["campus.geojson"]["features"][0]["properties"]
    properties["campus"] = None
    properties["telephone"] = ""
    properties["cbsa_id"] = None
    C.check_campus_fields(relaxed)
    C.check_references(relaxed)


def test_a_campus_missing_its_institution_fails(published):
    broken = copy.deepcopy(published)
    broken["campus.geojson"]["features"][0]["properties"]["institution"] = ""
    with pytest.raises(C.ContractError, match="institution"):
        C.check_campus_fields(broken)


def test_an_optional_field_dropped_altogether_still_fails(published):
    """The value may be empty, but the key must be published."""
    broken = copy.deepcopy(published)
    broken["campus.geojson"]["features"][0]["properties"].pop("campus")
    with pytest.raises(C.ContractError, match="campus"):
        C.check_campus_fields(broken)


def test_the_data_really_does_exercise_the_optional_case(published):
    """114 campuses publish no campus name, so this is not a hypothetical."""
    empty = [
        f
        for f in published["campus.geojson"]["features"]
        if not f["properties"]["campus"]
    ]
    assert len(empty) == 114


# --- 1.4 the provenance figures the page displays ---------------------------

@pytest.mark.parametrize("field", C.PROVENANCE_REQUIRED)
def test_a_missing_provenance_figure_fails(published, field):
    broken = copy.deepcopy(published)
    broken["provenance.json"].pop(field)
    with pytest.raises(C.ContractError, match=field):
        C.check_provenance_fields(broken)


def test_a_source_missing_its_title_fails(published):
    broken = copy.deepcopy(published)
    broken["provenance.json"]["sources"]["colleges"].pop("title")
    with pytest.raises(C.ContractError, match="title"):
        C.check_provenance_fields(broken)


def test_a_missing_published_feature_count_fails(published):
    broken = copy.deepcopy(published)
    broken["provenance.json"]["published"].pop("campus.geojson")
    with pytest.raises(C.ContractError, match="campus.geojson"):
        C.check_provenance_fields(broken)


def test_the_eager_files_are_present_and_valid_json():
    C.check_page_can_fetch_what_it_reads()
    for name in ("campus.geojson", "assignments.json", "provenance.json"):
        json.loads((OUT_DIR / name).read_text())
