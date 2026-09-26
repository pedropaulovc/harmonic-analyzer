r"""The 16T:64T crank-mesh fit-up stack, and the MHA-149 throw that absorbs it.

SolidWorks-free.  At fit-up the fitter turns the MHA-149 eccentric bushing in
MHA-016's crank bore until the crank mesh reads FITUP_BACKLASH_MM at its tight
spot, then bonds it (#906 R1).  Every other contributor to the mesh is a named
term below, each in mm of backlash at the tight spot and taken at the two
corners of the stack:

* ``tight`` -- everything that closes the mesh at its limit: the bushing must
  OPEN the centre distance far enough to lift the reading to the target;
* ``loose`` -- everything that opens it: the bushing must CLOSE it.

The bushing's reach is its throw at the bottom of its band, about the post
bore; the post bore's own place (``cone_pivot_post_spec.CRANK_BORE_DROP`` below
the frame's crank axis, plus its printed spacing band) is the first term, so
the reach is measured from the frame.  Import fails if either end runs out, if
the printed drop is not the one that centres the reach, or if a worst-case tip
can touch the mating root at the loose fit-up.

Where the numbers come from (``diagnostics/crank_mesh_backlash_study.py``,
exact tooth solids, min backlash over nine crank phases):

* the B-star cutter's centre-distance cases at -/+0.150 give KC (verifier's
  fit controls, 2026-09-26); the older B cases give the tooth-thinning slopes;
* the R1 cases (dt-logs/crankhub/crank-mesh-R1-fitup-20260926.jsonl) put the
  linear model within LINEAR_RESIDUAL_MM of the solids from -0.35 to +0.15 of
  centre distance, and within 0.002 at both R1 fit-up states;
* the pose cases (crankhub/crank-mesh-angle-20260926.jsonl) give the crank
  axis's yaw and tilt.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import _config
import cone_pivot_post_spec as post
import crank_drive_gear_notes
import crank_drive_gear_spec as gear64
import crank_eccentric_bushing_spec as bushing
import crank_pinion_spec as pinion
from retained_joint_fit import RETAINED_JOINT_CLEARANCE


# --- The fit-up requirement --------------------------------------------------
# The drive-train sheet's acceptance at the tight spot, set by the bushing.
FITUP_BACKLASH_MM = 0.25
FITUP_BACKLASH_BAND_MM = 0.03

# --- The frame ---------------------------------------------------------------
# build_drive_train_assembly's MESH16_C2C: both radii at the transverse DP plus
# the crank_mesh slack (39.735), with the crank axis CRANK_AXIS_HEIGHT above
# the post foot and the cone axis BORE_HEIGHT above it.
R64 = gear64.PITCH_DIA / 2.0
R16 = (16.0 / gear64.DIAMETRAL_PITCH) * gear64.MM_PER_IN / 2.0
FRAME_C2C = R64 + R16 + _config.fit("crank_mesh", "c2c_slack_mm")
FRAME_DY = post.CRANK_AXIS_HEIGHT - post.BORE_HEIGHT  # 39.332
FRAME_DX = math.sqrt(FRAME_C2C**2 - FRAME_DY**2)
DC_PER_DY = FRAME_DY / FRAME_C2C  # 0.990
DC_PER_DX = FRAME_DX / FRAME_C2C  # 0.142

# --- The study -------------------------------------------------------------
_EXTRA_NOMINAL = 0.4225696498924991  # FRAME_C2C - R64 - R16
NOMINAL_TIGHT_BACKLASH_MM = 0.32269  # Bstar0
_BSTAR_CD = {-0.150: 0.23685, +0.150: 0.41222}  # B-star, centre distance -/+0.150
_B_THIN64 = {0.05: 0.22079, 0.25: 0.41722}  # 64T thinned 0.05 / 0.25
_B_THIN16 = {0.00: 0.31888, 0.05: 0.36930}  # 16T thinned 0 / 0.05
KC = (_BSTAR_CD[0.150] - _BSTAR_CD[-0.150]) / 0.300  # per mm of centre distance
K64 = (_B_THIN64[0.25] - _B_THIN64[0.05]) / 0.20  # per mm of 64T thinning
K16 = (_B_THIN16[0.05] - _B_THIN16[0.00]) / 0.05  # per mm of 16T thinning
# (centre-distance offset from the frame, 64T thinning, 16T thinning, backlash)
STUDY_CHECKS = {
    "Bstar-cd-0.35": (-0.35, 0.15, 0.00, 0.11570),
    "Bstar-cd-0.25": (-0.25, 0.15, 0.00, 0.17760),
    "Bstar-cd-0.15": (-0.15, 0.15, 0.00, 0.23685),
    "Bstar-cd+0.15": (+0.15, 0.15, 0.00, 0.41222),
    "R1-tight-fitup": (0.4664672651183648 - _EXTRA_NOMINAL, 0.05, 0.00, 0.25110),
    "R1-loose-fitup": (0.17841893904636286 - _EXTRA_NOMINAL, 0.20, 0.02, 0.24830),
}
LINEAR_RESIDUAL_MM = 0.0035
# Pose cases, min backlash with the crank axis turned 1 deg about each axis.
_YAW = {+1.0: 0.29715, -1.0: 0.22040}
_TILT = {+1.0: 0.34323, -1.0: 0.28188}


def _linear_backlash(dc: float, thin64: float, thin16: float) -> float:
    return (
        NOMINAL_TIGHT_BACKLASH_MM
        + KC * dc
        + K64 * (thin64 - gear64.BACKLASH_MM)
        + K16 * thin16
    )


for _case, (_dc, _w64, _w16, _measured) in STUDY_CHECKS.items():
    if abs(_measured - _linear_backlash(_dc, _w64, _w16)) > LINEAR_RESIDUAL_MM + 1e-4:
        raise AssertionError(f"{_case}: the linear mesh model left its measured residual")


def _pose_range(cases: dict[float, float], limit_deg: float) -> tuple[float, float]:
    """(min, max) backlash change over +/-limit_deg from the +/-1 deg pair,
    fitted as p*t + q*t^2 through the nominal."""
    up = cases[+1.0] - NOMINAL_TIGHT_BACKLASH_MM
    down = cases[-1.0] - NOMINAL_TIGHT_BACKLASH_MM
    p, q = (up - down) / 2.0, (up + down) / 2.0
    samples = [limit_deg * k / 20.0 for k in range(-20, 21)]
    values = [p * t + q * t * t for t in samples]
    return min(values), max(values)


# --- Geometry each term reads ------------------------------------------------
_RUNNING = tuple(
    float(v) for v in _config.fit("shaft_in_bushing")["diametral_clearance_mm"]
)
_ROW_1 = float(str(_config.title_block("linear_1pl")["display"]).lstrip("±"))
_ROW_2 = float(str(_config.title_block("linear_2pl")["display"]).lstrip("±"))
# The cone bore's plan angle turns the 64T, 26.69 out along the cone shaft
# from the post axis, sideways by this much per degree (U31 table,
# cone_pivot_post_spec).
PLAN_DX_PER_DEG = 0.444
# The 64T's axial station on the inclined shaft, +/-0.5, moves the centre
# distance this much (U31 table).
STATION_64T_DC = 0.015
# Mesh mid-face overhangs past each bearing's inboard end (U31 table).
CRANK_OVERHANG = 5.65
CONE_OVERHANG = 5.68
# The 16T's mid-face stands this far north of the boss's spot face (the widest
# seat gap + half the face), where the bushing's north end sits flush.  The
# crank bore's spacing is inspected at the post axis, so a post angle error
# moves the mesh by MESH_LEVER.
PINION_BEYOND_BUSHING = pinion.SEAT_GAP_MAX_MM + pinion.FACE_WIDTH / 2.0
MESH_LEVER = post.CRANK_BOSS_NORTH_FACE + PINION_BEYOND_BUSHING

# The crank axis's angle budget: the post's angularity frame, the bushing
# bore's parallelism to its OD, and the bushing cocking in its g6/H7 seat
# before the compound cures.
POST_ANGLE_DEG = post.CRANK_BORE_ANGLE_LIMIT_DEG
BUSHING_ANGLE_DEG = math.degrees(math.atan(bushing.BORE_PARALLELISM_MM / bushing.LENGTH))
SEAT_CLEARANCE_MAX = post.CRANK_BORE_BAND[0] - bushing.OD_BAND[1]
SEAT_COCK_DEG = math.degrees(math.atan(SEAT_CLEARANCE_MAX / bushing.POST_BORE_LENGTH))
CRANK_ANGLE_DEG = POST_ANGLE_DEG + BUSHING_ANGLE_DEG + SEAT_COCK_DEG
# What each of them moves the 16T's mid-face by, in any direction (so, at
# worst, along the line of centres): the post's frame about the inspection
# point, the bushing's two about the bushing's own length.
POST_ANGLE_AT_MESH = MESH_LEVER * math.tan(math.radians(POST_ANGLE_DEG))
BUSHING_BORE_AT_MESH = bushing.BORE_PARALLELISM_MM / 2.0 + (
    bushing.BORE_PARALLELISM_MM / bushing.LENGTH * PINION_BEYOND_BUSHING
)
SEAT_AT_MESH = SEAT_CLEARANCE_MAX / 2.0 + (
    SEAT_CLEARANCE_MAX / bushing.POST_BORE_LENGTH * PINION_BEYOND_BUSHING
)

# Cutting runout of each gear's teeth to its own bore: not on either sheet
# today.  Proposed at this TIR on both gear-data blocks; carried here as a
# reach term so the throw covers it.
TOOTH_RUNOUT_TIR_MM = 0.05


def _float_at_rest(clearance: float, bearing_length: float, overhang: float) -> float:
    """Radial drop of a shaft in a bearing of that diametral clearance, plus
    its tilt carried out to the mesh."""
    return clearance / 2.0 + clearance / bearing_length * overhang


@dataclass(frozen=True)
class Term:
    name: str
    tight: float  # backlash at the closing corner, mm (<= 0 closes)
    loose: float  # backlash at the opening corner, mm


def stack_terms(
    *,
    spacing_printed: float,
    plan_limit_deg: float,
    crank_angle_deg: float,
    crank_bearing_length: float,
) -> tuple[Term, ...]:
    """Every contributor but the bushing, relative to the frame's nominal."""
    band_high = post.CRANK_ABOVE_CONE_BAND[0]
    band_low = post.CRANK_ABOVE_CONE_BAND[1]
    plan_dc = PLAN_DX_PER_DEG * plan_limit_deg * DC_PER_DX
    post_at_mesh = MESH_LEVER * math.tan(math.radians(plan_limit_deg))
    thick64_high, thin64_low = crank_drive_gear_notes.TOOTH_THICKNESS_DEVIATIONS
    yaw = _pose_range(_YAW, crank_angle_deg)
    tilt = _pose_range(_TILT, crank_angle_deg)
    crank_float = [
        _float_at_rest(c, crank_bearing_length, CRANK_OVERHANG) for c in _RUNNING
    ]
    cone_float = [
        _float_at_rest(c, post.CONE_BOSS_LENGTH, CONE_OVERHANG) for c in _RUNNING
    ]
    return (
        # The printed crank-above-cone spacing, placed against the frame: R1's
        # bore sits CRANK_BORE_DROP low, so its whole band is below the frame.
        Term(
            "crank bore spacing (printed band, from the frame)",
            KC * (spacing_printed + band_low - FRAME_DY) * DC_PER_DY,
            KC * (spacing_printed + band_high - FRAME_DY) * DC_PER_DY,
        ),
        Term("cone bore plan angle", -KC * plan_dc, KC * plan_dc),
        Term("64T axial station", -KC * STATION_64T_DC, KC * STATION_64T_DC),
        # At rest both shafts sag: the crank toward the 64T, the cone shaft
        # away from the crank.  Each corner takes one at its largest clearance
        # and the other at its smallest.
        Term(
            "crank float at rest",
            -KC * crank_float[1] * DC_PER_DY,
            -KC * crank_float[0] * DC_PER_DY,
        ),
        Term(
            "cone float at rest",
            KC * cone_float[0] * DC_PER_DY,
            KC * cone_float[1] * DC_PER_DY,
        ),
        # A gear offset on its bore, or cut out of true to it, puts the
        # closing side at the tight spot, so each only ever closes there.
        Term(
            "gear bore runout (16T slip, 64T bonded)",
            -KC * (pinion.BORE_DIAMETRAL_CLEARANCE[1] + RETAINED_JOINT_CLEARANCE[1]) / 2.0,
            0.0,
        ),
        Term("tooth-to-bore cutting runout (proposed)", -KC * TOOTH_RUNOUT_TIR_MM, 0.0),
        Term("64T tooth thickness", -K64 * thick64_high, -K64 * thin64_low),
        Term(
            "16T tooth thickness",
            -K16 * pinion.TOOTH_THICKNESS_UPPER_DEVIATION,
            -K16 * pinion.TOOTH_THICKNESS_LOWER_DEVIATION,
        ),
        # Yaw and tilt each at the full budget: a diametral zone bounds their
        # vector sum, so this is up to sqrt(2) conservative.
        Term("crank axis yaw", yaw[0], yaw[1]),
        Term("crank axis tilt", tilt[0], tilt[1]),
        Term("post frame angle at the mesh", -KC * post_at_mesh, KC * post_at_mesh),
        Term("bushing bore parallelism at the mesh", -KC * BUSHING_BORE_AT_MESH, KC * BUSHING_BORE_AT_MESH),
        Term("bushing seated in its clearance, at the mesh", -KC * SEAT_AT_MESH, KC * SEAT_AT_MESH),
        Term("linear-model residual", -LINEAR_RESIDUAL_MM, LINEAR_RESIDUAL_MM),
    )


