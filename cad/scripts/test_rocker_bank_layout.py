"""Offline contracts for the rocker-bank retention stack (issue #743, PR2)."""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

import _config
import cam_plane
import ch_amplitude_bar_spec as bar
import channel_frame_geom as frame
import channel_kinematics as ck
import error_budget
import ch_rocker_arm_notes as arm_notes
import cylinder_bank_layout as drum_bank
import ch_pivot_bracket_spec as bracket
import ch_pivot_shaft_spec as shaft
import ch_vn_rocker_thrust_washer_spec as washer
import ch_rocker_arm_spec as arm
import rocker_bank_layout as bank
from _buildgraph import config_files_of, module_deps_of
from _printed_tolerance import printed_band_mm

SCRIPTS = Path(__file__).resolve().parent
_BAND_2PL = _config.title_block("linear_2pl")["value_in"] * 25.4  # 0.508


def test_hub_length_is_the_station_pitch_and_only_comes_out_long() -> None:
    assert arm.HUB_LENGTH == pytest.approx(
        _config.machine("channels", "station_pitch_mm"), abs=1e-9
    )
    upper, lower = arm.HUB_LENGTH_BAND
    assert lower == 0.0 < upper == pytest.approx(0.0508)
    assert bank.STACK_L20 == pytest.approx(bank.COUNT * arm.HUB_LENGTH)
    # #948 ruling R tightened the acceptance to +.004/0 in (a fit-up re-face).
    assert bank.STACK_L20_ACCEPT == pytest.approx(
        (bank.STACK_L20, bank.STACK_L20 + 0.1016)
    )


def test_preload_rule_is_the_cylinder_bank_rule() -> None:
    """The rocker layout shares ONE datum with cylinder_bank_layout (the cam
    plane, its arm plane, from the cam_plane leaf) but restates the set-blade,
    preload and fit-up compensation rules, because it has its own spring and datum ear; this
    pins the two in lockstep."""
    assert bank.MARGIN_SPARE == drum_bank.MARGIN_SPARE
    assert bank.FEELER_STEP == drum_bank.FEELER_STEP
    # Same set-error rule; the rocker sheet prints it inch (+/-.004), the
    # drive-train sheet still mm (+/-0.10) until that sheet converts.
    assert bank.ROCKER_SPRING_SET_BAND == pytest.approx(
        drum_bank.BANK_SPRING_SET_BAND, abs=0.002
    )
    assert bank.PRELOAD_LIMITS == drum_bank.PRELOAD_LIMITS
    assert bank.MIC_RESIDUAL == drum_bank.MIC_RESIDUAL
    assert bank.NORTH_EAR_LOCATE_BAND == drum_bank.FRONT_STRAP_LOCATE_BAND


def test_the_bank_is_preloaded_by_its_spring() -> None:
    # #948 ruling R: the 0.45 leaf became a 9714K24 wave spring set on a 0.60
    # blade; its whole set band stays in the spring's working range at a
    # light, single-digit-newton preload; no end play, no shaft float.
    assert bank.ROCKER_SPRING_SET == pytest.approx(0.60)
    assert bank.ROCKER_SPRING_HEIGHT == pytest.approx((0.4984, 0.7016))
    assert bank.ROCKER_PRELOAD == pytest.approx((2.12, 9.23), abs=0.01)
    assert bank.ROCKER_SPRING_Z == (bank.SOUTH_EAR_INNER_Z, bank.SOUTH_WASHER_Z[0])
    assert not hasattr(bank, "ROCKER_END_PLAY")
    # The north washer replaces the shaft's shoulder in the datum chain, its
    # stock band mic-compensated as the shoulder's was (user, 2026-10-10).
    assert bank.NORTH_DATUM_STACK == pytest.approx(
        {"north ear DRO locate": 0.10, "north washer, mic-compensated": 0.013}
    )


