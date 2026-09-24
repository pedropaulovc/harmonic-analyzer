r"""Pure-data dimensional contract for the integral MHA-102 pinion arbor.

The turned head, neck, and long shaft are deliberately one piece.  This is an
approved photo-derived reconstruction choice, not proof of the historical
joint detail.  The exact released external envelope is preserved while the
former socket and unsupported radial retention pin are removed.
"""

from __future__ import annotations

import math
from itertools import product

from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from pinion_bracket_geometry import THICKNESS as STRAP_T
from pinion_handle_geometry import ROD_DIA, ROD_DIA_BAND

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

# --- Drum station and journal-land length (Main ruling A, 2026-09-24) --------
# MHA-102 owns where the MHA-002 drum is bonded: its front end sits
# DRUM_STATION from the head shoulder, and the drum, trapped between the two
# MHA-056 straps, is what places the arbor's lands on the straps.  Every land
# end is printed from the head shoulder at .X, and the lands are centred on
# their straps at nominal (to the one place they print at).  Each land must still cover its strap by
# MIN_LAND_OVER_STRAP at the worst corner of every printed band (stations,
# land length, strap thickness, drum length, drum-station band) and of the
# drum's axial float.  JOURNAL_LEN is the smallest whole millimetre that does
# so with a printed station band of at least MIN_DRUM_STATION_BAND; no .X band
# is tightened to make it fit (U27).
LINEAR_X_BAND = 0.8  # .X title-block row
# MHA-056 prints its thickness at .X (pinion_bracket_spec.THICKNESS_BAND,
# pinned equal by test).  Not imported: the drive-train recipe reads this spec
# and must not depend on the bracket's drawing contract.
STRAP_T_BAND = LINEAR_X_BAND
# User ruling 2026-09-24: the drum is bonded 0.3 further aft than the as-built
# station so MHA-027 gear j=19 reads its full 3.0 face at nominal.
DRUM_STATION_AS_BUILT = 61.25  # BDT APINION_Z_FRONT from the head shoulder
DRUM_AFT_SHIFT = 0.3
DRUM_STATION = DRUM_STATION_AS_BUILT + DRUM_AFT_SHIFT
DRUM_LEN = 143.2  # MHA-002 FACE_WIDTH
DRUM_LEN_BAND = (LINEAR_X_BAND, -LINEAR_X_BAND)  # general .X
MIN_LAND_OVER_STRAP = 0.5
MIN_DRUM_STATION_BAND = 0.5
# User ruling 2026-09-24 (option c): the pivot blocks locate the swing cluster.
# It is pushed against the back block, and the front block's slotted base
# holes are set at fit-up with an END_PLAY feeler, within END_PLAY_SET_ERROR.
# That total play is the float between the drum ends and the strap inner
# faces, split either way, whatever the drum's length.  The drum hard forward
# and hard aft are the two stops.
STRAP_AXIAL_LOCATION = "block-stop-slot-set"
END_PLAY = 0.25
END_PLAY_SET_ERROR = 0.10
MIN_END_PLAY = 0.1  # the drum never binds between the straps
LAND_FINISH_RUNOUT = 2.0  # the Ra 1.6 pass runs out this far past the land
LAND_ENDS = ("front inboard", "front outboard", "back inboard", "back outboard")
STOPS = {"drum forward": 0.0, "drum aft": 1.0}  # share of the air at the front


def drum_total_air() -> tuple[float, float]:
    """Total axial air between the drum ends and the strap inner faces."""
    if STRAP_AXIAL_LOCATION != "block-stop-slot-set":
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


def drum_station_band(journal_len: float) -> float:
    """The widest one-place station band that keeps every margin."""
    slack = min(worst_land_margins(journal_len, 0.0).values()) - MIN_LAND_OVER_STRAP
    return math.floor(slack * 10.0 + 1e-9) / 10.0


def _smallest_journal_len() -> float:
    for journal_len in range(int(STRAP_T) + 1, 40):
        if drum_station_band(float(journal_len)) >= MIN_DRUM_STATION_BAND:
            return float(journal_len)
    raise AssertionError("no whole-mm journal land meets the drum-station stack")


