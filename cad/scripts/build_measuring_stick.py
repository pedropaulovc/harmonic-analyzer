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
    anchor_point_to_origin,
    apply_material,
    check,
    ensure_fully_defined,
    measure_check,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_isometric_view,
)

PART_NAME = "measuring-stick"
MATERIAL = "Brass"  # see _common.apply_material docstring

BODY_LENGTH = 200.0  # DIMENSIONS.md ch16: annotated (high)
BODY_WIDTH = 8.0  # DIMENSIONS.md ch16: stick width, annotated (high) — the 8 mm
# callout is the stick WIDTH (bd992c6 re-read), not the division spacing; the
# superseded ~15 mm scaled body-width is retired.
BODY_THICKNESS = 3.0  # DIMENSIONS.md ch16: scaled (low)
DIVISION_SPACING = 8.0  # DIMENSIONS.md ch16: scale span 80 mm / 10 divisions
# (derived, med) — one half of the rocker-arm working length, NOT 10×8 mm.
DIVISION_COUNT = 11  # ticks 0..10 (stated 0-10 scale)
SCALE_START_X = (BODY_LENGTH - 10 * DIVISION_SPACING) / 2.0  # centre the scale

TICK_WIDTH = 0.4
# Graduation-mark lengths are modelling choices: ch16 pins only the 200×8 body and
# the 0–10 / 80 mm scale, not how far the marks reach across the width. Sized to the
# 8 mm body at ~the original 15 mm-body proportions (≈0.40 / 0.50 of width) so they
# stay short edge graduations and the 0.5 tick reads "longer than any other". The old
# 6/7 mm predated the width 15→8 re-read (bd992c6) and spanned 75/87 % of the new
# width — that put the 0.5 tick's bottom corner 1 mm off the edge, which SolidWorks
# rejected when dimensioning that corner to the origin (vertical_distance = 1).
TICK_LENGTH = 3.0  # main ticks, from the top edge down
HALF_TICK_LENGTH = 4.0  # the special 0.5 tick ("longer than any other")
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
    await anchor_point_to_origin(
        adapter,
        f"{bottom}.start",
        x_center - half,
        BODY_WIDTH - length,
        f"{label} corner",
    )
    await ensure_fully_defined(adapter, f"{label} sketch")
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
    set_isometric_view(adapter)

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
    # Pin the (0, 0) corner to the origin. The h/v relations + the two dims fix
    # the bar's shape but not its position; that corner was previously located
    # only by SolidWorks snapping it onto the origin during the (inference-on)
    # line draw -- a crutch removed now that add_line_chain suppresses inference.
    check(
        "body corner -> origin",
        await adapter.add_sketch_constraint(f"{bottom}.start", "origin", "coincident"),
    )
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

    await apply_material(adapter, MATERIAL)

    # Verify the annotated 200 mm length and the untouched front face
    # (the 8 mm tick spacing is driven by the linear pattern's spacing).
    # End faces are edge-on in the active view (point picking is
    # screen-projected) — measure the uncut front-bottom edge instead;
    # the ticks only engrave the back face from the top edge down.
    mid_y = BODY_WIDTH / 2.0
    await measure_check(
        adapter,
        "body length (annotated 200)",
        [{"entity_type": "EDGE", "point": [BODY_LENGTH / 2.0, 0.0, BODY_THICKNESS]}],
        "length",
        BODY_LENGTH,
    )
    await measure_check(
        adapter,
        "front face area (ticks cut the back face only)",
        [
            {
                "entity_type": "FACE",
                "point": [BODY_LENGTH / 2.0, mid_y, BODY_THICKNESS],
            }
        ],
        "area",
        BODY_LENGTH * BODY_WIDTH,
        tol=1.0,
    )

    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
