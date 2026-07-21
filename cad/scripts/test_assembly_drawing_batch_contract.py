"""Cross-sheet offline contracts for the seven assembly drawings."""

from __future__ import annotations

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
    "FINISH:",
    "GENERAL TOLERANCE",
    "MATERIAL:",
    "REMOVE BURR",
    "UNLESS OTHERWISE SPECIFIED",
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
