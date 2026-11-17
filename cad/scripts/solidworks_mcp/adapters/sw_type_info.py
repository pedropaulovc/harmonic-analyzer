"""
SolidWorks early-bound COM interface resolution (with a flagging fallback).

Primary path — **early binding**: ``early_bound(obj, "IFace2")`` wraps a
pywin32 dispatch in the makepy interface class from a *checked-in* wrapper for
``sldworks.tlb`` (``._generated.sldworks_2026``), so members invoke by DISPID
via ``InvokeTypes`` — no per-name ``GetIDsOfNames`` round-trip. The wrapper is
vendored (not built in each user's ``gen_py`` cache), so startup never depends
on a writable temp dir or typelib discovery through a ROT proxy. Call sites use
``early_bound_or_flag(obj, iface, *fallback_names)`` and **reassign** the result
(``x = early_bound_or_flag(x, ...)``) — the wrapper is a new object.

Off-interface members FAIL LOUD: SW dispatches are polymorphic (a face is an
``IFace2`` and an ``IEntity``; a part model answers ``IModelDoc2`` and
``IPartDoc``), so a call site that reaches for a member the named interface does
not declare must bind the OWNING interface explicitly (``early_bound(obj,
"IEntity").Select2(...)``). ``early_bound`` returns a ``_strict_subclass`` that
raises ``AttributeError`` for any undeclared member instead of silently
degrading it to late binding — task #7 rebound every build/verify call site and
a full cold ``doit`` build proved zero off-interface accesses remain, so a NEW
one is a bug that should crash in development, not quietly pay the late-binding
tax again.

Fallback path — **method flagging**: for interfaces absent from ``sldworks.tlb``
(the undocumented motion methods) or when the wrapper can't load, pywin32's
late-binding sometimes resolves SW zero-argument methods (``GetTitle``,
``GetPathName`` …) as *properties*, so calling them raises ``TypeError:
'str' object is not callable``. ``flag_methods(obj, *interfaces)`` /
``flag_method_names(obj, *names)`` call ``CDispatch._FlagAsMethod(name)`` to
force method (``Invoke``) resolution for names that belong to the object's real
interface. Per-interface (not flag-everything) because each unknown name is a
~5 ms ``GetIDsOfNames`` round-trip and the full TLB has ~6 000 names across 482
interfaces; per-interface flagging is ~1-3 s, whole-object early binding is ~0.

This module:

1. Loads the checked-in makepy wrapper for ``sldworks.tlb`` (``gen_py`` and
   lazy generation remain only as compatibility fallbacks), plus lazily
   generated wrappers for the auxiliary typelibs in ``_AUX_TYPELIBS``
   (``swdimxpert.tlb`` — whose dispatches expose no type info, making this
   wrapper the ONLY way to early-bind them).
2. Builds per-interface sets of method names for the flagging fallback.
3. Exposes ``early_bound`` / ``early_bound_or_flag`` (primary) and
   ``flag_methods`` / ``flag_method_names`` / ``flag_doc`` (fallback).
"""

from __future__ import annotations

import inspect
import threading
import weakref
from pathlib import Path
from typing import Any

from loguru import logger

try:
    import win32com.client  # noqa: F401 — optional Windows dep
    from win32com.client import DispatchBaseClass, gencache

    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False


# SolidWorks type library IID (stable across SW versions).
SW_TLB_IID = "{83A33D31-27C5-11CE-BFD4-00400513BB57}"

# Auxiliary SolidWorks typelibs whose interfaces ``early_bound`` also serves,
# keyed by the .tlb filename next to sldworks.exe, valued by the expected IID.
#
# The DimXpert library is the motivating case: its dispatches expose NO type
# info (``GetTypeInfo`` -> "Invalid index"), so ``win32com.client.Dispatch``
# and ``CastTo`` BOTH silently fall back to a late-bound ``CDispatch`` — and
# every property PUT is then refused (``Property '<unknown>.X' can not be
# set``). Constructing the makepy class generated from ``swdimxpert.tlb``
# around the RAW ``_oleobj_`` is the only binding that works, which is exactly
# what :func:`early_bound` does. Unlike ``sldworks.tlb`` there is no checked-in
# wrapper for these: the module is makepy-generated into the user's ``gen_py``
# cache on first use (~0.1 s), lazily, only when an interface misses the
# primary wrapper — a mock/SolidWorks-free session never pays it.
_AUX_TYPELIBS: dict[str, str] = {
    "swdimxpert.tlb": "{582D0D5B-FF58-42CD-8968-A8A001A52454}",
}

