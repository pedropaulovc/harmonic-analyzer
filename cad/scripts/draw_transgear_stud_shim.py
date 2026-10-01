r"""Create the manufacturing drawing for the transgear stud shim (MHA-178).

The edge view is the ``*Top`` orientation rotated a quarter turn in the
sheet so the shim's axis lies horizontal, as it sits in the lathe: the arm
face (z = THICKNESS) on the left, the collar face (z = 0) on the right, each
with its finish.  The face view is the ``*Front`` orientation, on the
profile's axis to its left, and carries both diameters.
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
    add_surface_finish,
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from paper_drive_assembly_steps import step_ref
from transgear_stud_shim_spec import (
    BORE_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    ID,
    OD,
    SURFACE_FINISHES,
    THICKNESS,
    THICKNESS_CALLOUT,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["transgear_stud_shim"]
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

# A Ø12 shim, drawn as fitted: 5:1 keeps both diameters, the thickness and
# the two face finishes legible without crowding the landscape sheet.
SHEET_SCALE = (5.0, 1.0)
VIEW_SCALE = (5, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0  # model mm -> sheet m
# The *Top view rotated -90 degrees: model +Z runs to paper-left.
SIDE_VIEW_ANGLE = -math.pi / 2.0
SIDE_CENTER = (0.200, 0.165)
# The face view, on the profile's axis.
END_CENTER = (0.090, SIDE_CENTER[1])
ISO_CENTER = (0.310, SIDE_CENTER[1])

_COLLAR_X = SIDE_CENTER[0] + THICKNESS * _S / 2.0  # z 0, right end
_ARM_X = SIDE_CENTER[0] - THICKNESS * _S / 2.0  # z THICKNESS, left end
_SIDE_TOP = SIDE_CENTER[1] + OD * _S / 2.0
_SIDE_BOTTOM = SIDE_CENTER[1] - OD * _S / 2.0

# Faced to fit at MHA-A06's stud step; the pointer comes from the registry.
FIT_STEP_KEY = "stud-faced-to-fit"
DIMENSION_CALLOUTS = {
    "BoreDia": BORE_CALLOUT,
    "DiscThick": f"{THICKNESS_CALLOUT},\nPER {step_ref(FIT_STEP_KEY)}",
}

DRAWING_PRECISION_BY_NAME = {
    name: digits
    for names in DRAWING_PRECISION.values()
    for name, digits in names.items()
}

END_KEEP = {
    "DiscDia": (0.045, 0.220),
    "BoreDia": (0.125, 0.220),
}
# Under the profile, so its callout lines run down into open sheet.
SIDE_KEEP = {
    "DiscThick": (SIDE_CENTER[0], _SIDE_BOTTOM - 0.022),
}


# Each face's pick lies on its edge line between the bore and O.D. radii.
# The arm face's symbol stands above-left, clear of every dimension; the
# collar face's stands right of the part, below the axis.
_FACE_PICK_UP = SIDE_CENTER[1] + (ID + OD) / 4.0 * _S
_FACE_PICK_DOWN = SIDE_CENTER[1] - (ID + OD) / 4.0 * _S
FACE_FINISHES = {
    "arm_face": ((_ARM_X, _FACE_PICK_UP), (_ARM_X - 0.022, _SIDE_TOP + 0.014)),
    "collar_face": (
        (_COLLAR_X, _FACE_PICK_DOWN),
        (_COLLAR_X + 0.014, SIDE_CENTER[1] - 0.008),
    ),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open transgear-stud-shim source", await adapter.open_model(str(SOURCE)))
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
            0: "Transgear Stud Shim Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear stud shim; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    end = place_view(adapter, str(SOURCE), "*Front", *END_CENTER, scale=VIEW_SCALE)
    side = place_view(adapter, str(SOURCE), "*Top", *SIDE_CENTER, scale=VIEW_SCALE)
    native_side = _early_bound(side, "IView")
    native_side.Angle = SIDE_VIEW_ANGLE
    if (
        abs(math.remainder(float(native_side.Angle) - SIDE_VIEW_ANGLE, 2.0 * math.pi))
        > 1e-9
    ):
        raise RuntimeError("failed to lay the shim's edge view horizontal")
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
    # Faced to fit at assembly: the modelled thickness prints as a REFERENCE
    # value and the callout under it is the requirement; the blank it is
    # faced from is the Manufacturing Notes' make-to size.
    thickness_annotations = [
        annotation
        for annotation in annotations
        if dimension_name(adapter, annotation) == "DiscThick"
    ]
    if len(thickness_annotations) != 1:
        raise RuntimeError("edge view does not carry exactly one shim thickness")
    set_reference_dimension(adapter, thickness_annotations[0], label="shim thickness")
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the shim face view")
    for key, label in (
        ("arm_face", "shim arm face finish"),
        ("collar_face", "shim collar face finish"),
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
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.075)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Stud Shim Manufacturing Drawing",
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
