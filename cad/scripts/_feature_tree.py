"""Feature-tree traversal and stable feature names.

Separate module so edits affect only recipes that use this scope.
"""

from __future__ import annotations

from typing import Any

import _telemetry
from _com import _bind, _com_invoke, _early_bound, _read_member


def feature_name_by_type(adapter: Any, type_name: str) -> str:
    """Return the name of the last feature whose GetTypeName2 matches.

    Recovers features whose creator call returns None on success (e.g. the
    raw-COM ``InsertHelix`` stopgap used until Phase 3 lands). Searches from
    the newest feature back over raw dispatches (see
    :func:`_iter_features_newest_first`), so finding the sketch or helix just
    made costs a step or two rather than a wrapped walk of the whole tree.
    """

    def matches(feat: Any) -> bool:
        try:
            return _com_invoke(feat, "IFeature", "GetTypeName2") == type_name
        except Exception:
            return False

    answered = False
    for feat in _iter_features_newest_first(adapter):
        answered = True
        if matches(feat):
            return str(_com_invoke(feat, "IFeature", "Name"))
    if answered:
        return ""
    found = ""
    for feat in _iter_features(adapter):
        if matches(feat):
            found = str(_com_invoke(feat, "IFeature", "Name"))
    return found


# ---------------------------------------------------------------------------
# Friendly names: tree (sketches/features) + dimensions, plus globals/equations.
#
# The build calls (create_sketch / create_extrusion / add_sketch_dimension)
# leave SolidWorks' OWN auto names -- ``Sketch1``, ``Boss-Extrude1``,
# ``D1@Sketch1`` -- so anyone who opens the part to fine-tune it must first
# reverse-engineer which "D7" is which. These helpers rename the tree and the
# driving dimensions to stable, human names AS the part is built, so a GUI edit
# references ``OuterWidth@OuterProfile``, never ``D3@Sketch1``. They also wrap
# the equation-manager surface (globals + driving equations) so those named
# dims can later be re-coupled to a handful of editable globals.
#
# All raw COM -- the adapter exposes no rename/enumerate surface. APIs (see the
# developing-solidworks bundle): IFeature.Name (get/set), IFeature.GetFirst/
# GetNextDisplayDimension, IDisplayDimension.GetDimension2, IDimension.Name/
# FullName/SystemValue. A name takes effect immediately for the API; the tree
# label only refreshes on the next rebuild (harmless mid-build).
# ---------------------------------------------------------------------------
def _iter_features(adapter: Any):
    """Yield every top-level feature of the active doc in tree order, as RAW
    dispatches (:func:`_com_invoke`): :func:`_bind` the one you keep.

    Raw, because the generated ``FirstFeature``/``GetNextFeature`` wrap every
    feature they step over (three extra round trips each, ~30 ms a feature on
    a farm seat). No in-place method flagging either: this walks the SHARED
    ``adapter.currentModel``, and ``_FlagAsMethod`` mutates that instance in
    place -- flipping ``FirstFeature`` to method dispatch would break the
    adapter's OWN bare property reads (its ``create_cut_extrude`` walks
    ``FirstFeature`` as a property to find the profile to cut)."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    feat = _com_invoke(model, "IModelDoc2", "FirstFeature")
    for _ in range(5000):
        if feat is None:
            return
        yield feat
        feat = _com_invoke(feat, "IFeature", "GetNextFeature")


def _iter_features_newest_first(adapter: Any):
    """Top-level features newest first, as RAW dispatches; stops early (and
    callers fall back to :func:`_iter_features`) if the seat will not answer.

    ``IModelDoc2.FeatureByPositionReverse(n)`` counts back from the end of the
    same model-definition order ``FirstFeature``/``GetNextFeature`` walk (the
    API reference says so for all three), one round trip per step. The
    features a build looks up are the ones it just made, so a search from the
    newest end stops after a step or two instead of walking the whole tree:
    the forward walk cost 0.9 s per rename at p50 and 2 s on harmonic_base."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    for position in range(5000):
        try:
            feat = _com_invoke(
                model, "IModelDoc2", "FeatureByPositionReverse", position
            )
        except Exception:
            return
        if feat is None:
            return
        yield feat


def _last_feature(adapter: Any) -> Any:
    """The most-recently created top-level feature: a just-exited sketch, or the
    boss/cut that just consumed it -- the LAST one the forward walk reaches.

    ``FeatureByPositionReverse(0)`` is that feature when it has no next
    feature (checked: one more round trip); otherwise the forward walk
    decides, and the disagreement is logged."""
    candidate = next(iter(_iter_features_newest_first(adapter)), None)
    if candidate is not None and (
        _com_invoke(candidate, "IFeature", "GetNextFeature") is None
    ):
        return _bind(candidate, "IFeature")
    last = None
    for feat in _iter_features(adapter):
        last = feat
    if last is None:
        raise RuntimeError("name_last_feature: the active document has no features")
    if candidate is not None:
        _telemetry.event("feature.reverse_order_mismatch", member="last")
    return _bind(last, "IFeature")


def _feature_by_name(adapter: Any, name: str) -> Any:
    """The top-level feature called ``name`` (feature names are unique, so the
    newest-first search and the forward walk can only find the same one)."""
    for walk in (_iter_features_newest_first, _iter_features):
        for feat in walk(adapter):
            if str(_com_invoke(feat, "IFeature", "Name")) == name:
                return _bind(feat, "IFeature")
    raise RuntimeError(f"feature {name!r} not found in the active document")


def name_last_feature(adapter: Any, name: str) -> str:
    """Rename the most-recent feature (a sketch right after ``exit_sketch``, or
    the boss/cut right after its creator) to ``name``. Returns ``name`` so it
    can be threaded straight into :func:`name_dimensions`."""
    feat = _last_feature(adapter)
    old = str(_read_member(feat, "Name"))
    feat.Name = name
    _telemetry.success(f"feature {old!r} -> {name!r}")
    return name
