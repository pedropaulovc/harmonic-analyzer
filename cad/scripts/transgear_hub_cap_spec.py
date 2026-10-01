r"""Pure-data contract for MHA-160, the transgear hub cap (contract §2.2, R9-5).

A brass cap nut on the stud MHA-082's #6-32 front thread.  Its plain rear face
seats on the stud's journal shoulder (machine z -158.05 as fitted), so the
cap is torqued against the stud and never against the disc cluster; the
cluster floats between the stud's Ø9 thrust step and that shoulder.  Two
wrench flats over the whole length take an 11/32 open-end spanner (R9-58).

Frame: axis local +Z toward the machine front, origin on the rear face (the
Front Plane, z 0), so machine z = -158.05 - local z.  ``FrontFace`` is the
plane at z 6.00; ``Axis1`` the cap axis.  The flats stand square to local X,
so the axial section in the Right plane cuts the full turned profile clear
of both.

PURE DATA: the build and the drawing both import it.
"""

from __future__ import annotations

import math

import _config
from _gtol_spec import PlanarFace
from _hole_spec import HoleSpec, blind_cut_dia_mm
from _printed_tolerance import printed_band_mm
from _surface_finish import SEAT_UM, SurfaceFinishControl
from transgear_disc_hub_spec import SHANK_DIA, SHANK_DIA_BAND
from transgear_stub_spec import (
    CAP_SHOULDER_STATION,
    FRONT_THREAD,
    FRONT_THREAD_CALLOUT,
    FRONT_THREAD_END,
    FRONT_THREAD_END_MIN,
    FRONT_THREAD_MAJOR,
    RELIEF_WIDTH,
    RELIEF_WIDTH_MAX,
    SEAT_MACHINE_Z,
)

REAR_FACE_MACHINE_Z = SEAT_MACHINE_Z - CAP_SHOULDER_STATION  # -158.05

CAP_DIA = 10.50
# R9-66: 6.00, not 5.80 -- the 0.2 buys back the thread the front tap mouth's
# break costs once that loss is measured to the tap drill (R9-63).
CAP_LENGTH = 6.00
# 45-degree break on the front O.D. edge, printed as a single MAX limit so
# its inner edge stays outside the flats and they run out the front face:
# swTolMAX prints the NOMINAL then "MAX", so the nominal sits at the band's top.
FRONT_CHAMFER = 0.5
FRONT_CHAMFER_BAND = (0.0, -0.3)  # (upper, lower)
FRONT_CHAMFER_TOL_TYPE = 6  # swTolType_e.swTolMAX (offline API docs, enums/swTolType_e)
CHAMFER_CALLOUT = "X 45 DEG"

# #6-32 UNC-2B through, one thread authority with the stud.
TAP_SPEC = HoleSpec("tapped", FRONT_THREAD)
TAP_DRILL_DIA = blind_cut_dia_mm(TAP_SPEC)
# R9-66: no countersink.  Measured to the tap drill (R9-63) a countersink must
# clear the major, so it costs at least (3.505 - 2.705)/2 = 0.40 of thread;
# the front mouth carries only the title block's edge break, the rear mouth
# lies inside the stud's thread relief.
TAP_MOUTH_BREAK = max(
    float(_config.title_block("edge_break")[key])
    for key in ("radius_mm", "chamfer_max_mm")
)

# Two wrench flats square to local X over the whole length (R9-58), for an
# 11/32 open-end spanner: ASME B18.2.2 opens that spanner at least
# 1.005 W + 0.001 in over the 11/32 basic, so a flat pair no wider than the
# basic enters it.
FLATS_ACROSS = 8.600
# The flats are cut symmetric about the bore axis (the model's FlatsProfile
# halves the across-flats from the axis): the fleet's centring term on their
# centre plane, half the .XXX band, is printed with them and spent below.
FLATS_POSITION_TOL = printed_band_mm(3) / 2.0  # 0.065
FLATS_CALLOUT = f"CENTRED ON BORE AXIS \u00b1{FLATS_POSITION_TOL:.3f}"
SPANNER_BASIC_ACROSS = 11.0 / 32.0 * 25.4  # 8.731

