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
  ``VGroove``: the V triangle, its included angle and both mouth edges (each
  from the front face) driving and its apex height a driven reference, cut +X
  from the paper end to ``RELIEF_X0``.
* ``ReliefProfile`` (Top plane, sketch (u, v) = model (X, -Z)) -> ``Relief``:
  the slot from ``RELIEF_X0`` to the free end, both walls stationed from the
  front face, its two step corners the end mill's ``RELIEF_CORNER_R`` arcs,
  cut +Y to the roof.
* ``PivotBoreProfile`` (Top plane) -> ``PivotBore``: the reamed bore, a
  sketched through cut; it removes brass only between the top face and the
  relief roof.  Its diameter carries the H7 band.
* ``PivotBoreChamfer``: 45 deg on the bore's top edge (it clears the rod's
  shoulder-root fillet); ``PivotReference`` prints its size, a single MIN limit.
* ``SetScrewHole``: Hole Wizard #4-40 tap from the front face, up to the
  pivot bore (``through_next``); built after the bore so it stops there.
* ``LighteningBore``: Hole Wizard 5/16 drill from the top face, through all;
  it opens into the relief.
* ``SectionAPlane``: parallel to the Right plane through the pivot-bore axis,
  section A-A's cutting plane (hidden).
* ``ReliefReference`` / ``PivotReference`` (on ``SectionAPlane``) and
  ``LighteningReference`` (Top plane), all hidden: construction chords on
  edges the sheet shows, owning each feature's station across the depth from
  the front face and the relief height from the bottom face to the roof
  (``pn_pen_v_block_spec`` contract).  The section's two lie IN its cutting
  plane (the bond cradle's recipe): the drawing cuts the section while the
  part shows them, which is how a section imports a hidden sketch's dims.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pn_pen_v_block.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _check import check
from _com import _early_bound, _read_member
from _dimensions import drive_dimension, name_dimensions, set_global
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_prefix import set_dimension_prefix
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _feature_tree import _feature_by_name, name_last_feature
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
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _visibility import blank_reference_geometry
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
    REFERENCE_DIMENSIONS,
    REFERENCE_SKETCHES,
    RELIEF_CORNER_R,
    RELIEF_HEIGHT,
    RELIEF_WIDTH,
    RELIEF_X0,
    RELIEF_Z0,
    RELIEF_Z1,
    SET_SCREW_TAP_SPEC,
    SET_SCREW_Y,
    V_ANGLE_DEG,
    V_APEX_Y,
    V_MOUTH_WIDTH,
    V_MOUTH_Z0,
    V_MOUTH_Z1,
)

PART_NAME = "pn-pen-v-block"
MATERIAL = "Brass"  # see _appearance.apply_material docstring

THROUGH_CUT_DEPTH = 80.0  # mid-plane total; > any extent crossed
TAP_DRILL_DIA = TAP_DRILL_MM[SET_SCREW_TAP_SPEC.size]
_Z_MID = BLOCK_DEPTH / 2.0
# Section A-A's cutting plane (the drawing cuts at x = PIVOT_BORE_X): the
# section's reference sketches lie in it.
SECTION_PLANE = "SectionAPlane"
# Length of the pivot reference's two marker chords (front face, bore axis);
# unprinted, short enough to stay on the front face above the set-screw tap.
_STUB = 1.0

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


# Sketch (u, v) of a point inside the V's wedge, under the apex on its axis:
# where the included angle's text goes, which picks the wedge the angle is
# measured in (AddSpecificDimension takes the region holding its text point).
def _v_angle_text_point() -> tuple[float, float]:
    return (-_Z_MID, V_APEX_Y / 2.0)


