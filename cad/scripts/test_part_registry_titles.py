"""Every registry row names its part, and each drawing's document title agrees.

The title block's PART cell reads the part's summary Title, which
_common.part_properties stamps from the registry ``title:`` and otherwise
falls back to the raw stem. 51 drawn parts printed "cone-gear"-style stems
(MHA-013, MHA-096). So every row carries an explicit title. Where a drawing
script names its sheet (summary field 0, "<title> Manufacturing Drawing"),
the two must agree, so the PART cell and the document title can't drift apart.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import _config

SCRIPTS = Path(__file__).resolve().parent
# The sheet kinds a drawing script names in its summary field 0. Purchased
# reference sheets build theirs from the stamped Title at run time.
SHEET_SUFFIXES = (" Manufacturing Drawing", " — Modified Stock Drawing")


def _sheet_names(script: Path) -> list[str]:
    """Literal summary field-0 values passed to stamp_drawing_summary."""
    names: list[str] = []
    for node in ast.walk(ast.parse(script.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call):
            continue
        func = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
        if func != "stamp_drawing_summary":
            continue
        for arg in (*node.args, *(keyword.value for keyword in node.keywords)):
            if not isinstance(arg, ast.Dict):
                continue
            for key, value in zip(arg.keys, arg.values, strict=True):
                if isinstance(key, ast.Constant) and key.value == 0:
                    assert isinstance(value, ast.Constant), (
                        f"{script.name}: summary field 0 is not a literal"
                    )
                    names.append(str(value.value))
    return names


def _drawn_rows() -> list[tuple[str, Path]]:
    registry = _config.parts()
    rows = []
    for script in sorted(SCRIPTS.glob("draw_*.py")):
        stem = script.stem.removeprefix("draw_").replace("_", "-")
        if stem in registry:
            rows.append((stem, script))
    return rows


@pytest.mark.parametrize("stem", sorted(_config.parts()))
def test_every_registry_row_has_a_title_that_is_not_its_stem(stem: str) -> None:
    title = str(_config.parts(stem).get("title") or "").strip()
    assert title, f"{stem}: registry row has no title; the PART cell would print the stem"
    assert title != stem, f"{stem}: title repeats the stem"


@pytest.mark.parametrize(("stem", "script"), _drawn_rows(), ids=lambda value: str(value))
def test_a_drawing_names_its_sheet_after_the_registry_title(stem: str, script: Path) -> None:
    title = str(_config.parts(stem).get("title") or "")
    for name in _sheet_names(script):
        assert name in {f"{title}{suffix}" for suffix in SHEET_SUFFIXES}, (
            f"{script.name}: sheet named {name!r}, but the registry title is {title!r}"
        )


def test_the_drawn_row_scan_sees_the_named_sheets() -> None:
    # Guard the scan itself: a refactor that renamed stamp_drawing_summary
    # would otherwise pass the agreement test vacuously.
    named = [stem for stem, script in _drawn_rows() if _sheet_names(script)]
    assert len(named) >= 60, named
