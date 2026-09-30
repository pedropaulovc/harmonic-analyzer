"""Diameter and across-flat bands of the cone gear shaft's lands (MHA-014) and
the gears on them.

The shaft spec applies these bands to its model dimensions; the cone gears
derive their bores from them.  They live here, not in
``cone_gear_shaft_spec``, so the gear family reads the bands without importing
the shaft's finish, GD&T and installation data: an unrelated shaft-spec edit
does not re-key every cone gear (Main ruling, 2026-09-25).
"""

from __future__ import annotations

from _fit_limits import SHAFT_H

# Diameter bands, one NAMED class per land, applied to the model dimension
# by build_cone_gear_shaft -- never "+0.00/-0.02" typed as sheet callout text.
#
# The Ø12.231 pivot journal RUNS, so it keeps the shared ground-shaft h band:
# it turns in the pivot post's Ø12.2808 bore (0.05 nominal clearance).  The
# Ø1.588 tip land keeps the same h band: it carries the T012 and T006 seats
# and, flatted through to the tip, the MHA-096 set-screw collar, whose stock
# 1/16 in bore (cone_tip_collar_spec.BORE_DIA) slips over it.
RUNNING_DIA_BAND = SHAFT_H
# GEAR_SEAT_BAND (U27, 2026-09-23): the three intermediate lands only carry
# gears, slid on against the stack (gear_seat_fit).  The upper limit stays at
# nominal, so every gear still passes down its land to its station; the -0.05
# lower limit holds the gear within 0.05 radially with its bore band -- a
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
    RUNNING_DIA_BAND,  # Sec4: T012 + T006 seats + MHA-096 stack collar
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

# D-flats (user ruling 2026-09-28): every gear land carries one flat, milled
# full length at the same clock (the shaft's local +X), and every gear on it
# has a matching D-bore, so the flats carry the one angular datum all twenty
# channels and the 64T share.  Each flat is about 8% of its land's diameter
# deep (user ruling, "~8% D"), sized so its across-flat -- flat to the
# opposite side of the land, the size a micrometer reads -- prints exactly at
# three places.  Index-aligned with SECTION_DIA_BANDS; the pivot journal
# (Sec0) has no flat.
SECTION_FLAT_AF: tuple[float | None, ...] = (
    None,  # Sec0: pivot journal
    8.763,  # Sec1: Ø9.525, 0.762 deep
    5.842,  # Sec2: Ø6.35, 0.508 deep
    2.921,  # Sec3: Ø3.175, 0.254 deep
    1.460,  # Sec4: Ø1.5875, 0.1275 deep
)
# The land's across-flat band ("interchangeable tight", user ruling
# 2026-09-28): the bores take theirs from it through
# gear_seat_fit.flat_bore_af_band.
FLAT_AF_BAND = (0.000, -0.010)
