r"""Reproduction script: pen frame / stirrup (book ch. 24, pp. 64-65).

The plain rectangular brass ring that hangs over the v-block's paper end: its
top rail rests on the block top, the marker barrel passes through the window
under the block, and the #4-40 thumb screw threaded up through the bottom rail
presses the barrel into the V-groove. Nested sketch contours (outer + inner
rectangle) extrude directly into the ring.

Geometry and the drawing contract live in ``pn_pen_frame_spec`` (pure data,
shared with ``pn_pen_carriage_geom`` and ``draw_pn_pen_frame``).

Part frame (the assembly's placement contract): ring in the XY plane, origin
at the bottom-left outer corner of the sketch (Front-plane) face, width along
+X (0..OUTER_WIDTH), height along +Y (0..OUTER_HEIGHT), depth extruded +Z
(0..FRAME_DEPTH). The window is centred in X, so the ring is symmetric about
x = OUTER_WIDTH / 2 and cannot be mounted mirrored. The #4-40 tapped hole is a
Hole Wizard feature drilled up from the bottom face (y = 0) at
(OUTER_WIDTH / 2, 0, FRAME_DEPTH / 2), through the bottom rail into the
window; its axis is the named reference axis ``SetScrewAxis``.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pn_pen_frame.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _dimensions import drive_dimension, name_dimensions, set_global
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _feature_tree import name_last_feature
from _holes import wizard_holes
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import SketchDims, add_line_chain, ensure_fully_defined
from _sketch_chains import define_rectilinear_chain
from pn_pen_frame_spec import (
    BOTTOM_VIEW_NOTE,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FRAME_DEPTH,
    FRONT_VIEW_NOTE,
    ISOMETRIC_VIEW_NOTE,
    OUTER_HEIGHT,
    OUTER_WIDTH,
    RAIL_END,
    RAIL_SIDE,
    SET_SCREW_TAP_DRILL_DIA,
    SET_SCREW_TAP_SPEC,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)

PART_NAME = "pn-pen-frame"
MATERIAL = "Brass"  # see _appearance.apply_material docstring
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Front View Note",
    "Bottom View Note",
    "Isometric View Note",
)

# Analytic volumes (mm^3): the ring is the outer rectangle less the window,
# extruded FRAME_DEPTH; the tapped hole pierces only the bottom rail
# (y 0..RAIL_END) at the tap-drill diameter.
V_RING = (OUTER_WIDTH * OUTER_HEIGHT - WINDOW_WIDTH * WINDOW_HEIGHT) * FRAME_DEPTH
V_SCREW_HOLE = math.pi * (SET_SCREW_TAP_DRILL_DIA / 2.0) ** 2 * RAIL_END
V_FINAL = V_RING - V_SCREW_HOLE


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the outer envelope, the two rail
    # widths and the depth. The mm suffix is load-bearing -- this is an INCH
    # document and the equation manager reads BARE numbers in document units
    # (an unsuffixed 28 = 28 in, blowing the part up 25.4x in-plane).
    await set_global(adapter, "OuterWidth", f"{OUTER_WIDTH}mm")
    await set_global(adapter, "OuterHeight", f"{OUTER_HEIGHT}mm")
    await set_global(adapter, "RailSide", f"{RAIL_SIDE}mm")
    await set_global(adapter, "RailEnd", f"{RAIL_END}mm")
    await set_global(adapter, "FrameDepth", f"{FRAME_DEPTH}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Outer + inner rectangles in one sketch -> ring on extrude. One SketchDims
    # spans BOTH chains in emission order: outer first (width span, height; its
    # anchor vertex IS the origin, so no anchor dims -- 2 dims), then inner
    # (width span, height span, anchor X, anchor Y -- the window corner sits at
    # (RailSide, RailEnd), so both anchor dims emit; 4 dims).
    ring = SketchDims()
    check("create_sketch ring", await adapter.create_sketch("Front"))
    outer_rect = [
        (0.0, 0.0),
        (OUTER_WIDTH, 0.0),
        (OUTER_WIDTH, OUTER_HEIGHT),
        (0.0, OUTER_HEIGHT),
    ]
    outer = await add_line_chain(adapter, outer_rect)
    inner_rect = [
        (RAIL_SIDE, RAIL_END),
        (OUTER_WIDTH - RAIL_SIDE, RAIL_END),
        (OUTER_WIDTH - RAIL_SIDE, OUTER_HEIGHT - RAIL_END),
        (RAIL_SIDE, OUTER_HEIGHT - RAIL_END),
    ]
    inner = await add_line_chain(adapter, inner_rect)
    await define_rectilinear_chain(
        adapter,
        outer,
        outer_rect,
        label="outer ring",
        dims=ring,
        names=["OuterSpanX", "OuterHeightDim"],
        drives=['"OuterWidth"', '"OuterHeight"'],
    )
    await define_rectilinear_chain(
        adapter,
        inner,
        inner_rect,
        label="inner ring",
        dims=ring,
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
    depth_dim = name_dimensions(adapter, "Ring", ["Depth"])
    drive_jobs += [(depth_dim[0], '"FrameDepth"')]
    await volume_check(adapter, "ring", V_RING, 0.005 * V_RING)

    # Thumb-screw hole: ONE native Hole Wizard #4-40 tapped feature drilled up
    # from the bottom face (y = 0, outward normal -Y). THROUGH_NEXT stops at
    # the window cavity so only the bottom rail is pierced (the top rail is
    # spared). The hole sits at the rail mid-span in X and the depth mid-plane
    # in Z, each located from the origin corner's faces.
    screw_cut = wizard_holes(
        adapter,
        SET_SCREW_TAP_SPEC,
        [[OUTER_WIDTH / 2.0, 0.0, FRAME_DEPTH / 2.0]],
        (0.0, -1.0, 0.0),
        "thumb-screw tapped hole (#4-40)",
        name="ScrewHole",
        placement_dims=[
            (
                ("ScrewX", '"OuterWidth" / 2'),
                ("ScrewZ", '"FrameDepth" / 2'),
            )
        ],
    )
    drive_jobs += screw_cut.placement_drive_jobs
    # Loose tol for the rounding / mesh at the cut walls.
    await volume_check(adapter, "screw hole", V_FINAL, 15.0)

    await name_bore_axis(
        adapter,
        "Right Plane",
        OUTER_WIDTH / 2.0,
        "Front Plane",
        FRAME_DEPTH / 2.0,
        "thumb-screw hole",
    )
    name_last_feature(adapter, "SetScrewAxis")

    # Apply the deferred drive equations after the whole model + a rebuild
    # exists, then re-check neutrality (each equation evaluates to the as-built
    # value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven pen frame (equations neutral)", V_FINAL, 15.0)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    # Printed places live on the model (the sheet only reads them back); then
    # mark exactly the print's dimensions and stamp the title-block properties.
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Front View Note": FRONT_VIEW_NOTE,
            "Bottom View Note": BOTTOM_VIEW_NOTE,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
