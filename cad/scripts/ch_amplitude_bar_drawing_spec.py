"""Pure-data drawing contract for the amplitude bar: its surface finishes.

Split from ``ch_amplitude_bar_spec`` on purpose: the channel kinematics, the
rocker-bank layout and the spring specs import the bar's geometry, so the
finish controls (and the ``_gtol_spec``/``_surface_finish`` closure they pull
in) living there would re-key the channel, magnifier and summing assemblies on
every finish edit (the codex #354 lesson). This module is imported only by the
part build (which authors the PMI) and its drawing.
"""

from __future__ import annotations

from _gtol_spec import PlanarFace
from _surface_finish import GROUND_UM, SurfaceFinishControl
from ch_amplitude_bar_spec import BOTTOM_NOTCH_HEIGHT

# The foot notch's floor rides the rocker's top edge (ch. 15): the bar's one
# running face, ground, symbol on the floor in DETAIL A (Main ruling
# 2026-09-27, Codex #936 PRRT_kwDOPHDy386mWF0L). PlanarFace offsets run ALONG
# the outward normal (point . normal): the floor looks -Y, down into the notch,
# from y = BOTTOM_NOTCH_HEIGHT; the ledges' -Y faces sit at 0.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "bottom_notch_floor",
        GROUND_UM,
        PlanarFace((0, -1, 0), -BOTTOM_NOTCH_HEIGHT),
    ),
)
