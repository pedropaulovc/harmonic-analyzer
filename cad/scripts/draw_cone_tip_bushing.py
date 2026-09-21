r"""Create the curated machinist drawing for the cone-tip spacer bushing.

Recreated under ``cad/docs/drawing-simplicity-policy.md``. A plain sleeve uses
two orthographic views plus an isometric and three native model dimensions --
OD, reamed bore, and length -- with one fit-identification note. There are no
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
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    add_surface_finish,
    add_view_centerline,
    assert_imported_precision,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from cone_tip_bushing_spec import (
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    OUTER_DIA,
    SURFACE_FINISHES,
)
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
END_CENTER = (0.085, 0.190)
SIDE_CENTER = (0.190, 0.190)
ISO_CENTER = (0.315, 0.205)
MANUFACTURING_NOTES_POS = (0.022, 0.095)

OUTER_R = OUTER_DIA * VIEW_SCALE[0] / 2000.0  # 0.024
BORE_R = BORE_DIA * VIEW_SCALE[0] / 2000.0  # 0.00635

END_KEEP = {
    "ODDim": (
        END_CENTER[0] - 0.035,
        END_CENTER[1] + 0.010,
    ),
    "BoreDiaDim": (
        END_CENTER[0] + OUTER_R + 0.005,
        END_CENTER[1] - 0.010,
    ),
}
SIDE_KEEP = {
    "Depth": (SIDE_CENTER[0] + 0.036, SIDE_CENTER[1]),
}
DIMENSION_CALLOUTS = {
    "BoreDiaDim": "REAM THRU",
}


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
    annotations = [*end_annotations, *side_annotations]
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

    # Right of the end view at just above bore height. The symbol's ARM
    # extends left of the anchor and its TEXT renders ABOVE the arm and to the
    # RIGHT (ASME Y14.36), so it occupies roughly x=0.112..0.151 / y=0.200..0.215
    # -- right of the OD circle (which ends at x=0.109), clear of the
    # BoreDiaDim callout below it and well left of the side view (x=0.166).
    add_surface_finish(
        adapter,
        end,
        edge_xy=(END_CENTER[0] + BORE_R, END_CENTER[1]),
        symbol_xy=(0.115, 0.200),
        control=surface_finish_by_key(SURFACE_FINISHES, "bushing_bore"),
        label="bushing bore finish",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", *MANUFACTURING_NOTES_POS)
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
