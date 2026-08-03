r"""Lever-wire dimensional contract -- the single source of truth shared by the
part build (``build_lever_wire.py``) and its manufacturing drawing
(``draw_lever_wire.py``).

PURE DATA, no SolidWorks/COM imports.  ``build_lever_wire`` imports this contract
to stamp the print notes; the wire's COMPUTED endpoints/yoke
(``WIRE_START``/``WIRE_END``/``WIRE_LEN``/``YOKE_POINT``) live in the
drawing-free ``lever_wire_geom`` module, which the magnifier assembly and the
magnifying wheel import DIRECTLY -- so editing THESE print notes rebuilds only
the lever-wire part + sheet, never the wheel or the assembly.  (The wire
originally kept no geom split; codex #360 showed the note text leaking into
both closures through the ``build_lever_wire`` import chain, so the solver
moved wholesale into ``lever_wire_geom``.)

The wire is a Ø0.8 drawn-steel cylinder ~353 long -- a thin silhouette with no
flat face, no end-face big enough to pick and no selectable silhouette edge, so
NOTHING is a marked dimension; the diameter and straight rest-run length ride the
notes.  The rest-run length is COMPUTED between the two solved endpoints, but it
is NOT a developed cut length: the source model deliberately omits both end
terminations and the hub wrap, so their development allowance is unknown.
"""

from __future__ import annotations

from lever_wire_geom import WIRE_DIA  # noqa: F401 (re-export, import-pure)

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
FRONT_VIEW_NOTE = "FRONT VIEW SCALE 1:5"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:5"
