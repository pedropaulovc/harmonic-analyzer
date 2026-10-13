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
  the slot from ``RELIEF_X0`` to the free end, its two step corners the end
  mill's ``RELIEF_CORNER_R`` arcs, cut +Y to the roof.
* ``PivotBoreProfile`` (Top plane) -> ``PivotBore``: the reamed bore, a
  sketched through cut; it removes brass only between the top face and the
  relief roof.  Its diameter carries the H7 band.
* ``PivotBoreChamfer``: 45 deg on the bore's top edge (it clears the rod's
  shoulder-root fillet); ``PivotReference`` prints its size, a single MIN limit.
* ``SetScrewHole``: Hole Wizard #4-40 tap from the front face, up to the
  pivot bore (``through_next``); built after the bore so it stops there.
* ``LighteningBore``: Hole Wizard 5/16 drill from the top face, through all;
  it opens into the relief.
* ``ReliefReference`` / ``PivotReference`` (Right plane) and
  ``LighteningReference`` (Top plane), all hidden: construction chords owning
  each feature's station across the depth from the front face, and the relief
  height from the bottom face to the roof, on edges the sheet shows
  (``pn_pen_v_block_spec`` contract).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pn_pen_v_block.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_prefix import set_dimension_prefix
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
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _visibility import blank_sketch_feature
import _telemetry
from pn_pen_v_block_spec import (
    BLOCK_DEPTH,
    BLOCK_HEIGHT,
    BLOCK_LENGTH,
    CHAMFER,
    DIMENSION_PREFIXES,
    DRAWING_BANDS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    LIGHTENING_DIA,
    LIGHTENING_SPEC,
    LIGHTENING_X,
    PIVOT_BORE_DIA,
    PIVOT_BORE_TOP_CHAMFER,
    PIVOT_BORE_X,
    PIVOT_CHAMFER_BAND,
    PIVOT_CHAMFER_TOL_TYPE,
    RELIEF_CORNER_R,
    RELIEF_HEIGHT,
    RELIEF_WIDTH,
    RELIEF_X0,
    SET_SCREW_TAP_SPEC,
    SET_SCREW_Y,
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
# Each step corner leaves its R x R square less the quarter disc standing.
V_RELIEF_CORNERS = 2.0 * (1.0 - math.pi / 4.0) * RELIEF_CORNER_R**2 * RELIEF_HEIGHT
V_RELIEF = RELIEF_WIDTH * RELIEF_HEIGHT * (BLOCK_LENGTH - RELIEF_X0) - V_RELIEF_CORNERS
# Both vertical bores remove brass only from the relief roof to the top face.
V_PIVOT_BORE = math.pi * (PIVOT_BORE_DIA / 2.0) ** 2 * (BLOCK_HEIGHT - RELIEF_HEIGHT)
# A 45 deg chamfer of leg c round a bore of radius r: the c x c / 2 triangle
# swept about the axis at its centroid's radius r + c / 3.
V_PIVOT_CHAMFER = (
    math.pi
    * PIVOT_BORE_TOP_CHAMFER**2
    * (PIVOT_BORE_DIA / 2.0 + PIVOT_BORE_TOP_CHAMFER / 3.0)
)
# The tap runs from the front face to where its whole profile is inside the
# bore: the drill cylinder to the bore axis less its near half of the
# drill-through-bore intersection (already void).
V_SET_SCREW_TAP = (
    math.pi * (TAP_DRILL_DIA / 2.0) ** 2 * _Z_MID
    - cross_hole_volume_mm3(TAP_DRILL_DIA, PIVOT_BORE_DIA) / 2.0
)
V_LIGHTENING = math.pi * (LIGHTENING_DIA / 2.0) ** 2 * (BLOCK_HEIGHT - RELIEF_HEIGHT)
V_TOTAL = (
    V_BLOCK
    - V_GROOVE
    - V_RELIEF
    - V_PIVOT_BORE
    - V_PIVOT_CHAMFER
    - V_SET_SCREW_TAP
    - V_LIGHTENING
)


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
    front mouth edge from the front face (a real edge on the bottom face, so
    the V is located from the front face, not by the depth's symmetry), the
    apex above the bottom, and the mouth width (which with the apex height
    sets the included angle) -- 6 DOF less 3 relations + 3 dims = 0.  The
    mouth is a point-pair distance, not an adapter "angular" dimension: that
    one selects a segment and its vertex, dimensions the flank against the
    sketch axes, and left the farm's first native run (c0b95549c)
    over-defined ('no_solution').
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
        f"{flank_a}.start",
        "origin",
        "horizontal_distance",
        _Z_MID - half,
        "V front mouth from the front face",
    )
    dims.record("VMouthZ", '("BlockDepth" - "VMouth") / 2')
    await dimension_between(
        adapter,
        f"{flank_a}.end",
        "origin",
        "vertical_distance",
        V_APEX_Y,
        "V apex height",
    )
    dims.record("VApexY", '"VApexY"')
    await dimension_between(
        adapter,
        f"{flank_a}.start",
        f"{flank_b}.end",
        "horizontal_distance",
        V_MOUTH_WIDTH,
        "V mouth width",
    )
    dims.record("VMouth", '"VMouth"')


async def _construction_chord(
    adapter, feature: str, start: tuple[float, float], end: tuple[float, float]
) -> str:
    """One construction line, placed with inference off (ms_stop_geom recipe)."""
    set_sketch_direct_db(adapter, True)
    line = check(feature, await adapter.add_line(*start, *end))
    set_sketch_direct_db(adapter, False)
    segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not segment.ConstructionGeometry:
        raise RuntimeError(f"{feature}: construction flag rejected")
    return line


async def _relief_reference(adapter) -> list[tuple[str, str]]:
    """The relief's depth-wise location, width and height on section A-A's edges.

    Right plane, sketch (u, v) = model (-Z, Y), construction only and hidden
    after marking.  The relief is cut from a Top-plane profile, whose stations
    across the depth project edge-on in the section, and its cut depth is a
    vector from the bottom-face plane that ends in air.  These chords sit on
    the section's real edges instead: the mouth chord along the bottom face
    from the near wall's foot to the far wall's (ReliefWidth), anchored to the
    front face's foot (ReliefZ0, the origin), and the wall chord up the near
    wall from its foot to the roof (ReliefHeight).  4 + 4 DOF less horizontal,
    on-level, vertical and the shared foot (1 + 1 + 1 + 2) and 3 dims = 0.
    """
    feature = "ReliefReference"
    z0 = (BLOCK_DEPTH - RELIEF_WIDTH) / 2.0
    check(f"create sketch {feature}", await adapter.create_sketch("Right"))
    mouth = await _construction_chord(
        adapter, feature, (-z0, 0.0), (-(z0 + RELIEF_WIDTH), 0.0)
    )
    check(feature, await adapter.add_sketch_constraint(mouth, None, "horizontal"))
    await dimension_between(
        adapter,
        f"{mouth}.start",
        f"{mouth}.end",
        "horizontal_distance",
        RELIEF_WIDTH,
        f"{feature} width",
    )
    await anchor_point_to_origin(
        adapter, f"{mouth}.start", -z0, 0.0, f"{feature} near wall foot"
    )
    wall = await _construction_chord(adapter, feature, (-z0, 0.0), (-z0, RELIEF_HEIGHT))
    check(feature, await adapter.add_sketch_constraint(wall, None, "vertical"))
    check(
        feature,
        await adapter.add_sketch_constraint(
            f"{wall}.start", f"{mouth}.start", "coincident"
        ),
    )
    await dimension_between(
        adapter,
        f"{wall}.start",
        f"{wall}.end",
        "vertical_distance",
        RELIEF_HEIGHT,
        f"{feature} height",
    )
    await ensure_fully_defined(adapter, feature)
    check(f"exit sketch {feature}", await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    width, z0_name, height = name_dimensions(
        adapter, feature, ["ReliefWidth", "ReliefZ0", "ReliefHeight"]
    )
    return [
        (width, '"ReliefWidth"'),
        (z0_name, '("BlockDepth" - "ReliefWidth") / 2'),
        (height, '"ReliefHeight"'),
    ]


async def _pivot_reference(adapter) -> list[tuple[str, str]]:
    """The pivot bore's depth-wise station and top chamfer, in section A-A.

    Right plane, sketch (u, v) = model (-Z, Y), construction only and hidden
    after marking.  The bore's own Top-plane station projects edge-on in the
    section; the first chord runs along the top face from the front face's
    top edge to the bore axis (the section's centreline), its height on the
    top face held by an unprinted station dim.  The second is the chamfer's
    face on the bore's FAR (z 11) side, from its rim on the top face to its
    foot on the bore wall: its run is the printed chamfer size, so the
    extension lines rise from the chamfer's own vertices left of the bore
    axis, clear of PivotZ (the chamfer feature's dimension could attach on
    either side).  4 + 4 DOF less horizontal, the start on the origin's
    vertical and 2 dims (span, station); less the rim on the top-face level,
    the foot's offset from the axis (the bore radius), and the run and drop
    = 0.
    """
    feature = "PivotReference"
    radius = PIVOT_BORE_DIA / 2.0
    chamfer = PIVOT_BORE_TOP_CHAMFER
    check(f"create sketch {feature}", await adapter.create_sketch("Right"))
    chord = await _construction_chord(
        adapter, feature, (0.0, BLOCK_HEIGHT), (-_Z_MID, BLOCK_HEIGHT)
    )
    check(feature, await adapter.add_sketch_constraint(chord, None, "horizontal"))
    await dimension_between(
        adapter,
        f"{chord}.start",
        f"{chord}.end",
        "horizontal_distance",
        _Z_MID,
        f"{feature} bore axis from the front face",
    )
    await anchor_point_to_origin(
        adapter, f"{chord}.start", 0.0, BLOCK_HEIGHT, f"{feature} top-face station"
    )
    leg = await _construction_chord(
        adapter,
        feature,
        (-(_Z_MID + radius + chamfer), BLOCK_HEIGHT),
        (-(_Z_MID + radius), BLOCK_HEIGHT - chamfer),
    )
    check(
        feature,
        await adapter.add_sketch_constraint(
            f"{leg}.start", f"{chord}.start", "horizontal_points"
        ),
    )
    await dimension_between(
        adapter,
        f"{leg}.end",
        f"{chord}.end",
        "horizontal_distance",
        radius,
        f"{feature} chamfer foot on the bore wall",
    )
    await dimension_between(
        adapter,
        f"{leg}.start",
        f"{leg}.end",
        "horizontal_distance",
        chamfer,
        f"{feature} chamfer run",
    )
    await dimension_between(
        adapter,
        f"{leg}.start",
        f"{leg}.end",
        "vertical_distance",
        chamfer,
        f"{feature} chamfer drop",
    )
    await ensure_fully_defined(adapter, feature)
    check(f"exit sketch {feature}", await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    pivot_z, station, bore_r, run, drop = name_dimensions(
        adapter,
        feature,
        [
            "PivotZ",
            "PivotStation",
            "PivotChamferBoreR",
            "PivotChamferSize",
            "PivotChamferDrop",
        ],
    )
    return [
        (pivot_z, '"BlockDepth" / 2'),
        (station, '"BlockHeight"'),
        (bore_r, '"PivotBoreDia" / 2'),
        (run, '"PivotChamfer"'),
        (drop, '"PivotChamfer"'),
    ]


async def _lightening_reference(adapter) -> list[tuple[str, str]]:
    """The lightening bore's depth-wise station from the front face.

    Top plane (the bottom face), sketch (u, v) = model (X, -Z), construction
    only and hidden after marking.  The bore's own placement dimension runs to
    the placement sketch's origin, the paper end's front corner, so in the
    bottom view its extension line would lie along the whole front edge.  This
    chord runs from the free end's front corner (a real vertex there) to the
    bore's centre, so LighteningZ's extension lines leave that corner and the
    centre mark.  4 DOF less the start on the origin's level and 3 dims (the
    corner's station, and the chord's run and drop) = 0.
    """
    feature = "LighteningReference"
    check(f"create sketch {feature}", await adapter.create_sketch("Top"))
    chord = await _construction_chord(
        adapter, feature, (BLOCK_LENGTH, 0.0), (LIGHTENING_X, -_Z_MID)
    )
    await anchor_point_to_origin(
        adapter, f"{chord}.start", BLOCK_LENGTH, 0.0, f"{feature} free-end corner"
    )
    await dimension_between(
        adapter,
        f"{chord}.start",
        f"{chord}.end",
        "horizontal_distance",
        BLOCK_LENGTH - LIGHTENING_X,
        f"{feature} bore from the free end",
    )
    await dimension_between(
        adapter,
        f"{chord}.start",
        f"{chord}.end",
        "vertical_distance",
        _Z_MID,
        f"{feature} bore from the front face",
    )
    await ensure_fully_defined(adapter, feature)
    check(f"exit sketch {feature}", await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    corner, run, drop = name_dimensions(
        adapter, feature, ["LighteningFreeEnd", "LighteningRun", "LighteningZ"]
    )
    return [
        (corner, '"BlockLength"'),
        (run, '"BlockLength" - "LighteningX"'),
        (drop, '"BlockDepth" / 2'),
    ]


def _hide_references(adapter) -> None:
    """Blank the reference sketches once their dimensions are marked."""
    model = _early_bound(adapter.currentModel, "IPartDoc")
    for name in ("ReliefReference", "PivotReference", "LighteningReference"):
        feature = model.FeatureByName(name)
        if feature is None:
            raise RuntimeError(f"missing pen v-block reference sketch {name}")
        blank_sketch_feature(
            adapter.currentModel, _early_bound(feature, "IFeature"), name
        )


def _pivot_chamfer_min_limit(adapter) -> None:
    """PivotChamferSize as a MIN single limit carrying the band's deviations
    (build_pn_pen_rod._shoulder_fillet_max_limit's recipe, MIN for MAX)."""
    lower, upper = deviations(PIVOT_CHAMFER_BAND)
    _, dimension = _named_dimension(adapter, "PivotReference", "PivotChamferSize")
    label = "PivotChamferSize@PivotReference"
    value = float(dimension.SystemValue)
    if not math.isclose(value, PIVOT_BORE_TOP_CHAMFER / 1000.0, abs_tol=1e-9):
        raise RuntimeError(
            f"{label}: nominal {value * 1000.0:.7f} is not the band's min "
            f"{PIVOT_BORE_TOP_CHAMFER}"
        )
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = PIVOT_CHAMFER_TOL_TYPE
    if not tolerance.SetValues(lower / 1000.0, upper / 1000.0):
        raise RuntimeError(f"{label}: SetValues rejected {lower:+g}/{upper:+g} mm")
    if (
        int(tolerance.Type) != PIVOT_CHAMFER_TOL_TYPE
        or not math.isclose(
            float(tolerance.GetMinValue()), lower / 1000.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), upper / 1000.0, abs_tol=1e-12
        )
    ):
        raise RuntimeError(f"{label}: MIN-limit tolerance readback changed")
    _telemetry.success(f"{label}: single limit {PIVOT_BORE_TOP_CHAMFER:g} MIN")


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
        ("VMouth", V_MOUTH_WIDTH),
        ("ReliefX0", RELIEF_X0),
        ("ReliefWidth", RELIEF_WIDTH),
        ("ReliefHeight", RELIEF_HEIGHT),
        ("ReliefCornerR", RELIEF_CORNER_R),
        ("PivotBoreX", PIVOT_BORE_X),
        ("PivotBoreDia", PIVOT_BORE_DIA),
        ("PivotChamfer", PIVOT_BORE_TOP_CHAMFER),
        ("SetScrewY", SET_SCREW_Y),
        ("LighteningX", LIGHTENING_X),
    ):
        await set_global(adapter, name, f"{value}mm")

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
    # Sketch (u, v) = model (X, -Z).  Drawn counter-clockwise (add_arc runs
    # counter-clockwise start -> end) from the back wall's tangent point: back
    # wall to the free end, the free end, the front wall back to the step,
    # then the step between the two end-mill corner arcs, whose centres stand
    # one radius into the slot.  Exact-coordinate endpoints merge in the
    # sketch DB (inference off).  The front-face corner's radius is the one
    # the sheet prints ("2X"); the back one is driven by the same global.
    relief = SketchDims()
    check("create_sketch relief", await adapter.create_sketch("Top"))
    z0 = (BLOCK_DEPTH - RELIEF_WIDTH) / 2.0
    z1 = z0 + RELIEF_WIDTH
    corner_r = RELIEF_CORNER_R
    x1 = RELIEF_X0 + corner_r
    set_sketch_direct_db(adapter, True)
    back = check("relief back wall", await adapter.add_line(x1, -z1, BLOCK_LENGTH, -z1))
    free_end = check(
        "relief free end",
        await adapter.add_line(BLOCK_LENGTH, -z1, BLOCK_LENGTH, -z0),
    )
    front = check(
        "relief front wall", await adapter.add_line(BLOCK_LENGTH, -z0, x1, -z0)
    )
    front_corner = check(
        "relief front corner",
        await adapter.add_arc(
            x1, -(z0 + corner_r), x1, -z0, RELIEF_X0, -(z0 + corner_r)
        ),
    )
    step = check(
        "relief step",
        await adapter.add_line(
            RELIEF_X0, -(z0 + corner_r), RELIEF_X0, -(z1 - corner_r)
        ),
    )
    back_corner = check(
        "relief back corner",
        await adapter.add_arc(
            x1, -(z1 - corner_r), RELIEF_X0, -(z1 - corner_r), x1, -z1
        ),
    )
    set_sketch_direct_db(adapter, False)
    for label, first, second, relation in (
        ("relief back wall horizontal", back, None, "horizontal"),
        ("relief front wall horizontal", front, None, "horizontal"),
        ("relief free end vertical", free_end, None, "vertical"),
        ("relief step vertical", step, None, "vertical"),
        ("relief front corner tangent wall", front_corner, front, "tangent"),
        ("relief front corner tangent step", front_corner, step, "tangent"),
        ("relief back corner tangent step", back_corner, step, "tangent"),
        ("relief back corner tangent wall", back_corner, back, "tangent"),
    ):
        check(label, await adapter.add_sketch_constraint(first, second, relation))
    await dimension_between(
        adapter,
        f"{step}.start",
        f"{free_end}.start",
        "horizontal_distance",
        BLOCK_LENGTH - RELIEF_X0,
        "relief length",
    )
    relief.record("ReliefLength", '"BlockLength" - "ReliefX0"')
    check(
        "relief width",
        await adapter.add_sketch_dimension(free_end, None, "linear", RELIEF_WIDTH),
    )
    relief.record("ReliefWidth", '"ReliefWidth"')
    # The station runs from the paper end to the step's far (z 14.5) end, so
    # its extension line leaves the step's own edge, not the corner arc.
    await dimension_between(
        adapter,
        f"{step}.end",
        "origin",
        "horizontal_distance",
        RELIEF_X0,
        "relief start station",
    )
    relief.record("ReliefX0", '"ReliefX0"')
    await dimension_between(
        adapter,
        f"{front}.start",
        "origin",
        "vertical_distance",
        z0,
        "relief front wall from the front face",
    )
    relief.record("ReliefZ0", '("BlockDepth" - "ReliefWidth") / 2')
    for name, arc in (
        ("ReliefCornerR", front_corner),
        ("OtherReliefCornerR", back_corner),
    ):
        check(
            f"{name} radius",
            await adapter.add_sketch_dimension(arc, None, "radial", corner_r),
        )
        relief.record(name, '"ReliefCornerR"')
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

    # 4b. The bore's top-edge chamfer, where the rod's square shoulder seats:
    # it clears the rod's shoulder-root fillet.  Picked on the bore's top
    # circular edge at +X, the only edge through that point.
    check(
        "chamfer pivot bore top edge",
        await adapter.add_chamfer(
            PIVOT_BORE_TOP_CHAMFER,
            [[PIVOT_BORE_X + PIVOT_BORE_DIA / 2.0, BLOCK_HEIGHT, _Z_MID]],
        ),
    )
    name_last_feature(adapter, "PivotBoreChamfer")
    chamfer_dims = name_dimensions(
        adapter, "PivotBoreChamfer", ["PivotChamferDistance", "PivotChamferAngle"]
    )
    drive_jobs.append((chamfer_dims[0], '"PivotChamfer"'))
    volume = await volume_check(
        adapter,
        "pivot-bore chamfer",
        volume - V_PIVOT_CHAMFER,
        0.1 * V_PIVOT_CHAMFER + 0.05,
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

    # 7. The hidden depth-wise references the sheet prints (no solid change).
    drive_jobs += await _relief_reference(adapter)
    drive_jobs += await _pivot_reference(adapter)
    drive_jobs += await _lightening_reference(adapter)

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
    _pivot_chamfer_min_limit(adapter)
    for (feature_name, dimension_name), prefix in DIMENSION_PREFIXES.items():
        set_dimension_prefix(adapter, feature_name, dimension_name, prefix)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    _hide_references(adapter)
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
