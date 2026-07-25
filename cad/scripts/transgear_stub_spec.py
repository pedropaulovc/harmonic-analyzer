r"""Pure-data dimensional contract shared by the transgear stud and drawing.

PURE DATA: the marked-dimension map + sheet notes. The turned-part NOMINALS
live one level down in ``transgear_stub_geom`` (drawing-free) and are re-exported
here, so ``build_paper_drive_assembly`` can seat the disc on the stud's own stack
without pulling this module's prose into the assembly recipe.
"""

from __future__ import annotations

from transgear_stub_geom import (  # noqa: F401  (re-exported for the drawing)
    BASE_DIA,
    BASE_LEN,
    COLLAR_DIA,
    COLLAR_LEN,
    MM_PER_IN,
    SEAT_DIA,
    SEAT_LEN,
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "StubProfile": {
        "BaseDia",
        "SeatDia",
        "CollarDia",
        "BaseLength",
        "SeatLength",
        "CollarLength",
    },
}

DRAWING_NOTES = "\n".join(
    (
        "TURN FROM 16 MM (5/8 IN) BAR IN ONE SETUP; SEAT AND COLLAR "
        "CONCENTRIC WITH BASE.",
    )
)