# Loaded aux wrapper modules; None = not yet attempted (lazy). Published only
# AFTER every registered typelib has been attempted (under _aux_lock), so a
# concurrent first lookup never observes a half-built list.
_aux_modules: list[Any] | None = None
_aux_lock = threading.Lock()

# Module state: populated by _load_wrapper() the first time it's needed.
_wrapper_module: Any | None = None
_interface_methods: dict[str, frozenset[str]] = {}
# Per-object record of which interfaces have already been flagged. Keyed by
# id(obj) so ``flag_methods(doc, 'IModelDoc2')`` followed by
# ``flag_methods(doc, 'IAssemblyDoc')`` does incremental work, not a no-op.
# The value carries a weakref to the object so a *new* dispatch landing at a
# recycled address is never mistaken for an already-flagged one — that
# collision left ``GetActiveSketch2`` (etc.) unflagged on fresh documents in
# long sessions, silently degrading them to property reads. Dead entries are
# evicted by the weakref callback.
_flag_cache: dict[int, tuple[weakref.ref[Any], set[str]]] = {}


# Native enum values are read once from the installed constants typelib, not
# the adapter's intentionally small legacy constant table.
_constants: dict[str, int] | None = None
_constants_lock = threading.Lock()


def constant(name: str) -> int:
    """Resolve a named enum from the installed swconst.tlb, cached per process."""
    global _constants
    if _constants is None:
        with _constants_lock:
            if _constants is None:
                if not PYWIN32_AVAILABLE:
                    raise RuntimeError("SolidWorks constants require pywin32")
                import pythoncom

                path = _find_aux_tlb("swconst.tlb")
                if path is None:
                    raise RuntimeError("Installed SolidWorks swconst.tlb not found")
                typelib = pythoncom.LoadTypeLib(str(path))
                values: dict[str, int] = {}
                for index in range(typelib.GetTypeInfoCount()):
                    if typelib.GetTypeInfoType(index) != pythoncom.TKIND_ENUM:
                        continue
                    info = typelib.GetTypeInfo(index)
                    for variable in range(info.GetTypeAttr().cVars):
                        descriptor = info.GetVarDesc(variable)
                        values[info.GetNames(descriptor[0])[0]] = int(descriptor[1])
                _constants = values
    try:
        return _constants[name]
    except KeyError as exc:
        raise RuntimeError(f"SolidWorks named constant unavailable: {name}") from exc


def _cache_entry_for(obj: Any) -> set[str]:
    """Return the flagged-interface set for ``obj``, verifying identity.

    A hit requires the stored weakref to resolve to ``obj`` itself; a stale
    entry from a garbage-collected object at the same address is replaced.
    Objects that cannot be weak-referenced get a fresh (uncached) set each
    call — correct, just without the no-op shortcut.
    """
    obj_id = id(obj)
    entry = _flag_cache.get(obj_id)
    if entry is not None and entry[0]() is obj:
        return entry[1]

    already: set[str] = set()

    def _evict(ref: weakref.ref[Any], obj_id: int = obj_id) -> None:
        current = _flag_cache.get(obj_id)
        if current is not None and current[0] is ref:
            del _flag_cache[obj_id]

    try:
        _flag_cache[obj_id] = (weakref.ref(obj, _evict), already)
    except TypeError:
        pass
    return already


