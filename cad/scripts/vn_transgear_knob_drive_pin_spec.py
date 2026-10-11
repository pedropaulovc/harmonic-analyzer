r"""MHA-VN-038 transgear-knob-drive-pin: McMaster 98381A433 stock dowel.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Two are pressed into the brass knob drive collar (MHA-PD-022) and
stand ``pd_transgear_removable_spec.DRIVE_PIN_PROUD`` out of its front (seat)
face, where the removable sprocket's two holes drop over them.  The knob
takes the 3/16 length of the crank's 3/32 dowel, and its holes are reamed
THROUGH the collar body, the press depth set from the seat face by a stop.

Catalogue: 3/32 x 3/16 alloy-steel dowel, Round x Chamfer ends; the size row
and the diameter tolerance are ``diagnostics.diag_mcmaster_dowel``'s.

Part frame: axis local +Y through the origin; the pressed (chamfered) end
face at y = 0, the rounded lead end at y = LENGTH.
"""

from __future__ import annotations

from _mcmaster_98381a433 import (
    DIA_BAND_IN,  # noqa: F401 -- re-exported: catalogue diameter tolerance (in)
    DOWEL_SIZE,
    MM_PER_IN,  # noqa: F401 -- re-exported with the inch band
)
from pd_transgear_removable_spec import DRIVE_PIN_DIA, DRIVE_PIN_PROUD, PLATE, PLATE_BAND

SKU = "98381A433"
DIA, LENGTH = DOWEL_SIZE  # 2.38125 x 4.7625
if abs(DIA - DRIVE_PIN_DIA) > 1e-12:
    raise AssertionError(f"{SKU} is not the seat interface's drive pin")

# No floor sets the depth in a through hole: the fitter presses each pin in
# from the seat face onto a stop that leaves it DRIVE_PIN_PROUD out, to
# +/-PROUD_SET_TOL (the installation note on the MHA-VN-038 sheet prints the
# range).  The stop sets the tip, so the dowel's length grade moves only the
# pressed end, inside the collar (pd_transgear_drive_collar_spec checks it).
PROUD_SET_TOL = 0.10
PROUD_RANGE = (DRIVE_PIN_PROUD - PROUD_SET_TOL, DRIVE_PIN_PROUD + PROUD_SET_TOL)
# The nominal pin's pressed end stands this far behind the seat face, inside
# the MHA-PD-022 collar's through hole: the press fit's engaged length.
PRESS_DEPTH = LENGTH - DRIVE_PIN_PROUD  # 2.3625

# The thumbnut's Ø14 neck clamps the T24 on its front face and covers the
# inner half of each pin hole, so a tip standing past that face would take
# the clamp off the wheel.  The highest-set pin stays inside the THINNEST
# wheel by at least one more set tolerance.
THINNEST_PLATE = PLATE + min(PLATE_BAND)  # 2.7
TIP_INSET_MIN = PROUD_SET_TOL


def checked_tip_inset(proud_max: float, plate_min: float) -> float:
    """Air from the highest pin tip back to the thinnest wheel's front face,
    where the thumbnut's neck bears; raises below ``TIP_INSET_MIN``."""
    inset = plate_min - proud_max
    if inset < TIP_INSET_MIN - 1e-9:
        raise AssertionError(
            f"a knob drive pin {proud_max:.3f} proud reaches within {inset:.3f} of"
            f" the {plate_min:.2f} wheel's front face (thumbnut clamp)"
        )
    return inset


TIP_INSET_WORST = checked_tip_inset(max(PROUD_RANGE), THINNEST_PLATE)  # 0.20
