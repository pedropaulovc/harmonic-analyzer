r"""Pure-data contract for the cone tip gears' phasing comb (MHA-DT-03-TL-02).

Shop tooling, not a machine part (cad/docs/subsystem-identities.md): the
fixture MHA-DT-00 step 1 engages while LOCTITE 638 grabs, so the bonded tip
gears cure in phase with the keyed stack (owner ruling 2026-11-09 (b1) via PR
#1992, C1 keyed; single blade per gear, owner ruling 2026-11-10 via PR #1992).
Every cone gear has a tooth centred on its local +X (phase 0; the keyway runs
through T030's), so a tooth space is centred at SPACE_ANGLE = +180/N deg on
every gear: from +X toward the gear model's +Y, counter-clockwise looking
down the gear model's +Z (its Front plane's normal). One flat plate lying
parallel to the +X radial plane drops one blade into that space of T030 (the
reference, keyed) and of the bonded T024, T018, T012 (MHA-DT-03) and T006
(MHA-DT-37) at once.

Frame (the SolidWorks model). X runs along the cone axis, north (the plate's
length); Y runs radially outward, along the gears' +X (its height); Z is the
tangential direction, the gears' +Y (its thickness). Z0 is the plate's back
face, the blades' datum. The origin is the north end of the T030 blade on the
SEAT line, T030's largest tip radius: the plate's edge over T030 bears on the
tip land of T030's phase-0 tooth there. Over each gear the plate's edge
stands clear of that gear's tips (a STEP), and one blade drops from it: a
slab BLADE_WIDTH thick whose near face stands BLADE_FACE off the back face,
its tip between its gear's root and pitch circles.

Every blade is cut to the shop's own rows (drawing-guidelines.md "What the
shop holds"): its thickness at the milled-slot row, its location from the back
face and its tip depth at the milled-step row. A blade's walls are parallel
to the +X radial plane while its space is centred on SPACE_ANGLE, so the
play is worked on the real slab against each gear's four printed tooth
corners (``play_window_rad``). ``PHASE_ERROR_MM`` proves every bonded gear's
worst phase against T030 at those limits inside the booked error_budget.yaml
cone_tip_bond_clock tolerance.

Assumption: the fitter presses the comb radially, so its edge over T030
bears flat on the phase-0 tooth's tip land and the plate stays parallel to
the radial plane; it slides tangentially only as far as T030's blade lets it.
"""

from __future__ import annotations

import functools
import itertools
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


def inch_grid_mm(value_mm: float, places: int, rounding=round) -> float:
    """``value_mm`` on the printed inch grid (rule 3)."""
    return family.inch_grid_mm(value_mm, places, rounding)


def inch_text(value_mm: float, places: int) -> str:
    return family.inch_text(value_mm, places)


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


# --- Axial: each blade stands inside its gear's face --------------------------
FACE_WIDTH = family.FACE_WIDTH


def _south_face_mm(teeth: int) -> float:
    """Nominal south face of ``teeth``'s leaves from T030's south face: T030,
    one STACK_FEELER, then T024, T018, T012 and T006 face to face."""
    index = GEARS.index(teeth)
    return index * FACE_WIDTH + (STACK_FEELER if index else 0.0)


# A blade never overhangs the larger gear south of it (it would strike that
# gear's teeth), and the T006 blade never reaches past T006's north face (the
# MHA-DT-38 bushing); a blade's north end over the smaller gear beyond it
# clears that gear's tips (its tip stands over them, below).  The blades stop
# BLADE_INSET short of both faces; T030..T012 blades are BLADE_LENGTH long,
# and the T006 blade runs to the plate's north end. Every length is .XX at
# the title block's band (rule 3): the inset keeps each blade inside its
# face at that band (AXIAL_PLACEMENT_WINDOW).
BLADE_INSET = 0.030 * INCH
BLADE_LENGTH_PLACES = 2
BLADE_LENGTH = inch_grid_mm(
    FACE_WIDTH - 2.0 * BLADE_INSET, BLADE_LENGTH_PLACES, math.floor
)
# Blade south ends from the plate's south end (the T030 blade's), printed.
BLADE_START_MM: dict[int, float] = {
    teeth: inch_grid_mm(_south_face_mm(teeth), BLADE_LENGTH_PLACES) for teeth in GEARS
}
PLATE_LENGTH = BLADE_START_MM[GEARS[-1]] + BLADE_LENGTH


