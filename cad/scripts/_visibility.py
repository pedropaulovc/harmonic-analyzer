"""Saved-document display hygiene: hide construction geometry, and prove it."""

from __future__ import annotations

import time
from collections.abc import Iterator, Mapping
from types import SimpleNamespace
from typing import Any

from opentelemetry import trace

import _telemetry


@_telemetry.traced("appearance.blank_reference_geometry")
def blank_reference_geometry(
    adapter: Any, references: tuple[tuple[str, str], ...]
) -> None:
    """Keep named planes/axes selectable while hiding them from saved renders."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = adapter.currentModel
    model.ClearSelection2(True)
    for index, (name, kind) in enumerate(references):
        selected = model.Extension.SelectByID2(
            name,
            kind,
            0,
            0,
            0,
            index > 0,
            0,
            null_callout(),
            0,
        )
        if not selected:
            raise RuntimeError(f"cannot select {name!r} to hide reference geometry")
    model.BlankRefGeom()
    model.ClearSelection2(True)
    _telemetry.success(f"blanked {len(references)} reference entities")


# swVisibilityState_e: IFeature.Visible reads 1 (Hide) once a sketch or
# reference entity is blanked and 2 (Shown) while it renders.
_HIDDEN = 1
_SHOWN = 2
# Feature types whose shown state draws construction geometry in every render
# of the document and of every assembly that places it: sketch points and lines
# (a Hole Wizard's placement points included), planes, axes, points and
# reference curves.  Solid features also read Visible == 2 (their bodies are
# shown), so only these types are checked.
REFERENCE_FEATURE_KINDS = {
    "ProfileFeature": "sketch",
    "3DProfileFeature": "3D sketch",
    "RefPlane": "plane",
    "RefAxis": "axis",
    "RefPoint": "point",
    "Helix": "curve",
    "CompositeCurve": "curve",
}
# An assembly lists each placed component as a feature of this type.  Its
# sub-features are the component's own tree, which that part's save proved.
_COMPONENT_FEATURE_TYPES = frozenset({"Reference"})
_MAX_FEATURES = 20000


class FeatureWalk:
    """Every feature of a model and, recursively, its sub-features, in tree order.

    The stock-fastener cleanup's walk.  It does not descend into an assembly's
    components (each part's own save proved its tree), counts what it visits in
    ``visited`` for the span that owns the walk, and refuses a runaway
    traversal.  The save check does not use it: it costs three COM calls per
    feature just to move (``visible_reference_geometry``).
    """

    def __init__(self, model: Any) -> None:
        self.model = model
        self.visited = 0

    def __iter__(self) -> Iterator[Any]:
        from _common import _early_bound, _read_member

        def siblings(feature: Any, next_member: str) -> Iterator[Any]:
            while feature:
                self.visited += 1
                if self.visited > _MAX_FEATURES:
                    raise RuntimeError(
                        f"feature traversal exceeded {_MAX_FEATURES} features"
                    )
                feature = _early_bound(feature, "IFeature")
                yield feature
                kind = str(_read_member(feature, "GetTypeName2"))
                if kind not in _COMPONENT_FEATURE_TYPES:
                    child = _read_member(feature, "GetFirstSubFeature")
                    yield from siblings(child, "GetNextSubFeature")
                feature = _read_member(feature, next_member)

        yield from siblings(_read_member(self.model, "FirstFeature"), "GetNextFeature")


class _RecordedCall:
    """Stands in for a raw dispatch, so a generated member hands over its call."""

    def __init__(self) -> None:
        self.args: tuple[Any, ...] = ()

    def InvokeTypes(self, *args: Any) -> None:
        self.args = args


_INVOCATIONS: dict[tuple[str, str], tuple[Any, ...]] = {}


def _invocation(interface: str, member: str, *args: Any) -> tuple[Any, ...]:
    """The ``InvokeTypes`` arguments ``interface``'s generated wrapper sends for
    ``member`` (called with ``args``), recorded once per process.

    The dispid, flags and types come from the type-library wrapper, never from
    a hand-written number, and recording them makes no COM call: the wrapper
    is built on a stand-in that keeps the call instead of sending it.  The
    tuple ends with ``args``, which never changes per key here."""
    from _common import _early_bound

    key = (interface, member)
    if key not in _INVOCATIONS:
        recorded = _RecordedCall()
        wrapper = _early_bound(SimpleNamespace(_oleobj_=recorded), interface)
        value = getattr(wrapper, member)  # a property sends its call here
        if callable(value):
            value(*args)
        if not recorded.args:
            raise RuntimeError(f"{interface}.{member}: the wrapper sent no call")
        _INVOCATIONS[key] = recorded.args
    return _INVOCATIONS[key]


def _dispatch(obj: Any) -> Any:
    """The raw IDispatch under a pywin32 wrapper (a test double is its own)."""
    return getattr(obj, "_oleobj_", obj)


def visible_reference_geometry(model: Any, label: str = "") -> list[tuple[str, str]]:
    """``(name, kind)`` of every shown sketch, plane, axis, point or curve.

    One ``IFeatureManager.GetFeatures(False)`` call returns every feature and
    child feature, and none inside an assembly's components (the SolidWorks
    API reference), so nothing is walked.  Every call after the first hop goes
    straight to a RAW dispatch by dispid (``_invocation``), because pywin32
    wraps what a wrapper returns, and each wrap costs round trips: it reads
    the element's type info (GetTypeInfo, GetTypeAttr), and the generated
    class it builds runs a QueryInterface in its constructor, as
    ``_early_bound`` does on a raw dispatch.  Three per ``GetFeatures``
    element: 1.94 s of harmonic_base's 3.18 s check on a farm seat (~6-9 ms
    a round trip).

    So each feature costs one round trip, ``GetTypeName2``; ``Visible`` is read
    only on the reference types and ``Name`` only on a shown one.  Plus three
    per check: ``FeatureManager``, ``GetFeatures``, and a ``GetIDsOfNames`` on
    the first feature proving the elements answer ``IFeature``'s dispids (the
    array is untyped, and a foreign table would read every type as unknown,
    so the check would pass blind).  #880's save bar is <= 1 s."""
    from _common import _early_bound

    started = time.perf_counter()
    manager = _dispatch(_early_bound(model, "IModelDoc2")).InvokeTypes(
        *_invocation("IModelDoc2", "FeatureManager")
    )
    features = tuple(
        manager.InvokeTypes(*_invocation("IFeatureManager", "GetFeatures", False)) or ()
    )
    fetch_s = time.perf_counter() - started
    com_calls = 2
    if len(features) > _MAX_FEATURES:
        raise RuntimeError(f"{label}: {len(features)} features exceed {_MAX_FEATURES}")
    type_name = _invocation("IFeature", "GetTypeName2")
    if features:
        answered = features[0].GetIDsOfNames(0, "GetTypeName2")
        com_calls += 1
        if answered != type_name[0]:
            raise RuntimeError(
                f"{label}: GetFeatures returned a dispatch whose GetTypeName2 is "
                f"dispid {answered}, not IFeature's {type_name[0]}"
            )
    visible = _invocation("IFeature", "Visible")
    feature_name = _invocation("IFeature", "Name")
    shown: list[tuple[str, str]] = []
    seen: set[str] = set()
    for feature in features:
        kind = REFERENCE_FEATURE_KINDS.get(str(feature.InvokeTypes(*type_name)))
        com_calls += 1
        if kind is None:
            continue
        com_calls += 1
        if int(feature.InvokeTypes(*visible)) != _SHOWN:
            continue
        name = str(feature.InvokeTypes(*feature_name))
        com_calls += 1
        if name in seen:
            continue
        seen.add(name)
        shown.append((name, kind))
    _record_scan(
        label, len(features), com_calls, fetch_s, time.perf_counter() - started
    )
    return shown


