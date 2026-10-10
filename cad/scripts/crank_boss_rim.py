r"""The 64T against MHA-DT-005's north side, at print-worst.

SolidWorks-free.  The 64T (MHA-DT-007) turns on the inclined cone shaft just
north of MHA-DT-005, and its south face and tip sweep past everything on the
post's north side: the crank boss's north face and rim, the Ø42.75 head,
the turned Ø42 body and the cone boss's north end face.  The post retains
the v36 datums (user ruling 2026-09-28), with its body/head raised for the
normal-24DP crank. The crank boss starts on the head's tangent plane, uncut,
and the crank bore carries no bushing. The 64T
stands on the unchanged MHA-DT-004 collar; its south face is fixed there, while
the solid gear stack grows its north face to touch T120. The collar and boss
bands, not the gear face-width band, govern clearance to MHA-DT-005.

Frame: machine axes (north = +z, up = +y), origin where the cone axis crosses
the post axis.  The cone axis leans ``post.INCLINE_DEG`` in plan, the crank
axis runs along z ``CRANK_AXIS_Y`` above it, and after the post's Ry(180)
installation the crank boss's north face stands ``CRANK_BOSS_NORTH_FACE``
north of the post axis.  The 64T's centre sits ``gear_offset`` along the cone
axis from the origin; the drive-train assembly owns that station and passes
it in.

Each clearance is the gear's worst point against one solid, measured as a
true distance to a finite solid: the crank boss a crank-axis cylinder ending
at its north face, the head and the body vertical cylinders about the post
axis over their height bands, the cone boss's end a disc square to the cone
axis.  Past an edge the distance runs to the edge.  A negative value is
overlap.  The gear is an untoothed disc to its tip diameter, so the real cut
gear can only read farther (gear64_post_measure checks that natively).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import _config
import dt_cone_gear_shaft_spec as shaft
import dt_cone_pivot_post_spec as post
import dt_crank_drive_gear_spec as gear64

Point = tuple[float, float, float]

RULING = "user ruling 2026-09-28"


def _row(places: int) -> float:
    return float(str(_config.title_block(f"linear_{places}pl")["display"]).lstrip("±"))


SIN_I = math.sin(math.radians(post.INCLINE_DEG))
COS_I = math.cos(math.radians(post.INCLINE_DEG))
CRANK_AXIS_Y = post.CRANK_ABOVE_CONE
HEAD_Y = (
    post.HEAD_BASE_Y - post.BORE_HEIGHT,
    post.HEAD_BASE_Y + post.HEAD_HEIGHT - post.BORE_HEIGHT,
)
# The body occupies the full native MainBody extrusion, including the core
# inside the larger head.  Use its actual height, not a truncated surrogate.
BODY_Y = (-post.BORE_HEIGHT, post.BLOCK_HEIGHT - post.BORE_HEIGHT)

# --- The print-worst terms ----------------------------------------------------
# Each moves a surface toward the other.
#   the crank boss's north face, CrankBossStartZ at .XX
CRANK_BOSS_NORTH = _row(post.DRAWING_PRECISION_BY_NAME["CrankBossStartZ"])
#   the cast crank boss, CrankBossDia at .X: its face disc reaches further down
#   toward the gear's tip
CRANK_BOSS_GROWTH = _row(post.DRAWING_PRECISION_BY_NAME["CrankBossDia"]) / 2.0
#   the crank axis over the crank-above-cone spacing band, both ends taken
#   (a lower boss reaches deeper into the tip's sweep)
CRANK_AXIS_Y_BAND = tuple(CRANK_AXIS_Y + d for d in sorted(post.CRANK_ABOVE_CONE_BAND))
#   the head's lower edge, the top face (MainBodyHt) less the head
#   (HeadHt), each at .X, with the foot's height about the cone axis
HEAD_EDGE_LOW = (
    _row(post.DRAWING_PRECISION_BY_NAME["MainBodyHt"])
    + _row(post.DRAWING_PRECISION_BY_NAME["HeadHt"])
    + post.JOURNAL_AXIS_HEIGHT_TOLERANCE_MM
)
#   the head, HeadDia at .X; the turned body, MainBodyDia at .X
HEAD_GROWTH = _row(post.DRAWING_PRECISION_BY_NAME["HeadDia"]) / 2.0
BODY_GROWTH = _row(post.DRAWING_PRECISION_BY_NAME["MainBodyDia"]) / 2.0
#   the cone boss's end faces, ConeBossLen at .XX, symmetric about the post
#   axis: the north end SHORT brings the seated collar and 64T toward the
#   post; the boss itself, ConeBossDia at .X
CONE_BOSS_END_GROWTH = _row(post.DRAWING_PRECISION_BY_NAME["ConeBossLen"]) / 2.0
CONE_BOSS_GROWTH = _row(post.DRAWING_PRECISION_BY_NAME["ConeBossDia"]) / 2.0
#   the 64T's station: the ONE input for how far it may stand toward the
#   post.  MHA-DT-000 step 1 sets it against MHA-DT-004's thrust collar (#916),
#   and the collar bears on the cone boss's north end, so the gear's south
#   face stands the boss end plus CollarWidth off the post axis.  Both
#   joints are butts, nominally closed (build_dt_drive_train_assembly asserts
#   each; collar_contacts below reads their sum) and only ever opening, so
#   they add nothing toward the post. The stack is the boss end SHORT by
#   its row and the collar thin by its own (Main's ruling (b), 2026-09-27).
COLLAR_WIDTH_SHORT = _row(shaft.DRAWING_PRECISION_BY_NAME["CollarWidth"])
GEAR64_STATION_TOWARD_POST = CONE_BOSS_END_GROWTH + COLLAR_WIDTH_SHORT
#   FaceWidth's ±0.025 extends NORTH of the seated south face and does not
#   consume any margin to the post; only the collar and MHA-DT-005 bands do.
#   64T tip, OutsideDia +/-OUTSIDE_DIA_TOLERANCE_MM (user, #906)
GEAR_TIP_GROWTH = gear64.OUTSIDE_DIA_TOLERANCE_MM / 2.0

# Every MHA-DT-005 north feature holds this much air to the 64T at print-worst.
FLOOR_CLEARANCE_MM = 0.25


@dataclass(frozen=True)
class Gear:
    """The 64T as a solid disc about the cone axis: its south and north faces
    as stations along that axis, and its tip radius."""

    south: float
    north: float
    tip_radius: float

    def south_face(self, t: float, r: float) -> Point:
        return self._at(self.south, r, t)

    def tip(self, t: float, a: float) -> Point:
        return self._at(a, self.tip_radius, t)

    @staticmethod
    def _at(a: float, r: float, t: float) -> Point:
        # a*u + r*(cos t * e1 + sin t * e2); u = (sin i, 0, cos i),
        # e1 = (cos i, 0, -sin i), e2 = (0, 1, 0)
        ct, st = math.cos(t), math.sin(t)
        return (a * SIN_I + r * ct * COS_I, r * st, a * COS_I - r * ct * SIN_I)


def _crank_boss(p: Point, radius: float, face_z: float, axis_y: float) -> float:
    """From a crank-axis cylinder ending at ``face_z``: radial beside it,
    axial over the face, to the rim edge past both."""
    radial = math.hypot(p[0], p[1] - axis_y) - radius
    axial = p[2] - face_z
    if axial <= 0.0:
        return radial
    return math.hypot(radial, axial) if radial > 0.0 else axial


def _post_cylinder(p: Point, band: tuple[float, float], radius: float) -> float:
    """From a vertical cylinder about the post axis over the height ``band``:
    normal to it beside the band, to its edge circle above or below."""
    x, y, z = p
    radial = math.hypot(x, z) - radius
    beyond = max(band[0] - y, y - band[1], 0.0)
    if beyond == 0.0:
        return radial
    return math.hypot(max(radial, 0.0), beyond)


def _cone_boss_end(p: Point, end: float, radius: float) -> float:
    """From the cone boss's north end disc: along the cone axis over it, to
    its rim edge beyond it."""
    x, y, z = p
    along = x * SIN_I + z * COS_I
    off_axis = math.sqrt(max(0.0, x * x + y * y + z * z - along * along))
    axial = along - end
    if off_axis <= radius:
        return axial
    return math.hypot(off_axis - radius, max(axial, 0.0))


def seated_gear_offset(*, collar_thickness: float = shaft.COLLAR_THICKNESS) -> float:
    """The 64T's centre along the cone axis, with its south face seated on
    the cone boss's north end plus the collar."""
    return post.CONE_BOSS_LENGTH / 2.0 + collar_thickness + gear64.FACE_WIDTH / 2.0


