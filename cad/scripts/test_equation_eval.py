"""Equation precision (#889): the evaluator and the set_global readback gate.
SolidWorks-free; the chokepoint guard is test_equation_chokepoint.py."""

from __future__ import annotations

import asyncio
import itertools
import math
from types import SimpleNamespace
from typing import Any

import pytest

import _common
import _equation_eval as ev

INCHES = ev.DocumentUnits.from_length_unit(3)
_TITLES = itertools.count()  # distinct document titles


def _evaluate(expression: str, values: dict[str, float] | None = None) -> float:
    return ev.evaluate(expression, (values or {}).__getitem__, INCHES)


@pytest.mark.parametrize(
    ("expression", "value"),
    [
        ("25.4mm", 1.0),
        ("2in", 2.0),
        ("1cm", 1.0 / 2.54),
        ("12.5182deg", 12.5182),
        ("0.5rad", math.degrees(0.5)),
        ("197", 197.0),
        ("cos(60)", 0.5),  # trig takes degrees
        ("atn(1)", 45.0),  # and the inverse returns them
        ("sqr(2)", math.sqrt(2.0)),
        ("2 ^ 3", 8.0),
        ("-(3 - 5) * 2", 4.0),
        ("pi", math.pi),
        ('0 + 0.5*cos(20*"T" + 0.0)', 0.5 * math.cos(math.radians(40.0))),
    ],
)
def test_evaluator_reads_the_dialect(expression: str, value: float) -> None:
    assert _evaluate(expression, {"T": 2.0}) == pytest.approx(value, rel=1e-12)


def test_evaluator_resolves_globals_in_document_units() -> None:
    # Replayed from a gooseneck leaf log: ArmY = "LegTop" + "BendR" -> 6.42913386.
    values = {"LegTop": _evaluate("157.3mm"), "BendR": _evaluate("6.0mm")}
    assert _evaluate('"LegTop" + "BendR"', values) == pytest.approx(6.42913386, abs=5e-8)


@pytest.mark.parametrize(
    "expression", ["2 + ", "iif(1, 2, 3)", "3 % 2", "12furlong", "1e-13"]
)
def test_evaluator_refuses_what_it_cannot_read(expression: str) -> None:
    with pytest.raises(ev.EquationError):
        _evaluate(expression, {})


# ---------------------------------------------------------------- set_global --


class _Extension:
    def __init__(self, prefs: dict[int, int], accept_writes: bool = True) -> None:
        self.prefs = prefs
        self.accept_writes = accept_writes

    def GetUserPreferenceInteger(self, pref: int, _option: int) -> int:
        return self.prefs[pref]

    def SetUserPreferenceInteger(self, pref: int, _option: int, value: int) -> bool:
        if not self.accept_writes:
            return False
        self.prefs[pref] = value
        return True


class _EquationMgr:
    """The fake document's rows: its globals (active configuration first), then
    its dimension equations."""

    def __init__(self, doc: _Adapter) -> None:
        names = dict.fromkeys(name for _, name in doc.stored)
        self.rows = [
            (n, doc.stored.get((doc.active, n), doc.stored.get(("", n)))) for n in names
        ]
        self.rows += list(doc.dimension_equations.items())
        self.doc = doc

    def GetCount(self) -> int:
        return len(self.rows)

    def Equation(self, index: int) -> str:
        return f'"{self.rows[index][0]}" = {self.rows[index][1]}'

    def Value(self, index: int) -> float:
        return self.doc._value(self.rows[index][1])


