r"""Crank-pin keeper ring (MHA-DT-27) drawing-only data: the marked-dimension
and precision contract and the manufacturing notes the part build stamps into
the SLDPRT.

Kept out of ``dt_crank_pin_ring_spec`` (the ``ch_rod_pivot_pin_notes``
split): the drive train, the keeper chain and the interference contract
import the spec, so prose there would re-key them on every drawing edit.
Imported ONLY by ``build_dt_crank_pin_ring``, ``draw_dt_crank_pin_ring`` and
the offline tests.

The ring is ``visual_noncritical``: on its decimal-inch sheet (#290) the inside
diameter takes the title block's .XX band (drawing-guidelines.md rule 3). The ring's inside
diameter is the one controlling size, on the blanked ``RingReference`` sketch
in the ring's own plane, because a torus has no edge to dimension
(drawing-simplicity-policy.md: a value no feature dimension carries is
modelled by a hidden reference sketch). The wire is purchased stock, so it
prints as REFERENCE.

drawing-guidelines.md rule 7 (notes: few, flagged, never a method): owner
ruling 2026-11-08 (D6) closes the ring with pliers, not solder, once it is
threaded through the taper pin's cross-hole and the keeper chain's far link,
since a closed ring passes neither; the note states that and the butt gap's
band, which no model dimension carries. The title block owns the brass wire.
"""

from __future__ import annotations

import dt_crank_pin_ring_spec as ring

# The ring's inside diameter, on the wire's inner edge, and its places: the
# spec owns both, because it asserts the smallest printed ring still threads
# the taper pin's cross-hole.
RING_ID = ring.RING_ID

# ``WireProfile`` (Front plane) is the revolve's wire circle: the front view,
# where the ring is edge-on, prints it. ``RingReference`` (Top plane) carries
# the inside diameter in the top view, where the ring reads at true shape.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "WireProfile": {"WireDia"},
    "RingReference": {"RingID"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "WireProfile": {"WireDia": 3},
    "RingReference": {"RingID": ring.RING_ID_PLACES},
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
}
if {name for names in DRAWING_DIMENSIONS.values() for name in names} != set(
    DRAWING_PRECISION_BY_NAME
):
    raise AssertionError("every marked ring dimension needs authored places")
if not REFERENCE_DIMENSIONS <= set(DRAWING_PRECISION_BY_NAME):
    raise AssertionError("every reference ring dimension must be marked")
# The gap's band in the sheet's inch: closed (0) up to its upper limit.
if ring.BUTT_GAP_BAND[0] != 0.0:
    raise AssertionError("the butt-gap note prints a band from closed")
_GAP_MAX_IN = f"{ring.BUTT_GAP_BAND[1] / 25.4:.3f}".removeprefix("0")
DRAWING_NOTES = "\n".join(
    (
        "1. THREAD THROUGH THE MHA-DT-09 CROSS-HOLE AND MHA-DT-VN-65 FAR LINK.",
        f"2. CLOSE WITH PLIERS; BUTT GAP 0-{_GAP_MAX_IN}.",
    )
)
