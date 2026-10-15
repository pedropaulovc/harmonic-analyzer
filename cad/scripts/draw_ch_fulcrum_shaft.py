r"""Create the curated machinist drawing for the lever fulcrum shaft."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimensions import set_dimension_callouts
from _drawing_finish import add_surface_finish
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from ch_fulcrum_shaft_spec import (
    ACROSS_FLAT_CALLOUT,
    DRAWING_DIMENSIONS,
    FLAT_FROM_END,
    FLAT_LENGTH,
    SHAFT_DIA,
    SHAFT_DIA_CALLOUT,
    SHAFT_LENGTH,
    SURFACE_FINISHES,
)


SPEC = DRAWINGS_BY_NAME["ch_fulcrum_shaft"]
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

# 2:1 for every orthographic view: the 0.3 flats and their stations read at
# that size, the side view spans most of the sheet width and the end view
# needs no scale note of its own.
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]
AXIS_Y = 0.212
FRONT_CENTER = (0.026, AXIS_Y)
RIGHT_CENTER = (0.216, AXIS_Y)
# The isometric fills the free band over the title block at 1:1 (half the
# sheet scale, hence its note): the shaft runs lower-left to upper-right
# about 114 x 66 mm, so x 0.261-0.375, y 0.089-0.155.
ISO_CENTER = (0.318, 0.122)
ISO_SCALE = (1, 1)


def _on_sheet(mm: float) -> float:
    """A model length in mm as sheet metres at the view scale."""
    return mm * VIEW_SCALE / 1000.0


# Both profile sketches lie on the Right plane, so every print dimension
# lands in the side view.  The sketch +u axis is model -Z, which the *Right
# view draws to sheet-RIGHT (the build_ch_pivot_shaft mapping): both flat
# stations run from the sheet-LEFT dome tip, the flat length and the
# across-flat witness ride the sheet-right flat, the dome radius the left
# dome.
_LEFT_TIP_X = RIGHT_CENTER[0] - _on_sheet(SHAFT_LENGTH / 2.0)
_RIGHT_TIP_X = RIGHT_CENTER[0] + _on_sheet(SHAFT_LENGTH / 2.0)
_RIGHT_FLAT_INNER_X = _RIGHT_TIP_X - _on_sheet(FLAT_FROM_END + FLAT_LENGTH)
# Rows above the shaft, nearest first; every text stands where no other
# dimension's extension line runs: 5.45 outboard left of the left tip, the
# flat length left of its flat's inner edge, and the overall length (the
# only dimension off the right tip) on the top row.
_ROW_1 = AXIS_Y + 0.014
_ROW_2 = AXIS_Y + 0.026
_ROW_3 = AXIS_Y + 0.038
FRONT_KEEP: dict[str, tuple[float, float]] = {}
RIGHT_KEEP = {
    "FlatFromEnd": (_LEFT_TIP_X - 0.0065, _ROW_1),
    "FlatLength": (_RIGHT_FLAT_INNER_X - 0.0105, _ROW_1),
    "FlatBaseline": (RIGHT_CENTER[0] - 0.020, _ROW_2),
    "OverallLength": (RIGHT_CENTER[0], _ROW_3),
    # Under the shaft: the limit Ø with its fit callout, left of centre (its
    # value block ~3 mm clear of the lower silhouette), and the dome's
    # reference radius under the left dome, right of the end view's Ra.
    "ShaftDia": (RIGHT_CENTER[0] - 0.050, AXIS_Y - 0.015),
    "DomeRadius": (_LEFT_TIP_X + 0.030, AXIS_Y - 0.018),
    # Right of the right tip, its two-line callout under it.
    "AcrossFlat": (_RIGHT_TIP_X + 0.018, AXIS_Y),
}


def _set_dome_reference(adapter: Any, annotations: list[Any]) -> None:
    """Print DomeRadius as ``2X (SR3.18)``: both domes, a spherical reference
    (the full hemisphere follows from the toleranced diameter). The display's
    own radius prefix stays behind the ``(S``; the readback proves it stuck."""
    (annotation,) = [
        item for item in annotations if dimension_name(adapter, item) == "DomeRadius"
    ]
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    existing = str(display.GetText(1) or "")  # swDimensionTextPrefix
    prefix = "2X (S" + existing
    display.SetText(1, prefix)
    display.SetText(2, ")")  # swDimensionTextSuffix
    applied = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
    _telemetry.info(f"DomeRadius: prefix {existing!r} -> {applied[0]!r}")
    if applied != (prefix, ")"):
        raise RuntimeError(
            f"failed to mark DomeRadius as a spherical reference: {applied}"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open fulcrum-shaft source", await adapter.open_model(str(SOURCE)))
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
            "Iso View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Iso View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Fulcrum Shaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "fulcrum shaft; bearing shaft; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    # The end view carries no dimension: it shows the flat's chord on the
    # round, and every size is in the side view.
    curated = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Rule 4: each three-place size names the mate and fit it serves.
    set_dimension_callouts(
        adapter,
        curated,
        {"ShaftDia": SHAFT_DIA_CALLOUT, "AcrossFlat": ACROSS_FLAT_CALLOUT},
    )
    _set_dome_reference(adapter, curated)
    # SolidWorks classifies a solid circular end silhouette under the same
    # AutoInsertCenterMarks2 "hole" bit as a bored circle; disabling that bit
    # makes the API a guaranteed no-op even though the end view is circular.
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to shaft end view")

    # The bearing O.D.'s roughness: picked on the end circle's lower-right
    # point (the flat is on top), the symbol well below so its leader runs
    # down clear of the side view's left-end dimensions.
    end_radius = _on_sheet(SHAFT_DIA / 2.0)
    add_surface_finish(
        adapter,
        front,
        edge_xy=(
            FRONT_CENTER[0] + end_radius * 0.7071,
            FRONT_CENTER[1] - end_radius * 0.7071,
        ),
        symbol_xy=(FRONT_CENTER[0] - 0.004, AXIS_Y - 0.040),
        control=surface_finish_by_key(SURFACE_FINISHES, "bearing"),
        label="fulcrum bearing finish",
    )

    # 0.020: the note is left-aligned on its anchor, so the ink starts here. The
    # left bound is the 12.7 mm zone margin (~0.0127), which the re-centred frame
    # rule now matches (~0.0126); 0.020 clears both, and the audit enforces it.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.115)
    # The iso renders at 1:1 while the title block reads 2:1, so the pictorial
    # needs its own scale callout; it stands in the empty lower-right corner
    # of the iso's bounding box, clear of the title block.
    add_property_linked_note(
        adapter, "Iso View Note", ISO_CENTER[0] + 0.015, ISO_CENTER[1] - 0.022
    )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Fulcrum Shaft Manufacturing Drawing",
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
