r"""Pure-data dimensional contract shared by the cone-tip-block part and drawing."""

from __future__ import annotations

import _config
from _gtol_spec import PlanarFace
from _hole_spec import THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm
from _surface_finish import SEAT_UM, SurfaceFinishControl


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
# Rule-12 E11/W1 (Main, 2026-09-24): a #10-32 x 3/8 cup set screw (McMaster
# 94025A164) in a thread tapped THROUGH the block, a 90-degree countersink at
# both mouths, and no block growth.  A through tap has no floor to break out
# and no tap lead to deduct; the shaft tip enters through the same thread.
# The cup rim sits ADJUSTER_EMBED in from the north face (the 3/8 screw stands
# 0.03 proud).  Worst case at the printed bands: the tip station can come
# 0.8 north (the shaft's .X overall length), and the north countersink eats
# its depth, so engagement is min(L, embed - 0.8) - countersink >= 1.5D.  The
# block's own axial location is set at fit-up (integration item "tip-block
# axial fit-up slot"), not stacked.
ADJUSTER_THREAD = "#10-32"
ADJUSTER_SCREW_LENGTH = 9.525
ADJUSTER_EMBED = 9.5
# 45-degree break on each tap-drill mouth: a 90-degree countersink to about the
# thread major, so the first full thread starts under it.
ADJUSTER_CSK = 0.4
# ASME B1.1 #10-32 UNF-2B minimum minor diameter (0.1560 in): the tightest
# envelope the shaft tip passes through.
ADJUSTER_MINOR_MIN_DIA = 0.1560 * 25.4
SHAFT_PASSAGE_DIA = ADJUSTER_MINOR_MIN_DIA
# U30 hold-down: one #6-32 x 1/2 button-head socket cap screw (McMaster
# 91255A148, head 0.262 x 0.073; rule-12 W22 swapped it in for the taller
# socket head) comes up through the platform's counterbored lateral slot into
# the foot centre. Under the head the platform leaves a ledge of stock
# thickness (6.35 +/-0.13, user ruling U41: "1/4 PLATE AS SUPPLIED") less the
# 2.80 .XX counterbore depth, 2.91..4.19
# (cone_swing_platform_spec.TIP_LEDGE_RANGE), and the fit-up shim pack is
# 0.05..2.20, so the 12.7 screw reaches 6.31..9.74 into the block (1.80D at
# the short end).  Judged at the printed worst case: engagement >= 1.5D, and
# the deepest reach stays on full thread -- ThreadDepth .X, so 0.8 under
# nominal.
FOOT_THREAD = "#6-32"
FOOT_SCREW_LENGTH = 12.7
FOOT_LEDGE_RANGE_MM = (2.91, 4.19)
FOOT_SHIM_RANGE_MM = (0.05, 2.20)
FOOT_SCREW_REACH_MM = (
    FOOT_SCREW_LENGTH - FOOT_LEDGE_RANGE_MM[1] - FOOT_SHIM_RANGE_MM[1],
    FOOT_SCREW_LENGTH - FOOT_LEDGE_RANGE_MM[0] - FOOT_SHIM_RANGE_MM[0],
)
FOOT_THREAD_DEPTH = 12.5
# The tap drill runs 1.5P past the deepest full thread at the printed limits
# (both depths .X), so a plug tap's lead never eats the full-thread depth.
FOOT_DEPTH = 15.5
_FOOT_PITCH_MM = 25.4 / 32.0
if FOOT_SCREW_REACH_MM[0] < 1.5 * THREAD_MAJOR_MM[FOOT_THREAD]:
    raise AssertionError("foot screw engagement falls below 1.5D")
if FOOT_SCREW_REACH_MM[1] > FOOT_THREAD_DEPTH - 0.8 - 0.25:
    raise AssertionError("foot screw can reach the tap's incomplete lead threads")
if (FOOT_DEPTH - 0.8) - (FOOT_THREAD_DEPTH + 0.8) < 1.5 * _FOOT_PITCH_MM:
    raise AssertionError("foot tap drill leaves no lead room past the full thread")
