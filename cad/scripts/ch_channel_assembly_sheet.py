"""Drawing-only data of the channel fitter package (MHA-CH-00).

Which marked dimension the sheet shows as a reference, the BOM descriptions,
the settings-dimension callouts and the sheet 6 setting table the sheets
print. Only draw_ch_channel_assembly (and its tests) import this module; no
assembly builder may (``test_assembly_sheet_isolation`` pins it), so a
wording edit here does not rebuild the channel assembly. No SolidWorks.
"""

from __future__ import annotations

import math

import _config
import sh_vn_arbor_set_screw_spec as arbor_set_screw
import ch_vn_bracket_hold_down_screw_spec as hold_down_screw
import ch_vn_frame_side_screw_spec as frame_side_screw
import ch_vn_fulcrum_set_screw_spec as fulcrum_set_screw
from _inch_fraction import inch_fraction
from _title_block_units import LENGTH_UNITS, render_number
import ch_channel_assembly_steps as steps
from ch_channel_assembly_spec import (
    BAR_BOW_MAX_MM,
    BAR_GAP,
    DIMENSION_FEATURE,
    DIMENSION_TOLERANCES,
    EAR_SPAN_DIMENSION,
    KEEPER_FRONT_Z_DIMENSION,
    KEEPER_REAR_Z_DIMENSION,
    KEEPER_X_DIMENSION,
    LUG_SPAN_DIMENSION,
    TIP_PROUD_DIMENSION,
    TOLERANCE_PRECISION,
    UNIT,
)
from ch_fulcrum_keeper_spec import KEEPER_TAP_SPEC
from fr_top_frame_spec import KEEPER_TAP_WALL_ACCEPTED_MM
from ch_keeper_fitup import END_PLAY_MM, REAR_KEEPER_LEAF_MM
from rocker_bank_layout import EAR_INNER_SPAN, END_CLEARANCE_MIN, RUNNING_FLOOR
from ch_channel_explode_spec import (
    ARM,
    BAR,
    BAR_PIN,
    BRACKET,
    BRACKET_HOLD_DOWN,
    BRACKET_SET_SCREW,
    CHANNEL_SPRING,
    HOOK,
    KEEPER,
    KEEPER_FOOT_SCREW,
    KEEPER_SET_SCREW,
    ROD,
    ROD_PIN,
)

# The lug span prints as a reference: the pair is set off the top frame. The
# rear lug inner face too: the rear keeper is set to the lever stack (C10,
# ch_channel_assembly_spec REAR_KEEPER_LEAF_MM).
REFERENCE_DIMENSIONS = frozenset({LUG_SPAN_DIMENSION, KEEPER_REAR_Z_DIMENSION})
if set(DIMENSION_TOLERANCES) | REFERENCE_DIMENSIONS != set(DIMENSION_FEATURE):
    raise AssertionError("every marked dimension is toleranced or reference")
# The ear span's upper limit as view D prints it, its nominal plus its band's
# upper deviation: the right-hub remedy re-sets the right ear outward to it.
EAR_SPAN_UPPER_TEXT = render_number(
    (EAR_INNER_SPAN + DIMENSION_TOLERANCES[EAR_SPAN_DIMENSION][1]) / LENGTH_UNITS[UNIT],
    UNIT,
    TOLERANCE_PRECISION[EAR_SPAN_DIMENSION],
)


def _screw(thread: str, length_mm: float, kind: str) -> str:
    """``#4-40 X 1/4 CUP-POINT SET SCREW``: the vendor thread and catalogue
    length."""
    return f"{thread} X {inch_fraction(length_mm, what=kind)} {kind}"


# A callout's ``{arm}`` is the rocker arm's BOM item, which the drawing fills
# in from its BOM (as it numbers the setting table's parts).
DIMENSION_CALLOUTS = {
    # Set by DRO off the left bracket's ear (the right-bracket span step):
    # the ears' inner faces, between which the arms float, each located by
    # its rod (#3114). What the band protects (rule 4): each end arm's hub,
    # following its rod, stays clear of its ear (the end-hubs-clear check).
    EAR_SPAN_DIMENSION: "EAR SPAN, INNER FACES: END {arm} HUBS CLEAR",
    # View D's left tip off the left ear's outer face (the shaft-set step,
    # caliper depth rod); R5 machinist review, rule 22: the setting prints on
    # the view, not in the step.
    TIP_PROUD_DIMENSION: "TIP PROUD",
    LUG_SPAN_DIMENSION: "LUG SPAN",
    # View F: what each fit-up band sets. Both Z settings run to a lug inner
    # face; the view's own projection shows which.
    KEEPER_X_DIMENSION: "LUG CENTRE",
    KEEPER_FRONT_Z_DIMENSION: "LUG INNER FACE",
    KEEPER_REAR_Z_DIMENSION: "LUG INNER FACE",
}
if set(DIMENSION_CALLOUTS) != set(DIMENSION_FEATURE):
    raise AssertionError("every marked dimension carries a callout")

