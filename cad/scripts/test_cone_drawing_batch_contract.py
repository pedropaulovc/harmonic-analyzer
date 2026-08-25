"""Cross-sheet offline contracts for the five cone-cluster drawings."""

from __future__ import annotations

import _config
import arbor_pedestal_spec
import cone_gear_shaft_spec
import cone_pivot_post_spec
import cone_tip_block_spec
import pivot_ball_mount_spec


SHEETS = (
    ("arbor-pedestal", arbor_pedestal_spec),
    ("cone-gear-shaft", cone_gear_shaft_spec),
    ("cone-pivot-post", cone_pivot_post_spec),
    ("cone-tip-block", cone_tip_block_spec),
    ("pivot-ball-mount", pivot_ball_mount_spec),
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


def test_notes_do_not_repeat_title_block_metadata() -> None:
    # Feature-specific edge limits remain valid exceptions to the title block's
    # general edge treatment.  Pivot-ball-mount intentionally tightens its two
    # functional shoulders to 0.10 max, rather than repeating the UOS 0.25 max.
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
