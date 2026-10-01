r"""Create the manufacturing drawing for the transgear hub cap (MHA-160).

The face view is the ``*Front`` orientation, looking at the front face: it
carries the native #6-32 through-thread callout with the front countersink
named under its thread line, and the two drilled spanner holes' Ø and
spacing.  Section A-A cuts it on the cap axis through the Right plane, the
plane of the turned profile and of both spanner holes, so the O.D., the
length, the front chamfer and the holes' depth print on solid cut edges.  No
roughness symbol: the plain rear face seats on the stud shoulder, a clamp
face (policy rule 5); its flatness is a note.
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
    add_property_linked_note,
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
from transgear_hub_cap_spec import (
    CAP_DIA,
    CAP_LENGTH,
    CHAMFER_CALLOUT,
    CSK_QUALIFIER,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    SPANNER_HOLE_CALLOUT,
    SPANNER_HOLE_R,
    TAP_DRILL_DIA,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)

SPEC = DRAWINGS_BY_NAME["transgear_hub_cap"]
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

# A Ø10.5 × 5.8 cap: 5:1 draws the Ø1.2 spanner holes 6 mm across and leaves
# room round the section for its four dimensions.
SHEET_SCALE = (5.0, 1.0)
VIEW_SCALE = (5, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
FACE_CENTER = (0.090, 0.165)
SECTION_CENTER = (0.215, FACE_CENTER[1])
ISO_CENTER = (0.345, FACE_CENTER[1])
ISO_SCALE = (3, 1)
# Half the O.D. on the sheet, and the cutting line's overrun past it.
HALF_OD = CAP_DIA * _S / 2000.0
HALF_LENGTH = CAP_LENGTH * _S / 2000.0
SECTION_LINE_OVERRUN = 0.005
# Up the face view on the cap axis: sheet Y is model Y in *Front, so the cut
# is the Right plane, the plane of the turned profile and the spanner holes.
SECTION_LINE = (
    (FACE_CENTER[0], FACE_CENTER[1] - HALF_OD - SECTION_LINE_OVERRUN),
    (FACE_CENTER[0], FACE_CENTER[1] + HALF_OD + SECTION_LINE_OVERRUN),
)
# The section lays the axis horizontal with the O.D. up and down: the O.D.
# stands off one end, the length and the hole depth below and above, the
# chamfer's leg above at the top corner.  Every axial dimension's text sits
# on the section's centre line so either end-for-end projection reads.
SECTION_KEEP = {
    "CapDia": (SECTION_CENTER[0] + HALF_LENGTH + 0.016, SECTION_CENTER[1]),
    "CapLength": (SECTION_CENTER[0], SECTION_CENTER[1] - HALF_OD - 0.014),
    "SpannerHoleDepth": (SECTION_CENTER[0], SECTION_CENTER[1] + HALF_OD + 0.014),
    "FrontChamfer": (SECTION_CENTER[0], SECTION_CENTER[1] + HALF_OD + 0.030),
}
# The face view: the holes' Ø off the upper hole, their spacing left of the
# face.
FACE_KEEP = {
    "SpannerHoleDia": (
        FACE_CENTER[0] + 0.024,
        FACE_CENTER[1] + SPANNER_HOLE_R * _S / 1000.0 + 0.020,
    ),
    "SpannerHoleSpacing": (FACE_CENTER[0] - HALF_OD - 0.012, FACE_CENTER[1]),
}
DIMENSION_CALLOUTS_BELOW = {
    "SpannerHoleDia": SPANNER_HOLE_CALLOUT,
    "FrontChamfer": CHAMFER_CALLOUT,
}
THREAD_CALLOUT_XY = (FACE_CENTER[0] + 0.030, FACE_CENTER[1] - HALF_OD - 0.020)
ISO_NOTE_XY = (ISO_CENTER[0] - 0.030, ISO_CENTER[1] - 0.040)
NOTES_XY = (0.016, 0.070)


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
    """Name the front countersink under the native through-thread line."""
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
            "hub cap countersink line did not persist: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open hub cap source", await adapter.open_model(str(SOURCE)))
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
            0: "Transgear Hub Cap Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear hub cap; turned and drilled brass; #6-32",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    face = place_view(adapter, str(SOURCE), "*Front", *FACE_CENTER, scale=VIEW_SCALE)
    section = create_section_view(
        adapter,
        face,
        line_start=SECTION_LINE[0],
        line_end=SECTION_LINE[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="hub cap axial section",
    )
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
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
    annotations = [*face_annotations, *section_annotations]
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(
        adapter, annotations, DIMENSION_CALLOUTS_BELOW, location="below"
    )
    if not auto_center_marks(adapter, face, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the hub cap face view")
    # The tap-drill edge under the front countersink: the Hole Wizard
    # feature's one visible circle from the front.
    thread_callout = add_native_hole_callout(
        adapter,
        face,
        edge=visible_circle_edge(adapter, face, TAP_DRILL_DIA),
        callout_xy=THREAD_CALLOUT_XY,
        label="#6-32 through thread",
    )
    _set_thread_callout_text(thread_callout)
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Hub Cap Manufacturing Drawing",
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
