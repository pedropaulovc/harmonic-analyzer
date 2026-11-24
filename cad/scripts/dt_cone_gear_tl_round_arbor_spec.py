r"""Pure-data contract for the round tooth-cutting arbor (MHA-DT-03-TL-07).

Shop tooling, not a machine part (cad/docs/subsystem-identities.md; issue
#2356). T024 (MHA-DT-03) is reamed round Ø.250 for MHA-DT-04's land 2 before
its teeth are cut. The keyed arbor MHA-DT-03-TL-03 cannot carry it: that
arbor's 1/4-28 nut (corners Ø.505) and its smallest collar (Ø.50) stand over
T024's root (Ø.4413 MIN). Owner ruling 2026-11-20 (Pedro), #2356
(https://github.com/pedropaulovc/harmonic-analyzer/issues/2356#issuecomment-7051703304):
"Option 2. #8-32 end, Ø.38 collar, purchased #8-32 nut under the root, no
tail centre; the overhung compliance (1.85-2.59x the 64T setup, estimated
0.65-1.3x its deflection at the lighter 48 DP cut) is accepted."

So the blank slides onto this arbor's seat, bears on the integral shoulder
and is clamped there by one backing collar (MHA-DT-03-TL-08) and a purchased
#8-32 hex machine screw nut (McMaster 90480A009, bought with the kit and
given no Number: no kit assembly runs interference against it, so its fit is
asserted here), every one of them under T024's root. No key: a round bore
takes no clock, so the teeth are cut wherever the head's first index lands.

One hold, as the keyed arbor's: the BS-0's 3-jaw grips the Ø.62 grip with
its jaw faces on the grip's step, and the seat is indicated true there within
the sheet's setup allowance (the keyed arbor's rule). The blank's near face
(the shoulder) stands STANDOFF from the jaws, the keyed arbor's .75 floor
plus the .02 a length between two stations holds: the stiffer end of the
owner-accepted overhang. No centre holes: the owner ruled out the tail
centre, and the #8-32 root's own radius is under rule 17's .060 wall floor,
so no centre hole in the thread end could hold it (asserted below); the
grip end needs none either, since the arbor is turned in one chucking and
indicated on its seat.

Frame (the SolidWorks model, MHA-DT-04's recipe): the axis is model +Z; z = 0
is the grip's end face, the shoulder (the blank's datum) stands at
SHOULDER_Z. Every length is a station from the grip's end face (rule 10's
one datum, rule 11's faced end) and the overall length ties the thread's end
to it; a length between two blank-side stations (the shoulder to the seat's
end, say) then holds twice the .XX band.

The rules (air under the root, backing share, seat play share, chuck
standoff, shoulder root) are the keyed arbor's
(``dt_cone_gear_tl_keyed_arbor_spec``), restated here so this recipe does
not carry the keyed kit in its closure; the test asserts they agree.

Every number below is derived and asserted here; ``BLANK`` is the one blank
the arbor carries, with its printed bore, face and root limits.
"""

from __future__ import annotations

import math
import textwrap
from dataclasses import dataclass

import _config
import dt_cone_gear_spec as cone
from _inch_wall_limits import WALL_FLOOR_MM
from _mcmaster_90480a009 import ACROSS_FLATS as _NUT_ACROSS_FLATS
from _package_units import drawing_unit
from _printed_tolerance import drilled_oversize_mm, printed_band_mm

PART_NAME = "dt-cone-gear-tl-round-arbor"
_ROW = _config.parts("dt-cone-gear-tl-round-arbor")
if PART_NAME != "dt-cone-gear-tl-round-arbor":
    raise AssertionError("PART_NAME and the registry row it reads disagree")
PART_NUMBER = str(_ROW["number"])
UNIT = drawing_unit("parts/dt-cone-gear-tl-round-arbor", _ROW)
INCH = cone.MM_PER_IN
if UNIT != "in":
    raise AssertionError("the round arbor prints in inch")
