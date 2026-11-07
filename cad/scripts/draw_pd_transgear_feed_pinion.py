r"""Create the curated manufacturing drawing for the feed-pinion sleeve (MHA-PD-10).

An end view, a longitudinal section B-B, VIEW D on the rear face, VIEW C
outside in the section's direction and an isometric at 3:1 (the section
takes B: A names the bore datum). The end view looks at the rear face
(*Back), the third-angle left view of the section, whose rear face stands
left (the 2026-10-27 ENFORCE review: a nose view there broke the
projection). It carries the genuine native two-tooth span, finish, datum A
and VIEW C's viewing arrow; VIEW D, named by an arrow on VIEW C, carries the
toothspace inspection callout on a full-depth flank and the root's MIN
across two gap floors; VIEW C carries the cutter's full-depth station and
run-out limit from the floor of the gap facing it; the section
carries diameters beside their axial extent, the D-flat from the axis, the
lengths baselined from the rear face (drawing-guidelines.md rule 11 (turned
parts read like the lathe)) and the step face (the disc hub's seat) square to
the bore, all imported natively from the part with the places, bands and
callout text the part authored (``pd_transgear_feed_pinion_spec``,
``pd_transgear_feed_pinion_callouts``).  The GEAR DATA block is the
drawing's own note: its span row cites the MHA-PD-00 step that sets the
mesh.  The oil hole is drilled through the seated hub into the bore at
assembly, so the section carries only its drill note; its station belongs
to the hub's sheet.  Decimal-inch sheet (#290); the model
keeps its millimetre nominals.  Views C and D print at the sheet's 3:1, so
no caption restates a scale (rule 9).
"""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Sequence
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_annotation_extent import move_annotation
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision
from _drawing_finish import add_surface_finish
from _drawing_gdt import add_feature_control_frame
from _drawing_layout_collect import check_drawing_layout
from _drawing_leader_notes import add_leader_note
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _gear_drawing_entities import visible_circle_edge
from _native_axis_datum import add_native_axis_datum
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _part_properties import part_drawing_unit
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
import pd_paper_drive_assembly_steps as assembly_steps
import pd_transgear_feed_pinion_callouts as callouts
from paper_drive_stock_drawing import add_toothspace_callout, require_source_control
from pd_rack_pinion_spec import inch_text
from pd_transgear_disc_hub_spec import OIL_HOLE_DIA, OIL_HOLE_SLEEVE_Z
from pd_transgear_feed_pinion_spec import (
    BORE_DATUM,
    BORE_DIA,
    BOSS_DIA,
    CUTTER_NUMBER,
    CUTTER_RUNOUT_MAX,
    CUTTER_TOOTH_RANGE,
    DIAMETRAL_PITCH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FACE_WIDTH,
    GEOMETRIC_TOLERANCES_IN,
    HUB_NUMBER,
    OUTSIDE_DIA,
    OVERALL_LENGTH,
    PITCH_DIA,
    PRESSURE_ANGLE_DEG,
    RACK_NUMBER,
    RADIAL_SETTING,
    SURFACE_FINISHES,
    TEETH,
    STOCK_PROFILE,
    TOOTHSPACE_GAUGE_DIA_MM,
    TOOTH_SPACE_INSPECTION_END_MM,
    TOOTH_SPACE_INSPECTION_PHASE_RAD,
    TOOTH_SPACE_CALLOUT_PROPERTY,
    TOOTH_EDGE_NOTE,
    WHOLE_DEPTH,
)

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_transgear_feed_pinion"]
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

SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
# The end view looks at the rear face (*Back): the section looks along
# model +X with
# the rear face left, so its third-angle left view sees the rear face.
END_VIEW_ORIENTATION = "*Back"
FRONT_CENTER = (0.080, 0.160)
RIGHT_CENTER = (0.230, 0.160)
# The isometric (94 x 88 mm at 3:1) stands upper right, clear of the title
# block and right of the oil-hole note.
ISO_CENTER = (0.367, 0.214)
# The toothspace pin seats on the straight pass's full-depth flank at the
# REAR face (TOOTH_SPACE_INSPECTION_END_MM).  The nose view once used as the
# end view looked at the step face, where the cutter's run-out leaves only
# partial-depth gaps (run 11's pick there found a flank 0.23 mm off the
# contact).  The end view now sees the rear face, but its lanes hold the
# span, finish, datum and VIEW C's arrow, so the callout and the root's MIN
# land on a second rear-face view in the free lane below the section, left
# of the title block (left edge 216 mm, top 66 mm) and under the section
# caption (bottom ~78 mm).  It is not projected, so it is VIEW D, named by a
# viewing arrow on VIEW C (rule 9; the 2026-11-07 screen read the prose
# "VIEW FROM GEAR END" as unlabelled); its caption hangs centred below the
# view's measured outline (run 12: at a fixed point it overlapped the
# outline by 2.4 mm; the outline runs 6 mm past the tip circle).
# 2 mm lower than run 12 left room for the tooth length's stack row above.
REAR_CENTER = (0.165, 0.044)
OUTSIDE_VIEW_LETTER = "C"
REAR_VIEW_LETTER = "D"
REAR_CAPTION = f"VIEW {REAR_VIEW_LETTER}"
REAR_CAPTION_XY = (REAR_CENTER[0] - 0.020, REAR_CENTER[1] - 0.0215)
REAR_CAPTION_GAP_M = 0.002
# INote.GetExtent reads ~0.3 mm apart between sessions; settle within twice.
CAPTION_SETTLE_M = 0.0006
# Every gap is the patterned seed. Gap 3 (model 105 deg) mirrors to the rear
# view's upper side, where the contact flank faces up-left into its own gap,
# toward the callout lane, so the leader arrives through air.
TOOTH_SPACE_GAP_INDEX = 3
SHEET_INNER_BORDER = (0.0127, 0.0127, 0.4191, 0.2667)

# Half the printed tooth-tip circle in sheet metres: the section's half-height,
# which every dimension is placed clear of.
HALF_OD = OUTSIDE_DIA * VIEW_SCALE[0] / 2000.0
# The cutting line through the end view's axis, drawn top to bottom so its
# arrows point left: in the rear-face view that is model +X, the section's
# direction of sight, so the section keeps its rear face left (drawn bottom
# to top, the arrows point right and the section would lay the nose left).
# It overshoots the tips 8 mm, so the lower "B" clears datum A's tag below
# the bore (run 20261027T054041865Z layout audit: 5 mm left 1.35 mm).
_SECTION_LINE_OVERSHOOT = 0.008
SECTION_LINE = (
    (FRONT_CENTER[0], FRONT_CENTER[1] + HALF_OD + _SECTION_LINE_OVERSHOOT),
    (FRONT_CENTER[0], FRONT_CENTER[1] - HALF_OD - _SECTION_LINE_OVERSHOOT),
)


