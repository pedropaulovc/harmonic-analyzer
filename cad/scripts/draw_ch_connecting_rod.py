r"""Create the curated machinist drawing for the connecting rod.

The SLDPRT remains authoritative.  This recipe supplies only the connecting-rod
views, dimension layout, callout text, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The rod is a tall thin lollipop (~190 mm ring-bottom to fork crown), so the
sheet runs at 1:1 with a 1:2 isometric.

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_connecting_rod.py ch-connecting-rod
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from ch_connecting_rod_spec import GEOMETRIC_TOLERANCES_MM

import _telemetry
from _check import check
from _paths import CAD_ROOT
from _session import run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_edge_dimension,
    add_feature_control_frame,
    add_property_linked_note,
    add_surface_finish,
    assert_imported_precision,
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
from _surface_finish import surface_finish_by_key
from ch_connecting_rod_notes import DRAWING_DIMENSIONS, DRAWING_PRECISION
from ch_connecting_rod_spec import (
    CENTER_DISTANCE,
    FORK_BASE_Y,
    FORK_CROTCH_Y,
    FORK_THICKNESS,
    FORK_TOP_Y,
    PIN_HOLE_DIA,
    RING_BORE_DIA,
    RING_BOTTOM_Y,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["ch_connecting_rod"]
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
_PIN_HOLE_DIA = PIN_HOLE_DIA

SHEET_SCALE = (1.0, 1.0)  # 1:1

# Front-view model bbox: X symmetric about 0, Y from the ring bottom up to the
# fork crown.  The left view shares it (Z symmetric about the mid-plane).
_BBOX_CY = (RING_BOTTOM_Y + FORK_TOP_Y) / 2.0

FRONT_CENTER = (0.180, 0.135)
# Third-angle left view, aligned with the front view so the fork's thickness
# and slot dimensions stand in the clear band above its crown.
LEFT_CENTER = (0.080, FRONT_CENTER[1])
ISO_CENTER = (0.385, 0.140)
# The notes column sits between the front view's pin annotations and the
# isometric view (the left view now runs down the old bottom-left column).
NOTES_XY = (0.258, 0.185)


def _sheet_xy(mx: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) of a model point in the bbox-centred front view (1:1)."""
    return (
        FRONT_CENTER[0] + mx / 1000.0,
        FRONT_CENTER[1] + (my - _BBOX_CY) / 1000.0,
    )


