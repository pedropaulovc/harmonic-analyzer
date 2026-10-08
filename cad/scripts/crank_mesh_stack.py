"""Fixed-centre 16T:64T tight-backlash stack (user ruling 2026-09-28).

No backlash window or adjustable axis: the printed post-bore angularity and
spacing must leave positive backlash at the worst closing corner. Slopes and
pose readings below come from nine-phase normal-24DP PA20 studies at the
48DP cone incline; the native interference gate still checks the real face.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import _config
import dt_cone_pivot_post_spec as post
import dt_crank_drive_gear_notes
import dt_crank_drive_gear_spec as gear64
import dt_crank_pinion_spec as pinion
import dt_crankshaft_spec as shaft
from cone_line import COS_I, POST_STATION, SIN_I
from cone_stack_end_play import CONE_FLOAT_NORTH
from dt_cone_pivot_post_installation import GEAR_AXIS_SHIFT
from gear_seat_fit import GEAR_SEAT_CLEARANCE

R64 = gear64.PITCH_DIA / 2.0
R16 = pinion.PITCH_DIA / 2.0
FRAME_C2C = R64 + R16 + _config.fit("crank_mesh", "c2c_slack_mm")
# The configured post height closes the pair at the physical 64T centre,
# rather than the retired all-transverse-pitch reference plane.
FRAME_DY = post.CRANK_BORE_HEIGHT - post.BORE_HEIGHT
FRAME_DX = math.sqrt(FRAME_C2C**2 - FRAME_DY**2)
DC_PER_DY = FRAME_DY / FRAME_C2C
DC_PER_DX = FRAME_DX / FRAME_C2C
GEAR64_POST_OFFSET = (
    gear64.LAYOUT_CENTRE_STATION + GEAR_AXIS_SHIFT + gear64.CENTRE_SHIFT_NORTH
    - POST_STATION
)
if not R64 > R16 > 0 or not FRAME_C2C > FRAME_DY > 0:
    raise AssertionError("fixed-centre mesh geometry needs ordered radii and real axis spacing")
if not math.isclose(DC_PER_DX**2 + DC_PER_DY**2, 1.0):
    raise AssertionError("mesh centre-distance projections must be orthonormal")

# Normal-24DP PA20 pair at the derived 48DP cone incline: nine phases per
# case in gstd-inch-train-measure1.jsonl and gstd-inch-train-poses1.jsonl.
NOMINAL_TIGHT_BACKLASH_MM = 0.30434519716270647
KC = (0.41892560804330814 - 0.19236232708292442) / 0.300
K64 = (0.4018972850157124 - 0.20794757188784255) / 0.20
K16 = (0.35427570366735156 - 0.30434519716270647) / 0.05
if not (KC > 0 and K64 > 0 and K16 > 0):
    raise AssertionError("measured mesh sensitivities must preserve the tight-corner sign")
LINEAR_RESIDUAL_MM = 0.007  # measured maximum 0.006783, rounded outward
STUDY_CASES = {
    -0.15: 0.19236232708292442,
    -0.075: 0.24792083865601214,
    +0.075: 0.3614910947807395,
    +0.15: 0.41892560804330814,
    +0.30: 0.5376909457696748,
}
for _dc, _measured in STUDY_CASES.items():
    if abs(_measured - (NOMINAL_TIGHT_BACKLASH_MM + KC * _dc)) > LINEAR_RESIDUAL_MM:
        raise AssertionError("mesh linear residual does not cover the measured centre-distance cases")

_RUNNING = tuple(float(v) for v in _config.fit("shaft_in_bushing")["diametral_clearance_mm"])
# Outward bound including the printed station stack and north contact lever.
PLAN_DX_PER_DEG = 0.487
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
_FACE_UPPER = pinion.printed_deviations(
    pinion.FACE_WIDTH, pinion.FACE_WIDTH_PLACES, pinion.FACE_WIDTH_LIMITS
)[1]
PINION_HALF_FACE_MAX = (pinion.FACE_WIDTH + _FACE_UPPER) / 2.0
CRANK_OVERHANG = (
    shaft.SEAT_PINION + pinion.SEAT_GAP_MAX_MM - pinion.SEAT_FEELER_MM
    + PINION_HALF_FACE_MAX - CRANK_SUPPORT_NORTH_MIN
)
CONE_OVERHANG = GEAR64_POST_OFFSET - post.CONE_BOSS_LENGTH / 2.0
MESH_LEVER = post.CRANK_BOSS_NORTH_FACE + pinion.SEAT_GAP_MAX_MM + PINION_HALF_FACE_MAX
POST_ANGLE_DEG = post.CRANK_BORE_ANGLE_LIMIT_DEG
POST_ANGLE_AT_MESH = MESH_LEVER * math.tan(math.radians(POST_ANGLE_DEG))
if not (CRANK_BEARING_LENGTH > 0 and CRANK_SUPPORT_NORTH_MIN > 0 and CRANK_OVERHANG >= 0):
    raise AssertionError("crankshaft journal must support the 16T mesh plane")
if not (MESH_LEVER > 0 and POST_ANGLE_AT_MESH > 0):
    raise AssertionError("post angularity must be carried into the worst tight-corner mesh budget")
TOOTH_RUNOUT_TIR_MM = 0.05
TIP_ROOT_BAND_RADIAL = max(pinion.OUTSIDE_DIA_TOLERANCE_MM, gear64.OUTSIDE_DIA_TOLERANCE_MM) / 2.0
if TIP_ROOT_BAND_RADIAL <= 0:
    raise AssertionError("gear tip-root tolerance must have a positive closing allowance")
# Low-tip controls lose at most 0.002021 mm; retain the outward allowance.
TIP_BAND_CLOSE = -0.005
_YAW = {+1.0: 0.23608759723005585, -1.0: 0.28962579929139487}
_TILT = {+1.0: 0.3444627717531438, -1.0: 0.26105285048237836}


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
        Term("gear bore runout", -KC * (pinion.BORE_DIAMETRAL_CLEARANCE[1] + GEAR_SEAT_CLEARANCE[1]) / 2.0),
        Term("tooth-to-bore cutting runout", -KC * TOOTH_RUNOUT_TIR_MM),
        Term("tip diameter band", TIP_BAND_CLOSE),
        Term("64T tooth thickness", -K64 * dt_crank_drive_gear_notes.TOOTH_THICKNESS_DEVIATIONS[0]),
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


# --- Contact ratio at the open corner (user ruling 2026-09-30) -------------
# TERMS is the closing corner. Least engagement is the other one: the bore
# spacing at its +0.37 end and every centre term at the end that parts the
# axes, the cone shaft floating on its largest running clearance. Only centre
# translations enter; tooth thinning, the fitted pose losses and the linear
# residual move no centre. The 64T stands at its model pose at the closing
# corner (the stack's south stop) and floats north at the open one.
def open_terms(*, spacing_printed: float, plan_limit_deg: float, crank_bearing_length: float) -> dict[str, float]:
    """Centre-distance opening (mm) per term at the open corner."""
    return {
        "crank bore spacing": (spacing_printed + post.CRANK_ABOVE_CONE_BAND[0] - FRAME_DY) * DC_PER_DY,
        "cone bore plan angle": PLAN_DX_PER_DEG * plan_limit_deg * DC_PER_DX,
        "64T axial station": STATION_64T_DC,
        # The stack's north float slides the 64T up the inclined cone axis,
        # lengthening the in-plane horizontal leg by F*sin(i)*cos(i). Booked
        # linearly on the physical frame's DC_PER_DX. The assembly also
        # checks the unchanged contact-ratio floor using exact float opening.
        "cone stack north float": CONE_FLOAT_NORTH * SIN_I * COS_I * DC_PER_DX,
        "crank float at rest": _float_at_rest(_RUNNING[1], crank_bearing_length, CRANK_OVERHANG) * DC_PER_DY,
        "cone float at rest": _float_at_rest(_RUNNING[1], post.CONE_BOSS_LENGTH, CONE_OVERHANG) * DC_PER_DY,
        "gear bore runout": (pinion.BORE_DIAMETRAL_CLEARANCE[1] + GEAR_SEAT_CLEARANCE[1]) / 2.0,
        "tooth-to-bore cutting runout": TOOTH_RUNOUT_TIR_MM,
        "post frame angle at the mesh": MESH_LEVER * math.tan(math.radians(plan_limit_deg)),
    }


OPEN_TERMS = open_terms(spacing_printed=SPACING_PRINTED, plan_limit_deg=POST_ANGLE_DEG, crank_bearing_length=CRANK_BEARING_LENGTH)
OPEN_CENTRE_DISTANCE_MM = sum(OPEN_TERMS.values())
if min(OPEN_TERMS.values()) < 0.0:
    raise AssertionError("an open-corner centre term closes the mesh")

# The 16T is spur, cut square by the 64T's normal-plane cutter; the 64T is a
# helix crossed on the inclined cone axis. The ratio is screened in the 64T's
# normal section (the 16T's transverse section): the 64T takes its equivalent
# radius R/cos^2(helix), keeping its addendum and the centre opening, and both
# share the cutter's base pitch.
_CUTTER_PA = math.radians(gear64.CUTTER_PRESSURE_ANGLE_DEG)
EQUIVALENT_RADIUS_GROWTH_64 = R64 / math.cos(math.radians(gear64.HELIX_ANGLE_DEG)) ** 2 - R64
BASE_PITCH_MM = math.pi * gear64.NORMAL_MODULE_MM * math.cos(_CUTTER_PA)


def contact_ratio(*, centre_distance: float, tip_dia_16: float, tip_dia_64: float) -> float:
    """16T:64T contact ratio at ``centre_distance`` with the two tip diameters."""
    grow = EQUIVALENT_RADIUS_GROWTH_64
    rb16 = pinion.PITCH_DIA / 2.0 * math.cos(_CUTTER_PA)
    rb64 = (R64 + grow) * math.cos(_CUTTER_PA)
    q16 = math.sqrt((tip_dia_16 / 2.0) ** 2 - rb16**2)
    q64 = math.sqrt((tip_dia_64 / 2.0 + grow) ** 2 - rb64**2)
    line = math.sqrt((centre_distance + grow) ** 2 - (rb16 + rb64) ** 2)
    return (min(q16, line) - max(line - q64, 0.0)) / BASE_PITCH_MM


def printed_tip_low(outside_dia: float, places: int, tolerance: float) -> float:
    """The smallest tip diameter the sheet accepts: printed nominal less its band."""
    return round(outside_dia, places) - tolerance


TIP_DIA_LOW_16 = printed_tip_low(pinion.OUTSIDE_DIA, pinion.DRAWING_PRECISION_BY_NAME["OutsideDia"], pinion.OUTSIDE_DIA_TOLERANCE_MM)
TIP_DIA_LOW_64 = printed_tip_low(gear64.OUTSIDE_DIA, gear64.DRAWING_PRECISION_BY_NAME["OutsideDia"], gear64.OUTSIDE_DIA_TOLERANCE_MM)


def stack_text() -> str:
    return "\n".join([
        f"fixed-centre crank mesh: physical reference C {FRAME_C2C:.3f}; post angularity {POST_ANGLE_DEG:.4f} deg",
        f"  worst supported span {CRANK_BEARING_LENGTH:.4f}, north support {CRANK_SUPPORT_NORTH_MIN:.4f}, overhang {CRANK_OVERHANG:.4f} mm",
        *[f"  {t.name:38s} {t.tight:+.5f} mm backlash" for t in TERMS],
        f"  worst-case tight backlash {TIGHT_BACKLASH_MM:.5f} mm > 0 (no backlash window)",
    ])


if __name__ == "__main__":
    print(stack_text())
