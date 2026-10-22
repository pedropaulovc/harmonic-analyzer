r"""Build the approved blued low-carbon-steel L bracket, with no collar or press.

The mounting seat and threaded-lever pose stay fixed; the two clearance holes
follow the lowered plate-tap row. The foot's right edge extends to the centred
12.50 neck, with no rear stub or ledge. The Right-plane neck has parallel sides
and a true concentric semicircle.
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_color, apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing, mark_dimensions_for_drawing
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_tolerances import set_dimension_bilateral_tolerance, set_dimension_symmetric_tolerance
from _extrude import extrude_at_offset
from _feature_tree import name_last_feature
from _fit_deviations import deviations
from _holes import wizard_holes
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import SketchDims, add_line_chain, anchor_point_to_origin, anchor_point_to_point, blank_reference_sketches, dimension_between, ensure_fully_defined, set_sketch_direct_db
from _sketch_chains import define_rectilinear_chain
from magnifying_bracket_joint_layout import BRACKET_HOLE_POINTS, CLEARANCE_DIA, CLEARANCE_SPEC, POSITION_BAND, SIDE_PLATE_X as FLANGE_X, SIDE_PLATE_Y as FLANGE_Y, SIDE_PLATE_Z as FLANGE_Z, SIDE_PLATE_THICKNESS
from mg_lever_thread_joint import HOLE_LOCATION_TOL, MOUTH_CHAMFER, MOUTH_CHAMFER_BAND, MOUTH_CHAMFER_MAX, NECK_HALF_X, NECK_THICKNESS, NOSE_R, NOSE_R_TOL, TAP_DRILL_DIA, TAP_SPEC
from mg_magnifying_bracket_spec import DRAWING_DIMENSIONS, DRAWING_PRECISION, FOOT_CORNER_R, ISOMETRIC_VIEW_NOTE, ROOT_R

PART_NAME = "mg-magnifying-bracket"
MATERIAL = "Plain Carbon Steel"


def _construction(adapter, entity: str) -> None:
    segment = _early_bound(adapter._sketch_entities[entity], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity}: construction flag did not persist")




def _assert_placement_sketches_fully_defined(adapter) -> None:
    """Read the retained native sketch, not the SDK's lossy named lookup."""
    model = _early_bound(adapter.currentModel, "IPartDoc")
    for feature_name in ("MountingHoles", "LeverTap"):
        feature = model.FeatureByName(feature_name)
        if feature is None:
            raise RuntimeError(f"{feature_name}: native part feature not found")
        sub = _early_bound(feature, "IFeature").GetFirstSubFeature()
        while sub is not None:
            sub = _early_bound(sub, "IFeature")
            if str(sub.GetTypeName2()) in ("ProfileFeature", "3DProfileFeature"):
                sketch = _early_bound(sub.GetSpecificFeature2(), "ISketch")
                if sketch.GetSketchPoints2() and not sketch.GetSketchSegments():
                    status = sketch.GetConstrainedStatus()  # swFullyConstrained = 3
                    if type(status) is not int or status != 3:
                        raise RuntimeError(f"{feature_name}: placement sketch {sub.Name} is not fully defined: native status={status!r}")
                    break
            sub = sub.GetNextSubFeature()
        else:
            raise RuntimeError(f"{feature_name}: point-only placement sketch not found")


async def _coordinates(adapter, jobs) -> None:
    # The mounting coordinates still originate on the real west/lower edges.
    dims = SketchDims()
    check("mounting coordinates", await adapter.create_sketch("Front"))
    for index, point in enumerate(BRACKET_HOLE_POINTS):
        start = (FLANGE_X[0], FLANGE_Y[0])
        corner = (point[0], start[1])
        lines = await add_line_chain(adapter, [start, corner, point[:2]], close=False)
        if index == 0:  # exact-coordinate branches share this one corner
            await anchor_point_to_origin(adapter, f"{lines[0]}.start", *start, "mounting corner")
            dims.record("MountingOriginX")
            dims.record("MountingOriginY")
        await anchor_point_to_point(adapter, f"{lines[0]}.start", f"{lines[0]}.end", corner[0] - start[0], 0.0, "mounting X")
        dims.record(f"MountingX{index}")
        await anchor_point_to_point(adapter, f"{lines[1]}.start", f"{lines[1]}.end", 0.0, point[1] - start[1], "mounting Y")
        dims.record(f"MountingY{index}")
        for line in lines:
            _construction(adapter, line)
    await ensure_fully_defined(adapter, "mounting coordinates")
    check("exit mounting coordinates", await adapter.exit_sketch())
    name_last_feature(adapter, "MountingCoordinates")
    jobs.extend(dims.apply(adapter, "MountingCoordinates"))
    for name in ("MountingX0", "MountingX1", "MountingY0", "MountingY1"):
        set_dimension_symmetric_tolerance(adapter, "MountingCoordinates", name, POSITION_BAND)

    # Nonzero, inspectable hole locations from the nose TIP and a neck SIDE.
    # Right coordinates (u,v)=(-Z,Y): (R,-R) is their theoretical intersection.
    # The native witness dimensions own the manufactured location requirement;
    # the Wizard's on-origin placement owns the nominal hole geometry.
    dims = SketchDims()
    check("tap coordinate sketch", await adapter.create_sketch("Right"))
    lines = await add_line_chain(adapter, [(NOSE_R, -NOSE_R), (0.0, -NOSE_R), (0.0, 0.0)], close=False)
    await anchor_point_to_origin(adapter, f"{lines[0]}.start", NOSE_R, -NOSE_R, "nose tip and side")
    dims.record("TipReference", '"NoseR"')
    dims.record("SideReference", '"NoseR"')
    await anchor_point_to_point(adapter, f"{lines[0]}.start", f"{lines[0]}.end", -NOSE_R, 0.0, "tap from tip")
    dims.record("TapFromTip", '"NoseR"')
    await anchor_point_to_point(adapter, f"{lines[1]}.start", f"{lines[1]}.end", 0.0, NOSE_R, "tap from side")
    dims.record("TapFromSide", '"NoseR"')
    for line in lines:
        _construction(adapter, line)
    await ensure_fully_defined(adapter, "tap coordinates")
    check("exit tap coordinates", await adapter.exit_sketch())
    name_last_feature(adapter, "TapCoordinates")
    jobs.extend(dims.apply(adapter, "TapCoordinates"))
    for name in ("TapFromTip", "TapFromSide"):
        set_dimension_symmetric_tolerance(adapter, "TapCoordinates", name, HOLE_LOCATION_TOL)



