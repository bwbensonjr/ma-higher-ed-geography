"""Topology-preserving simplification.

Simplifying each polygon on its own moves a shared border differently for
each of the two polygons that share it, which tears a boundary layer apart.
`topojson` decomposes a layer into shared arcs, simplifies each arc once,
and reassembles, so a shared border stays shared.
"""

import geopandas as gpd
import pandas as pd
import shapely
import topojson
from shapely.geometry import MultiPolygon

# Degrees. ~22 m at this latitude: enough to cut the municipality layer well
# under the size budget while leaving every campus assignment unchanged (the
# guard in build.py re-checks that on every run).
DEFAULT_TOLERANCE = 0.0002

# Per-file ceiling for a layer served over GitHub Pages with no tiling.
SIZE_BUDGET_BYTES = 2_000_000


def _polygonal_only(geometry):
    """Keep just the polygonal parts of a simplified geometry.

    Simplification can leave a GeometryCollection holding a polygon plus a
    degenerate line or point artifact. Only the polygons are the area.
    """
    if geometry is None or geometry.is_empty:
        return geometry
    if geometry.geom_type in ("Polygon", "MultiPolygon"):
        return geometry
    if geometry.geom_type == "GeometryCollection":
        parts = [g for g in geometry.geoms if g.geom_type in ("Polygon", "MultiPolygon")]
        if not parts:
            raise ValueError("simplified geometry has no polygonal part")
        flat = []
        for part in parts:
            if part.geom_type == "MultiPolygon":
                flat.extend(part.geoms)
            else:
                flat.append(part)
        return flat[0] if len(flat) == 1 else MultiPolygon(flat)
    raise ValueError(f"unexpected simplified geometry type {geometry.geom_type}")


def quantize(frame: gpd.GeoDataFrame, grid_size: float) -> gpd.GeoDataFrame:
    """Snap coordinates to the grid the outputs are written on.

    Quantizing before the layers are dissolved is what makes the published
    files exactly consistent. Dissolving first and rounding at write time
    leaves the derived boundaries a rounding step away from the boundaries
    they came from, which shows up as a hairline mismatch between layers.
    """
    snapped = frame.copy()
    snapped.geometry = shapely.set_precision(
        frame.geometry.values, grid_size=grid_size
    )
    return _normalize(snapped)


def _normalize(frame: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    frame = frame.copy()
    frame.geometry = frame.geometry.make_valid().apply(_polygonal_only)
    kinds = set(frame.geometry.geom_type)
    if not kinds <= {"Polygon", "MultiPolygon"}:
        raise ValueError(f"simplified layer holds non-polygonal geometry: {kinds}")
    return frame


def simplify_layer(frame: gpd.GeoDataFrame, tolerance: float) -> gpd.GeoDataFrame:
    """Simplify one polygon layer, preserving borders shared within it."""
    if tolerance <= 0:
        return frame.copy()
    topology = topojson.Topology(
        frame.to_crs(4326), toposimplify=tolerance, prequantize=False
    )
    simplified = topology.to_gdf(crs="EPSG:4326").set_index(frame.index)
    return _normalize(simplified)


def simplify_layers_together(
    layers: dict[str, gpd.GeoDataFrame], tolerance: float
) -> dict[str, gpd.GeoDataFrame]:
    """Simplify every area layer in one shared topology.

    Simplifying each layer on its own lets the coastline drift differently in
    each, so the layers stop agreeing about where Massachusetts ends. Feeding
    all of them through one topology means a boundary that appears in more
    than one layer -- the coast above all -- becomes one arc, simplified once,
    and every layer keeps the same outer edge.

    Callers must clip the layers to a common mask first, so those boundaries
    really are identical on the way in.
    """
    if tolerance <= 0:
        return {name: frame.copy() for name, frame in layers.items()}

    keys = ["area_id", "layer"]
    combined = pd.concat(
        [frame[keys + ["geometry"]].to_crs(4326) for frame in layers.values()],
        ignore_index=True,
    )
    combined = gpd.GeoDataFrame(combined, geometry="geometry", crs=4326)

    topology = topojson.Topology(combined, toposimplify=tolerance, prequantize=False)
    simplified = _normalize(topology.to_gdf(crs="EPSG:4326").set_index(combined.index))
    simplified[keys] = combined[keys].values

    result = {}
    for name, original in layers.items():
        part = simplified[simplified["layer"] == name]
        geometry_by_id = dict(zip(part["area_id"], part.geometry, strict=True))
        rebuilt = original.copy()
        rebuilt.geometry = [geometry_by_id[a] for a in rebuilt["area_id"]]
        result[name] = rebuilt
    return result
