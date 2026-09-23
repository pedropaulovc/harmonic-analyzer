r"""Pure-data dimensional contract shared by the cone-tip-block part and drawing."""

from __future__ import annotations

import _config
from _gtol_spec import PlanarFace
from _hole_spec import THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm
from _surface_finish import SEAT_UM, SurfaceFinishControl
from build_cone_tip_adjuster import CUP_DIA as SHAFT_PASSAGE_DIA


# Small black-steel clamp block on the swing platform that carries the axial
# end-play adjuster. See build_cone_tip_block.py for the derivation; this module
# is the drawing's single source of the marked dimensions.
# U24b (2026-09-23): 15 wide so the adjuster thread's side walls keep 2.05 at
# the printed width (.X) and passage-centre (.XX) bands.
BLOCK_X = 15.0  # plan width across the shaft
BLOCK_Z = 12.0  # plan depth along the shaft
# User ruling U30 (2026-09-23): the block stands on a blackened shim pack
# (1.10 nominal, set at fit-up) and is held by one hidden #6-32 screw from
# under the swing platform. The whole block therefore drops 1.10 below the
# cone axis: every feature keeps its place relative to the adjuster axis, and
# the shim restores the drive height in the assembly. The 2026-09-21 DFM
# correction still stands relative to that axis: free material above the
# slit floor, and the pinch screw located from the adjuster axis.
SHIM_NOMINAL = 1.10
ADJUSTER_AXIS_HEIGHT = 33.368 - SHIM_NOMINAL  # 32.268 above the foot
# User ruling U24b (2026-09-23, W-target): the pinch screw rises 8.85 above the
# adjuster axis at the title-block .XX band (the former native +/-0.05 band is
# gone) and the top sits 14.56 above the axis, so the slit-mouth web between
# the pinch clearance hole and the adjuster thread root, and the ligament over
# the pinch hole, both keep 2.0 after edge breaks at the printed limits.
TOP_ABOVE_AXIS = 14.56
BLOCK_HEIGHT = ADJUSTER_AXIS_HEIGHT + TOP_ABOVE_AXIS  # 46.828
PINCH_RISE = 8.85
PINCH_HEIGHT = ADJUSTER_AXIS_HEIGHT + PINCH_RISE
SLIT_FLOOR = ADJUSTER_AXIS_HEIGHT - 0.65
SLIT_W = 1.2
SLIT_DEPTH = BLOCK_HEIGHT - SLIT_FLOOR
ADJUSTER_THREAD = "5/16-18"  # blind tapped hole from the far (north) face
# U30 / E1: the adjuster threads 8.9 mm into the block (>= 8 mm of 5/16-18
# engagement), so the full thread runs 9.5 and the tap-drill shoulder 11.
ADJUSTER_THREAD_DEPTH = 9.5  # full-form thread; leaves lead beyond usable thread
ADJUSTER_DEPTH = 11.0  # tap-drill shoulder
# U30 hold-down: one #6-32 x 1/2 socket head cap screw (McMaster 91251A148)
# comes up through the platform's counterbored lateral slot into the foot
# centre. Under the head the platform leaves a 1.64..2.66 ledge and the fit-up
# shim pack is 0.05..2.20, so the 12.7 screw reaches 7.84..11.01 into the
# block: at least 1.5D of engagement, and never onto the tap's lead threads.
FOOT_THREAD = "#6-32"
FOOT_SCREW_LENGTH = 12.7
FOOT_SCREW_REACH_MM = (12.7 - 2.66 - 2.20, 12.7 - 1.64 - 0.05)
FOOT_THREAD_DEPTH = 11.5
FOOT_DEPTH = 14.0
if FOOT_SCREW_REACH_MM[0] < 1.5 * THREAD_MAJOR_MM[FOOT_THREAD]:
    raise AssertionError("foot screw engagement falls below 1.5D")
if FOOT_SCREW_REACH_MM[1] > FOOT_THREAD_DEPTH - 0.25:
    raise AssertionError("foot screw can reach the tap's incomplete lead threads")
