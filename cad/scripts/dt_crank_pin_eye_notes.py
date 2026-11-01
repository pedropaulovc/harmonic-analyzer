r"""Keeper-chain anchor eye (MHA-DT-28) drawing-only data: the marked-dimension
and precision contract and the manufacturing notes the part build stamps into
the SLDPRT.

Kept out of ``dt_crank_pin_eye_spec`` (the ``ch_rod_pivot_pin_notes`` split):
the drive train and the keeper chain import the spec, so prose there would
re-key them on every drawing edit. Imported ONLY by
``build_dt_crank_pin_eye``, ``draw_dt_crank_pin_eye`` and the offline tests.

The eye is ``visual_noncritical``: on its decimal-inch sheet (#290) the loop and
tail take the title block's .XX band (drawing-guidelines.md rule 3). The loop's inside
diameter and the tail's length from the loop centre live on the blanked
``EyeReference`` sketch in the eye's own plane, because a torus has no edge to
dimension (drawing-simplicity-policy.md: a value no feature dimension carries
is modelled by a hidden reference sketch). The wire is purchased stock, so it
prints as REFERENCE on the tail's end, where the top view sees it end-on.

drawing-guidelines.md rule 7 (notes: few, flagged, never a method): the loop
is closed on the tail, and the tail is clamped flat under the anchor screw's
head; the loop's callout names the chain that threads it. The title block
owns the brass wire.
"""

from __future__ import annotations

import dt_crank_pin_eye_spec as eye

# The loop's inside diameter, on the wire's inner edge, and its places: the
# spec owns both, because the keeper chain asserts its bead passes the loop's
# smallest printed size.
LOOP_ID = eye.LOOP_ID

# --- Drawing contract (drawing-simplicity-policy.md `How the repository implements the guidelines`: the PART owns places and bands). ---
# ``WireProfile`` (Top plane) is the loop's wire circle, at the origin where
# the tail's end face sees it end-on in the top view. ``EyeReference`` (Right
# plane, the eye's own plane) carries the loop and the tail in the side view.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "WireProfile": {"WireDia"},
    "EyeReference": {"LoopID", "TailLen"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "WireProfile": {"WireDia": 3},
    "EyeReference": {"LoopID": eye.LOOP_ID_PLACES, "TailLen": 2},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: decimals
    for dimensions in DRAWING_PRECISION.values()
    for name, decimals in dimensions.items()
}
REFERENCE_DIMENSIONS = frozenset({"WireDia"})
# The wire is bought stock: an untoleranced reference whose supplier tolerance
# governs (owner rule; #290 reviews asked for a printed band).
DIMENSION_CALLOUTS: dict[str, str] = {
    "WireDia": "WIRE AS SUPPLIED;\nSUPPLIER TOLERANCE",
    "LoopID": "MHA-DT-VN-65 BEAD CHAIN PASSES FREELY",
}
if {name for names in DRAWING_DIMENSIONS.values() for name in names} != set(
    DRAWING_PRECISION_BY_NAME
):
    raise AssertionError("every marked eye dimension needs authored places")
if not REFERENCE_DIMENSIONS <= set(DRAWING_PRECISION_BY_NAME):
    raise AssertionError("every reference eye dimension must be marked")

DRAWING_NOTES = "\n".join(
    (
        "1. LOOP CLOSED ON THE TAIL; LOOP AND TAIL IN ONE PLANE.",
        "2. TAIL STRAIGHT AND FLAT; CLAMPS UNDER THE MHA-SH-VN-51 HEAD"
        " ON THE MHA-DT-06 ARM.",
    )
)
