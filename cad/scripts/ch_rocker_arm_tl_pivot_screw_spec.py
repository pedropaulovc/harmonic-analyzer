r"""Pure-data contract for the rocker arm's pivot shoulder screw (MHA-CH-006-TL-06).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). In the
rocker arm's S4 profile hold (prechips S4) the shoulder passes through the
part's reamed pivot bore (datum A) into the profile plate's 6.500 H7 locating
bore, the M5 thread screws into the plate's tap, and the head clamps the
MHA-CH-006-TL-07 washer onto the upper hub face. The Ø8 head is the S4 X/Y
pickup and carries the outline-template bush.

Route (shop-additions.md section 2, binding): unhardened pre-hardened 4140;
shoulder and head turned and ring-lapped in ONE chucking from the bar, so
their coaxiality rides on the spindle axis; slot drive (no hex broach in the
shop); no heat treatment.

Frame (the inventory's fixture frame, rocker-inv:1735-1748): origin on the
pivot axis at the upper hub face, +Z up; S4 poses it at the rocker frame-A
origin. The washer sits Z0..1.5, the head Z1.5..5.5, the shoulder Z-20..1.5
and the thread Z-28.5..-20. Axial sizes print from the faced head top.
"""

from __future__ import annotations

import ch_rocker_arm_spec as rocker
from _feature_requirements import ExportFeature, limits
from _hole_spec import THREAD_MAJOR_MM
from _gtol_spec import CylinderFace, PlanarFace
from _printed_tolerance import printed_band_mm
from _surface_finish import GROUND_UM, MACHINED_UM, SurfaceFinishControl

# --- stations (fixture frame, mm) -------------------------------------------
WASHER_THICK = 1.5  # the MHA-CH-006-TL-07 washer under the head
HEAD_DIA = 8.0
HEAD_LENGTH = 4.0
SHOULDER_DIA = 6.49
SHOULDER_LENGTH = 21.5
# Shop-to-shop thread follows the HA US-customary fastener policy (UNC, 2A per
# the title block): the inventory's M5x0.8 maps to #10-24. The thread is 8.5
# long, not the inventory's 7.2, so with the shoulder ending 1 mm above the
# plate bore floor it engages 7.5 = 1.55D in the plate's tap (rule of 1.5D;
# MHA-CH-006-TL-02 taps 10.0 full thread below that floor).
THREAD_SIZE = "#10-24"
THREAD_CALLOUT = f"{THREAD_SIZE} UNC"
THREAD_MODEL_DIA = THREAD_MAJOR_MM[THREAD_SIZE]
THREAD_LENGTH = 8.5
PLATE_FLOOR_GAP = 1.0
ENGAGEMENT_MIN_D = 1.5
if THREAD_LENGTH - PLATE_FLOOR_GAP < ENGAGEMENT_MIN_D * THREAD_MODEL_DIA:
    raise AssertionError("pivot-screw thread engages under 1.5D in the plate")
TIP_CHAMFER = 0.5
CHAMFER_CALLOUT = "X 45 DEG"
SLOT_WIDTH = 1.0
# 1.2 deep (route said 1.5): the head and slot depth print at two places so
# the worst head left behind the slot stays over the rule-12 floor.
SLOT_DEPTH = 1.2

UNDERHEAD_Z = WASHER_THICK
HEAD_TOP_Z = UNDERHEAD_Z + HEAD_LENGTH
SHOULDER_END_Z = round(UNDERHEAD_Z - SHOULDER_LENGTH, 6)
TIP_Z = round(SHOULDER_END_Z - THREAD_LENGTH, 6)
# Axial sizes from the one faced end, the head top.
SHOULDER_END_STATION = HEAD_LENGTH + SHOULDER_LENGTH
OVERALL_LENGTH = round(SHOULDER_END_STATION + THREAD_LENGTH, 6)

