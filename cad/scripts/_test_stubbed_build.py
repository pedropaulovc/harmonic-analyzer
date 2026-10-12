"""Test-only: run a real PD ``build`` offline with its seat helpers stubbed.

The general form of ``_stubbed_build`` in ``test_dt_cone_gear_shaft_drawing``:
every helper a module imports from a seat-touching module, and every local
coroutine or adapter-first function, is replaced by a recording mock attached
to one parent, so ``seat.mock_calls`` is the build's seat traffic in order.
Pure modules (specs, geometry, gear maths, adapter parameter types) stay real,
as do the local functions a test names in ``keep``.
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


def _takes_seat(value: Any) -> bool:
    try:
        parameters = list(inspect.signature(value).parameters)
    except (TypeError, ValueError):
        return False
    return bool(parameters) and parameters[0] in _SEAT_PARAMETERS


def stub_seat(
    monkeypatch: pytest.MonkeyPatch, module: ModuleType, *, keep: Iterable[str] = ("build",)
) -> MagicMock:
    """Stub ``module``'s seat helpers; return the parent recording them in order.

    ``add_line_chain`` answers one line name per segment, as on a seat.
    """
    kept = set(keep)
    seat = MagicMock()
    stubbed: set[str] = set()
    for name, value in list(vars(module).items()):
        if name in kept or name.startswith("__"):
            continue
        if not (inspect.isfunction(value) or inspect.isclass(value)):
            continue
        local = getattr(value, "__module__", "") == module.__name__
        if local and not (inspect.iscoroutinefunction(value) or _takes_seat(value)):
            continue
        if not local and _pure(value):
            continue
        stub = AsyncMock() if inspect.iscoroutinefunction(value) else MagicMock()
        monkeypatch.setattr(module, name, stub)
        seat.attach_mock(stub, name)
        stubbed.add(name)
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
