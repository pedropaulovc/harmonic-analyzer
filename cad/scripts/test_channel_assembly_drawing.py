"""Offline contract for the channel assembly drawing (MHA-A02)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import _config
import channel_assembly_steps as steps
import draw_channel_assembly as drawing
import pytest
import rocker_bank_layout as bank
from _drawing_registry import DRAWINGS_BY_NAME

STEP_HEAD = re.compile(r"^(\d+)\. ", re.MULTILINE)
# A drive-train or frame sequence head, sub-steps included ("9G. ").
ANY_STEP_HEAD = re.compile(r"^(\d+[A-Z]?)\. ", re.MULTILINE)
STEP_POINTER = re.compile(r"(MHA-A\d{2}) STEP (\d+[A-Z]?)")
# Default-format note text, measured on r743-rocker-fix3's render (leaf
# 20260926T112244Z-1-a884759d); #945 moves these into _drawing_common.
NOTE_CHAR_WIDTH = 0.00276
NOTE_LINE_PITCH = 0.0045


def _step_body(key: str) -> str:
    """The printed text of one step, from its head to the next head."""
    text = drawing.FITUP_STEPS
    heads = list(STEP_HEAD.finditer(text))
    index = steps.step_number(key) - 1
    end = heads[index + 1].start() if index + 1 < len(heads) else len(text)
    return " ".join(text[heads[index].end() : end].split())


def _sequence_steps(text: str) -> dict[str, str]:
    """Every step of a printed sequence: its head label to its joined text."""
    heads = list(ANY_STEP_HEAD.finditer(text))
    bodies = {}
    for index, head in enumerate(heads):
        end = heads[index + 1].start() if index + 1 < len(heads) else len(text)
        assert head.group(1) not in bodies, f"step {head.group(1)} printed twice"
        bodies[head.group(1)] = " ".join(text[head.end() : end].split())
    return bodies


def _literal_number(script: str, key: str) -> str:
    """The drawing number a build script stamps into its Number property."""
    path = Path(drawing.__file__).with_name(script)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values = {
        node.values[index].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Dict)
        for index, item in enumerate(node.keys)
        if isinstance(item, ast.Constant) and item.value == key
    }
    (value,) = values
    return value


def test_channel_assembly_keeps_registry_outputs_and_precomputed_placement() -> None:
    spec = DRAWINGS_BY_NAME["channel_assembly"]
    assert spec.source_kind == "assembly"
    assert spec.part == "channel"
    assert drawing.SOURCE == spec.source
    assert drawing.OUTPUTS == drawing.OUTPUTS.__class__(
        spec.outputs["slddrw"], spec.outputs["pdf"], spec.outputs["png"]
    )
    assert drawing.SHEET_SCALE == (1.0, 7.0)
    assert drawing.FRONT_CENTER == (0.060, 0.150)
    assert drawing.RIGHT_CENTER == (0.130, 0.150)
    assert drawing.ISO_CENTER == (0.225, 0.140)


def test_the_step_registry_names_this_sheet_and_the_fitup_sheet() -> None:
    assert steps.DRAWING_NUMBER == _literal_number(
        "build_channel_assembly.py", "Number"
    )
    assert steps.FITUP_DRAWING_NUMBER == _literal_number(
        "build_drive_train_assembly.py", "Number"
    )
    for index, key in enumerate(steps.SEQUENCE, start=1):
        assert steps.step_number(key) == index
    assert steps.step_ref("south-bracket-feeler-set") == "MHA-A02 STEP 4"
    with pytest.raises(KeyError):
        steps.step_number("no-such-step")


def test_every_cross_sheet_step_pointer_lands_on_the_step_it_names() -> None:
    """Codex #936 (PRRT_kwDOPHDy386mRlAE): step 2 sent the fitter to an A03
    step that did not exist. The user ruled option A: A03 step 9G sets the
    north bracket by DRO, after MHA-A04 step 8 has screwed the support down.
    Each pointer must land on a printed step that does what it cites."""
    import draw_drive_train_assembly as drive_train
    import draw_frame_assembly as frame

    bracket = _config.parts("pivot-bracket")["number"]
    support = _config.parts("rocker-arm-support")["number"]
    sheets = {
        steps.DRAWING_NUMBER: _sequence_steps(drawing.FITUP_STEPS),
        steps.FITUP_DRAWING_NUMBER: _sequence_steps(
            "\n".join(
                (drive_train.CONE_CRANK_STEPS, drive_train.BANK_STEPS, drive_train.RIG_STEPS)
            )
        ),
        _literal_number("build_frame_assembly.py", "Number"): _sequence_steps(
            frame.ASSEMBLY_STEPS
        ),
    }
    # What each pointer's target must name, keyed by (citing sheet, pointer).
    expected = {
        (steps.DRAWING_NUMBER, steps.NORTH_BRACKET_SET_REF): f"THE NORTH {bracket}",
        (steps.FITUP_DRAWING_NUMBER, "MHA-A04 STEP 8"): f"{support} ON DECK",
    }
    found = set()
    for sheet, bodies in sheets.items():
        for body in bodies.values():
            for pointer in STEP_POINTER.finditer(body):
                found.add((sheet, pointer.group(0)))
                target = sheets[pointer.group(1)][pointer.group(2)]
                assert expected[(sheet, pointer.group(0))] in target, pointer.group(0)
    assert found == set(expected)
    north = sheets[steps.FITUP_DRAWING_NUMBER][steps.NORTH_BRACKET_SET_STEP]
    assert "EAR INNER FACE TO Y" in north and "DRO STILL ZEROED AS 9A" in north
    # Positive control: the step before it is the bank's end play, not the ear.
    assert f"NORTH {bracket}" not in sheets[steps.FITUP_DRAWING_NUMBER]["9F"]
    # 9G follows 9F on the bank sheet, before the rig continuation line.
    labels = list(sheets[steps.FITUP_DRAWING_NUMBER])
    assert labels.index(steps.NORTH_BRACKET_SET_STEP) == labels.index("9F") + 1


def test_the_printed_step_heads_are_the_registry_in_order() -> None:
    printed = [int(n) for n in STEP_HEAD.findall(drawing.FITUP_STEPS)]
    assert printed == list(range(1, len(steps.SEQUENCE) + 1))


def test_the_feeler_set_and_its_acceptance_are_printed_from_the_layout() -> None:
    """Codex #936 (PRRT_kwDOPHDy386mRSOK): the south bracket's feeler and the
    end play it leaves lived only in rocker_bank_layout. Rule 6: the channel
    assembly's steps carry both, generated from the layout, never typed."""
    feeler = _step_body("south-bracket-feeler-set")
    assert f"{bank.ROCKER_END_FEELER:.2f} FEELER" in feeler
    accept = _step_body("end-play-accepted")
    low, high = bank.ROCKER_END_PLAY
    assert f"{low:.2f} TO {high:.2f}" in accept
    assert f"STEP {steps.step_number('south-bracket-feeler-set')}" in accept
    stack = _step_body("rocker-stack-accepted")
    assert f"{bank.STACK_L20_ACCEPT[0]:.2f} TO {bank.STACK_L20_ACCEPT[1]:.2f}" in stack
    assert steps.NORTH_BRACKET_SET_REF in _step_body("north-ear-datum")
    # Positive control: the feeler is not what step 3 sets.
    assert "FEELER" not in _step_body("south-washer-fitted")


