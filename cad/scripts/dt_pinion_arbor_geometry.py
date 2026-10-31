r"""Geometry of the integral MHA-DT-22 pinion arbor: envelope, drum station and
journal-land stack.

GEOMETRY ONLY: no drawing notes, marks or precision maps (the
``pinion_cam_geometry`` precedent).  The drive train sizes the drum air and
the land margins from this module, so a print-wording or precision edit in
``pinion_arbor_spec`` can never re-key it (Main, restricted review of #858).

The turned head, neck, and long shaft are deliberately one piece.  This is an
approved photo-derived reconstruction choice, not proof of the historical
joint detail.  The exact released external envelope is preserved while the
former socket and unsupported radial retention pin are removed.
"""

from __future__ import annotations

import math
from itertools import product

import _config
from _fit_ream_slide import REAM_SLIDE
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm
from dt_pinion_bracket_geometry import THICKNESS as STRAP_T
from dt_pinion_bracket_geometry import THICKNESS_BAND as STRAP_T_BAND
from dt_pinion_handle_geometry import ROD_DIA, ROD_DIA_BAND
from pinion_rig_layout import (
    DRUM_END_SHIM,
    DRUM_END_SHIM_SET_ERROR,
    DRUM_LEN,
    DRUM_LEN_BAND as _DRUM_LEN_PRINTED_BAND,
    RIG_MARGIN_SPARE,
)

# #290: the registry row's drawing_unit (in) is MHA-DT-22's sheet unit.  Every
# axial station and length on it prints at the title block's .XX: the land,
# drum-station, pin, wall and run-out stacks all read them, so none is .X.
UNIT = drawing_unit("parts/dt-pinion-arbor", _config.parts("dt-pinion-arbor"))
LINEAR_XX_BAND = printed_band_mm(2, unit=UNIT)  # .XX title-block row, .01 in


def on_xx_grid(value_mm: float) -> float:
    """``value_mm`` snapped to the .01-in grid, half away from zero."""
    return round(math.floor(value_mm / 0.254 + 0.5) * 0.254, 9)


# 5/16 in (owner ruling 2026-10-30): the arbor follows the owned .3135 over
# reamer that cuts its strap and drum bores; 8 mm has no owned reamer.
SHAFT_DIA = 7.9375
# Origin to back-crown root: the back rim prints 8.93 (226.822) from the head
# rear face at -0.66 (#290; was 226.25, 0.088 longer).
SHAFT_LEN = 226.162
# Only the two short lands that run in the MHA-DT-14 strap bores (REAM_SLIDE)
# carry the running band and the Ra 1.6 finish (U39).  Everything else,
# the MHA-DT-01 drum bond zone included, is 5/16 -.0004/-.0038 in: the drum's
# REAM_SLIDE bore starts at .3135, so the guaranteed slide-on clearance is
# .0014 in, and the loosest pair (.3140 on .3087) stays a .0053 in diametral
# gap, inside Loctite 638's 0.25 mm.
SHAFT_DIA_BAND = (-0.01016, -0.09652)
# The drum also slides over the back land on its way on from the back crown,
# so the lands sit .0004 in under 5/16 too (Main ruling): the same .0008-wide
# band as ground shafting, shifted down, so it is no harder to turn.  In the
# MHA-DT-14 REAM_SLIDE bores (.3135-.3140) the running clearance is
# .0014-.0027 in.
JOURNAL_DIA_BAND = (-0.01016, -0.03048)

