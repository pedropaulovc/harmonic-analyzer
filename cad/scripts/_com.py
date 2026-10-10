"""Low-level COM binding, invocation and scalar reads.

Separate module so edits affect only recipes that use this scope.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any


def _read_member(obj: Any, name: str) -> Any:
    """Read a COM accessor that pywin32 may expose as a method or property."""
    member = getattr(obj, name, None)
    if not callable(member):
        return member
    try:
        return member()
    except Exception:
        return member


# ---------------------------------------------------------------------------
# Assembly helpers (M6)
# ---------------------------------------------------------------------------

# The MIRROR_PLANE per-part chirality table and its consumer mirror_placement
# are GONE (#151): every assembly is authored machine-handed and components
# insert on their exact machine transforms (see _transforms.py).

# swConstrainedStatus_e
UNDER_CONSTRAINED = 2


FULLY_CONSTRAINED = 3


def _flag(obj: Any, interface: str) -> None:
    from solidworks_mcp.adapters import sw_type_info

    try:
        sw_type_info.flag_methods(obj, interface)
    except Exception:
        pass


def _early_bound(obj: Any, interface: str) -> Any:
    """Return the generated interface wrapper, or RAISE -- never a raw dispatch.

    Early-bound wrappers invoke known DISPIDs directly and avoid the repeated
    ``GetIDsOfNames`` calls paid by whole-interface method flagging.

    **This never silently returns the unwrapped object.** It used to
    (``except Exception: return obj``), and that one line is the root of the
    ``[out]``-param trap: 542 SolidWorks methods have ``[out]`` params, and
    which marshalling convention applies depends ENTIRELY on whether the object
    is early-bound. makepy handles all 542 uniformly -- call bare, read the
    return tuple -- but on a raw late-bound dispatch that same call needs
    ``VT_BYREF`` VARIANTs. A silent fallback therefore flipped the convention
    invisibly, and the failure mode is a WRONG ANSWER, not an error: an
    unwritten byref reads as "no data" == "no errors found". That cost a full
    session chasing a non-existent "GetWhatsWrong is blind mid-build" defect.

    So a call site can now TRUST that what it gets back is early-bound, and the
    single calling convention (consume the tuple) is always correct.

    Two quiet passthroughs remain, both provably not COM: ``None``, and an
    object with no ``_oleobj_`` (a test double, which never reaches a COM
    boundary).

    The former ``*method_names`` varargs are GONE, not merely ignored. They only
    ever fed ``flag_method_names``, the exact-name fallback used when no
    generated class resolved -- i.e. the silent late-binding path removed above.
    All 74 call sites that passed them were stripped in the same change, so a
    lingering name is now a ``TypeError`` at the call site rather than an
    argument that silently means nothing.
    """
    from solidworks_mcp.adapters import sw_type_info

    if obj is None or getattr(obj, "_oleobj_", None) is None:
        return obj  # not a COM dispatch -- nothing to bind, nothing to marshal

    # Raises ValueError on an interface absent from the wrapper -- a typo or a
    # wrapper that needs regenerating. Let it out; that is a bug, not a mode.
    typed = sw_type_info.early_bound(obj, interface)
    if sw_type_info.is_early_bound(typed, interface):
        return typed

    raise RuntimeError(
        f"_early_bound({interface}) could not bind a generated wrapper to a live"
        f" COM dispatch ({type(obj).__name__}). Refusing to hand back the raw"
        " late-bound object: [out] params would then need VT_BYREF VARIANTs"
        " instead of the return tuple, and getting that wrong reads as 'no"
        " data' rather than failing. Regenerate the checked-in makepy wrapper"
        " for this SolidWorks version, or bind the interface that declares the"
        " member being called."
    )


class _RecordedInvoke:
    """Stands in for a raw dispatch, so a generated member hands over its call."""

    def __init__(self) -> None:
        self.args: tuple[Any, ...] = ()

    def InvokeTypes(self, *args: Any) -> None:
        self.args = args

    def Invoke(self, *args: Any) -> None:  # a generated property put
        self.args = args


_COM_HEADERS: dict[tuple[str, str], tuple[Any, ...]] = {}


def _com_header(interface: str, member: str) -> tuple[Any, ...]:
    """The ``(dispid, lcid, flags, return type, arg types)`` that ``interface``'s
    generated wrapper sends for ``member``, recorded once per process.

    The numbers come from the type-library wrapper, never from a hand-written
    dispid, and recording them makes no COM call: the wrapper is built on a
    stand-in that keeps the call instead of sending it."""
    key = (interface, member)
    header = _COM_HEADERS.get(key)
    if header is None:
        recorded = _RecordedInvoke()
        wrapper = _early_bound(SimpleNamespace(_oleobj_=recorded), interface)
        value = getattr(wrapper, member)  # a property sends its call here
        if callable(value):
            value()  # every generated parameter has a placeholder default
        if len(recorded.args) < 5:
            raise RuntimeError(f"{interface}.{member}: the wrapper sent no call")
        header = _COM_HEADERS[key] = recorded.args[:5]
    return header


def _com_invoke(obj: Any, interface: str, member: str, *args: Any) -> Any:
    """Call ``interface.member`` on ``obj``'s RAW dispatch by dispid.

    One round trip, and an object result stays a raw ``PyIDispatch``. A
    generated wrapper instead wraps every object it returns from a method
    typed ``object`` (``FirstFeature``, ``GetNextFeature``,
    ``GetFirstSubFeature``, ``GetNextDisplayDimension``, …): pywin32 reads the
    element's type info (``GetTypeInfo``, ``GetTypeAttr``) and the generated
    class runs a ``QueryInterface`` in its constructor -- three extra round
    trips of ~7 ms on a farm seat for each object a walk merely steps over.
    Walk raw, then :func:`_bind` only the object a caller keeps.

    A test double (no ``InvokeTypes``) answers through its plain Python
    members, as :func:`_read_member` reads it."""
    raw = getattr(obj, "_oleobj_", obj)
    invoke = getattr(raw, "InvokeTypes", None)
    if invoke is None:
        value = getattr(obj, member)
        return value(*args) if callable(value) else value
    return invoke(*_com_header(interface, member), *args)


def _com_put(obj: Any, interface: str, member: str, value: Any) -> None:
    """Set property ``interface.member`` on ``obj``'s RAW dispatch: the one
    ``Invoke`` the generated wrapper's setter sends, without binding the
    object first (a :func:`_bind` is a ``QueryInterface`` round trip).
    A test double is set as a plain attribute."""
    raw = getattr(obj, "_oleobj_", obj)
    invoke = getattr(raw, "Invoke", None)
    if invoke is None or not hasattr(raw, "InvokeTypes"):
        setattr(obj, member, value)
        return
    key = (interface, f"{member}=")
    header = _COM_HEADERS.get(key)
    if header is None:
        recorded = _RecordedInvoke()
        wrapper = _early_bound(SimpleNamespace(_oleobj_=recorded), interface)
        setattr(wrapper, member, None)
        if len(recorded.args) < 5:
            raise RuntimeError(f"{interface}.{member}: the wrapper sent no put")
        header = _COM_HEADERS[key] = recorded.args
    invoke(*header[:4], value, *header[5:])


def _bind(raw: Any, interface: str) -> Any:
    """Early-bind one raw dispatch :func:`_com_invoke` returned (one
    ``QueryInterface``); ``None``, a wrapper or a test double passes through."""
    if raw is None or getattr(raw, "_oleobj_", None) is not None:
        return raw
    if not hasattr(raw, "InvokeTypes"):
        return raw
    return _early_bound(SimpleNamespace(_oleobj_=raw), interface)


def _flag_only(obj: Any, *method_names: str) -> None:
    """Flag ONLY the named zero-arg methods on ``obj`` -- not its whole
    interface.

    Each ``_FlagAsMethod`` is one ``GetIDsOfNames`` COM round-trip (~3 ms over
    the out-of-process bridge). ``_flag(comp, "IComponent2")`` flags all ~165
    IComponent2 methods (~0.45 s) -- a steep tax in a loop over every component
    when only one or two zero-arg methods are actually called (issue #87). Flag
    just those instead, so the per-component cost drops to a couple of ms.

    Property reads (``Name2``, ``Transform2`` …) and methods called WITH args
    (``Select2(True, 0)``, ``GetBox(False, False)``) need NO flagging at all --
    drop the flag entirely there rather than calling this. ``_FlagAsMethod`` is
    a pywin32 ``CDispatch`` method, so this needs no gen_py wrapper; unknown
    names raise inside it and are skipped."""
    flag = getattr(obj, "_FlagAsMethod", None)
    if flag is None:
        return
    for name in method_names:
        try:
            flag(name)
        except Exception:
            pass


def _scalar(value: Any) -> Any:
    """An OTel-safe attribute value: scalars pass through, anything else is JSON."""
    if isinstance(value, (bool, int, float, str)):
        return value
    return json.dumps(value, default=str, sort_keys=True)
