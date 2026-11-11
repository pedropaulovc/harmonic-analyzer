"""Every cone gear bore against what it rides on: the key, land 2, or the spigot.

Cross-part contract between the cone gear family (MHA-DT-03), the cone gear
shaft (MHA-DT-04) and the cone tip gear's spigot (MHA-DT-37), owner decision
C1 keyed, 2026-11-09, PR #1992:

* T030..T120 slide on the keyed round land 1: the shared gear seat fit
  (gear_seat_fit, 0.0254-0.09652 diametral) and cone_land_key's keyway
  clearances to the key;
* T024 is a LOCTITE 638 bonded slip fit on the round land 2, T018 and T012
  on the spigot: never interference, never past the compound's largest gap
  (cone_tip_cluster);
* no D-bore remains.
"""

from __future__ import annotations

import math

import pytest

import cone_land_key
import cone_tip_cluster
import dt_cone_gear_spec as spec
import cone_shaft_land_bands as lands
from gear_seat_fit import GEAR_SEAT_CLEARANCE, seat_bore_band

MIN_BAND_WIDTH = 0.01


def _limits(nominal: float, band: tuple[float, float]) -> tuple[float, float]:
    return nominal + band[1], nominal + band[0]


def test_family_partitions_into_keyed_land_and_bonded_round_bores() -> None:
    assert spec.CONFIGURATION_TEETH == tuple(range(12, 121, 6))
    assert spec.CONE_TEETH == (6, *spec.CONFIGURATION_TEETH)
    assert set(spec.KEYED_TEETH) == set(lands.SECTION_CONE_GEAR_TEETH[spec.KEYED_LAND])
    assert spec.KEYED_TEETH == tuple(range(30, 121, 6))
    assert spec.LAND_2_TEETH == (24,)
    assert spec.SPIGOT_TEETH == (12, 18)
    assert spec.ROUND_BORE_TEETH == (12, 18, 24)
    for teeth in spec.CONFIGURATION_TEETH:
        assert spec.keyed(teeth) == (teeth in spec.KEYED_TEETH)
    with pytest.raises(ValueError):
        spec.bore_dia_mm(6)


def test_each_bore_takes_its_mates_size_and_band() -> None:
    for teeth in spec.SPIGOT_TEETH:
        assert spec.bore_dia_mm(teeth) == cone_tip_cluster.STEM_BORE_DIA_MM
        assert spec.bore_dia_band(teeth) == cone_tip_cluster.STEM_BORE_BAND
        assert spec.bonded_mate(teeth) == cone_tip_cluster.SPIGOT
    assert spec.bore_dia_mm(24) == pytest.approx(6.35)
    assert spec.bonded_mate(24) == (spec.bore_dia_mm(24), lands.GEAR_SEAT_BAND)
    assert spec.BORE_DIA_BAND == seat_bore_band(lands.GEAR_SEAT_BAND)
    for teeth in (24, *spec.KEYED_TEETH):
        assert spec.bore_dia_band(teeth) == spec.BORE_DIA_BAND
    for teeth in spec.KEYED_TEETH:
        assert spec.bore_dia_mm(teeth) == cone_land_key.LAND_DIA_MM
        with pytest.raises(ValueError):
            spec.bonded_mate(teeth)


def test_every_bond_stays_inside_the_compounds_gap() -> None:
    for teeth in spec.ROUND_BORE_TEETH:
        bore = _limits(spec.bore_dia_mm(teeth), spec.bore_dia_band(teeth))
        mate = _limits(*spec.bonded_mate(teeth))
        low, high = bore[0] - mate[1], bore[1] - mate[0]
        assert spec.bond_clearance_mm(teeth) == pytest.approx((low, high))
        assert low >= 0.0, teeth
        assert high <= cone_tip_cluster.RETAINING_COMPOUND_MAX_GAP_MM, teeth
    assert spec.bond_clearance_mm(12) == pytest.approx(
        cone_tip_cluster.SPIGOT_BOND_CLEARANCE_MM
    )


def test_keyed_seat_keeps_the_round_clearance_window() -> None:
    bore_upper, bore_lower = spec.BORE_DIA_BAND
    assert bore_upper - bore_lower >= MIN_BAND_WIDTH - 1e-9
    land_upper, land_lower = lands.SECTION_DIA_BANDS[spec.KEYED_LAND]
    round_min, round_max = GEAR_SEAT_CLEARANCE
    assert bore_lower - land_upper >= round_min - 1e-9
    assert bore_upper - land_lower <= round_max + 1e-9


