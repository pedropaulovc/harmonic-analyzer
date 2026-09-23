r"""Pure-data dimensional contract shared by the cone swing platform and drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_cone_swing_platform`` imports the
marked-dimension NAME map, the decimal places and the surface-finish controls
from here; ``draw_cone_swing_platform`` keeps exactly ``DRAWING_DIMENSIONS`` and
imports the plate's plan geometry from ``build_cone_swing_platform`` for its
view math.
"""

from __future__ import annotations

from _gtol_spec import PlanarFace
from _hole_spec import HoleSpec, blind_cut_dia_mm
from _surface_finish import MACHINED_UM, SEAT_UM, SurfaceFinishControl

import cone_pivot_post_spec
from crank_drive_gear_spec import OUTSIDE_DIA as CRANK_GEAR_OUTSIDE_DIA

POST_ATTACHMENT_SPACING = cone_pivot_post_spec.ATTACHMENT_SPACING
POST_BLOCK_DIA = cone_pivot_post_spec.BLOCK_DIA
POST_CONE_BORE_HEIGHT = cone_pivot_post_spec.BORE_HEIGHT


PLATE_THICKNESS = 6.35
PIVOT_BEARING_RELIEF_DIAMETER = 10.50
PIVOT_BEARING_RELIEF_DEPTH = 0.25  # Reference nominal; the finished matched fit governs.
PIVOT_HEAD_RADIAL_CLEARANCE = 0.4875
PIVOT_BEARING_THICKNESS = PLATE_THICKNESS - PIVOT_BEARING_RELIEF_DEPTH
# User decision relayed by Main, 2026-09-22: fit the actual purchased shoulder
# and finished plate; do not invent a numerical axial-clearance band.
PIVOT_RELIEF_FIT_REQUIREMENT = (
    "TOP PIVOT SPOTFACE: MATCH DEPTH TO FINISHED PLATE\n"
    "AND ACTUAL CONE-PIVOT-SCREW (McMASTER 91829A560).\n"
    "WITH SCREW SHOULDER FULLY SEATED ON BASE AND LOCK\n"
    "KNOB RELEASED, PLATFORM SHALL SWING FREELY WITHOUT\n"
    "CLAMPING, WITH MINIMAL PERCEPTIBLE AXIAL PLAY."
)
# The platform swings on the stock 1/4-in shoulder, but this occasional setup
# pivot has no measured need for a close running bearing fit.  Preserve the
# established native Hole Wizard close-clearance feature and its table size.
PIVOT_HOLE_SPEC = HoleSpec("clearance", "1/4", fit="close")
PIVOT_HOLE_DIA = blind_cut_dia_mm(PIVOT_HOLE_SPEC)


# The recentered DP25.731 gear is smaller than the intermediate DP24.74 gear;
# its complete swept OD now clears the platform top, so the obsolete scallop is
# removed and the plate remains full thickness beneath the mesh.
CRANK_GEAR_PLATFORM_CLEARANCE = POST_CONE_BORE_HEIGHT - CRANK_GEAR_OUTSIDE_DIA / 2.0
if CRANK_GEAR_PLATFORM_CLEARANCE < 0.5:
    raise AssertionError("recentered crank gear has under 0.5 mm platform air")


# The post's 1/4-in fillister clearance bores mate to these platform threads.
# The pitch is imported from the post spec; the tapped-hole size is the
# counterpart required by that purchased screw family.
POST_MOUNT_SPEC = HoleSpec("tapped", "1/4-20")
POST_MOUNT_TAP_DIA = blind_cut_dia_mm(POST_MOUNT_SPEC)


# U30 (2026-09-23): the cone tip block is held by one hidden #6-32 x 1/2
# socket head cap screw (McMaster 91251A148) coming up from under the plate
# through a lateral slot; a counterbored slot sinks the head below the slide
# face. The slot runs across the cone axis so the block can be shifted +/-2.25
# at fit-up; a shim pack under the foot sets its height. Both slots share the
# same two end centres, TIP_SCREW_HALF_TRAVEL either side of the cone axis, at
# the tip block's station (11.0 south of the pivot, from the drive-train
# layout: PIVOT_STATION = TIP_BLOCK_STATION + 11.0).
TIP_SCREW_LOCAL_Z = -11.0
TIP_SCREW_HALF_TRAVEL = 2.0
TIP_SCREW_MAJOR = 3.505  # #6-32 basic major
TIP_SCREW_HEAD_DIA = (5.54, 5.74)  # ASME B18.3 #6 SHCS head min/max
TIP_SCREW_HEAD_H_MAX = 3.505
# The slot widths are cut in one pass by an end mill of that size, so they
# carry the same one-sided +0.10/0 band as the title block's DRILLED HOLES
# row: the cutter makes the size, the machinist holds nothing tight.
TIP_SLOT_W = 4.0
TIP_CBORE_W = 6.5
TIP_SLOT_W_BAND = (0.0, 0.10)
TIP_CBORE_DEPTH = 4.2  # .XX
_XX = 0.51
TIP_SLOT_SCREW_CLEARANCE = TIP_SLOT_W - TIP_SCREW_MAJOR
TIP_SLOT_HEAD_BEARING = (
    TIP_SCREW_HEAD_DIA[0] - (TIP_SLOT_W + TIP_SLOT_W_BAND[1])
) / 2.0
TIP_CBORE_HEAD_CLEARANCE = TIP_CBORE_W - TIP_SCREW_HEAD_DIA[1]
TIP_HEAD_RECESS = TIP_CBORE_DEPTH - _XX - TIP_SCREW_HEAD_H_MAX
TIP_LEDGE_RANGE = (
    PLATE_THICKNESS - TIP_CBORE_DEPTH - _XX,
    PLATE_THICKNESS - TIP_CBORE_DEPTH + _XX,
)
if TIP_SLOT_SCREW_CLEARANCE < 0.25:
    raise AssertionError("tip-block screw slot does not clear the #6-32 major")
