"""Assertion helpers for the offline ``test_*_drawing.py`` contracts.

TEST-ONLY, pure data — never imported by a build or drawing recipe.

The drawing tests historically pinned a sheet's specification by asserting its
SOURCE TEXT (``assert 'roughness_ra="1.6"' in source``).  That makes the literal
load-bearing: moving the value to a shared catalog or a part spec — strictly an
improvement — turns ``check:*`` red, and a reviewer cannot tell expected refactor
churn from a real regression.

Assert IDENTITY instead: the sheet must REFERENCE the named constant, and the
name must resolve to the value the catalog defines.  That is strictly stronger
than the text assertion (it catches a sheet that reimplements the value under
the right name) while surviving any relocation of where the number lives.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any

_TOLERANCE_SETTERS = frozenset(
    {"set_dimension_bilateral_tolerance", "set_dimension_symmetric_tolerance"}
)


def model_toleranced_dimensions(build_module: Any) -> dict[tuple[str, str], str]:
    """Map ``(feature, dimension) -> band expression`` for one build script.

    AST, not substring matching: the call spans several lines after formatting,
    so a text assertion pins the line breaks as well as the contract and goes red
    on a pure reformat.  The value is the SOURCE of the deviation arguments (e.g.
    ``*deviations(SEAT_DIA_BAND)``), which is what a test wants to assert — that
    the band came from a named constant rather than a typed number.
    """
    tree = ast.parse(Path(build_module.__file__).read_text(encoding="utf-8"))
    found: dict[tuple[str, str], str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
        if name not in _TOLERANCE_SETTERS or len(node.args) < 3:
            continue
        # A build script may tolerance a family of lands in a loop, where the
        # feature/dimension are f-strings rather than literals. Report the
        # SOURCE expression in that case instead of dropping the call — a
        # silently-skipped call site would let the gate pass on a part that
        # tolerances nothing.
        key = tuple(
            arg.value if isinstance(arg, ast.Constant) else ast.unparse(arg)
            for arg in node.args[1:3]
        )
        found[key] = ", ".join(ast.unparse(arg) for arg in node.args[3:])
    return found


def assert_sheet_references(module: Any, name: str, expected: Any) -> None:
    """Assert ``module`` uses shared constant ``name`` and that it holds ``expected``.

    Two checks, deliberately both:

    * the name is bound in the sheet's namespace and equals ``expected`` — so a
      catalog retune that the sheet did not intend fails here; and
    * the name is actually LOADED inside ``build()`` (an ``ast.Name`` read, not
      a substring — a comment or docstring mentioning it must not count) — so
      an import left behind after the last call site was deleted, or a literal
      retyped beside a stale mention, does not keep passing.
    """
    actual = getattr(module, name, None)
    if actual is None:
        raise AssertionError(
            f"{module.__name__} does not import {name!r} "
            "(a shared constant it is required to use)"
        )
    if actual != expected:
        raise AssertionError(
            f"{module.__name__}.{name} is {actual!r}, expected {expected!r}"
        )
    tree = ast.parse(inspect.getsource(module))
    builds = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
        and node.name == "build"
    ]
    if not builds:
        raise AssertionError(f"{module.__name__} has no build() to inspect")
    loaded = any(
        isinstance(node, ast.Name)
        and node.id == name
        and isinstance(node.ctx, ast.Load)
        for build in builds
        for node in ast.walk(build)
    )
    if not loaded:
        raise AssertionError(
            f"{module.__name__} imports {name!r} but never loads it in build()"
        )
