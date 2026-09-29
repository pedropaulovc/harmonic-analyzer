"""SolidWorks-free failure cases for the transient cam coupling proofs."""

from __future__ import annotations

import asyncio
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import _assembly_postbuild
import build_drive_train_assembly as rig
import build_mobility_probe as probe
import pinion_rig_park_geometry as park
import verify


class _Report:
    def __init__(self):
        self.failed = []

    async def agate(self, _label, operation):
        await operation()


@pytest.mark.parametrize(
    "along",
    [
        lambda: rig.FPIN_SEAT_LEN + 0.5,
        lambda: rig.FPIN_LEN - rig.FPIN_CAP_SAG - 0.5,
    ],
    ids=["buried-in-seat", "inside-dome"],
)
def test_contact_gate_rejects_nonexposed_shank(monkeypatch, tmp_path: Path, along):
    station = along()
    (tmp_path / "drive-train.SLDASM").write_bytes(b"fake assembly")
    monkeypatch.setattr(park, "SPR_U", (0.0, 1.0, 0.0))
    monkeypatch.setattr(verify, "_assert_fresh", lambda *_: True)
    monkeypatch.setattr(
        verify, "load_dof_manifest", lambda _name: [{"key": "pinion_cam"}]
    )
    monkeypatch.setattr(verify, "check", lambda _label, result: result)
    monkeypatch.setattr(verify, "_rebuild", lambda _adapter: None)
    monkeypatch.setattr(verify, "discard_open_documents", lambda _adapter: None)
    monkeypatch.setattr(verify, "OUT_SLDASM", tmp_path)

    # The cam-axis projection lands at the requested station on each pin's
    # local +Z; the gate must reject it before accepting any radial gap.
    def transform(_adapter, component):
        z = 0.0
        if component.startswith("pinion-cam-pin-"):
            tag = int(component.rsplit("-", 1)[1])
            z = (rig.CAM_PIN_STATION[tag - 1] - station) / 1000.0
        return [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, z]

    monkeypatch.setattr(verify, "component_transform", transform)
    parameter = SimpleNamespace(SystemValue=0.0)
    model = SimpleNamespace(Parameter=lambda _key: parameter)
    adapter = SimpleNamespace(
        currentModel=model,
        swApp=SimpleNamespace(CloseAllDocuments=lambda _save: None),
        _attempt=lambda operation, default=None: operation(),
        open_model=None,
    )

    async def open_model(_path):
        return True

    adapter.open_model = open_model

    async def author(_adapter, _specs):
        return ["DRIVE_pinion_cam"]

    monkeypatch.setattr(verify, "author_dof_drives", author)
    with pytest.raises(RuntimeError, match="outside its exposed straight shank"):
        asyncio.run(verify._verify_pinion_cam_contact(adapter, _Report()))


def test_contact_gate_sweeps_full_engage_pose_with_pinion_cam_drive(
    monkeypatch, tmp_path: Path
):
    (tmp_path / "drive-train.SLDASM").write_bytes(b"fake assembly")
    monkeypatch.setattr(verify, "_assert_fresh", lambda *_: True)
    monkeypatch.setattr(verify, "check", lambda _label, result: result)
    monkeypatch.setattr(verify, "_rebuild", lambda _adapter: None)
    monkeypatch.setattr(verify, "discard_open_documents", lambda _adapter: None)
    monkeypatch.setattr(verify, "OUT_SLDASM", tmp_path)

    cam_spec = {"key": "pinion_cam", "params": {"angle": "recorded-rest"}}
    specs = [{"key": "other-dof"}, cam_spec]
    monkeypatch.setattr(verify, "load_dof_manifest", lambda _name: specs)
    parameter = SimpleNamespace(SystemValue=0.0)
    model = SimpleNamespace(Parameter=lambda _key: parameter)
    adapter = SimpleNamespace(
        currentModel=model,
        swApp=SimpleNamespace(CloseAllDocuments=lambda _save: None),
        _attempt=lambda operation, default=None: operation(),
    )

    async def open_model(_path):
        return True

    async def author(_adapter, received_specs):
        assert received_specs == [cam_spec]
        return ["DRIVE_pinion_cam"]

    monkeypatch.setattr(verify, "author_dof_drives", author)
    seen_cam_angles = []

    def ideal_swing(theta):
        low, high = 0.0, rig._PHI_ENG
        for _ in range(60):
            mid = (low + high) / 2.0
            if park.cam_pin_gap(theta, mid) > 0.0:
                high = mid
            else:
                low = mid
        return (low + high) / 2.0

    def transform(_adapter, component):
        theta = parameter.SystemValue
        if component.startswith("pinion-cam-pin-"):
            tag = int(component.rsplit("-", 1)[1])
            swing = ideal_swing(theta)
            center, normal = park._pin_frame(park.REST_SWING_RAD + swing)
            direction = (-normal[0], -normal[1], 0.0)
            return [
                normal[1], -normal[0], 0.0,
                0.0, 0.0, 1.0,
                *direction,
                (center[0] + rig._FPIN_S0 * direction[0]) / 1000.0,
                (center[1] + rig._FPIN_S0 * direction[1]) / 1000.0,
                rig.CAM_PIN_STATION[tag - 1] / 1000.0,
            ]
        if component.startswith("pinion-cam-"):
            seen_cam_angles.append(theta)
            c, s = math.cos(theta), math.sin(theta)
            return [
                c, s, 0.0,
                -s, c, 0.0,
                0.0, 0.0, 1.0,
                rig.LIFT_X / 1000.0,
                rig.LIFT_Y / 1000.0,
                0.0,
            ]
        if component == "pinion-bracket-1":
            swing = ideal_swing(theta)
            c, s = math.cos(swing), math.sin(swing)
            ux, uy = park.SPR_U
            u = (ux * c - uy * s, ux * s + uy * c)
            return [
                u[1], -u[0], 0.0,
                u[0], u[1], 0.0,
                0.0, 0.0, 1.0,
                0.0, 0.0, 0.0,
            ]
        raise AssertionError(f"unexpected component {component!r}")

    monkeypatch.setattr(verify, "component_transform", transform)
    adapter.open_model = open_model
    asyncio.run(verify._verify_pinion_cam_contact(adapter, _Report()))

    engage_rad = math.radians(rig.CAM_ENGAGE_ROTATION_DEG)
    assert (
        sum(math.isclose(angle, engage_rad, abs_tol=1e-9) for angle in seen_cam_angles)
        == 2
    )


def test_cam_probe_rejects_lift_rod_free_without_bracket(monkeypatch):
    monkeypatch.setattr(probe, "check", lambda _label, result: result)
    monkeypatch.setattr(_assembly_postbuild, "load_dof_manifest", lambda _sub: [])
    monkeypatch.setattr(
        probe, "_drivers_by_family", lambda *_: {"pinion-lift-rod": ["cam-driver"]}
    )
    states = iter(
        [
            {"pinion-lift-rod-1": 3, "pinion-bracket-1": 3},
            {"pinion-lift-rod-1": probe.UNDER_CONSTRAINED, "pinion-bracket-1": 3},
            {"pinion-lift-rod-1": 3, "pinion-bracket-1": 3},
        ]
    )
    monkeypatch.setattr(probe, "_component_status", lambda _adapter: next(states))

    async def success(_params):
        return True

    adapter = SimpleNamespace(
        currentModel=object(), open_model=success, suppress_mate=success
    )
    with pytest.raises(RuntimeError, match="bracket stayed constrained"):
        asyncio.run(
            probe._probe_sub(
                adapter,
                "drive-train",
                [("drive-train", "pinion-lift-rod", "cam engage")],
            )
        )