def test_the_rocker_spring_fits_the_shaft_and_under_the_bar_foot() -> None:
    import ch_vn_rocker_bank_spring_spec as spring

    # The ch0 bar's foot passes over it as over the hubs; the washer is
    # smaller still.
    assert spring.OD + spring.OD_BAND[0] <= arm.HUB_DIA
    assert washer.OD_MAX <= arm.HUB_DIA
    # It bears on the washer's face clear of the washer's bore.
    assert spring.OD + spring.OD_BAND[1] > washer.ID_MAX
    # Nominal ID clears the shaft; the catalogue's -0.02 in reaches under it,
    # which the channel assembly's slide-free check catches.
    assert spring.SHAFT_CLEARANCE_NOMINAL == pytest.approx(0.1905)
    assert spring.ID + spring.ID_BAND[1] < shaft.SHAFT_DIA


def test_hub_mid_planes_are_the_channel_arm_planes() -> None:
    z0 = _config.machine("channels", "station_z0_mm")
    pitch = _config.machine("channels", "station_pitch_mm")
    # Option A (rod fork joint): the arm plane IS the cam plane.
    assert bank.ARM_MID_DZ == cam_plane.CAM_MID_DZ
    assert bank.ARM_MID_DZ == pytest.approx(-3.52825)
    for j in (0, 7, 19):
        assert bank.hub_mid_z(j) == pytest.approx(z0 + pitch * j + cam_plane.CAM_MID_DZ)
    assert bank.STACK_MID_Z == pytest.approx(
        (bank.hub_mid_z(0) + bank.hub_mid_z(19)) / 2
    )


def test_stack_closes_north_on_a_washer_against_the_north_ear() -> None:
    """User, 2026-10-10: the shaft's shoulder is gone; hub 19 bears on a
    MHA-CH-VN-56 thrust washer against the north ear's inner face, the bank's
    datum."""
    assert bank.HUB19_NORTH_FACE_Z == pytest.approx(
        bank.hub_mid_z(19) + arm.HUB_LENGTH / 2
    )
    assert bank.NORTH_WASHER_Z == pytest.approx(
        (bank.HUB19_NORTH_FACE_Z, bank.HUB19_NORTH_FACE_Z + washer.THICKNESS)
    )
    assert bank.NORTH_EAR_INNER_Z == pytest.approx(bank.NORTH_WASHER_Z[1])
    assert bank.NORTH_EAR_OUTER_Z == pytest.approx(
        bank.NORTH_EAR_INNER_Z + bracket.EAR_T
    )
    assert bank.NORTH_EAR_INNER_Z == pytest.approx(70.848, abs=5e-4)
    assert not hasattr(bank, "SHOULDER_Z")


def test_south_bracket_is_set_off_the_thrust_washer_by_the_spring() -> None:
    assert bank.HUB0_SOUTH_FACE_Z == pytest.approx(
        bank.hub_mid_z(0) - arm.HUB_LENGTH / 2
    )
    assert bank.SOUTH_WASHER_Z == pytest.approx(
        (bank.HUB0_SOUTH_FACE_Z - washer.THICKNESS, bank.HUB0_SOUTH_FACE_Z)
    )
    assert bank.SOUTH_WASHER_Z[0] - bank.SOUTH_EAR_INNER_Z == pytest.approx(
        bank.ROCKER_SPRING_SET
    )
    assert bank.SOUTH_EAR_OUTER_Z == pytest.approx(
        bank.SOUTH_EAR_INNER_Z - bracket.EAR_T
    )
    assert bank.SOUTH_EAR_INNER_Z == pytest.approx(-72.456, abs=5e-4)


def test_the_washers_are_purchased_0_031_ring_shims() -> None:
    """Owner, 2026-10-15: every washer is a purchased part. McMaster
    3088A429's 0.031 in nominal is within 0.003 of the retired 1/32 sheet
    washer, so the south bracket keeps its foot room beside the .320 ear,
    and its +/-0.002 in band is inside the sheet's."""
    assert washer.SKU == "3088A429"
    assert washer.COUNT == 2
    assert washer.THICKNESS == pytest.approx(0.031 * 25.4)
    assert (washer.THICKNESS_MIN, washer.THICKNESS_MAX) == pytest.approx(
        (0.7366, 0.8382), abs=5e-5
    )
    assert _config.parts("ch-vn-rocker-thrust-washer")["number"] == "MHA-CH-VN-56"