def _placement_window_mm(
    feeler: float, faces: tuple[float, ...], ends: tuple[float, ...]
) -> float:
    """Width of the comb shifts that keep every blade inside its face, for one
    stack (the feeler's and each face's deviation, T030 first) and one print
    (``ends``: each blade start's deviation, T006's last, then the plate
    length's)."""
    south: list[float] = []
    station = 0.0
    for index, teeth in enumerate(GEARS):
        if index:
            station += FACE_WIDTH + faces[index - 1] + (feeler if index == 1 else 0.0)
        south.append(station)
    # Comb placed with its south end BLADE_INSET north of T030's south face,
    # then shifted by s: blade g's south end at INSET + START_g + end_g + s.
    low = max(
        south[index] - (BLADE_INSET + BLADE_START_MM[teeth] + ends[index])
        for index, teeth in enumerate(GEARS)
    )
    north_face = south[-1] + FACE_WIDTH + faces[-1]
    high = north_face - (BLADE_INSET + PLATE_LENGTH + ends[-1])
    return high - low


def _placement_window_min_mm() -> float:
    face, feeler, printed = abs(family.FACE_WIDTH_BAND[1]), STACK_FEELER_BAND, _XX
    widths = []
    for signs in itertools.product((-1.0, 1.0), repeat=len(GEARS) + 3):
        faces = tuple(sign * face for sign in signs[: len(GEARS)])
        stack_feeler = signs[len(GEARS)] * feeler
        # Every print: the blade starts at either end of their .XX band
        # (together), the plate's length at either end of its own.
        start, length = signs[-2] * printed, signs[-1] * printed
        ends = (0.0, *(start for _ in GEARS[1:]), length)
        widths.append(_placement_window_mm(stack_feeler, faces, ends))
    return min(widths)


# The fitter centres the comb on the stack by eye; at the worst stack and
# print it still has this much axial freedom.
AXIAL_PLACEMENT_WINDOW_MM = _placement_window_min_mm()
if AXIAL_PLACEMENT_WINDOW_MM < 0.1:
    raise AssertionError(
        f"comb placement window {AXIAL_PLACEMENT_WINDOW_MM:.3f} mm: a blade overhangs"
    )

# --- Radial: the seat and the steps -------------------------------------------
RADIAL_PLACES = 3
# The comb seats on the tip of T030's phase-0 tooth: the seat line is T030's
# largest tip radius; a smaller tip lets the comb down by its band.
SEAT_RADIUS_MM = tip_radius_limits_mm(REFERENCE_TEETH)[1]
SEAT_DROP_MM = SEAT_RADIUS_MM - tip_radius_limits_mm(REFERENCE_TEETH)[0]
# Before the compound grabs a bonded gear may float radially by half its bond
# clearance (T024 on land 2; T018, T012 and T006's spigot on .0625).
BOND_FLOAT_MM = max(
    *(family.bond_clearance_mm(teeth)[1] / 2.0 for teeth in (24, 18, 12)),
    cluster.SPIGOT_BOND_CLEARANCE_MM[1] / 2.0,
)
# Each step (the plate's edge north of a blade) stands this far over the
# largest tip it passes over, after the seat's drop, its band and the float.
TIP_AIR = 0.010 * INCH


def _below_seat(radius_mm: float, places: int, rounding=round) -> float:
    return inch_grid_mm(SEAT_RADIUS_MM - radius_mm, places, rounding)


# The step north of each of T030..T012's blades passes over that gear's tip
# and the next, smaller one's: .XX, rounded toward the seat (never less air).
# T030's step is the seat line itself.
STEP_PLACES = 2
_STEP_BAND = printed_band_mm(STEP_PLACES, unit=UNIT)
STEP_DEPTH_MM: dict[int, float] = {
    teeth: (
        0.0
        if teeth == REFERENCE_TEETH
        else _below_seat(
            tip_radius_limits_mm(teeth)[1]
            + SEAT_DROP_MM
            + _STEP_BAND
            + BOND_FLOAT_MM
            + TIP_AIR,
            STEP_PLACES,
            math.floor,
        )
    )
    for teeth in GEARS[:-1]
}
# The plate stands this high over the seat (.XX).
PLATE_HEIGHT = 0.25 * INCH


