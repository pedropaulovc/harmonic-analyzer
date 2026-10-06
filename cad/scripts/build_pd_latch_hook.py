r"""Reproduction script: latch hook (MHA-PD-014; book ch. 23 pp. 58-63; video 4/4).

The "small latch that allows the operator to disengage the gearing from the
platen" (ch23 text; p.58 "latch" callout): a 10 x 0.6 dead-soft bright steel
strip riveted at its square top end to the MHA-PD-021 bracket flap and curved
EDGEWISE down past the swing arm, where the 1/8 latch pin's crowned tip drops
into its Ø5.4 hole.  The operator releases the arm by flexing the strip +X.
Geometry and frame: ``pd_latch_hook_geometry`` (tangent R850 / R490 centreline,
full-round free end); printed bands, walls and notes: ``pd_latch_hook_spec``.

Layout (part frame, Front plane): origin at the centre of the square top cut;
the strip runs toward local -X.  The profile is one closed sketch -- the top
cut line, the outer edge (R855 then R495), the R5 full round, the inner edge
(R485 then R845) -- with the template's inner radii, the tangency run and the
tip run as its printed dimensions.  Extruded 0.6 along +Z (local +Z = machine
+X, the face on the flap).  The Ø5.4 pin hole and the two Ø1.65 rivet holes
are cut from their own sketches, their runs measured from the top cut.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_latch_hook.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
    SketchDims,
    apply_color,
    apply_material,
    bbox_extent_check,
    check,
    define_circle,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from pd_latch_hook_geometry import (
    C1_L,
    C2_L,
    END_L,
    END_LOWER,
    END_UPPER,
    INNER_R1,
    INNER_R2,
    JUNCTION_LOWER,
    JUNCTION_RUN,
    JUNCTION_UPPER,
    LOCAL_X_MAX,
    LOCAL_X_MIN,
    LOCAL_Y_MAX,
    LOCAL_Y_MIN,
    PIN_HOLE_DIA,
    PIN_HOLE_L,
    PROFILE_AREA,
    R1,
    R2,
    RIVET_HOLE_DIA,
    RIVET_L,
    RIVET_PITCH,
    STRIP_T,
    STRIP_W,
    TIP_RUN,
    TOP_LOWER,
    TOP_UPPER,
)
from pd_latch_hook_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    HOLE_BAND,
)

PART_NAME = "pd-latch-hook"
MATERIAL = "Plain Carbon Steel"  # dead-soft low-carbon strip (registry row)

# Extents (part frame) for the assembly's clearance asserts.
X_MIN = LOCAL_X_MIN
X_MAX = LOCAL_X_MAX
Y_MIN = LOCAL_Y_MIN
Y_MAX = LOCAL_Y_MAX

V_STRIP = PROFILE_AREA * STRIP_T
V_PIN_HOLE = math.pi * (PIN_HOLE_DIA / 2.0) ** 2 * STRIP_T
V_RIVET_HOLES = 2.0 * math.pi * (RIVET_HOLE_DIA / 2.0) ** 2 * STRIP_T


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). mm suffix load-bearing (INCH document).
    for name, value in (
        ("StripW", STRIP_W),
        ("StripT", STRIP_T),
        ("HookR1", R1),
        ("HookR2", R2),
        ("PinHoleDia", PIN_HOLE_DIA),
        ("RivetHoleDia", RIVET_HOLE_DIA),
        ("RivetPitch", RIVET_PITCH),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Outline: the top cut line and five arcs, direct-to-DB at their exact
    # coordinates, then constrained explicitly (29 DOF):
    # 6 joins (12) + 2 concentric pairs (4) + top line vertical, centred on
    # the origin, StripW long (4) + arc-1 centre under the origin (1) +
    # InnerR1 (1) + 4 tangencies (4) + InnerR2 (1) + JunctionRun (1) +
    # TipRun (1).  The outer radii and the R5 round follow from the width.
    # add_arc runs COUNTER-CLOCKWISE from its first to its second point.
    hook = SketchDims()
    check("create_sketch hook", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    top = check("top cut", await adapter.add_line(*TOP_LOWER, *TOP_UPPER))
    outer1 = check(
        "outer arc 1", await adapter.add_arc(*C1_L, *TOP_UPPER, *JUNCTION_UPPER)
    )
    outer2 = check(
        "outer arc 2", await adapter.add_arc(*C2_L, *JUNCTION_UPPER, *END_UPPER)
    )
    tip = check("free-end round", await adapter.add_arc(*END_L, *END_UPPER, *END_LOWER))
    inner2 = check(
        "inner arc 2", await adapter.add_arc(*C2_L, *JUNCTION_LOWER, *END_LOWER)
    )
    inner1 = check(
        "inner arc 1", await adapter.add_arc(*C1_L, *TOP_LOWER, *JUNCTION_LOWER)
    )
    set_sketch_direct_db(adapter, False)
    for label, a, b in (
        ("top-outer join", f"{top}.end", f"{outer1}.start"),
        ("outer junction", f"{outer1}.end", f"{outer2}.start"),
        ("outer-tip join", f"{outer2}.end", f"{tip}.start"),
        ("tip-inner join", f"{tip}.end", f"{inner2}.end"),
        ("inner junction", f"{inner2}.start", f"{inner1}.end"),
        ("inner-top join", f"{inner1}.start", f"{top}.start"),
        ("arc 1 concentric", f"{outer1}.center", f"{inner1}.center"),
        ("arc 2 concentric", f"{outer2}.center", f"{inner2}.center"),
    ):
        check(label, await adapter.add_sketch_constraint(a, b, "coincident"))
    check(
        "top cut vertical", await adapter.add_sketch_constraint(top, None, "vertical")
    )
    check(
        "top cut centred on origin",
        await adapter.add_sketch_constraint("origin", top, "midpoint"),
    )
    check(
        "strip width", await adapter.add_sketch_dimension(top, None, "linear", STRIP_W)
    )
    hook.record("StripW", '"StripW"')
    # Square top cut: arc 1 leaves it along -X, so its centre is under the origin.
    check(
        "arc 1 centre under the top cut",
        await adapter.add_sketch_constraint(
            f"{inner1}.center", "origin", "vertical_points"
        ),
    )
    check(
        "inner radius 1",
        await adapter.add_sketch_dimension(inner1, None, "radial", INNER_R1),
    )
    hook.record("InnerR1", '"HookR1" - "StripW" / 2')
    for label, a, b in (
        ("outer arcs tangent", outer1, outer2),
        ("inner arcs tangent", inner1, inner2),
        ("round tangent to outer", outer2, tip),
        ("round tangent to inner", inner2, tip),
    ):
        check(label, await adapter.add_sketch_constraint(a, b, "tangent"))
    check(
        "inner radius 2",
        await adapter.add_sketch_dimension(inner2, None, "radial", INNER_R2),
    )
    hook.record("InnerR2", '"HookR2" - "StripW" / 2')
    await dimension_between(
        adapter,
        "origin",
        f"{inner1}.end",
        "horizontal_distance",
        JUNCTION_RUN,
        "template tangency run",
    )
    hook.record("JunctionRun")
    await dimension_between(
        adapter,
        "origin",
        f"{tip}.center",
        "horizontal_distance",
        TIP_RUN,
        "free-end round run",
    )
    hook.record("TipRun")
    await ensure_fully_defined(adapter, "hook sketch")
    check("exit_sketch hook", await adapter.exit_sketch())
    name_last_feature(adapter, "HookProfile")
    drive_jobs += hook.apply(adapter, "HookProfile")
    check(
        "extrude hook",
        await adapter.create_extrusion(ExtrusionParameters(depth=STRIP_T)),
    )
    name_last_feature(adapter, "Hook")
    drive_jobs.append(("D1@Hook", '"StripT"'))
    expected = V_STRIP
    await volume_check(adapter, "hook strip", expected, 0.005 * V_STRIP)
    await bbox_extent_check(adapter, "hook run", "x", X_MAX - X_MIN)
    await bbox_extent_check(adapter, "hook drop", "y", Y_MAX - Y_MIN)
    await bbox_extent_check(adapter, "strip thickness", "z", STRIP_T)

    # The latch pin's hole, drilled after forming on the strip centreline.
    pin = SketchDims()
    check("create_sketch pin hole", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        *PIN_HOLE_L,
        PIN_HOLE_DIA / 2.0,
        "latch pin hole",
        dims=pin,
        names=("PinHoleRun", "PinHoleDrop", "PinHoleDia"),
        drives=(None, None, '"PinHoleDia"'),
    )
    await ensure_fully_defined(adapter, "pin hole sketch")
    check("exit_sketch pin hole", await adapter.exit_sketch())
    name_last_feature(adapter, "PinHoleProfile")
    drive_jobs += pin.apply(adapter, "PinHoleProfile")
    check(
        "cut pin hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * STRIP_T + 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "PinHole")
    expected -= V_PIN_HOLE
    await volume_check(adapter, "pin hole", expected, 0.02 * V_PIN_HOLE)

    # The two 1/16 rivet holes across the strip: the lower one anchored from
    # the origin (run from the top cut), the upper one straight above it at
    # the pitch, equal size.
    rivets = SketchDims()
    check("create_sketch rivet holes", await adapter.create_sketch("Front"))
    lower = await define_circle(
        adapter,
        *RIVET_L[0],
        RIVET_HOLE_DIA / 2.0,
        "lower rivet hole",
        dims=rivets,
        names=("RivetRun", "RivetDrop", "RivetHoleDia"),
        drives=(None, None, '"RivetHoleDia"'),
    )
    set_sketch_direct_db(adapter, True)
    upper = check(
        "upper rivet hole",
        await adapter.add_circle(*RIVET_L[1], RIVET_HOLE_DIA / 2.0),
    )
    set_sketch_direct_db(adapter, False)
    check(
        "rivet holes in line across the strip",
        await adapter.add_sketch_constraint(
            f"{upper}.center", f"{lower}.center", "vertical_points"
        ),
    )
    check(
        "rivet holes equal", await adapter.add_sketch_constraint(upper, lower, "equal")
    )
    await dimension_between(
        adapter,
        f"{lower}.center",
        f"{upper}.center",
        "vertical_distance",
        RIVET_PITCH,
        "rivet pitch",
    )
    rivets.record("RivetPitch", '"RivetPitch"')
    await ensure_fully_defined(adapter, "rivet hole sketch")
    check("exit_sketch rivet holes", await adapter.exit_sketch())
    name_last_feature(adapter, "RivetHoleProfile")
    drive_jobs += rivets.apply(adapter, "RivetHoleProfile")
    check(
        "cut rivet holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * STRIP_T + 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "RivetHoles")
    expected -= V_RIVET_HOLES
    await volume_check(adapter, "rivet holes", expected, 0.05 * V_RIVET_HOLES)

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven hook (equations neutral)", expected, 0.005 * expected
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    set_dimension_bilateral_tolerance(
        adapter, "PinHoleProfile", "PinHoleDia", *deviations(HOLE_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "RivetHoleProfile", "RivetHoleDia", *deviations(HOLE_BAND)
    )
    # Every other printed dimension is governed by its places: no model band.
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
