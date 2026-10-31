"""SolidWorks-free contract for ``_rebuild.rebuild_stale_configurations`` and
``_rebuild.assert_saved_configurations_regenerate``.

pc-p1r: dt-drive-train.SLDASM opened with NeedsRebuild2=1 because MHA-DT-30's
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

import ast
import importlib
import inspect
import re
import unicodedata
from pathlib import Path

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


def test_the_save_chokepoint_checks_every_configuration_right_before_its_final_save() -> (
    None
):
    # Inside save_part_and_images: after every caller edit and every edit the
    # chokepoint itself makes (block tolerances, properties, summary info), and
    # nothing runs between it and the re-save that persists the part.
    source = inspect.getsource(_part_save.save_part_and_images)
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


SCRIPTS = Path(__file__).resolve().parent
CONFIGURATION_CREATORS = re.compile(
    r"create_configuration|AddConfiguration\d*|add_simplified_configurations"
)
TRIPWIRE = re.compile(r"assert_saved_configurations_regenerate\(adapter, (PART_NAME|part_name)\)")
SAVE = re.compile(
    r"(?:save_part_and_images|save_simplified_part|save_supplier_reference_part|"
    r"persist_configurations_in_place)\(adapter, (PART_NAME|part_name)\b"
)
FORCED_REBUILDS = ("ForceRebuild3", "set_active_configuration(", "assert_saved_configuration_topology(")


def _creates_configurations(path: Path, *, native_only: bool = False) -> bool:
    text = path.read_text(encoding="utf-8")
    # A matching call spells a creator name in its source, so skip parsing the
    # rest. Python NFKC-normalizes identifiers; search non-ASCII text normalized.
    spelled = text if text.isascii() else unicodedata.normalize("NFKC", text)
    if not CONFIGURATION_CREATORS.search(spelled):
        return False
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", getattr(node.func, "attr", ""))
        if (
            re.fullmatch(r"AddConfiguration\d*", name)
            if native_only
            else CONFIGURATION_CREATORS.fullmatch(name)
        ):
            return True
    return False


def _configuration_builders() -> set[str]:
    return {
        ".".join(path.relative_to(SCRIPTS).with_suffix("").parts)
        for path in SCRIPTS.rglob("build_*.py")
        if _creates_configurations(path)
    }


def test_configuration_creators_have_explicit_saved_cache_coverage() -> None:
    """Enroll actual calls, not comments; both missing and new producers fail."""
    assert _configuration_builders() == {
        "build_dt_crank_handle_ferrule",
        "build_dt_cone_gear",
        "build_dt_crank_handle_pivot_screw",
        "build_dt_pinion_lever_pin",
        "build_pd_transgear_removable",
        "build_dt_vn_cone_tip_collar",
        "build_ch_vn_spring_hook",
        "build_dt_vn_post_mount_screw",
        "build_pd_vn_transgear_pivot_screw",
        "build_sm_vn_boss_hook",
        "build_sm_vn_knife_hanger_stud",
    }


def test_only_the_known_helpers_create_configurations_outside_builders() -> None:
    """Each actual helper creator has separate native state-preservation coverage."""
    creators = {
        ".".join(path.relative_to(SCRIPTS).with_suffix("").parts)
        for path in SCRIPTS.rglob("_*.py")
        if _creates_configurations(path, native_only=True)
    }
    assert creators == {"_assembly", "_simplified_part", "_supplier_spring_reference"}


@pytest.mark.parametrize("nested", (False, True))
def test_new_configuration_authors_cannot_escape_the_inventory(
    monkeypatch, tmp_path, nested
) -> None:
    scripts = tmp_path / "scripts"
    directory = scripts / "nested" if nested else scripts
    directory.mkdir(parents=True)
    source = directory / "build_unregistered.py"
    source.write_text("adapter.create_configuration('Installed')\n", encoding="utf-8")
    monkeypatch.setitem(globals(), "SCRIPTS", scripts)
    expected = "nested.build_unregistered" if nested else "build_unregistered"
    assert _configuration_builders() == {expected}
    with pytest.raises(AssertionError):
        test_configuration_creators_have_explicit_saved_cache_coverage()


def test_configuration_inventory_cannot_pass_after_a_no_match_scan(
    monkeypatch, tmp_path
) -> None:
    source = tmp_path / "build_comment_only.py"
    source.write_text("# AddConfiguration3(...) is documentation, not a call\n", encoding="utf-8")
    monkeypatch.setitem(globals(), "SCRIPTS", tmp_path)
    assert not _configuration_builders()
    with pytest.raises(AssertionError):
        test_configuration_creators_have_explicit_saved_cache_coverage()


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
    module = importlib.import_module(stem)
    source = inspect.getsource(module.build)
    if "await adapter.open_model(" not in source:
        if "await save_simplified_part(" in source:
            return
        tree = ast.parse(source)
        callbacks = [
            keyword.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "build_stock_fastener"
            for keyword in node.keywords
            if keyword.arg == "save_threaded_part"
        ]
        assert len(callbacks) == 1 and isinstance(callbacks[0], ast.Name), (
            f"{stem}: configuration author has no proven saved-cache callback"
        )
        source = inspect.getsource(getattr(module, callbacks[0].id))
    _assert_reopened_then_tripwire(source)


@pytest.mark.parametrize(
    "build_source",
    (
        "async def build(adapter):\n    await build_stock_fastener(adapter)\n",
        "async def build(adapter):\n"
        "    await build_stock_fastener(adapter, save_threaded_part=choose_saver())\n",
    ),
)
def test_configuration_author_with_unknown_saver_fails_closed(
    monkeypatch, build_source
) -> None:
    class Producer:
        build = object()

    monkeypatch.setattr(importlib, "import_module", lambda _name: Producer)
    monkeypatch.setattr(inspect, "getsource", lambda _function: build_source)
    with pytest.raises(AssertionError, match="no proven saved-cache callback"):
        test_every_configuration_builder_proves_its_saved_caches_on_reopen("unknown")


def test_the_simplified_part_save_proves_its_saved_caches_on_reopen() -> None:
    import _simplified_part

    _assert_reopened_then_tripwire(inspect.getsource(_simplified_part.save_simplified_part))