class _Adapter:
    """One open document. A literal with a unit is stored rounded to the
    document's places for that unit, as the equation manager stores it; a
    driven dimension takes its equation's value, optionally rounded too."""

    def __init__(self, title: str, extension: _Extension) -> None:
        self.title = title
        self.extension = extension
        self.stored: dict[tuple[str, str], str] = {}
        self.active = ""
        self.dimensions: dict[str, list[float]] = {}  # name -> [kind, system value]
        self.dimension_equations: dict[str, str] = {}
        self.dimension_places: int | None = None
        self.currentModel = SimpleNamespace(
            Extension=extension,
            GetTitle=lambda: self.title,
            GetEquationMgr=lambda: _EquationMgr(self),
            Parameter=self._parameter,
        )

    def _attempt(self, fn: Any, default: Any = None) -> Any:
        try:
            return fn()
        except Exception:  # noqa: BLE001 -- mirrors the adapter
            return default

    def _parameter(self, name: str) -> Any:
        if name not in self.dimensions:
            return None
        kind, system = self.dimensions[name]
        return SimpleNamespace(SystemValue=system, GetType=lambda: int(kind))

    def _lookup(self, name: str) -> float:
        if "@" in name:
            return self._dimension_doc_value(name)
        expression = self.stored.get((self.active, name), self.stored.get(("", name)))
        return self._value(expression)

    def _value(self, expression: str) -> float:
        value = ev.evaluate(expression, self._lookup, INCHES)
        if "deg" in expression:
            return round(value, self.extension.prefs[_common._PREF_UNITS_ANGULAR_DECIMALS])
        if "mm" in expression:
            return round(value, self.extension.prefs[_common._PREF_UNITS_LINEAR_DECIMALS])
        return value

    def _dimension_doc_value(self, name: str) -> float:
        kind, system = self.dimensions[name]
        return math.degrees(system) if kind == 1 else system * 1000.0 * INCHES.per_mm

    def _solve(self) -> None:
        for name, rhs in self.dimension_equations.items():
            value = self._value(rhs)
            if self.dimension_places is not None:
                value = round(value, self.dimension_places)
            kind = self.dimensions[name][0]
            system = math.radians(value) if kind == 1 else value / INCHES.per_mm / 1000.0
            self.dimensions[name][1] = system

    async def set_global_variable(self, params: Any) -> Any:
        self.active = params.configuration or self.active
        self.stored[(params.configuration, params.name)] = params.expression
        self._solve()
        value = self._value(params.expression)
        return SimpleNamespace(is_success=True, data={"value": value}, error=None)

    async def create_equation(self, params: Any) -> Any:
        lhs, _, rhs = params.equation.partition("=")
        self.dimension_equations[lhs.strip().strip('"')] = rhs.strip()
        self._solve()
        return SimpleNamespace(is_success=True, data={}, error=None)


def _adapter(
    angular_places: int = 2, accept_writes: bool = True, title: str | None = None
) -> _Adapter:
    prefs = {
        _common._PREF_UNITS_LINEAR: 3,
        _common._PREF_UNITS_LINEAR_DECIMALS: 8,
        _common._PREF_UNITS_ANGULAR_DECIMALS: angular_places,
    }
    return _Adapter(title or f"part-{next(_TITLES)}", _Extension(prefs, accept_writes))


def _run(coroutine: Any) -> Any:
    return asyncio.run(coroutine)


def test_an_angular_global_is_stored_at_full_precision() -> None:
    adapter = _adapter(angular_places=2)
    stored = _run(_common.set_global(adapter, "ConeIncline", "12.5182deg"))
    assert stored == 12.5182
    assert adapter.extension.prefs[_common._PREF_UNITS_ANGULAR_DECIMALS] == 8


def test_the_readback_gate_catches_a_rounded_global() -> None:
    # The pre-#889 state: a document that keeps two angular places.
    adapter = _adapter(angular_places=2)

    async def stuck_at_two(params: Any) -> Any:
        value = round(ev.evaluate(params.expression, {}.__getitem__, INCHES), 2)
        return SimpleNamespace(is_success=True, data={"value": value}, error=None)

    adapter.set_global_variable = stuck_at_two  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="rounded or misread"):
        _run(_common.set_global(adapter, "ConeIncline", "12.5182deg"))


def test_a_literal_is_held_to_1e8_absolute() -> None:
    # ConeIncline's bound: 1e-8 deg, however large the angle.
    assert _common.readback_tolerance("12.5182deg", 12.5182) == 1e-8
    assert _common.readback_tolerance('2 * "A"', 400.0) == pytest.approx(8e-6)


def test_a_rejected_precision_write_fails_loud() -> None:
    adapter = _adapter(angular_places=2, accept_writes=False)
    with pytest.raises(RuntimeError, match="angular decimal places"):
        _run(_common.set_global(adapter, "ConeIncline", "12.5182deg"))


def test_formulas_resolve_through_the_stored_globals() -> None:
    adapter = _adapter()
    _run(_common.set_global(adapter, "ColumnX", "197mm"))
    _run(_common.set_global(adapter, "RailW", "12.7mm"))
    stored = _run(_common.set_global(adapter, "InnerX", '"ColumnX" - "RailW" / 2'))
    assert stored == pytest.approx((197.0 - 6.35) / 25.4, abs=5e-8)


