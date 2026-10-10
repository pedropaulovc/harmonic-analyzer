"""Shared gear grades read from ``tolerances.yaml``.

Kept apart from ``_fit_limits`` (pure constants every part imports) so only
the gear specs that read these grades depend on ``tolerances.yaml``.
"""

from __future__ import annotations

import math

import _config
from _fit_limits import deviations


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
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0.0:
        raise SourceDomainUnknown("drum tooth-to-CAM-NOTCH clock must be a finite positive source requirement")
    return float(value)
