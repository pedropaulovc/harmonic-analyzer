r"""Create the manufacturing drawing for the transgear knob thrust ring (MHA-156).

The edge view is the ``*Right`` orientation rotated a quarter turn in the
sheet so the ring's axis lies horizontal, as it sits in the lathe: the front
face (on the 12T) on the left, the rear face (on the plate hub) on the
right, each with its running finish, and the length between them under its
explicit band.  The face view is the ``*Bottom`` orientation -- exactly the
third-angle LEFT view of that rotated profile -- so it sits on the profile's
axis to its left and carries both diameters.
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
    add_surface_finish,
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
from _surface_finish import surface_finish_by_key
from transgear_knob_thrust_ring_spec import (
    BORE_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    ID,
    LENGTH,
    OD,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["transgear_knob_thrust_ring"]
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

# A Ø13.6 ring: 4:1 keeps both diameters, the banded length and the two face
# finishes legible without crowding the landscape sheet.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
# The *Right view rotated -90 degrees: model +Y runs to paper-right.
SIDE_VIEW_ANGLE = -math.pi / 2.0
SIDE_CENTER = (0.180, 0.170)
# Third-angle left view of the front face, on the profile's axis.
END_CENTER = (0.090, SIDE_CENTER[1])
ISO_CENTER = (0.300, SIDE_CENTER[1])

DIMENSION_CALLOUTS = {"BoreDia": BORE_CALLOUT}

END_KEEP = {
    "RingOd": (0.040, 0.225),
    "BoreDia": (0.130, 0.225),
}
SIDE_KEEP = {
    "RingLength": (0.180, 0.215),
}


def _sheet_x(model_y_mm: float) -> float:
    """Sheet X of a model-Y station on the horizontal edge view."""
    return SIDE_CENTER[0] + (model_y_mm - LENGTH / 2.0) * _S / 1000.0


# Each face's pick lies on its O.D. edge line, between the bore and the O.D.
# radii, below the axis and clear of the length dimension above.  The front
# face's symbol stands above the pick and outboard, its leader running down
# to it; the rear face's stands below and outboard.
_FACE_PICK_Y = SIDE_CENTER[1] - (ID + OD) / 4.0 * _S / 1000.0
FACE_FINISHES = {
    "front_face": ((_sheet_x(0.0), _FACE_PICK_Y), (_sheet_x(0.0) - 0.025, 0.155)),
    "rear_face": ((_sheet_x(LENGTH), _FACE_PICK_Y), (_sheet_x(LENGTH) + 0.025, 0.120)),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open knob-thrust-ring source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Transgear Knob Thrust Ring Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear knob thrust ring; turned brass",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    end = place_view(adapter, str(SOURCE), "*Bottom", *END_CENTER, scale=VIEW_SCALE)
    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=VIEW_SCALE)
    native_side = _early_bound(side, "IView")
    native_side.Angle = SIDE_VIEW_ANGLE
    if (
        abs(math.remainder(float(native_side.Angle) - SIDE_VIEW_ANGLE, 2.0 * math.pi))
        > 1e-9
    ):
        raise RuntimeError("failed to lay the ring's edge view horizontal")
    drawing_model.EditRebuild3()
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (end, side, iso):
        set_hidden_lines_removed(adapter, view)

    end_annotations = curate_view_dimensions(
        adapter,
        end,
        keep=END_KEEP,
        view_label="face",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="edge",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*end_annotations, *side_annotations]
    # Decimal places (and so the general-tolerance row each dimension claims)
    # and the bore's and length's bands are authored on the part; the sheet
    # only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, end_annotations, DIMENSION_CALLOUTS)
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the ring face view")
    for key, label in (
        ("front_face", "ring front (12T) face finish"),
        ("rear_face", "ring rear (plate hub) face finish"),
    ):
        pick, symbol = FACE_FINISHES[key]
        add_surface_finish(
            adapter,
            side,
            edge_xy=pick,
            symbol_xy=symbol,
            control=surface_finish_by_key(SURFACE_FINISHES, key),
            label=label,
            char_height=0.0025,
        )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Knob Thrust Ring Manufacturing Drawing",
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
