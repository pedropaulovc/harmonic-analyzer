"""The land-1 key on the cone gear shaft (MHA-DT-04) and its hub keyways.

Owner decision C1 keyed, 2026-11-09 (PR #1992, research
``research/3-detailed-design/drive-train-cone-tip-options.md``): one 1/16 in
square key, purchased key stock cut to length (MHA-DT-VN-71), sits in a
keyseat milled along MHA-DT-04's Ø.375 land 1 and drives T030..T120
(MHA-DT-03) and the 64T (MHA-DT-07), each broached for it with a stock 1/16 A
broach and a 3/8 A bushing.  It replaces land 1's D-flat (user ruling
2026-09-28, superseded).  ANSI B17.1 gives a 3/32 key for a 3/8 shaft; that
leaves T030 a .052 web, under rule 17's floor, so the owner took the 1/16 key.

Dimensioning follows ANSI B17.1: the keyseat by its width and S (keyseat floor
to the far side of the land), each hub keyway by its width and T (keyway top
to the far side of the bore).  Neither is a micrometer reading: the anvils do
not enter a .0625 slot.  S is read with calipers over the key laid in the
keyseat, less the key's own height; T as .375 plus the largest pin gauge that
passes between the keyway's top and a .375 pin held on the bore's far side
(the shop's .001-step pin set, cad/process/shop.toml).
The key, keyseat and keyways are centred on each part's local +X (its Right
Plane normal), the clock the land-1 D-flat held, so the gears keep their tooth
phase to the shaft.

Radial clearance between the key's top and a keyway's top is T - S - H with
the hub's far side on the land's far side, the worst case whatever the two
diameters; the band below keeps it positive at every printed limit.  The
keyway's corner, not its centreline, is nearest a gear's root: the web the
gear families book is ``hub_keyway_corner_radius_max_mm`` under the minimum
root envelope.

Its own small module so only its importers re-key.
"""

from __future__ import annotations

import math

MM_PER_IN = 25.4

# Land 1: the Ø.375 seat of the 64T and T030..T120.  The shaft spec's
# SECTION_DIAS[1] reads this number; its diameter band is
# cone_shaft_land_bands.GEAR_SEAT_BAND and every bore on it takes
# gear_seat_fit.seat_bore_band of that band.
LAND_DIA_MM = 9.525  # 3/8

# 1/16 square key stock (ANSI B17.1 square key), undersized so the key slides
# in a keyway broached at the broach's least width: +.000/-.002 on width and
# height.  (upper, lower) deviations, mm.
KEY_SIZE_MM = 1.5875  # 1/16
KEY_STOCK_BAND = (0.0, -0.0508)  # +.000/-.002

# Shaft keyseat: milled with a 1/16 end mill, width +.0020/-.0000 (the shop
# table's milled-width row, .002 wide: the key slides in any keyseat a 1/16
# end mill cuts, so the width needs no tighter band and no fit route), floor
# at S = .3355 +.0000/-.0040, the row for a milled step located from its
# datum (.004 wide).  S follows the broached keyway below: its largest is
# T's smallest less the largest key and the .0015 top clearance PR #2331 set
# (.3995 - .0625 - .0015 = .3355).  .0395 deep at the keyseat's centreline,
# .0044 deeper than ANSI B17.1's S for this key and land (.3411, below):
# B17.1 keeps the standard shaft keyseat under a shallow hub, but here
# .3411 + .0625 = .4036 stands over the broach's shallowest cut.
KEYSEAT_WIDTH_MM = KEY_SIZE_MM
KEYSEAT_WIDTH_BAND = (0.0508, 0.0)  # +.0020/-.0000
KEYSEAT_S_MM = 8.5217  # .3355
KEYSEAT_S_BAND = (0.0, -0.1016)  # +.0000/-.0040
KEYSEAT_PLACES = 4
# Distance of the keyseat floor from the land's axis, on +X.
KEYSEAT_FLOOR_OFFSET_MM = KEYSEAT_S_MM - LAND_DIA_MM / 2.0
KEYSEAT_DEPTH_MM = LAND_DIA_MM - KEYSEAT_S_MM  # .0395 at the centreline

