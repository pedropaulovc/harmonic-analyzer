r"""Crankshaft manufacturing contract.

The v36 MHA-DT-05 bore carries integral running lands again; the pinion sits
SEAT_FEELER_MM off its north boss face. All axial stations are measured from
the dome root in the model and printed from the far end.  Behind the crank
hub an integral
collar carries the removable sprocket MHA-PD-09's seat and its two pressed
drive pins (ch. 23); its rear face bears on the post boss's south face (owner
ruling D1, 2026-10-15: no crank-seat washer).
"""

from __future__ import annotations

import _config
import cone_line
from _hole_spec import HoleSpec, blind_cut_dia_mm, drill_process
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import (
    drilled_oversize_mm,
    edge_break_chamfer_mm,
    edge_break_radius_mm,
    printed_band_mm,
    printed_deviations,
)
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from dt_cone_pivot_post_spec import CRANK_BORE_DIA as JOURNAL_BORE_DIA
from dt_cone_pivot_post_spec import RUNNING_BORE_BAND as JOURNAL_BORE_BAND
import dt_cone_pivot_post_spec
import dt_crank_pinion_spec
from dt_crank_drive_gear_spec import inch_text
import dt_vn_crank_seat_drive_pin_spec
import _sprocket_seat_geometry as seat_geometry
from dt_crank_hub_geometry import (
    FIDUCIAL_MODEL_DEPTH,  # noqa: F401 -- re-exported to the drawing contract
    FIDUCIAL_MODEL_DIA,  # noqa: F401 -- re-exported to the drawing contract
    HUB_LENGTH,
    HUB_LENGTH_BAND,
    SERVICE_PIN_STATION,
    SHAFT_DIA,
    SHAFT_DIA_BAND,
    SHAFT_DOME_HEIGHT,  # noqa: F401 -- re-exported to the drawing contract
    SHAFT_FIDUCIAL_RADIUS,  # noqa: F401 -- re-exported to the drawing contract
)


# #290: the registry row's drawing_unit (in) is this sheet's unit; the bands,
# places and callout text below are authored for it.
UNIT = drawing_unit("parts/dt-crankshaft", _config.parts("dt-crankshaft"))
# The post's own sheet unit, read from its row so this stays right whichever
# of the two conversions lands first (#290).
POST_UNIT = drawing_unit("parts/dt-cone-pivot-post", _config.parts("dt-cone-pivot-post"))
_floor = dt_crank_pinion_spec.floor_to_places
_ceil = dt_crank_pinion_spec.ceil_to_places
_step = dt_crank_pinion_spec.print_step

# The restored v36 post's north boss face, measured from the shifted dome root.
# Keep this independent of the post's rebuild closure; assembly checks the mate.
POST_BORE_END = cone_line.cone_station(cone_line.POST_STATION)[2] + 183.0 + 21.3753
SEAT_PINION = POST_BORE_END + dt_crank_pinion_spec.SEAT_FEELER_MM
if SEAT_PINION <= POST_BORE_END:
    raise AssertionError("the 16T seat must clear the restored post boss north face")
# Owner ruling D1 (2026-10-15): no crank-seat washer.  The collar's rear face
# is pulled hard onto the post boss's south face, the 16T is set on its feeler
# off the north face and only then is its pin match-drilled at boss
# mid-length, so the end play is the feeler.  The 16T's place on the shaft is
# no longer set by the shaft end, and the end is left proud of its north face
# (SHAFT_END_PROUD_RANGE below), not faced at assembly.
POST_BOSS_SOUTH = POST_BORE_END - dt_cone_pivot_post_spec.CRANK_BOSS_LENGTH
# The dome-side Depth band: the crank hub is set flush with the dome root, and
# the hub-air and drive-pin stacks (SEAT_COLLAR_BAND) are proved at this
# +.000/-.016; the title block's .XX +/-.01 alone would leave the shaft long.
SHAFT_LENGTH_SHORT_MM = 0.4064
SHAFT_LENGTH_BAND = (0.00, -SHAFT_LENGTH_SHORT_MM)

# The sprocket seat face's local station (28.7 behind the crank face, machine
# -183.0 as the drive train's CRANK_FACE_Z, is SEAT_FACE_Z -154.3, which
# build_dt_drive_train_assembly asserts from both sides), and the collar from
# it back to the boss's south face, floored to its two-place print so the
# model's rear face stands at most .001 in short of the boss (the fitter
# pulls it hard on).  Both collar faces print from the far end at +/-.004
# (.XXX); the seat face is the chain plane's, not an inch grid value, so its
# far-end station prints rounded and every stack reads it at its printed
# limits.
SEAT_COLLAR = 28.7
COLLAR_STATION_PLACES = 3
COLLAR_STATION_TOL = 0.1016
COLLAR_LENGTH = _floor(
    POST_BOSS_SOUTH - SEAT_COLLAR, COLLAR_STATION_PLACES, UNIT
)  # seat face to rear face, spigot included
COLLAR_REAR = SEAT_COLLAR + COLLAR_LENGTH  # on the post boss's south face
COLLAR_BOSS_AIR = POST_BOSS_SOUTH - COLLAR_REAR
if not -1e-9 <= COLLAR_BOSS_AIR < _step(COLLAR_STATION_PLACES, UNIT):
    raise AssertionError(
        f"the collar's rear face stands {COLLAR_BOSS_AIR:.4f} off the post boss"
    )


