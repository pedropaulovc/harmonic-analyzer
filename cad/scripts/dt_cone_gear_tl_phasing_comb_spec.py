r"""Pure-data contract for the cone tip gears' phasing comb (MHA-DT-03-TL-02).

Shop tooling, not a machine part (cad/docs/subsystem-identities.md): the
fixture MHA-DT-00 step 1 engages while LOCTITE 638 grabs, so the bonded tip
gears cure in phase with the keyed stack (owner ruling 2026-11-09 (b1) via PR
#1992, C1 keyed; single blade per gear, owner ruling 2026-11-10 via PR #1992).
The 1898 machine has no such tool (its gears are fixed differently); this is
shop tooling for the replica's bonded tip. Owner ruling 2026-11-13: the comb
is cut to shape from a single sheet of metal. Owner, 2026-11-14 (#2734): the
cone is assembled standing up like a pyramid, so the comb is one flat U,
SHEET_THICK thick as bought, clipped over the tip: no blade is thinned, no
face is a datum and nothing is bent.

Every cone gear has a tooth centred on its local +X (phase 0; the keyway runs
through T030's), so a tooth space is centred at +180/N deg on every gear. A
space's centre stands about half a circular pitch off the +X radial plane on
every 48 DP gear at its pitch circle, so one sheet lying parallel to that
plane, that far off it, passes down the space beside the phase-0 tooth of
T030 (the reference, keyed) and of the bonded T024, T018, T012 (MHA-DT-03)
and T006 (MHA-DT-37) at once. T030 has an even count, so across the cone the
same plane passes down T030's space at 180 - 180/30 deg, the mirror of the
first.

The U. Its near arm's edge is a staircase: one level (a blade) per gear, each
deeper than the last, south to north. Its far arm is a plain blade in T030's
mirror space. The bridge joins them over MHA-DT-37's pivot. Both arms stand
on T036 (MHA-DT-04 stands on its journal, MHA-DT-00 step 1), so the comb's
south end is T030's south face. The span between the two T030 blades is cut
under T030's root diameter: the far arm is a spring that holds both blades
on their seats, so the U can turn across the cone only as far as both T030
spaces let it (LEAN_MAX_RAD).

Frame (the SolidWorks model). X runs along the cone axis, north (up as the
cone stands); Y runs radially outward through the near arm, along the gears'
+X; Z is the tangential direction, the gears' +Y (the sheet's thickness). The
origin is the near arm's south end on its T030 blade's edge: the SEAT line.

The seat: each T030 blade drops into its space until it bottoms on T030's
root; on the thickest sheet over the narrowest root space it binds between
the flanks just above it instead. Where it bottoms, the sheet may slide
across the space as far as the space lets it (``SEAT_CONDITIONS``,
``COMB_SLIDE_MM``). Every other blade stands at its printed depth under the
seat line, at the title block's .XXX band; each bonded gear turns until its
space holds its blade, anywhere in that space's play, while it floats any
way by BOND_FLOAT_MM and the U leans as far as LEAN_MAX_RAD. The depths are
the deepest on the .001 grid at which no blade bottoms on its gear's root or
binds in its space at any of those limits: the deeper the blade, the
narrower the space and the less play. ``PHASE_ERROR_MM`` proves every bonded
gear's worst phase against T030 at every limit inside the booked
error_budget.yaml cone_tip_bond_clock.
"""

from __future__ import annotations

import functools
import math

import _config
import cone_tip_cluster as cluster
import dt_cone_gear_spec as family
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm
from cone_stack_end_play import STACK_FEELER, STACK_FEELER_BAND

PART_NAME = "dt-cone-gear-tl-phasing-comb"
_ROW = _config.parts("dt-cone-gear-tl-phasing-comb")
if PART_NAME != "dt-cone-gear-tl-phasing-comb":
    raise AssertionError("PART_NAME and the registry row it reads disagree")
PART_NUMBER = str(_ROW["number"])
UNIT = drawing_unit("parts/dt-cone-gear-tl-phasing-comb", _ROW)
INCH = family.MM_PER_IN
if UNIT != "in":
    raise AssertionError("the phasing comb prints in inch")

# --- The gears it phases, south to north --------------------------------------
# T030 is keyed (the reference); the others are bonded with the comb engaged.
GEARS = (30, 24, 18, 12, 6)
REFERENCE_TEETH = GEARS[0]
BONDED_TEETH = GEARS[1:]
if family.keyed(REFERENCE_TEETH) is not True:
    raise AssertionError("the comb's reference gear must be keyed")
if any(teeth in family.KEYED_TEETH for teeth in BONDED_TEETH):
    raise AssertionError("every other comb gear must be a bonded tip gear")
if REFERENCE_TEETH % 2:
    raise AssertionError("the far blade's mirror space needs an even T030")
_FAMILY_NUMBER = str(_config.parts("dt-cone-gear")["number"])
_TIP_GEAR_NUMBER = str(_config.parts("dt-cone-tip-gear")["number"])


def gear_number(teeth: int) -> str:
    """The drawing number the comb's blade serves."""
    if teeth == 6:
        return _TIP_GEAR_NUMBER
    return family.configuration_number(_FAMILY_NUMBER, teeth)


def gear_tag(teeth: int) -> str:
    """The name a blade carries in the model: ``T030``."""
    return f"T{teeth:03d}"


# --- The title block's bands (inch sheet) -------------------------------------
_XX = printed_band_mm(2, unit=UNIT)
DEPTH_PLACES = 3
_XXX = printed_band_mm(DEPTH_PLACES, unit=UNIT)