def _side_x(z_mm: float) -> float:
    """Sheet x of a model-z station in the longitudinal section.

    The section lays model +Z to the RIGHT (the crank pinion's read-back): the
    rear face (z = 0) is the left edge and the nose the right edge.
    """
    return RIGHT_CENTER[0] + (z_mm - OVERALL_LENGTH / 2.0) * VIEW_SCALE[0] / 1000.0


# The end view is pictorial and carries its center mark, the bore finish
# and the two-tooth span (its rack mate under its limits).
# On the section, the tip and boss diameters print inline on the axis,
# between their own extension lines and off the part (the crank hub's and
# the disc hub's layout): the tip left of the rear face, where its witness
# starts; the boss right of the nose, beyond the flat.  Each prints its mate
# under its value.  The flat's distance from the axis hangs below the
# section right of the nose, its mate under it: the four rows are taller
# than the flat's depth.  The bore keeps its shelf above-left of the rear
# face, which holds its two-row band, process and fit callout clear of its
# own extension lines (the fit there, not on a separate end-view note: run
# 20261101T054343686Z's note overlapped the oil hole note's leader extent).
# The lengths stay baseline-stacked below from the rear
# face, shortest innermost, so no extension line crosses an inner row; the
# tooth length's and the flat end's texts, wider than their spans with their
# mates, stand left of the rear face, clear of every station's extension
# line, and the overall's stands centred in its span.  The section plane
# passes through teeth, where neither the root nor the cutter's stations
# have an edge (2026-10-24 ENFORCE review): the root prints on the rear-face
# view, where the full-depth gaps show their floors, and the cutter's
# full-depth station and run-out limit (R9-67) on an outside view in the
# section's direction, from the floor of the gap that faces it.  The span's
# text stands 2.5 mm higher than with one callout row, so its matched-fit
# row clears the toothspace control below (round 2).
FRONT_KEEP: dict[str, tuple[float, float]] = {"ToothSpan": (FRONT_CENTER[0], 0.1145)}
_SIDE_TOP = RIGHT_CENTER[1] + HALF_OD
_SIDE_BOTTOM = RIGHT_CENTER[1] - HALF_OD
_REAR_X = _side_x(0.0)
_NOSE_X = _side_x(OVERALL_LENGTH)
# Text left of the rear face ends this far short of its extension line.
_LEFT_OF_REAR_AIR = 0.004


def _left_of(edge_x: float, width: float) -> float:
    """Centre x of a text ``width`` wide that ends ``_LEFT_OF_REAR_AIR`` short
    of ``edge_x``."""
    return edge_x - _LEFT_OF_REAR_AIR - width / 2.0


# Widths of the texts that stand left of a rear face, as the drawing test
# estimates them (3.5 mm caps, 2.61 mm advance, a space padding either side;
# test_pd_transgear_feed_pinion_drawing): the rows are placed by their text
# centres, each a 3 mm gap under the row above.
_FACE_WIDTH_TEXT_WIDTH = 0.0627
_FLAT_END_TEXT_WIDTH = 0.0601
RIGHT_KEEP: dict[str, tuple[float, float]] = {
    # 4 mm farther out than run 20261027T064211655Z, whose "RACK" touched
    # the bore dimension's lower extension line (r1, r3).
    "OutsideDia": (_REAR_X - 0.044, RIGHT_CENTER[1]),
    # Its fit's two rows (the standard fit name and the mate's name and
    # number, the route and the clearance REF) are the sheet's widest:
    # centred this far out, the text starts right of the flat's dimension
    # line and ends inside the border.
    "BossDia": (_NOSE_X + 0.074, RIGHT_CENTER[1]),
    # Its dimension line stands just right of the nose; the text prints right
    # of the line, below the flat (run 20261027T032128736Z: 30 mm out, the
    # outside view's outline struck its last row).
    "FlatToAxis": (_NOSE_X + 0.006, _SIDE_BOTTOM - 0.0079),
    "BoreDia": (_REAR_X - 0.010, _SIDE_TOP + 0.040),
    # The tooth length's band and its second callout row (the disc cluster
    # stack) make it a three-row text, centred on its point: every row stands
    # 3 mm lower than with the bare tooth length.
    "FaceWidth": (_left_of(_REAR_X, _FACE_WIDTH_TEXT_WIDTH), _SIDE_BOTTOM - 0.0099),
    "FlatEnd": (_left_of(_REAR_X, _FLAT_END_TEXT_WIDTH), _SIDE_BOTTOM - 0.0278),
    "OverallLength": (RIGHT_CENTER[0], _SIDE_BOTTOM - 0.0452),
}

