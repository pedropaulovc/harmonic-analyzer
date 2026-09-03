r"""Create the curated machinist drawing for the channel (top) lever.

The SLDPRT remains authoritative.  This recipe supplies only the channel-lever
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The lever is a long thin third-class lever (190.55 mm nose-to-tip, 9.5 mm tall,
3.0 mm thick).  The sheet runs at 1:1 with a small 1:4 isometric; the 3.0 x 9.5
section is dimensioned on a right end view.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): every
station is a coordinate from the fulcrum bore that the block tolerance holds
identically on all 20 levers, so the sheet carries no datums, no
feature-control frames, no roughness symbols and no basic dimensions.  The
one fitted feature -- the reamed fulcrum bore -- carries its +0.03/0 band on
the model dimension (build_channel_lever.py) and prints at three decimals.

Run with SolidWorks open::

    uv run python cad\scripts\draw_channel_lever.py channel-lever
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_native_hole_callout,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_max,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from channel_lever_spec import (
    BAR_PIN_X,
    BAR_TALL,
    LEVER_SPRING_X,
    LEVER_THICKNESS,
    NOSE_RADIUS,
    PIVOT_HOLE_DIA,
    TIP_END_X,
)
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
    view_name,
)


SPEC = DRAWINGS_BY_NAME["channel_lever"]
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

_NOSE_R = NOSE_RADIUS  # 4.75
_BBOX_CX = (-_NOSE_R + TIP_END_X) / 2.0  # front-view X centre
_SPRING_HOLE_DIA = 4.039  # #21 drill
_BAR_PIN_DIA = 1.994  # #47 drill

FRONT_CENTER = (0.150, 0.155)
RIGHT_CENTER = (0.295, 0.155)
ISO_CENTER = (0.360, 0.210)

# Longitudinal stack under the front view, one origin (the fulcrum bore),
# shortest lane nearest the outline and the true end-to-end overall OUTERMOST
# so it is the conspicuous one (policy rule 7).  Texts are staggered in X so
# five values never read as one column.
STACK_Y = {
    "bar_pin": 0.141,  # 127.00 fulcrum -> bar-pin c2c
    "bar_length": 0.133,  # 169.00 bar step (marked BarLength)
    "spring": 0.125,  # 177.80 fulcrum -> spring-eye c2c
    "tip_centre": 0.117,  # 182.80 fulcrum -> tip R3 centre (marked TipCentreX)
    "overall": 0.109,  # (190.55) nose extreme -> tip extreme, reference
}


def _sheet_xy(mx: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) of a model point in the bbox-centred front view (1:1)."""
    return (
        FRONT_CENTER[0] + (mx - _BBOX_CX) / 1000.0,
        FRONT_CENTER[1] + my / 1000.0,
    )


def _add_tip_arc_center_mark(adapter: Any, view: Any) -> None:
    """Center-mark the outer R3 arc so its TipCentreX coordinate has a centre."""
    draw = adapter.currentModel
    drawing_doc = _sw_type_info.early_bound_or_flag(
        draw, "IDrawingDoc", "ActivateView", "InsertCenterMark3"
    )
    if not drawing_doc.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate channel-lever front view")
    draw.ClearSelection2(True)
    tip_edge = _sheet_xy(TIP_END_X, 0.0)
    selected = draw.Extension.SelectByID2(
        "", "EDGE", tip_edge[0], tip_edge[1], 0.0, False, 0, null_callout(), 0
    )
    if not selected:
        raise RuntimeError("failed to select channel-lever tip R3 arc")
    center_mark = drawing_doc.InsertCenterMark3(2, False, False)
    draw.ClearSelection2(True)
    if center_mark is None:
        raise RuntimeError("failed to add channel-lever tip R3 center mark")