def test_no_fitup_value_is_typed_into_the_drawing() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    values = (
        bank.ROCKER_END_FEELER,
        *bank.ROCKER_END_PLAY,
        *bank.STACK_L20_ACCEPT,
    )
    for value in values:
        assert f"{value:.2f}" not in source, value
    assert not re.search(r"STEP \d", source)
    assert not re.search(r"MHA-\d{3}", source)


def test_the_step_block_fits_the_field_right_of_the_isometric() -> None:
    left, top = drawing.FITUP_NOTE_XY
    right_limit, bottom_limit = drawing.FITUP_FIELD_LIMIT
    lines = drawing.FITUP_STEPS.splitlines()
    assert left + max(map(len, lines)) * NOTE_CHAR_WIDTH < right_limit
    assert top - len(lines) * NOTE_LINE_PITCH > bottom_limit
    # The isometric's right edge sat at x ~0.248 on the v36 render.
    assert left > 0.248 + 0.015


def test_the_shaft_supplied_long_is_cut_to_fit_before_the_end_play_is_accepted() -> None:
    """Codex #936 (PRRT_kwDOPHDy386mSteE): MHA-065 is supplied long with its
    plain end uncut, and its print defers the length to the assembly, but no
    step cut it. A step between the south bracket's setting and the end-play
    acceptance must scribe the shaft at the ear, take it out, and cut and dome
    it to the layout's band."""
    import pivot_shaft_spec as shaft

    # The part's promise this sheet has to keep.
    assert "PLAIN END UNCUT" in shaft.DRAWING_NOTES
    assert shaft.LENGTH_CALLOUT.startswith("CUT TO FIT")
    cut_steps = [key for key in steps.SEQUENCE if "PLAIN END" in _step_body(key)]
    assert len(cut_steps) == 1
    (key,) = cut_steps
    number = steps.step_number(key)
    assert steps.step_number("south-bracket-feeler-set") < number
    assert number < steps.step_number("end-play-accepted")
    body = _step_body(key)
    upper, lower = bank.PLAIN_END_CUT_BAND
    cut = f"{shaft.DOME_HEIGHT + lower:.1f} TO {shaft.DOME_HEIGHT + upper:.1f}"
    assert f"CUT THE PLAIN END {cut} PAST THE SCRIBE" in body
    assert f"DOME IT {shaft.DOME_HEIGHT:.1f}" in body
    assert "SCRIBE" in body.split("CUT")[0] and "SOUTH EAR'S OUTER FACE" in body
    # It comes out only with the south bracket off, and goes back at the feeler.
    assert "UNSCREW THE SOUTH" in body
    assert f"AT THE FEELER AS STEP {steps.step_number('south-bracket-feeler-set')}" in body
    # Positive control: no other step mentions the cut.
    assert "SCRIBE" not in _step_body("south-bracket-feeler-set")
