"""Offline contracts for the rocker template trammel pivot plate (MHA-CH-006-TL-19)."""

from __future__ import annotations

import math
import re

import _config
import ch_rocker_arm_tl_trammel_pivot_plate_spec as spec
import ch_rocker_arm_tl_trammel_spec as kit
import draw_ch_rocker_arm_tl_trammel_pivot_plate as drawing
import export_features

STEM = "ch_rocker_arm_tl_trammel_pivot_plate"


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.TOP_KEEP) | set(drawing.SECTION_KEEP) == marked
    assert not set(drawing.TOP_KEEP) & set(drawing.SECTION_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert {name for _feature, name in spec.DRILLED_DIMENSIONS} <= marked
    assert set(spec.CALLOUTS_ABOVE) | set(spec.CALLOUTS_BELOW) <= marked


def test_plate_is_the_block_bar_offcut() -> None:
    assert (spec.PLATE_LENGTH, spec.PLATE_WIDTH, spec.PLATE_HEIGHT) == (
        kit.BLOCK_LENGTH,
        kit.BLOCK_WIDTH,
        kit.BLOCK_HEIGHT,
    )


def test_seat_matches_the_pivot_point_and_the_centre_drill() -> None:
    seat = _features()["pivot_seat"]
    assert spec.SEAT_ANGLE == kit.CENTER_DRILL_ANGLE == kit.PIVOT_TIP_ANGLE
    # The sheet prints the face-to-flank angle: 90 - half the included.
    assert seat["angle_deg"] == 60.0
    assert seat["angle_tol_deg"] == 2.0
    assert math.isclose(90.0 - spec.SEAT_ANGLE / 2.0, spec.SEAT_FLANK_ANGLE)
    assert spec.CALLOUTS_BELOW["SeatDia"].endswith("MHA-CH-006-TL-18 PIVOT POINT")
    pilot = _features()["seat_pilot"]
    assert pilot["dia"] == [1.98, 2.08]
    assert abs(pilot["dia_nominal"] - kit.CENTER_DRILL_PILOT_DIA) < 0.005


def test_sharp_pivot_tip_clears_the_shallowest_pilot_floor() -> None:
    seat, pilot = _features()["pivot_seat"], _features()["seat_pilot"]
    sharpest_half = math.radians((seat["angle_deg"] - seat["angle_tol_deg"]) / 2.0)
    deepest_apex = seat["dia"][1] / 2.0 / math.tan(sharpest_half)
    assert deepest_apex < pilot["depth"][0]
    # A flank remains between the largest pilot and the smallest mouth.
    assert seat["dia"][0] > pilot["dia"][1]


def test_walls_hold_rule_17_at_worst_case() -> None:
    assert min(spec.WALLS_MM.values()) >= 2.0
    features = _features()
    left, right = features["screw_hole_left"], features["screw_hole_right"]
    csk_r = features["screw_hole_left_countersink"]["dia"][1] / 2.0
    seat_r = features["pivot_seat"]["dia"][1] / 2.0
    length_min = features["seat_face"]["length"][0]
    seat_x = features["seat_pilot"]["station"]
    assert left["station"][0] - csk_r >= 2.0
    assert length_min - right["station"][1] - csk_r >= 2.0
    assert seat_x[0] - seat_r - (left["station"][1] + csk_r) >= 2.0
    assert right["station"][0] - csk_r - (seat_x[1] + seat_r) >= 2.0


def test_wood_screws_hold_rule_18_and_sink_their_heads() -> None:
    assert spec.HEAD_TOP_DEPTH_MIN >= 0.0
    assert spec.SCREW_FULL_THREAD_MIN >= 1.5 * spec.SCREW_BODY_DIA
    assert spec.SCREW_IN_BOARD_MAX < spec.BOARD_THICKNESS
    assert _features()["screw_hole_left"]["dia"][0] > spec.SCREW_BODY_DIA


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-trammel-pivot-plate")["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)
    assert number == "MHA-CH-006-TL-19"


def test_notes_follow_the_simplicity_policy() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert not re.search(r"\d", spec.DRAWING_NOTES)
    assert not re.search(r"DRILL|COUNTERSINK|SAW|MILL|REAM", spec.DRAWING_NOTES.upper())


def test_every_exported_band_endpoint_is_a_printed_value() -> None:
    """One fact: a band applied to an unrounded model nominal exports limits
    the sheet never prints."""
    checked = 0
    for name, feature in _features().items():
        for requirement in feature["requirements"]:
            band = feature.get(requirement)
            if not (isinstance(band, list) and len(band) == 2):
                continue
            places = feature["precision"][requirement]
            for end in band:
                assert abs(end - round(end, places)) < 1e-9, (
                    name,
                    requirement,
                    band,
                    places,
                )
            nominal = feature.get(f"{requirement}_nominal")
            if nominal is not None:
                assert band[0] <= nominal <= band[1], (name, requirement, nominal, band)
                assert abs(nominal - round(nominal, places)) < 1e-9, (
                    name,
                    requirement,
                    nominal,
                )
            checked += 1
    assert checked


def test_prechips_solids_are_valid_fixture_solids() -> None:
    from prechips.model import FixtureSolid

    for solid in spec.PRECHIPS_SOLIDS:
        FixtureSolid.model_validate(solid)
    names = {solid["name"] for solid in spec.PRECHIPS_SOLIDS}
    assert {"pivot plate", "seat pilot", "screw hole 1", "screw hole 2"} == names
    for solid in spec.PRECHIPS_SOLIDS:
        if solid.get("void"):
            assert solid["cuts"] == ["pivot plate"]
