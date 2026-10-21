r"""Reproduction script: magnifying-lever clamp (MHA-MG-02; book ch. 20 p. 48).

A vertical length of 1/2 in hex brass that slides along the magnifying lever
(#1559 owner ruling): the full-body quarter-inch lever passes across the
corners. The top #4-40 thumb screw pinches it; the bottom MHA-MG-04 rod
shoulder seats on the opposite end. Each tap entry has an actual-flat normal
location and a direct transverse bore-rim location, not an assumed common axis.

Layout (part frame, ``mg_magnifying_clamp_geom``): origin at the bottom-face
centre, hex axis +Y, corners on +/-X, flats square to +/-Z.

* ``HexProfile``: the 1/2 hex on the Top plane (sketch (x, y) -> model
  (X, -Z)), corners on the sketch's horizontal axis, extruded +Y as ``Block``
  (``Height``). The regular section centres only the nominal CAD origin.
  Five linked native dimensions own the flat and relative-axis locations.
* ``LeverBoreProfile``: the Ø6.50 drilled lever bore, a Right-plane circle on
  the hex axis at ``LeverBoreYDim``, cut mid-plane through both corners.
* ``ThumbTap``: blind Hole Wizard #4-40 from the top face on the hex axis,
  thread ending at the bore, drill to the bore axis.
* ``RodTap``: blind Hole Wizard #4-40 from the bottom face on the hex axis
  (``mg_rod_clamp_joint.ROD_TAP_SPEC``).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_mg_magnifying_clamp.py
"""

from __future__ import annotations

import math
import sys
from typing import Any

from _appearance import PANEL_BLACK, apply_color, apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _feature_tree import name_last_feature
from _gtol_face_resolve import resolve_faces
from _gtol_planar import PlanarFace
from _holes import blind_hole_volume_mm3, cross_hole_volume_mm3, wizard_holes
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_save import save_part_and_images
from _printed_tolerance import drilled_oversize_mm
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    blank_reference_sketches,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from mg_magnifying_clamp_geom import (
    BLOCK_HEIGHT,
    HEX_AC,
    HEX_AF,
    LEVER_BORE_DIA,
    LEVER_BORE_Y,
    RELATIVE_AXIS_BAND,
    ROD_TAP_DRILL_DIA,
    THUMB_TAP_DRILL_DEPTH,
    THUMB_TAP_SPEC,
    WALL_TARGET,
)
from mg_magnifying_clamp_spec import (
    AREA_HATCH_STYLE_PATTERN,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    PREF_MATERIAL_HATCH_PATTERN,
    PREF_MATERIAL_HATCH_STYLE,
    PREF_NO_OPTION,
    SECTION_HATCH_PATTERN,
)
from mg_rod_clamp_joint import ROD_TAP_DRILL_DEPTH, ROD_TAP_SPEC

PART_NAME = "mg-magnifying-clamp"
MATERIAL = "Brass"  # see _appearance.apply_material docstring

HEX_CORNER_RADIUS = HEX_AC / 2.0
BORE_R = LEVER_BORE_DIA / 2.0
DRILL_R = ROD_TAP_DRILL_DIA / 2.0
# The lever bore's mid-plane cut: past both corners.
BORE_CUT_DEPTH = HEX_AC + 2.0
# The corner radius is the flats over sqrt(3): the hex sketch's equation.
_CORNER_PER_AF = 1.0 / math.sqrt(3.0)

# swSelectType_e: both return ISketchPoint. A Hole Wizard placement point is
# external (25) while the separate bore-location witness sketch is active.
# Type alone is insufficient (25 can also denote an origin); IsSame must still
# identify the actual expected point. The converted witness segment stays 10.
_SKETCH_POINT_SELECTION_TYPES = (11, 25)  # swSelSKETCHPOINTS, swSelEXTSKETCHPOINTS

# --- Analytic volumes (mm^3) ---------------------------------------------------
V_HEX = math.sqrt(3.0) / 2.0 * HEX_AF**2 * BLOCK_HEIGHT
# The bore across the corners: over its cross-section the hex's chord along X
# is 2(R - |z|/sqrt(3)), so it removes 2R·πr² less (2/sqrt(3))·(4/3)r³
# (build_mg_output_fixture._bore_volume).
V_BORE = 2.0 * math.pi * HEX_CORNER_RADIUS * BORE_R**2 - 8.0 * BORE_R**3 / (
    3.0 * math.sqrt(3.0)
)
# The thumb tap drill to the bore axis, less its share of the bore's upper
# half; its point stops in the bore's air (mg_magnifying_clamp_spec proves it).
V_THUMB = (
    math.pi * DRILL_R**2 * THUMB_TAP_DRILL_DEPTH
    - cross_hole_volume_mm3(ROD_TAP_DRILL_DIA, LEVER_BORE_DIA) / 2.0
)
# The rod tap: a blind drill and point, wholly in solid under the bore.
V_ROD_TAP = blind_hole_volume_mm3(ROD_TAP_DRILL_DIA, ROD_TAP_DRILL_DEPTH)
V_TOTAL = V_HEX - V_BORE - V_THUMB - V_ROD_TAP