def _corner_backlash(terms: tuple[Term, ...]) -> tuple[float, float]:
    return (
        NOMINAL_TIGHT_BACKLASH_MM + sum(t.tight for t in terms),
        NOMINAL_TIGHT_BACKLASH_MM + sum(t.loose for t in terms),
    )


# --- R1 as printed -----------------------------------------------------------
_SPACING_PLACES = post.DRAWING_PRECISION_BY_NAME["CrankAboveCone"]
SPACING_PRINTED = round(post.CRANK_ABOVE_CONE, _SPACING_PLACES)
CRANK_BEARING_LENGTH = bushing.LENGTH - _ROW_1
TERMS = stack_terms(
    spacing_printed=SPACING_PRINTED,
    plan_limit_deg=POST_ANGLE_DEG,
    crank_angle_deg=CRANK_ANGLE_DEG,
    crank_bearing_length=CRANK_BEARING_LENGTH,
)
TIGHT_BACKLASH_MM, LOOSE_BACKLASH_MM = _corner_backlash(TERMS)
# Centre distance the bushing must supply, from the post bore's place.
OPEN_NEEDED = (FITUP_BACKLASH_MM - TIGHT_BACKLASH_MM) / KC
CLOSE_NEEDED = (LOOSE_BACKLASH_MM - FITUP_BACKLASH_MM) / KC
THROW_REACH = bushing.ECCENTRICITY + bushing.ECCENTRICITY_BAND[1]
OPEN_MARGIN = THROW_REACH - OPEN_NEEDED
CLOSE_MARGIN = THROW_REACH - CLOSE_NEEDED
# The drop that centres the reach on the window, at the spacing's printed
# places: raising the bore by d opens both corners by KC * d * DC_PER_DY.
IDEAL_DROP = post.CRANK_BORE_DROP + (OPEN_MARGIN - CLOSE_MARGIN) / (2.0 * DC_PER_DY)
if round(IDEAL_DROP, _SPACING_PLACES) != post.CRANK_BORE_DROP:
    raise AssertionError(
        f"cone_pivot_post_spec.CRANK_BORE_DROP {post.CRANK_BORE_DROP} is not the "
        f"drop that centres the MHA-149 reach ({IDEAL_DROP:.4f})"
    )

