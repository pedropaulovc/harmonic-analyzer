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
the reach is measured from the frame.  Import fails if either end runs out.

Where the numbers come from:

* ``diagnostics/crank_mesh_backlash_study.py`` -- exact tooth solids, min
  backlash over nine crank phases.  Its slopes (the ``B-*`` cases,
  dt-logs/crank-mesh-C-B-20260925.jsonl) give backlash per mm of centre
  distance and of tooth thinning; its ``Bstar*`` cases
  (crank-mesh-C-Bstar-20260925.jsonl) give the frame's nominal and the two
  measured corners; the pose cases (crankhub/crank-mesh-angle-20260926.jsonl)
  give the crank axis's yaw and tilt.
* KC was fitted over -0.150..+0.150 of centre distance.  The fit-up asks it to
  hold out to about -0.77 (the bushing fully closed at the loose corner).  The
  loose corner at +0.49 already reads +0.019 above the linear model, so that
  measured excess is carried as a term; nothing was measured past -0.15.
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
FRAME_C2C = (
    gear64.PITCH_DIA / 2.0
    + (16.0 / gear64.DIAMETRAL_PITCH) * gear64.MM_PER_IN / 2.0
    + _config.fit("crank_mesh", "c2c_slack_mm")
)
FRAME_DY = post.CRANK_AXIS_HEIGHT - post.BORE_HEIGHT  # 39.332
FRAME_DX = math.sqrt(FRAME_C2C**2 - FRAME_DY**2)
DC_PER_DY = FRAME_DY / FRAME_C2C  # 0.990
DC_PER_DX = FRAME_DX / FRAME_C2C  # 0.142

# --- The study -------------------------------------------------------------
# Min backlash over nine crank phases (mm).  Slopes from the B cases:
_B_CD = {-0.150: 0.23172, +0.150: 0.40616}  # centre distance -/+0.150
_B_THIN64 = {0.05: 0.22079, 0.25: 0.41722}  # 64T thinned 0.05 / 0.25
_B_THIN16 = {0.00: 0.31888, 0.05: 0.36930}  # 16T thinned 0 / 0.05
KC = (_B_CD[0.150] - _B_CD[-0.150]) / 0.300  # per mm of centre distance
K64 = (_B_THIN64[0.25] - _B_THIN64[0.05]) / 0.20  # per mm of 64T thinning
K16 = (_B_THIN16[0.05] - _B_THIN16[0.00]) / 0.05  # per mm of 16T thinning
# The B-star cutter at the frame: nominal, and the two corners as measured.
# Each corner is (centre-distance offset, 64T thinning, 16T thinning, backlash);
# the model's own 64T thinning is gear_train.yaml's 0.15.
_EXTRA_NOMINAL = 0.4225696498924991
NOMINAL_TIGHT_BACKLASH_MM = 0.32269
STUDY_CORNERS = {
    "tight": (0.2095696498924991 - _EXTRA_NOMINAL, 0.05, 0.00, 0.10230),
    "loose": (0.9125696498924991 - _EXTRA_NOMINAL, 0.20, 0.02, 0.69568),
}
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
    crank_bearing_length: float,
    residual: bool = True,
) -> tuple[Term, ...]:
    """Every contributor but the bushing, relative to the frame's nominal."""
    band_high = post.CRANK_ABOVE_CONE_BAND[0]
    band_low = post.CRANK_ABOVE_CONE_BAND[1]
    plan_dc = PLAN_DX_PER_DEG * plan_limit_deg * DC_PER_DX
    thick64_high, thin64_low = crank_drive_gear_notes.TOOTH_THICKNESS_DEVIATIONS
    yaw = _pose_range(_YAW, plan_limit_deg)
    tilt = _pose_range(_TILT, plan_limit_deg)
    terms = [
        # The printed crank-above-cone spacing, placed against the frame: R1's
        # bore sits CRANK_BORE_DROP low, so its whole band is below the frame.
        Term(
            "crank bore spacing (printed band, from the frame)",
            KC * (spacing_printed + band_low - FRAME_DY) * DC_PER_DY,
            KC * (spacing_printed + band_high - FRAME_DY) * DC_PER_DY,
        ),
        Term("cone bore plan angle", -KC * plan_dc, KC * plan_dc),
        Term("64T axial station", -KC * STATION_64T_DC, KC * STATION_64T_DC),
        # At rest gravity drops the crank toward the 64T and the cone shaft
        # away from the crank; each is zero at the other corner.
        Term(
            "crank float at rest",
            -KC * _float_at_rest(_RUNNING[1], crank_bearing_length, CRANK_OVERHANG),
            0.0,
        ),
        Term(
            "cone float at rest",
            0.0,
            KC * _float_at_rest(_RUNNING[1], post.CONE_BOSS_LENGTH, CONE_OVERHANG),
        ),
        # A gear offset on its bore puts its runout's closing side at the tight
        # spot, so it only ever closes there.
        Term(
            "gear bore runout (16T slip, 64T bonded)",
            -KC * (pinion.BORE_DIAMETRAL_CLEARANCE[1] + RETAINED_JOINT_CLEARANCE[1]) / 2.0,
            0.0,
        ),
        Term("64T tooth thickness", -K64 * thick64_high, -K64 * thin64_low),
        Term(
            "16T tooth thickness",
            -K16 * pinion.TOOTH_THICKNESS_UPPER_DEVIATION,
            -K16 * pinion.TOOTH_THICKNESS_LOWER_DEVIATION,
        ),
        # Yaw and tilt each at the full limit: a diametral zone bounds their
        # vector sum, so this is up to sqrt(2) conservative.
        Term("crank axis yaw", yaw[0], yaw[1]),
        Term("crank axis tilt", tilt[0], tilt[1]),
    ]
    if residual:
        # What the exact solids read over the linear model at each measured
        # corner, taken only where it hurts.
        excess = {
            corner: backlash - _linear_backlash(dc, thin64, thin16)
            for corner, (dc, thin64, thin16, backlash) in STUDY_CORNERS.items()
        }
        terms.append(
            Term(
                "study excess over the linear model",
                min(excess["tight"], 0.0),
                max(excess["loose"], 0.0),
            )
        )
    return tuple(terms)


