"""Identifier verifications (tasks 4.1, 4.2)."""

import json
import random

import pytest

from ma_geo import ids
from ma_geo.paths import RAW_DIR


def _colleges() -> list[dict]:
    path = RAW_DIR / "colleges.geojson"
    if not path.exists():
        pytest.skip("colleges not fetched")
    return [f["properties"] for f in json.loads(path.read_text())["features"]]


# --- 4.1 campus_id -----------------------------------------------------------

def test_campus_ids_are_distinct_for_all_206_records():
    rows = _colleges()
    assert len(rows) == 206
    campus_ids = [ids.campus_id(r["COLLEGE"], r["CAMPUS"]) for r in rows]
    assert len(set(campus_ids)) == 206


def test_campus_ids_do_not_depend_on_read_order():
    rows = _colleges()
    ordered = {ids.campus_id(r["COLLEGE"], r["CAMPUS"]) for r in rows}
    shuffled = rows[:]
    random.Random(20260910).shuffle(shuffled)
    assert {ids.campus_id(r["COLLEGE"], r["CAMPUS"]) for r in shuffled} == ordered


def test_campus_id_shape():
    assert ids.campus_id("Northeastern University", "Burlington") == (
        "northeastern-university--burlington"
    )
    assert ids.campus_id("Amherst College", None) == "amherst-college"
    assert ids.campus_id("Amherst College", "") == "amherst-college"


def test_nces_id_is_not_usable_as_identity():
    """The reason campus_id is a slug: NCES_ID is neither complete nor unique."""
    rows = _colleges()
    nces = [r["NCES_ID"] for r in rows]
    assert sum(1 for n in nces if not n) == 22
    # 184 records carry a value, but only 139 distinct ones: satellite
    # campuses repeat their parent institution's ID.
    assert sum(1 for n in nces if n) == 184
    assert len({n for n in nces if n}) == 139


def test_nces_id_is_published_but_only_as_an_attribute():
    import geopandas as gpd

    from ma_geo.build import CAMPUS_PROPERTY_MAP

    assert CAMPUS_PROPERTY_MAP["nces_id"] == "NCES_ID"
    published = gpd.read_file("docs/data/campus.geojson")
    assert "nces_id" in published.columns
    # Identity columns are the slugs, never the NCES value.
    assert published["campus_id"].is_unique
    assert not published["nces_id"].fillna("").is_unique


# --- 4.2 institution_id ------------------------------------------------------

def test_exactly_160_distinct_institutions():
    rows = _colleges()
    institution_ids = {ids.institution_id(r["COLLEGE"]) for r in rows}
    assert len(institution_ids) == 160


def test_no_two_institution_names_collide_on_one_id():
    """Aggressive normalization must not merge two different institutions."""
    rows = _colleges()
    by_id: dict[str, set[str]] = {}
    for row in rows:
        by_id.setdefault(ids.institution_id(row["COLLEGE"]), set()).add(row["COLLEGE"])
    collisions = {k: v for k, v in by_id.items() if len(v) > 1}
    assert collisions == {}


def test_all_seven_harvard_campuses_share_one_institution_id():
    rows = _colleges()
    harvard = [r for r in rows if r["COLLEGE"] == "Harvard University"]
    assert len(harvard) == 7
    assert {ids.institution_id(r["COLLEGE"]) for r in harvard} == {
        "harvard-university"
    }
    # ...and they are seven distinct campuses.
    assert len({ids.campus_id(r["COLLEGE"], r["CAMPUS"]) for r in harvard}) == 7


def test_records_without_a_campus_name_have_equal_ids():
    rows = _colleges()
    blank = [r for r in rows if not r["CAMPUS"]]
    assert len(blank) == 114
    for row in blank:
        assert ids.campus_id(row["COLLEGE"], row["CAMPUS"]) == ids.institution_id(
            row["COLLEGE"]
        )


# --- display names -----------------------------------------------------------

def test_display_name_keeps_minor_words_lowercase():
    assert ids.display_name("MANCHESTER-BY-THE-SEA") == "Manchester-by-the-Sea"
    assert ids.display_name("NORTH ANDOVER") == "North Andover"
    assert ids.display_name("SUFFOLK") == "Suffolk"


def test_missing_values_are_treated_as_absent():
    assert ids.slugify(None) == ""
    assert ids.slugify(float("nan")) == ""
    assert ids.display_name(float("nan")) == ""
