r"""Create the manufacturing drawing for the transgear knob shaft (MHA-PD-08).

A turned side view, aligned rear and front end views, a 10:1 detail of the
front neck, VIEW C (the gear end from the stud tip at 4:1, named by a viewing
arrow on the side view), and an isometric.
The side view imports the source-owned turned sizes; each chucking's
lengths run from its faced end: the stud's stations from the tip face, the
controlled overall to the rear face, the journal a reference.  Each tight
band names its mate once: the journal's running fit and the D-section's
sliding fit are numbered notes their callouts link by "SEE NOTE n"
(drawing-guidelines.md rule 4), and the mesh with the disc is the gear data
block's, the span's matched fit accepted by its last row.  The front
end view carries the D-flat's distance from the
axis, where the flat shows true, and the leadered tooth-edge note.  VIEW C
carries the gear's native acceptance dimensions: the span over two teeth
(LIMITS) and the root envelope (MIN).  The rear view identifies the actual
running journal datum and calls out the rear #2-56 tap natively.  The #8-32 thread callout belongs to its real thread
blank.  Cutter identity and approved inspection controls are properties of
the saved source, never values retyped here.
The source-linked formed-flank callout carries radial TIR, the paid
pitch-index range at REF pitch diameter, all-space/wrap receiving and the
certified pin. Neither span thickness nor a pin-centre radius substitutes
for that independent index control.
The rear end is tapped #2-56 for the MHA-PD-VN-71 cup screw; the front
D-core has no crosshole. This script does not certify a native build or release a prototype
toothspace runout grade.
"""

from __future__ import annotations

import argparse
import math
import sys
import textwrap
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    dimension_name,
    place_view,
    remove_notes_matching,
)

