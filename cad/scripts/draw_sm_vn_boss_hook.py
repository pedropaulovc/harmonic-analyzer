"""Create the manufacturing drawing for the modified McMaster 9490T1 anchor."""

from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note, dimension_name, iter_views, place_view, view_name,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import set_dimension_callouts, set_dimension_precision
from _drawing_layout_check import DEFAULT_BOUNDARY_ALLOWANCE_M
from _drawing_hidden_sketches import (
    _show_hidden_owners, curate_view_dimensions as curate_stock_dimensions,
)
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_projection import model_points_in_view
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_sheet_region import sheet_drawable_region
from _purchased_fastener_drawing import _box, _inside, assert_supplier_view_fits
from _drawing_selection import _select_view_entity
from _rebuild import active_configuration_name
from _supplier_dimensions import (
    assert_supplier_reference_dimension, supplier_reference_dimension,
)
from _drawing_view_display import set_hidden_lines_removed
from _session import run_build
import _stock_trim_drawing as trim_drawing
import _telemetry
from stock_anchor_geom import ANCHOR_9490T1 as _SUPPLIER_ANCHOR
from sm_vn_boss_hook_spec import (
    CHAMFER_ANGLE_DEG,
    CHAMFER_ANGLE_TOLERANCE_DEG,
    CHAMFER_WIDTH_MM,
    CHAMFER_WIDTH_TOLERANCE_MM,
    DIMENSION_PRECISION,
    DRAWING_DIMENSIONS,
    DIMENSION_TOLERANCE_TYPES,
    FINISHED_OVERALL_MM,
    FINISHED_OVERALL_TOLERANCE_MM,
    REFERENCE_SKETCHES,
    SUPPLIER_EYE_ID_MM,
    SUPPLIER_FRACTION_DENOMINATOR,
    SUPPLIER_NOMINAL_EYE_OD_MM,
    SUPPLIER_NOMINAL_WIRE_MM,
    SUPPLIER_REFERENCE_PRECISION,
    SUPPLIER_STOCK_CONFIGURATION,
    SUPPLIER_STOCK_DIMENSIONS,
    SUPPLIER_STOCK_FEATURE,
    SUPPLIER_STOCK_AXIS_MM,
    SUPPLIER_STOCK_OVERALL_MM,
    SUPPLIER_STOCK_SHANK_MM,
    SUPPLIER_STOCK_WIRE_CENTER_MM,
    SUPPLIER_THREAD,
    SUPPLIER_THREAD_MAJOR_MM,
    SUPPLIER_THREAD_DIMENSIONS,
    SUPPLIER_THREAD_FEATURE,
)

SPEC = DRAWINGS_BY_NAME["sm_vn_boss_hook"]
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(**SPEC.outputs)
# diag_build_9490T1 names the merged circular-profile eye sweep "Wire".
_SUPPLIER_EYE_FEATURE = "Wire"
SHEET_SCALE = (4.0, 1.0)
ISO_SCALE = (2.0, 1.0)
STOCK_SCALE = (2.0, 1.0)
SHEET_NAMES = ("FINISHED", "SUPPLIER-STOCK")
STOCK_CENTER = (0.150, 0.175)
# The jam-nut shank (#1189) is 3.8 longer, 15 mm on the sheet: the view sits
# high enough that the cut-end chamfer dimensions clear the notes below it.
FRONT_CENTER = (0.100, 0.175)
ISO_CENTER = (0.310, 0.213)
# The cut-end deburr is dimensioned on the 4:1 front view itself (its 0.8 leg
# prints 3.2 long); a magnified detail added nothing a machinist needs.
FRONT_KEEP = {
    "FinishedOverall": (0.040, 0.175),
    "ChamferWidth": (0.150, 0.089),
    "ChamferAngle": (0.132, 0.106),
}
# The deburr band is tighter than the title block because its minimum leg
# must bring the cut end under the 3.797 tap drill, so the cut thread starts
# in the lever's tap: the callout names that mate.
CHAMFER_CALLOUT = {"ChamferWidth": "LEAD-IN TO MHA-SM-03 TAP"}
NOTES_Y = 0.076
EXPECTED_CONTROLS = {
    "FinishedOverall": (
        FINISHED_OVERALL_MM / 1000,
        -FINISHED_OVERALL_TOLERANCE_MM / 1000,
        FINISHED_OVERALL_TOLERANCE_MM / 1000,
    ),
    "ChamferWidth": (
        CHAMFER_WIDTH_MM / 1000,
        -CHAMFER_WIDTH_TOLERANCE_MM / 1000,
        CHAMFER_WIDTH_TOLERANCE_MM / 1000,
    ),
    "ChamferAngle": (
        math.radians(CHAMFER_ANGLE_DEG),
        -math.radians(CHAMFER_ANGLE_TOLERANCE_DEG),
        math.radians(CHAMFER_ANGLE_TOLERANCE_DEG),
    ),
}


