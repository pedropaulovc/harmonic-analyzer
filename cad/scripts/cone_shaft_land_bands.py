"""Diameter and across-flat bands of the cone gear shaft's lands (MHA-DT-004) and
the gears on them.

The shaft spec applies these bands to its model dimensions; the cone gears
derive their bores from them.  They live here, not in
``cone_gear_shaft_spec``, so the gear family reads the bands without importing
the shaft's finish, GD&T and installation data: an unrelated shaft-spec edit
does not re-key every cone gear (Main ruling, 2026-09-25).
"""

from __future__ import annotations

import math

from _printed_tolerance import printed_band_mm
from gear_seat_fit import seat_bore_band
from _fit_limits import SHAFT_H

# Diameter bands, one NAMED class per land, applied to the model dimension
# by build_dt_cone_gear_shaft -- never "+0.00/-0.02" typed as sheet callout text.
#
# The pivot journal RUNS and keeps the shared ground-shaft h band. The
# terminal land keeps that class too; only its size changes. Both small gears
# and the custom MHA-VN-016 collar read the same terminal diameter below.
# Historical U40 used 1/16 in; the cutter-native 48DP redesign uses 1/32 in
# so the current printed floor MINs retain the user's T006/T012 web guards.
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
    RUNNING_DIA_BAND,  # Sec4: T012 + T006 seats + MHA-VN-016 stack collar
)
# Shared displayed precision: native drawing and physical-limit consumers
# read the same per-section table; no unrounded-nominal acceptance mapping.
LAND_DIA_PLACES = (3, 3, 3, 3, 3)
LAND_AF_PLACES = (None, 3, 3, 3, 3)


def land_finished_dia_limits_mm(native_diameter_mm: float, section: int) -> tuple[float, float]:
    """Absolute PRINTED (MIN,MAX), with the retained named land size band."""
    nominal = round(native_diameter_mm, LAND_DIA_PLACES[section])
    upper, lower = SECTION_DIA_BANDS[section]
    return nominal+lower, nominal+upper



