r"""Pure-data drawing contract for the magnifying-wheel drum (MHA-MG-010).

A brass ring pressed on the wheel's spigot; the lever wire wraps it. The
nominals and bands live in the drawing-FREE ``mg_wheel_drum_geom`` (the wheel
and the wire solvers import them); they are re-exported here for the build,
the drawing and the offline lockstep test.
"""

from __future__ import annotations

from mg_magnifying_wheel_geom import DRUM_PRESS, SPIGOT_BAND, SPIGOT_DIA
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

# The fit the bore makes, stated on the sheet (the geom refuses a minimum
# interference that is not positive).
_SPIGOT = (SPIGOT_DIA + SPIGOT_BAND[1], SPIGOT_DIA + SPIGOT_BAND[0])
DRAWING_NOTES = "\n".join(
    (
        f"PRESS ON MG-MAGNIFYING-WHEEL SPIGOT Ø{_SPIGOT[0]:.3f}-{_SPIGOT[1]:.3f}",
        f"(INTERFERENCE {DRUM_PRESS[0]:.3f}-{DRUM_PRESS[1]:.3f}), HARD AGAINST THE BOSS.",
    )
)