def inch_grid_mm(value_mm: float, places: int, rounding=round) -> float:
    """``value_mm`` on the printed inch grid (rule 3)."""
    return family.inch_grid_mm(value_mm, places, rounding)


def inch_text(value_mm: float, places: int) -> str:
    return family.inch_text(value_mm, places)


# --- The sheet ----------------------------------------------------------------
# .020 in shim stock as bought. The registry row names the stock (one line
# there changes it): 1095 blue-tempered spring steel (McMaster-Carr 9014K143,
# ASTM A684 / SAE AMS5122, +/-.001 in, read 2026-11-14), or half-hard C26000
# brass (9011K111, ASTM B36, +/-.002 in, read 2026-11-13). The proof takes
# the wider +/-.002 so either stock serves. Of the stock gauges .015, .020
# and .025, .020 is the one whose worst phase stays inside the booked bond
# clock: thinner leaves more play in every space, and .025 binds in T030's
# space at a depth that its tolerance moves by several times as much.
SHEET_THICK = 0.020 * INCH
SHEET_THICK_TOLERANCE_MM = 0.002 * INCH
SHEET_LIMITS_MM = (
    SHEET_THICK - SHEET_THICK_TOLERANCE_MM,
    SHEET_THICK,
    SHEET_THICK + SHEET_THICK_TOLERANCE_MM,
)
# The model's material follows the row (see _appearance.apply_material).
MATERIAL = "Brass" if "BRASS" in str(_ROW["material"]).upper() else "Plain Carbon Steel"
# The spring arm is proven on the weaker stock, so it serves in either:
# half-hard C26000 yields at Rp0.2 >= 270 MPa (Wieland M30, H02) on a 110 GPa
# modulus (16,000 ksi, Copper Development Association C26000), both read
# 2026-11-14; hardened 1095 at about 230 ksi tensile (Precision Brand AMS 5122
# certificate) on about twice the modulus bends several times as far.
SPRING_YIELD_STRAIN = 270.0 / 110_000.0


# --- Gear radii, read from the family's tooth layer ---------------------------
def pitch_radius_mm(teeth: int) -> float:
    return family.stock_form_profile(teeth).pitch_radius_mm


def tip_radius_limits_mm(teeth: int) -> tuple[float, float]:
    """(smallest, largest) printed tip radius."""
    outside = family.outside_dia_mm(teeth)
    upper, lower = family.blank_dia_band(teeth)
    return (outside + lower) / 2.0, (outside + upper) / 2.0


def space_angle_rad(teeth: int) -> float:
    """The blade's tooth space's centre: +180/N deg from the phase-0 tooth."""
    return math.pi / teeth


# --- Axial: the comb stands on T036 -------------------------------------------
FACE_WIDTH = family.FACE_WIDTH
_FACE_BAND = abs(family.FACE_WIDTH_BAND[1])


def _south_face_mm(teeth: int) -> float:
    """Nominal south face of ``teeth``'s leaves from T030's south face: T030,
    one STACK_FEELER, then T024, T018, T012 and T006 face to face."""
    index = GEARS.index(teeth)
    return index * FACE_WIDTH + (STACK_FEELER if index else 0.0)


# The keyed gears slide on face to face (MHA-DT-00 1B), so T036's north face
# is T030's south face, where both arms stand: the comb's south end. Each
# blade's level runs from the step at its south end north to the next step:
# over its own gear's face, then over the smaller gear beyond it, whose tips
# it clears (below). Each step stands BLADE_INSET north of its gear's south
# face, so it never stands over the larger gear south of it (the deeper level
# would strike that gear's teeth), and T006's level, BLADE_LENGTH long, stops
# BLADE_INSET inside T006's north face, where MHA-DT-38 is pressed on; past
# it the arm's edge returns to the seat line, well out of MHA-DT-38's reach.
# Every length is .XX at
# the title block's band (rule 3); AXIAL_MARGIN_MM proves each step and the
# level's end clear at every stack and print limit.
BLADE_INSET = 0.030 * INCH
BLADE_LENGTH_PLACES = 2
BLADE_LENGTH = inch_grid_mm(
    FACE_WIDTH - 2.0 * BLADE_INSET, BLADE_LENGTH_PLACES, math.floor
)
# Blade south ends (the steps) from the comb's south end, printed; T030's
# blade starts at the south end.
BLADE_START_MM: dict[int, float] = {
    teeth: (
        0.0
        if teeth == REFERENCE_TEETH
        else inch_grid_mm(
            _south_face_mm(teeth) + BLADE_INSET, BLADE_LENGTH_PLACES, math.ceil
        )
    )
    for teeth in GEARS
}
LEVEL_END_MM = BLADE_START_MM[GEARS[-1]] + BLADE_LENGTH
# T006's north face at the longest stack: every face and the feeler long.
_T006_NORTH_MAX_MM = (
    _south_face_mm(GEARS[-1]) + FACE_WIDTH + len(GEARS) * _FACE_BAND + STACK_FEELER_BAND
)