# Hub keyway: one pass of a 1/16 A broach, width +.0020/-.0000 (the shop
# table's milled-width row, .002 wide; machinist review of PR #2331 at
# 5994f29: a .001 band named no fit route), its top at T = .4030 +/-.0035
# from the bore's far side.  The broach sets T.  A 1/16 A broach in its 3/8
# A bushing cuts its full depth in one pass with no shim (duMONT catalogue:
# no shims for the 1/16-A); the published depth is 0.70 mm (Rev Broaching
# Tool's duMONT table, "Standard broaches for keyway - inch sizes", 1/16"-A
# row, read live 2026-11-10), BROACH_DEPTH_MM across its 0.01 mm rounding.
# The table names no reference, so the band holds every reading of it
# (test_dt_cone_gear_seat_fit): from the bore's far side, or from the
# bushing's 3/8 circle when the cut pushes the bushing onto that side; at the
# keyway's centreline, or at its walls, where ANSI B17.1 takes depth and the
# circle stands its chord height Y below the centreline.  That is .3996
# (3/8 circle, widest cut's wall) to .4046 (largest bore, centreline).  The
# depth is taken as the broach-and-bushing pair's in a 3/8 bore: the
# bushing's own slide clearance is not published, and a bushing that sits
# low by it cuts T low by as much, which the first gear's T check finds and
# one more pass over a shim of that size makes up.  A one-pass broach
# cannot be set shallower, so the band's room is above the deepest reading:
# it stops at .4065, the T the keyed webs were ruled at
# (cad/config/parts/dt-cone-gear.yaml RV-07).  ANSI B17.1's T for this key
# and land, .4087 (below), would take T030's web under rule 17's floor.
KEYWAY_WIDTH_MM = KEY_SIZE_MM
KEYWAY_WIDTH_BAND = (0.0508, 0.0)  # +.0020/-.0000
KEYWAY_T_MM = 10.2362  # .4030
KEYWAY_T_BAND = (0.0889, -0.0889)  # +/-.0035
KEYWAY_PLACES = 4


def limits(nominal_mm: float, band: tuple[float, float]) -> tuple[float, float]:
    """(minimum, maximum) of ``nominal_mm`` under an (upper, lower) band."""
    return nominal_mm + band[1], nominal_mm + band[0]


# ANSI B17.1-1967 (R1998) depth control values, S = D - Y - H/2 and
# T = D - Y + H/2 + C, C = .005 for a parallel key (the formulas reproduce
# B17.1 Table 2, reprinted in Machinery's Handbook 26th ed. p. 2343: Ø1/2
# with a 1/8 key gives S .430 and T .560), for a 1/16 key on Ø.375: Y .0026,
# S .3411, T .4087.  Neither is printed (see above).
#
# The 1/16-A broach's published one-pass depth, (least, most) at the table's
# 0.01 mm rounding of 0.70 mm.
BROACH_DEPTH_MM = (0.695, 0.705)


def keyway_top_offset_mm(bore_dia_mm: float) -> float:
    """Nominal distance of a hub keyway's top from its bore axis, on +X."""
    return KEYWAY_T_MM - bore_dia_mm / 2.0


def hub_keyway_corner_radius_max_mm(bore_dia_min_mm: float) -> float:
    """Farthest point of a hub keyway from its bore axis at the print limits:
    the top corner, with T at its maximum, the bore at its minimum (the top
    measured from the bore's far side) and the broach at its widest."""
    top = limits(KEYWAY_T_MM, KEYWAY_T_BAND)[1] - bore_dia_min_mm / 2.0
    half = limits(KEYWAY_WIDTH_MM, KEYWAY_WIDTH_BAND)[1] / 2.0
    return math.hypot(top, half)


# The key's top under a keyway's top, worst case: T at its minimum, S and the
# key at their maximum.  At least .0015: a gear always slides over the key.
KEY_TOP_RADIAL_CLEARANCE_FLOOR_MM = 0.0381  # .0015
KEY_TOP_RADIAL_CLEARANCE_MIN_MM = (
    limits(KEYWAY_T_MM, KEYWAY_T_BAND)[0]
    - limits(KEYSEAT_S_MM, KEYSEAT_S_BAND)[1]
    - limits(KEY_SIZE_MM, KEY_STOCK_BAND)[1]
)
if KEY_TOP_RADIAL_CLEARANCE_MIN_MM < KEY_TOP_RADIAL_CLEARANCE_FLOOR_MM - 1e-9:
    raise AssertionError(
        f"the key's top comes within {KEY_TOP_RADIAL_CLEARANCE_MIN_MM:.4f} mm "
        "of a keyway's top at the limits"
    )
