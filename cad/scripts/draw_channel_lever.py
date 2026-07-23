r"""Create the curated machinist drawing for the channel (top) lever.

The SLDPRT remains authoritative.  This recipe supplies only the channel-lever
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The lever is a long thin third-class lever (~186 mm nose-to-tip, 9.5 mm tall,
3.0 mm thick).  The sheet runs at 1:1 with a small 1:4 isometric; the 3.0 x 9.5
section is dimensioned on a right end view.

Run with SolidWorks open::

    uv run python cad\scripts\draw_channel_lever.py channel-lever
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_edge_dimension,
    add_feature_control_frame,
    add_native_hole_callout,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_view_properties,
    set_basic_dimension,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from channel_lever_spec import (
    BAR_PIN_X,
    BAR_TALL,
    LEVER_SPRING_X,
    LEVER_THICKNESS,
    PIVOT_HOLE_DIA,
    TIP_END_X,
)
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
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

_NOSE_R = BAR_TALL / 2.0  # 4.75
_BBOX_CX = (-_NOSE_R + TIP_END_X) / 2.0  # front-view X centre
_SPRING_HOLE_DIA = 4.039  # #21 drill
_BAR_PIN_DIA = 1.994  # #47 drill

FRONT_CENTER = (0.150, 0.155)
RIGHT_CENTER = (0.295, 0.155)
ISO_CENTER = (0.360, 0.210)


def _sheet_xy(mx: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) of a model point in the bbox-centred front view (1:1)."""
    return (
        FRONT_CENTER[0] + (mx - _BBOX_CX) / 1000.0,
        FRONT_CENTER[1] + my / 1000.0,
    )


def _force_dimension_black(dimension: Any, *, label: str) -> None:
    """Make an added basic dimension print at full black instead of driven gray."""
    display = _sw_type_info.early_bound_or_flag(
        dimension, "IDisplayDimension", "GetAnnotation"
    )
    annotation = display.GetAnnotation()
    if annotation is None:
        raise RuntimeError(f"{label} has no annotation")
    annotation = _sw_type_info.early_bound_or_flag(
        annotation, "IAnnotation", "Color", "LayerOverride"
    )
    annotation.Color = 0  # COLORREF black; overrides the drawing layer color.
    if int(annotation.Color) != 0:
        raise RuntimeError(f"{label} did not retain black annotation color")
    if not int(annotation.LayerOverride) & 0x1:
        raise RuntimeError(f"{label} did not retain its color override")


def _add_tip_arc_center_mark(adapter: Any, view: Any) -> None:
    """Center-mark the outer R3 arc so its boxed centre coordinate is explicit."""
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
    "BarLength": (FRONT_CENTER[0] - 0.010, 0.138),
    "TipCentreX": (FRONT_CENTER[0] + 0.070, 0.125),
    "NoseRadius": (0.070, 0.172),
    "TipRadius": (0.240, 0.172),
    "FulcrumDia": (0.075, 0.180),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
