r"""Reproduction script: magnifying-lever clamp (MHA-MG-02; book ch. 20 p. 48).

A vertical length of 1/2 in hex brass that slides along the magnifying lever
(#1559 owner ruling): the full-body quarter-inch lever passes across the
corners. The top #4-40 thumb screw pinches it; the bottom MHA-MG-04 rod
shoulder seats on the opposite end. Each tap entry has actual diagonal-flat
and common Z-flat locations; nominal common axes are not manufactured authority.

Layout (part frame, ``mg_magnifying_clamp_geom``): origin at the bottom-face
centre, hex axis +Y, corners on +/-X, flats square to +/-Z.

* ``HexProfile``: the 1/2 hex on the Top plane (sketch (x, y) -> model
  (X, -Z)), corners on the sketch's horizontal axis, extruded +Y as ``Block``
  (``Height``). The regular section centres only the nominal CAD origin.
  Five linked native dimensions own the two diagonal and three common-flat locations.
* ``LeverBoreProfile``: the Ø6.50 drilled lever bore, a Right-plane circle on
  the hex axis at ``LeverBoreYDim``, cut mid-plane through both corners.
* ``ThumbTap``: blind Hole Wizard #4-40 from the top face on the hex axis,
  thread ending at the bore, drill to the bore axis.
* ``RodTap``: blind Hole Wizard #4-40 from the bottom face on the hex axis
  (``mg_rod_clamp_joint.ROD_TAP_SPEC``).
* ``REFERENCE_SKETCHES`` names the three actual-source location witnesses;
  those names drive their creation and the part saves all three hidden. The
  drawing imports their dimensions through ``_drawing_hidden_sketches``.

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
from _feature_tree import name_last_feature
from _gtol_face_resolve import resolve_faces
from _gtol_planar import PlanarFace
from _holes import blind_hole_volume_mm3, cross_hole_volume_mm3, wizard_holes
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_save import save_part_and_images
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
    ROD_TAP_DRILL_DIA,
    THUMB_TAP_DRILL_DEPTH,
    THUMB_TAP_SPEC,
    WALL_FLOOR,
)
from mg_magnifying_clamp_spec import (
    AREA_HATCH_STYLE_PATTERN,
    DRAWING_DIMENSIONS,
    HEX_AF_PREFIX,
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
REFERENCE_SKETCHES = (
    "ThumbTapLocationProfile",
    "RodTapLocationProfile",
    "LeverBoreLocationProfile",
)

HEX_CORNER_RADIUS = HEX_AC / 2.0
BORE_R = LEVER_BORE_DIA / 2.0
DRILL_R = ROD_TAP_DRILL_DIA / 2.0
# The lever bore's mid-plane cut: past both corners.
BORE_CUT_DEPTH = HEX_AC + 2.0
# The corner radius is the flats over sqrt(3): the hex sketch's equation.
_CORNER_PER_AF = 1.0 / math.sqrt(3.0)

# swSelectType_e: both return ISketchPoint. A Hole Wizard placement point is
# external (25) while the separate bore-location witness sketch is active.
# Type alone is insufficient (25 can also denote an origin); _point_identity
# must prove the actual expected point. The converted witness segment stays 10.
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


def _sketch_owners(adapter: Any) -> tuple[tuple[str, Any], ...]:
    """Retain this stage's actual feature/sketch pairs, never across a rebuild."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    manager = _early_bound(model.FeatureManager, "IFeatureManager")
    features = manager.GetFeatures(False)
    if features is None:
        raise RuntimeError("native sketch owner feature inventory unavailable")
    application = _early_bound(adapter.swApp, "ISldWorks")
    owners = []
    for raw_feature in features:
        if raw_feature is None:
            raise RuntimeError("native sketch owner feature inventory contains null")
        feature = _early_bound(raw_feature, "IFeature")
        feature_type = feature.GetTypeName2()
        if type(feature_type) is not str or not feature_type:
            raise RuntimeError(f"native sketch owner feature type unavailable: {feature_type!r}")
        if feature_type not in ("ProfileFeature", "3DProfileFeature"):
            continue
        name = feature.Name
        if type(name) is not str or not name:
            raise RuntimeError(f"invalid native sketch owner feature name: {name!r}")
        specific = feature.GetSpecificFeature2()
        if specific is None:
            raise RuntimeError(f"native sketch owner sketch unavailable: {name!r}")
        sketch = _early_bound(specific, "ISketch")
        code = application.IsSame(sketch, sketch)
        if type(code) is not int or code != 1:
            raise RuntimeError(f"native inventory sketch identity positive control failed: {name!r}")
        owners.append((name, sketch))
    return tuple(owners)


def _sketch_owner_name(adapter: Any, raw_owner: Any, readback: dict[str, Any], owners: tuple[tuple[str, Any], ...] | None) -> str:
    """Read fresh identity against the stage's actual sketch owners."""
    if raw_owner is None:
        raise RuntimeError("native sketch entity has no owning sketch")
    owner = _early_bound(raw_owner, "ISketch")
    application = _early_bound(adapter.swApp, "ISldWorks")
    readback["self"] = application.IsSame(owner, owner)
    if type(readback["self"]) is not int or readback["self"] != 1:
        raise RuntimeError("native sketch owner identity positive control failed")
    if owners is None:
        owners = _sketch_owners(adapter)
    for name, sketch in owners:
        code = application.IsSame(owner, sketch)
        readback["candidates"].append({"name": name, "owner_match_code": code})
        if type(code) is not int or code not in (0, 1):
            raise RuntimeError(f"native sketch owner comparison unavailable: {name!r}, {code!r}")
        if code == 1:
            readback["matches"].append(name)
    if len(readback["matches"]) != 1:
        raise RuntimeError(f"native sketch owner has no unique matching sketch feature: {readback['matches']!r}")
    return readback["matches"][0]


def _segment_identity(adapter: Any, entity: Any, *, stage: str, role: str, owners: tuple[tuple[str, Any], ...] | None = None) -> tuple[str, int, int, int]:
    """Fresh actual owner/type/ordered-ID key; never cast ISketch to IFeature."""
    import _telemetry

    kind = identifiers = key = readback_error = None
    owner_readback = {"self": None, "candidates": [], "matches": []}
    try:
        segment = _early_bound(entity, "ISketchSegment")
        kind = segment.GetType()
        identifiers = tuple(segment.GetID() or ())
        if type(kind) is not int or kind < 0:
            raise RuntimeError(f"invalid native segment type: {kind!r}")
        if len(identifiers) != 2 or any(type(value) is not int for value in identifiers):
            raise RuntimeError(f"invalid native segment ID pair: {identifiers!r}")
        name = _sketch_owner_name(adapter, segment.GetSketch(), owner_readback, owners)
        key = name, kind, identifiers[0], identifiers[1]
        return key
    except Exception as exc:
        readback_error = exc
        raise RuntimeError(f"native segment identity readback failed: {exc}") from exc
    finally:
        _telemetry.info(
            f"clamp native segment owner: stage={stage}, role={role}, type={kind!r}, IDs={identifiers!r}, owner={owner_readback!r}, key={key!r}, readback_error={readback_error!r}",
            operation_stage=stage, identity_role=role, segment_type=kind, segment_ids=identifiers,
            owner_self_identity_code=owner_readback["self"], owner_candidates=repr(owner_readback["candidates"]),
            owner_matches=tuple(owner_readback["matches"]), segment_identity=repr(key),
            segment_identity_readback_error=repr(readback_error),
        )


