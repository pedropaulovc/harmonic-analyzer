r"""Create the four-sheet pen fitter package (MHA-PN-00).

Sheet 1 shows the pen assembled (front and right) beside four details, three
of which carry its settings as the builder's driving, toleranced model
dimensions: DETAIL A the stud height and its jam nut (``StudSetting``),
DETAIL B the hanger screw's nut and jam nut, DETAIL C the pen yaw and nib
preset (``CarriageSetting``), DETAIL D the stirrup and its thumb screw on the
block, with the as-shipped note; sheet 2 the builder-owned ``PN_EXPLODED``
presentation (``pn_pen_explode_spec``) with its explode trails, the BOM
(numbers, descriptions, vendor SKU, quantity) and a balloon on every row;
sheet 3 the finished isometric beside the numbered bench steps; sheet 4 the
at-machine steps and the checks. Every setting and pose comes from
``pn_pen_assembly_spec``, every printed text and detail region from
``pn_pen_assembly_sheet``, the rest from the part registry; this recipe only
lays the sheets out. It never edits the source assembly or its explodes.
"""

from __future__ import annotations

import argparse
import math
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import _config
import _mcmaster_99607a213 as thumb_screw
import _telemetry
import pn_pen_adjust_screw_spec as stud
import pn_pen_assembly_sheet as notes
import pn_pen_assembly_spec as spec
import pn_pen_carriage_geom as carriage
import pn_pen_explode_spec as explode
import pn_pen_frame_spec as frame
import pn_pen_hanger_spec as hanger
import pn_pen_rod_spec as rod
import pn_pen_v_block_spec as v_block
import pn_vn_pen_marker_spec as marker
import sh_vn_music_wire_pen_geom as wire
from _check import check
from _com import _early_bound
from _component_references import component_identity, component_reference_names
from _session import run_build
from _drawing_balloons import (
    BalloonAnchor,
    add_component_bom_balloons,
    assert_balloon_landings,
    isolate_drawing_view_components,
)
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_high_quality_shaded_with_edges,
)
from _drawing_detail_crop import _transform_point, native_circle_geometry
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_hidden_sketches import _show_base_view_sketches
from _drawing_leader_notes import add_leader_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME, DrawingLayout
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_tables import (
    bom_row_identities,
    insert_bom_table,
    validate_bom_number_property,
)
from _drawing_view_configuration import (
    ASSEMBLY_VIEW_CONFIGURATION,
    SIMPLIFIED_VIEW_CONFIGURATION,
    ViewRole,
    apply_view_configuration,
    assert_full_detail_view,
    set_view_exploded_state,
)
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    dimension_name,
    place_view,
    view_name,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE
SPEC = DRAWINGS_BY_NAME["pn_pen_assembly"]
ARTIFACT_STEM = SPEC.artifact_stem
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png
PDF_TITLE = "Pen Assembly Drawing Package"

SHEET_NAMES = (
    "ASSEMBLED VIEWS + SETTINGS",
    "EXPLODED VIEW + BOM",
    "ASSEMBLY STEPS",
    "ASSEMBLY STEPS CONTINUED",
)
if SPEC.layout is not DrawingLayout.LANDSCAPE:
    raise AssertionError("the pen package sheets are landscape")
SHEET_LAYOUTS = {name: DrawingLayout.LANDSCAPE for name in SHEET_NAMES}
SHEET_SCALE = (1.0, 2.0)
SHEET_SCALES = {name: SHEET_SCALE for name in SHEET_NAMES}

# Sheet geometry, metres: the template's inner border and the title block in
# its lower-right corner. Every view outline, balloon ring, dimension and note
# stays inside the border and out of the title block (drawing-guidelines.md
# rule 13 (stay inside the border)).
_TEMPLATE = DRAWING_TEMPLATES[DrawingLayout.LANDSCAPE]
SHEET_INNER_BORDER = (
    0.0127,
    0.0127,
    _TEMPLATE.width_m - 0.0127,
    _TEMPLATE.height_m - 0.0127,
)
TITLE_BLOCK = (
    _TEMPLATE.title_block_left_m,
    0.0,
    _TEMPLATE.width_m,
    _TEMPLATE.title_block_top_m,
)
# Default-format note text measured on the ms package (farm run
# 20261015T235155114Z): 2.55 mm per character, 4.53 mm per line.
NOTE_GAP = 0.006
VIEW_LABEL_GAP = 0.004

# --- sheet 1: assembled views and the three settings details -------------------
# The pen at 1:2: front and right side by side down the left, labels under
# them; DETAIL C (the carriage plan at 2:1, turned marker-axis across) under
# them; DETAILs A and B at 2:1 across the top right with the as-shipped note
# under them.
FRONT_CENTER = (0.050, 0.192)
RIGHT_CENTER = (0.125, 0.192)
SETTINGS_NOTE_XY = (0.225, 0.150)
SETTINGS_NOTE_WIDTH = 70  # characters
CROP_NO_ERROR = 1  # swCropViewErrors_e.swCropViewErrors_NoError
DETAIL_POSITION_TOL_M = 1e-4
DETAIL_LETTER_GAP = 0.001
# One default-format glyph's width (the measured 2.55 mm per character
# above): where C's arrow letter starts left of its tip before it is squared.
DETAIL_LETTER_WIDTH = 0.00255
BOUNDARY_COLOR = 0  # COLORREF black, the outline's colour.
# Each circled detail's parent view, by the orientation the detail shares with
# it. A and B are bounded on RIGHT, where the stud and the hanger screw both
# show (on FRONT the strap hides the stud); D on FRONT, which it enlarges.
# D's letter stands at its circle's upper left: the marker's grip block fills
# the upper right on FRONT.
BOUNDED_ON = {"stud": "*Right", "hanger": "*Right", "stirrup": "*Front"}
LETTERED_LEFT = frozenset(("stirrup",))
# C, the turned plan, is named by a viewing arrow on FRONT instead
# (draw_sm_summing_lever's VIEW F arrow): the letter's top stands this far over
# the tip, the leader leaving the letter's side squared over the tip.
VIEW_ARROW_RISE = 0.010
VIEW_ARROW_SQUARE_TOL = 0.0003
# The arrow's tip stands at least this far off D's circle, so it reads as
# pointing at the block, not at the circle.
VIEW_ARROW_CIRCLE_CLEARANCE = 0.002
TRAIL_LINE_STYLE = 2  # swLineStyles_e.swLinePHANTOM: the explode trail

_CARRIAGE_STEMS = frozenset(notes.CARRIAGE_STEMS)


@dataclass(frozen=True)
class Detail:
    """One isolated, circle-cropped model view of a setting or a lock.

    ``model_centre`` (machine mm) lands on the sheet at ``centre``; the crop
    circle reaches ``radius_mm`` model millimetres round it. ``feature`` is the
    builder's settings sketch whose marked dimensions the detail prints
    (``None``: a lock shown, nothing dimensioned). ``axis_points`` (machine mm,
    from, to), when given, is the direction the view is turned to lay along
    sheet +X, clockwise by ``turn_cw_deg`` (the angle its title prints)."""

    key: str
    orientation: str
    scale: tuple[int, int]
    model_centre: tuple[float, float, float]
    radius_mm: float
    centre: tuple[float, float]
    stems: frozenset[str]
    feature: str | None
    label_xy: tuple[float, float]
    axis_points: (
        tuple[tuple[float, float, float], tuple[float, float, float]] | None
    ) = None
    turn_cw_deg: float | None = None

    @property
    def title(self) -> str:
        return notes.SHEET_TITLES[self.key]

    @property
    def label(self) -> str:
        return f"pen {self.key} detail"

    @property
    def mm(self) -> float:
        """Sheet metres per model millimetre."""
        return self.scale[0] / self.scale[1] / 1000.0

    @property
    def crop_radius(self) -> float:
        return self.radius_mm * self.mm

    @property
    def model_centre_m(self) -> tuple[float, float, float]:
        return tuple(value / 1000.0 for value in self.model_centre)


STUD_DETAIL = Detail(
    key="stud",
    orientation="*Right",
    scale=(2, 1),
    model_centre=notes.STUD_DETAIL_CENTRE,
    radius_mm=notes.STUD_DETAIL_RADIUS,
    centre=(0.262, 0.214),
    stems=frozenset((spec.ROD, spec.STUD, spec.STUD_NUT, spec.WIRE)),
    feature=spec.STUD_FEATURE,
    label_xy=(0.246, 0.180),
)
HANGER_DETAIL = Detail(
    key="hanger",
    orientation="*Right",
    scale=(2, 1),
    model_centre=notes.HANGER_DETAIL_CENTRE,
    radius_mm=notes.HANGER_DETAIL_RADIUS,
    centre=(0.362, 0.214),
    stems=frozenset(
        (spec.HANGER, spec.HANGER_SCREW, spec.HANGER_NUT, spec.HANGER_JAM_NUT)
    ),
    feature=None,
    label_xy=(0.346, 0.174),
)
CARRIAGE_DETAIL = Detail(
    key="carriage",
    orientation="*Top",
    scale=(2, 1),
    model_centre=notes.CARRIAGE_DETAIL_CENTRE,
    radius_mm=notes.CARRIAGE_DETAIL_RADIUS,
    centre=(0.110, 0.058),
    stems=_CARRIAGE_STEMS,
    feature=spec.CARRIAGE_FEATURE,
    label_xy=(0.156, 0.090),
    axis_points=notes.CARRIAGE_AXIS_POINTS,
    turn_cw_deg=notes.CARRIAGE_TURN_CW_DEG,
)
# D sits in the free band right of C's title, between the as-shipped note
# and the title block, its title to its right.
STIRRUP_DETAIL = Detail(
    key="stirrup",
    orientation="*Front",
    scale=(1, 1),
    model_centre=notes.STIRRUP_DETAIL_CENTRE,
    radius_mm=notes.STIRRUP_DETAIL_RADIUS,
    centre=(0.262, 0.099),
    stems=_CARRIAGE_STEMS,
    feature=None,
    label_xy=(0.294, 0.113),
)
DETAILS = (STUD_DETAIL, HANGER_DETAIL, CARRIAGE_DETAIL, STIRRUP_DETAIL)


