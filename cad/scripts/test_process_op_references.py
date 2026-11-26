"""Every printed "Op <n>" in a traveler plan names an operation that exists.

prechips numbers a plan's operations by tens in plan order, across all its
setups: the first ``[[setups.operations]]`` is Op 10, the next Op 20, and so
on. A reference typed into printed text ("as Op 200's Stop says", "Ops
110–160") does not move when an operation is inserted or removed above it, so
an edit that shifts the numbering can leave it naming a missing operation.
This test catches a reference past the plan's last operation or off the tens;
a plan whose references must also name the right operation pins each one to
its target's text in its own process test (test_ms_stick_process).

Setup pictures and operation pictures (``diagram = { file, alt }``) carry
the same references in their SVG text and alt, and a conversion that
renumbered a plan's operations left picture titles naming another operation
(#3684's round 3). So for every picture: each "Op <n>" in its SVG text names
an operation that exists (its alt is plan text, checked above); a title or
alt that opens with "Op <n>" / "Setup <n>" names the picture's own operation
or setup (a setup picture's own operations are its setup's); "as Op <n>'s
picture" names an operation that has a picture; and a tool its title names
(``T4``) is one its own operation's instruction loads.
"""

from __future__ import annotations

import re
import tomllib
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path

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


SETUP_REFERENCE = re.compile(
    r"\bsetups?\s+\d+(?:(?:\s*[–—-]\s*|\s*,\s*|\s+(?:and|to|through)\s+)\d+)*",
    re.IGNORECASE,
)
# "As Op 80's picture", "as Setup 5's picture".
PICTURE_REFERENCE = re.compile(r"\b(op|setup)\s+(\d+)['’]s picture", re.IGNORECASE)
TOOL = re.compile(r"\bT(\d+)\b")
_SVG = "{http://www.w3.org/2000/svg}"


def _named(reference: str, step: int) -> list[int]:
    """The numbers a reference names; a range ("Ops 140–160") names every one."""
    numbers = [int(n) for n in re.findall(r"\d+", reference)]
    if len(numbers) == 2 and re.search(r"[–—-]|\bto\b|\bthrough\b", reference):
        return list(range(numbers[0], numbers[1] + step, step))
    return numbers


def pictures(plan: dict) -> Iterator[tuple[int, int | None, list[int], dict]]:
    """(setup number, its op number or None for a setup picture, the setup's
    op numbers, the diagram) for each picture."""
    number = 0
    for index, setup in enumerate(plan.get("setups", []), 1):
        operations = setup.get("operations", [])
        own = [number + 10 * (i + 1) for i in range(len(operations))]
        if "diagram" in setup:
            yield index, None, own, setup["diagram"]
        for op_number, op in zip(own, operations, strict=True):
            if "diagram" in op:
                yield index, op_number, own, op["diagram"]
        number += 10 * len(operations)


def picture_texts(plan_dir: Path, diagram: dict) -> list[tuple[str, str]]:
    """("title" | "text" | "alt", the text) for a picture's SVG text and alt."""
    root = ET.parse(plan_dir / diagram["file"]).getroot()
    texts = [
        ("title" if "title" in (t.get("class") or "").split() else "text", "".join(t.itertext()))
        for t in root.iter(f"{_SVG}text")
    ]
    return [*texts, ("alt", diagram.get("alt", ""))]


def _opening(text: str) -> list[tuple[str, str]]:
    """The references a title or alt opens with: "Op 80 (…)", "Setup 4, Op 150: …"."""
    out = []
    rest = text.lstrip()
    for _ in range(2):
        match = SETUP_REFERENCE.match(rest) or OP_REFERENCE.match(rest)
        if not match:
            break
        out.append(("Setup" if match.re is SETUP_REFERENCE else "Op", match.group(0)))
        rest = rest[match.end():].lstrip(" ,")
    return out


def picture_problems(plan_dir: Path, plan: dict) -> list[str]:
    ops = op_numbers(plan)
    pictured = list(pictures(plan))
    pictured_ops = {op for _, op, _, _ in pictured if op is not None}
    pictured_setups = {setup for setup, op, _, _ in pictured if op is None}
    found = []
    for setup, own_op, setup_ops, diagram in pictured:
        name = f"{diagram['file']} (Setup {setup}{f', Op {own_op}' if own_op else ''})"
        for where, text in picture_texts(plan_dir, diagram):
            if where != "alt":
                found += [
                    f"{name} {where}: {m.group(0)} names Op {n}, not one of the plan's "
                    f"Op 10–{max(ops, default=0)}"
                    for m in OP_REFERENCE.finditer(text)
                    for n in map(int, re.findall(r"\d+", m.group(0)))
                    if n not in ops
                ]
            if where in ("title", "alt"):
                for kind, reference in _opening(text):
                    if kind == "Setup" and setup not in _named(reference, 1):
                        found.append(f"{name} {where} opens with {reference!r}, not its own Setup {setup}")
                    if kind == "Op":
                        named = _named(reference, 10)
                        if own_op is not None and own_op not in named:
                            found.append(f"{name} {where} opens with {reference!r}, not its own Op {own_op}")
                        if own_op is None and not all(n in setup_ops for n in named):
                            found.append(
                                f"{name} {where} opens with {reference!r}, outside its setup's "
                                f"Ops {setup_ops[0]}–{setup_ops[-1]}"
                            )
            for kind, number in PICTURE_REFERENCE.findall(text):
                op = kind.lower() == "op"
                target, have = (pictured_ops, "an operation") if op else (pictured_setups, "a setup")
                if int(number) not in target:
                    found.append(f"{name} {where}: '{kind} {number}'s picture' names {have} without one")
                if int(number) == (own_op if op else (setup if own_op is None else None)):
                    found.append(f"{name} {where}: '{kind} {number}'s picture' names this picture")
            if where == "title" and own_op is not None:
                loaded = set(TOOL.findall(ops[own_op].get("instruction", "")))
                found += [
                    f"{name} title names T{tool}; its Op {own_op} loads "
                    f"{', '.join(f'T{t}' for t in sorted(loaded)) or 'no tool'}"
                    for tool in TOOL.findall(text)
                    if tool not in loaded
                ]
    return found


@pytest.mark.parametrize("stem", _process_plans.TRAVELER_STEMS)
def test_every_picture_names_its_own_operation_and_setup(stem: str) -> None:
    path = _process_plans.plan_path(stem)
    plan = tomllib.loads(path.read_text(encoding="utf-8"))
    assert picture_problems(path.parent, plan) == []