def shaft_end_proud_links(shaft_length: float) -> dict[str, tuple[float, float, float]]:
    """The shaft end's stand past the 16T's north face, collar on the boss and
    16T on its feeler: the printed CollarRearStation (far end to the collar's
    rear face) less the post's crank boss, the feeler and the 16T's overall
    length.  Each link is ``(nominal, lower, upper)`` at its printed limits."""
    station = shaft_length - COLLAR_REAR
    boss = dt_cone_pivot_post_spec.CRANK_BOSS_LENGTH
    overall = dt_crank_pinion_spec.OVERALL_LENGTH
    station_lower, station_upper = printed_deviations(
        station, COLLAR_STATION_PLACES, (-COLLAR_STATION_TOL, COLLAR_STATION_TOL),
        unit=UNIT,
    )
    boss_lower, boss_upper = printed_deviations(
        boss, dt_cone_pivot_post_spec.DRAWING_PRECISION_BY_NAME["CrankBossLen"],
        unit=POST_UNIT,
    )
    overall_lower, overall_upper = printed_deviations(
        overall, dt_crank_pinion_spec.OVERALL_LENGTH_PLACES,
        unit=dt_crank_pinion_spec.UNIT,
    )
    return {
        "MHA-DT-11 CollarRearStation": (station, station_lower, station_upper),
        "MHA-DT-05 crank boss length": (-boss, -boss_upper, -boss_lower),
        "MHA-DT-10 seat feeler": (-dt_crank_pinion_spec.SEAT_FEELER_MM, 0.0, 0.0),
        "MHA-DT-10 overall length": (-overall, -overall_upper, -overall_lower),
    }


def shaft_end_proud_range(shaft_length: float) -> tuple[float, float]:
    """``(least, most)`` the shaft end stands past the 16T's north face."""
    links = shaft_end_proud_links(shaft_length).values()
    nominal = sum(link[0] for link in links)
    return (
        nominal + sum(link[1] for link in links),
        nominal + sum(link[2] for link in links),
    )


# The shortest one-place shaft whose end is never inside the 16T: long enough
# that the pin always has shaft past it (W15 below), and left proud.
_SHAFT_PRINT_STEP = _step(dt_crank_pinion_spec.SHAFT_LENGTH_PLACES, UNIT)
_PAST_COLLAR = list(shaft_end_proud_links(COLLAR_REAR).values())[1:]
SHAFT_LENGTH = _ceil(
    COLLAR_REAR
    + COLLAR_STATION_TOL
    - sum(nominal + lower for nominal, lower, _upper in _PAST_COLLAR),
    dt_crank_pinion_spec.SHAFT_LENGTH_PLACES,
    UNIT,
)
SHAFT_END_PROUD_LINKS = shaft_end_proud_links(SHAFT_LENGTH)
SHAFT_END_PROUD_RANGE = shaft_end_proud_range(SHAFT_LENGTH)
SHAFT_END_PROUD_NOMINAL = sum(link[0] for link in SHAFT_END_PROUD_LINKS.values())
if SHAFT_END_PROUD_RANGE[0] < -1e-9:
    raise AssertionError(
        f"the crankshaft end can sit {-SHAFT_END_PROUD_RANGE[0]:.3f} inside the 16T"
    )
if shaft_end_proud_range(SHAFT_LENGTH - _SHAFT_PRINT_STEP)[0] >= -1e-9:
    raise AssertionError("a shaft one print step shorter still stays proud: not the shortest")

# Integral lands run directly in the restored post bore. Derive the journal
# from the named running fit and the bore's published REAM_H7 band.
_RUNNING_CLEARANCE = tuple(_config.fit("shaft_in_bushing")["diametral_clearance_mm"])
JOURNAL_DIA = JOURNAL_BORE_DIA + JOURNAL_BORE_BAND[1] - _RUNNING_CLEARANCE[0]
JOURNAL_DIA_BAND = (
    0.0,
    round(JOURNAL_BORE_DIA + JOURNAL_BORE_BAND[0] - _RUNNING_CLEARANCE[1] - JOURNAL_DIA, 5),
)
JOURNAL_CLEARANCE = JOURNAL_BORE_DIA - JOURNAL_DIA
_JOURNAL_CLEARANCE_LOW = JOURNAL_BORE_BAND[1] - JOURNAL_DIA_BAND[0] + JOURNAL_CLEARANCE
_JOURNAL_CLEARANCE_HIGH = JOURNAL_BORE_BAND[0] - JOURNAL_DIA_BAND[1] + JOURNAL_CLEARANCE
JOURNAL_DIAMETRAL_CLEARANCE_MM = (_JOURNAL_CLEARANCE_LOW, _JOURNAL_CLEARANCE_HIGH)
if not (
    _RUNNING_CLEARANCE[0] - 1e-9
    <= _JOURNAL_CLEARANCE_LOW
    <= _JOURNAL_CLEARANCE_HIGH
    <= _RUNNING_CLEARANCE[1] + 1e-9
):
    raise AssertionError("integral journal and post bore exceed the running-fit clearance band")

