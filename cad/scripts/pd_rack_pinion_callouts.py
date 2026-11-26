"""Sheet text for the MHA-PD-06 reducer disc drawing.

Drawing-only: imported by ``draw_pd_rack_pinion`` (and its test), never by
the part builder, so rewording the sheet re-keys only the drawing.
``pd_rack_pinion_spec``, which the part, the feed pinion, the disc hub and
the paper-drive assembly import, keeps the geometry and limits; every value
printed here is read from it.

drawing-guidelines.md rule 7: a callout carries its size and process lines
plus at most two lines of words; anything longer is a numbered note its
callout links by ``SEE NOTE n``.  Rule 4: the reamed bore prints no band;
its note names the mate, says that mate is turned to this bore (the
acceptance, a clearance, prints once, on MHA-PD-17, made last) and what the
ream protects (the
necessity answer); one feature with several tight dimensions (the teeth:
span and tip) names its mate once, in the GEAR DATA block both dimensions
link.
"""

from __future__ import annotations


from pd_rack_pinion_spec import (
    BORE_FRONT_CHAMFER,
    CUTTER_NUMBER,
    CUTTER_TOOTH_RANGE,
    DIAMETRAL_PITCH,
    HUB_NUMBER,
    MESH_PINION_TEETH,
    MOUTH_BREAK_MAX,
    PITCH_DIA,
    PRESSURE_ANGLE_DEG,
    TAP_WALL_TEXT,
    TEETH,
    WHOLE_DEPTH,
    inch_text,
)
from pd_paper_drive_assembly_steps import step_ref

# The trial mesh is MHA-PD-00's located step (12K-12N), where the pair runs
# together on its real seats before the plate is doweled.
TRIAL_MESH_STEP = step_ref("arm-plate-located")

KNOB_NUMBER = "MHA-PD-08"
SCREW_NUMBER = "MHA-SH-VN-59"
BORE_NOTE = 1
TAP_NOTE = 2

# The reamed bore: process then depth under its native size (rule 26:
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
# block's last row (rule 4: matching does not waive the limits).  One
# line: the sheet's above-callout lane prints a single line (round 2 printed
# nothing of a two-line one), 22 characters keeping it left of the
# tooth-space control's leader.
SPAN_CALLOUT = "MATCHED, SEE GEAR DATA"
MESH_CALLOUT = "SEE GEAR DATA"
# The .XXX thickness is the screw engagement's: its least is the tapped
# length (pd_transgear_disc_screw_spec), and .XX would cut that below
# 1.5D.
FACE_WIDTH_CALLOUT = f"SETS {SCREW_NUMBER}\nENGAGEMENT"

# Rule 4, form 2: the bore's mate is made to this bore (the MHA-PD-17
# spigot prints REF and the clearance,
# the pair's one acceptance).  What the ream protects is the register's
# (cad/config/necessity/pd-rack-pinion.yaml; owner ruling 2026-11-24: the
# reason is not printed on the sheet).
# Rule 20: the tap-to-bore web's stated shortfall (RV-03) ends the tap note.
DRAWING_NOTES = "\n".join(
    (
        f"{BORE_NOTE}. {HUB_NUMBER} SPIGOT IS TURNED TO THIS BORE.",
        f"{TAP_NOTE}. MATCH-DRILL AT ASSEMBLY WITH {HUB_NUMBER}: SPOT THRU ITS FLANGE",
        f"   HOLES, THEN DRILL AND TAP; MATCH-MARK BOTH. {TAP_WALL_TEXT}.",
    )
)

# What a machinist needs to cut and check the teeth (Main ruling 2026-10-10):
# the cutting rows, the mate and the acceptance that is the span band's fit
# route (rule 4): the pair runs together with no tight spot, tried at
# MHA-PD-00's trial mesh.  No backlash number prints: a feeler leaf cannot be
# laid between 48DP flanks (#2417), and MHA-PD-00 reads the mesh's shake on a
# dial indicator (owner ruling 2026-11-24, audit part 2 question C2: "Yes.",
# the feeler row deleted).  MHA-PD-08's GEAR DATA prints the same rows.  The
# span prints on the face view with its limits, not again here.  The SPAN row
# says the limits are cut to and the trial mesh proves the pair (drawing-
# guidelines rule 4 form 4: gear tooth data keep the gear data block's rules,
# rule 7; fit audit part 2, B7); the limits stay as printed (a wider band is
# unproven: the mesh check reads the profiles derived from them, MHA-PD-06
# RV-04).  ACCEPTED is a word the sheet may not print (rule 20).
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
    ("SPAN", f"CUT TO THE LIMITS SHOWN; PROVED AT\n   {TRIAL_MESH_STEP} BY THE TRIAL MESH"),
    ("SPAN MATCHED FIT", "RUNS ON MATE WITH NO TIGHT SPOT"),
)
GEAR_DATA_NOTE = "\n".join(
    ("GEAR DATA", *(f"{label}:  {value}" for label, value in _GEAR_DATA_ROWS))
)
