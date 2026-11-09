"""TL-32 integral feed block, rail 1; same pivot/carriage interface as TL-22.

The bought brass flange nut supplied with the lead screw (the FeedNut of
leadscrew kit MHA-CH-06-TL-VN-84, ``ch_rocker_arm_tl_vn_oblique_leadscrew_kit_feed_nut_spec``; owner
ruling 2026-11-04, #2177 option B) seats flat on the lug's +X face, flush
with the block's +X end, its spigot faced off, so the lug needs no recess.
Four #4-40 X 5/8 flat heads
(MHA-CH-06-TL-VN-67) pass through the nut's countersunk flange holes into
the lug's four #4-40 taps, tapped THRU, on the nut's 16 mm PCD at 45° to the
lug's faces; all coordinates are block-local. The taps are transferred
through the seated nut at TL-00 assembly, with the nut threaded on the
aligned leadscrew (Main ruling 2026-11-03, Codjiflo P1 on #2112): the sheet
locates them only by that transfer callout, as it located the retired
dowel hole. The nut face's print locates the leadscrew clearance from the
lug end and the carriage face (``NutPatternReference``).

Issue #290: the sheet prints decimal inch. The lug outline (its -X face
from the -X edge, its end from the +Y edge; its +X face is the block's end)
and the screw clearance sit on the inch grid; the axis closes on the leadscrew's
(``NUT_AXIS_Y`` from its lateral, ``NUT_AXIS_Z`` = its height over the
carriage top). The axis height belongs to the metric-only KP08 vendor line,
so it prints exact millimetres, labelled mm (owner ruling 4, 2026-11-01;
``METRIC_DIMENSIONS``).
"""
from __future__ import annotations
import math
import _config
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_oblique_end_bracket_spec as end_bracket
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_arm_tl_vn_oblique_leadscrew_kit_feed_nut_spec as feed_nut
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as lead
from _hole_spec import HoleSpec, TAP_DRILL_MM, THREAD_MAJOR_MM
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm

PART_NAME = "ch-rocker-arm-tl-oblique-feed-block"
UNIT = drawing_unit(
    "parts/ch-rocker-arm-tl-oblique-feed-block",
    _config.parts("ch-rocker-arm-tl-oblique-feed-block"),
)
NUMBER = "MHA-CH-06-TL-32"
QUANTITY = 1
BLOCK_X0, BLOCK_X1 = pivot.BLOCK_X0, pivot.BLOCK_X1
BLOCK_LENGTH, BLOCK_WIDTH, BLOCK_HEIGHT = pivot.BLOCK_LENGTH, pivot.BLOCK_WIDTH, pivot.BLOCK_HEIGHT
PLAN_LUG_X = 22.098  # .87, the lug's -X face from the block's -X edge
PLAN_OVERALL_Y = 88.138  # 3.47, +Y edge to the lug end
# Owner ruling 2026-11-07 (via Main): the lug runs flush with the block's
# +X end, one continuous face. The c40296ac sheet's .87 + .73 = 1.60 lug end
# stood .04 short of the 1.64 head, a useless step. The lug's width is the
# remainder (.77), not a printed size: 1.64 and .87 locate both its faces.
LUG_X0 = BLOCK_X0 + PLAN_LUG_X
LUG_X1 = BLOCK_X1
LUG_WIDTH = LUG_X1 - LUG_X0  # 19.558, .77
LUG_Y1 = -BLOCK_WIDTH / 2
LUG_Y0 = BLOCK_WIDTH / 2 - PLAN_OVERALL_Y
LUG_LENGTH = LUG_Y1 - LUG_Y0
# The block-local plan outline, an L with no step: the lug's +X face and the
# block's +X end are one edge from the lug end to the +Y edge.
PLAN_OUTLINE = (
    (BLOCK_X0, LUG_Y1), (LUG_X0, LUG_Y1), (LUG_X0, LUG_Y0),
    (BLOCK_X1, LUG_Y0), (BLOCK_X1, BLOCK_WIDTH / 2), (BLOCK_X0, BLOCK_WIDTH / 2),
)
# Every edge axis-aligned and of real length, and every vertex a real
# corner: no zero-length step, no collinear split of the +X face.
_EDGE_VERTICAL = []
for _i, _start in enumerate(PLAN_OUTLINE):
    _end = PLAN_OUTLINE[(_i + 1) % len(PLAN_OUTLINE)]
    _flat = (abs(_end[0] - _start[0]) < 1e-9, abs(_end[1] - _start[1]) < 1e-9)
    if _flat not in ((True, False), (False, True)):
        raise AssertionError(f"TL-32 plan outline edge {_start} -> {_end} is not a real side")
    _EDGE_VERTICAL.append(_flat[0])