def _verify_controls(adapter: Any, annotations: list[Any]) -> None:
    trim_drawing.verify_machining_controls(
        adapter,
        annotations,
        expected=EXPECTED_CONTROLS,
        tolerance_types=DIMENSION_TOLERANCE_TYPES,
        precision=DIMENSION_PRECISION,
    )


def _supplier_eye_source(
    view: Any, finished_configuration: str,
) -> tuple[Any, Any] | None:
    """Resolve Wire only in the exact finished-view source part."""
    if str(view.ReferencedConfiguration) != finished_configuration:
        return None
    raw_document = view.ReferencedDocument
    if raw_document is None:
        return None
    document = _early_bound(raw_document, "IModelDoc2")
    native_path = str(document.GetPathName())
    if native_path.replace("\\", "/").casefold() != SOURCE.resolve().as_posix().casefold():
        return None
    feature = _early_bound(raw_document, "IPartDoc").FeatureByName(_SUPPLIER_EYE_FEATURE)
    if feature is None:
        return None
    return document, _early_bound(feature, "IFeature")


def _supplier_eye_torus(
    adapter: Any, raw_face: Any, expected_feature: Any,
) -> tuple[float, ...] | None:
    """Require a source-context Wire face with the unchanged native eye torus."""
    if raw_face is None:
        return None
    face = _early_bound(raw_face, "IFace2")
    owner = face.GetFeature()
    if owner is None or int(adapter.swApp.IsSame(owner, expected_feature)) != 1:
        return None
    raw_surface = face.GetSurface()
    if raw_surface is None:
        return None
    surface = _early_bound(raw_surface, "ISurface")
    if not surface.IsTorus():
        return None
    torus = tuple(float(value) for value in surface.TorusParams)
    if not (
        len(torus) == 8
        and all(math.isfinite(value) for value in torus)
        and all(abs(value) < 1e-8 for value in torus[:3])
        and abs(abs(torus[5]) - 1.0) < 1e-8
        and abs(torus[6] * 2000.0 - 2.0 * _SUPPLIER_ANCHOR.eye_mean_radius_mm) < 1e-5
        and abs(torus[7] * 2000.0 - _SUPPLIER_ANCHOR.wire_dia_mm) < 1e-5
    ):
        return None
    return torus


def _supplier_eye_circle(
    adapter: Any, view: Any, raw: Any, finished_configuration: str,
) -> tuple[float, ...] | None:
    """Read the exact physical ID, normalizing its face into the source part."""
    source = _supplier_eye_source(view, finished_configuration)
    if source is None or raw is None:
        return None
    document, expected_feature = source
    silhouette = _early_bound(raw, "ISilhouetteEdge")
    raw_curve = silhouette.GetCurve()
    if raw_curve is None:
        return None
    curve = _early_bound(raw_curve, "ICurve")
    if not curve.IsCircle():
        return None
    circle = tuple(float(value) for value in curve.CircleParams)
    if not (
        len(circle) == 7
        and all(math.isfinite(value) for value in circle)
        and all(abs(value) < 1e-8 for value in circle[:3])
        and abs(abs(circle[5]) - 1.0) < 1e-8
        and abs(circle[6] * 2000.0 - SUPPLIER_EYE_ID_MM) < 1e-5
    ):
        return None
    native_view = silhouette.GetView()
    if (
        native_view is None
        or view_name(adapter, native_view) != view_name(adapter, view)
        or str(native_view.ReferencedConfiguration) != finished_configuration
    ):
        return None
    raw_face = silhouette.GetFace()
    raw_extension = document.Extension
    if raw_face is None or raw_extension is None:
        return None
    # Drawing-context feature identity cannot prove source ownership. Always
    # map the face, even if its direct owner appears to be the source Wire.
    extension = _early_bound(raw_extension, "IModelDocExtension")
    source_face = extension.GetCorrespondingEntity2(_early_bound(raw_face, "IFace2"))
    if _supplier_eye_torus(adapter, source_face, expected_feature) is None:
        return None
    return circle


