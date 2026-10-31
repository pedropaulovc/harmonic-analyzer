"""Diameter and across-flat bands of the cone gear shaft's lands (MHA-DT-04) and
the gears on them.

The shaft spec applies these bands to its model dimensions; the cone gears
derive their bores from them.  They live here, not in
``cone_gear_shaft_spec``, so the gear family reads the bands without importing
the shaft's finish, GD&T and installation data: an unrelated shaft-spec edit
does not re-key every cone gear (Main ruling, 2026-09-25).
"""

from __future__ import annotations

import math

import _config
from _package_units import drawing_unit
from _printed_tolerance import edge_break_chamfer_mm, printed_band_mm, printed_deviations
from gear_seat_fit import seat_bore_band
from _fit_shaft_h import SHAFT_H

# #290: the shaft sheet's unit (its registry row's drawing_unit); every land
# and across-flat below prints, and is judged, in it.
UNIT = drawing_unit("parts/dt-cone-gear-shaft", _config.parts("dt-cone-gear-shaft"))

# Diameter bands, one NAMED class per land, applied to the model dimension
# by build_dt_cone_gear_shaft -- never "+0.00/-0.02" typed as sheet callout text.
#
# The pivot journal RUNS and keeps the shared ground-shaft h band. The
# terminal land keeps that class too; only its size changes. Both small gears
# and the custom MHA-DT-VN-54 collar read the same terminal diameter below.
# Historical U40 used 1/16 in; the cutter-native 48DP redesign uses a .031 in
# land so the current printed floor MINs retain the user's T006/T012 web guards.
RUNNING_DIA_BAND = SHAFT_H
# GEAR_SEAT_BAND (U27, 2026-09-23): the three intermediate lands only carry
# gears, slid on against the stack (gear_seat_fit).  The upper limit stays at
# nominal, so every gear still passes down its land to its station; the
# -.0020 in lower limit holds the gear within about .002 in radially with its
# bore band -- a small fraction of the ~0.51 mm module, so mesh runout does
# not suffer.  2.5x the h band, which a micrometer holds on a manual lathe.
# Spec-local on purpose: _fit_shaft_h is imported by every ground-shaft
# h-band user.
GEAR_SEAT_BAND = (0.0, -0.0508)
SECTION_DIA_BANDS: tuple[tuple[float, float], ...] = (
    RUNNING_DIA_BAND,  # Sec0: pivot journal
    GEAR_SEAT_BAND,  # Sec1: T030-T120 seats
    GEAR_SEAT_BAND,  # Sec2: T024 seat
    GEAR_SEAT_BAND,  # Sec3: T018 seat
    RUNNING_DIA_BAND,  # Sec4: T012 + T006 seats + MHA-DT-VN-54 stack collar
)
# Shared displayed precision: native drawing and physical-limit consumers
# read the same per-section table; no unrounded-nominal acceptance mapping.
# Inch places: four on every land and across-flat, the places their
# .0008/.0020/.0004 in bands need (.4825, .3750, .3450, .0310, .0170).
LAND_DIA_PLACES = (4, 4, 4, 4, 4)
LAND_AF_PLACES = (None, 4, 4, 4, 4)


def _printed_mm(native_mm: float, places: int) -> float:
    """The number the shaft sheet prints for ``native_mm`` at ``places``, in mm."""
    return native_mm + printed_deviations(native_mm, places, (0.0, 0.0), unit=UNIT)[0]


def land_finished_dia_limits_mm(native_diameter_mm: float, section: int) -> tuple[float, float]:
    """Absolute PRINTED (MIN,MAX), with the retained named land size band."""
    nominal = _printed_mm(native_diameter_mm, LAND_DIA_PLACES[section])
    upper, lower = SECTION_DIA_BANDS[section]
    return nominal+lower, nominal+upper



