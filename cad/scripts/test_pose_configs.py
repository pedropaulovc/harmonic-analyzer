"""Offline contracts for the saved pose configurations (poses.yaml + _pose_configs)."""

from __future__ import annotations

import math

import _buildgraph
import _config
import _pose_configs as pc
import build_channel_assembly as ch
from pathlib import Path


def test_configuration_roles_and_three_amplitude_states():
    poses = _config.poses()
    rows = _config.channels()
    expected_default = [
        0.0,
        4.2105,
        8.4211,
        12.6316,
        16.8421,
        21.0526,
        25.2632,
        29.4737,
        33.6842,
        37.8947,
        42.1053,
        46.3158,
        50.5263,
        54.7368,
        58.9474,
        63.1579,
        67.3684,
        71.5789,
        75.7895,
        80.0,
    ]
    default_amplitudes = [float(row["amplitude_mm"]) for row in rows]
    parallel_amplitudes = [float(poses["parallel"]["target_amplitude_mm"])] * len(rows)
    sinusoid_amplitudes = list(default_amplitudes)

    assert list(_config.assembly_configuration_roles().items()) == [
        ("default", pc.REST_CONFIGURATION),
        ("parallel", "parallel-bank"),
        ("sinusoid", "sinusoid-6-cranks"),
    ]
    assert default_amplitudes == expected_default
    assert default_amplitudes == sorted(default_amplitudes)
    assert parallel_amplitudes == [0.0] * 20
    assert sinusoid_amplitudes == expected_default
    assert _config.machine("amplitude", "preset") == "fan"
    fundamental = float(_config.machine("amplitude", "fundamental_station_mm"))
    assert all(
        abs(amplitude - fundamental * j / 19.0) < 5e-4
        for j, amplitude in enumerate(default_amplitudes)
    )
    assert int(poses["sinusoid"]["crank_turns"]) == poses["sinusoid"]["crank_turns"] > 0


def test_cam_pose_reproduces_the_rest_pose_at_zero_cranks():
    for k in (1, 10, 20):
        st = ch.solve_cam_pose(0.0, k)
        assert abs(st["arm_tilt"] - ch._ARC["arm_tilt"]) < 1e-9
        assert abs(st["rod_tilt"] - ch._ARC["rod_tilt"]) < 1e-9
        assert abs(st["ring_x"] - ch.RING_CENTER[0]) < 1e-9
        assert abs(st["ring_y"] - ch.RING_CENTER[1]) < 1e-9


def test_cam_pose_is_periodic_in_whole_cam_turns():
    # gear k turns k/80 rev per crank: 80 cranks bring every cam home
    for k in (1, 7, 20):
        a, b = ch.solve_cam_pose(0.0, k), ch.solve_cam_pose(80.0, k)
        assert abs(a["arm_tilt"] - b["arm_tilt"]) < 1e-9
    # and the k = 20 cam completes a turn every 4 cranks
    a, b = ch.solve_cam_pose(1.0, 20), ch.solve_cam_pose(5.0, 20)
    assert abs(a["ring_x"] - b["ring_x"]) < 1e-9


def test_cam_pose_swings_the_rocker_from_the_stroke_top():
    """Rest (lobe up) IS the top of the stroke (ch14: the 0-crank tip row is
    level at the top), so over one cam turn the rocker only dips: max tilt ~0 at
    rest, min ~ the full 2e throw over the lever arm."""
    tilts = [
        ch.solve_cam_pose(t, 20)["arm_tilt"] for t in [i * 0.25 for i in range(16)]
    ]
    assert abs(max(tilts)) < 0.01, tilts
    throw = math.degrees(math.atan2(2.0 * ch.CAM_ECC, ch.ARM_ROD_LEVER))
    assert -1.2 * throw < min(tilts) < -0.8 * throw, (min(tilts), throw)


def test_sinusoid_gear_residuals_are_whole_tooth_pitches():
    """120-tooth cylinder gears: every residual after whole cranks is a whole
    number of 3-degree tooth pitches, so the cone meshes are geometrically
    unchanged and only the cams move (build_drive_train_assembly)."""
    n = _config.poses()["sinusoid"]["crank_turns"]
    for row in _config.channels():
        k = int(row["harmonic_n"])
        residual = 360.0 * n * k / 80.0
        assert abs(residual / 3.0 - round(residual / 3.0)) < 1e-9, (k, residual)
        # cone gear k has 6k teeth and the cone shaft turns n/4 times: whole pitches too
        cone = 360.0 * n / 4.0 * (6 * k) / 360.0
        assert abs(cone - round(cone)) < 1e-9


