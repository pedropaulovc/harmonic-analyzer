"""COM-conversation record/replay at pywin32's ``_oleobj_`` boundary.

EXPERIMENT BRANCH ONLY (``experiment/com-replay-20261110``): never merge.

A build reaches SolidWorks only through pywin32 interface objects: the raw
``PyIDispatch`` behind every generated wrapper (``wrapper._oleobj_``), every
``CDispatch`` and every bare dispatch ``_com._com_invoke`` walks. This module
interposes one proxy per interface object at that boundary and either

* RECORDS every operation on it (``InvokeTypes``, ``Invoke``,
  ``QueryInterface``, ``GetIDsOfNames``, ``GetTypeInfo``, identity
  comparison, and any method of a non-dispatch interface such as
  ``ITypeInfo``) as one :class:`Call` with canonical arguments and response, or
* REPLAYS a recorded log with SolidWorks absent: the ``k``-th recipe request
  must equal the recorded ``k``-th recipe request exactly (after the declared
  provenance mask) and is then answered with the recorded response, in which a
  string equal to a masked recorded value is served as the value this replay
  wrote (a readback of the Generator stamp). The first mismatch is sticky and
  raised as :class:`ReplayStop`, a ``BaseException`` so the adapter's
  ``except Exception`` fallbacks cannot swallow it.

Every call carries its :class:`Origin`. A call made while a function of a
recipe-inert module (``_buildgraph.RECIPE_INERT_MODULES``) runs is INERT: for
the recording or replay window those modules' functions are wrapped so their
dynamic extent sets a context variable, an O(1) test per call instead of a
stack walk. ``check:inert`` proves such code only observes (no COM mutator
before a save, pinned call sites whose results the build discards), so its
requests are not part of the no-op claim. Replay serves them best-effort from
the recorded inert calls by exact request, in any order, and answers an
unrecorded one with ``E_FAIL``; their handles come from a separate (negative)
range, so inert activity cannot renumber the objects recipe requests name.
A call reaching an inert function through a reference bound before the window
opened stays RECIPE: the conservative direction (strict order), never a hidden
request. :class:`CallerCapture` decides how much of the Python caller (the
nearest frames outside this module, pywin32 and the makepy wrappers) a recording
keeps; a replay names the caller of a divergence regardless.

Files SolidWorks writes during the window are kept gzip-compressed beside the
log (``<log>.files/<seq>/<rel>.gz``, digest of the uncompressed bytes) and
restored by the replay at the same point. A replay may import changed helper
modules from an overlay directory placed first on ``sys.path``
(:func:`use_overlay`); the log pins only the engine, the declared environment
and the external files COM arguments name, never Python source.

pywin32 recognises its own interface objects by ``isinstance(...,
PyIDispatchType)``; that C type cannot be subclassed, so :func:`funnel`
patches the three pywin32 functions that make that decision
(``DispatchBaseClass.__init__``, ``win32com.client._get_good_single_object_``
and ``dynamic.CDispatch._get_good_single_object_``) to treat a proxy exactly
like the object it stands for, including the ``QueryInterface`` a generated
class runs in its constructor. The patches defer to the originals for
anything that is not a proxy.

Canonical form: floats as ``float.hex`` (bitwise equality), strings with the
redirected output root and the repository root replaced by placeholders,
tuples/lists/VARIANTs/byte arrays tagged, interface objects as handles
allocated in first-returned order. Equality is exact; there is no tolerance.

Replay is offline by construction (:class:`Sandbox`): every Python route that
creates or attaches to a COM server raises, and an audit hook refuses writes
inside the repository outside the scratch output root.

Nothing in a part/assembly/drawing recipe closure imports this module
(``test_com_conversation`` asserts it), so it re-keys no recipe. Design:
``reconcile-adapter-design.md`` sections 1 and 3.1.
"""

from __future__ import annotations

import base64
import contextlib
import contextvars
import datetime
import functools
import gc
import gzip
import hashlib
import importlib
import inspect
import itertools
import json
import os
import re
import shutil
import sys
import threading
import time
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

SCHEMA = 1
ENGINE_FILE = Path(__file__).resolve()
REPO_ROOT = ENGINE_FILE.parents[2]
EXIT_REPLAY_NOT_NOOP = 91
# The only process inputs read inside part closures besides files (design Q5).
ENVIRONMENT_KEYS = ("PYTHONHASHSEED", "HARMONIC_FASTENER_ROWS", "HARMONIC_FIT_GROUPS")
# Leading arguments of each pywin32 dispatch op that identify the member
# (dispid, lcid, flags, return type[, arg types]); interned once per log.
_HEADER_WIDTH = {"InvokeTypes": 5, "Invoke": 4}
# gzip level of the kept SolidWorks-written files: _artifact_cache._PACK_LEVEL,
# so log-plus-captures bytes compare like with like against the output archive.
_CAPTURE_LEVEL = 6


class Mode(StrEnum):
    RECORD = "record"
    REPLAY = "replay"


class Kind(StrEnum):
    CALL = "call"
    GET = "get"
    PUT = "put"
    QI = "qi"
    IDS = "ids"
    TYPEINFO = "typeinfo"
    EQ = "eq"
    METHOD = "method"
    ADOPT = "adopt"


class Phase(StrEnum):
    TREE = "tree"
    DECORATION = "decoration"
    READ = "read"
    OUTPUT = "output"


class Verdict(StrEnum):
    NOOP = "noop"
    DIVERGED = "diverged"
    EXHAUSTED = "exhausted"
    UNCONSUMED = "unconsumed"
    INPUT_MISMATCH = "input_mismatch"
    SANDBOX = "sandbox"
    ERROR = "error"


class Side(StrEnum):
    REQUEST = "request"
    RESPONSE = "response"
    LENGTH = "length"


class Field(StrEnum):
    """Which part of a call differs."""

    OP = "op"
    MEMBER = "member"
    HANDLE = "handle"
    ARGS = "args"
    RESULT = "result"
    RAISED = "raised"
    OUTS = "outs"
    LENGTH = "length"


class Origin(StrEnum):
    """Who issued a call: build code, or a recipe-inert module (observation
    only, enforced by ``check:inert``)."""

    RECIPE = "recipe"
    INERT = "inert"


class GuardMode(StrEnum):
    WARN = "warn"
    RAISE = "raise"


class CallerCapture(StrEnum):
    """How much of the Python caller a recording keeps per call."""

    OFF = "off"  # none, and a replay names no caller either
    DIVERGENCE_ONLY = "divergence"  # the log keeps none; a replay names its own
    FULL = "full"  # every logged call carries its caller frames


# The cheap default: a log carries no caller frames (a FULL lookup cost 10-11 us
# per call offline on the real arm-plate replay stacks); a replay names its
# own caller at a divergence.
DEFAULT_CALLERS = CallerCapture.DIVERGENCE_ONLY


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Call:
    """One operation on one interface object."""

    seq: int
    handle: int
    op: str
    args: list[Any]
    site: str
    result: Any = None
    raised: Any = None
    outs: list[Any] | None = None
    foreign_thread: bool = False
    origin: Origin = Origin.RECIPE
    caller: str = ""

    @property
    def kind(self) -> Kind:
        return kind_of(self.op, self.args)

    def request(self) -> dict[str, Any]:
        return {
            "h": self.handle,
            "op": self.op,
            "args": self.args,
            "site": self.site,
            "caller": self.caller,
            "origin": self.origin.value,
        }

    def to_json(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "kind": self.kind.value,
            **self.request(),
            "result": self.result,
            "raised": self.raised,
            "outs": self.outs,
        }


@dataclass(frozen=True, slots=True)
class Header:
    schema: int
    label: str
    script: str
    script_sha256: str
    engine: str
    sw_revision: str | None
    environment: dict[str, str | None]
    provenance_mask: list[dict[str, str]]
    adapter_state: dict[str, Any]
    roots: dict[str, str]
    started_utc: str

    def to_json(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__slots__}

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Header:
        return cls(**{name: data[name] for name in cls.__slots__})


@dataclass(frozen=True, slots=True)
class Divergence:
    """Where a request stream stops matching: ``index`` in the recipe stream,
    ``seq`` the recorded call's log position (``None`` past its end)."""

    index: int
    seq: int | None
    side: Side
    field: Field
    expected: dict[str, Any] | None
    actual: dict[str, Any] | None
    phase: Phase | None
    last_tree_seq_base: int | None
    feature: str | None
    context: list[dict[str, Any]]

    def to_json(self) -> dict[str, Any]:
        expected = self.expected or {}
        actual = self.actual or {}
        return {
            "index": self.index,
            "seq": self.seq,
            "side": self.side.value,
            "field": self.field.value,
            "member_expected": expected.get("site"),
            "member_actual": actual.get("site"),
            "kind": expected.get("kind") or actual.get("kind"),
            "caller_expected": expected.get("caller"),
            "caller_actual": actual.get("caller"),
            "phase": self.phase.value if self.phase else None,
            "phase_basis": "heuristic member-verb classifier",
            "last_tree_seq_base": self.last_tree_seq_base,
            "feature": self.feature,
            "feature_basis": "last IFeature.Name put at or before index in the base",
            "expected": self.expected,
            "actual": self.actual,
            "context": self.context,
        }


@dataclass(frozen=True, slots=True)
class ReplayResult:
    verdict: Verdict
    divergence: Divergence | None
    served: int
    recorded: int
    seconds: float
    com_outputs: dict[str, str]
    py_outputs: dict[str, str]
    details: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "divergence": self.divergence.to_json() if self.divergence else None,
            "served": self.served,
            "recorded": self.recorded,
            "seconds": self.seconds,
            "com_outputs": self.com_outputs,
            "py_outputs": self.py_outputs,
            **self.details,
        }


@dataclass(frozen=True, slots=True)
class Conversation:
    header: Header
    calls: list[Call]
    trailer: dict[str, Any]


class ReplayStop(BaseException):
    """The replay cannot continue (divergence, exhaustion, unservable answer).

    A ``BaseException`` so ``except Exception`` fallbacks in the adapter
    (``_attempt``) cannot turn a divergence into a default value."""

    def __init__(self, verdict: Verdict, divergence: Divergence | None, reason: str):
        super().__init__(f"{verdict.value}: {reason}")
        self.verdict = verdict
        self.divergence = divergence
        self.reason = reason


class SandboxViolation(BaseException):
    """A replay tried to reach a live COM server or write outside its scratch."""


# ---------------------------------------------------------------------------
# Provenance mask
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MaskRule:
    """Mask string arguments matching ``pattern`` in a request that also
    carries the exact string ``marker`` (the property name being written)."""

    name: str
    marker: str
    pattern: re.Pattern[str]

    def to_json(self) -> dict[str, str]:
        return {
            "name": self.name,
            "marker": self.marker,
            "pattern": self.pattern.pattern,
        }


# The one declared provenance entry: the Generator custom property written by
# _part_properties.part_properties ("harmonic-analyzer @ <git sha>[-dirty]").
# Replay treats a mask as a substitution, not an ignore: when a masked request
# matches, the recorded value is bound to the value this replay wrote, and a
# later served response string EQUAL to the recorded value is served as the
# replay's value (apply_custom_properties reads every property back and raises
# on mismatch). Equality, never substring: a readback returns exactly what was
# written; a longer string that merely contains it is not the masked write.
PROVENANCE_MASK: tuple[MaskRule, ...] = (
    MaskRule("Generator", "Generator", re.compile(r"harmonic-analyzer @ \S+")),
)


def _masked(args: list[Any], mask: Sequence[MaskRule]) -> list[Any]:
    for rule in mask:
        if rule.marker not in args:
            continue
        args = [
            f"<masked:{rule.name}>"
            if isinstance(a, str) and rule.pattern.fullmatch(a)
            else a
            for a in args
        ]
    return args


# ---------------------------------------------------------------------------
# Exact structural equality (True != 1, list != tuple tag, float by hex)
# ---------------------------------------------------------------------------


def same(a: Any, b: Any) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    return a == b


def kind_of(op: str, args: Sequence[Any]) -> Kind:
    if op in _HEADER_WIDTH:
        flags = args[2] if len(args) > 2 and type(args[2]) is int else 1
        if flags & (4 | 8):
            return Kind.PUT
        if flags == 2:
            return Kind.GET
        return Kind.CALL
    return {
        "QueryInterface": Kind.QI,
        "GetIDsOfNames": Kind.IDS,
        "GetTypeInfo": Kind.TYPEINFO,
        "GetTypeInfoCount": Kind.TYPEINFO,
        "__eq__": Kind.EQ,
        "__hash__": Kind.EQ,
        "__ne__": Kind.EQ,
        "ADOPT": Kind.ADOPT,
    }.get(op, Kind.METHOD)


_OUTPUT_VERBS = ("Save", "Export")
_DECORATION_WORDS = (
    "Property",
    "Material",
    "Tolerance",
    "Appearance",
    "Color",
    "Summary",
)
_READ_VERBS = ("Get", "Is", "First", "Next", "Count", "Has")


def classify(site: str, kind: Kind) -> Phase:
    """Heuristic phase of a member (used only to describe a divergence)."""
    iface, _, member = site.rpartition(".")
    if member.startswith(_OUTPUT_VERBS):
        return Phase.OUTPUT
    if iface in ("ICustomPropertyManager", "ISummaryInfo") or any(
        word in member for word in _DECORATION_WORDS
    ):
        return Phase.DECORATION
    if kind in (
        Kind.GET,
        Kind.QI,
        Kind.IDS,
        Kind.TYPEINFO,
        Kind.EQ,
    ) or member.startswith(_READ_VERBS):
        return Phase.READ
    return Phase.TREE


