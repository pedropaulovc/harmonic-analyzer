r"""Create the curated machinist drawing for the pivot ball mount."""

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
    add_datum_feature,
    add_edge_dimension,
    add_feature_control_frame,
    add_property_linked_note,
    add_surface_finish,
    add_view_centerline,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_basic_dimension,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from pivot_ball_mount_spec import (
    BALL_CENTER_H,
    BALL_DIA,
    BASE_DIA,
    BASE_H,
    BORE_DIA,
    STEM_DIA,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pivot_ball_mount"]
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

SHEET_SCALE = (3.0, 1.0)  # small ~32 mm turned pillar -- 3:1 gives it presence
_S = SHEET_SCALE[0] / 1000.0  # sheet meters per model mm

# A turned/revolved part reads from one profile view; the cross-bore shows as a
# hidden circle there and the isometric shows the through-hole. Front elevation
# left of centre, isometric to the right.
_BALL_TOP_Y = BALL_CENTER_H + BALL_DIA / 2.0  # 31.7: seat 0 .. ball top
FRONT_CENTER = (0.110, 0.150)
ISO_CENTER = (0.320, 0.150)


def _front_y(model_y: float) -> float:
    """Sheet Y of a model-Y point in the front view (seat at model y=0)."""
    return FRONT_CENTER[1] + (model_y - _BALL_TOP_Y / 2.0) * _S


# The elevation carries the shared sphere/bore center height and bore diameter.
# The turned diameters use explicit leadered feature callouts below rather than
# displaying radial sketch dimensions as ambiguous pseudo-diameters.
FRONT_KEEP = {
    "BallRise": (FRONT_CENTER[0] - 0.050, _front_y(BALL_CENTER_H / 2.0)),
    "ShaftBoreDia": (FRONT_CENTER[0] + 0.052, _front_y(BALL_CENTER_H)),
}
# No second orthographic view carries dimensions; keep the test contract honest.
TOP_KEEP: dict[str, tuple[float, float]] = {}
DIMENSION_CALLOUTS = {
    "ShaftBoreDia": "+0.00/-0.05 THRU",
}
STEM_DIM_TEXT = (0.180, _front_y(12.0))


def _set_stem_dimension_format(adapter: Any, dimension: Any) -> None:
    """Render the drawing-native stem width as a toleranced diameter."""
    display = _early_bound(
        dimension,
        "IDisplayDimension",
        "SetText",
        "GetText",
        "GetDimension",
    )
    prefix = "<MOD-DIAM>"
    display.SetText(1, prefix)  # swDimensionTextPrefix
    if str(display.GetText(1) or "") != prefix:
        raise RuntimeError("stem diameter glyph did not persist")
    model_dimension = _early_bound(display.GetDimension(), "IDimension")
    tolerance = _early_bound(
        model_dimension.Tolerance,
        "IDimensionTolerance",
        "SetValues",
        "GetMinValue",
        "GetMaxValue",
    )
    tolerance.Type = 2  # swTolType_e.swTolBILAT
    limit_m = 0.05 / 1000.0
    if not tolerance.SetValues(-limit_m, limit_m):
        raise RuntimeError("stem diameter bilateral tolerance was rejected")
    if (
        abs(float(tolerance.GetMinValue()) + limit_m) > 1e-9
        or abs(float(tolerance.GetMaxValue()) - limit_m) > 1e-9
    ):
        raise RuntimeError("stem diameter bilateral tolerance did not persist")
    adapter.currentModel.EditRebuild3()


def _front_entities(adapter: Any, view: Any) -> tuple[Any, Any]:
    """Return real seat and cross-bore edges from the front view."""
    drawing_view = _early_bound(view, "IView")
    circles: list[tuple[float, float, Any]] = []
    for component in drawing_view.GetVisibleComponents() or []:
        for raw_edge in drawing_view.GetVisibleEntities2(component, 1) or []:
            edge = _early_bound(raw_edge, "IEdge")
            curve = edge.GetCurve()
            if curve is None:
                continue
            curve = _early_bound(curve, "ICurve")
            if not curve.IsCircle():
                continue
            params = tuple(float(value) * 1000.0 for value in curve.CircleParams)
            circles.append((params[6], params[1], edge))
    if not circles:
        raise RuntimeError("front view has no circular model edges")
    seat_radius, seat_height, seat_edge = min(
        circles,
        key=lambda item: abs(item[0] - BALL_DIA / 2.0) + abs(item[1]),
    )
    if abs(seat_radius - BALL_DIA / 2.0) > 0.01 or abs(seat_height) > 0.01:
        raise RuntimeError("no circular edge matches the seat face")
    radius, height, bore_edge = min(
        circles,
        key=lambda item: abs(item[0] - BORE_DIA / 2.0)
        + abs(item[1] - BALL_CENTER_H),
    )
    if abs(radius - BORE_DIA / 2.0) > 0.01 or abs(height - BALL_CENTER_H) > 0.01:
        raise RuntimeError(
            f"no circular edge matches cross-bore at {BALL_CENTER_H:.3f} mm"
        )
    return seat_edge, bore_edge


def _cylindrical_face(adapter: Any, view: Any, diameter_mm: float) -> Any:
    """Return the visible cylindrical face for one turned diameter."""
    drawing_view = _early_bound(view, "IView")
    candidates: list[tuple[float, Any]] = []
    for component in drawing_view.GetVisibleComponents() or []:
        for raw_face in drawing_view.GetVisibleEntities2(component, 3) or []:
            face = _early_bound(raw_face, "IFace2")
            surface = face.GetSurface()
            if surface is None:
                continue
            surface = _early_bound(surface, "ISurface")
            if not surface.IsCylinder():
                continue
            candidates.append((float(surface.CylinderParams[6]) * 1000.0, face))
    if not candidates:
        raise RuntimeError("front view has no visible cylindrical faces")
    target_radius = diameter_mm / 2.0
    radius, face = min(candidates, key=lambda item: abs(item[0] - target_radius))
    if abs(radius - target_radius) > 0.01:
        raise RuntimeError(
            f"no cylindrical face matches radius {target_radius:.4f} mm; "
            f"nearest is {radius:.4f} mm"
        )
    return face


def _ball_silhouette_xy(model_y: float) -> tuple[float, float]:
    """Exact right-hand sphere outline at one model-space ordinate."""
    radius = BALL_DIA / 2.0
    dy = model_y - BALL_CENTER_H
    if abs(dy) >= radius:
        raise ValueError(f"ball silhouette ordinate {model_y:g} is outside the sphere")
    model_x = math.sqrt(radius * radius - dy * dy)
    return (FRONT_CENTER[0] + model_x * _S, _front_y(model_y))


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pivot-ball-mount source", await adapter.open_model(str(SOURCE)))
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pivot Ball Mount Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pivot ball mount; turned steel ball pillar; cross-bore",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(3, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(3, 1))
    set_hidden_lines_removed(adapter, iso)
    # The elevation carries the cross-bore as a hidden circle through the ball.
    set_hidden_lines_visible(adapter, front)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    front_by_name = {
        dimension_name(adapter, annotation): annotation
        for annotation in front_annotations
    }
    rise_display = adapter._attempt(
        lambda: front_by_name["BallRise"].GetSpecificAnnotation()
    )
    if rise_display is None:
        raise RuntimeError("BallRise has no display dimension to box")
    set_basic_dimension(adapter, rise_display, label="ball and cross-bore height")
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the front view")

    stem_face = _cylindrical_face(adapter, front, STEM_DIA)
    add_view_centerline(
        adapter,
        front,
        face_xy=(FRONT_CENTER[0] + STEM_DIA / 2.0 * _S, _front_y(12.0)),
        label="turned stem axis",
        entity=stem_face,
    )

    # Explicit arrowed feature callouts avoid the old R6.50 / DIA13 duplicate
    # and identify exactly which turned surface each size controls.
    ball_outline = _ball_silhouette_xy(30.0)
    add_attached_note(
        adapter,
        front,
        text="S<MOD-DIAM>13.00 +/-0.05 BALL",
        edge_xy=ball_outline,
        note_xy=(0.170, 0.202),
        label="spherical ball size",
        entity_type="SILHOUETTE",
    )
    stem_dimension = add_edge_dimension(
        adapter,
        front,
        p0=(FRONT_CENTER[0] - STEM_DIA / 2.0 * _S, _front_y(12.0)),
        p1=(FRONT_CENTER[0] + STEM_DIA / 2.0 * _S, _front_y(12.0)),
        text_xy=STEM_DIM_TEXT,
        label="stem diameter",
        entity_type="SILHOUETTE",
    )
    _set_stem_dimension_format(adapter, stem_dimension)
    add_attached_note(
        adapter,
        front,
        text="<MOD-DIAM>13.00 +/-0.05 X 4.00 +/-0.05 PAD",
        edge_xy=(FRONT_CENTER[0] + BASE_DIA / 2.0 * _S, _front_y(BASE_H / 2.0)),
        note_xy=(0.168, 0.094),
        label="seat pad size",
        entity_type="SILHOUETTE",
    )

    # Datum A is the seat face. Datum B is derived from the cylindrical stem,
    # making the sphere, pad, and cross-bore controls inspectable from one DRF.
    _bore_r = BORE_DIA / 2.0 * _S
    seat_edge = (FRONT_CENTER[0] + 0.008, _front_y(0.0))
    seat_entity, bore_entity = _front_entities(adapter, front)
    add_datum_feature(
        adapter,
        front,
        edge_xy=seat_edge,
        symbol_xy=(FRONT_CENTER[0] + 0.024, _front_y(0.0) - 0.010),
        datum="A",
        label="seat face",
        entity=seat_entity,
    )
    add_datum_feature(
        adapter,
        front,
        edge_xy=STEM_DIM_TEXT,
        symbol_xy=STEM_DIM_TEXT,
        datum="B",
        label="stem diameter feature of size",
        entity_type="DIMENSION",
        position_tolerance_m=0.0005,
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=STEM_DIM_TEXT,
        frame_xy=(0.180, _front_y(12.0) - 0.022),
        characteristic="perpendicularity",
        tolerance="0.05",
        datums=("A",),
        diameter=True,
        quantity="STEM AXIS",
        label="datum-B axis perpendicularity",
        entity_type="DIMENSION",
        leader=False,
    )
    # The BASIC height and position zone locate the cross-bore axis from the
    # seat plane and through the stem axis without a prose-only acceptance rule.
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0], _front_y(BALL_CENTER_H) + _bore_r),  # bore top
        # Keep this leader wholly to the right of the bore.  SolidWorks retains
        # a long native association leader on the stem-axis control below; a
        # left-side bore leader necessarily intersects that diagonal.
        frame_xy=(0.205, 0.165),
        characteristic="position",
        tolerance="0.05",
        datums=("A", "B"),
        diameter=True,
        label="cross-bore true position",
        entity=bore_entity,
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=ball_outline,
        frame_xy=(0.255, 0.202),
        characteristic="profile_surface",
        tolerance="0.10",
        datums=("A", "B"),
        quantity="SPHERE",
        label="sphere profile and center location",
        entity_type="SILHOUETTE",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0] + BASE_DIA / 2.0 * _S, _front_y(BASE_H / 2.0)),
        frame_xy=(0.255, 0.094),
        characteristic="circular_runout",
        tolerance="0.05",
        datums=("B",),
        quantity="PAD OD",
        label="pad-to-stem runout",
        entity_type="SILHOUETTE",
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0] + _bore_r, _front_y(BALL_CENTER_H)),  # bore right
        symbol_xy=(0.152, _front_y(BALL_CENTER_H) - 0.026),
        roughness_ra="1.6",
        label="cross-bore finish",
        entity=bore_entity,
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=ball_outline,
        symbol_xy=(0.286, 0.178),
        roughness_ra="0.8",
        label="turned exterior finish before plate",
        entity_type="SILHOUETTE",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.068)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pivot Ball Mount Manufacturing Drawing",
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
