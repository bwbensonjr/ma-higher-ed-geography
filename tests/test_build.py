"""Build verifications for the area layers, campus layer, assignment,
and simplification (tasks 3.1 - 3.6, 4.3 - 4.8, 5.1 - 5.3)."""

import json
import warnings

import geopandas as gpd
import pytest
from shapely.geometry import Point, Polygon

from ma_geo import build as B
from ma_geo import sources
from ma_geo.paths import OUT_DIR
from ma_geo.simplify import SIZE_BUDGET_BYTES, simplify_layer

warnings.filterwarnings("ignore")

pytestmark = pytest.mark.filterwarnings("ignore")


def _published(name: str) -> dict:
    path = OUT_DIR / name
    if not path.exists():
        pytest.skip(f"{name} not built; run `uv run ma-geo build`")
    return json.loads(path.read_text())


def _props(name: str) -> list[dict]:
    return [f["properties"] for f in _published(name)["features"]]


@pytest.fixture(scope="module")
def municipality():
    return B.build_municipality_layer(B._read_raw(sources.MUNICIPALITIES))


@pytest.fixture(scope="module")
def massgis_counties():
    return B.build_county_layer(B._read_raw(sources.COUNTIES))


@pytest.fixture(scope="module")
def tiger():
    return B._read_tiger()


@pytest.fixture(scope="module")
def layers(municipality, tiger):
    derived, _ = B._derive_layers(municipality, tiger)
    return derived


@pytest.fixture(scope="module")
def cbsa_report(municipality, tiger):
    _, report = B._derive_layers(municipality, tiger)
    return report


@pytest.fixture(scope="module")
def campus_frame():
    return B.build_campus_layer(B._read_raw(sources.COLLEGES))


# --- 3.1 counties ------------------------------------------------------------

def test_county_layer_has_14_named_unique_areas():
    rows = _props("county.geojson")
    assert len(rows) == 14
    assert all(r["layer"] == "county" for r in rows)
    names = [r["name"] for r in rows]
    assert all(names) and len(set(names)) == 14
    # area_id is the 5-digit state-county FIPS.
    assert all(len(r["area_id"]) == 5 and r["area_id"].startswith("25") for r in rows)
    by_name = {r["name"]: r["area_id"] for r in rows}
    assert by_name["Suffolk"] == "25025"


# --- 3.2 municipalities ------------------------------------------------------

def test_municipality_layer_has_351_areas_linked_to_counties():
    rows = _props("municipality.geojson")
    assert len(rows) == 351
    assert all(r["layer"] == "municipality" for r in rows)
    names = [r["name"] for r in rows]
    assert all(names) and len(set(names)) == 351

    county_ids = {r["area_id"] for r in _props("county.geojson")}
    assert {r["county_id"] for r in rows} <= county_ids

    assert all(
        r["municipality_type"] in
        {"city", "town", "town with city form of government"}
        for r in rows
    )
    by_name = {r["name"]: r for r in rows}
    assert by_name["Boston"]["county_id"] == "25025"
    assert by_name["Manchester-by-the-Sea"]["municipality_type"] == "town"


# --- 3.3 the clip mask -------------------------------------------------------

def test_counties_are_dissolved_from_the_municipalities(layers):
    """The county layer is the towns, combined -- not a separate rendering."""
    county = layers["county"]
    assert len(county) == 14
    municipal_union = layers["municipality"].geometry.union_all()
    county_union = county.geometry.union_all()
    # Same arcs, so the two outlines are identical to floating-point zero.
    assert county_union.symmetric_difference(municipal_union).area < 1e-12


# --- 3.3 the cross-check against the MassGIS county layer -------------------

def test_dissolved_counties_agree_with_the_massgis_layer(layers, massgis_counties):
    result = B.cross_check_counties(layers["county"], massgis_counties)
    # The layers render the coastline differently; 0.22% is that difference.
    assert result["worst_relative_difference"] < 0.01


