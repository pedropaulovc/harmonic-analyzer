"""Cross-sheet metadata and note-ownership contracts for PR 354."""

from __future__ import annotations

import importlib

import _config


# Module carrying each sheet's DRAWING_NOTES / ISOMETRIC_VIEW_NOTE.  Parts
# whose geometry is imported by an assembly keep their prose in a separate
# *_notes module (codex #354) so notes edits stay out of assembly closures.
CHANNEL_SPECS = {
    "amplitude-bar": "amplitude_bar_spec",
    "channel-lever": "channel_lever_spec",
    "channel-spring-installed": "channel_spring_installed_notes",
    "connecting-rod": "connecting_rod_notes",
    "counter-spring": "counter_spring_notes",
    "rocker-arm": "rocker_arm_notes",
    "spring-hook": "spring_hook_notes",
    "summing-lever": "summing_lever_notes",
}


def test_title_block_owns_material_finish_units_and_general_requirements() -> None:
    forbidden = (
        "UNLESS OTHERWISE",
        "GENERAL TOLER",
        "LINEAR +/-",
        " UOS",
        "UNIT:",
        "UNITS:",
        " MILLIMET",
        " MM",
        "MATERIAL",
        "FINISH",
        "AISI",
        "ASTM",
        "STEEL",
        "IRON",
        "CHROME",
        "OXIDE",
        "JAPAN",
        "DEBUR",
        "REMOVE BURR",
        "BREAK SHARP",
        "EDGE BREAK",
    )
    for part_name, module_name in CHANNEL_SPECS.items():
        module = importlib.import_module(module_name)
        sheet_notes = (module.DRAWING_NOTES, module.ISOMETRIC_VIEW_NOTE)
        config = _config.parts(part_name)
        assert config["material_specification"].strip(), part_name
        assert config["finish"].strip(), part_name
        for note in sheet_notes:
            for duplicate in forbidden:
                assert duplicate not in note.upper(), (part_name, duplicate)


def test_manufacturing_notes_have_no_placeholder_callouts() -> None:
    for part_name, module_name in CHANNEL_SPECS.items():
        module = importlib.import_module(module_name)
        sheet_notes = (module.DRAWING_NOTES, module.ISOMETRIC_VIEW_NOTE)
        for note in sheet_notes:
            for placeholder in ("TBD", "TBC", "X.XX", "TO BE DETERMINED"):
                assert placeholder not in note.upper(), (part_name, placeholder)


# The two coil springs are spec sheets: their "notes" ARE the spring data
# block, the rule-6 exception to the four-line cap.
SPRING_DATA_SHEETS = {"channel-spring-installed", "counter-spring"}


def test_notes_are_few_and_carry_no_gdt_prose() -> None:
    # cad/docs/drawing-simplicity-policy.md rule 6: at most four short lines
    # of process fact; never a datum explanation, a boxed-basic reference, a
    # "within" limit or a tolerance band.
    for part_name, module_name in CHANNEL_SPECS.items():
        module = importlib.import_module(module_name)
        notes = module.DRAWING_NOTES
        if part_name not in SPRING_DATA_SHEETS:
            assert len(notes.split("\n")) <= 4, part_name
        for banned in ("DATUM", "BASIC", "FCF", "WITHIN", "+/-", "PER CALLOUT"):
            assert banned not in notes.upper(), (part_name, banned)


def test_spring_data_blocks_are_compact_shop_contracts() -> None:
    for part_name in SPRING_DATA_SHEETS:
        module = importlib.import_module(CHANNEL_SPECS[part_name])
        lines = module.DRAWING_NOTES.splitlines()
        assert 6 <= len(lines) <= 8, part_name
        assert lines[0] == "EXTENSION SPRING DATA", part_name
        for field in (
            "WIRE Ø",
            "OD",
            "FREE LENGTH",
            "ACTIVE COILS",
            "RIGHT HAND",
            "ENDS",
        ):
            assert field in module.DRAWING_NOTES, (part_name, field)
        assert max(map(len, lines)) <= 52, part_name
