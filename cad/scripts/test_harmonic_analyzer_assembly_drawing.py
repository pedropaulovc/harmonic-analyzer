"""Offline contracts for the top-level harmonic-analyzer ASSEMBLY drawing."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import draw_harmonic_analyzer_assembly as drawing
from _drawing_registry import DRAWINGS, DRAWINGS_BY_NAME

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_dodo():
    spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_registry_row_resolves_the_assembly_source() -> None:
    spec = DRAWINGS_BY_NAME["harmonic_analyzer_assembly"]
    assert spec.source_kind == "assembly"
    assert spec.part == "harmonic_analyzer"
    assert spec.source.as_posix().endswith("/out/sldasm/harmonic-analyzer.SLDASM")
    assert spec.script == Path(drawing.__file__).resolve()


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith(
        "/slddrw/harmonic-analyzer-assembly.SLDDRW"
    )
    assert drawing.PDF.as_posix().endswith("/pdf/harmonic-analyzer-assembly.pdf")
    assert drawing.PNG.as_posix().endswith(
        "/png/harmonic-analyzer-assembly_drawing.png"
    )
    assert drawing.SOURCE == DRAWINGS_BY_NAME["harmonic_analyzer_assembly"].source


def test_part_rows_keep_their_part_source() -> None:
    for spec in DRAWINGS:
        if spec.source_kind == "assembly":
            continue
        assert spec.source.as_posix().endswith(
            f"/out/sldprt/{spec.artifact_stem}.SLDPRT"
        )


def test_dodo_deps_use_the_sldasm_recipe_and_exact_assembly_token() -> None:
    dodo = _load_dodo()
    deps = dodo._drawing_file_deps("harmonic_analyzer_assembly")
    assert any(
        dep.replace("\\", "/").endswith("/out/sldasm/harmonic-analyzer.SLDASM")
        for dep in deps
    )
    assert dodo._assembly_execution_token("harmonic-analyzer") in deps
    assert any(dep.endswith("harmonic-analyzer-assembly.DRWDOT") for dep in deps)


def test_dodo_yields_the_assembly_drawing_task() -> None:
    dodo = _load_dodo()
    assert "harmonic_analyzer_assembly" in dodo._drawing_order()
    task = next(
        task
        for task in dodo.task_drawing()
        if task["name"] == "harmonic_analyzer_assembly"
    )
    targets = {Path(target).name for target in task["targets"]}
    assert targets == {
        "harmonic-analyzer-assembly.SLDDRW",
        "harmonic-analyzer-assembly.pdf",
        "harmonic-analyzer-assembly_drawing.png",
    }


def test_bom_covers_every_top_level_component() -> None:
    """Every BOM row is a top-level component the machine build inserts.

    The seven subassemblies are inserted from the SUBASSEMBLIES tuple and the
    measuring stick via place_component, so the check is a string presence test
    -- the runtime insert_bom_table validates one BOM row per component.
    """
    source = (
        Path(__file__).parent / "build_harmonic_analyzer_assembly.py"
    ).read_text(encoding="utf-8")
    for component in drawing.BOM_COMPONENTS:
        assert f'"{component}"' in source, f"{component} not a top-level component"


def test_assembly_stamps_title_block_properties() -> None:
    source = (
        Path(__file__).parent / "build_harmonic_analyzer_assembly.py"
    ).read_text(encoding="utf-8")
    assert "apply_custom_properties" in source
    assert "SEE COMPONENT DRAWINGS" in source
    assert "assembly_title_properties(ASM_NAME)" in source
    assert "part_properties(ASM_NAME)" not in source
    assert '"MHA-A08"' in source
    assert source.count('"Material": "SEE COMPONENT DRAWINGS"') == 1
    assert source.count('"Material Specification": "SEE COMPONENT DRAWINGS"') == 1
    assert source.count('"Finish": "SEE COMPONENT DRAWINGS"') == 1


def test_drawing_places_bom_and_balloons() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("insert_identified_bom_table(") == 1
    assert source.count("add_component_bom_balloons(") == 3
    balloon_items = (
        drawing.FRONT_BALLOON_ITEMS
        + drawing.RIGHT_BALLOON_ITEMS
        + drawing.ISO_BALLOON_ITEMS
    )
    assert {item for _stem, item in balloon_items} == {
        str(item) for item in range(1, len(drawing.BOM_COMPONENTS) + 1)
    }
    assert len(balloon_items) == len(drawing.BOM_COMPONENTS)
    assert drawing.SHEET_SCALE == (1.0, 8.0)
    assert drawing.ID_VIEW_SCALE == (1, 10)
    assert drawing.SHEET_NAMES == (
        "GENERAL ARRANGEMENT",
        "INSTALLATION AND ITEM IDENTIFICATION",
    )
    assert source.count("scale=VIEW_SCALE") == 3
    assert source.count("scale=ID_VIEW_SCALE") == 3
    assert source.count("create_blank_drawing_sheets(") == 1
    assert "expected_sheet_names=SHEET_NAMES" in source
    assert source.count("add_note(") == 1
    assert "MHA-A01 THROUGH MHA-A07" in drawing.ASSEMBLY_NOTES
    assert "INSTALL IN ORDER" in drawing.ASSEMBLY_NOTES
    assert "ALIGN ASSEMBLY ORIGINS" in drawing.ASSEMBLY_NOTES
    assert "ADD NO TOP-LEVEL FASTENERS" in drawing.ASSEMBLY_NOTES
    assert "RELEASE HOLD" not in drawing.ASSEMBLY_NOTES
    assert all(
        token not in drawing.ASSEMBLY_NOTES
        for token in ("MATERIAL", "FINISH", "UOS", "DEBUR", "BREAK SHARP")
    )
