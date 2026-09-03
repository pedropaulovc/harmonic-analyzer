"""Cross-sheet offline contracts for the seven pen/summing drawings.

Every sheet in this batch follows cad/docs/drawing-simplicity-policy.md: at
most four short note lines of part-specific process fact, nothing the title
block already says, and no GD&T narration.
"""

from __future__ import annotations

from pathlib import Path

import _config
import boss_hook_spec
import draw_boss_hook
import draw_gooseneck
import draw_measuring_stick
import draw_output_fixture
import draw_pen_frame
import draw_pen_hanger
import draw_pen_wire
import gooseneck_spec
import measuring_stick_spec
import output_fixture_spec
import pen_frame_spec
import pen_hanger_spec
import pen_wire_spec


SHEETS = (
    ("boss-hook", boss_hook_spec, draw_boss_hook),
    ("gooseneck", gooseneck_spec, draw_gooseneck),
    ("measuring-stick", measuring_stick_spec, draw_measuring_stick),
    ("output-fixture", output_fixture_spec, draw_output_fixture),
    ("pen-frame", pen_frame_spec, draw_pen_frame),
    ("pen-hanger", pen_hanger_spec, draw_pen_hanger),
    ("pen-wire", pen_wire_spec, draw_pen_wire),
)

TITLE_BLOCK_OWNED_NOTE_TEXT = (
    "ALL DIMENSIONS",
    "BREAK SHARP",
    "DEBUR",
    "FINISH:",
    "GENERAL TOLERANCE",
    "MATERIAL:",
    "REMOVE ALL BURR",
    "U.O.S.",
    "UNLESS OTHERWISE SPECIFIED",
    " UOS",
)

# drawing-simplicity-policy.md rule 3 and 6: a note never carries a
# tolerance, never explains a datum letter, never narrates a frame.
GDT_AND_TOLERANCE_NOTE_TEXT = (
    "+/-",
    "DATUM",
    "PER FCF",
    "WITHIN",
    "TIR",
)

GDT_HELPERS = (
    "add_datum_feature(",
    "add_feature_control_frame(",
    "add_surface_finish(",
    "set_basic_dimension(",
    "project_part_pmi(",
)


def test_notes_do_not_repeat_title_block_metadata() -> None:
    for part_name, spec, _drawing in SHEETS:
        notes = spec.DRAWING_NOTES.upper()
        for duplicate in TITLE_BLOCK_OWNED_NOTE_TEXT:
            assert duplicate not in notes, f"{part_name}: {duplicate}"


def test_notes_are_at_most_four_lines_without_gdt_narration() -> None:
    for part_name, spec, _drawing in SHEETS:
        notes = spec.DRAWING_NOTES
        assert len(notes.split("\n")) <= 4, part_name
        for banned in GDT_AND_TOLERANCE_NOTE_TEXT:
            assert banned not in notes.upper(), f"{part_name}: {banned}"


def test_sheets_carry_no_gdt_or_roughness_symbols() -> None:
    # None of these parts is on the policy's GD&T allowlist and nothing on
    # them runs against another part at a controlled finish.
    for part_name, spec, drawing in SHEETS:
        source = Path(drawing.__file__).read_text(encoding="utf-8")
        for helper in GDT_HELPERS:
            assert helper not in source, f"{part_name}: {helper}"
        assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM"), part_name


def test_finish_field_does_not_repeat_generic_edge_break_instruction() -> None:
    for part_name, _spec, _drawing in SHEETS:
        finish = str(_config.parts(part_name)["finish"]).upper()
        assert "DEBUR" not in finish
        assert "REMOVE BURR" not in finish
        assert "BREAK SHARP" not in finish
