r"""Pure-data contract for the keyed tooth-cutting arbor (MHA-DT-03-TL-03).

Shop tooling, not a machine part (cad/docs/subsystem-identities.md; issue
#2465). The sixteen keyed cone gears T030..T120 (MHA-DT-03) and the 64T
crank-drive gear (MHA-DT-07) are bored Ø.375 and broached for the 1/16 key
(``cone_land_key``) BEFORE their teeth are cut, so the teeth are cut clocked
to the keyway: each blank slides onto this arbor's seat over a short key of
the machine's own undersized 1/16 stock (MHA-DT-03-TL-06), bears on the
integral shoulder, and is clamped there by one backing collar
(MHA-DT-03-TL-04, three sizes) and a 1/4-28 hex nut (MHA-DT-03-TL-VN-50).

Two holds, one arbor:

* Cone gears: between the BS-0's centres, driven by a dog on the grip. A 60°
  centre hole in each end: Ø.11 in the grip end, Ø.070 in the 1/4-28 end,
  the largest whose wall to the thread root stays over rule 17's .060 floor.
* 64T: the head tilted 12° (machining-dfm.md, crossed crank pair) leaves no
  tailstock, so the BS-0's 3-jaw grips the Ø.62 grip with its jaw faces on the
  grip's step; the blank's near face (the shoulder) then stands STANDOFF from
  the jaws, at least the .75 the #2533 setup asks (issue #2465 comment), so the
  cutter on the vertical stub arbor runs out past the face.

Frame (the SolidWorks model, MHA-DT-04's recipe): the axis is model +Z; z = 0
is the grip's end face, the shoulder (the blank's datum) stands at
SHOULDER_Z, and the keyseat is centred on +X. The arbor is turned between
its centres in one setup, so every length is a station from the grip's end
face (rule 10's one datum, rule 11's faced end) and the overall length ties
the thread's end to it; a length between two blank-side stations (the
shoulder to the seat's end, say) then holds twice the .XX band.

Every number below is derived and asserted here; ``KEYED_GEARS`` names each
blank the arbor carries with its printed bore, face and root limits.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import _config
import cone_land_key
import dt_cone_gear_spec as cone
import dt_crank_drive_gear_spec as crank
from _inch_wall_limits import WALL_FLOOR_MM
from _package_units import drawing_unit
from _printed_tolerance import angular_band_deg, drilled_oversize_mm, printed_band_mm

PART_NAME = "dt-cone-gear-tl-keyed-arbor"
_ROW = _config.parts("dt-cone-gear-tl-keyed-arbor")
if PART_NAME != "dt-cone-gear-tl-keyed-arbor":
    raise AssertionError("PART_NAME and the registry row it reads disagree")
PART_NUMBER = str(_ROW["number"])
UNIT = drawing_unit("parts/dt-cone-gear-tl-keyed-arbor", _ROW)
INCH = cone.MM_PER_IN
if UNIT != "in":
    raise AssertionError("the keyed arbor prints in inch")
_CONE_NUMBER = str(_config.parts("dt-cone-gear")["number"])
_CRANK_NUMBER = str(_config.parts("dt-crank-drive-gear")["number"])
_COLLAR_NUMBER = str(_config.parts("dt-cone-gear-tl-arbor-collar")["number"])
# The collar shares this sheet's MHA-DT-03 parent: its short form (rule 4).
_COLLAR_SHORT = _COLLAR_NUMBER.removeprefix(f"{_CONE_NUMBER}-")
if _COLLAR_SHORT == _COLLAR_NUMBER:
    raise AssertionError("the collar no longer shares the arbor's parent number")
_XX = printed_band_mm(2, unit=UNIT)
_XXX = printed_band_mm(3, unit=UNIT)
_DRILL_PLUS = drilled_oversize_mm(unit=UNIT)


def inch_grid_mm(value_mm: float, places: int, rounding=round) -> float:
    """``value_mm`` on the printed inch grid (rule 3)."""
    return cone.inch_grid_mm(value_mm, places, rounding)


def inch_text(value_mm: float, places: int) -> str:
    return cone.inch_text(value_mm, places)


# --- The blanks it carries -------------------------------------------------------
@dataclass(frozen=True)
class Blank:
    """One keyed blank at its printed limits (mm)."""

    tag: str
    number: str
    bore: tuple[float, float]  # (min, max) diameter
    face: tuple[float, float]  # (min, max) width
    root_min_dia: float  # smallest printed root envelope


def _cone_blank(teeth: int) -> Blank:
    upper, lower = cone.bore_dia_band(teeth)
    bore = cone.bore_dia_mm(teeth)
    face = cone.FACE_WIDTH
    return Blank(
        f"T{teeth:03d}",
        cone.configuration_number(_CONE_NUMBER, teeth),
        (bore + lower, bore + upper),
        (face + cone.FACE_WIDTH_BAND[1], face + cone.FACE_WIDTH_BAND[0]),
        cone.floor_limits_mm(teeth)[0],
    )


def _crank_blank() -> Blank:
    upper, lower = crank.BORE_DIA_BAND
    face_upper, face_lower = crank.FACE_WIDTH_BAND
    return Blank(
        f"{crank.TEETH}T",
        _CRANK_NUMBER,
        (crank.BORE_DIA + lower, crank.BORE_DIA + upper),
        (crank.FACE_WIDTH + face_lower, crank.FACE_WIDTH + face_upper),
        crank.ROOT_DIA_MIN,
    )


KEYED_GEARS: tuple[Blank, ...] = (
    *(_cone_blank(teeth) for teeth in cone.KEYED_TEETH),
    _crank_blank(),
)
if len(KEYED_GEARS) != 17:
    raise AssertionError("the arbor serves the sixteen keyed cones and the 64T")
if any(cone.bore_dia_mm(t) != cone_land_key.LAND_DIA_MM for t in cone.KEYED_TEETH):
    raise AssertionError("a keyed cone gear is no longer bored for land 1")
BORE_MIN_MM = min(blank.bore[0] for blank in KEYED_GEARS)
BORE_MAX_MM = max(blank.bore[1] for blank in KEYED_GEARS)
FACE_MIN_MM = min(blank.face[0] for blank in KEYED_GEARS)
FACE_MAX_MM = max(blank.face[1] for blank in KEYED_GEARS)

# --- Seat: a matched sliding fit whose play keeps a share of the tooth TIR -------
# Both gear families print the same setup allowance about the finished bore
# (TOOTH CUTTING SETUP ... .002 TIR MAX; crank_mesh.yaml 0.0508 mm). A blank
# with diametral play c on the seat can sit c/2 off the arbor's axis, so its
# teeth, cut true to the arbor, run c TIR about its own bore. The play may
# take at most PLAY_SHARE of the allowance; the rest is left for the seat's own
# runout on its centres (turned between them in one setup) and for indicating
# the seat true in the 3-jaw on the tilted head.
TOOTH_RUNOUT_TIR_MM = min(
    float(_config.fit("cone_drum_oblique_mesh", "tooth_cutting_runout_tir_mm")),
    float(_config.fit("crank_mesh", "tooth_cutting_runout_tir_mm")),
)
PLAY_SHARE = 2.0 / 3.0
# That share leaves the seat a band under the turned-diameter row of the shop
# table, so the seat is not cut to a number: it prints at the title block's
# three places (the supply size, line to line with the smallest bore) and its
# flag note states the fit (rule 4): a sliding fit matched to the keyed
# bores, diametral clearance from line to line up to the share, floored onto
# the .0001 grid, in every bore.
SEAT_PLACES = 3
SEAT_DIA = BORE_MIN_MM
SEAT_CLEARANCE_MM = (
    0.0,
    inch_grid_mm(PLAY_SHARE * TOOTH_RUNOUT_TIR_MM, 4, math.floor),
)
# The smallest seat the fit admits: the largest bore less the clearance.
SEAT_DIA_MIN = BORE_MAX_MM - SEAT_CLEARANCE_MM[1]
if SEAT_DIA_MIN > SEAT_DIA + 1e-9:
    raise AssertionError("no one seat fits every keyed bore inside the share")
SEAT_PLAY_TIR_MM = SEAT_CLEARANCE_MM[1]
SEAT_RUNOUT_ALLOWANCE_MM = TOOTH_RUNOUT_TIR_MM - SEAT_PLAY_TIR_MM

# --- Sections, inch (rule 3 grid) ------------------------------------------------
# Two blank-side stations from the grip's end face: a length between them.
_PAIR = 2.0 * _XX
# Grip: 5/8 cold-finished bar left at stock (.623-.625 lies in .62 +/-.01),
# the 3-jaw's and the dog's land. Its step is the jaw stop.
GRIP_DIA = 0.62 * INCH
GRIP_LENGTH = 0.75 * INCH
# Standoff: Ø.50, under T030's root, from the grip's step to the shoulder;
# its end face is the integral shoulder the blank bears on.
STANDOFF_DIA = 0.50 * INCH
STANDOFF = 0.88 * INCH
CHUCK_STANDOFF_MIN = 0.75 * INCH  # issue #2465 comment: #2 cutter run-out
if STANDOFF - _PAIR < CHUCK_STANDOFF_MIN - 1e-9:
    raise AssertionError("the blank's near face stands closer than .75 to the jaws")
# The seat stops short of every blank's far face, so the collar always bears
# on the blank, never on the seat's end (rule 19: held by the loose bands).
SEAT_LENGTH = 0.24 * INCH
if SEAT_LENGTH + _PAIR >= FACE_MIN_MM:
    raise AssertionError("the seat's end can reach a blank's far face")
SEAT_ENGAGEMENT_MIN = SEAT_LENGTH - _PAIR
# Pilot: the collars' bore slides on it, under the keyseat floor so the keyseat
# runs out over it, over the thread's major so the thread is reduced. Its
# .XXX holds the collar's float on it, which sets the Ø.50 collar's reach
# under T030's root (a .XX pilot leaves no collar clear of it). That third
# place gives it a function, so its callout names the fit and the collar it
# locates (rule 4, a standard fit name: machinist review r1-r2 of farm
# 20261113T042822797Z refused the private word PILOTS).
PILOT_DIA = 0.275 * INCH
PILOT_END = 0.42 * INCH
PILOT_FIT = "LOCATIONAL CLEARANCE FIT"
# Thread relief, at least one pitch wide and under the thread's root (rule 16).
THREAD = "1/4-28"
THREAD_SERIES = "UNF"
THREAD_PITCH = INCH / 28.0
THREAD_MAJOR = 0.25 * INCH
# ASME B1.1 1/4-28 UNF-2A: major .2490/.2425; the root (UNR minimum root
# radius) stands 1.22687 p under the major, so its least diameter is
THREAD_MAJOR_MIN = 0.2425 * INCH
THREAD_ROOT_MIN = THREAD_MAJOR_MIN - 1.22687 * THREAD_PITCH
RELIEF_DIA = 0.18 * INCH
RELIEF_END = 0.48 * INCH
ARBOR_END = 0.95 * INCH
if RELIEF_DIA + _XX >= THREAD_ROOT_MIN:
    raise AssertionError("the relief does not clear the thread root")
RELIEF_WIDTH_MIN = (RELIEF_END - _XX) - (PILOT_END + _XX)
if RELIEF_WIDTH_MIN < THREAD_PITCH:
    raise AssertionError("the thread relief is under one pitch (rule 16)")
if not PILOT_DIA - _XXX > THREAD_MAJOR:
    raise AssertionError("the pilot no longer stands over the thread")
OVERALL_LENGTH = GRIP_LENGTH + STANDOFF + ARBOR_END
STOCK_DIA = 0.625 * INCH
if not GRIP_DIA - _XX <= STOCK_DIA - 0.002 * INCH and STOCK_DIA <= GRIP_DIA + _XX:
    raise AssertionError("5/8 stock no longer passes as the grip")

# Shoulder root: the blank bears flat on the shoulder, so its root may not
# stand proud of the bore's edge break: R.004 MAX, the land-step root of
# MHA-DT-04 (dt_cone_gear_shaft_spec), printed as a single limit.
SHOULDER_R = 0.004 * INCH
SHOULDER_R_BAND = (0.0, -SHOULDER_R)
SHOULDER_R_TOL_TYPE = 6  # swTolType_e.swTolMAX: prints "R.004 MAX"

# --- Centre holes ------------------------------------------------------------------
CENTRE_INCLUDED_ANGLE_DEG = 60.0
CENTRE_HALF_ANGLE_DEG = CENTRE_INCLUDED_ANGLE_DEG / 2.0
# The grip end: the head's driving centre, within a #1 centre drill's
# Ø.125 body at the band's top.
HEAD_CENTRE_DIA = 0.11 * INCH
if HEAD_CENTRE_DIA + _XX > 0.125 * INCH + 1e-9:
    raise AssertionError("the head centre is over a #1 centre drill's body")
# The thread end: the tailstock centre. Its mouth at .XXX holds the wall to
# the thread root over rule 17's floor (rule 3: stated on the callout).
TAIL_CENTRE_DIA = 0.070 * INCH
TAIL_CENTRE_WALL_MIN = (THREAD_ROOT_MIN - (TAIL_CENTRE_DIA + _XXX)) / 2.0
if TAIL_CENTRE_WALL_MIN < WALL_FLOOR_MM:
    raise AssertionError(
        f"tail centre wall {TAIL_CENTRE_WALL_MIN / INCH:.4f} in under .060"
    )
TAIL_CENTRE_WALL_TEXT = math.floor(TAIL_CENTRE_WALL_MIN / INCH * 1000.0 + 1e-9) / 1000.0
CENTRE_PILOT_MAX = 0.047 * INCH  # #1 centre drill pilot (3/64)
if TAIL_CENTRE_DIA - _XXX <= CENTRE_PILOT_MAX:
    raise AssertionError("the tail centre's cone is no wider than the drill's pilot")


def centre_depth_mm(mouth_dia_mm: float) -> float:
    """Apex depth of a 60° centre hole with mouth ``mouth_dia_mm``."""
    return mouth_dia_mm / 2.0 / math.tan(math.radians(CENTRE_HALF_ANGLE_DEG))


# --- Keyseat and key (cone_land_key's numbers, imported) ---------------------------
KEYSEAT_WIDTH = cone_land_key.KEYSEAT_WIDTH_MM
KEYSEAT_WIDTH_BAND = cone_land_key.KEYSEAT_WIDTH_BAND
KEYSEAT_S = cone_land_key.KEYSEAT_S_MM
KEYSEAT_S_BAND = cone_land_key.KEYSEAT_S_BAND
KEYSEAT_PLACES = cone_land_key.KEYSEAT_PLACES
# The end mill closes the keyseat at the shoulder end, its radius centred this
# far from the shoulder (the shaft's collar-end set, the same reason: clear of
# the face at the band's low limit).
KEY_END_SET = cone_land_key.KEY_END_SET_MM
KEY_END_SET_PLACES = cone_land_key.KEY_END_SET_PLACES
if (
    KEY_END_SET - _XX - cone_land_key.limits(KEYSEAT_WIDTH, KEYSEAT_WIDTH_BAND)[1] / 2.0
    <= SHOULDER_R
):
    raise AssertionError("the keyseat's end radius reaches the shoulder root")
_SEAT_RADIUS_MIN = SEAT_DIA_MIN / 2.0
_SEAT_RADIUS_MAX = SEAT_DIA / 2.0
# Floor from the axis: S (from the seat's far side) less the far side's radius.
KEYSEAT_FLOOR_OFFSET = KEYSEAT_S - SEAT_DIA / 2.0
KEYSEAT_FLOOR_MIN = (
    cone_land_key.limits(KEYSEAT_S, KEYSEAT_S_BAND)[0] - _SEAT_RADIUS_MAX
)
KEYSEAT_FLOOR_MAX = (
    cone_land_key.limits(KEYSEAT_S, KEYSEAT_S_BAND)[1] - _SEAT_RADIUS_MIN
)
# The keyseat runs out over the pilot: the pilot stands under the floor.
PILOT_UNDER_FLOOR_MIN = KEYSEAT_FLOOR_MIN - (PILOT_DIA + _XXX) / 2.0
if PILOT_UNDER_FLOOR_MIN <= 0.0:
    raise AssertionError("the keyseat's run-out cuts the pilot")
# The key stays half buried at the keyseat's edge (the shaft's check, on this
# seat's smallest radius).
KEYSEAT_EDGE_DEPTH_MIN = (
    math.sqrt(
        _SEAT_RADIUS_MIN**2
        - (cone_land_key.limits(KEYSEAT_WIDTH, KEYSEAT_WIDTH_BAND)[1] / 2.0) ** 2
    )
    - KEYSEAT_FLOOR_MAX
)
if (
    KEYSEAT_EDGE_DEPTH_MIN
    < cone_land_key.limits(cone_land_key.KEY_SIZE_MM, cone_land_key.KEY_STOCK_BAND)[1]
    / 2.0
):
    raise AssertionError("the arbor key stands more than half out of its keyseat")
# A broached blank slides over the key: T and S share the far side, whatever
# the two diameters (cone_land_key's own worst case, asserted there).
KEY_TOP_CLEARANCE_MIN = cone_land_key.KEY_TOP_RADIAL_CLEARANCE_MIN_MM
# The key: .15 of the machine's key stock (MHA-DT-03-TL-06), its square
# end on the end radius's centre line, lying wholly on the seat (supported by
# the keyseat floor) and wholly under every blank (the collar's plain bore
# then never meets it).
KEY_LENGTH = 0.15 * INCH
KEY_LENGTH_PLACES = 2
KEY_FAR_END_MAX = KEY_END_SET + _XX + KEY_LENGTH + _XX
if KEY_FAR_END_MAX > SEAT_LENGTH - _PAIR + 1e-9:
    raise AssertionError("the key overhangs the seat's end")
if KEY_FAR_END_MAX >= FACE_MIN_MM:
    raise AssertionError("the key reaches past a blank into the collar")
KEY_ENGAGEMENT_MIN = KEY_LENGTH - _XX

# --- The clock the key carries -------------------------------------------------------
# The key is bonded in its keyseat (MHA-DT-03-TL-05 step 1), so the keyseat's
# own side play never reaches the blank; the blank turns on the key only by
# half its keyway's side clearance, at the bore's radius (the least radius a
# keyway flank meets the key at). That must stay inside the gear sheets'
# keyway-to-tooth clock, the title block's angle (error_budget cone_flat_clock).
KEY_CLOCK_PLAY_DEG = math.degrees(
    cone_land_key.KEYWAY_SIDE_CLEARANCE_MM[1] / 2.0 / (BORE_MIN_MM / 2.0)
)
KEY_CLOCK_TOLERANCE_DEG = angular_band_deg(unit=cone.UNIT)
if KEY_CLOCK_PLAY_DEG >= KEY_CLOCK_TOLERANCE_DEG:
    raise AssertionError("the blank's play on the key exceeds the keyway clock")
KEY_SETTING_ALLOWANCE_DEG = KEY_CLOCK_TOLERANCE_DEG - KEY_CLOCK_PLAY_DEG

# --- Backing: every blank backed under its root ---------------------------------------
# The cutter runs out past both faces at the root circle, so everything beside
# a blank stands under its root by AIR_MIN at the printed limits: the integral
# shoulder on one face, one loose collar (MHA-DT-03-TL-04) on the other. The
# collar is needed for clamping (the nut's 7/16 face does not cover a Ø.376
# bore's annulus), so one collar per setup, never a pair. Its size is the
# largest that clears the root and backs at least BACKING_SHARE_MIN of it.
AIR_MIN = 0.010 * INCH
BACKING_SHARE_MIN = 0.5
COLLAR_DIAS: tuple[float, ...] = (0.50 * INCH, 1.00 * INCH, 1.75 * INCH)
# .33 long: with every blank-side station held from the grip's end face, the
# nearest collar face still leaves the nut full thread (the stack below).
COLLAR_LENGTH = 0.33 * INCH
# The collar's plain bore on the pilot: a plain drilled size (letter L).
COLLAR_BORE = 0.290 * INCH
COLLAR_FLOAT = ((COLLAR_BORE + _DRILL_PLUS) - (PILOT_DIA - _XXX)) / 2.0
if COLLAR_BORE - (PILOT_DIA + _XXX) <= 0.0:
    raise AssertionError("a collar does not slide over the largest pilot")
if COLLAR_BORE <= THREAD_MAJOR:
    raise AssertionError("a collar does not pass over the thread")


def collar_reach_mm(index: int) -> float:
    """Largest radius a collar of COLLAR_DIAS[index] reaches: its .XX band and
    its float on the pilot."""
    return COLLAR_DIAS[index] / 2.0 + _XX + COLLAR_FLOAT


SHOULDER_REACH = STANDOFF_DIA / 2.0 + _XX


def _collar_for(blank: Blank) -> int:
    fits = [
        i
        for i in range(len(COLLAR_DIAS))
        if collar_reach_mm(i) <= blank.root_min_dia / 2.0 - AIR_MIN
    ]
    if not fits:
        raise AssertionError(f"{blank.tag}: no collar clears its root")
    return max(fits)


COLLAR_BY_GEAR: dict[str, int] = {
    blank.tag: _collar_for(blank) for blank in KEYED_GEARS
}
BACKING_SHARE: dict[str, float] = {
    blank.tag: COLLAR_DIAS[COLLAR_BY_GEAR[blank.tag]] / blank.root_min_dia
    for blank in KEYED_GEARS
}
ROOT_AIR: dict[str, float] = {
    blank.tag: blank.root_min_dia / 2.0
    - max(collar_reach_mm(COLLAR_BY_GEAR[blank.tag]), SHOULDER_REACH)
    for blank in KEYED_GEARS
}
for _blank in KEYED_GEARS:
    if BACKING_SHARE[_blank.tag] < BACKING_SHARE_MIN:
        raise AssertionError(f"{_blank.tag} is backed under half its root")
    if ROOT_AIR[_blank.tag] < AIR_MIN - 1e-9:
        raise AssertionError(f"{_blank.tag}: the cutter meets the shoulder or collar")
if sorted(set(COLLAR_BY_GEAR.values())) != list(range(len(COLLAR_DIAS))):
    raise AssertionError("a collar size backs no gear")
# The integral shoulder: no larger than the smallest collar it pairs with.
if STANDOFF_DIA != COLLAR_DIAS[0]:
    raise AssertionError("the shoulder and the smallest collar differ")

# --- The nut ----------------------------------------------------------------------
# 1/4-28 hex nut, ASME B18.2.2, 7/16 across flats (MHA-DT-03-TL-VN-50): its
# corners stand under the smallest root by AIR_MIN even beside the blank.
NUT_ACROSS_FLATS = 7.0 / 16.0 * INCH
NUT_ACROSS_CORNERS = NUT_ACROSS_FLATS / math.cos(math.radians(30.0))
NUT_THICKNESS_MAX = 0.226 * INCH  # B18.2.2 1/4 hex nut H max
_ROOT_MIN = min(blank.root_min_dia for blank in KEYED_GEARS)
NUT_ROOT_AIR = _ROOT_MIN / 2.0 - NUT_ACROSS_CORNERS / 2.0
if NUT_ROOT_AIR < AIR_MIN:
    raise AssertionError("the nut's corners stand over T030's root")
if NUT_ACROSS_FLATS <= COLLAR_BORE + _DRILL_PLUS:
    raise AssertionError("the nut's face does not bear on the collar")

# --- The stack along the arbor (stations from the shoulder, mm) -------------------
# Each blank-side station stands off the shoulder by _PAIR (both from the
# grip's end face). The collar's near face is the blank's far face; its far
# face carries the nut.
COLLAR_FACE_MIN = FACE_MIN_MM + COLLAR_LENGTH - _XX
COLLAR_FACE_MAX = FACE_MAX_MM + COLLAR_LENGTH + _XX
# The nut seats on full thread: the relief ends short of the nearest collar face
# by two pitches (the die's incomplete start).
NUT_THREAD_MARGIN = COLLAR_FACE_MIN - (RELIEF_END + _PAIR) - 2.0 * THREAD_PITCH
if NUT_THREAD_MARGIN <= 0.0:
    raise AssertionError("the nut would seat on the thread's run-out")
# The collar's bore engages the pilot under the thickest blank.
PILOT_ENGAGEMENT_MIN = (PILOT_END - _PAIR) - FACE_MAX_MM
if PILOT_ENGAGEMENT_MIN < 0.10 * INCH:
    raise AssertionError("the collar barely engages the pilot")
# The nut bears on the collar, never on the pilot's end.
if PILOT_END + _PAIR >= COLLAR_FACE_MIN:
    raise AssertionError("the pilot's end can reach the collar's far face")
# Thread left past the farthest nut: at least the die's lead, 1.5 pitches.
# The thread's end: the relief's station plus the thread's own length.
THREAD_PAST_NUT_MIN = (ARBOR_END - 2.0 * _XX) - (COLLAR_FACE_MAX + NUT_THICKNESS_MAX)
if THREAD_PAST_NUT_MIN < 1.5 * THREAD_PITCH:
    raise AssertionError("the nut runs off the thread's end")

# --- Pose in the kit (MHA-DT-03-TL-05) ----------------------------------------------
# The kit shows the 64T setup: the largest collar on the pilot where the 64T's
# far face would stand, the nut on it.
KIT_BLANK_FACE = crank.FACE_WIDTH

# --- Model ------------------------------------------------------------------------
# The model follows MHA-DT-04's recipe (build_dt_cone_gear_shaft): each turned
# diameter a circle on the plane at its own end station, extruded back to the
# grip's end face, so every diameter's dimension stands on its own step in the
# side view and every length is a feature depth from that one face. Model +Z
# is the axis; z = 0 (the Front Plane) is the grip's end face, the datum;
# SHOULDER_Z is the shoulder face (the ShoulderPlane) the blank bears on. The
# keyseat is centred on +X (cone_land_key's clock).
SHOULDER_Z = GRIP_LENGTH + STANDOFF
SEAT_END_Z = SHOULDER_Z + SEAT_LENGTH
PILOT_END_Z = SHOULDER_Z + PILOT_END
RELIEF_END_Z = SHOULDER_Z + RELIEF_END
THREAD_LENGTH = ARBOR_END - RELIEF_END
ARBOR_END_Z = SHOULDER_Z + ARBOR_END
if abs(ARBOR_END_Z - OVERALL_LENGTH) > 1e-9:
    raise AssertionError("the arbor's stations do not close on its length")
KEY_END_Z = SHOULDER_Z + KEY_END_SET

# The turned sections in build order: (name, diameter, start z, end z). Each
# section up to the relief runs back from its end to the grip's end face
# inside the larger ones before it; the thread, larger than the relief, runs
# back only to the relief's end.
SECTIONS: tuple[tuple[str, float, float, float], ...] = (
    ("Grip", GRIP_DIA, 0.0, GRIP_LENGTH),
    ("Standoff", STANDOFF_DIA, 0.0, SHOULDER_Z),
    ("Seat", SEAT_DIA, 0.0, SEAT_END_Z),
    ("Pilot", PILOT_DIA, 0.0, PILOT_END_Z),
    ("Relief", RELIEF_DIA, 0.0, RELIEF_END_Z),
    ("Thread", THREAD_MAJOR, RELIEF_END_Z, ARBOR_END_Z),
)


def _union_volume() -> float:
    """The turned sections' union: at each station the largest diameter."""
    stations = sorted({z for _n, _d, a, b in SECTIONS for z in (a, b)})
    volume = 0.0
    for z0, z1 in zip(stations, stations[1:], strict=False):
        mid = (z0 + z1) / 2.0
        dia = max(d for _n, d, a, b in SECTIONS if a <= mid <= b)
        volume += math.pi * (dia / 2.0) ** 2 * (z1 - z0)
    return volume