# VIEW C: the *Left view looks along +X, the section's direction of sight,
# so it lays the rear face left like the section and imports the section
# plane's (Right plane's) dimensions.  It stands lower right, above the
# title block and below the boss's callout; its two cutter rows hang below
# it with their texts left of its rear face.  Its tangent edges are hidden.
# It is not projected from any view, so it takes a letter and a viewing
# arrow on the end view (rule 9; the 2026-11-07 screen read the prose
# "OUTSIDE VIEW SAME SIDE AS B-B" as unlabelled and private).  It is cropped
# (below) and a break line closes the boss stub at the crop (2026-10-28
# ENFORCE review, r1, r2: without one, the 13.80 MAX's extension line
# landed past the drawn end and the view read as the whole part).
# It stands 4 mm higher than the uncropped view did, so the full depth's
# extra row stays above the title block, and 15 mm farther right than round
# 2, so the full depth's text, naming the rack, clears the overall's.
LEFT_CENTER = (0.388, 0.116)
LEFT_CAPTION = f"VIEW {OUTSIDE_VIEW_LETTER}"
# The caption's estimated width (the drawing test's 3.5 mm text box).
_LEFT_CAPTION_WIDTH = 0.016
TANGENT_EDGES_HIDDEN = 0  # swDisplayTangentEdges_e.swTangentEdgesHidden
_LEFT_REAR_X = LEFT_CENTER[0] - OVERALL_LENGTH / 2.0 * VIEW_SCALE[0] / 1000.0
_LEFT_BOTTOM = LEFT_CENTER[1] - HALF_OD
# The view is cropped just past the cutter's run-out limit: it exists for
# the teeth, and the section shows the boss.  Uncropped, runs
# 20261027T032128736Z..054041865Z drew one tooth-space line of the facing
# gap on to the boss to ~15.3 mm, where the part has no edge (its STL holds
# no vertex on the boss between 13.6 and 16.6 mm), and the review read it
# as a run-out past the 13.80 MAX (r1, r2).  The crop stands 0.2 mm past
# the MAX (0.6 mm on the sheet), so the break line drawn on it stays
# distinct from the MAX's extension line, which lands on the boss stub
# between the step and the break.
OUTSIDE_CROP_Z = CUTTER_RUNOUT_MAX + 0.2
OUTSIDE_CROP_FENCE = (
    _LEFT_REAR_X - 0.004,
    _LEFT_BOTTOM - 0.004,
    _LEFT_REAR_X + OUTSIDE_CROP_Z * VIEW_SCALE[0] / 1000.0,
    LEFT_CENTER[1] + HALF_OD + 0.004,
)
# The long-break line on the crop (draw_fr_nameplate's SECTION_BREAK): thin,
# across the Ø8.2 boss and past both its outlines, with its Z on the side of
# the axis away from the facing gap's floor, so the 13.80 MAX's extension
# line, which drops from that floor to its row below the view, never meets
# it.  Model (radial y, axial z) in mm; the view prints model +Y up.
_BREAK_OVERRUN = 0.35
_BREAK_Z_MID_Y = 2.0
_BREAK_Z_HALF_HEIGHT = 0.3
_BREAK_Z_TIP = 0.15
OUTSIDE_BREAK = (
    (-(BOSS_DIA / 2.0 + _BREAK_OVERRUN), OUTSIDE_CROP_Z),
    (_BREAK_Z_MID_Y - _BREAK_Z_HALF_HEIGHT, OUTSIDE_CROP_Z),
    (_BREAK_Z_MID_Y - _BREAK_Z_HALF_HEIGHT / 2.0, OUTSIDE_CROP_Z - _BREAK_Z_TIP),
    (_BREAK_Z_MID_Y + _BREAK_Z_HALF_HEIGHT / 2.0, OUTSIDE_CROP_Z + _BREAK_Z_TIP),
    (_BREAK_Z_MID_Y + _BREAK_Z_HALF_HEIGHT, OUTSIDE_CROP_Z),
    (BOSS_DIA / 2.0 + _BREAK_OVERRUN, OUTSIDE_CROP_Z),
)


def _outside_sheet_xy(radial_y: float, axial_z: float) -> tuple[float, float]:
    """A model (y, z) point of the outside view on the sheet."""
    s = VIEW_SCALE[0] / 1000.0
    return (_LEFT_REAR_X + axial_z * s, LEFT_CENTER[1] + radial_y * s)


_FULL_DEPTH_TEXT_WIDTH = 0.0757
_CUTTER_TEXT_WIDTH = 0.0418
LEFT_KEEP: dict[str, tuple[float, float]] = {
    "FullDepth": (_left_of(_LEFT_REAR_X, _FULL_DEPTH_TEXT_WIDTH), _LEFT_BOTTOM - 0.0100),
    "CutterRunout": (_left_of(_LEFT_REAR_X, _CUTTER_TEXT_WIDTH), _LEFT_BOTTOM - 0.0250),
}
# The caption stands beside the cropped view, right of its own box (the crop
# fence and the native margin round it) and level with the axis, the lane
# right of the view being empty down to the title block.  Over the view it
# read as one of B-B's callouts (round 2, run 20261107T121559938Z); at +7.5 mm
# over it the native box, top 142.3 mm against the fence's 137.25, took the
# caption's lower 4.8 mm (layout audit, round 1 run 20261107T103915122Z).
_VIEW_BOX_MARGIN = 0.0051
_CAPTION_VIEW_AIR = 0.003
LEFT_CAPTION_HEIGHT = 0.0035
LEFT_CAPTION_XY = (
    OUTSIDE_CROP_FENCE[2] + _VIEW_BOX_MARGIN + _CAPTION_VIEW_AIR,
    LEFT_CENTER[1] + LEFT_CAPTION_HEIGHT / 2.0,
)

# Viewing arrows (rule 9): a letter note whose straight leader is the arrow
# (draw_fr_top_frame._add_view_arrow), the letter at the cutting-plane
# letters' height, the tip a small gap off the face it looks at, level
# with the letter's mid-height.
VIEW_LETTER_HEIGHT = 0.005
# The letter's estimated width (the drawing test's text box at that height).
VIEW_LETTER_WIDTH = 0.0037
VIEW_ARROW_TIP_GAP = 0.0035
VIEW_ARROW_LEADER = 0.009
VIEW_ARROW_SQUARE_TOL = 0.0003
# C's arrow points left at the end view's tooth tip level with the bore:
# model +X in the mirrored *Back view, the sight of B-B's arrows, so VIEW C
# (*Left) sees that side uncut.  The letter stands right of the tip, short
# of the tip diameter's text left of the section's rear face.
_VIEW_C_TIP = (FRONT_CENTER[0] + HALF_OD + VIEW_ARROW_TIP_GAP, FRONT_CENTER[1])
VIEW_C_ARROW = (
    (_VIEW_C_TIP[0] + VIEW_ARROW_LEADER, _VIEW_C_TIP[1] + VIEW_LETTER_HEIGHT / 2.0),
    _VIEW_C_TIP,
)
# D's arrow points right (model +Z) at VIEW C's rear face, 6 mm under the
# axis: VIEW D (*Back) looks at the rear face from behind.  The letter
# stands left of the face, under the flat's callout and over the cutter
# rows.
_VIEW_D_TIP = (_LEFT_REAR_X - VIEW_ARROW_TIP_GAP, LEFT_CENTER[1] - 0.006)
VIEW_D_ARROW = (
    (
        _VIEW_D_TIP[0] - VIEW_ARROW_LEADER - VIEW_LETTER_WIDTH,
        _VIEW_D_TIP[1] + VIEW_LETTER_HEIGHT / 2.0,
    ),
    _VIEW_D_TIP,
)

# The rear-face view's root diameter reads along a gap bisector (the *Back
# view mirrors model x; model gaps at 15° + k·30° print at 165° - k·30°), so
# its arrows land on two gap floors; the text stands lower left, clear of the
# view, under the notes and over its caption.
_ROOT_TEXT_ANGLE = math.radians(195.0)
_ROOT_TEXT_RADIUS = 0.057
REAR_KEEP: dict[str, tuple[float, float]] = {
    "RootDia": (
        REAR_CENTER[0] + _ROOT_TEXT_RADIUS * math.cos(_ROOT_TEXT_ANGLE),
        REAR_CENTER[1] + _ROOT_TEXT_RADIUS * math.sin(_ROOT_TEXT_ANGLE),
    )
}