def axial_margins_mm() -> dict[str, float]:
    """Least clearance at any stack and print limit: each step north of its
    gear's south face, and T006's level's end south of T006's north face.
    A station moves by every face south of it and, past T030, the feeler; a
    printed length by the title block's band."""
    margins = {
        gear_tag(teeth): BLADE_START_MM[teeth]
        - _XX
        - (_south_face_mm(teeth) + index * _FACE_BAND + STACK_FEELER_BAND)
        for index, teeth in enumerate(GEARS)
        if teeth != REFERENCE_TEETH
    }
    north_min = (
        _south_face_mm(GEARS[-1])
        + FACE_WIDTH
        - len(GEARS) * _FACE_BAND
        - STACK_FEELER_BAND
    )
    margins["end"] = north_min - (LEVEL_END_MM + _XX)
    return margins


AXIAL_MARGIN_MM = min(axial_margins_mm().values())
if AXIAL_MARGIN_MM <= 0.0:
    raise AssertionError(
        f"comb axial margin {AXIAL_MARGIN_MM:.3f} mm: a step overhangs its gear"
    )

# Before the compound grabs a bonded gear may float any way by half its bond
# clearance (T024 on land 2; T018, T012 and T006's spigot on .0625).
BOND_FLOAT_MM = max(
    *(family.bond_clearance_mm(teeth)[1] / 2.0 for teeth in (24, 18, 12)),
    cluster.SPIGOT_BOND_CLEARANCE_MM[1] / 2.0,
)
# The tip over T030's south face: MHA-DT-37's pivot at its .XX length's top
# over T006's north face; MHA-DT-38 (.XXX OD) on it, off a floating axis.
PIVOT_END_MAX_MM = _T006_NORTH_MAX_MM + cluster.PIVOT_LENGTH_MM + _XX
BUSHING_REACH_MM = (cluster.BUSHING_OD_MM + _XXX) / 2.0 + BOND_FLOAT_MM


# --- The tooth space against a blade -----------------------------------------
def _profiles(teeth: int):
    return family.manufacturing_corner_profiles(teeth)


_GAP_SAMPLES = 96


@functools.cache
def _gap_table(teeth: int, corner: int) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """(radii, half-space angles) of ``teeth``'s printed corner from just over
    its root to its tip."""
    profile = _profiles(teeth)[corner]
    low = profile.root_radius_max_mm * (1.0 + 1e-9)
    top = min(profile.blank_radius_mm, profile.support_radius_max_mm)
    radii = tuple(low + (top - low) * i / _GAP_SAMPLES for i in range(_GAP_SAMPLES + 1))
    return radii, tuple(profile._gap_angle_at_radius(r) for r in radii)


def _half_space_rad(teeth: int, corner: int, radius_mm: float) -> float:
    radii, gaps = _gap_table(teeth, corner)
    if not radii[0] <= radius_mm <= radii[-1]:
        raise ValueError(f"T{teeth:03d}: {radius_mm} mm is off the tooth space")
    step = (radii[-1] - radii[0]) / _GAP_SAMPLES
    index = min(int((radius_mm - radii[0]) / step), _GAP_SAMPLES - 1)
    share = (radius_mm - radii[index]) / step
    return gaps[index] + share * (gaps[index + 1] - gaps[index])


def root_radius_mm(teeth: int, corner: int) -> float:
    return _profiles(teeth)[corner].root_radius_max_mm


def play_window_rad(
    teeth: int, corner: int, edge_mm: float, near_mm: float, far_mm: float
) -> tuple[float, float]:
    """(least, greatest) turn of ``teeth``'s gear (printed ``corner``) from its
    phase that keeps every point of a blade in the space centred on
    SPACE_ANGLE: the blade's edge at ``edge_mm`` along the gear's +X, the
    sheet's faces at ``near_mm`` and ``far_mm`` along +Y. Each radius from the
    edge's nearest corner out to the gear's tip meets the blade over one arc;
    the space must hold it. Raises ValueError where the blade bottoms on the
    root."""
    radii, _gaps = _gap_table(teeth, corner)
    nearest = math.hypot(edge_mm, near_mm)
    if nearest <= radii[0]:
        raise ValueError(f"T{teeth:03d} blade bottoms on the root")
    samples = sorted(
        {nearest, *(r for r in (math.hypot(edge_mm, far_mm),) if r < radii[-1])}
        | {r for r in radii if r > nearest}
    )
    centre = space_angle_rad(teeth)
    low, high = -math.inf, math.inf
    for radius in samples:
        half = _half_space_rad(teeth, corner, radius)
        reach = min(far_mm, math.sqrt(max(0.0, radius * radius - edge_mm * edge_mm)))
        high = min(high, math.asin(near_mm / radius) + half - centre)
        low = max(low, math.asin(reach / radius) - half - centre)
    return low, high


def _window(
    teeth: int, corner: int, edge_mm: float, mid_mm: float, sheet_mm: float
) -> tuple[float, float]:
    """``play_window_rad`` for the sheet's mid-plane at ``mid_mm``."""
    return play_window_rad(
        teeth, corner, edge_mm, mid_mm - sheet_mm / 2.0, mid_mm + sheet_mm / 2.0
    )


def _bisect(holds, low: float, high: float) -> float:
    """The boundary of a predicate false at ``low`` and true at ``high``."""
    if holds(low) or not holds(high):
        raise AssertionError("bisection bounds do not bracket the boundary")
    for _ in range(56):
        middle = (low + high) / 2.0
        if holds(middle):
            high = middle
        else:
            low = middle
    return (low + high) / 2.0


# --- The seat on T030 ---------------------------------------------------------
# The sheet's mid-plane is searched over this band along T030's +Y (half a
# circular pitch is .0327).
_MID_SEARCH_MM = (0.020 * INCH, 0.042 * INCH)


