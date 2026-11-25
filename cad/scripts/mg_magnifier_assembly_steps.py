"""The MHA-MG-00 magnifier fit-up sequence, numbered in one place.

The ch_channel_assembly_steps pattern: a step's number is its position in
STEPS, so inserting a step renumbers every later one and every pointer that
cites a step by key follows. The release's ASSEMBLY.md prints the step text
(mg_magnifier_assembly_sheet.STEP_TEXT, ha_assembly_package); this module
holds only the order.
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

DRUM_BONDED_KEY = "drum-bonded"
DRUM_HELD_KEY = "drum-held"
PRESS_SLEEVE_MADE_KEY = "press-sleeve-made"
SPACER_FITTED_KEY = "spacer-fitted"
AXLE_DRY_FITTED_KEY = "axle-dry-fitted"
AXLE_BONDED_KEY = "axle-bonded"
AXLE_HELD_KEY = "axle-held"
AXLE_TRIAL_KEY = "axle-trial-fitted"
TRIAL_WASHER_SEATED_KEY = "trial-washer-seated"
AXLE_NUT_ON_THREAD_KEY = "trial-nut-on-thread"
AXLE_CHECKED_KEY = "axle-checked"
AXLE_SINK_RECORDED_KEY = "axle-sink-recorded"
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
    # Wheel group. Each fixed joint is accepted at the bench before anything
    # else goes on it (rule 23): it does not turn or slide by hand.
    # Owner ruling 2026-11-24, fit audit question 17: the drum is always
    # bonded on a spigot turned to slide in its drilled bore, centred on an
    # indicator while wet; a drum that turns once cured is stripped and
    # bonded again. Rule 22 (machinist review of run 20261125T172832344Z,
    # r2 and r3): one action per step, a check apart from its remedy, so the
    # S4 seat is its own check after the cure and the strip runs as pull
    # off, clean, return.
    (
        DRUM_BONDED_KEY,
        "drum-centred",
        "drum-bond-cured",
        "drum-seated",
        DRUM_HELD_KEY,
        "drum-stripped",
        "drum-cleaned",
        "drum-rebonded",
    ),
    # The sleeve the axle is pushed through on its shoulder and the spacer
    # are their own steps (rule 22).
    (PRESS_SLEEVE_MADE_KEY,),
    (SPACER_FITTED_KEY,),
    # Owner ruling 2026-11-24, fit audit part 2, C11 ("Yes, set to the trial
    # stack") with fit audit question 18 (the axle is bonded): a cured bond
    # cannot be re-pressed, so C11's trial stack can only be set dry, before
    # the bond. The axle goes in with
    # its plain end flush on the surface plate, the expected setting; the
    # trial accepts on C11's three things to see, the first nut on thread,
    # the thread end inside DETAIL B and (the flush start, never pushed
    # further) the plain end not proud, and on the front washer seated on
    # the hub, which reads the shank step inside it (mg_wheel_group
    # TRIAL_STEP_INSIDE_HUB_MIN). A short thread end slides the axle out by
    # the shortfall to the window's middle and trials again from the seat.
    # Any other failure strips the trial and pushes the axle out; a part out
    # of its limits (the bar's depth, the spacer's length, the hub's, the
    # washers' and nuts' thickness), else the axle, is replaced, and the
    # trial restarts from the spacer.
    (AXLE_DRY_FITTED_KEY,),
    (
        AXLE_TRIAL_KEY,
        TRIAL_WASHER_SEATED_KEY,
        "trial-feeler-placed",
        "trial-nuts-jammed",
        AXLE_NUT_ON_THREAD_KEY,
        AXLE_CHECKED_KEY,
        "trial-nuts-off",
        "axle-sunk",
        "trial-rerun",
        "trial-stripped",
        "trial-axle-withdrawn",
        "stack-parts-measured",
        "stack-part-replaced",
        "axle-replaced",
        "trial-refitted",
    ),
    (AXLE_SINK_RECORDED_KEY,),
    # The spacer comes off with the trial stack: on the shank during the
    # bond it would sit in the squeeze-out at the bar's face.
    ("trial-parts-removed",),
    ("axle-withdrawn",),
    # Bonded to the trial's setting, squared to the bar while wet (nothing
    # else squares a bonded axle), cured, then accepted by hand (rule 23).
    (
        AXLE_BONDED_KEY,
        "axle-squared",
        "axle-bond-cured",
        AXLE_HELD_KEY,
        "axle-stripped",
        "axle-cleaned",
        "axle-rebonded",
    ),
    ("column-clamps-fitted",),
    (COLUMN_CLAMP_STARTED_KEY, "column-clamp-screws-left-loose"),
    ("axle-oiled",),
    ("spacer-refitted",),
    ("wheel-stacked",),
    (
        ENDSHAKE_SET_KEY,
        ENDSHAKE_CHECKED_KEY,
        "endshake-loosened",
        "endshake-tightened",
        "endshake-repeated",
    ),
    (LOCKNUT_JAMMED_KEY, "endshake-rechecked", "locknut-loosened", "locknut-reset"),
    (
        AXLE_ACCEPTED_KEY,
        "locknut-backed-off",
        "axle-endshake-closed",
        "endshake-reset",
    ),
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
    (
        WIRE_HOOKED_KEY,
        "lever-wire-led-down",
        "lever-wire-hook-knotted",
        "lever-wire-hook-closed",
    ),
    ("machine-at-rest",),
    (WHEEL_TURNED_KEY,),
    (
        "lever-wire-wrapped",
        "lever-wire-through-tie",
        "lever-wire-tie-knotted",
        "lever-wire-knots-held",
        "lever-wire-cut-off",
        "lever-wire-renewed",
        WIRE_TIED_KEY,
    ),
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
