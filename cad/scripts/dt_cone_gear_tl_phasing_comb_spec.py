r"""Pure-data contract for the cone tip gears' phasing comb (MHA-DT-03-TL-02).

Shop tooling, not a machine part (cad/docs/subsystem-identities.md): the
fixture MHA-DT-00 step 1 engages while LOCTITE 638 grabs, so the bonded tip
gears cure in phase with the keyed stack (owner ruling 2026-11-09 (b1) via PR
#1992, C1 keyed). Every cone gear has a tooth centred on its local +X
(phase 0; the keyway runs through T030's), so the forks of one flat plate
lying in that radial plane straddle T030's tooth over the key and the
phase-0 tooth of T024, T018, T012 (MHA-DT-03) and T006 (MHA-DT-37) at once.

Frame (the SolidWorks model). X runs along the cone axis, north (the plate's
length); Y runs radially outward (its height); Z is the tangential direction
(its thickness, the plate symmetric about Z0). The origin is the north end of
the T030 fork on the SEAT line: T030's fork slot bottom, which bears on the
tip of T030's phase-0 tooth and is the sheet's radial origin, and the step
north of that fork (both at Y0). Each fork is the plate's edge stepped down to
a FORK TIP below its gear's tip circle and above its pitch circle, split by a
slot that straddles the tooth; its two tines enter the neighbouring tooth
spaces. Between forks the edge stands clear of the gears' tips.

Every slot and its location are cut to the shop's own rows (drawing-guidelines.md
"What the shop holds"): the width at the milled-slot row, its least width
clearing the thickest tooth its gear prints, and the four bonded slots' centre
planes within the milled-step location row of T030's. ``PHASE_ERROR_MM``
proves every bonded gear's worst phase against T030 at those limits inside the
booked error_budget.yaml cone_tip_bond_clock tolerance.

Assumption: the fitter presses the comb radially, so the T030 slot bottom bears
flat on the phase-0 tooth's tip land and the plate stays in the radial plane.
The tip land holds no tilt about that tooth by geometry.
"""

from __future__ import annotations

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
    """The drawing number the comb's fork serves."""
    if teeth == 6:
        return _TIP_GEAR_NUMBER
    return family.configuration_number(_FAMILY_NUMBER, teeth)


def gear_tag(teeth: int) -> str:
    """The name a fork carries in the model: ``T030``."""
    return f"T{teeth:03d}"


# --- The title block's bands (inch sheet) -------------------------------------
_XXX = printed_band_mm(3, unit=UNIT)


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


# --- Axial: each fork stands inside its gear's face ---------------------------
FACE_WIDTH = family.FACE_WIDTH


def _south_face_mm(teeth: int) -> float:
    """Nominal south face of ``teeth``'s leaves from T030's south face: T030,
    one STACK_FEELER, then T024, T018, T012 and T006 face to face."""
    index = GEARS.index(teeth)
    return index * FACE_WIDTH + (STACK_FEELER if index else 0.0)


# A fork never overhangs the larger gear south of it (its tines would strike
# that gear's teeth), and the T006 fork never reaches past T006's north face
# (the MHA-DT-38 bushing); a fork's north end over the smaller gear beyond it
# clears that gear's tips (its fork tip stands over them, below).  The forks
# stop FINGER_INSET short of both faces; T030..T012 forks are FINGER_LENGTH
# long, and the T006 fork runs to the plate's north end.
FINGER_INSET = 0.020 * INCH
FINGER_PLACES = 3
FINGER_LENGTH = inch_grid_mm(FACE_WIDTH - 2.0 * FINGER_INSET, FINGER_PLACES, math.floor)
# Fork south ends from the plate's south end (the T030 fork's), printed.
FINGER_START_MM: dict[int, float] = {
    teeth: inch_grid_mm(_south_face_mm(teeth), FINGER_PLACES) for teeth in GEARS
}
PLATE_LENGTH = FINGER_START_MM[GEARS[-1]] + FINGER_LENGTH


