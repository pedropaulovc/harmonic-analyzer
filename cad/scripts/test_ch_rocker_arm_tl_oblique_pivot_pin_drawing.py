"""Offline contracts for the oblique trammel's pivot pin (MHA-CH-06-TL-23)."""

from __future__ import annotations

import inspect
import re

import pytest

import _config
import _drawing_contract
import ch_rocker_arm_tl_oblique_pivot_block_spec as block
import ch_rocker_arm_tl_oblique_pivot_pin_spec as spec
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import draw_ch_rocker_arm_tl_oblique_pivot_pin as drawing
import export_features
from _fit_deviations import deviations
from _printed_limits import limits
from prechips.model import TOLERANCE_REQUIREMENTS

STEM = "ch_rocker_arm_tl_oblique_pivot_pin"
DASHED = "ch-rocker-arm-tl-oblique-pivot-pin"


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def test_section_lengths_derive_from_the_bearing_and_collar_constants() -> None:
    assert spec.BEARING_LENGTH == (
        trammel.BEARINGS_PER_PIN * trammel.BEARING_WIDTH + trammel.BEARING_SHOULDER
    )
    assert spec.BEARING_LENGTH == 22.0
    assert spec.COLLAR_HEIGHT == trammel.PIN_COLLAR_HEIGHT == 4.0
    assert spec.COLLAR_HEIGHT == trammel.BEARING_RECESS + trammel.PIN_COLLAR_PROUD
    assert spec.CARRIER_LENGTH == trammel.CARRIER_THICK - spec.CARRIER_TOP_SHORTFALL
    assert spec.CARRIER_LENGTH == 11.0 < trammel.CARRIER_THICK
    assert spec.OVERALL_LENGTH == (
        spec.BEARING_LENGTH + spec.COLLAR_HEIGHT + spec.CARRIER_LENGTH
    )
    assert spec.OVERALL_LENGTH == 37.0
    assert spec.TOP_TO_COLLAR_SEAT == spec.COLLAR_HEIGHT + spec.CARRIER_LENGTH
    assert spec.FIT_DIA == trammel.BEARING_BORE


def test_fit_limits_match_the_printed_callouts() -> None:
    k5_low, k5_high = (spec.FIT_DIA + d for d in deviations(spec.BEARING_BAND))
    h6_low, h6_high = (spec.FIT_DIA + d for d in deviations(spec.CARRIER_BAND))
    assert (round(k5_low, 6), round(k5_high, 6)) == (10.001, 10.007)
    assert (round(h6_low, 6), round(h6_high, 6)) == (9.991, 10.0)
    race_low, race_high = (spec.FIT_DIA + d for d in deviations(spec.RACE_BORE_BAND))
    hole_low, hole_high = (spec.FIT_DIA + d for d in deviations(spec.PIN_HOLE_BAND))
    interference = (round(k5_low - race_high, 6), round(k5_high - race_low, 6))
    clearance = (round(hole_low - h6_high, 6), round(hole_high - h6_low, 6))
    assert interference == (0.001, 0.015)
    assert clearance == (0.0, 0.024)
    assert spec.BEARING_NOTE == (
        f"{interference[0]:.3f}-{interference[1]:.3f} DIAMETRAL INTERFERENCE ON "
        "6200-2RS INNER RACE"
    )
    assert spec.CARRIER_NOTE.startswith(
        f"{clearance[0]:.3f}-{clearance[1]:.3f} DIAMETRAL CLEARANCE ON "
        "MHA-CH-06-TL-21 PIN HOLES"
    )
    assert spec.DIMENSION_CALLOUTS["BearingDia"] == spec.BEARING_CALLOUT
    assert spec.DIMENSION_CALLOUTS["CarrierDia"] == spec.CARRIER_CALLOUT
    printed = limits(spec.BEARING_DIA, spec.FIT_PLACES, spec.BEARING_PRINT_BAND)
    assert printed == [round(k5_low, 12), round(k5_high, 12)]
    build_source = inspect.getsource(
        __import__("build_ch_rocker_arm_tl_oblique_pivot_pin")
    )
    assert "*deviations(BEARING_PRINT_BAND)" in build_source
    assert "*deviations(CARRIER_BAND)" in build_source


