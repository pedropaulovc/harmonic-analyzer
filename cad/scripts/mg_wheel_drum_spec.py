r"""Pure-data drawing contract for the magnifying-wheel drum (MHA-MG-010).

A brass ring pressed on the wheel's spigot; the lever wire wraps it. The
nominals and bands live in the drawing-FREE ``mg_wheel_drum_geom`` (the wheel
and the wire solvers import them); they are re-exported here for the build,
the drawing and the offline lockstep test.
"""

from __future__ import annotations

from _gtol_cylinder import CylinderFace
from _surface_finish import SEAT_UM, SurfaceFinishControl
from mg_magnifying_wheel_geom import DRUM_PRESS, DRUM_RECESS
from mg_wheel_drum_geom import (  # noqa: F401 (re-export)
    DRUM_BORE,
    DRUM_BORE_BAND,
    DRUM_LEN,
    DRUM_LEN_BAND,
    DRUM_OD,
    DRUM_OD_PLACES,
)

# Marked model dimensions and the places the model authors on them
# (drawing-simplicity rule 2): the press-fit bore at three places, the O.D.
# on the title block's .XX row.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingProfile": {"DrumOd", "DrumBore"},
    "Drum": {"DrumLen"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RingProfile": {"DrumOd": DRUM_OD_PLACES, "DrumBore": 3},
    "Drum": {"DrumLen": 2},
}

# Each band's need, printed on its own callout (policy rules 2 and 6): the
# bore's interference on the wheel spigot (the geom refuses a minimum that is
# not positive) with the seating stop, and how far the length leaves the
# drum's front face under the spigot's, so the front washer bears on the iron
# (DRUM_RECESS refuses a drum proud of the spigot). No general note.
PRESS_CALLOUT = (
    "PRESS ON MG-MAGNIFYING-WHEEL\n"
    "SPIGOT, HARD AGAINST BOSS\n"
    f"{DRUM_PRESS[0]:.3f}-{DRUM_PRESS[1]:.3f} INTERFERENCE"
)
RECESS_CALLOUT = (
    f"FRONT FACE {DRUM_RECESS[0]:.2f}-{DRUM_RECESS[1]:.2f} BELOW\nWHEEL SPIGOT FACE"
)
# Rule 5: the bore is a static locating press seat on the wheel's spigot.
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = (
    SurfaceFinishControl("mg_drum_bore", SEAT_UM, CylinderFace(DRUM_BORE)),
)