# Rule 20: the lug centre's band holds the wall of the keeper's transferred
# foot tap in the MHA-FR-02 rail web at the accepted .076, under rule 17's
# .080 target (necessity N-01; fr_top_frame_spec KEEPER_TAP_WALL_ACCEPTED_MM,
# the .0767 floored, as MHA-FR-02 sheet 7 prints it). The shortfall is this
# package's minor exception CH-00-rail-web-tap-wall (ch-channel.yaml), the
# same wall as MHA-FR-02 RV-14. Stated once, as a plain fact, under the lug
# centre's value (machinist review of farm run 20261125T172832344Z, r1 and
# r2).
KEEPER_TAP_WALL_PLACES = 3
KEEPER_TAP_WALL_TEXT = (
    f"RAIL WEB {KEEPER_TAP_SPEC.size.lstrip('#')} TAP WALL "
    f"{render_number(KEEPER_TAP_WALL_ACCEPTED_MM / LENGTH_UNITS[UNIT], UNIT, KEEPER_TAP_WALL_PLACES)}"
    " MIN"
)
DIMENSION_BELOW_CALLOUTS = {KEEPER_X_DIMENSION: KEEPER_TAP_WALL_TEXT}
if not set(DIMENSION_BELOW_CALLOUTS) <= set(DIMENSION_FEATURE):
    raise AssertionError("a below-callout names no marked dimension")

# --- sheet 6: the setting table ------------------------------------------------
# R5 machinist review (rule 22): the feeler acceptances printed only in their
# steps. None is one model dimension (a leaf that must pass between each end
# rocker hub and its ear, a leaf that must not enter under a bar on the
# plate, a leaf that must pass between bars, a leaf the pushed-together
# levers must leave room for at the other lug), so each is a row of a native
# general table (draw_dt_drive_train_assembly's SETTING TABLE columns) the
# steps cite by row; every value is built from the spec. The drawing places
# the table under view G's label and numbers each row's part from its BOM.
SETTING_TABLE_SHEET_NUMBER = 6
SETTING_TABLE_TITLE = "SETTING TABLE"
SETTING_TABLE_HEADER = (
    "ROW",
    "STEP",
    "SETTING",
    "MEASURE FIRST",
    "SET TO / ACCEPT",
    "CHECK WITH",
)
# A feeler leaf prints .XXX, the .001 grid a feeler set is sold in.
FEELER_LEAF_PLACES = 3


def _inch(mm: float) -> str:
    return render_number(mm / LENGTH_UNITS[UNIT], UNIT, FEELER_LEAF_PLACES)


# The lever bank is never set to its stations: each lever floats between its
# neighbours and the lugs, and its bar leans to the arm below it
# (test_channel_axial_budget). The rear keeper is set to the bare stack over
# a leaf (C10, ch_keeper_fitup), so the bank's end play is that leaf; the
# lever-bank-slides check gauges it on a feeler leaf: the leaf less the
# push's settle, rounded down to .01 in, so a bank set to its leaf always
# passes (moved here from the MHA-CH-02 hub callout, FoChFab2 round 1).
_END_PLAY_MIN_IN = END_PLAY_MM[0] / LENGTH_UNITS[UNIT]
END_PLAY_LEAF_MM = math.floor(_END_PLAY_MIN_IN * 100.0) / 100.0 * LENGTH_UNITS[UNIT]
if END_PLAY_LEAF_MM <= 0.0:
    raise AssertionError(
        "the lever bank must slide between the lugs, but the rear keeper's "
        "leaf leaves no gaugeable play"
    )
