"""SolidWorks-free contracts for MHA-DT-38, the cone tip bushing."""

from __future__ import annotations

import math

import pytest

import _config
import cone_tip_cluster as tip
import dt_cone_tip_bushing_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _inch_wall_limits import WALL_TARGET_MM
from _machinist_review_mode import MachinistReviewMode

IN = 25.4


def test_registry_row_is_the_turned_brass_bushing() -> None:
    row = _config.parts(spec.PART_NAME)
    assert row["number"] == "MHA-DT-38"
    assert row["material_specification"] == "C36000 free-machining brass"
    assert row["quantity"] == 1
    assert row["drawing_unit"] == spec.UNIT == "in"
    assert "ream the bore" in row["process"]
    assert "machinist_exceptions" not in row


def test_mates_are_named_by_their_registered_numbers() -> None:
    assert _config.parts("dt-cone-tip-gear")["number"] == spec.PIVOT_NUMBER
    assert _config.parts("dt-cone-tip-end-screw")["number"] == spec.END_SCREW_NUMBER


def test_sizes_are_the_tip_cluster_contract() -> None:
    assert spec.OUTER_DIA == pytest.approx(0.228 * IN)
    assert spec.LENGTH == pytest.approx(0.160 * IN)
    assert spec.BORE_DIA == pytest.approx(0.0615 * IN)
    assert spec.BORE_DIA_BAND == tip.REAM_H7 == (0.0127, 0.0)


def test_press_on_the_pivot_interferes_at_every_limit() -> None:
    bore = (spec.BORE_DIA, spec.BORE_DIA + max(spec.BORE_DIA_BAND))
    pivot = (
        tip.STEM_DIA_MM + min(tip.PIVOT_DIA_BAND),
        tip.STEM_DIA_MM + max(tip.PIVOT_DIA_BAND),
    )
    least, most = pivot[0] - bore[1], pivot[1] - bore[0]
    assert least > 0.0
    assert spec.PRESS_INTERFERENCE == pytest.approx((least, most))
    assert least / IN == pytest.approx(0.0002)
    assert most / IN == pytest.approx(0.0010)


def test_wall_holds_the_rule_17_target_at_the_worst_case() -> None:
    worst = (spec.OUTER_DIA - 0.005 * IN - (spec.BORE_DIA + 0.0005 * IN)) / 2.0
    assert spec.WALL_WORST == pytest.approx(worst)
    assert spec.WALL_WORST >= WALL_TARGET_MM


def test_bore_callout_names_process_fit_mate_and_interference() -> None:
    assert spec.BORE_CALLOUT.splitlines() == [
        "REAM THRU",
        "PRESS FIT ON MHA-DT-37 PIVOT",
        "(INTERFERENCE .0002-.0010 REF)",
    ]


def test_every_marked_dimension_has_places() -> None:
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "OuterDia": 3,
        "BoreDia": 4,
        "Length": 3,
        "EndChamferSize": 2,
    }


def test_builder_volume_is_the_annulus_less_both_corner_breaks() -> None:
    import build_dt_cone_tip_bushing as build

    ring = math.pi / 4.0 * (spec.OUTER_DIA**2 - spec.BORE_DIA**2) * spec.LENGTH
    assert build.V_RING == pytest.approx(ring)
    # Pappus: each 45 deg triangle of leg c, centroid c/3 inside the O.D.
    c = spec.END_CHAMFER
    one_break = c * c / 2.0 * 2.0 * math.pi * (spec.OUTER_DIA / 2.0 - c / 3.0)
    assert build.V_BUSHING == pytest.approx(ring - 2.0 * one_break)


