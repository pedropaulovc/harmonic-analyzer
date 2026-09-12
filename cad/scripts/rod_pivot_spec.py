"""Centered two-cheek rod fork with a plain, peened pivot pin.

The photographs establish two black cheeks straddling the silver rocker, not
prong dimensions or retention details. Peening is the user's reconstruction
choice, not a historically verified fastener. Cheek, flare, root and head sizes
are design dimensions; the 2.5 mm rocker thickness is photograph-callout data.
All dimensions are mm. There is no axial rod/rocker center offset or spacer.
"""

from __future__ import annotations

import math

from _hole_spec import HoleSpec, NUMBER_DRILL_MM

ROCKER_THICKNESS = 2.5
FORK_CHEEK_THICKNESS = 1.25
JOINT_ENDFLOAT_MIN = 0.02
JOINT_ENDFLOAT_MAX = 0.05
JOINT_ENDFLOAT_NOMINAL = (JOINT_ENDFLOAT_MIN + JOINT_ENDFLOAT_MAX) / 2.0
FORK_SLOT_NOMINAL = ROCKER_THICKNESS + JOINT_ENDFLOAT_NOMINAL
FORK_OUTER_THICKNESS = FORK_SLOT_NOMINAL + 2.0 * FORK_CHEEK_THICKNESS
# Short transition, comparable to the photographed head height, not measured.
FORK_FLARE_LENGTH = 6.0
# Round-ended slot: this explicit root avoids a sharp internal fork crotch.
FORK_ROOT_RADIUS = FORK_SLOT_NOMINAL / 2.0
FORK_ROOT_CENTER_BELOW_PIN = 7.0
FORK_HOLE_SPEC = HoleSpec("drilled_number", "#47")
ROCKER_HOLE_SPEC = HoleSpec("drilled_number", "#47")
ROCKER_BORE_NOMINAL = NUMBER_DRILL_MM["#47"]
PIN_JOURNAL_DIA = 1.98
PIN_DIAMETRAL_CLEARANCE = (0.010, 0.025)
PIN_HEAD_DIA = 3.0
PIN_HEAD_THICKNESS = 0.4
# Final formed-head acceptance (reconstruction design, not a load rating).
# Measure the minimum continuous bearing-rim thickness separately from the
# maximum axial head height; a thin-edged dome must not pass on height alone.
PIN_HEAD_DIAMETER_MIN = 2.80
PIN_HEAD_RIM_THICKNESS_MIN = 0.30
PIN_HEAD_RADIAL_OVERLAP_MIN = 0.35
PIN_NEIGHBOR_CLEARANCE_MIN = 0.50
# Installed representation: flat inner head faces touch the outer cheeks.
# Peening must not close the finished fork slot or clamp the moving rocker.
PIN_GRIP_LENGTH = FORK_OUTER_THICKNESS
PIN_LENGTH = PIN_GRIP_LENGTH + 2.0 * PIN_HEAD_THICKNESS

# Physical manufacturing state: one preformed head, plain journal and upset
# stock beyond the matched grip. This is a design allowance, not a prediction
# or certification of a forming operation.
PIN_BLANK_CONFIGURATION = "OneHeadedBlank"
PIN_UPSET_ALLOWANCE = 1.0


def check_measured_joint(
    *, fork_gap: float, rocker: float, cheek_left: float, cheek_right: float,
    head_left: float, head_right: float, bore: float, journal: float,
    head_dia_left: float, head_dia_right: float,
    head_rim_left: float, head_rim_right: float,
    ear_bore_left: float, ear_bore_right: float, station_pitch: float,
) -> dict[str, float]:
    """Check finished fit, geometric retention and neighboring clearance.

    Head_left/right are maximum axial heights; head_rim_left/right are minimum
    continuous thicknesses around the load-bearing annuli. Measure diameters
    at the retaining rims, not a wider unsupported crown. Reject cracked or
    discontinuous heads and verify free pivoting separately: scalar sizes
    cannot certify peening quality, load capacity or fatigue life.
    """
    measurements = (
        fork_gap, rocker, cheek_left, cheek_right, head_left, head_right,
        bore, journal, head_dia_left, head_dia_right, head_rim_left,
        head_rim_right, ear_bore_left, ear_bore_right, station_pitch,
    )
    if any(not math.isfinite(v) or v <= 0.0 for v in measurements):
        raise ValueError("rod pivot requires finite positive finished dimensions")
    endfloat = fork_gap - rocker
    diametral_clearance = bore - journal
    envelope = cheek_left + fork_gap + cheek_right + head_left + head_right
    overlap_left = (head_dia_left - ear_bore_left) / 2.0
    overlap_right = (head_dia_right - ear_bore_right) / 2.0
    values = {
        "endfloat_mm": endfloat,
        "diametral_clearance_mm": diametral_clearance,
        "axial_envelope_mm": envelope,
        "axial_envelope_max_mm": station_pitch - PIN_NEIGHBOR_CLEARANCE_MIN,
        "neighbor_clearance_mm": station_pitch - envelope,
        "head_overlap_left_mm": overlap_left,
        "head_overlap_right_mm": overlap_right,
        "minimum_head_rim_mm": min(head_rim_left, head_rim_right),
    }
    failures = []
    if not JOINT_ENDFLOAT_MIN - 1e-9 <= endfloat <= JOINT_ENDFLOAT_MAX + 1e-9:
        failures.append("post-peening sideplay outside matched-fit range")
    if not PIN_DIAMETRAL_CLEARANCE[0] - 1e-9 <= diametral_clearance <= PIN_DIAMETRAL_CLEARANCE[1] + 1e-9:
        failures.append("journal diametral clearance outside running-fit range")
    if min(ear_bore_left, ear_bore_right) < journal:
        failures.append("journal does not pass through both fork ears")
    if min(head_dia_left, head_dia_right) < PIN_HEAD_DIAMETER_MIN - 1e-9:
        failures.append("retaining head diameter below minimum")
    if min(overlap_left, overlap_right) < PIN_HEAD_RADIAL_OVERLAP_MIN - 1e-9:
        failures.append("insufficient retaining overlap over fork bore")
    if min(head_rim_left, head_rim_right) < PIN_HEAD_RIM_THICKNESS_MIN - 1e-9:
        failures.append("continuous head bearing rim too thin")
    if head_rim_left > head_left or head_rim_right > head_right:
        failures.append("rim thickness exceeds measured maximum head height")
    if values["neighbor_clearance_mm"] < PIN_NEIGHBOR_CLEARANCE_MIN - 1e-9:
        failures.append("formed heads exceed neighboring-station envelope")
    if failures:
        raise ValueError(f"rod pivot rejected: {failures}; measured={values}")
    return values
