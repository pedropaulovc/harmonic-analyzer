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
origin. The washer sits Z0..2, the head Z2..6, the shoulder Z-14..2 and the
thread Z-26.3..-14. The head length prints from the faced head top; the
shoulder length and the length under the head print from the underhead, the
face that clamps the washer, because they set the axial stack into the plate.
"""

from __future__ import annotations

import ch_rocker_arm_notes as rocker_notes
import ch_rocker_arm_spec as rocker
import ch_rocker_arm_tl_profile_fixture_spec as profile
from _feature_requirements import ExportFeature, limits
from _gtol_spec import CylinderFace, PlanarFace
from _hole_spec import THREAD_MAJOR_MM
from _printed_tolerance import printed_band_mm
from _surface_finish import GROUND_UM, MACHINED_UM, SurfaceFinishControl

# --- stations (fixture frame, mm) -------------------------------------------
# The MHA-CH-006-TL-07 washer under the head. 2.0, not the inventory's 1.5:
# at .XXX its thinnest stays over the rule-12 floor.
WASHER_THICK = 2.0
WASHER_THICK_PLACES = 3
HEAD_DIA = 8.0
HEAD_LENGTH = 4.0
SHOULDER_DIA = 6.49
# Shop-to-shop thread follows the HA US-customary fastener policy (UNC, 2A per
# the title block): the inventory's M5x0.8 maps to #10-24. The thread runs
# from the shoulder end to the tip.
THREAD_SIZE = "#10-24"
THREAD_CALLOUT = f"{THREAD_SIZE} UNC"
THREAD_MODEL_DIA = THREAD_MAJOR_MM[THREAD_SIZE]
THREAD_PITCH = 25.4 / 24.0
# Basic external minor diameter, D - 1.22687P (ASME B1.1 table 2 basis).
THREAD_ROOT_DEPTH = round((1.22687 * THREAD_PITCH) / 2.0, 6)
# The tip is chamfered 45 degrees to the thread root: its axial length is the
# root depth, so the first full thread sits a fixed distance from the tip.
TIP_CHAMFER = round(THREAD_ROOT_DEPTH, 2)
CHAMFER_CALLOUT = "X 45 DEG TO THREAD ROOT"
# The two direct axial sizes the stack rides on, both from the underhead
# (the face that clamps the washer), both at .XXX.
SHOULDER_LENGTH = 16.0  # underhead to shoulder end
UNDER_HEAD_LENGTH = 28.3  # underhead to tip
AXIAL_PLACES = 3
THREAD_LENGTH = round(UNDER_HEAD_LENGTH - SHOULDER_LENGTH, 6)
SLOT_WIDTH = 1.0
# 0.9 deep (route said 1.5): at the one-place general band
# the worst head left behind the slot stays over the rule-12 floor.
SLOT_DEPTH = 0.9

UNDERHEAD_Z = WASHER_THICK
HEAD_TOP_Z = UNDERHEAD_Z + HEAD_LENGTH
SHOULDER_END_Z = round(UNDERHEAD_Z - SHOULDER_LENGTH, 6)
TIP_Z = round(UNDERHEAD_Z - UNDER_HEAD_LENGTH, 6)
OVERALL_LENGTH = round(HEAD_LENGTH + UNDER_HEAD_LENGTH, 6)

# --- axial stack into the profile plate (MHA-CH-006-TL-02) --------------------
# Depths below the upper hub face (screw Z0), worst case over the printed
# bands: the hub stands on the arm strap centred on the plate pads, so the hub
# face sits (hub + strap) / 2 over the pad tops; the plate's printed PlateDrop
# and LocatingBoreDepth carry it to the bore floor; the tap runs below that.
_XXX = printed_band_mm(3)
_STRAP_BAND = printed_band_mm(rocker_notes.DEFAULT_DRAWING_PRECISION)
_HUB_FACE_OVER_PADS = (
    (rocker.HUB_LENGTH + rocker.HUB_LENGTH_BAND[1] + rocker.ARM_THICKNESS - _STRAP_BAND) / 2.0,
    (rocker.HUB_LENGTH + rocker.HUB_LENGTH_BAND[0] + rocker.ARM_THICKNESS + _STRAP_BAND) / 2.0,
)
FLOOR_DEPTH = (
    round(_HUB_FACE_OVER_PADS[0] + profile.PLATE_DROP - _XXX
          + profile.LOCATING_BORE_DEPTH - profile.LOCATING_BORE_DEPTH_BAND, 6),
    round(_HUB_FACE_OVER_PADS[1] + profile.PLATE_DROP + _XXX
          + profile.LOCATING_BORE_DEPTH + profile.LOCATING_BORE_DEPTH_BAND, 6),
)
_PLATE_TOP_DEPTH_MAX = _HUB_FACE_OVER_PADS[1] + profile.PLATE_DROP + _XXX
_W = (WASHER_THICK - _XXX, WASHER_THICK + _XXX)
_SHOULDER_END = (_W[0] + SHOULDER_LENGTH - _XXX, _W[1] + SHOULDER_LENGTH + _XXX)
_TIP = (_W[0] + UNDER_HEAD_LENGTH - _XXX, _W[1] + UNDER_HEAD_LENGTH + _XXX)
# A die leaves up to two pitches of incomplete thread against the shoulder;
# that run-out stays in the plain bore, clear of the floor, so the shoulder
# never bottoms and every thread entering the tap is full.
THREAD_RUNOUT = round(2.0 * THREAD_PITCH, 6)
FLOOR_CLEARANCE_MIN = round(FLOOR_DEPTH[0] - _SHOULDER_END[1], 6)
if FLOOR_CLEARANCE_MIN < THREAD_RUNOUT + 0.1:
    raise AssertionError("pivot-screw shoulder or thread run-out reaches the plate bore floor")
# The shoulder still enters the plate's locating bore at worst case.
PLATE_BORE_ENTRY_MIN = round(_SHOULDER_END[0] - _PLATE_TOP_DEPTH_MAX, 6)
if PLATE_BORE_ENTRY_MIN < 2.0:
    raise AssertionError("pivot-screw shoulder barely enters the plate locating bore")
# Full screw thread ends one root depth (the chamfer) plus half a pitch of
# chamfer-thinned crest short of the tip; the tapped full thread is the
# plate's printed PIVOT_TAP_THREAD_DEPTH at .XX.
_TAP_FULL_MIN = profile.PIVOT_TAP_THREAD_DEPTH - printed_band_mm(2)
ENGAGEMENT_MIN_D = 1.5
FULL_ENGAGEMENT_MIN = round(
    min(_TIP[0] - FLOOR_DEPTH[1] - (TIP_CHAMFER + THREAD_PITCH / 2.0), _TAP_FULL_MIN), 6
)
if FULL_ENGAGEMENT_MIN < ENGAGEMENT_MIN_D * THREAD_MODEL_DIA:
    raise AssertionError("pivot-screw full thread engages under 1.5D in the plate")
# The screw's last full thread never runs past the tap's full thread, and the
# tip stays inside the tap drill.
if _TIP[1] - FLOOR_DEPTH[0] - TIP_CHAMFER > _TAP_FULL_MIN:
    raise AssertionError("pivot-screw full thread runs past the plate's tapped full thread")
TIP_DRILL_CLEARANCE_MIN = round(
    profile.PIVOT_TAP_DRILL_DEPTH - printed_band_mm(2) - (_TIP[1] - FLOOR_DEPTH[0]), 6
)
if TIP_DRILL_CLEARANCE_MIN < 0.5:
    raise AssertionError("pivot-screw tip reaches the plate's tap-drill bottom")

# --- locating fits ------------------------------------------------------------
# The shoulder locates in the rocker arm's reamed pivot bore (datum A,
# PIVOT_HOLE_BAND) and in the profile plate's 6.500 H7 locating bore.
PLATE_BORE_LIMITS = (
    profile.LOCATING_BORE_DIA + profile.LOCATING_BORE_BAND[1],
    profile.LOCATING_BORE_DIA + profile.LOCATING_BORE_BAND[0],
)
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
        "ShoulderLength",
        "UnderHeadLength",
        "TipChamfer",
    },
    "SlotProfile": {"SlotWidth"},
    "DriverSlot": {"SlotDepth"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ScrewProfile": {
        "HeadDia": HEAD_PLACES,
        "HeadLength": 1,
        "ShoulderDia": SHOULDER_PLACES,
        "ShoulderLength": AXIAL_PLACES,
        "UnderHeadLength": AXIAL_PLACES,
        "TipChamfer": 2,
    },
    "SlotProfile": {"SlotWidth": 1},
    "DriverSlot": {"SlotDepth": 1},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dimensions in DRAWING_PRECISION.values() for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked pivot-screw dimension needs authored places")

# Policy rule 2/6: a matched fit sits ON the feature callout, naming each
# mate by name and Number and the acceptance; the general notes carry no
# digits. The outline-template bush has no Number yet, so it is named only.
ROCKER_NUMBER = "MHA-CH-006"
PROFILE_PLATE_NUMBER = "MHA-CH-006-TL-02"
SHOULDER_FIT_CALLOUT = "\n".join(
    (
        "MATCH-FIT: SLIDES",
        "FREELY WITHOUT SHAKE IN",
        f"ROCKER ARM {ROCKER_NUMBER}",
        "PIVOT BORE AND PROFILE",
        f"PLATE {PROFILE_PLATE_NUMBER}",
        "LOCATING BORE",
    )
)
HEAD_FIT_CALLOUT = "\n".join(
    (
        "MATCH-FIT: SLIDES",
        "FREELY WITHOUT SHAKE IN",
        "OUTLINE-TEMPLATE BUSH",
    )
)
HEAD_COAXIAL_NOTE = "HEAD COAXIAL WITH SHOULDER"
# The two .XXX stack lengths say why on the dimension: they set how deep the
# shoulder and thread sit in the profile plate.
STACK_CALLOUT = f"SETS DEPTH IN PLATE {PROFILE_PLATE_NUMBER}"
# The head-top-to-tip overall prints as a stock cut-off reference.
OVERALL_REFERENCE_PLACES = 1
DRAWING_NOTES = "\n".join(
    (
        "BRACKETED DIAMETERS ARE THE STARTING SIZE FOR THE MATCH-FIT.",
        f"{HEAD_COAXIAL_NOTE}.",
        # One axial baseline: the underhead clamps the washer and sets the
        # depth in the plate; the slot depth is the slot's own size.
        "AXIAL LENGTHS RUN FROM THE UNDERSIDE OF THE HEAD; THE SLOT DEPTH FROM THE HEAD TOP.",
    )
)
# The head left behind the slot at worst case.
_HEAD_BEHIND_SLOT_MIN = round(
    HEAD_LENGTH - SLOT_DEPTH - 2.0 * printed_band_mm(1), 6
)
if _HEAD_BEHIND_SLOT_MIN < 1.5:
    raise AssertionError("pivot-screw slot leaves under the rule-12 floor in the head")
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 2:1"

_AXIS = ([0.0, 0.0, 1.0], ("__frame__",))
_ROCKER = "ch_rocker_arm_spec"
# One fact, one source: features.toml carries what the print says -- the
# bracketed reference diameters and each feature's printed fit callout.
# SHOULDER_BAND / HEAD_BAND stay design intent for the stack checks only.

EXPORT_FEATURES: dict[str, ExportFeature] = {
    "shoulder": ExportFeature(
        kind="boss",
        faces=(SURFACE_FINISHES[0].face,),
        requirements=("note", "finish_ra"),
        fields={
            "at": ([0.0, 0.0, SHOULDER_END_Z], ("SHOULDER_END_Z",)),
            "axis": _AXIS,
            "dia_nominal": (SHOULDER_DIA, ("SHOULDER_DIA",)),
            "length": (limits(SHOULDER_LENGTH, AXIAL_PLACES), ("SHOULDER_LENGTH", "AXIAL_PLACES")),
            "finish_ra": (GROUND_UM, ("SURFACE_FINISHES",)),
            "process": ("lap", ("SURFACE_FINISHES",)),
            "note": (" ".join(SHOULDER_FIT_CALLOUT.splitlines()), ("SHOULDER_FIT_CALLOUT",)),
        },
        precision={"length": AXIAL_PLACES, "finish_ra": 1},
    ),
    "head": ExportFeature(
        kind="boss",
        faces=(CylinderFace(HEAD_DIA),),
        requirements=("note", "finish_ra"),
        fields={
            "at": ([0.0, 0.0, UNDERHEAD_Z], ("UNDERHEAD_Z",)),
            "axis": _AXIS,
            "dia_nominal": (HEAD_DIA, ("HEAD_DIA",)),
            "length": (limits(HEAD_LENGTH, 1), ("HEAD_LENGTH",)),
            "finish_ra": (MACHINED_UM, ("SURFACE_FINISHES",)),
            "process": ("lap", ("SURFACE_FINISHES",)),
            "coaxial_to": ("shoulder", ("DRAWING_NOTES",)),
            "note": (" ".join(HEAD_FIT_CALLOUT.splitlines()), ("HEAD_FIT_CALLOUT",)),
        },
        precision={"length": 1, "finish_ra": 1},
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
            # Shoulder end to tip: the printed UnderHeadLength less the
            # printed ShoulderLength, both at .XXX.
            "length": (
                [
                    round(UNDER_HEAD_LENGTH - SHOULDER_LENGTH - 2.0 * _XXX, 6),
                    round(UNDER_HEAD_LENGTH - SHOULDER_LENGTH + 2.0 * _XXX, 6),
                ],
                ("UNDER_HEAD_LENGTH", "SHOULDER_LENGTH", "AXIAL_PLACES"),
            ),
        },
        precision={"length": AXIAL_PLACES},
    ),
}