if any(_EDGE_VERTICAL[_i - 1] == _vertical for _i, _vertical in enumerate(_EDGE_VERTICAL)):
    raise AssertionError("TL-32 plan outline has a collinear split (a step or a seam)")
NUT_FACE_X = LUG_X1
NUT_AXIS_Y = -lead.SCREW_LATERAL
NUT_AXIS_Z = 12.4  # the leadscrew axis over the carriage top (checked below)
# .351: the smallest three-place drill that clears the Tr8 major at the
# vertical stack (LEADSCREW_RADIAL_CLEARANCE, below).
SCREW_CLEARANCE_DIA = 0.351 * 25.4  # 8.915
# The nut is turned 45° about its axis, so its four holes sit on the lug's
# diagonals (the owner's option-B sketch, 2026-11-04). The band binds EVERY
# tap, not one (Codjiflo 4477879822 on #2187): the supplier gives the holes
# no angular stations, so TL-00 step F1B sets all four holes within it before
# any tap is transferred and rejects a nut whose four cannot all be set there.
# The walls below charge each tap anywhere in the band. The band is a native
# angular dimension, NutClock on NutPatternReference (4477879826): from the
# centreline through the axis along +Z (square to the carriage face) to the
# (-Y, +Z) tap, VIEW D prints it 4X, and F1B cites that view.
NUT_CLOCK_DEG = 45.0
NUT_CLOCK_TOL_DEG = 5.0
NUT_CLOCK_DIMENSION = "NutClock"
NUT_CLOCK_TAP = 1  # NUT_HOLES_YZ's (-Y, +Z) tap, VIEW D's lower left
NUT_CLOCK_VIEW = "VIEW D"
_TAP_DIAGONAL = feed_nut.HOLE_PCD / 2 * math.cos(math.radians(NUT_CLOCK_DEG))
# The taps at the nominal nut, ordered (-Y, -Z), (-Y, +Z), (+Y, -Z), (+Y, +Z).
NUT_HOLES_YZ = tuple(
    (NUT_AXIS_Y + side_y * _TAP_DIAGONAL, NUT_AXIS_Z + side_z * _TAP_DIAGONAL)
    for side_y in (-1, 1)
    for side_z in (-1, 1)
)
NUT_TAP_SPEC = HoleSpec("tapped", feed_nut.SCREW_THREAD, end="through_all")
NUT_TAP_DRILL = TAP_DRILL_MM[feed_nut.SCREW_THREAD]
# The nut points away from the spindle; its screws enter from the +X face.
NUT_REACH_X = (LUG_X0, NUT_FACE_X + feed_nut.REACH)
NUT_MACHINE_Z = trammel.CARRIAGE_TOP_Z + NUT_AXIS_Z
PLAN_DATUM_REFERENCE = pivot.PLAN_DATUM_REFERENCE
CBORE_FLOOR_REFERENCE = pivot.CBORE_FLOOR_REFERENCE
# B-B prints the block height from the floor sketch's interior line (TL-22,
# whose sections never imported it, prints the Block extrusion's depth on a
# standard Right view).
# The plan's Y ordinates run from the full-width +Y edge, BlockSideY's and
# the hole rows' witnesses leaving the +X/+Y corner: the L's -Y edge is only
# the step left of the lug, and a +X/-Y witness left the lug's right edge,
# where no -Y edge exists (restack farm r4 20261108T055431582Z). The 1.58
# has no -Y end on the +X side either, so the plan prints the lug's length
# from the step face instead (3.47 - 1.89 locates the step); BlockWidth
# still drives BlockProfile. Main-approved 2026-11-08, dimensioning only.
PLAN_ROW_HOLES_FROM_TOP = {name: BLOCK_WIDTH / 2 - y for name, (_x, y) in pivot.PLAN_ROW_HOLES.items()}
DRAWING_VALUES = {k: v for k, v in pivot.DRAWING_VALUES.items() if k != "BlockHeight"} | PLAN_ROW_HOLES_FROM_TOP | {
    "SectionBlockHeight": BLOCK_HEIGHT,
    "PlanLugX": LUG_X0 - BLOCK_X0,
    "PlanOverallY": BLOCK_WIDTH / 2 - LUG_Y0,
    "PlanLugLength": LUG_LENGTH,
    "NutClearanceDia": SCREW_CLEARANCE_DIA,
    "NutCentreZ": NUT_AXIS_Z, "NutCentreY": NUT_AXIS_Y - LUG_Y0,
}
# VIEW D prints the clearance from the lug end and the carriage face, and the
# taps' clocking band; the taps' transfer callout locates them.
NUT_PATTERN_PRINTED = ("NutCentreZ", "NutCentreY", NUT_CLOCK_DIMENSION)
DRAWING_DIMENSIONS = {k: v for k, v in pivot.DRAWING_DIMENSIONS.items() if k != "Block"} | {
    "BlockProfile": tuple(name for name in pivot.DRAWING_DIMENSIONS["BlockProfile"] if name != "BlockWidth"),
    CBORE_FLOOR_REFERENCE: pivot.DRAWING_DIMENSIONS[CBORE_FLOOR_REFERENCE] + ("SectionBlockHeight",),
    PLAN_DATUM_REFERENCE: pivot.DRAWING_DIMENSIONS[PLAN_DATUM_REFERENCE] + ("PlanLugX", "PlanOverallY",
                                                                            "PlanLugLength"),
    "NutClearanceProfile": ("NutClearanceDia",),
    "NutPatternReference": NUT_PATTERN_PRINTED,
}
# The axis is the leadscrew's closure (not on the .01 grid): three places;
# its height is the KP08 vendor line's, exact millimetres (owner ruling 4).
# Owner ruling 2026-11-08 (Pedro), A2 option (i): the Ø.351 leadscrew
# clearance alone is located ±.002 in Y and Z on VIEW D (±.05 mm on its
# millimetre height), so its wall to the THRU taps holds the .060 floor with
# rule 17's drill wander charged; no geometry changes.
NUT_PATTERN_PLACES = 3
METRIC_UNIT = "mm"
METRIC_BAND = printed_band_mm(NUT_PATTERN_PLACES, unit=METRIC_UNIT)  # 0.13
NUT_CLEARANCE_BAND_Z = 0.05  # mm, NutCentreZ (.002 in is 0.0508)
NUT_CLEARANCE_BAND_Y = 0.002 * 25.4  # NutCentreY, inch
METRIC_DIMENSIONS = {("NutPatternReference", "NutCentreZ"): (NUT_PATTERN_PLACES, NUT_CLEARANCE_BAND_Z)}
INCH_TOLERANCED_DIMENSIONS = {("NutPatternReference", "NutCentreY"): (NUT_PATTERN_PLACES, NUT_CLEARANCE_BAND_Y)}
# The leadscrew clearance is drilled: inch drill sizes print three places.
THREE_PLACE_DIMENSIONS = pivot.THREE_PLACE_DIMENSIONS | {
    "NutClearanceDia", "NutCentreZ", "NutCentreY",
}
DRAWING_PRECISION = {k: v for k, v in pivot.DRAWING_PRECISION.items() if k != "Block"} | {
    "BlockProfile": {name: places for name, places in pivot.DRAWING_PRECISION["BlockProfile"].items()
                     if name in DRAWING_DIMENSIONS["BlockProfile"]},
} | {
    feature: {
        name: (
            0 if name == NUT_CLOCK_DIMENSION
            else 3 if name in THREE_PLACE_DIMENSIONS else 2
        )
        for name in DRAWING_DIMENSIONS[feature]
    }
    for feature in (CBORE_FLOOR_REFERENCE, PLAN_DATUM_REFERENCE,
                    "NutClearanceProfile", "NutPatternReference")
}
DRAWING_PRECISION_BY_NAME = {
    name: places for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
assert DRAWING_PRECISION_BY_NAME["NutCentreY"] == DRAWING_PRECISION_BY_NAME["NutCentreZ"] == NUT_PATTERN_PLACES
REFERENCE_SKETCHES = pivot.REFERENCE_SKETCHES + ("NutPatternReference",)
# The transferred taps' native callout leads with where they come from
# (MHA-FR-05's transferred seats); TL-00 says how.
TRANSFER_PROCESS = f"TRANSFER THROUGH {feed_nut.NUMBER}\nFEED NUT AT ASSEMBLY;\n"
# NutClock's two construction rays from the axis on NutPatternReference: the
# baseline along +Z and the ray to the NUT_CLOCK_TAP tap's centre, each the
# PCD radius long (unprinted), with the angle between them driving. Its count
# says the band holds at every tap; TL-00's F1B cites it by view.
NUT_CLOCK_RAY = feed_nut.HOLE_PCD / 2
CALLOUTS_PREFIX = {NUT_CLOCK_DIMENSION: f"{feed_nut.SCREW_COUNT}X "}
NUT_CLOCK_SHEET = 2  # VIEW D's, the 'Nut interface' sheet
NUT_CLOCK_REFERENCE = f"{NUMBER} SHEET {NUT_CLOCK_SHEET} {NUT_CLOCK_VIEW}"

# --- The leadscrew in the lug: the vertical stack the clearance absorbs ---------
# The KP08s seat on TL-28's as-bought 1 in thickness (±.012) and the lug's
# clearance stands 12.400 ±.05 mm over the carriage face, so the leadscrew may
# run LEADSCREW_OFFSET_Z (.355 mm) off the clearance's axis vertically
# (Codjiflo P1 on #2112); laterally the KP08s float to centre it, within the
# clearance's own ±.002 station. The Ø.351 clears the Tr8's major at both
# at the KP08's nominal 15 axis height, which is UNVERIFIED until the pillow
# blocks are measured (#2184).
_AXIS_Y_BAND = printed_band_mm(NUT_PATTERN_PLACES, unit=UNIT)  # .005
LEADSCREW_OFFSET_Z = end_bracket.THICK_STOCK_BAND + NUT_CLEARANCE_BAND_Z  # .355 mm
LEADSCREW_OFFSET_Y = NUT_CLEARANCE_BAND_Y
LEADSCREW_OFFSET = math.hypot(LEADSCREW_OFFSET_Y, LEADSCREW_OFFSET_Z)
LEADSCREW_RADIAL_CLEARANCE = (SCREW_CLEARANCE_DIA - lead.SCREW_MAJOR_DIA) / 2
assert LEADSCREW_RADIAL_CLEARANCE > LEADSCREW_OFFSET, (LEADSCREW_RADIAL_CLEARANCE, LEADSCREW_OFFSET)
# The leadscrew clearance clears the screw at its least size.
assert SCREW_CLEARANCE_DIA - printed_band_mm(3, unit=UNIT) > lead.SCREW_MAJOR_DIA

# --- Fit-up: each tap spotted through its nut hole ------------------------------
# A #29 drill (.136) spots each tap through the nut's Ø3.5 hole, so a tap
# stands at most FIT_UP_RESIDUAL off its hole's axis at the largest hole.
TRANSFER_SPOT_DIA = 0.136 * 25.4  # #29, 3.454
assert TRANSFER_SPOT_DIA < feed_nut.HOLE_DIA_MIN
FIT_UP_RESIDUAL = (feed_nut.HOLE_DIA_MAX - TRANSFER_SPOT_DIA) / 2  # 0.073
# --- The flat heads beside the nut body: radial stack-up, term by term ---------
# Radii from the nut axis, mm. A seated head's axis lies between its
# countersink's axis (CSK_ECCENTRICITY_MAX off the hole's, an ASSUMPTION) and
# its tap's (FIT_UP_RESIDUAL off it): the cone pushes the head toward the
# first, the thread holds the screw on the second. So the head stands at most
# the larger of the two inward of its hole, not their sum; tap squareness is
# not charged. The 82° seat leaves every head proud of the flange
# (feed_nut.HEAD_PROUD_MIN, 0.05: B18.6.3's least head in the band's Ø4.76
# mouth), so the head's full top
# Ø stands beside the body's cylinder and the seat depth takes nothing off the
# gap. The body's root corner is modelled sharp (the listing gives no fillet).
_HEAD_OFF_HOLE = max(FIT_UP_RESIDUAL, feed_nut.CSK_ECCENTRICITY_MAX)
if feed_nut.HEAD_PROUD_MIN <= 0.0:
    raise AssertionError("a flat head sinks below the flange face; its mouth governs the gap")
HEAD_TO_BODY_TERMS: dict[str, float] = {
    "hole PCD radius": feed_nut.HOLE_PCD / 2,  # +8.000
    "PCD band (±0.1 on Ø)": -feed_nut.HOLE_STATION_BAND,  # -0.050
    "head off its hole (the larger of tap residual and countersink eccentricity)": -_HEAD_OFF_HOLE,  # -0.073
    "head radius (F2 limit Ø.212, the catalogue's)": -feed_nut.SCREW_HEAD_DIA_MAX / 2,  # -2.692
    "82° seat depth (every head proud of the face)": 0.0,
    "body radius (receipt limit Ø10.3)": -feed_nut.BODY_DIA_MAX / 2,  # -5.150
}
HEAD_TO_BODY_MIN = sum(HEAD_TO_BODY_TERMS.values())  # +0.035
# A head centred in its countersink.
HEAD_TO_BODY_CENTRED = (
    HEAD_TO_BODY_MIN + _HEAD_OFF_HOLE - feed_nut.CSK_ECCENTRICITY_MAX
)  # +0.088
if HEAD_TO_BODY_MIN <= 0.0:
    raise AssertionError("a flat head at F2's limit reaches the nut body at the worst case")
# ASME B18.6.3 lets a #4 flat head reach Ø.225 at its sharp-edge maximum
# (trammel.RISER_SCREW_HEAD_DIA; McMaster states .212 with no tolerance).
# Such a head reaches the body even centred, so F2 rejects every nut screw
# head over feed_nut.SCREW_HEAD_DIA_MAX (owner ruling 2026-11-04, #2177
# option 3); the window refuses that check once a Ø.225 head clears.
HEAD_DIA_SHARP_MAX = trammel.RISER_SCREW_HEAD_DIA  # 5.715
_SHARP_EXCESS = (HEAD_DIA_SHARP_MAX - feed_nut.SCREW_HEAD_DIA_MAX) / 2  # 0.165
HEAD_TO_BODY_SHARP_MIN = HEAD_TO_BODY_MIN - _SHARP_EXCESS  # -0.130
HEAD_TO_BODY_SHARP_CENTRED = HEAD_TO_BODY_CENTRED - _SHARP_EXCESS  # -0.078
if HEAD_TO_BODY_SHARP_CENTRED >= 0.0:
    raise AssertionError("B18.6.3's largest flat head clears the body; drop F2's head check")

# --- Rule 17: lug walls at the printed worst case (.080 target) -----------------
# Every transferred tap sits where the nut puts it: the leadscrew at its
# offset from the clearance, the nut's hole at its station band, the spot's
# residual, and that tap's own clocking anywhere in NutClock's band, each
# tap independently (F1B sets all four holes in it; the supplier bounds no
# hole's angular station). The clearance wall is radial, so it takes the
# offset's largest component along a tap's direction; each face wall takes
# a tap's largest reach toward it. NutClock measures from +Z, the angle a
# below from Y: the band is symmetric about 45°, so the two are the same
# set, and |cos|, |sin| put the same set in every quadrant.
NUT_TAP_MAJOR = THREAD_MAJOR_MM[feed_nut.SCREW_THREAD]
# The ±.002 station is a bored hole's (drawing-guidelines' shop table: a
# drilled hole holds ±.005; restack farm r1 20261108T040030048Z asked for the
# route), so the Ø.351 is bored at its station and its size takes the title
# block's .XXX ±.005, not DRILLED HOLES' +.004.
NUT_CLEARANCE_PROCESS = "BORE"
_CLEARANCE_R = (SCREW_CLEARANCE_DIA + printed_band_mm(3, unit=UNIT)) / 2
_TAP_RADIUS = feed_nut.HOLE_PCD / 2 + feed_nut.HOLE_STATION_BAND + FIT_UP_RESIDUAL
_TAP_RADIUS_MIN = feed_nut.HOLE_PCD / 2 - feed_nut.HOLE_STATION_BAND - FIT_UP_RESIDUAL
_CLOCK_STEPS = 100  # 0.1° across the ±5° band; both limits included
# Rule 17's wander on the THRU taps (.770 deep, about 8.7 D of the #43): the
# fleet's 0.3° drift (fr_top_frame_spec.KEEPER_TAP_DRILL_WANDER_DEG),
# charged in any direction at the -X face, the deepest point from the
# spotted +X nut face (machinist review, farm r1 20261107T221729532Z).
NUT_TAP_DRILL_WANDER_DEG = 0.3
NUT_TAP_WANDER = LUG_WIDTH * math.tan(math.radians(NUT_TAP_DRILL_WANDER_DEG))  # 0.102


def lug_walls_mm(clock_tol_deg: float = NUT_CLOCK_TOL_DEG) -> dict[str, float]:
    """The lug's tap walls, mm, with every tap anywhere within
    ``NUT_CLOCK_DEG`` ± ``clock_tol_deg`` (a wider band is the test's
    negative control), each with the THRU taps' wander charged."""
    clockings = tuple(
        math.radians(NUT_CLOCK_DEG + clock_tol_deg * (2 * k / _CLOCK_STEPS - 1))
        for k in range(_CLOCK_STEPS + 1)
    )
    # A tap at angle a from the lug's Y axis: its Y and Z reach from the axis.
    reach_y = max(_TAP_RADIUS * abs(math.cos(a)) for a in clockings)
    reach_z = max(_TAP_RADIUS * abs(math.sin(a)) for a in clockings)
    offset_toward_tap = max(
        LEADSCREW_OFFSET_Y * abs(math.cos(a)) + LEADSCREW_OFFSET_Z * abs(math.sin(a))
        for a in clockings
    )
    tap = NUT_TAP_MAJOR / 2 + NUT_TAP_WANDER
    return {
        "taps to the leadscrew clearance": _TAP_RADIUS_MIN - offset_toward_tap
        - tap - _CLEARANCE_R,
        "taps to the lug end": (NUT_AXIS_Y - LUG_Y0) - _AXIS_Y_BAND - LEADSCREW_OFFSET_Y
        - reach_y - tap,
        "taps to the bottom face": NUT_AXIS_Z - METRIC_BAND - LEADSCREW_OFFSET_Z
        - reach_z - tap,
        "taps to the top face": BLOCK_HEIGHT - NUT_AXIS_Z - METRIC_BAND - LEADSCREW_OFFSET_Z
        - reach_z - tap,
    }


LUG_WALLS_MM = lug_walls_mm()
# Owner ruling 2026-11-04 (#2177, option B): the clearance-to-tap wall's
# shortfall under the .080 target, over the .060 floor, is accepted and
# stated as plain fact on the clearance callout, floored to three places (a
# MIN never rounds up), the riser RV-01 precedent; with the wander charged
# it holds by the ±.002 clearance station (owner ruling 2026-11-08 (Pedro),
# A2 option (i)). The window refuses a wall under the floor and a stale
# statement once the wall reaches the target.
NUT_WALL_MIN_MM = min(LUG_WALLS_MM.values())
if not WALL_FLOOR_MM <= NUT_WALL_MIN_MM < WALL_TARGET_MM:
    raise AssertionError("the TL-32 clearance-to-tap wall no longer matches its stated shortfall")
if min(v for k, v in LUG_WALLS_MM.items() if k != "taps to the leadscrew clearance") < WALL_TARGET_MM:
    raise AssertionError("a TL-32 tap-to-face wall is under the .080 target")
NUT_WALL_MIN = math.floor(NUT_WALL_MIN_MM / 25.4 * 1000.0 + 1e-9) / 1000.0 * 25.4
NUT_WALL_MIN_TEXT = f"WALL {carrier.inch_text(NUT_WALL_MIN, 3)} MIN TO TAPS"
# The nut screws' tips stop inside the THRU tap.
assert feed_nut.SCREW_TIP_REACH_MAX < LUG_WIDTH
# The round flange stands within the lug's span of the +X face at the
# leadscrew's offset, clear of the lug end and the bottom and top faces.
NUT_Y = (
    NUT_AXIS_Y - _AXIS_Y_BAND - LEADSCREW_OFFSET_Y - feed_nut.FLANGE_DIA_MAX / 2,
    NUT_AXIS_Y + _AXIS_Y_BAND + LEADSCREW_OFFSET_Y + feed_nut.FLANGE_DIA_MAX / 2,
)
NUT_Z = (
    NUT_AXIS_Z - METRIC_BAND - LEADSCREW_OFFSET_Z - feed_nut.FLANGE_DIA_MAX / 2,
    NUT_AXIS_Z + METRIC_BAND + LEADSCREW_OFFSET_Z + feed_nut.FLANGE_DIA_MAX / 2,
)
assert 0.0 <= NUT_Z[0] and NUT_Z[1] <= BLOCK_HEIGHT
assert LUG_Y0 <= NUT_Y[0] and NUT_Y[1] < LUG_Y1
assert BLOCK_WIDTH / 2 - LUG_Y0 < pivot.STOCK_WIDTH
assert abs(NUT_MACHINE_Z - lead.SCREW_AXIS_Z) < 1e-6

CALLOUTS_SUFFIX = dict(pivot.CALLOUTS_SUFFIX)
CALLOUTS_ABOVE = dict(pivot.CALLOUTS_ABOVE) | {
    # The front view's leader identifies the counterbored face; B-B gives
    # its floor. VIEW D / SHEET 2 identifies the separate leadscrew face.
    "CarriageCounterbores3Dia": "4X COUNTERBORE",
    "NutClearanceDia": "DRILL THRU",
}
# BlockWidth prints nowhere on TL-32 (PlanLugLength replaces it), so it
# carries no callout.
CALLOUTS_BELOW = {k: v for k, v in pivot.CALLOUTS_BELOW.items() if k != "BlockWidth"} | {
    "NutClearanceDia": f"LEADSCREW CLEARANCE\n{NUT_WALL_MIN_TEXT}",
    # r2 review: "BOTTOM" named no face a view defines; the face the
    # counterbored screws pull onto the HGH15CA-style carriage does.
    "NutCentreZ": "FROM CARRIAGE FACE\nON KP08 LEADSCREW AXIS",
    "NutCentreY": "ON KP08 LEADSCREW AXIS",
}
# Travel-end clearance includes the proud nut, not only the lug, at the
# longest fitted nut.
FEED_GAPS = {
    (name, station): max(box[0] - (station + NUT_REACH_X[1]), (station + NUT_REACH_X[0]) - box[1])
    for name, box in lead.KP08_BOXES.items()
    for station in trammel.CARRIAGE_TRAVEL
}
assert min(FEED_GAPS.values()) >= lead.FEED_GAP, FEED_GAPS
# The block bore and lug ordinate each carry .XX. The nut face is the block's
# +X end, so the far end carries the bore and BlockLength instead. The
# support envelope includes both mounting-hole floats and their printed
# stations, including the permitted lower-joint slip.
_PLAN_BORE_BAND = printed_band_mm(pivot.DRAWING_PRECISION_BY_NAME["PlanBoreX"], unit=pivot.UNIT)
LUG_POSITION_BAND = printed_band_mm(2, unit=UNIT) + _PLAN_BORE_BAND
NUT_FACE_POSITION_BAND = printed_band_mm(
    pivot.DRAWING_PRECISION_BY_NAME["BlockLength"], unit=pivot.UNIT
) + _PLAN_BORE_BAND
FEED_GAPS_WORST = {
    "near": trammel.CARRIAGE_TRAVEL[0] + NUT_REACH_X[0]
    - lead.KP08_BOXES["KP08 near"][1] - LUG_POSITION_BAND - lead.KP08_STATION_ENVELOPE,
    "far": lead.KP08_BOXES["KP08 far"][0]
    - (trammel.CARRIAGE_TRAVEL[1] + NUT_REACH_X[1])
    - NUT_FACE_POSITION_BAND - lead.KP08_STATION_ENVELOPE,
}
if min(FEED_GAPS_WORST.values()) < lead.FEED_GAP:
    raise AssertionError(f"centred feed reaches a displaced KP08: {FEED_GAPS_WORST}")
