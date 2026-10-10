"""Shared gear grades read from ``tolerances.yaml``.

Kept apart from ``_fit_limits`` (pure constants every part imports) so only
the gear specs that read these grades depend on ``tolerances.yaml``.
"""

from __future__ import annotations

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
