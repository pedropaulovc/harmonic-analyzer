"""Drawing-only fit-up instructions for MHA-DT-00.

Part specifications own permitted cuts, limits and pin fits. The assembly
prints their bench checks and remedies, without design-clearance narration.
Kept separate from the explode contract so text changes do not rebuild CAD.

The package prints decimal inch (#290).  The inch helpers below are the one
formatter for every value MHA-DT-00's steps, checks and fit-up notes print:
a window rounds inward, a maximum down and a minimum up, so the sheet never
admits a value the owning spec refuses; a nominal (a feeler, a reference)
rounds to its places.
"""

import math

from _hole_spec import NUMBER_DRILL_MM
from _printed_tolerance import drilled_oversize_mm

import dt_crank_handle_spec as _handle
import dt_crank_pinion_spec as pinion
import dt_pinion_lever_geometry as _lever
import dt_pinion_lever_pin_spec as _lever_pin

MM_PER_IN = 25.4


def inch_text(value_mm: float, places: int) -> str:
    """``value_mm`` as decimal-inch print text, rounded: ``.018``, ``5.4060``."""
    text = f"{value_mm / MM_PER_IN:.{places}f}"
    return text[1:] if text.startswith("0.") else text


def inch_floor_mm(value_mm: float, places: int) -> float:
    """``value_mm`` floored onto the ``places``-place inch grid, in mm."""
    return math.floor(value_mm / MM_PER_IN * 10**places + 1e-9) / 10**places * MM_PER_IN


def inch_ceil_mm(value_mm: float, places: int) -> float:
    """``value_mm`` raised onto the ``places``-place inch grid, in mm."""
    return math.ceil(value_mm / MM_PER_IN * 10**places - 1e-9) / 10**places * MM_PER_IN


def inch_window(limits_mm: tuple[float, float], places: int, joiner: str = "-") -> str:
    """A (min, max) window, rounded inward."""
    low = inch_ceil_mm(limits_mm[0], places)
    high = inch_floor_mm(limits_mm[1], places)
    if low > high:
        raise ValueError(f"{limits_mm!r} mm holds no {places}-place inch window")
    return f"{inch_text(low, places)}{joiner}{inch_text(high, places)}"


def inch_max_text(limit_mm: float, places: int) -> str:
    """A maximum, rounded down: ``.004``."""
    return inch_text(inch_floor_mm(limit_mm, places), places)


def inch_min_text(limit_mm: float, places: int) -> str:
    """A minimum, rounded up: ``.718``."""
    return inch_text(inch_ceil_mm(limit_mm, places), places)


# A feeler reading prints to the thousandth, a feeler gage's leaf step.
FEELER_PLACES = 3

# Owner ruling 2026-10-24 (#1900): MHA-DT-34 cures on a mandrel through the
# MHA-DT-08 pivot bore.  Step 7 prints the requirement, the bore's offset off
# that axis that MHA-DT-34's skimmed wall is budgeted on, not the mandrel;
# MHA-DT-32 passes through the larger MHA-DT-34 bore and does not locate it.
HANDLE_FERRULE_CURE = (
    "THE MHA-DT-34 BORE CENTRED ON THE MHA-DT-08 PIVOT BORE WITHIN "
    f"{inch_max_text(_handle.FERRULE_OFFSET_MAX, 3)}"
)

# The check's feeler rounds to the thousandth but never under the air it
# proves; the band and shoulder minima round up.
T120_FITUP_FEELER_TEXT = inch_text(pinion.T120_FITUP_FEELER_MM, FEELER_PLACES)
if float(T120_FITUP_FEELER_TEXT) * MM_PER_IN < pinion.T120_FITUP_FEELER_MM - 1e-9:
    raise AssertionError("the printed T120 fit-up feeler is thinner than its check")
# A check and its remedy are separate steps, and each check does one thing
# (drawing-guidelines rule 22): push, then the band, then the shoulder.
T120_FITUP_PUSH = (
    f"PUSH {pinion.T120_FITUP_PUSHED[0]} AND {pinion.T120_FITUP_PUSHED[1]} TOWARD EACH OTHER."
)
T120_FITUP_BAND_CHECK = (
    f"TURN MHA-DT-07 SLOWLY BY HAND: A {T120_FITUP_FEELER_TEXT} FEELER PASSES ALL ROUND "
    "BETWEEN THE MHA-DT-10 BAND AND THE T120 TIPS."
)
T120_FITUP_SHOULDER_CHECK = (
    f"TURN IT AGAIN: THE {T120_FITUP_FEELER_TEXT} FEELER PASSES ALL ROUND BETWEEN THE "
    "MHA-DT-10 SHOULDER AND THE T120 FRONT FACE."
)
T120_FITUP_BAND_REMEDY = (
    "IF IT STOPS AT THE BAND, TURN MHA-DT-10'S BAND DOWN, "
    f"Ø{inch_min_text(pinion.TURNED_DIA_FITUP_MIN, 3)} MIN."
)
T120_FITUP_SHOULDER_REMEDY = (
    "IF IT STOPS AT THE SHOULDER, FACE THE SHOULDER BACK, "
    f"{inch_min_text(pinion.SHOULDER_LENGTH_FITUP_MIN, 3)} MIN."
)

# The lever and lift-rod prints defer this hole to assembly. The pin contract
# specifies a stock 1/16 in slip fit retained by peening, not a reamed press fit.
# The drill must cut inside both prints' Ø.064 +.004/0 DRILLED HOLES limits:
# #51 (.0670) does; #52 (.0635) is under the minimum (Codjiflo on #2106).
LEVER_PIN_HOLE_DRILL = "#51"
_LEVER_PIN_DRILL_MM = NUMBER_DRILL_MM[LEVER_PIN_HOLE_DRILL]
if not (
    _lever.PIN_HOLE_DIA
    <= _LEVER_PIN_DRILL_MM
    <= _lever.PIN_HOLE_DIA + drilled_oversize_mm(unit=_lever.UNIT)
):
    raise AssertionError(
        f"LEVER PIN SET's {LEVER_PIN_HOLE_DRILL} drill ({_LEVER_PIN_DRILL_MM} mm) "
        "cuts outside the lever and lift rod's drilled pin-hole limits"
    )
LEVER_PIN_HOLE_FIT = "\n".join(
    (
        f"HOLE AT {_lever_pin.LEVER_NUMBER}'S PRINTED STATION: "
        f"{LEVER_PIN_HOLE_DRILL} DRILL THRU;",
        f"{_lever_pin.PIN_NUMBER} SLIP FIT.",
    )
)
