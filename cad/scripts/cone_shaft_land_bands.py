"""Diameter bands of the cone gear shaft's lands (MHA-014) and the gears on them.

The shaft spec applies these bands to its model dimensions; the cone gears
derive their bonded bores from them.  They live here, not in
``cone_gear_shaft_spec``, so the gear family reads the bands without importing
the shaft's finish, GD&T and installation data: an unrelated shaft-spec edit
does not re-key every cone gear (Main ruling, 2026-09-25).
"""

from __future__ import annotations

from _fit_limits import SHAFT_H

# Diameter bands, one NAMED class per land, applied to the model dimension
# by build_cone_gear_shaft -- never "+0.00/-0.02" typed as sheet callout text.
#
# The two lands that RUN keep the shared ground-shaft h band: the Ø12.231
# journal turns in the pivot post's Ø12.2808 bore (0.05 nominal clearance),
# and the Ø1.588 tip land -- the T012 and T006 seats AND the journal -- turns
# in the cone tip bushing's 1.5875 +0.05/0 bore, 0..0.07 running clearance.
RUNNING_DIA_BAND = SHAFT_H
# GEAR_SEAT_BAND (U27, 2026-09-23): the three intermediate lands only carry
# soldered gears.  The upper limit stays at nominal, so every gear still
# passes down its land to its pitch station; the -0.05 lower limit is the
# soft-solder capillary gap, and holds the gear within 0.025 radially -- a
# small fraction of the ~0.51 mm module, so mesh runout does not suffer.
# 2.5x the h band, which a micrometer holds on a manual lathe; -0.10 would
# allow ~20% of the module in runout on hand-cut teeth.  Spec-local on
# purpose: _fit_limits is imported fleet-wide.
GEAR_SEAT_BAND = (0.000, -0.050)
SECTION_DIA_BANDS: tuple[tuple[float, float], ...] = (
    RUNNING_DIA_BAND,  # Sec0: pivot journal
    GEAR_SEAT_BAND,  # Sec1: T030-T120 seats
    GEAR_SEAT_BAND,  # Sec2: T024 seat
    GEAR_SEAT_BAND,  # Sec3: T018 seat
    RUNNING_DIA_BAND,  # Sec4: T012 + T006 seats + tip journal
)
# The cone gears each section carries (U40 S1), index-aligned with
# SECTION_DIA_BANDS.  The 64T crank-drive gear also rides Sec1.
SECTION_CONE_GEAR_TEETH: tuple[tuple[int, ...], ...] = (
    (),
    tuple(range(30, 121, 6)),
    (24,),
    (18,),
    (6, 12),
)