# Every axial station prints from the FAR END at two places (.XX +/-.01;
# drawing-guidelines.md rule 11 (turned parts read like the lathe)), and
# each one below is chosen to print EXACTLY, so its printed row IS its limit
# and no rounding of a printed nominal can eat a margin.  Local stations (from
# the dome root, where the features measure) follow from the far end.
STATION_PLACES = 2
STATION_ROW = printed_band_mm(STATION_PLACES, unit=UNIT)  # .01 in


def local_station(far_end_station: float) -> float:
    """Dome-root station of a feature printed ``far_end_station`` from the far end."""
    return SHAFT_LENGTH - far_end_station


# The outboard journal starts a bare Ø.375 land behind the collar's rear
# face, inside the post bore: at print-worst (rear face .004 north, journal
# start a row south) the land still spans the bore mouth's edge break, so the
# collar's inside corner never rides the bore edge and the rear face seats
# flat on the boss.
# The post's own sheet (still millimetre) sets its bore mouth's edge break.
BORE_MOUTH_BREAK_MAX = edge_break_chamfer_mm()
JOURNAL_START = local_station(
    _floor(
        SHAFT_LENGTH
        - (COLLAR_REAR + COLLAR_STATION_TOL + STATION_ROW + BORE_MOUTH_BREAK_MAX),
        STATION_PLACES,
        UNIT,
    )
)

# RULING (b), Main 2026-09-26 (#906): the 16T sits on a Ø.3125 seat (#290;
# was Ø9.0), a step down from the 3/8 in shaft at the far end's side of the
# post bore.  The pinion is
# still set on its feeler and pinned, so the step never locates it; the step
# only has to stay out from under the pinion's nominal seat.  An accepted step
# can print a row north of its nominal, and an inside corner up to the sheet's
# R.010 MAX ceiling (DRAWING_NOTES) stands the pinion's bore edge off it by
# that much more; together they must stay inside the seat gap's north range
# (dt_crank_pinion_spec.SEAT_GAP_MAX_MM).  So the step sits south of the
# seat, not at it.
PINION_SEAT_DIA = dt_crank_pinion_spec.SEAT_DIA
PINION_SEAT_DIA_BAND = SHAFT_DIA_BAND  # the through shaft's turned-fit band
PINION_SEAT_STATION = 22.606  # .89, far end to the step
SEAT_STEP = local_station(PINION_SEAT_STATION)
STEP_CORNER_RADIUS_MAX = edge_break_radius_mm(unit=UNIT)  # R.010, the edge break's size
SEAT_STEP_STANDOFF_WORST = SEAT_STEP + STATION_ROW + STEP_CORNER_RADIUS_MAX - SEAT_PINION
SEAT_GAP_NORTH_RANGE = dt_crank_pinion_spec.SEAT_GAP_MAX_MM - dt_crank_pinion_spec.SEAT_FEELER_MM
if SEAT_STEP_STANDOFF_WORST > SEAT_GAP_NORTH_RANGE + 1e-9:
    raise AssertionError(
        f"Ø{PINION_SEAT_DIA} seat step stands the 16T off {SEAT_STEP_STANDOFF_WORST:.3f} "
        f"at print-worst, past the seat gap's {SEAT_GAP_NORTH_RANGE:.2f} north range"
    )

# Restore the two bearing lands and the relieved middle. Printed stations
# remain baseline dimensions from the faced far end, at the routine .X band.
WEB_TARGET_MM = WALL_TARGET_MM
JOURNAL_INBOARD_STATION = 26.162  # 1.03
JOURNAL_END = local_station(JOURNAL_INBOARD_STATION)
JOURNAL_LENGTH = JOURNAL_END - JOURNAL_START
# Both ends print from the far end, so the web is their printed difference.
STEP_WEB_WORST = JOURNAL_INBOARD_STATION - PINION_SEAT_STATION - 2.0 * STATION_ROW
RELIEF_DIA = 10.414  # .41
RELIEF_DIA_PLACES = 2
# The post bore's south rim and the general edge breaks leave the outboard
# land's real contact short; this relief end stays inset from it on the
# station grid. Outer journal ends, seats and fits are unchanged.
RELIEF_OUTBOARD_STATION = 78.994  # 3.11
RELIEF_INBOARD_STATION = 41.148  # 1.62
RELIEF_START = local_station(RELIEF_OUTBOARD_STATION)
RELIEF_END = local_station(RELIEF_INBOARD_STATION)
RELIEF_LENGTH = RELIEF_END - RELIEF_START
_RELIEF_ROW = printed_band_mm(RELIEF_DIA_PLACES, unit=UNIT)
_OUTBOARD_START_LOWER, _ = printed_deviations(
    SHAFT_LENGTH - JOURNAL_START, STATION_PLACES, unit=UNIT
)
JOURNAL_LAND_L_OVER_D_MIN = 1.0
JOURNAL_LANDS_WORST = (
    SHAFT_LENGTH - JOURNAL_START + _OUTBOARD_START_LOWER
    - RELIEF_OUTBOARD_STATION - STATION_ROW,
    RELIEF_INBOARD_STATION - JOURNAL_INBOARD_STATION - 2.0 * STATION_ROW,
)
# Extreme retained contact stations, not the full post bore or the relieved
# middle. Both stations share the shaft's far-end datum, so its overall-length
# variation cancels from their separation. Used by local mesh and global pose.
JOURNAL_SUPPORT_SPAN_MIN_MM = (
    SHAFT_LENGTH - JOURNAL_START - JOURNAL_INBOARD_STATION - 2.0 * STATION_ROW
)
if STEP_WEB_WORST < WEB_TARGET_MM - 1e-9:
    raise AssertionError("journal-to-pinion-seat web falls below its printed worst-case floor")