def _mounted_clearance(shaft_interference: float, seat_interference: float) -> float:
    """C3 minimum less NTN's conservative take-up: 70 % of the shaft's
    interference after 7 µm smoothing, 60 % of the seat's."""
    shaft_loss = 0.7 * max(shaft_interference - 0.007, 0.0)
    return trammel.BEARING_RADIAL_PLAY[0] - shaft_loss - 0.6 * seat_interference


def test_presses_leave_the_pivot_free() -> None:
    """Codex (#1578), Main ruling 4: p6 with the N6 seat could preload the
    6200s by 24 µm at their tightest; k5 leaves play at mid-limits and at
    worst a light 12 µm preload."""
    seat = (block.INTERFERENCE_MIN, block.INTERFERENCE_MAX)
    assert seat == (0.002, 0.024)
    shaft = (spec.BEARING_INTERFERENCE_MIN, spec.BEARING_INTERFERENCE_MAX)
    worst = _mounted_clearance(shaft[1], seat[1])
    assert worst == pytest.approx(-0.012, abs=1e-6)
    middle = _mounted_clearance(sum(shaft) / 2.0, sum(seat) / 2.0)
    middle += sum(trammel.BEARING_RADIAL_PLAY) / 2.0 - trammel.BEARING_RADIAL_PLAY[0]
    assert middle > 0.0
    assert _mounted_clearance(0.032, seat[1]) == pytest.approx(-0.0239, abs=1e-6)


def test_mounted_play_stays_inside_the_calculator_bound() -> None:
    # Main ruling 4: the calculator's 0.041 on R is the unmounted bound; at
    # the presses' loosest limits the seat takes 0.0012 off (0.039 on R).
    seat_min = block.INTERFERENCE_MIN
    shaft_min = spec.BEARING_INTERFERENCE_MIN
    loosest = _mounted_clearance(shaft_min, seat_min) + (
        trammel.BEARING_RADIAL_PLAY[1] - trammel.BEARING_RADIAL_PLAY[0]
    )
    assert loosest == pytest.approx(0.0218, abs=1e-6)
    assert loosest <= trammel.BEARING_RADIAL_PLAY[1]
    radius = trammel.RADIUS_PER_SPACING * loosest
    assert f"{radius:.3f}" == "0.039"
    assert radius <= trammel.RADIUS_FROM_BEARING_PLAY


def test_collar_seats_on_the_inner_race_only() -> None:
    # Codex (#1578): at one place the Ø12.5 could go to 11.7, under the
    # abutment; the bar's own Ø12.70 at two places holds 12.19.
    assert spec.COLLAR_DIA == spec.STOCK_DIA and spec.COLLAR_PLACES == 2
    assert spec.BEARING_DA_MIN <= spec.COLLAR_DIA - 0.51
    assert spec.BEARING_DA_MIN <= spec.STOCK_DIA_MIN
    assert spec.SHOULDER_FILLET_RADIUS < spec.BEARING_BORE_CHAMFER_MIN


def test_every_marked_dimension_prints_once() -> None:
    assert set(drawing.PROFILE_KEEP) == set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(spec.DRAWING_PRECISION_BY_NAME) == set(drawing.PROFILE_KEEP)
    assert set(spec.DIMENSION_CALLOUTS) <= set(drawing.PROFILE_KEEP)


def test_every_exported_band_is_a_requirement() -> None:
    for name, feature in _features().items():
        for key, value in feature.items():
            if key in TOLERANCE_REQUIREMENTS and isinstance(value, list):
                assert key in feature["requirements"], (name, key)


def test_every_exported_nominal_lies_inside_its_band() -> None:
    for name, feature in _features().items():
        for key, nominal in feature.items():
            if not key.endswith("_nominal"):
                continue
            band = feature.get(key.removesuffix("_nominal"))
            if band is None:
                assert "note" in feature["requirements"], (name, key)
                continue
            low, high = band
            assert low <= nominal <= high, (name, key)


