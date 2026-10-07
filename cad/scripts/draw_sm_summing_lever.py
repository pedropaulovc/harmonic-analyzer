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
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    ViewEdge,
    ViewEdges,
    _surface_finish_entity_faces,
    _surface_finish_face_signatures,
    add_datum_feature,
    add_edge_dimension,
    add_feature_control_frame,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    assert_dimension_measures,
    assert_native_hole_callout_attachment,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    property_link,
    read_required_properties,
    scan_view_edges,
    set_basic_dimension,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from _part_pmi import _face_matches
from sm_summing_lever_notes import DRAWING_NOTES, PICKUP_PROCESS, PICKUP_PROCESS_PROPERTY
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
    MACHINED_PICKUP_FACES,
    PLATE_L,
    PLATE_T,
    PLATE_W,
    SURFACE_FINISHES,
    TIP_X,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    place_view,
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


def _end_face_edge(edges: ViewEdges, *, x_mm: float, z_mm: float) -> ViewEdge:
    """The one visible line of the actual plate/rib end crossing ``x_mm``.

    At either z = +/-PLATE_L/2 the edge rib's outer top edge covers the plate's
    own end edge until the rib tapers below the plate near x = PLATE_W. The
    inboard flange is 5.08 mm nearer the centre and the underside (y < 0) is
    hidden, so exactly one visible +y line at the requested end spans x;
    anything else is a changed model and fails loud.
    """
    matches = [
        item
        for item in edges.lines
        if all(abs(point[2] - z_mm) < 1e-6 and point[1] > -1e-6 for point in item.line)
        and min(point[0] for point in item.line) - 1e-6 <= x_mm
        and x_mm <= max(point[0] for point in item.line) + 1e-6
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"summing lever plate/rib end face: expected one visible line at z={z_mm:g} "
            f"spanning x={x_mm:g} in the {edges.label!r} scan, found "
            f"{[item.line for item in matches]}"
        )
    return matches[0]


FRONT_KEEP = {
    "CylDia": (0.145, 0.260),
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
    "AnchorOuterDia": (0.145, 0.175),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}


@_telemetry.traced("drawing.summing_pickup_process")
def _assert_pickup_process_note(note: Any) -> None:
    """Read back the actual model-owned process, not a typed drawing substitute."""
    native_note = _early_bound(note, "INote")
    linked = str(native_note.PropertyLinkedText or "")
    resolved = str(native_note.GetText() or "").replace("\r", "")
    if linked != property_link("Manufacturing Notes"):
        raise RuntimeError(f"pickup process note lost its native model link: {linked!r}")
    if resolved != DRAWING_NOTES:
        raise RuntimeError(
            f"pickup process note does not resolve this part's requirement: {resolved!r}"
        )
    _telemetry.event(
        "drawing.summing_pickup_process",
        property_name="Manufacturing Notes",
        property_link=linked,
        resolved_text=resolved,
    )


