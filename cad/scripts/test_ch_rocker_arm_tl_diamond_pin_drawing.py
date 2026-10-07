"""Offline contracts for the rocker rod diamond pin (MHA-CH-006-TL-03)."""

from __future__ import annotations

import re

import _config
import _hole_spec
import ch_rocker_arm_spec as rocker
import ch_rocker_arm_tl_diamond_pin_spec as spec
import draw_ch_rocker_arm_tl_diamond_pin as drawing
import export_features

STEM = "ch_rocker_arm_tl_diamond_pin"


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    views = (drawing.AXIAL_XY, drawing.DIAMETER_XY, drawing.END_KEEP)
    assert set().union(*map(set, views)) == marked
    assert sum(len(view) for view in views) == len(marked)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    # every body size lands on the section; only the pin sizes stay on the end view
    assert set(drawing.END_KEEP) == {"LandDia", "FlatsAF"}


def test_lands_enter_every_rod_pin_hole_the_rocker_prints() -> None:
    lands = _features()["lands"]["dia"]
    smallest_hole = _hole_spec.blind_cut_dia_mm(rocker.ROD_HOLE_SPEC) - float(
        _config.title_block("drilled_hole")["minus_mm"]
    )
    assert smallest_hole - lands[1] >= spec.LAND_CLEARANCE_MIN
    # the bought Class X 0.0782 in plus pin: 0.07820-0.07824 in
    assert lands == [round(0.07820 * 25.4, 4), round(0.07824 * 25.4, 4)]


def test_flats_stay_inside_the_lands_at_every_printed_size() -> None:
    lands = _features()["lands"]
    assert lands["width"][1] < lands["dia"][0]


def test_tip_stays_in_the_strap_and_neck_face_never_lifts_the_arm() -> None:
    height = _features()["lands"]["height"]
    neck = _features()["neck_face"]["height"]
    assert neck[1] <= spec.FACE_B_ABOVE_PLATE
    assert height[1] - (spec.FACE_B_ABOVE_PLATE - neck[1]) <= rocker.ARM_THICKNESS
    assert height[0] - (spec.FACE_B_ABOVE_PLATE - neck[0]) >= rocker.ARM_THICKNESS / 2.0


def test_shank_slips_into_the_fixture_ream_with_a_bondable_gap() -> None:
    low, high = _features()["shank"]["dia"]
    # profile-fixture pin hole 3.000-3.010; Loctite 638 fills to 0.25 mm gap,
    # but the pin must still locate: keep the diametral gap within 0.03.
    assert high < 3.000
    assert 3.010 - low <= 0.030


def test_construction_is_built_up_from_the_printed_note() -> None:
    assert export_features.requirement_manifest(STEM)["construction"] == "built_up_permitted"
    assert spec.BUILT_UP_PERMISSION_NOTE in spec.DRAWING_NOTES


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-diamond-pin")["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)
    assert number == "MHA-CH-006-TL-03"


def test_notes_follow_the_simplicity_policy() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert not re.search(r"\d", spec.DRAWING_NOTES)
    assert "GROUND" not in spec.DRAWING_NOTES
