"""Offline contracts for the drive-train ASSEMBLY drawing."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import _config
import draw_drive_train_assembly as drawing
from _drawing_registry import DRAWINGS_BY_NAME

REPO_ROOT = Path(__file__).resolve().parents[2]


class _CallableChildren:
    def GetChildren(self):
        return ("a", "b")


class _MaterializedChildren:
    GetChildren = ("a", "b")


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
    assert source.count("_add_drive_train_balloons(") == 2
    assert 'configuration_grouping="same-part"' in source
    assert "expected_sheet_names=SHEET_NAMES" in source
    assert source.count("add_note(") == 5
    assert source.count("scale=VIEW_SCALE") == 8
    assert source.count("scale=VIEW_SCALE,") == 1
    assert '"*Bottom"' in source
    assert "_isolate_bottom_balloon_components(adapter, concealed_bottom)" in source
    assert "drawing_component.Visible = bool(matched)" in source
    assert drawing.SHEET_NAMES == (
        "GENERAL ASSEMBLY",
        "PARTS LIST",
        "EXTERIOR ITEM IDENTIFICATION",
        "CONCEALED ITEM IDENTIFICATION",
    )
    assert drawing.BOTTOM_VISIBILITY_STEMS == {
        "cone-tip-bushing",
        "cone-gear-shaft",
        "crank-drive-gear",
    }
    assert drawing.CONCEALED_BALLOON_ITEMS == {
        "cone-tip-bushing": "6",
        "cone-gear-shaft": "25",
        "crank-drive-gear": "26",
    }
    assert drawing.MANUAL_EXTERIOR_BALLOON_ITEMS == {
        "cone-tip-adjuster": "7",
        "cone-tip-pinch-screw": "8",
        "swing-stop-screw": "11",
        "alignment-pinion": "12",
        "crank-pinion": "30",
    }
    assert drawing.MANUAL_EXTERIOR_VIEW_ORDER == {
        "cone-tip-adjuster": (2, 1, 0),
        "cone-tip-pinch-screw": (0, 2, 1),
        "swing-stop-screw": (1, 2, 0),
        "alignment-pinion": (2, 1, 0),
        "crank-pinion": (1, 2, 0),
    }
    assert drawing.FRONT_DEFERRED_BALLOON_STEMS == {
        "swing-stop-screw",
        "pinion-pivot-shaft",
        "pinion-lever",
        "foot-screw",
        "crankshaft",
        "crank-pinion",
    }
    assert drawing.FRONT_DEFERRED_BALLOON_ITEMS == {
        "11",
        "15",
        "20",
        "24",
        "29",
        "30",
    }
    assert "_defer_front_balloons(adapter, balloons)" in source
    assert '"IModelDocExtension", "DeleteSelection2"' in source
    assert "RootDrawingComponent2(False)" in source
    assert "GetVisibleEntities2(c, 1)" in source
    assert "selected_view.SelectEntity(selected_edge, False)" in source
    assert '"IModelDocExtension",\n        "CreateBalloonOptions",\n        "InsertBOMBalloon2"' in source
    assert 'drawing_name.rsplit("/", 1)[-1].casefold()' in source
    assert 'identity.startswith(f"{stem}-")' in source
    assert "enumerated drawing components" in source
    assert "HorizontalAutoSplit(" not in source
    assert sum(drawing.BOM_COLUMN_WIDTHS.values()) == 0.125
    assert drawing.EXTERIOR_BALLOON_RING_MARGINS == (0.014, 0.014, 0.014)
    assert drawing.CONCEALED_BALLOON_RING_MARGIN == 0.035
    assert drawing.CONCEALED_BALLOON_CLEARANCE == 0.006
    assert "_swap_drive_train_balloon_slots" not in source
    assert "T006-T120" in drawing.ASSEMBLY_NOTES
    assert "CONE PLATFORM ENGAGED" in drawing.ASSEMBLY_NOTES
    assert "0.05-0.10 MM" in drawing.ASSEMBLY_NOTES
    assert "2.00 MM TIP GAP" in drawing.ASSEMBLY_NOTES
    assert "0.10-0.25 MM" in drawing.ASSEMBLY_NOTES
    assert "BACK STRAP ONLY" in drawing.ASSEMBLY_NOTES
    assert "FRONT REMAINS SPRING-FREE" in drawing.ASSEMBLY_NOTES
    assert all(
        token not in drawing.ASSEMBLY_NOTES
        for token in ("MATERIAL", "FINISH", "UOS", "DEBUR", "BREAK SHARP")
    )


def test_drawing_component_children_accepts_both_pywin32_shapes() -> None:
    assert drawing._drawing_component_children(_CallableChildren()) == ("a", "b")
    assert drawing._drawing_component_children(_MaterializedChildren()) == ("a", "b")


def test_live_hierarchical_drawing_names_are_matched_by_leaf() -> None:
    name = "drive-train-4/cone-gear-shaft-1"
    drawing_name = name.split("@", 1)[0].replace("\\", "/")
    identity = drawing_name.rsplit("/", 1)[-1].casefold()
    stem = "cone-gear-shaft"
    assert identity.startswith(f"{stem}-")
    assert identity.removeprefix(f"{stem}-").isdigit()
