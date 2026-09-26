"""The MHA-A03 drive-train assembly sequence, numbered in one place.

A step's number is its position in SEQUENCE, so inserting a step renumbers
every later one and every pointer that cites a step by key follows.  Part
sheets and checks cite a step with ``step_ref(key)``, never a typed number.
Pure data: no SolidWorks, no config reads.
"""

from __future__ import annotations

DRAWING_NUMBER = "MHA-A03"

SEQUENCE: tuple[str, ...] = (
    # Cone set and crank (CONE_CRANK_STEPS).
    "cone-gears-bonded",
    "post-and-tip-block",
    "tip-adjuster-set",
    "crank-mesh-checked",
    "paper-drive-wheel",
    "crank-hub-fitted",
    "crank-handle-fitted",
    # Cylinder bank (BANK_STEPS).
    "cylinder-stack-accepted",
    "cylinder-bank-located",
    # Pinion rig (RIG_STEPS).
    "cam-pins-seated",
    "crossrod-fitted",
    "arbor-collar-pinned",
    "arbor-through-front-strap",
    "drum-fitted",
    "cluster-hung",
    "straps-pinned-to-torque-shaft",
    "cams-and-lever-fitted",
    "rig-located",
    "rig-tip-gap-set",
    "rig-seats-transferred",
    "other-base-mounting",
)

_NUMBER = {key: index for index, key in enumerate(SEQUENCE, start=1)}
if len(_NUMBER) != len(SEQUENCE):
    raise ValueError("drive_train_steps.SEQUENCE repeats a key")


def step_number(key: str) -> int:
    """The printed number of ``key``; a KeyError names an unknown step."""
    return _NUMBER[key]


def step_ref(key: str) -> str:
    """A pointer another sheet prints, e.g. ``MHA-A03 STEP 19``."""
    return f"{DRAWING_NUMBER} STEP {step_number(key)}"
