r"""Create the curated machinist drawing for the amplitude bar.

The SLDPRT remains authoritative.  This recipe supplies only the amplitude-bar
views, dimension layout, and manufacturing notes;
sheet/template and export behavior lives in ``_drawing_common``.
Dimension import and curation live in ``_drawing_dimension_import``.

The bar is ~31.8 in long but only 1/4 in square, so the print shows a 1:4
full-length front view (overall length only) and enlarged cropped model views
of its two ends: a 4:1 detail of each end notch (centring ledge, width and
depth, and at the foot the floor's Ra symbol), VIEW C, the 4:1 right side of
the top end's detail (the reamed pin hole, located from the bar's top edge,
and the square stock), and a 3:1 isometric of each end.  The sheet runs at
1:4; one numbered note states the pin hole's matched press fit.

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_amplitude_bar.py ch-amplitude-bar
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    dimension_name,
    place_view,
    view_name,
)

from _check import check
from _com import _early_bound, _read_member
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_curve_quality import set_precise_curve_quality
from _drawing_leader_notes import add_leader_note
from _drawing_view_arrow import square_view_arrow
from _drawing_notes import add_property_linked_note
from _drawing_edges import visible_view_entities
from _drawing_finish import add_surface_finish
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _printed_limits import limits
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import MACHINED_UM, surface_finish_by_key
import _telemetry
from ch_amplitude_bar_drawing_spec import SURFACE_FINISHES
from ch_amplitude_bar_notes import (
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION_BY_NAME,
    LEVER_NUMBER,
    REFERENCE_DIMENSIONS,
    ROCKER_ARM_NUMBER,
    ROOT_CALLOUT,
    TOP_PIN_NUMBER,
)
from ch_amplitude_bar_spec import (
    BAR_DEPTH,
    BAR_LENGTH,
    BAR_STOCK_UNDERSIZE,
    BAR_WIDTH,
    BOTTOM_NOTCH_DEPTH_BAND,
    BOTTOM_NOTCH_HEIGHT,
    BOTTOM_NOTCH_OFFSET,
    BOTTOM_NOTCH_WIDTH,
    BOTTOM_NOTCH_WIDTH_BAND,
    NOTCH_OFFSET_TOLERANCE_MM,
    TOP_NOTCH_HEIGHT,
    TOP_NOTCH_OFFSET,
    TOP_NOTCH_WIDTH,
    TOP_NOTCH_WIDTH_BAND,
    TOP_PIN_DROP,
    TOP_PIN_HOLE_DIA,
    TOP_PIN_HOLE_LIMITS,
    TOP_PIN_Y,
    UNIT,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_amplitude_bar"]
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

SHEET_SCALE = (1.0, 4.0)  # 1:4
FRONT_CENTER = (0.065, 0.140)
FRONT_KEEP = {
    "BarLength": (FRONT_CENTER[0] - 0.035, FRONT_CENTER[1]),
}


@dataclass(frozen=True)
class CroppedView:
    """A cropped model view of one end of the bar, at its own scale.

    ``fence_mm`` is the crop circle's centre in part (x, y, z) -- bar width
    along x from the origin corner, length along y, depth along z -- and
    ``centre`` where that point lands on the sheet. A view with a ``letter``
    is a detail: its region is circled and lettered on the 1:4 front view.
    """

    name: str
    title: str
    orientation: str
    scale: tuple[int, int]
    fence_mm: tuple[float, float, float]
    radius_mm: float
    centre: tuple[float, float]
    letter: str | None = None
    label_dx: float = 0.0

    @property
    def mm(self) -> float:
        """Sheet metres per part millimetre in the view."""
        return self.scale[0] / self.scale[1] / 1000.0

    def sheet_xy(
        self, x_mm: float, y_mm: float, z_mm: float = 0.0
    ) -> tuple[float, float]:
        """Where part point (x, y, z) lands on the sheet in a *Front or a
        *Right view (the latter looks along -X, so +Z runs to the left)."""
        fx, fy, fz = self.fence_mm
        if self.orientation == "*Front":
            across = x_mm - fx
        elif self.orientation == "*Right":
            across = fz - z_mm
        else:
            raise ValueError(
                f"{self.name}: no planar sheet mapping for {self.orientation}"
            )
        return (
            self.centre[0] + across * self.mm,
            self.centre[1] + (y_mm - fy) * self.mm,
        )

    @property
    def label_xy(self) -> tuple[float, float]:
        """The view-owned label note's top centre, under the crop circle
        (``label_dx`` east of its centre)."""
        return (
            self.centre[0] + self.label_dx,
            self.centre[1] - self.radius_mm * self.mm - DETAIL_LABEL_DROP,
        )

    @property
    def label_text(self) -> str:
        """The view label's words, in the native detail label's form."""
        return f"{self.title}\nSCALE {self.scale[0]} : {self.scale[1]}"

    @property
    def crop_radius(self) -> float:
        """The crop circle's radius on the sheet, metres."""
        return self.radius_mm * self.mm

    @property
    def mark_radius(self) -> float:
        """The same circle drawn on the 1:4 front view, metres."""
        return self.radius_mm * SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0


# A model view has no native label the API can show, so each view's label
# is a note the view owns, in the native label's words, its top edge this far
# under the crop circle; the front view carries each detail's crop circle and
# letter, east of the bar.
DETAIL_LABEL_DROP = 0.007
PARENT_LETTER_GAP = 0.005
CROP_NO_ERROR = 1  # swCropViewErrors_e.swCropViewErrors_NoError
DETAIL_POSITION_TOL_M = 1e-4
NOTE_CENTRING_TOL_M = 0.001
NOTE_CENTRING_PASSES = 2

