r"""Create the curated machinist drawing for the pivot ball mount."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_attached_note,
    add_datum_feature,
    add_feature_control_frame,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
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
    "BallRise": "+/-0.05",
}


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
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the front view")

    # Explicit arrowed feature callouts avoid the old R6.50 / DIA13 duplicate
    # and identify exactly which turned surface each size controls.
    add_attached_note(
        adapter,
        front,
        text="S<MOD-DIAM>13.00 +/-0.05 BALL",
        edge_xy=(FRONT_CENTER[0] + BALL_DIA / 2.0 * _S * 0.75, _front_y(30.0)),
        note_xy=(0.170, 0.202),
        label="spherical ball size",
        entity_type="SILHOUETTE",
    )
    add_attached_note(
        adapter,
        front,
        text="<MOD-DIAM>8.00 +/-0.05 STEM",
        edge_xy=(FRONT_CENTER[0] + STEM_DIA / 2.0 * _S, _front_y(12.0)),
        note_xy=(0.038, 0.128),
        label="stem diameter",
        entity_type="SILHOUETTE",
    )
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
        edge_xy=(FRONT_CENTER[0] + STEM_DIA / 2.0 * _S, _front_y(10.0)),
        symbol_xy=(FRONT_CENTER[0] + 0.026, _front_y(10.0)),
        datum="B",
        label="stem axis",
        entity_type="SILHOUETTE",
    )
    # Position to B controls cross-bore intersection with the pillar axis;
    # parallelism to A controls the bore-axis attitude.
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0], _front_y(BALL_CENTER_H) + _bore_r),
        frame_xy=(0.180, _front_y(BALL_CENTER_H) + 0.060),
        characteristic="position",
        tolerance="0.05",
        datums=("B",),
        diameter=True,
        label="cross-bore intersection",
        entity=bore_entity,
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0], _front_y(BALL_CENTER_H) + _bore_r),  # bore top
        frame_xy=(0.180, _front_y(BALL_CENTER_H) + 0.036),
        characteristic="parallelism",
        tolerance="0.05",
        datums=("A",),
        diameter=True,  # cylindrical zone -- the control is on the bore AXIS
        label="cross-bore parallelism",
        entity=bore_entity,
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0] + BALL_DIA / 2.0 * _S * 0.75, _front_y(30.0)),
        frame_xy=(0.255, 0.202),
        characteristic="circular_runout",
        tolerance="0.05",
        datums=("B",),
        label="ball-to-stem runout",
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
        edge_xy=(FRONT_CENTER[0] + BALL_DIA / 2.0 * _S * 0.75, _front_y(30.0)),
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
