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
    _early_bound,
    _feature_by_name,
    _iter_features,
    _read_member,
)


def _iter_subfeatures(feature: Any):
    """Yield a feature's complete subfeature tree in display order."""
    subfeature = _read_member(feature, "GetFirstSubFeature")
    for _ in range(5000):
        if not subfeature:
            return
        yield subfeature
        yield from _iter_subfeatures(subfeature)
        subfeature = _read_member(subfeature, "GetNextSubFeature")


def _iter_features_deep(adapter: Any):
    for feature in _iter_features(adapter):
        yield feature
        yield from _iter_subfeatures(feature)


def _feature_by_name_deep(adapter: Any, name: str) -> Any:
    for feature in _iter_features_deep(adapter):
        if str(_read_member(feature, "Name")) == name:
            return feature
    raise RuntimeError(f"feature {name!r} not found in the active document")


def set_dimension_symmetric_tolerance(
    adapter: Any,
    feature_name: str,
    dimension_name: str,
    tolerance_mm: float,
) -> None:
    """Tolerance one named source-model dimension and verify the stored values."""
    if tolerance_mm <= 0.0:
        raise ValueError("symmetric dimension tolerance must be positive")
    feature = _feature_by_name(adapter, feature_name)
    matches: list[Any] = []
    display = _read_member(feature, "GetFirstDisplayDimension")
    for _ in range(1000):
        if not display:
            break
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        name = str(_read_member(dimension, "Name"))
        if _dim_owner_feature(dimension) == feature_name and name == dimension_name:
            matches.append(dimension)
        display = feature.GetNextDisplayDimension(display)
    if len(matches) != 1:
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: expected exactly one dimension, "
            f"found {len(matches)}"
        )
    tolerance = _early_bound(matches[0].Tolerance, "IDimensionTolerance")
    tolerance.Type = 4  # swTolType_e.swTolSYMMETRIC
    tolerance_m = tolerance_mm / 1000.0
    # SOLIDWORKS 2026 rejects SetValues2 for this extrusion-depth dimension in
    # both all-configuration and active-configuration forms.  SetValues is the
    # source-model path already exercised by _holes._tolerance_hole_diameter.
    if not tolerance.SetValues(-tolerance_m, tolerance_m):
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: SetValues rejected +/-{tolerance_mm} mm"
        )
    if int(tolerance.Type) != 4:
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: symmetric tolerance type did not persist"
        )
    minimum = float(tolerance.GetMinValue())
    maximum = float(tolerance.GetMaxValue())
    if abs(minimum + tolerance_m) > 1e-9 or abs(maximum - tolerance_m) > 1e-9:
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: tolerance readback "
            f"{minimum:g}/{maximum:g} m != +/-{tolerance_m:g} m"
        )
    _telemetry.success(
        f"toleranced {dimension_name}@{feature_name}: +/-{tolerance_mm:.2f} mm"
    )


def set_dimension_bilateral_tolerance(
    adapter: Any,
    feature_name: str,
    dimension_name: str,
    lower_deviation_mm: float,
    upper_deviation_mm: float,
) -> None:
    """Apply signed lower/upper deviations to one named source dimension."""
    if lower_deviation_mm > upper_deviation_mm:
        raise ValueError("lower dimension deviation must not exceed upper deviation")
    if lower_deviation_mm == upper_deviation_mm:
        raise ValueError("bilateral dimension tolerance must have a nonzero range")
    feature = _feature_by_name(adapter, feature_name)
    matches: list[Any] = []
    display = _read_member(feature, "GetFirstDisplayDimension")
    for _ in range(1000):
        if not display:
            break
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        name = str(_read_member(dimension, "Name"))
        if _dim_owner_feature(dimension) == feature_name and name == dimension_name:
            matches.append(dimension)
        display = feature.GetNextDisplayDimension(display)
    if len(matches) != 1:
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: expected exactly one dimension, "
            f"found {len(matches)}"
        )
    tolerance = _early_bound(matches[0].Tolerance, "IDimensionTolerance")
    tolerance.Type = 2  # swTolType_e.swTolBILAT
    lower_m = lower_deviation_mm / 1000.0
    upper_m = upper_deviation_mm / 1000.0
    if not tolerance.SetValues(lower_m, upper_m):
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: SetValues rejected "
            f"{lower_deviation_mm:+.2f}/{upper_deviation_mm:+.2f} mm"
        )
    if int(tolerance.Type) != 2:
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: bilateral tolerance type did not persist"
        )
    minimum = float(tolerance.GetMinValue())
    maximum = float(tolerance.GetMaxValue())
    if abs(minimum - lower_m) > 1e-9 or abs(maximum - upper_m) > 1e-9:
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: tolerance readback "
            f"{minimum:g}/{maximum:g} m != {lower_m:g}/{upper_m:g} m"
        )
    _telemetry.success(
        f"toleranced {dimension_name}@{feature_name}: "
        f"{lower_deviation_mm:+.2f}/{upper_deviation_mm:+.2f} mm"
    )


def mark_dimensions_for_drawing(
    adapter: Any, feature_name: str, dimension_names: set[str]
) -> None:
    """Mark only this part's explicit manufacturing dimensions for insertion."""
    feature = _feature_by_name_deep(adapter, feature_name)
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
    for feature in _iter_features_deep(adapter):
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
