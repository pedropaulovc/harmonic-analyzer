r"""Reproduction script: channel (top) lever (book ch. 17, pp. 38-41).

One of the 20 cast third-class levers at the top of the machine: fulcrum
pivot at one end (Ø6.5 hole riding the common Ø6.35 fulcrum shaft - the
p.40 ball clevis is the shaft's END mount, mirroring the rocker-pivot
design), channel-spring pull from a narrow end tab (Ø4 hook hole at
177.8 = 7"), driven in between by its amplitude bar pinned Ø2 at 127
(5"). Section 9.5 tall x 3.0 thick: 20 levers at the 7.0565 channel
pitch cap the thickness (the M2 12.5 "width" violated the pitch), and
3.0 lets the bar's 3.2 top slot straddle the lever at the pin.

The earlier 254 (10", "clean 2:1") length is REFUTED by the calibrated
ch. 30 front view: the lever bank ends at x ~ -30 (not +54), the
summing-lever plate (44.45 wide, pivot bolt read at x ~ +13..17) sits
directly under the tab line, and the 32 mm channel springs can only
bridge lever tab -> plate if the tab holes are at x ~ -22 - i.e.
c2c = 177.8 from the -199.9 fulcrum (motion ratio 177.8/127 = 1.4).
The p.39 close-up also shows the bar pin only ~4-5 bar-heights from the
tip (50.8/9.5 = 5.3 fits; 127/9.5 = 13 does not). The tab itself is the
narrow stepped end visible on p.39/p.41: bar height 9.5 steps to a 6.0
centred tab carrying the spring hole, rounded tip.

Dimensions: cad/DIMENSIONS.md "Chapter 17" - lengths/section derived in
M6.3/M6.4 (med), hole diameters low.

Layout: lever length along +X from the pivot axis at the origin, bar
height in Y, thickness extruded mid-plane in Z. Through-holes use
mid-plane blind cuts (MCP issue #38 workaround).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_channel_lever.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    check,
    define_circle,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _holes import NUMBER_DRILL_MM, HoleSpec, wizard_holes

PART_NAME = "channel-lever"
MATERIAL = "Gray Cast Iron"  # see _common.apply_material docstring

LEVER_SPRING_X = 177.8  # DIMENSIONS.md ch17: fulcrum->spring-hole c2c, 7" (derived,
# M6.4: supersedes the 254 "2:1" guess - see docstring)
BAR_TALL = 9.5  # DIMENSIONS.md ch17: bar height, p.39 vs spring OD (low)
LEVER_THICKNESS = 3.0  # DIMENSIONS.md ch17: fits 7.06 pitch + 3.2 bar slot (derived)
PIVOT_HOLE_DIA = 6.5  # DIMENSIONS.md ch17: rides the 6.35 fulcrum shaft (derived)
BAR_PIN_X = 127.0  # 5" from the fulcrum (bar line -72.9, fulcrum -199.9)
# bar pin hole: was Ø2.0 drill, now #47 (Ø1.994) native Hole Wizard feature.
# spring eye hole: was Ø4.0 drill, now #21 (Ø4.039) native Hole Wizard feature
# -- sized so the spring's O5.5-mean O1-wire eye threads the tab with ~0.3
# margins; the O3 photo read (low) is infeasible. build_channel_assembly.py
# _assert_spring_threading checks threading against its own SPRING_HOLE_DIA=4.0
# (the #21 bore is 0.039 wider -> slightly MORE clearance, still fine).
TAB_START_X = 169.0  # bar steps down to the end tab (p.39/p.41, low)
TAB_HALF = 3.0  # tab 6.0 tall, centred on the bar axis
TIP_RADIUS = 3.0  # rounded tab tip; tip overhang = 182.8 + 3 - 177.8 = 8
TIP_ARC_CX = LEVER_SPRING_X + 5.0  # 182.8

HALF_BAR = BAR_TALL / 2.0
THROUGH_CUT_DEPTH = 40.0  # mid-plane total; > extrude width


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the lever's design constants. A GUI
    # fine-tune edits THESE globals -- never an auto "D1@Sketch1". The mm suffix
    # is load-bearing: this is an INCH document and the equation manager reads
    # BARE numbers in document units (an unsuffixed 177.8 = 177.8 in, blowing the
    # part up 25.4x). Derived globals (TipArcCx) reference others as equation
    # strings so the tip stays a fixed overhang past the spring hole.
    await set_global(adapter, "LeverSpringX", f"{LEVER_SPRING_X}mm")
    await set_global(adapter, "BarTall", f"{BAR_TALL}mm")
    await set_global(adapter, "LeverThickness", f"{LEVER_THICKNESS}mm")
    await set_global(adapter, "PivotHoleDia", f"{PIVOT_HOLE_DIA}mm")
    # (The old BarPinHoleDia/SpringHoleDia/BarPinX knobs are gone: the bar-pin and
    # spring holes are now native Hole Wizard features whose diameters come from
    # the #47/#21 drill standard, not equation-driven sketch dims.)
    await set_global(adapter, "TabStartX", f"{TAB_START_X}mm")
    await set_global(adapter, "TabHalf", f"{TAB_HALF}mm")
    await set_global(adapter, "TipRadius", f"{TIP_RADIUS}mm")
    await set_global(adapter, "TipArcCx", '"LeverSpringX" + 5mm')

    # Each sketch records its dim names + drive equations into a per-sketch
    # SketchDims as the dims are created; the drives are collected here and
    # applied in one deferred batch at the end (every equation target must
    # resolve against the finished model + a rebuild).
    drive_jobs: list[tuple[str, str]] = []

    # Side profile: round fulcrum nose, flat bar, stepped end tab with a
    # rounded tip (two arcs + 6-line chain). The manual constraints/dims below
    # define the sketch; each driving dim is record()ed into ``outline`` in the
    # exact order it is added so naming/driving land structurally.
    outline = SketchDims()
    check("create_sketch outline", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    nose = check(
        "add_arc fulcrum nose",
        await adapter.add_arc(0.0, 0.0, 0.0, HALF_BAR, 0.0, -HALF_BAR),
    )
    lower = await add_line_chain(
        adapter,
        [
            (0.0, -HALF_BAR),
            (TAB_START_X, -HALF_BAR),
            (TAB_START_X, -TAB_HALF),
            (TIP_ARC_CX, -TAB_HALF),
        ],
        close=False,
    )
    tip = check(
        "add_arc tab tip",
        await adapter.add_arc(
            TIP_ARC_CX, 0.0, TIP_ARC_CX, -TAB_HALF, TIP_ARC_CX, TAB_HALF
        ),
    )
    upper = await add_line_chain(
        adapter,
        [
            (TIP_ARC_CX, TAB_HALF),
            (TAB_START_X, TAB_HALF),
            (TAB_START_X, HALF_BAR),
            (0.0, HALF_BAR),
        ],
        close=False,
    )
    set_sketch_direct_db(adapter, False)
    # Semantic scheme: bar/tab edges horizontal, steps vertical; the nose
    # semicircle is pinned by centre-at-origin + radius + both ends on the
    # Y axis; the tip arc by its centre on the X axis at TIP_ARC_CX +
    # radius + both ends vertically aligned with its centre. One alignment
    # ties the lower step to the upper, one dim carries the bar length.
    lower_bar, lower_step, tab_bottom = lower
    tab_top, upper_step, upper_bar = upper
    for edge in (lower_bar, tab_bottom, tab_top, upper_bar):
        check(f"horizontal {edge}", await adapter.add_sketch_constraint(edge, None, "horizontal"))
    for edge in (lower_step, upper_step):
        check(f"vertical {edge}", await adapter.add_sketch_constraint(edge, None, "vertical"))
    check(
        "nose centre -> origin",
        await adapter.add_sketch_constraint(f"{nose}.center", "origin", "coincident"),
    )
    # Dim 1 (emission order): nose radius = HALF_BAR = BarTall / 2.
    check("nose radius", await adapter.add_sketch_dimension(nose, None, "radial", HALF_BAR))
    outline.record("NoseRadius", '"BarTall" / 2')
    for point in (f"{nose}.start", f"{nose}.end"):
        check(
            f"{point} on Y axis",
            await adapter.add_sketch_constraint(point, "origin", "vertical_points"),
        )
    # Dim 2: tip-centre X (on the X axis, +TIP_ARC_CX, so an unsigned distance
    # that already evaluates positive -- no negation needed).
    await anchor_point_to_origin(adapter, f"{tip}.center", TIP_ARC_CX, 0.0, "tip centre")
    outline.record("TipCentreX", '"TipArcCx"')
    # Dim 3: tip radius.
    check("tip radius", await adapter.add_sketch_dimension(tip, None, "radial", TIP_RADIUS))
    outline.record("TipRadius", '"TipRadius"')
    for point in (f"{tip}.start", f"{tip}.end"):
        check(
            f"{point} above/below tip centre",
            await adapter.add_sketch_constraint(point, f"{tip}.center", "vertical_points"),
        )
    check(
        "tab steps aligned",
        await adapter.add_sketch_constraint(
            f"{lower_step}.start", f"{upper_step}.start", "vertical_points"
        ),
    )
    # Dim 4: bar length (TAB_START_X).
    await dimension_between(
        adapter, f"{lower_bar}.start", f"{lower_bar}.end",
        "horizontal_distance", TAB_START_X, "bar length",
    )
    outline.record("BarLength", '"TabStartX"')
    await ensure_fully_defined(adapter, "lever outline")
    check("exit_sketch outline", await adapter.exit_sketch())
    name_last_feature(adapter, "LeverOutline")
    drive_jobs += outline.apply(adapter, "LeverOutline")
    check(
        "extrude lever",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=LEVER_THICKNESS, both_directions=True)
        ),
    )
    name_last_feature(adapter, "LeverBody")
    area = (
        TAB_START_X * BAR_TALL
        + math.pi * HALF_BAR**2 / 2.0
        + (TIP_ARC_CX - TAB_START_X) * 2.0 * TAB_HALF
        + math.pi * TIP_RADIUS**2 / 2.0
    )
    expected = area * LEVER_THICKNESS
    await volume_check(adapter, "lever outline", expected, 0.005 * expected)

    # Fulcrum hole (Ø6.5, rides the fulcrum shaft): a bearing bore, kept a plain
    # circle cut. On the origin, so only its diameter is a dim.
    fulcrum = SketchDims()
    check("create_sketch fulcrum hole", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, PIVOT_HOLE_DIA / 2.0, "fulcrum hole", dims=fulcrum,
        names=("FulcrumCx", "FulcrumCz", "FulcrumDia"),
        drives=(None, None, '"PivotHoleDia"'),
    )
    await ensure_fully_defined(adapter, "fulcrum hole sketch")
    check("exit_sketch fulcrum hole", await adapter.exit_sketch())
    name_last_feature(adapter, "FulcrumProfile")
    drive_jobs += fulcrum.apply(adapter, "FulcrumProfile")
    check(
        "cut fulcrum hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "FulcrumHole")
    v_fulcrum = math.pi * (PIVOT_HOLE_DIA / 2.0) ** 2 * LEVER_THICKNESS
    expected -= v_fulcrum
    await volume_check(adapter, "fulcrum hole", expected, 0.005 * expected)

    # Bar-pin hole (was Ø2.0 cut, now #47 Ø1.994) and spring-eye hole (was Ø4.0
    # cut, now #21 Ø4.039): native Hole Wizard through-holes drilled +Z through
    # the 3 mm lever (memory/fastener-policy-us-customary). Two specs -> two
    # feature calls, both on the +Z front face; each is fully inside the material
    # (the spring eye rides the 6.0 tab, Ø4.039 < 6.0), so removal is pi*r^2*t.
    bar_dia = NUMBER_DRILL_MM["#47"]
    wizard_holes(
        adapter,
        HoleSpec("drilled_number", "#47"),
        [[BAR_PIN_X, 0.0, LEVER_THICKNESS / 2.0]],
        (0.0, 0.0, 1.0),
        "bar-pin hole (#47)",
        name="BarPinHole",
    )
    expected -= math.pi * (bar_dia / 2.0) ** 2 * LEVER_THICKNESS
    await volume_check(adapter, "bar-pin hole", expected, 0.005 * expected)

    spring_dia = NUMBER_DRILL_MM["#21"]
    wizard_holes(
        adapter,
        HoleSpec("drilled_number", "#21"),
        [[LEVER_SPRING_X, 0.0, LEVER_THICKNESS / 2.0]],
        (0.0, 0.0, 1.0),
        "spring-eye hole (#21)",
        name="SpringHole",
    )
    expected -= math.pi * (spring_dia / 2.0) ** 2 * LEVER_THICKNESS
    await volume_check(adapter, "spring-eye hole", expected, 0.005 * expected)

    # Named bore axes for assembly mates (view-independent name selection):
    # Axis1 = fulcrum bore (origin, rides the fulcrum shaft), Axis2 = bar-pin
    # bore (127, 0, the amplitude bar's top pin).
    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "fulcrum bore")
    await name_bore_axis(
        adapter, "Right Plane", BAR_PIN_X, "Top Plane", 0.0, "bar pin bore"
    )

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves. Each equation evaluates to the value just
    # built, so the geometry must not move -- the re-check below is the proof.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven channel lever (equations neutral)", expected, 0.005 * expected)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
