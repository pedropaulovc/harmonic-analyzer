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


def test_end_for_end_cylinder_copy_preserves_the_seed_relative_axial_side() -> None:
    source = (Path(__file__).parent / "build_drive_train_assembly.py").read_text(
        encoding="utf-8"
    )
    assert "flips[cylinder_dim_slot] = True" not in source
    assert "flips = [False, False]" in source
    assert "flip_alignments[cylinder_dim_slot] = True" in source
    assert "flip_alignments=flip_alignments" in source
    assert "SolidWorks hard errors" in source
    assert "whats_wrong(" in source
    assert "component_mate_dump(adapter, new_name)" in source


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
    assert "assembly_title_properties(ASM_NAME)" in source
    assert "part_properties(ASM_NAME)" not in source
    assert source.count('"Material": "SEE COMPONENT DRAWINGS"') == 1
    assert source.count('"Material Specification": "SEE COMPONENT DRAWINGS"') == 1
    assert source.count('"Finish": "SEE COMPONENT DRAWINGS"') == 1


def test_drive_train_has_seven_named_and_numbered_sheets() -> None:
    build_source = inspect.getsource(drawing.build)
    assert drawing.SHEET_NAMES == (
        "GENERAL ASSEMBLY",
        "PARTS LIST",
        "GEAR-TRAIN ITEM IDENTIFICATION",
        "CONCEALED ITEM IDENTIFICATION",
        "GEAR-TRAIN SETUP",
        "PINION ITEM IDENTIFICATION",
        "PINION SETUP AND ACCEPTANCE",
    )
    for index, name in enumerate(drawing.SHEET_NAMES):
        assert f"ActivateSheet(SHEET_NAMES[{index}])" in build_source
        assert f"SHEET {index + 1} OF 7 — {name}" in build_source
    assert "expected_sheet_names=SHEET_NAMES" in build_source
    assert "SEE SHEET 5" in drawing.GENERAL_POINTER_NOTE
    assert "SEE SHEET 6" in drawing.GENERAL_POINTER_NOTE


def test_sheet_two_parts_list_fits_the_drawing_zone() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert drawing.BOM_ANCHOR == (0.018, 0.266)
    assert drawing.BOM_ROW_HEIGHT == 0.0075
    assert drawing.BOM_MAX_ROW_HEIGHT == 0.0103
    assert "table.SetRowHeight(row, BOM_ROW_HEIGHT, 0)" in source


def test_identification_sheets_balloon_by_autoballoon_and_prove_full_coverage() -> None:
    """The three identification sheets use the stock AutoBalloon path.

    Balloons used to be placed one component at a time: walk the view's
    drawing-component tree, hide everything that is not the target, find a
    visible edge, InsertBOMBalloon2, rebuild. That cost ~200 s of the drawing's
    277 s and it is exactly the kind of runtime placement tweaking the project
    no longer does. AutoBalloon5 balloons a whole view in one call, so coverage
    is accumulated across the sheets instead and proved once at the end.
    """
    build_source = inspect.getsource(drawing.build)
    assert build_source.count("add_auto_balloons_across_views(") == 3

    # Sheets 3 and 4 accumulate; sheet 6 -- the last one -- asserts. Getting
    # this backwards would silently stop proving that every BOM item is
    # identified somewhere, which is the whole point of the package.
    assert build_source.count('coverage="accumulate"') == 2
    assert build_source.count("existing_balloons=identification_balloons") == 2
    tail = build_source.split("SHEET_NAMES[5]", 1)[1]
    assert "add_auto_balloons_across_views(" in tail
    assert 'coverage="accumulate"' not in tail
    assert "expected=len(BOM_COMPONENTS)" in tail

    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # No runtime component-visibility toggling anywhere: a view shows what it
    # shows, decided at code-write time.
    for gone in (
        "_isolate_balloon_components",
        "_create_component_balloon",
        "_add_component_balloons",
        "_drawing_component_matches",
        "_drawing_component_children",
        ".Visible = ",
        "EXTERIOR_VIEW_STEMS",
    ):
        assert gone not in source, gone
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


def test_sheet_seven_uses_state_and_acceptance_tables_with_a_parked_view() -> None:
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
        f"{drawing.PINION_PARK_ANGLE_DEG:.2f} DEG",
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
        f"{drawing.PINION_PARK_ANGLE_DEG:.2f} DEG",
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




def test_every_exterior_view_is_a_distinct_orientation():
    """Two sheets share this tuple; a repeated name is the same picture twice.

    These views used to carry per-view component isolation, which made two
    *Isometric entries different pictures. Without it, sheet 6 rendered the
    identical complete assembly under two labels (Codex P2). Nothing else would
    catch that -- the drawing builds clean and the layout audits pass; it is
    only WRONG to a reader.
    """
    names = drawing.EXTERIOR_VIEW_NAMES
    assert len(set(names)) == len(names), f"repeated orientation in {names}"


def test_exterior_view_labels_do_not_claim_an_isolated_subsystem():
    """One label per view, and the label describes what the view shows.

    With isolation gone every exterior view shows the WHOLE assembly, so a label
    naming a subsystem ("PINION CAM / CONTROLS") is a caption for a picture that
    is not on the sheet.
    """
    labels = drawing.EXTERIOR_VIEW_LABELS
    assert len(labels) == len(drawing.EXTERIOR_VIEW_NAMES)
    assert len(set(labels)) == len(labels)
    for label in labels:
        assert "DRIVE TRAIN" in label, f"{label!r} does not name the subject shown"


def test_the_setup_view_isolates_exactly_the_items_its_note_promises():
    """Sheet 7's note says "ITEMS 12-24"; the view must show items 12-24.

    This view carries no balloons -- it exists to show one mechanism at a fixed
    scale -- so nothing downstream would notice it quietly widening to the whole
    32-item train while the note kept promising a subset.
    """
    low, high = drawing.PINION_SETUP_ITEM_RANGE
    expected = {
        stem
        for index, stem in enumerate(drawing.BOM_COMPONENTS, start=1)
        if low <= index <= high
    }
    assert drawing.PINION_SETUP_VIEW_STEMS == expected
    assert len(expected) == high - low + 1
    source = inspect.getsource(drawing.build)
    assert "visible_stems=PINION_SETUP_VIEW_STEMS" in source