if JOURNAL_END + STATION_ROW >= POST_BORE_END:
    raise AssertionError("the journal must stay inside the restored post bore at print-worst")
if not RELIEF_START < RELIEF_END < JOURNAL_END:
    raise AssertionError("the relieved middle must stay within the integral journal lands")
if RELIEF_DIA + _RELIEF_ROW >= JOURNAL_DIA + JOURNAL_DIA_BAND[1]:
    raise AssertionError("relief must remain below the journal at print-worst")
if RELIEF_DIA - _RELIEF_ROW <= SHAFT_DIA + SHAFT_DIA_BAND[0]:
    raise AssertionError("relief must stand proud of the through shaft at print-worst")
if min(JOURNAL_LANDS_WORST) < JOURNAL_LAND_L_OVER_D_MIN * JOURNAL_DIA:
    raise AssertionError("the integral journal lands fall below their printed L/D floor")
# W15 under ruling D1: the shaft end stands proud of the 16T's north face at
# every accepted part set (SHAFT_END_PROUD_RANGE), so the shaft's wall past
# the match-drilled pin is the pinion's own plus the proud length, never less
# (dt_crank_pinion_spec sizes the boss for that wall).  The retention hole is
# laid out at boss middle.
PINION_PIN_STATION_Y = SEAT_PINION + dt_crank_pinion_spec.PIN_STATION
PINION_PIN_EDGE_TO_END_WORST = (
    dt_crank_pinion_spec.PIN_AXIAL_LIGAMENT_WORST + SHAFT_END_PROUD_RANGE[0]
)
if PINION_PIN_EDGE_TO_END_WORST < dt_crank_pinion_spec.PIN_EDGE_MIN_WORST - 1e-9:
    raise AssertionError("W15 pin edge-to-shaft-end wall falls below its print-worst floor")
# MHA-DT-09 hub-to-shaft cross-hole behind the crank arm.
PIN_HOLE_SPEC = HoleSpec("drilled_number", "#9")
PIN_HOLE_HEIGHT = SERVICE_PIN_STATION

# --- ch. 23 crank seat (CONTRACT-crank): the integral collar replaces the
# plain 5-mm T12 band.  Its front is a Ø.689 seat spigot whose face is
# MHA-PD-09's seat, at the shared provider's SEAT_FACE_Z, stepping up to the Ø.81
# collar body, whose rear face bears on the post boss's south face.  The #25
# plates wrapping the T12 pass over the spigot and in front of the body's
# front face: long enough that a bought chain's
# envelope, floated rearmost on the thinnest wheel
# (_sprocket_seat_geometry.chain_reach_rear, 3.59 behind the seat), keeps
# air to the body at the spigot's print-worst length (the drive train asserts
# it, with the radial air for the CAD link and a real ANSI plate).  The seat
# diameter is the interface both shafts share, so the pure provider owns it.
# #290: .689 +.000/-.004 (fit row D2s); the shared provider takes the same
# inch values in the PD batch, so these two read it once that lands.
SPIGOT_DIA = 17.5006  # .689, seat_geometry.SEAT_SPIGOT_DIA
SPIGOT_DIA_BAND = (0.0, -0.1016)  # seat_geometry.SPIGOT_DIA_BAND
# User ruling 2026-09-30: the seat face moved 1.8 forward with the shared
# band and the body's front face stayed put, so the spigot grew.  Owner
# ruling D1 (2026-10-15) deleted the crank-seat washer and ran the body back
# to the post boss: the collar is the seat face to the boss's south face,
# floored to its print so the model's rear face stands under a print step
# short of the boss (the fitter pulls it hard on).
SPIGOT_LENGTH = 5.7912  # .228
COLLAR_DIA = 20.574  # .81
SPIGOT_END = SEAT_COLLAR + SPIGOT_LENGTH  # the body's front face, -148.5
# Two pressed MHA-DT-VN-67 dowels on the wheel's pin circle at its +/-Y holes,
# which the placed shaft (local z = machine -y) carries on local -/+Z.  The
# pins' pressed ends bear on the blind holes' flat floor, so the depth is set
# by the proud length the wheel needs.
if seat_geometry.PIN_HOLE_ANGLES_DEG != (90.0, 270.0):
    raise AssertionError("the drive-pin holes are laid out on local +/-Z only")
DRIVE_PIN_CIRCLE_RADIUS = seat_geometry.PIN_CIRCLE_RADIUS
# #290: each pin located .2756 +/-.0009 from the axis (the PD batch moves the
# shared DRIVE_PIN_OFFSET_TOL to the same value; this reads it once it lands).
DRIVE_PIN_OFFSET_TOL = 0.02286
DRIVE_PIN_OFFSET_PLACES = 4
DRIVE_PIN_HOLE_DIA = seat_geometry.DRIVE_PIN_HOLE_DIA
DRIVE_PIN_DEPTH = dt_vn_crank_seat_drive_pin_spec.PRESS_DEPTH  # 3.95
DRIVE_PIN_FLOOR = SEAT_COLLAR + DRIVE_PIN_DEPTH
if not SEAT_COLLAR < SPIGOT_END < COLLAR_REAR:
    raise AssertionError("the seat spigot must end inside the collar")
