r"""Create the manufacturing drawing for the south cylinder-bank end disc (MHA-DT-26)."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)

from _check import check
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from dt_cylinder_end_disc_spec import (
    BORE_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    THICKNESS_CALLOUT,
    WASHER_OD,
    WASHER_THICK,
)


SPEC = DRAWINGS_BY_NAME["dt_cylinder_end_disc"]
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

# A native axial section puts both turned diameters on solid side-view edges.
# The end view carries only its cutting line and centre mark.
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
FRONT_CENTER = (0.105, 0.175)
SECTION_CENTER = (0.225, 0.175)
ISO_CENTER = (0.350, 0.175)

HALF_OD = WASHER_OD * VIEW_SCALE[0] / (2.0 * VIEW_SCALE[1] * 1000.0)
SECTION_LINE = (
    (FRONT_CENTER[0], FRONT_CENTER[1] - HALF_OD - 0.005),
    (FRONT_CENTER[0], FRONT_CENTER[1] + HALF_OD + 0.005),
)
# Retained native audit/PDF ink from farm run 20261022T062316620Z:
# DiscThick's origin is (225, 255) mm; its three below-layout baselines are
# 257.7781, 252.2219 and 246.6656 mm (5.55625 mm pitch). The extension ends
# at 247.6656 mm strike the last datum row's ink, 247.5996..251.1649 mm.
# Translating that whole block also translates the extension ends; it cannot
# remove the 0.066 mm strike, and the old top ink, 262.2774 mm, has only
# 4.4226 mm to the 266.7 mm border.
# Put the datum ABOVE the native size, not below the extension ends. Only its
# line break becomes a space: every source word, mate identity and control is
# retained. mg_magnifier_assembly_spec documents native run 20261012T185729782Z:
# multiline slot 3 can read back yet print nothing, so use its single-line
# above-callout pattern, not a known-nonprinting two-line block.
# The retained datum-row widths total 129.476 mm, plus a 1.293 mm space;
# reserve a conservative 140 mm lane, x155..295, centred at x225. It lies
# inside x12.7..419.1 and left of the isometric's x303.541 outline.
# Two rows (datum, native size) instead of three retain the y255 origin:
# existing native above-callouts put the first baseline at the origin, then
# the size one 5.55625 mm pitch below it. With the retained ink offsets this
# projects top ink near y259.50, below the old y262.2774 envelope; lowering
# the station is unnecessary. This is a layout estimate, NOT native clearance
# proof: the next farm drawing and machinist review must prove the complete
# visible datum, size, extension-line separation and border containment.
SECTION_KEEP = {
    "DiscDia": (0.195, 0.175),
    "BoreDia": (0.270, 0.175),
    "DiscThick": (0.225, 0.255),
}
# swDimensionTextParts_e compartments for ordinary model display dimensions,
# not Hole Wizard callouts (GetText excludes those). Never replace the native
# value/prefix/suffix or rewrite model-owned precision to rearrange the text.
_CALLOUT_ABOVE = 3
_CALLOUT_BELOW = 4
DIMENSION_CALLOUTS = {
    "BoreDia": (_CALLOUT_BELOW, BORE_CALLOUT),
    "DiscThick": (_CALLOUT_ABOVE, THICKNESS_CALLOUT.replace("\n", " ")),
}


def _set_required_callouts(adapter: Any, annotations: list[Any]) -> None:
    """Refuse export unless the process and datum requirements persist."""
    remaining = dict(DIMENSION_CALLOUTS)
    for annotation in annotations:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetSpecificAnnotation"
        )
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        part, text = remaining[name]
        display = annotation.GetSpecificAnnotation()
        if display is None:
            raise RuntimeError(f"disc dimension {name!r} has no display annotation")
        display = _sw_type_info.early_bound_or_flag(
            display, "IDisplayDimension", "SetText", "GetText"
        )
        # SetText returns void: do not route either call through _attempt,
        # which swallows COM exceptions. DRILL THRU selects the bore limits
        # used by the clearance proof, so an ineffective write must fail too.
        display.SetText(part, text)
        actual = display.GetText(part)
        location = "above" if part == _CALLOUT_ABOVE else "below"
        if actual != text:
            raise RuntimeError(
                f"disc dimension {name!r} {location} callout did not persist: "
                f"{actual!r} != {text!r}"
            )
        del remaining[name]
    if remaining:
        raise RuntimeError(f"disc required callouts missing: {sorted(remaining)}")


def _require_horizontal_axis(adapter: Any, section: Any) -> None:
    south, north = model_points_in_view(
        adapter,
        section,
        ((0.0, 0.0, 0.0), (0.0, 0.0, WASHER_THICK / 1000.0)),
        label="disc turning axis",
        names=("south face", "north face"),
    )
    if abs(north[0] - south[0]) <= 1e-8 or abs(north[1] - south[1]) > 1e-8:
        raise RuntimeError("disc axial section does not have a horizontal turning axis")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cylinder-end-disc source", await adapter.open_model(str(SOURCE)))
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
            0: "Cylinder Bank South End Disc Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cylinder bank south end disc; C36000 brass",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    # Reuse the pinion-sleeve longitudinal-section recipe. The shared helper
    # reads back the exact centre cut; targeted import below must deliver the
    # real model diameters or fail, never substitute numeric drawing text.
    section = create_section_view(
        adapter,
        front,
        line_start=SECTION_LINE[0],
        line_end=SECTION_LINE[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="south end disc axial centre section",
    )
    _require_horizontal_axis(adapter, section)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (front, section, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="disc axial section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _set_required_callouts(adapter, annotations)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the disc face view")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cylinder Bank South End Disc Manufacturing Drawing",
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
