"""Pure 91251A108 socket-screw dimensions; isolate mechanical cache inputs."""

from _socket_head_dimensions import SocketHeadScrew

PART_NO = "91251A108"
IN = 25.4


DIMS = SocketHeadScrew(
    part_no=PART_NO,
    major_dia=0.112 * IN,
    pitch=IN / 40.0,
    length=0.375 * IN,
    head_dia=0.183 * IN,
    head_h=0.112 * IN,
    socket_af=3.0 / 32.0 * IN,
    socket_depth=0.055 * IN,
)


# McMaster engineering drawing inspected 2026-10-19. Its hex drive is
# fractional, while the nominal thread diameter explicitly prints 0.1120 in.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260108/B4B87592/"
    "91251A108_Black-Oxide%20Alloy%20Steel%20Socket%20Head%20ScrewX.GIF"
)
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierLength", -DIMS.length, "vertical"),
    ("SupplierHeadHeight", DIMS.head_h, "vertical"),
    ("SupplierHeadDiameter", DIMS.head_dia, "horizontal"),
    ("SupplierThreadDiameter", DIMS.major_dia, "horizontal"),
    ("SupplierDriveWidth", DIMS.socket_af, "horizontal"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierLength": (DIMS.major_dia / 2.0, 0.0),
    "SupplierHeadHeight": (-DIMS.head_dia / 2.0, 0.0),
    "SupplierHeadDiameter": (-DIMS.head_dia / 2.0, 0.0),
    "SupplierThreadDiameter": (-DIMS.major_dia / 2.0, -DIMS.length / 2.0),
    "SupplierDriveWidth": (-DIMS.socket_af / 2.0, 0.0),
}
SUPPLIER_REFERENCE_PLANES = {
    "SupplierHeadDiameter": "Top",
    "SupplierDriveWidth": "Top",
}
SUPPLIER_REFERENCE_SIDES = {"SupplierThreadDiameter": "bottom"}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierLength": (3, "length", None, None),
    "SupplierHeadHeight": (3, "length", None, None),
    "SupplierHeadDiameter": (3, "diameter", None, None),
    "SupplierThreadDiameter": (4, "diameter", None, "4-40"),
    "SupplierDriveWidth": (0, "length", 32, None),
}