def _add_driving_v_angle(adapter, flank_a: str, flank_b: str) -> None:
    """The V's included angle between its two flanks, as a DRIVING dimension.

    ``build_dt_cone_pivot_post._add_driving_plan_incline``'s recipe: both
    flanks selected as segments (the adapter's "angular" route selects one
    segment and its vertex and left the farm's first native run, c0b95549c,
    over-defined), the text point inside the wedge, passed as sketch (u, v)
    in the x / y slots and as the model point (Z = -u) in the z slot, so it
    lands in the wedge whichever space SOLIDWORKS reads it in (the Right
    plane's normal, model X, projects away).  The measured value is checked
    before the dimension is made driving.
    """
    from solidworks_mcp.adapters import sw_type_info as _sw_type_info
    from solidworks_mcp.adapters.solidworks.sketch import _select_sketch_entities

    label = "V included angle"
    u, v = (value / 1000.0 for value in _v_angle_text_point())
    model = adapter.currentModel
    model.ClearSelection2(True)
    _select_sketch_entities(adapter, [flank_a, flank_b], 0)
    extension = _sw_type_info.early_bound_or_flag(
        model.Extension, "IModelDocExtension", "AddSpecificDimension"
    )
    display, status = extension.AddSpecificDimension(
        u,
        v,
        -u,
        3,  # swDimensionType_e.swAngularDimension
        0,
    )
    model.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"{label}: AddSpecificDimension(angular) failed ({status})")
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    actual_rad = abs(float(dimension.SystemValue))
    if abs(actual_rad - math.radians(V_ANGLE_DEG)) > 1e-8:
        raise RuntimeError(
            f"{label}: measured {math.degrees(actual_rad):.6f} deg, "
            f"expected {V_ANGLE_DEG:.6f} deg"
        )
    dimension.DrivenState = 2  # swDimensionDrivenState_e.swDimensionDriving
    if int(dimension.DrivenState) != 2:
        raise RuntimeError(f"{label}: angular dimension did not become driving")
    _telemetry.success(f"driving {label}: {V_ANGLE_DEG:g} deg")


def _make_driven(adapter, dimension_id: str, label: str) -> None:
    """Turn a just-made sketch dimension into a DRIVEN (reference) one."""
    display = _early_bound(adapter._sketch_entities[dimension_id], "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    dimension.DrivenState = 1  # swDimensionDrivenState_e.swDimensionDriven
    if int(dimension.DrivenState) != 1:
        raise RuntimeError(f"{label}: dimension did not become driven")


async def _v_groove(adapter, dims: SketchDims) -> None:
    """The V triangle on the Right plane, sketch (u, v) = model (-Z, Y).

    LA runs front mouth -> apex, LB apex -> back mouth, LC back mouth -> front
    mouth along the bottom face.  Relations: LC horizontal, its front mouth on
    the origin's level, LA = LB (the V symmetric about the apex).  Driving
    dims: both mouth edges from the front face (real edges on the bottom face,
    baselines from the face the print locates everything from, so neither is
    chained from the other and the V is not placed by the depth's symmetry)
    and the included angle -- 6 DOF less 3 relations + 3 dims = 0.  The mouth
    width is their difference and the apex height what they leave: a DRIVEN
    dimension the print shows as a reference.  It is made driven before the
    angle exists, so the sketch is never over-defined.
    """
    points = [(-V_MOUTH_Z0, 0.0), (-_Z_MID, V_APEX_Y), (-V_MOUTH_Z1, 0.0)]
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
        V_MOUTH_Z0,
        "V front mouth edge from the front face",
    )
    dims.record("VMouthZ0", '"VMouthFrontZ"')
    apex = await dimension_between(
        adapter,
        f"{flank_a}.end",
        "origin",
        "vertical_distance",
        V_APEX_Y,
        "V apex height",
    )
    _make_driven(adapter, apex, "V apex height")
    dims.record("VApexY")
    await dimension_between(
        adapter,
        f"{flank_b}.end",
        "origin",
        "horizontal_distance",
        V_MOUTH_Z1,
        "V back mouth edge from the front face",
    )
    dims.record("VMouthZ1", '"VMouthBackZ"')
    _add_driving_v_angle(adapter, flank_a, flank_b)
    dims.record("VAngle", '"VAngle"')


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


def _plane_frame(adapter, name: str) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """(rotation, origin mm) of a reference plane, read back from
    ``IRefPlane::Transform`` (diag_build_1330K524._plane_frame's layout:
    nine rotation doubles, then the translation in metres)."""
    feature = _early_bound(_feature_by_name(adapter, name), "IFeature")
    plane = _early_bound(feature.GetSpecificFeature2(), "IRefPlane")
    data = [
        float(v) for v in _read_member(_read_member(plane, "Transform"), "ArrayData")
    ]
    return tuple(data[0:9]), tuple(v * 1000.0 for v in data[9:12])