def _segment_identity(adapter: Any, entity: Any, *, stage: str, role: str) -> tuple[str, int, int, int]:
    """Resolve GetSketch through the live feature inventory, never cast it to IFeature.

    GetFeatures(False) includes absorbed/child sketches, without relying on tree
    order. GetSpecificFeature2 supplies ISketch only for documented sketch feature
    types. Compare those sketches, not a feature dispatch against a sketch.
    GetID is unique only with the owning sketch name and segment type. Nothing
    is cached across calls (in particular, across sketch renames or rebuilds).
    """
    import _telemetry

    kind = identifiers = owner_self = key = None
    candidates = []
    matches = []
    readback_error = None
    try:
        segment = _early_bound(entity, "ISketchSegment")
        kind = segment.GetType()
        identifiers = tuple(segment.GetID() or ())
        if type(kind) is not int or kind < 0:
            raise RuntimeError(f"invalid native segment type: {kind!r}")
        if len(identifiers) != 2 or any(type(value) is not int for value in identifiers):
            raise RuntimeError(f"invalid native segment ID pair: {identifiers!r}")
        raw_owner = segment.GetSketch()
        if raw_owner is None:
            raise RuntimeError("native segment has no owning sketch")
        owner = _early_bound(raw_owner, "ISketch")
        application = _early_bound(adapter.swApp, "ISldWorks")
        owner_self = application.IsSame(owner, owner)
        if type(owner_self) is not int or owner_self != 1:
            raise RuntimeError("native segment owner identity positive control failed")
        model = _early_bound(adapter.currentModel, "IModelDoc2")
        manager = _early_bound(model.FeatureManager, "IFeatureManager")
        features = manager.GetFeatures(False)
        if features is None:
            raise RuntimeError("native segment owner feature inventory unavailable")
        for raw_feature in features:
            if raw_feature is None:
                raise RuntimeError("native segment owner feature inventory contains null")
            feature = _early_bound(raw_feature, "IFeature")
            feature_type = feature.GetTypeName2()
            if type(feature_type) is not str or not feature_type:
                raise RuntimeError(f"native segment owner feature type unavailable: {feature_type!r}")
            if feature_type not in ("ProfileFeature", "3DProfileFeature"):
                continue
            name = feature.Name
            candidate = {"name": name, "feature_type": feature_type}
            candidates.append(candidate)
            if type(name) is not str or not name:
                raise RuntimeError(f"invalid native segment owner feature name: {name!r}")
            specific = feature.GetSpecificFeature2()
            if specific is None:
                raise RuntimeError(f"native segment owner sketch unavailable: {name!r}")
            sketch = _early_bound(specific, "ISketch")
            self_code = application.IsSame(sketch, sketch)
            code = application.IsSame(owner, sketch)
            candidate.update(self_code=self_code, owner_match_code=code)
            if type(self_code) is not int or self_code != 1:
                raise RuntimeError(f"native segment inventory sketch identity positive control failed: {name!r}")
            if type(code) is not int or code not in (0, 1):
                raise RuntimeError(f"native segment owner comparison unavailable: {name!r}, {code!r}")
            if code == 1:
                matches.append(name)
        if not matches:
            raise RuntimeError("native segment owner has no matching sketch feature")
        if len(matches) != 1:
            raise RuntimeError(f"native segment owner has ambiguous sketch features: {matches!r}")
        key = matches[0], kind, identifiers[0], identifiers[1]
        return key
    except Exception as exc:
        readback_error = exc
        raise RuntimeError(f"native segment identity readback failed: {exc}") from exc
    finally:
        _telemetry.info(
            f"clamp native segment owner: stage={stage}, role={role}, type={kind!r}, IDs={identifiers!r}, owner_self={owner_self!r}, candidates={candidates!r}, matches={matches!r}, key={key!r}, readback_error={readback_error!r}",
            operation_stage=stage,
            identity_role=role,
            segment_type=kind,
            segment_ids=identifiers,
            owner_self_identity_code=owner_self,
            owner_candidates=repr(candidates),
            owner_matches=tuple(matches),
            segment_identity=repr(key),
            segment_identity_readback_error=repr(readback_error),
        )


