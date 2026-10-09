"""Drawing-only gear data for the straight crank pinion.

Geometry and exact stock tangent-span acceptance remain in dt_crank_pinion_spec.
Assembly requirements are requirements, not a measured crossed-mesh certificate.
"""

from __future__ import annotations

import dt_crank_drive_gear_notes as mate_notes
import dt_crank_pinion_spec as spec


STOCK_FORM_COVERAGE_ROW = (
    "STOCK-FORM COVERAGE WITH MHA-DT-007, ACCEPT AT ASSEMBLY",
    mate_notes.STOCK_FORM_COVERAGE_ROW[1],
)

# The spur's normal and transverse sections coincide. Its physical tooth
# count selects a different stock cutter from the helical mate's virtual count.
GEAR_DATA = mate_notes.gear_data_note(
    [
        ("NUMBER OF TEETH", f"{spec.TEETH}"),
        (
            "DIAMETRAL PITCH, NORMAL = TRANSVERSE (CUTTER)",
            f"{spec.DIAMETRAL_PITCH:.2f}",
        ),
        (
            "FORM CUTTER",
            f"#{spec.CUTTER_NUMBER}, {spec.CUTTER_TEETH_RANGE[0]}-{spec.CUTTER_TEETH_RANGE[1]}T; "
            f"{spec.CUTTER_TEMPLATE.reference_teeth}T REFERENCE",
        ),
        ("MODULE (mm, REF)", f"{spec.MODULE_MM:.3f}"),
        ("PRESSURE ANGLE, NORMAL = TRANSVERSE", f"{spec.PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("PITCH DIAMETER (mm, REF)", f"{spec.PITCH_DIA:.2f}"),
        (
            "ACTUAL ROOT DIA MIN-MAX / MAX CUT DEPTH (mm, REF)",
            f"{spec.ROOT_DIA_MIN:.3f}-{spec.ROOT_DIA_MAX:.3f} / {spec.WHOLE_DEPTH:.3f}",
        ),
        ("NORMAL TOOL PLUNGE (mm, REF)", f"{spec.TOOL_PLUNGE_MM:.3f}"),
        (
            f"BASE TANGENT SPAN OVER {spec.BASE_TANGENT_SPAN_TEETH} TEETH (mm), ACCEPT ON THIS PART",
            f"{spec.BASE_TANGENT_SPAN_LIMITS_MM[0]:.{spec.BASE_TANGENT_SPAN_PLACES}f} TO "
            f"{spec.BASE_TANGENT_SPAN_LIMITS_MM[1]:.{spec.BASE_TANGENT_SPAN_PLACES}f}",
        ),
        (
            "ACTUAL CIRCULAR PITCH THICKNESS (mm, REF)",
            f"{spec.TRANSVERSE_CIRCULAR_TOOTH_THICKNESS:.3f}",
        ),
        (
            "TOOTH CUTTING SETUP, ACCEPT AT SETUP",
            f"{spec.TOOTH_RUNOUT_TIR_MM:.2f} TIR MAX TO FINISHED BORE",
        ),
        (
            "TOOTH FORM",
            f"FULL-DEPTH NORMAL-{spec.DIAMETRAL_PITCH:g}DP PA{spec.PRESSURE_ANGLE_DEG:g} "
            f"FINITE STOCK #{spec.CUTTER_NUMBER}/{spec.CUTTER_TEMPLATE.reference_teeth}T; STANDARD ROOT",
        ),
        ("MATES WITH", "CRANK DRIVE GEAR MHA-DT-007, 64T RIGHT-HAND HELICAL"),
        STOCK_FORM_COVERAGE_ROW,
    ]
)
