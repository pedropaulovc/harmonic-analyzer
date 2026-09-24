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

# Drawing scripts whose part builds own display precision (policy rule 2):
# ``<part>_spec.DRAWING_PRECISION`` is applied natively on the .SLDPRT and the
# drawing only reads it back.  A render-time ``SetPrecision3`` /
# ``set_dimension_precision`` / ``set_hole_callout_precision``, or a number
# typed into sheet text at chosen places (``f"{DEPTH:.1f} DEEP"``), in one of
# these is a part missing its tolerance.
#
# One exception, and only one: a pure REFERENCE dimension is a read-only sum
# of model-owned values, carries no tolerance, and has no model dimension to
# import, so its places are not a tolerance statement.  Those places are still
# specification, so a sheet may pass them through ``SetPrecision3`` ONLY from
# a ``*_spec`` constant (``DRAWING_REFERENCE_PRECISION``) -- never a literal.
# The remaining fleet migrates under #766; until then the rule is scoped here.
PRECISION_MIGRATED_DRAWINGS = frozenset(
    {"draw_harmonic_base.py", "draw_top_frame.py", "draw_tube_frame.py"}
)
_PRECISION_SETTERS = frozenset(
    {
        "set_dimension_precision",
        # Per-variable ICalloutLengthVariable.Precision on a Hole Wizard callout:
        # the same render-time places statement, one callout token at a time.
        "set_hole_callout_precision",
    }
)
_DIRECT_PRECISION_METHODS = frozenset({"SetPrecision3"})
# A static ``{VALUE:.1f}`` spec (fixed, exponent, general, locale or percent
# presentation) prints a number at places the DRAWING chose -- the note-text
# form of a render-time precision (policy rule 2: ``f"{DEPTH:.1f} DEEP"``).
# ``\x00`` stands in for a nested replacement field, ``{VALUE:.{PLACES}f}``.
_FORMAT_PRECISION = re.compile(r"\.(?:\d+|\x00)[eEfFgGn%]?$")
# Diagnostics never reach the sheet: an exception message, an assertion, a
# telemetry/log/span record, a build-step ``check`` or a ``label=`` may format
# numbers at any precision it likes.  So may a finding appended to a problem
# list or a helper's return value -- both end in a raise far more often than on
# the sheet, and the f-string rule only follows text into a CALL (see
# ``_SheetFlow``).
_DIAGNOSTIC_CALLS = frozenset(
    {
        "check",
        "critical",
        "debug",
        "error",
        "event",
        "exception",
        "info",
        "log",
        "print",
        "span",
        "success",
        "warn",
        "warning",
    }
)
_COLLECTION_BUILDERS = frozenset({"add", "append", "appendleft", "extend", "insert"})
# String and container plumbing that hands its text on to whatever consumes
# the result (``_telemetry.event(nearest=tuple(f"..." for ...))``).
_TRANSPARENT_CALLS = frozenset(
    {
        "format",
        "frozenset",
        "join",
        "list",
        "lower",
        "lstrip",
        "replace",
        "rstrip",
        "set",
        "sorted",
        "str",
        "strip",
        "tuple",
        "upper",
    }
)
_DIAGNOSTIC_KEYWORDS = frozenset({"description", "message", "reason"})

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
_WITHIN_FRAGMENT = re.compile(
    rf"\bWITHIN\s+{_VALUE_FRAGMENT}(?![\d.])",
    re.IGNORECASE,
)
_PROPERTY_LINK = re.compile(r'\s*\$PRP(?:SHEET)?:"[^"]+"\s*', re.IGNORECASE)
_FORMAT_SIGN_OPTION = re.compile(r"^(?:.[<>=^]|[<>=^])?([+\- ])")

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


REFERENCE_PRECISION_NAME = "DRAWING_REFERENCE_PRECISION"
# Hole Wizard callout places have no model-side home: ``SetPrecision3`` cannot
# set a callout's per-variable places, so ``set_hole_callout_precision`` must
# write them from the sheet.  The next-closest source of truth is the part's
# spec, so the helper is allowed ONLY with the spec's ``HOLE_CALLOUT_PRECISION``
# (or an item of it) -- never a literal map (policy rule 2).
HOLE_CALLOUT_PRECISION_NAME = "HOLE_CALLOUT_PRECISION"
_HOLE_CALLOUT_SETTER = "set_hole_callout_precision"


