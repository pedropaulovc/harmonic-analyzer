"""Final supplier-band corruption rejection; no native geometry-parity claim."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import _supplier_extension_spring as extension
import _supplier_extension_spring_drawing as extension_drawing
import vn_channel_spring_installed_spec as channel


@pytest.mark.parametrize("corruption", ["type", "lower", "upper", "precision"])
def test_settled_checks_reject_supplier_tolerance_corruption(monkeypatch, corruption):
    tolerance = SimpleNamespace(
        Type=4,
        GetMinValue=lambda: -channel.SUPPLIER_COIL_OD_TOLERANCE_MM / 1000,
        GetMaxValue=lambda: channel.SUPPLIER_COIL_OD_TOLERANCE_MM / 1000,
    )
    no_band = SimpleNamespace(Type=0)
    displays = {
        name: SimpleNamespace(
            GetDimension2=lambda index, name=name: SimpleNamespace(
                Tolerance=tolerance if name == extension.COIL_OD else no_band,
                FullName=f"{name}@{next(feature for feature, names in extension.DIMENSIONS_BY_FEATURE.items() if name in names)}@Source",
            ),
            GetPrimaryTolPrecision2=lambda: (
                channel.SUPPLIER_COIL_OD_TOLERANCE_PRECISION
            ),
        )
        for name in channel.SUPPLIER_PRECISION
    }

    def curate(adapter, view, *, keep, **kwargs):
        return [
            SimpleNamespace(
                name=name, GetSpecificAnnotation=lambda name=name: displays[name]
            )
            for name in keep
        ]

    monkeypatch.setattr(
        extension_drawing, "_early_bound", lambda value, interface: value
    )
    monkeypatch.setattr(extension_drawing, "curate_view_dimensions", curate)
    monkeypatch.setattr(
        extension_drawing, "dimension_name", lambda adapter, annotation: annotation.name
    )
    monkeypatch.setattr(
        extension_drawing,
        "supplier_reference_dimension",
        lambda adapter, display, **kwargs: display,
    )
    monkeypatch.setattr(
        extension_drawing,
        "assert_supplier_reference_dimension",
        lambda *args, **kwargs: None,
    )
    views = {
        key: SimpleNamespace(GetOutline=lambda: (0.1, 0.1, 0.2, 0.12))
        for key in ("free_front", "free_right", "max_front")
    }
    checks = extension_drawing.extension_spring_dimensions(
        object(),
        views,
        free_length_mm=channel.FREE_LENGTH_MM,
        max_length_mm=channel.MAX_LENGTH_MM,
        coil_od_mm=channel.SUPPLIER_COIL_OD_MM,
        wire_dia_mm=channel.SUPPLIER_WIRE_DIA_MM,
        precision=channel.SUPPLIER_PRECISION,
        od_tolerance_mm=channel.SUPPLIER_COIL_OD_TOLERANCE_MM,
        od_tolerance_precision=channel.SUPPLIER_COIL_OD_TOLERANCE_PRECISION,
    )
    for check in checks:
        check()
    if corruption == "type":
        tolerance.Type = 0
    elif corruption == "lower":
        tolerance.GetMinValue = lambda: 0.0
    elif corruption == "upper":
        tolerance.GetMaxValue = lambda: 0.0
    else:
        displays[extension.COIL_OD].GetPrimaryTolPrecision2 = lambda: 0
    with pytest.raises(RuntimeError, match="band changed after final rebuild"):
        for check in checks:
            check()
