r"""Lever-wire dimensional contract -- the single source of truth shared by the
part build (``build_lever_wire.py``) and its manufacturing drawing
(``draw_lever_wire.py``).

PURE DATA, no SolidWorks/COM imports.  ``build_lever_wire`` imports this contract
to mark the print's two model dimensions, band the wire diameter and stamp the
print notes; the wire's COMPUTED endpoints/yoke
(``WIRE_START``/``WIRE_END``/``WIRE_LEN``/``YOKE_POINT``) live in the
drawing-free ``lever_wire_geom`` module, which the magnifier assembly and the
magnifying wheel import DIRECTLY -- so editing THESE print notes rebuilds only
the lever-wire part + sheet, never the wheel or the assembly.  (The wire
originally kept no geom split; codex #360 showed the note text leaking into
both closures through the ``build_lever_wire`` import chain, so the solver
moved wholesale into ``lever_wire_geom``.)

The wire is a Ø0.8 drawn-steel cylinder ~353 long.  Two model dimensions are
marked: the profile circle's ``WireDiaDim`` (read on a 10:1 END view -- at the
1:5 sheet scale the wire is a hairline -- carrying the bought-wire band as a
native model tolerance, since neither title-block band fits a 0.8 wire) and the
extrusion's ``Depth`` (the straight rest-run, hub end to hook end, shown on the
front view as a REFERENCE dimension: it is NOT a cut length -- the source model
omits both end terminations and the hub wrap, so the maker forms those at
assembly and cuts long).
"""

from __future__ import annotations

from lever_wire_geom import WIRE_DIA  # noqa: F401 (re-export, import-pure)

# The bought music wire's diameter band, a caliper-checkable limit (ASTM A228
# holds far tighter).  Applied to WireDiaDim in the build (policy rule 2) so
# the end view prints it natively; the title block's .X/.XX bands (+/-0.8,
# +/-0.51) would let a 0.8 wire read anywhere from nothing to 1.3.
WIRE_DIA_TOLERANCE_MM = 0.02

# Marked set: the profile circle's diameter (END view) and the extrusion's
# depth, renamed ``Depth`` in the build (FRONT view, reference).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "WireProfile": {"WireDiaDim"},
    "Wire": {"Depth"},
}

# One line of forming fact the views cannot carry (policy rule 6): the hook
# and the hub wrap are formed at assembly, so the wire is cut long.  Every
# number is on a view.
DRAWING_NOTES = (
    "ONE PIECE. END HOOK AND HUB WRAP FORMED AT ASSEMBLY; CUT LONG AND TRIM."
)
# The sheet runs 1:5 (title block), so the front caption does not repeat the
# sheet scale; the enlarged end view states its own.
FRONT_VIEW_NOTE = "FRONT VIEW"
END_VIEW_NOTE = "END VIEW SCALE 10:1"
