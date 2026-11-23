"""The shop's one feeler gauge: its leaves, the stack a setting takes, its error.

Owner ruling 2026-11-23 (Pedro, #3042, asked whether to buy the metric
Starrett 66MA): "arent all measurements be done in inches by now".  Every set
feeler and shim on MHA-DT-00 is a stack of whole inch leaves of the feeler
gauge the shop owns (cad/config/shop-equipment/gauges.toml
``gauges.feeler-gauges``); the metric set is not bought.

The owned set is Harbor Freight's Pittsburgh SAE/metric feeler gauge, 32
pieces, SKU 63665 (also sold as 32214): 32 blades in 31 sizes, the .010 twice,
each etched with its inch and metric size
(harborfreight.com/saemetric-feeler-gauge-32-piece-63665.html, "Size(s)" and
"Etched SAE and metric size indicators", read 2026-11-23).

Import-free on purpose: the geometry-only layouts (pinion_rig_layout,
cone_stack_end_play, cylinder_bank_layout) size their settings from it, and
none of them may pick up a spec through this module.
"""

from __future__ import annotations

import functools
import itertools

MM_PER_IN = 25.4

# The 31 leaf sizes, in ten-thousandths of an inch (the half-thousandth leaves
# make the thousandth too coarse a unit).  A stack takes each size once: the
# second .010 blade is a spare, never a second leaf of a stack.
_LEAVES_TENTHS = (15, 20, 25, *range(30, 261, 10), 280, 300, 320, 350)
BLADE_COUNT = len(_LEAVES_TENTHS) + 1  # the .010 is in the set twice
LEAVES_IN = tuple(tenths / 10000.0 for tenths in _LEAVES_TENTHS)

# A setting is a whole thousandth of an inch, the place a feeler reading
# prints to (dt_drive_train_assembly_sheet.FEELER_PLACES).
LEAF_STEP = 0.0254
_STEP_TENTHS = 10

# [INFERENCE] The set states no accuracy (its page: "Specifications are
# approximate"), so each leaf is taken as its etched size within half a
# thousandth, about twice what the gauge-stock makers hold on leaves this
# thick.  A stack's error is that per leaf, and it is charged beside the
# setting's own set error wherever that is charged.
LEAF_TOLERANCE = 0.0127  # .0005 in

# No setting takes more leaves than this: a taller stack is a gauge block's
# job, not a feeler's.
MAX_STACK_LEAVES = 4


def thousandths(count: int) -> float:
    """``count`` thousandths of an inch, in mm."""
    return round(count * LEAF_STEP, 4)


def _tenths(setting: float) -> int:
    tenths = round(setting / MM_PER_IN * 10000.0)
    if abs(tenths * MM_PER_IN / 10000.0 - setting) > 1e-9 or tenths % _STEP_TENTHS:
        raise AssertionError(f"{setting} mm is not a whole thousandth of an inch")
    return tenths


@functools.cache
def _stack_tenths(target: int) -> tuple[int, ...]:
    for count in range(1, MAX_STACK_LEAVES + 1):
        stacks = [
            stack
            for stack in itertools.combinations(reversed(_LEAVES_TENTHS), count)
            if sum(stack) == target
        ]
        if stacks:
            # Fewest leaves; of those, the stack whose thinnest leaf is the
            # thickest (the foil leaves crease), then the thickest leaves.
            return max(stacks, key=lambda stack: (stack[-1], stack))
    raise AssertionError(
        f".{target // _STEP_TENTHS:03d} takes more than {MAX_STACK_LEAVES} leaves of the set"
    )


def leaf_stack(setting: float) -> tuple[float, ...]:
    """The leaves that make up ``setting`` (mm), thickest first, each once:
    the fewest the set allows."""
    return tuple(
        round(tenths * MM_PER_IN / 10000.0, 5) for tenths in _stack_tenths(_tenths(setting))
    )


def stack_error(setting: float) -> float:
    """What the leaves of ``setting``'s stack can be off by, together."""
    return len(leaf_stack(setting)) * LEAF_TOLERANCE


def smallest_setting(floor: float, set_error: float) -> float:
    """The thinnest setting that keeps ``floor`` once its own ``set_error``
    and its stack's error are both taken off it."""
    count = max(1, round(floor / LEAF_STEP) - 1)
    while True:
        setting = thousandths(count)
        try:
            error = stack_error(setting)
        except AssertionError:
            if count > sum(_LEAVES_TENTHS[-MAX_STACK_LEAVES:]) // _STEP_TENTHS:
                raise
        else:
            if setting - set_error - error >= floor - 1e-9:
                return setting
        count += 1


def leaf_text(leaf: float) -> str:
    """A leaf by its etched inch size: ``.035``, ``.0025``."""
    tenths = round(leaf / MM_PER_IN * 10000.0)
    places = 3 if tenths % _STEP_TENTHS == 0 else 4
    return f"{tenths / 10000.0:.{places}f}".lstrip("0")


__all__ = [
    "BLADE_COUNT",
    "LEAF_STEP",
    "LEAF_TOLERANCE",
    "LEAVES_IN",
    "MAX_STACK_LEAVES",
    "leaf_stack",
    "leaf_text",
    "smallest_setting",
    "stack_error",
    "thousandths",
]
