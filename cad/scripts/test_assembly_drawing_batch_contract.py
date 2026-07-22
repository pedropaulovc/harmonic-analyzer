"""Cross-sheet offline contracts for the seven assembly drawings."""

from __future__ import annotations

import re
from pathlib import Path

import _config
import _assembly_drawing_bom
import _drawing_common as drawing_common
import draw_channel_assembly
import draw_drive_train_assembly
import draw_frame_assembly
import draw_harmonic_analyzer_assembly
import draw_magnifier_assembly
import draw_paper_drive_assembly
import draw_summing_assembly
from _drawing_common import (
    _bom_identity_map,
    _configure_manual_bom_column,
    _set_bom_cell_text,
)


SHEETS = (
    draw_channel_assembly,
    draw_drive_train_assembly,
    draw_frame_assembly,
    draw_harmonic_analyzer_assembly,
    draw_magnifier_assembly,
    draw_paper_drive_assembly,
    draw_summing_assembly,
)

ORDINARY_SHEETS = tuple(
    drawing for drawing in SHEETS if drawing is not draw_drive_train_assembly
)

TITLE_BLOCK_OWNED_NOTE_TEXT = (
    "ALL DIMENSIONS",
    "BREAK ALL",
    "BREAK SHARP",
    "BURR",
    "DEBUR",
    "DIMENSIONS IN",
    "DRAWING UNITS",
    "EDGE BREAK",
    "FINISH:",
    "GENERAL TOLER",
    "MATERIAL:",
    "REMOVE BURR",
    "SHARP EDGE",
    "UNLESS OTHERWISE SPECIFIED",
    "UNITS:",
    " UOS",
)


def test_grouped_bom_columns_become_user_defined_before_cell_writes(
    monkeypatch,
) -> None:
    class GroupedTable:
        def __init__(self) -> None:
            self.calls: list[tuple[int, int, bool, str]] = []
            self.column_types = {1: 201, 2: 204}
            self.column_titles = {1: "PART NUMBER", 2: "DESCRIPTION"}
            self.column_properties: dict[int, str] = {}
            self.values: dict[tuple[int, int], str] = {}

        def SetColumnType3(
            self, column: int, column_type: int, include_hidden: bool, title: str
        ) -> int:
            self.column_types[column] = column_type
            return 0

        def GetColumnType2(self, column: int, include_hidden: bool) -> int:
            return self.column_types[column]

        def SetColumnTitle2(
            self, column: int, title: str, include_hidden: bool
        ) -> bool:
            self.column_titles[column] = title
            return True

        def SetColumnCustomProperty(self, column: int, title: str) -> bool:
            if self.column_types[column] != 204:
                return False
            self.column_properties[column] = title
            return True

        def GetColumnCustomProperty(self, column: int) -> str:
            return self.column_properties.get(column, "")

        def SetText2(
            self, row: int, column: int, include_hidden: bool, text: str
        ) -> None:
            self.calls.append((row, column, include_hidden, text))
            if column in self.column_properties:
                self.values[row, column] = text

        def DisplayedText2(
            self, row: int, column: int, include_hidden: bool
        ) -> str:
            return self.values.get((row, column), "")

    monkeypatch.setattr(
        drawing_common._sw_type_info,
        "early_bound_or_flag",
        lambda table, *_args: table,
    )

    for column, value, label in (
        (2, "CHAIN SPROCKET, T12/T18/T24; 1 EACH", "DESCRIPTION"),
        (1, "MHA-081", "PART NUMBER"),
    ):
        table = GroupedTable()
        _configure_manual_bom_column(
            table,
            column,
            label,
            replace_native=label == "PART NUMBER",
            label=label,
        )
        _set_bom_cell_text(
            table,
            4,
            column,
            value,
            label=label,
        )
        assert table.DisplayedText2(4, column, False) == value
        assert table.column_properties[column] == label
        assert table.calls == [(4, column, False, value)]

    common_source = Path(_set_bom_cell_text.__code__.co_filename).read_text(
        encoding="utf-8"
    )
    identified_source = Path(_assembly_drawing_bom.__file__).read_text(
        encoding="utf-8"
    )
    assert "label=f\"{label} BOM description\"" in common_source
    assert "label=f\"{label} BOM part number\"" in identified_source


