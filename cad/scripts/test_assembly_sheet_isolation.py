"""Drawing-only assembly data stays out of every assembly builder's recipe.

An assembly's cache key is its builder's import closure
(``_buildgraph.module_deps_of``). BOM text, captions, assembly-sequence steps
and sheet precision reach no saved .SLDASM, so they live in drawing-only
modules -- ``draw_*.py``, ``*_assembly_sheet.py`` and the ``*_steps.py``
assembly sequences -- that no builder may import, or a wording edit re-keys
and rebuilds the assembly (and every gate behind it). Explode data the builder
authors lives in a pure ``*_explode_spec.py`` beside the builder's placement
spec.

The sheet and steps modules print numbers only by interpolating spec/model
symbols: a decimal, an inch fraction or a Ø size typed into one of their
string literals is a dimension restated by hand, and fails here.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import _buildgraph

SCRIPTS = Path(__file__).resolve().parent
ASSEMBLY_BUILDERS = tuple(
    _buildgraph.script_for(stem).resolve() for stem in _buildgraph.ASSEMBLY_ORDER
)
# A typed dimension: a decimal, an inch fraction, or a diameter sign on a digit.
_TYPED_DIMENSION = re.compile(r"\d+\.\d+|\d+/\d+|\u00d8\s*\d")


def is_drawing_only(name: str) -> bool:
    """Whether a script file name is a drawing-only module."""
    if name.startswith("test_"):
        return False
    return name.startswith("draw_") or name.endswith(
        ("_assembly_sheet.py", "_steps.py")
    )


def sheet_modules() -> tuple[Path, ...]:
    """Every sheet/steps module whose literals the second guard scans."""
    return tuple(
        sorted(
            path
            for path in SCRIPTS.glob("*.py")
            if is_drawing_only(path.name) and not path.name.startswith("draw_")
        )
    )


def drawing_only_deps(builder: Path) -> list[str]:
    """Drawing-only modules in ``builder``'s recipe closure."""
    return sorted(
        Path(dep).name
        for dep in _buildgraph.module_deps_of(builder)
        if is_drawing_only(Path(dep).name)
    )


def _not_printed(tree: ast.Module) -> set[int]:
    """Docstrings (prose for readers) and f-string format specs (``10.3f``)."""
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FormattedValue) and node.format_spec is not None:
            found.update(id(part) for part in ast.walk(node.format_spec))
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                found.add(id(body[0].value))
    return found


def typed_dimensions(source: str) -> list[tuple[int, str]]:
    """(line, literal) of every string literal piece that types a dimension.

    f-string interpolations are not literals, so ``f"{spec.X:.2f}"`` passes
    and ``"22.0"`` (or the literal head of ``f"22.0 {unit}"``) does not.
    """
    tree = ast.parse(source)
    skipped = _not_printed(tree)
    return sorted(
        (node.lineno, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in skipped
        and _TYPED_DIMENSION.search(node.value)
    )


def test_every_assembly_builder_is_checked() -> None:
    globbed = {path.resolve() for path in SCRIPTS.glob("build_*_assembly.py")}
    assert set(ASSEMBLY_BUILDERS) == globbed
    assert len(ASSEMBLY_BUILDERS) == 9


@pytest.mark.parametrize("builder", ASSEMBLY_BUILDERS, ids=lambda path: path.stem)
def test_assembly_builder_closure_has_no_drawing_only_module(builder: Path) -> None:
    assert drawing_only_deps(builder) == []


def test_sheet_modules_exist_to_scan() -> None:
    names = {path.name for path in sheet_modules()}
    assert {
        "ms_measuring_stick_assembly_sheet.py",
        "pd_paper_drive_assembly_steps.py",
        "ch_channel_assembly_steps.py",
        "dt_drive_train_steps.py",
    } <= names


@pytest.mark.parametrize("module", sheet_modules(), ids=lambda path: path.stem)
def test_sheet_text_interpolates_every_printed_number(module: Path) -> None:
    assert typed_dimensions(module.read_text(encoding="utf-8")) == []


def test_drawing_only_names() -> None:
    assert is_drawing_only("draw_ms_measuring_stick_assembly.py")
    assert is_drawing_only("ms_measuring_stick_assembly_sheet.py")
    assert is_drawing_only("pd_paper_drive_assembly_steps.py")
    assert is_drawing_only("dt_drive_train_steps.py")
    assert not is_drawing_only("ms_measuring_stick_assembly_spec.py")
    assert not is_drawing_only("ms_measuring_stick_explode_spec.py")
    assert not is_drawing_only("test_dt_drive_train_steps.py")


def test_typed_dimension_scan_catches_restated_numbers() -> None:
    source = '''"""Docstring 1.5 mm is prose."""
import spec
STEPS = (
    f"1. SET {spec.GAP:10.2f} mm; DIA {spec.DIA:.1f}",
    "2. FACE TO 22.0 mm",
    f"3. DRILL \\u00d83.3 AT {spec.X}",
    "4. 1/4 SCREW",
    f"5. \\u00d8{spec.DIA:.2f} THROUGH",
    "6. SEE SHEET 3",
)
'''
    found = typed_dimensions(source)
    assert [line for line, _text in found] == [5, 6, 7]
    assert found[0][1] == "2. FACE TO 22.0 mm"
