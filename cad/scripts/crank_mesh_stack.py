"""Fixed-centre 16T:64T tight-backlash stack (user ruling 2026-09-28).

No backlash window or adjustable axis: the printed post-bore angularity and
spacing must leave positive backlash at the worst closing corner. Slopes and
pose readings are from the exact-solid B-star and crank-mesh-angle studies
(2026-09-26); their residual is retained conservatively.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import _config
import cone_pivot_post_spec as post
import crank_drive_gear_notes
import crank_drive_gear_spec as gear64
import crank_pinion_spec as pinion
import crankshaft_spec as shaft
from retained_joint_fit import RETAINED_JOINT_CLEARANCE

R64 = gear64.PITCH_DIA / 2.0
R16 = (16.0 / gear64.DIAMETRAL_PITCH) * gear64.MM_PER_IN / 2.0
FRAME_C2C = R64 + R16 + _config.fit("crank_mesh", "c2c_slack_mm")
# This is the conservative historical reference plane, not the physical
# narrowed-gear centre; the assembly asserts the latter is farther apart.
FRAME_DY = post.CRANK_BORE_HEIGHT - post.BORE_HEIGHT
FRAME_DX = math.sqrt(FRAME_C2C**2 - FRAME_DY**2)
DC_PER_DY = FRAME_DY / FRAME_C2C
DC_PER_DX = FRAME_DX / FRAME_C2C
if not R64 > R16 > 0 or not FRAME_C2C > FRAME_DY > 0:
    raise AssertionError("fixed-centre mesh geometry needs ordered radii and real axis spacing")
if not math.isclose(DC_PER_DX**2 + DC_PER_DY**2, 1.0):
    raise AssertionError("mesh centre-distance projections must be orthonormal")

NOMINAL_TIGHT_BACKLASH_MM = 0.32269
KC = (0.41222 - 0.23685) / 0.300
K64 = (0.41722 - 0.22079) / 0.20
K16 = (0.36930 - 0.31888) / 0.05
if not KC > 0 and K64 > 0 and K16 > 0:
    raise AssertionError("measured mesh sensitivities must preserve the tight-corner sign")
LINEAR_RESIDUAL_MM = 0.006
STUDY_CASES = {
    -0.35: 0.11570,
    -0.25: 0.17760,
    -0.15: 0.23685,
    +0.15: 0.41222,
}
for _dc, _measured in STUDY_CASES.items():
    if abs(_measured - (NOMINAL_TIGHT_BACKLASH_MM + KC * _dc)) > LINEAR_RESIDUAL_MM:
        raise AssertionError("mesh linear residual does not cover the measured centre-distance cases")

_RUNNING = tuple(float(v) for v in _config.fit("shaft_in_bushing")["diametral_clearance_mm"])
PLAN_DX_PER_DEG = 0.444
STATION_64T_DC = 0.015
# The outboard land starts at a fixed dome-root station; the inboard end
# prints from the far end. A longer shaft therefore lengthens the supported
# span and moves its north limit, both carried into the float-at-rest budget.
CRANK_BEARING_LENGTH = (
    round(shaft.SHAFT_LENGTH - shaft.JOURNAL_START, shaft.STATION_PLACES)
    - shaft.JOURNAL_INBOARD_STATION - 2.0 * shaft.STATION_ROW
)
CRANK_SUPPORT_NORTH_MIN = (
    shaft.SHAFT_LENGTH + shaft.SHAFT_LENGTH_BAND[1]
    - shaft.JOURNAL_INBOARD_STATION - shaft.STATION_ROW
)
_FACE_UPPER = pinion.printed_deviations(pinion.FACE_WIDTH, pinion.FACE_WIDTH_PLACES)[1]
PINION_HALF_FACE_MAX = (pinion.FACE_WIDTH + _FACE_UPPER) / 2.0
CRANK_OVERHANG = (
    shaft.SEAT_PINION + pinion.SEAT_GAP_MAX_MM - pinion.SEAT_FEELER_MM
    + PINION_HALF_FACE_MAX - CRANK_SUPPORT_NORTH_MIN
)
CONE_OVERHANG = 5.68
MESH_LEVER = post.CRANK_BOSS_NORTH_FACE + pinion.SEAT_GAP_MAX_MM + PINION_HALF_FACE_MAX
POST_ANGLE_DEG = post.CRANK_BORE_ANGLE_LIMIT_DEG
POST_ANGLE_AT_MESH = MESH_LEVER * math.tan(math.radians(POST_ANGLE_DEG))
if not CRANK_BEARING_LENGTH > 0 and CRANK_SUPPORT_NORTH_MIN > 0 and CRANK_OVERHANG >= 0:
    raise AssertionError("crankshaft journal must support the 16T mesh plane")
if not MESH_LEVER > 0 and POST_ANGLE_AT_MESH > 0:
    raise AssertionError("post angularity must be carried into the worst tight-corner mesh budget")
TOOTH_RUNOUT_TIR_MM = 0.05
TIP_ROOT_BAND_RADIAL = max(pinion.OUTSIDE_DIA_TOLERANCE_MM, gear64.OUTSIDE_DIA_TOLERANCE_MM) / 2.0
if TIP_ROOT_BAND_RADIAL <= 0:
    raise AssertionError("gear tip-root tolerance must have a positive closing allowance")
# Exact-solid tip-diameter cases lost at most 0.00435; round outward.
TIP_BAND_CLOSE = -0.005
_YAW = {+1.0: 0.29715, -1.0: 0.22040}
_TILT = {+1.0: 0.34323, -1.0: 0.28188}


def _pose_loss(cases: dict[float, float], limit_deg: float) -> float:
    """Minimum quadratic pose change over the full permitted angle interval."""
    up = cases[+1.0] - NOMINAL_TIGHT_BACKLASH_MM
    down = cases[-1.0] - NOMINAL_TIGHT_BACKLASH_MM
    p, q = (up - down) / 2.0, (up + down) / 2.0
    angles = [-limit_deg, limit_deg]
    if q > 0 and abs(-p / (2.0 * q)) < limit_deg:
        angles.append(-p / (2.0 * q))
    return min(p * t + q * t * t for t in angles)


def _float_at_rest(clearance: float, bearing_length: float, overhang: float) -> float:
    return clearance / 2.0 + clearance / bearing_length * overhang


@dataclass(frozen=True)
class Term:
    name: str
    tight: float


def stack_terms(*, spacing_printed: float, plan_limit_deg: float, crank_angle_deg: float, crank_bearing_length: float) -> tuple[Term, ...]:
    """Closing corner, including gravity, print bands, runout and axis pose."""
    plan_dc = PLAN_DX_PER_DEG * plan_limit_deg * DC_PER_DX
    post_at_mesh = MESH_LEVER * math.tan(math.radians(plan_limit_deg))
    return (
        Term("crank bore spacing", KC * (spacing_printed + post.CRANK_ABOVE_CONE_BAND[1] - FRAME_DY) * DC_PER_DY),
        Term("cone bore plan angle", -KC * plan_dc),
        Term("64T axial station", -KC * STATION_64T_DC),
        Term("crank float at rest", -KC * _float_at_rest(_RUNNING[1], crank_bearing_length, CRANK_OVERHANG) * DC_PER_DY),
        Term("cone float at rest", KC * _float_at_rest(_RUNNING[0], post.CONE_BOSS_LENGTH, CONE_OVERHANG) * DC_PER_DY),
        Term("gear bore runout", -KC * (pinion.BORE_DIAMETRAL_CLEARANCE[1] + RETAINED_JOINT_CLEARANCE[1]) / 2.0),
        Term("tooth-to-bore cutting runout", -KC * TOOTH_RUNOUT_TIR_MM),
        Term("tip diameter band", TIP_BAND_CLOSE),
        Term("64T tooth thickness", -K64 * crank_drive_gear_notes.TOOTH_THICKNESS_DEVIATIONS[0]),
        Term("16T tooth thickness", -K16 * pinion.TOOTH_THICKNESS_UPPER_DEVIATION),
        Term("crank axis yaw", _pose_loss(_YAW, crank_angle_deg)),
        Term("crank axis tilt", _pose_loss(_TILT, crank_angle_deg)),
        Term("post frame angle at the mesh", -KC * post_at_mesh),
        Term("linear-model residual", -LINEAR_RESIDUAL_MM),
    )


SPACING_PRINTED = round(post.CRANK_ABOVE_CONE, post.DRAWING_PRECISION_BY_NAME["CrankAboveCone"])
if abs(SPACING_PRINTED - FRAME_DY) >= 0.01:
    raise AssertionError("printed post bore spacing diverges from the mesh reference")
TERMS = stack_terms(spacing_printed=SPACING_PRINTED, plan_limit_deg=POST_ANGLE_DEG, crank_angle_deg=POST_ANGLE_DEG, crank_bearing_length=CRANK_BEARING_LENGTH)
TIGHT_BACKLASH_MM = NOMINAL_TIGHT_BACKLASH_MM + sum(t.tight for t in TERMS)
if TIGHT_BACKLASH_MM <= 0.0:
    raise AssertionError("fixed-centre 16T:64T mesh binds at the worst tight corner (user ruling 2026-09-28)")


def stack_text() -> str:
    return "\n".join([
        f"fixed-centre crank mesh: conservative reference C {FRAME_C2C:.3f}; post angularity {POST_ANGLE_DEG:.4f} deg",
        f"  worst supported span {CRANK_BEARING_LENGTH:.4f}, north support {CRANK_SUPPORT_NORTH_MIN:.4f}, overhang {CRANK_OVERHANG:.4f} mm",
        *[f"  {t.name:38s} {t.tight:+.5f} mm backlash" for t in TERMS],
        f"  worst-case tight backlash {TIGHT_BACKLASH_MM:.5f} mm > 0 (no backlash window)",
    ])


if __name__ == "__main__":
    print(stack_text())
