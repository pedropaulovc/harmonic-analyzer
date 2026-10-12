r"""Create the curated machinist drawing for the magnifying lever rod.

The rod is a revolved Ø6 x 165 brass capsule with hemispherical ends -- a
smooth, tangent-continuous body with NO flat face, no end-face circle and no
selectable silhouette edge, so coordinate picks are unreliable (the dome-tip
pick fails) and the print rests on the auto-imported profile marks (the far
dome-centre station and the dome radius R3) plus two blanked reference sketches
the FRONT view shows and dimensions: ``RodStock`` (the stock Ø6 at mid-length)
and ``PressZone`` (the straight engagement the bracket collar grips -- its
length from the dome tangent and its banded diameter, tied to the MHA-MG-001
bore it enters).  The overall length rides the notes (the note-based path the
recipe pitfall endorses for un-pickable turned features).  The rod axis is
local +X, so the FRONT view is the long side elevation and the RIGHT view is
the circular end.

Run with SolidWorks open::

    uv run python cad\scripts\draw_mg_magnifying_lever.py mg-magnifying-lever
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)

from _check import check
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_hidden_sketches import curate_view_dimensions as curate_hidden_dimensions
from _drawing_dimensions import set_dimension_callouts
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from mg_lever_press_fit_geom import COLLAR_ENGAGEMENT, ROD_DIA
from mg_magnifying_lever_spec import (
    DRAWING_DIMENSIONS,
    PRESS_ZONE_DIA_CALLOUT,
    ROD_LENGTH,
)


SPEC = DRAWINGS_BY_NAME["mg_magnifying_lever"]
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
# (below the side view) and the dome radius, above and right of the right dome
# so its leader climbs steeply, clear of the press zone's extension line at
# the dome tangent.
FRONT_KEEP = {
    "RightDomeCentre": (FRONT_CENTER[0], FRONT_CENTER[1] - 0.032),
    "DomeRadius": (RIGHT_CENTER[0] - 0.047, FRONT_CENTER[1] + 0.025),
}
# The reference sketches' dims.  The stock diameter above the rod at
# mid-length.  The press zone at the rod's east (dome-tip) end: the straight
# engagement's length above the rod, pushed left of the dome-radius leader
# (the 7 mm span cannot hold its own text, so SolidWorks sets the text outside
# the extension lines; v41 landed "FROM TIP" under the R3 leader at -0.006);
# the banded diameter below-right of the tip, its long mate callout running
# right under the end view, below the isometric caption and above the end-view
# caption, clear of the far-dome-centre dimension line (x <= 0.195).
_ROD_TIP_X = FRONT_CENTER[0] + ROD_LENGTH * SHEET_SCALE[0] / 2000.0
_PRESS_ZONE_MID_X = (
    _ROD_TIP_X - (ROD_DIA / 2.0 + COLLAR_ENGAGEMENT / 2.0) * SHEET_SCALE[0] / 1000.0
)
REFERENCE_KEEP = {
    "RodDia": (FRONT_CENTER[0], FRONT_CENTER[1] + 0.020),
    "PressZoneLen": (_PRESS_ZONE_MID_X - 0.026, FRONT_CENTER[1] + 0.013),
    "PressZoneDia": (_ROD_TIP_X + 0.018, FRONT_CENTER[1] - 0.025),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
DIMENSION_CALLOUTS = {
    "DomeRadius": "BOTH ENDS",
    "RightDomeCentre": "TO FAR DOME CENTRE",
}
REFERENCE_CALLOUTS = {
    "RodDia": "STOCK OD",
    "PressZoneLen": "PRESS ZONE",
    "PressZoneDia": PRESS_ZONE_DIA_CALLOUT,
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
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
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right")
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    # The part saves PressZone and RodStock blanked (they would print in every
    # assembly render); shown here per view, their dimensions import and stay.
    reference_annotations = curate_hidden_dimensions(
        adapter,
        front,
        keep=REFERENCE_KEEP,
        view_label="front reference sketches",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(adapter, reference_annotations, REFERENCE_CALLOUTS)
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
