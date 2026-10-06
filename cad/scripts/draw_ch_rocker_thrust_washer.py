r"""Create the manufacturing drawing for the rocker-bank south thrust washer (MHA-CH-009)."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from ch_rocker_thrust_washer_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    STOCK_TEXT_PREFIX,
    STOCK_TEXT_SUFFIX,
    THICKNESS,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["ch_rocker_thrust_washer"]
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

# A O10.2 x 1/16 washer: 4:1 keeps both diameters and the thickness legible
# without crowding the landscape sheet.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
FRONT_CENTER = (0.110, 0.180)
RIGHT_CENTER = (0.200, 0.180)
ISO_CENTER = (0.320, 0.180)

DRAWING_PRECISION_BY_NAME = {
    name: digits
    for names in DRAWING_PRECISION.values()
    for name, digits in names.items()
}

FRONT_KEEP = {
    "DiscDia": (0.060, 0.240),
    "BoreDia": (0.150, 0.240),
}
RIGHT_KEEP = {
    "DiscThick": (0.235, 0.225),
}

# The faces carry no finish symbol (Main 2026-09-26): they are the 1/16
# sheet's as supplied, and the title block's surface row is a process
# statement, not a roughness number, so nothing reimposes one.


def _set_stock_text(adapter: Any, annotations: list[Any]) -> None:
    """Print the thickness as the stock's: "1/16 (1.59) STOCK".

    The washer is cut from 1/16 in stock (user ruling, 2026-09-26), so the
    mill's tolerance governs the thickness, not the .XX row. Prefix and
    suffix, not a whole-text override: the value between them stays the
    model's dimension at its model-owned places, and the parentheses mark it
    as reference.
    """
    for annotation in annotations:
        if dimension_name(adapter, annotation) != "DiscThick":
            continue
        annotation = _early_bound(annotation, "IAnnotation")
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        if abs(float(dimension.SystemValue) - THICKNESS / 1000.0) > 1e-9:
            raise RuntimeError(
                f"washer thickness {float(dimension.SystemValue)!r} m "
                f"is not the modelled {THICKNESS} mm"
            )
        display.SetText(1, STOCK_TEXT_PREFIX)  # swDimensionTextPrefix
        display.SetText(2, STOCK_TEXT_SUFFIX)  # swDimensionTextSuffix
        readback = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
        if readback != (STOCK_TEXT_PREFIX, STOCK_TEXT_SUFFIX):
            raise RuntimeError(f"washer stock text did not persist: {readback!r}")
        rebuild_drawing(adapter, label="washer stock thickness text")
        return
    raise RuntimeError("washer edge view has no DiscThick dimension to label")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open rocker-thrust-washer source", await adapter.open_model(str(SOURCE)))
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
            0: "Rocker Bank Thrust Washer Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker bank south thrust washer; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        *curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="front",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            right,
            keep=RIGHT_KEEP,
            view_label="right",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _set_stock_text(adapter, annotations)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the washer face view")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        spec=SPEC,
        pdf_title="Rocker Bank Thrust Washer Manufacturing Drawing",
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