async def _section_plane(adapter) -> None:
    """Section A-A's cutting plane: the Right plane carried +X to the pivot-bore
    axis.  Read back against the Right plane: the same rotation (so a sketch on
    it keeps the Right plane's (u, v) = model (-Z, Y)) and an origin shifted by
    exactly PIVOT_BORE_X along +X; anything else raises before a chord is laid.
    """
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    check(
        f"create plane {SECTION_PLANE}",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Right Plane", offset=PIVOT_BORE_X
            )
        ),
    )
    name_last_feature(adapter, SECTION_PLANE)
    right_rotation, right_origin = _plane_frame(adapter, "Right Plane")
    rotation, origin = _plane_frame(adapter, SECTION_PLANE)
    shift = tuple(o - r for o, r in zip(origin, right_origin))
    if any(abs(a - b) > 1e-9 for a, b in zip(rotation, right_rotation)) or any(
        abs(s - e) > 1e-6 for s, e in zip(shift, (PIVOT_BORE_X, 0.0, 0.0))
    ):
        raise RuntimeError(
            f"{SECTION_PLANE}: rotation {rotation} / origin shift {shift} mm, "
            f"expected the Right plane's {right_rotation} shifted "
            f"({PIVOT_BORE_X}, 0, 0)"
        )


def _require_on_section_plane(adapter, sketch: str) -> None:
    """create_sketch falls back to a standard plane when a named one fails to
    select; the sketch's parents must name SECTION_PLANE."""
    feature = _early_bound(_feature_by_name(adapter, sketch), "IFeature")
    parents = [
        str(_early_bound(parent, "IFeature").Name)
        for parent in (feature.GetParents() or ())
    ]
    if SECTION_PLANE not in parents:
        raise RuntimeError(f"{sketch} is not on {SECTION_PLANE}: parents {parents}")


