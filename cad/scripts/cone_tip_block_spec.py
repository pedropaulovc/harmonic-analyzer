r"""Pure-data dimensional contract shared by the cone-tip-block part and drawing."""

from __future__ import annotations

import math

import _config
from _fit_limits import deviations
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
# 90-degree countersink on each mouth to Ø5.0, just over the 4.826 major, so
# the first thread starts full rather than on a feather edge (Main,
# 2026-09-24).  Its depth is the 45-degree break on the tap drill.
ADJUSTER_CSK_DIA = 5.0
# ASME B1.1 #10-32 UNF-2B minimum minor diameter (0.1560 in): the tightest
# envelope the shaft tip passes through.
ADJUSTER_MINOR_MIN_DIA = 0.1560 * 25.4
SHAFT_PASSAGE_DIA = ADJUSTER_MINOR_MIN_DIA
# I31 option 1 (Main, 2026-09-25): the block is held down through a south
# foot flange.  One #6-32 x 5/8 hex-head screw (McMaster 93075A150) rises from
# the swing platform's counterbored lateral slot, through the fit-up shim pack
# and an axial slot in the flange, into a #6-32 nylon-insert locknut
# (McMaster 90631A007) on the flange top.  The plate slot lets the block move
# across the cone axis, the flange slot along it, so the block sits wherever
# the shaft tip puts it and the screw clamps it there; the counterbore slot's
# walls hold the hex head, so the nut is turned from above alone.
FOOT_THREAD = "#6-32"
FOOT_SHIM_RANGE_MM = (0.05, 2.20)
PINCH_THREAD = "#4-40"  # cross-bore tapped hole that squeezes the top slit
ADJUSTER_BORE_SPEC = HoleSpec("tapped", ADJUSTER_THREAD)
ADJUSTER_BORE_DIA = blind_cut_dia_mm(ADJUSTER_BORE_SPEC)
ADJUSTER_CSK = (ADJUSTER_CSK_DIA - ADJUSTER_BORE_DIA) / 2.0
if ADJUSTER_CSK_DIA < THREAD_MAJOR_MM[ADJUSTER_THREAD]:
    raise AssertionError("adjuster countersink ends inside the thread major")
PINCH_BORE_SPEC = HoleSpec("tapped", PINCH_THREAD)
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
# The adjuster's working window, cup rim measured in from the north face:
# shallow end = 1.5D of full thread under the north countersink; deep end = the
# cup rim still on full thread above the south countersink with the block at
# its .X-short depth.  Fit-up sets the block so the cup seats at
# ADJUSTER_EMBED; end-play turns (1/8 turn = 0.099) move it inside the window.
ADJUSTER_EMBED_WINDOW = (
    1.5 * THREAD_MAJOR_MM[ADJUSTER_THREAD] + ADJUSTER_CSK,
    round(BLOCK_Z, 1) - _GENERAL_1PL_MM - ADJUSTER_CSK,
)
if not (
    ADJUSTER_EMBED_WINDOW[0]
    <= ADJUSTER_EMBED - _GENERAL_1PL_MM
    <= ADJUSTER_EMBED + _GENERAL_1PL_MM
    <= ADJUSTER_EMBED_WINDOW[1]
):
    raise AssertionError("adjuster embed band leaves its working window")