def _slide_mm(corner: int, sheet_mm: float, edge_of) -> tuple[float, float]:
    """(least, greatest) mid-plane along T030's +Y that holds T030 at its
    phase, the blade's edge at ``edge_of(mid)``: the window's top meets the
    phase at the least, its bottom at the greatest (both rise with it)."""

    def window(mid: float) -> tuple[float, float]:
        return _window(REFERENCE_TEETH, corner, edge_of(mid), mid, sheet_mm)

    return (
        _bisect(lambda mid: window(mid)[1] >= 0.0, *_MID_SEARCH_MM),
        _bisect(lambda mid: window(mid)[0] > 0.0, *_MID_SEARCH_MM),
    )


def _seat(corner: int, sheet_mm: float) -> tuple[tuple[float, float], ...]:
    """(edge, mid-plane) of the comb resting on T030 at one printed corner and
    sheet: bottomed on the root at either end of its slide, or bound between
    the flanks above the root (one point)."""
    root = root_radius_mm(REFERENCE_TEETH, corner) * (1.0 + 1e-7)

    def on_root(mid: float) -> float:
        return math.sqrt(root * root - (mid - sheet_mm / 2.0) ** 2)

    least, greatest = _slide_mm(corner, sheet_mm, on_root)
    if least <= greatest:
        return (on_root(least), least), (on_root(greatest), greatest)
    # Bound above the root: lift the blade until some slide holds T030 (it
    # does well before its edge reaches the pitch circle).
    top = pitch_radius_mm(REFERENCE_TEETH) * math.cos(space_angle_rad(REFERENCE_TEETH))

    def lifted(lift: float):
        return lambda mid: on_root(mid) + lift

    def clear(lift: float) -> bool:
        low, high = _slide_mm(corner, sheet_mm, lifted(lift))
        return low <= high

    lift = _bisect(clear, 0.0, top - root)
    least, greatest = _slide_mm(corner, sheet_mm, lifted(lift))
    mid = (least + greatest) / 2.0
    return ((lifted(lift)(mid), mid),)


# Each T030 blade's seats at every printed corner and sheet.
_SEATS = {
    (corner, sheet): _seat(corner, sheet)
    for corner in range(len(_profiles(REFERENCE_TEETH)))
    for sheet in SHEET_LIMITS_MM
}
# (edge, mid-plane, sheet) of every seat at every printed corner and sheet.
SEAT_CONDITIONS: tuple[tuple[float, float, float], ...] = tuple(
    (edge, mid, sheet)
    for (_corner, sheet), seats in _SEATS.items()
    for edge, mid in seats
)
SEAT_EDGE_MM = (
    min(edge for edge, _mid, _sheet in SEAT_CONDITIONS),
    max(edge for edge, _mid, _sheet in SEAT_CONDITIONS),
)
# How far the comb slides across T030's space, along its +Y.
COMB_SLIDE_MM = (
    min(mid for _edge, mid, _sheet in SEAT_CONDITIONS),
    max(mid for _edge, mid, _sheet in SEAT_CONDITIONS),
)
_SEAT_EDGE_MID = sum(SEAT_EDGE_MM) / 2.0


# --- The U --------------------------------------------------------------------
# The span between the two T030 blades' edges (.XXX, the title block's band)
# is under T030's root diameter at every limit: the far arm springs both
# blades onto their seats, so neither lifts off. It spreads up to
# SPREAD_MAX_MM in use.
GRIP_PLACES = 3
# At its widest print the span still takes this much interference, so the
# spring always preloads both blades on their seats.
GRIP_PRELOAD_MIN_MM = 0.002 * INCH
GRIP_SPAN = inch_grid_mm(
    2.0 * SEAT_EDGE_MM[0] - _XXX - GRIP_PRELOAD_MIN_MM, GRIP_PLACES, math.floor
)
if GRIP_SPAN + _XXX + GRIP_PRELOAD_MIN_MM > 2.0 * SEAT_EDGE_MM[0] + 1e-9:
    raise AssertionError("the U's span must grip T030 at every limit")
SPREAD_MAX_MM = 2.0 * SEAT_EDGE_MM[1] - (GRIP_SPAN - _XXX)
# The far arm (.XX wide) is the spring, at rule 17's .080 wall target so its
# narrowest print holds the .060 floor; the U's overall height (.XX) leaves
# the near arm about .25 over the seat line, a grip for the fingers, and the
# bridge is as wide.
SPRING_WIDTH = 0.08 * INCH
if SPRING_WIDTH - _XX < 0.060 * INCH - 1e-9:
    raise AssertionError("the spring arm's narrowest print is under rule 17's floor")
