r"""Create the curated machinist drawing for the magnifying-wheel axle."""

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
    add_view_centerline,
    assert_imported_precision,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from mg_wheel_axle_spec import (
    BACK_Y,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    STEP_Y,
    THREAD_CALLOUT,
    THREAD_END_Y,
    TIP_Y,
)
from solidworks_mcp.adapters.solidworks.drawing import place_view, view_outline


SPEC = DRAWINGS_BY_NAME["mg_wheel_axle"]
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

# Every view prints at the sheet scale, so none needs a caption. 4:1 lays the
# 37.17 pin 149 mm long and its 3/16 shank 19 mm across.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
# One side view: the *Front view (parallel to the profile sketch, so its
# dimensions import), turned so the pin lies horizontal, back end left.
SIDE_CENTER = (0.160, 0.170)
SIDE_VIEW_ANGLE = -math.pi / 2.0  # model +Y (back end -> tip) to paper right
ISO_CENTER = (0.335, 0.185)
_MID_Y = (BACK_Y + TIP_Y) / 2.0


def _sheet_x(model_y_mm: float) -> float:
    """Sheet X of a model-Y station on the side view (the view is centred on
    the model bbox, back end to tip)."""
    return SIDE_CENTER[0] + (model_y_mm - _MID_Y) * _S / 1000.0


BACK_X = _sheet_x(BACK_Y)
STEP_X = _sheet_x(STEP_Y)
THREAD_END_X = _sheet_x(THREAD_END_Y)
TIP_X = _sheet_x(TIP_Y)

# Rows below the profile, 15 mm apart: the shank from the back end chained to
# the thread from the step (the press gauge's datum), then the overall.
# Diameters on the profile.
_ROW_Y = (SIDE_CENTER[1] - 0.025, SIDE_CENTER[1] - 0.040)
SIDE_KEEP = {
    "ShankLength": ((BACK_X + STEP_X) / 2.0, _ROW_Y[0]),
    "ThreadLength": ((STEP_X + THREAD_END_X) / 2.0, _ROW_Y[0]),
    "PinLength": ((BACK_X + TIP_X) / 2.0, _ROW_Y[1]),
    # The shank's dimension line crosses the shank near the step.
    "PinDia": (STEP_X - 0.030, SIDE_CENTER[1] + 0.030),
    # Below-right of the tip, clear of the thread callout above it.
    "DomeR": (TIP_X + 0.015, SIDE_CENTER[1] - 0.015),
}
DRAWING_PRECISION_BY_NAME = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
# The thread callout's leader lands on the thread's end edge (where the dome
# starts); the note stands up and right so the leader leans back onto it.
THREAD_PICK = (THREAD_END_X, SIDE_CENTER[1] + 0.003)
THREAD_NOTE_XY = (THREAD_END_X + 0.012, SIDE_CENTER[1] + 0.042)
# A point on the shank face, clear of the Ø dimension line.
CENTERLINE_PICK = (BACK_X + 0.020, SIDE_CENTER[1] + 0.003)
# Bottom-left, above the title-block line.
NOTES_XY = (0.020, 0.048)


def _view_center_delta(
    adapter: Any, view: Any, intended: tuple[float, float], label: str
) -> tuple[float, float]:
    """Measured-vs-intended geometry-center delta for coordinate picks.

    ``place_view`` anchors on the model origin's projection, not the geometry
    box center, so a part that is not origin-symmetric (this pin spans
    y -8.9..28.27) lands its geometry offset from the requested center. Every
    layout constant in this recipe is authored about the intended geometry
    center; shifting by this delta makes the edge picks and text positions
    track wherever SolidWorks actually put the geometry.
    """
    outline = view_outline(adapter, view)
    if outline is None:
        raise RuntimeError(f"{label} drawing view has no outline")
    cx = (outline[0] + outline[2]) / 2.0
    cy = (outline[1] + outline[3]) / 2.0
    _telemetry.debug(
        f"{label} view geometry center ({cx:.4f}, {cy:.4f}) vs intended "
        f"({intended[0]:.4f}, {intended[1]:.4f})"
    )
    return cx - intended[0], cy - intended[1]


def _shift(
    points: dict[str, tuple[float, float]], dx: float, dy: float
) -> dict[str, tuple[float, float]]:
    return {name: (x + dx, y + dy) for name, (x, y) in points.items()}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open wheel-axle source", await adapter.open_model(str(SOURCE)))
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Wheel Axle Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: f"wheel axle; 3/16 drill-rod pin; {THREAD_CALLOUT}; steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Front", *SIDE_CENTER, scale=VIEW_SCALE)
    native = _early_bound(side, "IView")
    native.Angle = SIDE_VIEW_ANGLE
    if abs(math.remainder(float(native.Angle) - SIDE_VIEW_ANGLE, 2.0 * math.pi)) > 1e-9:
        raise RuntimeError("failed to rotate the wheel-axle side view")
    drawing_model.EditRebuild3()
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (side, iso):
        set_hidden_lines_removed(adapter, view)

    dx, dy = _view_center_delta(adapter, side, SIDE_CENTER, "side")

    def spt(x: float, y: float) -> tuple[float, float]:
        return (x + dx, y + dy)

    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=_shift(SIDE_KEEP, dx, dy),
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, side_annotations, DRAWING_PRECISION_BY_NAME)
    add_view_centerline(
        adapter,
        side,
        face_xy=spt(*CENTERLINE_PICK),
        label="wheel axle turning axis",
    )
    add_attached_note(
        adapter,
        side,
        text=THREAD_CALLOUT,
        entity_xy=spt(*THREAD_PICK),
        note_xy=spt(*THREAD_NOTE_XY),
        label="wheel axle thread callout",
    )

    # x=0.020: a note is left-aligned on its anchor, so the ink starts here,
    # clear of the 12.7 mm zone margin.
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Wheel Axle Manufacturing Drawing",
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