# I31 heel relief (Main, 2026-09-25): the cone pivot screw's head (McMaster
# 91829A560, Ø9.525 x 4.7625) stands on the platform top 11.0 north of the
# block centre, only 0.2375 off the block's north face at nominal, and the
# block's north face moves north with the shaft tip (Sec4End, .X) at fit-up.
# A rectangular step along the whole north-bottom edge clears the head: the
# drive-train builder derives the required depth (tip travel + head float in
# the pivot hole + 0.20 air - nominal gap) and height (head top above the
# lowest foot) from the live parts and asserts these printed .XX values cover
# them (build_drive_train_assembly, "heel relief").
HEEL_RELIEF_DEPTH = 1.53
HEEL_RELIEF_HEIGHT = 5.56
# --- I31 foot flange and its axial slot --------------------------------------
# The purchased hardware the flange is sized for, from the McMaster product
# pages (read 2026-09-25): 93075A150 is a 6-32 x 5/8 low-strength zinc-plated
# steel hex head screw, head 1/4 wide x 3/32 high (ASME B18.6.3); 90631A007 is
# a 6-32 zinc-plated steel nylon-insert locknut, 5/16 wide x 11/64 high.  The
# catalogue gives no insert height, so the whole 11/64 counts as nut and the
# screw must stand a full pitch past its top face.
HOLDDOWN_SCREW_LENGTH = 0.625 * 25.4
HOLDDOWN_NUT_AF = 5.0 / 16.0 * 25.4
HOLDDOWN_NUT_H = 11.0 / 64.0 * 25.4
# Sharp corners: the largest the nut can sweep.
HOLDDOWN_NUT_AC = HOLDDOWN_NUT_AF / (3.0**0.5 / 2.0)
HOLDDOWN_PITCH_MM = 25.4 / 32.0
_HOLDDOWN_MAJOR_MM = THREAD_MAJOR_MM[FOOT_THREAD]
_BAND_BY_PLACES = {1: _GENERAL_1PL_MM, 2: _GENERAL_2PL_MM}
# The flange slot is one pass of a 5/32 end mill, so its width carries the
# cutter's one-sided +0.10/0 band (the title block's drilled-hole row),
# written (upper, lower) like every _fit_limits band and only ever read
# through _fit_limits.deviations, here and on the model -- never by index.
FLANGE_SLOT_W = 5.0 / 32.0 * 25.4
FLANGE_SLOT_W_BAND = (_DRILLED_HOLE_PLUS_MM, 0.0)
_FLANGE_SLOT_W_LOWER, _FLANGE_SLOT_W_UPPER = deviations(FLANGE_SLOT_W_BAND)
FLANGE_SLOT_W_MIN = FLANGE_SLOT_W + _FLANGE_SLOT_W_LOWER
FLANGE_SLOT_W_MAX = FLANGE_SLOT_W + _FLANGE_SLOT_W_UPPER
FLANGE_SLOT_FLOAT = (FLANGE_SLOT_W_MAX - _HOLDDOWN_MAJOR_MM) / 2.0
# Fit-up chain: how far the screw can sit from where the block needs it,
# along the axis.  The block's north face follows the shaft tip (the cup seats
# at ADJUSTER_EMBED), so the chain runs tip -> north face -> south face ->
# flange-slot centre -> screw -> plate slot centre: the shaft's overall
# length Sec4End (.X; asserted against the shaft spec in
# build_drive_train_assembly), the block Depth (.X), FlangeSlotZ (.X), the
# plate's TipSlotZ station (.XX; asserted against the platform spec there
# too) and the screw's float across the plate's 4.0 +0.10 slot.
SHAFT_OVERALL_LENGTH_PLACES = 1
BLOCK_DEPTH_PLACES = 1
FLANGE_SLOT_Z_PLACES = 1
PLATE_TIP_SLOT_Z_PLACES = 2
PLATE_TIP_SLOT_W = 4.0
PLATE_TIP_SLOT_W_PLUS = _DRILLED_HOLE_PLUS_MM
PLATE_TIP_SLOT_FLOAT = (
    PLATE_TIP_SLOT_W + PLATE_TIP_SLOT_W_PLUS - _HOLDDOWN_MAJOR_MM
) / 2.0
FIT_UP_CHAIN_MM = (
    _BAND_BY_PLACES[SHAFT_OVERALL_LENGTH_PLACES]
    + _BAND_BY_PLACES[BLOCK_DEPTH_PLACES]
    + _BAND_BY_PLACES[FLANGE_SLOT_Z_PLACES]
    + _BAND_BY_PLACES[PLATE_TIP_SLOT_Z_PLACES]
    + PLATE_TIP_SLOT_FLOAT
)
FIT_UP_MARGIN_MM = 1.0
FLANGE_SLOT_HALF_TRAVEL = FIT_UP_CHAIN_MM + FIT_UP_MARGIN_MM
# The slot prints its arc-centre spacing (.XX), rounded up.
FLANGE_SLOT_CTOC = math.ceil(2.0 * FLANGE_SLOT_HALF_TRAVEL * 100.0 - 1e-6) / 100.0
_SLOT_HALF_CTOC = (
    (FLANGE_SLOT_CTOC - _GENERAL_2PL_MM) / 2.0,
    (FLANGE_SLOT_CTOC + _GENERAL_2PL_MM) / 2.0,
)
if _SLOT_HALF_CTOC[0] + FLANGE_SLOT_FLOAT < FIT_UP_CHAIN_MM:
    raise AssertionError("flange slot no longer covers the fit-up chain at its short limit")
