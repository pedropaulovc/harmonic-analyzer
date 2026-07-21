r"""Create the curated machinist drawing for the channel-spring plate hook.

A small formed-wire open J-hook.  The print shows a 5:1 front (profile) view, a
5:1 top view for the wire diameter, and a 5:1 isometric; the form is described
in the notes.  Shared behavior lives in ``_drawing_common``.

Run with SolidWorks open::

    uv run python cad\scripts\draw_spring_hook.py spring-hook
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
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from spring_hook_spec import (
    ARM_HEIGHT,
    ROD_DIA,
    SHANK_RISE,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    place_view,
)


SPEC = DRAWINGS_BY_NAME["spring_hook"]
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

SHEET_SCALE = (5.0, 1.0)  # 5:1
_S = SHEET_SCALE[0] / SHEET_SCALE[1]  # sheet-mm per model-mm (5.0)

# Front-view model bbox: X 0..arm-tip, Y 0..arm-height.
_BBOX_CX = 2.0
_BBOX_CY = ARM_HEIGHT / 2.0

FRONT_CENTER = (0.110, 0.150)
TOP_CENTER = (0.210, 0.150)
ISO_CENTER = (0.300, 0.150)


def _sheet_xy(mx: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) of a model point in the bbox-centred front view (5:1)."""
    return (
        FRONT_CENTER[0] + (mx - _BBOX_CX) * _S / 1000.0,
        FRONT_CENTER[1] + (my - _BBOX_CY) * _S / 1000.0,
    )


FRONT_KEEP = {
    "Rise": (0.075, FRONT_CENTER[1]),
    "ArmRun": (0.130, 0.205),
}
TOP_KEEP = {
    "RodDia": (0.210, 0.110),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open spring-hook source", await adapter.open_model(str(SOURCE)))
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
            0: "Spring Hook Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "spring hook; formed wire; plate hook",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(5, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(5, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(5, 1))
    for view in (top, iso):
        set_hidden_lines_removed(adapter, view)

    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    curate_view_dimensions(adapter, top, keep=TOP_KEEP, view_label="top")

    # Ra on the seating shank surface.
    shank_edge = _sheet_xy(ROD_DIA / 2.0, SHANK_RISE / 2.0)
    add_surface_finish(
        adapter,
        front,
        edge_xy=shank_edge,
        symbol_xy=(shank_edge[0] + 0.016, shank_edge[1] + 0.010),
        roughness_ra="1.6",
        label="shank seating finish",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.075)
    add_property_linked_note(adapter, "Isometric View Note", 0.280, 0.100)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Spring Hook Manufacturing Drawing",
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
