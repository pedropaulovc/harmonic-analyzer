r"""Knife-mount dimensional contract -- the single source of truth shared by the
part build (``build_sm_knife_mount.py``) and its manufacturing drawing
(``draw_sm_knife_mount.py``).

PURE DATA, no SolidWorks/COM imports.  Nothing else consumes this part's
nominals (no assembly imports ``build_sm_knife_mount``), so one ``_spec`` module is
right here.  The block/bore geometry is derived in the build from the summing-
assembly layout; the fixed values are mirrored here for the drawing's view math,
and the offline lockstep test asserts the part marks and the drawing keeps
EXACTLY ``DRAWING_DIMENSIONS``.

NOTE on the "knife edge": this hardened-steel BEARING BLOCK (ch18 p.42,
2026-09-02 user re-read: unpainted heat-treated steel, not brass) carries a
circular bore CLOSE around the mating hex trunnion (Ø12 over the 8.653 x 10.268
hex), so only the trunnion's TOP VERTEX LINE nears the bore's upper inner wall
-- the true knife-edge line contact.  The sharp ridge is on the LEVER trunnion
(``build_sm_summing_lever``), NOT on this part; this part's critical surface is the
bore's upper inner wall, the knife SEAT: it carries ``MACHINED_UM`` (1.6, policy
rule 5 -- ``GROUND_UM`` 0.8 is reserved for knife edges and pivot-screw
shoulders).
"""

from __future__ import annotations

import math

import _config
import vn_knife_mount_dowel_spec as DOWEL
from _gtol_spec import CylinderFace
from _hole_spec import DRILL_POINT_H, TAP_DRILL_MM, THREAD_MAJOR_MM, HoleSpec
from _surface_finish import MACHINED_UM, SurfaceFinishControl

# --- fixed geometry for the drawing's view math (mirrors build_sm_knife_mount) ----
R_BORE = 6.0  # Ø12 knife-bearing bore (2026-09-02 ch18 p.42 re-read: close bore)
BLK_HALF_X = 12.0  # block half-width (24 across)
SUPPORT_Z_THICK = 14.0  # axial depth straddling the trunnion mid
BLK_TOP = 14.87  # local block top (clamped to the top-frame casting underside)
BLK_BOT = -14.75  # local block bottom (BORE_CY - R_BORE - 3.0 wall)
BORE_CY = -5.75  # bore centre below the ridge origin (TopClear 0.25 - R_BORE)

SURFACE_FINISHES = (
    SurfaceFinishControl("knife_bore", MACHINED_UM, CylinderFace(2.0 * R_BORE)),
)

# --- Knife-hanger screw tap and anti-rotation dowel hole (top seat) ----------
# General tolerances the printed places claim (title block, policy rule 12).
_XX = float(str(_config.title_block("linear_2pl")["display"]).lstrip("\u00b1"))
_XXX = float(str(_config.title_block("linear_3pl")["display"]).lstrip("\u00b1"))
# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "knife-bore position": "0.20",
}
# The bore's position tolerance (diametral zone) from the top seat, datum A.
KNIFE_BORE_POSITION_TOL = float(GEOMETRIC_TOLERANCES_MM["knife-bore position"])
# The bore crown (its upper inner wall) below the top seat: 14.62.
BORE_CROWN_DEPTH = BLK_TOP - (BORE_CY + R_BORE)
# MHA-VN-024, a stock #6-32 socket head cap screw down through the crossbar,
# threads into a bottoming tap on the bore's vertical centreline at
# mid-depth.  The drill runs 1.2 past the full thread (>= 1.5 P for the
# bottoming tap's chamfer).
STUD_THREAD = "#6-32"
STUD_TAP_DRILL_DEPTH = 10.9
STUD_TAP_THREAD_DEPTH = 9.7
STUD_TAP_SPEC = HoleSpec(
    "tapped_bottoming",
    STUD_THREAD,
    end="blind",
    depth_mm=STUD_TAP_DRILL_DEPTH,
    overrides_mm={"ThreadDepth": STUD_TAP_THREAD_DEPTH},
)
STUD_TAP_DIA = TAP_DRILL_MM[STUD_THREAD]  # #36 drill, 2.705
STUD_THREAD_MAJOR = THREAD_MAJOR_MM[STUD_THREAD]  # 3.505
STUD_PITCH = DOWEL.MM_PER_IN / int(STUD_THREAD.rsplit("-", 1)[1])  # 0.794
STUD_TAP_RUNOUT = STUD_TAP_DRILL_DEPTH - STUD_TAP_THREAD_DEPTH
if STUD_TAP_RUNOUT < 1.5 * STUD_PITCH:
    raise AssertionError(
        f"knife-mount tap drill runs {STUD_TAP_RUNOUT:.3f} past the thread,"
        f" under 1.5 P ({1.5 * STUD_PITCH:.3f})"
    )
