r"""Lever-wire dimensional contract -- the single source of truth shared by the
part build (``build_vn_lever_wire.py``) and its manufacturing drawing
(``draw_vn_lever_wire.py``).

PURE DATA, no SolidWorks/COM imports.  ``build_vn_lever_wire`` imports this contract
to stamp the print notes; the wire's COMPUTED endpoints/yoke
(``WIRE_START``/``WIRE_END``/``WIRE_LEN``/``YOKE_POINT``) live in the
drawing-free ``vn_lever_wire_geom`` module, which the magnifier assembly and the
magnifying wheel import DIRECTLY -- so editing THESE print notes rebuilds only
the lever-wire part + sheet, never the wheel or the assembly.  (The wire
originally kept no geom split; codex #360 showed the note text leaking into
both closures through the ``build_vn_lever_wire`` import chain, so the solver
moved wholesale into ``vn_lever_wire_geom``.)

The wire is purchased McMaster-Carr 9666K56 music wire (0.031 in, modelled at
its Ø0.8 design nominal inside the catalogue band), cut from the coil: a ~353
long thin silhouette with no flat face, no end-face big enough to pick and no
selectable silhouette edge, so NOTHING is a marked dimension; the SKU and the
straight rest-run length ride the notes.  The rest-run length is COMPUTED between
the two solved endpoints, but it is NOT a cut length: the hook and drum wrap are
formed, and the wire trimmed, at assembly, so no developed length is needed.
"""

from __future__ import annotations

from _mcmaster_9666k56 import SKU
from vn_lever_wire_geom import WIRE_DIA  # noqa: F401 (re-export, import-pure)

# Note-based: the un-pickable Ø0.8 wire carries no marked model dimension, so the
# marked set is empty and the drawing keeps nothing (the lockstep test asserts
# union(marks) == union(keeps) == {}).
DRAWING_DIMENSIONS: dict[str, set[str]] = {}

# True free-text instructions only; the build stamps these and APPENDS the
# computed straight-run line, then the drawing displays only the $PRPSHEET link.
DRAWING_NOTES = "\n".join(
    (
        f"PURCHASED WIRE: McMASTER-CARR {SKU}, Ø0.031 IN, CUT FROM COIL.",
        "THIS SHEET SHOWS THE STRAIGHT REST RUN ONLY.",
        "CUT OVERLENGTH; HOOK, DRUM WRAP AND TRIM AT ASSEMBLY.",
    )
)
FRONT_VIEW_NOTE = "FRONT VIEW SCALE 1:5"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:5"
