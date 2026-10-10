r"""Create the manufacturing drawing for the transgear knob thrust ring (MHA-PD-015).

The edge view is the ``*Right`` orientation rotated a quarter turn in the
sheet so the ring's axis lies horizontal, as it sits in the lathe: the front
face (on the 12T) on the left, the rear face (on the plate hub) on the
right, each with its running finish, the length between them under its
explicit band and the O.D. beside it.  The face view is the ``*Bottom``
orientation -- exactly the third-angle LEFT view of that rotated profile --
so it sits on the profile's axis to its left and carries the bore's callout.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _check import check
from _com import _early_bound
from _paths import CAD_ROOT
from _session import run_build
from _drawing_common import (
    DrawingOutputs,
    add_surface_finish,
    add_view_centerline,
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from pd_transgear_knob_thrust_ring_spec import (
    BORE_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    ID,
    LENGTH,
    OD,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pd_transgear_knob_thrust_ring"]
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

# The bore's callout stays on the end view (a drilled hole is defined by its
# callout, and the side view is hidden-lines-removed); the O.D. arrives there
# too and is moved onto the side view, so no two diameter lines cross the
# end view's centre.
END_KEEP = {
    "RingOd": (0.040, 0.120),  # donor: moved onto the side view
    "BoreDia": (0.130, 0.225),
}
MOVED_TO_SIDE = frozenset({"RingOd"})
SIDE_KEEP = {
    "RingLength": (0.180, 0.215),
}


def _sheet_x(model_y_mm: float) -> float:
    """Sheet X of a model-Y station on the horizontal edge view."""
    return SIDE_CENTER[0] + (model_y_mm - LENGTH / 2.0) * _S / 1000.0


# The O.D. right of the rear face, its dimension line far enough out that the
# rear face's finish symbol sits between the part and it.
OD_ON_SIDE = (_sheet_x(LENGTH) + 0.045, SIDE_CENTER[1])

# Each face's pick lies on its edge line, between the bore and the O.D.
# radii, below the axis and clear of the length dimension above.  The front
# face's symbol stands left of the part, its leader running down to it; the
# rear face's stands right of the part inside the O.D.'s extension-line band,
# below the axis, short of the O.D. dimension line.
_FACE_PICK_Y = SIDE_CENTER[1] - (ID + OD) / 4.0 * _S / 1000.0
FACE_FINISHES = {
    "front_face": ((_sheet_x(0.0), _FACE_PICK_Y), (_sheet_x(0.0) - 0.025, 0.155)),
    "rear_face": (
        (_sheet_x(LENGTH), _FACE_PICK_Y),
        (_sheet_x(LENGTH) + 0.014, SIDE_CENTER[1] - 0.008),
    ),
}


def _move_dimension(
    adapter: Any,
    annotation: Any,
    target: Any,
    text_xy: tuple[float, float],
    *,
    source_view: Any,
) -> Any:
    """Move a model dimension to the projection that shows its extension lines."""
    name = dimension_name(adapter, annotation)
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, source_view)):
        raise RuntimeError(f"{name}: failed to activate source dimension view")
    draw.ClearSelection2(True)
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    selection_name = str(display.GetNameForSelection() or "")
    if not selection_name or not draw.Extension.SelectByID2(
        selection_name,
        "DIMENSION",
        0.0,
        0.0,
        0.0,
        False,
        0,
        null_callout(),
        0,
    ):
        raise RuntimeError(
            f"failed to select model dimension {name}: {selection_name!r}"
        )
    drawing.DragModelDimension(
        view_name(adapter, target), 2, text_xy[0], text_xy[1], 0.0
    )
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    matches = [
        _early_bound(item, "IAnnotation")
        for item in (_early_bound(target, "IView").GetAnnotations() or ())
        if dimension_name(adapter, _early_bound(item, "IAnnotation")) == name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"{name}: native dimension did not move into target view")
    return matches[0]


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
    donors = [
        annotation
        for annotation in end_annotations
        if dimension_name(adapter, annotation) in MOVED_TO_SIDE
    ]
    if len(donors) != len(MOVED_TO_SIDE):
        raise RuntimeError("expected one ring O.D. donor dimension on the end view")
    moved = [
        _move_dimension(adapter, donor, side, OD_ON_SIDE, source_view=end)
        for donor in donors
    ]
    end_annotations = [
        annotation
        for annotation in end_annotations
        if dimension_name(adapter, annotation) not in MOVED_TO_SIDE
    ]
    annotations = [*end_annotations, *side_annotations, *moved]
    # Decimal places (and so the general-tolerance row each dimension claims)
    # and the bore's and length's bands are authored on the part; the sheet
    # only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, end_annotations, DIMENSION_CALLOUTS)
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the ring face view")
    # The turning axis, picked on the O.D. face above it.
    add_view_centerline(
        adapter,
        side,
        face_xy=(SIDE_CENTER[0], SIDE_CENTER[1] + OD * _S / 4000.0),
        label="knob thrust ring axis centerline",
    )
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
