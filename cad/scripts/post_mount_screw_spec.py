r"""Pure-data contract shared by the MHA-142 post mount screw part and drawing.

MHA-142 is MSC 40923898 (1/4-20 x 3-1/2 slotted fillister, U37c) cut to
length: a MODIFIED purchased part.  Its head seats on the MHA-016
counterbore floor and the shank threads through the MHA-091 plate, which
swings over the base, so the cut end must never stand proud of the plate's
underside.  The cut length is therefore a real, model-owned dimension on the
sheet (policy rule 2), not a number in an installation note (rule 6, Main's
eye pass of warm-c486).  Across the printed post and plate bands no single
length both stays flush and keeps the engagement minimum (U27 check below),
so the length prints as a REFERENCE and each screw is cut to its own hole at
assembly.

The engagement this leaves is the named rule-12 exception in
``cad/docs/drawing-simplicity-policy.md``; it is held here as a model
assert, not printed on the part sheet.
"""

from __future__ import annotations

import _config
import cone_pivot_post_spec as post
import cone_swing_platform_spec as platform
from diagnostics.diag_mcmaster_fillister import FILLISTER_SIZES

SKU = "40923898"
THREAD_DIA_MM, CUT_LENGTH_MM, _HEAD_H, _HEAD_DIA, _PITCH = FILLISTER_SIZES[SKU]

# Head seated on the MHA-016 counterbore floor: the under-head face to the
# plate's top face, at the model's nominal post.
GRIP_MM = post.BLOCK_HEIGHT - post.ATTACHMENT_CBORE_DEPTH
# The longest cut whose end is flush with the MHA-091 underside.
FLUSH_LENGTH_MM = GRIP_MM + platform.PLATE_THICKNESS

# Model-owned drawing controls: one hidden reference sketch whose single
# driving dimension IS the cut length, under-head face to cut end.
CUT_LENGTH_SKETCH = "CutLengthReference"
CUT_LENGTH_DIMENSION = "CutLength"
DRAWING_DIMENSIONS: dict[str, set[str]] = {CUT_LENGTH_SKETCH: {CUT_LENGTH_DIMENSION}}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    CUT_LENGTH_SKETCH: {CUT_LENGTH_DIMENSION: 1}
}
DRAWING_PRECISION_BY_NAME = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
REFERENCE_SKETCHES = (CUT_LENGTH_SKETCH,)

# --- U27: can one fixed cut length serve every in-band post and plate? ---
# The printed bands, as the shop reads them off the title block: the post's
# overall height is a .X dimension, its counterbore depth a .XX callout, and
# the plate is 1/4 flat bar as supplied (U41) at its mill tolerance.
_GENERAL_1PL_MM = float(str(_config.title_block("linear_1pl")["display"]).lstrip("±"))
_GENERAL_2PL_MM = float(str(_config.title_block("linear_2pl")["display"]).lstrip("±"))
_POST_HEIGHT_PRINTED = round(post.BLOCK_HEIGHT, 1)
_CBORE_DEPTH_PRINTED = round(post.ATTACHMENT_CBORE_DEPTH, 2)
# U41: 1/4 plate as supplied.  Integ carries the same mill band as
# cone_swing_platform_spec.PLATE_STOCK_BAND; this branch predates it.
PLATE_STOCK_BAND_MM = 0.13
# Title block: REMOVE BURRS AND BREAK SHARP EDGES R0.25 OR CHAMFER 0.25 MAX.
# Two breaks eat thread: the tap's entry at the plate top and the screw's
# chamfered cut end (the cut-end chamfer carries no size, so the title block
# limits it).
EDGE_BREAK_MAX_MM = float(_config.title_block("edge_break")["chamfer_max_mm"])
ENGAGEMENT_BREAKS_MM = 2.0 * EDGE_BREAK_MAX_MM