import _config
from _check import check
from _com import _early_bound
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
    view_name,
)
from _column_clamp_drawing import set_hole_callout_below
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_finish import add_surface_finish
from _drawing_gdt import add_datum_feature, add_feature_control_frame
from _drawing_leader_notes import add_attached_note, add_leader_note
from _drawing_view_arrow import square_view_arrow
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _gear_drawing_entities import visible_circle_edge
from _hole_callout_thread_class import omit_title_block_thread_class
from _holes import DIAMETER_TOLERANCE_MM, _verify_tap_metadata
from _gtol_face_resolve import resolve_faces
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _part_properties import part_drawing_unit
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from paper_drive_stock_drawing import add_toothspace_callout, require_source_control
import pd_transgear_knob_bush_geometry as BUSH
from pd_transgear_knob_shaft_spec import (
    CORE_DIA,
    CORE_FRONT_Z,
    CUTTER_NUMBER,
    CUTTER_TOOTH_RANGE,
    FRONT_CORNER_RADIUS,
    FRONT_RELIEF_DIA,
    FRONT_RELIEF_WIDTH,
    DIAMETRAL_PITCH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FACE_WIDTH,
    FACE_WIDTH_CALLOUT,
    JOURNAL_DIA,
    JOURNAL_DIA_BAND,
    OUTSIDE_DIA,
    PLAIN_CORE,
    PRESSURE_ANGLE_DEG,
    GEOMETRIC_CONTROLS,
    GEOMETRIC_TOLERANCES_IN,
    GEOMETRIC_TOLERANCES_MM,
    PART_DATUMS,
    REAR_END_Z,
    REAR_TAP_DEPTH_PLACES,
    REAR_TAP_DRILL_DEPTH,
    REAR_TAP_DRILL_DIA,
    REAR_TAP_DRILL_DIA_PLACES,
    REAR_TAP_FULL_THREAD_MIN,
    REAR_TAP_SPEC,
    PITCH_DIA,
    SURFACE_FINISHES,
    STOCK_PROFILE,
    GAP_AZIMUTH_DEG,
    SPAN_TEETH,
    SINGLE_MAX_SUFFIX,
    SINGLE_MIN_SUFFIX,
    TOOTH_SPACE_GAUGE_PIN_DIA_MM,
    TOOTH_SPACE_CALLOUT,
    TOOTH_SPACE_CALLOUT_PROPERTY,
    TEETH,
    THREAD_CALLOUT,
    TIP_CHAMFER,
    TIP_CHAMFER_CALLOUT,
    TIP_STATION,
    WHOLE_DEPTH,
    TIP_Z,
    inch_text,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_transgear_knob_shaft"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

# The retained shaft stations fit at 3:1. Inspection carriers use a separate
# aligned front end view, not the journal-obscured rear projection.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
# 2 mm left of 0.183: the 3/8 arm's longer journal (#2019) adds 4.7 mm at
# 3:1, split between the GEAR DATA block's margin (its backlash row wrapped
# shorter) and the tip side's chamfer callout and notes.
SIDE_CENTER = (0.181, 0.160)
# Third-angle: the rear face is the side view's LEFT end, so the view from
# the rear stands left of it, on the shaft axis.
END_CENTER = (0.045, SIDE_CENTER[1])
FRONT_CENTER = (0.335, SIDE_CENTER[1])
# Upper right, over the tooth-edge note.
ISO_CENTER = (0.370, 0.228)
ISO_SCALE = (1, 1)
_BBOX_MID_Z = (TIP_Z + REAR_END_Z) / 2.0


def _sheet_x(model_z_mm: float) -> float:
    """Sheet X of a model-Z station on the side view (model +Z runs left).

    The view is centred on the model bbox, stud tip to rear face.
    """
    return SIDE_CENTER[0] + (_BBOX_MID_Z - model_z_mm) * _S / 1000.0


def _sheet_y(radius_mm: float) -> float:
    """Sheet Y of a point ``radius_mm`` above the shaft axis (model +Y up)."""
    return SIDE_CENTER[1] + radius_mm * _S / 1000.0


REAR_X = _sheet_x(REAR_END_Z)
PINION_REAR_X = _sheet_x(FACE_WIDTH)
F_X = _sheet_x(0.0)
CORE_END_X = _sheet_x(CORE_FRONT_Z)
THREAD_END_X = _sheet_x(-PLAIN_CORE)
TIP_X = _sheet_x(TIP_Z)
# Where the thread blank meets the tip chamfer.
CHAMFER_START_X = _sheet_x(-(TIP_STATION - TIP_CHAMFER))
HALF_OD = OUTSIDE_DIA * _S / 2000.0

# Turned sizes stay beside their own axial regions. Baseline lengths nest
# below F. The D-flat's distance from the axis reads in the end view from
# the tip, where the flat shows true (END_KEEP).
_ABOVE_Y = SIDE_CENTER[1] + HALF_OD + 0.016
_ROW_PITCH = 0.010
_ROW_Y = tuple(SIDE_CENTER[1] - HALF_OD - 0.016 - i * _ROW_PITCH for i in range(6))
# The overall's text stands 1.5 mm over its row: on it, VIEW C's span text
# (top 76.3 mm) stood 2.39 mm under it and read as one callout (the audit
# wants 3.57; r4 and r6).  The face width's block above it ends right of the
# pinion's witness line, so the lift meets nothing.
_OVERALL_LIFT = 0.0015
# Mates named once at their tight bands (drawing-guidelines rule 4), by the
# config's part name (less the family's "TRANSGEAR") and number.
THUMBNUT_NUMBER = _config.parts("pd-transgear-thumbnut")["number"]


def _mate_name(part: dict) -> str:
    """A mate as the shop reads it: its config title, less the family word
    every part on the sheet shares, and its part number. Callers read the row
    by a literal key, so the drawing's config inputs stay per-row."""
    title = part["title"].upper().removeprefix("TRANSGEAR ")
    return f"{title} {part['number']}"


# The journal is made to fit (drawing-guidelines rule 4, form 2): turned
# last to the MHA-PD-28 bush's reamed bore and tried
# in it, so it prints REF and no limits.  JOURNAL_DIA_BAND stays the
# ANALYSIS band (the modelled result of that fitting) and this the
# clearance the stacks consume; neither prints.
JOURNAL_CLEARANCE_MM = (
    BUSH.BORE_DIA + min(BUSH.BORE_DIA_LIMITS) - (JOURNAL_DIA + max(JOURNAL_DIA_BAND)),
    BUSH.BORE_DIA + max(BUSH.BORE_DIA_LIMITS) - (JOURNAL_DIA + min(JOURNAL_DIA_BAND)),
)
# The numbered notes the bands link by "SEE NOTE n": the journal's running
# fit; the D-section's one sliding fit, which its Ø and its flat's distance
# from the axis link; the D-flat seat the two .XXX tip stations locate and
# the full thread the third bounds (round 2: printed .XXX with no stated
# function), one reason each with no values in the text (machinist review
# r1 of #2019, rule 7); and the neck's mate, which its Ø limits and the
# flat's end limits link (round 2: the flat end's .005 band named no mate).
# The journal's length is the controlled one at .XX and the overall a .XX
# reference.  They stand in the open field right of the
# overall's tip witness line, over the title block; at 2.2 mm a line runs
# ~1.5 mm a character, so no line runs past 70 characters (~105 mm).
JOURNAL_FIT_NOTE = 1
D_SECTION_FIT_NOTE = 2
STATIONS_NOTE = 3
NECK_NOTE = 4
THREAD_NOTE = 5
NOTES_LINE_CHARS_MAX = 70
_COLLAR = _mate_name(_config.parts("pd-transgear-drive-collar"))
NOTE_TEXTS = (
    (
        JOURNAL_FIT_NOTE,
        f"RUNNING FIT IN {_mate_name(_config.parts('pd-transgear-knob-bush'))}: "
        "TURN TO ITS REAMED BORE, TURNS FREE WITH NO SHAKE.",
    ),
    # Made to fit (owner ruling 2026-11-24, fit audit question 7): the
    # collar's bore is drilled and its pin pressed first; the core's Ø and
    # the flat's distance print as REF and link this note, whose two fits by
    # feel are the requirement.  No reason prints (owner ruling 2026-11-24:
    # a justification on the sheet is narration).  The acceptance prints
    # here once, on the member made last; MHA-PD-22's bore callout names
    # this core.  The pressed pin's crest stands inside the bore from the
    # rear face to its floor, so the round core is tried from the pilot end,
    # where the bore is clear of it (Codjiflo r2 on #3485).
    (
        D_SECTION_FIT_NOTE,
        f"MADE TO FIT {_COLLAR}: CORE ENTERS ITS BORE FROM THE PILOT END UP TO "
        "THE PIN BY HAND, NO SHAKE; D-FLAT: COLLAR WITH PIN PRESSED SLIDES ON BY "
        "HAND.",
    ),
    (STATIONS_NOTE, f"D-FLAT SEAT UNDER {_COLLAR}."),
    # The flat's end prints .007 MAX from F with no lower limit, so the note
    # says the tool stops short of F (Codjiflo r2 on #3485).
    (NECK_NOTE, f"NECK AND D-FLAT END UNDER {_COLLAR}; GEAR FACE UNCUT."),
    (THREAD_NOTE, f"FULL THREAD FOR {_mate_name(_config.parts('pd-transgear-thumbnut'))}."),
)
# Rule 7: a note runs to four short lines at most.
NOTE_LINES_MAX = 4
NOTE_LINES = tuple(
    tuple(
        textwrap.wrap(f"{number}. {text}", NOTES_LINE_CHARS_MAX, break_on_hyphens=False)
    )
    for number, text in NOTE_TEXTS
)
if max(map(len, NOTE_LINES)) > NOTE_LINES_MAX:
    raise AssertionError("a numbered note runs past four lines")
NOTES = "\n".join(("NOTES:", *(line for lines in NOTE_LINES for line in lines)))
if max(map(len, NOTES.splitlines())) > NOTES_LINE_CHARS_MAX:
    raise AssertionError("a numbered note line runs past the open field")
JOURNAL_FIT_LINK = f"SEE NOTE {JOURNAL_FIT_NOTE}"
D_SECTION_FIT_LINK = f"SEE NOTE {D_SECTION_FIT_NOTE}"
STATIONS_LINK = f"SEE NOTE {STATIONS_NOTE}"
NECK_LINK = f"SEE NOTE {NECK_NOTE}"
THREAD_LINK = f"SEE NOTE {THREAD_NOTE}"

# The gear's tip and span bands are set by the mesh with MHA-PD-06, which the
# GEAR DATA block names (MATES WITH); their fit route is the block's last
# row, as MHA-PD-06's block words it: the pair runs together with no tight
# spot, tried at MHA-PD-00's trial mesh.  No backlash number prints (owner
# ruling 2026-11-24, audit part 2 question C2: "Yes.", the feeler row
# deleted: a leaf cannot be laid between 48DP flanks, #2417).  The span's
# limits still print and control (the mesh check
# derives its gates from SPAN_LIMITS), so the span is not a reference.
# What a machinist needs to cut and check the teeth (Main ruling 2026-10-10):
# the cutting rows, the mate and the acceptance that is the span
# band's fit route (rule 4).  The span prints in VIEW C with its limits, not
# again here.  The mate's number and the last row's tail wrap so the block
# ends left of the overall's rear witness line (REAR_X): on the 3/8 arm's
# longer shaft (#2019) the one-line mate ran under it (machinist review r1).
GEAR_DATA_ROWS = (
    ("NUMBER OF TEETH", f"{TEETH}"),
    ("DIAMETRAL PITCH", f"{DIAMETRAL_PITCH:.2f}"),
    ("PRESSURE ANGLE", f"{PRESSURE_ANGLE_DEG:.1f} DEG"),
    ("PITCH DIAMETER (REF)", inch_text(PITCH_DIA, 4)),
    ("WHOLE DEPTH (REF)", inch_text(WHOLE_DEPTH, 4)),
    ("CUTTER", f"#{CUTTER_NUMBER}, {CUTTER_TOOTH_RANGE[0]}-{CUTTER_TOOTH_RANGE[1]}T"),
    ("MATES WITH", "\n   ".join(_mate_name(_config.parts("pd-rack-pinion")).rsplit(" ", 1))),
    ("SPAN MATCHED FIT", "RUNS ON\n   MATE WITH NO TIGHT SPOT"),
)
GEAR_DATA_NOTE = "\n".join(
    ("GEAR DATA", *(f"{label}:  {value}" for label, value in GEAR_DATA_ROWS))
)
# An above callout prints only as ONE line (a line break there is stored but
# never printed: farm run 20261031T205208603Z's four mate callouts went
# unmatched), set as one run centred on its dimension's text: 40 characters
# read 110.6 mm (draw_dt_cone_gear_shaft), and the shoulder under a Ø's text
# spans that run (this sheet's journal: 38 characters, 104.3 mm). Each block
# runs from 7.3 mm under its keep to 8.7 mm over it plus the callout row.
ABOVE_CALLOUT_CHAR_WIDTH = 0.1106243 / 40
_DIA_ROW_PITCH = 0.0205
# The journal's row, 3 mm under the first row (its shoulder 10 mm over the
# journal), so the staircase's top block stays 6 mm under the border.
_DIA_ROW_Y = tuple(_ABOVE_Y - 0.003 + i * _DIA_ROW_PITCH for i in range(4))
# The vertical Ø texts climb in a staircase, one row each: the journal's
# hangs RIGHT of its line (left of the view's centre) and ends left of the
# pinion's line; every other text hangs LEFT, so each line to the right
# rises past the blocks on its left, and no shoulder runs over a line
# (that run: the journal's shoulder at its row crossed the core's and the
# relief's lines).
SIDE_KEEP: dict[str, tuple[float, float]] = {
    "OutsideDia": (F_X - 0.0015, _DIA_ROW_Y[1]),
    "CoreDia": ((F_X + CORE_END_X) / 2.0, _DIA_ROW_Y[2]),
    # Run 12: from the relief's mid the hung text's shoulder started left of
    # F's witness line (214.4) and ran through the front-neck frame. Four
    # fifths along the relief it started right of F, above that frame;
    # #2425's shorter journal re-centred the view, so it now stands 19/20
    # along, its text's left end right of detail B's core frame.
    "ReliefDia": ((CORE_END_X + 19.0 * THREAD_END_X) / 20.0, _DIA_ROW_Y[3]),
    # A Ø's line stands at its point; right of the view's centre the text
    # hangs LEFT of it (the pinion's and core's, run 20261001T085006647Z), and
    # the blank's banded text and shoulder run 27.5 mm (19e33c6c2: from the
    # blank's mid the shoulder crossed the relief's line).  9 mm in from the
    # chamfer the line stays 9 mm off the thread callout's leader to the
    # chamfer.
    "ThreadBlankDia": (CHAMFER_START_X - 0.009, _ABOVE_Y),
    # 1.5 mm left of mid-journal, right of detail B's crop: its one-line run
    # hangs right of the line, short of the pinion's line.
    "JournalDia": ((PINION_REAR_X + REAR_X) / 2.0 - 0.0015, _DIA_ROW_Y[0]),
    # Its three-line block (~58 mm wide with "DISC CLUSTER STACK WITH") is
    # wider than the 17.7 mm between its witness lines, so it stands outside
    # right of F's (217.7): text ~218.6..277 mm, left of the tip's witness
    # line (289.4), over the overall's line on the last row.
    "FaceWidth": (F_X + 0.030, _ROW_Y[4]),
    # The stud chucking's stations run from the faced tip (rule 11): the
    # thread's end, the core's front and F stack outward on rows 0-2 from the
    # tip's witness line; each starts right of the next one's foot, so no
    # witness line crosses a dimension line.
    "ThreadEndFromTip": ((THREAD_END_X + TIP_X) / 2.0, _ROW_Y[0]),
    "CoreFromTip": ((CORE_END_X + TIP_X) / 2.0, _ROW_Y[1]),
    "TipStation": ((F_X + TIP_X) / 2.0, _ROW_Y[2]),
    # The journal, pinion rear face to rear end: controlled, .XX.
    "JournalLength": ((PINION_REAR_X + REAR_X) / 2.0, _ROW_Y[0]),
    # The reference overall, tip face to rear face, on the last row, its
    # rear witness line right of the gear data block.  Its text centres
    # between the rear witness line and the pinion's rear witness line
    # (round 3: text left of F ran into the face width's left witness line
    # and arrow, which drop to the overall text's height); OVERALL_TEXT_*
    # below check both ends.
    "OverallLength": ((REAR_X + PINION_REAR_X) / 2.0, _ROW_Y[5] + _OVERALL_LIFT),
    # #2425: the rear chamfer's leg, under the rear end (REAR_CHAMFER_FUNCTION).
    "RearChamferSize": (REAR_X + 0.030, _sheet_y(-JOURNAL_DIA / 2.0) - 0.0065),
}
END_KEEP: dict[str, tuple[float, float]] = {
    # The flat's distance from the axis, where the flat shows true (machinist
    # review r7: in the side view its line ran over the #8-32 thread, level
    # with the thread's lower edge, so it read as the thread's radius).  The
    # line stands 5 mm right of the tooth tips; the limits and the note link
    # hang right of it, their top under the flat's arrow and over the
    # tooth-space note (y <= 112.4).
    "FlatToAxis": (FRONT_CENTER[0] + HALF_OD + 0.005, FRONT_CENTER[1] - 0.022),
}
# Callouts over the vertical Ø texts (a below-callout there would sit on
# the Ø's own line unless it starts a space off it, as the journal's rear
# chamfer row does), each one line.  Every kept tight band prints its
# matched-fit route at its callout (delegated ruling 2026-11-07 (Main) F5):
# the tooth tips link the gear data block, which names the mesh mate and its
# backlash acceptance; the thread relief's is a plain clearance.
GEAR_DATA_LINK = "SEE GEAR DATA"
DIMENSION_CALLOUTS_ABOVE = {
    "JournalDia": JOURNAL_FIT_LINK,
    "OutsideDia": GEAR_DATA_LINK,
    "CoreDia": D_SECTION_FIT_LINK,
    "ReliefDia": f"CLEARS THUMBNUT {THUMBNUT_NUMBER}",
}
if any("\n" in text for text in DIMENSION_CALLOUTS_ABOVE.values()):
    raise AssertionError("an above-callout with a line break does not print")
# The face width's ±band names the disc cluster stack (rule 4); its one
# line hangs into the empty sixth baseline row below it.  The flat's link
# hangs under its text, past the end of its witness line.  The span's
# limits still control: its callout names the matched fit and links the
# GEAR DATA block's backlash acceptance, worded as MHA-PD-06's span callout
# (two lines of words under "SPAN 2 TEETH" and its limits).  Lengths and
# locations print their values alone.
# #2425: the journal's .015 X 45° rear chamfer prints as its own sketch
# dimension (JournalProfile RearChamferSize, the axial leg) under the rear
# end, " X 45°" its suffix and the function of its third place on the row
# under it (pd_transgear_knob_shaft_spec: the least leg clears the MHA-PD-16
# pilot's floor corner).  Over the rear corner it sat on detail B's ".016
# SEE NOTE 4" and ".007" (farm r6); as a "REAR END" row of the journal Ø's
# callout nothing tied it to the chamfer and its third place stated no
# function (machinist review r10, three runs); a native chamfer dimension
# needs the chamfer's silhouette, and that sweep of the toothed side view
# crashed SOLIDWORKS three times (farm r11).  Below the shaft its two
# extension lines drop from the upper corner along the rear face's line and
# the chamfer's own edge line (both drawn edge-on), then on under the lower
# corner to the dimension line, where the journal's finish stood (that moved
# right, JOURNAL_FINISH_PICK).  The value row (~26 mm) and the function row
# (16 characters, at most 44.3 mm) centre 30 mm right of the rear end: right
# of the rear witness line (77.3) and left of the journal Ø's lower arrow
# (134.8), 4.5 mm under the outline (150.5) and over the journal length's
# line (127.6).
REAR_CHAMFER_SUFFIX = " X 45\u00b0"
REAR_CHAMFER_FUNCTION = f"CLEARS {_config.parts('pd-transgear-knob-cup')['number']}"
REAR_CHAMFER_BLOCK_HALF_WIDTH = (
    len(REAR_CHAMFER_FUNCTION) * ABOVE_CALLOUT_CHAR_WIDTH / 2.0
)
SPAN_CALLOUT = f"MATCHED FIT,\n{GEAR_DATA_LINK}"
DIMENSION_CALLOUTS_BELOW = {
    "FaceWidth": FACE_WIDTH_CALLOUT,
    "FlatToAxis": D_SECTION_FIT_LINK,
    "ToothSpan": SPAN_CALLOUT,
    "RearChamferSize": REAR_CHAMFER_FUNCTION,
    "FlatEnd": NECK_LINK,
}
# The two D-flat stations link the seat note and the thread's end the thread
# note, each on its value's line; detail
# B's neck Ø (LIMITS) links the neck note on its value's line and the D-flat
# end's single MAX on the row under it (".007 MAX SEE NOTE 4" on one line
# would run from F's witness line out over the end view), which
# names both features and MHA-PD-22 once.  The note names the D-flat end in
# words (round-4 repeat read a bare link as locating the neck corner's
# tangent; round 5
# read a bare `FLAT END` label as coined and unlinked).  (A row under the
# neck Ø would top out past the border, and the side rows stand 10 mm apart.)
# The four single limits carry no native tolerance: SolidWorks prints its
# own as "max." and "min." (rule 26), so the limit word is the suffix.
DIMENSION_SUFFIXES = {
    "RearChamferSize": REAR_CHAMFER_SUFFIX,
    "ThreadEndFromTip": f" {THREAD_LINK}",
    "CoreFromTip": f" {STATIONS_LINK}",
    "TipStation": f" {STATIONS_LINK}",
    "FrontReliefDia": f" {NECK_LINK}",
    "FlatEnd": SINGLE_MAX_SUFFIX,
    "FlatToolRadius": SINGLE_MAX_SUFFIX,
    "FrontCornerRadius": SINGLE_MAX_SUFFIX,
    "RootDia": SINGLE_MIN_SUFFIX,
    # Round 7: the neck width keeps .XXX (at .XX its least, .006, falls
    # under the flat end's .007) and links the neck note like its neighbours.
    "FrontReliefWidth": f" {NECK_LINK}",
}
# The overall prints as a .XX reference: the journal's length is the
# controlled dimension (pd_transgear_knob_shaft_spec.JOURNAL_LENGTH_PLACES),
# so no three-place overall needs a function the sheet may not state.
# The overall's one-line text (~2.75 mm a character, centred on its keep;
# the round-6 render's digits ran 2.32 mm) ends 5 mm short of the face
# width's left witness line (the pinion's rear face, which drops to the
# text's height with its arrow) and starts 5 mm right of the rear witness
# line.  It sits over the overall's line; SPAN 2 TEETH and the GEAR DATA
# block stand under that line and left of the rear witness line.
OVERALL_TEXT_CHARS = len(f"({inch_text(REAR_END_Z - TIP_Z, 2)})")
_OVERALL_HALF = OVERALL_TEXT_CHARS * 0.00275 / 2.0
OVERALL_TEXT_LEFT = SIDE_KEEP["OverallLength"][0] - _OVERALL_HALF
OVERALL_TEXT_RIGHT = SIDE_KEEP["OverallLength"][0] + _OVERALL_HALF
if OVERALL_TEXT_RIGHT > PINION_REAR_X - 0.005:
    raise AssertionError("the overall's text runs into the face width's witness line")
if OVERALL_TEXT_LEFT < REAR_X + 0.005:
    raise AssertionError("the overall's text runs over the rear witness line")
# Reference sizes (parenthesized): the overall (the journal's length
# controls the rear end), the journal's Ø (made to fit the bush's reamed
# bore, note 1), the thread blank the #8-32 UNC-2A class governs, and the
# D-core's Ø and its flat's distance from the axis, both made to fit
# MHA-PD-22 (note 2).  Name -> diameter glyph.
REFERENCE_DIMENSIONS = {
    "OverallLength": False,
    "JournalDia": True,
    "ThreadBlankDia": True,
    "CoreDia": True,
    "FlatToAxis": False,
}

# The thread callout lands on the edge where the thread blank meets the tip
# chamfer and stands up and left, clear of the tooth-tip Ø over the pinion.
# Its right end (~39.2 mm from the anchor) stops 0.5 mm short of the pick,
# so the leader drops plumb from that end: centred over the blank, it ran
# down and left through its own second line (farm run 20261101T095301211Z).
THREAD_PICK = (CHAMFER_START_X, SIDE_CENTER[1] + 0.002)
THREAD_NOTE_XY = (THREAD_PICK[0] - 0.0397, _ABOVE_Y + 0.020)
# The tip chamfer's callout stands under the tip, its leader climbing to the
# same blank/chamfer edge from below, right of the tip's witness lines.  On
# one line it ran 64 mm, under the front view and through the tooth-space
# note's leader (farm run 20261031T205208603Z); its two 2.78 mm-a-character
# lines end ~39 mm right of the anchor, short of that leader (x 337..340 mm
# at the callout's rows).
TIP_CHAMFER_NOTE = TIP_CHAMFER_CALLOUT.replace(" TO ", "\nTO ")
CHAMFER_PICK = (CHAMFER_START_X, SIDE_CENTER[1] - 0.002)
CHAMFER_NOTE_XY = (TIP_X + 0.004, SIDE_CENTER[1] - HALF_OD - 0.002)
# The running journal owns the one finish, in the side view where the
# journal reads alone: in the rear end view its leader landed where the
# journal circle meets the teeth and read as a finish on the teeth
# (machinist review r5).  The native symbol's V tip stands at its position,
# its leader runs 6.35 mm level toward the landing then to it, and its
# "Ra" text tops out ~10.3 mm over the tip (run 20261101T004958072Z's end
# view symbol).  Under the journal's right half the symbol stands 3 mm
# below the outline, right of the journal Ø's lower arrow (134.8 mm) and the
# journal length's "(1.55)" (to 144.8) and left of the pinion (195.4): the
# rear chamfer's dimension took its place under the left half (r10).
# The symbol attaches to the journal's controlled cylindrical model FACE,
# resolved on the referenced part, its leader landing here on the lower
# outline: a hit-tested SILHOUETTE re-solved onto another face after
# insertion (farm r5 of #2425, same_entity=False), as on MHA-PD-23's shank
# and MHA-DT-27's (draw_pd_transgear_pin, draw_dt_pinion_cam_pin).
JOURNAL_FINISH_PICK = (REAR_X + 0.083, _sheet_y(-JOURNAL_DIA / 2.0))
JOURNAL_FINISH_SYMBOL = (REAR_X + 0.088, JOURNAL_FINISH_PICK[1] - 0.0135)
# A point on the journal's face for the turning axis.
CENTERLINE_PICK = ((PINION_REAR_X + REAR_X) / 2.0, SIDE_CENTER[1] + 0.003)
# Lower left, under the journal's 40.938 row (y 0.133), at MHA-PD-06's
# block height.  A line of capitals runs ~0.68 of the height a character
# (round-1 render: 39 characters at 2.5 mm ran 66 mm), so the block's
# widest line ends left of the overall's and the journal's rear witness line
# (REAR_X), which drops past the block to the last row (round 1: the
# backlash row ran under it).
GEAR_DATA_XY = (0.016, 0.118)
GEAR_DATA_CHAR_HEIGHT = 0.0022
NOTE_CHAR_WIDTH_PER_HEIGHT = 0.68
NOTE_LINE_PITCH_PER_HEIGHT = 1.24
GEAR_DATA_RIGHT = GEAR_DATA_XY[0] + max(
    map(len, GEAR_DATA_NOTE.splitlines())
) * NOTE_CHAR_WIDTH_PER_HEIGHT * GEAR_DATA_CHAR_HEIGHT
if GEAR_DATA_RIGHT > REAR_X - 0.003:
    raise AssertionError("the GEAR DATA block runs under the rear witness line")
# The numbered notes in the open field right of the overall's tip witness
# line (289.7) at the gear data's height: their top under the tooth-space
# note (bottom ~0.106), their bottom over the title block (top ~0.0663),
# their right end inside the border (0.4191 - 0.0127).
NOTES_XY = (0.300, 0.100)
TITLE_BLOCK_TOP = 0.0663
NOTES_CHAR_HEIGHT = GEAR_DATA_CHAR_HEIGHT
# Datum A stands on the journal's own upper outline in the side view, where
# only the journal can be meant: on the rear view's journal circle its
# triangle read as resting on the tooth-root circle .005 outside it
# (machinist review r2 of the fit batch).  A turned flank is a drawing
# SILHOUETTE.  The tag stands between detail B's kept texts (right ends
# ~0.100) and the journal Ø's line (0.1348), under the detail's crop.
DATUM_A_PICK = (REAR_X + 0.041, _sheet_y(JOURNAL_DIA / 2.0))
DATUM_A_SYMBOL = (DATUM_A_PICK[0], DATUM_A_PICK[1] + 0.011)
# The rear #2-56 tap's native callout, from the rear view's hole to the open
# field under the journal.  Its leader lands on the lower corner of the
# rows' underline, so rows that straddle the hole's x are struck by it
# (r7 of #2425: centred under the rear view, the leader hid the "#" of
# "#2-56" and the rows stood 1.6 mm over GEAR DATA), and the rear view has
# no 47 mm clear of the border beside or above it (r6: 16 mm past the left
# border).  Right of the rear witness line (77.3) the rows (~47 mm wide,
# ~14.5 mm tall, centred on the point) run x 83.3-130.3 mm and y
# 102.7-117.3 mm: under the journal's REF length line (y ~128), over the
# overall's (y ~82) and right of the GEAR DATA block; the leader crosses
# only the rear witness line, an extension line (rule 14).  The drill and
# the full thread at their places (rule 12: the full thread and the deeper
# drill each print), the screw it takes under the rows.
REAR_TAP_CALLOUT_XY = (REAR_X + 0.0295, 0.110)
REAR_TAP_CALLOUT_HALF_WIDTH = 0.0235
REAR_TAP_CALLOUT_HALF_HEIGHT = 0.0073
REAR_TAP_CALLOUT_PRECISION = {
    "hw-tapdrldia": REAR_TAP_DRILL_DIA_PLACES,
    "hw-threaddepth": REAR_TAP_DEPTH_PLACES,
    "hw-tapdrldepth": REAR_TAP_DEPTH_PLACES,
}
REAR_TAP_CALLOUT_BELOW = (
    f"FOR {_config.parts('pd-vn-transgear-knob-cup-screw')['number']}"
)
# SolidWorks pins its own "#2-56 Tapped Hole" note beside a tap's native
# callout; the callout already states the thread.
TAPPED_HOLE_NOTE = "Tapped Hole"
# The edge-break note stands by the front end view, its leader on the
# feature it names (machinist review r8).  That view is mirrored (sheet
# angle = 180 deg - model angle).  The note lands on tooth 5's tip (teeth
# centre on 2*pi*k/TEETH, model 120 deg, sheet 60 deg: ~(341.8, 171.7) mm)
# and stands over it on one line, under the isometric (from 202.5).  The
# title block's .010 edge break is a fifth of this fine tooth's whole depth,
# so the teeth take this one exception.  Anchors are top-left.
TOOTH_EDGE_NOTE = "NO EDGE BREAK ON TEETH"
TOOTH_EDGE_TOOTH = 5
TOOTH_EDGE_NOTE_XY = (0.345, 0.200)

# --- Detail B: the front neck at 10:1 -----------------------------------------
# At 3:1 the 0.400 neck is 1.2 mm of sheet: its Ø, width, corner R and
# runout frame crossed one another and the core's annotations (mr-stack6).
# Detail B is a cropped 10:1 *Right MODEL view, draw_dt_pinion_spring's
# detail-A recipe: native detail views imported no dimensions on the
# amplitude bar (r743-6), dt_vn_post_mount_screw and the pinion spring
# (pc-r13/14).
DETAIL_SCALE = (10, 1)
_DS = DETAIL_SCALE[0] / DETAIL_SCALE[1]
DETAIL_LETTER = "B"  # A is the journal datum.
DETAIL_LABEL_TEXT = f"DETAIL {DETAIL_LETTER}\nSCALE {DETAIL_SCALE[0]} : {DETAIL_SCALE[1]}"
# The fence, model mm (z, y): mid-neck, 0.1 under the axis.  Radius 2.7
# holds both neck floors (the Ø's two arrows land on drawn floor), the
# core's top step corner (2.53 out), the Ø's lower arrow tail (2.6 under
# the axis; 2.52 out), the axis and F origin that FrontReliefDia,
# FrontReliefWidth and FlatEnd reference, and the D-flat tool's end arc
# and its lower tangent point (2.13 out) that FlatEnd and FlatToolRadius
# reference: a crop drops a dimension whose reference it cuts away.
DETAIL_FOCUS_MM = (-FRONT_RELIEF_WIDTH / 2.0, -0.1)
_DETAIL_FOCUS_M = (0.0, DETAIL_FOCUS_MM[1] / 1000.0, DETAIL_FOCUS_MM[0] / 1000.0)
DETAIL_RADIUS_MM = 2.7
DETAIL_CROP_RADIUS = DETAIL_RADIUS_MM * _DS / 1000.0
# Upper left, over the journal: x 0.078-0.132 clears the end view (x <=
# 0.064) and the journal Ø's witness line (x 0.1348);
# y 0.1945-0.2485 stands over the journal Ø's text (top 0.193) and leaves the
# frame row under the border (0.2667).  1.5 mm lower than run
# 20261101T111116817Z, where the neck Ø's upper limit touched the border.
DETAIL_CENTER = (0.105, 0.2215)
CROP_NO_ERROR = 1  # swCropViewErrors_e.swCropViewErrors_NoError
# The focus, and the neck landing that proves the view's scale and handing,
# must land within 0.1 mm of where this script places them.
DETAIL_POSITION_TOL_M = 1e-4


def _detail_xy(z_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet point of model (z, y) mm in detail B (model +Z runs left)."""
    return (
        DETAIL_CENTER[0] + (DETAIL_FOCUS_MM[0] - z_mm) * _DS / 1000.0,
        DETAIL_CENTER[1] + (y_mm - DETAIL_FOCUS_MM[1]) * _DS / 1000.0,
    )


_NECK_FLOOR_R = FRONT_RELIEF_DIA / 2.0
_STEP_X = _detail_xy(-FRONT_RELIEF_WIDTH, 0.0)[0]
_CORNER_CENTER = _detail_xy(-FRONT_CORNER_RADIUS, _NECK_FLOOR_R + FRONT_CORNER_RADIUS)
_F_DETAIL_X = _detail_xy(0.0, 0.0)[0]
_DETAIL_TOP = DETAIL_CENTER[1] + DETAIL_CROP_RADIUS
_DETAIL_BOTTOM = DETAIL_CENTER[1] - DETAIL_CROP_RADIUS
# The neck frame's leader lands on the straight floor 0.27 from F and climbs
# plumb through the neck's air to a frame RIGHT of it (the neck Ø's block
# took the lane left of it: LIMITS and its reason).  A frame
# prints 31.3 mm wide and 7 mm tall with a 6.3 mm shoulder at mid-height
# (stack PDF: box x 0.1884-0.2197, shoulder to 0.2260), so its left edge
# stands one shoulder right of the landing.  Its row is the top one, 1.5 mm
# under the border, over the core frame's.
_FRAME_WIDTH = 0.0313
_FRAME_HEIGHT = 0.007
_FRAME_SHOULDER = 0.0063
NECK_LANDING_Z_MM = -0.27
NECK_RUNOUT_LANDING = _detail_xy(NECK_LANDING_Z_MM, _NECK_FLOOR_R)
NECK_RUNOUT_FRAME = (NECK_RUNOUT_LANDING[0] + _FRAME_SHOULDER, _DETAIL_TOP + 0.0152)
# The core frame also stands in detail B: in the side view every route to
# the core crossed a Ø line (main and run 20261031T233549214Z: its leader
# from over the thread blank crossed the relief's line at x 238.6; from the
# left it would cross the core's or the pinion's).  It lands on the core's
# round top 0.8 behind F, inside the crop (2.60 from the focus), right of
# the neck Ø's line, and stands right of the crop a row under the neck
# frame's (1.2 mm between the boxes), its box left of the relief's mate
# callout (x >= 166.5 mm since #2425's shorter journal re-centred the side
# view) and its shoulder on the box's left, so the leader descends 5.25 mm
# over 15.3 mm into the crop, under the neck frame's box.
CORE_LANDING_Z_MM = -0.8
CORE_RUNOUT_LANDING = _detail_xy(CORE_LANDING_Z_MM, CORE_DIA / 2.0)
CORE_RUNOUT_FRAME = (
    CORE_RUNOUT_LANDING[0] + _FRAME_SHOULDER + 0.0153,
    _DETAIL_TOP + 0.007,
)
DETAIL_KEEP: dict[str, tuple[float, float]] = {
    # Its line rises through the neck's air 0.14 from F, 1.3 mm left of the
    # neck frame's plumb leader, to its shoulder 1.5 mm over the crop's top;
    # the text hangs LEFT of the line over the shoulder.  LIMITS stack two
    # 4.5 mm rows, so the block runs from ~2.3 mm under its keep to ~5.7 mm
    # over it (run 20261101T035809796Z).  A row under the value would top
    # out past the border, so the one reason rides the value's line as a
    # suffix, starting well inside the border.
    "FrontReliefDia": (_detail_xy(-0.14, 0.0)[0], _DETAIL_TOP + 0.0093),
    # Under the crop, LEFT of F's witness line (round 7: with its note link
    # the ~39 mm text no longer fits the 23 mm between the step's witness
    # line and the journal Ø's column on the right), its line running out
    # past F over the flat end's block, as the flat end's own text stands
    # outside its witness lines.  DETAIL_TEXT_* below check it against the
    # round-6 render's measures.
    "FrontReliefWidth": (_F_DETAIL_X - 0.0225, _DETAIL_BOTTOM - 0.0060),
    # Left of the crop: the leader runs from the corner 12-24 deg below
    # level, inside the corner's own quadrant, through the pinion's blank
    # interior under its root and over the axis.  Its 23.5 mm text, centred
    # on the keep, ends 2.5 mm short of the crop circle (at 32.5 mm in, run
    # 20261031T233549214Z, the circle crossed its last letter).
    "FrontCornerRadius": (_CORNER_CENTER[0] - 0.0365, _CORNER_CENTER[1] - 0.006),
    # The D-flat tool's end from F, under the crop: its single MAX on the
    # value's line and the neck note's link on the row under it, left of F's
    # witness line, on its own dimension line 9 mm under the neck width's
    # (round 1: at 2.3 mm the two read as one line).  The line (~174) stays
    # over the end view's teeth (top 0.1735) and the journal's outline
    # (0.169); the ~26 mm block, centred on the keep, ends 12 mm left of F
    # and right of the end view's tooth tips (x ~0.0585).
    "FlatEnd": (_F_DETAIL_X - 0.025, _DETAIL_BOTTOM - 0.0160),
    # Left of the crop, just over the tool's end arc (centre ~0.105, 0.2003):
    # the leader enters the arc's own quadrant from the left, under the
    # detail label.
    "FlatToolRadius": (_F_DETAIL_X - 0.031, _DETAIL_BOTTOM + 0.0085),
}
# Round-6 render, detail B: a one-line value's text ran keep - 1.9 mm to
# keep + 1.5 mm over its line at keep - 2.8 mm (.016 at keep y 185.8: text
# 183.9-187.3, line 183.0); the flat end's stacked limits ran to keep +
# 4.3 mm (182.8 at keep 178.5); ".007 SEE NOTE 4" ran 34.7 mm, so 2.6 mm a
# character covers it.
DETAIL_CHAR_WIDTH = 0.0026
_WIDTH_X, _WIDTH_Y = DETAIL_KEEP["FrontReliefWidth"]
_WIDTH_HALF = (
    len(inch_text(FRONT_RELIEF_WIDTH, 3) + DIMENSION_SUFFIXES["FrontReliefWidth"])
    * DETAIL_CHAR_WIDTH / 2.0
)
DETAIL_TEXT_WIDTH_BOX = (
    _WIDTH_X - _WIDTH_HALF, _WIDTH_Y - 0.0028, _WIDTH_X + _WIDTH_HALF, _WIDTH_Y + 0.0015
)
DETAIL_TEXT_FLAT_END_TOP = DETAIL_KEEP["FlatEnd"][1] + 0.0043
_left, _line, _right, _top = DETAIL_TEXT_WIDTH_BOX
if _right > _F_DETAIL_X - 0.003:
    raise AssertionError("the neck width's text runs into F's witness line")
if _line < DETAIL_TEXT_FLAT_END_TOP + 0.002:
    raise AssertionError("the neck width's line runs into the flat end's limits")
if math.dist((_right, _top), DETAIL_CENTER) < DETAIL_CROP_RADIUS + 0.003:
    raise AssertionError("the neck width's text runs into detail B's crop")
if _left < END_CENTER[0] + HALF_OD + 0.002:
    raise AssertionError("the neck width's text runs over the end view")
# Top-left anchors.  The label stands left of the crop, 3 mm under the
# corner R's text (its limits print to 5 mm under its point).
DETAIL_LABEL_XY = (0.042, _CORNER_CENTER[1] - 0.014)
# The mark's "B" stands under the pinion, right of the face width's rear
# witness line (x 199.7 mm) and 7 mm left of the tooth-tip Ø's lower arrow,
# which now stands just behind F (run 20261031T233549214Z: at F - 5.7 mm
# the "B" stood 1.4 mm from that arrow), clear of the mark circle.
PARENT_LETTER_XY = (PINION_REAR_X + 0.007, SIDE_CENTER[1] - HALF_OD - 0.0025)

# Each frame's leader landing on its surface's upper outline, and the frame.
# The neck's straight floor is 0.2 mm long between its two R0.10 corner tori,
# so a silhouette hit-test there landed on a neighbour (run 10: a type-46
# silhouette of another face). Like main's arbor finishes, each frame
# attaches to the model FACE its spec control names, resolved on the
# referenced part, at this landing, in the view CONTROL_VIEWS names.
CONTROL_ATTACHMENTS = {
    "core_total_runout": (CORE_RUNOUT_LANDING, CORE_RUNOUT_FRAME),
    "front_neck_total_runout": (NECK_RUNOUT_LANDING, NECK_RUNOUT_FRAME),
}
CONTROL_VIEWS = {"core_total_runout": "detail", "front_neck_total_runout": "detail"}
# Lower right: the gauge gap is TOOTH_SPACE_GAP_INDEX pitches round from
# the first, so its landing sits low right of the front view, away from the
# flat's witness lines, and the note's leader climbs to it from below
# without crossing them.
TOOTH_SPACE_GAP_INDEX = 9
TOOTHSPACE_NOTE_XY = (0.330, 0.115)

# --- VIEW C: the gear end, enlarged 4:1 ---------------------------------------
# The span over two teeth and the root envelope print as the part's native
# dimensions (codjiflo P2 on cb74f3d8d: as gear-data text alone no feature
# dimension carried them).  At 3:1 the span's dimension crossed the bores and
# the flat (machinist review r8), so both print on an enlarged *Back view,
# the front view's direction, in the empty lower-left field (x 13-215 mm, y
# 13-75 mm: under the (70.74) row, left of the title block).  At 5:1 (run
# 20261101T210436532Z) the span's limits stood 1.5 mm under the (70.74) text
# and the root's 63 mm text, centred on its point, ran into the teeth; at 4:1
# the tooth tips reach 17.96 mm round the axis, x 142-178 and y 18-54 mm.
# Off its parent's projection line the view is a removed view: a letter and
# a viewing arrow on the side view name it (drawing-guidelines.md rule 9).
ENLARGED_SCALE = (4, 1)
_ES = ENLARGED_SCALE[0] / ENLARGED_SCALE[1]
ENLARGED_CENTER = (0.160, 0.036)
ENLARGED_HALF_OD = OUTSIDE_DIA * _ES / 2000.0
ENLARGED_LETTER = "C"  # A is the journal datum, B the neck detail.
ENLARGED_LABEL_TEXT = (
    f"VIEW {ENLARGED_LETTER}\nSCALE {ENLARGED_SCALE[0]} : {ENLARGED_SCALE[1]}"
)
# Top-left anchor: left of the view, over the root's text, under the
# numbered notes (bottom ~0.056) and the (70.74) row.
ENLARGED_LABEL_XY = (0.060, 0.052)
# VIEW C's viewing arrow on the side view: a letter note whose straight
# leader points -X, square onto the stud's tip face 0.8 mm over the axis
# (clear of the turning axis's centreline),
# its tip just right of the face, the letter right of it in the open field
# short of the front end view's teeth (from ~321 mm), level with the tip
# (draw_fr_top_frame's VIEW G arrow, turned end for end).
VIEW_ARROW_FACE_RADIUS_MM = 0.8
VIEW_ARROW_TIP_GAP = 0.0035
VIEW_ARROW_LENGTH = 0.013
VIEW_LETTER_HEIGHT = 0.005


def _enlarged_sheet_angle(model_deg: float) -> float:
    """Sheet angle (rad) of a model direction in a *Back view (mirrored x)."""
    return math.pi - math.radians(model_deg)


# The span's anvils straddle SPAN_TEETH teeth about their gaps' bisector
# (paper_drive_stock_native.author_span), model 36 deg, sheet 144 deg.  Its
# dimension line stands 26 mm out along that bisector, 8 mm past the tips,
# and its text 18.5 mm along the line up and right, over the teeth: the
# block (then limits and a mate row) ran ~6.7 mm under to ~7.3 mm over its point
# (run 20261101T210436532Z).  At 19.8 mm (run 20261101T214844567Z) it
# topped out 3.22 mm under the (70.74) text (from 77.8 mm), close enough to
# read as one callout (the audit wants 3.57); here it stands ~4.3 mm under
# it and ~2.4 mm over the end of the bisector's construction line (35.9 mm
# out), which struck the mate row at 5:1.
SPAN_BISECTOR_SHEET_RAD = _enlarged_sheet_angle(
    GAP_AZIMUTH_DEG + 180.0 * SPAN_TEETH / TEETH
)
_SPAN_LINE_OUT = 0.026
_SPAN_TEXT_ALONG = 0.0185
# The root envelope's one-line text (63 mm) is centred on its point; its
# leader runs from the shoulder under the text's right end (35 mm right of
# and 3 mm under the point, run 20261101T214844567Z) toward the axis, so it
# arrives along a gap bisector (sheet 216 deg, model 324) and its arrow lands
# on a gap floor.  The point stands out along sheet 192 deg (model 348, also
# a gap), far enough that the text ends 10 mm left of the teeth, under the
# label.
ROOT_LEADER_SHEET_RAD = _enlarged_sheet_angle(GAP_AZIMUTH_DEG + 14 * 360.0 / TEETH)
_ROOT_TEXT_OUT = 0.0565
# The root leader's shoulder end, from the root text's point (that run).
ROOT_SHOULDER_FROM_TEXT = (0.0350, -0.00305)
ENLARGED_KEEP: dict[str, tuple[float, float]] = {
    "ToothSpan": (
        ENLARGED_CENTER[0]
        + _SPAN_LINE_OUT * math.cos(SPAN_BISECTOR_SHEET_RAD)
        + _SPAN_TEXT_ALONG * math.sin(SPAN_BISECTOR_SHEET_RAD),
        ENLARGED_CENTER[1]
        + _SPAN_LINE_OUT * math.sin(SPAN_BISECTOR_SHEET_RAD)
        - _SPAN_TEXT_ALONG * math.cos(SPAN_BISECTOR_SHEET_RAD),
    ),
    "RootDia": (
        ENLARGED_CENTER[0] + _ROOT_TEXT_OUT * math.cos(ROOT_LEADER_SHEET_RAD),
        ENLARGED_CENTER[1] + _ROOT_TEXT_OUT * math.sin(ROOT_LEADER_SHEET_RAD),
    ),
}


def _activate_view(adapter: Any, view: Any, *, label: str) -> str:
    """Make ``view`` the active view (sketch entities and notes land in it)."""
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate the {label} {name!r}")
    adapter.currentModel.ClearSelection2(True)
    return name


def _sketch_circle(
    adapter: Any,
    view: Any,
    center: tuple[float, float],
    radius: float,
    *,
    label: str,
    add_to_db: bool = False,
) -> Any:
    """Sketch a circle in the ACTIVE ``view``'s own sketch from sheet points.

    The sheet points go through the view sketch's ModelToSketchTransform.
    Without ``add_to_db`` the circle is left SELECTED, which Crop2 consumes.
    """
    sketch = _early_bound(_early_bound(view, "IView").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(adapter.currentModel.SketchManager, "ISketchManager")
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = add_to_db
    try:
        circle = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous_add_to_db
    if circle is None:
        raise RuntimeError(f"failed to sketch the {label} circle")
    return circle


def _moved_model_view(
    adapter: Any,
    orientation: str,
    center: tuple[float, float],
    scale: tuple[int, int],
    focus_m: tuple[float, float, float],
    proof: tuple[tuple[float, float, float], tuple[float, float], str],
    *,
    label: str,
) -> Any:
    """A model view at ``scale`` moved so ``focus_m`` lands on ``center``.

    ``proof`` (a model point, the sheet point it must land on, its label) is
    projected too, so a view at another scale or handing than the script's
    sheet mapping assumes raises."""
    draw = adapter.currentModel
    view = _early_bound(
        place_view(adapter, str(SOURCE), orientation, *center, scale=scale), "IView"
    )
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if ratio != tuple(float(value) for value in scale):
        raise RuntimeError(f"{label} scale {ratio!r}, expected {scale!r}")
    found = model_point_in_view(adapter, view, focus_m, label=f"{label} focus")
    position = tuple(float(value) for value in view.Position)
    target = [position[axis] + center[axis] - found[axis] for axis in range(2)]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError(f"failed to move the {label} onto its sheet position")
    draw.EditRebuild3()
    for point, expected, point_label in ((focus_m, center, f"{label} focus"), proof):
        found = model_point_in_view(adapter, view, point, label=point_label)
        if math.dist(found, expected) > DETAIL_POSITION_TOL_M:
            raise RuntimeError(f"{point_label} sits at {found!r}, not {expected!r}")
    return view


def _placed_detail_view(adapter: Any) -> Any:
    """Detail B, uncropped: a 10:1 *Right model view whose fence focus lands
    on DETAIL_CENTER, proved by the neck landing (_detail_xy's mapping)."""
    landing_m = (0.0, _NECK_FLOOR_R / 1000.0, NECK_LANDING_Z_MM / 1000.0)
    return _moved_model_view(
        adapter, "*Right", DETAIL_CENTER, DETAIL_SCALE, _DETAIL_FOCUS_M,
        (landing_m, NECK_RUNOUT_LANDING, "neck runout landing"),
        label="neck detail",
    )


def _placed_enlarged_view(adapter: Any) -> Any:
    """The 4:1 *Back view whose axis at F lands on ENLARGED_CENTER, proved by
    the tip of tooth 0 (model +X): the mirrored view prints it left of the
    axis, ENLARGED_HALF_OD out, the mapping ENLARGED_KEEP assumes."""
    tip_m = (OUTSIDE_DIA / 2000.0, 0.0, 0.0)
    tip_xy = (ENLARGED_CENTER[0] - ENLARGED_HALF_OD, ENLARGED_CENTER[1])
    return _moved_model_view(
        adapter, "*Back", ENLARGED_CENTER, ENLARGED_SCALE, (0.0, 0.0, 0.0),
        (tip_m, tip_xy, "enlarged tooth tip"),
        label="enlarged gear end",
    )


def _crop_detail_view(adapter: Any, view: Any) -> None:
    """Crop detail B to its fence circle round DETAIL_CENTER.

    Sketch the circle in the active view's own sketch and Crop2 while it is
    still selected, with the circle as the outline.  Crop status,
    IsCropped, the outline and its style are read back and raise.
    """
    draw = adapter.currentModel
    view = _early_bound(view, "IView")
    uncropped = tuple(float(value) for value in view.GetOutline())
    name = _activate_view(adapter, view, label="neck detail")
    _sketch_circle(
        adapter, view, DETAIL_CENTER, DETAIL_CROP_RADIUS, label="neck-detail crop"
    )
    status = int(view.Crop2(False, False, 1))
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    view.UpdateViewDisplayGeometry()
    cropped = bool(view.IsCropped())
    outline = tuple(float(value) for value in view.GetOutline())
    _telemetry.info(
        f"knob-shaft: neck detail {name!r}, Crop2 status {status}, IsCropped "
        f"{cropped}, outline {tuple(round(value * 1000, 1) for value in outline)} mm",
        crop_status=status,
        cropped=cropped,
    )
    if status != CROP_NO_ERROR or not cropped:
        raise RuntimeError(
            f"neck detail is not cropped: Crop2 status {status}, IsCropped {cropped}"
        )
    # Uncropped, the 10:1 view spans the whole 70.7 mm shaft (~707 mm of
    # sheet), the crop 48 mm, so a crop that took at least halves the width.
    if (
        len(outline) != 4
        or len(uncropped) != 4
        or outline[2] - outline[0] > (uncropped[2] - uncropped[0]) / 2.0
    ):
        raise RuntimeError(
            f"neck-detail crop did not take: outline {outline!r}, before {uncropped!r}"
        )
    boundary = (bool(view.CropViewJaggedOutline), bool(view.CropViewNoOutline))
    if boundary != (False, False):
        raise RuntimeError(
            f"neck detail's crop boundary is not its plain circle: jagged, "
            f"no-outline {boundary!r}"
        )


def _view_dimension_names(adapter: Any, view: Any) -> list[str]:
    """The model-dimension names ``view`` holds, sorted."""
    return sorted(
        name
        for name in (
            dimension_name(adapter, _early_bound(annotation, "IAnnotation"))
            for annotation in (_early_bound(view, "IView").GetAnnotations() or ())
        )
        if name
    )


def _dimension_then_crop_detail(adapter: Any, detail: Any) -> list[Any]:
    """Import and curate detail B's dimensions uncropped, then crop it.

    The names are read back before and after the crop as one
    ``neck_detail.crop`` event; any kept dimension missing afterwards raises.
    """
    annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="neck detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    before = _view_dimension_names(adapter, detail)
    _crop_detail_view(adapter, detail)
    after = _view_dimension_names(adapter, detail)
    lost = sorted(set(DETAIL_KEEP) - set(after))
    _telemetry.event(
        "neck_detail.crop",
        dimensions_before=",".join(before),
        dimensions_after=",".join(after),
        lost=",".join(lost),
    )
    if lost:
        raise RuntimeError(
            f"neck detail lost {lost} to its crop; before {before}, after {after}"
        )
    return annotations


def _mark_detail_on_side(adapter: Any, side: Any) -> None:
    """Circle detail B's fence on the side view in the outline's black."""
    _activate_view(adapter, side, label="side view")
    center = model_point_in_view(adapter, side, _DETAIL_FOCUS_M, label="neck detail mark")
    circle = _sketch_circle(
        adapter,
        side,
        center,
        DETAIL_RADIUS_MM * _S / 1000.0,
        label="neck-detail mark",
        add_to_db=True,
    )
    segment = _early_bound(circle, "ISketchSegment")
    segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
    if int(segment.Color) != 0:
        raise RuntimeError("neck-detail mark circle colour did not persist")
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()


def _plain_text(text: str) -> str:
    """A note's words with its line breaks and spacing folded to single spaces."""
    return " ".join(str(text).split())


def _label_views(adapter: Any, detail: Any, side: Any, enlarged: Any) -> None:
    """Label detail B beside its crop, letter its mark on the side view and
    label VIEW C: both differ from the sheet's 3:1.

    A note lands in the ACTIVE view, so each view is activated first; a
    note that did not land in its view raises.
    """
    sheet = _early_bound(
        _early_bound(adapter.currentModel, "IDrawingDoc").GetCurrentSheet(), "ISheet"
    )
    if not sheet.SetScale(*SHEET_SCALE, False, False):
        raise RuntimeError("failed to pin sheet scale before labelling the views")
    for view, text, xy, label in (
        (detail, DETAIL_LABEL_TEXT, DETAIL_LABEL_XY, "neck-detail label"),
        (side, DETAIL_LETTER, PARENT_LETTER_XY, "neck-detail letter"),
        (enlarged, ENLARGED_LABEL_TEXT, ENLARGED_LABEL_XY, "enlarged-view label"),
    ):
        _activate_view(adapter, view, label=label)
        if add_note(adapter, text, *xy) is None:
            raise RuntimeError(f"failed to add the {label} note")
        texts = [
            _plain_text(_early_bound(found, "INote").GetText() or "")
            for found in (_early_bound(view, "IView").GetNotes() or ())
        ]
        if texts.count(_plain_text(text)) != 1:
            raise RuntimeError(f"{label} note did not land in its view: {texts!r}")


def _set_dimension_suffixes(adapter: Any, annotations: list[Any]) -> None:
    """Write each DIMENSION_SUFFIXES dimension's native suffix (after its
    value, on its one line) and read it back; the value stays the model's."""
    remaining = dict(DIMENSION_SUFFIXES)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        text = remaining.pop(dimension_name(adapter, annotation), None)
        if text is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.SetText(2, text)  # swDimensionTextSuffix
        got = str(display.GetText(2) or "")
        if got != text:
            raise RuntimeError(f"dimension suffix {text!r} did not persist: {got!r}")
    if remaining:
        raise RuntimeError(f"dimension suffixes not applied: {sorted(remaining)}")


def _add_tooth_edge_note(adapter: Any, front: Any) -> None:
    """Leader the edge-break note to a tooth tip in the front end view
    (TOOTH_EDGE_NOTE_XY)."""
    tip_r = OUTSIDE_DIA / 2000.0
    tooth = TOOTH_EDGE_TOOTH * 2.0 * math.pi / TEETH
    tooth_tip = model_point_in_view(
        adapter,
        front,
        (tip_r * math.cos(tooth), tip_r * math.sin(tooth), 0.0),
        label="tooth-edge note landing",
    )
    add_attached_note(
        adapter,
        front,
        text=TOOTH_EDGE_NOTE,
        entity_xy=tooth_tip,
        note_xy=TOOTH_EDGE_NOTE_XY,
        label="MHA-PD-08 tooth edge note",
    )


def _add_view_arrow(adapter: Any, side: Any) -> None:
    """VIEW C's lettered viewing arrow on the side view, square onto the stud
    tip face (draw_fr_top_frame._add_view_arrow, pointing -X)."""
    face = model_point_in_view(
        adapter,
        side,
        (0.0, VIEW_ARROW_FACE_RADIUS_MM / 1000.0, TIP_Z / 1000.0),
        label="view C arrow tip face",
    )
    tip_xy = (face[0] + VIEW_ARROW_TIP_GAP, face[1])
    text_xy = (tip_xy[0] + VIEW_ARROW_LENGTH, tip_xy[1] + VIEW_LETTER_HEIGHT / 2.0)
    label = f"view {ENLARGED_LETTER} viewing arrow"
    note = add_leader_note(
        adapter, ENLARGED_LETTER, text_xy=text_xy, attach_xy=tip_xy, view=side, label=label,
    )
    square_view_arrow(
        adapter, note, text_xy=text_xy, tip_xy=tip_xy, axis=1, label=label,
        letter_height=VIEW_LETTER_HEIGHT,
    )


def _add_sheet_note(
    adapter: Any, text: str, xy: tuple[float, float], *, char_height: float, label: str
) -> None:
    """A sheet note at ``xy`` (top-left) at ``char_height``; its last line is
    read back, so a note that lost its own text raises."""
    note = add_note(adapter, text, *xy)
    if note is None:
        raise RuntimeError(f"failed to add the {label}")
    annotation = _early_bound(_early_bound(note, "INote").GetAnnotation(), "IAnnotation")
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError(f"{label} has no text format")
    text_format.CharHeight = float(char_height)
    if annotation.SetTextFormat(0, False, text_format) is not True:
        raise RuntimeError(f"failed to set the {label} text height")
    got = str(_early_bound(note, "INote").GetText() or "").splitlines()
    if not got or got[-1].strip() != text.splitlines()[-1].strip():
        raise RuntimeError(f"{label} reads back {got!r}")


def _require_saved_rear_tap(model: Any) -> None:
    """Require the saved native rear tap's size, class, blind ends, drill Ø
    and both depths before the callout reads them."""
    feature = _early_bound(model, "IPartDoc").FeatureByName("RearTap")
    if feature is None:
        raise RuntimeError("saved knob shaft has no native RearTap")
    feature = _early_bound(feature, "IFeature")
    if str(feature.GetTypeName2()) != "HoleWzd":
        raise RuntimeError("saved knob shaft RearTap is not a native Hole Wizard tap")
    definition = feature.GetDefinition()
    if definition is None:
        raise RuntimeError("saved knob shaft RearTap has no hole definition")
    definition = _early_bound(definition, "IWizardHoleFeatureData2")
    if str(definition.FastenerSize).strip() != REAR_TAP_SPEC.size:
        raise RuntimeError("saved knob shaft RearTap has the wrong thread size")
    _verify_tap_metadata(definition, REAR_TAP_SPEC, "saved knob shaft RearTap")
    for member, expected, what in (
        ("TapDrillDiameter", REAR_TAP_DRILL_DIA, "tap drill"),
        ("TapDrillDepth", REAR_TAP_DRILL_DEPTH, "tap drill depth"),
        ("ThreadDepth", REAR_TAP_FULL_THREAD_MIN, "thread depth"),
    ):
        value = float(getattr(definition, member)) * 1000.0
        if not math.isfinite(value) or abs(value - expected) > DIAMETER_TOLERANCE_MM:
            raise RuntimeError(
                f"saved knob shaft rear tap {what} {value:.3f} != {expected:.3f} mm"
            )


def _print_full_thread_as_min(callout: Any) -> None:
    """The full thread's depth prints as a MIN (rule 12; the spec's
    REAR_TAP_FULL_THREAD_MIN): callout variables own their presentation,
    apart from the source dimension (draw_sm_summing_lever's bracket tap)."""
    from win32com.client.dynamic import Dispatch as dynamic_dispatch

    for raw in callout.GetHoleCalloutVariables() or ():
        # Concrete callout interfaces alias the generic metadata DISPIDs.
        variable = dynamic_dispatch(raw._oleobj_)
        if str(variable.VariableName) != "hw-threaddepth":
            continue
        variable.ToleranceType = 5  # swTolType_e.swTolMIN
        if int(variable.ToleranceType) != 5:
            raise RuntimeError("knob shaft rear tap full thread did not persist as MIN")
        return
    raise RuntimeError("knob shaft rear tap callout has no hw-threaddepth variable")


def _add_rear_tap_callout(adapter: Any, end: Any) -> None:
    """The rear #2-56 tap, natively called out on the rear view: the title
    block's THREADS row owns the 2B class (rule 2), the full thread prints as
    a MIN and the deeper drill at .XX, and the screw it takes prints under
    the native rows."""
    callout = add_native_hole_callout(
        adapter,
        end,
        edge=visible_circle_edge(adapter, end, REAR_TAP_DRILL_DIA),
        callout_xy=REAR_TAP_CALLOUT_XY,
        label=f"knob shaft rear {REAR_TAP_SPEC.size} blind tap",
    )
    omit_title_block_thread_class(callout, label="knob shaft rear tap")
    set_hole_callout_precision(
        callout, REAR_TAP_CALLOUT_PRECISION, label="knob shaft rear tap depths"
    )
    _print_full_thread_as_min(callout)
    set_hole_callout_below(
        callout, REAR_TAP_CALLOUT_BELOW, label="knob shaft rear tap"
    )
    rebuild_drawing(adapter, label="knob shaft rear tap callout")


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open transgear-knob-shaft source", adapter.open_model(str(SOURCE)))
    _require_saved_rear_tap(adapter.currentModel)
    source_properties = read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            TOOTH_SPACE_CALLOUT_PROPERTY,
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            TOOTH_SPACE_CALLOUT_PROPERTY,
        ),
    )
    require_source_control(
        source_properties[TOOTH_SPACE_CALLOUT_PROPERTY], TOOTH_SPACE_CALLOUT,
        label="knob shaft toothspace grade",
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Transgear Knob Shaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: (
                f"transgear knob shaft; steel; {TEETH}T {DIAMETRAL_PITCH:g}DP "
                f"PA{PRESSURE_ANGLE_DEG:g}; finite stock #{CUTTER_NUMBER}; #8-32 stud; D-core"
            ),
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=VIEW_SCALE)
    end = place_view(adapter, str(SOURCE), "*Front", *END_CENTER, scale=VIEW_SCALE)
    front = place_view(adapter, str(SOURCE), "*Back", *FRONT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (side, end, front, iso):
        set_hidden_lines_removed(adapter, view)

    # Detail B is placed and dimensioned FIRST: its five dimensions live in
    # StudProfile with the side view's, and in CoreFlatProfile, and a
    # dimension already on the sheet is never imported again
    # (draw_dt_pinion_spring's detail A), so the side view's targeted import
    # skips the five the detail holds.  The detail is dimensioned uncropped
    # and cropped after.
    detail = _placed_detail_view(adapter)
    set_hidden_lines_removed(adapter, detail)
    detail_annotations = _dimension_then_crop_detail(adapter, detail)
    # The 4:1 view from the tip shows the hidden span and root sketches, in
    # it alone (curate_view_dimensions shows each per view), and takes their
    # two dimensions; no other view's keep names them.
    enlarged = _placed_enlarged_view(adapter)
    set_hidden_lines_removed(adapter, enlarged)
    enlarged_annotations = curate_view_dimensions(
        adapter,
        enlarged,
        keep=ENLARGED_KEEP,
        view_label="enlarged gear end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    end_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=END_KEEP,
        view_label="front finite-form inspection",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [
        *side_annotations, *end_annotations, *detail_annotations, *enlarged_annotations,
    ]
    set_dimension_callouts(
        adapter, annotations, DIMENSION_CALLOUTS_ABOVE, location="above"
    )
    set_dimension_callouts(
        adapter, annotations, DIMENSION_CALLOUTS_BELOW, location="below"
    )
    _set_dimension_suffixes(adapter, annotations)
    for annotation in annotations:
        name = dimension_name(adapter, _early_bound(annotation, "IAnnotation"))
        if name in REFERENCE_DIMENSIONS:
            set_reference_dimension(
                adapter, annotation, label=f"knob shaft {name} reference",
                diameter=REFERENCE_DIMENSIONS[name],
            )
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)

    add_view_centerline(
        adapter, side, face_xy=CENTERLINE_PICK, label="MHA-PD-08 turning axis"
    )
    add_attached_note(
        adapter,
        side,
        text=THREAD_CALLOUT,
        entity_xy=THREAD_PICK,
        note_xy=THREAD_NOTE_XY,
        label="MHA-PD-08 stud thread callout",
    )
    add_attached_note(
        adapter,
        side,
        text=TIP_CHAMFER_NOTE,
        entity_xy=CHAMFER_PICK,
        note_xy=CHAMFER_NOTE_XY,
        label="MHA-PD-08 tip chamfer callout",
    )

    # The one running surface, authored on the part and read back (drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates)).
    part_model = _early_bound(
        _early_bound(side, "IView").ReferencedDocument, "IModelDoc2"
    )
    journal_finish = surface_finish_by_key(SURFACE_FINISHES, "journal")
    add_surface_finish(
        adapter,
        side,
        entity=resolve_faces(part_model, {journal_finish.key: journal_finish.face})[
            journal_finish.key
        ],
        symbol_xy=JOURNAL_FINISH_SYMBOL,
        control=journal_finish,
        label="journal finish",
        entity_type="FACE",
        leader_attach_xy=JOURNAL_FINISH_PICK,
        char_height=0.0025,
    )
    # The saved source owns datum/control semantics. The drawing attaches
    # those same source declarations to the actual journal/core entities.
    journal_datum = PART_DATUMS[0]
    add_datum_feature(
        adapter,
        side,
        edge_xy=DATUM_A_PICK,
        entity_type="SILHOUETTE",
        symbol_xy=DATUM_A_SYMBOL,
        datum=journal_datum.letter,
        label="knob running journal datum",
    )
    _add_rear_tap_callout(adapter, end)
    controls = {control.key: control for control in GEOMETRIC_CONTROLS}
    if set(controls) != set(GEOMETRIC_TOLERANCES_MM):
        raise RuntimeError("knob shaft frames do not cover the spec's geometric controls")
    control_faces = resolve_faces(
        part_model,
        {key: control.face for key, control in controls.items()},
    )
    views = {"side": side, "detail": detail}
    for (key,) in (("core_total_runout",), ("front_neck_total_runout",)):
        control = controls[key]
        landing, frame_xy = CONTROL_ATTACHMENTS[key]
        add_feature_control_frame(
            adapter,
            views[CONTROL_VIEWS[key]],
            entity=control_faces[key],
            leader_attach_xy=landing,
            frame_xy=frame_xy,
            characteristic=control.characteristic,
            tolerance=GEOMETRIC_TOLERANCES_IN[key],  # the printed inch text
            datums=control.datums,
            diameter=control.tolerance_zone == "diametral",
            entity_type="FACE",
            label=control.key,
        )
    add_toothspace_callout(
        adapter, front, profile=STOCK_PROFILE,
        actual_pin_diameter_mm=TOOTH_SPACE_GAUGE_PIN_DIA_MM,
        rotate_rad=math.pi / TEETH + TOOTH_SPACE_GAP_INDEX * 2.0 * math.pi / TEETH,
        axial_station_mm=0.0,
        property_name=TOOTH_SPACE_CALLOUT_PROPERTY,
        note_xy=TOOTHSPACE_NOTE_XY,
    )
    _add_tooth_edge_note(adapter, front)
    _add_view_arrow(adapter, side)
    # The mark and the labels go on once every pick is done, so no
    # coordinate pick in the side view meets the mark circle.
    _mark_detail_on_side(adapter, side)
    _label_views(adapter, detail, side, enlarged)
    # The GEAR DATA block, its matched-fit backlash acceptance as the last row.
    _add_sheet_note(
        adapter,
        GEAR_DATA_NOTE,
        GEAR_DATA_XY,
        char_height=GEAR_DATA_CHAR_HEIGHT,
        label="gear data block",
    )
    _add_sheet_note(
        adapter, NOTES, NOTES_XY, char_height=NOTES_CHAR_HEIGHT, label="numbered notes"
    )
    removed_tap_labels = remove_notes_matching(adapter, TAPPED_HOLE_NOTE)
    _telemetry.info(f"removed {removed_tap_labels} automatic tapped-hole label(s)")
    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Knob Shaft Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        redundant_note_substrings=(TAPPED_HOLE_NOTE,),
        expected_redundant_notes=0,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