def _point_identity(adapter: Any, entity: Any, *, stage: str, role: str, owners: tuple[tuple[str, Any], ...] | None = None) -> tuple[str, str, int, int]:
    """Official point type + actual owner name + ordered GetID; never persistent."""
    import pythoncom
    import _telemetry
    from solidworks_mcp.adapters._generated.sldworks_2026 import ISketchPoint, ISketchSegment

    identifiers = self_code = key = readback_error = None
    queries = []
    owner_readback = {"self": None, "candidates": [], "matches": []}
    try:
        for interface, cls in (("ISketchPoint", ISketchPoint), ("ISketchSegment", ISketchSegment)):
            query = {"interface": interface, "iid": str(cls.CLSID), "supported": None, "hresult": None, "error": None}
            queries.append(query)
            try:
                pointer = entity._oleobj_.QueryInterface(cls.CLSID, pythoncom.IID_IUnknown)
                if pointer is None:
                    raise RuntimeError("native QueryInterface returned no interface pointer")
                query.update(supported=True, hresult=0)
            except pythoncom.com_error as exc:
                query["hresult"] = exc.hresult
                if exc.hresult == -2147467262:
                    query["supported"] = False
                else:
                    query["error"] = repr(exc)
            except Exception as exc:
                query["error"] = repr(exc)
        if queries[0]["supported"] is not True or queries[1]["supported"] is not False:
            raise RuntimeError("native point interface is ambiguous, unsupported or unavailable")
        point = _early_bound(entity, "ISketchPoint")
        application = _early_bound(adapter.swApp, "ISldWorks")
        self_code = application.IsSame(point, point)
        if type(self_code) is not int or self_code != 1:
            raise RuntimeError("native point identity positive control failed")
        identifiers = tuple(point.GetID() or ())
        if len(identifiers) != 2 or any(type(value) is not int for value in identifiers):
            raise RuntimeError(f"invalid native point ID pair: {identifiers!r}")
        name = _sketch_owner_name(adapter, point.GetSketch(), owner_readback, owners)
        key = name, "ISketchPoint", identifiers[0], identifiers[1]
        return key
    except Exception as exc:
        readback_error = exc
        raise RuntimeError(f"native point identity readback failed: {exc}") from exc
    finally:
        _telemetry.info(
            f"clamp native point identity: stage={stage}, role={role}, QI={queries!r}, self={self_code!r}, IDs={identifiers!r}, owner={owner_readback!r}, key={key!r}, error={readback_error!r}",
            operation_stage=stage, identity_role=role, point_interface_queries=repr(queries),
            point_self_identity_code=self_code, point_ids=identifiers, point_identity=repr(key),
            owner_self_identity_code=owner_readback["self"], owner_candidates=repr(owner_readback["candidates"]),
            owner_matches=tuple(owner_readback["matches"]), point_identity_readback_error=repr(readback_error),
        )


