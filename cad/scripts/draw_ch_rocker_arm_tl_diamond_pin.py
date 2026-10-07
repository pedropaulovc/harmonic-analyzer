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
    add_view_centerline,
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from ch_rocker_arm_tl_diamond_pin_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
)
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
# The turned profile (Top view: axis vertical, lands up as fitted) carries
# every body size: all axial sizes from the neck face, each diameter beside
# its own step. Hidden lines show the reamed bore and the bonded pin in it.
# The end view looks down on the lands (Back view) and keeps the two pin
# sizes, the round lands and the flats; it also donates the neck and ream
# diameters. The Front view only donates the collar and shank diameters and
# is deleted.
PROFILE_CENTER = (0.150, 0.150)
END_CENTER = (0.270, 0.205)
DONOR_CENTER = (0.055, 0.240)
ISO_CENTER = (0.335, 0.105)
ISO_NOTE_XY = (0.300, 0.055)
PROFILE_KEEP = {
    "LandHeight": (0.185, 0.200),
    "NeckLength": (0.185, 0.180),
    "CollarEnd": (0.200, 0.162),
    "OverallLength": (0.215, 0.143),
    "ReamDepth": (0.230, 0.170),
}
END_KEEP = {
    "LandDia": (0.300, 0.235),
    "FlatsAF": (0.270, 0.245),
    "NeckDia": (0.240, 0.230),
    "ReamDia": (0.240, 0.180),
}
DONOR_KEEP = {
    "CollarDia": (0.055, 0.265),
    "ShankDia": (0.055, 0.215),
}
PROFILE_DIAMETER_XY = {
    "NeckDia": (0.105, 0.182),
    "ReamDia": (0.100, 0.160),
    "CollarDia": (0.105, 0.140),
    "ShankDia": (0.105, 0.110),
}


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

    donor = place_view(adapter, str(SOURCE), "*Front", *DONOR_CENTER, scale=VIEW_SCALE)
    profile = place_view(adapter, str(SOURCE), "*Top", *PROFILE_CENTER, scale=VIEW_SCALE)
    end = place_view(adapter, str(SOURCE), "*Back", *END_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (donor, end):
        set_hidden_lines_removed(adapter, view)
    set_hidden_lines_visible(adapter, profile)

    donor_annotations = curate_view_dimensions(
        adapter,
        donor,
        keep=DONOR_KEEP,
        view_label="collar and shank donor",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    end_annotations = curate_view_dimensions(
        adapter,
        end,
        keep=END_KEEP,
        view_label="land end view",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    profile_annotations = curate_view_dimensions(
        adapter,
        profile,
        keep=PROFILE_KEEP,
        view_label="turned profile",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    moved = []
    kept_on_end = []
    for source, source_annotations in ((donor, donor_annotations), (end, end_annotations)):
        for annotation in source_annotations:
            name = dimension_name(adapter, annotation)
            if name in PROFILE_DIAMETER_XY:
                moved.append(
                    _move_dimension(
                        adapter, annotation, profile, PROFILE_DIAMETER_XY[name],
                        source_view=source,
                    )
                )
            else:
                kept_on_end.append(annotation)
    donor_name = view_name(adapter, donor)
    delete_view(adapter, donor)
    if any(view_name(adapter, view) == donor_name for view in iter_views(adapter)):
        raise RuntimeError("failed to delete the empty diameter donor view")

    annotations = [*moved, *kept_on_end, *profile_annotations]
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    add_view_centerline(
        adapter, profile, face_xy=PROFILE_CENTER, label="pin turning axis"
    )
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.070)
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