# ---------------------------------------------------------------------------
# pywin32 facts (imported lazily so --help and the offline CLI need no pywin32)
# ---------------------------------------------------------------------------


class _Pywin32:
    """Lazily imported pywin32 types the codec and patches need."""

    def __init__(self) -> None:
        import pythoncom
        import pywintypes
        import win32com.client
        import win32com.client.dynamic

        self.pythoncom = pythoncom
        self.pywintypes = pywintypes
        self.client = win32com.client
        self.dynamic = win32com.client.dynamic
        self.dispatch_type = pythoncom.TypeIIDs[pythoncom.IID_IDispatch]
        self.unknown_type = pythoncom.TypeIIDs[pythoncom.IID_IUnknown]
        self.interface_types = set(pythoncom.TypeIIDs.values())
        self.sentinels = {
            id(getattr(pythoncom, name)): name
            for name in ("Missing", "Empty", "ArgNotFound", "Nothing")
        }
        self.variant = win32com.client.VARIANT
        self.com_error = pywintypes.com_error
        self.iid_type = pywintypes.IIDType


_PYWIN32: _Pywin32 | None = None


def _pw() -> _Pywin32:
    global _PYWIN32
    if _PYWIN32 is None:
        _PYWIN32 = _Pywin32()
    return _PYWIN32


# Fake interface types registered by offline tests: type -> (dispatch?, unknown?).
_FAKE_INTERFACES: dict[type, tuple[bool, bool]] = {}


def register_interface_type(cls: type, *, dispatch: bool = True) -> None:
    """Declare ``cls`` (a test stand-in for a pywin32 interface type) as an
    interface object the funnel must proxy."""
    _FAKE_INTERFACES[cls] = (dispatch, True)


def is_interface(value: Any) -> bool:
    cls = type(value)
    if cls in _FAKE_INTERFACES:
        return True
    return _PYWIN32 is not None and cls in _PYWIN32.interface_types


def _type_facts(value: Any) -> dict[str, Any]:
    cls = type(value)
    if cls in _FAKE_INTERFACES:
        dispatch, unknown = _FAKE_INTERFACES[cls]
    else:
        pw = _pw()
        dispatch = isinstance(value, pw.dispatch_type)
        unknown = isinstance(value, pw.unknown_type)
    methods = sorted(
        name
        for name in dir(cls)
        if not name.startswith("_") and callable(getattr(cls, name, None))
    )
    return {"methods": methods, "dispatch": dispatch, "unknown": unknown}


_METHOD_SETS: dict[tuple[str, ...], frozenset[str]] = {}


def _method_set(methods: Sequence[str]) -> frozenset[str]:
    key = tuple(methods)
    found = _METHOD_SETS.get(key)
    if found is None:
        found = _METHOD_SETS[key] = frozenset(key)
    return found


def _oleobj_of(value: Any) -> Any:
    """``value._oleobj_`` without running a ``__getattr__`` (which on a
    ``CoClassBaseClass`` or a ``CDispatch`` could itself be a COM call)."""
    inner = getattr(value, "__dict__", None)
    if inner is not None and "_oleobj_" in inner:
        return inner["_oleobj_"]
    slot = (
        type(value).__dict__.get("_oleobj_")
        if hasattr(type(value), "__dict__")
        else None
    )
    if slot is not None and hasattr(slot, "__get__") and not callable(slot):
        return getattr(value, "_oleobj_", None)
    return None


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Roots:
    """The run's redirected output root and the repository root.

    ``encode`` replaces them (either separator style, any case) with
    ``<OUT>``/``<OUT/>``/``<REPO>``/``<REPO/>``; ``decode`` substitutes this
    run's roots back. The out root is matched first: it lives under the repo."""

    out: Path
    repo: Path = REPO_ROOT

    def __post_init__(self) -> None:
        def pattern(text: str) -> re.Pattern[str]:
            return re.compile(re.escape(text) + r"(?=$|[\\/\"';,|\s])", re.IGNORECASE)

        out, repo = Path(self.out), Path(self.repo)
        object.__setattr__(
            self,
            "_subs",
            (
                (pattern(str(out)), "<OUT>"),
                (pattern(out.as_posix()), "<OUT/>"),
                (pattern(str(repo)), "<REPO>"),
                (pattern(repo.as_posix()), "<REPO/>"),
            ),
        )
        object.__setattr__(
            self,
            "_back",
            (
                ("<OUT/>", out.as_posix()),
                ("<OUT>", str(out)),
                ("<REPO/>", repo.as_posix()),
                ("<REPO>", str(repo)),
            ),
        )
        object.__setattr__(self, "_shortest", min(len(str(out)), len(str(repo))))

    def encode(self, text: str) -> str:
        if len(text) < self._shortest:  # type: ignore[attr-defined]
            return text
        for regex, placeholder in self._subs:  # type: ignore[attr-defined]
            text = regex.sub(placeholder, text)
        return text

    def decode(self, text: str) -> str:
        if "<" not in text:
            return text
        for placeholder, value in self._back:  # type: ignore[attr-defined]
            text = text.replace(placeholder, value)
        return text

    def out_relative(self, canonical: str) -> str | None:
        for placeholder in ("<OUT>", "<OUT/>"):
            if canonical.startswith(placeholder):
                rest = canonical[len(placeholder) :].lstrip("\\/")
                return rest.replace("\\", "/") if rest else None
        return None


def _looks_absolute(text: str) -> bool:
    return len(text) > 3 and (text[1:3] in (":\\", ":/") or text.startswith("\\\\"))


def _out_relatives(roots: Roots, canonical: Iterable[Any]) -> list[str]:
    """Output-root-relative paths among canonical arguments (nested too)."""
    found: list[str] = []
    for value in canonical:
        if isinstance(value, dict) and ("t" in value or "l" in value):
            found.extend(_out_relatives(roots, value.get("t", value.get("l"))))
            continue
        if type(value) is str:
            relative = roots.out_relative(value)
            if relative is not None:
                found.append(relative)
    return found


def _signature(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return (stat.st_size, stat.st_mtime_ns) if path.is_file() else None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with _ENGINE_IO, path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class _EngineIO(threading.local):
    """Marks the engine's own file I/O so the audit observers ignore it."""

    active = 0

    def __enter__(self) -> None:
        self.active += 1

    def __exit__(self, *exc: object) -> None:
        self.active -= 1


_ENGINE_IO = _EngineIO()


# ---------------------------------------------------------------------------
# Proxies
# ---------------------------------------------------------------------------


class ComProxy:
    """Stands in for one pywin32 interface object at the ``_oleobj_`` boundary."""

    __slots__ = (
        "_h",
        "_ptype",
        "_methods",
        "_is_dispatch",
        "_is_unknown",
        "_engine",
        "__weakref__",
    )

    def __init__(self, engine: Any, handle: int, ptype: str, facts: dict[str, Any]):
        self._h = handle
        self._ptype = ptype
        self._methods = _method_set(facts["methods"])
        self._is_dispatch = bool(facts["dispatch"])
        self._is_unknown = bool(facts["unknown"])
        self._engine = engine

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_") or name not in self._methods:
            raise AttributeError(name)
        engine = self._engine
        proxy = self

        def operation(*args: Any) -> Any:
            return engine.call(proxy, name, args)

        operation.__name__ = name
        return operation

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ComProxy):
            return NotImplemented
        return self._engine.compare(self, "__eq__", other)

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, ComProxy):
            return NotImplemented
        return self._engine.compare(self, "__ne__", other)

    def __hash__(self) -> int:
        # Equal COM objects must hash equal (pywin32 hashes the IUnknown
        # pointer), so a dict or set of raw dispatches dedups as it would live.
        return self._engine.identity(self)

    def __repr__(self) -> str:
        return f"<ComProxy {self._ptype} h={self._h}>"


class RecordingProxy(ComProxy):
    __slots__ = ("_real",)

    def __init__(self, engine: Any, handle: int, real: Any, facts: dict[str, Any]):
        super().__init__(engine, handle, type(real).__name__, facts)
        self._real = real


class ReplayProxy(ComProxy):
    __slots__ = ()


def _unproxied(value: Any) -> Any:
    """The object pywin32 would have received: proxies and wrappers around
    proxies become their real interface object (recording only)."""
    cls = type(value)
    if cls is RecordingProxy:
        return value._real
    if cls in (str, int, float, bool, type(None), bytes):
        return value
    if cls is tuple:
        items = [_unproxied(v) for v in value]
        return (
            value
            if all(a is b for a, b in zip(items, value, strict=True))
            else tuple(items)
        )
    if cls is list:
        items = [_unproxied(v) for v in value]
        return (
            value if all(a is b for a, b in zip(items, value, strict=True)) else items
        )
    inner = _oleobj_of(value)
    if type(inner) is RecordingProxy:
        return inner._real
    return value


def _iter_variants(args: Iterable[Any], variant_type: type) -> Iterator[Any]:
    """Every ``win32com.client.VARIANT`` among ``args`` (nested), in order."""
    for value in args:
        if isinstance(value, variant_type):
            yield value
        elif type(value) in (tuple, list):
            yield from _iter_variants(value, variant_type)


# ---------------------------------------------------------------------------
# Codec
# ---------------------------------------------------------------------------


def _struct_attributes(value: Any) -> dict[str, Any] | None:
    """Public data members of a pywin32 C struct (``FUNCDESC``, ``TYPEATTR``
    ...), which pywin32's own type-info code reads by attribute."""
    cls = type(value)
    if not cls.__name__.startswith("Py") or cls.__module__ not in _STRUCT_MODULES:
        return None
    attrs: dict[str, Any] = {}
    for name in dir(value):
        if name.startswith("_"):
            continue
        try:
            member = getattr(value, name)
        except Exception:  # noqa: BLE001 - a member this struct cannot report
            continue
        if not callable(member):
            attrs[name] = member
    return attrs


_STRUCT_MODULES = ("builtins", "pythoncom", "pywintypes")


class ReplayStruct:
    """A recorded pywin32 struct served back: indexable like the original
    (when it was) and carrying its data members as attributes."""

    def __init__(self, kind: str, items: tuple | None, attrs: dict[str, Any]):
        self.__dict__.update(attrs)
        self._kind = kind
        self._items = items

    def __getitem__(self, index: int) -> Any:
        if self._items is None:
            raise TypeError(f"{self._kind} (replayed) is not indexable")
        return self._items[index]

    def __len__(self) -> int:
        if self._items is None:
            raise TypeError(f"{self._kind} (replayed) has no len()")
        return len(self._items)

    def __repr__(self) -> str:
        return f"<replayed {self._kind}>"


class Codec:
    """Canonical JSON-compatible form of COM arguments and responses."""

    def __init__(self, roots: Roots, replayer: Replayer | None = None):
        self.roots = roots
        self.replayer = replayer
        self.pw = _pw()

    # -- encode --------------------------------------------------------------

    def encode(self, value: Any, *, result: bool = False) -> Any:
        cls = type(value)
        if value is None or cls is bool or cls is int:
            return value
        if cls is float:
            return {"f": value.hex()}
        if cls is str:
            return self.roots.encode(value)
        if isinstance(value, ComProxy):
            return {"h": value._h, "p": value._ptype} if result else {"h": value._h}
        if cls is tuple:
            return {"t": [self.encode(v, result=result) for v in value]}
        if cls is list:
            return {"l": [self.encode(v, result=result) for v in value]}
        if cls in (bytes, bytearray, memoryview):
            return {
                "b": base64.b64encode(bytes(value)).decode("ascii"),
                "k": cls.__name__,
            }
        pw = self.pw
        if id(value) in pw.sentinels:
            return {"s": pw.sentinels[id(value)]}
        if isinstance(value, pw.iid_type):
            return {"iid": str(value)}
        if isinstance(value, datetime.datetime):
            return {"time": value.isoformat()}
        if isinstance(value, pw.variant):
            return {"v": [value.varianttype, self.encode(value._value, result=result)]}
        if isinstance(value, pw.com_error):
            return {"com_error": [self.encode(a, result=result) for a in value.args]}
        if is_interface(value):
            return {"escape": cls.__name__}
        inner = _oleobj_of(value)
        if isinstance(inner, ComProxy):
            return {"h": inner._h, "p": inner._ptype} if result else {"h": inner._h}
        if inner is not None and is_interface(inner):
            return {"escape": f"{cls.__name__}({type(inner).__name__})"}
        if cls is dict:
            return {
                "d": [
                    [self.encode(k, result=result), self.encode(v, result=result)]
                    for k, v in value.items()
                ]
            }
        items = None
        if hasattr(value, "__getitem__") and hasattr(value, "__len__"):
            try:
                items = [value[i] for i in range(len(value))]
            except Exception:  # noqa: BLE001 - not indexable after all
                items = None
        attrs = _struct_attributes(value)
        if items is None and attrs is None:
            return {
                "opaque": f"{cls.__module__}.{cls.__qualname__}",
                "repr": repr(value),
            }
        encoded: dict[str, Any] = {"struct": cls.__name__}
        if items is not None:
            encoded["items"] = [self.encode(v, result=result) for v in items]
        if attrs:
            encoded["attrs"] = {
                k: self.encode(v, result=result) for k, v in sorted(attrs.items())
            }
        return encoded

    # -- decode (replay) -------------------------------------------------------

    def decode(self, value: Any) -> Any:
        cls = type(value)
        if value is None or cls is bool or cls is int:
            return value
        if cls is str:
            return self.roots.decode(value)
        if cls is not dict:
            raise ValueError(f"not a canonical value: {value!r}")
        if "f" in value:
            return float.fromhex(value["f"])
        if "h" in value:
            assert self.replayer is not None
            return self.replayer.proxy(value["h"], value.get("p"))
        if "t" in value:
            return tuple(self.decode(v) for v in value["t"])
        if "l" in value:
            return [self.decode(v) for v in value["l"]]
        if "b" in value:
            data = base64.b64decode(value["b"])
            return memoryview(data) if value.get("k") == "memoryview" else data
        if "s" in value:
            return getattr(self.pw.pythoncom, value["s"])
        if "iid" in value:
            return self.pw.pywintypes.IID(value["iid"])
        if "time" in value:
            return datetime.datetime.fromisoformat(value["time"])
        if "v" in value:
            vt, inner = value["v"]
            return self.pw.variant(vt, self.decode(inner))
        if "d" in value:
            return {self.decode(k): self.decode(v) for k, v in value["d"]}
        if "struct" in value:
            items = value.get("items")
            attrs = value.get("attrs", {})
            if not attrs and items is not None:
                return tuple(self.decode(v) for v in items)
            return ReplayStruct(
                value["struct"],
                None if items is None else tuple(self.decode(v) for v in items),
                {k: self.decode(v) for k, v in attrs.items()},
            )
        if "com_error" in value:
            return self.pw.com_error(*(self.decode(v) for v in value["com_error"]))
        raise ReplayStop(
            Verdict.ERROR,
            None,
            f"unservable recorded value {value!r} (no live object exists)",
        )

    def exception(self, raised: Any) -> BaseException:
        """Rebuild a recorded exception: ``com_error`` exactly, a Python
        conversion error by type name."""
        if "com_error" in raised:
            return self.decode(raised)
        payload = raised["py"]
        cls = {
            "TypeError": TypeError,
            "ValueError": ValueError,
            "OverflowError": OverflowError,
            "AttributeError": AttributeError,
            "MemoryError": MemoryError,
        }.get(payload["type"], RuntimeError)
        return cls(payload["message"])


