"""Offline contracts for the paper-drive ASSEMBLY drawing."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import draw_paper_drive_assembly as drawing
from _drawing_registry import DRAWINGS_BY_NAME

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_dodo():
    spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_registry_row_resolves_the_assembly_source() -> None:
    spec = DRAWINGS_BY_NAME["paper_drive_assembly"]
    assert spec.source_kind == "assembly"
    assert spec.part == "paper_drive"
    assert spec.source.as_posix().endswith("/out/sldasm/paper-drive.SLDASM")
    assert spec.script == Path(drawing.__file__).resolve()


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith(
        "/slddrw/paper-drive-assembly.SLDDRW"
    )
    assert drawing.PDF.as_posix().endswith("/pdf/paper-drive-assembly.pdf")
    assert drawing.PNG.as_posix().endswith(
        "/png/paper-drive-assembly_drawing.png"
    )
    assert drawing.SOURCE == DRAWINGS_BY_NAME["paper_drive_assembly"].source


def test_dodo_uses_the_assembly_recipe_and_token() -> None:
    dodo = _load_dodo()
    deps = dodo._drawing_file_deps("paper_drive_assembly")
    assert any(
        dep.replace("\\", "/").endswith("/out/sldasm/paper-drive.SLDASM")
        for dep in deps
    )
    assert dodo._assembly_execution_token("paper_drive") in deps
    assert dodo._part_execution_token("paper_drive") not in deps
    task = next(
        task
        for task in dodo.task_drawing()
        if task["name"] == "paper_drive_assembly"
    )
    assert {Path(target).name for target in task["targets"]} == {
        "paper-drive-assembly.SLDDRW",
        "paper-drive-assembly.pdf",
        "paper-drive-assembly_drawing.png",
    }


def test_assembly_owns_see_parts_list_title_block() -> None:
    source = (Path(__file__).parent / "build_paper_drive_assembly.py").read_text(
        encoding="utf-8"
    )
    assert '"MHA-A06"' in source
    assert "assembly_title_properties(ASM_NAME)" in source
    assert "part_properties(ASM_NAME)" not in source
    assert source.count('"Material": "SEE COMPONENT DRAWINGS"') == 1
    assert source.count('"Material Specification": "SEE COMPONENT DRAWINGS"') == 1
    assert source.count('"Finish": "SEE COMPONENT DRAWINGS"') == 1


def test_drawing_is_one_simple_three_view_diagram() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("place_view(") == 3
    assert source.count("scale=VIEW_SCALE") == 3
    assert "for view in (front, right, iso):" in source
    assert '"*Front"' in source
    assert '"*Right"' in source
    assert '"*Isometric"' in source
    assert "insert_identified_bom_table(" not in source
    assert "add_auto_balloons" not in source
    assert "add_component_bom_balloons(" not in source
    assert "isolate_drawing_view_components(" not in source
    assert "add_note(" not in source
    assert drawing.SHEET_SCALE == (1.0, 5.0)
    assert drawing.VIEW_SCALE == (1, 5)
    assert drawing.SHEET_NAMES == ("THREE-VIEW DIAGRAM",)
    assert "expected_sheet_names=SHEET_NAMES" in source
