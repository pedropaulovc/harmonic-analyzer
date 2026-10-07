r"""Create the drawing for the rocker arm's vise blank-end stop (MHA-CH-006-TL-01).

Third-angle at 3:2, the latch-hook-bracket layout for a Z-up part:

* the elevation is ``*Bottom`` (looking +Y, X right, Z up): the arm with the
  taller finger at its left end; it carries the two axial sizes, both from
  the seat face (the face clamped to the magnetic base);
* the plan above it is ``*Front`` (looking -Z, X right, Y up): the L itself,
  the finger reaching across the blank end;
* the side view to the elevation's right is ``*Right`` (looking -X onto the
  seat face) turned a quarter turn so Z runs up: the finger section, the arm
  section and both drilled holes, every size and position from the shared
  rear and bottom faces.

The bonding and mounting instructions ride the part's Manufacturing Notes.
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
    add_property_linked_note,
    assert_imported_precision,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from ch_rocker_arm_tl_vise_stop_spec import (
    ARM_INNER_Y,
    ARM_TOP_Z,
    BACK_X,
    BOTTOM_Z,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    NOSE_PIN_CALLOUT,
    FINGER_END_Y,
    FINGER_FRONT_X,
    FINGER_TOP_Z,
    NOSE_Y,
    NOSE_Z,
    REAR_Y,
    SCREW_Y,
    SCREW_Z,
    SCREW_HOLE_CALLOUT,
    SEAT_X,
)
from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vise_stop"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 69 x 59 x 24 L: 3:2 stacks the plan over the elevation above the title
# block, with the side view and its dimensions to the elevation's right.
SHEET_SCALE = (3.0, 2.0)
VIEW_SCALE = (3, 2)
ISO_SCALE = (1, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0  # sheet metres per model mm
ELEVATION_CENTER = (0.115, 0.118)
PLAN_CENTER = (ELEVATION_CENTER[0], 0.215)
SIDE_CENTER = (0.290, ELEVATION_CENTER[1])
ISO_CENTER = (0.335, 0.220)
NOTES_XY = (0.020, 0.050)
ISO_NOTE_XY = (0.300, 0.192)
# The *Right view turned so model +Z runs up the sheet (and +Y to the right).
SIDE_VIEW_ANGLE = -math.pi / 2.0

# Bounding-box centres: each view centres the part's box on its placement.
_XC = (SEAT_X + BACK_X) / 2.0
_YC = (REAR_Y + FINGER_END_Y) / 2.0
_ZC = (BOTTOM_Z + FINGER_TOP_Z) / 2.0


def _elevation(x_mm: float, z_mm: float) -> tuple[float, float]:
    """Sheet point of a model (X, Z) on the elevation."""
    return (
        ELEVATION_CENTER[0] + (x_mm - _XC) * _S,
        ELEVATION_CENTER[1] + (z_mm - _ZC) * _S,
    )


def _side(y_mm: float, z_mm: float) -> tuple[float, float]:
    """Sheet point of a model (Y, Z) on the turned side view."""
    return (
        SIDE_CENTER[0] + (y_mm - _YC) * _S,
        SIDE_CENTER[1] + (z_mm - _ZC) * _S,
    )


_ELEVATION_TOP = _elevation(0.0, FINGER_TOP_Z)[1]
_SIDE_LEFT, _SIDE_BOTTOM = _side(FINGER_END_Y, BOTTOM_Z)
_SIDE_RIGHT, _SIDE_TOP = _side(REAR_Y, FINGER_TOP_Z)

# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position. Both axial sizes stack above the elevation, from the seat face.
# On the side view the Y runs stand below (finger, nose) and above (arm,
# screw) the section, the heights to its left (finger, nose) and right
# (arm, screw), each hole size beside its own hole.
ELEVATION_KEEP = {
    "FingerFront": (_elevation((SEAT_X + FINGER_FRONT_X) / 2.0, 0.0)[0], _ELEVATION_TOP + 0.010),
    "OverallLength": (_elevation(_XC, 0.0)[0], _ELEVATION_TOP + 0.022),
}
SIDE_KEEP = {
    "FingerLength": (SIDE_CENTER[0], _SIDE_BOTTOM - 0.012),
    "NoseFromRear": (_side((NOSE_Y + REAR_Y) / 2.0, 0.0)[0], _SIDE_BOTTOM - 0.023),
    "ScrewFromRear": (_side((SCREW_Y + REAR_Y) / 2.0, 0.0)[0], _SIDE_TOP + 0.010),
    "ArmWidth": (_side((ARM_INNER_Y + REAR_Y) / 2.0, 0.0)[0], _SIDE_TOP + 0.021),
    "FingerHeight": (_SIDE_LEFT - 0.012, SIDE_CENTER[1]),
    "NoseHeight": (_SIDE_LEFT - 0.024, _side(0.0, (BOTTOM_Z + NOSE_Z) / 2.0)[1]),
    "ScrewHeight": (_SIDE_RIGHT + 0.012, _side(0.0, (BOTTOM_Z + SCREW_Z) / 2.0)[1]),
    "ArmHeight": (_SIDE_RIGHT + 0.024, _side(0.0, (BOTTOM_Z + ARM_TOP_Z) / 2.0)[1]),
    "NoseHoleDia": (_side(NOSE_Y, 0.0)[0] - 0.004, _SIDE_TOP + 0.016),
    "ScrewHoleDia": (_SIDE_RIGHT + 0.040, _side(0.0, SCREW_Z)[1] + 0.030),
}
# The bought nose pin reads above its hole's size, the drilling below.
CALLOUTS_ABOVE = {"NoseHoleDia": NOSE_PIN_CALLOUT}
CALLOUTS_BELOW = {"NoseHoleDia": "DRILL THRU", "ScrewHoleDia": SCREW_HOLE_CALLOUT}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open vise-stop source", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Manufacturing Notes",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Vise Blank-End Stop Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker arm vise blank-end stop; milled steel L; MHA-CH-006-TL-01",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    elevation = place_view(
        adapter, str(SOURCE), "*Bottom", *ELEVATION_CENTER, scale=VIEW_SCALE
    )
    plan = place_view(adapter, str(SOURCE), "*Front", *PLAN_CENTER, scale=VIEW_SCALE)
    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=VIEW_SCALE)
    native_side = _early_bound(side, "IView")
    native_side.Angle = SIDE_VIEW_ANGLE
    if (
        abs(math.remainder(float(native_side.Angle) - SIDE_VIEW_ANGLE, 2.0 * math.pi))
        > 1e-9
    ):
        raise RuntimeError("failed to stand the vise stop's side view upright")
    drawing_model.EditRebuild3()
    # finalize_drawing shades the pictorial isometric with edges.
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (elevation, plan, side):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        *curate_view_dimensions(
            adapter,
            elevation,
            keep=ELEVATION_KEEP,
            view_label="elevation",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            side,
            keep=SIDE_KEEP,
            view_label="side",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    # Places (and so each dimension's tolerance) and the drilled-hole band are
    # authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    set_dimension_callouts(adapter, annotations, CALLOUTS_BELOW)
    if not auto_center_marks(adapter, side, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the drilled holes")
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Vise Blank-End Stop Drawing",
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
