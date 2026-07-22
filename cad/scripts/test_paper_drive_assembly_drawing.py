"""Offline contracts for the paper-drive ASSEMBLY drawing."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import _chain
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


def test_bom_covers_every_top_level_component_family() -> None:
    source = (Path(__file__).parent / "build_paper_drive_assembly.py").read_text(
        encoding="utf-8"
    )
    for component in drawing.BOM_COMPONENTS:
        assert f'"{component}"' in source, f"{component} not placed by build"
    assert len(drawing.BOM_COMPONENTS) == 22


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


def test_drawing_places_bom_balloons_and_specific_notes() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("insert_identified_bom_table(") == 1
    assert 'configuration_grouping="same-part"' in source
    assert source.count("add_auto_balloons_across_views(") == 1
    assert "(iso, front, right)," in source
    assert source.count("add_note(") == 4
    assert source.count("place_view(") == 7
    assert source.count("scale=VIEW_SCALE") == 5
    assert source.count("scale=ISO_VIEW_SCALE") == 1
    assert source.count("isolate_drawing_view_components(") == 1
    assert source.count("add_component_bom_balloons(") == 1
    assert "existing_balloons=targeted_balloons" in source
    assert drawing.SHEET_SCALE == (1.0, 5.0)
    assert drawing.VIEW_SCALE == (1, 5)
    assert drawing.ISO_VIEW_SCALE == (1, 7)
    assert drawing.SHEET_NAMES == (
        "GENERAL ASSEMBLY",
        "PARTS LIST AND ITEM IDENTIFICATION",
    )
    assert "expected_sheet_names=SHEET_NAMES" in source
    assert f"{_chain.LINK_COUNT}-LINK CHAIN" in drawing.ASSEMBLY_NOTES
    assert "T24 AND T12 SPROCKETS" in drawing.ASSEMBLY_NOTES
    assert all(
        token not in drawing.ASSEMBLY_NOTES
        for token in ("MATERIAL", "FINISH", "UOS", "DEBUR", "BREAK SHARP")
    )