def _encode_exception(codec: Codec, exc: BaseException) -> dict[str, Any]:
    if isinstance(exc, codec.pw.com_error):
        return codec.encode(exc)
    return {"py": {"type": type(exc).__name__, "message": str(exc)}}


# ---------------------------------------------------------------------------
# Call sites (metadata only; never part of request equality)
# ---------------------------------------------------------------------------

_SKIP_FRAMES = frozenset(
    {"_ApplyTypes_", "_get_good_object_", "_get_good_single_object_"}
)


def _iface_name(obj: Any) -> str:
    name = type(obj).__name__
    return name.removesuffix("_EarlyBound")


def _site() -> str:
    frame = sys._getframe(2)
    engine_file = __file__
    for _ in range(10):
        if frame is None:
            return "?"
        code = frame.f_code
        name = code.co_name
        if code.co_filename == engine_file or name in _SKIP_FRAMES:
            frame = frame.f_back
            continue
        local = frame.f_locals
        if name in ("__getattr__", "__setattr__") and "attr" in local:
            return f"{_iface_name(local.get('self'))}.{local['attr']}"
        if name in ("_com_invoke", "_com_put", "invoke") and "member" in local:
            return f"{local.get('interface')}.{local['member']}"
        owner = local.get("self")
        if owner is not None and hasattr(type(owner), "CLSID"):
            return f"{_iface_name(owner)}.{name}"
        return name
    return "?"


class _Role(StrEnum):
    PLUMBING = "plumbing"  # this module, pywin32, makepy-generated wrappers
    INERT = "inert"  # a module in _buildgraph.RECIPE_INERT_MODULES
    BUILD = "build"  # the repository's build code (cad/scripts, an overlay)
    LIBRARY = "library"  # the adapter, asyncio, the standard library


# Directory names whose frames are COM plumbing rather than callers: pywin32's
# package and the makepy output (gen_py, the adapter's checked-in _generated).
_PLUMBING_DIRS = frozenset({"win32com", "gen_py", "_generated"})
_CALLER_FRAMES = 3
_BUILD_FRAMES = 2
# Frames a caller lookup examines at most (a part build's deepest recorded
# stack was 42 frames).
_CALLER_DEPTH = 64
_ENGINE_PATH = os.path.normcase(__file__)
_BUILD_PREFIXES: list[str] = [os.path.normcase(os.path.dirname(__file__)) + os.sep]
# Role and module stem per ``co_filename``. Keyed by the file name, whose str
# hash is cached: a code object's hash is recomputed from its constants on every
# lookup (25 us for one large build function), which made a whole-stack walk
# keyed by code objects cost 85 us per call.
_FILE_ROLES: dict[str, tuple[_Role, str]] = {}


@functools.cache
def _inert_files() -> frozenset[str]:
    """The recipe-inert modules' files (``os.path.normcase``), from the one
    registry ``check:inert`` enforces."""
    import _buildgraph

    return frozenset(
        os.path.normcase(str(_buildgraph.SCRIPTS_DIR / name))
        for name in _buildgraph.RECIPE_INERT_MODULES
    )


def _file_role(filename: str) -> tuple[_Role, str]:
    path = os.path.normcase(filename)
    stem = Path(filename).stem
    if path == _ENGINE_PATH or _PLUMBING_DIRS.intersection(Path(path).parts):
        return _Role.PLUMBING, stem
    if path in _inert_files():
        return _Role.INERT, stem
    if path.startswith(tuple(_BUILD_PREFIXES)):
        return _Role.BUILD, stem
    return _Role.LIBRARY, stem


def caller() -> str:
    """The nearest non-plumbing frames as ``module:function:line``, innermost
    first, plus the two nearest build-code frames when those three are all
    adapter or library frames (a decorator's wrapper is often the first).
    Stops as soon as that is settled, never deeper than ``_CALLER_DEPTH``."""
    callers: list[str] = []
    build_frames: list[str] = []
    build_seen = False
    frame = sys._getframe(1)
    for _ in range(_CALLER_DEPTH):
        if frame is None:
            break
        current, frame = frame, frame.f_back
        code = current.f_code
        role = _FILE_ROLES.get(code.co_filename)
        if role is None:
            role = _FILE_ROLES[code.co_filename] = _file_role(code.co_filename)
        kind, stem = role
        if kind is _Role.PLUMBING:
            continue
        label = f"{stem}:{code.co_name}:{current.f_lineno}"
        if len(callers) < _CALLER_FRAMES:
            callers.append(label)
            build_seen = build_seen or kind is not _Role.LIBRARY
            if build_seen and len(callers) == _CALLER_FRAMES:
                break
            continue
        if kind is _Role.LIBRARY:
            continue
        build_frames.append(label)
        if len(build_frames) == _BUILD_FRAMES:
            break
    if build_frames:
        callers.append("... " + " < ".join(build_frames))
    return " < ".join(callers)


# True while a function of a recipe-inert module runs. A context variable, so an
# asyncio task gets its own copy: one task's inert probe never tags another's.
_IN_INERT: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "com_conversation_in_inert", default=False
)


def _origin() -> Origin:
    return Origin.INERT if _IN_INERT.get() else Origin.RECIPE


@functools.cache
def _inert_module_names() -> tuple[str, ...]:
    import _buildgraph

    return tuple(sorted(Path(name).stem for name in _buildgraph.RECIPE_INERT_MODULES))


def _inert_modules() -> list[Any]:
    """The recipe-inert modules, imported (every build has them loaded)."""
    return [importlib.import_module(name) for name in _inert_module_names()]


def _inert_entry(function: Callable[..., Any]) -> Callable[..., Any]:
    """``function`` with its dynamic extent marked INERT. A coroutine function
    is marked while awaited; a generator function only while it creates its
    generator, so its body runs RECIPE (the conservative direction)."""
    if inspect.iscoroutinefunction(function):

        @functools.wraps(function)
        async def awaited(*args: Any, **kwargs: Any) -> Any:
            token = _IN_INERT.set(True)
            try:
                return await function(*args, **kwargs)
            finally:
                _IN_INERT.reset(token)

        return awaited

    @functools.wraps(function)
    def called(*args: Any, **kwargs: Any) -> Any:
        token = _IN_INERT.set(True)
        try:
            return function(*args, **kwargs)
        finally:
            _IN_INERT.reset(token)

    return called


@contextlib.contextmanager
def inert_entry_points() -> Iterator[list[str]]:
    """Wrap every function the recipe-inert modules define, for one window.

    Build code calls them as ``module.function`` (``check:inert`` pins those
    call sites) and they call one another through their module globals, so
    replacing the module attributes covers every route in; a reference bound
    before the window bypasses the wrapper and its calls stay RECIPE. Yields
    the wrapped names; restores the originals on exit."""
    swapped: list[tuple[Any, str, Any]] = []
    for module in _inert_modules():
        for name, value in list(vars(module).items()):
            if inspect.isfunction(value) and value.__module__ == module.__name__:
                swapped.append((module, name, value))
                setattr(module, name, _inert_entry(value))
    try:
        yield [f"{module.__name__}.{name}" for module, name, _ in swapped]
    finally:
        for module, name, value in reversed(swapped):
            setattr(module, name, value)


# ---------------------------------------------------------------------------
# Log I/O
# ---------------------------------------------------------------------------


