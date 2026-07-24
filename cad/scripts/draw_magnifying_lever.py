r"""Create the curated machinist drawing for the magnifying lever rod.

The rod is a revolved Ø6 x 165 brass capsule with hemispherical ends -- a
smooth, tangent-continuous body with NO flat face, no end-face circle and no
selectable silhouette edge, so coordinate picks are unreliable (the dome-tip
pick fails) and the print rests on the auto-imported profile marks only: the far
dome-centre station and the dome radius R3.  The outside diameter and the overall
length ride the dome-radius callout + the notes (the note-based path the recipe
pitfall endorses for un-pickable turned features).  The rod axis is local +X, so
the FRONT view is the long side elevation and the RIGHT view is the circular end.

Run with SolidWorks open::

    uv run python cad\scripts\draw_magnifying_lever.py magnifying-lever
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
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from magnifying_lever_spec import ROD_DIA, ROD_LENGTH
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["magnifying_lever"]
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
END_VIEW_SCALE = 4.0
FRONT_CENTER = (0.115, 0.150)
RIGHT_CENTER = (
    FRONT_CENTER[0] + ROD_LENGTH * SHEET_SCALE[0] / 2000.0 + 0.055,
    FRONT_CENTER[1],
)
ISO_CENTER = (0.350, 0.185)
ISO_SCALE = (1, 2)

# The two native profile dims the print keeps: the far dome-centre station
# (below the side view) and the dome radius (above the right dome).
FRONT_KEEP = {
    "RightDomeCentre": (FRONT_CENTER[0], FRONT_CENTER[1] - 0.032),
    "DomeRadius": (RIGHT_CENTER[0] - 0.075, FRONT_CENTER[1] + 0.028),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
DIMENSION_CALLOUTS = {
    "DomeRadius": "FULL R, BOTH ENDS - Ø6 ROD",
    "RightDomeCentre": "TO FAR DOME CENTRE",
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open magnifying-lever source", await adapter.open_model(str(SOURCE)))
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Magnifying Lever Rod Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "magnifying lever; turned brass rod; domed ends",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(4, 1))
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right")
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    # The end silhouette is circular; SolidWorks files it under the same
    # "hole" bit as a bored circle, so a disabled bit makes the API a no-op.
    if not auto_center_marks(adapter, right, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to rod end view")

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.100)
    add_property_linked_note(adapter, "End View Note", RIGHT_CENTER[0] - 0.022, 0.100)
    add_property_linked_note(adapter, "Iso View Note", 0.320, 0.140)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Magnifying Lever Rod Manufacturing Drawing",
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
