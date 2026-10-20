"""Drawing-only data of the channel fitter package (MHA-CH-00).

Which marked dimension the sheet shows as a reference, the BOM descriptions
and the settings-dimension callouts the sheets print. Only
draw_ch_channel_assembly (and its tests) import this module; no assembly
builder may (``test_assembly_sheet_isolation`` pins it), so a wording edit
here does not rebuild the channel assembly. No SolidWorks.
"""

from __future__ import annotations

import _mcmaster_91375a106 as arbor_set_screw
import ch_vn_bracket_hold_down_screw_spec as hold_down_screw
import ch_vn_frame_side_screw_spec as frame_side_screw
import ch_vn_fulcrum_set_screw_spec as fulcrum_set_screw
from _inch_fraction import inch_fraction
from ch_channel_assembly_spec import (
    DIMENSION_FEATURE,
    DIMENSION_TOLERANCES,
    KEEPER_FRONT_Z_DIMENSION,
    KEEPER_REAR_Z_DIMENSION,
    KEEPER_X_DIMENSION,
    LUG_SPAN_DIMENSION,
    SPRING_SET_DIMENSION,
    STACK_LENGTH_DIMENSION,
)
from ch_channel_explode_spec import (
    ANCHOR_NUT,
    BANK_SPRING,
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
    WASHER,
)

# The lug span prints as a reference: the pair is set off the top frame.
REFERENCE_DIMENSIONS = frozenset({LUG_SPAN_DIMENSION})
if set(DIMENSION_TOLERANCES) | REFERENCE_DIMENSIONS != set(DIMENSION_FEATURE):
    raise AssertionError("every marked dimension is toleranced or reference")


def _screw(thread: str, length_mm: float, kind: str) -> str:
    """``#4-40 X 1/4 CUP-POINT SET SCREW``: the vendor thread and catalogue
    length."""
    return f"{thread} X {inch_fraction(length_mm, what=kind)} {kind}"


DIMENSION_CALLOUTS = {
    SPRING_SET_DIMENSION: "SPRING-SET BLADE",
    # The accepted stack caps the hubs' summed excess, so each strap stays on
    # its rod's cam plane and under its bar's foot notch (test_channel_axial_
    # budget); r10 machinist review: name what the tight band sets (rule 4).
    STACK_LENGTH_DIMENSION: "STACK, CLOSED UP: STRAP PITCH TO RODS AND BARS",
    LUG_SPAN_DIMENSION: "LUG SPAN",
    # The keeper plan view: what each fit-up band sets (step 10's reason).
    # The faces are named by bank end as the steps and the lever bank view
    # name them (042726e review); the frame's front is the south end, which
    # the plan view's label states (draw_ch_channel_assembly.KEEPER_PLAN).
    KEEPER_X_DIMENSION: "LUG CENTRE",
    KEEPER_FRONT_Z_DIMENSION: "SOUTH LUG INNER FACE",
    KEEPER_REAR_Z_DIMENSION: "NORTH LUG INNER FACE",
}
if set(DIMENSION_CALLOUTS) != set(DIMENSION_FEATURE):
    raise AssertionError("every marked dimension carries a callout")

# Hand-written (components carry no Description property), keyed by family
# stem; the drawing keys the spring row by its built variant stem.
BOM_DESCRIPTIONS = {
    "ch-pivot-shaft": "ROCKER PIVOT SHAFT",
    "ch-fulcrum-shaft": "LEVER FULCRUM SHAFT",
    BRACKET: "ROCKER PIVOT BRACKET",
    BRACKET_SET_SCREW: _screw(
        arbor_set_screw.THREAD, arbor_set_screw.LENGTH, "CUP-POINT SET SCREW"
    ),
    WASHER: "ROCKER BANK THRUST WASHER",
    BANK_SPRING: "WAVE DISC SPRING",
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
    "ch-rod-pivot-pin": "ROD PIVOT PIN",
    BAR_PIN: "BAR PIVOT PIN",
    CHANNEL_SPRING: "EXTENSION SPRING",
    HOOK: "#6-32 EYEBOLT SPRING ANCHOR",
    ANCHOR_NUT: "#6-32 ROUND ANCHOR JAM NUT",
}
