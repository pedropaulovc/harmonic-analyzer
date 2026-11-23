r"""Create the curated machinist drawing for the pen frame (stirrup).

The SLDPRT remains authoritative.  This recipe supplies only the frame's views,
the dimension layout and the tapped-hole callout; sheet/template and export
behavior lives in ``_drawing_common``.  Dimension import and curation live in
``_drawing_dimension_import``.

The pen frame is a flat rectangular brass ring with a centred, corner-filleted
window and a #4-40 thumb-screw hole tapped up through the bottom rail.  Every
size is a native associative dimension marked on the part
(``pn_pen_frame_spec``): the front view carries the outer envelope, the
window's size and its lower-left corner from the left and bottom faces (the
window corners print no radius: the title block governs); the bottom view,
looking up at the tapped rail, carries the depth, the hole's two coordinates
from the outer faces (the .16 stating the far wall it sets, WALL .074 MIN),
and the hole's native Hole Wizard callout.  No datums, no
frames (drawing-guidelines.md rule 5), no note block.  The sheet runs 2:1 in
decimal inch (the part's ``drawing_unit: in``); the isometric stays 2:1, so
only the pictorial carries a caption, without a scale (rule 9).

Run with SolidWorks open::

    uv run python cad\scripts\draw_pn_pen_frame.py pn-pen-frame
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
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
    offset_dimension_text,
    set_dimension_callouts,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_edges import scan_view_edges
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _part_properties import part_drawing_unit
from _printed_limits import drilled_limits, limits
from _drawing_view_display import set_hidden_lines_removed
from _hole_callout_thread_class import omit_title_block_thread_class
from _hole_spec import blind_cut_dia_mm
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from pn_pen_frame_spec import (
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FRAME_DEPTH,
    ISOMETRIC_VIEW_NOTE,
    OUTER_HEIGHT,
    OUTER_WIDTH,
    RAIL_BOTTOM,
    RAIL_SIDE,
    SET_SCREW_TAP_SPEC,
    TAP_WALL_CALLOUT,
    TAP_WALL_MIN_MM,
    UNIT,
    WINDOW_CORNER_R,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pn_pen_frame"]
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

SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]  # sheet-mm per model-mm

# Sheet layout (meters).  Third angle: the bottom view projects straight
# below the front view (model X shared); the isometric rides to the right.
# Both orthographic views are bbox-centred: the front on the 25 x 40 ring face
# (x 0.090..0.140, y 0.145..0.225), the bottom on the 25 x 8 underside
# (x 0.090..0.140, y 0.097..0.113), whose centre IS the tapped hole's axis.
FRONT_CENTER = (0.115, 0.185)
BOTTOM_CENTER = (0.115, 0.105)
# The pictorial runs 2:1 like the sheet: at 1:1 the 2.26 tap mouth and the
# window fillets read as polygons and banded shading (machinist review r1).
# A true isometric of the 25 x 40 x 8 ring spans (25 + 8) cos 45 = 23.5 wide
# and 40 x 0.816 + (25 + 8) x 0.408 = 46.4 tall, so at 2:1 about 47 x 93 mm:
# centred at (0.320, 0.180) it fills x 0.297..0.343, y 0.134..0.226, clear of
# the front view's 40.0 dimension (x 0.173), its note (ends ~x 0.23), the top
# border (0.267) and the title block (top 0.065).
ISO_SCALE = (2, 1)
ISO_CENTER = (0.320, 0.180)
ISO_HALF_EXTENT = (
    (OUTER_WIDTH + FRAME_DEPTH) * 0.7071 * ISO_SCALE[0] / ISO_SCALE[1] / 2000.0,
    (OUTER_HEIGHT * 0.8165 + (OUTER_WIDTH + FRAME_DEPTH) * 0.4082)
    * ISO_SCALE[0]
    / ISO_SCALE[1]
    / 2000.0,
)


def _front_xy(model_x_mm: float, model_y_mm: float) -> tuple[float, float]:
    """Sheet point of a model (x, y) in the front view (bbox-centred)."""
    return (
        FRONT_CENTER[0] + (model_x_mm - OUTER_WIDTH / 2.0) * VIEW_SCALE / 1000.0,
        FRONT_CENTER[1] + (model_y_mm - OUTER_HEIGHT / 2.0) * VIEW_SCALE / 1000.0,
    )


def _bottom_xy(model_x_mm: float, model_z_mm: float) -> tuple[float, float]:
    """Sheet point of a model (x, z) in the bottom view: model X across, model
    +Z up (the face nearer the front view's viewer stands nearer it)."""
    return (
        BOTTOM_CENTER[0] + (model_x_mm - OUTER_WIDTH / 2.0) * VIEW_SCALE / 1000.0,
        BOTTOM_CENTER[1] + (model_z_mm - FRAME_DEPTH / 2.0) * VIEW_SCALE / 1000.0,
    )


FRONT_LEFT_X, FRONT_BOTTOM_Y = _front_xy(0.0, 0.0)
FRONT_RIGHT_X, FRONT_TOP_Y = _front_xy(OUTER_WIDTH, OUTER_HEIGHT)
BOTTOM_LEFT_X, BOTTOM_LOW_Y = _bottom_xy(0.0, 0.0)
BOTTOM_RIGHT_X, BOTTOM_HIGH_Y = _bottom_xy(OUTER_WIDTH, FRAME_DEPTH)
HOLE_CENTER_MM = (OUTER_WIDTH / 2.0, 0.0, FRAME_DEPTH / 2.0)
HOLE_SHEET_XY = _bottom_xy(HOLE_CENTER_MM[0], HOLE_CENTER_MM[2])
HOLE_R_SHEET = blind_cut_dia_mm(SET_SCREW_TAP_SPEC) * VIEW_SCALE / 2000.0
# Per-view survivors of the marked-dimension import: parametric name -> sheet
# text position.  Front view (ring x 0.090..0.140, y 0.145..0.225; window
# x 0.096..0.134, y 0.157..0.214):
# - The 28.0 width rides above, alone: no other dimension leaves the top.
# - The window corner's two location dims and its two sizes all leave from
#   the window's left and bottom edges (build_pn_pen_frame's chain order), so
#   they stack left and below, each smaller one nearer the ring: the 28.0
#   window height 10 mm left (its text 4.5 mm off the left face), the 6.00
#   bottom wall 24 mm left with its text between its own extension lines; the
#   20.00 window width 8 mm below, the 4.00 left wall 17 mm below with its
#   text outboard left as before.  Each pair shares the extension line from
#   the window's bottom-left corner, so neither crosses the other's
#   dimension line.
# - The 1.58 height stands 30 mm right of the ring.
# - The window corners' 4X R.065 rides up-right of the ring, clear of the
#   1.00 above and the 1.58's line, its leader to the top-right corner (the
#   fillet's first edge, build_pn_pen_frame).
FRONT_KEEP = {
    "OuterSpanX": (FRONT_CENTER[0], FRONT_TOP_Y + 0.014),
    "OuterHeightDim": (FRONT_RIGHT_X + 0.030, FRONT_CENTER[1]),
    "WindowHeight": (FRONT_LEFT_X - 0.010, FRONT_CENTER[1]),
    "BottomWall": (FRONT_LEFT_X - 0.024, _front_xy(0.0, RAIL_BOTTOM / 2.0)[1]),
    "WindowWidth": (FRONT_CENTER[0], FRONT_BOTTOM_Y - 0.008),
    "LeftWall": (FRONT_LEFT_X - 0.012, FRONT_BOTTOM_Y - 0.017),
    "WindowCornerR": (FRONT_RIGHT_X + 0.045, FRONT_TOP_Y + 0.020),
}
# Bottom view: the hole's X coordinate below, its Z coordinate left, the depth
# right; the hole callout stands above-right, between the bottom view and the
# front view's height dimension.
BOTTOM_KEEP = {
    "ScrewX": (_bottom_xy(OUTER_WIDTH / 4.0, 0.0)[0], BOTTOM_LOW_Y - 0.010),
    "ScrewZ": (BOTTOM_LEFT_X - 0.010, _bottom_xy(0.0, FRAME_DEPTH / 4.0)[1]),
    "Depth": (BOTTOM_RIGHT_X + 0.016, BOTTOM_CENTER[1]),
}
# The .16's 8 mm run cannot hold its two rows (.16 over WALL .074 MIN, ~36 mm
# wide): centred on its line the wall row would cross both extension lines.
# Native OffsetText parks the text on a leader left of where the extension
# lines end (line x - 0.001), its right edge ~5 mm clear of them; the anchor
# is the value row's bottom centre.
SCREW_Z_TEXT_XY = (BOTTOM_LEFT_X - 0.034, BOTTOM_KEEP["ScrewZ"][1])
_TEXT_SETTLE_M = 0.0005
_CENTER_MARK_ANNOTATION = 13  # swAnnotationType_e.swCenterMarkSym
HOLE_CALLOUT_XY = (0.165, 0.128)
# The through-next tap's drill diameter prints .XXX, under whichever
# drill-size variable the native callout carries (_tap_drill_variable).
TAP_DRILL_PLACES = 3
_TAP_DRILL_VARIABLES = ("hw-tapdrldia", "hw-thrutapdrldia")
_CALLOUT_DEFINITION_PARTS = (5, 6, 7, 8)  # swDimensionTextParts_e definitions

# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what this sheet prints, beside the constants of the
# code that prints it, in the part frame (pn_pen_frame_spec: the ring in XY,
# origin the bottom-left outer corner of the sketch face, width +X, height +Y,
# depth +Z; the window centred in X). Every size and station prints .XX
# (DRAWING_PRECISION_BY_NAME), the tap drill the DRILLED HOLES row at
# TAP_DRILL_PLACES; the window's corners print 4X R.065 at .XXX (owner
# ruling 2026-11-23, tool audit Q9). The declarations print nothing.
_P = DRAWING_PRECISION_BY_NAME
_SELF = "draw_pn_pen_frame"
_FRAME = "__frame__"
_TAP_DRILL = blind_cut_dia_mm(SET_SCREW_TAP_SPEC)
_SCREW_AT = (OUTER_WIDTH / 2.0, 0.0, FRAME_DEPTH / 2.0)


def _plane(axis: str, value: float) -> dict[str, Any]:
    return {"frame": "model", "axis": axis, "value": value}


def _band(name: str, model: float, sources: tuple) -> tuple[list[float], tuple]:
    return limits(model, _P[name], unit=UNIT), (
        *sources,
        "UNIT",
        "DRAWING_PRECISION_BY_NAME",
    )


part_metadata(
    model_sources=("OUTER_WIDTH", "OUTER_HEIGHT", "FRAME_DEPTH"),
    precision_sources=(
        "DRAWING_PRECISION",
        "DRAWING_PRECISION_BY_NAME",
        (_SELF, "TAP_DRILL_PLACES"),
    ),
)
# The three faces the print locates from: the left (LeftWall, ScrewX), the
# bottom (BottomWall, the tap's entry) and the sketch face (ScrewZ, Depth).
for _name, _normal, _axis in (
    ("left_face", (-1.0, 0.0, 0.0), "x"),
    ("bottom_face", (0.0, -1.0, 0.0), "y"),
    ("front_face", (0.0, 0.0, -1.0), "z"),
):
    requirement(
        _name,
        kind="face",
        faces=(PlanarFace(_normal, 0.0),),
        requirements=("plane",),
        fields={"plane": (_plane(_axis, 0.0), (_FRAME,))},
    )
# The outer width 1.00 (FRONT_KEEP OuterSpanX), height 1.58 (OuterHeightDim)
# and depth .31 (BOTTOM_KEEP Depth), each from its opposite face.
for _name, _normal, _axis, _value, _key, _dim, _source, _from, _keep in (
    (
        "right_face",
        (1.0, 0.0, 0.0),
        "x",
        OUTER_WIDTH,
        "width",
        "OuterSpanX",
        "OUTER_WIDTH",
        "left_face",
        "FRONT_KEEP",
    ),
    (
        "top_face",
        (0.0, 1.0, 0.0),
        "y",
        OUTER_HEIGHT,
        "height",
        "OuterHeightDim",
        "OUTER_HEIGHT",
        "bottom_face",
        "FRONT_KEEP",
    ),
    (
        "back_face",
        (0.0, 0.0, 1.0),
        "z",
        FRAME_DEPTH,
        "depth",
        "Depth",
        "FRAME_DEPTH",
        "front_face",
        "BOTTOM_KEEP",
    ),
):
    requirement(
        _name,
        kind="face",
        faces=(PlanarFace(_normal, _value),),
        requirements=(_key,),
        fields={
            "plane": (_plane(_axis, _value), (_source,)),
            _key: _band(_dim, _value, (_source, (_SELF, _keep))),
            f"{_key}_nominal": (_value, (_source,)),
            f"{_key}_from": (_from, ((_SELF, _keep),)),
        },
        precision={_key: _P[_dim]},
    )
# The window, through the depth: its width .74 and height 1.12, and its
# lower-left corner .13 from the left face and .24 from the bottom face
# (FRONT_KEEP). Its four walls and four corner rounds; the rounds print
# 4X R.065 (FRONT_KEEP WindowCornerR).
_WINDOW_X = (RAIL_SIDE, RAIL_SIDE + WINDOW_WIDTH)
_WINDOW_Y = (RAIL_BOTTOM, RAIL_BOTTOM + WINDOW_HEIGHT)
requirement(
    "window",
    kind="pocket",
    faces=(
        PlanarFace((1.0, 0.0, 0.0), _WINDOW_X[0]),
        PlanarFace((-1.0, 0.0, 0.0), -_WINDOW_X[1]),
        PlanarFace((0.0, 1.0, 0.0), _WINDOW_Y[0]),
        PlanarFace((0.0, -1.0, 0.0), -_WINDOW_Y[1]),
        *(
            CylinderFace(
                2.0 * WINDOW_CORNER_R,
                contains_x_mm=_x + _sx * 0.3 * WINDOW_CORNER_R,
                contains_y_mm=_y + _sy * 0.3 * WINDOW_CORNER_R,
            )
            for _x, _sx in ((_WINDOW_X[0], 1.0), (_WINDOW_X[1], -1.0))
            for _y, _sy in ((_WINDOW_Y[0], 1.0), (_WINDOW_Y[1], -1.0))
        ),
    ),
    requirements=("width", "height", "left_wall", "bottom_wall", "corner_r"),
    fields={
        "axis": ((0.0, 0.0, 1.0), (_FRAME,)),
        "thru": (True, ("FRAME_DEPTH", _FRAME)),
        "width": _band(
            "WindowWidth", WINDOW_WIDTH, ("WINDOW_WIDTH", (_SELF, "FRONT_KEEP"))
        ),
        "width_nominal": (WINDOW_WIDTH, ("WINDOW_WIDTH",)),
        "height": _band(
            "WindowHeight", WINDOW_HEIGHT, ("WINDOW_HEIGHT", (_SELF, "FRONT_KEEP"))
        ),
        "height_nominal": (WINDOW_HEIGHT, ("WINDOW_HEIGHT",)),
        "left_wall": _band("LeftWall", RAIL_SIDE, ("RAIL_SIDE", (_SELF, "FRONT_KEEP"))),
        "left_wall_nominal": (RAIL_SIDE, ("RAIL_SIDE",)),
        "left_wall_from": ("left_face", ((_SELF, "FRONT_KEEP"),)),
        "bottom_wall": _band(
            "BottomWall", RAIL_BOTTOM, ("RAIL_BOTTOM", (_SELF, "FRONT_KEEP"))
        ),
        "bottom_wall_nominal": (RAIL_BOTTOM, ("RAIL_BOTTOM",)),
        "bottom_wall_from": ("bottom_face", ((_SELF, "FRONT_KEEP"),)),
        "corner_r": _band(
            "WindowCornerR",
            WINDOW_CORNER_R,
            ("WINDOW_CORNER_R", (_SELF, "FRONT_KEEP")),
        ),
        "corner_r_nominal": (WINDOW_CORNER_R, ("WINDOW_CORNER_R",)),
        "corner_count": (4, ("DIMENSION_PREFIXES",)),
    },
    precision={
        "width": _P["WindowWidth"],
        "height": _P["WindowHeight"],
        "left_wall": _P["LeftWall"],
        "bottom_wall": _P["BottomWall"],
        "corner_r": _P["WindowCornerR"],
    },
)
# The thumb-screw tap up through the bottom rail into the window: one native
# callout (Ø.089 THRU, 4-40 UNC THRU), its station .50 from the left face and
# .16 from the sketch face, which states the far wall (WALL .074 MIN).
requirement(
    "thumb_screw_tap",
    kind="threaded_hole",
    faces=(CylinderFace(_TAP_DRILL, contains_y_mm=RAIL_BOTTOM / 2.0),),
    requirements=("thread", "dia", "thru", "station", "depth_station"),
    fields={
        "at": (list(_SCREW_AT), ("OUTER_WIDTH", "FRAME_DEPTH", _FRAME)),
        "axis": ((0.0, 1.0, 0.0), ("SET_SCREW_TAP_SPEC", _FRAME)),
        "thread": (
            f"{SET_SCREW_TAP_SPEC.size} UNC-2B",
            ("SET_SCREW_TAP_SPEC", (_SELF, "build")),
        ),
        "dia": (
            drilled_limits(_TAP_DRILL, TAP_DRILL_PLACES, unit=UNIT),
            ("SET_SCREW_TAP_SPEC", "UNIT", (_SELF, "TAP_DRILL_PLACES")),
        ),
        "nominal_dia": (_TAP_DRILL, ("SET_SCREW_TAP_SPEC",)),
        # THROUGH_NEXT: through the bottom rail, out into the window.
        "thru": (True, ("SET_SCREW_TAP_SPEC", (_SELF, "build"))),
        "breaks_into": ("window", ("SET_SCREW_TAP_SPEC",)),
        "station": _band(
            "ScrewX", _SCREW_AT[0], ("OUTER_WIDTH", (_SELF, "BOTTOM_KEEP"))
        ),
        "station_nominal": (_SCREW_AT[0], ("OUTER_WIDTH",)),
        "station_from": ("left_face", ((_SELF, "BOTTOM_KEEP"),)),
        "depth_station": _band(
            "ScrewZ", _SCREW_AT[2], ("FRAME_DEPTH", (_SELF, "BOTTOM_KEEP"))
        ),
        "depth_station_nominal": (_SCREW_AT[2], ("FRAME_DEPTH",)),
        "depth_station_from": ("front_face", ((_SELF, "BOTTOM_KEEP"),)),
        "wall_min": (TAP_WALL_MIN_MM, ("TAP_WALL_MIN_MM",)),
        "wall_note": (TAP_WALL_CALLOUT, ("TAP_WALL_CALLOUT", "DIMENSION_CALLOUTS")),
    },
    precision={
        "dia": TAP_DRILL_PLACES,
        "station": _P["ScrewX"],
        "depth_station": _P["ScrewZ"],
    },
)


def _tap_drill_variable(definitions: dict[int, str]) -> str:
    """The one native drill-size variable the callout carries."""
    text = "\n".join(definitions.values())
    found = [name for name in _TAP_DRILL_VARIABLES if f"<{name}>" in text]
    if len(found) != 1:
        raise RuntimeError(f"expected one tap drill-size variable: {definitions!r}")
    return found[0]


# The note's left end: its text (~2.5 mm a character) centres under the
# isometric, ~15 mm below the view's lowest corner (y 0.133).
ISO_VIEW_NOTE_XY = (ISO_CENTER[0] - len(ISOMETRIC_VIEW_NOTE) * 0.0025 / 2.0, 0.116)


def _offset_screw_z_text(adapter: Any, annotations: list[Any]) -> None:
    """Park the .16's text on its leader shelf and read it back."""
    offset_dimension_text(adapter, annotations, {"ScrewZ": SCREW_Z_TEXT_XY})
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        if dimension_name(adapter, annotation) != "ScrewZ":
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        position = annotation.GetPosition()
        if (
            not bool(display.OffsetText)
            or position is None
            or math.dist(position[:2], SCREW_Z_TEXT_XY) > _TEXT_SETTLE_M
        ):
            raise RuntimeError(
                f"ScrewZ text at {position!r}, not offset to {SCREW_Z_TEXT_XY!r}"
            )


def _center_mark_count(view: Any) -> int:
    """The view's centre-mark annotations (a bare view answers None)."""
    return len(
        _early_bound(view, "IView").GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ()
    )


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pen-frame source", adapter.open_model(str(SOURCE)))
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
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
            0: "Pen Frame Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pen frame; brass stirrup; #4-40 thumb-screw tap",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    bottom = place_view(adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # The tapped hole is fully defined by its callout (drawing-guidelines.md
    # rule 9): no view needs hidden lines.  finalize_drawing turns the
    # pictorial into precise Shaded With Edges (rule 8); at 2:1 its tap mouth
    # and window fillets read round rather than faceted.
    for view in (front, bottom, iso):
        set_hidden_lines_removed(adapter, view)

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
            bottom,
            keep=BOTTOM_KEEP,
            view_label="bottom",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    # Places are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    _offset_screw_z_text(adapter, annotations)

    # The template may centre-mark the tap as the view is placed: every round's
    # layout audit found two identical marks on it (duplicate-annotation, as
    # draw_pn_pen_rod, fleet issue #913).  Mark only a bare view, then prove
    # the tap carries exactly one.
    if _center_mark_count(bottom) == 0 and not auto_center_marks(
        adapter, bottom, holes=True, size=0.0025
    ):
        raise RuntimeError("failed to add ASME center marks to the bottom view")
    if (found := _center_mark_count(bottom)) != 1:
        raise RuntimeError(
            f"bottom view carries {found} centre marks, not the tap's one"
        )
    hole_rim = scan_view_edges(bottom, label="bottom").circle_at(
        HOLE_CENTER_MM,
        blind_cut_dia_mm(SET_SCREW_TAP_SPEC) / 2.0,
        axis=(0.0, 1.0, 0.0),
        label="thumb-screw tap mouth",
    )
    tap_callout = add_native_hole_callout(
        adapter,
        bottom,
        edge=hole_rim.edge,
        callout_xy=HOLE_CALLOUT_XY,
        label="thumb-screw tapped hole",
    )
    # Size first (drawing-guidelines.md rule 26): no process prefix, and the
    # title block's THREADS row owns the 2B class (rule 2), so the callout
    # reads 4-40 UNC THRU.
    omit_title_block_thread_class(tap_callout, label="thumb-screw tapped hole")
    native = _early_bound(tap_callout, "IDisplayDimension")
    drill_variable = _tap_drill_variable(
        {part: str(native.GetText(part) or "") for part in _CALLOUT_DEFINITION_PARTS}
    )
    set_hole_callout_precision(
        tap_callout, {drill_variable: TAP_DRILL_PLACES}, label="thumb-screw tapped hole"
    )

    add_property_linked_note(adapter, "Isometric View Note", *ISO_VIEW_NOTE_XY)

    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pen Frame Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # SolidWorks pins its own "#4-40 Tapped Hole" note to the bottom view
        # once the tap carries a hole callout; the callout already states the
        # thread, and the note sat under it with the callout's leader through
        # it (farm c0b95549c: merged-blocks + leader-through-text).
        redundant_note_substrings=("Tapped Hole",),
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
