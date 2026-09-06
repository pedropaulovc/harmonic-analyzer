r"""Create the curated machinist drawing for the pen marker.

A turned revolve (barrel + conical tip) whose model axis runs +Y, so the
profile view is ROTATED 90 deg on the sheet to the lathe convention (axis
horizontal, tip left). Model entities anchor the native overall length and
end-view diameter (the revolve's sketch chain only carries radius / partial-
length dims); the tip-cone height is the one marked model dimension.
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
    add_entity_dimension,
    add_feature_control_frame,
    add_property_linked_note,
    add_surface_finish,
    add_view_centerline,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_entities import CircleEdge, ModelEntities, ModelVertex
from _drawing_registry import DRAWINGS_BY_NAME
from _gtol_spec import ConeFace, CylinderFace
from _surface_finish import surface_finish_by_key
from pen_marker_spec import BARREL_DIA, BARREL_TOP_Y, CONE_H, SURFACE_FINISHES
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
END_CENTER = (0.330, 0.100)
ENTITY_ROLES = {
    "apex": ModelVertex((0.0, 0.0, 0.0)),
    "end": CircleEdge(BARREL_DIA / 2, (0.0, BARREL_TOP_Y, 0.0), (0, 1, 0)),
    "barrel": CylinderFace(BARREL_DIA),
    "tip": ConeFace(math.degrees(math.atan((BARREL_DIA / 2) / CONE_H))),
}

# Sheet-space layout of the rotated profile (model +Y -> sheet +X: tip on
# the LEFT, barrel top face on the RIGHT), all in meters at the 2:1 view scale.
_HALF_LEN = BARREL_TOP_Y * SHEET_SCALE[0] / 2000.0
APEX = (FRONT_CENTER[0] - _HALF_LEN, FRONT_CENTER[1])

FRONT_KEEP = {
    "ConeH": (APEX[0] + 0.005, FRONT_CENTER[1] - 0.030),
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


def _add_barrel_diameter(
    adapter: Any,
    view: Any,
    *,
    edge: Any,
    text_xy: tuple[float, float],
    label: str,
) -> Any:
    """Create a true diameter dimension on the model rim in its end view."""
    draw = adapter.currentModel
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate drawing view {name!r}")
    draw.ClearSelection2(True)
    if edge is None or not view.SelectEntity(edge, False):
        raise RuntimeError(f"failed to select model rim for {label}")
    dimension = draw.AddDiameterDimension2(text_xy[0], text_xy[1], 0.0)
    draw.ClearSelection2(True)
    if dimension is None:
        raise RuntimeError(f"failed to add the {label} dimension")
    draw.EditRebuild3()
    return dimension


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
    end = place_view(adapter, str(SOURCE), "*Top", *END_CENTER, scale=(2, 1))
    for view in (front, iso, end):
        set_hidden_lines_removed(adapter, view)
    # Lathe convention: axis horizontal. Model +Y (the pen axis) points up in
    # *Front; -90 deg turns it to +X so the tip apex lands on the LEFT. The
    # rotation does not pivot about the geometry center, so re-pin the center
    # afterwards for layout; entity identity does not depend on that position.
    _rotate_view(adapter, front, -math.pi / 2.0, label="pen-marker profile")
    if not set_view_position(adapter, front, *FRONT_CENTER):
        raise RuntimeError("failed to re-center the rotated pen-marker profile")
    _telemetry.info(
        f"pen-marker profile outline after rotate: {view_outline(adapter, front)}"
    )

    entities = ModelEntities(front.ReferencedDocument).resolve(ENTITY_ROLES)
    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    add_view_centerline(adapter, front, entity=entities["barrel"], label="pen-marker")

    add_entity_dimension(
        adapter,
        front,
        entities=(entities["apex"], entities["end"]),
        text_xy=(FRONT_CENTER[0], FRONT_CENTER[1] + 0.042),
        label="overall length",
        orientation="horizontal",
    )
    _add_barrel_diameter(
        adapter,
        end,
        edge=entities["end"],
        text_xy=(END_CENTER[0] + 0.030, END_CENTER[1]),
        label="barrel diameter",
    )

    add_datum_feature(
        adapter,
        front,
        entity=entities["barrel"],
        datum="A",
        label="pen-marker barrel axis",
        entity_type="FACE",
    )
    add_feature_control_frame(
        adapter,
        front,
        entity=entities["tip"],
        characteristic="circular_runout",
        tolerance=GEOMETRIC_TOLERANCES_MM["marker tip runout"],
        datums=("A",),
        label="marker tip runout",
        entity_type="FACE",
    )
    add_surface_finish(
        adapter,
        front,
        entity=entities["barrel"],
        control=surface_finish_by_key(SURFACE_FINISHES, "barrel"),
        label="barrel bearing finish",
        entity_type="FACE",
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