# The oil hole lies in the section plane (+Y), so the cut shows it as a gap in
# the upper boss wall; the note's leader lands mid-wall on its front edge.
# The note stands above the section, its last (longer) row ending just left
# of the hole: SolidWorks leaves the leader from the last row's end nearer
# the tip, so it runs down clear of the text.  Run 20261027T064211655Z,
# note right of the hole: the leader left the rows' left end and struck both
# (r1, r2).  Run 20261027T072743812Z, the short row last: it left that row's
# right end, crossed the step's frame leader and the note's left end met the
# end view (layout audit).  It is match drilled with the hub seated, so the
# note names the hub once; the hub's sheet sets its position (2026-11-07
# screen: a second statement of the hub was narration).  Size first, then
# the process (rule 26).
OIL_HOLE_NOTE = "\n".join(
    (
        f"\u00d8{inch_text(OIL_HOLE_DIA, 3)} INTO BORE",
        f"MATCH-DRILL AT ASSY WITH {HUB_NUMBER}",
    )
)
OIL_HOLE_EDGE = (
    _side_x(OIL_HOLE_SLEEVE_Z + OIL_HOLE_DIA / 2.0),
    RIGHT_CENTER[1] + (BORE_DIA + BOSS_DIA) / 4.0 * VIEW_SCALE[0] / 1000.0,
)
# Its last row: run 20261027T064211655Z drew 61 characters 151 mm wide.
_OIL_HOLE_NOTE_WIDTH = 0.151 * len(OIL_HOLE_NOTE.splitlines()[-1]) / 61
OIL_HOLE_CALLOUT = (OIL_HOLE_EDGE[0] - 0.008 - _OIL_HOLE_NOTE_WIDTH, _SIDE_TOP + 0.079)
NOTE_HEIGHT = 0.0025

_BORE_SHEET_RADIUS = BORE_DIA * VIEW_SCALE[0] / 2000.0
# The finite-form data block uses the upper-left lane.  It is the drawing's
# own note (draw_pd_transgear_knob_shaft's pattern), not a part property: its
# span row cites the MHA-PD-00 step that sets the mesh, and a part property
# would re-key the part on every renumbering of that sequence.  What a
# machinist needs to cut and check the teeth (Main ruling 2026-10-10); the
# span prints on the end view with its limits, not again here.  The span's
# .0008 band is matched to the rack at assembly: MHA-PD-00 sets the platen
# shake at the datum on a dial, which sets the feed mesh depth, and the row
# prints that window as MHA-PD-00 does (RACK_DATUM_BACKLASH_TEXT, the mesh
# check's band rounded inward).
GEAR_DATA_XY = (0.016, 0.262)
GEAR_DATA_CHAR_HEIGHT = 0.0025
MESH_SET_STEP = assembly_steps.step_ref("hanger-meshed")
GEAR_DATA_ROWS = (
    ("NUMBER OF TEETH", f"{TEETH}"),
    ("DIAMETRAL PITCH", f"{DIAMETRAL_PITCH:.2f}"),
    ("PRESSURE ANGLE", f"{PRESSURE_ANGLE_DEG:.1f} DEG"),
    ("PITCH DIAMETER (REF)", inch_text(PITCH_DIA, 4)),
    ("WHOLE DEPTH (REF)", inch_text(WHOLE_DEPTH, 4)),
    ("CUTTER", f"#{CUTTER_NUMBER}, {CUTTER_TOOTH_RANGE[0]}-{CUTTER_TOOTH_RANGE[1]}T"),
    ("MATES WITH", f"PLATEN RACK {RACK_NUMBER}"),
    # Three short lines keep the block left of the bore's callout.
    (
        "SPAN MATCHED FIT",
        "BACKLASH WITH MATE\n"
        f"   SET AT ASSY {assembly_steps.RACK_DATUM_BACKLASH_TEXT} (DIAL),\n"
        f"   PER {MESH_SET_STEP}",
    ),
)
GEAR_DATA_NOTE = "\n".join(
    ("GEAR DATA", *(f"{label}:  {value}" for label, value in GEAR_DATA_ROWS))
)
# Separate radial-runout and relative-index controls share one source-linked
# callout on the real finite tooth flank, not the OD. Its three rows use the
# standard 3.5 mm font; at x 50 mm its lower-right corner stands up-left of
# the rear-view contact, inside the flank's open quarter (run 12: at 16 mm
# the shorter callout's leader arrived from behind the flank).
TOOTH_SPACE_CALLOUT_XY = (0.050, 0.102)
# The tooth-edge exception stands below the callout's leader (run 12: at
# y 70 mm the notes overlapped the leader's extent down to the 60 mm
# landing), flagged at the teeth: its leader runs from its longer last row's
# right end to the tip land of the gear-end view's upper-left tooth (sheet
# 150°; model 30°, a tooth, as *Back mirrors x), clear above the root's
# 165° arrow (2026-10-27 ENFORCE review, r2, r3: a loose "do not cut" note
# reached no feature, rule 7).  The remaining notes hang below it.
TOOTH_EDGE_LEADER_NOTE = TOOTH_EDGE_NOTE.replace(" ON TOOTH", "\nON TOOTH")
TOOTH_EDGE_NOTE_XY = (0.016, 0.056)
TOOTH_EDGE_ATTACH = (
    REAR_CENTER[0]
    + (OUTSIDE_DIA / 2.0 - 0.05) * VIEW_SCALE[0] / 1000.0 * math.cos(math.radians(150.0)),
    REAR_CENTER[1]
    + (OUTSIDE_DIA / 2.0 - 0.05) * VIEW_SCALE[0] / 1000.0 * math.sin(math.radians(150.0)),
)
NOTES_XY = (0.016, TOOTH_EDGE_NOTE_XY[1] - 0.0100)
TOOTH_SPACE_CALLOUT_CHAR_HEIGHT = 0.0035
# The section's native caption, placed by its top centre, sits below the
# stacked lengths, the overall's two-row callout the lowest.
SECTION_CAPTION = (RIGHT_CENTER[0], _SIDE_BOTTOM - 0.0548)
# The finish stands lower LEFT of the end view: when the section line's
# arrows and their "B" labels pointed right, toward the section, a
# lower-right leader ran through the lower label (run 20261001T035353825Z
# layout audit).  They now point left, the lower label below the finish's
# leader, which lands level with the bore centre.  It
# stands farther out and nearer level with the bore, so its leader climbs
# shallowly and passes right of the symbol's own "Ra" text rather than through
# it (run 20261001T110844152Z layout audit).  The symbol grows up and right
# from its insertion point in proportion to its text, so its text keeps the
# note height: at the document's 6.35 mm default (run 20261002T153039266Z)
# "Ra 1.6" printed 13.5-37.4 mm right of and 10.8-17.2 mm above the point,
# over the teeth.  At 2.5 mm the symbol's ink stands well below the bore
# centre and its text ends
# 7 mm left of the tip circle.  The leader lands on the bore's 170° point:
# the nose view once ran the two-tooth span's extension lines along the
# lower-left diagonal (machinist review, stack6: a -135° finish leader
# crossed them); the rear-face view mirrors them lower right.  On the .125
# bore (#290) the 180° point stood too near that diagonal, so the landing
# climbs 10°, still shallow enough to pass right of the symbol's own text.
# The symbol stands 10 mm below the centre.
FINISH_ATTACH = (
    FRONT_CENTER[0] + _BORE_SHEET_RADIUS * math.cos(math.radians(170.0)),
    FRONT_CENTER[1] + _BORE_SHEET_RADIUS * math.sin(math.radians(170.0)),
)
FINISH_SYMBOL = (FRONT_CENTER[0] - HALF_OD - 0.022, FRONT_CENTER[1] - 0.010)
FINISH_CHAR_HEIGHT = 0.0025

