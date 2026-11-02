r"""Create the curated machinist drawing for the platen plate (MHA-PD-02).

The platen is a 10.62 x 5.31 brass plate, .152 thick, with four Ø.28 bosses
standing proud of its back face round the #2-56 clip-screw through taps and
ten counterbored #4 loose through holes for the guide screws.  The sheet
prints decimal inch (the part's ``drawing_unit: in``) and runs at 1:2: the
front view carries the outline, the bosses and every hole
coordinate from the plate's bottom-left corner, an enlarged 1:1 right view the
thickness on a native text shelf clear of its witnesses and the boss height,
a 4:1 partial section A-A through one
counterbore the user-accepted counterbore floor as a reference dimension with
its worst case, and a 1:4 isometric the form.  The counterbores' far side is
named in their callout.

Every printed dimension is an associative model dimension whose places the
part authors (``pd_platen_spec.DRAWING_PRECISION``); the hole sizes ship as
native Hole Wizard callouts.

Run (SolidWorks already open)::

    uv run python cad\scripts\draw_pd_platen.py pd-platen
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    place_view,
    visible_component_entities,
)

from _check import check
from _com import _early_bound
from _drawing_annotation_extent import (
    CLEAR_GAP_M,
    PLACE_SETTLE_M,
    callout_ink,
    move_annotation,
    require_inside,
    sheet_region,
)
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
    offset_dimension_text,
    set_dimension_callouts,
    set_reference_dimension,
)
import _drawing_hidden_sketches
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_leaders import dimension_segments
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _hole_callout_thread_class import omit_title_block_thread_class
from _hole_spec import blind_cut_dia_mm
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _section_axis import position_section_caption
from _session import run_build
import _telemetry
from pd_platen_spec import (
    CBORE_DEPTH,
    CBORE_FLOOR_CALLOUT,
    CBORE_SECTION_HOLE_Y,
    CBORE_SECTION_X,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    GUIDE_CALLOUT_PRECISION,
    GUIDE_HOLE_DIA,
    GUIDE_HOLE_X,
    GUIDE_HOLE_XY,
    GUIDE_HOLE_Y,
    PLATE_HEIGHT,
    PLATE_THICKNESS,
    PLATE_WIDTH,
    SOCKET_BOSS_H,
    SOCKET_SPEC,
    SOCKET_XY,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_platen"]
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

SHEET_SCALE = (1.0, 2.0)
VIEW_SCALE = (1, 2)
RIGHT_SCALE = (1, 1)
ISO_SCALE = (1, 4)
_S = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0  # sheet m per model mm, 1:2
_RIGHT_S = 1.0 / 1000.0  # enlarged right view, 1:1

# Sheet layout (meters; the B-size field is x 0.0127..0.4191, y 0.0127..0.2667
# and the title block holds x >= 0.216, y <= 0.066).  The front view's hole
# coordinates stack below it (smallest nearest) and at its sides; the enlarged
# right view and the isometric stand right of the front view, section A-A
# under the isometric, right of the right view's note: its floor reference
# below it, its caption between it and the isometric's note.
FRONT_CENTER = (0.140, 0.190)
RIGHT_CENTER = (0.300, 0.175)
ISO_CENTER = (0.370, 0.202)
ISO_NOTE_XY = (0.338, 0.168)
RIGHT_NOTE_XY = (0.262, 0.100)
# Section A-A: a partial cut down the top row's middle guide hole (x =
# CBORE_SECTION_X, its cutting plane the part's CBORE_SECTION_PLANE) from
# SECTION_SPAN below the hole's centre to as far above, at 2:1 (40 mm tall),
# +Y up.  The span sets the cutting-plane line's length on the 1:2 front
# view: at 4.5 (4.5 mm of line) its two arrows stood side by side and the
# lower A's apex sat in the upper A's legs (machinist review round 2); at 10
# the line runs 10 mm, each labelled end ~4 mm clear of the Ø.26 counterbore.
# The cut stays symmetric about the hole: run from 14.7 below to 5.3 above
# (to stop short of the clip-screw boss seen beyond), the section imported
# no CboreFloorReference sketch (farm fail8, round 4).
# The floor reference stands
# mid-annulus below the hole (pd_platen_spec), so its value hangs below the
# cut's lower end, where the dimension line runs under the text: the text
# stands LEFT of the extension lines, its right end at SECTION_TEXT_RIGHT
# (r5: centred on them, they ran down through all three of its rows); the
# native caption's top centre stands above the cut.
SECTION_SCALE = (2, 1)
_SECTION_S = SECTION_SCALE[0] / SECTION_SCALE[1] / 1000.0
SECTION_SPAN = 10.0
SECTION_CENTER = (0.390, 0.114)
SECTION_CAPTION_XY = (0.385, 0.157)
# The floor value's top row stands 14 mm of sheet under the cut's lower end.
_SECTION_TEXT_DROP_M = 0.014
# The value's widest row (".027 MIN WORST CASE", ~47 mm) ends 2.5
# short of the near extension line, the floor's counterbore face.
_SECTION_TEXT_HALF_WIDTH = 0.0245
SECTION_TEXT_RIGHT = (
    SECTION_CENTER[0] + (CBORE_DEPTH - PLATE_THICKNESS / 2.0) * _SECTION_S - 0.0025
)
# Model mm, in the cutting plane: the cut's ends, its centre (the hole's axis
# at mid-thickness) and the floor value's text, _SECTION_TEXT_DROP_M below
# the cut and left of the floor (model +Z is sheet +X in the cut).
SECTION_LINE_MODEL_MM = (
    (CBORE_SECTION_X, CBORE_SECTION_HOLE_Y - SECTION_SPAN, 0.0),
    (CBORE_SECTION_X, CBORE_SECTION_HOLE_Y + SECTION_SPAN, 0.0),
)
_SECTION_ANCHOR_MM = (CBORE_SECTION_X, CBORE_SECTION_HOLE_Y, PLATE_THICKNESS / 2.0)
SECTION_TEXT_MODEL_MM = {
    "CboreFloor": (
        CBORE_SECTION_X,
        CBORE_SECTION_HOLE_Y - SECTION_SPAN - _SECTION_TEXT_DROP_M / _SECTION_S,
        PLATE_THICKNESS / 2.0
        + (SECTION_TEXT_RIGHT - _SECTION_TEXT_HALF_WIDTH - SECTION_CENTER[0])
        / _SECTION_S,
    ),
}
# The right view's bbox spans the plate and the bosses behind it (model Z).
_DEPTH_SPAN = PLATE_THICKNESS + SOCKET_BOSS_H


def _front_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front view (bbox-centred)."""
    return FRONT_CENTER[0] + (model_x_mm - PLATE_WIDTH / 2.0) * _S