# At 1:4 an end is under two millimetres wide on the sheet, so each end's
# notch prints in a 4:1 detail (Main ruling 2026-09-27). Each is a cropped
# *Front model view, dimensioned while uncropped and cropped after: r743-6
# (d92938949, leaf 20260927T020523Z-1-e3f9f1f7) showed a native detail of the
# front view refusing the targeted import (available=[]). The same pattern serves
# current MHA-DT-VN-61 / MHA-DT-22 / MHA-DT-24 (pc-r15 detail, d6b8ed93f). A crop
# drops any dimension whose reference lies outside it, so every printed
# edge's ends stay inside the circle (test_cropped_views_frame_their_ends...).
# The foot's views run along the bottom of the sheet, the top end's along the
# top: DETAIL A and the foot isometric; DETAIL B, its right side and the top
# isometric.
DETAIL_A = CroppedView(
    "A",
    "DETAIL A",
    "*Front",
    (4, 1),
    (BAR_WIDTH / 2.0 + 2.0, 0.0, 0.0),
    7.5,
    (0.150, 0.100),
    letter="A",
    # East of centre: the width row's right witness runs down past the
    # circle, and a centred label stood in its path (r1, 64ebba372).
    label_dx=0.016,
)
# DETAIL B and its right side frame the top end down to the .55 notch roof
# (#1038 option 2 deepened it from 1/2); the bar's top edge stays where it
# printed on the sheet before, and the label stays clear of DETAIL A's
# four-line depth stack.
DETAIL_B = CroppedView(
    "B",
    "DETAIL B",
    "*Front",
    (4, 1),
    (BAR_WIDTH / 2.0, BAR_LENGTH - 7.0, 0.0),
    8.5,
    (0.150, 0.196),
    letter="B",
)
# DETAIL B's right side, on its row at its scale: the reamed pin hole,
# located from the back end of the bar's top edge, and that edge's length --
# the square stock. Machinist round 1 (#1293): the hole was a note. A view of
# a detail is not a projected principal view, so it is VIEW C, named by a
# viewing arrow on DETAIL B (rule 9; fan-out screen 2026-11-07 named the
# prose title "RIGHT SIDE OF DETAIL B").
VIEW_C_LETTER = "C"
TOP_SIDE = CroppedView(
    "B right side",
    f"VIEW {VIEW_C_LETTER}",
    "*Right",
    (4, 1),
    (BAR_WIDTH, BAR_LENGTH - 7.0, BAR_DEPTH / 2.0),
    8.5,
    (0.255, DETAIL_B.centre[1]),
)
# The pictorials: each end at 3:1 (machinist round 1, #1293: the full bar at
# 1:8 was an unreadable sliver). The finalizer shades every *Isometric.
TOP_ISO = CroppedView(
    "top isometric",
    "ISOMETRIC, TOP END",
    "*Isometric",
    (3, 1),
    (BAR_WIDTH / 2.0, BAR_LENGTH - 7.0, BAR_DEPTH / 2.0),
    10.0,
    (0.365, 0.205),
)
FOOT_ISO = CroppedView(
    "foot isometric",
    "ISOMETRIC, FOOT END",
    "*Isometric",
    (3, 1),
    (BAR_WIDTH / 2.0, 2.5, BAR_DEPTH / 2.0),
    7.0,
    (0.245, 0.112),
)
CROPPED_VIEWS = (DETAIL_A, DETAIL_B, TOP_SIDE, TOP_ISO, FOOT_ISO)

# A callout's text stands this far outside DETAIL A's fence; a ledge row this
# far outside the bar's end.
DETAIL_A_FENCE_TEXT_GAP = 0.020
DETAIL_ROW_GAP = 0.012
# DETAIL A's width row hangs under its ledge row.
DETAIL_A_WIDTH_ROW_GAP = 0.032
# A width's text block (value, its one-sided band stack, two callout lines)
# prints ~50 mm wide, far wider than a mouth at 4:1 (the top's 12.6 mm, the
# foot's 10.6 mm since #3114): centred on the mouth it
# straddled both extension lines, and in DETAIL A the Ra leader ran through it
# (r743-6b, 64fedd3cc). So each width's text stands west of the bar, its centre
# this far out from the bar's edge, clear of the bar and its own witnesses, and
# the dimension line runs out to it.
WIDTH_TEXT_OFFSET = 0.030
# A depth's ROOTS callout (~40 mm) rides one line over its value; the top
# notch's depth stands this far east of the bar so the callout clears it and
# VIEW C's arrow and letter fit between the bar and its dimension line.
DETAIL_B_DEPTH_TEXT_GAP = 0.028
# The foot depth's text stands this far over the notch floor, outside its
# 9.5 mm span: inside it, the ROOTS line sat on the floor's witness (r1).
DETAIL_A_DEPTH_TEXT_RISE = 0.008
# Text set outside a vertical span hangs WEST of its dimension line, right
# end on it (r2: the ~40 mm ROOTS block centred 20 mm west of the x asked for
# and printed over the front view's bar). So the foot depth's line stands
# just west of the fence and the block hangs from it.
DETAIL_A_DEPTH_LINE_GAP = 0.002
_DETAIL_A_FENCE_X = DETAIL_A.centre[0] - DETAIL_A.radius_mm * DETAIL_A.mm
_DETAIL_A_TEXT_X = _DETAIL_A_FENCE_X - DETAIL_A_FENCE_TEXT_GAP
_DETAIL_A_ROW_Y = DETAIL_A.sheet_xy(0.0, 0.0)[1] - DETAIL_ROW_GAP
_DETAIL_A_WIDTH_ROW_Y = DETAIL_A.sheet_xy(0.0, 0.0)[1] - DETAIL_A_WIDTH_ROW_GAP
DETAIL_A_KEEP = {
    # Left of the fence, over the notch floor: the depth and its band, the
    # ROOTS callout above it, hanging west of the dimension line.
    "BottomNotchHeight": (
        _DETAIL_A_FENCE_X - DETAIL_A_DEPTH_LINE_GAP,
        DETAIL_A.sheet_xy(0.0, BOTTOM_NOTCH_HEIGHT)[1] + DETAIL_A_DEPTH_TEXT_RISE,
    ),
    # One row under the open end: the centring ledge, its text left of the
    # fence. The width two rows lower, its witnesses running down the walls
    # through the notch's air and its text west of the bar, so its dimension
    # line runs west and leaves the air under the right cheek to the Ra symbol.
    "BottomLeftLedge": (_DETAIL_A_TEXT_X, _DETAIL_A_ROW_Y),
    "BottomNotchWidth": (
        DETAIL_A.sheet_xy(0.0, 0.0)[0] - WIDTH_TEXT_OFFSET,
        _DETAIL_A_WIDTH_ROW_Y,
    ),
}
# The ledge's text stands wholly east of the bar's right-face witness (r6,
# c8fafeb80: centred 10 mm out, that witness struck the leading '1' of 1.60):
# the value's half-width plus a 2 mm gap. The value and its band print as
# ten characters (.XXX, a space, the ± band).
LEDGE_TEXT_CHARS = 10
_DETAIL_B_TEXT_X = (
    DETAIL_B.sheet_xy(BAR_WIDTH, 0.0)[0]
    + LEDGE_TEXT_CHARS * 0.0026 / 2.0
    + 0.002
)
_DETAIL_B_ROW_Y = DETAIL_B.sheet_xy(0.0, BAR_LENGTH)[1] + DETAIL_ROW_GAP
DETAIL_B_KEEP = {
    "TopNotchHeight": (
        DETAIL_B.sheet_xy(BAR_WIDTH, 0.0)[0] + DETAIL_B_DEPTH_TEXT_GAP,
        DETAIL_B.sheet_xy(0.0, BAR_LENGTH - TOP_NOTCH_HEIGHT / 2.0)[1],
    ),
    # One row over the open end, chained on the ledge's inner witness: the
    # width's text west of the bar with its callout under it, the ledge's east
    # of it.
    "TopNotchWidth": (
        DETAIL_B.sheet_xy(0.0, 0.0)[0] - WIDTH_TEXT_OFFSET,
        _DETAIL_B_ROW_Y,
    ),
    "TopRightLedge": (_DETAIL_B_TEXT_X, _DETAIL_B_ROW_Y),
}
# The top end's right side: the hole's offset from the back face one row over
# the end, its text east of the back face's witness (the section shares that
# witness) by the half-width of its HOLE WALL callout over it, the section a
# row higher with its STOCK callout over it, the drop east of the bar, and the
# diameter's leader out to the south-east with its THRU / PRESS FIT callout
# under the value.
_TOP_SIDE_END_Y = TOP_SIDE.sheet_xy(0.0, BAR_LENGTH, 0.0)[1]
_TOP_SIDE_BACK_X = TOP_SIDE.sheet_xy(0.0, 0.0, 0.0)[0]
TOP_SIDE_KEEP = {
    "TopPinX": (
        _TOP_SIDE_BACK_X + 0.026,
        _TOP_SIDE_END_Y + DETAIL_ROW_GAP - 0.002,
    ),
    "BarSection": (
        TOP_SIDE.sheet_xy(0.0, 0.0, BAR_DEPTH / 2.0)[0],
        _TOP_SIDE_END_Y + 0.026,
    ),
    "TopPinDrop": (
        _TOP_SIDE_BACK_X + DETAIL_ROW_GAP,
        TOP_SIDE.sheet_xy(0.0, BAR_LENGTH - TOP_PIN_DROP / 2.0, 0.0)[1],
    ),
    "TopPinDia": (
        _TOP_SIDE_BACK_X + 0.032,
        TOP_SIDE.sheet_xy(0.0, BAR_LENGTH - TOP_PIN_DROP, 0.0)[1] - 0.017,
    ),
}
# Callouts that stack over their value; the rest hang under it. SOLIDWORKS
# drops a multi-line callout above a value from the print (r1: the two-line
# TopNotchWidth callout never reached the PDF), so these are one line each.
CALLOUTS_ABOVE = frozenset({"BottomNotchHeight", "BarSection", "TopPinX"})

# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what this sheet prints, beside the constants of the
# code that prints it, in the part frame (CroppedView: bar width along X from
# the origin corner, length along Y from the foot end, depth along Z from the
# back face; the top notch at +Y, its pin hole along X through both cheeks).
# A band is the dimension's own native band, else the title block's row for
# the places the sheet prints (DRAWING_PRECISION_BY_NAME); the 1/4 square's
# two sides print once, as the reference stock section, and carry the
# stock's +0/-.002 band. The declarations print nothing.
_P = DRAWING_PRECISION_BY_NAME
_SELF = "draw_ch_amplitude_bar"
_SPEC = "ch_amplitude_bar_spec"
_NOTES = "ch_amplitude_bar_notes"
_FRAME = (_SELF, "CroppedView")
# ROOTS R.015 MAX (ROOT_CALLOUT): the largest corner radius either notch's
# root may carry, in mm.
_ROOT_RADIUS_MAX = 0.015 * 25.4


def _plane(axis: str, value: float) -> dict[str, Any]:
    return {"frame": "model", "axis": axis, "value": value}


part_metadata(
    model_sources=(
        _FRAME,
        (_SPEC, "BAR_LENGTH"),
        (_SPEC, "BAR_WIDTH"),
        (_SPEC, "BAR_DEPTH"),
    ),
    precision_sources=(
        (_NOTES, "DRAWING_PRECISION"),
        (_NOTES, "DRAWING_PRECISION_BY_NAME"),
    ),
)
# The stock section, 1/4 SQ (.25) REF on the top end's side view
# (TOP_SIDE_KEEP "BarSection"): as bought, +0/-.002 on both sides.
_SECTION_SOURCES = (
    (_SPEC, "BAR_STOCK_UNDERSIZE"),
    (_NOTES, "REFERENCE_DIMENSIONS"),
    (_SELF, "TOP_SIDE_KEEP"),
)
_SECTION_CALLOUT = (
    DIMENSION_CALLOUTS["BarSection"],
    ((_NOTES, "DIMENSION_CALLOUTS"),),
)
# The back face: the pin hole's offset runs from it (TOP_SIDE_KEEP "TopPinX").
requirement(
    "back_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("plane",),
    fields={"plane": (_plane("z", 0.0), (_FRAME,))},
)
requirement(
    "front_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), BAR_DEPTH),),
    requirements=("section",),
    fields={
        "plane": (_plane("z", BAR_DEPTH), (_FRAME, (_SPEC, "BAR_DEPTH"))),
        "section": (
            [BAR_DEPTH - BAR_STOCK_UNDERSIZE, BAR_DEPTH],
            ((_SPEC, "BAR_DEPTH"), *_SECTION_SOURCES),
        ),
        "section_nominal": (BAR_DEPTH, ((_SPEC, "BAR_DEPTH"),)),
        "section_from": ("back_face", ((_SELF, "TOP_SIDE_KEEP"),)),
        "dimension_type": ("reference", ((_NOTES, "REFERENCE_DIMENSIONS"),)),
        "callout": _SECTION_CALLOUT,
    },
    precision={"section": _P["BarSection"]},
)
# The left face: the foot notch's centring ledge runs from it (DETAIL_A_KEEP
# "BottomLeftLedge"); the right face: the top notch's (DETAIL_B_KEEP
# "TopRightLedge"), across the square's width.
requirement(
    "left_face",
    kind="face",
    faces=(PlanarFace((-1.0, 0.0, 0.0), 0.0),),
    requirements=("plane",),
    fields={"plane": (_plane("x", 0.0), (_FRAME,))},
)
requirement(
    "right_face",
    kind="face",
    faces=(PlanarFace((1.0, 0.0, 0.0), BAR_WIDTH),),
    requirements=("width",),
    fields={
        "plane": (_plane("x", BAR_WIDTH), (_FRAME, (_SPEC, "BAR_WIDTH"))),
        "width": (
            [BAR_WIDTH - BAR_STOCK_UNDERSIZE, BAR_WIDTH],
            ((_SPEC, "BAR_WIDTH"), *_SECTION_SOURCES),
        ),
        "width_nominal": (BAR_WIDTH, ((_SPEC, "BAR_WIDTH"),)),
        "width_from": ("left_face", ((_SELF, "TOP_SIDE_KEEP"),)),
        "dimension_type": ("reference", ((_NOTES, "REFERENCE_DIMENSIONS"),)),
        "callout": _SECTION_CALLOUT,
    },
    precision={"width": _P["BarSection"]},
)
# Both ends, each split in two by its notch: the length 31.82 between them
# (FRONT_KEEP "BarLength"); every depth along the bar runs from its own end.
requirement(
    "foot_end",
    kind="face",
    faces=(PlanarFace((0.0, -1.0, 0.0), 0.0),),
    requirements=("plane",),
    fields={"plane": (_plane("y", 0.0), (_FRAME,))},
)
requirement(
    "top_end",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), BAR_LENGTH),),
    requirements=("length",),
    fields={
        "plane": (_plane("y", BAR_LENGTH), (_FRAME, (_SPEC, "BAR_LENGTH"))),
        "length": (
            limits(BAR_LENGTH, _P["BarLength"], unit=UNIT),
            ((_SPEC, "BAR_LENGTH"), (_SPEC, "UNIT"), (_SELF, "FRONT_KEEP")),
        ),
        "length_nominal": (BAR_LENGTH, ((_SPEC, "BAR_LENGTH"),)),
        "length_from": ("foot_end", ((_SELF, "FRONT_KEEP"),)),
    },
    precision={"length": _P["BarLength"]},
)
# Each end's notch, centred on the width and through the whole depth: its
# two walls and its root. Its width carries its one-sided native band and its
# mate (RUNNING FIT, CHEEK WALL MIN), its centring ledge +/-.002 from one side
# face, its depth from its own end, and the ROOTS R.015 MAX callout on that
# depth. The foot notch's root is the bar's one sliding face (Ra on it).
_TOP_NOTCH_LEFT = BAR_WIDTH - TOP_NOTCH_OFFSET - TOP_NOTCH_WIDTH
_BOTTOM_NOTCH_RIGHT = BOTTOM_NOTCH_OFFSET + BOTTOM_NOTCH_WIDTH
_LEDGE_BAND = (NOTCH_OFFSET_TOLERANCE_MM, -NOTCH_OFFSET_TOLERANCE_MM)
_ROOT = (_ROOT_RADIUS_MAX, ((_NOTES, "ROOT_CALLOUT"),))
requirement(
    "top_notch",
    kind="notch",
    faces=(
        PlanarFace((1.0, 0.0, 0.0), _TOP_NOTCH_LEFT),
        PlanarFace((-1.0, 0.0, 0.0), -(BAR_WIDTH - TOP_NOTCH_OFFSET)),
        PlanarFace((0.0, 1.0, 0.0), BAR_LENGTH - TOP_NOTCH_HEIGHT),
    ),
    requirements=("width", "ledge", "depth", "root_radius_max"),
    fields={
        "open_to": ("top_end", (_FRAME,)),
        "thru": (True, ((_SELF, "DETAIL_B"), (_SELF, "TOP_ISO"))),
        "width": (
            limits(TOP_NOTCH_WIDTH, _P["TopNotchWidth"], TOP_NOTCH_WIDTH_BAND),
            (
                (_SPEC, "TOP_NOTCH_WIDTH"),
                (_SPEC, "TOP_NOTCH_WIDTH_BAND"),
                (_SELF, "DETAIL_B_KEEP"),
            ),
        ),
        "width_nominal": (TOP_NOTCH_WIDTH, ((_SPEC, "TOP_NOTCH_WIDTH"),)),
        "ledge": (
            limits(TOP_NOTCH_OFFSET, _P["TopRightLedge"], _LEDGE_BAND),
            (
                (_SPEC, "TOP_NOTCH_OFFSET"),
                (_SPEC, "NOTCH_OFFSET_TOLERANCE_MM"),
                (_SELF, "DETAIL_B_KEEP"),
            ),
        ),
        "ledge_nominal": (TOP_NOTCH_OFFSET, ((_SPEC, "TOP_NOTCH_OFFSET"),)),
        "ledge_from": ("right_face", ((_SELF, "DETAIL_B_KEEP"),)),
        "depth": (
            limits(TOP_NOTCH_HEIGHT, _P["TopNotchHeight"], unit=UNIT),
            ((_SPEC, "TOP_NOTCH_HEIGHT"), (_SPEC, "UNIT"), (_SELF, "DETAIL_B_KEEP")),
        ),
        "depth_nominal": (TOP_NOTCH_HEIGHT, ((_SPEC, "TOP_NOTCH_HEIGHT"),)),
        "depth_from": ("top_end", ((_SELF, "DETAIL_B_KEEP"),)),
        "root_radius_max": _ROOT,
        "mate": (LEVER_NUMBER, ((_NOTES, "LEVER_NUMBER"),)),
        "width_callout": (
            DIMENSION_CALLOUTS["TopNotchWidth"],
            ((_NOTES, "DIMENSION_CALLOUTS"),),
        ),
        "depth_callout": (ROOT_CALLOUT, ((_NOTES, "DIMENSION_CALLOUTS"),)),
    },
    precision={
        "width": _P["TopNotchWidth"],
        "ledge": _P["TopRightLedge"],
        "depth": _P["TopNotchHeight"],
    },
)
_FOOT_FINISH = surface_finish_by_key(SURFACE_FINISHES, "bottom_notch_floor")
requirement(
    "foot_notch",
    kind="notch",
    faces=(
        PlanarFace((1.0, 0.0, 0.0), BOTTOM_NOTCH_OFFSET),
        PlanarFace((-1.0, 0.0, 0.0), -_BOTTOM_NOTCH_RIGHT),
        _FOOT_FINISH.face,
    ),
    requirements=("width", "ledge", "depth", "root_radius_max", "finish_ra"),
    fields={
        "open_to": ("foot_end", (_FRAME,)),
        "thru": (True, ((_SELF, "DETAIL_A"), (_SELF, "FOOT_ISO"))),
        "width": (
            limits(BOTTOM_NOTCH_WIDTH, _P["BottomNotchWidth"], BOTTOM_NOTCH_WIDTH_BAND),
            (
                (_SPEC, "BOTTOM_NOTCH_WIDTH"),
                (_SPEC, "BOTTOM_NOTCH_WIDTH_BAND"),
                (_SELF, "DETAIL_A_KEEP"),
            ),
        ),
        "width_nominal": (BOTTOM_NOTCH_WIDTH, ((_SPEC, "BOTTOM_NOTCH_WIDTH"),)),
        "ledge": (
            limits(BOTTOM_NOTCH_OFFSET, _P["BottomLeftLedge"], _LEDGE_BAND),
            (
                (_SPEC, "BOTTOM_NOTCH_OFFSET"),
                (_SPEC, "NOTCH_OFFSET_TOLERANCE_MM"),
                (_SELF, "DETAIL_A_KEEP"),
            ),
        ),
        "ledge_nominal": (BOTTOM_NOTCH_OFFSET, ((_SPEC, "BOTTOM_NOTCH_OFFSET"),)),
        "ledge_from": ("left_face", ((_SELF, "DETAIL_A_KEEP"),)),
        "depth": (
            limits(
                BOTTOM_NOTCH_HEIGHT, _P["BottomNotchHeight"], BOTTOM_NOTCH_DEPTH_BAND
            ),
            (
                (_SPEC, "BOTTOM_NOTCH_HEIGHT"),
                (_SPEC, "BOTTOM_NOTCH_DEPTH_BAND"),
                (_SELF, "DETAIL_A_KEEP"),
            ),
        ),
        "depth_nominal": (BOTTOM_NOTCH_HEIGHT, ((_SPEC, "BOTTOM_NOTCH_HEIGHT"),)),
        "depth_from": ("foot_end", ((_SELF, "DETAIL_A_KEEP"),)),
        "root_radius_max": _ROOT,
        "finish_ra": (
            MACHINED_UM,
            (("ch_amplitude_bar_drawing_spec", "SURFACE_FINISHES"),),
        ),
        "mate": (ROCKER_ARM_NUMBER, ((_NOTES, "ROCKER_ARM_NUMBER"),)),
        "width_callout": (
            DIMENSION_CALLOUTS["BottomNotchWidth"],
            ((_NOTES, "DIMENSION_CALLOUTS"),),
        ),
        "depth_callout": (ROOT_CALLOUT, ((_NOTES, "DIMENSION_CALLOUTS"),)),
    },
    precision={
        "width": _P["BottomNotchWidth"],
        "ledge": _P["BottomLeftLedge"],
        "depth": _P["BottomNotchHeight"],
    },
)
# The reamed press hole across the top notch, through both cheeks
# (TOP_SIDE_KEEP): the .0775 reamer's size, no band, and REAM THRU / SEE NOTE
# 1 callout (owner ruling 2026-11-24, fit audit question 3), its offset from
# the back face (.XXX, HOLE WALL MIN) and its drop from the top end. "dia" is
# the spec's ANALYSIS band (what the reamer is modelled to cut), not a
# printed limit.
_HOLE_SOURCES = ((_NOTES, "DIMENSION_CALLOUTS"), (_SELF, "TOP_SIDE_KEEP"))
requirement(
    "top_pin_hole",
    kind="hole",
    faces=(CylinderFace(TOP_PIN_HOLE_DIA),),
    requirements=("dia", "thru", "location_from_back", "drop"),
    fields={
        "at": (
            [0.0, TOP_PIN_Y, BAR_DEPTH / 2.0],
            ((_SPEC, "TOP_PIN_Y"), (_SPEC, "BAR_DEPTH")),
        ),
        "axis": ((1.0, 0.0, 0.0), (_FRAME,)),
        "dia": (
            list(TOP_PIN_HOLE_LIMITS),
            ((_SPEC, "TOP_PIN_HOLE_LIMITS"), (_SELF, "TOP_SIDE_KEEP")),
        ),
        "nominal_dia": (TOP_PIN_HOLE_DIA, ((_SPEC, "TOP_PIN_HOLE_DIA"),)),
        "thru": (True, _HOLE_SOURCES),
        "process": ("ream", _HOLE_SOURCES),
        "location_from_back": (
            limits(BAR_DEPTH / 2.0, _P["TopPinX"], unit=UNIT),
            ((_SPEC, "BAR_DEPTH"), (_SPEC, "UNIT"), (_SELF, "TOP_SIDE_KEEP")),
        ),
        "location_from_back_nominal": (BAR_DEPTH / 2.0, ((_SPEC, "BAR_DEPTH"),)),
        "location_from": ("back_face", ((_SELF, "TOP_SIDE_KEEP"),)),
        "drop": (
            limits(TOP_PIN_DROP, _P["TopPinDrop"], unit=UNIT),
            ((_SPEC, "TOP_PIN_DROP"), (_SPEC, "UNIT"), (_SELF, "TOP_SIDE_KEEP")),
        ),
        "drop_nominal": (TOP_PIN_DROP, ((_SPEC, "TOP_PIN_DROP"),)),
        "drop_from": ("top_end", ((_SELF, "TOP_SIDE_KEEP"),)),
        "press_fit_on": (TOP_PIN_NUMBER, ((_NOTES, "TOP_PIN_NUMBER"),)),
        "callout": (DIMENSION_CALLOUTS["TopPinDia"], _HOLE_SOURCES),
        "location_callout": (DIMENSION_CALLOUTS["TopPinX"], _HOLE_SOURCES),
        "fit_note": (DRAWING_NOTES, ((_NOTES, "DRAWING_NOTES"),)),
    },
    precision={
        "dia": _P["TopPinDia"],
        "location_from_back": _P["TopPinX"],
        "drop": _P["TopPinDrop"],
    },
)

