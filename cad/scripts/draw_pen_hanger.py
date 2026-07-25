r"""Create the curated machinist drawing for the pen hanger.

The SLDPRT remains authoritative.  This recipe supplies only the hanger's views,
strap/block envelope dimensions, the hanger-screw callout, and manufacturing
notes; every shared sheet/template, import, curation, and export behavior lives
in ``_drawing_common``.

The pen hanger is a black tapered steel strap (3 thick, 10 -> 16 wide) rising
from a 12 x 12 guide block; the block carries a 5.4 square vertical channel the
pen rod slides in, and a #6-32 tapped hanger-screw hole passes through the strap
top from behind.  The part is tall and narrow (~82 x 22), so the front profile is
the sole ortho view at 2:1 with an isometric to its right.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pen_hanger.py pen-hanger
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    auto_center_marks,
    DrawingOutputs,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from build_pen_hanger import (
    BLOCK_HALF,
    STRAP_BOT_X,
    STRAP_TOP_X,
    STRAP_TOP_Y,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pen_hanger"]
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

SHEET_SCALE = (2.0, 1.0)   # 2:1 whole sheet (~82 mm tall part)
VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]  # 2.0 sheet-mm per model-mm / 1000

# Front-view model bounding box (X-Y profile of the strap + block).
_BBOX_X = (min(STRAP_TOP_X[0], STRAP_BOT_X[0], -BLOCK_HALF),
           max(STRAP_TOP_X[1], STRAP_BOT_X[1], BLOCK_HALF))
_BBOX_Y = (-BLOCK_HALF, STRAP_TOP_Y)
_BBOX_CX = (_BBOX_X[0] + _BBOX_X[1]) / 2.0
_BBOX_CY = (_BBOX_Y[0] + _BBOX_Y[1]) / 2.0

# Sheet layout (meters).  Tall front view hugs the left; the isometric sits to
# the right; the notes fill the clear mid band between them (never crossing the
# thin front view).
FRONT_CENTER = (0.075, 0.150)
ISO_CENTER = (0.320, 0.170)
TOP_CENTER = (0.205, 0.225)


def _fx(model_x_mm: float) -> float:
    return FRONT_CENTER[0] + (model_x_mm - _BBOX_CX) * VIEW_SCALE / 1000.0


def _fy(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - _BBOX_CY) * VIEW_SCALE / 1000.0


# Per-view survivors of the marked-dimension import (all Front-plane sketch dims):
# the block width, the strap bottom/top widths and the strap rise.  Positioned to
# the left / top of the tall narrow view, clear of the mid-band notes.
FRONT_KEEP = frozenset(
    {"StrapTopRun", "StrapTaperDy", "StrapBotWidth", "BlockWidth"}
)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pen-hanger source", await adapter.open_model(str(SOURCE)))
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
            "Front View Note",
            "Top View Note",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Front View Note",
            "Top View Note",
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
            0: "Pen Hanger Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pen hanger; tapered strap; pen-rod guide block",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))

    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    if not auto_center_marks(adapter, front, holes=True):
        raise RuntimeError("failed to add ASME center mark to the hanger-screw hole")

    # Do not add a native callout here: R2026x renders a through tapped Hole
    # Wizard feature as the contradictory "thread depth 0.00".  The linked
    # manufacturing note carries the complete #6-32 UNC-2B THRU requirement,
    # while the center mark and modeled hole remain associative.

    add_property_linked_note(adapter, "Manufacturing Notes", 0.115, 0.150)
    add_property_linked_note(adapter, "Front View Note", 0.030, 0.036)
    add_property_linked_note(adapter, "Top View Note", 0.170, 0.195)
    add_property_linked_note(adapter, "Isometric View Note", 0.286, 0.104)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pen Hanger Manufacturing Drawing",
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