# Non-bearing clearance passage from the south face into the adjuster bore. Its
# diameter matches the already-defined adjuster cup, so the shaft tip has one
# continuous envelope without reviving the removed fictional journal fit.
PINCH_THREAD = "#4-40"  # cross-bore tapped hole that squeezes the top slit
ADJUSTER_BORE_SPEC = HoleSpec(
    "tapped",
    ADJUSTER_THREAD,
    end="blind",
    depth_mm=ADJUSTER_DEPTH,
    overrides_mm={"ThreadDepth": ADJUSTER_THREAD_DEPTH},
)
ADJUSTER_BORE_DIA = blind_cut_dia_mm(ADJUSTER_BORE_SPEC)
PINCH_BORE_SPEC = HoleSpec("tapped", PINCH_THREAD)
FOOT_BORE_SPEC = HoleSpec(
    "tapped",
    FOOT_THREAD,
    end="blind",
    depth_mm=FOOT_DEPTH,
    overrides_mm={"ThreadDepth": FOOT_THREAD_DEPTH},
)
FOOT_BORE_DIA = blind_cut_dia_mm(FOOT_BORE_SPEC)
PINCH_BORE_DIA = blind_cut_dia_mm(PINCH_BORE_SPEC)
PINCH_CLEARANCE_SPEC = HoleSpec(
    "clearance",
    "#4",
    fit="normal",
    end="blind",
    depth_mm=(BLOCK_X - SLIT_W) / 2.0,
)
PINCH_CLEARANCE_DIA = blind_cut_dia_mm(PINCH_CLEARANCE_SPEC)

# Prove every web against what the PRINT permits, not just nominal CAD (U27:
# 2.0 target, 1.5 floor, at the worst case of the printed bands).  Relative
# stations chain from the adjuster axis: axis, rise and height all print .XX.
_GENERAL_1PL_MM = float(str(_config.title_block("linear_1pl")["display"]).lstrip("±"))
_GENERAL_2PL_MM = float(str(_config.title_block("linear_2pl")["display"]).lstrip("±"))
_DRILLED_HOLE_PLUS_MM = float(
    str(_config.title_block("drilled_hole")["display_plus"]).lstrip("+")
)
# Title block: REMOVE BURRS AND BREAK SHARP EDGES R0.25 OR CHAMFER 0.25 MAX.
# Where a web ends in two exposed edges (the slit mouth, the pinch-hole mouth
# under the top face) both breaks come off the same web.
EDGE_BREAK_MAX_MM = 0.25
MIN_WEB_MM = 2.0
# ASME B1.1 5/16-18 UNC-2B has no specified maximum major diameter; its
# section 5.8.2(a) reference envelope (basic major + 0.14433757P + the 2B
# pitch-diameter tolerance) stands in for the finished thread root.
_ADJ_PITCH_MM = 25.4 / 18.0
ADJUSTER_ROOT_REF_DIA = 7.9375 + 0.14433757 * _ADJ_PITCH_MM + 0.0053 * 25.4
_root_r = ADJUSTER_ROOT_REF_DIA / 2.0
_worst_clearance_radius = (
    round(PINCH_CLEARANCE_DIA, 2) + _DRILLED_HOLE_PLUS_MM
) / 2.0
_min_slit_half = (round(SLIT_W, 2) - _GENERAL_2PL_MM) / 2.0
_adjuster_major_radius = THREAD_MAJOR_MM[ADJUSTER_THREAD] / 2.0
_pinch_major_radius = THREAD_MAJOR_MM[PINCH_THREAD] / 2.0
_worst_rise = round(PINCH_RISE, 2) - _GENERAL_2PL_MM
# On the slit wall the pinch clearance hole and the adjuster thread root come
# closest where the wall is narrowest (the minimum slot width).
WORST_SLIT_MOUTH_WEB_MM = (
    _worst_rise
    - _worst_clearance_radius
    - (_root_r**2 - _min_slit_half**2) ** 0.5
    - 2.0 * EDGE_BREAK_MAX_MM
)
WORST_SCREW_ENVELOPE_GAP_MM = (
    _worst_rise - _pinch_major_radius - _adjuster_major_radius
)
WORST_TOP_LIGAMENT_MM = (
    round(BLOCK_HEIGHT, 2)
    - _GENERAL_2PL_MM
    - (round(ADJUSTER_AXIS_HEIGHT, 2) + _GENERAL_2PL_MM)
    - (round(PINCH_RISE, 2) + _GENERAL_2PL_MM)
    - _worst_clearance_radius
    - 2.0 * EDGE_BREAK_MAX_MM
)
WORST_ADJUSTER_SIDE_LIGAMENT_MM = (
    round(BLOCK_X, 1)
    - _GENERAL_1PL_MM
    - (round(BLOCK_X / 2.0, 2) + _GENERAL_2PL_MM)
    - _root_r
)
WORST_PINCH_DEPTH_LIGAMENT_MM = (
    round(BLOCK_Z, 1)
    - _GENERAL_1PL_MM
    - (round(BLOCK_Z / 2.0, 1) + _GENERAL_1PL_MM)
    - _worst_clearance_radius
)
for _name, _web in (
    ("slit-mouth web", WORST_SLIT_MOUTH_WEB_MM),
    ("top ligament", WORST_TOP_LIGAMENT_MM),
    ("adjuster side wall", WORST_ADJUSTER_SIDE_LIGAMENT_MM),
    ("pinch-depth ligament", WORST_PINCH_DEPTH_LIGAMENT_MM),
):
    if round(_web, 6) < MIN_WEB_MM:
        raise AssertionError(f"{_name} is {_web:.3f} at the printed limits (< 2.0, U27)")
