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
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm
from dt_pinion_bracket_geometry import THICKNESS as STRAP_T
from dt_pinion_bracket_geometry import THICKNESS_LIMITS as STRAP_T_LIMITS
from dt_pinion_handle_geometry import ROD_DIA, ROD_DIA_BAND, ROD_SPAN
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
# Origin to back-crown root: the back rim prints 9.35 (237.490) from the head
# rear face at -0.66.  #1038 re-pitch: the 6.06 in drum moved the back land
# .42 in aft (198.882 -> 209.550 from the head rear face), so the shaft grew
# the same 10.668 (226.162 -> 236.830) to keep the land clear of the crown.
SHAFT_LEN = 236.83
# Only the two short lands that run in the MHA-DT-14 strap bores (made to
# fit, JOURNAL_DIA_BAND below) carry the Ra 1.6 finish (U39).  The two
# MHA-DT-01 bond lands are made to fit too (BOND_LAND_DIA_BAND below).  The
# other Ø5/16 spans (the collar's, by the head, and the back stub) are 5/16
# -.0004/-.0038 in: MHA-DT-33 slides over them.  The middle of the drum's
# length is relieved (BOND_RELIEF_* below).
SHAFT_DIA_BAND = (-0.01016, -0.09652)
# The two bond lands are turned last to the MHA-DT-01 drum bore, drilled
# 5/16 from both ends (owner ruling 2026-11-24, fit audit question 13: the
# bore drilled, the bond taking the size): at least .002 under the smaller
# of its two measured ends, so the drum slides on by hand, and never more
# than .008 under its larger end, inside LOCTITE 638's gap (made to fit,
# form 2: delegated ruling 2026-11-24 (FitLaneDT), in place of question 13's
# printed -.0014/-.0048).  The shaft is finished whole length to the
# journals' aim first; the lands are skimmed only where that aim leaves the
# drum less than .002.  The sheet prints the size REF and the acceptance
# (draw_dt_pinion_arbor note 3).  BOND_FIT_CLEARANCE is the fit's own
# diametral clearance anywhere along the drum; BOND_LAND_DIA_BAND is NOT a
# printed limit: it is the ANALYSIS band the fit is modelled to produce over
# the drilled range, .3085-.3121 (its top .0004 under 5/16, as the journals',
# so the MHA-DT-33 collar still slides over both lands on its way to the
# head).
BOND_FIT_CLEARANCE = (0.0508, 0.2032)  # .002-.008 in
BOND_LAND_DIA_BAND = (-0.01016, -0.1016)  # ANALYSIS deviations, -.0004/-.0040 in
# The two journals are made to fit (owner ruling 2026-11-24, fit audit
# question 12): turned last to the 5/16 drilled MHA-DT-14 strap bores
# (.3125-.3165 at the DRILLED HOLES row), clearance .001-.003, and the drum
# still slides over the back one on its way on.  The sheet prints the size
# REF and that acceptance (draw_dt_pinion_arbor note 1).  JOURNAL_DIA_BAND is
# NOT a printed limit: it is the ANALYSIS band, the journal the fit is
# modelled to produce over the drilled range, .3095-.3121 (its top .0004
# under 5/16, so the drum and the collar still pass it).
JOURNAL_DIA_BAND = (-0.01016, -0.0762)  # ANALYSIS deviations, -.0004/-.0030 in
# The clearance the journals are turned to in the measured strap bores: the
# fit's own acceptance, the modelled result every running stack reads.
JOURNAL_FIT_CLEARANCE = (0.0254, 0.0762)  # .001-.003 in

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
# drum's axial float.  The drum station is set at the bond to this .XX-width
# band, which MHA-DT-00 prints on its drum-station setting
# (dt_drum_station_setting_spec; the arbor shows the station as a reference); no band is
# tightened to make it fit (U27, Main 2026-09-24: a longer land rather than a
# tighter station).  #290: the land keeps its 20 mm, snapped to .79.
# MHA-DT-14's printed thickness limits (STRAP_T_LIMITS) and the MHA-DT-01 drum length come from
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
# The one drum-station band: every stack here, the collar gap, the rig's
# advance/retreat stacks and MHA-DT-00's printed setting all read it.
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
    Every land end prints as its own station from the head rear face (#1038
    delegated ruling (a): no length chained off a station), so each reads one
    band.
    """
    front, back = land_stations(journal_len)
    x = LINEAR_XX_BAND
    shares = (STOPS[stop],) if stop is not None else tuple(STOPS.values())
    worst = dict.fromkeys(LAND_ENDS, math.inf)
    for a, f, b, e, strap, station, drum, total, share in product(
        (front - x, front + x),
        (front + journal_len - x, front + journal_len + x),
        (back - x, back + x),
        (back + journal_len - x, back + journal_len + x),
        STRAP_T_LIMITS,
        (DRUM_STATION - station_band, DRUM_STATION + station_band),
        (DRUM_LEN + DRUM_LEN_BAND[1], DRUM_LEN + DRUM_LEN_BAND[0]),
        drum_total_air(),
        shares,
    ):
        shoulder = -station
        front_inner = -share * total
        back_inner = drum + (1.0 - share) * total
        margins = {
            "front inboard": shoulder + f - front_inner,
            "front outboard": front_inner - strap - (shoulder + a),
            "back inboard": back_inner - (shoulder + b),
            "back outboard": shoulder + e - (back_inner + strap),
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
# #1038 delegated ruling (a), on the machinist reviews of 057ffb6 (the back
# land's .79 chained off its 8.25) and 703211d (the front land's .79 chained
# off its 1.82): each land's crown-side end prints as its own station from
# the head rear face, 2.61 and 9.04.  Delegated rulings (a) and (b) (the
# relief's back shoulder, below): delegated ruling 2026-11-11, no
# precedent, made by Repitch1038 as integration owner under the owner's
# 2026-11-11 re-pitch rulings (commits 4a51a72647 and 7c268934d2), applying
# drawing-guidelines rules 10/11 (baseline every axial station from one
# faced end); the owner reviews them on #2144
# (https://github.com/pedropaulovc/harmonic-analyzer/issues/2144).
# Each land's length is then the difference
# of two .XX stations, .79 -.02/+.02; every end it bears on reads one band.
FRONT_JOURNAL_END_FROM_HEAD_REAR = FRONT_JOURNAL_FROM_HEAD_REAR + JOURNAL_LEN
BACK_JOURNAL_END_FROM_HEAD_REAR = BACK_JOURNAL_FROM_HEAD_REAR + JOURNAL_LEN
for _END in (FRONT_JOURNAL_END_FROM_HEAD_REAR, BACK_JOURNAL_END_FROM_HEAD_REAR):
    if abs(on_xx_grid(_END) - _END) > 1e-9:
        raise AssertionError("a land's end station is off the .01 in grid")
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
# is 1/4 bar.  Fit audit F14 (owner ruling 2026-11-24): the hole is reamed
# with the owned .2510 reamer (inventory tools.reamers "0.2510in") and prints
# no band, the rod entering by hand its acceptance (".2510 REAM THRU; MHA-DT-15
# ROD ENTERS BY HAND; BOND LOCTITE 638").  The model nominal is the reamer's
# size; CROSS_HOLE_DIA_BAND is the ANALYSIS band (what the reamer is modelled
# to cut, .2510-.2515), not a printed limit.  The bond's two ends still hold:
# the largest catalogue rod (ROD_DIA_BAND, ASTM A108 1/4 cold-finished)
# enters with CROSSROD_ENTRY_CLEARANCE, and the loosest pair stays inside
# Loctite 638's diametral gap ceiling (TDS: 0.25 mm max gap).  A 1/4 drill
# can cut under the largest rod and an F drill's .261 overruns the gap: the
# necessity register's N-01.
OWNED_CROSS_HOLE_REAMER_MM = 0.2510 * 25.4
CROSS_HOLE_DIA = OWNED_CROSS_HOLE_REAMER_MM  # 6.3754, .2510 reamer
CROSS_HOLE_DIA_PLACES = 4
CROSSROD_ENTRY_CLEARANCE = 0.0254  # .001 in over the largest rod
CROSS_HOLE_DIA_BAND = (0.0127, 0.0)  # ANALYSIS (upper, lower) deviations
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
# (r5: no band tightened for the wall): rear web .23 - .01 - .255 / 2 =
# .0925 in, front web (.48 - .01) - (.23 + .01) - .255 / 2 = .1025 in.
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
    BACK_JOURNAL_END_FROM_HEAD_REAR + LINEAR_XX_BAND + LAND_FINISH_RUNOUT
    > BACK_RIM_FROM_HEAD_REAR - LINEAR_XX_BAND
):
    raise AssertionError("back journal land runs into the back-crown root")
# --- Bond lands and middle relief (#2360; owner, 2026-11-11) -----------------
# The 6.06 in MHA-DT-01 bore is longer than a 5/16 jobber drill reaches, so
# it is drilled from both ends (owner ruling 2026-11-24, fit audit question
# 13) and its two halves meet near mid-length with whatever small step the
# re-chucking leaves.  The owner's direction (2026-11-11): hold the fit only
# at the two ends and let the middle be clearance.  A recess in the drum's
# bore cannot be cut with owned tools (it would need a boring bar reaching
# 3.0 in through a 5/16 land), so the clearance is turned on the arbor
# instead: a plain relief between two bond lands.  The drum then bears and
# bonds only on those lands, and the long shaft no longer has to follow the
# bore's straightness over its whole length.  The drum is tried on before
# bonding (note 3's SLIDES ON BY HAND), so a step at the meeting point that
# would stop it is found then, not at the bond.  The loosest pair is the
# drill's .3165 top over the smallest land (.3085): .0080 in (0.203 mm),
# inside LOCTITE 638's 0.25 mm (BOND_GAP_MAX below).
#
# Both relief shoulders are located from the head rear face, the sheet's
# datum for every station (drawing-guidelines rules 10/11; machinist review
# of 7454ba6d gated a chain off the front land, and the review of 057ffb6 the
# 2.60 length chained off the 4.20; #1038 delegated ruling (b)).  Both at .XX,
# so the relief's length is the difference, 2.60 -.02/+.02.  The front land
# is the longer: the operator's torque enters at the head and reaches the
# drum through it; it also carries the bond-zone diameter's witness
# (BOND_ZONE_DIA_FROM_HEAD_REAR).
BOND_RELIEF_FROM_HEAD_REAR = 106.68  # 4.20
BOND_RELIEF_BACK_FROM_HEAD_REAR = 172.72  # 6.80
BOND_RELIEF_LEN = BOND_RELIEF_BACK_FROM_HEAD_REAR - BOND_RELIEF_FROM_HEAD_REAR
BOND_RELIEF_Z = HEAD_REAR_Z + BOND_RELIEF_FROM_HEAD_REAR
# Ø.28 at the title block's .XX: from the drum's .3125 minimum drilled bore
# to the relief's .29 maximum the radial air is .0113 in (0.29 mm), so
# nothing in the middle touches.
BOND_RELIEF_DIA = 7.112  # .28
BOND_RELIEF_MIN_RADIAL_AIR = 0.25
# MHA-DT-01's 5/16 drilled bore, its ANALYSIS band (the DRILLED HOLES row's
# +.004/0): dt_alignment_pinion_spec.ARBOR_BORE_BAND, which imports nothing
# from here; test_dt_alignment_pinion_drawing pins the two together.
DRUM_BORE_BAND = (0.1016, 0.0)
DRUM_BORE_MIN = SHAFT_DIA + DRUM_BORE_BAND[1]  # .3125
DRUM_BORE_MAX = SHAFT_DIA + DRUM_BORE_BAND[0]  # .3165
BOND_RELIEF_RADIAL_AIR = (DRUM_BORE_MIN - (BOND_RELIEF_DIA + LINEAR_XX_BAND)) / 2.0
if BOND_RELIEF_RADIAL_AIR < BOND_RELIEF_MIN_RADIAL_AIR:
    raise AssertionError(
        f"bond relief clears the drum bore by {BOND_RELIEF_RADIAL_AIR:.3f}, "
        f"under {BOND_RELIEF_MIN_RADIAL_AIR}"
    )
# The made-to-fit bond (BOND_FIT_CLEARANCE, BOND_LAND_DIA_BAND above): the
# drum slides on, and the loosest pair, the drill's top over the smallest
# land, stays inside the fit's own .008 and so inside the compound's gap.
BOND_GAP_MIN = BOND_FIT_CLEARANCE[0]
BOND_GAP_MAX = DRUM_BORE_MAX - (SHAFT_DIA + BOND_LAND_DIA_BAND[1])
if BOND_GAP_MIN <= 0.0:
    raise AssertionError("MHA-DT-01 no longer slides onto its bond lands")
if BOND_GAP_MAX > min(BOND_FIT_CLEARANCE[1], RETAINING_COMPOUND_MAX_GAP_MM) + 1e-9:
    raise AssertionError(
        f"drum bond gap {BOND_GAP_MAX:.3f} exceeds the fit's "
        f"{BOND_FIT_CLEARANCE[1]:.4f} or the {RETAINING_COMPOUND} limit "
        f"{RETAINING_COMPOUND_MAX_GAP_MM}"
    )
# Each drum end's bonded overlap, every printed band at its short corner: the
# relief's shoulders from the head rear face; the drum from its station and
# length.
FRONT_BOND_OVERLAP_MIN = (BOND_RELIEF_FROM_HEAD_REAR - LINEAR_XX_BAND) - (
    DRUM_STATION + DRUM_STATION_BAND
)
BACK_BOND_OVERLAP_MIN = (
    DRUM_STATION - DRUM_STATION_BAND + DRUM_LEN + DRUM_LEN_BAND[1]
) - (BOND_RELIEF_BACK_FROM_HEAD_REAR + LINEAR_XX_BAND)
# The relief spans the drum's mid-length, where halves drilled to about half
# depth from each end meet.  This is not a requirement: a deeper pass from
# one end may leave the step under a land, where note 3's slide-on trial
# before bonding already bounds it.  #1038 re-pitch: the 6.06 in drum keeps
# this relief; its mid moved 5.22 -> 5.43 in, the front land stays the longer
# (1.80 in against the back land's 1.66, was 1.24) and both hold over three
# times the hand torque.
_DRUM_MID = DRUM_STATION + DRUM_LEN / 2.0
if not (
    BOND_RELIEF_FROM_HEAD_REAR + LINEAR_XX_BAND < _DRUM_MID - DRUM_STATION_BAND
    and _DRUM_MID + DRUM_STATION_BAND < BOND_RELIEF_BACK_FROM_HEAD_REAR - LINEAR_XX_BAND
):
    raise AssertionError("the bond relief must span the drum's mid-length")
# Torque: either land alone holds twice a hard hand twist on the MHA-DT-15
# T-bar (30 N at each end, about 32.5 mm out: 2.0 N m).  LOCTITE 638's ISO
# 10123 shear is 25 N/mm^2 minimum (TDS), derated with the Henkel LOCTITE
# Retaining Compound Design Guide's factors taken low: 0.4 for the brass drum
# (Factor 2, Materials, p. 10: "Copper and Alloys 0.4", the lower of the
# dissimilar pair against mild steel's 1.0; read 2026-11-20, #2608), 0.3 for
# the clearance at the loosest pair (.0080 in, 0.203 mm, BOND_GAP_MAX;
# sm_gooseneck_spring_joint books 0.3 at 0.25 mm) and 0.5 for a long land.
LOCTITE_638_SHEAR_MPA = 25.0
BOND_FACTOR = 0.4 * 0.3 * 0.5
HAND_TORQUE_NM = 2.0 * 30.0 * ROD_SPAN / 2.0 / 1000.0
BOND_TORQUE_MARGIN_MIN = 2.0


def bond_torque_capacity(overlap: float) -> float:
    """N m one bonded land of ``overlap`` mm holds on the Ø5/16 shaft."""
    return (
        LOCTITE_638_SHEAR_MPA
        * BOND_FACTOR
        * math.pi
        * SHAFT_DIA
        * overlap
        * SHAFT_DIA
        / 2.0
        / 1000.0
    )


if (
    min(
        bond_torque_capacity(FRONT_BOND_OVERLAP_MIN),
        bond_torque_capacity(BACK_BOND_OVERLAP_MIN),
    )
    < BOND_TORQUE_MARGIN_MIN * HAND_TORQUE_NM
):
    raise AssertionError("a drum bond land does not hold twice the hand torque")
# Stiffness: the drum is bonded at both ends, so between the lands the brass
# drum (root Ø15.6 over the .3135 bore, E 97 GPa) carries the bending; its
# EI is about 12 times the relieved steel's at Ø.27.  The relief carries no
# torque either: the front land hands it to the drum.

# The bond lands' 5/16 -.0004/-.0038 in is dimensioned on its own flank, from
# a Top-plane reference sketch like the lands', not off the end-on shaft
# circle: that circle sits in the neck face on the Front plane, so its
# witnesses ran along the neck and out through the detail-A fence (run
# 492a7be5).  The witness station lies on a bond land, clear of the relief
# and the journal, so the diameter reads as the bond lands'.  Machinist
# review r1 of #1685 hung the callout below the shaft over the back bond
# land.  #1038 delegated ruling (b) (machinist reviews of 057ffb6 and
# 7c26893): the relief's back shoulder prints as a station from the head
# rear face, which can stand
# neither above the shaft (the collar pin hole's leader would cross it) nor
# below with the callout there (its extension would drop through the block).
# So the witness moves to the front bond land and the callout hangs above
# the shaft, left of its line, between detail A's label and the front land.
# At 75.0 (r5, 9dc1a4d) the block ended one character from the label's
# SCALE 2 : 1 (review, clarity); 69.5, 3.2 off the front land's 2.61 end,
# stands its line 4.2 mm short of that end and the block ~7 mm clear of the
# label.
BOND_ZONE_DIA_FROM_HEAD_REAR = 69.5
BOND_ZONE_DIA_Z = HEAD_REAR_Z + BOND_ZONE_DIA_FROM_HEAD_REAR
BOND_ZONE_LAND_CLEARANCE = 3.0
if not (
    FRONT_JOURNAL_END_FROM_HEAD_REAR + BOND_ZONE_LAND_CLEARANCE
    <= BOND_ZONE_DIA_FROM_HEAD_REAR
    <= BOND_RELIEF_FROM_HEAD_REAR - BOND_ZONE_LAND_CLEARANCE
    and BOND_ZONE_DIA_FROM_HEAD_REAR > DRUM_STATION + DRUM_STATION_BAND
):
    raise AssertionError(
        "the bond-zone diameter must sit on the front bond land, clear of the "
        "front journal and the relief"
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