def _placement_window_mm(
    feeler: float, faces: tuple[float, ...], ends: tuple[float, ...]
) -> float:
    """Width of the comb shifts that keep every fork inside its face, for one
    stack (the feeler's and each face's deviation, T030 first) and one print
    (``ends``: each fork start's deviation, T006's last, then the plate
    length's)."""
    south: list[float] = []
    station = 0.0
    for index, teeth in enumerate(GEARS):
        if index:
            station += FACE_WIDTH + faces[index - 1] + (feeler if index == 1 else 0.0)
        south.append(station)
    # Comb placed with its south end FINGER_INSET north of T030's south face,
    # then shifted by s: fork g's south end at INSET + START_g + end_g + s.
    low = max(
        south[index] - (FINGER_INSET + FINGER_START_MM[teeth] + ends[index])
        for index, teeth in enumerate(GEARS)
    )
    north_face = south[-1] + FACE_WIDTH + faces[-1]
    high = north_face - (FINGER_INSET + PLATE_LENGTH + ends[-1])
    return high - low


def _placement_window_min_mm() -> float:
    face, feeler, printed = abs(family.FACE_WIDTH_BAND[1]), STACK_FEELER_BAND, _XXX
    widths = []
    for signs in itertools.product((-1.0, 1.0), repeat=len(GEARS) + 1):
        faces = tuple(sign * face for sign in signs[: len(GEARS)])
        stack_feeler = signs[-1] * feeler
        # The print's worst: fork starts early (south ends nearer the larger
        # gear), the plate long (T006's north end nearer the bushing).
        ends = (0.0, *(-printed for _ in GEARS[1:]), printed)
        widths.append(_placement_window_mm(stack_feeler, faces, ends))
    return min(widths)


# The fitter centres the comb on the stack by eye; at the worst stack and
# print it still has this much axial freedom.
AXIAL_PLACEMENT_WINDOW_MM = _placement_window_min_mm()
if AXIAL_PLACEMENT_WINDOW_MM < 0.1:
    raise AssertionError(
        f"comb placement window {AXIAL_PLACEMENT_WINDOW_MM:.3f} mm: a fork overhangs"
    )

# --- Radial: the seat, the steps and the fork tips ---------------------------
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
# Each step (the plate's edge north of a fork) stands this far over the
# largest tip it passes over, after the seat's drop, its band and the float.
TIP_AIR = 0.010 * INCH
# A fork tip stands this far over its gear's pitch circle (nominal).
FORK_TIP_RISE = 0.007 * INCH
# Tooth inside the slot at the shallowest fork: the forks catch the tooth
# over at least this much of its addendum.
ENGAGEMENT_MIN = 0.10


def _below_seat(radius_mm: float, places: int, rounding=round) -> float:
    return inch_grid_mm(SEAT_RADIUS_MM - radius_mm, places, rounding)


# Printed, seat line down (positive): each fork tip.
FORK_TIP_DEPTH_MM: dict[int, float] = {
    teeth: _below_seat(pitch_radius_mm(teeth) + FORK_TIP_RISE, RADIAL_PLACES)
    for teeth in GEARS
}
# The step north of each of T030..T012's forks passes over that gear's tip
# (and the next, smaller one's): .XX, rounded toward the seat (never less
# air). T030's step is the seat line itself. Every slot runs from under its
# fork tip up to the seat line, so no slot has a bottom of its own to print.
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


def _radius_limits(depth_mm: float, band_mm: float) -> tuple[float, float]:
    """(lowest, highest) radius a printed depth below the seat reaches."""
    return (
        SEAT_RADIUS_MM - SEAT_DROP_MM - depth_mm - band_mm,
        SEAT_RADIUS_MM - depth_mm + band_mm,
    )


# The fork tips carry the shop's milled-step row (+/-.002) from the seat: the
# tooth tapers outward, so where a fork tip stands sets the chord its slot
# meets, and the title block's .XXX band would let a slot cleared for the
# thickest tooth at the lowest tip turn the thinnest at the highest by over
# the equal-share phasing allowance.
FORK_DEPTH_BAND_MM = 0.002 * INCH
FORK_DEPTH_DEVIATIONS_MM = (-FORK_DEPTH_BAND_MM, FORK_DEPTH_BAND_MM)
FORK_TIP_RADIUS_LIMITS_MM = {
    teeth: _radius_limits(FORK_TIP_DEPTH_MM[teeth], FORK_DEPTH_BAND_MM)
    for teeth in GEARS
}
for _teeth in GEARS:
    _low, _high = FORK_TIP_RADIUS_LIMITS_MM[_teeth]
    if _low <= pitch_radius_mm(_teeth):
        raise AssertionError(f"T{_teeth:03d} fork tip reaches its pitch circle")
    if _high > tip_radius_limits_mm(_teeth)[0] - ENGAGEMENT_MIN:
        raise AssertionError(
            f"T{_teeth:03d} fork catches under {ENGAGEMENT_MIN} mm of tooth"
        )
    # A bonded gear's slot runs up to the seat line, far over its tip.
    if _teeth != REFERENCE_TEETH and (
        SEAT_RADIUS_MM - SEAT_DROP_MM - BOND_FLOAT_MM <= tip_radius_limits_mm(_teeth)[1]
    ):
        raise AssertionError(f"T{_teeth:03d} slot top reaches its tooth tip")
