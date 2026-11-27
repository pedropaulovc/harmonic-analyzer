r"""Build the approved blued low-carbon-steel L bracket, with no collar or press.

The mounting seat and threaded-lever pose stay fixed; the two clearance holes
follow the lowered plate-tap row. The foot's right edge extends to the centred
neck, with no rear stub or ledge. The Right-plane neck has parallel sides and
a true concentric semicircle. The part's document units are inch (#290).
"""

from __future__ import annotations

import json
import math
import sys

from _appearance import apply_color, apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _bind, _early_bound
from _dimensions import _dim_value_mm, _display_dimensions, drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing, mark_dimensions_for_drawing
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_tolerances import set_dimension_bilateral_tolerance, set_dimension_symmetric_tolerance
from _extrude import extrude_at_offset
from _feature_tree import name_last_feature
from _fit_deviations import deviations
from _gtol_cylinder import CylinderFace
from _gtol_face_read import face_geometry
from _gtol_face_resolve import resolve_faces
from _gtol_planar import PlanarFace
from _holes import wizard_holes
from _part_checks import report_mass_properties, volume_check
from _part_pmi import author_part_pmi
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import SketchDims, add_line_chain, anchor_point_to_origin, anchor_point_to_point, blank_reference_sketches, dimension_between, ensure_fully_defined, set_sketch_direct_db
from _sketch_chains import define_rectilinear_chain
from magnifying_bracket_joint_layout import BRACKET_HOLE_POINTS, CLEARANCE_DIA, CLEARANCE_SPEC, SIDE_PLATE_X as FLANGE_X, SIDE_PLATE_Y as FLANGE_Y, SIDE_PLATE_Z as FLANGE_Z, SIDE_PLATE_THICKNESS
from mg_lever_thread_joint import HOLE_LOCATION_TOL, MOUTH_CHAMFER, MOUTH_CHAMFER_BAND, MOUTH_CHAMFER_MAX, NECK_HALF_X, NECK_THICKNESS, NOSE_R, NOSE_R_TOL, TAP_DRILL_DIA, TAP_SPEC
from mg_magnifying_bracket_spec import DIMENSION_CALLOUTS, DRAWING_DIMENSIONS, DRAWING_PRECISION, FOOT_CORNER_R, INSIDE_ROOT_R, ISOMETRIC_VIEW_NOTE, UNIT
from mg_magnifying_bracket_finish_spec import SURFACE_FINISHES
import _telemetry

PART_NAME = "mg-magnifying-bracket"
MATERIAL = "Plain Carbon Steel"
# Top-plane foot chain (sketch y = -model Z). The first vertical segment is
# the free -X end, so the drawing's FlangeDepth witnesses start on the real
# foot top and bottom corners, not on the +X face shared with the upright.
# Same anchor vertex and FlangeWidth segment as before; geometry is unchanged.
FOOT_PROFILE = ((FLANGE_X[0], -FLANGE_Z[0]), (FLANGE_X[0], -FLANGE_Z[1]), (FLANGE_X[1], -FLANGE_Z[1]), (FLANGE_X[1], -FLANGE_Z[0]))
FOOT_PROFILE_ANCHOR = 1
FOOT_PROFILE_DIMENSIONS = ("FlangeDepth", "FlangeWidth", "FlangeCornerX", "FlangeCornerZ")


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


def _author_dimension_callouts(adapter) -> None:
    """Persist approved structural reasons on the source dimensions, not notes."""
    for feature, callouts in DIMENSION_CALLOUTS.items():
        for name, text in callouts.items():
            display, _dimension = _named_dimension(adapter, feature, name)
            display.SetText(4, text)  # swDimensionTextCalloutBelow; native value stays visible.
            if str(display.GetText(4) or "").replace("\r\n", "\n") != text:
                raise RuntimeError(f"{name}@{feature}: structural callout did not persist")


