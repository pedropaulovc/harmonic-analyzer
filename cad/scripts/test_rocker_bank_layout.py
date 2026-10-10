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
import ch_rocker_thrust_washer_spec as washer
import ch_rocker_arm_spec as arm
import rocker_bank_layout as bank
from _buildgraph import config_files_of, module_deps_of

SCRIPTS = Path(__file__).resolve().parent
_BAND_2PL = _config.title_block("linear_2pl")["value_in"] * 25.4  # 0.508


def test_hub_length_is_the_station_pitch_and_only_comes_out_long() -> None:
    assert arm.HUB_LENGTH == pytest.approx(
        _config.machine("channels", "station_pitch_mm"), abs=1e-9
    )
    upper, lower = arm.HUB_LENGTH_BAND
    assert lower == 0.0 < upper == pytest.approx(0.05)
    assert bank.STACK_L20 == pytest.approx(bank.COUNT * arm.HUB_LENGTH)
    # #948 ruling R tightened the acceptance to +0.10/0 (a fit-up re-face).
    assert bank.STACK_L20_ACCEPT == pytest.approx(
        (bank.STACK_L20, bank.STACK_L20 + 0.10)
    )


def test_preload_rule_is_the_cylinder_bank_rule() -> None:
    """The rocker layout shares ONE datum with cylinder_bank_layout (the cam
    plane, its arm plane, from the cam_plane leaf) but restates the set-blade,
    preload and fit-up compensation rules, because it has its own spring and datum ear; this
    pins the two in lockstep."""
    assert bank.MARGIN_SPARE == drum_bank.MARGIN_SPARE
    assert bank.FEELER_STEP == drum_bank.FEELER_STEP
    assert bank.ROCKER_SPRING_SET_BAND == drum_bank.BANK_SPRING_SET_BAND
    assert bank.PRELOAD_LIMITS == drum_bank.PRELOAD_LIMITS
    assert bank.MIC_RESIDUAL == drum_bank.MIC_RESIDUAL
    assert bank.NORTH_EAR_LOCATE_BAND == drum_bank.BACK_STRAP_LOCATE_BAND


def test_the_bank_is_preloaded_by_its_spring() -> None:
    # #948 ruling R: the 0.45 leaf became a 9714K24 wave spring set on a 0.60
    # blade; its whole set band stays in the spring's working range at a
    # light, single-digit-newton preload; no end play, no shaft float.
    assert bank.ROCKER_SPRING_SET == pytest.approx(0.60)
    assert bank.ROCKER_SPRING_HEIGHT == pytest.approx((0.50, 0.70))
    assert bank.ROCKER_PRELOAD == pytest.approx((2.17, 9.18), abs=0.01)
    assert bank.ROCKER_SPRING_Z == (bank.SOUTH_EAR_INNER_Z, bank.SOUTH_WASHER_Z[0])
    assert not hasattr(bank, "ROCKER_END_PLAY")
    # The north washer replaces the shaft's shoulder in the datum chain, its
    # stock band mic-compensated as the shoulder's was (user, 2026-10-10).
    assert bank.NORTH_DATUM_STACK == pytest.approx(
        {"north ear DRO locate": 0.10, "north washer, mic-compensated": 0.013}
    )


def test_the_rocker_spring_fits_the_shaft_and_under_the_bar_foot() -> None:
    import vn_rocker_bank_spring_spec as spring

    # The ch0 bar's foot passes over it as over the washer and the hubs.
    assert spring.OD + spring.OD_BAND[0] <= washer.OD == arm.HUB_DIA
    # It bears on the washer's face clear of the washer's bore.
    assert spring.OD + spring.OD_BAND[1] > washer.BORE_DIA + washer.BORE_BAND[0]
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
    MHA-CH-009 thrust washer against the north ear's inner face, the bank's
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
    assert bank.NORTH_EAR_INNER_Z == pytest.approx(70.851, abs=5e-4)
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
    assert bank.SOUTH_EAR_INNER_Z == pytest.approx(-72.459, abs=5e-4)


def test_the_washers_are_cut_from_1_32_stock() -> None:
    """User, 2026-10-10: 1/32 stock (was 1/16) keeps the south bracket's
    foot room for its hold-down beside the 8-thick ear."""
    assert washer.STOCK_THICKNESS == pytest.approx(25.4 / 32)
    assert washer.THICKNESS == 0.79
    assert washer.STOCK_THICKNESS_RANGE == pytest.approx((0.7175, 0.8700), abs=5e-4)