def _load_wrapper() -> None:
    """Load the generated wrapper and extract per-interface method names.

    The checked-in SOLIDWORKS 2026 wrapper is the normal path.  SOLIDWORKS keeps
    existing automation interface IIDs and DISPIDs binary compatible between
    releases, so it can bind those interfaces on older supported seats as well.
    ``gencache`` remains only as a compatibility fallback for an installation
    where the vendored artifact cannot be imported.
    """
    global _wrapper_module, _interface_methods

    if not PYWIN32_AVAILABLE:
        return

    try:
        from ._generated import sldworks_2026

        _wrapper_module = sldworks_2026
    except Exception as exc:
        logger.warning(
            "Checked-in SolidWorks wrapper could not be imported; "
            f"falling back to pywin32 gen_py: {exc}"
        )

    # Compatibility only: reuse an existing per-user wrapper.  Probe common
    # versions because the type-library major changes with each SW release.
    for major in (35, 34, 33, 32, 31, 30) if _wrapper_module is None else ():
        try:
            mod = gencache.GetModuleForTypelib(SW_TLB_IID, 0, major, 0)
        except Exception:
            mod = None
        if mod is not None:
            _wrapper_module = mod
            break

    if _wrapper_module is None:
        # Last resort for unusual installations or damaged package artifacts.
        for major in (35, 34, 33, 32, 31, 30):
            try:
                gencache.EnsureModule(SW_TLB_IID, 0, major, 0)
                _wrapper_module = gencache.GetModuleForTypelib(SW_TLB_IID, 0, major, 0)
                if _wrapper_module is not None:
                    break
            except Exception:
                continue

    if _wrapper_module is None:
        logger.warning(
            "SolidWorks generated wrapper not available; method flagging "
            "disabled. Zero-arg SW methods may raise TypeError. To fix, "
            "run: python -m win32com.client.makepy "
            '"C:\\Program Files\\SOLIDWORKS Corp\\SOLIDWORKS\\sldworks.tlb"'
        )
        return

    # Build per-interface method sets by inspecting each DispatchBaseClass
    # subclass in the wrapper module.
    for name in dir(_wrapper_module):
        cls = getattr(_wrapper_module, name, None)
        if not (inspect.isclass(cls) and issubclass(cls, DispatchBaseClass)):
            continue
        method_names: set[str] = set()
        for attr_name, attr in cls.__dict__.items():
            if attr_name.startswith("_"):
                continue
            if callable(attr):
                method_names.add(attr_name)
        if method_names:
            _interface_methods[name] = frozenset(method_names)

    # Make TYPED returns strict too (see _register_strict_classes).
    _register_strict_classes(_wrapper_module)

    logger.info(
        f"SolidWorks type info loaded: {len(_interface_methods)} interfaces, "
        f"wrapper={_wrapper_module.__name__}"
    )


def _ensure_loaded() -> None:
    """Lazy-load the wrapper on first use."""
    if _wrapper_module is None and PYWIN32_AVAILABLE:
        _load_wrapper()


def _find_aux_tlb(filename: str) -> Path | None:
    """Locate an auxiliary .tlb next to the registered SolidWorks server exe,
    falling back to the conventional install roots."""
    try:
        from . import sw_install

        exe = sw_install.resolve_com_server_path()
    except Exception:
        exe = None
    if exe:
        candidate = Path(exe).parent / filename
        if candidate.is_file():
            return candidate
    hits: list[Path] = []
    for pattern in (
        (Path(r"C:\Program Files\Dassault Systemes"), f"SOLIDWORKS*/SOLIDWORKS/{filename}"),
        (Path(r"C:\Program Files\SOLIDWORKS Corp"), f"SOLIDWORKS/{filename}"),
    ):
        root, glob = pattern
        if root.is_dir():
            hits.extend(sorted(root.glob(glob)))
    return hits[-1] if hits else None


def _load_aux_wrappers() -> list[Any]:
    """makepy-generate (and import) the auxiliary typelib wrappers.

    Lazy and memoized: runs on the first :func:`early_bound` miss against the
    primary wrapper. Best-effort per library — a seat without the .tlb (mock
    mode, no SolidWorks install) simply yields no aux modules, and
    ``early_bound`` then raises its normal unknown-interface ``ValueError``.
    The typelib version is read off the installed file (``LoadTypeLib`` →
    ``GetLibAttr``), never hard-coded, so a SolidWorks upgrade that bumps the
    library version keeps binding without a code change.
    """
    global _aux_modules
    if _aux_modules is not None:
        return _aux_modules
    with _aux_lock:
        if _aux_modules is not None:  # lost the race — another thread finished
            return _aux_modules
        loaded: list[Any] = []
        if not PYWIN32_AVAILABLE:
            _aux_modules = loaded
            return _aux_modules
        import pythoncom

        for filename, expected_iid in _AUX_TYPELIBS.items():
            path = _find_aux_tlb(filename)
            if path is None:
                logger.warning(
                    f"auxiliary typelib {filename} not found; its interfaces are "
                    "unavailable to early_bound"
                )
                continue
            try:
                iid, lcid, _syskind, major, minor, _flags = pythoncom.LoadTypeLib(
                    str(path)
                ).GetLibAttr()
                if str(iid) != expected_iid:
                    logger.warning(
                        f"{filename} reports IID {iid}, expected {expected_iid}; "
                        "binding it anyway"
                    )
                module = gencache.EnsureModule(str(iid), lcid, major, minor)
                if module is None:
                    raise RuntimeError("gencache.EnsureModule returned None")
            except Exception as exc:
                logger.warning(f"auxiliary typelib {filename} failed to load: {exc}")
                continue
            _register_strict_classes(module)
            loaded.append(module)
            logger.info(
                f"auxiliary SolidWorks typelib loaded: {filename} ({module.__name__})"
            )
        _aux_modules = loaded
    return _aux_modules