if WORST_SCREW_ENVELOPE_GAP_MM <= 0.0:
    raise AssertionError("pinch screw can collide with the installed adjuster")

SURFACE_FINISHES = (
    # This face locates the adjuster block on the swing platform. Everything
    # else remains governed by the title-block CAST/MACHINED process row.
    SurfaceFinishControl("foot_seat", SEAT_UM, PlanarFace((0, -1, 0), 0.0)),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"Width", "Depth"},
    "Block": {"BlockHt"},
    "PassageProfile": {"PassageDiaDim", "PassageZ"},
    "PassageCenterReference": {"PassageCenter"},
    "PinchDepthReference": {"PinchDepthCenter"},
    "PinchRiseReference": {"PinchRise"},
    "SlitProfile": {"SlitW"},
    "TopSlit": {"SlitDepth"},
}

# Decimal places carry the general tolerance and therefore live on the model.
# U24b: the webs close at the title-block bands, so no dimension carries its
# own band. The height stack (axis, rise, overall height) and the passage
# centre print .XX; plain envelope dimensions keep .X.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BlockProfile": {"Width": 1, "Depth": 1},
    "Block": {"BlockHt": 2},
    "PassageProfile": {"PassageDiaDim": 2, "PassageZ": 2},
    "PassageCenterReference": {"PassageCenter": 2},
    "PinchDepthReference": {"PinchDepthCenter": 1},
    "PinchRiseReference": {"PinchRise": 2},
    "SlitProfile": {"SlitW": 2},
    "TopSlit": {"SlitDepth": 1},
}
DRAWING_PRECISION_BY_NAME = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if len(DRAWING_PRECISION_BY_NAME) != sum(
    len(dimensions) for dimensions in DRAWING_PRECISION.values()
):
    raise AssertionError("two features share a cone-tip-block drawing dimension name")
for _feature, _dimensions in DRAWING_PRECISION.items():
    _unmarked = sorted(set(_dimensions) - DRAWING_DIMENSIONS.get(_feature, set()))
    if _unmarked:
        raise AssertionError(
            f"DRAWING_PRECISION names unmarked {_feature} dimensions: {_unmarked}"
        )

