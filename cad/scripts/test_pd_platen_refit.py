"""SolidWorks-free contracts for the ch30-p002 platen-system refit."""

from __future__ import annotations

import math

import pytest

import _chain as chain
import build_pd_paper_drive_assembly as assembly
import pd_transgear_drive_collar_spec as collar
import pd_transgear_removable_spec as band
import pd_platen_spec as platen
import build_pd_platen_clip as clip
import build_pd_platen_guide as guide
import paper_drive_geom as paper_geometry
import pd_platen_rack_spec as rack
import build_pd_support_bar as support
import vn_fillister_screw_spec as fillister
import vn_platen_clip_screw_spec as clip_screw
from _printed_tolerance import printed_deviations


def test_platen_envelope_preserves_fitted_top_left_and_ratio() -> None:
    assert math.isclose(platen.PLATE_HEIGHT * 2.0, platen.PLATE_WIDTH)
    assert math.isclose(assembly.PLATE_X0_PHOTO, -33.213)
    assert math.isclose(assembly.PLATE_Y0 + platen.PLATE_HEIGHT, 408.054)


def test_the_rack_is_flush_with_the_platen_and_a_gap_sits_over_the_stud() -> None:
    """Codex P2 (724f78f26): MHA-PD-000 solders the rack ends flush with the
    platen's, so the model places it flush, and the mesh phasing (a rack gap
    centre on the feed pinion's +90-deg tooth over the stud) moves the platen
    off its photo x by the least shift instead of the rack along the platen."""
    assert rack.BAR_LENGTH == platen.PLATE_WIDTH
    assert assembly.RACK_X0 == assembly.PLATE_X0
    # Rx180 keeps local +X along machine +X: both bodies run +X from origin.
    assert assembly.RACK_X0 + rack.BAR_LENGTH == assembly.PLATE_X0 + platen.PLATE_WIDTH
    gaps = (assembly.STUD_XY[0] - assembly.RACK_X0 - rack.FIRST_GAP_X) / rack.PITCH
    assert gaps == pytest.approx(round(gaps), abs=1e-9)
    shift = assembly.PLATE_X0 - assembly.PLATE_X0_PHOTO
    assert abs(shift) <= rack.PITCH / 2.0
    photo_gap = (
        assembly.STUD_XY[0] - assembly.PLATE_X0_PHOTO - rack.FIRST_GAP_X
    ) / rack.PITCH
    assert shift == pytest.approx((photo_gap - round(photo_gap)) * rack.PITCH)
    assembly._assert_rack_mesh()


def test_platen_furniture_cascades_with_resized_envelope() -> None:
    assert math.isclose(rack.BAR_LENGTH, platen.PLATE_WIDTH)
    assert math.isclose(guide.GUIDE_LENGTH, platen.PLATE_WIDTH)
    assert guide.SCREW_STATION_X == platen.GUIDE_HOLE_X

    clip_y0 = platen.PLATE_HEIGHT - clip.CLIP_LENGTH
    assert math.isclose(platen.SOCKET_XY[0][1], clip_y0 + clip.HOLE_INSET)
    assert math.isclose(platen.SOCKET_XY[1][1], platen.PLATE_HEIGHT - clip.HOLE_INSET)
    # The sheet sits 3.6 to -X of centre (the rack sweep; paper_drive_geom),
    # still wholly between the two brass edge clips: each clip's screw rail
    # hugs its plate edge and its spring rail points inward, short of the sheet.
    left = paper_geometry.RECORDING_PAPER_LEFT_INSET_MM
    right = paper_geometry.RECORDING_PAPER_RIGHT_INSET_MM
    assert math.isclose(left, 14.6)
    assert math.isclose(
        left + paper_geometry.RECORDING_PAPER_WIDTH_MM + right, platen.PLATE_WIDTH
    )
    clip_inner_edges = (
        platen.SOCKET_XY[0][0] - clip.HOLE_Y + clip.CLIP_WIDTH,
        platen.PLATE_WIDTH - platen.SOCKET_XY[2][0] - clip.HOLE_Y + clip.CLIP_WIDTH,
    )
    assert (
        min(platen.SOCKET_XY[0][0], platen.PLATE_WIDTH - platen.SOCKET_XY[2][0])
        > clip.HOLE_Y
    )
    assert left - clip_inner_edges[0] > 2.0
    assert right - clip_inner_edges[1] > 2.0
    assert math.isclose(
        platen.PLATE_HEIGHT - paper_geometry.RECORDING_PAPER_HEIGHT_MM - 3.0,
        51.32,
    )