# One actual terminal-size reader, independent of gear/collar/shaft specs.
# The gear owner checks this against its current cutter-owned floor limits;
# importing a floor here would create a shaft -> gear -> shaft cycle.
MM_PER_IN = 25.4
TERMINAL_DIA_IN = 1.0 / 32.0
TERMINAL_DIA_MM = TERMINAL_DIA_IN * MM_PER_IN
# Manufacturing limits follow the ACTUAL displayed size, not hidden model
# digits. Exact native 1/32 representation is retained separately above.
TERMINAL_DIA_PLACES = LAND_DIA_PLACES[4]
TERMINAL_PRINTED_DIA_MM = round(TERMINAL_DIA_MM, TERMINAL_DIA_PLACES)
TERMINAL_FINISHED_DIA_LIMITS_MM = land_finished_dia_limits_mm(TERMINAL_DIA_MM, 4)
# Retention requirements live with the land, not in the collar consumer:
# the terminal D-flat must accommodate the real ground dog and its complete
# fit/position budget. Intermediate flats retain the historical ~8% depth.
FLAT_AF_BAND = (0.000, -0.010)
TIP_SCREW_MAJOR_DIA_MM = 0.086 * MM_PER_IN
TIP_SCREW_PITCH_MM = MM_PER_IN / 56.0
TIP_SCREW_DOG_DIA_MM = 0.20
TIP_SCREW_DOG_DIA_BAND = (0.01, -0.01)
TIP_SCREW_DOG_LENGTH_MM = 1.20
TIP_SCREW_DOG_TOTAL_RUNOUT_MM = 0.02
TIP_SCREW_DOG_ENVELOPE_RADIUS_MM = (
    TIP_SCREW_DOG_DIA_MM + TIP_SCREW_DOG_DIA_BAND[0]
    + TIP_SCREW_DOG_TOTAL_RUNOUT_MM
) / 2.0
TIP_SCREW_POSITION_DIA_MM = 0.05
TIP_SCREW_REQUIRED_FULL_ENGAGEMENT_MM = 1.5 * TIP_SCREW_MAJOR_DIA_MM
# ASME B1.1 #2-56 pitch-diameter limits: stock external 3A MIN .0728 in,
# receiver internal 2B MAX .0772 in (BBI thread details / Amesweb UNC chart).
TIP_SCREW_THREAD_RADIAL_PLAY_MM = (0.0772 - 0.0728) * MM_PER_IN / 2.0
# Main ruling E: the terminal torque corners need this functional MAX for
# whole-dog contact. It consumes the former 0.020 side reserve ONCE.
TERMINAL_FLAT_EDGE_BREAK_MAX = 0.020
# Collar geometry governing the loaded bore/contact span; the collar spec
# consumes these readers so the terminal retention law cannot fork its width.
# Single coupled owned-geometry delta: move the large collar material, tip
# and pivot together without changing the gear stations or any retained band.
# Selected .50-mm coupled shift: parent-authorized full-P1 engineering DESIGN
# covered all 2400 closed material-pair cells. Not a stock/native qualification
# or a global minimum outside the released [.50,1.00]-mm candidate domain.
TIP_COLLAR_BODY_NORTH_SHIFT_MM = 0.50
TIP_COLLAR_WIDTH_MM = 11.0 + TIP_COLLAR_BODY_NORTH_SHIFT_MM
TIP_COLLAR_WIDTH_BAND_MM = printed_band_mm(2)
TIP_COLLAR_NOSE_LENGTH_MM = 3.0 + TIP_COLLAR_BODY_NORTH_SHIFT_MM
TIP_COLLAR_TAP_STATION_MM = (TIP_COLLAR_NOSE_LENGTH_MM + TIP_COLLAR_WIDTH_MM) / 2.0
TIP_COLLAR_FREE_EDGE_BREAK_MAX_MM = 0.25
# Conservative AF design radius retains the original exact-native h lower
# corner as well as printed stock; it is NOT the actual stock acceptance
# minimum. Do not spend the display-rounding difference to lift the D-flat.
_TERMINAL_MIN_R = (TERMINAL_DIA_MM + RUNNING_DIA_BAND[1]) / 2.0
_COLLAR_BORE_UPPER = seat_bore_band(RUNNING_DIA_BAND)[0]
TIP_COLLAR_MAX_RADIAL_FLOAT_MM = (
    _COLLAR_BORE_UPPER - RUNNING_DIA_BAND[1]
) / 2.0
TIP_SCREW_MAX_AXIS_ANGLE_RAD = math.atan(
    2.0 * (TIP_SCREW_THREAD_RADIAL_PLAY_MM + TIP_SCREW_POSITION_DIA_MM / 2.0)
    / TIP_SCREW_REQUIRED_FULL_ENGAGEMENT_MM
)
TIP_SCREW_MAJOR_AXIAL_PROJECTION_MM = (
    TIP_SCREW_MAJOR_DIA_MM / 2.0 * math.sin(TIP_SCREW_MAX_AXIS_ANGLE_RAD)
)
TIP_SCREW_DOG_AXIAL_PROJECTION_MM = (
    TIP_SCREW_DOG_ENVELOPE_RADIUS_MM * math.sin(TIP_SCREW_MAX_AXIS_ANGLE_RAD)
)
# Projection onto the shaft's flat is assigned below, after the installed
# two-end bore-contact cock has been derived. Stock-in-collar projections
# above remain relative to the receiver's own axis.
# At either end of the qualified full engagement, the screw axis may occupy
# opposite extremes of BOTH the 3A/2B fit and the receiver position zone.
# Extrapolate that maximum slope to the dog, not just the nominal hole centre.
TIP_SCREW_FREE_PROJECTION_MM = (
    TIP_SCREW_DOG_LENGTH_MM + printed_band_mm(2) + TIP_SCREW_PITCH_MM
    + FLAT_AF_BAND[0] - FLAT_AF_BAND[1]
    + (RUNNING_DIA_BAND[0] - RUNNING_DIA_BAND[1]) / 2.0
    + 2.0 * TIP_COLLAR_MAX_RADIAL_FLOAT_MM
    + TIP_SCREW_MAJOR_AXIAL_PROJECTION_MM + TIP_SCREW_DOG_AXIAL_PROJECTION_MM
)
TIP_SCREW_DOG_AXIS_OFFSET_MM = (
    TIP_SCREW_THREAD_RADIAL_PLAY_MM + TIP_SCREW_POSITION_DIA_MM / 2.0
) * (1.0 + 2.0 * TIP_SCREW_FREE_PROJECTION_MM / TIP_SCREW_REQUIRED_FULL_ENGAGEMENT_MM)
TIP_COLLAR_MIN_RADIAL_FLOAT_MM = (
    seat_bore_band(RUNNING_DIA_BAND)[1] - RUNNING_DIA_BAND[0]
) / 2.0
TIP_COLLAR_MIN_CONTACT_SPAN_MM = (
    TIP_COLLAR_WIDTH_MM - TIP_COLLAR_WIDTH_BAND_MM
    - 2.0 * TIP_COLLAR_FREE_EDGE_BREAK_MAX_MM
)
_DOG_CONTACT_AXIAL_ENVELOPE_MM = (
    TIP_SCREW_POSITION_DIA_MM / 2.0
    + TIP_SCREW_FREE_PROJECTION_MM * math.sin(TIP_SCREW_MAX_AXIS_ANGLE_RAD)
    + TIP_SCREW_DOG_ENVELOPE_RADIUS_MM / math.cos(TIP_SCREW_MAX_AXIS_ANGLE_RAD)
)
TIP_COLLAR_MIN_REACTION_ARM_MM = min(
    TIP_COLLAR_TAP_STATION_MM - TIP_COLLAR_FREE_EDGE_BREAK_MAX_MM,
    TIP_COLLAR_WIDTH_MM - TIP_COLLAR_WIDTH_BAND_MM
    - TIP_COLLAR_FREE_EDGE_BREAK_MAX_MM - TIP_COLLAR_TAP_STATION_MM,
) - _DOG_CONTACT_AXIAL_ENVELOPE_MM
# Loaded, the dog force points toward the D's retained round back arc.
# Its pressure centroid is inside both bearing ends. The maximum axial
# force's moment is too small to reverse either end reaction. The loose D
# journal's much larger free offset is NOT the installed fit law.
_LOADED_AXIS_ANGLE_UPPER_RAD = TIP_SCREW_MAX_AXIS_ANGLE_RAD + math.atan(
    2.0 * TIP_COLLAR_MAX_RADIAL_FLOAT_MM / TIP_COLLAR_MIN_CONTACT_SPAN_MM
)
# Axial clamp force is reacted on the BACK arc, not at the shaft centre.
# Its lever is the dog-to-back chord (bounded by the WHOLE diameter), not r.
# Use the diameter ceiling before deriving AF to avoid a circular AF bound.
_LOADED_FORCE_COUPLE_ARM_MM = (
    TERMINAL_FINISHED_DIA_LIMITS_MM[1] * math.tan(_LOADED_AXIS_ANGLE_UPPER_RAD)
)
if not 0.0 < _LOADED_FORCE_COUPLE_ARM_MM < TIP_COLLAR_MIN_REACTION_ARM_MM:
    raise AssertionError("dog force cannot positively seat both retained back-arc bearing ends")
