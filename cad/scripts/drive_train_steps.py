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
    "cone-gears-stacked",
    "post-and-tip-block",
    "tip-adjuster-set",
    "crank-mesh-checked",
    "paper-drive-wheel",
    "crank-hub-fitted",
    "crank-handle-fitted",
    # Cylinder bank (BANK_STEPS).
    "cylinder-stack-accepted",
    "cylinder-bank-located",
    # #936 P1 b (user ruling, option A): the rocker bank's north MHA-123 is
    # set on the bank's DRO zero, so it closes BANK_STEPS. Channel assembly
    # MHA-A02 cites it by key (channel_assembly_steps).
    "north-pivot-bracket-set",
    # Pinion rig (rig_steps; pinion_rig_fitup.ASSEMBLY_SEQUENCE in order,
    # with the hang, the cams, the locate, the seats and the base between).
    "arbor-collar-pinned",
    "drum-bonded",
    "handle-bonded",
    "cam-pins-bonded",
    "cluster-hung",
    "straps-pinned-to-torque-shaft",
    "cams-and-lever-fitted",
    "rig-located",
    "rig-set",
    "rig-seats-transferred",
    "cam-collars-set",
    "lever-pin-set",
    "other-base-mounting",
)

_NUMBER = {key: index for index, key in enumerate(SEQUENCE, start=1)}
if len(_NUMBER) != len(SEQUENCE):
    raise ValueError("drive_train_steps.SEQUENCE repeats a key")


def step_number(key: str) -> int:
    """The printed number of ``key``; a KeyError names an unknown step."""
    return _NUMBER[key]


def step_ref(key: str) -> str:
    """A pointer another sheet prints, e.g. ``MHA-A03 STEP 20``."""
    return f"{DRAWING_NUMBER} STEP {step_number(key)}"