TURNED_VOLUME = _union_volume()
CENTRE_VOLUME = sum(
    math.pi * (dia / 2.0) ** 2 * centre_depth_mm(dia) / 3.0
    for dia in (HEAD_CENTRE_DIA, TAIL_CENTRE_DIA)
)


def keyseat_area_mm2() -> float:
    """The seat's cross-section lost to the keyseat: the strip |y| <= W/2
    beyond the floor inside the seat circle (build_dt_cone_gear_shaft's form)."""
    radius = SEAT_DIA / 2.0
    half = KEYSEAT_WIDTH / 2.0
    floor = KEYSEAT_FLOOR_OFFSET
    if floor > math.sqrt(radius**2 - half**2):
        raise AssertionError("keyseat floor lies outside the seat at its edges")
    strip = half * math.sqrt(radius**2 - half**2) + radius**2 * math.asin(half / radius)
    return strip - 2.0 * half * floor


def keyseat_end_volume_mm3(steps: int = 4000) -> float:
    """The end mill's half disc beyond the straight cut, floor to seat
    surface (midpoint rule)."""
    radius = SEAT_DIA / 2.0
    half = KEYSEAT_WIDTH / 2.0
    floor = KEYSEAT_FLOOR_OFFSET
    dy = 2.0 * half / steps
    total = 0.0
    for k in range(steps):
        y = -half + (k + 0.5) * dy
        total += math.sqrt(half**2 - y**2) * (math.sqrt(radius**2 - y**2) - floor) * dy
    return total


