r"""Create the curated drawing for the project-authored pen marker silhouette.

The model axis runs +Y, so the profile view is rotated 90 degrees on the sheet
with the writing point at left.  Overall length and maximum diameter are
drawing-native picked dimensions; the narrow felt-point reach is the one
marked model dimension.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from pen_marker_spec import GEOMETRIC_TOLERANCES_MM

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
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from pen_marker_spec import (
    BARREL_FLARE_Y,
    MAX_DIAMETER,
    OVERALL_LENGTH,
    SHOULDER_DIAMETER,
    SHOULDER_Y,
    SURFACE_FINISHES,
    TIP_NECK_DIAMETER,
    TIP_POINT_DIAMETER,
    TIP_POINT_Y,
    TIP_NECK_Y,
)
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

# Sheet-space geometry of the rotated profile (model +Y -> sheet +X), all in
# meters at the 2:1 view scale.
_AXIAL_SCALE = SHEET_SCALE[0] / 1000.0
_RADIAL_SCALE = SHEET_SCALE[0] / 1000.0
_HALF_LEN = OVERALL_LENGTH * _AXIAL_SCALE / 2.0
_HALF_DIA = MAX_DIAMETER * _RADIAL_SCALE / 2.0
APEX = (FRONT_CENTER[0] - _HALF_LEN, FRONT_CENTER[1])
TIP_NECK_X = APEX[0] + TIP_NECK_Y * _AXIAL_SCALE
END_POINT = (FRONT_CENTER[0] + _HALF_LEN, FRONT_CENTER[1])
BARREL_FLARE_X = APEX[0] + BARREL_FLARE_Y * _AXIAL_SCALE
BARREL_MAX_TOP = (BARREL_FLARE_X, FRONT_CENTER[1] + _HALF_DIA)
_FLARE_PICK_Y = (SHOULDER_Y + BARREL_FLARE_Y) / 2.0
_FLARE_PICK_RADIUS = (SHOULDER_DIAMETER + MAX_DIAMETER) / 4.0
_FLARE_PICK_X = APEX[0] + _FLARE_PICK_Y * _AXIAL_SCALE
BARREL_TOP_EDGE = (
    _FLARE_PICK_X,
    FRONT_CENTER[1] + _FLARE_PICK_RADIUS * _RADIAL_SCALE,
)
BARREL_BOTTOM_EDGE = (
    _FLARE_PICK_X,
    FRONT_CENTER[1] - _FLARE_PICK_RADIUS * _RADIAL_SCALE,
)
_TIP_PICK_Y = (TIP_POINT_Y + TIP_NECK_Y) / 2.0
_TIP_PICK_RADIUS = (TIP_POINT_DIAMETER + TIP_NECK_DIAMETER) / 4.0
TIP_FLANK = (
    APEX[0] + _TIP_PICK_Y * _AXIAL_SCALE,
    FRONT_CENTER[1] + _TIP_PICK_RADIUS * _RADIAL_SCALE,
)

FRONT_KEEP = {
    "TipPointY": (APEX[0] + 0.005, FRONT_CENTER[1] - 0.030),
}


def _rotate_view(adapter: Any, view: Any, angle: float, *, label: str) -> None:
    """Rotate a placed drawing view about its center (``IView.Angle``, radians)."""
    adapter._attempt(lambda: setattr(view, "Angle", float(angle)))
    applied = float(adapter._get_attr_or_call(view, "Angle") or 0.0)
    if abs(applied - float(angle)) > 1e-9:
        raise RuntimeError(
            f"failed to rotate {label} view to {angle:g} rad (reads {applied:g})"
        )
    adapter.currentModel.EditRebuild3()


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
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
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
    draw.EditRebuild3()
    if dimension is None:
        raise RuntimeError(f"failed to add the {label} dimension")
    return dimension


def _display_as_diameter(adapter: Any, dimension: Any, *, label: str) -> None:
    """Force a one-edge circular dimension to display as a true diameter."""
    display = _sw_type_info.early_bound_or_flag(
        dimension, "IDisplayDimension", "SetText", "GetText"
    )
    # A circular edge can initially produce a radial display dimension.  The
    # Diametric flag doubles the measured radius; the prefix supplies the ASME
    # diameter glyph explicitly, matching the other turned-profile drawings.
    adapter._attempt(lambda: setattr(display, "Diametric", True))
    adapter._attempt(lambda: display.SetText(1, "<MOD-DIAM>"))  # swDimensionTextPrefix
    applied = str(adapter._attempt(lambda: display.GetText(1)) or "")
    if "<MOD-DIAM>" not in applied:
        raise RuntimeError(f"{label} dimension did not take the diameter prefix")
    adapter.currentModel.EditRebuild3()


def _add_axis_centerline(adapter: Any, view: Any, *, label: str) -> Any:
    """Insert the turned-part axis centerline between the barrel silhouettes."""
    draw = adapter.currentModel
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
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
    draw.EditRebuild3()
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
            3: "pen marker; regular fine point; project-authored revolved profile",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)
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
        picks=(("VERTEX", APEX), ("VERTEX", END_POINT)),
        text_xy=(FRONT_CENTER[0], FRONT_CENTER[1] + 0.042),
        label="overall length",
    )
    maximum_dia = _add_picked_dimension(
        adapter,
        front,
        picks=(("EDGE", BARREL_MAX_TOP),),
        text_xy=(END_POINT[0] + 0.030, FRONT_CENTER[1]),
        label="maximum barrel diameter",
    )
    _display_as_diameter(adapter, maximum_dia, label="maximum barrel diameter")

    add_datum_feature(
        adapter,
        front,
        edge_xy=BARREL_BOTTOM_EDGE,
        symbol_xy=(BARREL_BOTTOM_EDGE[0], FRONT_CENTER[1] - 0.026),
        datum="A",
        label="pen-marker barrel axis",
        entity_type="SILHOUETTE",
    )
    # Route the tip-runout frame above and just behind the narrow holder neck.
    # Keeping it on the body side of the writing point avoids the sheet border
    # now that the full 123.11 mm envelope occupies most of the profile view.
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=TIP_FLANK,
        frame_xy=(TIP_NECK_X + 0.010, FRONT_CENTER[1] + 0.032),
        characteristic="circular_runout",
        tolerance=GEOMETRIC_TOLERANCES_MM["marker tip runout"],
        datums=("A",),
        label="marker tip runout",
        entity_type="SILHOUETTE",
    )
    # Anchor the finish to a stable point on the gently sloped barrel face,
    # clear of the sharp maximum-diameter station vertex.
    add_surface_finish(
        adapter,
        front,
        edge_xy=BARREL_TOP_EDGE,
        symbol_xy=(BARREL_TOP_EDGE[0] + 0.008, 0.196),
        control=surface_finish_by_key(SURFACE_FINISHES, "barrel"),
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