def _interface_class(interface: str) -> type | None:
    """Resolve an interface name to its makepy class — primary wrapper first,
    then the lazily-loaded auxiliary typelibs."""
    cls = getattr(_wrapper_module, interface, None) if _wrapper_module else None
    if inspect.isclass(cls):
        return cls
    for module in _load_aux_wrappers():
        cls = getattr(module, interface, None)
        if inspect.isclass(cls):
            return cls
    return None


def interface_method_names(interface: str) -> frozenset[str]:
    """Return the set of method names declared by the given SW interface.

    Args:
        interface: Interface name as it appears in the type library
            (e.g. ``"ISldWorks"``, ``"IModelDoc2"``).

    Returns:
        Immutable set of method names, or an empty set if the interface is
        unknown or the wrapper isn't loaded.
    """
    _ensure_loaded()
    return _interface_methods.get(interface, frozenset())


# Interface sets most tool operations need to flag. When acquiring a doc
# dispatch, always flag IModelDoc2 (base) plus the subclass that matches the
# doc type. For the app root, flag ISldWorks.
DOC_TYPE_TO_INTERFACES: dict[int, tuple[str, ...]] = {
    # Values match swDocumentTypes_e: 1=Part, 2=Assembly, 3=Drawing
    1: ("IModelDoc2", "IPartDoc"),
    2: ("IModelDoc2", "IAssemblyDoc"),
    3: ("IModelDoc2", "IDrawingDoc"),
}


def flag_methods(obj: Any, *interfaces: str) -> int:
    """Flag SW methods on ``obj`` so pywin32 dispatches them as methods,
    not properties.

    Safe to call repeatedly on the same object — results are cached by
    ``id(obj)``. Unknown method names are silently skipped (those are
    the ones that don't belong to the object's real interface).

    Args:
        obj: A pywin32 ``CDispatch`` wrapping a SolidWorks COM object.
        *interfaces: One or more interface names whose methods to flag.
            Common values: ``"ISldWorks"``, ``"IModelDoc2"``,
            ``"IAssemblyDoc"``, ``"IPartDoc"``, ``"IDrawingDoc"``.

    Returns:
        Number of methods successfully flagged.
    """
    _ensure_loaded()

    if not _interface_methods or obj is None:
        return 0

    already = _cache_entry_for(obj)

    # Only flag methods from interfaces we haven't already processed for
    # this object. Repeats are a no-op; novel interfaces add incrementally.
    new_interfaces = [i for i in interfaces if i not in already]
    if not new_interfaces:
        return 0

    names: set[str] = set()
    for iface in new_interfaces:
        names.update(_interface_methods.get(iface, ()))

    flagged = 0
    for name in sorted(names):
        try:
            obj._FlagAsMethod(name)
            flagged += 1
        except Exception:
            # Name not on this dispatch's real interface — skip silently.
            pass

    already.update(new_interfaces)
    return flagged


def flag_method_names(obj: Any, *names: str) -> int:
    """Flag only the named ambiguous zero-argument methods on ``obj``.

    Whole-interface flagging is appropriate for long-lived root objects, but
    prohibitively expensive for transient wrappers returned by drawing and
    feature-tree walks.  This helper performs one ``GetIDsOfNames`` round trip
    per requested name and caches successful or failed attempts per object.

    Args:
        obj: A pywin32 ``CDispatch`` wrapping a SolidWorks COM object.
        *names: Exact method names to pass to ``_FlagAsMethod``.

    Returns:
        Number of names successfully flagged.
    """
    if obj is None:
        return 0
    flag = getattr(obj, "_FlagAsMethod", None)
    if not callable(flag):
        return 0

    already = _cache_entry_for(obj)
    flagged_count = 0
    for name in names:
        cache_key = f"@method:{name}"
        if cache_key in already:
            continue
        try:
            flag(name)
            flagged_count += 1
        except Exception:
            pass
        already.add(cache_key)
    return flagged_count


