r"""Create the curated machinist drawing for the gooseneck counter-spring post.

The SLDPRT remains authoritative.  This recipe supplies only the post's
elevation + isometric views, the bend-radius / arm-run dimensions, and the
manufacturing notes; every shared sheet/template, import, curation, and export
behavior lives in ``_drawing_common``.

The post is a polished chrome Ø16 tube: a tall vertical leg, a 90-degree bend
(R51) at the top, and a horizontal arm carrying a Ø4 spring cross-pin at its
lug.  The part is ~506 mm tall, so the sheet runs 1:3; the isometric drops to
1:4.

Run with SolidWorks open::

    uv run python cad\scripts\draw_gooseneck.py gooseneck
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
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.solidworks.drawing import place_view


SPEC = DRAWINGS_BY_NAME["gooseneck"]
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

SHEET_SCALE = (1.0, 3.0)   # 1:3 whole sheet (~506 mm tall post)

# Sheet layout (meters).  The elevation (front) shows the goose-neck profile
# (leg + bend + arm) right of centre so the notes clear it; the isometric (1:4)
# sits far right; the notes fill the lower-left.
FRONT_CENTER = (0.180, 0.150)
ISO_CENTER = (0.350, 0.150)
# NO lug detail view. Four attempts (three commits + a bbox-shift fix) left
# CreateDetailViewAt4 rendering an empty or near-empty circle even with the
# fence verified ON the lug: the activated-view sketch transform anchors the
# model ORIGIN at the view position while CreateDrawViewFromModelView3 centers
# the geometry BBOX there, and even a correctly-shifted fence produced a detail
# whose content window did not match its fence. The lug/pin are fully specified
# by notes 3-5 (sizes, locations, braze schedule), matching the note-based
# style the rest of this batch already uses, so the detail adds legibility
# only -- not manufacturability -- and is dropped rather than iterated again.

# Per-view survivors of the marked-dimension import: the bend radius (R51) and
# the horizontal arm run, both on the Front-plane sweep path (so both project to
# the elevation).  Positions are near the bend/arm at the top of the view.
FRONT_KEEP = {
    "BendRadius": (0.225, 0.212),
    "ArmRun": (0.150, 0.250),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open gooseneck source", await adapter.open_model(str(SOURCE)))
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
            "Elevation View Note",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Elevation View Note",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Gooseneck Post Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "gooseneck; chrome tube; 90-deg bend; spring post",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 3))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 4))
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)

    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")

    # 0.114 (was 0.105): machinist round 2 grew the notes to 22 lines and the
    # block crossed the bottom zone border by 16.1 mm; the trim reclaims ~2
    # lines and the raise covers the rest (nothing sits above until the
    # elevation leg at x>0.16).
    add_property_linked_note(adapter, "Manufacturing Notes", 0.016, 0.114)
    add_property_linked_note(adapter, "Elevation View Note", 0.160, 0.022)
    add_property_linked_note(adapter, "Isometric View Note", 0.300, 0.095)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Gooseneck Post Manufacturing Drawing",
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
