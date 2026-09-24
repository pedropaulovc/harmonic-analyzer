"""Drawing dimensions owned by reference sketches the part saves HIDDEN.

A construction-only reference sketch (a centre, an envelope, a location
chord) renders in every assembly unless its part blanks it, so a part may
save such sketches hidden.  The targeted import in ``_drawing_common`` then
delivers none of their marked dimensions, whatever ``HiddenFeatureDims``
says (summing lever r17: BossAxialLocation, CylRefDia and
SummationArcCentreX/Z missing).  This module is the opt-in fix.  A drawing
whose part hides a dimension-carrying sketch imports its ``curate_view_dimensions``
and ``part_sketches_shown`` from here instead.  ``_drawing_common`` stays
untouched: every drawing's cache key depends on it, and this concerns a few.

The measured behaviour this code rests on (summing lever, SolidWorks 2026):

- Probe run 20260924T160303083Z-67cebdcd:
  - With the part hiding the sketch and no per-view override, the import
    delivers nothing.
  - After a per-view ``UnblankSketch`` (the sketch selected as
    ``<sketch>@<component>@<view>``), it delivers the sketch's dimensions.
  - After ``UnblankSketch`` on the drawing's open PART (Visible read back
    as shown, drawing rebuilt), an existing projected view still imports
    nothing.
- r21 (run 20260924T164017514Z-cbb1bb7f): blanking the sketch in the view
  again after the import HIDES what it delivered (``IAnnotation.Visible``
  3).  So a sketch stays shown in the view that dimensions it, and every
  sketch shown must own a dimension that survives there, or it would print
  undimensioned geometry.
- r21: a profile that a feature consumed also reads hidden in the part, yet
  it always imported.  Only childless sketches count.
- r22 and probe run 20260924T170431016Z-c0514e35: a DERIVED view (a detail)
  refuses the per-view override through its own qualifier and ignores its
  parent's.  It takes the sketch's visibility from the part when it is
  created.  A detail created while the part shows the sketch imports its
  dimensions, and they stay visible after the part blanks it again.  Hence
  ``part_sketches_shown`` around creating and dimensioning such a view.
- r18/r19 went silent: a raw dispatch answered ``getattr(doc,
  "FeatureByName", None)`` with None, and the check returned nothing.  Every
  read is therefore logged at INFO, and nothing defaults silently.
- r20: ``FeatureByName`` is IPartDoc's, not IModelDoc2's.
"""

from __future__ import annotations

import contextlib
import hashlib
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

import _drawing_common as _dc
import _telemetry
from _common import _early_bound, _read_member
from solidworks_mcp.adapters.pywin32_adapter import null_callout

# swVisibilityState_e
_VISIBILITY_HIDDEN = 1
_VISIBILITY_SHOWN = 2
# swAnnotationVisibilityState_e: HalfHidden, Hidden
_ANNOTATION_NOT_SHOWN = (2, 3)
_SKETCH_FEATURE_TYPES = ("ProfileFeature", "3DProfileFeature")
_DOC_PART = 1  # swDocumentTypes_e.swDocPART


def _model_hidden_sketches(
    view: Any, features: Sequence[str]
) -> tuple[list[str], dict[str, str]]:
    """Those of ``features`` that are childless sketches the view's part saves
    hidden, plus what was read for every requested feature (the INFO record).

    Only a part's own sketches are considered.  Anything else is reported
    and left to the import.
    """
    referenced = getattr(_early_bound(view, "IView"), "ReferencedDocument", None)
    if referenced is None:
        return [], {"*": "no referenced document"}
    doc_type = int(_early_bound(referenced, "IModelDoc2").GetType())
    if doc_type != _DOC_PART:
        return [], {"*": f"referenced document type {doc_type}, not a part"}
    model = _early_bound(referenced, "IPartDoc")
    hidden: list[str] = []
    report: dict[str, str] = {}
    for name in features:
        raw = model.FeatureByName(name)
        if raw is None:
            report[name] = "not found"
            continue
        feature = _early_bound(raw, "IFeature")
        type_name = str(feature.GetTypeName2())
        if type_name not in _SKETCH_FEATURE_TYPES:
            report[name] = type_name
            continue
        visible = int(_read_member(feature, "Visible"))
        children = len(feature.GetChildren() or ())
        report[name] = f"{type_name} Visible={visible} children={children}"
        if visible == _VISIBILITY_HIDDEN and not children:
            hidden.append(name)
    return hidden, report