# Former handle-body envelope, turned integrally with the arbor.  drawing-guidelines.md rule 17 (walls and webs)
# (audit W6, 2026-09-23): the Ø6 crossrod hole left 1.50 of wall to each face
# of the 9.0 head at nominal and -0.10 at the printed worst case (HeadLen and
# the hole station both .X).  The head grew to 10.5 about the unchanged
# crossrod station (world z -6.5), and the hole is printed CENTRED on the Ø15
# cylinder's length rather than located by a .X station, so only the HeadLen
# band reaches the web.  The machinist review of 7f7fc1717 then flagged that
# web, (10.5 - 0.8) / 2 - 6.10 / 2 = 1.80, under the novice-machinist 2.0
# target; Main's ruling (option 2) grows the head to 11.5, again about the
# crossrod station: 2.30 worst case.  Machinist review r3 of #1685 then
# asked for a toleranced station in place of CENTRED.  At the 11.5 head only
# a .XXX station and a .XX HeadLen held the target, and r5 ruled that a
# band tightened to rescue a wall (drawing-guidelines.md rules 4 and 17).
# So the head grows forward only, 11.5 -> 12.2: the crossrod station and the
# rear face stay put, and with the station at 5.75 (.XX) and HeadLen at .X
# both webs hold the target (CROSS_HOLE_WEB_WORST below).  HEAD_CENTER_Z
# keeps its name for its consumers but is the crossrod station, 0.35 aft of
# the head's mid-length.
#
# Every station on the print runs from the head rear face, so its position
# decides which lengths print exactly at .X.  With SHAFT_LEN released, the
# rear face sits at -0.75, where the back-rim length (227.0) and the overall
# (243.4) are .X; the neck shoulder moves 0.25 forward, 10.0 -> 9.75, so the
# neck (10.5, flagged at 11.25) is .X too.  The drum station (61.05) and the
# crossrod station (5.75) are the .XX lengths.
# #290 (decimal inch): every printed nominal sits on its .XX grid.  The head
# rear face moves 0.09 aft (-0.75 -> -0.66) so the drum station, which the
# drum's world position fixes, prints exactly 2.40, and the crossrod station
# .23 then puts the crossrod 0.002 forward of its released -6.5.
HEAD_DIA = 14.986  # .59
HEAD_LEN = 12.192  # .48
# The front crown prints its SR.43; its sag follows and prints as a REF.
HEAD_CAP_R = 10.922  # SR.43
HEAD_CAP_SAG = HEAD_CAP_R - math.sqrt(HEAD_CAP_R**2 - (HEAD_DIA / 2.0) ** 2)
HEAD_REAR_Z = -0.66
CROSS_HOLE_STATION = 5.842  # .23 from the head rear face
HEAD_CENTER_Z = HEAD_REAR_Z - CROSS_HOLE_STATION  # the crossrod station
HEAD_FRONT_Z = HEAD_REAR_Z - HEAD_LEN