def _coordinates(adapter, jobs) -> None:
    # The mounting coordinates still originate on the real west/lower edges.
    dims = SketchDims()
    check("mounting coordinates", adapter.create_sketch("Front"))
    for index, point in enumerate(BRACKET_HOLE_POINTS):
        start = (FLANGE_X[0], FLANGE_Y[0])
        corner = (point[0], start[1])
        lines = add_line_chain(adapter, [start, corner, point[:2]], close=False)
        if index == 0:  # exact-coordinate branches share this one corner
            anchor_point_to_origin(adapter, f"{lines[0]}.start", *start, "mounting corner")
            dims.record("MountingOriginX")
            dims.record("MountingOriginY")
        anchor_point_to_point(adapter, f"{lines[0]}.start", f"{lines[0]}.end", corner[0] - start[0], 0.0, "mounting X")
        dims.record(f"MountingX{index}")
        anchor_point_to_point(adapter, f"{lines[1]}.start", f"{lines[1]}.end", 0.0, point[1] - start[1], "mounting Y")
        dims.record(f"MountingY{index}")
        for line in lines:
            _construction(adapter, line)
    ensure_fully_defined(adapter, "mounting coordinates")
    check("exit mounting coordinates", adapter.exit_sketch())
    name_last_feature(adapter, "MountingCoordinates")
    jobs.extend(dims.apply(adapter, "MountingCoordinates"))
    # No explicit band: the holes drill to the title block's .XXX row and the
    # MHA-SM-03 taps are spotted through them at assembly
    # (magnifying_bracket_joint_layout.BRACKET_POSITION_BAND).

    # Nonzero, inspectable hole locations from the nose TIP and a neck SIDE.
    # Right coordinates (u,v)=(-Z,Y): (R,-R) is their theoretical intersection.
    # The native witness dimensions own the manufactured location requirement;
    # the Wizard's on-origin placement owns the nominal hole geometry.
    dims = SketchDims()
    check("tap coordinate sketch", adapter.create_sketch("Right"))
    lines = add_line_chain(adapter, [(NOSE_R, -NOSE_R), (0.0, -NOSE_R), (0.0, 0.0)], close=False)
    anchor_point_to_origin(adapter, f"{lines[0]}.start", NOSE_R, -NOSE_R, "nose tip and side")
    dims.record("TipReference", '"NoseR"')
    dims.record("SideReference", '"NoseR"')
    anchor_point_to_point(adapter, f"{lines[0]}.start", f"{lines[0]}.end", -NOSE_R, 0.0, "tap from tip")
    dims.record("TapFromTip", '"NoseR"')
    anchor_point_to_point(adapter, f"{lines[1]}.start", f"{lines[1]}.end", 0.0, NOSE_R, "tap from side")
    dims.record("TapFromSide", '"NoseR"')
    for line in lines:
        _construction(adapter, line)
    ensure_fully_defined(adapter, "tap coordinates")
    check("exit tap coordinates", adapter.exit_sketch())
    name_last_feature(adapter, "TapCoordinates")
    jobs.extend(dims.apply(adapter, "TapCoordinates"))
    for name in ("TapFromTip", "TapFromSide"):
        set_dimension_symmetric_tolerance(adapter, "TapCoordinates", name, HOLE_LOCATION_TOL, display_unit=UNIT)



def _apply_fillet_item_radii(
    fillet_data, expected_count: int, root_probe_m: tuple[float, float, float]
) -> None:
    item_count = int(fillet_data.FilletItemsCount)
    if item_count != expected_count:
        raise RuntimeError(
            f"RootAndFootRounds: expected {expected_count} fillet items, found {item_count}"
        )
    root_hits = 0
    for index in range(item_count):
        item = fillet_data.GetFilletItemAtIndex(index)
        if item is None:
            raise RuntimeError(f"RootAndFootRounds: missing fillet item {index}")
        closest = _early_bound(item, "IEdge").GetClosestPointOn(*root_probe_m)
        if closest is None or len(closest) < 3:
            raise RuntimeError(f"RootAndFootRounds: fillet item {index} has no closest point")
        is_root = math.dist(tuple(float(v) for v in closest[:3]), root_probe_m) < 1e-6
        target_m = (INSIDE_ROOT_R if is_root else FOOT_CORNER_R) / 1000.0
        fillet_data.SetRadius(item, target_m)
        root_hits += int(is_root)
    if root_hits != 1:
        raise RuntimeError(
            f"RootAndFootRounds: expected 1 inside-root item, matched {root_hits} of {item_count}"
        )