# The metal the tap's drill point leaves over the bore crown, every band at
# its worst (the tap and the bore print .XX, the bore's position zone is
# KNIFE_BORE_POSITION_TOL): 14.62 - 0.10 - 0.255 - 11.41 - 0.813 = 2.04.
STUD_TAP_WEB_MIN = 2.0
STUD_TAP_POINT_H = STUD_TAP_DIA / 2.0 * DRILL_POINT_H  # 0.813
STUD_TAP_DRILL_DEPTH_MAX = STUD_TAP_DRILL_DEPTH + _XX  # 11.41
BORE_CROWN_DEPTH_MIN = BORE_CROWN_DEPTH - KNIFE_BORE_POSITION_TOL / 2.0 - _XX / 2.0


def tap_web_worst(blk_top: float, drill_depth: float, tap_drill_dia: float) -> float:
    """Worst-case metal between a top-seat tap's 118 deg drill point and the
    bore crown, the seat at local ``blk_top``: the deepest .XX drill, the
    largest .XX bore, the bore at the top of its position zone.  The build
    calls it with its derived (unrounded) top, the regression test with the
    retired 1/2-13 tap."""
    crown_min = blk_top - (BORE_CY + R_BORE) - KNIFE_BORE_POSITION_TOL / 2.0 - _XX / 2.0
    return crown_min - (drill_depth + _XX) - tap_drill_dia / 2.0 * DRILL_POINT_H


STUD_TAP_WEB_WORST = tap_web_worst(BLK_TOP, STUD_TAP_DRILL_DEPTH, STUD_TAP_DIA)
if STUD_TAP_WEB_WORST < STUD_TAP_WEB_MIN:
    raise AssertionError(
        f"knife-mount tap point leaves {STUD_TAP_WEB_WORST:.3f} over the bore"
        f" crown at worst case, under {STUD_TAP_WEB_MIN}"
    )
# The full thread the screw can use, at the shallowest printed thread depth.
STUD_TAP_THREAD_DEPTH_MIN = STUD_TAP_THREAD_DEPTH - _XX  # 9.19
# The tap's thread to the block's front/back faces: 7 - 1.75 = 5.25.
STUD_TAP_Z_WALL = SUPPORT_Z_THICK / 2.0 - STUD_THREAD_MAJOR / 2.0
if STUD_TAP_Z_WALL < STUD_TAP_WEB_MIN:
    raise AssertionError(f"knife-mount tap leaves a {STUD_TAP_Z_WALL:.3f} z wall")

# MHA-VN-051 dowel: a blind flat-bottom reamed hole in the top seat at
# DOWEL.HANGER_OFFSET along local +X from the tap axis, at mid-depth.  The
# reamed hole holds the press of the stock dowel, as the MHA-PD-018 latch-pin
# hole holds the same 1/8 series' (``pd_transgear_arm_geometry``).
PIN_HOLE_X = DOWEL.HANGER_OFFSET  # 6.350
PIN_HOLE_X_PLACES = DOWEL.HANGER_OFFSET_PLACES
PIN_HOLE_X_TOL = DOWEL.HANGER_OFFSET_TOL
PIN_HOLE_DIA = DOWEL.DIA  # 3.175
PIN_HOLE_DIA_BAND = (0.0, -0.010)
PIN_HOLE_DIA_PLACES = 3
PIN_HOLE_DEPTH = DOWEL.PRESS_DEPTH  # 9.5
PIN_HOLE_DEPTH_PLACES = DOWEL.PRESS_DEPTH_PLACES
DOWEL_NUMBER = "MHA-VN-051"
if abs(PIN_HOLE_X_TOL - _XXX) > 1e-9 or PIN_HOLE_X_PLACES != 3:
    raise AssertionError("the dowel station must print .XXX at the title-block band")
# (loosest, tightest) press from the ream band and the catalogue band:
# 0.00254..0.01762, printed rounded outward to four places.
PIN_PRESS_INTERFERENCE = (
    round(DOWEL.DIA_MIN - (PIN_HOLE_DIA + max(PIN_HOLE_DIA_BAND)), 6),
    round(DOWEL.DIA_MAX - (PIN_HOLE_DIA + min(PIN_HOLE_DIA_BAND)), 6),
)
if PIN_PRESS_INTERFERENCE[0] <= 0.0:
    raise AssertionError("the knife-mount dowel ream loses MHA-VN-051's press")
