r"""Create the curated machinist drawing for the channel (top) lever.

The SLDPRT remains authoritative.  Every size, location and band prints from
its native model dimension (``ch_channel_lever_notes.DRAWING_DIMENSIONS``, at
the places the part authors); this recipe supplies only the views, the
placement of those dimensions, the function each tight band serves, the hole
callouts, the bore's roughness and one reference overall length.
Sheet/template and export behaviour lives in ``_drawing_common``.

The lever is a long thin third-class lever (7.34 in over the hub, .43 in
tall, .118 in thick); the sheet prints decimal inch (the part's
``drawing_unit: in``).  The sheet runs at 1:1: the front view carries the
profile, bore, hub, both arms from the fulcrum bore and the overall length;
the top view the plate thickness and the hub length; a 1:2 isometric.

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_channel_lever.py ch-channel-lever
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)

import _config
from _check import check
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
# The plate offset is owned by a reference sketch the part saves hidden.
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_arc_endpoints_to_max,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_finish import add_surface_finish
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_leaders import set_near_side_diameter
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _drawing_view_display import set_hidden_lines_removed
from _hole_spec import blind_cut_dia_mm, drill_process
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from ch_channel_lever_notes import DRAWING_DIMENSIONS, DRAWING_PRECISION
from ch_channel_lever_spec import (
    BAR_PIN_HOLE_SPEC,
    BAR_PIN_X,
    HUB_DIA,
    LEVER_SPRING_X,
    PIVOT_HOLE_BAND,
    PIVOT_HOLE_DIA,
    SPRING_EYE_HOLE_SPEC,
    SURFACE_FINISHES,
    TIP_END_X,
)
from ch_fulcrum_shaft_spec import SHAFT_DIA, SHAFT_DIA_BAND

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["ch_channel_lever"]
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
ISO_SCALE = (1, 2)

_HUB_R = HUB_DIA / 2.0
_BBOX_CX = (-_HUB_R + TIP_END_X) / 2.0  # both 1:1 views centre on the hub..tip span
_SPRING_HOLE_DIA = blind_cut_dia_mm(SPRING_EYE_HOLE_SPEC)
_BAR_PIN_DIA = blind_cut_dia_mm(BAR_PIN_HOLE_SPEC)

FRONT_CENTER = (0.150, 0.155)
TOP_CENTER = (0.150, 0.220)  # above the profile: plate thickness, hub length
ISO_CENTER = (0.345, 0.215)
ISO_NOTE_XY = (0.315, 0.185)  # left end: centres the label under the iso


def _name_hole_mate(display: Any, *, label: str) -> None:
    """Add the hole's mate under its native callout.

    swDimensionTextCalloutBelowDefinition (8) pairs with the writable
    swDimensionTextCalloutBelow (4); the prefix, size and depth definitions
    stay untouched, so the Hole Wizard variables stay associative
    (draw_ch_rocker_arm_tl_profile_fixture._locate_pivot_tap_depths)."""
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    below = definitions[8].rstrip()
    mate = HOLE_MATES[label]
    updated = f"{below}\n{mate}" if below else mate
    display.SetText(4, updated)
    if str(display.GetText(8) or "").replace("\r", "") != updated or any(
        str(display.GetText(part) or "") != definitions[part] for part in (5, 6, 7)
    ):
        raise RuntimeError(
            f"{label}: hole callout mate or native definitions did not persist: "
            f"{[str(display.GetText(part) or '') for part in (5, 6, 7, 8)]!r}"
        )


def _sheet_x(mx: float) -> float:
    """Sheet x of a model x in either 1:1 view (both are bbox-centred)."""
    return FRONT_CENTER[0] + (mx - _BBOX_CX) / 1000.0


# --- Mates and functions named on the bands' own callouts (rules 4 and 7). ---
SHAFT_NUMBER = _config.parts("ch-fulcrum-shaft")["number"]
BAR_NUMBER = _config.parts("ch-amplitude-bar")["number"]
PIN_NUMBER = _config.parts("ch-bar-pivot-pin")["number"]
SPRING_NUMBER = _config.parts("ch-vn-channel-spring-installed")["number"]
STATIONS = _config.machine("channels", "count")
_CLEARANCE_LEAST = (PIVOT_HOLE_DIA + PIVOT_HOLE_BAND[1]) - (SHAFT_DIA + SHAFT_DIA_BAND[0])
_CLEARANCE_MOST = (PIVOT_HOLE_DIA + PIVOT_HOLE_BAND[0]) - (SHAFT_DIA + SHAFT_DIA_BAND[1])


def _inch(value_mm: float) -> str:
    """Four-place inch text, no leading zero (.0060)."""
    return f"{value_mm / 25.4:.4f}".removeprefix("0")


# The bar-to-hub roots are inside corners: the title block's INSIDE CORNERS
# row controls them, so no callout repeats it (rule 2; review r1-r3).
FRONT_CALLOUTS = {
    "FulcrumDia": (
        f"REAM THRU; RUNS ON\nSHAFT {SHAFT_NUMBER},"
        f" {_inch(_CLEARANCE_LEAST)}-{_inch(_CLEARANCE_MOST)}\nDIAMETRAL CLEARANCE"
    ),
    "BarHeight": "FULL R AT TIP",
    "BarPinCx": "SETS LEVER RATIO",
    "SpringCx": "SETS LEVER RATIO",
}
# What engages each drilled hole rides its own hole callout (machinist r5:
# on the arm's location it did not say the hole is a running bore).
HOLE_MATES = {
    "bar-pin hole": f"RUNS ON PIN\n{PIN_NUMBER}",
    "spring-eye hole": f"HOOKS SPRING\n{SPRING_NUMBER}",
}
# Each drilled hole's native size prints .XXX.
HOLE_PRECISION = {"hw-diam": 3}
TOP_CALLOUTS = {
    "LeverThick": f"SLIDING FIT IN NOTCH\nOF {BAR_NUMBER}",
    "PlateOffset": f"LOCATES {BAR_NUMBER} NOTCH;\nSETS GAP TO NEXT BAR",
    "HubLength": f"{STATIONS} HUBS STACK;\nSETS STATION PITCH",
}

FRONT_KEEP = {
    # Left of the hub, just above its axis: the near-side leader stops on the
    # left rim, clear of the overall length's extension line below the hub
    # and of the REAM leader, which lands from the upper right.
    "HubDia": (0.033, 0.165),
    "FulcrumDia": (0.050, 0.190),
    # Above the bar, so neither dimension line runs into the text.
    "BarHeight": (0.262, 0.171),
    "BarPinCx": (_sheet_x(BAR_PIN_X / 2.0), 0.126),
    "SpringCx": (_sheet_x(LEVER_SPRING_X / 2.0 + 25.0), 0.104),
}
TOP_KEEP = {
    # Above the plate: its arrows come in from outside the 3.00 span.
    "LeverThick": (0.264, TOP_CENTER[1] + 0.032),
    # Both above the hub, their lines just right of it (left of the hub there
    # is no room inside the border).  Each text runs right from its own line
    # (r2 render), so the outer (right) line carries the lower text and
    # neither line runs through the other's text.
    "HubLength": (0.075, TOP_CENTER[1] + 0.032),
    "PlateOffset": (0.095, TOP_CENTER[1] + 0.014),
}
OVERALL_TEXT_XY = (FRONT_CENTER[0], 0.082)
BAR_PIN_CALLOUT_XY = (0.170, 0.188)
SPRING_CALLOUT_XY = (0.240, 0.188)
BORE_FINISH_SYMBOL = (0.080, 0.140)
FINISH_CHAR_HEIGHT = 0.0025


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open channel-lever source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("ch-channel-lever"),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Channel Lever Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "channel lever; cast iron; third-class lever",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    # The integral Ø.47 x .278 fulcrum hub hides the whole plate section
    # in an end view, so the plate thickness and the hub length read here.
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, top, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    top_annotations = curate_view_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # The bands import with their named model dimensions, at the part's
    # places; the drawing owns only the callout text beneath them.
    assert_imported_precision(
        adapter,
        front_annotations,
        {
            **DRAWING_PRECISION["LeverOutline"],
            **DRAWING_PRECISION["HubProfile"],
            **DRAWING_PRECISION["FulcrumProfile"],
            **DRAWING_PRECISION["BarPinHole"],
            **DRAWING_PRECISION["SpringHole"],
        },
    )
    assert_imported_precision(
        adapter,
        top_annotations,
        {
            **DRAWING_PRECISION["LeverBody"],
            **DRAWING_PRECISION["Hub"],
            **DRAWING_PRECISION["PlateOffsetReference"],
        },
    )
    # Native, the Ø.47 line runs rim to rim through the hub centre and
    # crosses the REAM leader there (review r3): one arrow on the near rim.
    hub_dia = [a for a in front_annotations if dimension_name(adapter, a) == "HubDia"]
    if len(hub_dia) != 1:
        raise RuntimeError(f"expected one HubDia dimension, found {len(hub_dia)}")
    set_near_side_diameter(hub_dia[0], "hub diameter")
    rebuild_drawing(adapter, label="hub diameter near-side leader")
    set_dimension_callouts(adapter, front_annotations, FRONT_CALLOUTS)
    set_dimension_callouts(adapter, top_annotations, TOP_CALLOUTS)

    # Overall length over the hub and the full-round tip, for the stock cut:
    # a reference (the hub, the spring-hole location and the bar's full round
    # set it).  Both ends are arcs in the front view, each picked on its
    # extreme and re-anchored to it (a horizontal arc pick resolves to the
    # centre by default and would read the 175.05 spring arm).
    hub_end, tip_end = (
        model_point_in_view(adapter, front, (x / 1000.0, 0.0, 0.0), label=label)
        for x, label in ((-_HUB_R, "hub extreme"), (TIP_END_X, "tip extreme"))
    )
    overall = add_edge_dimension(
        adapter,
        front,
        p0=hub_end,
        p1=tip_end,
        text_xy=OVERALL_TEXT_XY,
        label="overall length",
        orientation="horizontal",
    )
    set_arc_endpoints_to_max(adapter, overall, label="overall length")
    # Value-only: both picks are arcs the recipe locates by coordinate, and
    # the far-extreme sum is the one value either centre-anchored mistake
    # (175.05, 181.05, 180.55) cannot produce.
    assert_dimension_measures(
        adapter, overall, expected_mm=_HUB_R + TIP_END_X, label="overall length"
    )
    overall = _sw_type_info.early_bound_or_flag(
        overall, "IDisplayDimension", "GetAnnotation"
    )
    set_reference_dimension(adapter, overall.GetAnnotation(), label="overall length")

    # Hole callouts (bar-pin #47, spring-eye #21) say DRILL ahead of the native
    # size.  Pick a point ON each hole's rim, not its centre: edge selection
    # only catches the circular edge within tolerance of the rim.  The spring
    # eye is picked at 9 o'clock, clear of the concentric full-round tip.
    bar_pin_edge = model_point_in_view(
        adapter, front, (BAR_PIN_X / 1000.0, _BAR_PIN_DIA / 2000.0, 0.0),
        label="bar-pin hole rim",
    )
    spring_edge = model_point_in_view(
        adapter,
        front,
        ((LEVER_SPRING_X - _SPRING_HOLE_DIA / 2.0) / 1000.0, 0.0, 0.0),
        label="spring-eye hole rim",
    )
    bar_pin_callout = add_native_hole_callout(
        adapter,
        front,
        edge_xy=bar_pin_edge,
        callout_xy=BAR_PIN_CALLOUT_XY,
        label="bar-pin hole",
        process=drill_process(BAR_PIN_HOLE_SPEC) + "\n",
    )
    _name_hole_mate(bar_pin_callout, label="bar-pin hole")
    set_hole_callout_precision(bar_pin_callout, HOLE_PRECISION, label="bar-pin hole")
    spring_callout = add_native_hole_callout(
        adapter,
        front,
        edge_xy=spring_edge,
        callout_xy=SPRING_CALLOUT_XY,
        label="spring-eye hole",
        process=drill_process(SPRING_EYE_HOLE_SPEC) + "\n",
    )
    _name_hole_mate(spring_callout, label="spring-eye hole")
    set_hole_callout_precision(spring_callout, HOLE_PRECISION, label="spring-eye hole")
    rebuild_drawing(adapter, label="hole callout mates")

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    # The reamed fulcrum bore is the one running surface (rule 6): Ra on its
    # rim at 300 degrees, the symbol below-right of the hub: between the REAM
    # leader (about 240 degrees through the bore) and the hub's (about 345),
    # right of the arms' extension line.
    bore_rim = model_point_in_view(
        adapter,
        front,
        (PIVOT_HOLE_DIA / 2000.0 * 0.5, -PIVOT_HOLE_DIA / 2000.0 * 0.8660, 0.0),
        label="fulcrum bore rim",
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=bore_rim,
        symbol_xy=BORE_FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "fulcrum_bore"),
        label="fulcrum bore finish",
        char_height=FINISH_CHAR_HEIGHT,
    )

    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Channel Lever Manufacturing Drawing",
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