def _supplier_eye_selection_observation(
    adapter: Any, front: Any, finished_configuration: str, *,
    original: dict[str, Any], document: Any, feature: Any,
    torus: tuple[float, ...], model_point: tuple[float, ...],
    sheet_point: tuple[float, ...],
) -> str:
    """Failure-only readback of the actual pick, never evidence for acceptance."""
    def safe(value: Any) -> Any:
        if isinstance(value, float) and not math.isfinite(value):
            return "NaN" if math.isnan(value) else ("Infinity" if value > 0 else "-Infinity")
        if isinstance(value, str):
            return value[:512]
        if isinstance(value, dict):
            return {key: safe(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [safe(item) for item in value]
        return value

    def read(row: dict[str, Any], field: str, getter: Any, *, obj: bool = False) -> Any:
        try:
            value = getter()
            row[field] = {"present": value is not None} if obj else {"value": value}
            return value
        except Exception as error:
            row[field] = {"error": {
                "field": field, "type": type(error).__name__, "message": str(error),
            }}
            return None

    def bind(row: dict[str, Any], raw: Any, interface: str) -> Any:
        return read(row, interface, lambda: _early_bound(raw, interface), obj=True)

    def numbers(raw: Any) -> dict[str, Any]:
        values = tuple(raw)
        sample = tuple(float(value) for value in values[:16])
        return {
            "length": len(values), "values": sample,
            "sample_truncated": len(values) > 16,
            "sample_all_finite": all(math.isfinite(value) for value in sample),
        }

    def feature_row(raw: Any) -> dict[str, Any]:
        row: dict[str, Any] = {}
        native = bind(row, raw, "IFeature")
        if native is not None:
            read(row, "Name", lambda: str(native.Name))
            read(row, "GetTypeName2", lambda: str(native.GetTypeName2()))
            read(row, "GetID", lambda: int(native.GetID()))
            read(row, "IsSame_self", lambda: int(adapter.swApp.IsSame(native, native)))
            read(row, "IsSame_source_Wire", lambda: int(adapter.swApp.IsSame(native, feature)))
        return row

    def face_row(raw: Any, *, map_to_source: bool) -> dict[str, Any]:
        row: dict[str, Any] = {"context": "drawing" if map_to_source else "source"}
        face = bind(row, raw, "IFace2")
        if face is None:
            return row
        owner = read(row, "GetFeature", lambda: face.GetFeature(), obj=True)
        row["owner"] = feature_row(owner)
        raw_surface = read(row, "GetSurface", lambda: face.GetSurface(), obj=True)
        surface = bind(row, raw_surface, "ISurface")
        if surface is not None:
            is_torus = read(row, "IsTorus", lambda: bool(surface.IsTorus()))
            if is_torus:
                read(row, "TorusParams", lambda: numbers(surface.TorusParams))
        if map_to_source:
            raw_extension = read(row, "source.Extension", lambda: document.Extension, obj=True)
            extension = bind(row, raw_extension, "IModelDocExtension")
            if extension is not None:
                mapped = read(
                    row, "GetCorrespondingEntity2",
                    lambda: extension.GetCorrespondingEntity2(face), obj=True,
                )
                row["mapped_source_face"] = face_row(mapped, map_to_source=False)
        return row

    def curve_row(raw: Any) -> dict[str, Any]:
        row: dict[str, Any] = {}
        curve = bind(row, raw, "ICurve")
        if curve is not None:
            read(row, "Identity", lambda: int(curve.Identity()))
            is_circle = read(row, "IsCircle", lambda: bool(curve.IsCircle()))
            if is_circle:
                read(row, "CircleParams", lambda: numbers(curve.CircleParams))
            is_line = read(row, "IsLine", lambda: bool(curve.IsLine()))
            if is_line:
                read(row, "LineParams", lambda: numbers(curve.LineParams))
        return row

    def view_row(raw: Any) -> dict[str, Any]:
        row: dict[str, Any] = {}
        native = bind(row, raw, "IView")
        if native is not None:
            read(row, "name", lambda: view_name(adapter, native))
            read(row, "ReferencedConfiguration", lambda: str(native.ReferencedConfiguration))
            read(row, "GetDisplayMode2", lambda: int(native.GetDisplayMode2()))
            referenced = read(row, "ReferencedDocument", lambda: native.ReferencedDocument, obj=True)
            referenced = bind(row, referenced, "IModelDoc2")
            if referenced is not None:
                read(row, "source_path", lambda: str(referenced.GetPathName()))
            transform = read(row, "ModelToViewTransform", lambda: native.ModelToViewTransform, obj=True)
            transform = bind(row, transform, "IMathTransform")
            if transform is not None:
                read(row, "ArrayData", lambda: numbers(transform.ArrayData))
        return row

    def entity_row(raw: Any, kind: int | None) -> dict[str, Any]:
        row: dict[str, Any] = {"present": raw is not None}
        if raw is None:
            return row
        if kind == 12:  # swSelDRAWINGVIEWS: do not pretend a view is a curve.
            row["drawing_view"] = view_row(raw)
            return row
        if kind == 2:  # swSelFACES
            row["face"] = face_row(raw, map_to_source=True)
        # A wrong selection kind does not prove that either interface is absent.
        # Observe their independent errors; neither route can accept the pick.
        for interface in ("ISilhouetteEdge", "IEdge"):
            geometry: dict[str, Any] = {}
            row[interface] = geometry
            native = bind(geometry, raw, interface)
            if native is None:
                continue
            curve = read(geometry, "GetCurve", lambda: native.GetCurve(), obj=True)
            geometry["curve"] = curve_row(curve)
            if interface == "ISilhouetteEdge":
                face = read(geometry, "GetFace", lambda: native.GetFace(), obj=True)
                geometry["face"] = face_row(face, map_to_source=True)
                view = read(geometry, "GetView", lambda: native.GetView(), obj=True)
                geometry["view"] = view_row(view)
            else:
                faces = read(
                    geometry, "GetTwoAdjacentFaces2",
                    lambda: native.GetTwoAdjacentFaces2(), obj=True,
                )
                if faces is not None:
                    geometry["adjacent_faces"] = [
                        face_row(face, map_to_source=True) for face in faces
                    ]
        return row

    later: dict[str, Any] = {"view": view_row(front), "source_Wire": feature_row(feature)}
    source: dict[str, Any] = {}
    later["source"] = source
    read(source, "GetPathName", lambda: str(document.GetPathName()))
    manager = read(source, "ConfigurationManager", lambda: document.ConfigurationManager, obj=True)
    manager = bind(source, manager, "IConfigurationManager")
    if manager is not None:
        configuration = read(source, "ActiveConfiguration", lambda: manager.ActiveConfiguration, obj=True)
        configuration = bind(source, configuration, "IConfiguration")
        if configuration is not None:
            read(source, "active_configuration_name", lambda: str(configuration.Name))
    current_source = read(source, "view.ReferencedDocument", lambda: front.ReferencedDocument, obj=True)
    current_source = bind(source, current_source, "IModelDoc2")
    if current_source is not None:
        read(source, "current_view_source_path", lambda: str(current_source.GetPathName()))
        read(source, "IsSame_authoritative_document", lambda: int(
            adapter.swApp.IsSame(current_source, document)
        ))
    selected: dict[str, Any] = {"entries": []}
    later["selection"] = selected
    raw_selection = read(
        selected, "SelectionManager", lambda: adapter.currentModel.SelectionManager, obj=True,
    )
    selection = bind(selected, raw_selection, "ISelectionMgr")
    if selection is not None:
        count = read(selected, "GetSelectedObjectCount2", lambda: int(selection.GetSelectedObjectCount2(-1)))
        if count is not None:
            for index in range(1, count + 1):
                entry: dict[str, Any] = {"index": index}
                selected["entries"].append(entry)
                kind = read(entry, "GetSelectedObjectType3", lambda: int(
                    selection.GetSelectedObjectType3(index, -1)
                ))
                raw = read(entry, "GetSelectedObject6", lambda: selection.GetSelectedObject6(index, -1), obj=True)
                entry["entity"] = (
                    {"presence": "unreadable"}
                    if "error" in entry["GetSelectedObject6"] else entity_row(raw, kind)
                )
    packet = {
        "kind": "sm_eye_id_selection_failure",
        "expected": {
            "selected_count": 1, "selected_type": 46, "entity_present": True,
            "physical_id_mm": SUPPLIER_EYE_ID_MM,
            "finished_configuration": finished_configuration,
            "source_path": str(SOURCE.resolve()), "source_feature": _SUPPLIER_EYE_FEATURE,
            "circle_parameters": 7, "torus_parameters": 8, "all_parameters_finite": True,
            "absolute_center_limit_m_exclusive": 1e-8,
            "absolute_axis_z_magnitude": 1.0, "axis_z_error_limit_exclusive": 1e-8,
            "diameter_error_limit_mm_exclusive": 1e-5,
            "torus_major_diameter_mm": 2.0 * _SUPPLIER_ANCHOR.eye_mean_radius_mm,
            "torus_minor_diameter_mm": _SUPPLIER_ANCHOR.wire_dia_mm,
            "source_owner_IsSame": 1,
        },
        "original_predicate": original,
        "acquisition": {
            "source_torus": torus, "model_top_inner_point_m": model_point,
            "projected_sheet_point_m": sheet_point,
        },
        "later_readback": later,
    }
    return json.dumps(safe(packet), allow_nan=False, separators=(",", ":"))


def _supplier_references(
    adapter: Any, front: Any, finished_configuration: str,
) -> list[tuple[str, dict[str, Any]]]:
    """Acquire the physical eye ID at its native source-torus inner point."""
    # Keep the existing pre-query HLV-to-HLR setup. Visibility-filtered
    # enumeration need not expose the ID; supported coordinate selection does
    # its own hit test, whose returned physical contour must still be proved.
    set_hidden_lines_removed(adapter, front)
    front.UpdateViewDisplayGeometry()
    source = _supplier_eye_source(front, finished_configuration)
    if source is None:
        raise RuntimeError("unchanged counter eye has no exact ID circular silhouette")
    _document, feature = source
    eye_tori = []
    for face in feature.GetFaces() or ():
        torus = _supplier_eye_torus(adapter, face, feature)
        if torus is not None:
            eye_tori.append(torus)
    if len(eye_tori) != 1:
        raise RuntimeError(
            "counter eye requires one authoritative source Wire eye torus; "
            f"found {len(eye_tori)}"
        )
    cx, cy, cz, _nx, _ny, _nz, major, minor = eye_tori[0]
    model_point = (cx, cy + major - minor, cz)
    point = model_points_in_view(
        adapter, front, [model_point], label="EyeID",
    )[0]
    original: dict[str, Any] = {
        "stage": "select_view_entity", "selected_count": "not_read",
        "selected_type": "not_read", "entity_present": "not_read",
        "helper_return_present": "not_returned",
        "exact_source_circle": "not_read",
    }
    failure: Exception | None = None
    try:
        eye = _select_view_entity(adapter, front, "SILHOUETTE", point, label="EyeID")
        original["helper_return_present"] = eye is not None
        original["stage"] = "selection_manager"
        selection = _early_bound(adapter.currentModel.SelectionManager, "ISelectionMgr")
        original["stage"] = "selected_count"
        count = int(selection.GetSelectedObjectCount2(-1))
        original["selected_count"] = count
        if count != 1:
            raise RuntimeError(
                f"counter eye ID selection expected count=1; actual count={count}"
            )
        original["stage"] = "selected_type"
        kind = int(selection.GetSelectedObjectType3(1, -1))
        original["selected_type"] = kind
        if kind != 46:
            raise RuntimeError(
                f"counter eye ID selection expected type=46; actual type={kind}"
            )
        original["stage"] = "entity_present"
        original["entity_present"] = eye is not None
        if eye is None:
            raise RuntimeError(
                "counter eye ID selection expected entity_present=True; actual entity_present=False"
            )
        original["stage"] = "exact_source_circle"
        circle = _supplier_eye_circle(adapter, front, eye, finished_configuration)
        original["exact_source_circle"] = circle is not None
        if circle is None:
            raise RuntimeError(
                "unchanged counter eye has no exact ID circular silhouette; "
                f"expected physical ID={SUPPLIER_EYE_ID_MM} mm and mapped source Wire; "
                "actual exact-source-circle predicate=False"
            )
        original["stage"] = "AddDiameterDimension2"
        display = adapter.currentModel.AddDiameterDimension2(0.150, 0.241, 0.0)
    except Exception as error:
        failure = error
        original["failure"] = {"type": type(error).__name__, "message": str(error)[:512]}
        try:
            note = _supplier_eye_selection_observation(
                adapter, front, finished_configuration, original=original,
                document=_document, feature=feature, torus=eye_tori[0],
                model_point=model_point, sheet_point=point,
            )
        except Exception as observation_error:
            # A receipt failure must never replace the native acquisition error.
            note = json.dumps({
                "kind": "sm_eye_id_selection_failure", "original_predicate": original,
                "observation_error": {
                    "type": type(observation_error).__name__,
                    "message": str(observation_error)[:512],
                },
            }, allow_nan=False, separators=(",", ":"))
        error.add_note(note)
        raise
    finally:
        try:
            adapter.currentModel.ClearSelection2(True)
        except Exception as clear_error:
            if failure is None:
                raise
            raise failure from clear_error
    if display is None:
        raise RuntimeError("cannot dimension the counter eye ID silhouette")
    contract = dict(
        label="EyeID", expected_mm=SUPPLIER_EYE_ID_MM, units="in",
        precision=SUPPLIER_REFERENCE_PRECISION["EyeID"], presentation="diameter",
        fraction_denominator=SUPPLIER_FRACTION_DENOMINATOR,
    )
    display = supplier_reference_dimension(adapter, display, **contract)
    refs = [(str(_early_bound(display.GetDimension2(0), "IDimension").FullName), contract)]
    annotations = curate_stock_dimensions(
        adapter, front, keep={"SupplierThreadMajor": (0.166, 0.170)},
        view_label="supplier thread nominal major, not helical geometry",
        dimensions_by_feature=SUPPLIER_THREAD_DIMENSIONS,
    )
    for annotation in annotations:
        contract = dict(
            label="SupplierThreadMajor", expected_mm=SUPPLIER_THREAD_MAJOR_MM,
            units="in", precision=SUPPLIER_REFERENCE_PRECISION["SupplierThreadMajor"],
            presentation="diameter",
            callout=f"{SUPPLIER_THREAD} THREAD\nNOMINAL MAJOR — SUPPLIER REF",
        )
        display = supplier_reference_dimension(
            adapter, annotation.GetSpecificAnnotation(), **contract
        )
        refs.append((str(_early_bound(display.GetDimension2(0), "IDimension").FullName), contract))
    return refs


def _supplier_stock_diagram(adapter: Any):
    """A separate zero-body source profile, never false-sized finished edges."""
    stock = _early_bound(
        place_view(adapter, str(SOURCE), "*Front", *STOCK_CENTER, scale=STOCK_SCALE),
        "IView",
    )
    stock.ReferencedConfiguration = SUPPLIER_STOCK_CONFIGURATION
    if str(stock.ReferencedConfiguration) != SUPPLIER_STOCK_CONFIGURATION:
        raise RuntimeError("supplier stock view references the finished configuration")
    set_hidden_lines_removed(adapter, stock)
    # Reveal the saved-hidden sketch before the first outline/projection/fit.
    shown = _show_hidden_owners(
        adapter, stock, (SUPPLIER_STOCK_FEATURE,),
        view_label="counter anchor source diagram before fitting",
    )
    if set(shown) != {SUPPLIER_STOCK_FEATURE}:
        raise RuntimeError("counter anchor source diagram owner is not saved hidden")
    if adapter.currentModel.EditRebuild3() is not True:
        raise RuntimeError("cannot rebuild the revealed supplier nominal stock view")
    stock.UpdateViewDisplayGeometry()
    outline = _box(stock.GetOutline(), label="revealed counter anchor source diagram")
    ratio = STOCK_SCALE[0] / STOCK_SCALE[1]
    expected_spans = (
        (
            SUPPLIER_STOCK_WIRE_CENTER_MM[0]
            + SUPPLIER_NOMINAL_WIRE_MM / 2.0
            + SUPPLIER_NOMINAL_EYE_OD_MM / 2.0
        ) / 1000.0 * ratio,
        SUPPLIER_STOCK_OVERALL_MM / 1000.0 * ratio,
    )
    for actual, expected in zip(
        (outline[2] - outline[0], outline[3] - outline[1]), expected_spans, strict=True
    ):
        if not expected - 1e-7 <= actual <= expected + 2.0 * DEFAULT_BOUNDARY_ALLOWANCE_M:
            raise RuntimeError("revealed supplier diagram outline does not cover its source profile")
    midpoint = (
        0.0,
        (SUPPLIER_STOCK_AXIS_MM[0][1] + SUPPLIER_STOCK_AXIS_MM[-1][1]) / 2000.0,
        0.0,
    )
    projected = model_points_in_view(
        adapter, stock, [midpoint], label="source stock envelope centre"
    )[0]
    before = tuple(float(value) for value in stock.Position)
    stock.Position = double_array([
        before[0] + STOCK_CENTER[0] - projected[0],
        before[1] + STOCK_CENTER[1] - projected[1],
    ])
    if adapter.currentModel.EditRebuild3() is not True:
        raise RuntimeError("cannot position the complete supplier stock envelope")
    keep = {
        "SupplierNominalEyeOD": (0.180, 0.244),
        "SupplierNominalWire": (0.255, 0.235),
        "SupplierStockShank": (0.105, 0.160),
        "SupplierStockOverall": (0.065, STOCK_CENTER[1]),
    }
    annotations = curate_stock_dimensions(
        adapter, stock, keep=keep,
        view_label="as-supplied nominal stock envelope and wire section",
        dimensions_by_feature=SUPPLIER_STOCK_DIMENSIONS,
    )
    expected = {
        "SupplierNominalEyeOD": SUPPLIER_NOMINAL_EYE_OD_MM,
        "SupplierNominalWire": SUPPLIER_NOMINAL_WIRE_MM,
        "SupplierStockShank": SUPPLIER_STOCK_SHANK_MM,
        "SupplierStockOverall": SUPPLIER_STOCK_OVERALL_MM,
    }
    refs = []
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        contract = dict(
            label=name, expected_mm=expected[name], units="in",
            precision=SUPPLIER_REFERENCE_PRECISION[name],
            presentation="diameter" if name.startswith("SupplierNominal") else "length",
            fraction_denominator=(
                None if name == "SupplierStockOverall" else SUPPLIER_FRACTION_DENOMINATOR
            ),
            callout={
                "SupplierNominalEyeOD": "NOMINAL EYE ENVELOPE",
                "SupplierNominalWire": "NOMINAL WIRE SECTION",
                "SupplierStockShank": "AS-SUPPLIED SHANK / THREAD",
                "SupplierStockOverall": "AS-SUPPLIED OVERALL",
            }[name],
        )
        display = supplier_reference_dimension(
            adapter, annotation.GetSpecificAnnotation(), **contract
        )
        refs.append((str(_early_bound(display.GetDimension2(0), "IDimension").FullName), contract))
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    drawing.ActivateView("")  # False is documented for sheet context.
    if drawing.GetEditSheet() is not True or drawing.ActiveDrawingView is not None:
        raise RuntimeError("cannot enter supplier stock sheet context for labels")
    sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
    properties = tuple(sheet.GetProperties2())
    region = sheet_drawable_region(
        adapter, sheet, width=float(properties[5]), height=float(properties[6])
    )
    notes = []
    for text, x, y in (
        (
            "SUPPLIER NOMINAL STOCK ENVELOPE — AS SUPPLIED",
            region.xmin + 0.0033, region.ymax - 0.004,
        ),
        (
            "NOMINAL PROFILE ONLY — INSTALLED VENDOR-CAD EYE UNCHANGED\n"
            "STOCK REFERENCES ONLY — FINISHED TRIM AND CHAMFER: SHEET 1",
            0.016, 0.089,
        ),
    ):
        note = add_note(adapter, text, x, y)
        if note is None:
            raise RuntimeError("cannot label the supplier nominal stock envelope")
        notes.append((_early_bound(note, "INote"), text))
    return stock, refs, notes


def _verify_supplier_references(adapter, refs_by_sheet, view_contracts):
    """Read geometry and attachments without refreshing or repairing the views."""
    if sum(len(refs) for refs in refs_by_sheet.values()) != 6:
        raise RuntimeError("counter anchor must retain all six supplier dimensions")
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    for sheet_name, refs in refs_by_sheet.items():
        if drawing.ActivateSheet(sheet_name) is not True:
            raise RuntimeError(f"cannot inspect settled references on {sheet_name}")
        views = {view_name(adapter, raw): _early_bound(raw, "IView") for raw in iter_views(adapter)}
        names, configuration = view_contracts[sheet_name]
        for name in names:
            if name not in views or str(views[name].ReferencedConfiguration) != configuration:
                raise RuntimeError(f"{sheet_name}: supplier view lost its source configuration")
        view = views[names[0]]
        displays = {}
        display = view.GetFirstDisplayDimension6()
        while display is not None:
            display = _early_bound(display, "IDisplayDimension")
            native = _early_bound(display.GetDimension2(0), "IDimension")
            key = str(native.FullName)
            if key in displays:
                raise RuntimeError(f"{sheet_name}: duplicate native dimension {key}")
            displays[key] = display
            display = display.GetNext5()
        expected_count = len(refs) + (len(FRONT_KEEP) if sheet_name == SHEET_NAMES[0] else 0)
        if len(displays) != expected_count:
            raise RuntimeError(f"{sheet_name}: settled native dimension coverage changed")
        for key, contract in refs:
            if key not in displays:
                raise RuntimeError(f"{contract['label']}: settled supplier dimension disappeared")
            display = displays[key]
            assert_supplier_reference_dimension(adapter, display, **contract)
            native = _early_bound(display.GetDimension2(0), "IDimension")
            if int(_early_bound(native.Tolerance, "IDimensionTolerance").Type) != 0:
                raise RuntimeError(f"{contract['label']}: supplier reference acquired a tolerance band")
            if contract["label"] != "EyeID":
                feature = (
                    SUPPLIER_THREAD_FEATURE
                    if contract["label"] == "SupplierThreadMajor" else SUPPLIER_STOCK_FEATURE
                )
                if str(native.FullName).split("@")[:2] != [contract["label"], feature]:
                    raise RuntimeError(f"{contract['label']}: nominal model attachment changed")
                if contract["label"] == "SupplierStockOverall" and int(native.DrivenState) != 1:
                    raise RuntimeError("supplier overall lost its driven envelope measurement")
            else:
                annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
                entities = tuple(annotation.GetAttachedEntities3() or ())
                kinds = tuple(int(value) for value in (annotation.GetAttachedEntityTypes() or ()))
                if (
                    int(annotation.GetAttachedEntityCount3()) != 1
                    or len(entities) != 1
                    or kinds != (46,)
                    or entities[0] is None
                    or annotation.IsDangling()
                ):
                    raise RuntimeError(
                        "supplier eye ID must retain one live physical silhouette; "
                        f"entities={len(entities)}, kinds={kinds}"
                    )
                circle = _supplier_eye_circle(adapter, view, entities[0], configuration)
                if circle is None:
                    raise RuntimeError(
                        f"supplier eye ID lost its exact physical source contour; circle={circle!r}"
                    )


def _verify_supplier_layout(adapter, view_contracts, notes):
    """Inspect complete native view/dimension ink and sheet-owned label extents."""
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    for sheet_name, (names, _configuration) in view_contracts.items():
        if drawing.ActivateSheet(sheet_name) is not True:
            raise RuntimeError(f"cannot inspect supplier ink on {sheet_name}")
        sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
        properties = tuple(sheet.GetProperties2())
        region = sheet_drawable_region(
            adapter, sheet, width=float(properties[5]), height=float(properties[6])
        )
        border = (region.xmin, region.ymin, region.xmax, region.ymax)
        cell = (
            region.xmin, 0.094 if sheet_name == SHEET_NAMES[1] else 0.0651,
            region.xmax, region.ymax - (0.009 if sheet_name == SHEET_NAMES[1] else 0.0),
        )
        views = {view_name(adapter, raw): _early_bound(raw, "IView") for raw in iter_views(adapter)}
        for name in names:
            if name not in views:
                raise RuntimeError(f"{sheet_name}: supplier dimension view disappeared")
            view = views[name]
            view.UpdateViewDisplayGeometry()
            assert_supplier_view_fits(adapter, view, cell, label=f"counter anchor {sheet_name}")
        if sheet_name == SHEET_NAMES[1]:
            for note, text in notes:
                annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
                bounds = _box(note.GetExtent(), label=text, kind="note")
                if (
                    int(annotation.OwnerType) != 1 or not _inside(bounds, border)
                    or str(note.GetText()).replace("\r\n", "\n") != text
                ):
                    raise RuntimeError(f"supplier stock label changed or leaves the usable sheet: {text}")


def _verify_source_state(adapter, source_model, finished_configuration):
    if active_configuration_name(adapter, source_model) != finished_configuration:
        raise RuntimeError("supplier drawing changed the source part's active configuration")
    part = _early_bound(source_model, "IPartDoc")
    for name in REFERENCE_SKETCHES:
        feature = part.FeatureByName(name)
        if feature is None or int(_early_bound(feature, "IFeature").Visible) != 1:
            raise RuntimeError(f"{name}: supplier drawing changed saved-hidden source visibility")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open modified anchor", await adapter.open_model(str(SOURCE)))
    source_model = _early_bound(adapter.currentModel, "IModelDoc2")
    finished_configuration = active_configuration_name(adapter, source_model)
    if not finished_configuration or finished_configuration == SUPPLIER_STOCK_CONFIGURATION:
        raise RuntimeError("source counter anchor is not saved in its finished configuration")
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Stock Name",
        "Supplier",
        "Supplier SKUs",
        "Manufacturing Notes",
        "Isometric View Note",
    )
    read_required_properties(adapter.currentModel, required, required=required)
    draw, _sheet = new_project_drawing(
        adapter, property_view=SPEC.artifact_stem, scale=SHEET_SCALE, layout=SPEC.layout
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="counter anchor stock package")
    drawing = _early_bound(draw, "IDrawingDoc")
    if drawing.ActivateSheet(SHEET_NAMES[0]) is not True:
        raise RuntimeError("cannot activate finished counter anchor sheet")
    stamp_drawing_summary(
        adapter,
        draw,
        {
            0: "Counter Spring Anchor — Modified Stock Drawing",
            1: "Manufacturing controls for modified purchased stock",
            2: "Harmonic Analyzer Project",
            3: "MHA-SM-VN-50; McMaster-Carr 9490T1",
            4: "Native dimension-driven trim and end deburr",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, iso):
        view = _early_bound(view, "IView")
        view.ReferencedConfiguration = finished_configuration
    # Hidden lines removed: the helix's back side, dashed, told the machinist
    # nothing about a purchased thread and cluttered the cut end.
    set_hidden_lines_removed(adapter, front)
    annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="finished overall and cut end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_precision(adapter, annotations, DIMENSION_PRECISION)
    set_dimension_callouts(adapter, annotations, CHAMFER_CALLOUT)
    _verify_controls(adapter, annotations)
    refs = _supplier_references(adapter, front, finished_configuration)
    add_property_linked_note(adapter, "Supplier", 0.016, 0.060, char_height=0.003)
    add_property_linked_note(adapter, "Supplier SKUs", 0.080, 0.060, char_height=0.003)
    add_property_linked_note(adapter, "Stock Name", 0.016, 0.049, char_height=0.003)
    add_property_linked_note(adapter, "Isometric View Note", 0.275, 0.163)
    add_property_linked_note(
        adapter, "Manufacturing Notes", 0.016, NOTES_Y, char_height=0.003
    )
    # Re-assert after annotating: a real mode change regenerates the edge set.
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)
    if drawing.ActivateSheet(SHEET_NAMES[1]) is not True:
        raise RuntimeError("cannot activate counter anchor supplier stock sheet")
    stock, stock_refs, stock_notes = _supplier_stock_diagram(adapter)
    set_hidden_lines_removed(adapter, stock)
    view_contracts = {
        SHEET_NAMES[0]: ((view_name(adapter, front), view_name(adapter, iso)), finished_configuration),
        SHEET_NAMES[1]: ((view_name(adapter, stock),), SUPPLIER_STOCK_CONFIGURATION),
    }
    refs_by_sheet = {SHEET_NAMES[0]: refs, SHEET_NAMES[1]: stock_refs}

    def verify_after_native_save(event):
        if event != "after_drawing_save":
            return
        # Still-open post-SaveAs3 inspection, not cold-reopen disk proof.
        _verify_supplier_references(adapter, refs_by_sheet, view_contracts)
        if drawing.ActivateSheet(SHEET_NAMES[0]) is not True:
            raise RuntimeError("cannot restore finished counter anchor sheet after saved-eye inspection")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Counter Spring Anchor — Modified Stock Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        sheet_scales={SHEET_NAMES[0]: SHEET_SCALE, SHEET_NAMES[1]: STOCK_SCALE},
        settled_checks=(
            lambda: _verify_controls(adapter, annotations),
            # The layout check owns pre-save view refreshes; the attachment
            # verifier is also safe to call after the native save.
            lambda: _verify_supplier_layout(adapter, view_contracts, stock_notes),
            lambda: _verify_supplier_references(adapter, refs_by_sheet, view_contracts),
            lambda: _verify_source_state(adapter, source_model, finished_configuration),
        ),
        checkpoint=verify_after_native_save,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
