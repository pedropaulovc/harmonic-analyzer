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

import math
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


def _named_dimension(
    adapter: Any, feature_name: str, dimension_name: str
) -> tuple[Any, Any]:
    """Resolve exactly one named display/source dimension on ``feature_name``."""
    feature = _feature_by_name(adapter, feature_name)
    matches: list[tuple[Any, Any]] = []
    display = _read_member(feature, "GetFirstDisplayDimension")
    for _ in range(1000):
        if not display:
            break
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        name = str(_read_member(dimension, "Name"))
        if _dim_owner_feature(dimension) == feature_name and name == dimension_name:
            matches.append((display, dimension))
        display = feature.GetNextDisplayDimension(display)
    if len(matches) != 1:
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: expected exactly one dimension, "
            f"found {len(matches)}"
        )
    return matches[0]


def set_dimension_symmetric_tolerance(
    adapter: Any,
    feature_name: str,
    dimension_name: str,
    tolerance_mm: float,
) -> None:
    """Tolerance one named source-model dimension and verify the stored values."""
    if tolerance_mm <= 0.0:
        raise ValueError("symmetric dimension tolerance must be positive")
    _, dimension = _named_dimension(adapter, feature_name, dimension_name)
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
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
    _, dimension = _named_dimension(adapter, feature_name, dimension_name)
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
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


def set_dimension_symmetric_angular_tolerance(
    adapter: Any,
    feature_name: str,
    dimension_name: str,
    tolerance_degrees: float,
    *,
    require_driven: bool = False,
) -> None:
    """Tolerance one angular model dimension; SolidWorks stores radians."""
    if tolerance_degrees <= 0.0:
        raise ValueError("symmetric angular tolerance must be positive")
    _, dimension = _named_dimension(adapter, feature_name, dimension_name)
    if require_driven and int(_read_member(dimension, "DrivenState")) != 1:
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: expected a driven reference dimension"
        )
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = 4  # swTolType_e.swTolSYMMETRIC
    tolerance_rad = math.radians(tolerance_degrees)
    if not tolerance.SetValues(-tolerance_rad, tolerance_rad):
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: SetValues rejected "
            f"+/-{tolerance_degrees} deg"
        )
    minimum = float(tolerance.GetMinValue())
    maximum = float(tolerance.GetMaxValue())
    if abs(minimum + tolerance_rad) > 1e-12 or abs(maximum - tolerance_rad) > 1e-12:
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: angular tolerance readback "
            f"{minimum:g}/{maximum:g} rad != +/-{tolerance_rad:g} rad"
        )
    _telemetry.success(
        f"toleranced {dimension_name}@{feature_name}: +/-{tolerance_degrees:.2f} deg"
    )


def set_dimension_prefix(
    adapter: Any, feature_name: str, dimension_name: str, prefix: str
) -> None:
    """Set and verify a model display dimension's native prefix text."""
    display, _ = _named_dimension(adapter, feature_name, dimension_name)
    display = _early_bound(display, "IDisplayDimension")
    if not display.SetText(1, prefix):  # swDimensionTextParts_e.swDimensionTextPrefix
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: failed to set prefix {prefix!r}"
        )
    if str(display.GetText(1) or "") != prefix:
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: prefix did not persist as {prefix!r}"
        )


@_telemetry.traced("dim.diametric", label_param="label")
async def add_diametric_linear_dimension(
    adapter: Any,
    centerline: str,
    line: str,
    text_xy: tuple[float, float],
    label: str,
) -> Any:
    """Create a doubled centerline-to-outline diameter dimension."""
    from solidworks_mcp.adapters import sw_type_info as _sw_type_info
    from solidworks_mcp.adapters.solidworks.sketch import (
        _resolve_entity_ref,
        _select_sketch_entities,
    )

    model = adapter.currentModel
    model.ClearSelection2(True)
    if line.endswith((".start", ".end", ".center")):
        _select_sketch_entities(adapter, [centerline], 0)
        point = _resolve_entity_ref(adapter, line)
        if not bool(point.Select4(True, None)):
            raise RuntimeError(f"{label}: failed to select sketch point {line!r}")
    else:
        _select_sketch_entities(adapter, [centerline, line], 0)
    extension = _sw_type_info.early_bound_or_flag(
        model.Extension, "IModelDocExtension", "AddSpecificDimension"
    )
    display, status = extension.AddSpecificDimension(
        text_xy[0] / 1000.0,
        text_xy[1] / 1000.0,
        0.0,
        15,  # swDimensionType_e.swDiametricLinearDimension
        0,
    )
    model.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"{label}: AddSpecificDimension(diametric) failed ({status})")
    display = _early_bound(display, "IDisplayDimension")
    if not bool(_read_member(display, "Diametric")):
        raise RuntimeError(f"{label}: new dimension is not diametric")
    _telemetry.success(f"diametric dim {label}")
    return display


@_telemetry.traced("dim.angular_reference", label_param="label")
async def add_angular_reference_dimension(
    adapter: Any,
    first_line: str,
    second_line: str,
    text_xy: tuple[float, float],
    label: str,
    *,
    expected_degrees: float,
) -> Any:
    """Create and verify a driven angular dimension between two sketch lines."""
    from solidworks_mcp.adapters import sw_type_info as _sw_type_info
    from solidworks_mcp.adapters.solidworks.sketch import _select_sketch_entities

    if expected_degrees <= 0.0 or expected_degrees >= 180.0:
        raise ValueError("expected reference angle must be between 0 and 180 degrees")
    model = adapter.currentModel
    model.ClearSelection2(True)
    _select_sketch_entities(adapter, [first_line, second_line], 0)
    extension = _sw_type_info.early_bound_or_flag(
        model.Extension, "IModelDocExtension", "AddSpecificDimension"
    )
    display, status = extension.AddSpecificDimension(
        text_xy[0] / 1000.0,
        text_xy[1] / 1000.0,
        0.0,
        3,  # swDimensionType_e.swAngularDimension
        0,
    )
    model.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"{label}: AddSpecificDimension(angular) failed ({status})")
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    dimension.DrivenState = 1  # swDimensionDrivenState_e.swDimensionDriven
    if int(_read_member(dimension, "DrivenState")) != 1:
        raise RuntimeError(f"{label}: angular dimension did not become driven")

    expected_rad = math.radians(expected_degrees)
    actual_rad = abs(float(_read_member(dimension, "SystemValue")))
    if abs(actual_rad - expected_rad) > 1e-8:
        supplement_rad = abs(math.pi - actual_rad)
        if abs(supplement_rad - expected_rad) > 1e-8 or not display.SupplementaryAngle():
            raise RuntimeError(
                f"{label}: angular dimension measured {math.degrees(actual_rad):.6f} "
                f"deg, expected {expected_degrees:.6f} deg"
            )
        actual_rad = abs(float(_read_member(dimension, "SystemValue")))
    if abs(actual_rad - expected_rad) > 1e-8:
        raise RuntimeError(
            f"{label}: angular dimension readback {math.degrees(actual_rad):.6f} "
            f"deg != {expected_degrees:.6f} deg"
        )
    _telemetry.success(f"angular reference dim {label}: {expected_degrees:.3f} deg")
    return display


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