FLANGE_SLOT_LEN = FLANGE_SLOT_CTOC + FLANGE_SLOT_W
# The nut sits on the flange top next to the body's south wall.  At the
# slot's north end (spacing at its long limit, the screw floating north,
# FlangeSlotZ short) its corners keep NUT_WALL_AIR off the wall.
NUT_WALL_AIR = 0.5
FLANGE_SLOT_Z = (
    math.ceil(
        (
            HOLDDOWN_NUT_AC / 2.0
            + NUT_WALL_AIR
            + _BAND_BY_PLACES[FLANGE_SLOT_Z_PLACES]
            + _SLOT_HALF_CTOC[1]
            + FLANGE_SLOT_FLOAT
        )
        * 10.0
        - 1e-6
    )
    / 10.0
)
# From the south face; the flange's own length is .X like the body's plan.
_SLOT_SOUTH_EDGE_MAX = (
    FLANGE_SLOT_Z
    + _BAND_BY_PLACES[FLANGE_SLOT_Z_PLACES]
    + _SLOT_HALF_CTOC[1]
    + (FLANGE_SLOT_W_MAX) / 2.0
)
FLANGE_LEN = (
    math.ceil((_SLOT_SOUTH_EDGE_MAX + MIN_WEB_MM + _GENERAL_1PL_MM) * 10.0 - 1e-6) / 10.0
)
# The slot is on the block's centre plane, located .XX from the +X face (the
# PassageCenter datum); the flange is the block's full width (.X).
FLANGE_SLOT_X = BLOCK_X / 2.0
WORST_FLANGE_SIDE_WEB_MM = min(
    round(FLANGE_SLOT_X, 2) - _GENERAL_2PL_MM,
    round(BLOCK_X, 1) - _GENERAL_1PL_MM - (round(FLANGE_SLOT_X, 2) + _GENERAL_2PL_MM),
) - (FLANGE_SLOT_W_MAX) / 2.0
WORST_FLANGE_END_WEB_MM = FLANGE_LEN - _GENERAL_1PL_MM - _SLOT_SOUTH_EDGE_MAX
WORST_FLANGE_ROOT_WEB_MM = (
    FLANGE_SLOT_Z
    - _BAND_BY_PLACES[FLANGE_SLOT_Z_PLACES]
    - _SLOT_HALF_CTOC[1]
    - (FLANGE_SLOT_W_MAX) / 2.0
)
WORST_NUT_WALL_AIR_MM = (
    FLANGE_SLOT_Z
    - _BAND_BY_PLACES[FLANGE_SLOT_Z_PLACES]
    - _SLOT_HALF_CTOC[1]
    - FLANGE_SLOT_FLOAT
    - HOLDDOWN_NUT_AC / 2.0
)
# The nut bears on the flange beside the slot without a washer.
NUT_BEARING_MM = (HOLDDOWN_NUT_AF - (FLANGE_SLOT_W_MAX)) / 2.0
for _name, _web in (
    ("flange side web", WORST_FLANGE_SIDE_WEB_MM),
    ("flange end web", WORST_FLANGE_END_WEB_MM),
    ("flange root web", WORST_FLANGE_ROOT_WEB_MM),
):
    if round(_web, 6) < MIN_WEB_MM:
        raise AssertionError(f"{_name} is {_web:.3f} at the printed limits (< 2.0, U27)")