_CONE_NUMBER = str(_config.parts("dt-cone-gear")["number"])
_COLLAR_NUMBER = str(_config.parts("dt-cone-gear-tl-round-arbor-collar")["number"])
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


# --- The blank it carries ----------------------------------------------------------
@dataclass(frozen=True)
class Blank:
    """The round-bored blank at its printed limits (mm)."""

    tag: str
    number: str
    bore: tuple[float, float]  # (min, max) diameter
    face: tuple[float, float]  # (min, max) width
    root_min_dia: float  # smallest printed root envelope


TEETH = 24
if TEETH in cone.KEYED_TEETH or TEETH not in cone.ROUND_BORE_TEETH:
    raise AssertionError("T024 is no longer round-bored")
# The other round bores (T012, T018: Ø.0625 on MHA-DT-37's spigot) are cut on
# the bar before boring (#2356 option A, their sheets accept the setup to the
# turned OD); land 2's one gear is this arbor's one blank.
if tuple(cone.LAND_2_TEETH) != (TEETH,):
    raise AssertionError("MHA-DT-04's land 2 no longer carries T024 alone")


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


BLANK = _cone_blank(TEETH)
BLANKS: tuple[Blank, ...] = (BLANK,)
BORE_MIN_MM, BORE_MAX_MM = BLANK.bore
FACE_MIN_MM, FACE_MAX_MM = BLANK.face
ROOT_MIN_MM = BLANK.root_min_dia

# --- Seat: a matched sliding fit whose play keeps a share of the tooth TIR -------
# The cone sheet prints the setup allowance about the finished bore (TOOTH
# CUTTING SETUP ... .002 TIR MAX). A blank with diametral play c on the seat
# can sit c/2 off the arbor's axis, so its teeth, cut true to the arbor, run
# c TIR about its own bore. The play may take at most PLAY_SHARE of the
# allowance (the keyed arbor's share); the rest is left for indicating the
# seat true in the 3-jaw.
TOOTH_RUNOUT_TIR_MM = float(
    _config.fit("cone_drum_oblique_mesh", "tooth_cutting_runout_tir_mm")
)
PLAY_SHARE = 2.0 / 3.0
# The seat prints at the title block's three places (line to line with the
# bore's low limit) and its flag note states the fit (rule 4): a sliding fit
# matched to T024's bore, diametral clearance from line to line up to the
# share, floored onto the plain .001 inch step, as the keyed arbor's (the
# .0013 the .0001 grid gave read as converted mm: machinist review r1, farm
# run 20261124T110807008Z). Necessity register N-01 (mesh): cone_set_stack
# books this play inside T024's .002 TIR, and a seat at the title block
# (.004 play) takes T024's contact ratio to 0.92 against
# NOMINAL_CONTACT_RATIO_MIN 1.0 (drawing-guidelines rule 4, form 2;
# cone_set_stack C-01 at .004 play gives T024 CR 0.92).
SEAT_PLACES = 3
SEAT_DIA = BORE_MIN_MM
SEAT_CLEARANCE_MM = (
    0.0,
    inch_grid_mm(PLAY_SHARE * TOOTH_RUNOUT_TIR_MM, 3, math.floor),
)
# The smallest seat the fit admits: the largest bore less the clearance.
SEAT_DIA_MIN = BORE_MAX_MM - SEAT_CLEARANCE_MM[1]
if SEAT_DIA_MIN > SEAT_DIA + 1e-9:
    raise AssertionError("no seat fits T024's bore inside the share")
SEAT_PLAY_TIR_MM = SEAT_CLEARANCE_MM[1]
SEAT_RUNOUT_ALLOWANCE_MM = TOOTH_RUNOUT_TIR_MM - SEAT_PLAY_TIR_MM