def test_brackets_sit_on_their_ears_and_move_in_from_78() -> None:
    south, north = bank.PIVOT_BRACKET_Z
    assert south == pytest.approx(bank.SOUTH_EAR_INNER_Z - bracket.EAR_T / 2)
    assert north == pytest.approx(bank.NORTH_EAR_INNER_Z + bracket.EAR_T / 2)
    assert bracket.EAR_T == pytest.approx(0.320 * 25.4)
    assert (south, north) == pytest.approx((-76.520, 74.912), abs=5e-4)
    assert bank.STACK_MID_Z - south < 78.0
    assert north - bank.STACK_MID_Z < 78.0
    # Both feet stay on the rocker-arm-support's +-88.9 top.
    assert south - bracket.EAR_T / 2 > -88.9
    assert north + bracket.EAR_T / 2 < 88.9


def test_shaft_is_a_plain_rod_spanning_both_ears() -> None:
    assert bank.PIVOT_SHAFT_SOUTH_Z == pytest.approx(
        bank.SOUTH_EAR_OUTER_Z + bank.SOUTH_END_INSET
    )
    assert bank.PIVOT_SHAFT_NORTH_Z == pytest.approx(bank.NORTH_EAR_OUTER_Z)
    # The overall length prints at .XX and is finished to it: the shaft
    # between the dome bases takes the rounding, its south end inset from
    # the south ear's outer face by under half a grid step.
    assert bank.PIVOT_SHAFT_OVERALL_LENGTH == pytest.approx(6.40 * 25.4)
    assert bank.PIVOT_SHAFT_LENGTH == pytest.approx(
        bank.PIVOT_SHAFT_OVERALL_LENGTH - 2 * shaft.DOME_HEIGHT
    )
    assert 0.0 <= bank.SOUTH_END_INSET <= 0.127
    assert bank.PIVOT_SHAFT_LENGTH == pytest.approx(
        bank.NORTH_EAR_OUTER_Z - bank.SOUTH_EAR_OUTER_Z - bank.SOUTH_END_INSET
    )
    # Domed .06 like the arbor ends (user, #743 Q4): SR .16 on the 1/4 rod.
    assert shaft.DOME_HEIGHT == pytest.approx(0.06 * 25.4)
    assert shaft.DOME_SPHERE_RADIUS == pytest.approx(4.069, abs=5e-3)
    assert 0.0 < shaft.DOME_HEIGHT <= shaft.SHAFT_DIA / 2
    for gone in ("SHOULDER_DIA", "SHOULDER_LENGTH", "JOURNAL_LENGTH", "RELIEF_DIA"):
        assert not hasattr(shaft, gone)


def test_hub_keeps_its_od_over_each_wall_floor_and_the_washer_rides_the_shaft() -> None:
    """The hub keeps Ø.400 (#290); PR #1354 includes coaxial eccentricity in the
    hub's own rule-12 diameter floor, without changing the nominal. The
    purchased washer's catalogue bore floor is the shaft's nominal, so it
    slides on the h-band shaft at worst line on line, and its OD stays under
    the hub's."""
    assert arm.LINEAR_2PL == pytest.approx(printed_band_mm(2, unit=arm.UNIT))
    assert arm.HUB_DIA == pytest.approx(10.16)
    bore_max = arm.PIVOT_HOLE_DIA + arm.PIVOT_HOLE_BAND[0]
    eccentricity = arm.HUB_COAXIALITY_DIA / 2.0
    required_od = bore_max + 2.0 * (arm.RULE12_WALL_FLOOR + eccentricity) + arm.LINEAR_2PL
    ceiling = math.ceil(round(required_od * 100.0, 9)) / 100.0
    assert required_od == pytest.approx(9.9314)
    assert arm.HUB_DIA >= arm.HUB_DIA_MIN == pytest.approx(ceiling)
    assert arm.HUB_DIA_MIN == pytest.approx(9.94)
    assert washer.ID_MIN == pytest.approx(shaft.SHAFT_DIA + shaft.SHAFT_DIA_BAND[0])
    assert washer.ID_MIN <= washer.ID <= washer.ID_MAX
    assert washer.OD_MAX < arm.HUB_DIA_MIN