class LogWriter:
    """Gzipped JSON lines: header, interned dispatch headers, calls in seq
    order, trailer."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with _ENGINE_IO:
            self._stream = gzip.open(path, "wt", encoding="utf-8", compresslevel=6)
        self._headers: dict[str, int] = {}
        self._pending: dict[int, Call] = {}
        self._next = 0
        self.calls = 0

    def _line(self, value: dict[str, Any]) -> None:
        with _ENGINE_IO:
            self._stream.write(
                json.dumps(value, separators=(",", ":"), allow_nan=False)
            )
            self._stream.write("\n")

    def header(self, header: Header) -> None:
        self._line({"header": header.to_json()})

    def emit(self, call: Call) -> None:
        self._pending[call.seq] = call
        while self._next in self._pending:
            self._write(self._pending.pop(self._next))
            self._next += 1

    def _write(self, call: Call) -> None:
        line: dict[str, Any] = {
            "s": call.seq,
            "h": call.handle,
            "o": call.op,
            "w": call.site,
        }
        args = call.args
        width = _HEADER_WIDTH.get(call.op)
        if width is not None and len(args) >= width:
            key = json.dumps(args[:width], separators=(",", ":"))
            ident = self._headers.get(key)
            if ident is None:
                ident = self._headers[key] = len(self._headers)
                self._line({"H": [ident, args[:width]]})
            line["x"] = ident
            args = args[width:]
        line["a"] = args
        line["r"] = call.result
        if call.raised is not None:
            line["e"] = call.raised
        if call.outs is not None:
            line["u"] = call.outs
        if call.foreign_thread:
            line["t"] = 1
        if call.origin is Origin.INERT:
            line["g"] = "i"
        if call.caller:
            line["c"] = call.caller
        self._line(line)
        self.calls += 1

    def close(self, trailer: dict[str, Any]) -> None:
        for seq in sorted(self._pending):  # an interrupted call never completed
            self._write(self._pending.pop(seq))
        self._line({"trailer": trailer})
        with _ENGINE_IO:
            self._stream.close()


def load(log: Path) -> Conversation:
    """Read a log written by :class:`LogWriter`."""
    header: Header | None = None
    trailer: dict[str, Any] = {"status": "missing"}
    headers: dict[int, list[Any]] = {}
    calls: list[Call] = []
    with _ENGINE_IO, gzip.open(log, "rt", encoding="utf-8") as stream:
        for text in stream:
            line = json.loads(text)
            if "s" in line:
                args = line["a"]
                if "x" in line:
                    args = [*headers[line["x"]], *args]
                calls.append(
                    Call(
                        seq=line["s"],
                        handle=line["h"],
                        op=line["o"],
                        args=args,
                        site=line["w"],
                        result=line["r"],
                        raised=line.get("e"),
                        outs=line.get("u"),
                        foreign_thread=bool(line.get("t")),
                        origin=Origin.INERT if line.get("g") == "i" else Origin.RECIPE,
                        caller=line.get("c", ""),
                    )
                )
            elif "H" in line:
                ident, value = line["H"]
                headers[ident] = value
            elif "header" in line:
                header = Header.from_json(line["header"])
            elif "trailer" in line:
                trailer = line["trailer"]
    if header is None:
        raise ValueError(f"{log}: no header line")
    return Conversation(header, calls, trailer)


def _conversation(value: Path | Conversation) -> Conversation:
    return value if isinstance(value, Conversation) else load(Path(value))


# ---------------------------------------------------------------------------
# Divergence analysis
# ---------------------------------------------------------------------------


_CONTEXT_CALLS = 5
_CLIP = 240
_EXAMPLES = 25


def recipe_calls(calls: Sequence[Call]) -> list[Call]:
    """The calls the no-op claim is about: all but recipe-inert ones."""
    return [call for call in calls if call.origin is Origin.RECIPE]


def clip(value: Any, width: int = _CLIP) -> str:
    """A bounded one-line JSON rendering of a canonical value."""
    text = json.dumps(value, separators=(",", ":"), default=str)
    return text if len(text) <= width else f"{text[: width - 3]}..."


def brief(call: Call) -> dict[str, Any]:
    """One call, bounded: what a reader needs to place it."""
    width = _HEADER_WIDTH.get(call.op, 0)
    return {
        "seq": call.seq,
        "site": call.site,
        "kind": call.kind.value,
        "h": call.handle,
        "caller": call.caller,
        "args": clip(call.args[width:]),
        "response": clip(call.raised if call.raised is not None else call.result),
    }


def _feature_before(calls: Sequence[Call], index: int) -> str | None:
    for call in reversed(calls[: index + 1]):
        if call.kind is Kind.PUT and call.site.endswith("IFeature.Name"):
            names = [a for a in call.args if isinstance(a, str)]
            if names:
                return names[-1]
    return None


def _last_tree_seq(calls: Sequence[Call]) -> int | None:
    for call in reversed(calls):
        if (
            call.kind in (Kind.CALL, Kind.PUT)
            and classify(call.site, call.kind) is Phase.TREE
        ):
            return call.seq
    return None


def _divergence(
    stream: Sequence[Call],
    index: int,
    side: Side,
    field: Field,
    expected: Call | None,
    actual: dict[str, Any] | None,
) -> Divergence:
    site = (expected.site if expected else None) or (actual or {}).get("site") or "?"
    kind = (
        expected.kind
        if expected
        else kind_of((actual or {}).get("op", ""), (actual or {}).get("args", []))
    )
    return Divergence(
        index=index,
        seq=expected.seq if expected else None,
        side=side,
        field=field,
        expected=expected.to_json() if expected else None,
        actual=actual,
        phase=classify(site, kind),
        last_tree_seq_base=_last_tree_seq(stream),
        feature=_feature_before(stream, min(index, len(stream) - 1))
        if stream
        else None,
        context=[brief(c) for c in stream[max(0, index - _CONTEXT_CALLS) : index]],
    )


def request_field(
    expected: Call,
    handle: int,
    op: str,
    args: list[Any],
    mask: Sequence[MaskRule] = PROVENANCE_MASK,
) -> Field | None:
    """The first part of a request that differs from ``expected`` (args after
    ``mask``), or ``None`` when it is the same request."""
    if expected.op != op:
        return Field.OP
    width = _HEADER_WIDTH.get(op, 0)
    if not same(expected.args[:width], args[:width]):
        return Field.MEMBER
    if expected.handle != handle:
        return Field.HANDLE
    if not same(_masked(expected.args, mask), _masked(args, mask)):
        return Field.ARGS
    return None


def _response_field(a: Call, b: Call) -> Field | None:
    if not same(a.raised, b.raised):
        return Field.RAISED
    if not same(a.result, b.result):
        return Field.RESULT
    if not same(a.outs, b.outs):
        return Field.OUTS
    return None


def _response_of(call: Call, field: Field) -> Any:
    if field is Field.RAISED:
        return call.raised
    if field is Field.OUTS:
        return call.outs
    return call.result


def _request_divergence(
    a: Sequence[Call],
    b: Sequence[Call],
    index: int,
    field: Field,
    preceding: dict[str, Any] | None,
) -> dict[str, Any]:
    x = a[index] if index < len(a) else None
    y = b[index] if index < len(b) else None
    side = Side.LENGTH if field is Field.LENGTH else Side.REQUEST
    found = _divergence(a, index, side, field, x, y.to_json() if y else None).to_json()
    found["seq_new"] = y.seq if y else None
    found["preceding_response_difference"] = preceding
    return found


def _capture_differences(
    base: Conversation, new: Conversation, a: Sequence[Call], b: Sequence[Call]
) -> list[dict[str, Any]]:
    """SolidWorks-written files whose bytes differ, keyed by recipe index."""

    def by_index(
        conversation: Conversation, stream: Sequence[Call]
    ) -> dict[tuple[int | None, str], str]:
        index_of = {call.seq: i for i, call in enumerate(stream)}
        return {
            (index_of.get(int(seq)), rel): digest
            for seq, files in conversation.trailer.get("captured", {}).items()
            for rel, digest in files.items()
        }

    left, right = by_index(base, a), by_index(new, b)
    differences = []
    for key in sorted(set(left) | set(right), key=str):
        if left.get(key) == right.get(key):
            continue
        index, rel = key
        member = a[index].site if index is not None and index < len(a) else None
        differences.append(
            {
                "index": index,
                "member": member,
                "file": rel,
                "a": left.get(key),
                "b": right.get(key),
            }
        )
    return differences[:_EXAMPLES]


def compare_conversations(
    base_log: Path | Conversation,
    new_log: Path | Conversation,
    mask: Sequence[MaskRule] = PROVENANCE_MASK,
) -> dict[str, Any]:
    """K1: do two recordings of one script issue the same requests?

    Recipe calls are aligned by position. The first request that differs
    (operation, member, handle or masked arguments) ends the alignment and is
    THE request divergence, reported with its context and the nearest earlier
    response difference (a response that may have steered it). Responses may
    differ legitimately between two live sessions (process ids, window
    handles, times, temporary paths, persistent ids): every one before the
    request divergence is counted by member with its first example, and none
    is masked. Recipe-inert calls are compared only as per-member counts, and
    SolidWorks-written files by digest per recipe call."""
    base, new = _conversation(base_log), _conversation(new_log)
    a, b = recipe_calls(base.calls), recipe_calls(new.calls)
    counts: Counter[str] = Counter()
    examples: dict[str, dict[str, Any]] = {}
    preceding: dict[str, Any] | None = None
    divergence: dict[str, Any] | None = None
    for index, (x, y) in enumerate(zip(a, b, strict=False)):
        changed = request_field(x, y.handle, y.op, y.args, mask)
        if changed is not None:
            divergence = _request_divergence(a, b, index, changed, preceding)
            break
        changed = _response_field(x, y)
        if changed is None:
            continue
        counts[x.site] += 1
        preceding = {
            "index": index,
            "seq": [x.seq, y.seq],
            "member": x.site,
            "field": changed.value,
            "caller": x.caller,
            "a": clip(_response_of(x, changed)),
            "b": clip(_response_of(y, changed)),
        }
        if x.site not in examples and len(examples) < _EXAMPLES:
            examples[x.site] = preceding
    else:
        if len(a) != len(b):
            index = min(len(a), len(b))
            divergence = _request_divergence(a, b, index, Field.LENGTH, preceding)
    inert_a = Counter(c.site for c in base.calls if c.origin is Origin.INERT)
    inert_b = Counter(c.site for c in new.calls if c.origin is Origin.INERT)
    return {
        "recipe_calls": [len(a), len(b)],
        "inert_calls": [sum(inert_a.values()), sum(inert_b.values())],
        "request_divergence": divergence,
        "response_difference_count": sum(counts.values()),
        "response_differences": dict(counts.most_common()),
        "response_examples": list(examples.values()),
        "inert_differences": {
            site: [inert_a[site], inert_b[site]]
            for site in sorted(set(inert_a) | set(inert_b))
            if inert_a[site] != inert_b[site]
        },
        "capture_differences": _capture_differences(base, new, a, b),
        "header_differences": compare_headers(base.header, new.header),
    }


def compare_headers(a: Header, b: Header) -> dict[str, Any]:
    """Header fields that differ between two logs (inputs, not the script)."""
    fields = (
        "engine",
        "sw_revision",
        "environment",
        "provenance_mask",
        "adapter_state",
    )
    return {
        name: {"a": getattr(a, name), "b": getattr(b, name)}
        for name in fields
        if getattr(a, name) != getattr(b, name)
    }


# ---------------------------------------------------------------------------
# Audit-hook observers (hooks cannot be removed: one dispatcher per process)
# ---------------------------------------------------------------------------

_AUDITED = frozenset(
    {
        "open",
        "os.remove",
        "os.rename",
        "os.replace",
        "os.mkdir",
        "os.rmdir",
        "os.truncate",
        "os.link",
        "os.symlink",
        "shutil.rmtree",
        "shutil.copyfile",
        "shutil.copytree",
        "shutil.move",
    }
)
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC


class Access(StrEnum):
    READ = "read"
    WRITE = "write"
    REMOVE = "remove"


_MOVES = frozenset({"os.rename", "os.replace", "shutil.move"})
_REMOVALS = frozenset({"os.remove", "os.rmdir", "shutil.rmtree"})


def _as_path(value: Any) -> Path | None:
    if isinstance(value, (str, bytes, os.PathLike)):
        return Path(os.fsdecode(value))
    return None


def _event_paths(event: str, args: tuple[Any, ...]) -> list[tuple[Path, Access]]:
    """``(path, access)`` for each filesystem path an audited event touches."""
    if event == "open":
        path, mode, flags = (*args, None, None, None)[:3]
        target = _as_path(path)
        if target is None:
            return []
        if isinstance(mode, str):
            write = any(c in mode for c in "wax+")
        else:
            write = isinstance(flags, int) and bool(flags & _WRITE_FLAGS)
        return [(target, Access.WRITE if write else Access.READ)]
    first = _as_path(args[0]) if args else None
    second = _as_path(args[1]) if len(args) > 1 else None
    if event in ("shutil.copyfile", "shutil.copytree"):
        pairs = [(first, Access.READ), (second, Access.WRITE)]
    elif event in _MOVES:
        pairs = [(first, Access.REMOVE), (second, Access.WRITE)]
    elif event in _REMOVALS:
        pairs = [(first, Access.REMOVE)]
    elif event in ("os.link", "os.symlink"):
        pairs = [(second, Access.WRITE)]
    elif event == "os.mkdir" and first is not None and first.is_dir():
        pairs = []  # mkdir(exist_ok=True) on an existing directory changes nothing
    else:
        pairs = [(first, Access.WRITE)]
    return [(path, access) for path, access in pairs if path is not None]


def _under(path: Path, root: Path) -> bool:
    try:
        return os.path.normcase(os.path.abspath(path)).startswith(
            os.path.normcase(os.path.abspath(root)).rstrip("\\/") + os.sep
        ) or os.path.normcase(os.path.abspath(path)) == os.path.normcase(
            os.path.abspath(root)
        )
    except (OSError, ValueError):
        return False


class _FileObserver:
    """Write/read accounting for one recording or replay window."""

    def __init__(self, out_root: Path, mode: GuardMode, allowed: Sequence[Path]):
        self.out_root = out_root
        self.mode = mode
        self.allowed = list(allowed)
        self.reads: list[tuple[str, str]] = []
        self.written: set[str] = set()
        self.removed: set[str] = set()
        self.outside: list[dict[str, str]] = []
        self.violations: list[dict[str, str]] = []

    def _relative(self, path: Path) -> str:
        return Path(
            os.path.relpath(os.path.abspath(path), os.path.abspath(self.out_root))
        ).as_posix()

    def observe(self, event: str, args: tuple[Any, ...]) -> None:
        for path, access in _event_paths(event, args):
            if "__pycache__" in path.parts:
                continue
            inside = _under(path, self.out_root)
            if access is Access.READ:
                if inside and path.is_file():
                    self.reads.append((self._relative(path), sha256_file(path)))
                continue
            if inside:
                relative = self._relative(path)
                if access is Access.REMOVE:
                    self.written.discard(relative)
                    self.removed.add(relative)
                else:
                    self.written.add(relative)
                continue
            if any(_under(path, root) for root in self.allowed):
                continue
            if event == "os.mkdir" and any(
                _under(root, path) for root in (self.out_root, *self.allowed)
            ):
                continue  # creating the directory chain down to a permitted root
            entry = {"event": event, "path": str(path), "access": access.value}
            if self.mode is GuardMode.RAISE and _under(path, REPO_ROOT):
                self.violations.append(entry)
                raise SandboxViolation(f"replay write outside scratch: {event} {path}")
            self.outside.append(entry)


class _AuditDispatcher:
    def __init__(self) -> None:
        self.observer: _FileObserver | None = None
        self.installed = False

    def hook(self, event: str, args: tuple[Any, ...]) -> None:
        observer = self.observer
        if observer is None or event not in _AUDITED or _ENGINE_IO.active:
            return
        with _ENGINE_IO:
            observer.observe(event, args)

    def install(self) -> None:
        if not self.installed:
            sys.addaudithook(self.hook)
            self.installed = True


_AUDIT = _AuditDispatcher()


def _allowed_side_writes() -> list[Path]:
    """Writes a build may legitimately make outside its output root."""
    roots = [REPO_ROOT / "cad" / "out" / "reports" / "telemetry"]
    with contextlib.suppress(Exception):
        import win32com

        roots.append(Path(win32com.__gen_path__))
    return roots


# ---------------------------------------------------------------------------
# Funnel: make pywin32 treat a proxy exactly like the object it stands for
# ---------------------------------------------------------------------------

_ACTIVE: Recorder | Replayer | None = None
_FUNNEL_DEPTH = 0
_ORIGINALS: dict[str, Any] = {}


def _adopt_real(value: Any) -> Any:
    """Recording: a real interface object reaching pywin32's wrapping logic
    outside a proxied result becomes a proxy (an escape when no call is in
    progress)."""
    active = _ACTIVE
    if isinstance(active, Recorder) and is_interface(value):
        return active.adopt(value)
    return value


def _patched_dbc_init(self: Any, oobj: Any = None) -> None:
    pw = _pw()
    wrapped = isinstance(oobj, pw.client.DispatchBaseClass)
    target = _adopt_real(oobj.__dict__.get("_oleobj_") if wrapped else oobj)
    if isinstance(target, ComProxy):
        if target._is_dispatch:
            # As DispatchBaseClass.__init__ does for a PyIDispatch (or a
            # generated wrapper of one): QueryInterface for the class's IID,
            # keeping the object when the server refuses.
            try:
                target = target.QueryInterface(self.CLSID, pw.pythoncom.IID_IDispatch)
            except pw.pythoncom.com_error:
                pass
        self.__dict__["_oleobj_"] = target
        return
    _ORIGINALS["dbc_init"](self, oobj)


def _patched_good_single(
    obj: Any, obUserName: Any = None, resultCLSID: Any = None
) -> Any:
    obj = _adopt_real(obj)
    if isinstance(obj, ComProxy) and obj._is_dispatch:
        return _pw().client.Dispatch(obj, obUserName, resultCLSID)
    return _ORIGINALS["good_single"](obj, obUserName, resultCLSID)


def _patched_cdispatch_good_single(
    self: Any, ob: Any, userName: Any = None, ReturnCLSID: Any = None
) -> Any:
    ob = _adopt_real(ob)
    if isinstance(ob, ComProxy):
        if ob._is_dispatch:
            return self._wrap_dispatch_(ob, userName, ReturnCLSID)
        if ob._is_unknown:
            pythoncom = _pw().pythoncom
            try:
                ob = ob.QueryInterface(pythoncom.IID_IDispatch)
            except pythoncom.com_error:
                return ob
            return self._wrap_dispatch_(ob, userName, ReturnCLSID)
        return ob
    return _ORIGINALS["cdispatch_good_single"](self, ob, userName, ReturnCLSID)


@contextlib.contextmanager
def funnel() -> Iterator[None]:
    """Install the three pywin32 patches (re-entrant; restored on exit)."""
    global _FUNNEL_DEPTH
    pw = _pw()
    if _FUNNEL_DEPTH == 0:
        _ORIGINALS["dbc_init"] = pw.client.DispatchBaseClass.__init__
        _ORIGINALS["good_single"] = pw.client._get_good_single_object_
        _ORIGINALS["cdispatch_good_single"] = (
            pw.dynamic.CDispatch._get_good_single_object_
        )
        pw.client.DispatchBaseClass.__init__ = _patched_dbc_init
        pw.client._get_good_single_object_ = _patched_good_single
        pw.dynamic.CDispatch._get_good_single_object_ = _patched_cdispatch_good_single
    _FUNNEL_DEPTH += 1
    try:
        yield
    finally:
        _FUNNEL_DEPTH -= 1
        if _FUNNEL_DEPTH == 0:
            pw.client.DispatchBaseClass.__init__ = _ORIGINALS["dbc_init"]
            pw.client._get_good_single_object_ = _ORIGINALS["good_single"]
            pw.dynamic.CDispatch._get_good_single_object_ = _ORIGINALS[
                "cdispatch_good_single"
            ]


# ---------------------------------------------------------------------------
# Recorder
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _WriteBack:
    """One VARIANT argument of a recorded call: the caller's object, the
    stand-in pywin32 receives, its value before the call, and whether
    pywin32 wrote the result through the ``value`` property."""

    original: Any
    passed: Any
    before: Any
    via_property: bool = False


@contextlib.contextmanager
def _raw_write_back(
    variant_type: type, tracked: Sequence[_WriteBack]
) -> Iterator[None]:
    """For the duration of one call, store pywin32's byref write-back into
    each stand-in VARIANT unconverted. ``VARIANT.value``'s setter would wrap a
    returned interface on the spot; recording the raw handle instead lets the
    replay run that same wrapping (and its COM calls) against the log."""
    if not tracked:
        yield
        return
    by_id = {id(entry.passed): entry for entry in tracked}
    original = variant_type.__dict__["value"]

    def set_value(variant: Any, newval: Any) -> None:
        entry = by_id.get(id(variant))
        if entry is None or entry.passed is not variant:
            original.__set__(variant, newval)
            return
        entry.via_property = True
        variant._value = newval

    variant_type.value = property(original.fget, set_value, original.fdel)
    try:
        yield
    finally:
        variant_type.value = original


class Recorder:
    """Forwards every proxied operation to the real object and logs it."""

    def __init__(
        self,
        writer: LogWriter,
        roots: Roots,
        capture_dir: Path | None = None,
        callers: CallerCapture = DEFAULT_CALLERS,
    ):
        self.writer = writer
        self.roots = roots
        self.codec = Codec(roots)
        self.pw = self.codec.pw
        self.capture_dir = capture_dir
        self.callers = callers
        self.closed = False
        self.seq = 0
        self._handles = {
            Origin.RECIPE: itertools.count(1),
            Origin.INERT: itertools.count(-1, -1),
        }
        self.allocated: Counter[Origin] = Counter()
        self.origins: Counter[Origin] = Counter()
        self.depth = 0
        self.types: dict[str, dict[str, Any]] = {}
        self._identities: dict[Origin, dict[int, int]] = {o: {} for o in Origin}
        self.adopted_inside = 0
        self.adopted_outside = 0
        self.foreign_thread_calls = 0
        self.external: dict[str, str] = {}
        self.internal_paths: set[str] = set()
        self.captured: dict[str, dict[str, str]] = {}
        self.capture_bytes = 0
        self.capture_stored_bytes = 0
        self._digests: dict[str, str | None] = {}
        # Nanoseconds inside call(): in total, inside the real COM call, in
        # caller capture and in capture compression (the engine's own cost is
        # calls - com).
        self.clock: Counter[str] = Counter()
        self._thread = threading.get_ident()

    # -- handles ---------------------------------------------------------------

    def _new_proxy(self, real: Any, origin: Origin) -> RecordingProxy:
        ptype = type(real).__name__
        facts = self.types.get(ptype)
        if facts is None:
            facts = self.types[ptype] = _type_facts(real)
        proxy = RecordingProxy(self, next(self._handles[origin]), real, facts)
        self.allocated[origin] += 1
        return proxy

    def root(self, real: Any) -> RecordingProxy:
        """A pre-window object the build inherits through the adapter."""
        return self._new_proxy(real, Origin.RECIPE)

    def _caller(self) -> str:
        if self.callers is not CallerCapture.FULL:
            return ""
        started = time.perf_counter_ns()
        frames = caller()
        self.clock["caller"] += time.perf_counter_ns() - started
        return frames

    def adopt(self, real: Any) -> RecordingProxy:
        origin = _origin()
        proxy = self._new_proxy(real, origin)
        if self.closed:
            return proxy
        if self.depth > 0:  # a byref write-back of the call in progress
            self.adopted_inside += 1
            return proxy
        self.adopted_outside += 1
        seq = self._next_seq()
        self._emit(
            Call(
                seq,
                proxy._h,
                "ADOPT",
                [],
                _site(),
                self.codec.encode(proxy, result=True),
                origin=origin,
                caller=self._caller(),
            )
        )
        return proxy

    def wrap(self, value: Any, origin: Origin) -> Any:
        cls = type(value)
        if cls is tuple:
            items = [self.wrap(v, origin) for v in value]
            return (
                value
                if all(a is b for a, b in zip(items, value, strict=True))
                else tuple(items)
            )
        if cls is list:
            return [self.wrap(v, origin) for v in value]
        if is_interface(value):
            return self._new_proxy(value, origin)
        return value

    def _emit(self, call: Call) -> None:
        self.origins[call.origin] += 1
        self.writer.emit(call)

    def _next_seq(self) -> int:
        seq = self.seq
        self.seq += 1
        return seq

    # -- external inputs -------------------------------------------------------

    def _note_paths(self, args: Iterable[Any]) -> None:
        for value in args:
            if type(value) in (tuple, list):
                self._note_paths(value)
                continue
            if type(value) is not str or not _looks_absolute(value):
                continue
            canonical = self.roots.encode(value)
            if self.roots.out_relative(canonical) is not None:
                self.internal_paths.add(canonical)
                continue
            if canonical in self._digests:
                continue
            path = Path(value)
            digest = sha256_file(path) if path.is_file() else None
            self._digests[canonical] = digest
            if digest is not None:
                self.external[canonical] = digest

    # -- SolidWorks-written files (R10) ----------------------------------------

    def _watch(self, op: str, canonical: list[Any], site: str) -> dict[str, Any] | None:
        """Pre-call signatures of the output files a save/export names."""
        if (
            self.capture_dir is None
            or classify(site, kind_of(op, canonical)) is not Phase.OUTPUT
        ):
            return None
        return {
            rel: _signature(self.roots.out / rel)
            for rel in _out_relatives(self.roots, canonical)
        }

    def _capture(self, seq: int, watch: dict[str, Any]) -> None:
        """Keep a gzip copy of every named output file the call created or
        changed, so a replay can recreate it at the same point (even an
        intermediate that Python deletes later, such as ``SaveBMP``'s
        ``.capture.bmp``); the digest is of the uncompressed bytes."""
        assert self.capture_dir is not None
        started = time.perf_counter_ns()
        for rel, before in watch.items():
            source = self.roots.out / rel
            after = _signature(source)
            if after is None or after == before:
                continue
            target = self.capture_dir / str(seq) / f"{rel}.gz"
            with _ENGINE_IO:
                target.parent.mkdir(parents=True, exist_ok=True)
                data = source.read_bytes()
                target.write_bytes(
                    gzip.compress(data, compresslevel=_CAPTURE_LEVEL, mtime=0)
                )
            digest = hashlib.sha256(data).hexdigest()
            self.captured.setdefault(str(seq), {})[rel] = digest
            self.capture_bytes += len(data)
            self.capture_stored_bytes += target.stat().st_size
        self.clock["capture"] += time.perf_counter_ns() - started

    # -- operations ------------------------------------------------------------

    def call(self, proxy: RecordingProxy, op: str, args: tuple[Any, ...]) -> Any:
        method = getattr(proxy._real, op)
        if self.closed:
            return method(*_unproxied(list(args)))
        entered = time.perf_counter_ns()
        seq = self._next_seq()
        site = _site()
        origin = _origin()
        caller_frames = self._caller()
        foreign = threading.get_ident() != self._thread
        self.foreign_thread_calls += foreign
        canonical = [self.codec.encode(a) for a in args]
        self._note_paths(args)
        watch = self._watch(op, canonical, site)
        real_args, variants = self._prepare(args)
        self.depth += 1
        com_started = time.perf_counter_ns()
        try:
            with _raw_write_back(self.pw.variant, variants):
                raw = method(*real_args)
        except BaseException as exc:
            self.clock["com"] += time.perf_counter_ns() - com_started
            self.depth -= 1
            outs = self._outs(variants, origin)
            if watch:
                self._capture(seq, watch)
            self._emit(
                Call(
                    seq,
                    proxy._h,
                    op,
                    canonical,
                    site,
                    None,
                    _encode_exception(self.codec, exc),
                    outs,
                    foreign,
                    origin,
                    caller_frames,
                )
            )
            self.clock["calls"] += time.perf_counter_ns() - entered
            raise
        self.clock["com"] += time.perf_counter_ns() - com_started
        self.depth -= 1
        result = self.wrap(raw, origin)
        outs = self._outs(variants, origin)
        if watch:
            self._capture(seq, watch)
        self._emit(
            Call(
                seq,
                proxy._h,
                op,
                canonical,
                site,
                self.codec.encode(result, result=True),
                None,
                outs,
                foreign,
                origin,
                caller_frames,
            )
        )
        self.clock["calls"] += time.perf_counter_ns() - entered
        return result

    def _prepare(self, args: tuple[Any, ...]) -> tuple[list[Any], list[_WriteBack]]:
        """Real arguments for pywin32; every VARIANT is passed as a fresh
        stand-in so its byref write-back can be observed raw."""
        variant_type = self.pw.variant
        tracked: list[_WriteBack] = []

        def convert(value: Any) -> Any:
            if isinstance(value, variant_type):
                passed = variant_type(value.varianttype, _unproxied(value._value))
                tracked.append(_WriteBack(value, passed, passed._value))
                return passed
            if type(value) in (tuple, list):
                return type(value)(convert(v) for v in value)
            return _unproxied(value)

        return [convert(a) for a in args], tracked

    def _outs(self, tracked: list[_WriteBack], origin: Origin) -> list[Any] | None:
        """Encode each write-back as ``[attribute, raw value]`` and apply it
        to the caller's VARIANT the way pywin32 would have (``value`` wraps
        interfaces through ``_get_good_object_``; those wrapping calls are
        recorded after this call, exactly where a replay issues them)."""
        if not tracked:
            return None
        outs: list[Any] = []
        for entry in tracked:
            after = entry.passed._value
            if after is entry.before and not entry.via_property:
                outs.append(None)
                continue
            after = self.wrap(after, origin)
            via = "value" if entry.via_property else "_value"
            outs.append([via, self.codec.encode(after, result=True)])
            setattr(entry.original, via, after)
        return outs

    def compare(self, proxy: RecordingProxy, op: str, other: ComProxy) -> bool:
        assert isinstance(other, RecordingProxy)
        outcome = (
            (proxy._real == other._real)
            if op == "__eq__"
            else (proxy._real != other._real)
        )
        if self.closed:
            return outcome
        origin = _origin()
        caller_frames = self._caller()
        seq = self._next_seq()
        self._emit(
            Call(
                seq,
                proxy._h,
                op,
                [{"h": other._h}],
                _site(),
                bool(outcome),
                origin=origin,
                caller=caller_frames,
            )
        )
        return outcome

    def identity(self, proxy: RecordingProxy) -> int:
        """``hash()`` of a proxy: a small identity index, equal for equal COM
        objects (recorded, so the replay answers the same index)."""
        if self.closed:
            return hash(proxy._real)
        seq = self._next_seq()
        site = _site()
        origin = _origin()
        caller_frames = self._caller()
        try:
            real_hash = hash(proxy._real)
        except Exception as exc:
            self._emit(
                Call(
                    seq,
                    proxy._h,
                    "__hash__",
                    [],
                    site,
                    None,
                    _encode_exception(self.codec, exc),
                    origin=origin,
                    caller=caller_frames,
                )
            )
            raise
        identities = self._identities[origin]
        index = identities.setdefault(real_hash, len(identities))
        self._emit(
            Call(
                seq,
                proxy._h,
                "__hash__",
                [],
                site,
                index,
                origin=origin,
                caller=caller_frames,
            )
        )
        return index


# ---------------------------------------------------------------------------
# Replayer
# ---------------------------------------------------------------------------


class Materialiser:
    """Recreates SolidWorks' file writes during a replay.

    The recorder kept every output file a save/export call created or changed
    as ``<log>.files/<seq>/<rel>.gz``; after serving that call the replay
    writes the same bytes into the scratch output root, so Python reading or
    testing the file afterwards (``os.path.exists`` after ``SaveAs3``, Pillow
    converting the ``SaveBMP`` capture) sees what it saw in the recording."""

    def __init__(
        self, conversation: Conversation, capture_dir: Path, scratch_root: Path
    ):
        self.captured: dict[str, dict[str, str]] = conversation.trailer.get(
            "captured", {}
        )
        self.capture_dir = capture_dir
        self.scratch_root = scratch_root
        self.copied: dict[str, str] = {}
        self.missing: list[str] = []

    def __call__(self, seq: int) -> None:
        for rel, digest in self.captured.get(str(seq), {}).items():
            source = self.capture_dir / str(seq) / f"{rel}.gz"
            if not source.is_file():
                self.missing.append(f"{seq}/{rel}")
                continue
            target = self.scratch_root / rel
            with _ENGINE_IO:
                data = gzip.decompress(source.read_bytes())
                if hashlib.sha256(data).hexdigest() != digest:
                    self.missing.append(f"{seq}/{rel} (digest differs)")
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            self.copied[rel] = digest


def capture_dir_of(log: Path) -> Path:
    """Where :func:`recording` keeps the files SolidWorks wrote for ``log``."""
    return log.with_name(log.name + ".files")


# The answer to a recipe-inert request the recording never saw: E_FAIL. Inert
# code guards every probe ("provenance is never fatal"), so it records an
# unreadable value and carries on, exactly as with a seat that refuses.
_UNRECORDED_INERT = {
    "com_error": [
        -2147467259,
        "replay: this recipe-inert request was not recorded",
        None,
        None,
    ]
}


class Replayer:
    """Serves a recorded conversation; the first recipe mismatch is sticky."""

    def __init__(
        self,
        conversation: Conversation,
        roots: Roots,
        mask: Sequence[MaskRule] = PROVENANCE_MASK,
        materialise: Callable[[int], None] | None = None,
        callers: CallerCapture = DEFAULT_CALLERS,
    ):
        self.header = conversation.header
        self.strict = recipe_calls(conversation.calls)
        self.inert = [c for c in conversation.calls if c.origin is Origin.INERT]
        self.types: dict[str, dict[str, Any]] = conversation.trailer.get("types", {})
        self.roots = roots
        self.mask = mask
        self.codec = Codec(roots, self)
        self.materialise = materialise
        self.callers = callers
        self.pos = 0
        self.served = 0
        self.stop: ReplayStop | None = None
        self.proxies: dict[int, ReplayProxy] = {}
        self._inert_used = [False] * len(self.inert)
        self._inert_first = 0
        self.inert_served = 0
        self.inert_unserved: Counter[str] = Counter()
        self._unserved_callers: dict[str, str] = {}
        # Masked values: recorded -> replayed (one-to-one), and the responses
        # served with a recorded value replaced, by member.
        self.bindings: dict[str, dict[str, Any]] = {}
        self._bound_from: dict[str, str] = {}
        self._substitutable: dict[str, str] = {}
        self.substituted: Counter[str] = Counter()

    def proxy(self, handle: int, ptype: str | None) -> ReplayProxy:
        existing = self.proxies.get(handle)
        if existing is not None:
            return existing
        if ptype is None or ptype not in self.types:
            self._halt(
                Verdict.ERROR, None, f"handle {handle} has no recorded type {ptype!r}"
            )
        proxy = ReplayProxy(self, handle, ptype, self.types[ptype])
        self.proxies[handle] = proxy
        return proxy

    def _halt(
        self, verdict: Verdict, divergence: Divergence | None, reason: str
    ) -> None:
        if self.stop is None:
            self.stop = ReplayStop(verdict, divergence, reason)
        raise self.stop

    def _actual(
        self, handle: int, op: str, canonical: list[Any], site: str
    ) -> dict[str, Any]:
        """The replay's side of an event (a divergence, an exhausted log): the
        only place a replay looks up its Python caller."""
        return {
            "h": handle,
            "op": op,
            "args": canonical,
            "site": site,
            "caller": "" if self.callers is CallerCapture.OFF else caller(),
            "kind": kind_of(op, canonical).value,
        }

    def _expect(self, handle: int, op: str, canonical: list[Any], site: str) -> Call:
        if self.stop is not None:
            raise self.stop
        if _IN_INERT.get():
            return self._serve_inert(handle, op, canonical, site)
        if self.pos >= len(self.strict):
            actual = self._actual(handle, op, canonical, site)
            self._halt(
                Verdict.EXHAUSTED,
                _divergence(
                    self.strict, self.pos, Side.LENGTH, Field.LENGTH, None, actual
                ),
                f"recipe request #{self.pos} ({site} from {actual['caller'] or '?'}) "
                f"beyond the {len(self.strict)} recorded",
            )
        expected = self.strict[self.pos]
        changed = request_field(expected, handle, op, canonical, self.mask)
        if changed is not None:
            actual = self._actual(handle, op, canonical, site)
            self._halt(
                Verdict.DIVERGED,
                _divergence(
                    self.strict, self.pos, Side.REQUEST, changed, expected, actual
                ),
                f"request {expected.seq}: expected {expected.site} got {site} "
                f"({changed.value} differs; recorded from {expected.caller or '?'}, "
                f"now from {actual['caller'] or '?'})",
            )
        self._bind(expected, canonical, handle, op, site)
        self.pos += 1
        self.served += 1
        return expected

    def _bind(
        self, expected: Call, canonical: list[Any], handle: int, op: str, site: str
    ) -> None:
        """A matched request's masked arguments: each recorded value now stands
        for the value this replay wrote. The binding is one-to-one for the whole
        replay; a write that would break that is a divergence."""
        for rule in self.mask:
            if rule.marker not in expected.args:
                continue
            for recorded, replayed in zip(expected.args, canonical, strict=True):
                if not (isinstance(recorded, str) and rule.pattern.fullmatch(recorded)):
                    continue
                bound = self.bindings.get(recorded)
                owner = self._bound_from.get(replayed)
                if bound is None and owner is None:
                    self.bindings[recorded] = {
                        "rule": rule.name,
                        "recorded": recorded,
                        "replayed": replayed,
                        "seq": expected.seq,
                    }
                    self._bound_from[replayed] = recorded
                    if replayed != recorded:
                        self._substitutable[recorded] = replayed
                    continue
                if bound is not None and bound["replayed"] == replayed:
                    continue
                actual = self._actual(handle, op, canonical, site)
                self._halt(
                    Verdict.DIVERGED,
                    _divergence(
                        self.strict,
                        self.pos,
                        Side.REQUEST,
                        Field.ARGS,
                        expected,
                        actual,
                    ),
                    f"request {expected.seq}: masked {rule.name} {replayed!r} for "
                    f"recorded {recorded!r} breaks the one-to-one binding (bound "
                    f"{bound['replayed'] if bound else None!r} <- {owner!r})",
                )

    def _rebound(self, value: Any, site: str) -> Any:
        """A recorded response as this replay's masked writes make it: every
        string equal to a bound recorded value becomes the replay's value."""
        if not self._substitutable:
            return value
        if type(value) is str:
            replayed = self._substitutable.get(value)
            if replayed is None:
                return value
            self.substituted[site] += 1
            return replayed
        if type(value) is not dict:
            return value
        if "t" in value:
            return {"t": [self._rebound(v, site) for v in value["t"]]}
        if "l" in value:
            return {"l": [self._rebound(v, site) for v in value["l"]]}
        if "v" in value:
            vt, inner = value["v"]
            return {"v": [vt, self._rebound(inner, site)]}
        if "d" in value:
            return {
                "d": [
                    [self._rebound(k, site), self._rebound(v, site)]
                    for k, v in value["d"]
                ]
            }
        if "struct" in value:
            rebound = dict(value)
            if "items" in value:
                rebound["items"] = [self._rebound(v, site) for v in value["items"]]
            if "attrs" in value:
                rebound["attrs"] = {
                    k: self._rebound(v, site) for k, v in value["attrs"].items()
                }
            return rebound
        return value

    def _serve_inert(
        self, handle: int, op: str, canonical: list[Any], site: str
    ) -> Call:
        """Best effort: the first unused recorded inert call with exactly this
        request, wherever it was recorded; else ``E_FAIL``."""
        masked = _masked(canonical, self.mask)
        for index in range(self._inert_first, len(self.inert)):
            candidate = self.inert[index]
            if self._inert_used[index] or candidate.handle != handle:
                continue
            if candidate.op != op or not same(
                _masked(candidate.args, self.mask), masked
            ):
                continue
            self._inert_used[index] = True
            while (
                self._inert_first < len(self.inert)
                and self._inert_used[self._inert_first]
            ):
                self._inert_first += 1
            self.inert_served += 1
            return candidate
        self.inert_unserved[site] += 1
        if site not in self._unserved_callers:
            self._unserved_callers[site] = self._actual(handle, op, canonical, site)[
                "caller"
            ]
        return Call(
            -1,
            handle,
            op,
            canonical,
            site,
            None,
            _UNRECORDED_INERT,
            origin=Origin.INERT,
        )

    def call(self, proxy: ComProxy, op: str, args: tuple[Any, ...]) -> Any:
        canonical = [self.codec.encode(a) for a in args]
        expected = self._expect(proxy._h, op, canonical, _site())
        if expected.outs is not None:
            variants = list(_iter_variants(args, self.codec.pw.variant))
            for variant, out in zip(variants, expected.outs, strict=False):
                if out is not None:
                    via, value = out
                    setattr(
                        variant,
                        via,
                        self.codec.decode(self._rebound(value, expected.site)),
                    )
        if self.materialise is not None:
            self.materialise(expected.seq)
        if expected.raised is not None:
            raise self.codec.exception(expected.raised)
        return self.codec.decode(self._rebound(expected.result, expected.site))

    def compare(self, proxy: ComProxy, op: str, other: ComProxy) -> bool:
        expected = self._expect(proxy._h, op, [{"h": other._h}], _site())
        return bool(expected.result)

    def identity(self, proxy: ComProxy) -> int:
        expected = self._expect(proxy._h, "__hash__", [], _site())
        if expected.raised is not None:
            raise self.codec.exception(expected.raised)
        return int(expected.result)

    def finish(self) -> tuple[Verdict, Divergence | None, str]:
        if self.stop is not None:
            return self.stop.verdict, self.stop.divergence, self.stop.reason
        if self.pos < len(self.strict):
            expected = self.strict[self.pos]
            return (
                Verdict.UNCONSUMED,
                _divergence(
                    self.strict, self.pos, Side.LENGTH, Field.LENGTH, expected, None
                ),
                f"script returned with {len(self.strict) - self.pos} recorded "
                "recipe requests unserved",
            )
        return (
            Verdict.NOOP,
            None,
            "every recipe request matched and the recipe stream was fully consumed",
        )

    def inert_report(self) -> dict[str, Any]:
        """How the recipe-inert calls were served (none of it is the verdict)."""
        unconsumed = Counter(
            call.site
            for call, used in zip(self.inert, self._inert_used, strict=True)
            if not used
        )
        return {
            "recorded": len(self.inert),
            "served": self.inert_served,
            "unserved": sum(self.inert_unserved.values()),
            "unserved_members": [
                {"member": site, "count": count, "caller": self._unserved_callers[site]}
                for site, count in self.inert_unserved.most_common(_EXAMPLES)
            ],
            "unconsumed": sum(unconsumed.values()),
            "unconsumed_members": dict(unconsumed.most_common(_EXAMPLES)),
        }

    def substitution_report(self) -> dict[str, Any]:
        """Masked values this replay rebound, and the responses it rewrote."""
        return {
            "rule": "a served response string EQUAL to a bound recorded value is "
            "served as the replay's value; substrings are never rewritten",
            "bindings": list(self.bindings.values()),
            "count": sum(self.substituted.values()),
            "by_member": dict(self.substituted.most_common()),
        }