TIP_COLLAR_BACK_ARC_REACTION_ANGLE_RAD = (
    _LOADED_AXIS_ANGLE_UPPER_RAD
    + math.asin(_LOADED_FORCE_COUPLE_ARM_MM / TIP_COLLAR_MIN_REACTION_ARM_MM)
)
if TIP_COLLAR_BACK_ARC_REACTION_ANGLE_RAD >= math.pi / 2.0:
    raise AssertionError("loaded collar reaction leaves the retained round back arc")
TIP_COLLAR_INSTALLED_COCK_ANGLE_RAD = math.atan(
    (
        TIP_COLLAR_MAX_RADIAL_FLOAT_MM - TIP_COLLAR_MIN_RADIAL_FLOAT_MM
        + 2.0 * TIP_COLLAR_MAX_RADIAL_FLOAT_MM * math.sin(TIP_COLLAR_BACK_ARC_REACTION_ANGLE_RAD)
    ) / TIP_COLLAR_MIN_CONTACT_SPAN_MM
)
TIP_SCREW_TO_JOURNAL_MAX_AXIS_ANGLE_RAD = (
    TIP_SCREW_MAX_AXIS_ANGLE_RAD + TIP_COLLAR_INSTALLED_COCK_ANGLE_RAD
)
TIP_SCREW_DOG_PROJECTED_RADIUS_MM = (
    TIP_SCREW_DOG_ENVELOPE_RADIUS_MM / math.cos(TIP_SCREW_TO_JOURNAL_MAX_AXIS_ANGLE_RAD)
)
TERMINAL_REQUIRED_HALF_CHORD_MM = (
    TIP_SCREW_DOG_PROJECTED_RADIUS_MM
    + TIP_COLLAR_MAX_RADIAL_FLOAT_MM + TIP_SCREW_DOG_AXIS_OFFSET_MM
    + TERMINAL_FLAT_EDGE_BREAK_MAX
)
if TERMINAL_REQUIRED_HALF_CHORD_MM >= _TERMINAL_MIN_R:
    raise AssertionError("terminal journal cannot contain the complete dog/fit budget")