PINCH_THREAD = "#4-40"  # cross-bore tapped hole that squeezes the top slit
ADJUSTER_BORE_SPEC = HoleSpec("tapped", ADJUSTER_THREAD)
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
# ASME B1.1 #10-32 UNF-2B has no specified maximum major diameter; its
# section 5.8.2(a) reference envelope (basic major + 0.14433757P + the 2B
# pitch-diameter tolerance, 0.1736 - 0.1697 in) stands in for the finished
# thread root.
_ADJ_PITCH_MM = 25.4 / 32.0
ADJUSTER_ROOT_REF_DIA = (
    THREAD_MAJOR_MM[ADJUSTER_THREAD] + 0.14433757 * _ADJ_PITCH_MM + 0.0039 * 25.4
)
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
# Rule-12 E1: the #4-40 x 1/2 pinch screw (McMaster 90280A110, 12.7 under the
# head) seats on the +X face.  PassageCenter prints .XX from that same face,
# so the near jaw is at most PassageCenter + band - (SlitW - band)/2 and the
# far jaw keeps >= 1.5D of thread; the tip stays short of the -X face.
PINCH_SCREW_LENGTH = 12.7
WORST_PINCH_NEAR_JAW_MM = (
    round(BLOCK_X / 2.0, 2) + _GENERAL_2PL_MM - _min_slit_half
)
WORST_PINCH_ENGAGEMENT_MM = PINCH_SCREW_LENGTH - WORST_PINCH_NEAR_JAW_MM
if WORST_PINCH_ENGAGEMENT_MM < 1.5 * THREAD_MAJOR_MM[PINCH_THREAD]:
    raise AssertionError(
        f"pinch screw far-jaw engagement {WORST_PINCH_ENGAGEMENT_MM:.2f} < 1.5D"
    )
if PINCH_SCREW_LENGTH > round(BLOCK_X, 1) - _GENERAL_1PL_MM:
    raise AssertionError("pinch screw can stand proud of the far (-X) face")
# E11/W1: the through thread is the whole block, so the screw is the limit.
WORST_ADJUSTER_ENGAGEMENT_MM = (
    min(ADJUSTER_SCREW_LENGTH, ADJUSTER_EMBED - _GENERAL_1PL_MM) - ADJUSTER_CSK
)
if WORST_ADJUSTER_ENGAGEMENT_MM < 1.5 * THREAD_MAJOR_MM[ADJUSTER_THREAD]:
    raise AssertionError(
        f"adjuster engagement {WORST_ADJUSTER_ENGAGEMENT_MM:.2f} < 1.5D at the "
        "printed worst case"
    )
# The cup rim stays inside the block with a full thread past the south
# countersink at the far end of the embed band.
if ADJUSTER_EMBED + _GENERAL_1PL_MM > round(BLOCK_Z, 1) - _GENERAL_1PL_MM - ADJUSTER_CSK:
    raise AssertionError("adjuster cup can leave the south thread at the printed limits")

SURFACE_FINISHES = (
    # This face locates the adjuster block on the swing platform. Everything
    # else remains governed by the title-block CAST/MACHINED process row.
    SurfaceFinishControl("foot_seat", SEAT_UM, PlanarFace((0, -1, 0), 0.0)),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"Width", "Depth"},
    "Block": {"BlockHt"},
    # E11/W1: the through thread replaced the passage sketch that used to
    # carry the axis height; a construction reference owns it now.
    "AxisHeightReference": {"AxisHeight"},
    "PassageCenterReference": {"PassageCenter"},
    "PinchDepthReference": {"PinchDepthCenter"},
    "PinchRiseReference": {"PinchRise"},
    "SlitProfile": {"SlitW"},
    "TopSlit": {"SlitDepth"},
    # The #6-32 foot tap, located from two finished faces (review
    # 2026-09-23: centre marks alone are not a location).
    "FootTapXReference": {"FootTapX"},
    "FootTapZReference": {"FootTapZ"},
}

# Decimal places carry the general tolerance and therefore live on the model.
# U24b: the webs close at the title-block bands, so no dimension carries its
# own band. The height stack (axis, rise, overall height) and the axis
# centre print .XX; plain envelope dimensions keep .X.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BlockProfile": {"Width": 1, "Depth": 1},
    "Block": {"BlockHt": 2},
    "AxisHeightReference": {"AxisHeight": 2},
    "PassageCenterReference": {"PassageCenter": 2},
    "PinchDepthReference": {"PinchDepthCenter": 1},
    "PinchRiseReference": {"PinchRise": 2},
    "SlitProfile": {"SlitW": 2},
    "TopSlit": {"SlitDepth": 1},
    # A centred tap in a 15 x 12 foot: .X leaves 4.95 of wall to the edge.
    "FootTapXReference": {"FootTapX": 1},
    "FootTapZReference": {"FootTapZ": 1},
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

