"""Offline contracts for the oblique trammel's HUB locator pin (MHA-CH-06-TL-25)."""

from __future__ import annotations

import inspect
import re

import pytest

import _config
import _drawing_contract
import ch_rocker_arm_spec as rocker
import ch_rocker_arm_tl_oblique_hub_pin_spec as spec
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import draw_ch_rocker_arm_tl_oblique_hub_pin as drawing
import export_features
from _printed_limits import limits
from _printed_tolerance import printed_band_mm
from prechips.model import TOLERANCE_REQUIREMENTS

STEM = "ch_rocker_arm_tl_oblique_hub_pin"
DASHED = "ch-rocker-arm-tl-oblique-hub-pin"


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def test_every_marked_dimension_prints_once() -> None:
    assert set(drawing.PROFILE_KEEP) == set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(spec.DRAWING_PRECISION_BY_NAME) == set(drawing.PROFILE_KEEP)
    assert set(spec.DIMENSION_CALLOUTS) <= set(drawing.PROFILE_KEEP)


def test_every_exported_band_is_a_requirement() -> None:
    for name, feature in _features().items():
        for key, value in feature.items():
            if key in TOLERANCE_REQUIREMENTS and isinstance(value, list):
                assert key in feature["requirements"], (name, key)


def test_fit_bands_are_p6_and_g6_on_10_20() -> None:
    features = _features()
    assert features["press_seat"]["dia"] == [10.218, 10.229]
    assert features["strap_locator"]["dia"] == [10.183, 10.194]
    assert features["press_seat"]["dia"] == limits(spec.FIT_DIA, 3, spec.SEAT_BAND)
    assert features["strap_locator"]["dia"] == limits(
        spec.FIT_DIA, 3, spec.LOCATOR_BAND
    )


def test_sections_are_modelled_at_their_low_limits() -> None:
    """The pivot pin's convention: each fit section at its low limit printed
    +0.011/0, so the two are distinct faces with a real step at the seat top."""
    assert (spec.SEAT_DIA, spec.SEAT_PRINT_BAND) == (10.218, (0.011, 0.0))
    assert (spec.LOCATOR_DIA, spec.LOCATOR_PRINT_BAND) == (10.183, (0.011, 0.0))
    features = _features()
    assert features["press_seat"]["dia_nominal"] == spec.SEAT_DIA
    assert features["strap_locator"]["dia_nominal"] == spec.LOCATOR_DIA
    assert spec.SEAT_DIA > spec.LOCATOR_DIA + spec.LOCATOR_PRINT_BAND[0]
    assert set(spec.DRAWING_DIMENSIONS) == {"PinProfile", "HeadFillet"}
    build_source = inspect.getsource(
        __import__("build_ch_rocker_arm_tl_oblique_hub_pin")
    )
    assert "*deviations(SEAT_PRINT_BAND)" in build_source
    assert "*deviations(LOCATOR_PRINT_BAND)" in build_source
    assert "LocatorProfile" not in build_source


def test_matched_fit_callouts_name_their_mates() -> None:
    assert spec.SEAT_CALLOUT.splitlines()[0] == "0.000-0.029 DIAMETRAL"
    assert spec.SEAT_CALLOUT.endswith("MHA-CH-06-TL-21 HUB HOLE")
    assert spec.LOCATOR_CALLOUT.splitlines()[0] == "0.006-0.035 DIAMETRAL"
    assert spec.LOCATOR_CALLOUT.endswith("MHA-CH-13 STRAP HOLE")
    for text in spec.DIMENSION_CALLOUTS.values():
        for line in text.splitlines():
            assert len(line) <= 30, line
    source = inspect.getsource(drawing)
    assert 'DIMENSION_CALLOUTS, location="below"' in source


def test_sections_follow_the_jig_stack() -> None:
    assert (spec.HEAD_DIA, spec.HEAD_LENGTH) == (16.0, 4.0)
    assert spec.SEAT_LENGTH == trammel.CARRIER_THICK == 12.0
    assert spec.LOCATOR_LENGTH == trammel.RISER_THICK + rocker.ARM_THICKNESS - 0.5
    assert spec.LOCATOR_LENGTH == 8.0
    assert spec.OVERALL_LENGTH == 24.0
    assert spec.FIT_DIA + spec.SEAT_BAND[0] < spec.RISER_HUB_CLEARANCE_DIA
    assert spec.HEAD_DIA < spec.STOCK_DIA


