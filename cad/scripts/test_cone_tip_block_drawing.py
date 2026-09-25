"""Offline manufacturing contracts for the cone-tip-block drawing."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import build_cone_tip_block as part
import cone_tip_block_spec
import draw_cone_tip_block as drawing
from _drawing_registry import DRAWINGS_BY_NAME
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


def test_foot_hold_down_tap_is_blind_and_clear_of_the_adjuster() -> None:
    """U30: the hidden #6-32 hold-down threads into the foot, nowhere else."""
    spec = cone_tip_block_spec.FOOT_BORE_SPEC
    assert spec.kind == "tapped"
    assert spec.size == "#6-32"
    assert spec.end == "blind"
    assert 0.0 < spec.overrides_mm["ThreadDepth"] < spec.depth_mm
    low, high = cone_tip_block_spec.FOOT_SCREW_REACH_MM
    assert low >= 1.5 * 3.505
    assert high <= spec.overrides_mm["ThreadDepth"] - 0.25
    passage_floor = part.ADJUSTER_AXIS_HEIGHT - part.ADJUSTER_BORE_DIA / 2.0
    assert passage_floor - spec.depth_mm >= 10.0


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

    Right (PinchDepthCenter) and bottom (FootTapX/Z) always do; the adjuster
    elevation (AxisHeight/PassageCenter) opts in at build time; plan, left
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
    assert hidden_owners(drawing.BOTTOM_KEEP) == {"FootTapXReference", "FootTapZReference"}
    assert hidden_owners({"AxisHeight": 0, "PassageCenter": 0}) == {
        "AxisHeightReference",
        "PassageCenterReference",
    }
    for keep in (drawing.TOP_KEEP, drawing.LEFT_KEEP, drawing.FRONT_KEEP):
        assert hidden_owners(keep) == set()


def test_slot_width_text_stands_left_of_its_outside_arrows() -> None:
    """Main eye-pass 5637ac42: the 1.2 slot's extension lines ran through "1.20"."""
    slot_x = drawing.FRONT_CENTER[0]
    text_x = drawing.FRONT_KEEP["SlitW"][0]
    left_wall = slot_x - part.SLIT_W * drawing._S / 2.0
    arrow_tail = left_wall - drawing.ARROW_LENGTH
    assert text_x + drawing.VALUE_TEXT_HALF_WIDTH <= arrow_tail - 0.001
    assert drawing.ARROWS_OUTSIDE == ("SlitW",)


@pytest.mark.parametrize(
    ("keep", "name", "center", "half_span"),
    [
        (drawing.BOTTOM_KEEP, "FootTapX", drawing.BOTTOM_CENTER[0], part.BLOCK_X),
        (drawing.RIGHT_KEEP, "PinchDepthCenter", drawing.RIGHT_CENTER[0], part.BLOCK_Z),
    ],
)
def test_half_block_station_values_clear_both_witnesses(
    keep, name, center, half_span
) -> None:
    """Main eye-pass 5637ac42: the tap and hole witnesses ended in the decimal point.

    Each station runs from a block edge to the centre; the value sits between
    the two witness lines with room on both sides, not on either.
    """
    text_x = keep[name][0]
    half_width = 0.0065 / 2.0  # a three-character value, measured on 5637ac42
    edge = center - half_span * drawing._S / 2.0
    assert edge + 0.002 <= text_x - half_width
    assert text_x + half_width <= center - 0.002


def test_foot_tap_z_value_clears_both_witnesses() -> None:
    """The vertical station's value sits mid-span, off the tap's witness line."""
    text_y = drawing.BOTTOM_KEEP["FootTapZ"][1]
    half_height = 0.0019  # cap height ~3.8 mm on 5637ac42
    tap_y = drawing.BOTTOM_CENTER[1]
    edge_y = tap_y + part.BLOCK_Z * drawing._S / 2.0
    assert tap_y + 0.002 <= text_y - half_height
    assert text_y + half_height <= edge_y - 0.002


def test_pinch_depth_dimension_line_stands_off_the_block_top() -> None:
    """At +0.003 the 6.0's dimension line printed on the block's top edge."""
    top = drawing._elevation_y(part.BLOCK_HEIGHT, drawing.RIGHT_CENTER)
    assert drawing.RIGHT_KEEP["PinchDepthCenter"][1] - top == pytest.approx(
        drawing.BOTTOM_KEEP["FootTapX"][1]
        - (drawing.BOTTOM_CENTER[1] + part.BLOCK_Z * drawing._S / 2.0)
    )
