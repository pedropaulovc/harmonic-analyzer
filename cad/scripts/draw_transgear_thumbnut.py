r"""Create the manufacturing drawing for the transgear thumbnut (MHA-126).

The face view is the ``*Top`` orientation, looking at the dished front face:
it carries the native 1/4-20 through-thread callout with both countersinks
named under its thread line.  Section A-A cuts it on the nut axis through the
Front plane, the plane of the turned profiles and of two knurl crests, so the
knurl diameter, the head, waist and flange, the overall length from the seat
face and the dish's chord and depth print on solid cut edges.  No roughness
symbol: the seat face clamps the wheel (policy rule 5).
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_native_hole_callout,
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
from _gear_drawing_entities import visible_circle_edge
from transgear_thumbnut_spec import (
    CSK_QUALIFIER,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FLANGE_LENGTH,
    HEAD_DIA,
    HEAD_LENGTH,
    KNURL_CALLOUT,
    OVERALL_LENGTH,
    TAP_DRILL_DIA,
    WAIST_LENGTH,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["transgear_thumbnut"]
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

# A Ø20.5 × 16.1 nut: 3:1 leaves room round the section for its eight
# dimensions and the knurl callout on the landscape sheet.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
FACE_CENTER = (0.085, 0.165)
SECTION_CENTER = (0.215, FACE_CENTER[1])
ISO_CENTER = (0.345, FACE_CENTER[1])
# Half the knurl diameter on the sheet, and the cutting line's overrun past it.
HALF_HEAD = HEAD_DIA * _S / 2000.0
SECTION_LINE_OVERRUN = 0.005
# Across the face view on the nut axis: sheet X is model X in *Top, so the
# cut is the Front plane, the plane of the turned profiles.
SECTION_LINE = (
    (FACE_CENTER[0] - HALF_HEAD - SECTION_LINE_OVERRUN, FACE_CENTER[1]),
    (FACE_CENTER[0] + HALF_HEAD + SECTION_LINE_OVERRUN, FACE_CENTER[1]),
)


def _section_x(model_x_mm: float) -> float:
    """Sheet X of a model-X offset from the axis on the section."""
    return SECTION_CENTER[0] + model_x_mm * _S / 1000.0


def _section_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y station on the section (rim up)."""
    return SECTION_CENTER[1] + (model_y_mm - OVERALL_LENGTH / 2.0) * _S / 1000.0


# The diameters stack above the rim (knurl outermost) and below the seat
# face (waist outermost); the lengths stand off the right (head, overall) and
# the left (waist, dish depth) of the silhouette.
SECTION_KEEP = {
    "HeadDia": (SECTION_CENTER[0], _section_y(OVERALL_LENGTH) + 0.030),
    "DishDia": (SECTION_CENTER[0], _section_y(OVERALL_LENGTH) + 0.014),
    "DishDepth": (_section_x(-HEAD_DIA / 2.0) - 0.016, _section_y(OVERALL_LENGTH)),
    "HeadLength": (
        _section_x(HEAD_DIA / 2.0) + 0.014,
        _section_y(OVERALL_LENGTH - HEAD_LENGTH / 2.0),
    ),
    "OverallLength": (_section_x(HEAD_DIA / 2.0) + 0.032, SECTION_CENTER[1]),
    "WaistLength": (
        _section_x(-HEAD_DIA / 2.0) - 0.016,
        _section_y(FLANGE_LENGTH + WAIST_LENGTH / 2.0),
    ),
    "FlangeDia": (SECTION_CENTER[0], _section_y(0.0) - 0.014),
    "WaistDia": (SECTION_CENTER[0], _section_y(0.0) - 0.028),
}
# The face view prints only the native thread callout.
FACE_KEEP: dict[str, tuple[float, float]] = {}
# Above the knurl diameter: the below lane would run into the dish chord.
DIMENSION_CALLOUTS_ABOVE = {"HeadDia": KNURL_CALLOUT}
THREAD_CALLOUT_XY = (FACE_CENTER[0] - 0.050, FACE_CENTER[1] + 0.060)


def _thread_callout_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """Append the countersink line to the one compartment holding the thread."""
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected thread callout parts: {definitions!r}")
    thread_parts = [
        part for part, text in definitions.items() if "<hw-threadclass>" in text
    ]
    if len(thread_parts) != 1:
        raise RuntimeError(f"thread line is not in one callout part: {definitions!r}")
    updated = dict(definitions)
    part = thread_parts[0]
    updated[part] = f"{updated[part].rstrip()}\n{CSK_QUALIFIER}"
    return updated


def _set_thread_callout_text(display: Any) -> None:
    """Name both countersinks under the native through-thread line."""
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    updated = _thread_callout_definitions(definitions)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            display.SetText(writable_part, updated[definition_part])
    persisted = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    resolved = {part: str(display.GetText(part) or "") for part in (1, 2, 3, 4)}
    thread = [text for text in resolved.values() if "UNC" in text]
    if (
        persisted != updated
        or len(thread) != 1
        or not thread[0].rstrip().endswith(CSK_QUALIFIER)
    ):
        raise RuntimeError(
            "thumbnut countersink line did not persist: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open thumbnut source", await adapter.open_model(str(SOURCE)))
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
            0: "Transgear Thumbnut Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear thumbnut; turned and knurled brass",
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
        label="thumbnut axial section",
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
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(
        adapter, [*face_annotations, *section_annotations], DRAWING_PRECISION_BY_NAME
    )
    set_dimension_callouts(
        adapter, section_annotations, DIMENSION_CALLOUTS_ABOVE, location="above"
    )
    if not auto_center_marks(adapter, face, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the thumbnut face view")
    # The tap-drill edge under the front countersink: the one visible circle
    # of the Hole Wizard feature from the front.
    thread_callout = add_native_hole_callout(
        adapter,
        face,
        edge=visible_circle_edge(adapter, face, TAP_DRILL_DIA),
        callout_xy=THREAD_CALLOUT_XY,
        label="1/4-20 through thread",
    )
    _set_thread_callout_text(thread_callout)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Thumbnut Manufacturing Drawing",
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