if TIP_SLOT_HEAD_BEARING < 0.5:
    raise AssertionError("tip-block screw head bears on under 0.5 mm per side")
if TIP_CBORE_HEAD_CLEARANCE < 0.25:
    raise AssertionError("tip-block counterbore slot does not clear the screw head")
if TIP_HEAD_RECESS < 0.1:
    raise AssertionError("tip-block screw head can stand proud of the slide face")
if TIP_LEDGE_RANGE[0] < 1.5:
    raise AssertionError("tip-block counterbore ledge is below the U27 1.5 floor")


# Only functional sliding/locating surfaces carry roughness.  The existing
# close-clearance pivot hole needs no bearing-finish control; the top locates
# the post and tip block, and the underside slides on the harmonic-base deck.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "post_seat", SEAT_UM, PlanarFace((0, 1, 0), PLATE_THICKNESS)
    ),
    SurfaceFinishControl(
        "base_slide", MACHINED_UM, PlanarFace((0, -1, 0), 0.0)
    ),
)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The pivot-hole centre is the layout origin: every plan corner,
# both post-mount taps and the lock notch are located from it in the plate's own
# axes (station along the cone axis, offset across it), so a shop lays the whole
# plate out from one scribed centre.  Corner radii come off their fillets. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateProfile": {
        "NorthEastX",
        "NorthEdgeZ",
        "NorthWestX",
        "SouthWestX",
        "PlateLenDim",
        "SouthEastX",
    },
    "Plate": {"PlateThk"},
    "PivotBearingReliefProfile": {"PivotBearingReliefDia"},
    "PivotBearingRelief": {"PivotBearingReliefDepth"},
    "PostMountHoles": {
        "PostMountWestX",
        "PostMountWestZ",
        "PostMountEastX",
        "PostMountEastZ",
    },
    "LockNotchCapEProfile": {"CapECx", "CapECz", "CapEDia"},
    "TipScrewSlotProfile": {"TipSlotEastCx", "TipSlotWestCx", "TipSlotZ", "TipSlotW"},
    "TipScrewCboreProfile": {"TipCboreW"},
    "CornerNE": {"CornerNER"},
    "CornerNW": {"CornerNWR"},
    "CornerSW": {"CornerSWR"},
    "CornerSE": {"CornerSER"},
}

# Decimal places ARE the tolerance statement (drawing-simplicity policy rule
# 2), so the MODEL owns them: build_cone_swing_platform applies this map to the
# .SLDPRT and draw_cone_swing_platform only reads it back. The whole plate
# outline prints one place (+/-0.8): the east edge at the swing stop and the
# west edge at the notch mouth spend the disengaged lock-collar margin, which
# build_cone_swing_platform.DISENGAGE_COLLAR_MARGIN sizes to keep >= 2.0 mm
# at this band.  Relief diameter, tapped-hole pattern and notch stay at the
# .XX grade. Relief
# depth is a reference nominal governed by the matched fit above. The Hole
# Wizard owns the pivot-hole size/callout.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PlateProfile": {
        "NorthEastX": 1,
        "NorthEdgeZ": 1,
        "NorthWestX": 1,
        "SouthWestX": 1,
        "PlateLenDim": 1,
        "SouthEastX": 1,
    },
    "Plate": {"PlateThk": 2},
    "PivotBearingReliefProfile": {"PivotBearingReliefDia": 2},
    "PivotBearingRelief": {"PivotBearingReliefDepth": 2},
    "PostMountHoles": {
        "PostMountWestX": 2,
        "PostMountWestZ": 2,
        "PostMountEastX": 2,
        "PostMountEastZ": 2,
    },
    "LockNotchCapEProfile": {"CapECx": 2, "CapECz": 2, "CapEDia": 2},
    # The slot ends are .XX so the +/-2.25 fit-up travel keeps >= +/-1.74.
    "TipScrewSlotProfile": {
        "TipSlotEastCx": 2,
        "TipSlotWestCx": 2,
        "TipSlotZ": 2,
        "TipSlotW": 1,
    },
    "TipScrewCboreProfile": {"TipCboreW": 1},
    "CornerNE": {"CornerNER": 1},
    "CornerNW": {"CornerNWR": 1},
    "CornerSW": {"CornerSWR": 1},
    "CornerSE": {"CornerSER": 1},
}


_PRECISION_NAMES = [
    (feature, name) for feature, names in DRAWING_PRECISION.items() for name in names
]
if any(
    name not in DRAWING_DIMENSIONS.get(feature, frozenset())
    for feature, name in _PRECISION_NAMES
):
    raise AssertionError("DRAWING_PRECISION names a dimension the part never marks")
if any(
    name not in {name for names in DRAWING_PRECISION.values() for name in names}
    for names in DRAWING_DIMENSIONS.values()
    for name in names
):
    raise AssertionError("a marked dimension prints without part-authored places")
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: DRAWING_PRECISION[feature][name] for feature, name in _PRECISION_NAMES
}
if len(DRAWING_PRECISION_BY_NAME) != len(_PRECISION_NAMES):
    raise AssertionError("DRAWING_PRECISION repeats a dimension name across features")


# View scales differ from the sheet scale and therefore remain property-linked
# labels.  The split plans are named so each dimension set has an unambiguous
# owner; these are view captions, not manufacturing notes.
PROFILE_VIEW_NOTE = "PLATE PROFILE — SCALE 1:2"
FEATURE_VIEW_NOTE = "HOLE LOCATIONS — SCALE 1:2"
NOTCH_VIEW_NOTE = "LOCK NOTCH — SCALE 1:2"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:3"