# The straight keyseat: from the seat's end (SeatEndPlane) back to the end
# radius's centre; the end mill's semicircle closes it toward the shoulder.
KEYSEAT_CUT_LENGTH = SEAT_LENGTH - KEY_END_SET
KEYSEAT_VOLUME = keyseat_area_mm2() * KEYSEAT_CUT_LENGTH
KEYSEAT_END_VOLUME = keyseat_end_volume_mm3()
FINISHED_VOLUME = TURNED_VOLUME - CENTRE_VOLUME - KEYSEAT_VOLUME - KEYSEAT_END_VOLUME

# Model globals (mm); the build sets each and drives its dimensions from it.
# Every station is from the grip's end face (the Front Plane).
GLOBALS: dict[str, float] = {
    "GripDia": GRIP_DIA,
    "GripLength": GRIP_LENGTH,
    "StandoffDia": STANDOFF_DIA,
    "ShoulderZ": SHOULDER_Z,
    "SeatDia": SEAT_DIA,
    "SeatEndZ": SEAT_END_Z,
    "PilotDia": PILOT_DIA,
    "PilotEndZ": PILOT_END_Z,
    "ReliefDia": RELIEF_DIA,
    "ReliefEndZ": RELIEF_END_Z,
    "ThreadDia": THREAD_MAJOR,
    "OverallLength": OVERALL_LENGTH,
    "HeadCentreDia": HEAD_CENTRE_DIA,
    "TailCentreDia": TAIL_CENTRE_DIA,
    "KeyseatW": KEYSEAT_WIDTH,
    "KeyseatS": KEYSEAT_S,
    "KeyseatEndSet": KEY_END_SET,
}
SHOULDER_EXPRESSION = '"ShoulderZ"'
OVERALL_EXPRESSION = '"OverallLength"'
THREAD_LENGTH_EXPRESSION = '"OverallLength" - "ReliefEndZ"'
KEYSEAT_LENGTH_EXPRESSION = '"SeatEndZ" - "ShoulderZ" - "KeyseatEndSet"'

