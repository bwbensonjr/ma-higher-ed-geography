"""Transform the raw cache into the published outputs."""

import json
from datetime import date

import geopandas as gpd
import pandas as pd
import shapely
from shapely.geometry import mapping
from shapely.ops import unary_union

from ma_geo import ids, sources
from ma_geo.geojson_io import byte_size, render_geojson, render_json, write_text
from ma_geo.paths import OUT_DIR, RAW_DIR, ensure_dirs
from ma_geo.geojson_io import COORD_GRID
from ma_geo.simplify import (
    DEFAULT_TOLERANCE,
    SIZE_BUDGET_BYTES,
    quantize,
    simplify_layer,
)

LAYERS = ("county", "municipality", "cbsa")

# Massachusetts State Plane, for area thresholds in real units.
AREA_CRS = 26986



class BuildError(RuntimeError):
    """The build cannot produce output that satisfies the spec."""


# --- loading -----------------------------------------------------------------


def _read_raw(source: sources.ArcGisSource) -> gpd.GeoDataFrame:
    path = RAW_DIR / source.raw_name
    if not path.exists():
        raise BuildError(f"{path} is missing; run `uv run ma-geo fetch` first")
    frame = gpd.read_file(path)
    if len(frame) != source.expected_count:
        raise BuildError(
            f"{source.key}: raw cache holds {len(frame)} features, expected "
            f"{source.expected_count}"
        )
    return frame.to_crs(4326)


def _read_tiger() -> gpd.GeoDataFrame:
    archive = RAW_DIR / sources.CBSA.raw_name
    if not archive.exists():
        raise BuildError(f"{archive} is missing; run `uv run ma-geo fetch` first")
    return gpd.read_file(f"zip://{archive}").to_crs(4326)


# --- area layers -------------------------------------------------------------


