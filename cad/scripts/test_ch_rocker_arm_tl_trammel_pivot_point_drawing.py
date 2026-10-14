"""Offline contracts for the rocker template trammel's pivot point (MHA-CH-006-TL-18)."""

from __future__ import annotations

import inspect
import math
import re

import _config
import _drawing_contract
import ch_rocker_arm_tl_trammel_pivot_point_spec as spec
import ch_rocker_arm_tl_trammel_spec as kit
import draw_ch_rocker_arm_tl_trammel_pivot_point as drawing
import export_features
from _printed_limits import limits
from prechips.model import TOLERANCE_REQUIREMENTS

STEM = "ch_rocker_arm_tl_trammel_pivot_point"
DASHED = "ch-rocker-arm-tl-trammel-pivot-point"


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def test_every_marked_dimension_prints_once() -> None:
    assert set(drawing.PROFILE_KEEP) == set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(spec.DRAWING_PRECISION_BY_NAME) == set(drawing.PROFILE_KEEP)
    assert set(spec.DIMENSION_CALLOUTS) <= set(drawing.PROFILE_KEEP)
    assert spec.REFERENCE_DIMENSIONS <= set(drawing.PROFILE_KEEP)


def test_every_exported_band_is_a_requirement() -> None:
    """One-fact rule: prechips inspects only the bands a feature lists."""
    for name, feature in _features().items():
        for key, value in feature.items():
            if key in TOLERANCE_REQUIREMENTS and isinstance(value, list):
                assert key in feature["requirements"], (name, key)


def test_every_exported_nominal_lies_inside_its_band() -> None:
    for name, feature in _features().items():
        for key, nominal in feature.items():
            if key.endswith("_nominal"):
                band = feature.get(key.removesuffix("_nominal"))
            elif key.endswith("_nominal_deg"):
                band = feature.get(key.removesuffix("_nominal_deg") + "_deg")
            else:
                continue
            if band is None:
                assert "note" in feature["requirements"], (name, key)
                continue
            low, high = band
            assert low <= nominal <= high, (name, key)


def test_every_printed_band_has_a_requirement_owner() -> None:
    """Each printed toleranced dimension reaches prechips as a listed band at
    its printed places. The rod O.D. is a stock reference under its callout;
    the hardened zone is a heat-treat extent, not a measured face."""
    owners = {
        "PointLength": ("back_face", "station", None),
        "TipFlatDia": ("tip_flat", "dia", spec.TIP_FLAT_DIA_BAND),
    }
    exempt = {"RodDia", "HardenedLength", "TipHalfAngle"}
    assert set(owners) | exempt == set(spec.DRAWING_PRECISION_BY_NAME)
    features = _features()
    for printed, (name, key, band) in owners.items():
        feature = features[name]
        assert key in feature["requirements"], printed
        places = spec.DRAWING_PRECISION_BY_NAME[printed]
        nominal = feature[f"{key}_nominal"]
        assert round(nominal, places) == nominal, printed
        assert feature[key] == limits(nominal, places, band), printed
    cone = features["tip_cone"]
    assert "land_angle_deg" in cone["requirements"]
    assert cone["land_angle_deg"] == [spec.TIP_HALF_ANGLE_MIN, spec.TIP_HALF_ANGLE_MAX]
    assert cone["angle_deg"] == kit.PIVOT_TIP_ANGLE
    shank = features["shank"]
    assert "dia" not in shank
    assert shank["dia_nominal"] == kit.POINT_ROD_DIA
    assert shank["note"] == spec.ROD_NOTE
    assert "MHA-CH-006-TL-14" in spec.ROD_CALLOUT


def test_tip_flat_truncates_the_point_on_the_cone() -> None:
    """Rule 16: a stated flat, printed MAX, whose model value is that max,
    sitting on the cone well inside the rod."""
    assert spec.TIP_FLAT_DIA == spec.TIP_FLAT_DIA_MAX > 0.0
    assert math.isclose(
        spec.TIP_FLAT_STATION * math.tan(math.radians(spec.TIP_HALF_ANGLE)),
        spec.TIP_FLAT_DIA / 2.0,
    )
    assert spec.TIP_FLAT_STATION < spec.CONE_LENGTH < spec.HARDENED_LENGTH


def test_point_slides_in_the_reamed_hole_and_passes_through_its_block() -> None:
    assert spec.ROD_HOLE_CLEARANCE_MIN > 0.0
    assert spec.POINT_LENGTH - kit.POINT_PROJECTION > kit.BLOCK_HEIGHT
    assert spec.HARDENED_LENGTH > kit.POINT_PROJECTION


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts(DASHED)["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)
    assert number == "MHA-CH-006-TL-18"
    assert _config.parts(DASHED)["quantity"] == 1


def test_finish_fits_one_title_block_line() -> None:
    finish = _config.parts(DASHED)["finish"]
    assert "\n" not in finish and len(finish) <= 40, finish


def test_callouts_are_short_below_lane_lines() -> None:
    """Callout text does not wrap, so every line stays short; the drawing
    puts every callout in the below lane."""
    for name, text in spec.DIMENSION_CALLOUTS.items():
        for line in text.splitlines():
            assert len(line) <= 30, (name, line)
    source = inspect.getsource(drawing)
    assert 'location="above"' not in source
    assert 'DIMENSION_CALLOUTS, location="below"' in source


def test_notes_follow_the_simplicity_policy() -> None:
    notes = spec.DRAWING_NOTES
    assert 1 <= len(notes.splitlines()) <= 4
    assert not re.search(r"\d", notes)
    assert "GROUND" not in notes and "GRIND" not in notes
    # The Finish field carries the hardness; the seats ride the angle callout.
    assert "HARD" not in notes and "SEAT" not in notes


def test_tightened_cone_names_its_seats_on_its_callout() -> None:
    """Rule 4: the half-angle band names the pivot plate's and the setting
    bar's cones by Number on the angle callout itself."""
    callout = spec.DIMENSION_CALLOUTS["TipHalfAngle"]
    assert "MHA-CH-006-TL-19" in callout and "MHA-CH-006-TL-17" in callout
    assert spec.TIP_ANGLE_TOL_DEG == spec.TIP_HALF_ANGLE_TOL_DEG * 2.0


def test_drawing_script_meets_the_drawing_contract() -> None:
    filename = f"draw_{STEM}.py"
    assert filename in _drawing_contract.PRECISION_MIGRATED_DRAWINGS
    source = inspect.getsource(drawing)
    violations = _drawing_contract.drawing_specification_violations(
        source, filename=filename
    )
    assert not violations, violations


def test_pivot_point_seats_in_the_centre_drilled_cone_without_bottoming() -> None:
    """The sharpest printed cone with no flat reaches deepest: it bears on the
    No. 2 centre drill's pilot entry and its apex stays above the pilot's
    118 degree drill-point floor, with radial room left there."""
    depth = spec.PILOT_R / math.tan(math.radians(spec.TIP_HALF_ANGLE_MIN))
    assert depth == spec.TIP_DEPTH_MAX < spec.PILOT_LENGTH
    room = (spec.PILOT_LENGTH - depth) * math.tan(
        math.radians(spec.PILOT_POINT_HALF_ANGLE)
    )
    assert room == spec.TIP_FLOOR_ROOM > 0.0
    assert spec.TIP_HALF_ANGLE_MAX < spec.PILOT_POINT_HALF_ANGLE
    assert spec.TIP_FLAT_DIA_MAX < kit.CENTER_DRILL_PILOT_DIA
    assert spec.TIP_HALF_ANGLE == kit.CENTER_DRILL_ANGLE / 2.0
