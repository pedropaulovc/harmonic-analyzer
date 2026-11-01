r"""Create the curated manufacturing drawing for the rod pivot pin (MHA-CH-10).

Under ``cad/docs/drawing-guidelines.md``: the INSTALLED pin -- a 5/64
drill-rod cylinder pressed into the connecting rod's reamed fork pin hole and
dressed flush with both tines (user ruling 2026-10-09, PR #1292 review F1) --
on three native model dimensions, all on the side view where a turned part's
diameter sits beside its length (drawing-guidelines.md rule 11 (turned parts read like the lathe)): the Ø as the 5/64
stock fraction's REFERENCE (the drill rod's grind governs), the stock and its
two fits named below it (rules 4 and 7: the
mates are flagged where they apply), the installed length as REFERENCE
(the fork's thickness; the MHA-CH-03 print owns it), and the blank's cut
length as a single MIN limit from the part's blanked ``BlankReference``
sketch. An axis centerline, a bare end view with its center mark, the
isometric, and the property-linked note (installed state, flush ends,
removable). No datums, no frames, no roughness symbol.
The decimal places are the PART's (``ch_rod_pivot_pin_notes.DRAWING_PRECISION``,
applied natively by ``build_ch_rod_pivot_pin``); this script reads them back
off the sheet and dresses the journal as its stock fraction. Decimal-inch
sheet (#290); the model keeps its millimetre nominals.

Drawn 10:1 -- a 5/64 x .240 pin is a speck on a B sheet at anything less.
"""

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
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
import _drawing_hidden_sketches as hidden_sketches
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from _supplier_dimensions import supplier_reference_dimension
from ch_rod_pivot_pin_notes import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    PIN_DIA_CALLOUT,
    PIN_DIA_FRACTION_DENOMINATOR,
    REFERENCE_DIMENSIONS,
)
from ch_rod_pivot_pin_spec import PIN_DIA, PIN_INSTALLED_LENGTH


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

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
FRONT_CENTER = (0.080, 0.170)  # end view: a bare circle
RIGHT_CENTER = (0.200, 0.170)  # side view: the pin along its axis
ISO_CENTER = (0.330, 0.170)
NOTES_XY = (0.020, 0.085)  # left of the title block, below the views

# Printed half-sizes in sheet metres, which every dimension is placed clear of.
HALF_DIA = PIN_DIA * VIEW_SCALE[0] / 2000.0  # 0.0099
HALF_LEN = PIN_INSTALLED_LENGTH * VIEW_SCALE[0] / 2000.0  # 0.0304

# Side view: the diameter above the view, its text left of centre so the
# axis-centerline pick at the view's middle lands on bare face, high enough
# that its three callout lines below (stock, then the two fits) stay clear of
# the pin's top edge; the installed length below, and the blank's cut length
# below that, both two-line texts (value over word), spaced to stay apart.
RIGHT_KEEP = {
    "PinDia": (RIGHT_CENTER[0] - 0.020, RIGHT_CENTER[1] + HALF_DIA + 0.034),
    "PinLen": (RIGHT_CENTER[0], RIGHT_CENTER[1] - HALF_DIA - 0.016),
    "BlankLen": (RIGHT_CENTER[0], RIGHT_CENTER[1] - HALF_DIA - 0.036),
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
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("ch-rod-pivot-pin"),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rod Pivot Pin Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "rod pivot pin; installed state; pressed drill rod",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    # A solid pin has nothing inside: hidden lines off everywhere (drawing-guidelines.md rule 9 (show internal shape in solid lines)).
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
    # Descriptive text only; the values and MIN limit are the model's. The
    # installed reference says what it is, and that word -- no descender --
    # sits on the dimension line instead of the reference's parentheses (r2
    # review, rule 14: the line touched the reference).
    set_dimension_callouts(
        adapter,
        right_annotations,
        {"PinLen": "INSTALLED", "BlankLen": "BLANK"},
    )
    # The journal is the as-bought drill rod: its native value prints as the
    # 5/64 stock fraction's REFERENCE (#290: supplier tolerance governs), the
    # stock and its two fits below it (drawing-guidelines.md rules 4 and 7:
    # name the mate where it applies).
    journals = [a for a in right_annotations if dimension_name(adapter, a) == "PinDia"]
    if len(journals) != 1:
        raise RuntimeError("expected one pin PinDia dimension")
    supplier_reference_dimension(
        adapter,
        _early_bound(
            _early_bound(journals[0], "IAnnotation").GetSpecificAnnotation(),
            "IDisplayDimension",
        ),
        label="pin PinDia",
        units="in",
        precision=DRAWING_PRECISION_BY_NAME["PinDia"],
        expected_mm=PIN_DIA,
        presentation="diameter",
        fraction_denominator=PIN_DIA_FRACTION_DENOMINATOR,
        callout=PIN_DIA_CALLOUT,
    )
    # The installed length is the fork's thickness: a LINEAR reference. The
    # plural set_reference_dimensions forces a diameter glyph.
    for name in sorted(REFERENCE_DIMENSIONS):
        matches = [a for a in right_annotations if dimension_name(adapter, a) == name]
        if len(matches) != 1:
            raise RuntimeError(f"expected one pin {name} reference dimension")
        set_reference_dimension(adapter, matches[0], label=f"pin {name}")
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
