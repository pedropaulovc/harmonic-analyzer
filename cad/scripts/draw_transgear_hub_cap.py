r"""Create the manufacturing drawing for the transgear hub cap (MHA-160).

The face view is the ``*Front`` orientation, looking at the front face: it
carries the native #6-32 through-thread callout and the wrench flats'
across-flats size with their centring on the bore axis above it.
Section A-A cuts it on the cap axis through the Right plane, clear of both
flats, so the O.D., the length and the front chamfer print on solid cut
edges.  The rear face seats on the stud shoulder: its seat roughness symbol
stands on its edge in the section (policy rule 5).
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
from _gear_drawing_entities import visible_circle_edge
from _section_axis import position_section_caption
from _surface_finish import surface_finish_by_key
from transgear_hub_cap_spec import (
    CAP_DIA,
    CAP_LENGTH,
    CHAMFER_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FLATS_CALLOUT,
    SURFACE_FINISHES,
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

# A Ø10.5 × 6.0 cap: 5:1 leaves room round the section for its three
# dimensions and the seat's finish symbol.
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
# is the Right plane, the plane of the turned profile, square to the flats.
SECTION_LINE = (
    (FACE_CENTER[0], FACE_CENTER[1] - HALF_OD - SECTION_LINE_OVERRUN),
    (FACE_CENTER[0], FACE_CENTER[1] + HALF_OD + SECTION_LINE_OVERRUN),
)
# The section lays the axis horizontal with the O.D. up and down, the front
# (chamfered) end right (farm run 20261001T110844152Z): the O.D. stands off
# the front end, the length below, the chamfer's leg above at the top corner.
SECTION_KEEP = {
    "CapDia": (SECTION_CENTER[0] + HALF_LENGTH + 0.016, SECTION_CENTER[1]),
    "CapLength": (SECTION_CENTER[0], SECTION_CENTER[1] - HALF_OD - 0.014),
    "FrontChamfer": (SECTION_CENTER[0], SECTION_CENTER[1] + HALF_OD + 0.030),
}
# The native A-A caption under the length dimension, not on it (the same run
# printed it through the 5.80).
CAPTION_XY = (SECTION_CENTER[0] - 0.020, SECTION_CENTER[1] - HALF_OD - 0.028)
# The rear (seat) face is the section's left edge; the pick lies on it in the
# cut wall between the tap drill and the O.D., the symbol above-left of it.
REAR_FACE_X = SECTION_CENTER[0] - HALF_LENGTH
REAR_FACE_PICK = (REAR_FACE_X, SECTION_CENTER[1] + 0.6 * HALF_OD)
REAR_FACE_SYMBOL_XY = (REAR_FACE_X - 0.016, SECTION_CENTER[1] + HALF_OD + 0.010)
# The face view: the across-flats above the face, its text over the cutting
# line's top end.
FACE_KEEP = {
    "FlatsAcross": (FACE_CENTER[0], FACE_CENTER[1] + HALF_OD + 0.016),
}
DIMENSION_CALLOUTS_BELOW = {"FrontChamfer": CHAMFER_CALLOUT}
# The flats' centring reads above their size.  One line only: SolidWorks drops
# an above-callout holding a line break (drive collar, farm run
# 20261001T151531763Z: its two-line slot callout never printed).
DIMENSION_CALLOUTS_ABOVE = {"FlatsAcross": FLATS_CALLOUT}
# Right of the face view, below the axis: its leader reaches the tap drill's
# right side, clear of the cutting line, the across-flats extension lines and
# the lower A.
THREAD_CALLOUT_XY = (FACE_CENTER[0] + HALF_OD + 0.034, FACE_CENTER[1] - 0.020)
ISO_NOTE_XY = (ISO_CENTER[0] - 0.030, ISO_CENTER[1] - 0.040)
NOTES_XY = (0.016, 0.070)


def _printable_above_callouts(callouts: dict[str, str]) -> dict[str, str]:
    """The above-callouts, refused if any holds a line break (it would not print)."""
    broken = sorted(name for name, text in callouts.items() if "\n" in text)
    if broken:
        raise RuntimeError(f"above-callouts with a line break do not print: {broken}")
    return callouts


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
    set_dimension_callouts(
        adapter,
        annotations,
        _printable_above_callouts(DIMENSION_CALLOUTS_ABOVE),
        location="above",
    )
    if not auto_center_marks(adapter, face, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the hub cap face view")
    # The tap drill's edge on the front face: the Hole Wizard feature's one
    # visible circle from the front.
    add_native_hole_callout(
        adapter,
        face,
        edge=visible_circle_edge(adapter, face, TAP_DRILL_DIA),
        callout_xy=THREAD_CALLOUT_XY,
        label="#6-32 through thread",
    )
    position_section_caption(adapter, section, CAPTION_XY, label="hub cap")
    add_surface_finish(
        adapter,
        section,
        edge_xy=REAR_FACE_PICK,
        symbol_xy=REAR_FACE_SYMBOL_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "rear_face"),
        label="cap rear (seat) face finish",
        char_height=0.0025,
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Hub Cap Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # The Hole Wizard thread's own "#6-32 Tapped Hole" note restates the
        # hole callout.
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=1,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