# --- Drum station and journal-land length (Main ruling A, 2026-09-24) --------
# MHA-DT-22 owns where the MHA-DT-01 drum is bonded: its front end sits
# DRUM_STATION from the head shoulder, and the drum, trapped between the two
# MHA-DT-14 straps, is what places the arbor's lands on the straps.  Every land
# end is printed from the head shoulder at .XX, and the lands are centred on
# their straps at nominal (to the .01 in they print at).  Each land must still cover its strap by
# MIN_LAND_OVER_STRAP at the worst corner of every printed band (stations,
# land length, strap thickness, drum length, drum-station band) and of the
# drum's axial float.  The drum station prints the .XX band; no band is
# tightened to make it fit (U27, Main 2026-09-24: a longer land rather than a
# tighter station).  #290: the land keeps its 20 mm, snapped to .79.
# MHA-DT-14's thickness band (STRAP_T_BAND) and the MHA-DT-01 drum length come from
# their geometry owners, dt_pinion_bracket_geometry and pinion_rig_layout, not
# their drawing contracts: the drive-train recipe reads this spec.
# User ruling 2026-09-24: the drum is bonded 0.3 further aft than the as-built
# station so MHA-DT-12 gear j=19 reads its full 3.0 face at nominal.
# The released (pre-ruling) pose, before MECHANISM_Z_SHIFT: the drum front
# end at z -75.0 and the arbor root at z -135.0, so the drum front sits at a
# fixed arbor-local 60.0 (BDT APINION_Z_FRONT - ARBOR_Z0 before the aft
# shift, pinned by test).  The station is that position from the head rear
# face, so it follows the face whenever the head changes (61.25 at the 10.5
# head, 60.75 at 11.5) and the drum itself never moves in the world.
RELEASED_DRUM_FRONT_Z = -75.0
RELEASED_ARBOR_ROOT_Z = -135.0
DRUM_FRONT_Z_AS_BUILT = RELEASED_DRUM_FRONT_Z - RELEASED_ARBOR_ROOT_Z
DRUM_STATION_AS_BUILT = DRUM_FRONT_Z_AS_BUILT - HEAD_REAR_Z
DRUM_AFT_SHIFT = 0.3
DRUM_STATION = DRUM_STATION_AS_BUILT + DRUM_AFT_SHIFT
# The MHA-DT-01 drum sheet's own printed length band (pinion_rig_layout).
DRUM_LEN_BAND = (_DRUM_LEN_PRINTED_BAND, -_DRUM_LEN_PRINTED_BAND)
MIN_LAND_OVER_STRAP = 0.5
DRUM_STATION_BAND = LINEAR_XX_BAND
# User ruling 2026-09-24 (option c): the pivot blocks locate the swing
# cluster.  Option E-a then pins both straps to the torque shaft, which is
# match-drilled with the END_PLAY feeler as a shim at the drum's front end
# (Main, restricted review of #858): the strap spacing is frozen at the drum
# plus the shim, so the drum turns between the straps in END_PLAY +/-
# END_PLAY_SET_ERROR of air, split any way between its two ends.  The block
# gaps are the pinned group's own end play and no longer feed the drum's air.
# The assembly shows the drilling set-up, the drum hard on the back strap
# (pinion_rig_layout).  The drum hard forward and hard aft are the two stops.
STRAP_AXIAL_LOCATION = "pinned-shim-set"
END_PLAY = DRUM_END_SHIM  # the shaft's drilling shim (pinion_rig_layout)
END_PLAY_SET_ERROR = DRUM_END_SHIM_SET_ERROR
MIN_END_PLAY = 0.1  # the drum never binds between the straps
LAND_FINISH_RUNOUT = 2.0  # the Ra 1.6 pass runs out this far past the land
LAND_ENDS = ("front inboard", "front outboard", "back inboard", "back outboard")
STOPS = {"drum forward": 0.0, "drum aft": 1.0}  # share of the air at the front


def drum_total_air() -> tuple[float, float]:
    """Total axial air between the drum ends and the strap inner faces."""
    if STRAP_AXIAL_LOCATION != "pinned-shim-set":
        raise AssertionError(f"no float model for {STRAP_AXIAL_LOCATION!r}")
    return (END_PLAY - END_PLAY_SET_ERROR, END_PLAY + END_PLAY_SET_ERROR)


def land_stations(journal_len: float) -> tuple[float, float]:
    """Front and back land stations from the head shoulder, printed at .XX.

    Each land is centred on its strap with the drum mid-way through its play,
    then snapped to the .01-in grid it prints at; the worst-case stack below
    runs on the snapped values.
    """
    air = END_PLAY / 2.0
    front_inner = DRUM_STATION - air
    back_inner = DRUM_STATION + DRUM_LEN + air
    return (
        on_xx_grid(front_inner - (journal_len + STRAP_T) / 2.0),
        on_xx_grid(back_inner - (journal_len - STRAP_T) / 2.0),
    )


