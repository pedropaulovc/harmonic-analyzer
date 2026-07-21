r"""Create the curated machinist drawing for the connecting rod.

The SLDPRT remains authoritative.  This recipe supplies only the connecting-rod
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The rod is a tall thin lollipop (~170 mm ring-bottom to head-crown), so the
sheet runs at 1:1 with a 1:2 isometric.

Run with SolidWorks open::

    uv run python cad\scripts\draw_connecting_rod.py connecting-rod
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
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_basic_dimension,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from connecting_rod_spec import (
    CENTER_DISTANCE,
    HEAD_TOP_Y,
    PIN_HOLE_DIA,
    RING_BORE_DIA,
    RING_BOTTOM_Y,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["connecting_rod"]
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

SHEET_SCALE = (1.0, 1.0)  # 1:1

# Front-view model bbox: X symmetric about 0, Y from the ring bottom up to the
# head crown.
_BBOX_CY = (RING_BOTTOM_Y + HEAD_TOP_Y) / 2.0

FRONT_CENTER = (0.180, 0.135)
LEFT_CENTER = (0.080, 0.180)  # stepped-thickness profile, above the notes block
ISO_CENTER = (0.360, 0.140)


def _sheet_xy(mx: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) of a model point in the bbox-centred front view (1:1)."""
    return (
        FRONT_CENTER[0] + mx / 1000.0,
        FRONT_CENTER[1] + (my - _BBOX_CY) / 1000.0,
    )


FRONT_KEEP = {
    "RingOuterDia": (0.185, 0.070),
    "StrapBoreDia": (0.190, 0.052),
    "ShankWidthDim": (0.180, 0.150),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
TOP_KEEP: dict[str, tuple[float, float]] = {}

BORE_FINISH_EDGE = _sheet_xy(RING_BORE_DIA / 2.0, 0.0)
BORE_FINISH_SYMBOL = (BORE_FINISH_EDGE[0] + 0.025, BORE_FINISH_EDGE[1] + 0.015)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open connecting-rod source", await adapter.open_model(str(SOURCE)))
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
            0: "Connecting Rod Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "connecting rod; cast iron; cam strap",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    # The 1:1 left view (third angle: placed LEFT of the front) shows the
    # stepped thickness (ring 3.0 / shank+head 2.5) the notes describe -- a
    # single orthographic view left the step geometry to prose (machinist
    # round 2).  The right-hand column belongs to the title block, so the
    # section lives on the left.
    left = place_view(adapter, str(SOURCE), "*Left", *LEFT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    for view in (left, iso):
        set_hidden_lines_removed(adapter, view)
    set_hidden_lines_visible(adapter, front)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    # The strap bore is a machined fit over the 30.60 cam: the general ±0.51
    # block would even allow interference, so the bore dimension carries its
    # own +0.10/0 callout (the notes explain the running clearance).
    set_dimension_callouts(
        adapter, front_annotations, {"StrapBoreDia": "BORE +0.10/0"}
    )

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    # Centre distance: ring bore edge to the rocker-pin bore edge (SolidWorks
    # dimensions circle edges centre-to-centre); box it BASIC.  Pick each bore's
    # LEFT rim -- the pin bore is tiny and sits inside the head crown, so a TOP
    # pick snapped to the crown arc (read 145.07); the left rim is unambiguously
    # on the pin circle, clear of the wider crown.
    ring_rim = _sheet_xy(-RING_BORE_DIA / 2.0, 0.0)
    pin_rim = _sheet_xy(-PIN_HOLE_DIA / 2.0, CENTER_DISTANCE)
    centre_distance = add_edge_dimension(
        adapter,
        front,
        p0=ring_rim,
        p1=pin_rim,
        text_xy=(0.125, FRONT_CENTER[1]),
        label="rod centre distance",
    )
    set_basic_dimension(adapter, centre_distance, label="rod centre distance")

    # Rocker pin hole native callout (the #47 wizard hole in the head).
    add_native_hole_callout(
        adapter,
        front,
        edge_xy=pin_rim,
        callout_xy=(0.235, 0.208),
        label="rocker pin hole",
    )

    # Datum A on the strap bore axis (picked at 9 o'clock so the tag stands off
    # to the LEFT), Ra on the bore at 6 o'clock, and a position FCF tying the
    # rocker pin hole to A.
    bore_left = _sheet_xy(-RING_BORE_DIA / 2.0, 0.0)
    add_datum_feature(
        adapter,
        front,
        edge_xy=bore_left,
        symbol_xy=(bore_left[0] - 0.020, bore_left[1]),
        datum="A",
        label="strap bore axis",
    )
    # Datum B: the shank's left flank.  A alone leaves rotation about the bore
    # axis unconstrained, so the pin-hole position (and the 147.67 direction)
    # could not be inspected; B clocks the rod and the 4.00 BASIC below ties
    # the pin to the shank centreline.
    shank_flank = _sheet_xy(-4.0, 100.0)
    add_datum_feature(
        adapter,
        front,
        edge_xy=shank_flank,
        symbol_xy=(shank_flank[0] - 0.016, shank_flank[1] - 0.010),
        datum="B",
        label="shank left flank",
    )
    pin_offset = add_edge_dimension(
        adapter,
        front,
        p0=shank_flank,
        p1=pin_rim,
        text_xy=(0.152, 0.224),
        label="pin C/L from shank flank",
        orientation="horizontal",
    )
    set_basic_dimension(adapter, pin_offset, label="pin C/L from shank flank")
    add_surface_finish(
        adapter,
        front,
        edge_xy=BORE_FINISH_EDGE,
        symbol_xy=BORE_FINISH_SYMBOL,
        roughness_ra="1.6",
        label="strap bore finish",
    )
    # The hole callout owns the 9-o'clock rim and routes down-right to its
    # text; anchoring the FCF at the same point crossed the two leaders (layout
    # audit).  Attach the frame at 3 o'clock and keep it in a higher lane so
    # its whole leader stays clear of the callout path.
    pin_fcf_rim = _sheet_xy(PIN_HOLE_DIA / 2.0, CENTER_DISTANCE)
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=pin_fcf_rim,
        frame_xy=(0.222, 0.222),
        characteristic="position",
        tolerance="0.20",
        datums=("A", "B"),
        diameter=True,
        label="rocker pin hole position",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.090)
    add_property_linked_note(adapter, "Isometric View Note", 0.325, 0.205)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Connecting Rod Manufacturing Drawing",
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