# VIEW C's viewing arrow on DETAIL B: level, looking -X onto the bar's right
# face (the *Right view's direction), its tip just off the face between the
# notch floor's witness and the depth's text, its letter at the tail
# (draw_fr_top_frame._add_view_arrow, mirrored: the letter stands east).
VIEW_LETTER_HEIGHT = 0.005
VIEW_ARROW_TIP_GAP = 0.0035
VIEW_ARROW_LENGTH = 0.010
VIEW_ARROW_RISE_MM = 2.5  # over the notch floor, in part millimetres
_VIEW_C_TIP = (
    DETAIL_B.sheet_xy(BAR_WIDTH, 0.0)[0] + VIEW_ARROW_TIP_GAP,
    DETAIL_B.sheet_xy(0.0, BAR_LENGTH - TOP_NOTCH_HEIGHT + VIEW_ARROW_RISE_MM)[1],
)
VIEW_C_ARROW = (
    (_VIEW_C_TIP[0] + VIEW_ARROW_LENGTH, _VIEW_C_TIP[1] + VIEW_LETTER_HEIGHT / 2.0),
    _VIEW_C_TIP,
)
# The pin hole's matched-fit note, linked from its callout: under DETAIL A's
# label, right of the front view's foot, left of the title block (upper-left).
NOTES_XY = (0.075, 0.046)

