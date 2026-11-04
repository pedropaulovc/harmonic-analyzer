"""Metric vendor-line dimensions on an inch sheet (#290 owner ruling 4, 2026-11-01).

A dimension whose value belongs to a metric-only vendor line (the HGR15R rail's
hole pattern, the KP08 stations along the Tr8 leadscrew) stays exact
millimetres on an inch sheet: never snapped, printed in mm and labelled ``mm``
like the supplier references (``_supplier_dimensions``, ``" mm)"``). The inch
title block's general rows do not cover a millimetre value, so each such
dimension carries its own symmetric band in mm, set beside this helper with
``_drawing_tolerances.set_dimension_symmetric_tolerance(display_unit="mm")``.

The part authors the presentation on its model dimension (units, places,
suffix); an imported dimension keeps the places and suffix but takes the
sheet's document units, so ``_drawing_metric_vendor`` sets millimetres on the
sheet and reads them back.
"""

from __future__ import annotations

from typing import Any

import _telemetry
from _com import _early_bound
from _drawing_precision import _named_dimension

MM_SUFFIX = " mm"
_SW_MM = 0  # swLengthUnit_e.swMM
_SW_DECIMAL = 1  # swFractionDisplay_e.swDECIMAL
_KEEP = -1  # swDimensionPrecisionSettings_e: do not change


def _presentation(display: Any) -> tuple[bool, int, int, str]:
    return (
        bool(display.GetUseDocUnits()),
        int(display.GetUnits()),
        int(display.GetPrimaryPrecision2()),
        str(display.GetText(2) or ""),  # swDimensionTextSuffix
    )


@_telemetry.traced("dim.metric_vendor_units", label_param="dimension_name")
def set_metric_vendor_units(
    adapter: Any,
    feature_name: str,
    dimension_name: str,
    *,
    places: int,
) -> None:
    """Print one model dimension in mm at ``places``, labelled ``mm``."""
    label = f"{dimension_name}@{feature_name}"
    raw, _dimension = _named_dimension(adapter, feature_name, dimension_name)
    display = _early_bound(raw, "IDisplayDimension")
    if display.SetUnits2(False, _SW_MM, _SW_DECIMAL, 0, False, 0) != 0:
        raise RuntimeError(f"{label}: millimetre units were rejected")
    if display.SetPrecision3(places, _KEEP, _KEEP, _KEEP) != 0:
        raise RuntimeError(f"{label}: {places} millimetre places were rejected")
    display.SetText(2, MM_SUFFIX)
    expected = (False, _SW_MM, places, MM_SUFFIX)
    if _presentation(display) != expected:
        raise RuntimeError(
            f"{label}: millimetre presentation did not persist: "
            f"{_presentation(display)!r} != {expected!r}"
        )