# ---------------------------------------------------------------------------
# Adapter state at build entry (R11)
# ---------------------------------------------------------------------------


def _class_ref(cls: type) -> dict[str, str]:
    if cls.__name__.endswith("_EarlyBound") and len(cls.__bases__) == 1:
        base = cls.__bases__[0]
        return {"strict": base.__name__, "module": base.__module__}
    return {"module": cls.__module__, "qualname": cls.__qualname__}


@contextlib.contextmanager
def replaying(adapter: Any, replayer: Replayer) -> Iterator[dict[str, Any]]:
    """Serve ``replayer``'s log to everything the build does through
    ``adapter`` (a freshly constructed one; its recorded build-entry state is
    restored first), with the recipe-inert entry points wrapped exactly as in
    the recording. Yields the R11 restoration evidence."""
    global _ACTIVE
    with funnel(), inert_entry_points():
        evidence = restore_adapter(adapter, replayer.header.adapter_state, replayer)
        _ACTIVE = replayer
        try:
            yield evidence
        finally:
            _ACTIVE = None


def _resolve_class(ref: dict[str, str]) -> type:
    import importlib

    module = importlib.import_module(ref["module"])
    if "strict" in ref:
        from solidworks_mcp.adapters import sw_type_info

        # Connect registers the strict classes for typed returns
        # (_early_bound_application -> _ensure_loaded); a replay never
        # connects, so do the same registration here.
        sw_type_info._ensure_loaded()
        return sw_type_info._strict_subclass(getattr(module, ref["strict"]))
    target: Any = module
    for part in ref["qualname"].split("."):
        target = getattr(target, part)
    return target


