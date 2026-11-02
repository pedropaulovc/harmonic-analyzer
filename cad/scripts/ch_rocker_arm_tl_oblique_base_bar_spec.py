r"""Pure-data contract for the oblique trammel's base bars (MHA-CH-06-TL-20).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). Two bars
lie on the PM-30MV table, one under each HGR15R rail (bought, shop inventory
``fixtures.trammel-hgr15-rails`` in ``cad/process/shop/inventory.toml``) of the rocker
arm's oblique-trammel mill jig (``ch_rocker_arm_tl_oblique_trammel_spec``,
imported as ``trammel``; values marked ⚙ are read from it). Each bar carries
its rail off its centreline, toward the operator, and is held down by two
1/2-13 T-slot studs in slots across the bar. The rails are aligned on the
table by indicating the pin, so the bar's own position on the table does not
matter; the only tight bands are the rail holes' end distance and pitch
(below).

Issue #290: the sheet prints decimal inch (``drawing_unit: in``). Lengths
stay physical millimetres, each fabricated nominal the exact millimetres of
its printed inch value. Exempt: the near slot's station (it closes the T-slot
pitch), which prints rounded, its worst cases reading the printed value's
limits. The HGR15R rail's hole pattern and the bracket holes' stations (the
leadscrew's KP08 stations along the Tr8 screw) belong to metric-only vendor
lines (owner ruling 4, 2026-11-01, option B): they print exact millimetres,
labelled ``mm``, each with its own band (``METRIC_DIMENSIONS``,
``_metric_vendor_dimension``).

Material and stock: 6061-T6511 aluminium flat bar milled from the owned 1/2 x
6 bar (OnlineMetals 1173; owner ruling #2083), sawn and faced to ⚙
``BASE_BAR_LENGTH`` 17.32 (the rail's 440 cut; rail and bar flush within the
length's band) and milled to width ⚙ ``BASE_BAR_WIDTH`` 5.50 on edge in the
vise, no bandsaw rip: the width is a machined size at the title block's .XX
band. Both large faces are faced from ⚙ ``BASE_BAR_STOCK_THICK`` to ⚙
``BASE_BAR_THICK`` .47 (owner ruling 2026-10-30, option A), held by the title
block's .XX band like the TL-21 carrier: each is a static locating seat, so
each carries Ra 125 µin (rule 6, ``SURFACE_FINISHES``). Bar 1's underside
sits on the mill table and its top carries the rail and the TL-28 brackets;
bar 2, turned over, uses them the other way round. The PM-30MV's 23 in X and
8.75 in Y travel cover the 17.32 x 5.50 face, gripped across the 5.50 in the
5.75 vise opening. The user's 2026-10-17 ruling (a) widened the bar from 1/2 x
4 to 1/2 x 6 so the leadscrew's TL-28 end brackets (PR C4) stand wholly on bar
1; the 2026-10-30 ruling narrowed it to 5.50, inside the 6 in vise's stock
hard jaws, keeping the column-side edge and so the brackets.

Frame: origin at the bar's spindle-end face, on the rail axis, on the bottom
face; +X along the bar away from the spindle, +Y across it, +Z up
(right-handed). On rail 1 the part's y is minus the calculator's lateral
(``trammel.rail_point``, +lateral toward the column), so the column-side edge
⚙ ``BASE_BAR_COLUMN_EDGE`` (lateral +3.50) is the -Y side and the
operator-side edge ⚙ ``BASE_BAR_OPERATOR_EDGE`` (lateral -2.00) the +Y side.

Rail holes: 7 x #8-32 UNC tapped THRU on the rail axis (y 0) at x = ⚙
``RAIL_HOLE_END`` + k * ⚙ ``RAIL_HOLE_PITCH`` (40 .. 400 mm, the rail's own
pattern, printed ``40.00 ±0.08 mm`` .. ``400.00 ±0.08 mm``). The rail is a
custom cut; its symmetric E = 40 end distance is the ORDER requirement, an
unverified vendor value until the supplier confirms the cut. The rail's
Ø4.5 mm holes take #8 socket
screws (⚙ ``RAIL_SCREW``); a 3/4 in screw seats ⚙ 9.7 mm above the rail base,
so .368 engages the bar (rule 18: at least 1.5D).

Rail-hole bands (the one tight requirement): a #8 screw (Ø.164) fixed in the
bar's tapped hole has only ``RAIL_SCREW_CLEARANCE`` .0066 a side in the
rail's Ø4.5 mm hole (a fixed-fastener pattern), so every bar hole's position
error plus the rail's own must stay inside that radius. Every hole is located
by DRO absolutes from the two faced datums: its station from the spindle-end
face at 2 mm places ± ``RAIL_HOLE_BAND`` 0.08 mm, the rail's pitch, and the row
from the faced -Y edge (``RAIL_ROW_Y`` 3.50, the column-side edge's lateral)
at the title block's .XX (``RAIL_ROW_PLACES``; c3-r7, rule 4: the row's
height has no mate, the hold-down slots set the bar's place at fit-up and
the rail is indicated in). All seven holes are cut at the one DRO Y setting,
so the row's band moves the whole row: only the station band scatters the
holes, ``RAIL_HOLE_POSITION_RADIUS`` from nominal (the stations print exact,
so no rounding adds to it), leaving ``RAIL_PATTERN_ALLOWANCE`` for the rail's
own hole positions (an unverified vendor value). The outermost station
carries the mate on a second line, "MATCHES HGR15R RAIL HOLES". The row's
3.50 carries its reason (``RAIL_ROW_CALLOUT``).

Hold-down slots: two through slots ⚙ ``HOLD_DOWN_SLOT_WIDTH`` .53 wide, axis
along Y, stud travel ± ⚙ ``HOLD_DOWN_ADJUST`` .08 (.69 overall). Near slot
centre x = ⚙ ``HOLD_DOWN_NEAR_S`` - ⚙ ``RAIL_NEAR_S`` (prints .87), far slot
x = ⚙ ``HOLD_DOWN_FAR_S`` - ⚙ ``RAIL_NEAR_S`` (15.35), each ± ⚙
``HOLD_DOWN_LATERAL`` (1.48) off the rail axis. Per drawing-guidelines rule
12 the slots are dimensioned to their radius centres: width .53 and the .16
between the two end-arc centres, each centre carrying a printed centre mark.

One part, one configuration, two off (Main's ruling): every feature goes
through, so the bar under rail 2 is the same part turned over (rotated 180°
about its X axis). Turning it over mirrors plan X and keeps lateral, so on
both bars the column-side edge stays on the column side, the near slot on
the near stud and the rail row on the rail. The part as modelled is the
rail-1 bar: near slot at y -1.48, far slot at +1.48. Both slots are located
from the faced -Y side, the datum every hole uses, to their lower end
centres (c3-r6 review, rule 10): the near slot's rise ``NEAR_SLOT_RISE``
1.94, the far slot's ``FAR_SLOT_RISE`` 4.90.

Walls (rule 17, .080 target, .060 floor, worst case at the printed bands):
the near slot to the bar's spindle end; a slot end to its bar side (the far
slot to the +Y side is the thinner: its rise, run and the stock width's
supplier band all enter it).

End bracket holes (PR C4): 8 x #8 SHCS clearance (``BRACKET_HOLE_DIA``
.196, normal fit) THRU, counterbored Ø.313 x .189 from the UNDERSIDE, at
the leadscrew layout's ``BASE_BAR_HOLES`` (four in a row at each KP08
station; rows 2.425, 1.768, .902 and .245 from the -Y edge). Four #8-32 x
5/8 SHCS per TL-28 bracket go up through the bar into the bracket's tapped
holes before the bar goes on the table; the heads sit below the underside.
Since the 2026-10-17 widening (ruling A′) each bracket stands wholly on the
bar, its outer end flush with the -Y edge. Both bars carry the holes; on the
turned-over bar 2 the counterbores face up, unused. The rows print at .XXX:
their spacings must hold TL-28's tapped row inside the screws' float, so the
callout names the mate. The two stations are the KP08's metric stations and
print exact, ``57.000 ±0.13 mm`` and ``428.000 ±0.13 mm`` (the millimetre
title block's three-place band, stated on each). Worst-case walls:
``bracket_hole_walls``.
"""

