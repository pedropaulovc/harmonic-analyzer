r"""Crank-arm drawing prose -- the hub-seat, seam and pivot callouts on its sheet.

Imported ONLY by ``draw_crank_arm`` and its offline test (codex #361; see
``crank_hub_notes``), so a wording edit re-keys the drawing, never the part.

The arm's by-eye punched witness aligns with the crankshaft-dome witness when
refitting the arm/hub after gear service (``cad/config/dimensions.yaml``,
Chapter 11 construction notes). It has no controlled location, diameter or depth;
its function belongs on the existing feature-attached drawing callout.
"""

from __future__ import annotations

from dt_crank_handle_pivot_screw_spec import TAPPED_MOUTH_DIA_MAX
from dt_crank_hub_geometry import (
    AXIAL_PIN_DIA,
    AXIAL_PIN_LENGTH,
    SEAT_PRESS_INTERFERENCE,
)

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
        f"{_PRESS_LOW:.3f}-{_PRESS_HIGH:.3f} DIAMETRAL",
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
        f"(<MOD-DIAM>{AXIAL_PIN_DIA:.1f}) <HOLE-DEPTH> {AXIAL_PIN_LENGTH:.1f}",
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
    f"MOUTH <MOD-DIAM>{TAPPED_MOUTH_DIA_MAX:.1f} MAX, NEAR SIDE"
)
# The punched fiducial is flagged at the mark, not in the general notes
# (#984 machinist review r2/r3: an unlabelled crosshair could read as an
# undimensioned hole). Name its reassembly purpose without controlling its spot.
FIDUCIAL_CALLOUT = (
    "PUNCH FIDUCIAL MARK;\n"
    "LOCATE BY EYE\n"
    "ALIGN WITH MHA-DT-11 MARK\n"
    "WHEN REFITTING CRANK"
)
