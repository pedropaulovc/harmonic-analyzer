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


# --- cone gear: saved configuration caches -----------------------------------
#
# cg-fx1 (9459428ec, dt-logs/farm-runs/leaf-logs/cg-fx1-task.log:305-345): the
# drive train swapped 19 cone-gear copies to T006..T114 and its EditRebuild3
# failed, every copy on ToothGapCut + ToothGapPattern at error 1.  In the part,
# each of those configurations faulted as loaded, a plain EditRebuild3 returned
# False and left it faulted, and only ForceRebuild3 cleared it -- all while
# NeedsRebuild read false.  The double below reproduces exactly that seat
# behaviour.

import build_cone_gear  # noqa: E402

CONE_FAULTS = (("ToothGapCut", 1, False), ("ToothGapPattern", 1, False))


class _ConeConfig:
    def __init__(self, name: str) -> None:
        self.Name = name
        self.NeedsRebuild = False


class _ConeManager:
    def __init__(self, part: _ConeGear) -> None:
        self.part = part

    @property
    def ActiveConfiguration(self):  # noqa: N802
        return self.part.configs[self.part.active]


class _ConeExtension:
    def __init__(self, part: _ConeGear) -> None:
        self.part = part

    def GetWhatsWrong(self):  # noqa: N802
        faults = CONE_FAULTS if self.part.active in self.part.bad else ()
        names, codes, warnings = zip(*faults) if faults else ((), (), ())
        return True, [_Feature(name) for name in names], list(codes), list(warnings)


class _ConeGear:
    """cone-gear.SLDPRT reopened, active on T120, ``bad`` configurations saved
    with the cg-fx1 caches."""

    def __init__(self, bad: tuple[str, ...], stuck: tuple[str, ...] = ()) -> None:
        self.configs = {name: _ConeConfig(name) for name in CONE_GEAR}
        self.active = "T120"
        self.bad = set(bad)
        self.stuck = set(stuck)  # faults no rebuild clears
        self.log: list[str] = []
        self.ConfigurationManager = _ConeManager(self)
        self.Extension = _ConeExtension(self)

    def GetConfigurationNames(self):  # noqa: N802
        return tuple(self.configs)

    def GetConfigurationByName(self, name):  # noqa: N802
        return self.configs[name]

    def ShowConfiguration2(self, name) -> bool:  # noqa: N802
        if name == self.active:
            return False  # SolidWorks refuses the already-active configuration
        self.log.append(f"show {name}")
        self.active = name
        return True

    def EditRebuild3(self) -> bool:  # noqa: N802
        self.log.append(f"edit {self.active}")
        return self.active not in self.bad

    def ForceRebuild3(self, _top_only) -> bool:  # noqa: N802
        self.log.append(f"force {self.active}")
        if self.active not in self.stuck:
            self.bad.discard(self.active)
        return True


@pytest.fixture
def cone_gear(monkeypatch):
    monkeypatch.setattr(_common, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(build_cone_gear, "_early_bound", lambda obj, _iface: obj)

    def make(bad=(), stuck=()):
        part = _ConeGear(tuple(bad), tuple(stuck))
        return _Adapter(part), part

    return make


SWAPPED = CONE_GEAR[1:-1]  # T006..T114, the configurations the copies take


def test_saved_caches_that_fault_as_an_assembly_loads_them_fail_the_reopen(
    cone_gear,
) -> None:
    adapter, part = cone_gear(bad=SWAPPED)
    with pytest.raises(RuntimeError, match="do not regenerate") as failure:
        build_cone_gear.assert_saved_caches_regenerate(adapter)
    message = str(failure.value)
    for name in SWAPPED:
        assert f"{name}: loaded ['ToothGapCut (1)', 'ToothGapPattern (1)']" in message
    assert "EditRebuild3=False" in message
    assert "T120:" not in message and "Default:" not in message
    # The check reads the caches, it never repairs them.
    assert not any(entry.startswith("force") for entry in part.log)


def test_clean_saved_caches_pass_with_one_plain_rebuild_each_ending_on_t120(
    cone_gear,
) -> None:
    adapter, part = cone_gear()
    build_cone_gear.assert_saved_caches_regenerate(adapter)
    assert [entry for entry in part.log if entry.startswith("edit")] == [
        f"edit {name}" for name in (*CONE_GEAR[:-1], "T120")
    ]
    assert part.active == "T120"
    assert not any(entry.startswith("force") for entry in part.log)


def test_the_part_reopen_proves_the_saved_caches_before_any_forced_rebuild() -> None:
    source = inspect.getsource(build_cone_gear.build)
    reopened = source.index('"reopen saved cone-gear"')
    caches = source.index("assert_saved_caches_regenerate(adapter)", reopened)
    forced = source.index("assert_saved_configuration_topology(", reopened)
    assert reopened < caches < forced


def test_the_save_pass_force_rebuilds_every_configuration_active_ending_on_t120(
    cone_gear,
) -> None:
    adapter, part = cone_gear(bad=SWAPPED)
    build_cone_gear.rebuild_each_configuration_active(adapter)
    assert [entry for entry in part.log if entry.startswith("force")] == [
        f"force {name}" for name in (*CONE_GEAR[:-1], "T120")
    ]
    assert part.active == "T120"
    # What the save then persists regenerates the way the drive train loads it.
    build_cone_gear.assert_saved_caches_regenerate(adapter)


def test_a_configuration_still_faulted_after_its_active_rebuild_stops_the_save(
    cone_gear,
) -> None:
    adapter, _part = cone_gear(bad=("T006", "T060"), stuck=("T060",))
    with pytest.raises(
        RuntimeError,
        match=r"did not rebuild clean while active: "
        r"T060: \['ToothGapCut \(1\)', 'ToothGapPattern \(1\)'\]$",
    ):
        build_cone_gear.rebuild_each_configuration_active(adapter)


def test_the_save_tail_rebuilds_each_configuration_active_right_before_save3() -> None:
    source = inspect.getsource(build_cone_gear.build)
    assert "ForceRebuildAll" not in source
    marks = source.index("AddRebuildSaveMark(2")
    rebuild = source.index("rebuild_each_configuration_active(adapter)")
    save = source.index('label="rebuild and persist all marked configurations"')
    assert marks < rebuild < save
    between = source[rebuild:save]
    for edit in ("apply_", "set_dimension", "mark_dimensions", "set_global"):
        assert edit not in between
