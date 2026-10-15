r"""Create the manufacturing drawing for the rocker-bank thrust washer (MHA-CH-009)."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_leaders import (
    assert_leaders_clear,
    dimension_segments,
    set_near_side_diameter,
)
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from ch_rocker_thrust_washer_spec import (
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    OD,
    STOCK_TEXT_PREFIX,
    STOCK_TEXT_SUFFIX,
    THICKNESS,
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

# A O10.2 x 1/32 washer: 4:1 keeps both diameters and the thickness legible
# without crowding the landscape sheet. The group sits 35 mm lower than it
# first did: at y 0.180 it left a dead field under it (PR #1317 machinist
# review).
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
FRONT_CENTER = (0.110, 0.145)
RIGHT_CENTER = (0.200, 0.145)
ISO_CENTER = (0.320, 0.145)

DRAWING_PRECISION_BY_NAME = {
    name: digits
    for names in DRAWING_PRECISION.values()
    for name, digits in names.items()
}

FRONT_KEEP = {
    "DiscDia": (0.060, 0.205),
    "BoreDia": (0.150, 0.205),
}
RIGHT_KEEP = {
    "DiscThick": (0.235, 0.190),
}
# drawing-guidelines.md rule 12 (hole and slot callouts say what to do): a hole callout states its process. The bore is a drilled running
# clearance on the shaft, so the title block's DRILLED HOLES row is its band
# (PR #1317 machinist review).
BORE_CALLOUT = "DRILL THRU"

# drawing-guidelines.md rule 14 (keep text off the part): native, each diameter's line ran rim to rim
# through the centre, so the two crossed in the bore (Opus #1022 baseline
# clarity). Each takes one arrow on its near rim (set_near_side_diameter):
# the OD's on its upper left, the bore's on its upper right, and neither
# reaches the centre.
NEAR_SIDE_DIAMETERS = ("DiscDia", "BoreDia")
_SHEET_PER_MODEL_MM = VIEW_SCALE[0] / (VIEW_SCALE[1] * 1000.0)
OD_SHEET_RADIUS = OD * _SHEET_PER_MODEL_MM / 2.0
BORE_SHEET_RADIUS = BORE_DIA * _SHEET_PER_MODEL_MM / 2.0
# Where each leader must END, from the washer centre (sheet metres): on its
# own rim. A reading outside the band means the segments are not sheet metres.
LEADER_LANDING = {
    "DiscDia": (0.9 * OD_SHEET_RADIUS, 1.1 * OD_SHEET_RADIUS),
    "BoreDia": (0.8 * BORE_SHEET_RADIUS, 1.2 * BORE_SHEET_RADIUS),
}
# No OD ink inside the ring; no bore ink across the bore's centre half.
LEADER_KEEP_OUT = {
    "DiscDia": 0.9 * OD_SHEET_RADIUS,
    "BoreDia": 0.5 * BORE_SHEET_RADIUS,
}
# The stated wall (spec WALL_NOTE), lower left, clear of the views and the
# title block.
NOTES_XY = (0.025, 0.090)

# The faces carry no finish symbol (Main 2026-09-26): they are the stock
# sheet's as supplied, and the title block's surface row is a process
# statement, not a roughness number, so nothing reimposes one.


def _set_stock_text(adapter: Any, annotations: list[Any]) -> None:
    """Print the thickness as the stock's, e.g. "1/32 (0.79) STOCK".

    The washer is cut from 1/32 in stock (user, 2026-10-10; the stock ruling
    2026-09-26), so the
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


def _named(adapter: Any, annotations: list[Any], name: str) -> Any:
    matches = [a for a in annotations if dimension_name(adapter, a) == name]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {name} dimension, found {len(matches)}")
    return matches[0]


def _near_side_diameters_clear(
    adapter: Any, front: Any, annotations: list[Any]
) -> None:
    """Restyle both face-view diameters to their near rims and prove that
    neither crosses the other nor reaches the centre."""
    named = {name: _named(adapter, annotations, name) for name in NEAR_SIDE_DIAMETERS}
    for name, annotation in named.items():
        set_near_side_diameter(annotation, f"washer {name}")
    rebuild_drawing(adapter, label="washer near-side diameters")
    assert_leaders_clear(
        {name: dimension_segments(annotation) for name, annotation in named.items()},
        centre=model_point_in_view(adapter, front, (0.0, 0.0, 0.0), label="washer centre"),
        keep_out=LEADER_KEEP_OUT,
        lands_within=LEADER_LANDING,
        label="washer face diameters",
    )


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
            0: "Rocker Bank Thrust Washer Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker bank thrust washers, north and south; 1/32 steel sheet",
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
    set_dimension_callouts(adapter, annotations, {"BoreDia": BORE_CALLOUT})
    _near_side_diameters_clear(adapter, front, annotations)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the washer face view")
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
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
