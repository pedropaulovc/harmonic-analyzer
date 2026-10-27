"""A model dimension printed as a single MAX or MIN limit.

``swTolMAX`` / ``swTolMIN`` print the nominal followed by MAX / MIN, so the
modelled value IS the printed limit; the band's deviations stay on the native
tolerance as the model's record of it (sharp up to a MAX radius, say).

Separate to limit cache blast radius: only the recipes that call it carry it in
their closure.  The per-recipe copies this generalises
(``build_ch_fulcrum_keeper._single_limit``, ``build_pn_pen_v_block.
_single_limits`` and their siblings) move here when their recipes next change;
moving them unprompted would re-key those parts and their enforced sheets.
"""

from __future__ import annotations

import math
from typing import Any

import _telemetry
from _com import _early_bound
from _drawing_precision import _named_dimension
from _fit_deviations import deviations

SW_TOL_MIN = 5  # swTolType_e.swTolMIN
SW_TOL_MAX = 6  # swTolType_e.swTolMAX
_WORDS = {SW_TOL_MAX: "MAX", SW_TOL_MIN: "MIN"}


def set_single_limit(
    adapter: Any,
    feature_name: str,
    dimension_name: str,
    *,
    limit: float,
    band: tuple[float, float],
    tol_type: int,
) -> None:
    """Print ``dimension_name@feature_name`` as the single limit ``limit`` mm.

    ``band`` is ``(upper, lower)`` mm about the nominal, as every named band in
    the specs is written.  Fails loud when the model's nominal is not the
    limit, when SolidWorks rejects the deviations, or when the type or the
    deviations do not read back.
    """
    word = _WORDS.get(tol_type)
    if word is None:
        raise ValueError(f"tolerance type {tol_type} is not a single limit")
    label = f"{dimension_name}@{feature_name}"
    lower, upper = deviations(band)
    _, dimension = _named_dimension(adapter, feature_name, dimension_name)
    value = float(dimension.SystemValue)
    if not math.isclose(value, limit / 1000.0, abs_tol=1e-9):
        raise RuntimeError(
            f"{label}: nominal {value * 1000.0:.7f} is not the {word} limit {limit:g}"
        )
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = tol_type
    if not tolerance.SetValues(lower / 1000.0, upper / 1000.0):
        raise RuntimeError(f"{label}: SetValues rejected {lower:+g}/{upper:+g} mm")
    if (
        int(tolerance.Type) != tol_type
        or not math.isclose(
            float(tolerance.GetMinValue()), lower / 1000.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), upper / 1000.0, abs_tol=1e-12
        )
    ):
        raise RuntimeError(f"{label}: {word}-limit tolerance readback changed")
    _telemetry.success(f"{label}: single limit {limit:g} {word}")
