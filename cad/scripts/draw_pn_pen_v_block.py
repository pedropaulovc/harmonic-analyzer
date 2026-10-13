r"""Create the curated machinist drawing for the pen v-block.

The SLDPRT remains authoritative.  This recipe supplies only the v-block's
views, the placement of its imported model dimensions, the two native hole
callouts and the isometric's scale note; sheet/template and export behavior
lives in ``_drawing_common``.  Dimension import and curation live in
``_drawing_dimension_import``; places and the pivot band are authored on the
part (``pn_pen_v_block_spec``).

The views follow the part frame (x 0 the paper end, z 0 the front face):

* front: ``*Back`` looks at the z 0 face the set screw enters, so the paper
  end is on the RIGHT.  It carries the chamfered outline and the tap's two
  coordinates, the tap's native callout, and section A-A's cutting line on
  the pivot-bore axis.
* right (third angle, right of the ``*Back`` face): ``*Left``, the paper end,
  shows the V in solid lines -- apex height, angle, and the block depth.
* bottom: ``*Bottom`` turned 180 degrees to keep the front view's X, looking
  up into the V and the relief; through the relief the roof shows both
  vertical bores.  It carries the V's length, the relief width, the pivot
  bore (station and reamed, banded diameter) and the lightening bore's
  station with its native callout.
* section A-A through the pivot-bore axis: bore, tap and relief in one cut;
  it carries the relief height.

No datums, frames, basic dimensions or roughness (drawing-simplicity-policy.md
rules 5 and 6), no note block: material and finish ride the title block.  The
sheet runs 4:1; the isometric stays 1:1.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pn_pen_v_block.py pn-pen-v-block
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view

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
from _drawing_dimension_import import curate_view_dimensions, import_cosmetic_threads
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_edges import scan_view_edges
from _drawing_hole_callout import add_native_hole_callout
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _hole_spec import TAP_DRILL_MM
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from pn_pen_v_block_spec import (
    BLOCK_DEPTH,
    BLOCK_HEIGHT,
    BLOCK_LENGTH,
    CHAMFER,
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    LIGHTENING_DIA,
    LIGHTENING_X,
    PIVOT_BORE_X,
    RELIEF_HEIGHT,
    RELIEF_X0,
    SET_SCREW_TAP_SPEC,
    SET_SCREW_Y,
    V_APEX_Y,
)


SPEC = DRAWINGS_BY_NAME["pn_pen_v_block"]
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

SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
ISO_SCALE = (1, 1)
_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0  # sheet metres per model mm

# Sheet layout (meters).  At 4:1 the 36 x 18 x 18 block is 144 x 72 mm in the
# front and bottom views and 72 x 72 in the end view and the section.  The
# front (x 0.040..0.184, y 0.156..0.228) stacks over the bottom view (y
# 0.054..0.126), both left of the title block (x 0.216); the end view
# (x 0.219..0.291) and section A-A (x 0.324..0.396) share the front's row; the
# isometric sits over the title block.
FRONT_CENTER = (0.112, 0.192)
BOTTOM_CENTER = (FRONT_CENTER[0], 0.090)
RIGHT_CENTER = (0.255, FRONT_CENTER[1])
SECTION_CENTER = (0.360, FRONT_CENTER[1])
ISO_CENTER = (0.375, 0.105)
ISO_NOTE_XY = (0.350, 0.074)
TAP_CALLOUT_XY = (0.235, 0.252)
LIGHTENING_CALLOUT_XY = (0.060, 0.140)
# Section A-A's cutting line: the pivot-bore axis (x = PIVOT_BORE_X), 1.5 mm
# past the bottom and top faces, so the cut closes across the whole block.
SECTION_LINE_MODEL_MM = (
    (PIVOT_BORE_X, -1.5, 0.0),
    (PIVOT_BORE_X, BLOCK_HEIGHT + 1.5, 0.0),
)

_CX, _CY, _CZ = BLOCK_LENGTH / 2.0, BLOCK_HEIGHT / 2.0, BLOCK_DEPTH / 2.0
_TAP_DRILL_R = TAP_DRILL_MM[SET_SCREW_TAP_SPEC.size] / 2.0


def _fx(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front (``*Back``) and bottom views:
    both run model +X to the sheet's left (the paper end on the right)."""
    return FRONT_CENTER[0] - (model_x_mm - _CX) * _S


def _fy(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - _CY) * _S


def _bz(model_z_mm: float) -> float:
    """Sheet Y of a model-Z point in the turned bottom view: the front face
    (z 0) toward the front view above it."""
    return BOTTOM_CENTER[1] - (model_z_mm - _CZ) * _S


def _rz(model_z_mm: float) -> float:
    """Sheet X of a model-Z point in the paper-end view: z 0 on its left, next
    to the front view."""
    return RIGHT_CENTER[0] + (model_z_mm - _CZ) * _S


def _ry(model_y_mm: float) -> float:
    return RIGHT_CENTER[1] + (model_y_mm - _CY) * _S


# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.
# Front: overall length on top over the free-end chamfer leg, height left; the
# tap's coordinates from the paper-end/bottom corner sit right of and below the
# view, the station clear of section A-A's cutting-line end.
FRONT_KEEP = {
    "Length": (_fx(_CX), _fy(BLOCK_HEIGHT) + 0.028),
    "Chamfer2dx": (_fx(BLOCK_LENGTH - CHAMFER / 2.0), _fy(BLOCK_HEIGHT) + 0.012),
    "Height": (_fx(BLOCK_LENGTH) - 0.014, _fy(_CY)),
    "SetScrewY": (_fx(0.0) + 0.010, _fy(SET_SCREW_Y / 2.0)),
    "SetScrewX": (_fx(PIVOT_BORE_X / 4.0), _fy(0.0) - 0.012),
}
# Paper end: the depth under the view, the V's angle just under its mouth, the
# apex height right of the view.
RIGHT_KEEP = {
    "Depth": (RIGHT_CENTER[0], _ry(0.0) - 0.020),
    "VAngle": (RIGHT_CENTER[0], _ry(0.0) - 0.007),
    "VApexY": (_rz(BLOCK_DEPTH) + 0.012, _ry(V_APEX_Y / 2.0)),
}
# Bottom: the bore station above the view (the gap under the front view), the
# V length and lightening station stacked below, the relief width left, the
# reamed diameter right of the view.
BOTTOM_KEEP = {
    "PivotX": (_fx(PIVOT_BORE_X / 2.0), _bz(0.0) + 0.008),
    "VLength": (_fx(RELIEF_X0 / 2.0), _bz(BLOCK_DEPTH) - 0.012),
    "LighteningX": (_fx(LIGHTENING_X / 2.0), _bz(BLOCK_DEPTH) - 0.024),
    "ReliefWidth": (_fx(BLOCK_LENGTH) - 0.014, BOTTOM_CENTER[1]),
    "PivotDia": (_fx(0.0) + 0.016, _bz(0.0) - 0.008),
}
# Section A-A: the relief height right of the cut.
SECTION_KEEP = {
    "ReliefHeight": (
        SECTION_CENTER[0] + _CZ * _S + 0.012,
        SECTION_CENTER[1] + (RELIEF_HEIGHT / 2.0 - _CY) * _S,
    ),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pen-v-block source", await adapter.open_model(str(SOURCE)))
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pen V-Block Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pen v-block; brass; grip V, body relief, reamed pivot bore",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Back", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Left", *RIGHT_CENTER, scale=VIEW_SCALE)
    bottom = place_view(
        adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=VIEW_SCALE
    )
    _orient_bottom_view(adapter, bottom)
    line = [
        model_point_in_view(
            adapter,
            front,
            tuple(value / 1000.0 for value in point),
            label="section line",
        )
        for point in SECTION_LINE_MODEL_MM
    ]
    section = create_section_view(
        adapter,
        front,
        line_start=line[0],
        line_end=line[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="pivot bore and set-screw tap section",
    )
    # finalize_drawing shades the pictorial isometric with edges.
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, right, bottom, section):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        annotation
        for view, keep, label in (
            (front, FRONT_KEEP, "front"),
            (right, RIGHT_KEEP, "paper end"),
            (bottom, BOTTOM_KEEP, "bottom"),
            (section, SECTION_KEEP, "section A-A"),
        )
        for annotation in curate_view_dimensions(
            adapter,
            view,
            keep=keep,
            view_label=label,
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
    ]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    # Places (and the pivot band) are authored on the part; the sheet only
    # proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    for view, label in ((front, "front"), (bottom, "bottom")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to the {label} view")

    # Native Hole Wizard callouts on each hole's visible rim: the tap's mouth on
    # the front face, the lightening bore where it breaks through the relief roof.
    tap_rim = scan_view_edges(front, label="front").circle_at(
        (PIVOT_BORE_X, SET_SCREW_Y, 0.0),
        _TAP_DRILL_R,
        axis=(0.0, 0.0, 1.0),
        label="set-screw tap mouth",
    )
    add_native_hole_callout(
        adapter,
        front,
        edge=tap_rim.edge,
        callout_xy=TAP_CALLOUT_XY,
        label="rod set-screw tap into the pivot bore",
        process="TAP",
    )
    lightening_rim = scan_view_edges(bottom, label="bottom").circle_at(
        (LIGHTENING_X, RELIEF_HEIGHT, _CZ),
        LIGHTENING_DIA / 2.0,
        axis=(0.0, 1.0, 0.0),
        label="lightening bore at the relief roof",
    )
    add_native_hole_callout(
        adapter,
        bottom,
        edge=lightening_rim.edge,
        callout_xy=LIGHTENING_CALLOUT_XY,
        label="free-end lightening bore",
        process="DRILL",
    )

    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    # Materialize the iso's cosmetic thread before the strict final note cleanup;
    # otherwise its descriptive label first appears during the native drawing save.
    import_cosmetic_threads(adapter, iso)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pen V-Block Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        redundant_note_substrings=(f"{SET_SCREW_TAP_SPEC.size} Tapped Hole",),
        expected_redundant_notes=1,
    )


def _orient_bottom_view(adapter: Any, view: Any) -> None:
    """Make *Bottom the third-angle underside of the displayed *Back face."""
    native = _early_bound(view, "IView")
    native.Angle = math.pi
    rebuild_drawing(adapter, label="v-block underside orientation")
    applied = float(native.Angle)
    if (
        not math.isfinite(applied)
        or abs(math.remainder(applied - math.pi, math.tau)) > 1e-9
    ):
        raise RuntimeError(
            f"v-block underside rotation did not take: {applied!r} rad, expected pi"
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
