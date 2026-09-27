r"""The 64T against MHA-016's north side, at print-worst.

SolidWorks-free.  The 64T (MHA-021) turns on the inclined cone shaft just
north of MHA-016, and its south face and tip sweep past everything on the
post's north side: the crank boss's spot face and the flat it runs out into,
the Ø44 cast collar, the turned Ø42 body, the cone boss's north end face and
the MHA-149 bushing's north end.  cg-fx2b's drive-train interference gate
caught the tip in the crank boss (0.00045 mm³ at nominal, once #906 R1 had
dropped the boss 0.21); the stack is dt-logs/handoffs/to-main/crankhub-0347.md
(probe: dt-logs/scratch/crankhub/gear64_boss_probe2.py, probe2d.log).

Frame: machine axes (north = +z, up = +y), origin where the cone axis crosses
the post axis.  The cone axis leans ``post.INCLINE_DEG`` in plan, the crank
bore runs along z ``CRANK_AXIS_Y`` above it, and after the post's Ry(180)
installation the spot face stands ``face_z`` north of the post axis.  The
64T's centre sits ``gear_offset`` along the cone axis from the origin; the
drive-train assembly owns that station and passes it in.

Each clearance is the gear's worst point against one solid: the boss and the
bushing end are cylinders ending at their north face (Euclidean past the
corner, axial over the face), the cone boss end a disc square to the cone
axis (along that axis), the collar and body vertical cylinders cut down to
the spot face over its footprint (the normal distance to the cylinder, and
over the footprint the larger of that and the air above the face -- a lower
bound, so never optimistic).  A negative value is overlap.

The collar and body were once z-axial air, which reads 1/cos(incline) wide
of the normal distance where the gear's tilted south face is the near
surface: the rim-124f SolidWorks cross-check measured 1.6812 on the Ø42 body
where the axial model said 1.722 (dt-logs/scratch/crankhub/rim_euclid.log).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import _config
import cone_gear_shaft_spec as shaft
import cone_pivot_post_spec as post
import crank_drive_gear_spec as gear64
import crank_eccentric_bushing_spec as bushing
import crank_pinion_spec as pinion

Point = tuple[float, float, float]


def _row(places: int) -> float:
    return float(str(_config.title_block(f"linear_{places}pl")["display"]).lstrip("±"))


SIN_I = math.sin(math.radians(post.INCLINE_DEG))
COS_I = math.cos(math.radians(post.INCLINE_DEG))
CRANK_AXIS_Y = post.CRANK_BORE_HEIGHT - post.BORE_HEIGHT
COLLAR_Y = (post.HEAD_BASE_Y - post.BORE_HEIGHT, post.BLOCK_HEIGHT - post.BORE_HEIGHT)
BODY_Y = (-post.BORE_HEIGHT, COLLAR_Y[0])

# --- The print-worst terms ----------------------------------------------------
# Each moves a surface toward the other.
#   spot-face station, CrankBossStartZ at .XX: the face stands north, and the
#   bushing, set flush with it, with it
SPOT_FACE_NORTH = _row(post.DRAWING_PRECISION_BY_NAME["CrankBossStartZ"])
#   its run-out flat's width and length below the crank axis, each at its row
SPOT_FACE_WIDTH_SHORT = _row(post.DRAWING_PRECISION_BY_NAME["SpotFaceWidth"])
#   ... and the crank axis, which the flat is laid out from, as high above
#   the cone axis as its spacing band allows
SPOT_FACE_RUN_OUT_SHORT = (
    _row(post.DRAWING_PRECISION_BY_NAME["SpotFaceRunOut"]) + post.CRANK_ABOVE_CONE_BAND[0]
)
#   the collar's lower edge, the top face (MainBodyHt) less the collar
#   (HeadHt), each at .X, with the foot's height about the cone axis
COLLAR_EDGE_LOW = (
    _row(post.DRAWING_PRECISION_BY_NAME["MainBodyHt"])
    + _row(post.DRAWING_PRECISION_BY_NAME["HeadHt"])
    + post.JOURNAL_AXIS_HEIGHT_TOLERANCE_MM
)
#   64T FaceWidth at .X: each face half the band nearer
GEAR_FACE_GROWTH = _row(gear64.DRAWING_PRECISION_BY_NAME["FaceWidth"]) / 2.0
#   64T tip, OutsideDia +/-OUTSIDE_DIA_TOLERANCE_MM (user, #906)
GEAR_TIP_GROWTH = gear64.OUTSIDE_DIA_TOLERANCE_MM / 2.0
#   the as-cast collar, HeadDia at .X; the turned body, MainBodyDia at .X
COLLAR_GROWTH = _row(post.DRAWING_PRECISION_BY_NAME["HeadDia"]) / 2.0
BODY_GROWTH = _row(post.DRAWING_PRECISION_BY_NAME["MainBodyDia"]) / 2.0
#   the cone boss's end faces, ConeBossLen at .X, symmetric about the post
#   axis: the north one short carries the collar and the 64T with it
CONE_BOSS_END_GROWTH = _row(post.DRAWING_PRECISION_BY_NAME["ConeBossLen"]) / 2.0
#   the 64T's station: the ONE input for how far it may stand toward the
#   post.  MHA-A03 step 1 sets it against MHA-014's thrust collar (#916),
#   and the collar bears on the cone boss's north end, so the gear's south
#   face stands the boss end plus CollarWidth off the post axis.  Both
#   joints are butts, nominally closed (build_drive_train_assembly asserts
#   each; collar_contacts below reads their sum) and only ever opening, so
#   they add nothing toward the post.  The stack is the boss end short by
#   its row and the collar thin by its own (Main's ruling (b), 2026-09-27).
COLLAR_WIDTH_SHORT = _row(shaft.DRAWING_PRECISION_BY_NAME["CollarWidth"])
GEAR64_STATION_TOWARD_POST = CONE_BOSS_END_GROWTH + COLLAR_WIDTH_SHORT
#   MHA-149's OD at the top of its g6 band
BUSHING_RADIUS_MAX = (bushing.OUTER_DIA + bushing.OD_BAND[0]) / 2.0

# --- The requirement ----------------------------------------------------------
# The floor every feature holds at print-worst is the running gap this
# assembly already sets between two parts: the 16T's seat feeler off the spot
# face (MHA-A03 step 4; Main's ruling, 2026-09-27).  build_drive_train_assembly
# asserts only this floor.  The steps below record the derivation: under the
# collar stack, the ruled 2.5 retreat and the 23 x 17 run-out each miss the
# floor a step smaller, which the unit tests pin.
FLOOR_CLEARANCE_MM = pinion.SEAT_FEELER_MM
RETREAT_STEP = 0.5
WIDTH_STEP = 1.0
RUN_OUT_STEP = 1.0


@dataclass(frozen=True)
class Gear:
    """The 64T as a solid disc: centre offset along the cone axis, half face
    width, tip radius."""

    gear_offset: float
    half_face: float
    tip_radius: float

    def south_face(self, t: float, r: float) -> Point:
        return self._at(-self.half_face, r, t)

    def tip(self, t: float, s: float) -> Point:
        return self._at(s, self.tip_radius, t)

    def _at(self, s: float, r: float, t: float) -> Point:
        # centre + s*u + r*(cos t * e1 + sin t * e2); u = (sin i, 0, cos i),
        # e1 = (cos i, 0, -sin i), e2 = (0, 1, 0)
        a = self.gear_offset + s
        ct, st = math.cos(t), math.sin(t)
        return (a * SIN_I + r * ct * COS_I, r * st, a * COS_I - r * ct * SIN_I)


@dataclass(frozen=True)
class SpotFace:
    """The crank boss's spot face: the boss disc at ``face_z``, run out as a
    flat ``width`` wide from the crank axis ``run_out`` down (``width`` None:
    the disc alone)."""

    face_z: float
    width: float | None = None
    run_out: float = 0.0

    def covers(self, x: float, y: float) -> bool:
        if math.hypot(x, y - CRANK_AXIS_Y) <= post.CRANK_BOSS_DIA / 2.0:
            return True
        return (
            self.width is not None
            and abs(x) <= self.width / 2.0
            and CRANK_AXIS_Y - self.run_out <= y <= CRANK_AXIS_Y
        )

    def at_print_worst(self) -> SpotFace:
        """North by the station's row, and the flat as narrow and short as
        its rows allow."""
        return SpotFace(
            self.face_z + SPOT_FACE_NORTH,
            None if self.width is None else self.width - SPOT_FACE_WIDTH_SHORT,
            self.run_out - SPOT_FACE_RUN_OUT_SHORT,
        )


def _cylinder_end(p: Point, radius: float, face_z: float) -> float:
    """Signed clearance to a crank-axis cylinder ending at ``face_z``."""
    radial = math.hypot(p[0], p[1] - CRANK_AXIS_Y) - radius
    axial = p[2] - face_z
    if axial <= 0.0:
        return radial
    return math.hypot(radial, axial) if radial > 0.0 else axial


def _casting(p: Point, band: tuple[float, float], radius: float, spot: SpotFace | None) -> float:
    """Distance from a vertical cylinder about the post axis over ``band``,
    cut down to the spot face wherever that covers it: normal to the
    cylinder, and over the footprint the larger of that and the air above the
    face (the distance to an intersection is at least either one)."""
    x, y, z = p
    if not band[0] <= y <= band[1]:
        return math.inf
    radial = math.hypot(x, z) - radius
    if spot is not None and spot.covers(x, y):
        return max(radial, z - spot.face_z)
    return radial


def _cone_boss_end(p: Point, end: float) -> float:
    """Along the cone axis, from the cone boss's north end disc."""
    x, y, z = p
    along = x * SIN_I + z * COS_I
    if x * x + y * y + z * z - along * along > (post.CONE_BOSS_DIA / 2.0) ** 2:
        return math.inf
    return along - end


