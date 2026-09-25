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
    assert spec.WORST_SLIT_MOUTH_WEB_MM == pytest.approx(3.664, abs=1e-3)
    assert spec.WORST_TOP_LIGAMENT_MM == pytest.approx(2.00, abs=1e-6)
    assert spec.WORST_ADJUSTER_SIDE_LIGAMENT_MM == pytest.approx(3.670, abs=1e-3)
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


def test_section_a_shows_every_hidden_sketch_it_dimensions() -> None:
    """A derived view keeps the part's sketch visibility from its creation.

    995a7c94 hides every reference sketch in the part; section A is made off
    the plan and dimensions PinchRise, so it is created and curated while the
    part shows exactly the hidden sketches that own its kept dimensions.
    """
    owners = {
        feature
        for feature, names in cone_tip_block_spec.DRAWING_DIMENSIONS.items()
        if set(names) & set(drawing.SECTION_KEEP)
    }
    hidden = owners & set(part.REFERENCE_SKETCHES)
    assert hidden == {"PinchRiseReference"}
    assert tuple(sorted(hidden)) == tuple(sorted(drawing.SECTION_SKETCHES))


def test_only_views_dimensioning_hidden_sketches_opt_in() -> None:
    """The opt-in import goes where a kept dimension lives on a hidden sketch.

    Right (PinchDepthCenter) and the plan (FlangeSlotX/Z, I31) always do; the
    adjuster elevation (AxisHeight/PassageCenter) opts in at build time; left
    and the base front keep only solid-feature dimensions and stay on
    _drawing_common's import.
    """

    def hidden_owners(keep) -> set[str]:
        return {
            feature
            for feature, names in cone_tip_block_spec.DRAWING_DIMENSIONS.items()
            if set(names) & set(keep)
        } & set(part.REFERENCE_SKETCHES)

    assert hidden_owners(drawing.RIGHT_KEEP) == {"PinchDepthReference"}
    assert hidden_owners(drawing.TOP_KEEP) == {
        "FlangeSlotXReference",
        "FlangeSlotZReference",
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
        "FlangeSlotCtoC",
        "FlangeSlotZ",
        "FlangeSlotW",
        "FlangeSlotX",
    }


