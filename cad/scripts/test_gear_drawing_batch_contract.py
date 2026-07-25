"""Cross-sheet offline contracts for the eight current gear drawings."""

from __future__ import annotations

from pathlib import Path

import _config
import alignment_pinion_spec
import cone_gear_spec
import crank_drive_gear_spec
import crank_pinion_spec
import cylinder_gear_spec
import draw_alignment_pinion
import draw_cone_gear
import draw_crank_drive_gear
import draw_crank_pinion
import draw_cylinder_gear
import draw_rack_pinion
import draw_transgear_feed_pinion
import draw_transgear_pinion
import rack_pinion_spec
import transgear_feed_pinion_spec
import transgear_pinion_spec


SHEETS = (
    ("alignment-pinion", alignment_pinion_spec),
    ("cone-gear", cone_gear_spec),
    ("crank-drive-gear", crank_drive_gear_spec),
    ("crank-pinion", crank_pinion_spec),
    ("cylinder-gear", cylinder_gear_spec),
    ("rack-pinion", rack_pinion_spec),
    ("transgear-feed-pinion", transgear_feed_pinion_spec),
    ("transgear-pinion", transgear_pinion_spec),
)

DRAWING_MODULES = (
    draw_alignment_pinion,
    draw_cone_gear,
    draw_crank_drive_gear,
    draw_crank_pinion,
    draw_cylinder_gear,
    draw_rack_pinion,
    draw_transgear_feed_pinion,
    draw_transgear_pinion,
)

CRANK_PAIR_MODULES = (
    draw_crank_drive_gear,
    draw_crank_pinion,
)

PRECOMPUTED_BORE_PICK_MODULES = (
    draw_alignment_pinion,
    draw_cone_gear,
    draw_crank_drive_gear,
    draw_crank_pinion,
    draw_cylinder_gear,
    draw_rack_pinion,
    draw_transgear_feed_pinion,
    draw_transgear_pinion,
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


def test_notes_do_not_repeat_title_block_quantity() -> None:
    for part_name, spec in SHEETS:
        if part_name == "cone-gear":
            # One of each configuration is essential family-table scope, not a
            # repeat of the per-configuration title-block quantity.
            continue
        assert " REQUIRED" not in spec.DRAWING_NOTES.upper(), part_name


def test_bore_annotations_use_explicit_nonconflicting_selectors() -> None:
    assert PRECOMPUTED_BORE_PICK_MODULES == DRAWING_MODULES
    for module in PRECOMPUTED_BORE_PICK_MODULES:
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "visible_circle_edge" not in source, module.__name__
        assert "entity=bore_edge" not in source, module.__name__
        assert source.count("edge_xy=bore_top") == 2, module.__name__
        assert "leader_attach_xy=" not in source, module.__name__
        expected_tolerance = "position_tolerance_m=0.0001"
        if module in CRANK_PAIR_MODULES:
            expected_tolerance = "position_tolerance_m=0.080"
        if module is draw_cylinder_gear:
            expected_tolerance = "position_tolerance_m=0.008"
        assert expected_tolerance in source, module.__name__
        assert "shoulder=True" in source, module.__name__


def test_crank_pair_runout_uses_typed_precomputed_tooth_top_pick() -> None:
    for module in CRANK_PAIR_MODULES:
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "visible_tooth_tip_silhouette" not in source
        assert "edge_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] + HALF_OD)" in source
        assert 'entity_type="SILHOUETTE"' in source


def test_tooth_runout_is_stated_against_the_bore_axis_datum() -> None:
    for (part_name, spec), module in zip(SHEETS, DRAWING_MODULES, strict=True):
        if module in CRANK_PAIR_MODULES:
            source = Path(module.__file__).read_text(encoding="utf-8")
            assert 'characteristic="circular_runout"' in source, part_name
            assert 'datums=("A",)' in source, part_name
            assert 'quantity="TOOTH TIPS"' in source, part_name
            continue
        notes = spec.DRAWING_NOTES.upper()
        assert (
            "GEAR TEETH: CIRCULAR RUNOUT 0.05 MAX ABOUT DATUM A, "
            "MEASURED AT THE TOOTH TIPS" in notes
        ), part_name
        assert "WITHIN 0.05 TIR" not in notes, part_name
