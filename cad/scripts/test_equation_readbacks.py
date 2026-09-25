"""Replay logged set_global readbacks through the #889 gate. SolidWorks-free.

test_data/equation_readbacks.json holds every distinct readback the pre-#889
leaf logs recorded. The gate must accept all of them except the one the
2-place angular template rounded (ConeIncline = 12.5182deg -> 12.52), which it
must flag in every run that wrote it. This is the positive control for both the
evaluator (it reads every logged expression) and the tolerance (it separates
8-place rounding from the defect).
"""

from __future__ import annotations

import json
from pathlib import Path

import _common
import _equation_eval as ev

FIXTURE = Path(__file__).resolve().parent / "test_data" / "equation_readbacks.json"
INCHES = ev.DocumentUnits.from_length_unit(3)


def _replay() -> tuple[int, list[tuple[str, str, str]]]:
    checked = 0
    flagged: list[tuple[str, str, str]] = []
    for run in json.loads(FIXTURE.read_text(encoding="utf-8"))["runs"]:
        # References resolve through stored values, as _common.set_global does.
        held: dict[str, float] = {}
        for name, expression, stored in run["readbacks"]:
            intended = ev.evaluate(expression, held.__getitem__, INCHES)
            held[name] = stored
            checked += 1
            if abs(stored - intended) > _common.readback_tolerance(expression, intended):
                flagged.append((run["source"], name, expression))
    return checked, flagged


def test_the_gate_flags_only_the_rounded_angle() -> None:
    checked, flagged = _replay()
    assert checked == 281
    assert {(name, expression) for _, name, expression in flagged} == {
        ("ConeIncline", "12.5182deg")
    }
    assert len(flagged) == 3  # every cone-pivot-post run in the corpus
