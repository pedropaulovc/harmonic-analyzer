"""Behavioral checks for transient setup-motion sweeps."""

from __future__ import annotations

import asyncio
import math
from types import SimpleNamespace

import pytest

import build_drive_train_assembly as rig
import build_motion_setup_drives as motion
import pinion_rig_park_geometry as park


class _MotionAdapter:
    def __init__(self, cam_path_scale: float = 1.0, cam_direction: float = -1.0):
        self.time = 0.0
        self.cam_path_scale = cam_path_scale
        self.cam_direction = cam_direction

    async def open_model(self, _path):
        return True

    async def ensure_motion_addin(self):
        return True

    async def create_motion_study(self, _params):
        return {"name": "test-p2"}

    async def add_motor(self, _params):
        return True

    async def calculate_motion(self, _params):
        return True

    async def set_motion_time(self, params):
        self.time = params.time
        return True

    async def export_motion_video(self, _params):
        return SimpleNamespace(is_success=False)


def _ideal_swing(cam_angle: float) -> float:
    lo, hi = 0.0, rig._PHI_ENG
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if park.cam_pin_gap(cam_angle, mid) > 0.0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2.0


def _component_pose(component, adapter: _MotionAdapter):
    fraction = adapter.time / motion.SWING_DURATION
    target = math.copysign(motion.P2_CAM_SWEEP_DEG, rig.CAM_ENGAGE_ROTATION_DEG)
    cam_deg = adapter.cam_direction * abs(target) * adapter.cam_path_scale * fraction
    theta = math.radians(cam_deg)
    if component.needle == "pinion-lift-rod":
        c, s = math.cos(theta), math.sin(theta)
        return [
            c, s, 0.0,
            -s, c, 0.0,
            0.0, 0.0, 1.0,
            0.0, 0.0, 0.0,
        ]
    if component.needle == "pinion-bracket-1":
        if adapter.cam_direction < 0.0:
            swing = _ideal_swing(theta)
        else:
            # A reversed motor can still leave the visually observed member
            # moving; the gate must reject the input sign, not just a dead pose.
            swing = math.radians(4.0) * fraction
        c, s = math.cos(swing), math.sin(swing)
        ux, uy = park.SPR_U
        u = (ux * c - uy * s, ux * s + uy * c)
        return [
            u[1], -u[0], 0.0,
            u[0], u[1], 0.0,
            0.0, 0.0, 1.0,
            0.0, 0.0, 0.0,
        ]
    raise AssertionError(component.needle)


@pytest.mark.parametrize(
    ("cam_direction", "cam_path_scale", "message"),
    [
        (1.0, 1.0, "expected -"),
        (-1.0, 0.25, "expected -"),
    ],
    ids=["wrong-cam-direction", "short-cam-excursion"],
)
def test_p2_study_rejects_wrong_direction_or_short_excursion(
    monkeypatch, cam_direction, cam_path_scale, message
):
    monkeypatch.setattr(motion, "check", lambda _label, result: result)
    monkeypatch.setattr(motion, "_reset_to_assembled", lambda _adapter: asyncio.sleep(0))
    monkeypatch.setattr(motion, "_assert_dof_already_free", lambda *_: None)
    monkeypatch.setattr(motion, "_family_driver_names", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        motion,
        "_find_one",
        lambda _adapter, needle: (SimpleNamespace(needle=needle), f"{needle}-1"),
    )
    adapter = _MotionAdapter(cam_path_scale, cam_direction)
    monkeypatch.setattr(
        motion, "_comp_xform", lambda _adapter, component: _component_pose(component, adapter)
    )

    with pytest.raises(RuntimeError, match=message):
        asyncio.run(motion._drive_p2(adapter))


def test_p2_study_accepts_contact_derived_direction_and_excursion(monkeypatch):
    monkeypatch.setattr(motion, "check", lambda _label, result: result)
    monkeypatch.setattr(motion, "_reset_to_assembled", lambda _adapter: asyncio.sleep(0))
    monkeypatch.setattr(motion, "_assert_dof_already_free", lambda *_: None)
    monkeypatch.setattr(motion, "_family_driver_names", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        motion,
        "_find_one",
        lambda _adapter, needle: (SimpleNamespace(needle=needle), f"{needle}-1"),
    )
    adapter = _MotionAdapter()
    monkeypatch.setattr(
        motion, "_comp_xform", lambda _adapter, component: _component_pose(component, adapter)
    )

    result = asyncio.run(motion._drive_p2(adapter))
    assert result["dof"] == "p2 cam-driven bracket engage"
    assert float(result["span_deg"]) == pytest.approx(
        math.degrees(_ideal_swing(math.radians(-motion.P2_CAM_SWEEP_DEG))),
        abs=0.01,
    )
