r"""Create the manufacturing drawing for the latch hook (MHA-PD-14).

One formed spring-steel part, printed in decimal inch (the row's
``drawing_unit: in``), all orthographic views at 3:2 (each pinned so
the part origin -- the ear's outer face, the base's underside and its low-Y
edge -- lands where the layout puts it):

* ``*Front`` (looking -Z, X right, Y up; hidden lines removed): the screw
  holes on the base, located from the ear's outer face and the low-Y edge;
  the arm's formed profile -- the roll's start below the ear, its inside
  radius (shortened leader: the centre is off the sheet), the inside tab
  radius, the tab end's X and the far face where the pin crosses it, in X
  and Y from the origin, ending on the pin's axis, drawn as a centreline --
  and the straight's length as a reference;
* ``*Right`` (looking -X, Z running left): the width, the root relief and
  the full round; the pin hole's size and note 2 (its centre transferred at
  assembly) on a leader to its rim; left of it the formed overall height,
  a reference from
  the ear's top edge to the full round's tip; beside it the flat pattern,
  the part's hidden ``FlatBlank`` reference sketch shown in this view only
  (labelled FLAT PATTERN; its outline black at the visible-edge
  weight, its bend centrelines black chain lines): the blank across the
  bend, the arm's two strip widths (its controlling widths), its developed
  stations of the taper and the round's centre (centre-marked), and the
  bend centrelines' references;
* ``*Bottom`` (looking +Y, X right, Z up), projected under the front view
  (third angle, so unlabelled): the base length, the ear height and the
  inside bend.

The stock and its temper ride the title block's MATERIAL and FINISH cells;
the fit-up sequence is the assembly's (the registry row's process).
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
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
    stamp_drawing_summary,
)
from _drawing_dimensions import (
    assert_imported_precision,
    set_arc_endpoints_to_max,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension
from _drawing_edges import scan_view_edges
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_leader_notes import add_attached_note
from _drawing_notes import add_property_linked_note
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _printed_limits import drilled_limits, limits
from _printed_tolerance import printed_deviations
from _session import run_build
import _telemetry
from build_pd_latch_hook import FAR_FACE_POINT, FLAT_GAP
from pd_latch_hook_geometry import (
    ARM_N,
    ARM_U,
    ARM_W,
    BASE_LENGTH,
    BBOX_X,
    BBOX_Y,
    BBOX_Z,
    DEV_ROLL_C,
    DEV_TAB_C,
    DEV_TAPER,
    DEV_TIP,
    EAR_HEIGHT,
    FLAT_BEND_C,
    FLAT_LENGTH,
    INNER_ROLL_R,
    INNER_TAB_R,
    INSIDE_BEND_R,
    K_BEND,
    LOW_W,
    OUTER_ROLL_END,
    OUTER_ROLL_R,
    OUTER_ROLL_START,
    OUTER_TAB_END,
    OUTER_TAB_R,
    OUTER_TAB_START,
    OUTSIDE_BEND_R,
    PART_ORIGIN_MACHINE,
    PIN_HOLE_DIA,
    PIN_HOLE_L,
    PIN_HOLE_ZL,
    ROLL_TURN_DEG,
    ROOT_R,
    ROUND_C_L,
    ROUND_R,
    SCREW_HOLE_DIA,
    SCREW_HOLE_X,
    SCREW_HOLE_Y,
    SHEET_T,
    SHEET_T_MINUS,
    SHEET_T_PLUS,
    TAB_C_L,
    TAB_TURN_DEG,
    TAPER_L,
    WIDTH,
)
from pd_latch_hook_spec import (
    BEND_LINE_DIMENSIONS,
    BEND_TOL_DEG,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    FLAT_SKETCH,
    FORMED_PLACES,
    FORMED_TOL,
    HOLE_PLACES,
    MATERIAL_TITLE,
    OVERALL_HEIGHT,
    PAIR_CALLOUT,
    PIN_HOLE_CALLOUT,
    PIN_HOLE_NOTE,
    REFERENCE_DIMENSIONS,
    ROUND_CALLOUT,
    ROUND_REFERENCE,
    SCREW_HOLE_CALLOUT,
    SCREW_HOLE_MATE,
    SCREW_HOLE_WALL_TEXT,
    UNIT,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_latch_hook"]
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

# A 30 x 97 x 16 mm formed part: 3:2 keeps the arm's drop and its dimensions
# between the border and the title block, and the .032 strip legible.
SHEET_SCALE = (3.0, 2.0)
VIEW_SCALE = (3, 2)
ISO_SCALE = (1, 2)
_S = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0  # sheet metres per model mm
_PIN_TOL_M = 1e-4  # how close a pinned view's origin must land

# The part's local bounding box (mm): X and Y on the front view, Z the band.
_LOCAL_X = tuple(x - PART_ORIGIN_MACHINE[0] for x in BBOX_X)
_LOCAL_Y = tuple(y - PART_ORIGIN_MACHINE[1] for y in BBOX_Y)
_LOCAL_Z = tuple(z - PART_ORIGIN_MACHINE[2] for z in BBOX_Z)
_MID_X = sum(_LOCAL_X) / 2.0
_MID_Y = sum(_LOCAL_Y) / 2.0
_MID_Z = sum(_LOCAL_Z) / 2.0

# View centres (the part's bounding box centre on the sheet): the front view
# at the left, the side view and its flat pattern level with it, the bottom
# view projected under the front view (its top clear under the front view's
# lowest text), the isometric at the right above the title block (top
# 0.066), the notes in the free top-right corner.
FRONT_CENTER = (0.072, 0.170)
RIGHT_CENTER = (0.205, FRONT_CENTER[1])
BOTTOM_CENTER = (FRONT_CENTER[0], 0.0544)
ISO_CENTER = (0.380, 0.135)
NOTES_XY = (0.316, 0.262)
ISO_NOTE_XY = (ISO_CENTER[0] - 0.030, ISO_CENTER[1] - 0.035)
FLAT_NOTE_XY = (0.245, 0.083)
NOTE_HEIGHT = 0.003  # the notes' characters (top-left anchored)

# Where each view puts the part origin.
FRONT_ORIGIN = (FRONT_CENTER[0] - _MID_X * _S, FRONT_CENTER[1] - _MID_Y * _S)
RIGHT_ORIGIN = (RIGHT_CENTER[0] + _MID_Z * _S, FRONT_ORIGIN[1])
BOTTOM_ORIGIN = (BOTTOM_CENTER[0] - _MID_X * _S, BOTTOM_CENTER[1] - _MID_Z * _S)


def _front(x_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet point of a local (X, Y) on the front view."""
    return (FRONT_ORIGIN[0] + x_mm * _S, FRONT_ORIGIN[1] + y_mm * _S)


