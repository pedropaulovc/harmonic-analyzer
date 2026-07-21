"""Offline contracts for the drive-train ASSEMBLY drawing."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import _config
import draw_drive_train_assembly as drawing
from _drawing_registry import DRAWINGS_BY_NAME

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_dodo():
    spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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


def test_bom_covers_every_top_level_component_family() -> None:
    source = (Path(__file__).parent / "build_drive_train_assembly.py").read_text(
        encoding="utf-8"
    )
    for component in drawing.BOM_COMPONENTS:
        assert f'"{component}"' in source, f"{component} not placed by build"
    assert len(drawing.BOM_COMPONENTS) == 32


def test_grouped_cone_gear_row_has_a_source_description_property() -> None:
    description = _config.parts("cone-gear")["description"]
    assert description == drawing.BOM_COMPONENTS["cone-gear"]
    source = (Path(__file__).parent / "build_cone_gear.py").read_text(
        encoding="utf-8"
    )
    assert 'apply_custom_properties(adapter, {"Description": description})' in source


def test_assembly_owns_see_parts_list_title_block() -> None:
    source = (Path(__file__).parent / "build_drive_train_assembly.py").read_text(
        encoding="utf-8"
    )
    assert '"MHA-A03"' in source
    assert "part_properties(ASM_NAME)" in source
    assert source.count('"Material": "SEE COMPONENT DRAWINGS"') == 1
    assert source.count('"Material Specification": "SEE COMPONENT DRAWINGS"') == 1
    assert source.count('"Finish": "SEE COMPONENT DRAWINGS"') == 1


def test_drawing_places_bom_balloons_and_specific_notes() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("insert_identified_bom_table(") == 1
    assert source.count("add_auto_balloons_across_views(") == 1
    assert 'configuration_grouping="same-part"' in source
    assert "adapter, (front, right, iso, bottom)" in source
    assert source.count("add_note(") == 1
    assert source.count("scale=VIEW_SCALE") == 4
    assert '"*Bottom"' in source
    assert "T006-T120" in drawing.ASSEMBLY_NOTES
    assert "CONE PLATFORM ENGAGED" in drawing.ASSEMBLY_NOTES
    assert all(
        token not in drawing.ASSEMBLY_NOTES
        for token in ("MATERIAL", "FINISH", "UOS", "DEBUR", "BREAK SHARP")
    )
