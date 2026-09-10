"""Check the published outputs against the guarantees the spec makes.

Conditions that break a guarantee raise. Conditions that are legitimate but
worth knowing -- campuses in no CBSA, areas with no campuses, a municipality
that disagrees with its source attribute -- are reported and the run
succeeds.
"""

import json

from ma_geo import sources
from ma_geo.paths import OUT_DIR

LAYERS = ("county", "municipality", "cbsa")
REQUIRED_LAYERS = ("county", "municipality")

EXPECTED_FEATURES = {
    "campus.geojson": sources.COLLEGES.expected_count,
    "county.geojson": sources.COUNTIES.expected_count,
    "municipality.geojson": sources.MUNICIPALITIES.expected_count,
}


class ValidationError(RuntimeError):
    """A published output violates a guarantee in the spec."""


def load_published() -> dict:
    published = {}
    for name in (
        "campus.geojson",
        "county.geojson",
        "municipality.geojson",
        "cbsa.geojson",
        "assignments.json",
        "provenance.json",
    ):
        path = OUT_DIR / name
        if not path.exists():
            raise ValidationError(f"{path} is missing; run `uv run ma-geo build`")
        published[name] = json.loads(path.read_text())
    return published


def check_feature_counts(published: dict) -> None:
    """A published layer must hold as many features as its source."""
    for name, expected in EXPECTED_FEATURES.items():
        actual = len(published[name]["features"])
        if actual != expected:
            raise ValidationError(
                f"{name} holds {actual} features but its source has {expected}"
            )


def check_required_assignments(campus_features: list[dict]) -> None:
    """Every campus needs a county and a municipality."""
    for layer in REQUIRED_LAYERS:
        key = f"{layer}_id"
        missing = [
            f["properties"]["campus_id"]
            for f in campus_features
            if not f["properties"].get(key)
        ]
        if missing:
            raise ValidationError(
                f"{len(missing)} campuses have no {layer}: {missing[:10]}"
            )


def check_identifiers(campus_features: list[dict]) -> None:
    """campus_id is unique; institution_id is present on every campus."""
    campus_ids = [f["properties"]["campus_id"] for f in campus_features]
    duplicates = sorted({c for c in campus_ids if campus_ids.count(c) > 1})
    if duplicates:
        raise ValidationError(f"campus_id is not unique: {duplicates}")
    without = [
        f["properties"]["campus_id"]
        for f in campus_features
        if not f["properties"].get("institution_id")
    ]
    if without:
        raise ValidationError(f"campuses with no institution_id: {without[:10]}")


def check_coordinate_order(campus_features: list[dict]) -> None:
    """Longitude first: Massachusetts is near -71, +42."""
    for feature in campus_features:
        lon, lat = feature["geometry"]["coordinates"]
        if not (-74 < lon < -69 and 41 < lat < 43.5):
            raise ValidationError(
                f"{feature['properties']['campus_id']} has coordinates "
                f"({lon}, {lat}), which are outside Massachusetts or swapped"
            )


def check_assignments_index(index: dict, campus_features: list[dict]) -> None:
    """The reverse index must agree with the campus properties."""
    institution_of = {
        f["properties"]["campus_id"]: f["properties"]["institution_id"]
        for f in campus_features
    }

    for layer in LAYERS:
        if layer not in index:
            raise ValidationError(f"assignments.json has no {layer} layer")
        for area_id, entry in index[layer].items():
            if entry["campus_count"] != len(entry["campus_ids"]):
                raise ValidationError(
                    f"{layer}/{area_id}: campus_count {entry['campus_count']} "
                    f"does not match {len(entry['campus_ids'])} campus_ids"
                )
            if entry["institution_count"] != len(entry["institution_ids"]):
                raise ValidationError(
                    f"{layer}/{area_id}: institution_count "
                    f"{entry['institution_count']} does not match "
                    f"{len(entry['institution_ids'])} institution_ids"
                )
            if len(set(entry["institution_ids"])) != len(entry["institution_ids"]):
                raise ValidationError(
                    f"{layer}/{area_id}: institution_ids holds duplicates"
                )
            expected = sorted({institution_of[c] for c in entry["campus_ids"]})
            if sorted(entry["institution_ids"]) != expected:
                raise ValidationError(
                    f"{layer}/{area_id}: institution_ids do not match the "
                    f"institutions of its campuses"
                )

    # Forward and reverse must describe the same relation.
    for layer in LAYERS:
        forward: dict[str, list[str]] = {}
        for feature in campus_features:
            area_id = feature["properties"].get(f"{layer}_id")
            if area_id:
                forward.setdefault(str(area_id), []).append(
                    feature["properties"]["campus_id"]
                )
        for area_id, campuses in forward.items():
            entry = index[layer].get(area_id)
            if entry is None:
                raise ValidationError(f"{layer}/{area_id} is missing from the index")
            if sorted(entry["campus_ids"]) != sorted(campuses):
                raise ValidationError(
                    f"{layer}/{area_id}: index and campus properties disagree"
                )