# Each step clears the tips of the gear south of it and the next, smaller one.
for _south, _north in zip(GEARS, GEARS[1:]):
    if _south == REFERENCE_TEETH:
        continue
    _step = _radius_limits(STEP_DEPTH_MM[_south], _STEP_BAND)[0]
    for _teeth in (_south, _north):
        if _step - BOND_FLOAT_MM <= tip_radius_limits_mm(_teeth)[1]:
            raise AssertionError(f"step north of T{_south:03d} reaches T{_teeth:03d}")


# --- Tooth geometry at a radius (the family's corner profiles) ---------------
def _tooth_half_angle_rad(profile, radius_mm: float) -> float:
    """Half the tooth's angle at ``radius_mm`` (tooth centred on +X)."""
    return profile.angular_pitch_rad / 2.0 - profile._gap_angle_at_radius(radius_mm)


def _profiles(teeth: int):
    return family.manufacturing_corner_profiles(teeth)


def _radii(low: float, high: float, samples: int = 64) -> list[float]:
    return [low + (high - low) * index / samples for index in range(samples + 1)]


def tooth_chord_limits_mm(teeth: int, radius_mm: float) -> tuple[float, float]:
    """(thinnest, thickest) chord of ``teeth``'s tooth at ``radius_mm`` over the
    four printed corners."""
    chords = [
        2.0 * radius_mm * math.sin(_tooth_half_angle_rad(profile, radius_mm))
        for profile in _profiles(teeth)
    ]
    return min(chords), max(chords)


# --- Slot: milled to the shop's slot row --------------------------------------
# Each slot width carries the milled-slot row (+/-.001, drawing-guidelines.md
# "What the shop holds"), so no matched fit is needed; its least width clears
# the thickest tooth its gear prints, at the lowest fork tip, by
# SLOT_MIN_CLEARANCE.
SLOT_PLACES = 3
SLOT_BAND_MM = 0.001 * INCH
SLOT_DEVIATIONS_MM = (-SLOT_BAND_MM, SLOT_BAND_MM)
SLOT_MIN_CLEARANCE_MM = 0.0005 * INCH


def thickest_tooth_mm(teeth: int) -> float:
    """The thickest chord ``teeth``'s tooth prints at a fork-tip radius the
    print allows (the tooth tapers outward, so a slot's walls see it there)."""
    low, high = FORK_TIP_RADIUS_LIMITS_MM[teeth]
    return max(
        2.0 * radius * math.sin(_tooth_half_angle_rad(profile, radius))
        for profile in _profiles(teeth)
        for radius in _radii(low, min(high, profile.blank_radius_mm), 8)
    )


SLOT_WIDTH_MM: dict[int, float] = {
    teeth: inch_grid_mm(
        thickest_tooth_mm(teeth) + SLOT_BAND_MM + SLOT_MIN_CLEARANCE_MM,
        SLOT_PLACES,
        math.ceil,
    )
    for teeth in GEARS
}
SLOT_WIDTH_MAX_MM = {
    teeth: width + SLOT_BAND_MM for teeth, width in SLOT_WIDTH_MM.items()
}
for _teeth, _width in SLOT_WIDTH_MM.items():
    if _width - SLOT_BAND_MM < thickest_tooth_mm(_teeth) + SLOT_MIN_CLEARANCE_MM - 1e-9:
        raise AssertionError(f"T{_teeth:03d} slot binds on its thickest tooth")
