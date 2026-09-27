r"""Create the curated machinist drawing for the pinion cam-follower pin.

A short Ø4 drill-rod stud with a shallow domed outer end, bonded into the
MHA-056 strap's follower seat.  The sheet runs at 8:1 so the 20.8-long pin
reads at arm's length.  The side view lies as the pin is turned (rule 7) and
carries every dimension: the diameter, the length, the crown radius and a
reference overall.  The end view projects to its left (third angle), and a
4:1 isometric sits clear of the title block.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_cam_pin.py pinion-cam-pin
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
    add_surface_finish,
    add_view_centerline,
    assert_imported_precision,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_max,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from pinion_cam_pin_spec import (
    CAP_RADIUS,
    CAP_SAG,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    PIN_DIA as PIN_DIA,
    PIN_DIA_CALLOUT,
    PIN_LEN,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_cam_pin"]
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

# Machinist review of 7f7fc1717: the end view sat beside a vertical
# elevation, out of projection, and alone carried the diameter.  The *Right
# side view now lays the pin as it is turned (model +Z to the left: the crown
# on the left, the seated end on the right) and its Right-plane profiles put
# the diameter, the length and the crown radius on it.  Third angle: the
# *Front end view looks at the crown end, so it projects to the LEFT and
# shares the side view's Y station.  Its bbox centre is the pin's mid-length.
SHEET_SCALE = (8.0, 1.0)
_S = SHEET_SCALE[0] / 1000.0
OVERALL = PIN_LEN + CAP_SAG
RIGHT_CENTER = (0.235, 0.165)
FRONT_CENTER = (0.065, RIGHT_CENTER[1])
ISO_CENTER = (0.375, 0.215)
ISO_NOTE_XY = (0.340, 0.178)
HALF_DIA = PIN_DIA / 2.0 * _S


def side_view_x(z_mm: float) -> float:
    """Sheet X of model station ``z_mm`` on the side view (+Z runs left)."""
    return RIGHT_CENTER[0] - (z_mm - OVERALL / 2.0) * _S


# Both lengths sit ABOVE the side view (Depth inner, the reference overall
# outer), so every extension line runs up and the crown's radius and
# roughness leaders reach it from the lower left without crossing one.  The
# diameter sits below, its dimension line right of centre so the
# axis-centerline pick at the view's middle lands on bare face.
RIGHT_KEEP = {
    "PinDia": (RIGHT_CENTER[0] + 0.040, RIGHT_CENTER[1] - HALF_DIA - 0.030),
    "Depth": (RIGHT_CENTER[0], RIGHT_CENTER[1] + HALF_DIA + 0.031),
    # Lower left, on the line from the crown centre through its lower flank,
    # so the radius leader lands on the crown below the axis.
    "CapR": (0.105, 0.110),
}
OVERALL_TEXT_XY = (RIGHT_CENTER[0], RIGHT_CENTER[1] + HALF_DIA + 0.059)
# The crown's roughness leader leaves the symbol's shelf end and rises to the
# crown, while its "Ra 1.6" text sits above the shelf to the right of that
# end.  At (0.120, 0.140) the leader climbed 19 mm over 26 mm and ran through
# the "1.6" (pc-r4-860 render; codex machinist review of 7b21b56c0).  Raised
# 10 mm, it climbs 9 mm and passes under the text.
CROWN_FINISH_SYMBOL_XY = (0.120, 0.150)
CROWN_FINISH_FROM_ROOT_MM = 0.7
DIMENSION_CALLOUTS = {
    "PinDia": PIN_DIA_CALLOUT,
    "Depth": "SEATED FLAT END\nTO CROWN ROOT",
    "CapR": "OUTER CROWN",
}


def _crown_point(axial_from_root_mm: float) -> tuple[float, float, float]:
    """Model point on the crown's -Y silhouette (the side view's lower flank),
    measured from the crown root."""
    rise = CAP_RADIUS - CAP_SAG + axial_from_root_mm
    radial = math.sqrt(CAP_RADIUS**2 - rise**2)
    return (0.0, -radial / 1000.0, (PIN_LEN + axial_from_root_mm) / 1000.0)


def _overall_reference(adapter: Any, right: Any) -> None:
    """The (20.80) overall, seated end to crown apex (rule 7, Harvey #25)."""
    label = "cam-pin overall length reference"
    seated_end = model_point_in_view(
        adapter, right, (0.0, PIN_DIA / 4000.0, 0.0), label="cam-pin seated end"
    )
    apex = model_point_in_view(
        adapter, right, (0.0, 0.0, OVERALL / 1000.0), label="cam-pin crown apex"
    )
    display = add_edge_dimension(
        adapter,
        right,
        p0=seated_end,
        p1=apex,
        text_xy=OVERALL_TEXT_XY,
        label=label,
        orientation="horizontal",
        entity_types=("EDGE", "SILHOUETTE"),
    )
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    measured_mm = abs(float(dimension.SystemValue) * 1000.0)
    if abs(measured_mm - OVERALL) > 1e-4:
        # A line-to-arc pick may resolve to the crown's centre; the overall
        # runs to its far extreme.
        set_arc_endpoints_to_max(adapter, display, label=label)
        measured_mm = abs(float(dimension.SystemValue) * 1000.0)
    if abs(measured_mm - OVERALL) > 1e-4:
        raise RuntimeError(f"{label} measured {measured_mm:g}, expected {OVERALL:g}")
    set_reference_dimension(adapter, display.GetAnnotation(), label=label)
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != DRAWING_REFERENCE_PRECISION:
        raise RuntimeError(f"{label} precision did not persist")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-cam-pin source", await adapter.open_model(str(SOURCE)))
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
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pinion Cam-Follower Pin Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion cam-follower pin; drill-rod stud; steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(8, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(8, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(4, 1))
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    # The end view is a bare circle with its center mark: every dimension
    # lives on the Right-plane profiles and imports into the side view only.
    annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to pin end view")

    # Before the centreline, so the apex pick cannot land on the axis line.
    _overall_reference(adapter, right)
    add_view_centerline(
        adapter,
        right,
        face_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] + 0.004),
        label="pinion cam-pin shank axis centerline",
    )
    # Rule 5: the crown rides the cam, so it carries the one roughness symbol.
    # Its leader meets the crown's lower flank near the apex from the lower
    # left, above the CapR leader (which lands further round the crown).
    crown_finish_point = model_point_in_view(
        adapter,
        right,
        _crown_point(CROWN_FINISH_FROM_ROOT_MM),
        label="cam-pin crown finish point",
    )
    add_surface_finish(
        adapter,
        right,
        edge_xy=crown_finish_point,
        symbol_xy=CROWN_FINISH_SYMBOL_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "crown"),
        label="cam-pin crown finish",
        entity_type="SILHOUETTE",
        char_height=0.0025,  # the pivot-block size; the default read oversized at 8:1
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.058)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Cam-Follower Pin Manufacturing Drawing",
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
