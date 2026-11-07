"""Sheet text for the MHA-PD-06 reducer disc drawing.

Drawing-only: imported by ``draw_pd_rack_pinion`` (and its test), never by
the part builder, so rewording the sheet re-keys only the drawing.
``pd_rack_pinion_spec``, which the part, the feed pinion, the disc hub and
the paper-drive assembly import, keeps the geometry and limits; every value
printed here is read from it.

drawing-guidelines.md rule 7: a callout carries its size and process lines
plus at most two lines of words; anything longer is a numbered note its
callout links by ``SEE NOTE n``.  Rule 4: the bore's matched fit takes a
standard fit name, the mate's drawing number and the resulting clearance as
REF; one feature with several tight dimensions (the teeth: span and tip)
names its mate once, in the GEAR DATA block both dimensions link.
"""

from __future__ import annotations

import math

import paper_drive_mesh_check as mesh_check
import pd_transgear_knob_shaft_spec as knob
from pd_rack_pinion_spec import (
    BORE_FRONT_CHAMFER,
    CENTRE_DISTANCE_WINDOW,
    FRONT_FACE_DATUM,
    GEAR_DATA,
    HUB_NUMBER,
    KNOB_NUMBER,
    MESH_PINION_TEETH,
    MOUTH_BREAK_MAX,
    PITCH_DIA,
    PRESSURE_ANGLE_DEG,
    SCREW_NUMBER,
    SPIGOT_DIAMETRAL_CLEARANCE,
    TAP_WALL_TEXT,
    inch_ceil_mm,
    inch_floor_mm,
    inch_text,
)

BORE_NOTE = 1
TAP_NOTE = 2

# The reamed bore: process then depth under its native limits (rule 26:
# size, process, depth), the fit and the front edge's chamfer (hidden
# behind the face view's rear face) in its note.
BORE_CALLOUT = f"REAM THRU\nSEE NOTE {BORE_NOTE}"
# The #0-80 taps: under the native drill and thread lines, the mouth breaks
# (tighter than the title block's .010 because the screw's engagement spends
# them, so the screw is named) and the link to the transfer note.
TAP_CALLOUT_LINES = (
    f"BREAK EDGES {inch_text(MOUTH_BREAK_MAX, 3)} MAX FOR {SCREW_NUMBER}",
    f"SEE NOTE {TAP_NOTE}",
)
TAP_CALLOUT_QUALIFIER = "\n".join(TAP_CALLOUT_LINES)
# The span and the tip serve the one mesh: each links the GEAR DATA block,
# which names the mate once with its backlash acceptance.
MESH_CALLOUT = "SEE GEAR DATA"

_CLEARANCE = "-".join(inch_text(value, 4) for value in SPIGOT_DIAMETRAL_CLEARANCE)
# Rule 20: the tap-to-bore web's stated shortfall (RV-03) rides the tap note.
DRAWING_NOTES = "\n".join(
    (
        f"{BORE_NOTE}. LOCATIONAL CLEARANCE FIT ON {HUB_NUMBER} SPIGOT",
        f"   (CLEARANCE {_CLEARANCE} REF). CHAMFER "
        f"{inch_text(BORE_FRONT_CHAMFER, 3)} X 45\u00b0 AT FACE {FRONT_FACE_DATUM}.",
        f"{TAP_NOTE}. MATCH-DRILL AT ASSEMBLY WITH {HUB_NUMBER}: SPOT THRU ITS FLANGE",
        f"   HOLES, THEN DRILL AND TAP; MATCH-MARK BOTH. {TAP_WALL_TEXT}.",
    )
)


def _feeler_backlash_mm(circular_mm: float, centre_distance_mm: float) -> float:
    """Circular backlash on the operating pitch circles as the normal
    backlash a feeler gauge reads between the flanks: times the operating
    pressure angle's cosine at that centre."""
    base_sum = (knob.PITCH_DIA + PITCH_DIA) / 2.0 * math.cos(
        math.radians(PRESSURE_ANGLE_DEG)
    )
    return circular_mm * base_sum / centre_distance_mm


# The reducer's backlash budget (paper_drive_mesh_check.reducer_band_meshes):
# tight at the low end of the set centre band less the runout shift with the
# thickest printed teeth, loose at the high end plus the shift with the
# thinnest.  The acceptance is that budget as a feeler reads it, rounded
# inward onto the .001 in grid: a disc whose span is anywhere in its band
# meshes MHA-PD-08 inside it.  MHA-PD-08's GEAR DATA prints the same row.
_SHIFT = mesh_check.reducer_runout_shift_mm()
_LOW_BAND, _HIGH_BAND = mesh_check.reducer_band_meshes()
BACKLASH_BUDGET_MM = (
    _feeler_backlash_mm(_LOW_BAND.backlash_mm[0], CENTRE_DISTANCE_WINDOW[0] - _SHIFT),
    _feeler_backlash_mm(_HIGH_BAND.backlash_mm[1], CENTRE_DISTANCE_WINDOW[1] + _SHIFT),
)
BACKLASH_ACCEPT_MM = (
    inch_ceil_mm(BACKLASH_BUDGET_MM[0], 3),
    inch_floor_mm(BACKLASH_BUDGET_MM[1], 3),
)
if not BACKLASH_BUDGET_MM[0] <= BACKLASH_ACCEPT_MM[0] < BACKLASH_ACCEPT_MM[1] <= BACKLASH_BUDGET_MM[1]:
    raise AssertionError(
        f"MHA-PD-06 backlash acceptance {BACKLASH_ACCEPT_MM} leaves the budget "
        f"{BACKLASH_BUDGET_MM}"
    )

# The part's cutting rows (its "Gear Data" property) less the span, which the
# face view prints with its limits, and the mate, restated with the backlash
# acceptance that is the span band's fit route (rule 4).
_MOVED_ROWS = ("SPAN OVER ", "MATES WITH:")
GEAR_DATA_NOTE = "\n".join(
    (
        *(line for line in GEAR_DATA.splitlines() if not line.startswith(_MOVED_ROWS)),
        f"MATES WITH:  KNOB SHAFT {KNOB_NUMBER}, {MESH_PINION_TEETH}T",
        "BACKLASH WITH MATE (FEELER):  "
        + "-".join(inch_text(value, 3) for value in BACKLASH_ACCEPT_MM),
    )
)
