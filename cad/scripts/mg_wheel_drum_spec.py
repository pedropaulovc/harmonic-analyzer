r"""Pure-data drawing contract for the magnifying-wheel drum (MHA-MG-010).

A brass ring pressed on the wheel's spigot; the lever wire wraps it. The
nominals and bands live in the drawing-FREE ``mg_wheel_drum_geom`` (the wheel
and the wire solvers import them); they are re-exported here for the build,
the drawing and the offline lockstep test.
"""

from __future__ import annotations

from mg_wheel_drum_geom import (  # noqa: F401 (re-export)
    DRUM_BORE,
    DRUM_BORE_BAND,
    DRUM_LEN,
    DRUM_LEN_BAND,
    DRUM_OD,
    DRUM_OD_BAND,
)

# Marked model dimensions and the places the model authors on them
# (drawing-simplicity rule 2): the press-fit bore at three places.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingProfile": {"DrumOd", "DrumBore"},
    "Drum": {"DrumLen"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RingProfile": {"DrumOd": 2, "DrumBore": 3},
    "Drum": {"DrumLen": 2},
}

DRAWING_NOTES = "PRESS ON THE MG-MAGNIFYING-WHEEL SPIGOT, HARD AGAINST THE BOSS."