# --- locating fits ------------------------------------------------------------
# The shoulder locates in the rocker arm's reamed pivot bore (datum A,
# PIVOT_HOLE_BAND) and in the profile plate's 6.500 H7 locating bore. The plate
# (MHA-CH-006-TL-02, ch_rocker_arm_tl_profile_fixture_spec LOCATING_BORE_DIA
# 6.5 / LOCATING_BORE_BAND (0.012, 0.0)) lands on a sibling branch, so its
# bore is the inventory value here (rocker-inv:1738-1739; make-data.md 7.4).
PLATE_BORE_LIMITS = (6.500, 6.512)
SHOULDER_BAND = (0.0, -0.005)  # (upper, lower): 6.485-6.490, ring-lapped
SHOULDER_PLACES = 3
_SHOULDER_MAX = SHOULDER_DIA + SHOULDER_BAND[0]
_SHOULDER_MIN = SHOULDER_DIA + SHOULDER_BAND[1]
_BORE_A_MIN = rocker.PIVOT_HOLE_DIA + rocker.PIVOT_HOLE_BAND[1]
_BORE_A_MAX = rocker.PIVOT_HOLE_DIA + rocker.PIVOT_HOLE_BAND[0]
# Inventory fit: 0.010-0.045 in reamed A, 0.010-0.027 in the plate bore.
BORE_A_CLEARANCE = (round(_BORE_A_MIN - _SHOULDER_MAX, 6), round(_BORE_A_MAX - _SHOULDER_MIN, 6))
PLATE_CLEARANCE = (
    round(PLATE_BORE_LIMITS[0] - _SHOULDER_MAX, 6),
    round(PLATE_BORE_LIMITS[1] - _SHOULDER_MIN, 6),
)
LOCATING_CLEARANCE_MIN = 0.010
if min(BORE_A_CLEARANCE[0], PLATE_CLEARANCE[0]) < LOCATING_CLEARANCE_MIN - 1e-9:
    raise AssertionError("pivot-screw shoulder does not slide into bore A and the plate bore")

# The head carries the outline-template bush. No template constant exists
# yet, so its bore is the inventory value (rocker-inv:1752: 8.000-8.015).
TEMPLATE_BUSH_BORE_LIMITS = (8.000, 8.015)
HEAD_BAND = (0.0, -0.005)  # (upper, lower): 7.995-8.000, ring-lapped
HEAD_PLACES = 3
if HEAD_DIA + HEAD_BAND[0] > TEMPLATE_BUSH_BORE_LIMITS[0] + 1e-9:
    raise AssertionError("pivot-screw head does not enter the outline-template bush")

# The head bears on the washer, never on the hub: the shoulder passes the
# washer bore (the washer spec checks its side of this).
if HEAD_DIA <= SHOULDER_DIA:
    raise AssertionError("pivot-screw head must overhang the shoulder to clamp")

# Ra 0.8 is reserved for pivot-screw shoulders: the lapped locating shoulder.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "pivot_shoulder",
        GROUND_UM,
        CylinderFace(SHOULDER_DIA, contains_z_mm=(UNDERHEAD_Z + SHOULDER_END_Z) / 2.0),
    ),
    # The head slides in the template bush: machined, not the reserved Ra 0.8.
    SurfaceFinishControl(
        "pivot_head",
        MACHINED_UM,
        CylinderFace(HEAD_DIA, contains_z_mm=(UNDERHEAD_Z + HEAD_TOP_Z) / 2.0),
    ),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ScrewProfile": {
        "HeadDia",
        "HeadLength",
        "ShoulderDia",
        "ShoulderEnd",
        "OverallLength",
        "TipChamfer",
    },
    "SlotProfile": {"SlotWidth"},
    "DriverSlot": {"SlotDepth"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ScrewProfile": {
        "HeadDia": HEAD_PLACES,
        "HeadLength": 2,
        "ShoulderDia": SHOULDER_PLACES,
        "ShoulderEnd": 1,
        "OverallLength": 1,
        "TipChamfer": 1,
    },
    "SlotProfile": {"SlotWidth": 1},
    "DriverSlot": {"SlotDepth": 2},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dimensions in DRAWING_PRECISION.values() for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked pivot-screw dimension needs authored places")