def _front_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the front view (bbox-centred)."""
    return FRONT_CENTER[1] + (model_y_mm - PLATE_HEIGHT / 2.0) * _S


def _right_x(model_z_mm: float) -> float:
    """Sheet X of a model-Z point in the right view (seen from +X: -Z right)."""
    return RIGHT_CENTER[0] - (model_z_mm - _DEPTH_SPAN / 2.0) * _RIGHT_S


def _right_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the enlarged right view."""
    return RIGHT_CENTER[1] + (model_y_mm - PLATE_HEIGHT / 2.0) * _RIGHT_S


LEFT_EDGE_X = _front_x(0.0)
RIGHT_EDGE_X = _front_x(PLATE_WIDTH)
BOTTOM_EDGE_Y = _front_y(0.0)
TOP_EDGE_Y = _front_y(PLATE_HEIGHT)
_SOCKET_LEFT_X, _SOCKET_RIGHT_X = sorted({x for x, _ in SOCKET_XY})
_SOCKET_LOW_Y, _SOCKET_HIGH_Y = sorted({y for _, y in SOCKET_XY})

# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.  Below the front view the X coordinates stack from the corner,
# smallest nearest, 7.5 mm apart: the left sockets' .170 and the first guide
# hole's 1.062 print outboard of the plate's left edge (their spans are
# narrower than the text), left of the bottom guide row's Y dimension so its
# outside arrow strikes neither; the rest mid-span, the overall width
# outermost.  The guide rows' Y coordinates stand left of the plate, each value
# on its own line clear of the other's; the sockets' Y coordinates and the
# height stand right of it.  The upper left boss carries the bosses' Ø up-left
# over the plate's corner.  The enlarged right view carries the plate's
# thickness above it and the boss height beside the lower boss (the dimension
# attaches there, so its extension lines stay on the boss); section A-A the
# counterbore floor (SECTION_TEXT_MODEL_MM, placed by projection once the cut
# stands).
_ROW_Y = (0.1485, 0.141, 0.1335, 0.126, 0.1185, 0.111, 0.1035, 0.096)
_OUTBOARD_X = 0.040
FRONT_KEEP = {
    "Socket3X": (_OUTBOARD_X, _ROW_Y[0]),
    "Guide1X": (_OUTBOARD_X, _ROW_Y[1]),
    "Guide2X": (_front_x(GUIDE_HOLE_X[1] / 2.0), _ROW_Y[2]),
    "Guide3X": (_front_x(GUIDE_HOLE_X[2] / 2.0), _ROW_Y[3]),
    "Guide4X": (_front_x(GUIDE_HOLE_X[3] / 2.0), _ROW_Y[4]),
    "Guide5X": (_front_x(GUIDE_HOLE_X[4] / 2.0), _ROW_Y[5]),
    "Socket1X": (_front_x(_SOCKET_RIGHT_X / 2.0), _ROW_Y[6]),
    "Width": (FRONT_CENTER[0], _ROW_Y[7]),
    "Guide1Y": (0.058, _front_y(GUIDE_HOLE_Y[0] / 2.0)),
    "Guide6Y": (0.030, _front_y(GUIDE_HOLE_Y[1] / 2.0)),
    "Socket1Y": (0.222, _front_y(_SOCKET_LOW_Y / 2.0)),
    "Socket2Y": (0.250, _front_y(_SOCKET_HIGH_Y * 0.68)),
    "Height": (0.272, FRONT_CENTER[1]),
    "Boss2Dia": (0.035, 0.238),
}
RIGHT_KEEP = {
    "Depth": (_right_x(PLATE_THICKNESS / 2.0), 0.251),
    "BossH": (0.284, _right_y(_SOCKET_LOW_Y)),
}
SECTION_KEEP_NAMES = frozenset(SECTION_TEXT_MODEL_MM)
# The thickness states what its .XXX is spent on (the air to the reducer
# disc, by number: r7 review); the floor is a reference dimension (the
# user-accepted exception) that also states its printed worst case
# (pd_platen_spec.CBORE_FLOOR_CALLOUT); the bosses say what they are.
DISC_NUMBER = "MHA-PD-06"
DIMENSION_CALLOUTS_ABOVE = {"Depth": f"SETS AIR TO {DISC_NUMBER} DISC"}
DIMENSION_CALLOUTS_BELOW = {
    "CboreFloor": CBORE_FLOOR_CALLOUT,  # pd-platen RV-02
    "Boss2Dia": "BOSS",
    "BossH": "TAP BOSS",
}
REFERENCE_DIMENSION = "CboreFloor"
# One printed coordinate stands for every hole on its station: 5X per guide
# row and column pair, 2X per socket station.  A custom prefix replaces
# SolidWorks' own diameter symbol, so the boss's carries it.
DIMENSION_PREFIXES = {
    "Socket1X": "2X ",
    "Socket3X": "2X ",
    "Socket1Y": "2X ",
    "Socket2Y": "2X ",
    "Guide1X": "2X ",
    "Guide2X": "2X ",
    "Guide3X": "2X ",
    "Guide4X": "2X ",
    "Guide5X": "2X ",
    "Guide1Y": "5X ",
    "Guide6Y": "5X ",
    "Boss2Dia": "4X Ø",
}

