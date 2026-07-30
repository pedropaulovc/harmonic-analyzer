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
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

_TOLERANCE_SETTERS = frozenset(
    {
        "set_dimension_bilateral_tolerance",
        "set_dimension_symmetric_angular_tolerance",
        "set_dimension_symmetric_tolerance",
    }
)

_UNSIGNED_VALUE_FRAGMENT = r"(?:\d+(?:\.\d*)?|\.\d+|\x00)"
_SIGNED_VALUE_FRAGMENT = rf"(?:[-+]\s*{_UNSIGNED_VALUE_FRAGMENT})"
_VALUE_FRAGMENT = r"(?:[-+]?(?:\d+(?:\.\d*)?|\.\d+)|\x00)"
_ZERO_FRAGMENT = r"(?:[-+]?\s*(?:0+(?:\.0*)?|\.0+))"
_RA_FRAGMENT = re.compile(rf"\bRa\s*{_VALUE_FRAGMENT}", re.IGNORECASE)
_LIMIT_FRAGMENT = re.compile(
    rf"(?:{_VALUE_FRAGMENT}\s*(?:MAX|MIN)\b|\b(?:MAX|MIN)\s*{_VALUE_FRAGMENT})",
    re.IGNORECASE,
)
_BILATERAL_FRAGMENT = re.compile(
    rf"(?:±|\+/-)\s*{_VALUE_FRAGMENT}|"
    rf"{_SIGNED_VALUE_FRAGMENT}\s*/\s*{_SIGNED_VALUE_FRAGMENT}",
    re.IGNORECASE,
)
_UNILATERAL_FRAGMENT = re.compile(
    rf"(?:\+\s*{_UNSIGNED_VALUE_FRAGMENT}\s*/\s*{_ZERO_FRAGMENT}|"
    rf"{_ZERO_FRAGMENT}\s*/\s*-\s*{_UNSIGNED_VALUE_FRAGMENT})",
    re.IGNORECASE,
)
_PROPERTY_LINK = re.compile(r'\s*\$PRP(?:SHEET)?:"[^"]+"\s*', re.IGNORECASE)

_DIRECT_TOLERANCE_METHODS = frozenset(
    {
        "SetMaxValue",
        "SetMinValue",
        "SetToleranceType",
        "SetToleranceValues",
        "SetToleranceValues2",
    }
)
_TOLERANCE_OBJECT_METHODS = frozenset({"SetValues"})
_TOLERANCE_INTERFACES = frozenset({"IDimensionTolerance"})


@dataclass(frozen=True, order=True)
class DrawingSpecificationViolation:
    """One manufacturing value authored by a drawing script."""

    filename: str
    line: int
    column: int
    rule: str
    evidence: str

    def __str__(self) -> str:
        return (
            f"{self.filename}:{self.line}:{self.column + 1}: "
            f"{self.rule}: {self.evidence}"
        )


def _module_is(module: str | None, expected: str) -> bool:
    return bool(module) and (module == expected or module.endswith(f".{expected}"))


def _imported_functions(
    tree: ast.AST, module_name: str, function_names: frozenset[str]
) -> tuple[dict[str, str], frozenset[str]]:
    direct: dict[str, str] = {}
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and _module_is(node.module, module_name):
            for alias in node.names:
                if alias.name in function_names:
                    direct[alias.asname or alias.name] = alias.name
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _module_is(alias.name, module_name):
                    modules.add(alias.asname or alias.name.split(".")[-1])
    return direct, frozenset(modules)


def _call_is(
    node: ast.Call,
    name: str,
    direct: dict[str, str],
    modules: frozenset[str],
) -> bool:
    if isinstance(node.func, ast.Name):
        return direct.get(node.func.id, node.func.id) == name
    return (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == name
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in modules
    )


def _simple_assignments(tree: ast.AST) -> dict[str, ast.expr]:
    assignments: dict[str, ast.expr] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments[target.id] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.value is not None:
                assignments[node.target.id] = node.value
    return assignments