from __future__ import annotations

import math

import _config
from _gtol_planar import PlanarFace
from _hole_spec import CLEARANCE_MM, THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import drilled_oversize_mm, printed_band_mm, printed_deviations
from _surface_finish import SEAT_UM, SurfaceFinishControl
import ch_rocker_arm_tl_oblique_trammel_spec as trammel

INCH = 25.4
UNIT = drawing_unit(
    "parts/ch-rocker-arm-tl-oblique-base-bar",
    _config.parts("ch-rocker-arm-tl-oblique-base-bar"),
)
# The metric vendor lines' stations print in millimetres on the inch sheet
# (owner ruling 4, 2026-11-01): exact, so no rounding adds to their band.
METRIC_UNIT = "mm"


def _deviation(
    value: float, places: int, band: float | None = None, *, unit: str = UNIT
) -> float:
    """The widest a part may sit off ``value`` (mm) when the sheet prints it
    at ``places`` of ``unit`` with its title-block band, or ``band``: the band
    plus the rounding of a value off the printed grid."""
    limits = None if band is None else (-band, band)
    low, high = printed_deviations(value, places, limits, unit=unit)
    return max(-low, high)


BAR_THICK = trammel.BASE_BAR_THICK  # ⚙ .47, faced
BAR_WIDTH = trammel.BASE_BAR_WIDTH  # ⚙ 5.50, milled to width (#2083)
BAR_LENGTH = trammel.BASE_BAR_LENGTH  # ⚙ 17.32
# The width is milled from the 1/2 x 6 bar (owner ruling #2083), so it prints
# as a machined size at the title block's .XX band.
WIDTH_PLACES = 2
BAR_WIDTH_BAND = printed_band_mm(WIDTH_PLACES, unit=UNIT)
# The two long sides in the rail-1 part frame (y = -lateral): the rail sits
# off the centreline since the 2026-10-17 widening, so each side is read from
# its own calculator edge, never as half the width.
LOW_SIDE_Y = -trammel.BASE_BAR_COLUMN_EDGE  # ⚙ -3.50: the faced -Y, column side
HIGH_SIDE_Y = -trammel.BASE_BAR_OPERATOR_EDGE  # ⚙ 2.00: the +Y, operator side
if abs(HIGH_SIDE_Y - LOW_SIDE_Y - BAR_WIDTH) > 1e-9:
    raise AssertionError("the base bar's sides miss its width")

