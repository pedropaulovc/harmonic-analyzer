"""SolidWorks-free contract for ``_common.rebuild_stale_configurations`` and
``_common.assert_saved_configurations_regenerate``.

pc-p1r: dt-drive-train.SLDASM opened with NeedsRebuild2=1 because MHA-DT-030's
INSTALLED configuration, the one the assembly places, was saved stale (amet
probe, dt-logs/pc-p1r/probe-saved-rebuild.jsonl).  The shared part-save
chokepoint reads every configuration first and leaves a clean part alone, and
it refuses to save a refused rebuild, a hard fault, or a configuration still
stale.

cg-fx1 (9459428ec, dt-logs/farm-runs/leaf-logs/cg-fx1-task.log:305-345): the
drive train swapped 19 cone-gear copies to T006..T114 and its EditRebuild3
failed, every copy on ToothGapCut + ToothGapPattern at error 1.  In the part,
each of those configurations faulted as loaded, a plain EditRebuild3 returned
False and left it faulted, and only an activated ForceRebuild3 cleared it --
all while NeedsRebuild read false.  efae8d795 had rebuilt stale inactive
configurations with one no-switch EditRebuildAll; the user's ruling
(2026-09-27, option (a)) moved the fix into the shared helper: exactly one
switch per stale INACTIVE configuration, and none when nothing inactive is
stale.  The double below reproduces the cg-fx1 seat behaviour.
"""

from __future__ import annotations

import importlib
import inspect
import re
from pathlib import Path

import pytest

import _common

CONE_FAULTS = (("ToothGapCut", 1, False), ("ToothGapPattern", 1, False))


class _Config:
    def __init__(self, name: str, stale: bool) -> None:
        self.Name = name
        self.NeedsRebuild = stale


class _Manager:
    def __init__(self, part: _Part) -> None:
        self.part = part

    @property
    def ActiveConfiguration(self):  # noqa: N802
        return self.part.configs[self.part.active]


class _Extension:
    def __init__(self, part: _Part) -> None:
        self.part = part

    def EditRebuildAll(self) -> bool:  # noqa: N802
        # cg-fx1: clears NeedsRebuild everywhere, repairs no bad cache.
        self.part.log.append("EditRebuildAll")
        for name, config in self.part.configs.items():
            if name not in self.part.stuck:
                config.NeedsRebuild = False
        return self.part.rebuild_result

    def GetWhatsWrong(self):  # noqa: N802
        faults = self.part.faults
        if self.part.active in self.part.bad:
            faults = (*faults, *CONE_FAULTS)
        names, codes, warnings = zip(*faults) if faults else ((), (), ())
        return True, [_Feature(name) for name in names], list(codes), list(warnings)


class _Feature:
    def __init__(self, name: str) -> None:
        self.Name = name


class _Part:
    """An IModelDoc2 double.  It records every rebuild or activation call, so a
    test can prove which ones the chokepoint made.

    ``bad`` configurations carry cg-fx1's saved caches: faulted while shown, a
    plain EditRebuild3 returns False over them, and only ForceRebuild3 while
    active repairs them.  ``stuck`` ones no rebuild repairs or un-stales.
    """

    def __init__(
        self,
        stale: dict[str, bool],
        *,
        active: str | None = None,
        bad: tuple[str, ...] = (),
        stuck: tuple[str, ...] = (),
        rebuild_result: bool = True,
        force_result: bool = True,
        faults: tuple[tuple[str, int, bool], ...] = (),
    ) -> None:
        self.configs = {name: _Config(name, flag) for name, flag in stale.items()}
        self.active = active or next(iter(self.configs))
        self.bad = set(bad)
        self.stuck = set(stuck)
        self.rebuild_result = rebuild_result
        self.force_result = force_result
        self.faults = faults
        self.log: list[str] = []
        self.ConfigurationManager = _Manager(self)
        self.Extension = _Extension(self)

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
            self.configs[self.active].NeedsRebuild = False
        return self.force_result


class _Adapter:
    def __init__(self, part: _Part) -> None:
        self.currentModel = part

    def _attempt(self, fn, default=None):
        return fn()

    async def set_active_configuration(self, name: str):
        raise AssertionError("the chokepoint switches with ShowConfiguration2 only")


