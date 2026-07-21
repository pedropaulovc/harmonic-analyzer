"""Cross-sheet offline contracts for the eight pinion-cluster drawings."""

from __future__ import annotations

import _config
import crank_handle_spec
import pinion_bracket_spec
import pinion_cam_pin_spec
import pinion_cam_spec
import pinion_handle_spec
import pinion_lever_spec
import pinion_pivot_shaft_spec
import pinion_spring_spec


SHEETS = (
    ("crank-handle", crank_handle_spec),
    ("pinion-bracket", pinion_bracket_spec),
    ("pinion-cam", pinion_cam_spec),
    ("pinion-cam-pin", pinion_cam_pin_spec),
    ("pinion-handle", pinion_handle_spec),
    ("pinion-lever", pinion_lever_spec),
    ("pinion-pivot-shaft", pinion_pivot_shaft_spec),
    ("pinion-spring", pinion_spring_spec),
)

TITLE_BLOCK_OWNED_NOTE_TEXT = (
    "ALL DIMENSIONS",
    "BREAK EDGES",
    "BREAK SHARP",
    "DEBUR",
    "EDGE BREAK",
    "FINISH:",
    "GENERAL TOLERANCE",
    "MATERIAL:",
    "REMOVE BURR",
    "SHARP EDGES",
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