def worst_land_margins(
    journal_len: float, station_band: float, *, stop: str | None = None
) -> dict[str, float]:
    """Worst land-over-strap margin at each land end, over every band corner.

    The drum's front end is the origin; the head shoulder sits DRUM_STATION
    before it and each strap's inner face sits its drum-end air away.  Every
    margin is linear in each input, so the corners bound it.  ``stop`` limits
    the float to one end of its range (the drum hard forward or hard aft).
    """
    front, back = land_stations(journal_len)
    x = LINEAR_XX_BAND
    shares = (STOPS[stop],) if stop is not None else tuple(STOPS.values())
    worst = dict.fromkeys(LAND_ENDS, math.inf)
    for a, b, length, strap, station, drum, total, share in product(
        (front - x, front + x),
        (back - x, back + x),
        (journal_len - x, journal_len + x),
        (STRAP_T - STRAP_T_BAND, STRAP_T + STRAP_T_BAND),
        (DRUM_STATION - station_band, DRUM_STATION + station_band),
        (DRUM_LEN + DRUM_LEN_BAND[1], DRUM_LEN + DRUM_LEN_BAND[0]),
        drum_total_air(),
        shares,
    ):
        shoulder = -station
        front_inner = -share * total
        back_inner = drum + (1.0 - share) * total
        margins = {
            "front inboard": shoulder + a + length - front_inner,
            "front outboard": front_inner - strap - (shoulder + a),
            "back inboard": back_inner - (shoulder + b),
            "back outboard": shoulder + b + length - (back_inner + strap),
        }
        for key, value in margins.items():
            worst[key] = min(worst[key], value)
    return worst


# The novice-margin rule (Main, restricted review of #858): the lands keep
# RIG_MARGIN_SPARE over the floor too.  With the 0.45 drum shim the 19 land
# left 0.70 at the drum-forward stop, 0.20 over it.
LAND_OVER_STRAP_REQUIRED = MIN_LAND_OVER_STRAP + RIG_MARGIN_SPARE


def land_margin_slack(journal_len: float) -> float:
    """Worst land-over-strap margin above the floor and its spare, both stops."""
    margins = worst_land_margins(journal_len, DRUM_STATION_BAND)
    return min(margins.values()) - LAND_OVER_STRAP_REQUIRED


JOURNAL_LEN = 20.066  # .79
FRONT_JOURNAL_FROM_HEAD_REAR, BACK_JOURNAL_FROM_HEAD_REAR = land_stations(JOURNAL_LEN)
LAND_MARGINS_AT_STOPS = {
    stop: worst_land_margins(JOURNAL_LEN, DRUM_STATION_BAND, stop=stop)
    for stop in STOPS
}
for _stop, _margins in LAND_MARGINS_AT_STOPS.items():
    if min(_margins.values()) < LAND_OVER_STRAP_REQUIRED - 1e-9:
        raise AssertionError(
            f"journal land margins at {_stop}: {_margins} under "
            f"{LAND_OVER_STRAP_REQUIRED}"
        )
if END_PLAY - END_PLAY_SET_ERROR < MIN_END_PLAY:
    raise AssertionError("the drum can bind between the straps")
# The back crown prints its SR.28; its sag follows and prints as a REF.
BACK_CAP_R = 7.112  # SR.28
BACK_CAP_SAG = BACK_CAP_R - math.sqrt(BACK_CAP_R**2 - (SHAFT_DIA / 2.0) ** 2)

NECK_DIA = 10.414  # .41
NECK_LEN = 10.414  # .41
NECK_END_Z = HEAD_REAR_Z + NECK_LEN
EXPOSED_SHAFT_LEN = SHAFT_LEN - NECK_END_Z
# R1 (U27 precedent, Main 2026-09-24): as-received bar cannot make a press, so
# MHA-DT-15 is bonded in with Loctite 638.  #290 (owner ruling): the crossrod
# is 1/4 bar, and the owned .2510 over reamer cuts the hole .250 +.0015/+.0010
# (REAM_SLIDE); the model carries rod and hole at the .250 nominal (line to
# line).
CROSS_HOLE_DIA = 6.35  # .250
CROSS_HOLE_DIA_BAND = REAM_SLIDE  # (upper, lower) deviations
RETAINING_COMPOUND = "LOCTITE 638"
RETAINING_COMPOUND_MAX_GAP_MM = 0.25  # 638 TDS diametral gap limit
OVERALL_LEN = SHAFT_LEN + BACK_CAP_SAG - (HEAD_FRONT_Z - HEAD_CAP_SAG)
BACK_RIM_FROM_HEAD_REAR = SHAFT_LEN - HEAD_REAR_Z
FRONT_JOURNAL_Z = HEAD_REAR_Z + FRONT_JOURNAL_FROM_HEAD_REAR
BACK_JOURNAL_Z = HEAD_REAR_Z + BACK_JOURNAL_FROM_HEAD_REAR