JOURNAL_LEN = _smallest_journal_len()
DRUM_STATION_BAND = drum_station_band(JOURNAL_LEN)
FRONT_JOURNAL_FROM_HEAD_REAR, BACK_JOURNAL_FROM_HEAD_REAR = land_stations(JOURNAL_LEN)
LAND_MARGINS_AT_STOPS = {
    stop: worst_land_margins(JOURNAL_LEN, DRUM_STATION_BAND, stop=stop)
    for stop in STOPS
}
for _stop, _margins in LAND_MARGINS_AT_STOPS.items():
    if min(_margins.values()) < MIN_LAND_OVER_STRAP - 1e-9:
        raise AssertionError(f"journal land margins at {_stop}: {_margins} under 0.5")
if END_PLAY - END_PLAY_SET_ERROR < MIN_END_PLAY:
    raise AssertionError("the drum can bind between the straps")
BACK_CAP_SAG = 1.2
BACK_CAP_R = (SHAFT_DIA / 2.0) ** 2 / (2.0 * BACK_CAP_SAG) + BACK_CAP_SAG / 2.0

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
HEAD_LEN_BAND = 0.8  # .X title-block row
CROSS_HOLE_WEB_WORST = (
    (HEAD_LEN - HEAD_LEN_BAND) / 2.0 - (CROSS_HOLE_DIA + CROSS_HOLE_DIA_BAND[0]) / 2.0
)
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

SURFACE_FINISHES = tuple(
    SurfaceFinishControl(
        key,
        MACHINED_UM,
        CylinderFace(SHAFT_DIA, contains_z_mm=station + JOURNAL_LEN / 2.0),
    )
    for key, station in (
        ("front_journal", FRONT_JOURNAL_Z),
        ("back_journal", BACK_JOURNAL_Z),
    )
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    # Head and neck diameters are the same Front-plane circle pattern as
    # ShaftDia: imported end-on on the donor view and moved onto the 1:1
    # profile (5cc191fb's proven path; a detail silhouette screen pick is
    # seat-dependent and failed on w6).
    "HeadProfile": {"HeadDia"},
    "NeckProfile": {"NeckDia"},
    "Head": {"HeadLen"},
    "Neck": {"NeckLen"},
    "ShaftProfile": {"ShaftDia"},
    "FrontCapProfile": {"HeadCapR", "HeadCapSagDim"},
    "BackCapProfile": {"BackCapR", "BackCapSagDim"},
    "CrossHoleProfile": {"CrossHoleDia"},
    "BackRimReference": {"BackRimFromHeadRear"},
    "OverallReference": {"OverallLen"},
    "FrontJournalReference": {
        "FrontJournalFromHeadRear",
        "FrontJournalLen",
        "FrontJournalDia",
    },
    "BackJournalReference": {
        "BackJournalFromHeadRear",
        "BackJournalLen",
        "BackJournalDia",
    },
}

DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "HeadProfile": {"HeadDia": 1},
    "NeckProfile": {"NeckDia": 1},
    "Head": {"HeadLen": 1},
    "Neck": {"NeckLen": 2},
    "ShaftProfile": {"ShaftDia": 2},
    "FrontCapProfile": {"HeadCapR": 1, "HeadCapSagDim": 1},
    "BackCapProfile": {"BackCapR": 1, "BackCapSagDim": 1},
    "CrossHoleProfile": {"CrossHoleDia": 2},
    "BackRimReference": {"BackRimFromHeadRear": 1},
    "OverallReference": {"OverallLen": 1},
    "FrontJournalReference": {
        "FrontJournalFromHeadRear": 1,
        "FrontJournalLen": 1,
        "FrontJournalDia": 2,
    },
    "BackJournalReference": {
        "BackJournalFromHeadRear": 1,
        "BackJournalLen": 1,
        "BackJournalDia": 2,
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked integral-arbor dimension needs authored places")

CROSS_HOLE_CALLOUT = (
    "REAM THRU,\n"
    "CENTRED ON HEAD LENGTH"
)
DRAWING_NOTES = "\n".join(
    (
        "JOURNALS RUN IN MHA-056 REAMED BORES.",
        f"SHAFT SLIPS INTO MHA-002; BOND WITH {RETAINING_COMPOUND}, DRUM FRONT END",
        f"  {DRUM_STATION:.2f} +/-{DRUM_STATION_BAND:.1f} FROM HEAD SHOULDER. "
        "WIPE SQUEEZE-OUT OFF JOURNAL LANDS.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