def _surface_finish_imports(tree: ast.AST) -> tuple[frozenset[str], frozenset[str]]:
    direct: set[str] = set()
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and _module_is(
            node.module, "_surface_finish"
        ):
            direct.update(alias.asname or alias.name for alias in node.names)
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _module_is(alias.name, "_surface_finish"):
                    modules.add(alias.asname or alias.name.split(".")[-1])
    return frozenset(direct), frozenset(modules)


def _part_spec_imports(tree: ast.AST) -> tuple[frozenset[str], frozenset[str]]:
    """Return bindings whose value originates in a part-owned ``*_spec`` module."""

    def is_part_spec(module: str | None) -> bool:
        leaf = (module or "").rsplit(".", 1)[-1]
        return leaf.endswith("_spec") and not leaf.startswith("_")

    direct: set[str] = set()
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and is_part_spec(node.module):
            direct.update(alias.asname or alias.name for alias in node.names)
        if isinstance(node, ast.Import):
            for alias in node.names:
                if is_part_spec(alias.name):
                    modules.add(alias.asname or alias.name.split(".")[-1])
    return frozenset(direct), frozenset(modules)


def _part_spec_surface_control(
    expression: ast.expr,
    *,
    direct: frozenset[str],
    modules: frozenset[str],
    lookup_direct: dict[str, str],
    lookup_modules: frozenset[str],
    assignments: dict[str, ast.expr],
    seen: frozenset[str] = frozenset(),
) -> bool:
    """Whether a finish control is selected from a part-owned specification."""
    if isinstance(expression, ast.Name):
        if expression.id in direct:
            return True
        if expression.id in seen or expression.id not in assignments:
            return False
        return _part_spec_surface_control(
            assignments[expression.id],
            direct=direct,
            modules=modules,
            lookup_direct=lookup_direct,
            lookup_modules=lookup_modules,
            assignments=assignments,
            seen=seen | {expression.id},
        )
    if isinstance(expression, ast.Attribute):
        return isinstance(expression.value, ast.Name) and expression.value.id in modules
    if isinstance(expression, ast.Subscript):
        return _part_spec_surface_control(
            expression.value,
            direct=direct,
            modules=modules,
            lookup_direct=lookup_direct,
            lookup_modules=lookup_modules,
            assignments=assignments,
            seen=seen,
        )
    if not isinstance(expression, ast.Call) or not _call_is(
        expression, "surface_finish_by_key", lookup_direct, lookup_modules
    ):
        return False
    controls = expression.args[0] if expression.args else next(
        (keyword.value for keyword in expression.keywords if keyword.arg == "controls"),
        None,
    )
    return controls is not None and _part_spec_surface_control(
        controls,
        direct=direct,
        modules=modules,
        lookup_direct=lookup_direct,
        lookup_modules=lookup_modules,
        assignments=assignments,
        seen=seen,
    )


def _catalog_sourced(
    expression: ast.expr,
    *,
    direct: frozenset[str],
    modules: frozenset[str],
    assignments: dict[str, ast.expr],
    seen: frozenset[str] = frozenset(),
) -> bool:
    if isinstance(expression, ast.Name):
        if expression.id in direct:
            return True
        if expression.id in seen or expression.id not in assignments:
            return False
        return _catalog_sourced(
            assignments[expression.id],
            direct=direct,
            modules=modules,
            assignments=assignments,
            seen=seen | {expression.id},
        )
    if isinstance(expression, ast.Attribute):
        return isinstance(expression.value, ast.Name) and expression.value.id in modules
    if isinstance(expression, ast.Call):
        return (
            _catalog_sourced(
                expression.func,
                direct=direct,
                modules=modules,
                assignments=assignments,
                seen=seen,
            )
            and all(
                _catalog_sourced(
                    argument,
                    direct=direct,
                    modules=modules,
                    assignments=assignments,
                    seen=seen,
                )
                for argument in expression.args
            )
            and all(
                keyword.arg is not None
                and _catalog_sourced(
                    keyword.value,
                    direct=direct,
                    modules=modules,
                    assignments=assignments,
                    seen=seen,
                )
                for keyword in expression.keywords
            )
        )
    if isinstance(expression, ast.Subscript):
        return _catalog_sourced(
            expression.value,
            direct=direct,
            modules=modules,
            assignments=assignments,
            seen=seen,
        )
    return False