# The step face (the disc hub's seat) shows edge-on in the section where the
# cut passes through the tooth on +Y: the pick lands mid-face between the
# boss and the tip.  The frame stands above the section, left of the step
# and of the oil-hole note's leader, clear of the bore's shelf.
STEP_FACE_EDGE = (
    _side_x(FACE_WIDTH),
    RIGHT_CENTER[1] + (BOSS_DIA + OUTSIDE_DIA) / 4.0 * VIEW_SCALE[0] / 1000.0,
)
STEP_FRAME = (_side_x(FACE_WIDTH) - 0.020, _SIDE_TOP + 0.012)


@_telemetry.traced("drawing.planar_centerline", label_param="label")
def _create_section_axis_centerline(
    adapter: Any, view: Any, *, label: str, nose_mm: float = OVERALL_LENGTH
) -> Any:
    """Create the turning axis in a side view's sketch, 1 mm past the rear face
    and past ``nose_mm`` (a cropped view's last station)."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    name = view_name(adapter, view)
    if not drawing.ActivateView(name):
        raise RuntimeError(f"failed to activate section view {name!r} ({label})")
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(sketch_manager.AddToDB)
    previous_display = bool(sketch_manager.DisplayWhenAdded)
    sketch_manager.AddToDB = True
    sketch_manager.DisplayWhenAdded = True
    half_length = OVERALL_LENGTH / 2000.0
    nose = (nose_mm - OVERALL_LENGTH / 2.0) / 1000.0
    try:
        centerline = sketch_manager.CreateCenterLine(
            -half_length - 0.001, 0.0, 0.0, nose + 0.001, 0.0, 0.0
        )
    finally:
        sketch_manager.AddToDB = previous_add_to_db
        sketch_manager.DisplayWhenAdded = previous_display
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    if centerline is None:
        raise RuntimeError(f"failed to create section-axis centerline ({label})")
    return centerline


def _pin_sheet_scale(adapter: Any) -> None:
    """Hold the sheet at its printed 3:1, read back.

    Placing a model view drifts the sheet scale, and a native section caption
    carries a scale field when its view's scale differs from the sheet's at
    creation (draw_fr_top_frame._pin_sheet_scale): the 2026-11-07 screen read
    SECTION B-B's "SCALE 3 : 1" as restating the title block (rule 9).  The
    rear view's caption is placed against the pinned scale too, so
    finalization re-applying it cannot move the view after that readback.
    """
    sheet = _early_bound(
        _early_bound(adapter.currentModel, "IDrawingDoc").GetCurrentSheet(), "ISheet"
    )
    if not sheet.SetScale(*SHEET_SCALE, False, False):
        raise RuntimeError("cannot pin the pinion-sleeve sheet at 3:1")
    properties = list(sheet.GetProperties2() or ())
    if len(properties) < 4 or (float(properties[2]), float(properties[3])) != SHEET_SCALE:
        raise RuntimeError(f"pinion-sleeve sheet scale did not persist: {properties!r}")


def _position_section_caption(
    adapter: Any, view: Any, target: tuple[float, float]
) -> None:
    """Move the native linked section caption clear of the length dimensions.

    It is found by its label field (``_section_axis.position_section_caption``)
    and must carry no scale field: B-B prints at the sheet's scale."""
    bound_view = _early_bound(view, "IView")
    candidates = []
    for raw_note in bound_view.GetNotes() or ():
        note = _early_bound(raw_note, "INote")
        linked_text = str(note.PropertyLinkedText or "")
        if "<VLLABEL>" in linked_text:
            candidates.append((note, linked_text))
    if len(candidates) != 1:
        raise RuntimeError(
            f"expected one native linked section caption, found {len(candidates)}"
        )
    note, linked_text = candidates[0]
    if "<VLSCALEV>" in linked_text:
        raise RuntimeError(
            f"section B-B caption {linked_text!r} restates the sheet's scale"
        )
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    if not annotation.SetPosition2(*target, 0.0):
        raise RuntimeError("failed to position the pinion-sleeve section caption")
    rebuild_drawing(adapter, label="position pinion-sleeve section caption")
    position = tuple(float(value) for value in annotation.GetPosition())
    if math.dist(position[:2], target) > 1e-6:
        raise RuntimeError("pinion-sleeve section caption position did not persist")
    if str(note.PropertyLinkedText or "") != linked_text:
        raise RuntimeError("pinion-sleeve section caption lost its native fields")