# --- Rail holes ---------------------------------------------------------------
RAIL_SCREW = trammel.RAIL_SCREW  # ⚙ "#8-32"
TAP_SPEC = HoleSpec("tapped", RAIL_SCREW)
TAP_DRILL = blind_cut_dia_mm(TAP_SPEC)
RAIL_HOLE_X: tuple[float, ...] = tuple(
    trammel.RAIL_HOLE_END + k * trammel.RAIL_HOLE_PITCH
    for k in range(trammel.RAIL_HOLE_COUNT)
)
if len(RAIL_HOLE_X) != 7:
    raise AssertionError("the brief's base bar carries seven rail holes")
RAIL_ROW_Y = -LOW_SIDE_Y  # 3.50: the row (y 0) from the faced -Y edge
# The HGR15R rail's metric pattern prints exact millimetres at two places,
# each station with the rail pitch's own band (``40.00 ±0.08 mm``).
RAIL_HOLE_PLACES = 2
RAIL_HOLE_BAND = 0.08  # the stations only: the rail's hole pitch
# The row's height prints at the title block's band (c3-r7, rule 4): nothing
# mates with it, and the one DRO Y setting keeps the holes in line.
RAIL_ROW_PLACES = 2
RAIL_HOLE_DIA = 4.5  # HGR15R rail's screw hole (catalogue)
RAIL_SCREW_CLEARANCE = (RAIL_HOLE_DIA - THREAD_MAJOR_MM[RAIL_SCREW]) / 2.0  # .0066
# One Y setting for the row: only the station band scatters hole from hole.
RAIL_HOLE_POSITION_RADIUS = max(
    _deviation(x, RAIL_HOLE_PLACES, RAIL_HOLE_BAND, unit=METRIC_UNIT)
    for x in RAIL_HOLE_X
)
RAIL_PATTERN_ALLOWANCE = RAIL_SCREW_CLEARANCE - RAIL_HOLE_POSITION_RADIUS
if RAIL_PATTERN_ALLOWANCE <= 0.0:
    raise AssertionError("the rail-hole position bands bind the rail screws")
