"""SolidWorks-free failure cases for the transient cam coupling proofs."""

from __future__ import annotations

import asyncio
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