def test_a_reopened_title_resolves_through_the_new_document() -> None:
    """Nothing carries over from a closed document that had the same title."""
    first = _adapter(title="pen.SLDASM")
    _run(_common.set_global(first, "Base", "197mm"))
    _run(_common.set_global(first, "Twice", '2 * "Base"'))
    reopened = _adapter(title="pen.SLDASM")
    reopened.stored[("", "Base")] = "100mm"  # what the file holds now
    stored = _run(_common.set_global(reopened, "Twice", '2 * "Base"'))
    assert stored == pytest.approx(200.0 / 25.4, abs=5e-8)


def test_a_formula_checked_against_a_value_the_document_lacks_fails() -> None:
    # Stored 2 x 197 mm while the document holds Base = 100 mm: the check must
    # read the document, not trust the write.
    adapter = _adapter()
    _run(_common.set_global(adapter, "Base", "100mm"))

    async def from_a_closed_document(params: Any) -> Any:
        return SimpleNamespace(is_success=True, data={"value": 2 * 197.0 / 25.4}, error=None)

    adapter.set_global_variable = from_a_closed_document  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="rounded or misread"):
        _run(_common.set_global(adapter, "Twice", '2 * "Base"'))


def test_a_formula_naming_an_undefined_global_fails_loud() -> None:
    adapter = _adapter()

    async def lenient(params: Any) -> Any:  # SolidWorks would reject it anyway
        return SimpleNamespace(is_success=True, data={"value": 0.0}, error=None)

    adapter.set_global_variable = lenient  # type: ignore[method-assign]
    with pytest.raises(ev.EquationError, match="defines no global"):
        _run(_common.set_global(adapter, "Twice", '2 * "Ghost"'))


def test_configuration_scoped_globals_shadow_the_default() -> None:
    adapter = _adapter()
    _run(_common.set_global(adapter, "ToothCount", "120"))
    _run(_common.set_global(adapter, "ToothCount", "6", configuration="T006"))
    stored = _run(
        _common.set_global(adapter, "Pitch", '"ToothCount" / 2', configuration="T006")
    )
    assert stored == 3.0


def test_expected_value_is_still_checked() -> None:
    adapter = _adapter()
    with pytest.raises(RuntimeError, match="dialect mismatch"):
        _run(_common.set_global(adapter, "TrigProbe", "cos(60)", 0.6))


# ---------------------------------------------------------- dimension equations --


def _plane_part(angular_places: int = 2) -> _Adapter:
    adapter = _adapter(angular_places=angular_places)
    adapter.dimensions["D1@Plane"] = [1, 0.0]  # angular
    adapter.dimensions["Width@Profile"] = [0, 0.0]  # linear
    _run(_common.set_global(adapter, "ConeIncline", "12.5182deg"))
    _run(_common.set_global(adapter, "Half", "42.011mm"))
    return adapter


def test_drive_dimension_widens_precision_first() -> None:
    adapter = _adapter(angular_places=2)
    adapter.dimensions["D1@Plane"] = [1, 0.0]
    adapter.stored[("", "ConeIncline")] = "12.5182deg"
    _run(_common.drive_dimension(adapter, "D1@Plane", '"ConeIncline"'))
    assert adapter.extension.prefs[_common._PREF_UNITS_ANGULAR_DECIMALS] == 8
    assert adapter.dimension_equations == {"D1@Plane": '"ConeIncline"'}


def test_every_equation_is_proven_at_save() -> None:
    adapter = _plane_part()
    _run(_common.drive_dimension(adapter, "D1@Plane", '"ConeIncline"'))
    _run(_common.drive_dimension(adapter, "Width@Profile", '2 * "Half"'))
    _common.check_equations(adapter)
    assert math.degrees(adapter.dimensions["D1@Plane"][1]) == pytest.approx(12.5182, abs=1e-9)


def test_a_rounded_dimension_equation_fails_at_save() -> None:
    adapter = _plane_part()
    adapter.dimension_places = 2  # the dimension keeps two places
    _run(_common.drive_dimension(adapter, "D1@Plane", '"ConeIncline"'))
    with pytest.raises(RuntimeError, match='"D1@Plane" = "ConeIncline" holds 12.52'):
        _common.check_equations(adapter)


def test_a_global_rounded_after_its_write_fails_at_save() -> None:
    adapter = _plane_part()
    adapter.extension.prefs[_common._PREF_UNITS_ANGULAR_DECIMALS] = 2  # reset behind our back
    with pytest.raises(RuntimeError, match='"ConeIncline" = 12.5182deg holds 12.52'):
        _common.check_equations(adapter)


def test_a_document_without_equations_passes_untouched() -> None:
    adapter = _adapter(angular_places=2)
    _common.check_equations(adapter)
    assert adapter.extension.prefs[_common._PREF_UNITS_ANGULAR_DECIMALS] == 2
