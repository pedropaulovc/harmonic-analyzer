r"""Pure-data drawing contract for the magnifying-wheel drum (MHA-MG-10).

A brass ring pressed on the wheel's spigot; the lever wire wraps it. The
nominals and bands live in the drawing-FREE ``mg_wheel_drum_geom`` (the wheel
and the wire solvers import them); they are re-exported here for the build,
the drawing and the offline lockstep test.
"""

from __future__ import annotations

from _surface_finish import SurfaceFinishControl
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
# (drawing-simplicity-policy.md `How the repository implements the guidelines`): the press-fit bore at three places, the O.D.
# on the title block's .X row (the geom's WALL_WORST holds 2.0 under it).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingProfile": {"DrumOd", "DrumBore"},
    "Drum": {"DrumLen"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RingProfile": {"DrumOd": DRUM_OD_PLACES, "DrumBore": 3},
    "Drum": {"DrumLen": 2},
}

# Each band's need, printed on its own callout (drawing-guidelines.md rule 4 (tighten only for function, and name the mate) and drawing-guidelines.md rule 7 (notes: few, flagged, never a method)): the
# bore's diametral interference on the wheel spigot, which is turned to it
# (the bore keeps its H7 band: the drum is made first), with the seating
# stop, and how far the length leaves the drum's front face under the
# spigot's, so the front washer bears on the iron (DRUM_RECESS refuses a drum
# proud of the spigot). No general note.
# The mate prints by its drawing number (drawing-guidelines.md rule 4): the
# spigot is turned to the interference in this bore.
PRESS_CALLOUT = (
    "PRESS ON MHA-MG-05 WHEEL\n"
    "SPIGOT, HARD AGAINST BOSS\n"
    f"{DRUM_PRESS[0]:.3f}-{DRUM_PRESS[1]:.3f} DIAMETRAL INTERFERENCE"
)
RECESS_CALLOUT = (
    f"FRONT FACE {DRUM_RECESS[0]:.2f}-{DRUM_RECESS[1]:.2f} BELOW\nWHEEL SPIGOT FACE"
)
# drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates): the bore is
# pressed on the wheel's spigot and neither runs nor slides; the drum seats
# axially on its face against the boss, so no surface carries a symbol.
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()