def _round_foot_root(adapter, jobs) -> None:
    """Solve the .020 inside X-root and .010 outside foot rounds together."""
    from solidworks_mcp.adapters import sw_type_info as _sw_type_info

    # Matched Y sides make these a single interacting corner treatment.
    # Do not first create the inside-root cylinder and then try to terminate
    # two new side rounds against its tangent boundary. Select only the raw
    # root and free-foot front edges, never the upright's long sharp edges.
    targets = (
        (-NECK_HALF_X, 0.0, FLANGE_Z[0]),
        ((FLANGE_X[0] - NECK_HALF_X) / 2.0, FLANGE_Y[0], FLANGE_Z[0]),
        ((FLANGE_X[0] - NECK_HALF_X) / 2.0, FLANGE_Y[1], FLANGE_Z[0]),
    )
    part = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = tuple(part.GetBodies2(0, True) or ())
    if len(bodies) != 1:
        raise RuntimeError(f"RootAndFootRounds: expected 1 solid body, found {len(bodies)}")
    body_edges = tuple(_early_bound(bodies[0], "IBody2").GetEdges() or ())
    if not body_edges:
        raise RuntimeError("RootAndFootRounds: solid body has no edges")
    selected = []
    for point_mm in targets:
        point_m = tuple(coord / 1000.0 for coord in point_mm)
        best_edge = None
        best_gap = 0.0005
        for raw_edge in body_edges:
            edge = _early_bound(raw_edge, "IEdge")
            closest = edge.GetClosestPointOn(*point_m)
            if closest is None or len(closest) < 3:
                continue
            gap = math.dist(tuple(float(v) for v in closest[:3]), point_m)
            if gap < best_gap:
                best_gap = gap
                best_edge = raw_edge
        if best_edge is None:
            raise RuntimeError(f"RootAndFootRounds: no body edge near {point_mm} mm")
        selected.append(best_edge)
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    fm = _early_bound(model.FeatureManager, "IFeatureManager")
    model.ClearSelection2(True)
    sw_fm_fillet = _sw_type_info.constant("swFmFillet")
    raw_defn = fm.CreateDefinition(sw_fm_fillet)
    if raw_defn is None:
        raise RuntimeError("RootAndFootRounds: CreateDefinition(swFmFillet) returned None")
    defn = _early_bound(raw_defn, "ISimpleFilletFeatureData2")
    if not defn.Initialize(_sw_type_info.constant("swConstRadiusFillet")):
        raise RuntimeError("RootAndFootRounds: Initialize(swConstRadiusFillet) failed")
    defn.ConicTypeForCrossSectionProfile = _sw_type_info.constant("swFeatureFilletCircular")
    defn.OverflowType = _sw_type_info.constant("swFilletOverFlowType_Default")
    defn.PropagateToTangentFaces = False
    defn.DefaultRadius = FOOT_CORNER_R / 1000.0
    for index, raw_edge in enumerate(selected):
        if not _early_bound(raw_edge, "IEntity").Select2(index > 0, 1):
            raise RuntimeError(f"RootAndFootRounds: Select2(Mark=1) failed for edge {index}")
    defn.IsMultipleRadius = True
    root_probe_m = (-NECK_HALF_X / 1000.0, 0.0, FLANGE_Z[0] / 1000.0)
    pre_count = int(defn.FilletItemsCount)
    if pre_count == len(selected):
        _apply_fillet_item_radii(defn, len(selected), root_probe_m)
    _telemetry.info(
        f"RootAndFootRounds pre-create: swFmFillet={sw_fm_fillet} items={pre_count}"
    )
    raw_created = fm.CreateFeature(defn)
    model.ClearSelection2(True)
    if raw_created is None:
        raise RuntimeError("RootAndFootRounds: CreateFeature(ISimpleFilletFeatureData2) returned None")
    name_last_feature(adapter, "RootAndFootRounds")
    force_rebuild(adapter)
    raw_feature = part.FeatureByName("RootAndFootRounds")
    if raw_feature is None:
        raise RuntimeError("RootAndFootRounds: native part feature not found")
    feature = _early_bound(raw_feature, "IFeature")
    dims = list(_display_dimensions(feature, "RootAndFootRounds"))
    root_dims = [
        idim for idim in dims
        if math.isclose(_dim_value_mm(idim), INSIDE_ROOT_R, abs_tol=1e-6)
    ]
    if len(root_dims) != 1:
        committed = _early_bound(feature.GetDefinition(), "ISimpleFilletFeatureData2")
        if not committed.AccessSelections(model, None):
            raise RuntimeError("RootAndFootRounds: post-create AccessSelections failed")
        try:
            committed.IsMultipleRadius = True
            _telemetry.info(
                f"RootAndFootRounds post-create modify: items={int(committed.FilletItemsCount)} dims_before={len(dims)}"
            )
            _apply_fillet_item_radii(committed, len(selected), root_probe_m)
            if not feature.ModifyDefinition(committed, model, None):
                raise RuntimeError("RootAndFootRounds: post-create ModifyDefinition failed")
        except BaseException:
            committed.ReleaseSelectionAccess()
            raise
        force_rebuild(adapter)
        dims = list(_display_dimensions(feature, "RootAndFootRounds"))
        root_dims = [
            idim for idim in dims
            if math.isclose(_dim_value_mm(idim), INSIDE_ROOT_R, abs_tol=1e-6)
        ]
    _telemetry.info(
        f"RootAndFootRounds dimensions_mm={[round(_dim_value_mm(d), 6) for d in dims]}"
    )
    if len(root_dims) != 1:
        raise RuntimeError(
            f"RootAndFootRounds: expected one {INSIDE_ROOT_R:g} mm dimension, found {len(root_dims)} of {len(dims)}"
        )
    _bind(root_dims[0], "IDimension").Name = "InsideRootRadius"
    jobs.append(("InsideRootRadius@RootAndFootRounds", '"InsideRootR"'))