def test_hub_wall_covers_the_worst_printed_limits_and_eccentricity() -> None:
    """The minimum on the sheet is a physical wall, not the raw class band."""
    from _inch_wall_limits import WALL_TARGET_MM

    places = arm_notes.DRAWING_PRECISION["HubProfile"]["HubDia"]
    printed_band = printed_band_mm(places, unit=arm.UNIT)
    assert printed_band == pytest.approx(0.254)
    od = round(arm.HUB_DIA / 25.4, places) * 25.4
    bore_max = arm.PIVOT_HOLE_DIA + arm.PIVOT_HOLE_BAND[0]
    eccentricity = arm.HUB_COAXIALITY_DIA / 2.0
    assert od == pytest.approx(10.16)
    assert bore_max == pytest.approx(6.5278)
    assert arm.HUB_COAXIALITY_DIA == pytest.approx(0.1016)
    wall = (od - printed_band - bore_max) / 2.0 - eccentricity
    assert wall == pytest.approx(1.6383)
    # Named exception (RV-03): above the .060 floor, under the .080 target.
    assert arm.RULE12_WALL_FLOOR <= wall < WALL_TARGET_MM
    stated_wall = math.floor(wall / 25.4 * 1000 + 1e-9) / 1000 * 25.4
    assert arm_notes.HUB_WALL_MIN == pytest.approx(stated_wall)
    assert stated_wall <= wall + 1e-9
    assert arm_notes.HUB_WALL_NOTE == f"HUB WALL {arm.inch_text(stated_wall, 3)} MIN"
    assert arm_notes.HUB_WALL_NOTE in arm_notes.DRAWING_NOTES
    # The eccentricity is the hub OD's printed position zone to A.
    assert arm.GEOMETRIC_TOLERANCES_MM["hub OD position to bore"] == pytest.approx(
        arm.HUB_COAXIALITY_DIA
    )
    # The spec's pessimistic hundredth-mm ceiling covers the printed class;
    # lowering that floor by one hundredth does not.
    floor_wall = (arm.HUB_DIA_MIN - printed_band - bore_max) / 2.0 - eccentricity
    assert floor_wall >= arm.RULE12_WALL_FLOOR - 1e-9
    assert floor_wall - 0.01 / 2.0 < arm.RULE12_WALL_FLOOR
    # R9's inherited Ø0.50 zone is unsafe at the unchanged nominal OD.
    old_coaxiality = 0.50
    old_wall = (od - printed_band - bore_max) / 2.0 - old_coaxiality / 2.0
    assert old_wall == pytest.approx(1.4391)
    assert old_wall < arm.RULE12_WALL_FLOOR
    # Omitting eccentricity recreates the old floor, which cannot meet the floor.
    old_floor = math.ceil(
        round((bore_max + 2.0 * arm.RULE12_WALL_FLOOR + arm.LINEAR_2PL) * 100, 9)
    ) / 100
    assert (old_floor - printed_band - bore_max) / 2.0 - eccentricity < (
        arm.RULE12_WALL_FLOOR
    )


