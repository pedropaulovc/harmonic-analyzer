r"""Knife-mount dimensional contract -- the single source of truth shared by the
part build (``build_knife_mount.py``) and its manufacturing drawing
(``draw_knife_mount.py``).

PURE DATA, no SolidWorks/COM imports.  The block/bore geometry is derived in
the build from the summing-assembly layout; the fixed values are mirrored here
for drawing view math, native nominal readback, tolerance-stack checks, and the
assembly's unambiguous tap-depth contract.

NOTE on the "knife edge": this hardened-steel BEARING BLOCK (ch18 p.42,
2026-09-02 user re-read: unpainted heat-treated steel, not brass) carries a
circular bore CLOSE around the mating hex trunnion (Ø12 over the 8.653 x 10.268
hex).  The trunnion's TOP VERTEX LINE contacts the bore crown; every other
facet clears.  The sharp ridge is on the LEVER trunnion
(``build_summing_lever``), NOT on this part; this part's critical surface is the
bore's upper inner wall.
"""

from __future__ import annotations

import math

from _gtol_spec import CylinderFace
from _hole_spec import DRILL_POINT_H, HoleSpec, blind_cut_dia_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl

# --- fixed geometry for the drawing's view math (mirrors build_knife_mount) ----
R_BORE = 6.0  # Ø12 knife-bearing bore (2026-09-02 ch18 p.42 re-read: close bore)
BLK_HALF_X = 12.0  # block half-width (24 across)
SUPPORT_Z_THICK = 16.0  # axial depth; 8.00-centred matched tap retains wall
BLK_TOP = 14.616  # exact local top from 999.7 - (979.7 + 10.268/2) - 0.25
BORE_CY = -6.0  # bore crown is the knife axis: actual trunnion line contact
BLK_BOT = -15.0  # BORE_CY - R_BORE - 3.0 wall
BORE_FROM_TOP = BLK_TOP - BORE_CY
BORE_DIAMETER_TOLERANCE_MM = 0.20
BORE_FROM_TOP_TOLERANCE_MM = 0.10

# Mating-interface envelope.  The lever print carries two-place dimensions on
# both trunnion sizes, hence the title-block +0.51-mm adverse material limit.
# dimensions.yaml:1329-1335 derives about 1.6 degrees of summing-bar knife rock
# from the observed 6-mm tip arc.
MATING_HEX_SIZE_PLUS_MM = 0.51
REQUIRED_ROCK_SWEEP_DEG = 1.6

# Native blind hanger-stud tap, shared by the model and its hole callout.  Depth
# is the 118-degree tap-drill's cylindrical shoulder; ThreadDepth is the full
# usable thread.  The asymmetric native bands close the crown, tool-lead, and
# shortened-stud stack without depending on the much looser general tolerance.
STUD_TAP_DRILL_DEPTH_MM = 10.5
STUD_TAP_DRILL_DEPTH_DEVIATIONS_MM = (-0.10, 0.0)
STUD_TAP_THREAD_DEPTH_MM = 6.3
STUD_TAP_THREAD_DEPTH_DEVIATIONS_MM = (0.0, 0.10)
STUD_TAP_SPEC = HoleSpec(
    "tapped_bottoming",
    "1/2-13",
    end="blind",
    depth_mm=STUD_TAP_DRILL_DEPTH_MM,
    overrides_mm={"ThreadDepth": STUD_TAP_THREAD_DEPTH_MM},
)
STUD_TAP_DIA = blind_cut_dia_mm(STUD_TAP_SPEC)
STUD_TAP_POINT_HEIGHT_MM = 0.5 * STUD_TAP_DIA * DRILL_POINT_H
STUD_TAP_CROWN_WEB_MM = (
    BLK_TOP - STUD_TAP_DRILL_DEPTH_MM - STUD_TAP_POINT_HEIGHT_MM
)

