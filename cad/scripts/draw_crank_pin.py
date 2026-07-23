r"""Create the curated machinist drawing for the crank tapered pin."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_view_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from crank_pin_spec import PIN_LENGTH
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
    view_name,
)


SPEC = DRAWINGS_BY_NAME["crank_pin"]
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
SMALL_END_EDGE = (FRONT_CENTER[0] + _HALF_LENGTH, FRONT_CENTER[1])

FRONT_KEEP = {
    "Length": (FRONT_CENTER[0], FRONT_CENTER[1] - 0.033),
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
    ddoc = _early_bound(draw, "IDrawingDoc")  # IDrawingDoc view for drawing-only methods (same dispatch)
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
    display = _sw_type_info.early_bound_or_flag(
        display, "IDisplayDimension", "SetText"
    )
    # An edge-on circle can come in as a radial dimension; force the
    # doubled/diameter display (no-op on dimension types it does not apply to).
    adapter._attempt(lambda: setattr(display, "Diametric", True))
    display.SetText(4, below)  # swDimensionTextCalloutBelow
    draw.EditRebuild3()
    return display


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    drawing_model, _sheet = new_project_drawing(
        adapter,
        category=SPEC.category,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
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
    read_required_view_properties(
        adapter,
        front,
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
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    _add_end_diameter(
        adapter,
        front,
        edge_xy=BIG_END_EDGE,
        text_xy=(BIG_END_EDGE[0] - 0.028, FRONT_CENTER[1] + 0.030),
        below="BIG END",
        label="big end",
    )
    _add_end_diameter(
        adapter,
        front,
        edge_xy=SMALL_END_EDGE,
        text_xy=(SMALL_END_EDGE[0] + 0.028, FRONT_CENTER[1] + 0.030),
        below="SMALL END",
        label="small end",
    )
    # SolidWorks classifies a solid circular end silhouette under the same
    # AutoInsertCenterMarks2 "hole" bit as a bored circle; disabling that bit
    # makes the API a guaranteed no-op even though the end view is circular.
    if not auto_center_marks(adapter, right, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to pin end view")

    # The cone's side-view outline is a SILHOUETTE, not a selectable model
    # edge, so the taper-seat finish symbol attaches to the big-end circle —
    # the taper surface's own boundary edge.
    add_surface_finish(
        adapter,
        front,
        edge_xy=BIG_END_EDGE,
        symbol_xy=(FRONT_CENTER[0] - 0.018, FRONT_CENTER[1] + 0.022),
        roughness_ra="1.6",
        label="taper seating finish",
    )

    # 0.020: the note is left-aligned on its anchor, so the ink starts here. The
    # left bound is the 12.7 mm zone margin (~0.0127), which the re-centred frame
    # rule now matches (~0.0126); 0.020 clears both, and the audit enforces it.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.108)
    add_property_linked_note(adapter, "End View Note", RIGHT_CENTER[0] - 0.022, 0.162)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Pin Manufacturing Drawing",
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
