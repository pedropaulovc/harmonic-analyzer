r"""Pure-data contract for the cone tip gears' phasing comb (MHA-DT-03-TL-02).

Shop tooling, not a machine part (cad/docs/subsystem-identities.md): the
fixture MHA-DT-00 step 1 engages while LOCTITE 638 grabs, so the bonded tip
gears cure in phase with the keyed stack (owner ruling 2026-11-09 (b1) via PR
#1992, C1 keyed; single blade per gear, owner ruling 2026-11-10 via PR #1992).
The 1898 machine has no such tool (its gears are fixed differently); this is
shop tooling for the replica's bonded tip. Owner ruling 2026-11-13: the comb
is cut to shape from a single sheet of metal. It is one flat brass sheet,
SHEET_THICK thick as bought, its stepped edge the whole part: no blade is
thinned and no face is a datum.

Every cone gear has a tooth centred on its local +X (phase 0; the keyway runs
through T030's), so a tooth space is centred at +180/N deg on every gear. A
space's centre stands about half a circular pitch off the +X radial plane on
every 48 DP gear at its pitch circle, so one sheet lying parallel to that
plane, that far off it, passes down the space beside the phase-0 tooth of
T030 (the reference, keyed) and of the bonded T024, T018, T012 (MHA-DT-03)
and T006 (MHA-DT-37) at once. Its edge is a staircase: one level (a blade)
per gear, each deeper than the last, south to north.

Frame (the SolidWorks model). X runs along the cone axis, north (the sheet's
length); Y runs radially outward, along the gears' +X (its height); Z is the
tangential direction, the gears' +Y (its thickness). The origin is the
sheet's south end on its T030 blade's edge: the SEAT line.

The seat: T030's blade drops into T030's space until it bottoms on T030's
root; on the thickest sheet over the narrowest root space it binds between
the flanks just above it instead. Where it bottoms, the sheet may slide
across the space as far as the space lets it (``SEAT_CONDITIONS``,
``COMB_SLIDE_MM``). Every other
blade stands at its printed depth under the seat line, at the title block's
.XXX band; each bonded gear turns until its space holds its blade, anywhere
in that space's play. The depths are the deepest on the .001 grid at which no
blade bottoms on its gear's root or binds in its space at any printed limit:
the deeper the blade, the narrower the space and the less play.
``PHASE_ERROR_MM`` proves every bonded gear's worst phase against T030 at
every limit inside the booked error_budget.yaml cone_tip_bond_clock.

Assumption: the fitter presses the comb radially and holds the sheet
parallel to the radial plane; it slides tangentially only as far as T030's
space lets it.
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
DEPTH_PLACES = 3
_XXX = printed_band_mm(DEPTH_PLACES, unit=UNIT)


def inch_grid_mm(value_mm: float, places: int, rounding=round) -> float:
    """``value_mm`` on the printed inch grid (rule 3)."""
    return family.inch_grid_mm(value_mm, places, rounding)


def inch_text(value_mm: float, places: int) -> str:
    return family.inch_text(value_mm, places)


# --- The sheet ----------------------------------------------------------------
# Half-hard brass shim stock, .020 in, as bought (ASTM B36); its listed
# thickness tolerance is +/-.002 in (McMaster-Carr 9011K111, 8 x 12 in sheet,
# read 2026-11-13). Of the stock gauges .015, .020 and .025, .020 is the one
# whose worst phase stays inside the booked bond clock: thinner leaves more
# play in every space, and .025 binds in T030's space at a depth that its
# +/-.001 moves by several times as much.
SHEET_THICK = 0.020 * INCH
SHEET_THICK_TOLERANCE_MM = 0.002 * INCH
SHEET_LIMITS_MM = (
    SHEET_THICK - SHEET_THICK_TOLERANCE_MM,
    SHEET_THICK,
    SHEET_THICK + SHEET_THICK_TOLERANCE_MM,
)


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


# --- Axial: each blade starts inside its gear's face --------------------------
FACE_WIDTH = family.FACE_WIDTH


def _south_face_mm(teeth: int) -> float:
    """Nominal south face of ``teeth``'s leaves from T030's south face: T030,
    one STACK_FEELER, then T024, T018, T012 and T006 face to face."""
    index = GEARS.index(teeth)
    return index * FACE_WIDTH + (STACK_FEELER if index else 0.0)


# Each blade's level runs from the step at its south end north to the next
# step: over its own gear's face, then over the smaller gear beyond it, whose
# tips it clears (below). A step never stands over the larger gear south of
# it (the deeper level would strike that gear's teeth), the sheet's south
# end never over T030's south neighbour, and its north end never past
# T006's north face (the MHA-DT-38 bushing). The sheet stops BLADE_INSET
# inside T030's south face and T006's north face, and each step stands
# BLADE_INSET north of its gear's south face. T006's level is BLADE_LENGTH
# long. Every length is .XX at the title block's band (rule 3): the inset
# keeps every step clear at that band (AXIAL_PLACEMENT_WINDOW).
BLADE_INSET = 0.030 * INCH
BLADE_LENGTH_PLACES = 2
BLADE_LENGTH = inch_grid_mm(
    FACE_WIDTH - 2.0 * BLADE_INSET, BLADE_LENGTH_PLACES, math.floor
)
# Blade south ends (the steps) from the sheet's south end, printed.
BLADE_START_MM: dict[int, float] = {
    teeth: inch_grid_mm(_south_face_mm(teeth), BLADE_LENGTH_PLACES) for teeth in GEARS
}
SHEET_LENGTH = BLADE_START_MM[GEARS[-1]] + BLADE_LENGTH


def _placement_window_mm(
    feeler: float, faces: tuple[float, ...], ends: tuple[float, ...]
) -> float:
    """Width of the comb shifts that keep every step and both ends clear, for
    one stack (the feeler's and each face's deviation, T030 first) and one
    print (``ends``: each step's deviation, T006's last, then the sheet
    length's)."""
    south: list[float] = []
    station = 0.0
    for index, teeth in enumerate(GEARS):
        if index:
            station += FACE_WIDTH + faces[index - 1] + (feeler if index == 1 else 0.0)
        south.append(station)
    # Comb placed with its south end BLADE_INSET north of T030's south face,
    # then shifted by s: step g at INSET + START_g + end_g + s.
    low = max(
        south[index] - (BLADE_INSET + BLADE_START_MM[teeth] + ends[index])
        for index, teeth in enumerate(GEARS)
    )
    north_face = south[-1] + FACE_WIDTH + faces[-1]
    high = north_face - (BLADE_INSET + SHEET_LENGTH + ends[-1])
    return high - low


def _placement_window_min_mm() -> float:
    face, feeler, printed = abs(family.FACE_WIDTH_BAND[1]), STACK_FEELER_BAND, _XX
    widths = []
    for signs in itertools.product((-1.0, 1.0), repeat=len(GEARS) + 3):
        faces = tuple(sign * face for sign in signs[: len(GEARS)])
        stack_feeler = signs[len(GEARS)] * feeler
        # Every print: the steps at either end of their .XX band (together),
        # the sheet's length at either end of its own.
        start, length = signs[-2] * printed, signs[-1] * printed
        ends = (0.0, *(start for _ in GEARS[1:]), length)
        widths.append(_placement_window_mm(stack_feeler, faces, ends))
    return min(widths)


# The fitter centres the comb on the stack by eye; at the worst stack and
# print it still has this much axial freedom.
AXIAL_PLACEMENT_WINDOW_MM = _placement_window_min_mm()
if AXIAL_PLACEMENT_WINDOW_MM < 0.1:
    raise AssertionError(
        f"comb placement window {AXIAL_PLACEMENT_WINDOW_MM:.3f} mm: a step overhangs"
    )

# Before the compound grabs a bonded gear may float radially by half its bond
# clearance (T024 on land 2; T018, T012 and T006's spigot on .0625).
BOND_FLOAT_MM = max(
    *(family.bond_clearance_mm(teeth)[1] / 2.0 for teeth in (24, 18, 12)),
    cluster.SPIGOT_BOND_CLEARANCE_MM[1] / 2.0,
)


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


# (edge, mid-plane, sheet) of every seat at every printed corner and sheet.
SEAT_CONDITIONS: tuple[tuple[float, float, float], ...] = tuple(
    (edge, mid, sheet)
    for corner in range(len(_profiles(REFERENCE_TEETH)))
    for sheet in SHEET_LIMITS_MM
    for edge, mid in _seat(corner, sheet)
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


# --- Each bonded blade's depth below the seat line -----------------------------
def _float_mm(teeth: int) -> float:
    return 0.0 if teeth == REFERENCE_TEETH else BOND_FLOAT_MM


def _conditions(teeth: int, depth_mm: float):
    """Every printed limit a bonded blade meets: each seat, each tooth corner
    of its gear, the depth's band and the gear's float either way. Yields
    (corner, edge, mid-plane, sheet)."""
    for edge, mid, sheet in SEAT_CONDITIONS:
        for corner in range(len(_profiles(teeth))):
            for band in (-_XXX, _XXX):
                for drift in (-_float_mm(teeth), _float_mm(teeth)):
                    yield corner, edge - depth_mm + band + drift, mid, sheet


def _enters(teeth: int, depth_mm: float) -> bool:
    """At every limit the blade neither bottoms on the root nor binds."""
    for corner, edge, mid, sheet in _conditions(teeth, depth_mm):
        try:
            low, high = _window(teeth, corner, edge, mid, sheet)
        except ValueError:
            return False
        if high <= low:
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
    if math.hypot(_shallowest, COMB_SLIDE_MM[1]) >= tip_radius_limits_mm(_teeth)[0]:
        raise AssertionError(f"T{_teeth:03d} blade stands over its gear's tips")
# Each level passes over the next, smaller gear's tips (its own blade's step
# stands BLADE_INSET into that gear's face) at the lowest print and seat and
# the smaller gear's highest float.
for _south, _north in zip(GEARS, GEARS[1:], strict=False):
    _band = 0.0 if _south == REFERENCE_TEETH else _XXX
    _lowest = SEAT_EDGE_MM[0] - blade_depth_mm(_south) - _band
    if _lowest <= tip_radius_limits_mm(_north)[1] + BOND_FLOAT_MM:
        raise AssertionError(f"T{_south:03d} level reaches T{_north:03d}'s tips")


def phase_error_mm(teeth: int) -> float:
    """A bonded gear's worst phase against T030, pitch arc: the comb on T030
    at every seat, the gear's corner, its blade's depth band and its float,
    the gear turned to either end of its space's play about the blade."""
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
# plane under its rim, clear of it by about a balloon's diameter; the kit's
# build places it here and its sheet shows it there under item 1.
KIT_POSITION_MM = (-17.0, -70.0, 0.0)

# --- Model --------------------------------------------------------------------
# The sheet stands this high over the seat line (.XX): a grip.
SHEET_HEIGHT = 0.25 * INCH


def blade_depth_name(teeth: int) -> str:
    return f"BladeDepth{gear_tag(teeth)}"


def blade_start_name(teeth: int) -> str:
    return f"Start{gear_tag(teeth)}"


# Model globals: name -> value (mm); the build sets each and drives from it.
GLOBALS: dict[str, float] = {
    "SheetLength": SHEET_LENGTH,
    "SheetHeight": SHEET_HEIGHT,
    "SheetThick": SHEET_THICK,
    **{blade_start_name(t): BLADE_START_MM[t] for t in BONDED_TEETH},
    **{blade_depth_name(t): BLADE_DEPTH_MM[t] for t in BONDED_TEETH},
}


def blade_x_mm(teeth: int) -> tuple[float, float]:
    """(south, north) model x of ``teeth``'s level: its step to the next
    step (T030's from the south end, T006's to the north end)."""
    index = GEARS.index(teeth)
    south = BLADE_START_MM[teeth]
    north = SHEET_LENGTH if teeth == GEARS[-1] else BLADE_START_MM[GEARS[index + 1]]
    return south, north


def profile_points_mm() -> list[tuple[float, float]]:
    """The closed staircase the sheet sketch draws (model mm: x north, y
    outward): the south end down to the seat line, each level north to its
    step and down the step, T006's level to the north end, up and back along
    the top."""
    points = [(0.0, SHEET_HEIGHT), (0.0, 0.0)]
    for teeth in GEARS[1:]:
        south, _north = blade_x_mm(teeth)
        points.append((south, -blade_depth_mm(GEARS[GEARS.index(teeth) - 1])))
        points.append((south, -blade_depth_mm(teeth)))
    points.append((SHEET_LENGTH, -blade_depth_mm(GEARS[-1])))
    points.append((SHEET_LENGTH, SHEET_HEIGHT))
    return points


def step_corner_index(teeth: int) -> int:
    """Index in ``profile_points_mm`` of the lower corner of the step at
    ``teeth``'s level's south end, where its start and depth are measured."""
    return 1 + 2 * GEARS.index(teeth)


if profile_points_mm()[1] != (0.0, 0.0):
    raise AssertionError("the model origin is the south end on the seat line")
for _teeth in BONDED_TEETH:
    if profile_points_mm()[step_corner_index(_teeth)] != (
        BLADE_START_MM[_teeth],
        -BLADE_DEPTH_MM[_teeth],
    ):
        raise AssertionError(f"T{_teeth:03d} step corner out of order")


def _area(points: list[tuple[float, float]]) -> float:
    return 0.5 * abs(
        sum(
            x0 * y1 - x1 * y0
            for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1], strict=True)
        )
    )


