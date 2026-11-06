"""The MHA-MG-00 magnifier fit-up sequence, numbered in one place.

The ch_channel_assembly_steps pattern: a step's number is its position in
SEQUENCE, so inserting a step renumbers every later one and every pointer
that cites a step by key follows. The sheet prints the step text
(mg_magnifier_assembly_sheet.STEP_TEXT); this module holds only the order.
Pure data: no SolidWorks, no config reads.

Each step does one thing (drawing-guidelines.md rule 22): a check and its
remedy are their own steps. The bench builds the wheel group and the lever
group apart. The wheel bar is clamped to the front column, and the bracket
screwed to the summing lever, at MHA-HA-00; the lever wire goes on after
both, so its steps come last (WIRE_HOOKED_KEY to WIRE_TIED_KEY, which the
MHA-SH-VN-56 sheet cites as one range).
"""

from __future__ import annotations

DRAWING_NUMBER = "MHA-MG-00"

AXLE_PRESSED_KEY = "axle-pressed"
AXLE_TRIAL_KEY = "axle-trial-fitted"
AXLE_CHECKED_KEY = "axle-checked"
COLUMN_CLAMP_STARTED_KEY = "column-clamp-started"
ENDSHAKE_SET_KEY = "endshake-set"
ENDSHAKE_CHECKED_KEY = "endshake-checked"
LOCKNUT_JAMMED_KEY = "locknut-jammed"
LEVER_THREADED_KEY = "lever-threaded"
CLAMP_SET_KEY = "clamp-set"
FIXTURE_SET_KEY = "fixture-set"
WIRE_HOOKED_KEY = "lever-wire-hooked"
WIRE_TIED_KEY = "lever-wire-tied"

SEQUENCE: tuple[str, ...] = (
    # Wheel group.
    "drum-pressed",
    AXLE_PRESSED_KEY,
    AXLE_TRIAL_KEY,
    "trial-nuts-jammed",
    AXLE_CHECKED_KEY,
    "trial-parts-removed",
    "axle-pressed-further",
    "column-clamps-fitted",
    COLUMN_CLAMP_STARTED_KEY,
    "axle-oiled",
    "wheel-stacked",
    ENDSHAKE_SET_KEY,
    ENDSHAKE_CHECKED_KEY,
    "endshake-loosened",
    "endshake-tightened",
    LOCKNUT_JAMMED_KEY,
    "endshake-rechecked",
    "locknut-reset",
    "axle-accepted",
    # Lever group.
    LEVER_THREADED_KEY,
    "clamp-thumb-screw-started",
    CLAMP_SET_KEY,
    "clamp-thumb-screw-tightened",
    "fixture-thumb-screw-started",
    "rod-through-fixture",
    "rod-seated",
    FIXTURE_SET_KEY,
    "fixture-thumb-screw-tightened",
    # Lever wire, on the machine.
    WIRE_HOOKED_KEY,
    "lever-wire-hook-twisted",
    "lever-wire-hook-trimmed",
    "machine-at-rest",
    "wheel-turned",
    "lever-wire-wrapped",
    "lever-wire-through-tie",
    "lever-wire-tie-twisted",
    WIRE_TIED_KEY,
)

_NUMBER = {key: index for index, key in enumerate(SEQUENCE, start=1)}
if len(_NUMBER) != len(SEQUENCE):
    raise ValueError("mg_magnifier_assembly_steps.SEQUENCE repeats a key")


def step_number(key: str) -> int:
    """The printed number of ``key``; a KeyError names an unknown step."""
    return _NUMBER[key]


def step_ref(key: str) -> str:
    """A pointer another sheet prints, e.g. ``MHA-MG-00 STEP 11``."""
    return f"{DRAWING_NUMBER} STEP {step_number(key)}"
