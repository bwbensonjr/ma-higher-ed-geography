"""The contract the web page reads the published outputs through.

The page fetches these files directly and reads these field names, so a
rename or a dropped field breaks it at page load with no other warning.
These checks make that failure happen here instead, while the previously
published outputs are still in place.

The four files the page fetches at load are `campus.geojson`,
`assignments.json`, `area.json`, and `provenance.json`; the area layers are
fetched only when a visitor draws one.

A field is either required, meaning it must be present and non-empty, or
optional, meaning the key must be present but an empty value is a legitimate
answer: 114 of the 206 campuses publish no campus name, and a campus outside
every statistical area has no `cbsa_id`.
"""

import json

from ma_geo.paths import OUT_DIR

LAYERS = ("county", "municipality", "cbsa")

# Identity and the attributes the table and the popup display.
AWARD_TIERS = ("sub_associate", "two_year", "four_year")
DEGREE_GRANTING_TIERS = ("two_year", "four_year")

CAMPUS_REQUIRED = (
    "campus_id",
    "institution_id",
    "institution",
    "address",
    "city",
    "zip_code",
    "institution_type",
    "category",
    "degrees_offered",
    "county_id",
    "municipality_id",
    "award_tier",
)
CAMPUS_OPTIONAL = (
    "campus",
    "telephone",
    "website",
    "cbsa_id",
)

AREA_REQUIRED = ("area_id", "layer", "name")
AREA_REQUIRED_BY_LAYER = {"municipality": ("county_id",)}

ASSIGNMENT_LIST_FIELDS = ("campus_ids", "institution_ids")
ASSIGNMENT_COUNT_FIELDS = (
    "campus_count",
    "institution_count",
    "degree_granting_campus_count",
    "degree_granting_institution_count",
)

# Figures the page displays out of the provenance record.
PROVENANCE_REQUIRED = (
    "generated",
    "institution_count",
    "degree_granting_institution_count",
)

AREA_INDEX_REQUIRED = ("name",)
AREA_INDEX_REQUIRED_BY_LAYER = {"municipality": ("county_id",)}

CAMPUS_FILE = "campus.geojson"
ASSIGNMENTS_FILE = "assignments.json"
AREA_INDEX_FILE = "area.json"
PROVENANCE_FILE = "provenance.json"


class ContractError(RuntimeError):
    """A published output no longer matches what the page reads."""


def _area_file(layer: str) -> str:
    return f"{layer}.geojson"


def check_campus_fields(published: dict) -> None:
    """Every campus carries its identity, its area ids, and its display fields."""
    for feature in published[CAMPUS_FILE]["features"]:
        properties = feature["properties"]
        label = properties.get("campus_id") or "<a campus with no campus_id>"
        for field in CAMPUS_REQUIRED:
            if field not in properties:
                raise ContractError(
                    f"{CAMPUS_FILE}: {label} is missing the required field "
                    f"{field!r}, which the page reads"
                )
            if properties[field] in (None, ""):
                raise ContractError(
                    f"{CAMPUS_FILE}: {label} has an empty {field!r}, which the "
                    f"page requires to be present"
                )
        for field in CAMPUS_OPTIONAL:
            if field not in properties:
                raise ContractError(
                    f"{CAMPUS_FILE}: {label} is missing the field {field!r}; "
                    f"the value may be empty but the field must be published"
                )
        if "degree_granting" not in properties:
            raise ContractError(
                f"{CAMPUS_FILE}: {label} is missing the required field "
                f"'degree_granting', which the page reads"
            )
        if not isinstance(properties["degree_granting"], bool):
            raise ContractError(
                f"{CAMPUS_FILE}: {label} publishes 'degree_granting' as "
                f"{type(properties['degree_granting']).__name__}, not a boolean"
            )
        if properties["award_tier"] not in AWARD_TIERS:
            raise ContractError(
                f"{CAMPUS_FILE}: {label} has award_tier "
                f"{properties['award_tier']!r}, which is not one of "
                f"{list(AWARD_TIERS)}"
            )
        expected = properties["award_tier"] in DEGREE_GRANTING_TIERS
        if properties["degree_granting"] is not expected:
            raise ContractError(
                f"{CAMPUS_FILE}: {label} is award_tier "
                f"{properties['award_tier']!r} but degree_granting "
                f"{properties['degree_granting']!r}"
            )
        if feature["geometry"]["type"] != "Point":
            raise ContractError(
                f"{CAMPUS_FILE}: {label} is a "
                f"{feature['geometry']['type']}, not a Point"
            )


