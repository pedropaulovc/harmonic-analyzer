"""The MHA-MG-00 magnifier fit-up sequence, numbered in one place.

The ch_channel_assembly_steps pattern: a step's number is its position in
STEPS, so inserting a step renumbers every later one and every pointer that
cites a step by key follows. The sheet prints the step text
(mg_magnifier_assembly_sheet.STEP_TEXT); this module holds only the order.
Pure data: no SolidWorks, no config reads.

Each step does one thing (drawing-guidelines.md rule 22). A numbered step
opens with its action; its check and that check's remedies follow it as
lettered sub-steps (``2``, ``2A`` check, ``2B`` remedy), the form the shared
step lint reads (_test_assembly_steps, #2248). The bench builds the wheel
group and the lever group apart. The wheel bar is clamped to the front
column, and the bracket screwed to the summing lever, at MHA-HA-00; the lever
wire goes on after both, so its steps come last (WIRE_HOOKED_KEY to
WIRE_TIED_KEY, which the MHA-SH-VN-56 sheet cites as one range).
"""

from __future__ import annotations

DRAWING_NUMBER = "MHA-MG-00"

DRUM_PRESSED_KEY = "drum-pressed"
DRUM_HELD_KEY = "drum-held"
AXLE_PRESSED_KEY = "axle-pressed"
AXLE_HELD_KEY = "axle-held"
AXLE_TRIAL_KEY = "axle-trial-fitted"
AXLE_CHECKED_KEY = "axle-checked"
AXLE_ACCEPTED_KEY = "axle-accepted"
COLUMN_CLAMP_STARTED_KEY = "column-clamp-started"
ENDSHAKE_SET_KEY = "endshake-set"
ENDSHAKE_CHECKED_KEY = "endshake-checked"
LOCKNUT_JAMMED_KEY = "locknut-jammed"
LEVER_THREADED_KEY = "lever-threaded"
CLAMP_SET_KEY = "clamp-set"
CLAMP_HELD_KEY = "clamp-held"
FIXTURE_SET_KEY = "fixture-set"
FIXTURE_HELD_KEY = "fixture-held"
WIRE_HOOKED_KEY = "lever-wire-hooked"
WHEEL_TURNED_KEY = "wheel-turned"
WIRE_TIED_KEY = "lever-wire-tied"

# One tuple per numbered step: its action, then its lettered sub-steps.
STEPS: tuple[tuple[str, ...], ...] = (
    # Wheel group. Each press is accepted at the bench before anything else
    # goes on it (rule 23): it does not turn or slide by hand, and a slip fit
    # has its own single-action remedies.
    (DRUM_PRESSED_KEY, DRUM_HELD_KEY, "drum-pulled-off", "drum-bonded"),
    (AXLE_PRESSED_KEY, AXLE_HELD_KEY, "axle-pressed-out", "axle-remade", "axle-repressed"),
    (
        AXLE_TRIAL_KEY,
        "trial-nuts-jammed",
        AXLE_CHECKED_KEY,
        "trial-parts-removed-to-press",
        "axle-pressed-further",
        "axle-pressed-back",
        "axle-rechecked",
    ),
    ("trial-parts-removed",),
    ("column-clamps-fitted",),
    (COLUMN_CLAMP_STARTED_KEY, "column-clamp-screws-left-loose"),
    ("axle-oiled",),
    ("wheel-stacked",),
    (
        ENDSHAKE_SET_KEY,
        ENDSHAKE_CHECKED_KEY,
        "endshake-loosened",
        "endshake-tightened",
        "endshake-repeated",
    ),
    (LOCKNUT_JAMMED_KEY, "endshake-rechecked", "locknut-loosened", "locknut-reset"),
    (AXLE_ACCEPTED_KEY, "axle-stack-removed", "axle-reset"),
    # Lever group.
    (LEVER_THREADED_KEY,),
    ("clamp-thumb-screw-started",),
    # Each hand-set clamp is checked to hold its setting (rule 23).
    (CLAMP_SET_KEY, "clamp-thumb-screw-tightened", CLAMP_HELD_KEY, "clamp-reset"),
    ("fixture-thumb-screw-started",),
    ("rod-through-fixture",),
    ("rod-seated",),
    (FIXTURE_SET_KEY, "fixture-thumb-screw-tightened", FIXTURE_HELD_KEY, "fixture-reset"),
    # Lever wire, on the machine.
    (WIRE_HOOKED_KEY, "lever-wire-led-down", "lever-wire-hook-twisted", "lever-wire-hook-trimmed"),
    ("machine-at-rest",),
    (WHEEL_TURNED_KEY,),
    ("lever-wire-wrapped", "lever-wire-through-tie", "lever-wire-tie-twisted", WIRE_TIED_KEY),
)
SEQUENCE: tuple[str, ...] = tuple(key for step in STEPS for key in step)

# Sub-step letters skip I and O, which read as 1 and 0.
_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"
_NUMBER = {
    key: f"{number}{_LETTERS[index - 1] if index else ''}"
    for number, step in enumerate(STEPS, start=1)
    for index, key in enumerate(step)
}
if len(_NUMBER) != len(SEQUENCE):
    raise ValueError("mg_magnifier_assembly_steps.STEPS repeats a key")
if max(len(step) for step in STEPS) > len(_LETTERS) + 1:
    raise ValueError("a numbered step runs out of sub-step letters")


def step_number(key: str) -> str:
    """The printed head of ``key`` (``12`` or ``12A``); a KeyError names an
    unknown step."""
    return _NUMBER[key]


def step_ref(key: str) -> str:
    """A pointer another sheet prints, e.g. ``MHA-MG-00 STEP 11``."""
    return f"{DRAWING_NUMBER} STEP {step_number(key)}"