# --- Sections, inch (rule 3 grid) ------------------------------------------------
# Two blank-side stations from the grip's end face: a length between them.
_PAIR = 2.0 * _XX
# Grip: 5/8 cold-finished bar left at stock (.623-.625 lies in .62 +/-.01),
# the 3-jaw's land. Its step is the jaw stop.
GRIP_DIA = 0.62 * INCH
GRIP_LENGTH = 0.75 * INCH
STOCK_DIA = 0.625 * INCH
if not (GRIP_DIA - _XX <= STOCK_DIA - 0.002 * INCH and STOCK_DIA <= GRIP_DIA + _XX):
    raise AssertionError("5/8 stock no longer passes as the grip")
# Standoff: Ø.40, under T024's root, from the grip's step to the shoulder;
# its end face is the integral shoulder the blank bears on.
STANDOFF_DIA = 0.40 * INCH
STANDOFF = 0.77 * INCH
CHUCK_STANDOFF_MIN = 0.75 * INCH  # issue #2465 comment: #2 cutter run-out
if STANDOFF - _PAIR < CHUCK_STANDOFF_MIN - 1e-9:
    raise AssertionError("the blank's near face stands closer than .75 to the jaws")
# The seat stops short of the blank's far face, so the collar always bears
# on the blank, never on the seat's end (rule 19: held by the loose bands).
SEAT_LENGTH = 0.24 * INCH
if SEAT_LENGTH + _PAIR >= FACE_MIN_MM:
    raise AssertionError("the seat's end can reach the blank's far face")
SEAT_ENGAGEMENT_MIN = SEAT_LENGTH - _PAIR
# Pilot: the collar's drilled bore slides on it; under the blank's bore so
# the blank passes over it, over the thread's major so the thread is
# reduced. A plain clearance size at the title block's .XXX band, never a
# fit (the keyed arbor's pilot): its largest limit stands under the collar's
# smallest drilled bore. Small enough that the #1-drilled collar keeps rule
# 17's wall at Ø.38 (below).
PILOT_DIA = 0.220 * INCH
PILOT_END = 0.42 * INCH
if not PILOT_DIA + _XXX < BORE_MIN_MM:
    raise AssertionError("the blank does not pass over the largest pilot")
# Thread: #8-32 UNC, the title block carries the class (rule 2). ASME B1.1
# #8-32 UNC-2A: major .1631/.1571; the root (UNR minimum root radius) stands
# 1.22687 p under the major, so its least diameter is
THREAD = "#8-32"
THREAD_SERIES = "UNC"
THREAD_PITCH = INCH / 32.0
THREAD_MAJOR = 0.164 * INCH
THREAD_MAJOR_MAX = 0.1631 * INCH
THREAD_MAJOR_MIN = 0.1571 * INCH
THREAD_ROOT_MIN = THREAD_MAJOR_MIN - 1.22687 * THREAD_PITCH
if not PILOT_DIA - _XXX > THREAD_MAJOR_MAX:
    raise AssertionError("the pilot no longer stands over the thread")
# Thread relief, at least one pitch wide at its narrowest and under the
# thread's root (rule 16), printed at .XXX so its smallest limit stays near
# the root: it carries the nut's whole clamp tension and thread torque.
RELIEF_DIA = 0.112 * INCH
RELIEF_END = 0.48 * INCH
ARBOR_END = 0.81 * INCH
if RELIEF_DIA + _XXX >= THREAD_ROOT_MIN:
    raise AssertionError("the relief does not clear the thread root")
# Its smallest section keeps at least the keyed arbor's share of its own
# thread's tensile stress area: the keyed relief Ø.17 MIN over 1/4-28 UNF's
# As .0364 in² is pi/4 * .17² / .0364 = .6236 (dt_cone_gear_tl_keyed_arbor_spec
# RELIEF_DIA, restated so the keyed kit stays out of this closure). ASME B1.1
# tensile stress area of #8-32 UNC: As = .0140 in².
THREAD_STRESS_AREA_MM2 = 0.0140 * INCH**2
RELIEF_AREA_SHARE_MIN = 0.6236
RELIEF_AREA_MIN_MM2 = math.pi / 4.0 * (RELIEF_DIA - _XXX) ** 2
RELIEF_AREA_SHARE = RELIEF_AREA_MIN_MM2 / THREAD_STRESS_AREA_MM2
if RELIEF_AREA_SHARE < RELIEF_AREA_SHARE_MIN:
    raise AssertionError("the relief's least section is weaker than the keyed arbor's")
