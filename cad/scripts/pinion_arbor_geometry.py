r"""Geometry of the integral MHA-102 pinion arbor: envelope, drum station and
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

from _printed_tolerance import printed_band_mm
from pinion_bracket_geometry import THICKNESS as STRAP_T
from pinion_bracket_geometry import THICKNESS_BAND as STRAP_T_BAND
from pinion_handle_geometry import ROD_DIA, ROD_DIA_BAND
from pinion_rig_layout import (
    DRUM_END_SHIM,
    DRUM_END_SHIM_SET_ERROR,
    DRUM_LEN,
    RIG_MARGIN_SPARE,
)

SHAFT_DIA = 8.0
SHAFT_LEN = 226.25  # unchanged origin-to-back-crown-root station
# Only the two short lands that run in the MHA-056 strap bores (REAM_SLIDE)
# carry the running band and the Ra 1.6 finish (U39).  Everything else,
# the MHA-002 drum bond zone included, is Ø8 -0.01/-0.10: the drum keeps its
# stock-H7-reamer bore (8.000-8.100), so the guaranteed slide-on clearance
# comes from this side (min 0.010 at 7.99), and the loosest pair (8.10 on
# 7.90) stays a 0.20 diametral gap, inside Loctite 638's 0.25.
SHAFT_DIA_BAND = (-0.010, -0.100)
# The drum also slides over the back land on its way on from the back crown,
# so the lands sit 0.01 under 8.00 too (Main ruling): the same 0.02-wide band
# as ground shafting, shifted down, so it is no harder to turn.  In the
# MHA-056 REAM_SLIDE bores (8.010-8.025) the running clearance is 0.020-0.055.
JOURNAL_DIA_BAND = (-0.010, -0.030)

# Former handle-body envelope, turned integrally with the arbor.  Rule 12
# (audit W6, 2026-09-23): the Ø6 crossrod hole left 1.50 of wall to each face
# of the 9.0 head at nominal and -0.10 at the printed worst case (HeadLen and
# the hole station both .X).  The head grows to 10.5 about the unchanged
# crossrod station (world z -6.5), and the hole is printed CENTRED on the head
# length rather than located by a .X station, so only the HeadLen band reaches
# the web: (10.5 - 0.8) / 2 - 6.10 / 2 = 1.80 worst case.
HEAD_DIA = 15.0
HEAD_LEN = 10.5
HEAD_CAP_SAG = 3.0
HEAD_CAP_R = ((HEAD_DIA / 2.0) ** 2 + HEAD_CAP_SAG**2) / (2.0 * HEAD_CAP_SAG)
HEAD_CENTER_Z = -6.5  # the released crossrod station
HEAD_REAR_Z = HEAD_CENTER_Z + HEAD_LEN / 2.0
HEAD_FRONT_Z = HEAD_CENTER_Z - HEAD_LEN / 2.0

# --- Drum station and journal-land length (Main ruling A, 2026-09-24) --------
# MHA-102 owns where the MHA-002 drum is bonded: its front end sits
# DRUM_STATION from the head shoulder, and the drum, trapped between the two
# MHA-056 straps, is what places the arbor's lands on the straps.  Every land
# end is printed from the head shoulder at .X, and the lands are centred on
# their straps at nominal (to the one place they print at).  Each land must still cover its strap by
# MIN_LAND_OVER_STRAP at the worst corner of every printed band (stations,
# land length, strap thickness, drum length, drum-station band) and of the
# drum's axial float.  The drum station prints the general .X band, and
# JOURNAL_LEN is the smallest whole millimetre that keeps every margin with it;
# no band is tightened to make it fit (U27, Main 2026-09-24: a longer land
# rather than a tighter station).
LINEAR_X_BAND = printed_band_mm(1)  # .X title-block row, 0.8
# MHA-056's thickness band (STRAP_T_BAND) and the MHA-002 drum length come from
# their geometry owners, pinion_bracket_geometry and pinion_rig_layout, not
# their drawing contracts: the drive-train recipe reads this spec.
# User ruling 2026-09-24: the drum is bonded 0.3 further aft than the as-built
# station so MHA-027 gear j=19 reads its full 3.0 face at nominal.
# The released (pre-ruling) pose, before MECHANISM_Z_SHIFT: the drum front
# end at z -75.0 and the arbor root at z -135.0, so the drum sat 61.25 from
# the head shoulder.
RELEASED_DRUM_FRONT_Z = -75.0
RELEASED_ARBOR_ROOT_Z = -135.0
DRUM_STATION_AS_BUILT = RELEASED_DRUM_FRONT_Z - RELEASED_ARBOR_ROOT_Z - HEAD_REAR_Z
DRUM_AFT_SHIFT = 0.3
DRUM_STATION = DRUM_STATION_AS_BUILT + DRUM_AFT_SHIFT
DRUM_LEN_BAND = (LINEAR_X_BAND, -LINEAR_X_BAND)  # general .X
MIN_LAND_OVER_STRAP = 0.5
DRUM_STATION_BAND = LINEAR_X_BAND
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
    """Front and back land stations from the head shoulder, printed at .X.

    Each land is centred on its strap with the drum mid-way through its play,
    then rounded to the one place it prints at; the worst-case stack below
    runs on the rounded values.
    """
    air = END_PLAY / 2.0
    front_inner = DRUM_STATION - air
    back_inner = DRUM_STATION + DRUM_LEN + air
    return (
        round(front_inner - (journal_len + STRAP_T) / 2.0, 1),
        round(back_inner - (journal_len - STRAP_T) / 2.0, 1),
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
    x = LINEAR_X_BAND
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


def _smallest_journal_len() -> float:
    for journal_len in range(int(STRAP_T) + 1, 40):
        if land_margin_slack(float(journal_len)) >= -1e-9:
            return float(journal_len)
    raise AssertionError("no whole-mm journal land meets the drum-station stack")


JOURNAL_LEN = _smallest_journal_len()
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
BACK_CAP_SAG = 1.2
BACK_CAP_R = (SHAFT_DIA / 2.0) ** 2 / (2.0 * BACK_CAP_SAG) + BACK_CAP_SAG / 2.0

NECK_DIA = 10.5
NECK_END_Z = 10.0
NECK_LEN = NECK_END_Z - HEAD_REAR_Z
EXPOSED_SHAFT_LEN = SHAFT_LEN - NECK_END_Z
# R1 (U27 precedent, Main 2026-09-24): a stock 6 mm reamer cuts 6.000-6.015
# and as-received bar is at most 6.000, so a novice cannot make the old 0.0125
# press.  The hole is reamed Ø6.00 +0.10/0 and MHA-058 is bonded in with
# Loctite 638; the model carries both at the 6.00 nominal (line to line).
CROSS_HOLE_DIA = 6.0
CROSS_HOLE_DIA_BAND = (0.100, 0.000)  # (upper, lower) deviations
RETAINING_COMPOUND = "LOCTITE 638"
RETAINING_COMPOUND_MAX_GAP_MM = 0.25  # 638 TDS diametral gap limit
OVERALL_LEN = SHAFT_LEN + BACK_CAP_SAG - (HEAD_FRONT_Z - HEAD_CAP_SAG)
BACK_RIM_FROM_HEAD_REAR = SHAFT_LEN - HEAD_REAR_Z
FRONT_JOURNAL_Z = HEAD_REAR_Z + FRONT_JOURNAL_FROM_HEAD_REAR
BACK_JOURNAL_Z = HEAD_REAR_Z + BACK_JOURNAL_FROM_HEAD_REAR

# Rule 12 worst-case web from the centred crossrod hole to either head face:
# the .X HeadLen band split over both sides, the hole at its upper limit.
HEAD_LEN_PLACES = 1  # HeadLen
HEAD_CAP_SAG_PLACES = 1  # HeadCapSagDim
NECK_LEN_PLACES = 2  # NeckLen
HEAD_LEN_BAND = printed_band_mm(HEAD_LEN_PLACES)  # .X title-block row
CROSS_HOLE_WEB_WORST = (HEAD_LEN - HEAD_LEN_BAND) / 2.0 - (
    CROSS_HOLE_DIA + CROSS_HOLE_DIA_BAND[0]
) / 2.0
# Crossrod bond: the rod must still enter the hole at its tightest pair, and
# the loosest pair must stay inside the retaining compound's gap.
CROSSROD_MIN_CLEARANCE = (CROSS_HOLE_DIA + CROSS_HOLE_DIA_BAND[1]) - (
    ROD_DIA + ROD_DIA_BAND[0]
)
CROSSROD_MAX_CLEARANCE = (CROSS_HOLE_DIA + CROSS_HOLE_DIA_BAND[0]) - (
    ROD_DIA + ROD_DIA_BAND[1]
)
if CROSS_HOLE_WEB_WORST < 1.5:
    raise AssertionError(
        f"crossrod hole web {CROSS_HOLE_WEB_WORST:.2f} is under the 1.5 floor"
    )
if CROSSROD_MIN_CLEARANCE < 0.0:
    raise AssertionError("MHA-058 crossrod no longer enters its reamed hole")
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
    BACK_JOURNAL_FROM_HEAD_REAR + JOURNAL_LEN + 2.0 * LINEAR_X_BAND + LAND_FINISH_RUNOUT
    > BACK_RIM_FROM_HEAD_REAR - LINEAR_X_BAND
):
    raise AssertionError("back journal land runs into the back-crown root")

# The bond zone's Ø8 -0.01/-0.10 is dimensioned on its own flank, from a
# Top-plane reference sketch like the lands', not off the end-on shaft circle:
# that circle sits in the neck face on the Front plane, so its witnesses ran
# along the neck and out through the detail-A fence (run 492a7be5).  The
# witness station lies inside the drum's bond zone, clear of both lands, so
# the diameter reads as the bond zone's.
BOND_ZONE_DIA_FROM_HEAD_REAR = 113.0
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