# --- Decimal places ARE the tolerance (policy rule 2) --------------------------
# .XX: the O.D. and the length (the thread engagement below).  .XXX: the
# across-flats (the spanner's opening above, the sleeve nose's thrust annulus
# and the flat-to-thread wall below).  The chamfer prints its MAX.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "CapProfile": {"CapDia", "CapLength", "FrontChamfer"},
    "FlatsProfile": {"FlatsAcross"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "CapProfile": {"CapDia": 2, "CapLength": 2, "FrontChamfer": 1},
    "FlatsProfile": {"FlatsAcross": 3},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked MHA-160 dimension needs authored places")


def _band(name: str) -> float:
    return printed_band_mm(DRAWING_PRECISION_BY_NAME[name])


CAP_LENGTH_MIN = round(CAP_LENGTH - _band("CapLength"), 6)
CAP_LENGTH_MAX = round(CAP_LENGTH + _band("CapLength"), 6)
CAP_DIA_MIN = round(CAP_DIA - _band("CapDia"), 6)
FRONT_CHAMFER_MAX = round(FRONT_CHAMFER + FRONT_CHAMFER_BAND[0], 6)
FLATS_ACROSS_MIN = round(FLATS_ACROSS - _band("FlatsAcross"), 6)
FLATS_ACROSS_MAX = round(FLATS_ACROSS + _band("FlatsAcross"), 6)
# The tapped hole's major may run up to 0.05 over basic on diameter
# (contract §8's "tap major 0.025" radial term).
TAP_MAJOR_RADIAL_ALLOWANCE = 0.025

# --- #6-32 engagement on the stud (contract §7, R9-5, R9-66) --------------------
# The cap's rear face seats on the shoulder: the stud's relief takes the first
# RELIEF_WIDTH of the cap, the front tap mouth's edge break its depth at the
# other end.  No first-thread deduction: the relief takes the stud's run-out
# and the break the tap entry.
#   nominal 6.00 - 1.1 - 0.25 = 4.65 = 1.33D
#   worst   5.49 - 1.2 - 0.25 = 4.04 = 1.15D (floored)
ENGAGEMENT_NOMINAL = round(
    min(CAP_LENGTH - TAP_MOUTH_BREAK, FRONT_THREAD_END) - RELIEF_WIDTH, 6
)
ENGAGEMENT_WORST = round(
    min(CAP_LENGTH_MIN - TAP_MOUTH_BREAK, FRONT_THREAD_END_MIN) - RELIEF_WIDTH_MAX, 6
)
ENGAGEMENT_NOMINAL_D = ENGAGEMENT_NOMINAL / FRONT_THREAD_MAJOR
ENGAGEMENT_WORST_D = ENGAGEMENT_WORST / FRONT_THREAD_MAJOR
# User ruling 1 (round 5) approved 1.08D worst for this joint; R9-5 moved the
# stop to the stud shoulder and restated the pair; R9-66 (the countersink gone,
# the cap 6.00) restated the named row at the 1.15D the sheet prints.
APPROVED_ENGAGEMENT_FLOOR_D = 1.08
NAMED_ROW_ENGAGEMENT_D = 1.15
# A MIN never rounds up: floored to two places.
ENGAGEMENT_NOMINAL_D_PRINTED = round(ENGAGEMENT_NOMINAL_D, 2)
ENGAGEMENT_WORST_D_PRINTED = math.floor(ENGAGEMENT_WORST_D * 100.0) / 100.0

# --- Flats (R9-58) ----------------------------------------------------------------
# Flat to the tap major: 4.3 - 1.7526 = 2.547 nominal; worst at the narrowest
# flats, shifted off the axis by their centring, less the tap major's 0.025.
FLAT_WALL_NOMINAL = FLATS_ACROSS / 2.0 - FRONT_THREAD_MAJOR / 2.0
FLAT_WALL_WORST = (
    FLATS_ACROSS_MIN / 2.0
    - FLATS_POSITION_TOL
    - FRONT_THREAD_MAJOR / 2.0
    - TAP_MAJOR_RADIAL_ALLOWANCE
)
# The feed sleeve's nose (the hub's press-seat shank) thrusts on the rear face
# when the cluster floats forward: the flats stand outside its largest O.D.
SLEEVE_NOSE_R_MAX = (SHANK_DIA + SHANK_DIA_BAND[0]) / 2.0
# The nearer flat at the narrowest flats and the full centring offset.
FLAT_NEAR_R_MIN = FLATS_ACROSS_MIN / 2.0 - FLATS_POSITION_TOL
# The farther flat at the widest flats and the full centring offset.
FLAT_FAR_R_MAX = FLATS_ACROSS_MAX / 2.0 + FLATS_POSITION_TOL
# The chamfer's inner edge on the front face at the smallest O.D. and the
# largest chamfer (4.995 - 0.5 = 4.495) against the farther flat (4.43).
CHAMFER_INNER_EDGE_R_MIN = CAP_DIA_MIN / 2.0 - FRONT_CHAMFER_MAX
# The spanner's bearing: the farther flat's chord at the smallest O.D.,
# 2 x sqrt(4.995^2 - 4.43^2) = 4.62.
FLAT_CHORD_WORST = 2.0 * math.sqrt((CAP_DIA_MIN / 2.0) ** 2 - FLAT_FAR_R_MAX**2)

for _ok, _what in (
    (
        ENGAGEMENT_WORST_D >= max(APPROVED_ENGAGEMENT_FLOOR_D, NAMED_ROW_ENGAGEMENT_D),
        f"#6-32 engagement {ENGAGEMENT_WORST_D:.3f}D worst under the named row's "
        f"{NAMED_ROW_ENGAGEMENT_D}D",
    ),
    (
        FRONT_CHAMFER == FRONT_CHAMFER_MAX,
        "swTolMAX prints the nominal: the chamfer nominal must be its max",
    ),
    (
        FLAT_WALL_WORST >= 2.0,
        f"flat to the #6-32 major {FLAT_WALL_WORST:.3f} worst under the 2.0 target",
    ),
    (
        FLATS_ACROSS_MAX <= SPANNER_BASIC_ACROSS,
        f"widest flats {FLATS_ACROSS_MAX:.3f} do not enter an 11/32 spanner",
    ),
    (
        FLAT_NEAR_R_MIN > SLEEVE_NOSE_R_MAX,
        "the flats cut into the sleeve nose's thrust annulus on the rear face",
    ),
    (
        CHAMFER_INNER_EDGE_R_MIN > FLAT_FAR_R_MAX,
        f"front chamfer edge r {CHAMFER_INNER_EDGE_R_MIN:.3f} runs inside the "
        f"flats (r {FLAT_FAR_R_MAX:.3f})",
    ),
    (
        math.isclose(REAR_FACE_MACHINE_Z, -158.05, abs_tol=1e-6),
        "cap rear face is not at machine z -158.05 as fitted (R9-47)",
    ),
):
    if not _ok:
        raise AssertionError(f"MHA-160: {_what}")

# The rear face seats on the stud shoulder and takes the sleeve nose: a static
# locating seat (policy rule 5), on the exact face the part build resolves.
SURFACE_FINISHES = (
    SurfaceFinishControl("rear_face", SEAT_UM, PlanarFace((0.0, 0.0, -1.0), 0.0)),
)

# The sheet states the approved shortfall (contract §10.1); the ruling IDs
# stay here.
# Named exception: MHA-160 engagement (drawing-simplicity-policy.md, "Named exceptions").
DRAWING_NOTES = "\n".join(
    (
        f"THREAD ENGAGEMENT ON THE STUD {ENGAGEMENT_NOMINAL_D_PRINTED:.2f}D NOMINAL, "
        f"{ENGAGEMENT_WORST_D_PRINTED:.2f}D MIN.",
        "REAR FACE SEATS ON THE STUD SHOULDER.",
    )
)
THREAD_CALLOUT = FRONT_THREAD_CALLOUT
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 3:1"