def test_a_corrupted_county_id_fails_the_cross_check(municipality, massgis_counties):
    """Moving a town into the wrong county must not reshape a county quietly."""
    tampered = municipality.copy()
    boston = tampered["name"] == "Boston"
    tampered.loc[boston, "county_id"] = "25003"  # Berkshire, across the state
    tampered.loc[boston, "county_name"] = "BERKSHIRE"
    dissolved = B.dissolve_counties(tampered)
    with pytest.raises(B.BuildError, match="differs from its MassGIS polygon"):
        B.cross_check_counties(dissolved, massgis_counties)


# --- 3.4 CBSA selection and clipping -----------------------------------------

def test_all_three_published_layers_share_one_outer_boundary():
    """The point of deriving the layers: the coast cannot drift between them.

    The published files agree to within the coordinate grid they are written
    on, not to the bit -- rounding to six decimals can move a node a tenth of
    a metre. The ceiling below is one part in ten million of the state's area;
    the theoretical worst case for a boundary this long is four orders of
    magnitude larger, and nothing at this scale is renderable.
    """
    from ma_geo.validate import OUTLINE_AGREEMENT

    outlines = {}
    for name in ("county", "municipality", "cbsa"):
        outlines[name] = gpd.read_file(
            OUT_DIR / f"{name}.geojson"
        ).geometry.union_all()
    reference = outlines["municipality"]
    for name, outline in outlines.items():
        relative = outline.symmetric_difference(reference).area / reference.area
        assert relative < OUTLINE_AGREEMENT, f"{name} differs by {relative:.3e}"


def test_the_derivation_itself_is_exact_before_publication(layers):
    """Before rounding, the layers are the same geometry, not near-identical."""
    reference = layers["municipality"].geometry.union_all()
    for name, frame in layers.items():
        difference = frame.geometry.union_all().symmetric_difference(reference).area
        assert difference < 1e-12, f"{name} differs by {difference:.3e}"


def test_every_county_belongs_to_exactly_one_statistical_area(cbsa_report, layers):
    membership = cbsa_report["membership"]
    assigned = [c for counties in membership.values() for c in counties]
    assert len(assigned) == 14
    assert len(set(assigned)) == 14
    assert set(assigned) == set(layers["county"]["area_id"])


def test_boston_cbsa_keeps_its_full_name_but_loses_new_hampshire(cbsa_report):
    frame = gpd.read_file(OUT_DIR / "cbsa.geojson")
    boston = frame[frame["name"] == "Boston-Cambridge-Newton, MA-NH Metro Area"]
    assert len(boston) == 1, "the multi-state name must be preserved verbatim"
    # The MA/NH border runs at about 42.7N; the NH portion is absent.
    assert boston.geometry.iloc[0].bounds[3] < 42.9
    # It is the union of its five Massachusetts counties.
    counties = cbsa_report["membership"][boston["area_id"].iloc[0]]
    assert set(counties) == {"25009", "25017", "25021", "25023", "25025"}


def test_only_massachusetts_areas_are_published():
    names = [r["name"] for r in _props("cbsa.geojson")]
    assert len(names) == 10
    # Out-of-state areas that only graze the state line are excluded.
    for absent in ("Manchester-Nashua", "Keene", "Brattleboro", "Bennington",
                   "Hudson", "Torrington", "Hartford", "Albany", "Putnam"):
        assert not any(absent in n for n in names), f"{absent} should be dropped"
    assert any("Nantucket" in n for n in names)


# --- 3.5 sliver reporting ----------------------------------------------------

def test_border_grazing_areas_are_excluded_without_an_area_threshold():
    """No threshold needed: they contain no Massachusetts county."""
    excluded = _published("provenance.json")["derivation"]["cbsa_excluded"]
    assert len(excluded) == 9
    names = " | ".join(e["name"] for e in excluded)
    for expected in ("Manchester-Nashua", "Keene", "Brattleboro", "Bennington",
                     "Hudson", "Torrington", "Hartford", "Albany", "Putnam"):
        assert expected in names, expected


def test_no_campus_was_lost_to_a_dropped_fragment_or_area():
    """A campus inside a dropped piece would have ended up with no CBSA."""
    rows = _props("campus.geojson")
    without = [r["campus_id"] for r in rows if not r.get("cbsa_id")]
    assert without == []


