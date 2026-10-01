"""SolidWorks-free contracts for the ch30-p002 platen-system refit."""

from __future__ import annotations

import math

import pytest

import _chain as chain
import build_paper_drive_assembly as assembly
import transgear_drive_collar_spec as collar
import transgear_removable_spec as band
import platen_spec as platen
import build_platen_clip as clip
import build_platen_guide as guide
import build_platen_paper as paper
import build_platen_rack as rack
import build_support_bar as support
import fillister_screw_spec as fillister
from _printed_tolerance import printed_deviations


def test_platen_envelope_preserves_fitted_top_left_and_ratio() -> None:
    assert math.isclose(platen.PLATE_HEIGHT * 2.0, platen.PLATE_WIDTH)
    assert math.isclose(assembly.PLATE_X0, -33.213)
    assert math.isclose(assembly.PLATE_Y0 + platen.PLATE_HEIGHT, 408.054)


def test_platen_furniture_cascades_with_resized_envelope() -> None:
    assert math.isclose(rack.BAR_LENGTH, platen.PLATE_WIDTH)
    assert math.isclose(guide.GUIDE_LENGTH, platen.PLATE_WIDTH)
    assert guide.SCREW_STATION_X == platen.GUIDE_HOLE_X

    clip_y0 = platen.PLATE_HEIGHT - clip.CLIP_LENGTH
    assert math.isclose(platen.SOCKET_XY[0][1], clip_y0 + clip.HOLE_INSET)
    assert math.isclose(platen.SOCKET_XY[1][1], platen.PLATE_HEIGHT - clip.HOLE_INSET)
    side_margin = (platen.PLATE_WIDTH - paper.PAPER_WIDTH) / 2.0
    assert math.isclose(side_margin, 18.2007)
    assert math.isclose(
        platen.PLATE_HEIGHT - paper.PAPER_HEIGHT - 3.0,
        51.32,
    )


def test_platen_clip_is_one_center_bridged_sheet() -> None:
    assert clip.CLIP_THICKNESS == clip.SHEET_T == 0.8
    assert math.isclose(
        clip.SCREW_RAIL_WIDTH + clip.NOTCH_WIDTH + clip.SPRING_RAIL_WIDTH,
        clip.CLIP_WIDTH,
    )
    assert math.isclose(
        2.0 * clip.NOTCH_LENGTH + clip.CENTER_BRIDGE_LENGTH,
        clip.CLIP_LENGTH,
    )
    assert clip.CENTER_BRIDGE_LENGTH == 5.0
    spring_plan_area = (
        (clip.CLIP_LENGTH - 2.0 * clip.SPRING_END_RADIUS)
        * clip.SPRING_RAIL_WIDTH
        + math.pi * clip.SPRING_END_RADIUS**2
    )
    expected = (
        clip.CLIP_LENGTH * clip.SCREW_RAIL_WIDTH
        + clip.CENTER_BRIDGE_LENGTH * clip.NOTCH_WIDTH
        + spring_plan_area
        - 2.0 * math.pi * (clip.HOLE_DIA / 2.0) ** 2
    ) * clip.SHEET_T + (
        2.0
        * math.pi
        * ((clip.SCREW_SEAT_DIA / 2.0) ** 2 - (clip.HOLE_DIA / 2.0) ** 2)
        * clip.SCREW_SEAT_BOSS_H
    )
    assert math.isclose(clip.V_FINAL, expected)


def test_platen_clip_free_halves_arch_and_return_to_sheet_plane() -> None:
    stations = clip.ARCH_FRONT_XZ
    assert stations[0] == (clip.SPRING_END_RADIUS, 0.0)
    assert stations[-1] == (clip.CLIP_LENGTH - clip.SPRING_END_RADIUS, 0.0)
    bridge_x0 = (clip.CLIP_LENGTH - clip.CENTER_BRIDGE_LENGTH) / 2.0
    bridge_x1 = bridge_x0 + clip.CENTER_BRIDGE_LENGTH
    assert stations[3] == (bridge_x0, 0.0)
    assert stations[4] == (bridge_x1, 0.0)
    assert [z for _, z in stations].count(-clip.ARCH_RISE) == 2
    assert clip.ARCH_RISE == 1.5
    assert math.isclose(clip.SPRING_END_RADIUS * 2.0, clip.SPRING_RAIL_WIDTH)