def _json_value(value: Any, codec: Codec) -> tuple[bool, Any]:
    cls = type(value)
    if value is None or cls in (bool, int, str):
        return True, value
    if cls is float:
        return True, codec.encode(value)
    if cls in (list, tuple):
        items = [_json_value(v, codec) for v in value]
        if all(ok for ok, _ in items):
            return True, {cls.__name__: [v for _, v in items]}
        return False, None
    if cls is dict and all(type(k) is str for k in value):
        items = {k: _json_value(v, codec) for k, v in value.items()}
        if all(ok for ok, _ in items.values()):
            return True, {"dict": {k: v for k, (_, v) in items.items()}}
    return False, None


def _qualname(value: Any) -> str:
    return f"{type(value).__module__}.{type(value).__qualname__}"


def _describe_state(
    obj: Any,
    codec: Codec,
    root: Callable[[Any, str, Any], ComProxy] | None,
    adapter: Any = None,
) -> dict[str, Any]:
    """Describe ``obj.__dict__`` (the adapter, then each service bound to
    it); with ``root``, swap every COM object held for a root proxy."""
    adapter = obj if adapter is None else adapter
    state: dict[str, Any] = {}
    for key, value in sorted(vars(obj).items()):
        inner = _oleobj_of(value)
        if inner is not None and (is_interface(inner) or isinstance(inner, ComProxy)):
            if root is not None and not isinstance(inner, ComProxy):
                inner = root(value, "_oleobj_", inner)
                value.__dict__["_oleobj_"] = inner
            state[key] = {
                "com": getattr(inner, "_h", None),
                "ptype": getattr(inner, "_ptype", type(inner).__name__),
                "class": _class_ref(type(value)),
            }
            continue
        if is_interface(value) or isinstance(value, ComProxy):
            if root is not None and not isinstance(value, ComProxy):
                value = root(obj, key, value)
                setattr(obj, key, value)
            state[key] = {
                "com_raw": getattr(value, "_h", None),
                "ptype": getattr(value, "_ptype", type(value).__name__),
            }
            continue
        ok, encoded = _json_value(value, codec)
        if ok:
            state[key] = {"json": encoded}
        elif obj is adapter and getattr(value, "_adapter", None) is adapter:
            state[key] = {
                "service": _qualname(value),
                "state": _describe_state(value, codec, root, adapter),
            }
        else:
            state[key] = {"opaque": _qualname(value)}
    return state


