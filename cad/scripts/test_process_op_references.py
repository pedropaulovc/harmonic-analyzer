"""Every printed "Op <n>" in a traveler plan names an operation that exists.

prechips numbers a plan's operations by tens in plan order, across all its
setups: the first ``[[setups.operations]]`` is Op 10, the next Op 20, and so
on. A reference typed into printed text ("as Op 200's Stop says", "Ops
110–160") does not move when an operation is inserted or removed above it, so
an edit that shifts the numbering can leave it naming a missing operation.
This test catches a reference past the plan's last operation or off the tens;
a plan whose references must also name the right operation pins each one to
its target's text in its own process test (test_ms_stick_process).
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Iterator

import pytest

import _process_plans

# "Op 270", "op 40", "Ops 320–330", "Ops 40, 90, 100 and 110", "Ops 90–210 and
# 260–300", "Ops 20 to 60": every number after the word resolves (a range by
# both its ends).
OP_REFERENCE = re.compile(
    r"\bops?\s+\d+(?:(?:\s*[–—-]\s*|\s*,\s*|\s+(?:and|to|through)\s+)\d+)*",
    re.IGNORECASE,
)


def op_numbers(plan: dict) -> dict[int, dict]:
    """Op number -> the operation prechips prints under it."""
    ops = [op for setup in plan.get("setups", []) for op in setup.get("operations", [])]
    return {10 * (i + 1): op for i, op in enumerate(ops)}


def printed_references(plan: dict) -> Iterator[tuple[str, int, str]]:
    """(where, op number, the reference's text) for each printed reference."""

    def walk(value: object, where: str) -> Iterator[tuple[str, str]]:
        if isinstance(value, str):
            yield where, value
        elif isinstance(value, dict):
            for key, item in value.items():
                yield from walk(item, f"{where}.{key}")
        elif isinstance(value, list):
            for i, item in enumerate(value):
                yield from walk(item, f"{where}[{i}]")

    for where, text in walk(plan, "plan"):
        for match in OP_REFERENCE.finditer(text):
            for number in re.findall(r"\d+", match.group(0)):
                yield where, int(number), match.group(0)


def broken_references(plan: dict) -> list[str]:
    ops = op_numbers(plan)
    return [
        f"{where}: {text} names Op {number}, not one of the plan's Op 10–{max(ops, default=0)}"
        for where, number, text in printed_references(plan)
        if number not in ops
    ]


@pytest.mark.parametrize("stem", _process_plans.TRAVELER_STEMS)
def test_every_printed_op_reference_names_an_operation(stem: str) -> None:
    plan = tomllib.loads(_process_plans.plan_path(stem).read_text(encoding="utf-8"))
    assert broken_references(plan) == []


def test_a_reference_past_the_last_operation_is_caught() -> None:
    plan = {
        "setups": [
            {
                "operations": [
                    {"instruction": "Mic it."},
                    {"instruction": "As Op 10 says."},
                ]
            },
            {
                "operations": [
                    {
                        "instruction": "Redo Ops 10–30, then op 25; see Ops 20, 30 and 40."
                    }
                ]
            },
        ]
    }
    assert sorted(n for _, n, _ in printed_references(plan)) == [
        10,
        10,
        20,
        25,
        30,
        30,
        40,
    ]
    where = "plan.setups[1].operations[0].instruction"
    assert broken_references(plan) == [
        f"{where}: op 25 names Op 25, not one of the plan's Op 10–30",
        f"{where}: Ops 20, 30 and 40 names Op 40, not one of the plan's Op 10–30",
    ]
