"""Offline contract for the channel assembly drawing (MHA-A02)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import channel_assembly_steps as steps
import draw_channel_assembly as drawing
import pytest
import rocker_bank_layout as bank
from _drawing_registry import DRAWINGS_BY_NAME

STEP_HEAD = re.compile(r"^(\d+)\. ", re.MULTILINE)
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
    assert steps.FITUP_DRAWING_NUMBER in _step_body("north-ear-datum")
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
