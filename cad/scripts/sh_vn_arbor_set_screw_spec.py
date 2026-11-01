r"""Pure McMaster 91375A106 apex set-screw dimensions for CH and DT.

PURCHASED: #4-40 x 1/4 in alloy steel cup-tip set screw, black oxide,
Class 3A, Rockwell C45, 0.050 in hex drive (ASME B18.3 / ASTM F912).
The C45 cup bites the spotted steel arbor where an 18-8 (B80) cup would not.

One screw in each DT arbor pedestal's crown apex fixes the arbor after the
bank's end-play leaf is set (#743, Q3: "set screw located at apex of straps").
The same SKU, one per MHA-CH-08 ear, drops through the ear's arch apex onto
a flat on the rocker pivot shaft (user, 2026-10-10).

The native part has the shared Number MHA-SH-VN-54. These layout nominals
come from the vendor replica (diagnostics/diag_build_91375A106), without
importing its SolidWorks recipe or either parent's mechanical specs. The
thread-table major diameter is the existing fit nominal, not the replica's
more precise harvested diameter; test_ch_vn_arbor_set_screw keeps the shared
dimensions in step with that recipe.
"""

from __future__ import annotations

from _hole_spec import THREAD_MAJOR_MM

MM_PER_IN = 25.4

THREAD = "#4-40"
MAJOR_DIA = THREAD_MAJOR_MM[THREAD]  # 0.112 in, rounded thread-table nominal
LENGTH = 0.250 * MM_PER_IN  # nominal length, cup end to socket face
HEX_AF = 0.050 * MM_PER_IN
# The vendor's cup-end chamfer, 45 deg x one pitch: the plain point below the
# first full thread, which must span the arbor's running clearance.
POINT_LENGTH = MM_PER_IN / 40.0

if POINT_LENGTH >= LENGTH:
    raise AssertionError("set-screw point overruns its length")

# Supplier references use the replica's exact nominal, not the rounded fit
# table value above. They do not change the purchased solid or its placement.
REPLICA_MAJOR_DIA = 0.112 * MM_PER_IN
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260925/2DE2B046/"
    "91375A106_Alloy%20Steel%20Cup-Tip%20Set%20ScrewX.GIF"
)
# Final frame: cup end Y=0, socket face Y=LENGTH. Top is end-on.
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierLength", LENGTH, "vertical"),
    ("SupplierThreadDiameter", REPLICA_MAJOR_DIA, "horizontal"),
    ("SupplierDriveWidth", HEX_AF, "horizontal"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierLength": (REPLICA_MAJOR_DIA / 2.0, 0.0),
    "SupplierThreadDiameter": (-REPLICA_MAJOR_DIA / 2.0, 0.0),
    "SupplierDriveWidth": (-HEX_AF / 2.0, 0.0),
}
SUPPLIER_REFERENCE_PLANES = {
    "SupplierThreadDiameter": "Top",
    "SupplierDriveWidth": "Top",
}
SUPPLIER_REFERENCE_SIDES = {}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierLength": (2, "length", None, None),
    "SupplierThreadDiameter": (3, "diameter", None, "4-40"),
    "SupplierDriveWidth": (3, "length", None, "HEX SOCKET"),
}