SHEET_VOLUME = _area(profile_points_mm()) * SHEET_THICK

# --- Drawing -------------------------------------------------------------------
PROFILE_SKETCH = "SheetProfile"
SHEET_FEATURE = "Sheet"
PROFILE_DIMENSIONS = frozenset(
    {
        "SheetLength",
        "SheetHeight",
        *(blade_start_name(t) for t in BONDED_TEETH),
        *(blade_depth_name(t) for t in BONDED_TEETH),
    }
)
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    PROFILE_SKETCH: set(PROFILE_DIMENSIONS),
    SHEET_FEATURE: {"SheetThick"},
}
# Every length and height no fit depends on is .XX (rule 3); each blade's
# depth (it decides where the blade meets its space) is .XXX at the title
# block's band, and the stock's thickness .XXX as a reference.
_THREE_PLACE = frozenset({"SheetThick", *(blade_depth_name(t) for t in BONDED_TEETH)})
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
# Each blade's depth names its gear (rule 4) and flags note 1, which says
# what the depth is for (rule 7); the left blade, T030's, is the depths'
# datum. The thickness is the stock's, printed as a reference over SHEET
# STOCK (pn-pen-hanger, pd-platen-clip): the stock's own tolerance governs.
NOTE_FLAG = "SEE NOTE 1"
SHEET_NOTES = "\n".join(
    (
        "1. EACH BLADE DROPS INTO ONE TOOTH SPACE OF THE GEAR NAMED AT ITS",
        "   DEPTH, CLEAR OF THAT GEAR'S ROOT. THE LEFT BLADE, FROM WHICH THE",
        f"   DEPTHS ARE TAKEN, SEATS IN A TOOTH SPACE OF {gear_number(REFERENCE_TEETH)}.",
    )
)
if len(SHEET_NOTES.splitlines()) > 4:
    raise AssertionError("at most four note lines")
STOCK_TEXT = "SHEET STOCK"
REFERENCE_DIMENSIONS = frozenset({"SheetThick"})
CALLOUTS_BELOW: dict[str, str] = {
    **{blade_depth_name(t): f"{gear_number(t)}\n{NOTE_FLAG}" for t in BONDED_TEETH},
    "SheetThick": STOCK_TEXT,
}
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
