"""Diameter bands of the cone gear shaft's lands (MHA-DT-04) and the gears on
them.

The shaft spec applies these bands to its model dimensions; the cone gears
derive their bores from them.  They live here, not in
``cone_gear_shaft_spec``, so the gear family reads the bands without importing
the shaft's finish, GD&T and installation data: an unrelated shaft-spec edit
does not re-key every cone gear (Main ruling, 2026-09-25).
"""

from __future__ import annotations

import _config
from _package_units import drawing_unit
from _printed_tolerance import printed_deviations
from _fit_shaft_h import SHAFT_H

# #290: the shaft sheet's unit (its registry row's drawing_unit); every land
# below prints, and is judged, in it.
UNIT = drawing_unit("parts/dt-cone-gear-shaft", _config.parts("dt-cone-gear-shaft"))

# Diameter bands, one NAMED class per land, applied to the model dimension
# by build_dt_cone_gear_shaft -- never "+0.00/-0.02" typed as sheet callout text.
#
# The pivot journal RUNS and keeps the shared ground-shaft h band.
RUNNING_DIA_BAND = SHAFT_H
# GEAR_SEAT_BAND (U27, 2026-09-23): the two gear lands only carry gears,
# slid on against the stack (gear_seat_fit).  The upper limit stays at
# nominal, so every gear still passes down its land to its station; the
# -.0020 in lower limit holds the gear within about .002 in radially with its
# bore band -- a small fraction of the ~0.51 mm module, so mesh runout does
# not suffer.  2.5x the h band, which a micrometer holds on a manual lathe.
# Spec-local on purpose: _fit_shaft_h is imported by every ground-shaft
# h-band user.
GEAR_SEAT_BAND = (0.0, -0.0508)
# Three sections (owner decision C1 keyed, 2026-11-09, PR #1992;
# cone_tip_cluster): the journal, land 1 keyed (cone_land_key) and the round
# land 2.  The tip lands 3 and 4 are gone: T018 and T012 ride T006's spigot,
# bonded in a socket in land 2's end.  That decision supersedes the user
# ruling 2026-09-28 (one D-flat per gear land, every gear on a D-bore; no
# keys, no solder, no retaining compound, no gear bonded) -- no flat remains
# on the shaft -- and U40 (2026-09-23: the slender terminal tip land turned
# with tailstock support), retired with land 4.
SECTION_DIA_BANDS: tuple[tuple[float, float], ...] = (
    RUNNING_DIA_BAND,  # Sec0: pivot journal
    GEAR_SEAT_BAND,  # Sec1: 64T + T030-T120, keyed
    GEAR_SEAT_BAND,  # Sec2: T024, round, bonded
)
# Shared displayed precision: native drawing and physical-limit consumers
# read the same per-section table; no unrounded-nominal acceptance mapping.
# Inch places: four on every land, the places their .0008/.0020 in bands
# need (.4825, .3750, .2500).
LAND_DIA_PLACES = (4, 4, 4)


def _printed_mm(native_mm: float, places: int) -> float:
    """The number the shaft sheet prints for ``native_mm`` at ``places``, in mm."""
    return native_mm + printed_deviations(native_mm, places, (0.0, 0.0), unit=UNIT)[0]


def land_finished_dia_limits_mm(native_diameter_mm: float, section: int) -> tuple[float, float]:
    """Absolute PRINTED (MIN,MAX), with the retained named land size band."""
    nominal = _printed_mm(native_diameter_mm, LAND_DIA_PLACES[section])
    upper, lower = SECTION_DIA_BANDS[section]
    return nominal+lower, nominal+upper


# The cone gears each section carries, index-aligned with SECTION_DIA_BANDS.
# The 64T crank-drive gear also rides Sec1.  T018 and T012 ride T006's
# spigot, and T006 (MHA-DT-37) is its own part, so land 2 carries T024 alone.
SECTION_CONE_GEAR_TEETH: tuple[tuple[int, ...], ...] = (
    (),
    tuple(range(30, 121, 6)),
    (24,),
)
