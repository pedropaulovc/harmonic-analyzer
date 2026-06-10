r"""Reproduction script: measuring stick (book ch. 16, pp. 34-37).

Ruled brass gauge (Wm. Gaertner & Co.) used to position the amplitude bars:
0-10 scale whose 10 divisions span one half of the rocker arm's working
length. The original is hand-stamped (unevenly); this model uses the nominal
8 mm spacing. The book notes the 0.5 tick is longer than any other -- modelled
as one extra, longer tick between marks 0 and 1. The sliding/locking stop is
a separate component, deferred to the channel subassembly work.

Dimensions: cad/DIMENSIONS.md "Chapter 16" -- 200 mm length and 8 mm spacing
are book-annotated; body width/thickness are low-confidence photo scalings.

Layout: bar along +X with the bottom-left corner on the origin; graduations
engraved 0.5 mm deep into the back face (z=0), tick 0 at x=60 so the 80 mm
scale is centred on the bar.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_measuring_stick.py
"""

from __future__ import annotations

import sys

from _common import (
    add_line_chain,
    check,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
)

PART_NAME = "measuring-stick"

BODY_LENGTH = 200.0  # DIMENSIONS.md ch16: annotated (high)
BODY_WIDTH = 15.0  # DIMENSIONS.md ch16: scaled (low)
BODY_THICKNESS = 3.0  # DIMENSIONS.md ch16: scaled (low)
DIVISION_SPACING = 8.0  # DIMENSIONS.md ch16: annotated (high)
DIVISION_COUNT = 11  # ticks 0..10 (stated 0-10 scale)
SCALE_START_X = (BODY_LENGTH - 10 * DIVISION_SPACING) / 2.0  # centre the scale

TICK_WIDTH = 0.4
TICK_LENGTH = 6.0  # main ticks, from the top edge down
HALF_TICK_LENGTH = 7.0  # the special 0.5 tick ("longer than any other")
TICK_DEPTH = 0.5  # engraving depth
TICK_OVERHANG = 1.0  # sketch reaches past the top edge: a line drawn exactly
# on a model edge picks up an inferred collinear relation that over-defines
# the sketch against the explicit horizontal constraint


async def _cut_tick(adapter, label: str, x_center: float, length: float) -> str:
    """Cut one graduation tick; returns the cut feature name."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check(f"create_sketch {label}", await adapter.create_sketch("Front"))
    half = TICK_WIDTH / 2.0
    top_y = BODY_WIDTH + TICK_OVERHANG
    lines = await add_line_chain(
        adapter,
        [
            (x_center - half, BODY_WIDTH - length),
            (x_center + half, BODY_WIDTH - length),
            (x_center + half, top_y),
            (x_center - half, top_y),
        ],
    )
    bottom, right, top, left = lines
    for ent, relation in (
        (bottom, "horizontal"),
        (top, "horizontal"),
        (right, "vertical"),
        (left, "vertical"),
    ):
        check(f"{label} constraint {relation}", await adapter.add_sketch_constraint(ent, None, relation))
    check(
        f"{label} width dim",
        await adapter.add_sketch_dimension(bottom, None, "linear", TICK_WIDTH),
    )
    check(
        f"{label} length dim",
        await adapter.add_sketch_dimension(
            right, None, "linear", length + TICK_OVERHANG
        ),
    )
    await ensure_fully_defined(adapter, f"{label} sketch", fix_entities=lines)
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    cut = await adapter.create_cut_extrude(ExtrusionParameters(depth=TICK_DEPTH))
    check(f"cut {label}", cut)
    return cut.data.name


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        ExtrusionParameters,
        LinearPatternParameters,
    )

    check("create_part", await adapter.create_part())

    # Body: plain rectangular bar.
    check("create_sketch body", await adapter.create_sketch("Front"))
    body = await add_line_chain(
        adapter,
        [(0.0, 0.0), (BODY_LENGTH, 0.0), (BODY_LENGTH, BODY_WIDTH), (0.0, BODY_WIDTH)],
    )
    bottom, right, top, left = body
    for ent, relation in (
        (bottom, "horizontal"),
        (top, "horizontal"),
        (right, "vertical"),
        (left, "vertical"),
    ):
        check(f"body constraint {relation}", await adapter.add_sketch_constraint(ent, None, relation))
    check("body length dim", await adapter.add_sketch_dimension(bottom, None, "linear", BODY_LENGTH))
    check("body width dim", await adapter.add_sketch_dimension(right, None, "linear", BODY_WIDTH))
    await ensure_fully_defined(adapter, "body sketch")
    check("exit_sketch body", await adapter.exit_sketch())
    check(
        "extrude body",
        await adapter.create_extrusion(ExtrusionParameters(depth=BODY_THICKNESS)),
    )

    # Tick 0 (seed) + linear pattern for ticks 1..10.
    seed_name = await _cut_tick(adapter, "tick 0", SCALE_START_X, TICK_LENGTH)
    check(
        "linear pattern ticks 1..10",
        await adapter.linear_pattern_feature(
            LinearPatternParameters(
                direction_point=[BODY_LENGTH / 2.0, 0.0, 0.0],
                features=[seed_name],
                count=DIVISION_COUNT,
                spacing=DIVISION_SPACING,
            )
        ),
    )

    # The hand-stamped artefact the book calls out: a longer 0.5 tick.
    await _cut_tick(
        adapter, "tick 0.5", SCALE_START_X + DIVISION_SPACING / 2.0, HALF_TICK_LENGTH
    )

    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