def collar_contacts(gear_offset: float) -> float:
    """The two collar butts' nominal air, summed: the 64T's south face less
    the cone boss's north end and the collar between them.  Zero when the
    drive train seats the gear the way step 1 sets it."""
    south_face = gear_offset - gear64.FACE_WIDTH / 2.0
    return south_face - (post.CONE_BOSS_LENGTH / 2.0 + shaft.COLLAR_THICKNESS)


def clearances(*, gear_offset: float, spot: SpotFace, worst: bool = True) -> dict[str, float]:
    """Least clearance from the 64T to each feature on MHA-016's north side.

    ``gear_offset`` and ``spot`` are nominal; ``worst`` moves every term above
    toward the gear.  MHA-149's north end is set flush with the spot face.
    The cone boss end rides with the gear through the collar, so it is
    measured from the gear's south face by the collar at its low limit, never
    by the boss end's own growth on top of the station term.
    """
    air = collar_contacts(gear_offset)
    if abs(air) > 1e-6:
        raise ValueError(f"the 64T stands {air:+.4f} off the collar stack; its butts are open")
    grow = 1.0 if worst else 0.0
    gear = Gear(
        gear_offset - grow * GEAR64_STATION_TOWARD_POST,
        # Grown on both faces about the centre.  With the south face seated
        # on the collar, face width can only grow north, so the south-side
        # ~0.4 understates every margin here.  Kept: the ruled 2.5 / 23 x 17
        # minimality and its fail-first steps were derived under it, and
        # coupling it moves that derivation (#1049).
        gear64.FACE_WIDTH / 2.0 + grow * GEAR_FACE_GROWTH,
        gear64.OUTSIDE_DIA / 2.0 + grow * GEAR_TIP_GROWTH,
    )
    face = spot.at_print_worst() if worst else spot
    collar_r = post.HEAD_DIA / 2.0 + grow * COLLAR_GROWTH
    collar_low = COLLAR_Y[0] - grow * COLLAR_EDGE_LOW
    body_r = post.BLOCK_DIA / 2.0 + grow * BODY_GROWTH
    boss_end = gear.gear_offset - gear.half_face - (
        shaft.COLLAR_THICKNESS - grow * COLLAR_WIDTH_SHORT
    )
    bushing_r = BUSHING_RADIUS_MAX if worst else bushing.OUTER_DIA / 2.0
    measures: dict[str, Callable[[Point], float]] = {
        "crank boss": lambda p: _cylinder_end(p, post.CRANK_BOSS_DIA / 2.0, face.face_z),
        "MHA-149 north end": lambda p: _cylinder_end(p, bushing_r, face.face_z),
        "collar": lambda p: _casting(p, (collar_low, COLLAR_Y[1]), collar_r, face),
        "body": lambda p: _casting(p, (BODY_Y[0], collar_low), body_r, face),
        "cone boss end": lambda p: _cone_boss_end(p, boss_end),
    }
    return {name: _least(gear, measure) for name, measure in measures.items()}