RAIL_MATE_CALLOUT = "MATCHES HGR15R RAIL HOLES"
RAIL_ROW_CALLOUT = "HOLES IN LINE\nFOR HGR15R RAIL"
# Rule 18: the screw's thread in the bar at least 1.5 major diameters.
RAIL_SCREW_ENGAGEMENT = trammel.RAIL_SCREW_LENGTH - trammel.RAIL_SCREW_SEAT_ABOVE_BASE
if RAIL_SCREW_ENGAGEMENT < 1.5 * THREAD_MAJOR_MM[RAIL_SCREW]:
    raise AssertionError("the rail screws engage the bar under 1.5D")
if RAIL_SCREW_ENGAGEMENT > BAR_THICK - printed_band_mm(
    trammel.BASE_BAR_THICK_PLACES, unit=UNIT
):
    raise AssertionError("the rail screws stand out of the bar's underside")

# --- Hold-down slots ------------------------------------------------------------
SLOT_WIDTH = trammel.HOLD_DOWN_SLOT_WIDTH  # ⚙ .53
SLOT_RUN = 2.0 * trammel.HOLD_DOWN_ADJUST  # ⚙ .16: the stud's travel along the slot
SLOT_LENGTH = SLOT_RUN + SLOT_WIDTH  # .69 overall
SLOT_LATERAL = trammel.HOLD_DOWN_LATERAL  # ⚙ 1.48
NEAR_SLOT_X = trammel.HOLD_DOWN_NEAR_S - trammel.RAIL_NEAR_S  # ⚙ closure, prints .87
FAR_SLOT_X = trammel.HOLD_DOWN_FAR_S - trammel.RAIL_NEAR_S  # ⚙ 15.35
HOLD_DOWN_STUD_DIA = 0.5 * INCH  # 1/2-13 T-slot stud

# The part as modelled is the rail-1 bar; the rail-2 bar is it turned over.
NEAR_SLOT_Y = -SLOT_LATERAL
FAR_SLOT_Y = SLOT_LATERAL
QUANTITY = 2


def slot_rise(y_centre: float) -> float:
    """A slot's lower end centre above the bar's -Y side: the located value."""
    return y_centre - SLOT_RUN / 2.0 - LOW_SIDE_Y


NEAR_SLOT_RISE = slot_rise(NEAR_SLOT_Y)  # 1.94, from the -Y side
FAR_SLOT_RISE = slot_rise(FAR_SLOT_Y)  # 4.90, from the -Y side too

# --- Printed places and rule-17 walls -------------------------------------------
# Every length, station and slot size a wall reads prints at the title
# block's .XX; the inch .X is for unread features only.
STATION_PLACES = 2
SLOT_PLACES = 2
THICK_PLACES = trammel.BASE_BAR_THICK_PLACES  # .47 at .XX
_XX = printed_band_mm(SLOT_PLACES, unit=UNIT)
# The narrowest printed slot still passes the 1/2 in stud.
if SLOT_WIDTH - _XX <= HOLD_DOWN_STUD_DIA:
    raise AssertionError("the slot's low limit binds the 1/2-13 hold-down stud")