def _show_view_sketches(
    draw: Any,
    sketches: Sequence[str],
    *,
    paths: Sequence[tuple[str, str]],
    label: str,
) -> None:
    """Show ``sketches`` in ONE drawing view (per-view override), for good.

    ``paths`` are ``_drawing_common._model_item_paths``' qualifiers; the first
    that selects wins.
    """
    for sketch in sketches:
        draw.ClearSelection2(True)
        if not any(
            draw.Extension.SelectByID2(
                f"{sketch}@{component}@{in_view}",
                "SKETCH",
                0.0,
                0.0,
                0.0,
                False,
                0,
                null_callout(),
                0,
            )
            for component, in_view in paths
        ):
            raise RuntimeError(f"{label}: cannot select sketch {sketch!r} to show it")
        draw.UnblankSketch()
        draw.ClearSelection2(True)


def _show_hidden_owners(
    adapter: Any, view: Any, features: Sequence[str], *, view_label: str
) -> list[str]:
    """Detect the view's part-hidden owner sketches and show them in the view."""
    name = _dc.view_name(adapter, view)
    hidden, report = _model_hidden_sketches(view, features)
    _telemetry.info(f"hidden-sketch check {name}: {report}; showing {hidden}")
    if not hidden:
        return []
    orientation = str(adapter._get_attr_or_call(view, "GetOrientationName") or "")
    if _dc.is_pictorial_orientation(orientation):
        raise RuntimeError(
            f"{view_label} ({name}): a pictorial view ({orientation}) must never "
            f"show a reference sketch, but it dimensions {hidden}"
        )
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate drawing view {name!r}")
    _show_view_sketches(
        adapter.currentModel,
        hidden,
        paths=_dc._model_item_paths(adapter, view),
        label=name,
    )
    return hidden


def _warn_undetected_owners(
    view: Any, owners: Sequence[str], *, view_label: str
) -> list[str]:
    """WARN naming the owners of missing dimensions that were NOT detected as
    part-hidden sketches: a detection miss must show in the log (r18)."""
    hidden, report = _model_hidden_sketches(view, owners)
    undetected = [owner for owner in owners if owner not in hidden]
    if undetected:
        _telemetry.warn(
            f"{view_label} view: missing dimensions' owners {undetected} were "
            f"not detected as part-hidden sketches: {report}"
        )
    return undetected


class _PartShown:
    """One ``part_sketches_shown`` block: the sketches it shows, those a
    curate inside it has dimensioned, and the kept annotations they own
    (re-read after the re-blank)."""

    def __init__(self, sketches: Sequence[str], label: str) -> None:
        self.sketches = tuple(sketches)
        self.label = label
        self.dimensioned: set[str] = set()
        self.annotations: list[tuple[str, str, Any]] = []


_PART_SHOWN: list[_PartShown] = []


def _owners_dimensioned(
    sketches: Iterable[str],
    present: set[str],
    dimensions_by_feature: Mapping[str, Iterable[str]],
) -> set[str]:
    return {
        sketch
        for sketch in sketches
        if set(dimensions_by_feature.get(sketch, ())) & present
    }


