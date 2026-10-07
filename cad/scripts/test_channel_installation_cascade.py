"""Offline contracts for the v2 channel-bank installation cascade."""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import pytest

import _config
import _cwm
import build_ch_channel_assembly as channel
import channel_kinematics
import ch_connecting_rod_spec
import cylinder_bank_layout
import cylinder_cam_spec
import channel_frame_geom
import ch_rocker_arm_spec
import ch_fulcrum_shaft_spec
import rocker_bank_layout
from _assembly import _seed_flip, activate_assembly_contract
from dt_cone_pivot_post_installation import CHANNEL_Z0, DRUM_X, MECHANISM_Z_SHIFT
from test_dodo_recipe import isolated_assembly_helper_keys  # noqa: F401 - pytest fixture


def test_machine_config_and_channel_interface_share_one_installation_contract() -> None:
    assert math.isclose(
        _config.machine("channels", "station_z0_mm"), CHANNEL_Z0, abs_tol=1e-12
    )
    assert math.isclose(channel.Z0, CHANNEL_Z0, abs_tol=1e-12)
    assert channel.X_DRUM == DRUM_X
    # #743 solid stack: the ring rides the middle of its closed cam slot.
    assert channel.CAM_DZ == pytest.approx(cylinder_bank_layout.CAM_MID_DZ)
    assert channel.CAM_DZ == pytest.approx(-7.0565 / 2.0)

    phase = math.radians(channel.GEAR_PHASE_DEG)
    assert channel.RING_CENTER == (
        DRUM_X + channel.CAM_ECC * math.sin(phase),
        channel.Y_DRIVE + channel.CAM_ECC * math.cos(phase),
    )


def test_rocker_and_rod_reclose_the_level_plumb_neutral_pose() -> None:
    assert ch_connecting_rod_spec.CENTER_DISTANCE == channel.ROD_C2C
    assert abs(channel_kinematics.ARC["arm_tilt"]) < 0.02
    assert abs(channel_kinematics.ARC["rod_tilt"]) < 0.02


def test_existing_shafts_and_translated_mounts_cover_the_shifted_bank() -> None:
    assert channel.CHANNEL_BANK_REAR_SHIFT == MECHANISM_Z_SHIFT

    row_min = channel.z_station(0) + channel.ARM_MID_DZ - channel.LEVER_THICKNESS / 2.0
    row_max = (
        channel.z_station(channel.CHANNELS - 1)
        + channel.ARM_MID_DZ
        + channel.LEVER_THICKNESS / 2.0
    )

    # #743 PR2: the pivot shaft's origin is its north (shouldered) end; its
    # cylinder spans both bracket ears (rocker_bank_layout).
    pivot_max = channel.PIVOT_SHAFT_Z
    pivot_min = pivot_max - rocker_bank_layout.PIVOT_SHAFT_LENGTH
    assert pivot_min < row_min < row_max < pivot_max
    # 481ec429 (2026-09 pivot-bracket re-derive): the asymmetric A-frame/
    # support mounts became a pivot-bracket pair on the shaft.
    bracket_lo, bracket_hi = channel.PIVOT_BRACKET_Z
    assert pivot_min < bracket_lo < row_min < row_max < bracket_hi < pivot_max

    fulcrum_min = channel.FULCRUM_SHAFT_Z - ch_fulcrum_shaft_spec.SHAFT_LENGTH / 2.0
    fulcrum_max = channel.FULCRUM_SHAFT_Z + ch_fulcrum_shaft_spec.SHAFT_LENGTH / 2.0
    assert fulcrum_min < row_min < row_max < fulcrum_max
    # The end keepers grip the shaft ENDS: ball centres 2.25 inboard of each
    # end, feet + screws inboard of the corner-boss lands (2026-08-02 remount).
    keeper_lo = channel.FULCRUM_SHAFT_Z - channel.KEEPER_Z_OFF
    keeper_hi = channel.FULCRUM_SHAFT_Z + channel.KEEPER_Z_OFF
    assert fulcrum_min < keeper_lo < row_min < row_max < keeper_hi < fulcrum_max
    assert channel.KEEPER_Z_OFF - channel.KEEPER_SCREW_Z_OFF == 14.75


def test_positive_fulcrum_station_uses_the_relearned_mate_side() -> None:
    activate_assembly_contract("ch-channel")
    assert _seed_flip("ch-fulcrum-shaft-1 datum z d=35.41", channel.FULCRUM_SHAFT_Z)