if not SEAT_COLLAR < DRIVE_PIN_FLOOR < COLLAR_REAR:
    raise AssertionError("the blind drive-pin holes must end inside the collar")
_PIN_HOLE_OUTER_R = DRIVE_PIN_CIRCLE_RADIUS + DRIVE_PIN_HOLE_DIA / 2.0
if not _PIN_HOLE_OUTER_R < SPIGOT_DIA / 2.0 < COLLAR_DIA / 2.0:
    raise AssertionError("the spigot must enclose the pin holes, inside the body")

# Functional bands (drawing-guidelines.md rule 3 (decimal places carry the tolerance)), each at the places that print it:
# - The two collar faces print from the far end like every station, but at
#   the title block's rows the seat face could come toward the crank and
#   close the contracted air between the hub's rear face and the wheel, and
#   the rear face's station is a link of the shaft end's stand past the 16T
#   (SHAFT_END_PROUD_RANGE).  +/-.004 (COLLAR_STATION_TOL) at .XXX.
# - The spigot diameter is held under nominal, +.000/-.004 at .XXX: over it
#   the ANSI #25 plates wrapping the T12, floated off-centre by
#   WHEEL_SEAT_FLOAT, lose their worst-case radial air; under it the rim to
#   the pin holes thins (DRIVE_PIN_SPIGOT_RIM_WORST).
# - The spigot's length prints from the seat face, not the far end, so the
#   body's front face rides with the wheel and the chain: +/-.002 at .XXX
#   keeps a bought chain's envelope clear of it.
# - The collar body OD is not a seat and meets no mate (machinist review of
#   5a219a81904f): it prints at two places under the title block's .XX band,
#   and the bearing ring it gives the post boss holds at either limit.
# - The MHA-PD-09 holes (PIN_HOLE_DIA) slip over the pins with diametral
#   clearance that absorbs the pin spacing error of BOTH parts; each pin's
#   location band spends half of it here, leaving the wheel the same share.
# - Pressed to the floor, the pin stands PROUD = LENGTH - depth: the depth
#   band plus the dowel's +/-.010 in length grade must keep the tip clear
#   of the crank hub and engaged in the wheel.  +/-.004, printed at the
#   hole callout's places.
SPIGOT_DIA_PLACES = 3
SPIGOT_LENGTH_PLACES = 3
SPIGOT_LENGTH_TOL = 0.0508
# The drive-pin holes print through a native callout on their cut-extrude
# (size and depth stay the model's), not as marked dimensions.  The shared
# 2.38 hole needs four inch places to print its limits truthfully
# (.0937/.0933); a cut-extrude callout takes the sheet's document places, so
# draw_dt_crankshaft opens the sheet at these.
HOLE_CALLOUT_PLACES = 4
DRIVE_PIN_DEPTH_TOL = 0.1016
# The shared hole's (0/-.010) band on the inch grid this sheet prints; the
# mm sheets keep the shared constant.  D14 (#290's final step) converts the
# shared hole and removes this copy.
DRIVE_PIN_HOLE_BAND = (0.0, -0.01016)  # +.0000/-.0004
# Local (dome-root) deviations of the seat face as (upper, lower): a station
# printed from the far end moves by its own printed band (its model value is
# the chain plane's, so it prints rounded) plus the Depth's.  The drive
# train's hub-air stack reads it.
_SEAT_STATION_LOWER, _SEAT_STATION_UPPER = printed_deviations(
    SHAFT_LENGTH - SEAT_COLLAR,
    COLLAR_STATION_PLACES,
    (-COLLAR_STATION_TOL, COLLAR_STATION_TOL),
    unit=UNIT,
)
SEAT_COLLAR_BAND = (
    SHAFT_LENGTH_BAND[0] - _SEAT_STATION_LOWER,
    SHAFT_LENGTH_BAND[1] - _SEAT_STATION_UPPER,
)
_DOWEL_OD = tuple(
    dt_vn_crank_seat_drive_pin_spec.DIA + inch * dt_vn_crank_seat_drive_pin_spec.MM_PER_IN
    for inch in dt_vn_crank_seat_drive_pin_spec.DIA_BAND_IN
)
DRIVE_PIN_PRESS_INTERFERENCE = (
    _DOWEL_OD[0] - (DRIVE_PIN_HOLE_DIA + DRIVE_PIN_HOLE_BAND[0]),
    _DOWEL_OD[1] - (DRIVE_PIN_HOLE_DIA + DRIVE_PIN_HOLE_BAND[1]),
)
if min(DRIVE_PIN_PRESS_INTERFERENCE) <= 0.0:
    raise AssertionError("the drive-pin hole band loses the press at its upper limit")
