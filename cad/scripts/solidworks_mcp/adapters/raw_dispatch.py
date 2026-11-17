"""Call SolidWorks members on a RAW ``PyIDispatch`` by dispid.

A makepy wrapper wraps every object a member typed ``object``/``VARIANT``
returns: ``FirstFeature``, ``GetNextFeature``, and each element of the array
``IBody2.GetEdges``/``GetFaces`` hand back. For every such object pywin32 reads
its type info (``GetTypeInfo``, ``GetTypeAttr``), and binding the result to an
interface class (:func:`sw_type_info.early_bound`) adds a ``QueryInterface``:
three extra cross-process round trips per object a walk merely steps over.
Walking a 40-feature tree twice per ``create_plane`` or scoring 300 body edges
per fillet point pays them hundreds of times.

:func:`invoke` sends the one ``InvokeTypes`` the generated member would send and
returns objects as bare ``PyIDispatch``; :func:`bind` early-binds only the object
a caller keeps. The dispid and signature come from the checked-in type-library
wrapper, recorded without a COM call (:func:`_header`), never hand-written.

A test double (no ``InvokeTypes``) answers through its plain Python members.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from . import sw_type_info as _sw_type_info


class _RecordedInvoke:
    """Stands in for a raw dispatch, so a generated member hands over its call."""

    def __init__(self) -> None:
        self.args: tuple[Any, ...] = ()

    def InvokeTypes(self, *args: Any) -> None:
        self.args = args


_HEADERS: dict[tuple[str, str], tuple[Any, ...]] = {}


def _header(interface: str, member: str) -> tuple[Any, ...]:
    """The ``(dispid, lcid, flags, return type, arg types)`` ``interface``'s
    generated wrapper sends for ``member``, recorded once per process.

    The wrapper is built around a stand-in that keeps the call instead of
    sending it, so recording makes no COM call."""
    key = (interface, member)
    header = _HEADERS.get(key)
    if header is None:
        recorded = _RecordedInvoke()
        wrapper = _sw_type_info.early_bound(
            SimpleNamespace(_oleobj_=recorded), interface
        )
        value = getattr(wrapper, member)  # a property sends its call here
        if callable(value):
            value()  # every generated parameter has a placeholder default
        if len(recorded.args) < 5:
            raise RuntimeError(f"{interface}.{member}: the wrapper sent no call")
        header = _HEADERS[key] = recorded.args[:5]
    return header


def invoke(obj: Any, interface: str, member: str, *args: Any) -> Any:
    """Call ``interface.member`` on ``obj``'s raw dispatch: one round trip, and
    an object result (or array element) stays a bare ``PyIDispatch``.

    ``obj`` may be a wrapper (its ``_oleobj_`` is used) or a raw dispatch. A
    test double answers through ``getattr``: called when callable, else read."""
    raw = getattr(obj, "_oleobj_", obj)
    send = getattr(raw, "InvokeTypes", None)
    if send is None:
        value = getattr(obj, member)
        return value(*args) if callable(value) else value
    return send(*_header(interface, member), *args)


def bind(raw: Any, interface: str) -> Any:
    """Early-bind one raw dispatch :func:`invoke` returned (one
    ``QueryInterface``); ``None``, a wrapper or a test double passes through."""
    if raw is None or getattr(raw, "_oleobj_", None) is not None:
        return raw
    if not hasattr(raw, "InvokeTypes"):
        return raw
    return _sw_type_info.early_bound(SimpleNamespace(_oleobj_=raw), interface)
