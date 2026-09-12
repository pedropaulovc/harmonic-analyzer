"""Drawing-only text, excluded from the channel's shared geometry imports."""

from __future__ import annotations

import cylinder_gear_spec as spec

BORE_FIT_CALLOUT = (
    "FINISH BORE THRU; ALL 20 GEARS\n"
    "MATCH TO FINISHED\n"
    "CYLINDER-GEAR-SHAFT MHA-028\n"
    f"{spec.BORE_DIAMETRAL_CLEARANCE_MM[0]:.3f}-{spec.BORE_DIAMETRAL_CLEARANCE_MM[1]:.3f} "
    "DIAMETRAL CLEARANCE"
)
# TODO(#744): validate the forked rod and centered channel bank in the native
# assembly. The drawing requirement below does not certify that integration.
# TODO(#743): establish physical shaft-end retention and measured bank endplay,
# then prove full ring support through the stroke and every allowed axial position.
# Static assembly mates and the 3.5 mm reference cam width are not that proof.
CAM_AXIAL_FIT_CALLOUT = (
    "FIT TO CONNECTING ROD MHA-017\n"
    "SUPPORT FULL RING WIDTH\n"
    "THROUGHOUT OPERATION\n"
    "FREE MOVEMENT; NO AXIAL BINDING\n"
    "OR ADJACENT-PART CONTACT"
)
GEAR_DATA = "\n".join(
    (
        "GEAR DATA",
        f"NUMBER OF TEETH:  {spec.TEETH}",
        f"DIAMETRAL PITCH:  {spec.DIAMETRAL_PITCH:.2f} (NONSTANDARD)",
        f"MODULE (mm, REF):  {spec.MODULE_MM:.3f}",
        f"PRESSURE ANGLE:  {spec.PRESSURE_ANGLE_DEG:.1f} DEG",
        f"PITCH DIAMETER (mm, REF):  {spec.PITCH_DIA:.2f}",
        f"OUTSIDE DIAMETER (mm):  {spec.OUTSIDE_DIA:.2f} +0/-0.10",
        f"WHOLE DEPTH (mm):  {spec.WHOLE_DEPTH:.2f} +0.05/0",
        "TOOTH FORM:  INVOLUTE, FULL DEPTH",
    )
)
DRAWING_NOTES = "\n".join(
    (
        "ALIGNMENT NOTCH IS FIRST TOOTH ROOT CCW FROM CAM LOBE AS VIEWED FROM CAM FACE.",
        "CAM ECCENTRICITY RANGE ACROSS ALL 20 MHA-027 GEARS IN ONE ANALYZER: "
        f"{spec.SET_ECCENTRICITY_RANGE_MM:.3f} MAX.",
        "MATES WITH CONE GEAR FAMILY MHA-013.",
    )
)