def _add_view_arrow(
    adapter: Any,
    parent: Any,
    letter: str,
    arrow: tuple[tuple[float, float], tuple[float, float]],
) -> None:
    """A horizontal letter arrow on ``parent`` naming a removed view, square
    onto the face it looks at (draw_fr_top_frame._add_view_arrow): the
    letter slides in y by any miss."""
    text_xy, tip_xy = arrow
    label = f"view {letter} viewing arrow"
    note = add_leader_note(
        adapter, letter, text_xy=text_xy, attach_xy=tip_xy, view=parent, label=label,
    )
    # add_note leaves text at the document height; size the letter here and
    # prove the leader tip did not move with it.
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError(f"{label} note has no text format")
    text_format.CharHeight = VIEW_LETTER_HEIGHT
    if not annotation.SetTextFormat(0, False, text_format):
        raise RuntimeError(f"failed to size the {label} letter")
    rebuild_drawing(adapter, label=f"{label} letter")
    points = list(annotation.GetLeaderPointsAtIndex(0) or ())
    if len(points) < 6 or math.dist((points[-3], points[-2]), tip_xy) > 0.001:
        raise RuntimeError(f"{label} tip moved when its letter was sized")
    # The leader leaves the letter's nearer side at the text's mid-height.
    miss = tip_xy[1] - points[1]
    if abs(miss) > VIEW_ARROW_SQUARE_TOL:
        x, y, z = (float(value) for value in annotation.GetPosition())
        if not annotation.SetPosition2(x, y + miss, z):
            raise RuntimeError(f"failed to square the {label}")
        rebuild_drawing(adapter, label=f"square {label}")
        points = list(annotation.GetLeaderPointsAtIndex(0) or ())
        if (
            len(points) < 6
            or math.dist((points[-3], points[-2]), tip_xy) > 0.001
            or abs(tip_xy[1] - points[1]) > VIEW_ARROW_SQUARE_TOL
        ):
            raise RuntimeError(f"{label} did not square: leader {points}")
    _assert_note_inside_border(note, label)
    _telemetry.info(
        f"{label}: leader {points[0]:.5f},{points[1]:.5f} -> "
        f"{points[-3]:.5f},{points[-2]:.5f} (square when the y agree)"
    )


def _assert_note_inside_border(note: Any, label: str) -> None:
    extent = tuple(float(v) for v in (_early_bound(note, "INote").GetExtent() or ()))
    _telemetry.info(f"{label} extent {extent}")
    x0, y0, x1, y1 = SHEET_INNER_BORDER
    if len(extent) < 5 or not (
        x0 <= extent[0] and y0 <= extent[1] and extent[3] <= x1 and extent[4] <= y1
    ):
        raise RuntimeError(
            f"{label} extent {extent} left the inner border {SHEET_INNER_BORDER}"
        )


_OWNER_VIEW = 0  # swAnnotationOwner_e.swAnnotationOwner_DrawingView


def _insert_view_caption(
    adapter: Any, view: Any, text: str, xy: tuple[float, float], label: str
) -> Any:
    """Insert a caption owned by ``view``, read back.

    A note joins the active view, so the view is activated first: after the
    outside view's crop the gear-end caption joined the outside view
    (codjiflo P2 on edb402b).  The owner is read back
    (``IAnnotation.OwnerType``/``Owner``)."""
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate {name!r} for the {label} caption")
    raw_note = add_note(adapter, text, *xy)
    if raw_note is None:
        raise RuntimeError(f"the {label} caption was not inserted")
    note = _early_bound(raw_note, "INote")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    owner_type = int(annotation.OwnerType)
    owner = view_name(adapter, annotation.Owner) if owner_type == _OWNER_VIEW else None
    if owner != name:
        raise RuntimeError(
            f"the {label} caption is owned by {owner!r} (OwnerType {owner_type}), not {name!r}"
        )
    return note


def _place_rear_caption(adapter: Any, view: Any) -> None:
    """Hang the rear view's caption, centred, below the view's measured outline.

    Both boxes are measured (``IView.GetOutline``, ``INote.GetExtent``), as
    main's draw_dt_cone_gear_shaft places its view captions, against the
    pinned sheet scale."""
    _pin_sheet_scale(adapter)
    outline = tuple(float(value) for value in _early_bound(view, "IView").GetOutline())
    target = ((outline[0] + outline[2]) / 2.0, outline[1] - REAR_CAPTION_GAP_M)
    note = _insert_view_caption(adapter, view, REAR_CAPTION, REAR_CAPTION_XY, "rear view")
    for _attempt in range(4):
        extent = tuple(float(value) for value in note.GetExtent())
        error = (target[0] - (extent[0] + extent[3]) / 2.0, target[1] - extent[4])
        if max(abs(error[0]), abs(error[1])) < CAPTION_SETTLE_M:
            break
        move_annotation(adapter, note.GetAnnotation(), *error, label="rear view caption")
    else:
        raise RuntimeError(
            f"rear view caption stayed at {extent}, its top centre requested at {target}"
        )
    if extent[1] < SHEET_INNER_BORDER[1]:
        raise RuntimeError(f"rear view caption {extent} left the inner border")
    _telemetry.info(f"rear view caption: outline {outline}, extent {extent}")


def _hide_tangent_edges(view: Any) -> None:
    """Hide the outside view's tangent edges, read back.

    Run 20261027T032128736Z printed them in their phantom font along every
    tooth space, and all three reviewers read them as hidden-line clutter.
    """
    bound = _early_bound(view, "IView")
    bound.SetDisplayTangentEdges2(TANGENT_EDGES_HIDDEN)
    if int(bound.GetDisplayTangentEdges2()) != TANGENT_EDGES_HIDDEN:
        raise RuntimeError("failed to hide the outside view's tangent edges")
    bound.UpdateViewDisplayGeometry()