@_telemetry.traced("drawing.curate_dimensions", label_param="view_label")
def curate_view_dimensions(
    adapter: Any,
    view: Any,
    *,
    keep: dict[str, tuple[float, float]],
    view_label: str,
    dimensions_by_feature: Mapping[str, Iterable[str]],
) -> list[Any]:
    """``_drawing_common.curate_view_dimensions``, targeted form, for a view
    whose part may hide the sketches that own ``keep``.

    Each childless part-hidden owner sketch is shown in this view before the
    import and stays shown.  After curation:
    - every kept dimension must read ``IAnnotation.Visible`` 1;
    - every sketch shown here must own a dimension that survived;
    - inside ``part_sketches_shown``, every sketch that block showed and this
      view dimensions is recorded as dimensioned.
    """
    if not keep:
        return []
    features = _dc._features_owning(dimensions_by_feature, keep, view_label=view_label)
    hidden = _show_hidden_owners(adapter, view, features, view_label=view_label)
    named = _dc.insert_feature_dimensions(adapter, view, features)
    annotations = [annotation for _, annotation in named]
    extra = tuple(sorted({name for name, _ in named if name and name not in keep}))
    unnamed = sum(1 for name, _ in named if not name)
    if extra or unnamed:
        _telemetry.warn(
            f"{view_label} view's targeted import delivered unrequested "
            f"annotations from features={list(features)}: dimensions={list(extra)}, "
            f"unnamed={unnamed}; deleting them"
        )
        if unnamed:
            annotations = _dc.delete_unnamed_imports(adapter, annotations)
    curated = _dc.curate_dimensions(
        adapter, annotations, delete=extra, reposition=dict(keep)
    )
    present = {_dc.dimension_name(adapter, annotation) for annotation in curated}
    missing = sorted(set(keep) - present)
    if missing:
        _warn_undetected_owners(
            view,
            _dc._features_owning(dimensions_by_feature, missing, view_label=view_label),
            view_label=view_label,
        )
        raise RuntimeError(
            f"{view_label} view is missing model dimensions: {missing}; "
            f"available={sorted(present)} from features={list(features)}"
        )
    curated = _dc.curate_dimensions(adapter, curated, reposition=dict(keep))
    part_shown = [sketch for block in _PART_SHOWN for sketch in block.sketches]
    if hidden or part_shown:
        _assert_dimensions_visible(adapter, curated, hidden, view_label=view_label)
    undimensioned = sorted(
        set(hidden) - _owners_dimensioned(hidden, present, dimensions_by_feature)
    )
    if undimensioned:
        raise RuntimeError(
            f"{view_label} view shows {undimensioned} but keeps none of their "
            f"dimensions (kept {sorted(present)}): a shown reference sketch "
            "must dimension something in its view"
        )
    for block in _PART_SHOWN:
        block.dimensioned |= _owners_dimensioned(
            block.sketches, present, dimensions_by_feature
        )
        owned = {
            item
            for sketch in block.sketches
            for item in dimensions_by_feature.get(sketch, ())
        }
        block.annotations.extend(
            (view_label, item, annotation)
            for annotation in curated
            if (item := _dc.dimension_name(adapter, annotation)) in owned
        )
    return curated


def _assert_dimensions_visible(
    adapter: Any, curated: Sequence[Any], hidden: Sequence[str], *, view_label: str
) -> None:
    states = {
        _dc.dimension_name(adapter, annotation): int(
            _read_member(_early_bound(annotation, "IAnnotation"), "Visible")
        )
        for annotation in curated
    }
    _telemetry.event(
        "drawing.hidden_sketches_imported",
        view=view_label,
        sketches=", ".join(hidden),
        dimension_visibility=repr(states),
    )
    _telemetry.info(
        f"{view_label}: shown {list(hidden)} in the view; kept dimension "
        f"Visible states {states}"
    )
    dropped = sorted(item for item, v in states.items() if v in _ANNOTATION_NOT_SHOWN)
    if dropped:
        raise RuntimeError(f"{view_label}: kept dimensions read hidden: {dropped}")