# Every slot's near wall is located from the plate's back face (the model's
# Z0, the Front plane) by one common distance, SLOT_FACE, held to the shop's
# milled-step location row (+/-.002): the slots stand in line, so the gears
# phase together. A slot's centre plane then lies within SLOT_CENTRE_BAND of
# its nominal.
SLOT_FACE_BAND_MM = 0.002 * INCH
SLOT_FACE_DEVIATIONS_MM = (-SLOT_FACE_BAND_MM, SLOT_FACE_BAND_MM)
SLOT_CENTRE_BAND_MM = SLOT_FACE_BAND_MM + SLOT_BAND_MM / 2.0


def _turn_in_slot_rad(profile, radius_mm: float, width_mm: float) -> float:
    """How far a tooth of ``profile`` turns in a ``width_mm`` slot whose tip
    is at ``radius_mm`` before a corner touches a wall (the tooth tapers
    outward, so the fork tip's corner touches first)."""
    tip = profile.blank_radius_mm
    return min(
        math.asin(min(1.0, width_mm / (2.0 * radius)))
        - _tooth_half_angle_rad(profile, radius)
        for radius in _radii(radius_mm, tip)
    )


def fork_play_rad(teeth: int) -> float:
    """The largest turn of ``teeth``'s tooth in its slot: the widest slot the
    band allows on every printed corner at every fork-tip radius."""
    low, high = FORK_TIP_RADIUS_LIMITS_MM[teeth]
    return max(
        _turn_in_slot_rad(profile, radius, SLOT_WIDTH_MAX_MM[teeth])
        for profile in _profiles(teeth)
        for radius in _radii(low, min(high, profile.blank_radius_mm), 8)
    )


FORK_PLAY_RAD = {teeth: fork_play_rad(teeth) for teeth in GEARS}
BOND_CLOCK_TOLERANCE_MM = float(
    _config._doc("error_budget")["critical_features"]["cone_tip_bond_clock"][
        "tolerance"
    ]
)


def phase_error_mm(teeth: int) -> float:
    """A bonded gear's worst phase against T030, pitch arc: its own fork's
    play, T030's fork's (the comb turns with it), and the two slots' centre
    planes standing apart: each by its centre band, and by half the two
    nominal widths' difference (the near walls are in line)."""
    pitch = pitch_radius_mm(teeth)
    fork_low = FORK_TIP_RADIUS_LIMITS_MM[teeth][0]
    reference_low = FORK_TIP_RADIUS_LIMITS_MM[REFERENCE_TEETH][0]
    play = (FORK_PLAY_RAD[teeth] + FORK_PLAY_RAD[REFERENCE_TEETH]) * pitch
    stagger = abs(SLOT_WIDTH_MM[teeth] - SLOT_WIDTH_MM[REFERENCE_TEETH]) / 2.0
    offset = (SLOT_CENTRE_BAND_MM + stagger) * pitch / fork_low
    offset += SLOT_CENTRE_BAND_MM * pitch / reference_low
    return play + offset


PHASE_ERROR_MM = {teeth: phase_error_mm(teeth) for teeth in BONDED_TEETH}
for _teeth, _error in PHASE_ERROR_MM.items():
    if _error > BOND_CLOCK_TOLERANCE_MM:
        raise AssertionError(
            f"T{_teeth:03d} phases to +/-{_error:.4f} mm pitch arc, over the "
            f"booked {BOND_CLOCK_TOLERANCE_MM} mm"
        )

# --- Plate thickness: each tine stays inside its neighbouring tooth space ----
# The plate is milled to thickness at the shop's row (+/-.001): the tines
# must fit the neighbouring tooth spaces with the slot between them, which the
# title block's .XX band cannot hold. Nominal on the .XX grid, printed .XXX.
THICKNESS_PLACES = 3
THICKNESS_BAND_MM = 0.001 * INCH
THICKNESS_DEVIATIONS_MM = (-THICKNESS_BAND_MM, THICKNESS_BAND_MM)
TINE_AIR = 0.05