# drawing-guidelines.md rule 17 (walls and webs) worst-case web from the crossrod hole to either head
# face.  Machinist review r3 of #1685 (clarity, 3 of 3 runs): "CENTRED ON Ø15
# CYLINDER LENGTH" told the shop neither where to measure from nor how
# closely, so the hole is an ordinary toleranced station from the head rear
# face.  Every band is the title-block row for the places the value needs
# (r5: no band tightened for the wall): rear web .23 - .01 - .2515 / 2 =
# .0942 in, front web (.48 - .01) - (.23 + .01) - .2515 / 2 = .1042 in.
HEAD_LEN_PLACES = 2  # HeadLen
HEAD_CAP_SAG_PLACES = 2  # HeadCapSagDim (REF)
NECK_LEN_PLACES = 2  # NeckLen
HEAD_LEN_BAND = printed_band_mm(HEAD_LEN_PLACES, unit=UNIT)  # .XX title-block row
CROSS_HOLE_STATION_PLACES = 2  # CrossHoleFromHeadRear
CROSS_HOLE_STATION_BAND = printed_band_mm(CROSS_HOLE_STATION_PLACES, unit=UNIT)
CROSS_HOLE_REAR_WEB_WORST = (
    CROSS_HOLE_STATION
    - CROSS_HOLE_STATION_BAND
    - (CROSS_HOLE_DIA + CROSS_HOLE_DIA_BAND[0]) / 2.0
)
CROSS_HOLE_FRONT_WEB_WORST = (
    (HEAD_LEN - HEAD_LEN_BAND)
    - (CROSS_HOLE_STATION + CROSS_HOLE_STATION_BAND)
    - (CROSS_HOLE_DIA + CROSS_HOLE_DIA_BAND[0]) / 2.0
)
CROSS_HOLE_WEB_WORST = min(CROSS_HOLE_REAR_WEB_WORST, CROSS_HOLE_FRONT_WEB_WORST)
# Crossrod bond: the rod must still enter the hole at its tightest pair, and
# the loosest pair must stay inside the retaining compound's gap.
CROSSROD_MIN_CLEARANCE = (CROSS_HOLE_DIA + CROSS_HOLE_DIA_BAND[1]) - (
    ROD_DIA + ROD_DIA_BAND[0]
)
CROSSROD_MAX_CLEARANCE = (CROSS_HOLE_DIA + CROSS_HOLE_DIA_BAND[0]) - (
    ROD_DIA + ROD_DIA_BAND[1]
)
# Rule 17 on an inch sheet: .080 in target, .060 in floor.  The machinist
# review of 7f7fc1717 held this web to the target, not the floor.
CROSS_HOLE_WEB_TARGET = WALL_TARGET_MM
if CROSS_HOLE_WEB_WORST < CROSS_HOLE_WEB_TARGET:
    raise AssertionError(
        f"crossrod hole web {CROSS_HOLE_WEB_WORST:.2f} is under the "
        f"{CROSS_HOLE_WEB_TARGET} target"
    )
if CROSSROD_MIN_CLEARANCE < 0.0:
    raise AssertionError("MHA-DT-15 crossrod no longer enters its reamed hole")