def _require_location_selection(
    adapter: Any, segment: Any, *, point: Any | None = None, stage: str
) -> None:
    """Require the actual point/segment pair, using documented segment identity.

    Direct IsSame of a raw selected dispatch and a bound ISketchSegment returned
    different on the native working point/flat path. Keep that result visible,
    but use the documented owner/type/GetID key for segment identity, not a
    direct dispatch comparison or coincident coordinates.
    """
    import _telemetry

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    manager = _early_bound(model.SelectionManager, "ISelectionMgr")
    application = _early_bound(adapter.swApp, "ISldWorks")
    count = int(manager.GetSelectedObjectCount2(-1))
    selected = tuple(manager.GetSelectedObject6(index, -1) for index in range(1, count + 1))
    types = tuple(int(manager.GetSelectedObjectType3(index, -1)) for index in range(1, count + 1))
    expected = ((1, point), (2, segment)) if point is not None else ((2, segment),)
    compared = tuple((index, entity) for index, entity in expected if index <= count and selected[index - 1] is not None)
    codes = tuple(int(application.IsSame(selected[index - 1], entity)) for index, entity in compared)
    self_codes = tuple(int(application.IsSame(entity, entity)) for _index, entity in expected)
    actual_key = expected_key = None
    readback_error = None
    error = ""
    if count != 2:
        error = "expected two selected objects"
    elif any(entity is None for entity in selected):
        error = "selected object unavailable"
    elif types[0] not in _SKETCH_POINT_SELECTION_TYPES or types[1] != 10:  # swSelSKETCHSEGS
        error = "expected native sketch point and sketch segment selection types"
    elif point is not None and self_codes[0] != 1:
        error = "native point identity positive control failed"
    elif point is not None and codes[0] != 1:
        error = "actual selected point identity differs or is unavailable"
    else:
        keys = []
        for role, entity in (("selected", selected[1]), ("expected", segment)):
            try:
                keys.append(_segment_identity(adapter, entity, stage=stage, role=role))
            except Exception as exc:
                keys.append(None)
                readback_error = exc
                error = "native segment identity unavailable"
        actual_key, expected_key = keys
        if not error and actual_key != expected_key:
            error = "actual selected segment owner/type/ID differs"
    detail = f"stage={stage}, count={count}, types={types}, compared={tuple(index for index, _entity in compared)}, IsSame={codes}, self={self_codes}, segment={actual_key!r}, expected_segment={expected_key!r}, readback_error={readback_error!r}"
    _telemetry.info(
        f"clamp native selection: {detail}",
        operation_stage=stage,
        selection_count=count,
        selected_types=types,
        selected_available=tuple(entity is not None for entity in selected),
        compared_selection_indices=tuple(index for index, _entity in compared),
        identity_codes=codes,
        self_identity_codes=self_codes,
        selected_segment_identity=repr(actual_key),
        expected_segment_identity=repr(expected_key),
        segment_identity_readback_error=repr(readback_error),
    )
    if error:
        raise RuntimeError(f"clamp location: {error}; {detail}") from readback_error


def _native_select(adapter: Any, entity: Any, interface: str, *, append: bool) -> None:
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    manager = _early_bound(model.SelectionManager, "ISelectionMgr")
    data = _early_bound(manager.CreateSelectData(), "ISelectData")
    data.Mark = 0
    if int(data.Mark) != 0 or _early_bound(entity, interface).Select4(append, data) is not True:
        raise RuntimeError(f"clamp location: cannot select {interface}")


def _has_conversion_source(adapter: Any, segment: Any, source: Any) -> bool:
    """Require a native external reference, not just equal coordinates."""
    native = _early_bound(segment, "ISketchSegment")
    application = _early_bound(adapter.swApp, "ISldWorks")
    for raw_relation in native.GetRelations() or ():
        relation = _early_bound(raw_relation, "ISketchRelation")
        for entity in relation.GetDefinitionEntities2() or ():
            if entity is not None and int(application.IsSame(entity, source)) == 1:
                return True
    return False


def _convert_location_source(adapter: Any, source: Any, interface: str) -> Any:
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    sketch = _early_bound(model.GetActiveSketch2(), "ISketch")
    application = _early_bound(adapter.swApp, "ISldWorks")
    previous = tuple(sketch.GetSketchSegments() or ())
    model.ClearSelection2(True)
    _native_select(adapter, source, interface, append=False)
    manager = _early_bound(adapter.currentSketchManager, "ISketchManager")
    if manager.SketchUseEdge3(False, False) is not True:
        raise RuntimeError("clamp location: native edge conversion failed")
    model.ClearSelection2(True)
    added = [candidate for candidate in sketch.GetSketchSegments() or () if not any(int(application.IsSame(candidate, old)) == 1 for old in previous)]
    if len(added) != 1 or not _has_conversion_source(adapter, added[0], source):
        raise RuntimeError("clamp location: conversion did not retain exactly one actual source entity")
    converted = _early_bound(added[0], "ISketchSegment")
    converted.ConstructionGeometry = True
    if converted.ConstructionGeometry is not True:
        raise RuntimeError("clamp location: converted geometry is not construction")
    return converted


def _line_endpoints_mm(edge: Any) -> tuple[tuple[float, ...], ...]:
    native = _early_bound(edge, "IEdge")
    points = []
    for raw in (native.GetStartVertex(), native.GetEndVertex()):
        if raw is None:
            raise RuntimeError("clamp location: a straight stock edge has no vertex")
        vertex = _early_bound(raw, "IVertex")
        points.append(tuple(float(value) * 1000.0 for value in vertex.GetPoint()))
    return tuple(points)


def _stock_edge(face: Any, endpoints: tuple[tuple[float, ...], tuple[float, ...]]) -> Any:
    matches = []
    for raw in _early_bound(face, "IFace2").GetEdges() or ():
        edge = _early_bound(raw, "IEdge")
        curve = _early_bound(edge.GetCurve(), "ICurve")
        if not curve.IsLine():
            continue
        actual = _line_endpoints_mm(edge)
        if any(all(math.dist(point, wanted) <= 0.005 for point, wanted in zip(order, endpoints, strict=True)) for order in (actual, actual[::-1])):
            matches.append(edge)
    if len(matches) != 1:
        raise RuntimeError(f"clamp location: stock boundary {endpoints!r} matched {len(matches)} edges")
    return matches[0]


