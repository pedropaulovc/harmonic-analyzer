"""The step registry matches the numbers MHA-A03 prints (SolidWorks-free)."""

from __future__ import annotations

import re

import cone_gear_stack
import cone_stack_end_play
import draw_cone_tip_shim as shim
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
POINTER = re.compile(rf"{re.escape(steps.DRAWING_NUMBER)} STEP (\d+)\b")


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


def test_the_cone_stack_step_prints_measured_limits_and_feeler() -> None:
    """The fitter accepts the touching gear stack before setting the tip gap."""
    low, high = cone_gear_stack.STACK_L20_ACCEPT
    stack = _step_body("cone-gears-stacked")
    fitup = _step_body("post-and-tip-block")
    assert "MHA-021" in stack and "MHA-013" in stack
    assert "T120 FIRST THROUGH T006" in stack
    assert "EACH FLAT TO FLAT AND AGAINST THE LAST" in stack
    assert f"{low:.3f}-{high:.3f}" in stack
    assert "RE-FACE A LONG STACK" in stack
    assert "REMAKE THE THINNEST GEAR OF A SHORT ONE" in stack
    assert f"{cone_stack_end_play.TIP_BLOCK_FEELER:.2f} FEELER ON MHA-096" in fitup
    assert "IT NIPS; SNUG MHA-140" in fitup


def test_the_printed_shaft_end_play_keeps_the_bushing_off_the_tip_block() -> None:
    """Codex P1 on #1128: the collar carries the stack north by MHA-014's end
    play, so the printed top spends the stack's float.  At the tightest feeler
    setting the bushing must still run MIN_END_PLAY off the block."""
    match = re.search(r"END PLAY (\d+\.\d+)-(\d+\.\d+)", _step_body("tip-adjuster-set"))
    assert match is not None
    low, high = (float(value) for value in match.groups())
    assert 0.0 < low < high
    running = cone_stack_end_play.STACK_FLOAT[0] - high
    assert running >= cone_stack_end_play.MIN_END_PLAY - 1e-9, running


def test_a_cite_to_the_wrong_step_is_caught() -> None:
    """Positive control: RIG SET sets the rig along the bank, not its tip gap."""
    assert TIP_GAP_FEELER not in _step_body("rig-set")


def _cited_keys(notes: str) -> list[str]:
    """The registry keys of every MHA-A03 step pointer printed in ``notes``."""
    return [steps.SEQUENCE[int(n) - 1] for n in POINTER.findall(notes)]


def test_the_shim_sheet_points_at_the_step_that_fits_the_shim_pack() -> None:
    """Codex P2 on #857: MHA-141 dropped its leaf-fitting note for MHA-A03's
    fit-up step, so its sheet must carry a generated pointer to that step."""
    cited = _cited_keys(shim.PRINTED_MANUFACTURING_NOTE)
    assert cited == [key for key in steps.SEQUENCE if "MHA-141" in _step_body(key)]
    assert len(cited) == 1
    assert "SHIM" in _step_body(cited[0])


def test_a_pointer_to_a_step_that_never_names_the_part_is_caught() -> None:
    """Positive control: step 3 sets the adjuster, not the shim pack."""
    assert _cited_keys(f"SEE {steps.step_ref('tip-adjuster-set')}.") == [
        "tip-adjuster-set"
    ]
    assert "MHA-141" not in _step_body("tip-adjuster-set")
