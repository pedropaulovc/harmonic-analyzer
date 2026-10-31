r"""Reproduction script: fulcrum-shaft end keeper (book ch. 17 p. 40; 2 used).

The black bracket at each end of the top-lever fulcrum shaft (ch. 17 p. 40
bottom-left closeup and p. 2 img08; ch. 30 top view corners + eight-views
p008): a stubby straight L. The upright round-topped lug sits against the
outermost lever hub and carries the plain Ø6.35 fulcrum shaft in a reamed
bore, the shaft's domed end proud of its outer face; a #1-72 cup-point set
screw (MHA-CH-VN-55) in the crown tap bears on the shaft's flat and fixes it.
The short straight foot points OUTBOARD and is screwed down into the
top-frame rail top face by one slotted #2-56 fillister frame-side
screw (MHA-CH-VN-52) seated flush in a counterbore; the foot-to-lug inside
corner is filleted at the title block's INSIDE CORNERS ceiling
(``CornerFillet``).

Layout (part frame): +X along the shaft, OUTBOARD (away from the lever
bank; the lug mid-plane / set-screw axis is x = 0); +Y up from the seat
(y = 0 lands on the rail top face, machine 1036.2); +Z across the 14 width.
The lug spans x -4..+4 from the seat up; the foot runs outboard from the
lug's outer face to x = +12.5, and the whole underside x -4..+12.5 is the
flat seat.

One part serves both ends: the assembly places the +Z (rear) end keeper
part-X -> machine +Z and the front keeper flipped Ry180.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_fulcrum_keeper.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _appearance import PANEL_BLACK, apply_color, apply_material
from _check import check
from _com import _early_bound, _read_member
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_rectilinear_chain
from _sketch_circle import define_circle
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _fit_deviations import deviations
from _hole_spec import blind_cut_dia_mm
from _holes import cross_hole_volume_mm3, wizard_hole_on_cylinder, wizard_holes
from ch_vn_frame_side_screw_spec import HEAD_DIA as FRAME_SIDE_HEAD_DIA
from ch_vn_frame_side_screw_spec import HEAD_H as FRAME_SIDE_HEAD_H
from ch_vn_frame_side_screw_spec import SHANK_DIA as FRAME_SIDE_SHANK_DIA
from ch_vn_frame_side_screw_spec import THREAD as FRAME_SIDE_THREAD
from ch_fulcrum_keeper_spec import (
    BORE_DIA,
    BORE_DIA_BAND,
    BORE_FROM_SIDE,
    CBORE_DEPTH_MM,
    CBORE_DIA_MM,
    CORNER_R,
    CROWN_R,
    CROWN_TOP_Y,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    FOOT_H,
    FOOT_L,
    FOOT_SCREW_THREAD,
    FOOT_TIP_X,
    HOLE_DIA_MM,
    ISOMETRIC_VIEW_NOTE,
    KEEPER_WIDTH,
    LUG_HALF_T,
    OVERALL_LENGTH,
    REFERENCE_SKETCHES,
    SCREW_FROM_SIDE,
    SCREW_FROM_TIP,
    SCREW_X,
    SCREW_HOLE_SPEC,
    SET_SCREW_HOLE_SPEC,
    SHAFT_AXIS_H,
    SUPPLY_HEIGHT_MIN,
    SUPPLY_HEIGHT_TOL_TYPE,
    UNIT,
)

PART_NAME = "ch-fulcrum-keeper"
MATERIAL = "Plain Carbon Steel"  # see _appearance.apply_material docstring

LUG_T = 2.0 * LUG_HALF_T  # 8.0 lug thickness along X
# Mid-plane through-cut total (both_directions splits the depth half per side
# of the sketch plane): past the lug's +-4 X extent, clear of the foot below.
BORE_CUT_DEPTH = 2.0 * LUG_T

# The keeper's foot screw is the part-owned #2 close-clearance counterbore;
# its depth is the exact stock head height so the bearing face stays flush.
if FOOT_SCREW_THREAD != FRAME_SIDE_THREAD:
    raise AssertionError("keeper foot screw thread drifted from MHA-CH-VN-52")
if HOLE_DIA_MM <= FRAME_SIDE_SHANK_DIA:
    raise AssertionError("standard #2 keeper clearance binds on the stock screw")
if CBORE_DIA_MM <= FRAME_SIDE_HEAD_DIA:
    raise AssertionError("keeper counterbore does not clear the stock screw head")
if CBORE_DEPTH_MM != FRAME_SIDE_HEAD_H:
    raise AssertionError("keeper counterbore depth is not the stock head height")
if CBORE_DEPTH_MM >= FOOT_H:
    raise AssertionError("keeper counterbore leaves no foot material at its floor")
# The crown tap's drill must stay inside the lug thickness, or the cross-hole
# volume below (a full crown cylinder across the drill) does not hold.
if blind_cut_dia_mm(SET_SCREW_HOLE_SPEC) >= LUG_T:
    raise AssertionError("crown tap drill breaks out of the lug faces")
# The foot-to-lug inside corner's fillet adds its spandrel, (1 - pi/4) R^2,
# along the keeper's width.
V_CORNER = (1.0 - math.pi / 4.0) * CORNER_R**2 * KEEPER_WIDTH

# The drawing-reference lines (ch_fulcrum_keeper_spec.REFERENCE_SKETCHES):
# (sketch, plane, dimension, start, end, orientation, value, drives), the
# dt_arbor_pedestal pattern. Each line starts on the feature it is measured
# from (drawing-guidelines.md rule 10 (dimension from a real feature)): the
# set-screw tap's runs on the seat (Top plane: sketch u = model X, v = -model
# Z) along the lug mid-width from the inner lug face -- the face the fit-up
# sets -- to the tap axis, so the plan dimensions it from the inner face's
# edge; the foot screw's two run on the seat from the foot-tip/-Z
# side corner along the side face to the screw station and down the tip
# face to the screw axis, so their extension lines leave the plan's outline
# without crossing; the bore's runs on the Right plane
# (the end view's frame) from a side face to the bore axis; the finished and
# supplied heights' run up the lug's inner face from the seat to the crown
# top and to the blank's least top; the overall length's along the seat
# from the inner lug face to the foot tip. ``drives`` binds the value
# dimension, then the start point's
# origin anchors, to the part's globals.
REFERENCE_LINES = (
    (
        "SetScrewReference",
        "Top",
        "SetScrewLocation",
        (-LUG_HALF_T, 0.0),
        (0.0, 0.0),
        "horizontal",
        LUG_HALF_T,
        ('"LugT" / 2', '"LugT" / 2'),
    ),
    (
        "FootScrewReference",
        "Top",
        "ScrewFromTip",
        (FOOT_TIP_X, SCREW_FROM_SIDE),
        (SCREW_X, SCREW_FROM_SIDE),
        "horizontal",
        SCREW_FROM_TIP,
        ('"FootScrewFromTip"', '"LugT" / 2 + "FootL"', '"KeeperWidth" / 2'),
    ),
    (
        "FootScrewSideReference",
        "Top",
        "ScrewFromSide",
        (FOOT_TIP_X, SCREW_FROM_SIDE),
        (FOOT_TIP_X, 0.0),
        "vertical",
        SCREW_FROM_SIDE,
        ('"KeeperWidth" / 2', '"LugT" / 2 + "FootL"', '"KeeperWidth" / 2'),
    ),
    (
        "BoreSideReference",
        "Right",
        "BoreFromSide",
        (BORE_FROM_SIDE, SHAFT_AXIS_H),
        (0.0, SHAFT_AXIS_H),
        "horizontal",
        BORE_FROM_SIDE,
        ('"KeeperWidth" / 2', '"KeeperWidth" / 2', '"ShaftAxisH"'),
    ),
    (
        "OverallHeightReference",
        "Front",
        "OverallHeight",
        (-LUG_HALF_T, 0.0),
        (-LUG_HALF_T, CROWN_TOP_Y),
        "vertical",
        CROWN_TOP_Y,
        ('"ShaftAxisH" + "CrownR"', '"LugT" / 2'),
    ),
    (
        "SupplyHeightReference",
        "Front",
        "SupplyHeight",
        (-LUG_HALF_T, 0.0),
        (-LUG_HALF_T, SUPPLY_HEIGHT_MIN),
        "vertical",
        SUPPLY_HEIGHT_MIN,
        ('"SupplyH"', '"LugT" / 2'),
    ),
    (
        "OverallLengthReference",
        "Front",
        "OverallLength",
        (-LUG_HALF_T, 0.0),
        (FOOT_TIP_X, 0.0),
        "horizontal",
        OVERALL_LENGTH,
        ('"LugT" + "FootL"', '"LugT" / 2'),
    ),
)
if tuple(row[0] for row in REFERENCE_LINES) != REFERENCE_SKETCHES:
    raise AssertionError("REFERENCE_LINES and REFERENCE_SKETCHES disagree")
# The supplied blank's square top (MR-fleet r8, 7b21790: the supply height's
# extension line ended in air above the crown): a second construction line in
# the supply height's sketch, across the lug thickness from the height line's
# top, so the dimension lands on drawn geometry, the blank's phantom outline.
SUPPLY_TOP_SKETCH = "SupplyHeightReference"
SUPPLY_TOP_DIMENSION = "SupplyTopWidth"
if SUPPLY_TOP_SKETCH not in REFERENCE_SKETCHES:
    raise AssertionError("the supply top's sketch is not a reference sketch")


def _as_construction(adapter, entity_id: str) -> None:
    """Flag a registered sketch line as construction geometry (the setter is
    on ISketchSegment, not the ISketchLine the registry binds)."""
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


async def _supply_square_top(adapter, sketch: str, height_line: str, corner) -> None:
    """The blank's square top: a horizontal construction line LUG_T long from
    the supply height line's top corner, sized by its own dimension."""
    set_sketch_direct_db(adapter, True)
    top = check(
        f"{sketch} square top",
        await adapter.add_line(*corner, corner[0] + LUG_T, corner[1]),
    )
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, top)
    check(
        f"{sketch} square top horizontal",
        await adapter.add_sketch_constraint(top, None, "horizontal"),
    )
    check(
        f"{sketch} square top starts on the height line",
        await adapter.add_sketch_constraint(
            f"{height_line}.end", f"{top}.start", "coincident"
        ),
    )
    await dimension_between(
        adapter, f"{top}.start", f"{top}.end", "horizontal_distance", LUG_T, sketch
    )