def _tap_entry_circle(face: Any, end_y: float) -> Any:
    matches = []
    for raw in _early_bound(face, "IFace2").GetEdges() or ():
        edge = _early_bound(raw, "IEdge")
        curve = _early_bound(edge.GetCurve(), "ICurve")
        if not curve.IsCircle():
            continue
        p = tuple(float(value) for value in curve.CircleParams)
        if math.dist(p[:3], (0.0, end_y / 1000.0, 0.0)) <= 1e-7 and abs(p[6] * 1000.0 - DRILL_R) <= 0.005 and abs(abs(p[4]) - 1.0) <= 1e-6 and math.hypot(p[3], p[5]) <= 1e-6:
            matches.append(edge)
    if len(matches) != 1:
        raise RuntimeError(f"clamp location: actual tap entry at Y{end_y:g} matched {len(matches)} rims")
    return matches[0]


def _location_sources(adapter: Any) -> dict[str, tuple[str, Any, str, tuple[tuple[str, Any], ...]]]:
    """Sources are actual stock edges and actual cut/entry circles."""
    faces = resolve_faces(adapter.currentModel, {
        "top": PlanarFace((0.0, 1.0, 0.0), BLOCK_HEIGHT),
        "bottom": PlanarFace((0.0, -1.0, 0.0), 0.0),
        "zflat": PlanarFace((0.0, 0.0, 1.0), HEX_AF / 2.0),
    })
    a, r = HEX_AF / 2.0, HEX_CORNER_RADIUS
    sources = {}
    for prefix, key, y in (("ThumbTap", "top", BLOCK_HEIGHT), ("RodTap", "bottom", 0.0)):
        # One ordinary stock-flat location plus direct bore-rim location
        # controls both entry coordinates without a derived stock midplane.
        diagonal = _stock_edge(faces[key], ((r, y, 0.0), (r / 2.0, y, a)))
        circle = _tap_entry_circle(faces[key], y)
        sources[f"{prefix}LocationProfile"] = ("Top", circle, "IEntity", ((f"{prefix}FromDiagonalFlat", diagonal),))
    part = _early_bound(adapter.currentModel, "IPartDoc")
    feature = part.FeatureByName("LeverBoreProfile")
    if feature is None:
        raise RuntimeError("clamp location: actual bore-producing sketch is missing")
    sketch = _early_bound(_early_bound(feature, "IFeature").GetSpecificFeature2(), "ISketch")
    segments = tuple(sketch.GetSketchSegments() or ())
    if len(segments) != 1 or int(_early_bound(segments[0], "ISketchSegment").GetType()) != 1:
        raise RuntimeError("clamp location: bore-producing sketch is not one actual circle")
    flat = _stock_edge(faces["zflat"], ((r / 2.0, 0.0, a), (r / 2.0, BLOCK_HEIGHT, a)))
    sources["LeverBoreLocationProfile"] = ("Right", segments[0], "ISketchSegment", (("LeverBoreFromZFlat", flat),))
    return sources