def check_area_fields(published: dict) -> None:
    """Every area carries an id, its layer, and a display name."""
    for layer in LAYERS:
        name = _area_file(layer)
        required = AREA_REQUIRED + AREA_REQUIRED_BY_LAYER.get(layer, ())
        for feature in published[name]["features"]:
            properties = feature["properties"]
            label = properties.get("area_id") or "<an area with no area_id>"
            for field in required:
                if field not in properties:
                    raise ContractError(
                        f"{name}: area {label} is missing the required field "
                        f"{field!r}, which the page reads"
                    )
                if properties[field] in (None, ""):
                    raise ContractError(
                        f"{name}: area {label} has an empty {field!r}"
                    )
            if properties["layer"] != layer:
                raise ContractError(
                    f"{name}: area {label} declares layer "
                    f"{properties['layer']!r} but is published in {name}"
                )


def check_assignment_fields(published: dict) -> None:
    """Every area of every layer carries both memberships and both counts."""
    index = published[ASSIGNMENTS_FILE]
    for layer in LAYERS:
        if layer not in index:
            raise ContractError(
                f"{ASSIGNMENTS_FILE} has no {layer!r} layer, which the page reads"
            )
        for area_id, entry in index[layer].items():
            for field in ASSIGNMENT_LIST_FIELDS:
                if field not in entry:
                    raise ContractError(
                        f"{ASSIGNMENTS_FILE}: {layer}/{area_id} is missing "
                        f"{field!r}, which the page reads"
                    )
                if not isinstance(entry[field], list):
                    raise ContractError(
                        f"{ASSIGNMENTS_FILE}: {layer}/{area_id} has {field!r} "
                        f"as {type(entry[field]).__name__}, not a list"
                    )
            for field in ASSIGNMENT_COUNT_FIELDS:
                if field not in entry:
                    raise ContractError(
                        f"{ASSIGNMENTS_FILE}: {layer}/{area_id} is missing "
                        f"{field!r}, which the page reads"
                    )
                if not isinstance(entry[field], int):
                    raise ContractError(
                        f"{ASSIGNMENTS_FILE}: {layer}/{area_id} has {field!r} "
                        f"as {type(entry[field]).__name__}, not a whole number"
                    )


def check_population_counts(published: dict) -> None:
    """The published counts must agree with the campuses' own flags.

    The page reads these counts rather than deriving them, so a count that
    drifts from the flags would be displayed as fact with nothing to catch
    it. Institution counts are not additive, which is why they are counted
    here rather than left to a consumer.
    """
    campus_features = published[CAMPUS_FILE]["features"]
    granting = {
        f["properties"]["campus_id"]
        for f in campus_features
        if f["properties"].get("degree_granting")
    }
    institution_of = {
        f["properties"]["campus_id"]: f["properties"]["institution_id"]
        for f in campus_features
    }
    index = published[ASSIGNMENTS_FILE]
    for layer in LAYERS:
        for area_id, entry in index[layer].items():
            members = [c for c in entry["campus_ids"] if c in granting]
            if entry["degree_granting_campus_count"] != len(members):
                raise ContractError(
                    f"{ASSIGNMENTS_FILE}: {layer}/{area_id} publishes "
                    f"degree_granting_campus_count "
                    f"{entry['degree_granting_campus_count']} but its members' "
                    f"flags in {CAMPUS_FILE} imply {len(members)}"
                )
            institutions = {institution_of[c] for c in members}
            if entry["degree_granting_institution_count"] != len(institutions):
                raise ContractError(
                    f"{ASSIGNMENTS_FILE}: {layer}/{area_id} publishes "
                    f"degree_granting_institution_count "
                    f"{entry['degree_granting_institution_count']} but its "
                    f"members' flags in {CAMPUS_FILE} imply {len(institutions)}"
                )


def check_references(published: dict) -> None:
    """Every identifier one file uses must resolve in the file that defines it."""
    campus_features = published[CAMPUS_FILE]["features"]
    campus_ids = {f["properties"]["campus_id"] for f in campus_features}
    institution_ids = {f["properties"]["institution_id"] for f in campus_features}
    areas = {
        layer: {
            str(f["properties"]["area_id"])
            for f in published[_area_file(layer)]["features"]
        }
        for layer in LAYERS
    }

    for feature in campus_features:
        properties = feature["properties"]
        for layer in LAYERS:
            area_id = properties.get(f"{layer}_id")
            if not area_id:
                continue
            if str(area_id) not in areas[layer]:
                raise ContractError(
                    f"{CAMPUS_FILE}: {properties['campus_id']} references "
                    f"{layer}_id {area_id!r}, which no area in "
                    f"{_area_file(layer)} carries"
                )

    index = published[ASSIGNMENTS_FILE]
    for layer in LAYERS:
        for area_id, entry in index[layer].items():
            if area_id not in areas[layer]:
                raise ContractError(
                    f"{ASSIGNMENTS_FILE}: {layer}/{area_id} is not an area in "
                    f"{_area_file(layer)}"
                )
            for campus_id in entry["campus_ids"]:
                if campus_id not in campus_ids:
                    raise ContractError(
                        f"{ASSIGNMENTS_FILE}: {layer}/{area_id} lists campus "
                        f"{campus_id!r}, which no feature in {CAMPUS_FILE} carries"
                    )
            for institution_id in entry["institution_ids"]:
                if institution_id not in institution_ids:
                    raise ContractError(
                        f"{ASSIGNMENTS_FILE}: {layer}/{area_id} lists institution "
                        f"{institution_id!r}, which no feature in "
                        f"{CAMPUS_FILE} carries"
                    )


