r"""Create the curated machinist drawing for the pivot ball mount."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
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
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from pivot_ball_mount_spec import BALL_CENTER_H, BALL_DIA, BORE_DIA
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


# The whole turned profile is defined in the front elevation: seat-pad radius +
# height, ball rise + spherical radius, and the cross-bore diameter.
FRONT_KEEP = {
    "BaseRadius": (FRONT_CENTER[0] + 0.030, _front_y(0.0) + 0.006),
    "BaseHeight": (FRONT_CENTER[0] - 0.032, _front_y(2.0)),
    "BallRise": (FRONT_CENTER[0] - 0.050, _front_y(BALL_CENTER_H / 2.0)),
    "BallRadius": (FRONT_CENTER[0] + 0.044, _front_y(_BALL_TOP_Y)),
    "ShaftBoreDia": (FRONT_CENTER[0] + 0.052, _front_y(BALL_CENTER_H)),
}
# No second orthographic view carries dimensions; keep the test contract honest.
TOP_KEEP: dict[str, tuple[float, float]] = {}
DIMENSION_CALLOUTS = {
    "ShaftBoreDia": "+0.00/-0.05 THRU",
    "BallRadius": "SPHERICAL",
    "BaseRadius": "(DIA 13 PAD)",
}


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

    # Datum A = the seat face (the base-seat datum the ball rise measures from).
    # The cross-bore is toleranced parallel to it and carries the running-fit
    # finish (it journals the rotating pivot shaft).
    _bore_r = BORE_DIA / 2.0 * _S
    seat_edge = (FRONT_CENTER[0] + 0.008, _front_y(0.0))
    add_datum_feature(
        adapter,
        front,
        edge_xy=seat_edge,
        symbol_xy=(FRONT_CENTER[0] + 0.024, _front_y(0.0) - 0.010),
        datum="A",
        label="seat face",
    )
    # The cross-bore is seen end-on (a circle); its axis runs horizontal (along
    # Z), so it is PARALLEL to the horizontal seat (datum A).
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0], _front_y(BALL_CENTER_H) + _bore_r),  # bore top
        frame_xy=(0.150, _front_y(BALL_CENTER_H) + 0.030),
        characteristic="parallelism",
        tolerance="0.05",
        datums=("A",),
        diameter=True,  # cylindrical zone -- the control is on the bore AXIS
        label="cross-bore parallelism",
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0] + _bore_r, _front_y(BALL_CENTER_H)),  # bore right
        symbol_xy=(0.152, _front_y(BALL_CENTER_H) - 0.026),
        roughness_ra="1.6",
        label="cross-bore finish",
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
