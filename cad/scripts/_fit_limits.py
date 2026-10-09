"""Shared fit-limit formatting for released drawing callouts.

PURE DATA, no SolidWorks/COM imports.  Every released MAX/MIN final-size
callout must derive from its spec nominal plus a NAMED offset band through
:func:`fit_limits` — literal limit text in a drawing script is a defect: a
spec retune rebuilds the part and the displayed nominal while the released
shop limits silently keep the old values (codex #359 rounds 2-3, six sheets).

The bands here are the fit CLASSES shared across parts; a band peculiar to
one part (an asymmetric mid-nominal ream, a press band) lives as a named
constant in that part's ``*_spec.py`` next to the nominal it tolerances.
"""

from __future__ import annotations

import math

import _config

# Fit classes: (upper, lower) offsets in mm, added to the nominal.
# Reamed slide/running fit for a ground rod or arbor over its shared nominal.
REAM_SLIDE = (0.025, 0.010)
# Ground-shaft h band: nominal down to -0.020.
SHAFT_H = (0.000, -0.020)
# ISO H7 reamed hole, 3-6 mm size range: +0.012 / +0.000.
REAM_H7 = (0.012, 0.000)
# ISO g6 ground shaft, 3-6 mm size range: -0.004 / -0.012.
# Source: Mitsubishi Materials shaft-fit table, >3 through 6 mm row (micrometres).
# https://www.mitsubishicarbide.net/contents/mhg/enuk/html/product/technical_information/information/pdf/fit_tolerance_table_shaft.pdf
SHAFT_G6_3_TO_6_MM = (-0.004, -0.012)


def measured_close_running_clearance_mm() -> tuple[float, float]:
    """H7/g6-equivalent diametral clearance for a bore matched to its shaft.

    This is a clearance class, not permission to replace a supplied shaft's
    size band. The owning part must measure that shaft and accept the bore
    between the measured size plus these limits; a model nominal is REF.
    """
    hole_lower, hole_upper = deviations(REAM_H7)
    shaft_lower, shaft_upper = deviations(SHAFT_G6_3_TO_6_MM)
    return hole_lower - shaft_upper, hole_upper - shaft_lower


def gear_tip_band_mm(grade: str) -> tuple[float, float]:
    """Read one functional gear-tip grade as ``(upper, lower)`` deviations.

    These are the shared fit/process classes in ``tolerances.yaml``, not
    tooth-form or AGMA accuracy claims.  Part specs own the printed nominal
    and derive their accepted MIN/MAX from that rounded value.
    """
    if grade not in {"standard", "contact_critical"}:
        raise ValueError(f"unsupported gear-tip grade {grade!r}")
    upper, lower = _config.fit("gear_tip", f"{grade}_band_mm")
    band = float(upper), float(lower)
    deviations(band)
    return band


class SourceDomainUnknown(ValueError):
    """A real physical source authority needed by the full mesh is absent."""


def tooth_cutting_runout_tir_mm(body: str) -> float:
    """Read the shared part's required process/inspection TIR, not measured stock.

    These source keys receive grades only after actual all-profile margins
    establish an achievable observable requirement. Their absence is refusal.
    The drum grade is also the same 120T part's alignment-mesh input.
    """
    if body not in ("cone", "drum"):
        raise ValueError("tooth runout body must be cone or drum")
    key = f"{body}_tooth_cutting_runout_tir_mm"
    try:
        value = _config.fit("cone_drum_oblique_mesh", key)
    except KeyError as error:
        raise SourceDomainUnknown(f"missing actual {body} tooth-to-bore TIR authority: {key}") from error
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0.0:
        raise SourceDomainUnknown(f"{body} tooth-to-bore TIR must be a finite positive source requirement")
    return float(value)


def drum_tooth_to_cam_notch_clock_deg() -> float:
    """Require the actual gear-pattern/CAM-NOTCH grade, not the lobe grade.

    Whole-body NOTCH-up setup is not this manufactured angular error.
    A proposed or full-pitch engineering band is not a production requirement.
    """
    key = "drum_tooth_to_cam_notch_clock_deg"
    try:
        value = _config.fit("cone_drum_oblique_mesh", key)
    except KeyError as error:
        raise SourceDomainUnknown(f"missing actual drum tooth-to-CAM-NOTCH clock authority: {key}") from error
    if type(value) not in (int,float) or not math.isfinite(value) or value<=0.0:
        raise SourceDomainUnknown("drum tooth-to-CAM-NOTCH clock must be a finite positive source requirement")
    return float(value)


def band_text(band: tuple[float, float]) -> str:
    """Render an ``(upper, lower)`` band the way a shop note quotes it.

    Upper deviation first (ASME Y14.5 §2.3.2).  A note that quotes a band beside
    a nominal must render it from the SAME constant the model dimension is
    toleranced with, or the two drift — the half-migrated pattern where the
    nominal is f-stringed and the band beside it is typed.

    A nil deviation keeps its band's SIGN (``-0.00`` on the low side of a
    unilateral band), because that is what the released sheets print today and
    this helper exists to make a relocation a pure refactor.  Y14.5 §2.3.2
    actually prefers a bare ``0`` for a nil limit; switching to it changes ink on
    every affected sheet, so it is a deliberate drawing change to make on its
    own, not a side effect of moving a constant.
    """
    upper, lower = band
    if upper <= lower:
        raise ValueError(f"fit band is inverted: {band!r}")
    low = f"{lower:+.2f}" if lower else "-0.00"
    return f"{upper:+.2f}/{low}"


def deviations(band: tuple[float, float]) -> tuple[float, float]:
    """Return ``(lower, upper)`` — the argument order the model setter takes.

    The bands above are written ``(upper, lower)`` because that is how a fit is
    quoted on a print (upper deviation first, ASME Y14.5 §2.3.2), but
    ``_drawing_marks.set_dimension_bilateral_tolerance`` takes
    ``(lower_deviation_mm, upper_deviation_mm)``.  BOTH orderings type-check and
    a silent swap INVERTS the band, so no call site is allowed to transpose by
    hand — splat this instead::

        set_dimension_bilateral_tolerance(adapter, "StubProfile", "SeatDia",
                                          *deviations(SHAFT_H))
    """
    upper, lower = band
    if upper <= lower:
        raise ValueError(f"fit band is inverted: {band!r}")
    return lower, upper


def fit_limits(
    nominal: float,
    band: tuple[float, float],
    *,
    decimals: int = 3,
    diameter: bool = False,
) -> str:
    """Render ``X.XXX MAX / X.XXX MIN`` from a nominal + (upper, lower) band."""
    upper, lower = band
    if upper <= lower:
        raise ValueError(f"fit band is inverted: {band!r}")
    prefix = "<MOD-DIAM>" if diameter else ""
    return (
        f"{prefix}{nominal + upper:.{decimals}f} MAX / "
        f"{prefix}{nominal + lower:.{decimals}f} MIN"
    )