# --- 3.6 CBSA identifiers ----------------------------------------------------

def test_cbsa_area_ids_are_distinct_five_digit_codes():
    rows = _props("cbsa.geojson")
    area_ids = [r["area_id"] for r in rows]
    assert len(set(area_ids)) == len(area_ids)
    assert all(a.isdigit() and len(a) == 5 for a in area_ids)
    assert all(r["area_kind"] in {"metropolitan", "micropolitan"} for r in rows)


# --- 4.3 the authoritative assignment ----------------------------------------

def test_every_campus_gets_one_county_one_municipality_and_at_most_one_cbsa():
    rows = _props("campus.geojson")
    assert len(rows) == 206
    for row in rows:
        assert row["county_id"], row["campus_id"]
        assert row["municipality_id"], row["campus_id"]
        assert row.get("cbsa_id") is None or isinstance(row["cbsa_id"], str)


def test_ambiguous_assignment_is_rejected(campus_frame):
    """A campus inside two areas of one layer is a spec violation."""
    point = campus_frame.geometry.iloc[0]
    box = Polygon(
        [
            (point.x - 0.01, point.y - 0.01),
            (point.x + 0.01, point.y - 0.01),
            (point.x + 0.01, point.y + 0.01),
            (point.x - 0.01, point.y + 0.01),
        ]
    )
    overlapping = gpd.GeoDataFrame(
        {"area_id": ["A", "B"]}, geometry=[box, box], crs=4326
    )
    with pytest.raises(B.BuildError, match="more than one area"):
        B.assign_campuses(campus_frame, {"cbsa": overlapping})


