"""Cross-sheet offline contracts for the six cone-cluster drawings.

Every sheet here is a plain print under cad/docs/drawing-simplicity-policy.md:
none is on the GD&T allowlist, so no datums, frames, basics or drawing-owned
tolerance mappings, and at most four lines of process notes.
"""

from __future__ import annotations

from pathlib import Path

import _config
import arbor_pedestal_spec
import cone_gear_shaft_spec
import cone_lock_knob_spec
import cone_pivot_post_spec
import cone_tip_adjuster_spec
import cone_tip_block_spec
import draw_arbor_pedestal
import draw_cone_gear_shaft
import draw_cone_lock_knob
import draw_cone_pivot_post
import draw_cone_tip_adjuster
import draw_cone_tip_block


SHEETS = (
    ("arbor-pedestal", arbor_pedestal_spec, draw_arbor_pedestal),
    ("cone-gear-shaft", cone_gear_shaft_spec, draw_cone_gear_shaft),
    ("cone-lock-knob", cone_lock_knob_spec, draw_cone_lock_knob),
    ("cone-pivot-post", cone_pivot_post_spec, draw_cone_pivot_post),
    ("cone-tip-adjuster", cone_tip_adjuster_spec, draw_cone_tip_adjuster),
    ("cone-tip-block", cone_tip_block_spec, draw_cone_tip_block),
)

TITLE_BLOCK_OWNED_NOTE_TEXT = (
    "ALL DIMENSIONS",
    "BREAK SHARP",
    "DEBUR",
    "DRAWING UNITS",
    "FINISH:",
    "GENERAL TOLERANCE",
    "MATERIAL:",
    "REMOVE BURR",
    "UNLESS OTHERWISE SPECIFIED",
    "UNITS:",
    " UOS",
)


GDT_HELPERS = (
    "add_datum_feature(",
    "add_feature_control_frame(",
    "set_basic_dimension(",
    "project_part_pmi(",
)
# Words a note carries only when it is restating a dimension, a deleted
# frame or the title block.
NOTE_BANNED_WORDS = ("+/-", "DATUM", "WITHIN", "BASIC", "FCF", "GD&T", "UOS")


def test_notes_do_not_repeat_title_block_metadata() -> None:
    for part_name, spec, _drawing in SHEETS:
        notes = spec.DRAWING_NOTES.upper()
        for duplicate in TITLE_BLOCK_OWNED_NOTE_TEXT:
            assert duplicate not in notes, f"{part_name}: {duplicate}"


def test_notes_are_at_most_four_lines_of_process_fact() -> None:
    for part_name, spec, _drawing in SHEETS:
        lines = spec.DRAWING_NOTES.split("\n")
        assert len(lines) <= 4, (part_name, len(lines))
        for word in NOTE_BANNED_WORDS:
            assert word not in spec.DRAWING_NOTES, (part_name, word)


def test_sheets_carry_no_gdt_or_basic_dimensions() -> None:
    for part_name, spec, drawing in SHEETS:
        source = Path(drawing.__file__).read_text(encoding="utf-8")
        for helper in GDT_HELPERS:
            assert helper not in source, (part_name, helper)
        assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM"), part_name
        assert getattr(spec, "GEOMETRIC_CONTROLS", ()) == (), part_name
        assert getattr(spec, "PART_DATUMS", ()) == (), part_name


def test_finish_field_does_not_repeat_generic_edge_break_instruction() -> None:
    for part_name, _spec, _drawing in SHEETS:
        finish = str(_config.parts(part_name)["finish"]).upper()
        assert "DEBUR" not in finish, part_name
        assert "REMOVE BURR" not in finish, part_name
        assert "BREAK SHARP" not in finish, part_name
