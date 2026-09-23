r"""Create the curated machinist drawing for the cone-tip spacer bushing.

Recreated under ``cad/docs/drawing-simplicity-policy.md``. A plain sleeve uses
two orthographic views plus an isometric and three native model dimensions --
OD, reamed bore, and length -- with one fit-identification note. The OD and
the length sit on the side view (policy rule 7, turned parts: diameters on the
side view); the end view keeps only the reamed-bore callout and its finish, so
no two diametric leaders cross at the centre. There are no
datums or feature-control frames: a spacer bushing is not on the GD&T allowlist,
and the retired OD-runout and end-face-parallelism frames said nothing a hobby
shop could hold that turning the OD, bore, and faces in one chucking does not
already give. The sole roughness symbol is rule 5's running-surface case: the
bore runs on the shaft's tip journal. Decimal places are the part's
(``cone_tip_bushing_spec.DRAWING_PRECISION``, applied natively by
``build_cone_tip_bushing``); this script only reads them back off the sheet.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    add_surface_finish,
    add_view_centerline,
    assert_imported_precision,
    check_drawing_layout,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    rebuild_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from cone_tip_bushing_spec import (
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    LENGTH,
    OUTER_DIA,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["cone_tip_bushing"]
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

# O6 x 4 is tiny: 8:1 puts the end-view circle at O48 on the sheet, matching
# the lever-bushing print's read (O12 at 4:1). The part is extruded from the
# Top plane (axis along Y), so the circular end view is *Top and the side
# view is *Front (axis vertical on the sheet).
SHEET_SCALE = (8.0, 1.0)
VIEW_SCALE = (8, 1)
# The group sits at mid-height with the fit note just below it, so the usable
# field is balanced instead of leaving an empty band under high views (codex).
END_CENTER = (0.085, 0.160)
SIDE_CENTER = (0.190, 0.160)
ISO_CENTER = (0.315, 0.170)
MANUFACTURING_NOTES_POS = (0.022, 0.115)

OUTER_R = OUTER_DIA * VIEW_SCALE[0] / 2000.0  # 0.024
BORE_R = BORE_DIA * VIEW_SCALE[0] / 2000.0  # 0.00635

HALF_LENGTH = LENGTH * VIEW_SCALE[0] / 2000.0  # 0.016: side view half height

# The circle's ODDim imports only on the end view (its sketch plane), so it is
# imported there as a donor and dragged onto the side view -- the pattern the
# cone-gear-shaft sheet proved natively.  The ~33 mm stacked bore callout is
# centred right of and below the OD circle, clear of it and of the side view.
END_KEEP = {
    "ODDim": (END_CENTER[0] - 0.040, END_CENTER[1] + 0.030),
    "BoreDiaDim": (
        END_CENTER[0] + OUTER_R + 0.022,
        END_CENTER[1] - 0.020,
    ),
}
SIDE_KEEP = {
    "Depth": (SIDE_CENTER[0] + 0.036, SIDE_CENTER[1]),
}
# Horizontal OD dimension above the side view (axis vertical on the sheet).
SIDE_OD_XY = (SIDE_CENTER[0], SIDE_CENTER[1] + HALF_LENGTH + 0.010)
# Surface-finish symbol (anchor = lower-left of the glyph) above-right of the
# end view; its leader lands on the bore's right quadrant, away from the bore
# callout's lower-right leader and left of the side view.
BORE_FINISH_XY = (END_CENTER[0] + OUTER_R + 0.006, END_CENTER[1] + 0.012)
DIMENSION_CALLOUTS = {
    "BoreDiaDim": "REAM THRU",
}


def _move_dimension(
    adapter: Any,
    annotation: Any,
    target: Any,
    text_xy: tuple[float, float],
    *,
    source_view: Any,
) -> Any:
    """Move, never copy, a model dimension and verify its new owner view."""
    name = dimension_name(adapter, annotation)
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, source_view)):
        raise RuntimeError(f"{name}: failed to activate source dimension view")
    draw.ClearSelection2(True)
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    selection_name = str(display.GetNameForSelection() or "")
    if not selection_name or not draw.Extension.SelectByID2(
        selection_name, "DIMENSION", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(
            f"failed to select model dimension {name}: {selection_name!r}"
        )
    ddoc.DragModelDimension(view_name(adapter, target), 2, text_xy[0], text_xy[1], 0.0)
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    annotations = [
        _early_bound(item, "IAnnotation")
        for item in (_early_bound(target, "IView").GetAnnotations() or ())
    ]
    matches = [item for item in annotations if dimension_name(adapter, item) == name]
    if len(matches) != 1:
        raise RuntimeError(f"{name}: native dimension did not move into target view")
    return matches[0]


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-tip-bushing source", await adapter.open_model(str(SOURCE)))
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
            0: "Cone Tip Bushing Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone tip bushing; turned spacer; brass",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    end = place_view(adapter, str(SOURCE), "*Top", *END_CENTER, scale=VIEW_SCALE)
    side = place_view(adapter, str(SOURCE), "*Front", *SIDE_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    # The end view and native REAM THRU callout fully define the bore; dashed
    # bore lines in the side view add no manufacturing fact.
    for view in (end, side, iso):
        set_hidden_lines_removed(adapter, view)

    end_annotations = curate_view_dimensions(
        adapter,
        end,
        keep=END_KEEP,
        view_label="end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    bore_annotations = [
        annotation
        for annotation in end_annotations
        if dimension_name(adapter, annotation) == "BoreDiaDim"
    ]
    od_annotations = [
        annotation
        for annotation in end_annotations
        if dimension_name(adapter, annotation) == "ODDim"
    ]
    if len(bore_annotations) != 1 or len(od_annotations) != 1:
        raise RuntimeError("end view must import exactly one OD and one bore dimension")
    od_annotation = _move_dimension(
        adapter, od_annotations[0], side, SIDE_OD_XY, source_view=end
    )
    annotations = [*bore_annotations, *side_annotations, od_annotation]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to end view")
    # Axis centerline of the OD cylinder in the side view, selected through its
    # projected cylindrical face rather than by a hidden bore edge.
    add_view_centerline(
        adapter,
        side,
        face_xy=(SIDE_CENTER[0] - 0.012, SIDE_CENTER[1]),
        label="bushing side-view axis centerline",
    )

    # Above-right of the end view: right of the OD circle (x <= 0.109), above
    # the bore callout (top ~0.147) and left of the side view (x >= 0.166).
    # Same glyph height as the cone-gear sheets -- the default rendered ~2x
    # every other annotation (codex/eye pass, 2026-09-23).
    add_surface_finish(
        adapter,
        end,
        edge_xy=(END_CENTER[0] + BORE_R, END_CENTER[1]),
        symbol_xy=BORE_FINISH_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "bushing_bore"),
        label="bushing bore finish",
        char_height=0.0025,
    )

    add_property_linked_note(adapter, "Manufacturing Notes", *MANUFACTURING_NOTES_POS)
    rebuild_drawing(adapter, label="cone-tip-bushing layout audit")
    check_drawing_layout(adapter, layout=SPEC.layout, stem=PART_STEM)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Tip Bushing Manufacturing Drawing",
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