# Counterbore floor above PlateTop (the post foot seats on it), both ends.
FLOOR_LOW_MM = (_POST_HEIGHT_PRINTED - _GENERAL_1PL_MM) - (
    _CBORE_DEPTH_PRINTED + _GENERAL_2PL_MM
)
FLOOR_HIGH_MM = (_POST_HEIGHT_PRINTED + _GENERAL_1PL_MM) - (
    _CBORE_DEPTH_PRINTED - _GENERAL_2PL_MM
)
PLATE_THIN_MM = platform.PLATE_THICKNESS - PLATE_STOCK_BAND_MM
PLATE_THICK_MM = platform.PLATE_THICKNESS + PLATE_STOCK_BAND_MM

# The named rule-12 exception (User, U37c/U41): 0.90D minimum engagement.
MIN_ENGAGEMENT_DIAMETERS = 0.90
MIN_ENGAGEMENT_MM = MIN_ENGAGEMENT_DIAMETERS * THREAD_DIA_MM
# Corner 1, never proud: lowest floor on the thinnest plate.  A fixed length
# must not exceed this.
FIXED_LENGTH_FLUSH_MAX_MM = FLOOR_LOW_MM + PLATE_THIN_MM
# Corner 2, enough thread: highest floor, thickest plate.  A fixed length
# must reach at least this, after both edge breaks.  The thick plate does not
# cap it: cut flush there, the plate still holds the minimum.
FIXED_LENGTH_ENGAGEMENT_MIN_MM = FLOOR_HIGH_MM + MIN_ENGAGEMENT_MM + ENGAGEMENT_BREAKS_MM
if FIXED_LENGTH_ENGAGEMENT_MIN_MM > FLOOR_HIGH_MM + PLATE_THICK_MM:
    raise ValueError("the thick plate cannot hold 0.90D even when cut flush")
# No single length satisfies both corners (84.89 vs 87.51 at the current
# bands), so the shop cannot cut to a print band: each screw is cut to its
# own hole at assembly (MHA-A03), and the sheet prints the modelled length as
# a REFERENCE dimension with no band.  If the bands ever tighten enough for a
# fixed length to exist, this raises and the sheet should carry that band.
FIXED_CUT_LENGTH_EXISTS = FIXED_LENGTH_ENGAGEMENT_MIN_MM <= FIXED_LENGTH_FLUSH_MAX_MM
if FIXED_CUT_LENGTH_EXISTS:
    raise ValueError(
        "a fixed MHA-142 cut length now fits both corners "
        f"({FIXED_LENGTH_ENGAGEMENT_MIN_MM:.2f}..{FIXED_LENGTH_FLUSH_MAX_MM:.2f}): "
        "print it with its band instead of a reference length"
    )

# The fit-to-hole allowance (MHA-A03): each screw is cut flush to this much
# short of its own MHA-091 underside, never proud.  The one copy: integ's
# platform engagement stack and drive-train assembly step import it.
POST_SCREW_CUT_TO_FIT_SHORT = 0.3

# The model as built, on the nominal chain: the reference length never
# stands proud, and still holds the exception's minimum.
if CUT_LENGTH_MM > FLUSH_LENGTH_MM:
    raise ValueError(
        f"MHA-142 modelled length {CUT_LENGTH_MM} stands proud of the nominal "
        f"MHA-091 underside ({FLUSH_LENGTH_MM:.2f})"
    )
ENGAGEMENT_NOMINAL_MM = CUT_LENGTH_MM - GRIP_MM
if ENGAGEMENT_NOMINAL_MM < MIN_ENGAGEMENT_MM:
    raise ValueError(
        f"MHA-142 nominal engagement {ENGAGEMENT_NOMINAL_MM:.2f} is under "
        f"{MIN_ENGAGEMENT_DIAMETERS:.2f}D"
    )

# Rule 6: no dimension, no tolerance, no installation sequence.  The cut
# length is the reference dimension above; cutting each screw to its hole is
# an MHA-A03 step.
MANUFACTURING_NOTES = (
    "CHAMFER CUT END.\nUNDIMENSIONED PURCHASED GEOMETRY IS REFERENCE."
)
