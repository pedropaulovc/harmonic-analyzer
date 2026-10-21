"""Purchased dimensions only for the captured-pivot cartridge (millimetres).

Primary pages read 2026-10-20; evidence: C:/temp/pivot-retention/hardware-sources.md.
No cartridge dimensions/imports belong here: the cartridge imports this provider.
Catalogue geometry is representative, not vendor-CAD replication or a load rating.
"""

from __future__ import annotations

from _socket_head_dimensions import SocketHeadScrew

INCH = 25.4
SOURCE_DATE = "2026-10-20"
SCREW_SKU = "NAS1352N5H12"
SCREW_SUPPLIER = "CBS Fasteners"
SCREW_SUPPLIER_SKU = SCREW_SKU
SCREW_SUPPLIER_DESCRIPTION = "5/16-18 X 3/4 SHC A286 DRLD"
SCREW_SOURCE_URL = "https://cbsfasteners.com/nas-fastener-inventory/"
SCREW_STANDARD_URL = "https://www.aaestore.com.au/media/specs/NAS1352.pdf"
SCREW_ASME_SOURCE_URL = "https://www.finesz.com/pic/ASME%20B18.3.pdf"
SCREW_THREAD_SOURCE_URL = "https://www.engineeredpartsinc.com/wp-content/uploads/unified-external-screw-threads.pdf"
# UNRC-3A threaded major limits; NAS Table I D minimum is smooth-body only.
SCREW_MAJOR_DIA_MIN = 0.3038 * INCH
SCREW_MAJOR_DIA_MAX = 0.3125 * INCH
SCREW_MAJOR_DIA = SCREW_MAJOR_DIA_MAX
SCREW_LENGTH = 0.750 * INCH
SCREW_LENGTH_MIN = 0.720 * INCH
SCREW_HEAD_DIA_MIN = 0.457 * INCH
SCREW_HEAD_DIA_MAX = 0.469 * INCH
SCREW_HEAD_DIA = (SCREW_HEAD_DIA_MIN + SCREW_HEAD_DIA_MAX) / 2
SCREW_HEAD_HEIGHT_MIN = 0.306 * INCH
SCREW_HEAD_HEIGHT_MAX = 0.312 * INCH
SCREW_HEAD_HEIGHT = (SCREW_HEAD_HEIGHT_MIN + SCREW_HEAD_HEIGHT_MAX) / 2
# NAS Table I K overrides generic ASME K. This is a flat-bearing footprint,
# not a uniform-contact/pressure guarantee: ASME permits a one-degree face.
SCREW_HEAD_EDGE_BREAK_MAX = 0.008 * INCH
SCREW_HEAD_BEARING_DIA_MIN = SCREW_HEAD_DIA_MIN - 2 * SCREW_HEAD_EDGE_BREAK_MAX
SCREW_HEAD_RUNOUT_FIM_MAX = max(0.02 * SCREW_MAJOR_DIA_MAX, 0.006 * INCH)
SCREW_HEAD_ECCENTRICITY_MAX = SCREW_HEAD_RUNOUT_FIM_MAX / 2
SCREW_BEARING_ANGLE_MAX_DEGREES = 1.0
# ASME B18.3 Table 2 envelope, applicable via NAS1352 sheet 2 note (g).
# Neither this fillet envelope nor body diameter locates a full thread crest.
SCREW_FILLET_JUNCTION_DIA_MIN = 0.329 * INCH
SCREW_FILLET_JUNCTION_DIA_MAX = 0.347 * INCH
SCREW_FILLET_LENGTH_MAX = 0.029 * INCH
SCREW_SOCKET_AF = 0.250 * INCH
SCREW_SOCKET_DEPTH_MIN = 0.151 * INCH  # NAS Table I minimum key engagement
SCREW_WIRE_HOLE_DIA_MIN = 0.044 * INCH
SCREW_WIRE_HOLE_DIA_MAX = 0.050 * INCH
SCREW_WIRE_HOLE_DIA = (SCREW_WIRE_HOLE_DIA_MIN + SCREW_WIRE_HOLE_DIA_MAX) / 2
SCREW_WIRE_FROM_TOP_MIN = 0.084 * INCH
SCREW_WIRE_FROM_TOP_MAX = 0.104 * INCH
SCREW_WIRE_FROM_TOP = (SCREW_WIRE_FROM_TOP_MIN + SCREW_WIRE_FROM_TOP_MAX) / 2
SCREW_WIRE_HEIGHT = SCREW_HEAD_HEIGHT - SCREW_WIRE_FROM_TOP
SCREW_WIRE_HEIGHT_MIN = SCREW_HEAD_HEIGHT_MIN - SCREW_WIRE_FROM_TOP_MAX
SCREW_WIRE_HEIGHT_MAX = SCREW_HEAD_HEIGHT_MAX - SCREW_WIRE_FROM_TOP_MIN
# A short screw is threaded as close to the head as practicable (NAS note c).
# The existing fully-threaded native representation supplies no crest-distance
# or complete-engagement guarantee; those require receiving/joint inspection.
SCREW_WIRE_HOLE_ANGLES = (0.0, 60.0, 120.0, 180.0, 240.0, 300.0)
SCREW_DIMS = SocketHeadScrew(
    part_no=SCREW_SKU,
    major_dia=SCREW_MAJOR_DIA,
    pitch=INCH / 18,
    length=SCREW_LENGTH,
    head_dia=SCREW_HEAD_DIA,
    head_h=SCREW_HEAD_HEIGHT,
    socket_af=SCREW_SOCKET_AF,
    socket_depth=SCREW_SOCKET_DEPTH_MIN,
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