def test_slot_width_text_stands_left_of_its_outside_arrows() -> None:
    """Main eye-pass 5637ac42: the 1.2 slot's extension lines ran through "1.20"."""
    slot_x = drawing.FRONT_CENTER[0]
    text_x = drawing.FRONT_KEEP["SlitW"][0]
    left_wall = slot_x - part.SLIT_W * drawing._S / 2.0
    arrow_tail = left_wall - drawing.ARROW_LENGTH
    assert text_x + drawing.VALUE_TEXT_HALF_WIDTH <= arrow_tail - 0.001
    assert drawing.ARROWS_OUTSIDE == ("SlitW", "HeelReliefDepth", "FlangeSlotW")


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
    """Left of the plan: Depth and FlangeLen chained on one line, each value
    mid-span, the slot's spacing between that line and the part.  Right: the
    slot's station and, past the end of its span, the slot width.  Above the
    south end, higher than the A-A arrow: the slot's location from +X."""
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
    ctoc_x = keep["FlangeSlotCtoC"][0]
    # The chain's own values are centred on its line: measured from the line
    # alone (+0.004), I31's "20.8" printed 0.7 mm from "8.42".
    assert drawing.PLAN_CHAIN_X + half_width + drawing.TEXT_CLEARANCE <= ctoc_x - half_width
    assert ctoc_x + half_width <= plan_left - 0.0005
    slot_z_x, slot_z_y = keep["FlangeSlotZ"]
    assert plan_right + 0.004 <= slot_z_x - half_width
    assert drawing._plan_y(south_face) + half_height <= slot_z_y
    assert slot_z_y + half_height <= drawing._plan_y(drawing.FLANGE_SLOT_CENTER_Z)
    width_x, width_y = keep["FlangeSlotW"]
    assert plan_right + drawing.ARROW_LENGTH <= width_x - half_width
    # Past the station's span, level with the slot's straight south half.
    centre_y = drawing._plan_y(drawing.FLANGE_SLOT_CENTER_Z)
    assert centre_y + 0.002 <= width_y - half_height
    south_arc_centre = (
        drawing.FLANGE_SLOT_CENTER_Z - cone_tip_block_spec.FLANGE_SLOT_CTOC / 2.0
    )
    # Its line, 4.5 mm under the value, crosses the straight south half 3 mm
    # clear of the 10.7's witness from the slot centre (287c: 0.5 mm).
    width_line_y = width_y - drawing.FLANGE_SLOT_W_LINE_DROP
    assert centre_y + 0.003 <= width_line_y <= drawing._plan_y(south_arc_centre)
    # "3.97" starts 2 mm right of the plan (287c: 0.2 mm).
    value_left = width_x - drawing._VALUE_EXTENTS["FlangeSlotW"][0]
    assert value_left == pytest.approx(plan_right + 0.002)
    loc_x, loc_y = keep["FlangeSlotX"]
    assert drawing.TOP_CENTER[0] < loc_x < plan_right
    assert loc_y - drawing._plan_y(drawing.Z_SOUTH) >= 0.015
    # VIEW C's letter stands left of the stem, clear of the location's value.
    view_c_note = drawing.VIEW_C_ARROW[0]
    assert view_c_note[0] + drawing.VIEW_LETTER_HEIGHT <= loc_x - half_width


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
# What the 287c sheet commanded at 287c5cf6a, before this round.
_R287_PLACEMENT = {
    "TOP_CENTER[0] + 0.036,": "TOP_CENTER[0] + 0.022,",
    "FLANGE_SLOT_CTOC * 0.6": "FLANGE_SLOT_CTOC * 0.4",
    "_plan_y(Z_SOUTH) + 0.0105)": "_plan_y(Z_SOUTH) + 0.013)",
    "(RIGHT_CENTER[0] - 0.058, 0.176)": "(RIGHT_CENTER[0] - 0.033, 0.178)",
    "FOOT_FINISH_CENTER = BACK_CENTER": "FOOT_FINISH_CENTER = FRONT_CENTER",
    "_PLAN_RIGHT + 0.0094 + 0.002,": (
        "_PLAN_RIGHT + ARROW_LENGTH + TEXT_CLEARANCE + VALUE_TEXT_HALF_WIDTH,"
    ),
    'ARROWS_INSIDE = ("SlitDepth",)': "ARROWS_INSIDE: tuple[str, ...] = ()",
}
# ... and what the I31 sheet commanded at 7ab69742b, before round 1.
_I31_PLACEMENT = {
    **_R287_PLACEMENT,
    "(RIGHT_CENTER[0] - 0.058, 0.176)": "(RIGHT_CENTER[0] - 0.033, 0.1735)",
    "PLAN_CHAIN_X = TOP_CENTER[0] - 0.036": "PLAN_CHAIN_X = TOP_CENTER[0] - 0.030",
    "RIGHT_CENTER = (0.171,": "RIGHT_CENTER = (0.166,",
    "LEFT_CENTER = (0.243,": "LEFT_CENTER = (0.238,",
    "BACK_CENTER = (0.315,": "BACK_CENTER = (0.310,",
    "ADJUSTER_CALLOUT_Y = 0.121": "ADJUSTER_CALLOUT_Y = 0.115",
}
# The whole-sheet audit of the 287c placement.
_R287_FINDINGS = [
    "text-on-outline: 'FlangeSlotW' ... plan outline",
    "text-on-line: FlangeSlotZ's dimension line crosses 'FlangeSlotW'",
    "leader-on-dimension: foot finish's leader crosses Width's",
    "leader-on-dimension: pinch clearance callout's leader crosses PinchDepthCenter's",
    "line-beside-line: FlangeSlotW's and FlangeSlotZ's",
    "arrow-near-text: FlangeSlotX's arrow ... 'view C letter'",
    "arrow-near-text: FlangeSlotZ's arrow ... 'FlangeSlotW'",
    "arrow-near-text: HeelReliefHt's arrow ... 'foot finish'",
    "arrow-near-text: SlitDepth's arrow ... 'ADJUSTER ENTRY'",
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
    moves = {
        "FlangeLen": (drawing.PLAN_CHAIN_X - 0.042, 0.0),
        "FlangeSlotCtoC": (
            drawing.TOP_KEEP["FlangeSlotCtoC"][0] - (0.042 + 0.06075) / 2.0,
            0.0,
        ),
        # Round 1 raised it from 0.1735 to 0.178 with the right view.
        "pinch clearance callout": (right_dx, 0.178 - 0.1735),
        "PinchDepthCenter": (right_dx, 0.0),
        "adjuster callout": (0.0, drawing.ADJUSTER_CALLOUT_Y - 0.115),
    }

    def moved(box, dx, dy):
        return (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)

    texts = {name: moved(box, *moves[name]) for name, box in texts.items()}
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
        assert any(_matches(finding, pattern) for finding in findings), (pattern, findings)
    slack = 0.0003
    predicted = old.sheet_text_boxes()
    for name, box in _I31_TEXT_MM.items():
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
        (("PLAN_CHAIN_X = TOP_CENTER[0] - 0.036",), [_I31_FINDINGS[0]]),
        (
            ("(RIGHT_CENTER[0] - 0.058, 0.176)",),
            [
                _I31_FINDINGS[1],
                _R287_FINDINGS[3],
                "arrow-near-text: PinchDepthCenter's arrow ... 'pinch clearance callout'",
            ],
        ),
        (
            ("RIGHT_CENTER = (0.171,", "LEFT_CENTER = (0.243,", "BACK_CENTER = (0.315,"),
            [_I31_FINDINGS[2]],
        ),
        (
            ("ADJUSTER_CALLOUT_Y = 0.121",),
            [
                _I31_FINDINGS[3],
                "arrow-near-text: HeelReliefHt's arrow ... 'adjuster callout'",
            ],
        ),
    ],
    ids=["a-plan-chain", "b-pinch-callout", "c-right-view", "c-adjuster-callout"],
)
def test_each_i31_move_is_what_clears_its_collision(reverted, expected) -> None:
    mutant = _drawing_at({line: _I31_PLACEMENT[line] for line in reverted})
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
    moves = {
        "pinch clearance callout": _delta(
            drawing.PINCH_CLEARANCE_CALLOUT_XY, old.PINCH_CLEARANCE_CALLOUT_XY
        ),
        "foot finish": _delta(
            drawing._foot_finish_placement()[0], old._foot_finish_placement()[0]
        ),
        "FlangeSlotW": _delta(drawing.TOP_KEEP["FlangeSlotW"], old.TOP_KEEP["FlangeSlotW"]),
        "FlangeSlotZ": _delta(drawing.TOP_KEEP["FlangeSlotZ"], old.TOP_KEEP["FlangeSlotZ"]),
        "view C letter": _delta(drawing.VIEW_C_ARROW[0], old.VIEW_C_ARROW[0]),
    }
    still = (0.0, 0.0)
    texts = {
        name: (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)
        for name, box in texts.items()
        for dx, dy in [moves.get(name, still)]
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
        start = (leader.start[0] + dx, leader.start[1] + dy)
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
        assert _covers(predicted[name], _m(box), slack), name
    plan = old.sheet_view_silhouettes()["plan"]
    assert plan == pytest.approx(_m(_R287_PLAN_MM), abs=slack)
    ink = old.sheet_dimension_ink()
    for kind, measured in (("lines", _R287_LINES_MM), ("arrows", _R287_ARROWS_MM)):
        for name, segments in measured.items():
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


@pytest.mark.parametrize(
    ("reverted", "expected"),
    [
        (("TOP_CENTER[0] + 0.036,",), [_R287_FINDINGS[1], _R287_FINDINGS[6]]),
        (("FLANGE_SLOT_CTOC * 0.6",), [_R287_FINDINGS[4]]),
        (("_PLAN_RIGHT + 0.0094 + 0.002,",), [_R287_FINDINGS[0]]),
        (("(RIGHT_CENTER[0] - 0.058, 0.176)",), [_R287_FINDINGS[3]]),
        (("FOOT_FINISH_CENTER = BACK_CENTER",), [_R287_FINDINGS[2], _R287_FINDINGS[7]]),
        (('ARROWS_INSIDE = ("SlitDepth",)',), [_R287_FINDINGS[8]]),
        (("_plan_y(Z_SOUTH) + 0.0105)",), [_R287_FINDINGS[5]]),
    ],
    ids=[
        "plan-10.7-station",
        "plan-3.97-line",
        "plan-3.97-value",
        "b-pinch-callout",
        "ra-finish-to-view-c",
        "slit-depth-inside",
        "view-c-letter",
    ],
)
def test_each_287c_move_is_what_clears_its_collision(reverted, expected) -> None:
    mutant = _drawing_at({line: _R287_PLACEMENT[line] for line in reverted})
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
    assert drawing.ARROWS_INSIDE == ("SlitDepth",)
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


def test_flange_slot_travel_is_built_from_the_fit_up_chain() -> None:
    """Main I31 ruling: slot travel +-(3.21 + 1) from named grade constants."""
    spec = cone_tip_block_spec
    general = {1: 0.8, 2: 0.51}
    chain = (
        general[spec.SHAFT_OVERALL_LENGTH_PLACES]
        + general[spec.BLOCK_DEPTH_PLACES]
        + general[spec.FLANGE_SLOT_Z_PLACES]
        + general[spec.PLATE_TIP_SLOT_Z_PLACES]
        + spec.PLATE_TIP_SLOT_FLOAT
    )
    assert spec.FIT_UP_CHAIN_MM == pytest.approx(chain) == pytest.approx(3.2075)
    assert spec.PLATE_TIP_SLOT_FLOAT == pytest.approx((4.0 + 0.10 - 3.505) / 2.0)
    assert spec.FIT_UP_MARGIN_MM == 1.0
    assert spec.FLANGE_SLOT_HALF_TRAVEL == pytest.approx(4.2075)
    assert spec.FLANGE_SLOT_CTOC == 8.42
    # The spacing's short limit plus the screw's float still spans the chain.
    assert (8.42 - 0.51) / 2.0 + spec.FLANGE_SLOT_FLOAT >= spec.FIT_UP_CHAIN_MM
    # The literal is never typed: the source builds it from the grades.
    source = Path(spec.__file__).read_text(encoding="utf-8")
    assert "3.21" not in source
    assert spec.DRAWING_PRECISION["BlockProfile"]["Depth"] == spec.BLOCK_DEPTH_PLACES
    assert (
        spec.DRAWING_PRECISION["FlangeSlotZReference"]["FlangeSlotZ"]
        == spec.FLANGE_SLOT_Z_PLACES
    )


def test_flange_slot_is_one_pass_of_a_five_thirty_second_end_mill() -> None:
    spec = cone_tip_block_spec
    assert spec.FLANGE_SLOT_W == pytest.approx(5.0 / 32.0 * 25.4)
    # (upper, lower), set through deviations() like every other band.
    assert spec.FLANGE_SLOT_W_BAND == (0.10, 0.0)
    assert deviations(spec.FLANGE_SLOT_W_BAND) == (0.0, 0.10)
    assert spec.FLANGE_SLOT_W - 3.505 >= 0.25
    assert spec.FLANGE_SLOT_X == spec.BLOCK_X / 2.0
    assert spec.DRAWING_DIMENSIONS["FlangeSlotProfile"] == {
        "FlangeSlotW",
        "FlangeSlotCtoC",
    }
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
    half_ctoc_max = (8.42 + 0.51) / 2.0
    # The slot is located .XX from +X; the flange's 15.0 width is .X.
    assert spec.WORST_FLANGE_SIDE_WEB_MM == pytest.approx(
        min(7.5 - 0.51, 15.0 - 0.8 - (7.5 + 0.51)) - slot_max / 2.0
    )
    assert spec.WORST_FLANGE_END_WEB_MM == pytest.approx(
        20.8 - 0.8 - (10.7 + 0.8 + half_ctoc_max + slot_max / 2.0)
    )
    assert spec.WORST_FLANGE_ROOT_WEB_MM == pytest.approx(
        10.7 - 0.8 - half_ctoc_max - slot_max / 2.0
    )
    for web in (
        spec.WORST_FLANGE_SIDE_WEB_MM,
        spec.WORST_FLANGE_END_WEB_MM,
        spec.WORST_FLANGE_ROOT_WEB_MM,
    ):
        assert round(web, 6) >= spec.MIN_WEB_MM == 2.0
    assert spec.WORST_NUT_WALL_AIR_MM >= spec.NUT_WALL_AIR == 0.5
    assert spec.NUT_BEARING_MM >= 1.0


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
    assert part.REFERENCE_SKETCHES[-2:] == (
        "FlangeSlotXReference",
        "FlangeSlotZReference",
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
