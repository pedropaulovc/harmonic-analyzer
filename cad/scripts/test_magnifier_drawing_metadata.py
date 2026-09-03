"""Cross-sheet note ownership and simplicity contracts for the magnifier sheets.

Started as the PR 360 placeholder/ownership contract; now also pins the
cad/docs/drawing-simplicity-policy.md note rules (few lines, no release holds,
no GD&T narration) across every magnifier spec at once.
"""

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

# The only magnifier part on the policy's GD&T allowlist (the knife-edge
# system): one position frame on the bore, one datum.
GDT_ALLOWLISTED = {"knife-mount"}


def _sheet_notes(module_name: str) -> tuple[str, ...]:
    module = importlib.import_module(module_name)
    return tuple(
        value
        for name, value in vars(module).items()
        if isinstance(value, str) and (name == "DRAWING_NOTES" or name.endswith("_NOTE"))
    )


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
        notes = "\n".join(_sheet_notes(module_name)).upper()
        config = _config.parts(part_name)
        material = config["material_specification"].strip().upper()
        finish = config["finish"].strip().upper()
        # Exact title-block values must not be repeated.
        assert material and material not in notes, part_name
        assert finish and finish not in notes, part_name
        for duplicate in template_owned:
            assert duplicate not in notes, (part_name, duplicate)


def test_manufacturing_notes_have_no_placeholder_values() -> None:
    for part_name, module_name in MAGNIFIER_SPECS.items():
        for note in _sheet_notes(module_name):
            for placeholder in ("TBD", "TBC", "X.XX", "TO BE DETERMINED"):
                assert placeholder not in note.upper(), (part_name, placeholder)


def test_manufacturing_notes_are_few_and_never_a_hold_or_a_gdt_lecture() -> None:
    # Policy rule 6: at most four short lines of process fact; a release hold,
    # a datum explanation or a frame paraphrase is not a machining instruction.
    banned = (
        "DO NOT RELEASE",
        "NOT DEFINED",
        "SOURCE MODEL",
        "DATUM",
        "CONTROL PER FCF",
        "PERPENDICULAR",
        "PARALLEL",
        "RUNOUT",
        "WITHIN 0.",
        "+/-",
        "Ra ",
    )
    for part_name, module_name in MAGNIFIER_SPECS.items():
        module = importlib.import_module(module_name)
        lines = module.DRAWING_NOTES.split("\n")
        assert 1 <= len(lines) <= 4, (part_name, len(lines))
        assert all(line.strip() for line in lines), part_name
        for phrase in banned:
            assert phrase not in module.DRAWING_NOTES, (part_name, phrase)


def test_only_the_knife_mount_keeps_a_geometric_tolerance_table() -> None:
    # Policy rule 3: the knife mount is the one magnifier part on the allowlist.
    for part_name, module_name in MAGNIFIER_SPECS.items():
        module = importlib.import_module(module_name)
        has_gdt = hasattr(module, "GEOMETRIC_TOLERANCES_MM") or bool(
            getattr(module, "GEOMETRIC_CONTROLS", ())
        )
        assert has_gdt == (part_name in GDT_ALLOWLISTED), part_name
