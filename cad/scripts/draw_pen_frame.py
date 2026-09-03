r"""Create the curated machinist drawing for the pen frame (stirrup yoke).

The SLDPRT remains authoritative.  This recipe supplies only the frame's views,
the outer + window dimensions, the set-screw hole callout and stations, and the
machining note; every shared sheet/template, import, curation, and export
behavior lives in ``_drawing_common``.

The pen frame is a brass yoke: a flat 26 x 40 rectangular ring, 10 thick, with a
window (4-wide side rails, 5-wide end rails), the platen-side edge trimmed back
0.75, and a #4-40 set-screw tapped up through the bottom rail.  It is small, so
the sheet runs 2:1; the isometric stays 1:1.  The RIGHT view carries the
frame's thickness (a real outline width, the stock size); the BOTTOM view
(looking up at the bottom rail, where the tapped hole is a visible circle)
carries the hole's native callout and its two stations from the trimmed left
face and the front face -- never dimensioned to the front view's hidden lines
(cad/docs/drawing-simplicity-policy.md rule 7).

Run with SolidWorks open::

    uv run python cad\scripts\draw_pen_frame.py pen-frame
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_native_hole_callout,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    find_edge_near,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_center,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _holes import TAP_DRILL_MM
from build_pen_frame import FRAME_DEPTH, OUTER_HEIGHT, OUTER_WIDTH, TRIM_NEAR
from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view


SPEC = DRAWINGS_BY_NAME["pen_frame"]
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

SHEET_SCALE = (2.0, 1.0)   # 2:1 whole sheet (small 26 x 40 ring)
VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]  # 2.0 sheet-mm per model-mm

# Sheet layout (meters).  The front ring face is the main view; the right
# view sits beside it, the bottom view under it (third angle), the isometric
# (1:1) to the far right.  The outer envelope dims frame the front view
# (width above, height left); the bottom view's stations sit left/below it.
FRONT_CENTER = (0.115, 0.165)
RIGHT_CENTER = (0.220, 0.165)
BOTTOM_CENTER = (0.115, 0.088)
ISO_CENTER = (0.325, 0.175)

FRONT_KEEP = {
    "OuterHeightDim": (
        FRONT_CENTER[0] - OUTER_WIDTH * VIEW_SCALE / 2000.0 - 0.016,
        FRONT_CENTER[1],
    ),
    "OuterSpanX": (
        FRONT_CENTER[0],
        FRONT_CENTER[1] + OUTER_HEIGHT * VIEW_SCALE / 2000.0 + 0.014,
    ),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
BOTTOM_KEEP: dict[str, tuple[float, float]] = {}

# The set-screw hole (model mm): mid-width, mid-depth, tapped up the bottom
# rail.  Its stations read from the TRIMMED left face (the one the machinist
# has) and the front face.
SCREW_X = OUTER_WIDTH / 2.0
SCREW_Z = FRAME_DEPTH / 2.0
SCREW_DRILL_R = TAP_DRILL_MM["#4-40"] / 2.0
SCREW_STATION_X = SCREW_X - TRIM_NEAR  # 12.25
# The one process fact the native callout does not state: the tap pierces
# the bottom rail only (THROUGH NEXT stops at the window), written as the
# callout's prefix so it is read with the size (policy rule 6).
SET_SCREW_PROCESS = "TAP THRU THE BOTTOM RAIL ONLY:"


def _model_frame(adapter: Any, view: Any, *, scale: float, label: str):
    """Model-mm -> sheet projection for ``view`` plus the sheet unit vectors of
    model +X/+Y/+Z, read from the view's own transform so no sign is guessed.
    The projected length of a 10 mm model step is checked against ``scale``
    so a transform that omitted the view scale fails loud instead of
    mis-picking."""

    def at(x_mm: float, y_mm: float, z_mm: float) -> tuple[float, float]:
        return model_point_in_view(
            adapter, view, (x_mm / 1000.0, y_mm / 1000.0, z_mm / 1000.0),
            label=f"{label} pick",
        )

    origin = at(0.0, 0.0, 0.0)
    units: list[tuple[float, float]] = []
    for axis in ((10.0, 0.0, 0.0), (0.0, 10.0, 0.0), (0.0, 0.0, 10.0)):
        point = at(*axis)
        dx, dy = point[0] - origin[0], point[1] - origin[1]
        norm = math.hypot(dx, dy)
        if norm < 1e-6:  # the axis normal to the view
            units.append((0.0, 0.0))
            continue
        if abs(norm - 0.010 * scale) > 0.0002 * scale:
            raise RuntimeError(
                f"{label}: a 10 mm model step projects to {norm * 1000:.2f} mm on "
                f"the sheet; expected {10.0 * scale:.2f} mm at {scale:g}:1"
            )
        units.append((dx / norm, dy / norm))
    return at, tuple(units)


def _offset(
    point: tuple[float, float], direction: tuple[float, float], distance: float
) -> tuple[float, float]:
    return (point[0] + direction[0] * distance, point[1] + direction[1] * distance)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pen-frame source", await adapter.open_model(str(SOURCE)))
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
            "Front View Note",
            "Right View Note",
            "Bottom View Note",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Front View Note",
            "Right View Note",
            "Bottom View Note",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pen Frame Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pen frame; brass stirrup yoke; set-screw rail",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    bottom = place_view(adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    set_hidden_lines_removed(adapter, iso)
    # Hidden lines ON in every orthographic view: the front and right views
    # show the set-screw thread path up the bottom rail into the window.
    for view in (front, right, bottom):
        set_hidden_lines_visible(adapter, view)

    # The front view claims the envelope marks; the other views keep none.
    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right")
    curate_view_dimensions(adapter, bottom, keep=BOTTOM_KEEP, view_label="bottom")
    if not auto_center_marks(adapter, bottom, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the set-screw hole")

    # Frame thickness (10): across the right view's two outline edges (the
    # right rail's front/back faces), picked mid-window so no hidden window
    # line is under the cursor; text above the view.
    at_right, (_rx, right_y, _rz) = _model_frame(
        adapter, right, scale=VIEW_SCALE, label="right view"
    )
    add_edge_dimension(
        adapter,
        right,
        p0=find_edge_near(
            adapter, right, at_right(OUTER_WIDTH, OUTER_HEIGHT / 2.0, 0.0),
            axis="x", label="frame front face",
        ),
        p1=find_edge_near(
            adapter, right, at_right(OUTER_WIDTH, OUTER_HEIGHT / 2.0, FRAME_DEPTH),
            axis="x", label="frame back face",
        ),
        text_xy=_offset(at_right(OUTER_WIDTH, OUTER_HEIGHT, SCREW_Z), right_y, 0.014),
        label="frame thickness",
        orientation="horizontal",
    )

    # Set-screw hole on the bottom view, where it is a visible circle: the
    # native #4-40 callout (prefix: the rail it pierces) and its two stations,
    # each re-anchored to the arc CENTRE so the value locates the axis.
    at_bottom, (bottom_x, _by, bottom_z) = _model_frame(
        adapter, bottom, scale=VIEW_SCALE, label="bottom view"
    )
    screw_rim = find_edge_near(
        adapter, bottom, at_bottom(SCREW_X, 0.0, SCREW_Z - SCREW_DRILL_R),
        axis="y", label="set-screw hole rim",
    )
    # 12.25 from the trimmed left face, text below the view.
    width_station = add_edge_dimension(
        adapter,
        bottom,
        p0=find_edge_near(
            adapter, bottom, at_bottom(TRIM_NEAR, 0.0, SCREW_Z * 0.6),
            axis="x", label="frame trimmed left face",
        ),
        p1=screw_rim,
        text_xy=_offset(
            at_bottom((TRIM_NEAR + SCREW_X) / 2.0, 0.0, 0.0), bottom_z, -0.014
        ),
        label="set-screw width station",
        orientation="horizontal",
    )
    set_arc_endpoints_to_center(adapter, width_station, label="set-screw width station")
    # 5.00 from the front face (mid-depth), text left of the view.
    depth_station = add_edge_dimension(
        adapter,
        bottom,
        p0=find_edge_near(
            adapter, bottom, at_bottom(OUTER_WIDTH * 0.3, 0.0, 0.0),
            axis="y", label="frame front face edge",
        ),
        p1=screw_rim,
        text_xy=_offset(at_bottom(TRIM_NEAR, 0.0, SCREW_Z / 2.0), bottom_x, -0.012),
        label="set-screw depth station",
        orientation="vertical",
    )
    set_arc_endpoints_to_center(adapter, depth_station, label="set-screw depth station")
    add_native_hole_callout(
        adapter,
        bottom,
        edge_xy=screw_rim,
        callout_xy=_offset(at_bottom(OUTER_WIDTH, 0.0, SCREW_Z), bottom_x, 0.016),
        label="set-screw tap",
        process=SET_SCREW_PROCESS,
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.016, 0.040)
    add_property_linked_note(adapter, "Front View Note", 0.094, 0.112)
    add_property_linked_note(adapter, "Right View Note", 0.196, 0.112)
    add_property_linked_note(adapter, "Bottom View Note", 0.092, 0.052)
    add_property_linked_note(adapter, "Isometric View Note", 0.288, 0.096)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pen Frame Manufacturing Drawing",
        scale=SHEET_SCALE,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
