"""Offline contracts for the rocker arm profile fixture (MHA-CH-006-TL-02)."""

from __future__ import annotations

import re
from pathlib import Path

import _config
import _drawing_contract
import ch_rocker_arm_spec as rocker
import ch_rocker_arm_notes as rocker_notes
import ch_rocker_arm_tl_profile_fixture_spec as spec
import draw_ch_rocker_arm_tl_profile_fixture as drawing
import export_features
from _printed_tolerance import printed_band_mm

STEM = "ch_rocker_arm_tl_profile_fixture"
# Agreed with the MHA-CH-006-TL pivot screw and diamond pin (their specs live
# on sibling branches): the screw's ground shoulder and the pin's shank, a
# bonded slip fit (Ø2.97 ±0.02, MHA-CH-006-TL-03).
PIVOT_SCREW_SHOULDER = (6.485, 6.490)
DIAMOND_PIN_SHANK = (2.950, 2.990)


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    views = (
        drawing.PLAN_KEEP_AT,
        drawing.SECTION_KEEP_AT,
        drawing.DETAIL_KEEP_AT,
        drawing.ELEVATION_KEEP_Z,
    )
    assert sum(len(view) for view in views) == len(marked)
    assert set().union(*views) == marked
    # a banded schedule cell is a model dimension with authored places too,
    # but it prints once, in its schedule, never as a marked dimension
    scheduled = {name for cells in spec.SCHEDULE_CELL_DIMENSIONS.values() for _f, name in cells}
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked | scheduled
    assert not marked & scheduled
    assert {name for _f, name in spec.EXPLICIT_SYMMETRIC_TOLERANCES_MM} == scheduled
    assert set(spec.DIMENSION_CALLOUTS) <= marked


def test_locating_bore_takes_every_pivot_screw_shoulder() -> None:
    bore = _features()["locating_bore"]["dia"]
    assert bore[0] > PIVOT_SCREW_SHOULDER[1]
    # the bore is the rocker's own pivot hole, so the arm drops on the same screw
    assert spec.LOCATING_BORE_DIA == rocker.PIVOT_HOLE_DIA


def test_rod_pin_hole_takes_every_diamond_pin_shank() -> None:
    hole = _features()["rod_pin_hole"]["dia"]
    assert hole[0] > DIAMOND_PIN_SHANK[1]


def test_exported_bands_are_the_printed_bands() -> None:
    features = _features()
    for name, nominal, band in (
        ("locating_bore", spec.LOCATING_BORE_DIA, spec.LOCATING_BORE_BAND),
        ("rod_pin_hole", spec.ROD_PIN_HOLE_DIA, spec.ROD_PIN_HOLE_BAND),
    ):
        assert features[name]["dia"] == [round(nominal + band[1], 3), round(nominal + band[0], 3)]
    # StandDrop prints at the general .XXX band, measured from the pad tops
    stand = features["stand_top"]
    band = printed_band_mm(spec.DRAWING_PRECISION_BY_NAME["StandDrop"])
    assert stand["height"] == [round(spec.STAND_DROP - band, 3), round(spec.STAND_DROP + band, 3)]
    assert stand["height_from"] == "pad_tops"
    # the rest tops print once, as RestTopHeight at its authored places, and a
    # rest seated on its floor (two .XXX sizes stacked) stays inside that band
    band = printed_band_mm(spec.DRAWING_PRECISION_BY_NAME["RestTopHeight"])
    rests = features["rail_rest_tops"]["height"]
    assert rests == [round(spec.REST_TOP_HEIGHT - band, 3), round(spec.REST_TOP_HEIGHT + band, 3)]
    stack = 2.0 * printed_band_mm(3)
    assert rests[0] <= spec.REST_HEIGHT - spec.REST_POCKET_DEPTH - stack
    assert rests[1] >= spec.REST_HEIGHT - spec.REST_POCKET_DEPTH + stack
    # the rod-pin ream's coordinates from the bore print with their own band in
    # the schedule, and that band is the exported one (X as station, Y as
    # height, both from the locating bore)
    row = next(row for row in spec.FEATURE_SCHEDULE if row[0] == "P")
    hole = features["rod_pin_hole"]
    assert hole["height_from"] == "locating_bore"
    for key, nominal, printed in zip(("station", "height"), spec.ROD_PIN_HOLE_XY, row[2:4]):
        value, plus = re.fullmatch(r"(-?\d+\.\d{3}) \u00b1(\d\.\d{3})", printed).groups()
        assert float(value) == round(nominal, 3)
        assert hole[key] == [round(nominal - float(plus), 3), round(nominal + float(plus), 3)]
    # its worst corner stays inside a quarter of the rocker rod hole's zone
    zone = float(rocker.GEOMETRIC_TOLERANCES_MM["rod-pin hole position"])
    assert float(plus) * 2**0.5 <= 0.25 * zone / 2.0


def test_hub_stand_carries_the_hub_and_clears_the_strap() -> None:
    # the highest printed stand stays under the lowest accepted hub face: the
    # longest hub on the thinnest strap the rocker print accepts ...
    strap_band = printed_band_mm(rocker_notes.DEFAULT_DRAWING_PRECISION)
    thinnest_strap = rocker.ARM_THICKNESS - strap_band
    longest_step = (rocker.HUB_LENGTH + rocker.HUB_LENGTH_BAND[0] - thinnest_strap) / 2.0
    band = printed_band_mm(spec.DRAWING_PRECISION_BY_NAME["StandDrop"])
    lowest_drop = spec.STAND_DROP - band
    assert lowest_drop >= longest_step
    # ... and 2 mm under the strap where its annulus reaches past the hub
    assert lowest_drop >= 2.0
    # the drilled bore, at its largest, still holds the hub
    assert spec.STAND_BORE + 0.10 < rocker.HUB_DIA


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-profile-fixture")["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)


def test_notes_follow_the_simplicity_policy() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert not re.search(r"\d", spec.DRAWING_NOTES)
    assert spec.BUILT_UP_PERMISSION_NOTE in lines
    assert "GROUND" not in spec.DRAWING_NOTES


def test_draw_script_passes_the_precision_gate() -> None:
    script = Path(drawing.__file__)
    assert script.name in _drawing_contract.PRECISION_MIGRATED_DRAWINGS
    assert not _drawing_contract.drawing_specification_violations(
        script.read_text(encoding="utf-8"), filename=script.name
    )

