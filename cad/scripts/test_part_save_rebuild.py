"""SolidWorks-free contract for ``_common.rebuild_stale_configurations``.

pc-p1r: drive-train.SLDASM opened with NeedsRebuild2=1 because MHA-135's
INSTALLED configuration, the one the assembly places, was saved stale (amet
probe, dt-logs/pc-p1r/probe-saved-rebuild.jsonl).  The shared part-save
chokepoint reads every configuration first and leaves a clean part alone.  A
stale one gets exactly one EditRebuildAll, with no configuration switch, and
the chokepoint refuses to save a refused rebuild, a hard fault, or a
configuration still stale.
"""

from __future__ import annotations

import inspect

import pytest

import _common


class _Config:
    def __init__(self, stale: bool) -> None:
        self.NeedsRebuild = stale


class _Extension:
    def __init__(self, part: _Part) -> None:
        self.part = part

    def EditRebuildAll(self) -> bool:  # noqa: N802
        self.part.log.append("EditRebuildAll")
        for name, config in self.part.configs.items():
            if name not in self.part.stuck:
                config.NeedsRebuild = False
        return self.part.rebuild_result

    def GetWhatsWrong(self):  # noqa: N802
        names, codes, warnings = (
            zip(*self.part.faults) if self.part.faults else ((), (), ())
        )
        return True, [_Feature(name) for name in names], list(codes), list(warnings)


class _Feature:
    def __init__(self, name: str) -> None:
        self.Name = name


class _Part:
    """An IModelDoc2 double.  It records every rebuild or activation call, so a
    test can prove which ones the chokepoint made."""

    def __init__(
        self,
        stale: dict[str, bool],
        *,
        stuck: tuple[str, ...] = (),
        rebuild_result: bool = True,
        faults: tuple[tuple[str, int, bool], ...] = (),
    ) -> None:
        self.configs = {name: _Config(flag) for name, flag in stale.items()}
        self.stuck = set(stuck)
        self.rebuild_result = rebuild_result
        self.faults = faults
        self.log: list[str] = []
        self.Extension = _Extension(self)

    def GetConfigurationNames(self):  # noqa: N802
        return tuple(self.configs)

    def GetConfigurationByName(self, name):  # noqa: N802
        return self.configs[name]

    def ShowConfiguration2(self, name):  # noqa: N802
        self.log.append(f"ShowConfiguration2 {name}")
        return True

    def EditRebuild3(self) -> bool:  # noqa: N802
        self.log.append("EditRebuild3")
        return True

    def ForceRebuild3(self, _top_only) -> bool:  # noqa: N802
        self.log.append("ForceRebuild3")
        return True


class _Adapter:
    def __init__(self, part: _Part) -> None:
        self.currentModel = part

    def _attempt(self, fn, default=None):
        return fn()

    async def set_active_configuration(self, name: str):
        self.currentModel.log.append(f"activate {name}")
        raise AssertionError("the save chokepoint must not switch configurations")


@pytest.fixture
def seat(monkeypatch):
    monkeypatch.setattr(_common, "_early_bound", lambda obj, _iface: obj)

    def make(stale, **kwargs):
        part = _Part(stale, **kwargs)
        return _Adapter(part), part

    return make


CONE_GEAR = ("Default", *(f"T{teeth:03d}" for teeth in range(6, 121, 6)))


def test_a_clean_part_gets_no_rebuild_call_at_all(seat) -> None:
    adapter, part = seat({name: False for name in CONE_GEAR})
    _common.rebuild_stale_configurations(adapter, "cone-gear")
    assert part.log == []


def test_a_stale_configuration_gets_one_edit_rebuild_all_and_no_switch(seat) -> None:
    adapter, part = seat({"Default": False, "INSTALLED": True})
    _common.rebuild_stale_configurations(adapter, "pinion-lever-pin")
    assert part.log == ["EditRebuildAll"]
    assert not any(config.NeedsRebuild for config in part.configs.values())


def test_many_stale_configurations_still_get_exactly_one_rebuild(seat) -> None:
    adapter, part = seat({name: True for name in CONE_GEAR})
    _common.rebuild_stale_configurations(adapter, "cone-gear")
    assert part.log == ["EditRebuildAll"]


def test_configurations_still_stale_after_the_rebuild_raise_naming_part_and_all(
    seat,
) -> None:
    adapter, part = seat({name: True for name in CONE_GEAR[:5]}, stuck=("T006", "T018"))
    with pytest.raises(
        RuntimeError, match=r"cone-gear: configurations \['T006', 'T018'\]"
    ):
        _common.rebuild_stale_configurations(adapter, "cone-gear")
    assert part.log == ["EditRebuildAll"]


def test_a_refused_rebuild_raises_even_when_the_flags_read_clean(seat) -> None:
    # Codex P1 on #928: a feature that fails to rebuild can leave NeedsRebuild
    # false, so the rebuild's own verdict is enforced, not just recorded.
    adapter, _part = seat({"Default": False, "INSTALLED": True}, rebuild_result=False)
    with pytest.raises(RuntimeError, match=r"pinion-lever-pin: EditRebuildAll refused"):
        _common.rebuild_stale_configurations(adapter, "pinion-lever-pin")


def test_a_hard_fault_after_the_rebuild_raises_but_a_warning_does_not(seat) -> None:
    adapter, _part = seat({"INSTALLED": True}, faults=(("Pin", 2, False),))
    with pytest.raises(RuntimeError, match=r"left faults \['Pin \(rebuild-error\)'\]"):
        _common.rebuild_stale_configurations(adapter, "pinion-lever-pin")
    adapter, part = seat({"INSTALLED": True}, faults=(("Pin", 1, True),))
    _common.rebuild_stale_configurations(adapter, "pinion-lever-pin")
    assert part.log == ["EditRebuildAll"]


def test_code_one_is_a_fault_unless_what_s_wrong_flags_it_a_warning(seat) -> None:
    # swFeatureError_e 1 is swFeatureErrorUnknown, not a warning: the warning
    # verdict comes only from GetWhatsWrong's is_warning array, as verify.py
    # and _assembly's health gates read it (Main's #928 review).
    adapter, _part = seat({"INSTALLED": True}, faults=(("Pin", 1, False),))
    with pytest.raises(RuntimeError, match=r"left faults \['Pin \(unknown-error\)'\]"):
        _common.rebuild_stale_configurations(adapter, "pinion-lever-pin")
    adapter, part = seat({"INSTALLED": True}, faults=(("Pin", 1, True),))
    _common.rebuild_stale_configurations(adapter, "pinion-lever-pin")
    assert part.log == ["EditRebuildAll"]
    assert _common._FEATURE_ERROR[1] == "unknown-error"


def test_the_save_chokepoint_checks_every_configuration_right_before_its_final_save() -> (
    None
):
    # Inside save_part_and_images: after every caller edit and every edit the
    # chokepoint itself makes (block tolerances, properties, summary info), and
    # nothing runs between it and the re-save that persists the part.
    source = inspect.getsource(_common.save_part_and_images)
    call = "rebuild_stale_configurations(adapter, part_name)"
    guard = source.index(call)
    for edit in (
        "apply_block_tolerances(",
        "apply_custom_properties(",
        "apply_summary_info(",
    ):
        assert source.index(edit) < guard
    between = source[guard + len(call) : source.index('f"re-save with properties')]
    assert between.split() == ["check("]