RELIEF_WIDTH_MIN = (RELIEF_END - _XX) - (PILOT_END + _XX)
if RELIEF_WIDTH_MIN < THREAD_PITCH:
    raise AssertionError("the thread relief is under one pitch (rule 16)")
OVERALL_LENGTH = GRIP_LENGTH + STANDOFF + ARBOR_END
# No centre hole: even a point at the axis leaves the thread root's own
# radius as the wall, under rule 17's floor.
if THREAD_ROOT_MIN / 2.0 >= WALL_FLOOR_MM:
    raise AssertionError("the #8-32 root now holds a centre hole's wall")

# Shoulder root: the blank bears flat on the shoulder, so its root may not
# stand proud of the bore's edge break: R.004 MAX, the keyed arbor's (and
# MHA-DT-04's land-step root), printed as a single limit with " MAX" as the
# value's suffix and no native tolerance. It serves the seat's mate, so it
# carries the seat's note flag (rule 4).
SHOULDER_R = 0.004 * INCH
SHOULDER_R_TOL_TYPE = 0  # swTolType_e.swTolNONE
SHOULDER_R_SUFFIX = " MAX"

# --- Backing: the blank backed under its root ---------------------------------------
# The cutter runs out past both faces at the root circle, so everything beside
# the blank stands under its root by AIR_MIN at the printed limits: the
# integral shoulder on one face, the loose collar (MHA-DT-03-TL-08) on the
# other, backing at least BACKING_SHARE_MIN of the root (the keyed arbor's
# rules).
AIR_MIN = 0.010 * INCH
BACKING_SHARE_MIN = 0.5
ROOT_REACH_MAX = ROOT_MIN_MM / 2.0 - AIR_MIN
SHOULDER_REACH = STANDOFF_DIA / 2.0 + _XX
if SHOULDER_REACH > ROOT_REACH_MAX + 1e-9:
    raise AssertionError("the cutter meets the shoulder")
# The collar: 3/8 cold-finished bar left at stock (.373-.375 lies in .38
# +/-.01), faced to length and drilled through with a #1 (.228) drill.
COLLAR_DIA = 0.38 * INCH
COLLAR_STOCK_DIA = 0.375 * INCH
if not (
    COLLAR_DIA - _XX <= COLLAR_STOCK_DIA - 0.002 * INCH
    and COLLAR_STOCK_DIA <= COLLAR_DIA + _XX
):
    raise AssertionError("3/8 stock no longer passes as the collar")
COLLAR_LENGTH = 0.30 * INCH
COLLAR_BORE = 0.228 * INCH
COLLAR_FLOAT = ((COLLAR_BORE + _DRILL_PLUS) - (PILOT_DIA - _XXX)) / 2.0
if COLLAR_BORE - (PILOT_DIA + _XXX) <= 0.0:
    raise AssertionError("the collar does not slide over the largest pilot")
if COLLAR_BORE <= THREAD_MAJOR:
    raise AssertionError("the collar does not pass over the thread")
# The collar's wall at the printed worst case (rule 17): the smallest OD over
# the largest drilled bore. The OD is left at stock, so drill and OD are not
# turned together.
COLLAR_WALL_MIN = ((COLLAR_DIA - _XX) - (COLLAR_BORE + _DRILL_PLUS)) / 2.0
if COLLAR_WALL_MIN < WALL_FLOOR_MM:
    raise AssertionError(
        f"collar wall {COLLAR_WALL_MIN / INCH:.4f} in under rule 17's .060 floor"
    )
# Largest radius the collar reaches: its .XX band and its float on the pilot.
COLLAR_REACH = COLLAR_DIA / 2.0 + _XX + COLLAR_FLOAT
if COLLAR_REACH > ROOT_REACH_MAX + 1e-9:
    raise AssertionError("the cutter meets the collar")
