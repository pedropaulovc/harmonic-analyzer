"""Purchased dimensions only for the captured-pivot cartridge (millimetres).

Primary pages read 2026-10-20; evidence: C:/temp/pivot-retention/hardware-sources.md.
No cartridge dimensions/imports belong here: the cartridge imports this provider.
Catalogue geometry is representative, not vendor-CAD replication or a load rating.
"""

from __future__ import annotations

from _socket_head_dimensions import SocketHeadScrew

INCH = 25.4
SOURCE_DATE = "2026-10-20"
SCREW_SKU = "NAS1352N4H12"
SCREW_SUPPLIER_SKU = "1216451"
SCREW_SOURCE_URL = "https://www.hardwarespecialty.com/Product/1216451"
SCREW_STANDARD_URL = "https://www.aaestore.com.au/media/specs/NAS1352.pdf"
SCREW_THREAD_SOURCE_URL = "https://www.engineeredpartsinc.com/wp-content/uploads/unified-external-screw-threads.pdf"
SCREW_MAJOR_DIA_MIN = 0.2419 * INCH
SCREW_MAJOR_DIA_MAX = 0.2500 * INCH
SCREW_MAJOR_DIA = SCREW_MAJOR_DIA_MAX
SCREW_LENGTH = 0.750 * INCH
SCREW_LENGTH_MIN = 0.720 * INCH
SCREW_HEAD_DIA_MIN = 0.365 * INCH
SCREW_HEAD_DIA_MAX = 0.375 * INCH
SCREW_HEAD_DIA = (SCREW_HEAD_DIA_MIN + SCREW_HEAD_DIA_MAX) / 2
SCREW_HEAD_HEIGHT_MIN = 0.244 * INCH
SCREW_HEAD_HEIGHT_MAX = 0.250 * INCH
SCREW_HEAD_HEIGHT = (SCREW_HEAD_HEIGHT_MIN + SCREW_HEAD_HEIGHT_MAX) / 2
SCREW_WIRE_HOLE_DIA_MIN = 0.044 * INCH
SCREW_WIRE_HOLE_DIA_MAX = 0.050 * INCH
SCREW_WIRE_HOLE_DIA = (SCREW_WIRE_HOLE_DIA_MIN + SCREW_WIRE_HOLE_DIA_MAX) / 2
SCREW_WIRE_FROM_TOP_MIN = 0.065 * INCH
SCREW_WIRE_FROM_TOP_MAX = 0.085 * INCH
SCREW_WIRE_FROM_TOP = (SCREW_WIRE_FROM_TOP_MIN + SCREW_WIRE_FROM_TOP_MAX) / 2
SCREW_WIRE_HEIGHT = SCREW_HEAD_HEIGHT - SCREW_WIRE_FROM_TOP
SCREW_WIRE_HOLE_ANGLES = (0.0, 60.0, 120.0, 180.0, 240.0, 300.0)
SCREW_DIMS = SocketHeadScrew(
    part_no=SCREW_SKU,
    major_dia=SCREW_MAJOR_DIA,
    pitch=INCH / 20,
    length=SCREW_LENGTH,
    head_dia=SCREW_HEAD_DIA,
    head_h=SCREW_HEAD_HEIGHT,
    socket_af=3 / 16 * INCH,
    socket_depth=0.120 * INCH,  # NAS1352 Table I minimum key engagement
)

CLEVIS_SKU = "CLPS6-0187-1250D"
CLEVIS_SOURCE_URL = "https://www.huyett.com/clps6-0187-1250d"
# The listing's rounded .188 nominal is NOT an acceptable manufactured OD.
CLEVIS_DIA_MIN = 0.181 * INCH
CLEVIS_DIA_MAX = 0.186 * INCH
CLEVIS_DIA = (CLEVIS_DIA_MIN + CLEVIS_DIA_MAX) / 2
CLEVIS_LENGTH = 1.250 * INCH
CLEVIS_LENGTH_MAX = 1.270 * INCH
CLEVIS_HEAD_DIA = 0.310 * INCH
CLEVIS_HEAD_DIA_MIN = 0.302 * INCH
CLEVIS_HEAD_DIA_MAX = 0.320 * INCH
CLEVIS_HEAD_HEIGHT = 0.061 * INCH
CLEVIS_HEAD_HEIGHT_MIN = 0.052 * INCH
CLEVIS_HEAD_HEIGHT_MAX = 0.070 * INCH
CLEVIS_HOLE_DIA = 0.094 * INCH
CLEVIS_HOLE_DIA_MIN = 0.088 * INCH
CLEVIS_HOLE_DIA_MAX = 0.103 * INCH
# Huyett diagram M ends at the NEAR edge of the hole, not its centre.
CLEVIS_EFFECTIVE_LENGTH = 1.109 * INCH
CLEVIS_HOLE_FROM_HEAD = CLEVIS_EFFECTIVE_LENGTH + CLEVIS_HOLE_DIA / 2

COTTER_SKU = "CP-062-0500"
COTTER_SOURCE_URL = "https://www.huyett.com/cp-062-0500"
COTTER_DIA_MIN = 0.056 * INCH
COTTER_DIA_MAX = 0.063 * INCH
COTTER_DIA = (COTTER_DIA_MIN + COTTER_DIA_MAX) / 2
COTTER_WIDTH_MIN = 0.044 * INCH
COTTER_WIDTH_MAX = 0.060 * INCH
COTTER_WIDTH = (COTTER_WIDTH_MIN + COTTER_WIDTH_MAX) / 2
COTTER_LENGTH = 0.500 * INCH
COTTER_LENGTH_MIN = 0.470 * INCH
COTTER_LENGTH_MAX = 0.530 * INCH
COTTER_HEAD_DIA_MIN = 0.120 * INCH
COTTER_PRONG_DIFFERENCE_MIN = 0.030 * INCH

WIRE_SKU = "05-02685"
WIRE_SOURCE_URL = "https://www.aircraftspruce.com/catalog/appages/safetywire.php"
WIRE_CATALOG_URL = "https://www.aircraftspruce.com/pdf/2027Individual/Cat270142.pdf"
WIRE_DIA = 0.032 * INCH
WIRE_MATERIAL = "302/304 stainless steel, soft temper, MS20995"