# --- Tips against roots at the loose fit-up ----------------------------------
# The closest the pair ever runs: the loose corner with the bushing closed to
# the target.  Each gear's tip can print a whole .XX row over nominal
# (crank_pinion_spec / crank_drive_gear_spec OD notes) and sit on its cutting
# runout; the other gear's root is cut to depth.
_POSE_LOOSE = sum(
    t.loose for t in TERMS
    if t.name in ("crank axis yaw", "crank axis tilt", "linear-model residual")
)
_LOOSE_NET_DC = (
    FITUP_BACKLASH_MM
    - _POSE_LOOSE
    - _linear_backlash(
        0.0,
        gear64.BACKLASH_MM - crank_drive_gear_notes.TOOTH_THICKNESS_DEVIATIONS[1],
        -pinion.TOOTH_THICKNESS_LOWER_DEVIATION,
    )
) / KC
# Either gear's tip into the other's root: the smaller tooth-system tip
# clearance, less the general .XX band on a tip circle, taken radially.
TIP_CLEARANCE_MM = min(pinion.TIP_CLEARANCE_MM, gear64.TIP_CLEARANCE_MM)
TIP_ROOT_BAND_RADIAL = _ROW_2 / 2.0
TIP_ROOT_AIR_WORST = (
    _EXTRA_NOMINAL
    + _LOOSE_NET_DC
    + TIP_CLEARANCE_MM
    - TIP_ROOT_BAND_RADIAL
    - TOOTH_RUNOUT_TIR_MM / 2.0
)
if TIP_ROOT_AIR_WORST <= 0.0:
    raise AssertionError(
        f"a worst-case tip can reach the mating root at the loose fit-up "
        f"({TIP_ROOT_AIR_WORST:.3f})"
    )