def test_brackets_sit_on_their_ears_and_move_in_from_78() -> None:
    south, north = bank.PIVOT_BRACKET_Z
    assert south == pytest.approx(bank.SOUTH_EAR_INNER_Z - bracket.EAR_T / 2)
    assert north == pytest.approx(bank.NORTH_EAR_INNER_Z + bracket.EAR_T / 2)
    assert bracket.EAR_T == 8.0
    assert (south, north) == pytest.approx((-76.459, 74.851), abs=5e-4)
    assert bank.STACK_MID_Z - south < 78.0
    assert north - bank.STACK_MID_Z < 78.0
    # Both feet stay on the rocker-arm-support's +-88.9 top.
    assert south - bracket.EAR_T / 2 > -88.9
    assert north + bracket.EAR_T / 2 < 88.9


def test_shaft_is_a_plain_rod_spanning_both_ears() -> None:
    assert bank.PIVOT_SHAFT_SOUTH_Z == pytest.approx(bank.SOUTH_EAR_OUTER_Z)
    assert bank.PIVOT_SHAFT_NORTH_Z == pytest.approx(bank.NORTH_EAR_OUTER_Z)
    assert bank.PIVOT_SHAFT_LENGTH == pytest.approx(
        bank.NORTH_EAR_OUTER_Z - bank.SOUTH_EAR_OUTER_Z
    )
    assert bank.PIVOT_SHAFT_LENGTH == pytest.approx(159.31, abs=5e-3)
    assert bank.PIVOT_SHAFT_OVERALL_LENGTH == pytest.approx(
        bank.PIVOT_SHAFT_LENGTH + 2 * shaft.DOME_HEIGHT
    )
    # Domed 1.5 like the arbor ends (user, #743 Q4): SR 4.11 on the 1/4 rod.
    assert shaft.DOME_HEIGHT == 1.5
    assert shaft.DOME_SPHERE_RADIUS == pytest.approx(4.11, abs=5e-3)
    assert 0.0 < shaft.DOME_HEIGHT <= shaft.SHAFT_DIA / 2
    for gone in ("SHOULDER_DIA", "SHOULDER_LENGTH", "JOURNAL_LENGTH", "RELIEF_DIA"):
        assert not hasattr(shaft, gone)


def test_hub_and_washer_share_one_od_over_each_wall_floor() -> None:
    """Main 2026-09-26: hub and washer share O10.20; each part's own rule-12
    floor is derived in its spec (10.04 hub, 10.11 washer), never typed."""
    assert arm.LINEAR_2PL == pytest.approx(_BAND_2PL)
    assert washer.OD == arm.HUB_DIA
    assert arm.HUB_DIA >= arm.HUB_DIA_MIN == pytest.approx(10.04)
    assert washer.OD >= washer.OD_MIN == pytest.approx(10.11)
    assert washer.BORE_DIA == bracket.BORE_DIA


def test_the_set_screws_bite_flats_clear_of_the_hubs() -> None:
    """User, 2026-10-10: one #4-40 set screw down through each ear's apex onto
    a flat at that ear's mid-plane holds the shaft. At the fit-up's worst
    axial wander (the north end set flush; the south ear moved by the stack's
    acceptance, the blade's set and both washers' stock bands) each cup stays
    wholly on its flat, and no hub's bore rides over a flat's edge (the ear,
    the washer and the spring may: none of them runs on the shaft)."""
    south, north = bank.PIVOT_BRACKET_Z
    assert bank.PIVOT_SHAFT_FLAT_STATIONS == pytest.approx(
        (bank.PIVOT_SHAFT_NORTH_Z - south, bank.PIVOT_SHAFT_NORTH_Z - north)
    )
    assert bank.PIVOT_SHAFT_FLAT_STATIONS == pytest.approx((155.31, 4.0), abs=5e-3)
    assert shaft.NORTH_FLAT_STATION == bracket.EAR_T / 2
    assert bank.FLAT_OFFSET_MAX == pytest.approx((0.6099, 0.25), abs=5e-4)
    washer_thin = washer.STOCK_THICKNESS_RANGE[0]
    ear_half_min = (bracket.EAR_T - bracket.EAR_T_BAND) / 2
    hub_free = (
        ear_half_min + washer_thin + bank.ROCKER_SPRING_HEIGHT[0],
        ear_half_min + washer_thin,
    )
    assert bank.FLAT_RUN_MAX == pytest.approx(hub_free)
    for offset, run_max in zip(bank.FLAT_OFFSET_MAX, hub_free, strict=True):
        reach = offset + shaft.FLAT_STATION_BAND + bracket.SET_SCREW_STATION_BAND
        assert reach + shaft.SET_SCREW_CUP_DIA / 2 <= shaft.FLAT_LENGTH_RANGE[0] / 2
        assert (
            offset + shaft.FLAT_STATION_BAND + shaft.FLAT_LENGTH_RANGE[1] / 2
            <= run_max - bank.RUNNING_FLOOR
        )
    assert shaft.flat_chord(shaft.FLAT_DEPTH_RANGE[0]) > shaft.SET_SCREW_CUP_DIA + 1.0