# The guide-hole callout rides the top row's first hole, its leader up to
# text above the plate's left half, right of the upper left boss; the socket
# callout rides the upper right socket's tap drill, its leader up to text above
# the plate's right end.  Both name the part whose pattern their .XXX
# coordinates match; the counterbores open on the far (paper) face, deep
# enough to sink the named guide screw's heads.
_GUIDE_PICK_HOLE = (GUIDE_HOLE_X[0], GUIDE_HOLE_Y[1])
_DIAG = math.sqrt(0.5)
GUIDE_EDGE_XY = (
    _front_x(_GUIDE_PICK_HOLE[0]) + GUIDE_HOLE_DIA / 2.0 * _S * _DIAG,
    _front_y(_GUIDE_PICK_HOLE[1]) + GUIDE_HOLE_DIA / 2.0 * _S * _DIAG,
)
GUIDE_CALLOUT_XY = (0.128, 0.248)
# Four rows at most (r4 tall-block): the drill, the far-side counterbore and
# the screw whose heads it sinks share one (r5 asked for the process word).
GUIDE_CALLOUT_PROCESS = (
    "PATTERN MATCHES MHA-PD-11\nDRILL, C'BORE FAR SIDE FOR MHA-SH-VN-51\n"
)
SOCKET_DRILL_DIA = blind_cut_dia_mm(SOCKET_SPEC)
SOCKET_DRILL_R_SHEET = SOCKET_DRILL_DIA / 2.0 * _S
SOCKET_EDGE_XY = (
    _front_x(_SOCKET_RIGHT_X) + SOCKET_DRILL_R_SHEET * _DIAG,
    _front_y(_SOCKET_HIGH_Y) + SOCKET_DRILL_R_SHEET * _DIAG,
)
SOCKET_CALLOUT_XY = (0.215, 0.252)
SOCKET_CALLOUT_PROCESS = "PATTERN MATCHES MHA-PD-03\nTAP"  # pd-platen RV-01
# The template centre-marks every hole as the view is placed (an explicit
# AutoInsertCenterMarks2 printed all 28 marks twice in r1); the front view
# proves exactly one mark per hole.
_CENTER_MARK_ANNOTATION = 13  # swAnnotationType_e.swCenterMarkSym
CENTER_MARKS_PER_VIEW = len(SOCKET_XY) + len(GUIDE_HOLE_XY)
# The socket's native callout drops one automatic "Tapped Hole" note.
REDUNDANT_NOTE = "Tapped Hole"