# --- Drawing -------------------------------------------------------------------------
SHOULDER_PLANE = "ShoulderPlane"
KEYSEAT_SKETCH = "KeyseatProfile"
KEYSEAT_FEATURE = "Keyseat"
KEYSEAT_END_PLANE = "KeyseatEndPlane"
KEYSEAT_END_SKETCH = "KeyseatEndProfile"
KEYSEAT_END_FEATURE = "KeyseatEnd"
CENTRE_SKETCH = "CentreProfile"
CENTRE_FEATURE = "Centres"
SHOULDER_FILLET = "ShoulderFillet"


def profile_sketch(section: str) -> str:
    return f"{section}Profile"


def end_plane(section: str) -> str:
    return f"{section}EndPlane"


# Each section: its diameter on its profile sketch, its length the extrude's
# depth back to the grip's end face (the thread's from its end back to the
# relief, left off the sheet: the overall ties the thread's end).
SECTION_DIMENSIONS: dict[str, tuple[str, str]] = {
    "Grip": ("GripDia", "GripLength"),
    "Standoff": ("StandoffDia", "Shoulder"),
    "Seat": ("SeatDia", "SeatEnd"),
    "Pilot": ("PilotDia", "PilotEnd"),
    "Relief": ("ReliefDia", "ReliefEnd"),
    "Thread": ("ThreadDia", "ThreadLength"),
}
# Each section's end station (its plane's offset from the Front Plane; the
# standoff's is the ShoulderPlane) and its extrude depth, as equations.
END_STATION_DRIVES: dict[str, str] = {
    "Seat": '"SeatEndZ"',
    "Pilot": '"PilotEndZ"',
    "Relief": '"ReliefEndZ"',
    "Thread": OVERALL_EXPRESSION,
}
LENGTH_DRIVES: dict[str, str] = {
    "GripLength": '"GripLength"',
    "Shoulder": SHOULDER_EXPRESSION,
    "SeatEnd": '"SeatEndZ"',
    "PilotEnd": '"PilotEndZ"',
    "ReliefEnd": '"ReliefEndZ"',
    "ThreadLength": THREAD_LENGTH_EXPRESSION,
}
SHEET_LENGTHS = ("GripLength", "Shoulder", "SeatEnd", "PilotEnd", "ReliefEnd")
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    **{profile_sketch(s): {dia} for s, (dia, _length) in SECTION_DIMENSIONS.items()},
    **{
        s: {length}
        for s, (_dia, length) in SECTION_DIMENSIONS.items()
        if length in SHEET_LENGTHS
    },
    CENTRE_SKETCH: {"HeadCentreDia", "TailCentreDia", "CentreOverall"},
    KEYSEAT_SKETCH: {"KeyseatWidth", "KeyseatS"},
    KEYSEAT_END_SKETCH: {"KeyseatEndSet"},
    SHOULDER_FILLET: {"ShoulderR"},
}
_PLACES_BY_NAME: dict[str, int] = {
    "GripDia": 2,
    "GripLength": 2,
    "StandoffDia": 2,
    "Shoulder": 2,
    "SeatDia": SEAT_PLACES,
    "SeatEnd": 2,
    "PilotDia": 3,
    "PilotEnd": 2,
    "ThreadDia": 3,
    "ReliefDia": 2,
    "ReliefEnd": 2,
    "CentreOverall": 2,
    "HeadCentreDia": 2,
    "TailCentreDia": 3,
    "KeyseatWidth": KEYSEAT_PLACES,
    "KeyseatS": KEYSEAT_PLACES,
    "KeyseatEndSet": KEY_END_SET_PLACES,
    "ShoulderR": 3,
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    feature: {name: _PLACES_BY_NAME[name] for name in sorted(names)}
    for feature, names in DRAWING_DIMENSIONS.items()
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dims in DRAWING_PRECISION.values() for name, places in dims.items()
}
if set(_PLACES_BY_NAME) != set(DRAWING_PRECISION_BY_NAME):
    raise AssertionError("every marked arbor dimension needs authored places")
