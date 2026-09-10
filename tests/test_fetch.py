"""Verifications for the fetch layer (tasks 2.1 - 2.5)."""

import json

import pytest

from ma_geo import sources
from ma_geo.fetch import FetchError, fetch_arcgis, fetch_tiger
from ma_geo.paths import RAW_DIR


def _raw(name: str) -> dict:
    path = RAW_DIR / name
    if not path.exists():
        pytest.skip(f"{name} not fetched; run `uv run ma-geo fetch`")
    return json.loads(path.read_text())


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeSession:
    """Stands in for requests.Session, returning canned payloads."""

    def __init__(self, count_payload, query_payload):
        self.count_payload = count_payload
        self.query_payload = query_payload
        self.calls = 0

    def get(self, url, params=None, timeout=None, **kwargs):
        self.calls += 1
        if params and params.get("returnCountOnly") == "true":
            return FakeResponse(self.count_payload)
        return FakeResponse(self.query_payload)


def _feature():
    props = {f: "x" for f in sources.COUNTIES.out_fields}
    return {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": []},
            "properties": props}


# --- 2.1 the helper and its count assertion ---------------------------------

def test_fetch_arcgis_returns_geojson_when_counts_agree():
    payload = {"type": "FeatureCollection",
               "features": [_feature() for _ in range(14)]}
    session = FakeSession({"count": 14}, payload)
    result = fetch_arcgis(sources.COUNTIES, session)
    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 14


def test_fetch_arcgis_raises_when_returned_count_is_short():
    """A truncated or paged response must not be published."""
    payload = {"type": "FeatureCollection",
               "features": [_feature() for _ in range(13)]}
    session = FakeSession({"count": 14}, payload)
    with pytest.raises(FetchError, match="truncated or paged"):
        fetch_arcgis(sources.COUNTIES, session)


def test_fetch_arcgis_raises_when_service_population_changed():
    payload = {"type": "FeatureCollection",
               "features": [_feature() for _ in range(15)]}
    session = FakeSession({"count": 15}, payload)
    with pytest.raises(FetchError, match="expects 14"):
        fetch_arcgis(sources.COUNTIES, session)


def test_fetch_arcgis_raises_when_a_field_is_missing():
    feature = _feature()
    del feature["properties"]["FIPS_STCO"]
    payload = {"type": "FeatureCollection", "features": [feature] * 14}
    session = FakeSession({"count": 14}, payload)
    with pytest.raises(FetchError, match="missing fields"):
        fetch_arcgis(sources.COUNTIES, session)


def test_raw_files_are_valid_geojson():
    for name in ("colleges.geojson", "counties.geojson", "municipalities.geojson"):
        payload = _raw(name)
        assert payload["type"] == "FeatureCollection"
        assert payload["features"]


# --- 2.2 colleges ------------------------------------------------------------

def test_colleges_raw_holds_206_points_with_required_fields():
    payload = _raw("colleges.geojson")
    features = payload["features"]
    assert len(features) == 206
    assert {f["geometry"]["type"] for f in features} == {"Point"}
    required = {"COLLEGE", "CAMPUS", "GEOG_TOWN", "NCES_ID", "TYPE", "CATEGORY",
                "DEGREEOFFR", "ADDRESS", "MAIN_TEL", "URL"}
    for feature in features:
        assert required <= set(feature["properties"])


# --- 2.3 counties ------------------------------------------------------------

def test_counties_raw_holds_14_polygons():
    features = _raw("counties.geojson")["features"]
    assert len(features) == 14
    assert {f["geometry"]["type"] for f in features} <= {"Polygon", "MultiPolygon"}
    for feature in features:
        assert {"COUNTY", "FIPS_STCO"} <= set(feature["properties"])


# --- 2.4 municipalities ------------------------------------------------------

def test_municipalities_raw_holds_351_polygons():
    features = _raw("municipalities.geojson")["features"]
    assert len(features) == 351
    assert {f["geometry"]["type"] for f in features} <= {"Polygon", "MultiPolygon"}
    for feature in features:
        assert {"TOWN", "TOWN_ID", "COUNTY", "FIPS_STCO", "TYPE"} <= set(
            feature["properties"]
        )


# --- 2.5 the TIGER archive ---------------------------------------------------

def test_tiger_archive_reads_as_a_polygon_layer():
    import geopandas as gpd

    archive = RAW_DIR / sources.CBSA.raw_name
    if not archive.exists():
        pytest.skip("TIGER archive not fetched")
    frame = gpd.read_file(f"zip://{archive}")
    assert len(frame) > 900
    assert set(frame.geometry.geom_type) <= {"Polygon", "MultiPolygon"}
    assert {"CBSAFP", "NAME", "NAMELSAD", "LSAD", "MEMI"} <= set(frame.columns)


def test_tiger_rerun_makes_no_second_download(monkeypatch):
    """A complete cached archive must be reused, not re-fetched."""
    archive = RAW_DIR / sources.CBSA.raw_name
    if not archive.exists():
        pytest.skip("TIGER archive not fetched")

    def explode(*args, **kwargs):
        raise AssertionError("re-downloaded an already-cached archive")

    monkeypatch.setattr("requests.Session.get", explode)
    downloaded, size = fetch_tiger(sources.CBSA, force=False)
    assert downloaded is False
    assert size == archive.stat().st_size