async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create part", await adapter.create_part())
    for name, value in (("NoseR", NOSE_R), ("SeatToAxis", FLANGE_Z[1]), ("NeckThickness", NECK_THICKNESS)):
        await set_global(adapter, name, f"{value}mm")
    jobs = []
    dims = SketchDims()
    check("neck profile", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    arc = check("semicircular nose", await adapter.add_arc(0.0, 0.0, 0.0, -NOSE_R, 0.0, NOSE_R))
    lines = await add_line_chain(adapter, [(0.0, NOSE_R), (-FLANGE_Z[1], NOSE_R), (-FLANGE_Z[1], -NOSE_R), (0.0, -NOSE_R)], close=False)
    set_sketch_direct_db(adapter, False)
    for first, second in ((f"{arc}.end", f"{lines[0]}.start"), (f"{arc}.start", f"{lines[2]}.end")):
        check("nose contour closes", await adapter.add_sketch_constraint(first, second, "coincident"))
    check("nose centre", await adapter.add_sketch_constraint(f"{arc}.center", "origin", "coincident"))
    for point in (f"{arc}.start", f"{arc}.end"):
        check("nose semicircle", await adapter.add_sketch_constraint(point, "origin", "vertical_points"))
    check("nose radius", await adapter.add_sketch_dimension(arc, None, "radial", NOSE_R))
    dims.record("NoseR", '"NoseR"')
    for line, relation in zip(lines, ("horizontal", "vertical", "horizontal"), strict=True):
        check("parallel straight neck", await adapter.add_sketch_constraint(line, None, relation))
    await dimension_between(adapter, f"{lines[0]}.end", "origin", "horizontal_distance", FLANGE_Z[1], "seat to nose axis")
    dims.record("SeatToAxis", '"SeatToAxis"')
    await ensure_fully_defined(adapter, "neck profile")
    check("exit neck profile", await adapter.exit_sketch())
    name_last_feature(adapter, "NeckProfile")
    jobs.extend(dims.apply(adapter, "NeckProfile"))
    check("centred neck", await adapter.create_extrusion(ExtrusionParameters(depth=NECK_THICKNESS, both_directions=True)))
    name_last_feature(adapter, "Neck")
    jobs.append((name_dimensions(adapter, "Neck", ["NeckThickness"])[0], '"NeckThickness"'))

    dims = SketchDims()
    check("foot profile", await adapter.create_sketch("Top"))
    points = [(FLANGE_X[0], -FLANGE_Z[1]), (FLANGE_X[1], -FLANGE_Z[1]), (FLANGE_X[1], -FLANGE_Z[0]), (FLANGE_X[0], -FLANGE_Z[0])]
    lines = await add_line_chain(adapter, points)
    await define_rectilinear_chain(adapter, lines, points, label="foot", dims=dims, names=["FlangeWidth", "FlangeDepth", "FlangeCornerX", "FlangeCornerZ"])
    await ensure_fully_defined(adapter, "foot profile")
    check("exit foot profile", await adapter.exit_sketch())
    name_last_feature(adapter, "FlangeProfile")
    jobs.extend(dims.apply(adapter, "FlangeProfile"))
    extrude_at_offset(adapter, FLANGE_Y[1] - FLANGE_Y[0], FLANGE_Y[0])
    name_last_feature(adapter, "Flange")
    name_dimensions(adapter, "Flange", ["FlangeHeight"])
    if FLANGE_X[1] != NECK_HALF_X:
        raise AssertionError("foot and neck must share the right face without a ledge")

    check("foot inside X root", await adapter.add_fillet(FOOT_CORNER_R, [[-NECK_HALF_X, 0.0, FLANGE_Z[0]]], propagate=False))
    name_last_feature(adapter, "InsideRoot")
    check("smooth axial roots", await adapter.add_fillet(ROOT_R, [[0.0, y, FLANGE_Z[0]] for y in (-NOSE_R, NOSE_R)], propagate=False))
    name_last_feature(adapter, "AxialRoots")
    check("tangent outside foot edges", await adapter.add_fillet(FOOT_CORNER_R, [[(FLANGE_X[0] - NECK_HALF_X) / 2.0, y, FLANGE_Z[0]] for y in FLANGE_Y], propagate=False))
    name_last_feature(adapter, "FootTopEdges")
    check("rounded parallel foot corners", await adapter.add_fillet(FOOT_CORNER_R, [[x, y, sum(FLANGE_Z) / 2.0] for x in FLANGE_X for y in FLANGE_Y], propagate=False))
    name_last_feature(adapter, "FootCorners")
    name_dimensions(adapter, "FootCorners", ["FootCornerR"])
    wizard_holes(adapter, CLEARANCE_SPEC, BRACKET_HOLE_POINTS, (0.0, 0.0, -1.0), "relocated plate-tap mounting holes", name="MountingHoles", expect_dia_mm=CLEARANCE_DIA, placement_dims=[((None, None), (None, None)) for _ in BRACKET_HOLE_POINTS])
    wizard_holes(adapter, TAP_SPEC, [(NECK_HALF_X, 0.0, 0.0)], (1.0, 0.0, 0.0), "lever through tap", name="LeverTap", expect_dia_mm=TAP_DRILL_DIA, placement_dims=[((None, None), (None, None))])
    _assert_placement_sketches_fully_defined(adapter)
    check("both tap mouth chamfers", await adapter.add_chamfer(MOUTH_CHAMFER, [[x, TAP_DRILL_DIA / 2.0, 0.0] for x in (-NECK_HALF_X, NECK_HALF_X)]))
    name_last_feature(adapter, "MouthBreak")
    name_dimensions(adapter, "MouthBreak", ["MouthChamfer"])
    set_dimension_bilateral_tolerance(adapter, "MouthBreak", "MouthChamfer", *deviations(MOUTH_CHAMFER_BAND))
    # Width is capped natively; the joint charges the ordinary angular band
    # for the other leg rather than claiming both legs have this same maximum.
    _, chamfer_dimension = _named_dimension(adapter, "MouthBreak", "MouthChamfer")
    chamfer_tolerance = _early_bound(chamfer_dimension.Tolerance, "IDimensionTolerance")
    chamfer_nominal = float(chamfer_dimension.SystemValue) * 1000.0
    if not (
        math.isclose(chamfer_nominal, MOUTH_CHAMFER, abs_tol=1e-6)
        and math.isclose(chamfer_nominal + float(chamfer_tolerance.GetMinValue()) * 1000.0, 0.0, abs_tol=1e-6)
        and math.isclose(chamfer_nominal + float(chamfer_tolerance.GetMaxValue()) * 1000.0, MOUTH_CHAMFER_MAX, abs_tol=1e-6)
    ):
        raise RuntimeError("MouthChamfer@MouthBreak: native primary-distance limits changed")
    await _coordinates(adapter, jobs)
    await force_rebuild(adapter)
    for dimension, expression in jobs:
        await drive_dimension(adapter, dimension, expression)
    await force_rebuild(adapter)
    # Exact nominal prismatic volume plus bounded small corner/chamfer changes.
    neck = NECK_THICKNESS * (2.0 * NOSE_R * FLANGE_Z[1] + math.pi * NOSE_R**2 / 2.0)
    foot = (FLANGE_X[1] - FLANGE_X[0]) * SIDE_PLATE_THICKNESS * (FLANGE_Y[1] - FLANGE_Y[0])
    overlap = NECK_THICKNESS * 2.0 * NOSE_R * SIDE_PLATE_THICKNESS
    holes = math.pi / 4.0 * (TAP_DRILL_DIA**2 * NECK_THICKNESS + 2.0 * CLEARANCE_DIA**2 * SIDE_PLATE_THICKNESS)
    expected = neck + foot - overlap - holes
    await volume_check(adapter, "simple L with through tap and rounded corners", expected, 10.0)
    await name_bore_axis(adapter, "Front Plane", 0.0, "Top Plane", 0.0, "threaded lever axis")
    set_dimension_symmetric_tolerance(adapter, "NeckProfile", "NoseR", NOSE_R_TOL)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature, names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature, names)
    blank_reference_sketches(adapter, ("MountingCoordinates", "TapCoordinates"))
    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, (0.12, 0.12, 0.13))  # blued, not bare steel
    apply_drawing_properties(adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE})
    await report_mass_properties(adapter)
    await force_rebuild(adapter)
    await volume_check(adapter, "final native dimensions preserve L bracket", expected, 10.0)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
