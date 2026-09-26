r"""Pure data: MHA-102's cross hole for the MHA-144 collar's spring pin (R1a).

User ruling 2026-09-24: the collar is pinned to the arbor with the rig's one
pin family, the ASME B18.8.2 1/16 x 1/2 slotted spring pin, in a hole drilled
with the MHA-135 1/16 drill (``pinion_strap_pin_spec``).  The hole is drilled
at the bench at a .X station from the head rear face, on the crossrod's local
axis so one V-block setup serves both cross holes.

Kept apart from ``pinion_arbor_spec`` on purpose: the drive-train assembly
imports that module for the pin STATION, and this one reads the strap-pin
spec, which the assembly never does.  The part, its drawing and the collar
spec read the hole from here.
"""

from __future__ import annotations

import pinion_strap_pin_spec as _pin
from pinion_arbor_geometry import (
    NECK_LEN,
    PIN_STATION_FROM_HEAD_REAR,
    SHAFT_DIA,
)
from pinion_arbor_spec import (
    FRONT_JOURNAL_FROM_HEAD_REAR,
    LAND_FINISH_RUNOUT,
    LINEAR_X_BAND,
    PIN_STATION_BAND,
    SHAFT_DIA_BAND,
)

PIN_HOLE_DIA = _pin.HOLE_DIA
PIN_HOLE_DIA_BAND = _pin.HOLE_BAND
PIN_HOLE_DIA_MAX = _pin.HOLE_MAX
PIN_HOLE_CALLOUT = _pin.DRILL_THRU_CALLOUT

# At its worst corner the hole stays clear of the front land and its Ra 1.6
# run-out (the pin never enters the land), clear of the Ø10.5 neck shoulder,
# and leaves the U27 2.0 web target of steel beside it.
PIN_HOLE_LAND_CLEARANCE = (
    FRONT_JOURNAL_FROM_HEAD_REAR
    - LINEAR_X_BAND
    - LAND_FINISH_RUNOUT
    - (PIN_STATION_FROM_HEAD_REAR + PIN_STATION_BAND + PIN_HOLE_DIA_MAX / 2.0)
)
PIN_HOLE_NECK_CLEARANCE = (
    PIN_STATION_FROM_HEAD_REAR
    - PIN_STATION_BAND
    - PIN_HOLE_DIA_MAX / 2.0
    - (NECK_LEN + LINEAR_X_BAND)
)
PIN_HOLE_LIGAMENT_WORST = (SHAFT_DIA + SHAFT_DIA_BAND[1] - PIN_HOLE_DIA_MAX) / 2.0
for _name, _margin in (
    ("front land run-out", PIN_HOLE_LAND_CLEARANCE),
    ("Ø10.5 neck shoulder", PIN_HOLE_NECK_CLEARANCE),
    ("arbor ligament beside the hole", PIN_HOLE_LIGAMENT_WORST),
):
    if _margin < 2.0:
        raise AssertionError(f"collar pin hole: {_name} is {_margin:.2f}, under 2.0")
