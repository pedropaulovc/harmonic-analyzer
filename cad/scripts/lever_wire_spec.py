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
notes.  The rest-run length is COMPUTED between the two solved endpoints (the
build appends it as the third note line), but it is NOT a developed cut length:
the source model omits both end terminations and the hub wrap, so the maker
forms those at assembly and cuts long.
"""

from __future__ import annotations

from lever_wire_geom import WIRE_DIA  # noqa: F401 (re-export, import-pure)

# Note-based: the un-pickable Ø0.8 wire carries no marked model dimension, so the
# marked set is empty and the drawing keeps nothing (the lockstep test asserts
# union(marks) == union(keeps) == {}).
DRAWING_DIMENSIONS: dict[str, set[str]] = {}

# Wire data only (policy rule 6): diameter, and the forming the print cannot
# dimension.  The build APPENDS the computed straight rest-run line, so the
# stamped note is three lines.
DRAWING_NOTES = "\n".join(
    (
        f"Ø{WIRE_DIA:g} WIRE, ONE PIECE.",
        "END HOOK AND HUB WRAP FORMED AT ASSEMBLY; CUT LONG AND TRIM.",
    )
)
FRONT_VIEW_NOTE = "FRONT VIEW SCALE 1:5"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:5"