DRAWING_VALUES_BY_NAME: dict[str, float] = {
    "GripDia": GRIP_DIA,
    "GripLength": GRIP_LENGTH,
    "StandoffDia": STANDOFF_DIA,
    "Shoulder": SHOULDER_Z,
    "SeatDia": SEAT_DIA,
    "SeatEnd": SEAT_END_Z,
    "PilotDia": PILOT_DIA,
    "PilotEnd": PILOT_END_Z,
    "ThreadDia": THREAD_MAJOR,
    "ReliefDia": RELIEF_DIA,
    "ReliefEnd": RELIEF_END_Z,
    "CentreOverall": OVERALL_LENGTH,
    "HeadCentreDia": HEAD_CENTRE_DIA,
    "TailCentreDia": TAIL_CENTRE_DIA,
    "KeyseatWidth": KEYSEAT_WIDTH,
    "KeyseatS": KEYSEAT_S,
    "KeyseatEndSet": KEY_END_SET,
    "ShoulderR": SHOULDER_R,
}
if set(DRAWING_VALUES_BY_NAME) != set(DRAWING_PRECISION_BY_NAME):
    raise AssertionError("every marked arbor dimension needs its value")
# Fabricated nominals sit on their printed grid (rule 3).
for _name, _value in DRAWING_VALUES_BY_NAME.items():
    _places = DRAWING_PRECISION_BY_NAME[_name]
    if abs(inch_grid_mm(_value, _places) - _value) > 1e-9:
        raise AssertionError(f"{_name} {_value} mm is off its .{'X' * _places} grid")
