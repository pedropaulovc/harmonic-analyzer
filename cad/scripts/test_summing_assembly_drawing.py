"""Offline contracts for the summing ASSEMBLY drawing."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import draw_summing_assembly as drawing
from _drawing_registry import DRAWINGS, DRAWINGS_BY_NAME

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_dodo():
    spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_registry_row_resolves_the_assembly_source() -> None:
    spec = DRAWINGS_BY_NAME["summing_assembly"]
    assert spec.source_kind == "assembly"
    assert spec.part == "summing"
    assert spec.source.as_posix().endswith("/out/sldasm/summing.SLDASM")
    assert spec.script == Path(drawing.__file__).resolve()


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/summing-assembly.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/summing-assembly.pdf")
    assert drawing.PNG.as_posix().endswith("/png/summing-assembly_drawing.png")
    assert drawing.SOURCE == DRAWINGS_BY_NAME["summing_assembly"].source


def test_part_rows_keep_their_part_source() -> None:
    """The assembly rows must not disturb the part-drawing rows."""
    for spec in DRAWINGS:
        if spec.source_kind == "assembly":
            continue
        assert spec.source.as_posix().endswith(
            f"/out/sldprt/{spec.artifact_stem}.SLDPRT"
        )


def test_dodo_deps_use_the_sldasm_recipe_and_exact_assembly_token() -> None:
    dodo = _load_dodo()
    deps = dodo._drawing_file_deps("summing_assembly")
    assert any(
        dep.replace("\\", "/").endswith("/out/sldasm/summing.SLDASM") for dep in deps
    )
    assert dodo._assembly_execution_token("summing") in deps
    assert dodo._part_execution_token("summing") not in deps
    assert any(dep.endswith("harmonic-analyzer.DRWDOT") for dep in deps)


def test_dodo_yields_the_assembly_drawing_task() -> None:
    dodo = _load_dodo()
    assert "summing_assembly" in dodo._drawing_order()
    task = next(
        task for task in dodo.task_drawing() if task["name"] == "summing_assembly"
    )
    targets = {Path(target).name for target in task["targets"]}
    assert targets == {
        "summing-assembly.SLDDRW",
        "summing-assembly.pdf",
        "summing-assembly_drawing.png",
    }


def test_bom_covers_every_placed_component() -> None:
    """Every UNIQUE placed component appears once in the BOM list.

    knife-mount is placed twice (front + back bearing support); the standard
    BOM collapses it to one QTY-2 row, so the UNIQUE placed set -- not the raw
    call count -- must match the BOM keys.
    """
    source = (Path(__file__).parent / "build_summing_assembly.py").read_text(
        encoding="utf-8"
    )
    for component in drawing.BOM_COMPONENTS:
        assert f'"{component}"' in source, f"{component} not placed by the build"
    placed = re.findall(r'place_component\(\s*adapter,\s*"([a-z0-9-]+)"', source)
    assert set(placed) == set(drawing.BOM_COMPONENTS)
    assert len(placed) == 8  # knife-mount placed twice (front + back support)


def test_assembly_stamps_title_block_properties() -> None:
    source = (Path(__file__).parent / "build_summing_assembly.py").read_text(
        encoding="utf-8"
    )
    assert "apply_custom_properties" in source
    assert "SEE PARTS LIST" in source
    assert "part_properties(ASM_NAME)" in source  # carries the required TOL_* cells
    assert '"MHA-A07"' in source


def test_drawing_places_bom_and_balloons() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("insert_bom_table(") == 1
    assert source.count("add_auto_balloons(") == 1
    assert drawing.SHEET_SCALE == (1.0, 5.0)
    assert source.count("scale=VIEW_SCALE") == 3  # every view pins its scale