def test_the_set_screws_bite_flats_clear_of_the_hubs() -> None:
    """User, 2026-10-10: one #4-40 set screw down through each ear's apex onto
    a flat at that ear's mid-plane holds the shaft. At the fit-up's worst
    axial wander (the north tip set on the north ear's outboard face; the
    south ear moved by the north ear's thickness, the stack's acceptance, the
    blade's set and both washers' stock bands; each flat stationed from its
    own tip, so the south one also carries the overall length's band) each
    cup stays wholly on its flat, and no hub's bore rides over a flat's edge
    (the ear, the washer and the spring may: none of them runs on the
    shaft)."""
    south, north = bank.PIVOT_BRACKET_Z
    # The bar is the same either way round, so the south flat sits the
    # shaft's south end inset off the south ear's centre.
    assert bank.PIVOT_SHAFT_FLAT_STATIONS == pytest.approx(
        (
            bank.PIVOT_SHAFT_NORTH_Z - south - bank.SOUTH_END_INSET,
            bank.PIVOT_SHAFT_NORTH_Z - north,
        )
    )
    assert bank.PIVOT_SHAFT_FLAT_STATIONS == pytest.approx((155.448, 4.064), abs=5e-3)
    assert shaft.NORTH_FLAT_STATION == bracket.EAR_T / 2
    # Each from its own tip: the bar is the same either way round.
    assert shaft.FLAT_TIP_STATION == pytest.approx(
        bank.PIVOT_SHAFT_OVERALL_LENGTH - (bank.PIVOT_SHAFT_FLAT_STATIONS[0] + shaft.DOME_HEIGHT)
    )
    assert shaft.FLAT_TIP_STATION == pytest.approx(0.22 * 25.4)
    # .010 tip set + .004 north-ear thickness + 0.3048 south-ear set + the
    # south end's inset.
    assert bank.FLAT_OFFSET_MAX == pytest.approx(
        (0.254 + 0.1016 + 0.3048 + bank.SOUTH_END_INSET, 0.254), abs=5e-4
    )
    station_error = (
        shaft.FLAT_STATION_BAND + shaft.LENGTH_BAND,
        shaft.FLAT_STATION_BAND,
    )
    assert bank.FLAT_STATION_ERROR == pytest.approx(station_error)
    washer_thin = washer.THICKNESS_MIN
    # The taps run from each ear's inboard face, the shaft from the north
    # ear's outboard face. South: the south ear's own thickness cancels (its
    # inboard face carries both the tap and the hub run), the north ear's is
    # in the offset. North: the inboard face and the tap both lose the whole
    # ear band.
    hub_free = (
        (bracket.EAR_T - bracket.EAR_T_BAND) / 2
        + washer_thin
        + bank.ROCKER_SPRING_HEIGHT[0],
        bracket.EAR_T / 2 - bracket.EAR_T_BAND + washer_thin,
    )
    tap_band = (
        bracket.SET_SCREW_STATION_BAND,
        bracket.SET_SCREW_STATION_BAND + bracket.EAR_T_BAND,
    )
    assert bank.FLAT_RUN_MAX == pytest.approx(hub_free)
    for offset, error, run_max, band in zip(
        bank.FLAT_OFFSET_MAX, station_error, hub_free, tap_band, strict=True
    ):
        reach = offset + error + band
        assert reach + shaft.SET_SCREW_CUP_DIA / 2 <= shaft.FLAT_LENGTH_RANGE[0] / 2
        assert (
            offset + error + shaft.FLAT_LENGTH_RANGE[1] / 2
            <= run_max - bank.RUNNING_FLOOR
        )
    assert shaft.flat_chord(shaft.FLAT_DEPTH_RANGE[0]) > shaft.SET_SCREW_CUP_DIA + 1.0


def test_south_apex_stays_on_the_support_at_the_worst_case() -> None:
    """Main (a): both ends domed. The shaft comes finished to its overall
    length and its north tip is set DOME_HEIGHT proud of the north ear, so
    the south tip stands DOME_HEIGHT past the south ear give or take the
    tip's set, the length's band, both ears' thicknesses and the south ear's
    set; it must stay over the rocker-arm-support's -88.9 end. Outboard of
    the south ear at the shaft's height there is only the support's own top,
    so its end is the bound. The set screws hold the shaft, so it never
    floats south."""
    assert bank.SOUTH_APEX_REACH_MAX == pytest.approx(
        shaft.DOME_HEIGHT
        + 0.254
        + 0.254
        + 2 * bracket.EAR_T_BAND
        + 0.3048
        - bank.SOUTH_END_INSET,
        abs=5e-4,
    )
    apex_z = bank.SOUTH_EAR_OUTER_Z - bank.SOUTH_APEX_REACH_MAX
    assert apex_z == pytest.approx(-83.076, abs=5e-4)
    assert apex_z - (-88.9) >= 2.0


