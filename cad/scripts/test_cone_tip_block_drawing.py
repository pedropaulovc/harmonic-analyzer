"""Offline manufacturing contracts for the cone-tip-block drawing."""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path

import pytest

import build_cone_tip_block as part
import cone_tip_block_spec
import draw_cone_tip_block as drawing
from _drawing_registry import DRAWINGS_BY_NAME
from _fit_limits import deviations
from _hole_spec import blind_cut_dia_mm
from _surface_finish import SEAT_UM


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cone-tip-block.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cone-tip-block.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cone-tip-block_drawing.png")
    assert DRAWINGS_BY_NAME["cone_tip_block"].script == Path(drawing.__file__).resolve()


def test_adjuster_thread_is_tapped_through_with_no_floor() -> None:
    """E11/W1: no floor to break out and no tap lead to deduct (Main, 2026-09-24)."""
    spec = cone_tip_block_spec
    assert spec.ADJUSTER_THREAD == "#10-32"
    assert spec.ADJUSTER_BORE_SPEC.end == "through_all"
    assert spec.ADJUSTER_BORE_SPEC.depth_mm == 0.0
    assert "ThreadDepth" not in spec.ADJUSTER_BORE_SPEC.overrides_mm
    assert "PassageProfile" not in spec.DRAWING_DIMENSIONS
    # The tip passes the thread's minimum minor diameter, not a separate hole.
    assert spec.SHAFT_PASSAGE_DIA == pytest.approx(3.9624)
    assert spec.SHAFT_PASSAGE_DIA < spec.ADJUSTER_BORE_DIA


def test_adjuster_engagement_closes_at_the_printed_worst_case() -> None:
    """min(L, embed - .X) - countersink >= 1.5D; the cup stays on full thread."""
    spec = cone_tip_block_spec
    assert spec.WORST_ADJUSTER_ENGAGEMENT_MM == pytest.approx(8.2193)
    assert spec.WORST_ADJUSTER_ENGAGEMENT_MM >= 1.5 * 4.826
    assert spec.ADJUSTER_CSK_DIA > 4.826
    assert spec.ADJUSTER_EMBED_WINDOW == pytest.approx((7.7197, 10.7193))
    low, high = spec.ADJUSTER_EMBED_WINDOW
    assert low <= spec.ADJUSTER_EMBED - 0.8 <= spec.ADJUSTER_EMBED + 0.8 <= high
    assert drawing.ADJUSTER_CSK_QUALIFIER == "90° CSK Ø5.0 BOTH ENDS"


def test_adjuster_callout_names_both_countersinks_under_the_thread() -> None:
    native = {
        5: "<MOD-DIAM> <hw-thrutapdrldia> <hw-thru>",
        6: "",
        7: "<hw-threaddesc> <hw-threadclass> <hw-thru>",
        8: "",
    }
    rewritten = drawing._adjuster_callout_definitions(native)
    assert rewritten[5] == native[5]
    assert rewritten[7] == (
        "<hw-threaddesc> <hw-threadclass> <hw-thru>\n90° CSK Ø5.0 BOTH ENDS"
    )
    with pytest.raises(RuntimeError):
        drawing._adjuster_callout_definitions({**native, 5: native[7]})


def test_pinch_joint_uses_entry_clearance_and_opposite_jaw_thread() -> None:
    """The screw must pass one jaw and engage the other, not bind in both."""
    tap = part.PINCH_BORE_SPEC
    clearance = part.PINCH_CLEARANCE_SPEC
    assert tap is cone_tip_block_spec.PINCH_BORE_SPEC
    assert tap.kind == "tapped"
    assert tap.size == cone_tip_block_spec.PINCH_THREAD
    assert tap.end == "through_all"
    assert clearance is cone_tip_block_spec.PINCH_CLEARANCE_SPEC
    assert clearance.kind == "clearance"
    assert clearance.size == "#4"
    assert clearance.fit == "normal"
    assert clearance.end == "blind"
    assert clearance.depth_mm == (part.BLOCK_X - part.SLIT_W) / 2.0
    assert part.PINCH_BORE_DIA == blind_cut_dia_mm(tap)
    assert part.PINCH_CLEARANCE_DIA == blind_cut_dia_mm(clearance)
    assert part.PINCH_CLEARANCE_DIA > part.PINCH_BORE_DIA


def test_pinch_thread_callout_keeps_native_variables_but_limits_both_extents() -> None:
    """The print must describe the remaining threaded jaw, not the pre-clearance cut."""
    original = {
        5: "<hw-threaddesc> <hw-threadclass> <hw-thru>",
        6: "",
        7: "<MOD-DIAM> <hw-thrutapdrldia> <hw-thru>",
        8: "",
    }
    rewritten = drawing._pinch_thread_callout_definitions(original)
    text = "\n".join(rewritten.values())
    assert "THRU ALL" not in text
    assert text.count("TO SLOT") == 2
    assert drawing._PINCH_THREAD_QUALIFIER in text
    assert all(token in text for token in drawing._PINCH_THREAD_NATIVE_TOKENS)
    # Drill line, thread line, then the prose (Main eye-pass af561fa7).
    assert rewritten[5] == (
        "<hw-threaddesc> <hw-threadclass> TO SLOT\nCOAXIAL WITH CLEARANCE"
    )
    assert rewritten[7] == "<MOD-DIAM> <hw-thrutapdrldia> TO SLOT"
    assert "LEFT-JAW" not in text


def test_pinch_spacing_closes_every_print_tolerance_stack() -> None:
    """The user-approved relative axis control prevents both breakout and collision."""
    assert abs(part.PINCH_BORE_Y - part.ADJUSTER_AXIS_HEIGHT - part.PINCH_RISE) < 1e-12
    assert abs(
        cone_tip_block_spec.BLOCK_HEIGHT
        - cone_tip_block_spec.SLIT_DEPTH
        - cone_tip_block_spec.SLIT_FLOOR
    ) < 1e-12
    spec = cone_tip_block_spec
    assert spec.WORST_SCREW_ENVELOPE_GAP_MM > 0.0
    # U24b / U27: every web keeps 2.0 at the printed limits after edge breaks.
    # E11/W1's #10-32 root (ref Ø5.04 vs Ø8.28) adds ~1.6 to the adjuster webs.
    # r3: PinchHeight .XX from the foot, AxisHeight and BlockHt .X; the
    # 17 block (5/8 pinch screw) adds 1.0 to the adjuster's side wall.
    assert spec.WORST_SLIT_MOUTH_WEB_MM == pytest.approx(2.834, abs=1e-3)
    assert spec.WORST_TOP_LIGAMENT_MM == pytest.approx(2.19, abs=1e-6)
    assert spec.WORST_ADJUSTER_SIDE_LIGAMENT_MM == pytest.approx(4.670, abs=1e-3)
    for web in (
        spec.WORST_SLIT_MOUTH_WEB_MM,
        spec.WORST_TOP_LIGAMENT_MM,
        spec.WORST_ADJUSTER_SIDE_LIGAMENT_MM,
        spec.WORST_PINCH_DEPTH_LIGAMENT_MM,
    ):
        assert round(web, 6) >= spec.MIN_WEB_MM
    tap_bottom = part.PINCH_BORE_Y - part.PINCH_BORE_DIA / 2.0
    assert cone_tip_block_spec.SLIT_FLOOR <= tap_bottom


def test_foot_seat_is_the_only_locating_surface_finish() -> None:
    (finish,) = cone_tip_block_spec.SURFACE_FINISHES
    assert finish.key == "foot_seat"
    assert finish.roughness_um == SEAT_UM
    assert finish.face.normal == (0, -1, 0)
    assert finish.face.offset_mm == 0.0


def test_part_config_preserves_manufacturing_metadata() -> None:
    import _config

    config = _config.parts("cone-tip-block")
    assert "1018" in str(config["material_specification"])
    assert "1018" in str(config["material"])
    assert config["finish"]
    assert int(config["quantity"]) == 1


def test_block_drops_by_the_shim_and_keeps_every_axis_relation() -> None:
    """U30: the shim restores the old axis height; nothing moves off the axis."""
    spec = cone_tip_block_spec
    assert spec.ADJUSTER_AXIS_HEIGHT + spec.SHIM_NOMINAL == 33.368
    assert abs(spec.SLIT_FLOOR - (spec.ADJUSTER_AXIS_HEIGHT - 0.65)) < 1e-12
    assert abs(spec.PINCH_HEIGHT - spec.ADJUSTER_AXIS_HEIGHT - spec.PINCH_RISE) < 1e-12
    assert spec.ADJUSTER_EMBED == 9.5
    assert spec.DRAWING_DIMENSIONS["AxisHeightReference"] == {"AxisHeight"}


def test_pinch_thread_readback_checks_the_thread_part_not_string_order() -> None:
    """c6981bac (run 244bc8bb) resolved exactly this and was wrongly refused."""
    resolved = {
        1: "4-40 UNC - 2B TO SLOT\nCOAXIAL WITH CLEARANCE",
        2: "",
        3: "<MOD-DIAM> 2.26 TO SLOT",
        4: "",
    }
    assert drawing._pinch_thread_callout_resolved(resolved)
    assert not drawing._pinch_thread_callout_resolved(
        {**resolved, 1: "COAXIAL WITH CLEARANCE\n4-40 UNC - 2B TO SLOT"}
    )
    assert not drawing._pinch_thread_callout_resolved(
        {**resolved, 3: "<MOD-DIAM> 2.26 THRU ALL"}
    )


def test_part_hides_every_model_reference_sketch() -> None:
    """f76387f5's iso and 8929d954's drive-train iso printed reference sketches.

    The part blanks every construction-only reference sketch it authors before
    save, so no drawing view or assembly instance renders one, and a new one
    cannot be authored unlisted.
    """

    source = Path(part.__file__).read_text(encoding="utf-8")
    authored = re.findall(r'feature_name="([A-Za-z]+Reference)"', source)
    assert authored and tuple(authored) == part.REFERENCE_SKETCHES
    build_body = source[source.index("async def build(") :]
    assert "_blank_reference_sketches(adapter, REFERENCE_SKETCHES)" in build_body
    assert build_body.index("_blank_reference_sketches(") < build_body.index(
        "save_part_and_images("
    )


