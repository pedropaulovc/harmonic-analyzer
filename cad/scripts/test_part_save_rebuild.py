"""SolidWorks-free contract for ``_rebuild.rebuild_stale_configurations`` and
``_rebuild.assert_saved_configurations_regenerate``.

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

import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

import _appearance
import _com
import _custom_properties
import _feature_tree
import _part_checks
import _part_properties
import _part_save
import _rebuild
import _session
import _sketch
import _sketch_rectangle


def cone_faults(configuration: str) -> tuple[tuple[str, int, bool], ...]:
    """Current native row names, unlike the historical incident names above."""
    return (
        (f"ToothGapCut{configuration}", 1, False),
        (f"ToothGapPattern{configuration}", 1, False),
    )


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
        self.part.fault_reads.add(self.part.active)
        faults = self.part.faults
        if self.part.active in self.part.bad:
            faults = (*faults, *cone_faults(self.part.active))
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
        self.fault_reads: set[str] = set()
        self.metadata: dict[str, object] = {}
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
    monkeypatch.setattr(_appearance, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(_com, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(_custom_properties, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(_feature_tree, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(_part_checks, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(_part_properties, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(_part_save, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(_rebuild, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(_session, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(_sketch, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(_sketch_rectangle, "_early_bound", lambda obj, _iface: obj)

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
    _rebuild.rebuild_stale_configurations(adapter, "dt-cone-gear")
    assert part.log == []


def test_a_stale_active_configuration_gets_one_edit_rebuild_all_and_no_switch(
    seat,
) -> None:
    """efae8d795's perf intent, kept by the 2026-09-27 ruling: nothing inactive
    is stale, so nothing switches."""
    adapter, part = seat({"Default": True})
    _rebuild.rebuild_stale_configurations(adapter, "dt-pinion-lever-pin")
    assert part.log == ["EditRebuildAll"]
    adapter, part = seat({"Default": True, "INSTALLED": False})
    _rebuild.rebuild_stale_configurations(adapter, "dt-pinion-lever-pin")
    assert part.log == ["EditRebuildAll"]


def test_a_stale_inactive_configuration_gets_one_switch_and_a_forced_rebuild(
    seat,
) -> None:
    """The 2026-09-27 ruling (replacing efae8d795's no-switch EditRebuildAll):
    one switch per stale inactive configuration, then the active one is shown
    again."""
    adapter, part = seat({"Default": False, "INSTALLED": True})
    _rebuild.rebuild_stale_configurations(adapter, "dt-pinion-lever-pin")
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
    _rebuild.rebuild_stale_configurations(adapter, "dt-cone-gear")
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
        _rebuild.rebuild_stale_configurations(adapter, "dt-cone-gear")


def test_a_refused_rebuild_raises_even_when_the_flags_read_clean(seat) -> None:
    # Codex P1 on #928: a feature that fails to rebuild can leave NeedsRebuild
    # false, so the rebuild's own verdict is enforced, not just recorded.
    adapter, _part = seat({"Default": True, "INSTALLED": False}, rebuild_result=False)
    with pytest.raises(RuntimeError, match=r"pinion-lever-pin: EditRebuildAll refused"):
        _rebuild.rebuild_stale_configurations(adapter, "dt-pinion-lever-pin")
    adapter, part = seat({"Default": False, "INSTALLED": True}, force_result=False)
    with pytest.raises(
        RuntimeError, match=r"INSTALLED: ForceRebuild3 returned False"
    ):
        _rebuild.rebuild_stale_configurations(adapter, "dt-pinion-lever-pin")
    assert part.active == "Default"


def test_a_hard_fault_after_the_rebuild_raises_but_a_warning_does_not(seat) -> None:
    adapter, _part = seat({"INSTALLED": True}, faults=(("Pin", 2, False),))
    with pytest.raises(RuntimeError, match=r"left faults \['Pin \(rebuild-error\)'\]"):
        _rebuild.rebuild_stale_configurations(adapter, "dt-pinion-lever-pin")
    adapter, part = seat({"INSTALLED": True}, faults=(("Pin", 1, True),))
    _rebuild.rebuild_stale_configurations(adapter, "dt-pinion-lever-pin")
    assert part.log == ["EditRebuildAll"]


def test_code_one_is_a_fault_unless_what_s_wrong_flags_it_a_warning(seat) -> None:
    # swFeatureError_e 1 is swFeatureErrorUnknown, not a warning: the warning
    # verdict comes only from GetWhatsWrong's is_warning array, as verify.py
    # and _assembly's health gates read it (Main's #928 review).
    adapter, _part = seat({"INSTALLED": True}, faults=(("Pin", 1, False),))
    with pytest.raises(RuntimeError, match=r"left faults \['Pin \(unknown-error\)'\]"):
        _rebuild.rebuild_stale_configurations(adapter, "dt-pinion-lever-pin")
    adapter, part = seat({"INSTALLED": True}, faults=(("Pin", 1, True),))
    _rebuild.rebuild_stale_configurations(adapter, "dt-pinion-lever-pin")
    assert part.log == ["EditRebuildAll"]
    assert _rebuild._FEATURE_ERROR[1] == "unknown-error"


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
        r"active: T060: \['ToothGapCutT060 \(unknown-error\)', "
        r"'ToothGapPatternT060 \(unknown-error\)'\]$",
    ):
        _rebuild.rebuild_stale_configurations(adapter, "dt-cone-gear")
    assert part.active == "T120"


@pytest.fixture
def saved_part(seat, monkeypatch, tmp_path):
    """Property edits dirty native state; saving and opening copy disk state.

    Only unrelated camera, visibility, property-authoring and export boundaries
    are substituted. The save chokepoint and configuration rebuilds run normally.
    """
    import _visibility

    def edit(adapter, field, configuration, value):
        model = adapter.currentModel
        model.metadata[field] = value
        model.configs[configuration].NeedsRebuild = True

    async def export_stl(adapter, path):
        adapter.exports.append(path)

    monkeypatch.setattr(
        _part_save._seat_forensics, "record_authoring_context", lambda *_args: None
    )
    monkeypatch.setattr(
        _visibility, "assert_reference_geometry_hidden", lambda *_args: None
    )
    monkeypatch.setattr(_part_save, "set_isometric_view", lambda _adapter: None)
    monkeypatch.setattr(_part_save, "export_part_stl", export_stl)
    monkeypatch.setattr(_part_save, "OUT_SLDPRT", tmp_path / "sldprt")
    monkeypatch.setattr(_part_save, "OUT_PNG", tmp_path / "png")
    monkeypatch.setattr(_part_save, "OUT_STL", tmp_path / "stl")
    monkeypatch.setattr(
        _part_save,
        "apply_block_tolerances",
        lambda adapter: edit(adapter, "tolerances", "Default", True),
    )
    monkeypatch.setattr(_part_save, "part_properties", lambda name: {"Title": name})
    monkeypatch.setattr(
        _part_save,
        "apply_custom_properties",
        lambda adapter, values: edit(adapter, "properties", "INSTALLED", dict(values)),
    )
    monkeypatch.setattr(
        _part_save,
        "apply_summary_info",
        lambda adapter, *, title: edit(adapter, "title", "SupplierStock", title),
    )

    def make(*, fail_save=None, **kwargs):
        adapter, part = seat(
            {"Default": False, "INSTALLED": False, "SupplierStock": False},
            active="INSTALLED",
            **kwargs,
        )
        saved: list[_Part] = []
        adapter.save_attempts = []
        adapter.exports = []

        async def save_file(path):
            adapter.save_attempts.append(path)
            if len(adapter.save_attempts) == fail_save:
                return SimpleNamespace(is_success=False, error="native save refused")
            saved.append(deepcopy(adapter.currentModel))
            return SimpleNamespace(is_success=True, data=None)

        async def open_model(_path):
            adapter.currentModel = deepcopy(saved[-1])
            adapter.currentModel.log.clear()
            return SimpleNamespace(is_success=True, data=None)

        adapter.save_file = save_file
        adapter.open_model = open_model
        return adapter, part, saved

    return make


def test_the_saved_part_contains_final_edits_and_clean_configuration_caches(
    saved_part,
) -> None:
    adapter, authored, saved = saved_part(bad=("Default", "SupplierStock"))
    artefacts = asyncio.run(
        _part_save.save_part_and_images(adapter, "fixture", views=())
    )
    expected = {
        "tolerances": True,
        "properties": {"Title": "fixture"},
        "title": "fixture",
    }
    assert saved[-1].metadata == expected
    assert not any(config.NeedsRebuild for config in saved[-1].configs.values())
    assert not saved[-1].bad
    assert saved[-1].active == "INSTALLED"

    # Read the saved state, not the still-open authoring object.
    authored.metadata.clear()
    asyncio.run(adapter.open_model(artefacts["part"]))
    reopened = adapter.currentModel
    assert reopened is not authored
    assert reopened.metadata == expected
    assert not any(config.NeedsRebuild for config in reopened.configs.values())
    _rebuild.assert_saved_configurations_regenerate(adapter, "fixture")
    assert set(reopened.log) >= {
        "edit Default",
        "edit INSTALLED",
        "edit SupplierStock",
    }
    assert reopened.active == "INSTALLED"
    assert not any(entry.startswith("force") for entry in reopened.log)


@pytest.mark.parametrize(
    "failure",
    ["inactive rebuild", "active rebuild", "hard fault", "stale", "final save"],
)
def test_a_failed_finalization_does_not_persist_the_edited_part(
    saved_part, failure
) -> None:
    kwargs = {
        "inactive rebuild": {"force_result": False},
        "active rebuild": {"rebuild_result": False},
        "hard fault": {"faults": (("Pin", 2, False),)},
        "stale": {"stuck": ("SupplierStock",)},
        "final save": {"fail_save": 2},
    }[failure]
    adapter, authored, saved = saved_part(**kwargs)
    with pytest.raises(RuntimeError):
        asyncio.run(_part_save.save_part_and_images(adapter, "fixture", views=()))
    assert authored.metadata == {
        "tolerances": True,
        "properties": {"Title": "fixture"},
        "title": "fixture",
    }
    assert authored.active == "INSTALLED"
    assert len(saved) == 1 and saved[0].metadata == {}
    assert len(adapter.save_attempts) == (2 if failure == "final save" else 1)
    assert adapter.exports == []
    if failure == "inactive rebuild":
        assert {"force Default", "force SupplierStock"} <= set(authored.log)
        assert "EditRebuildAll" not in authored.log
    elif failure == "active rebuild":
        assert "EditRebuildAll" in authored.log
        assert not any(config.NeedsRebuild for config in authored.configs.values())
    elif failure == "hard fault":
        assert {"Default", "SupplierStock"} <= authored.fault_reads
        assert "EditRebuildAll" not in authored.log
    elif failure == "stale":
        assert "force SupplierStock" in authored.log
        assert authored.configs["SupplierStock"].NeedsRebuild
    else:
        assert "EditRebuildAll" in authored.log
        assert not any(config.NeedsRebuild for config in authored.configs.values())


def test_a_refused_initial_save_leaves_no_saved_or_finalized_part(saved_part) -> None:
    adapter, authored, saved = saved_part(fail_save=1)
    with pytest.raises(RuntimeError):
        asyncio.run(_part_save.save_part_and_images(adapter, "fixture", views=()))
    assert len(adapter.save_attempts) == 1
    assert adapter.exports == []
    assert not saved
    assert authored.metadata == {}


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
    assert _rebuild.stale_configurations(part, CONE_GEAR) == []
    part.log.clear()
    with pytest.raises(RuntimeError) as failure:
        _rebuild.assert_saved_configurations_regenerate(adapter, "dt-cone-gear")
    message = str(failure.value)
    # Every faulted configuration remains diagnosable; prose and formatting
    # are not part of the regeneration contract.
    assert all(name in message for name in SWAPPED)
    assert all(
        feature in message
        for configuration in SWAPPED
        for feature, _code, _warning in cone_faults(configuration)
    )
    assert "T120:" not in message and "Default:" not in message
    assert not any(entry.startswith("force") for entry in part.log)
    assert part.bad == set(SWAPPED)
    assert part.active == "T120"


def test_the_chokepoint_heals_the_cg_fx1_caches_so_the_reopen_passes(seat) -> None:
    adapter, part = seat(
        {name: name != "T120" for name in CONE_GEAR}, active="T120", bad=SWAPPED
    )
    _rebuild.rebuild_stale_configurations(adapter, "dt-cone-gear")
    part.log.clear()
    _rebuild.assert_saved_configurations_regenerate(adapter, "dt-cone-gear")
    assert [entry for entry in part.log if entry.startswith("edit")] == [
        f"edit {name}" for name in (*CONE_GEAR[:-1], "T120")
    ]
    assert part.active == "T120"
    assert not any(entry.startswith("force") for entry in part.log)


def test_clean_saved_caches_pass_with_one_plain_rebuild_each_ending_on_active(
    seat,
) -> None:
    adapter, part = seat({name: False for name in CONE_GEAR}, active="T120")
    _rebuild.assert_saved_configurations_regenerate(adapter, "dt-cone-gear")
    assert [entry for entry in part.log if entry.startswith("edit")] == [
        f"edit {name}" for name in (*CONE_GEAR[:-1], "T120")
    ]
    assert part.active == "T120"
    assert not any(entry.startswith("force") for entry in part.log)


def test_a_single_configuration_part_regenerates_with_no_switch(seat) -> None:
    adapter, part = seat({"Default": False})
    _rebuild.assert_saved_configurations_regenerate(adapter, "dt-crank-pin")
    assert part.log == ["edit Default"]