_TERMINAL_AF_CAP = _TERMINAL_MIN_R + math.sqrt(
    _TERMINAL_MIN_R**2 - TERMINAL_REQUIRED_HALF_CHORD_MM**2
)
# Round DOWN to a shop-readable hundredth; native AF prints three places and
# keeps the existing 0/-0.010 fit. This is derived, not a frozen shallow-flat ratio.
TERMINAL_FLAT_AF_MM = math.floor(_TERMINAL_AF_CAP * 100.0) / 100.0
TERMINAL_FLAT_OFFSET_MAX_MM = TERMINAL_FLAT_AF_MM + FLAT_AF_BAND[0] - _TERMINAL_MIN_R
TERMINAL_HALF_CHORD_MIN_MM = math.sqrt(
    _TERMINAL_MIN_R**2 - TERMINAL_FLAT_OFFSET_MAX_MM**2
)
if not 0.0 < TERMINAL_FLAT_OFFSET_MAX_MM < _TERMINAL_MIN_R:
    raise AssertionError("terminal D section must retain its axis and >180-degree round guidance")
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
# channels and the 64T share. Intermediate flats are about 8% of the land
# diameter deep. The terminal flat instead derives from the complete dog
# retention budget above. Across-flat is the flat-to-opposite-round size a
# micrometer reads. Index-aligned with SECTION_DIA_BANDS; Sec0 has no flat.
SECTION_FLAT_AF: tuple[float | None, ...] = (
    None,  # Sec0: pivot journal
    8.763,  # Sec1: Ø9.525, 0.762 deep
    5.842,  # Sec2: Ø6.35, 0.508 deep
    2.921,  # Sec3: Ø3.175, 0.254 deep
    TERMINAL_FLAT_AF_MM,  # Sec4: complete dog retention budget, same named AF band
)


def land_finished_af_limits_mm(section: int) -> tuple[float, float]:
    """Absolute PRINTED (MIN,MAX) of a real D-flat; journal has no AF."""
    native = SECTION_FLAT_AF[section]
    places = LAND_AF_PLACES[section]
    if native is None or places is None:
        raise ValueError("round pivot journal has no finished across-flat limits")
    nominal = round(native, places)
    return nominal+FLAT_AF_BAND[1], nominal+FLAT_AF_BAND[0]


TERMINAL_FINISHED_AF_LIMITS_MM = land_finished_af_limits_mm(4)
