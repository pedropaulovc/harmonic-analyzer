"""Cross-sheet title-block and manufacturing-note contracts for PR 358."""

from __future__ import annotations

import importlib

import _config


FASTENER_SPECS = {
    "bracket-screw": "bracket_screw_spec",
    "clamp-screw": "clamp_screw_spec",
    "cone-pivot-screw": "cone_pivot_screw_spec",
    "cone-tip-pinch-screw": "cone_tip_pinch_screw_spec",
    "fillister-screw": "fillister_screw_spec",
    "foot-screw": "foot_screw_spec",
    "hanger-screw": "hanger_screw_spec",
    "hex-bolt": "hex_bolt_spec",
    "lag-screw": "lag_screw_spec",
    "pen-set-screw": "pen_set_screw_spec",
    "slotted-screw": "slotted_screw_spec",
    "swing-stop-screw": "swing_stop_screw_spec",
    "thumb-screw": "thumb_screw_spec",
}


def test_title_block_uses_the_exact_material_grade_and_finish() -> None:
    for part_name in FASTENER_SPECS:
        config = _config.parts(part_name)
        assert config["material"] == config["material_specification"], part_name
        assert config["finish"].strip(), part_name


def test_notes_are_complete_but_do_not_repeat_title_or_template_requirements() -> None:
    for part_name, module_name in FASTENER_SPECS.items():
        spec = importlib.import_module(module_name)
        notes = spec.DRAWING_NOTES.upper()

        assert spec.THREAD_DESIGNATION in spec.DRAWING_NOTES, part_name
        assert (
            "THREADS OMITTED FOR CLARITY" in notes
            or "THREADED END BELOW IT IS NOT MODELED" in notes
        ), part_name
        assert "HEAD" in notes or "KNOB" in notes, part_name

        for title_owned in (
            "AISI 12L14",
            "ASTM B16",
            "C36000",
            "BLACK OXIDE",
            "TURNED AND POLISHED",
            "UNLESS OTHERWISE SPECIFIED",
            "GENERAL TOLERANCE",
            "MATERIAL:",
            "FINISH:",
            "DEBURR",
            "REMOVE BURRS",
            "BREAK SHARP",
        ):
            assert title_owned not in notes, (part_name, title_owned)