async def _reference_line(
    adapter, sketch, plane, dimension, start, end, orientation, value, drives
) -> list[tuple[str, str]]:
    """One hidden-reference sketch: a construction line whose driving
    dimension IS ``value``; returns its deferred drive jobs."""
    check(f"create_sketch {sketch}", await adapter.create_sketch(plane))
    # Direct-to-DB: the line lies on an outline station along a sketch axis
    # direction, so creation-time inference would over-define the sketch.
    set_sketch_direct_db(adapter, True)
    line = check(f"{sketch} line", await adapter.add_line(*start, *end))
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, line)
    check(
        f"{sketch} {orientation}",
        await adapter.add_sketch_constraint(line, None, orientation),
    )
    await dimension_between(
        adapter,
        f"{line}.start",
        f"{line}.end",
        f"{orientation}_distance",
        value,
        sketch,
    )
    await anchor_point_to_origin(adapter, f"{line}.start", *start, sketch)
    names = [dimension, *(f"{dimension}Anchor{i}" for i in range(1, len(drives)))]
    if sketch == SUPPLY_TOP_SKETCH:
        await _supply_square_top(adapter, sketch, line, end)
        names.append(SUPPLY_TOP_DIMENSION)
        drives = (*drives, '"LugT"')
    await ensure_fully_defined(adapter, f"{sketch} sketch")
    check(f"exit_sketch {sketch}", await adapter.exit_sketch())
    name_last_feature(adapter, sketch)
    full = name_dimensions(adapter, sketch, names)
    measured = (
        float(
            _early_bound(
                adapter.currentModel.Parameter(full[0]), "IDimension"
            ).SystemValue
        )
        * 1000.0
    )
    if abs(measured - value) > 1e-6:
        raise RuntimeError(f"{full[0]} measures {measured:g} mm, expected {value:g} mm")
    return list(zip(full, drives, strict=True))