def _set_part_sketches(
    adapter: Any, part_model: Any, sketches: Sequence[str], *, shown: bool
) -> None:
    """Show or blank ``sketches`` in the open PART, reading each one back."""
    model = _early_bound(part_model, "IModelDoc2")
    part = _early_bound(part_model, "IPartDoc")
    want = _VISIBILITY_SHOWN if shown else _VISIBILITY_HIDDEN
    for sketch in sketches:
        raw = part.FeatureByName(sketch)
        if raw is None:
            raise RuntimeError(f"part has no sketch {sketch!r} to toggle")
        feature = _early_bound(raw, "IFeature")
        model.ClearSelection2(True)
        if not feature.Select2(False, 0):
            raise RuntimeError(f"cannot select part sketch {sketch!r}")
        if shown:
            model.UnblankSketch()
        else:
            model.BlankSketch()
        model.ClearSelection2(True)
        visible = int(_read_member(feature, "Visible"))
        if visible != want:
            raise RuntimeError(
                f"part sketch {sketch!r} reads Visible={visible} after "
                f"{'UnblankSketch' if shown else 'BlankSketch'}, not {want}"
            )
    adapter.currentModel.EditRebuild3()


@contextlib.contextmanager
def part_sketches_shown(
    adapter: Any, part_model: Any, sketches: Sequence[str], *, label: str
) -> Iterator[None]:
    """Show part-hidden ``sketches`` in the drawing's open part, in memory, for
    the life of the block, then blank them again.

    Create a DERIVED view (a detail or section) that dimensions them inside
    the block, and curate it here with this module's
    ``curate_view_dimensions``.  The view takes the sketches as the part
    shows them at creation, and keeps both them and their dimensions after
    the re-blank.  Every sketch the block shows must be dimensioned by a
    curate inside it, or the block raises.  The drawing saves only itself
    (``SaveAs3`` options 0), and the part file's SHA-256 is checked before
    and after: a change raises, because the drawing must never save the part.
    """
    path = Path(str(_early_bound(part_model, "IModelDoc2").GetPathName()))
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    block = _PartShown(sketches, label)
    _set_part_sketches(adapter, part_model, sketches, shown=True)
    _telemetry.info(f"{label}: part sketches {list(sketches)} shown in memory")
    _PART_SHOWN.append(block)
    completed = False
    try:
        yield
        completed = True
    finally:
        _PART_SHOWN.remove(block)
        _set_part_sketches(adapter, part_model, sketches, shown=False)
        after = hashlib.sha256(path.read_bytes()).hexdigest()
        _telemetry.event(
            "drawing.part_sketches_reblanked",
            view=label,
            sketches=", ".join(sketches),
            part_sha256=after,
        )
        _telemetry.info(
            f"{label}: part sketches {list(sketches)} blanked again; "
            f"{path.name} sha256 {after[:12]} unchanged={after == before}"
        )
        if after != before:
            raise RuntimeError(
                f"{label}: {path} changed on disk while its sketches were shown "
                f"({before[:12]} -> {after[:12]}); the drawing must never save the part"
            )
    if not completed:
        return
    undimensioned = sorted(set(block.sketches) - block.dimensioned)
    if undimensioned:
        raise RuntimeError(
            f"{label}: part sketches {undimensioned} were shown but no view "
            "curated inside the block keeps a dimension they own"
        )
    # The curate's visibility gate ran while the part still showed the
    # sketches; the re-blank and rebuild come after it.  Measured harmless for
    # a detail (probe 20260924T170431016Z-c0514e35), but re-read here so any
    # other derived view that does lose them fails before the save (Codex).
    states = {
        f"{view}:{item}": int(
            _read_member(_early_bound(annotation, "IAnnotation"), "Visible")
        )
        for view, item, annotation in block.annotations
    }
    _telemetry.info(f"{label}: after the part re-blank, dimension Visible {states}")
    dropped = sorted(key for key, v in states.items() if v in _ANNOTATION_NOT_SHOWN)
    if dropped:
        raise RuntimeError(
            f"{label}: dimensions hidden by the part re-blank of "
            f"{list(block.sketches)}: {dropped}"
        )