SHEET_HEIGHT = inch_grid_mm(0.25 * INCH + GRIP_SPAN + SPRING_WIDTH, 2, math.ceil)
ARM_WIDTH = SHEET_HEIGHT - GRIP_SPAN - SPRING_WIDTH
# Its narrowest print: the height's, the span's and the spring's bands.
ARM_WIDTH_MIN_MM = ARM_WIDTH - 2.0 * _XX - _XXX
# Clipped on, the near arm stands this far out (no blade reaches under its
# gear's root) while it is lowered past MHA-DT-38, so the far arm opens by
# INSTALL_SPREAD_MM before both close on their seats (MHA-DT-00 step 1).
INSTALL_LIFT_MM = BUSHING_REACH_MM - min(
    root_radius_mm(GEARS[-1], corner) for corner in range(len(_profiles(GEARS[-1])))
)
INSTALL_SPREAD_MM = INSTALL_LIFT_MM + SPREAD_MAX_MM
# Opened that far as a cantilever from the bridge the spring's root strains
# 1.5 * width * spread / length^2; the slot is long enough to keep that under
# SPRING_YIELD_STRAIN at its widest and shortest print, and in any case clears
# the pivot's end.
# The slot's closed end is a full round (a drilled hole the slot's sides are
# sawn to), so the spring arm runs into the bridge with no sharp root.
# SLOT_LENGTH (.XX) runs to the round's centre, where its straight sides end:
# that straight length is the spring's cantilever, and the round reaches the
# axis SLOT_END_RADIUS_MM further, clear of the pivot's end.
SLOT_END_RADIUS_MM = GRIP_SPAN / 2.0
SPRING_LENGTH_MIN_MM = math.sqrt(
    1.5 * (SPRING_WIDTH + _XX) * INSTALL_SPREAD_MM / SPRING_YIELD_STRAIN
)
SLOT_LENGTH = inch_grid_mm(
    max(PIVOT_END_MAX_MM - SLOT_END_RADIUS_MM, SPRING_LENGTH_MIN_MM) + _XX,
    2,
    math.ceil,
)
SLOT_END_MM = SLOT_LENGTH + SLOT_END_RADIUS_MM
SPRING_STRAIN = (
    1.5 * (SPRING_WIDTH + _XX) * INSTALL_SPREAD_MM / (SLOT_LENGTH - _XX) ** 2
)
if SPRING_STRAIN >= SPRING_YIELD_STRAIN:
    raise AssertionError(f"the spring arm yields opening ({SPRING_STRAIN:.5f})")
# The bridge is at least .25 wide past the round, as the near arm about.
SHEET_LENGTH = inch_grid_mm(SLOT_END_MM + 0.25 * INCH, 2, math.ceil)
# The far arm's edge stands over every bonded gear's tips on its seat.
if SEAT_EDGE_MM[0] <= max(tip_radius_limits_mm(t)[1] for t in BONDED_TEETH) + (
    BOND_FLOAT_MM
):
    raise AssertionError("the far arm reaches a bonded gear's tips")

# With both T030 blades seated the U turns about its near seat line only as
# far as both spaces let the blades slide (the far one 2 R across): each
# slides at most SLIDE_WIDTH_MM.
SLIDE_WIDTH_MM = max(seats[-1][1] - seats[0][1] for seats in _SEATS.values())
LEAN_MAX_RAD = 2.0 * SLIDE_WIDTH_MM / (4.0 * SEAT_EDGE_MM[0])
# Turned about the radial line through both T030 blades (yaw), the sheet is
# held only by T030's face: each T030 blade's mid-plane may stand anywhere in
# its slide at both ends of that face, so a station x north of the south end
# stands on the line through the two.
T030_FACE_MM = FACE_WIDTH - _FACE_BAND
YAW_MAX_RAD = SLIDE_WIDTH_MM / T030_FACE_MM


def _seat_lines(seats) -> tuple[tuple[float, float, float], ...]:
    """(edge, mid at x = 0, mid at x = T030_FACE_MM) of each extreme line."""
    (e0, m0), (e1, m1) = seats[0], seats[-1]
    lines = {(e0, m0, m0), (e1, m1, m1), (e0, m0, m1), (e1, m1, m0)}
    return tuple(sorted(lines))


SEAT_LINES: tuple[tuple[float, float, float, float], ...] = tuple(
    (edge, start, end, sheet)
    for (_corner, sheet), seats in _SEATS.items()
    for edge, start, end in _seat_lines(seats)
)


def blade_span_mm(teeth: int) -> tuple[float, float]:
    """The stretch of a bonded blade inside its own gear's face."""
    return BLADE_START_MM[teeth], BLADE_START_MM[teeth] + BLADE_LENGTH


def _flex_share(station_mm: float) -> float:
    """Of the spread the two T030 blades take, the share by which a near-arm
    point ``station_mm`` north of the south end ends deeper than the near
    T030 blade: the near arm bends as a cantilever off the bridge and turns
    with the bridge's end. Beam formulas, one modulus and thickness
    throughout (they cancel): the near arm and bridge at their narrowest
    print, the spring at its widest."""
    length = SLOT_LENGTH
    across = SHEET_HEIGHT + _XX
    stiff = ARM_WIDTH_MIN_MM**3
    spring = (SPRING_WIDTH + _XX) ** 3
    root = length - station_mm
    near = (length**3 / 3.0 - root**2 * (3.0 * length - root) / 6.0) / stiff
    turn = length * across * station_mm / (2.0 * stiff)
    spread = (
        length**3 / (3.0 * spring)
        + length**3 / (3.0 * stiff)
        + length**2 * across / stiff
    )
    return (near + turn) / spread


def blade_x_mm(teeth: int) -> tuple[float, float]:
    """(south, north) model x of ``teeth``'s level: its step to the next
    step (T030's from the south end, T006's to LEVEL_END_MM)."""
    index = GEARS.index(teeth)
    south = BLADE_START_MM[teeth]
    north = LEVEL_END_MM if teeth == GEARS[-1] else BLADE_START_MM[GEARS[index + 1]]
    return south, north


# How much deeper than printed each bonded blade can stand, the far arm
# spread its most.
FLEX_MM: dict[int, float] = {
    teeth: SPREAD_MAX_MM * _flex_share(blade_x_mm(teeth)[1]) for teeth in BONDED_TEETH
}


