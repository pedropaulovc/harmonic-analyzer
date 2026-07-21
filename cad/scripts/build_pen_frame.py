r"""Reproduction script: pen frame / stirrup (book ch. 24, pp. 64-65).

The rectangular brass yoke that wraps the v-block and marker; the set
screw threads up through its bottom rail to set the pen angle. Nested
sketch contours (outer + inner rectangle) extrude directly into the ring.

Dimensions: cad/DIMENSIONS.md "Chapter 24" — scaled from the p.64-65
photos vs the ~5 mm square rod (low). Side rails 4, end rails 5 (the
window must span the marker + pen rod when the frame lies flat on the
v-block, long axis along machine X -- see build_pen_assembly.py).

Layout: width along +X, height along +Y from the origin corner, depth
extruded +Z; set-screw hole cut along Y from a Top-plane sketch with a
mid-plane depth short enough to spare the top rail.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pen_frame.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    add_line_chain,
    apply_material,
    check,
    define_rectilinear_chain,
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
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _holes import TAP_DRILL_MM, HoleSpec, wizard_holes
from pen_frame_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    FRONT_VIEW_NOTE,
    ISOMETRIC_VIEW_NOTE,
    RIGHT_VIEW_NOTE,
)

PART_NAME = "pen-frame"
MATERIAL = "Brass"  # see _common.apply_material docstring

OUTER_WIDTH = 22.0  # X  DIMENSIONS.md ch24: p.64/65 vs 5 mm rod (low)
OUTER_HEIGHT = 40.0  # Y
RAIL_SIDE = 4.0  # long-side rails (local X): read thinner in the photo; the
# extra 1 mm of window also clears the marker barrel at the platen side in
# the M6.4 flat-on-the-v-block layout
RAIL_END = 5.0  # end rails (local Y); the screw rail keeps thread depth
TRIM_NEAR = 0.75  # local x = 0 edge pulled back: that rail faces the platen
# (machine z = -143 - local x) and must clear the recording paper's front
# face at -143.4 by the 0.25+ margin (M6.8 platen-paper)
FRAME_DEPTH = 10.0  # Z
# The set screw threads INTO the bottom rail, so its hole is a #4-40 tapped
# Hole Wizard hole (tap drill Ø2.261; was a plain Ø3.0 cut) drilled up from the
# bottom face. THROUGH_NEXT (not through-all) stops at the window cavity so the
# top rail is spared, matching the old mid-plane cut -- fastener-policy memory.


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the outer envelope, the two rail
    # widths, the near-edge trim and the depth, plus the set-screw diameter. The
    # mm suffix is load-bearing -- this is an INCH document and the equation
    # manager reads BARE numbers in document units (an unsuffixed 22 = 22 in,
    # blowing the part up 25.4x in-plane).
    await set_global(adapter, "OuterWidth", f"{OUTER_WIDTH}mm")
    await set_global(adapter, "OuterHeight", f"{OUTER_HEIGHT}mm")
    await set_global(adapter, "RailSide", f"{RAIL_SIDE}mm")
    await set_global(adapter, "RailEnd", f"{RAIL_END}mm")
    await set_global(adapter, "TrimNear", f"{TRIM_NEAR}mm")
    await set_global(adapter, "FrameDepth", f"{FRAME_DEPTH}mm")
    # (The old ScrewHoleDia knob is gone: the set-screw hole is now a native
    # Hole Wizard #4-40 tapped feature placed by point.)

    drive_jobs: list[tuple[str, str]] = []

    # Outer + inner rectangles in one sketch -> ring on extrude. Inference
    # OFF for the outer chain: the TRIM_NEAR corners sit 0.75 from the
    # origin/axes and snap back to x = 0 with it on (caught by the extrude
    # volume reading untrimmed 4600). One SketchDims spans BOTH chains in
    # emission order: outer first (width-span, height, anchor-X -- anchor at
    # (TrimNear, 0) emits only X; 3 dims), then inner (width-span, height,
    # anchor-X, anchor-Z -- anchor at (RailSide, RailEnd) emits both; 4 dims):
    # seven display dims on the one RingProfile feature.
    ring = SketchDims()
    check("create_sketch ring", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    outer_rect = [
        (TRIM_NEAR, 0.0),
        (OUTER_WIDTH, 0.0),
        (OUTER_WIDTH, OUTER_HEIGHT),
        (TRIM_NEAR, OUTER_HEIGHT),
    ]
    outer = await add_line_chain(adapter, outer_rect)
    set_sketch_direct_db(adapter, False)
    inner_rect = [
        (RAIL_SIDE, RAIL_END),
        (OUTER_WIDTH - RAIL_SIDE, RAIL_END),
        (OUTER_WIDTH - RAIL_SIDE, OUTER_HEIGHT - RAIL_END),
        (RAIL_SIDE, OUTER_HEIGHT - RAIL_END),
    ]
    inner = await add_line_chain(adapter, inner_rect)
    await define_rectilinear_chain(
        adapter, outer, outer_rect, label="outer ring", dims=ring,
        names=["OuterSpanX", "OuterHeightDim", "OuterAnchorX"],
        drives=['"OuterWidth" - "TrimNear"', '"OuterHeight"', '"TrimNear"'],
    )
    await define_rectilinear_chain(
        adapter, inner, inner_rect, label="inner ring", dims=ring,
        names=["InnerSpanX", "InnerSpanY", "InnerAnchorX", "InnerAnchorY"],
        drives=[
            '"OuterWidth" - 2 * "RailSide"',
            '"OuterHeight" - 2 * "RailEnd"',
            '"RailSide"',
            '"RailEnd"',
        ],
    )
    await ensure_fully_defined(adapter, "ring sketch")
    check("exit_sketch ring", await adapter.exit_sketch())
    name_last_feature(adapter, "RingProfile")
    drive_jobs += ring.apply(adapter, "RingProfile")
    check(
        "extrude ring",
        await adapter.create_extrusion(ExtrusionParameters(depth=FRAME_DEPTH)),
    )
    name_last_feature(adapter, "Ring")
    ring_expected = (
        (OUTER_WIDTH - TRIM_NEAR) * OUTER_HEIGHT
        - (OUTER_WIDTH - 2.0 * RAIL_SIDE) * (OUTER_HEIGHT - 2.0 * RAIL_END)
    ) * FRAME_DEPTH
    # volume_check fails loud on mismatch -- same guard the old explicit raise
    # served (a TRIM_NEAR corner snapping back to x = 0 reads untrimmed).
    await volume_check(adapter, "ring", ring_expected, 0.005 * ring_expected)

    # Set-screw hole: ONE native Hole Wizard #4-40 tapped feature drilled up
    # from the bottom face (Y=0, outward normal -Y). THROUGH_NEXT stops at the
    # window cavity so only the bottom rail is pierced (the top rail is spared),
    # matching the old mid-plane cut. The hole sits at the rail mid-span in X
    # and the depth mid-plane in Z.
    screw_cut = wizard_holes(
        adapter,
        HoleSpec("tapped", "#4-40", end="through_next"),
        [[OUTER_WIDTH / 2.0, 0.0, FRAME_DEPTH / 2.0]],
        (0.0, -1.0, 0.0),
        "set-screw tapped hole (#4-40)", name="ScrewHole",
        placement_dims=[(
            ("ScrewX", '"OuterWidth" / 2'),
            ("ScrewZ", '"FrameDepth" / 2'),
        )],
    )
    drive_jobs += screw_cut.placement_drive_jobs
    # The tapped column pierces only the bottom rail (Y 0..RailEnd), so it
    # removes pi*r^2*RailEnd at the tap-drill diameter. Loose tol for the
    # rounding / mesh at the cut walls.
    v_screw = math.pi * (TAP_DRILL_MM["#4-40"] / 2.0) ** 2 * RAIL_END
    v_final = ring_expected - v_screw
    await volume_check(adapter, "screw hole", v_final, 15.0)

    await name_bore_axis(
        adapter,
        "Right Plane",
        OUTER_WIDTH / 2.0,
        "Front Plane",
        FRAME_DEPTH / 2.0,
        "set-screw hole",
    )
    name_last_feature(adapter, "SetScrewAxis")

    # Apply the deferred drive equations after the whole model + a rebuild
    # exists, then re-check neutrality (each equation evaluates to the as-built
    # value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven pen frame (equations neutral)", v_final, 15.0)

    await apply_material(adapter, MATERIAL)
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
            "Right View Note": RIGHT_VIEW_NOTE,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
