"""Cross-sheet note ownership and placeholder contracts for PR 360."""

from __future__ import annotations

import importlib

import _config


MAGNIFIER_SPECS = {
    "sm-knife-mount": "sm_knife_mount_spec",
    "mg-lever-wire": "mg_lever_wire_spec",
    "mg-magnifying-bracket": "mg_magnifying_bracket_spec",
    "mg-magnifying-clamp": "mg_magnifying_clamp_spec",
    "mg-magnifying-lever": "mg_magnifying_lever_spec",
    "mg-magnifying-vertical-rod": "mg_magnifying_vertical_rod_spec",
    "mg-magnifying-wheel": "mg_magnifying_wheel_spec",
    "mg-wheel-bar": "mg_wheel_bar_spec",
    "mg-wheel-drum": "mg_wheel_drum_spec",
}


def test_title_block_owns_material_finish_units_and_general_requirements() -> None:
    template_owned = (
        "UNLESS OTHERWISE",
        "GENERAL TOLER",
        "LINEAR +/-",
        "DIMENSIONS IN",
        " UOS",
        "UNIT:",
        "UNITS:",
        " MILLIMET",
        " MM",
        "MATERIAL:",
        "FINISH:",
        "DEBUR",
        "BURR",
        "REMOVE BURR",
        "BREAK SHARP",
        "BREAK ALL",
        "SHARP EDGE",
        "EDGE BREAK",
    )
    for part_name, module_name in MAGNIFIER_SPECS.items():
        module = importlib.import_module(module_name)
        sheet_notes = tuple(
            value
            for name, value in vars(module).items()
            if isinstance(value, str)
            and (name == "DRAWING_NOTES" or name.endswith("_NOTE"))
        )
        notes = "\n".join(sheet_notes).upper()
        config = _config.parts(part_name)
        material = config["material_specification"].strip().upper()
        finish = config["finish"].strip().upper()
        # Exact title-block values must not be repeated.  Other material words
        # remain legal when they identify a feature-specific exception or an
        # explicit release hold (for example the wheel's unresolved brass hub).
        assert material and material not in notes, part_name
        assert finish and finish not in notes, part_name
        for duplicate in template_owned:
            assert duplicate not in notes, (part_name, duplicate)


def test_manufacturing_notes_have_no_placeholder_values() -> None:
    for part_name, module_name in MAGNIFIER_SPECS.items():
        module = importlib.import_module(module_name)
        sheet_notes = tuple(
            value
            for name, value in vars(module).items()
            if isinstance(value, str)
            and (name == "DRAWING_NOTES" or name.endswith("_NOTE"))
        )
        for note in sheet_notes:
            for placeholder in ("TBD", "TBC", "X.XX", "TO BE DETERMINED"):
                assert placeholder not in note.upper(), (part_name, placeholder)
