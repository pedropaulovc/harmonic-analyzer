"""Offline contracts for the frame ASSEMBLY drawing."""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import build_frame_assembly as frame
import draw_frame_assembly as drawing
from cone_pivot_post_installation import (
    FRAME_FRONT_COLUMN_Z,
    FRAME_REAR_COLUMN_Z,
    ROCKER_SUPPORT_Z,
)
from _drawing_registry import DRAWINGS, DRAWINGS_BY_NAME

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_dodo():
    spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_registry_row_resolves_the_assembly_source() -> None:
    spec = DRAWINGS_BY_NAME["frame_assembly"]
    assert spec.source_kind == "assembly"
    assert spec.part == "frame"
    assert spec.source.as_posix().endswith("/out/sldasm/frame.SLDASM")
    assert spec.script == Path(drawing.__file__).resolve()


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/frame-assembly.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/frame-assembly.pdf")
    assert drawing.PNG.as_posix().endswith("/png/frame-assembly_drawing.png")
    assert drawing.SOURCE == DRAWINGS_BY_NAME["frame_assembly"].source


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
    deps = dodo._drawing_file_deps("frame_assembly")
    assert any(
        dep.replace("\\", "/").endswith("/out/sldasm/frame.SLDASM") for dep in deps
    )
    assert dodo._assembly_execution_token("frame") in deps
    assert dodo._part_execution_token("frame") not in deps
    assert any(dep.endswith("harmonic-analyzer.DRWDOT") for dep in deps)


def test_dodo_yields_the_assembly_drawing_task() -> None:
    dodo = _load_dodo()
    assert "frame_assembly" in dodo._drawing_order()
    task = next(
        task for task in dodo.task_drawing() if task["name"] == "frame_assembly"
    )
    targets = {Path(target).name for target in task["targets"]}
    assert targets == {
        "frame-assembly.SLDDRW",
        "frame-assembly.pdf",
        "frame-assembly_drawing.png",
    }


def test_bom_covers_every_placed_component() -> None:
    """Every BOM row corresponds to a component the frame build places.

    The frame mixes ``insert_component`` (base, seed column, top-frame),
    ``place_component`` (support, seed lag-screw, nameplate) and
    ``grid_component_pattern`` (columns x4, lag-screws x4), so the check is a
    string presence test, not a ``place_component`` count -- the runtime
    ``insert_bom_table`` validates one BOM row per expected component.
    """
    source = (Path(__file__).parent / "build_frame_assembly.py").read_text(
        encoding="utf-8"
    )
    for component in drawing.BOM_COMPONENTS:
        assert f'"{component}"' in source, f"{component} not placed by the build"


def test_assembly_stamps_title_block_properties() -> None:
    source = (Path(__file__).parent / "build_frame_assembly.py").read_text(
        encoding="utf-8"
    )
    assert "apply_custom_properties" in source
    assert "SEE COMPONENT DRAWINGS" in source
    assert "assembly_title_properties(ASM_NAME)" in source
    assert "part_properties(ASM_NAME)" not in source
    assert '"MHA-A04"' in source
    assert source.count('"Material": "SEE COMPONENT DRAWINGS"') == 1
    assert source.count('"Material Specification": "SEE COMPONENT DRAWINGS"') == 1
    assert source.count('"Finish": "SEE COMPONENT DRAWINGS"') == 1


def test_drawing_places_bom_and_balloons() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("insert_identified_bom_table(") == 1
    assert source.count("add_auto_balloons(") == 1
    assert drawing.SHEET_SCALE == (1.0, 6.0)
    assert drawing.SHEET_NAMES == (
        "GENERAL ASSEMBLY",
        "PARTS LIST AND ITEM IDENTIFICATION",
    )
    assert source.count("scale=VIEW_SCALE") == 3  # every view pins its scale
    assert source.count("add_note(") == 3
    assert "create_blank_drawing_sheets" in source
    assert "expected_sheet_names=SHEET_NAMES" in source
    assert "BASE UNDERSIDE" in drawing.ASSEMBLY_NOTES
    assert all(
        token not in drawing.ASSEMBLY_NOTES
        for token in ("MATERIAL", "FINISH", "UOS", "DEBUR", "BREAK SHARP")
    )


def test_frame_uses_the_asymmetric_rear_reanchor_contract() -> None:
    assert frame.FRONT_COLUMN_Z == FRAME_FRONT_COLUMN_Z
    assert frame.REAR_COLUMN_Z == FRAME_REAR_COLUMN_Z
    assert frame.SUPPORT_Z == ROCKER_SUPPORT_Z
    assert math.isclose(frame.REAR_COLUMN_Z - frame.FRONT_COLUMN_Z, 259.415)
    assert {z for _, z in frame.LAG_SCREW_XZ} == {
        ROCKER_SUPPORT_Z - 60.32,
        ROCKER_SUPPORT_Z + 60.32,
    }