_R_MAX = (SLOT_WIDTH + _XX) / 2.0
NEAR_END_WALL = NEAR_SLOT_X - SLOT_WIDTH / 2.0
NEAR_END_WALL_WORST = NEAR_SLOT_X - _deviation(NEAR_SLOT_X, STATION_PLACES) - _R_MAX
# The rail sits off the bar's centreline, so each slot has its own side wall:
# the near slot's to the -Y side, the far slot's to the +Y side.
NEAR_SIDE_WALL = NEAR_SLOT_RISE - SLOT_WIDTH / 2.0
FAR_SIDE_WALL = BAR_WIDTH - (FAR_SLOT_RISE + SLOT_RUN) - SLOT_WIDTH / 2.0
SIDE_WALL = min(NEAR_SIDE_WALL, FAR_SIDE_WALL)
# Both slots are located from the -Y side (c3-r6, rule 10), so the far slot's
# wall to the +Y side carries the width's .XX, its rise's and its run's.
FAR_SIDE_WALL_WORST = (
    (BAR_WIDTH - BAR_WIDTH_BAND) - (FAR_SLOT_RISE + _XX + SLOT_RUN + _XX) - _R_MAX
)
SIDE_WALL_WORST = min(NEAR_SLOT_RISE - _XX - _R_MAX, FAR_SIDE_WALL_WORST)
for _label, _worst in (
    ("near slot to the bar end", NEAR_END_WALL_WORST),
    ("slot end to the bar side", SIDE_WALL_WORST),
):
    if _worst < WALL_TARGET_MM:
        raise AssertionError(f"base bar wall {_label}: {_worst:.3f} worst")
# The slots stay clear of the rail holes' row and of the rail's footprint.
if SLOT_LATERAL - SLOT_RUN / 2.0 - _R_MAX <= trammel.RAIL_WIDTH / 2.0:
    raise AssertionError("a hold-down slot runs under the rail")

# --- End bracket holes (PR C4) -------------------------------------------
# The two TL-28 brackets' #8-32 x 5/8 SHCS, fitted up through the bar before it
# goes on the table. Positions: ``ch_rocker_arm_tl_vn_oblique_leadscrew_spec``'s
# BASE_BAR_HOLES, which imports this module; only the build, drawing and test
# read them, and pass them to ``bracket_hole_walls``.
BRACKET_SCREW = "#8"
BRACKET_HOLE_FIT = "normal"
BRACKET_HOLE_DIA = CLEARANCE_MM[(BRACKET_SCREW, BRACKET_HOLE_FIT)]  # .196
BRACKET_SCREW_HEAD_DIA = 0.270 * INCH  # #8 SHCS head, ASME B18.3 max
BRACKET_SCREW_HEAD_HEIGHT = 0.164 * INCH
BRACKET_CBORE_DIA = 7.9502  # .313, the 5/16 counterbore
BRACKET_CBORE_DEPTH = 4.8006  # .189: the head sinks at the shallowest print
BRACKET_HOLE_SPEC = HoleSpec(
    "counterbore_socket",
    BRACKET_SCREW,
    fit=BRACKET_HOLE_FIT,
    overrides_mm={
        "HoleDiameter": BRACKET_HOLE_DIA,
        "CounterBoreDiameter": BRACKET_CBORE_DIA,
        "CounterBoreDepth": BRACKET_CBORE_DEPTH,
    },
)
# Rows at .XXX: their spacings must hold TL-28's four tapped holes inside the
# screws' float. Every Hole Wizard length prints .XXX. The stations are the
# KP08's along the Tr8 screw (owner ruling 4): exact millimetres, each
# stating the millimetre title block's three-place band. Whole millimetres,
# they print two places like the rail row (machinist review: a third place
# adds nothing under an explicit band).
BRACKET_HOLE_PLACES = 3
BRACKET_STATION_PLACES = 2
BRACKET_STATION_BAND = printed_band_mm(3, unit=METRIC_UNIT)  # 0.13
BRACKET_CBORE_PLACES = 3
BRACKET_CALLOUT_PRECISION = {
    "hw-thruholedia": 3,
    "hw-cbdia": BRACKET_CBORE_PLACES,
    "hw-cbdepth": BRACKET_CBORE_PLACES,
}
BRACKET_MATE = "MHA-CH-06-TL-28"
# The plan looks at the top face; the counterbores open on the underside.
BRACKET_CALLOUT_PROCESS = f"MATCHES {BRACKET_MATE}\nDRILL, C'BORE FAR SIDE\n"
_XXX = printed_band_mm(BRACKET_HOLE_PLACES, unit=UNIT)
_CB = printed_band_mm(BRACKET_CBORE_PLACES, unit=UNIT)
_THICK_BAND = printed_band_mm(THICK_PLACES, unit=UNIT)
# Public for the leadscrew layout's rule-17 window (ruling A′): a hole's .XXX
# band and the counterbore's largest printed radius.
BRACKET_HOLE_BAND = _XXX
BRACKET_CBORE_RADIUS_MAX = (BRACKET_CBORE_DIA + _CB) / 2.0
BRACKET_HEAD_RECESS_MIN = BRACKET_CBORE_DEPTH - _CB - BRACKET_SCREW_HEAD_HEIGHT
BRACKET_HEAD_CLEARANCE_MIN = BRACKET_CBORE_DIA - _CB - BRACKET_SCREW_HEAD_DIA
BRACKET_HEAD_BEARING_MIN = (
    BRACKET_SCREW_HEAD_DIA - (BRACKET_HOLE_DIA + drilled_oversize_mm(unit=UNIT))
) / 2.0
BRACKET_CBORE_FLOOR_MIN = BAR_THICK - _THICK_BAND - (BRACKET_CBORE_DEPTH + _CB)
if BRACKET_HEAD_RECESS_MIN < 0.1:
    raise AssertionError("a bracket screw head can stand proud of the underside")