# One actual terminal-size reader, independent of gear/collar/shaft specs.
# The gear owner checks this against its current cutter-owned floor limits;
# importing a floor here would create a shaft -> gear -> shaft cycle.
MM_PER_IN = 25.4
# F4 (#290): the turned terminal land is .031 in, on the .001 grid; the T006
# and T012 bores take the .0320 micro reamer over it (gear_seat_fit).
TERMINAL_DIA_MM = 0.7874  # .031
TERMINAL_DIA_IN = TERMINAL_DIA_MM / MM_PER_IN
# Manufacturing limits follow the ACTUAL displayed size, not hidden model
# digits.
TERMINAL_DIA_PLACES = LAND_DIA_PLACES[4]
TERMINAL_PRINTED_DIA_MM = _printed_mm(TERMINAL_DIA_MM, TERMINAL_DIA_PLACES)
TERMINAL_FINISHED_DIA_LIMITS_MM = land_finished_dia_limits_mm(TERMINAL_DIA_MM, 4)
# The terminal D-flat: the T006/T012 D-bores are cut to this across-flat and
# the MHA-DT-VN-54 collar's stock set screw bears on it. Its governing limit is
# round guidance, checked at the end of this module: at the deepest printed
# flat on the largest printed land the round must still wrap past the axis.
# The collar's screw landing on the flat is gated by dt_vn_cone_tip_collar_spec.
FLAT_AF_BAND = (0.0, -0.01016)  # 0/-.0004 in
TERMINAL_FLAT_AF_MM = 0.4318  # .017
# The flat's torque corners: the title block's R.010 would leave the flat
# face about +/-.005 wide on this .031 land, so the shaft sheet prints its
# own MAX; the collar screw landing books it.
TERMINAL_FLAT_EDGE_BREAK_MAX = 0.0254  # .001
# Collar geometry the shaft spec reads, so the collar's width, nose and tap
# station cannot fork between the two parts.
# Single coupled owned-geometry delta: move the large collar material, tip
# and pivot together without changing the gear stations or any retained band.
# Selected .50-mm coupled shift: parent-authorized full-P1 engineering DESIGN
# covered all 2400 closed material-pair cells. Not a stock/native qualification
# or a global minimum outside the released [.50,1.00]-mm candidate domain.
TIP_COLLAR_BODY_NORTH_SHIFT_MM = 0.50
TIP_COLLAR_WIDTH_MM = 11.0 + TIP_COLLAR_BODY_NORTH_SHIFT_MM
# The collar's width, nose and tap station print at the title block's .XXX
# (+/-0.13, ordinary lathe facing and spotting): at .XX the stock screw's
# tapped hole leaves less than the collar's 2.0 wall to its faces.
TIP_COLLAR_AXIAL_PLACES = 3
TIP_COLLAR_WIDTH_BAND_MM = printed_band_mm(TIP_COLLAR_AXIAL_PLACES)
TIP_COLLAR_NOSE_LENGTH_MM = 3.0 + TIP_COLLAR_BODY_NORTH_SHIFT_MM
TIP_COLLAR_TAP_STATION_MM = (TIP_COLLAR_NOSE_LENGTH_MM + TIP_COLLAR_WIDTH_MM) / 2.0
TIP_COLLAR_FREE_EDGE_BREAK_MAX_MM = edge_break_chamfer_mm()  # title-block edge break
_COLLAR_BORE_BAND = seat_bore_band(RUNNING_DIA_BAND)
TIP_COLLAR_MAX_RADIAL_FLOAT_MM = (_COLLAR_BORE_BAND[0] - RUNNING_DIA_BAND[1]) / 2.0
TIP_COLLAR_MIN_RADIAL_FLOAT_MM = (_COLLAR_BORE_BAND[1] - RUNNING_DIA_BAND[0]) / 2.0
TIP_COLLAR_MIN_CONTACT_SPAN_MM = (
    TIP_COLLAR_WIDTH_MM - TIP_COLLAR_WIDTH_BAND_MM
    - 2.0 * TIP_COLLAR_FREE_EDGE_BREAK_MAX_MM
)
# The most the collar can cock on its journal: its whole diametral clearance
# over its shortest bearing length.
TIP_COLLAR_INSTALLED_COCK_ANGLE_RAD = math.atan(
    2.0 * TIP_COLLAR_MAX_RADIAL_FLOAT_MM / TIP_COLLAR_MIN_CONTACT_SPAN_MM
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
# channels and the 64T share. Intermediate flats are about 8% of the land
# diameter deep. The terminal flat is the deep D above, held by round
# guidance. Across-flat is the flat-to-opposite-round size a
# micrometer reads. Index-aligned with SECTION_DIA_BANDS; Sec0 has no flat.
SECTION_FLAT_AF: tuple[float | None, ...] = (
    None,  # Sec0: pivot journal
    8.763,  # Sec1: .345 on the 3/8 land, .030 deep
    5.842,  # Sec2: .230 on the 1/4 land, .020 deep
    2.921,  # Sec3: .115 on the 1/8 land, .010 deep
    TERMINAL_FLAT_AF_MM,  # Sec4: deep D held by round guidance, same named AF band
)


def land_finished_af_limits_mm(section: int) -> tuple[float, float]:
    """Absolute PRINTED (MIN,MAX) of a real D-flat; journal has no AF."""
    native = SECTION_FLAT_AF[section]
    places = LAND_AF_PLACES[section]
    if native is None or places is None:
        raise ValueError("round pivot journal has no finished across-flat limits")
    nominal = _printed_mm(native, places)
    return nominal+FLAT_AF_BAND[1], nominal+FLAT_AF_BAND[0]


TERMINAL_FINISHED_AF_LIMITS_MM = land_finished_af_limits_mm(4)
# Round guidance: the flat's least offset from the axis (deepest flat on the
# largest land) must stay positive, so the round keeps more than 180 degrees.
TERMINAL_FLAT_OFFSET_MIN_MM = (
    TERMINAL_FINISHED_AF_LIMITS_MM[0] - TERMINAL_FINISHED_DIA_LIMITS_MM[1] / 2.0
)
if TERMINAL_FLAT_OFFSET_MIN_MM <= 0.0:
    raise AssertionError("terminal D-flat cuts past the axis: the round loses its guidance")
# The flat's narrowest face: shallowest flat on the smallest land.
TERMINAL_FLAT_OFFSET_MAX_MM = (
    TERMINAL_FINISHED_AF_LIMITS_MM[1] - TERMINAL_FINISHED_DIA_LIMITS_MM[0] / 2.0
)
TERMINAL_HALF_CHORD_MIN_MM = math.sqrt(
    (TERMINAL_FINISHED_DIA_LIMITS_MM[0] / 2.0) ** 2 - TERMINAL_FLAT_OFFSET_MAX_MM**2
)
