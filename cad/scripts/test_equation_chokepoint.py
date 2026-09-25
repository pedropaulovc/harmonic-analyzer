"""Every equation write goes through _common (#889). SolidWorks-free.

``_common.set_global`` widens the document to 8 decimal places and reads the
stored global back; ``_common.drive_dimension`` widens it before binding a
dimension. A script that calls the adapter's equation writers, or the equation
manager, directly skips both, and one that sets the angular places itself can
undo them. This scans every build script and diagnostic for either.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent
_SWUNITS_ANGULAR_DECIMAL_PLACES = 52  # swUserPreferenceIntegerValue_e

# Adapter and IEquationMgr members that write an equation or a global.
_WRITERS = {"set_global_variable", "create_equation", "SetEquation", "SetEquationAndConfigurationOption"}
# IEquationMgr members that also exist elsewhere (custom properties), so they
# only count in a file that reaches the equation manager.
_MANAGER_WRITERS = {"Add2", "Add3", "Delete"}
# The one function allowed to call each writer, and to set the angular places.
_OWNERS = {
    "set_global_variable": "set_global",
    "create_equation": "drive_dimension",
    "angular places": "ensure_equation_precision",
}


def _constants(tree: ast.Module) -> dict[str, object]:
    values: dict[str, object] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    values[target.id] = node.value.value
    return values


def _enclosing_functions(tree: ast.Module) -> dict[ast.AST, str]:
    # ast.walk is breadth-first, so an inner function overwrites its outer one.
    owner: dict[ast.AST, str] = {}
    for function in ast.walk(tree):
        if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for node in ast.walk(function):
                owner[node] = function.name
    return owner


def _sets_angular_places(call: ast.Call, constants: dict[str, object]) -> bool:
    func = call.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
    if not name.startswith("SetUserPreference") or not call.args:
        return False
    first = call.args[0]
    if isinstance(first, ast.Constant):
        return first.value == _SWUNITS_ANGULAR_DECIMAL_PLACES
    ref = first.id if isinstance(first, ast.Name) else getattr(first, "attr", "")
    return constants.get(ref) == _SWUNITS_ANGULAR_DECIMAL_PLACES or "ANGULAR_DECIMAL" in ref.upper()


def violations(module: str, source: str) -> list[str]:
    """Equation writes and angular-place writes in ``source`` outside their owner."""
    tree = ast.parse(source)
    constants = _constants(tree)
    owner = _enclosing_functions(tree)
    reaches_manager = "GetEquationMgr" in source
    found: list[str] = []
    if "swUnitsAngularDecimalPlaces" in source and module != "_common":
        found.append(f"{module}: names swUnitsAngularDecimalPlaces")
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        where = f"{module}:{node.lineno}"
        in_function = owner.get(node, "<module>")
        attr = node.func.attr if isinstance(node.func, ast.Attribute) else None
        if attr in _WRITERS or (reaches_manager and attr in _MANAGER_WRITERS):
            allowed = module == "_common" and _OWNERS.get(attr) == in_function
            if not allowed:
                found.append(f"{where} .{attr} in {in_function}")
        if _sets_angular_places(node, constants):
            if not (module == "_common" and in_function == _OWNERS["angular places"]):
                found.append(f"{where} sets angular decimal places in {in_function}")
    if module == "_common":
        # The owner's own write goes through a loop variable; pin the constant
        # to it so a second setter in _common cannot hide behind one.
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "_PREF_UNITS_ANGULAR_DECIMALS":
                function = owner.get(node)
                if function not in (None, _OWNERS["angular places"]):
                    found.append(f"_common:{node.lineno} angular places used in {function}")
    return found


def _sources() -> list[Path]:
    paths = [*SCRIPTS.glob("*.py"), *(SCRIPTS / "diagnostics").glob("*.py")]
    return sorted(p for p in paths if not p.name.startswith("test_") and p.name != "conftest.py")


def test_every_equation_write_goes_through_common() -> None:
    found = [v for path in _sources() for v in violations(path.stem, path.read_text(encoding="utf-8"))]
    assert not found, (
        "write globals with _common.set_global and dimension equations with "
        "_common.drive_dimension; only _common.ensure_equation_precision sets "
        "angular decimal places: " + "; ".join(found)
    )


def test_the_writers_widen_precision_first() -> None:
    tree = ast.parse((SCRIPTS / "_common.py").read_text(encoding="utf-8"))
    for function in ast.walk(tree):
        if not isinstance(function, ast.AsyncFunctionDef) or function.name not in ("set_global", "drive_dimension"):
            continue
        calls = [
            (node.lineno, node.func.id if isinstance(node.func, ast.Name) else node.func.attr)
            for node in ast.walk(function)
            if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute))
        ]
        widen = min(line for line, name in calls if name == "ensure_equation_precision")
        write = min(line for line, name in calls if name in _WRITERS)
        assert widen < write, function.name


@pytest.mark.parametrize(
    ("source", "needle"),
    [
        ("async def f(a, p):\n    await a.set_global_variable(p)\n", ".set_global_variable in f"),
        ("async def f(a, p):\n    await a.create_equation(p)\n", ".create_equation in f"),
        ("def f(m):\n    m.GetEquationMgr().Add3(-1, 'x', True, 1, None)\n", ".Add3 in f"),
        ("def f(m):\n    m.SetEquation(0, '\"A\" = 1')\n", ".SetEquation in f"),
        ("def f(e):\n    e.SetUserPreferenceInteger(52, 0, 2)\n", "sets angular decimal places in f"),
        ("P = 52\ndef f(e):\n    e.SetUserPreferenceInteger(P, 0, 2)\n", "sets angular decimal places in f"),
        ("def f(e, P_ANGULAR_DECIMALS):\n    e.SetUserPreferenceInteger(P_ANGULAR_DECIMALS, 0, 2)\n", "sets angular decimal places"),
        ("X = 'swUnitsAngularDecimalPlaces'\n", "names swUnitsAngularDecimalPlaces"),
    ],
)
def test_the_guard_catches_a_planted_bypass(source: str, needle: str) -> None:
    assert any(needle in v for v in violations("build_planted", source))


def test_a_second_setter_in_common_is_caught() -> None:
    source = "def g(e):\n    e.SetUserPreferenceInteger(_PREF_UNITS_ANGULAR_DECIMALS, 0, 2)\n"
    assert violations("_common", source)


def test_the_guard_passes_clean_and_unrelated_writes() -> None:
    clean = (
        "async def f(a, e, props):\n"
        "    await set_global(a, 'X', '1mm')\n"
        "    props.Add3('Rev', 30, 'A', 2)\n"  # custom properties, no equation manager
        "    e.SetUserPreferenceInteger(542, 0, 1)\n"
    )
    assert violations("build_clean", clean) == []
