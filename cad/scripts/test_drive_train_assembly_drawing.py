"""Offline contracts for the drive-train ASSEMBLY drawing."""

from __future__ import annotations

import importlib.util
import inspect
import math
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


def _normalized_table_text(rows: tuple[tuple[str, ...], ...]) -> str:
    return " ".join(" ".join(row) for row in rows).replace("–", "-").replace(
        "°", " DEG"
    )


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


def test_drive_train_has_six_named_and_numbered_sheets() -> None:
    build_source = inspect.getsource(drawing.build)
    assert drawing.SHEET_NAMES == (
        "GENERAL ASSEMBLY",
        "PARTS LIST",
        "EXTERIOR ITEM IDENTIFICATION",
        "CONCEALED ITEM IDENTIFICATION",
        "GEAR-TRAIN SETUP",
        "PINION SETUP AND ACCEPTANCE",
    )
    for index, name in enumerate(drawing.SHEET_NAMES):
        assert f"ActivateSheet(SHEET_NAMES[{index}])" in build_source
        assert f"SHEET {index + 1} OF 6 — {name}" in build_source
    assert "expected_sheet_names=SHEET_NAMES" in build_source
    assert "SEE SHEET 5" in drawing.GENERAL_POINTER_NOTE
    assert "SEE SHEET 6" in drawing.GENERAL_POINTER_NOTE


def test_sheet_three_identifies_four_disjoint_subsystems_deliberately() -> None:
    expected = (
        frozenset(
            {
                "cone-swing-platform",
                "cone-pivot-post",
                "cone-tip-block",
                "cone-tip-adjuster",
                "cone-tip-pinch-screw",
                "cone-lock-knob",
                "cone-pivot-screw",
                "swing-stop-screw",
                "cone-gear",
            }
        ),
        frozenset(
            {
                "alignment-pinion",
                "pinion-bracket",
                "pinion-pivot-block",
                "pinion-pivot-shaft",
                "pinion-lift-rod",
                "pinion-spring",
            }
        ),
        frozenset(
            {
                "pinion-cam-pin",
                "pinion-cam",
                "pinion-lever",
                "pinion-handle",
                "pinion-arbor",
                "slotted-screw",
                "foot-screw",
            }
        ),
        frozenset(
            {
                "cylinder-gear-shaft",
                "arbor-pedestal",
                "cylinder-gear",
                "crankshaft",
                "crank-pinion",
                "crank-arm",
                "crank-handle",
            }
        ),
    )
    assert drawing.EXTERIOR_VIEW_STEMS == expected
    assert drawing.EXTERIOR_VIEW_LABELS == (
        "VIEW A — CONE PLATFORM / GEAR TRAIN",
        "VIEW B — PINION SUPPORT / STRAPS",
        "VIEW C — PINION CAM / CONTROLS",
        "VIEW D — CYLINDER / CRANK",
    )
    groups = expected
    assert not any(
        left & right
        for i, left in enumerate(groups)
        for right in groups[i + 1 :]
    )
    assert set().union(*groups) == set(drawing.BOM_COMPONENTS) - set(
        drawing.CONCEALED_BALLOON_ITEMS
    )

    source = Path(drawing.__file__).read_text(encoding="utf-8")
    build_source = inspect.getsource(drawing.build)
    assert "_create_auto_balloons(" not in build_source
    assert "_add_component_balloons(" in build_source
    assert "_create_component_balloon(" in source
    assert "_spread_balloons(" in source
    assert "EXTERIOR_VIEW_STEMS" in build_source
    assert "_isolate_balloon_components(" in build_source
    assert "position_bom_balloon(" not in source


