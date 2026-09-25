r"""Create the modified-stock drawing for the MHA-142 cone pivot post mount screw.

MSC 40923898 is bought by SKU and cut to length, so the sheet is a
modified-purchased-part drawing (the boss hook's pattern), not the purchased
reference sheet: a Front view carrying the cut length -- the part's hidden
reference dimension, imported with its model-owned places and its band
(never proud of the MHA-091 underside) -- and an isometric, both 1:1.  The
only note says to chamfer the cut end and that the undimensioned purchased
geometry is reference.  No installation sequence, engagement figure or rule
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
from _common import check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    assert_imported_precision,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _fit_limits import deviations
from post_mount_screw_spec import (
    CUT_LENGTH_BAND,
    CUT_LENGTH_DIMENSION,
    CUT_LENGTH_MM,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
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
# shank's silhouette, midway along the span.
FRONT_KEEP = {CUT_LENGTH_DIMENSION: (FRONT_CENTER[0] - 0.022, FRONT_CENTER[1])}
# Below the Front view (its lower end ~0.119), above the stock rows.
NOTES_XY = (0.016, 0.100)
STOCK_ROWS = (
    ("Supplier", 0.016, 0.060),
    ("Supplier SKUs", 0.080, 0.060),
    ("Stock Name", 0.016, 0.049),
)
# The cut length is a live cutting control: driving, bilateral (swTolBILAT
# = 2), at the model's nominal and band -- re-read on the sheet, not trusted.
_LOWER, _UPPER = deviations(CUT_LENGTH_BAND)
EXPECTED_CONTROLS = {
    CUT_LENGTH_DIMENSION: (CUT_LENGTH_MM / 1000, _LOWER / 1000, _UPPER / 1000)
}
TOLERANCE_TYPES = {CUT_LENGTH_DIMENSION: 2}


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
    trim_drawing.verify_machining_controls(
        adapter,
        annotations,
        expected=EXPECTED_CONTROLS,
        tolerance_types=TOLERANCE_TYPES,
        precision=DRAWING_PRECISION_BY_NAME,
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
