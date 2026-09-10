"""Award-tier classification and both populations' counts (tasks 1.1 - 3.4)."""

import copy
import json

import pytest

from ma_geo import build as B
from ma_geo import contract as C
from ma_geo import validate as V
from ma_geo.paths import OUT_DIR


@pytest.fixture
def published():
    if not (OUT_DIR / "campus.geojson").exists():
        pytest.skip("outputs not built; run `uv run ma-geo build`")
    return V.load_published()


@pytest.fixture
def campuses(published):
    return [f["properties"] for f in published["campus.geojson"]["features"]]


# --- 1.1 the tier normalization --------------------------------------------

@pytest.mark.parametrize(
    ("nces_type", "expected"),
    [
        ("< 2-year, Private for-profit", "sub_associate"),
        ("< 2-year, Public", "sub_associate"),
        ("2-year, Public", "two_year"),
        ("2-year, Private not-for-profit", "two_year"),
        ("4-year, Private not-for-profit", "four_year"),
        ("4-year, Public", "four_year"),
        # The source qualifies three records this way; they are four-year.
        ("4-year, primarily associate's, Private not-for-profit", "four_year"),
        ("4-year, primarily associate's, Public", "four_year"),
    ],
)
def test_the_tier_is_normalized_from_the_source(nces_type, expected):
    assert B.award_tier(nces_type) == expected


def test_every_published_campus_classifies(campuses):
    assert len(campuses) == 206
    tiers = [B.award_tier(p["nces_type"]) for p in campuses]
    assert all(tiers)
    counts = {tier: tiers.count(tier) for tier in set(tiers)}
    assert counts == {"sub_associate": 56, "two_year": 38, "four_year": 112}


def test_the_degree_granting_rule(campuses):
    assert B.is_degree_granting("two_year")
    assert B.is_degree_granting("four_year")
    assert not B.is_degree_granting("sub_associate")


# --- 1.2 an unrecognized tier fails ----------------------------------------

@pytest.mark.parametrize("value", [None, "", "   ", "unknown", "5-year, Public", "Public"])
def test_an_unclassifiable_tier_raises(value):
    with pytest.raises(B.BuildError, match="cannot classify award tier"):
        B.award_tier(value)


def test_the_failure_names_the_campus(monkeypatch, campuses):
    """The build reports which campus it could not classify."""
    with pytest.raises(B.BuildError) as error:
        B.award_tier("no such tier")
    assert "no such tier" in str(error.value)


# --- 1.3 the published fields ----------------------------------------------

def test_every_campus_publishes_its_tier_and_flag(campuses):
    for p in campuses:
        assert p["award_tier"] in ("sub_associate", "two_year", "four_year"), p["campus_id"]
        assert isinstance(p["degree_granting"], bool), p["campus_id"]
        assert p["degree_granting"] == (p["award_tier"] != "sub_associate")


def test_the_published_populations(campuses):
    granting = [p for p in campuses if p["degree_granting"]]
    assert len(granting) == 150
    assert len({p["institution_id"] for p in granting}) == 116
    rest = [p for p in campuses if not p["degree_granting"]]
    assert len(rest) == 56
    assert len({p["institution_id"] for p in rest}) == 44


# --- 1.4 the classification pinned against known institutions --------------

COSMETOLOGY_KEYWORDS = (
    "beauty", "nail", "hair", "cosmetolog", "barber", "esthet", "electrolog", "spa",
)


def test_the_cosmetology_family_is_sub_associate(campuses):
    family = [
        p for p in campuses
        if any(k in p["institution"].lower() for k in COSMETOLOGY_KEYWORDS)
    ]
    assert len(family) == 22
    for p in family:
        assert p["award_tier"] == "sub_associate", p["institution"]
        assert p["degree_granting"] is False


@pytest.mark.parametrize(
    "institution",
    [
        "Harvard University",
        "Williams College",
        "Bunker Hill Community College",
        "University of Massachusetts Amherst",
    ],
)
def test_the_obvious_colleges_are_degree_granting(campuses, institution):
    matches = [p for p in campuses if p["institution"] == institution]
    assert matches, institution
    assert all(p["degree_granting"] for p in matches)