# The bands tighter than the title block, set on the model's own dimension:
# (feature, dimension) -> (upper, lower) band, mm. The keyseat's are
# cone_land_key's, for its key; the seat has none (its fit is note 1's).
MODEL_BANDS_MM: dict[tuple[str, str], tuple[float, float]] = {
    (KEYSEAT_SKETCH, "KeyseatWidth"): KEYSEAT_WIDTH_BAND,
    (KEYSEAT_SKETCH, "KeyseatS"): KEYSEAT_S_BAND,
}

# --- Sheet words -----------------------------------------------------------------------
# One numbered note states the seat's matched fit with its mates and
# acceptance, and the keyseat's key (rule 4: one flag note linked to every
# dimension of the one feature; every mate by its drawing number). The key's
# clock and its setting are the kit's fitting steps (MHA-DT-03-TL-05), not
# this sheet's.
KEY_NUMBER = str(_config.parts("dt-cone-gear-tl-arbor-key")["number"])
SEAT_NOTE_NUMBER = 1
SEAT_NOTE_FLAG = f"SEE NOTE {SEAT_NOTE_NUMBER}"
SEAT_CLEARANCE_TEXT = "-".join(
    inch_text(value, 4) if value > 1e-9 else ".0000" for value in SEAT_CLEARANCE_MM
)
_CONE_SPAN = (KEYED_GEARS[0].number, KEYED_GEARS[-2].number)
if not all(n.startswith(f"{_CONE_NUMBER}-T") for n in _CONE_SPAN):
    raise AssertionError("the note's cone span no longer runs over MHA-DT-03's members")
