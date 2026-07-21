"""Cross-sheet note ownership and placeholder contracts for PR 360."""

from __future__ import annotations

import importlib

import _config


MAGNIFIER_SPECS = {
    "knife-mount": "knife_mount_spec",
    "lever-wire": "lever_wire_spec",
    "magnifying-bracket": "magnifying_bracket_spec",
    "magnifying-clamp": "magnifying_clamp_spec",
    "magnifying-lever": "magnifying_lever_spec",
    "magnifying-vertical-rod": "magnifying_vertical_rod_spec",
    "magnifying-wheel": "magnifying_wheel_spec",
    "wheel-bar": "wheel_bar_spec",
}


def test_title_block_owns_material_finish_units_and_general_requirements() -> None:
    template_owned = (
        "UNLESS OTHERWISE",
        "GENERAL TOLER",
        "LINEAR +/-",
        " UOS",
        "UNIT:",
        "UNITS:",
        " MILLIMET",
        " MM",
        "MATERIAL:",
        "FINISH:",
        "AISI",
        "ASTM",
        "C36000",
        "GRAY IRON",
        "CAST IRON",
        "BRASS",
        "STEEL",
        "DEBUR",
        "REMOVE BURR",
        "BREAK SHARP",
        "EDGE BREAK",
    )
    for part_name, module_name in MAGNIFIER_SPECS.items():
        notes = importlib.import_module(module_name).DRAWING_NOTES.upper()
        config = _config.parts(part_name)
        material = config["material_specification"].strip().upper()
        finish = config["finish"].strip().upper()
        assert material and material not in notes, part_name
        assert finish and finish not in notes, part_name
        for duplicate in template_owned:
            assert duplicate not in notes, (part_name, duplicate)


def test_manufacturing_notes_have_no_placeholder_values() -> None:
    for part_name, module_name in MAGNIFIER_SPECS.items():
        notes = importlib.import_module(module_name).DRAWING_NOTES.upper()
        for placeholder in ("TBD", "TBC", "X.XX", "TO BE DETERMINED"):
            assert placeholder not in notes, (part_name, placeholder)
