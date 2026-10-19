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

The installed wire is purchased McMaster-Carr 9666K56 music wire, represented
at the in-band Ø0.8 design envelope. A separate sketch-only configuration
carries the supplier's exact nominal stock cross-section and native inch
diameter; it does not change that installed envelope or its endpoints.
The rest-run length is computed between the two solved endpoints, but is
not a developed cut length: the source model omits end terminations and the
drum wrap, so the sheet stays DO NOT RELEASE until those are specified.
"""

from __future__ import annotations

from _mcmaster_9666k56 import SKU
from _mcmaster_9666k56_reference import SUPPLIER_REFERENCE_DIMENSIONS
from vn_lever_wire_geom import WIRE_DIA  # noqa: F401 (re-export, import-pure)

# No installed-wire size is imported: only the distinct supplier nominal
# stock cross-section carries a reference diameter.
DRAWING_DIMENSIONS = {**SUPPLIER_REFERENCE_DIMENSIONS}

# The balloon ring's station, as a fraction of the run from the drum end
# (build_vn_lever_wire.BalloonRingSplit): mid-run, on the free span between
# the wheel rim and the fixture, where MHA-MG-000's finished view balloons the
# wire. Shared so the drawing's balloon anchor and the build agree.
BALLOON_RING_FRACTION = 0.5

# True free-text instructions only; the build stamps these and APPENDS the
# computed straight-run line, then the drawing displays only the $PRPSHEET link.
DRAWING_NOTES = "\n".join(
    (
        f"PURCHASED WIRE: McMASTER-CARR {SKU}.",
        "THIS SHEET DEFINES THE STRAIGHT REST RUN ONLY.",
        "FORMED HOOK, DRUM WRAP, AND DEVELOPED CUT LENGTH ARE NOT DEFINED BY",
        "THE SOURCE MODEL. DO NOT RELEASE UNTIL THOSE DETAILS ARE SPECIFIED.",
    )
)
FRONT_VIEW_NOTE = "FRONT VIEW SCALE 1:5"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:5"