def flagged(obj: Any, *interfaces: str) -> Any:
    """Flag ``obj``'s methods then return ``obj`` — call-chain friendly.

    Useful for inline flagging of short-lived dispatches::

        config = sw_type_info.flagged(
            model.GetActiveConfiguration(), "IConfiguration"
        )
        name = config.GetName()

    If ``obj`` is ``None`` (e.g. SW returned Nothing), passes through
    unchanged.
    """
    if obj is not None:
        flag_methods(obj, *interfaces)
    return obj


# Cache of strict subclasses keyed by their makepy base class, so every
# ``early_bound(obj, "IFace2")`` reuses one generated subclass rather than
# minting a new type per call.
_strict_classes: dict[type, type] = {}


def _strict_subclass(base: type) -> type:
    """Return a subclass of the makepy interface ``base`` that FAILS LOUD for any
    member ``base`` does not declare.

    Why this exists: a makepy interface class exposes ONLY the members the type
    library lists for that one interface, and its ``__getattr__`` /
    ``__setattr__`` raise ``AttributeError`` for anything else. Real SW dispatches
    are polymorphic — a face is an ``IFace2`` AND an ``IEntity`` (``Select2``
    lives on the latter); a part model answers both ``IModelDoc2`` and
    ``IPartDoc`` (``GetBodies2`` lives on the latter). An earlier design degraded
    such off-interface members to a lazily-built late-bound dispatch so call sites
    could mix interfaces freely on one object.

    Task #7 removed that fallback: every build/verify call site was rebound to the
    interface that DECLARES the member it calls, and a full cold ``doit`` build
    proved zero off-interface accesses remain. So this subclass now RAISES
    ``AttributeError`` (naming the interface and member) for an undeclared member
    instead of silently reintroducing late binding — a new off-interface access is
    a bug (a missed rebind, or a regression) that should crash in development
    rather than quietly pay the per-name ``GetIDsOfNames`` tax again. The fix is
    always to bind the OWNING interface at the call site:
    ``early_bound(obj, "IEntity").Select2(...)``.

    The subclass keeps DISPID-fast ``InvokeTypes`` for every DECLARED member
    (normal attribute lookup finds real methods; declared properties go through
    the base ``__getattr__``); only an UNDECLARED member is rejected.
    """
    cached = _strict_classes.get(base)
    if cached is not None:
        return cached

    class _EarlyBoundStrict(base):  # type: ignore[valid-type, misc]
        def __getattr__(self, attr: str) -> Any:
            # Reached only when normal lookup misses (declared methods and the
            # __dict__ entry _oleobj_ never get here).
            # Reject every underscore/dunder name WITHOUT a COM round-trip: these
            # are Python probes (pickle, copy, IPython canaries) and, critically,
            # ``getattr(obj, "_FlagAsMethod", None)`` — a strict wrapper must miss
            # that probe so a caller never mistakes it for a raw late-bound object.
            if attr.startswith("_"):
                raise AttributeError(attr)
            # Declared property on THIS interface: let makepy resolve it fast.
            try:
                return base.__getattr__(self, attr)
            except AttributeError:
                pass
            # Off-interface member: FAIL LOUD. The live dispatch may well answer
            # ``attr`` through a different interface, but binding it here would
            # silently reintroduce late binding. Rebind the CALL SITE to the
            # interface that declares ``attr`` instead.
            raise AttributeError(
                f"{base.__name__} does not declare {attr!r}. The dispatch may "
                f"expose it through another interface — bind that interface at the "
                f"call site (e.g. early_bound(obj, '<IOwningInterface>').{attr}"
                f"(...)); the late-binding fallback was removed in task #7."
            )

        def __setattr__(self, attr: str, value: Any) -> None:
            # Internal dunder/underscore attrs go straight to __dict__ so they are
            # never forwarded onto the COM object.
            if attr.startswith("_"):
                self.__dict__[attr] = value
                return
            try:
                base.__setattr__(self, attr, value)
            except AttributeError:
                raise AttributeError(
                    f"{base.__name__} does not declare a settable {attr!r}. Rebind "
                    f"the call site to the owning interface; the late-binding "
                    f"fallback was removed in task #7."
                ) from None

    _EarlyBoundStrict.__name__ = f"{base.__name__}_EarlyBound"
    _EarlyBoundStrict.__qualname__ = _EarlyBoundStrict.__name__
    _strict_classes[base] = _EarlyBoundStrict
    return _EarlyBoundStrict


