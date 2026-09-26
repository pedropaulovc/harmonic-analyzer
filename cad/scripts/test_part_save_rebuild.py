"""SolidWorks-free contract for ``_common.rebuild_all_configurations``.

pc-p1r: drive-train.SLDASM opened with NeedsRebuild2=1 because MHA-135's
INSTALLED configuration, the one the assembly places, was saved stale (amet
probe, dt-logs/pc-p1r/probe-saved-rebuild.jsonl).  The shared part-save
chokepoint now rebuilds every configuration after the last edit, restores the
active one, and refuses to save a configuration that still reads stale.
"""

from __future__ import annotations

import asyncio
import inspect
from types import SimpleNamespace

import pytest

import _common


class _Config:
    def __init__(self, stale: bool) -> None:
        self.NeedsRebuild = stale


class _Part:
    """An IModelDoc2 double: configurations, the active one, and rebuilds that
    clear the active configuration's flag unless it is stuck."""

    def __init__(
        self, stale: dict[str, bool], active: str, stuck: tuple[str, ...] = ()
    ):
        self.configs = {name: _Config(flag) for name, flag in stale.items()}
        self.active = active
        self.stuck = set(stuck)
        self.log: list[str] = []

    def GetConfigurationNames(self):  # noqa: N802
        return tuple(self.configs)

    def GetConfigurationByName(self, name):  # noqa: N802
        return self.configs[name]

    def EditRebuild3(self) -> bool:  # noqa: N802
        self.log.append(f"rebuild {self.active}")
        if self.active not in self.stuck:
            self.configs[self.active].NeedsRebuild = False
        return True


class _Adapter:
    def __init__(self, part: _Part) -> None:
        self.currentModel = part

    async def set_active_configuration(self, name: str):
        self.currentModel.log.append(f"activate {name}")
        self.currentModel.active = name
        return SimpleNamespace(is_success=True, data={"name": name}, error=None)


@pytest.fixture
def seat(monkeypatch):
    monkeypatch.setattr(_common, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(
        _common,
        "active_configuration_name",
        lambda adapter: adapter.currentModel.active,
    )

    def make(stale, active, stuck=()):
        part = _Part(stale, active, stuck)
        return _Adapter(part), part

    return make


def test_a_stale_inactive_configuration_is_rebuilt_and_the_active_restored(
    seat,
) -> None:
    adapter, part = seat({"Default": False, "INSTALLED": True}, "Default")
    asyncio.run(_common.rebuild_all_configurations(adapter, "pinion-lever-pin"))
    assert part.log == [
        "activate INSTALLED",
        "rebuild INSTALLED",
        "activate Default",
        "rebuild Default",
    ]
    assert part.active == "Default"
    assert not any(config.NeedsRebuild for config in part.configs.values())


def test_a_single_configuration_part_pays_one_rebuild_and_no_activation(seat) -> None:
    adapter, part = seat({"Default": False}, "Default")
    asyncio.run(_common.rebuild_all_configurations(adapter, "crank-pin"))
    assert part.log == ["rebuild Default"]


def test_every_one_of_n_configurations_is_rebuilt_active_last(seat) -> None:
    names = ("Default", *(f"T{teeth:03d}" for teeth in range(6, 31, 6)))
    adapter, part = seat({name: True for name in names}, "T012")
    asyncio.run(_common.rebuild_all_configurations(adapter, "cone-gear"))
    rebuilt = [line.removeprefix("rebuild ") for line in part.log if "rebuild" in line]
    assert sorted(rebuilt) == sorted(names)
    assert rebuilt[-1] == "T012"
    assert part.active == "T012"


def test_configurations_still_stale_after_their_rebuild_raise_naming_part_and_all(
    seat,
) -> None:
    names = ("Default", "T006", "T012", "T018", "T024")
    adapter, _part = seat(
        {name: True for name in names}, "Default", stuck=("T006", "T018")
    )
    with pytest.raises(
        RuntimeError, match=r"cone-gear: configurations \['T006', 'T018'\]"
    ):
        asyncio.run(_common.rebuild_all_configurations(adapter, "cone-gear"))


def test_the_read_back_reads_every_configuration_and_passes_when_clean() -> None:
    part = _Part({"Default": False, "INSTALLED": False}, "Default")
    _common.require_configurations_rebuilt(
        part, "pinion-lever-pin", ("Default", "INSTALLED")
    )


def test_the_save_chokepoint_rebuilds_every_configuration_right_before_its_final_save() -> (
    None
):
    # Inside save_part_and_images, so after every caller edit and every edit
    # the chokepoint itself makes (block tolerances, properties, summary info),
    # and nothing runs between it and the re-save that persists the part.
    source = inspect.getsource(_common.save_part_and_images)
    call = "await rebuild_all_configurations(adapter, part_name)"
    rebuild = source.index(call)
    for edit in (
        "apply_block_tolerances(",
        "apply_custom_properties(",
        "apply_summary_info(",
    ):
        assert source.index(edit) < rebuild
    between = source[rebuild + len(call) : source.index('f"re-save with properties')]
    assert between.split() == ["check("]
