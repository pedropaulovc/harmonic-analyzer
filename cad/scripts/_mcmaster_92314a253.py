"""Pure catalogue and UNC-2A thread-class inputs; no diagnostic imports."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HexScrewDimensions:
    part_no: str
    major_dia: float
    pitch: float
    length: float
    head_af: float
    head_h: float


CATALOG_URL = "https://www.mcmaster.com/92314A253/"
CATALOG_CHECKED_DATE = "2026-10-13"
CATALOG_STANDARD = None  # Specifications Met is omitted for this SKU.
CATALOG_DIMENSIONAL_TOLERANCES = None  # Not published in the live table/PDF.
CATALOG_THREAD = "#10-24 UNC-2A"
CATALOG_THREADING = "Fully Threaded"
CATALOG_TIP = "Flat"
CATALOG_TENSILE_PSI = 80_000
CATALOG_MATERIAL = "18-8 Stainless Steel"

# External #10-24 UNC-2A major limits from ASME B1.1, not added supplier
# head/length tolerances. DIMS.major_dia remains the nominal CAD depiction.
THREAD_MAJOR_SOURCE = (
    "ASME B1.1-1989 (R2001), external #10-24 class 2A: "
    "major diameter MIN 0.1818 in / MAX 0.1890 in; "
    "https://www.engineersedge.com/screw_threads_chart.htm"
)
THREAD_MAJOR_MIN = 0.1818 * 25.4
THREAD_MAJOR_MAX = 0.1890 * 25.4

DIMS = HexScrewDimensions(
    part_no="92314A253",
    major_dia=4.826,
    pitch=25.4 / 24,
    length=50.8,
    head_af=7.9375,
    head_h=3.175,
)
