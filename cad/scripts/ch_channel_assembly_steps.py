"""The MHA-CH-000 channel-assembly fit-up sequence, numbered in one place.

The drive_train_steps pattern (MHA-DT-000): a step's number is its position in
SEQUENCE, so inserting a step renumbers every later one and every pointer that
cites a step by key follows. The sheet prints the step text; this module holds
only the order. Pure data: no SolidWorks, no config reads.
"""

from __future__ import annotations

import dt_drive_train_steps

DRAWING_NUMBER = "MHA-CH-000"
# The north pivot bracket is set by DRO in the drive-train fit-up, off the
# located drum bank's datum (user ruling on #936 P1 b, option A), so this sheet
# points there by key: MHA-DT-000 prints the same key's number as the step head,
# so the pointer follows any renumbering of MHA-DT-000.
NORTH_BRACKET_SET_KEY = "north-pivot-bracket-set"
NORTH_BRACKET_SET_REF = dt_drive_train_steps.step_ref(NORTH_BRACKET_SET_KEY)
# Each rod's ring is captured in its closed cam slot as the cylinder stack goes
# together (MHA-DT-000 BANK_STEPS), and the rod's fork is pinned to its arm with
# a pin pressed at the bench, so the rod + arm pair must be pinned BEFORE that
# step: the pinning step points there by key, and that drive-train step points
# back at the pinning step (RODS_PINNED_KEY). The hub stack is proved on the
# shaft first, while the arms are still loose.
CYLINDER_STACK_KEY = "cylinder-stack-accepted"
CYLINDER_STACK_REF = dt_drive_train_steps.step_ref(CYLINDER_STACK_KEY)
RODS_PINNED_KEY = "rod-forks-pinned"

SEQUENCE: tuple[str, ...] = (
    "rocker-stack-accepted",
    RODS_PINNED_KEY,
    "north-ear-datum",
    "south-washer-fitted",
    "south-bracket-spring-set",
    "shaft-cut-to-fit",
    "set-screws-driven",
    "preload-accepted",
)

_NUMBER = {key: index for index, key in enumerate(SEQUENCE, start=1)}
if len(_NUMBER) != len(SEQUENCE):
    raise ValueError("ch_channel_assembly_steps.SEQUENCE repeats a key")


def step_number(key: str) -> int:
    """The printed number of ``key``; a KeyError names an unknown step."""
    return _NUMBER[key]


def step_ref(key: str) -> str:
    """A pointer another sheet prints, e.g. ``MHA-CH-000 STEP 4``."""
    return f"{DRAWING_NUMBER} STEP {step_number(key)}"


RODS_PINNED_REF = step_ref(RODS_PINNED_KEY)
