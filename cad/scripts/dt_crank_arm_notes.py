r"""Crank-arm drawing prose -- the hub-seat, seam and pivot callouts on its sheet.

Imported ONLY by ``draw_crank_arm`` and its offline test (codex #361; see
``crank_hub_notes``), so a wording edit re-keys the drawing, never the part.
"""

from __future__ import annotations

from dt_crank_handle_pivot_screw_spec import TAPPED_MOUTH_DIA_MAX
from dt_crank_hub_geometry import (
    AXIAL_PIN_DIA,
    AXIAL_PIN_LENGTH,
    SEAT_ROOT_FILLET_R,
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
# The MHA-DT-VN-59 seam is match-drilled with the hub at assembly.  The dowel's
# axial pull thread gives it a way out of the blind seat without first
# pressing the arm off the hub (coordinator's corrected M2 THRU ruling).
SEAM_CALLOUT = "\n".join(
    (
        f"(<MOD-DIAM>{AXIAL_PIN_DIA:.1f}) <HOLE-DEPTH> {AXIAL_PIN_LENGTH:.1f}",
        "MATCH-DRILL/REAM WITH MHA-DT-31 AT ASSEMBLY,",
        "CENTRED ON THE SEAM, FOR MHA-DT-VN-59 AXIAL PIN:",
        "LIGHT DRIVE FIT; AXIAL THREAD FOR EXTRACTION",
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
# undimensioned hole).
FIDUCIAL_CALLOUT = "PUNCH FIDUCIAL MARK;\nLOCATE BY EYE"
# The hub seat's inboard-mouth chamfer: the native leg prints its LIMIT band
# and the model's 45 degrees rides this row.  The rows name the face (section
# A-A shows the corner) and the mate's seat-root radius it must clear
# (drawing-guidelines.md rule 4).  Two trailing spaces keep each row's ink off
# the leg's overrunning extension line (draw_dt_crank_drive_gear's finding).
BORE_REAR_CHAMFER_CALLOUT = (
    f" X 45 DEG, INBOARD FACE  \nCLEARS MHA-DT-031 ROOT R{SEAT_ROOT_FILLET_R:.1f}  "
)
