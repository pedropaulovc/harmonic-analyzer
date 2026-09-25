r"""Create the modified-stock drawing for the MHA-142 cone pivot post mount screw.

MSC 40923898 is bought by SKU and cut to length, so the sheet is a
modified-purchased-part drawing (the boss hook's pattern), not the purchased
reference sheet: a Front view carrying the cut length -- the part's hidden
reference-sketch dimension, imported at its model-owned places -- and an
isometric, both 1:1.  No single length suits every in-band post and plate
(post_mount_screw_spec's U27 check), so the length prints as a REFERENCE,
"(86.0)", with "CUT TO FIT AT ASSEMBLY" beneath it and no band; MHA-A03 says
how.  The cut end's deburr break is a live banded dimension, 0.1 +0/-0.1.  The only note says to chamfer the cut end and that the undimensioned
purchased geometry is reference.  No installation sequence, engagement figure or rule
number is printed: the sequence is an MHA-A03 assembly step and the
engagement a model assert (Main's eye pass of warm-c486, policy rule 6).

Run with SolidWorks open::

    uv run python cad\scripts\draw_post_mount_screw.py post-mount-screw
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _drawing_hidden_sketches as hidden_sketches
import _stock_trim_drawing as trim_drawing
import _telemetry
from _common import _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    assert_imported_precision,
    finalize_drawing,
    new_project_drawing,
    dimension_name,
    offset_dimension_text,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _fit_limits import deviations
from post_mount_screw_spec import (
    CUT_END_BREAK_BAND,
    CUT_END_BREAK_DIMENSION,
    CUT_END_BREAK_MM,
    CUT_LENGTH_DIMENSION,
    CUT_LENGTH_MM,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HEAD_H_MM,
    THREAD_DIA_MM,
)
from solidworks_mcp.adapters.solidworks.drawing import place_view

SPEC = DRAWINGS_BY_NAME["post_mount_screw"]
PART_STEM = SPEC.artifact_stem
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(**SPEC.outputs)
TITLE = "Cone Pivot Post Mount Screw — Modified Stock Drawing"

SHEET_SCALE = (1.0, 1.0)
# The screw stands head up in the Front view: under-head face at model y 0,
# cut end at -CUT_LENGTH_MM, head top ~6 above.
FRONT_CENTER = (0.100, 0.165)
ISO_CENTER = (0.270, 0.185)
# The cut length reads on the left, where its reference line runs along the
# shank's silhouette, midway along the span, far enough out that its
# two-line callout clears the shank.
# The cut end's 0.1 break spans 0.1 mm at 1:1, so its dimension line sits
# just below the end face and its text leads out to the right, clear of the
# shank and above the note block.  (The view is placed by its outline's
# centre: the end face is half the screw's overall height below it.)
TIP_Y = FRONT_CENTER[1] - (CUT_LENGTH_MM + HEAD_H_MM) / 2000.0
BREAK_X = FRONT_CENTER[0] + (THREAD_DIA_MM / 2.0 - CUT_END_BREAK_MM / 2.0) / 1000.0
FRONT_KEEP = {
    CUT_LENGTH_DIMENSION: (FRONT_CENTER[0] - 0.030, FRONT_CENTER[1]),
    CUT_END_BREAK_DIMENSION: (BREAK_X, TIP_Y - 0.006),
}
BREAK_TEXT = (FRONT_CENTER[0] + 0.028, TIP_Y - 0.006)
DIMENSION_CALLOUTS = {CUT_LENGTH_DIMENSION: "CUT TO FIT\nAT ASSEMBLY"}
# The break is a live cutting control: driving, bilateral (swTolBILAT = 2)
# at the model's nominal and band -- re-read on the sheet, not trusted.
_break_lower, _break_upper = deviations(CUT_END_BREAK_BAND)
BREAK_CONTROLS = {
    CUT_END_BREAK_DIMENSION: (
        CUT_END_BREAK_MM / 1000.0,
        _break_lower / 1000.0,
        _break_upper / 1000.0,
    )
}
BREAK_TOLERANCE_TYPES = {CUT_END_BREAK_DIMENSION: 2}
# Below the Front view (its lower end ~0.119), above the stock rows.
NOTES_XY = (0.016, 0.100)
STOCK_ROWS = (
    ("Supplier", 0.016, 0.060),
    ("Supplier SKUs", 0.080, 0.060),
    ("Stock Name", 0.016, 0.049),
)


def _reference_cut_length(adapter: Any, annotations: list[Any]) -> None:
    """Re-read the imported cut length, then mark it reference.

    It must be the model's nominal and carry NO band (swTolNONE): a band
    would promise a fixed length the post and plate bands cannot honour.
    """
    for annotation in annotations:
        if dimension_name(adapter, annotation) != CUT_LENGTH_DIMENSION:
            continue
        display = _early_bound(
            _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
            "IDisplayDimension",
        )
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        if abs(float(dimension.SystemValue) - CUT_LENGTH_MM / 1000.0) > 1e-9:
            raise RuntimeError(
                f"cut length {float(dimension.SystemValue)!r} m is not the "
                f"modelled {CUT_LENGTH_MM} mm"
            )
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        if int(tolerance.Type) != 0:  # swTolNONE
            raise RuntimeError("cut length carries a band; it must be reference")
        set_reference_dimension(adapter, annotation, label="cut length")
        return
    raise RuntimeError("Front view has no cut length to mark reference")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open cut post mount screw", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Stock Name",
        "Supplier",
        "Supplier SKUs",
        "Manufacturing Notes",
    )
    read_required_properties(adapter.currentModel, required, required=required)
    draw, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        draw,
        {
            0: TITLE,
            1: "Manufacturing controls for modified purchased stock",
            2: "Harmonic Analyzer Project",
            3: "MHA-142; MSC Industrial Supply 40923898",
            4: "Native dimension-driven cut length",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=SHEET_SCALE)
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)

    # The cut length lives on a part-hidden reference sketch, so the Front
    # view takes the opt-in curation that shows it in this view only.
    annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="cut length",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _reference_cut_length(adapter, annotations)
    trim_drawing.verify_machining_controls(
        adapter,
        [
            annotation
            for annotation in annotations
            if dimension_name(adapter, annotation) in BREAK_CONTROLS
        ],
        expected=BREAK_CONTROLS,
        tolerance_types=BREAK_TOLERANCE_TYPES,
        precision=DRAWING_PRECISION_BY_NAME,
    )
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    offset_dimension_text(
        adapter, annotations, {CUT_END_BREAK_DIMENSION: BREAK_TEXT}
    )

    add_property_linked_note(
        adapter, "Manufacturing Notes", *NOTES_XY, char_height=0.003
    )
    for name, x, y in STOCK_ROWS:
        add_property_linked_note(adapter, name, x, y, char_height=0.003)

    set_hidden_lines_removed(adapter, front)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title=TITLE,
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