# A dowel pressed into a blind hole has no way out (drawing-guidelines.md
# rule 16 (design for the cutter)): each drive-pin hole's floor is pierced by
# a #54 knockout drilled through from the collar's rear face, so a 3/64 pin
# punch drives a pin back out of the seat face.  The reamed hole keeps its
# depth, so the pin still bottoms on the annular floor the knockout leaves,
# and the knockout leaves the rear face inside the post boss's bearing ring,
# clear of the bore mouth.
DRIVE_PIN_KNOCKOUT_SPEC = HoleSpec("drilled_number", "#54")
DRIVE_PIN_KNOCKOUT_DIA = blind_cut_dia_mm(DRIVE_PIN_KNOCKOUT_SPEC)  # 1.397
DRIVE_PIN_KNOCKOUT_PROCESS = drill_process(DRIVE_PIN_KNOCKOUT_SPEC)
DRIVE_PIN_KNOCKOUT_LENGTH = COLLAR_REAR - DRIVE_PIN_FLOOR
_KNOCKOUT_DIA_MAX = DRIVE_PIN_KNOCKOUT_DIA + drilled_oversize_mm(unit=UNIT)
DRIVE_PIN_FLOOR_LAND_WORST = (
    DRIVE_PIN_HOLE_DIA + DRIVE_PIN_HOLE_BAND[1] - _KNOCKOUT_DIA_MAX
) / 2.0
if DRIVE_PIN_FLOOR_LAND_WORST < 0.4:
    raise AssertionError("the knockout leaves the pressed pin no floor to bottom on")
if (
    DRIVE_PIN_CIRCLE_RADIUS - DRIVE_PIN_OFFSET_TOL - _KNOCKOUT_DIA_MAX / 2.0
    <= JOURNAL_BORE_DIA / 2.0 + JOURNAL_BORE_BAND[0] + BORE_MOUTH_BREAK_MAX
    or DRIVE_PIN_CIRCLE_RADIUS + DRIVE_PIN_OFFSET_TOL + _KNOCKOUT_DIA_MAX / 2.0
    >= COLLAR_DIA / 2.0 - BORE_MOUTH_BREAK_MAX
):
    raise AssertionError("the knockout must leave the rear face on its bearing ring")
_SPIGOT_R_WORST = (SPIGOT_DIA + SPIGOT_DIA_BAND[1]) / 2.0
_PIN_HOLE_OUTER_R_WORST = (
    DRIVE_PIN_CIRCLE_RADIUS
    + DRIVE_PIN_OFFSET_TOL
    + (DRIVE_PIN_HOLE_DIA + DRIVE_PIN_HOLE_BAND[0]) / 2.0
)
# Pin hole to the spigot rim: under the .060 in floor at nominal and at the
# printed worst case, rounded DOWN to the .001 in it prints at, so a sheet
# never states more rim than the limits give.
DRIVE_PIN_SPIGOT_RIM = seat_geometry.SEAT_SPIGOT_RIM
DRIVE_PIN_SPIGOT_RIM_WORST = _floor(_SPIGOT_R_WORST - _PIN_HOLE_OUTER_R_WORST, 3, UNIT)
if DRIVE_PIN_SPIGOT_RIM_WORST >= WALL_FLOOR_MM:
    raise AssertionError("the rim meets the floor now: retire RV-02")
if DRIVE_PIN_SPIGOT_RIM_WORST <= 0.0:
    raise AssertionError("the drive-pin holes break out of the spigot at print-worst")
DRIVE_PIN_SPACING_ERROR_MAX = 2.0 * DRIVE_PIN_OFFSET_TOL
if (
    2.0 * DRIVE_PIN_SPACING_ERROR_MAX
    >= seat_geometry.PIN_HOLE_DIA - _DOWEL_OD[1]
):
    raise AssertionError("shaft + wheel pin spacing error exceeds the slip clearance")
# The wheel rides its seat on the two pins alone; nothing else centres it.
# At the printed limits it moves off the shaft axis by one hole's slip
# clearance (the wheel's pin holes drilled to their largest over the
# smallest stock dowel) plus a pin centre and its hole's centre each
# DRIVE_PIN_OFFSET_TOL off nominal, the other way: along the pins' line
# both pairs can lie so at once.  The wheel's bore caps it only where its
# own loosest clearance on the pilot is smaller, and it is not.  The chain
# wrapping the wheel moves with it, so the drive train's radial chain air
# takes this off.  The wheel's holes are drilled to the wheel's own sheet.
_DRILL_OVERSIZE = drilled_oversize_mm(
    unit=drawing_unit("parts/pd-transgear-removable", _config.parts("pd-transgear-removable"))
)
# A pin centre (this sheet's location band) and its hole centre (the wheel's)
# each at their limit, opposite ways along the pins' line.
_WHEEL_PIN_FLOAT = (
    seat_geometry.PIN_HOLE_DIA + _DRILL_OVERSIZE - _DOWEL_OD[0]
) / 2.0 + DRIVE_PIN_OFFSET_TOL + seat_geometry.DRIVE_PIN_OFFSET_TOL
_WHEEL_BORE_FLOAT = (
    seat_geometry.BORE_DIA
    + _DRILL_OVERSIZE
    - (SHAFT_DIA + SHAFT_DIA_BAND[1])
) / 2.0
WHEEL_SEAT_FLOAT = min(_WHEEL_PIN_FLOAT, _WHEEL_BORE_FLOAT)  # 0.156
_PROUD = dt_vn_crank_seat_drive_pin_spec.LENGTH - DRIVE_PIN_DEPTH
# The depth is the interface's (proud length), so it prints rounded.
_DEPTH_LOWER, _DEPTH_UPPER = printed_deviations(
    DRIVE_PIN_DEPTH,
    HOLE_CALLOUT_PLACES,
    (-DRIVE_PIN_DEPTH_TOL, DRIVE_PIN_DEPTH_TOL),
    unit=UNIT,
)
DRIVE_PIN_PROUD_RANGE = (
    _PROUD - _DEPTH_UPPER - seat_geometry.DRIVE_PIN_LENGTH_GRADE,
    _PROUD - _DEPTH_LOWER + seat_geometry.DRIVE_PIN_LENGTH_GRADE,
)
if not 0.0 < DRIVE_PIN_PROUD_RANGE[0] < DRIVE_PIN_PROUD_RANGE[1]:
    raise AssertionError("a pressed drive pin sinks below the seat face at print-worst")