async def _relief_reference(adapter) -> list[tuple[str, str]]:
    """The relief's depth-wise walls and height in section A-A.

    On SECTION_PLANE, sketch (u, v) = model (-Z, Y), construction only and
    hidden.  The relief is cut from a Top-plane profile whose stations across
    the depth project edge-on in the section, and its cut depth is a vector
    that ends in air.  A shown reference sketch prints, so its chords lie only
    on the section's own edges, never across the open mouth: the near wall
    from its foot to the roof, its foot from the origin, the front face's foot
    (ReliefZ0), and the far wall, whose foot is ReliefZ1 from the same origin
    (a baseline, not chained from the near wall) and whose height is the
    printed ReliefHeight (the section draws the far wall on its right, outside
    the stations under it).  2 x 4 DOF less the near foot's level, both chords
    vertical, the far foot's level (4) and 4 dims = 0.
    """
    feature = "ReliefReference"
    z0, z1 = RELIEF_Z0, RELIEF_Z1
    check(f"create sketch {feature}", await adapter.create_sketch(SECTION_PLANE))
    near = await _construction_chord(adapter, feature, (-z0, 0.0), (-z0, RELIEF_HEIGHT))
    await anchor_point_to_origin(
        adapter, f"{near}.start", -z0, 0.0, f"{feature} near wall foot"
    )
    check(feature, await adapter.add_sketch_constraint(near, None, "vertical"))
    await dimension_between(
        adapter,
        f"{near}.start",
        f"{near}.end",
        "vertical_distance",
        RELIEF_HEIGHT,
        f"{feature} height",
    )
    far = await _construction_chord(adapter, feature, (-z1, 0.0), (-z1, RELIEF_HEIGHT))
    check(
        feature,
        await adapter.add_sketch_constraint(
            f"{far}.start", f"{near}.start", "horizontal_points"
        ),
    )
    await dimension_between(
        adapter,
        f"{far}.start",
        "origin",
        "horizontal_distance",
        z1,
        f"{feature} far wall from the front face",
    )
    check(feature, await adapter.add_sketch_constraint(far, None, "vertical"))
    await dimension_between(
        adapter,
        f"{far}.start",
        f"{far}.end",
        "vertical_distance",
        RELIEF_HEIGHT,
        f"{feature} far wall",
    )
    await ensure_fully_defined(adapter, feature)
    check(f"exit sketch {feature}", await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    _require_on_section_plane(adapter, feature)
    z0_name, near_wall, z1_name, height = name_dimensions(
        adapter, feature, ["ReliefZ0", "ReliefNearWall", "ReliefZ1", "ReliefHeight"]
    )
    return [
        (z0_name, '"ReliefFrontZ"'),
        (near_wall, '"ReliefHeight"'),
        (z1_name, '"ReliefBackZ"'),
        (height, '"ReliefHeight"'),
    ]


async def _pivot_reference(adapter) -> list[tuple[str, str]]:
    """The pivot bore's depth-wise station and top chamfer, in section A-A.

    On SECTION_PLANE, sketch (u, v) = model (-Z, Y), construction only and
    hidden.  The bore's own Top-plane station projects edge-on in the section.
    A shown reference sketch prints, so no chord crosses the bore's open
    mouth: a _STUB chord down the front face from its top edge, another down
    the bore axis (the section's centreline) from the top face, PivotZ between
    their tops; and the chamfer's face on the bore's FAR (z 11) side, from its
    rim on the top face to its foot on the bore wall, whose run is the printed
    chamfer size (its extension lines rise from the chamfer's own vertices,
    clear of PivotZ's span).  3 x 4 DOF less: the front top on the origin's
    vertical, both stubs vertical, the axis top and the rim level with the
    front top (5); and 7 dims (station, two stub lengths, PivotZ, the foot's
    offset from the axis, run, drop) = 0.
    """
    feature = "PivotReference"
    radius = PIVOT_BORE_DIA / 2.0
    chamfer = PIVOT_BORE_TOP_CHAMFER
    top = BLOCK_HEIGHT
    check(f"create sketch {feature}", await adapter.create_sketch(SECTION_PLANE))
    front = await _construction_chord(adapter, feature, (0.0, top), (0.0, top - _STUB))
    await anchor_point_to_origin(
        adapter, f"{front}.start", 0.0, top, f"{feature} front face top edge"
    )
    check(feature, await adapter.add_sketch_constraint(front, None, "vertical"))
    await dimension_between(
        adapter,
        f"{front}.start",
        f"{front}.end",
        "vertical_distance",
        _STUB,
        f"{feature} front stub",
    )
    axis = await _construction_chord(
        adapter, feature, (-_Z_MID, top), (-_Z_MID, top - _STUB)
    )
    check(
        feature,
        await adapter.add_sketch_constraint(
            f"{axis}.start", f"{front}.start", "horizontal_points"
        ),
    )
    await dimension_between(
        adapter,
        f"{front}.start",
        f"{axis}.start",
        "horizontal_distance",
        _Z_MID,
        f"{feature} bore axis from the front face",
    )
    check(feature, await adapter.add_sketch_constraint(axis, None, "vertical"))
    await dimension_between(
        adapter,
        f"{axis}.start",
        f"{axis}.end",
        "vertical_distance",
        _STUB,
        f"{feature} axis stub",
    )
    leg = await _construction_chord(
        adapter,
        feature,
        (-(_Z_MID + radius + chamfer), top),
        (-(_Z_MID + radius), top - chamfer),
    )
    check(
        feature,
        await adapter.add_sketch_constraint(
            f"{leg}.start", f"{front}.start", "horizontal_points"
        ),
    )
    await dimension_between(
        adapter,
        f"{leg}.end",
        f"{axis}.start",
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
    _require_on_section_plane(adapter, feature)
    # The stubs' lengths are fixed: nothing in the part sets them.
    station, _, pivot_z, _, bore_r, run, drop = name_dimensions(
        adapter,
        feature,
        [
            "PivotStation",
            "PivotFrontStub",
            "PivotZ",
            "PivotAxisStub",
            "PivotChamferBoreR",
            "PivotChamferSize",
            "PivotChamferDrop",
        ],
    )
    return [
        (station, '"BlockHeight"'),
        (pivot_z, '"BlockDepth" / 2'),
        (bore_r, '"PivotBoreDia" / 2'),
        (run, '"PivotChamfer"'),
        (drop, '"PivotChamfer"'),
    ]


async def _lightening_reference(adapter) -> list[tuple[str, str]]:
    """The lightening bore's depth-wise station from the front face.

    Top plane (the bottom face), sketch (u, v) = model (X, -Z), construction
    only and hidden.  The bore's own placement dimension runs to the placement
    sketch's origin, the paper end's front corner, so in the bottom view its
    extension line would lie along the whole front edge.  A shown reference
    sketch prints, so its chords lie on what the bottom view already draws:
    one up the free end's edge from its front corner to the bore's level
    (LighteningZ: extension lines from that corner and that level), one along
    the bore's centreline from there to its centre.  2 x 4 DOF less the
    corner on the origin's level, both chords' directions, the shared point
    (2) and 3 dims (the corner's station, LighteningZ, the run) = 0.
    """
    feature = "LighteningReference"
    check(f"create sketch {feature}", await adapter.create_sketch("Top"))
    edge = await _construction_chord(
        adapter, feature, (BLOCK_LENGTH, 0.0), (BLOCK_LENGTH, -_Z_MID)
    )
    await anchor_point_to_origin(
        adapter, f"{edge}.start", BLOCK_LENGTH, 0.0, f"{feature} free-end corner"
    )
    check(feature, await adapter.add_sketch_constraint(edge, None, "vertical"))
    await dimension_between(
        adapter,
        f"{edge}.start",
        f"{edge}.end",
        "vertical_distance",
        _Z_MID,
        f"{feature} bore level from the front face",
    )
    centre = await _construction_chord(
        adapter, feature, (BLOCK_LENGTH, -_Z_MID), (LIGHTENING_X, -_Z_MID)
    )
    check(
        feature,
        await adapter.add_sketch_constraint(
            f"{centre}.start", f"{edge}.end", "coincident"
        ),
    )
    check(feature, await adapter.add_sketch_constraint(centre, None, "horizontal"))
    await dimension_between(
        adapter,
        f"{centre}.start",
        f"{centre}.end",
        "horizontal_distance",
        BLOCK_LENGTH - LIGHTENING_X,
        f"{feature} bore from the free end",
    )
    await ensure_fully_defined(adapter, feature)
    check(f"exit sketch {feature}", await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    corner, lightening_z, run = name_dimensions(
        adapter, feature, ["LighteningFreeEnd", "LighteningZ", "LighteningRun"]
    )
    return [
        (corner, '"BlockLength"'),
        (lightening_z, '"BlockDepth" / 2'),
        (run, '"BlockLength" - "LighteningX"'),
    ]


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


def _author_reference_dimensions(adapter) -> None:
    """Show each driven dimension as a reference: no tolerance, "(6.0)"
    (build_ms_stop_block._author_plate_location_references' recipe)."""
    for feature_name, dimension_name in REFERENCE_DIMENSIONS:
        display, dimension = _named_dimension(adapter, feature_name, dimension_name)
        label = f"{dimension_name}@{feature_name}"
        if int(dimension.DrivenState) != 1:
            raise RuntimeError(f"{label}: a reference dimension must be driven")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        tolerance.Type = 0  # swTolType_e.swTolNONE; property put, no success retval
        # The native prefix/suffix channel around the live model value, not
        # ShowParenthesis (which brackets above-line text).
        display.SetText(1, "(")
        display.SetText(2, ")")
        if (
            int(tolerance.Type) != 0
            or (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
            != ("(", ")")
            or not bool(display.ShowDimensionValue)
        ):
            raise RuntimeError(f"{label}: reference display did not persist")


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
        ("VMouthFrontZ", V_MOUTH_Z0),
        ("VMouthBackZ", V_MOUTH_Z1),
        ("ReliefX0", RELIEF_X0),
        ("ReliefFrontZ", RELIEF_Z0),
        ("ReliefBackZ", RELIEF_Z1),
        ("ReliefHeight", RELIEF_HEIGHT),
        ("ReliefCornerR", RELIEF_CORNER_R),
        ("PivotBoreX", PIVOT_BORE_X),
        ("PivotBoreDia", PIVOT_BORE_DIA),
        ("PivotChamfer", PIVOT_BORE_TOP_CHAMFER),
        ("SetScrewY", SET_SCREW_Y),
        ("LighteningX", LIGHTENING_X),
    ):
        await set_global(adapter, name, f"{value}mm")
    # The V's included angle drives its sketch (degrees, not mm).
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
    # Sketch (u, v) = model (X, -Z).  Drawn counter-clockwise (add_arc runs
    # counter-clockwise start -> end) from the back wall's tangent point: back
    # wall to the free end, the free end, the front wall back to the step,
    # then the step between the two end-mill corner arcs, whose centres stand
    # one radius into the slot.  Exact-coordinate endpoints merge in the
    # sketch DB (inference off).  The front-face corner's radius is the one
    # the sheet prints ("2X"); the back one is driven by the same global.
    relief = SketchDims()
    check("create_sketch relief", await adapter.create_sketch("Top"))
    z0, z1 = RELIEF_Z0, RELIEF_Z1
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
    # The back wall from the front face, a baseline like the front wall's
    # below: neither wall is chained from the other.
    await dimension_between(
        adapter,
        f"{back}.start",
        "origin",
        "vertical_distance",
        z1,
        "relief back wall from the front face",
    )
    relief.record("ReliefZ1", '"ReliefBackZ"')
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
    relief.record("ReliefZ0", '"ReliefFrontZ"')
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
    await _section_plane(adapter)
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
    _author_reference_dimensions(adapter)
    for (feature_name, dimension_name), prefix in DIMENSION_PREFIXES.items():
        set_dimension_prefix(adapter, feature_name, dimension_name, prefix)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # Saved hidden: the drawing shows them per view (_drawing_hidden_sketches).
    blank_reference_sketches(adapter, REFERENCE_SKETCHES)
    blank_reference_geometry(adapter, ((SECTION_PLANE, "PLANE"),))
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
