r"""Pure-data contract for MHA-160, the transgear hub cap (contract §2.2, R9-5).

A brass cap nut on the stud MHA-082's #6-32 front thread.  Its plain rear face
seats on the stud's journal shoulder (machine z -158.05 as fitted), so the
cap is torqued against the stud and never against the disc cluster; the
cluster floats between the stud's Ø9 thrust step and that shoulder.  Two
wrench flats over the whole length take an 11/32 open-end spanner (R9-58).

Frame: axis local +Z toward the machine front, origin on the rear face (the
Front Plane, z 0), so machine z = -158.05 - local z.  ``FrontFace`` is the
plane at z 5.80; ``Axis1`` the cap axis.  The flats stand square to local X,
so the axial section in the Right plane cuts the full turned profile clear
of both.

PURE DATA: the build and the drawing both import it.
"""

from __future__ import annotations

import math

from _gtol_spec import PlanarFace
from _hole_spec import HoleSpec, blind_cut_dia_mm
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
from _surface_finish import SEAT_UM, SurfaceFinishControl
from transgear_disc_hub_spec import SHANK_DIA, SHANK_DIA_BAND
from transgear_stub_spec import (
    ARM_SEAT_MACHINE_Z,
    CAP_SHOULDER_STATION,
    FRONT_THREAD,
    FRONT_THREAD_CALLOUT,
    FRONT_THREAD_END,
    FRONT_THREAD_END_MIN,
    FRONT_THREAD_MAJOR,
    RELIEF_WIDTH,
    RELIEF_WIDTH_MAX,
)

REAR_FACE_MACHINE_Z = ARM_SEAT_MACHINE_Z - CAP_SHOULDER_STATION  # -158.05

CAP_DIA = 10.50
CAP_LENGTH = 5.80
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
# 90-degree entry countersink at the FRONT only; the rear face stays plain
# (it is the seat).  The title block's drilled row (+0.10/0) governs its Ø.
# R9-58 took it from 3.9 to 3.6: nothing else on the face competes for room,
# and the smaller loss lengthens the engagement.
CSK_DIA = 3.6
CSK_DIA_MAX = round(CSK_DIA + drilled_oversize_mm(), 6)
CSK_QUALIFIER = f"90\u00b0 CSK \u00d8{CSK_DIA:.1f} FRONT"

# Two wrench flats square to local X over the whole length (R9-58), for an
# 11/32 open-end spanner: ASME B18.2.2 opens that spanner at least
# 1.005 W + 0.001 in over the 11/32 basic, so a flat pair no wider than the
# basic enters it.
FLATS_ACROSS = 8.600
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

# --- #6-32 engagement on the stud (contract §7, R9-5) ---------------------------
# The cap's rear face seats on the shoulder: the stud's relief takes the first
# RELIEF_WIDTH of the cap, the front countersink (csk - major)/2 at the other
# end.  No first-thread deduction: the relief takes the stud's run-out and the
# countersink the tap entry.
#   nominal 5.80 - 1.1 - (3.6 - 3.505)/2 = 4.6525 = 1.33D
#   worst   5.29 - 1.2 - (3.7 - 3.505)/2 = 3.9925 = 1.13D (floored)
CSK_LOSS_NOMINAL = (CSK_DIA - FRONT_THREAD_MAJOR) / 2.0
CSK_LOSS_MAX = (CSK_DIA_MAX - FRONT_THREAD_MAJOR) / 2.0
ENGAGEMENT_NOMINAL = round(
    min(CAP_LENGTH - CSK_LOSS_NOMINAL, FRONT_THREAD_END) - RELIEF_WIDTH, 6
)
ENGAGEMENT_WORST = round(
    min(CAP_LENGTH_MIN - CSK_LOSS_MAX, FRONT_THREAD_END_MIN) - RELIEF_WIDTH_MAX, 6
)
ENGAGEMENT_NOMINAL_D = ENGAGEMENT_NOMINAL / FRONT_THREAD_MAJOR
ENGAGEMENT_WORST_D = ENGAGEMENT_WORST / FRONT_THREAD_MAJOR
# User ruling 1 (round 5) approved 1.08D worst for this joint; R9-5 moved the
# stop to the stud shoulder and restated the pair.
APPROVED_ENGAGEMENT_FLOOR_D = 1.08
# A MIN never rounds up: floored to two places.
ENGAGEMENT_NOMINAL_D_PRINTED = round(ENGAGEMENT_NOMINAL_D, 2)
ENGAGEMENT_WORST_D_PRINTED = math.floor(ENGAGEMENT_WORST_D * 100.0) / 100.0

# --- Flats (R9-58) ----------------------------------------------------------------
# Flat to the tap major: 4.3 - 1.7526 = 2.547 nominal; worst at the narrowest
# flats less the tap major's 0.025.
FLAT_WALL_NOMINAL = FLATS_ACROSS / 2.0 - FRONT_THREAD_MAJOR / 2.0
FLAT_WALL_WORST = (
    FLATS_ACROSS_MIN / 2.0 - FRONT_THREAD_MAJOR / 2.0 - TAP_MAJOR_RADIAL_ALLOWANCE
)
# The feed sleeve's nose (the hub's press-seat shank) thrusts on the rear face
# when the cluster floats forward: the flats stand outside its largest O.D.
SLEEVE_NOSE_R_MAX = (SHANK_DIA + SHANK_DIA_BAND[0]) / 2.0
# The chamfer's inner edge on the front face at the smallest O.D. and the
# largest chamfer (4.995 - 0.5 = 4.495) against the widest flats (4.365).
CHAMFER_INNER_EDGE_R_MIN = CAP_DIA_MIN / 2.0 - FRONT_CHAMFER_MAX
# The spanner's bearing: each flat's chord at the smallest O.D. and the widest
# flats, 2 x sqrt(4.995^2 - 4.365^2) = 4.86.
FLAT_CHORD_WORST = 2.0 * math.sqrt(
    (CAP_DIA_MIN / 2.0) ** 2 - (FLATS_ACROSS_MAX / 2.0) ** 2
)

for _ok, _what in (
    (
        ENGAGEMENT_WORST_D >= APPROVED_ENGAGEMENT_FLOOR_D,
        f"#6-32 engagement {ENGAGEMENT_WORST_D:.3f}D worst under the approved "
        f"{APPROVED_ENGAGEMENT_FLOOR_D}D",
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
        FLATS_ACROSS_MIN / 2.0 > SLEEVE_NOSE_R_MAX,
        "the flats cut into the sleeve nose's thrust annulus on the rear face",
    ),
    (
        CHAMFER_INNER_EDGE_R_MIN > FLATS_ACROSS_MAX / 2.0,
        f"front chamfer edge r {CHAMFER_INNER_EDGE_R_MIN:.3f} runs inside the "
        f"flats (r {FLATS_ACROSS_MAX / 2.0:.3f})",
    ),
    (
        math.isclose(REAR_FACE_MACHINE_Z, -158.05, abs_tol=1e-6),
        "cap rear face is not at machine z -158.05 as fitted (R9-47)",
    ),
    (CSK_DIA > FRONT_THREAD_MAJOR, "the countersink ends inside the thread major"),
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
