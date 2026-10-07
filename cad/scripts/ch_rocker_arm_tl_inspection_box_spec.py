r"""Pure-data contract for the rocker inspection box (MHA-CH-006-TL-08).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). The
rocker arm's off-machine A/B/C position check (prechips S4 op 50) seats the
arm's datum-B strap face on the box front face and its datum-C tip land on the
C stop bar (MHA-CH-006-TL-09), two light clamps reaching through the left-wall
windows; the readings are taken base-down and right-side-down on the granite.

Bought, then reworked (shop-additions section 4, binding): the shop cannot
cast or grind a 120 mm box to 0.003/100, so it buys a Suburban Tool
BXP-050505-G box parallel -- 5 x 5 x 5 in ground fine-grain stress-relieved
cast iron, size +-0.002 in, faces square and parallel within 0.0005 in per
6 in, one through core, wall D = 11/16 in, no webs (subtool.com product page
and its BXP drawing, read 2026-10-07). The model carries that bought geometry;
the drawing dimensions only the shop's work: two clamp windows through the
left wall, an access window through the back wall, and two #8-32 taps for the
C stop bar in the front wall. The core runs vertically, so the base, right
side and front face stay whole ground faces. Windows are rescaled from the
inventory's 120 box (left 38/83 above the base -> 40/88; back 80 x 80 centred)
keeping their sizes; the clamp windows start just inside the front wall's
inner face so a clamp jaw reaches it. Squareness after rework is re-checked
by reversal on the granite (a note: fixtures carry no GD&T).

Frame (model): origin at the outer corner where the left face, the front face
and the base meet; +X toward the right side, +Y up from the base, +Z out of
the front face (the box occupies Z -127..0). The inventory's box frame
(rocker-inv fixtures.rocker-inspection-box) maps as inventory (x, y, z) =
model (x, -z, y).
"""

from __future__ import annotations

import ch_rocker_arm_spec as rocker
import ch_rocker_arm_tl_c_stop_bar_spec as bar
from _feature_requirements import ExportFeature, limits
from _gtol_spec import CylinderFace, PlanarFace
from _hole_spec import THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm
from _printed_tolerance import printed_band_mm

INCH = 25.4
# Bought Suburban Tool BXP-050505-G (A = B = C = 5 in, D = 11/16 in).
BOX = 5.0 * INCH
WALL = 11.0 / 16.0 * INCH
CORE = BOX - 2.0 * WALL

# Clamp windows through the left wall (model Right-plane sketch: u = -Z from
# the front face, v = +Y from the base).
WINDOW_W = 32.0  # along the left wall, from the front
WINDOW_H = 24.0
WINDOW_FRONT = 16.0  # from the front face: inside the front wall's inner face
WINDOW_LOW_BASE = 40.0
WINDOW_UP_BASE = 88.0
# Access window through the back wall, centred (model Front-plane sketch).
BACK_WINDOW = 80.0
BACK_WINDOW_X0 = (BOX - BACK_WINDOW) / 2.0
BACK_WINDOW_Y0 = (BOX - BACK_WINDOW) / 2.0

_X = printed_band_mm(1)
# The clamp windows open into the core past the front wall's inner face and
# stop short of the box top; the back window stays inside the core.
if not WINDOW_FRONT + _X < WALL < WINDOW_FRONT + WINDOW_W - _X:
    raise AssertionError("clamp window does not open past the front wall's inner face")
if WINDOW_UP_BASE + WINDOW_H + _X > BOX - 2.0:  # rule 12 floor over the window
    raise AssertionError("upper clamp window breaks the box top lip")
if WINDOW_LOW_BASE + WINDOW_H + 2.0 * _X > WINDOW_UP_BASE:
    raise AssertionError("clamp windows merge")
if BACK_WINDOW_X0 - _X < WALL:
    raise AssertionError("back window cuts into the side walls")

# C stop bar taps in the front wall, at the bar's own screw stations (the bar
# bottom on the base plane, its left end flush with the left face).
TAP_SPEC = HoleSpec("tapped", bar.SCREW_THREAD, end="blind", depth_mm=12.0,
                    overrides_mm={"ThreadDepth": 10.0})
TAP_DRILL_DIA = blind_cut_dia_mm(TAP_SPEC)
TAP_X = bar.SCREW_X
TAP_Y = bar.SCREW_Y
if bar.SCREW_ENGAGEMENT > TAP_SPEC.overrides_mm["ThreadDepth"]:
    raise AssertionError("C stop bar screw bottoms in its tap")
if TAP_SPEC.depth_mm + TAP_DRILL_DIA >= WALL:
    raise AssertionError("C stop bar tap breaks into the core")
