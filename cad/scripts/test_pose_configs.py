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
