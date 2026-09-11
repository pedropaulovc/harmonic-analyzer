r"""Create the curated machinist drawing for the summing lever.

The SLDPRT remains authoritative.  This recipe supplies only the summing-lever
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

A large green cast-iron first-class lever hung on hex knife-edge trunnions (no
bore): a coefficients plate on the +X arm carrying the 20 channel-spring holes,
a solid pivot cylinder (152.4 long, along Z), and a summation arm reaching to
the counter-spring anchor eye on the -X arm.  The portrait sheet shows aligned
1:1 top/front manufacturing views and a 1:3 shaded isometric.

Run with SolidWorks open::

    uv run python cad\scripts\draw_summing_lever.py summing-lever
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from summing_lever_spec import GEOMETRIC_TOLERANCES_MM

import _telemetry
from _hole_spec import blind_cut_dia_mm
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_edge_dimension,
    add_feature_control_frame,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    create_section_view,
    finalize_drawing,
    new_project_drawing,
    model_point_in_view,
    read_required_properties,
    set_basic_dimension,
    set_dimension_callouts,
    set_arc_endpoints_to_center,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from summing_lever_spec import (
    ANCHOR_BORE_R,
    ANCHOR_H,
    ANCHOR_R,
    CYL_R,
    CHANNEL_PITCH,
    HEX_DEPTH,
    HEX_H,
    HEX_W,
    HEX_Z_INNER,
    HEX_Z_OUTER,
    HOLE_SPEC,
    HOLE_X,
    HOLE_Z_FIRST,
    OVERALL_Z,
    PLATE_L,
    PLATE_T,
    PLATE_W,
    SURFACE_FINISHES,
    TIP_X,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    place_view,
)


SPEC = DRAWINGS_BY_NAME["summing_lever"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
HOLE_DIA = blind_cut_dia_mm(HOLE_SPEC)

SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (1.0, 1.0)
ISO_SCALE = (1.0, 3.0)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]

# Front and top share the same model-X projection and therefore the same sheet
# X centre.  In ASME third-angle projection the top view belongs ABOVE front.
_BBOX_CX = (TIP_X - ANCHOR_R + PLATE_W) / 2.0

FRONT_CENTER = (0.125, 0.135)
TOP_CENTER = (0.125, 0.290)
ISO_CENTER = (0.225, 0.125)


def _front_xy(mx: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) of a model (X, Y) point in the 1:1 front view."""
    return (
        FRONT_CENTER[0] + (mx - _BBOX_CX) * _S / 1000.0,
        FRONT_CENTER[1] + my * _S / 1000.0,
    )


def _top_xy(mx: float, mz: float) -> tuple[float, float]:
    """Sheet (x, y) of model (X, Z) in the 1:1 SolidWorks top view.

    SolidWorks projects model +Z toward sheet -Y in ``*Top``.  Keeping that
    reversal explicit is essential for the unequal 9.90/8.43 pattern end
    offsets: a sign-blind transform silently dimensions the opposite end.
    """
    return (
        TOP_CENTER[0] + (mx - _BBOX_CX) * _S / 1000.0,
        TOP_CENTER[1] - mz * _S / 1000.0,
    )

def _assert_dimension_value(display: Any, expected_mm: float, *, label: str) -> None:
    """Reject a successful-but-wrong edge pick before the drawing can ship."""
    native = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(native.GetDimension2(0), "IDimension")
    measured_mm = abs(float(dimension.SystemValue)) * 1000.0
    if abs(measured_mm - expected_mm) > 1e-5:
        raise RuntimeError(
            f"{label} measured {measured_mm:.6f} mm; expected {expected_mm:.6f} mm"
        )