def _top_plan_point(uv: tuple[float, float]) -> tuple[float, float, float]:
    """A Top-plane sketch point (u, v) = machine (X, -Z) as machine mm; the
    plan view projects Y away."""
    return (uv[0], notes.CARRIAGE_DETAIL_CENTRE[1], -uv[1])


# Each kept dimension's text point, machine mm, projected into its detail.
DIMENSION_TEXT_POINTS = {
    STUD_DETAIL.key: {
        spec.STUD_DIMENSION: notes.STUD_TEXT_POINT,
    },
    CARRIAGE_DETAIL.key: {
        spec.YAW_DIMENSION: _top_plan_point(spec.YAW_TEXT_UV),
        spec.NIB_DIMENSION: _top_plan_point(notes.NIB_TEXT_UV),
    },
}
# Every callout is two lines, which only the below compartment prints.
CALLOUT_LOCATION = "below"
CALLOUT_TEXT_PART = 4  # swDimensionTextParts_e: swDimensionTextCalloutBelow
if set(notes.DIMENSION_CALLOUTS) != {
    name for names in spec.DRAWING_DIMENSIONS.values() for name in names
}:
    raise AssertionError("every pen setting carries its callout")

# --- sheet 2: the exploded isometric, BOM and balloons ---------------------------
BOM_COLUMN_WIDTHS = {
    "item": 0.012,
    "part": 0.030,
    "description": 0.086,
    "sku": 0.028,
    "quantity": 0.012,
}
BOM_SKU_TITLE = "VENDOR SKU"
MADE_PART_SKU = "-"
BOM_ROW_HEIGHT = 0.006
BOM_ANCHOR = (
    SHEET_INNER_BORDER[2] - sum(BOM_COLUMN_WIDTHS.values()) - 0.003,
    SHEET_INNER_BORDER[3] - 0.004,
)
BALLOON_MARGIN = 0.012
# The exploded outline plus its balloon ring keeps left of the BOM.
EXPLODED_RIGHT_LIMIT = BOM_ANCHOR[0] - 0.006
EXPLODED_ISO_CENTER = (
    (SHEET_INNER_BORDER[0] + EXPLODED_RIGHT_LIMIT) / 2.0,
    (SHEET_INNER_BORDER[1] + SHEET_INNER_BORDER[3]) / 2.0,
)
# Largest first: the sheet scale, then smaller only if the ring overflows.
EXPLODED_SCALES = ((1.0, 2.0), (2.0, 5.0), (1.0, 3.0))

WIRE_ROW = f"sh-vn-music-wire--{wire.CONFIGURATION}"
BOM_ROW_KEYS = {stem: WIRE_ROW if stem == spec.WIRE else stem for stem in spec.BOM_ORDER}
BOM_QUANTITIES = {BOM_ROW_KEYS[stem]: spec.QUANTITIES[stem] for stem in spec.BOM_ORDER}
BOM_COMPONENT_IDENTITIES = {
    BOM_ROW_KEYS[stem]: (stem, wire.CONFIGURATION if stem == spec.WIRE else None)
    for stem in spec.BOM_ORDER
}
BOM_COMPONENTS = tuple(BOM_QUANTITIES)
# Literal stems, so the config-dependency analysis reads exactly these rows.
PART_ROWS = {
    "pn-pen-hanger": _config.parts("pn-pen-hanger"),
    "pn-pen-rod": _config.parts("pn-pen-rod"),
    "pn-pen-v-block": _config.parts("pn-pen-v-block"),
    "pn-vn-pen-marker": _config.parts("pn-vn-pen-marker"),
    "pn-pen-frame": _config.parts("pn-pen-frame"),
    "pn-vn-pen-set-screw": _config.parts("pn-vn-pen-set-screw"),
    "pn-vn-pen-rod-set-screw": _config.parts("pn-vn-pen-rod-set-screw"),
    "pn-pen-adjust-screw": _config.parts("pn-pen-adjust-screw"),
    "pn-vn-pen-adjust-nut": _config.parts("pn-vn-pen-adjust-nut"),
    WIRE_ROW: _config.parts("sh-vn-music-wire"),
    "pn-vn-hanger-screw": _config.parts("pn-vn-hanger-screw"),
    "pn-vn-pen-hanger-nut": _config.parts("pn-vn-pen-hanger-nut"),
    "pn-vn-pen-hanger-jam-nut": _config.parts("pn-vn-pen-hanger-jam-nut"),
}
if set(PART_ROWS) != set(BOM_COMPONENTS):
    raise AssertionError("BOM registry rows must cover exactly the pen families")
BOM_PART_NUMBERS = {stem: str(row["number"]) for stem, row in PART_ROWS.items()}
# The registry owns part numbers and vendor SKU; components own material/finish.
BOM_SKUS = {
    stem: " / ".join(str(sku) for sku in row.get("supplier_skus") or ())
    or MADE_PART_SKU
    for stem, row in PART_ROWS.items()
}
BOM_DESCRIPTIONS = {BOM_ROW_KEYS[stem]: text for stem, text in notes.BOM_DESCRIPTIONS.items()}
BOM_IDENTITY_ALIASES = {number: stem for stem, number in BOM_PART_NUMBERS.items()}
# Every family is one separated body on the exploded view: each balloon walks
# its own part for a visible edge, except the families pinned below. Each pin
# is a point on a drawn edge in part millimetres, derived from the view's own
# axes (spec.EXPLODED_VIEW_AXES), so the side it takes follows the camera.
#
# * The stud's and the rod's, off the stack the stud, its jam nut and the
#   rod's top make: there three walked attachments sat within 2 mm of one sheet
#   bearing at different radii, so leaders 2/9 and 8/9 crossed (farm run
#   20261016T061511876Z). The stud's takes the sheet-rightmost point of its
#   head's top edge (revolved about +Y, placed unrotated).
# * The rod's takes the sheet-right vertical corner of its square (part mm:
#   square x, z +-S/2, y up from the shoulder; placed unrotated), a
#   silhouette, ROD_ANCHOR_Y up. The rod stands just right of the view centre
#   with the v-block under it, the stirrup down-right and the hanger right, so
#   its radial leader clears all three only in a band of the square: low, it
#   ran down across the v-block (machinist review, farm run
#   20261023T222629630Z); at 55 it crosses the stirrup, at 70 the hanger's
#   lower U guide. At 63 it runs down-right between them, ~6 mm off each.
# * The wire's takes the sheet-leftmost point of its top end (extruded up +Y
#   from the origin, unrotated): walked, it took the end by the strap's corner
#   and its leader crossed the strap and the hanger screw (machinist review
#   r3).
# * The hanger's takes the strap's sheet-rightmost long edge at mid-length
#   (part mm: Front-plane outline, top edge y 0, extruded from the bar seat z 0
#   to -T; placed unrotated): walked, it took the strap's top corner, its
#   leader ran along screw 11's shank and landed beside balloon 11's arrow
#   (machinist gate 2026-10-17). With sheet-right running -x and +z, that edge
#   is the strap's -x side on its bar-seat face: a silhouette, clear of the
#   screw, nuts and U guides.
# * The stirrup's and the thumb screw's: walked, both landed side by side on
#   the stirrup's bottom rail, balloon 5's leader through the thumb screw's
#   knob (machinist review, farm run 20261023T222629630Z). The stirrup's takes
#   its sheet-right outer vertical edge, a silhouette, three quarters up; the
#   thumb screw's the knob's top rim (the inner edge of the vendor model's
#   HeadDia/16 head chamfer on the face the collar rises from,
#   diagnostics/diag_build_99607A213), on the side facing the reader's lower
#   right.
# * The v-block's and the marker's: walked, the block took its far-end bottom
#   corner and the marker its nib, both straight above the rod set screw in
#   this view, so their leaders ran down past it. The block's takes its front
#   face's bottom edge under the tap; the marker's the edge round its back end
#   (its last taper station before the dome), nearest the reader.
_RIGHT, _UP, _TOWARD = spec.EXPLODED_VIEW_AXES
if abs(_RIGHT[1]) > 1e-12:
    raise AssertionError("the exploded view keeps model +Y up the sheet")
if not _RIGHT[0] < 0.0 < _RIGHT[2]:
    raise AssertionError("the hanger anchor assumes sheet-right runs -x and +z")