# #3114: the rocker arms float, each located by its rod, so the ears' span is
# the bank's only setting; each end hub is accepted clear of its ear on a
# feeler leaf, the least worst-case air (rocker_bank_layout.END_CLEARANCE_MIN:
# the end arm following its rod at the extreme of every band) floored to
# .001, never under the running floor: a bank inside its bands always passes.
END_HUB_LEAF_MM = (
    math.floor(round(min(END_CLEARANCE_MIN) / LENGTH_UNITS[UNIT] * 1000.0, 9))
    / 1000.0
    * LENGTH_UNITS[UNIT]
)
if END_HUB_LEAF_MM < RUNNING_FLOOR:
    raise AssertionError(
        "an end rocker hub may close on its ear below the running floor"
    )
# #2341: each bar's bow is accepted at the surface plate before it is pinned
# (no leaf of the allowed bow enters under either side face); the bank is
# then accepted on the bars' least running gap, at the worst case of every
# band with each bar at that bow, floored to .001 (the assembly spec's
# bar-gap budget): a bank inside its bands always passes.
SETTINGS = (
    # (step key, the part the setting names (its BOM item prefixes the
    # setting) or None, setting, set to / accept, check with)
    (
        "end-hubs-clear",
        ARM,
        "HUB TO EAR",
        f"{_inch(END_HUB_LEAF_MM)} MIN",
        "FEELER LEAF",
    ),
    ("bars-straight", BAR, "BAR BOW", f"{_inch(BAR_BOW_MAX_MM)} MAX", "FEELER LEAF"),
    ("bars-gapped", BAR, "BAR GAP", f"{_inch(BAR_GAP['leaf'])} MIN", "FEELER LEAF"),
    (
        "lever-bank-slides",
        None,
        "LEVER END PLAY",
        f"{_inch(END_PLAY_LEAF_MM)} MIN",
        "FEELER LEAF",
    ),
    (
        "rear-keeper-to-stack",
        None,
        "LEFT LUG TO LAST HUB",
        _inch(REAR_KEEPER_LEAF_MM),
        "FEELER LEAF",
    ),
)
_SETTING_ROW = {key: row for row, (key, *_rest) in enumerate(SETTINGS, start=1)}
if set(_SETTING_ROW) - set(steps.SEQUENCE):
    raise AssertionError("a setting table row names no fit-up step")


def setting_row(key: str) -> str:
    """How a step cites its setting table row."""
    return f"SETTING TABLE ROW {_SETTING_ROW[key]} (SHEET {SETTING_TABLE_SHEET_NUMBER})"


# Hand-written (components carry no Description property), keyed by family
# stem (each pivot pin member by stem--member, its configured BOM key). The
# spring's installed configurations stamp their grouped BOM description, which
# wins over the written cell, so its text is the registry row's.
BOM_DESCRIPTIONS = {
    "ch-pivot-shaft": "ROCKER PIVOT SHAFT",
    "ch-fulcrum-shaft": "LEVER FULCRUM SHAFT",
    BRACKET: "ROCKER PIVOT BRACKET",
    BRACKET_SET_SCREW: _screw(
        arbor_set_screw.THREAD, arbor_set_screw.LENGTH, "CUP-POINT SET SCREW"
    ),
    BRACKET_HOLD_DOWN: _screw(
        hold_down_screw.THREAD, hold_down_screw.SHANK_LEN, "FILLISTER HEAD SCREW"
    ),
    KEEPER: "FULCRUM SHAFT KEEPER",
    KEEPER_FOOT_SCREW: _screw(
        frame_side_screw.THREAD, frame_side_screw.SHANK_LEN, "FILLISTER HEAD SCREW"
    ),
    KEEPER_SET_SCREW: _screw(
        fulcrum_set_screw.THREAD, fulcrum_set_screw.LENGTH, "CUP-POINT SET SCREW"
    ),
    "ch-rocker-arm": "ROCKER ARM",
    ROD: "CONNECTING ROD",
    BAR: "AMPLITUDE BAR",
    "ch-channel-lever": "CHANNEL LEVER",
    ROD_PIN: "ROD PIVOT PIN",
    BAR_PIN: "BAR PIVOT PIN",
    CHANNEL_SPRING: str(_config.parts("ch-vn-channel-spring-installed")["description"]),
    HOOK: "#6-32 EYEBOLT SPRING ANCHOR",
}