def test_platen_clip_holes_and_handed_assembly_placements_follow_flat_rail() -> None:
    assert clip.HOLE_Y == clip.SCREW_RAIL_WIDTH / 2.0
    assert clip.HOLE_Y - clip.HOLE_DIA / 2.0 > 0.0
    assert clip.HOLE_Y + clip.HOLE_DIA / 2.0 < clip.SCREW_RAIL_WIDTH
    assert tuple(row[3] for row in assembly.CLIP_PLACEMENTS) == (90.0, -90.0)
    assert math.isclose(
        clip.SPRING_RAIL_Y0 - (clip.HOLE_Y + clip.SCREW_SEAT_DIA / 2.0),
        clip.CLIP_SCREW_HEAD_CLEARANCE,
    )
    assert clip.SCREW_SEAT_DIA > clip.HEAD_DIA
    assert (
        clip.SPRING_RAIL_Y0 - (clip.HOLE_Y + clip.HEAD_DIA / 2.0)
        > clip.CLIP_SCREW_HEAD_CLEARANCE
    )

    plate_mid_x = assembly.PLATE_X0 + assembly.PLATE_WIDTH / 2.0
    expected_y = sorted(
        (
            assembly.PLATE_Y0 + assembly.PLATEN_SOCKET_XY[0][1],
            assembly.PLATE_Y0 + assembly.PLATEN_SOCKET_XY[1][1],
        )
    )
    for sx, origin_x, origin_y, rz in assembly.CLIP_PLACEMENTS:
        sin_rz = math.sin(math.radians(rz))
        socket_x = assembly.PLATE_X0 + assembly.PLATE_WIDTH - sx
        assert math.isclose(origin_x - sin_rz * clip.HOLE_Y, socket_x)
        actual_y = sorted(
            origin_y + sin_rz * local_x
            for local_x in (clip.HOLE_INSET, clip.CLIP_LENGTH - clip.HOLE_INSET)
        )
        assert all(
            math.isclose(actual, expected)
            for actual, expected in zip(actual_y, expected_y, strict=True)
        )
        spring_direction_x = -sin_rz
        assert (socket_x - plate_mid_x) * spring_direction_x < 0.0


def test_cascaded_drive_geometry_closes() -> None:
    assert rack.GAP_COUNT == 101
    assembly._assert_rack_mesh()
    assembly._assert_gear_mesh()
    assembly._assert_knob_shaft_clearance()
    assembly._assert_chain_layout()