def worst_shortfalls(gear_offset: float, spot: SpotFace) -> dict[str, float]:
    """The features that miss FLOOR_CLEARANCE_MM at print-worst, by how much."""
    return {
        name: FLOOR_CLEARANCE_MM - value
        for name, value in clearances(gear_offset=gear_offset, spot=spot).items()
        if value < FLOOR_CLEARANCE_MM
    }


def spot_face(retreat: float, width: float, run_out: float) -> SpotFace:
    return SpotFace(post.CRANK_BOSS_HARVESTED_NORTH_FACE - retreat, width, run_out)


def one_step_short(retreat: float, width: float, run_out: float) -> dict[str, SpotFace]:
    """The spot face a step smaller in each of its three sizes."""
    return {
        "retreat": spot_face(retreat - RETREAT_STEP, width, run_out),
        "width": spot_face(retreat, width - WIDTH_STEP, run_out),
        "run-out": spot_face(retreat, width, run_out - RUN_OUT_STEP),
    }


def _least(gear: Gear, measure: Callable[[Point], float]) -> float:
    """Least of ``measure`` over the gear's south face and tip cylinder: a
    grid over each, then two zooms about its worst cell."""
    face = _zoom(lambda t, r: measure(gear.south_face(t, r)), (0.0, 2.0 * math.pi), (0.0, gear.tip_radius))
    tip = _zoom(lambda t, s: measure(gear.tip(t, s)), (0.0, 2.0 * math.pi), (-gear.half_face, gear.half_face))
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
        if value == math.inf:
            return math.inf
        best = min(best, value)
        da, db = 2.0 * (a1 - a0) / n_a, 2.0 * (b1 - b0) / n_b
        ai, bk = a0 + (a1 - a0) * i / n_a, b0 + (b1 - b0) * k / n_b
        a = (ai - da, ai + da)
        b = (max(b[0], bk - db), min(b[1], bk + db))
    return best
