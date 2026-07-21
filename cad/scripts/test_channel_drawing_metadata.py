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
    "channel-spring-installed": "channel_spring_installed_spec",
    "connecting-rod": "connecting_rod_notes",
    "counter-spring": "counter_spring_spec",
    "rocker-arm": "rocker_arm_notes",
    "spring-hook": "spring_hook_spec",
    "summing-lever": "summing_lever_spec",
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
