r"""Create the manufacturing drawing for the crank seat thrust washer (MHA-172).

The edge view is the ``*Right`` orientation rotated a quarter turn in the
sheet so the washer's axis lies horizontal, as it sits in the lathe: the
collar face on the left, the boss face on the right, each with its running
finish.  The face view is the ``*Bottom`` orientation -- exactly the
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
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from crank_seat_washer_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    ID,
    OD,
    SURFACE_FINISHES,
    THICKNESS,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["crank_seat_washer"]
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

# A O20.6 x 1.5 washer: 4:1 keeps both diameters, the thickness and the two
# face finishes legible without crowding the landscape sheet.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
# The *Right view rotated -90 degrees: model +Y runs to paper-right.
SIDE_VIEW_ANGLE = -math.pi / 2.0
SIDE_CENTER = (0.180, 0.170)
# Third-angle left view of the collar face, on the profile's axis.
END_CENTER = (0.090, SIDE_CENTER[1])
ISO_CENTER = (0.310, SIDE_CENTER[1])

DRAWING_PRECISION_BY_NAME = {
    name: digits
    for names in DRAWING_PRECISION.values()
    for name, digits in names.items()
}

END_KEEP = {
    "DiscDia": (0.040, 0.240),
    "BoreDia": (0.130, 0.240),
}
SIDE_KEEP = {
    "DiscThick": (0.195, 0.230),
}


def _sheet_x(model_y_mm: float) -> float:
    """Sheet X of a model-Y station on the horizontal edge view."""
    return SIDE_CENTER[0] + (model_y_mm - THICKNESS / 2.0) * _S / 1000.0


# Each face's pick lies on its O.D. edge, between the bore and the O.D. radii
# (below the axis, clear of the thickness dimension above), where no bore
# edge projects onto the same line.  The symbols stand below and outboard.
_FACE_PICK_Y = SIDE_CENTER[1] - (ID + OD) / 4.0 * _S / 1000.0
FACE_FINISHES = {
    "collar_face": ((_sheet_x(0.0), _FACE_PICK_Y), (_sheet_x(0.0) - 0.025, 0.110)),
    "boss_face": (
        (_sheet_x(THICKNESS), _FACE_PICK_Y),
        (_sheet_x(THICKNESS) + 0.025, 0.110),
    ),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-seat-washer source", await adapter.open_model(str(SOURCE)))
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
        required=("Number", "Material Specification", "Finish", "Quantity"),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Crank Seat Thrust Washer Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank seat thrust washer; turned steel",
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
        raise RuntimeError("failed to lay the washer's edge view horizontal")
    drawing_model.EditRebuild3()
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (end, side, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        *curate_view_dimensions(
            adapter,
            end,
            keep=END_KEEP,
            view_label="face",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            side,
            keep=SIDE_KEEP,
            view_label="edge",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the washer face view")
    for key, label in (
        ("collar_face", "washer collar face finish"),
        ("boss_face", "washer boss face finish"),
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
        pdf_title="Crank Seat Thrust Washer Manufacturing Drawing",
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
