"""Drawing-only text, excluded from the channel's shared geometry imports."""

from __future__ import annotations

import cylinder_bank_layout as bank
import dt_cylinder_gear_spec as spec

BORE_FIT_CALLOUT = (
    "FINISH BORE THRU; ALL 20 GEARS\n"
    "MATCH TO FINISHED\n"
    "CYLINDER-GEAR-SHAFT MHA-DT-013\n"
    f"{spec.BORE_DIAMETRAL_CLEARANCE_MM[0]:.3f}-{spec.BORE_DIAMETRAL_CLEARANCE_MM[1]:.3f} "
    "DIAMETRAL CLEARANCE"
)
# TODO(#744): validate the forked rod and centered channel bank in the native
# assembly. The drawing requirement below does not certify that integration.
# The bank is a solid, unpreloaded stack (#743): a ring can overhang its cam
# only by an interface the end play lets open, so the acceptance names that
# bound (cylinder_bank_layout.RING_OVERHANG_MAX, user ruling Q1).
STACK_FIT_CALLOUT = (
    "STACKS CAM FACE TO BACK FACE\n"
    "ON CYLINDER-GEAR-SHAFT MHA-DT-013;\n"
    "CONNECTING ROD MHA-CH-003 RING\n"
    f"OVERHANGS CAM {bank.RING_OVERHANG_MAX:.2f} MAX"
)
GEAR_DATA = "\n".join(
    (
        "GEAR DATA",
        f"NUMBER OF TEETH:  {spec.TEETH}",
        f"DIAMETRAL PITCH:  {spec.DIAMETRAL_PITCH:.2f}",
        f"MODULE (mm, REF):  {spec.MODULE_MM:.3f}",
        f"PRESSURE ANGLE:  {spec.PRESSURE_ANGLE_DEG:.1f} DEG",
        f"PITCH DIAMETER (mm, REF):  {spec.PITCH_DIA:.2f}",
        f"ROOT ENVELOPE DIAMETER (mm, REF):  "
        f"{spec.ROOT_ENVELOPE_DIA_MM[0]:.3f}-{spec.ROOT_ENVELOPE_DIA_MM[1]:.3f}",
        f"CUTTER PLUNGE (mm):  {spec.WHOLE_DEPTH:.{spec.WHOLE_DEPTH_PLACES}f} "
        f"+{spec.WHOLE_DEPTH_BAND[0]:.2f}/{spec.WHOLE_DEPTH_BAND[1]:.2f}",
        f"FORM CUTTER (REF):  #{spec.CUTTER_NUMBER}, "
        f"{spec.CUTTER_TEETH_RANGE[0]}-{spec.CUTTER_TEETH_RANGE[1]}T; "
        f"{spec.CUTTER_REFERENCE_TEETH}T REFERENCE",
        f"PITCH TOOTH THICKNESS (mm, REF):  {spec.PITCH_TOOTH_THICKNESS_MM:.3f}",
        "TOOTH FORM:  TRANSLATED STOCK FORM; FINITE FLANKS AND OFF-CENTRE ROOT ARC",
    )
)
DRAWING_NOTES = "\n".join(
    (
        "ALIGNMENT NOTCH IS FIRST TOOTH ROOT CCW FROM CAM LOBE AS VIEWED FROM CAM FACE.",
        "CAM ECCENTRICITY RANGE ACROSS ALL 20 MHA-DT-012 GEARS",
        f"IN ONE ANALYZER: {spec.SET_ECCENTRICITY_RANGE_MM:.3f} MAX.",
        "MATES WITH CONE GEAR FAMILY MHA-DT-003.",
    )
)