BACKING_SHARE = COLLAR_DIA / ROOT_MIN_MM
if BACKING_SHARE < BACKING_SHARE_MIN:
    raise AssertionError("T024 is backed under half its root")
ROOT_AIR = ROOT_MIN_MM / 2.0 - max(COLLAR_REACH, SHOULDER_REACH)

# --- The nut ----------------------------------------------------------------------
# #8-32 hex machine screw nut, ASME B18.6.3, 11/32 across flats
# (McMaster 90480A009; its catalogue sizes are
# _mcmaster_90480a009's): its corners stand under T024's root by AIR_MIN even
# beside the blank, and its face covers the collar's drilled bore. The stack
# takes the standard's thickness limit, not the catalogue's 1/8 nominal.
NUT_ACROSS_FLATS = _NUT_ACROSS_FLATS
NUT_ACROSS_CORNERS = NUT_ACROSS_FLATS / math.cos(math.radians(30.0))
NUT_THICKNESS_MAX = 0.130 * INCH  # B18.6.3 #8 hex machine screw nut H max
NUT_ROOT_AIR = ROOT_MIN_MM / 2.0 - NUT_ACROSS_CORNERS / 2.0
if NUT_ROOT_AIR < AIR_MIN:
    raise AssertionError("the nut's corners stand over T024's root")
if NUT_ACROSS_FLATS <= COLLAR_BORE + _DRILL_PLUS:
    raise AssertionError("the nut's face does not bear on the collar")

# --- The stack along the arbor (stations from the shoulder, mm) -------------------
# Each blank-side station stands off the shoulder by _PAIR (both from the
# grip's end face). The collar's near face is the blank's far face; its far
# face carries the nut.
COLLAR_FACE_MIN = FACE_MIN_MM + COLLAR_LENGTH - _XX
COLLAR_FACE_MAX = FACE_MAX_MM + COLLAR_LENGTH + _XX
# The nut seats on full thread: the relief ends short of the nearest collar
# face by two pitches (the die's incomplete start).
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
THREAD_PAST_NUT_MIN = (ARBOR_END - 2.0 * _XX) - (COLLAR_FACE_MAX + NUT_THICKNESS_MAX)
if THREAD_PAST_NUT_MIN < 1.5 * THREAD_PITCH:
    raise AssertionError("the nut runs off the thread's end")

# --- Model ------------------------------------------------------------------------
# The keyed arbor's recipe (MHA-DT-04's): each turned diameter a circle on the
# plane at its own end station, extruded back to the grip's end face, so every
# diameter's dimension stands on its own step in the side view and every
# length is a feature depth from that one face. The thread, larger than the
# relief, runs back only to the relief's end, so the overall length lives on
# a hidden reference sketch whose one driving dimension it is
# (drawing-simplicity-policy.md: a printed value no feature dimension
# carries). Model +Z is the axis; z = 0 (the Front Plane) is the grip's end
# face; SHOULDER_Z is the shoulder face (the ShoulderPlane).
SHOULDER_Z = GRIP_LENGTH + STANDOFF
SEAT_END_Z = SHOULDER_Z + SEAT_LENGTH
PILOT_END_Z = SHOULDER_Z + PILOT_END
RELIEF_END_Z = SHOULDER_Z + RELIEF_END
THREAD_LENGTH = ARBOR_END - RELIEF_END
ARBOR_END_Z = SHOULDER_Z + ARBOR_END
if abs(ARBOR_END_Z - OVERALL_LENGTH) > 1e-9:
    raise AssertionError("the arbor's stations do not close on its length")

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
if [d for _n, d, *_z in SECTIONS[:-1]] != sorted(
    (d for _n, d, *_z in SECTIONS[:-1]), reverse=True
):
    raise AssertionError("a section would vanish inside a smaller one before it")


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
FINISHED_VOLUME = TURNED_VOLUME

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
}
SHOULDER_EXPRESSION = '"ShoulderZ"'
OVERALL_EXPRESSION = '"OverallLength"'
THREAD_LENGTH_EXPRESSION = '"OverallLength" - "ReliefEndZ"'

