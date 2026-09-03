r"""Create the curated machinist drawing for the magnifying-wheel bar.

A 10 x 9 steel bar, 234 long, carrying the wheel axle and the pen-hanger strap.
Three bores run along the depth (front-back), so the FRONT view (looking down the
bore axis) shows them as circles: 2x #8 clamp-screw clearance holes flanking the
column and 1x #6 pen-hanger hole at the free end.  The bar length + section ride
the auto-imported profile marks; the depth is added across the right-view
section; each bore carries a native DRILL callout and a horizontal station from
the LEFT END (one origin), stacked below the bar with the shortest span nearest;
the bores' common transverse station (5.00 from the bottom edge to the
pen-hanger hole axis -- all three sit on the bar's centreline) is added at the
left end, nested inside the 10.00 section height.

The print is plain (cad/docs/drawing-simplicity-policy.md): a clamped support
bar is not on the GD&T allowlist, so it carries no datum, no frame, no
roughness symbol and no basic dimension.

Run with SolidWorks open::

    uv run python cad\scripts\draw_wheel_bar.py wheel-bar
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_native_hole_callout,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    find_edge_near,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_center,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from wheel_bar_spec import (
    BAR_DEPTH,
    BAR_LENGTH,
    BAR_SIDE,
    CLAMP_HOLE_DIA,
    CLAMP_HOLE_X,
    PEN_HANGER_HOLE_DIA,
    SCREW_HOLE_X,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["wheel_bar"]
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
_S = SHEET_SCALE[0] / 1000.0  # sheet meters per model mm
FRONT_CENTER = (0.155, 0.175)
RIGHT_CENTER = (0.320, 0.175)
ISO_CENTER = (0.320, 0.095)

_HALF_LEN = BAR_LENGTH * _S / 2.0
_HALF_SIDE = BAR_SIDE * _S / 2.0
LEFT_END = FRONT_CENTER[0] - _HALF_LEN
BAR_BOTTOM = FRONT_CENTER[1] - _HALF_SIDE


def _front_x(model_x: float) -> float:
    """Sheet x of a model x station in the origin-centred front view."""
    return FRONT_CENTER[0] + model_x * _S


# The overall length moves down one row to make room for the three station
# dimensions stacked between it and the bar.  The section height (10.00)
# stands left of the left end, OUTSIDE the transverse hole station, with its
# text lifted off the mid-height row: the pen-hanger hole's extended centre
# mark runs along that row through the end face (review 2026-09-02).
FRONT_KEEP = {
    "Length": (FRONT_CENTER[0], BAR_BOTTOM - 0.038),
    "Side": (LEFT_END - 0.023, FRONT_CENTER[1] + 0.011),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}

RIGHT_HALF_Z = BAR_DEPTH * _S / 2.0
RIGHT_HALF_Y = BAR_SIDE * _S / 2.0

# The left end face is the one origin; the pen-hanger hole sits 2.5 from it,
# so that pick lands well above the bar's mid-height, clear of the circle.
END_FACE_PICK = (LEFT_END, FRONT_CENTER[1] + 0.0035)
# The bottom edge, picked just inboard of the left end, is the origin of the
# transverse station (bottom edge -> pen-hanger hole axis); its text sits
# left of the end, nearest the view, inside the 10.00 lane.
BOTTOM_EDGE_PICK = (LEFT_END + 0.006, BAR_BOTTOM)
TRANSVERSE_STATION_TEXT_XY = (LEFT_END - 0.011, FRONT_CENTER[1] - 0.0025)

# Station rows below the bar, shortest span nearest (so no extension line
# crosses a shorter dimension's text): (model x, hole Ø, text sheet xy).  The
# 2.5 station is far narrower than its text, so the text sits right of the
# span rather than between the extension lines.
_ROW_Y = (BAR_BOTTOM - 0.008, BAR_BOTTOM - 0.018, BAR_BOTTOM - 0.028)


def _span_mid_x(model_x: float) -> float:
    return (LEFT_END + _front_x(model_x)) / 2.0


HOLE_STATIONS = (
    (SCREW_HOLE_X, PEN_HANGER_HOLE_DIA, (LEFT_END + 0.016, _ROW_Y[0])),
    (CLAMP_HOLE_X[0], CLAMP_HOLE_DIA, (_span_mid_x(CLAMP_HOLE_X[0]), _ROW_Y[1])),
    (CLAMP_HOLE_X[1], CLAMP_HOLE_DIA, (_span_mid_x(CLAMP_HOLE_X[1]), _ROW_Y[2])),
)

# Native DRILL callouts above the bar, one per Hole Wizard feature (the clamp
# pair reads 2X from its own instance count): (model x, hole Ø, callout xy).
HOLE_CALLOUTS = (
    ("pen-hanger hole", SCREW_HOLE_X, PEN_HANGER_HOLE_DIA, (0.062, 0.204)),
    ("clamp-screw holes", CLAMP_HOLE_X[0], CLAMP_HOLE_DIA, (0.236, 0.204)),
)


def _rim_pick(
    adapter: Any, view: Any, model_x: float, dia: float, label: str, *, side: int = 1
):
    """Refine the top (``side=1``) or bottom (``side=-1``) rim point of a
    Ø``dia`` bore at ``model_x`` to a real edge."""
    return find_edge_near(
        adapter,
        view,
        (_front_x(model_x), FRONT_CENTER[1] + side * dia * _S / 2.0),
        axis="y",
        label=label,
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open wheel-bar source", await adapter.open_model(str(SOURCE)))
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
            0: "Wheel Bar Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "wheel bar; steel support bar; clearance holes",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    set_hidden_lines_removed(adapter, iso)
    # Front carries the hole circles; the end view shows the transverse bores
    # dashed (blind review round 1: an empty end rectangle hid them).
    for view in (front, right):
        set_hidden_lines_visible(adapter, view)

    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right")
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to wheel-bar bores")

    # Bar depth (9): dimension the right view's flat front/back faces.
    add_edge_dimension(
        adapter,
        right,
        p0=(RIGHT_CENTER[0] - RIGHT_HALF_Z, RIGHT_CENTER[1]),
        p1=(RIGHT_CENTER[0] + RIGHT_HALF_Z, RIGHT_CENTER[1]),
        text_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] - RIGHT_HALF_Y - 0.014),
        label="bar-depth overall",
    )

    # Hole stations: left end face -> each bore axis, re-anchored to the arc
    # CENTRE so the value locates the axis, not the rim.
    for model_x, dia, text_xy in HOLE_STATIONS:
        label = f"hole station at {model_x:g}"
        station = add_edge_dimension(
            adapter,
            front,
            p0=END_FACE_PICK,
            p1=_rim_pick(adapter, front, model_x, dia, label),
            text_xy=text_xy,
            label=label,
            orientation="horizontal",
        )
        set_arc_endpoints_to_center(adapter, station, label=label)

    # Transverse station (5.00): bottom edge -> pen-hanger hole axis.  All
    # three bores share the bar's centreline, so the one station at the free
    # end locates every axis across the 10 width (review 2026-09-02: the
    # midline was drawn, never dimensioned).
    transverse = add_edge_dimension(
        adapter,
        front,
        p0=find_edge_near(
            adapter, front, BOTTOM_EDGE_PICK, axis="y", label="bar bottom edge"
        ),
        p1=_rim_pick(
            adapter, front, SCREW_HOLE_X, PEN_HANGER_HOLE_DIA,
            "transverse hole station", side=-1,
        ),
        text_xy=TRANSVERSE_STATION_TEXT_XY,
        label="transverse hole station",
        orientation="vertical",
    )
    set_arc_endpoints_to_center(adapter, transverse, label="transverse hole station")

    # Hole sizes: native Hole Wizard callouts, DRILL as the process prefix.
    for label, model_x, dia, callout_xy in HOLE_CALLOUTS:
        add_native_hole_callout(
            adapter,
            front,
            edge_xy=_rim_pick(adapter, front, model_x, dia, label),
            callout_xy=callout_xy,
            label=label,
            process="DRILL",
        )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.112)
    # x <= 0.235 keeps the ~55 mm label fully left of the title-block keep-out
    # (x >= 0.264) -- the first run landed it 25.6 x 4.5 mm into the block.
    add_property_linked_note(adapter, "Isometric View Note", 0.180, 0.070)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Wheel Bar Manufacturing Drawing",
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
