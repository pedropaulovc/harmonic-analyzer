"""Drawing-only text, excluded from the channel's shared geometry imports."""

from __future__ import annotations

import _config
import dt_cylinder_gear_spec as spec
from stock_form_cutter import TOOTH_FORM_NOTE

# The cone mesh stack (cone_set_stack) books this runout on every cone and
# on the drum.
TOOTH_RUNOUT_TIR_MM = float(_config.fit("cone_drum_oblique_mesh", "tooth_cutting_runout_tir_mm"))

# Narrow rows (machinist review r1): the leader leaves the block's lower
# right corner, and only a corner left of x ~0.07 m clears the cam diameter's
# diametral line on its way down to the bore.  The worst-case wall to the cam
# OD is under the 2.0 target, so it is stated as a plain fact (rule 20).
BORE_FIT_CALLOUT = (
    "FINISH BORE THRU;\n"
    "ALL 20 GEARS\n"
    "MATCH TO FINISHED\n"
    "SHAFT MHA-DT-13\n"
    f"{spec.BORE_DIAMETRAL_CLEARANCE_MM[0]:.3f}-{spec.BORE_DIAMETRAL_CLEARANCE_MM[1]:.3f}\n"
    "DIAMETRAL CLEARANCE\n"
    f"{spec.CAM_WALL_MIN_MM:.2f} MIN WALL\n"
    "TO CAM OD"
)
# TODO(#744): validate the forked rod and centered channel bank in the native
# assembly. The drawing requirement below does not certify that integration.
# The bank is a solid stack preloaded onto its datum (#948 ruling R, PR #1292):
# no gear interface opens, so a connecting-rod ring never overhangs its cam
# and the callout no longer states an overhang bound.
# Rows <= 18 characters: the stacking text stands right of the side view's
# rims, clear of its extension lines, inside the border.
STACK_FIT_CALLOUT = "STACKS CAM FACE TO\nBACK FACE ON SHAFT\nMHA-DT-13"
GEAR_DATA = "\n".join(
    (
        "GEAR DATA",
        f"NUMBER OF TEETH:  {spec.TEETH}",
        f"DIAMETRAL PITCH:  {spec.DIAMETRAL_PITCH:.2f}",
        f"MODULE (mm, REF):  {spec.MODULE_MM:.3f}",
        f"PRESSURE ANGLE:  {spec.PRESSURE_ANGLE_DEG:.1f} DEG",
        f"PITCH DIAMETER (mm, REF):  {spec.PITCH_DIA:.2f}",
        # One reference value (machinist review r1): the two-micron
        # envelope read as limits.
        f"ROOT DIAMETER (mm, REF):  {sum(spec.ROOT_ENVELOPE_DIA_MM) / 2.0:.2f}",
        f"CUTTER PLUNGE (mm):  {spec.WHOLE_DEPTH:.{spec.WHOLE_DEPTH_PLACES}f} "
        f"+{spec.WHOLE_DEPTH_BAND[0]:.2f}/{spec.WHOLE_DEPTH_BAND[1]:.2f}; "
        "SETS BACKLASH WITH CONE GEARS MHA-DT-03",
        f"FORM CUTTER:  #{spec.CUTTER_NUMBER}, "
        f"{spec.CUTTER_TEETH_RANGE[0]}-{spec.CUTTER_TEETH_RANGE[1]}T; "
        f"{spec.CUTTER_REFERENCE_TEETH}T REFERENCE",
        f"PITCH TOOTH THICKNESS (mm, REF):  {spec.PITCH_TOOTH_THICKNESS_MM:.3f}",
        f"TOOTH FORM:  {TOOTH_FORM_NOTE}",
        f"TOOTH CUTTING SETUP, ACCEPT AT SETUP:  {TOOTH_RUNOUT_TIR_MM:.2f} TIR MAX TO FINISHED BORE",
    )
)
# The mesh mate (MHA-DT-03) is named at the OD callout and the eccentricity
# carries its per-gear band only, so one note remains (rule 7).
DRAWING_NOTES = (
    "ALIGNMENT NOTCH IS FIRST TOOTH ROOT CCW FROM CAM LOBE AS VIEWED FROM CAM FACE."
)