def blade_root_depth_mm(teeth: int) -> float:
    """Where ``teeth``'s blade leaves the plate, seat line down: the step
    south of it (T030's at the seat itself), which clears this gear's tips."""
    index = GEARS.index(teeth)
    return 0.0 if index == 0 else STEP_DEPTH_MM[GEARS[index - 1]]


def _radius_limits(depth_mm: float, band_mm: float) -> tuple[float, float]:
    """(lowest, highest) radius a printed depth below the seat reaches."""
    return (
        SEAT_RADIUS_MM - SEAT_DROP_MM - depth_mm - band_mm,
        SEAT_RADIUS_MM - depth_mm + band_mm,
    )


# Each step clears the tips of the gear south of it and the next, smaller one.
for _south, _north in zip(GEARS, GEARS[1:], strict=False):
    if _south == REFERENCE_TEETH:
        continue
    _step = _radius_limits(STEP_DEPTH_MM[_south], _STEP_BAND)[0]
    for _teeth in (_south, _north):
        if _step - BOND_FLOAT_MM <= tip_radius_limits_mm(_teeth)[1]:
            raise AssertionError(f"step north of T{_south:03d} reaches T{_teeth:03d}")


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


def root_radius_max_mm(teeth: int) -> float:
    return max(profile.root_radius_max_mm for profile in _profiles(teeth))


def play_window_rad(
    teeth: int, corner: int, tip_mm: float, near_mm: float, far_mm: float
) -> tuple[float, float]:
    """(least, greatest) turn of ``teeth``'s gear (printed ``corner``) from its
    phase that keeps every point of a blade in the space centred on
    SPACE_ANGLE: the blade's tip face at ``tip_mm`` along the gear's +X, its
    walls at ``near_mm`` and ``far_mm`` along +Y. Each radius from the tip
    face's nearest corner out to the gear's tip meets the blade over one arc;
    the space must hold it."""
    radii, _gaps = _gap_table(teeth, corner)
    nearest = math.hypot(tip_mm, near_mm)
    if nearest <= radii[0]:
        raise ValueError(f"T{teeth:03d} blade bottoms on the root")
    samples = sorted(
        {nearest, *(r for r in (math.hypot(tip_mm, far_mm),) if r < radii[-1])}
        | {r for r in radii if r > nearest}
    )
    centre = space_angle_rad(teeth)
    low, high = -math.inf, math.inf
    for radius in samples:
        half = _half_space_rad(teeth, corner, radius)
        reach = min(far_mm, math.sqrt(max(0.0, radius * radius - tip_mm * tip_mm)))
        high = min(high, math.asin(near_mm / radius) + half - centre)
        low = max(low, math.asin(reach / radius) - half - centre)
    return low, high


# --- Blade: tip depth, thickness and location ---------------------------------
# Every blade carries the shop's rows: its tip depth from the seat and its
# location from the back face at the milled-step row (+/-.002), its thickness
# at the milled-slot row (+/-.001).
BLADE_PLACES = 3
BLADE_DEPTH_BAND_MM = 0.002 * INCH
BLADE_DEPTH_DEVIATIONS_MM = (-BLADE_DEPTH_BAND_MM, BLADE_DEPTH_BAND_MM)
BLADE_WIDTH_BAND_MM = 0.001 * INCH
BLADE_WIDTH_DEVIATIONS_MM = (-BLADE_WIDTH_BAND_MM, BLADE_WIDTH_BAND_MM)
BLADE_FACE_BAND_MM = 0.002 * INCH
BLADE_FACE_DEVIATIONS_MM = (-BLADE_FACE_BAND_MM, BLADE_FACE_BAND_MM)
# A blade's centre plane stands within this of its nominal from the back face.
BLADE_CENTRE_BAND_MM = BLADE_FACE_BAND_MM + BLADE_WIDTH_BAND_MM / 2.0
# The widest blade still turns its gear through this much play (at its tip).
BLADE_CLEARANCE_MM = 0.0005 * INCH
# The lowest blade tip stands this far off the largest root.
ROOT_AIR = 0.002 * INCH
# Tooth over the highest blade tip: at least this much of its addendum.
ENGAGEMENT_MIN = 0.10


def _float_mm(teeth: int) -> float:
    return 0.0 if teeth == REFERENCE_TEETH else BOND_FLOAT_MM