@_telemetry.traced("appearance.hide_reference_sketches")
def _hide_reference_sketches(adapter) -> None:
    """Blank the drawing-reference sketches and prove each one reads hidden."""
    for name in REFERENCE_SKETCHES:
        blank_sketch(adapter, name)
    part = _early_bound(adapter.currentModel, "IPartDoc")
    shown = {
        name: visible
        for name in REFERENCE_SKETCHES
        # swVisibilityState_e: 1 hidden
        if (visible := int(_read_member(part.FeatureByName(name), "Visible"))) != 1
    }
    if shown:
        raise RuntimeError(f"reference sketches still visible after blanking: {shown}")


def _single_limit(
    adapter,
    feature: str,
    name: str,
    limit: float,
    tol_type: int,
    lower: float,
    upper: float,
) -> None:
    """``name@feature`` as a single limit: its nominal IS the printed limit
    (swTolMAX / swTolMIN print the nominal plus MAX / MIN), carrying the
    deviations ``lower`` / ``upper`` mm (build_ch_pivot_bracket.
    _corner_radius_max_limit's recipe)."""
    _, dimension = _named_dimension(adapter, feature, name)
    label = f"{name}@{feature}"
    value = float(dimension.SystemValue)
    if not math.isclose(value, limit / 1000.0, abs_tol=1e-9):
        raise RuntimeError(
            f"{label}: nominal {value * 1000.0:.7f} is not the limit {limit}"
        )
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = tol_type
    if not tolerance.SetValues(lower / 1000.0, upper / 1000.0):
        raise RuntimeError(f"{label}: SetValues rejected {lower:+g}/{upper:+g} mm")
    if (
        int(tolerance.Type) != tol_type
        or not math.isclose(
            float(tolerance.GetMinValue()), lower / 1000.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), upper / 1000.0, abs_tol=1e-12
        )
    ):
        raise RuntimeError(f"{label}: single-limit tolerance readback changed")
    _telemetry.success(f"{label}: single limit {limit:g} (type {tol_type})")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations). mm suffix load-bearing (INCH
    # document; the equation manager reads bare numbers in document units).
    await set_global(adapter, "FootL", f"{FOOT_L}mm")
    await set_global(adapter, "FootH", f"{FOOT_H}mm")
    await set_global(adapter, "KeeperWidth", f"{KEEPER_WIDTH}mm")
    await set_global(adapter, "LugT", f"{LUG_T}mm")
    await set_global(adapter, "ShaftAxisH", f"{SHAFT_AXIS_H}mm")
    await set_global(adapter, "CrownR", f"{CROWN_R}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "CornerR", f"{CORNER_R}mm")
    await set_global(adapter, "SupplyH", f"{SUPPLY_HEIGHT_MIN}mm")
    await set_global(adapter, "FootScrewFromTip", f"{SCREW_FROM_TIP}mm")

    drive_jobs: list[tuple[str, str]] = []

    # --- Lug: end-profile rectangle on Right (ZY), extruded +-X -----------
    # From the seat up to the shaft axis; the crown rounds it off above.
    lug = SketchDims()
    check("create_sketch lug", await adapter.create_sketch("Right"))
    half_w = KEEPER_WIDTH / 2.0
    lug_pts = [
        (-half_w, 0.0),
        (half_w, 0.0),
        (half_w, SHAFT_AXIS_H),
        (-half_w, SHAFT_AXIS_H),
    ]
    lug_lines = await add_line_chain(adapter, lug_pts)
    await define_rectilinear_chain(
        adapter,
        lug_lines,
        lug_pts,
        label="lug profile",
        dims=lug,
        names=["LugWidth", "LugRise", "LugAnchorZ"],
        drives=['"KeeperWidth"', '"ShaftAxisH"', '"KeeperWidth" / 2'],
    )
    await ensure_fully_defined(adapter, "lug profile")
    check("exit_sketch lug", await adapter.exit_sketch())
    name_last_feature(adapter, "LugProfile")
    drive_jobs += lug.apply(adapter, "LugProfile")
    check(
        "extrude lug",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=LUG_T, both_directions=True)
        ),
    )
    name_last_feature(adapter, "LugBody")
    lug_depth = name_dimensions(adapter, "LugBody", ["LugThickness"])
    drive_jobs += [(lug_depth[0], '"LugT"')]
    v_lug = KEEPER_WIDTH * SHAFT_AXIS_H * LUG_T
    volume = await volume_check(adapter, "lug", v_lug, 0.005 * v_lug)

    # --- Foot: side-profile rectangle on Front (XY), extruded +-Z ---------
    # Outboard of the lug's outer face, x +4..+12.5, y 0..8; its underside
    # is coplanar with the lug's, so the two make one flat seat.
    foot = SketchDims()
    check("create_sketch foot", await adapter.create_sketch("Front"))
    pts = [
        (LUG_HALF_T, 0.0),
        (FOOT_TIP_X, 0.0),
        (FOOT_TIP_X, FOOT_H),
        (LUG_HALF_T, FOOT_H),
    ]
    lines = await add_line_chain(adapter, pts)
    await define_rectilinear_chain(
        adapter,
        lines,
        pts,
        label="foot profile",
        dims=foot,
        names=["FootLength", "FootRise", "FootAnchorX"],
        drives=['"FootL"', '"FootH"', '"LugT" / 2'],
    )
    await ensure_fully_defined(adapter, "foot profile")
    check("exit_sketch foot", await adapter.exit_sketch())
    name_last_feature(adapter, "FootProfile")
    drive_jobs += foot.apply(adapter, "FootProfile")
    check(
        "extrude foot",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=KEEPER_WIDTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Foot")
    depth_dim = name_dimensions(adapter, "Foot", ["Depth"])
    drive_jobs += [(depth_dim[0], '"KeeperWidth"')]
    v_foot = FOOT_L * FOOT_H * KEEPER_WIDTH
    volume = await volume_check(adapter, "foot", volume + v_foot, 0.005 * v_foot)

    # Foot-to-lug inside corner (drawing-guidelines.md rule 16): the edge where
    # the foot top meets the lug's outer face, filleted at the title block's
    # INSIDE CORNERS R1.0 MAX (CORNER_R), whose tangent line stays off the
    # counterbore; the sheet prints no local limit.
    check(
        "fillet foot-to-lug corner",
        await adapter.add_fillet(
            CORNER_R, [[LUG_HALF_T, FOOT_H, 0.0]], propagate=False
        ),
    )
    name_last_feature(adapter, "CornerFillet")
    corner_dim = name_dimensions(adapter, "CornerFillet", ["CornerRadius"])
    drive_jobs.append((corner_dim[0], '"CornerR"'))
    volume = await volume_check(
        adapter, "foot-to-lug corner fillet", volume + V_CORNER, 0.1 * V_CORNER
    )

    # --- Crown: full-round lug top, concentric with the shaft axis --------
    crown = SketchDims()
    check("create_sketch crown", await adapter.create_sketch("Right"))
    await define_circle(
        adapter,
        0.0,
        SHAFT_AXIS_H,
        CROWN_R,
        "lug crown",
        dims=crown,
        names=("CrownCz", "ShaftAxisH", "CrownRadius"),
        drives=(None, '"ShaftAxisH"', '"CrownR"'),
        size_dimension="radius",
    )
    await ensure_fully_defined(adapter, "lug crown sketch")
    check("exit_sketch crown", await adapter.exit_sketch())
    name_last_feature(adapter, "LugCrownProfile")
    drive_jobs += crown.apply(adapter, "LugCrownProfile")
    check(
        "extrude crown",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=LUG_T, both_directions=True)
        ),
    )
    name_last_feature(adapter, "LugCrown")
    crown_depth = name_dimensions(adapter, "LugCrown", ["Depth"])
    drive_jobs += [(crown_depth[0], '"LugT"')]
    r_c = CROWN_R
    # The crown circle's lower half merges into the lug rectangle (its centre
    # sits ON the lug top edge and its bottom, y 18.2, is inside the lug), so
    # only the upper half adds metal.
    v_crown = 0.5 * math.pi * r_c * r_c * LUG_T
    volume = await volume_check(adapter, "lug crown", volume + v_crown, 0.01 * v_crown)

    # --- Shaft bore: plain reamed Ø6.35 through the lug on the axis -------
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Right"))
    await define_circle(
        adapter,
        0.0,
        SHAFT_AXIS_H,
        BORE_DIA / 2.0,
        "shaft bore",
        dims=bore,
        names=("BoreCz", "BoreH", "BoreDia"),
        drives=(None, '"ShaftAxisH"', '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "shaft bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "ShaftBoreProfile")
    drive_jobs += bore.apply(adapter, "ShaftBoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=BORE_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ShaftBore")
    # Coaxial cylinder through the 8.0 lug only: the bore (y 22.0..28.4)
    # lies wholly inside the lug + crown and well above the foot (y <= 8).
    v_bore = math.pi * (BORE_DIA / 2.0) ** 2 * LUG_T
    volume = await volume_check(adapter, "shaft bore", volume - v_bore, 0.01 * v_bore)

    # --- Foot screw hole: fillister counterbore SCREW_FROM_TIP off the tip --
    screw_hole = wizard_holes(
        adapter,
        SCREW_HOLE_SPEC,
        [[SCREW_X, FOOT_H, 0.0]],
        (0.0, 1.0, 0.0),
        "keeper foot screw hole (#2 cbore)",
        expect_dia_mm=HOLE_DIA_MM,
        name="FootScrewHole",
    )
    v_cb = math.pi * (screw_hole.cbore_dia_mm / 2.0) ** 2 * screw_hole.cbore_depth_mm
    v_thru = (
        math.pi
        * (screw_hole.hole_dia_mm / 2.0) ** 2
        * (FOOT_H - screw_hole.cbore_depth_mm)
    )
    volume = await volume_check(
        adapter, "foot screw hole", volume - v_cb - v_thru, 0.01 * (v_cb + v_thru)
    )

    # --- Crown set-screw tap: #1-72 down through the crown top ------------
    # ONE native tapped hole drilled radially into the crown cylinder at its
    # apex on the lug mid-plane and stopped at the next surface -- the shaft
    # bore -- so it never runs on through the lug (the dt_arbor_pedestal
    # apex-tap idiom). Right Plane (x = 0) and Front Plane (z = 0) pin the
    # 3D placement point onto the apex.
    wizard_hole_on_cylinder(
        adapter,
        SET_SCREW_HOLE_SPEC,
        [0.0, CROWN_TOP_Y, 0.0],
        f"crown set-screw tap ({SET_SCREW_HOLE_SPEC.size})",
        name="SetScrewTap",
        point_planes=("Right Plane", "Front Plane"),
    )
    # The tap drill removes the crown wall between the crown and the bore:
    # half of each perpendicular cross-hole volume, crown minus bore (the
    # drill's +-0.76 footprint along X stays inside the 8.0 lug, so the crown
    # is a full cylinder across it).
    tap_dia = blind_cut_dia_mm(SET_SCREW_HOLE_SPEC)
    v_tap = (
        cross_hole_volume_mm3(tap_dia, 2.0 * CROWN_R)
        - cross_hole_volume_mm3(tap_dia, BORE_DIA)
    ) / 2.0
    volume = await volume_check(
        adapter, "crown set-screw tap", volume - v_tap, 0.03 * v_tap
    )

    # The tap station's drawing-reference line (no metal).
    for row in REFERENCE_LINES:
        drive_jobs += await _reference_line(adapter, *row)

    # Deferred drive equations, then re-check neutrality (each evaluates to
    # the as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven keeper (equations neutral)", volume, 0.005 * volume
    )
    _hide_reference_sketches(adapter)
    # Decimal places are the tolerance statement, so the PART carries them;
    # the reamed bore's running band (BORE_DIA_BAND) is a native model tolerance.
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    # Any taller blank rounds down to the crown: no deviation either way.
    _single_limit(
        adapter,
        "SupplyHeightReference",
        "SupplyHeight",
        SUPPLY_HEIGHT_MIN,
        SUPPLY_HEIGHT_TOL_TYPE,
        0.0,
        0.0,
    )
    # The crown is a full round tangent to both sides: no band of its own
    # (the width's governs it); the sheet prints it as a radial reference.
    # The bands are millimetres; UNIT prints them in inches.
    set_dimension_bilateral_tolerance(
        adapter,
        "ShaftBoreProfile",
        "BoreDia",
        *deviations(BORE_DIA_BAND),
        display_unit=UNIT,
    )

    # Manufacturing drawing support: mark exactly the print's dimensions and
    # stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