# What the proud tips can meet.  Nothing bears on the T12's front face: the
# first thing in front of it is the crank hub's rear face (the end face of
# its Ø16.5 relief, which covers the pin circle), the drive train's gap B
# away.  The hub is set flush with the dome root, so its rear face sits at
# local HUB_LENGTH + HUB_LENGTH_BAND.  The longest pin stands past the
# THINNEST wheel's front face (2.754 > 2.7) into that gap, which is harmless;
# what must hold is the tip's air to the hub (seat forward, hub long) and,
# with the thinnest wheel floated forward onto the hub (seat aft, hub short),
# the shortest pin's reach into the wheel's hole.
def drive_pin_front_clearances(
    proud_range: tuple[float, float],
    *,
    seat_face: float,
    seat_face_band: tuple[float, float],
    hub_rear: float,
    hub_rear_band: tuple[float, float],
    plate_min: float,
) -> tuple[float, float]:
    """Worst-case ``(tip air to the hub rear face, floated engagement)`` of the
    seat's drive pins, local stations from the dome root; raises when either
    closes."""
    seat_fwd = seat_face + min(seat_face_band)
    seat_aft = seat_face + max(seat_face_band)
    hub_air = seat_fwd - max(proud_range) - (hub_rear + max(hub_rear_band))
    wheel_float = seat_aft - plate_min - (hub_rear + min(hub_rear_band))
    engagement = min(proud_range) - wheel_float
    if hub_air <= 0.0:
        raise AssertionError(
            f"the longest drive pin reaches the crank hub's rear face: air {hub_air:.3f}"
        )
    if engagement <= 0.0:
        raise AssertionError(
            f"the wheel floated onto the hub leaves the drive pins: {engagement:.3f}"
        )
    return hub_air, engagement


DRIVE_PIN_HUB_AIR_WORST, DRIVE_PIN_ENGAGEMENT_WORST = drive_pin_front_clearances(
    DRIVE_PIN_PROUD_RANGE,
    seat_face=SEAT_COLLAR,
    seat_face_band=SEAT_COLLAR_BAND,
    hub_rear=HUB_LENGTH,
    hub_rear_band=HUB_LENGTH_BAND,
    plate_min=seat_geometry.PLATE + min(seat_geometry.PLATE_BAND),
)  # 0.151, 0.618
# The bare land behind the collar keeps the bore mouth's edge break at both
# print limits (JOURNAL_START above).
if (
    JOURNAL_START - STATION_ROW - (COLLAR_REAR + COLLAR_STATION_TOL)
    < BORE_MOUTH_BREAK_MAX - 1e-9
):
    raise AssertionError(
        "the outboard journal reaches the bore mouth behind the collar at print-worst"
    )
# The Ø.375 core is turned bare in three places: the dome-side shank (dome
# root to the seat face), the land behind the collar (rear face to the
# outboard journal, inside the bore mouth) and the land past the inboard
# journal (to the Ø.3125 seat step).  The shank fits the crank hub and carries
# the ShaftDiaDim band. Both non-mating necks use the title block's .XXX:
# the right imports NeckDiaDim; the left measures the full width between
# opposite native silhouettes (the hub's fit band would be over-specified).
SHAFT_CORE_LANDS = (
    (0.0, SEAT_COLLAR),
    (COLLAR_REAR, JOURNAL_START),
    (JOURNAL_END, SEAT_STEP),
)
if any(start >= end for start, end in SHAFT_CORE_LANDS):
    raise AssertionError("every bare Ø.375 core land must have a length")
NECK_DIA_PLACES = 3
# The collar-side neck has no separate authored model dimension to import.
# Its drawing-only driven linear full-width measurement carries only a native
# diameter-symbol prefix and the right-hand neck's loose places, not the shank fit.
DRAWING_REFERENCE_PRECISION = {"OutboardNeckDia": NECK_DIA_PLACES}
if SHAFT_DIA + printed_band_mm(NECK_DIA_PLACES, unit=UNIT) >= (
    JOURNAL_DIA + JOURNAL_DIA_BAND[1]
):
    raise AssertionError("a loose neck must stay under the journal at print-worst")
# Both Ø.449 lands run in MHA-DT-05 and therefore need their own Ra 63
# control on the native cylindrical face and their own drawing leader.  The
# collar's rear face runs against the post boss's south face, so it
# carries the running grade too; the wheel's seat face is a static sprocket
# seat and stays "cast/machined" (drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates)).
SURFACE_FINISHES = (
    *(
        SurfaceFinishControl(
            key,
            MACHINED_UM,
            CylinderFace(JOURNAL_DIA, contains_y_mm=(start + end) / 2.0),
            display_unit=UNIT,
        )
        for key, start, end in (
            ("outboard_journal", JOURNAL_START, RELIEF_START),
            ("inboard_journal", RELIEF_END, JOURNAL_END),
        )
    ),
    SurfaceFinishControl(
        "collar_rear_face",
        MACHINED_UM,
        PlanarFace((0.0, 1.0, 0.0), COLLAR_REAR),
        display_unit=UNIT,
    ),
)