# The foot notch floor's Ra (Main ruling B, 2026-09-27). The symbol is ~17 mm
# wide at the fleet's 2.5 mm height, wider than the 10.6 mm mouth, so it
# stands under the right cheek, inside the fence, and its bent leader climbs
# through the mouth to the floor. With the width row hanging under the mouth,
# a leader out of it must cross a witness or the dimension line; it crosses
# only the right witness, between the bar's end and the row (an extension
# line may be crossed; a dimension line should not be). The leader lands
# 0.5 mm west of the floor's middle: from the east half of the .104 floor
# (#3114) it left the mouth within 0.5 mm of the right cheek's corner.
FLOOR_FINISH_ATTACH = DETAIL_A.sheet_xy(BAR_WIDTH / 2.0 - 0.5, BOTTOM_NOTCH_HEIGHT)
FLOOR_FINISH_SYMBOL = (
    DETAIL_A.sheet_xy(BAR_WIDTH / 2.0, 0.0)[0] + 0.0163,
    DETAIL_A.sheet_xy(0.0, 0.0)[1] - 0.017,
)
FINISH_CHAR_HEIGHT = 0.0025
# The bent leader's shoulder runs this far from the symbol's vertex toward the
# attach point before it turns (measured on the pivot-shaft sheet, r743-5).
FINISH_SHOULDER = 0.0063