def collar_contacts(
    gear_offset: float, *, collar_thickness: float = shaft.COLLAR_THICKNESS
) -> float:
    """The two collar butts' nominal air, summed; zero for a seated gear."""
    return gear_offset - seated_gear_offset(collar_thickness=collar_thickness)


def clearances(
    *, gear_offset: float, worst: bool = True,
    collar_thickness: float = shaft.COLLAR_THICKNESS,
) -> dict[str, float]:
    """Least clearance from the 64T to each feature on MHA-DT-005's north side.

    ``gear_offset`` must seat the south face on ``collar_thickness``. ``worst``
    moves each published boss/collar/gear-tip band toward its opposing surface;
    FaceWidth's ±0.025 shifts only the north face and cannot move this seat.
    """
    air = collar_contacts(gear_offset, collar_thickness=collar_thickness)
    if abs(air) > 1e-6:
        raise ValueError(f"the 64T stands {air:+.4f} off the collar stack; its butts are open")
    grow = 1.0 if worst else 0.0
    south = gear_offset - gear64.FACE_WIDTH / 2.0 - grow * GEAR64_STATION_TOWARD_POST
    gear = Gear(
        south,
        south + gear64.FACE_WIDTH + grow * gear64.FACE_WIDTH_BAND[0],
        gear64.OUTSIDE_DIA / 2.0 + grow * GEAR_TIP_GROWTH,
    )
    boss_r = post.CRANK_BOSS_DIA / 2.0 + grow * CRANK_BOSS_GROWTH
    boss_z = post.CRANK_BOSS_NORTH_FACE + grow * CRANK_BOSS_NORTH
    axes = CRANK_AXIS_Y_BAND if worst else (CRANK_AXIS_Y,)
    head_r = post.HEAD_DIA / 2.0 + grow * HEAD_GROWTH
    head_low = HEAD_Y[0] - grow * HEAD_EDGE_LOW
    body_r = post.BLOCK_DIA / 2.0 + grow * BODY_GROWTH
    boss_end = gear.south - (collar_thickness - grow * COLLAR_WIDTH_SHORT)
    cone_r = post.CONE_BOSS_DIA / 2.0 + grow * CONE_BOSS_GROWTH
    measures: dict[str, Callable[[Point], float]] = {
        "crank boss": lambda p: min(_crank_boss(p, boss_r, boss_z, y) for y in axes),
        "head": lambda p: _post_cylinder(p, (head_low, HEAD_Y[1]), head_r),
        "body": lambda p: _post_cylinder(p, BODY_Y, body_r),
        "cone boss end": lambda p: _cone_boss_end(p, boss_end, cone_r),
    }
    return {name: _least(gear, measure) for name, measure in measures.items()}