def test_number_and_quantity() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts(DASHED)["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)
    assert number == "MHA-CH-06-TL-25"
    assert _config.parts(DASHED)["quantity"] == 1
    finish = _config.parts(DASHED)["finish"]
    assert "\n" not in finish and len(finish) <= 40


def test_sheet_carries_no_notes() -> None:
    assert spec.DRAWING_NOTES == ""
    assert '"Manufacturing Notes"' not in inspect.getsource(drawing)


def test_lengths_read_like_the_lathe() -> None:
    """Rule 11 (machinist review r2): the head thickness and the press seat
    are a baseline from the seating face, the locator is the remainder, and
    the overall prints as the faced-to-fit reference."""
    printed = spec.DRAWING_PRECISION_BY_NAME
    assert {"PinLength", "HeadLength", "SeatLength"} <= set(printed)
    assert "LocatorLength" not in printed
    features = _features()
    for name, nominal, origin in (
        ("head_bottom", spec.HEAD_LENGTH, "seating_face"),
        ("seat_end", spec.SEAT_LENGTH, "seating_face"),
    ):
        feature = features[name]
        assert feature["height_from"] == origin, name
        assert feature["station_nominal"] == nominal, name
        assert feature["station"] == limits(nominal, spec.LENGTH_PLACES), name
    assert features["seating_face"]["requirements"] == []
    top = features["top_face"]
    assert top["requirements"] == [] and "station" not in top
    assert top["station_nominal"] == spec.OVERALL_LENGTH
    assert top["note"] == spec.PIN_LENGTH_NOTE
    build_source = inspect.getsource(
        __import__("build_ch_rocker_arm_tl_oblique_hub_pin")
    )
    assert 'f"{head_top}.start",\n        f"{head_bottom}.end"' in build_source
    assert 'f"{head_top}.start",\n        f"{step}.start"' in build_source


def test_top_is_faced_to_fit_over_the_stack() -> None:
    """Codex (#1582): head, carrier and riser at their bands would put the
    locator's top anywhere in 2.0 ± 2.4 above the riser against a 2.5 strap;
    rule 19 faces it to fit in place instead."""
    band = printed_band_mm(1)
    low = (spec.OVERALL_LENGTH - band) - (spec.HEAD_LENGTH + band)
    low -= (trammel.CARRIER_THICK + band) + trammel.RISER_THICK + band
    assert low - spec.LEAD_CHAMFER < 0.0  # a turned-to-print pin can miss the strap
    assert (spec.LOCATOR_SET_MIN, spec.LOCATOR_SET_MAX) == (1.8, 2.2)
    assert spec.LOCATOR_SET_ABOVE_RISER == spec.LOCATOR_LENGTH - trammel.RISER_THICK
    assert spec.LOCATOR_SET_MAX < rocker.ARM_THICKNESS + rocker.ARM_THICKNESS_BAND[1]
    assert spec.LOCATOR_SET_MIN - spec.LEAD_CHAMFER >= spec.STRAP_ENGAGEMENT_MIN
    # The shortest supply still faces clean at the tallest stack.
    tallest = (spec.HEAD_LENGTH + band) + (trammel.CARRIER_THICK + band)
    tallest += trammel.RISER_THICK + band + spec.LOCATOR_SET_MAX
    assert spec.SUPPLY_LENGTH_MIN == pytest.approx(tallest + spec.FACING_ALLOWANCE)
    assert spec.SUPPLY_LENGTH_MIN == pytest.approx(26.8)
    # Stacked under the overall's value (close-c3-r3): below, since SOLIDWORKS
    # drops a multi-line callout above a value (jig-r12).
    assert spec.PIN_LENGTH_CALLOUT.splitlines() == [
        "SUPPLY 26.8 MIN;",
        "FACE LOCATOR END AT ASSEMBLY",
        "1.80-2.20 ABOVE MHA-CH-06-TL-24;",
        "RECUT LEAD CHAMFER",
    ]
    assert spec.REFERENCE_CALLOUTS == {"PinLength": spec.PIN_LENGTH_CALLOUT}
    assert "PinLength" not in spec.DIMENSION_CALLOUTS
    source = inspect.getsource(drawing)
    assert 'REFERENCE_CALLOUTS, location="below"' in source
    # The fit-up rows sit inside the overall's extension lines (~2.5 mm a
    # character at this font, 4:1).
    widest = max(len(row) for row in spec.PIN_LENGTH_CALLOUT.splitlines())
    span = drawing.side_view_x(0.0) - drawing.side_view_x(spec.OVERALL_LENGTH)
    assert widest * 0.0025 < span - 0.008
    assert "set_reference_dimension(" in source


def test_head_fillet_is_a_max_radius_inside_the_hub_hole_break() -> None:
    """Rule 16 (machinist review r2): the seat-to-head corner prints R0.2 MAX,
    the model carrying the printed maximum. The title block sets no minimum
    break (Codex, #1582), so the HUB hole's underside break is a stated
    minimum the fillet fits inside."""
    assert spec.SHOULDER_FILLET_RADIUS == 0.2
    assert spec.RADIUS_TOL_TYPE == 6  # swTolType_e.swTolMAX
    assert spec.DRAWING_DIMENSIONS["HeadFillet"] == {"HeadFilletR"}
    assert spec.SHOULDER_FILLET_RADIUS <= spec.HUB_HOLE_UNDERSIDE_BREAK_MIN
    assert "sets no\nminimum break" in spec.__doc__
    build_source = inspect.getsource(
        __import__("build_ch_rocker_arm_tl_oblique_hub_pin")
    )
    assert "[[0.0, SEAT_R, HEAD_LENGTH]]" in build_source
    assert '_max_limit(adapter, "HeadFillet", "HeadFilletR")' in build_source
    # Codex #1582: the lead chamfer is a MAX too, so the faced locator keeps
    # its strap engagement at the printed limit.
    assert '_max_limit(adapter, "PinProfile", "LeadChamfer")' in build_source


# Sheet ink as run 20261017T022004769Z printed it (sheet mm), the pivot pin's
# calibration from the same run.
_CHAR_MM = 2.52
_BLOCK_HALF = 12.85  # a four-line fit block about its position's y
_RADIUS_TEXT = 24.3
_RADIUS_KNEE = 13.7
_AIR = 1.78
_LINE_BELOW_TEXT = 2.8  # a length's dimension line under its text position
_CHAMFER_EXT_BELOW = 4.6  # a chamfer's extension lines end under its position
_CHAMFER_TEXT = 48.0 * 27 / 22  # "0.5 max. X 45° LEAD CHAMFER"


def _mm(xy: tuple[float, float]) -> tuple[float, float]:
    return xy[0] * 1000.0, xy[1] * 1000.0


def test_head_radius_keeps_clear_below_the_view() -> None:
    """The radius text sits under the press seat, clear of the seat diameter's
    line and block, its shoulder and knee short of the head face."""
    keep = {name: _mm(xy) for name, xy in drawing.PROFILE_KEEP.items()}
    x, y = keep["HeadFilletR"]
    box = (x - _RADIUS_TEXT / 2.0, y - 1.8, x + _RADIUS_TEXT / 2.0, y + 1.7)
    knee = x + _RADIUS_KNEE  # the corner is right of the text (+Z runs left)
    corner_x = drawing.side_view_x(spec.HEAD_LENGTH) * 1000.0
    seat_bottom = (
        drawing.PROFILE_CENTER[1] - spec.SEAT_DIA / 2.0 * drawing._S
    ) * 1000.0
    assert knee < corner_x - _AIR
    assert box[3] < seat_bottom - _AIR
    assert y - _LINE_BELOW_TEXT > drawing._BELOW * 1000.0  # over the head's outline
    seat_x, seat_y = keep["SeatDia"]
    seat_width = _CHAR_MM * max(len(line) for line in spec.SEAT_CALLOUT.splitlines())
    assert box[0] - seat_x >= _AIR  # the seat diameter's line
    assert box[1] - (seat_y + _BLOCK_HALF) >= _AIR  # the seat's fit block
    assert seat_x + seat_width < keep["HeadDia"][0]  # under the Ø16's line
    locator_x = keep["LocatorDia"][0]
    assert not knee - _RADIUS_TEXT - 1.5 <= locator_x <= knee


def test_lengths_and_chamfer_keep_clear_above_the_view() -> None:
    """The baseline row sits nearest the part, the overall above it; the
    chamfer's extension lines end under the overall's line and its callout
    stays outboard of the overall's extension line at the top face."""
    keep = {name: _mm(xy) for name, xy in drawing.PROFILE_KEEP.items()}
    above = drawing._ABOVE * 1000.0
    head_y, seat_y, overall_y = (
        keep[n][1] for n in ("HeadLength", "SeatLength", "PinLength")
    )
    assert above < head_y == seat_y < overall_y
    overall_line = overall_y - _LINE_BELOW_TEXT
    assert overall_line - (seat_y + 2.0) >= _AIR  # over the baseline text
    chamfer_x, chamfer_y = keep["LeadChamfer"]
    locator_top = (
        drawing.PROFILE_CENTER[1] + spec.LOCATOR_DIA / 2.0 * drawing._S
    ) * 1000.0
    assert chamfer_y - _CHAMFER_EXT_BELOW > locator_top + _AIR  # above the part
    assert chamfer_y + 5.0 < overall_line - _AIR  # the block under the overall
    top_x = drawing.side_view_x(spec.OVERALL_LENGTH) * 1000.0
    assert chamfer_x + _CHAMFER_TEXT / 2.0 < top_x - _AIR
    # The baseline dims stand over the head and seat only, right of the
    # chamfer block.
    seat_end_x = drawing.side_view_x(spec.SEAT_STATION) * 1000.0
    assert chamfer_x + _CHAMFER_TEXT / 2.0 < seat_end_x


def test_drawing_script_meets_the_drawing_contract() -> None:
    filename = f"draw_{STEM}.py"
    assert filename in _drawing_contract.PRECISION_MIGRATED_DRAWINGS
    violations = _drawing_contract.drawing_specification_violations(
        inspect.getsource(drawing), filename=filename
    )
    assert not violations, violations
