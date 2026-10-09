r"""Create the curated manufacturing drawing for the rod pivot pin (MHA-CH-010).

Under ``cad/docs/drawing-simplicity-policy.md``: the INSTALLED pin -- a
5/64 drill-rod journal whose ends are peened into the fork's countersinks --
on three native model dimensions, all on the side view where a turned part's
diameter sits beside its length (rule 7): the journal Ø with the drill rod's
own grind band, the installed length as REFERENCE (the fork's thickness;
the MHA-CH-003 print owns it), and the blank's cut length with its band from
the part's blanked ``BlankReference`` sketch. An axis centerline, a bare end
view with its center mark, the isometric, and the property-linked notes (cut
the blank, the peen-at-assembly step, the running fit, the #746
reconstruction statement). No datums, no frames, no roughness symbol.
The decimal places and the band are the PART's
(``ch_rod_pivot_pin_notes.DRAWING_PRECISION``, applied natively by
``build_ch_rod_pivot_pin``); this script only reads them back off the sheet.

Drawn 10:1 -- a Ø1.98 x 6.08 pin is a speck on a B sheet at anything less.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _drawing_hidden_sketches as hidden_sketches
import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    add_view_centerline,
    assert_imported_precision,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimensions,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from ch_rod_pivot_pin_notes import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    REFERENCE_DIMENSIONS,
)
from ch_rod_pivot_pin_spec import PIN_CSK_DIA, PIN_DIA, PIN_INSTALLED_LENGTH
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["ch_rod_pivot_pin"]
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

SHEET_SCALE = (10.0, 1.0)
VIEW_SCALE = (10, 1)
FRONT_CENTER = (0.080, 0.170)  # end view: the countersink-rim circle
RIGHT_CENTER = (0.200, 0.170)  # side view: the journal and its flared ends
ISO_CENTER = (0.330, 0.170)
NOTES_XY = (0.020, 0.085)  # left of the title block, below the views

# Printed half-sizes in sheet metres, which every dimension is placed clear of.
HALF_DIA = PIN_DIA * VIEW_SCALE[0] / 2000.0  # 0.0099
HALF_RIM = PIN_CSK_DIA * VIEW_SCALE[0] / 2000.0  # 0.016
HALF_LEN = PIN_INSTALLED_LENGTH * VIEW_SCALE[0] / 2000.0  # 0.0304

# Side view: the diameter above the view, its text left of centre so the
# axis-centerline pick at the view's middle lands on bare face; the installed
# length below, and the blank's cut length below that.
RIGHT_KEEP = {
    "PinDia": (RIGHT_CENTER[0] - 0.020, RIGHT_CENTER[1] + HALF_RIM + 0.016),
    "PinLen": (RIGHT_CENTER[0], RIGHT_CENTER[1] - HALF_RIM - 0.016),
    "BlankLen": (RIGHT_CENTER[0], RIGHT_CENTER[1] - HALF_RIM - 0.032),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open rod-pivot-pin source", await adapter.open_model(str(SOURCE)))
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
            0: "Rod Pivot Pin Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "rod pivot pin; installed state; peened drill rod",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    # A solid pin has nothing inside: hidden lines off everywhere (rule 7).
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    # The journal and installed length live on the revolve's half-profile and
    # the blank length on a reference sketch the part saves hidden, all on the
    # Right plane: the side view curates through _drawing_hidden_sketches,
    # which shows that sketch in this view only. The end view is a bare
    # circle with its center mark.
    right_annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, right_annotations, DRAWING_PRECISION_BY_NAME)
    # The installed length is the fork's thickness: REFERENCE, keyed by name.
    set_reference_dimensions(adapter, right_annotations, REFERENCE_DIMENSIONS)
    # Descriptive text only; the value and band are the model's.
    set_dimension_callouts(adapter, right_annotations, {"BlankLen": "BLANK"})
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the pin end view")
    add_view_centerline(
        adapter,
        right,
        face_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] + 0.004),
        label="rod pivot pin axis centerline",
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rod Pivot Pin Manufacturing Drawing",
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