def _assert_matched_width_topology(adapter) -> None:
    """Prove the real foot sides are flush and no upright corner was rounded."""
    neck_z = FLANGE_Z[0] / 2.0
    foot_z = sum(FLANGE_Z) / 2.0
    foot_x = (FLANGE_X[0] - NECK_HALF_X) / 2.0
    requests = {"nose": CylinderFace(2.0 * NOSE_R, contains_z_mm=-NOSE_R / 2.0)}
    root_radius = INSIDE_ROOT_R
    root_center = (-NECK_HALF_X - root_radius, 0.0, FLANGE_Z[0] - root_radius)
    root_point = (
        root_center[0] + root_radius / math.sqrt(2.0), 0.0,
        root_center[2] + root_radius / math.sqrt(2.0),
    )
    requests["root_round"] = CylinderFace(
        2.0 * root_radius, contains_x_mm=root_point[0],
        contains_y_mm=0.0, contains_z_mm=root_point[2],
    )
    radius = FOOT_CORNER_R
    cylinders = {
        "nose": (0, (0.0, 0.0, 0.0), NOSE_R),
        "root_round": (1, root_center, root_radius),
    }
    probes = [("root_round", root_point)]
    for sign in (-1, 1):
        normal = (0.0, float(sign), 0.0)
        requests[f"neck_{sign}"] = PlanarFace(
            normal, NOSE_R, contains_x_mm=0.0, contains_z_mm=neck_z
        )
        requests[f"foot_{sign}"] = PlanarFace(
            normal, NOSE_R, contains_x_mm=foot_x, contains_z_mm=foot_z
        )
        # These are physical sharp head corners, not points on an untrimmed
        # surface. An accidental full-length FootCorners fillet removes them.
        probes.extend(
            (f"neck_{sign}", (x, sign * NOSE_R, neck_z))
            for x in (-NECK_HALF_X, NECK_HALF_X)
        )
        probes.extend(
            (f"neck_{sign}", (0.0, sign * NOSE_R, FLANGE_Z[0] + delta))
            for delta in (-FOOT_CORNER_R, 0.0, FOOT_CORNER_R)
        )
        probes.append((f"foot_{sign}", (foot_x, sign * NOSE_R, foot_z)))
        round_label = f"foot_round_{sign}"
        round_center = (0.0, sign * (NOSE_R - radius), FLANGE_Z[0] + radius)
        round_point = (
            foot_x, round_center[1] + sign * radius / math.sqrt(2.0),
            round_center[2] - radius / math.sqrt(2.0),
        )
        requests[round_label] = CylinderFace(
            2.0 * radius, contains_x_mm=foot_x,
            contains_y_mm=round_point[1], contains_z_mm=round_point[2],
        )
        cylinders[round_label] = (0, round_center, radius)
        probes.append((round_label, round_point))
        probes.extend(
            ("nose", (x, sign * NOSE_R / math.sqrt(2.0), -NOSE_R / math.sqrt(2.0)))
            for x in (-NECK_HALF_X, NECK_HALF_X)
        )
    faces = resolve_faces(adapter.currentModel, requests)
    for label, (axis, center, expected_radius) in cylinders.items():
        geometry = face_geometry(faces[label])
        if (
            geometry is None or len(geometry.parameters) != 7
            or not all(math.isfinite(float(value)) for value in geometry.parameters)
            or math.dist(
                tuple(abs(value) for value in geometry.parameters[3:6]),
                tuple(float(index == axis) for index in range(3)),
            ) > 1e-8
            or max(
                abs(geometry.parameters[index] * 1000.0 - center[index])
                for index in range(3) if index != axis
            ) > 1e-5
            or abs(geometry.parameters[6] * 1000.0 - expected_radius) > 1e-5
        ):
            raise RuntimeError(
                f"matched-width cut changed the native {label} radius or axis"
            )
    records = []
    for label, point in probes:
        raw = faces[label].GetClosestPointOn(*(value / 1000.0 for value in point))
        if raw is None or len(raw) != 5 or not all(math.isfinite(float(v)) for v in raw):
            raise RuntimeError(f"{label}: matched-width native closest point is unavailable")
        nearest = tuple(float(value) * 1000.0 for value in raw[:3])
        gap = math.dist(point, nearest)
        if gap > 1e-5:
            raise RuntimeError(
                f"{label}: foot step or altered head corner at {point}; native gap {gap:g} mm"
            )
        records.append({"face": label, "point_mm": point, "nearest_mm": nearest, "gap_mm": gap})
    evidence = json.dumps(records, sort_keys=True)
    _telemetry.info(f"matched-width native topology: {evidence}", auditJSON=evidence)


