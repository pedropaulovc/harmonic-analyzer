"""No rule numbers or ruling ids in anything printed on a shop sheet.

Policy (drawing-simplicity-policy.md, Named exceptions): a named exception is
stated in plain shop words, without rule numbers or dimensions, and its
recorded range lives in the model/spec asserts. A machinist cannot act on
"RULE 12" or "U37c"; those ids belong in comments and commit messages.

Printed text is found two ways:

* every string constant in a cad/scripts module (tests and docstrings
  excluded) that reads as shop text: it has letters and no lowercase ones.
  Developer messages and comments are mixed case, so they fall outside;
* every ``*note*`` field of a parts-registry row (cad/config/parts), which
  build scripts write into the part as notes or properties.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
import yaml

SCRIPTS = Path(__file__).resolve().parent
PARTS = SCRIPTS.parent / "config" / "parts"

# Policy rule numbers and ruling ids (U42, U37c, O1-b). Hole-table tags such
# as E1 are real sheet labels, so E/I/W ids stay out of the pattern.
JARGON = re.compile(r"\b(RULE[ -]?\d+|U\d+[A-Z]?|O\d+(-?[A-Z])?)\b")


# str.format placeholders ({cone_gears}X MHA-013) are filled at placement.
PLACEHOLDER = re.compile(r"\{[a-z_][a-z0-9_]*\}")


def _is_shop_text(text: str) -> bool:
    text = PLACEHOLDER.sub("", text)
    return any(ch.isalpha() for ch in text) and not any(ch.islower() for ch in text)


def _docstring_ids(tree: ast.AST) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            continue
        body = node.body
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            ids.add(id(body[0].value))
    return ids


def source_hits(source: str, label: str) -> list[str]:
    """Jargon in the shop-text string constants of one module's source."""
    tree = ast.parse(source, filename=label)
    docstrings = _docstring_ids(tree)
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        if id(node) in docstrings or not _is_shop_text(node.value):
            continue
        match = JARGON.search(node.value)
        if match:
            hits.append(f"{label}:{node.lineno} {match.group(0)!r}")
    return hits


def registry_hits(document: dict, label: str) -> list[str]:
    """Jargon in the note fields of one parts-registry document."""
    hits = []
    for stem, row in (document or {}).items():
        if not isinstance(row, dict):
            continue
        for key, value in row.items():
            if "note" not in key or not isinstance(value, str):
                continue
            match = JARGON.search(value.upper())
            if match:
                hits.append(f"{label} {stem}.{key} {match.group(0)!r}")
    return hits


def _tree_hits() -> list[str]:
    hits = []
    for path in sorted(SCRIPTS.glob("*.py")):
        if path.name.startswith("test_"):
            continue
        hits += source_hits(path.read_text(encoding="utf-8"), path.name)
    for path in sorted(PARTS.glob("*.yaml")):
        hits += registry_hits(yaml.safe_load(path.read_text(encoding="utf-8")), path.name)
    return hits


def test_no_printed_text_cites_a_rule_or_ruling() -> None:
    assert _tree_hits() == []


def test_scanner_reads_real_notes() -> None:
    # A scanner that silently read nothing would pass the test above.
    import cone_swing_platform_spec
    import draw_drive_train_assembly

    assert _is_shop_text(cone_swing_platform_spec.POST_MOUNT_ENGAGEMENT_NOTE)
    assert _is_shop_text(draw_drive_train_assembly.CONE_CRANK_STEPS)
    assert list(PARTS.glob("*.yaml"))


@pytest.mark.parametrize(
    "source",
    [
        'NOTE = "ENGAGEMENT 0.90D MIN: NAMED EXCEPTION TO RULE 12."',
        'NOTE = f"CUT TO FIT {1}: RULE-6 LIMIT"',
        'STEPS = "\\n".join(("1. FIT MHA-091.", "2. PER U37C, CUT TO FIT."))',
        'NOTE = "SPRING PER O1-B."',
        'STEP = "2. FIT {slotted}X MHA-101 PER RULE 12."',
    ],
)
def test_planted_jargon_is_caught(source: str) -> None:
    assert source_hits(source, "planted.py")


@pytest.mark.parametrize(
    "source",
    [
        '"""Docstring citing RULE 12 and U37c is developer text."""',
        'raise AssertionError("below the U27 2.0 target")',
        'TAGS = ("E1", "E2")',
        'NOTE = "SHORT THREAD ENGAGEMENT ACCEPTED HERE BY DESIGN."',
    ],
)
def test_developer_text_and_sheet_labels_pass(source: str) -> None:
    assert source_hits(source, "planted.py") == []


def test_registry_note_fields_are_scanned() -> None:
    planted = {"widget": {"installation_notes": "Cut to fit: named exception to rule 12."}}
    assert registry_hits(planted, "widget.yaml")
    assert registry_hits({"widget": {"title": "Rule 12 widget"}}, "widget.yaml") == []
