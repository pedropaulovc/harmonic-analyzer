"""Part-side drawing dimension marks and manufacturing properties.

Used by parts that ship a manufacturing drawing (see ``_drawing_registry``)
and by ``_drawing_precision`` for the shared ``_feature_tree`` traversal.
Deliberately separate from ``_part_properties`` so
adding a drawing to one part never shifts the recipe digest of the ~100 parts
that carry no drawing.

Separate from dimension precision, tolerances, prefix text and insertion helpers
so edits to those concerns do not widen the cache blast radius to every part
that carries drawing marks or properties.

The drawing recipe (``draw_<part>.py``) later imports exactly the dimensions a
part marks here (``swInsertDimensionsMarkedForDrawing``), so the SLDPRT stays
the single source of every manufacturing dimension.
"""

from __future__ import annotations

from typing import Any, Mapping

import _config
import _telemetry
from _com import _com_invoke, _com_put, _early_bound
from _custom_properties import apply_custom_properties
from _dimensions import _feature_display_dimensions
from _feature_tree import _feature_by_name


def _feature_tree(feature: Any) -> Any:
    """Yield ``feature`` and every subfeature, depth-first, as RAW dispatches
    (``_com._com_invoke``: one round trip a step, no wrapper per feature).

    Hole Wizard placement dimensions live on ``ProfileFeature`` subfeatures,
    so both the mark AND the clear path must walk the same tree — a clear
    that stops at top level leaves stale marks on child-feature dimensions.
    """
    stack = [feature]
    while stack:
        current = stack.pop()
        yield current
        child = _com_invoke(current, "IFeature", "GetFirstSubFeature")
        children: list[Any] = []
        for _ in range(1000):
            if child is None:
                break
            children.append(child)
            child = _com_invoke(child, "IFeature", "GetNextSubFeature")
        stack.extend(reversed(children))


def mark_dimensions_for_drawing(
    adapter: Any, feature_name: str, dimension_names: set[str]
) -> None:
    """Mark only this part's explicit manufacturing dimensions for insertion.

    Hole Wizard placement dimensions belong to a ``ProfileFeature`` subfeature,
    not to the top-level ``HoleWzd`` feature named by the part recipe.  Walk the
    requested feature and its subfeature tree so those authored placement
    dimensions remain usable as native drawing dimensions.  A requested name
    must resolve exactly once within that tree; duplicate matches are rejected
    instead of silently marking an arbitrary dimension.
    """
    feature = _feature_by_name(adapter, feature_name)
    matches: dict[str, tuple[Any, str]] = {}
    for current in _feature_tree(feature):
        current_name = str(_com_invoke(current, "IFeature", "Name"))
        for display in _feature_display_dimensions(current):
            dimension = _com_invoke(display, "IDisplayDimension", "GetDimension2", 0)
            name = str(_com_invoke(dimension, "IDimension", "Name"))
            if name not in dimension_names:
                continue
            full_name = str(_com_invoke(dimension, "IDimension", "FullName"))
            owner = full_name.split("@")[1] if "@" in full_name else ""
            if owner != current_name:
                continue
            previous = matches.get(name)
            if previous is not None and previous[1] != full_name:
                raise RuntimeError(
                    f"{feature_name}: drawing dimension {name!r} is ambiguous: "
                    f"{previous[1]!r}, {full_name!r}"
                )
            matches[name] = (display, full_name)

    missing = dimension_names - matches.keys()
    if missing:
        raise RuntimeError(
            f"{feature_name}: dimensions not marked for drawing: {sorted(missing)}"
        )
    for name, (display, full_name) in matches.items():
        _com_put(display, "IDisplayDimension", "MarkedForDrawing", True)
        if not bool(_com_invoke(display, "IDisplayDimension", "MarkedForDrawing")):
            raise RuntimeError(f"{full_name}: mark-for-drawing failed")
    _telemetry.success(
        f"marked for drawing {feature_name}: {', '.join(sorted(matches))}"
    )


def clear_dimensions_for_drawing(adapter: Any) -> None:
    """Unmark every model dimension, top-level features and subfeatures alike.

    ``IFeatureManager.GetFeatures(False)`` returns every top-level feature
    and every child feature in one call (the API reference: "the top-level
    features and all child features"), the set the recursive tree walk
    reached with two or three round trips per feature; order is irrelevant
    to clearing.  Each display dimension is then read and, if marked, put
    raw."""
    with _telemetry.span("dim.clear_drawing_marks") as span:
        model = _early_bound(adapter.currentModel, "IModelDoc2")
        manager = _com_invoke(model, "IModelDoc2", "FeatureManager")
        features = _com_invoke(manager, "IFeatureManager", "GetFeatures", False)
        displays = cleared = 0
        for feature in features or ():
            for display in _feature_display_dimensions(feature):
                displays += 1
                if bool(_com_invoke(display, "IDisplayDimension", "MarkedForDrawing")):
                    _com_put(display, "IDisplayDimension", "MarkedForDrawing", False)
                    cleared += 1
        span.set_attribute("features_visited", len(features or ()))
        span.set_attribute("displays_visited", displays)
        span.set_attribute("cleared", cleared)
    _telemetry.success(f"cleared {cleared} model-dimension drawing marks")


# Drafter shown in the title block DRAWN field. Checked/approval are left blank
# on the sheet (a machinist signs them on the printed copy). See issue #249 for
# the title-block property-provenance consolidation this path is part of.
DRAWN_BY = "PPVC"


def apply_drawing_properties(
    adapter: Any, part_name: str, extra: Mapping[str, str] | None = None
) -> None:
    """Stamp the make-critical custom properties a drawing title block reads.

    ``material_specification`` / ``finish`` / ``quantity`` come from the part's
    config registry row; the production-control fields (``Drawn By``,
    ``Revision Description``) are stamped here too so the title block's DRAWN /
    revision rows resolve.  ``Checked By`` / ``Date`` are intentionally blank
    fill-ins.  ``extra`` carries part-specific rows (e.g. a thread spec).  The
    drawing recipe fails loud if any REQUIRED property is blank.
    """
    spec = _config.parts(part_name)
    rev_desc = str(spec.get("revision_description") or "Initial release")
    apply_custom_properties(
        adapter,
        {
            "Material Specification": str(spec["material_specification"]),
            "Finish": str(spec["finish"]),
            "Quantity": str(spec["quantity"]),
            "Drawn By": DRAWN_BY,
            "Revision Description": rev_desc,
            **dict(extra or {}),
        },
    )
