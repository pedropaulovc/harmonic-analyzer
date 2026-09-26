"""add_note sizes nothing, so no caller may believe it does.

The adapter's add_note used to accept a ``height`` and discard it: every note
took the document's default format while the callers that passed a height
believed they had sized it (r743-rocker-fix3 measured 2.76 mm a character on a
note "sized" 2.5 mm). A note that needs another size sets its text format
itself, as add_property_linked_note does with ``char_height``.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import _drawing_common
from solidworks_mcp.adapters.solidworks import drawing as sw_drawing

SCRIPTS = Path(__file__).resolve().parent
NOTE_HELPERS = {"add_note", "add_leader_note"}


def test_note_helpers_take_no_size() -> None:
    assert "height" not in inspect.signature(sw_drawing.add_note).parameters
    assert "height" not in inspect.signature(_drawing_common.add_leader_note).parameters


def test_no_script_sizes_a_note_through_the_note_helpers() -> None:
    offenders = []
    for path in sorted(SCRIPTS.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name in NOTE_HELPERS and any(k.arg == "height" for k in node.keywords):
                offenders.append(f"{path.relative_to(SCRIPTS)}:{node.lineno}")
    assert offenders == []