def test_amplitude_bars_clear_both_thrust_faces_at_the_worst_case(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The bar straddles its arm plate (z_mid +- BAR_WIDTH/2) while the hub
    face's offset from the plate prints at .XX. A plate-wide thrust face on
    an end hub would reach the end bar; the washers (under the bar foot, like
    the hubs) stand both ears off. The washer is 0.031 stock, so its catalogue
    band's thin side counts; the south ear stands a spring set further off."""
    proud_min = (arm.HUB_LENGTH - arm.ARM_THICKNESS) / 2 - _BAND_2PL
    face_offset_min = arm.ARM_THICKNESS / 2 + proud_min
    standoff_min = washer.THICKNESS_MIN
    clearance = {
        "north": standoff_min + face_offset_min - bar.BAR_WIDTH / 2,
        "south": standoff_min
        + bank.ROCKER_SPRING_HEIGHT[0]
        + face_offset_min
        - bar.BAR_WIDTH / 2,
    }
    for air in clearance.values():
        assert air >= bank.RUNNING_FLOOR + bank.MARGIN_SPARE
    assert clearance["north"] == pytest.approx(0.5816, abs=5e-4)
    # Without a stand-off the bar would reach the ear.
    assert face_offset_min - bar.BAR_WIDTH / 2 < 0.0
    assert bank.BAR_TO_THRUST_EAR == pytest.approx(
        washer.THICKNESS + arm.HUB_LENGTH / 2 - bar.BAR_WIDTH / 2
    )
    # The clearance is axial only: the tall ear's arch stands above the
    # cheeks, which pass over the hub at d = 0.
    assert _cheek_cap(monkeypatch, 0.0, 0.0) < bracket.EAR_ARCH_R
    # The apex set screw stands within the ear's own z band, so the bars
    # clear it as they clear the ear.
    assert (
        bracket.SET_SCREW_OFF_MID_MAX + bracket.SET_SCREW_MAJOR_DIA / 2
        < (bracket.EAR_T - bracket.EAR_T_BAND) / 2
    )


def _cheek_cap(
    monkeypatch: pytest.MonkeyPatch, notch_deeper: float, edge_lower: float
) -> float:
    """Foot-axis height over the pivot axis at d = 0 (channel_kinematics
    ``bar_bottom``: the cheeks' underside), with the bar's foot notch cut
    ``notch_deeper`` deep and the rocker's top edge ``edge_lower`` low. Both
    move the cheeks one for one; the solver carries the rest of the chain."""
    with monkeypatch.context() as patch:
        patch.setattr(ck, "_CONTACT_OFF_Y", ck._CONTACT_OFF_Y + notch_deeper)
        patch.setitem(ck.ARC, "acy", ck.ARC["acy"] - edge_lower)
        return ck.solve_state(0.0)["bar_bottom"] - frame.ROCKER_PIVOT_XY[1]


def test_bar_foot_cheeks_clear_the_hub_at_the_worst_case(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """At d = 0 each amplitude bar's foot cheeks pass over its own rocker's
    hub (the washers sit axially outboard of the end bars' cheeks,
    test_amplitude_bars_clear_both_thrust_faces_at_the_worst_case, and are
    smaller than the hub). Worst case: the notch at its deepest, the
    rocker's top edge at its lowest, and the hub at maximum material and off
    the bore axis by the printed coaxiality's radius. The one-sided bands
    (user ruling 2026-09-26) put no term on the notch or the edge; PR #1354's
    spec-owned Ø.004 coaxiality spends .002 of the air."""
    # (upper, lower) deviations: the notch deepens by its upper one, the edge
    # drops by its lower one.
    notch_deeper = bar.BOTTOM_NOTCH_DEPTH_BAND[0]
    edge_lower = -arm.TOP_EDGE_BAND[1]
    assert notch_deeper == edge_lower == 0.0
    worst = _cheek_cap(monkeypatch, notch_deeper, edge_lower)
    nominal = _cheek_cap(monkeypatch, 0.0, 0.0)
    assert worst == pytest.approx(nominal - notch_deeper - edge_lower, abs=1e-6)
    hub_max_material_r = (arm.HUB_DIA + arm.LINEAR_2PL) / 2.0
    # Ø.400 keeps ~0.44 of air at maximum material on the bore axis: the cap
    # is nominal geometry, so the bands above are what hold it.
    assert worst - hub_max_material_r == pytest.approx(0.438, abs=5e-3)
    eccentricity = arm.HUB_COAXIALITY_DIA / 2.0
    hub_top = hub_max_material_r + eccentricity
    clearance = worst - hub_top
    assert clearance >= 0.0
    assert clearance == pytest.approx(0.387, abs=5e-3)
    places = arm_notes.DRAWING_PRECISION["HubProfile"]["HubDia"]
    printed_od_band = printed_band_mm(places, unit=arm.UNIT)
    printed_hub_max_material_r = (
        round(arm.HUB_DIA / 25.4, places) * 25.4 + printed_od_band
    ) / 2.0
    printed_clearance = worst - (printed_hub_max_material_r + eccentricity)
    assert printed_clearance >= 0.0
    assert clearance - printed_clearance == pytest.approx(
        (printed_od_band - arm.LINEAR_2PL) / 2.0
    )
    # This is the source-derived OD ceiling behind the named wall exception.
    nominal_od_ceiling = 2.0 * (worst - eccentricity) - printed_od_band
    assert arm.HUB_DIA <= nominal_od_ceiling
    assert nominal_od_ceiling - arm.HUB_DIA == pytest.approx(2.0 * printed_clearance)
    # Tightening Ø0.50 to Ø.004 recovers ~0.2 radial clearance without
    # changing any nominal geometry or legitimate tolerance band.
    old_clearance = worst - (hub_max_material_r + 0.50 / 2.0)
    assert old_clearance == pytest.approx(0.188, abs=5e-3)
    assert clearance - old_clearance == pytest.approx(
        (0.50 - arm.HUB_COAXIALITY_DIA) / 2.0
    )
    # The former "+0.10" fault is now safe, so derive a genuinely looser
    # diametral zone from the actual available air, then overspend that air.
    modestly_looser = arm.HUB_COAXIALITY_DIA + 0.10
    assert worst - (printed_hub_max_material_r + modestly_looser / 2.0) >= 0.0
    contact_coaxiality = 2.0 * (worst - printed_hub_max_material_r)
    assert contact_coaxiality > arm.HUB_COAXIALITY_DIA
    looser = contact_coaxiality + arm.HUB_COAXIALITY_DIA
    fault_clearance = worst - (printed_hub_max_material_r + looser / 2.0)
    assert fault_clearance == pytest.approx(-eccentricity)
    assert fault_clearance < 0.0
    # Bilateral .XX on both formerly one-sided features closes the air.
    assert _cheek_cap(monkeypatch, arm.LINEAR_2PL, arm.LINEAR_2PL) - hub_top < 0.0
    # The washer's edge, off the axis by its bore's float on the thinnest shaft.
    washer_float = (washer.ID_MAX - (shaft.SHAFT_DIA + shaft.SHAFT_DIA_BAND[1])) / 2.0
    assert washer.OD_MAX / 2.0 + washer_float <= hub_max_material_r


def test_hub_root_fillet_clears_a_cheek_running_on_the_strap_face(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Opus #1020 r2 C2 (rule 16): the hub-to-strap roots carry a fillet up to
    HUB_ROOT_RADIUS_MAX. The bar floats axially in its foot notch, so at d = 0
    a cheek can run on the strap face, where the fillet stands its full radius
    proud of the hub wall. At the worst hub (maximum material, off the bore
    axis by the coaxiality's radius) that radius must still pass under the
    cheeks' underside."""
    worst = _cheek_cap(
        monkeypatch, bar.BOTTOM_NOTCH_DEPTH_BAND[0], -arm.TOP_EDGE_BAND[1]
    )
    places = arm_notes.DRAWING_PRECISION["HubProfile"]["HubDia"]
    hub_top = (
        round(arm.HUB_DIA / 25.4, places) * 25.4 + printed_band_mm(places, unit=arm.UNIT)
    ) / 2.0 + arm.HUB_COAXIALITY_DIA / 2.0
    air = worst - hub_top
    radius = arm.HUB_ROOT_RADIUS_MAX

    def proud(gap: float, r: float) -> float:
        """Fillet surface height over the hub wall ``gap`` out from the strap face."""
        return r - math.sqrt(r * r - (r - gap) ** 2) if gap < r else 0.0

    # The cheek's inner face anywhere from on the strap face out past the
    # fillet: the worst is on the face, the full radius.
    worst_proud = max(proud(gap, radius) for gap in np.linspace(0.0, radius, 41))
    assert worst_proud == pytest.approx(radius)
    assert radius <= air
    # Negative control: r2's R0.5 proposal, sized for a centred bar, would
    # reach a cheek running on the strap face.
    assert proud(0.0, 0.5) > air
    # The print states it as a single MAX limit (sharp is acceptable).
    assert arm_notes.HUB_ROOT_R_BAND == (0.0, -radius)
    assert arm_notes.HUB_ROOT_R_TOL_TYPE == 6  # swTolType_e.swTolMAX


def test_the_one_sided_bands_lift_the_bar_about_1_mm_at_rest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The shallow-notch and high-edge limits can only lift a bar: at most
    1.008 at rest, a steady ~0.45 deg on its channel lever, and at most 0.0036
    of fundamental at any station (0.04 % of the d = 88 term), from the exact
    chain in error_budget (rocker_arm_spec states both)."""
    notch_shallower = -bar.BOTTOM_NOTCH_DEPTH_BAND[1]
    edge_higher = arm.TOP_EDGE_BAND[0]
    lift = notch_shallower + edge_higher
    assert lift == pytest.approx(1.008)
    with monkeypatch.context() as patch:
        base = ck.solve_state(0.0)
        patch.setattr(ck, "_CONTACT_OFF_Y", ck._CONTACT_OFF_Y - notch_shallower)
        patch.setitem(ck.ARC, "acy", ck.ARC["acy"] + edge_higher)
        up = ck.solve_state(0.0)
    assert up["bar_bottom"] - base["bar_bottom"] == pytest.approx(lift, abs=1e-3)
    assert abs(up["lever_tilt"] - base["lever_tilt"]) == pytest.approx(0.45, abs=0.01)

    nom = error_budget.nominal()
    lifted = replace(
        nom,
        arc_cy=nom.arc_cy + edge_higher,
        contact_dy=nom.contact_dy - notch_shallower,
    )
    theta = np.arange(720) * 2.0 * math.pi / 720

    def fundamental(n: error_budget.Nominal, d: float) -> float:
        u = error_budget.hook_displacement(theta, d, n)
        return math.hypot(
            2.0 * float(np.mean(u * np.cos(theta))),
            2.0 * float(np.mean(u * np.sin(theta))),
        )

    stations = np.linspace(nom.d_max / 8.0, nom.d_max, 8)
    deltas = [abs(fundamental(lifted, d) - fundamental(nom, d)) for d in stations]
    assert max(deltas) < 0.004
    assert max(deltas) / fundamental(nom, nom.d_max) < 0.0005


def test_layout_reads_only_the_channel_stations_and_the_cam_plane() -> None:
    """The rocker bank reads the channel stations and, for CAM_MID_DZ alone,
    the cam_plane leaf over the cylinder gear spec: the arm plane is the cam
    plane. Not the whole cylinder_bank_layout closure (whose bank pitch reads
    gear_train/cone_incline; PR #1292 review F3), and no builder or notes
    module joins it. Its part specs add their own parts rows (their print
    unit), no machine file."""
    def machine(files: frozenset[str]) -> set[str]:
        return {t for t in files if t.startswith("machine/")}

    assert machine(config_files_of(Path(bank.__file__))) == machine(
        config_files_of(SCRIPTS / "cam_plane.py")
    ) | {"machine/channels.yaml"}
    deps = {Path(p).name for p in module_deps_of(Path(bank.__file__))}
    assert "cam_plane.py" in deps
    assert deps.isdisjoint(
        {
            "cylinder_bank_layout.py",
            "build_ch_pivot_bracket.py",
            "build_ch_pivot_shaft.py",
            "ch_rocker_arm_notes.py",
        }
    )


def test_pivot_parts_read_only_the_rocker_bank_config() -> None:
    """The shaft reads the stations and the cam plane through the rocker bank
    layout, and so does the bracket (its feet end flush with the support from
    the ear stations)."""
    shaft_cfg = config_files_of(SCRIPTS / "build_ch_pivot_shaft.py")
    machine_cfg = {t for t in shaft_cfg if t.startswith("machine/")}
    # The cam plane's cylinder gear spec also reads the shared title-block
    # and tolerance tables (its printed gear bands); only machine files are
    # the rocker bank's stations.
    assert machine_cfg == {
        t for t in config_files_of(Path(bank.__file__)) if t.startswith("machine/")
    }
    bracket_cfg = config_files_of(SCRIPTS / "build_ch_pivot_bracket.py")
    assert {t for t in bracket_cfg if t.startswith("machine/")} == machine_cfg