if BRACKET_HEAD_CLEARANCE_MIN < 0.25:
    raise AssertionError("the bracket counterbore does not clear the screw head")
if BRACKET_HEAD_BEARING_MIN < 0.5:
    raise AssertionError("the bracket screw head bears on under 0.5 a side")
if BRACKET_CBORE_FLOOR_MIN < WALL_TARGET_MM:
    raise AssertionError("the bracket counterbore floor is under rule 17's .080")
BRACKET_WALL_MIN = WALL_FLOOR_MM  # rule 17, worst case


def bracket_screw_under_head(screw_length: float) -> tuple[float, float]:
    """The screw's reach past the bar's top (min, max) at the printed bands:
    its length less the bar left under the counterbore."""
    return (
        screw_length - (BAR_THICK + _THICK_BAND - (BRACKET_CBORE_DEPTH - _CB)),
        screw_length - (BAR_THICK - _THICK_BAND - (BRACKET_CBORE_DEPTH + _CB)),
    )


def bracket_hole_walls(holes: tuple[tuple[float, float], ...]) -> dict[str, float]:
    """Rule-17 walls round the bracket counterbores (the widest cut of each
    hole), worst case at the printed bands and roundings, for part-frame hole
    centres."""

    def station(x: float) -> float:
        return _deviation(
            x, BRACKET_STATION_PLACES, BRACKET_STATION_BAND, unit=METRIC_UNIT
        )

    def row(y: float) -> float:
        return _deviation(y - LOW_SIDE_Y, BRACKET_HOLE_PLACES)

    def position(x: float, y: float) -> float:
        return math.hypot(station(x), row(y))  # a hole's corner of its square

    # A rail tap's station holds its band but its row only the title block's
    # .XX (c3-r7): the row moves all seven taps against these holes' rows.
    rail_position = math.hypot(RAIL_HOLE_POSITION_RADIUS, _XX)
    radius = BRACKET_CBORE_RADIUS_MAX
    # Both slots: station and rise at .XX from the -Y side, as the holes' rows.
    slots = (
        (
            NEAR_SLOT_X,
            NEAR_SLOT_Y,
            math.hypot(_deviation(NEAR_SLOT_X, STATION_PLACES), _XX),
        ),
        (
            FAR_SLOT_X,
            FAR_SLOT_Y,
            math.hypot(_deviation(FAR_SLOT_X, STATION_PLACES), _XX),
        ),
    )
    length_band = _deviation(BAR_LENGTH, STATION_PLACES)
    return {
        "-Y edge": min(y - LOW_SIDE_Y - row(y) for _, y in holes) - radius,
        "+Y edge": min(
            BAR_WIDTH - BAR_WIDTH_BAND - (y - LOW_SIDE_Y + row(y)) for _, y in holes
        )
        - radius,
        "spindle end": min(x - station(x) for x, _ in holes) - radius,
        "far end": min(BAR_LENGTH - length_band - (x + station(x)) for x, _ in holes)
        - radius,
        "neighbour counterbore": min(
            math.dist(a, b) - position(*a) - position(*b)
            for i, a in enumerate(holes)
            for b in holes[i + 1 :]
        )
        - 2.0 * radius,
        "rail tap": min(
            math.hypot(x - rx, y) - position(x, y)
            for x, y in holes
            for rx in RAIL_HOLE_X
        )
        - rail_position
        - radius
        - THREAD_MAJOR_MM[RAIL_SCREW] / 2.0,
        "hold-down slot": min(
            math.hypot(x - sx, max(0.0, abs(y - sy) - SLOT_RUN / 2.0))
            - slot_position
            - position(x, y)
            for x, y in holes
            for sx, sy, slot_position in slots
        )
        - _R_MAX
        - radius,
    }