@pytest.fixture
def seat(monkeypatch):
    monkeypatch.setattr(_common, "_early_bound", lambda obj, _iface: obj)

    def make(stale, **kwargs):
        part = _Part(stale, **kwargs)
        return _Adapter(part), part

    return make


CONE_GEAR = ("Default", *(f"T{teeth:03d}" for teeth in range(6, 121, 6)))
SWAPPED = CONE_GEAR[1:-1]  # T006..T114, the configurations the copies take


def _switches(part: _Part) -> list[str]:
    return [entry for entry in part.log if entry.startswith("show")]


# --- rebuild_stale_configurations ---------------------------------------------


def test_a_clean_part_gets_no_rebuild_call_at_all(seat) -> None:
    adapter, part = seat({name: False for name in CONE_GEAR}, active="T120")
    _common.rebuild_stale_configurations(adapter, "dt-cone-gear")
    assert part.log == []


def test_a_stale_active_configuration_gets_one_edit_rebuild_all_and_no_switch(
    seat,
) -> None:
    """efae8d795's perf intent, kept by the 2026-09-27 ruling: nothing inactive
    is stale, so nothing switches."""
    adapter, part = seat({"Default": True})
    _common.rebuild_stale_configurations(adapter, "dt-pinion-lever-pin")
    assert part.log == ["EditRebuildAll"]
    adapter, part = seat({"Default": True, "INSTALLED": False})
    _common.rebuild_stale_configurations(adapter, "dt-pinion-lever-pin")
    assert part.log == ["EditRebuildAll"]


def test_a_stale_inactive_configuration_gets_one_switch_and_a_forced_rebuild(
    seat,
) -> None:
    """The 2026-09-27 ruling (replacing efae8d795's no-switch EditRebuildAll):
    one switch per stale inactive configuration, then the active one is shown
    again."""
    adapter, part = seat({"Default": False, "INSTALLED": True})
    _common.rebuild_stale_configurations(adapter, "dt-pinion-lever-pin")
    assert part.log == ["show INSTALLED", "force INSTALLED", "show Default"]
    assert part.active == "Default"
    assert not any(config.NeedsRebuild for config in part.configs.values())


def test_many_stale_configurations_switch_once_each_and_end_on_the_active_one(
    seat,
) -> None:
    """Cone gear, every configuration stale, T120 active: 20 switches for the
    20 stale inactive ones, one back to T120, and T120 itself keeps the single
    EditRebuildAll (efae8d795's no-switch rebuild for the active one)."""
    adapter, part = seat({name: True for name in CONE_GEAR}, active="T120")
    _common.rebuild_stale_configurations(adapter, "dt-cone-gear")
    inactive = [name for name in CONE_GEAR if name != "T120"]
    assert _switches(part) == [f"show {name}" for name in (*inactive, "T120")]
    assert [entry for entry in part.log if entry.startswith("force")] == [
        f"force {name}" for name in inactive
    ]
    assert part.log[-1] == "EditRebuildAll"
    assert part.active == "T120"


def test_configurations_still_stale_after_the_rebuild_raise_naming_part_and_all(
    seat,
) -> None:
    adapter, _part = seat(
        {name: True for name in CONE_GEAR[:5]}, active="Default", stuck=("T006", "T018")
    )
    with pytest.raises(
        RuntimeError, match=r"cone-gear: configurations \['T006', 'T018'\]"
    ):
        _common.rebuild_stale_configurations(adapter, "dt-cone-gear")


def test_a_refused_rebuild_raises_even_when_the_flags_read_clean(seat) -> None:
    # Codex P1 on #928: a feature that fails to rebuild can leave NeedsRebuild
    # false, so the rebuild's own verdict is enforced, not just recorded.
    adapter, _part = seat({"Default": True, "INSTALLED": False}, rebuild_result=False)
    with pytest.raises(RuntimeError, match=r"pinion-lever-pin: EditRebuildAll refused"):
        _common.rebuild_stale_configurations(adapter, "dt-pinion-lever-pin")
    adapter, part = seat({"Default": False, "INSTALLED": True}, force_result=False)
    with pytest.raises(
        RuntimeError, match=r"INSTALLED: ForceRebuild3 returned False"
    ):
        _common.rebuild_stale_configurations(adapter, "dt-pinion-lever-pin")
    assert part.active == "Default"


