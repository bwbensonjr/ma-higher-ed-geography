"""Fetch the upstream sources into the raw cache.

The MassGIS layers come from hosted ArcGIS feature services, asked for as
GeoJSON already reprojected to EPSG:4326, with an explicit field list. The
service is asked separately for its own record count, and the returned
feature count is asserted against it: that is what catches a truncated or
paged response rather than publishing a short layer.
"""

import json
from datetime import date

import requests

from ma_geo import sources
from ma_geo.paths import RAW_DIR, ensure_dirs

TIMEOUT = 120
USER_AGENT = "ma-higher-ed-geography/0.1 (data pipeline)"


class FetchError(RuntimeError):
    """An upstream fetch did not return what the pipeline requires."""


def _session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


def reported_count(source: sources.ArcGisSource, session: requests.Session) -> int:
    """Ask the service how many records the layer holds."""
    response = session.get(
        f"{source.layer_url}/query",
        params={"where": "1=1", "returnCountOnly": "true", "f": "json"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    if "count" not in payload:
        raise FetchError(f"{source.key}: service returned no count: {payload}")
    return int(payload["count"])


def fetch_arcgis(source: sources.ArcGisSource, session: requests.Session) -> dict:
    """Fetch one layer as GeoJSON in EPSG:4326, asserting the feature count."""
    expected = reported_count(source, session)
    if expected != source.expected_count:
        raise FetchError(
            f"{source.key}: service reports {expected} records but the pipeline "
            f"expects {source.expected_count}. The upstream layer has been revised; "
            f"review the change before updating the expected count."
        )

    response = session.get(
        f"{source.layer_url}/query",
        params={
            "where": "1=1",
            "outFields": ",".join(source.out_fields),
            "outSR": "4326",
            "returnGeometry": "true",
            "f": "geoJSON",
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()

    features = payload.get("features")
    if features is None:
        raise FetchError(f"{source.key}: response has no features: {payload}")
    if len(features) != expected:
        raise FetchError(
            f"{source.key}: fetched {len(features)} features but the service "
            f"reports {expected}. The response was truncated or paged."
        )
    if any(f.get("geometry") is None for f in features):
        raise FetchError(f"{source.key}: response contains a feature with no geometry")

    missing = set(source.out_fields) - set(features[0].get("properties", {}))
    if missing:
        raise FetchError(f"{source.key}: response is missing fields {sorted(missing)}")

    return payload


def fetch_tiger(source: sources.TigerSource, force: bool = False) -> tuple[bool, int]:
    """Download the national CBSA zip, reusing a complete cached copy.

    Returns (downloaded, size_in_bytes).
    """
    target = RAW_DIR / source.raw_name
    session = _session()

    head = session.head(source.url, timeout=TIMEOUT, allow_redirects=True)
    head.raise_for_status()
    remote_size = int(head.headers.get("content-length", 0))

    if target.exists() and not force:
        local_size = target.stat().st_size
        if remote_size and local_size == remote_size:
            print(f"  cbsa: cached ({local_size:,} bytes), no download")
            return False, local_size
        print(
            f"  cbsa: cached copy is {local_size:,} bytes but remote is "
            f"{remote_size:,}; re-downloading"
        )

    print(f"  cbsa: downloading {remote_size:,} bytes")
    with session.get(source.url, timeout=TIMEOUT, stream=True) as response:
        response.raise_for_status()
        with open(target, "wb") as handle:
            for chunk in response.iter_content(chunk_size=1 << 16):
                handle.write(chunk)

    size = target.stat().st_size
    if remote_size and size != remote_size:
        target.unlink()
        raise FetchError(
            f"cbsa: download is {size:,} bytes but expected {remote_size:,}"
        )
    return True, size


def run_fetch(force: bool = False) -> int:
    ensure_dirs()
    session = _session()
    manifest: dict[str, dict] = {}

    print("Fetching MassGIS feature services")
    for source in sources.ARCGIS_SOURCES:
        target = RAW_DIR / source.raw_name
        if target.exists() and not force:
            cached = json.loads(target.read_text())
            print(
                f"  {source.key}: cached ({len(cached['features'])} features), "
                "no request"
            )
            payload = cached
        else:
            payload = fetch_arcgis(source, session)
            target.write_text(json.dumps(payload))
            print(f"  {source.key}: {len(payload['features'])} features")
        manifest[source.key] = {
            "title": source.title,
            "url": source.layer_url,
            "fetched": date.today().isoformat(),
            "source_count": len(payload["features"]),
        }

    print("Fetching Census TIGER CBSA archive")
    downloaded, size = fetch_tiger(sources.CBSA, force=force)
    manifest[sources.CBSA.key] = {
        "title": sources.CBSA.title,
        "url": sources.CBSA.url,
        "vintage": sources.CBSA.vintage,
        "fetched": date.today().isoformat(),
        "archive_bytes": size,
    }

    (RAW_DIR / "fetch_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"\nRaw cache: {RAW_DIR}")
    return 0
