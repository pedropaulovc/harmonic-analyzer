"""Sheet text for the MHA-PD-06 reducer disc drawing.

Drawing-only: imported by ``draw_pd_rack_pinion`` (and its test), never by
the part builder, so rewording the sheet re-keys only the drawing.
``pd_rack_pinion_spec``, which the part, the feed pinion, the disc hub and
the paper-drive assembly import, keeps the geometry and limits; every value
printed here is read from it.

drawing-guidelines.md rule 7: a callout carries its size and process lines
plus at most two lines of words; anything longer is a numbered note its
callout links by ``SEE NOTE n``.  Rule 4: the bore's fit takes a standard
fit name, the mate's drawing number and the resulting clearance as REF; one
feature with several tight dimensions (the teeth: span and tip) names its
mate once, in the GEAR DATA block both dimensions link.
"""

from __future__ import annotations

import math

import paper_drive_mesh_check as mesh_check
import pd_transgear_knob_shaft_spec as knob
from pd_rack_pinion_spec import (
    BORE_FRONT_CHAMFER,
    CENTRE_DISTANCE_WINDOW,
    CUTTER_NUMBER,
    CUTTER_TOOTH_RANGE,
    DIAMETRAL_PITCH,
    HUB_NUMBER,
    MESH_PINION_TEETH,
    MOUTH_BREAK_MAX,
    PITCH_DIA,
    PRESSURE_ANGLE_DEG,
    SPIGOT_DIAMETRAL_CLEARANCE,
    TAP_WALL_TEXT,
    TEETH,
    WHOLE_DEPTH,
    inch_ceil_mm,
    inch_floor_mm,
    inch_text,
)

KNOB_NUMBER = "MHA-PD-08"
SCREW_NUMBER = "MHA-PD-VN-55"
BORE_NOTE = 1
TAP_NOTE = 2

# The reamed bore: process then depth under its native limits (rule 26:
# size, process, depth), and its fit in its note.
BORE_CALLOUT = f"REAM THRU\nSEE NOTE {BORE_NOTE}"
# The bore's front-edge chamfer is a feature, not the title block's edge
# break: its least must pass the spigot root's R.004 (the disc can ride on
# the spigot's side while it is centred).  Detail B of section A-A shows it;
# this leadered note sizes it at .XXX (the title block's row gives
# .005-.015) and names the root it clears, on three rows so it stays narrow
# beside the detail.
CHAMFER_NOTE = "\n".join(
    (
        f"{inch_text(BORE_FRONT_CHAMFER, 3)} X 45\u00b0",
        f"CLEARS {HUB_NUMBER}",
        "SPIGOT ROOT",
    )
)
# The #0-80 taps: under the native drill and thread lines, the mouth breaks
# (tighter than the title block's .010 because the screw's engagement spends
# them, so the screw is named) and the link to the transfer note.
TAP_CALLOUT_LINES = (
    f"BREAK EDGES {inch_text(MOUTH_BREAK_MAX, 3)} MAX FOR {SCREW_NUMBER}",
    f"SEE NOTE {TAP_NOTE}",
)
TAP_CALLOUT_QUALIFIER = "\n".join(TAP_CALLOUT_LINES)
# The span and the tip serve the one mesh: each links the GEAR DATA block,
# which names the mate once.  The span's .0007 band is under the milled row
# and still controls (paper_drive_mesh_check reads the span-inverted cutter
# translations for backlash, root clearance and contact ratio), so its
# callout names its fit route, a matched fit with MHA-PD-08 accepted by the
# block's backlash row (rule 4: matching does not waive the limits).  One
# line: the sheet's above-callout lane prints a single line (round 2 printed
# nothing of a two-line one), 22 characters keeping it left of the
# tooth-space control's leader.
SPAN_CALLOUT = "MATCHED, SEE GEAR DATA"
MESH_CALLOUT = "SEE GEAR DATA"
# The .XXX thickness is the screw engagement's: its least is the tapped
# length (pd_vn_transgear_disc_screw_spec), and .XX would cut that below
# 1.5D.
FACE_WIDTH_CALLOUT = f"SETS {SCREW_NUMBER}\nENGAGEMENT"

_CLEARANCE = "-".join(inch_text(value, 4) for value in SPIGOT_DIAMETRAL_CLEARANCE)
# Rule 20: the tap-to-bore web's stated shortfall (RV-03) ends the tap note.
DRAWING_NOTES = "\n".join(
    (
        f"{BORE_NOTE}. LOCATIONAL CLEARANCE FIT ON {HUB_NUMBER} SPIGOT",
        f"   (CLEARANCE {_CLEARANCE} REF).",
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
if not (
    BACKLASH_BUDGET_MM[0]
    <= BACKLASH_ACCEPT_MM[0]
    < BACKLASH_ACCEPT_MM[1]
    <= BACKLASH_BUDGET_MM[1]
):
    raise AssertionError(
        f"MHA-PD-06 backlash acceptance {BACKLASH_ACCEPT_MM} leaves the budget "
        f"{BACKLASH_BUDGET_MM}"
    )

# What a machinist needs to cut and check the teeth (Main ruling 2026-10-10):
# the cutting rows, the mate and the backlash acceptance that is the span
# band's fit route (rule 4).  The span prints on the face view with its
# limits, not again here.
_GEAR_DATA_ROWS = (
    ("NUMBER OF TEETH", f"{TEETH}"),
    ("DIAMETRAL PITCH", f"{DIAMETRAL_PITCH:.2f}"),
    ("PRESSURE ANGLE", f"{PRESSURE_ANGLE_DEG:.1f} DEG"),
    ("PITCH DIAMETER (REF)", inch_text(PITCH_DIA, 4)),
    ("WHOLE DEPTH (REF)", inch_text(WHOLE_DEPTH, 4)),
    (
        "CUTTER",
        # #1 is open-ended (135T to rack): print the catalogue's range.
        f"#{CUTTER_NUMBER}, {CUTTER_TOOTH_RANGE[0]}T-RACK"
        if CUTTER_TOOTH_RANGE[1] is None
        else f"#{CUTTER_NUMBER}, {CUTTER_TOOTH_RANGE[0]}-{CUTTER_TOOTH_RANGE[1]}T",
    ),
    ("MATES WITH", f"KNOB SHAFT {KNOB_NUMBER}, {MESH_PINION_TEETH}T"),
    (
        "SPAN MATCHED FIT",
        "BACKLASH WITH MATE "
        + "-".join(inch_text(value, 3) for value in BACKLASH_ACCEPT_MM)
        + ", FEELER",
    ),
)
GEAR_DATA_NOTE = "\n".join(
    ("GEAR DATA", *(f"{label}:  {value}" for label, value in _GEAR_DATA_ROWS))
)