def _right(z_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet point of a local (Z, Y) on the side view (Z runs left)."""
    return (RIGHT_ORIGIN[0] - z_mm * _S, RIGHT_ORIGIN[1] + y_mm * _S)


def _flat(u_mm: float, v_mm: float) -> tuple[float, float]:
    """Sheet point of a FlatBlank sketch point (Right-plane sketch x, y)."""
    return (RIGHT_ORIGIN[0] + u_mm * _S, RIGHT_ORIGIN[1] + v_mm * _S)


def _bottom(x_mm: float, z_mm: float) -> tuple[float, float]:
    """Sheet point of a local (X, Z) on the bottom view."""
    return (BOTTOM_ORIGIN[0] + x_mm * _S, BOTTOM_ORIGIN[1] + z_mm * _S)


def _on(point: tuple[float, float], u: float, n: float = 0.0) -> tuple[float, float]:
    """``point`` moved ``u`` along ARM_U and ``n`` along ARM_N (local mm)."""
    return (
        point[0] + u * ARM_U[0] + n * ARM_N[0],
        point[1] + u * ARM_U[1] + n * ARM_N[1],
    )


# Per-view survivors of the marked-dimension import: name -> sheet position.
# Front: the screw X pair stacked above the base, their texts right of the
# ear's outer face (its extension line crossed them between the arrows,
# review 4), their Y left of it; the roll start and the far face's
# Y right of the arm, the roll start inside so its text clears the far
# face's dimension line; the far face's X
# and the tab end's X stacked below it; the straight's length on the arm's
# -U side (its extension set clear of the far face's X, which drops from the
# far face);
# the inside roll radius in the roll's concave side, the tab radius outside
# the tab, its leader radial through the middle of the tab's 35 deg arc
# (147-182 deg about its centre), clear of the end face and its X.
# The screws' size and its five-row callout stand far left and low, ~3 mm
# over the roll radius's break: SolidWorks centres the block on this point
# and runs the leader from the last row's underline, 1/16 in past the widest
# row (FOR ... TAPS; LOCATE ... TAPS in that run), straight at the far
# hole's centre.  From (-25, -8) that line climbed 25 deg off vertical
# through the S of TAPS (farm run
# 20261105T023327427Z, layout audit dim-line-through-own-text); here it
# rises 7 deg off vertical, ~0.7 mm clear of TAPS, the block's left end
# 3 mm inside the border and its 2X 18 mm under ScrewY's extension.
_TAB_LEADER_DEG = 165.0
FRONT_KEEP = {
    "ScrewX2": _front(11.0, 12.5),
    "ScrewX1": _front(11.0, 17.5),
    "ScrewY": _front(-32.0, SCREW_HOLE_Y / 2.0),
    "ScrewDia": _front(-30.8, -21.0),
    "RollStart": _front(14.0, OUTER_ROLL_START[1] / 2.0),
    "FaceY": _front(24.0, FAR_FACE_POINT[1] / 2.0),
    "FaceX": _front(FAR_FACE_POINT[0] / 2.0, -96.0),
    "TabEndX": _front(OUTER_TAB_END[0] / 2.0, -103.0),
    "StraightLen": _front(*_on(OUTER_ROLL_END, -28.0, -5.0)),
    "RollR": _front(-20.0, -35.0),
    "TabR": _front(
        TAB_C_L[0] + 26.0 * math.cos(math.radians(_TAB_LEADER_DEG)),
        TAB_C_L[1] + 26.0 * math.sin(math.radians(_TAB_LEADER_DEG)),
    ),
}
# Side view: the width left of the ear, the root relief right of its corner,
# the round under the tip; the flat's length above it over the ear bend's
# centreline; its two strip widths (the arm's controlling widths) left of
# it, between the views; its developed stations stacked to its right, the
# longer outside (the roll's centreline among them, its text clear below
# the taper's), the tab's centreline chained under the round's centre, its
# text below the blank's tip.
RIGHT_KEEP = {
    "Width": _right(26.0, 4.0),
    "RootR": _right(-4.0, -8.0),
    "RoundR": _right(-6.0, -95.0),
    "FlatBendC": _flat(FLAT_GAP + FLAT_BEND_C / 2.0, 14.0),
    "FlatLength": _flat(FLAT_GAP + FLAT_LENGTH / 2.0, 19.5),
    "FlatArmW": _flat(10.0, -12.0),
    "FlatLowW": _flat(10.0, -40.0),
    "DevTaper1": _flat(58.0, -DEV_TAPER[0] / 2.0),
    "DevTaper2": _flat(66.0, -DEV_TAPER[1] / 2.0),
    "FlatRollC": _flat(74.0, -DEV_ROLL_C / 2.0),
    "DevRoundC": _flat(82.0, -50.0),
    "FlatTabC": _flat(82.0, -(DEV_TIP + 4.0)),
}
# Bottom view: the base length well under the base, the ear height right of
# the ear, and the inside bend's text between the two, right of the ear: its
# radial leader leaves the bend at 45 deg, through the corner gap between
# the two dimensions' extension lines, and crosses no dimension line (review
# 4: from below, it cut the base length's).  SolidWorks lands that leader on
# an underline under the text.
BOTTOM_KEEP = {
    "BaseLength": _bottom(-BASE_LENGTH / 2.0, -11.0),
    "EarHeight": _bottom(6.0, EAR_HEIGHT / 2.0),
    "InsideBendR": _bottom(13.0, -2.0),
}
CALLOUTS_ABOVE = {
    "ScrewDia": PAIR_CALLOUT,
}
# The screw-hole callout's last line states the holes' finished wall to the
# base's edges, under the .080 target (rule 20; pd-latch-hook.yaml).  The
# location dimensions (FaceX/FaceY, DevRoundC) carry no words (rule 7): they
# end on the pin axis's centreline and the full round's centre mark.
CALLOUTS_BELOW = {
    "ScrewDia": f"{SCREW_HOLE_CALLOUT}\n{SCREW_HOLE_MATE}\n{SCREW_HOLE_WALL_TEXT}",
    "RoundR": ROUND_CALLOUT,
}
# The pin's axis where it crosses the strip, the far face's reference
# station's end: a centreline along U through the far face point, past the
# near and far faces by the overshoot (3 mm on the sheet at 3:2).  Part-frame
# millimetres (x, y, z), z the pin's height.
PIN_AXIS_OVERSHOOT_MM = 2.0
PIN_AXIS_ENDS = tuple(
    (
        FAR_FACE_POINT[0] + run * ARM_U[0],
        FAR_FACE_POINT[1] + run * ARM_U[1],
        PIN_HOLE_ZL,
    )
    for run in (-(SHEET_T + PIN_AXIS_OVERSHOOT_MM), PIN_AXIS_OVERSHOOT_MM)
)
# The flat pattern's full-round centre in FlatBlank sketch (u, v) = model
# (-Z, Y): DevRoundC and FlatTabC end on it, so it carries a centre mark, a
# cross of two centrelines CENTRE_MARK_ARM_MM each way (3 mm on the sheet).
FLAT_ROUND_CENTRE = (FLAT_GAP + ROUND_R, ROUND_R - DEV_TIP)
CENTRE_MARK_ARM_MM = 2.0
FLAT_ROUND_MARK_ENDS = tuple(
    tuple(
        (0.0, FLAT_ROUND_CENTRE[1] + dv * sign, -(FLAT_ROUND_CENTRE[0] + du * sign))
        for sign in (-1.0, 1.0)
    )
    for du, dv in ((CENTRE_MARK_ARM_MM, 0.0), (0.0, CENTRE_MARK_ARM_MM))
)
# The pin hole's callout (PIN_HOLE_NOTE, size first) on the side view, where
# the hole shows its outline; the front view has it edge-on, in hidden lines
# only, and draws hidden lines no more (round 2: the Ø.128 ran to them).
# The leader lands on the far-face rim, the face toward the side view's +X
# viewer (U leans +X), at its -Z point (screen right).  The note stands right
# of the strip (edge x ~0.2117), left of the flat pattern (x ~0.2466), its
# top level just over the hole (y ~0.1248), so the leader runs nearly level.
_PIN_RIM_RUN = (FAR_FACE_POINT[0] - PIN_HOLE_L[0]) * ARM_U[0] + (
    FAR_FACE_POINT[1] - PIN_HOLE_L[1]
) * ARM_U[1]
PIN_RIM_CENTRE = (
    PIN_HOLE_L[0] + _PIN_RIM_RUN * ARM_U[0],
    PIN_HOLE_L[1] + _PIN_RIM_RUN * ARM_U[1],
    PIN_HOLE_ZL,
)
PIN_RIM_AXIS = (ARM_U[0], ARM_U[1], 0.0)
PIN_RIM_LANDING = (
    PIN_RIM_CENTRE[0],
    PIN_RIM_CENTRE[1],
    PIN_RIM_CENTRE[2] - PIN_HOLE_DIA / 2.0,
)
PIN_NOTE_XY = (0.2155, 0.1300)
# The roll's centre sits ~80 mm left of the vertical: off the sheet at 3:2.
SHORTENED_RADII = ("RollR",)
# The formed overall height (drawing-guidelines.md rule 10 (dimension from a real feature)), a reference left of the side view: its
# dimension line passes left of the width's text, its text below the front
# view's far-face Y level and clear right of it; picked on the ear's top edge and
# on the full round, re-anchored to the round's far extreme (its tip).
_ROUND_PICK_DEG = -120.0  # on the round, clear of its tip and the RoundR leader
OVERALL_PICKS = (
    _right(12.0, WIDTH),
    _right(
        ROUND_C_L[1] + ROUND_R * math.cos(math.radians(_ROUND_PICK_DEG)),
        ROUND_C_L[0] + ROUND_R * math.sin(math.radians(_ROUND_PICK_DEG)),
    ),
)
OVERALL_TEXT_XY = _right(38.0, -55.0)

# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what this sheet prints, in the part frame
# (build_pd_latch_hook's docstring: origin at the ear's outer face x = 0, the
# base's underside z = 0 and its low-Y edge y = 0).  The hook is one strip
# blank, the flat pattern: FlatLength across the ear's bend, the base's width
# plus the arm's developed length along the arm.  The ear is bent, the screw
# holes drilled from its outer face, the arm rolled and the tab formed; the
# pin hole is transferred at assembly (note 2).  The formed arm's values take
# the printed ±FORMED_TOL on their printed .XX value; the developed stations
# are the flat pattern's.  The declarations print nothing.
_P = DRAWING_PRECISION_BY_NAME
_SELF = "draw_pd_latch_hook"
_GEOM = "pd_latch_hook_geometry"
_KEEPS = (
    ("FRONT_KEEP", FRONT_KEEP),
    ("RIGHT_KEEP", RIGHT_KEEP),
    ("BOTTOM_KEEP", BOTTOM_KEEP),
)
_NOTE_LINES = DRAWING_NOTES.split("\n")
RADII_NOTE = _NOTE_LINES[0].removeprefix("1. ")
PIN_NOTE = " ".join(line.strip() for line in _NOTE_LINES[1:]).removeprefix("2. ")
_ARM_FRONT_Z = EAR_HEIGHT - ARM_W  # the arm's front edge above the taper
_ARM_LOW_Z = EAR_HEIGHT - LOW_W  # and below it
_TAPER_RUN = math.hypot(TAPER_L[1] - TAPER_L[0], _ARM_LOW_Z - _ARM_FRONT_Z)
# The taper's outward normal: square to its run in (y, z), toward -Z.
_TAPER_N = (
    0.0,
    (_ARM_FRONT_Z - _ARM_LOW_Z) / _TAPER_RUN,
    (TAPER_L[1] - TAPER_L[0]) / _TAPER_RUN,
)
_FAR_N = (ARM_U[0], ARM_U[1], 0.0)  # the straight's far face looks along +U


def _g(*names: str) -> tuple[tuple[str, str], ...]:
    return tuple((_GEOM, name) for name in names)


def _keep(name: str) -> tuple[str, str]:
    """The view table that places a printed dimension."""
    return next((_SELF, keep) for keep, table in _KEEPS if name in table)


def _row(value: float, name: str, *sources) -> tuple[list[float], tuple]:
    """A title-block band on the printed ``name``."""
    return (
        limits(value, _P[name], unit=UNIT),
        (*sources, "DRAWING_PRECISION_BY_NAME", "UNIT", _keep(name)),
    )


def _formed(value: float, name: str, *sources) -> tuple[list[float], tuple]:
    """A formed arm value: its printed .XX value ±FORMED_TOL."""
    low, high = printed_deviations(
        value, FORMED_PLACES, (-FORMED_TOL, FORMED_TOL), unit=UNIT
    )
    return (
        [round(value + low, 12), round(value + high, 12)],
        (*sources, "FORMED_TOL", "FORMED_PLACES", "UNIT", _keep(name)),
    )


part_metadata(
    model_sources=_g("PART_ORIGIN_MACHINE", "SHEET_T", "WIDTH", "EAR_HEIGHT"),
    precision_sources=("DRAWING_PRECISION", "DRAWING_PRECISION_BY_NAME", "HOLE_PLACES"),
)
requirement(
    "strip",
    kind="blank",
    faces=(PlanarFace((0.0, 0.0, 1.0), SHEET_T),),
    requirements=("width", "thickness", "developed_length"),
    fields={
        "section": ("strip", _g("SHEET_T")),
        "width": _row(FLAT_LENGTH, "FlatLength", *_g("FLAT_LENGTH")),
        "width_nominal": (FLAT_LENGTH, _g("FLAT_LENGTH")),
        "thickness": (
            [SHEET_T - SHEET_T_MINUS, SHEET_T + SHEET_T_PLUS],
            (*_g("SHEET_T", "SHEET_T_MINUS", "SHEET_T_PLUS"), "MATERIAL_TITLE"),
        ),
        "thickness_nominal": (SHEET_T, _g("SHEET_T")),
        "developed_length": (WIDTH + DEV_TIP, _g("WIDTH", "DEV_TIP")),
        "k_factor": (K_BEND, _g("K_BEND")),
        "material": (MATERIAL_TITLE, ("MATERIAL_TITLE",)),
        "radii_note": (RADII_NOTE, ("DRAWING_NOTES",)),
    },
    precision={"width": _P["FlatLength"]},
)
requirement(
    "base_underside",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("plane",),
    fields={
        "plane": (
            {"frame": "model", "axis": "z", "value": 0.0},
            _g("PART_ORIGIN_MACHINE"),
        )
    },
)
requirement(
    "ear_face",
    kind="face",
    faces=(PlanarFace((1.0, 0.0, 0.0), 0.0),),
    requirements=("plane",),
    fields={
        "plane": (
            {"frame": "model", "axis": "x", "value": 0.0},
            _g("PART_ORIGIN_MACHINE"),
        )
    },
)
requirement(
    "low_edge",
    kind="face",
    faces=(PlanarFace((0.0, -1.0, 0.0), 0.0),),
    requirements=("plane",),
    fields={
        "plane": (
            {"frame": "model", "axis": "y", "value": 0.0},
            _g("PART_ORIGIN_MACHINE"),
        )
    },
)
requirement(
    "base_end",
    kind="face",
    faces=(PlanarFace((-1.0, 0.0, 0.0), BASE_LENGTH),),
    requirements=("length",),
    fields={
        "plane": (
            {"frame": "model", "axis": "x", "value": -BASE_LENGTH},
            _g("BASE_LENGTH"),
        ),
        "length": _row(BASE_LENGTH, "BaseLength", *_g("BASE_LENGTH")),
        "length_nominal": (BASE_LENGTH, _g("BASE_LENGTH")),
        "length_from": ("ear_face", (_keep("BaseLength"),)),
    },
    precision={"length": _P["BaseLength"]},
)
requirement(
    "side_edge",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), WIDTH),),
    requirements=("width",),
    fields={
        "plane": ({"frame": "model", "axis": "y", "value": WIDTH}, _g("WIDTH")),
        "width": _row(WIDTH, "Width", *_g("WIDTH")),
        "width_nominal": (WIDTH, _g("WIDTH")),
        "width_from": ("low_edge", (_keep("Width"),)),
    },
    precision={"width": _P["Width"]},
)
requirement(
    "ear_top",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), EAR_HEIGHT),),
    requirements=("height",),
    fields={
        "plane": (
            {"frame": "model", "axis": "z", "value": EAR_HEIGHT},
            _g("EAR_HEIGHT"),
        ),
        "height": _row(EAR_HEIGHT, "EarHeight", *_g("EAR_HEIGHT")),
        "height_nominal": (EAR_HEIGHT, _g("EAR_HEIGHT")),
        "height_from": ("base_underside", (_keep("EarHeight"),)),
    },
    precision={"height": _P["EarHeight"]},
)
requirement(
    "ear_bend",
    kind="bend",
    faces=(CylinderFace(2.0 * INSIDE_BEND_R), CylinderFace(2.0 * OUTSIDE_BEND_R)),
    requirements=("radius",),
    fields={
        "radius": _row(INSIDE_BEND_R, "InsideBendR", *_g("INSIDE_BEND_R")),
        "radius_nominal": (INSIDE_BEND_R, _g("INSIDE_BEND_R")),
        "angle": ([90.0 - BEND_TOL_DEG, 90.0 + BEND_TOL_DEG], ("BEND_TOL_DEG",)),
        "angle_nominal": (90.0, _g("BEND_ALLOWANCE")),
        "flat_centreline": (FLAT_BEND_C, (*_g("FLAT_BEND_C"), "BEND_LINE_DIMENSIONS")),
    },
    precision={"radius": _P["InsideBendR"]},
)
requirement(
    "roll",
    kind="bend",
    faces=(CylinderFace(2.0 * INNER_ROLL_R), CylinderFace(2.0 * OUTER_ROLL_R)),
    requirements=("radius", "start"),
    fields={
        "radius": _formed(INNER_ROLL_R, "RollR", *_g("INNER_ROLL_R")),
        "radius_nominal": (INNER_ROLL_R, _g("INNER_ROLL_R")),
        "angle": (ROLL_TURN_DEG, _g("ROLL_TURN_DEG")),
        "start": _formed(-OUTER_ROLL_START[1], "RollStart", *_g("OUTER_ROLL_START")),
        "start_nominal": (-OUTER_ROLL_START[1], _g("OUTER_ROLL_START")),
        "start_from": ("low_edge", (_keep("RollStart"),)),
        "flat_centreline": (DEV_ROLL_C, (*_g("DEV_ROLL_C"), "BEND_LINE_DIMENSIONS")),
    },
    precision={"radius": FORMED_PLACES, "start": FORMED_PLACES},
)
requirement(
    "tab",
    kind="bend",
    faces=(CylinderFace(2.0 * OUTER_TAB_R), CylinderFace(2.0 * INNER_TAB_R)),
    requirements=("radius", "end_x"),
    fields={
        "radius": _formed(OUTER_TAB_R, "TabR", *_g("OUTER_TAB_R")),
        "radius_nominal": (OUTER_TAB_R, _g("OUTER_TAB_R")),
        "angle": (TAB_TURN_DEG, _g("TAB_TURN_DEG")),
        "end_x": _formed(-OUTER_TAB_END[0], "TabEndX", *_g("OUTER_TAB_END")),
        "end_x_nominal": (-OUTER_TAB_END[0], _g("OUTER_TAB_END")),
        "end_x_from": ("ear_face", (_keep("TabEndX"),)),
        "flat_centreline": (DEV_TAB_C, (*_g("DEV_TAB_C"), "BEND_LINE_DIMENSIONS")),
    },
    precision={"radius": FORMED_PLACES, "end_x": FORMED_PLACES},
)
requirement(
    "far_face",
    kind="face",
    faces=(
        PlanarFace(_FAR_N, FAR_FACE_POINT[0] * ARM_U[0] + FAR_FACE_POINT[1] * ARM_U[1]),
    ),
    requirements=("x", "y"),
    fields={
        "x": _formed(-FAR_FACE_POINT[0], "FaceX", "FAR_FACE_POINT"),
        "x_nominal": (-FAR_FACE_POINT[0], ("FAR_FACE_POINT",)),
        "x_from": ("ear_face", (_keep("FaceX"),)),
        "y": _formed(-FAR_FACE_POINT[1], "FaceY", "FAR_FACE_POINT"),
        "y_nominal": (-FAR_FACE_POINT[1], ("FAR_FACE_POINT",)),
        "y_from": ("low_edge", (_keep("FaceY"),)),
        "straight_length": (
            math.dist(OUTER_ROLL_END, OUTER_TAB_START),
            (*_g("OUTER_ROLL_END", "OUTER_TAB_START"), "REFERENCE_DIMENSIONS"),
        ),
    },
    precision={"x": FORMED_PLACES, "y": FORMED_PLACES},
)
requirement(
    "screw_holes",
    kind="hole",
    faces=(CylinderFace(SCREW_HOLE_DIA, contains_z_mm=SHEET_T / 2.0),),
    requirements=("dia", "x_near", "x_far", "y", "thru"),
    fields={
        "at": (
            [SCREW_HOLE_X[1], SCREW_HOLE_Y, 0.0],
            _g("SCREW_HOLE_X", "SCREW_HOLE_Y"),
        ),
        "axis": ([0.0, 0.0, 1.0], _g("SHEET_T")),
        "dia": (
            drilled_limits(SCREW_HOLE_DIA, _P["ScrewDia"], unit=UNIT),
            (*_g("SCREW_HOLE_DIA"), "DRAWING_PRECISION_BY_NAME", "UNIT"),
        ),
        "dia_nominal": (SCREW_HOLE_DIA, _g("SCREW_HOLE_DIA")),
        "x_near": _row(-SCREW_HOLE_X[1], "ScrewX2", *_g("SCREW_HOLE_X")),
        "x_near_nominal": (-SCREW_HOLE_X[1], _g("SCREW_HOLE_X")),
        "x_far": _row(-SCREW_HOLE_X[0], "ScrewX1", *_g("SCREW_HOLE_X")),
        "x_far_nominal": (-SCREW_HOLE_X[0], _g("SCREW_HOLE_X")),
        "x_near_from": ("ear_face", (_keep("ScrewX2"),)),
        "y": _row(SCREW_HOLE_Y, "ScrewY", *_g("SCREW_HOLE_Y")),
        "y_nominal": (SCREW_HOLE_Y, _g("SCREW_HOLE_Y")),
        "y_from": ("low_edge", (_keep("ScrewY"),)),
        "thru": (True, ("SCREW_HOLE_CALLOUT",)),
        "process": ("drill", ("SCREW_HOLE_CALLOUT",)),
        "count": (2, ((_SELF, "CALLOUTS_ABOVE"),)),
        "callout": (SCREW_HOLE_CALLOUT, ("SCREW_HOLE_CALLOUT",)),
        "mate": (SCREW_HOLE_MATE, ("SCREW_HOLE_MATE",)),
        "wall": (SCREW_HOLE_WALL_TEXT, ("SCREW_HOLE_WALL_TEXT",)),
    },
    precision={
        "dia": _P["ScrewDia"],
        "x_near": _P["ScrewX2"],
        "x_far": _P["ScrewX1"],
        "y": _P["ScrewY"],
    },
)
requirement(
    "pin_hole",
    kind="profile",
    faces=(CylinderFace(PIN_HOLE_DIA, contains_z_mm=PIN_HOLE_ZL),),
    requirements=("dia", "note"),
    fields={
        "dia": (
            drilled_limits(PIN_HOLE_DIA, HOLE_PLACES, unit=UNIT),
            (*_g("PIN_HOLE_DIA"), "HOLE_PLACES", "UNIT", (_SELF, "PIN_NOTE_XY")),
        ),
        "dia_nominal": (PIN_HOLE_DIA, _g("PIN_HOLE_DIA")),
        "note": (PIN_NOTE, ("DRAWING_NOTES",)),
        "callout": (PIN_HOLE_CALLOUT, ("PIN_HOLE_CALLOUT",)),
    },
    precision={"dia": HOLE_PLACES},
)
requirement(
    "root_relief",
    kind="profile",
    faces=(CylinderFace(2.0 * ROOT_R),),
    requirements=("radius",),
    fields={
        "radius": _row(ROOT_R, "RootR", *_g("ROOT_R")),
        "radius_nominal": (ROOT_R, _g("ROOT_R")),
    },
    precision={"radius": _P["RootR"]},
)
requirement(
    "tip_round",
    kind="profile",
    faces=(CylinderFace(2.0 * ROUND_R),),
    requirements=("radius", "centre_station"),
    fields={
        "radius": (ROUND_R, (*_g("ROUND_R"), "ROUND_REFERENCE", (_SELF, "RIGHT_KEEP"))),
        "dimension_type": ("reference", ("ROUND_REFERENCE",)),
        "callout": (ROUND_CALLOUT, ("ROUND_CALLOUT",)),
        "centre_station": _row(
            DEV_TIP - ROUND_R, "DevRoundC", *_g("DEV_TIP", "ROUND_R")
        ),
        "centre_station_nominal": (DEV_TIP - ROUND_R, _g("DEV_TIP", "ROUND_R")),
        "centre_station_from": ("low_edge", (_keep("DevRoundC"),)),
        "overall_height": (
            OVERALL_HEIGHT,
            ("OVERALL_HEIGHT", (_SELF, "OVERALL_TEXT_XY")),
        ),
    },
    precision={"centre_station": _P["DevRoundC"]},
)
requirement(
    "arm_front",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), -_ARM_FRONT_Z),),
    requirements=("width",),
    fields={
        "plane": ({"frame": "model", "axis": "z", "value": _ARM_FRONT_Z}, _g("ARM_W")),
        "width": _row(ARM_W, "FlatArmW", *_g("ARM_W")),
        "width_nominal": (ARM_W, _g("ARM_W")),
        "width_from": ("ear_top", (_keep("FlatArmW"),)),
    },
    precision={"width": _P["FlatArmW"]},
)
requirement(
    "arm_low_front",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), -_ARM_LOW_Z),),
    requirements=("width",),
    fields={
        "plane": ({"frame": "model", "axis": "z", "value": _ARM_LOW_Z}, _g("LOW_W")),
        "width": _row(LOW_W, "FlatLowW", *_g("LOW_W")),
        "width_nominal": (LOW_W, _g("LOW_W")),
        "width_from": ("ear_top", (_keep("FlatLowW"),)),
    },
    precision={"width": _P["FlatLowW"]},
)
requirement(
    "taper",
    kind="face",
    faces=(
        PlanarFace(_TAPER_N, _TAPER_N[1] * TAPER_L[0] + _TAPER_N[2] * _ARM_FRONT_Z),
    ),
    requirements=("start", "end"),
    fields={
        "start": _row(DEV_TAPER[0], "DevTaper1", *_g("DEV_TAPER")),
        "start_nominal": (DEV_TAPER[0], _g("DEV_TAPER")),
        "end": _row(DEV_TAPER[1], "DevTaper2", *_g("DEV_TAPER")),
        "end_nominal": (DEV_TAPER[1], _g("DEV_TAPER")),
        "start_from": ("low_edge", (_keep("DevTaper1"),)),
    },
    precision={"start": _P["DevTaper1"], "end": _P["DevTaper2"]},
)


def _pin_origin(
    adapter: Any, view: Any, target: tuple[float, float], *, label: str
) -> None:
    """Move ``view`` so the part origin lands on ``target`` (sheet m), and
    read the projection back.  The view's annotations move with it."""
    view = _early_bound(view, "IView")
    at = model_point_in_view(adapter, view, (0.0, 0.0, 0.0), label=f"{label} origin")
    if math.dist(at, target) <= _PIN_TOL_M:
        return
    position = tuple(float(value) for value in view.Position)
    moved = [position[axis] + target[axis] - at[axis] for axis in range(2)]
    if not view.SetViewPosition(double_array(moved), False):
        raise RuntimeError(f"failed to move the {label} onto its sheet position")
    adapter.currentModel.EditRebuild3()
    at = model_point_in_view(adapter, view, (0.0, 0.0, 0.0), label=f"{label} origin")
    if math.dist(at, target) > _PIN_TOL_M:
        raise RuntimeError(f"{label}: part origin sits at {at!r}, not {target!r}")


def _shorten_radii(
    adapter: Any, annotations: list[Any], names: tuple[str, ...]
) -> None:
    """Foreshorten the named radius dimensions and read each one back.

    ``IDisplayDimension::ShortenedRadius`` draws the radius line toward the
    centre but stops it short of it -- the jogged radius for a centre beyond
    the sheet.  A property put that SolidWorks ignores still returns, so the
    flag is read back.
    """
    remaining = set(names)
    for annotation in annotations:
        annotation = _early_bound(annotation, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ShortenedRadius = True
        if not bool(display.ShortenedRadius):
            raise RuntimeError(f"radius {name!r} did not keep its shortened leader")
        remaining.discard(name)
    if remaining:
        raise RuntimeError(f"radii not shortened: {sorted(remaining)}")


@_telemetry.traced("drawing.latch_hook.pin_hole_note")
def _pin_hole_note(adapter: Any, right: Any) -> None:
    """The pin hole's size and note 2 on a leader to its rim on the side view.

    The rim is found by its model circle (centre, radius and axis: the far
    face's, not the near face's of the same bore) and the leader lands on
    it by entity at a projected model point, the
    draw_ch_rocker_arm_tl_vn_oblique_pivot_screw end-rim recipe: the rim is
    inclined to the view, so a sheet-point pick has no stable coordinate.
    """
    label = "latch-hook pin hole"
    rim = scan_view_edges(right, label=f"{label} rim").circle_at(
        PIN_RIM_CENTRE, PIN_HOLE_DIA / 2.0, axis=PIN_RIM_AXIS, label=f"{label} rim"
    ).edge
    landing = model_point_in_view(
        adapter,
        right,
        tuple(value / 1000.0 for value in PIN_RIM_LANDING),
        label=f"{label} rim landing",
    )
    add_attached_note(
        adapter,
        right,
        text=PIN_HOLE_NOTE,
        entity=rim,
        leader_attach_xy=landing,
        note_xy=PIN_NOTE_XY,
        label=label,
    )


def _overall_reference(adapter: Any, right: Any) -> None:
    """The (3.80) formed overall height, ear top edge to the round's tip."""
    label = "latch-hook overall height reference"
    display = add_edge_dimension(
        adapter,
        right,
        p0=OVERALL_PICKS[0],
        p1=OVERALL_PICKS[1],
        text_xy=OVERALL_TEXT_XY,
        label=label,
        orientation="vertical",
    )
    set_arc_endpoints_to_max(adapter, display, label=label)
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    measured_mm = abs(float(dimension.SystemValue) * 1000.0)
    if abs(measured_mm - OVERALL_HEIGHT) > 1e-4:
        raise RuntimeError(
            f"{label} measured {measured_mm:g}, expected {OVERALL_HEIGHT:g}"
        )
    set_reference_dimension(adapter, display.GetAnnotation(), label=label)
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != DRAWING_REFERENCE_PRECISION:
        raise RuntimeError(f"{label} precision did not persist")


@_telemetry.traced("drawing.latch_hook.view_centreline", label_param="label")
def _view_centreline(
    adapter: Any,
    view: Any,
    ends_mm: tuple[tuple[float, float, float], tuple[float, float, float]],
    *,
    label: str,
) -> None:
    """One black view-sketch centreline between two part-frame points (mm).

    The model points are projected through the view and its sketch's own
    transform, and the line is created direct-to-database so screen-space
    inference cannot snap an end onto nearby geometry (the
    draw_dt_pinion_arbor turning-axis recipe).
    """
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"failed to activate the view for the {label}")
    draw.ClearSelection2(True)
    sketch = _early_bound(_early_bound(view, "IView").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for end in ends_mm:
        x, y = model_point_in_view(
            adapter, view, tuple(value / 1000.0 for value in end), label=f"{label} end"
        )
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        segment = manager.CreateCenterLine(*points[0], *points[1])
    finally:
        manager.AddToDB = previous_add_to_db
    if segment is None:
        raise RuntimeError(f"failed to draw the {label}")
    segment = _early_bound(segment, "ISketchSegment")
    segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
    if int(segment.Color) != 0:
        raise RuntimeError(f"{label} colour did not persist")
    draw.ClearSelection2(True)
    draw.EditRebuild3()


# A model sketch shown in a view draws thin and grey (review 3: the flat
# pattern read unlike the views).  Its outline takes the visible edges'
# black and weight; its bend centrelines (construction, the chain font)
# black, thin.
FLAT_LINE_COLOR = 0  # COLORREF black, the outline's colour
_SW_LW_THICK = 2  # swLineWeights_e.swLW_THICK, the visible-edge weight
_FLAT_SEGMENTS = {False: 9, True: 3}  # outline / bend centrelines


@_telemetry.traced("drawing.latch_hook.flat_pattern_lines")
def _flat_pattern_lines(adapter: Any, right: Any) -> None:
    """Draw the flat pattern's outline as visible edges, its bend lines black."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    native = _early_bound(right, "IView")
    if not drawing.ActivateView(view_name(adapter, right)):
        raise RuntimeError("cannot activate the side view for the flat pattern")
    model = native.ReferencedDocument
    feature = (
        None
        if model is None
        else _early_bound(model, "IPartDoc").FeatureByName(FLAT_SKETCH)
    )
    if feature is None:
        raise RuntimeError(f"the side view's model has no {FLAT_SKETCH} sketch")
    sketch = _early_bound(
        _early_bound(feature, "IFeature").GetSpecificFeature2(), "ISketch"
    )
    segments = [
        _early_bound(raw, "ISketchSegment") for raw in sketch.GetSketchSegments() or ()
    ]
    selection = _early_bound(draw.SelectionManager, "ISelectionMgr")
    for construction, count in _FLAT_SEGMENTS.items():
        picked = [s for s in segments if bool(s.ConstructionGeometry) is construction]
        label = "bend centrelines" if construction else "outline"
        if len(picked) != count:
            raise RuntimeError(
                f"flat pattern {label}: {len(picked)} segments, want {count}"
            )
        draw.ClearSelection2(True)
        for index, segment in enumerate(picked):
            in_view = native.GetCorresponding(segment)
            if in_view is None:
                raise RuntimeError(f"flat pattern {label}: a segment has no instance")
            data = selection.CreateSelectData()
            data.View = right
            if not _early_bound(in_view, "ISketchSegment").Select4(index > 0, data):
                raise RuntimeError(f"cannot select the flat pattern {label}")
        if int(selection.GetSelectedObjectCount2(-1)) != count:
            raise RuntimeError(f"flat pattern {label}: the selection lost segments")
        drawing.SetLineColor(FLAT_LINE_COLOR)
        if not construction:
            drawing.SetLineWidth(_SW_LW_THICK)
        _telemetry.info(f"latch-hook: flat pattern {label} drawn black ({count})")
    draw.ClearSelection2(True)
    draw.EditRebuild3()


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open latch-hook source", adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
            "Flat Pattern Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
            "Flat Pattern Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Latch Hook Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "latch hook; formed brass sheet",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    bottom = place_view(
        adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=VIEW_SCALE
    )
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, right, bottom, iso):
        set_hidden_lines_removed(adapter, view)
    for view, origin, label in (
        (front, FRONT_ORIGIN, "front view"),
        (right, RIGHT_ORIGIN, "side view"),
        (bottom, BOTTOM_ORIGIN, "bottom view"),
    ):
        _pin_origin(adapter, view, origin, label=label)

    annotations = [
        *curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="front",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            right,
            keep=RIGHT_KEEP,
            view_label="side",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            bottom,
            keep=BOTTOM_KEEP,
            view_label="bottom",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    # Showing the FlatBlank sketch may grow the side view's box; put its
    # origin back (its dimensions travel with it).
    _pin_origin(adapter, right, RIGHT_ORIGIN, label="side view with flat pattern")
    _flat_pattern_lines(adapter, right)
    # Places (and so each dimension's title-block row) and every band are
    # authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    set_dimension_callouts(adapter, annotations, CALLOUTS_BELOW)
    _shorten_radii(adapter, annotations, SHORTENED_RADII)
    # The straight's length (the developed length already fixes it), the
    # flat pattern's bend centrelines and the full round's radius (the .45
    # width sets it) print as references.
    by_name = {dimension_name(adapter, a): a for a in annotations}
    references = REFERENCE_DIMENSIONS | BEND_LINE_DIMENSIONS | {ROUND_REFERENCE}
    for name in sorted(references):
        set_reference_dimension(adapter, by_name[name], label=f"MHA-PD-14 {name}")
    _overall_reference(adapter, right)
    _pin_hole_note(adapter, right)
    # The far face's station ends on the pin's axis and the flat pattern's
    # round stations on the round's centre: both drawn, so neither location
    # dimension carries words (rule 7).
    _view_centreline(adapter, front, PIN_AXIS_ENDS, label="latch-pin axis")
    for index, ends in enumerate(FLAT_ROUND_MARK_ENDS):
        _view_centreline(
            adapter, right, ends, label=f"flat full-round centre mark {index}"
        )
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the screw holes")
    # Re-asserted after annotating: the toggle regenerates the dashed edges,
    # and the edge-on pin hole's would read as a feature to dimension.
    set_hidden_lines_removed(adapter, front)
    for name, xy in (
        ("Manufacturing Notes", NOTES_XY),
        ("Isometric View Note", ISO_NOTE_XY),
        ("Flat Pattern Note", FLAT_NOTE_XY),
    ):
        add_property_linked_note(adapter, name, *xy, char_height=NOTE_HEIGHT)

    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Latch Hook Manufacturing Drawing",
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