# Adverse crown stack: the ordinary top-seat location may shorten by 0.10 mm;
# the close bore and tap-drill diameter may both finish at their upper limits.
# The drill-point term also allows a conservative 1-degree included-angle
# deviation from the conventional 118-degree point.
DRILLED_HOLE_DIAMETER_PLUS_MM = 0.10
DRILL_POINT_MIN_INCLUDED_ANGLE_DEG = 117.0
STUD_TAP_WORST_CASE_CROWN_WEB_MM = (
    BORE_FROM_TOP
    - BORE_FROM_TOP_TOLERANCE_MM
    - (2.0 * R_BORE + BORE_DIAMETER_TOLERANCE_MM) / 2.0
    - (
        STUD_TAP_DRILL_DEPTH_MM
        + STUD_TAP_DRILL_DEPTH_DEVIATIONS_MM[1]
    )
    - 0.5
    * (STUD_TAP_DIA + DRILLED_HOLE_DIAMETER_PLUS_MM)
    / math.tan(math.radians(DRILL_POINT_MIN_INCLUDED_ANGLE_DEG / 2.0))
)
STUD_TAP_WORST_CASE_RUNOUT_MM = (
    STUD_TAP_DRILL_DEPTH_MM
    + STUD_TAP_DRILL_DEPTH_DEVIATIONS_MM[0]
    - STUD_TAP_THREAD_DEPTH_MM
    - STUD_TAP_THREAD_DEPTH_DEVIATIONS_MM[1]
)

SURFACE_FINISHES = (
    SurfaceFinishControl("knife_bore", MACHINED_UM, CylinderFace(2.0 * R_BORE)),
)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print imports. All location dimensions drive the actual shared block/bore
# profile; the hanger tap shares the bore centreline and extrusion mid-plane.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {
        "BlockWidth",
        "BlockHeight",
        "BoreFromSide",
        "BoreFromTop",
        "BoreDia",
    },
    "Block": {"Depth"},
    "StudTap": {"TapFromEnd"},
}

# Decimal places carry the ordinary size tolerance and therefore live on the
# actual model dimensions. BoreFromTop has the tighter explicit native band.
# BoreFromSide prints one place: the bore and the tap share one centreline
# (the tap's side location is only a reference read of it), and 6-mm walls
# either side leave nothing for .XX to protect (machinist review, knife-cc-6).
# TapFromEnd keeps two places: it locates the Ø12.7 thread from ONE end face,
# so its band stacks with Depth's against the far wall (see
# test_end_located_hanger_tap_retains_axial_wall_at_limits).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BlockProfile": {
        "BlockWidth": 1,
        "BlockHeight": 1,
        "BoreFromSide": 1,
        "BoreFromTop": 2,
        "BoreDia": 2,
    },
    "Block": {"Depth": 1},
    "StudTap": {"TapFromEnd": 2},
}

_PRECISION_NAMES = [
    (feature, name) for feature, names in DRAWING_PRECISION.items() for name in names
]
if any(
    name not in DRAWING_DIMENSIONS.get(feature, frozenset())
    for feature, name in _PRECISION_NAMES
):
    raise AssertionError("DRAWING_PRECISION names a dimension the part never marks")
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: DRAWING_PRECISION[feature][name] for feature, name in _PRECISION_NAMES
}
if len(DRAWING_PRECISION_BY_NAME) != len(_PRECISION_NAMES):
    raise AssertionError("DRAWING_PRECISION repeats a dimension name across features")

DRAWING_NOMINALS_MM: dict[str, float] = {
    "BlockWidth": 2.0 * BLK_HALF_X,
    "BlockHeight": BLK_TOP - BLK_BOT,
    "Depth": SUPPORT_Z_THICK,
    "BoreDia": 2.0 * R_BORE,
    "BoreFromTop": BORE_FROM_TOP,
    "BoreFromSide": BLK_HALF_X,
    "TapFromEnd": SUPPORT_Z_THICK / 2.0,
}
REFERENCE_DIMENSION_NOMINALS_MM = {
    "TapFromSide": BLK_HALF_X,
}
DRAWING_REFERENCE_PRECISION = {
    "TapFromSide": 1,  # a read of BoreFromSide's centreline, same precision
}
# The native tap definition and the bore-location/size bands close the adverse
# uninterrupted-crown stack; the drawing's center section shows that geometry.
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
