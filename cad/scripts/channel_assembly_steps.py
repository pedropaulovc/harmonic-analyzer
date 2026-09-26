"""The MHA-A02 channel-assembly fit-up sequence, numbered in one place.

The drive_train_steps pattern (MHA-A03): a step's number is its position in
SEQUENCE, so inserting a step renumbers every later one and every pointer that
cites a step by key follows. The sheet prints the step text; this module holds
only the order. Pure data: no SolidWorks, no config reads.
"""

from __future__ import annotations

DRAWING_NUMBER = "MHA-A02"
# The north pivot bracket is set in the drive-train fit-up, off the located
# drum bank (rocker_bank_layout), so this sheet points there.
FITUP_DRAWING_NUMBER = "MHA-A03"

SEQUENCE: tuple[str, ...] = (
    "rocker-stack-accepted",
    "north-ear-datum",
    "south-washer-fitted",
    "south-bracket-feeler-set",
    "end-play-accepted",
)

_NUMBER = {key: index for index, key in enumerate(SEQUENCE, start=1)}
if len(_NUMBER) != len(SEQUENCE):
    raise ValueError("channel_assembly_steps.SEQUENCE repeats a key")


def step_number(key: str) -> int:
    """The printed number of ``key``; a KeyError names an unknown step."""
    return _NUMBER[key]


def step_ref(key: str) -> str:
    """A pointer another sheet prints, e.g. ``MHA-A02 STEP 4``."""
    return f"{DRAWING_NUMBER} STEP {step_number(key)}"
