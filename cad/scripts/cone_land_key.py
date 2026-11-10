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
to the far side of the bore), both sizes a micrometer reads across the part.
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
# at S = .3385 +.0000/-.0040, the row for a milled step located from its
# datum (.004 wide).  S and T are both printed at their rows, so their
# nominals are set from the limits that matter: T's largest keeps the gears'
# webs where the owner ruled them, and S's largest keeps half the key below
# the land's surface at the keyseat's edge on the smallest land (the guard
# below; .3391 left .7898 against the key's .7938 half, Codjiflo review of
# PR #2331) and the key's top under T's smallest.  .0365 deep at the
# keyseat's centreline (the research's square-key seat).
KEYSEAT_WIDTH_MM = KEY_SIZE_MM
KEYSEAT_WIDTH_BAND = (0.0508, 0.0)  # +.0020/-.0000
KEYSEAT_S_MM = 8.5979  # .3385
KEYSEAT_S_BAND = (0.0, -0.1016)  # +.0000/-.0040
KEYSEAT_PLACES = 4
# Distance of the keyseat floor from the land's axis, on +X.
KEYSEAT_FLOOR_OFFSET_MM = KEYSEAT_S_MM - LAND_DIA_MM / 2.0
KEYSEAT_DEPTH_MM = LAND_DIA_MM - KEYSEAT_S_MM  # .0365 at the centreline

# Hub keyway: one pass of a 1/16 A broach, width +.0020/-.0000 (the shop
# table's milled-width row, .002 wide; machinist review of PR #2331 at
# 5994f29: a .001 band named no fit route), its top at T = .4045 +/-.0020
# from the bore's far side, the milled-step row (machinist review of PR
# #2331's follow-on run 20261110T001845485Z: +/-.0010 named no fit route):
# T's largest, .4065, is the one the keyed webs were ruled at; .0035 over
# the key at the nominals, never under zero at the limits.
KEYWAY_WIDTH_MM = KEY_SIZE_MM
KEYWAY_WIDTH_BAND = (0.0508, 0.0)  # +.0020/-.0000
KEYWAY_T_MM = 10.2743  # .4045
KEYWAY_T_BAND = (0.0508, -0.0508)  # +/-.0020
KEYWAY_PLACES = 4


def limits(nominal_mm: float, band: tuple[float, float]) -> tuple[float, float]:
    """(minimum, maximum) of ``nominal_mm`` under an (upper, lower) band."""
    return nominal_mm + band[1], nominal_mm + band[0]


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
# key at their maximum.  Positive: a gear always slides over the key.
KEY_TOP_RADIAL_CLEARANCE_MIN_MM = (
    limits(KEYWAY_T_MM, KEYWAY_T_BAND)[0]
    - limits(KEYSEAT_S_MM, KEYSEAT_S_BAND)[1]
    - limits(KEY_SIZE_MM, KEY_STOCK_BAND)[1]
)
if KEY_TOP_RADIAL_CLEARANCE_MIN_MM <= 0.0:
    raise AssertionError(
        f"the key's top reaches a keyway's top at the limits: "
        f"{KEY_TOP_RADIAL_CLEARANCE_MIN_MM:.4f} mm"
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

# The key's length.  The keyseat runs from the 64T seat (the collar's
# tip-side face, CollarEndPlane) to land 1's end, where it runs out into air
# over the Ø.250 land as the flat did.  The 1/16 end mill leaves its radius at
# the collar end, so the key's square south end sits one KEY_END_SET (half the
# keyseat) north of the collar face; its .XX length keeps its north end on
# land 1 within the title block's band, and T024's south face, one
# SEAT_STEP_SETBACK past land 1's end, captures it north.
KEY_END_SET_MM = KEYSEAT_WIDTH_MM / 2.0
KEY_LENGTH_MM = 115.316  # 4.54
KEY_LENGTH_PLACES = 2
