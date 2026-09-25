"""Offline manufacturing contracts for the cone-tip-block drawing."""

from __future__ import annotations

import re
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
    assert width_y <= drawing._plan_y(south_arc_centre)
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
# What the I31 sheet commanded at 7ab69742b, before this fix.
_I31_PLACEMENT = {
    "PLAN_CHAIN_X = TOP_CENTER[0] - 0.036": "PLAN_CHAIN_X = TOP_CENTER[0] - 0.030",
    "RIGHT_CENTER = (0.171,": "RIGHT_CENTER = (0.166,",
    "LEFT_CENTER = (0.243,": "LEFT_CENTER = (0.238,",
    "BACK_CENTER = (0.315,": "BACK_CENTER = (0.310,",
    "(RIGHT_CENTER[0] - 0.033, 0.178)": "(RIGHT_CENTER[0] - 0.033, 0.1735)",
    "ADJUSTER_CALLOUT_Y = 0.121": "ADJUSTER_CALLOUT_Y = 0.115",
}
_I31_FINDINGS = [
    "text-on-text: 'FlangeLen' and 'FlangeSlotCtoC'",
    "text-on-text: 'PinchDepthCenter' and 'pinch clearance callout'",
    "text-on-outline: 'adjuster callout'",
    "text-on-line: HeelReliefHt's dimension line crosses 'adjuster callout'",
]


def _m(box):
    return tuple(value / 1000.0 for value in box)


def _findings_match(findings: list[str], expected: list[str]) -> bool:
    return len(findings) == len(expected) and all(
        finding.startswith(prefix) for finding, prefix in zip(findings, expected)
    )


def _drawing_at(replacements: dict[str, str]):
    """The drawing module with some placement lines swapped (a mutant)."""
    import types

    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for old, new in replacements.items():
        assert source.count(old) == 1, old
        source = source.replace(old, new)
    mutant = types.ModuleType("draw_cone_tip_block_mutant")
    mutant.__file__ = drawing.__file__
    exec(compile(source, drawing.__file__, "exec"), mutant.__dict__)
    return mutant


def _sheet_findings(module) -> list[str]:
    return module.sheet_ink_collisions(
        module.sheet_text_boxes(),
        module.sheet_view_silhouettes(),
        module.sheet_dimension_lines(),
    )


def test_sheet_ink_audit_flags_the_i31_render_and_clears_the_moved_ink() -> None:
    """Main's eye-pass of I31: "20.8" ran into "8.42", the pinch callout sat on
    the 6.0, and the adjuster callout ran over the right view's north face and
    the 5.56's outside arrow.  The shared audit compares none of those pairs
    (dimension and callout boxes are CollisionScope.NONE).  Planted from the
    render's own ink, the sheet audit flags all four; each box moved by what
    its placement constant moved clears them."""
    texts = {name: _m(box) for name, box in _I31_TEXT_MM.items()}
    silhouettes = {"right body": _m(_I31_RIGHT_BODY_MM)}
    lines = {"HeelReliefHt": tuple(_m(point) for point in _I31_HEEL_HEIGHT_LINE_MM)}
    findings = drawing.sheet_ink_collisions(texts, silhouettes, lines)
    assert _findings_match(findings, _I31_FINDINGS), findings

    right_dx = drawing.RIGHT_CENTER[0] - 0.166
    moves = {
        "FlangeLen": (drawing.PLAN_CHAIN_X - 0.042, 0.0),
        "FlangeSlotCtoC": (
            drawing.TOP_KEEP["FlangeSlotCtoC"][0] - (0.042 + 0.06075) / 2.0,
            0.0,
        ),
        "pinch clearance callout": (
            drawing.PINCH_CLEARANCE_CALLOUT_XY[0] - 0.133,
            drawing.PINCH_CLEARANCE_CALLOUT_XY[1] - 0.1735,
        ),
        "PinchDepthCenter": (right_dx, 0.0),
        "adjuster callout": (0.0, drawing.ADJUSTER_CALLOUT_Y - 0.115),
    }

    def moved(box, dx, dy):
        return (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)

    texts = {name: moved(box, *moves[name]) for name, box in texts.items()}
    silhouettes = {"right body": moved(silhouettes["right body"], right_dx, 0.0)}
    lines = {
        "HeelReliefHt": tuple(
            (x + right_dx, y) for x, y in lines["HeelReliefHt"]
        )
    }
    assert drawing.sheet_ink_collisions(texts, silhouettes, lines) == []


def test_sheet_ink_model_reproduces_the_i31_render() -> None:
    """At the I31 placement the module's own boxes cover the measured ink
    (within 0.3 mm) and the audit reports exactly the four collisions."""
    old = _drawing_at(_I31_PLACEMENT)
    assert _findings_match(_sheet_findings(old), _I31_FINDINGS), _sheet_findings(old)
    slack = 0.0003
    predicted = old.sheet_text_boxes()
    for name, box in _I31_TEXT_MM.items():
        model, ink = predicted[name], _m(box)
        assert model[0] <= ink[0] + slack and model[1] <= ink[1] + slack, name
        assert model[2] >= ink[2] - slack and model[3] >= ink[3] - slack, name
    body = old.sheet_view_silhouettes()["right body"]
    assert body == pytest.approx(_m(_I31_RIGHT_BODY_MM), abs=slack)
    (x0, y0), (x1, y1) = old.sheet_dimension_lines()["HeelReliefHt"]
    (ink_x0, ink_y0), (ink_x1, ink_y1) = (_m(p) for p in _I31_HEEL_HEIGHT_LINE_MM)
    assert (x0, x1) == pytest.approx((ink_x0, ink_x1), abs=slack)
    assert y0 <= ink_y0 + slack and y1 >= ink_y1 - slack


@pytest.mark.parametrize(
    ("reverted", "expected"),
    [
        (("PLAN_CHAIN_X = TOP_CENTER[0] - 0.036",), [_I31_FINDINGS[0]]),
        (("(RIGHT_CENTER[0] - 0.033, 0.178)",), [_I31_FINDINGS[1]]),
        (
            ("RIGHT_CENTER = (0.171,", "LEFT_CENTER = (0.243,", "BACK_CENTER = (0.315,"),
            [_I31_FINDINGS[2]],
        ),
        (("ADJUSTER_CALLOUT_Y = 0.121",), [_I31_FINDINGS[3]]),
    ],
    ids=["a-plan-chain", "b-pinch-callout", "c-right-view", "c-adjuster-callout"],
)
def test_each_i31_move_is_what_clears_its_collision(reverted, expected) -> None:
    mutant = _drawing_at({line: _I31_PLACEMENT[line] for line in reverted})
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
    ):
        assert placed in body, placed
    assert body.count("add_note(adapter,") == 1


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