if CROSSROD_MAX_CLEARANCE > RETAINING_COMPOUND_MAX_GAP_MM:
    raise AssertionError(
        f"crossrod bond gap {CROSSROD_MAX_CLEARANCE:.3f} exceeds the "
        f"{RETAINING_COMPOUND} limit {RETAINING_COMPOUND_MAX_GAP_MM}"
    )
if min(HEAD_LEN, NECK_LEN, EXPOSED_SHAFT_LEN) <= 0.0:
    raise AssertionError("integral arbor axial spans must be positive")
if not NECK_END_Z < FRONT_JOURNAL_Z < FRONT_JOURNAL_Z + JOURNAL_LEN < BACK_JOURNAL_Z:
    raise AssertionError("front journal land must sit on the exposed shaft")
if BACK_JOURNAL_Z + JOURNAL_LEN >= SHAFT_LEN:
    raise AssertionError("back journal land must end before the back crown")
# Worst case, the back land's far end plus its finishing run-out still stops
# short of the back-crown root.
if (
    BACK_JOURNAL_FROM_HEAD_REAR
    + JOURNAL_LEN
    + 2.0 * LINEAR_XX_BAND
    + LAND_FINISH_RUNOUT
    > BACK_RIM_FROM_HEAD_REAR - LINEAR_XX_BAND
):
    raise AssertionError("back journal land runs into the back-crown root")

# The bond zone's 5/16 -.0004/-.0038 in is dimensioned on its own flank, from a
# Top-plane reference sketch like the lands', not off the end-on shaft circle:
# that circle sits in the neck face on the Front plane, so its witnesses ran
# along the neck and out through the detail-A fence (run 492a7be5).  The
# witness station lies inside the drum's bond zone, clear of both lands, so
# the diameter reads as the bond zone's.  Machinist review r1 of #1685: the
# callout grew to name its scope and the drum, too tall for the gap above the
# shaft under detail A, so the witness moved back to 188.0, 11 mm short of
# the back land, where the callout hangs below the shaft in the open run
# between the back land and the drum station's text.
BOND_ZONE_DIA_FROM_HEAD_REAR = 188.0
BOND_ZONE_DIA_Z = HEAD_REAR_Z + BOND_ZONE_DIA_FROM_HEAD_REAR
BOND_ZONE_LAND_CLEARANCE = 10.0
if not (
    max(FRONT_JOURNAL_FROM_HEAD_REAR + JOURNAL_LEN, DRUM_STATION)
    + BOND_ZONE_LAND_CLEARANCE
    <= BOND_ZONE_DIA_FROM_HEAD_REAR
    <= min(BACK_JOURNAL_FROM_HEAD_REAR, DRUM_STATION + DRUM_LEN)
    - BOND_ZONE_LAND_CLEARANCE
):
    raise AssertionError(
        "the bond-zone diameter must sit on the drum, clear of both lands"
    )

# R1a (user, 2026-09-24): the station of the cross hole for the MHA-DT-33
# collar's spring pin, at the general band from the head rear face (U27:
# the collar-to-strap gap grows to absorb it, dt_pinion_arbor_collar_spec).  The
# drive-train assembly reads the station; the hole itself and its clearance
# proofs live in dt_pinion_arbor_pin_spec.  38.0, not R1a's 39.0: on #858's
# pinned straps the drum's front air runs to the whole 0.55 of end play and
# the 11.5 head moved the drum station to 61.05, which closed the worst-case
# collar-to-strap gap to 0.00 at the mm .X band; one millimetre forward
# restored it to 1.00, over the 0.25 the novice-margin rule asks
# (dt_pinion_arbor_collar_spec).  #290: snapped to 1.50 at .XX.
PIN_STATION_FROM_HEAD_REAR = 38.1  # 1.50
PIN_STATION_BAND = LINEAR_XX_BAND
PIN_Z = HEAD_REAR_Z + PIN_STATION_FROM_HEAD_REAR