# Every printed axial station is a baseline from ONE origin: the FAR END, the
# one faced end the shop zeroes on (drawing-guidelines.md rule 11 (turned parts read like the lathe)).  The features themselves
# measure from the dome root, so the far-end stations, the overall and the
# dome's spherical radius live on a construction-only StationReference sketch
# driven by the same globals (no geometry).  Depth (far end to dome root) and
# DomeHeight complete the chain; the overall and SR are references.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShaftProfile": {"ShaftDiaDim"},
    "Shaft": {"Depth"},
    "ShaftDomeProfile": {"DomeHeight"},
    "JournalProfile": {"JournalDiaDim"},
    "ReliefProfile": {"ReliefDiaDim"},
    "PinionSeatProfile": {"PinionSeatDiaDim", "NeckDiaDim"},
    "CollarProfile": {"CollarDiaDim"},
    "SpigotProfile": {"SpigotDiaDim"},
    "Spigot": {"SpigotLength"},
    "DrivePinProfile": {"DrivePinOffset1", "DrivePinOffset2"},
    "StationReference": {
        "OverallLength",
        "PinionSeatStation",
        "JournalInboardStation",
        "ReliefInboardStation",
        "ReliefOutboardStation",
        "JournalOutboardStation",
        "CollarRearStation",
        "CollarSeatStation",
        "PinHoleStation",
        "DomeSphereRadius",
    },
}
# Inch places: running/seat diameters carry their fit bands at four (their
# .0008 bands need them). Relief and axial stations carry the routine
# two-place title-block band; the collar's functional bands print at the
# places that hold them.  The dome height is the crank hub's (it prints
# rounded, a non-functional cap).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ShaftProfile": {"ShaftDiaDim": 4},
    "Shaft": {"Depth": dt_crank_pinion_spec.SHAFT_LENGTH_PLACES},
    "ShaftDomeProfile": {"DomeHeight": 3},
    "JournalProfile": {"JournalDiaDim": 4},  # 11.4046, .449 in
    "ReliefProfile": {"ReliefDiaDim": RELIEF_DIA_PLACES},
    "PinionSeatProfile": {"PinionSeatDiaDim": 4, "NeckDiaDim": NECK_DIA_PLACES},
    "CollarProfile": {"CollarDiaDim": 2},
    "SpigotProfile": {"SpigotDiaDim": SPIGOT_DIA_PLACES},
    "Spigot": {"SpigotLength": SPIGOT_LENGTH_PLACES},
    "DrivePinProfile": {
        "DrivePinOffset1": DRIVE_PIN_OFFSET_PLACES,
        "DrivePinOffset2": DRIVE_PIN_OFFSET_PLACES,
    },
    "StationReference": {
        "OverallLength": 2,
        "PinionSeatStation": STATION_PLACES,
        "JournalInboardStation": STATION_PLACES,
        "ReliefInboardStation": STATION_PLACES,
        "ReliefOutboardStation": STATION_PLACES,
        "JournalOutboardStation": STATION_PLACES,
        "CollarRearStation": COLLAR_STATION_PLACES,
        "CollarSeatStation": COLLAR_STATION_PLACES,
        "PinHoleStation": STATION_PLACES,
        "DomeSphereRadius": 3,
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked crankshaft dimension needs authored places")
# Read-only restatements: the overall is Depth + DomeHeight, and a spherical
# cap of DomeHeight on the Ø.375 end already fixes its radius.
REFERENCE_DIMENSIONS = frozenset({"OverallLength", "DomeSphereRadius"})
SPHERICAL_DIMENSIONS = frozenset({"DomeSphereRadius"})

# The native cross-hole callout's process prefix: the drill reads first; the
# taper-ream prose under it lives in dt_crankshaft_notes (drawing-only).
CROSS_HOLE_PROCESS = drill_process(PIN_HOLE_SPEC)
# The drive-pin holes' process prefix; the press prose is in the notes.
DRIVE_PIN_HOLE_PROCESS = "REAM"
HOLE_CALLOUT_PRECISION: dict[str, dict[str, int]] = {
    "DrivePinProfile": {
        "DrivePinHoleDia1": HOLE_CALLOUT_PLACES,
        "DrivePinHoleDia2": HOLE_CALLOUT_PLACES,
    },
    "DrivePinHoles": {"DrivePinDepth": HOLE_CALLOUT_PLACES},
}
# The one general note is the shop's inside-corner ceiling at every shoulder
# (drawing-guidelines.md rule 11 (turned parts read like the lathe)); the
# punch mark is flagged at the mark itself (dt_crankshaft_notes FIDUCIAL_NOTE).
# TODO(#1625): drop the note when the title block carries the default.
DRAWING_NOTES = f"INSIDE CORNERS R{inch_text(STEP_CORNER_RADIUS_MAX, 3)} MAX."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 1:1"