def blade_tip_limits_mm(teeth: int, depth_mm: float) -> tuple[float, float]:
    """(lowest, highest) blade tip along the gear's +X at the print's limits:
    the seat's drop, the depth band and the gear's float."""
    low, high = _radius_limits(depth_mm, BLADE_DEPTH_BAND_MM)
    return low - _float_mm(teeth), high + _float_mm(teeth)


def _centred_mm(teeth: int, tip_mm: float, width_mm: float) -> float:
    """The blade centre (along the gear's +Y) that centres its play on the
    phase over the four printed corners, at ``tip_mm``."""

    def balance(centre: float) -> float:
        windows = [
            play_window_rad(
                teeth, corner, tip_mm, centre - width_mm / 2.0, centre + width_mm / 2.0
            )
            for corner in range(len(_profiles(teeth)))
        ]
        return sum(low + high for low, high in windows)

    guess = tip_mm * math.tan(space_angle_rad(teeth))
    low, high = guess - 0.3, guess + 0.3
    for _ in range(48):
        middle = (low + high) / 2.0
        if balance(middle) < 0.0:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def _conditions(teeth: int, depth_mm: float, width_mm: float):
    """Every printed limit a blade meets: each tooth corner, the lowest and
    highest tip, the thinnest and thickest blade."""
    for corner in range(len(_profiles(teeth))):
        for tip in blade_tip_limits_mm(teeth, depth_mm):
            for width in (
                width_mm - BLADE_WIDTH_BAND_MM,
                width_mm + BLADE_WIDTH_BAND_MM,
            ):
                yield corner, tip, width


def _fits(teeth: int, depth_mm: float, width_mm: float, centre_mm: float) -> bool:
    """The thickest blade turns its gear through BLADE_CLEARANCE at its tip,
    on every corner at both tip limits."""
    for corner, tip, width in _conditions(teeth, depth_mm, width_mm):
        if width < width_mm:
            continue
        low, high = play_window_rad(
            teeth, corner, tip, centre_mm - width / 2.0, centre_mm + width / 2.0
        )
        if (high - low) * math.hypot(tip, centre_mm) < BLADE_CLEARANCE_MM:
            return False
    return True


def _space_chord_mm(teeth: int, radius_mm: float) -> float:
    """The narrowest space (thickest tooth) of the four corners at a radius."""
    return min(
        2.0 * radius_mm * math.sin(_half_space_rad(teeth, corner, radius_mm))
        for corner in range(len(_profiles(teeth)))
    )


def _design_blade(teeth: int) -> tuple[float, float, float]:
    """(tip depth, thickness, centre) of ``teeth``'s blade. The tip: the
    shallowest .XXX depth whose highest tip face centre stands on or under the
    pitch circle. The thickness: the narrowest space at the lowest tip less
    the clearance and its band, on the .001 grid, thinned until the thickest
    blade clears the slab-on-space walls. The centre: the play centred on the
    phase."""
    angle = space_angle_rad(teeth)
    pitch = pitch_radius_mm(teeth)
    depth = _below_seat(pitch * math.cos(angle), BLADE_PLACES, math.floor)
    while True:
        lowest, highest = blade_tip_limits_mm(teeth, depth)
        chord = _space_chord_mm(teeth, lowest / math.cos(angle))
        width = inch_grid_mm(
            chord - BLADE_CLEARANCE_MM - BLADE_WIDTH_BAND_MM, BLADE_PLACES, math.floor
        )
        while True:
            centre = _centred_mm(teeth, SEAT_RADIUS_MM - depth, width)
            if _fits(teeth, depth, width, centre):
                break
            width -= 0.001 * INCH
            if width <= 0.010 * INCH:
                raise AssertionError(f"T{teeth:03d}: no blade fits its tooth space")
        if math.hypot(highest, centre) <= pitch:
            return depth, width, centre
        depth += 0.001 * INCH


