"""Cross-sheet offline contracts for the eight pinion-cluster drawings."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import _assembly
import _config
import _interference_contracts
import crank_handle_spec
import draw_pinion_cam_pin
import draw_pinion_handle
import pinion_bracket_spec
import pinion_cam_pin_spec
import pinion_cam_spec
import pinion_handle_spec
import pinion_lever_spec
import pinion_pivot_shaft_spec
import pinion_spring_spec
from _buildgraph import module_deps_of


SHEETS = (
    ("crank-handle", crank_handle_spec),
    ("pinion-bracket", pinion_bracket_spec),
    ("pinion-cam", pinion_cam_spec),
    ("pinion-cam-pin", pinion_cam_pin_spec),
    ("pinion-handle", pinion_handle_spec),
    ("pinion-lever", pinion_lever_spec),
    ("pinion-pivot-shaft", pinion_pivot_shaft_spec),
    ("pinion-spring", pinion_spring_spec),
)

TITLE_BLOCK_OWNED_NOTE_TEXT = (
    "ALL DIMENSIONS",
    "BREAK EDGES",
    "BREAK SHARP",
    "DEBUR",
    "EDGE BREAK",
    "FINISH:",
    "GENERAL TOLERANCE",
    "MATERIAL:",
    "REMOVE BURR",
    "SHARP EDGES",
    "U.O.S.",
    "UNLESS OTHERWISE SPECIFIED",
    " UOS",
)


def test_notes_do_not_repeat_title_block_metadata() -> None:
    for part_name, spec in SHEETS:
        notes = spec.DRAWING_NOTES.upper()
        for duplicate in TITLE_BLOCK_OWNED_NOTE_TEXT:
            assert duplicate not in notes, f"{part_name}: {duplicate}"


def test_finish_field_does_not_repeat_generic_edge_break_instruction() -> None:
    for part_name, _spec in SHEETS:
        finish = str(_config.parts(part_name)["finish"]).upper()
        assert "DEBUR" not in finish, part_name
        assert "REMOVE BURR" not in finish, part_name
        assert "BREAK SHARP" not in finish, part_name


def test_part_numbers_are_unique_across_the_complete_registry() -> None:
    by_number: dict[str, list[str]] = {}
    for part_name, part in _config.parts().items():
        by_number.setdefault(str(part["number"]), []).append(part_name)

    duplicates = {
        number: names for number, names in by_number.items() if len(names) > 1
    }
    assert duplicates == {}


def test_new_pin_and_spring_numbers_use_reserved_unique_allocations() -> None:
    assert _config.parts("pinion-cam-pin")["number"] == "MHA-116"
    assert _config.parts("pinion-spring")["number"] == "MHA-114"


def test_drawing_notes_do_not_change_the_drive_train_recipe() -> None:
    scripts = Path(__file__).resolve().parent
    deps = {Path(path).name for path in module_deps_of(scripts / "build_drive_train_assembly.py")}
    drawing_only = {
        "pinion_cam_spec.py",
        "pinion_cam_pin_spec.py",
        "pinion_handle_spec.py",
        "pinion_lever_spec.py",
        "pinion_spring_spec.py",
    }
    assert deps.isdisjoint(drawing_only)
    assert {
        "pinion_cam_geometry.py",
        "pinion_cam_pin_geometry.py",
        "pinion_handle_geometry.py",
        "pinion_lever_geometry.py",
        "pinion_spring_geometry.py",
    } <= deps


def test_drive_train_does_not_duplicate_bracket_geometry_constants() -> None:
    source = (Path(__file__).resolve().parent / "build_drive_train_assembly.py").read_text(
        encoding="utf-8"
    )
    for name in ("STRAP_T", "STRAP_R_END", "STRAP_C2C"):
        assert re.search(rf"^\s*{name}\s*=", source, re.MULTILINE) is None


def test_make_critical_free_text_is_formatted_from_geometry_constants() -> None:
    source_tokens = {
        crank_handle_spec: (
            "{2.0 * NECK_R:.2f}",
            "{HANDLE_MAX_DIA:.2f}",
            "{2.0 * CAP_R:.2f}",
        ),
        pinion_cam_spec: ("{ECC:.2f}", "{CAM_OD:.2f}"),
        draw_pinion_cam_pin: ("{CAP_SAG:.2f}",),
        pinion_handle_spec: (
            "{CAP_SAG:.2f}",
        ),
        draw_pinion_handle: ("z_max / 1000.0",),
        pinion_lever_spec: ("{HUB_LEN:.2f}", "{HUB_LEN / 2.0:.2f}"),
        pinion_pivot_shaft_spec: ("{CAP_SAG:.2f}",),
        pinion_spring_spec: (
            "{FLAT_LEN:.2f}",
            "{90.0 - BLADE_TILT_DEG + KINK_DEG:.2f}",
            "{HOLE_FROM_END:.2f}",
        ),
        pinion_bracket_spec: ("{R_END:.2f}",),
    }
    for module, tokens in source_tokens.items():
        source = Path(module.__file__).read_text(encoding="utf-8")
        for token in tokens:
            assert token in source, f"{Path(module.__file__).name}: {token}"


class _InterferenceComponent:
    def __init__(self, name: str) -> None:
        self.Name2 = name
        self.ReferencedConfiguration = ""


class _Interference:
    def __init__(self, names: tuple[str, str], volume_mm3: float) -> None:
        self.Components = [_InterferenceComponent(name) for name in names]
        self.Volume = volume_mm3 / 1e9


class _InterferenceManager:
    def __init__(self, interference: _Interference) -> None:
        self._interference = interference

    def GetInterferences(self) -> list[_Interference]:
        return [self._interference]

    def Done(self) -> None:
        pass


class _InterferenceAssembly:
    def __init__(self, interference: _Interference) -> None:
        self.InterferenceDetectionManager = _InterferenceManager(interference)

    def ToolsCheckInterference(self) -> None:
        pass


class _InterferenceAdapter:
    def __init__(self, interference: _Interference) -> None:
        self.currentModel = _InterferenceAssembly(interference)

    @staticmethod
    def _attempt(action, *, default=None):
        try:
            return action()
        except Exception:
            return default


def test_intentional_fit_allowance_is_pair_and_volume_bounded(monkeypatch) -> None:
    pair = ("pinion-bracket-1", "pinion-cam-pin-1")
    monkeypatch.setattr(_assembly, "_early_bound", lambda obj, *_args: obj)

    adapter = _InterferenceAdapter(_Interference(pair, 0.37))
    _assembly.check_no_interference(
        adapter,
        allowed_pairs={frozenset(pair): 0.45},
    )

    with pytest.raises(RuntimeError, match="0.46 mm\\^3"):
        _assembly.check_no_interference(
            _InterferenceAdapter(_Interference(pair, 0.46)),
            allowed_pairs={frozenset(pair): 0.45},
        )

    with pytest.raises(RuntimeError, match="pinion-cam-pin-2"):
        _assembly.check_no_interference(
            _InterferenceAdapter(
                _Interference(("pinion-bracket-1", "pinion-cam-pin-2"), 0.37)
            ),
            allowed_pairs={frozenset(pair): 0.45},
        )


def test_drive_train_allows_only_the_two_modeled_cam_pin_press_fits() -> None:
    allowed = _interference_contracts.allowed_interference_pairs("drive-train")
    assert set(allowed) == {
        frozenset(("pinion-bracket-1", "pinion-cam-pin-1")),
        frozenset(("pinion-bracket-2", "pinion-cam-pin-2")),
    }
    assert 0.40 < set(allowed.values()).pop() < 0.45
    assert _interference_contracts.allowed_interference_pairs("channel") == {}

    scripts = Path(_assembly.__file__).parent
    build_source = (scripts / "build_drive_train_assembly.py").read_text(
        encoding="utf-8"
    )
    verify_source = (scripts / "verify.py").read_text(encoding="utf-8")
    assembly_source = (scripts / "_assembly.py").read_text(encoding="utf-8")
    refresh_source = (scripts / "refresh_assembly.py").read_text(encoding="utf-8")
    assert "allowed_pairs=allowed_interference_pairs(ASM_NAME)" in build_source
    assert "allowed_pairs=allowed_interference_pairs(name)" in verify_source
    # The refresh gate gets the allowance from its ENTRYPOINT: the lookup lives
    # in refresh_assembly.py (outside every assembly's recipe closure) and is
    # parameter-threaded into _assembly.refresh_assembly. The common helper
    # must NOT import the contracts module itself -- that would fold the
    # press-fit constants into every assembly's recipe (codex #359).
    assert "allowed_pairs=allowed_interference_pairs(asm_name)" in refresh_source
    assert "allowed_pairs=allowed_pairs" in assembly_source
    assert "from _interference_contracts import" not in assembly_source