@_telemetry.traced("drawing.machined_pickup_faces")
def _assert_machined_pickup_faces(edges: dict[str, Any]) -> None:
    """Witness the real source faces named by the model's machining instruction.

    New pickup machining is nonnumeric: the linked Manufacturing Notes own
    the process and the part build qualifies its physical faces, not new
    drawing symbols or a borrowed Ra grade. Linked text alone is not this witness.
    """
    if edges.keys() != MACHINED_PICKUP_FACES.keys():
        raise RuntimeError("summing lever machining witness omitted a required pickup")
    for key, edge in edges.items():
        faces = _surface_finish_entity_faces(edge, entity_type="EDGE", label=key)
        signatures = _surface_finish_face_signatures(faces)
        matches = [
            item for item in signatures
            if _face_matches(item["geometry"], MACHINED_PICKUP_FACES[key])
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"{key}: machining pickup edge must touch exactly one specified "
                f"physical face, found {len(matches)}"
            )
        witness = matches[0]
        _telemetry.info(
            f"MACHINED_PICKUP_FACE {key}: normal={witness['normal']!r}; "
            f"box_m={witness['box']!r}"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open summing-lever source", await adapter.open_model(str(SOURCE)))
    properties = read_required_properties(
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
            PICKUP_PROCESS_PROPERTY,
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
            PICKUP_PROCESS_PROPERTY,
        ),
    )
    if properties.get(PICKUP_PROCESS_PROPERTY, "").replace("\r", "") != PICKUP_PROCESS:
        raise RuntimeError(
            f"source pickup-process property {PICKUP_PROCESS_PROPERTY!r} "
            "does not match this part's requirement"
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

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 2))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 2))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 4))
    for view in (top, iso):
        set_hidden_lines_removed(adapter, view)

    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    curate_view_dimensions(adapter, top, keep=TOP_KEEP, view_label="top")

    # The Hole Wizard owns this rim: centre on the boss's +Y face, axis +Y,
    # radius from COUNTER_HOLE_SPEC's tap drill. Reuse the same visible-edge
    # scan and rim as the checked X-location dimension below; do not ask the
    # seat's graphics aperture to guess which edge a sheet point means.
    top_edges = scan_view_edges(top, label="summing lever top plan")
    anchor_rim = top_edges.circle_at(
        (TIP_X, ANCHOR_H / 2.0, 0.0),
        COUNTER_R,
        axis=(0.0, 1.0, 0.0),
        label="counter-anchor tap rim",
        selection="unique",
        adapter=adapter,
    )
    anchor_callout = add_native_hole_callout(
        adapter,
        top,
        edge=anchor_rim.edge,
        callout_xy=(0.145, 0.155),
        label="anchor tap",
    )

    # Datum A is the actual knife-edge pivot ridge, not the merged cylinder
    # silhouette hidden by the ribs in the front view.  A SolidWorks Top view
    # reverses model Z on the sheet: the positive sheet offset selects the -Z
    # ridge, while the negative offset selects the part-owned +Z finish face.
    # Keep datum and finish on opposite ridges so their leaders stay distinct.
    # The same visible-edge scan serves every named pick below.
    # The ridge is the hexagon's top vertex line, y = HEX_H/2 (vertex-up
    # sketch centred on the pivot axis, build_summing_lever._hex_collar).
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
    end_edge = _end_face_edge(top_edges, x_mm=10.0, z_mm=PLATE_L / 2.0)
    add_datum_feature(
        adapter,
        top,
        edge_entity=end_edge.edge,
        symbol_xy=(plate_end_edge[0] + 0.0062, plate_end_edge[1] - 0.0035),
        datum="B",
        label="plate +Z end face",
    )
    # The part's nonnumeric machining instruction names the physical +Z B
    # face, opposite length pickup and free +X width pickup. Retain native
    # edges for the final face-qualification witness, without adding a new
    # numeric grade or cluttering the dimension field with finish symbols.
    opposite_end = _end_face_edge(top_edges, x_mm=10.0, z_mm=-PLATE_L / 2.0)
    free_plate_edge = top_edges.exact_line_through(
        (PLATE_W, PLATE_T / 2.0, PLATE_L / 4.0),
        label="free +X plate edge",
    )
    machining_pickups = {
        "knife_edge_datum_a": datum_ridge.edge,
        "plate_end_datum_b": end_edge.edge,
        "plate_opposite_end": opposite_end.edge,
        "plate_free_edge": free_plate_edge.edge,
    }
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
    # 8.43 spans 4.2 mm of sheet (0.0919..0.0961); text between the arrows
    # would sit on its own line (3.35 there stood on 7.06's extension line
    # and 152.40's), so it hangs above the span, right of the 7.06 text
    # (0.275..0.284, up to 0.1035) and left of the 152.40 line (0.396).
    start_z = add_edge_dimension(
        adapter,
        top,
        p0=plate_end_edge,
        p1=seed_rim_top,
        text_xy=(0.292, 0.106),
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
        text_xy=(0.275, 0.1015),
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
    middle_callout = add_native_hole_callout(
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

    process_note = add_property_linked_note(
        adapter, "Manufacturing Notes", 0.020, 0.120
    )
    add_property_linked_note(adapter, "Isometric View Note", 0.300, 0.185)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Summing Lever Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=3,
        settled_checks=(
            lambda: _assert_machined_pickup_faces(machining_pickups),
            lambda: _assert_pickup_process_note(process_note),
            lambda: assert_native_hole_callout_attachment(
                adapter, top, anchor_callout, edge=anchor_rim.edge, label="anchor tap"
            ),
            lambda: assert_native_hole_callout_attachment(
                adapter, top, middle_callout, edge=mid_rim.edge, label="spring-hole middle"
            ),
        ),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
