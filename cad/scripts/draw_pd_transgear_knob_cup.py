r"""Create the manufacturing drawing for the transgear knob cup (MHA-PD-016).

The face view is the ``*Top`` orientation, looking into the ring from the
rear: it carries the reamed bore with its process and the note that the
MHA-VN-048 pin hole is drilled at assembly (through cup and journal together,
so it is not dimensioned here).  Section A-A cuts it on the cup axis through
the Front plane, the plane of the turned profile, so the O.D. and the length
print on solid cut edges.  The front face is the running face on the plate's
rear boss and carries its finish.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_surface_finish,
    assert_imported_precision,
    create_section_view,
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
from pd_transgear_knob_cup_spec import (
    BORE_CALLOUT,
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    LENGTH,
    OD,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pd_transgear_knob_cup"]
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

# A Ø19 x 8 ring: 4:1 keeps the section (76 x 32 mm on the sheet) and the
# two-line bore callout legible without crowding the landscape sheet.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
FACE_CENTER = (0.090, 0.170)
SECTION_CENTER = (0.200, FACE_CENTER[1])
ISO_CENTER = (0.330, FACE_CENTER[1])
# Half the cup's O.D. on the sheet, and the cutting line's overrun past it.
HALF_OD = OD * _S / 2000.0
SECTION_LINE_OVERRUN = 0.005
# Across the face view on the cup axis: sheet X is model X in *Top, so the
# cut is the Front plane, the plane of the turned profile.
SECTION_LINE = (
    (FACE_CENTER[0] - HALF_OD - SECTION_LINE_OVERRUN, FACE_CENTER[1]),
    (FACE_CENTER[0] + HALF_OD + SECTION_LINE_OVERRUN, FACE_CENTER[1]),
)

DIMENSION_CALLOUTS = {"BoreDia": BORE_CALLOUT}

FACE_KEEP = {
    "BoreDia": (0.040, 0.225),
}
# The section spans sheet y 0.154 .. 0.186: the O.D. below it, the length
# outboard on the right.
SECTION_KEEP = {
    "CupDia": (0.200, 0.130),
    "CupLength": (0.255, SECTION_CENTER[1]),
}


def _section_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y station on the section (front face up).

    The section is cut from the *Top face view, and it shows model +Y down:
    mapped rear face up, the front-face pick landed on the y = LENGTH face
    (run 20261001T011714683Z).
    """
    return SECTION_CENTER[1] - (model_y_mm - LENGTH / 2.0) * _S / 1000.0


# The front face's pick lies on its cut edge, midway between the bore and
# the O.D. on the right half; the symbol stands above and outboard, clear of
# the length dimension's upper extension line on the right.
_FRONT_PICK = (
    SECTION_CENTER[0] + (BORE_DIA + OD) / 4.0 * _S / 1000.0,
    _section_y(0.0),
)
FRONT_FINISH = (_FRONT_PICK, (_FRONT_PICK[0] + 0.020, _FRONT_PICK[1] + 0.022))


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open knob-cup source", await adapter.open_model(str(SOURCE)))
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
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Transgear Knob Cup Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear knob cup; turned brass",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    face = place_view(adapter, str(SOURCE), "*Top", *FACE_CENTER, scale=VIEW_SCALE)
    section = create_section_view(
        adapter,
        face,
        line_start=SECTION_LINE[0],
        line_end=SECTION_LINE[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="knob cup axial section",
    )
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (face, section, iso):
        set_hidden_lines_removed(adapter, view)

    face_annotations = curate_view_dimensions(
        adapter,
        face,
        keep=FACE_KEEP,
        view_label="face",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    section_annotations = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="axial section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Decimal places (and so the general-tolerance row each dimension claims)
    # and the bore's band are authored on the part; the sheet only proves the
    # import kept them.
    assert_imported_precision(
        adapter, [*face_annotations, *section_annotations], DRAWING_PRECISION_BY_NAME
    )
    set_dimension_callouts(adapter, face_annotations, DIMENSION_CALLOUTS)
    if not auto_center_marks(adapter, face, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the cup face view")
    pick, symbol = FRONT_FINISH
    add_surface_finish(
        adapter,
        section,
        edge_xy=pick,
        symbol_xy=symbol,
        control=surface_finish_by_key(SURFACE_FINISHES, "front_face"),
        label="cup front (running) face finish",
        char_height=0.0025,
    )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        spec=SPEC,
        pdf_title="Transgear Knob Cup Manufacturing Drawing",
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
