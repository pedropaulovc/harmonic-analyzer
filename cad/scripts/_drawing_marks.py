"""Part-side drawing support: dimension marks + manufacturing properties.

Imported ONLY by parts that ship a manufacturing drawing (see
``_drawing_registry``).  Deliberately a separate module from ``_common`` so
adding a drawing to one part never shifts the recipe digest of the ~100 parts
that carry no drawing.

The drawing recipe (``draw_<part>.py``) later imports exactly the dimensions a
part marks here (``swInsertDimensionsMarkedForDrawing``), so the SLDPRT stays
the single source of every manufacturing dimension.
"""

from __future__ import annotations

from typing import Any, Mapping

import _config
import _telemetry
from _common import (
    apply_custom_properties,
    _dim_owner_feature,
    _feature_by_name,
    _iter_features,
    _read_member,
)


def _feature_tree(feature: Any) -> Any:
    """Yield ``feature`` and every subfeature, depth-first.

    Hole Wizard placement dimensions live on ``ProfileFeature`` subfeatures,
    so both the mark AND the clear path must walk the same tree — a clear
    that stops at top level leaves stale marks on child-feature dimensions.
    """
    stack = [feature]
    while stack:
        current = stack.pop()
        yield current
        child = _read_member(current, "GetFirstSubFeature")
        children: list[Any] = []
        for _ in range(1000):
            if not child:
                break
            children.append(child)
            child = _read_member(child, "GetNextSubFeature")
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
        current_name = str(_read_member(current, "Name"))
        display = _read_member(current, "GetFirstDisplayDimension")
        for _ in range(1000):
            if not display:
                break
            dimension = display.GetDimension2(0)
            name = str(_read_member(dimension, "Name"))
            owner = _dim_owner_feature(dimension)
            if owner == current_name and name in dimension_names:
                full_name = str(_read_member(dimension, "FullName"))
                previous = matches.get(name)
                if previous is not None and previous[1] != full_name:
                    raise RuntimeError(
                        f"{feature_name}: drawing dimension {name!r} is ambiguous: "
                        f"{previous[1]!r}, {full_name!r}"
                    )
                matches[name] = (display, full_name)
            display = current.GetNextDisplayDimension(display)

    missing = dimension_names - matches.keys()
    if missing:
        raise RuntimeError(
            f"{feature_name}: dimensions not marked for drawing: {sorted(missing)}"
        )
    for name, (display, full_name) in matches.items():
        display.MarkedForDrawing = True
        if not bool(_read_member(display, "MarkedForDrawing")):
            raise RuntimeError(f"{full_name}: mark-for-drawing failed")
    _telemetry.success(
        f"marked for drawing {feature_name}: {', '.join(sorted(matches))}"
    )


def clear_dimensions_for_drawing(adapter: Any) -> None:
    cleared = 0
    for feature in _iter_features(adapter):
        for current in _feature_tree(feature):
            display = _read_member(current, "GetFirstDisplayDimension")
            for _ in range(1000):
                if not display:
                    break
                if bool(_read_member(display, "MarkedForDrawing")):
                    display.MarkedForDrawing = False
                    cleared += 1
                display = current.GetNextDisplayDimension(display)
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