def restore_adapter(
    adapter: Any, recorded: dict[str, Any], replayer: Replayer
) -> dict[str, Any]:
    """Give a freshly constructed adapter the recorded build-entry state:
    COM attributes become replay proxies; plain values are compared and, where
    they differ, restored from the record. Returns the R11 evidence."""
    report: dict[str, Any] = {"com": [], "restored": [], "mismatched": [], "extra": []}
    _restore(adapter, recorded, replayer, report, "")
    return report


def _restore(
    obj: Any,
    recorded: dict[str, Any],
    replayer: Replayer,
    report: dict[str, Any],
    prefix: str,
) -> None:
    fresh = _describe_state(obj, replayer.codec, None)
    for key, entry in recorded.items():
        name = prefix + key
        if "com" in entry or "com_raw" in entry:
            handle = entry.get("com", entry.get("com_raw"))
            if handle is None:
                report["mismatched"].append({"key": name, "recorded": entry})
                continue
            proxy = replayer.proxy(handle, entry["ptype"])
            if "com" in entry:
                cls = _resolve_class(entry["class"])
                wrapper = cls.__new__(cls)
                wrapper.__dict__["_oleobj_"] = proxy
                setattr(obj, key, wrapper)
            else:
                setattr(obj, key, proxy)
            report["com"].append(name)
            continue
        current = fresh.get(key)
        if "service" in entry and current is not None and "service" in current:
            _restore(getattr(obj, key), entry["state"], replayer, report, f"{name}.")
            continue
        if current == entry:
            continue
        if "json" in entry:
            setattr(obj, key, _decode_state(entry["json"], replayer.codec))
            report["restored"].append(
                {"key": name, "recorded": entry, "fresh": current}
            )
            continue
        report["mismatched"].append({"key": name, "recorded": entry, "fresh": current})
    report["extra"].extend(prefix + key for key in sorted(set(fresh) - set(recorded)))


def _decode_state(value: Any, codec: Codec) -> Any:
    if not isinstance(value, dict):
        return value
    if "f" in value:
        return codec.decode(value)
    if "list" in value:
        return [_decode_state(v, codec) for v in value["list"]]
    if "tuple" in value:
        return tuple(_decode_state(v, codec) for v in value["tuple"])
    return {k: _decode_state(v, codec) for k, v in value["dict"].items()}


# ---------------------------------------------------------------------------
# R1 escape audit
# ---------------------------------------------------------------------------


def _wrapper_census(pw: _Pywin32) -> dict[str, Any]:
    """Live pywin32 wrappers by what their ``_oleobj_`` is."""
    proxied = 0
    real: Counter[str] = Counter()
    wrapper_types = (pw.client.DispatchBaseClass, pw.dynamic.CDispatch)
    for obj in gc.get_objects():
        if not isinstance(obj, wrapper_types):
            continue
        inner = obj.__dict__.get("_oleobj_")
        if isinstance(inner, ComProxy):
            proxied += 1
        elif inner is not None and is_interface(inner):
            real[type(obj).__name__] += 1
    count = getattr(pw.pythoncom, "_GetInterfaceCount", None)
    return {
        "wrappers_on_proxies": proxied,
        "wrappers_on_real_objects": dict(real),
        "live_interface_objects": count() if count else None,
    }


# ---------------------------------------------------------------------------
# Recording window
# ---------------------------------------------------------------------------


def _environment() -> dict[str, str | None]:
    return {key: os.environ.get(key) for key in ENVIRONMENT_KEYS}