# --- Each bonded blade's depth below the seat line -----------------------------
def _float_mm(teeth: int) -> float:
    return 0.0 if teeth == REFERENCE_TEETH else BOND_FLOAT_MM


# The float's directions sampled round its circle.
_FLOAT_DIRECTIONS = 16


def _conditions(teeth: int, depth_mm: float):
    """Every limit a bonded blade meets: each seat, the U leaned either way,
    each tooth corner of its gear, the depth's band (deeper by the arm's
    flex) and the gear's float round its circle. Yields (corner, edge,
    mid-plane, sheet across the space)."""
    drift = _float_mm(teeth)
    floats = tuple(
        (
            drift * math.cos(2.0 * math.pi * k / _FLOAT_DIRECTIONS),
            drift * math.sin(2.0 * math.pi * k / _FLOAT_DIRECTIONS),
        )
        for k in range(_FLOAT_DIRECTIONS)
    )
    bands = (-_XXX - FLEX_MM[teeth], _XXX)
    south, north = blade_span_mm(teeth)
    for edge, start, end, sheet_mm in SEAT_LINES:
        at_south = start + (end - start) * south / T030_FACE_MM
        at_north = start + (end - start) * north / T030_FACE_MM
        mid = (at_south + at_north) / 2.0
        sweep = abs(at_north - at_south)
        for lean in (-LEAN_MAX_RAD, LEAN_MAX_RAD):
            # Turned about the seat line, a point the depth below it rises
            # by depth * (1 - cos) and moves across by depth * sin.
            rise = depth_mm * (1.0 - math.cos(lean))
            across = depth_mm * math.sin(lean)
            thick = sheet_mm / math.cos(lean) + sweep
            for corner in range(len(_profiles(teeth))):
                for band in bands:
                    for radial, tangential in floats:
                        yield (
                            corner,
                            edge - depth_mm + band + rise + radial,
                            mid + across + tangential,
                            thick,
                        )


# At every limit each blade keeps this much play at its edge (the wax film
# and a sheared burr live in it) and this much air over its gear's root.
BLADE_PLAY_MM = 0.0005 * INCH
ROOT_AIR_MM = 0.002 * INCH


def _enters(teeth: int, depth_mm: float) -> bool:
    """At every limit the blade keeps its play and its root air."""
    for corner, edge, mid, sheet in _conditions(teeth, depth_mm):
        if math.hypot(edge, mid - sheet / 2.0) < root_radius_mm(teeth, corner) + (
            ROOT_AIR_MM
        ):
            return False
        try:
            low, high = _window(teeth, corner, edge, mid, sheet)
        except ValueError:
            return False
        if (high - low) * math.hypot(edge, mid) < BLADE_PLAY_MM:
            return False
    return True


def _design_depth(teeth: int) -> float:
    """The deepest .001 depth below the seat line at which ``teeth``'s blade
    enters at every limit, searched down from the gear's pitch circle."""
    mil = 0.001 * INCH
    shallow = math.floor((_SEAT_EDGE_MID - pitch_radius_mm(teeth)) / mil)
    deep = math.ceil((SEAT_EDGE_MM[1] + _XXX - root_radius_mm(teeth, 0)) / mil) + 1
    if not _enters(teeth, shallow * mil) or _enters(teeth, deep * mil):
        raise AssertionError(f"T{teeth:03d}: depth search does not bracket")
    while deep - shallow > 1:
        middle = (shallow + deep) // 2
        if _enters(teeth, middle * mil):
            shallow = middle
        else:
            deep = middle
    return shallow * mil


# Printed, seat line down (positive): each bonded blade's edge.
BLADE_DEPTH_MM: dict[int, float] = {t: _design_depth(t) for t in BONDED_TEETH}


def blade_depth_mm(teeth: int) -> float:
    return 0.0 if teeth == REFERENCE_TEETH else BLADE_DEPTH_MM[teeth]


for _teeth in BONDED_TEETH:
    # Engaged: at the shallowest limit the blade's edge stands inside the
    # gear's smallest tip circle.
    _shallowest = SEAT_EDGE_MM[1] - BLADE_DEPTH_MM[_teeth] + _XXX + BOND_FLOAT_MM
    _across = (
        COMB_SLIDE_MM[1]
        + BOND_FLOAT_MM
        + BLADE_DEPTH_MM[_teeth] * math.sin(LEAN_MAX_RAD)
    )
    if math.hypot(_shallowest, _across) >= tip_radius_limits_mm(_teeth)[0]:
        raise AssertionError(f"T{_teeth:03d} blade stands over its gear's tips")
# Each level passes over the next, smaller gear's tips (its own blade's step
# stands BLADE_INSET into that gear's face) at the lowest print and seat, its
# deepest flex and the smaller gear's float.
INSIDE_CORNER_MAX_MM = 0.040 * INCH
for _south, _north in zip(GEARS, GEARS[1:], strict=False):
    _band = 0.0 if _south == REFERENCE_TEETH else _XXX + FLEX_MM[_south]
    _lowest = SEAT_EDGE_MM[0] - blade_depth_mm(_south) - _band
    if _lowest <= tip_radius_limits_mm(_north)[1] + BOND_FLOAT_MM:
        raise AssertionError(f"T{_south:03d} level reaches T{_north:03d}'s tips")
    # The step's inside corner at the title block's R.040 MAX hangs below the
    # level by at most this over the smaller gear's face.
    _r = INSIDE_CORNER_MAX_MM
    _u = min(axial_margins_mm()[gear_tag(_north)], _r)
    _sag = _r - math.sqrt(_r * _r - (_r - _u) ** 2)
    if _lowest - _sag <= tip_radius_limits_mm(_north)[1] + BOND_FLOAT_MM:
        raise AssertionError(f"T{_south:03d} step corner reaches T{_north:03d}'s tips")
