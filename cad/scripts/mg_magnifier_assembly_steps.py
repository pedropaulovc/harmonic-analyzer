"""The MHA-MG-000 magnifier fit-up sequence, numbered in one place.

The ch_channel_assembly_steps pattern: a step's number is its position in
SEQUENCE, so inserting a step renumbers every later one and every pointer
that cites a step by key follows. The sheet prints the step text
(mg_magnifier_assembly_notes.STEP_TEXT); this module holds only the order.
Pure data: no SolidWorks, no config reads.

The bench builds the wheel group and the lever group apart. The wheel bar is
clamped to the front column, and the bracket screwed to the summing lever, at
MHA-HA-000; the lever wire goes on after both, so its two steps come last.
"""

from __future__ import annotations

DRAWING_NUMBER = "MHA-MG-000"

AXLE_PRESSED_KEY = "axle-pressed"
COLUMN_CLAMP_STARTED_KEY = "column-clamp-started"
ENDSHAKE_SET_KEY = "endshake-set"
LOCKNUT_JAMMED_KEY = "locknut-jammed"
CLAMP_SET_KEY = "clamp-set"
FIXTURE_SET_KEY = "fixture-set"
WIRE_HOOKED_KEY = "lever-wire-hooked"
WIRE_TIED_KEY = "lever-wire-tied"

SEQUENCE: tuple[str, ...] = (
    AXLE_PRESSED_KEY,
    COLUMN_CLAMP_STARTED_KEY,
    "drum-pressed",
    "wheel-stacked",
    ENDSHAKE_SET_KEY,
    LOCKNUT_JAMMED_KEY,
    "collar-pressed",
    CLAMP_SET_KEY,
    FIXTURE_SET_KEY,
    WIRE_HOOKED_KEY,
    WIRE_TIED_KEY,
)

_NUMBER = {key: index for index, key in enumerate(SEQUENCE, start=1)}
if len(_NUMBER) != len(SEQUENCE):
    raise ValueError("mg_magnifier_assembly_steps.SEQUENCE repeats a key")


def step_number(key: str) -> int:
    """The printed number of ``key``; a KeyError names an unknown step."""
    return _NUMBER[key]


def step_ref(key: str) -> str:
    """A pointer another sheet prints, e.g. ``MHA-MG-000 STEP 11``."""
    return f"{DRAWING_NUMBER} STEP {step_number(key)}"
