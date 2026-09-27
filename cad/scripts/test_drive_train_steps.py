"""The step registry matches the numbers MHA-A03 prints (SolidWorks-free)."""

from __future__ import annotations

import re

import cone_tip_shim_spec as shim
import draw_drive_train_assembly as drawing
import drive_train_steps as steps
import pytest

SEQUENCE_BLOCKS = (drawing.CONE_CRANK_STEPS, drawing.BANK_STEPS, drawing.RIG_STEPS)
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


def test_the_cone_gear_joint_prints_in_the_step_that_bonds_the_gears() -> None:
    """#834 (rule 6) took the MHA-013 joining method off every cone gear sheet,
    so the step that bonds the gears states it, and the adhesive note sends
    the fitter to that step, not to a print that no longer carries it."""
    import cone_gear_notes
    import cone_gear_spec

    joint = cone_gear_notes.ATTACHMENT
    for teeth in cone_gear_spec.CONFIGURATION_TEETH:
        assert joint not in cone_gear_notes.drawing_notes(teeth)
        assert joint not in cone_gear_notes.gear_data(teeth)
    body = _step_body("cone-gears-bonded")
    assert "MHA-013" in body and joint in body
    adhesive = next(
        line
        for line in drawing.CONSUMABLES_NOTES.splitlines()
        if line.startswith("ADHESIVE:")
    )
    assert "MHA-013" in adhesive
    assert f"STEP {steps.step_number('cone-gears-bonded')}" in adhesive
    assert "PRINT" not in adhesive


def test_a_cite_to_the_wrong_step_is_caught() -> None:
    """Positive control: step 18 locates the rig but does not set the gap."""
    assert "2.5 FEELER" not in _step_body("rig-located")


def _cited_keys(notes: str) -> list[str]:
    """The registry keys of every MHA-A03 step pointer printed in ``notes``."""
    return [steps.SEQUENCE[int(n) - 1] for n in POINTER.findall(notes)]


def test_the_shim_sheet_points_at_the_step_that_fits_the_shim_pack() -> None:
    """Codex P2 on #857: MHA-141 dropped its leaf-fitting note for MHA-A03's
    fit-up step, so its sheet must carry a generated pointer to that step."""
    cited = _cited_keys(shim.MANUFACTURING_NOTES)
    assert cited == [key for key in steps.SEQUENCE if "MHA-141" in _step_body(key)]
    assert len(cited) == 1
    assert "SHIM" in _step_body(cited[0])


def test_a_pointer_to_a_step_that_never_names_the_part_is_caught() -> None:
    """Positive control: step 3 sets the adjuster, not the shim pack."""
    assert _cited_keys(f"SEE {steps.step_ref('tip-adjuster-set')}.") == [
        "tip-adjuster-set"
    ]
    assert "MHA-141" not in _step_body("tip-adjuster-set")