SHEET_NOTES = "\n".join(
    (
        f"{SEAT_NOTE_NUMBER}. SEAT: SLIDING FIT, MATCHED TO THE KEYED BORES OF "
        f"{_CONE_SPAN[0]}",
        f"   TO {_CONE_SPAN[1]} AND {_CRANK_NUMBER}, CLEARANCE {SEAT_CLEARANCE_TEXT} "
        "IN EACH BORE;",
        f"   KEYSEAT FOR KEY {KEY_NUMBER}.",
    )
)
if len(SHEET_NOTES.splitlines()) > 4:
    raise AssertionError("at most four note lines")
CENTRE_PREFIX = "<HOLE-SINK><MOD-DIAM>"
CENTRE_SUFFIX = f" X {CENTRE_INCLUDED_ANGLE_DEG:.0f}°"
# The title block carries the thread class (rule 2).
THREAD_CALLOUT = f"{THREAD} {THREAD_SERIES}"
# The thread's schematic major cylinder reads as its designation
# (_drawing_dimensions.set_dimension_text).
DIMENSION_TEXT: dict[str, str] = {"ThreadDia": THREAD_CALLOUT}
CALLOUTS_BELOW: dict[str, str] = {
    "SeatDia": SEAT_NOTE_FLAG,
    "KeyseatWidth": SEAT_NOTE_FLAG,
    "KeyseatS": SEAT_NOTE_FLAG,
    "GripDia": "STOCK OK",
    "PilotDia": f"{PILOT_FIT} IN {_COLLAR_SHORT}",
    "HeadCentreDia": "CENTRE HOLE",
    "TailCentreDia": (
        f"CENTRE HOLE\nHOLDS WALL {inch_text(TAIL_CENTRE_WALL_TEXT * INCH, 3)} MIN"
    ),
}
DIMENSION_PREFIXES: dict[str, str] = {
    "HeadCentreDia": CENTRE_PREFIX,
    "TailCentreDia": CENTRE_PREFIX,
}
DIMENSION_SUFFIXES: dict[str, str] = {
    "HeadCentreDia": CENTRE_SUFFIX,
    "TailCentreDia": CENTRE_SUFFIX,
}
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