def worst_shortfalls(
    gear_offset: float, *, collar_thickness: float = shaft.COLLAR_THICKNESS
) -> dict[str, float]:
    """The features that miss FLOOR_CLEARANCE_MM at print-worst, by how much."""
    return {
        name: FLOOR_CLEARANCE_MM - value
        for name, value in clearances(
            gear_offset=gear_offset, collar_thickness=collar_thickness
        ).items()
        if value < FLOOR_CLEARANCE_MM
    }


def _least(gear: Gear, measure: Callable[[Point], float]) -> float:
    """Least of ``measure`` over the gear's south face and tip cylinder: a
    grid over each, then two zooms about its worst cell."""
    face = _zoom(lambda t, r: measure(gear.south_face(t, r)), (0.0, 2.0 * math.pi), (0.0, gear.tip_radius))
    tip = _zoom(lambda t, a: measure(gear.tip(t, a)), (0.0, 2.0 * math.pi), (gear.south, gear.north))
    return min(face, tip)


def _zoom(f: Callable[[float, float], float], a: tuple[float, float], b: tuple[float, float]) -> float:
    best = math.inf
    for n_a, n_b in ((240, 24), (40, 20), (40, 20)):
        (a0, a1), (b0, b1) = a, b
        cells = [
            (f(a0 + (a1 - a0) * i / n_a, b0 + (b1 - b0) * k / n_b), i, k)
            for i in range(n_a + 1)
            for k in range(n_b + 1)
        ]
        value, i, k = min(cells)
        best = min(best, value)
        da, db = 2.0 * (a1 - a0) / n_a, 2.0 * (b1 - b0) / n_b
        ai, bk = a0 + (a1 - a0) * i / n_a, b0 + (b1 - b0) * k / n_b
        a = (ai - da, ai + da)
        b = (max(b[0], bk - db), min(b[1], bk + db))
    return best


# Every feature clears the print-worst floor on the seated collar. The prior
# "one face-width step wider fails" was tied to an obsolete south-growing gear.
# A collar made enough thinner instead eventually fails on the crank boss.
WORST_CLEARANCES = clearances(gear_offset=seated_gear_offset())
GOVERNING_FEATURE = min(WORST_CLEARANCES, key=WORST_CLEARANCES.__getitem__)
if WORST_CLEARANCES[GOVERNING_FEATURE] < FLOOR_CLEARANCE_MM:
    raise AssertionError(
        f"the seated 64T comes {WORST_CLEARANCES[GOVERNING_FEATURE]:.3f} "
        f"from MHA-DT-005's {GOVERNING_FEATURE} at print-worst, under the "
        f"{FLOOR_CLEARANCE_MM} floor ({RULING})"
    )
COLLAR_MARGIN_MM = WORST_CLEARANCES[GOVERNING_FEATURE] - FLOOR_CLEARANCE_MM
THINNER_COLLAR = shaft.COLLAR_THICKNESS - COLLAR_MARGIN_MM - 0.01
THINNER_COLLAR_CLEARANCE = clearances(
    gear_offset=seated_gear_offset(collar_thickness=THINNER_COLLAR),
    collar_thickness=THINNER_COLLAR,
)[GOVERNING_FEATURE]
if THINNER_COLLAR_CLEARANCE >= FLOOR_CLEARANCE_MM:
    raise AssertionError("thinning the collar past its remaining margin must breach the post floor")