def check_area_layers_present(published: dict, index: dict) -> None:
    """Every area in a layer is a key in the index, even with no campuses."""
    for layer in LAYERS:
        area_ids = {
            str(f["properties"]["area_id"])
            for f in published[f"{layer}.geojson"]["features"]
        }
        keys = set(index[layer])
        if area_ids != keys:
            raise ValidationError(
                f"{layer}: layer has {len(area_ids)} areas but the index has "
                f"{len(keys)} keys; difference "
                f"{sorted(area_ids ^ keys)[:10]}"
            )


# The published layers are derived from one geometry source, so their
# boundaries are identical before writing. Rounding coordinates to the
# publication grid can leave a hairline where a dissolve placed a node off
# that grid. Observed residual is under 100 sq m against a 21,012 sq km
# state -- five parts per billion -- so the ceiling is set at one part in
# ten million of the state's area, still far below anything renderable.
OUTLINE_AGREEMENT = 1e-7


def check_shared_outline(published: dict) -> dict:
    """The three area layers must describe one Massachusetts."""
    import geopandas as gpd

    outlines = {}
    for layer in LAYERS:
        frame = gpd.GeoDataFrame.from_features(
            published[f"{layer}.geojson"]["features"], crs=4326
        )
        outlines[layer] = frame.geometry.union_all()

    reference = outlines["municipality"]
    worst = 0.0
    for layer, outline in outlines.items():
        relative = outline.symmetric_difference(reference).area / reference.area
        worst = max(worst, relative)
        if relative > OUTLINE_AGREEMENT:
            raise ValidationError(
                f"the {layer} layer's outline differs from the municipality "
                f"outline by {relative:.3e} of the state's area, above the "
                f"{OUTLINE_AGREEMENT:.0e} ceiling"
            )
    return {"worst_relative_outline_difference": worst}


def informational_report(published: dict, index: dict) -> dict:
    """Legitimate but noteworthy counts."""
    campus_features = published["campus.geojson"]["features"]
    without_cbsa = [
        f["properties"]["campus_id"]
        for f in campus_features
        if not f["properties"].get("cbsa_id")
    ]
    empty_areas = {
        layer: [a for a, e in index[layer].items() if e["campus_count"] == 0]
        for layer in LAYERS
    }
    institution_sum = {
        layer: sum(e["institution_count"] for e in index[layer].values())
        for layer in LAYERS
    }
    campus_sum = {
        layer: sum(e["campus_count"] for e in index[layer].values())
        for layer in LAYERS
    }
    return {
        "campuses_without_cbsa": len(without_cbsa),
        "empty_areas": {k: len(v) for k, v in empty_areas.items()},
        "institution_count_sums": institution_sum,
        "campus_count_sums": campus_sum,
        "statewide_institutions": published["provenance.json"]["institution_count"],
        "municipality_discrepancies": published["provenance.json"]["reports"][
            "municipality_discrepancies"
        ],
    }


def run_validate() -> int:
    published = load_published()
    campus_features = published["campus.geojson"]["features"]
    index = published["assignments.json"]

    print("Checking the published outputs")
    check_feature_counts(published)
    print("  feature counts match their sources")
    check_identifiers(campus_features)
    print("  campus_id unique, institution_id present on every campus")
    check_required_assignments(campus_features)
    print("  every campus has a county and a municipality")
    check_coordinate_order(campus_features)
    print("  coordinates are longitude-first and inside Massachusetts")
    check_area_layers_present(published, index)
    print("  every area in every layer is a key in the index")
    check_assignments_index(index, campus_features)
    print("  the index agrees with the campus properties")
    outline = check_shared_outline(published)
    print(
        f"  the three layers share one outline (worst difference "
        f"{outline['worst_relative_outline_difference']:.2e} of state area)"
    )

    report = informational_report(published, index)
    print("\nInformational")
    print(f"  campuses in no CBSA: {report['campuses_without_cbsa']}")
    for layer, count in report["empty_areas"].items():
        print(f"  {layer} areas with no campuses: {count}")
    print(
        f"  municipality discrepancies vs source: "
        f"{report['municipality_discrepancies']}"
    )
    print(
        f"  statewide distinct institutions: {report['statewide_institutions']}"
    )
    for layer in LAYERS:
        print(
            f"  {layer}: campus counts sum to "
            f"{report['campus_count_sums'][layer]}, institution counts sum to "
            f"{report['institution_count_sums'][layer]} "
            f"(non-additive, not a statewide total)"
        )

    print("\nAll checks passed.")
    return 0
