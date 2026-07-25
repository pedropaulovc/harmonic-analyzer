r"""Create the curated machinist drawing for the pen marker.

A turned revolve (barrel + conical tip) whose model axis runs +Y, so the
profile view is ROTATED 90 deg on the sheet to the lathe convention (axis
horizontal, tip left).  The barrel diameter and overall length live on the
silhouette as drawing-native picked dimensions (the revolve's sketch chain
only carries radius / partial-length dims); the tip-cone height is the one
marked model dimension.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_feature_control_frame,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from pen_marker_spec import BARREL_DIA, BARREL_TOP_Y, CONE_H
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    place_view,
    set_view_position,
    view_name,
    view_outline,
)


SPEC = DRAWINGS_BY_NAME["pen_marker"]
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
FRONT_CENTER = (0.150, 0.180)
ISO_CENTER = (0.330, 0.190)

# Sheet-space geometry of the rotated profile (model +Y -> sheet -X: tip on
# the LEFT, barrel top face on the RIGHT), all in meters at the 2:1 view scale.
_HALF_LEN = BARREL_TOP_Y * SHEET_SCALE[0] / 2000.0
_HALF_DIA = BARREL_DIA * SHEET_SCALE[0] / 2000.0
APEX = (FRONT_CENTER[0] - _HALF_LEN, FRONT_CENTER[1])
CONE_BASE_X = APEX[0] + CONE_H * SHEET_SCALE[0] / 1000.0
END_FACE = (FRONT_CENTER[0] + _HALF_LEN, FRONT_CENTER[1])
BARREL_TOP_EDGE = (FRONT_CENTER[0] + 0.035, FRONT_CENTER[1] + _HALF_DIA)
BARREL_BOTTOM_EDGE = (FRONT_CENTER[0] + 0.035, FRONT_CENTER[1] - _HALF_DIA)
CONE_FLANK = (
    (APEX[0] + CONE_BASE_X) / 2.0,
    FRONT_CENTER[1] + _HALF_DIA / 2.0,
)

FRONT_KEEP = frozenset({"ConeH"})


def _rotate_view(adapter: Any, view: Any, angle: float, *, label: str) -> None:
    """Rotate a placed drawing view about its center (``IView.Angle``, radians)."""
    adapter._attempt(lambda: setattr(view, "Angle", float(angle)))
    applied = float(adapter._get_attr_or_call(view, "Angle") or 0.0)
    if abs(applied - float(angle)) > 1e-9:
        raise RuntimeError(
            f"failed to rotate {label} view to {angle:g} rad (reads {applied:g})"
        )


def _add_picked_dimension(
    adapter: Any,
    view: Any,
    *,
    picks: tuple[tuple[str, tuple[float, float]], ...],
    text_xy: tuple[float, float],
    label: str,
) -> Any:
    """Dimension across explicit typed picks (EDGE/VERTEX) at sheet points.

    ``_drawing_common.add_edge_dimension`` only picks edges; the revolve's tip
    apex is a VERTEX, so the overall length needs a mixed-type pick.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")  # IDrawingDoc view for drawing-only methods (same dispatch)
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate drawing view {name!r}")
    draw.ClearSelection2(True)
    for index, (entity_type, (x, y)) in enumerate(picks):
        selected = draw.Extension.SelectByID2(
            "", entity_type, x, y, 0.0, index > 0, 0, null_callout(), 0
        )
        if not selected:
            raise RuntimeError(
                f"failed to select {label} {entity_type.lower()} {index} at "
                f"sheet ({x:g}, {y:g})"
            )
    dimension = draw.AddDimension2(text_xy[0], text_xy[1], 0.0)
    draw.ClearSelection2(True)
    if dimension is None:
        raise RuntimeError(f"failed to add the {label} dimension")
    return dimension


def _display_as_diameter(adapter: Any, dimension: Any, *, label: str) -> None:
    """Prefix a silhouette-width dimension with the ASME diameter symbol."""
    display = _sw_type_info.early_bound_or_flag(
        dimension, "IDisplayDimension", "SetText", "GetText"
    )
    adapter._attempt(lambda: display.SetText(1, "<MOD-DIAM>"))  # swDimensionTextPrefix
    applied = str(adapter._attempt(lambda: display.GetText(1)) or "")
    if "<MOD-DIAM>" not in applied:
        raise RuntimeError(f"{label} dimension did not take the diameter prefix")