if TAP_Y - THREAD_MAJOR_MM[bar.SCREW_THREAD] / 2.0 < 2.0:
    raise AssertionError("C stop bar tap is under rule 12 from the base")
# The rocker's datum-B strap face seats on the front face above the bar.
if rocker.ARM_THICKNESS >= bar.BAR_WIDTH:
    raise AssertionError("C stop bar projection does not carry the rocker strap")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ClampWindowProfile": {
        "WinLowW", "WinLowH", "WinLowFront", "WinLowBase", "WinUpBase",
    },
    "BackWindowProfile": {"BackW", "BackH", "BackX0", "BackY0"},
    "BarTaps": {"TapLeftX", "TapRightX", "TapY"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ClampWindowProfile": {
        "WinLowW": 1, "WinLowH": 1, "WinLowFront": 1, "WinLowBase": 1, "WinUpBase": 1,
    },
    "BackWindowProfile": {"BackW": 1, "BackH": 1, "BackX0": 1, "BackY0": 1},
    "BarTaps": {"TapLeftX": 2, "TapRightX": 2, "TapY": 2},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dimensions in DRAWING_PRECISION.values() for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked inspection-box dimension needs authored places")
DRAWING_BANDS: dict[tuple[str, str], tuple[float, float]] = {
    ("BarTaps", "TapLeftX"): bar.SCREW_POSITION_BAND,
    ("BarTaps", "TapRightX"): bar.SCREW_POSITION_BAND,
    ("BarTaps", "TapY"): bar.SCREW_POSITION_BAND,
}

SURFACE_FINISHES = ()
DRAWING_NOTES = (
    "BOUGHT GROUND BOX PARALLEL: MACHINE ONLY THE DIMENSIONED FEATURES.\n"
    "DO NOT CUT OR MARK THE BASE, RIGHT SIDE OR FRONT FACE.\n"
    "AFTER REWORK RE-CHECK BASE TO RIGHT SIDE SQUARENESS BY REVERSAL ON THE\n"
    "GRANITE AND RECORD THE CORRECTION ON THE BOX."
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:3"

EXPORT_FEATURES: dict[str, ExportFeature] = {
    "datum_b_face": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 0.0, 1.0), 0.0),),
        requirements=("width", "height"),
        fields={
            "normal": ([0.0, 0.0, 1.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
            "width": (BOX, ("BOX",)),
            "height": (BOX, ("BOX",)),
        },
    ),
    "base": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, -1.0, 0.0), 0.0),),
        requirements=("width",),
        fields={
            "normal": ([0.0, -1.0, 0.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "y", "value": 0.0}, ("__frame__",)),
            "width": (BOX, ("BOX",)),
            "thickness": (WALL, ("WALL",)),
        },
    ),
    "right_side": ExportFeature(
        kind="face",
        faces=(PlanarFace((1.0, 0.0, 0.0), BOX),),
        requirements=("width",),
        fields={
            "normal": ([1.0, 0.0, 0.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "x", "value": BOX}, ("BOX",)),
            "width": (BOX, ("BOX",)),
        },
    ),
    **{
        f"bar_tap_{side}": ExportFeature(
            kind="hole",
            faces=(CylinderFace(TAP_DRILL_DIA, contains_x_mm=x),),
            requirements=("at", "thread", "depth"),
            fields={
                "at": ([x, TAP_Y, 0.0], ("TAP_X", "TAP_Y", ("ch_rocker_arm_tl_c_stop_bar_spec", "SCREW_X"))),
                "axis": ([0.0, 0.0, -1.0], ("__frame__",)),
                "station": (
                    limits(x, 2, bar.SCREW_POSITION_BAND),
                    ("TAP_X", ("ch_rocker_arm_tl_c_stop_bar_spec", "SCREW_POSITION_BAND")),
                ),
                "height": (
                    limits(TAP_Y, 2, bar.SCREW_POSITION_BAND),
                    ("TAP_Y", ("ch_rocker_arm_tl_c_stop_bar_spec", "SCREW_POSITION_BAND")),
                ),
                "thread": (f"{bar.SCREW_THREAD} UNC-2B", ("TAP_SPEC",)),
                "depth": (TAP_SPEC.overrides_mm["ThreadDepth"], ("TAP_SPEC",)),
                "tap_drill_mm": (TAP_DRILL_DIA, ("TAP_DRILL_DIA", "TAP_SPEC")),
                "thru": (False, ("TAP_SPEC",)),
            },
            precision={"station": 2, "height": 2},
        )
        for side, x in zip(("left", "right"), TAP_X, strict=True)
    },
}
