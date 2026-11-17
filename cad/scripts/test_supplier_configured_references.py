"""Offline native-inventory regressions; not a claim of SOLIDWORKS parity."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import _supplier_spring_drawing as supplier_drawing
from _mcmaster_9666k142 import DIA
from _mcmaster_9666k142_reference import (
    SUPPLIER_REFERENCE_CONFIGURATION,
    SUPPLIER_REFERENCE_DIMENSION,
    SUPPLIER_REFERENCE_FEATURE,
)


class _NativeDimension:
    def __init__(self, name, owner, value_mm):
        self.FullName = f"{name}@{owner}@native-part.SLDPRT"
        self.value_mm = value_mm
        self.Tolerance = SimpleNamespace(Type=0)

    def GetSystemValue3(self, which, configuration_names):
        assert which == 3
        raw_names = getattr(configuration_names, "value", configuration_names)
        names = (raw_names,) if isinstance(raw_names, str) else tuple(raw_names)
        if names != (SUPPLIER_REFERENCE_CONFIGURATION,):
            # An unqualified/installed-member lookup must not happen to pass.
            return (1.3 / 1000.0,)
        return (self.value_mm / 1000.0,)


class _Display:
    def __init__(self, name, owner, value_mm):
        self.native = _NativeDimension(name, owner, value_mm)

    def GetDimension2(self, index):
        assert index == 0
        return self.native


def test_wire_nominal_cannot_be_read_from_the_wire_lane(monkeypatch):
    monkeypatch.setattr(
        supplier_drawing, "_early_bound", lambda value, _interface: value
    )
    display = _Display(SUPPLIER_REFERENCE_DIMENSION, SUPPLIER_REFERENCE_FEATURE, DIA)
    supplier_drawing.assert_supplier_configuration_value(
        display,
        SUPPLIER_REFERENCE_CONFIGURATION,
        0.2032,
        label="supplier wire circle",
    )
    display.native.value_mm = 0.8
    with pytest.raises(RuntimeError, match="configured supplier dimension changed"):
        supplier_drawing.assert_supplier_configuration_value(
            display,
            SUPPLIER_REFERENCE_CONFIGURATION,
            DIA,
            label="supplier wire circle",
        )