# Past T006's level the near arm's edge returns to the seat line, flexed in
# by the most the spread bends it there, and stands clear of MHA-DT-38.
if SEAT_EDGE_MM[0] - _flex_share(SLOT_LENGTH) * SPREAD_MAX_MM <= BUSHING_REACH_MM:
    raise AssertionError("the near arm reaches MHA-DT-38 past T006's level")


def phase_error_mm(teeth: int) -> float:
    """A bonded gear's worst phase against T030, pitch arc: the comb on T030
    at every seat and lean, the gear's corner, its blade's depth band and
    flex and its float, the gear turned to either end of its space's play
    about the blade."""
    worst = 0.0
    for corner, edge, mid, sheet in _conditions(teeth, BLADE_DEPTH_MM[teeth]):
        low, high = _window(teeth, corner, edge, mid, sheet)
        worst = max(worst, high, -low)
    return worst * pitch_radius_mm(teeth)


BOND_CLOCK_TOLERANCE_MM = float(
    _config._doc("error_budget")["critical_features"]["cone_tip_bond_clock"][
        "tolerance"
    ]
)
PHASE_ERROR_MM = {teeth: phase_error_mm(teeth) for teeth in BONDED_TEETH}
for _teeth, _error in PHASE_ERROR_MM.items():
    if _error > BOND_CLOCK_TOLERANCE_MM:
        raise AssertionError(
            f"T{_teeth:03d} phases to +/-{_error:.4f} mm pitch arc, over the "
            f"booked {BOND_CLOCK_TOLERANCE_MM} mm"
        )

# --- Pose in the shop kit (MHA-DT-03-TL-00) -----------------------------------
# The comb's model origin (mm) in the kit frame, in the index plate's front
# plane under its rim, clear of it and over the kit's isometric; the kit's
# build places it here and its sheet shows it there under item 1.
KIT_POSITION_MM = (-17.0, -63.5, 0.0)


# --- Model --------------------------------------------------------------------
def blade_depth_name(teeth: int) -> str:
    return f"BladeDepth{gear_tag(teeth)}"


def blade_start_name(teeth: int) -> str:
    return f"Start{gear_tag(teeth)}"


# Model globals: name -> value (mm); the build sets each and drives from it.
GLOBALS: dict[str, float] = {
    "SheetLength": SHEET_LENGTH,
    "SlotLength": SLOT_LENGTH,
    "SheetHeight": SHEET_HEIGHT,
    "SpringWidth": SPRING_WIDTH,
    "GripSpan": GRIP_SPAN,
    "LevelEnd": LEVEL_END_MM,
    "SheetThick": SHEET_THICK,
    **{blade_start_name(t): BLADE_START_MM[t] for t in BONDED_TEETH},
    **{blade_depth_name(t): BLADE_DEPTH_MM[t] for t in BONDED_TEETH},
}


def profile_points_mm() -> list[tuple[float, float]]:
    """The closed U the sheet sketch draws (model mm: x north, y outward
    through the near arm): the near arm's south end down to the seat line,
    each level north to its step and down the step, T006's level to its end,
    back up to the seat line and on to the bridge, across under the bridge to
    the spring arm, down its inner edge (the far T030 blade's), across its
    south end, up its outer edge, back across the bridge's top and down the
    near arm's back."""
    points = [(0.0, ARM_WIDTH), (0.0, 0.0)]
    for teeth in GEARS[1:]:
        south, _north = blade_x_mm(teeth)
        points.append((south, -blade_depth_mm(GEARS[GEARS.index(teeth) - 1])))
        points.append((south, -blade_depth_mm(teeth)))
    far = -(GRIP_SPAN + SPRING_WIDTH)
    points += [
        (LEVEL_END_MM, -blade_depth_mm(GEARS[-1])),
        (LEVEL_END_MM, 0.0),
        (SLOT_LENGTH, 0.0),
        (SLOT_LENGTH, -GRIP_SPAN),
        (0.0, -GRIP_SPAN),
        (0.0, far),
        (SHEET_LENGTH, far),
        (SHEET_LENGTH, ARM_WIDTH),
    ]
    return points


def step_corner_index(teeth: int) -> int:
    """Index in ``profile_points_mm`` of the lower corner of the step at
    ``teeth``'s level's south end, where its start and depth are measured."""
    return 1 + 2 * GEARS.index(teeth)