def _add_axis_centerline(adapter: Any, view: Any, *, label: str) -> Any:
    """Insert the turned-part axis centerline between the barrel silhouettes."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")  # IDrawingDoc view for drawing-only methods (same dispatch)
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate drawing view {name!r}")
    draw.ClearSelection2(True)
    for index, (x, y) in enumerate((BARREL_TOP_EDGE, BARREL_BOTTOM_EDGE)):
        selected = draw.Extension.SelectByID2(
            "", "SILHOUETTE", x, y, 0.0, index > 0, 0, null_callout(), 0
        )
        if not selected:
            raise RuntimeError(
                f"failed to select {label} silhouette edge {index} at "
                f"sheet ({x:g}, {y:g})"
            )
    centerline = ddoc.InsertCenterLine2()
    draw.ClearSelection2(True)
    if centerline is None:
        raise RuntimeError(f"failed to insert the {label} axis centerline")
    return centerline


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pen-marker source", await adapter.open_model(str(SOURCE)))
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
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
            0: "Pen Marker Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pen marker; marking pen; turned brass",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    # Lathe convention: axis horizontal. Model +Y (the pen axis) points up in
    # *Front; -90 deg turns it to +X so the tip apex lands on the LEFT. The
    # rotation does not pivot about the geometry center, so re-pin the center
    # afterwards -- every sheet coordinate below assumes it.
    _rotate_view(adapter, front, -math.pi / 2.0, label="pen-marker profile")
    if not set_view_position(adapter, front, *FRONT_CENTER):
        raise RuntimeError("failed to re-center the rotated pen-marker profile")
    _telemetry.info(
        f"pen-marker profile outline after rotate: {view_outline(adapter, front)}"
    )

    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    _add_axis_centerline(adapter, front, label="pen-marker")

    _add_picked_dimension(
        adapter,
        front,
        picks=(("VERTEX", APEX), ("EDGE", END_FACE)),
        text_xy=(FRONT_CENTER[0], FRONT_CENTER[1] + 0.042),
        label="overall length",
    )
    barrel_dia = _add_picked_dimension(
        adapter,
        front,
        picks=(
            ("SILHOUETTE", BARREL_TOP_EDGE),
            ("SILHOUETTE", BARREL_BOTTOM_EDGE),
        ),
        text_xy=(END_FACE[0] + 0.030, FRONT_CENTER[1]),
        label="barrel diameter",
    )
    _display_as_diameter(adapter, barrel_dia, label="barrel diameter")

    add_datum_feature(
        adapter,
        front,
        edge_xy=BARREL_BOTTOM_EDGE,
        symbol_xy=(BARREL_BOTTOM_EDGE[0], FRONT_CENTER[1] - 0.026),
        datum="A",
        label="pen-marker barrel axis",
        entity_type="SILHOUETTE",
    )
    # frame_xy is the frame's TOP-LEFT corner and the box grows RIGHT from it:
    # measured, the anchor (APEX[0]-0.014 = 0.076) rendered the box at
    # x 0.0759..0.1012, y 0.2062..0.2121 -- 25.3 mm wide. The overall-length
    # dimension below picks the apex VERTEX, so its left extension line rises at
    # exactly APEX[0] = 0.090, which fell 14 mm INSIDE that box and struck out
    # the "0.10" tolerance cell. (The 60.00 is a GRAY reference dimension, so a
    # crop thresholded at 128 cannot see the line at all -- only the render or a
    # 200-threshold crop shows it.)
    #
    # -0.032 puts the box at 0.058..0.0833: its right edge clears APEX[0] by
    # 6.7 mm, and it lands in empty sheet (the only ink measured in
    # x 0.030..0.076, y 0.204..0.214 was the box's own left border). It may NOT
    # go right instead: the Ra body's ink starts at x=0.1119, so a box left-
    # anchored past the extension line would end at 0.1173 and run 5.4 mm into
    # it -- the "x<=0.111" bound noted below is real and tight. The leader now
    # crosses the gray extension line on its way to the cone flank, which is
    # ordinary ASME routing; a struck-out tolerance value is not.
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=CONE_FLANK,
        frame_xy=(APEX[0] - 0.032, FRONT_CENTER[1] + 0.032),
        characteristic="circular_runout",
        tolerance="0.10",
        datums=("A",),
        label="marker tip runout",
        entity_type="SILHOUETTE",
    )
    # In the band ABOVE the barrel, between the barrel top (0.188) and the 60.00
    # dimension line (~0.221) -- NOT above that dimension, where an early pass
    # ran the leader through the 60.00 text and struck it out.
    #
    # The leader leaves the anchor at the symbol's ▽ tip and the ▽ opens UPWARD,
    # so a leader that has to CLIMB to its target is drawn through the glyph (or
    # along its flank) unless it escapes sideways faster than the ▽'s ~1.8 flank
    # slope. Anchoring to the TOP silhouette instead makes the leader run DOWN
    # and away from the body entirely, so it stays short and unambiguous. The
    # body draws up and RIGHT of the anchor (~x+0.039, y+0.019), which fixes the
    # 0.196 ceiling here and keeps it clear of the tip-runout frame at x<=0.111.
    add_surface_finish(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0] - 0.024, FRONT_CENTER[1] + _HALF_DIA),
        symbol_xy=(FRONT_CENTER[0] - 0.016, 0.196),
        roughness_ra="1.6",
        label="barrel bearing finish",
        entity_type="SILHOUETTE",
    )

    # x=0.020: the anchor is the text's left edge, so the ink starts here. The
    # sheet's 0.0127 zone margin and the re-centred border rule (~0.0126) now
    # agree, so 0.020 clears the rule and the audit enforces the same bound.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.100)
    add_property_linked_note(adapter, "Isometric View Note", 0.305, 0.135)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pen Marker Manufacturing Drawing",
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
