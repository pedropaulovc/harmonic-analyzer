r"""Create the manufacturing drawing for the transgear knob thrust ring (MHA-PD-15).

The edge view is the ``*Right`` orientation rotated a quarter turn in the
sheet so the ring's axis lies horizontal, as it sits in the lathe: the front
face (on the pinion) on the left, the rear face (on the plate hub) on the
right, each with its running finish, the length between them under its
explicit band and the O.D. beside it; the length's callout names the stack
its band serves.  The face view is the ``*Bottom`` orientation -- exactly the
third-angle LEFT view of that rotated profile -- so it sits on the profile's
axis to its left and carries the drilled bore under the DRILLED HOLES row.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
)

from _check import check
from _com import _early_bound
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision
from _drawing_finish import add_surface_finish
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from pd_transgear_knob_thrust_ring_spec import (
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    ID,
    LENGTH,
    OD,
    SURFACE_FINISHES,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

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

# The bore's callout stays on the end view (a drilled hole is defined by its
# callout, and the side view is hidden-lines-removed); the O.D. arrives there
# too and is moved onto the side view, so no two diameter lines cross the
# end view's centre.
END_KEEP = {
    "RingOd": (0.040, 0.120),  # donor: moved onto the side view
    "BoreDia": (0.130, 0.225),
}
MOVED_TO_SIDE = frozenset({"RingOd"})
# The length's text and its callout stand outside the right extension line:
# the 20.8 mm span between the faces is narrower than "5.200 ±0.05", so text
# centred between them is struck by both extension lines.  Far enough right
# that the callout's left edge clears the right extension line, and high
# enough that its second line clears the O.D.'s upper extension line.
SIDE_KEEP = {
    "RingLength": (SIDE_CENTER[0] + LENGTH / 2.0 * _S / 1000.0 + 0.032, 0.224),
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

# swAnnotationType_e.swCenterMarkSym.  The template centre-marks the face
# view's bore as it is placed; an unconditional auto_center_marks printed a
# second identical mark over it (layout audit duplicate-annotation,
# DetailItem347/348, ENFORCE fix run 1; the draw_dt_pinion_cam_pin
# precedent), so the sheet adds one only if the template did not, and proves
# exactly one.
_CENTER_MARK_ANNOTATION = 13


def _center_mark_count(view: Any) -> int:
    """The view's centre-mark annotations (a bare view answers None)."""
    return len(
        _early_bound(view, "IView").GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ()
    )


@_telemetry.traced("drawing.pd_transgear_knob_thrust_ring.callouts")
def _assert_dimension_callouts(adapter: Any, annotations: list[Any]) -> None:
    """Import the part-authored callout rows verbatim; never write them here.

    Text set from the drawing writes through to the built part (fleet issue
    #1942), so the sheet only proves each callout dimension printed once with
    the rows its part authored.
    """
    for callouts in DIMENSION_CALLOUTS.values():
        for name, text in callouts.items():
            matches = [
                item for item in annotations if dimension_name(adapter, item) == name
            ]
            if len(matches) != 1:
                raise RuntimeError(f"{name}: expected one imported callout dimension")
            display = _early_bound(
                _early_bound(matches[0], "IAnnotation").GetSpecificAnnotation(),
                "IDisplayDimension",
            )
            if str(display.GetText(4) or "").replace("\r\n", "\n") != text:
                raise RuntimeError(f"{name}: imported callout differs from the part's")


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
    # Decimal places (and so the general-tolerance row each dimension claims),
    # the length's band and both callout rows are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _assert_dimension_callouts(adapter, annotations)
    if _center_mark_count(end) == 0 and not auto_center_marks(
        adapter, end, holes=True, size=0.0025
    ):
        raise RuntimeError("failed to add ASME center mark to the ring face view")
    found = _center_mark_count(end)
    if found != 1:
        raise RuntimeError(
            f"expected 1 centre mark in the ring face view, found {found}"
        )
    # The turning axis, picked on the O.D. face above it.
    add_view_centerline(
        adapter,
        side,
        face_xy=(SIDE_CENTER[0], SIDE_CENTER[1] + OD * _S / 4000.0),
        label="knob thrust ring axis centerline",
    )
    for key, label in (
        ("front_face", "ring front (pinion) face finish"),
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