ORIGIN = "origin"
LEVEL_END_POINT = 10
# The near arm's edge from here to SLOT_POINT lies on the seat line (one
# line with the T030 blade's edge, from the origin).
RETURN_POINT = 11
SLOT_POINT = 12
GRIP_POINT = 14
SPRING_POINT = 15
CORNER_POINT = 16
TOP_POINT = 17
# The sketch's driving dimensions: (global, from, to, kind), each end the
# origin or an index in ``profile_points_mm``; every value a global's.
SKETCH_DIMENSIONS: tuple[tuple[str, str | int, int, str], ...] = (
    ("SheetLength", 0, TOP_POINT, "horizontal_distance"),
    ("SheetHeight", CORNER_POINT, TOP_POINT, "vertical_distance"),
    *(
        (blade_start_name(t), ORIGIN, step_corner_index(t), "horizontal_distance")
        for t in BONDED_TEETH
    ),
    *(
        (blade_depth_name(t), ORIGIN, step_corner_index(t), "vertical_distance")
        for t in BONDED_TEETH
    ),
    ("LevelEnd", ORIGIN, LEVEL_END_POINT, "horizontal_distance"),
    ("SlotLength", ORIGIN, SLOT_POINT, "horizontal_distance"),
    ("GripSpan", ORIGIN, GRIP_POINT, "vertical_distance"),
    ("SpringWidth", GRIP_POINT, SPRING_POINT, "vertical_distance"),
)


def sketch_point_mm(ref: str | int) -> tuple[float, float]:
    return (0.0, 0.0) if ref == ORIGIN else profile_points_mm()[ref]


if profile_points_mm()[1] != (0.0, 0.0):
    raise AssertionError("the model origin is the near arm's south end on the seat")
for _name, _from, _to, _kind in SKETCH_DIMENSIONS:
    (_x0, _y0), (_x1, _y1) = sketch_point_mm(_from), sketch_point_mm(_to)
    _span = abs(_x1 - _x0) if _kind == "horizontal_distance" else abs(_y1 - _y0)
    if abs(_span - GLOBALS[_name]) > 1e-9:
        raise AssertionError(f"{_name} does not measure its own sketch points")
if {name for name, *_rest in SKETCH_DIMENSIONS} != set(GLOBALS) - {"SheetThick"}:
    raise AssertionError("every sketch global is one driving dimension")


def _area(points: list[tuple[float, float]]) -> float:
    return 0.5 * abs(
        sum(
            x0 * y1 - x1 * y0
            for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1], strict=True)
        )
    )


# The slot's round end (between SLOT_POINT and its neighbour) takes a half
# disc past the polygon's chord.
SHEET_VOLUME = (
    _area(profile_points_mm()) - math.pi * SLOT_END_RADIUS_MM**2 / 2.0
) * SHEET_THICK

# --- Drawing -------------------------------------------------------------------
PROFILE_SKETCH = "SheetProfile"
SHEET_FEATURE = "Sheet"
PROFILE_DIMENSIONS = frozenset(name for name, *_rest in SKETCH_DIMENSIONS)
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    PROFILE_SKETCH: set(PROFILE_DIMENSIONS),
    SHEET_FEATURE: {"SheetThick"},
}
# Every length and width no fit depends on is .XX (rule 3); each blade's
# depth (it decides where the blade meets its space) and the grip span are
# .XXX at the title block's band, and the stock's thickness .XXX as a
# reference.
_THREE_PLACE = frozenset(
    {"SheetThick", "GripSpan", *(blade_depth_name(t) for t in BONDED_TEETH)}
)
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    feature: {name: DEPTH_PLACES if name in _THREE_PLACE else 2 for name in names}
    for feature, names in DRAWING_DIMENSIONS.items()
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dims in DRAWING_PRECISION.values() for name, places in dims.items()
}
DRAWING_VALUES_BY_NAME: dict[str, float] = {
    name: GLOBALS[name] for name in DRAWING_PRECISION_BY_NAME
}
# Fabricated nominals sit on their printed inch grid (rule 3).
for _name, _value in DRAWING_VALUES_BY_NAME.items():
    _places = DRAWING_PRECISION_BY_NAME[_name]
    if abs(inch_grid_mm(_value, _places) - _value) > 1e-9:
        raise AssertionError(f"{_name} {_value} mm is off its .{'X' * _places} grid")

# --- Sheet words ----------------------------------------------------------------
# Each blade's depth states its function on its own line in rule 3's form: it
# clears its gear's root, named by number (rule 4). The grip span states its
# fit at the dimension (rule 26): the interference its limits take across
# T030's roots, from none at the tightest pair to SPREAD_MAX_MM. The
# thickness is the stock's, printed as a reference over SHEET STOCK
# (pn-pen-hanger, pd-platen-clip): the stock's own tolerance governs. No
# numbered note is left.
STOCK_TEXT = "SHEET STOCK"
GRIP_INTERFERENCE_IN = (
    math.floor((2.0 * SEAT_EDGE_MM[0] - GRIP_SPAN - _XXX) / INCH * 1000.0) / 1000.0,
    math.ceil(SPREAD_MAX_MM / INCH * 1000.0) / 1000.0,
)
if GRIP_INTERFERENCE_IN[0] < 0.0:
    raise AssertionError("the grip span must interfere at every limit")
GRIP_TEXT = (
    f"{GRIP_INTERFERENCE_IN[0]:.3f}-{GRIP_INTERFERENCE_IN[1]:.3f}".replace("0.", ".")
    + f" INTERFERENCE\nON {gear_number(REFERENCE_TEETH)} ROOTS"
)
REFERENCE_DIMENSIONS = frozenset({"SheetThick"})
DEPTH_SUFFIX: dict[str, str] = {
    blade_depth_name(t): f", CLEARS {gear_number(t)} ROOT" for t in BONDED_TEETH
}
# The slot's length runs to its full round's centre.
DEPTH_SUFFIX["SlotLength"] = " TO FULL R"
CALLOUTS_BELOW: dict[str, str] = {
    "GripSpan": GRIP_TEXT,
    "SheetThick": STOCK_TEXT,
}
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
