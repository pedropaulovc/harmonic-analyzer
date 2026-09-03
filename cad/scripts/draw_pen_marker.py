r"""Create the curated machinist drawing for the pen marker.

A turned revolve (barrel + conical tip) whose model axis runs +Y, so the
profile view is ROTATED 90 deg on the sheet to the lathe convention (axis
horizontal, tip left).  The barrel diameter and overall length live on the
silhouette as drawing-native picked dimensions (the revolve's sketch chain
only carries radius / partial-length dims); the tip-cone height is the one
marked model dimension.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): the
marker is clamped in the v-block groove, so it carries no datum, frame or
roughness symbol; the title block's general tolerances govern.  The tip
allowance is a leader note on the apex, so the two dimensions that end there
are read as running to the theoretical sharp.
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
    add_attached_note,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from pen_marker_spec import BARREL_DIA, BARREL_TOP_Y, CONE_H, TIP_NOTE
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
END_FACE = (FRONT_CENTER[0] + _HALF_LEN, FRONT_CENTER[1])
BARREL_TOP_EDGE = (FRONT_CENTER[0] + 0.035, FRONT_CENTER[1] + _HALF_DIA)
BARREL_BOTTOM_EDGE = (FRONT_CENTER[0] + 0.035, FRONT_CENTER[1] - _HALF_DIA)

# The tip-cone height sits ABOVE the barrel (between the silhouette and the
# 110.00 lane), text offset right of its short span, so the region under the
# apex stays clear for the tip-flat leader note.
FRONT_KEEP = {
    "ConeH": (APEX[0] + 0.016, FRONT_CENTER[1] + 0.030),
}
# Tip-flat note anchored under the apex; its leader rises straight to the
# apex vertex with nothing between (the 5.00 lane is above the barrel).
TIP_NOTE_XY = (0.020, 0.145)


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
    """Prefix a silhouette-width dimension with the ASME diameter symbol."""
    display = _sw_type_info.early_bound_or_flag(
        dimension, "IDisplayDimension", "SetText", "GetText"
    )
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
            3: "pen marker; marking pen; turned brass",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    set_hidden_lines_removed(adapter, iso)
    set_hidden_lines_visible(adapter, front)
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

    # The tip allowance flagged from the view (policy rule 6): the leader lands
    # on the apex vertex the 110.00 and 5.00 both run to.
    add_attached_note(
        adapter,
        front,
        text=TIP_NOTE,
        entity_xy=APEX,
        note_xy=TIP_NOTE_XY,
        label="tip flat allowance",
        entity_type="VERTEX",
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