def _joined_string(node: ast.JoinedStr) -> tuple[str, tuple[ast.expr, ...]]:
    fragments: list[str] = []
    expressions: list[ast.expr] = []
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            fragments.append(value.value)
        elif isinstance(value, ast.FormattedValue):
            fragments.append("\x00")
            expressions.append(value.value)
    return "".join(fragments), tuple(expressions)


def _docstring_nodes(tree: ast.AST) -> frozenset[int]:
    found: set[int] = set()
    containers = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    for node in ast.walk(tree):
        if not isinstance(node, containers) or not node.body:
            continue
        first = node.body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            found.add(id(first.value))
    return frozenset(found)


def _tolerance_names(tree: ast.AST) -> frozenset[str]:
    """Return local names proven to hold ``IDimensionTolerance`` objects."""
    assignments = _simple_assignments(tree)
    names: set[str] = set()

    def is_tolerance(expression: ast.expr) -> bool:
        if isinstance(expression, ast.Name):
            return expression.id in names
        if isinstance(expression, ast.Attribute):
            return expression.attr == "Tolerance" or is_tolerance(expression.value)
        if not isinstance(expression, ast.Call):
            return False
        return any(
            isinstance(argument, ast.Constant)
            and argument.value in _TOLERANCE_INTERFACES
            for argument in expression.args
        ) or any(is_tolerance(argument) for argument in expression.args)

    changed = True
    while changed:
        changed = False
        for name, expression in assignments.items():
            if name not in names and is_tolerance(expression):
                names.add(name)
                changed = True
    return frozenset(names)


def _is_tolerance_expression(node: ast.expr, names: frozenset[str]) -> bool:
    if isinstance(node, ast.Name):
        return node.id in names
    if isinstance(node, ast.Attribute):
        return node.attr == "Tolerance" or _is_tolerance_expression(node.value, names)
    if isinstance(node, ast.Call):
        return any(
            isinstance(argument, ast.Constant)
            and argument.value in _TOLERANCE_INTERFACES
            for argument in node.args
        ) or any(_is_tolerance_expression(argument, names) for argument in node.args)
    return False