def test_south_apex_stays_on_the_support_at_the_worst_case() -> None:
    """Main (a): both ends domed. The plain end is cut flush to +0.5 past the
    south ear, then domed; the apex must stay over the rocker-arm-support's
    -88.9 end. Outboard of the south ear at the shaft's height there is only
    the support's own top, so its end is the bound. The set screws hold the
    shaft, so it never floats south."""
    assert bank.PLAIN_END_CUT_BAND == (0.5, 0.0)
    assert bank.SOUTH_APEX_REACH_MAX == pytest.approx(0.5 + 1.5)
    apex_z = bank.SOUTH_EAR_OUTER_Z - bank.SOUTH_APEX_REACH_MAX
    assert apex_z == pytest.approx(-82.459, abs=5e-4)
    assert apex_z - (-88.9) >= 2.0


def test_amplitude_bars_clear_both_thrust_faces_at_the_worst_case(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The bar straddles its arm plate (z_mid +- BAR_WIDTH/2) while the hub
    face's offset from the plate prints at .XX. A plate-wide thrust face on
    an end hub would reach the end bar; the washers (under the bar foot, like
    the hubs) stand both ears off. The washer is 1/32 stock, so the mill's
    band is its thin side; the south ear stands a spring set further off."""
    proud_min = (arm.HUB_LENGTH - arm.ARM_THICKNESS) / 2 - _BAND_2PL
    face_offset_min = arm.ARM_THICKNESS / 2 + proud_min
    standoff_min = washer.STOCK_THICKNESS_RANGE[0]
    clearance = {
        "north": standoff_min + face_offset_min - bar.BAR_WIDTH / 2,
        "south": standoff_min
        + bank.ROCKER_SPRING_HEIGHT[0]
        + face_offset_min
        - bar.BAR_WIDTH / 2,
    }
    for air in clearance.values():
        assert air >= bank.RUNNING_FLOOR + bank.MARGIN_SPARE
    assert clearance["north"] == pytest.approx(0.5625, abs=5e-4)
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
    held no larger than the hub). Worst case: the notch at its deepest, the
    rocker's top edge at its lowest, and the hub at maximum material and off
    the bore axis by the printed coaxiality's radius. The one-sided bands
    (user ruling 2026-09-26) put no term on the notch or the edge; the
    coaxiality note (Main 2026-09-26) spends 0.25 of the air."""
    # (upper, lower) deviations: the notch deepens by its upper one, the edge
    # drops by its lower one.
    notch_deeper = bar.BOTTOM_NOTCH_DEPTH_BAND[0]
    edge_lower = -arm.TOP_EDGE_BAND[1]
    assert notch_deeper == edge_lower == 0.0
    worst = _cheek_cap(monkeypatch, notch_deeper, edge_lower)
    nominal = _cheek_cap(monkeypatch, 0.0, 0.0)
    assert worst == pytest.approx(nominal - notch_deeper - edge_lower, abs=1e-6)
    hub_max_material_r = (arm.HUB_DIA + _BAND_2PL) / 2.0
    # O10.20 keeps ~0.29 of air at maximum material on the bore axis: the cap
    # (Ø11.29) is nominal geometry, so the bands above are what hold it.
    assert worst - hub_max_material_r == pytest.approx(0.291, abs=5e-3)
    eccentricity = arm_notes.HUB_COAXIALITY_DIA / 2.0
    hub_top = hub_max_material_r + eccentricity
    assert worst - hub_top >= 0.0
    assert worst - hub_top == pytest.approx(0.041, abs=5e-3)
    assert f"WITHIN Ø{arm_notes.HUB_COAXIALITY_DIA:.2f}" in arm_notes.DRAWING_NOTES
    # A looser coaxiality would put the cheeks into the hub, and so would the
    # bilateral .XX the notch and the edge printed before -- every band binds.
    looser = arm_notes.HUB_COAXIALITY_DIA + 0.10
    assert worst - (hub_max_material_r + looser / 2.0) < 0.0
    assert _cheek_cap(monkeypatch, _BAND_2PL, 0.0) - hub_top < 0.0
    assert _cheek_cap(monkeypatch, 0.0, _BAND_2PL) - hub_top < 0.0
    assert (washer.OD + _BAND_2PL) / 2.0 <= hub_max_material_r


def test_the_one_sided_bands_lift_the_bar_at_most_1_mm_at_rest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The shallow-notch and high-edge limits can only lift a bar: at most
    1.0 at rest, a steady ~0.45 deg on its channel lever, and at most 0.0036
    of fundamental at any station (0.04 % of the d = 88 term), from the exact
    chain in error_budget (rocker_arm_spec states both)."""
    notch_shallower = -bar.BOTTOM_NOTCH_DEPTH_BAND[1]
    edge_higher = arm.TOP_EDGE_BAND[0]
    lift = notch_shallower + edge_higher
    assert lift == pytest.approx(1.0)
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
    module joins it."""
    assert config_files_of(Path(bank.__file__)) == config_files_of(
        SCRIPTS / "cam_plane.py"
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