def test_platen_clip_is_one_center_bridged_sheet() -> None:
    assert clip.CLIP_THICKNESS == clip.SHEET_T == 0.8
    assert math.isclose(
        clip.SCREW_RAIL_WIDTH + clip.NOTCH_WIDTH + clip.SPRING_RAIL_WIDTH,
        clip.CLIP_WIDTH,
    )
    # ch22 img03: equal 32-px rails either side of a 4-px slit.
    assert math.isclose(clip.SCREW_RAIL_WIDTH, clip.SPRING_RAIL_WIDTH)
    assert math.isclose(clip.NOTCH_WIDTH / clip.CLIP_WIDTH, 4.0 / 68.0)
    assert math.isclose(
        clip.BRIDGE_X0 + clip.CENTER_BRIDGE_LENGTH + clip.BRIDGE_X0, clip.CLIP_LENGTH
    )
    assert math.isclose(clip.SLIT_END_RADIUS * 2.0, clip.NOTCH_WIDTH)
    flat_plan_area = (
        clip.CLIP_LENGTH * clip.SCREW_RAIL_WIDTH
        - (4.0 - math.pi)
        / 2.0
        * (clip.SCREW_RAIL_END_RADIUS**2 + clip.SCREW_RAIL_SLIT_RADIUS**2)
        + clip.CENTER_BRIDGE_LENGTH * clip.NOTCH_WIDTH
        - math.pi * clip.SLIT_END_RADIUS**2
    )
    spring_plan_area = (
        clip.MID_SURFACE_LENGTH * clip.SPRING_RAIL_WIDTH
        + math.pi * clip.SPRING_END_RADIUS**2
    )
    expected = (
        flat_plan_area + spring_plan_area - 2.0 * math.pi * (clip.HOLE_DIA / 2.0) ** 2
    ) * clip.SHEET_T
    assert math.isclose(clip.V_FINAL, expected)
    assert not hasattr(clip, "SCREW_SEAT_BOSS_H")


def test_platen_clip_spring_rail_follows_its_knobs() -> None:
    # The thin extrusion's width, start offset and wall are all equation-bound;
    # the build names them by value, so the three values must be distinct.
    drives = {name: (value, expr) for name, value, expr in clip.SPRING_RAIL_DRIVES}
    assert drives == {
        "RailWidth": (clip.SPRING_RAIL_WIDTH, '"SpringRailW"'),
        "StartOffset": (clip.SPRING_RAIL_Y0, '"SpringRailY0"'),
        "WallT": (clip.SHEET_T, '"SheetT"'),
    }
    values = sorted(value for value, _ in drives.values())
    assert all(b - a > 0.1 for a, b in zip(values, values[1:]))
    assert "SpringRail" not in clip.BOSS_DRIVES
    # The native flex predicts each edited volume analytically and moves it
    # well past the 0.5 % volume tolerance.
    neutrals = {"sheet_t": clip.SHEET_T, "notch_w": clip.NOTCH_WIDTH}
    assert clip.clip_volumes() == clip.clip_volumes(**neutrals)
    for knob, neutral, flexed, knob_arg in clip.EQUATION_FLEX:
        assert neutrals[knob_arg] == neutral
        knobs = {**neutrals, knob_arg: flexed}
        flat, spring, ends, holes = clip.clip_volumes(**knobs)
        flexed_volume = flat + spring + ends - holes
        assert abs(flexed_volume - clip.V_FINAL) > 0.02 * clip.V_FINAL, knob
        # The end round stays wholly on the flat tip at the flexed slit width.
        spring_w = clip.CLIP_WIDTH - clip.SCREW_RAIL_WIDTH - knobs["notch_w"]
        assert spring_w <= clip.HOLE_INSET


def test_platen_clip_free_halves_bow_smoothly_and_return_to_sheet_plane() -> None:
    # Three equal tangent arcs per free half (concave, crown, concave): the
    # run and the rise close, so the bow lands back in the sheet plane at the
    # bridge with no crease.
    r, a = clip.BEND_RADIUS, clip.BEND_ANGLE
    assert math.isclose(4.0 * r * math.sin(a), clip.BOW_RUN)
    assert math.isclose(2.0 * r * (1.0 - math.cos(a)), clip.ARCH_RISE)
    assert clip.ARCH_RISE == 1.5
    assert clip.BOW_RUN == pytest.approx(clip.BRIDGE_X0 - clip.HOLE_INSET)
    # Gentle brass bend, far above the sheet thickness.
    assert r > 20.0 * clip.SHEET_T
    near = clip._bow_points(clip.HOLE_INSET, 0.0)
    for key in ("p1", "p2"):
        assert math.dist(near[key], near["c2"]) == pytest.approx(r)
    assert math.dist(near["p1"], near["c1"]) == pytest.approx(r)
    assert math.dist(near["p2"], near["c3"]) == pytest.approx(r)
    assert near["c2"][1] + r == pytest.approx(clip.ARCH_RISE)
    # The end round lies wholly on the flat tip, before the bow lifts.
    assert 2.0 * clip.SPRING_END_RADIUS <= clip.HOLE_INSET
    assert math.isclose(clip.SPRING_END_RADIUS * 2.0, clip.SPRING_RAIL_WIDTH)


