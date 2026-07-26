"""Offline contracts for the summing ASSEMBLY drawing."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

import build_summing_assembly as assembly
import draw_summing_assembly as drawing
import top_crossbar_spec
from _assembly import _seed_flip
from _drawing_registry import DRAWINGS, DRAWINGS_BY_NAME
from cone_pivot_post_installation import MECHANISM_Z_SHIFT, SUMMING_Z

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


def test_summing_chain_shares_the_v2_world_anchor() -> None:
    """The lever/knife/counter family follows the recentered mechanism."""
    assert SUMMING_Z == MECHANISM_Z_SHIFT
    assert assembly.BOSS_HOOK_POS[2] == SUMMING_Z
    assert assembly.SPRING_POS[2] == SUMMING_Z

    source = Path(assembly.__file__).read_text(encoding="utf-8")
    assert "SUMMING_Z + HEX_Z_MID" in source
    assert "SUMMING_Z - HEX_Z_MID" in source
    assert '[KNIFE[0], KNIFE[1], SUMMING_Z]' in source
    assert 'list(BOSS_HOOK_POS)' in source
    assert 'list(SPRING_POS)' in source
    assert '[COLUMN_X, 1210.0, SUMMING_Z]' in source
    assert '[COLUMN_X, 1040.7, SUMMING_Z]' in source


def test_positive_summing_station_uses_the_relearned_axial_mate_side() -> None:
    assert _seed_flip("summing-lever axial", SUMMING_Z)


def test_crossbar_body_and_stud_use_distinct_world_anchors() -> None:
    """The asymmetric bar centre must not drag the summing stud off-axis."""
    assert top_crossbar_spec.BAR_CENTER_Z == pytest.approx(0.0)
    assert top_crossbar_spec.STUD_HOLE_Z == pytest.approx(SUMMING_Z)
    assert top_crossbar_spec.BAR_CENTER_Z + top_crossbar_spec.STUD_HOLE_Z == pytest.approx(SUMMING_Z)

    source = Path(assembly.__file__).read_text(encoding="utf-8")
    assert '[KNIFE[0], 1010.0, BAR_CENTER_Z]' in source


def test_assembly_stamps_title_block_properties() -> None:
    source = (Path(__file__).parent / "build_summing_assembly.py").read_text(
        encoding="utf-8"
    )
    assert "apply_custom_properties" in source
    assert "SEE COMPONENT DRAWINGS" in source
    assert "assembly_title_properties(ASM_NAME)" in source
    assert "part_properties(ASM_NAME)" not in source
    assert '"MHA-A07"' in source
    assert source.count('"Material": "SEE COMPONENT DRAWINGS"') == 1
    assert source.count('"Material Specification": "SEE COMPONENT DRAWINGS"') == 1
    assert source.count('"Finish": "SEE COMPONENT DRAWINGS"') == 1


def test_drawing_places_bom_and_balloons() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("insert_identified_bom_table(") == 1
    assert source.count("add_auto_balloons(") == 1
    assert drawing.SHEET_SCALE == (1.0, 5.0)
    assert source.count("scale=VIEW_SCALE") == 3  # every view pins its scale
    assert source.count("add_note(") == 1
    assert "KNIFE-MOUNT EDGES" not in drawing.ASSEMBLY_NOTES
    assert "HARDENED KNIFE SEATS" in drawing.ASSEMBLY_NOTES
    assert all(
        token not in drawing.ASSEMBLY_NOTES
        for token in ("MATERIAL", "FINISH", "UOS", "DEBUR", "BREAK SHARP")
    )