def test_harmonic_mapping_matches_the_ladders():
    """Channel j rides cylinder-gear-{j+1}; both read harmonic_n from channels.yaml
    row j (drive-train spike 2026-09-02: instance 1 turned 20/80 per crank)."""
    rows = _config.channels()
    assert [r["index"] for r in rows] == list(range(len(rows)))
    assert rows[0]["harmonic_n"] == 20 and rows[-1]["harmonic_n"] == 1


def test_pose_helpers_are_pure():
    assert pc.pose_mate_name("bar_amplitude_00") == "POSE_bar_amplitude_00"
    assert pc.pose_dim_name("x") == "D1@POSE_x"
    assert pc.POSE_PREFIX != "DRIVE_"
    assert pc.wrap_deg(190.0) == -170.0 and pc.wrap_deg(-190.0) == 170.0
    assert (
        abs(
            pc.yaw_deg(
                [0.0, 1.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0, 0, 0, 1, 0, 0, 0]
            )
            - 90.0
        )
        < 1e-12
    )


def test_pose_module_rides_the_three_assembly_recipes():
    scripts = Path(_buildgraph.__file__).resolve().parent
    for stem in (
        "build_channel_assembly.py",
        "build_drive_train_assembly.py",
        "build_harmonic_analyzer_assembly.py",
    ):
        deps = {Path(p).name for p in _buildgraph.module_deps_of(scripts / stem)}
        assert "_pose_configs.py" in deps, (stem, sorted(deps))
        assert "poses.yaml" in _buildgraph.config_files_of(scripts / stem), stem


def _roof_corners(fx, fy, beta):
    """Both notch-roof corners of a bar at foot (fx, fy) with solve_state's swing
    root ``beta`` (up vector (sin b, cos b), +X edge (cos b, -sin b))."""
    s, c = math.sin(beta), math.cos(beta)
    return [
        (
            fx + side * ch._CONTACT_OFF_X * c + ch._CONTACT_OFF_Y * s,
            fy - side * ch._CONTACT_OFF_X * s + ch._CONTACT_OFF_Y * c,
        )
        for side in (-1.0, 1.0)
    ]


def test_default_fanned_bar_roof_lies_flat_on_its_arc():
    # The photographed monotonic fan is the build state. At every sampled
    # Default station both notch-roof corners lie on the R800 rocker arc.
    for amplitude in (0.0, 40.0, 80.0):
        state = ch.solve_state(amplitude)
        beta = -math.radians(state["bar_tilt"])
        for cx, cy in _roof_corners(ch.PIVOT[0] + amplitude, state["bar_bottom"], beta):
            radius = math.hypot(cx - ch._ARC["acx"], cy - ch._ARC["acy"])
            assert abs(radius - ch.ARM_TOP_RADIUS) < 0.01, (
                amplitude,
                cx,
                cy,
                radius,
            )
        assert abs(ch.foot_radius(amplitude) - ch.foot_radius(0.0)) < 0.02


def test_sinusoid_foot_reproduces_each_default_amplitude_at_zero_cranks():
    for amplitude in (0.0, 42.1053, 80.0):
        default = ch.solve_state(amplitude)
        sinusoid = ch.solve_sinusoid_foot(ch.solve_cam_pose(0.0, 20), amplitude)
        assert abs(sinusoid["theta_deg"]) < 1e-9
        assert sinusoid["foot_x"] == ch.PIVOT[0] + amplitude
        assert abs(sinusoid["foot_y"] - default["bar_bottom"]) < 0.01
        assert abs(sinusoid["foot_r"] - ch.foot_radius(amplitude)) < 0.01
        assert abs(sinusoid["lever_tilt"] - default["lever_tilt"]) < 0.01


