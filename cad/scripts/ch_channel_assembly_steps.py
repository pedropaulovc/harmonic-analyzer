"""The MHA-CH-00 channel-assembly fit-up sequence, numbered in one place.

The drive_train_steps pattern (MHA-DT-00): a step's number is its position in
SEQUENCE, so inserting a step renumbers every later one and every pointer that
cites a step by key follows. The sheet prints the step text; this module holds
only the order. Pure data: no SolidWorks, no config reads.

Each step does one thing (drawing-guidelines.md rule 22): a check and its
remedy are their own steps, and every fixed joint the package makes is
accepted at the bench right after it is made (rule 23).
"""

from __future__ import annotations

import dt_drive_train_steps

DRAWING_NUMBER = "MHA-CH-00"
# The north pivot bracket is set by DRO in the drive-train fit-up, off the
# located drum bank's datum (user ruling on #936 P1 b, option A), so this sheet
# points there by key: MHA-DT-00 prints the same key's number as the step head,
# so the pointer follows any renumbering of MHA-DT-00.
NORTH_BRACKET_SET_KEY = "north-pivot-bracket-set"
NORTH_BRACKET_SET_REF = dt_drive_train_steps.step_ref(NORTH_BRACKET_SET_KEY)
# Each rod's ring is captured in its closed cam slot as the cylinder stack goes
# together (MHA-DT-00 BANK_STEPS), and the rod's fork is pinned to its arm with
# a pin pressed at the bench, so the rod + arm pair must be pinned BEFORE that
# step: the pinning step points there by key, and that drive-train step points
# back at the pinning step (RODS_PINNED_KEY). The hub stack is proved on the
# shaft first, while the arms are still loose.
CYLINDER_STACK_KEY = "cylinder-stack-accepted"
CYLINDER_STACK_REF = dt_drive_train_steps.step_ref(CYLINDER_STACK_KEY)
RODS_PINNED_KEY = "rod-forks-pinned"
# The pivot shaft's set screws are run onto its flats, then staked.
PIVOT_SET_SCREWS_STAKED_KEY = "pivot-set-screws-staked"
# The fulcrum shaft's end keepers (MHA-CH-07) are reamed as a pair at the
# bench, so their bores share one axis whatever their printed bore heights;
# the pair is then set on the top frame by DRO with the shaft through both
# (the frame's keeper taps are transferred from the foot holes), and the set
# screws are staked once the shaft carries the lever bank.
KEEPERS_PAIR_REAMED_KEY = "fulcrum-keepers-pair-reamed"
KEEPERS_SET_KEY = "fulcrum-keepers-set"
KEEPERS_SCREWED_KEY = "fulcrum-keepers-screwed"
FULCRUM_SET_SCREWS_DRIVEN_KEY = "fulcrum-set-screws-driven"
SET_SCREWS_STAKED_KEY = "fulcrum-set-screws-staked"
# The lever bank: each amplitude bar is pinned to its lever at the bench (the
# pin is pressed into the bar's cheeks and runs in the lever), then the levers
# go onto the fulcrum shaft between the set keepers in channel order, each
# bar's foot notch dropped over its rocker's arm, before the keeper set
# screws are staked onto the shaft's flats. The channel springs are hooked
# last; their anchors are threaded and set at MHA-HA-00.
BARS_PINNED_KEY = "bars-pinned"
LEVER_BANK_THREADED_KEY = "lever-bank-threaded"
SPRINGS_HOOKED_KEY = "springs-hooked"
# The anchors are threaded, locked and set at MHA-HA-00 (key
# "channel-anchors-set"). The pointer stays literal so the part sheets that
# import this module do not take MHA-HA-00's order as a dependency;
# test_ha_harmonic_analyzer_assembly_drawing proves it against that registry.
HA_ANCHORS_SET_REF = "MHA-HA-00 STEP 5"

# The spring-back acceptance runs while the south bracket is still only
# clamped (machinist review, PR #1605), so its remedy re-sets a bracket that
# can still move; the foot hole is transferred and the bracket screwed down
# only once that check has passed.
# The south bracket is set by DRO off an indicator zero taken on its foot end
# with its ear on the south washer, before the wave spring goes on (#2337: the
# spring covers the washer face, so no feeler leaf can bear on it beside the
# spring); the bracket comes off the shaft for the spring, goes back on under
# a light clamp and is tapped to that zero at the DRO's spring-set offset.
ROCKER_SEQUENCE: tuple[str, ...] = (
    "rocker-stack-accepted",
    "rocker-stack-measured",
    "rocker-stack-refaced",
    "rockers-kept-in-order",
    RODS_PINNED_KEY,
    "rod-pins-dressed",
    "rod-pins-held",
    "rod-arms-swing",
    "rod-pin-remade",
    "north-bracket-held",
    "arms-swung-up",
    "north-ear-datum",
    "rocker-hubs-threaded",
    "south-washer-fitted",
    "south-bracket-on-washer",
    "south-bracket-zeroed",
    "south-bracket-slid-off",
    "bank-spring-checked",
    "bank-spring-replaced",
    "bank-spring-fitted",
    "south-bracket-refitted",
    "south-bracket-spring-set",
    "south-bracket-clamped",
    "spring-back-checked",
    "south-bracket-reset",
    "south-foot-transferred",
    "south-foot-tapped",
    "south-bracket-screwed",
    "south-bracket-unclamped",
    "south-bracket-held",
    "shaft-set",
    "set-screws-driven",
    PIVOT_SET_SCREWS_STAKED_KEY,
    "pivot-shaft-held",
)
LEVER_SEQUENCE: tuple[str, ...] = (
    "keepers-clamped",
    KEEPERS_PAIR_REAMED_KEY,
    "keeper-bores-checked",
    "keeper-tops-finished",
    "keeper-taps-made",
    "keepers-on-frame",
    KEEPERS_SET_KEY,
    "keeper-faces-set",
    "keepers-clamped-on-frame",
    "keeper-feet-transferred",
    "keeper-feet-tapped",
    KEEPERS_SCREWED_KEY,
    "keepers-unclamped",
    "keepers-held",
    "bars-straight",
    "bar-notches-set",
    BARS_PINNED_KEY,
    "bar-pins-dressed",
    "bar-pins-held",
    "bars-swing",
    "bar-pin-remade",
    "fulcrum-shaft-withdrawn",
    LEVER_BANK_THREADED_KEY,
    "bar-feet-seated",
    "bars-gapped",
    "levers-swing",
    "lever-bank-slides",
    "fulcrum-flats-aligned",
    FULCRUM_SET_SCREWS_DRIVEN_KEY,
    SET_SCREWS_STAKED_KEY,
    "fulcrum-shaft-held",
    SPRINGS_HOOKED_KEY,
    "spring-bottom-loops-left",
)
SEQUENCE: tuple[str, ...] = ROCKER_SEQUENCE + LEVER_SEQUENCE

_NUMBER = {key: index for index, key in enumerate(SEQUENCE, start=1)}
if len(_NUMBER) != len(SEQUENCE):
    raise ValueError("ch_channel_assembly_steps.SEQUENCE repeats a key")


def step_number(key: str) -> int:
    """The printed number of ``key``; a KeyError names an unknown step."""
    return _NUMBER[key]


def step_ref(key: str) -> str:
    """A pointer another sheet prints, e.g. ``MHA-CH-00 STEP 4``."""
    return f"{DRAWING_NUMBER} STEP {step_number(key)}"


RODS_PINNED_REF = step_ref(RODS_PINNED_KEY)
