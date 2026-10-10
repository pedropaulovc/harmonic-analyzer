"""Fixed-centre 16T:64T crossed mesh: dimensional stack and standard check.

The 64T is a right-hand helix on the inclined cone axis, cut with the same
normal 24DP PA20 stock cutter as the straight 16T. It is checked as an
ordinary crossed pair in the 64T's normal section: the 64T takes its virtual
radius R/cos^2(helix) and its thickness scales by cos(helix), while the 16T is
already in that plane (to within the 0.52 deg crossing). The centre range is
the closed-form sum of the printed and fitted terms below, each booked at the
end that closes or opens the mesh. Everything is read from part specs and
config. The native assembly interference gate checks the real flanks.
"""
from __future__ import annotations

import math
from dataclasses import replace

import _config
import dt_cone_pivot_post_spec as post
import dt_crank_drive_gear_spec as gear64
import dt_crank_pinion_spec as pinion
import dt_crankshaft_spec as shaft
import dt_cone_gear_shaft_spec as cone_shaft
from cone_line import COS_I, POST_STATION, SIN_I
from cone_stack_end_play import CONE_FLOAT_NORTH
from dt_cone_pivot_post_installation import GEAR_AXIS_SHIFT
from gear_seat_fit import GEAR_SEAT_CLEARANCE
from standard_mesh_checks import MeshCheck, check_mesh, plane_gear

R64 = gear64.PITCH_DIA / 2.0
R16 = pinion.PITCH_DIA / 2.0
FRAME_C2C = R64 + R16 + _config.fit("crank_mesh", "c2c_slack_mm")
FRAME_DY = post.CRANK_BORE_HEIGHT - post.BORE_HEIGHT
FRAME_DX = math.sqrt(FRAME_C2C**2 - FRAME_DY**2)
DC_PER_DY = FRAME_DY / FRAME_C2C
DC_PER_DX = FRAME_DX / FRAME_C2C
if not R64 > R16 > 0 or not FRAME_C2C > FRAME_DY > 0:
    raise AssertionError("fixed-centre mesh geometry needs ordered radii and real axis spacing")
GEAR64_POST_OFFSET = (
    gear64.LAYOUT_CENTRE_STATION + GEAR_AXIS_SHIFT + gear64.CENTRE_SHIFT_NORTH - POST_STATION
)
CRANK_RUNNING = shaft.JOURNAL_DIAMETRAL_CLEARANCE_MM
CONE_RUNNING = cone_shaft.JOURNAL_DIAMETRAL_CLEARANCE_MM
CRANK_BEARING_LENGTH = shaft.JOURNAL_SUPPORT_SPAN_MIN_MM
CONE_BEARING_LENGTH = cone_shaft.JOURNAL_SUPPORT_SPAN_MIN_MM
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
TOOTH_RUNOUT_TIR_MM = gear64.TOOTH_RUNOUT_TIR_MM
TIP_ROOT_BAND_RADIAL = max(pinion.OUTSIDE_DIA_TOLERANCE_MM, gear64.OUTSIDE_DIA_TOLERANCE_MM) / 2.0
SPACING_PRINTED = round(post.CRANK_ABOVE_CONE, post.DRAWING_PRECISION_BY_NAME["CrankAboveCone"])
if not (CRANK_BEARING_LENGTH > 0 and CRANK_SUPPORT_NORTH_MIN > 0 and CRANK_OVERHANG >= 0):
    raise AssertionError("crankshaft journal must support the 16T mesh plane")
if abs(SPACING_PRINTED - FRAME_DY) >= 0.01:
    raise AssertionError("printed post bore spacing diverges from the mesh reference")


def _float_at_rest(clearance: float, bearing_length: float, overhang: float) -> float:
    """Journal float at the mesh: c/2 plus the c/L tilt over the overhang."""
    return clearance / 2.0 + clearance / bearing_length * max(overhang, 0.0)


# Centre-distance terms (mm). Shaft floats and runouts can act either way;
# the printed spacing band and the cone stack's north float only open.
_SYMMETRIC_TERMS = {
    "crank float at rest": _float_at_rest(CRANK_RUNNING[1], CRANK_BEARING_LENGTH, CRANK_OVERHANG),
    "cone float at rest": _float_at_rest(CONE_RUNNING[1], CONE_BEARING_LENGTH, CONE_OVERHANG),
    "gear bore clearance": (pinion.BORE_DIAMETRAL_CLEARANCE[1] + GEAR_SEAT_CLEARANCE[1]) / 2.0,
    "tooth-to-bore cutting runout (both gears)": TOOTH_RUNOUT_TIR_MM,
    "post bore angularity at the mesh": MESH_LEVER * math.tan(math.radians(POST_ANGLE_DEG)),
}
CLOSING_TERMS = {
    **_SYMMETRIC_TERMS,
    "crank bore spacing": -(SPACING_PRINTED + post.CRANK_ABOVE_CONE_BAND[1] - FRAME_DY) * DC_PER_DY,
}
OPENING_TERMS = {
    **_SYMMETRIC_TERMS,
    "crank bore spacing": (SPACING_PRINTED + post.CRANK_ABOVE_CONE_BAND[0] - FRAME_DY) * DC_PER_DY,
    "cone stack north float": CONE_FLOAT_NORTH * SIN_I * COS_I * DC_PER_DX,
}
CENTRE_RANGE_MM = (
    FRAME_C2C - sum(max(v, 0.0) for v in CLOSING_TERMS.values()),
    FRAME_C2C + sum(max(v, 0.0) for v in OPENING_TERMS.values()),
)

_BETA = math.radians(gear64.HELIX_ANGLE_DEG)
EQUIVALENT_RADIUS_GROWTH_64 = R64 / math.cos(_BETA) ** 2 - R64


def _normal_section_64(profile):
    gear = plane_gear(profile, gear64.MODULE_MM, radius_growth=EQUIVALENT_RADIUS_GROWTH_64,
                      thickness_scale=math.cos(_BETA))
    return replace(gear, teeth=round(gear64.TEETH / math.cos(_BETA) ** 3))


def standard_check() -> MeshCheck:
    """AGMA-style closed-form check over every printed corner and the centre range."""
    grow = EQUIVALENT_RADIUS_GROWTH_64
    return check_mesh(
        "crank 16T/64T",
        (plane_gear(pinion.STOCK_PROFILE, pinion.MODULE_MM),
         _normal_section_64(gear64.STOCK_PROFILE), FRAME_C2C + grow),
        [plane_gear(profile, pinion.MODULE_MM) for _, profile in pinion.STOCK_PROFILE_CORNERS],
        [_normal_section_64(profile) for _, profile in gear64.STOCK_PROFILE_CORNERS],
        (CENTRE_RANGE_MM[0] + grow, CENTRE_RANGE_MM[1] + grow),
        gear64.CUTTER_PRESSURE_ANGLE_DEG,
        gear64.NORMAL_MODULE_MM,
    )


def stack_text() -> str:
    lines = [f"fixed-centre crank mesh: nominal C {FRAME_C2C:.4f} mm, range "
             f"{CENTRE_RANGE_MM[0]:.4f}..{CENTRE_RANGE_MM[1]:.4f} mm"]
    lines += [f"  closing {name:42s} {value:.5f}" for name, value in CLOSING_TERMS.items()]
    lines += [f"  opening {name:42s} {value:.5f}" for name, value in OPENING_TERMS.items()]
    lines.append("  " + standard_check().text())
    return "\n".join(lines)


if __name__ == "__main__":
    print(stack_text())
