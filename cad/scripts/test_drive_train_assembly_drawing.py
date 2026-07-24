"""Offline contracts for the drive-train three-view reference drawing."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import draw_drive_train_assembly as drawing
from _drawing_registry import DRAWINGS_BY_NAME


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_dodo():
    spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_registry_row_resolves_the_assembly_source() -> None:
    spec = DRAWINGS_BY_NAME["drive_train_assembly"]
    assert spec.source_kind == "assembly"
    assert spec.part == "drive_train"
    assert spec.source.as_posix().endswith("/out/sldasm/drive-train.SLDASM")
    assert spec.script == Path(drawing.__file__).resolve()


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith(
        "/slddrw/drive-train-assembly.SLDDRW"
    )
    assert drawing.PDF.as_posix().endswith("/pdf/drive-train-assembly.pdf")
    assert drawing.PNG.as_posix().endswith(
        "/png/drive-train-assembly_drawing.png"
    )
    assert drawing.SOURCE == DRAWINGS_BY_NAME["drive_train_assembly"].source


def test_dodo_uses_the_assembly_recipe_and_token() -> None:
    dodo = _load_dodo()
    deps = dodo._drawing_file_deps("drive_train_assembly")
    assert any(
        dep.replace("\\", "/").endswith("/out/sldasm/drive-train.SLDASM")
        for dep in deps
    )
    assert dodo._assembly_execution_token("drive_train") in deps
    assert dodo._part_execution_token("drive_train") not in deps
    task = next(
        task
        for task in dodo.task_drawing()
        if task["name"] == "drive_train_assembly"
    )
    assert {Path(target).name for target in task["targets"]} == {
        "drive-train-assembly.SLDDRW",
        "drive-train-assembly.pdf",
        "drive-train-assembly_drawing.png",
    }


def test_reference_sheet_is_exactly_three_hlr_views() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert drawing.SHEET_SCALE == (1.0, 3.0)
    assert drawing.VIEW_SCALE == (1, 3)
    assert source.count("place_view(") == 3
    assert '"*Front"' in source
    assert '"*Right"' in source
    assert '"*Isometric"' in source
    assert "for view in (front, right, iso):" in source
    assert "set_hidden_lines_removed(adapter, view)" in source


def test_reference_sheet_omits_redesign_owned_documentation() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for removed in (
        "BOM_COMPONENTS",
        "insert_identified_bom_table",
        "add_component_bom_balloons",
        "add_auto_balloons",
        "isolate_drawing_view_components",
        "create_blank_drawing_sheets",
        "ASSEMBLY_NOTES",
        "ACCEPTANCE_ROWS",
        "GEAR_PAIR_ROWS",
    ):
        assert removed not in source


def test_assembly_owns_see_component_drawings_title_block() -> None:
    source = (Path(__file__).parent / "build_drive_train_assembly.py").read_text(
        encoding="utf-8"
    )
    assert '"MHA-A03"' in source
    assert "assembly_title_properties(ASM_NAME)" in source
    assert "part_properties(ASM_NAME)" not in source
    assert source.count('"Material": "SEE COMPONENT DRAWINGS"') == 1
    assert source.count('"Material Specification": "SEE COMPONENT DRAWINGS"') == 1
    assert source.count('"Finish": "SEE COMPONENT DRAWINGS"') == 1
