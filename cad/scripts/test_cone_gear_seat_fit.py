"""Every cone gear bore against the shaft land it is bonded to.

Cross-part contract between the cone gear family (MHA-013) and the cone gear
shaft (MHA-014), closing two Codex findings:

* #834: a gear's bore must be the diameter of the land under its station
  (the U40 S1 bores and #839's moved lands arrive in different PRs);
* #811: a "slip fit" needs a stated, positive clearance.  Main's retained-joint
  ruling (2026-09-25) makes it the shared bonded fit, 0.025-0.105 diametral.
"""

from __future__ import annotations

import pytest

import _fit_limits
import build_cone_gear_shaft
import cone_gear_shaft_spec as shaft
import cone_gear_spec as spec
import cone_shaft_land_bands as lands
from retained_joint_fit import RETAINED_JOINT_CLEARANCE, bonded_bore_band

# Henkel's Loctite 648 gap-fill cap, less a margin (Main, 2026-09-25).
GAP_FILL_CAP = 0.15 - 0.02
MIN_BAND_WIDTH = 0.02


def _land_of(teeth: int) -> int:
    sections = [
        index
        for index, carried in enumerate(lands.SECTION_CONE_GEAR_TEETH)
        if teeth in carried
    ]
    assert len(sections) == 1, teeth
    return sections[0]


def test_the_shaft_reads_the_land_bands_from_their_own_module() -> None:
    assert shaft.SECTION_DIA_BANDS is lands.SECTION_DIA_BANDS
    assert shaft.GEAR_SEAT_BAND is lands.GEAR_SEAT_BAND
    assert shaft.RUNNING_DIA_BAND is lands.RUNNING_DIA_BAND
    assert lands.RUNNING_DIA_BAND is _fit_limits.SHAFT_H
    assert build_cone_gear_shaft.SECTION_DIA_BANDS is lands.SECTION_DIA_BANDS
    assert len(lands.SECTION_CONE_GEAR_TEETH) == len(shaft.SECTIONS)


def test_every_gear_bore_is_the_land_under_it() -> None:
    carried = sorted(t for teeth in lands.SECTION_CONE_GEAR_TEETH for t in teeth)
    assert carried == sorted(spec.CONFIGURATION_TEETH)
    for teeth in spec.CONFIGURATION_TEETH:
        assert spec.bore_dia_mm(teeth) == pytest.approx(
            shaft.SECTION_DIAS[_land_of(teeth)]
        ), teeth


def test_every_gear_station_lies_on_its_land() -> None:
    import build_drive_train_assembly as drive
    import cone_pivot_post_installation

    seat0 = (
        shaft.FRONT_STUB
        + cone_pivot_post_installation.GEAR_AXIS_SHIFT
        + drive.SHAFT_T120_STATION
        + (drive.CONE_FACE_STATION_REFERENCE - drive.CONE_FACE) / 2.0
    )
    for j, teeth in enumerate(range(120, 0, -6)):
        centre = seat0 + j * drive.SEAT_PITCH
        section = _land_of(teeth)
        land_start = shaft.SECTION_ENDS[section - 1]
        land_end = shaft.SECTION_ENDS[section]
        assert land_start <= centre - drive.CONE_FACE / 2.0, teeth
        assert centre + drive.CONE_FACE / 2.0 <= land_end, teeth


def test_bonded_bore_band_is_the_retained_joint_fit() -> None:
    assert RETAINED_JOINT_CLEARANCE == (0.025, 0.105)
    assert bonded_bore_band(lands.GEAR_SEAT_BAND) == (0.055, 0.025)
    assert bonded_bore_band(lands.RUNNING_DIA_BAND) == (0.085, 0.025)


def test_every_bonded_seat_keeps_the_retained_joint_window() -> None:
    bore_upper, bore_lower = spec.BORE_DIA_BAND
    assert bore_upper - bore_lower >= MIN_BAND_WIDTH - 1e-9
    clearance_min, clearance_max = RETAINED_JOINT_CLEARANCE
    for teeth in spec.CONFIGURATION_TEETH:
        land_upper, land_lower = lands.SECTION_DIA_BANDS[_land_of(teeth)]
        tightest = bore_lower - land_upper
        loosest = bore_upper - land_lower
        assert tightest >= clearance_min - 1e-9, teeth
        assert loosest <= clearance_max + 1e-9, teeth
        assert loosest <= GAP_FILL_CAP, teeth


def test_the_t006_web_caps_the_bore_band() -> None:
    # The largest T006 bore under its printed MIN floor keeps the named web.
    floor_min = spec.FLOOR_LIMITS_MM[6][0]
    largest_bore = spec.bore_dia_mm(6) + spec.BORE_DIA_BAND[0]
    assert (floor_min - largest_bore) / 2.0 >= spec.WEB_EXCEPTIONS_MM[6] - 1e-9