def _require_location_selection(
    adapter: Any, segment: Any, *, point: Any | None = None, stage: str
) -> None:
    """Require actual point/segment owner/type/ordered-ID identities, not dispatch equality."""
    import _telemetry

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    manager = _early_bound(model.SelectionManager, "ISelectionMgr")
    count = actual_key = expected_key = None
    selected_list, type_list = [], []
    point_keys = ()
    readback_error = None
    error = ""
    try:
        count = manager.GetSelectedObjectCount2(-1)
        if type(count) is not int or count < 0:
            error = "native selection count unavailable"
        else:
            for index in range(1, count + 1):
                type_list.append(manager.GetSelectedObjectType3(index, -1))
                selected_list.append(manager.GetSelectedObject6(index, -1))
        if not error and count != 2:
            error = "expected two selected objects"
        elif not error and any(entity is None for entity in selected_list):
            error = "selected object unavailable"
        elif not error and (any(type(kind) is not int for kind in type_list) or type_list[0] not in _SKETCH_POINT_SELECTION_TYPES or type_list[1] != 10):
            error = "expected native sketch point and sketch segment selection types"
        if not error:
            owners = _sketch_owners(adapter)
            selected = tuple(selected_list)
            if point is not None:
                point_keys = tuple(_point_identity(adapter, entity, stage=stage, role=role, owners=owners) for role, entity in (("selected-point", selected[0]), ("expected-point", point)))
                if point_keys[0] != point_keys[1]:
                    error = "actual selected point identity differs"
            actual_key = _segment_identity(adapter, selected[1], stage=stage, role="selected", owners=owners)
            expected_key = _segment_identity(adapter, segment, stage=stage, role="expected", owners=owners)
            if actual_key != expected_key:
                error = "actual selected segment owner/type/ID differs"
    except Exception as exc:
        readback_error = exc
        error = str(exc)
    selected, types = tuple(selected_list), tuple(type_list)
    detail = f"stage={stage}, count={count}, types={types}, point_keys={point_keys!r}, segment={actual_key!r}, expected_segment={expected_key!r}, readback_error={readback_error!r}"
    _telemetry.info(
        f"clamp native selection: {detail}",
        operation_stage=stage,
        selection_count=count,
        selected_types=types,
        selected_available=tuple(entity is not None for entity in selected),
        selected_and_expected_point_identities=repr(point_keys),
        selected_segment_identity=repr(actual_key),
        expected_segment_identity=repr(expected_key),
        selection_identity_readback_error=repr(readback_error),
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
    thumb_profile, rod_profile, bore_profile = REFERENCE_SKETCHES
    for profile, prefix, key, y in (
        (thumb_profile, "ThumbTap", "top", BLOCK_HEIGHT),
        (rod_profile, "RodTap", "bottom", 0.0),
    ):
        # The diagonal normal plus the common Z-flat baseline controls both
        # entry coordinates without deriving a stock midplane.
        diagonal = _stock_edge(faces[key], ((r, y, 0.0), (r / 2.0, y, a)))
        circle = _tap_entry_circle(faces[key], y)
        sources[profile] = ("Top", circle, "IEntity", ((f"{prefix}FromDiagonalFlat", diagonal),))
    part = _early_bound(adapter.currentModel, "IPartDoc")
    feature = part.FeatureByName("LeverBoreProfile")
    if feature is None:
        raise RuntimeError("clamp location: actual bore-producing sketch is missing")
    sketch = _early_bound(_early_bound(feature, "IFeature").GetSpecificFeature2(), "ISketch")
    segments = tuple(sketch.GetSketchSegments() or ())
    if len(segments) != 1 or int(_early_bound(segments[0], "ISketchSegment").GetType()) != 1:
        raise RuntimeError("clamp location: bore-producing sketch is not one actual circle")
    flat = _stock_edge(faces["zflat"], ((r / 2.0, 0.0, a), (r / 2.0, BLOCK_HEIGHT, a)))
    sources[bore_profile] = ("Right", segments[0], "ISketchSegment", (("LeverBoreFromZFlat", flat),))
    return sources


def _measure_location(adapter: Any, center: Any, flat: Any, name: str) -> Any:
    """Native perpendicular point-to-line measurement, never an adapter drive."""
    import _telemetry

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
    raw, constructor_error = None, None
    try:
        raw = model.AddDimension2(0.02, 0.02, 0.0)
    except Exception as exc:
        constructor_error = exc
    _telemetry.info(
        f"clamp native point-flat constructor: name={name}, created={raw is not None}, error={constructor_error!r}",
        operation_stage=f"{name}.point-flat-constructor", native_created=raw is not None,
        native_method="IModelDoc2.AddDimension2", placement_m=(0.02, 0.02, 0.0),
        constructor_error=repr(constructor_error),
    )
    model.ClearSelection2(True)
    if raw is None:
        raise RuntimeError(f"{name}: native point-to-flat dimension failed: {constructor_error!r}") from constructor_error
    display = _early_bound(raw, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    dimension.DrivenState = 1
    dimension.Name = name
    display.ShowParenthesis = False
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = 0  # swTolNONE: ordinary .XX location, not an explicit rim band.
    retained_type, retained_state, retained_name = tolerance.Type, dimension.DrivenState, dimension.Name
    retained_reference, retained_value = display.ShowParenthesis, dimension.SystemValue
    _telemetry.info(
        f"clamp native location readback: name={name}, actual_name={retained_name!r}, state={retained_state!r}, reference={retained_reference!r}, value_m={retained_value!r}, tolerance={retained_type!r}",
        operation_stage=f"{name}.point-flat-readback", actual_dimension_name=repr(retained_name),
        native_driven_state=repr(retained_state), native_reference=repr(retained_reference),
        native_value_m=repr(retained_value), native_tolerance_type=repr(retained_type),
    )
    if type(retained_type) is not int or retained_type != 0:
        raise RuntimeError(f"{name}: ordinary location tolerance did not persist")
    if type(retained_state) is not int or retained_state != 1 or retained_name != name or retained_reference is not False:
        raise RuntimeError(f"{name}: native measured manufacturing dimension did not persist")
    if type(retained_value) not in (int, float) or not math.isclose(retained_value * 1000.0, HEX_AF / 2.0, abs_tol=0.005):
        raise RuntimeError(f"{name}: measurement is not the normal distance to the actual flat: {retained_value!r} m")
    owners = _sketch_owners(adapter)
    if _point_flat_attachment(adapter, display, flat, stage=f"{name}.after-create", owners=owners) != _point_identity(adapter, center, stage=f"{name}.after-create", role="expected-location", owners=owners):
        raise RuntimeError(f"{name}: native dimension is not attached to its actual point")
    return display


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
                    points[f"{name}FromZFlat"] = _early_bound(candidates[0], "ISketchPoint")
                    break
            child = native.GetNextSubFeature()
        else:
            raise RuntimeError(f"{name}: expected one actual native placement point")
    return points


def _transform_location(adapter: Any, coordinates: tuple[float, ...], transform: Any) -> tuple[float, ...]:
    from solidworks_mcp.adapters.com_variant import double_array

    application = _early_bound(adapter.swApp, "ISldWorks")
    utility = _early_bound(application.GetMathUtility(), "IMathUtility")
    point = _early_bound(utility.CreatePoint(double_array(list(coordinates))), "IMathPoint")
    projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
    result = tuple(float(value) for value in (projected.ArrayData or ()))
    if len(result) != 3 or not all(math.isfinite(value) for value in result):
        raise RuntimeError("clamp location: invalid native transformed point")
    return result


def _point_in_location_sketch(adapter: Any, point: Any, sketch: Any) -> tuple[float, ...]:
    """Use the actual point's owning frame, never its XYZ as model coordinates."""
    native = _early_bound(point, "ISketchPoint")
    owner = _early_bound(native.GetSketch(), "ISketch")
    source = _early_bound(owner.ModelToSketchTransform, "IMathTransform")
    target = _early_bound(sketch, "ISketch")
    model_point = _transform_location(adapter, (float(native.X), float(native.Y), float(native.Z)), source.Inverse())
    return _transform_location(adapter, model_point, target.ModelToSketchTransform)


def _witness_relation_records(relations: Any) -> tuple[list[dict[str, Any]], list[tuple[Any, ...]]]:
    """Snapshot actual kinds/definitions without treating a returned handle as effect."""
    import pythoncom
    from solidworks_mcp.adapters._generated.sldworks_2026 import ISketchPoint, ISketchSegment

    rows, definitions = [], []
    for raw in relations or ():
        row = {"kind": None, "count": None, "definition_interfaces": [], "definition_fields": [], "internal_entity_types": None, "internal_count": None, "suppressed": None, "point_keys": (), "expected_point_keys": (), "segment_key": None, "identity_matches": False, "alignment": None, "readback_errors": [], "mandatory_readback_errors": [], "unavailable_fields": []}
        rows.append(row)

        def capture(field, getter, *, mandatory=False):
            try:
                return getter()
            except Exception as exc:
                detail = f"{field}: {exc!r}"
                row["readback_errors"].append(detail)
                if mandatory:
                    row["mandatory_readback_errors"].append(detail)
                row["unavailable_fields"].append(field)
                return None

        relation = capture("binding", lambda: _early_bound(raw, "ISketchRelation"), mandatory=True)
        if relation is None:
            row["readback_errors"].append("binding: native relation unavailable")
            row["mandatory_readback_errors"].append("binding: native relation unavailable")
            row["unavailable_fields"].extend(("kind", "definitions", "suppressed", "internal_types", "internal_entities"))
            row["definitions_available"] = False
            definitions.append(())
            continue
        row["kind"] = capture("kind", lambda: relation.GetRelationType(), mandatory=True)
        actual = capture("definitions", lambda: tuple(relation.GetDefinitionEntities2()), mandatory=True)
        entities = actual or ()
        row["count"] = len(entities)
        row["definitions_available"] = actual is not None
        row["suppressed"] = capture("suppressed", lambda: relation.Suppressed, mandatory=True)
        # These optional diagnostics describe GetEntities, NOT the actual
        # definitions. Their availability must not change relation acceptance.
        row["internal_entity_types"] = capture("internal_types", lambda: relation.GetEntitiesType())
        row["internal_count"] = capture("internal_entities", lambda: len(relation.GetEntities()))
        for index, entity in enumerate(entities):
            fields = {"present": entity is not None, "interface": None}
            row["definition_fields"].append(fields)
            if entity is not None:
                # Query actual native capabilities; generated wrapper creation
                # can fall through after failed QI and is not capability proof.
                # IUnknown is a valid base for every COM interface. We never
                # invoke methods on these capability-only returned pointers.
                queries = []
                fields["query_interfaces"] = queries
                for interface, cls in (("ISketchPoint", ISketchPoint), ("ISketchSegment", ISketchSegment)):
                    query = {"interface": interface, "iid": str(cls.CLSID), "hresult": None, "supported": None}
                    queries.append(query)

                    def query_support():
                        try:
                            result = entity._oleobj_.QueryInterface(cls.CLSID, pythoncom.IID_IUnknown)
                        except pythoncom.com_error as exc:
                            query["hresult"] = exc.hresult
                            if exc.hresult == -2147467262:  # E_NOINTERFACE, not arbitrary failure.
                                return False
                            raise
                        if result is None:
                            raise RuntimeError("native QueryInterface returned no interface pointer")
                        query["hresult"] = 0  # S_OK; pywin32 raises on failure.
                        return True

                    query["supported"] = capture(f"definition[{index}].QI({interface})", query_support, mandatory=True)
                supported = [query["interface"] for query in queries if query["supported"] is True]
                if len(supported) == 1 and all(type(query["supported"]) is bool for query in queries):
                    fields["interface"] = supported[0]
                else:
                    detail = f"definition[{index}]: ambiguous, unsupported or unavailable native interfaces"
                    row["readback_errors"].append(detail)
                    row["mandatory_readback_errors"].append(detail)
            row["definition_interfaces"].append(fields["interface"])
            if fields["interface"] == "ISketchPoint":
                point = capture(f"definition[{index}].point-binding", lambda: _early_bound(entity, "ISketchPoint"), mandatory=True)
                fields["id"] = capture(f"definition[{index}].id", lambda: point.GetID(), mandatory=True)
                fields["coordinates"] = capture(f"definition[{index}].coordinates", lambda: (float(point.X), float(point.Y), float(point.Z)))
        definitions.append(entities)
    return rows, definitions


def _require_witness_relation(adapter: Any, relations: Any, kind: int, points: tuple[Any, ...], segment: Any = None, *, stage: str, owners: tuple[tuple[str, Any], ...] | None = None) -> None:
    """Require the exact requested constraint in the actual owner relation inventory.

    AddRelation and GetRelationType both document swConstraintType_e, not an
    input/output normalization map. Only the requested kind with the actual
    definition entities and alignment proves the required constraint.
    """
    import _telemetry

    application = _early_bound(adapter.swApp, "ISldWorks")
    matches, rows = 0, []
    error = None
    try:
        if owners is None:
            owners = _sketch_owners(adapter)
        rows, definitions = _witness_relation_records(relations)
        expected_point_keys = tuple(_point_identity(adapter, point, stage=stage, role=f"relation-source-point-{index}", owners=owners) for index, point in enumerate(points))
        if len(set(expected_point_keys)) != len(expected_point_keys):
            raise RuntimeError("native relation source points are not distinct")
        expected_key = _segment_identity(adapter, segment, stage=stage, role="relation-source", owners=owners) if segment is not None else None
        for row, entities in zip(rows, definitions, strict=True):
            # Census every row first; only the requested kind can define this constraint.
            if type(row["kind"]) is not int or row["kind"] != kind:
                continue
            interfaces = row["definition_interfaces"]
            if row["mandatory_readback_errors"] or len(entities) != len(points) + (segment is not None) or any(value is None for value in entities):
                continue
            actual_points = [entity for entity, interface in zip(entities, interfaces, strict=True) if interface == "ISketchPoint"]
            actual_segments = [entity for entity, interface in zip(entities, interfaces, strict=True) if interface == "ISketchSegment"]
            if len(actual_points) != len(points) or len(actual_segments) != (segment is not None):
                continue
            if kind in (25, 26) and len(actual_points) == 2:
                local = _early_bound(points[0], "ISketchPoint")
                target = _early_bound(local.GetSketch(), "ISketch")
                coordinates = tuple(_point_in_location_sketch(adapter, entity, target) for entity in actual_points)
                axis = 0 if kind == 26 else 1
                delta = coordinates[0][axis] - coordinates[1][axis]
                row["alignment"] = {"target_coordinates": coordinates, "axis": axis, "delta_m": delta, "aligned": abs(delta) <= 1e-9}
            actual_point_keys = [_point_identity(adapter, entity, stage=stage, role=f"relation-definition-point-{index}", owners=owners) for index, entity in enumerate(actual_points)]
            row["point_keys"] = tuple(actual_point_keys)
            row["expected_point_keys"] = expected_point_keys
            for point_key in expected_point_keys:
                if actual_point_keys.count(point_key) != 1:
                    break
                actual_point_keys.remove(point_key)
            else:
                if segment is not None:
                    actual_segment = actual_segments[0]
                    self_codes = (application.IsSame(segment, segment), application.IsSame(actual_segment, actual_segment))
                    row["segment_self_codes"] = self_codes
                    if any(type(code) is not int or code != 1 for code in self_codes):
                        raise RuntimeError("native relation segment self-identity unavailable")
                    actual_key = _segment_identity(adapter, actual_segment, stage=stage, role="relation-definition", owners=owners)
                    row["segment_key"] = actual_key
                    if actual_key != expected_key:
                        continue
                row["identity_matches"] = True
                if row["suppressed"] is not False:
                    raise RuntimeError("native defining constraint is suppressed or unavailable")
                if row["alignment"] is not None and not row["alignment"]["aligned"]:
                    raise RuntimeError("native defining point alignment differs")
                matches += 1
        if matches != 1:
            raise RuntimeError(f"expected exactly one native constraint {kind}, found {matches}; actual kinds={[row['kind'] for row in rows]!r}")
    except Exception as exc:
        error = exc
    _telemetry.info(
        f"clamp native witness relation: stage={stage}, requested_kind={kind}, actual_kinds={[row['kind'] for row in rows]!r}, matches={matches}, definitions={rows!r}, error={error!r}",
        operation_stage=stage, relation_kind=kind, actual_relation_kinds=tuple(row["kind"] for row in rows), relation_matches=matches,
        relation_definitions=repr(rows), relation_readback_error=repr(error),
    )
    if error is not None:
        raise RuntimeError(f"{stage}: {error}") from error


def _require_independent_witness_endpoints(adapter: Any, line: Any, center: Any, *, stage: str, owners: tuple[tuple[str, Any], ...] | None = None) -> tuple[Any, Any]:
    """Equal solved coordinates must not merge independently associated native points."""
    import _telemetry

    application = _early_bound(adapter.swApp, "ISldWorks")
    key, rows, comparisons, own_count, error = None, [], [], 0, None
    points = []
    try:
        if owners is None:
            owners = _sketch_owners(adapter)
        native = _early_bound(line, "ISketchSegment")
        key = _segment_identity(adapter, native, stage=stage, role="endpoint-line", owners=owners)
        owner = _early_bound(native.GetSketch(), "ISketch")
        straight = _early_bound(native, "ISketchLine")
        points = [("start", straight.GetStartPoint2()), ("end", straight.GetEndPoint2()), ("bore-center", center)]
        for candidate in owner.GetSketchSegments() or ():
            candidate_key = _segment_identity(adapter, candidate, stage=stage, role="endpoint-inventory", owners=owners)
            if candidate_key == key:
                own_count += 1
            elif candidate_key[1] == 0:
                other = _early_bound(candidate, "ISketchLine")
                points.extend(((f"{candidate_key!r}.start", other.GetStartPoint2()), (f"{candidate_key!r}.end", other.GetEndPoint2())))
        for label, raw in points:
            row = {"role": label, "present": raw is not None, "self": None, "owner": None, "coordinates": None, "key": None}
            rows.append(row)
            if raw is None:
                raise RuntimeError("native witness endpoint unavailable")
            point = _early_bound(raw, "ISketchPoint")
            row["key"] = _point_identity(adapter, point, stage=stage, role=label, owners=owners)
            row["self"] = application.IsSame(point, point)
            row["owner"] = application.IsSame(point.GetSketch(), owner)
            row["coordinates"] = (float(point.X), float(point.Y), float(point.Z))
        for index in (0, 1):
            for other_index in range(index + 1, len(points)):
                comparisons.append((points[index][0], points[other_index][0], rows[index]["key"] != rows[other_index]["key"]))
        if key[1] != 0 or own_count != 1:
            raise RuntimeError("native witness line inventory identity is ambiguous")
        if any(type(row[field]) is not int or row[field] != 1 for row in rows for field in ("self", "owner")):
            raise RuntimeError("native witness endpoint self/owner identity unavailable")
        if any(not math.isfinite(value) for row in rows for value in row["coordinates"]):
            raise RuntimeError("native witness endpoint coordinates unavailable")
        if any(distinct is not True for _left, _right, distinct in comparisons):
            raise RuntimeError("native witness endpoints merged or distinctness unavailable")
    except Exception as exc:
        error = exc
    _telemetry.info(
        f"clamp native witness endpoint identity: stage={stage}, line={key!r}, own_count={own_count}, points={rows!r}, comparisons={comparisons!r}, error={error!r}",
        operation_stage=stage, witness_line_identity=repr(key), witness_line_inventory_count=own_count,
        endpoint_identity_rows=repr(rows), endpoint_identity_comparisons=repr(comparisons),
        endpoint_identity_readback_error=repr(error),
    )
    if error is not None:
        raise RuntimeError(f"{stage}: {error}") from error
    return _early_bound(points[0][1], "ISketchPoint"), _early_bound(points[1][1], "ISketchPoint")


def _assert_tap_projection(adapter: Any, line: Any, point: Any, circle: Any, *, stage: str, owners: tuple[tuple[str, Any], ...] | None = None) -> tuple[Any, Any]:
    """Prove the actual tap's transverse projection; the rim only anchors construction."""
    import _telemetry

    if owners is None:
        owners = _sketch_owners(adapter)
    native = _early_bound(line, "ISketchSegment")
    key = _segment_identity(adapter, native, stage=stage, role="measurement-line", owners=owners)
    circle_key = _segment_identity(adapter, circle, stage=stage, role="bore-circle", owners=owners)
    if key[1] != 0 or circle_key[1] != 1 or key[0] != circle_key[0] or native.ConstructionGeometry is not True:
        raise RuntimeError(f"{stage}: measurement line is not construction in the actual bore witness")
    owner = _early_bound(native.GetSketch(), "ISketch")
    arc = _early_bound(circle, "ISketchArc")
    center = _early_bound(arc.GetCenterPoint2(), "ISketchPoint")
    start, end = _require_independent_witness_endpoints(adapter, native, center, stage=f"{stage}.endpoint-identity", owners=owners)
    _require_witness_relation(adapter, native.GetRelations(), 4, (), native, stage=f"{stage}.horizontal-line", owners=owners)
    _require_witness_relation(adapter, start.GetRelations(), 26, (start, point), stage=f"{stage}.actual-tap-axis", owners=owners)
    _require_witness_relation(adapter, end.GetRelations(), 25, (end, center), stage=f"{stage}.bore-station", owners=owners)
    _require_witness_relation(adapter, end.GetRelations(), 9, (end,), circle, stage=f"{stage}.actual-bore-rim", owners=owners)
    tap = _point_in_location_sketch(adapter, point, owner)
    actual = (float(start.X), float(start.Y), float(start.Z), float(end.X), float(end.Y), float(end.Z))
    radius = float(arc.GetRadius())
    expected = (tap[0], float(center.Y), 0.0, float(center.X) + radius, float(center.Y), 0.0)
    status = owner.GetConstrainedStatus()
    _telemetry.info(
        f"clamp native witness geometry: stage={stage}, line={key!r}, tap={tap!r}, endpoints={actual!r}, expected={expected!r}, status={status!r}",
        operation_stage=stage, witness_line_identity=repr(key), actual_tap_sketch_m=tap,
        witness_endpoints_m=actual, expected_endpoints_m=expected, constrained_status=status,
    )
    if type(status) is not int or status != 3 or not math.isfinite(radius) or radius <= 0.0 or any(not math.isfinite(value) or not math.isfinite(wanted) or abs(value - wanted) > 1e-9 for value, wanted in zip(actual, expected, strict=True)):
        raise RuntimeError(f"{stage}: native constrained axis-to-positive-rim witness changed")
    return start, end


def _create_tap_projection(adapter: Any, point: Any, circle: Any, name: str) -> Any:
    from solidworks_mcp.adapters.com_variant import dispatch_array
    import _telemetry

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    raw_sketch = model.GetActiveSketch2()
    if raw_sketch is None:
        raise RuntimeError(f"{name}: no active native witness sketch")
    sketch = _early_bound(raw_sketch, "ISketch")
    application = _early_bound(adapter.swApp, "ISldWorks")
    native_circle = _early_bound(circle, "ISketchSegment")
    owner = native_circle.GetSketch()
    codes = (application.IsSame(sketch, sketch), application.IsSame(owner, owner), application.IsSame(owner, sketch))
    _telemetry.info(f"clamp native active witness: name={name}, sketch_identity_codes={codes!r}", operation_stage=f"{name}.active-sketch", sketch_identity_codes=codes)
    if any(type(code) is not int or code != 1 for code in codes):
        raise RuntimeError(f"{name}: converted bore circle is not owned by the active sketch")
    arc = _early_bound(circle, "ISketchArc")
    center = _early_bound(arc.GetCenterPoint2(), "ISketchPoint")
    tap = _point_in_location_sketch(adapter, point, sketch)
    radius = float(arc.GetRadius())
    if not math.isfinite(radius) or radius <= 0.0:
        raise RuntimeError(f"{name}: invalid native bore radius")
    # AddToDB suppresses inference, but exact-coordinate points still merge in
    # the database (_sketch.add_line_chain). These provisional coordinates stay
    # away from the center/rim and prior solved witnesses; only native constraints
    # below determine the final geometry and dimension value.
    offset = radius / 2.0
    seed = (tap[0] + offset, float(center.Y) + offset, 0.0, float(center.X) + radius + offset, float(center.Y) + offset, 0.0)
    manager = _early_bound(adapter.currentSketchManager, "ISketchManager")
    previous = manager.AddToDB
    if type(previous) is not bool:
        raise RuntimeError(f"{name}: native AddToDB state unavailable")
    model.ClearSelection2(True)
    try:
        manager.AddToDB = True  # Suppress inference; this does NOT prevent exact DB merges.
        if manager.AddToDB is not True:
            raise RuntimeError(f"{name}: native inference isolation failed")
        _telemetry.info(f"clamp native measurement line request: name={name}, tap={tap!r}, provisional_seed={seed!r}", operation_stage=f"{name}.create-line-request", actual_tap_sketch_m=tap, provisional_seed_m=seed)
        raw = manager.CreateLine(seed[0], seed[1], seed[2], seed[3], seed[4], seed[5])
        _telemetry.info(f"clamp native measurement line: name={name}, created={raw is not None}", operation_stage=f"{name}.create-line", native_created=raw is not None)
        if raw is None:
            raise RuntimeError(f"{name}: native measurement line creation failed")
    finally:
        manager.AddToDB = previous
    if manager.AddToDB is not previous:
        raise RuntimeError(f"{name}: native inference state was not restored")
    line = _early_bound(raw, "ISketchSegment")
    line.ConstructionGeometry = True
    start, end = _require_independent_witness_endpoints(adapter, line, center, stage=f"{name}.seed-endpoint-identity")
    actual_seed = (float(start.X), float(start.Y), float(start.Z), float(end.X), float(end.Y), float(end.Z))
    _telemetry.info(
        f"clamp native witness seed readback: name={name}, requested={seed!r}, actual={actual_seed!r}",
        operation_stage=f"{name}.seed-readback", provisional_seed_m=seed, actual_seed_m=actual_seed,
    )
    if any(not math.isfinite(value) or abs(value - wanted) > 1e-9 for value, wanted in zip(actual_seed, seed, strict=True)):
        raise RuntimeError(f"{name}: native witness endpoints do not match the provisional seed")
    relations = _early_bound(sketch.RelationManager, "ISketchRelationManager")
    for kind, points, segment in ((4, (), line), (26, (start, point), None), (25, (end, center), None), (9, (end,), circle)):
        # Prove a new constraint on its actual owning entity, not merely a
        # non-null AddRelation return. R12 returned a USEEDGE handle for a
        # VERTPOINTS request without ever observing the endpoint's post-state.
        constraint_owner = line if kind == 4 else points[0]
        owner_interface = "ISketchSegment" if kind == 4 else "ISketchPoint"
        native_owner = _early_bound(constraint_owner, owner_interface)
        before_rows, before_error = [], None
        try:
            before_rows, _ = _witness_relation_records(native_owner.GetRelations())
        except Exception as exc:
            before_error = exc
        before_kinds = tuple(row["kind"] for row in before_rows)
        _telemetry.info(
            f"clamp native constraint before-state: name={name}, requested_kind={kind}, actual_kinds={before_kinds!r}, definitions={before_rows!r}, error={before_error!r}",
            operation_stage=f"{name}.before-constraint", relation_kind=kind,
            actual_relation_kinds=before_kinds, relation_definitions=repr(before_rows),
            relation_readback_error=repr(before_error), relation_owner_interface=owner_interface,
        )
        if before_error is not None or any(type(value) is not int for value in before_kinds):
            raise RuntimeError(f"{name}: native pre-constraint relation inventory unavailable") from before_error
        if kind in before_kinds:
            raise RuntimeError(f"{name}: native constraint {kind} already exists before creation")
        entities = [*points, *(() if segment is None else (segment,))]
        _telemetry.info(f"clamp native constraint request: name={name}, kind={kind}", operation_stage=f"{name}.add-relation-request", relation_kind=kind)
        relation = relations.AddRelation(dispatch_array(entities), kind)
        returned_rows, _ = _witness_relation_records((relation,))
        _telemetry.info(
            f"clamp native constraint return: name={name}, requested_kind={kind}, created={relation is not None}, returned_kinds={tuple(row['kind'] for row in returned_rows)!r}, returned_definitions={returned_rows!r}",
            operation_stage=f"{name}.add-relation", relation_kind=kind, native_created=relation is not None,
            returned_relation_kinds=tuple(row["kind"] for row in returned_rows),
            returned_relation_definitions=repr(returned_rows),
        )
        if relation is None:
            raise RuntimeError(f"{name}: native constraint {kind} creation failed")
        after, after_error = (), None
        try:
            after = tuple(native_owner.GetRelations() or ())
        except Exception as exc:
            after_error = exc
        _telemetry.info(
            f"clamp native constraint post-state: name={name}, requested_kind={kind}, count={len(after)}, error={after_error!r}",
            operation_stage=f"{name}.constraint-poststate", relation_kind=kind,
            relation_count=len(after), relation_readback_error=repr(after_error),
            relation_owner_interface=owner_interface,
        )
        if after_error is not None:
            raise RuntimeError(f"{name}: native post-constraint relation inventory unavailable") from after_error
        _require_witness_relation(adapter, after, kind, points, segment, stage=f"{name}.created-constraint")
    _assert_tap_projection(adapter, line, point, circle, stage=f"{name}.before-dimension")
    return line


def _point_flat_attachment(adapter: Any, display: Any, flat: Any, *, stage: str, owners: tuple[tuple[str, Any], ...] | None = None) -> tuple[str, str, int, int]:
    """Prove actual part attachments using fresh part-inventory identity keys."""
    import _telemetry

    attached = types = ()
    point_key = flat_key = expected_flat = error = None
    error_traceback = None
    dangling = None
    try:
        annotation = _early_bound(_early_bound(display, "IDisplayDimension").GetAnnotation(), "IAnnotation")
        attached = tuple(annotation.GetAttachedEntities3() or ())
        types = tuple(annotation.GetAttachedEntityTypes() or ())
        dangling = annotation.IsDangling()
        if len(attached) != 2 or len(types) != 2 or any(value is None for value in attached) or dangling is not False or any(type(kind) is not int for kind in types):
            raise RuntimeError("invalid native point/flat attachments")
        points = [entity for entity, kind in zip(attached, types, strict=True) if kind in _SKETCH_POINT_SELECTION_TYPES]
        segments = [entity for entity, kind in zip(attached, types, strict=True) if kind == 10]
        if len(points) != 1 or len(segments) != 1:
            raise RuntimeError("invalid native point/flat attachment types")
        if owners is None:
            owners = _sketch_owners(adapter)
        point_key = _point_identity(adapter, points[0], stage=stage, role="attached-location-point", owners=owners)
        flat_key = _segment_identity(adapter, segments[0], stage=stage, role="attached-flat", owners=owners)
        expected_flat = _segment_identity(adapter, flat, stage=stage, role="expected-common-flat", owners=owners)
        if flat_key != expected_flat or flat_key[1] != 0:
            raise RuntimeError("native location is not attached to the exact common flat")
    except Exception as exc:
        error = exc
        error_traceback = exc.__traceback__
    try:
        _telemetry.info(
            f"clamp native point/flat attachment: stage={stage}, types={types!r}, point={point_key!r}, flat={flat_key!r}, expected_flat={expected_flat!r}, dangling={dangling!r}, error={error!r}",
            operation_stage=stage, attachment_count=len(attached), attached_types=types,
            attached_point_identity=repr(point_key), attached_flat_identity=repr(flat_key),
            expected_flat_identity=repr(expected_flat), dangling=dangling, attachment_readback_error=repr(error),
        )
    finally:
        # Formatting/logging cannot replace the original native/guard exception.
        if error is not None:
            raise error.with_traceback(error_traceback)
    return point_key


def _assert_tap_flat_attachment(adapter: Any, display: Any, point: Any, circle: Any, flat: Any, *, name: str, stage: str, owners: tuple[tuple[str, Any], ...] | None = None) -> tuple[Any, ...]:
    """Recover the independently source-proven tap projection from its measured point."""
    if owners is None:
        owners = _sketch_owners(adapter)
    point_key = _point_flat_attachment(adapter, display, flat, stage=stage, owners=owners)
    flat_key = _segment_identity(adapter, flat, stage=stage, role="common-flat", owners=owners)
    native_circle = _early_bound(circle, "ISketchSegment")
    sketch = _early_bound(native_circle.GetSketch(), "ISketch")
    matches = []
    for raw in sketch.GetSketchSegments() or ():
        segment = _early_bound(raw, "ISketchSegment")
        if segment.GetType() != 0:
            continue
        key = _segment_identity(adapter, segment, stage=stage, role="projection-candidate", owners=owners)
        if key == flat_key:
            continue
        line = _early_bound(segment, "ISketchLine")
        if _point_identity(adapter, line.GetStartPoint2(), stage=stage, role="projection-start", owners=owners) != point_key:
            continue
        _assert_tap_projection(adapter, segment, point, circle, stage=stage, owners=owners)
        matches.append(key)
    if len(matches) != 1:
        raise RuntimeError(f"{name}: native attachments do not identify exactly one actual tap projection")
    return matches[0]


def _measure_tap_from_flat(adapter: Any, point: Any, circle: Any, flat: Any, name: str) -> None:
    """Measure the proven local tap projection from the same physical Z flat as the bore."""
    line = _create_tap_projection(adapter, point, circle, name)
    start = _early_bound(line, "ISketchLine").GetStartPoint2()
    display = _measure_location(adapter, start, flat, name)
    _assert_tap_flat_attachment(adapter, display, point, circle, flat, name=name, stage=f"{name}.after-create")


async def _location_profiles(adapter: Any) -> None:
    sources = _location_sources(adapter)
    for feature, (plane, circle, interface, flats) in sources.items():
        check(f"create_sketch {feature}", await adapter.create_sketch(plane))
        converted = _convert_location_source(adapter, circle, interface)
        arc = _early_bound(converted, "ISketchArc")
        center = _early_bound(arc.GetCenterPoint2(), "ISketchPoint")
        converted_flats = {}
        for name, flat in flats:
            converted_flats[name] = _convert_location_source(adapter, flat, "IEntity")
            _measure_location(adapter, center, converted_flats[name], name)
        if feature == "LeverBoreLocationProfile":
            for name, point in _tap_placement_points(adapter).items():
                _measure_tap_from_flat(adapter, point, converted, converted_flats["LeverBoreFromZFlat"], name)
        model = _early_bound(adapter.currentModel, "IModelDoc2")
        sketch = _early_bound(model.GetActiveSketch2(), "ISketch")
        status = sketch.GetConstrainedStatus()
        if type(status) is not int or status != 3:
            raise RuntimeError(f"{feature}: linked witness is not fully defined: {status!r}")
        check(f"exit_sketch {feature}", await adapter.exit_sketch())
        name_last_feature(adapter, feature)
    blank_reference_sketches(adapter, tuple(sources))


def _assert_location_profiles(adapter: Any, *, owners: tuple[tuple[str, Any], ...] | None = None) -> None:
    if owners is None:
        owners = _sketch_owners(adapter)
    part = _early_bound(adapter.currentModel, "IPartDoc")
    for feature, (_plane, source_circle, _interface, flats) in _location_sources(adapter).items():
        native_feature = _early_bound(part.FeatureByName(feature), "IFeature")
        sketch = _early_bound(native_feature.GetSpecificFeature2(), "ISketch")
        segments = tuple(sketch.GetSketchSegments() or ())
        extra = len(_tap_placement_points(adapter)) if feature == "LeverBoreLocationProfile" else 0
        if len(segments) != len(flats) + 1 + extra or sketch.GetConstrainedStatus() != 3:
            raise RuntimeError(f"{feature}: native linked witness changed after rebuild")
        for source in (source_circle, *(edge for _name, edge in flats)):
            if sum(_has_conversion_source(adapter, segment, source) for segment in segments) != 1:
                raise RuntimeError(f"{feature}: native source identity did not survive rebuild")
        circle = next(segment for segment in segments if _has_conversion_source(adapter, segment, source_circle))
        center = _early_bound(circle, "ISketchArc").GetCenterPoint2()
        converted_flats = {}
        for name, edge in flats:
            flat = next(segment for segment in segments if _has_conversion_source(adapter, segment, edge))
            converted_flats[name] = flat
            display, dimension = _named_dimension(adapter, feature, name)
            _assert_ordinary_location(display, dimension, name)
            if _point_flat_attachment(adapter, display, flat, stage=f"{name}.after-rebuild", owners=owners) != _point_identity(adapter, center, stage=f"{name}.after-rebuild", role="expected-center", owners=owners):
                raise RuntimeError(f"{name}: actual center attachment changed")
        if feature == "LeverBoreLocationProfile":
            flat = converted_flats["LeverBoreFromZFlat"]
            radius = float(_early_bound(circle, "ISketchArc").GetRadius()) * 1000.0
            if HEX_AF / 2.0 - radius < WALL_FLOOR:
                raise RuntimeError("LeverBore: actual model loses the policy wall floor")
            measured_lines = set()
            for name, point in _tap_placement_points(adapter).items():
                display, dimension = _named_dimension(adapter, feature, name)
                _assert_ordinary_location(display, dimension, name)
                key = _assert_tap_flat_attachment(adapter, display, point, circle, flat, name=name, stage=f"{name}.after-rebuild", owners=owners)
                if key in measured_lines:
                    raise RuntimeError(f"{name}: distinct tap witnesses merged into one native line")
                measured_lines.add(key)


def _assert_ordinary_location(display: Any, dimension: Any, name: str) -> None:
    import _telemetry

    actual, error = {}, None
    try:
        display = _early_bound(display, "IDisplayDimension")
        dimension = _early_bound(dimension, "IDimension")
        actual["driven_state"] = dimension.DrivenState
        actual["reference"] = display.ShowParenthesis
        actual["value_m"] = dimension.SystemValue
        actual["tolerance_type"] = _early_bound(dimension.Tolerance, "IDimensionTolerance").Type
        actual["places"] = display.GetPrimaryPrecision2()
    except Exception as exc:
        error = exc
    _telemetry.info(
        f"clamp ordinary location readback: name={name}, actual={actual!r}, error={error!r}",
        operation_stage=f"{name}.ordinary-location-readback",
        native_measurement=repr(actual), measurement_readback_error=repr(error),
    )
    if error is not None:
        raise RuntimeError(f"{name}: native ordinary location readback unavailable: {actual!r}") from error
    if type(actual["driven_state"]) is not int or actual["driven_state"] != 1 or actual["reference"] is not False or type(actual["value_m"]) not in (int, float) or not math.isclose(actual["value_m"] * 1000.0, HEX_AF / 2.0, abs_tol=1e-5):
        raise RuntimeError(f"{name}: ordinary native location measurement/ink changed: {actual!r}")
    if type(actual["tolerance_type"]) is not int or actual["tolerance_type"] != 0 or type(actual["places"]) is not int or actual["places"] != 2:
        raise RuntimeError(f"{name}: ordinary .XX default location acceptance changed: {actual!r}")


def _assert_stock_af(display: Any, dimension: Any, *, stage: str) -> None:
    """The native non-REF .XX AF uses ordinary title-block size acceptance."""
    import _telemetry

    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(dimension, "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    actual = {
        "full_name": dimension.FullName,
        "value_m": dimension.SystemValue,
        "reference": display.ShowParenthesis,
        "prefix": str(display.GetText(1) or ""),  # swDimensionTextPrefix
        "suffix": str(display.GetText(2) or ""),  # swDimensionTextSuffix
        "places": display.GetPrimaryPrecision2(),
        "tolerance_places": display.GetPrimaryTolPrecision2(),
        "tolerance_type": tolerance.Type,
        # Inactive native fields are observations, not the .XX accepted limits.
        "inactive_minimum_m": tolerance.GetMinValue(),
        "inactive_maximum_m": tolerance.GetMaxValue(),
    }
    _telemetry.info("clamp native stock AF acceptance", operation_stage=stage, native_measurement=repr(actual))
    if type(actual["full_name"]) is not str or actual["full_name"].split("@")[:2] != ["HexAf", "HexProfile"]:
        raise RuntimeError(f"HexAf: wrong native source dimension at {stage}: {actual!r}")
    # set_reference_dimension authors these affixes independently of
    # ShowParenthesis; either stale half must fail every source/import readback.
    if any("(" in actual[field] or ")" in actual[field] for field in ("prefix", "suffix")):
        raise RuntimeError(f"HexAf: native reference affix remained at {stage}: {actual!r}")
    if actual["prefix"] != HEX_AF_PREFIX or actual["suffix"] != "":
        raise RuntimeError(f"HexAf: ordinary HEX size no longer owns all opposed-flat pairs at {stage}: {actual!r}")
    if actual["reference"] is not False or any(type(actual[field]) is not int or actual[field] != value for field, value in (("places", 2), ("tolerance_places", 2), ("tolerance_type", 0))):
        raise RuntimeError(f"HexAf: native non-reference ordinary precision/tolerance changed at {stage}: {actual!r}")
    if type(actual["value_m"]) not in (int, float) or not math.isclose(actual["value_m"], HEX_AF / 1000.0, rel_tol=0.0, abs_tol=1e-9):
        raise RuntimeError(f"HexAf: native receiving size changed at {stage}: {actual!r}")


def _assert_stock_af_source(adapter: Any, *, stage: str) -> tuple[Any, Any]:
    """Prove the named native AF still measures two actual HexProfile endpoints."""
    import _telemetry

    display, dimension = _named_dimension(adapter, "HexProfile", "HexAf")
    _assert_stock_af(display, dimension, stage=stage)
    annotation = _early_bound(_early_bound(display, "IDisplayDimension").GetAnnotation(), "IAnnotation")
    entities = tuple(annotation.GetAttachedEntities3() or ())
    types = tuple(annotation.GetAttachedEntityTypes() or ())
    count, dangling = annotation.GetAttachedEntityCount3(), annotation.IsDangling()
    _telemetry.info("clamp native stock AF source attachments", operation_stage=stage, attachment_count=count, attachment_types=repr(types), returned_count=len(entities), dangling=dangling)
    if type(count) is not int or count != 2 or len(entities) != 2 or len(types) != 2 or any(type(kind) is not int or kind != 11 for kind in types) or any(entity is None for entity in entities) or dangling is not False:
        raise RuntimeError(f"HexAf: actual two-point source attachment changed at {stage}")
    owners = _sketch_owners(adapter)
    keys = tuple(_point_identity(adapter, entity, stage=stage, role=f"af-endpoint-{index}", owners=owners) for index, entity in enumerate(entities))
    if keys[0] == keys[1] or any(key[:2] != ("HexProfile", "ISketchPoint") for key in keys):
        raise RuntimeError(f"HexAf: source endpoints are not distinct actual HexProfile points: {keys!r}")
    points = tuple(_early_bound(entity, "ISketchPoint") for entity in entities)
    coordinates = tuple((point.X, point.Y) for point in points)
    _telemetry.info("clamp native stock AF source span", operation_stage=stage, point_keys=repr(keys), coordinates=repr(coordinates))
    if any(type(value) not in (int, float) or not math.isfinite(value) for point in coordinates for value in point) or not math.isclose(coordinates[0][0], coordinates[1][0], rel_tol=0.0, abs_tol=1e-9) or not math.isclose(abs(coordinates[0][1] - coordinates[1][1]), HEX_AF / 1000.0, rel_tol=0.0, abs_tol=1e-9):
        raise RuntimeError(f"HexAf: actual source points no longer span the opposite flats: {coordinates!r}")
    return display, dimension


def _author_stock_af(adapter: Any) -> None:
    # This is a fresh HexProfile, not migration of an old toleranced part.
    # NONE owns the ordinary band; inactive min/max getters do not define it.
    display, dimension = _named_dimension(adapter, "HexProfile", "HexAf")
    display = _early_bound(display, "IDisplayDimension")
    _early_bound(dimension.Tolerance, "IDimensionTolerance").Type = 0
    display.ShowParenthesis = False
    display.SetText(1, HEX_AF_PREFIX)
    display.SetText(2, "")
    precision_status = display.SetPrecision3(2, -1, 2, -1)
    if type(precision_status) is not int or precision_status != 0:
        raise RuntimeError(f"HexAf: ordinary precision authoring refused: {precision_status!r}")
    _assert_stock_af_source(adapter, stage="HexAf.source-authored")


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
    # The verified drawing title block owns DRILLED HOLES +0.10/0.
    # Do not print a duplicate explicit band on the native diameter.
    _bore_display, bore_dimension = _named_dimension(adapter, "LeverBoreProfile", "LeverBoreDiaDim")
    bore_tolerance = _early_bound(bore_dimension.Tolerance, "IDimensionTolerance")
    bore_tolerance.Type = 0
    if int(bore_tolerance.Type) != 0:
        raise RuntimeError("LeverBoreDiaDim: duplicate explicit drilled-hole tolerance remained")
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    _author_stock_af(adapter)
    _assert_location_profiles(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
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
