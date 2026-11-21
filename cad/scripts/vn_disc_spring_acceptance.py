"""Receiving ID/OD limits for the wave disc spring MHA-DT-VN-68.

PURE DATA, no SolidWorks/COM calls. Owner ruling 2026-11-17 on #3044: the
OD and the ID maximum are the supplier catalogue's tolerances (the specs'
``OD_BAND``/``ID_BAND``); the ID minimum is an owner-directed receiving
acceptance tighter than the catalogue, because the catalogue's smallest ID
does not pass the mating shaft (some purchased springs may be rejected at
receiving). The minimum is the shaft's largest printed size plus a sliding
allowance, the middle of the ``shaft_in_bushing`` slip-fit diametral
clearance (tolerances/shaft_in_bushing.yaml), rounded up to the print's
.001 in. The diagram dimensions print these limits
(``vn_disc_spring_supplier_stock``); the bank-layout test consumes them.
"""

from __future__ import annotations

import math

import _config
import dt_cylinder_gear_shaft_spec as cylinder_arbor
import dt_vn_cylinder_bank_spring_spec as cylinder

MM_PER_IN = 25.4
PLACES = 3  # the diagram dimensions' printed inch places
_SLIP_FIT = _config.fit("shaft_in_bushing")["diametral_clearance_mm"]
SLIDING_ALLOWANCE_MM = (float(_SLIP_FIT[0]) + float(_SLIP_FIT[1])) / 2.0


def _ceil_inch_mm(value_mm: float) -> float:
    """``value_mm`` rounded up to the print's .001 in, in mm."""
    step = 10**-PLACES
    return math.ceil(value_mm / MM_PER_IN / step - 1e-9) * step * MM_PER_IN


def accepted_id_min_mm(shaft_dia: float, shaft_band: tuple[float, float]) -> float:
    """The smallest spring ID that slides on the largest printed shaft."""
    return _ceil_inch_mm(shaft_dia + max(shaft_band) + SLIDING_ALLOWANCE_MM)


def _limits(spec, shaft_dia: float, shaft_band: tuple[float, float]) -> dict:
    return {
        "ID": (accepted_id_min_mm(shaft_dia, shaft_band), spec.ID + spec.ID_BAND[0]),
        "OD": (spec.OD + spec.OD_BAND[1], spec.OD + spec.OD_BAND[0]),
    }


# (minimum, maximum) mm, by SKU and spec field.
LIMITS = {
    cylinder.SKU: _limits(
        cylinder, cylinder_arbor.SHAFT_DIA, cylinder_arbor.SHAFT_DIA_BAND
    ),
}

for _sku, _fields in LIMITS.items():
    for _field, (_low, _high) in _fields.items():
        if not _low < _high:
            raise AssertionError(f"{_sku} {_field} acceptance {_low}-{_high} is empty")
