"""The step registry matches the numbers MHA-A03 prints (SolidWorks-free)."""

from __future__ import annotations

import re

import cone_gear_stack
import cone_stack_end_play
import draw_drive_train_assembly as drawing
import drive_train_steps as steps
import pinion_rig_tip_gap as tip_gap
import pytest

SEQUENCE_BLOCKS = (
    drawing.CONE_CRANK_STEPS,
    drawing.BANK_STEPS,
    drawing.rig_steps(pivot_blocks=2, cams=2, slotted=4),
)
TIP_GAP_FEELER = f"{tip_gap.TIP_GAP_FEELER:.2f} FEELER"
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
        assert steps.step_ref(key) == f"MHA-A03 STEP {index}"
    with pytest.raises(KeyError):
        steps.step_number("no-such-step")


@pytest.mark.parametrize(
    ("text", "key", "phrase"),
    (
        (drawing.CHECKS, "rig-located", TIP_GAP_FEELER),
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


def test_the_cone_stack_step_prints_measured_limits() -> None:
    """The fitter accepts the touching gear stack before setting the tip."""
    low, high = cone_gear_stack.STACK_L20_ACCEPT
    stack = _step_body("cone-gears-stacked")
    assert "MHA-021" in stack and "MHA-013" in stack
    assert "T120 FIRST THROUGH T006" in stack
    assert "EACH FLAT TO FLAT AND AGAINST THE LAST" in stack
    assert f"{low:.3f}-{high:.3f}" in stack
    assert "RE-FACE A LONG STACK" in stack
    assert "REMAKE THE THINNEST GEAR OF A SHORT ONE" in stack


def test_the_tip_step_sets_the_collar_before_the_end_play() -> None:
    """User ruling 2026-09-29: the collar is set to T006 over the feeler and
    locked first, so the stack's float is fixed on the shaft before the cup
    screw sets MHA-014's end play and the pinch screw locks it."""
    fitup = _step_body("tip-adjuster-set")
    order = (
        f"PUSH MHA-096 ONTO A {cone_stack_end_play.COLLAR_FEELER:.2f} FEELER ON T006",
        "LOCK ITS SET SCREW",
        "THREAD MHA-097 INTO MHA-092",
        "TIGHTEN MHA-098",
    )
    positions = [fitup.find(phrase) for phrase in order]
    assert -1 not in positions, positions
    assert positions == sorted(positions)
    # The block is placed by its hold-down alone: nothing is set against it.
    placed = _step_body("post-and-tip-block")
    assert "MHA-140 UP FROM UNDER THE PLATE" in placed
    assert "FEELER" not in placed


def test_the_printed_shaft_end_play_is_the_band_the_stacks_book() -> None:
    """The collar-to-block air and the adjuster's embed window book
    cone_stack_end_play.SHAFT_END_PLAY; the sheet prints exactly that band."""
    match = re.search(r"END PLAY (\d+\.\d+)-(\d+\.\d+)", _step_body("tip-adjuster-set"))
    assert match is not None
    printed = tuple(float(value) for value in match.groups())
    assert printed == cone_stack_end_play.SHAFT_END_PLAY
    assert 0.0 < printed[0] < printed[1]


def test_a_cite_to_the_wrong_step_is_caught() -> None:
    """Positive control: RIG SET sets the rig along the bank, not its tip gap."""
    assert TIP_GAP_FEELER not in _step_body("rig-set")



