r"""Reproduction script: pen frame / stirrup (book ch. 24, pp. 64-65).

The plain rectangular brass ring that hangs over the v-block's paper end: its
top rail rests on the block top, the marker barrel passes through the window
under the block, and the #4-40 thumb screw threaded up through the bottom rail
presses the barrel into the V-groove. Nested sketch contours (outer + inner
rectangle) extrude directly into the ring; the window's four internal corners
are then filleted.

Geometry and the drawing contract live in ``pn_pen_frame_spec`` (pure data,
shared with ``pn_pen_carriage_geom`` and ``draw_pn_pen_frame``).

Part frame (the assembly's placement contract): ring in the XY plane, origin
at the bottom-left outer corner of the sketch (Front-plane) face, width along
+X (0..OUTER_WIDTH), height along +Y (0..OUTER_HEIGHT), depth extruded +Z
(0..FRAME_DEPTH). The window is centred in X, so the ring is symmetric about
x = OUTER_WIDTH / 2 and cannot be mounted mirrored. The #4-40 tapped hole is a
Hole Wizard feature drilled up from the bottom face (y = 0) at
(OUTER_WIDTH / 2, 0, FRAME_DEPTH / 2), through the bottom rail into the
window; its axis is the named reference axis ``SetScrewAxis``. The hidden
Top-plane sketch ``TapWallReference`` carries the tap's stated far-wall
minimum (``TapWallMin``, a native MIN single limit) for the bottom view.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pn_pen_frame.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _feature_tree import name_last_feature
from _holes import wizard_holes
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _single_limit_tolerance import set_single_limit
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
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
    TAP_WALL_MIN_BAND,
    TAP_WALL_MIN_MM,
    TAP_WALL_MIN_TOL_TYPE,
    TAP_WALL_START_Z,
    WINDOW_CORNER_R,
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
# extruded FRAME_DEPTH; each concave window-corner fillet ADDS back its R x R
# square less the quarter disc; the tapped hole pierces only the bottom rail
# (y 0..RAIL_END) at the tap-drill diameter.
V_RING = (OUTER_WIDTH * OUTER_HEIGHT - WINDOW_WIDTH * WINDOW_HEIGHT) * FRAME_DEPTH
V_WINDOW_CORNER = (
    WINDOW_CORNER_R**2 - math.pi * WINDOW_CORNER_R**2 / 4.0
) * FRAME_DEPTH
V_SCREW_HOLE = math.pi * (SET_SCREW_TAP_DRILL_DIA / 2.0) ** 2 * RAIL_END
V_FINAL = V_RING + 4.0 * V_WINDOW_CORNER - V_SCREW_HOLE


async def _tap_wall_reference(adapter) -> None:
    """RV-01's accepted far wall, stated on the sheet natively (rule 20): a
    hidden construction line on the Top plane (the bottom face; sketch x =
    model X, sketch y = model -Z) running +Z from the tap's thread major on
    its axis, as long as the printed minimum, so its driving dimension prints
    ".074 MIN" once set_single_limit types it (build_dt_pinion_cam's
    _thin_wall_reference)."""
    check("create_sketch tap wall reference", await adapter.create_sketch("Top"))
    # Direct-to-DB: the line starts on the tap's rim, where creation-time
    # inference would snap it to the hole's edge.
    set_sketch_direct_db(adapter, True)
    start = (OUTER_WIDTH / 2.0, -TAP_WALL_START_Z)
    line = check(
        "tap wall reference line",
        await adapter.add_line(*start, start[0], start[1] - TAP_WALL_MIN_MM),
    )
    set_sketch_direct_db(adapter, False)
    segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError("tap wall reference line did not take the construction flag")
    check(
        "tap wall reference vertical",
        await adapter.add_sketch_constraint(line, None, "vertical"),
    )
    await dimension_between(
        adapter,
        f"{line}.start",
        f"{line}.end",
        "vertical_distance",
        TAP_WALL_MIN_MM,
        "tap wall reference",
    )
    await anchor_point_to_origin(adapter, f"{line}.start", *start, "tap wall reference")
    await ensure_fully_defined(adapter, "tap wall reference sketch")
    check("exit_sketch tap wall reference", await adapter.exit_sketch())
    name_last_feature(adapter, "TapWallReference")
    name_dimensions(adapter, "TapWallReference", ["TapWallMin", "TapWallX", "TapWallZ"])
    blank_reference_sketches(adapter, ("TapWallReference",))


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations): the outer envelope, the two rail
    # widths, the window corner radius and the depth. The mm suffix is
    # load-bearing -- this is an INCH document and the equation manager reads
    # BARE numbers in document units (an unsuffixed 28 = 28 in, blowing the
    # part up 25.4x in-plane).
    await set_global(adapter, "OuterWidth", f"{OUTER_WIDTH}mm")
    await set_global(adapter, "OuterHeight", f"{OUTER_HEIGHT}mm")
    await set_global(adapter, "RailSide", f"{RAIL_SIDE}mm")
    await set_global(adapter, "RailEnd", f"{RAIL_END}mm")
    await set_global(adapter, "FrameDepth", f"{FRAME_DEPTH}mm")
    await set_global(adapter, "WindowCornerR", f"{WINDOW_CORNER_R}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Outer + inner rectangles in one sketch -> ring on extrude. One SketchDims
    # spans BOTH chains in emission order: outer first (width span, height; its
    # anchor vertex IS the origin, so no anchor dims -- 2 dims), then inner. The
    # inner chain starts at the window's top-left corner and runs down, so its
    # two span dims sit on the window's LEFT edge (height) and BOTTOM edge
    # (width) -- the sheet prints them left of and below the ring, their
    # extension lines crossing only the rail they measure past -- and it is
    # anchored at its bottom-left corner (vertex 1): the left wall and the
    # bottom wall, each from a real outer face (drawing-guidelines.md rule 10).
    # Six dims fully define both rectangles; the right and top walls follow.
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
        (RAIL_SIDE, OUTER_HEIGHT - RAIL_END),
        (RAIL_SIDE, RAIL_END),
        (OUTER_WIDTH - RAIL_SIDE, RAIL_END),
        (OUTER_WIDTH - RAIL_SIDE, OUTER_HEIGHT - RAIL_END),
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
        anchor=1,
        label="inner ring",
        dims=ring,
        names=["WindowHeight", "WindowWidth", "LeftWall", "BottomWall"],
        drives=[
            '"OuterHeight" - 2 * "RailEnd"',
            '"OuterWidth" - 2 * "RailSide"',
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

    # Window internal corners (pn_pen_frame_spec.WINDOW_CORNER_R), each concave
    # fillet adding back its R x R square less the quarter disc. The printed 4X
    # radius belongs to "WindowCorner", a fillet on the TOP-RIGHT window edge
    # alone: an imported fillet dimension attaches to its feature's first edge
    # (pd_guide_lock's farm run 20261012T061737079Z), and the top-right corner
    # is the one no window dimension's extension line leaves from, so the
    # sheet's radius leader runs out through the right rail without crossing
    # one. The other three corners are one unprinted fillet driven by the same
    # WindowCornerR. Edge points sit at mid-depth on each corner's Z edge.
    window_x = (RAIL_SIDE, OUTER_WIDTH - RAIL_SIDE)
    window_y = (RAIL_END, OUTER_HEIGHT - RAIL_END)
    corner_features = (
        ("WindowCorner", "WindowCornerR", ((window_x[1], window_y[1]),)),
        (
            "OtherWindowCorners",
            "OtherWindowCornerR",
            (
                (window_x[0], window_y[0]),
                (window_x[1], window_y[0]),
                (window_x[0], window_y[1]),
            ),
        ),
    )
    v_after = V_RING
    for feature, dimension, corners in corner_features:
        edges = [[x, y, FRAME_DEPTH / 2.0] for x, y in corners]
        check(f"fillet {feature}", await adapter.add_fillet(WINDOW_CORNER_R, edges))
        name_last_feature(adapter, feature)
        corner_dim = name_dimensions(adapter, feature, [dimension])
        drive_jobs.append((corner_dim[0], '"WindowCornerR"'))
        v_corners = len(corners) * V_WINDOW_CORNER
        v_after += v_corners
        await volume_check(adapter, f"ring with {feature}", v_after, 0.1 * v_corners)

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
    await _tap_wall_reference(adapter)

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
    set_single_limit(
        adapter,
        "TapWallReference",
        "TapWallMin",
        limit=TAP_WALL_MIN_MM,
        band=TAP_WALL_MIN_BAND,
        tol_type=TAP_WALL_MIN_TOL_TYPE,
    )
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
