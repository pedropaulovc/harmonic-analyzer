r"""Create the curated machinist drawing for the tube-frame column.

The SLDPRT remains authoritative.  This recipe supplies only the column's views,
diameter/length dimensions, and manufacturing notes; every shared sheet/template,
import, curation, and export behavior lives in ``_drawing_common``.

The tube axis runs along +Y, so the length view is the ``*Front`` orientation
(tube vertical) and the annulus end view is ``*Top``.  The column is ~990 mm
long, so the sheet runs 1:5; the end view carries an explicit 2:1 override so the
Ø25.4/Ø19.3 annulus is legible.  A plain polished tube is fully described by the
length view + annulus end view + notes, so no isometric is drawn (it would only
crowd the tall length view).

Run with SolidWorks open::

    uv run python cad\scripts\draw_tube_frame.py tube-frame
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_feature_control_frame,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)
from tube_frame_spec import COLUMN_LENGTH, OUTER_DIA


SPEC = DRAWINGS_BY_NAME["tube_frame"]
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

SHEET_SCALE = (1.0, 5.0)   # 1:5 whole sheet (~990 mm column)
END_VIEW_SCALE = 2.0

# Sheet layout (meters).  The length view (tube vertical) hugs the far left,
# full sheet height; the annulus end view sits upper-right at 2:1.  The notes
# fill the clear mid band to the RIGHT of the thin tube (so they never cross it).
LENGTH_CENTER = (0.065, 0.150)
END_CENTER = (0.300, 0.195)

# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position (meters).  Diameters live on the end view, the length on the tube view.
END_KEEP = {
    "OuterDia": (
        END_CENTER[0] - OUTER_DIA * END_VIEW_SCALE / 1000.0 - 0.024,
        END_CENTER[1] + 0.010,
    ),
}
LENGTH_KEEP = {
    "Depth": (LENGTH_CENTER[0] + 0.028, LENGTH_CENTER[1]),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open tube-frame source", await adapter.open_model(str(SOURCE)))
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
            "Length View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "End View Note",
            "Length View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Tube Frame Column Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "tube frame; column; steel tube; polished",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    length = place_view(adapter, str(SOURCE), "*Front", *LENGTH_CENTER, scale=(1, 5))
    end = place_view(adapter, str(SOURCE), "*Top", *END_CENTER, scale=(2, 1))
    set_hidden_lines_removed(adapter, end)
    # The length view carries the bore as greyed hidden lines, so the wall shows.
    set_hidden_lines_visible(adapter, length)

    end_annotations = curate_view_dimensions(
        adapter, end, keep=END_KEEP, view_label="end"
    )
    curate_view_dimensions(adapter, length, keep=LENGTH_KEEP, view_label="length")
    set_dimension_precision(adapter, end_annotations, {"OuterDia": 2})
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the annulus end view")

    end_top = (
        END_CENTER[0],
        END_CENTER[1] + OUTER_DIA * END_VIEW_SCALE / 2000.0,
    )
    add_datum_feature(
        adapter,
        end,
        edge_xy=end_top,
        symbol_xy=(END_CENTER[0], END_CENTER[1] + 0.038),
        datum="A",
        label="finished OD derived axis",
    )
    flank_x = LENGTH_CENTER[0] + OUTER_DIA / 10000.0
    add_feature_control_frame(
        adapter,
        length,
        edge_xy=(flank_x, LENGTH_CENTER[1]),
        frame_xy=(0.115, 0.205),
        characteristic="cylindricity",
        tolerance="0.03",
        quantity="FULL OD LENGTH",
        label="full-length OD cylindricity",
        entity_type="SILHOUETTE",
    )
    half_length_on_sheet = COLUMN_LENGTH / 10000.0
    for edge_y, frame_y, label, quantity in (
        (
            LENGTH_CENTER[1] - half_length_on_sheet,
            0.045,
            "bottom end perpendicularity",
            "BOTTOM END FACE",
        ),
        (
            LENGTH_CENTER[1] + half_length_on_sheet,
            0.255,
            "top end perpendicularity",
            "TOP END FACE",
        ),
    ):
        add_feature_control_frame(
            adapter,
            length,
            edge_xy=(LENGTH_CENTER[0], edge_y),
            frame_xy=(0.090, frame_y),
            characteristic="perpendicularity",
            tolerance="0.10",
            datums=("A",),
            quantity=quantity,
            label=label,
        )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.115, 0.125)
    add_property_linked_note(adapter, "End View Note", 0.275, 0.162)
    add_property_linked_note(adapter, "Length View Note", 0.020, 0.033)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Tube Frame Column Manufacturing Drawing",
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