def _reference_precision_names(
    tree: ast.AST, constant: str = REFERENCE_PRECISION_NAME
) -> frozenset[str]:
    """Local bindings of a ``*_spec`` module's ``constant`` (by default
    ``DRAWING_REFERENCE_PRECISION``)."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        leaf = (node.module or "").rsplit(".", 1)[-1]
        if not leaf.endswith("_spec") or leaf.startswith("_"):
            continue
        names.update(
            alias.asname or alias.name for alias in node.names if alias.name == constant
        )
    return frozenset(names)


def _reference_precision_sourced(
    expression: ast.expr,
    *,
    names: frozenset[str],
    modules: frozenset[str],
    constant: str = REFERENCE_PRECISION_NAME,
) -> bool:
    """Whether ``expression`` IS the spec's ``DRAWING_REFERENCE_PRECISION`` (or an
    item of it) -- the one value a sheet may pass to ``SetPrecision3``. Any other
    ``*_spec`` value (a diameter, a count) is spec data, not a places statement,
    and must not launder a render-time precision (CodeRabbit, #754)."""
    if isinstance(expression, ast.Subscript):
        expression = expression.value
    if isinstance(expression, ast.Name):
        return expression.id in names
    if isinstance(expression, ast.Attribute):
        return (
            expression.attr == constant
            and isinstance(expression.value, ast.Name)
            and expression.value.id in modules
        )
    return False


def _bound_names(target: ast.expr) -> frozenset[str]:
    if isinstance(target, ast.Name):
        return frozenset({target.id})
    if isinstance(target, (ast.List, ast.Tuple)):
        return frozenset(
            name for element in target.elts for name in _bound_names(element)
        )
    return frozenset()


def _part_spec_sourced(
    expression: ast.expr,
    *,
    direct: frozenset[str],
    modules: frozenset[str],
    assignments: dict[str, ast.expr],
    seen: frozenset[str] = frozenset(),
    bound: frozenset[str] = frozenset(),
) -> bool:
    """Whether a value can be traced to a part-owned ``*_spec`` contract.

    Attribute access and indexing only select data from an already-proven
    contract.  The comprehension case covers the common, still inspectable
    ``next(row for row in GEOMETRIC_CONTROLS if ...)`` selector without
    treating arbitrary drawing-local helper calls as provenance.
    """
    if isinstance(expression, ast.Name):
        if (
            expression.id in direct
            or expression.id in modules
            or expression.id in bound
        ):
            return True
        if expression.id in seen or expression.id not in assignments:
            return False
        return _part_spec_sourced(
            assignments[expression.id],
            direct=direct,
            modules=modules,
            assignments=assignments,
            seen=seen | {expression.id},
            bound=bound,
        )
    if isinstance(expression, ast.Attribute):
        return _part_spec_sourced(
            expression.value,
            direct=direct,
            modules=modules,
            assignments=assignments,
            seen=seen,
            bound=bound,
        )
    if isinstance(expression, ast.Subscript):
        return _part_spec_sourced(
            expression.value,
            direct=direct,
            modules=modules,
            assignments=assignments,
            seen=seen,
            bound=bound,
        )
    if isinstance(expression, ast.JoinedStr):
        formatted = [
            value.value
            for value in expression.values
            if isinstance(value, ast.FormattedValue)
        ]
        owns_numeric_text = any(
            isinstance(value, ast.Constant)
            and isinstance(value.value, str)
            and any(character.isdigit() for character in value.value)
            for value in expression.values
        )
        return (
            bool(formatted)
            and not owns_numeric_text
            and all(
                _part_spec_sourced(
                    value,
                    direct=direct,
                    modules=modules,
                    assignments=assignments,
                    seen=seen,
                    bound=bound,
                )
                for value in formatted
            )
        )
    if isinstance(expression, (ast.GeneratorExp, ast.ListComp, ast.SetComp)):
        comprehension_bound = set(bound)
        for generator in expression.generators:
            if not _part_spec_sourced(
                generator.iter,
                direct=direct,
                modules=modules,
                assignments=assignments,
                seen=seen,
                bound=frozenset(comprehension_bound),
            ):
                return False
            comprehension_bound.update(_bound_names(generator.target))
        return _part_spec_sourced(
            expression.elt,
            direct=direct,
            modules=modules,
            assignments=assignments,
            seen=seen,
            bound=frozenset(comprehension_bound),
        )
    if isinstance(expression, ast.Call):
        return (
            isinstance(expression.func, ast.Name)
            and expression.func.id == "next"
            and bool(expression.args)
            and _part_spec_sourced(
                expression.args[0],
                direct=direct,
                modules=modules,
                assignments=assignments,
                seen=seen,
                bound=bound,
            )
        )
    return False


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
    controls = (
        expression.args[0]
        if expression.args
        else next(
            (
                keyword.value
                for keyword in expression.keywords
                if keyword.arg == "controls"
            ),
            None,
        )
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


def _static_format_spec(node: ast.FormattedValue) -> str | None:
    format_spec = node.format_spec
    if format_spec is None:
        return ""
    if not isinstance(format_spec, ast.JoinedStr):
        return None
    if not all(
        isinstance(value, ast.Constant) and isinstance(value.value, str)
        for value in format_spec.values
    ):
        return None
    return "".join(value.value for value in format_spec.values)


def _formatted_placeholder(node: ast.FormattedValue) -> str:
    """Represent a formatted value without discarding a static sign option."""
    format_spec = _static_format_spec(node)
    if format_spec is None:
        return "\x00"
    sign = _FORMAT_SIGN_OPTION.match(format_spec)
    if sign is not None:
        return f"{sign.group(1)}\x00"
    return "\x00"


def _joined_string(node: ast.JoinedStr) -> tuple[str, tuple[ast.expr, ...]]:
    fragments: list[str] = []
    expressions: list[ast.expr] = []
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            fragments.append(value.value)
        elif isinstance(value, ast.FormattedValue):
            fragments.append(_formatted_placeholder(value))
            expressions.append(value.value)
    return "".join(fragments), tuple(expressions)


def _rendered_string_expression(
    expression: ast.expr,
    *,
    assignments: dict[str, ast.expr],
    seen: frozenset[str] = frozenset(),
) -> tuple[str, tuple[tuple[int, ast.expr], ...]] | None:
    """Render statically-known string pieces and locate f-string expressions."""
    if isinstance(expression, ast.Constant) and isinstance(expression.value, str):
        return expression.value, ()
    if isinstance(expression, ast.Name):
        if expression.id in seen or expression.id not in assignments:
            return None
        return _rendered_string_expression(
            assignments[expression.id],
            assignments=assignments,
            seen=seen | {expression.id},
        )
    if isinstance(expression, ast.JoinedStr):
        fragments: list[str] = []
        formatted: list[tuple[int, ast.expr]] = []
        rendered_length = 0
        for value in expression.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                fragments.append(value.value)
                rendered_length += len(value.value)
                continue
            if not isinstance(value, ast.FormattedValue):
                return None
            placeholder = _formatted_placeholder(value)
            formatted.append((rendered_length, value.value))
            fragments.append(placeholder)
            rendered_length += len(placeholder)
        return "".join(fragments), tuple(formatted)
    if isinstance(expression, ast.BinOp) and isinstance(expression.op, ast.Add):
        left = _rendered_string_expression(
            expression.left, assignments=assignments, seen=seen
        )
        right = _rendered_string_expression(
            expression.right, assignments=assignments, seen=seen
        )
        if left is None or right is None:
            return None
        left_text, left_formatted = left
        right_text, right_formatted = right
        return left_text + right_text, left_formatted + tuple(
            (position + len(left_text), value) for position, value in right_formatted
        )
    return None


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


def _call_name(node: ast.Call) -> str:
    return getattr(node.func, "id", None) or getattr(node.func, "attr", None) or ""


def _is_diagnostic_call(node: ast.Call) -> bool:
    name = _call_name(node)
    return name in _DIAGNOSTIC_CALLS or name.endswith(("Error", "Exception", "Warning"))


def _is_diagnostic_keyword(name: str | None) -> bool:
    return bool(name) and ("label" in name or name in _DIAGNOSTIC_KEYWORDS)


class _SheetFlow:
    """Whether a string expression can reach sheet text, by syntactic flow.

    Walk up from the expression. A raise, assert, return, diagnostic call,
    ``label=``-style keyword or collection builder ends the flow as NOT sheet
    text. Any other call is a sink: the text is handed to the drawing. An
    assignment follows the bound name to its reads, module-wide by name, so a
    name that reaches a sink anywhere counts (conflation can only flag more). A
    name with no reads at all counts as sheet text, the conservative answer.
    """

    def __init__(self, tree: ast.AST, parent: dict[ast.AST, ast.AST]) -> None:
        self._parent = parent
        self._reads: dict[str, list[ast.Name]] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                self._reads.setdefault(node.id, []).append(node)
        self._names: dict[str, bool] = {}

    def bound(self, node: ast.AST) -> bool:
        current = node
        keyword: str | None = None
        while current in self._parent:
            current = self._parent[current]
            if isinstance(current, (ast.Raise, ast.Assert, ast.Return)):
                return False
            if isinstance(current, (ast.Yield, ast.YieldFrom)):
                return False
            if isinstance(current, ast.keyword):
                keyword = current.arg
                continue
            if isinstance(current, ast.Call):
                if _is_diagnostic_call(current) or _is_diagnostic_keyword(keyword):
                    return False
                name = _call_name(current)
                if name in _COLLECTION_BUILDERS:
                    return False
                if name in _TRANSPARENT_CALLS:
                    keyword = None
                    continue
                return True
            if isinstance(current, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = (
                    current.targets
                    if isinstance(current, ast.Assign)
                    else [current.target]
                )
                if not all(
                    isinstance(target, (ast.Name, ast.Tuple, ast.List))
                    for target in targets
                ):
                    # ``CALLOUTS["X"] = ...`` / ``obj.text = ...`` leave the
                    # name flow; count them as sheet text.
                    return True
                return any(
                    self._name_bound(name)
                    for target in targets
                    for name in _bound_names(target)
                )
            if isinstance(current, ast.stmt):
                return False
        return False

    def _name_bound(self, name: str) -> bool:
        if name in self._names:
            return self._names[name]
        # Provisional answer breaks a cycle (``text = text + ...``).
        self._names[name] = False
        reads = self._reads.get(name, [])
        answer = not reads or any(self.bound(read) for read in reads)
        self._names[name] = answer
        return answer


def _format_precision(
    node: ast.FormattedValue,
    *,
    reference_names: frozenset[str],
    reference_modules: frozenset[str],
) -> str | None:
    """The format spec when it fixes decimal places the drawing owns.

    A nested ``{VALUE:.{PLACES}f}`` is the note-text twin of ``SetPrecision3``
    and gets the same single exception: ``PLACES`` IS the spec's
    ``DRAWING_REFERENCE_PRECISION``.
    """
    format_spec = node.format_spec
    if not isinstance(format_spec, ast.JoinedStr):
        return None
    rendered, nested = _joined_string(format_spec)
    if not _FORMAT_PRECISION.search(rendered):
        return None
    if nested and all(
        _reference_precision_sourced(
            expression, names=reference_names, modules=reference_modules
        )
        for expression in nested
    ):
        return None
    return rendered.replace("\x00", "{...}")


def _leaves_primary_precision(node: ast.Call) -> bool:
    """``SetPrecision3(-1, ...)``: the primary places are left alone.

    The first positional argument is ``swDimensionPrecisionSettings_e`` for the
    primary value; ``-1`` (do-not-change) is how the model-side tolerance helper
    sets only the tolerance places.  Anything else, or a non-literal, rewrites
    the nominal's precision on the sheet.
    """
    if not node.args:
        return False
    first = node.args[0]
    return (
        isinstance(first, ast.UnaryOp)
        and isinstance(first.op, ast.USub)
        and isinstance(first.operand, ast.Constant)
        and first.operand.value == 1
    )


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
    reference_precision_names = _reference_precision_names(tree)
    hole_callout_precision_names = _reference_precision_names(
        tree, HOLE_CALLOUT_PRECISION_NAME
    )
    finish_lookup_direct, finish_lookup_modules = _imported_functions(
        tree, "_surface_finish", frozenset({"surface_finish_by_key"})
    )
    fit_direct, fit_modules = _imported_functions(
        tree, "_fit_limits", frozenset({"fit_limits", "band_text"})
    )
    surface_direct, surface_modules = _imported_functions(
        tree, "_drawing_common", frozenset({"add_surface_finish"})
    )
    gtol_direct, gtol_modules = _imported_functions(
        tree, "_drawing_common", frozenset({"add_feature_control_frame"})
    )
    note_direct, note_modules = _imported_functions(
        tree, "_drawing_common", frozenset({"add_attached_note"})
    )
    tolerance_names = _tolerance_names(tree)
    precision_direct, precision_modules = _imported_functions(
        tree, "_drawing_common", _PRECISION_SETTERS
    )
    sheet_flow = _SheetFlow(tree, parent)
    # A value formatted inside an attached note's ``WITHIN <limit>`` is a
    # geometric limit, not a nominal's display precision: ``drawing-gdt-note``
    # already governs it (a local value is flagged there, a part-contract value
    # is allowed), so the f-string precision rule leaves it to that gate.
    within_limits: set[int] = set()
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call) or not _call_is(
            call, "add_attached_note", note_direct, note_modules
        ):
            continue
        text = next((kw.value for kw in call.keywords if kw.arg == "text"), None)
        rendered_note = (
            None
            if text is None
            else _rendered_string_expression(text, assignments=assignments)
        )
        if rendered_note is None:
            continue
        rendered_text, formatted_note = rendered_note
        for match in _WITHIN_FRAGMENT.finditer(rendered_text):
            within_limits.update(
                id(expression)
                for position, expression in formatted_note
                if match.start() <= position < match.end()
            )
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

        if (
            isinstance(node, ast.JoinedStr)
            and not isinstance(parent.get(node), ast.FormattedValue)
            and sheet_flow.bound(node)
        ):
            for value in node.values:
                if (
                    not isinstance(value, ast.FormattedValue)
                    or id(value.value) in within_limits
                ):
                    continue
                places = _format_precision(
                    value,
                    reference_names=reference_precision_names,
                    reference_modules=part_spec_modules,
                )
                if places is not None:
                    add(
                        value,
                        "drawing-owned-precision",
                        f"f-string {{{ast.unparse(value.value)}:{places}}} types "
                        "drawing-chosen decimal places into sheet text",
                    )

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

            if _call_is(node, "add_feature_control_frame", gtol_direct, gtol_modules):
                tolerance = next(
                    (kw.value for kw in node.keywords if kw.arg == "tolerance"),
                    None,
                )
                if tolerance is not None and not _part_spec_sourced(
                    tolerance,
                    direct=part_spec_direct,
                    modules=part_spec_modules,
                    assignments=assignments,
                ):
                    add(
                        tolerance,
                        "drawing-gdt-provenance",
                        f"tolerance={ast.unparse(tolerance)} is not part-spec-sourced",
                    )

            if _call_is(node, "add_attached_note", note_direct, note_modules):
                text = next(
                    (kw.value for kw in node.keywords if kw.arg == "text"), None
                )
                if text is not None:
                    rendered_note = _rendered_string_expression(
                        text, assignments=assignments
                    )
                    if rendered_note is not None:
                        rendered_text, formatted_note = rendered_note
                        for match in _WITHIN_FRAGMENT.finditer(rendered_text):
                            values = tuple(
                                expression
                                for position, expression in formatted_note
                                if match.start() <= position < match.end()
                            )
                            if values and all(
                                _part_spec_sourced(
                                    value,
                                    direct=part_spec_direct,
                                    modules=part_spec_modules,
                                    assignments=assignments,
                                )
                                for value in values
                            ):
                                continue
                            add(
                                text,
                                "drawing-gdt-note",
                                repr(match.group(0).replace("\x00", "{...}")),
                            )

            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name in _PRECISION_SETTERS or any(
                _call_is(node, setter, precision_direct, precision_modules)
                for setter in _PRECISION_SETTERS
            ):
                setter = (
                    name
                    if name in _PRECISION_SETTERS
                    else precision_direct.get(str(name), str(name))
                )
                places = next(
                    (kw.value for kw in node.keywords if kw.arg == "precision"),
                    node.args[1] if len(node.args) > 1 else None,
                )
                if setter != _HOLE_CALLOUT_SETTER:
                    add(
                        node,
                        "drawing-owned-precision",
                        f"{setter}(...) rewrites display precision at render time",
                    )
                elif places is None or not _reference_precision_sourced(
                    places,
                    names=hole_callout_precision_names,
                    modules=part_spec_modules,
                    constant=HOLE_CALLOUT_PRECISION_NAME,
                ):
                    add(
                        node,
                        "drawing-owned-precision",
                        f"{setter}(...) writes callout places that are not the "
                        f"spec's {HOLE_CALLOUT_PRECISION_NAME}",
                    )
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr in _DIRECT_PRECISION_METHODS
                and not _leaves_primary_precision(node)
                and not (
                    node.args
                    and _reference_precision_sourced(
                        node.args[0],
                        names=reference_precision_names,
                        modules=part_spec_modules,
                    )
                )
            ):
                add(
                    node,
                    "drawing-owned-precision",
                    f"direct COM {node.func.attr}(...) writes a precision that is "
                    f"not the spec's {REFERENCE_PRECISION_NAME}",
                )
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
    """Scan drawing scripts in deterministic path/line order.

    ``drawing-owned-precision`` applies only to ``PRECISION_MIGRATED_DRAWINGS``
    until #766 moves the rest of the fleet's precision into its part builds.
    """
    violations = (
        violation
        for path in sorted(paths)
        for violation in drawing_specification_violations(
            path.read_text(encoding="utf-8"), filename=str(path)
        )
        if violation.rule != "drawing-owned-precision"
        or path.name in PRECISION_MIGRATED_DRAWINGS
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