def _left_xy(offset: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) ``offset`` mm right of the left view's mid-plane at model
    height ``my`` (1:1)."""
    return (
        LEFT_CENTER[0] + offset / 1000.0,
        LEFT_CENTER[1] + (my - _BBOX_CY) / 1000.0,
    )


FRONT_KEEP = {
    "RingOuterDia": (0.185, 0.070),
    "StrapBoreDia": (0.190, 0.052),
    "ShankWidthDim": (0.180, 0.150),
    "ForkWidthDim": _sheet_xy(0.0, FORK_TOP_Y + 8.0),
    # The reamed pin hole's Ø and band leave the hole for the lane above the
    # crown, right of the fork; the position FCF attaches at the 3-o'clock rim
    # with a level leader below that lane, so the two leaders cannot cross.
    "PinHoleDia": (0.240, 0.243),
}
# Descriptive text beneath each native value/band: the strap bore; the fork's
# crown, a full round on the pin tangent to its sides; the reamed press hole
# (policy rule 7: the decimal Ø and the process).
FRONT_CALLOUTS = {
    "StrapBoreDia": "BORE",
    "ForkWidthDim": "FULL R",
    "PinHoleDia": "THRU - REAM",
}
# Side-view ink, read off the farm render of 1b1f2f7fd (run
# 20261009T190048955Z; mm at 1:1, from each dimension's keep point).  A
# horizontal dimension's text centres on its keep x.  The thickness's one
# line ("6.075 ±0.05", 23.9 wide) centres on its keep y and stands on its
# dimension line FORK_THICK_LINE_DROP_MM under it.  The slot's stacked band
# ("2.625 +0.127/0.000", 26.9 wide) rises over the value: its frame tops out
# SLOT_WIDTH_TEXT_RISE_MM over the keep y, its line SLOT_WIDTH_LINE_DROP_MM
# under it.  Smart arrows stand outside these short spans, their tails
# DIM_ARROW_REACH_MM past the extension line (the 14.75 and 18.00 top tails
# rise that far over the tine tops); an arrowhead is ARROW_HALF_WIDTH_MM
# either side of its line.
FORK_THICK_TEXT_HALF_WIDTH_MM = 12.0
FORK_THICK_LINE_DROP_MM = 2.8
SLOT_WIDTH_TEXT_HALF_WIDTH_MM = 13.5
SLOT_WIDTH_TEXT_RISE_MM = 4.4
SLOT_WIDTH_LINE_DROP_MM = 4.5
VERTICAL_TEXT_HALF_WIDTH_MM = 5.4  # "14.75", "18.00"
DIM_ARROW_REACH_MM = 6.4
ARROW_HALF_WIDTH_MM = 0.3
# Air between side-view text and any other dimension's ink.
SIDE_TEXT_CLEARANCE_MM = 2.5
# The slot's 2.625 span is narrower than its value: centred over the slot, the
# thickness's dimension line cut the top of its band, the thickness's right
# extension line and the 14.75's top arrow tail ran through its "0.000"
# (farm render of 1b1f2f7fd).  So the slot's text stands LEFT of the fork,
# clear of the thickness's left extension line, on its own dimension line
# run out just above the tine tops; the thickness stands centred over the
# fork, its line and arrows clear above the slot's band.  The slot depth and
# the boss length run from the tine tops down the right-hand side, their
# values a clear gap apart.
SLOT_WIDTH_TEXT_DX_MM = -(
    FORK_THICKNESS / 2.0 + SIDE_TEXT_CLEARANCE_MM + SLOT_WIDTH_TEXT_HALF_WIDTH_MM
)
SLOT_WIDTH_RISE_MM = 6.0
FORK_THICK_RISE_MM = 16.5
SLOT_DEPTH_DX_MM = 12.0
FORK_BOSS_LENGTH_DX_MM = 28.0
LEFT_KEEP = {
    "SlotWidth": _left_xy(SLOT_WIDTH_TEXT_DX_MM, FORK_TOP_Y + SLOT_WIDTH_RISE_MM),
    "ForkThick": _left_xy(0.0, FORK_TOP_Y + FORK_THICK_RISE_MM),
    "SlotDepth": _left_xy(SLOT_DEPTH_DX_MM, (FORK_TOP_Y + FORK_CROTCH_Y) / 2.0),
    "ForkBossLength": _left_xy(
        FORK_BOSS_LENGTH_DX_MM, (FORK_TOP_Y + FORK_BASE_Y) / 2.0
    ),
}
TOP_KEEP: dict[str, tuple[float, float]] = {}

BORE_FINISH_EDGE = _sheet_xy(RING_BORE_DIA / 2.0, 0.0)
BORE_FINISH_SYMBOL = (BORE_FINISH_EDGE[0] + 0.025, BORE_FINISH_EDGE[1] + 0.015)
# Datum B on the shank's left flank. The tag's edge attachment re-solves
# square to the flank, so its leader runs level at the tag's height; the tag
# stands 4.5 mm above the ShankWidthDim keep, whose 3.5 mm text reads
# 148.2..151.7 at y 150, leaving the leader 2.8 mm over the text (it rode 1.3
# mm lower, through the text, once the fork's crown raised the bbox centre).
DATUM_B_EDGE = _sheet_xy(-4.0, 100.0)
DATUM_B_SYMBOL = (DATUM_B_EDGE[0] - 0.016, FRONT_KEEP["ShankWidthDim"][1] + 0.0045)


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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Connecting Rod Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "connecting rod; 1018 steel; fork and cam strap",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    # The 1:1 left view (third angle: placed LEFT of the front) shows the
    # stepped thickness -- one 2.200 plate for ring and shank (note 2), and the
    # 6.075 fork split by its slot into two tines -- and carries the fork's
    # thickness, slot width, slot depth and boss length.  The right-hand
    # column belongs to the title block,
    # so the side view lives on the left.
    left = place_view(adapter, str(SOURCE), "*Left", *LEFT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    for view in (left, iso):
        set_hidden_lines_removed(adapter, view)
    set_hidden_lines_visible(adapter, front)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    curate_view_dimensions(
        adapter,
        left,
        keep=LEFT_KEEP,
        view_label="left",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # The strap-bore and reamed pin-hole bands import with their named model
    # dimensions, at the part's places; the drawing owns only the callout
    # text beneath them.
    assert_imported_precision(
        adapter, front_annotations, DRAWING_PRECISION["PinHoleProfile"]
    )
    set_dimension_callouts(adapter, front_annotations, FRONT_CALLOUTS)

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    # Centre distance: ring bore edge to the rocker-pin bore edge (SolidWorks
    # dimensions circle edges centre-to-centre); box it BASIC.  Pick each bore's
    # LEFT rim -- the pin bore is tiny and sits inside the fork crown, so a TOP
    # pick snapped to the crown arc (read 145.07); the left rim is on the pin
    # circle, clear of the wider crown.
    ring_rim = _sheet_xy(-RING_BORE_DIA / 2.0, 0.0)
    pin_rim = _sheet_xy(-_PIN_HOLE_DIA / 2.0, CENTER_DISTANCE)
    centre_distance = add_edge_dimension(
        adapter,
        front,
        p0=ring_rim,
        p1=pin_rim,
        text_xy=(0.125, FRONT_CENTER[1]),
        label="rod centre distance",
    )
    set_basic_dimension(adapter, centre_distance, label="rod centre distance")

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
    add_datum_feature(
        adapter,
        front,
        edge_xy=DATUM_B_EDGE,
        symbol_xy=DATUM_B_SYMBOL,
        datum="B",
        label="shank left flank",
    )
    pin_offset = add_edge_dimension(
        adapter,
        front,
        p0=DATUM_B_EDGE,
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
        control=surface_finish_by_key(SURFACE_FINISHES, "strap_bore"),
        label="strap bore finish",
    )
    # The position FCF attaches at the reamed pin hole's 3-o'clock rim with a
    # level leader, below the Ø callout's lane.
    pin_fcf_rim = _sheet_xy(_PIN_HOLE_DIA / 2.0, CENTER_DISTANCE)
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=pin_fcf_rim,
        frame_xy=(0.222, 0.222),
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["rocker pin hole position"],
        datums=("A", "B"),
        diameter=True,
        label="rocker pin hole position",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", 0.350, 0.205)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Connecting Rod Manufacturing Drawing",
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
