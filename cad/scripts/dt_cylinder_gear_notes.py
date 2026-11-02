"""Drawing-only text, excluded from the channel's shared geometry imports."""

from __future__ import annotations

import _config
import dt_cylinder_gear_spec as spec
from stock_form_cutter import TOOTH_FORM_NOTE

# The cone mesh stack (cone_set_stack) books this runout on every cone and
# on the drum.
TOOTH_RUNOUT_TIR_MM = float(_config.fit("cone_drum_oblique_mesh", "tooth_cutting_runout_tir_mm"))


def inch_text(value_mm: float, places: int) -> str:
    """``value_mm`` as decimal-inch print text: ``.072``, ``2.500``."""
    text = f"{value_mm / 25.4:.{places}f}"
    return text[1:] if text.startswith("0.") else text


# Narrow rows (machinist review r1): the leader leaves the block's lower
# right corner, and only a corner left of x ~0.07 m clears the cam diameter's
# diametral line on its way down to the bore.  The worst-case wall to the cam
# OD is under the .080 in target, so it is stated as a plain fact (rule 20).
BORE_FIT_CALLOUT = (
    "REAM THRU;\n"
    "ALL 20 GEARS\n"
    "RUNS ON SHAFT\n"
    "MHA-DT-13\n"
    f"{inch_text(spec.CAM_WALL_MIN_MM, 3)} MIN WALL\n"
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
        f"PRESSURE ANGLE:  {spec.PRESSURE_ANGLE_DEG:.1f} DEG",
        f"PITCH DIAMETER (REF):  {inch_text(spec.PITCH_DIA, 3)}",
        # One reference value (machinist review r1): the two-micron
        # envelope read as limits.
        f"ROOT DIAMETER (REF):  {inch_text(sum(spec.ROOT_ENVELOPE_DIA_MM) / 2.0, 3)}",
        f"CUTTER PLUNGE:  {inch_text(spec.WHOLE_DEPTH, spec.WHOLE_DEPTH_PLACES)} "
        f"+{inch_text(spec.WHOLE_DEPTH_BAND[0], spec.WHOLE_DEPTH_PLACES)}"
        f"/{inch_text(spec.WHOLE_DEPTH_BAND[1], spec.WHOLE_DEPTH_PLACES)}; "
        "SETS BACKLASH WITH CONE GEARS MHA-DT-03",
        f"FORM CUTTER:  #{spec.CUTTER_NUMBER}, "
        f"{spec.CUTTER_TEETH_RANGE[0]}-{spec.CUTTER_TEETH_RANGE[1]}T; "
        f"{spec.CUTTER_REFERENCE_TEETH}T REFERENCE",
        f"PITCH TOOTH THICKNESS (REF):  {inch_text(spec.PITCH_TOOTH_THICKNESS_MM, 4)}",
        f"TOOTH FORM:  {TOOTH_FORM_NOTE}",
        "TOOTH CUTTING SETUP, ACCEPT AT SETUP:  "
        f"{inch_text(TOOTH_RUNOUT_TIR_MM, 3)} TIR MAX TO FINISHED BORE",
    )
)
