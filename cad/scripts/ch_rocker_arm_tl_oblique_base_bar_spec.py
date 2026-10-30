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

Material and stock: 6061-T6511 aluminium flat bar, 1/2 x 5-1/2 in (OnlineMetals
17666; ⚙ ``BASE_BAR_THICK`` 12.7 x ⚙ ``BASE_BAR_WIDTH`` 139.7), sawn and faced
to ⚙ ``BASE_BAR_LENGTH`` 440 (the rail's length; rail and bar are flush).
Width and thickness are left as supplied and print "STOCK". Overall stock size
440 x 139.7 x 12.7. The user's 2026-10-17 ruling (a) widened the bar from
1/2 x 4 to 1/2 x 6 so the leadscrew's TL-28 end brackets (PR C4) stand wholly
on bar 1; the 2026-10-30 ruling narrowed it to 1/2 x 5-1/2, the widest listed
OnlineMetals bar that fits the 6 in vise's stock hard jaws (5 3/4 in), keeping
the column-side edge and so the brackets.

Frame: origin at the bar's spindle-end face, on the rail axis, on the bottom
face; +X along the bar away from the spindle, +Y across it, +Z up
(right-handed). On rail 1 the part's y is minus the calculator's lateral
(``trammel.rail_point``, +lateral toward the column), so the column-side edge
⚙ ``BASE_BAR_COLUMN_EDGE`` (lateral +88.9) is the -Y side and the
operator-side edge ⚙ ``BASE_BAR_OPERATOR_EDGE`` (lateral -50.8) the +Y side:
the bar spans x 0 .. 440, y ``LOW_SIDE_Y`` -88.9 .. ``HIGH_SIDE_Y`` 50.8,
z 0 .. 12.7.

Rail holes: 7 x #8-32 UNC tapped THRU on the rail axis (y 0) at x = ⚙
``RAIL_HOLE_END`` + k * ⚙ ``RAIL_HOLE_PITCH`` (40 .. 400). The rail is a
custom 440 cut; its symmetric E = 40 end distance is the ORDER requirement,
an unverified vendor value until the supplier confirms the cut. The rail's
Ø4.5 holes take #8 socket screws (⚙ ``RAIL_SCREW``); a 3/4 in screw seats
⚙ 9.7 above the rail base, so 9.35 engages the bar (rule 18: at least
1.5D = 6.25).

Rail-hole bands (the one tight requirement): a #8 screw (Ø4.17) fixed in the
bar's tapped hole has only ``RAIL_SCREW_CLEARANCE`` 0.167 a side in the rail's
Ø4.5 hole (a fixed-fastener pattern), so every bar hole's position error plus
the rail's own must stay inside that radius. Every hole is located by DRO
absolutes from the two faced datums: its station from the spindle-end face
(40.00 .. 400.00) at 2 places ± ``RAIL_HOLE_BAND`` 0.08, the rail's pitch,
and the row from the faced -Y edge (``RAIL_ROW_Y`` 88.90, the column-side
edge's lateral) at the title block's .XX (``RAIL_ROW_PLACES``; c3-r7, rule
4: the row's height has no mate, the hold-down slots set the bar's place at
fit-up and the rail is indicated in). All seven holes are cut at the one DRO
Y setting, so the row's band moves the whole row, not one hole off another:
only the station band scatters the holes, ``RAIL_HOLE_POSITION_RADIUS``
0.08 from nominal, leaving ``RAIL_PATTERN_ALLOWANCE`` 0.087 radius for the
rail's own hole positions (an unverified vendor value). The outermost
station (400.00) carries the mate on a second line, "MATCHES HGR15R RAIL
HOLES", above the stack where no extension line crosses it. The row's 88.90
carries its reason (``RAIL_ROW_CALLOUT``): every hole in line with the
rail's straight row of Ø4.5 holes, which the one setting gives.

Hold-down slots: two through slots ⚙ ``HOLD_DOWN_SLOT_WIDTH`` 13.5 wide, axis
along Y, stud travel ± ⚙ ``HOLD_DOWN_ADJUST`` 2 (17.5 overall). Near slot centre
x = ⚙ ``HOLD_DOWN_NEAR_S`` - ⚙ ``RAIL_NEAR_S`` (20.92), far slot x = ⚙
``HOLD_DOWN_FAR_S`` - ⚙ ``RAIL_NEAR_S`` (390), each ± ⚙ ``HOLD_DOWN_LATERAL``
(37.5) off the rail axis. Per drawing-guidelines rule 12 the slots are
dimensioned to their radius centres: width 13.50 and the 4.00 between the two
end-arc centres, each centre carrying a printed centre mark, so the 4.00
reads as centre-to-centre and not as the slot's 17.5 overall length.

One part, one configuration, two off (Main's ruling): every feature goes
through, so the bar under rail 2 is the same part turned over (rotated 180°
about its X axis). Turning it over mirrors plan X and keeps lateral, so on
both bars the column-side edge stays on the column side, the near slot on
the near stud (lateral +37.5) and the rail row on the rail. The part as
modelled is the rail-1 bar: near slot at y -37.5, far slot at +37.5. Both
slots are located from the faced -Y side, the datum every hole uses, to
their lower end centres (c3-r6 review, rule 10: one datum per view): the
near slot's rise ``NEAR_SLOT_RISE`` 49.4, the far slot's ``FAR_SLOT_RISE``
124.4. On the 1/2 x 4 bar the far slot's wall to the +Y side, carrying the
stock width's band, fell to 1.2 worst (c4-r2), so it was dropped from the +Y
side. The 1/2 x 5-1/2 bar at the old ±3 travel fell to 1.18 worst again; the
2026-10-30 ruling cut the travel to ±2 rather than bring the +Y datum back.

Walls (rule 17, worst case at the printed bands): the near slot to the bar's
spindle end 14.2 nominal; a slot end to its bar side 4.55 nominal (the far
slot to the +Y side; the near slot to the -Y side is 42.65), 2.18 worst (the
far slot's: its rise, run and the stock width's bands all enter it).

End bracket holes (PR C4): 8 x #8 SHCS clearance (``BRACKET_HOLE_DIA``
4.978, normal fit) THRU, counterbored Ø7.94 x 4.80 from the UNDERSIDE, at
the leadscrew layout's ``BASE_BAR_HOLES`` (four in a row at each KP08
station, derived there; y -27.5, -44, -66 and -82.5, so rows 61.4, 44.9,
22.9 and 6.4 from the -Y edge). Four #8-32 x 5/8 SHCS per TL-28 bracket go
up through the bar into the bracket's tapped holes before the bar goes on
the table; the heads sit 0.12 or more below the underside. Since the
2026-10-17 widening (ruling A′) each bracket stands wholly on the bar, its
outer end flush with the -Y edge. Both bars carry the holes; on the
turned-over bar 2 the counterbores face up, unused. Stations and rows print
at .XXX (±0.13): the row's spacings must hold TL-28's tapped row inside the
screws' 0.406 float, so the callout names the mate. Worst-case walls
(``bracket_hole_walls``): counterbore to the -Y edge 2.05 (the rule-17
target, which bounds the outer screws' half-span), to the far end 6.85, to its
row neighbour 7.68, to the nearest rail tap and hold-down slot over 20;
counterbore floor 6.88.
"""

from __future__ import annotations

import math


from _hole_spec import CLEARANCE_MM, THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
import ch_rocker_arm_tl_oblique_trammel_spec as trammel

INCH = 25.4

BAR_THICK = trammel.BASE_BAR_THICK  # ⚙ 12.7
BAR_WIDTH = trammel.BASE_BAR_WIDTH  # ⚙ 139.7
BAR_LENGTH = trammel.BASE_BAR_LENGTH  # ⚙ 440
# The two long sides in the rail-1 part frame (y = -lateral): the rail sits
# off the centreline since the 2026-10-17 widening, so each side is read from
# its own calculator edge, never as half the width.
LOW_SIDE_Y = -trammel.BASE_BAR_COLUMN_EDGE  # ⚙ -88.9: the faced -Y, column side
HIGH_SIDE_Y = -trammel.BASE_BAR_OPERATOR_EDGE  # ⚙ 50.8: the +Y, operator side
if abs(HIGH_SIDE_Y - LOW_SIDE_Y - BAR_WIDTH) > 1e-9:
    raise AssertionError("the base bar's sides miss its stock width")

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
RAIL_ROW_Y = -LOW_SIDE_Y  # 88.90: the row (y 0) from the faced -Y edge
RAIL_HOLE_PLACES = 2
RAIL_HOLE_BAND = 0.08  # the stations only: the rail's hole pitch
# The row's height prints at the title block's band (c3-r7, rule 4): nothing
# mates with it, and the one DRO Y setting keeps the holes in line.
RAIL_ROW_PLACES = 2
RAIL_HOLE_DIA = 4.5  # HGR15R rail's screw hole (catalogue)
RAIL_SCREW_CLEARANCE = (RAIL_HOLE_DIA - THREAD_MAJOR_MM[RAIL_SCREW]) / 2.0  # 0.167
# One Y setting for the row: only the station band scatters hole from hole.
RAIL_HOLE_POSITION_RADIUS = RAIL_HOLE_BAND  # 0.08
RAIL_PATTERN_ALLOWANCE = RAIL_SCREW_CLEARANCE - RAIL_HOLE_POSITION_RADIUS  # 0.087
if RAIL_PATTERN_ALLOWANCE <= 0.0:
    raise AssertionError("the rail-hole position bands bind the rail screws")
RAIL_MATE_CALLOUT = "MATCHES HGR15R RAIL HOLES"
RAIL_ROW_CALLOUT = "HOLES IN LINE\nFOR HGR15R RAIL"
# Rule 18: the screw's thread in the bar at least 1.5 major diameters.
RAIL_SCREW_ENGAGEMENT = trammel.RAIL_SCREW_LENGTH - trammel.RAIL_SCREW_SEAT_ABOVE_BASE
if RAIL_SCREW_ENGAGEMENT < 1.5 * THREAD_MAJOR_MM[RAIL_SCREW]:
    raise AssertionError("the rail screws engage the bar under 1.5D")
if RAIL_SCREW_ENGAGEMENT > BAR_THICK:
    raise AssertionError("the rail screws stand out of the bar's underside")

# --- Hold-down slots ------------------------------------------------------------
SLOT_WIDTH = trammel.HOLD_DOWN_SLOT_WIDTH  # ⚙ 13.5
SLOT_RUN = 2.0 * trammel.HOLD_DOWN_ADJUST  # ⚙ 4: the stud's travel along the slot
SLOT_LENGTH = SLOT_RUN + SLOT_WIDTH  # 17.5 overall
SLOT_LATERAL = trammel.HOLD_DOWN_LATERAL  # ⚙ 37.5
NEAR_SLOT_X = trammel.HOLD_DOWN_NEAR_S - trammel.RAIL_NEAR_S  # ⚙ 20.92
FAR_SLOT_X = trammel.HOLD_DOWN_FAR_S - trammel.RAIL_NEAR_S  # ⚙ 390
HOLD_DOWN_STUD_DIA = 0.5 * INCH  # 1/2-13 T-slot stud

# The part as modelled is the rail-1 bar; the rail-2 bar is it turned over.
NEAR_SLOT_Y = -SLOT_LATERAL
FAR_SLOT_Y = SLOT_LATERAL
QUANTITY = 2


def slot_rise(y_centre: float) -> float:
    """A slot's lower end centre above the bar's -Y side: the located value."""
    return y_centre - SLOT_RUN / 2.0 - LOW_SIDE_Y


NEAR_SLOT_RISE = slot_rise(NEAR_SLOT_Y)  # 49.4, from the -Y side
FAR_SLOT_RISE = slot_rise(FAR_SLOT_Y)  # 124.4, from the -Y side too

# --- Printed places and rule-17 walls -------------------------------------------
STATION_PLACES = 1  # bar length, width and slot stations: the title block's .X band
SLOT_PLACES = 2  # slot width and run: the .XX band
THICK_PLACES = 2  # the 1/2 in stock thickness prints 12.70 (the feed lever's)
_X = printed_band_mm(STATION_PLACES)
_XX = printed_band_mm(SLOT_PLACES)
# The narrowest printed slot still passes the 1/2 in stud.
if SLOT_WIDTH - _XX <= HOLD_DOWN_STUD_DIA:
    raise AssertionError("the slot's low limit binds the 1/2-13 hold-down stud")
_R_MAX = (SLOT_WIDTH + _XX) / 2.0
NEAR_END_WALL = NEAR_SLOT_X - SLOT_WIDTH / 2.0  # 14.2 nominal
NEAR_END_WALL_WORST = NEAR_SLOT_X - _X - _R_MAX
# The rail sits off the bar's centreline, so each slot has its own side wall:
# the near slot's to the -Y side (42.65), the far slot's to the +Y side (4.55).
NEAR_SIDE_WALL = NEAR_SLOT_RISE - SLOT_WIDTH / 2.0
FAR_SIDE_WALL = BAR_WIDTH - (FAR_SLOT_RISE + SLOT_RUN) - SLOT_WIDTH / 2.0
SIDE_WALL = min(NEAR_SIDE_WALL, FAR_SIDE_WALL)  # 4.55
# Both slots are located from the -Y side (c3-r6, rule 10), so the far slot's
# wall to the +Y side carries the stock width's .X band, its rise's and its
# run's .XX: 2.175 worst on the 1/2 x 5-1/2 bar at ±2 travel.
FAR_SIDE_WALL_WORST = (
    (BAR_WIDTH - _X) - (FAR_SLOT_RISE + _X + SLOT_RUN + _XX) - _R_MAX
)  # 2.175
SIDE_WALL_WORST = min(NEAR_SLOT_RISE - _X - _R_MAX, FAR_SIDE_WALL_WORST)
for _label, _nominal, _worst in (
    ("near slot to the bar end", NEAR_END_WALL, NEAR_END_WALL_WORST),
    ("slot end to the bar side", SIDE_WALL, SIDE_WALL_WORST),
):
    if _nominal < 2.0 or _worst < 1.5:
        raise AssertionError(
            f"base bar wall {_label}: {_nominal:.2f} nominal, {_worst:.2f} worst"
        )
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
BRACKET_HOLE_DIA = CLEARANCE_MM[(BRACKET_SCREW, BRACKET_HOLE_FIT)]  # 4.978
BRACKET_SCREW_HEAD_DIA = 0.270 * INCH  # #8 SHCS head, ASME B18.3 max: 6.858
BRACKET_SCREW_HEAD_HEIGHT = 0.164 * INCH  # 4.166
BRACKET_CBORE_DIA = 7.94  # 5/16 in
BRACKET_CBORE_DEPTH = 4.80  # the shallowest printed depth still sinks the head
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
# Stations and rows at .XXX (±0.13 a side): the row's spacings must hold
# TL-28's four tapped holes inside the screws' 0.406 float.
BRACKET_HOLE_PLACES = 3
BRACKET_CBORE_PLACES = 2
BRACKET_CALLOUT_PRECISION = {
    "hw-thruholedia": 2,
    "hw-cbdia": BRACKET_CBORE_PLACES,
    "hw-cbdepth": BRACKET_CBORE_PLACES,
}
BRACKET_MATE = "MHA-CH-06-TL-28"
# The plan looks at the top face; the counterbores open on the underside.
BRACKET_CALLOUT_PROCESS = f"MATCHES {BRACKET_MATE}\nDRILL, C'BORE FAR SIDE\n"
_XXX = printed_band_mm(BRACKET_HOLE_PLACES)
_CB = printed_band_mm(BRACKET_CBORE_PLACES)
# Public for the leadscrew layout's rule-17 window (ruling A′): a hole's .XXX
# band and the counterbore's largest printed radius.
BRACKET_HOLE_BAND = _XXX
BRACKET_CBORE_RADIUS_MAX = (BRACKET_CBORE_DIA + _CB) / 2.0
BRACKET_HEAD_RECESS_MIN = BRACKET_CBORE_DEPTH - _CB - BRACKET_SCREW_HEAD_HEIGHT
BRACKET_HEAD_CLEARANCE_MIN = BRACKET_CBORE_DIA - _CB - BRACKET_SCREW_HEAD_DIA
BRACKET_HEAD_BEARING_MIN = (
    BRACKET_SCREW_HEAD_DIA - (BRACKET_HOLE_DIA + drilled_oversize_mm())
) / 2.0
BRACKET_CBORE_FLOOR_MIN = (
    BAR_THICK - printed_band_mm(THICK_PLACES) - (BRACKET_CBORE_DEPTH + _CB)
)
if BRACKET_HEAD_RECESS_MIN < 0.1:
    raise AssertionError("a bracket screw head can stand proud of the underside")
if BRACKET_HEAD_CLEARANCE_MIN < 0.25:
    raise AssertionError("the bracket counterbore does not clear the screw head")
if BRACKET_HEAD_BEARING_MIN < 0.5:
    raise AssertionError("the bracket screw head bears on under 0.5 a side")
if BRACKET_CBORE_FLOOR_MIN < 1.5:
    raise AssertionError("the bracket counterbore floor is under rule 17's 1.5")
BRACKET_WALL_MIN = 1.5  # rule 17, worst case


def bracket_screw_under_head(screw_length: float) -> tuple[float, float]:
    """The screw's reach past the bar's top (min, max) at the printed bands:
    its length less the bar left under the counterbore."""
    thick = printed_band_mm(THICK_PLACES)
    return (
        screw_length - (BAR_THICK + thick - (BRACKET_CBORE_DEPTH - _CB)),
        screw_length - (BAR_THICK - thick - (BRACKET_CBORE_DEPTH + _CB)),
    )


def bracket_hole_walls(holes: tuple[tuple[float, float], ...]) -> dict[str, float]:
    """Rule-17 walls round the bracket counterbores (the widest cut of each
    hole), worst case at the printed bands, for part-frame hole centres."""
    position = math.hypot(_XXX, _XXX)  # a hole's corner of its .XXX square
    # A rail tap's station holds ±0.08 but its row only the title block's .XX
    # (c3-r7): the row moves all seven taps against these holes' .XXX rows.
    rail_position = math.hypot(RAIL_HOLE_BAND, printed_band_mm(RAIL_ROW_PLACES))
    radius = BRACKET_CBORE_RADIUS_MAX
    xs = [x for x, _ in holes]
    rows = [y - LOW_SIDE_Y for _, y in holes]  # from the faced -Y edge
    # Both slots: station and rise at .X from the -Y side, as the holes' rows
    # (c3-r6: the far slot's drop from the +Y side, which added the stock
    # width's band, became a rise).
    slots = (
        (NEAR_SLOT_X, NEAR_SLOT_Y, math.hypot(_X, _X)),
        (FAR_SLOT_X, FAR_SLOT_Y, math.hypot(_X, _X)),
    )
    return {
        "-Y edge": min(rows) - _XXX - radius,
        "+Y edge": BAR_WIDTH - _X - (max(rows) + _XXX) - radius,
        "spindle end": min(xs) - _XXX - radius,
        "far end": BAR_LENGTH - _X - (max(xs) + _XXX) - radius,
        "neighbour counterbore": min(
            math.dist(a, b) for i, a in enumerate(holes) for b in holes[i + 1 :]
        )
        - 2.0 * position
        - 2.0 * radius,
        "rail tap": min(math.hypot(x - rx, y) for x, y in holes for rx in RAIL_HOLE_X)
        - position
        - rail_position
        - radius
        - THREAD_MAJOR_MM[RAIL_SCREW] / 2.0,
        "hold-down slot": min(
            math.hypot(x - sx, max(0.0, abs(y - sy) - SLOT_RUN / 2.0)) - slot_position
            for x, y in holes
            for sx, sy, slot_position in slots
        )
        - position
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
# The bar's width and thickness are the flat bar as bought: "STOCK" under them.
STOCK_DIMENSIONS = frozenset({"BarWidth", "BarThick"})
# The rail holes' stations carry the one tight band (the rail's pitch); the
# row's height takes the title block's (c3-r7): (feature, dimension) ->
# symmetric band.
TOLERANCES: dict[tuple[str, str], float] = {
    ("RailHoles", name): RAIL_HOLE_BAND
    for name in sorted(DRAWING_DIMENSIONS["RailHoles"])
}
_PLACES = {
    "SlotWidth": SLOT_PLACES,
    "SlotRun": SLOT_PLACES,
    "BarThick": THICK_PLACES,
    "RailRowY": RAIL_ROW_PLACES,
    **{name: RAIL_HOLE_PLACES for _feature, name in TOLERANCES},
    **{
        name: BRACKET_HOLE_PLACES
        for feature in ("BracketHoles", "BracketRowReference")
        for name in DRAWING_DIMENSIONS[feature]
    },
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

SURFACE_FINISHES = ()
# No general note: the stock sizes say STOCK and the rail holes' mate rides
# their callout.
DRAWING_NOTES = ""
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:5"