# The cropped-view helpers below are copied from draw_pinion_spring's pc-r15
# kink detail (d6b8ed93f); a shared crop module is #1036, after the release.


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
    Without ``add_to_db`` the circle is left SELECTED, which is what Crop2
    consumes.
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


def _placed_cropped_view(adapter: Any, spec: CroppedView) -> Any:
    """``spec``'s view, uncropped: a standalone model view in its orientation
    and at its scale, moved so the fence point lands on ``spec.centre``
    (checked to DETAIL_POSITION_TOL_M)."""
    draw = adapter.currentModel
    view = _early_bound(
        place_view(
            adapter, str(SOURCE), spec.orientation, *spec.centre, scale=spec.scale
        ),
        "IView",
    )
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if ratio != tuple(float(value) for value in spec.scale):
        raise RuntimeError(f"{spec.name} scale {ratio!r}, expected {spec.scale!r}")
    focus = tuple(value / 1000.0 for value in spec.fence_mm)
    label = f"{spec.name} centre"
    center = model_point_in_view(adapter, view, focus, label=label)
    position = tuple(float(value) for value in view.Position)
    target = [position[axis] + spec.centre[axis] - center[axis] for axis in range(2)]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError(f"failed to move {spec.name} onto its spot")
    draw.EditRebuild3()
    center = model_point_in_view(adapter, view, focus, label=label)
    if math.dist(center, spec.centre) > DETAIL_POSITION_TOL_M:
        raise RuntimeError(
            f"{spec.name} centre sits at {center!r}, not {spec.centre!r}"
        )
    return view