# --- The acceptance budget after bonding ------------------------------------
# The g6 OD can settle anywhere in the H7 bore while the compound cures; that
# moves the set centre distance by up to half the seat clearance.
RESEAT_DC = SEAT_AT_MESH
RESEAT_BACKLASH = KC * RESEAT_DC
READING_ALLOWANCE = FITUP_BACKLASH_BAND_MM - RESEAT_BACKLASH


def stack_text() -> str:
    lines = [
        f"crank mesh fit-up stack: target {FITUP_BACKLASH_MM:.2f} "
        f"+/-{FITUP_BACKLASH_BAND_MM:.2f} at the tight spot; KC {KC:.4f}, "
        f"K64 {K64:.3f}, K16 {K16:.3f}; frame C {FRAME_C2C:.3f}, "
        f"DY/C {DC_PER_DY:.4f}, DX/C {DC_PER_DX:.4f}",
        f"  crank angle budget {CRANK_ANGLE_DEG:.4f} deg (post {POST_ANGLE_DEG:.4f} + "
        f"bushing {BUSHING_ANGLE_DEG:.4f} + seat {SEAT_COCK_DEG:.4f}); mesh lever "
        f"{MESH_LEVER:.3f}; at the mesh: post {POST_ANGLE_AT_MESH:.4f}, bushing bore "
        f"{BUSHING_BORE_AT_MESH:.4f}, seat {SEAT_AT_MESH:.4f}",
        f"  {'term':52s} {'tight':>8s} {'loose':>8s}  (backlash mm)",
    ]
    lines += [f"  {t.name:52s} {t.tight:+8.4f} {t.loose:+8.4f}" for t in TERMS]
    lines += [
        f"  corner backlash before the bushing: tight {TIGHT_BACKLASH_MM:.4f}, "
        f"loose {LOOSE_BACKLASH_MM:.4f}",
        f"  bushing must open {OPEN_NEEDED:.4f} and close {CLOSE_NEEDED:.4f}; "
        f"throw reach {THROW_REACH:.3f}",
        f"  margin: open {OPEN_MARGIN:+.4f}, close {CLOSE_MARGIN:+.4f}; drop "
        f"{post.CRANK_BORE_DROP} (ideal {IDEAL_DROP:.4f})",
        f"  tip-root air at the loose fit-up, worst: {TIP_ROOT_AIR_WORST:.4f}",
        f"  bonding re-seat {RESEAT_DC:.4f} dC = {RESEAT_BACKLASH:.4f} backlash; "
        f"{READING_ALLOWANCE:.4f} of the +/-{FITUP_BACKLASH_BAND_MM:.2f} left for the reading",
    ]
    return "\n".join(lines)


if OPEN_MARGIN < 0.0 or CLOSE_MARGIN < 0.0:
    raise AssertionError(
        "the MHA-149 throw does not reach both ends of the crank-mesh stack\n"
        + stack_text()
    )
if READING_ALLOWANCE <= 0.0:
    raise AssertionError(
        "the bushing's bonding re-seat alone uses the fit-up acceptance\n" + stack_text()
    )


if __name__ == "__main__":
    print(stack_text())
