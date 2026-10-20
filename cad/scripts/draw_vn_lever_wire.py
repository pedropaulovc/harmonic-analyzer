r"""Create the curated machinist drawing for the lever wire (WIRE 1).

The installed straight-run envelope and its incomplete development remain
unchanged. A separate sketch-only stock view carries the supplier's nominal
diameter in supplier units and displayed precision, without applying that
nominal to the installed in-band 0.8 mm silhouette. The rest-run note is not
a developed cut length: the model does not define hook or drum-wrap allowance.

Run with SolidWorks open::

    uv run python cad\scripts\draw_vn_lever_wire.py vn-lever-wire
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import place_view

from _check import check
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
from _supplier_wire_stock_drawing import STOCK_KEEP as STOCK_KEEP
from _supplier_wire_stock_drawing import add_nominal_stock_cross_section
from vn_lever_wire_spec import DRAWING_DIMENSIONS
import _telemetry


SPEC = DRAWINGS_BY_NAME["vn_lever_wire"]
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
WIRE_SCALE = (1, 5)  # ~353 long reduced to ~71 mm on the sheet
FRONT_CENTER = (0.135, 0.150)
ISO_CENTER = (0.320, 0.160)

# The installed envelope carries no size import. The separate stock view
# imports STOCK_KEEP from the source-authored nominal cross-section.
FRONT_KEEP: dict[str, tuple[float, float]] = {}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open lever-wire source", await adapter.open_model(str(SOURCE)))
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
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Front View Note",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Lever Wire (WIRE 1) Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "lever wire; purchased music wire; amplification chain",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=WIRE_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=WIRE_SCALE)
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)

    curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_settled_stock = add_nominal_stock_cross_section(adapter, SOURCE)

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.075)
    add_property_linked_note(adapter, "Front View Note", 0.100, 0.100)
    add_property_linked_note(adapter, "Isometric View Note", 0.300, 0.100)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Lever Wire (WIRE 1) Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(assert_settled_stock,),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
