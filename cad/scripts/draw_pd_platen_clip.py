r"""Create the curated machinist drawing for the platen clip (MHA-PD-003).

The clip is one 0.8 brass sheet, 83.5 long: a flat screw rail carrying the two
#2 loose screw holes, an open-ended slit from each end, and a spring rail
joined to the screw rail only at the centre bridge, formed into two shallow
bows that press the paper.  The sheet runs at 3:1: the plan (front view)
carries the blank (length, rail widths from the outer edge, bridge, corner
radii, hole stations), the profile (top view) above it the sheet and the bows'
stations and bend radius, and a 1:1 isometric the form.

Every printed dimension is an associative model dimension whose places the
part authors (``build_pd_platen_clip.DRAWING_PRECISION``); the hole size ships
as a native Hole Wizard callout.

Run (SolidWorks already open)::

    uv run python cad\scripts\draw_pd_platen_clip.py pd-platen-clip
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
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from build_pd_platen_clip import (
    BRIDGE_X0,
    CENTER_BRIDGE_LENGTH,
    CLIP_LENGTH,
    CLIP_WIDTH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HOLE_CALLOUT_PRECISION,
    HOLE_DIA,
    HOLE_INSET,
    HOLE_Y,
    SCREW_RAIL_SLIT_RADIUS,
    SCREW_RAIL_WIDTH,
    SPRING_RAIL_WIDTH,
    SPRING_RAIL_Y0,
)


SPEC = DRAWINGS_BY_NAME["pd_platen_clip"]
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
ISO_SCALE = (1, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0  # sheet m per model mm, 3:1

# Sheet layout (meters; the B-size field is x 0.0127..0.4191, y 0.0127..0.2667
# and the title block holds x >= 0.216, y <= 0.066).  The plan (250.5 x 34.1
# at 3:1) sits mid-sheet with its hole stations below and its bridge and
# length above; the profile, third-angle above it, carries its bow stations
# between the two; the isometric sits bottom-left, clear of the title block.
FRONT_CENTER = (0.200, 0.150)
TOP_CENTER = (0.200, 0.215)
ISO_CENTER = (0.090, 0.062)
ISO_NOTE_XY = (0.020, 0.032)


def _plan_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the plan or the profile (bbox-centred)."""
    return FRONT_CENTER[0] + (model_x_mm - CLIP_LENGTH / 2.0) * _S


def _plan_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the plan (bbox-centred)."""
    return FRONT_CENTER[1] + (model_y_mm - CLIP_WIDTH / 2.0) * _S


LEFT_EDGE_X = _plan_x(0.0)
RIGHT_EDGE_X = _plan_x(CLIP_LENGTH)
BOTTOM_EDGE_Y = _plan_y(0.0)
TOP_EDGE_Y = _plan_y(CLIP_WIDTH)
HOLE_FAR_X = CLIP_LENGTH - HOLE_INSET

# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.  Plan: the two hole stations stack below it from the near end, the
# bridge's start and length chain above it with the overall length outermost;
# left of it the hole row's height, the screw rail's width and the spring
# rail's start stand in their own columns from the outer edge (smallest
# nearest), the spring rail's width beside its own span; the outer and the
# slit-side corner radii off the right end.  Profile: the near bow's start and
# the far bow's end stack between it and the plan, the bend radius above the
# near bow, the sheet off the near end.
FRONT_KEEP = {
    "LeftX": (_plan_x(HOLE_INSET / 2.0), 0.125),
    "RightX": (_plan_x(HOLE_FAR_X / 2.0), 0.118),
    "BridgeX0": (_plan_x(BRIDGE_X0 / 2.0), 0.175),
    "BridgeLength": (_plan_x(BRIDGE_X0 + CENTER_BRIDGE_LENGTH / 2.0), 0.175),
    "Length": (FRONT_CENTER[0], 0.183),
    "LeftZ": (0.062, _plan_y(HOLE_Y / 2.0)),
    "RailWidth": (0.050, _plan_y(SCREW_RAIL_WIDTH * 0.75)),
    "StartOffset": (0.038, _plan_y(SPRING_RAIL_Y0 * 0.35)),
    "SpringRailWidth": (0.062, _plan_y(SPRING_RAIL_Y0 + SPRING_RAIL_WIDTH / 2.0)),
    "EndR1": (0.345, 0.122),
    "SlitCornerR1": (0.352, 0.164),
}
TOP_KEEP = {
    "BowStartX": (_plan_x(HOLE_INSET / 2.0), 0.204),
    "FarBowEndX": (_plan_x(HOLE_FAR_X / 2.0), 0.197),
    "BendR1": (0.100, 0.232),
    "SheetDepth": (0.060, 0.2125),
}
# The hole row's height stands for both holes; each printed radius for its
# equal set.  A custom prefix replaces SolidWorks' own radius "R", so it
# carries it.
DIMENSION_PREFIXES = {
    "LeftZ": "2X ",
    "EndR1": "2X R",
    "SlitCornerR1": "2X R",
    "BendR1": "6X R",
}

# The callout rides the far hole, its leader leaving the rim up-right over
# the clip's right end to text clear of the corner radii.
_DIAG = math.sqrt(0.5)
HOLE_R_SHEET = HOLE_DIA / 2.0 * _S
HOLE_EDGE_XY = (
    _plan_x(HOLE_FAR_X) + HOLE_R_SHEET * _DIAG,
    _plan_y(HOLE_Y) + HOLE_R_SHEET * _DIAG,
)
HOLE_CALLOUT_XY = (0.370, 0.142)
HOLE_CALLOUT_PROCESS = "DRILL"
# Where the slit-side corner radius lands (its leader target), for the layout
# tests: the screw rail's top-right corner.
SLIT_CORNER_XY = (
    _plan_x(CLIP_LENGTH - SCREW_RAIL_SLIT_RADIUS),
    _plan_y(SCREW_RAIL_WIDTH - SCREW_RAIL_SLIT_RADIUS),
)

_VIEW_KEEPS = {"front": FRONT_KEEP, "top": TOP_KEEP}
if set().union(*_VIEW_KEEPS.values()) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError(
        "the platen-clip views must keep exactly the marked dimensions"
    )


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


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open platen-clip source", await adapter.open_model(str(SOURCE)))
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
            0: "Platen Clip Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "platen clip; manufacturing drawing; sheet brass spring; #2 holes",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # The through holes are fully defined by their callout; the formed sheet
    # seen edge-on needs no hidden lines.
    for view in (front, top, iso):
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
            top,
            keep=TOP_KEEP,
            view_label="top",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _set_dimension_prefixes(adapter, annotations, DIMENSION_PREFIXES)

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    callout = add_native_hole_callout(
        adapter,
        front,
        edge_xy=HOLE_EDGE_XY,
        callout_xy=HOLE_CALLOUT_XY,
        label="platen-clip screw holes",
        process=HOLE_CALLOUT_PROCESS,
    )
    set_hole_callout_precision(
        callout, HOLE_CALLOUT_PRECISION, label="platen-clip screw holes"
    )
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Platen Clip Manufacturing Drawing",
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
