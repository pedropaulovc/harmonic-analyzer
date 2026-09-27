r"""Create the curated machinist drawing for the pinion cam-follower pin.

A short Ø4 drill-rod stud with a shallow domed outer end, bonded into the
MHA-056 strap's follower seat.  The sheet runs at 8:1 so the 20.8-long pin
reads at arm's length: the end view carries the diameter, the side elevation
carries the length, the crown radius and a reference overall, and a 4:1
isometric sits clear of the title block.

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
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_max,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from pinion_cam_pin_spec import (
    CAP_RADIUS,
    CAP_SAG,
    DRAWING_REFERENCE_PRECISION,
    PIN_DIA as PIN_DIA,
    PIN_LEN,
    SEAT_NUMBER,
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

# Fable review r4: at 4:1 the pin sat bunched in the top half with a dead
# field below.  At 8:1 the vertical side elevation spans most of the sheet's
# height; the end view keeps its upper-left corner and the notes the
# lower-left strip under the reference overall.
SHEET_SCALE = (8.0, 1.0)
_S = SHEET_SCALE[0] / 1000.0
OVERALL = PIN_LEN + CAP_SAG
FRONT_CENTER = (0.075, 0.200)
# The *Top elevation stands the pin axis up the sheet: seated end on top,
# crown at the bottom.  Its bbox centre is the pin's mid-length.
RIGHT_CENTER = (0.250, 0.160)
ISO_CENTER = (0.360, 0.205)


# r6 eye-pass: at (0.035, 0.255) the four-line callout stacked up past the
# sheet border; below the end view it has the whole left field.
FRONT_KEEP = {
    "PinDia": (0.060, 0.150),
}
# Both lengths sit LEFT of the elevation (Depth inner, the reference overall
# outer) so the crown's radius and roughness leaders reach it from the right
# without crossing a dimension line.
RIGHT_KEEP = {
    "Depth": (0.205, 0.150),
    # Level with the crown centre and well outside the R2.90 circle: nearer,
    # the arc extension ran through OUTER CROWN.
    "CapR": (0.307, 0.100),
}
OVERALL_TEXT_XY = (0.160, 0.165)
DIMENSION_CALLOUTS = {
    "PinDia": f"DRILL ROD; SLIP FIT IN\n{SEAT_NUMBER} FOLLOWER SEAT",
    "Depth": "SEATED FLAT END\nTO CROWN ROOT",
    "CapR": "OUTER CROWN",
}


def _crown_point(axial_from_root_mm: float) -> tuple[float, float, float]:
    """Model point on the crown's +X silhouette, measured from the crown root."""
    rise = CAP_RADIUS - CAP_SAG + axial_from_root_mm
    radial = math.sqrt(CAP_RADIUS**2 - rise**2)
    return (radial / 1000.0, 0.0, (PIN_LEN + axial_from_root_mm) / 1000.0)


def _overall_reference(adapter: Any, right: Any) -> None:
    """The (20.80) overall, seated end to crown apex (rule 7, Harvey #25)."""
    label = "cam-pin overall length reference"
    seated_end = model_point_in_view(
        adapter, right, (PIN_DIA / 4000.0, 0.0, 0.0), label="cam-pin seated end"
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
        orientation="vertical",
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
    right = place_view(adapter, str(SOURCE), "*Top", *RIGHT_CENTER, scale=(8, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(4, 1))
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    set_dimension_callouts(
        adapter, [*front_annotations, *right_annotations], DIMENSION_CALLOUTS
    )
    set_dimension_precision(adapter, front_annotations, {"PinDia": 2})
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
    # Its leader meets the crown near the apex from the right, below the
    # CapR leader (which lands at mid-sag).
    crown_finish_point = model_point_in_view(
        adapter, right, _crown_point(0.7), label="cam-pin crown finish point"
    )
    add_surface_finish(
        adapter,
        right,
        edge_xy=crown_finish_point,
        symbol_xy=(0.300, 0.075),
        control=surface_finish_by_key(SURFACE_FINISHES, "crown"),
        label="cam-pin crown finish",
        entity_type="SILHOUETTE",
        char_height=0.0025,  # the pivot-block size; the default read oversized at 8:1
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.058)
    add_property_linked_note(adapter, "Isometric View Note", 0.325, 0.160)

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
