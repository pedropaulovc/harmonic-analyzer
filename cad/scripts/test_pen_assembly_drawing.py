"""Offline contracts for the pen ASSEMBLY drawing (the first assembly print)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import draw_pen_assembly as drawing
from _drawing_registry import DRAWINGS, DRAWINGS_BY_NAME

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_dodo():
    spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_registry_row_resolves_the_assembly_source() -> None:
    spec = DRAWINGS_BY_NAME["pen_assembly"]
    assert spec.source_kind == "assembly"
    assert spec.part == "pen"
    assert spec.source.as_posix().endswith("/out/sldasm/pen.SLDASM")
    assert spec.script == Path(drawing.__file__).resolve()


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pen-assembly.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pen-assembly.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pen-assembly_drawing.png")
    assert drawing.SOURCE == DRAWINGS_BY_NAME["pen_assembly"].source


def test_part_rows_keep_their_part_source() -> None:
    """The assembly extension must not disturb the six part-drawing rows."""
    for spec in DRAWINGS:
        if spec.name == "pen_assembly":
            continue
        assert spec.source_kind == "part"
        assert spec.source.as_posix().endswith(f"/out/sldprt/{spec.artifact_stem}.SLDPRT")


def test_dodo_deps_use_the_sldasm_recipe_and_exact_assembly_token() -> None:
    dodo = _load_dodo()
    deps = dodo._drawing_file_deps("pen_assembly")
    assert any(dep.replace("\\", "/").endswith("/out/sldasm/pen.SLDASM") for dep in deps)
    assert dodo._assembly_execution_token("pen") in deps
    assert dodo._part_execution_token("pen") not in deps
    assert any(dep.endswith("harmonic-analyzer.DRWDOT") for dep in deps)
    # Regression: part drawings keep their execution-token identity dep.
    part_deps = dodo._drawing_file_deps("fulcrum_shaft")
    assert any(dep.endswith(".fulcrum-shaft.execution") for dep in part_deps)
    assert any(dep.replace("\\", "/").endswith("/out/sldprt/fulcrum-shaft.SLDPRT")
               for dep in part_deps)


def test_dodo_yields_the_assembly_drawing_task() -> None:
    dodo = _load_dodo()
    assert "pen_assembly" in dodo._drawing_order()
    task = next(
        task for task in dodo.task_drawing() if task["name"] == "pen_assembly"
    )
    targets = {Path(target).name for target in task["targets"]}
    assert targets == {"pen-assembly.SLDDRW", "pen-assembly.pdf", "pen-assembly_drawing.png"}


def test_bom_covers_every_placed_component() -> None:
    """Every part build_pen_assembly places appears exactly once in the BOM list."""
    source = (Path(__file__).parent / "build_pen_assembly.py").read_text(
        encoding="utf-8"
    )
    for component in drawing.BOM_COMPONENTS:
        assert f'"{component}"' in source, f"{component} not placed by the assembly build"
    placed = source.count("place_component(")
    assert placed == len(drawing.BOM_COMPONENTS)


def test_assembly_stamps_title_block_properties() -> None:
    source = (Path(__file__).parent / "build_pen_assembly.py").read_text(
        encoding="utf-8"
    )
    assert "apply_custom_properties" in source
    assert "SEE PARTS LIST" in source
    assert "part_properties(ASM_NAME)" in source  # carries the required TOL_* cells


def test_drawing_places_bom_and_balloons() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("insert_bom_table(") == 1
    assert source.count("add_auto_balloons(") == 1
    assert drawing.SHEET_SCALE == (1.0, 2.0)
    assert source.count("scale=VIEW_SCALE") == 3  # every view pins its scale
