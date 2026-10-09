r"""Create the curated machinist drawing for the summing lever.

The SLDPRT remains authoritative.  This recipe supplies only the summing-lever
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

A large green cast-iron first-class lever hung on hex knife-edge trunnions (no
bore): a coefficients plate on the +X arm carrying the 20 channel-spring anchor
taps, a solid pivot cylinder (152.4 long, along Z), and a summation arm
reaching to the tapped counter-spring anchor boss on the -X arm.  Both spring
anchors are purchased eyebolts that thread straight into those taps, so the
print controls thread identity and position, never a seat bore.  The print
shows a 1:2 front profile (pivot Ø), a 1:2 top plan (plate width/length +
anchor boss), and a 1:4 isometric.  The sheet runs at 1:2.

Run with SolidWorks open::

    uv run python cad\scripts\draw_sm_summing_lever.py sm-summing-lever
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from sm_summing_lever_spec import GEOMETRIC_TOLERANCES_MM

import _telemetry
from _hole_spec import blind_cut_dia_mm
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    ViewEdge,
    _early_bound,
    ViewEdges,
    add_datum_feature,
    add_edge_dimension,
    add_feature_control_frame,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    assert_dimension_measures,
    curate_view_dimensions,
    create_blank_drawing_sheets,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    scan_view_edges,
    set_basic_dimension,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from sm_summing_lever_spec import (
    ANCHOR_H,
    ANCHOR_R,
    CHANNEL_PITCH,
    COUNTER_HOLE_SPEC,
    HEX_DEPTH,
    HEX_H,
    HOLE_COUNT,
    HOLE_END_OFFSET_LAST,
    HOLE_SPEC,
    HOLE_X,
    HOLE_Z_FIRST,
    HOLE_Z_LAST,
    PLATE_L,
    PLATE_T,
    PLATE_W,
    SURFACE_FINISHES,
    TIP_X,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    place_view,
)

from magnifying_bracket_joint_layout import (
    LEVER_HOLE_POINTS, TAP_DRILL_DIA, THREAD_DEPTH, DRILL_DEPTH,
    THREAD_DEPTH_BAND, DRILL_DEPTH_BAND,
)

SPEC = DRAWINGS_BY_NAME["sm_summing_lever"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
HOLE_DIA = blind_cut_dia_mm(HOLE_SPEC)
# Tap-drill diameter of the boss's counter-anchor tap; the rim points below
# pick its circular edge, and the native callout prints the thread itself.
COUNTER_R = blind_cut_dia_mm(COUNTER_HOLE_SPEC) / 2.0

SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (1.0, 2.0)  # 1:2
_S = SHEET_SCALE[0] / SHEET_SCALE[1]  # sheet-mm per model-mm (0.5)

# Front (down -Z) and top (down -Y) share the same X extent: anchor eye
# (TIP_X - ANCHOR_R) on the left to the plate right edge (PLATE_W).
_BBOX_CX = (TIP_X - ANCHOR_R + PLATE_W) / 2.0

FRONT_CENTER = (0.225, 0.235)
TOP_CENTER = (0.225, 0.130)  # aligned plan below the front profile
ISO_CENTER = (0.350, 0.225)
BACK_CENTER = (0.225, 0.190)
SHEET_NAMES = ("Lever Geometry", "Bracket Receiver")


def _back_xy(mx: float, my: float) -> tuple[float, float]:
    """Back view reverses X and looks at the blind taps' -Z entry face."""
    return (
        BACK_CENTER[0] - (mx - _BBOX_CX) * _S / 1000.0,
        BACK_CENTER[1] + my * _S / 1000.0,
    )

def _mounting_rims(back: Any) -> list[Any]:
    """Back looks from -Z directly onto the blind taps' entry circles."""
    edges = scan_view_edges(back, label="bracket receiver face")
    return [
        edges.circle_at(
            point, TAP_DRILL_DIA / 2.0, axis=(0.0, 0.0, 1.0),
            label=f"bracket receiver {index}",
        )
        for index, point in enumerate(LEVER_HOLE_POINTS)
    ]