_VIEW_KEEPS = {
    "front": FRONT_KEEP,
    "right": RIGHT_KEEP,
    "section A-A": dict.fromkeys(SECTION_KEEP_NAMES),
}
if set().union(*_VIEW_KEEPS.values()) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("the platen views must keep exactly the marked dimensions")


def _set_dimension_prefixes(
    adapter: Any, annotations: list[Any], prefixes: dict[str, str]
) -> None:
    """Write a native prefix on named imported dimensions and read it back."""
    remaining = dict(prefixes)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        prefix = remaining.pop(dimension_name(adapter, annotation), None)
        if prefix is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.SetText(1, prefix)  # swDimensionTextPrefix
        if str(display.GetText(1) or "") != prefix:
            raise RuntimeError(f"dimension prefix {prefix!r} did not persist")
    if remaining:
        raise RuntimeError(f"dimension prefixes not applied: {sorted(remaining)}")


def _place_thickness_text(adapter: Any, annotations: list[Any]) -> None:
    """Keep the 3.850 line fixed and shelf its complete function/value block.

    The native review crop shows both witnesses striking the digits.  Offset
    only the text, then measure its full native shoulder rather than sizing
    the move from the number alone (the function row is much wider).
    """
    matches = [
        _early_bound(annotation, "IAnnotation")
        for annotation in annotations
        if dimension_name(adapter, annotation) == "Depth"
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one platen Depth dimension, found {len(matches)}")
    annotation = matches[0]
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if int(display.Type2) not in (2, 11, 12):
        raise RuntimeError("platen thickness is not a native linear dimension")
    rebuild_drawing(adapter, label="platen thickness function text")
    lines = dimension_segments(annotation)
    if not lines:
        raise RuntimeError("platen thickness has no native dimension lines")
    right = max(point[0] for line in lines for point in line)
    position = tuple(float(value) for value in annotation.GetPosition())
    # Seed beside the existing line and outside-arrow tail.  The native
    # shoulder then supplies the actual width of both rows for the final move.
    offset_dimension_text(adapter, [annotation], {"Depth": (right, position[1])})
    ink = callout_ink(adapter, annotation, label="platen thickness")
    dx = right + CLEAR_GAP_M + PLACE_SETTLE_M - ink.text[0]
    target = (right + dx, position[1])
    move_annotation(adapter, annotation, dx, 0.0, label="platen thickness text")
    ink = callout_ink(adapter, annotation, label="platen thickness")
    placed = tuple(float(value) for value in annotation.GetPosition())
    if not bool(display.OffsetText) or math.dist(placed[:2], target) > 1e-5:
        raise RuntimeError(f"platen thickness text offset did not persist: {placed}")
    if str(display.GetText(3) or "") != DIMENSION_CALLOUTS_ABOVE["Depth"]:
        raise RuntimeError("platen thickness lost its native function text")
    if ink.text[0] < right + CLEAR_GAP_M:
        raise RuntimeError(
            f"platen thickness text {ink.text} still crowds its native line at {right}"
        )
    require_inside("platen thickness text", ink.text, sheet_region(adapter))


def _socket_tap_edge(adapter: Any, view: Any) -> Any:
    """The upper right socket's tap-drill rim, found by its radius.

    A pick at SOCKET_EDGE_XY alone selected the Ø7 boss's rim at 1:2 (r2), so
    the callout printed the boss as a Ø7.00 x 1.70 "tap".  Of the front view's
    visible circles of the tap-drill radius, the one furthest up and right
    (*Front: model +X right, +Y up) is the upper right socket's.
    """
    radius_m = SOCKET_DRILL_DIA / 2000.0
    rims: list[tuple[float, Any]] = []
    for component in (
        adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    ):
        for raw in visible_component_entities(view, component, 1) or ():
            edge = _early_bound(raw, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            params = tuple(float(value) for value in curve.CircleParams)
            if abs(params[6] - radius_m) <= 1e-6:
                rims.append((params[0] + params[1], edge))
    if not rims:
        raise RuntimeError("platen front view shows no clip-screw tap-drill rim")
    return max(rims, key=lambda rim: rim[0])[1]


def _metres(point_mm: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(value / 1000.0 for value in point_mm)


def _orient_section(adapter: Any, section: Any) -> None:
    """Turn section A-A until model +Y runs up the sheet, as in the right view.

    Which way the cut looks along X only mirrors the symmetric counterbore,
    so the cut direction is left as SolidWorks takes it.
    """
    native = _early_bound(section, "IView")
    for attempt in range(3):
        origin = model_point_in_view(
            adapter, native, _metres(_SECTION_ANCHOR_MM), label="section A-A axis"
        )
        above = model_point_in_view(
            adapter,
            native,
            _metres(
                (
                    _SECTION_ANCHOR_MM[0],
                    _SECTION_ANCHOR_MM[1] + 1.0,
                    _SECTION_ANCHOR_MM[2],
                )
            ),
            label="section A-A +Y",
        )
        dx, dy = above[0] - origin[0], above[1] - origin[1]
        if dy > 0.0 and abs(dx) <= 1e-7:
            _telemetry.info(
                f"section A-A +Y up after {attempt} turn(s), "
                f"angle={float(native.Angle):.6f} rad"
            )
            return
        native.Angle = float(native.Angle) + math.pi / 2.0 - math.atan2(dy, dx)
        rebuild_drawing(adapter, label="platen section A-A turned")
    raise RuntimeError(f"section A-A does not run +Y up: ({dx:g}, {dy:g})")


def _centre_section(adapter: Any, section: Any) -> None:
    """Land the cut's centre (the hole's axis at mid-thickness) on
    SECTION_CENTER; a section's Position is its cut-plane origin, not its
    outline's centre (draw_pn_pen_v_block ``_centre_section``)."""
    native = _early_bound(section, "IView")
    for attempt in range(4):
        native.UpdateViewDisplayGeometry()
        projected = model_point_in_view(
            adapter,
            native,
            _metres(_SECTION_ANCHOR_MM),
            label=f"section A-A centre, pass {attempt}",
        )
        if math.dist(projected, SECTION_CENTER) <= 1e-4:
            return
        position = tuple(float(value) for value in native.Position)
        moved = [
            position[axis] + SECTION_CENTER[axis] - projected[axis] for axis in (0, 1)
        ]
        if not native.SetViewPosition(double_array(moved), False):
            raise RuntimeError("failed to re-centre platen section A-A")
        rebuild_drawing(adapter, label="platen section A-A re-centred")
    raise RuntimeError(
        f"section A-A centre stands at {projected}, not {SECTION_CENTER}"
    )


def _floor_section(adapter: Any, source_model: Any, front: Any) -> list[Any]:
    """Section A-A through one counterbore, carrying the floor reference.

    The floor's hidden owner sketch lies in the cutting plane; a derived view
    takes it from the part as it stands when cut and selects it through its
    base view, so the section is cut and curated while the part shows it
    (draw_pn_pen_v_block's recipe).  A section shows no hidden lines.
    """
    line = [
        model_point_in_view(adapter, front, _metres(point), label="section A-A line")
        for point in SECTION_LINE_MODEL_MM
    ]
    with _drawing_hidden_sketches.part_sketches_shown(
        adapter,
        source_model,
        ("CboreFloorReference",),
        label="section A-A floor reference",
        base_view=front,
    ):
        section = create_section_view(
            adapter,
            front,
            line_start=line[0],
            line_end=line[1],
            view_xy=SECTION_CENTER,
            section_label="A",
            scale=SECTION_SCALE,
            partial=True,
            label="counterbore floor section",
        )
        _orient_section(adapter, section)
        set_hidden_lines_removed(adapter, section)
        _centre_section(adapter, section)
        keep = {
            name: model_point_in_view(
                adapter, section, _metres(point), label=f"section A-A {name} text"
            )
            for name, point in SECTION_TEXT_MODEL_MM.items()
        }
        annotations = _drawing_hidden_sketches.curate_view_dimensions(
            adapter,
            section,
            keep=keep,
            view_label="section A-A",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
    position_section_caption(
        adapter, section, SECTION_CAPTION_XY, label="platen section A-A"
    )
    return annotations


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open platen source", await adapter.open_model(str(SOURCE)))
    source_model = adapter.currentModel
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
            "Right View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
            "Right View Note",
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
            0: "Platen Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "platen; manufacturing drawing; #2-56 taps; #4 counterbores",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=RIGHT_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # The holes are fully defined by their callouts and section A-A draws the
    # counterbore, so no view shows hidden lines (r4).
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    section_annotations = _floor_section(adapter, source_model, front)
    annotations = [*front_annotations, *right_annotations, *section_annotations]
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _set_dimension_prefixes(adapter, annotations, DIMENSION_PREFIXES)
    floor = [
        a
        for a in section_annotations
        if dimension_name(adapter, a) == REFERENCE_DIMENSION
    ]
    if len(floor) != 1:
        raise RuntimeError(
            f"expected one {REFERENCE_DIMENSION} dimension, found {len(floor)}"
        )
    set_reference_dimension(adapter, floor[0], label="counterbore floor")
    set_dimension_callouts(
        adapter, annotations, DIMENSION_CALLOUTS_ABOVE, location="above"
    )
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS_BELOW)
    _place_thickness_text(adapter, right_annotations)

    marks = (
        _early_bound(front, "IView").GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ()
    )
    if len(marks) != CENTER_MARKS_PER_VIEW:
        raise RuntimeError(
            f"expected {CENTER_MARKS_PER_VIEW} centre marks in the front view, "
            f"found {len(marks)}"
        )

    guide_callout = add_native_hole_callout(
        adapter,
        front,
        edge_xy=GUIDE_EDGE_XY,
        callout_xy=GUIDE_CALLOUT_XY,
        label="guide-screw counterbored holes",
        process=GUIDE_CALLOUT_PROCESS,
    )
    set_hole_callout_precision(
        guide_callout, GUIDE_CALLOUT_PRECISION, label="guide-screw counterbored holes"
    )
    socket_callout = add_native_hole_callout(
        adapter,
        front,
        edge_xy=SOCKET_EDGE_XY,
        edge=_socket_tap_edge(adapter, front),
        callout_xy=SOCKET_CALLOUT_XY,
        label="clip-screw through taps",
        process=SOCKET_CALLOUT_PROCESS,
    )
    # The title block's THREADS row owns the general thread class (r4).
    omit_title_block_thread_class(socket_callout, label="clip-screw through taps")
    set_hole_callout_precision(
        socket_callout, {"hw-thrutapdrldia": 3}, label="clip-screw through taps"
    )
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    add_property_linked_note(adapter, "Right View Note", *RIGHT_NOTE_XY)
    _telemetry.info("platen sheet: views, dimensions and callouts placed")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Platen Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        redundant_note_substrings=(REDUNDANT_NOTE,),
        expected_redundant_notes=1,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
