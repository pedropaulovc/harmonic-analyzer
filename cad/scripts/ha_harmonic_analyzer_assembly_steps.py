"""The MHA-HA-00 final-assembly (integration) sequence, numbered in one place.

The dt_drive_train_steps pattern (MHA-DT-00): a step's number is its position
in SEQUENCE, so inserting a step renumbers every later one and every pointer
that cites a step by key follows. The sheet prints the step text
(ha_harmonic_analyzer_assembly_spec); this module holds only the order, so
the joint table (joint_retention) can cite a step without importing the
sheet's prose.

Each subassembly arrives built and checked to its own sheet; these steps are
the joints between them, their locks and consumables, and the settings only
the complete machine can make.
"""

from __future__ import annotations

DRAWING_NUMBER = "MHA-HA-00"

SEQUENCE: tuple[str, ...] = (
    "frame-built",
    "drive-train-built",
    "summing-hung",
    "channel-built",
    # The 20 MHA-CH-VN-51 anchors thread into the summing plate here; MHA-CH-00
    # hooks each spring's top loop and leaves its bottom loop to this step.
    "channel-anchors-set",
    "summing-levelled",
    "paper-drive-built",
    "magnifier-bar-clamped",
    "magnifier-bracket-screwed",
    "lever-wire-fitted",
    "pen-hung",
    "pen-wire-tied",
    # The as-modelled, parked nib (a feeler's gap off the paper); the next
    # step brings it onto the paper for running.
    "nib-set",
    "nib-on-paper",
    "stick-parked",
)

_NUMBER = {key: index for index, key in enumerate(SEQUENCE, start=1)}
if len(_NUMBER) != len(SEQUENCE):
    raise ValueError("ha_harmonic_analyzer_assembly_steps.SEQUENCE repeats a key")


def step_number(key: str) -> int:
    """The printed number of ``key``; a KeyError names an unknown step."""
    return _NUMBER[key]


def step_ref(key: str) -> str:
    """A pointer another sheet prints, e.g. ``MHA-HA-00 STEP 5``."""
    return f"{DRAWING_NUMBER} STEP {step_number(key)}"
