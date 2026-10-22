"""Offline contracts for the purchased 1330K524 reference sheet."""

from __future__ import annotations

import sm_vn_counter_spring_spec as spec
from spring_mount_geom import counter_force_n


def test_installed_spring_stays_within_catalogue_load_envelope() -> None:
    assert spec.FREE_LENGTH_MM <= spec.INSTALLED_LENGTH_MM <= spec.MAX_LENGTH_MM
    assert counter_force_n(spec.INSTALLED_LENGTH_MM) < spec.MAXIMUM_LOAD_N


def test_supplier_maximum_is_native_not_rounded_print_geometry() -> None:
    import math

    assert math.isclose(spec.FREE_LENGTH_MM, 10.00 * 25.4)
    assert math.isclose(spec.MAX_LENGTH_MM, 421.6146)
    assert not math.isclose(spec.MAX_LENGTH_MM, 16.60 * 25.4)
    assert math.isclose(spec.SUPPLIER_COIL_OD_MM, 0.500 * 25.4)
    assert math.isclose(spec.SUPPLIER_WIRE_DIA_MM, 0.063 * 25.4)
    assert spec.SUPPLIER_PRECISION == {
        "SupplierFreeLength": 2, "SupplierMaximumLength": 2,
        "SupplierCoilOD": 3, "SupplierWireDiameter": 3,
    }