@pytest.mark.parametrize(
    "fragment",
    [
        # Filed under a vocational or adult-education category, but 2- or
        # 4-year by tier, so the tier keeps them.
        "Urban College of Boston",
        "Holyoke Microcollege",
        "Springfield College-Regional",
        "FINE Mortuary College",
        # Two-year institutions awarding only certificates.
        "North Bennet Street School",
        "National Aviation Academy",
        "Brockton Hospital School of Nursing",
    ],
)
def test_the_judgment_calls_are_kept(campuses, fragment):
    matches = [p for p in campuses if fragment.lower() in p["institution"].lower()]
    assert matches, fragment
    for p in matches:
        assert p["degree_granting"] is True, (p["institution"], p["nces_type"])


def test_the_tier_governs_not_the_source_category(campuses):
    vocational_categories = {
        "Private Vocational School", "Private Occupational Program", "Adult Education",
    }
    kept = [
        p for p in campuses
        if p["category"] in vocational_categories and p["degree_granting"]
    ]
    assert len(kept) == 4
    dropped_elsewhere = [
        p for p in campuses
        if p["category"] not in vocational_categories and not p["degree_granting"]
    ]
    assert len(dropped_elsewhere) == 13


# --- 1.5 nothing is filtered out of the published data ---------------------

def test_no_campus_is_dropped_for_being_sub_associate(published, campuses):
    assert len(published["campus.geojson"]["features"]) == 206
    index = published["assignments.json"]
    assert sum(e["campus_count"] for e in index["municipality"].values()) == 206
    assert sum(e["campus_count"] for e in index["county"].values()) == 206


# --- 2.1 to 2.3 both populations counted per area --------------------------

LAYER_SIZES = {"county": 14, "municipality": 351, "cbsa": 10}


def test_every_area_carries_both_populations(published):
    index = published["assignments.json"]
    for layer, size in LAYER_SIZES.items():
        assert len(index[layer]) == size
        for area_id, entry in index[layer].items():
            for field in (
                "campus_count", "institution_count",
                "degree_granting_campus_count", "degree_granting_institution_count",
            ):
                assert field in entry, (layer, area_id, field)
                assert isinstance(entry[field], int)


def test_the_counts_agree_with_the_campus_flags(published, campuses):
    granting = {p["campus_id"] for p in campuses if p["degree_granting"]}
    institution_of = {p["campus_id"]: p["institution_id"] for p in campuses}
    index = published["assignments.json"]
    for layer in LAYER_SIZES:
        for area_id, entry in index[layer].items():
            members = [c for c in entry["campus_ids"] if c in granting]
            assert entry["degree_granting_campus_count"] == len(members), (layer, area_id)
            assert entry["degree_granting_institution_count"] == len(
                {institution_of[c] for c in members}
            ), (layer, area_id)


def counts_for(published, layer, name):
    areas = published["area.json"][layer]
    area_id = next(a for a, entry in areas.items() if entry["name"] == name)
    return published["assignments.json"][layer][area_id]


@pytest.mark.parametrize(
    ("layer", "name", "expected"),
    [
        ("county", "Middlesex", (45, 38, 28, 22)),
        ("county", "Worcester", (23, 23, 13, 13)),
        # Boston holds just one sub-associate campus.
        ("municipality", "Boston", (38, 35, 37, 34)),
    ],
)
def test_known_areas_report_both_populations(published, layer, name, expected):
    entry = counts_for(published, layer, name)
    actual = (
        entry["campus_count"], entry["institution_count"],
        entry["degree_granting_campus_count"],
        entry["degree_granting_institution_count"],
    )
    assert actual == expected


def test_an_area_with_no_degree_granting_campus_reports_zero(published):
    index = published["assignments.json"]["municipality"]
    emptied = [
        e for e in index.values()
        if e["campus_count"] and not e["degree_granting_campus_count"]
    ]
    assert len(emptied) == 17
    for entry in emptied:
        assert entry["degree_granting_campus_count"] == 0
        assert entry["degree_granting_institution_count"] == 0


# --- 2.4 the statewide figure ----------------------------------------------

