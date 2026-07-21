r"""Create the curated machinist drawing for the amplitude bar.

The SLDPRT remains authoritative.  This recipe supplies only the amplitude-bar
views, dimension layout, and manufacturing notes; every shared sheet/template,
import, curation, and export behavior lives in ``_drawing_common``.

The bar is ~813 mm long but only 6.35 mm square, so the print shows a 1:4
full-length front view (overall length only), a 4:1 top end view for the square
section, and a small 1:8 isometric; the two tiny end notches and the top pin
hole are dimensioned in the notes.  The sheet runs at 1:4.

Run with SolidWorks open::

    uv run python cad\scripts\draw_amplitude_bar.py amplitude-bar
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
    add_edge_dimension,
    add_feature_control_frame,
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
from amplitude_bar_spec import (
    BAR_DEPTH,
    BAR_LENGTH,
    BAR_WIDTH,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    place_view,
)


SPEC = DRAWINGS_BY_NAME["amplitude_bar"]
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

SHEET_SCALE = (1.0, 4.0)  # 1:4
_S = SHEET_SCALE[0] / SHEET_SCALE[1]  # sheet-mm per model-mm (0.25)

# Front-view model bbox: X symmetric about half-width, Y 0..BAR_LENGTH.
_BBOX_CX = BAR_WIDTH / 2.0
_BBOX_CY = BAR_LENGTH / 2.0

FRONT_CENTER = (0.110, 0.140)
TOP_CENTER = (0.220, 0.150)  # square-section end view (4:1)
ISO_CENTER = (0.330, 0.140)
_TOP_SCALE = 4.0


def _sheet_xy(mx: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) of a model point in the bbox-centred front view (1:4)."""
    return (
        FRONT_CENTER[0] + (mx - _BBOX_CX) * _S / 1000.0,
        FRONT_CENTER[1] + (my - _BBOX_CY) * _S / 1000.0,
    )


FRONT_KEEP = {
    "BarLength": (0.075, FRONT_CENTER[1]),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
TOP_KEEP: dict[str, tuple[float, float]] = {}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open amplitude-bar source", await adapter.open_model(str(SOURCE)))
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
            0: "Amplitude Bar Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "amplitude bar; chrome steel; coefficient bar",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 4))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 8))
    for view in (top, iso):
        set_hidden_lines_removed(adapter, view)

    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    curate_view_dimensions(adapter, top, keep=TOP_KEEP, view_label="top")

    # Square section on the top end view (4:1): width (X) horizontal, depth (Z)
    # vertical.
    half_w = BAR_WIDTH * _TOP_SCALE / 2000.0
    half_d = BAR_DEPTH * _TOP_SCALE / 2000.0
    add_edge_dimension(
        adapter,
        top,
        p0=(TOP_CENTER[0] - half_w, TOP_CENTER[1]),
        p1=(TOP_CENTER[0] + half_w, TOP_CENTER[1]),
        text_xy=(TOP_CENTER[0], TOP_CENTER[1] + 0.024),
        label="section width",
    )
    add_edge_dimension(
        adapter,
        top,
        p0=(TOP_CENTER[0], TOP_CENTER[1] - half_d),
        p1=(TOP_CENTER[0], TOP_CENTER[1] + half_d),
        text_xy=(TOP_CENTER[0] + 0.024, TOP_CENTER[1]),
        label="section depth",
    )

    # Datum A on a long side face (front view left edge), Ra on the sliding face,
    # and a flatness callout on the reference face (the form control the sliding
    # bar needs; the shared FCF helper carries no straightness symbol).
    left_edge = (FRONT_CENTER[0] - BAR_WIDTH * _S / 2000.0, FRONT_CENTER[1])
    add_datum_feature(
        adapter,
        front,
        edge_xy=left_edge,
        symbol_xy=(left_edge[0] - 0.016, FRONT_CENTER[1]),
        datum="A",
        label="bar reference face",
    )
    right_edge = (FRONT_CENTER[0] + BAR_WIDTH * _S / 2000.0, FRONT_CENTER[1] + 0.030)
    add_surface_finish(
        adapter,
        front,
        edge_xy=right_edge,
        symbol_xy=(right_edge[0] + 0.012, right_edge[1] + 0.006),
        roughness_ra="0.8",
        label="sliding face finish",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=left_edge,
        frame_xy=(0.045, 0.090),
        characteristic="flatness",
        tolerance="0.20",
        datums=(),
        label="bar flatness",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.150, 0.230)
    add_property_linked_note(adapter, "Isometric View Note", 0.300, 0.070)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Amplitude Bar Manufacturing Drawing",
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