_DESIGN = {teeth: _design_blade(teeth) for teeth in GEARS}
# Printed, seat line down (positive): each blade tip.
BLADE_TIP_DEPTH_MM: dict[int, float] = {t: d for t, (d, _w, _c) in _DESIGN.items()}
BLADE_WIDTH_MM: dict[int, float] = {t: w for t, (_d, w, _c) in _DESIGN.items()}
# The space centre's offset (along the gear's +Y) at each blade's working
# radius: where the blade's play is centred on the phase.
BLADE_CENTRE_MM: dict[int, float] = {t: c for t, (_d, _w, c) in _DESIGN.items()}
WORKING_RADIUS_MM: dict[int, float] = {
    t: BLADE_CENTRE_MM[t] / math.sin(space_angle_rad(t)) for t in GEARS
}
BLADE_TIP_LIMITS_MM = {
    teeth: blade_tip_limits_mm(teeth, BLADE_TIP_DEPTH_MM[teeth]) for teeth in GEARS
}
for _teeth in GEARS:
    _low, _high = BLADE_TIP_LIMITS_MM[_teeth]
    _near = (
        BLADE_CENTRE_MM[_teeth] - (BLADE_WIDTH_MM[_teeth] + BLADE_WIDTH_BAND_MM) / 2.0
    )
    if math.hypot(_low, _near) < root_radius_max_mm(_teeth) + ROOT_AIR:
        raise AssertionError(f"T{_teeth:03d} blade bottoms on its root")
    if math.hypot(_high, BLADE_CENTRE_MM[_teeth]) > pitch_radius_mm(_teeth) + 1e-6:
        raise AssertionError(f"T{_teeth:03d} blade tip stands over its pitch circle")
    if (
        math.hypot(_high, BLADE_CENTRE_MM[_teeth]) + ENGAGEMENT_MIN
        > tip_radius_limits_mm(_teeth)[0]
    ):
        raise AssertionError(f"T{_teeth:03d} blade catches under {ENGAGEMENT_MIN} mm")


# --- The comb's tangential play on T030 and each gear's phase -----------------
def _shift_limits_mm(
    teeth: int, corner: int, tip: float, width: float
) -> tuple[float, float]:
    """(least, greatest) shift of ``teeth``'s blade from its centre (along +Y)
    that still holds the gear at its phase: the comb's slide on T030."""
    centre = BLADE_CENTRE_MM[teeth]

    def window(shift: float) -> tuple[float, float]:
        return play_window_rad(
            teeth,
            corner,
            tip,
            centre + shift - width / 2.0,
            centre + shift + width / 2.0,
        )

    def edge(side: int) -> float:
        # Both ends of the window rise with the shift. side 0: where its top
        # meets the phase (the least shift); side 1: where its bottom does
        # (the greatest).
        low, high = -0.3, 0.3
        for _ in range(48):
            middle = (low + high) / 2.0
            if window(middle)[1 - side] < 0.0:
                low = middle
            else:
                high = middle
        return (low + high) / 2.0

    return edge(0), edge(1)


def _comb_slide_mm() -> tuple[float, float]:
    """(least, greatest) shift of the comb on T030 over every printed limit."""
    limits = [
        _shift_limits_mm(REFERENCE_TEETH, corner, tip, width)
        for corner, tip, width in _conditions(
            REFERENCE_TEETH,
            BLADE_TIP_DEPTH_MM[REFERENCE_TEETH],
            BLADE_WIDTH_MM[REFERENCE_TEETH],
        )
    ]
    return min(low for low, _ in limits), max(high for _, high in limits)


COMB_SLIDE_MM = _comb_slide_mm()

# --- The plate's faces: T030's blade sets the frame --------------------------
# The plate's edge over T030 covers the whole tip land of the phase-0 tooth
# (half its chord either side of +X) at the comb's farthest slide, with this
# much to spare.
SEAT_COVER = 0.002 * INCH
BLADE_FACE_PLACES = 3
SEAT_LAND_HALF_MM = max(
    profile.blank_radius_mm
    * math.sin(
        space_angle_rad(REFERENCE_TEETH)
        - profile._gap_angle_at_radius(profile.blank_radius_mm)
    )
    for profile in _profiles(REFERENCE_TEETH)
)
_REFERENCE_FACE_MM = inch_grid_mm(
    BLADE_CENTRE_MM[REFERENCE_TEETH]
    - BLADE_WIDTH_MM[REFERENCE_TEETH] / 2.0
    + SEAT_LAND_HALF_MM
    + COMB_SLIDE_MM[1]
    + BLADE_FACE_BAND_MM
    + SEAT_COVER,
    BLADE_FACE_PLACES,
    math.ceil,
)
# The back face along the gears' +Y with T030's blade at its centre.
BACK_FACE_MM = (
    BLADE_CENTRE_MM[REFERENCE_TEETH]
    - BLADE_WIDTH_MM[REFERENCE_TEETH] / 2.0
    - _REFERENCE_FACE_MM
)
# Each blade's near face from the back face, on the .001 grid; its centre
# then stands BLADE_OFFSET from its ideal (T030's on it).
BLADE_FACE_MM: dict[int, float] = {
    teeth: (
        _REFERENCE_FACE_MM
        if teeth == REFERENCE_TEETH
        else inch_grid_mm(
            BLADE_CENTRE_MM[teeth] - BLADE_WIDTH_MM[teeth] / 2.0 - BACK_FACE_MM,
            BLADE_FACE_PLACES,
        )
    )
    for teeth in GEARS
}
BLADE_OFFSET_MM: dict[int, float] = {
    teeth: BACK_FACE_MM
    + BLADE_FACE_MM[teeth]
    + BLADE_WIDTH_MM[teeth] / 2.0
    - BLADE_CENTRE_MM[teeth]
    for teeth in GEARS
}
if BACK_FACE_MM + COMB_SLIDE_MM[1] + BLADE_FACE_BAND_MM > -SEAT_LAND_HALF_MM:
    raise AssertionError("the comb's edge leaves T030's tip land")
