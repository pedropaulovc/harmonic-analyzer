"""Model-dimension display precision and named-dimension resolution.

Separate to limit cache blast radius. Tolerance and prefix helpers import the
shared ``_named_dimensions`` / ``_named_dimension`` resolution owned here.
"""

from __future__ import annotations

import time
from typing import Any

import _telemetry
from _com import _bind, _com_invoke, _early_bound
from _dimensions import _dim_owner_feature, _feature_display_dimensions
from _drawing_marks import _feature_tree
from _feature_tree import _feature_by_name, _iter_features


def _named_dimensions(
    adapter: Any,
    feature_name: str,
    dimension_names: set[str],
    *,
    feature: Any = None,
) -> dict[str, tuple[Any, Any]]:
    """Resolve each named display/source dimension on ``feature_name`` in ONE
    walk of its subfeature tree, bound to ``IDisplayDimension``/``IDimension``.

    Walks the same subfeature tree as ``mark_dimensions_for_drawing``: a Hole
    Wizard placement dimension belongs to a ``ProfileFeature`` subfeature, so a
    search that stopped at the top level could not author the decimal places or
    the tolerance of a dimension the mark path happily marks -- the recipe names
    the wizard feature, and the dimension is one level down.  Every candidate is
    matched against the name of the feature that actually owns it, and a name
    that resolves twice inside the tree is still rejected rather than guessed.
    ``feature`` is ``feature_name``'s dispatch when the caller already has it.
    """
    if feature is None:
        feature = _feature_by_name(adapter, feature_name)
    found: dict[str, list[tuple[Any, Any]]] = {name: [] for name in dimension_names}
    for current in _feature_tree(feature):
        current_name = str(_com_invoke(current, "IFeature", "Name"))
        for display in _feature_display_dimensions(current):
            dimension = _com_invoke(display, "IDisplayDimension", "GetDimension2", 0)
            name = str(_com_invoke(dimension, "IDimension", "Name"))
            if name in found and _dim_owner_feature(dimension) == current_name:
                found[name].append((display, dimension))
    resolved: dict[str, tuple[Any, Any]] = {}
    for name, matches in found.items():
        if len(matches) != 1:
            raise RuntimeError(
                f"{name}@{feature_name}: expected exactly one dimension, "
                f"found {len(matches)}"
            )
        display, dimension = matches[0]
        resolved[name] = (
            _bind(display, "IDisplayDimension"),
            _bind(dimension, "IDimension"),
        )
    return resolved


def _named_dimension(
    adapter: Any, feature_name: str, dimension_name: str
) -> tuple[Any, Any]:
    """Resolve exactly one named display/source dimension on ``feature_name``
    (see :func:`_named_dimensions`)."""
    return _named_dimensions(adapter, feature_name, {dimension_name})[dimension_name]


@_telemetry.traced("dim.display_precision", label_param="dimension_name")
def set_dimension_display_precision(
    adapter: Any,
    feature_name: str,
    dimension_name: str,
    decimals: int,
    *,
    display: Any = None,
) -> None:
    """Author the decimal places of one model dimension ON THE PART.

    Decimal places carry the tolerance (drawing-simplicity-policy.md `How the repository implements the guidelines`), so
    they are a property of the model dimension, not of the sheet: the part
    build applies ``<part>_spec.DRAWING_PRECISION`` here, the .SLDPRT stores
    the per-dimension override, and the drawing that imports the dimension
    reads the same places back instead of rewriting them at render time.
    Only the primary places move; dual and tolerance places are left alone
    (``_set_tolerance_precision`` owns the tolerance places).

    ``display`` is the dimension already resolved by
    :func:`apply_drawing_precision`'s one walk per feature; without it the
    dimension is looked up here and ``lookup_ms`` times that walk.
    """
    if decimals < 0 or decimals > 8:
        raise ValueError(f"display precision must be 0..8 decimals, got {decimals!r}")
    # Thousands of calls a week: time the COM steps as attributes of this span
    # rather than as child spans each.
    started = time.perf_counter()
    timings: dict[str, float] = {}
    if display is None:
        display, _dimension = _named_dimension(adapter, feature_name, dimension_name)
        timings["lookup_ms"] = round((time.perf_counter() - started) * 1000, 1)
    looked_up = time.perf_counter()
    display = _early_bound(display, "IDisplayDimension")
    bound = time.perf_counter()
    do_not_change = -1  # swDimensionPrecisionSettings_e
    display.SetPrecision3(decimals, do_not_change, do_not_change, do_not_change)
    set_at = time.perf_counter()
    applied = int(display.GetPrimaryPrecision2())
    _telemetry.annotate(
        **timings,
        bind_ms=round((bound - looked_up) * 1000, 1),
        set_ms=round((set_at - bound) * 1000, 1),
        readback_ms=round((time.perf_counter() - set_at) * 1000, 1),
    )
    if applied != decimals:
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: display precision did not persist: "
            f"requested {decimals} decimals, dimension reports {applied}"
        )
    _telemetry.success(
        f"precision {dimension_name}@{feature_name}: {decimals} decimals"
    )


def apply_drawing_precision(adapter: Any, precision: dict[str, dict[str, int]]) -> None:
    """Apply a spec's ``DRAWING_PRECISION`` -- ``{feature: {dimension: decimals}}``.

    One forward pass over the top-level features finds every named feature
    (``dim.precision_features``), then each feature's dimensions are resolved
    in one walk of its own tree (``dim.precision_lookup``): not one
    newest-first search per feature, nor one walk per dimension."""
    wanted = set(precision)
    features: dict[str, Any] = {}
    with _telemetry.span("dim.precision_features", features=len(wanted)) as span:
        visited = 0
        for feature in _iter_features(adapter):
            visited += 1
            name = str(_com_invoke(feature, "IFeature", "Name"))
            if name in wanted:
                features[name] = feature
                if len(features) == len(wanted):
                    break
        span.set_attribute("features_visited", visited)
    for feature_name, dimensions in precision.items():
        with _telemetry.span(
            "dim.precision_lookup", label=feature_name, dimensions=len(dimensions)
        ):
            resolved = _named_dimensions(
                adapter,
                feature_name,
                set(dimensions),
                feature=features.get(feature_name),
            )
        for dimension_name, decimals in dimensions.items():
            set_dimension_display_precision(
                adapter,
                feature_name,
                dimension_name,
                decimals,
                display=resolved[dimension_name][0],
            )
