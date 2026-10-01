r"""Pure-data contract for MHA-160, the transgear hub cap (contract §2.2, R9-5).

A brass cap nut on the stud MHA-082's #6-32 front thread.  Its plain rear face
seats on the stud's journal shoulder (machine z -157.8), so the cap is torqued
against the stud and never against the disc cluster; the cluster floats
between the stud's Ø9 thrust step and that shoulder.  Two drilled spanner
holes in the front face take a pin spanner.

Frame: axis local +Z toward the machine front, origin on the rear face (the
Front Plane, z 0), so machine z = -157.8 - local z.  ``FrontFace`` is the
plane at z 5.80; ``Axis1`` the cap axis.  The spanner holes lie on local Y,
in the Right plane of the turned profile, so one axial section shows the
profile, the thread and both holes.

PURE DATA: the build and the drawing both import it.
"""

from __future__ import annotations

import math

from _hole_spec import HoleSpec, blind_cut_dia_mm
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
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

REAR_FACE_MACHINE_Z = ARM_SEAT_MACHINE_Z - CAP_SHOULDER_STATION  # -157.8

CAP_DIA = 10.50
CAP_LENGTH = 5.80
# 45-degree break on the front O.D. edge, printed as a single MAX limit so
# its inner edge never reaches the spanner holes (R9-5): swTolMAX prints the
# NOMINAL then "MAX", so the nominal sits at the band's top.
FRONT_CHAMFER = 0.5
FRONT_CHAMFER_BAND = (0.0, -0.3)  # (upper, lower)
FRONT_CHAMFER_TOL_TYPE = 6  # swTolType_e.swTolMAX (offline API docs, enums/swTolType_e)
CHAMFER_CALLOUT = "X 45 DEG"

# #6-32 UNC-2B through, one thread authority with the stud.
TAP_SPEC = HoleSpec("tapped", FRONT_THREAD)
TAP_DRILL_DIA = blind_cut_dia_mm(TAP_SPEC)
# 90-degree entry countersink at the FRONT only; the rear face stays plain
# (it is the seat).  The title block's drilled row (+0.10/0) governs its Ø.
CSK_DIA = 3.9
CSK_DIA_MAX = round(CSK_DIA + drilled_oversize_mm(), 6)
CSK_QUALIFIER = f"90\u00b0 CSK \u00d8{CSK_DIA:.1f} FRONT"

# Two drilled spanner holes on local ±Y, 2.0 deep from the front face.
SPANNER_HOLE_DIA = 1.2
SPANNER_HOLE_DEPTH = 2.0
SPANNER_HOLE_SPACING = 6.800  # centre to centre, r 3.4 about the axis
SPANNER_HOLE_R = SPANNER_HOLE_SPACING / 2.0
SPANNER_HOLE_CALLOUT = "2X DRILL"