def test_bom_identity_map_accepts_stems_and_released_number_aliases() -> None:
    identities = _bom_identity_map(
        ("cone-gear", "pinion-cam-pin"),
        {"MHA-013": "cone-gear", "MHA-116": "pinion-cam-pin"},
    )
    assert identities["cone-gear"] == "cone-gear"
    assert identities["mha-013"] == "cone-gear"
    assert identities["pinion-cam-pin"] == "pinion-cam-pin"
    assert identities["mha-116"] == "pinion-cam-pin"


def test_assembly_notes_do_not_repeat_title_block_metadata() -> None:
    for drawing in SHEETS:
        notes = drawing.ASSEMBLY_NOTES.upper()
        for duplicate in TITLE_BLOCK_OWNED_NOTE_TEXT:
            assert duplicate not in notes, f"{drawing.ARTIFACT_STEM}: {duplicate}"


def test_assembly_notes_are_numbered_in_order() -> None:
    for drawing in SHEETS:
        lines = drawing.ASSEMBLY_NOTES.splitlines()
        assert lines[0] == "ASSEMBLY NOTES", drawing.ARTIFACT_STEM
        assert len(lines) >= 4, drawing.ARTIFACT_STEM
        expected_number = 1
        for line in lines[1:]:
            if line.startswith("   "):
                assert expected_number > 1, drawing.ARTIFACT_STEM
                assert line.strip(), drawing.ARTIFACT_STEM
                continue
            assert line.startswith(f"{expected_number}. "), (
                f"{drawing.ARTIFACT_STEM}: {line}"
            )
            expected_number += 1
        assert expected_number >= 4, drawing.ARTIFACT_STEM


def test_each_sheet_has_a_complete_bom_contract() -> None:
    for drawing in SHEETS:
        assert drawing.BOM_COMPONENTS, drawing.ARTIFACT_STEM
        assert all(drawing.BOM_COMPONENTS.values()), drawing.ARTIFACT_STEM
        assert len(drawing.BOM_COMPONENTS) == len(set(drawing.BOM_COMPONENTS.values())), (
            drawing.ARTIFACT_STEM
        )
        assert set(drawing.BOM_PART_NUMBERS) == set(drawing.BOM_COMPONENTS), (
            drawing.ARTIFACT_STEM
        )
        assert len(drawing.BOM_PART_NUMBERS) == len(
            set(drawing.BOM_PART_NUMBERS.values())
        ), drawing.ARTIFACT_STEM
        assert all(
            re.fullmatch(r"MHA-(?:\d{3}|A\d{2})", number)
            for number in drawing.BOM_PART_NUMBERS.values()
        ), drawing.ARTIFACT_STEM


def test_part_bom_numbers_come_from_the_part_registry() -> None:
    for drawing in SHEETS:
        if drawing is draw_harmonic_analyzer_assembly:
            continue
        assert drawing.BOM_PART_NUMBERS == {
            stem: _config.parts(stem)["number"]
            for stem in drawing.BOM_COMPONENTS
        }, drawing.ARTIFACT_STEM


def test_part_registry_numbers_are_globally_unique() -> None:
    numbers = {
        stem: record["number"]
        for stem, record in _config.parts().items()
    }
    assert len(numbers) == len(set(numbers.values()))
    assert numbers["lever-wire"] == "MHA-115"
    assert numbers["pen-wire"] == "MHA-100"
    assert numbers["pinion-cam-pin"] == "MHA-116"


def test_top_level_bom_uses_released_subassembly_numbers() -> None:
    assert draw_harmonic_analyzer_assembly.BOM_PART_NUMBERS == {
        "frame": "MHA-A04",
        "drive-train": "MHA-A03",
        "channel": "MHA-A02",
        "summing": "MHA-A07",
        "magnifier": "MHA-A05",
        "pen": "MHA-A01",
        "paper-drive": "MHA-A06",
        "measuring-stick": "MHA-046",
    }


