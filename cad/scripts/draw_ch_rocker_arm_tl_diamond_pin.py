r"""Create the drawing for the rocker arm's rod-hole diamond pin (MHA-CH-006-TL-03)."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    assert_imported_precision,
    create_section_view,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _section_axis import create_section_axis_centerline, position_section_caption
from ch_rocker_arm_tl_diamond_pin_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    LAND_HEIGHT,
    OVERALL_LENGTH,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import delete_view, iter_views, place_view

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_diamond_pin"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A O4.5 x 18.6 pin: 6:1 keeps the 1.76 flats and every step legible.
SHEET_SCALE = (6.0, 1.0)
VIEW_SCALE = (6, 1)
ISO_SCALE = (4, 1)
# Longitudinal section A-A (cut vertically through the land end view) is the
# main view: it shows the body and the bonded gauge pin as cut solids, the
# reamed bore the pin sits in and the one-piece neck/collar/shank. The
# section's axis lies horizontally; which end the lands fall on is read from
# the view transform at run time, so every text position below is given in
# (axial station from the neck face mm, sheet offset from the axis m).
# The *Top donor gives the axial sizes (all from the neck face), the *Front
# donor the body diameters; both are deleted. The end view keeps the lands.
SECTION_CENTER = (0.165, 0.175)
END_CENTER = (0.335, 0.200)
TOP_DONOR_CENTER = (0.060, 0.235)
FRONT_DONOR_CENTER = (0.300, 0.250)
ISO_CENTER = (0.330, 0.120)
ISO_NOTE_XY = (0.300, 0.088)
CAPTION_XY = (0.150, 0.122)
CUT_HALF = 0.020  # past the O4.5 collar's 13.5 mm sheet radius
AXIAL_XY = {
    "LandHeight": (-1.2, 0.022),
    "NeckLength": (2.2, 0.022),
    "ReamDepth": (4.0, 0.030),
    "CollarEnd": (5.1, 0.038),
    "OverallLength": (8.0, 0.046),
}
DIAMETER_XY = {
    "NeckDia": (1.0, -0.026),
    "CollarDia": (6.0, -0.038),
    "ReamDia": (8.6, -0.026),
    "ShankDia": (13.5, -0.026),
}
END_KEEP = {
    "LandDia": (0.375, 0.225),
    "FlatsAF": (0.335, 0.232),
}


def _section_mapper(adapter: Any, section: Any):
    """Return (station mm from the neck face, sheet offset m) -> sheet xy.

    The station runs along the pin axis in the section, whichever way the
    section lays it; the offset is perpendicular to the axis on the sheet.
    """
    view = _early_bound(section, "IView")
    transform = _early_bound(view.ModelToViewTransform, "IMathTransform")
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")

    def sheet(z_mm: float) -> tuple[float, float]:
        point = _early_bound(
            math_utility.CreatePoint(double_array([0.0, 0.0, z_mm / 1000.0])), "IMathPoint"
        )
        data = _early_bound(point.MultiplyTransform(transform), "IMathPoint").ArrayData
        return float(data[0]), float(data[1])

    origin, far = sheet(0.0), sheet(OVERALL_LENGTH)
    if abs(far[1] - origin[1]) > 1e-4:
        raise RuntimeError(f"section A-A does not lay the pin axis horizontally: {origin} {far}")

    def to_sheet(station_mm: float, offset_m: float) -> tuple[float, float]:
        x, y = sheet(station_mm)
        return x, y + offset_m

    return to_sheet


def _move_dimension(
    adapter: Any,
    annotation: Any,
    target: Any,
    text_xy: tuple[float, float],
    *,
    source_view: Any,
) -> Any:
    """Move a native model dimension and verify its new drawing-view owner."""
    name = dimension_name(adapter, annotation)
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, source_view)):
        raise RuntimeError(f"{name}: failed to activate source dimension view")
    draw.ClearSelection2(True)
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    selection_name = str(display.GetNameForSelection() or "")
    if not selection_name or not draw.Extension.SelectByID2(
        selection_name, "DIMENSION", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"failed to select model dimension {name}: {selection_name!r}")
    drawing.DragModelDimension(view_name(adapter, target), 2, text_xy[0], text_xy[1], 0.0)
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

    check("open diamond-pin source", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Manufacturing Notes",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Rod Diamond Pin Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker rod diamond pin; bonded gauge-pin lands; MHA-CH-006-TL-03",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    end = place_view(adapter, str(SOURCE), "*Back", *END_CENTER, scale=VIEW_SCALE)
    section = create_section_view(
        adapter,
        end,
        line_start=(END_CENTER[0], END_CENTER[1] - CUT_HALF),
        line_end=(END_CENTER[0], END_CENTER[1] + CUT_HALF),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="diamond-pin longitudinal section",
    )
    position_section_caption(adapter, section, CAPTION_XY, label="diamond pin")
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_DONOR_CENTER, scale=VIEW_SCALE)
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_DONOR_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (end, section, top, front):
        set_hidden_lines_removed(adapter, view)

    to_sheet = _section_mapper(adapter, section)
    donors = (
        (top, {name: (0.0, 0.0) for name in AXIAL_XY}, AXIAL_XY, "axial donor"),
        (front, {name: (0.0, 0.0) for name in DIAMETER_XY}, DIAMETER_XY, "diameter donor"),
    )
    moved = []
    for donor, keep, targets, label in donors:
        for annotation in curate_view_dimensions(
            adapter, donor, keep=keep, view_label=label,
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ):
            name = dimension_name(adapter, annotation)
            moved.append(
                _move_dimension(
                    adapter, annotation, section, to_sheet(*targets[name]), source_view=donor
                )
            )
    for donor in (top, front):
        donor_name = view_name(adapter, donor)
        delete_view(adapter, donor)
        if any(view_name(adapter, view) == donor_name for view in iter_views(adapter)):
            raise RuntimeError(f"failed to delete the empty donor view {donor_name}")
    kept_on_end = curate_view_dimensions(
        adapter, end, keep=END_KEEP, view_label="land end view",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )

    annotations = [*moved, *kept_on_end]
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    create_section_axis_centerline(
        adapter, section, length_mm=OVERALL_LENGTH + LAND_HEIGHT, label="pin turning axis"
    )
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.075)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Rod Diamond Pin Drawing",
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
