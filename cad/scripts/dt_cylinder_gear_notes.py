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
# diametral line on its way down to the bore.  Rule 4's third form (fit
# audit 2026-11-23, MHA-DT-12.bore): the bore is reamed with the .3760
# reamer and prints no band; its mate, the 3/8 ground shaft MHA-DT-13, is
# bought to size and is the gauge.  Why it stays reamed is in the necessity
# register (cad/config/necessity/dt-cylinder-gear.yaml), not on the sheet.
BORE_FIT_CALLOUT = "REAM THRU\nMHA-DT-13 ENTERS,\nNO SHAKE"
# The worst-case crescent wall to the cam OD is under the .080 in target, so
# it is stated as a plain fact (rule 20), at its own leader on the thin side.
CAM_WALL_NOTE = f"WALL {inch_text(spec.CAM_WALL_MIN_MM, 3)} MIN TO BORE"
# The stacking thickness's band has no mate to try: it prints value and band
# only, and the register says what it protects (rule 4).
GEAR_DATA = "\n".join(
    (
        "GEAR DATA",
        f"NUMBER OF TEETH:  {spec.TEETH}",
        f"DIAMETRAL PITCH:  {spec.DIAMETRAL_PITCH:.2f}",
        f"PRESSURE ANGLE:  {spec.PRESSURE_ANGLE_DEG:.1f}\u00b0",
        f"PITCH DIAMETER (REF):  {inch_text(spec.PITCH_DIA, 3)}",
        # One reference value (machinist review r1): the two-micron
        # envelope read as limits.
        f"ROOT DIAMETER (REF):  {inch_text(sum(spec.ROOT_ENVELOPE_DIA_MM) / 2.0, 3)}",
        f"CUTTER PLUNGE:  {inch_text(spec.WHOLE_DEPTH, spec.WHOLE_DEPTH_PLACES)} "
        f"+{inch_text(spec.WHOLE_DEPTH_BAND[0], spec.WHOLE_DEPTH_PLACES)}"
        f"/{inch_text(spec.WHOLE_DEPTH_BAND[1], spec.WHOLE_DEPTH_PLACES)}; "
        "SETS BACKLASH WITH CONE GEARS MHA-DT-03",
        f"FORM CUTTER:  #{spec.CUTTER_NUMBER} "
        f"({spec.CUTTER_TEETH_RANGE[0]}-{spec.CUTTER_TEETH_RANGE[1]}T RANGE, "
        f"{spec.CUTTER_REFERENCE_TEETH}T PROFILE)",
        f"PITCH TOOTH THICKNESS (REF):  {inch_text(spec.PITCH_TOOTH_THICKNESS_MM, 4)}",
        f"TOOTH FORM:  {TOOTH_FORM_NOTE}",
        # A finished-part requirement, not a setup check (machinist review of
        # #2712; the crank drive gear's precedent, PR #2331 round 9). Its
        # reason is the CUTTER PLUNGE row's, printed once there (rule 7).
        f"TOOTH RUNOUT TO BORE:  {inch_text(TOOTH_RUNOUT_TIR_MM, 3)} TIR MAX",
    )
)
