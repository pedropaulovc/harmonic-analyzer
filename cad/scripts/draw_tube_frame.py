r"""Create the curated machinist drawing for the tube-frame column.

The SLDPRT remains authoritative. This recipe supplies the regular open tube's
orthographic views, diameter/cut-length/cross-hole dimensions, and manufacturing
notes; shared sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The tube axis runs along +Y, so the length view is the ``*Front`` orientation
and the annulus end view is ``*Top``. The portrait sheet uses the long axis for
the 1018.765 mm cut length at 1:5; the aligned end view carries an explicit
2:1 override. The isometric is pictorial only.

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
    add_property_linked_note,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


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

SHEET_SCALE = (1.0, 5.0)  # 1:5 whole sheet (1018.765 mm cut tube)
END_VIEW_SCALE = 2.0
ISO_VIEW_SCALE = (1, 10)
# The aligned length/end views occupy the left column of the portrait sheet;
# fitting notes and the pictorial view occupy the right column.
LENGTH_CENTER = (0.055, 0.220)
END_CENTER = (LENGTH_CENTER[0], 0.360)
ISO_CENTER = (0.205, 0.140)

# Per-view survivors of the marked-dimension import.
END_KEEP = {
    "OuterDia": (
        END_CENTER[0] + 0.060,
        END_CENTER[1] + 0.010,
    ),
}
LENGTH_KEEP = {
    "Length": (LENGTH_CENTER[0] + 0.045, LENGTH_CENTER[1]),
    # Keep the station references clear of the tube and each other; the lower
    # one remains left of the tube now that its diameter prefix is removed.
    "LowerHoleY": (LENGTH_CENTER[0] - 0.020, LENGTH_CENTER[1] - 0.075),
    "UpperHoleY": (LENGTH_CENTER[0] + 0.028, LENGTH_CENTER[1] + 0.075),
    "CrossHoleDia": (LENGTH_CENTER[0] + 0.080, LENGTH_CENTER[1] - 0.120),
    "TopChamfer": (LENGTH_CENTER[0] + 0.080, LENGTH_CENTER[1] + 0.120),
}
DIMENSION_CALLOUTS = {
    "CrossHoleDia": "2 STATIONS; DRILL THRU BOTH WALLS",
    "TopChamfer": "X 45 DEG; TOP END; CAP MHA-133 MUST SEAT FULLY",
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
            "Isometric View Note",
            "Length View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "End View Note",
            "Isometric View Note",
            "Length View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
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
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_VIEW_SCALE
    )
    set_hidden_lines_removed(adapter, iso)

    end_annotations = curate_view_dimensions(
        adapter, end, keep=END_KEEP, view_label="end"
    )
    length_annotations = curate_view_dimensions(
        adapter, length, keep=LENGTH_KEEP, view_label="length"
    )
    dimensions = [*end_annotations, *length_annotations]
    set_dimension_callouts(adapter, dimensions, DIMENSION_CALLOUTS)
    set_dimension_precision(
        adapter,
        dimensions,
        {
            "OuterDia": 2,
            "Length": 2,
            "LowerHoleY": 2,
            "UpperHoleY": 2,
            "CrossHoleDia": 2,
            "TopChamfer": 2,
        },
    )
    for name in ("LowerHoleY", "UpperHoleY"):
        references = [
            annotation
            for annotation in length_annotations
            if dimension_name(adapter, annotation) == name
        ]
        if len(references) != 1:
            raise RuntimeError(
                f"expected one {name} reference dimension, got {len(references)}"
            )
        set_reference_dimension(
            adapter,
            references[0],
            label=f"{name} station reference",
        )
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the annulus end view")

    # Both end rims receive native centre marks; the length view exposes both
    # cross-drilled stations through visible hidden geometry.

    add_property_linked_note(
        adapter, "Manufacturing Notes", 0.145, 0.225, char_height=0.0025
    )
    add_property_linked_note(adapter, "End View Note", 0.020, 0.328)
    add_property_linked_note(adapter, "Isometric View Note", 0.170, 0.085)
    add_property_linked_note(adapter, "Length View Note", 0.020, 0.083)
    for view in (length, end):
        set_hidden_lines_visible(adapter, view)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Tube Frame Column Manufacturing Drawing",
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
