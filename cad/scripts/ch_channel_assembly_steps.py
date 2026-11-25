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
# back at the pinning step (RODS_PINNED_KEY). The arms float on the pivot
# shaft, each located along it by its rod (#3114).
CYLINDER_STACK_KEY = "cylinder-stack-accepted"
CYLINDER_STACK_REF = dt_drive_train_steps.step_ref(CYLINDER_STACK_KEY)
RODS_PINNED_KEY = "rod-forks-pinned"
# The pivot shaft's set screws are run onto its flats and left unstaked: the
# shaft comes out to change one channel part (owner ruling 2026-11-20, #2397).
# The fulcrum shaft's end keepers (MHA-CH-07) come finished to their own
# print (#2338: no pair ream); the pair is set on the top frame by DRO with
# the shaft through both (the frame's keeper taps are transferred from the
# foot holes), the shaft is checked to slide through both once they are
# screwed down, and the set screws are driven onto its flats once the shaft
# carries the lever bank, unstaked (#2397, as the pivot shaft's).
KEEPERS_SET_KEY = "fulcrum-keepers-set"
KEEPERS_SCREWED_KEY = "fulcrum-keepers-screwed"
FULCRUM_SET_SCREWS_DRIVEN_KEY = "fulcrum-set-screws-driven"
# The lever bank: each amplitude bar is pinned to its lever at the bench (the
# pin is pressed into the bar's cheeks and runs in the lever), then the levers
# go onto the fulcrum shaft between the set keepers in channel order, each
# bar's foot notch dropped over its rocker's arm, before the keeper set
# screws are driven onto the shaft's flats. The channel springs are hooked
# last; their anchors are threaded and set at MHA-HA-00.
BARS_PINNED_KEY = "bars-pinned"
LEVER_BANK_THREADED_KEY = "lever-bank-threaded"
SPRINGS_HOOKED_KEY = "springs-hooked"
# The anchors are threaded, locked and set at MHA-HA-00 (key
# "channel-anchors-set"). The pointer stays literal so the part sheets that
# import this module do not take MHA-HA-00's order as a dependency;
# test_ha_harmonic_analyzer_assembly_drawing proves it against that registry.
HA_ANCHORS_SET_REF = "MHA-HA-00 STEP 5"

# The south bracket is set by edge finder and DRO off the north one to the
# ears' inner-face span while the shaft runs bare through both ears (with the
# arms on it each inner face is only .05 from its end hub, out of the edge
# finder's reach). It stays only clamped while the shaft is drawn back, the
# arms are threaded on, each end arm is pushed toward its ear as far as its
# rod lets it (a floating arm would slide away from the leaf) and the end
# hubs are checked clear of the ears (machinist review, PR #1605: a failed
# check re-sets a bracket that can still move). Each end has its own remedy
# block, one action a step (rule 22): the left bracket, set and screwed at
# MHA-DT-00, is reset per its own sub-steps; both blocks return to the bare
# shaft. The foot hole is transferred and the bracket screwed down only once
# that check has passed. The arms are checked to slide freely with their
# rods once the shaft is held.
LEFT_HUB_REMEDY: tuple[str, ...] = (
    "left-hub-shaft-drawn-back",
    "left-hub-clamp-eased",
    "left-hub-hold-down-loosened",
    "left-hub-bracket-reset",
    "left-hub-hold-down-tightened",
    "left-hub-bracket-rechecked",
    "left-hub-return",
)
RIGHT_HUB_REMEDY: tuple[str, ...] = (
    "right-hub-shaft-drawn-back",
    "right-hub-clamp-eased",
    "right-hub-return",
)
# A pin that slid in by hand is bonded with LOCTITE 641 instead of its rod or
# bar being replaced (owner ruling 2026-11-24, fit audit question 3), per the
# sheet's pin bond note; once cured the pin is checked held and its arm or
# bar free, one check a step as the main flow's two are (rule 22), and a
# failed bond goes back to the bond.
ROD_PIN_REMEDY: tuple[str, ...] = (
    "rod-pin-bonded",
    "rod-pin-bond-held",
    "rod-pin-bond-swings",
    "rod-pin-return",
)
BAR_PIN_REMEDY: tuple[str, ...] = (
    "bar-pin-bonded",
    "bar-pin-bond-held",
    "bar-pin-bond-swings",
    "bar-pin-return",
)
# Each arm's strap is accepted where it works, in its rod's fork: once the
# rocker bank is on the shaft with the rods in their cams, and before the
# lever bank's bars sit on the arms, the strap must shake sideways between
# the tines (owner ruling 2026-11-20, #2343: the fork clearance is the
# functional check of the strap's position); a strap that binds is set by
# hand and checked again (rule 22: the remedy is its own steps). The rocker
# bank's two columns are full, so the check opens the lever bank's.
STRAP_SHAKE_REMEDY: tuple[str, ...] = (
    "strap-set-by-hand",
    "strap-set-return",
)
ROCKER_SEQUENCE: tuple[str, ...] = (
    RODS_PINNED_KEY,
    "rod-pins-dressed",
    "rod-pins-held",
    "rod-arms-swing",
    *ROD_PIN_REMEDY,
    "north-bracket-held",
    "south-bracket-stood",
    "bare-shaft-through-ears",
    "south-bracket-span-set",
    "south-bracket-clamped",
    "shaft-drawn-back",
    "arms-swung-up",
    "rocker-hubs-threaded",
    "end-arms-pushed-to-ears",
    "end-hubs-clear",
    *LEFT_HUB_REMEDY,
    *RIGHT_HUB_REMEDY,
    "south-foot-transferred",
    "south-foot-tapped",
    "south-bracket-screwed",
    "south-bracket-unclamped",
    "south-bracket-held",
    "shaft-set",
    "set-screws-driven",
    "pivot-shaft-held",
    "arms-follow-rods",
)
LEVER_SEQUENCE: tuple[str, ...] = (
    "straps-shake-in-forks",
    *STRAP_SHAKE_REMEDY,
    "keepers-on-frame",
    "fulcrum-shaft-through-keepers",
    KEEPERS_SET_KEY,
    "keeper-faces-set",
    "rear-keeper-to-stack",
    "keepers-clamped-on-frame",
    "keeper-feet-transferred",
    "keeper-feet-tapped",
    KEEPERS_SCREWED_KEY,
    "keepers-unclamped",
    "keepers-held",
    "keeper-bores-checked",
    "fulcrum-shaft-withdrawn",
    "bars-straight",
    "bar-straightened",
    "bar-straightened-return",
    "bar-notches-set",
    BARS_PINNED_KEY,
    "bar-pins-dressed",
    "bar-pins-held",
    "bars-swing",
    *BAR_PIN_REMEDY,
    LEVER_BANK_THREADED_KEY,
    "bar-feet-seated",
    "bars-gapped",
    "levers-swing",
    "lever-bank-slides",
    "fulcrum-flats-aligned",
    FULCRUM_SET_SCREWS_DRIVEN_KEY,
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
