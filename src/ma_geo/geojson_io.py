"""Deterministic GeoJSON writing.

Output must be byte-identical between runs so that a re-run produces no git
diff and a real upstream revision produces a reviewable one. That means a
fixed feature order, fixed key order, and rounded coordinates.
"""

import json
from pathlib import Path

# ~0.11 m at this latitude. Fine enough that rounding cannot move a boundary
# across a campus point, coarse enough to cut file size substantially.
COORD_PRECISION = 6
COORD_GRID = 10**-COORD_PRECISION


def _round_coords(coords):
    if isinstance(coords, (int, float)):
        return round(coords, COORD_PRECISION)
    return [_round_coords(part) for part in coords]


def round_geometry(geometry: dict) -> dict:
    return {
        "type": geometry["type"],
        "coordinates": _round_coords(geometry["coordinates"]),
    }


def render_geojson(features: list[dict]) -> str:
    """Serialize a FeatureCollection deterministically."""
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": feature["properties"],
                "geometry": round_geometry(feature["geometry"]),
            }
            for feature in features
        ],
    }
    return json.dumps(payload, separators=(",", ":"), sort_keys=False) + "\n"


def render_json(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=False) + "\n"


def byte_size(text: str) -> int:
    return len(text.encode("utf-8"))


def write_text(path: Path, text: str) -> int:
    """Write serialized output. Returns bytes written."""
    path.write_text(text)
    return byte_size(text)