def test_the_statewide_degree_granting_figure_is_published(published):
    provenance = published["provenance.json"]
    assert provenance["institution_count"] == 160
    assert provenance["degree_granting_institution_count"] == 116


def test_degree_granting_institution_counts_are_not_additive(published):
    """Summing them exceeds 116, so no consumer may present that sum."""
    index = published["assignments.json"]
    for layer in LAYER_SIZES:
        summed = sum(
            e["degree_granting_institution_count"] for e in index[layer].values()
        )
        assert summed > 116, (layer, summed)
    # Campus counts do sum.
    assert sum(
        e["degree_granting_campus_count"] for e in index["county"].values()
    ) == 150


# --- 2.5 and 2.6 the untouched outputs and the payload ---------------------

def test_the_area_layers_and_name_index_are_unchanged_in_shape(published):
    for layer, size in LAYER_SIZES.items():
        assert len(published[f"{layer}.geojson"]["features"]) == size
        first = published[f"{layer}.geojson"]["features"][0]["properties"]
        assert set(first) <= {"area_id", "layer", "name", "county_id",
                              "municipality_type", "area_kind"}
    assert len(published["area.json"]["municipality"]) == 351


def test_the_payload_stays_within_budget(published):
    sizes = {
        name: (OUT_DIR / name).stat().st_size
        for name in ("campus.geojson", "assignments.json", "area.json", "provenance.json")
    }
    assert sizes["assignments.json"] < 140_000
    assert sum(sizes.values()) < 350_000
    provenance = published["provenance.json"]["published"]
    for name, size in sizes.items():
        if name == "provenance.json":
            continue  # the record cannot carry its own size
        assert provenance[name]["bytes"] == size, name


# --- 3.1 to 3.4 the contract check -----------------------------------------

def test_the_committed_outputs_satisfy_the_widened_contract(published):
    C.check_contract(published)


@pytest.mark.parametrize("field", ["award_tier", "degree_granting"])
def test_a_campus_missing_its_classification_fails(published, field):
    broken = copy.deepcopy(published)
    broken["campus.geojson"]["features"][0]["properties"].pop(field)
    with pytest.raises(C.ContractError) as error:
        C.check_campus_fields(broken)
    assert field in str(error.value)
    assert "campus.geojson" in str(error.value)


def test_an_unknown_award_tier_fails(published):
    broken = copy.deepcopy(published)
    broken["campus.geojson"]["features"][0]["properties"]["award_tier"] = "five_year"
    with pytest.raises(C.ContractError, match="award_tier"):
        C.check_campus_fields(broken)


@pytest.mark.parametrize(
    "field", ["degree_granting_campus_count", "degree_granting_institution_count"]
)
def test_a_missing_population_count_fails(published, field):
    broken = copy.deepcopy(published)
    layer = broken["assignments.json"]["county"]
    layer[next(iter(layer))].pop(field)
    with pytest.raises(C.ContractError) as error:
        C.check_assignment_fields(broken)
    assert field in str(error.value)
    assert "assignments.json" in str(error.value)


def test_a_population_count_published_as_text_fails(published):
    broken = copy.deepcopy(published)
    layer = broken["assignments.json"]["county"]
    area_id = next(iter(layer))
    layer[area_id]["degree_granting_campus_count"] = "3"
    with pytest.raises(C.ContractError, match="not a whole number"):
        C.check_assignment_fields(broken)


def test_a_count_disagreeing_with_the_flags_fails(published):
    broken = copy.deepcopy(published)
    layer = broken["assignments.json"]["county"]
    area_id = next(a for a, e in layer.items() if e["degree_granting_campus_count"] > 1)
    layer[area_id]["degree_granting_campus_count"] += 1
    with pytest.raises(C.ContractError) as error:
        C.check_population_counts(broken)
    message = str(error.value)
    assert area_id in message
    assert "flags" in message


def test_the_statewide_figure_is_required(published):
    broken = copy.deepcopy(published)
    broken["provenance.json"].pop("degree_granting_institution_count")
    with pytest.raises(C.ContractError, match="degree_granting_institution_count"):
        C.check_provenance_fields(broken)