def _corner_backlash(terms: tuple[Term, ...]) -> tuple[float, float]:
    return (
        NOMINAL_TIGHT_BACKLASH_MM + sum(t.tight for t in terms),
        NOMINAL_TIGHT_BACKLASH_MM + sum(t.loose for t in terms),
    )


# --- R1 as printed -----------------------------------------------------------
_SPACING_PLACES = post.DRAWING_PRECISION_BY_NAME["CrankAboveCone"]
SPACING_PRINTED = round(post.CRANK_ABOVE_CONE, _SPACING_PLACES)
TERMS = stack_terms(
    spacing_printed=SPACING_PRINTED,
    plan_limit_deg=post.CRANK_BORE_ANGLE_LIMIT_DEG,
    crank_bearing_length=bushing.LENGTH - _ROW_1,
)
TIGHT_BACKLASH_MM, LOOSE_BACKLASH_MM = _corner_backlash(TERMS)
# Centre distance the bushing must supply, from the post bore's place.
OPEN_NEEDED = (FITUP_BACKLASH_MM - TIGHT_BACKLASH_MM) / KC
CLOSE_NEEDED = (LOOSE_BACKLASH_MM - FITUP_BACKLASH_MM) / KC
THROW_REACH = bushing.ECCENTRICITY + bushing.ECCENTRICITY_BAND[1]
OPEN_MARGIN = THROW_REACH - OPEN_NEEDED
CLOSE_MARGIN = THROW_REACH - CLOSE_NEEDED

# --- The acceptance budget after bonding ------------------------------------
# The g6 OD can settle anywhere in the H7 bore while the compound cures; that
# moves the set centre distance by up to half the seat clearance.
RESEAT_DC = (post.CRANK_BORE_BAND[0] - bushing.OD_BAND[1]) / 2.0
RESEAT_BACKLASH = KC * RESEAT_DC
READING_ALLOWANCE = FITUP_BACKLASH_BAND_MM - RESEAT_BACKLASH


def stack_text() -> str:
    lines = [
        f"crank mesh fit-up stack: target {FITUP_BACKLASH_MM:.2f} "
        f"+/-{FITUP_BACKLASH_BAND_MM:.2f} at the tight spot; KC {KC:.4f}, "
        f"K64 {K64:.3f}, K16 {K16:.3f}; frame C {FRAME_C2C:.3f}, "
        f"DY/C {DC_PER_DY:.4f}, DX/C {DC_PER_DX:.4f}",
        f"  {'term':52s} {'tight':>8s} {'loose':>8s}  (backlash mm)",
    ]
    lines += [f"  {t.name:52s} {t.tight:+8.4f} {t.loose:+8.4f}" for t in TERMS]
    lines += [
        f"  corner backlash before the bushing: tight {TIGHT_BACKLASH_MM:.4f}, "
        f"loose {LOOSE_BACKLASH_MM:.4f}",
        f"  bushing must open {OPEN_NEEDED:.4f} and close {CLOSE_NEEDED:.4f}; "
        f"throw reach {THROW_REACH:.3f}",
        f"  margin: open {OPEN_MARGIN:+.4f}, close {CLOSE_MARGIN:+.4f} "
        "(linear KC, fitted over +/-0.150 of centre distance)",
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
