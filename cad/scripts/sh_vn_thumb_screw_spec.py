"""Pure McMaster 91882A221 dimensions for its recipe and assembly placement.

Separate from the other thumb-screw SKU and COM recipe to limit cache blast radius.

MHA-SH-VN-55 serves MG and MS with this steel raised knurled-head #4-40 x 7/16 screw.
The native thumb-screw author and assembly placement read the same THUMB_SPEC.

Production part frame (build_sh_vn_thumb_screw): the outer head face lies at X=0,
the axis runs along +X, the collar bearing face is at X=HEAD_STACK_LEN and the
thread tip at X=OVERALL_LEN.
"""

from __future__ import annotations

SKU = "91882A221"
THREAD = "#4-40"

THUMB_SPEC = dict(
    major_r=2.8448 / 2.0,
    pitch=0.635,
    length=11.1125,
    collar_r=6.35 / 2.0,
    collar_h=2.38125,
    head_r=9.525 / 2.0,
    head_h=2.38125,
)

PITCH = THUMB_SPEC["pitch"]
COLLAR_DIA = 2.0 * THUMB_SPEC["collar_r"]
COLLAR_H = THUMB_SPEC["collar_h"]
HEAD_DIA = 2.0 * THUMB_SPEC["head_r"]
HEAD_H = THUMB_SPEC["head_h"]
HEAD_STACK_LEN = COLLAR_H + HEAD_H
SHANK_DIA = 2.0 * THUMB_SPEC["major_r"]
SHANK_LEN = THUMB_SPEC["length"]
OVERALL_LEN = HEAD_STACK_LEN + SHANK_LEN

SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260707/5003FE53/"
    "91882A221_Steel%20Raised%20Knurled-Head%20Thumb%20ScrewX.GIF"
)
# Supplier .438/.094 are rounded display spellings, never replacement values:
# thread length remains exactly 7/16 inch; both heights remain 3/32 inch.
SUPPLIER_UNITS = "in"
SUPPLIER_PRECISION = {
    "thread_length": 3,
    "head_height": 3,
    "collar_height": 3,
    "head_diameter": 3,
    "collar_diameter": 2,
    "thread_diameter": 3,
}
SUPPLIER_THREAD = "4-40"

# A knurled/chamfered rim is not the nominal envelope diameter. Import these
# construction-only model references; axial spans attach to physical rims.
DIAMETER_REFERENCES = (
    ("SupplierHeadDiameter", HEAD_DIA, "vertical"),
    ("SupplierCollarDiameter", COLLAR_DIA, "vertical"),
    ("SupplierThreadDiameter", SHANK_DIA, "vertical"),
)
DIAMETER_REFERENCE_STARTS = {
    "SupplierHeadDiameter": (HEAD_H / 2.0, -HEAD_DIA / 2.0),
    "SupplierCollarDiameter": (HEAD_H + COLLAR_H / 2.0, -COLLAR_DIA / 2.0),
    "SupplierThreadDiameter": (HEAD_STACK_LEN + SHANK_LEN / 2.0, -SHANK_DIA / 2.0),
}