# --- Decimal places ARE the tolerance (policy rule 2) --------------------------
# .XX: the O.D. (the spanner-hole web to the O.D. below) and the length (the
# thread engagement below).  .XXX: the spanner-hole spacing (±0.065 position
# in both webs).  The chamfer prints its MAX; the drilled holes read the title
# block's drilled row.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "CapProfile": {"CapDia", "CapLength", "FrontChamfer"},
    "SpannerHoleProfile": {"SpannerHoleDia", "SpannerHoleSpacing"},
    "SpannerHoles": {"SpannerHoleDepth"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "CapProfile": {"CapDia": 2, "CapLength": 2, "FrontChamfer": 1},
    "SpannerHoleProfile": {"SpannerHoleDia": 1, "SpannerHoleSpacing": 3},
    "SpannerHoles": {"SpannerHoleDepth": 1},
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
POSITION_TOL = _band("SpannerHoleSpacing") / 2.0  # each hole about the axis
HOLE_RADIAL_OVERSIZE = drilled_oversize_mm() / 2.0
# The tapped hole's major may run up to 0.05 over basic on diameter
# (contract §8's "tap major 0.025" radial term).
TAP_MAJOR_RADIAL_ALLOWANCE = 0.025

# --- #6-32 engagement on the stud (contract §7, R9-5) ---------------------------
# The cap's rear face seats on the shoulder: the stud's relief takes the first
# RELIEF_WIDTH of the cap, the front countersink (csk - major)/2 at the other
# end.  No first-thread deduction: the relief takes the stud's run-out and the
# countersink the tap entry.
#   nominal 5.80 - 1.1 - (3.9 - 3.505)/2 = 4.5025 = 1.28D
#   worst   5.29 - 1.2 - (4.0 - 3.505)/2 = 3.8425 = 1.09D (floored)
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

# --- Webs (contract §8) ---------------------------------------------------------
# Spanner hole to the tap major: 3.4 - 0.6 - 1.7526 = 1.047; worst less the
# hole position 0.065, its drilled oversize 0.05 and the tap major 0.025.
TAP_WEB_NOMINAL = SPANNER_HOLE_R - SPANNER_HOLE_DIA / 2.0 - FRONT_THREAD_MAJOR / 2.0
TAP_WEB_WORST = (
    TAP_WEB_NOMINAL - POSITION_TOL - HOLE_RADIAL_OVERSIZE - TAP_MAJOR_RADIAL_ALLOWANCE
)
# Spanner hole to the O.D.: 5.25 - 4.0 = 1.25; worst less the O.D.'s .XX
# 0.255, the position 0.065 and the oversize 0.05.
OD_WEB_NOMINAL = CAP_DIA / 2.0 - (SPANNER_HOLE_R + SPANNER_HOLE_DIA / 2.0)
OD_WEB_WORST = (
    OD_WEB_NOMINAL - _band("CapDia") / 2.0 - POSITION_TOL - HOLE_RADIAL_OVERSIZE
)
TAP_WEB_WORST_PRINTED = math.floor(round(TAP_WEB_WORST, 6) * 100.0) / 100.0
OD_WEB_WORST_PRINTED = math.floor(round(OD_WEB_WORST, 6) * 100.0) / 100.0
# The chamfer's inner edge on the front face at the smallest O.D. and the
# largest chamfer (4.995 - 0.5 = 4.495) against the holes' outer edge at the
# worst position and oversize (3.4 + 0.065 + 0.6 + 0.05 = 4.115).
CHAMFER_INNER_EDGE_R_MIN = CAP_DIA_MIN / 2.0 - FRONT_CHAMFER_MAX
SPANNER_HOLE_OUTER_EDGE_R_MAX = (
    SPANNER_HOLE_R + POSITION_TOL + SPANNER_HOLE_DIA / 2.0 + HOLE_RADIAL_OVERSIZE
)
# Countersink edge to the holes' inner edge: 2.685 - 2.0 at the worst case.
SPANNER_HOLE_INNER_EDGE_R_MIN = (
    SPANNER_HOLE_R - POSITION_TOL - SPANNER_HOLE_DIA / 2.0 - HOLE_RADIAL_OVERSIZE
)
# Hole floor to the rear (seat) face: 5.80 - 2.0 = 3.8 nominal, informational.
HOLE_FLOOR_WALL_WORST = CAP_LENGTH_MIN - (
    SPANNER_HOLE_DEPTH + _band("SpannerHoleDepth")
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
        CHAMFER_INNER_EDGE_R_MIN > SPANNER_HOLE_OUTER_EDGE_R_MAX,
        f"front chamfer edge r {CHAMFER_INNER_EDGE_R_MIN:.3f} breaks into the "
        f"spanner holes (outer edge r {SPANNER_HOLE_OUTER_EDGE_R_MAX:.3f})",
    ),
    (
        SPANNER_HOLE_INNER_EDGE_R_MIN > CSK_DIA_MAX / 2.0,
        "spanner holes break into the front countersink",
    ),
    (TAP_WEB_WORST > 0.0 and OD_WEB_WORST > 0.0, "a spanner-hole web is open"),
    (HOLE_FLOOR_WALL_WORST >= 2.0, "spanner-hole floor to the seat face under 2.0"),
    (
        math.isclose(REAR_FACE_MACHINE_Z, -157.8, abs_tol=1e-6),
        "cap rear face is not at machine z -157.8 (R9-5)",
    ),
    (CSK_DIA > FRONT_THREAD_MAJOR, "the countersink ends inside the thread major"),
):
    if not _ok:
        raise AssertionError(f"MHA-160: {_what}")

# The sheet states the approved shortfalls (contract §10.1); the ruling IDs
# stay here.
# Named exception: MHA-160 engagement (drawing-simplicity-policy.md, "Named exceptions").
# Named exception: MHA-160 web (drawing-simplicity-policy.md, "Named exceptions").
DRAWING_NOTES = "\n".join(
    (
        f"THREAD ENGAGEMENT ON THE STUD {ENGAGEMENT_NOMINAL_D_PRINTED:.2f}D NOMINAL, "
        f"{ENGAGEMENT_WORST_D_PRINTED:.2f}D MIN.",
        f"SPANNER HOLE WEB TO THE THREAD {TAP_WEB_WORST_PRINTED:.2f} MIN, "
        f"TO THE O.D. {OD_WEB_WORST_PRINTED:.2f} MIN.",
        "REAR FACE SEATS ON THE STUD SHOULDER: FACE IT FLAT AND SQUARE.",
    )
)
THREAD_CALLOUT = FRONT_THREAD_CALLOUT
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 3:1"
