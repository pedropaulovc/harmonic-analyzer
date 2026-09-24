r"""Create the machinist drawing for the MHA-141 cone tip shim pack.

One plan view carries the whole blank at 4:1: the 15.0 x 12.0 outline, the
horseshoe slot's width with its full-radius callout, and the radius centre
located from the closed edge and the lower edge (policy rule 7: a location
starts on a face the shop can pick up, never the model origin).  An edge
view below it shows the nominal stack as a reference dimension; the
stack-to-fit range rides the manufacturing notes and the leaf stock the
material specification, because the fitted thickness is set at assembly,
not machined.

Run with SolidWorks open::

    uv run python cad\scripts\draw_cone_tip_shim.py cone-tip-shim
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
    add_edge_dimension,
    add_property_linked_note,
    assert_imported_precision,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimensions,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from cone_tip_shim_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    SHIM_X,
    SHIM_Z,
    SLOT_OPEN_SIDE,
    SLOT_R,
)
from solidworks_mcp.adapters.solidworks.drawing import place_view


SPEC = DRAWINGS_BY_NAME["cone_tip_shim"]
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

SHEET_SCALE = (4.0, 1.0)
_S = SHEET_SCALE[0] / 1000.0
# Third-angle: the plan (Top) above the edge view (Front).
TOP_CENTER = (0.120, 0.170)
FRONT_CENTER = (TOP_CENTER[0], 0.100)
ISO_CENTER = (0.320, 0.180)
HALF_X = SHIM_X * _S / 2.0  # 0.030 on the sheet
HALF_Z = SHIM_Z * _S / 2.0  # 0.024 on the sheet

# The *Top view keeps model +X to the right, so the slot opens to the LEFT
# edge and the closed (radius) end looks right.
if SLOT_OPEN_SIDE != -1:
    raise ValueError("the plan layout assumes the slot opens to model -X")

# Larger dimensions stand outside smaller ones: the 12.0 depth outboard of
# the 6.0 radius-centre location on the right.
TOP_KEEP = {
    "Width": (TOP_CENTER[0], TOP_CENTER[1] + HALF_Z + 0.014),
    "Depth": (TOP_CENTER[0] + HALF_X + 0.024, TOP_CENTER[1]),
    # Past the open mouth, level with the slot's centreline.
    "SlotWidth": (TOP_CENTER[0] - HALF_X - 0.016, TOP_CENTER[1]),
}
FRONT_KEEP = {"Thickness": (TOP_CENTER[0] + HALF_X + 0.016, FRONT_CENTER[1])}
REFERENCE_DIMENSIONS = ("Thickness",)
DIMENSION_CALLOUTS = {"Thickness": "NOMINAL STACK", "SlotWidth": "SLOT, FULL R"}

# Radius-centre location from the closed (right) edge and the lower edge.
# Each value sits midway along its span, off both witnesses (the tip block's
# 5637ac42 lesson).
SLOT_X_TEXT = (TOP_CENTER[0] + HALF_X / 2.0, TOP_CENTER[1] - HALF_Z - 0.012)
SLOT_Z_TEXT = (TOP_CENTER[0] + HALF_X + 0.010, TOP_CENTER[1] - HALF_Z / 2.0)
NOTES_XY = (0.190, 0.120)


def _slot_end_xy(angle_deg: float) -> tuple[float, float]:
    """A point on the plan view's full-radius end, which spans -90..+90 deg."""
    if abs(angle_deg) >= 90.0:
        raise ValueError(f"{angle_deg} deg is off the slot's closed end")
    r = SLOT_R * _S
    a = math.radians(angle_deg)
    return (TOP_CENTER[0] + r * math.cos(a), TOP_CENTER[1] + r * math.sin(a))


def _checked_location(
    adapter: Any,
    view: Any,
    *,
    edge_xy: tuple[float, float],
    text_xy: tuple[float, float],
    orientation: str,
    expected_mm: float,
    label: str,
) -> Any:
    display = add_edge_dimension(
        adapter,
        view,
        p0=edge_xy,
        p1=_slot_end_xy(-45.0),
        text_xy=text_xy,
        label=label,
        orientation=orientation,
    )
    display = _early_bound(display, "IDisplayDimension")
    measured = float(_early_bound(display.GetDimension2(0), "IDimension").SystemValue)
    if abs(measured * 1000.0 - expected_mm) > 1e-4:
        raise RuntimeError(
            f"{label} measured {measured * 1000.0:.4f} mm, expected {expected_mm:.4f}"
        )
    return display


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-tip-shim source", await adapter.open_model(str(SOURCE)))
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
            0: "Cone Tip Shim Pack Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone tip shim pack; fit-up stack; shim stock",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=SHEET_SCALE)
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=SHEET_SCALE)
    for view in (top, front, iso):
        set_hidden_lines_removed(adapter, view)

    top_annotations = curate_view_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="plan",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="stack edge",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*top_annotations, *front_annotations]
    set_reference_dimensions(adapter, annotations, REFERENCE_DIMENSIONS)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)

    _checked_location(
        adapter,
        top,
        edge_xy=(TOP_CENTER[0] + HALF_X, TOP_CENTER[1] + HALF_Z / 2.0),
        text_xy=SLOT_X_TEXT,
        orientation="horizontal",
        expected_mm=SHIM_X / 2.0,
        label="slot radius centre from the closed edge",
    )
    _checked_location(
        adapter,
        top,
        edge_xy=(TOP_CENTER[0] + HALF_X / 2.0, TOP_CENTER[1] - HALF_Z),
        text_xy=SLOT_Z_TEXT,
        orientation="vertical",
        expected_mm=SHIM_Z / 2.0,
        label="slot radius centre from the lower edge",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)

    for view in (top, front):
        set_hidden_lines_removed(adapter, view)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Tip Shim Pack Manufacturing Drawing",
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