# --- Drawing -------------------------------------------------------------------------
SHOULDER_PLANE = "ShoulderPlane"
SHOULDER_FILLET = "ShoulderFillet"
# The hidden reference sketch on the Right Plane (the side view's plane): a
# centreline on the axis from the grip's end face to the thread's end.
OVERALL_SKETCH = "OverallReference"


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
    OVERALL_SKETCH: {"Overall"},
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
    "ReliefDia": 3,
    "ReliefEnd": 2,
    "Overall": 2,
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
    "Overall": OVERALL_LENGTH,
    "ShoulderR": SHOULDER_R,
}
if set(DRAWING_VALUES_BY_NAME) != set(DRAWING_PRECISION_BY_NAME):
    raise AssertionError("every marked arbor dimension needs its value")
# Fabricated nominals sit on their printed grid (rule 3).
for _name, _value in DRAWING_VALUES_BY_NAME.items():
    _places = DRAWING_PRECISION_BY_NAME[_name]
    if abs(inch_grid_mm(_value, _places) - _value) > 1e-9:
        raise AssertionError(f"{_name} {_value} mm is off its .{'X' * _places} grid")

# --- Sheet words -----------------------------------------------------------------------
# One numbered note states the seat's matched fit (rule 4: one flag note
# linked to every dimension of the one feature). A matched pair names its
# mate by name and full drawing number at the callout (the keyed arbor's
# note): here the one configuration MHA-DT-03-T024.
SEAT_NOTE_NUMBER = 1
SEAT_NOTE_FLAG = f"SEE NOTE {SEAT_NOTE_NUMBER}"
SEAT_CLEARANCE_TEXT = "-".join(inch_text(value, 3) for value in SEAT_CLEARANCE_MM)
NOTE_LINE_CHARS = 72
CONE_NUMBER = _CONE_NUMBER
SEAT_MATE_TEXT = f"CONE GEAR {BLANK.number}"
SHEET_NOTES = "\n".join(
    textwrap.wrap(
        f"{SEAT_NOTE_NUMBER}. SEAT: SLIDING FIT, MATCHED TO THE BORE OF "
        f"{SEAT_MATE_TEXT}, CLEARANCE {SEAT_CLEARANCE_TEXT}.",
        NOTE_LINE_CHARS,
        subsequent_indent="   ",
        break_on_hyphens=False,
    )
)
if max(map(len, SHEET_NOTES.splitlines())) > NOTE_LINE_CHARS:
    raise AssertionError("a note line runs into the title block")
# The title block carries the thread class (rule 2).
THREAD_CALLOUT = f"{THREAD} {THREAD_SERIES}"
# The thread's schematic major cylinder reads as its designation
# (_drawing_dimensions.set_dimension_text).
DIMENSION_TEXT: dict[str, str] = {"ThreadDia": THREAD_CALLOUT}
# The relief's third place is its function: at .XX its largest limit would
# stand over the thread's root, so it says so at the callout (guidelines
# rule 3's stated-function form; machinist review of b3a18541e7 asked for
# the function or .XX). The crank-handle pivot screw's relief words.
RELIEF_CALLOUT = "UNDER THREAD ROOT"
if inch_grid_mm(RELIEF_DIA, 2) + _XX < THREAD_ROOT_MIN:
    raise AssertionError("the relief no longer needs its third place")
CALLOUTS_BELOW: dict[str, str] = {
    "SeatDia": SEAT_NOTE_FLAG,
    "ShoulderR": SEAT_NOTE_FLAG,
    "GripDia": "STOCK OK",
    "PilotDia": f"CLEARS {_COLLAR_SHORT}",
    "ReliefDia": RELIEF_CALLOUT,
}
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