def _crop_view(adapter: Any, view: Any, spec: CroppedView) -> None:
    """Crop ``view`` to its circle round ``spec.centre``: activate it,
    sketch the circle in its own sketch and Crop2 while the circle is still
    selected. Crop status, IsCropped, the outline and its style are read back
    and raise."""
    draw = adapter.currentModel
    view = _early_bound(view, "IView")
    uncropped = tuple(float(value) for value in view.GetOutline())
    label = spec.name
    name = _activate_view(adapter, view, label=label)
    _sketch_circle(adapter, view, spec.centre, spec.crop_radius, label=f"{label} crop")
    status = int(view.Crop2(False, False, 1))
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    view.UpdateViewDisplayGeometry()
    cropped = bool(view.IsCropped())
    outline = tuple(float(value) for value in view.GetOutline())
    _telemetry.info(
        f"amplitude-bar: {label} {name!r} Crop2 status {status}, IsCropped "
        f"{cropped}, outline {tuple(round(value * 1000, 1) for value in outline)} mm",
        crop_status=status,
        cropped=cropped,
    )
    if status != CROP_NO_ERROR or not cropped:
        raise RuntimeError(
            f"{label} is not cropped: Crop2 status {status}, IsCropped {cropped}"
        )
    # Uncropped, each view spans the whole 808 mm bar (2-3 m on the sheet);
    # the crop is one ~40-64 mm circle.
    if (
        len(outline) != 4
        or len(uncropped) != 4
        or outline[3] - outline[1] > (uncropped[3] - uncropped[1]) / 2.0
    ):
        raise RuntimeError(
            f"{label} crop did not take: outline {outline!r}, before {uncropped!r}"
        )
    boundary = (bool(view.CropViewJaggedOutline), bool(view.CropViewNoOutline))
    if boundary != (False, False):
        raise RuntimeError(
            f"{label}'s crop boundary is not its plain circle: jagged, "
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


def _dimension_then_crop(
    adapter: Any, view: Any, spec: CroppedView, keep: dict[str, tuple[float, float]]
) -> list[Any]:
    """Import and curate ``spec``'s dimensions while it is uncropped, then
    crop it. The names read back before and after the crop ride one
    ``notch_detail.crop`` event; any kept dimension missing after raises."""
    annotations = curate_view_dimensions(
        adapter,
        view,
        keep=keep,
        view_label=spec.name,
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    before = _view_dimension_names(adapter, view)
    _crop_view(adapter, view, spec)
    after = _view_dimension_names(adapter, view)
    lost = sorted(set(keep) - set(after))
    _telemetry.event(
        "notch_detail.crop",
        detail=spec.name,
        dimensions_before=",".join(before),
        dimensions_after=",".join(after),
        lost=",".join(lost),
    )
    _telemetry.info(
        f"amplitude-bar: {spec.name} dimensions before crop {before}, after {after}"
    )
    if lost:
        raise RuntimeError(
            f"{spec.name} lost {lost} to its crop; before {before}, after {after}"
        )
    return annotations


def _mark_detail_on_front(
    adapter: Any, front: Any, detail: CroppedView
) -> tuple[float, float]:
    """Circle ``detail``'s region on the 1:4 front view; returns its sheet
    centre. A plain view-sketch circle, drawn direct to the database in the
    outline's black."""
    _activate_view(adapter, front, label="front view")
    center = model_point_in_view(
        adapter,
        front,
        (detail.fence_mm[0] / 1000.0, detail.fence_mm[1] / 1000.0, 0.0),
        label=f"detail {detail.name} mark centre",
    )
    circle = _sketch_circle(
        adapter,
        front,
        center,
        detail.mark_radius,
        label=f"detail {detail.name} mark",
        add_to_db=True,
    )
    segment = _early_bound(circle, "ISketchSegment")
    segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
    if int(segment.Color) != 0:
        raise RuntimeError(f"detail {detail.name} mark circle colour did not persist")
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()
    return center


def _plain_text(text: str) -> str:
    """A note's words with its line breaks and spacing folded to single spaces."""
    return " ".join(str(text).split())


def _note_box(note: Any, *, label: str) -> tuple[float, float, float, float]:
    """``INote.GetExtent``'s lower-left and upper-right corners, sheet metres."""
    values = tuple(float(value) for value in (note.GetExtent() or ()))
    if len(values) != 6 or not all(map(math.isfinite, values)):
        raise RuntimeError(f"{label}: invalid note extent {values!r}")
    box = (values[0], values[1], values[3], values[4])
    if box[0] >= box[2] or box[1] >= box[3]:
        raise RuntimeError(f"{label}: empty note extent {values!r}")
    return box


def _note_centring_error(
    box: tuple[float, float, float, float],
    center_x: float,
    top: float | None,
    center_y: float | None,
) -> tuple[float, float]:
    """How far a note's extent sits from its target: its horizontal centre
    against ``center_x``, and its top edge against ``top`` or else its
    vertical centre against ``center_y``."""
    error_x = (box[0] + box[2]) / 2.0 - center_x
    if top is not None:
        return error_x, box[3] - top
    if center_y is None:
        raise ValueError("a centred note needs a top edge or a centre height")
    return error_x, (box[1] + box[3]) / 2.0 - center_y


def _centred_view_note(
    adapter: Any,
    view: Any,
    text: str,
    *,
    center_x: float,
    top: float | None = None,
    center_y: float | None = None,
    label: str,
) -> tuple[float, float, float, float]:
    """Insert a note owned by ``view``, centred on ``center_x`` by its extent;
    ``top`` pins its top edge, ``center_y`` its middle. A note that does not
    centre, or lands in another view, raises."""
    _activate_view(adapter, view, label=label)
    y = top if top is not None else center_y
    note = add_note(adapter, text, center_x, y)
    if note is None:
        raise RuntimeError(f"failed to add the {label} note")
    note = _early_bound(note, "INote")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    box = _note_box(note, label=label)
    for _ in range(NOTE_CENTRING_PASSES):
        error_x, error_y = _note_centring_error(box, center_x, top, center_y)
        if max(abs(error_x), abs(error_y)) <= NOTE_CENTRING_TOL_M / 10.0:
            break
        position = tuple(
            float(value) for value in _read_member(annotation, "GetPosition")
        )
        if not annotation.SetPosition2(
            position[0] - error_x, position[1] - error_y, 0.0
        ):
            raise RuntimeError(f"failed to centre the {label} note")
        adapter.currentModel.EditRebuild3()
        box = _note_box(note, label=label)
    error_x, error_y = _note_centring_error(box, center_x, top, center_y)
    _telemetry.info(
        f"amplitude-bar: {label} note {text!r} extent "
        f"({box[0] * 1000:.1f}, {box[1] * 1000:.1f})-({box[2] * 1000:.1f}, "
        f"{box[3] * 1000:.1f}) mm",
        label=label,
    )
    if max(abs(error_x), abs(error_y)) > NOTE_CENTRING_TOL_M:
        raise RuntimeError(
            f"{label} note did not centre: off by ({error_x * 1000:.2f}, "
            f"{error_y * 1000:.2f}) mm"
        )
    first_line = _plain_text(text.split("\n")[0])
    texts = [
        _plain_text(_early_bound(found, "INote").GetText() or "")
        for found in (_early_bound(view, "IView").GetNotes() or ())
    ]
    if sum(found.startswith(first_line) for found in texts) != 1:
        raise RuntimeError(
            f"{label} note did not land in its view: its notes are {texts!r}"
        )
    return box


def _label_view(adapter: Any, view: Any, spec: CroppedView) -> None:
    """Label ``spec``'s view under its crop circle."""
    _centred_view_note(
        adapter,
        view,
        spec.label_text,
        center_x=spec.label_xy[0],
        top=spec.label_xy[1],
        label=f"{spec.name} label",
    )


def _letter_detail(
    adapter: Any, front: Any, detail: CroppedView, mark: tuple[float, float]
) -> None:
    """Letter ``detail``'s mark on the front view, east of the bar."""
    _centred_view_note(
        adapter,
        front,
        str(detail.letter),
        center_x=mark[0] + detail.mark_radius + PARENT_LETTER_GAP,
        center_y=mark[1],
        label=f"detail {detail.name} letter",
    )


def _add_view_arrow(adapter: Any, parent: Any) -> None:
    """VIEW C's level letter arrow on DETAIL B, square onto the bar's right
    face (draw_fr_top_frame._add_view_arrow, mirrored: the letter stands east
    of the tip, so it still slides only in y)."""
    text_xy, tip_xy = VIEW_C_ARROW
    label = f"view {VIEW_C_LETTER} viewing arrow"
    note = add_leader_note(
        adapter, VIEW_C_LETTER, text_xy=text_xy, attach_xy=tip_xy, view=parent, label=label
    )
    points = square_view_arrow(
        adapter, note, text_xy=text_xy, tip_xy=tip_xy, axis=1, label=label,
        letter_height=VIEW_LETTER_HEIGHT,
    )
    if points[0] <= tip_xy[0]:
        raise RuntimeError(f"{label} does not run west onto the face: leader {points}")


def _notch_floor_edge(view: Any) -> Any:
    """The foot notch floor's near edge in DETAIL A: edge-on it IS the floor's
    line, and its faces include the floor the control names."""
    span = sorted((BOTTOM_NOTCH_OFFSET, BOTTOM_NOTCH_OFFSET + BOTTOM_NOTCH_WIDTH))
    matches = []
    for raw in visible_view_entities(view, 1, label="bottom notch floor"):
        edge = _early_bound(raw, "IEdge")
        start, end = edge.GetStartVertex(), edge.GetEndVertex()
        if start is None or end is None:
            continue
        points = [
            tuple(float(v) * 1000.0 for v in _early_bound(vertex, "IVertex").GetPoint())
            for vertex in (start, end)
        ]
        if any(abs(p[1] - BOTTOM_NOTCH_HEIGHT) > 0.01 for p in points):
            continue
        if not all(
            math.isclose(a, b, abs_tol=0.01)
            for a, b in zip(sorted(p[0] for p in points), span)
        ):
            continue
        matches.append((points[0][2], edge))
    # The near (z = BarDepth) and far (z = 0) edges project onto one line and
    # both bound the floor; take the near one when both are listed.
    depths = sorted(round(z, 2) for z, _edge in matches)
    if depths not in ([0.0], [round(BAR_DEPTH, 2)], [0.0, round(BAR_DEPTH, 2)]):
        raise RuntimeError(f"unexpected bottom notch floor edges at z={depths} mm")
    return max(matches, key=lambda item: item[0])[1]


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open amplitude-bar source", adapter.open_model(str(SOURCE)))
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("ch-amplitude-bar"),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Amplitude Bar Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "amplitude bar; polished steel; coefficient bar",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # The pin hole is small enough that the default curve resolution drew it
    # as a polygon in every view (machinist review of main 31cea0b73).
    set_precise_curve_quality(adapter, label="amplitude-bar")

    # The front view goes on first: the first view is the title block's
    # property view.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 4))

    # The cropped views are placed and dimensioned before the front view's
    # import, one at a time, each while it is uncropped, then cropped. The
    # profile owns every notch dimension, so a targeted import of it delivers
    # the whole set; a dimension already on the sheet is never imported again,
    # while a deleted one is. Detail A keeps the foot's three and deletes the
    # rest, detail B takes the top's three back, the right side takes the pin
    # hole's sketch, and the front view's import then brings only the length
    # (r743-6: front first, its deletions and a native detail left detail A
    # nothing). The isometrics carry no dimensions.
    annotations: list[Any] = []
    views = {}
    keeps = {
        DETAIL_A.name: DETAIL_A_KEEP,
        DETAIL_B.name: DETAIL_B_KEEP,
        TOP_SIDE.name: TOP_SIDE_KEEP,
    }
    for spec in CROPPED_VIEWS:
        view = _placed_cropped_view(adapter, spec)
        if spec.orientation == "*Right":
            set_hidden_lines_removed(adapter, view)
        if spec.name in keeps:
            annotations += _dimension_then_crop(adapter, view, spec, keeps[spec.name])
        else:
            _crop_view(adapter, view, spec)
        views[spec.name] = view
    annotations += curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Decimal places (and so the band each dimension claims) are authored on
    # the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    # Each mating feature names its mate where it is dimensioned (rule 4).
    set_dimension_callouts(
        adapter,
        annotations,
        {
            name: text
            for name, text in DIMENSION_CALLOUTS.items()
            if name in CALLOUTS_ABOVE
        },
        location="above",
    )
    set_dimension_callouts(
        adapter,
        annotations,
        {
            name: text
            for name, text in DIMENSION_CALLOUTS.items()
            if name not in CALLOUTS_ABOVE
        },
        location="below",
    )
    for annotation in annotations:
        name = dimension_name(adapter, _early_bound(annotation, "IAnnotation"))
        if name in REFERENCE_DIMENSIONS:
            set_reference_dimension(adapter, annotation, label=f"{name} reference")

    # The circles and labels go on once every import is done, so nothing of
    # the front view's own sketch is near its import.
    sheet = _early_bound(
        _early_bound(adapter.currentModel, "IDrawingDoc").GetCurrentSheet(), "ISheet"
    )
    if not sheet.SetScale(*SHEET_SCALE, False, False):
        raise RuntimeError("failed to pin sheet scale before labelling the views")
    for spec in CROPPED_VIEWS:
        _label_view(adapter, views[spec.name], spec)
        if spec.letter is not None:
            mark = _mark_detail_on_front(adapter, front, spec)
            _letter_detail(adapter, front, spec, mark)
    _add_view_arrow(adapter, views[DETAIL_B.name])

    add_surface_finish(
        adapter,
        views[DETAIL_A.name],
        edge_entity=_notch_floor_edge(views[DETAIL_A.name]),
        symbol_xy=FLOOR_FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "bottom_notch_floor"),
        label="bottom notch floor finish",
        leader_attach_xy=FLOOR_FINISH_ATTACH,
        char_height=FINISH_CHAR_HEIGHT,
    )
    # The pin hole's matched-fit note belongs to the sheet, not a view.
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not ddoc.ActivateSheet(sheet.GetName()):
        raise RuntimeError("failed to activate the sheet for the notes")
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)

    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Amplitude Bar Manufacturing Drawing",
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
