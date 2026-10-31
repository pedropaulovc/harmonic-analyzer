r"""Crank-arm drawing prose -- the hub-seat, seam and pivot callouts on its sheet.

Imported ONLY by ``draw_crank_arm`` and its offline test (codex #361; see
``crank_hub_notes``), so a wording edit re-keys the drawing, never the part.
"""

from __future__ import annotations

from dt_crank_handle_pivot_screw_spec import TAPPED_MOUTH_DIA_MAX
from dt_crank_hub_geometry import (
    AXIAL_PIN_DIA,
    AXIAL_PIN_LENGTH,
    MM_PER_IN,
    SEAT_PRESS_INTERFERENCE,
)


def _inch(value_mm: float, places: int) -> str:
    """``value_mm`` as the inch sheet prints it, without a leading zero."""
    return f"{value_mm / MM_PER_IN:.{places}f}".removeprefix("0")


# Short lines: the callout is centred under the diameter, so its widest line
# sets how close to the left border the hub-end dimension can stand.  The
# bore is made first and keeps its printed band; the hub is turned to suit
# it, and the interference it is turned to is the fit's acceptance (#984
# machinist review r1: "LIGHT PRESS FIT" alone gave none).
_PRESS_LOW, _PRESS_HIGH = SEAT_PRESS_INTERFERENCE
HUB_SEAT_CALLOUT = "\n".join(
    (
        "MHA-DT-31 HUB TURNED TO",
        "SUIT FOR A LIGHT PRESS:",
        f"{_inch(_PRESS_LOW, 4)}-{_inch(_PRESS_HIGH, 4)} DIAMETRAL",
        "INTERFERENCE; FACES FLUSH",
    )
)
# The MHA-DT-VN-59 seam is match-drilled with the hub at assembly; its callout
# sits on the seam itself with the pin's nominal size and depth.  Half the
# hole is in the hub, open toward the arm's outboard face: pressing the hub
# out slides it off the pin, which then lifts out of the arm's half-hole --
# the drive-fit pin's way out (#984 machinist review r1, blind-hole finding).
SEAM_CALLOUT = "\n".join(
    (
        f"(<MOD-DIAM>{_inch(AXIAL_PIN_DIA, 3)}) <HOLE-DEPTH> {_inch(AXIAL_PIN_LENGTH, 3)}",
        "MATCH-DRILL/REAM WITH MHA-DT-31 AT ASSEMBLY,",
        "CENTRED ON THE SEAM, FOR MHA-DT-VN-59 AXIAL PIN:",
        "LIGHT DRIVE FIT; PRESSING MHA-DT-31 OUT FREES THE PIN",
    )
)
# The handle-pivot tap's mouth limit rides its own callout, under the native
# size, on the face the front view shows: the MHA-DT-32 shoulder seats
# round it (#984 machinist review r1: as a general note it named neither of
# the two identical taps nor the face).
PIVOT_TAP_ROWS = (
    "FOR MHA-DT-32 HANDLE PIVOT;\n"
    f"MOUTH <MOD-DIAM>{_inch(TAPPED_MOUTH_DIA_MAX, 3)} MAX, NEAR SIDE"
)
# The punched fiducial is flagged at the mark, not in the general notes
# (#984 machinist review r2/r3: an unlabelled crosshair could read as an
# undimensioned hole).  Its location is the two imported ordinates from the
# hub-seat axis; the callout states only what it is for (machinist review
# 2026-10-27: "LOCATE BY EYE" placed it in words).  Short lines keep the
# block's right end left of the mark, so its leader descends away from the
# block and the FiducialX ordinate.
FIDUCIAL_CALLOUT = "PUNCH MARK:\nALIGNS WITH\nMHA-DT-11\nDOME MARK"