# The press the sheet prints, rounded outward to four places (the MHA-PD-018
# latch-pin precedent, ``pd_transgear_arm_spec.LATCH_PIN_PRESS_PRINTED``).
PIN_PRESS_PRINTED = (
    math.floor(PIN_PRESS_INTERFERENCE[0] * 1e4 + 1e-6) / 1e4,
    math.ceil(PIN_PRESS_INTERFERENCE[1] * 1e4 - 1e-6) / 1e4,
)
if PIN_PRESS_PRINTED != (0.0025, 0.0177):
    raise AssertionError(f"knife-mount dowel press prints {PIN_PRESS_PRINTED}")
# Worst-case webs round the dowel hole (largest ream, station off by its band).
_PIN_R_MAX = (PIN_HOLE_DIA + max(PIN_HOLE_DIA_BAND)) / 2.0
# To the block's +X side face: 12 - 6.48 - 1.5875 = 3.93.
PIN_HOLE_SIDE_WEB = BLK_HALF_X - (PIN_HOLE_X + PIN_HOLE_X_TOL) - _PIN_R_MAX
# To the tap's thread major: 6.22 - 1.5875 - 1.7525 = 2.88.
PIN_HOLE_TAP_WEB = (PIN_HOLE_X - PIN_HOLE_X_TOL) - _PIN_R_MAX - STUD_THREAD_MAJOR / 2.0
# The hole floor's inner corner to the bore, the floor at its deepest and the
# bore at its largest, highest position: 4.97.
_PIN_FLOOR_Y_MIN = BLK_TOP - (PIN_HOLE_DEPTH + DOWEL.PRESS_DEPTH_TOL)
PIN_HOLE_BORE_WEB = (
    (PIN_HOLE_X - PIN_HOLE_X_TOL - _PIN_R_MAX) ** 2
    + (_PIN_FLOOR_Y_MIN - (BORE_CY + KNIFE_BORE_POSITION_TOL / 2.0)) ** 2
) ** 0.5 - (R_BORE + _XX / 2.0)
for _label, _web in (
    ("block side", PIN_HOLE_SIDE_WEB),
    ("tap thread", PIN_HOLE_TAP_WEB),
    ("bore", PIN_HOLE_BORE_WEB),
    ("z face", SUPPORT_Z_THICK / 2.0 - _PIN_R_MAX),
):
    if _web < STUD_TAP_WEB_MIN:
        raise AssertionError(
            f"knife-mount dowel hole leaves {_web:.3f} to the {_label}"
            f" at worst case, under {STUD_TAP_WEB_MIN}"
        )

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The block depth (14) is added on the sheet across the right-view
# section. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"BlockWidth", "BlockHeight"},
    # BoreCz was dropped from the print: the sketch dim measures the centre
    # from the invisible part origin, which sits 0.25 above the bore top -- on
    # the sheet it read as a (wrong) 12.45 bore radius (blind review round 2).
    # The centre height is a sheet-added BASIC from the datum-A top seat.
    "BoreProfile": {"BoreDia"},
    # The dowel hole: its reamed Ø, its station from the tap axis (the part
    # origin's projection in the top view) and its flat-floor depth.
    "PinHoleProfile": {"PinHoleDia", "PinHoleX"},
    "PinHole": {"PinHoleDepth"},
}
# Places the part authors on the dowel-hole dimensions (drawing-simplicity
# policy rule 2); the block and bore print at the document default.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinHoleProfile": {
        "PinHoleDia": PIN_HOLE_DIA_PLACES,
        "PinHoleX": PIN_HOLE_X_PLACES,
    },
    "PinHole": {"PinHoleDepth": PIN_HOLE_DEPTH_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
# Three short lines under the dowel hole's Ø (the MHA-PD-018 PIN_HOLE_CALLOUT
# precedent): the operation, the mating dowel, the press.
PIN_HOLE_CALLOUT = "\n".join(
    (
        "BLIND FLAT-BOTTOM REAM",
        f"PRESS {DOWEL_NUMBER} DOWEL TO FLOOR",
        f"{PIN_PRESS_PRINTED[0]:.4f}/{PIN_PRESS_PRINTED[1]:.4f} INTERFERENCE",
    )
)

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