if WORST_NUT_WALL_AIR_MM < NUT_WALL_AIR - 1e-9:
    raise AssertionError("the hold-down nut can reach the block's south wall")
if NUT_BEARING_MM < 1.0:
    raise AssertionError("the hold-down nut bears on under 1.0 beside the flange slot")
if FLANGE_SLOT_W_MIN - _HOLDDOWN_MAJOR_MM < 0.25:
    raise AssertionError("flange slot does not clear the #6-32 major")
# Flange thickness (.XX): with the thickest ledge under the head (the
# platform's stock-plate and counterbore bands, cone_swing_platform_spec
# TIP_LEDGE_RANGE, asserted equal in build_drive_train_assembly) and the
# thickest shim stack, the 5/8 screw still stands a pitch past the nut.
FLANGE_T = 3.50
HOLDDOWN_LEDGE_RANGE_MM = (2.71, 3.99)
HOLDDOWN_PROTRUSION_MM = (
    HOLDDOWN_SCREW_LENGTH
    - (
        HOLDDOWN_LEDGE_RANGE_MM[1]
        + FOOT_SHIM_RANGE_MM[1]
        + FLANGE_T
        + _GENERAL_2PL_MM
        + HOLDDOWN_NUT_H
    ),
    HOLDDOWN_SCREW_LENGTH
    - (
        HOLDDOWN_LEDGE_RANGE_MM[0]
        + FOOT_SHIM_RANGE_MM[0]
        + FLANGE_T
        - _GENERAL_2PL_MM
        + HOLDDOWN_NUT_H
    ),
)
if HOLDDOWN_PROTRUSION_MM[0] < HOLDDOWN_PITCH_MM:
    raise AssertionError(
        f"hold-down screw stands {HOLDDOWN_PROTRUSION_MM[0]:.3f} past the nut at "
        "the thickest stack (< one pitch past the nylon insert)"
    )
# The relief stays in the foot, well under the adjuster thread and its
# countersink.
if (
    HEEL_RELIEF_HEIGHT + _GENERAL_2PL_MM
    > ADJUSTER_AXIS_HEIGHT - ADJUSTER_CSK_DIA / 2.0 - MIN_WEB_MM
):
    raise AssertionError("heel relief rises into the adjuster countersink")

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
    # I31 heel relief: depth from the north face, height from the foot.
    "HeelReliefProfile": {"HeelReliefDepth", "HeelReliefHt"},
    # I31 foot flange: its length past the south face and its thickness; the
    # axial slot's width and arc-centre spacing, located from the +X face and
    # the south face (hidden reference sketches, like the old foot tap's).
    "FlangeProfile": {"FlangeLen"},
    "Flange": {"FlangeT"},
    "FlangeSlotProfile": {"FlangeSlotW", "FlangeSlotCtoC"},
    "FlangeSlotXReference": {"FlangeSlotX"},
    "FlangeSlotZReference": {"FlangeSlotZ"},
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
    "HeelReliefProfile": {"HeelReliefDepth": 2, "HeelReliefHt": 2},
    "FlangeProfile": {"FlangeLen": 1},
    "Flange": {"FlangeT": 2},
    # The width is the 5/32 cutter's (+0.10/0, set on the model); the spacing
    # is .XX (the fit-up travel spends its band).
    "FlangeSlotProfile": {"FlangeSlotW": 2, "FlangeSlotCtoC": 2},
    "FlangeSlotXReference": {"FlangeSlotX": 2},
    "FlangeSlotZReference": {"FlangeSlotZ": FLANGE_SLOT_Z_PLACES},
}
# The fit-up chain above reads these grades; the print must carry them.
if (
    DRAWING_PRECISION["BlockProfile"]["Depth"] != BLOCK_DEPTH_PLACES
    or DRAWING_PRECISION["FlangeSlotZReference"]["FlangeSlotZ"] != FLANGE_SLOT_Z_PLACES
):
    raise AssertionError("the flange fit-up chain reads grades the print does not carry")
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

