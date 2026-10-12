"""Drawing model-item import and dimension curation.

Recipes carrying model dimensions share feature import and curation here, while
hand-authored edge dimensions remain independent.
"""

from __future__ import annotations

import math
import time
from typing import Any, Iterable, Literal, Mapping, Sequence

from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    curate_dimensions,
    dimension_name,
    view_name,
)

from _com import _early_bound
from _drawing_common import rebuild_drawing
import _telemetry


# swInsertAnnotation_e flags used by the curated model-item import. Hole Wizard
# placement dimensions live on an absorbed sketch and require their dedicated
# flag; MarkedForDrawing alone does not make them importable.
_INSERT_DIMS_MARKED = 0x8000


_INSERT_HOLE_WIZARD_LOCATION_DIMS = 0x20000


@_telemetry.traced("drawing.cosmetic_threads")
def import_cosmetic_threads(adapter: Any, view: Any) -> tuple[int, int]:
    """Import a view's cosmetic threads and count seed plus pattern instances.

    ``IDrawingDoc.InsertModelAnnotations3`` with ``swInsertCThreads`` makes this
    independent of each seat's drawing annotation preferences.
    ``GetCThreadCount`` counts seed objects, while each
    ``ICThread.GetPatternedTransformsCount`` supplies its repeated instances.
    """
    view = _sw_type_info.early_bound_or_flag(
        view, "IView", "GetCThreadCount", "GetFirstCThread"
    )
    draw = adapter.currentModel
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    name = view_name(adapter, view)
    ddoc.ActivateView(name)
    draw.ClearSelection2(True)
    selected = draw.Extension.SelectByID2(
        name, "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    )
    if not selected:
        raise RuntimeError(f"failed to select drawing view {name!r}")
    adapter._attempt(
        lambda: ddoc.InsertModelAnnotations3(
            0,  # swImportModelItemsFromEntireModel
            0x1,  # swInsertCThreads
            False,
            True,
            True,
            False,
        )
    )
    adapter._attempt(lambda: adapter.currentModel.EditRebuild3())
    seed_count = int(adapter._get_attr_or_call(view, "GetCThreadCount") or 0)
    instance_count = 0
    thread = adapter._get_attr_or_call(view, "GetFirstCThread")
    visited = 0
    while thread is not None:
        visited += 1
        if visited > 10_000:
            raise RuntimeError("cosmetic-thread traversal exceeded 10,000 entries")
        thread = _sw_type_info.early_bound_or_flag(
            thread, "ICThread", "GetPatternedTransformsCount", "GetNext"
        )
        patterns = int(
            adapter._get_attr_or_call(thread, "GetPatternedTransformsCount") or 0
        )
        instance_count += 1 + patterns
        thread = adapter._get_attr_or_call(thread, "GetNext")
    if visited != seed_count:
        raise RuntimeError(
            f"cosmetic-thread count mismatch: API={seed_count}, traversed={visited}"
        )
    return seed_count, instance_count


@_telemetry.traced("drawing.marked_dimensions")
def insert_marked_dimensions(adapter: Any, view: Any) -> list[Any]:
    """Import the source part's marked-for-drawing dimensions into ``view``.

    Parts mark exactly their manufacturing dimensions
    (``_drawing_marks.mark_dimensions_for_drawing``), so the import mask is
    ``swInsertDimensionsMarkedForDrawing`` only.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    name = view_name(adapter, view)
    ddoc.ActivateView(name)
    draw.ClearSelection2(True)
    selected = draw.Extension.SelectByID2(
        name, "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    )
    if not selected:
        raise RuntimeError(f"failed to select drawing view {name!r}")
    result = adapter._attempt(
        lambda: ddoc.InsertModelAnnotations3(
            0,  # swImportModelItemsFromEntireModel
            _INSERT_DIMS_MARKED | _INSERT_HOLE_WIZARD_LOCATION_DIMS,
            False,
            True,
            True,
            False,
        )
    )
    if not result or isinstance(result, str):
        return []
    annotations = [
        _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetSpecificAnnotation"
        )
        for annotation in result
    ]
    names = sorted(
        name
        for name in (dimension_name(adapter, annotation) for annotation in annotations)
        if name
    )
    _telemetry.info(
        f"model-item import {name}: annotations={len(annotations)}, dimensions={names}"
    )
    return annotations


def delete_unnamed_imports(adapter: Any, annotations: list[Any]) -> list[Any]:
    """Remove automatic cosmetic-thread callouts from model annotation import."""
    draw = adapter.currentModel
    survivors: list[Any] = []
    for annotation in annotations:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "Select2"
        )
        if dimension_name(adapter, annotation):
            survivors.append(annotation)
            continue
        draw.ClearSelection2(True)
        if not annotation.Select2(False, 0):
            raise RuntimeError("failed to select an automatic model annotation")
        draw.EditDelete()
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="delete_unnamed_imports")
    return survivors


def _feature_by_dimension_name(
    dimensions_by_feature: Mapping[str, Iterable[str]],
) -> dict[str, str]:
    """Invert a part spec's ``DRAWING_DIMENSIONS`` to ``{dimension: feature}``.

    ``_dimensions.name_dimensions`` names a dimension per OWNING feature, so the
    inverse is total and unambiguous by construction.  A name claimed by two
    features is a spec bug, not a runtime condition — it would make the
    targeted import silently depend on feature order — so it raises here.
    """
    owner: dict[str, str] = {}
    for feature, names in dimensions_by_feature.items():
        for name in names:
            previous = owner.setdefault(name, feature)
            if previous != feature:
                raise ValueError(
                    f"dimension {name!r} is claimed by features {previous!r} and "
                    f"{feature!r}; parametric names are feature-unique"
                )
    return owner


def _features_owning(
    dimensions_by_feature: Mapping[str, Iterable[str]],
    keep: Iterable[str],
    *,
    view_label: str,
) -> tuple[str, ...]:
    """Name, sorted, the features whose marked dimensions cover ``keep``."""
    owner = _feature_by_dimension_name(dimensions_by_feature)
    unknown = sorted(name for name in keep if name not in owner)
    if unknown:
        raise RuntimeError(
            f"{view_label} view keeps dimensions no feature declares: {unknown}; "
            f"declared={sorted(owner)}"
        )
    return tuple(sorted({owner[name] for name in keep}))


def _drawing_component_name(adapter: Any, view: Any) -> str:
    """Name of the model instance a drawing view shows, e.g. ``"fr-tube-frame-2"``.

    ``SelectByID2`` wants it as the middle qualifier of a model item's name, and
    it is NOT derivable from the part's file name: SolidWorks numbers one
    instance per view (``fr-tube-frame-1`` in the first view, ``-2`` in the
    second), so it is read back per view from
    ``IView::RootDrawingComponent2`` — ``InChildContext=False`` for this view's
    own root component — rather than guessed.
    """
    root = _early_bound(view, "IView").RootDrawingComponent2(False)
    name = _early_bound(root, "IDrawingComponent").Name if root else None
    if not isinstance(name, str) or not name:
        raise RuntimeError(
            f"drawing view {view_name(adapter, view)!r} has no root drawing "
            f"component to qualify model feature names with: {name!r}"
        )
    return name


def _model_item_paths(adapter: Any, view: Any) -> tuple[tuple[str, str], ...]:
    """The ``@component@view`` qualifiers a model item of ``view`` answers to.

    A projected view answers to its own name.  A DERIVED view does not.  On
    top_frame's Section View A-A, every combination of
    ``"CapRecessProfile@fr-top-frame-7@Section View A-A"`` with SKETCH,
    BODYFEATURE, "" and SOLIDBODY refuses -- for instance suffixes 1..20
    (``RootDrawingComponent2(True)`` reads 'top-frame-16', which refuses too)
    and for the sheet-qualified view name -- while the section itself selects
    fine as a DRAWINGVIEW and the same two features resolve through its BASE
    view, whose component name it happens to share.

    Naming a feature through the base view does NOT import into the base view:
    ``InsertModelAnnotations3`` follows the SELECTED drawing view, so with the
    section selected the section is what gains the dimensions (measured: A-A's
    census gained a second CapRecessDepth and CapRecessDia, the base view
    gained none).  The base-view chain is therefore walked as a fallback, each
    name paired with the component name THAT view reports (SolidWorks numbers
    one instance per view), and the first qualifier that resolves wins.
    """
    paths = [(_drawing_component_name(adapter, view), view_name(adapter, view))]
    seen = {paths[0][1]}
    base = _early_bound(view, "IView").GetBaseView()
    while base is not None:
        base = _early_bound(base, "IView")
        name = view_name(adapter, base)
        if name in seen:
            break
        seen.add(name)
        paths.append((_drawing_component_name(adapter, base), name))
        base = base.GetBaseView()
    return tuple(paths)


def _select_model_feature(
    adapter: Any, feature: str, *, paths: Sequence[tuple[str, str]]
) -> str:
    """Append one model feature of a drawing view to the selection list.

    A feature is addressed from the drawing as
    ``"<feature>@<drawing component>@<view>"`` — the form
    ``IModelDocExtension::SelectByID2`` documents for model items seen through a
    view (``"Sketch1@model-7@Drawing View1"``, from the "Reset Visibility of
    Sketches in Drawing View" example).  The Type filter must name the real
    kind: a driving dimension's owner is usually a profile ``"SKETCH"`` but can
    be a ``"BODYFEATURE"`` (an extrude, a chamfer, a fillet), and an empty Type
    resolves NEITHER here, so both are tried and the winner is returned.

    ``paths`` are :func:`_model_item_paths`' qualifiers, the view's own first
    and then its base views' -- a derived view answers to none of its own.
    """
    draw = adapter.currentModel
    for component, in_view in paths:
        for type_name in ("SKETCH", "BODYFEATURE"):
            if draw.Extension.SelectByID2(
                f"{feature}@{component}@{in_view}",
                type_name,
                0.0,
                0.0,
                0.0,
                True,  # append: the view itself is already selected
                0,
                null_callout(),
                0,
            ):
                return f"{type_name} via {in_view}"
    raise RuntimeError(
        f"failed to select model feature {feature!r} as a SKETCH or a "
        "BODYFEATURE through any of "
        f"{[f'{feature}@{component}@{in_view}' for component, in_view in paths]}"
    )


@_telemetry.traced("drawing.targeted_model_items")
def insert_feature_dimensions(
    adapter: Any, view: Any, features: Sequence[str]
) -> list[tuple[str, Any]]:
    """Import only ``features``' marked dimensions into ``view``.

    ``InsertModelAnnotations3`` imports for the current SELECTION, so selecting
    the view plus the owning features and passing ``swImportModelItemsSource_e``
    ``swImportModelItemsFromSelectedFeature`` (1) rather than
    ``swImportModelItemsFromEntireModel`` (0) delivers exactly the recipe's ink
    — no whole-model marked set to select and ``EditDelete`` afterwards.  The
    mask still applies: the selected-feature import honours
    ``swInsertDimensionsMarkedForDrawing``.

    The selection list is the whole contract, and it is asymmetric: the view
    goes in FIRST (the method "inserts model annotations into this drawing
    document's currently selected drawing view") and every feature is APPENDED
    to it.  With the features alone selected the call silently imports nothing —
    it returns an empty array and no annotation reaches any view — and Option 2
    (``swImportModelItemsFromSelectedComponent``, which the pre-2008-SP3 help
    mislabelled "selected feature") imports nothing either way.  All of that is
    measured on tube-frame by ``diagnostics/probe_targeted_model_items.py``.
    Every feature rides in ONE selection list and ONE import call.

    Returns ``(parametric name, annotation)`` pairs — the import already reads
    every name to log what arrived, so handing them back spares the caller a
    second ``IDimension::Name`` walk over the same annotations.  An annotation
    that is not a model dimension pairs with ``""``.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate drawing view {name!r}")
    draw.ClearSelection2(True)
    if not draw.Extension.SelectByID2(
        name, "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"failed to select drawing view {name!r}")
    paths = _model_item_paths(adapter, view)
    types = [
        _select_model_feature(adapter, feature, paths=paths) for feature in features
    ]
    result = adapter._attempt(
        lambda: ddoc.InsertModelAnnotations3(
            1,  # swImportModelItemsFromSelectedFeature
            _INSERT_DIMS_MARKED | _INSERT_HOLE_WIZARD_LOCATION_DIMS,
            False,
            True,
            True,
            False,
        )
    )
    draw.ClearSelection2(True)
    if not result or isinstance(result, str):
        return []
    named = [
        (dimension_name(adapter, annotation), annotation)
        for annotation in (
            _sw_type_info.early_bound_or_flag(
                annotation, "IAnnotation", "GetSpecificAnnotation"
            )
            for annotation in result
        )
    ]
    _telemetry.info(
        f"targeted model-item import {name}: "
        f"features={[f'{f}[{t}]' for f, t in zip(features, types, strict=True)]}, "
        f"annotations={len(named)}, "
        f"dimensions={sorted(item for item, _ in named if item)}"
    )
    return named


def _curate_entire_model_import(
    adapter: Any,
    view: Any,
    *,
    keep: dict[str, tuple[float, float]],
    view_label: str,
) -> list[Any]:
    """Fallback: import the whole model's marked set, then delete the rest."""
    annotations = delete_unnamed_imports(
        adapter, insert_marked_dimensions(adapter, view)
    )
    names = {dimension_name(adapter, annotation) for annotation in annotations}
    delete = tuple(sorted(name for name in names if name and name not in keep))
    curated = curate_dimensions(
        adapter, annotations, delete=delete, reposition=dict(keep)
    )
    present = {dimension_name(adapter, annotation) for annotation in curated}
    missing = sorted(set(keep) - present)
    if missing:
        raise RuntimeError(
            f"{view_label} view is missing model dimensions: {missing}; "
            f"available={sorted(present)}"
        )
    return curate_dimensions(adapter, curated, reposition=dict(keep))


# How far a kept dimension may read back from its requested sheet point before
# it is placed again.  SetPosition + EditRebuild3 leaves an unmoved survivor
# exactly on its point (all 17 curate passes on the step-snapshot leaves read
# back equal at 1e-6 m); the two real shifts were 6.97 mm and 0.63 mm.
_REPOSITION_DRIFT_TOLERANCE_M = 1e-5


def _reposition_rerun_reason(
    adapter: Any,
    curated: Sequence[Any],
    names: Sequence[str],
    keep: Mapping[str, tuple[float, float]],
    *,
    deleted: bool,
) -> Literal["deleted", "drifted", "none"]:
    """Whether ``curate_view_dimensions`` must place its kept dimensions again.

    A pass that deleted can shift a survivor it already placed (top_frame
    ``Width`` 6.97 mm), so it is always followed by a second placement.  After
    a reposition-only pass one ``GetPosition`` per kept dimension (~3 ms each,
    against ~0.65 s for the pass) decides instead: any kept dimension off its
    requested point by more than ``_REPOSITION_DRIFT_TOLERANCE_M`` is placed
    again with the rest.  Records ``reposition_rerun_reason`` (and, for the
    readback, its count/cost/drift) on the current span.
    """
    if deleted:
        _telemetry.annotate(reposition_rerun_reason="deleted")
        return "deleted"
    started = time.perf_counter()
    drifted: list[str] = []
    read = 0
    for annotation, name in zip(curated, names):
        if name not in keep:
            continue
        read += 1
        position = adapter._attempt(
            lambda a=annotation: adapter._get_attr_or_call(a, "GetPosition")
        )
        if (
            not position
            or math.dist((float(position[0]), float(position[1])), keep[name])
            > _REPOSITION_DRIFT_TOLERANCE_M
        ):
            drifted.append(name)
    reason: Literal["drifted", "none"] = "drifted" if drifted else "none"
    _telemetry.annotate(
        reposition_rerun_reason=reason,
        reposition_readback_n=read,
        reposition_readback_s=round(time.perf_counter() - started, 4),
        reposition_drifted_n=len(drifted),
    )
    if drifted:
        _telemetry.info(
            f"kept dimensions {sorted(drifted)} read back off their requested "
            "position after the rebuild; placing the view's dimensions again"
        )
    return reason


@_telemetry.traced("drawing.curate_dimensions", label_param="view_label")
def curate_view_dimensions(
    adapter: Any,
    view: Any,
    *,
    keep: dict[str, tuple[float, float]],
    view_label: str,
    dimensions_by_feature: Mapping[str, Iterable[str]] | None = None,
) -> list[Any]:
    """Import a view's marked model dimensions and keep exactly ``keep``.

    ``keep`` maps each surviving dimension's parametric name to its sheet
    position (meters).  A missing expected dimension fails loud — the print
    must carry every manufacturing dimension the recipe promises.

    ``dimensions_by_feature`` is the source part spec's ``DRAWING_DIMENSIONS``
    (``{feature: {dimension names}}``).  Given it, only the features that own
    ``keep`` are selected and imported, so nothing arrives that must be deleted
    again and an empty ``keep`` costs no COM call at all.  Without it the view
    falls back to the entire-model import plus deletion sweep: the same ink for
    many times the round trips, so the fallback WARNS and names the view, which
    keeps every recipe still on it visible in the build log.

    The kept dimensions are positioned again when the first pass deleted some
    (a delete can shift a survivor the same pass already placed: top_frame
    ``Width`` 6.97 mm, ``RibWidth`` 0.63 mm) or when one reads back off its
    requested point after that pass's rebuild.  Otherwise the second pass is
    skipped: after a reposition-only pass it moved nothing and changed no PDF
    pixel on any of 9 views (diag branch pedro/drawing-step-snapshots-diag,
    a0e136c66, leaves cone_pivot_post/pinion_arbor/top_frame) and cost ~0.65 s
    each (one ``EditRebuild3`` plus a name read and ``SetPosition`` per
    dimension); the readback costs one ``GetPosition`` per kept dimension.
    """
    if dimensions_by_feature is None:
        _telemetry.warn(
            f"{view_label} view imports the ENTIRE model's marked dimensions and "
            "deletes the rest; pass dimensions_by_feature=<part>_spec."
            "DRAWING_DIMENSIONS to import only the features it dimensions"
        )
        return _curate_entire_model_import(
            adapter, view, keep=keep, view_label=view_label
        )
    if not keep:
        return []
    features = _features_owning(dimensions_by_feature, keep, view_label=view_label)
    named = insert_feature_dimensions(adapter, view, features)
    annotations = [annotation for _, annotation in named]
    extra = tuple(sorted({name for name, _ in named if name and name not in keep}))
    unnamed = sum(1 for name, _ in named if not name)
    if extra or unnamed:
        # A feature that owns a kept dimension can also own ink the recipe does
        # not place (a cosmetic-thread callout has no parametric name at all).
        # Deleting it keeps the sheet to the recipe; warning makes the surprise
        # visible instead of silently paid for on every build.
        _telemetry.warn(
            f"{view_label} view's targeted import delivered unrequested "
            f"annotations from features={list(features)}: dimensions={list(extra)}, "
            f"unnamed={unnamed}; deleting them"
        )
        if unnamed:
            annotations = delete_unnamed_imports(adapter, annotations)
    curated = curate_dimensions(
        adapter, annotations, delete=extra, reposition=dict(keep)
    )
    names = [dimension_name(adapter, annotation) for annotation in curated]
    missing = sorted(set(keep) - set(names))
    if missing:
        raise RuntimeError(
            f"{view_label} view is missing model dimensions: {missing}; "
            f"available={sorted(set(names))} from features={list(features)}"
        )
    if (
        _reposition_rerun_reason(adapter, curated, names, keep, deleted=bool(extra))
        == "none"
    ):
        return curated
    return curate_dimensions(adapter, curated, reposition=dict(keep))
