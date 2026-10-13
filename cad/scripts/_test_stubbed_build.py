"""Test-only: run a real PD ``build`` offline with its seat helpers stubbed.

The general form of ``_stubbed_build`` in ``test_dt_cone_gear_shaft_drawing``:
every helper a module imports from a seat-touching module, its own coroutines
and COM-first functions, and a pure module's coroutines and adapter-first
functions are replaced by recording mocks attached to one parent, so
``seat.mock_calls`` is the build's seat traffic in order.  Pure modules
(specs, geometry, gear maths, adapter parameter types) otherwise stay real,
as do the functions a test names in ``keep``.
"""

from __future__ import annotations

import inspect
from collections.abc import Iterable
from types import ModuleType
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

_PURE_SUFFIXES = ("_spec", "_geometry", "_geom", "_constants")
_PURE_PREFIXES = (
    "solidworks_mcp.adapters.base",
    "math",
    "builtins",
    "dataclasses",
    "typing",
    "pathlib",
    "functools",
    "itertools",
    "collections",
)
_PURE_MODULES = frozenset(
    {"stock_form_cutter", "_gear", "_tolerances", "_printed_tolerance",
     "_fit_bands", "_chain", "_config"}
)
_SEAT_PARAMETERS = frozenset({"adapter", "model", "view", "doc", "drawing_model", "display"})


def _pure(value: Any) -> bool:
    module = getattr(value, "__module__", "") or ""
    return (
        module.endswith(_PURE_SUFFIXES)
        or module.startswith(_PURE_PREFIXES)
        or module in _PURE_MODULES
    )


def _takes_seat(value: Any, parameters: frozenset[str] = _SEAT_PARAMETERS) -> bool:
    try:
        names = list(inspect.signature(value).parameters)
    except (TypeError, ValueError):
        return False
    return bool(names) and names[0] in parameters


def stub_seat(
    monkeypatch: pytest.MonkeyPatch,
    module: ModuleType,
    *,
    keep: Iterable[str] = ("build",),
    spy: Iterable[str] = (),
) -> MagicMock:
    """Stub ``module``'s seat helpers; return the parent recording them in order.

    Each name in ``spy`` keeps its real body but is recorded in that order
    too.  ``add_line_chain`` answers one line name per segment, as on a seat.
    """
    kept = set(keep)
    spied = set(spy)
    seat = MagicMock()
    stubbed: set[str] = set()
    for name, value in list(vars(module).items()):
        if name in kept or name.startswith("__"):
            continue
        if not (inspect.isfunction(value) or inspect.isclass(value)):
            continue
        mock = AsyncMock if inspect.iscoroutinefunction(value) else MagicMock
        if name in spied:
            stub = mock(side_effect=value)
        else:
            local = getattr(value, "__module__", "") == module.__name__
            if local or not _pure(value):
                seat_shaped = not local or inspect.iscoroutinefunction(value) or _takes_seat(value)
            else:  # a pure module's own seat helpers (``_gear.pattern_about_z``)
                seat_shaped = inspect.iscoroutinefunction(value) or _takes_seat(value, frozenset({"adapter"}))
            if not seat_shaped:
                continue
            stub = mock()
            stubbed.add(name)
        monkeypatch.setattr(module, name, stub)
        seat.attach_mock(stub, name)
    if spied - set(vars(module)):
        raise AttributeError(f"{module.__name__} has no {sorted(spied - set(vars(module)))}")
    if "add_line_chain" in stubbed:
        seat.add_line_chain.side_effect = lambda _adapter, points, close=True: [
            f"Line{k}" for k in range(len(points) if close else len(points) - 1)
        ]
    seat.stubbed = frozenset(stubbed)
    return seat


def offline_adapter() -> MagicMock:
    """An adapter whose coroutine methods are awaitable recording mocks."""
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = MagicMock()
    for name in dir(PyWin32Adapter):
        if inspect.iscoroutinefunction(getattr(PyWin32Adapter, name, None)):
            setattr(adapter, name, AsyncMock())
    return adapter


def keyed_artefacts() -> MagicMock:
    """An artefact mapping that answers ``"<key>"`` for each key it is asked."""
    artefacts = MagicMock()
    artefacts.__getitem__.side_effect = lambda key: f"<{key}>"
    return artefacts


def seat_calls(seat: MagicMock, *names: str) -> list[tuple[str, tuple, dict]]:
    """The recorded calls to ``names``, in build order."""
    return [
        (name, args, kwargs)
        for name, args, kwargs in seat.mock_calls
        if name in names
    ]