def _register_strict_classes(module: Any) -> None:
    """Make TYPED COM returns construct the strict subclass, not the plain
    makepy class.

    Importing the wrapper runs ``RegisterCLSIDsFromDict(CLSIDToClassMap)``, a
    process-global map pywin32 consults whenever it wraps a dispatch that has a
    declared return interface (a ``returnCLSID`` on a method, or an element of a
    dispatch array). So the canonical multi-interface objects arrive as PLAIN
    wrappers: ``OpenDoc6``/``NewDocument`` → ``IModelDoc2`` (which is the *only*
    interface on ``adapter.currentModel``, yet the code calls
    ``IPartDoc.GetBodies2`` / ``IDrawingDoc.GetCurrentSheet`` on it),
    ``Extension`` → ``IModelDocExtension``, ``GetCurrentSheet`` → ``ISheet`` … On
    a plain wrapper an off-interface member raises ``AttributeError`` (or, when
    swallowed by an ``_attempt`` wrapper, silently returns a default) — the exact
    hazard task #7's rebinds eliminated.

    Re-registering every CLSID to a :func:`_strict_subclass` makes those typed
    returns behave identically to objects :func:`early_bound` wraps from a raw
    ``CDispatch``: a declared member is DISPID-fast, an undeclared member raises a
    LOUD ``AttributeError`` naming the interface — so a stray off-interface access
    on a typed return crashes in development instead of quietly late-binding (or
    silently defaulting through ``_attempt``). It also makes the
    ``isinstance(obj, cls)`` short-circuit in :func:`early_bound` correct: a typed
    return is already a strict subclass, so re-binding it to its own interface is
    a genuine no-op rather than a missed upgrade.

    NOTE (documented side effect): this is process-global — after the wrapper
    loads, ANY ``win32com.client.Dispatch`` of a SolidWorks object in this
    process returns a strict subclass. That is the intent (uniform fail-loud early
    binding), not an accident.
    """
    try:
        from win32com.client import CLSIDToClass
    except Exception:
        return
    mapping = getattr(module, "CLSIDToClassMap", None)
    if not mapping:
        return
    for clsid, cls in list(mapping.items()):
        if inspect.isclass(cls) and issubclass(cls, DispatchBaseClass):
            try:
                CLSIDToClass.RegisterCLSID(clsid, _strict_subclass(cls))
            except Exception:
                # Best-effort: a class that won't re-register just keeps its
                # plain wrapper; early_bound() still upgrades it on a cross-cast.
                pass


