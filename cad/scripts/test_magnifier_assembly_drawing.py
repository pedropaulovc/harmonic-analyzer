"""Offline contracts for the magnifier ASSEMBLY drawing."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import draw_magnifier_assembly as drawing
from _drawing_registry import DRAWINGS, DRAWINGS_BY_NAME

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_dodo():
    spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_registry_row_resolves_the_assembly_source() -> None:
    spec = DRAWINGS_BY_NAME["magnifier_assembly"]
    assert spec.source_kind == "assembly"
    assert spec.part == "magnifier"
    assert spec.source.as_posix().endswith("/out/sldasm/magnifier.SLDASM")
    assert spec.script == Path(drawing.__file__).resolve()


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/magnifier-assembly.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/magnifier-assembly.pdf")
    assert drawing.PNG.as_posix().endswith("/png/magnifier-assembly_drawing.png")
    assert drawing.SOURCE == DRAWINGS_BY_NAME["magnifier_assembly"].source


def test_part_rows_keep_their_part_source() -> None:
    for spec in DRAWINGS:
        if spec.source_kind == "assembly":
            continue
        assert spec.source.as_posix().endswith(
            f"/out/sldprt/{spec.artifact_stem}.SLDPRT"
        )


def test_dodo_deps_use_the_sldasm_recipe_and_exact_assembly_token() -> None:
    dodo = _load_dodo()
    deps = dodo._drawing_file_deps("magnifier_assembly")
    assert any(
        dep.replace("\\", "/").endswith("/out/sldasm/magnifier.SLDASM") for dep in deps
    )
    assert dodo._assembly_execution_token("magnifier") in deps
    assert dodo._part_execution_token("magnifier") not in deps
    assert any(dep.endswith("harmonic-analyzer-assembly.DRWDOT") for dep in deps)


def test_dodo_yields_the_assembly_drawing_task() -> None:
    dodo = _load_dodo()
    assert "magnifier_assembly" in dodo._drawing_order()
    task = next(
        task for task in dodo.task_drawing() if task["name"] == "magnifier_assembly"
    )
    targets = {Path(target).name for target in task["targets"]}
    assert targets == {
        "magnifier-assembly.SLDDRW",
        "magnifier-assembly.pdf",
        "magnifier-assembly_drawing.png",
    }


def test_bom_covers_every_placed_component() -> None:
    """Every BOM row corresponds to a component the magnifier build places.

    The magnifier mixes single ``place_component`` calls, a two-arc placement
    loop and a native clamp-screw pattern, so the check is a string presence
    test -- the runtime ``insert_bom_table`` validates one BOM row per expected
    component.
    """
    source = (Path(__file__).parent / "build_magnifier_assembly.py").read_text(
        encoding="utf-8"
    )
    for component in drawing.BOM_COMPONENTS:
        assert f'"{component}"' in source, f"{component} not placed by the build"


def test_assembly_stamps_title_block_properties() -> None:
    source = (Path(__file__).parent / "build_magnifier_assembly.py").read_text(
        encoding="utf-8"
    )
    assert "apply_custom_properties" in source
    assert "SEE COMPONENT DRAWINGS" in source
    assert "assembly_title_properties(ASM_NAME)" in source
    assert "part_properties(ASM_NAME)" not in source
    assert '"MHA-A05"' in source
    assert source.count('"Material": "SEE COMPONENT DRAWINGS"') == 1
    assert source.count('"Material Specification": "SEE COMPONENT DRAWINGS"') == 1
    assert source.count('"Finish": "SEE COMPONENT DRAWINGS"') == 1


def test_drawing_places_bom_and_balloons() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("insert_identified_bom_table(") == 1
    assert source.count("add_auto_balloons_across_views(") == 1
    assert "adapter, (iso, front)" in source
    assert drawing.SHEET_SCALE == (1.0, 4.0)
    assert drawing.SHEET_NAMES == (
        "GENERAL ASSEMBLY",
        "PARTS LIST AND ITEM IDENTIFICATION",
    )
    assert source.count("scale=VIEW_SCALE") == 5
    assert source.count("add_note(") == 3
    assert "create_blank_drawing_sheets" in source
    assert "expected_sheet_names=SHEET_NAMES" in source
    assert "LEVER-WIRE TERMINATIONS" in drawing.ASSEMBLY_NOTES
    assert "WHEEL HUB/RIM" in drawing.ASSEMBLY_NOTES
    assert all(
        token not in drawing.ASSEMBLY_NOTES
        for token in ("MATERIAL", "FINISH", "UOS", "DEBUR", "BREAK SHARP")
    )