def test_every_printed_band_has_a_requirement_owner() -> None:
    owners = {
        "CarrierLength": ("collar_top", "station", None),
        "CollarSeatStation": ("collar_seat", "station", None),
        "PinLength": ("bottom_face", "station", None),
        "CollarDia": ("collar", "dia", None),
        "BearingDia": ("bearing_section", "dia", spec.BEARING_PRINT_BAND),
        "CarrierDia": ("carrier_section", "dia", spec.CARRIER_BAND),
    }
    exempt = {"BottomChamfer", "TopChamfer", "SeatFilletR", "CarrierFilletR"}
    assert set(owners) | exempt == set(spec.DRAWING_PRECISION_BY_NAME)
    features = _features()
    for printed, (name, key, band) in owners.items():
        feature = features[name]
        assert key in feature["requirements"], printed
        places = spec.DRAWING_PRECISION_BY_NAME[printed]
        nominal = feature[f"{key}_nominal"]
        assert round(nominal, places) == nominal, printed
        assert feature[key] == limits(nominal, places, band), printed
    assert features["bearing_section"]["note"] == spec.BEARING_NOTE
    assert features["carrier_section"]["note"] == spec.CARRIER_NOTE


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts(DASHED)["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)
    assert number == "MHA-CH-06-TL-23"
    assert _config.parts(DASHED)["quantity"] == 2


def test_finish_fits_one_title_block_line() -> None:
    finish = _config.parts(DASHED)["finish"]
    assert "\n" not in finish and len(finish) <= 40, finish


# Below-view geometry as run 20261017T022004769Z printed it (sheet mm).
_CHAR_MM = 2.52  # widest measured: 65.3 mm for 26 characters
_BLOCK_HALF = 12.85  # a four-line fit block about its position's y
_RADIUS_TEXT = 24.3
_RADIUS_KNEE = 13.7
_AIR = 1.78  # the audit's text-clearance air


def _mm(xy: tuple[float, float]) -> tuple[float, float]:
    return xy[0] * 1000.0, xy[1] * 1000.0


def _below_view_ink() -> tuple[dict, dict, dict]:
    """Text boxes (x0, y0, x1, y1), dimension lines (x, y0, y1) and radius
    shoulders (x0, x1, y), each keyed by dimension name."""
    keep = {name: _mm(xy) for name, xy in drawing.PROFILE_KEEP.items()}
    boxes, lines, shoulders = {}, {}, {}
    for name, top in (("BearingDia", 180.0), ("CarrierDia", 180.0)):
        x, y = keep[name]
        width = _CHAR_MM * max(
            len(line) for line in spec.DIMENSION_CALLOUTS[name].splitlines()
        )
        boxes[name] = (x, y - _BLOCK_HALF, x + width, y + _BLOCK_HALF)
        lines[name] = (x, y - _BLOCK_HALF, top)
    x, y = keep["CollarDia"]
    boxes["CollarDia"] = (x, y - 2.8, x + 19.4, y + 1.7)
    lines["CollarDia"] = (x, y - 2.8, 185.0)
    for name, side in (("SeatFilletR", -1.0), ("CarrierFilletR", 1.0)):
        x, y = keep[name]
        boxes[name] = (x - _RADIUS_TEXT / 2.0, y - 1.8, x + _RADIUS_TEXT / 2.0, y + 1.7)
        knee = x + side * _RADIUS_KNEE
        far = knee - side * (_RADIUS_TEXT + 1.5)
        shoulders[name] = (min(knee, far), max(knee, far), y - 2.8)
    return boxes, lines, shoulders


def test_below_view_blocks_keep_clear_of_each_other_and_every_line() -> None:
    """Run 20261017T022004769Z printed the carrier block over the collar's
    Ø12.5; run 20261017T015225029Z crossed the radius shoulders with the
    length extension lines. Every below-view text keeps the audit's air from
    every other, no diameter's dimension line passes through another's text
    or a radius shoulder, and the lengths and chamfers stand above."""
    keep = drawing.PROFILE_KEEP
    for name in ("CarrierLength", "CollarSeatStation", "PinLength"):
        assert keep[name][1] > drawing._ABOVE, name
    for name in ("TopChamfer", "BottomChamfer"):
        assert drawing._ABOVE < keep[name][1] < drawing.ROW_Y[0] - 0.006, name
    rows = [keep[n][1] for n in ("CarrierLength", "CollarSeatStation", "PinLength")]
    assert rows == sorted(rows)

    boxes, lines, shoulders = _below_view_ink()
    names = sorted(boxes)
    for i, a in enumerate(names):
        ax0, ay0, ax1, ay1 = boxes[a]
        assert ay1 < drawing._BELOW * 1000.0, a
        assert ay0 > 90.0, a
        for b in names[i + 1 :]:
            bx0, by0, bx1, by1 = boxes[b]
            gap = max(bx0 - ax1, ax0 - bx1, by0 - ay1, ay0 - by1)
            assert gap >= _AIR, (a, b, gap)
    for owner, (x, y0, y1) in lines.items():
        for name, (bx0, by0, bx1, by1) in boxes.items():
            if name == owner:
                continue
            assert not (bx0 - 0.5 < x < bx1 + 0.5 and y0 < by1 and by0 < y1), (
                owner,
                name,
            )
        for name, (sx0, sx1, sy) in shoulders.items():
            assert not (sx0 - 0.5 < x < sx1 + 0.5 and y0 < sy < y1), (owner, name)


def test_radius_leaders_stay_off_the_collar_and_the_extension_lines() -> None:
    """Each radius knee stands just outside its collar face, toward its own
    section: the seat radius's leader then passes left of where the bearing
    diameter's extension line starts at the collar face (run
    20261017T022004769Z's advisory crossing), and neither knee reaches the
    collar diameter's line between them."""
    _boxes, lines, shoulders = _below_view_ink()
    seat_face = drawing._x(spec.COLLAR_STATION) * 1000.0
    carrier_face = drawing._x(spec.CARRIER_STATION) * 1000.0
    seat_knee = shoulders["SeatFilletR"][0]
    carrier_knee = shoulders["CarrierFilletR"][1]
    assert seat_face - 4.0 < seat_knee < seat_face - 1.0
    assert carrier_face - 4.0 < carrier_knee < carrier_face
    assert carrier_knee < lines["CollarDia"][0] < seat_knee
    # Every diameter line stands on its own section.
    top_end, bottom_end = (
        drawing._x(spec.OVERALL_LENGTH) * 1000.0,
        drawing._x(0.0) * 1000.0,
    )
    assert top_end < lines["CarrierDia"][0] < carrier_face
    assert carrier_face < lines["CollarDia"][0] < seat_face
    assert seat_face < lines["BearingDia"][0] < bottom_end


def test_callouts_are_short_below_lane_lines() -> None:
    for name, text in spec.DIMENSION_CALLOUTS.items():
        for line in text.splitlines():
            assert len(line) <= 30, (name, line)
    source = inspect.getsource(drawing)
    assert 'location="above"' not in source
    assert 'DIMENSION_CALLOUTS, location="below"' in source


def test_sheet_carries_no_notes() -> None:
    assert spec.DRAWING_NOTES == ""
    assert '"Manufacturing Notes"' not in inspect.getsource(drawing)


def test_knockout_is_stated_in_the_docstring_not_a_note() -> None:
    assert "presses the pin" in spec.__doc__ and "out downward" in spec.__doc__


def test_drawing_script_meets_the_drawing_contract() -> None:
    filename = f"draw_{STEM}.py"
    assert filename in _drawing_contract.PRECISION_MIGRATED_DRAWINGS
    violations = _drawing_contract.drawing_specification_violations(
        inspect.getsource(drawing), filename=filename
    )
    assert not violations, violations
