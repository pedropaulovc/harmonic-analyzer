"""Cross-sheet offline contracts for the seven pen/summing drawings."""

from __future__ import annotations

import _config
import boss_hook_spec
import gooseneck_spec
import measuring_stick_spec
import output_fixture_spec
import pen_frame_spec
import pen_hanger_spec
import pen_wire_spec


SHEETS = (
    ("boss-hook", boss_hook_spec),
    ("gooseneck", gooseneck_spec),
    ("measuring-stick", measuring_stick_spec),
    ("output-fixture", output_fixture_spec),
    ("pen-frame", pen_frame_spec),
    ("pen-hanger", pen_hanger_spec),
    ("pen-wire", pen_wire_spec),
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


def test_notes_do_not_repeat_title_block_metadata() -> None:
    for part_name, spec in SHEETS:
        notes = spec.DRAWING_NOTES.upper()
        for duplicate in TITLE_BLOCK_OWNED_NOTE_TEXT:
            assert duplicate not in notes, f"{part_name}: {duplicate}"


def test_finish_field_does_not_repeat_generic_edge_break_instruction() -> None:
    for part_name, _spec in SHEETS:
        finish = str(_config.parts(part_name)["finish"]).upper()
        assert "DEBUR" not in finish, part_name
        assert "REMOVE BURR" not in finish, part_name
        assert "BREAK SHARP" not in finish, part_name