def test_sheet_five_has_an_explicit_twenty_pair_station_contract() -> None:
    assert len(drawing.GEAR_PAIR_ROWS) == 20
    assert len({row[0] for row in drawing.GEAR_PAIR_ROWS}) == 20
    assert len({row[1] for row in drawing.GEAR_PAIR_ROWS}) == 20
    for index, row in enumerate(drawing.GEAR_PAIR_ROWS):
        pair, config, reference, ratio, cone_center, cylinder_center = row
        teeth = 120 - 6 * index
        assert pair == f"{index + 1:02d}"
        assert config == f"T{120 - 6 * index:03d}"
        assert reference == "T120"
        assert ratio == f"{teeth}:120"
        assert math.isclose(
            float(cone_center), 40.55 + 6.888787817 * index, abs_tol=5e-4
        )
        assert math.isclose(
            float(cylinder_center), 22.90 + 7.056542133 * index, abs_tol=5e-4
        )

    requirements = _normalized_table_text(drawing.GEAR_REQUIREMENT_ROWS)
    assert "ITEM 27" in requirements
    assert "ITEM 25" in requirements
    assert "SOLDER" in requirements
    assert "NO KEY" in requirements
    assert "ITEM 28" in requirements
    assert "FREE ON ITEM 1" in requirements
    assert "ITEM 1" in requirements
    assert "0.05-0.20 MM" in requirements
    assert "BACKLASH" in requirements

    build_source = inspect.getsource(drawing.build)
    assert "_insert_cone_gear_schedule(" in build_source
    assert "_insert_gear_requirements_table(" in build_source


def test_sheet_six_uses_state_and_acceptance_tables_with_a_parked_view() -> None:
    parameters = drawing.PINION_PARAMETER_ROWS
    acceptance = drawing.ACCEPTANCE_ROWS
    assert len(parameters) == 8
    assert len(acceptance) == 4
    assert all(len(row) == 4 for row in parameters)
    assert all(len(row) == 2 for row in acceptance)
    parameter_text = _normalized_table_text(parameters)
    acceptance_text = _normalized_table_text(acceptance)
    for required in (
        "2.00 MM",
        "41.30 MM",
        "12.38 DEG",
        "0.25 MM",
        "7.00 MM",
        "0.10-0.25 MM",
        "40 DEG",
    ):
        assert required in parameter_text
    for required in (
        "ITEM 29",
        "ITEM 21",
        "ITEM 17",
        "ITEM 3",
    ):
        assert required in acceptance_text
    assert "NO AXIAL PLAY" not in acceptance_text

    build_source = inspect.getsource(drawing.build)
    assert "_insert_pinion_parameter_table(" in build_source
    assert "_insert_acceptance_table(" in build_source
    assert "PARK / DISENGAGED — SHOWN POSITION" in build_source


def test_setup_views_do_not_hide_an_unlabelled_scale_exception() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "SETUP_IDENTIFICATION_VIEW_SCALE" not in source
    assert "(1, 8)" not in source


def test_assembly_notes_preserve_the_source_backed_manufacturing_contract() -> None:
    assert isinstance(drawing.ASSEMBLY_NOTES, str)
    assembly_notes = drawing.ASSEMBLY_NOTES
    normalized_notes = " ".join(assembly_notes.split())
    assert assembly_notes.splitlines()[0] == "ASSEMBLY NOTES"
    for required in (
        "MACHINE FRONT = PAPER/OUTPUT SIDE (-Z)",
        "EAST = VIEWER RIGHT (-X)",
        '"T120 END" = ITEM 4 / ITEM 27 T120 END',
        '"T006 END" = ITEM 5 / ITEM 27 T006 END',
        "40.55 + j(6.889) MM",
        "22.90 + j(7.0565) MM",
        "2.00 MM CLEARANCE",
        "41.30 MM C-C",
        "12.38 DEG",
        "0.25 MM AXIAL CLEARANCE",
        "7.00 MM",
        "0.10-0.25 MM MINIMUM SURFACE",
        "40 DEG",
        "MACHINE-BACK ITEM 13",
        "FINAL FUNCTIONAL ACCEPTANCE",
    ):
        assert required in assembly_notes
    assert (
        "SET 0.05-0.20 MM TANGENTIAL BACKLASH AT EACH ITEM 27/28 "
        "PITCH-CIRCLE MESH"
    ) in normalized_notes
    assert "CAM SHAFT ONE FULL TURN" not in assembly_notes
    assert "0.05-0.10" not in assembly_notes

    rendered_text = " ".join(
        (
            assembly_notes,
            *(" ".join(row) for row in drawing.GEAR_REQUIREMENT_ROWS),
            *(" ".join(row) for row in drawing.PINION_PARAMETER_ROWS),
            *(" ".join(row) for row in drawing.ACCEPTANCE_ROWS),
        )
    ).upper()
    assert all(
        token not in rendered_text
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