def test_every_keyed_gear_slides_over_the_key_at_the_print_extremes() -> None:
    # Radial: the keyway's top (T at its least, from the far side of the
    # bore) clears the key's top (S at its most plus the key at its most),
    # with the hub's far side on the land's far side; sides: the broach's
    # least width against the key at its most.
    key_max = _limits(cone_land_key.KEY_SIZE_MM, cone_land_key.KEY_STOCK_BAND)[1]
    t_min = _limits(cone_land_key.KEYWAY_T_MM, cone_land_key.KEYWAY_T_BAND)[0]
    s_max = _limits(cone_land_key.KEYSEAT_S_MM, cone_land_key.KEYSEAT_S_BAND)[1]
    width_min = _limits(cone_land_key.KEYWAY_WIDTH_MM, cone_land_key.KEYWAY_WIDTH_BAND)[
        0
    ]
    assert t_min - s_max - key_max > 0.0
    assert width_min - key_max >= 0.0
    for teeth in spec.KEYED_TEETH:
        radius = spec.bore_dia_mm(teeth) / 2.0
        assert spec.keyway_top_offset_mm(teeth) == pytest.approx(
            cone_land_key.KEYWAY_T_MM - radius
        )
        assert spec.keyway_top_offset_mm(teeth) > radius > spec.KEYWAY_HALF_WIDTH_MM
    with pytest.raises(ValueError):
        spec.keyway_top_offset_mm(24)


def _chord_height(dia: float, width: float) -> float:
    return (dia - math.sqrt(dia * dia - width * width)) / 2.0


def test_one_broach_pass_lands_in_t_and_the_keyseat_clears_the_key_under_it() -> None:
    # A 1/16 A broach in its 3/8 A bushing cuts 0.70 mm deep in one pass
    # (duMONT 1/16"-A, Rev Broaching Tool's table, read across its 0.01 mm
    # rounding).  Every reading of that depth lands inside T: from the
    # bushing's 3/8 circle or the bore, at the keyway's centreline or at its
    # walls, where the circle stands its chord height below the centreline.
    t_min, t_max = _limits(cone_land_key.KEYWAY_T_MM, cone_land_key.KEYWAY_T_BAND)
    widths = _limits(cone_land_key.KEYWAY_WIDTH_MM, cone_land_key.KEYWAY_WIDTH_BAND)
    land = cone_land_key.LAND_DIA_MM
    bores = _limits(land, seat_bore_band(lands.GEAR_SEAT_BAND))
    for depth in (0.695, 0.705):
        for reference in (land, *bores):
            for drop in (0.0, *(_chord_height(reference, w) for w in widths)):
                assert t_min <= reference + depth - drop <= t_max, reference
    # ANSI B17.1 for a 1/16 key on Ø.375: T = D - Y + H/2 + .005 (.4087)
    # would cut past T's largest, where T030's web was ruled; its S =
    # D - Y - H/2 (.3411) would stand the key's top over T's smallest.  The
    # printed S at its largest keeps the key's top .0015 under it.
    key = cone_land_key.KEY_SIZE_MM
    key_max = _limits(key, cone_land_key.KEY_STOCK_BAND)[1]
    s_max = _limits(cone_land_key.KEYSEAT_S_MM, cone_land_key.KEYSEAT_S_BAND)[1]
    y = _chord_height(land, key)
    assert land - y + key / 2.0 + 0.127 > t_max
    assert land - y - key / 2.0 + key_max > t_min
    assert t_min - s_max - key_max == pytest.approx(0.0381)


