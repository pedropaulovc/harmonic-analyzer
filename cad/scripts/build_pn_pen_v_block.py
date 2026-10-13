r"""Reproduction script: pen v-block (MHA-PN-005), re-derived per
``pn_pen_v_block_spec``.

The bright brass block that hangs on the pen rod and carries the marker: 45
degree chamfered top corners; a 90 degree V-groove under the paper end that
seats the marker's grip; a flat-roofed relief slot over the rest of the length
that passes the marker's body; the rod's reamed pivot bore from the top face
down into the relief; a #4-40 set-screw tap from the front face into that bore;
and a 5/16 lightening bore at the free end, also opening into the relief.

Part frame (the assembly places the part by its origin and Front/Top/Right
planes, so this is a contract): X 0..BLOCK_LENGTH along the marker, x 0 the
PAPER end face; Y 0..BLOCK_HEIGHT up, y 0 the bottom face; Z 0..BLOCK_DEPTH
across the depth, z 0 the FRONT face (away from the paper). The origin is the
bottom/paper-end/front corner.

Features, in tree order:

* ``OutlineProfile`` (Front plane) -> ``Block``: the chamfered end outline,
  extruded +Z by the depth.
* ``VGrooveProfile`` (Right plane, sketch (u, v) = model (-Z, Y)) ->
  ``VGroove``: the V triangle, cut +X from the paper end to ``RELIEF_X0``.
* ``ReliefProfile`` (Top plane, sketch (u, v) = model (X, -Z)) -> ``Relief``:
  the slot rectangle from ``RELIEF_X0`` to the free end, cut +Y to the roof.
* ``PivotBoreProfile`` (Top plane) -> ``PivotBore``: the reamed bore, a
  sketched through cut; it removes brass only between the top face and the
  relief roof.  Its diameter carries the H7 band.
* ``SetScrewHole``: Hole Wizard #4-40 tap from the front face, up to the
  pivot bore (``through_next``); built after the bore so it stops there.
* ``LighteningBore``: Hole Wizard 5/16 drill from the top face, through all;
  it opens into the relief.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pn_pen_v_block.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _check import check
from _dimensions import drive_dimension, name_dimensions, set_global
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _feature_tree import name_last_feature
from _fit_deviations import deviations
from _holes import TAP_DRILL_MM, cross_hole_volume_mm3, wizard_holes
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
)
from _sketch_chains import define_rectilinear_chain
from _sketch_circle import define_circle
from pn_pen_v_block_spec import (
    BLOCK_DEPTH,
    BLOCK_HEIGHT,
    BLOCK_LENGTH,
    CHAMFER,
    DRAWING_BANDS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    LIGHTENING_DIA,
    LIGHTENING_SPEC,
    LIGHTENING_X,
    PIVOT_BORE_DIA,
    PIVOT_BORE_X,
    RELIEF_HEIGHT,
    RELIEF_WIDTH,
    RELIEF_X0,
    SET_SCREW_TAP_SPEC,
    SET_SCREW_Y,
    V_ANGLE_DEG,
    V_APEX_Y,
    V_MOUTH_WIDTH,
)

PART_NAME = "pn-pen-v-block"
MATERIAL = "Brass"  # see _appearance.apply_material docstring

THROUGH_CUT_DEPTH = 80.0  # mid-plane total; > any extent crossed
TAP_DRILL_DIA = TAP_DRILL_MM[SET_SCREW_TAP_SPEC.size]
_Z_MID = BLOCK_DEPTH / 2.0

# Analytic volumes (mm^3) of each feature, checked after it is built.
V_BLOCK = (BLOCK_LENGTH * BLOCK_HEIGHT - CHAMFER**2) * BLOCK_DEPTH
V_GROOVE = V_APEX_Y * V_MOUTH_WIDTH / 2.0 * RELIEF_X0
V_RELIEF = RELIEF_WIDTH * RELIEF_HEIGHT * (BLOCK_LENGTH - RELIEF_X0)
# Both vertical bores remove brass only from the relief roof to the top face.
V_PIVOT_BORE = math.pi * (PIVOT_BORE_DIA / 2.0) ** 2 * (BLOCK_HEIGHT - RELIEF_HEIGHT)
# The tap runs from the front face to where its whole profile is inside the
# bore: the drill cylinder to the bore axis less its near half of the
# drill-through-bore intersection (already void).
V_SET_SCREW_TAP = (
    math.pi * (TAP_DRILL_DIA / 2.0) ** 2 * _Z_MID
    - cross_hole_volume_mm3(TAP_DRILL_DIA, PIVOT_BORE_DIA) / 2.0
)
V_LIGHTENING = math.pi * (LIGHTENING_DIA / 2.0) ** 2 * (BLOCK_HEIGHT - RELIEF_HEIGHT)
V_TOTAL = V_BLOCK - V_GROOVE - V_RELIEF - V_PIVOT_BORE - V_SET_SCREW_TAP - V_LIGHTENING


async def _outline(adapter, dims: SketchDims) -> None:
    """The chamfered end outline on the Front plane, from the origin corner.

    Lines L0..L5 run (0,0) -> (L,0) -> (L,H-C) -> (L-C,H) -> (C,H) -> (0,H-C).
    Relations: L0 starts on the origin; L0/L3 horizontal, L1/L5 vertical.
    Dims: the overall length and height (top flat from the bottom), then each
    chamfer's two legs -- 12 point DOF less 2 + 4 relations + 6 dims = 0.
    """
    points = [
        (0.0, 0.0),
        (BLOCK_LENGTH, 0.0),
        (BLOCK_LENGTH, BLOCK_HEIGHT - CHAMFER),
        (BLOCK_LENGTH - CHAMFER, BLOCK_HEIGHT),
        (CHAMFER, BLOCK_HEIGHT),
        (0.0, BLOCK_HEIGHT - CHAMFER),
    ]
    lines = await add_line_chain(adapter, points)
    await anchor_point_to_origin(
        adapter, f"{lines[0]}.start", 0.0, 0.0, "outline origin corner"
    )
    for index, relation in (
        (0, "horizontal"),
        (1, "vertical"),
        (3, "horizontal"),
        (5, "vertical"),
    ):
        check(
            f"outline L{index} {relation}",
            await adapter.add_sketch_constraint(lines[index], None, relation),
        )
    await dimension_between(
        adapter,
        f"{lines[0]}.start",
        f"{lines[0]}.end",
        "horizontal_distance",
        BLOCK_LENGTH,
        "block length",
    )
    dims.record("Length", '"BlockLength"')
    await dimension_between(
        adapter,
        f"{lines[0]}.start",
        f"{lines[3]}.end",
        "vertical_distance",
        BLOCK_HEIGHT,
        "block height",
    )
    dims.record("Height", '"BlockHeight"')
    for corner, line in ((2, lines[2]), (4, lines[4])):
        await dimension_between(
            adapter,
            f"{line}.start",
            f"{line}.end",
            "horizontal_distance",
            CHAMFER,
            f"chamfer {corner} dx",
        )
        dims.record(f"Chamfer{corner}dx", '"Chamfer"')
        await dimension_between(
            adapter,
            f"{line}.start",
            f"{line}.end",
            "vertical_distance",
            CHAMFER,
            f"chamfer {corner} dy",
        )
        dims.record(f"Chamfer{corner}dy", '"Chamfer"')


async def _v_groove(adapter, dims: SketchDims) -> None:
    """The V triangle on the Right plane, sketch (u, v) = model (-Z, Y).

    LA runs front mouth -> apex, LB apex -> back mouth, LC back mouth -> front
    mouth along the bottom face.  Relations: LC horizontal, its front mouth on
    the origin's level, LA = LB (the V symmetric about the apex).  Dims: the
    apex across the depth and above the bottom, and the included angle --
    6 DOF less 3 relations + 3 dims = 0.
    """
    half = V_MOUTH_WIDTH / 2.0
    points = [(-(_Z_MID - half), 0.0), (-_Z_MID, V_APEX_Y), (-(_Z_MID + half), 0.0)]
    flank_a, flank_b, mouth = await add_line_chain(adapter, points)
    check(
        "V mouth horizontal",
        await adapter.add_sketch_constraint(mouth, None, "horizontal"),
    )
    check(
        "V mouth on the bottom face",
        await adapter.add_sketch_constraint(
            f"{flank_a}.start", "origin", "horizontal_points"
        ),
    )
    check(
        "V flanks equal", await adapter.add_sketch_constraint(flank_a, flank_b, "equal")
    )
    await dimension_between(
        adapter,
        f"{flank_a}.end",
        "origin",
        "horizontal_distance",
        _Z_MID,
        "V apex across depth",
    )
    dims.record("VApexZ", '"BlockDepth" / 2')
    await dimension_between(
        adapter,
        f"{flank_a}.end",
        "origin",
        "vertical_distance",
        V_APEX_Y,
        "V apex height",
    )
    dims.record("VApexY", '"VApexY"')
    check(
        "V included angle",
        await adapter.add_sketch_dimension(flank_a, flank_b, "angular", V_ANGLE_DEG),
    )
    dims.record("VAngle", '"VAngle"')


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 36 = 36 in).
    for name, value in (
        ("BlockLength", BLOCK_LENGTH),
        ("BlockHeight", BLOCK_HEIGHT),
        ("BlockDepth", BLOCK_DEPTH),
        ("Chamfer", CHAMFER),
        ("VApexY", V_APEX_Y),
        ("ReliefX0", RELIEF_X0),
        ("ReliefWidth", RELIEF_WIDTH),
        ("ReliefHeight", RELIEF_HEIGHT),
        ("PivotBoreX", PIVOT_BORE_X),
        ("PivotBoreDia", PIVOT_BORE_DIA),
        ("SetScrewY", SET_SCREW_Y),
        ("LighteningX", LIGHTENING_X),
    ):
        await set_global(adapter, name, f"{value}mm")
    await set_global(adapter, "VAngle", f"{V_ANGLE_DEG}deg")

    # Each sketch records its dim names + drive equations in emission order;
    # the equations are applied in one deferred batch once the model exists.
    drive_jobs: list[tuple[str, str]] = []

    # 1. Chamfered outline, extruded +Z by the depth.
    outline = SketchDims()
    check("create_sketch outline", await adapter.create_sketch("Front"))
    await _outline(adapter, outline)
    await ensure_fully_defined(adapter, "block outline")
    check("exit_sketch outline", await adapter.exit_sketch())
    name_last_feature(adapter, "OutlineProfile")
    drive_jobs += outline.apply(adapter, "OutlineProfile")
    check(
        "extrude block",
        await adapter.create_extrusion(ExtrusionParameters(depth=BLOCK_DEPTH)),
    )
    name_last_feature(adapter, "Block")
    drive_jobs += [(name_dimensions(adapter, "Block", ["Depth"])[0], '"BlockDepth"')]
    volume = await volume_check(adapter, "block", V_BLOCK, 0.001 * V_BLOCK)

    # 2. The grip's V-groove, cut +X (the Right plane's normal) from the paper
    # end face to the relief's start.
    groove = SketchDims()
    check("create_sketch V-groove", await adapter.create_sketch("Right"))
    await _v_groove(adapter, groove)
    await ensure_fully_defined(adapter, "V-groove sketch")
    check("exit_sketch V-groove", await adapter.exit_sketch())
    name_last_feature(adapter, "VGrooveProfile")
    drive_jobs += groove.apply(adapter, "VGrooveProfile")
    check(
        "cut V-groove",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=RELIEF_X0)),
    )
    name_last_feature(adapter, "VGroove")
    drive_jobs += [(name_dimensions(adapter, "VGroove", ["VLength"])[0], '"ReliefX0"')]
    volume = await volume_check(adapter, "V-groove", volume - V_GROOVE, 0.01 * V_GROOVE)

    # 3. The body's relief slot, cut +Y (the Top plane's normal) up to its roof.
    # The rectilinear chain starts at the slot's paper-end front corner; the
    # closure-implied segment of each direction is skipped, so it emits the
    # length and width, then the corner's X and Z anchor dims.
    relief = SketchDims()
    check("create_sketch relief", await adapter.create_sketch("Top"))
    z0 = (BLOCK_DEPTH - RELIEF_WIDTH) / 2.0
    rect = [
        (RELIEF_X0, -z0),
        (BLOCK_LENGTH, -z0),
        (BLOCK_LENGTH, -(z0 + RELIEF_WIDTH)),
        (RELIEF_X0, -(z0 + RELIEF_WIDTH)),
    ]
    rect_lines = await add_line_chain(adapter, rect)
    await define_rectilinear_chain(
        adapter,
        rect_lines,
        rect,
        label="relief slot",
        dims=relief,
        names=["ReliefLength", "ReliefWidth", "ReliefX0", "ReliefZ0"],
        drives=[
            '"BlockLength" - "ReliefX0"',
            '"ReliefWidth"',
            '"ReliefX0"',
            '("BlockDepth" - "ReliefWidth") / 2',
        ],
    )
    await ensure_fully_defined(adapter, "relief sketch")
    check("exit_sketch relief", await adapter.exit_sketch())
    name_last_feature(adapter, "ReliefProfile")
    drive_jobs += relief.apply(adapter, "ReliefProfile")
    check(
        "cut relief",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=RELIEF_HEIGHT)),
    )
    name_last_feature(adapter, "Relief")
    drive_jobs += [
        (name_dimensions(adapter, "Relief", ["ReliefHeight"])[0], '"ReliefHeight"')
    ]
    volume = await volume_check(
        adapter, "relief slot", volume - V_RELIEF, 0.01 * V_RELIEF
    )

    # 4. The rod's reamed pivot bore: a Top-plane circle cut mid-plane through
    # everything; below the roof it crosses only the relief's void.
    pivot = SketchDims()
    check("create_sketch pivot bore", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        PIVOT_BORE_X,
        -_Z_MID,
        PIVOT_BORE_DIA / 2.0,
        "pivot bore",
        dims=pivot,
        names=("PivotX", "PivotZ", "PivotDia"),
        drives=('"PivotBoreX"', '"BlockDepth" / 2', '"PivotBoreDia"'),
    )
    await ensure_fully_defined(adapter, "pivot bore sketch")
    check("exit_sketch pivot bore", await adapter.exit_sketch())
    name_last_feature(adapter, "PivotBoreProfile")
    drive_jobs += pivot.apply(adapter, "PivotBoreProfile")
    check(
        "cut pivot bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "PivotBore")
    volume = await volume_check(
        adapter, "pivot bore", volume - V_PIVOT_BORE, 0.01 * V_PIVOT_BORE
    )

    # 5. The rod set-screw tap: front face (outward normal -Z) up to the pivot
    # bore it locks the rod's pivot in.  Placement sketch on the z 0 face.
    tap = wizard_holes(
        adapter,
        SET_SCREW_TAP_SPEC,
        [[PIVOT_BORE_X, SET_SCREW_Y, 0.0]],
        (0.0, 0.0, -1.0),
        f"rod set-screw tap ({SET_SCREW_TAP_SPEC.size} into the pivot bore)",
        name="SetScrewHole",
        expect_dia_mm=TAP_DRILL_DIA,
        placement_dims=[(("SetScrewX", '"PivotBoreX"'), ("SetScrewY", '"SetScrewY"'))],
    )
    drive_jobs += tap.placement_drive_jobs
    volume = await volume_check(
        adapter, "set-screw tap", volume - V_SET_SCREW_TAP, 0.03 * V_SET_SCREW_TAP
    )

    # 6. The free-end lightening bore: top face (outward normal +Y), through
    # all, opening into the relief.  Placement sketch (x, y) = model (X, Z).
    lightening = wizard_holes(
        adapter,
        LIGHTENING_SPEC,
        [[LIGHTENING_X, BLOCK_HEIGHT, _Z_MID]],
        (0.0, 1.0, 0.0),
        f"free-end lightening bore ({LIGHTENING_SPEC.size} drill)",
        name="LighteningBore",
        expect_dia_mm=LIGHTENING_DIA,
        placement_dims=[
            (("LighteningX", '"LighteningX"'), ("LighteningZ", '"BlockDepth" / 2'))
        ],
    )
    drive_jobs += lightening.placement_drive_jobs
    await volume_check(
        adapter, "lightening bore", volume - V_LIGHTENING, 0.01 * V_LIGHTENING
    )

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves. Each equation evaluates to the value just
    # built, so the geometry must not move -- the re-check below is the proof.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven pen v-block (equations neutral)", V_TOTAL, 0.002 * V_TOTAL
    )

    # Bright brass in every photo: no colour override, the material appearance
    # is the finish.
    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    # Manufacturing drawing support: the pivot band, the authored places, and
    # exactly the print's dimensions marked (the drawing must find every one).
    for (feature_name, dimension_name), band in DRAWING_BANDS.items():
        set_dimension_bilateral_tolerance(
            adapter, feature_name, dimension_name, *deviations(band)
        )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE}
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(
        adapter,
        (
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
