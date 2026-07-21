r"""Create the curated machinist drawing for the summing-lever boss hook.

The SLDPRT remains authoritative.  This recipe supplies only the hook's views,
the three form dimensions (wire diameter, rise, arm run), and the manufacturing
notes; every shared sheet/template, import, curation, and export behavior lives
in ``_drawing_common``.

The boss hook is a tiny Ø3 steel wire J-hook (12 rise, 90-degree R3 elbow,
3.5 arm run), so the sheet runs 4:1; the front view carries the J profile, a
top view shows the round wire section, and the isometric drops to 2:1.

Run with SolidWorks open::

    uv run python cad\scripts\draw_boss_hook.py boss-hook
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
from build_boss_hook import ARM_RUN, ROD_DIA, SHANK_RISE
from solidworks_mcp.adapters.solidworks.drawing import place_view


SPEC = DRAWINGS_BY_NAME["boss_hook"]
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

SHEET_SCALE = (4.0, 1.0)  # 4:1 whole sheet (the hook is ~6.5 x 15 mm)

# Sheet layout (meters).  The front view (J profile) sits left; the top view
# (round wire section + arm plan) rides above it; the isometric drops to 2:1.
FRONT_CENTER = (0.110, 0.150)
TOP_CENTER = (0.110, 0.238)
ISO_CENTER = (0.335, 0.170)

# Per-view survivors of the marked-dimension import.  Rise + ArmRun live on the
# Front-plane path (front view); the wire diameter lives on the Top-plane
# profile (top view).
FRONT_KEEP = {
    "Rise": (0.076, 0.150),
    "ArmRun": (0.118, 0.196),
}
TOP_KEEP = {
    "RodDia": (0.156, 0.238),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open boss-hook source", await adapter.open_model(str(SOURCE)))
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
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
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
            0: "Boss Hook Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "boss hook; steel wire J-hook; counter-spring",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(4, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    for view in (front, top, iso):
        set_hidden_lines_removed(adapter, view)

    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    curate_view_dimensions(adapter, top, keep=TOP_KEEP, view_label="top")

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.070)
    add_property_linked_note(adapter, "Isometric View Note", 0.300, 0.150)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Boss Hook Manufacturing Drawing",
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