FRONT_KEEP = {
    "BarLength": (0.160, STACK_Y["bar_length"]),
    "TipCentreX": (0.190, STACK_Y["tip_centre"]),
    # Nose radius text left of the nose so its leader and the fulcrum-bore
    # leader approach the bore from opposite sides.
    "NoseRadius": (0.040, 0.169),
    # Tip radius text right of the tip, clear of the spring-eye callout lane.
    "TipRadius": (0.262, 0.170),
    "FulcrumDia": (0.080, 0.182),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
TOP_KEEP: dict[str, tuple[float, float]] = {}

# Process text beneath the fulcrum-bore diameter (Harvey #13: say ream).
DIMENSION_CALLOUTS = {"FulcrumDia": "REAM THRU"}
# The reamed bore is the ONE fitted feature: three decimals say "hold it"
# (its +0.03/0 band is a model tolerance; everything else stays two-place).
DIMENSION_PRECISION = {"FulcrumDia": 3}

# Hole-callout text centres: separated in X AND Y so the two callouts can
# never read as one underlined line with two leaders.
BAR_PIN_CALLOUT_XY = (0.150, 0.192)
SPRING_CALLOUT_XY = (0.232, 0.183)


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
            0: "Channel Lever Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "channel lever; cast iron; third-class lever",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 4))
    for view in (front, right):
        set_hidden_lines_visible(adapter, view)
    set_hidden_lines_removed(adapter, iso)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, front_annotations, DIMENSION_PRECISION)
    curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right")

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")
    _add_tip_arc_center_mark(adapter, front)

    # Fulcrum -> bar-pin (127) and fulcrum -> spring-eye (177.8) centre distances
    # (bore edge to bore edge; SolidWorks dimensions circle edges centre-to-centre).
    # One origin per view: both run from the fulcrum bore.
    fulcrum_rim = _sheet_xy(-PIVOT_HOLE_DIA / 2.0, 0.0)
    bar_pin_rim = _sheet_xy(BAR_PIN_X - _BAR_PIN_DIA / 2.0, 0.0)
    spring_rim = _sheet_xy(LEVER_SPRING_X - _SPRING_HOLE_DIA / 2.0, 0.0)
    add_edge_dimension(
        adapter,
        front,
        p0=fulcrum_rim,
        p1=bar_pin_rim,
        text_xy=(0.100, STACK_Y["bar_pin"]),
        label="fulcrum-to-bar-pin c2c",
    )
    add_edge_dimension(
        adapter,
        front,
        p0=fulcrum_rim,
        p1=spring_rim,
        text_xy=(0.125, STACK_Y["spring"]),
        label="fulcrum-to-spring c2c",
    )

    # True end-to-end overall (190.55): nose arc extreme to tip arc extreme.
    # An arc-to-arc pick defaults to centre-to-centre (which would repeat the
    # 182.80 tip-centre station), so both ends are flipped to the arcs'
    # furthest points, then the value is parenthesised: it is stock length,
    # not a station, and every station already carries its own tolerance.
    nose_extreme = _sheet_xy(-_NOSE_R, 0.0)
    tip_extreme = _sheet_xy(TIP_END_X, 0.0)
    overall = add_edge_dimension(
        adapter,
        front,
        p0=nose_extreme,
        p1=tip_extreme,
        text_xy=(0.150, STACK_Y["overall"]),
        label="overall length",
        orientation="horizontal",
    )
    set_arc_endpoints_to_max(adapter, overall, label="overall length")
    set_reference_dimension(
        adapter,
        _early_bound(overall, "IDisplayDimension").GetAnnotation(),
        label="overall length",
    )

    # Section thickness (3.0) + bar height (9.5) on the right end view.
    add_edge_dimension(
        adapter,
        right,
        p0=(RIGHT_CENTER[0] - LEVER_THICKNESS / 2000.0, RIGHT_CENTER[1]),
        p1=(RIGHT_CENTER[0] + LEVER_THICKNESS / 2000.0, RIGHT_CENTER[1]),
        text_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] + 0.028),
        label="lever thickness",
    )
    add_edge_dimension(
        adapter,
        right,
        p0=(RIGHT_CENTER[0], RIGHT_CENTER[1] - BAR_TALL / 2000.0),
        p1=(RIGHT_CENTER[0], RIGHT_CENTER[1] + BAR_TALL / 2000.0),
        text_xy=(RIGHT_CENTER[0] + 0.024, RIGHT_CENTER[1]),
        label="bar height",
    )

    # Hole callouts (bar-pin #47, spring-eye #21), each carrying its drill as
    # the prefix.  Pick a point ON each hole's rim, not its centre: SolidWorks
    # edge selection only catches the circular edge within tolerance of the
    # rim.  The bar-pin sits in the tall 9.5 mm bar, so its 12-o'clock rim is
    # clear.  The spring eye rides a narrow 6.0 mm tab (rim ~1 mm from the
    # tab's top edge), so a 12-o'clock pick grabs the tab edge and
    # AddHoleCallout2 fails -- pick it at 9 o'clock (toward the lever body, on
    # the Y=0 centreline), ~3 mm from the tab edges and clear of the tip.
    bar_pin_edge = _sheet_xy(BAR_PIN_X, _BAR_PIN_DIA / 2.0)
    spring_edge = _sheet_xy(LEVER_SPRING_X - _SPRING_HOLE_DIA / 2.0, 0.0)
    add_native_hole_callout(
        adapter,
        front,
        edge_xy=bar_pin_edge,
        callout_xy=BAR_PIN_CALLOUT_XY,
        label="bar-pin hole",
        process="#47 DRILL",
    )
    add_native_hole_callout(
        adapter,
        front,
        edge_xy=spring_edge,
        callout_xy=SPRING_CALLOUT_XY,
        label="spring-eye hole",
        process="#21 DRILL",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.075)
    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.175)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Channel Lever Manufacturing Drawing",
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