def _front_xy(mx: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) of a model (X, Y) point in the front profile view (1:2)."""
    return (
        FRONT_CENTER[0] + (mx - _BBOX_CX) * _S / 1000.0,
        FRONT_CENTER[1] + my * _S / 1000.0,
    )


def _top_xy(mx: float, mz: float) -> tuple[float, float]:
    """Sheet (x, y) of a model (X, Z) point in the top plan view (1:2)."""
    return (
        TOP_CENTER[0] + (mx - _BBOX_CX) * _S / 1000.0,
        TOP_CENTER[1] + mz * _S / 1000.0,
    )


def _end_face_edge(edges: ViewEdges, *, x_mm: float) -> ViewEdge:
    """The one visible line of the +Z end face crossing model ``x_mm``.

    In the plan the +Z end (bottom of the view) shows a single line at
    z = PLATE_L/2: the edge rib's outer top edge, which covers the plate's own
    end edge out to the rib's vertical end face at RIB_PLATE_REACH (35.75,
    0.44 proud of the plate there); the plate's end edge shows only beyond it.
    The end rib's inboard flange edge sits 5.08 mm up the sheet and the rib's
    underside edge (y < 0) is hidden, so exactly one visible +y line at that z
    spans the requested x; anything else is a changed model and fails loud.
    """
    z_mm = PLATE_L / 2.0
    matches = [
        item
        for item in edges.lines
        if all(abs(point[2] - z_mm) < 1e-6 and point[1] > -1e-6 for point in item.line)
        and min(point[0] for point in item.line) - 1e-6 <= x_mm
        and x_mm <= max(point[0] for point in item.line) + 1e-6
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"summing lever +Z end face: expected one visible line at z={z_mm:g} "
            f"spanning x={x_mm:g} in the {edges.label!r} scan, found "
            f"{[item.line for item in matches]}"
        )
    return matches[0]


FRONT_KEEP = {
    "CylDia": (0.145, 0.260),
    "PlateThickness": (0.320, 0.240),
}
TOP_KEEP = {
    # Below the plate end, its witness lines 14 mm long: at 0.160 they ran
    # from the end up past every hole, boxing the column's right side (the
    # 20X callout's leader had to cross one). The line prints 2.8 mm under
    # the keep, at 0.0785: 2.9 mm under datum B's box, 2.3 mm over the 39.85
    # text (whose line, with 76.20's, dropped to 0.0695 for that), and the
    # text sits right of the span, clear of B.
    "PlateWidth": (0.266, 0.0813),
    "PlateLength": (0.395, TOP_CENTER[1]),
    "RibDepth": (0.325, 0.160),  # -Z receiver rib: Top prints model +Z down
    "AnchorOuterDia": (0.145, 0.175),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open summing-lever source", await adapter.open_model(str(SOURCE)))
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
            "Bracket Receiver Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
            "Bracket Receiver Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Summing Lever Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "summing lever; gray iron; knife-edge first-class lever",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="summing lever package")
    drawing = _early_bound(drawing_model, "IDrawingDoc")
    if not drawing.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("failed to activate lever geometry sheet")

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 2))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 2))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 4))
    for view in (top, iso):
        set_hidden_lines_removed(adapter, view)

    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    curate_view_dimensions(adapter, top, keep=TOP_KEEP, view_label="top")

    # Counter-anchor tap native callout (thread + depth) in the top plan.  Pick
    # a point on the hole rim (not its centre) so SolidWorks catches the
    # circular edge.
    anchor_tap_edge = _top_xy(TIP_X, COUNTER_R)
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=anchor_tap_edge,
        callout_xy=(0.145, 0.155),
        label="anchor tap",
    )

    # Datum A is the actual knife-edge pivot ridge, not the merged cylinder
    # silhouette hidden by the ribs in the front view.  A SolidWorks Top view
    # reverses model Z on the sheet: the positive sheet offset selects the -Z
    # ridge, while the negative offset selects the part-owned +Z finish face.
    # Keep datum and finish on opposite ridges so their leaders stay distinct.
    # One sweep of the plan's visible edges serves every named pick below.
    # The ridge is the hexagon's top vertex line, y = HEX_H/2 (vertex-up
    # sketch centred on the pivot axis, build_summing_lever._hex_collar).
    top_edges = scan_view_edges(top, label="summing lever top plan")
    knife_edge_datum = _top_xy(0.0, PLATE_L / 2.0 + HEX_DEPTH / 2.0)
    datum_ridge = top_edges.exact_line_through(
        (0.0, HEX_H / 2.0, -(PLATE_L / 2.0 + HEX_DEPTH / 2.0)),
        label="-Z knife-edge ridge",
    )
    add_datum_feature(
        adapter,
        top,
        edge_xy=knife_edge_datum,
        expected_entity=datum_ridge.edge,
        # 24 mm out: at 20 the tag's box straddled the plate's right edge
        # (0.2575) and the edge ran through the 'A' (text-on-line on every
        # #1105 run); now the box starts 1.8 mm past it.
        symbol_xy=(knife_edge_datum[0] + 0.024, knife_edge_datum[1] - 0.012),
        datum="A",
        label="knife-edge pivot axis",
    )
    knife_edge = _top_xy(0.0, -(PLATE_L / 2.0 + HEX_DEPTH / 2.0))
    # The ridge lands in a pocket closed by the 76.20 extension line (left),
    # the 76.20/39.85 dimension line (below) and the plate (above); the default
    # 43 mm body cannot fit, so the 2.5 mm body sits inside it (layout audit:
    # the old leader crossed 76.20's extension line and datum B's leader).
    add_surface_finish(
        adapter,
        top,
        edge_xy=knife_edge,
        symbol_xy=(0.208, 0.084),
        control=surface_finish_by_key(SURFACE_FINISHES, "knife_edge_ridge"),
        label="knife-edge ridge finish",
        char_height=0.0025,
    )
    # Land the position frame on the tap rim's 3-o'clock point, opposite the
    # hole callout, which SolidWorks lands up-left of the 12-o'clock pick. From
    # the 9-o'clock point, with the frame up-left, the two leaders met 0.6 mm
    # apart and crossed (leader-crosses-leader). The frame now stands up-right
    # (x ~0.201..0.231, y ~0.176..0.183, 3 mm under the 20X frame's "20X") and
    # its leader drops almost vertically at x ~0.198, right of RD1's leader.
    # At +6 mm its right end sat on the pivot stud's top-left corner (x
    # ~0.2333); +3 mm leaves about 2 mm of air.
    anchor_tap_fcf_edge = _top_xy(TIP_X + COUNTER_R, 0.0)
    add_feature_control_frame(
        adapter,
        top,
        edge_xy=anchor_tap_fcf_edge,
        frame_xy=(
            anchor_tap_fcf_edge[0] + 0.003,
            anchor_tap_fcf_edge[1] + 0.053,
        ),
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["summation anchor position"],
        datums=("A",),
        diameter=True,
        label="summation anchor position",
    )
    # BASIC X coordinate backing the anchor position frame: knife-edge pivot
    # axis (the +Z trunnion ridge, the finish's) to the anchor tap. Both
    # endpoints are named: the ridge line through a mid-stub point, the tap's
    # rim on the boss top (centre (TIP_X, ANCHOR_H/2, 0), the hole wizard's
    # placement in build_summing_lever._counter_anchor_tap).
    ridge_dim_edge = _top_xy(0.0, -(PLATE_L / 2.0 + 0.3 * HEX_DEPTH))
    anchor_tap_bottom = _top_xy(TIP_X, -COUNTER_R)
    dim_ridge = top_edges.exact_line_through(
        (0.0, HEX_H / 2.0, PLATE_L / 2.0 + 0.3 * HEX_DEPTH),
        label="+Z knife-edge ridge",
    )
    anchor_rim = top_edges.circle_at(
        (TIP_X, ANCHOR_H / 2.0, 0.0),
        COUNTER_R,
        axis=(0.0, 1.0, 0.0),
        label="counter-anchor tap rim",
    )
    anchor_location = add_edge_dimension(
        adapter,
        top,
        p0=ridge_dim_edge,
        p1=anchor_tap_bottom,
        text_xy=(0.216, 0.0723),
        label="anchor tap X location",
        orientation="horizontal",
        entities=(dim_ridge.edge, anchor_rim.edge),
    )
    assert_dimension_measures(
        adapter,
        anchor_location,
        expected_mm=-TIP_X,
        label="anchor tap X location",
        entities=(dim_ridge.edge, anchor_rim.edge),
    )
    set_basic_dimension(adapter, anchor_location, label="anchor tap X location")

    # Anchor-tap pattern control: datum B on the plate end the seed hole is
    # located from, BASIC row-X / start-Z / pitch coordinates off A|B, a
    # native thread callout, and a 20X position frame -- the inspectable
    # pattern definition (the notes no longer carry these numbers as prose).
    # The plan prints model +Z DOWN the sheet, so the end at the bottom of the
    # view is the +Z end: the seed hole (HOLE_Z_LAST, HOLE_END_OFFSET_LAST off
    # that end) is the bottom hole of the column.
    # Hang B's tag straight down right of the +Z trunnion stub, between it and
    # the 39.85 extension line: left of the stub it sat in the finish leader's
    # only path (layout audit); the 20X callout now hangs on the middle hole,
    # well away from this tag.
    # Every datum and dimension here names its entities: a coordinate
    # hit-test on the plate corner resolved to the rib flange 5.08 mm inboard
    # (datum B on the flange, start Z reading 3.35 for 8.43 -- #1105), and a
    # value check alone cannot tell the seed rim from the nineteen others at
    # the same X or any equal-pitch pair. The picks below are the rims'
    # model positions (the hole wizard's seed at HOLE_Z_LAST, the pattern
    # marching -Z by CHANNEL_PITCH; build_summing_lever).
    plate_end_edge = _top_xy(10.0, -PLATE_L / 2.0)
    end_edge = _end_face_edge(top_edges, x_mm=10.0)
    add_datum_feature(
        adapter,
        top,
        edge_entity=end_edge.edge,
        symbol_xy=(plate_end_edge[0] + 0.0062, plate_end_edge[1] - 0.0035),
        datum="B",
        label="plate +Z end face",
    )
    seed_rim = top_edges.circle_at(
        (HOLE_X, PLATE_T / 2.0, HOLE_Z_LAST),
        HOLE_DIA / 2.0,
        axis=(0.0, 1.0, 0.0),
        label="spring-hole seed rim",
    )
    second_rim = top_edges.circle_at(
        (HOLE_X, PLATE_T / 2.0, HOLE_Z_LAST - CHANNEL_PITCH),
        HOLE_DIA / 2.0,
        axis=(0.0, 1.0, 0.0),
        label="spring-hole second rim",
    )
    seed_rim_right = _top_xy(HOLE_X + HOLE_DIA / 2.0, -HOLE_Z_LAST)
    # The start-Z and pitch texts ride with the hole column (tuned at the 0.8
    # arm offset, seed centre at sheet y 0.0961), so a station move keeps them.
    seed_y = seed_rim_right[1]
    row_x = add_edge_dimension(
        adapter,
        top,
        p0=ridge_dim_edge,
        p1=seed_rim_right,
        text_xy=(0.248, 0.0723),
        label="spring-hole row X",
        orientation="horizontal",
        entities=(dim_ridge.edge, seed_rim.edge),
    )
    assert_dimension_measures(
        adapter,
        row_x,
        expected_mm=HOLE_X,
        label="spring-hole row X",
        entities=(dim_ridge.edge, seed_rim.edge),
    )
    set_basic_dimension(adapter, row_x, label="spring-hole row X")
    seed_rim_top = _top_xy(HOLE_X, -HOLE_Z_LAST + HOLE_DIA / 2.0)
    # The start Z (12.76) spans 6.4 mm of sheet (0.0919..0.0983); text between
    # the arrows would sit on its own line (3.35 there stood on 7.06's extension
    # line and 152.40's), so it hangs above the span, right of the 7.06 text
    # (0.275..0.284, up to seed_y + 0.0074) and left of the 152.40 line (0.396).
    start_z = add_edge_dimension(
        adapter,
        top,
        p0=plate_end_edge,
        p1=seed_rim_top,
        text_xy=(0.292, seed_y + 0.0099),
        label="spring-hole start Z",
        orientation="vertical",
        entities=(end_edge.edge, seed_rim.edge),
    )
    assert_dimension_measures(
        adapter,
        start_z,
        expected_mm=HOLE_END_OFFSET_LAST,
        label="spring-hole start Z",
        entities=(end_edge.edge, seed_rim.edge),
    )
    set_basic_dimension(adapter, start_z, label="spring-hole start Z")
    second_rim_bottom = _top_xy(
        HOLE_X, -HOLE_Z_LAST + CHANNEL_PITCH - HOLE_DIA / 2.0
    )
    pitch = add_edge_dimension(
        adapter,
        top,
        p0=seed_rim_top,
        p1=second_rim_bottom,
        text_xy=(0.275, seed_y + 0.0054),
        label="spring-hole pitch",
        orientation="vertical",
        entities=(seed_rim.edge, second_rim.edge),
    )
    assert_dimension_measures(
        adapter,
        pitch,
        expected_mm=CHANNEL_PITCH,
        label="spring-hole pitch",
        entities=(seed_rim.edge, second_rim.edge),
    )
    set_basic_dimension(adapter, pitch, label="spring-hole pitch")
    # The 20X callout hangs on the middle hole, text in the open field right
    # of the column: with 44.45 below the plate end, 0.100..0.185 there
    # holds nothing. Every callout on the end hole had to leave it downward
    # and so crossed the plate-end extension lines of 152.40 and the start-Z
    # dimension -- steepening the leader only traded that for text-on-line
    # and arrow-near-text against the 39.85 arrowhead and the start-Z
    # overshoot (runs 20260928T130915425Z, ...131249806Z, ...131507773Z).
    mid_hole_z = HOLE_Z_LAST - (HOLE_COUNT // 2) * CHANNEL_PITCH
    mid_rim = top_edges.circle_at(
        (HOLE_X, PLATE_T / 2.0, mid_hole_z),
        HOLE_DIA / 2.0,
        axis=(0.0, 1.0, 0.0),
        label="spring-hole middle rim",
    )
    add_native_hole_callout(
        adapter,
        top,
        edge=mid_rim.edge,
        callout_xy=(0.292, _top_xy(HOLE_X, -mid_hole_z)[1] + 0.0015),
        label="spring-hole middle",
    )
    # The Top view reverses model Z, so -HOLE_Z_FIRST prints the seed hole at
    # the TOP of the column. The frame sits above the +Z trunnion stub with
    # its right stub ending over the rim, so the leader drops vertically
    # through the 1.5 mm gap between the flange end and datum A's tag and runs
    # only ~5 mm over the plate (the diagonal from 0.175 crossed the stub and
    # flange: leader-over-part, 24 mm).
    seed_rim_left = _top_xy(HOLE_X - HOLE_DIA / 2.0, -HOLE_Z_FIRST)
    add_feature_control_frame(
        adapter,
        top,
        edge_xy=seed_rim_left,
        frame_xy=(0.2133, 0.199),
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["spring-hole pattern position"],
        datums=("A", "B"),
        diameter=True,
        quantity="20X",
        label="spring-hole pattern position",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.120)
    add_property_linked_note(adapter, "Isometric View Note", 0.300, 0.185)

    if not drawing.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("failed to activate bracket receiver sheet")
    back = place_view(adapter, str(SOURCE), "*Back", *BACK_CENTER, scale=(1, 2))
    receiver_iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 4),
    )
    for view in (back, receiver_iso):
        set_hidden_lines_removed(adapter, view)
    curate_view_dimensions(adapter, back, keep={}, view_label="bracket receiver")
    mounting_rims = _mounting_rims(back)
    mounting_callout = add_native_hole_callout(
        adapter, back, edge=mounting_rims[0].edge,
        callout_xy=(0.292, 0.155), label="two blind bracket mounting taps",
        process="BOTTOMING TAP - FULL THREAD DEPTH / TAP DRILL DEPTH",
    )
    from win32com.client.dynamic import Dispatch as dynamic_dispatch
    required_depths = {
        "hw-threaddepth": THREAD_DEPTH,
        "hw-tapdrldepth": DRILL_DEPTH,
    }
    for raw in mounting_callout.GetHoleCalloutVariables() or ():
        # Concrete callout interfaces alias the generic metadata DISPIDs.
        variable = dynamic_dispatch(raw._oleobj_)
        variable_name = str(variable.VariableName)
        if variable_name not in required_depths:
            continue
        length = _early_bound(raw, "ICalloutLengthVariable")
        expected_depth = required_depths.pop(variable_name)
        if abs(float(length.Length) * 1000.0 - expected_depth) > 1e-5:
            raise RuntimeError(f"bracket mounting callout has wrong {variable_name}")
        band = THREAD_DEPTH_BAND if variable_name == "hw-threaddepth" else DRILL_DEPTH_BAND
        observed = (
            int(variable.ToleranceType),
            float(variable.ToleranceMin) * 1000.0,
            float(variable.ToleranceMax) * 1000.0,
        )
        _telemetry.info(
            f"bracket mounting callout {variable_name} imported tolerance "
            f"(type, lower mm, upper mm) = {observed!r}"
        )
        # A hole callout variable carries its OWN tolerance (SW 2016+:
        # ICalloutVariable.ToleranceType; the model IDimensionTolerance does
        # not override it). Farm 2026-10-09: the cosmetic-thread depth band
        # did not reach hw-threaddepth, so author the same source band here.
        variable.ToleranceType = 4  # swTolType_e.swTolSYMMETRIC
        variable.ToleranceMin = -band / 1000.0
        variable.ToleranceMax = band / 1000.0
        length.TolerancePrecision = 2
        if (
            int(variable.ToleranceType) != 4
            or abs(float(variable.ToleranceMin) * 1000.0 + band) > 1e-5
            or abs(float(variable.ToleranceMax) * 1000.0 - band) > 1e-5
            or int(length.TolerancePrecision) != 2
        ):
            raise RuntimeError(
                f"bracket mounting callout tolerance for {variable_name} did not "
                f"persist: wanted symmetric band {band} mm at 2 places"
            )
    if required_depths:
        raise RuntimeError(f"bracket tap callout omits native depths: {required_depths}")
    from _drawing_hidden_sketches import curate_view_dimensions as curate_hidden_dimensions
    curate_hidden_dimensions(
        adapter, back,
        keep={
            "ReceiverX0": (0.225, 0.220),
            "ReceiverX1": (0.225, 0.229),
            "ReceiverY0": (0.182, 0.185),
        },
        view_label="bracket receiver coordinates",
        dimensions_by_feature={
            "ReceiverCoordinates": ("ReceiverX0", "ReceiverX1", "ReceiverY0"),
        },
    )
    add_property_linked_note(adapter, "Bracket Receiver Note", 0.020, 0.120)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Summing Lever Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        redundant_note_substrings=("Tapped Hole",),
        # main's 3, plus the bracket taps' per-hole cosmetic threads (2) in the
        # receiver sheet's two views: 7 observed on the farm 2026-10-09.
        expected_redundant_notes=7,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