def test_a_hard_fault_after_the_rebuild_raises_but_a_warning_does_not(seat) -> None:
    adapter, _part = seat({"INSTALLED": True}, faults=(("Pin", 2, False),))
    with pytest.raises(RuntimeError, match=r"left faults \['Pin \(rebuild-error\)'\]"):
        _common.rebuild_stale_configurations(adapter, "dt-pinion-lever-pin")
    adapter, part = seat({"INSTALLED": True}, faults=(("Pin", 1, True),))
    _common.rebuild_stale_configurations(adapter, "dt-pinion-lever-pin")
    assert part.log == ["EditRebuildAll"]


def test_code_one_is_a_fault_unless_what_s_wrong_flags_it_a_warning(seat) -> None:
    # swFeatureError_e 1 is swFeatureErrorUnknown, not a warning: the warning
    # verdict comes only from GetWhatsWrong's is_warning array, as verify.py
    # and _assembly's health gates read it (Main's #928 review).
    adapter, _part = seat({"INSTALLED": True}, faults=(("Pin", 1, False),))
    with pytest.raises(RuntimeError, match=r"left faults \['Pin \(unknown-error\)'\]"):
        _common.rebuild_stale_configurations(adapter, "dt-pinion-lever-pin")
    adapter, part = seat({"INSTALLED": True}, faults=(("Pin", 1, True),))
    _common.rebuild_stale_configurations(adapter, "dt-pinion-lever-pin")
    assert part.log == ["EditRebuildAll"]
    assert _common._FEATURE_ERROR[1] == "unknown-error"


def test_an_inactive_configuration_still_faulted_while_active_stops_the_save(
    seat,
) -> None:
    adapter, part = seat(
        {name: True for name in CONE_GEAR},
        active="T120",
        bad=("T006", "T060"),
        stuck=("T060",),
    )
    with pytest.raises(
        RuntimeError,
        match=r"cone-gear: stale inactive configurations did not rebuild clean while "
        r"active: T060: \['ToothGapCut \(unknown-error\)', "
        r"'ToothGapPattern \(unknown-error\)'\]$",
    ):
        _common.rebuild_stale_configurations(adapter, "dt-cone-gear")
    assert part.active == "T120"


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


# --- assert_saved_configurations_regenerate -----------------------------------


def test_edit_rebuild_all_alone_leaves_the_cg_fx1_caches_that_fail_the_reopen(
    seat,
) -> None:
    """Fail-first on the double: efae8d795's no-switch EditRebuildAll clears
    NeedsRebuild but leaves the T00x caches faulted, and the reopen tripwire
    names them without repairing anything."""
    adapter, part = seat(
        {name: name != "T120" for name in CONE_GEAR}, active="T120", bad=SWAPPED
    )
    assert part.Extension.EditRebuildAll()
    assert _common.stale_configurations(part, CONE_GEAR) == []
    part.log.clear()
    with pytest.raises(RuntimeError, match="do not regenerate") as failure:
        _common.assert_saved_configurations_regenerate(adapter, "dt-cone-gear")
    message = str(failure.value)
    # cg-fx2a's shape (dt-logs/farm-runs/leaf-logs/cg-fx2a-task.log:486), with
    # the fleet's named fault codes: one entry per faulted configuration.
    faulted = "['ToothGapCut (unknown-error)', 'ToothGapPattern (unknown-error)']"
    assert message == (
        "saved cone-gear configurations do not regenerate the way a placing "
        "assembly loads them (activate, then a plain EditRebuild3): "
        + "; ".join(
            f"{name}: loaded {faulted}, EditRebuild3=False, after {faulted}"
            for name in SWAPPED
        )
    )
    assert "T120:" not in message and "Default:" not in message
    assert not any(entry.startswith("force") for entry in part.log)