def build_county_layer(raw: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    frame = gpd.GeoDataFrame(
        {
            "area_id": [ids.county_id(v) for v in raw["FIPS_STCO"]],
            "layer": "county",
            "name": [ids.display_name(v) for v in raw["COUNTY"]],
        },
        geometry=raw.geometry.values,
        crs=4326,
    )
    return frame.sort_values("area_id").reset_index(drop=True)


def build_municipality_layer(raw: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    frame = gpd.GeoDataFrame(
        {
            "area_id": [ids.municipality_id(v) for v in raw["TOWN_ID"]],
            "layer": "municipality",
            "name": [ids.display_name(v) for v in raw["TOWN"]],
            "municipality_type": [ids.municipality_type(v) for v in raw["TYPE"]],
            "county_id": [ids.county_id(v) for v in raw["FIPS_STCO"]],
            "county_name": list(raw["COUNTY"]),
        },
        geometry=raw.geometry.values,
        crs=4326,
    )
    return frame.sort_values("area_id", key=lambda s: s.astype(int)).reset_index(
        drop=True
    )


def build_mask(municipalities: gpd.GeoDataFrame):
    """The Massachusetts extent: the union of every municipality polygon."""
    mask = municipalities.geometry.union_all()
    if mask.is_empty:
        raise BuildError("clip mask is empty")
    return mask.buffer(0) if not mask.is_valid else mask


def dissolve_counties(municipalities: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Build the county layer by dissolving municipalities on county_id.

    Taking the geometry from the towns rather than the MassGIS county layer is
    what makes the layers nest exactly and share one outline: they are the
    same arcs.
    """
    names = {
        county_id: ids.display_name(name)
        for county_id, name in zip(
            municipalities["county_id"], municipalities["county_name"], strict=True
        )
    }
    dissolved = municipalities.dissolve(by="county_id", as_index=False)
    frame = gpd.GeoDataFrame(
        {
            "area_id": dissolved["county_id"].values,
            "layer": "county",
            "name": [names[c] for c in dissolved["county_id"]],
        },
        geometry=dissolved.geometry.values,
        crs=4326,
    )
    if len(frame) != sources.COUNTIES.expected_count:
        raise BuildError(
            f"dissolving produced {len(frame)} counties, expected "
            f"{sources.COUNTIES.expected_count}"
        )
    return frame.sort_values("area_id").reset_index(drop=True)


def cross_check_counties(
    dissolved: gpd.GeoDataFrame, massgis: gpd.GeoDataFrame, tolerance: float = 0.01
) -> dict:
    """Compare the dissolved counties with the fetched MassGIS county layer.

    The two disagree slightly because the layers render the coastline
    differently. A large divergence means something real, such as a
    mislabelled county_id in the municipality layer.
    """
    published = dict(zip(massgis["area_id"], massgis.geometry, strict=True))
    missing = set(dissolved["area_id"]) - set(published)
    if missing:
        raise BuildError(f"dissolved counties not in the MassGIS layer: {missing}")

    worst = 0.0
    worst_id = None
    for _, row in dissolved.iterrows():
        reference = published[row["area_id"]]
        relative = abs(row.geometry.area - reference.area) / reference.area
        if relative > worst:
            worst, worst_id = relative, row["area_id"]
        if relative > tolerance:
            raise BuildError(
                f"county {row['area_id']} differs from its MassGIS polygon by "
                f"{relative:.2%}, above the {tolerance:.0%} tolerance"
            )
    return {"worst_relative_difference": worst, "worst_county": worst_id}


def cbsa_membership(tiger: gpd.GeoDataFrame, counties: gpd.GeoDataFrame) -> dict:
    """Which counties belong to which CBSA, by majority overlap.

    In New England a CBSA is defined as a union of whole counties, so a county
    is either in an area or not; the majority test just tolerates the
    coastline disagreement between TIGER and MassGIS.
    """
    membership: dict[str, list[str]] = {}
    for _, county in counties.iterrows():
        matches = []
        for _, area in tiger.iterrows():
            overlap = county.geometry.intersection(area.geometry).area
            if overlap / county.geometry.area > 0.5:
                matches.append(str(area["CBSAFP"]))
        if len(matches) != 1:
            raise BuildError(
                f"county {county['area_id']} maps to {len(matches)} statistical "
                f"areas ({matches}); expected exactly one"
            )
        membership.setdefault(matches[0], []).append(county["area_id"])

    assigned = sum(len(v) for v in membership.values())
    if assigned != len(counties):
        raise BuildError(
            f"{assigned} counties assigned to statistical areas, expected "
            f"{len(counties)}"
        )
    return membership


def build_cbsa_layer(
    tiger: gpd.GeoDataFrame, counties: gpd.GeoDataFrame
) -> tuple[gpd.GeoDataFrame, dict]:
    """Derive the statistical-area layer by dissolving counties.

    TIGER supplies membership, the official name and the metropolitan or
    micropolitan kind. Its geometry is not published: an area's Massachusetts
    extent is the union of its Massachusetts counties, which is what the
    county-based New England definition means.
    """
    candidates = tiger[tiger.intersects(counties.geometry.union_all())].copy()
    membership = cbsa_membership(candidates, counties)

    attributes = {
        str(row["CBSAFP"]): {
            "name": row["NAMELSAD"],
            "area_kind": (
                "metropolitan" if str(row["MEMI"]) == "1" else "micropolitan"
            ),
        }
        for _, row in candidates.iterrows()
    }

    geometry_by_id = dict(zip(counties["area_id"], counties.geometry, strict=True))
    rows = []
    for cbsa_id, county_ids in membership.items():
        parts = [geometry_by_id[c] for c in county_ids]
        rows.append(
            {
                "area_id": cbsa_id,
                "layer": "cbsa",
                "name": attributes[cbsa_id]["name"],
                "area_kind": attributes[cbsa_id]["area_kind"],
                "geometry": shapely.make_valid(unary_union(parts)),
            }
        )

    frame = gpd.GeoDataFrame(rows, geometry="geometry", crs=4326)
    frame = frame.sort_values("area_id").reset_index(drop=True)

    excluded = [
        {"area_id": str(row["CBSAFP"]), "name": row["NAMELSAD"]}
        for _, row in tiger[
            tiger.intersects(counties.geometry.union_all())
        ].iterrows()
        if str(row["CBSAFP"]) not in membership
    ]
    report = {
        "counties_per_area": {k: len(v) for k, v in membership.items()},
        "membership": {k: sorted(v) for k, v in membership.items()},
        "excluded_areas": sorted(excluded, key=lambda e: e["area_id"]),
    }
    return frame, report


def check_nesting(
    finer: gpd.GeoDataFrame,
    coarser: gpd.GeoDataFrame,
    link: dict[str, str],
    tolerance: float = 1e-11,
) -> None:
    """Every finer area must lie inside its coarser area, together filling it.

    The tolerance is a fraction of the coarser area. The default is
    floating-point zero, which the derived geometry meets because it is
    literally the same arcs. Published files, whose coordinates are rounded
    to the publication grid, are checked against a looser bound.
    """
    groups: dict[str, list] = {}
    for _, row in finer.iterrows():
        parent = link[row["area_id"]]
        groups.setdefault(parent, []).append(row.geometry)

    coarser_geometry = dict(zip(coarser["area_id"], coarser.geometry, strict=True))
    for parent, parts in groups.items():
        combined = unary_union(parts)
        reference = coarser_geometry[parent]
        difference = combined.symmetric_difference(reference).area
        relative = difference / reference.area
        if relative > tolerance:
            raise BuildError(
                f"areas inside {parent} do not reproduce it exactly: "
                f"symmetric difference {difference:.3e}, which is "
                f"{relative:.3e} of the area, above the {tolerance:.0e} bound"
            )


# --- campus layer ------------------------------------------------------------

CAMPUS_PROPERTY_MAP = {
    "institution": "COLLEGE",
    "campus": "CAMPUS",
    "address": "ADDRESS",
    "city": "CITY",
    "zip_code": "ZIPCODE",
    "telephone": "MAIN_TEL",
    "website": "URL",
    "institution_type": "TYPE",
    "category": "CATEGORY",
    "degrees_offered": "DEGREEOFFR",
    "awards_offered": "AWARDSOFFR",
    "largest_program": "LARGEPROG",
    "campus_setting": "CAMPUSSETT",
    "campus_housing": "CAMPUSHOUS",
    "nces_id": "NCES_ID",
    "nces_type": "NCES_TYPE",
    "source_municipality": "GEOG_TOWN",
}


def build_campus_layer(raw: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    data = {
        "campus_id": [
            ids.campus_id(row["COLLEGE"], row["CAMPUS"])
            for _, row in raw.iterrows()
        ],
        "institution_id": [ids.institution_id(v) for v in raw["COLLEGE"]],
    }
    for out_name, src_name in CAMPUS_PROPERTY_MAP.items():
        data[out_name] = [
            None if pd.isna(v) or v == "" else v for v in raw[src_name]
        ]

    frame = gpd.GeoDataFrame(data, geometry=raw.geometry.values, crs=4326)

    duplicates = frame["campus_id"][frame["campus_id"].duplicated()].tolist()
    if duplicates:
        raise BuildError(f"campus_id is not unique: {sorted(set(duplicates))}")

    return frame.sort_values("campus_id").reset_index(drop=True)


# --- assignment --------------------------------------------------------------


def assign_campuses(
    campuses: gpd.GeoDataFrame, area_layers: dict[str, gpd.GeoDataFrame]
) -> pd.DataFrame:
    """Point-in-polygon assignment of every campus in every area layer.

    Required layers must match exactly one area; an ambiguous match means a
    campus sits on a shared border and is a spec violation, not a tie to
    break silently.
    """
    result = pd.DataFrame({"campus_id": campuses["campus_id"].values})

    for layer, areas in area_layers.items():
        joined = gpd.sjoin(
            campuses[["campus_id", "geometry"]],
            areas[["area_id", "geometry"]],
            how="left",
            predicate="intersects",
        )
        counts = joined.groupby("campus_id")["area_id"].nunique()
        ambiguous = counts[counts > 1]
        if not ambiguous.empty:
            detail = {
                cid: sorted(joined[joined["campus_id"] == cid]["area_id"].dropna())
                for cid in ambiguous.index
            }
            raise BuildError(
                f"{layer}: campuses match more than one area: {detail}"
            )
        mapping_series = (
            joined.dropna(subset=["area_id"])
            .drop_duplicates("campus_id")
            .set_index("campus_id")["area_id"]
        )
        result[f"{layer}_id"] = result["campus_id"].map(mapping_series)

    for layer in ("county", "municipality"):
        if layer not in area_layers:
            continue
        missing = result[result[f"{layer}_id"].isna()]["campus_id"].tolist()
        if missing:
            raise BuildError(
                f"{len(missing)} campuses have no {layer}: {missing[:10]}"
            )

    return result


def build_assignments_index(
    assignment: pd.DataFrame,
    campuses: gpd.GeoDataFrame,
    area_layers: dict[str, gpd.GeoDataFrame],
) -> dict:
    """The reverse direction: for each area, its campuses and institutions."""
    institution_of = dict(
        zip(campuses["campus_id"], campuses["institution_id"], strict=True)
    )
    index: dict[str, dict] = {}

    for layer, areas in area_layers.items():
        layer_index: dict[str, dict] = {}
        for area_id in areas["area_id"]:
            layer_index[str(area_id)] = {
                "campus_ids": [],
                "institution_ids": [],
                "campus_count": 0,
                "institution_count": 0,
            }
        for _, row in assignment.iterrows():
            area_id = row[f"{layer}_id"]
            if pd.isna(area_id):
                continue
            entry = layer_index[str(area_id)]
            entry["campus_ids"].append(row["campus_id"])
            institution = institution_of[row["campus_id"]]
            if institution not in entry["institution_ids"]:
                entry["institution_ids"].append(institution)
        for entry in layer_index.values():
            entry["campus_ids"].sort()
            entry["institution_ids"].sort()
            entry["campus_count"] = len(entry["campus_ids"])
            entry["institution_count"] = len(entry["institution_ids"])
        index[layer] = dict(sorted(layer_index.items()))

    return index


def build_area_index(published: dict[str, "gpd.GeoDataFrame"]) -> dict:
    """Area display names, so a consumer can name a campus's geographies.

    A name is otherwise published only inside its layer's geometry file, and
    a page that names a campus's county in a table would have to fetch all
    three layers to read it. This index is small enough to fetch eagerly.
    The campus `city` attribute is not a substitute: it is the mailing city,
    which names a different place than the assigned municipality for 18 of
    the 206 campuses.
    """
    index: dict[str, dict] = {}
    for layer in ("county", "municipality", "cbsa"):
        frame = published[layer]
        entries = {}
        for row in frame.itertuples():
            entry = {"name": row.name}
            if layer == "municipality":
                entry["county_id"] = row.county_id
            entries[str(row.area_id)] = entry
        # Sorted by name so the file reads in the order a reader expects and
        # a diff stays legible when one area is renamed upstream.
        index[layer] = dict(
            sorted(entries.items(), key=lambda item: item[1]["name"])
        )
    return index


def municipality_discrepancies(
    campuses: gpd.GeoDataFrame,
    assignment: pd.DataFrame,
    municipalities: gpd.GeoDataFrame,
) -> list[dict]:
    """Where the computed municipality disagrees with the source attribute.

    Informational, not fatal: the spatial answer is authoritative, but a
    disagreement is worth a human look.
    """
    name_of = dict(zip(municipalities["area_id"], municipalities["name"], strict=True))
    source_of = dict(
        zip(campuses["campus_id"], campuses["source_municipality"], strict=True)
    )
    findings = []
    for _, row in assignment.iterrows():
        computed = name_of.get(str(row["municipality_id"]))
        source = source_of.get(row["campus_id"])
        source_display = ids.display_name(source)
        if not source_display:
            continue
        if source_display != computed:
            findings.append(
                {
                    "campus_id": row["campus_id"],
                    "computed_municipality": computed,
                    "source_municipality": source_display,
                }
            )
    return findings


# --- writing -----------------------------------------------------------------


def _features(frame: gpd.GeoDataFrame) -> list[dict]:
    property_columns = [c for c in frame.columns if c != frame.geometry.name]
    features = []
    for _, row in frame.iterrows():
        properties = {}
        for column in property_columns:
            value = row[column]
            if isinstance(value, float) and pd.isna(value):
                value = None
            elif value is pd.NA:
                value = None
            properties[column] = value
        features.append({"properties": properties, "geometry": mapping(row.geometry)})
    return features


def _derive_layers(
    municipality: gpd.GeoDataFrame, tiger: gpd.GeoDataFrame
) -> tuple[dict[str, gpd.GeoDataFrame], dict]:
    """County and statistical-area layers, dissolved from the municipalities."""
    county = dissolve_counties(municipality)
    cbsa, report = build_cbsa_layer(tiger, county)
    return {"county": county, "municipality": municipality, "cbsa": cbsa}, report


def run_build(tolerance: float | None = None) -> int:
    ensure_dirs()
    tolerance = DEFAULT_TOLERANCE if tolerance is None else tolerance

    print("Reading the raw cache")
    municipality = build_municipality_layer(_read_raw(sources.MUNICIPALITIES))
    campus = build_campus_layer(_read_raw(sources.COLLEGES))
    massgis_counties = build_county_layer(_read_raw(sources.COUNTIES))
    tiger = _read_tiger()
    print(
        f"  {len(municipality)} municipalities, {len(campus)} campuses, "
        f"{campus['institution_id'].nunique()} distinct institutions"
    )

    print("Deriving the area layers from the municipality polygons")
    full_res, cbsa_report = _derive_layers(municipality, tiger)
    print(
        f"  county: {len(full_res['county'])} | "
        f"municipality: {len(full_res['municipality'])} | "
        f"cbsa: {len(full_res['cbsa'])}"
    )
    for cbsa_id, counties in sorted(cbsa_report["membership"].items()):
        name = full_res["cbsa"].set_index("area_id").loc[cbsa_id, "name"]
        print(f"      {name}: {len(counties)} county/counties")
    if cbsa_report["excluded_areas"]:
        print(
            f"  {len(cbsa_report['excluded_areas'])} areas excluded: they "
            "overlap the state line but contain no Massachusetts county"
        )
        for entry in cbsa_report["excluded_areas"]:
            print(f"      excluded {entry['name']}")

    check = cross_check_counties(full_res["county"], massgis_counties)
    print(
        f"  counties agree with the MassGIS layer within "
        f"{check['worst_relative_difference']:.2%} (worst: "
        f"{check['worst_county']})"
    )

    print("Assigning campuses (full resolution, authoritative)")
    assignment = assign_campuses(campus, full_res)
    no_cbsa = int(assignment["cbsa_id"].isna().sum())
    print(f"  every campus has a county and a municipality; {no_cbsa} have no CBSA")

    print(f"Simplifying the municipality layer ({tolerance}), then re-deriving")
    simplified_municipality = simplify_layer(municipality, tolerance)
    # Snap to the publication grid before dissolving, so the derived layers
    # are built from the same coordinates that get written to disk.
    simplified_municipality = quantize(simplified_municipality, COORD_GRID)
    simplified, _ = _derive_layers(simplified_municipality, tiger)

    print("Re-checking the assignment against the simplified geometry")
    recheck = assign_campuses(campus, simplified)
    for layer in LAYERS:
        column = f"{layer}_id"
        before = assignment.set_index("campus_id")[column]
        after = recheck.set_index("campus_id")[column]
        differing = before[
            before.fillna("~") != after.reindex(before.index).fillna("~")
        ]
        if not differing.empty:
            raise BuildError(
                f"simplification at tolerance {tolerance} moved {len(differing)} "
                f"campuses across a {layer} boundary: {differing.index.tolist()[:10]}"
            )
    print("  assignment unchanged by simplification")

    print("Checking that the published layers nest and share one outline")
    outlines = {
        name: frame.geometry.union_all() for name, frame in simplified.items()
    }
    reference = outlines["municipality"]
    for name, outline in outlines.items():
        difference = outline.symmetric_difference(reference).area
        if difference > 1e-12:
            raise BuildError(
                f"the {name} layer's outline differs from the municipality "
                f"outline by {difference:.3e}"
            )
    check_nesting(
        simplified["municipality"],
        simplified["county"],
        dict(zip(municipality["area_id"], municipality["county_id"], strict=True)),
    )
    county_to_cbsa = {
        county_id: cbsa_id
        for cbsa_id, county_ids in cbsa_report["membership"].items()
        for county_id in county_ids
    }
    check_nesting(simplified["county"], simplified["cbsa"], county_to_cbsa)
    print("  outlines identical; municipality nests in county nests in cbsa")

    discrepancies = municipality_discrepancies(campus, assignment, municipality)
    print(f"  {len(discrepancies)} municipality discrepancies vs the source attribute")
    for finding in discrepancies[:10]:
        print(
            f"      {finding['campus_id']}: computed "
            f"{finding['computed_municipality']}, source "
            f"{finding['source_municipality']}"
        )

    # The published campus layer carries its authoritative area IDs.
    campus_published = campus.merge(assignment, on="campus_id", how="left")

    print("Rendering the published outputs")
    index = build_assignments_index(assignment, campus, full_res)
    rendered = {"campus.geojson": render_geojson(_features(campus_published))}
    for name, frame in simplified.items():
        published = frame.drop(columns=["county_name"], errors="ignore")
        rendered[f"{name}.geojson"] = render_geojson(_features(published))
    rendered["assignments.json"] = render_json(index)
    rendered["area.json"] = render_json(build_area_index(simplified))

    sizes = {name: byte_size(text) for name, text in rendered.items()}

    # Check the budget before writing anything, so a failing run leaves the
    # previously published outputs untouched.
    over_budget = {
        name: size for name, size in sizes.items() if size > SIZE_BUDGET_BYTES
    }
    if over_budget:
        raise BuildError(
            f"files exceed the {SIZE_BUDGET_BYTES:,}-byte budget: "
            + ", ".join(f"{n} at {s:,}" for n, s in over_budget.items())
        )

    print("Writing the published outputs")
    for name, text in rendered.items():
        write_text(OUT_DIR / name, text)

    provenance = build_provenance(
        sizes=sizes,
        tolerance=tolerance,
        counts={
            "campus": len(campus_published),
            "county": len(full_res["county"]),
            "municipality": len(full_res["municipality"]),
            "cbsa": len(full_res["cbsa"]),
        },
        institution_count=int(campus["institution_id"].nunique()),
        cbsa_report=cbsa_report,
        discrepancies=len(discrepancies),
        campuses_without_cbsa=no_cbsa,
        county_cross_check=check,
    )
    write_text(OUT_DIR / "provenance.json", render_json(provenance))

    for name, size in sizes.items():
        print(f"  {name}: {size:,} bytes")
    print(f"\nPublished to {OUT_DIR}")
    return 0


def build_provenance(
    sizes: dict[str, int],
    tolerance: float,
    counts: dict[str, int],
    institution_count: int,
    cbsa_report: dict,
    discrepancies: int,
    campuses_without_cbsa: int,
    county_cross_check: dict,
) -> dict:
    manifest_path = RAW_DIR / "fetch_manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    return {
        "generated": date.today().isoformat(),
        "sources": {
            "colleges": manifest.get("colleges", {}),
            "counties": manifest.get("counties", {}),
            "municipalities": manifest.get("municipalities", {}),
            "cbsa": manifest.get("cbsa", {}),
        },
        "published": {
            "campus.geojson": {
                "features": counts["campus"],
                "bytes": sizes.get("campus.geojson"),
            },
            "county.geojson": {
                "features": counts["county"],
                "bytes": sizes.get("county.geojson"),
            },
            "municipality.geojson": {
                "features": counts["municipality"],
                "bytes": sizes.get("municipality.geojson"),
            },
            "cbsa.geojson": {
                "features": counts["cbsa"],
                "bytes": sizes.get("cbsa.geojson"),
            },
            "assignments.json": {"bytes": sizes.get("assignments.json")},
            "area.json": {"bytes": sizes.get("area.json")},
        },
        "institution_count": institution_count,
        "simplification": {
            "method": "topojson topology-preserving",
            "tolerance_degrees": tolerance,
            "size_budget_bytes": SIZE_BUDGET_BYTES,
        },
        "derivation": {
            "method": (
                "municipality polygons simplified once, dissolved on county_id "
                "into counties, dissolved on TIGER CBSA membership into "
                "statistical areas"
            ),
            "cbsa_membership": cbsa_report["membership"],
            "cbsa_excluded": cbsa_report["excluded_areas"],
            "county_cross_check": {
                "worst_relative_difference": round(
                    county_cross_check["worst_relative_difference"], 6
                ),
                "worst_county": county_cross_check["worst_county"],
            },
        },
        "reports": {
            "municipality_discrepancies": discrepancies,
            "campuses_without_cbsa": campuses_without_cbsa,
        },
        "notes": (
            "Institution counts are per-area and non-additive: an institution with "
            "campuses in two areas is counted in both, so summing institution_count "
            "across a layer exceeds institution_count above. Campus counts do sum."
        ),
    }
