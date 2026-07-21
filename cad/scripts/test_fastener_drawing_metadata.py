"""Cross-sheet title-block and manufacturing-note contracts for PR 358."""

from __future__ import annotations

import importlib
import re
from pathlib import Path

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

SLOTTED_MADE_PARTS = {
    "bracket_screw_spec": "build_bracket_screw",
    "clamp_screw_spec": "build_clamp_screw",
    "fillister_screw_spec": "build_fillister_screw",
    "foot_screw_spec": "build_foot_screw",
    "lag_screw_spec": "build_lag_screw",
    "slotted_screw_spec": "build_slotted_screw",
}


def test_title_block_uses_the_exact_material_grade_and_finish() -> None:
    for part_name in FASTENER_SPECS:
        config = _config.parts(part_name)
        assert config["material"] == config["material_specification"], part_name
        assert config["finish"].strip(), part_name


def test_notes_are_complete_but_do_not_repeat_title_or_template_requirements() -> None:
    for part_name, module_name in FASTENER_SPECS.items():
        spec = importlib.import_module(module_name)
        notes = "\n".join((spec.DRAWING_NOTES, spec.END_VIEW_NOTE)).upper()

        assert spec.THREAD_DESIGNATION in spec.DRAWING_NOTES, part_name
        assert (
            "THREAD GEOMETRY OMITTED IN VIEWS" in notes
            or "THREADED END BELOW IT IS NOT MODELED" in notes
        ), part_name
        assert "HEAD" in notes or "KNOB" in notes, part_name

        for title_owned in (
            "AISI 12L14",
            "ASTM B16",
            "C36000",
            "BLACK OXIDE",
            "TURNED AND POLISHED",
            "ALL DIMENSIONS",
            "DRAWING UNITS",
            "EDGE BREAK",
            "UNLESS OTHERWISE SPECIFIED",
            "GENERAL TOLERANCE",
            "MATERIAL:",
            "FINISH:",
            "UNITS:",
            " UOS",
            "DEBURR",
            "REMOVE BURRS",
            "BREAK SHARP",
        ):
            assert title_owned not in notes, (part_name, title_owned)

        assert re.search(r"\b(?:MM|MILLIMET(?:ER|RE)S?)\b", notes) is None, (
            part_name,
            "unit suffix",
        )


def test_finish_field_does_not_repeat_template_edge_break_instruction() -> None:
    for part_name in FASTENER_SPECS:
        finish = str(_config.parts(part_name)["finish"]).upper()
        assert "DEBUR" not in finish, part_name
        assert "REMOVE BURR" not in finish, part_name
        assert "BREAK SHARP" not in finish, part_name


def test_made_part_slot_callouts_use_the_same_contract_as_the_builder() -> None:
    for spec_name, build_name in SLOTTED_MADE_PARTS.items():
        spec = importlib.import_module(spec_name)
        build = importlib.import_module(build_name)
        source = Path(build.__file__).read_text(encoding="utf-8")

        assert f"{spec.SLOT_W:.2f} +/-0.10 WIDE" in spec.DRAWING_NOTES
        assert f"{spec.SLOT_D:.2f} +/-0.10 DEEP" in spec.DRAWING_NOTES
        if build_name in {"build_bracket_screw", "build_clamp_screw"}:
            assert "slot_width=SLOT_W" in source
            assert "slot_depth=SLOT_D" in source
            continue
        assert "width_mm=SLOT_W" in source
        assert "depth_mm=SLOT_D" in source
