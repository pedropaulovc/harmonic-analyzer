"""Offline contracts for the saved pose configurations (poses.yaml + _pose_configs)."""

from __future__ import annotations

import math

import _buildgraph
import _config
import _pose_configs as pc
import build_channel_assembly as ch
from pathlib import Path


def test_poses_yaml_shape():
    poses = _config.poses()
    fan, sinus = poses["amplitude_fan"], poses["sinusoid"]
    amps = fan["amplitude_mm"]
    assert len(amps) == 20
    assert all(0.0 <= a <= 88.0 for a in amps), amps  # the +-88 mm seesaw (ch.15)
    assert amps == sorted(amps), "the fan is a monotonic ramp (ch15 p.30)"
    assert fan["configuration"] != sinus["configuration"] != pc.REST_CONFIGURATION
    assert fan["configuration"] != pc.REST_CONFIGURATION
    assert int(sinus["crank_turns"]) == sinus["crank_turns"] > 0, "whole crank turns only"


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
    tilts = [ch.solve_cam_pose(t, 20)["arm_tilt"] for t in [i * 0.25 for i in range(16)]]
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
    assert abs(pc.yaw_deg([0.0, 1.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0, 0, 0, 1, 0, 0, 0]) - 90.0) < 1e-12


def test_pose_module_rides_the_three_assembly_recipes():
    scripts = Path(_buildgraph.__file__).resolve().parent
    for stem in ("build_channel_assembly.py", "build_drive_train_assembly.py", "build_harmonic_analyzer_assembly.py"):
        deps = {Path(p).name for p in _buildgraph.module_deps_of(scripts / stem)}
        assert "_pose_configs.py" in deps, (stem, sorted(deps))
        assert "poses.yaml" in _buildgraph.config_files_of(scripts / stem), stem


def _roof_corners(fx, fy, beta):
    """Both notch-roof corners of a bar at foot (fx, fy) with solve_state's swing
    root ``beta`` (up vector (sin b, cos b), +X edge (cos b, -sin b))."""
    s, c = math.sin(beta), math.cos(beta)
    return [
        (fx + side * ch._CONTACT_OFF_X * c + ch._CONTACT_OFF_Y * s,
         fy - side * ch._CONTACT_OFF_X * s + ch._CONTACT_OFF_Y * c)
        for side in (-1.0, 1.0)
    ]


def test_fanned_bar_roof_lies_flat_on_its_arc():
    # 2026-09-02: the contact-offset rotation was mirrored -- at a = 80 the bar
    # floated 0.64 mm off the arc. Both corners now sit on the R800 arc (the
    # roof is parallel to the arc's tangent because the bar hangs from ~the
    # arc centre), so the foot->centre radius is amplitude-independent.
    for a in (0.0, 40.0, 80.0):
        st = ch.solve_state(a)
        beta = -math.radians(st["bar_tilt"])
        for cx, cy in _roof_corners(ch.PIVOT[0] + a, st["bar_bottom"], beta):
            r = math.hypot(cx - ch._ARC["acx"], cy - ch._ARC["acy"])
            assert abs(r - ch.ARM_TOP_RADIUS) < 0.01, (a, cx, cy, r)
        assert abs(ch.foot_radius(a) - ch.foot_radius(0.0)) < 0.02, a


def test_sinusoid_foot_reproduces_the_rest_pose_at_zero_cranks():
    rest = ch.solve_state(0.0)
    sf = ch.solve_sinusoid_foot(ch.solve_cam_pose(0.0, 20))
    assert abs(sf["theta_deg"]) < 1e-9
    assert abs(sf["foot_y"] - rest["bar_bottom"]) < 1e-5
    assert abs(sf["foot_r"] - ch.foot_radius(0.0)) < 1e-5
    assert abs(sf["lever_tilt"] - rest["lever_tilt"]) < 1e-5


def test_sinusoid_foot_rides_the_turned_arc_on_its_lower_corner():
    rest = ch.solve_state(0.0)
    lifts = []
    for k in (1, 8, 14, 17, 20):
        st = ch.solve_cam_pose(6.0, k)
        sf = ch.solve_sinusoid_foot(st)
        assert abs(sf["theta_deg"] + st["arm_tilt"]) < 1e-4, (k, sf["theta_deg"], st["arm_tilt"])
        beta = -math.radians(sf["bar_tilt"])
        radii = [
            math.hypot(cx - sf["arc_cx"], cy - sf["arc_cy"])
            for cx, cy in _roof_corners(sf["foot_x"], sf["foot_y"], beta)
        ]
        # the lower corner ON the arc, the other one above it (inside R800)
        assert abs(max(radii) - ch.ARM_TOP_RADIUS) < 1e-6, (k, radii)
        assert min(radii) <= ch.ARM_TOP_RADIUS + 1e-6
        lift = sf["foot_y"] - rest["bar_bottom"]
        assert lift >= -1e-9
        lifts.append((abs(st["arm_tilt"]), lift))
        assert sf["foot_r"] <= ch.foot_radius(0.0) + 1e-9
    lifts.sort()
    assert all(b[1] >= a[1] for a, b in zip(lifts, lifts[1:]))  # monotone in |tilt|
    assert 0.4 < lifts[-1][1] < 0.6, lifts[-1]  # ~7.4 deg: 3.175 * tan + the centre swing