def test_every_keyed_web_is_proved_at_the_keyway_corner() -> None:
    # Rule 17 at the keyway's top corner (T at its most, bore at its least,
    # keyway at its widest), under the printed root envelope MIN: T030 is
    # the recorded minor (RV-07, .0621 in), above the .060 floor; every
    # other keyed gear keeps the .080 target.
    t_max = _limits(cone_land_key.KEYWAY_T_MM, cone_land_key.KEYWAY_T_BAND)[1]
    width_max = _limits(cone_land_key.KEYWAY_WIDTH_MM, cone_land_key.KEYWAY_WIDTH_BAND)[
        1
    ]
    for teeth in spec.KEYED_TEETH:
        bore_min = spec.bore_dia_mm(teeth) + spec.BORE_DIA_BAND[1]
        corner = math.hypot(t_max - bore_min / 2.0, width_max / 2.0)
        web = spec.floor_limits_mm(teeth)[0] / 2.0 - corner
        assert spec.keyway_web_min_mm(teeth) == pytest.approx(web)
        assert spec.web_min_mm(teeth) == pytest.approx(web)
        assert web >= spec.keyway_web_required_mm(teeth) - 1e-9, teeth
        if teeth not in spec.KEYWAY_WEB_EXCEPTIONS_MM:
            assert web >= spec.MACHINED_WEB_TARGET_MM - 1e-9, teeth
    assert set(spec.KEYWAY_WEB_EXCEPTIONS_MM) == {30}
    assert spec.inch_grid_mm(
        spec.keyway_web_min_mm(30), 4, math.floor
    ) == pytest.approx(spec.KEYWAY_WEB_EXCEPTIONS_MM[30])


def test_every_round_web_is_proved_at_the_largest_printed_bore() -> None:
    # Rule 17 from the largest printed reamed bore to the printed root
    # envelope MIN: T012 is RV-03's minor (.0646 in), T018 and T024 keep the
    # .080 target.
    for teeth in spec.ROUND_BORE_TEETH:
        bore_max = (
            math.ceil(
                (spec.bore_dia_mm(teeth) + spec.bore_dia_band(teeth)[0]) / 25.4 * 1e4
                - 1e-6
            )
            / 1e4
            * 25.4
        )
        web = (spec.floor_limits_mm(teeth)[0] - bore_max) / 2.0
        assert spec.round_bore_web_min_mm(teeth) == pytest.approx(web)
        assert spec.web_min_mm(teeth) == pytest.approx(web)
        assert web >= spec.web_required_mm(teeth) - 1e-9, teeth
    assert set(spec.WEB_EXCEPTIONS_MM) == {12}
    printed = {
        teeth: spec.inch_grid_mm(spec.round_bore_web_min_mm(teeth), 4, math.floor)
        / 25.4
        for teeth in spec.ROUND_BORE_TEETH
    }
    assert printed == pytest.approx({12: 0.0646, 18: 0.1268, 24: 0.0947})
    assert spec.WEB_EXCEPTIONS_MM[12] == pytest.approx(0.0646 * 25.4)
    assert (
        spec.MACHINED_WEB_FLOOR_MM
        < spec.WEB_EXCEPTIONS_MM[12]
        < spec.MACHINED_WEB_TARGET_MM
    )
    _start, minimum, _band = spec.web_reference_mm()
    assert minimum == pytest.approx(spec.WEB_EXCEPTIONS_MM[12])


def test_keyed_bore_area_is_the_round_bore_plus_the_keyway_outside_it() -> None:
    # Midpoint-rule integral of the keyway strip outside the round bore.
    for teeth in spec.KEYED_TEETH[:1]:
        radius = spec.bore_dia_mm(teeth) / 2.0
        half, top = spec.KEYWAY_HALF_WIDTH_MM, spec.keyway_top_offset_mm(teeth)
        steps = 20000
        dy = 2.0 * half / steps
        outside = sum(
            (top - math.sqrt(radius**2 - (-half + (i + 0.5) * dy) ** 2)) * dy
            for i in range(steps)
        )
        assert spec.keyway_area_outside_bore_mm2(teeth) == pytest.approx(
            outside, rel=1e-7
        )


def test_no_bore_is_clock_dimensioned() -> None:
    # The keyway shares the front view's drawn centreline with the phase-0
    # tooth: its clock is the title block's angle, undimensioned
    # (test_error_budget pins error_budget.yaml's cone_flat_clock to it); the
    # bonded round bores carry no clock.
    assert spec.DRAWING_DIMENSIONS[spec.BORE_SKETCH] == {"BoreCutDia"}
    assert "KeywayClock" not in spec.DRAWING_DIMENSIONS[spec.KEYED_BORE_SKETCH]
    assert not any("Clock" in name for name in spec.DRAWING_PRECISION_BY_NAME)
