"""Cross-sheet offline contracts for the seven assembly drawings."""

from __future__ import annotations

import re
from pathlib import Path

import _config
import draw_channel_assembly
import draw_drive_train_assembly
import draw_frame_assembly
import draw_harmonic_analyzer_assembly
import draw_magnifier_assembly
import draw_paper_drive_assembly
import draw_summing_assembly


SHEETS = (
    draw_channel_assembly,
    draw_drive_train_assembly,
    draw_frame_assembly,
    draw_harmonic_analyzer_assembly,
    draw_magnifier_assembly,
    draw_paper_drive_assembly,
    draw_summing_assembly,
)

TITLE_BLOCK_OWNED_NOTE_TEXT = (
    "ALL DIMENSIONS",
    "BREAK SHARP",
    "DEBUR",
    "DRAWING UNITS",
    "EDGE BREAK",
    "FINISH:",
    "GENERAL TOLERANCE",
    "MATERIAL:",
    "REMOVE BURR",
    "UNLESS OTHERWISE SPECIFIED",
    "UNITS:",
    " UOS",
)


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
        for number, line in enumerate(lines[1:], start=1):
            assert line.startswith(f"{number}. "), (
                f"{drawing.ARTIFACT_STEM}: {line}"
            )


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


def test_each_sheet_uses_three_hlr_views_bom_and_balloons() -> None:
    for drawing in SHEETS:
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
        assert source.count("add_auto_balloons(") == 1, drawing.ARTIFACT_STEM