def test_corner_breaks_leave_a_flat_seat_and_give_the_tip_its_air() -> None:
    """#2697: the .04 x 45 deg break on both O.D. corners prints .XX; at its
    largest each face keeps a flat round the bore, and at its smallest the
    cone tip's air to G19 books it (a square corner stands nearer the bank)."""
    import dataclasses

    import dt_cone_tip_air as air

    assert spec.END_CHAMFER == pytest.approx(0.04 * IN)
    assert spec.END_CHAMFER_MIN == pytest.approx(0.03 * IN)
    assert spec.FACE_FLAT_MIN >= 0.5
    bushing = next(tier for tier in air.TIERS if tier.name == "bushing")
    assert bushing.south_chamfer_mm == spec.END_CHAMFER_MIN
    fixed = air.DRUM_TIERS[0]
    chamfered = air.projection_nominal_mm("bushing", fixed)
    square = dataclasses.replace(bushing, south_chamfer_mm=0.0)
    tiers = tuple(square if tier is bushing else tier for tier in air.TIERS)
    original = air.TIERS
    air.TIERS = tiers
    try:
        assert chamfered > air.projection_nominal_mm("bushing", fixed) + 0.1
    finally:
        air.TIERS = original


def test_sheet_is_registered_and_enforced() -> None:
    import draw_dt_cone_tip_bushing as drawing

    sheet = DRAWINGS_BY_NAME["dt_cone_tip_bushing"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.artifact_stem == spec.PART_NAME
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
    assert set(drawing.SECTION_KEEP) == set(spec.DRAWING_PRECISION_BY_NAME)


def test_three_place_od_and_length_state_their_function() -> None:
    # Rule 3: a three-place size states the wall it holds or the stack it
    # sets; both specs refuse the .XX band they replace.
    assert spec.OUTER_DIA_CALLOUT == "HOLDS WALL .080 MIN"
    assert spec.LENGTH_CALLOUT.splitlines() == [
        "MHA-DT-37 PIVOT CLEARS",
        "MHA-DT-39 HOLE FLOOR",
    ]


def test_bore_block_stands_clear_of_its_extension_lines() -> None:
    import draw_dt_cone_tip_bushing as drawing

    # Farm run 20261110T001845485Z: the bore's extension lines ran through
    # its callout rows, and the 8:1 section caption repeated the sheet scale.
    _x, y = drawing.SECTION_KEEP["BoreDia"]
    assert (
        y + drawing._BORE_BLOCK_BELOW_KEEP > drawing.SECTION_CENTER[1] + drawing.BORE_R
    )
    assert drawing.SHEET_SCALE == (5.0, 1.0)
    assert tuple(spec.ISOMETRIC_VIEW_SCALE) != drawing.VIEW_SCALE
    # Round 2 (farm run 20261110T035403233Z): the "above" lane never printed
    # the length's stack rows; every callout rides the "below" lane, and the
    # length's block stands right of the north face, under the section.
    assert drawing.DIMENSION_CALLOUTS == {
        "BoreDia": spec.BORE_CALLOUT,
        "OuterDia": spec.OUTER_DIA_CALLOUT,
        "Length": spec.LENGTH_CALLOUT,
        "EndChamferSize": spec.END_CHAMFER_CALLOUT,
    }
    # #2697: the chamfer's text stands right of both its extension lines and
    # its rows above the bore's block.
    chamfer_x, chamfer_y = drawing.SECTION_KEEP["EndChamferSize"]
    south_x = drawing.SECTION_CENTER[0] - drawing.HALF_LENGTH
    assert chamfer_x > south_x + spec.END_CHAMFER * drawing._S
    assert chamfer_y - 2.0 * drawing._ROW > y
    length_x, length_y = drawing.SECTION_KEEP["Length"]
    assert length_x > drawing.NORTH_FACE_X + 0.03
    assert length_y < drawing.SECTION_CENTER[1] - drawing.OUTER_R


def test_section_caption_drops_only_its_scale_line() -> None:
    import draw_dt_cone_tip_bushing as drawing

    linked = "<VLNAME> <VLLABEL>\r\n<VLSCALE> <VLSCALEV>"
    assert drawing.caption_without_scale(linked) == "<VLNAME> <VLLABEL>"
    with pytest.raises(RuntimeError):
        drawing.caption_without_scale("<VLNAME>\n<VLLABEL>\n<VLSCALEV>")
