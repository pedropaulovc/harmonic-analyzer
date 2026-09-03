"""Offline contracts for the summing-lever drawing."""

from __future__ import annotations

import math
from pathlib import Path

import summing_lever_notes
import summing_lever_spec
import draw_summing_lever as drawing
import build_summing_lever as lever
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/summing-lever.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/summing-lever.pdf")
    assert drawing.PNG.as_posix().endswith("/png/summing-lever_drawing.png")
    assert DRAWINGS_BY_NAME["summing_lever"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert lever.DRAWING_DIMENSIONS is summing_lever_notes.DRAWING_DIMENSIONS
    marked = set().union(*summing_lever_notes.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    # The pivot diameter is a right-view silhouette dimension, not a marked
    # circle dimension: a leader to the circle in the front view would cross
    # the rib outline that wraps it.
    assert "CylDia" not in marked
    assert drawing.FRONT_KEEP == {}


def test_draw_view_math_matches_the_spec() -> None:
    assert (drawing.PLATE_W, drawing.TIP_X) == (
        summing_lever_spec.PLATE_W,
        summing_lever_spec.TIP_X,
    )
    assert summing_lever_spec.CYL_R == lever.CYL_R
    assert summing_lever_spec.ANCHOR_R == lever.ANCHOR_R
    assert summing_lever_spec.PLATE_W == lever.PLATE_W
    assert summing_lever_spec.PLATE_T == lever.PLATE_T
    assert summing_lever_spec.HEX_W == lever.HEX_W
    assert summing_lever_spec.HEX_H == lever.HEX_H
    assert summing_lever_spec.HEX_DEPTH == lever.HEX_DEPTH
    assert summing_lever_spec.HOLE_X == lever.HOLE_X
    assert summing_lever_spec.HOLE_COUNT == lever.HOLE_COUNT
    assert summing_lever_spec.CHANNEL_PITCH == lever.CHANNEL_PITCH
    # Rib geometry the sheet dimensions directly (front-view arc radius,
    # right-view rib bands) mirrors the build's constants.
    assert drawing.RIB_ARC_R == lever.ARC_R
    assert drawing.RIB_T == lever.RIB_T
    assert drawing.RIB_OFFSET == lever.RIB_OFFSET
    assert summing_lever_notes.MID_RIB_REACH == lever.MID_RIB_PLATE_REACH
    # The summation arm's side arcs are three-point arcs through the plate
    # corner, the mid-span point and the anchor: R = 138.85 on both sides.
    assert math.isclose(drawing.SUM_ARC_MID[0], lever.SX * lever.SUM_H / 2.0)
    assert math.isclose(drawing.SUM_ARC_MID[1], lever.SUM_BASE / 2.0 - lever.SUM_CURV)


def test_sheet_runs_at_1_to_2_with_1_to_4_isometric_and_2_to_1_detail() -> None:
    assert drawing.SHEET_SCALE == (1.0, 2.0)
    assert drawing.DETAIL_SCALE == (2, 1)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 4)" in source  # the isometric override
    assert source.count("scale=(1, 2)") == 3  # front, top, right
    assert summing_lever_notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:4"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = summing_lever_notes.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "KNIFE EDGE" in notes
    assert "AS CAST" in notes
    # The hex trunnion is dimensioned on DETAIL C (across flats, flat length,
    # included angle) and the right view (length, vertex height): no hex
    # numbers in prose, and never "regular" -- it is not a regular hexagon.
    assert "8.65" not in notes and "10.27" not in notes and "21.72" not in notes
    assert "REGULAR" not in notes
    # The block shares its band with the top view: keep every line short.
    assert max(len(line) for line in lines) <= 40
    # The spring-hole pattern, anchor location, pivot and plate are
    # dimensioned NATIVELY on the sheet; the notes must not repeat those.
    assert "#47" not in notes
    assert "PITCH" not in notes
    assert "152.40" not in notes
    assert "25.40" not in notes
    # Nothing the title block or a dimension already says, no GD&T prose.
    for banned in (
        "UOS", "DIMENSIONS IN", "LINEAR +/-", "+/-", "DATUM", "BASIC",
        "WITHIN", "MHA-", "GRAY-IRON", "GREEN ENAMEL", "Ra ",
    ):
        assert banned not in notes, banned
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_print_keeps_only_the_allowlisted_spring_pattern_frame() -> None:
    # drawing-simplicity-policy.md rule 3: the summing lever is allowlisted for
    # ONE position frame on the 20-hole spring pattern, with the datums it
    # references (A knife-edge axis, B plate end) and the basics that feed it.
    # The former "summation anchor position" frame is gone; the anchor bore is
    # an ordinary toleranced coordinate.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_feature_control_frame(") == 1
    assert source.count("add_datum_feature(") == 2
    assert 'datum="A"' in source
    assert 'datum="B"' in source
    assert 'label="plate -Z end face"' in source
    assert 'quantity="20X"' in source
    assert 'datums=("A", "B")' in source
    assert 'label="spring-hole pattern position"' in source
    assert "summation anchor position" not in source
    assert "anchor_bore_fcf_edge" not in source
    assert "project_part_pmi(" not in source
    assert summing_lever_spec.GEOMETRIC_TOLERANCES_MM == {
        "spring-hole pattern position": "0.30",
    }
    # Only the three pattern coordinates are BASIC; the anchor X is ordinary.
    assert source.count("set_basic_dimension(") == 3
    for basic in ("spring-hole row X", "spring-hole start Z", "spring-hole pitch"):
        assert f'label="{basic}"' in source, basic
    assert 'label="anchor bore X location"' in source
    assert 'set_basic_dimension(adapter, anchor_location' not in source
    # Datum A rides the +Z trunnion's top ridge in the RIGHT view (a clean
    # visible edge with clear space above); the top view's ridges carry the
    # station origin and the roughness symbol instead.
    assert "knife_edge_datum = _right_xy(HEX_Z_INNER + 0.2 * HEX_DEPTH, HEX_H / 2.0)" in source
    assert 'label="knife-edge pivot axis"' in source


def test_pattern_annotations_attach_to_distinct_holes() -> None:
    # Every pattern annotation hangs off a DIFFERENT hole of the column so no
    # leader crosses another leader or the basics' extension lines: end
    # offset and pitch on the end hole, the frame on the third, the callout
    # on the fifth; the row X runs to the hole at the OTHER end.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "end_hole_up = -HOLE_Z_LAST" in source
    assert "top_hole_up = -HOLE_Z_FIRST" in source
    assert "third_rim_top = _top_xy(HOLE_X, end_hole_up + 2.0 * CHANNEL_PITCH + HOLE_DIA / 2.0)" in source
    assert "fifth_rim_right = _top_xy(HOLE_X + HOLE_DIA / 2.0, end_hole_up + 4.0 * CHANNEL_PITCH)" in source
    assert "edge_xy=third_rim_top" in source
    assert "edge_xy=fifth_rim_right" in source


def test_station_origin_is_the_pivot_axis_with_a_centerline() -> None:
    # One origin per view (policy rule 7): the anchor X and the BASIC hole-row
    # X chain through the trunnion ridge (X=0) on one lane; the marked plate
    # width sits on the lane above; the pivot-axis centerline gives its X=0
    # extension line a visible terminus (the plate's X=0 edge is buried
    # inside the cylinder's plan rectangle).
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'label="pivot axis centerline"' in source
    assert "add_view_centerline(" in source
    assert "ridge_dim_edge = _top_xy(0.0, PLATE_L / 2.0 + 0.3 * HEX_DEPTH)" in source
    assert drawing.TOP_LANE_WIDTH_Y > drawing.TOP_LANE_CHAIN_Y
    # Both lanes clear the sheet-top trunnion tip.
    trunnion_tip_y = drawing._top_xy(0.0, summing_lever_spec.HEX_Z_OUTER)[1]
    assert drawing.TOP_LANE_CHAIN_Y > trunnion_tip_y + 0.003
    assert 'text_xy=(0.146, TOP_LANE_CHAIN_Y)' in source
    assert 'text_xy=(0.1758, TOP_LANE_CHAIN_Y)' in source


def test_cast_body_is_dimensioned_on_the_views_not_in_prose() -> None:
    # The casting's arms, web and junctions carry real dimensions: the rib
    # arc radius (front), both summation-arm side radii (top), and the
    # coefficients plate, both rib bands, trunnion length and vertex height
    # (right).  The pivot diameter is a silhouette width with the diameter
    # prefix.  DETAIL C enlarges the knife-edge trunnion end.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("_add_radial_dimension(") >= 3
    assert 'label="rib arc radius"' in source
    assert "summation arc radius" in source
    for label in (
        "pivot diameter",
        "coefficients plate thickness",
        "middle rib thickness",
        "edge rib thickness",
        "trunnion length",
        "hex vertex height",
        "hex across flats",
        "hex flat length",
        "knife-edge included angle",
    ):
        assert f'label="{label}"' in source, label
    assert '_display_as_diameter(adapter, pivot_dia, label="pivot diameter")' in source
    assert 'entity_type="SILHOUETTE"' in source
    assert source.count("create_detail_view(") == 1
    assert 'detail_label="C"' in source
    assert 'entity_types=("VERTEX", "VERTEX")' in source
    # The detail circle covers the hex (+-HEX_H/2 on the 1:2 parent) but not
    # the cylinder circle.
    half_hex_on_parent = summing_lever_spec.HEX_H / 2.0 * drawing._S / 1000.0
    cyl_on_parent = summing_lever_spec.CYL_R * drawing._S / 1000.0
    assert half_hex_on_parent < drawing.DETAIL_RADIUS < cyl_on_parent
    # The included angle the detail shows is the non-regular hexagon's.
    included = 180.0 - 2.0 * math.degrees(
        math.atan2(summing_lever_spec.HEX_H / 4.0, summing_lever_spec.HEX_W / 2.0)
    )
    assert abs(included - 118.64) < 0.01


def test_knife_edge_keeps_its_finish_and_holes_state_the_process() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_surface_finish(") == 1
    assert "knife_edge = _top_xy(0.0, -(PLATE_L / 2.0 + HEX_DEPTH / 2.0))" in source
    assert 'label="knife-edge ridge finish"' in source
    assert source.count("add_native_hole_callout(") == 2
    assert 'process="#47 DRILL"' in source
    assert 'process="DRILL"' in source
    # The seed callout sits in clear space above the title block (whose top
    # rule is at y ~0.0645 for x >= 0.218) and left of the plate-length lane.
    assert 'callout_xy=(0.232, 0.126)' in source
    assert drawing.TOP_KEEP["PlateLength"][0] > 0.232 + 0.030


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "for view in (front, top, right):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(lever.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("summing-lever")
    assert spec["material_specification"] == "ASTM A48 Class 30 gray cast iron"
    assert spec["finish"] == "green enamel; knife edges and anchor bore bare"
    assert int(spec["quantity"]) == 1


def test_surface_finish_is_part_owned_authored_and_consumed() -> None:
    (control,) = summing_lever_spec.SURFACE_FINISHES
    assert control.key == "knife_edge_ridge"
    assert control.roughness_um == 1.6
    assert control.face.normal == summing_lever_spec.KNIFE_FACE_NORMAL
    assert control.face.offset_mm == summing_lever_spec.KNIFE_FACE_OFFSET
    assert (lever.HEX_W, lever.HEX_H) == (
        summing_lever_spec.HEX_W,
        summing_lever_spec.HEX_H,
    )
    part_source = "".join(Path(lever.__file__).read_text(encoding="utf-8").split())
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    sheet_source = "".join(Path(drawing.__file__).read_text(encoding="utf-8").split())
    assert (
        'control=surface_finish_by_key(SURFACE_FINISHES,"knife_edge_ridge")'
        in sheet_source
    )
    assert "roughness_ra=" not in sheet_source
