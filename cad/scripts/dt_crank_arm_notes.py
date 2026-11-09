r"""Crank-arm drawing prose -- the hub-seat, seam and pivot callouts on its sheet.

Imported ONLY by ``draw_crank_arm`` and its offline test (codex #361; see
``crank_hub_notes``), so a wording edit re-keys the drawing, never the part.
"""

from __future__ import annotations

from dt_crank_handle_pivot_screw_spec import TAPPED_MOUTH_DIA_MAX
from dt_crank_hub_geometry import AXIAL_PIN_DIA, FIDUCIAL_MODEL_DIA, SEAM_DEPTH
from dt_crank_hub_notes import inch_text as _inch


# The bore is made first and keeps its printed band; the hub is made to the
# measured bore, and the interference it is made to is the fit's acceptance,
# flagged to note 2 (rule 4: the standard fit name, its mate by name and
# number).  The faces-flush stop is the MHA-DT-00 press step's (rule 7).
# Rows <= 24 characters: the block is centred under the diameter, so its
# widest row sets how close to the left border the hub-end dimension stands.
HUB_SEAT_CALLOUT = "PRESS FIT ON CRANK HUB\nMHA-DT-31, SEE NOTE 2"
# The MHA-DT-VN-59 seam: size, process and depth (rule 26: a depth is never
# deferred), then the flag to note 3, which carries the assembly-made ream,
# its mate, pin and fit and the permanent pair (rules 4 and 7).  The depth
# is the model's SeamDepth global, from the front face the front view shows.
# Its station from the bore axis is a reference dimension on the view (rule
# 26: a location is a dimension).
SEAM_CALLOUT = "\n".join(
    (
        f"(<MOD-DIAM>{_inch(AXIAL_PIN_DIA, 3)}) REAM <HOLE-DEPTH> "
        f"{_inch(SEAM_DEPTH, 2)}",
        "SEE NOTE 3",
    )
)
# The handle-pivot tap's mouth limit rides its own callout, under the native
# size, on the face the front view shows: the MHA-DT-32 shoulder seats
# round it (#984 machinist review r1: as a general note it named neither of
# the two identical taps nor the face).  A mouth chamfer prints as a
# countersink, in symbol form at the tapped-hole 90 degrees (rule 26), on the
# near side (the face the view shows; fan-out round 3: the face was not
# drawn), after the native size and process rows and before the mate.
PIVOT_TAP_ROWS = (
    f"<HOLE-SINK><MOD-DIAM>{_inch(TAPPED_MOUTH_DIA_MAX, 3)} MAX X 90\u00b0 NEAR SIDE\n"
    "FOR MHA-DT-32 HANDLE PIVOT"
)
# The punched fiducial is flagged at the mark, not in the general notes
# (#984 machinist review r2/r3: an unlabelled crosshair could read as an
# undimensioned hole).  Its location is the two imported ordinates from the
# hub-seat axis; the callout gives its size and process, then two short rows
# of what it is for (rule 7; machinist review 2026-10-27: "LOCATE BY EYE"
# placed it in words).  Short lines keep the block's right end left of the
# mark, so its leader descends away from the block and the FiducialX ordinate.
FIDUCIAL_CALLOUT = (
    f"<MOD-DIAM>{_inch(FIDUCIAL_MODEL_DIA, 2)} PUNCH\nMATCH MARK\nTO MHA-DT-11"
)