FRONT_KEEP: dict[str, tuple[float, float]] = {}
TOP_KEEP = {
    "PlateWidth": (0.165, 0.180),
    "PlateLength": (0.200, TOP_CENTER[1]),
    "AnchorOuterDia": (0.070, 0.317),
    "AnchorBoreDia": (0.070, 0.263),
}
KNIFE_SECTION_KEEP = {
    "HexKnifeFrontS1dy": (0.210, 0.255),
    "HexKnifeFrontTopY": (0.260, 0.255),
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
            0: "Summing Lever Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "summing lever; gray iron; knife-edge first-class lever",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 1))
    knife_cut_z = (HEX_Z_INNER + HEX_Z_OUTER) / 2.0
    knife_section = create_section_view(
        adapter,
        top,
        line_start=_top_xy(-10.0, knife_cut_z),
        line_end=_top_xy(10.0, knife_cut_z),
        view_xy=(0.235, 0.255),
        section_label="K",
        scale=(2, 1),
        label="knife-trunnion profile",
    )
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, top, knife_section):
        set_hidden_lines_visible(adapter, view)
    set_hidden_lines_removed(adapter, iso)

    # The enlarged section isolates the knife profile from the cylinder and
    # plate edges that made the same source dimensions ambiguous in Front.
    knife_annotations = curate_view_dimensions(
        adapter,
        knife_section,
        keep=KNIFE_SECTION_KEEP,
        view_label="knife section K-K",
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    set_dimension_precision(
        adapter,
        knife_annotations,
        {"HexKnifeFrontS1dy": 2, "HexKnifeFrontTopY": 2},
    )
    set_dimension_callouts(
        adapter,
        knife_annotations,
        {
            "HexKnifeFrontS1dy": "FLAT HT",
            "HexKnifeFrontTopY": "KNIFE HT FROM AXIS",
        },
    )
    set_dimension_precision(
        adapter,
        top_annotations,
        {
            "PlateWidth": 1,
            "PlateLength": 1,
            "AnchorOuterDia": 1,
            "AnchorBoreDia": 2,
        },
    )
    set_dimension_callouts(
        adapter, top_annotations, {"AnchorBoreDia": "DRILL THRU"}
    )

    # K-K cuts the free trunnion beyond the plate/cylinder body.  The imported
    # ordinate and middle-flat height, this across-flats size, and the bilateral
    # symmetry note fully define the affine (nonregular) hex profile.
    hex_left = model_point_in_view(
        adapter,
        knife_section,
        (-HEX_W / 2.0, 0.0, knife_cut_z),
        label="knife section left flat",
    )
    hex_right = model_point_in_view(
        adapter,
        knife_section,
        (HEX_W / 2.0, 0.0, knife_cut_z),
        label="knife section right flat",
    )
    hex_width = add_edge_dimension(
        adapter,
        knife_section,
        p0=hex_left,
        p1=hex_right,
        text_xy=(0.235, 0.280),
        label="hex across flats",
        orientation="horizontal",
    )
    _assert_dimension_value(hex_width, HEX_W, label="hex across flats")

    # Size the pivot cylinder from its two visible Top-view flanks rather than
    # the hidden end circle behind the projecting knife trunnion in Front.
    cylinder_diameter = add_edge_dimension(
        adapter,
        top,
        p0=_top_xy(-CYL_R, 40.0),
        p1=_top_xy(CYL_R, 40.0),
        text_xy=(0.125, 0.175),
        label="pivot cylinder diameter",
        orientation="horizontal",
        entity_types=("SILHOUETTE", "EDGE"),
    )
    _assert_dimension_value(
        cylinder_diameter, 2.0 * CYL_R, label="pivot cylinder diameter"
    )
    cylinder_display = _early_bound(cylinder_diameter, "IDisplayDimension")
    cylinder_display.SetText(1, "<MOD-DIAM>")
    if str(cylinder_display.GetText(1) or "") != "<MOD-DIAM>":
        raise RuntimeError("pivot-cylinder diameter glyph did not persist")
    precision_result = cylinder_display.SetPrecision3(1, -1, -1, -1)
    if precision_result is None or int(cylinder_display.GetPrimaryPrecision2()) != 1:
        raise RuntimeError("failed to retain pivot-cylinder diameter precision")
    add_edge_dimension(
        adapter,
        front,
        p0=_front_xy(42.0, -PLATE_T / 2.0),
        p1=_front_xy(42.0, PLATE_T / 2.0),
        text_xy=(0.195, FRONT_CENTER[1]),
        label="coefficient plate thickness",
        orientation="vertical",
    )
    add_edge_dimension(
        adapter,
        front,
        p0=_front_xy(TIP_X, -ANCHOR_H / 2.0),
        p1=_front_xy(TIP_X, ANCHOR_H / 2.0),
        text_xy=(0.045, FRONT_CENTER[1]),
        label="anchor boss height",
        orientation="vertical",
    )

    # Top-view axial definition: the 21.717 overhang is controlling; the
    # explicit 195.834 end-to-end span is reference because it is derived from
    trunnion_depth = add_edge_dimension(
        adapter,
        top,
        p0=_top_xy(0.0, HEX_Z_INNER),
        p1=_top_xy(0.0, HEX_Z_OUTER),
        text_xy=(0.205, _top_xy(0.0, (HEX_Z_INNER + HEX_Z_OUTER) / 2.0)[1]),
        label="knife trunnion depth",
        orientation="vertical",
    )
    trunnion_depth_display = _early_bound(trunnion_depth, "IDisplayDimension")
    trunnion_depth_display.SetText(4, "2X")
    if str(trunnion_depth_display.GetText(4) or "") != "2X":
        raise RuntimeError("2X knife-trunnion depth callout did not persist")
    overall = add_edge_dimension(
        adapter,
        top,
        p0=_top_xy(0.0, -OVERALL_Z / 2.0),
        p1=_top_xy(0.0, OVERALL_Z / 2.0),
        text_xy=(0.032, TOP_CENTER[1]),
        label="trunnion overall length",
        orientation="vertical",
    )
    overall_display = _early_bound(overall, "IDisplayDimension")
    overall_display = set_reference_dimension(
        adapter,
        overall_display.GetAnnotation(),
        label="trunnion overall length",
    )
    precision_result = overall_display.SetPrecision3(3, -1, -1, -1)
    if precision_result is None or int(overall_display.GetPrimaryPrecision2()) != 3:
        raise RuntimeError("failed to retain 195.834 overall reference precision")

    # Pattern datum reference frame: A is the reachable coefficient-plate
    # broad face (primary drill face), B the functional knife-edge pivot ridge,
    # and C the -Z plate end.  The three basic coordinates below locate the row,
    # first station, and pitch.  Anchor-eye location is ordinary, not GD&T.
    broad_face = _front_xy(42.0, PLATE_T / 2.0)
    add_datum_feature(
        adapter,
        front,
        edge_xy=broad_face,
        symbol_xy=(0.195, 0.162),
        datum="A",
        label="coefficient-plate broad face",
    )
    knife_edge_datum = _top_xy(0.0, HEX_Z_INNER + 0.72 * HEX_DEPTH)
    add_datum_feature(
        adapter,
        top,
        edge_xy=knife_edge_datum,
        symbol_xy=(0.120, 0.177),
        datum="B",
        label="knife-edge pivot ridge",
        callout_below="UPPER RIDGE",
    )
    plate_end_edge = _top_xy(10.0, -PLATE_L / 2.0)
    add_datum_feature(
        adapter,
        top,
        edge_xy=plate_end_edge,
        symbol_xy=(0.125, 0.395),
        datum="C",
        label="plate -Z end face",
    )

    ridge_dim_edge = _top_xy(0.0, HEX_Z_INNER + 0.30 * HEX_DEPTH)
    anchor_bore_rim = _top_xy(TIP_X, -ANCHOR_BORE_R)
    anchor_location = add_edge_dimension(
        adapter,
        top,
        p0=ridge_dim_edge,
        p1=anchor_bore_rim,
        text_xy=(0.105, 0.160),
        label="anchor bore X location",
        orientation="horizontal",
    )
    set_arc_endpoints_to_center(
        adapter, anchor_location, label="anchor bore X location"
    )
    seed_rim_right = _top_xy(HOLE_X + HOLE_DIA / 2.0, HOLE_Z_FIRST)
    row_x = add_edge_dimension(
        adapter,
        top,
        p0=ridge_dim_edge,
        p1=seed_rim_right,
        text_xy=(0.165, 0.405),
        label="spring-hole row X",
        orientation="horizontal",
    )
    set_arc_endpoints_to_center(adapter, row_x, label="spring-hole row X")
    set_basic_dimension(adapter, row_x, label="spring-hole row X")
    seed_outer_rim = _top_xy(HOLE_X, HOLE_Z_FIRST - HOLE_DIA / 2.0)
    start_z = add_edge_dimension(
        adapter,
        top,
        p0=plate_end_edge,
        p1=seed_outer_rim,
        text_xy=(0.205, 0.360),
        label="spring-hole start Z",
        orientation="vertical",
    )
    set_arc_endpoints_to_center(adapter, start_z, label="spring-hole start Z")
    set_basic_dimension(adapter, start_z, label="spring-hole start Z")
    seed_side = _top_xy(HOLE_X + HOLE_DIA / 2.0, HOLE_Z_FIRST)
    second_side = _top_xy(
        HOLE_X + HOLE_DIA / 2.0, HOLE_Z_FIRST + CHANNEL_PITCH
    )
    pitch = add_edge_dimension(
        adapter,
        top,
        p0=seed_side,
        p1=second_side,
        text_xy=(0.220, _top_xy(HOLE_X, HOLE_Z_FIRST + CHANNEL_PITCH / 2.0)[1]),
        label="spring-hole pitch",
        orientation="vertical",
    )
    set_arc_endpoints_to_center(adapter, pitch, label="spring-hole pitch")
    set_basic_dimension(adapter, pitch, label="spring-hole pitch")
    pitch_display = _early_bound(pitch, "IDisplayDimension")
    precision_result = pitch_display.SetPrecision3(4, -1, -1, -1)
    pitch_display.OffsetText = True
    pitch_annotation = _early_bound(pitch_display.GetAnnotation(), "IAnnotation")
    if not pitch_annotation.SetPosition2(
        0.242,
        _top_xy(HOLE_X, HOLE_Z_FIRST + CHANNEL_PITCH / 2.0)[1],
        0.0,
    ):
        raise RuntimeError("failed to offset spring-hole pitch text")
    pitch_display.SetText(4, "19 EQ SPACES")
    if (
        precision_result is None
        or int(pitch_display.GetPrimaryPrecision2()) != 4
        or str(pitch_display.GetText(4) or "") != "19 EQ SPACES"
    ):
        raise RuntimeError("spring-hole pitch precision/spacing callout did not persist")

    add_native_hole_callout(
        adapter,
        top,
        edge_xy=seed_outer_rim,
        callout_xy=(0.215, 0.392),
        label="spring-hole pattern",
        process="DRILL",
    )
    pattern_fcf_rim = _top_xy(HOLE_X - HOLE_DIA / 2.0, HOLE_Z_FIRST)
    add_feature_control_frame(
        adapter,
        top,
        edge_xy=pattern_fcf_rim,
        frame_xy=(0.215, 0.340),
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["spring-hole pattern position"],
        datums=("A", "B", "C"),
        diameter=True,
        label="20-hole spring pattern position",
        quantity="20X",
    )

    # The finish belongs on the actual +Z knife ridge, not the coefficient
    # plate.  Its reduced text height matches ordinary drawing annotations.
    knife_edge = _top_xy(0.0, (PLATE_L + HEX_DEPTH) / 2.0)
    add_surface_finish(
        adapter,
        top,
        edge_xy=knife_edge,
        symbol_xy=(0.175, 0.177),
        control=surface_finish_by_key(SURFACE_FINISHES, "knife_edge_ridge"),
        label="knife-edge ridge finish",
        char_height=0.0025,
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.015, 0.080)
    add_property_linked_note(adapter, "Isometric View Note", 0.195, 0.078)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Summing Lever Manufacturing Drawing",
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