def test_configured_variants_remain_visible_after_bom_row_collapse() -> None:
    assert draw_drive_train_assembly.BOM_COMPONENTS["cone-gear"] == (
        "CONE GEAR, T006-T120 BY 6; 1 EACH"
    )
    assert draw_paper_drive_assembly.BOM_COMPONENTS["transgear-removable"] == (
        "CHAIN SPROCKET, T12/T18/T24; 1 EACH"
    )


def test_unresolved_assembly_inputs_are_release_holds_not_guessed_details() -> None:
    assert "HARDENED KNIFE SEATS" in draw_summing_assembly.ASSEMBLY_NOTES
    assert "MOUNT-TO-CROSSBAR FASTENERS" in draw_summing_assembly.ASSEMBLY_NOTES
    assert "LEVER-WIRE TERMINATIONS" in draw_magnifier_assembly.ASSEMBLY_NOTES
    assert "WHEEL HUB/RIM" in draw_magnifier_assembly.ASSEMBLY_NOTES
    top_notes = draw_harmonic_analyzer_assembly.ASSEMBLY_NOTES
    assert "GENERAL-ARRANGEMENT REFERENCE ONLY" in top_notes
    assert "LOCATING FEATURES AND FASTENERS" in top_notes


def test_ordinary_sheets_use_three_hlr_views_bom_and_balloons() -> None:
    for drawing in ORDINARY_SHEETS:
        source = Path(drawing.__file__).read_text(encoding="utf-8")
        assert source.count("place_view(") == 3, drawing.ARTIFACT_STEM
        assert "for view in (front, right, iso):" in source, drawing.ARTIFACT_STEM
        assert "set_hidden_lines_removed(adapter, view)" in source, (
            drawing.ARTIFACT_STEM
        )
        assert source.count("insert_identified_bom_table(") == 1, (
            drawing.ARTIFACT_STEM
        )
        assert "part_numbers=BOM_PART_NUMBERS" in source, drawing.ARTIFACT_STEM
        balloon_calls = source.count("add_auto_balloons(") + source.count(
            "add_auto_balloons_across_views("
        )
        assert balloon_calls == 1, drawing.ARTIFACT_STEM


def test_drive_train_uses_dedicated_multisheet_identification_views() -> None:
    source = Path(draw_drive_train_assembly.__file__).read_text(encoding="utf-8")
    assert draw_drive_train_assembly.SHEET_NAMES == (
        "GENERAL ASSEMBLY",
        "PARTS LIST",
        "GEAR-TRAIN ITEM IDENTIFICATION",
        "CONCEALED ITEM IDENTIFICATION",
        "GEAR-TRAIN SETUP",
        "PINION ITEM IDENTIFICATION",
        "PINION SETUP AND ACCEPTANCE",
    )
    assert set().union(
        *draw_drive_train_assembly.EXTERIOR_VIEW_STEMS
    ) == set(draw_drive_train_assembly.BOM_COMPONENTS) - set(
        draw_drive_train_assembly.CONCEALED_BALLOON_ITEMS
    )
    assert len(draw_drive_train_assembly.GEAR_PAIR_ROWS) == 20
    assert draw_drive_train_assembly.PINION_PARAMETER_ROWS
    assert draw_drive_train_assembly.ACCEPTANCE_ROWS
    assert "_add_component_balloons(" in source
    assert "_isolate_balloon_components(" in source
    assert "insert_identified_bom_table(" in source
    assert "part_numbers=BOM_PART_NUMBERS" in source
    assert "HorizontalAutoSplit(" not in source
    assert "_format_drive_train_bom(adapter, bom_table)" in source
    assert "_create_drive_train_sheets(adapter)" in source
    assert "expected_sheet_names=SHEET_NAMES" in source
    assert "SETUP_IDENTIFICATION_VIEW_SCALE" not in source