TOP_KEEP: dict[str, tuple[float, float]] = {}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    drawing_model, _sheet = new_project_drawing(
        adapter,
        category=SPEC.category,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
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
    read_required_view_properties(
        adapter,
        front,
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
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 4))
    for view in (right, iso):
        set_hidden_lines_removed(adapter, view)
    set_hidden_lines_visible(adapter, front)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    profile_dimensions = {"BarLength", "TipCentreX", "NoseRadius", "TipRadius"}
    for annotation in front_annotations:
        name = dimension_name(adapter, annotation)
        if name not in profile_dimensions:
            continue
        display = annotation.GetSpecificAnnotation()
        if display is None:
            raise RuntimeError(f"profile dimension {name!r} has no display annotation")
        set_basic_dimension(adapter, display, label=f"profile {name}")
    curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right")

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")
    _add_tip_arc_center_mark(adapter, front)

    # Fulcrum -> bar-pin (127) and fulcrum -> spring-eye (177.8) centre distances
    # (bore edge to bore edge; SolidWorks dimensions circle edges centre-to-centre).
    fulcrum_rim = _sheet_xy(-PIVOT_HOLE_DIA / 2.0, 0.0)
    bar_pin_rim = _sheet_xy(BAR_PIN_X - _BAR_PIN_DIA / 2.0, 0.0)
    spring_rim = _sheet_xy(LEVER_SPRING_X - _SPRING_HOLE_DIA / 2.0, 0.0)
    bar_pin_c2c = add_edge_dimension(
        adapter,
        front,
        p0=fulcrum_rim,
        p1=bar_pin_rim,
        text_xy=(FRONT_CENTER[0] - 0.020, 0.128),
        label="fulcrum-to-bar-pin c2c",
    )
    set_basic_dimension(adapter, bar_pin_c2c, label="fulcrum-to-bar-pin c2c")
    _force_dimension_black(bar_pin_c2c, label="fulcrum-to-bar-pin c2c")
    spring_c2c = add_edge_dimension(
        adapter,
        front,
        p0=fulcrum_rim,
        p1=spring_rim,
        text_xy=(FRONT_CENTER[0], 0.118),
        label="fulcrum-to-spring c2c",
    )
    set_basic_dimension(adapter, spring_c2c, label="fulcrum-to-spring c2c")
    _force_dimension_black(spring_c2c, label="fulcrum-to-spring c2c")

    # Section thickness (3.0) + bar height (9.5) on the right end view.
    add_edge_dimension(
        adapter,
        right,
        p0=(RIGHT_CENTER[0] - LEVER_THICKNESS / 2000.0, RIGHT_CENTER[1]),
        p1=(RIGHT_CENTER[0] + LEVER_THICKNESS / 2000.0, RIGHT_CENTER[1]),
        text_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] + 0.028),
        label="lever thickness",
    )
    bar_height = add_edge_dimension(
        adapter,
        right,
        p0=(RIGHT_CENTER[0], RIGHT_CENTER[1] - BAR_TALL / 2000.0),
        p1=(RIGHT_CENTER[0], RIGHT_CENTER[1] + BAR_TALL / 2000.0),
        text_xy=(RIGHT_CENTER[0] + 0.024, RIGHT_CENTER[1]),
        label="bar height",
    )
    set_basic_dimension(adapter, bar_height, label="bar height from datum C")

    # Hole callouts (bar-pin #47, spring-eye #21).  Pick a point ON each hole's
    # rim, not its centre: SolidWorks edge selection only catches the circular
    # edge within tolerance of the rim.  The bar-pin sits in the tall 9.5 mm bar,
    # so its 12-o'clock rim is clear.  The spring eye rides a narrow 6.0 mm tab
    # (rim ~1 mm from the tab's top edge), so a 12-o'clock pick grabs the tab
    # edge and AddHoleCallout2 fails -- pick it at 9 o'clock (toward the lever
    # body, on the Y=0 centreline), ~3 mm from the tab edges and clear of the tip.
    bar_pin_edge = _sheet_xy(BAR_PIN_X, _BAR_PIN_DIA / 2.0)
    spring_edge = _sheet_xy(LEVER_SPRING_X - _SPRING_HOLE_DIA / 2.0, 0.0)
    spring_fcf_edge = _sheet_xy(LEVER_SPRING_X + _SPRING_HOLE_DIA / 2.0, 0.0)
    add_native_hole_callout(
        adapter,
        front,
        edge_xy=bar_pin_edge,
        callout_xy=(bar_pin_edge[0] - 0.010, 0.185),
        label="bar-pin hole",
    )
    add_native_hole_callout(
        adapter,
        front,
        edge_xy=spring_edge,
        callout_xy=(spring_edge[0] + 0.005, 0.185),
        label="spring-eye hole",
    )

    # Complete datum reference frame: A is a broad machined face (primary), B
    # is the functional fulcrum-bore axis (secondary), and C is the top narrow
    # face (tertiary clocking).  The two BASIC hole locations reference A|B|C.
    broad_face = (
        RIGHT_CENTER[0] - LEVER_THICKNESS / 2000.0,
        RIGHT_CENTER[1],
    )
    add_datum_feature(
        adapter,
        right,
        edge_xy=broad_face,
        symbol_xy=(broad_face[0] - 0.018, broad_face[1] - 0.018),
        datum="A",
        label="broad machined face",
    )
    fulcrum_left = _sheet_xy(-PIVOT_HOLE_DIA / 2.0, 0.0)
    add_datum_feature(
        adapter,
        front,
        edge_xy=fulcrum_left,
        symbol_xy=(fulcrum_left[0] - 0.018, fulcrum_left[1]),
        datum="B",
        # SolidWorks normalizes this legal bore-axis tag by 0.0020 mm when
        # committed.  This allowance checks annotation readback only; it does
        # not alter the part's manufacturing tolerances.
        label="fulcrum bore axis",
        position_tolerance_m=0.001,
    )
    top_face = (
        RIGHT_CENTER[0],
        RIGHT_CENTER[1] + BAR_TALL / 2000.0,
    )
    add_datum_feature(
        adapter,
        right,
        edge_xy=top_face,
        symbol_xy=(top_face[0] + 0.018, top_face[1] + 0.010),
        datum="C",
        label="top clocking face",
    )
    outer_profile = _sheet_xy(80.0, BAR_TALL / 2.0)
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=outer_profile,
        frame_xy=(0.105, 0.210),
        characteristic="profile_surface",
        tolerance="0.50",
        datums=("A", "B", "C"),
        all_around=True,
        label="outer perimeter profile",
    )
    fulcrum_bottom = _sheet_xy(0.0, -PIVOT_HOLE_DIA / 2.0)
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=fulcrum_bottom,
        frame_xy=(0.065, 0.200),
        characteristic="perpendicularity",
        tolerance="0.05",
        datums=("A",),
        diameter=True,
        label="fulcrum bore perpendicularity",
    )
    opposite_broad_face = (
        RIGHT_CENTER[0] + LEVER_THICKNESS / 2000.0,
        RIGHT_CENTER[1],
    )
    add_feature_control_frame(
        adapter,
        right,
        edge_xy=opposite_broad_face,
        frame_xy=(0.225, 0.205),
        characteristic="parallelism",
        tolerance="0.05",
        datums=("A",),
        label="opposite broad face parallelism",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=bar_pin_edge,
        # Keep this frame below the hole-callout elbow (y ~= 0.182) and in a
        # separate horizontal lane from the spring-eye frame.  Routing it from
        # the old above-left position crossed the bar-pin callout leader.
        frame_xy=(bar_pin_edge[0] - 0.045, 0.174),
        characteristic="position",
        tolerance="0.20",
        datums=("A", "B", "C"),
        diameter=True,
        label="bar-pin hole position",
    )
    add_feature_control_frame(
        adapter,
        front,
        # The hole callout owns the 9-o'clock rim and routes up-left.  Attach
        # the position frame at 3 o'clock and keep its whole leader to the
        # right of the callout path.
        edge_xy=spring_fcf_edge,
        frame_xy=(spring_fcf_edge[0] + 0.020, 0.174),
        characteristic="position",
        tolerance="0.20",
        datums=("A", "B", "C"),
        diameter=True,
        label="spring-eye hole position",
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
