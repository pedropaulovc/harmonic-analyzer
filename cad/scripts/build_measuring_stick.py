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

    uv run python cad\scripts\build_measuring_stick.py
"""

from __future__ import annotations

import sys

from _common import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    check,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    measure_check,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from measuring_stick_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    FRONT_VIEW_NOTE,
    ISOMETRIC_VIEW_NOTE,
)

PART_NAME = "measuring-stick"
MATERIAL = "Brass"  # see _common.apply_material docstring

BODY_LENGTH = 200.0  # DIMENSIONS.md ch16: annotated (high)
BODY_WIDTH = 8.0  # DIMENSIONS.md ch16: stick width, annotated (high) — the 8 mm
# callout is the stick WIDTH (bd992c6 re-read), not the division spacing; the
# superseded ~15 mm scaled body-width is retired.
BODY_THICKNESS = 3.0  # DIMENSIONS.md ch16: scaled (low)
DIVISION_SPACING = 14.2  # ch16 page001_img02 (200 mm bar at 5.65 px/mm): the
# 0 and 10 numerals sit 805 px = 142 mm apart -- one half of the rocker arm's
# 292 mm working arc, as the text says (2026-09 re-derive; the old 80 mm was a
# misread of the 8 mm width callout).
DIVISION_COUNT = 11  # full ticks 0..10 (stated 0-10 scale)
MINOR_PER_DIVISION = 10  # tenths: 9 short ticks between full ticks (page001_img03)
MINOR_SPACING = DIVISION_SPACING / MINOR_PER_DIVISION  # 1.42
SCALE_END_MARGIN = 0.5  # the 10 tick lands just short of the far end (img02)
SCALE_START_X = BODY_LENGTH - 10 * DIVISION_SPACING - SCALE_END_MARGIN  # 57.5

TICK_WIDTH = 0.4
# Graduation-mark lengths are modelling choices: ch16 pins only the 200×8 body and
# the 0–10 / 80 mm scale, not how far the marks reach across the width. Sized to the
# 8 mm body at ~the original 15 mm-body proportions (≈0.40 / 0.50 of width) so they
# stay short edge graduations and the 0.5 tick reads "longer than any other". The old
# 6/7 mm predated the width 15→8 re-read (bd992c6) and spanned 75/87 % of the new
# width — that put the 0.5 tick's bottom corner 1 mm off the edge, which SolidWorks
# rejected when dimensioning that corner to the origin (vertical_distance = 1).
TICK_LENGTH = 3.0  # main ticks, from the top edge down
MINOR_TICK_LENGTH = 1.8  # the tenths (~0.6 of a full tick, page001_img03)
HALF_TICK_LENGTH = 4.0  # the special 0.5 tick ("longer than any other")
TICK_DEPTH = 0.5  # engraving depth
TICK_OVERHANG = 1.0  # sketch reaches past the top edge: a line drawn exactly
# on a model edge picks up an inferred collinear relation that over-defines
# the sketch against the explicit horizontal constraint


async def _cut_tick(
    adapter,
    label: str,
    stem: str,
    x_center: float,
    length: float,
    *,
    drive_jobs: list[tuple[str, str]],
    drive_xcenter: str,
    drive_length: str,
) -> str:
    """Cut one graduation tick; returns the cut feature name.

    Self-naming: ``stem`` makes the sketch/feature/dim names unique per tick
    (the equation manager keys dims by ``leaf@feature``). The four sketch dims
    emit in creation order -- width, length, then the bottom-left corner anchor
    (x then z, both non-zero) -- recorded into a per-tick :class:`SketchDims` and
    driven via the deferred ``drive_jobs`` batch. ``drive_xcenter`` is the
    equation for the tick's centre x; the corner-X dim is an UNSIGNED distance,
    so it drives to that centre minus half the tick width.
    """
    from solidworks_mcp.adapters.base import ExtrusionParameters

    dims = SketchDims()
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
    dims.record(f"{stem}Width", '"TickWidth"')
    check(
        f"{label} length dim",
        await adapter.add_sketch_dimension(
            right, None, "linear", length + TICK_OVERHANG
        ),
    )
    dims.record(f"{stem}Length", f'{drive_length} + "TickOverhang"')
    # Corner anchor at (x_center - half, BODY_WIDTH - length): both non-zero, so
    # two dims (x then z). Both are unsigned distances from the origin and both
    # land positive here, so the drives evaluate positive directly.
    await anchor_point_to_origin(
        adapter,
        f"{bottom}.start",
        x_center - half,
        BODY_WIDTH - length,
        f"{label} corner",
    )
    dims.record(f"{stem}CornerX", f'{drive_xcenter} - "TickWidth" / 2')
    dims.record(f"{stem}CornerZ", f'"BodyWidth" - ({drive_length})')
    await ensure_fully_defined(adapter, f"{label} sketch")
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    name_last_feature(adapter, f"{stem}Profile")
    drive_jobs += dims.apply(adapter, f"{stem}Profile")
    cut = await adapter.create_cut_extrude(ExtrusionParameters(depth=TICK_DEPTH))
    check(f"cut {label}", cut)
    return name_last_feature(adapter, f"{stem}Cut")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        ExtrusionParameters,
        LinearPatternParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this is
    # an INCH document and the equation manager reads BARE numbers in document
    # units (an unsuffixed 200 = 200 in, a 25.4x blow-up). ScaleStartX is a
    # DERIVED global (centres the 80 mm scale on the bar), referencing the others
    # as an equation string. DivisionSpacing drives the linear-pattern spacing, a
    # FEATURE parameter -- a knob with nothing in the deferred sketch-dim batch,
    # like an extrude depth (matches the exemplars).
    await set_global(adapter, "BodyLength", f"{BODY_LENGTH}mm")
    await set_global(adapter, "BodyWidth", f"{BODY_WIDTH}mm")
    await set_global(adapter, "BodyThickness", f"{BODY_THICKNESS}mm")
    await set_global(adapter, "DivisionSpacing", f"{DIVISION_SPACING}mm")
    await set_global(adapter, "ScaleEndMargin", f"{SCALE_END_MARGIN}mm")
    await set_global(adapter, "TickWidth", f"{TICK_WIDTH}mm")
    await set_global(adapter, "TickLength", f"{TICK_LENGTH}mm")
    await set_global(adapter, "MinorTickLength", f"{MINOR_TICK_LENGTH}mm")
    await set_global(adapter, "HalfTickLength", f"{HALF_TICK_LENGTH}mm")
    await set_global(adapter, "TickOverhang", f"{TICK_OVERHANG}mm")
    await set_global(
        adapter,
        "ScaleStartX",
        '"BodyLength" - 10 * "DivisionSpacing" - "ScaleEndMargin"',
    )

    drive_jobs: list[tuple[str, str]] = []

    # Body: plain rectangular bar. Two display dims emit in creation order --
    # length then width -- recorded as they are added; the (0, 0) corner anchors
    # by a coincident relation (no dim).
    body_dims = SketchDims()
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
    body_dims.record("BodyLength", '"BodyLength"')
    check("body width dim", await adapter.add_sketch_dimension(right, None, "linear", BODY_WIDTH))
    body_dims.record("BodyWidth", '"BodyWidth"')
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
    name_last_feature(adapter, "BodyProfile")
    drive_jobs += body_dims.apply(adapter, "BodyProfile")
    check(
        "extrude body",
        await adapter.create_extrusion(ExtrusionParameters(depth=BODY_THICKNESS)),
    )
    name_last_feature(adapter, "Body")
    # Drive the body's extrude depth from BodyThickness too (D1 is the blind-
    # extrude depth dim) so the thickness knob is live, not inert. As-built ->
    # neutral.
    drive_jobs.append(("D1@Body", '"BodyThickness"'))

    # Tick 0 (seed) + linear pattern for ticks 1..10. The seed cut is RENAMED
    # ("Tick0Cut"), so the pattern must seed off the NEW name -- a captured
    # auto-name would go stale the moment name_last_feature ran (M: renamed-feature
    # references). _cut_tick returns the assigned name for exactly this reason.
    seed_name = await _cut_tick(
        adapter, "tick 0", "Tick0", SCALE_START_X, TICK_LENGTH,
        drive_jobs=drive_jobs,
        drive_xcenter='"ScaleStartX"',
        drive_length='"TickLength"',
    )
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
    name_last_feature(adapter, "TickPattern")
    # Drive the pattern's spacing from DivisionSpacing too. The seed (Tick0) and
    # half-tick are driven from ScaleStartX (DivisionSpacing-derived), so the
    # pattern's own spacing dim MUST track DivisionSpacing or ticks 1..10 keep
    # the old 8 mm pitch and the ruled scale corrupts on a GUI edit (the Codex
    # P2). The spacing is D3 (verified by dump_dimensions: D1 is the pattern's
    # ~11000 mm direction-reference length, NOT the pitch); D3 == as-built 8 mm,
    # so it stays neutral.
    drive_jobs.append(("D3@TickPattern", '"DivisionSpacing"'))

    # Tenths: nine short ticks between the 0 and 1 full ticks, cut one by one
    # (each drives off ScaleStartX + k * DivisionSpacing / 10), then the nine
    # patterned as a group across the other nine divisions. (A pattern of the
    # minor pattern would need two nested pattern features; nine seed cuts +
    # one pattern keeps every feature a plain cut or pattern.) The pattern's
    # own spacing dim is left static (as-built DIVISION_SPACING): its dim
    # index is not verified the way TickPattern's D3 is.
    minor_names = []
    for k in range(1, MINOR_PER_DIVISION):
        minor_names.append(
            await _cut_tick(
                adapter, f"minor tick 0.{k}", f"Minor{k}",
                SCALE_START_X + k * MINOR_SPACING, MINOR_TICK_LENGTH,
                drive_jobs=drive_jobs,
                drive_xcenter=f'"ScaleStartX" + {k} * "DivisionSpacing" / {MINOR_PER_DIVISION}',
                drive_length='"MinorTickLength"',
            )
        )
    check(
        "linear pattern minor ticks across divisions 1..9",
        await adapter.linear_pattern_feature(
            LinearPatternParameters(
                direction_point=[BODY_LENGTH / 2.0, 0.0, 0.0],
                features=minor_names,
                count=DIVISION_COUNT - 1,
                spacing=DIVISION_SPACING,
            )
        ),
    )
    name_last_feature(adapter, "MinorPattern")

    # The hand-stamped artefact the book calls out: a longer 0.5 tick (it
    # overcuts the 0.5 tenth above).
    await _cut_tick(
        adapter, "tick 0.5", "TickHalf",
        SCALE_START_X + DIVISION_SPACING / 2.0, HALF_TICK_LENGTH,
        drive_jobs=drive_jobs,
        drive_xcenter='"ScaleStartX" + "DivisionSpacing" / 2',
        drive_length='"HalfTickLength"',
    )

    await apply_material(adapter, MATERIAL)

    # Capture the as-built volume, then apply the deferred drive equations and
    # re-check: every equation evaluates to the value just built, so the geometry
    # must not move (the neutrality proof; this part's other checks are measures).
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"measuring stick: get_mass_properties failed: {mass.error}")
    v_built = float(mass.data.volume)
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven measuring-stick (equations neutral)", v_built, 0.005 * v_built
    )

    # Verify the annotated 200 mm length and the untouched front face
    # (the 14.2 mm tick spacing is driven by the linear pattern's spacing).
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
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Front View Note": FRONT_VIEW_NOTE,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
