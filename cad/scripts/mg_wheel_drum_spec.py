r"""Pure-data drawing contract for the magnifying-wheel drum (MHA-MG-10).

A brass ring pressed on the wheel's spigot; the lever wire wraps it. The
nominals and bands live in the drawing-FREE ``mg_wheel_drum_geom`` (the wheel
and the wire solvers import them); they are re-exported here for the build,
the drawing and the offline lockstep test.
"""

from __future__ import annotations

from _surface_finish import SurfaceFinishControl
from mg_wheel_drum_geom import (  # noqa: F401 (re-export)
    DRUM_BORE,
    DRUM_BORE_BAND,
    DRUM_BORE_PLACES,
    DRUM_LEN,
    DRUM_LEN_BAND,
    DRUM_LEN_PLACES,
    DRUM_OD,
    DRUM_OD_PLACES,
    UNIT,
)

# Marked model dimensions and the places the model authors on them
# (drawing-simplicity-policy.md `How the repository implements the guidelines`): the reamed bore at four places (its +.0005
# band), the length at three (its -.004 band), the O.D. on the title block's
# .XX row (the geom's WALL_WORST holds the wall under it).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingProfile": {"DrumOd", "DrumBore"},
    "Drum": {"DrumLen"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RingProfile": {"DrumOd": DRUM_OD_PLACES, "DrumBore": DRUM_BORE_PLACES},
    "Drum": {"DrumLen": DRUM_LEN_PLACES},
}

# drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates): the bore is
# pressed on the wheel's spigot and neither runs nor slides; the drum seats
# axially on its face against the boss, so no surface carries a symbol.
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()