def _repo_relative(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return Path(path).resolve().as_posix()


@contextlib.contextmanager
def recording(
    adapter: Any,
    *,
    script: Path,
    log: Path,
    roots: Roots,
    label: str | None = None,
    sw_revision: str | None = None,
    audit: bool = True,
    callers: CallerCapture = DEFAULT_CALLERS,
) -> Iterator[Recorder]:
    """Record every COM operation of the build window into ``log``.

    Wraps the COM objects the adapter holds at entry as root proxies, installs
    the funnel, the recipe-inert entry points and (WARN mode) the file
    observer, and on exit restores the adapter's original objects so teardown
    runs unrecorded on real ones."""
    global _ACTIVE
    writer = LogWriter(log)
    capture = capture_dir_of(log)
    if capture.exists():
        with _ENGINE_IO:
            shutil.rmtree(capture)
    recorder = Recorder(writer, roots, capture, callers)
    swapped: list[tuple[Any, str, Any]] = []

    def root(owner: Any, name: str, real: Any) -> ComProxy:
        swapped.append((owner, name, real))
        return recorder.root(real)

    with funnel(), inert_entry_points() as inert_entries:
        census_entry = _wrapper_census(recorder.pw) if audit else None
        state = _describe_state(adapter, recorder.codec, root)
        header = Header(
            schema=SCHEMA,
            label=label or Path(script).stem,
            script=_repo_relative(Path(script)),
            script_sha256=sha256_file(Path(script)),
            engine=sha256_file(ENGINE_FILE),
            sw_revision=sw_revision,
            environment=_environment(),
            provenance_mask=[rule.to_json() for rule in PROVENANCE_MASK],
            adapter_state=state,
            roots={"out": str(roots.out), "repo": str(roots.repo)},
            started_utc=datetime.datetime.now(datetime.UTC).isoformat(),
        )
        writer.header(header)
        observer = _FileObserver(roots.out, GuardMode.WARN, _allowed_side_writes())
        if audit:
            _AUDIT.install()
            _AUDIT.observer = observer
        outcome = "returned"
        started = time.perf_counter()
        _ACTIVE = recorder
        try:
            yield recorder
        except BaseException as exc:
            outcome = f"raised {type(exc).__name__}: {exc}"
            raise
        finally:
            window = time.perf_counter() - started
            _ACTIVE = None
            _AUDIT.observer = None
            audit_started = time.perf_counter()
            census_exit = _wrapper_census(recorder.pw) if audit else None
            audit_seconds = time.perf_counter() - audit_started
            recorder.closed = True
            for owner, name, real in reversed(swapped):
                if name == "_oleobj_":
                    owner.__dict__["_oleobj_"] = real
                else:
                    setattr(owner, name, real)
            writer.close(
                {
                    "status": "complete",
                    "outcome": outcome,
                    "calls": recorder.seq,
                    "handles": recorder.allocated[Origin.RECIPE],
                    "inert_handles": recorder.allocated[Origin.INERT],
                    "inert_calls": recorder.origins[Origin.INERT],
                    "types": recorder.types,
                    "external": recorder.external,
                    "internal_paths": sorted(recorder.internal_paths),
                    "reads": observer.reads,
                    "captured": recorder.captured,
                    "capture_dir": capture.name,
                    "capture_bytes": recorder.capture_bytes,
                    "capture_stored_bytes": recorder.capture_stored_bytes,
                    "callers": recorder.callers.value,
                    "inert_entry_points": len(inert_entries),
                    "clock_seconds": {
                        "in_calls": recorder.clock["calls"] / 1e9,
                        "com": recorder.clock["com"] / 1e9,
                        "engine": (recorder.clock["calls"] - recorder.clock["com"])
                        / 1e9,
                        "caller": recorder.clock["caller"] / 1e9,
                        "capture": recorder.clock["capture"] / 1e9,
                    },
                    "writes_outside_out": observer.outside,
                    "adopted_inside_calls": recorder.adopted_inside,
                    "adopted_outside_calls": recorder.adopted_outside,
                    "foreign_thread_calls": recorder.foreign_thread_calls,
                    "window_seconds": window,
                    "escape_audit": {
                        "at_entry": census_entry,
                        "at_exit": census_exit,
                        "seconds": audit_seconds,
                    },
                }
            )


# ---------------------------------------------------------------------------
# Sandbox (replay only)
# ---------------------------------------------------------------------------

_PYTHONCOM_ROOTS = (
    "CoCreateInstance",
    "CoCreateInstanceEx",
    "GetActiveObject",
    "connect",
    "new",
    "CoGetObject",
    "MkParseDisplayName",
    "GetRunningObjectTable",
)
_CLIENT_ROOTS = (
    "DispatchEx",
    "GetActiveObject",
    "GetObject",
    "Moniker",
    "DispatchWithEvents",
)


class Sandbox:
    """Makes every Python route to a live COM server raise.

    ``win32com.client.Dispatch`` and ``dynamic.Dispatch`` still wrap a
    proxy (that is how replayed results become wrappers); anything else --
    a ProgID, a CLSID, a real dispatch -- is a violation. The pythoncom
    entry points underneath them (``CoCreateInstance``, ``GetActiveObject``,
    ``connect``, ``new`` ...) raise unconditionally."""

    def __init__(self) -> None:
        self.violations: list[dict[str, str]] = []
        self._saved: list[tuple[Any, str, Any]] = []

    def _refuse(self, name: str) -> Callable[..., Any]:
        def refused(*args: Any, **kwargs: Any) -> Any:
            self.violations.append({"call": name, "args": repr(args)[:200]})
            raise SandboxViolation(f"replay attempted live COM: {name}{args!r:.200}")

        refused.__name__ = name.rpartition(".")[2]
        return refused

    def _guarded_dispatch(
        self, name: str, original: Callable[..., Any]
    ) -> Callable[..., Any]:
        refused = self._refuse(name)

        def dispatch(target: Any, *args: Any, **kwargs: Any) -> Any:
            if isinstance(target, ComProxy) or isinstance(_oleobj_of(target), ComProxy):
                return original(target, *args, **kwargs)
            return refused(target, *args, **kwargs)

        dispatch.__name__ = "Dispatch"
        return dispatch

    def _patch(self, owner: Any, name: str, value: Any) -> None:
        if hasattr(owner, name):
            self._saved.append((owner, name, getattr(owner, name)))
            setattr(owner, name, value)

    def install(self) -> Sandbox:
        pw = _pw()
        for name in _PYTHONCOM_ROOTS:
            self._patch(pw.pythoncom, name, self._refuse(f"pythoncom.{name}"))
        for name in _CLIENT_ROOTS:
            self._patch(pw.client, name, self._refuse(f"win32com.client.{name}"))
        self._patch(
            pw.client,
            "Dispatch",
            self._guarded_dispatch("win32com.client.Dispatch", pw.client.Dispatch),
        )
        self._patch(
            pw.dynamic,
            "Dispatch",
            self._guarded_dispatch(
                "win32com.client.dynamic.Dispatch", pw.dynamic.Dispatch
            ),
        )
        self._patch(
            pw.dynamic,
            "DumbDispatch",
            self._refuse("win32com.client.dynamic.DumbDispatch"),
        )
        from win32com.client import gencache

        for name in ("EnsureDispatch", "EnsureDispatchEx"):
            self._patch(gencache, name, self._refuse(f"gencache.{name}"))
        return self

    def uninstall(self) -> None:
        for owner, name, value in reversed(self._saved):
            setattr(owner, name, value)
        self._saved.clear()


# ---------------------------------------------------------------------------
# Record / replay a whole build script (the CLI's two modes)
# ---------------------------------------------------------------------------


def redirect_outputs(out_root: Path) -> None:
    """Point ``_paths.OUT_*`` at ``out_root`` BEFORE any build module binds
    them (``from _paths import OUT_SLDPRT`` copies the value at import)."""
    import _paths

    if "_part_save" in sys.modules:
        raise RuntimeError("_part_save was imported before the outputs were redirected")
    for name, sub in (
        ("OUT_SLDPRT", "sldprt"),
        ("OUT_SLDASM", "sldasm"),
        ("OUT_PNG", "png"),
        ("OUT_STL", "stl"),
    ):
        setattr(_paths, name, out_root / sub)


# Overlay directories (changed helper modules) placed first on sys.path by
# use_overlay, before the build imports anything from cad/scripts.
_OVERLAYS: list[Path] = []


def use_overlay(directory: Path) -> None:
    """Import modules from ``directory`` ahead of ``cad/scripts`` for this
    process: the source-change controls replay a log against a changed copy of
    a helper. Call before anything imports the overlaid modules (the CLI does it
    first); :func:`overlay_report` says which ones actually came from it."""
    path = directory.resolve()
    _OVERLAYS.append(path)
    sys.path.insert(0, str(path))
    _BUILD_PREFIXES.append(os.path.normcase(str(path)) + os.sep)


def overlay_report() -> dict[str, Any]:
    """Per overlay module: whether the build imported it, and from where."""
    modules: dict[str, dict[str, Any]] = {}
    for directory in _OVERLAYS:
        for source in sorted(directory.glob("*.py")):
            loaded = sys.modules.get(source.stem)
            origin = getattr(loaded, "__file__", None)
            from_overlay = origin is not None and Path(origin).resolve() == source
            modules[source.stem] = {
                "overlay": str(source),
                "sha256": sha256_file(source),
                "imported": loaded is not None,
                "from_overlay": from_overlay,
                "loaded_from": origin,
            }
    return {"directories": [str(d) for d in _OVERLAYS], "modules": modules}


def run_script(script: Path) -> int:
    """Run a build script as ``__main__`` (argv[0] drives run_build's labels).
    Its directory goes on ``sys.path`` after any overlay, never ahead of it."""
    import runpy

    sys.argv = [str(script)]
    if str(script.parent) not in sys.path:
        sys.path.insert(len(_OVERLAYS), str(script.parent))
    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        return code if isinstance(code, int) else 1
    return 0


def check_inputs(conversation: Conversation) -> list[dict[str, Any]]:
    """P3: the replay's inputs equal the record's, except Python source.

    Pinned: the engine (it decides what a request is and how a response is
    served), the declared environment keys (process inputs part closures read,
    design Q5), and every file outside the output root a COM argument named
    (templates and the like: SolidWorks reads them, so new content would change
    its answers behind an unchanged request). Never pinned: the build script and
    the helper modules. Changed source is what a replay exists to judge, and the
    request stream itself is the evidence; ``header.script_sha256`` is
    informational."""
    mismatches: list[dict[str, Any]] = []
    header = conversation.header
    if header.engine != sha256_file(ENGINE_FILE):
        mismatches.append({"input": "engine", "recorded": header.engine})
    for key, value in header.environment.items():
        if os.environ.get(key) != value:
            mismatches.append(
                {
                    "input": f"env:{key}",
                    "recorded": value,
                    "replay": os.environ.get(key),
                }
            )
    roots = Roots(Path(header.roots["out"]), REPO_ROOT)
    for canonical, digest in conversation.trailer.get("external", {}).items():
        path = Path(roots.decode(canonical))
        actual = sha256_file(path) if path.is_file() else None
        if actual != digest:
            mismatches.append(
                {"input": canonical, "recorded": digest, "replay": actual}
            )
    return mismatches


def _tree_files(root: Path) -> dict[str, str]:
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def record_build(
    script: Path,
    out_root: Path,
    log: Path | None,
    callers: CallerCapture = DEFAULT_CALLERS,
) -> dict[str, Any]:
    """Run ``script`` against the live seat with its outputs under ``out_root``.

    With ``log``, the build window (``build(adapter)``, after connect, discard
    and template pin, before teardown -- design section 1.2) is recorded; with
    no log the same window is only timed (the unrecorded W0 baseline)."""
    redirect_outputs(out_root)
    import _session

    original_run_build = _session.run_build
    timing: dict[str, Any] = {
        "script": _repo_relative(script),
        "out_root": str(out_root),
    }

    def recorded_run_build(build: Callable[[Any], Any]) -> int:
        async def window(adapter: Any) -> Any:
            started = time.perf_counter()
            try:
                if log is None:
                    return await build(adapter)
                revision = adapter._attempt(
                    lambda: adapter._get_attr_or_call(adapter.swApp, "RevisionNumber"),
                    default=None,
                )
                with recording(
                    adapter,
                    script=script,
                    log=log,
                    roots=Roots(out_root),
                    sw_revision=str(revision) if revision is not None else None,
                    callers=callers,
                ):
                    return await build(adapter)
            finally:
                timing["window_seconds"] = time.perf_counter() - started

        return original_run_build(window)

    _session.run_build = recorded_run_build
    started = time.perf_counter()
    timing["rc"] = run_script(script)
    timing["script_seconds"] = time.perf_counter() - started
    return timing


def replay_build(
    script: Path,
    log: Path,
    scratch_out: Path,
    base_outputs: Path,
    *,
    capture_dir: Path | None = None,
    mask: Sequence[MaskRule] = PROVENANCE_MASK,
) -> ReplayResult:
    """Run ``script`` with SolidWorks absent, serving ``log``'s responses.

    Process-global and one-shot: installs the sandbox and an audit hook that
    stay for the life of the process. Run it in a dedicated subprocess
    (``com_replay.py replay``). ``base_outputs`` is the recording run's output
    root, used only to compare the Python-written outputs byte for byte."""
    started = time.perf_counter()
    conversation = load(log)
    if capture_dir is None:
        capture_dir = log.parent / conversation.trailer.get(
            "capture_dir", capture_dir_of(log).name
        )
    details: dict[str, Any] = {
        "log": str(log),
        "script": _repo_relative(script),
        "base_outputs": str(base_outputs),
        "capture_dir": str(capture_dir),
        "scratch": str(scratch_out),
        "base_status": conversation.trailer.get("status"),
        "base_outcome": conversation.trailer.get("outcome"),
    }
    mismatches = check_inputs(conversation)
    if mismatches:
        details["input_mismatches"] = mismatches
        details["reason"] = "inputs differ from the recording: " + ", ".join(
            str(m["input"]) for m in mismatches
        )
        return ReplayResult(
            Verdict.INPUT_MISMATCH,
            None,
            0,
            len(recipe_calls(conversation.calls)),
            time.perf_counter() - started,
            {},
            {},
            details,
        )

    if scratch_out.exists():
        with _ENGINE_IO:
            shutil.rmtree(scratch_out)
    scratch_out.mkdir(parents=True)
    sys.dont_write_bytecode = True
    sandbox = Sandbox().install()
    observer = _FileObserver(scratch_out, GuardMode.RAISE, _allowed_side_writes())
    _AUDIT.install()
    _AUDIT.observer = observer
    roots = Roots(scratch_out, REPO_ROOT)
    materialiser = Materialiser(conversation, capture_dir, scratch_out)
    replayer = Replayer(
        conversation,
        roots,
        mask,
        materialiser,
        CallerCapture(conversation.trailer.get("callers", DEFAULT_CALLERS.value)),
    )
    redirect_outputs(scratch_out)
    import _session

    script_error: dict[str, Any] = {}
    window: dict[str, Any] = {}

    def note_error(exc: BaseException) -> None:
        import traceback

        script_error.update(
            type=type(exc).__name__,
            message=str(exc),
            traceback="".join(traceback.format_exception(exc)),
        )

    def replay_run_build(build: Callable[[Any], Any]) -> int:
        import asyncio

        import _telemetry
        from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

        name = Path(sys.argv[0]).stem if sys.argv and sys.argv[0] else "build"
        target = name.removeprefix("build_").removesuffix("_assembly")
        adapter = PyWin32Adapter({})
        with _telemetry.build_session(target, script=name):
            t0 = time.perf_counter()
            try:
                with replaying(adapter, replayer) as r11:
                    window["r11"] = r11
                    asyncio.run(build(adapter))
            except ReplayStop:
                return 1
            except (Exception, SandboxViolation) as exc:  # noqa: BLE001 - recorded
                note_error(exc)
                return 1
            finally:
                window["seconds"] = time.perf_counter() - t0
        return 0

    _session.run_build = replay_run_build
    try:
        rc = run_script(script)
    except ReplayStop:
        rc = 1
    except (Exception, SandboxViolation) as exc:  # noqa: BLE001 - recorded
        note_error(exc)
        rc = 1
    _AUDIT.observer = None
    verdict, divergence, reason = _verdict(
        replayer, sandbox, observer, script_error, rc
    )
    produced = _tree_files(scratch_out)
    com_outputs = {
        rel: digest
        for rel, digest in produced.items()
        if rel in materialiser.copied and rel not in observer.written
    }
    py_outputs = {
        rel: digest for rel, digest in produced.items() if rel not in com_outputs
    }
    base_files = _tree_files(base_outputs)
    recorded_reads = {tuple(entry) for entry in conversation.trailer.get("reads", [])}
    count = getattr(_pw().pythoncom, "_GetInterfaceCount", None)
    details.update(
        reason=reason,
        rc=rc,
        script_error=script_error or None,
        window_seconds=window.get("seconds"),
        r11=window.get("r11"),
        materialised=materialiser.copied,
        materialise_missing=materialiser.missing,
        py_output_mismatches={
            rel: {"replay": digest, "base": base_files.get(rel)}
            for rel, digest in py_outputs.items()
            if base_files.get(rel) != digest
        },
        base_only_outputs=sorted(set(base_files) - set(produced)),
        reads=observer.reads,
        read_mismatches=sorted(
            {tuple(entry) for entry in observer.reads} ^ recorded_reads
        ),
        writes_outside_scratch=observer.outside,
        sandbox_violations=sandbox.violations + observer.violations,
        proxies_served=len(replayer.proxies),
        live_interface_objects_at_end=count() if count else None,
        inert=replayer.inert_report(),
        substitutions=replayer.substitution_report(),
        recorded_total=len(conversation.calls),
        overlay=overlay_report(),
    )
    return ReplayResult(
        verdict,
        divergence,
        replayer.served,
        len(replayer.strict),
        time.perf_counter() - started,
        com_outputs,
        py_outputs,
        details,
    )


def _verdict(
    replayer: Replayer,
    sandbox: Sandbox,
    observer: _FileObserver,
    script_error: dict[str, Any],
    rc: int,
) -> tuple[Verdict, Divergence | None, str]:
    """Precedence: sandbox, replay stop, script failure, unconsumed, no-op."""
    verdict, divergence, reason = replayer.finish()
    if sandbox.violations or observer.violations:
        return (
            Verdict.SANDBOX,
            divergence,
            f"sandbox violation (replay state: {verdict.value}: {reason})",
        )
    if replayer.stop is not None:
        return verdict, divergence, reason
    if script_error:
        return (
            Verdict.ERROR,
            divergence,
            f"the script raised {script_error['type']} after {replayer.served} served requests",
        )
    if rc != 0:
        return Verdict.ERROR, divergence, f"the script exited {rc} with no replay stop"
    return verdict, divergence, reason
