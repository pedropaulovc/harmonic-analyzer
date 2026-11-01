r"""Crank-arm drawing prose -- the hub-seat, seam and pivot callouts on its sheet.

Imported ONLY by ``draw_crank_arm`` and its offline test (codex #361; see
``crank_hub_notes``), so a wording edit re-keys the drawing, never the part.
"""

from __future__ import annotations

from dt_crank_handle_pivot_screw_spec import TAPPED_MOUTH_DIA_MAX
from dt_crank_hub_geometry import SEAT_PRESS_INTERFERENCE
from dt_crank_hub_notes import inch_text as _inch
from dt_crank_hub_notes import seam_callout


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
# sits on the seam itself, the same requirement the hub's sheet prints (the
# blind pin makes the pair permanent; owner ruling 2026-11-01).
SEAM_CALLOUT = seam_callout("MHA-DT-31", "MHA-DT-VN-59 AXIAL PIN")
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
