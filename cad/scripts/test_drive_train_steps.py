"""The step registry matches the numbers MHA-A03 prints (SolidWorks-free)."""

from __future__ import annotations

import re

import draw_drive_train_assembly as drawing
import drive_train_steps as steps
import pytest

SEQUENCE_BLOCKS = (drawing.CONE_CRANK_STEPS, drawing.BANK_STEPS, drawing.RIG_STEPS)
STEP_HEAD = re.compile(r"^\s*(\d+)\. ", re.MULTILINE)


def _step_body(key: str) -> str:
    """The printed text of one step, from its head to the next head."""
    text = "\n".join(SEQUENCE_BLOCKS)
    heads = list(STEP_HEAD.finditer(text))
    number = steps.step_number(key)
    index = next(i for i, head in enumerate(heads) if int(head.group(1)) == number)
    end = heads[index + 1].start() if index + 1 < len(heads) else len(text)
    return " ".join(text[heads[index].end() : end].split())


def test_the_printed_step_heads_are_the_registry_in_order() -> None:
    printed = [int(n) for block in SEQUENCE_BLOCKS for n in STEP_HEAD.findall(block)]
    assert printed == list(range(1, len(steps.SEQUENCE) + 1))


def test_a_key_resolves_to_its_position_and_prints_a_pointer() -> None:
    for index, key in enumerate(steps.SEQUENCE, start=1):
        assert steps.step_number(key) == index
    assert steps.step_ref("rig-tip-gap-set") == "MHA-A03 STEP 19"
    with pytest.raises(KeyError):
        steps.step_number("no-such-step")


@pytest.mark.parametrize(
    ("text", "key", "phrase"),
    (
        (drawing.CHECKS, "rig-tip-gap-set", "2.5 FEELER"),
        (drawing.CONSUMABLES_NOTES, "crank-handle-fitted", "LOCTITE 222"),
    ),
)
def test_each_typed_step_cite_names_the_step_that_does_it(
    text: str, key: str, phrase: str
) -> None:
    """Until the drawing's cites read the registry, each typed "STEP n" must
    be the step that sets the condition it points at."""
    assert f"STEP {steps.step_number(key)})" in " ".join(text.split())
    assert phrase in _step_body(key)


def test_a_cite_to_the_wrong_step_is_caught() -> None:
    """Positive control: step 18 locates the rig but does not set the gap."""
    assert "2.5 FEELER" not in _step_body("rig-located")