# Either side of a blade the plate is cut away down its length: at least
# this much on the thinnest side at the print's worst.
RELIEF_MIN = 0.005 * INCH
THICKNESS_PLACES = 2
THICKNESS = inch_grid_mm(
    max(BLADE_FACE_MM[t] + BLADE_WIDTH_MM[t] for t in GEARS)
    + BLADE_FACE_BAND_MM
    + BLADE_WIDTH_BAND_MM
    + _XX
    + RELIEF_MIN,
    THICKNESS_PLACES,
    math.ceil,
)
for _teeth in GEARS:
    if BLADE_FACE_MM[_teeth] - BLADE_FACE_BAND_MM < RELIEF_MIN:
        raise AssertionError(f"T{_teeth:03d} blade's near face leaves no relief")


def phase_error_mm(teeth: int) -> float:
    """A bonded gear's worst phase against T030, pitch arc: the comb slides
    on T030 as far as T030's blade lets it, the two blades' centres stand
    apart by both centre bands and their nominal offsets, and the gear turns
    to either end of its own blade's play at every printed limit."""
    apart = 2.0 * BLADE_CENTRE_BAND_MM
    offset = BLADE_OFFSET_MM[teeth] - BLADE_OFFSET_MM[REFERENCE_TEETH]
    up = COMB_SLIDE_MM[1] + apart + offset
    down = COMB_SLIDE_MM[0] - apart + offset
    centre = BLADE_CENTRE_MM[teeth]
    worst = 0.0
    for corner, tip, width in _conditions(
        teeth, BLADE_TIP_DEPTH_MM[teeth], BLADE_WIDTH_MM[teeth]
    ):
        high = play_window_rad(
            teeth, corner, tip, centre + up - width / 2.0, centre + up + width / 2.0
        )[1]
        low = play_window_rad(
            teeth, corner, tip, centre + down - width / 2.0, centre + down + width / 2.0
        )[0]
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

# The thinnest blade anywhere: printed on the sheet as a plain fact.
BLADE_MIN_MM = min(BLADE_WIDTH_MM.values()) - BLADE_WIDTH_BAND_MM
BLADE_MIN_IN = math.floor(BLADE_MIN_MM / INCH * 1000.0 + 1e-9) / 1000.0

# --- Pose in the shop kit (MHA-DT-03-TL-00) -----------------------------------
# The comb's model origin (mm) in the kit frame, in the index plate's front
# plane under its rim, clear of it by about a balloon's diameter; the kit's
# build places it here and its sheet shows it there under item 1.
KIT_POSITION_MM = (-11.0, -70.0, 0.0)

# --- Model --------------------------------------------------------------------
# Each relief cut runs this far past the plate's faces, the blade's south end
# and its tip.
RELIEF_RUNOUT = 0.010 * INCH


def blade_width_name(teeth: int) -> str:
    return f"BladeWidth{gear_tag(teeth)}"


def blade_face_name(teeth: int) -> str:
    return f"BladeFace{gear_tag(teeth)}"


def blade_tip_name(teeth: int) -> str:
    return f"BladeTip{gear_tag(teeth)}"