def test_missing_required_assignment_is_rejected(campus_frame):
    empty_far_away = gpd.GeoDataFrame(
        {"area_id": ["Z"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs=4326,
    )
    with pytest.raises(B.BuildError, match="have no county"):
        B.assign_campuses(campus_frame, {"county": empty_far_away})


# --- 4.4 the published campus layer ------------------------------------------

def test_campus_layer_carries_both_identifiers_and_explicit_property_names():
    rows = _props("campus.geojson")
    for row in rows:
        assert row["campus_id"]
        assert row["institution_id"]
        assert row["institution"]
    # Source field names are not passed through.
    assert "institution_type" in rows[0]
    assert "TYPE" not in rows[0]
    assert "COLLEGE" not in rows[0]


def test_campus_coordinates_are_longitude_first():
    for feature in _published("campus.geojson")["features"]:
        assert feature["geometry"]["type"] == "Point"
        lon, lat = feature["geometry"]["coordinates"]
        assert -74 < lon < -69
        assert 41 < lat < 43.5


def test_a_sample_campus_reads_correctly_end_to_end():
    rows = {r["campus_id"]: r for r in _props("campus.geojson")}
    row = rows["harvard-university--business-school"]
    assert row["institution"] == "Harvard University"
    assert row["institution_id"] == "harvard-university"
    assert row["campus"] == "Business School"
    # HBS sits across the river in Boston, Suffolk County.
    municipalities = {r["area_id"]: r["name"] for r in _props("municipality.geojson")}
    counties = {r["area_id"]: r["name"] for r in _props("county.geojson")}
    assert municipalities[row["municipality_id"]] == "Boston"
    assert counties[row["county_id"]] == "Suffolk"


# --- 4.5 the assignments index ----------------------------------------------

def test_index_covers_every_area_including_empty_ones():
    index = _published("assignments.json")
    assert set(index) == {"county", "municipality", "cbsa"}
    assert len(index["county"]) == 14
    assert len(index["municipality"]) == 351
    assert len(index["cbsa"]) == 10
    # Areas with no campuses are present with empty memberships.
    empty = [a for a, e in index["municipality"].items() if e["campus_count"] == 0]
    assert empty
    for area_id in empty:
        assert index["municipality"][area_id]["campus_ids"] == []
        assert index["municipality"][area_id]["institution_ids"] == []


def test_index_counts_match_their_arrays_and_hold_no_duplicates():
    index = _published("assignments.json")
    for layer, areas in index.items():
        for area_id, entry in areas.items():
            assert entry["campus_count"] == len(entry["campus_ids"]), (layer, area_id)
            assert entry["institution_count"] == len(entry["institution_ids"])
            assert len(set(entry["institution_ids"])) == len(entry["institution_ids"])


def test_index_round_trips_against_the_campus_properties():
    index = _published("assignments.json")
    rows = _props("campus.geojson")
    for layer in ("county", "municipality", "cbsa"):
        forward: dict[str, set[str]] = {}
        for row in rows:
            area_id = row.get(f"{layer}_id")
            if area_id:
                forward.setdefault(area_id, set()).add(row["campus_id"])
        for area_id, campuses in forward.items():
            assert set(index[layer][area_id]["campus_ids"]) == campuses


# --- 4.6 the institution dimension against known figures --------------------

def test_known_campus_and_institution_counts():
    index = _published("assignments.json")
    municipalities = {r["name"]: r["area_id"] for r in _props("municipality.geojson")}
    expected = {"Boston": (38, 35), "Cambridge": (9, 6), "Worcester": (14, 14)}
    for name, (campuses, institutions) in expected.items():
        entry = index["municipality"][municipalities[name]]
        assert entry["campus_count"] == campuses, name
        assert entry["institution_count"] == institutions, name


def test_harvard_counts_in_both_suffolk_and_middlesex():
    index = _published("assignments.json")
    counties = {r["name"]: r["area_id"] for r in _props("county.geojson")}
    for county in ("Suffolk", "Middlesex"):
        entry = index["county"][counties[county]]
        assert "harvard-university" in entry["institution_ids"], county


# --- 4.7 non-additivity ------------------------------------------------------

def test_campus_counts_sum_but_institution_counts_do_not():
    """A campus has one municipality; an institution can have many.

    Summing institution_count across a layer therefore overshoots the
    statewide total. Consumers must not present such a sum as a total.
    """
    index = _published("assignments.json")
    statewide = _published("provenance.json")["institution_count"]
    assert statewide == 160

    for layer in ("county", "municipality", "cbsa"):
        campus_sum = sum(e["campus_count"] for e in index[layer].values())
        institution_sum = sum(e["institution_count"] for e in index[layer].values())
        assert campus_sum == 206, layer
        assert institution_sum > statewide, (
            f"{layer}: institution counts sum to {institution_sum}, which should "
            f"exceed the {statewide} distinct institutions"
        )


# --- 4.8 the municipality discrepancy report --------------------------------

def test_discrepancy_report_is_emitted(layers, campus_frame):
    assignment = B.assign_campuses(campus_frame, layers)
    findings = B.municipality_discrepancies(
        campus_frame, assignment, layers["municipality"]
    )
    assert isinstance(findings, list)
    assert _published("provenance.json")["reports"][
        "municipality_discrepancies"
    ] == len(findings)


def test_discrepancy_report_flags_an_altered_record(layers, campus_frame):
    """Rewriting one source attribute must show up as a finding."""
    assignment = B.assign_campuses(campus_frame, layers)
    tampered = campus_frame.copy()
    tampered.loc[tampered.index[0], "source_municipality"] = "SPRINGFIELD"
    findings = B.municipality_discrepancies(
        tampered, assignment, layers["municipality"]
    )
    altered = tampered.iloc[0]["campus_id"]
    flagged = [f for f in findings if f["campus_id"] == altered]
    assert len(flagged) == 1
    assert flagged[0]["source_municipality"] == "Springfield"
    assert flagged[0]["computed_municipality"] != "Springfield"


# --- 5.1 topology-preserving simplification ---------------------------------

def test_adjacent_municipalities_still_share_a_border():
    """Boston and Brookline must touch: no gap, no overlap."""
    frame = gpd.read_file(OUT_DIR / "municipality.geojson")
    boston = frame[frame["name"] == "Boston"].geometry.iloc[0]
    brookline = frame[frame["name"] == "Brookline"].geometry.iloc[0]
    shared = boston.intersection(brookline)
    assert not shared.is_empty, "simplification opened a gap"
    assert shared.length > 0, "the shared border vanished"
    assert shared.area == pytest.approx(0, abs=1e-12), "the polygons overlap"


def test_every_published_file_is_within_the_size_budget():
    for name in ("campus.geojson", "county.geojson", "municipality.geojson",
                 "cbsa.geojson", "assignments.json"):
        path = OUT_DIR / name
        if not path.exists():
            pytest.skip(f"{name} not built")
        assert path.stat().st_size <= SIZE_BUDGET_BYTES, name


# --- 5.2 the simplification guard -------------------------------------------

def test_a_far_too_coarse_tolerance_is_rejected(layers, campus_frame):
    """The guard must catch a tolerance that moves campuses off their area."""
    coarse = simplify_layer(layers["municipality"], 0.005)
    with pytest.raises(B.BuildError):
        B.assign_campuses(campus_frame, {"municipality": coarse})


def test_the_default_tolerance_moves_no_campus(layers, campus_frame):
    from ma_geo.simplify import DEFAULT_TOLERANCE

    baseline = B.assign_campuses(campus_frame, layers).set_index("campus_id")
    simplified = {
        name: simplify_layer(frame, DEFAULT_TOLERANCE)
        for name, frame in layers.items()
    }
    after = B.assign_campuses(campus_frame, simplified).set_index("campus_id")
    for layer in layers:
        column = f"{layer}_id"
        assert baseline[column].equals(after.reindex(baseline.index)[column])


# --- 5.3 recorded tolerance and sizes ---------------------------------------

def test_provenance_records_the_derivation_and_cross_check():
    derivation = _published("provenance.json")["derivation"]
    assert derivation["cbsa_membership"]
    assert derivation["county_cross_check"]["worst_relative_difference"] < 0.01
    assert derivation["county_cross_check"]["worst_county"]


def test_provenance_records_the_tolerance_and_the_file_sizes():
    provenance = _published("provenance.json")
    simplification = provenance["simplification"]
    assert simplification["tolerance_degrees"] > 0
    assert simplification["size_budget_bytes"] == SIZE_BUDGET_BYTES
    for name, entry in provenance["published"].items():
        assert entry["bytes"] == (OUT_DIR / name).stat().st_size, name


# --- 3.7 nesting -------------------------------------------------------------

def test_municipalities_nest_inside_their_counties(municipality, layers):
    """Exact on the derived geometry; grid-precision on the published files."""
    link = dict(zip(municipality["area_id"], municipality["county_id"], strict=True))
    B.check_nesting(layers["municipality"], layers["county"], link)

    published_muni = gpd.read_file(OUT_DIR / "municipality.geojson")
    published_county = gpd.read_file(OUT_DIR / "county.geojson")
    B.check_nesting(published_muni, published_county, link, tolerance=1e-7)


def test_counties_nest_inside_their_statistical_areas(cbsa_report, layers):
    link = {
        county_id: cbsa_id
        for cbsa_id, county_ids in cbsa_report["membership"].items()
        for county_id in county_ids
    }
    B.check_nesting(layers["county"], layers["cbsa"], link)

    published_county = gpd.read_file(OUT_DIR / "county.geojson")
    published_cbsa = gpd.read_file(OUT_DIR / "cbsa.geojson")
    B.check_nesting(published_county, published_cbsa, link, tolerance=1e-7)


def test_nesting_check_rejects_a_layer_that_does_not_fill_its_parent():
    """The guard must fire when a finer area fails to cover its parent."""
    parent = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
    half = Polygon([(0, 0), (1, 0), (1, 2), (0, 2)])
    finer = gpd.GeoDataFrame({"area_id": ["a"]}, geometry=[half], crs=4326)
    coarser = gpd.GeoDataFrame({"area_id": ["P"]}, geometry=[parent], crs=4326)
    with pytest.raises(B.BuildError, match="do not reproduce it exactly"):
        B.check_nesting(finer, coarser, {"a": "P"})
