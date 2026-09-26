"""SolidWorks-free contract for per-configuration part material.

MHA-135 (pinion-lever-pin) applied its material after the INSTALLED split, and
the adapter's apply_material set only the active configuration (Default).
_common.apply_material now sets every configuration by name, and the part-save
chokepoint refuses a part whose configurations disagree or carry none.
"""

from __future__ import annotations

import inspect

import pytest

import _common


class _Part:
    """IModelDoc2 + IPartDoc double holding one material per configuration."""

    def __init__(self, materials: dict[str, str]) -> None:
        self.materials = dict(materials)
        self.log: list[str] = []

    def GetConfigurationNames(self):  # noqa: N802
        return tuple(self.materials)

    def SetMaterialPropertyName2(self, config, database, name):  # noqa: N802
        self.log.append(f"set {config}")
        self.materials[config] = name

    def GetMaterialPropertyName2(self, config):  # noqa: N802
        name = self.materials[config]
        return name, ("SOLIDWORKS Materials" if name else "")

    def EditRebuild3(self) -> bool:  # noqa: N802
        self.log.append("EditRebuild3")
        return True


class _Adapter:
    def __init__(self, part: _Part) -> None:
        self.currentModel = part


@pytest.fixture
def seat(monkeypatch):
    monkeypatch.setattr(_common, "_early_bound", lambda obj, _iface: obj)

    def make(materials):
        part = _Part(materials)
        return _Adapter(part), part

    return make


@pytest.mark.asyncio
async def test_apply_material_sets_every_configuration_by_name(seat) -> None:
    adapter, part = seat({"Default": "", "INSTALLED": ""})
    await _common.apply_material(adapter, "Plain Carbon Steel")
    assert part.materials == {"Default": "Plain Carbon Steel", "INSTALLED": "Plain Carbon Steel"}
    assert part.log == ["set Default", "set INSTALLED", "EditRebuild3"]


@pytest.mark.asyncio
async def test_apply_material_raises_when_a_configuration_reads_back_wrong(
    seat, monkeypatch
) -> None:
    adapter, part = seat({"Default": "", "INSTALLED": ""})
    monkeypatch.setattr(part, "SetMaterialPropertyName2", lambda *_args: None)
    with pytest.raises(RuntimeError, match=r"configurations read \{'Default': '', 'INSTALLED': ''\}"):
        await _common.apply_material(adapter, "Brass")


def test_the_gate_passes_one_material_in_every_configuration(seat) -> None:
    adapter, _part = seat({"Default": "Brass", **{f"T{t:03d}": "Brass" for t in (6, 12)}})
    _common.require_one_material(adapter, "cone-gear")


@pytest.mark.parametrize(
    "materials",
    [
        {"Default": "Plain Carbon Steel", "INSTALLED": ""},
        {"Default": "Plain Carbon Steel", "INSTALLED": "Brass"},
        {"Default": ""},
    ],
)
def test_the_gate_names_the_part_and_every_configuration(seat, materials) -> None:
    adapter, _part = seat(materials)
    with pytest.raises(RuntimeError, match=r"pinion-lever-pin: every configuration"):
        _common.require_one_material(adapter, "pinion-lever-pin")


def test_the_save_chokepoint_gates_material_before_its_final_rebuild_and_save() -> None:
    source = inspect.getsource(_common.save_part_and_images)
    gate = source.index("require_one_material(adapter, part_name)")
    assert source.index("apply_summary_info(") < gate
    assert gate < source.index("rebuild_stale_configurations(adapter, part_name)")