def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create part", adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    for name, value in (
        ("NoseR", NOSE_R),
        ("SeatToAxis", FLANGE_Z[1]),
        ("NeckThickness", NECK_THICKNESS),
        ("InsideRootR", INSIDE_ROOT_R),
    ):
        set_global(adapter, name, f"{value}mm")
    jobs = []
    dims = SketchDims()
    check("neck profile", adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    arc = check("semicircular nose", adapter.add_arc(0.0, 0.0, 0.0, -NOSE_R, 0.0, NOSE_R))
    lines = add_line_chain(adapter, [(0.0, NOSE_R), (-FLANGE_Z[1], NOSE_R), (-FLANGE_Z[1], -NOSE_R), (0.0, -NOSE_R)], close=False)
    set_sketch_direct_db(adapter, False)
    for first, second in ((f"{arc}.end", f"{lines[0]}.start"), (f"{arc}.start", f"{lines[2]}.end")):
        check("nose contour closes", adapter.add_sketch_constraint(first, second, "coincident"))
    check("nose centre", adapter.add_sketch_constraint(f"{arc}.center", "origin", "coincident"))
    for point in (f"{arc}.start", f"{arc}.end"):
        check("nose semicircle", adapter.add_sketch_constraint(point, "origin", "vertical_points"))
    check("nose radius", adapter.add_sketch_dimension(arc, None, "radial", NOSE_R))
    dims.record("NoseR", '"NoseR"')
    for line, relation in zip(lines, ("horizontal", "vertical", "horizontal"), strict=True):
        check("parallel straight neck", adapter.add_sketch_constraint(line, None, relation))
    dimension_between(adapter, f"{lines[0]}.end", "origin", "horizontal_distance", FLANGE_Z[1], "seat to nose axis")
    dims.record("SeatToAxis", '"SeatToAxis"')
    ensure_fully_defined(adapter, "neck profile")
    check("exit neck profile", adapter.exit_sketch())
    name_last_feature(adapter, "NeckProfile")
    jobs.extend(dims.apply(adapter, "NeckProfile"))
    check("centred neck", adapter.create_extrusion(ExtrusionParameters(depth=NECK_THICKNESS, both_directions=True)))
    name_last_feature(adapter, "Neck")
    jobs.append((name_dimensions(adapter, "Neck", ["NeckThickness"])[0], '"NeckThickness"'))

    dims = SketchDims()
    check("foot profile", adapter.create_sketch("Top"))
    points = list(FOOT_PROFILE)
    lines = add_line_chain(adapter, points)
    define_rectilinear_chain(adapter, lines, points, anchor=FOOT_PROFILE_ANCHOR, label="foot", dims=dims, names=list(FOOT_PROFILE_DIMENSIONS))
    ensure_fully_defined(adapter, "foot profile")
    check("exit foot profile", adapter.exit_sketch())
    name_last_feature(adapter, "FlangeProfile")
    jobs.extend(dims.apply(adapter, "FlangeProfile"))
    extrude_at_offset(adapter, FLANGE_Y[1] - FLANGE_Y[0], FLANGE_Y[0])
    name_last_feature(adapter, "Flange")
    name_dimensions(adapter, "Flange", ["FlangeHeight"])
    if FLANGE_X[1] != NECK_HALF_X:
        raise AssertionError("foot and neck must share the right face without a ledge")

    # The matched-width foot has no axial side-root bridge. Its inside X
    # root and two outside foot edges are solved together on the raw solid.
    _round_foot_root(adapter, jobs)
    # Only the two free-end edges remain foot corners. At +X the old picks
    # now lie on full-length upright edges and must never receive a fillet.
    check("rounded free-end foot corners", adapter.add_fillet(FOOT_CORNER_R, [[FLANGE_X[0], y, sum(FLANGE_Z) / 2.0] for y in FLANGE_Y], propagate=False))
    name_last_feature(adapter, "FootCorners")
    name_dimensions(adapter, "FootCorners", ["FootCornerR"])
    wizard_holes(adapter, CLEARANCE_SPEC, BRACKET_HOLE_POINTS, (0.0, 0.0, -1.0), "relocated plate-tap mounting holes", name="MountingHoles", expect_dia_mm=CLEARANCE_DIA, placement_dims=[((None, None), (None, None)) for _ in BRACKET_HOLE_POINTS])
    wizard_holes(adapter, TAP_SPEC, [(NECK_HALF_X, 0.0, 0.0)], (1.0, 0.0, 0.0), "lever through tap", name="LeverTap", expect_dia_mm=TAP_DRILL_DIA, placement_dims=[((None, None), (None, None))])
    _assert_placement_sketches_fully_defined(adapter)
    check("both tap mouth chamfers", adapter.add_chamfer(MOUTH_CHAMFER, [[x, TAP_DRILL_DIA / 2.0, 0.0] for x in (-NECK_HALF_X, NECK_HALF_X)]))
    name_last_feature(adapter, "MouthBreak")
    name_dimensions(adapter, "MouthBreak", ["MouthChamfer"])
    set_dimension_bilateral_tolerance(adapter, "MouthBreak", "MouthChamfer", *deviations(MOUTH_CHAMFER_BAND), display_unit=UNIT)
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
    _coordinates(adapter, jobs)
    force_rebuild(adapter)
    for dimension, expression in jobs:
        drive_dimension(adapter, dimension, expression)
    force_rebuild(adapter)
    # Exact nominal prismatic volume plus bounded small corner/chamfer changes.
    neck = NECK_THICKNESS * (2.0 * NOSE_R * FLANGE_Z[1] + math.pi * NOSE_R**2 / 2.0)
    foot = (FLANGE_X[1] - FLANGE_X[0]) * SIDE_PLATE_THICKNESS * (FLANGE_Y[1] - FLANGE_Y[0])
    overlap = NECK_THICKNESS * 2.0 * NOSE_R * SIDE_PLATE_THICKNESS
    holes = math.pi / 4.0 * (TAP_DRILL_DIA**2 * NECK_THICKNESS + 2.0 * CLEARANCE_DIA**2 * SIDE_PLATE_THICKNESS)
    expected = neck + foot - overlap - holes
    volume_check(adapter, "simple L with through tap and rounded corners", expected, 10.0)
    name_bore_axis(adapter, "Front Plane", 0.0, "Top Plane", 0.0, "threaded lever axis")
    set_dimension_symmetric_tolerance(adapter, "NeckProfile", "NoseR", NOSE_R_TOL, display_unit=UNIT)
    _author_dimension_callouts(adapter)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature, names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature, names)
    blank_reference_sketches(adapter, ("MountingCoordinates", "TapCoordinates"))
    apply_material(adapter, MATERIAL)
    apply_color(adapter, (0.12, 0.12, 0.13))  # blued, not bare steel
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE})
    report_mass_properties(adapter)
    force_rebuild(adapter)
    _assert_matched_width_topology(adapter)
    volume_check(adapter, "final native dimensions preserve L bracket", expected, 10.0)
    return save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
