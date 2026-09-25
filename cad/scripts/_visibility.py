"""Saved-document display hygiene: hide construction geometry, and prove it."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
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
    """Every feature of a model and, recursively, its sub-features.

    The one tree walk the save check, the save backstop and the stock-fastener
    cleanup share.  It does not descend into an assembly's components (each
    part's own save proved its tree), counts what it visits in ``visited``
    for the span that owns the walk, and refuses a runaway traversal.
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


def _record_walk(walk: FeatureWalk) -> None:
    trace.get_current_span().set_attribute("features_visited", walk.visited)


def visible_reference_geometry(model: Any) -> list[tuple[str, str]]:
    """``(name, kind)`` of every shown sketch, plane, axis, point or curve."""
    shown: list[tuple[str, str]] = []
    seen: set[str] = set()
    walk = FeatureWalk(model)
    for feature in walk:
        kind = REFERENCE_FEATURE_KINDS.get(str(feature.GetTypeName2()))
        if kind is None:
            continue
        name = str(feature.Name)
        if name in seen or int(feature.Visible) != _SHOWN:
            continue
        seen.add(name)
        shown.append((name, kind))
    _record_walk(walk)
    return shown


# SelectByID2 types for the reference entities BlankRefGeom hides.  Sketches
# are not here: hiding one changes which dimensions its drawing imports
# (``_drawing_hidden_sketches``), so a shown sketch fails the check instead.
_REFERENCE_SELECT_TYPES = {
    "RefPlane": "PLANE",
    "RefAxis": "AXIS",
    "RefPoint": "DATUMPOINT",
    "Helix": "REFERENCECURVES",
    "CompositeCurve": "REFERENCECURVES",
}


@_telemetry.traced("appearance.hide_reference_geometry", label_param="label")
def hide_reference_geometry(adapter: Any, label: str) -> list[str]:
    """Hide every shown plane, axis, point and reference curve before a save.

    Parts and assemblies create them for sketch placement and as named mate
    targets, and a shown one prints its outline and label in every render
    (crank-arm's HandleSeat, Plane2, Axis1 and Axis2).  Blanked entities stay
    selectable by name, so mates and later features still find them.  Returns
    the names it hid.
    """
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = adapter.currentModel
    walk = FeatureWalk(model)
    shown = [
        (feature, str(feature.Name), _REFERENCE_SELECT_TYPES[kind])
        for feature in walk
        if (kind := str(feature.GetTypeName2())) in _REFERENCE_SELECT_TYPES
        and int(feature.Visible) == _SHOWN
    ]
    _record_walk(walk)
    # The creating helpers hide what they make, so this backstop should find
    # nothing; the count names what still reaches it and should trend to 0.
    trace.get_current_span().set_attribute("refgeom.hidden_at_save", len(shown))
    _telemetry.event(
        "refgeom.hidden_at_save",
        label=label,
        count=len(shown),
        names=",".join(name for _feature, name, _type in shown),
    )
    if not shown:
        return []
    model.ClearSelection2(True)
    for index, (_feature, name, select_type) in enumerate(shown):
        if not model.Extension.SelectByID2(
            name, select_type, 0, 0, 0, index > 0, 0, null_callout(), 0
        ):
            raise RuntimeError(
                f"{label}: cannot select {select_type} {name!r} to hide it"
            )
    model.BlankRefGeom()
    model.ClearSelection2(True)
    names = [name for _feature, name, _type in shown]
    still = [name for feature, name, _type in shown if int(feature.Visible) == _SHOWN]
    if still:
        raise RuntimeError(f"{label}: BlankRefGeom left {still} shown")
    _telemetry.info(
        f"{label}: refgeom.hidden_at_save={len(names)} ({', '.join(names)})"
    )
    return names


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
    shown = visible_reference_geometry(adapter.currentModel)
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
