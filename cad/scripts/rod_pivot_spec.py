"""Single rod/rocker pivot prototype: nominal geometry and measured matched fits.

The photograph establishes the recessed joint envelope, not internal dimensions.
These dimensions implement the approved removable shoulder-pin architecture.
The head is recessed in the rocker's local -Z face (world +Z under the
channel's Ry(180) transform). Its shoulder seats on the rod's local -Z face;
the #0-80 tip threads into the rod. The pin turns with the rod inside the
rocker bearing. This handedness preserves the visible head, without claiming
that the photograph resolves the historical thread direction.
"""

from __future__ import annotations

from _fit_limits import REAM_SLIDE
from _hole_spec import HoleSpec, NUMBER_DRILL_MM, TAP_DRILL_MM, THREAD_MAJOR_MM

THREAD_SIZE = "#0-80"
THREAD_PITCH_MM = 25.4 / 80.0
THREAD_MAJOR = THREAD_MAJOR_MM[THREAD_SIZE]
THREAD_TAP_DRILL = TAP_DRILL_MM[THREAD_SIZE]
ROD_THREAD_SPEC = HoleSpec("tapped", THREAD_SIZE, thread_class="2B")
ROD_HEAD_THICKNESS = 2.5
ROCKER_THICKNESS = 2.5
ROD_TO_ROCKER_CENTER_DISTANCE = 4.05
ROCKER_RECESS_DIA = 3.2
ROCKER_RECESS_DEPTH = 1.0
PIN_HEAD_DIA = 3.0
PIN_HEAD_THICKNESS = 0.8
PIN_SLOT_WIDTH = 0.4
PIN_SLOT_DEPTH = 0.3
PIN_SHOULDER_DIA = 1.98
PIN_DIAMETRAL_CLEARANCE = (REAM_SLIDE[1], REAM_SLIDE[0])
JOINT_ENDFLOAT_MIN = 0.02
JOINT_ENDFLOAT_MAX = 0.05
JOINT_ENDFLOAT_NOMINAL = (JOINT_ENDFLOAT_MIN + JOINT_ENDFLOAT_MAX) / 2.0
CAM_CENTER_RESIDUAL_MAX = 0.05
SPACER_ID = 2.05
SPACER_OD = 3.0
SPACER_LENGTH = ROD_TO_ROCKER_CENTER_DISTANCE - (ROD_HEAD_THICKNESS + ROCKER_THICKNESS) / 2.0
PIN_SHOULDER_LENGTH = ROCKER_THICKNESS - ROCKER_RECESS_DEPTH + SPACER_LENGTH + JOINT_ENDFLOAT_NOMINAL
PIN_THREAD_LENGTH = 2.2
PIN_THREAD_RELIEF_LENGTH = 0.2
PIN_THREAD_RELIEF_DIA = 1.10
ROD_THREAD_ENTRY_CHAMFER = 0.10
THREAD_TIP_CLEARANCE_MIN = 0.10
PIN_LENGTH = PIN_HEAD_THICKNESS + PIN_SHOULDER_LENGTH + PIN_THREAD_LENGTH
ROCKER_BORE_NOMINAL = NUMBER_DRILL_MM["#47"]


def check_measured_joint(
    *, rod_head: float, rocker: float, recess: float, sleeve: float,
    shoulder: float, head: float, thread: float, bore: float, journal: float,
    target_center_distance: float, station_pitch: float,
) -> dict[str, float]:
    """Check measured faces/diameters, never assume nominal plate thicknesses.

    Sleeve is fitted to locate the rod at mid-endfloat. Shoulder length is
    matched to remaining rocker bearing land + finished sleeve + required float.
    The returned full-thread engagement deducts the specified relief and entry
    chamfer; it is a geometric value, not a load-rating certification.
    """
    bearing_land = rocker - recess
    endfloat = shoulder - sleeve - bearing_land
    center_distance = (rod_head + rocker) / 2.0 + sleeve + endfloat / 2.0
    center_error = abs(center_distance - target_center_distance)
    diametral_clearance = bore - journal
    head_recess = recess - head - endfloat
    tip_clearance = rod_head - thread
    envelope = rod_head + rocker + sleeve + endfloat
    neighbor_clearance = station_pitch - envelope
    values = {
        "bearing_land_mm": bearing_land,
        "endfloat_mm": endfloat,
        "center_distance_mm": center_distance,
        "center_residual_mm": center_error,
        "diametral_clearance_mm": diametral_clearance,
        "minimum_head_recess_mm": head_recess,
        "thread_tip_clearance_mm": tip_clearance,
        "full_thread_engagement_mm": thread - PIN_THREAD_RELIEF_LENGTH - ROD_THREAD_ENTRY_CHAMFER,
        "axial_envelope_mm": envelope,
        "neighbor_clearance_mm": neighbor_clearance,
    }
    failures = []
    if bearing_land <= 0.0 or sleeve <= 0.0:
        failures.append("nonpositive bearing land or spacer")
    if not JOINT_ENDFLOAT_MIN - 1e-9 <= endfloat <= JOINT_ENDFLOAT_MAX + 1e-9:
        failures.append("endfloat outside matched-fit range")
    if center_error > CAM_CENTER_RESIDUAL_MAX + 1e-9:
        failures.append("rod midpoint outside cam-center allowance")
    if not PIN_DIAMETRAL_CLEARANCE[0] - 1e-9 <= diametral_clearance <= PIN_DIAMETRAL_CLEARANCE[1] + 1e-9:
        failures.append("journal diametral clearance outside running-fit range")
    if head_recess < 0.0 or tip_clearance < THREAD_TIP_CLEARANCE_MIN - 1e-9:
        failures.append("pin projects beyond its permitted envelope")
    if neighbor_clearance <= 0.0:
        failures.append("neighbor channel envelopes overlap")
    if failures:
        raise ValueError(f"rod pivot rejected: {failures}; measured={values}")
    return values
