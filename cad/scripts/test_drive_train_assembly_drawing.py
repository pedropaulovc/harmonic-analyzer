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
    assembly_notes = drawing.ASSEMBLY_NOTES
    normalized_notes = " ".join(assembly_notes.split())
    assert source.count("insert_identified_bom_table(") == 1
    assert source.count("_add_drive_train_balloons(") == 2
    assert 'configuration_grouping="same-part"' in source
    assert "_insert_cone_gear_schedule(adapter, bom_table, bom_iso)" in source
    assert '"GetComponents2"' in source
    assert '"InsertTableAnnotation2"' in source
    assert "expected_sheet_names=SHEET_NAMES" in source
    assert source.count("add_note(") == 7
    assert source.count("scale=VIEW_SCALE") == 9
    assert source.count("scale=VIEW_SCALE,") == 2
    assert '"*Bottom"' in source
    assert '"*Front"' in source
    assert source.count("_isolate_balloon_components(") == 3
    assert "drawing_component.Visible = bool(matched)" in source
    assert drawing.SHEET_NAMES == (
        "GENERAL ASSEMBLY",
        "PARTS LIST",
        "EXTERIOR ITEM IDENTIFICATION",
        "CONCEALED ITEM IDENTIFICATION",
        "SETUP AND ACCEPTANCE",
    )
    assert source.count(" OF 5") == 5
    assert " OF 4" not in source
    assert "ActivateSheet(SHEET_NAMES[4])" in source
    assert drawing.BOTTOM_VISIBILITY_STEMS == {
        "cone-tip-bushing",
        "cone-gear-shaft",
        "crank-drive-gear",
    }
    assert drawing.CONCEALED_BOTTOM_STEMS == {
        "cone-tip-bushing",
        "cone-gear-shaft",
    }
    assert drawing.CONCEALED_FRONT_STEMS == {"crank-drive-gear"}
    assert (
        drawing.CONCEALED_BOTTOM_STEMS | drawing.CONCEALED_FRONT_STEMS
        == drawing.BOTTOM_VISIBILITY_STEMS
    )
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
    assert drawing.BOM_COMPONENTS["cone-pivot-post"] == "T120 JOURNAL POST"
    assert drawing.BOM_COMPONENTS["cone-tip-block"] == "T006 JOURNAL BLOCK"
    assert len(drawing.CONE_GEAR_SCHEDULE) == 20
    assert drawing.CONE_GEAR_SCHEDULE[0] == (1, "T120", 120)
    assert drawing.CONE_GEAR_SCHEDULE[-1] == (20, "T006", 6)
    assert [row[2] for row in drawing.CONE_GEAR_SCHEDULE] == list(
        range(120, 0, -6)
    )
    assert len({row[1] for row in drawing.CONE_GEAR_SCHEDULE}) == 20
    assert drawing.CONE_SCHEDULE_ANCHOR == (0.155, 0.170)
    assert sum(drawing.CONE_SCHEDULE_COLUMN_WIDTHS) == 0.098
    assert drawing.CONE_SCHEDULE_TEXT_HEIGHT == 0.0025
    assert drawing.CONE_SCHEDULE_ROW_HEIGHT == 0.006
    assert drawing.EXTERIOR_BALLOON_RING_MARGINS == (0.014, 0.014, 0.014)
    assert drawing.PINION_PIVOT_SHAFT_BALLOON_POSITION == (0.199, 0.120)
    assert 'item_number="15"' in source
    assert 'label="drive-train item 15 leader routing"' in source
    assert "position_tolerance_m=0.0015" in source
    assert drawing.CONCEALED_BOTTOM_BALLOON_RING_MARGIN == 0.015
    assert drawing.CONCEALED_FRONT_BALLOON_RING_MARGIN == 0.025
    assert drawing.CONCEALED_BALLOON_CLEARANCE == 0.006
    assert drawing.CONCEALED_HEADING_ORIGIN == (0.060, 0.255)
    assert drawing.SETUP_HEADING_ORIGIN == (0.060, 0.255)
    assert drawing.SETUP_NOTE_ORIGINS == (
        (0.018, 0.070),
        (0.158, 0.070),
        (0.300, 0.095),
    )
    assert len(drawing.SETUP_NOTE_COLUMNS) == 3
    assert "_swap_drive_train_balloon_slots" not in source
    assert drawing.GENERAL_POINTER_NOTE == (
        "SETUP, ORIENTATION, BACKLASH, AND FINAL ACCEPTANCE: SEE SHEET 5."
    )
    assert "MACHINE FRONT = PAPER/OUTPUT SIDE (-Z)" in assembly_notes
    assert "EAST = VIEWER RIGHT (-X)" in assembly_notes
    assert '"T120 END" = ITEM 4 / ITEM 27 T120 END' in assembly_notes
    assert '"T006 END" = ITEM 5 / ITEM 27 T006 END' in assembly_notes
    assert "40.55 + j(6.889) MM" in assembly_notes
    assert "22.90 + j(7.0566) MM" in assembly_notes
    assert "2.00 MM CLEARANCE" in assembly_notes
    assert "41.30 MM C-C" in assembly_notes
    assert "12.38 DEG" in assembly_notes
    assert "0.25 MM AXIAL CLEARANCE" in assembly_notes
    assert "7.00 MM" in assembly_notes
    assert "0.10-0.25 MM MINIMUM SURFACE" in assembly_notes
    assert "40 DEG" in assembly_notes
    assert "MACHINE-BACK ITEM 13" in assembly_notes
    assert (
        "SET 0.05-0.20 MM TANGENTIAL BACKLASH AT EACH ITEM 27/28 "
        "PITCH-CIRCLE MESH"
    ) in normalized_notes
    assert "FINAL FUNCTIONAL ACCEPTANCE" in assembly_notes
    assert "ITEM 29 ONE REVOLUTION" in assembly_notes
    assert "ITEM 21 ONE" in assembly_notes
    assert "ITEM 17 SHALL RETURN ITEM 12 TO 2.00 MM GAP" in assembly_notes
    assert "ITEM 3 SHALL SWING FREELY TO CONTACT" in assembly_notes
    assert "RECHECK ITEM 25 FOR FREE" in assembly_notes
    assert "CAM SHAFT ONE FULL TURN" not in assembly_notes
    assert "0.05-0.10" not in assembly_notes
    assert all(
        token not in assembly_notes
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