def _record_scan(
    label: str, features: int, com_calls: int, fetch_s: float, scan_s: float
) -> None:
    """Put the check's size and cost on its span AND in the console log.

    A farm leaf uploads only its task.log, so this line is the per-save
    visibility cost that leaves the worker (#880's <= 1 s save bar)."""
    span = trace.get_current_span()
    span.set_attribute("features_visited", features)
    span.set_attribute("com_calls", com_calls)
    span.set_attribute("fetch_s", fetch_s)
    span.set_attribute("walk_s", scan_s)
    _telemetry.info(
        f"{label}: check scanned {features} features with {com_calls} COM calls "
        f"in {scan_s:.3f}s (GetFeatures {fetch_s:.3f}s)",
        features_visited=features,
        com_calls=com_calls,
        fetch_s=fetch_s,
        walk_s=scan_s,
        walk_purpose="check",
    )


@_telemetry.traced("appearance.blank_sketch_feature", label_param="label")
def blank_sketch_feature(model: Any, feature: Any, label: str) -> None:
    """Hide one 2D or 3D sketch feature and prove it by re-reading Visible."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    if int(feature.Visible) != _SHOWN:
        return
    name = str(feature.Name)
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        name, "SKETCH", 0, 0, 0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"{label}: cannot select sketch {name!r} to hide it")
    model.BlankSketch()
    model.ClearSelection2(True)
    state = int(feature.Visible)
    if state != _HIDDEN:
        raise RuntimeError(f"{label}: sketch {name!r} still visible (state {state})")


@_telemetry.traced("appearance.assert_reference_geometry_hidden", label_param="label")
def assert_reference_geometry_hidden(
    adapter: Any, label: str, allowed: Mapping[str, str] | None = None
) -> None:
    """Fail when ``label``'s document is about to save construction geometry shown.

    A shown sketch, plane, axis, point or curve renders in the document's own
    images and in every assembly that places it (the drive-train isometric
    carried grey dots and a line from them).  ``allowed`` maps an entity name
    to the owner and reason it may stay shown for now
    (``reference_visibility_allowances``); an entry that matches nothing shown
    fails too, so the list can only shrink.
    """
    allowed = dict(allowed or {})
    shown = visible_reference_geometry(adapter.currentModel, label)
    names = {name for name, _kind in shown}
    for name, kind in shown:
        if name in allowed:
            _telemetry.warn(f"{label}: {kind} {name!r} saves shown ({allowed[name]})")
            _telemetry.event("visibility.allowed", label=label, entity=name, kind=kind)
    unexpected = [f"{kind} {name!r}" for name, kind in shown if name not in allowed]
    stale = sorted(set(allowed) - names)
    _telemetry.event(
        "visibility.checked",
        label=label,
        shown=len(shown),
        allowed=len(shown) - len(unexpected),
        stale=len(stale),
    )
    # One error names every problem, so a single seat run enumerates them all.
    problems = []
    if unexpected:
        problems.append(
            "construction geometry would save shown, and it renders in every "
            f"assembly that places it: {', '.join(unexpected)}; hide it "
            "(blank_sketch / blank_reference_geometry) before the save"
        )
    if stale:
        problems.append(
            f"visibility allowance {stale} matches nothing shown; delete it "
            "from reference_visibility_allowances"
        )
    if problems:
        raise RuntimeError(f"{label}: " + "; ".join(problems))