# Side clearances (minimum, maximum), each width against the key's.
KEYSEAT_SIDE_CLEARANCE_MM = (
    limits(KEYSEAT_WIDTH_MM, KEYSEAT_WIDTH_BAND)[0]
    - limits(KEY_SIZE_MM, KEY_STOCK_BAND)[1],
    limits(KEYSEAT_WIDTH_MM, KEYSEAT_WIDTH_BAND)[1]
    - limits(KEY_SIZE_MM, KEY_STOCK_BAND)[0],
)
KEYWAY_SIDE_CLEARANCE_MM = (
    limits(KEYWAY_WIDTH_MM, KEYWAY_WIDTH_BAND)[0]
    - limits(KEY_SIZE_MM, KEY_STOCK_BAND)[1],
    limits(KEYWAY_WIDTH_MM, KEYWAY_WIDTH_BAND)[1]
    - limits(KEY_SIZE_MM, KEY_STOCK_BAND)[0],
)
if min(KEYSEAT_SIDE_CLEARANCE_MM[0], KEYWAY_SIDE_CLEARANCE_MM[0]) < 0.0:
    raise AssertionError(
        "the key does not slide in its keyseat or keyways at the limits"
    )
# The key stays in the keyseat: its bottom on the floor, at least half its
# largest height below the land's surface at the keyseat's edge at every
# limit.  Worst case: the smallest land (cone_shaft_land_bands.GEAR_SEAT_BAND,
# 0/-.0020, mirrored here: that module reads this one), the widest keyseat,
# and S at its largest measured from the far side of that same smallest land,
# so the floor stands S_max - R_min from the axis.
_LAND_RADIUS_MIN_MM = (LAND_DIA_MM - 0.0508) / 2.0
KEYSEAT_EDGE_DEPTH_MIN_MM = math.sqrt(
    _LAND_RADIUS_MIN_MM**2
    - (limits(KEYSEAT_WIDTH_MM, KEYSEAT_WIDTH_BAND)[1] / 2.0) ** 2
) - (limits(KEYSEAT_S_MM, KEYSEAT_S_BAND)[1] - _LAND_RADIUS_MIN_MM)
if KEYSEAT_EDGE_DEPTH_MIN_MM < limits(KEY_SIZE_MM, KEY_STOCK_BAND)[1] / 2.0:
    raise AssertionError(
        f"the key's seat is {KEYSEAT_EDGE_DEPTH_MIN_MM:.4f} deep at its edge, "
        "under half the key"
    )

# The key's length.  The keyseat runs from near the 64T seat (the collar's
# tip-side face, CollarEndPlane) to land 1's end, where it runs out into air
# over the Ø.250 land as the flat did.  The 1/16 end mill closes it at the
# collar end with its own radius, centred KEY_END_SET north of the collar
# face (printed .XX, KEY_END_SET_PLACES): far enough that at the printed low
# limit the cutter still stands clear of that face, the 64T's seat and the
# cone stack's origin (Codjiflo #2331 4521933063: at .03, tangent in the
# model, the low limit sank the cutter .011 into it; the spec proves the
# clearance).  The key's square south end comes to rest on that centre line,
# where the keyseat first runs full width, so it shares the station.  Its .XX
# length keeps its north end on land 1 at nominal, and T024's south face, one
# SEAT_STEP_SETBACK past land 1's end, captures it north at the print-worst
# of both .XX lengths (the shaft spec's KEY_NORTH_MARGIN_MM).
KEY_END_SET_MM = 1.27  # .05
KEY_END_SET_PLACES = 2
KEY_LENGTH_MM = 123.444  # 4.86 in; #1038 re-pitch seed; S2a proves it
KEY_LENGTH_PLACES = 2