def drawing_specification_violations(
    source: str, *, filename: str = "<string>"
) -> tuple[DrawingSpecificationViolation, ...]:
    """Find manufacturing semantics that a drawing script owns directly.

    Numeric literals by themselves are intentionally ignored: coordinates,
    scales, leader elbows, and table positions belong to the sheet.  The gate
    targets values that are rendered as tolerances/finish requirements or that
    mutate a drawing dimension's tolerance object.
    """
    tree = ast.parse(source, filename=filename)
    parent = {
        child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)
    }
    docstrings = _docstring_nodes(tree)
    assignments = _simple_assignments(tree)
    catalog_direct, catalog_modules = _surface_finish_imports(tree)
    part_spec_direct, part_spec_modules = _part_spec_imports(tree)
    finish_lookup_direct, finish_lookup_modules = _imported_functions(
        tree, "_surface_finish", frozenset({"surface_finish_by_key"})
    )
    fit_direct, fit_modules = _imported_functions(
        tree, "_fit_limits", frozenset({"fit_limits", "band_text"})
    )
    surface_direct, surface_modules = _imported_functions(
        tree, "_drawing_common", frozenset({"add_surface_finish"})
    )
    tolerance_names = _tolerance_names(tree)
    violations: list[DrawingSpecificationViolation] = []

    def add(node: ast.AST, rule: str, evidence: str) -> None:
        violations.append(
            DrawingSpecificationViolation(
                filename,
                int(getattr(node, "lineno", 1)),
                int(getattr(node, "col_offset", 0)),
                rule,
                evidence,
            )
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docstrings or isinstance(parent.get(node), ast.JoinedStr):
                continue
            rendered = node.value
            formatted: tuple[ast.expr, ...] = ()
        elif isinstance(node, ast.JoinedStr):
            rendered, formatted = _joined_string(node)
        else:
            rendered = ""
            formatted = ()

        if rendered and not _PROPERTY_LINK.fullmatch(rendered):
            ra = _RA_FRAGMENT.search(rendered)
            limits = _LIMIT_FRAGMENT.search(rendered)
            bilateral = _BILATERAL_FRAGMENT.search(rendered)
            unilateral = _UNILATERAL_FRAGMENT.search(rendered)
            catalog_ra = bool(ra and formatted) and all(
                _catalog_sourced(
                    expression,
                    direct=catalog_direct,
                    modules=catalog_modules,
                    assignments=assignments,
                )
                for expression in formatted
            )
            if (ra and not catalog_ra) or limits or bilateral or unilateral:
                match = ra or limits or bilateral or unilateral
                assert match is not None
                add(
                    node,
                    "drawing-spec-string",
                    repr(match.group(0).replace("\x00", "{...}")),
                )

        if isinstance(node, ast.Call):
            for renderer in ("fit_limits", "band_text"):
                if _call_is(node, renderer, fit_direct, fit_modules):
                    add(
                        node,
                        "drawing-tolerance-renderer",
                        f"{renderer}(...) belongs in model/spec",
                    )

            if _call_is(node, "add_surface_finish", surface_direct, surface_modules):
                roughness = next(
                    (kw.value for kw in node.keywords if kw.arg == "roughness_ra"), None
                )
                if roughness is not None and not _catalog_sourced(
                    roughness,
                    direct=catalog_direct,
                    modules=catalog_modules,
                    assignments=assignments,
                ):
                    add(
                        roughness,
                        "drawing-roughness-provenance",
                        f"roughness_ra={ast.unparse(roughness)} is not catalog-sourced",
                    )
                control = next(
                    (kw.value for kw in node.keywords if kw.arg == "control"), None
                )
                if control is not None and not _part_spec_surface_control(
                    control,
                    direct=part_spec_direct,
                    modules=part_spec_modules,
                    lookup_direct=finish_lookup_direct,
                    lookup_modules=finish_lookup_modules,
                    assignments=assignments,
                ):
                    add(
                        control,
                        "drawing-surface-finish-provenance",
                        f"control={ast.unparse(control)} is not part-spec-sourced",
                    )

            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name in _TOLERANCE_SETTERS:
                add(
                    node,
                    "drawing-tolerance-mutation",
                    f"{name}(...) modifies model tolerance",
                )
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in _DIRECT_TOLERANCE_METHODS:
                    add(
                        node,
                        "drawing-tolerance-mutation",
                        f"direct COM {node.func.attr}(...) call",
                    )
                elif (
                    node.func.attr in _TOLERANCE_OBJECT_METHODS
                    and _is_tolerance_expression(node.func.value, tolerance_names)
                ):
                    add(
                        node,
                        "drawing-tolerance-mutation",
                        f"IDimensionTolerance.{node.func.attr}(...) call",
                    )

        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
            for target in targets:
                if not isinstance(target, ast.Attribute):
                    continue
                if target.attr == "Tolerance" or (
                    target.attr == "Type"
                    and _is_tolerance_expression(target.value, tolerance_names)
                ):
                    add(
                        target,
                        "drawing-tolerance-mutation",
                        f"direct COM .{target.attr} assignment",
                    )

    return tuple(sorted(set(violations)))


def drawing_fleet_specification_violations(
    paths: Iterable[Path],
) -> tuple[DrawingSpecificationViolation, ...]:
    """Scan drawing scripts in deterministic path/line order."""
    violations = (
        violation
        for path in sorted(paths)
        for violation in drawing_specification_violations(
            path.read_text(encoding="utf-8"), filename=str(path)
        )
    )
    return tuple(sorted(violations))


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
