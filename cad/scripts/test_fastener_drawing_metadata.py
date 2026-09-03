"""Cross-sheet title-block and manufacturing-note contracts for the made
fasteners (PR 358 sheets plus the knife-hanger stud).

The group is the fleet's plainest: cad/docs/drawing-simplicity-policy.md rule 3
puts every screw and stud OFF the GD&T allowlist, rule 5 leaves one roughness
symbol (the cone pivot screw's ground shoulder) and rule 6 caps the notes at
four short lines of thread, representation and head-style fact.
"""

from __future__ import annotations

import importlib
import inspect
import re
from pathlib import Path

import _config
from _common import part_properties, save_part_and_images
from _drawing_registry import DRAWINGS_BY_NAME


FASTENER_SPECS = {
    "bracket-screw": "bracket_screw_spec",
    "clamp-screw": "clamp_screw_spec",
    "cone-pivot-screw": "cone_pivot_screw_spec",
    "cone-tip-pinch-screw": "cone_tip_pinch_screw_spec",
    "fillister-screw": "fillister_screw_spec",
    "foot-screw": "foot_screw_spec",
    "frame-side-screw": "frame_side_screw_spec",
    "gooseneck-set-screw": "gooseneck_set_screw_spec",
    "hanger-screw": "hanger_screw_spec",
    "knife-hanger-stud": "knife_hanger_stud_spec",
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
    "frame_side_screw_spec": "build_frame_side_screw",
    "lag_screw_spec": "build_lag_screw",
    "slotted_screw_spec": "build_slotted_screw",
}

# The only roughness symbol in the group: the cone pivot screw's ground
# shoulder is the pivot's running surface (policy rule 5).
GROUND_SHOULDER_SHEET = "cone-pivot-screw"

GDT_HELPERS = (
    "add_datum_feature(",
    "add_feature_control_frame(",
    "set_basic_dimension(",
    "project_part_pmi(",
)

# Phrases that belong to the title block, a dimension band or a deleted
# feature-control frame -- never to a fastener note (policy rules 1, 2, 3, 6).
BANNED_NOTE_PHRASES = (
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
    "TITLE-BLOCK",
    "TITLE BLOCK",
    "+/-",
    "PERPENDICULAR",
    "RUNOUT",
    "WITHIN",
    "DATUM",
    "FCF",
    "PITCH-DIAMETER",
    "ASME B1.",
    "SYSTEM 21",
    "B18",
    "MHA-",
    "DO NOT APPLY",
)


def _drawing_source(part_name: str) -> str:
    drawing = DRAWINGS_BY_NAME[part_name.replace("-", "_")]
    return drawing.script.read_text(encoding="utf-8")


def test_title_block_uses_the_exact_material_grade_and_finish() -> None:
    for part_name in FASTENER_SPECS:
        config = _config.parts(part_name)
        assert config["material"] == config["material_specification"], part_name
        assert config["finish"].strip(), part_name


def test_flat_end_pinch_screw_uses_noncontradictory_title_block_identity() -> None:
    assert part_properties("cone-tip-pinch-screw")["Title"] == "Flat-End Pinch Screw"
    source = inspect.getsource(save_part_and_images)
    assert 'apply_summary_info(adapter, title=properties["Title"])' in source


def test_notes_carry_the_thread_and_head_facts_a_machinist_cannot_see() -> None:
    for part_name, module_name in FASTENER_SPECS.items():
        spec = importlib.import_module(module_name)
        notes = "\n".join((spec.DRAWING_NOTES, spec.END_VIEW_NOTE)).upper()

        # The thread designation rides the VIEW as a leader to the shank
        # (_fastener_annotations.add_thread_leader, blind review 2026-09-02),
        # so the notes carry the thread-to-head fact without repeating it;
        # the old "THREAD NOT MODELED" CAD commentary is gone (policy rule 6).
        source = _drawing_source(part_name)
        assert (
            "add_thread_leader(" in source or "label_shank_thread(" in source
        ), part_name
        assert "THREAD NOT MODELED" not in spec.DRAWING_NOTES, part_name
        # The note says WHERE the thread runs: to the head/knob on the
        # through-threaded screws, on the tail/lower end only on the pivot
        # screw and the hanger stud.
        assert re.search(r"THREADED (TO THE|ON THE)|THREAD IS ON|GROUND TO SIZE", spec.DRAWING_NOTES), part_name
        assert "HEAD" in notes or "KNOB" in notes or "HEX" in notes, part_name
        assert re.search(r"\b(?:MM|MILLIMET(?:ER|RE)S?)\b", notes) is None, (
            part_name,
            "unit suffix",
        )


def test_notes_are_few_short_and_never_the_title_block_or_a_frame() -> None:
    # policy rule 6: at most four short lines of part-specific process fact.
    for part_name, module_name in FASTENER_SPECS.items():
        spec = importlib.import_module(module_name)
        lines = spec.DRAWING_NOTES.split("\n")
        assert 1 <= len(lines) <= 4, (part_name, len(lines))
        assert max(map(len, lines)) < 80, (part_name, max(map(len, lines)))
        assert all(line.endswith(".") for line in lines), part_name
        notes = spec.DRAWING_NOTES.upper()
        for banned in BANNED_NOTE_PHRASES:
            assert banned not in notes, (part_name, banned)


def test_sheets_carry_no_datums_frames_or_basic_dimensions() -> None:
    # policy rule 3: screws and studs are off the GD&T allowlist, so no sheet
    # in the group places a datum, a frame or a boxed dimension, and no spec
    # keeps a GD&T mapping behind them.
    for part_name, module_name in FASTENER_SPECS.items():
        source = _drawing_source(part_name)
        for helper in GDT_HELPERS:
            assert helper not in source, (part_name, helper)
        spec = importlib.import_module(module_name)
        assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM"), part_name
        assert not hasattr(spec, "GEOMETRIC_CONTROLS"), part_name
        assert not hasattr(spec, "PART_DATUMS"), part_name


def test_only_the_ground_pivot_shoulder_carries_a_roughness_symbol() -> None:
    # policy rule 5: a screw shoulder that merely seats is covered by the
    # block Ra; the cone pivot shoulder RUNS in the swing plate, so it keeps
    # exactly one GROUND symbol.
    for part_name, module_name in FASTENER_SPECS.items():
        source = _drawing_source(part_name)
        spec = importlib.import_module(module_name)
        expected = 1 if part_name == GROUND_SHOULDER_SHEET else 0
        assert source.count("add_surface_finish(") == expected, part_name
        if expected == 0:
            assert not hasattr(spec, "SURFACE_FINISHES"), part_name
            continue
        assert len(spec.SURFACE_FINISHES) == 1
        assert spec.SURFACE_FINISHES[0].key == "ground_shoulder"


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

        # The slot size is a marked model dimension on the side view now
        # (SlotWidth / SlotDepth), not a note line; the note keeps the
        # orientation fact only.
        assert "SLOT" in spec.DRAWING_NOTES.upper(), spec_name
        assert f"{spec.SLOT_W:.2f} WIDE" not in spec.DRAWING_NOTES, spec_name
        drawing_source = _drawing_source(spec_name.removesuffix("_spec").replace("_", "-"))
        assert '"SlotWidth"' in drawing_source and '"SlotDepth"' in drawing_source, spec_name
        if build_name in {"build_bracket_screw", "build_clamp_screw"}:
            assert "slot_width=SLOT_W" in source
            assert "slot_depth=SLOT_D" in source
            continue
        assert "width_mm=SLOT_W" in source
        assert "depth_mm=SLOT_D" in source