def early_bound(obj: Any, interface: str) -> Any:
    """Wrap a late-bound dispatch in its early-bound interface class.

    pywin32 late binding resolves members through SolidWorks's
    ``IDispatch::GetIDsOfNames``. A handful of methods are present in the
    type library (and the vtable) but **absent from that name table**, so a
    by-name call raises ``com_error -2147352573 ('Member not found')`` even
    though the method exists — ``IModelDocExtension::GetMotionStudyManager``
    is the known case. The early-bound wrapper class generated by makepy
    invokes by **dispid** (``InvokeTypes``), which bypasses the name lookup
    and works. It also drops the per-name ``GetIDsOfNames``/``_FlagAsMethod``
    round-trips that ``flag_methods`` needs (~155 ms/object) — the whole
    point of the migration.

    This reuses the already-loaded gen_py wrapper module, so the dispid comes
    from the type library for the connected SW version — nothing is
    hard-coded. The wrapper is constructed from the raw ``_oleobj_`` (passing
    the ``CDispatch`` itself drops the underlying IDispatch and breaks
    ``InvokeTypes``).

    The returned wrapper is a :func:`_strict_subclass` of the makepy class, so a
    member from a DIFFERENT interface on the same dispatch (``IFace2``'s
    ``Select2`` from ``IEntity``; a part model's ``GetBodies2`` from ``IPartDoc``)
    raises a LOUD ``AttributeError`` rather than silently late-binding. Task #7
    rebound every call site to the interface that declares the member it calls, so
    a surviving off-interface access is a bug — bind the owning interface at that
    call site (``early_bound(obj, "IEntity").Select2(...)``).

    Args:
        obj: A pywin32 ``CDispatch`` wrapping a SolidWorks COM object.
        interface: Interface name as it appears in the type library
            (e.g. ``"IModelDocExtension"``).

    Returns:
        The early-bound wrapper exposing dispid-fast declared members, or
        ``obj`` unchanged when the wrapper module is unavailable or ``obj``
        is a mock/test double without a raw ``_oleobj_``.

    Raises:
        RuntimeError: The generated interface class exists but cannot wrap the
            object's raw dispatch. This is a real binding failure; returning
            the late-bound object would hide the regression and restore the
            per-member COM name-lookup cost this helper exists to remove.
    """
    _ensure_loaded()
    if obj is None or _wrapper_module is None:
        return obj
    cls = _interface_class(interface)
    if cls is None:
        # The wrapper IS loaded but the requested interface is absent from it
        # AND from every auxiliary typelib — a wrong name or an incomplete
        # wrapper. Fail loud rather than silently return an unwrapped dispatch
        # that breaks with a confusing error much later.
        raise ValueError(
            f"early_bound: interface {interface!r} is not defined in the loaded "
            f"SolidWorks wrapper ({getattr(_wrapper_module, '__name__', '?')}) "
            f"or any auxiliary typelib ({', '.join(sorted(_AUX_TYPELIBS))}). "
            "Check the interface name against the type library, or regenerate the "
            "checked-in wrapper after a SolidWorks version upgrade."
        )
    oleobj = getattr(obj, "_oleobj_", None)
    if oleobj is None:
        # Not a real COM dispatch (a mock/test double) — nothing to wrap.
        return obj
    if isinstance(obj, cls):
        return obj
    try:
        return _strict_subclass(cls)(oleobj)
    except Exception as exc:
        raise RuntimeError(
            f"early_bound: failed to construct {interface!r} from "
            f"{type(obj).__name__} using the loaded SolidWorks wrapper "
            f"({getattr(_wrapper_module, '__name__', '?')})"
        ) from exc


def is_early_bound(obj: Any, interface: str) -> bool:
    """Return whether ``obj`` already uses the generated interface wrapper."""
    _ensure_loaded()
    if obj is None or _wrapper_module is None:
        return False
    cls = _interface_class(interface)
    return bool(cls is not None and isinstance(obj, cls))


# swSketchSegments_e value -> the derived ``ISketch*`` interface that DECLARES
# the segment's point accessors (``GetStartPoint2``/``GetEndPoint2``/
# ``GetCenterPoint2``/``GetStartPoint``/``GetEndPoint`` …). swSketchTEXT (4) and
# swSketchPARABOLA (5) carry no such accessors and are left as ISketchSegment.
_SKETCH_SEGMENT_INTERFACE: dict[int, str] = {
    0: "ISketchLine",  # swSketchLINE
    1: "ISketchArc",  # swSketchARC (also full circles)
    2: "ISketchEllipse",  # swSketchELLIPSE
    3: "ISketchSpline",  # swSketchSPLINE
}


def concrete_sketch_segment(obj: Any) -> Any:
    """Re-bind a sketch segment from base ``ISketchSegment`` to its derived class.

    makepy wraps ``CreateLine``/``CreateArc``/… results as the *base*
    ``ISketchSegment``, whose generated class does NOT expose the derived point
    accessors (``GetStartPoint2``, ``GetCenterPoint2``, …) — those live on
    ``ISketchLine`` / ``ISketchArc`` / …. ``ISketchSegment.GetType()`` names the
    concrete type (``swSketchSegments_e``), so this re-binds ``obj`` to the
    matching generated interface, where the accessors are declared DISPID
    methods — the pattern the ``swSketchSegments_e`` Remarks prescribe ("obtain
    the appropriate derived class … and call the appropriate derived class
    functions"). Non-segment dispatches (or a session without the wrapper) pass
    through unchanged.

    Args:
        obj: A pywin32 dispatch for a sketch segment (line/arc/circle/spline/
            ellipse), typically the base ``ISketchSegment`` makepy wrapper.

    Returns:
        The segment re-bound to its derived interface, or the base
        ``ISketchSegment`` for the point-less types (``swSketchTEXT`` /
        ``swSketchPARABOLA``). Raises rather than silently returning an
        unusable base wrapper when the segment type cannot be read.
    """
    segment = early_bound(obj, "ISketchSegment")
    if not is_early_bound(segment, "ISketchSegment"):
        return obj  # wrapper module not loaded (mock/degraded) — leave untouched
    seg_type = int(segment.GetType())
    interface = _SKETCH_SEGMENT_INTERFACE.get(seg_type)
    return early_bound(obj, interface) if interface else segment


