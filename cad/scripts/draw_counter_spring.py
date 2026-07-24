r"""Create the curated machinist SPEC SHEET for the counter spring.

A coil spring is documented by a data table, not by graphical dimensions on the
helix, so this print is a single 1:2 side view, a small 1:3 isometric, and the
spring data table (a property-linked note).  Every shared sheet/template lives
in ``_drawing_common``.

Run with SolidWorks open::

    uv run python cad\scripts\draw_counter_spring.py counter-spring
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
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.solidworks.drawing import (
    place_view,
)


SPEC = DRAWINGS_BY_NAME["counter_spring"]
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

SHEET_SCALE = (1.0, 2.0)  # 1:2

FRONT_CENTER = (0.090, 0.140)
ISO_CENTER = (0.230, 0.150)

FRONT_KEEP: tuple[str, ...] = ()
RIGHT_KEEP: tuple[str, ...] = ()
TOP_KEEP: tuple[str, ...] = ()


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open counter-spring source", await adapter.open_model(str(SOURCE)))
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
            0: "Counter Spring Spec Sheet",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "counter spring; extension spring; coiled wire",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 2))
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 3))

    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")

    # The spring data table (right of the side view) + the iso scale note.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.300, 0.235)
    add_property_linked_note(adapter, "Isometric View Note", 0.210, 0.075)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Counter Spring Spec Sheet",
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