def _sheet_points_in_view_sketch(
    adapter: Any, native: Any, points: Sequence[tuple[float, float]]
) -> list[tuple[float, float, float]]:
    """Sheet points (m) in ``native``'s own sketch space, through the sketch's
    ModelToSketchTransform (the drawing's model space is the sheet)."""
    sketch = _early_bound(native.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    projected_points = []
    for x, y in points:
        point = _early_bound(
            math_utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        projected_points.append(tuple(float(value) for value in projected.ArrayData))
    return projected_points


def _sketch_line_ends_on_sheet(
    adapter: Any, native: Any, segments: Sequence[Any]
) -> list[tuple[float, float]]:
    """Every end of ``segments`` (view-sketch lines) read back on the sheet,
    through the view's frame as it stands now."""
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    settled = _early_bound(native.GetSketch(), "ISketch")
    to_sheet = _early_bound(
        _early_bound(settled.ModelToSketchTransform, "IMathTransform").Inverse(),
        "IMathTransform",
    )
    ends = []
    for segment in segments:
        line = _early_bound(segment, "ISketchLine")
        for raw in (line.GetStartPoint2(), line.GetEndPoint2()):
            point = _early_bound(raw, "ISketchPoint")
            sheet_point = _early_bound(
                _early_bound(
                    math_utility.CreatePoint(double_array([point.X, point.Y, point.Z])),
                    "IMathPoint",
                ).MultiplyTransform(to_sheet),
                "IMathPoint",
            )
            ends.append(tuple(float(value) for value in sheet_point.ArrayData)[:2])
    return ends


@_telemetry.traced("drawing.outside_view_crop")
def _crop_outside_view(adapter: Any, view: Any) -> None:
    """Crop the outside view to OUTSIDE_CROP_FENCE (sheet left, foot, right,
    head) with no outline, read back.

    The fence is sketched direct to the database in the view's own sketch
    and handed to ``IView.Crop2`` (draw_dt_cone_swing_platform's section
    crop).  The proof is the fence's own endpoints, read back in sheet
    coordinates (codjiflo P2 on edb402b); the outline, which pads past the
    fence (5.8-9.8 mm on run 20261027T072743812Z), is only a sanity check
    that the view shrank to about the fence.
    """
    left, foot, right, head = OUTSIDE_CROP_FENCE
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    native = _early_bound(view, "IView")
    if not ddoc.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate the outside view for its crop")
    draw.ClearSelection2(True)
    before = tuple(float(value) for value in native.GetOutline())
    corners = _sheet_points_in_view_sketch(adapter, native, ((left, head), (right, foot)))
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(sketch_manager.AddToDB)
    sketch_manager.AddToDB = True
    try:
        segments = tuple(
            sketch_manager.CreateCornerRectangle(*corners[0], *corners[1]) or ()
        )
    finally:
        sketch_manager.AddToDB = previous_add_to_db
    if len(segments) != 4:
        raise RuntimeError(f"outside view crop fence has {len(segments)} segments, not 4")
    for segment in segments:
        if not _early_bound(segment, "ISketchSegment").Select4(True, None):
            raise RuntimeError("failed to select the outside view's crop fence")
    # IView.Crop2(jagged, no outline, intensity) returns swCropViewErrors_e,
    # where 1 is NoError.
    status = int(native.Crop2(False, True, 0))
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    native.UpdateViewDisplayGeometry()
    if status != 1 or not bool(native.IsCropped()):
        raise RuntimeError(f"outside view crop did not take: Crop2 status {status}")
    if not bool(native.CropViewNoOutline):
        raise RuntimeError("the outside view's crop prints an outline; expected none")
    # The view's frame as it stands after the crop and rebuild, not the
    # transform the fence was drawn with (codjiflo advisory on 09d0c82).
    ends = _sketch_line_ends_on_sheet(adapter, native, segments)
    fence = (
        min(x for x, _ in ends),
        min(y for _, y in ends),
        max(x for x, _ in ends),
        max(y for _, y in ends),
    )
    after = tuple(float(value) for value in native.GetOutline())
    _telemetry.info(f"outside view crop: fence {fence}, outline {before} -> {after}")
    if max(abs(a - b) for a, b in zip(fence, OUTSIDE_CROP_FENCE)) > 1e-6:
        raise RuntimeError(
            f"outside view crop fence reads back {fence}, not {OUTSIDE_CROP_FENCE}"
        )
    pad = 0.015
    removed = (OVERALL_LENGTH - OUTSIDE_CROP_Z) * VIEW_SCALE[0] / 1000.0
    if (
        len(after) != 4
        or after[0] < left - pad
        or after[1] < foot - pad
        or after[2] > right + pad
        or after[3] > head + pad
        or before[2] - after[2] < 0.5 * removed
    ):
        raise RuntimeError(
            f"outside view outline {before} -> {after} is not about its fence "
            f"{OUTSIDE_CROP_FENCE}"
        )


@_telemetry.traced("drawing.outside_view_break")
def _sketch_outside_break(adapter: Any, view: Any) -> None:
    """Draw OUTSIDE_BREAK into the cropped outside view's own sketch as thin
    lines (draw_fr_nameplate's section break), read back on the sheet.

    AddToDB keeps sketch inference from snapping the short Z segments onto
    the step's or the boss's edges."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    native = _early_bound(view, "IView")
    if not ddoc.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate the outside view for its break line")
    draw.ClearSelection2(True)
    sheet_points = [_outside_sheet_xy(y, z) for y, z in OUTSIDE_BREAK]
    points = _sheet_points_in_view_sketch(adapter, native, sheet_points)
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(sketch_manager.AddToDB)
    sketch_manager.AddToDB = True
    segments = []
    try:
        for index, (start, end) in enumerate(zip(points, points[1:])):
            segment = sketch_manager.CreateLine(*start, *end)
            if segment is None:
                raise RuntimeError(f"outside view break line segment {index} failed")
            segments.append(segment)
    finally:
        sketch_manager.AddToDB = previous_add_to_db
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    ends = _sketch_line_ends_on_sheet(adapter, native, segments)
    expected = [xy for pair in zip(sheet_points, sheet_points[1:]) for xy in pair]
    _telemetry.info(f"outside view break line: {ends}")
    if len(ends) != len(expected) or any(
        math.dist(got, want) > 1e-6 for got, want in zip(ends, expected)
    ):
        raise RuntimeError(f"outside view break line reads back {ends}, not {expected}")


def _place_outside_caption(adapter: Any, view: Any) -> None:
    """Insert the outside view's caption at LEFT_CAPTION_XY, owned by that
    view, read back.

    ``add_note`` returns the note even when SetPosition fails, leaving it at
    SolidWorks' default spot (codjiflo P2 on 0772285), so its native position
    and border containment are checked here."""
    note = _insert_view_caption(adapter, view, LEFT_CAPTION, LEFT_CAPTION_XY, "outside view")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    position = tuple(float(value) for value in annotation.GetPosition())
    if math.dist(position[:2], LEFT_CAPTION_XY) > 1e-6:
        raise RuntimeError(
            f"outside view caption stands at {position[:2]}, not {LEFT_CAPTION_XY}"
        )
    _assert_note_inside_border(note, "outside view caption")


@_telemetry.traced("drawing.part_authored_text")
def _assert_part_authored_text(adapter: Any, annotations: list[Any]) -> None:
    """Every imported dimension prints the text lanes its part authored.

    The mates, stacks and station names print nowhere else on the sheet, so
    a lost lane must fail the drawing.  Read-only: text set from the sheet
    would write through to the source part (#1942).
    """
    wanted = callouts.authored_by_name()
    displays: dict[str, list[Any]] = {name: [] for name in wanted}
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name in displays:
            displays[name].append(
                _early_bound(
                    _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
                    "IDisplayDimension",
                )
            )
    counts = {name: len(found) for name, found in displays.items() if len(found) != 1}
    if counts:
        raise RuntimeError(f"authored dimensions not printed exactly once: {counts!r}")
    wrong = {
        (name, lane): text
        for name, lanes in wanted.items()
        for lane in lanes
        if callouts.callout_rows(text := str(displays[name][0].GetText(lane) or ""))
        != callouts.callout_rows(lanes[lane])
    }
    if wrong:
        raise RuntimeError(f"imported dimension text differs from the part's: {wrong!r}")


def _add_sheet_note(
    adapter: Any, text: str, xy: tuple[float, float], *, char_height: float, label: str
) -> None:
    """A sheet note at ``xy`` (top-left) at ``char_height``; its last line is
    read back, so a note that lost its own text raises
    (draw_pd_transgear_knob_shaft._add_sheet_note)."""
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


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open transgear-feed-pinion source", await adapter.open_model(str(SOURCE)))
    source_properties = read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            TOOTH_SPACE_CALLOUT_PROPERTY,
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            TOOTH_SPACE_CALLOUT_PROPERTY,
        ),
    )
    require_source_control(
        source_properties[TOOTH_SPACE_CALLOUT_PROPERTY], callouts.TOOTH_SPACE_CALLOUT,
        label="feed pinion toothspace/index control",
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("pd-transgear-feed-pinion"),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Transgear Pinion Sleeve Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: (
                f"transgear pinion sleeve; steel; {TEETH}T {DIAMETRAL_PITCH:g}DP "
                f"PA{PRESSURE_ANGLE_DEG:g} finite stock form s={inch_text(RADIAL_SETTING, 4)} in; "
                "D-flat boss"
            ),
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(
        adapter, str(SOURCE), END_VIEW_ORIENTATION, *FRONT_CENTER, scale=VIEW_SCALE
    )
    _pin_sheet_scale(adapter)
    right = create_section_view(
        adapter,
        front,
        line_start=SECTION_LINE[0],
        line_end=SECTION_LINE[1],
        view_xy=RIGHT_CENTER,
        section_label="B",
        scale=VIEW_SCALE,
        label="pinion sleeve longitudinal centre section",
    )
    _position_section_caption(adapter, right, SECTION_CAPTION)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    rear = place_view(adapter, str(SOURCE), "*Back", *REAR_CENTER, scale=VIEW_SCALE)
    outside = place_view(adapter, str(SOURCE), "*Left", *LEFT_CENTER, scale=VIEW_SCALE)
    for view in (front, right, iso, rear, outside):
        set_hidden_lines_removed(adapter, view)
    _hide_tangent_edges(outside)
    _crop_outside_view(adapter, outside)
    _place_rear_caption(adapter, rear)
    _place_outside_caption(adapter, outside)

    annotations = []
    # The section first: the outside view then imports only the cutter
    # stations the section deleted (a model dimension prints in one view).
    for view, keep, view_label in (
        (front, FRONT_KEEP, "front"),
        (right, RIGHT_KEEP, "longitudinal section"),
        (outside, LEFT_KEEP, "outside"),
        (rear, REAR_KEEP, "rear face"),
    ):
        annotations += curate_view_dimensions(
            adapter,
            view,
            keep=keep,
            view_label=view_label,
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _assert_part_authored_text(adapter, annotations)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the sleeve bore")
    _create_section_axis_centerline(adapter, right, label="pinion sleeve axis")
    _create_section_axis_centerline(
        adapter, outside, label="outside view axis", nose_mm=OUTSIDE_CROP_Z - 1.0
    )
    _sketch_outside_break(adapter, outside)
    _add_view_arrow(adapter, front, OUTSIDE_VIEW_LETTER, VIEW_C_ARROW)
    _add_view_arrow(adapter, outside, REAR_VIEW_LETTER, VIEW_D_ARROW)

    oil_note = add_leader_note(
        adapter,
        OIL_HOLE_NOTE,
        text_xy=OIL_HOLE_CALLOUT,
        attach_xy=OIL_HOLE_EDGE,
        label="oil hole drill note",
        view=right,
        height=NOTE_HEIGHT,
    )
    adapter.currentModel.GraphicsRedraw2()
    _assert_note_inside_border(oil_note, "oil hole note")
    # The bore is the part's one running surface: its finish is authored on
    # the part and read back here (drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates)).
    add_surface_finish(
        adapter,
        front,
        symbol_xy=FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "bore"),
        label="sleeve bore finish",
        entity=visible_circle_edge(adapter, front, BORE_DIA),
        leader_attach_xy=FINISH_ATTACH,
        char_height=FINISH_CHAR_HEIGHT,
    )
    # Datum A, the bore, where it shows round; the end view has no datum tag
    # yet, as the native placement requires.
    add_native_axis_datum(
        adapter,
        front,
        entity=visible_circle_edge(adapter, front, BORE_DIA),
        source_path=SOURCE,
        radius_m=BORE_DIA / 2000.0,
        datum=BORE_DATUM,
        label="sleeve bore axis",
        shoulder=True,
        stability_tolerance_m=0.0001,
    )
    add_feature_control_frame(
        adapter,
        right,
        edge_xy=STEP_FACE_EDGE,
        frame_xy=STEP_FRAME,
        characteristic="perpendicularity",
        tolerance=GEOMETRIC_TOLERANCES_IN["step face perpendicularity to bore"],
        datums=(BORE_DATUM,),
        label="step face perpendicularity",
    )

    _add_sheet_note(
        adapter,
        GEAR_DATA_NOTE,
        GEAR_DATA_XY,
        char_height=GEAR_DATA_CHAR_HEIGHT,
        label="gear data block",
    )
    add_property_linked_note(
        adapter, "Manufacturing Notes", *NOTES_XY, char_height=0.0025
    )
    add_leader_note(
        adapter,
        TOOTH_EDGE_LEADER_NOTE,
        text_xy=TOOTH_EDGE_NOTE_XY,
        attach_xy=TOOTH_EDGE_ATTACH,
        label="tooth edge note",
        view=rear,
        height=0.0025,
    )
    toothspace_callout = add_toothspace_callout(
        adapter, rear, profile=STOCK_PROFILE,
        actual_pin_diameter_mm=TOOTHSPACE_GAUGE_DIA_MM,
        rotate_rad=TOOTH_SPACE_INSPECTION_PHASE_RAD
        + TOOTH_SPACE_GAP_INDEX * 2.0 * math.pi / TEETH,
        axial_station_mm=TOOTH_SPACE_INSPECTION_END_MM,
        property_name=TOOTH_SPACE_CALLOUT_PROPERTY, note_xy=TOOTH_SPACE_CALLOUT_XY,
    )
    _assert_note_inside_border(toothspace_callout, "toothspace inspection callout")
    rebuild_drawing(adapter, label="pinion sleeve layout audit")
    check_drawing_layout(adapter, layout=SPEC.layout, stem=PART_STEM)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Pinion Sleeve Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
