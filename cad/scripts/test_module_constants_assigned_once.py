"""No cad/scripts module assigns the same UPPERCASE module-level name twice.

A merge that keeps both sides of a rewritten section leaves the old block's
constants silently shadowing -- or shadowed by -- the new ones, and every
import-time gate between the two copies proves the wrong numbers (the
cascade -> integ merge kept integ's pre-#859 return-spring block after the
cascade's, redefining seven of its names; Main's restricted review).  A
re-assignment that is meant, such as a value refined in place, goes in the
allowlist with its reason.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
_UPPER = re.compile(r"^_?[A-Z][A-Z0-9_]*$")
# (module stem, name): why the second top-level assignment is intended.
ALLOWED_REASSIGNMENTS: dict[tuple[str, str], str] = {}


def _top_level_names(node: ast.stmt) -> list[str]:
    if isinstance(node, ast.Assign):
        targets = node.targets
    elif isinstance(node, ast.AnnAssign) and node.value is not None:
        targets = [node.target]
    else:
        return []
    names = []
    for target in targets:
        elements = target.elts if isinstance(target, (ast.Tuple, ast.List)) else [target]
        names += [e.id for e in elements if isinstance(e, ast.Name) and _UPPER.match(e.id)]
    return names


def duplicate_module_constants(source: str) -> dict[str, list[int]]:
    """UPPERCASE names assigned more than once at module top level, with their lines."""
    seen: dict[str, list[int]] = {}
    for node in ast.parse(source).body:
        for name in _top_level_names(node):
            seen.setdefault(name, []).append(node.lineno)
    return {name: lines for name, lines in seen.items() if len(lines) > 1}


def test_the_scan_catches_a_kept_old_block() -> None:
    source = "A = 1\n_B_C = 2\nx = 3\nif True:\n    A = 4\nA = 5\n_B_C, x = 6, 7\nx = 8\n"
    assert duplicate_module_constants(source) == {"A": [1, 6], "_B_C": [2, 7]}


def test_no_module_assigns_an_uppercase_name_twice() -> None:
    found = {}
    for path in sorted(SCRIPTS.glob("*.py")):
        for name, lines in duplicate_module_constants(path.read_text(encoding="utf-8")).items():
            if (path.stem, name) not in ALLOWED_REASSIGNMENTS:
                found[f"{path.name}:{name}"] = lines
    assert found == {}
