r"""Create the curated machinist drawing for the lever fulcrum shaft."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _check import check
from _paths import CAD_ROOT
from _session import run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    add_surface_finish,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from ch_fulcrum_shaft_spec import (
    DRAWING_DIMENSIONS,
    FLAT_FROM_END,
    SHAFT_DIA,
    SHAFT_LENGTH,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
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

SHEET_SCALE = (1.0, 1.0)
END_VIEW_SCALE = 2.0
FRONT_CENTER = (0.055, 0.205)
RIGHT_CENTER = (
    FRONT_CENTER[0] + SHAFT_LENGTH * SHEET_SCALE[0] / 2000.0 + 0.045,
    FRONT_CENTER[1],
)
ISO_CENTER = (0.355, 0.205)
# 1:2, like the near-identical 187 arbor on MHA-DT-013: at 1:1 the shaft's
# isometric is a long diagonal bar that runs over the right zone border.
ISO_SCALE = (1, 2)
# Both profile sketches lie on the Right plane, so every print dimension
# lands in the side view.  The sketch +u axis is model -Z, which the *Right
# view draws to sheet-RIGHT (the build_ch_pivot_shaft mapping); the flat
# length and the across-flat witness ride the +u flat, and the -u flat's
# station off the sheet-LEFT dome tip sits at the flat length's height,
# under the FlatPitch.
_TIP_X = RIGHT_CENTER[0] + SHAFT_LENGTH / 2000.0
_MINUS_U_STATION_X = (
    RIGHT_CENTER[0] - (SHAFT_LENGTH / 2.0 - FLAT_FROM_END / 2.0) / 1000.0
)
# Machinist review r8: the Ø6.350 limit text sat across the silhouette; it
# now stands under the shaft, ~3.5 mm clear of both the shaft's lower edge and
# the 161.35 text below it. The "2X 3.5" (wider than r8's "3.5", which the
# 148.000 pitch's extension line ran through) stands right of its flat
# over the dome tip. "2X 6.050" moves right to keep ~10 mm between its upper
# arrow and that flat length's dimension line.
SHAFT_DIA_TEXT_DROP = 0.011
FLAT_LENGTH_TEXT_X = _TIP_X + 0.005
ACROSS_FLAT_TEXT_X = _TIP_X + 0.022
FRONT_KEEP: dict[str, tuple[float, float]] = {}
RIGHT_KEEP = {
    "OverallLength": (RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.020),
    "ShaftDia": (RIGHT_CENTER[0] - 0.030, RIGHT_CENTER[1] - SHAFT_DIA_TEXT_DROP),
    # Chained, not baselined: 148 is the keeper pitch; a tip baseline stacks 2 bands.
    "FlatPitch": (RIGHT_CENTER[0], RIGHT_CENTER[1] + 0.024),
    "FlatFromEnd": (_MINUS_U_STATION_X, RIGHT_CENTER[1] + 0.013),
    "FlatLength": (FLAT_LENGTH_TEXT_X, RIGHT_CENTER[1] + 0.013),
    "AcrossFlat": (ACROSS_FLAT_TEXT_X, RIGHT_CENTER[1]),
}


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
            "End View Note",
            "Iso View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "End View Note",
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
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    # The end view carries no dimension: it shows the flat's chord on the
    # round, and every size is in the side view.
    curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # SolidWorks classifies a solid circular end silhouette under the same
    # AutoInsertCenterMarks2 "hole" bit as a bored circle; disabling that bit
    # makes the API a guaranteed no-op even though the end view is circular.
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to shaft end view")

    # The bearing O.D.'s roughness: picked on the end circle's RIGHTMOST point
    # (the flat is on top), symbol up-right so the leader comes in from the
    # right and never crosses the circle.
    end_radius = SHAFT_DIA * END_VIEW_SCALE / 2000.0
    add_surface_finish(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0] + end_radius, FRONT_CENTER[1]),
        symbol_xy=(0.075, 0.222),
        control=surface_finish_by_key(SURFACE_FINISHES, "bearing"),
        label="fulcrum bearing finish",
    )

    # 0.020: the note is left-aligned on its anchor, so the ink starts here. The
    # left bound is the 12.7 mm zone margin (~0.0127), which the re-centred frame
    # rule now matches (~0.0126); 0.020 clears both, and the audit enforces it.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.108)
    add_property_linked_note(adapter, "End View Note", 0.020, 0.170)
    # The iso renders at 1:2 while the title block reads 1:1, so the pictorial
    # needs its own scale callout or the sheet misstates it. Placed at the same
    # offset from ISO_CENTER that cylinder-gear-shaft uses for its identical 1:2
    # iso (dx -0.030, dy -0.048), so the two sibling shafts read alike.
    add_property_linked_note(adapter, "Iso View Note", 0.325, 0.157)

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