def _dot(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _unit(vector: tuple[float, ...]) -> tuple[float, ...]:
    length = math.sqrt(_dot(vector, vector))
    return tuple(value / length for value in vector)


def _in_part(rows: Any, direction: tuple[float, ...]) -> tuple[float, ...]:
    """``direction`` (model) in the frame of a part placed with ``rows``, the
    images of its local axes."""
    return tuple(_dot(tuple(row), direction) for row in rows)


def _silhouette_corner(
    rows: Any, size: tuple[float, float], *, label: str
) -> tuple[float, float]:
    """The (local x, local z) of a box part's sheet-right vertical edge, its
    faces at x 0..size[0] and z 0..size[1]; proved a silhouette (one of its
    two faces toward the reader)."""
    right, toward = _in_part(rows, _RIGHT), _in_part(rows, _TOWARD)
    x = size[0] if right[0] > 0.0 else 0.0
    z = size[1] if right[2] > 0.0 else 0.0
    x_face_seen = math.copysign(1.0, right[0]) * toward[0] > 0.0
    z_face_seen = math.copysign(1.0, right[2]) * toward[2] > 0.0
    if x_face_seen == z_face_seen:
        raise AssertionError(
            f"{label}: the sheet-right vertical edge is not a silhouette"
        )
    return x, z


ROD_ANCHOR_Y = 63.0
_HEAD_R = stud.HEAD_DIA / 2.0
_WIRE_R = wire.WIRE_DIA / 2.0
_ROD_CORNER = (
    math.copysign(rod.ROD_SECTION / 2.0, _RIGHT[0]),
    math.copysign(rod.ROD_SECTION / 2.0, _RIGHT[2]),
)
if (_ROD_CORNER[0] * _TOWARD[0] > 0.0) == (_ROD_CORNER[1] * _TOWARD[2] > 0.0):
    raise AssertionError("the rod anchor's corner is not a silhouette")
HANGER_ANCHOR_MM = (
    (hanger.STRAP_TOP_X[0] + hanger.STRAP_BOT_X[0]) / 2.0,
    hanger.STRAP_BOT_Y / 2.0,
    hanger.STRAP_Z[1],
)
_STIRRUP_X, _STIRRUP_Z = _silhouette_corner(
    carriage.FRAME_ROWS, (frame.OUTER_WIDTH, frame.FRAME_DEPTH), label="stirrup anchor"
)
STIRRUP_ANCHOR_MM = (_STIRRUP_X, 0.75 * frame.OUTER_HEIGHT, _STIRRUP_Z)
# The thumb screw's frame: the axis along local +X from the head top (x 0) to
# the tip; the head's base face, the collar's side, at x = TS_HEAD_H.
KNOB_RIM_R = thumb_screw.TS_HEAD_R - thumb_screw.HEAD_DIA / 16.0
_KNOB_SIDE = _in_part(
    carriage.THUMB_SCREW_ROWS,
    _unit(tuple(a + b for a, b in zip(_unit((_TOWARD[0], 0.0, _TOWARD[2])), _RIGHT))),
)
if abs(_KNOB_SIDE[0]) > 1e-12:
    raise AssertionError("the thumb screw stands on a vertical axis")
THUMB_SCREW_ANCHOR_MM = (
    thumb_screw.TS_HEAD_H,
    KNOB_RIM_R * _KNOB_SIDE[1],
    KNOB_RIM_R * _KNOB_SIDE[2],
)
V_BLOCK_ANCHOR_MM = (v_block.PIVOT_BORE_X, 0.0, v_block.BODY_Z0)
# The marker's frame: the axis along local +Y from the nib (y 0).
MARKER_BACK_STATION = marker.PROFILE[-4]
_MARKER_FACING = _in_part(carriage.MARKER_ROWS, _TOWARD)
_MARKER_RADIAL = _unit((_MARKER_FACING[0], _MARKER_FACING[2]))
MARKER_ANCHOR_MM = (
    MARKER_BACK_STATION[1] * _MARKER_RADIAL[0],
    MARKER_BACK_STATION[0],
    MARKER_BACK_STATION[1] * _MARKER_RADIAL[1],
)
BALLOON_ANCHORS = {
    **{stem: BalloonAnchor() for stem in BOM_COMPONENTS},
    spec.ROD: BalloonAnchor(point_mm=(_ROD_CORNER[0], ROD_ANCHOR_Y, _ROD_CORNER[1])),
    spec.STUD: BalloonAnchor(
        point_mm=(_HEAD_R * _RIGHT[0], stud.OVERALL_LENGTH, _HEAD_R * _RIGHT[2])
    ),
    WIRE_ROW: BalloonAnchor(
        instance="@PenWire:1",
        point_mm=(-_WIRE_R * _RIGHT[0], wire.WIRE_LEN, -_WIRE_R * _RIGHT[2]),
    ),
    spec.HANGER: BalloonAnchor(point_mm=HANGER_ANCHOR_MM),
    spec.FRAME: BalloonAnchor(point_mm=STIRRUP_ANCHOR_MM),
    spec.THUMB_SCREW: BalloonAnchor(point_mm=THUMB_SCREW_ANCHOR_MM),
    spec.V_BLOCK: BalloonAnchor(point_mm=V_BLOCK_ANCHOR_MM),
    spec.MARKER: BalloonAnchor(point_mm=MARKER_ANCHOR_MM),
}
EXPLODED_ORIENTATION = spec.EXPLODED_VIEW

EXPLODED_VIEW_NAMES = {
    ASSEMBLY_VIEW_CONFIGURATION: explode.exploded_view_name(ASSEMBLY_VIEW_CONFIGURATION),
    SIMPLIFIED_VIEW_CONFIGURATION: explode.exploded_view_name(
        SIMPLIFIED_VIEW_CONFIGURATION
    ),
}
if explode.SOURCE_CONFIGURATION != ASSEMBLY_VIEW_CONFIGURATION:
    raise AssertionError("the pen explode is authored in Default")

# --- sheets 3 and 4: the finished isometric beside the bench steps (sheet 3),
# then beside the at-machine steps and the checks (sheet 4) -------------------------
ASSEMBLY_ISO_CENTER = (0.062, 0.145)
# GetOutline frames the finished iso's projected bounding box, not its ink: on
# the c03368c sheets 3 and 4 the pen's ink spanned x 0.0304..0.0950, y
# 0.0955..0.1952 about ASSEMBLY_ISO_CENTER while the outline's bottom stood
# ~26 mm lower, so a label under the outline hung ~30 mm under the pen
# (machinist review c03368c).  The label stands VIEW_LABEL_GAP under the
# measured ink, left-aligned with it.
FINISHED_INK_LOWER_LEFT = (
    ASSEMBLY_ISO_CENTER[0] - 0.0316,
    ASSEMBLY_ISO_CENTER[1] - 0.0495,
)
STEPS_TOP = SHEET_INNER_BORDER[3] - 0.005
STEPS_LINE_WIDTH = 108  # characters


def _wrapped(lines: tuple[str, ...], *, width: int, heading: str | None = None) -> str:
    """Wrap each numbered line under its own number, one blank line between a
    step and whatever follows it; one note per block."""
    out = [heading] if heading else []
    after_step = False
    for line in lines:
        if after_step:
            out.append("")
        number, sep, rest = line.partition(". ")
        after_step = bool(sep and number.isdigit())
        if after_step:
            out += textwrap.wrap(
                rest,
                width=width,
                initial_indent=f"{number}. ",
                subsequent_indent=" " * (len(number) + 2),
            )
        else:
            out += textwrap.wrap(line, width=width, subsequent_indent="   ")
    return "\n".join(out)


# The spaced sequence and checks overran sheet 3 into the title block (main
# farm run 20261023T233427412Z: the checks' last line stood 31.5 mm above it,
# the 7 blank lines take 31.7 mm), so the second group heading's steps -- the
# ones done at MHA-HA-00 -- and the checks after them continue on sheet 4.
_GROUP_HEADINGS = tuple(
    index
    for index, line in enumerate(notes.ASSEMBLY_STEPS)
    if not line.partition(". ")[0].isdigit()
)
if len(_GROUP_HEADINGS) != 2 or _GROUP_HEADINGS[0] != 0:
    raise AssertionError("the pen sequence is a bench group then an at-machine group")
SETTINGS_NOTE = _wrapped((notes.SETTINGS_NOTE,), width=SETTINGS_NOTE_WIDTH)
ASSEMBLY_STEPS = _wrapped(
    notes.ASSEMBLY_STEPS[: _GROUP_HEADINGS[1]],
    width=STEPS_LINE_WIDTH,
    heading="ASSEMBLY SEQUENCE",
)
ASSEMBLY_STEPS_CONTINUED = _wrapped(
    notes.ASSEMBLY_STEPS[_GROUP_HEADINGS[1] :],
    width=STEPS_LINE_WIDTH,
    heading="ASSEMBLY SEQUENCE (CONT.)",
)
ASSEMBLY_CHECKS = _wrapped(notes.ASSEMBLY_CHECKS, width=STEPS_LINE_WIDTH)

Box = tuple[float, float, float, float]


def _activate_sheet(adapter: Any, name: str) -> Any:
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not ddoc.ActivateSheet(name):
        raise RuntimeError(f"failed to activate drawing sheet {name!r}")
    current = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    actual = str(current.GetName() or "")
    if actual != name:
        raise RuntimeError(f"active drawing sheet is {actual!r}, expected {name!r}")
    return current


def _sheet_findings(box: Box, *, right_limit: float | None = None) -> list[str]:
    """Why ``box`` (sheet metres) leaves the drawable sheet, if it does."""
    x0, y0, x1, y1 = box
    left, bottom, right, top = SHEET_INNER_BORDER
    if right_limit is not None:
        right = min(right, right_limit)
    findings = []
    if x0 < left or y0 < bottom or x1 > right or y1 > top:
        findings.append(f"leaves the drawable area {(left, bottom, right, top)}")
    tx0, ty0, tx1, ty1 = TITLE_BLOCK
    if x1 > tx0 and x0 < tx1 and y0 < ty1 and y1 > ty0:
        findings.append(f"enters the title block {TITLE_BLOCK}")
    return findings


def _assert_on_sheet(box: Box, *, label: str, right_limit: float | None = None) -> None:
    findings = _sheet_findings(box, right_limit=right_limit)
    if findings:
        raise RuntimeError(f"{label}: {box!r} " + "; ".join(findings))


def _note_box(note: Any, *, label: str) -> Box:
    """``INote.GetExtent``'s lower-left and upper-right corners, sheet metres."""
    values = tuple(float(value) for value in (note.GetExtent() or ()))
    if len(values) != 6 or not all(map(math.isfinite, values)):
        raise RuntimeError(f"{label}: invalid note extent {values!r}")
    box = (values[0], values[1], values[3], values[4])
    if box[0] >= box[2] or box[1] >= box[3]:
        raise RuntimeError(f"{label}: empty note extent {values!r}")
    return box


def _add_note_block(
    adapter: Any, sheet_name: str, text: str, xy: tuple[float, float], *, label: str
) -> Box:
    """A sheet-owned note (activate the sheet so no view owns it), proved
    printed as given and on the drawable sheet; returns its extent."""
    _activate_sheet(adapter, sheet_name)
    note = add_note(adapter, text, *xy)
    if note is None:
        raise RuntimeError(f"failed to place the pen {label}")
    note = _early_bound(note, "INote")
    printed = str(note.GetText() or "").replace("\r\n", "\n").replace("\r", "\n")
    if printed != text:
        raise RuntimeError(f"pen {label} printed as {printed!r}")
    box = _note_box(note, label=label)
    _assert_on_sheet(box, label=f"pen {label}")
    return box


def _view_outline(view: Any, *, label: str) -> Box:
    outline = tuple(float(value) for value in _early_bound(view, "IView").GetOutline())
    if len(outline) != 4 or outline[2] <= outline[0] or outline[3] <= outline[1]:
        raise RuntimeError(f"{label}: invalid view outline {outline!r}")
    return outline[0], outline[1], outline[2], outline[3]


def _grown(box: Box, margin: float) -> Box:
    return box[0] - margin, box[1] - margin, box[2] + margin, box[3] + margin


def _center_view_outline(
    adapter: Any, view: Any, center: tuple[float, float], *, label: str
) -> None:
    """Translate the view so its measured outline centres on ``center``."""
    view = _early_bound(view, "IView")
    x0, y0, x1, y1 = _view_outline(view, label=label)
    before = tuple(float(value) for value in view.Position)
    target = (
        before[0] + center[0] - (x0 + x1) / 2.0,
        before[1] + center[1] - (y0 + y1) / 2.0,
    )
    if not view.SetViewPosition(double_array(list(target)), False):
        raise RuntimeError(f"{label}: SetViewPosition refused {target!r}")
    adapter.currentModel.EditRebuild3()
    after = tuple(float(value) for value in view.Position)
    if len(after) != 2 or any(abs(a - b) > 1e-6 for a, b in zip(after, target)):
        raise RuntimeError(f"{label}: view moved to {after!r}, expected {target!r}")
    x0, y0, x1, y1 = _view_outline(view, label=label)
    if (
        abs((x0 + x1) / 2.0 - center[0]) > 1e-6
        or abs((y0 + y1) / 2.0 - center[1]) > 1e-6
    ):
        raise RuntimeError(f"{label}: measured outline did not centre at {center!r}")


def _set_view_scale(
    adapter: Any, view: Any, scale: tuple[float, float], *, label: str
) -> None:
    """Re-scale a placed drawing view and read the scale back."""
    view = _early_bound(view, "IView")
    view.ScaleRatio = double_array([float(scale[0]), float(scale[1])])
    adapter.currentModel.EditRebuild3()
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if len(ratio) != 2 or abs(ratio[0] / ratio[1] - scale[0] / scale[1]) > 1e-9:
        raise RuntimeError(f"{label}: view scale reads {ratio!r}, expected {scale!r}")


def _scale_text(scale: tuple[float, float]) -> str:
    return f"{scale[0]:g} : {scale[1]:g}"


def _activate_view(adapter: Any, view: Any, *, label: str) -> str:
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate the {label} {name!r}")
    adapter.currentModel.ClearSelection2(True)
    return name


def _view_note(
    adapter: Any, view: Any, text: str, xy: tuple[float, float], *, label: str
) -> tuple[Any, Box]:
    """A view-owned note at ``xy`` and its measured box, proved on the
    drawable sheet."""
    _activate_view(adapter, view, label=label)
    note = add_note(adapter, text, *xy)
    if note is None:
        raise RuntimeError(f"failed to label the {label}")
    note = _early_bound(note, "INote")
    box = _note_box(note, label=label)
    _assert_on_sheet(box, label=f"{label} label")
    return note, box


def _label_view(
    adapter: Any, view: Any, text: str, xy: tuple[float, float], *, label: str
) -> Box:
    """A view-owned label note at ``xy``, proved on the drawable sheet."""
    return _view_note(adapter, view, text, xy, label=label)[1]


def _move_note(
    adapter: Any, note: Any, delta: tuple[float, float], *, label: str
) -> Box:
    """Translate ``note`` by ``delta`` (sheet metres) and return its re-read
    box, proved on the drawable sheet."""
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    x, y, z = (float(value) for value in annotation.GetPosition())
    if not annotation.SetPosition2(x + delta[0], y + delta[1], z):
        raise RuntimeError(f"failed to move the {label}")
    adapter.currentModel.EditRebuild3()
    box = _note_box(note, label=label)
    _assert_on_sheet(box, label=f"{label} label")
    return box


def _component_stem(component: Any) -> str:
    component = _early_bound(component, "IComponent2")
    path = str(component.GetPathName() or "")
    if not path:
        raise RuntimeError(f"component {component.Name2!r} has no referenced path")
    return Path(path).stem.casefold()


def _validate_source(source_model: Any) -> None:
    """The builder-owned explodes exist, and the source opens collapsed with
    exactly the contracted families."""
    assembly = _early_bound(source_model, "IAssemblyDoc")
    manager = _early_bound(source_model.ConfigurationManager, "IConfigurationManager")
    configuration = _early_bound(manager.ActiveConfiguration, "IConfiguration")
    if str(configuration.Name) != ASSEMBLY_VIEW_CONFIGURATION:
        raise RuntimeError("pen source must open in its Default configuration")
    for owner, wanted in EXPLODED_VIEW_NAMES.items():
        names = tuple(assembly.GetExplodedViewNames2(owner) or ())
        if names != (wanted,):
            raise RuntimeError(f"pen {owner} exploded views {names!r} != {(wanted,)!r}")
    component_reference_names(
        source_model, {"@PenWire:1": (spec.WIRE, wire.CONFIGURATION)}
    )
    counts: dict[str, int] = {}
    for raw in tuple(assembly.GetComponents(True) or ()):
        component = _early_bound(raw, "IComponent2")
        stem = _component_stem(component)
        if stem == spec.WIRE:
            selected = component_identity(component)
            expected = (spec.WIRE, wire.CONFIGURATION)
            if selected != expected:
                raise RuntimeError(f"pen wire member {selected!r} != {expected!r}")
        row_key = BOM_ROW_KEYS.get(stem, stem)
        counts[row_key] = counts.get(row_key, 0) + 1
        total = _early_bound(component.GetTotalTransform(True), "IMathTransform")
        base = _early_bound(component.GetTotalTransform(False), "IMathTransform")
        if any(
            abs(float(actual) - float(expected)) > 1e-9
            for actual, expected in zip(total.ArrayData, base.ArrayData, strict=True)
        ):
            raise RuntimeError(
                f"pen source must open collapsed: {component.Name2!r} is displaced"
            )
    if counts != BOM_QUANTITIES:
        raise RuntimeError(f"pen families {counts!r} != contract {BOM_QUANTITIES!r}")


# --- sheet 1 ----------------------------------------------------------------------


def _placed_base_view(
    adapter: Any,
    orientation: str,
    center: tuple[float, float],
    title: str,
    *,
    label: str,
) -> Any:
    view = place_view(adapter, str(SOURCE), orientation, *center, scale=SHEET_SCALE)
    set_hidden_lines_removed(adapter, view)
    apply_view_configuration(adapter, view, role=ViewRole.PLAIN, label=label)
    _center_view_outline(adapter, view, center, label=label)
    x0, y0, x1, _y1 = _view_outline(view, label=label)
    _assert_on_sheet((x0, y0, x1, _y1), label=label)
    _label_view(adapter, view, title, (x0, y0 - VIEW_LABEL_GAP), label=label)
    return view


def _turn_detail(adapter: Any, view: Any, detail: Detail) -> None:
    """Turn ``view`` so ``detail.axis_points`` read along sheet +X, and prove
    it (the dt_crank_drive_gear A-A turn: ``IView.Angle`` less the axis's
    sheet angle). The axis's untouched sheet angle is the clockwise turn the
    title prints, so it must read ``detail.turn_cw_deg``."""
    native = _early_bound(view, "IView")
    label = f"{detail.label} axis"

    def axis() -> tuple[float, float]:
        start, end = (
            model_point_in_view(
                adapter,
                native,
                tuple(value / 1000.0 for value in point),
                label=label,
            )
            for point in detail.axis_points or ()
        )
        return end[0] - start[0], end[1] - start[1]

    dx, dy = axis()
    untouched = math.degrees(math.atan2(dy, dx))
    if detail.turn_cw_deg is None or abs(untouched - detail.turn_cw_deg) > 1e-3:
        raise RuntimeError(
            f"{label} reads {untouched!r} deg before the turn; its title prints "
            f"ROTATED {detail.turn_cw_deg!r} DEG CW"
        )
    native.Angle = float(native.Angle) - math.atan2(dy, dx)
    adapter.currentModel.EditRebuild3()
    dx, dy = axis()
    if dx <= 0.0 or abs(dy) > 1e-8:
        raise RuntimeError(f"{label} did not turn across: ({dx!r}, {dy!r})")
    _telemetry.info(f"{label}: turned to {math.degrees(float(native.Angle)):.3f} deg")


def _placed_detail(adapter: Any, detail: Detail) -> Any:
    """``detail`` uncropped and isolated: its orientation at its scale, moved
    so ``detail.model_centre`` lands on ``detail.centre``."""
    view = _early_bound(
        place_view(
            adapter, str(SOURCE), detail.orientation, *detail.centre, scale=detail.scale
        ),
        "IView",
    )
    set_hidden_lines_removed(adapter, view)
    apply_view_configuration(adapter, view, role=ViewRole.PLAIN, label=detail.label)
    if detail.axis_points is not None:
        _turn_detail(adapter, view, detail)
    label = f"{detail.label} centre"
    centre = model_point_in_view(adapter, view, detail.model_centre_m, label=label)
    position = tuple(float(value) for value in view.Position)
    target = [position[axis] + detail.centre[axis] - centre[axis] for axis in range(2)]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError(f"failed to move the {detail.label} onto its spot")
    adapter.currentModel.EditRebuild3()
    centre = model_point_in_view(adapter, view, detail.model_centre_m, label=label)
    if max(abs(a - b) for a, b in zip(centre, detail.centre)) > DETAIL_POSITION_TOL_M:
        raise RuntimeError(
            f"{detail.label} centre sits at {centre!r}, not {detail.centre!r}"
        )
    isolate_drawing_view_components(
        adapter, view, visible_stems=detail.stems, label=detail.label
    )
    return view


def _sketch_in_view(
    adapter: Any,
    view: Any,
    sheet_points: tuple[tuple[float, float], tuple[float, float]],
    kind: str,
    *,
    label: str,
    exact: bool = False,
) -> Any:
    """A ``kind`` ("circle": centre, rim point; "line": ends) at two sheet
    points (metres) in ``view``'s own sketch, left selected.

    ``exact`` authors straight to the sketch database (``AddToDB``), so no
    screen-space inference snaps a point onto the view's edges, and selects
    the segment explicitly (draw_ms_stick's exact fence): with inference the
    stud boundary's centre snapped 0.43 mm off its request, the rim point
    kept (farm run 20261028T061224266Z)."""
    view = _early_bound(view, "IView")
    _activate_view(adapter, view, label=label)
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in sheet_points:
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(adapter.currentModel.SketchManager, "ISketchManager")
    create = {"circle": manager.CreateCircle, "line": manager.CreateLine}[kind]
    previous = bool(manager.AddToDB)
    manager.AddToDB = exact
    try:
        segment = create(*points[0], *points[1])
    finally:
        manager.AddToDB = previous
    if segment is None:
        raise RuntimeError(f"failed to sketch the {label} {kind}")
    if exact:
        adapter.currentModel.ClearSelection2(True)
        selection = _early_bound(adapter.currentModel.SelectionManager, "ISelectionMgr")
        data = _early_bound(selection.CreateSelectData(), "ISelectData")
        data.View = view
        if _early_bound(segment, "ISketchSegment").Select4(False, data) is not True:
            raise RuntimeError(f"failed to select the {label} {kind}")
    return segment


def _sketch_view_circle(
    adapter: Any,
    view: Any,
    centre: tuple[float, float],
    radius: float,
    *,
    label: str,
    exact: bool = False,
) -> Any:
    """A circle (sheet metres) in ``view``'s own sketch, left selected; the
    sketch segment."""
    return _sketch_in_view(
        adapter,
        view,
        (centre, (centre[0] + radius, centre[1])),
        "circle",
        label=label,
        exact=exact,
    )


def _view_circle_on_sheet(
    adapter: Any, circle: Any, *, label: str
) -> tuple[tuple[float, float], float]:
    """A view-sketch circle as SolidWorks holds it: its sheet centre and
    radius, read back through the sketch's inverse transform (the
    _drawing_detail_crop sketch -> parent sheet hop)."""
    centre, radius = native_circle_geometry(circle, label=label)
    sketch = _early_bound(_early_bound(circle, "ISketchSegment").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    inverse = _early_bound(transform.Inverse(), "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    sheet_centre, rim = (
        _transform_point(utility, xyz, inverse, label=label)[:2]
        for xyz in (centre, (centre[0] + radius, centre[1], centre[2]))
    )
    return sheet_centre, math.dist(sheet_centre, rim)


def _add_explode_trail(
    adapter: Any,
    view: Any,
    trail: tuple[tuple[float, ...], tuple[float, ...]],
    *,
    label: str,
) -> None:
    """A black phantom line on the exploded ``view`` between two exploded
    model points (machine mm), read back as styled."""
    ends = tuple(
        model_point_in_view(
            adapter, view, tuple(value / 1000.0 for value in point), label=label
        )
        for point in trail
    )
    segment = _early_bound(
        _sketch_in_view(adapter, view, ends, "line", label=label), "ISketchSegment"
    )
    segment.Style = TRAIL_LINE_STYLE
    segment.Color = BOUNDARY_COLOR
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()
    style, color = int(segment.Style), int(segment.Color)
    if (style, color) != (TRAIL_LINE_STYLE, BOUNDARY_COLOR):
        raise RuntimeError(f"{label}: trail reads style {style}, colour {color}")
    _telemetry.info(f"{label}: {ends[0]!r} -> {ends[1]!r}")


def _mark_detail_boundary(
    adapter: Any, parent: Any, detail: Detail
) -> tuple[tuple[float, float], float]:
    """The detail's boundary on its parent view: a black circle round what
    the detail shows, lettered at its upper right, or its upper left for
    ``LETTERED_LEFT`` (machinist review, farm run 20261016T082735510Z: the
    fitter could not tell where A and B come from; run 20261024T091056564Z:
    nor D). Returns the circle's sheet centre and radius as read back."""
    label = f"{detail.label} boundary"
    requested = model_point_in_view(adapter, parent, detail.model_centre_m, label=label)
    radius = detail.radius_mm * SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0
    circle = _sketch_view_circle(
        adapter, parent, requested, radius, label=label, exact=True
    )
    # A view-sketch circle prints in the sketch's grey (farm run
    # 20261016T092607223Z); colour the selected circle as the outline.
    selection = _early_bound(adapter.currentModel.SelectionManager, "ISelectionMgr")
    if int(selection.GetSelectedObjectCount2(-1)) != 1:
        raise RuntimeError(f"{label}: the sketched circle is not the one selection")
    _early_bound(adapter.currentModel, "IDrawingDoc").SetLineColor(BOUNDARY_COLOR)
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()
    centre, drawn = _view_circle_on_sheet(adapter, circle, label=label)
    if (
        math.dist(centre, requested) > DETAIL_POSITION_TOL_M
        or abs(drawn - radius) > DETAIL_POSITION_TOL_M
    ):
        raise RuntimeError(
            f"{label}: circle reads centre {centre!r} radius {drawn!r}, "
            f"requested {requested!r} radius {radius!r}"
        )
    radius = drawn
    letter = notes.DETAIL_LETTERS[detail.key]
    if detail.key not in LETTERED_LEFT:
        reach = radius * math.sqrt(0.5) + DETAIL_LETTER_GAP
        _label_view(
            adapter, parent, letter, (centre[0] + reach, centre[1] + reach), label=label
        )
        return centre, radius
    # Upper left, the letter's measured box is moved so its lower-right corner
    # sits on the circle's upper-left 45 degree ray, DETAIL_LETTER_GAP outside
    # the rim; the whole box then lies up and left of that corner, clear of the
    # circle. Placing it by an assumed glyph size left the corner 0.4 mm inside
    # the gap once the glyph read 3.4 x 4.7 mm (rolling main 6d7f35476).
    clear = (radius + DETAIL_LETTER_GAP) * math.sqrt(0.5)
    corner = (centre[0] - clear, centre[1] + clear)
    note, box = _view_note(adapter, parent, letter, corner, label=label)
    box = _move_note(
        adapter, note, (corner[0] - box[2], corner[1] - box[1]), label=label
    )
    if math.dist((box[2], box[1]), corner) > DETAIL_POSITION_TOL_M:
        raise RuntimeError(f"{label}: letter {box!r} did not land at {corner!r}")
    _telemetry.info(f"{label}: circle {centre!r} r {radius!r}, letter {box!r}")
    return centre, radius


def _add_carriage_arrow(
    adapter: Any, front: Any, stirrup_circle: tuple[tuple[float, float], float]
) -> None:
    """DETAIL C's viewing arrow on FRONT: a letter note whose straight leader
    points straight down onto the block top, clear above D's circle
    (machinist review, farm run 20261024T091056564Z: C had no mark on any
    parent view). The leader leaves the letter's nearer side, so the letter
    slides by any miss until the arrow stands square
    (draw_sm_summing_lever._add_view_arrow)."""
    letter = notes.DETAIL_LETTERS[CARRIAGE_DETAIL.key]
    label = f"view {letter} viewing arrow"
    tip = model_point_in_view(
        adapter,
        front,
        tuple(value / 1000.0 for value in notes.CARRIAGE_ARROW_TIP),
        label=label,
    )
    centre, radius = stirrup_circle
    if math.dist(tip, centre) - radius < VIEW_ARROW_CIRCLE_CLEARANCE:
        raise RuntimeError(f"{label}: tip {tip!r} crowds D's circle at {centre!r}")
    note = add_leader_note(
        adapter,
        letter,
        text_xy=(tip[0] - DETAIL_LETTER_WIDTH, tip[1] + VIEW_ARROW_RISE),
        attach_xy=tip,
        view=front,
        label=label,
    )
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    points = list(annotation.GetLeaderPointsAtIndex(0) or ())
    if len(points) >= 6 and abs(tip[0] - points[0]) > VIEW_ARROW_SQUARE_TOL:
        x, y, z = (float(value) for value in annotation.GetPosition())
        if not annotation.SetPosition2(x + tip[0] - points[0], y, z):
            raise RuntimeError(f"failed to square the {label}")
        adapter.currentModel.EditRebuild3()
        points = list(annotation.GetLeaderPointsAtIndex(0) or ())
    if (
        len(points) < 6
        or math.dist((points[-3], points[-2]), tip) > 0.001
        or abs(tip[0] - points[0]) > VIEW_ARROW_SQUARE_TOL
        or points[1] <= tip[1]
    ):
        raise RuntimeError(f"{label} does not stand square over its tip: {points!r}")
    _assert_on_sheet(_note_box(_early_bound(note, "INote"), label=label), label=label)
    _telemetry.info(
        f"{label}: leader {points[0]:.5f},{points[1]:.5f} -> "
        f"{points[-3]:.5f},{points[-2]:.5f}"
    )


def _crop(adapter: Any, view: Any, detail: Detail) -> None:
    """Crop ``view`` to the circle round ``detail.centre``: sketch the circle
    in the active view's own sketch and Crop2 while it is still selected."""
    view = _early_bound(view, "IView")
    _sketch_view_circle(
        adapter, view, detail.centre, detail.crop_radius, label=f"{detail.label} crop"
    )
    status = int(view.Crop2(False, False, 1))
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()
    view.UpdateViewDisplayGeometry()
    cropped = bool(view.IsCropped())
    if status != CROP_NO_ERROR or not cropped:
        raise RuntimeError(
            f"{detail.label} is not cropped: Crop2 status {status}, IsCropped {cropped}"
        )
    _assert_on_sheet(
        (
            detail.centre[0] - detail.crop_radius,
            detail.centre[1] - detail.crop_radius,
            detail.centre[0] + detail.crop_radius,
            detail.centre[1] + detail.crop_radius,
        ),
        label=f"{detail.label} crop circle",
    )


def _detail(adapter: Any, detail: Detail) -> list[Any]:
    """Place ``detail``, import its settings (if any) at their text points,
    crop it, prove the kept dimensions survived, and label it."""
    view = _placed_detail(adapter, detail)
    annotations: list[Any] = []
    if detail.feature is not None:
        _show_base_view_sketches(adapter, view, (detail.feature,), label=detail.label)
        keep = {
            name: model_point_in_view(
                adapter,
                view,
                tuple(value / 1000.0 for value in xyz),
                label=f"{detail.label} {name} text",
            )
            for name, xyz in DIMENSION_TEXT_POINTS[detail.key].items()
        }
        annotations = curate_view_dimensions(
            adapter,
            view,
            keep=keep,
            view_label=detail.label,
            dimensions_by_feature=spec.DRAWING_DIMENSIONS,
        )
    _crop(adapter, view, detail)
    if detail.feature is not None:
        kept = {
            dimension_name(adapter, _early_bound(annotation, "IAnnotation"))
            for annotation in (_early_bound(view, "IView").GetAnnotations() or ())
        }
        lost = sorted(set(DIMENSION_TEXT_POINTS[detail.key]) - kept)
        if lost:
            raise RuntimeError(
                f"{detail.label} lost {lost} to its crop; kept {sorted(kept)}"
            )
    _label_view(adapter, view, detail.title, detail.label_xy, label=detail.label)
    return annotations


def _assert_dimension_ink_on_sheet(display: Any, *, label: str) -> None:
    """A dimension's native line ink (witness, dimension line, arrows) stays
    on the drawable sheet."""
    display = _early_bound(display, "IDisplayDimension")
    data = _early_bound(display.GetDisplayData(), "IDisplayData")
    points = []
    for index in range(int(data.GetLineCount())):
        line = tuple(float(value) for value in data.GetLineAtIndex2(index))
        if len(line) < 10:
            raise RuntimeError(f"{label}: incomplete native dimension line")
        points.extend(((line[4], line[5]), (line[7], line[8])))
    if not points or int(data.GetTextCount()) < 1:
        raise RuntimeError(f"{label}: missing native dimension display data")
    _assert_on_sheet(
        (
            min(point[0] for point in points),
            min(point[1] for point in points),
            max(point[0] for point in points),
            max(point[1] for point in points),
        ),
        label=f"{label} dimension ink",
    )


def _band(name: str) -> tuple[float, float]:
    """``name``'s nominal and symmetric band in SolidWorks system units."""
    if name in notes.ANGULAR_TOLERANCES:
        return math.radians(spec.YAW_DEG), math.radians(notes.ANGULAR_TOLERANCES[name])
    return notes.DIMENSION_NOMINALS[name] / 1000.0, notes.DIMENSION_TOLERANCES[
        name
    ] / 1000.0


def _assert_reference(name: str, display: Any, *, when: str) -> None:
    """A reference setting (the stud height, set from the stud's measured
    length) reads its nominal in parentheses, no band, and its callout."""
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    value = abs(float(dimension.SystemValue))
    brackets = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
    callout = str(display.GetText(CALLOUT_TEXT_PART) or "").replace("\r\n", "\n")
    if (
        abs(value - notes.DIMENSION_NOMINALS[name] / 1000.0) > 1e-8
        or brackets != ("(", ")")
        or int(tolerance.Type) != 0  # swTolNONE
        or callout != notes.DIMENSION_CALLOUTS[name]
    ):
        raise RuntimeError(
            f"{when} {name}: value {value!r}, brackets {brackets!r}, tolerance "
            f"type {int(tolerance.Type)}, callout {callout!r}"
        )


def _assert_settings(displays: list[tuple[str, Any]], *, when: str) -> None:
    """Each setting reads its nominal (the angle 45, not its supplement), its
    symmetric band and places, and its callout; a reference setting its
    parenthesised nominal."""
    for name, display in displays:
        if name in notes.REFERENCE_DIMENSIONS:
            _assert_reference(name, display, when=when)
            continue
        nominal, band = _band(name)
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        value = abs(float(dimension.SystemValue))
        callout = str(display.GetText(CALLOUT_TEXT_PART) or "").replace("\r\n", "\n")
        if (
            abs(value - nominal) > 1e-8
            or int(tolerance.Type) != 4  # swTolSYMMETRIC
            or abs(float(tolerance.GetMaxValue()) - band) > 1e-9
            or abs(float(tolerance.GetMinValue()) + band) > 1e-9
            or int(display.GetPrimaryTolPrecision2()) != notes.TOLERANCE_PRECISION[name]
            or callout != notes.DIMENSION_CALLOUTS[name]
        ):
            raise RuntimeError(
                f"{when} {name}: value {value!r} (nominal {nominal!r}), tolerance "
                f"type {int(tolerance.Type)} {float(tolerance.GetMinValue())!r}.."
                f"{float(tolerance.GetMaxValue())!r} (band {band!r}), tol places "
                f"{int(display.GetPrimaryTolPrecision2())}, callout {callout!r}"
            )


def _place_settings_sheet(adapter: Any) -> Callable[[], None]:
    """Front and right at 1:2, the four details, the as-shipped note; returns
    the check that re-reads every setting once the drawing has settled."""
    _activate_sheet(adapter, SHEET_NAMES[0])
    front = _placed_base_view(
        adapter, "*Front", FRONT_CENTER, notes.VIEW_TITLES["front"], label="pen front"
    )
    right = _placed_base_view(
        adapter, "*Right", RIGHT_CENTER, notes.VIEW_TITLES["right"], label="pen right"
    )
    annotations = [
        annotation for detail in DETAILS for annotation in _detail(adapter, detail)
    ]
    set_dimension_callouts(
        adapter, annotations, dict(notes.DIMENSION_CALLOUTS), location=CALLOUT_LOCATION
    )
    assert_imported_precision(
        adapter,
        annotations,
        {
            name: places
            for names in spec.DRAWING_PRECISION.values()
            for name, places in names.items()
        },
    )
    displays = [
        (
            dimension_name(adapter, annotation),
            _early_bound(
                _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
                "IDisplayDimension",
            ),
        )
        for annotation in annotations
    ]
    for annotation, (name, _display) in zip(annotations, displays):
        if name in notes.REFERENCE_DIMENSIONS:
            set_reference_dimension(adapter, annotation, label=f"pen {name}")
    if sorted(name for name, _ in displays) != sorted(notes.DIMENSION_CALLOUTS):
        raise RuntimeError(f"pen details imported {sorted(n for n, _ in displays)}")
    for name, display in displays:
        _assert_dimension_ink_on_sheet(display, label=f"pen {name}")
    _assert_settings(displays, when="placed")
    # A, B and D are circled on the view they enlarge (BOUNDED_ON); C, the
    # turned plan, is named by its viewing arrow on FRONT, clear of D's circle.
    parents = {"*Front": front, "*Right": right}
    circles = {
        detail.key: _mark_detail_boundary(
            adapter, parents[BOUNDED_ON[detail.key]], detail
        )
        for detail in DETAILS
        if detail.key in BOUNDED_ON
    }
    _add_carriage_arrow(adapter, front, circles[STIRRUP_DETAIL.key])
    _add_note_block(
        adapter,
        SHEET_NAMES[0],
        SETTINGS_NOTE,
        SETTINGS_NOTE_XY,
        label="as-shipped note",
    )
    return lambda: _assert_settings(displays, when="settled")


# --- sheet 2 ----------------------------------------------------------------------

_INSERT_COLUMN_AFTER = 3  # swTableItemInsertPosition_After
_INSERT_COLUMN_DEFAULT_WIDTH = 0  # swInsertColumn_DefaultWidth


def _bom_cells(table: Any) -> tuple[tuple[str, ...], ...]:
    """Every physical BOM cell, header row first, with visible native rows."""
    contents = []
    for row in range(int(table.RowCount)):
        if table.RowHidden(row) is not False:
            raise RuntimeError(f"pen BOM physical row {row} is not proven visible")
        contents.append(
            tuple(
                str(table.DisplayedText2(row, column, True) or "").strip()
                for column in range(int(table.ColumnCount))
            )
        )
    return tuple(contents)


def _bom_column(
    header: tuple[str, ...], predicate: Callable[[str], bool], label: str
) -> int:
    matches = [index for index, cell in enumerate(header) if predicate(cell.upper())]
    if len(matches) != 1:
        raise RuntimeError(f"pen BOM has no unique {label} column: {header!r}")
    return matches[0]


def _place_exploded_caption(adapter: Any, table: Any, scale: tuple[float, float]) -> None:
    """Place the caption below the rebuilt BOM, including every wrapped row."""
    table = _early_bound(table, "ITableAnnotation")
    annotation = _early_bound(table.GetAnnotation(), "IAnnotation")
    position = tuple(float(value) for value in (annotation.GetPosition() or ()))
    heights = tuple(float(table.GetRowHeight(row)) for row in range(int(table.RowCount)))
    if (
        len(position) != 3
        or not all(map(math.isfinite, position))
        or not heights
        or any(not math.isfinite(height) or height <= 0.0 for height in heights)
    ):
        raise RuntimeError(f"pen BOM has unreadable geometry: {position!r}, {heights!r}")
    bottom = position[1] - sum(heights)
    caption = _add_note_block(
        adapter,
        SHEET_NAMES[1],
        f"{notes.EXPLODED_CAPTION}\nSCALE {_scale_text(scale)}",
        (position[0], bottom - NOTE_GAP),
        label="exploded-view caption",
    )
    gap = bottom - caption[3]
    if gap < VIEW_LABEL_GAP:
        raise RuntimeError(
            f"pen exploded-view caption is only {gap * 1000.0:.2f} mm below BOM"
        )


def _validate_bom(adapter: Any, table: Any) -> tuple[tuple[str, str], ...]:
    """Prove associative Numbers, native identities, descriptions, quantities and
    the item numbers the steps cite; add the registry's VENDOR SKU column after
    DESCRIPTION and return (row key, item number) in BOM order. Material and
    finish remain on component drawings."""
    table = _early_bound(table, "ITableAnnotation")
    contents = _bom_cells(table)
    rows = len(contents)
    columns = len(contents[0]) if contents else 0
    if rows != len(BOM_COMPONENTS) + 1 or columns < 4:
        raise RuntimeError(
            f"pen BOM is {rows}x{columns}; expected {len(BOM_COMPONENTS) + 1} rows "
            "and at least four columns"
        )
    header = contents[0]
    for title in ("MATERIAL", BOM_SKU_TITLE):
        if title in (cell.upper() for cell in header):
            raise RuntimeError(f"pen BOM template already has {title!r}")
    item_column = _bom_column(
        header, lambda cell: cell.startswith("ITEM NO"), "ITEM NO."
    )
    part_column = _bom_column(header, lambda cell: cell == "PART NUMBER", "PART NUMBER")
    description_column = _bom_column(
        header, lambda cell: cell == "DESCRIPTION", "DESCRIPTION"
    )
    quantity_column = _bom_column(header, lambda cell: cell.startswith("QTY"), "QTY.")

    actual: dict[str, tuple[int, str, str, str]] = {}
    identities = bom_row_identities(
        table,
        configuration=SIMPLIFIED_VIEW_CONFIGURATION,
        component_identities=BOM_COMPONENT_IDENTITIES,
    )
    for stem, row_index in identities.items():
        row = contents[row_index]
        actual[stem] = (
            row_index,
            row[item_column],
            row[description_column],
            row[quantity_column],
        )
    if set(actual) != set(BOM_COMPONENTS):
        raise RuntimeError(
            f"pen BOM identities {sorted(actual)!r} != {sorted(BOM_COMPONENTS)!r}"
        )
    # The sequence and checks cite these item numbers (notes.ITEM).
    numbering = {stem: values[1] for stem, values in actual.items()}
    expected_numbering = {BOM_ROW_KEYS[stem]: str(notes.ITEM[stem]) for stem in spec.BOM_ORDER}
    if numbering != expected_numbering:
        raise RuntimeError(
            f"pen BOM item numbers {numbering!r} != {expected_numbering!r}"
        )
    for stem, (row_index, _item, description, quantity) in actual.items():
        number = BOM_PART_NUMBERS[stem]
        if contents[row_index][part_column] != number:
            raise RuntimeError(
                f"pen BOM Number for {stem!r} is "
                f"{contents[row_index][part_column]!r}, expected {number!r}"
            )
        if description != BOM_DESCRIPTIONS[stem]:
            raise RuntimeError(
                f"pen BOM description mismatch for {stem!r}: {description!r}"
            )
        if quantity != str(BOM_QUANTITIES[stem]):
            raise RuntimeError(
                f"pen BOM quantity for {stem!r} is {quantity!r}, "
                f"expected {BOM_QUANTITIES[stem]}"
            )

    # The parts carry no SKU property; made parts print MADE_PART_SKU.
    if not table.InsertColumn2(
        _INSERT_COLUMN_AFTER,
        description_column,
        BOM_SKU_TITLE,
        _INSERT_COLUMN_DEFAULT_WIDTH,
    ):
        raise RuntimeError("pen BOM refused the VENDOR SKU column")
    column = description_column + 1
    if not table.SetColumnTitle2(column, BOM_SKU_TITLE, True):
        raise RuntimeError("pen BOM VENDOR SKU column title did not set")
    for stem, (row_index, *_rest) in actual.items():
        if not table.IsCellTextEditable(row_index, column):
            raise RuntimeError(f"pen BOM VENDOR SKU cell for {stem!r} is locked")
        table.SetText2(row_index, column, True, BOM_SKUS[stem])

    header = _bom_cells(table)[0]
    widths = {
        "item": _bom_column(
            header, lambda cell: cell.startswith("ITEM NO"), "ITEM NO."
        ),
        "part": _bom_column(header, lambda cell: cell == "PART NUMBER", "PART NUMBER"),
        "description": _bom_column(
            header, lambda cell: cell == "DESCRIPTION", "DESCRIPTION"
        ),
        "sku": _bom_column(header, lambda cell: cell == BOM_SKU_TITLE, BOM_SKU_TITLE),
        "quantity": _bom_column(header, lambda cell: cell.startswith("QTY"), "QTY."),
    }
    if len(header) != len(BOM_COLUMN_WIDTHS) or set(widths) != set(BOM_COLUMN_WIDTHS):
        raise RuntimeError(f"pen BOM columns {header!r} are not the contract")
    for key, index in widths.items():
        width = BOM_COLUMN_WIDTHS[key]
        if abs(float(table.SetColumnWidth(index, width, 0)) - width) > 1e-6:
            raise RuntimeError(f"pen BOM {key} column width did not persist")
    for row in range(rows):
        table.SetRowHeight(row, BOM_ROW_HEIGHT, 0)
    before_rebuild = validate_bom_number_property(
        table,
        configuration=SIMPLIFIED_VIEW_CONFIGURATION,
        label="pen",
        expected_rows=rows,
        occurrence_quantities=True,
    )
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("pen BOM rebuild failed")
    settled = _bom_cells(table)
    for stem, (row_index, *_rest) in actual.items():
        for key, text in (("part", BOM_PART_NUMBERS[stem]), ("sku", BOM_SKUS[stem])):
            applied = settled[row_index][widths[key]]
            if applied != text:
                raise RuntimeError(
                    f"pen BOM {key} for {stem!r} reads {applied!r}, expected {text!r}"
                )
    if validate_bom_number_property(
        table,
        configuration=SIMPLIFIED_VIEW_CONFIGURATION,
        label="pen",
        expected_rows=rows,
        occurrence_quantities=True,
    ) != before_rebuild:
        raise RuntimeError(
            "pen native BOM membership/quantities changed during rebuild"
        )
    return tuple((stem, actual[stem][1]) for stem in BOM_COMPONENTS)


def _fit_exploded(adapter: Any, view: Any, *, label: str) -> tuple[float, float]:
    """The largest ``EXPLODED_SCALES`` entry whose outline plus balloon ring
    fits left of the BOM; each candidate is applied, centred and re-read."""
    findings = []
    current = EXPLODED_SCALES[0]
    for scale in EXPLODED_SCALES:
        if scale != current:
            _set_view_scale(adapter, view, scale, label=label)
            current = scale
        _center_view_outline(adapter, view, EXPLODED_ISO_CENTER, label=label)
        ring = _grown(_view_outline(view, label=label), BALLOON_MARGIN)
        overflow = _sheet_findings(ring, right_limit=EXPLODED_RIGHT_LIMIT)
        if not overflow:
            _telemetry.info(f"{label}: ring {ring!r} fits at {_scale_text(scale)}")
            return scale
        findings.append(f"{_scale_text(scale)}: ring {ring!r} " + "; ".join(overflow))
    raise RuntimeError(f"{label}: no scale fits: " + " | ".join(findings))


def _make_explode_readable(
    view: Any, configuration: str, *, label: str
) -> Callable[[], None]:
    """Leave the exploded view's ``configuration`` readable by the balloon
    walker; return the call that restores the source's active configuration.

    ``_drawing_balloons._view_explode_offsets`` reads a NON-active
    configuration's steps directly, and makes an ACTIVE one readable by showing
    its explode on the model. Placed from a builder-named view, the source's
    non-active Default Simplified read zero steps (farm run
    20261016T075516581Z), so when it does, Default Simplified is made the
    source's active configuration for the walk and Default shown again after.
    The source must come back as clean as it went in: the drawing save would
    otherwise write the released assembly.
    """
    bound = _early_bound(view, "IView")
    source = _early_bound(bound.ReferencedDocument, "IModelDoc2")
    manager = _early_bound(source.ConfigurationManager, "IConfigurationManager")

    def active_name() -> str:
        return str(_early_bound(manager.ActiveConfiguration, "IConfiguration").Name)

    active = active_name()
    owner = source.GetConfigurationByName(configuration)
    if owner is None:
        raise RuntimeError(f"{label}: source has no {configuration!r}")
    steps = int(_early_bound(owner, "IConfiguration").GetNumberOfExplodeSteps())
    _telemetry.event(
        "pen.explode_read", configuration=configuration, active=active, steps=steps
    )
    if steps or active == configuration:
        return lambda: None
    was_dirty = bool(source.GetSaveFlag())
    if not bool(source.ShowConfiguration2(configuration)) or (
        active_name() != configuration
    ):
        raise RuntimeError(
            f"{label}: cannot make {configuration!r} the source's active"
        )

    def restore() -> None:
        if not bool(source.ShowConfiguration2(active)) or active_name() != active:
            raise RuntimeError(f"{label}: cannot show the source's {active!r} again")
        if not bool(bound.IsExploded()):
            raise RuntimeError(f"{label}: restoring {active!r} collapsed the view")
        if bool(source.GetSaveFlag()) and not was_dirty:
            raise RuntimeError(
                f"{label}: switching the source's configuration dirtied it"
            )

    return restore


def _place_exploded_sheet(adapter: Any) -> Callable[[], None]:
    """The exploded isometric, its BOM (with vendor SKU) and one balloon per
    row; returns the check that proves the BOM and balloons after the last rebuild.
    """
    label = "pen exploded"
    _activate_sheet(adapter, SHEET_NAMES[1])
    exploded = place_view(
        adapter,
        str(SOURCE),
        EXPLODED_ORIENTATION,
        *EXPLODED_ISO_CENTER,
        scale=SHEET_SCALE,
    )
    set_high_quality_shaded_with_edges(adapter, exploded, label=label)
    # Configuration, then its own explode, then the BOM and balloons bind.
    configuration = apply_view_configuration(adapter, exploded, label=label)
    set_view_exploded_state(
        adapter, exploded, True, configuration=configuration, label=label
    )
    scale = _fit_exploded(adapter, exploded, label=label)
    table = insert_bom_table(
        adapter,
        exploded,
        anchor_xy=BOM_ANCHOR,
        expected_components=BOM_COMPONENTS,
        descriptions=BOM_DESCRIPTIONS,
        identity_aliases=BOM_IDENTITY_ALIASES,
        component_identities=BOM_COMPONENT_IDENTITIES,
        part_number_property="Number",
        configuration_grouping="same-name",
        label="pen",
    )
    items = _validate_bom(adapter, table)
    bom_snapshot = validate_bom_number_property(
        table,
        configuration=configuration,
        label="pen",
        expected_rows=1 + len(BOM_COMPONENTS),
        occurrence_quantities=True,
    )
    restore = _make_explode_readable(exploded, configuration, label=label)
    try:
        landings = add_component_bom_balloons(
            adapter,
            exploded,
            items=items,
            anchors=BALLOON_ANCHORS,
            label="pen exploded-view BOM coverage",
            margin=BALLOON_MARGIN,
        )
    finally:
        primary_error = sys.exception()
        try:
            restore()
        except Exception as cleanup_error:
            if primary_error is None:
                raise
            _telemetry.warn(f"{label}: after balloon failure: {cleanup_error}")
    if len(landings) != sum(BOM_QUANTITIES.values()):
        raise RuntimeError(
            f"pen exploded view carries {len(landings)} balloons, expected one per "
            f"component ({sum(BOM_QUANTITIES.values())})"
        )
    for name, trail in notes.EXPLODE_TRAILS.items():
        _add_explode_trail(adapter, exploded, trail, label=f"pen {name} explode trail")
    _place_exploded_caption(adapter, table, scale)

    def settled() -> None:
        retained = validate_bom_number_property(
            table,
            configuration=configuration,
            label="pen",
            expected_rows=1 + len(BOM_COMPONENTS),
            occurrence_quantities=True,
        )
        if retained != bom_snapshot:
            raise RuntimeError(
                "pen native BOM membership/quantities changed after placement"
            )
        assert_balloon_landings(adapter, landings)

    return settled


# --- sheets 3 and 4 ---------------------------------------------------------------


def _place_finished_view(adapter: Any, sheet_name: str) -> float:
    """The finished assembly in full detail down the sheet's left, labelled;
    returns the x the steps beside it start at. Every sheet needs a view for
    its title-block property links, so the continuation sheet repeats it."""
    label = f"pen finished ({sheet_name})"
    _activate_sheet(adapter, sheet_name)
    finished = place_view(
        adapter, str(SOURCE), "*Isometric", *ASSEMBLY_ISO_CENTER, scale=SHEET_SCALE
    )
    set_high_quality_shaded_with_edges(adapter, finished, label=label)
    configuration = apply_view_configuration(
        adapter, finished, role=ViewRole.FULL_DETAIL, label=label
    )
    set_view_exploded_state(
        adapter, finished, False, configuration=configuration, label=label
    )
    _center_view_outline(adapter, finished, ASSEMBLY_ISO_CENTER, label=label)
    x0, y0, x1, y1 = _view_outline(finished, label=label)
    _assert_on_sheet((x0, y0, x1, y1), label=label)
    assert_full_detail_view(adapter, label="pen assembly")
    _label_view(
        adapter,
        finished,
        notes.VIEW_TITLES["finished"],
        (FINISHED_INK_LOWER_LEFT[0], FINISHED_INK_LOWER_LEFT[1] - VIEW_LABEL_GAP),
        label=label,
    )
    return x1 + NOTE_GAP


def _place_steps_sheet(adapter: Any) -> None:
    """The finished assembly beside the bench steps."""
    steps_x = _place_finished_view(adapter, SHEET_NAMES[2])
    _add_note_block(
        adapter,
        SHEET_NAMES[2],
        ASSEMBLY_STEPS,
        (steps_x, STEPS_TOP),
        label="assembly sequence",
    )


def _place_steps_continued_sheet(adapter: Any) -> None:
    """The finished assembly beside the at-machine steps and the checks."""
    steps_x = _place_finished_view(adapter, SHEET_NAMES[3])
    steps = _add_note_block(
        adapter,
        SHEET_NAMES[3],
        ASSEMBLY_STEPS_CONTINUED,
        (steps_x, STEPS_TOP),
        label="assembly sequence continued",
    )
    _add_note_block(
        adapter,
        SHEET_NAMES[3],
        ASSEMBLY_CHECKS,
        (steps_x, steps[1] - NOTE_GAP),
        label="assembly checks",
    )


# --- package ----------------------------------------------------------------------


def _place_package(adapter: Any) -> Callable[[], None]:
    new_project_drawing(adapter, layout=SPEC.layout, scale=SHEET_SCALE, unit=notes.UNIT)
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="pen package")
    for sheet_name in SHEET_NAMES:
        sheet = _activate_sheet(adapter, sheet_name)
        scale = SHEET_SCALES[sheet_name]
        if not sheet.SetScale(float(scale[0]), float(scale[1]), False, False):
            raise RuntimeError(f"failed to set pen sheet scale: {sheet_name}")
    settings_settled = _place_settings_sheet(adapter)
    exploded_settled = _place_exploded_sheet(adapter)
    _place_steps_sheet(adapter)
    _place_steps_continued_sheet(adapter)

    def settled() -> None:
        settings_settled()
        exploded_settled()

    return settled


@_telemetry.traced("drawing.pn_pen_assembly")
async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")
    check("open pen drawing source", await adapter.open_model(str(SOURCE)))
    source_model = _early_bound(adapter.currentModel, "IModelDoc2")
    properties = read_required_properties(
        source_model,
        ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity"),
        required=("Number", "Revision", "Material Specification", "Finish", "Quantity"),
    )
    if properties["Number"] != notes.DRAWING_NUMBER:
        raise RuntimeError(
            f"pen source Number {properties['Number']!r} != {notes.DRAWING_NUMBER!r}"
        )
    _validate_source(source_model)

    settled = _place_package(adapter)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        layout=SPEC.layout,
        pdf_title=PDF_TITLE,
        scale=SHEET_SCALE,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts=SHEET_LAYOUTS,
        sheet_scales=SHEET_SCALES,
        settled_checks=(settled,),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[ARTIFACT_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
