r"""Lever-wire dimensional contract -- the single source of truth shared by the
part build (``build_lever_wire.py``) and its manufacturing drawing
(``draw_lever_wire.py``).

PURE DATA, no SolidWorks/COM imports.  ``build_lever_wire`` imports this contract
to stamp the print notes, and the magnifier assembly imports the wire's COMPUTED
endpoints (``WIRE_START``/``WIRE_END``/``WIRE_LEN``) from ``build_lever_wire`` --
so, unlike the four nominal-coupled magnifier parts, the wire keeps NO ``_geom``
split (its assembly coupling is an endpoint SOLVER living in the build, not a raw
nominal).  The only residual cost is that editing THESE print notes refreshes the
magnifier assembly -- rare and cheap; a geom split would have to relocate the
whole endpoint solver, which is not worth the churn.  Flagged, accepted.

The wire is a Ø0.8 drawn-steel cylinder ~363 long -- a thin silhouette with no
flat face, no end-face big enough to pick and no selectable silhouette edge, so
NOTHING is a marked dimension; the diameter and straight rest-run length ride the
notes.  The rest-run length is COMPUTED between the two solved endpoints, but it
is NOT a developed cut length: the source model deliberately omits both end
terminations and the hub wrap, so their development allowance is unknown.
"""

from __future__ import annotations

# mirror of build_lever_wire.WIRE_DIA (the offline test asserts equality); a bare
# constant keeps this module import-pure (no COM), while the build stays the sole
# source of the endpoint solver + the derived cut length.
WIRE_DIA = 0.8

# Note-based: the un-pickable Ø0.8 wire carries no marked model dimension, so the
# marked set is empty and the drawing keeps nothing (the lockstep test asserts
# union(marks) == union(keeps) == {}).
DRAWING_DIMENSIONS: dict[str, set[str]] = {}

# True free-text instructions only; the build stamps these and APPENDS the
# computed straight-run line, then the drawing displays only the $PRPSHEET link.
DRAWING_NOTES = "\n".join(
    (
        "Ø0.8 WIRE, ONE PIECE.",
        "THIS SHEET DEFINES THE STRAIGHT REST RUN ONLY.",
        "FORMED HOOK, HUB WRAP, AND DEVELOPED CUT LENGTH ARE NOT DEFINED BY",
        "THE SOURCE MODEL. DO NOT RELEASE UNTIL THOSE DETAILS ARE SPECIFIED.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:5"