# Policy: no digits, no GD&T. The notes name the mates that set the two
# lapped bands; the coaxiality requirement is stated by name, and the shop's
# one-chucking lapping route (shop-additions.md section 2) delivers it.
DRAWING_NOTES = "\n".join(
    (
        "LIMITS ARE THE SLIDING FITS TO THE ROCKER ARM PIVOT BORE AND PROFILE",
        "PLATE BORE (SHOULDER) AND THE OUTLINE-TEMPLATE BUSH (HEAD): EACH MUST",
        "SLIDE FREELY WITHOUT SHAKE. HEAD COAXIAL WITH SHOULDER.",
    )
)
# The head left behind the slot at worst case.
_HEAD_BEHIND_SLOT_MIN = round(
    HEAD_LENGTH - SLOT_DEPTH - 2.0 * printed_band_mm(2), 6
)
if _HEAD_BEHIND_SLOT_MIN < 1.5:
    raise AssertionError("pivot-screw slot leaves under the rule-12 floor in the head")
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 2:1"

_AXIS = ([0.0, 0.0, 1.0], ("__frame__",))
_ROCKER = "ch_rocker_arm_spec"
EXPORT_FEATURES: dict[str, ExportFeature] = {
    "shoulder": ExportFeature(
        kind="boss",
        faces=(SURFACE_FINISHES[0].face,),
        requirements=("dia", "finish_ra"),
        fields={
            "at": ([0.0, 0.0, SHOULDER_END_Z], ("SHOULDER_END_Z",)),
            "axis": _AXIS,
            "dia": (
                limits(SHOULDER_DIA, SHOULDER_PLACES, SHOULDER_BAND),
                (
                    "SHOULDER_DIA",
                    "SHOULDER_BAND",
                    (_ROCKER, "PIVOT_HOLE_DIA"),
                    (_ROCKER, "PIVOT_HOLE_BAND"),
                    "PLATE_BORE_LIMITS",
                ),
            ),
            "dia_nominal": (SHOULDER_DIA, ("SHOULDER_DIA",)),
            "length": (SHOULDER_LENGTH, ("SHOULDER_LENGTH",)),
            "finish_ra": (GROUND_UM, ("SURFACE_FINISHES",)),
            "process": ("lap", ("SHOULDER_BAND",)),
        },
        precision={"dia": SHOULDER_PLACES, "finish_ra": 1},
    ),
    "head": ExportFeature(
        kind="boss",
        faces=(CylinderFace(HEAD_DIA),),
        requirements=("dia",),
        fields={
            "at": ([0.0, 0.0, UNDERHEAD_Z], ("UNDERHEAD_Z",)),
            "axis": _AXIS,
            "dia": (
                limits(HEAD_DIA, HEAD_PLACES, HEAD_BAND),
                ("HEAD_DIA", "HEAD_BAND", "TEMPLATE_BUSH_BORE_LIMITS"),
            ),
            "dia_nominal": (HEAD_DIA, ("HEAD_DIA",)),
            "length": (limits(HEAD_LENGTH, 2), ("HEAD_LENGTH",)),
            "process": ("lap", ("HEAD_BAND",)),
        },
        precision={"dia": HEAD_PLACES, "length": 2},
    ),
    "underhead": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 0.0, -1.0), -UNDERHEAD_Z),),
        requirements=("plane",),
        fields={
            "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "z", "value": UNDERHEAD_Z}, ("UNDERHEAD_Z", "WASHER_THICK")),
        },
    ),
    "thread": ExportFeature(
        kind="thread",
        faces=(CylinderFace(THREAD_MODEL_DIA),),
        requirements=("thread", "length"),
        fields={
            "at": ([0.0, 0.0, TIP_Z], ("TIP_Z",)),
            "axis": _AXIS,
            "thread": (THREAD_CALLOUT, ("THREAD_CALLOUT",)),
            "length": (THREAD_LENGTH, ("THREAD_LENGTH",)),
        },
    ),
}