def _neighbour_reach_mm(teeth: int) -> float:
    """The smallest tangential distance from the slot's centre plane to the
    neighbouring tooth (largest corner, turned by the fork's play toward the
    tine) over the radii a tine spans: the tine's outer face must stay
    nearer."""
    pitch_angle = 2.0 * math.pi / teeth
    low = FORK_TIP_RADIUS_LIMITS_MM[teeth][0]
    reach = math.inf
    for profile in _profiles(teeth):
        root = profile.root_radius_max_mm
        for radius in _radii(root + 1e-6, profile.blank_radius_mm, 256):
            angle = (
                pitch_angle
                - _tooth_half_angle_rad(profile, radius)
                - FORK_PLAY_RAD[teeth]
            )
            if radius * math.cos(angle) >= low:
                reach = min(reach, radius * math.sin(angle))
    return reach


NEIGHBOUR_REACH_MM = {teeth: _neighbour_reach_mm(teeth) for teeth in GEARS}
# The plate's faces stand off each slot's centre plane by its centre's place
# (SLOT_FACE plus half the width) and the rest of the thickness; the farther
# face must stay inside the neighbouring tooth space. With SLOT_FACE half the
# rest of the thickness, the farther face's worst is half the thickness plus
# the thickness band and the centre band.
THICKNESS = inch_grid_mm(
    2.0 * (min(NEIGHBOUR_REACH_MM.values()) - TINE_AIR - SLOT_CENTRE_BAND_MM)
    - 2.0 * THICKNESS_BAND_MM,
    2,
    math.floor,
)
SLOT_FACE_PLACES = 3
SLOT_FACE_MM = inch_grid_mm(
    (THICKNESS - max(SLOT_WIDTH_MM.values())) / 2.0, SLOT_FACE_PLACES, math.floor
)


def face_reach_mm(teeth: int) -> float:
    """The farther plate face's worst distance from ``teeth``'s slot centre
    plane (thickest plate, centre farthest from that face)."""
    width = SLOT_WIDTH_MM[teeth]
    centre = SLOT_FACE_MM + width / 2.0
    near = centre + SLOT_CENTRE_BAND_MM
    far = THICKNESS + THICKNESS_BAND_MM - (centre - SLOT_CENTRE_BAND_MM)
    return max(near, far)


def tine_min_mm(teeth: int) -> float:
    """The thinner of ``teeth``'s two tines at the print's worst."""
    near = SLOT_FACE_MM - SLOT_FACE_BAND_MM
    far = (
        THICKNESS
        - THICKNESS_BAND_MM
        - (SLOT_FACE_MM + SLOT_FACE_BAND_MM)
        - SLOT_WIDTH_MAX_MM[teeth]
    )
    return min(near, far)


# The thinnest tine anywhere: printed on the sheet as a plain fact.
TINE_MIN_MM = min(tine_min_mm(t) for t in GEARS)
TINE_MIN_IN = math.floor(TINE_MIN_MM / INCH * 1000.0 + 1e-9) / 1000.0
if TINE_MIN_MM <= 0.25:
    raise AssertionError(f"tine {TINE_MIN_MM:.3f} mm thin")
for _teeth in GEARS:
    if face_reach_mm(_teeth) + TINE_AIR > NEIGHBOUR_REACH_MM[_teeth]:
        raise AssertionError(f"T{_teeth:03d} tine strikes the neighbouring tooth")

# --- Pose in the shop kit (MHA-DT-03-TL-00) -----------------------------------
# The comb's model origin (mm) in the kit frame, in the index plate's front
# plane under its rim; the kit's build places it here and its sheet finds it
# here.
KIT_POSITION_MM = (-11.0, -62.0, 0.0)

# --- Model --------------------------------------------------------------------
# The slot cuts run out this far below their fork tips.
SLOT_RUNOUT = 0.25


def slot_width_name(teeth: int) -> str:
    return f"SlotWidth{gear_tag(teeth)}"


def slot_face_name(teeth: int) -> str:
    return f"SlotFace{gear_tag(teeth)}"


# Model globals: name -> value (mm); the build sets each and drives from it.
GLOBALS: dict[str, float] = {
    "PlateLength": PLATE_LENGTH,
    "PlateHeight": PLATE_HEIGHT,
    "PlateThick": THICKNESS,
    "FingerLength": FINGER_LENGTH,
    "SlotRunout": SLOT_RUNOUT,
    "SlotFace": SLOT_FACE_MM,
    **{f"Start{gear_tag(t)}": FINGER_START_MM[t] for t in BONDED_TEETH},
    **{f"Fork{gear_tag(t)}": FORK_TIP_DEPTH_MM[t] for t in GEARS},
    **{f"Step{gear_tag(t)}": STEP_DEPTH_MM[t] for t in BONDED_TEETH[:-1]},
    **{slot_width_name(t): SLOT_WIDTH_MM[t] for t in GEARS},
}