def test_sinusoid_foot_keeps_nonzero_default_stations_on_the_turned_arc():
    rows = _config.channels()
    crank_turns = float(_config.poses()["sinusoid"]["crank_turns"])
    samples = (1, 8, 14, 17, 19)
    lifts = []
    for j in samples:
        amplitude = float(rows[j]["amplitude_mm"])
        harmonic = int(rows[j]["harmonic_n"])
        state = ch.solve_cam_pose(crank_turns, harmonic)
        sinusoid = ch.solve_sinusoid_foot(state, amplitude)
        assert amplitude > 0.0
        assert sinusoid["foot_x"] == ch.PIVOT[0] + amplitude
        assert abs(sinusoid["theta_deg"] + state["arm_tilt"]) < 1e-4

        beta = -math.radians(sinusoid["bar_tilt"])
        radii = [
            math.hypot(
                cx - sinusoid["arc_cx"],
                cy - sinusoid["arc_cy"],
            )
            for cx, cy in _roof_corners(sinusoid["foot_x"], sinusoid["foot_y"], beta)
        ]
        # The lower roof corner rides the arc; the other clears it.
        assert abs(max(radii) - ch.ARM_TOP_RADIUS) < 1e-6, (
            j,
            amplitude,
            radii,
        )
        assert min(radii) <= ch.ARM_TOP_RADIUS + 1e-6

        default = ch.solve_state(amplitude)
        lift = sinusoid["foot_y"] - default["bar_bottom"]
        assert lift >= -1e-6, (j, amplitude, lift)
        assert sinusoid["foot_r"] <= ch.foot_radius(amplitude) + 1e-6
        lifts.append(lift)
    assert 8.0 < max(lifts) < 8.3

def test_every_pose_spring_keeps_both_eye_centres_on_its_endpoints():
    amplitudes = [float(row["amplitude_mm"]) for row in _config.channels()]
    neutral = ch.solve_state(0.0)
    hole_x_0 = ch.FULCRUM[0] - ch.LEVER_SPRING_X * math.cos(
        math.radians(neutral["lever_tilt"])
    )
    default_specs = [ch._spring_spec(a, hole_x_0) for a in amplitudes]
    _, _, _, parallel_specs, sinusoid_specs = ch._saved_pose_spring_geometry(
        amplitudes, hole_x_0
    )
    banks = {
        "default": default_specs,
        "parallel": parallel_specs,
        "sinusoid": sinusoid_specs,
    }
    neutral_body = ch._spring_spec(0.0, hole_x_0)["body"]
    ch._assign_spring_parts(banks, neutral_body)

    def placed_point(placement, local):
        rows = placement["rows"]
        return [
            placement["position"][axis]
            + sum(local[i] * rows[i][axis] for i in range(3))
            for axis in range(3)
        ]

    for bank, specs in banks.items():
        assert len(specs) == ch.CHANNELS
        for j, spec in enumerate(specs):
            placement = ch._spring_grounded_spec(spec, j, bank)
            bottom = placed_point(
                placement, [0.0, -ch.SPRING_BOTTOM_LEAD, 0.0]
            )
            top = placed_point(
                placement, [0.0, spec["part_body"] + ch.SPRING_TOP_LEAD, 0.0]
            )
            expected_bottom = [
                hole_x_0,
                ch.PLATE_EYE_Y,
                ch.z_station(j) + ch.ARM_MID_DZ,
            ]
            expected_top = [
                hole_x_0 + spec["gap"] * spec["ux"],
                ch.PLATE_EYE_Y + spec["gap"] * spec["uy"],
                expected_bottom[2],
            ]
            assert math.isclose(
                spec["body"] + ch.SPRING_BOTTOM_LEAD + ch.SPRING_TOP_LEAD,
                spec["gap"],
                abs_tol=1e-9,
            )
            assert all(
                math.isclose(got, want, abs_tol=1e-9)
                for got, want in zip(bottom, expected_bottom, strict=True)
            )
            top_tolerance = 0.05 if bank == "default" else 5e-5
            assert all(
                math.isclose(got, want, abs_tol=top_tolerance)
                for got, want in zip(top, expected_top, strict=True)
            )

    # The phase lift is real: reusing or translating Default-length springs
    # cannot satisfy both endpoints in the sinusoidal configuration.
    assert max(
        abs(sinusoid_specs[j]["body"] - default_specs[j]["body"])
        for j in range(ch.CHANNELS)
    ) > 3.0

def test_default_transform_snapshot_skips_suppressed_pose_banks():
    class Transform:
        ArrayData = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.1, 0.2, 0.3]

    class Component:
        def __init__(self, name, suppressed):
            self.Name2 = name
            self._suppressed = suppressed
            self.Transform2 = None if suppressed else Transform()

        def IsSuppressed(self):
            return self._suppressed

    class Model:
        def __init__(self):
            self.components = {
                "live-1": Component("live-1", False),
                "pose-spring-1": Component("pose-spring-1", True),
            }

        def GetComponents(self, top_level_only):
            assert top_level_only
            return list(self.components.values())

        def GetComponentByName(self, name):
            return self.components.get(name)

    class Adapter:
        currentModel = Model()

        @staticmethod
        def _attempt(call, default=None):
            try:
                return call()
            except Exception:
                return default

    assert pc.snapshot_transforms(Adapter()) == {"live-1": Transform.ArrayData}
