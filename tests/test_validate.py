"""Provenance and validation verifications (tasks 6.1 - 6.4)."""

import copy
import json

import pytest

from ma_geo import validate as V
from ma_geo.paths import OUT_DIR


@pytest.fixture
def published():
    if not (OUT_DIR / "campus.geojson").exists():
        pytest.skip("outputs not built; run `uv run ma-geo build`")
    return V.load_published()


# --- 6.1 provenance ----------------------------------------------------------

def test_provenance_names_every_source_with_vintage_and_fetch_date(published):
    provenance = published["provenance.json"]
    for key in ("colleges", "counties", "municipalities", "cbsa"):
        entry = provenance["sources"][key]
        assert entry["title"]
        assert entry["url"]
        assert entry["fetched"]
    # TIGER is vintage-stamped; the MassGIS services are not.
    assert provenance["sources"]["cbsa"]["vintage"] == "TIGER2025"


def test_provenance_counts_match_the_published_files(published):
    provenance = published["provenance.json"]
    for name, entry in provenance["published"].items():
        if "features" in entry:
            assert entry["features"] == len(published[name]["features"]), name
        assert entry["bytes"] == (OUT_DIR / name).stat().st_size, name


def test_provenance_records_the_statewide_institution_count(published):
    assert published["provenance.json"]["institution_count"] == 160


# --- 6.2 the failing validations --------------------------------------------

def test_a_campus_with_no_county_fails(published):
    features = copy.deepcopy(published["campus.geojson"]["features"])
    features[0]["properties"]["county_id"] = None
    with pytest.raises(V.ValidationError, match="have no county"):
        V.check_required_assignments(features)


def test_a_campus_with_no_municipality_fails(published):
    features = copy.deepcopy(published["campus.geojson"]["features"])
    features[3]["properties"]["municipality_id"] = None
    with pytest.raises(V.ValidationError, match="have no municipality"):
        V.check_required_assignments(features)


def test_a_duplicated_campus_id_fails(published):
    features = copy.deepcopy(published["campus.geojson"]["features"])
    features[1]["properties"]["campus_id"] = features[0]["properties"]["campus_id"]
    with pytest.raises(V.ValidationError, match="not unique"):
        V.check_identifiers(features)


def test_a_missing_institution_id_fails(published):
    features = copy.deepcopy(published["campus.geojson"]["features"])
    features[2]["properties"]["institution_id"] = None
    with pytest.raises(V.ValidationError, match="no institution_id"):
        V.check_identifiers(features)


def test_a_layer_whose_count_disagrees_with_its_source_fails(published):
    tampered = copy.deepcopy(published)
    tampered["municipality.geojson"]["features"].pop()
    with pytest.raises(V.ValidationError, match="350 features but its source"):
        V.check_feature_counts(tampered)


def test_swapped_coordinates_fail(published):
    features = copy.deepcopy(published["campus.geojson"]["features"])
    lon, lat = features[0]["geometry"]["coordinates"]
    features[0]["geometry"]["coordinates"] = [lat, lon]
    with pytest.raises(V.ValidationError, match="outside Massachusetts or swapped"):
        V.check_coordinate_order(features)


def test_a_stale_count_in_the_index_fails(published):
    index = copy.deepcopy(published["assignments.json"])
    area_id = next(iter(index["county"]))
    index["county"][area_id]["campus_count"] += 1
    with pytest.raises(V.ValidationError, match="does not match"):
        V.check_assignments_index(index, published["campus.geojson"]["features"])


def test_a_duplicated_institution_in_the_index_fails(published):
    index = copy.deepcopy(published["assignments.json"])
    area_id = next(
        a for a, e in index["county"].items() if e["institution_count"] > 0
    )
    entry = index["county"][area_id]
    entry["institution_ids"].append(entry["institution_ids"][0])
    entry["institution_count"] += 1
    with pytest.raises(V.ValidationError, match="duplicates"):
        V.check_assignments_index(index, published["campus.geojson"]["features"])


def test_an_index_missing_an_area_fails(published):
    index = copy.deepcopy(published["assignments.json"])
    index["municipality"].pop(next(iter(index["municipality"])))
    with pytest.raises(V.ValidationError, match="351 areas but the index has 350"):
        V.check_area_layers_present(published, index)


def test_a_disagreeing_outline_fails(published):
    """A county layer drawn separately would not share the outline."""
    tampered = copy.deepcopy(published)
    for feature in tampered["county.geojson"]["features"]:
        rings = feature["geometry"]["coordinates"]
        feature["geometry"]["coordinates"] = [
            [[[x + 0.01, y] for x, y in ring] for ring in part]
            for part in rings
        ] if feature["geometry"]["type"] == "MultiPolygon" else [
            [[x + 0.01, y] for x, y in ring] for ring in rings
        ]
    with pytest.raises(V.ValidationError, match="differs from the municipality"):
        V.check_shared_outline(tampered)


def test_a_failing_run_leaves_the_published_outputs_untouched(tmp_path):
    """The budget is checked before anything is written."""
    from ma_geo import build as B

    before = {
        name: (OUT_DIR / name).read_bytes()
        for name in ("campus.geojson", "county.geojson", "municipality.geojson",
                     "cbsa.geojson", "assignments.json")
        if (OUT_DIR / name).exists()
    }
    if not before:
        pytest.skip("outputs not built")

    # A tolerance this coarse fails during the simplification guard, which
    # runs before the render and write phase.
    with pytest.raises(B.BuildError):
        B.run_build(tolerance=0.02)

    after = {name: (OUT_DIR / name).read_bytes() for name in before}
    assert after == before, "a failing build overwrote the published outputs"


# --- 6.3 the informational reports ------------------------------------------

def test_informational_report_counts_the_legitimate_gaps(published):
    index = published["assignments.json"]
    report = V.informational_report(published, index)

    assert report["campuses_without_cbsa"] == 0
    # Most Massachusetts towns have no college.
    assert report["empty_areas"]["municipality"] > 0
    assert report["empty_areas"]["county"] == 0
    assert report["statewide_institutions"] == 160
    assert report["municipality_discrepancies"] == 0


def test_informational_report_shows_the_non_additivity(published):
    report = V.informational_report(published, published["assignments.json"])
    for layer in V.LAYERS:
        assert report["campus_count_sums"][layer] == 206
        assert report["institution_count_sums"][layer] > 160


def test_the_run_succeeds_despite_legitimate_gaps():
    """Empty areas and absent CBSAs must not fail the run."""
    assert V.run_validate() == 0
