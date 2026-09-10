"""Upstream source definitions.

Each MassGIS layer is a hosted ArcGIS feature service. Every one of them
reports maxRecordCount 2000 and supports f=geoJSON, so a layer is one
unpaged request. The expected counts are asserted during the fetch so an
upstream revision that changes the population fails loudly.
"""

from dataclasses import dataclass, field

MASSGIS_HOST = "https://services1.arcgis.com/hGdibHYSPO59RG1h/arcgis/rest/services"


@dataclass(frozen=True)
class ArcGisSource:
    """A single layer of a hosted ArcGIS feature service."""

    key: str
    service: str
    layer: int
    title: str
    expected_count: int
    out_fields: tuple[str, ...]

    @property
    def layer_url(self) -> str:
        return f"{MASSGIS_HOST}/{self.service}/FeatureServer/{self.layer}"

    @property
    def raw_name(self) -> str:
        return f"{self.key}.geojson"


@dataclass(frozen=True)
class TigerSource:
    """The national CBSA shapefile, offered only as a zip archive."""

    key: str
    url: str
    title: str
    vintage: str
    raw_name: str = field(default="tl_2025_us_cbsa.zip")


COLLEGES = ArcGisSource(
    key="colleges",
    service="Colleges_and_Universities",
    layer=0,
    title="MassGIS Colleges and Universities",
    expected_count=206,
    out_fields=(
        "COLLEGE",
        "CAMPUS",
        "ADDRESS",
        "CITY",
        "ZIPCODE",
        "GEOG_TOWN",
        "MAIN_TEL",
        "URL",
        "NCES_ID",
        "NCES_TYPE",
        "TYPE",
        "CATEGORY",
        "DEGREEOFFR",
        "AWARDSOFFR",
        "LARGEPROG",
        "CAMPUSSETT",
        "CAMPUSHOUS",
    ),
)

COUNTIES = ArcGisSource(
    key="counties",
    service="Massachusetts_Counties_with_Generalized_Coastline",
    layer=1,
    title="MassGIS Massachusetts Counties with Generalized Coastline",
    expected_count=14,
    out_fields=("COUNTY", "FIPS_STCO"),
)

MUNICIPALITIES = ArcGisSource(
    key="municipalities",
    service="TownSurveyGenCoast_gdb",
    layer=1,
    title="MassGIS Massachusetts Municipalities with Generalized Coast",
    expected_count=351,
    out_fields=("TOWN", "TOWN_ID", "TYPE", "COUNTY", "FIPS_STCO"),
)

CBSA = TigerSource(
    key="cbsa",
    url="https://www2.census.gov/geo/tiger/TIGER2025/CBSA/tl_2025_us_cbsa.zip",
    title="Census TIGER/Line 2025 Core Based Statistical Areas",
    vintage="TIGER2025",
)

ARCGIS_SOURCES = (COLLEGES, COUNTIES, MUNICIPALITIES)

MA_STATE_FIPS = "25"
