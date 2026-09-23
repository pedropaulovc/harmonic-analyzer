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
import knife_hanger_interface as knife_hanger

# --- fixed geometry for the drawing's view math (mirrors build_knife_mount) ----
R_BORE = 6.0  # Ø12 knife-bearing bore (2026-09-02 ch18 p.42 re-read: close bore)
BLK_HALF_X = 12.0  # block half-width (24 across)
SUPPORT_Z_THICK = 18.0  # axial depth (user, 2026-09-22); mirrors build_knife_mount
BLK_TOP = 13.816  # exact local top from 999.7 - (979.7 + 10.268/2) - 1.05
BORE_CY = -6.0  # bore crown is the knife axis: actual trunnion line contact
BLK_BOT = -15.0  # BORE_CY - R_BORE - 3.0 wall
BORE_FROM_TOP = BLK_TOP - BORE_CY
BORE_DIAMETER_TOLERANCE_MM = knife_hanger.BORE_DIAMETER_PLUS_MM
BORE_FROM_TOP_TOLERANCE_MM = knife_hanger.BORE_FROM_TOP_TOLERANCE_MM

# Hanger-stud seat boss (knife_hanger_interface option D, user 2026-09-22): a
# round boss rising from the block top into the casting's hanger-stud hole,
# concentric with the tap. Its top is the stud shoulder's seat plane.
BOSS_DIA = knife_hanger.BOSS_DIA_MM
BOSS_HEIGHT = knife_hanger.BOSS_HEIGHT_MM
SEAT_TOP = BLK_TOP + BOSS_HEIGHT  # local y of the seat plane
if abs(SEAT_TOP - knife_hanger.KNIFE_BORE_CROWN_DEPTH_MM) > 1e-9:
    raise AssertionError("knife-mount seat-to-crown depth differs from the interface")

# Mating-interface envelope.  The lever print carries two-place dimensions on
# both trunnion sizes, hence the title-block +0.51-mm adverse material limit.
# dimensions.yaml:1329-1335 derives about 1.6 degrees of summing-bar knife rock
# from the observed 6-mm tip arc.
MATING_HEX_SIZE_PLUS_MM = 0.51
REQUIRED_ROCK_SWEEP_DEG = 1.6

# Native blind hanger-stud tap through the boss, shared by the model and its
# hole callout. Depth is the 118-degree tap-drill's cylindrical shoulder below
# the seat plane; ThreadDepth is the usable full thread, a MINIMUM (the drill
# caps it). The thread, depths and bands are the knife-hanger joint interface
# (user rulings 2026-09-22: engagement >= 1.5D, machining-dfm.md:73; bands at
# the title block). The drill depth carries the title-block .XX band, so the
# print states no explicit tolerance. The names stay STUD_TAP_* for the
# assembly.
STUD_TAP_DRILL_DEPTH_MM = knife_hanger.TAP_DRILL_DEPTH_MM
STUD_TAP_DRILL_DEPTH_DEVIATIONS_MM = knife_hanger.TAP_DRILL_DEPTH_DEVIATIONS_MM
STUD_TAP_THREAD_DEPTH_MM = knife_hanger.TAP_THREAD_DEPTH_MIN_MM
STUD_TAP_THREAD_DEPTH_DEVIATIONS_MM = (0.0, math.inf)  # printed "MIN"
# swTolType_e for the two native depth dimensions: the drill depth rides the
# title block (swTolNONE); the thread depth prints MIN (swTolMIN).
STUD_TAP_DRILL_DEPTH_TOLERANCE_TYPE = 0
STUD_TAP_THREAD_DEPTH_TOLERANCE_TYPE = 5
STUD_TAP_SPEC = HoleSpec(
    "tapped_bottoming",
    knife_hanger.THREAD,
    end="blind",
    depth_mm=STUD_TAP_DRILL_DEPTH_MM,
    overrides_mm={"ThreadDepth": STUD_TAP_THREAD_DEPTH_MM},
)
STUD_TAP_DIA = blind_cut_dia_mm(STUD_TAP_SPEC)
if abs(STUD_TAP_DIA - knife_hanger.TAP_DRILL_DIA_MM) > 1e-9:
    raise AssertionError("knife-mount tap drill differs from the hanger interface")