# Profile vertices (model mm: x north along the plate, y outward), the
# closed chain the plate sketch draws: the south end up from the T030 fork
# tip, then each fork and the step north of it, then the north end and the top.
_SOUTH_X = -FINGER_LENGTH


def finger_x_mm(teeth: int) -> tuple[float, float]:
    """(south, north) model x of ``teeth``'s fork."""
    south = _SOUTH_X + FINGER_START_MM[teeth]
    north = _SOUTH_X + PLATE_LENGTH if teeth == GEARS[-1] else south + FINGER_LENGTH
    return south, north


def profile_points_mm() -> list[tuple[float, float]]:
    points = [(_SOUTH_X, PLATE_HEIGHT)]
    for index, teeth in enumerate(GEARS):
        south, north = finger_x_mm(teeth)
        fork = -FORK_TIP_DEPTH_MM[teeth]
        if index:
            points.append(
                (south, -STEP_DEPTH_MM[GEARS[index - 1]] if index > 1 else 0.0)
            )
        points.append((south, fork))
        points.append((north, fork))
        if teeth != GEARS[-1]:
            points.append((north, -STEP_DEPTH_MM[teeth]))
    points.append((_SOUTH_X + PLATE_LENGTH, PLATE_HEIGHT))
    return points


if profile_points_mm()[3] != (0.0, 0.0):
    raise AssertionError("the model origin is the T030 fork's north end on the seat")


def slot_rectangle_mm(teeth: int) -> tuple[float, float, float, float]:
    """(x0, z0, x1, z1) of ``teeth``'s slot in the model: the fork's length,
    its near wall SLOT_FACE off the plate's back face (Z0). It is cut on the
    Top plane (the seat line) down through its fork, SLOT_RUNOUT past the tip."""
    south, north = finger_x_mm(teeth)
    return south, SLOT_FACE_MM, north, SLOT_FACE_MM + SLOT_WIDTH_MM[teeth]


def _area(points: list[tuple[float, float]]) -> float:
    return 0.5 * abs(
        sum(
            x0 * y1 - x1 * y0
            for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1], strict=True)
        )
    )


PLATE_VOLUME = _area(profile_points_mm()) * THICKNESS
# Each slot removes its fork's length and width from the tip up to the seat.
SLOT_VOLUME_MM3 = {
    teeth: (
        (slot_rectangle_mm(teeth)[2] - slot_rectangle_mm(teeth)[0])
        * FORK_TIP_DEPTH_MM[teeth]
        * SLOT_WIDTH_MM[teeth]
    )
    for teeth in GEARS
}
FINISHED_VOLUME = PLATE_VOLUME - sum(SLOT_VOLUME_MM3.values())

# --- Drawing -------------------------------------------------------------------
PROFILE_SKETCH = "PlateProfile"
PLATE_FEATURE = "Plate"


def slot_sketch(teeth: int) -> str:
    return f"SlotProfile{gear_tag(teeth)}"


def slot_feature(teeth: int) -> str:
    return f"Slot{gear_tag(teeth)}"