def test_copied_internal_rod_axial_mate_is_reset_to_the_seed_side(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Mate:
        Flipped = False
        CanBeFlipped = True

    mate = Mate()
    monkeypatch.setattr(_cwm, "_component_distance_mate", lambda *_a, **_kw: mate)

    assert _cwm.ensure_component_distance_mate_flip(
        object(), "ch-connecting-rod-3", 4.05, True
    )
    assert mate.Flipped is True
    assert not _cwm.ensure_component_distance_mate_flip(
        object(), "ch-connecting-rod-3", 4.05, True
    )


def _fresh_source_module(monkeypatch, name: str, path: Path | None = None):
    """Evaluate a real source module without reusing its cached scalar imports."""
    source = path or Path(__file__).with_name(f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


def _reclose_plumb_rod(monkeypatch, ring_center: tuple[float, float]) -> None:
    """Keep a deliberately changed cam/frame witness within the level-pose guard."""
    pivot = channel_frame_geom.ROCKER_PIVOT_XY
    rise = ch_rocker_arm_spec.ROD_HOLE_Y - ch_rocker_arm_spec.PIVOT_MID_Y
    monkeypatch.setattr(ch_rocker_arm_spec, "ROD_HOLE_X", pivot[0] - ring_center[0])
    monkeypatch.setattr(
        ch_connecting_rod_spec, "CENTER_DISTANCE", pivot[1] + rise - ring_center[1]
    )


def _configured_solver_stations() -> list[float]:
    """Use the CAD coefficient vector, named square fundamental and travel end.

    The assembly rejects negative stations and check:config owns the upper
    travel limit. Like verify_spring_base, exercise neutral, full scale and
    configured coefficients; also retain the named square-preset fundamental.
    """
    return sorted(
        {
            0.0,
            float(_config.machine("amplitude", "fundamental_station_mm")),
            float(_config.machine("amplitude", "max_travel_mm")),
            *_config.amplitudes(),
        }
    )


@pytest.mark.parametrize(
    ("eccentricity", "face_width"),
    ((8.64, 3.0), (8.9, 2.6), (8.4, 3.4)),
)
def test_channel_and_cylinder_consume_the_same_evaluated_cam_dimensions(
    tmp_path, monkeypatch, eccentricity: float, face_width: float
) -> None:
    # Mutate the real leaf source, including re-evaluating its derived thickness.
    # Alternative throws require the same plumb-rod co-solve as the real design;
    # this scalar/kinematics witness is not a claim about native variant geometry.
    source = Path(cylinder_cam_spec.__file__).read_text(encoding="utf-8")
    for old, new in (
        ("ECCENTRICITY = 8.64", f"ECCENTRICITY = {eccentricity!r}"),
        ("FACE_WIDTH = 3.0", f"FACE_WIDTH = {face_width!r}"),
    ):
        assert source.count(old) == 1
        source = source.replace(old, new)
    leaf_path = tmp_path / "cylinder_cam_spec.py"
    leaf_path.write_text(source, encoding="utf-8")
    cam = _fresh_source_module(monkeypatch, "cylinder_cam_spec", leaf_path)
    phase = math.radians(channel_frame_geom.CYLINDER_LOCK_PHASE_DEG)
    ring_center = (
        channel_frame_geom.CAM_SHAFT_XY[0] + eccentricity * math.sin(phase),
        channel_frame_geom.CAM_SHAFT_XY[1] + eccentricity * math.cos(phase),
    )
    if eccentricity != 8.64:
        _reclose_plumb_rod(monkeypatch, ring_center)
    kinematics = _fresh_source_module(monkeypatch, "channel_kinematics")
    assembly = _fresh_source_module(monkeypatch, "build_ch_channel_assembly")
    cylinder = _fresh_source_module(monkeypatch, "build_dt_cylinder_gear")

    assert cam.OVERALL_THICKNESS == 7.0565  # unchanged authored stacking dimension
    assert cam.CAM_THICKNESS == 7.0565 - face_width
    assert cylinder.FACE_WIDTH == assembly.CYL_FACE_WIDTH == face_width
    assert cylinder.CAM_THICKNESS == assembly.CYL_CAM_THICKNESS == cam.CAM_THICKNESS
    assert cylinder.ECCENTRICITY == assembly.CAM_ECC == eccentricity
    assert cylinder.THROUGH_ALL == 7.0565 + 2.0
    assert assembly.CAM_DZ == -(face_width + (7.0565 - face_width)) / 2.0
    assert assembly.RING_CENTER == kinematics._RING_CENTER == ring_center

    states = {
        amplitude: kinematics.solve_state(amplitude)
        for amplitude in _configured_solver_stations()
    }
    neutral = states[0.0]
    for state in states.values():
        pin = (state["pin_x"], state["pin_y"])
        assert math.dist(pin, ring_center) == pytest.approx(assembly.ROD_C2C)
        assert math.dist(pin, assembly.PIVOT) == pytest.approx(
            math.hypot(
                ch_rocker_arm_spec.ROD_HOLE_X,
                ch_rocker_arm_spec.ROD_HOLE_Y - ch_rocker_arm_spec.PIVOT_MID_Y,
            )
        )
    assert states[max(states)]["lever_tilt"] != neutral["lever_tilt"]
    if eccentricity == 8.64 and face_width == 3.0:
        for amplitude, state in states.items():
            assert state == channel_kinematics.solve_state(amplitude)


@pytest.mark.parametrize(
    ("diametral_pitch", "axis_shift", "phase_shift"),
    ((49.82, 0.0, 0.0), (40.0, 0.0, 0.0), (60.0, 0.0, 0.0), (49.82, 0.5, 0.3)),
)
def test_pitch_does_not_change_channel_math_but_axis_and_phase_do(
    monkeypatch, diametral_pitch: float, axis_shift: float, phase_shift: float
) -> None:
    original_machine = _config.machine
    drive_y = original_machine("gear_train", "drive_axis_y_mm") + axis_shift
    phase_deg = original_machine("gear_train", "cylinder_lock_phase_deg") + phase_shift

    def machine_value(*keys: str):
        if keys == ("gear_train", "diametral_pitch"):
            return diametral_pitch
        if keys == ("gear_train", "drive_axis_y_mm"):
            return drive_y
        if keys == ("gear_train", "cylinder_lock_phase_deg"):
            return phase_deg
        return original_machine(*keys)

    monkeypatch.setattr(_config, "machine", machine_value)
    frame = _fresh_source_module(monkeypatch, "channel_frame_geom")
    tooth_spec = _fresh_source_module(monkeypatch, "dt_cylinder_gear_spec")
    phase = math.radians(phase_deg)
    ring_center = (
        frame.CAM_SHAFT_XY[0] + cylinder_cam_spec.ECCENTRICITY * math.sin(phase),
        drive_y + cylinder_cam_spec.ECCENTRICITY * math.cos(phase),
    )
    if axis_shift or phase_shift:
        _reclose_plumb_rod(monkeypatch, ring_center)
    kinematics = _fresh_source_module(monkeypatch, "channel_kinematics")
    assembly = _fresh_source_module(monkeypatch, "build_ch_channel_assembly")

    assert tooth_spec.OUTSIDE_DIA == (tooth_spec.TEETH + 2) / diametral_pitch * 25.4
    assert assembly.Y_DRIVE == drive_y
    assert assembly.GEAR_PHASE_DEG == phase_deg
    assert assembly.RING_CENTER == kinematics._RING_CENTER == ring_center
    assert assembly.CAM_DZ == channel.CAM_DZ
    states = {
        amplitude: kinematics.solve_state(amplitude)
        for amplitude in _configured_solver_stations()
    }
    if not axis_shift and not phase_shift:
        assert ring_center == channel.RING_CENTER
        for amplitude, state in states.items():
            assert state == channel_kinematics.solve_state(amplitude)
    else:
        # The +0.5 mm axis / +0.3 degree phase variant moves ring Y and phased X.
        # The plumb co-solve follows that X but holds pin Y at its level datum;
        # a floating-point inequality in pin Y would not witness actual motion.
        neutral = states[0.0]
        assert abs(ring_center[1] - channel.RING_CENTER[1]) > 0.1
        assert abs(neutral["pin_x"] - channel_kinematics.ARC["pin_x"]) > 1e-3
        assert neutral["pin_y"] == pytest.approx(
            frame.ROCKER_PIVOT_XY[1]
            + ch_rocker_arm_spec.ROD_HOLE_Y
            - ch_rocker_arm_spec.PIVOT_MID_Y,
            abs=1e-9,
            rel=0.0,
        )


@pytest.mark.parametrize(
    ("relative", "old", "new", "changes_channel"),
    (
        (
            "cad/scripts/cylinder_cam_spec.py",
            "ECCENTRICITY = 8.64",
            "ECCENTRICITY = 8.9",
            True,
        ),
        (
            "cad/scripts/cylinder_cam_spec.py",
            "FACE_WIDTH = 3.0",
            "FACE_WIDTH = 3.4",
            True,
        ),
        (
            "cad/scripts/dt_cylinder_gear_spec.py",
            "TEETH = 120",
            "TEETH = 126",
            False,
        ),
        (
            "cad/config/machine/gear_train.yaml",
            "diametral_pitch: 49.82",
            "diametral_pitch: 40.0",
            True,
        ),
        (
            "cad/config/machine/gear_train.yaml",
            "drive_axis_y_mm: 90.518",
            "drive_axis_y_mm: 91.018",
            True,
        ),
        (
            "cad/config/machine/gear_train.yaml",
            "cylinder_lock_phase_deg: 1.5",
            "cylinder_lock_phase_deg: 1.8",
            True,
        ),
    ),
)
def test_cam_and_tooth_edits_invalidate_the_actual_recipe_and_cache_consumers(
    isolated_assembly_helper_keys, relative, old, new, changes_channel
) -> None:
    # Existing fixture copies the actual discovered production recipe inputs,
    # adapter identities and targets; no live CAD output or source is mutated.
    _dodo, root, snapshot = isolated_assembly_helper_keys
    before = snapshot()
    path = root / relative
    source = path.read_text(encoding="utf-8")
    assert source.count(old) == 1
    path.write_text(source.replace(old, new), encoding="utf-8")
    after = snapshot()

    for group in ("recipes", "assemblies"):
        assert (
            after[group]["ch_channel"] != before[group]["ch_channel"]
        ) is changes_channel
        assert after[group]["dt_drive_train"] != before[group]["dt_drive_train"]
    for group in ("part_recipes", "parts"):
        assert after[group]["dt_cylinder_gear"] != before[group]["dt_cylinder_gear"]
