r"""Create the manufacturing drawing for the transgear knob cup (MHA-PD-16).

Section A-A is the lathe view (drawing-guidelines.md rule 11): it cuts the
cup on its axis through the Front plane, the plane of the turned profile,
and lies axis-horizontal, so the O.D., the length, the end-milled .250
flat-bottom pilot and its depth, the rear head pocket and the two floor
corners' R.xxx MAX limits print together on solid cut edges.
The pilot's callout names the MHA-PD-08 journal it is bonded on and the
diametral clearance it keeps there (rule 23).  The face view, the ``*Top``
orientation turned a quarter, carries the cutting plane and the web's #33
drill for the MHA-PD-VN-71 screw, where it shows round.  The length and the
pilot depth are supply sizes: NOTE 1 gives the fitted pilot depth the front
face is faced to at assembly (rule 19).  The front face is the thrust face on
the MHA-PD-28 bush's rear face (the rear stop of the knob's end float) and
carries its finish under a caption that names that face.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
)

import _config
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
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimensions,
)
from _drawing_finish import add_surface_finish
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _section_axis import create_section_axis_centerline, position_section_caption
from _part_properties import part_drawing_unit
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _printed_limits import drilled_limits, limits
from pd_paper_drive_assembly_steps import step_ref
from pd_transgear_knob_cup_notes import (
    CBORE_DEPTH_CALLOUT,
    PILOT_CORNER_CALLOUT,
    POCKET_CORNER_CALLOUT,
)
from pd_transgear_knob_cup_spec import (
    BORE_DIA,
    BORE_CLEARANCE_TEXT,
    CBORE_DEPTH,
    CBORE_DIA,
    CLEAR_HOLE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    LENGTH,
    OD,
    PILOT_DEPTH,
    PILOT_CLEARANCE,
    PILOT_DEPTH_FITTED_TEXT,
    PILOT_FLOOR_R_MAX,
    POCKET_FLOOR_R_MAX,
    REFERENCE_DIMENSIONS,
    SURFACE_FINISHES,
    UNIT,
    WEB_MIN,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["pd_transgear_knob_cup"]
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

# A Ø.44 x .36 cup: 4:1 keeps the section (37 x 45 mm on the sheet), its
# stacked depth rows and the pilot's callout legible.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
FACE_CENTER = (0.090, 0.170)
SECTION_CENTER = (0.200, FACE_CENTER[1])
# Right of the bore's block (it ends near x 283 mm).
ISO_CENTER = (0.350, FACE_CENTER[1])
# Half the cup's O.D., pilot, pocket and length on the sheet, the pilot's
# and the pocket's depths there, and the cutting line's overrun past the O.D.
HALF_OD = OD * _S / 2000.0
HALF_BORE = BORE_DIA * _S / 2000.0
HALF_CBORE = CBORE_DIA * _S / 2000.0
HALF_LENGTH = LENGTH * _S / 2000.0
PILOT_DEPTH_ON_SHEET = PILOT_DEPTH * _S / 1000.0
CBORE_DEPTH_ON_SHEET = CBORE_DEPTH * _S / 1000.0
SECTION_LINE_OVERRUN = 0.005
# The face view turned a quarter: sheet Y is then model X, so a vertical cut
# on the cup axis is the Front plane, the plane of the turned profile, and
# A-A projects to the right with the cup axis horizontal (the
# draw_dt_crank_handle_ferrule layout).
FACE_VIEW_ANGLE = math.pi / 2.0
SECTION_LINE = (
    (FACE_CENTER[0], FACE_CENTER[1] - HALF_OD - SECTION_LINE_OVERRUN),
    (FACE_CENTER[0], FACE_CENTER[1] + HALF_OD + SECTION_LINE_OVERRUN),
)
# A-A lays the front face on the right (``_orient_section``): its finish
# rises there above the bore's dimension, and the O.D. takes the rear side.
FRONT_FACE_X = SECTION_CENTER[0] + HALF_LENGTH
REAR_FACE_X = SECTION_CENTER[0] - HALF_LENGTH
SECTION_TOP = SECTION_CENTER[1] + HALF_OD
SECTION_BOTTOM = SECTION_CENTER[1] - HALF_OD
# The native SECTION / SCALE caption, top-centre anchored, under the floor
# corners' radius row.
CAPTION_XY = (SECTION_CENTER[0], SECTION_BOTTOM - 0.026)

SHAFT_NUMBER = _config.parts("pd-transgear-knob-shaft")["number"]
BUSH_NUMBER = _config.parts("pd-transgear-knob-bush")["number"]
# drawing-guidelines.md rule 23: a bonded fit is a fit -- the pilot
# is made to fit its mate (rule 4, form 2): its size prints REF, the callout
# says what it is bored to and links note 2, which names the fit and its
# clearance (inside LOCTITE 641's gap fill; the spec asserts it); the method
# is the assembly step's.  A made-to-fit seat is no tight band, so the
# sheet has no necessity register (owner ruling 2026-11-24: no reason is
# printed on the sheet either).  No
# process row: the section draws the pilot's flat floor and R.005 MAX limits
# its corner, so "FLAT BOTTOM END MILL" named a tool, not a requirement
# (rule 7; machinist review r10, three runs).  Two lines of words, each
# within the 24 characters that fit between the front face and the isometric.
FIT_NOTE = 2
BORE_CALLOUT = f"BORE TO {SHAFT_NUMBER}\nSEE NOTE {FIT_NOTE}"
FIT_NOTE_TEXT = (
    f"{FIT_NOTE}. BONDED FIT ON {SHAFT_NUMBER}: CLEARANCE {BORE_CLEARANCE_TEXT}."
)
# The block hangs right of its own vertical dimension line, which drops to
# the shelf under the block's last row: the line struck the first row's text
# (machinist review r1-r3, text on lines).
# A leading space on every row holds the ink off the line
# (draw_ch_fulcrum_shaft's across-flat block), and a closing no-break-space
# row drops the shelf a row below the last.
BORE_CALLOUT_ROWS = "\n".join(f" {row}" for row in BORE_CALLOUT.splitlines()) + "\n\u00a0"
# The supply sizes refer to NOTE 1 (rule 19); the web drill prints its
# process where it shows round.
SUPPLY_CALLOUT = "SEE NOTE 1"
HOLE_CALLOUT = "#33 DRILL THRU"
# The pocket depth's function row is pd_transgear_knob_cup_notes' (the web
# its third place holds), as are the mates the two floor corners seat.
SECTION_CALLOUTS = {
    "BoreDia": BORE_CALLOUT_ROWS,
    "CupLength": SUPPLY_CALLOUT,
    "PilotDepth": SUPPLY_CALLOUT,
    "CboreDepth": CBORE_DEPTH_CALLOUT,
    "PilotFloorR": PILOT_CORNER_CALLOUT,
    "PocketFloorR": POCKET_CORNER_CALLOUT,
}
FACE_CALLOUTS = {"HoleDia": HOLE_CALLOUT}

# Half the height of the bore's value-and-callout block: 31 mm on the
# eecbf88 render for the stacked band over four callout rows, 31.7 mm for
# three and the shelf row (r10); two rows and the shelf row now.
BORE_BLOCK_HALF_HEIGHT = 0.0130
# The O.D. outermost on the rear-face side, between the face view and the
# section; the pocket's Ø inside it, its text dropped below the pocket so the
# two stand apart.  The pilot right of the front face: its block (taller than
# the 25 mm between the pilot's extension lines) stands below the lower one,
# clear of the finish above, the corner radii and the caption to its left,
# its dimension line right of the finish symbol's Ra text.
# Above the section, the two depths on one row, the length a row higher
# with its note reference under it.  Neither depth's text fits its span
# with air to both extension lines, so each stands outside: the pocket
# depth's ".108" over its function row (18 characters, at most 49.9 mm)
# left of the rear face, where the length's extension line rising from that
# face stood 1.39 mm from ".108" alone (r6 audit; 2.0 wanted); the row runs
# over the O.D.'s upper extension line with 3 mm of air and ends 10 mm right
# of the cutting line's upper letter; and the pilot depth's ".152 / SEE NOTE 1" (24 mm
# over 15 mm) right of the front face, where the length's extension line
# no longer strikes its NOTE row and the pocket depth's arrow no longer
# runs into its "S" (r5 render).  Below the section, the two floor corners'
# R.xxx MAX on one row, each over the mate it seats, the caption beneath.
# Each block's near end stands under its own corner, where the r1 render of
# 2026-11-23 began the leader (the pocket's corner 11 mm right of the rear
# face, the pilot's 15 mm left of the front face), so the pocket's block
# runs left from its corner and the pilot's right from its own, 12 mm
# apart, the pilot's ending 20 mm left of the pilot Ø's dimension line.
CORNER_TEXT_ADVANCE = 0.00277  # the callouts' width a character
POCKET_CORNER_HALF_WIDTH = len(POCKET_CORNER_CALLOUT) * CORNER_TEXT_ADVANCE / 2.0
PILOT_CORNER_HALF_WIDTH = len(PILOT_CORNER_CALLOUT) * CORNER_TEXT_ADVANCE / 2.0
CORNER_ROW_Y = SECTION_BOTTOM - 0.013
DEPTH_TEXT_HALF_WIDTH = 0.012  # "SEE NOTE 1", 23.9 mm on the r5 render
# The pocket depth's block: its function row at the callouts' 2.77 mm a
# character (".108" alone was 8.5 mm on the r6 render).
CBORE_DEPTH_TEXT_HALF_WIDTH = len(CBORE_DEPTH_CALLOUT) * 0.00277 / 2.0
SECTION_KEEP = {
    "CupDia": (REAR_FACE_X - 0.030, SECTION_CENTER[1]),
    "CboreDia": (REAR_FACE_X - 0.012, SECTION_CENTER[1] - HALF_CBORE - 0.0055),
    "CboreDepth": (
        REAR_FACE_X - 0.0025 - CBORE_DEPTH_TEXT_HALF_WIDTH, SECTION_TOP + 0.010
    ),
    "PilotDepth": (FRONT_FACE_X + 0.003 + DEPTH_TEXT_HALF_WIDTH, SECTION_TOP + 0.010),
    "CupLength": (SECTION_CENTER[0], SECTION_TOP + 0.026),
    # 10 mm under the pilot's lower extension line: 4 mm under it the
    # "BONDED FIT" row ran a hairline under the isometric's lower rim (r11).
    "BoreDia": (
        FRONT_FACE_X + 0.060,
        SECTION_CENTER[1] - HALF_BORE - BORE_BLOCK_HALF_HEIGHT - 0.010,
    ),
    "PocketFloorR": (REAR_FACE_X + 0.011 - POCKET_CORNER_HALF_WIDTH, CORNER_ROW_Y),
    "PilotFloorR": (FRONT_FACE_X - 0.014 + PILOT_CORNER_HALF_WIDTH, CORNER_ROW_Y),
}
# The web drill's Ø on the face view, up and left of it on a leader.
FACE_KEEP = {"HoleDia": (FACE_CENTER[0] - 0.040, FACE_CENTER[1] + 0.037)}

# The front face's pick lies on its cut edge, midway between the bore and
# the O.D. on the upper half.  The symbol stands level with it, outboard
# past the pilot depth's text, so its leader runs straight in under that
# text and over the pilot's upper extension line (a leader rising to a
# symbol over the face crossed the text's place).
_FRONT_PICK = (
    FRONT_FACE_X,
    SECTION_CENTER[1] + (BORE_DIA + OD) / 4.0 * _S / 1000.0,
)
FRONT_FINISH = (_FRONT_PICK, (_FRONT_PICK[0] + 0.037, _FRONT_PICK[1]))

# Rule 19: the supply sizes and the fitted size, with the step that sets it;
# the float it sets and how are the assembly step's.  Below the face view.
NOTES = (
    "NOTES:\n"
    "1. LENGTH AND PILOT DEPTH ARE SUPPLY SIZES. FITTED\n"
    f"   PILOT DEPTH {PILOT_DEPTH_FITTED_TEXT} AT {step_ref('knob-stack-fitted')}.\n"
    f"{FIT_NOTE_TEXT}"
)
NOTES_XY = (0.020, 0.112)
# The front face's finish caption names the face's function and its mate
# (rule 6: a finish only on a face that runs, slides or locates; machinist
# review: the face's function was stated nowhere).  On the symbol's own row,
# right of its Ra text (which ends 13.7 mm right of the V): over the symbol
# it stood on the pilot depth's ".152 / SEE NOTE 1" row and read as words on
# that dimension (machinist review r10, two runs).  Two rows (rule 7; r11:
# a third, "REAR FACE", was one too many and read as this part's rear), 32.7
# mm wide and top-left anchored, end 2 mm short of the isometric's outline
# and stand over the pilot Ø's upper arrow, which rises 3.5 mm off its
# extension line.
FRONT_FINISH_CAPTION = f"THRUST FACE\nON {BUSH_NUMBER}"
FRONT_FINISH_CAPTION_SIZE_M = (0.0327, 0.0096)
FRONT_FINISH_CAPTION_XY = (FRONT_FINISH[1][0] + 0.016, FRONT_FINISH[1][1] + 0.0105)

# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what this sheet prints, in the part frame
# (pd_transgear_knob_cup_spec: axis +Y; the front face, the running face
# on MHA-PD-28, at y = 0; the pilot's floor at y = PILOT_DEPTH; the pocket's
# floor at y = LENGTH - CBORE_DEPTH; the rear face at y = LENGTH). The O.D.
# and the length take the title block's .XX row, the pilot prints REF and is
# bored to the MHA-PD-08 journal at note 2's clearance, bonded, its depth and the pocket's
# depth the .XXX row, the pocket's Ø the .XX row, the web's #33 the DRILLED
# HOLES row, each floor corner its R MAX. The length and the pilot depth are
# supply sizes: MHA-PD-00 faces the front face to the fitted pilot depth
# (note 1). A counterbore's ``at`` is its floor's centre, so its depth is
# that floor's distance from the face it opens on. The declarations print
# nothing.
DRAWING_NOTES = NOTES
_P = DRAWING_PRECISION_BY_NAME
_SELF = "draw_pd_transgear_knob_cup"
_NOTES = "pd_transgear_knob_cup_notes"
part_metadata(
    model_sources=(
        "LENGTH",
        "OD",
        "BORE_DIA",
        "PILOT_DEPTH",
        "CBORE_DIA",
        "CBORE_DEPTH",
    ),
    precision_sources=("DRAWING_PRECISION", "DRAWING_PRECISION_BY_NAME"),
)
requirement(
    "front_face",
    kind="face",
    faces=(PlanarFace((0.0, -1.0, 0.0), 0.0),),
    requirements=("plane",),
    fields={
        "plane": ({"frame": "model", "axis": "y", "value": 0.0}, ("__frame__",)),
        "outward": ([0.0, -1.0, 0.0], ("__frame__",)),
        "faced_at": ("assembly", ((_SELF, "NOTES"),)),
    },
)
requirement(
    "rear_face",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), LENGTH),),
    requirements=("length",),
    fields={
        "plane": ({"frame": "model", "axis": "y", "value": LENGTH}, ("LENGTH",)),
        "outward": ([0.0, 1.0, 0.0], ("LENGTH",)),
        "length": (
            limits(LENGTH, _P["CupLength"], unit=UNIT),
            ("LENGTH", "UNIT", (_SELF, "SECTION_KEEP")),
        ),
        "length_nominal": (LENGTH, ("LENGTH",)),
        "length_from": ("front_face", ((_SELF, "SECTION_KEEP"),)),
        "supply": (True, ((_SELF, "NOTES"), (_SELF, "SUPPLY_CALLOUT"))),
    },
    precision={"length": _P["CupLength"]},
)
requirement(
    "outside",
    kind="outside_cylinder",
    faces=(CylinderFace(OD),),
    requirements=("dia",),
    fields={
        "at": ([0.0, 0.0, 0.0], ("__frame__",)),
        "axis": ([0.0, 1.0, 0.0], ("__frame__",)),
        "dia": (
            limits(OD, _P["CupDia"], unit=UNIT),
            ("OD", "UNIT", (_SELF, "SECTION_KEEP")),
        ),
        "nominal_dia": (OD, ("OD",)),
        "length_nominal": (LENGTH, ("LENGTH",)),
    },
    precision={"dia": _P["CupDia"]},
)
requirement(
    "pilot",
    kind="counterbore",
    faces=(
        CylinderFace(BORE_DIA, contains_y_mm=PILOT_DEPTH / 2.0),
        PlanarFace((0.0, -1.0, 0.0), -PILOT_DEPTH),
    ),
    requirements=("dia_ref", "depth", "corner_radius_max", "diametral_clearance"),
    fields={
        "at": ([0.0, PILOT_DEPTH, 0.0], ("PILOT_DEPTH",)),
        "axis": ([0.0, 1.0, 0.0], ("__frame__",)),
        "dia_ref": (
            BORE_DIA,
            ("BORE_DIA", "REFERENCE_DIMENSIONS", (_SELF, "SECTION_KEEP")),
        ),
        "depth": (
            limits(PILOT_DEPTH, _P["PilotDepth"], unit=UNIT),
            ("PILOT_DEPTH", "UNIT", (_SELF, "SECTION_KEEP")),
        ),
        "depth_nominal": (PILOT_DEPTH, ("PILOT_DEPTH",)),
        "depth_from": ("front_face", ((_SELF, "SECTION_KEEP"),)),
        "supply": (True, ((_SELF, "NOTES"), (_SELF, "SUPPLY_CALLOUT"))),
        "corner_radius_max": (
            PILOT_FLOOR_R_MAX,
            ("PILOT_FLOOR_R_MAX", "CORNER_SUFFIX"),
        ),
        "diametral_clearance": (
            list(PILOT_CLEARANCE),
            ("PILOT_CLEARANCE", "BORE_CLEARANCE_TEXT", (_SELF, "FIT_NOTE_TEXT")),
        ),
        "mate": (SHAFT_NUMBER, ((_SELF, "SHAFT_NUMBER"), (_SELF, "BORE_CALLOUT"))),
        "bonded": (True, ((_SELF, "FIT_NOTE_TEXT"),)),
        "callout": (BORE_CALLOUT, ((_SELF, "BORE_CALLOUT"),)),
        "note": (FIT_NOTE_TEXT, ((_SELF, "FIT_NOTE_TEXT"),)),
    },
    precision={"dia_ref": _P["BoreDia"], "depth": _P["PilotDepth"]},
)
requirement(
    "web_hole",
    kind="hole",
    faces=(CylinderFace(CLEAR_HOLE_DIA),),
    requirements=("dia", "thru"),
    fields={
        "at": ([0.0, LENGTH - CBORE_DEPTH, 0.0], ("LENGTH", "CBORE_DEPTH")),
        "axis": ([0.0, -1.0, 0.0], ("__frame__",)),
        "dia": (
            drilled_limits(CLEAR_HOLE_DIA, _P["HoleDia"], unit=UNIT),
            ("CLEAR_HOLE_DIA", "HOLE_BAND", "UNIT", (_SELF, "FACE_KEEP")),
        ),
        "nominal_dia": (CLEAR_HOLE_DIA, ("CLEAR_HOLE_DIA",)),
        "thru": (True, ((_SELF, "HOLE_CALLOUT"),)),
        "process": ("drill", ((_SELF, "HOLE_CALLOUT"),)),
        "drill": ("#33", ((_SELF, "HOLE_CALLOUT"),)),
        "callout": (HOLE_CALLOUT, ((_SELF, "HOLE_CALLOUT"),)),
    },
    precision={"dia": _P["HoleDia"]},
)
requirement(
    "pocket",
    kind="counterbore",
    faces=(
        CylinderFace(CBORE_DIA, contains_y_mm=LENGTH - CBORE_DEPTH / 2.0),
        PlanarFace((0.0, 1.0, 0.0), LENGTH - CBORE_DEPTH),
    ),
    requirements=("dia", "depth", "corner_radius_max"),
    fields={
        "at": ([0.0, LENGTH - CBORE_DEPTH, 0.0], ("LENGTH", "CBORE_DEPTH")),
        "axis": ([0.0, -1.0, 0.0], ("__frame__",)),
        "dia": (
            limits(CBORE_DIA, _P["CboreDia"], unit=UNIT),
            ("CBORE_DIA", "UNIT", (_SELF, "SECTION_KEEP")),
        ),
        "nominal_dia": (CBORE_DIA, ("CBORE_DIA",)),
        "depth": (
            limits(CBORE_DEPTH, _P["CboreDepth"], unit=UNIT),
            ("CBORE_DEPTH", "UNIT", (_SELF, "SECTION_KEEP")),
        ),
        "depth_nominal": (CBORE_DEPTH, ("CBORE_DEPTH",)),
        "depth_from": ("rear_face", ((_SELF, "SECTION_KEEP"),)),
        "corner_radius_max": (
            POCKET_FLOOR_R_MAX,
            ("POCKET_FLOOR_R_MAX", "CORNER_SUFFIX"),
        ),
        "web_min": (WEB_MIN, ("WEB_MIN", (_NOTES, "CBORE_DEPTH_CALLOUT"))),
        "callout": (CBORE_DEPTH_CALLOUT, ((_NOTES, "CBORE_DEPTH_CALLOUT"),)),
    },
    precision={"dia": _P["CboreDia"], "depth": _P["CboreDepth"]},
)
# A note's read-back position may differ from the one asked by this much.
NOTE_POSITION_TOL_M = 5e-4
# How far A-A's axis may sit from SECTION_CENTER / level before it is moved.
SECTION_POSITION_TOL_M = 1e-4


def _add_placed_note(
    adapter: Any, text: str, xy: tuple[float, float], label: str
) -> None:
    """Insert a free note and prove it landed at ``xy``.

    ``add_note`` only logs a failed ``IAnnotation.SetPosition``, which would
    leave the note at SolidWorks' default spot, so read the position back.
    """
    raw_note = add_note(adapter, text, *xy)
    if raw_note is None:
        raise RuntimeError(f"failed to add the {label}")
    raw_annotation = _early_bound(raw_note, "INote").GetAnnotation()
    if raw_annotation is None:
        raise RuntimeError(f"the {label} has no annotation")
    annotation = _early_bound(raw_annotation, "IAnnotation")
    position = tuple(float(value) for value in (annotation.GetPosition() or ()))
    if len(position) < 2 or any(
        abs(actual - wanted) > NOTE_POSITION_TOL_M
        for actual, wanted in zip(position[:2], xy, strict=True)
    ):
        raise RuntimeError(f"the {label} sits at {position[:2]}, not {xy}")


def _turn_face_view(adapter: Any, face: Any) -> None:
    """Turn the face view a quarter so the cut on its vertical centreline is
    the Front plane (``FACE_VIEW_ANGLE``)."""
    native = _early_bound(face, "IView")
    native.Angle = FACE_VIEW_ANGLE
    if abs(math.remainder(float(native.Angle) - FACE_VIEW_ANGLE, 2.0 * math.pi)) > 1e-9:
        raise RuntimeError("failed to turn the knob-cup face view a quarter")
    rebuild_drawing(adapter, label="knob cup face view turned")


def _section_axis_ends(adapter: Any, native: Any) -> tuple[tuple[float, float], ...]:
    """Sheet points of the cup axis at the front (y = 0) and rear faces."""
    return tuple(
        model_points_in_view(
            adapter,
            native,
            ((0.0, 0.0, 0.0), (0.0, LENGTH / 1000.0, 0.0)),
            label="knob cup section axis",
            names=("front", "rear"),
        )
    )


def _orient_section(adapter: Any, section: Any) -> None:
    """Lay A-A axis-horizontal, front face right, its axis on SECTION_CENTER.

    Cut from the quarter-turned face view, A-A lies axis-horizontal; which
    end the front face takes is read, not assumed, and a half turn (no
    change to a solid of revolution's section) puts it on the right.  Any
    other turn means the cut is not the expected projection: refuse it.
    """
    native = _early_bound(section, "IView")
    front, rear = _section_axis_ends(adapter, native)
    turn = math.atan2(front[1] - rear[1], front[0] - rear[0])
    if abs(turn) > 1e-6:
        if abs(abs(turn) - math.pi) > 1e-6:
            raise RuntimeError(
                f"knob cup A-A axis runs {math.degrees(turn):.3f} deg off the "
                f"sheet's horizontal (front {front}, rear {rear})"
            )
        native.Angle = float(native.Angle) - turn
        rebuild_drawing(adapter, label="knob cup section turned")
        front, rear = _section_axis_ends(adapter, native)
    middle = ((front[0] + rear[0]) / 2.0, (front[1] + rear[1]) / 2.0)
    shift = (SECTION_CENTER[0] - middle[0], SECTION_CENTER[1] - middle[1])
    if math.hypot(*shift) > SECTION_POSITION_TOL_M:
        position = tuple(float(value) for value in native.Position)
        if not native.SetViewPosition(
            double_array([position[0] + shift[0], position[1] + shift[1]]), False
        ):
            raise RuntimeError("failed to centre the knob cup section")
        rebuild_drawing(adapter, label="knob cup section centred")
        front, rear = _section_axis_ends(adapter, native)
    expected = (
        (FRONT_FACE_X, SECTION_CENTER[1]),
        (FRONT_FACE_X - 2 * HALF_LENGTH, SECTION_CENTER[1]),
    )
    if any(
        math.dist(actual, wanted) > SECTION_POSITION_TOL_M
        for actual, wanted in zip((front, rear), expected, strict=True)
    ):
        raise RuntimeError(
            f"knob cup A-A axis ends at front {front}, rear {rear}; wanted {expected}"
        )
    _telemetry.info(
        f"knob cup A-A angle={float(native.Angle):.6f} rad, turn={turn:.6f}"
    )


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open knob-cup source", adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Transgear Knob Cup Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear knob cup; turned brass",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    face = place_view(adapter, str(SOURCE), "*Top", *FACE_CENTER, scale=VIEW_SCALE)
    _turn_face_view(adapter, face)
    section = create_section_view(
        adapter,
        face,
        line_start=SECTION_LINE[0],
        line_end=SECTION_LINE[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="knob cup axial section",
    )
    _orient_section(adapter, section)
    position_section_caption(adapter, section, CAPTION_XY, label="knob cup")
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (face, section, iso):
        set_hidden_lines_removed(adapter, view)

    section_annotations = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="axial section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    face_annotations = curate_view_dimensions(
        adapter,
        face,
        keep=FACE_KEEP,
        view_label="face view",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Decimal places (and so the general-tolerance row each dimension claims)
    # and the pilot's band are authored on the part; the sheet only proves the
    # import kept them.
    assert_imported_precision(
        adapter, section_annotations + face_annotations, DRAWING_PRECISION_BY_NAME
    )
    set_dimension_callouts(adapter, section_annotations, SECTION_CALLOUTS)
    set_reference_dimensions(adapter, section_annotations, REFERENCE_DIMENSIONS)
    set_dimension_callouts(adapter, face_annotations, FACE_CALLOUTS)
    create_section_axis_centerline(
        adapter, section, length_mm=LENGTH, label="knob cup axis"
    )
    if not auto_center_marks(adapter, face, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the cup face view")
    pick, symbol = FRONT_FINISH
    add_surface_finish(
        adapter,
        section,
        edge_xy=pick,
        symbol_xy=symbol,
        control=surface_finish_by_key(SURFACE_FINISHES, "front_face"),
        label="cup front (running) face finish",
        char_height=0.0025,
    )
    _add_placed_note(
        adapter,
        FRONT_FINISH_CAPTION,
        FRONT_FINISH_CAPTION_XY,
        "front face finish caption",
    )
    _add_placed_note(adapter, NOTES, NOTES_XY, "supply and fit-up notes")

    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Knob Cup Manufacturing Drawing",
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
