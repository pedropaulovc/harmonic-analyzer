r"""Create the curated machinist drawing for the crank tapered pin."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
    view_name,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_centerline import add_view_centerline
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_leader_notes import add_leader_note
from _drawing_notes import add_property_linked_note, property_link
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _drawing_view_display import set_hidden_lines_removed
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from dt_crank_pin_spec import (
    BIG_END_DIA,
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    PIN_LENGTH,
    RING_HOLE_X,
    SMALL_END_DIA,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_crank_pin"]
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

SHEET_SCALE = (2.0, 1.0)
END_VIEW_SCALE = 4.0
FRONT_CENTER = (0.110, 0.195)
RIGHT_CENTER = (
    FRONT_CENTER[0] + PIN_LENGTH * SHEET_SCALE[0] / 2000.0 + 0.080,
    FRONT_CENTER[1],
)
ISO_CENTER = (0.340, 0.205)

# Side-view landmarks (sheet meters): the pin is centred on its bounding box,
# big end (model x=0) to the left, small end (x=PIN_LENGTH) to the right.
_HALF_LENGTH = PIN_LENGTH * SHEET_SCALE[0] / 2000.0
BIG_END_EDGE = (FRONT_CENTER[0] - _HALF_LENGTH, FRONT_CENTER[1])
# The upper taper outline at model x = TAPER_PICK_X, where the pin's radius
# is interpolated between its end diameters: the taper note's leader tip.
TAPER_PICK_X = PIN_LENGTH * 0.45
_TAPER_PICK_R = (BIG_END_DIA - (BIG_END_DIA - SMALL_END_DIA) * TAPER_PICK_X / PIN_LENGTH) / 2.0
TAPER_SILHOUETTE_PICK = (
    BIG_END_EDGE[0] + TAPER_PICK_X * SHEET_SCALE[0] / 1000.0,
    FRONT_CENTER[1] + _TAPER_PICK_R * SHEET_SCALE[0] / 1000.0,
)
# The taper note's top-left corner: above the pin and just right of the
# leader tip, so the leader leaves the start of the first line down-left,
# outside the text block (round 2 had it run back through all four lines).
TAPER_NOTE_XY = (TAPER_SILHOUETTE_PICK[0] + 0.006, FRONT_CENTER[1] + 0.063)

# The ring cross-hole, seen end-on as a circle on the axis.
RING_HOLE_CENTER = (
    BIG_END_EDGE[0] + RING_HOLE_X * SHEET_SCALE[0] / 1000.0,
    FRONT_CENTER[1],
)
# A point on the conical face, clear of the cross-hole, for the axis.
AXIS_FACE_PICK = (FRONT_CENTER[0] + 0.020, FRONT_CENTER[1] + 0.002)

# The 3.70 station's 9.05-mm-wide text cannot fit between its extension
# lines, only 7.4 mm apart at 2:1. Put the text outboard right, clear of
# the outside arrow's 6.35-mm tail and left of the taper-note leader.
# Below the hole: its Ø callout, then the overall length.
FRONT_KEEP = {
    "RingHoleX": (
        RING_HOLE_CENTER[0] + 0.014,
        FRONT_CENTER[1] + 0.016,
    ),
    "RingHoleDia": (RING_HOLE_CENTER[0] + 0.020, FRONT_CENTER[1] - 0.016),
    "Length": (FRONT_CENTER[0], FRONT_CENTER[1] - 0.045),
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}


@_telemetry.traced("drawing.end_diameter", label_param="label")
def _add_end_diameter(
    adapter: Any,
    view: Any,
    *,
    edge_xy: tuple[float, float],
    text_xy: tuple[float, float],
    below: str,
    label: str,
) -> Any:
    """Dimension one end-face circle seen edge-on in the side view.

    The pin's only model diameter dims are half-profile RADII (the frustum
    sketch dimensions each vertical line from the axis), which would print as
    bare 3.00/2.50 linears; dimensioning the projected end-face CIRCLE edge
    instead yields the true-diameter callout a turned-pin print carries at
    each end.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate drawing view {name!r} ({label})")
    draw.ClearSelection2(True)
    if not draw.Extension.SelectByID2(
        "", "EDGE", edge_xy[0], edge_xy[1], 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(
            f"failed to select {label} end-face edge at sheet "
            f"({edge_xy[0]:g}, {edge_xy[1]:g})"
        )
    display = draw.AddDimension2(text_xy[0], text_xy[1], 0.0)
    draw.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"failed to add the {label} diameter dimension")
    display = _sw_type_info.early_bound_or_flag(display, "IDisplayDimension", "SetText")
    # An edge-on circle can come in as a radial dimension; force the
    # doubled/diameter display (no-op on dimension types it does not apply to).
    adapter._attempt(lambda: setattr(display, "Diametric", True))
    display.SetText(4, below)  # swDimensionTextCalloutBelow
    draw.EditRebuild3()
    return display


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-pin source", await adapter.open_model(str(SOURCE)))
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
            "End View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "End View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Crank Pin Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank pin; tapered pin; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, front_annotations, DRAWING_PRECISION_BY_NAME)
    # Descriptive text only; the hole's size and station are the model's.
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    # The axis shows the cross-hole goes through the centre; its station runs
    # from the big-end face.
    add_view_centerline(
        adapter, front, face_xy=AXIS_FACE_PICK, label="crank pin axis centerline"
    )
    # The big end, the length and the 1:48 ratio define the taper; a printed
    # small end, rounded to .XX from the mm model, read as a second taper
    # (#290 machinist review of 29af6f44d), so it is not dimensioned.
    _add_end_diameter(
        adapter,
        front,
        edge_xy=BIG_END_EDGE,
        text_xy=(BIG_END_EDGE[0] - 0.028, FRONT_CENTER[1] + 0.030),
        below="BIG END",
        label="big end",
    )
    # SolidWorks classifies a solid circular end silhouette under the same
    # AutoInsertCenterMarks2 "hole" bit as a bored circle; disabling that bit
    # makes the API a guaranteed no-op even though the end view is circular.
    if not auto_center_marks(adapter, right, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to pin end view")

    add_property_linked_note(adapter, "End View Note", RIGHT_CENTER[0] - 0.022, 0.162)

    # The part's one note (taper ratio and matched fit) is flagged on the
    # taper it governs: its leader tip lands on the cone's upper outline,
    # mid-taper and clear of the ring cross-hole.
    add_leader_note(
        adapter,
        property_link("Manufacturing Notes"),
        text_xy=TAPER_NOTE_XY,
        attach_xy=TAPER_SILHOUETTE_PICK,
        label="taper fit note",
        view=front,
    )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Pin Manufacturing Drawing",
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
