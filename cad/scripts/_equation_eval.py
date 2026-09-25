"""Evaluate a SOLIDWORKS equation-manager expression in Python.

``_common.set_global`` reads back every global it writes and compares the stored
value with what the expression means. SOLIDWORKS rounds a literal to the
document's decimal places for its unit, and COM then returns the rounded value
as if it were exact: with the part template's 2 angular places,
``"ConeIncline" = 12.5182deg`` was stored as 12.52 (#889). This module supplies
the "what it means" side, at full precision, in the document's units.

The dialect is the subset the build scripts write, each form proven live:

* ``"Name"`` -- another global, resolved through the caller's ``lookup``;
* a number with an optional unit suffix (``mm cm m in ft deg rad``), converted
  to document units; a bare number is already in document units;
* ``+ - * / ^`` and parentheses;
* ``sin cos tan`` take DEGREES, ``atn arcsin arccos`` return degrees
  (``atn(1) = 45``, probed by build_cone_gear), ``sqr`` is the square root,
  plus ``abs exp log int sgn`` and the constant ``pi``.

Anything else raises :class:`EquationError`, so an unsupported form fails the
build loudly instead of passing an unchecked value.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass


class EquationError(ValueError):
    """An expression this evaluator cannot interpret."""


# swLengthUnit_e -> document length units per millimetre.
_DOC_UNITS_PER_MM = {
    0: 1.0,  # swMM
    1: 0.1,  # swCM
    2: 0.001,  # swMETER
    3: 1.0 / 25.4,  # swINCHES
    4: 1.0 / 304.8,  # swFEET
    8: 1000.0,  # swMICRON
}


@dataclass(frozen=True)
class DocumentUnits:
    """How literals convert into one document's units."""

    per_mm: float  # document length units per millimetre

    @classmethod
    def from_length_unit(cls, length_unit: int) -> DocumentUnits:
        per_mm = _DOC_UNITS_PER_MM.get(length_unit)
        if per_mm is None:
            raise EquationError(f"unsupported document length unit {length_unit}")
        return cls(per_mm=per_mm)

    def literal(self, value: float, unit: str) -> float:
        """``value`` written with ``unit``, in document units (angles in degrees)."""
        if unit == "":
            return value
        if unit == "deg":
            return value
        if unit == "rad":
            return math.degrees(value)
        return value * _MM_PER_UNIT[unit] * self.per_mm


_MM_PER_UNIT = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4, "ft": 304.8}


def _deg_trig(function: Callable[[float], float]) -> Callable[[float], float]:
    return lambda degrees: function(math.radians(degrees))


def _deg_inverse(function: Callable[[float], float]) -> Callable[[float], float]:
    return lambda value: math.degrees(function(value))


def _sign(value: float) -> float:
    return float((value > 0) - (value < 0))


_FUNCTIONS: dict[str, Callable[[float], float]] = {
    "sin": _deg_trig(math.sin),
    "cos": _deg_trig(math.cos),
    "tan": _deg_trig(math.tan),
    "atn": _deg_inverse(math.atan),
    "arcsin": _deg_inverse(math.asin),
    "arccos": _deg_inverse(math.acos),
    "sqr": math.sqrt,
    "abs": abs,
    "exp": math.exp,
    "log": math.log,
    "int": lambda value: float(math.floor(value)),
    "sgn": _sign,
}

_TOKEN = re.compile(
    r"""
    (?P<space>\s+)
  | "(?P<name>[^"]+)"
  | (?P<number>(?:\d+\.?\d*|\.\d+))(?P<unit>mm|cm|m|in|ft|deg|rad)?(?![A-Za-z_])
  | (?P<word>[A-Za-z_]\w*)
  | (?P<op>[-+*/^()])
    """,
    re.VERBOSE,
)


def to_python(expression: str, units: DocumentUnits) -> tuple[str, list[str]]:
    """Translate ``expression`` into Python source plus the globals it names."""
    parts: list[str] = []
    names: list[str] = []
    position = 0
    while position < len(expression):
        match = _TOKEN.match(expression, position)
        if match is None:
            raise EquationError(
                f"cannot read {expression[position:]!r} in equation {expression!r}"
            )
        position = match.end()
        if match.group("space"):
            continue
        if match.group("name") is not None:
            names.append(match.group("name"))
            parts.append(f"_g({len(names) - 1})")
            continue
        if match.group("number") is not None:
            value = units.literal(float(match.group("number")), match.group("unit") or "")
            parts.append(repr(value))
            continue
        word = match.group("word")
        if word is not None:
            if word == "pi":
                parts.append(repr(math.pi))
                continue
            if word not in _FUNCTIONS:
                raise EquationError(f"unsupported function {word!r} in {expression!r}")
            parts.append(f"_f[{word!r}]")
            continue
        op = match.group("op")
        parts.append("**" if op == "^" else op)
    return " ".join(parts), names


def evaluate(
    expression: str, lookup: Callable[[str], float], units: DocumentUnits
) -> float:
    """The value ``expression`` means, in document units, at full precision."""
    source, names = to_python(expression, units)
    values = [lookup(name) for name in names]
    try:
        result = eval(  # noqa: S307 -- source built from the whitelisted tokens above
            source,
            {"__builtins__": {}, "_f": _FUNCTIONS, "_g": values.__getitem__},
        )
    except (SyntaxError, TypeError, ValueError, ZeroDivisionError) as error:
        raise EquationError(f"cannot evaluate {expression!r}: {error}") from error
    return float(result)
