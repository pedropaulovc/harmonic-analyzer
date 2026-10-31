"""Drawing-only gear data for the straight crank pinion.

Geometry and exact stock tangent-span acceptance remain in dt_crank_pinion_spec.
"""

from __future__ import annotations

import dt_crank_drive_gear_notes as mate_notes
import dt_crank_pinion_spec as spec
from dt_crank_drive_gear_spec import inch_text
from stock_form_cutter import TOOTH_FORM_NOTE


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
        ("PRESSURE ANGLE, NORMAL = TRANSVERSE", f"{spec.PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("PITCH DIAMETER (REF)", inch_text(spec.PITCH_DIA, 3)),
        (
            "ACTUAL ROOT DIA MIN-MAX / MAX CUT DEPTH (REF)",
            f"{inch_text(spec.ROOT_DIA_MIN, 4)}-{inch_text(spec.ROOT_DIA_MAX, 4)} / "
            f"{inch_text(spec.WHOLE_DEPTH, 4)}",
        ),
        ("NORMAL TOOL PLUNGE (REF)", inch_text(spec.TOOL_PLUNGE_MM, 4)),
        (
            f"BASE TANGENT SPAN OVER {spec.BASE_TANGENT_SPAN_TEETH} TEETH, ACCEPT ON THIS PART",
            mate_notes.accept_limits_text(spec.BASE_TANGENT_SPAN_LIMITS_MM, 4),
        ),
        (
            "ACTUAL CIRCULAR PITCH THICKNESS (REF)",
            inch_text(spec.TRANSVERSE_CIRCULAR_TOOTH_THICKNESS, 4),
        ),
        (
            "TOOTH CUTTING SETUP, ACCEPT AT SETUP",
            f"{inch_text(spec.TOOTH_RUNOUT_TIR_MM, 3)} TIR MAX TO FINISHED BORE",
        ),
        ("TOOTH FORM", TOOTH_FORM_NOTE),
        ("MATES WITH", "CRANK DRIVE GEAR MHA-DT-07, 64T RIGHT-HAND HELICAL"),
    ]
)