# swDocumentTypes_e value -> the concrete document interface that DECLARES the
# doc-type-specific members (``FeatureByName``, ``GetComponents``,
# ``GetFirstView`` …) that ``IModelDoc2`` does NOT. ``currentModel`` is always
# bound to ``IModelDoc2`` (``io._bind_document``), so such a member must be
# reached through the matching derived interface.
_DOCUMENT_INTERFACE: dict[int, str] = {
    1: "IPartDoc",  # swDocPART
    2: "IAssemblyDoc",  # swDocASSEMBLY
    3: "IDrawingDoc",  # swDocDRAWING
}


def early_bound_doc(obj: Any) -> Any:
    """Re-bind a model dispatch to its concrete document interface.

    ``IModelDoc2`` does not declare the doc-type-specific members
    (``FeatureByName``, ``GetComponents``, ``GetFirstView`` …); those live on
    ``IPartDoc`` / ``IAssemblyDoc`` / ``IDrawingDoc``. ``currentModel`` is always
    bound to ``IModelDoc2`` (``io._bind_document``), so calling such a member on
    it resolves through the late-bound fallback. ``IModelDoc2.GetType()`` names
    the document type (``swDocumentTypes_e``), so this re-binds ``obj`` to the
    matching derived interface — where the member is a declared DISPID method.
    Non-document dispatches (or a session without the wrapper) pass through
    unchanged.

    Args:
        obj: A pywin32 dispatch for a SolidWorks document (part/assembly/
            drawing), typically ``adapter.currentModel`` (``IModelDoc2``) or a
            ``IComponent2.GetModelDoc2()`` result.

    Returns:
        The model re-bound to its derived document interface, or the object
        unchanged when the wrapper module is unavailable (mock/degraded) or the
        document type is unknown.
    """
    model = early_bound(obj, "IModelDoc2")
    if not is_early_bound(model, "IModelDoc2"):
        return obj  # wrapper module not loaded (mock/degraded) — leave untouched
    interface = _DOCUMENT_INTERFACE.get(int(model.GetType()))
    return early_bound(obj, interface) if interface else model


def early_bound_or_flag(obj: Any, interface: str, *method_names: str) -> Any:
    """Use the generated interface, or selectively flag exact fallback methods."""
    typed = early_bound(obj, interface)
    if typed is obj and not is_early_bound(obj, interface):
        flag_method_names(obj, *method_names)
    return typed


def flag_doc(obj: Any, doc_type: int) -> int:
    """Flag methods for a SolidWorks document dispatch given its type.

    Convenience wrapper around ``flag_methods`` that looks up the correct
    interface list for the document type.

    Args:
        obj: ``CDispatch`` wrapping the document.
        doc_type: Value returned by ``swDoc.GetType()`` — 1=Part, 2=Assembly,
            3=Drawing.

    Returns:
        Number of methods flagged.
    """
    interfaces = DOC_TYPE_TO_INTERFACES.get(doc_type, ("IModelDoc2",))
    return flag_methods(obj, *interfaces)


def invalidate_flag_cache(obj: Any | None = None) -> None:
    """Forget that ``obj`` has been flagged, or clear the cache entirely.

    Address reuse by a *different* object is detected automatically (the
    cache stores a weakref and verifies identity), so this is only needed
    when the same live dispatch must be re-flagged — e.g. after its gen_py
    wrapper state was rebuilt.
    """
    if obj is None:
        _flag_cache.clear()
    else:
        _flag_cache.pop(id(obj), None)