def test_platen_clip_screws_seat_on_the_flat_sheet_with_full_engagement() -> None:
    # The user's #2-56 brass fillister (90114A124): its head lies wholly on the
    # 4.23 screw rail, and the platen's through tap is the same thread.
    assert clip_screw.SKU == "90114A124" and clip_screw.THREAD == "#2-56"
    assert (platen.SOCKET_SPEC.kind, platen.SOCKET_SPEC.size) == ("tapped", "#2-56")
    assert clip.HOLE_DIA == clip.CLEARANCE_MM[("#2", "normal")]
    assert clip_screw.HEAD_DIA < clip.SCREW_RAIL_WIDTH
    assert clip.CLIP_THICKNESS + platen.SOCKET_THREAD_ENGAGEMENT == pytest.approx(
        clip_screw.SHANK_LEN
    )
    assert platen.SOCKET_THREAD_ENGAGEMENT >= 1.5 * clip.THREAD_MAJOR_MM["#2-56"]
    assert platen.SOCKET_BOSS_H == pytest.approx(1.70)


def test_platen_clip_holes_and_handed_assembly_placements_follow_flat_rail() -> None:
    assert clip.HOLE_Y == clip.SCREW_RAIL_WIDTH / 2.0
    assert clip.HOLE_Y - clip.HOLE_DIA / 2.0 > 0.0
    assert clip.HOLE_Y + clip.HOLE_DIA / 2.0 < clip.SCREW_RAIL_WIDTH
    assert tuple(row[3] for row in assembly.CLIP_PLACEMENTS) == (90.0, -90.0)
    assert clip.HEAD_TO_SPRING_RAIL == pytest.approx(
        clip.SPRING_RAIL_Y0 - (clip.HOLE_Y + clip.HEAD_DIA / 2.0)
    )
    assert clip.HEAD_TO_SPRING_RAIL > 0.25

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
    assert rack.GAP_COUNT == math.floor(rack.BAR_LENGTH / rack.PITCH)
    assembly._assert_rack_mesh()
    assembly._assert_gear_mesh()
    assembly._assert_knob_shaft_clearance()
    assembly._assert_chain_layout()


def test_chain_slack_run_clears_the_chain_plane_parts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # R9-30: the solved integer-link sag must clear every placed part in
    # the chain plane -- in plane, or axially by the band the chain sweeps.
    assembly._assert_chain_slack_clearance()
    run = assembly._slack_run_points()
    assert math.isclose(
        math.dist(run[0], assembly.KNOB_SHAFT_XY), chain.KNOB_PITCH_R, abs_tol=1e-3
    )
    crank_xy = (-assembly.CHAIN_CRANK_CENTRE[0], assembly.CHAIN_CRANK_CENTRE[1])
    assert math.isclose(math.dist(run[-1], crank_xy), chain.CRANK_PITCH_R, abs_tol=1e-3)
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
    # slotted pan heads, on the 1/16-sheet lock backs, pass under the hanger
    # arm's front face at the printed worst case.
    assembly._assert_lock_station_sweep()
    # Negative control: the stock fillister head stands into the arm.
    monkeypatch.setattr(assembly, "LOCK_SCREW_HEAD_H", fillister.HEAD_H)
    with pytest.raises(AssertionError, match="sweep into the arm"):
        assembly._assert_lock_station_sweep()


def test_clip_screw_bosses_sweep_clear_of_the_bar_and_hanger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The rear clip-screw bosses ride the platen back across its whole feed:
    # they pass above the bar's top edge and clear every fixed hanger section.
    lines: list[str] = []
    monkeypatch.setattr(assembly, "log", lines.append)
    assembly._assert_lock_station_sweep()
    (line,) = lines
    assert "clip-screw bosses " in line
    assert "clip-screw bosses on the bar " in line
    # Negative control: a boss station dropped onto the bar's top edge.
    x, _ = assembly.CLIP_SCREW_XY[0]
    monkeypatch.setattr(assembly, "CLIP_SCREW_XY", ((x, assembly.BAR_TOP_Y),))
    with pytest.raises(AssertionError, match="clip-screw boss"):
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
        # So does a lock plate whose thickness prints .XX, not its sheet band...
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
    # Both selected wheels sit on the one band: front face at
    # the band front, rear face on the seat face (the knob side's is the
    # MHA-PD-022 drive collar's front face, set in front of the 12T's face F).
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
    # The separate MHA-PD-022 collar is faced at fit-up so its rear face
    # seats on the 12T's front face F; the disc's front face stands behind F.
    assert collar.LENGTH == collar.SET_NOMINAL
    assert collar.SEAT_MIN_FROM_F <= collar.LENGTH <= collar.SEAT_MAX_FROM_F
    assert math.isclose(assembly.KNOB_SHAFT_Z0, -148.1)
    assert math.isclose(
        assembly.KNOB_COLLAR_REAR_Z, assembly.KNOB_COLLAR_Z0 + collar.LENGTH
    )
    assert math.isclose(assembly.KNOB_COLLAR_REAR_Z, assembly.KNOB_SHAFT_Z0)
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