def test_chain_slack_run_clears_the_chain_plane_parts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # R9-30: the sag the 68-link loop forces must clear every placed part in
    # the chain plane -- in plane, or axially by the band the chain sweeps.
    assembly._assert_chain_slack_clearance()
    run = assembly._slack_run_points()
    assert math.isclose(
        math.dist(run[0], assembly.KNOB_SHAFT_XY), chain.PITCH_R_T24, abs_tol=1e-3
    )
    crank_xy = (-assembly.CHAIN_CRANK_CENTRE[0], assembly.CHAIN_CRANK_CENTRE[1])
    assert math.isclose(math.dist(run[-1], crank_xy), chain.PITCH_R_T12, abs_tol=1e-3)
    # A part sitting on the sag's midpoint in the chain plane is refused...
    probe_xy = run[len(run) // 2]
    envelopes = assembly.CHAIN_PLANE_ENVELOPES
    on_path = (
        "probe",
        probe_xy,
        1.0,
        assembly.CHAIN_MID_Z - 1.0,
        assembly.CHAIN_MID_Z + 1.0,
    )
    monkeypatch.setattr(assembly, "CHAIN_PLANE_ENVELOPES", (*envelopes, on_path))
    with pytest.raises(AssertionError, match="slack run"):
        assembly._assert_chain_slack_clearance()
    # ...but the same footprint just behind the band the chain sweeps passes.
    chain_back = band.SEAT_FACE_Z + assembly.CHAIN_REACH_REAR_WORST
    behind = ("probe", probe_xy, 1.0, chain_back + 0.01, chain_back + 2.0)
    monkeypatch.setattr(assembly, "CHAIN_PLANE_ENVELOPES", (*envelopes, behind))
    assembly._assert_chain_slack_clearance()


def test_guide_lock_stations_sweep_clear_of_the_hanger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The lock stations ride the platen across its whole feed; R9-31's low
    # button heads pass under the hanger arm's front face at the printed
    # worst case.
    assembly._assert_lock_station_sweep()
    # Negative control: the stock fillister head stands into the arm.
    monkeypatch.setattr(assembly, "LOCK_SCREW_HEAD_H", fillister.HEAD_H)
    with pytest.raises(AssertionError, match="sweep into the arm"):
        assembly._assert_lock_station_sweep()


@pytest.mark.parametrize(
    ("deviation", "looser", "collides"),
    [
        # A rail printed at the plain .XX row stands the heads into the plate.
        (
            "_GUIDE_DEPTH_DEV",
            printed_deviations(assembly.GUIDE_DEPTH, 2),
            "heads .* into the arm plate as",
        ),
        # So does a lock plate whose strip thickness prints .XX...
        (
            "_LOCK_THICK_DEV",
            printed_deviations(assembly.LOCK_THICK, 2),
            "heads .* into the arm plate as",
        ),
        # ...and an arm plate whose notch depth prints .X.
        (
            "_NOTCH_DEPTH_DEV",
            printed_deviations(assembly.ARM_PLATE.NOTCH_DEPTH, 1),
            "heads .* into the arm plate as",
        ),
        # A lock plate that may run tall at .XX sweeps into the pivot spacer.
        (
            "_LOCK_HEIGHT_DEV",
            printed_deviations(assembly.LOCK_HEIGHT, 2),
            "lock plates .* into the pivot spacer",
        ),
        # A rail that may run 0.9 shallow rubs its plates on the bar.
        ("_GUIDE_DEPTH_DEV", (-0.9, 0.0), "bar's back face"),
    ],
)
def test_guide_lock_sweep_judges_every_section_at_its_printed_band(
    monkeypatch: pytest.MonkeyPatch,
    deviation: str,
    looser: tuple[float, float],
    collides: str,
) -> None:
    # Every one of these stacks clears at nominal; a part the looser print
    # accepts would still interfere, so the sweep must refuse it.
    monkeypatch.setattr(assembly, deviation, looser)
    with pytest.raises(AssertionError, match=collides):
        assembly._assert_lock_station_sweep()


def test_chain_wheels_share_the_spec_band_and_the_chain_straddles_it() -> None:
    # One chain plane, the spec's, for the links and both wheels.
    assert assembly.CHAIN_MID_Z == band.CHAIN_MID_Z
    # Both wheels (crank T12, knob T24) sit on the one band: front face at
    # the band front, rear face on the seat face (the knob side's is the
    # MHA-152 drive collar's front face, set in front of the 12T's face F).
    knob_seat_z = assembly.KNOB_COLLAR_Z0
    assert math.isclose(knob_seat_z, band.SEAT_FACE_Z)
    assert math.isclose(assembly.KNOB_SHAFT_Z0 - collar.SET_NOMINAL, knob_seat_z)
    assert math.isclose(assembly.REMOVABLE_Z0 + band.PLATE, knob_seat_z)
    assert math.isclose(
        (assembly.REMOVABLE_Z0 + knob_seat_z) / 2.0, assembly.CHAIN_MID_Z
    )
    # The knob drive pins end inside the wheel plate, short of its front face.
    tip_z = assembly.KNOB_DRIVE_PIN_Z0 - assembly.KNOB_PIN.LENGTH
    assert math.isclose(tip_z, band.DRIVE_PIN_TIP_Z)
    assert assembly.REMOVABLE_Z0 < tip_z < knob_seat_z
    # The chain's inner plates straddle the plate with running air each side,
    # and its rollers span the whole plate.
    front_inner = assembly.CHAIN_MID_Z - chain.INNER_PLATE_INNER_Z
    rear_inner = assembly.CHAIN_MID_Z + chain.INNER_PLATE_INNER_Z
    assert assembly.REMOVABLE_Z0 - front_inner >= chain.SPROCKET_CLEAR - 1e-9
    assert rear_inner - knob_seat_z >= chain.SPROCKET_CLEAR - 1e-9
    assert 2.0 * chain.BUSH_HALF_LEN >= band.PLATE


def test_knob_drive_collar_sits_between_the_seat_and_the_12t(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Round 10: the seat collar is no longer turned on the knob shaft; it is
    # the separate 4.0-long MHA-152, set at fit-up SET_NOMINAL in front of the
    # 12T's front face F.  Pushed fully rearward its rear face meets F, and
    # the disc's front face still stands behind F.
    assert collar.LENGTH == 4.0
    assert math.isclose(assembly.KNOB_SHAFT_Z0, -148.1)
    assert math.isclose(
        assembly.KNOB_COLLAR_REAR_Z, assembly.KNOB_COLLAR_Z0 + collar.LENGTH
    )
    travel = assembly.KNOB_SHAFT_Z0 - assembly.KNOB_COLLAR_REAR_Z
    assert math.isclose(travel, collar.REARWARD_TRAVEL_NOMINAL)
    assert min(collar.REARWARD_TRAVEL_RANGE) > 0.0
    assert assembly.DISC_Z0 - assembly.KNOB_SHAFT_Z0 > 0.0
    assembly._assert_knob_shaft_clearance()
    # Negative control: a disc 0.05 behind F binds on the collar pushed
    # fully rearward.
    monkeypatch.setattr(assembly, "DISC_Z0", assembly.KNOB_SHAFT_Z0 + 0.05)
    with pytest.raises(AssertionError, match="clear of the disc"):
        assembly._assert_knob_shaft_clearance()


def test_refitted_platen_clears_fixed_support_hardware() -> None:
    assert support.CLAMP_CBORE_DEPTH > 2.5
    assert support.CLAMP_CBORE_DIA > support.CLAMP_HOLE_DIA
    assert guide.LOCK_STATION_X == tuple(
        guide.GUIDE_LENGTH * fraction for fraction in (0.3, 0.7)
    )