def test_the_chokepoint_heals_the_cg_fx1_caches_so_the_reopen_passes(seat) -> None:
    adapter, part = seat(
        {name: name != "T120" for name in CONE_GEAR}, active="T120", bad=SWAPPED
    )
    _common.rebuild_stale_configurations(adapter, "dt-cone-gear")
    part.log.clear()
    _common.assert_saved_configurations_regenerate(adapter, "dt-cone-gear")
    assert [entry for entry in part.log if entry.startswith("edit")] == [
        f"edit {name}" for name in (*CONE_GEAR[:-1], "T120")
    ]
    assert part.active == "T120"
    assert not any(entry.startswith("force") for entry in part.log)


def test_clean_saved_caches_pass_with_one_plain_rebuild_each_ending_on_active(
    seat,
) -> None:
    adapter, part = seat({name: False for name in CONE_GEAR}, active="T120")
    _common.assert_saved_configurations_regenerate(adapter, "dt-cone-gear")
    assert [entry for entry in part.log if entry.startswith("edit")] == [
        f"edit {name}" for name in (*CONE_GEAR[:-1], "T120")
    ]
    assert part.active == "T120"
    assert not any(entry.startswith("force") for entry in part.log)


def test_a_single_configuration_part_regenerates_with_no_switch(seat) -> None:
    adapter, part = seat({"Default": False})
    _common.assert_saved_configurations_regenerate(adapter, "dt-crank-pin")
    assert part.log == ["edit Default"]


SCRIPTS = Path(__file__).resolve().parent
CONFIGURATION_CREATORS = re.compile(
    r"\bcreate_configuration\(|\bAddConfiguration\d*\(|\badd_simplified_configurations\("
)
TRIPWIRE = re.compile(r"assert_saved_configurations_regenerate\(adapter, (PART_NAME|part_name)\)")
SAVE = re.compile(r"save_part_and_images\(adapter, (PART_NAME|part_name)\b")
FORCED_REBUILDS = ("ForceRebuild3", "set_active_configuration(", "assert_saved_configuration_topology(")


def _configuration_builders() -> set[str]:
    return {
        path.stem
        for path in SCRIPTS.glob("build_*.py")
        if CONFIGURATION_CREATORS.search(path.read_text(encoding="utf-8"))
    }


def test_the_builders_that_create_configurations_are_the_known_five() -> None:
    """A new multi-configuration builder must fail here until it reopens its
    saved part and runs the tripwire (and joins this set).  Every other builder
    that derives drawing configurations goes through save_simplified_part,
    which reopens and runs the tripwire itself."""
    assert _configuration_builders() == {
        "build_dt_crank_handle_ferrule",
        "build_dt_cone_gear",
        "build_dt_crank_handle_pivot_screw",
        "build_dt_pinion_lever_pin",
        "build_pd_transgear_removable",
    }


def test_only_the_known_helpers_create_configurations_outside_builders() -> None:
    """The part-tier simplified-configuration helper and the assembly save
    chokepoint's Default Simplified are the only other creators."""
    creators = {
        path.stem
        for path in SCRIPTS.glob("_*.py")
        if re.search(r"\bAddConfiguration\d*\(", path.read_text(encoding="utf-8"))
    }
    assert creators == {"_assembly", "_drawing_simplified"}


def _assert_reopened_then_tripwire(source: str) -> None:
    reopened = source.rindex("await adapter.open_model(")
    tripwire = TRIPWIRE.search(source, reopened)
    assert tripwire is not None
    between = source[reopened : tripwire.start()]
    assert not [call for call in FORCED_REBUILDS if call in between]
    assert max(match.start() for match in SAVE.finditer(source)) < reopened


@pytest.mark.parametrize("stem", sorted(_configuration_builders()))
def test_every_configuration_builder_proves_its_saved_caches_on_reopen(stem) -> None:
    """Reopen, then the tripwire, with nothing force-rebuilding in between: a
    forced rebuild would repair the very caches the tripwire has to read.  A
    builder that saves through save_simplified_part inherits its reopen."""
    source = inspect.getsource(importlib.import_module(stem).build)
    if "await adapter.open_model(" not in source:
        assert "await save_simplified_part(" in source
        return
    _assert_reopened_then_tripwire(source)


def test_the_simplified_part_save_proves_its_saved_caches_on_reopen() -> None:
    import _drawing_simplified

    _assert_reopened_then_tripwire(inspect.getsource(_drawing_simplified.save_simplified_part))