def test_section_a_carries_no_dimension_so_shows_no_hidden_sketch() -> None:
    """A derived view keeps the part's sketch visibility from its creation.

    995a7c94 hides every reference sketch in the part.  Section A used to
    dimension PinchRise and was cut while the part showed that sketch; r3
    moved the pinch height to the right view, so the section keeps nothing
    and is cut with the part as saved.
    """
    assert drawing.SECTION_KEEP == {}
    assert not hasattr(drawing, "SECTION_SKETCHES")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build(") :]
    assert "part_sketches_shown(" not in body


def test_only_views_dimensioning_hidden_sketches_opt_in() -> None:
    """The opt-in import goes where a kept dimension lives on a hidden sketch.

    Right (PinchDepthCenter, and r3's PinchHeight) and the plan (FlangeSlotX,
    I31, and r3's two arc-centre baselines) always do; the adjuster elevation
    (AxisHeight/PassageCenter) opts in at build time; left and the base front
    keep only solid-feature dimensions and stay on _drawing_common's import.
    """

    def hidden_owners(keep) -> set[str]:
        return {
            feature
            for feature, names in cone_tip_block_spec.DRAWING_DIMENSIONS.items()
            if set(names) & set(keep)
        } & set(part.REFERENCE_SKETCHES)

    assert hidden_owners(drawing.RIGHT_KEEP) == {
        "PinchDepthReference",
        "PinchHeightReference",
    }
    assert hidden_owners(drawing.TOP_KEEP) == {
        "FlangeSlotXReference",
        "FlangeSlotNorthReference",
        "FlangeSlotSouthReference",
    }
    assert hidden_owners({"AxisHeight": 0, "PassageCenter": 0}) == {
        "AxisHeightReference",
        "PassageCenterReference",
    }
    for keep in (drawing.LEFT_KEEP, drawing.FRONT_KEEP):
        assert hidden_owners(keep) == set()
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build(") :]
    top_call = body[: body.index("keep=TOP_KEEP")]
    assert top_call.rstrip().endswith(
        "top_annotations = hidden_sketches.curate_view_dimensions(\n"
        "        adapter,\n        top,"
    )


def test_every_marked_dimension_is_kept_in_exactly_one_view() -> None:
    """I31 retired the bottom view with the foot tap; nothing it carried may be
    orphaned, and the flange's dimensions each land on one view."""
    adjuster_axis = {"AxisHeight", "PassageCenter", "SlitDepth"}
    kept = [
        *drawing.FRONT_KEEP,
        *drawing.TOP_KEEP,
        *drawing.RIGHT_KEEP,
        *drawing.LEFT_KEEP,
        *drawing.SECTION_KEEP,
        *adjuster_axis,
    ]
    marked = {
        name
        for names in cone_tip_block_spec.DRAWING_DIMENSIONS.values()
        for name in names
    }
    assert sorted(kept) == sorted(set(kept))
    assert set(kept) == marked
    assert not hasattr(drawing, "BOTTOM_KEEP")
    assert set(drawing.TOP_KEEP) == {
        "Depth",
        "FlangeLen",
        "FlangeSlotNorthZ",
        "FlangeSlotSouthZ",
        "FlangeSlotW",
        "FlangeSlotX",
    }


def test_slot_width_text_stands_right_of_its_outside_arrows() -> None:
    """Main eye-pass 5637ac42: the 1.2 slot's extension lines ran through "1.20".
    r3: PassageCenter's span from the -X face takes the slit's left, so the
    value stands right of the right arrow's tail."""
    slot_x = drawing.FRONT_CENTER[0]
    text_x = drawing.FRONT_KEEP["SlitW"][0]
    right_wall = slot_x + part.SLIT_W * drawing._S / 2.0
    arrow_tail = right_wall + drawing.ARROW_LENGTH
    assert text_x - drawing.VALUE_TEXT_HALF_WIDTH >= arrow_tail + 0.001
    passage_x = drawing._adjuster_axis_keep(drawing.FRONT_CENTER)["PassageCenter"][0]
    assert passage_x < slot_x < text_x
    assert drawing.ARROWS_OUTSIDE == (
        "SlitW",
        "HeelReliefDepth",
        "FlangeSlotW",
        "FlangeSlotNorthZ",
    )


def test_sheet_drops_to_three_to_two_for_the_flange() -> None:
    """The flange makes the block 32.8 long; every view centres on that box."""
    assert drawing.SHEET_SCALE == (3.0, 2.0)
    assert drawing._S == pytest.approx(0.0015)
    assert drawing.Z_NORTH - drawing.Z_SOUTH == pytest.approx(
        part.BLOCK_Z + cone_tip_block_spec.FLANGE_LEN
    )
    # *Top shows north down the sheet; the right view shows it on the left.
    assert drawing._plan_y(drawing.Z_NORTH) < drawing._plan_y(drawing.Z_SOUTH)
    assert drawing._right_x(drawing.Z_NORTH) < drawing._right_x(drawing.Z_SOUTH)
    assert (
        drawing._plan_y(drawing.Z_NORTH) + drawing._plan_y(drawing.Z_SOUTH)
    ) / 2.0 == pytest.approx(drawing.TOP_CENTER[1])
    assert (
        drawing._right_x(drawing.Z_NORTH) + drawing._right_x(drawing.Z_SOUTH)
    ) / 2.0 == pytest.approx(drawing.RIGHT_CENTER[0])


def test_half_block_station_value_clears_both_witnesses() -> None:
    """Main eye-pass 5637ac42: the hole witness ended in the decimal point.

    PinchDepthCenter runs from the north face to the pinch-hole centre (the
    model origin), so the value sits between the two witness lines with room
    on both sides, not on either.  At 3:2 the span is 9.0 mm on the sheet, so
    each side keeps 1 mm rather than 5637ac42's 2.
    """
    text_x = drawing.RIGHT_KEEP["PinchDepthCenter"][0]
    half_width = 0.0065 / 2.0  # a three-character value, measured on 5637ac42
    north = drawing._right_x(drawing.Z_NORTH)
    hole = drawing._right_x(0.0)
    assert north + 0.001 <= text_x - half_width
    assert text_x + half_width <= hole - 0.001


def test_pinch_depth_dimension_line_stands_between_the_block_and_section_a() -> None:
    """At +0.003 the 6.0's dimension line printed on the block's top edge."""
    top = drawing._elevation_y(part.BLOCK_HEIGHT, drawing.RIGHT_CENTER)
    line_y = drawing.RIGHT_KEEP["PinchDepthCenter"][1]
    section_foot = drawing._elevation_y(0.0, drawing.SECTION_CENTER)
    assert line_y - top >= 0.005
    assert line_y + drawing.VALUE_TEXT_HALF_HEIGHT <= section_foot - 0.005


def test_heel_relief_is_a_marked_xx_step_on_the_north_bottom_edge() -> None:
    """I31: a 1.53 x 5.56 step clears the cone pivot screw's head (Main,
    2026-09-25); the drive train proves the size from the live parts."""
    spec = cone_tip_block_spec
    assert (spec.HEEL_RELIEF_DEPTH, spec.HEEL_RELIEF_HEIGHT) == (1.53, 5.56)
    assert spec.DRAWING_DIMENSIONS["HeelReliefProfile"] == {
        "HeelReliefDepth",
        "HeelReliefHt",
    }
    assert spec.DRAWING_PRECISION["HeelReliefProfile"] == {
        "HeelReliefDepth": 2,
        "HeelReliefHt": 2,
    }
    source = Path(part.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build(") :]
    # Cut on the Right plane from the north face (sketch -x) down to the foot.
    assert 'create_sketch("Right")' in body[body.index("heel relief") :]
    assert body.index('"HeelRelief"') < body.index('"Flange"')
    assert body.index('"HeelRelief"') < body.index("drive_dimension(")


def test_heel_relief_values_sit_off_their_own_lines_in_the_right_view() -> None:
    """The right view has north on the left: the step is its lower-left notch.
    The depth's value stands left of the north face past its outside arrow,
    between the height's two extension lines, and right of the height's
    dimension line."""
    north_x = drawing._right_x(drawing.Z_NORTH)
    depth_x, depth_y = drawing.RIGHT_KEEP["HeelReliefDepth"]
    height_x, _height_y = drawing.RIGHT_KEEP["HeelReliefHt"]
    half_width = drawing.VALUE_TEXT_HALF_WIDTH
    assert depth_x + half_width <= north_x - drawing.ARROW_LENGTH
    assert height_x + 0.004 <= depth_x - half_width
    foot_y = drawing._elevation_y(0.0, drawing.RIGHT_CENTER)
    top_y = drawing._elevation_y(
        cone_tip_block_spec.HEEL_RELIEF_HEIGHT, drawing.RIGHT_CENTER
    )
    half_height = drawing.VALUE_TEXT_HALF_HEIGHT
    assert foot_y + 0.001 <= depth_y - half_height
    assert depth_y + half_height <= top_y - 0.001
    # Left of the right view, clear of the front view's right edge.
    front_right = drawing.FRONT_CENTER[0] + part.BLOCK_X * drawing._S / 2.0
    assert front_right + 0.010 <= height_x - half_width


def test_flange_thickness_stands_past_the_south_end_short_of_view_b() -> None:
    south_x = drawing._right_x(drawing.Z_SOUTH)
    text_x, text_y = drawing.RIGHT_KEEP["FlangeT"]
    half_width = drawing.VALUE_TEXT_HALF_WIDTH
    left_view_edge = drawing.LEFT_CENTER[0] - (
        drawing.Z_NORTH - drawing.Z_SOUTH
    ) * drawing._S / 2.0
    assert south_x + 0.004 <= text_x - half_width
    assert text_x + half_width <= left_view_edge - 0.003
    assert text_y == pytest.approx(
        drawing._elevation_y(cone_tip_block_spec.FLANGE_T / 2.0, drawing.RIGHT_CENTER)
    )


def test_plan_values_stand_off_the_part_and_each_other() -> None:
    """Left of the plan, stepping out: the north and south arc centres, each
    baselined from the body's south face (r3, option A), then Depth and
    FlangeLen chained on one line, each value mid-span.  Right: the slot
    width, its line across the slot's middle.  Above the south end, higher
    than the A-A arrow: the slot's location from -X (r3's datum)."""
    keep = drawing.TOP_KEEP
    half_width = drawing.VALUE_TEXT_HALF_WIDTH
    half_height = drawing.VALUE_TEXT_HALF_HEIGHT
    plan_left = drawing.TOP_CENTER[0] - part.BLOCK_X * drawing._S / 2.0
    plan_right = drawing.TOP_CENTER[0] + part.BLOCK_X * drawing._S / 2.0
    south_face = -part.BLOCK_Z / 2.0
    assert keep["Depth"][0] == keep["FlangeLen"][0] == drawing.PLAN_CHAIN_X
    assert keep["Depth"][1] == pytest.approx(drawing._plan_y(0.0))
    assert keep["FlangeLen"][1] == pytest.approx(
        drawing._plan_y((south_face + drawing.Z_SOUTH) / 2.0)
    )
    north_x, north_y = keep["FlangeSlotNorthZ"]
    south_x, south_y = keep["FlangeSlotSouthZ"]
    # Each value mid-span on its own line, the lines stepping out from the
    # part: a value keeps TEXT_CLEARANCE off the next line out and the part.
    assert north_y == pytest.approx(
        drawing._plan_y((south_face + drawing.FLANGE_SLOT_NORTH_CENTER_Z) / 2.0)
    )
    assert south_y == pytest.approx(
        drawing._plan_y((south_face + drawing.FLANGE_SLOT_SOUTH_CENTER_Z) / 2.0)
    )
    assert north_x + half_width + drawing.TEXT_CLEARANCE <= plan_left
    for inner, outer in ((north_x, south_x), (south_x, drawing.PLAN_CHAIN_X)):
        assert outer + half_width + drawing.TEXT_CLEARANCE <= inner
    # Both arc centres are located from the south face, not from each other.
    assert drawing.FLANGE_SLOT_NORTH_CENTER_Z == pytest.approx(
        south_face - cone_tip_block_spec.FLANGE_SLOT_NORTH_Z
    )
    assert drawing.FLANGE_SLOT_SOUTH_CENTER_Z == pytest.approx(
        south_face - cone_tip_block_spec.FLANGE_SLOT_SOUTH_Z
    )
    width_x, width_y = keep["FlangeSlotW"]
    assert plan_right + drawing.ARROW_LENGTH <= width_x - half_width
    # Its line, 4.5 mm under the value, runs across the slot's middle, well
    # inside the straight walls and clear of both arc centres' witnesses.
    centre_y = drawing._plan_y(drawing.FLANGE_SLOT_CENTER_Z)
    width_line_y = width_y - drawing.FLANGE_SLOT_W_LINE_DROP
    assert width_line_y == pytest.approx(centre_y)
    for arc_z in (drawing.FLANGE_SLOT_NORTH_CENTER_Z, drawing.FLANGE_SLOT_SOUTH_CENTER_Z):
        assert abs(drawing._plan_y(arc_z) - width_line_y) >= 0.005
    # "3.97" starts 2 mm right of the plan (287c: 0.2 mm).
    value_left = width_x - drawing._VALUE_EXTENTS["FlangeSlotW"][0]
    assert value_left == pytest.approx(plan_right + 0.002)
    loc_x, loc_y = keep["FlangeSlotX"]
    assert plan_left < loc_x < drawing.TOP_CENTER[0]
    assert loc_y - drawing._plan_y(drawing.Z_SOUTH) >= 0.015
    # VIEW C's letter, left of the stem, now stands under the location's
    # value (r3): clear of the value and of its line by TEXT_CLEARANCE.
    letter = drawing.sheet_text_boxes()["view C letter"]
    location_line_y = loc_y - drawing.HORIZONTAL_LINE_DROP
    assert letter[3] + drawing.TEXT_CLEARANCE <= location_line_y
    assert letter[2] <= drawing.TOP_CENTER[0]


# Ink measured on the I31 farm render (7ab69742b, cone-tip-block_drawing.png,
# 5100 x 3300 px = 431.8 x 279.4 mm, 11.81 px/mm): connected-component boxes
# of the dark pixels (< 128), converted to sheet mm with y up from the sheet's
# lower edge.  A callout's box spans its text lines and its leader shoulder.
# The 6.0's glyphs merge with that shoulder, so its box is the column extent
# of its glyph band under the shoulder (143.00 .. 148.84) with the merged
# component's rows.  The heel height's line is its dark column run.
_I31_TEXT_MM = {
    "FlangeLen": (37.68, 229.19, 46.31, 232.66),  # "20.8"
    "FlangeSlotCtoC": (46.99, 229.70, 55.63, 233.09),  # "8.42"
    "pinch clearance callout": (118.11, 170.60, 149.52, 175.68),
    "PinchDepthCenter": (143.00, 169.42, 148.84, 172.72),  # "6.0"
    "adjuster callout": (85.60, 106.51, 142.66, 122.68),
}
_I31_RIGHT_BODY_MM = (141.31, 93.81, 159.43, 164.17)
_I31_HEEL_HEIGHT_LINE_MM = ((119.25, 87.55), (119.25, 108.46))
# " ... " separates fragments a finding must carry, in order.
_I31_FINDINGS = [
    "text-on-text: 'FlangeLen' and 'FlangeSlotCtoC'",
    "text-on-text: 'PinchDepthCenter' and 'pinch clearance callout'",
    "text-on-outline: 'adjuster callout'",
    "text-on-line: HeelReliefHt's dimension line crosses 'adjuster callout'",
]

# Main's eye-pass of the 287c farm render (287c5cf6a, run mha092-287c),
# measured the same way.  A line's cross coordinate is the centre of its dark
# run (0.1 mm thick) and its ends are where the run stops.  An arrow is
# (tip, end of its tail): arrowhead and tail print as one run.  The callout's
# box is its glyphs and shoulder; "foot finish" is the Ra symbol, arm, text
# and shoulder; the 3.97's box includes its +0.1 / 0.0 stack.
_R287_TEXT_MM = {
    "pinch clearance callout": (123.19, 175.01, 154.43, 180.17),
    "PinchDepthCenter": (148.00, 169.33, 153.92, 172.72),  # "6.0"
    "foot finish": (98.98, 80.70, 123.70, 89.49),  # "Ra 3.2"
    "FlangeSlotW": (83.48, 232.58, 102.36, 240.96),  # "3.97" +0.1 / 0.0
    "FlangeSlotZ": (90.17, 221.66, 98.30, 225.04),  # "10.7"
    "ADJUSTER ENTRY": (95.17, 130.98, 131.49, 134.37),
    "view C letter": (64.60, 254.51, 69.17, 259.50),  # the "C" glyph
}
# The plan's outline: its edge columns' dark runs.
_R287_PLAN_MM = (60.75, 197.19, 83.25, 246.72)
_R287_LINES_MM = {
    "PinchDepthCenter": (((140.04, 168.32), (161.63, 168.32)),),  # 6.0's line and tails
    "Width": (((83.19, 78.06), (83.19, 92.60)),),  # 15.0's right extension line
    "FlangeSlotW": (((62.65, 231.95), (103.80, 231.95)),),  # the 3.97's line
    "FlangeSlotZ": (((72.98, 231.43), (94.91, 231.43)),),  # 10.7's slot-centre witness
}
_R287_ARROWS_MM = {
    "HeelReliefHt": (  # the 5.56's outside arrows
        ((124.25, 93.90), (124.25, 87.55)),
        ((124.25, 102.11), (124.25, 108.46)),
    ),
    "FlangeSlotZ": (  # the 10.7's outside arrows
        ((93.90, 231.39), (93.90, 237.74)),
        ((93.90, 215.48), (93.90, 209.04)),
    ),
    "SlitDepth": (((114.93, 141.39), (114.93, 134.87)),),  # the 15.2's lower arrow
    "FlangeSlotX": (((72.00, 259.88), (65.62, 259.88)),),  # the 7.50's left arrow
}
_R287_LEADERS_MM = {
    # Leaves the shoulder's right end and drops almost straight to the hole.
    "pinch clearance callout": ((154.43, 175.22), (155.07, 158.07)),
    "foot finish": ((99.31, 80.90), (77.63, 93.88)),
}
_R287_PINCH_HOLE_MM = ((155.40, 155.56), 2.45)  # the 6.0's hole: centre, radius
# r3 (codex FIX review of 72ab) took the 10.7 and the 8.42 off the print: the
# slot's arc centres are baselined from the south face instead.  Their
# measured ink above stays as the record of those renders, but no placement
# of today's module prints them, so every model comparison skips them.
_R3_RETIRED = frozenset({"FlangeSlotZ", "FlangeSlotCtoC"})
# Where the adjuster callout, its ADJUSTER ENTRY name and the right-hand view
# row stood from I31's round 1 (287c) to 9a0f50b1c, before #946 derived them
# from the hole: the callout below-right of the hole, its name over it, the
# right view at 0.171.
_RD1_PLACEMENT = {
    "RIGHT_CENTER = (_RIGHT_NORTH_FACE_X + (Z_NORTH - Z_MID) * _S,": "RIGHT_CENTER = (0.171,",
    "LEFT_CENTER = (RIGHT_CENTER[0] + VIEW_ROW_PITCH,": "LEFT_CENTER = (0.243,",
    "BACK_CENTER = (RIGHT_CENTER[0] + 2.0 * VIEW_ROW_PITCH,": "BACK_CENTER = (0.315,",
    "ADJUSTER_CALLOUT_DX = _ADJUSTER_SHOULDER_DX + ADJUSTER_CALLOUT_EXTENT[0]": (
        "ADJUSTER_CALLOUT_DX = 0.043"
    ),
    "ADJUSTER_CALLOUT_Y = ADJUSTER_SHOULDER_Y + ADJUSTER_CALLOUT_EXTENT[1]": (
        "ADJUSTER_CALLOUT_Y = 0.121"
    ),
    "ADJUSTER_ENTRY_DX = _ADJUSTER_SHOULDER_DX": "ADJUSTER_ENTRY_DX = 0.023",
    "ADJUSTER_ENTRY_Y = ADJUSTER_SHOULDER_Y - TEXT_CLEARANCE - ROUND_OUT": (
        "ADJUSTER_ENTRY_Y = ADJUSTER_CALLOUT_Y + 0.0135"
    ),
}
# What the 287c sheet commanded at 287c5cf6a, expressed against today's
# module: the r3 lines that replaced a 287c placement map back to it, the
# DRILL TO SLOT growth back to the blind depth's text, and r3's own new
# dimensions keep r3's arrow sides.
_R287_PLACEMENT = {
    **_RD1_PLACEMENT,
    "FLANGE_SLOT_W_Z = FLANGE_SLOT_CENTER_Z - 3.0": (
        "FLANGE_SLOT_W_Z = FLANGE_SLOT_CENTER_Z - 8.42 * 0.4"
    ),
    "_plan_y(Z_SOUTH) + 0.0105)": "_plan_y(Z_SOUTH) + 0.013)",
    "(RIGHT_CENTER[0] - 0.0605, 0.1715)": "(RIGHT_CENTER[0] - 0.033, 0.178)",
    "_PINCH_CLEARANCE_TEXT_GROWTH = 0.0196": "_PINCH_CLEARANCE_TEXT_GROWTH = 0.0",
    "FOOT_FINISH_CENTER = BACK_CENTER": "FOOT_FINISH_CENTER = FRONT_CENTER",
    "_PLAN_RIGHT + 0.0094 + 0.002,": (
        "_PLAN_RIGHT + ARROW_LENGTH + TEXT_CLEARANCE + VALUE_TEXT_HALF_WIDTH,"
    ),
    'ARROWS_INSIDE = ("SlitDepth", "FlangeSlotSouthZ", "PinchHeight")': (
        'ARROWS_INSIDE = ("FlangeSlotSouthZ", "PinchHeight")'
    ),
    # r3 widened the block to 17 and moved PassageCenter's datum (and
    # FlangeSlotX's) to the -X face; 287c printed a 15 block from +X, with
    # the slit width's value on the slit's left at 12 mm.
    'SPEC = DRAWINGS_BY_NAME["cone_tip_block"]': (
        'BLOCK_X = 15.0\nSPEC = DRAWINGS_BY_NAME["cone_tip_block"]'
    ),
    "adjuster_center[0] + minus_x_side * BLOCK_X * _S / 4.0,": (
        "adjuster_center[0] - minus_x_side * BLOCK_X * _S / 4.0,"
    ),
    'h, (ax - plus_x * half_x, ax), (top, top), drop("PassageCenter"), out': (
        'h, (ax, ax + plus_x * half_x), (top, top), drop("PassageCenter"), out'
    ),
    "TOP_CENTER[0] - BLOCK_X * _S / 4.0,": "TOP_CENTER[0] + BLOCK_X * _S / 4.0,",
    'h, (_PLAN_LEFT, tc), (_plan_y(Z_SOUTH),) * 2, drop("FlangeSlotX"), out': (
        'h, (tc, _PLAN_RIGHT), (_plan_y(Z_SOUTH),) * 2, drop("FlangeSlotX"), out'
    ),
    "FRONT_CENTER[0] + SLIT_TEXT_OFFSET,": "FRONT_CENTER[0] - SLIT_TEXT_OFFSET,",
    "SLIT_TEXT_RISE = 0.0145": "SLIT_TEXT_RISE = 0.012",
}
# ... and what the I31 sheet commanded at 7ab69742b, before round 1.
_I31_PLACEMENT = {
    **_R287_PLACEMENT,
    "(RIGHT_CENTER[0] - 0.0605, 0.1715)": "(RIGHT_CENTER[0] - 0.033, 0.1735)",
    "PLAN_CHAIN_X = _PLAN_LEFT - 3.0 * PLAN_BASELINE_STEP": (
        "PLAN_CHAIN_X = TOP_CENTER[0] - 0.030"
    ),
    "RIGHT_CENTER = (_RIGHT_NORTH_FACE_X + (Z_NORTH - Z_MID) * _S,": "RIGHT_CENTER = (0.166,",
    "LEFT_CENTER = (RIGHT_CENTER[0] + VIEW_ROW_PITCH,": "LEFT_CENTER = (0.238,",
    "BACK_CENTER = (RIGHT_CENTER[0] + 2.0 * VIEW_ROW_PITCH,": "BACK_CENTER = (0.310,",
    "ADJUSTER_CALLOUT_Y = ADJUSTER_SHOULDER_Y + ADJUSTER_CALLOUT_EXTENT[1]": (
        "ADJUSTER_CALLOUT_Y = 0.115"
    ),
}
# The whole-sheet audit of the 287c placement.  287c also reported three
# findings on the 10.7 (retired by r3): its line through "3.97", its witness
# beside the 3.97's line and its arrow into the 3.97's stack.
_R287_FINDINGS = [
    "text-on-outline: 'FlangeSlotW' ... plan outline",
    "leader-on-dimension: foot finish's leader crosses Width's",
    "leader-on-dimension: pinch clearance callout's leader crosses PinchDepthCenter's",
    "arrow-near-text: FlangeSlotX's arrow ... 'view C letter'",
    "arrow-near-text: HeelReliefHt's arrow ... 'foot finish'",
    "arrow-near-text: SlitDepth's arrow ... 'ADJUSTER ENTRY'",
    # r3 models section A-A's cutting-plane arrows: 287c's north arrow stood
    # 1.49 mm over the 7.50 (layoutcheck read 1.45 mm on run 1's render).
    "arrow-near-text: section A north's arrow ... 'PassageCenter'",
]


def _m(values):
    return tuple(value / 1000.0 for value in values)


def _m_segment(segment):
    return tuple(_m(point) for point in segment)


def _matches(finding: str, expected: str) -> bool:
    at = 0
    for fragment in expected.split(" ... "):
        at = finding.find(fragment, at)
        if at < 0:
            return False
        at += len(fragment)
    return True


def _findings_match(findings: list[str], expected: list[str]) -> bool:
    return len(findings) == len(expected) and all(
        _matches(finding, pattern) for finding, pattern in zip(findings, expected)
    )


def _drawing_at(replacements: dict[str, str]):
    """The drawing module with some placement lines swapped (a mutant)."""
    import types

    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for old, new in replacements.items():
        assert source.count(old) == 1, old
        source = source.replace(old, new)
    name = "draw_cone_tip_block_mutant"
    mutant = types.ModuleType(name)
    mutant.__file__ = drawing.__file__
    # dataclasses look their module up in sys.modules while decorating.
    sys.modules[name] = mutant
    try:
        exec(compile(source, drawing.__file__, "exec"), mutant.__dict__)
    finally:
        del sys.modules[name]
    return mutant


def _sheet_findings(module) -> list[str]:
    return module.sheet_ink_collisions(
        module.sheet_text_boxes(),
        module.sheet_view_silhouettes(),
        module.sheet_dimension_ink(),
        module.sheet_leaders(),
    )


def _covers(model, ink, slack: float) -> bool:
    """Whether a model box reaches every edge of the measured ink's box."""
    return (
        model[0] <= ink[0] + slack
        and model[1] <= ink[1] + slack
        and model[2] >= ink[2] - slack
        and model[3] >= ink[3] - slack
    )


def _segment_covers(model, ink, slack: float) -> bool:
    """Whether an axis-aligned model segment runs along all of a measured one."""
    for along, across in ((0, 1), (1, 0)):
        if abs(ink[0][across] - ink[1][across]) > slack:
            continue
        if any(abs(point[across] - ink[0][across]) > slack for point in model):
            return False
        model_lo, model_hi = sorted(point[along] for point in model)
        ink_lo, ink_hi = sorted(point[along] for point in ink)
        return model_lo <= ink_lo + slack and model_hi >= ink_hi - slack
    return False


def test_sheet_ink_audit_flags_the_i31_render_and_clears_the_moved_ink() -> None:
    """Main's eye-pass of I31: "20.8" ran into "8.42", the pinch callout sat on
    the 6.0, and the adjuster callout ran over the right view's north face and
    the 5.56's outside arrow.  The shared audit compares none of those pairs
    (dimension and callout boxes are CollisionScope.NONE).  Planted from the
    render's own ink, the sheet audit flags all four; each box moved by what
    its placement constant moved in round 1 clears them."""
    texts = {name: _m(box) for name, box in _I31_TEXT_MM.items()}
    silhouettes = {"right body": _m(_I31_RIGHT_BODY_MM)}
    heel = {"HeelReliefHt": drawing.DimensionInk(lines=(_m_segment(_I31_HEEL_HEIGHT_LINE_MM),))}
    findings = drawing.sheet_ink_collisions(texts, silhouettes, heel, {})
    assert _findings_match(findings, _I31_FINDINGS), findings

    right_dx = drawing.RIGHT_CENTER[0] - 0.166
    callout_x, callout_y = drawing.PINCH_CLEARANCE_CALLOUT_XY
    moves = {
        "FlangeLen": (drawing.PLAN_CHAIN_X - 0.042, 0.0),
        # Round 1 raised it from 0.1735 to 0.178 with the right view; r3 moved
        # it again for DRILL TO SLOT.
        "pinch clearance callout": (callout_x - (0.166 - 0.033), callout_y - 0.1735),
        "PinchDepthCenter": (right_dx, 0.0),
        # #946 moved it again, under SLOT DEPTH's floor line.
        "adjuster callout": (drawing.ADJUSTER_CALLOUT_DX - 0.043, drawing.ADJUSTER_CALLOUT_Y - 0.115),
    }
    grow = drawing._PINCH_CLEARANCE_TEXT_GROWTH / 2.0

    def moved(box, dx, dy, wider=0.0):
        return (box[0] + dx - wider, box[1] + dy, box[2] + dx + wider, box[3] + dy)

    # r3 took the 8.42 off the print.
    texts = {
        name: moved(box, *moves[name], grow if name == "pinch clearance callout" else 0.0)
        for name, box in texts.items()
        if name not in _R3_RETIRED
    }
    silhouettes = {"right body": moved(silhouettes["right body"], right_dx, 0.0)}
    line = tuple((x + right_dx, y) for x, y in heel["HeelReliefHt"].lines[0])
    heel = {"HeelReliefHt": drawing.DimensionInk(lines=(line,))}
    assert drawing.sheet_ink_collisions(texts, silhouettes, heel, {}) == []


def test_sheet_ink_model_reproduces_the_i31_render() -> None:
    """At the I31 placement the module's own boxes cover the measured ink
    (within 0.3 mm), and the audit reports the four round-1 collisions among
    those the round-2 rules add."""
    old = _drawing_at(_I31_PLACEMENT)
    findings = _sheet_findings(old)
    for pattern in _I31_FINDINGS:
        if any(retired in pattern for retired in _R3_RETIRED):
            continue
        assert any(_matches(finding, pattern) for finding in findings), (pattern, findings)
    slack = 0.0003
    predicted = old.sheet_text_boxes()
    for name, box in _I31_TEXT_MM.items():
        if name in _R3_RETIRED:
            continue
        assert _covers(predicted[name], _m(box), slack), name
    body = old.sheet_view_silhouettes()["right body"]
    assert body == pytest.approx(_m(_I31_RIGHT_BODY_MM), abs=slack)
    # The 5.56's arrows stand outside: its dark run is both arrows and tails.
    arrows = old.sheet_dimension_ink()["HeelReliefHt"].arrows
    (ink_x, ink_y0), (_, ink_y1) = _m_segment(_I31_HEEL_HEIGHT_LINE_MM)
    assert all(x == pytest.approx(ink_x, abs=slack) for arrow in arrows for x, _ in arrow)
    ys = [y for arrow in arrows for _, y in arrow]
    assert min(ys) <= ink_y0 + slack and max(ys) >= ink_y1 - slack


@pytest.mark.parametrize(
    ("reverted", "expected"),
    [
        # r3: the 8.42 is gone, but the chain's step out is still what keeps
        # "20.8" off the south arc centre's "14.9", and (the 17 plan reaching
        # 1.5 mm further left) the chain's arrows off the north one's "6.5".
        (
            ("PLAN_CHAIN_X = _PLAN_LEFT - 3.0 * PLAN_BASELINE_STEP",),
            [
                "text-on-text: 'FlangeLen' and 'FlangeSlotSouthZ'",
                "arrow-near-text: Depth's arrow ... 'FlangeSlotNorthZ'",
                "arrow-near-text: FlangeLen's arrow ... 'FlangeSlotNorthZ'",
                "arrow-near-text: FlangeSlotNorthZ's arrow ... 'Depth'",
                "arrow-near-text: FlangeSlotNorthZ's arrow ... 'FlangeLen'",
                "arrow-near-text: FlangeSlotSouthZ's arrow ... 'FlangeLen'",
            ],
        ),
        (
            ("(RIGHT_CENTER[0] - 0.0605, 0.1715)",),
            [
                _I31_FINDINGS[1],
                "arrow-near-text: PinchDepthCenter's arrow ... 'pinch clearance callout'",
            ],
        ),
        # The right view's 5 mm slide still clears the adjuster callout.  (r3's
        # wider pinch callout rides with it; with PassageCenter now on the
        # slit's left and SlitW's value raised, nothing else meets it.)
        (
            (
                "RIGHT_CENTER = (_RIGHT_NORTH_FACE_X + (Z_NORTH - Z_MID) * _S,",
                "LEFT_CENTER = (RIGHT_CENTER[0] + VIEW_ROW_PITCH,",
                "BACK_CENTER = (RIGHT_CENTER[0] + 2.0 * VIEW_ROW_PITCH,",
            ),
            [_I31_FINDINGS[2]],
        ),
        (
            ("ADJUSTER_CALLOUT_Y = ADJUSTER_SHOULDER_Y + ADJUSTER_CALLOUT_EXTENT[1]",),
            [
                _I31_FINDINGS[3],
                "arrow-near-text: HeelReliefHt's arrow ... 'adjuster callout'",
            ],
        ),
    ],
    ids=["a-plan-chain", "b-pinch-callout", "c-right-view", "c-adjuster-callout"],
)
def test_each_i31_move_is_what_clears_its_collision(reverted, expected) -> None:
    # Each move is reverted from where round 1 left the sheet, before #946.
    mutant = _drawing_at({**_RD1_PLACEMENT, **{line: _I31_PLACEMENT[line] for line in reverted}})
    findings = _sheet_findings(mutant)
    assert _findings_match(findings, expected), findings


def _r287_fixture(names: tuple[str, ...]):
    """The 287c render's measured ink for ``names``, as the audit's inputs."""
    texts = {name: _m(box) for name, box in _R287_TEXT_MM.items() if name in names}
    silhouettes = {"plan": _m(_R287_PLAN_MM)} if "plan" in names else {}
    dimensions = {
        name: drawing.DimensionInk(
            tuple(_m_segment(s) for s in _R287_LINES_MM.get(name, ())),
            tuple(_m_segment(s) for s in _R287_ARROWS_MM.get(name, ())),
        )
        for name in names
        if name in _R287_LINES_MM or name in _R287_ARROWS_MM
    }
    leaders = {
        name: drawing.Leader(*_m_segment(segment))
        for name, segment in _R287_LEADERS_MM.items()
        if name in names
    }
    return texts, silhouettes, dimensions, leaders


def _delta(new, old) -> tuple[float, float]:
    return new[0] - old[0], new[1] - old[1]


def _stretch(segment, dx: float, dy: float):
    """Move a segment with its value: up by ``dy``, and its right end (both
    ends of a vertical one) right by ``dx``.  Every value here moves right;
    a line's left end stays on its feature or arrow tail."""
    right = max(x for x, _ in segment)
    return tuple((x + dx if x == right else x, y + dy) for x, y in segment)


def _turned_inside(arrow):
    """An outside arrow turned inside: the same tip, the head pointing back."""
    (tip_x, tip_y), (tail_x, tail_y) = arrow
    run = drawing.ARROW_LENGTH / math.hypot(tail_x - tip_x, tail_y - tip_y)
    return ((tip_x, tip_y), (tip_x - (tail_x - tip_x) * run, tip_y - (tail_y - tip_y) * run))


def _moved_r287_fixture(names: tuple[str, ...]):
    """The planted 287c ink, each owner moved by what its constant moved."""
    old = _drawing_at(_R287_PLACEMENT)
    texts, silhouettes, dimensions, leaders = _r287_fixture(names)
    # r3 took the 10.7 off the print: its ink is simply gone.
    texts = {name: box for name, box in texts.items() if name not in _R3_RETIRED}
    dimensions = {
        name: ink for name, ink in dimensions.items() if name not in _R3_RETIRED
    }
    # #946 slid the right view's whole row, the pinch callout with it; the
    # 287c ink (the 6.0 and its hole) is planted where 287c printed it, so the
    # callout's move is taken in the right view's frame.
    row = drawing.RIGHT_CENTER[0] - old.RIGHT_CENTER[0]
    pinch_dx, pinch_dy = _delta(
        drawing.PINCH_CLEARANCE_CALLOUT_XY, old.PINCH_CLEARANCE_CALLOUT_XY
    )
    moves = {
        "pinch clearance callout": (pinch_dx - row, pinch_dy),
        "foot finish": _delta(
            drawing._foot_finish_placement()[0], old._foot_finish_placement()[0]
        ),
        "FlangeSlotW": _delta(drawing.TOP_KEEP["FlangeSlotW"], old.TOP_KEEP["FlangeSlotW"]),
        "view C letter": _delta(drawing.VIEW_C_ARROW[0], old.VIEW_C_ARROW[0]),
    }
    # r3's DRILL TO SLOT prints wider than 287c's blind depth, both sides of
    # the commanded point; its leader leaves the wider shoulder's right end.
    grow = {"pinch clearance callout": drawing._PINCH_CLEARANCE_TEXT_GROWTH / 2.0}
    still = (0.0, 0.0)
    texts = {
        name: (
            box[0] + dx - grow.get(name, 0.0),
            box[1] + dy,
            box[2] + dx + grow.get(name, 0.0),
            box[3] + dy,
        )
        for name, box in texts.items()
        for dx, dy in [moves.get(name, still)]
    }
    # r3 moved FlangeSlotX's datum to the -X face: its ink mirrors about the
    # plan's centre line rather than translating.
    centre_x = drawing.TOP_CENTER[0]
    mirrored = {"FlangeSlotX"}
    dimensions = {
        name: (
            drawing.DimensionInk(
                tuple(tuple((2.0 * centre_x - x, y) for x, y in s) for s in ink.lines),
                tuple(tuple((2.0 * centre_x - x, y) for x, y in s) for s in ink.arrows),
            )
            if name in mirrored
            else ink
        )
        for name, ink in dimensions.items()
    }
    turned = set(drawing.ARROWS_INSIDE) - set(old.ARROWS_INSIDE)
    dimensions = {
        name: drawing.DimensionInk(
            tuple(_stretch(s, *moves.get(name, still)) for s in ink.lines),
            tuple(
                _turned_inside(s) if name in turned else _stretch(s, *moves.get(name, still))
                for s in ink.arrows
            ),
        )
        for name, ink in dimensions.items()
    }
    hole, hole_r = _R287_PINCH_HOLE_MM
    moved_leaders = {}
    for name, leader in leaders.items():
        dx, dy = moves[name]
        start = (leader.start[0] + dx + grow.get(name, 0.0), leader.start[1] + dy)
        moved_leaders[name] = (
            drawing._leader_to_circle(start, _m(hole), hole_r / 1000.0)
            if name == "pinch clearance callout"
            else drawing.Leader(start, (leader.tip[0] + dx, leader.tip[1] + dy))
        )
    return texts, silhouettes, dimensions, moved_leaders


_R287_ITEMS = {
    # Main (b): the Ø3.26 callout's leader dropped through the 6.0's line.
    "b-pinch-leader": (
        ("pinch clearance callout", "PinchDepthCenter"),
        [
            "leader-on-dimension: pinch clearance callout's leader crosses "
            "PinchDepthCenter's dimension or extension line",
        ],
    ),
    # Main 2: the 5.56's lower arrow ran into the "2" of "Ra 3.2"; the Ra
    # leader also crossed the 15.0's right extension line.
    "ra-finish": (
        ("foot finish", "HeelReliefHt", "Width"),
        [
            "leader-on-dimension: foot finish's leader crosses Width's "
            "dimension or extension line",
            "arrow-near-text: HeelReliefHt's arrow stands 0.25 mm from 'foot finish'",
        ],
    ),
    # Main 3: the 10.7's upper arrow landed inside the 3.97's value and its
    # witness ran 0.5 mm off the 3.97's line; the "3" sat 0.2 mm off the plan.
    "plan-10.7": (
        ("FlangeSlotW", "FlangeSlotZ", "plan"),
        [
            "text-on-outline: 'FlangeSlotW' stands 0.23 mm from the plan outline",
            "text-on-line: FlangeSlotZ's dimension line crosses 'FlangeSlotW'",
            "line-beside-line: FlangeSlotW's and FlangeSlotZ's lines run 0.52 mm apart",
            "arrow-near-text: FlangeSlotZ's arrow stands 0.00 mm from 'FlangeSlotW'",
        ],
    ),
    # Found by the new rules elsewhere on the sheet.
    "slit-depth-tail": (
        ("SlitDepth", "ADJUSTER ENTRY"),
        ["arrow-near-text: SlitDepth's arrow stands 0.20 mm from 'ADJUSTER ENTRY'"],
    ),
    "view-c-letter": (
        ("FlangeSlotX", "view C letter"),
        ["arrow-near-text: FlangeSlotX's arrow stands 0.08 mm from 'view C letter'"],
    ),
}


@pytest.mark.parametrize("item", list(_R287_ITEMS))
def test_sheet_ink_audit_flags_the_287c_render_and_clears_the_moved_ink(item) -> None:
    """Main's eye-pass of 287c: a leader through a dimension line, an arrow
    0.4 mm from foreign text, an arrow inside another value's stack.  Planted
    from the render's own ink, the audit flags each; moved by what its
    placement constant moved, the same ink is clear."""
    names, expected = _R287_ITEMS[item]
    assert drawing.sheet_ink_collisions(*_r287_fixture(names)) == expected
    assert drawing.sheet_ink_collisions(*_moved_r287_fixture(names)) == []


def test_sheet_ink_model_reproduces_the_287c_render() -> None:
    """At the 287c placement the module's boxes cover the measured text; its
    lines, arrows and leaders run along the measured ink (within 0.3 mm); and
    the whole-sheet audit reports exactly the 287c collisions."""
    old = _drawing_at(_R287_PLACEMENT)
    findings = _sheet_findings(old)
    assert _findings_match(findings, _R287_FINDINGS), findings
    slack = 0.0003
    predicted = old.sheet_text_boxes()
    for name, box in _R287_TEXT_MM.items():
        if name in _R3_RETIRED:
            continue
        assert _covers(predicted[name], _m(box), slack), name
    plan = old.sheet_view_silhouettes()["plan"]
    assert plan == pytest.approx(_m(_R287_PLAN_MM), abs=slack)
    ink = old.sheet_dimension_ink()
    for kind, measured in (("lines", _R287_LINES_MM), ("arrows", _R287_ARROWS_MM)):
        for name, segments in measured.items():
            if name in _R3_RETIRED:
                continue
            for segment in segments:
                assert any(
                    _segment_covers(model, _m_segment(segment), slack)
                    for model in getattr(ink[name], kind)
                ), (name, kind, segment)
    leaders = old.sheet_leaders()
    for name, segment in _R287_LEADERS_MM.items():
        model = [value for point in leaders[name].segment() for value in point]
        measured = [value for point in _m_segment(segment) for value in point]
        assert model == pytest.approx(measured, abs=slack), name


# 287c's plan-10.7-station and plan-3.97-line moves cleared collisions with
# the 10.7, which r3 retired; the 3.97's line now runs across the slot's
# middle for a reason of its own (test_plan_values_stand_off_the_part_and_each_other).
@pytest.mark.parametrize(
    ("reverted", "expected"),
    [
        (("_PLAN_RIGHT + 0.0094 + 0.002,",), [_R287_FINDINGS[0]]),
        (("(RIGHT_CENTER[0] - 0.0605, 0.1715)",), [_R287_FINDINGS[2]]),
        (("FOOT_FINISH_CENTER = BACK_CENTER",), [_R287_FINDINGS[1], _R287_FINDINGS[4]]),
        # r3's lower, wider pinch callout now stands in the 15.2's upper
        # outside arrow's run too: inside arrows clear both.
        (
            ('ARROWS_INSIDE = ("SlitDepth", "FlangeSlotSouthZ", "PinchHeight")',),
            [
                "text-on-line: SlitDepth's dimension line crosses 'pinch clearance callout'",
                _R287_FINDINGS[5],
                "arrow-near-text: SlitDepth's arrow ... 'pinch clearance callout'",
            ],
        ),
        # r3: the location's value now stands over the letter, so at 287c's
        # height the letter meets the value itself.
        (
            ("_plan_y(Z_SOUTH) + 0.0105)",),
            ["text-on-text: 'FlangeSlotX' and 'view C letter'"],
        ),
    ],
    ids=[
        "plan-3.97-value",
        "b-pinch-callout",
        "ra-finish-to-view-c",
        "slit-depth-inside",
        "view-c-letter",
    ],
)
def test_each_287c_move_is_what_clears_its_collision(reverted, expected) -> None:
    # Each move is reverted from where round 2 left the sheet, before #946.
    mutant = _drawing_at({**_RD1_PLACEMENT, **{line: _R287_PLACEMENT[line] for line in reverted}})
    findings = _sheet_findings(mutant)
    assert _findings_match(findings, expected), findings


def test_sheet_ink_is_clear_and_the_build_places_what_it_audits() -> None:
    assert _sheet_findings(drawing) == []
    drawing.assert_sheet_ink_clear()
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build(") :]
    assert "assert_sheet_ink_clear(adjuster_center)" in body
    assert body.index("assert_sheet_ink_clear(") < body.index("curate(")
    for placed in (
        "callout_xy=_adjuster_callout_xy(adjuster_center)",
        "callout_xy=PINCH_CLEARANCE_CALLOUT_XY",
        "callout_xy=PINCH_THREAD_CALLOUT_XY",
        "for text, x, y in _sheet_notes(adjuster_center):",
        "adjuster_axis_keep = _adjuster_axis_keep(adjuster_center)",
        "[FOOT_FINISH_CENTER]",
        "foot_symbol, foot_right = _foot_finish_placement()",
        "symbol_xy=foot_symbol",
        "leader_attach_xy=foot_right",
        "_set_arrow_sides(",
        "for name in ARROWS_OUTSIDE",
        "for name in ARROWS_INSIDE",
    ):
        assert placed in body, placed
    assert body.count("add_note(adapter,") == 1
    # The foot's Ra 3.2 sits on VIEW C, where nothing is dimensioned under it.
    assert drawing.FOOT_FINISH_CENTER == drawing.BACK_CENTER
    assert drawing.ARROWS_INSIDE == ("SlitDepth", "FlangeSlotSouthZ", "PinchHeight")
    assert not set(drawing.ARROWS_INSIDE) & set(drawing.ARROWS_OUTSIDE)


def test_sheet_audit_uses_the_shared_leader_geometry() -> None:
    """Crossings and arrow-to-text gaps come from _drawing_leaders, the opt-in
    module the crank drawings gate on, not from a sheet-local copy."""
    import _drawing_leaders

    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_drawing_leaders.leader_crossings(" in source
    assert "_drawing_leaders.arrows_near_text(" in source
    assert drawing.ARROW_TEXT_CLEARANCE == _drawing_leaders.ARROW_TEXT_CLEARANCE == 0.002
    for local in ("def _segments_cross", "def _point_segment_distance"):
        assert local not in source, local


# #946's leader-over-part rule, on this sheet's own model: the run over the
# part from the leader's entry to its tip, minus the tip's shortest approach
# from outside (its distance to the nearest side of the view's outline).
# Swing's RD2 fix (4dda16fd5) left 3.8 mm; Main's brief for RD1 is ~4 mm.
LEADER_DETOUR_TARGET = 0.004


def _run_inside(segment, box) -> float:
    """Length of ``segment`` inside ``box`` (Liang-Barsky clip)."""
    (x0, y0), (x1, y1) = segment
    dx, dy = x1 - x0, y1 - y0
    low, high = 0.0, 1.0
    for p, q in ((-dx, x0 - box[0]), (dx, box[2] - x0), (-dy, y0 - box[1]), (dy, box[3] - y0)):
        if p == 0.0:
            if q < 0.0:
                return 0.0
            continue
        t = q / p
        if p < 0.0:
            low = max(low, t)
        else:
            high = min(high, t)
    return max(0.0, high - low) * math.hypot(dx, dy)


def _leader_detours(module) -> dict[str, tuple[float, float, float]]:
    """(over the part, shortest approach, detour) of every leader whose tip
    lands in a view outline, in sheet metres."""
    silhouettes = module.sheet_view_silhouettes()
    detours = {}
    for name, leader in module.sheet_leaders().items():
        tx, ty = leader.tip
        holding = sorted(
            (box for box in silhouettes.values() if box[0] <= tx <= box[2] and box[1] <= ty <= box[3]),
            key=lambda box: (box[2] - box[0]) * (box[3] - box[1]),
        )
        if not holding:
            continue
        box = holding[0]
        over = _run_inside(leader.segment(), box)
        approach = min(tx - box[0], box[2] - tx, ty - box[1], box[3] - ty)
        detours[name] = (over, approach, over - approach)
    return detours


def test_adjuster_callout_leader_takes_the_short_way_to_its_hole() -> None:
    """#946 / MHA-092: RD1's callout stood below-right of the adjuster hole and
    its leader climbed ~28 mm over the front view to the rim, ~16 mm further
    than the hole's 11.5 mm approach from the right face, reading as an edge
    of the part.  The leader now enters by the hole's shortest approach."""
    detours = _leader_detours(drawing)
    over, approach, detour = detours["adjuster callout"]
    assert detour <= LEADER_DETOUR_TARGET, (over, approach, detour)
    # The shoulder stays off the part, so the leader is the only ink over it.
    start = drawing.sheet_leaders()["adjuster callout"].start
    front = drawing.sheet_view_silhouettes()["front"]
    assert start[0] > front[2]


# The ASME B landscape sheet's frame and title block, as the layout audit's
# dump reads them (ISheet::GetZoneMargin 12.7 mm each side; the title block's
# box, layoutcal2-a cone-tip-block.json).
SHEET_INNER_BORDER = (0.0127, 0.0127, 0.4191, 0.2667)
TITLE_BLOCK = (0.216, 0.0, 0.4318, 0.066)


def _isometric_box(module) -> tuple[float, float, float, float]:
    """The isometric view's outer bound: the part's bounding box seen along
    (1, 1, 1), centred on the view's placement.  Across, (X + Z) / sqrt(2);
    up, Y * sqrt(2/3) + (X + Z) / sqrt(6)."""
    across = module.BLOCK_X + (module.Z_NORTH - module.Z_SOUTH)
    width = across / math.sqrt(2.0) * module._S
    height = (module.BLOCK_HEIGHT * math.sqrt(2.0 / 3.0) + across / math.sqrt(6.0)) * module._S
    x, y = module.ISO_CENTER
    return (x - width / 2.0, y - height / 2.0, x + width / 2.0, y + height / 2.0)


def test_the_slid_view_row_fits_the_sheet() -> None:
    """#946 slid the right view and the removed views B and C right to make
    room for the adjuster callout's short leader.  Every view outline, text
    block and dimension line stays inside the frame and off the title block,
    and no two views' outlines meet."""
    views = {**drawing.sheet_view_silhouettes(), "isometric": _isometric_box(drawing)}
    ink = {
        **{f"view {name}": box for name, box in views.items()},
        **{f"text {name}": box for name, box in drawing.sheet_text_boxes().items()},
    }
    for owner, dimension in drawing.sheet_dimension_ink().items():
        for index, ((x0, y0), (x1, y1)) in enumerate(dimension.segments()):
            ink[f"{owner} line {index}"] = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
    left, bottom, right, top = SHEET_INNER_BORDER
    outside = [
        name
        for name, box in ink.items()
        if box[0] < left or box[1] < bottom or box[2] > right or box[3] > top
    ]
    assert outside == []
    on_title = [
        name
        for name, box in ink.items()
        if box[0] < TITLE_BLOCK[2]
        and box[2] > TITLE_BLOCK[0]
        and box[1] < TITLE_BLOCK[3]
        and box[3] > TITLE_BLOCK[1]
    ]
    assert on_title == []
    # A view's body and its flange share an edge; different views may not.
    owner = {name: name.split(" ")[0] if name.startswith(("right", "view B")) else name for name in views}
    owner["view B body"] = owner["view B flange"] = "view B"
    names = sorted(views)
    touching = [
        (first, second)
        for index, first in enumerate(names)
        for second in names[index + 1 :]
        if owner[first] != owner[second]
        and drawing._box_gap(views[first], views[second]) < drawing.TEXT_CLEARANCE
    ]
    assert touching == []
    # The slide is what the callout needs: the right view's north face stands
    # one text clearance past the callout's right end.
    callout = drawing.sheet_text_boxes()["adjuster callout"]
    assert views["right body"][0] - callout[2] == pytest.approx(
        drawing.TEXT_CLEARANCE + drawing.ROUND_OUT, abs=1e-9
    )


def test_the_9a0f_placement_is_what_ran_the_leader_over_the_part() -> None:
    """Reverting #946's placement brings back the gating detour (the audit's
    provisional limit is 10 mm) and nothing else."""
    old = _drawing_at(_RD1_PLACEMENT)
    over, approach, detour = _leader_detours(old)["adjuster callout"]
    assert detour > 0.010, (over, approach, detour)
    assert _sheet_findings(old) == []


def test_no_leader_on_the_sheet_detours_over_the_part() -> None:
    detours = _leader_detours(drawing)
    assert {"adjuster callout", "pinch clearance callout", "pinch thread callout"} <= set(detours)
    long_way = {name: d for name, d in detours.items() if d[2] > LEADER_DETOUR_TARGET}
    assert long_way == {}


def test_flange_slot_travel_is_built_from_the_fit_up_chain() -> None:
    """Main I31 ruling: the slot passes the screw the fit-up chain plus 1.0
    each way.  r3 (option A): each arc centre is its own .X baseline from the
    south face, so each end spends its own band, not a .XX spacing's."""
    spec = cone_tip_block_spec
    general = {1: 0.8, 2: 0.51}
    chain = (
        general[spec.SHAFT_OVERALL_LENGTH_PLACES]
        + general[spec.BLOCK_DEPTH_PLACES]
        + general[spec.PLATE_TIP_SLOT_Z_PLACES]
        + spec.PLATE_TIP_SLOT_FLOAT
    )
    assert spec.FIT_UP_CHAIN_MM == pytest.approx(chain) == pytest.approx(2.4075)
    assert spec.PLATE_TIP_SLOT_FLOAT == pytest.approx((4.0 + 0.10 - 3.505) / 2.0)
    assert spec.FIT_UP_MARGIN_MM == 1.0
    assert (spec.FLANGE_SLOT_NORTH_Z, spec.FLANGE_SLOT_SOUTH_Z) == (6.5, 14.9)
    end_band = general[spec.FLANGE_SLOT_END_PLACES]
    north = spec.FLANGE_SLOT_Z - chain - (6.5 + end_band - spec.FLANGE_SLOT_FLOAT)
    south = (14.9 - end_band + spec.FLANGE_SLOT_FLOAT) - (spec.FLANGE_SLOT_Z + chain)
    assert spec.FIT_UP_NORTH_MARGIN_MM == pytest.approx(north)
    assert spec.FIT_UP_SOUTH_MARGIN_MM == pytest.approx(south)
    assert min(north, south) >= spec.FIT_UP_MARGIN_MM
    # The ends straddle the screw's nominal station (the plate's TipSlotZ).
    assert (6.5 + 14.9) / 2.0 == pytest.approx(spec.FLANGE_SLOT_Z)
    assert spec.FLANGE_SLOT_CTOC == pytest.approx(8.4)
    source = Path(spec.__file__).read_text(encoding="utf-8")
    assert "3.21" not in source
    assert spec.DRAWING_PRECISION["BlockProfile"]["Depth"] == spec.BLOCK_DEPTH_PLACES
    for end in ("North", "South"):
        assert (
            spec.DRAWING_PRECISION[f"FlangeSlot{end}Reference"][f"FlangeSlot{end}Z"]
            == spec.FLANGE_SLOT_END_PLACES
        )


def test_flange_slot_is_one_pass_of_a_five_thirty_second_end_mill() -> None:
    spec = cone_tip_block_spec
    assert spec.FLANGE_SLOT_W == pytest.approx(5.0 / 32.0 * 25.4)
    # (upper, lower), set through deviations() like every other band.
    assert spec.FLANGE_SLOT_W_BAND == (0.10, 0.0)
    assert deviations(spec.FLANGE_SLOT_W_BAND) == (0.0, 0.10)
    assert spec.FLANGE_SLOT_W - 3.505 >= 0.25
    assert spec.FLANGE_SLOT_X == spec.BLOCK_X / 2.0
    assert spec.DRAWING_DIMENSIONS["FlangeSlotProfile"] == {"FlangeSlotW"}
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert (
        'set_dimension_bilateral_tolerance(\n        adapter, "FlangeSlotProfile", '
        '"FlangeSlotW", *deviations(FLANGE_SLOT_W_BAND)\n    )'
    ) in source


def test_flange_webs_and_nut_clear_the_2_0_target_at_the_printed_limits() -> None:
    """U27 webs and the nut beside the body's south wall, worst case."""
    spec = cone_tip_block_spec
    assert (spec.FLANGE_SLOT_Z, spec.FLANGE_LEN, spec.FLANGE_T) == (10.7, 20.8, 3.50)
    slot_max = spec.FLANGE_SLOT_W + 0.10
    width = spec.BLOCK_X
    # r3: the slot is located .X from -X; the flange's width is .X.
    assert spec.WORST_FLANGE_SIDE_WEB_MM == pytest.approx(
        min(width / 2.0 - 0.8, width - 0.8 - (width / 2.0 + 0.8)) - slot_max / 2.0
    )
    # r3: each arc centre from the south face, .X.
    assert spec.WORST_FLANGE_END_WEB_MM == pytest.approx(
        20.8 - 0.8 - (14.9 + 0.8 + slot_max / 2.0)
    )
    assert spec.WORST_FLANGE_ROOT_WEB_MM == pytest.approx(6.5 - 0.8 - slot_max / 2.0)
    assert spec.WORST_NUT_WALL_AIR_MM == pytest.approx(
        6.5 - 0.8 - spec.FLANGE_SLOT_FLOAT - spec.HOLDDOWN_NUT_AC / 2.0
    )
    for web in (
        spec.WORST_FLANGE_SIDE_WEB_MM,
        spec.WORST_FLANGE_END_WEB_MM,
        spec.WORST_FLANGE_ROOT_WEB_MM,
    ):
        assert round(web, 6) >= spec.MIN_WEB_MM == 2.0
    assert spec.WORST_NUT_WALL_AIR_MM >= spec.NUT_WALL_AIR == 0.5
    assert spec.NUT_BEARING_MM >= 1.0


def test_flange_length_is_its_rule_plus_a_named_end_allowance() -> None:
    """The flange length is derived, not typed: the slot's south edge at its
    printed limits, plus the 2.0 web, plus the length's own .X band, rounded
    up to .X -- then a named allowance, so the end web sits well clear of
    the floor for a first-time machinist."""
    spec = cone_tip_block_spec
    slot_south_edge_max = 14.9 + 0.8 + (spec.FLANGE_SLOT_W + 0.10) / 2.0
    by_rule = math.ceil((slot_south_edge_max + 2.0 + 0.8) * 10.0 - 1e-6) / 10.0
    assert by_rule == pytest.approx(20.6)
    assert spec.FLANGE_END_ALLOWANCE_MM == 0.2
    assert spec.FLANGE_LEN == round(by_rule + 0.2, 1) == 20.8
    assert spec.WORST_FLANGE_END_WEB_MM - spec.MIN_WEB_MM == pytest.approx(
        0.2 + by_rule - (slot_south_edge_max + 2.0 + 0.8)
    )


def test_holddown_screw_stands_a_pitch_past_the_nut_at_the_thickest_stack() -> None:
    """93075A150 (6-32 x 5/8) into 90631A007: head ledge, shim, flange, nut."""
    spec = cone_tip_block_spec
    assert spec.HOLDDOWN_SCREW_LENGTH == pytest.approx(15.875)
    assert spec.HOLDDOWN_NUT_H == pytest.approx(11.0 / 64.0 * 25.4)
    assert spec.HOLDDOWN_NUT_AF == pytest.approx(5.0 / 16.0 * 25.4)
    assert spec.HOLDDOWN_LEDGE_RANGE_MM == (2.71, 3.99)
    shortest = 15.875 - (3.99 + 2.20 + 3.50 + 0.51 + spec.HOLDDOWN_NUT_H)
    assert spec.HOLDDOWN_PROTRUSION_MM[0] == pytest.approx(shortest)
    assert shortest >= 25.4 / 32.0


def test_foot_flange_is_built_after_the_heel_relief_and_before_the_drives() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build(") :]
    order = [
        body.index('name_last_feature(adapter, "HeelRelief")'),
        body.index('name_last_feature(adapter, "FlangeProfile")'),
        body.index('name_last_feature(adapter, "Flange")'),
        body.index('name_last_feature(adapter, "FlangeSlotProfile")'),
        body.index('name_last_feature(adapter, "FlangeSlot")'),
        body.index("drive_dimension("),
    ]
    assert order == sorted(order)
    assert "FootBore" not in source
    assert "FootTap" not in source
    assert part.REFERENCE_SKETCHES[-3:] == (
        "FlangeSlotXReference",
        "FlangeSlotNorthReference",
        "FlangeSlotSouthReference",
    )


# The flange slot at the printed worst case, as numbers: 5/32 +0.10/0 against
# the #6-32 major and the 5/16 nut.
_FLANGE_SLOT_WORST = {
    "FLANGE_SLOT_W_MIN": 5.0 / 32.0 * 25.4,
    "FLANGE_SLOT_W_MAX": 5.0 / 32.0 * 25.4 + 0.10,
    "FLANGE_SLOT_FLOAT": (5.0 / 32.0 * 25.4 + 0.10 - 3.505) / 2.0,
    "NUT_BEARING_MM": (5.0 / 16.0 * 25.4 - (5.0 / 32.0 * 25.4 + 0.10)) / 2.0,
}


def _flange_slot(namespace) -> dict[str, float]:
    return {name: getattr(namespace, name) for name in _FLANGE_SLOT_WORST}


def test_flange_slot_band_is_read_through_deviations() -> None:
    """dtscout / Main (I31): pinned at the worst case, and a raw index read of
    the (upper, lower) band -- or a dropped upper deviation -- moves it."""
    import re
    import types

    assert _flange_slot(cone_tip_block_spec) == pytest.approx(_FLANGE_SLOT_WORST, abs=1e-9)
    source = Path(cone_tip_block_spec.__file__).read_text(encoding="utf-8")
    assert not re.search(r"_BAND\[", source)
    for old, new in (
        (
            "_FLANGE_SLOT_W_LOWER, _FLANGE_SLOT_W_UPPER = deviations(FLANGE_SLOT_W_BAND)",
            # Built by concatenation so no raw index appears in this source.
            "_FLANGE_SLOT_W_LOWER, _FLANGE_SLOT_W_UPPER = "
            + ", ".join("FLANGE_SLOT_W_BAND" + f"[{i}]" for i in (0, 1)),
        ),
        (
            "FLANGE_SLOT_W_MAX = FLANGE_SLOT_W + _FLANGE_SLOT_W_UPPER",
            "FLANGE_SLOT_W_MAX = FLANGE_SLOT_W",
        ),
    ):
        assert source.count(old) == 1, old
        mutant = types.ModuleType("cone_tip_block_spec_mutant")
        mutant.__file__ = cone_tip_block_spec.__file__
        try:
            exec(compile(source.replace(old, new), cone_tip_block_spec.__file__, "exec"), mutant.__dict__)
        except AssertionError:
            continue  # an import-time floor caught it
        assert _flange_slot(mutant) != pytest.approx(_FLANGE_SLOT_WORST, abs=1e-9)


# --- r3: codex FIX review of 72ab (C:/src/dt-logs/mreview-i31/block-72ab) ----
# Every number below is recomputed from the print's own grades
# (DRAWING_PRECISION) and the title block's general bands, never read back
# from the spec's stack constants, so each test states the property itself.
_GENERAL = {1: 0.8, 2: 0.51}
_DRILLED_PLUS = 0.10


def _printed(name: str, nominal: float) -> tuple[float, float]:
    places = cone_tip_block_spec.DRAWING_PRECISION_BY_NAME[name]
    return round(nominal, places) - _GENERAL[places], round(nominal, places) + _GENERAL[places]


def _worst_near_jaw_wall() -> float:
    """Deepest the slit's near wall can stand from the +X (drill) face."""
    spec = cone_tip_block_spec
    passage = _printed("PassageCenter", spec.BLOCK_X / 2.0)
    width = _printed("Width", spec.BLOCK_X)
    slit_half_min = _printed("SlitW", spec.SLIT_W)[0] / 2.0
    return max(passage[1] - slit_half_min, width[1] - passage[0] - slit_half_min)


def test_pinch_clearance_print_breaks_into_the_slit_at_the_worst_case() -> None:
    """Blocker: 72ab printed the Ø3.26 6.9 deep (.X, floor 6.1) into a near
    jaw the print lets run to 8.47 -- the screw could thread-lock short of the
    slit.  Whatever the print says must break into the slit at the worst
    case: a printed blind depth by its lower limit, 0.25 past the deepest
    near wall; DRILL TO SLOT by definition, provided drilling full diameter
    0.25 past that wall only meets the far jaw inside its tap drill."""
    spec = cone_tip_block_spec
    near_wall = _worst_near_jaw_wall()
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    if '"hw-depth"' in source:
        depth = spec.PINCH_CLEARANCE_SPEC.depth_mm
        floor = round(depth, 1) - _GENERAL[1]
        assert floor >= near_wall + 0.25, (floor, near_wall)
        return
    assert drawing.PINCH_CLEARANCE_EXTENT_TEXT == "DRILL TO SLOT"
    clearance_max = round(spec.PINCH_CLEARANCE_DIA, 2) + _DRILLED_PLUS
    point = (clearance_max / 2.0) / math.tan(math.radians(118.0 / 2.0))
    slit_min = _printed("SlitW", spec.SLIT_W)[0]
    past_far_wall = 0.25 + point - slit_min
    assert clearance_max * max(past_far_wall, 0.0) / point <= spec.PINCH_BORE_DIA
    assert spec.WORST_PINCH_NEAR_WALL_MM == pytest.approx(near_wall)


def test_pinch_clearance_callout_rewrites_the_blind_depth_to_drill_to_slot() -> None:
    """The native blind depth pair becomes the instruction; the diameter
    stays its Hole Wizard variable, and any other shape fails loud."""
    native = {5: "<MOD-DIAM><hw-diam> <HOLE-DEPTH> <hw-depth>", 6: "", 7: "", 8: ""}
    rewritten = drawing._pinch_clearance_callout_definitions(native)
    assert rewritten == {5: "<MOD-DIAM><hw-diam> DRILL TO SLOT", 6: "", 7: "", 8: ""}
    with pytest.raises(RuntimeError):
        drawing._pinch_clearance_callout_definitions({**native, 5: "<MOD-DIAM><hw-diam>"})
    with pytest.raises(RuntimeError):
        drawing._pinch_clearance_callout_definitions({**native, 7: native[5]})
    assert drawing._pinch_clearance_callout_resolved(
        {1: "<MOD-DIAM> 3.26 DRILL TO SLOT", 2: "", 3: "", 4: ""}
    )
    assert not drawing._pinch_clearance_callout_resolved(
        {1: "<MOD-DIAM> 3.26 <HOLE-DEPTH> 6.9", 2: "", 3: "", 4: ""}
    )
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build(") :]
    assert "_set_pinch_clearance_callout_text(pinch_clearance_callout)" in body
    assert '"hw-depth"' not in source


def test_far_jaw_is_tapped_full_thread_through_to_the_slit() -> None:
    """The far jaw's thread runs through (TO SLOT), and the tap passes the
    near jaw's clearance, so its lead runs out in the slit, not the jaw."""
    spec = cone_tip_block_spec
    assert spec.PINCH_BORE_SPEC.end == "through_all"
    assert spec.PINCH_CLEARANCE_DIA > 0.112 * 25.4  # #4-40 basic major


def test_r3_prints_no_two_place_dimension_it_does_not_need() -> None:
    """Over-specification: 46.83, 32.27, 8.42 and 8.85 printed .XX with no fit
    or asserted margin needing it.  The overall and axis heights drop to .X;
    the spacing and the rise leave the print (the arc centres baseline from
    the south face, the pinch hole locates from the foot)."""
    grades = cone_tip_block_spec.DRAWING_PRECISION_BY_NAME
    assert grades["BlockHt"] == 1
    assert grades["AxisHeight"] == 1
    for gone in ("FlangeSlotCtoC", "PinchRise", "FlangeSlotZ"):
        assert gone not in grades, gone
    # Kept .XX, each for a named stack (see the report's list).
    assert {name for name, places in grades.items() if places == 2} == {
        "PassageCenter",
        "PinchHeight",
        "SlitW",
        "HeelReliefDepth",
        "HeelReliefHt",
        "FlangeT",
        "FlangeSlotW",
    }


def test_top_ligament_needs_the_pinch_height_at_two_places() -> None:
    """The one r3 .XX kept for a web: at .X the ligament over the pinch hole
    closes at 1.92, under the 2.0 target."""
    spec = cone_tip_block_spec
    clearance_r = (round(spec.PINCH_CLEARANCE_DIA, 2) + _DRILLED_PLUS) / 2.0
    height_min = _printed("BlockHt", spec.BLOCK_HEIGHT)[0]

    def ligament(places: int) -> float:
        pinch_max = round(spec.PINCH_HEIGHT, places) + _GENERAL[places]
        return height_min - pinch_max - clearance_r - 2.0 * spec.EDGE_BREAK_MAX_MM

    assert ligament(2) == pytest.approx(spec.WORST_TOP_LIGAMENT_MM)
    assert round(ligament(2), 6) >= 2.0 > ligament(1)


def _reference_call(body: str, feature: str) -> str:
    """The build's one reference-dimension call that authors ``feature``."""
    at = body.index(f'feature_name="{feature}"')
    start = body.rindex("await _author_", 0, at)
    return body[start : body.index("\n    )\n", at)]


def test_pinch_hole_height_is_located_from_the_foot() -> None:
    """Clarity: the pinch hole prints its height straight from the foot in the
    right view, where it is drilled, not chained off the adjuster axis."""
    spec = cone_tip_block_spec
    assert spec.DRAWING_DIMENSIONS["PinchHeightReference"] == {"PinchHeight"}
    assert "PinchHeight" in drawing.RIGHT_KEEP
    source = Path(part.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build(") :]
    call = _reference_call(body, "PinchHeightReference")
    # Its witness leaves the foot (sketch y 0) at the flange's south end.
    assert "start=(BLOCK_Z / 2.0 + FLANGE_LEN, 0.0)" in call
    assert "end_y=PINCH_BORE_Y" in call
    assert "drive_expression='\"PinchBoreY\"'" in call
    # Its value stands one value-width outside the flange thickness's, over
    # VIEW B's flange and short of VIEW B's body.
    text_x, text_y = drawing.RIGHT_KEEP["PinchHeight"]
    flange_t_x = drawing.RIGHT_KEEP["FlangeT"][0]
    half = drawing.VALUE_TEXT_HALF_WIDTH
    silhouettes = drawing.sheet_view_silhouettes()
    assert flange_t_x + half + drawing.TEXT_CLEARANCE <= text_x - half
    assert text_x + half <= silhouettes["view B body"][0] - 0.005
    assert text_y - drawing.VALUE_TEXT_HALF_HEIGHT >= silhouettes["view B flange"][3] + 0.005
    assert text_y == pytest.approx(
        drawing._elevation_y(spec.PINCH_HEIGHT / 2.0, drawing.RIGHT_CENTER)
    )


def test_flange_slot_arc_centres_baseline_from_the_south_face() -> None:
    """Clarity: each arc centre is located from the body's south face, a face
    the shop can reach, not from the slot's own midpoint."""
    spec = cone_tip_block_spec
    assert spec.DRAWING_DIMENSIONS["FlangeSlotNorthReference"] == {"FlangeSlotNorthZ"}
    assert spec.DRAWING_DIMENSIONS["FlangeSlotSouthReference"] == {"FlangeSlotSouthZ"}
    source = Path(part.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build(") :]
    for end in ("North", "South"):
        call = _reference_call(body, f"FlangeSlot{end}Reference")
        # Sketch y = -Z on the Top plane: BLOCK_Z / 2 is the south face.
        assert "start=(-BLOCK_X / 2.0, BLOCK_Z / 2.0)" in call
        assert f"end_y=BLOCK_Z / 2.0 + FLANGE_SLOT_{end.upper()}_Z" in call


def test_slit_breaks_into_the_adjuster_thread_at_the_printed_limits() -> None:
    """With the heights at .X the slit floor (SlitDepth down from the top)
    must still open into the adjuster's tap drill (AxisHeight up from the
    foot) by 0.25, or the jaws never grip the thread."""
    spec = cone_tip_block_spec
    floor_max = _printed("BlockHt", spec.BLOCK_HEIGHT)[1] - _printed(
        "SlitDepth", spec.SLIT_DEPTH
    )[0]
    crown_min = _printed("AxisHeight", spec.ADJUSTER_AXIS_HEIGHT)[0] + (
        spec.ADJUSTER_BORE_DIA / 2.0
    )
    assert crown_min - floor_max >= 0.25


def test_shim_takes_up_the_printed_axis_height_band() -> None:
    """The fit-up shim sets the adjuster axis on the shaft axis, so its range
    covers the printed AxisHeight band either way plus the pivot post's
    cone-axis height band (the post sets the shaft's height).  Read by value:
    the post's printed band, stacked with the block's, must fit the pack."""
    import cone_pivot_post_spec

    post_band = cone_pivot_post_spec.JOURNAL_AXIS_HEIGHT_TOLERANCE_MM
    spec = cone_tip_block_spec
    assert spec.FIT_UP_SHIM_MARGIN_MM == 0.25
    assert post_band <= spec.FIT_UP_SHIM_MARGIN_MM
    low, high = _printed("AxisHeight", spec.ADJUSTER_AXIS_HEIGHT)
    needed = (
        spec.SHIM_NOMINAL - (spec.ADJUSTER_AXIS_HEIGHT - low) - post_band,
        spec.SHIM_NOMINAL + (high - spec.ADJUSTER_AXIS_HEIGHT) + post_band,
    )
    assert spec.FOOT_SHIM_RANGE_MM[0] <= needed[0] + 1e-9
    assert needed[1] <= spec.FOOT_SHIM_RANGE_MM[1] + 1e-9


def test_flange_slot_fit_keeps_its_cutter_band_for_a_reason() -> None:
    """3.97 +0.1/0 is Main's ruled fit: a general .XX band would let the slot
    come out under the #6-32 major.  The reason is a spec comment and an
    import-time check, not a sheet note (policy rule 6)."""
    spec = cone_tip_block_spec
    assert spec.FLANGE_SLOT_W - _GENERAL[2] < 0.138 * 25.4  # #6-32 basic major
    lower, upper = deviations(spec.FLANGE_SLOT_W_BAND)
    assert spec.FLANGE_SLOT_W + lower - 0.138 * 25.4 >= 0.25
    source = Path(spec.__file__).read_text(encoding="utf-8")
    assert "the fit is\n# no longer needed" in source


# --- r3, round two: the 17 block, the 5/8 pinch screw, the -X datum ---------
# Main's ruling (option (a), 2026-09-25): a #4-40 x 5/8 18-8 stainless
# fillister (McMaster 91794A112) in a 17-wide block, PassageCenter and
# FlangeSlotX printed from the -X face, and a print-worst containment
# contract.  As above, each number is recomputed from the print's grades.
_PINCH_MAJOR_MM = 0.112 * 25.4  # #4-40 basic major


def _datum_face_x(feature: str) -> float:
    """Sketch x of the face the model's ``feature`` reference measures from."""
    source = Path(part.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build(") :]
    start = re.search(r"start=\(([^,]+),", _reference_call(body, feature))
    assert start is not None, feature
    return float(eval(start.group(1), vars(part)))


def _worst_head_face_half() -> float:
    """Farthest the +X (screw-head) face can stand from the adjuster axis at
    the printed limits, PassageCenter taken from the face the model uses."""
    spec = cone_tip_block_spec
    passage = _printed("PassageCenter", spec.BLOCK_X / 2.0)
    width = _printed("Width", spec.BLOCK_X)
    if _datum_face_x("PassageCenterReference") < 0.0:
        return width[1] - passage[0]
    return passage[1]


def _worst_far_wall_from_head() -> float:
    """The slit's far wall, where the far jaw's thread starts, from the head."""
    spec = cone_tip_block_spec
    return _worst_head_face_half() + _printed("SlitW", spec.SLIT_W)[1] / 2.0


def test_far_jaw_keeps_1_5d_of_thread_past_the_slits_far_wall() -> None:
    """72ab asserted 1.5D to the NEAR wall, crediting the slit as thread: the
    1/2 screw kept 3.835 (1.35D) past the far wall.  The 5/8 screw keeps
    5.21 (1.83D) at the printed worst case, the width's band on the head's
    side under the -X datum."""
    spec = cone_tip_block_spec
    engagement = spec.PINCH_SCREW_LENGTH - _worst_far_wall_from_head()
    assert engagement >= 1.5 * _PINCH_MAJOR_MM, engagement
    assert spec.WORST_PINCH_ENGAGEMENT_MM == pytest.approx(engagement)
    assert engagement == pytest.approx(5.21)


def test_pinch_screw_tip_stays_inside_the_minus_x_face() -> None:
    """Regression pin (the 1/2 screw passed it too): at the width's lower
    limit the 5/8 screw's tip stays 0.25 inside the far face."""
    spec = cone_tip_block_spec
    recess = _printed("Width", spec.BLOCK_X)[0] - spec.PINCH_SCREW_LENGTH
    assert recess >= 0.25
    assert spec.WORST_PINCH_TIP_RECESS_MM == pytest.approx(recess)
    assert recess == pytest.approx(0.325)


def test_axis_and_flange_slot_locate_from_the_minus_x_face() -> None:
    """Main's datum: PassageCenter, and FlangeSlotX with it, measure from the
    -X face; the model, the spec and both prints agree."""
    spec = cone_tip_block_spec
    for feature in ("PassageCenterReference", "FlangeSlotXReference"):
        assert _datum_face_x(feature) == pytest.approx(-spec.BLOCK_X / 2.0), feature
    assert spec.PASSAGE_CENTER_DATUM == "-X"
    # Each print's extension lines rise from the -X face and the centre.
    ink = drawing.sheet_dimension_ink()
    half_x = spec.BLOCK_X * drawing._S / 2.0

    def witnesses(name: str) -> list[float]:
        return sorted({round(a[0], 9) for a, b in ink[name].lines if a[0] == b[0]})

    assert witnesses("PassageCenter") == pytest.approx(
        [drawing.FRONT_CENTER[0] - half_x, drawing.FRONT_CENTER[0]]
    )
    assert witnesses("FlangeSlotX") == pytest.approx(
        [drawing._PLAN_LEFT, drawing.TOP_CENTER[0]]
    )


def test_print_worst_containment_fails_loud_on_the_east_datum() -> None:
    """The width band on the -X side would put the block's west face 0.252
    past the swing platform's trimmed corner at W 17; from the -X datum the
    west half is PassageCenter's .XX limit, 0.548 inside it (floor 0.25 plus
    the 0.25 print-worst margin)."""
    import build_drive_train_assembly as drive_train

    spec = cone_tip_block_spec
    with pytest.raises(AssertionError, match="overhang the swing platform"):
        drive_train.tip_block_print_worst_containment_mm(spec.worst_half_widths_mm("+X"))
    margin = drive_train.tip_block_print_worst_containment_mm(
        spec.worst_half_widths_mm(spec.PASSAGE_CENTER_DATUM)
    )
    assert margin == pytest.approx(0.548, abs=1e-3)
    assert margin >= (
        drive_train.PLATFORM_CONTAINMENT_FLOOR_MM + drive_train.TIP_PRINT_WORST_MARGIN_MM
    )
    assert drive_train.TIP_PRINT_WORST_CONTAINMENT_MM == pytest.approx(margin)
    source = Path(drive_train.__file__).read_text(encoding="utf-8")
    # Main's rider: one floor, read by the nominal loop and the print-worst
    # contract alike -- no bare literal beside the named one.
    assert source.count("PLATFORM_CONTAINMENT_FLOOR_MM = ") == 1
    assert "if _plat_half_width(_end) < _hx + PLATFORM_CONTAINMENT_FLOOR_MM:" in source
    assert (
        "if margin < PLATFORM_CONTAINMENT_FLOOR_MM + TIP_PRINT_WORST_MARGIN_MM" in source
    )
    assert "_hx + 0.25" not in source
    assert (
        "tip_block_print_worst_containment_mm(\n"
        "    tip_worst_half_widths_mm(TIP_PASSAGE_CENTER_DATUM)\n)"
    ) in source


def test_print_worst_containment_fails_off_the_plate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CodeRabbit (#838): the print-worst check read the plate's side edges by
    extrapolating them, so a flange run off the plate's south end still found
    'plate' there, and the extrapolated edges widen southwards.  A station off
    the plate must fail loud, as the nominal loop's _plat_half_width does."""
    import build_drive_train_assembly as drive_train

    south_end = (
        drive_train.PIVOT_STATION + drive_train.PLAT_OVERHANG - drive_train.PLAT_LEN
    )
    flange_south = (
        drive_train.TIP_BLOCK_STATION
        - drive_train.TIP_BLOCK_Z / 2.0
        - drive_train.TIP_FLANGE_LEN
    )
    past_the_end = drive_train.TIP_FLANGE_LEN + (flange_south - south_end) + 1.0
    monkeypatch.setattr(drive_train, "TIP_FLANGE_LEN", past_the_end)
    with pytest.raises(AssertionError, match="overhang the swing platform"):
        drive_train.tip_block_print_worst_containment_mm({"+X": 1.0, "-X": 1.0})
    assert drive_train._plat_side_half_widths(south_end - 1.0) == {"+X": -1.0, "-X": -1.0}
    assert drive_train._plat_side_half_widths(
        drive_train.PIVOT_STATION + drive_train.PLAT_OVERHANG + 1.0
    ) == {"+X": -1.0, "-X": -1.0}


def test_drive_train_screw_keeps_1_5d_past_the_far_wall() -> None:
    """The drive train's own check read the NEAR jaw at nominal (12.7 -
    (15 - 1.2)/2 >= 1.5 mm).  The placed screw keeps 1.5D past the printed
    worst far wall, and is the screw the block was sized for."""
    import build_drive_train_assembly as drive_train

    engagement = drive_train.PINCH_SHANK_LEN - _worst_far_wall_from_head()
    assert engagement >= 1.5 * _PINCH_MAJOR_MM, engagement
    source = Path(drive_train.__file__).read_text(encoding="utf-8")
    assert "_PINCH_NEAR_JAW" not in source
    assert "PINCH_SHANK_LEN - TIP_WORST_PINCH_FAR_WALL_MM" in source


def test_pinch_screw_is_the_5_8_stainless_fillister() -> None:
    """The hardware follows the ruling: 91794A112 everywhere and 15.875 under
    the head.  The stainless-over-steel (galvanic) choice is design
    rationale, not a machinist instruction: the material rides the title
    block and the purchased-part ID, so the installation note no longer
    restates it.  The sentence was deleted per the codex machinist review
    of MHA-098 and Main's ruling (a)."""
    import _config
    from _fastener_catalog import fastener
    from diagnostics.diag_mcmaster_fillister import FILLISTER_SIZES

    config = _config.parts("cone-tip-pinch-screw")
    assert config["supplier_skus"] == ["91794A112"]
    assert "18-8 stainless" in config["material"]
    notes = config["installation_notes"].upper()
    assert "STAINLESS" not in notes
    assert "18-8" not in notes
    assert " STEEL" not in notes
    assert fastener("cone-tip-pinch-screw").skus == ("91794A112",)
    assert fastener("cone-tip-pinch-screw").material == "AISI 304"
    assert FILLISTER_SIZES["91794A112"][1] == cone_tip_block_spec.PINCH_SCREW_LENGTH
    assert cone_tip_block_spec.PINCH_SCREW_SKU == "91794A112"
    assert "90280A110" not in FILLISTER_SIZES


# Run 1 (d09c2b9eb leaf dump, c2-dumps/cone-tip-block-d09c2b9eb.json.gz):
# section A's north arrow ran 0.072 -> 0.084 at y 0.209, and PassageCenter's
# 7.50 was centred at (0.0795, 0.205828).  layoutcheck's replay read the
# arrow 1.45 mm over the value (c5-near-crops/cone-tip-block-01).
_RUN1_SECTION_ARROW = ((0.072, 0.209), (0.084, 0.209))
_RUN1_PASSAGE_CENTER = (0.0795, 0.205828)


def test_sheet_audit_sees_section_arrows_run1_hid() -> None:
    """The sheet's own audit fed only dimension and leader arrows, so a
    cutting-plane arrow over a value passed it.  Planted from run 1, the
    same value is clear without the section arrow and flagged with it."""
    x, y = _RUN1_PASSAGE_CENTER
    half_w, half_h = drawing.VALUE_TEXT_HALF_WIDTH, drawing.VALUE_TEXT_HALF_HEIGHT
    texts = {"PassageCenter": (x - half_w, y - half_h, x + half_w, y + half_h)}
    assert drawing.sheet_ink_collisions(texts, {}, {}, {}) == []
    arrow = {"section A north": drawing.section_arrow_ink(*_RUN1_SECTION_ARROW)}
    # Its head, 3.2 across, reached into the value's box, as on the render.
    findings = drawing.sheet_ink_collisions(texts, {}, arrow, {})
    assert _findings_match(
        findings,
        [
            "text-on-line: section A north's dimension line crosses 'PassageCenter'",
            "arrow-near-text: section A north's arrow ... 'PassageCenter'",
        ],
    ), findings


def test_section_arrows_stand_clear_of_every_value() -> None:
    """Today both cutting-plane arrows keep ARROW_TEXT_CLEARANCE (2 mm) from
    every text: PassageCenter's value moved to the slit's left with its
    datum, 3.5 mm from the north arrow; VIEW C's letter is 2.65 mm from the
    south one.  The build cuts the section where the model draws it."""
    from _drawing_leaders import distance_to_box

    texts = drawing.sheet_text_boxes()
    ink = drawing.sheet_dimension_ink()
    gaps = {}
    for arrow in drawing.sheet_section_arrows():
        for name, box in texts.items():
            if name == arrow:
                continue
            nearest = min(distance_to_box(s, box) for s in ink[arrow].arrows)
            gaps[(arrow, name)] = nearest - drawing.ARROW_HALF_WIDTH
    assert min(gaps.values()) >= drawing.ARROW_TEXT_CLEARANCE
    assert gaps[("section A north", "PassageCenter")] == pytest.approx(0.00352, abs=5e-5)
    assert gaps[("section A south", "view C letter")] == pytest.approx(0.00265, abs=5e-5)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build(") :]
    assert "_plan_y(Z_NORTH) - SECTION_LINE_OVERSHOOT)" in body
    assert "_plan_y(Z_SOUTH) + SECTION_LINE_OVERSHOOT)" in body


def test_flange_slot_location_prints_one_place() -> None:
    """Main (r3): FlangeSlotX kept I31's .XX with no stack behind it.  At .X
    the flange's side webs keep 4.87 (target 2.0), and the hold-down screw
    can sit 0.8 + 0.51 = 1.31 off the adjuster axis, which the platform's
    worst cross-slot travel (1.7375, printed 1.74) plus the screw's float in
    the narrowest flange slot (0.23) takes up with 0.66 to spare (0.25
    required)."""
    spec = cone_tip_block_spec
    assert spec.DRAWING_PRECISION_BY_NAME["FlangeSlotX"] == 1
    slot = _printed("FlangeSlotX", spec.FLANGE_SLOT_X)
    width = _printed("Width", spec.BLOCK_X)
    lower, upper = deviations(spec.FLANGE_SLOT_W_BAND)
    side_web = min(slot[0], width[0] - slot[1]) - (spec.FLANGE_SLOT_W + upper) / 2.0
    assert side_web >= 2.0
    assert spec.WORST_FLANGE_SIDE_WEB_MM == pytest.approx(side_web)
    passage = _printed("PassageCenter", spec.BLOCK_X / 2.0)
    offset = max(slot[1] - passage[0], passage[1] - slot[0])
    float_min = (spec.FLANGE_SLOT_W + lower - 0.138 * 25.4) / 2.0
    take_up = 1.7375 + float_min
    assert offset + 0.25 <= take_up
    assert spec.WORST_HOLDDOWN_LATERAL_OFFSET_MM == pytest.approx(offset)
    # The thread table rounds the #6-32 major to 3.505; 0.138 in is 3.5052.
    assert spec.HOLDDOWN_LATERAL_TAKE_UP_MM == pytest.approx(take_up, abs=1e-3)
    assert take_up - offset == pytest.approx(0.6595, abs=1e-3)


_PLATFORM_TRAVEL_RIDER = (
    "merge rider (#838): cone_swing_platform_spec.TIP_LATERAL_TRAVEL_WORST "
    "lands with #830; when #830 is on the base, import it in "
    "cone_tip_block_spec and delete this skip"
)


def test_platform_lateral_travel_lockstep() -> None:
    """The hold-down take-up reads the swing platform's worst lateral travel
    through a named copy until #830 merges.  Once the platform's own symbol is
    importable the copy must equal it, so the platform cannot move its travel
    without this check seeing it."""
    import cone_swing_platform_spec as platform

    source = getattr(platform, "TIP_LATERAL_TRAVEL_WORST", None)
    if source is None:
        pytest.skip(_PLATFORM_TRAVEL_RIDER)
    assert cone_tip_block_spec.PLATE_TIP_LATERAL_TRAVEL_WORST_MM == pytest.approx(
        source, abs=1e-9
    )