STUD_TAP_PITCH_MM = knife_hanger.THREAD_PITCH_MM
STUD_TAP_MAJOR_DIA_MM = knife_hanger.THREAD_MAJOR_DIA_MM
STUD_TAP_POINT_HEIGHT_MM = 0.5 * STUD_TAP_DIA * DRILL_POINT_H
STUD_TAP_CROWN_WEB_MM = (
    SEAT_TOP - STUD_TAP_DRILL_DEPTH_MM - STUD_TAP_POINT_HEIGHT_MM
)

# Adverse crown stack from the seat plane: the boss may finish short, the bore
# location may shorten by its band, and the close bore and tap drill may both
# finish at their upper limits; the drill point also allows a conservative
# 1-degree blunter included angle than the conventional 118 degrees.
DRILLED_HOLE_DIAMETER_PLUS_MM = knife_hanger.DRILLED_HOLE_DIAMETER_PLUS_MM
DRILL_POINT_MIN_INCLUDED_ANGLE_DEG = knife_hanger.DRILL_POINT_MIN_INCLUDED_ANGLE_DEG
STUD_TAP_WORST_CASE_CROWN_WEB_MM = (
    BOSS_HEIGHT
    + knife_hanger.BOSS_HEIGHT_DEVIATIONS_MM[0]
    + BORE_FROM_TOP
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
if abs(STUD_TAP_WORST_CASE_CROWN_WEB_MM - knife_hanger.MIN_CROWN_WEB_MM) > 1e-9:
    raise AssertionError("knife-mount crown stack differs from the interface")
# Drill depth below the usable-thread minimum at the shallow drill limit.
STUD_TAP_WORST_CASE_RUNOUT_MM = (
    STUD_TAP_DRILL_DEPTH_MM
    + STUD_TAP_DRILL_DEPTH_DEVIATIONS_MM[0]
    - STUD_TAP_THREAD_DEPTH_MM
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
    "BossProfile": {"BossFromEnd"},
    "Boss": {"BossHeight"},
}

# Decimal places carry the ordinary size tolerance and therefore live on the
# actual model dimensions. BoreFromTop prints two places at the title block's
# .XX, which the interface's crown and gap stacks assume (knife-cc-17).
# BoreFromSide prints one place: the bore and the tap share one centreline
# (the tap's side location is only a reference read of it), and 6-mm walls
# either side leave nothing for .XX to protect (machinist review, knife-cc-6).
# BossFromEnd prints one place: it locates the boss (and the tap concentric
# with it) from ONE end face, and its .X band still leaves both axial walls
# >= 1.2 mm (test_end_located_hanger_tap_retains_axial_wall_at_limits). The
# boss height prints one place too: the interface derives the boss height, gap
# and clearances from the .X band.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BlockProfile": {
        "BlockWidth": 1,
        "BlockHeight": 1,
        "BoreFromSide": 1,
        "BoreFromTop": 2,
        "BoreDia": 2,
    },
    "Block": {"Depth": 1},
    "BossProfile": {"BossFromEnd": 1},
    "Boss": {"BossHeight": 1},
}

if (
    BORE_FROM_TOP_TOLERANCE_MM != knife_hanger.TITLE_BLOCK_XX_MM
    or DRAWING_PRECISION["BlockProfile"]["BoreFromTop"] != 2
):
    raise AssertionError("BoreFromTop no longer prints the band its stacks assume")

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
    "BossHeight": BOSS_HEIGHT,
    "BossFromEnd": SUPPORT_Z_THICK / 2.0,
}
# Sheet-side dimensions: measured on the view, never model-imported.
# TapFromSide is a parenthesized reference. BossDia is the lathe-turned boss
# printed as a turned diameter on the side (section) view per drawing policy
# rule 7; the model's circle dimension only reads on the end view, where rule 7
# forbids leader-piled diameters. It prints plain, at the interface's .X band.
REFERENCE_DIMENSION_NOMINALS_MM = {
    "TapFromSide": BLK_HALF_X,
    "BossDia": BOSS_DIA,
}
DRAWING_REFERENCE_PRECISION = {
    "TapFromSide": 1,  # a read of BoreFromSide's centreline, same precision
    "BossDia": 1,  # .X: knife_hanger_interface.BOSS_DIA_DEVIATIONS_MM
}
# Hole Wizard depth places (policy rule 2's callout exception): SetPrecision3
# cannot reach a callout's per-variable places, so the part build writes these
# onto the native depth dimensions and the drawing copies them to the callout.
HOLE_CALLOUT_PRECISION = {"hw-tapdrldepth": 2, "hw-threaddepth": 2}
# The native tap definition and the bore-location/size bands close the adverse
# uninterrupted-crown stack; the drawing's center section shows that geometry.
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