def check_area_index(published: dict) -> None:
    """The page names a campus's geographies out of this file alone."""
    index = published[AREA_INDEX_FILE]
    for layer in LAYERS:
        if layer not in index:
            raise ContractError(
                f"{AREA_INDEX_FILE} has no {layer!r} layer, which the page reads"
            )
        required = AREA_INDEX_REQUIRED + AREA_INDEX_REQUIRED_BY_LAYER.get(layer, ())
        published_areas = {
            str(f["properties"]["area_id"]): f["properties"]
            for f in published[_area_file(layer)]["features"]
        }
        for area_id, entry in index[layer].items():
            for field in required:
                if field not in entry:
                    raise ContractError(
                        f"{AREA_INDEX_FILE}: {layer}/{area_id} is missing "
                        f"{field!r}, which the page reads"
                    )
                if entry[field] in (None, ""):
                    raise ContractError(
                        f"{AREA_INDEX_FILE}: {layer}/{area_id} has an empty "
                        f"{field!r}"
                    )
            area = published_areas.get(area_id)
            if area is None:
                raise ContractError(
                    f"{AREA_INDEX_FILE}: {layer}/{area_id} names no area in "
                    f"{_area_file(layer)}"
                )
            if entry["name"] != area["name"]:
                raise ContractError(
                    f"{AREA_INDEX_FILE}: {layer}/{area_id} is named "
                    f"{entry['name']!r} but {_area_file(layer)} names it "
                    f"{area['name']!r}"
                )
        missing = set(published_areas) - set(index[layer])
        if missing:
            raise ContractError(
                f"{AREA_INDEX_FILE}: {len(missing)} {layer} areas are absent "
                f"from the index, including {sorted(missing)[:5]}; the page "
                f"would have no name for them"
            )


def check_provenance_fields(published: dict) -> None:
    """The figures the page displays out of the provenance record are present."""
    provenance = published[PROVENANCE_FILE]
    for field in PROVENANCE_REQUIRED:
        if not provenance.get(field):
            raise ContractError(
                f"{PROVENANCE_FILE} is missing {field!r}, which the page displays"
            )
    if not provenance.get("sources"):
        raise ContractError(
            f"{PROVENANCE_FILE} is missing 'sources', which the page displays"
        )
    for key, entry in provenance["sources"].items():
        for field in ("title", "fetched"):
            if not entry.get(field):
                raise ContractError(
                    f"{PROVENANCE_FILE}: source {key!r} is missing {field!r}, "
                    f"which the page displays"
                )
    if PROVENANCE_FILE and not provenance.get("published", {}).get(AREA_INDEX_FILE):
        raise ContractError(
            f"{PROVENANCE_FILE} does not record {AREA_INDEX_FILE}, which the "
            f"page fetches at load"
        )
    for name in (CAMPUS_FILE, *(_area_file(layer) for layer in LAYERS)):
        entry = provenance.get("published", {}).get(name)
        if entry is None or "features" not in entry:
            raise ContractError(
                f"{PROVENANCE_FILE} does not record a feature count for {name}"
            )


def check_page_can_fetch_what_it_reads() -> None:
    """The page fetches these three files eagerly; they must be readable."""
    for name in (CAMPUS_FILE, ASSIGNMENTS_FILE, AREA_INDEX_FILE, PROVENANCE_FILE):
        path = OUT_DIR / name
        if not path.exists():
            raise ContractError(f"{path} is missing; the page fetches it at load")
        try:
            json.loads(path.read_text())
        except json.JSONDecodeError as error:
            raise ContractError(f"{name} is not valid JSON: {error}") from error


def check_contract(published: dict) -> None:
    check_page_can_fetch_what_it_reads()
    check_campus_fields(published)
    check_area_fields(published)
    check_assignment_fields(published)
    check_area_index(published)
    check_population_counts(published)
    check_references(published)
    check_provenance_fields(published)
