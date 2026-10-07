r"""Create the rework drawing for the pivot bracket's angle plate (MHA-CH-008-TL-02).

The plate is bought; the sheet dimensions only the four holes the shop adds
to its upright. The front view (the upright's front face, 1:1) carries every
station: each hole X from the plate's left end and each row's height from
the base underside (the table plane), so no station chains through another.
Each hole pair takes one native callout; the iso rides top-right at 1:2.
No datums (policy rule 3).

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_pivot_bracket_tl_angle_plate.py ch-pivot-bracket-tl-angle-plate
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_native_hole_callout,
    add_property_linked_note,
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm, drill_process
from ch_pivot_bracket_tl_angle_plate_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    PLATE_HEIGHT,
    PLATE_LENGTH,
    SCREW_Y,
    STUD_SPEC,
    STUD_X,
    STUD_Y,
    TAP_SPEC,
    TAP_X,
)
from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view

SPEC = DRAWINGS_BY_NAME["ch_pivot_bracket_tl_angle_plate"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

SHEET_SCALE = (1.0, 1.0)
VIEW_SCALE = (1, 1)
ISO_SCALE = (1, 2)
# Front: the 127 x 88.9 upright face at 1:1, x 0.0615..0.1885 and
# y 0.1205..0.2094; the callouts stand right of it, the iso top-right.
FRONT_CENTER = (0.125, 0.165)
ISO_CENTER = (0.355, 0.200)
ISO_NOTE_XY = (0.320, 0.140)
NOTES_XY = (0.020, 0.060)


def _sheet_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front view (1:1, bbox-centred)."""
    return FRONT_CENTER[0] + (model_x_mm - PLATE_LENGTH / 2.0) * SHEET_SCALE[0] / 1000.0


def _sheet_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the front view (1:1, bbox-centred)."""
    return FRONT_CENTER[1] + (model_y_mm - PLATE_HEIGHT / 2.0) * SHEET_SCALE[0] / 1000.0


LEFT_EDGE_X = _sheet_x(0.0)
TAP_R_SHEET = blind_cut_dia_mm(TAP_SPEC) * SHEET_SCALE[0] / 2000.0
STUD_R_SHEET = blind_cut_dia_mm(STUD_SPEC) * SHEET_SCALE[0] / 2000.0

# Four X stations stack below the face from its left end, nearest first;
# the two row heights stand left of it from the base underside.
FRONT_KEEP = {
    "Stud1X": (_sheet_x(STUD_X[0] / 2.0), 0.108),
    "Tap1X": (_sheet_x(TAP_X[0] / 2.0), 0.100),
    "Tap2X": (_sheet_x(TAP_X[1] / 2.0), 0.092),
    "Stud2X": (_sheet_x(STUD_X[1] / 2.0), 0.084),
    "Tap1Y": (LEFT_EDGE_X - 0.012, _sheet_y(SCREW_Y / 2.0)),
    "Stud1Y": (LEFT_EDGE_X - 0.024, _sheet_y(STUD_Y / 2.0)),
}
# Each pair stands on the one row height the part prints.
DIMENSION_PREFIXES = {"Tap1Y": "2X ", "Stud1Y": "2X "}
# Both leaders enter their pair's right-hand hole from its upper right and
# cross only the plate's right end.
TAP_CALLOUT_XY = (0.205, 0.180)
STUD_CALLOUT_XY = (0.205, 0.225)
STUD_CALLOUT_PROCESS = drill_process(STUD_SPEC)


def _set_dimension_prefixes(
    adapter: Any, annotations: list[Any], prefixes: dict[str, str]
) -> None:
    """Write a native prefix on named imported dimensions and read it back."""
    remaining = dict(prefixes)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        prefix = remaining.pop(dimension_name(adapter, annotation), None)
        if prefix is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.SetText(1, prefix)  # swDimensionTextPrefix
        if str(display.GetText(1) or "") != prefix:
            raise RuntimeError(f"dimension prefix {prefix!r} did not persist")
    if remaining:
        raise RuntimeError(f"dimension prefixes not applied: {sorted(remaining)}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open angle-plate source", await adapter.open_model(str(SOURCE)))
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
            0: "Pivot Bracket Angle Plate Rework Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "pivot bracket angle plate; bought cast iron, reworked; MHA-CH-008-TL-02",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    set_hidden_lines_removed(adapter, front)

    annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="upright face",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Places and the station bands are authored on the part; the sheet only
    # proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _set_dimension_prefixes(adapter, annotations, DIMENSION_PREFIXES)

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the upright face")
    add_native_hole_callout(
        adapter,
        front,
        edge_xy=(
            _sheet_x(TAP_X[1]) + 0.6 * TAP_R_SHEET,
            _sheet_y(SCREW_Y) + 0.8 * TAP_R_SHEET,
        ),
        callout_xy=TAP_CALLOUT_XY,
        label="ledge screw taps",
    )
    add_native_hole_callout(
        adapter,
        front,
        edge_xy=(
            _sheet_x(STUD_X[1]) + 0.6 * STUD_R_SHEET,
            _sheet_y(STUD_Y) + 0.8 * STUD_R_SHEET,
        ),
        callout_xy=STUD_CALLOUT_XY,
        label="bridge stud holes",
        process=STUD_CALLOUT_PROCESS,
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pivot Bracket Angle Plate Rework Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # SolidWorks pins its own "#10-24 Tapped Hole" note to the face view
        # once the tap carries a hole callout; the callout already states it.
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
