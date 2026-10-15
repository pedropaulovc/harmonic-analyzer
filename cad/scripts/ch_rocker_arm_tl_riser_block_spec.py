r"""Pure-data contract for the rocker arm's riser blocks (MHA-CH-006-TL-10).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). In the
rocker arm's S1-S4 mill setups six blocks lie flat on the PM-30MV table, each
clamped by a T-slot strap or set against the work strap's own clamp; the raw
blank (S2, S3) or the strap shim stacks (S1, S4) stand on them, lifting the
work clear of the table for the through cuts and the drill exits. The work
spans all six at once, so they are faced together as one matched set.

Route (inventory fixtures.rocker-riser-blocks): the approved 1018 CR
3/4 x 1-1/2 in bar, sawn to length, lying flat (the 1-1/2 in across the bar
is the stock width), the 3/4 in faced down to the set height.

One part, two configurations (Main's ruling, 2026-10-14): L036, four off (the
end and outer blocks), and L045, two off (the inner blocks); the length is
the only difference, one ``BlockLength`` global per configuration.

Frame: origin at the block's left end, bottom (the table seat) and back; +X
along the length, +Y up (the height), +Z across the bar (the stock width).
The inventory's fixture frame maps as fixture (x, y, z) = at_mm + model
(x, z, y): a block's ``size_mm`` is (length, width, height).
"""

from __future__ import annotations

from _printed_tolerance import printed_band_mm

INCH = 25.4
BAR_THICK = 0.75 * INCH  # the 3/4 in the blocks are faced down from
BLOCK_WIDTH = round(1.5 * INCH, 6)  # 38.1: the bar's 1-1/2 in, left as stock
BLOCK_HEIGHT = 18.5  # faced to 18.50 as a set
SET_EQUALITY = 0.01  # every block in the set within this of the others

# (configuration, length, quantity): the saved configuration first.
CONFIGS: tuple[tuple[str, float, int], ...] = (("L036", 36.0, 4), ("L045", 45.0, 2))
LENGTHS = {name: length for name, length, _qty in CONFIGS}
QUANTITIES = {name: qty for name, _length, qty in CONFIGS}
DEFAULT_CONFIG = CONFIGS[0][0]  # the part saves on L036; the main views draw it
BLOCK_LENGTH = LENGTHS[DEFAULT_CONFIG]
QUANTITY = sum(QUANTITIES.values())
# The feature bundle and neutral STEP carry one STEP per configuration
# (export_features.step_configurations reads this literal statically).
FEATURE_STEP_CONFIGURATIONS = ("L036", "L045")
if FEATURE_STEP_CONFIGURATIONS != tuple(LENGTHS):
    raise AssertionError("feature STEP configurations drift from CONFIGS")
# The height's set requirement, printed in two callout lines and exported as
# one requirement note: every block of both lengths matches the others.
SET_CALLOUT = ("MATCHED SET OF SIX", f"EQUAL WITHIN {SET_EQUALITY:.2f}")
if QUANTITY != 6:
    raise AssertionError("the set callout counts six blocks")
SET_NOTE = ", ".join(SET_CALLOUT)

_X = printed_band_mm(1)
_XX = printed_band_mm(2)
# The tallest block the .XX title-block band admits still faces clean out of
# the 3/4 in bar.
if BLOCK_HEIGHT + _XX >= BAR_THICK:
    raise AssertionError(
        "riser block height band leaves no face-up stock on the 3/4 bar"
    )

# The validated six-block layout (rocker plan S1-S4; inventory
# fixtures.rocker-riser-blocks, 2026-10-12): left-end x of each block, its
# configuration, and what stands on it. Every block's back face sits at
# y = RISER_Y0 and its top at the fixture's z = 0 (the work underside plane).
RISER_Y0 = -12.4
_ENDS = "raw blank underside (or its strap shim stack)"
_WORK = "work underside or its strap shim stack"
RISERS: tuple[tuple[str, str, float, str], ...] = (
    ("left end riser", "L036", -178.0, f"{_ENDS}, left end"),
    ("left outer riser", "L036", -138.0, _WORK),
    ("left inner riser", "L045", -75.0, _WORK),
    ("right inner riser", "L045", 30.0, _WORK),
    ("right outer riser", "L036", 102.0, _WORK),
    ("right end riser", "L036", 142.0, f"{_ENDS}, right end"),
)
if {name: [r[1] for r in RISERS].count(name) for name in LENGTHS} != QUANTITIES:
    raise AssertionError("riser layout counts drift from the configuration quantities")
# Neighbouring blocks stay apart at their longest printed lengths.
_SPANS = sorted((x, x + LENGTHS[config]) for _name, config, x, _locates in RISERS)
if any(b[0] - a[1] <= 2.0 * _X for a, b in zip(_SPANS, _SPANS[1:])):
    raise AssertionError("riser blocks touch at their printed length limits")

# PM-30MV table 33 x 8.25 in (maker spec), drawing depth 50, centred under
# the bar; the blocks stand on its top.
TABLE_AT_XY = (-419.1, -97.975)
TABLE_SIZE_XY = (838.2, 209.55)
TABLE_DEPTH = 50.0

# The inventory's physical-size provenance, kept verbatim (remeasure: #1413).
_MEASURED = {
    "status": "measured",
    "by": "placeholder (realistic, remeasure: #1413)",
    "date": "2026-10-12",
    "instrument": (
        "digital calipers, height gauge and indicator; physical component sizes/fit only"
    ),
}

PRECHIPS_SOLIDS: list[dict] = [
    {
        "name": "table",
        "supply": "existing",
        "shape": "box",
        "at_mm": [*TABLE_AT_XY, -BLOCK_HEIGHT - TABLE_DEPTH],
        "size_mm": [*TABLE_SIZE_XY, TABLE_DEPTH],
        "note": "PM-30MV table 33 x 8.25 in (maker spec), drawing depth 50; centred under the bar",
        "measured": dict(_MEASURED),
    },
    *(
        {
            "name": name,
            "shape": "box",
            "at_mm": [x, RISER_Y0, -BLOCK_HEIGHT],
            "size_mm": [LENGTHS[config], BLOCK_WIDTH, BLOCK_HEIGHT],
            "label": "riser blocks",
            "locates": locates,
            "note": f"1018 CR 3/4 x 1-1/2, faced to {BLOCK_HEIGHT:.2f}",
            "measured": dict(_MEASURED),
        }
        for name, config, x, locates in RISERS
    ),
]

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"BlockLength", "BlockHeight"},
    "Block": {"BlockWidth"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BlockProfile": {"BlockLength": 1, "BlockHeight": 2},
    "Block": {"BlockWidth": 1},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked riser block dimension needs authored places")

SURFACE_FINISHES = ()
DRAWING_NOTES = "THE WORK RESTS ON ALL SIX BLOCKS AT ONCE."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"


def configuration_number(number: str, configuration: str) -> str:
    """A configuration's qualified Number (subsystem-identities.md: variants
    keep their configuration qualifier, e.g. MHA-DT-003-T006)."""
    if configuration not in LENGTHS:
        raise KeyError(f"unknown riser block configuration {configuration!r}")
    return f"{number}-{configuration}"