PROFILE_DIMENSIONS = frozenset(
    {
        "PlateLength",
        "PlateHeight",
        "FingerLength",
        *(f"Start{gear_tag(t)}" for t in BONDED_TEETH),
        *(f"Fork{gear_tag(t)}" for t in GEARS),
        *(f"Step{gear_tag(t)}" for t in BONDED_TEETH[:-1]),
    }
)
# The slots stand in line: one location prints, on T006's slot at the plate's
# north end, as 5X.
SLOT_FACE_PRINTED = slot_face_name(GEARS[-1])
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    PROFILE_SKETCH: set(PROFILE_DIMENSIONS),
    PLATE_FEATURE: {"PlateThick"},
    **{slot_sketch(t): {slot_width_name(t)} for t in GEARS[:-1]},
    slot_sketch(GEARS[-1]): {slot_width_name(GEARS[-1]), SLOT_FACE_PRINTED},
}
_TWO_PLACE = frozenset(
    {"PlateHeight", *(f"Step{gear_tag(t)}" for t in BONDED_TEETH[:-1])}
)
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    feature: {name: 2 if name in _TWO_PLACE else 3 for name in names}
    for feature, names in DRAWING_DIMENSIONS.items()
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dims in DRAWING_PRECISION.values() for name, places in dims.items()
}
DRAWING_VALUES_BY_NAME: dict[str, float] = {
    name: (SLOT_FACE_MM if name == SLOT_FACE_PRINTED else GLOBALS[name])
    for name in DRAWING_PRECISION_BY_NAME
}
# Fabricated nominals sit on their printed inch grid (rule 3).
for _name, _value in DRAWING_VALUES_BY_NAME.items():
    _places = DRAWING_PRECISION_BY_NAME[_name]
    if abs(inch_grid_mm(_value, _places) - _value) > 1e-9:
        raise AssertionError(f"{_name} {_value} mm is off its .{'X' * _places} grid")
# The bands tighter than the title block, each at its shop row and set on the
# model's own dimension: (feature, dimension) -> (lower, upper) deviation, mm.
# Every slot's location carries the band; T006's prints for all five.
MODEL_BANDS_MM: dict[tuple[str, str], tuple[float, float]] = {
    (PLATE_FEATURE, "PlateThick"): THICKNESS_DEVIATIONS_MM,
    **{(PROFILE_SKETCH, f"Fork{gear_tag(t)}"): FORK_DEPTH_DEVIATIONS_MM for t in GEARS},
    **{(slot_sketch(t), slot_width_name(t)): SLOT_DEVIATIONS_MM for t in GEARS},
    **{(slot_sketch(t), slot_face_name(t)): SLOT_FACE_DEVIATIONS_MM for t in GEARS},
}
# Each band's stamped places: its printed precision; the four unprinted slot
# locations take the printed one's.
MODEL_BAND_PLACES: dict[tuple[str, str], int] = {
    (feature, name): DRAWING_PRECISION_BY_NAME.get(name, SLOT_FACE_PLACES)
    for feature, name in MODEL_BANDS_MM
}

# --- Sheet words ----------------------------------------------------------------
# Every banded dimension serves the five gears' teeth; note 1 names the fit
# of each, the slot callouts name the gears (rule 4). Words only (rule 7).
SLOT_NOTE_NUMBER = 1
SLOT_NOTE_FLAG = f"SEE NOTE {SLOT_NOTE_NUMBER}"
SHEET_NOTES = "\n".join(
    (
        f"{SLOT_NOTE_NUMBER}. EACH SLOT: CLEARANCE FIT ON ONE TOOTH OF THE GEAR NAMED",
        "   AT IT. ALL FIVE SLOTS IN LINE, SO THE FIVE GEARS PHASE TOGETHER.",
        "   EACH FORK TIP: BETWEEN ITS GEAR'S PITCH AND TIP CIRCLES. THE TINES:",
        "   CLEARANCE FIT IN THE TOOTH SPACES EACH SIDE OF THAT TOOTH.",
    )
)
if len(SHEET_NOTES.splitlines()) > 4:
    raise AssertionError("at most four note lines")
# Each slot names the gear whose tooth it fits; every tight band points at
# note 1; the thin tines print as a plain fact (rule 20).
TINE_WALL_TEXT = f"TINE WALL {inch_text(TINE_MIN_IN * INCH, 3)} MIN"
CALLOUTS_BELOW: dict[str, str] = {
    **{slot_width_name(t): f"{gear_number(t)} TOOTH\n{SLOT_NOTE_FLAG}" for t in GEARS},
    **{f"Fork{gear_tag(t)}": SLOT_NOTE_FLAG for t in GEARS},
    SLOT_FACE_PRINTED: SLOT_NOTE_FLAG,
    "PlateThick": f"{SLOT_NOTE_FLAG}\n{TINE_WALL_TEXT}",
}
# The four equal fork lengths and the five in-line slot locations print once.
CALLOUTS_ABOVE: dict[str, str] = {
    "FingerLength": f"{len(GEARS) - 1}X",
    SLOT_FACE_PRINTED: f"{len(GEARS)}X",
}
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