# --- Drawing contract ----------------------------------------------------------
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BarProfile": {
        "BarLength",
        "BarWidth",
        "SlotWidth",
        "SlotRun",
        "NearSlotX",
        "NearSlotRise",
        "FarSlotX",
        "FarSlotRise",
    },
    "Bar": {"BarThick"},
    "RailHoles": {f"RailHole{k}X" for k in range(1, len(RAIL_HOLE_X) + 1)},
    "RailRowReference": {"RailRowY"},
    # The bracket rows' stations (one per KP08 station) from the spindle-end
    # face, and the four rows from the faced -Y edge (the hidden reference
    # sketch; ruling A′: four screws a bracket).
    "BracketHoles": {"BracketHole1X", "BracketHole5X"},
    "BracketRowReference": {f"BracketRow{k}Y" for k in range(1, 5)},
}
# The width is milled to size (owner ruling #2083) and the thickness faced
# (owner ruling 2026-10-30): both take the title block's .XX band; the rail
# row's height takes it too (c3-r7).
# The metric vendor lines' stations (owner ruling 4): (feature, dimension) ->
# (millimetre places, symmetric band mm). The rail holes' carries the one
# tight band (the rail's pitch).
METRIC_DIMENSIONS: dict[tuple[str, str], tuple[int, float]] = {
    **{
        ("RailHoles", name): (RAIL_HOLE_PLACES, RAIL_HOLE_BAND)
        for name in sorted(DRAWING_DIMENSIONS["RailHoles"])
    },
    **{
        ("BracketHoles", name): (BRACKET_STATION_PLACES, BRACKET_STATION_BAND)
        for name in sorted(DRAWING_DIMENSIONS["BracketHoles"])
    },
}
_PLACES = {
    "SlotWidth": SLOT_PLACES,
    "SlotRun": SLOT_PLACES,
    "BarThick": THICK_PLACES,
    "BarWidth": WIDTH_PLACES,
    "RailRowY": RAIL_ROW_PLACES,
    **{name: BRACKET_HOLE_PLACES for name in DRAWING_DIMENSIONS["BracketRowReference"]},
    **{name: places for (_feature, name), (places, _band) in METRIC_DIMENSIONS.items()},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    feature: {name: _PLACES.get(name, STATION_PLACES) for name in names}
    for feature, names in DRAWING_DIMENSIONS.items()
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked base bar dimension needs authored places")

# Both large faces are static locating seats (rule 6, Ra 125 µin): bar 1's
# underside on the mill table and its top under the rail and the TL-28
# brackets; bar 2, the same part turned over, the other way round.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "top_seat", SEAT_UM, PlanarFace((0.0, 0.0, 1.0), BAR_THICK), display_unit=UNIT
    ),
    SurfaceFinishControl(
        "underside_seat", SEAT_UM, PlanarFace((0.0, 0.0, -1.0), 0.0), display_unit=UNIT
    ),
)
# Why both faces carry a seat finish: each seats on the table or under the
# rail, depending on the bar (rule 7: say why, beside the symbols).
SEAT_FINISH_REASON = "TABLE AND RAIL SEATS"
# No general note: the seats' reason rides their symbols and the rail holes'
# mate rides their callout.
DRAWING_NOTES = ""
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:5"
