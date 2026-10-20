r"""LeverWire print contract of sh-vn-music-wire (MHA-SH-VN-56).

PURE DATA, no SolidWorks/COM imports. ``build_sh_vn_music_wire`` stamps these
notes for the LeverWire sheet of ``draw_sh_vn_music_wire``. Its computed
endpoints/yoke remain in ``sh_vn_music_wire_lever_geom``; layout consumers
import that drawing-free solver directly so print prose stays out of their
geometry recipe closures.

The wire is purchased McMaster-Carr 9666K56 music wire (0.031 in, modelled at
its Ø0.8 design nominal inside the catalogue band), cut from the coil: a ~353
long thin silhouette with no flat face, no end-face big enough to pick and no
selectable silhouette edge, so NOTHING is a marked dimension; the SKU and the
straight rest-run length ride the notes.  The rest-run length is COMPUTED between
the two solved endpoints, but it is NOT a developed cut length: the source model
deliberately omits both end terminations and the drum wrap, so their development
allowance is unknown and the sheet stays DO NOT RELEASE until they are specified.
"""

from __future__ import annotations

from _mcmaster_9666k56 import SKU
from sh_vn_music_wire_lever_geom import WIRE_DIA  # noqa: F401 (re-export, import-pure)

# Note-based: the un-pickable Ø0.8 wire carries no marked model dimension, so the
# marked set is empty and the drawing keeps nothing (the lockstep test asserts
# union(marks) == union(keeps) == {}).
DRAWING_DIMENSIONS: dict[str, set[str]] = {}

# The balloon ring's station, as a fraction of the run from the drum end
# (build_sh_vn_music_wire.BalloonRingSplit): mid-run, on the free span between
# the wheel rim and the fixture, where MHA-MG-00's finished view balloons the
# wire. Shared so the drawing's balloon anchor and the build agree.
BALLOON_RING_FRACTION = 0.5

# True free-text instructions only; the build stamps these and APPENDS the
# computed straight-run line, then the drawing displays only the $PRPSHEET link.
DRAWING_NOTES = "\n".join(
    (
        f"PURCHASED WIRE: McMASTER-CARR {SKU}, Ø0.031 IN.",
        "THIS SHEET DEFINES THE STRAIGHT REST RUN ONLY.",
        "FORMED HOOK, DRUM WRAP, AND DEVELOPED CUT LENGTH ARE NOT DEFINED BY",
        "THE SOURCE MODEL. DO NOT RELEASE UNTIL THOSE DETAILS ARE SPECIFIED.",
    )
)
FRONT_VIEW_NOTE = "FRONT VIEW SCALE 1:5"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:5"
