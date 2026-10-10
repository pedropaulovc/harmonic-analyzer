"""Cross-sheet offline contracts for the pen/summing drawings."""

from __future__ import annotations

import _config
import vn_boss_hook_spec
import sm_gooseneck_spec
import ms_stick_spec
import mg_output_fixture_spec
import pn_pen_frame_spec
import pn_pen_hanger_spec
import pn_pen_wire_spec


SHEETS = (
    ("vn-boss-hook", vn_boss_hook_spec),
    ("sm-gooseneck", sm_gooseneck_spec),
    ("ms-stick", ms_stick_spec),
    ("mg-output-fixture", mg_output_fixture_spec),
    ("pn-pen-frame", pn_pen_frame_spec),
    ("pn-pen-hanger", pn_pen_hanger_spec),
    ("pn-pen-wire", pn_pen_wire_spec),
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
