r"""Pure-data contract for MHA-DT-38, the cone tip bushing.

Owner decision C1 keyed, 2026-11-09 (PR #1992; ``cone_tip_cluster``): a
brass (C36000) ring pressed on the pivot of T006 (MHA-DT-37) against T006's
north face.  Its north face bears on the end of the MHA-DT-39 end screw,
which sets the shaft's end play (``cone_stack_end_play.SHAFT_END_PLAY``).
Every size is ``cone_tip_cluster``'s: Ø.228 x .160 at the title block's
.XXX, the bore reamed .0615 +.0005/-.0000 for the press on the Ø.0625
+.0000/-.0003 pivot.

The bore's callout names the fit and its mate, with the interference the
printed limits give as REF (drawing-guidelines.md rule 4).  The wall over the
bore holds rule 17's .080 target at the worst case (smallest OD, largest
bore; ``cone_tip_cluster`` asserts it, restated here at this sheet's bands).

#290: the sheet prints decimal inch; every length is the exact millimetre
value of its inch nominal.

Local frame: one revolve about local +X.  The south face, pressed against
T006's north face, is the origin plane (x = 0, the Right Plane); the north
face, on the end screw, is at x = LENGTH (``NorthFace``).  ``Axis1`` is the
bore axis.

PURE DATA, no SolidWorks/COM imports.
"""

from __future__ import annotations

import math

import _config
import cone_tip_cluster as tip
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm

PART_NAME = "dt-cone-tip-bushing"
UNIT = drawing_unit("parts/dt-cone-tip-bushing", _config.parts("dt-cone-tip-bushing"))
MM_PER_IN = tip.MM_PER_IN

OUTER_DIA = tip.BUSHING_OD_MM  # .228
LENGTH = tip.BUSHING_LENGTH_MM  # .160
SIZE_PLACES = tip.BUSHING_PLACES  # .XXX
BORE_DIA = tip.BUSHING_BORE_DIA_MM  # .0615 reamer
BORE_DIA_BAND = tip.BUSHING_BORE_BAND  # (upper, lower) +.0005/-.0000
BORE_PLACES = 4

# The pivot the bushing is pressed on: T006's own part (MHA-DT-37).  Quoted
# only to name the mate (rule 4); the offline test checks it against the
# registry.
PIVOT_NUMBER = "MHA-DT-37"
END_SCREW_NUMBER = "MHA-DT-39"

# (min, max) diametral interference of the reamed bore on the pivot.
PRESS_INTERFERENCE = tip.BUSHING_PRESS_INTERFERENCE_MM
if PRESS_INTERFERENCE[0] <= 0.0:
    raise AssertionError(f"MHA-DT-38 press interference {PRESS_INTERFERENCE} mm")

# Brass wall on radius at the worst case: the smallest OD at its .XXX band
# over the largest reamed bore.
OUTER_DIA_BAND = printed_band_mm(SIZE_PLACES, unit=UNIT)
WALL_WORST = (OUTER_DIA - OUTER_DIA_BAND - (BORE_DIA + max(BORE_DIA_BAND))) / 2.0
if WALL_WORST < WALL_TARGET_MM:
    raise AssertionError(
        f"MHA-DT-38 wall {WALL_WORST / MM_PER_IN:.4f} in under the .080 target"
    )


def inch_text(value_mm: float, places: int) -> str:
    """An mm length as ASME decimal-inch text (no leading zero)."""
    text = f"{value_mm / MM_PER_IN:.{places}f}"
    return text[1:] if text.startswith("0.") else text


def _floor_text(value_mm: float, places: int) -> str:
    """A stated minimum, never rounded up past the derived limit."""
    scaled = math.floor(round(value_mm / MM_PER_IN * 10**places, 6))
    return inch_text(scaled / 10**places * MM_PER_IN, places)


def _ceil_text(value_mm: float, places: int) -> str:
    """A stated maximum, never rounded down past the derived limit."""
    scaled = math.ceil(round(value_mm / MM_PER_IN * 10**places, 6))
    return inch_text(scaled / 10**places * MM_PER_IN, places)


# Rule 4: REAM, the standard fit name and its mate by drawing number, the
# interference the printed limits give as REF.  THRU: the section shows it.
BORE_CALLOUT = "\n".join(
    (
        "REAM THRU",
        f"PRESS FIT ON {PIVOT_NUMBER} PIVOT",
        f"(INTERFERENCE {_floor_text(PRESS_INTERFERENCE[0], 4)}-"
        f"{_ceil_text(PRESS_INTERFERENCE[1], 4)} REF)",
    )
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BushingProfile": {"OuterDia", "BoreDia", "Length"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BushingProfile": {
        "OuterDia": SIZE_PLACES,
        "BoreDia": BORE_PLACES,
        "Length": SIZE_PLACES,
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked MHA-DT-38 dimension needs authored places")

ISOMETRIC_VIEW_SCALE = (8, 1)
ISOMETRIC_VIEW_NOTE = (
    f"ISOMETRIC VIEW SCALE {ISOMETRIC_VIEW_SCALE[0]}:{ISOMETRIC_VIEW_SCALE[1]}"
)
