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


def mark_dimensions_for_drawing(
    adapter: Any, feature_name: str, dimension_names: set[str]
) -> None:
    """Mark only this part's explicit manufacturing dimensions for insertion."""
    feature = _feature_by_name(adapter, feature_name)
    marked: set[str] = set()
    display = _read_member(feature, "GetFirstDisplayDimension")
    for _ in range(1000):
        if not display:
            break
        dimension = display.GetDimension2(0)
        name = str(_read_member(dimension, "Name"))
        if _dim_owner_feature(dimension) == feature_name and name in dimension_names:
            display.MarkedForDrawing = True
            if not bool(_read_member(display, "MarkedForDrawing")):
                raise RuntimeError(f"{name}@{feature_name}: mark-for-drawing failed")
            marked.add(name)
        display = feature.GetNextDisplayDimension(display)
    missing = dimension_names - marked
    if missing:
        raise RuntimeError(
            f"{feature_name}: dimensions not marked for drawing: {sorted(missing)}"
        )
    _telemetry.success(
        f"marked for drawing {feature_name}: {', '.join(sorted(marked))}"
    )


def clear_dimensions_for_drawing(adapter: Any) -> None:
    cleared = 0
    for feature in _iter_features(adapter):
        display = _read_member(feature, "GetFirstDisplayDimension")
        for _ in range(1000):
            if not display:
                break
            if bool(_read_member(display, "MarkedForDrawing")):
                display.MarkedForDrawing = False
                cleared += 1
            display = feature.GetNextDisplayDimension(display)
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
