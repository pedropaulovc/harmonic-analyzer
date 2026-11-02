r"""Pure-data contract for the south cylinder-bank end disc (MHA-DT-26).

One C36000 brass disc closes gear 0's cam slot and bears directly on the south
arbor-pedestal strap (user ruling 2026-10-20). The later same-day ruling reduces
the OD to clear the unchanged drive; it is not the cylinder-gear tooth OD.
The ordinary thickness band leaves the full web target at its lower limit.
The south strap is located with the measured disc thickness compensated,
establishing the bank's hard datum; the north spring preloads south without
a north disc.
"""

from __future__ import annotations

import _config
from _package_units import drawing_unit
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
from dt_cylinder_end_disc_clearance import clearance_budget

# #290: the registry row's drawing_unit (in) is this sheet's unit; the bands
# and places below are authored for it.
UNIT = drawing_unit("parts/dt-cylinder-end-disc", _config.parts("dt-cylinder-end-disc"))

WASHER_OD = 55.118  # 2.17
# .XX, not .X: the drive and ring-capture budgets read the OD's band.
OUTSIDE_DIA_PLACES = 2
OUTSIDE_DIA_BAND_MM = printed_band_mm(OUTSIDE_DIA_PLACES, unit=UNIT)
RUNNING_AIR_MM = 0.10
CLEARANCE_SPARE_MM = 0.25
# Letter V drill (.377), clearing the 3/8 in MHA-DT-13 cylinder arbor.
WASHER_BORE = 9.5758  # .377
WASHER_THICK = 2.794  # .11
# .XX, not .X: the bank's datum chain reads the thickness band.
THICKNESS_PLACES = 2
WASHER_THICK_TOLERANCE_MM = printed_band_mm(THICKNESS_PLACES, unit=UNIT)
# The DRILL THRU callout inherits this band from the title block.
WASHER_BORE_BAND = (drilled_oversize_mm(unit=UNIT), 0.0)  # (upper, lower) deviations
BORE_CALLOUT = "LETTER V DRILL THRU\nCLEARANCE ON MHA-DT-13"
THICKNESS_CALLOUT = "SOUTH BANK DATUM BETWEEN\nMHA-DT-12 AND MHA-DT-02"

# Decimal places select the ordinary size bands; the actual disc thickness
# is measured and compensated when the south pedestal is located.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingProfile": {"DiscDia", "BoreDia"},
    "Disc": {"DiscThick"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RingProfile": {"DiscDia": OUTSIDE_DIA_PLACES, "BoreDia": 3},
    "Disc": {"DiscThick": THICKNESS_PLACES},
}
DRAWING_PRECISION_BY_NAME = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}


def installed_clearance_budget(datum_band: float) -> dict[str, float]:
    """Fail closed on drive interference or loss of continuous ring retention."""
    budget = clearance_budget(
        outer_dia=WASHER_OD,
        outer_band=OUTSIDE_DIA_BAND_MM,
        bore_max=WASHER_BORE + WASHER_BORE_BAND[0],
        thickness_min=WASHER_THICK - WASHER_THICK_TOLERANCE_MM,
        thickness_max=WASHER_THICK + WASHER_THICK_TOLERANCE_MM,
        datum_band=datum_band,
    )
    for name in ("cone worst", "engaged pinion worst"):
        if budget[name] < RUNNING_AIR_MM + CLEARANCE_SPARE_MM:
            raise AssertionError(
                f"south retaining disc {name}: {budget[name]:.6f} mm "
                f"< {RUNNING_AIR_MM + CLEARANCE_SPARE_MM:.2f} mm"
            )
    if budget["retaining land"] <= 0.0:
        raise AssertionError(
            "south disc no longer captures the ring's complete bore edge"
        )
    return budget