# Model globals: name -> value (mm); the build sets each and drives from it.
GLOBALS: dict[str, float] = {
    "PlateLength": PLATE_LENGTH,
    "PlateHeight": PLATE_HEIGHT,
    "PlateThick": THICKNESS,
    "BladeLength": BLADE_LENGTH,
    "ReliefRunout": RELIEF_RUNOUT,
    **{f"Start{gear_tag(t)}": BLADE_START_MM[t] for t in BONDED_TEETH},
    **{blade_tip_name(t): BLADE_TIP_DEPTH_MM[t] for t in GEARS},
    **{f"Step{gear_tag(t)}": STEP_DEPTH_MM[t] for t in BONDED_TEETH[:-1]},
    **{blade_width_name(t): BLADE_WIDTH_MM[t] for t in GEARS},
    **{blade_face_name(t): BLADE_FACE_MM[t] for t in GEARS},
}

# Profile vertices (model mm: x north along the plate, y outward), the
# closed chain the plate sketch draws: the south end up from the T030 blade
# tip, then each blade's full-thickness stock and the step north of it, then
# the north end and the top.
_SOUTH_X = -BLADE_LENGTH


def blade_x_mm(teeth: int) -> tuple[float, float]:
    """(south, north) model x of ``teeth``'s blade."""
    south = _SOUTH_X + BLADE_START_MM[teeth]
    north = _SOUTH_X + PLATE_LENGTH if teeth == GEARS[-1] else south + BLADE_LENGTH
    return south, north


def profile_points_mm() -> list[tuple[float, float]]:
    points = [(_SOUTH_X, PLATE_HEIGHT)]
    for index, teeth in enumerate(GEARS):
        south, north = blade_x_mm(teeth)
        tip = -BLADE_TIP_DEPTH_MM[teeth]
        if index:
            points.append(
                (south, -STEP_DEPTH_MM[GEARS[index - 1]] if index > 1 else 0.0)
            )
        points.append((south, tip))
        points.append((north, tip))
        if teeth != GEARS[-1]:
            points.append((north, -STEP_DEPTH_MM[teeth]))
    points.append((_SOUTH_X + PLATE_LENGTH, PLATE_HEIGHT))
    return points


if profile_points_mm()[3] != (0.0, 0.0):
    raise AssertionError("the model origin is the T030 blade's north end on the seat")
# The relief cuts run RELIEF_RUNOUT twice past a blade's south end, where
# only air stands under its root: the gap to the blade south of it.
for _south, _north in zip(GEARS, GEARS[1:], strict=False):
    if blade_x_mm(_north)[0] - blade_x_mm(_south)[1] <= 2.0 * RELIEF_RUNOUT:
        raise AssertionError(f"T{_north:03d} relief reaches the T{_south:03d} blade")


def relief_outline_mm(teeth: int) -> list[tuple[float, float]]:
    """(x, z) of ``teeth``'s relief: one closed rectilinear outline round its
    blade, open at the blade's north end. From the blade's near face at the
    north end (the anchor: its x and BladeFace from the back face), south past
    the blade's south end, across its width, north along its far face, out
    past the plate's front face, south, back past the back face and north to
    the start. It is cut from the blade's root down past its tip."""
    south, north = blade_x_mm(teeth)
    near = BLADE_FACE_MM[teeth]
    far = near + BLADE_WIDTH_MM[teeth]
    return [
        (north, near),
        (south - RELIEF_RUNOUT, near),
        (south - RELIEF_RUNOUT, far),
        (north, far),
        (north, THICKNESS + RELIEF_RUNOUT),
        (south - 2.0 * RELIEF_RUNOUT, THICKNESS + RELIEF_RUNOUT),
        (south - 2.0 * RELIEF_RUNOUT, -RELIEF_RUNOUT),
        (north, -RELIEF_RUNOUT),
    ]


def _area(points: list[tuple[float, float]]) -> float:
    return 0.5 * abs(
        sum(
            x0 * y1 - x1 * y0
            for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1], strict=True)
        )
    )


PLATE_VOLUME = _area(profile_points_mm()) * THICKNESS
# Each relief removes the plate beside its blade, root to tip, along the
# blade's length.
RELIEF_VOLUME_MM3 = {
    teeth: (
        (blade_x_mm(teeth)[1] - blade_x_mm(teeth)[0])
        * (BLADE_TIP_DEPTH_MM[teeth] - blade_root_depth_mm(teeth))
        * (THICKNESS - BLADE_WIDTH_MM[teeth])
    )
    for teeth in GEARS
}
FINISHED_VOLUME = PLATE_VOLUME - sum(RELIEF_VOLUME_MM3.values())