def _measure_location(adapter: Any, center: Any, flat: Any, name: str) -> None:
    """Native perpendicular point-to-line measurement, never an adapter drive."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    application = _early_bound(adapter.swApp, "ISldWorks")
    # Entering a new sketch can reset input suppression (stock-carrier pattern).
    for preference in (10, 372, 520):
        application.SetUserPreferenceToggle(preference, False)
        if application.GetUserPreferenceToggle(preference) is not False:
            raise RuntimeError(f"clamp location: dimension input preference {preference} stayed enabled")
    model.ClearSelection2(True)
    _native_select(adapter, center, "ISketchPoint", append=False)
    _native_select(adapter, flat, "ISketchSegment", append=True)
    _require_location_selection(adapter, flat, point=center, stage=f"{name}.point-flat.before-create")
    raw = model.AddDimension2(0.02, 0.02, 0.0)
    model.ClearSelection2(True)
    if raw is None:
        raise RuntimeError(f"{name}: native point-to-flat dimension failed")
    display = _early_bound(raw, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    dimension.DrivenState = 1
    dimension.Name = name
    display.ShowParenthesis = False
    if int(dimension.DrivenState) != 1 or str(dimension.Name) != name or display.ShowParenthesis is not False:
        raise RuntimeError(f"{name}: native measured manufacturing dimension did not persist")
    if not math.isclose(float(dimension.SystemValue) * 1000.0, HEX_AF / 2.0, abs_tol=0.005):
        raise RuntimeError(f"{name}: measurement is not the normal distance to the actual flat")


def _tap_placement_points(adapter: Any) -> dict[str, Any]:
    part = _early_bound(adapter.currentModel, "IPartDoc")
    points = {}
    for name in ("ThumbTap", "RodTap"):
        feature = part.FeatureByName(name)
        if feature is None:
            raise RuntimeError(f"{name}: native Hole Wizard feature is missing")
        child = _early_bound(feature, "IFeature").GetFirstSubFeature()
        while child is not None:
            native = _early_bound(child, "IFeature")
            if str(native.GetTypeName2()) == "ProfileFeature":
                sketch = _early_bound(native.GetSpecificFeature2(), "ISketch")
                candidates = tuple(sketch.GetSketchPoints2() or ())
                if len(candidates) == 1 and not tuple(sketch.GetSketchSegments() or ()):
                    status = sketch.GetConstrainedStatus()
                    if type(status) is not int or status != 3:
                        raise RuntimeError(f"{name}: native placement is not fully defined: {status!r}")
                    points[f"{name}ToBoreRim"] = _early_bound(candidates[0], "ISketchPoint")
                    break
            child = native.GetNextSubFeature()
        else:
            raise RuntimeError(f"{name}: expected one actual native placement point")
    return points


def _select_bore_rim(adapter: Any, circle: Any) -> None:
    """Give the exact selected circle a real rim pick before dimension creation.

    The Wizard points share the circle's transverse centre coordinate. An
    unspecified centre pick can request a zero horizontal span before the later
    near-arc endpoint setting can run. Native selection points distinguish the
    rim without replacing either attached entity or adding witness geometry.
    """
    from solidworks_mcp.adapters.com_variant import double_array
    import _telemetry

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    sketch = _early_bound(model.GetActiveSketch2(), "ISketch")
    arc = _early_bound(circle, "ISketchArc")
    center = _early_bound(arc.GetCenterPoint2(), "ISketchPoint")
    radius = float(arc.GetRadius())
    if not math.isfinite(radius) or radius <= 0.0:
        raise RuntimeError("clamp location: invalid native bore radius")
    rim = (float(center.X) + radius, float(center.Y), 0.0)
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    inverse = _early_bound(transform.Inverse(), "IMathTransform")
    application = _early_bound(adapter.swApp, "ISldWorks")
    utility = _early_bound(application.GetMathUtility(), "IMathUtility")
    point = _early_bound(utility.CreatePoint(double_array(list(rim))), "IMathPoint")
    projected = _early_bound(point.MultiplyTransform(inverse), "IMathPoint")
    coordinates = tuple(float(value) for value in (projected.ArrayData or ()))
    if len(coordinates) != 3 or not all(math.isfinite(value) for value in coordinates):
        raise RuntimeError("clamp location: native bore-rim transform failed")
    manager = _early_bound(model.SelectionManager, "ISelectionMgr")
    _require_location_selection(adapter, circle, stage="bore-rim.before-set-selection-point")
    accepted = retained = readback_error = None
    try:
        accepted = manager.SetSelectionPoint2(2, -1, coordinates[0], coordinates[1], coordinates[2])
        raw_pick = manager.GetSelectionPointInSketchSpace2(2, -1)
        if raw_pick is None:
            raise RuntimeError("native sketch-space selection point unavailable")
        retained = tuple(float(value) for value in raw_pick)
    except Exception as exc:
        readback_error = exc
    _telemetry.info(
        f"clamp native rim selection: sketch={rim!r}, model={coordinates!r}, accepted={accepted!r}, retained_sketch={retained!r}, readback_error={readback_error!r}",
        operation_stage="bore-rim.selection-point-readback",
        rim_sketch_m=rim,
        requested_model_m=coordinates,
        selection_point_accepted=accepted,
        retained_sketch_m=retained,
        selection_point_readback_error=repr(readback_error),
    )
    if readback_error is not None:
        raise RuntimeError("clamp location: native bore-rim selection point readback unavailable") from readback_error
    if accepted is not True:
        raise RuntimeError("clamp location: native bore-rim selection point failed")
    if len(retained) != 3 or any(not math.isfinite(actual) or abs(actual - expected) > 1e-10 for actual, expected in zip(retained, rim, strict=True)):
        raise RuntimeError("clamp location: native bore-rim selection point was not retained")


def _assert_relative_attachment(adapter: Any, display: Any, point: Any, circle: Any, *, name: str, stage: str) -> None:
    """Verify actual part-sketch attachments before and after the final rebuild."""
    import _telemetry

    attached = types = ()
    dangling = point_code = point_self = actual_key = expected_key = None
    readback_error = None
    try:
        display = _early_bound(display, "IDisplayDimension")
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        attached = tuple(annotation.GetAttachedEntities3() or ())
        types = tuple(int(value) for value in (annotation.GetAttachedEntityTypes() or ()))
        dangling = annotation.IsDangling()
        point_indices = tuple(index for index, kind in enumerate(types) if kind in _SKETCH_POINT_SELECTION_TYPES)
        if len(attached) != 2 or len(types) != 2 or len(point_indices) != 1 or types.count(10) != 1 or dangling is not False or any(entity is None for entity in attached):
            raise RuntimeError("invalid native point/circle attachments")
        application = _early_bound(adapter.swApp, "ISldWorks")
        point_self = application.IsSame(point, point)
        point_code = application.IsSame(attached[point_indices[0]], point)
        expected_key = _segment_identity(adapter, circle, stage=stage, role="expected-attachment")
        actual_key = _segment_identity(adapter, attached[types.index(10)], stage=stage, role="actual-attachment")
        if type(point_self) is not int or point_self != 1 or type(point_code) is not int or point_code != 1 or actual_key != expected_key:
            raise RuntimeError("native attachment identity differs")
    except Exception as exc:
        readback_error = exc
    detail = f"stage={stage}, count={len(attached)}, types={types}, dangling={dangling!r}, point_IsSame={point_code!r}, point_self={point_self!r}, segment={actual_key!r}, expected_segment={expected_key!r}, readback_error={readback_error!r}"
    _telemetry.info(
        f"clamp native attachment: {detail}",
        operation_stage=stage,
        attachment_count=len(attached),
        attached_types=types,
        dangling=dangling,
        point_identity_code=point_code,
        point_self_identity_code=point_self,
        attached_segment_identity=repr(actual_key),
        expected_segment_identity=repr(expected_key),
        attachment_readback_error=repr(readback_error),
    )
    if readback_error is not None:
        raise RuntimeError(f"{name}: {readback_error}; {detail}") from readback_error


def _measure_relative_axis(adapter: Any, point: Any, circle: Any, name: str) -> None:
    """Actual Wizard point to actual bore rim, transverse on the Right plane."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    model.ClearSelection2(True)
    _native_select(adapter, point, "ISketchPoint", append=False)
    _native_select(adapter, circle, "ISketchSegment", append=True)
    _require_location_selection(adapter, circle, point=point, stage=f"{name}.point-circle.after-select")
    _select_bore_rim(adapter, circle)
    raw = model.AddHorizontalDimension2(0.0, 0.02, 0.02)
    model.ClearSelection2(True)
    if raw is None:
        raise RuntimeError(f"{name}: native tap-point to bore-rim dimension failed")
    display = _early_bound(raw, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    dimension.DrivenState = 1
    dimension.Name = name
    display.ShowParenthesis = False
    circular = [index for index in (1, 2) if int(dimension.GetArcEndCondition(index)) != 0]
    if len(circular) != 1:
        raise RuntimeError(f"{name}: relative location does not have one actual circular endpoint")
    endpoint = circular[0]
    if int(dimension.SetArcEndCondition(endpoint, 2)) != 0 or int(dimension.GetArcEndCondition(endpoint)) != 2:
        raise RuntimeError(f"{name}: native near bore-rim endpoint was not retained")
    model.GraphicsRedraw2()
    if int(dimension.DrivenState) != 1 or str(dimension.Name) != name or bool(display.ShowParenthesis):
        raise RuntimeError(f"{name}: measured relative-axis ownership/ink was not retained")
    _assert_relative_attachment(adapter, display, point, circle, name=name, stage=f"{name}.after-create")
    if not math.isclose(float(dimension.SystemValue) * 1000.0, BORE_R, abs_tol=1e-5):
        raise RuntimeError(f"{name}: native attached point/circle dimension does not measure the bore radius")


async def _location_profiles(adapter: Any) -> None:
    sources = _location_sources(adapter)
    for feature, (plane, circle, interface, flats) in sources.items():
        check(f"create_sketch {feature}", await adapter.create_sketch(plane))
        converted = _convert_location_source(adapter, circle, interface)
        arc = _early_bound(converted, "ISketchArc")
        center = _early_bound(arc.GetCenterPoint2(), "ISketchPoint")
        for name, flat in flats:
            _measure_location(adapter, center, _convert_location_source(adapter, flat, "IEntity"), name)
        if feature == "LeverBoreLocationProfile":
            for name, point in _tap_placement_points(adapter).items():
                _measure_relative_axis(adapter, point, converted, name)
        model = _early_bound(adapter.currentModel, "IModelDoc2")
        sketch = _early_bound(model.GetActiveSketch2(), "ISketch")
        status = sketch.GetConstrainedStatus()
        if type(status) is not int or status != 3:
            raise RuntimeError(f"{feature}: linked witness is not fully defined: {status!r}")
        check(f"exit_sketch {feature}", await adapter.exit_sketch())
        name_last_feature(adapter, feature)
        if feature == "LeverBoreLocationProfile":
            for name in _tap_placement_points(adapter):
                set_dimension_bilateral_tolerance(adapter, feature, name, -RELATIVE_AXIS_BAND, RELATIVE_AXIS_BAND)
    blank_reference_sketches(adapter, tuple(sources))


def _assert_location_profiles(adapter: Any) -> None:
    part = _early_bound(adapter.currentModel, "IPartDoc")
    for feature, (_plane, source_circle, _interface, flats) in _location_sources(adapter).items():
        native_feature = _early_bound(part.FeatureByName(feature), "IFeature")
        sketch = _early_bound(native_feature.GetSpecificFeature2(), "ISketch")
        segments = tuple(sketch.GetSketchSegments() or ())
        if len(segments) != len(flats) + 1 or sketch.GetConstrainedStatus() != 3:
            raise RuntimeError(f"{feature}: native linked witness changed after rebuild")
        for source in (source_circle, *(edge for _name, edge in flats)):
            if sum(_has_conversion_source(adapter, segment, source) for segment in segments) != 1:
                raise RuntimeError(f"{feature}: native source identity did not survive rebuild")
        for name, _edge in flats:
            display, dimension = _named_dimension(adapter, feature, name)
            if int(dimension.DrivenState) != 1 or bool(display.ShowParenthesis) or not math.isclose(float(dimension.SystemValue) * 1000.0, HEX_AF / 2.0, abs_tol=0.005):
                raise RuntimeError(f"{name}: imported location's native measurement changed")
        if feature == "LeverBoreLocationProfile":
            circle = next(segment for segment in segments if _has_conversion_source(adapter, segment, source_circle))
            radius = float(_early_bound(circle, "ISketchArc").GetRadius()) * 1000.0
            if HEX_AF / 2.0 - radius < WALL_TARGET:
                raise RuntimeError("LeverBore: actual model has no room for its finished wall requirement")
            for name, point in _tap_placement_points(adapter).items():
                display, dimension = _named_dimension(adapter, feature, name)
                if int(dimension.DrivenState) != 1 or bool(display.ShowParenthesis):
                    raise RuntimeError(f"{name}: native relative-axis measurement changed")
                _assert_relative_attachment(adapter, display, point, circle, name=name, stage=f"{name}.after-rebuild")
                if not math.isclose(float(dimension.SystemValue) * 1000.0, radius, abs_tol=1e-5):
                    raise RuntimeError(f"{name}: attached relative-axis measurement changed")
                tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
                if int(tolerance.Type) != 2 or not math.isclose(float(tolerance.GetMinValue()) * 1000.0, -RELATIVE_AXIS_BAND, abs_tol=1e-9) or not math.isclose(float(tolerance.GetMaxValue()) * 1000.0, RELATIVE_AXIS_BAND, abs_tol=1e-9):
                    raise RuntimeError(f"{name}: native relative-axis acceptance band changed")
                if sorted(int(dimension.GetArcEndCondition(index)) for index in (1, 2)) != [0, 2]:
                    raise RuntimeError(f"{name}: native rim endpoint changed")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units.
    for name, value in (
        ("HexAf", HEX_AF),
        ("BlockHeight", BLOCK_HEIGHT),
        ("LeverBoreDia", LEVER_BORE_DIA),
        ("LeverBoreY", LEVER_BORE_Y),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # --- Hex block: the bar's section on the Top plane, extruded up +Y --------
    drive_jobs += await _hex_profile(adapter)
    check(
        "extrude block",
        await adapter.create_extrusion(ExtrusionParameters(depth=BLOCK_HEIGHT)),
    )
    name_last_feature(adapter, "Block")
    (height,) = name_dimensions(adapter, "Block", ["Height"])
    drive_jobs.append((height, '"BlockHeight"'))
    volume = await volume_check(adapter, "hex block", V_HEX, 0.005 * V_HEX)
    await bbox_extent_check(adapter, "block height", "y", BLOCK_HEIGHT)
    await bbox_extent_check(adapter, "hex across the flats", "z", HEX_AF)
    await bbox_extent_check(adapter, "hex across the corners", "x", HEX_AC)

    # --- Lever bore along X through both corners ---------------------------------
    # On the hex axis (sketch x = 0 is model Z = 0), so define_circle emits the
    # height then the diameter -- the x slot is ignored.
    lever = SketchDims()
    check("create_sketch lever bore", await adapter.create_sketch("Right"))
    await define_circle(
        adapter,
        0.0,
        LEVER_BORE_Y,
        BORE_R,
        "lever bore",
        dims=lever,
        names=("LeverCz", "LeverBoreYDim", "LeverBoreDiaDim"),
        drives=(None, '"LeverBoreY"', '"LeverBoreDia"'),
    )
    await ensure_fully_defined(adapter, "lever bore sketch")
    check("exit_sketch lever bore", await adapter.exit_sketch())
    name_last_feature(adapter, "LeverBoreProfile")
    drive_jobs += lever.apply(adapter, "LeverBoreProfile")
    check(
        "cut lever bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=BORE_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "LeverBore")
    volume = await volume_check(adapter, "lever bore", volume - V_BORE, 0.01 * V_BORE)

    # --- Thumb-screw tap: top face, hex axis, into the lever bore ---------------
    thumb = wizard_holes(
        adapter,
        THUMB_TAP_SPEC,
        [[0.0, BLOCK_HEIGHT, 0.0]],
        (0.0, 1.0, 0.0),
        f"thumb-screw tap ({THUMB_TAP_SPEC.size} into the lever bore)",
        name="ThumbTap",
        expect_dia_mm=ROD_TAP_DRILL_DIA,
        placement_dims=[((None, None), (None, None))],
    )
    drive_jobs += thumb.placement_drive_jobs
    volume = await volume_check(
        adapter, "thumb-screw tap", volume - V_THUMB, 0.03 * V_THUMB
    )

    # --- Rod tap: bottom face (outward normal -Y), hex axis, blind -------------
    rod = wizard_holes(
        adapter,
        ROD_TAP_SPEC,
        [[0.0, 0.0, 0.0]],
        (0.0, -1.0, 0.0),
        f"vertical-rod tap ({ROD_TAP_SPEC.size} blind, MHA-MG-04 seat)",
        name="RodTap",
        expect_dia_mm=ROD_TAP_DRILL_DIA,
        placement_dims=[((None, None), (None, None))],
    )
    drive_jobs += rod.placement_drive_jobs
    volume = await volume_check(
        adapter, "vertical-rod tap", volume - V_ROD_TAP, 0.03 * V_ROD_TAP
    )

    # Named lever-bore axis (local X through (y=LEVER_BORE_Y, z=0)) so the clamp
    # rides the magnifying lever as a concentric slider in the assembly.
    await name_bore_axis(
        adapter, "Top Plane", LEVER_BORE_Y, "Front Plane", 0.0, "lever bore axis",
        drive_a='"LeverBoreY"', drive_jobs=drive_jobs,
    )

    # Independent ordinary entry locations are measured from real stock flats;
    # nominal origin-coincident hole placement is not a tolerance statement.
    await _location_profiles(adapter)

    # Deferred drive equations, then re-check neutrality.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    _assert_location_profiles(adapter)
    await volume_check(
        adapter, "driven magnifying clamp (equations neutral)", V_TOTAL, 0.005 * V_TOTAL
    )

    await apply_material(adapter, MATERIAL)
    _set_section_hatch(adapter)
    # ch20 p.47 (img07) + p.46: the clamp block is BLACKENED brass (reads
    # dark against the bright lever rod and the bright thumb screw).
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)

    # Places are the tolerance statement (drawing-guidelines.md rule 3): the
    # part carries them, the drawing reads them back.
    set_dimension_bilateral_tolerance(adapter, "LeverBoreProfile", "LeverBoreDiaDim", 0.0, drilled_oversize_mm())
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


def _set_section_hatch(adapter: Any) -> None:
    """Give the part's Material Properties crosshatch the section pattern,
    after the material (which applies its own), and prove it by read-back:
    the drawing's section hatches from it (mg_magnifying_clamp_spec)."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    extension = _early_bound(model.Extension, "IModelDocExtension")
    extension.SetUserPreferenceInteger(
        PREF_MATERIAL_HATCH_STYLE, PREF_NO_OPTION, AREA_HATCH_STYLE_PATTERN
    )
    extension.SetUserPreferenceString(
        PREF_MATERIAL_HATCH_PATTERN, PREF_NO_OPTION, SECTION_HATCH_PATTERN
    )
    style = int(
        extension.GetUserPreferenceInteger(PREF_MATERIAL_HATCH_STYLE, PREF_NO_OPTION)
    )
    pattern = str(
        extension.GetUserPreferenceString(PREF_MATERIAL_HATCH_PATTERN, PREF_NO_OPTION)
    )
    if style != AREA_HATCH_STYLE_PATTERN or pattern != SECTION_HATCH_PATTERN:
        raise RuntimeError(
            f"clamp material crosshatch read back style {style}, pattern "
            f"{pattern!r}; wanted {AREA_HATCH_STYLE_PATTERN}, {SECTION_HATCH_PATTERN!r}"
        )


async def _hex_profile(adapter: Any) -> list[tuple[str, str]]:
    """The 1/2 hex on the Top plane, corners on the sketch's horizontal axis.

    The ``build_mg_output_fixture._hex_profile`` technique turned a quarter:
    both corners sit on the horizontal through the origin (model X), each a
    corner radius off it; each flat is horizontal (model Z = +/-AF/2), with
    equal sides either side of it.  The two flats equal centre the origin
    between them; the corner radius tied to the flats makes the section
    regular.  The flats are dimensioned point to point across the hex, between
    the ends of the two flats at -X: in the projected top view those are its
    upper vertices, so the dimension above it draws no extension line along a
    flat and leaves the right-hand flat clear for the thumb tap's leader.
    """
    half_af, corner = HEX_AF / 2.0, HEX_CORNER_RADIUS
    points = [
        (corner, 0.0),
        (corner / 2.0, half_af),
        (-corner / 2.0, half_af),
        (-corner, 0.0),
        (-corner / 2.0, -half_af),
        (corner / 2.0, -half_af),
    ]
    hexd = SketchDims()
    check("create_sketch hex", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    for flat in (lines[1], lines[4]):
        check(
            f"hex flat {flat} horizontal",
            await adapter.add_sketch_constraint(flat, None, "horizontal"),
        )
    for first, second in ((0, 1), (1, 2), (3, 4), (4, 5)):
        check(
            f"hex sides {first}={second}",
            await adapter.add_sketch_constraint(lines[first], lines[second], "equal"),
        )
    # Equal flats, equal halves: the hex axis centred between the flats.
    check(
        "hex flats equal (axis centred)",
        await adapter.add_sketch_constraint(lines[1], lines[4], "equal"),
    )
    corner_drive = f'"HexAf" * {_CORNER_PER_AF!r}'
    await anchor_point_to_origin(adapter, f"{lines[0]}.start", corner, 0.0, "hex +X corner")
    hexd.record("HexCornerPlus", corner_drive)
    await anchor_point_to_origin(adapter, f"{lines[3]}.start", -corner, 0.0, "hex -X corner")
    hexd.record("HexCornerMinus", corner_drive)
    await dimension_between(
        adapter,
        f"{lines[1]}.end",
        f"{lines[4]}.start",
        "vertical_distance",
        HEX_AF,
        "hex across the flats",
    )
    hexd.record("HexAf", '"HexAf"')
    await ensure_fully_defined(adapter, "hex profile")
    check("exit_sketch hex", await adapter.exit_sketch())
    name_last_feature(adapter, "HexProfile")
    return hexd.apply(adapter, "HexProfile")


if __name__ == "__main__":
    sys.exit(run_build(build))
