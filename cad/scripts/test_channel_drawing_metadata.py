"""Cross-sheet metadata and note-ownership contracts for PR 354."""

from __future__ import annotations

import importlib

import _config


CHANNEL_SPECS = {
    "amplitude-bar": "amplitude_bar_spec",
    "channel-lever": "channel_lever_spec",
    "channel-spring-installed": "channel_spring_installed_spec",
    "connecting-rod": "connecting_rod_spec",
    "counter-spring": "counter_spring_spec",
    "rocker-arm": "rocker_arm_spec",
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
        notes = importlib.import_module(module_name).DRAWING_NOTES.upper()
        config = _config.parts(part_name)
        assert config["material_specification"].strip(), part_name
        assert config["finish"].strip(), part_name
        for duplicate in forbidden:
            assert duplicate not in notes, (part_name, duplicate)


def test_manufacturing_notes_have_no_placeholder_callouts() -> None:
    for part_name, module_name in CHANNEL_SPECS.items():
        notes = importlib.import_module(module_name).DRAWING_NOTES.upper()
        for placeholder in ("TBD", "TBC", "X.XX", "TO BE DETERMINED"):
            assert placeholder not in notes, (part_name, placeholder)