# --- Drawing -------------------------------------------------------------------
PROFILE_SKETCH = "PlateProfile"
PLATE_FEATURE = "Plate"


def blade_sketch(teeth: int) -> str:
    return f"BladeProfile{gear_tag(teeth)}"


def relief_feature(teeth: int) -> str:
    return f"BladeRelief{gear_tag(teeth)}"


def root_plane(teeth: int) -> str | None:
    """The reference plane at ``teeth``'s blade root, or None on the Top
    plane (the seat)."""
    return None if blade_root_depth_mm(teeth) == 0.0 else f"BladeRoot{gear_tag(teeth)}"


PROFILE_DIMENSIONS = frozenset(
    {
        "PlateLength",
        "PlateHeight",
        "BladeLength",
        *(f"Start{gear_tag(t)}" for t in BONDED_TEETH),
        *(blade_tip_name(t) for t in GEARS),
        *(f"Step{gear_tag(t)}" for t in BONDED_TEETH[:-1]),
    }
)
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    PROFILE_SKETCH: set(PROFILE_DIMENSIONS),
    PLATE_FEATURE: {"PlateThick"},
    **{blade_sketch(t): {blade_width_name(t), blade_face_name(t)} for t in GEARS},
}
# Every length and height no fit depends on is .XX (rule 3).
_TWO_PLACE = frozenset(
    {
        "PlateLength",
        "PlateHeight",
        "PlateThick",
        "BladeLength",
        *(f"Start{gear_tag(t)}" for t in BONDED_TEETH),
        *(f"Step{gear_tag(t)}" for t in BONDED_TEETH[:-1]),
    }
)
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    feature: {name: 2 if name in _TWO_PLACE else 3 for name in names}
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
# The bands tighter than the title block, each at its shop row and set on the
# model's own dimension: (feature, dimension) -> (lower, upper) deviation, mm.
MODEL_BANDS_MM: dict[tuple[str, str], tuple[float, float]] = {
    **{(PROFILE_SKETCH, blade_tip_name(t)): BLADE_DEPTH_DEVIATIONS_MM for t in GEARS},
    **{
        (blade_sketch(t), blade_width_name(t)): BLADE_WIDTH_DEVIATIONS_MM for t in GEARS
    },
    **{(blade_sketch(t), blade_face_name(t)): BLADE_FACE_DEVIATIONS_MM for t in GEARS},
}

# --- Sheet words ----------------------------------------------------------------
# Every banded dimension serves one gear's tooth space. Each blade names its
# gear once, at its thickness (rule 4); its location and tip depth point at
# note 1, which ties the whole blade to the gear named at its thickness.
# Words only, no narration (rule 7).
BLADE_NOTE_NUMBER = 1
BLADE_NOTE_FLAG = f"SEE NOTE {BLADE_NOTE_NUMBER}"
SHEET_NOTES = "\n".join(
    (
        f"{BLADE_NOTE_NUMBER}. EACH BLADE: CLEARANCE FIT IN ONE TOOTH SPACE OF THE GEAR",
        "   NAMED AT ITS THICKNESS, ITS TIP BETWEEN THAT GEAR'S ROOT AND",
        "   PITCH CIRCLES.",
    )
)
if len(SHEET_NOTES.splitlines()) > 4:
    raise AssertionError("at most four note lines")
# The thin blades print as a plain fact (rule 20).
BLADE_WALL_TEXT = f"BLADE WALL {inch_text(BLADE_MIN_IN * INCH, 3)} MIN"
CALLOUTS_BELOW: dict[str, str] = {
    **{blade_width_name(t): f"{gear_number(t)}\n{BLADE_NOTE_FLAG}" for t in GEARS},
    **{blade_face_name(t): BLADE_NOTE_FLAG for t in GEARS},
    **{blade_tip_name(t): BLADE_NOTE_FLAG for t in GEARS},
    "PlateThick": BLADE_WALL_TEXT,
}
# The four equal blade lengths print once.
CALLOUTS_ABOVE: dict[str, str] = {"BladeLength": f"{len(GEARS) - 1}X"}
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
