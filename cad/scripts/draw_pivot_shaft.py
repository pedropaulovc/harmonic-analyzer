r"""Create the curated machinist drawing for the rocker pivot shaft."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    import_part_pmi,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import MACHINED
from pivot_shaft_spec import GEOMETRIC_CONTROLS, SHAFT_DIA, SHAFT_LENGTH
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pivot_shaft"]
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

SHEET_SCALE = (1.0, 1.0)
FRONT_CENTER = (0.055, 0.205)
RIGHT_CENTER = (
    FRONT_CENTER[0] + SHAFT_LENGTH * SHEET_SCALE[0] / 2000.0 + 0.045,
    FRONT_CENTER[1],
)
# NOT the fulcrum-shaft spot (0.355, 0.205): the 203.2 shaft's isometric
# silhouette reaches ~0.072 m each side of center, so up there it ran past the
# right border line and onto the right-end GD&T. The empty band between the
# notes block and the title block fits it whole (its low tip stays above the
# title block's 0.064 top rule).
ISO_CENTER = (0.320, 0.120)

# The shaft's flank in the *Right view: a 6.35-dia cylinder at 1:1, so its top
# silhouette runs ~3.2 mm above the view centre. The bearing Ra anchors HERE
# rather than on the front view's end circle -- see the finish block below.
SHAFT_FLANK_Y = RIGHT_CENTER[1] + SHAFT_DIA * SHEET_SCALE[0] / 2000.0

FRONT_KEEP = {
    # x=0.030, not the bbox-derived 0.017: horizontal text made this callout
    # ~25 mm wide ("+0.00/-0.02"), so centred that far left it ran over the
    # 12.7 mm zone margin. 0.030 clears the margin on the left and stops short
    # of the end circle at x=0.049 on the right.
    "ShaftDia": (0.030, 0.220),
}
RIGHT_KEEP = {
    "Depth": (RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.025),
}
DIMENSION_CALLOUTS = {"ShaftDia": "+0.00/-0.02", "Depth": "+/-0.25"}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pivot-shaft source", await adapter.open_model(str(SOURCE)))
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
            "End View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "End View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pivot Shaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pivot shaft; rocker bearing shaft; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    # Each call must consume every callout it is handed, so split by view.
    set_dimension_callouts(
        adapter,
        front_annotations,
        {n: t for n, t in DIMENSION_CALLOUTS.items() if n in FRONT_KEEP},
    )
    set_dimension_callouts(
        adapter,
        right_annotations,
        {n: t for n, t in DIMENSION_CALLOUTS.items() if n in RIGHT_KEEP},
    )
    # SolidWorks classifies a solid circular end silhouette under the same
    # AutoInsertCenterMarks2 "hole" bit as a bored circle; disabling that bit
    # makes the API a guaranteed no-op even though the end view is circular.
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to shaft end view")

    left_end = (RIGHT_CENTER[0] - SHAFT_LENGTH / 2000.0, RIGHT_CENTER[1])
    right_end = (RIGHT_CENTER[0] + SHAFT_LENGTH / 2000.0, RIGHT_CENTER[1])
    # GD&T is model PMI (pivot_shaft_spec.PART_DATUMS/GEOMETRIC_CONTROLS,
    # authored by build_pivot_shaft) — import it and place it where the
    # hand-authored symbols used to sit (sheet-LEFT of the *Right view is the
    # model +Z end, so the +Z squareness frame takes the left-end spot). Which
    # VIEW receives each annotation depends on its attachment (a datum tag
    # only lands in a view aligned with its face), and the importer fails
    # loud on any mismatch.
    import_part_pmi(
        adapter,
        (front, right),
        datum_positions={"A": (FRONT_CENTER[0], FRONT_CENTER[1] + 0.024)},
        control_positions={
            "bearing_cylindricity": (RIGHT_CENTER[0] - 0.045, 0.236),
            "plus_z_end_perpendicularity": (left_end[0] - 0.042, 0.180),
            "minus_z_end_perpendicularity": (right_end[0] + 0.014, 0.180),
        },
        controls=GEOMETRIC_CONTROLS,
        label="pivot shaft PMI",
    )
    # The bearing finish controls the shaft's CYLINDRICAL face, which the side
    # view shows edge-on -- so it anchors to the flank there instead of to the
    # front view's end circle (from which the leader had to run the whole way
    # back across the side view). A cylinder carries no model edge along its
    # side, so the pick is a SILHOUETTE entity (as in draw_transgear_stub).
    # The Ra text renders ABOVE the arm (ASME Y14.36), reaching y~0.236.
    add_surface_finish(
        adapter,
        right,
        edge_xy=(RIGHT_CENTER[0] + 0.045, SHAFT_FLANK_Y),
        symbol_xy=(RIGHT_CENTER[0] + 0.045, 0.222),
        roughness_ra=MACHINED,
        label="pivot bearing finish",
        entity_type="SILHOUETTE",
    )

    # 0.020: a note is left-aligned on its anchor, so the ink starts here. The
    # bound is the 12.7 mm zone margin (~0.0127), which the re-centred border rule
    # now matches (~0.0126); 0.020 clears both, and the audit enforces it.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.108)
    add_property_linked_note(adapter, "End View Note", 0.020, 0.170)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pivot Shaft Manufacturing Drawing",
        scale=SHEET_SCALE,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
