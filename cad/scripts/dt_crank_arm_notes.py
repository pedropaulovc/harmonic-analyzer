r"""Crank-arm drawing prose -- the hub-seat, seam and pivot callouts on its sheet.

Imported ONLY by ``draw_crank_arm`` and its offline test (codex #361; see
``crank_hub_notes``), so a wording edit re-keys the drawing, never the part.
"""

from __future__ import annotations

from dt_crank_handle_pivot_screw_spec import TAPPED_MOUTH_DIA_MAX
from dt_crank_hub_geometry import AXIAL_PIN_DIA, SEAM_DEPTH, SEAT_PRESS_INTERFERENCE
from dt_crank_hub_notes import inch_text as _inch


# The bore is made first and keeps its printed band; the hub is made to the
# measured bore, and the interference it is made to is the fit's acceptance
# (rule 4: the standard fit name, its mate, the interference).  The
# faces-flush stop is the MHA-DT-00 press step's, not this sheet's (rule 7).
# Rows <= 24 characters: the block is centred under the diameter, so its
# widest row sets how close to the left border the hub-end dimension stands.
_PRESS_LOW, _PRESS_HIGH = SEAT_PRESS_INTERFERENCE
HUB_SEAT_CALLOUT = "\n".join(
    (
        "PRESS FIT ON MHA-DT-31",
        f"INTERFERENCE {_inch(_PRESS_LOW, 4)}-{_inch(_PRESS_HIGH, 4)}",
    )
)
# The MHA-DT-VN-59 seam is reamed with the hub at assembly: size, process and
# depth on the first line (rule 26: a depth is never deferred), then two
# lines of words naming the mate and the pin's fit (rules 4 and 7), as the
# hub's own sheet prints it.  The depth is the model's SeamDepth global, from
# the front face the front view shows.  Its station from the bore axis is a
# reference dimension on the view (rule 26: a location is a dimension).
SEAM_CALLOUT = "\n".join(
    (
        f"(<MOD-DIAM>{_inch(AXIAL_PIN_DIA, 3)}) REAM <HOLE-DEPTH> "
        f"{_inch(SEAM_DEPTH, 2)} AT ASSEMBLY",
        "WITH CRANK HUB MHA-DT-31 FOR",
        "DOWEL PIN MHA-DT-VN-59, LIGHT DRIVE FIT",
    )
)
# The handle-pivot tap's mouth limit rides its own callout, under the native
# size, on the face the front view shows: the MHA-DT-32 shoulder seats
# round it (#984 machinist review r1: as a general note it named neither of
# the two identical taps nor the face).
PIVOT_TAP_ROWS = (
    "FOR MHA-DT-32 HANDLE PIVOT\n"
    f"CHAMFER <MOD-DIAM>{_inch(TAPPED_MOUTH_DIA_MAX, 3)} MAX ON FRONT FACE"
)
# The punched fiducial is flagged at the mark, not in the general notes
# (#984 machinist review r2/r3: an unlabelled crosshair could read as an
# undimensioned hole).  Its location is the two imported ordinates from the
# hub-seat axis; the callout states only what it is for (machinist review
# 2026-10-27: "LOCATE BY EYE" placed it in words).  Short lines keep the
# block's right end left of the mark, so its leader descends away from the
# block and the FiducialX ordinate.
FIDUCIAL_CALLOUT = "PUNCH MARK:\nALIGNS WITH\nMHA-DT-11\nDOME MARK"
