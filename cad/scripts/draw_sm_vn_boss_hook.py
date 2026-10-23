"""Create the manufacturing drawing for the modified McMaster 9490T1 anchor."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import bstr_array, double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note, dimension_name, iter_views, place_view, view_name,
)

from _check import check
from _com import _bind, _early_bound
from _dimensions import _feature_display_dimensions
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
from _drawing_notes import add_property_linked_note, property_link
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_projection import model_points_in_view
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_sheet_region import sheet_drawable_region
from _purchased_fastener_drawing import (
    _box, _inside, assert_supplier_annotations_fit, assert_supplier_view_fits,
)
from _drawing_selection import _select_view_entity
from _rebuild import active_configuration_name
from _supplier_dimensions import (
    _measured_supplier_value,
    assert_supplier_reference_dimension, supplier_reference_dimension,
)
from _supplier_reference_geometry import (
    NativeSketchGeometry, capture_native_sketch_geometry, native_sketch_view_bounds,
)
from _drawing_view_display import set_hidden_lines_removed
from _session import run_build
from _sketch import blank_reference_sketches
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
    SUPPLIER_STOCK_SHANK_OUTLINE_MM,
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
STOCK_KEEP = {
    # Diametric text already has a leader: existing native annotation placement
    # moves the complete callout, leaving its source circle/value unchanged.
    "SupplierNominalEyeOD": (0.200, 0.250),
    "SupplierNominalWire": (0.255, 0.235),
    "SupplierStockShank": (0.105, 0.159),
    "SupplierStockOverall": (0.065, STOCK_CENTER[1]),
}
_STOCK_PROFILE_BLACK = 0  # COLORREF RGB(0, 0, 0)
_SW_SEL_EXT_SKETCH_SEGS = 24  # swSelectType_e.swSelEXTSKETCHSEGS
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
        or int(adapter.swApp.IsSame(native_view, view)) != 1
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
    failure: Exception | None = None
    try:
        _select_view_entity(adapter, front, "SILHOUETTE", point, label="EyeID")
        selection = _early_bound(adapter.currentModel.SelectionManager, "ISelectionMgr")
        count = int(selection.GetSelectedObjectCount2(-1))
        if count not in (1, 2):
            raise RuntimeError(
                "counter eye ID coordinate selection expected one silhouette and "
                f"optional parent view; actual count={count}"
            )
        eye = None
        parent_seen = False
        for index in range(1, count + 1):
            kind = int(selection.GetSelectedObjectType3(index, -1))
            entity = selection.GetSelectedObject6(index, -1)
            if entity is None:
                raise RuntimeError(
                    f"counter eye ID coordinate selection {index} expected nonnull "
                    f"entity; actual type={kind}, entity=None"
                )
            if kind == 46:  # swSelSILHOUETTES
                if eye is not None:
                    raise RuntimeError("counter eye ID coordinate selection has duplicate silhouettes")
                eye = entity
            elif kind == 12:  # swSelDRAWINGVIEWS: only the exact parent is permitted.
                if parent_seen:
                    raise RuntimeError(
                        "counter eye ID coordinate selection expected at most one "
                        f"parent view; actual duplicate parent view at index={index}"
                    )
                same = int(adapter.swApp.IsSame(entity, front))
                if same != 1:
                    raise RuntimeError(
                        "counter eye ID coordinate selection parent view expected "
                        f"IsSame=1; actual IsSame={same} at index={index}"
                    )
                parent_seen = True
            else:
                raise RuntimeError(
                    "counter eye ID coordinate selection expected type=46 or parent "
                    f"type=12; actual type={kind} at index={index}"
                )
        if eye is None:
            raise RuntimeError("counter eye ID coordinate selection has no physical silhouette")
        if _supplier_eye_circle(adapter, front, eye, finished_configuration) is None:
            raise RuntimeError(
                "unchanged counter eye has no exact ID circular silhouette; "
                f"expected physical ID={SUPPLIER_EYE_ID_MM} mm and mapped source Wire"
            )
        # The coordinate hit may include its parent view. Always replace that
        # UI bookkeeping with the proved entity, even for an initial single pick.
        _select_view_entity(
            adapter, front, "SILHOUETTE", None, label="EyeID", entity=eye,
        )
        count = int(selection.GetSelectedObjectCount2(-1))
        if count != 1:
            raise RuntimeError(
                f"counter eye ID final selection expected count=1; actual count={count}"
            )
        kind = int(selection.GetSelectedObjectType3(1, -1))
        if kind != 46:
            raise RuntimeError(
                f"counter eye ID final selection expected type=46; actual type={kind}"
            )
        eye = selection.GetSelectedObject6(1, -1)
        if eye is None:
            raise RuntimeError("counter eye ID final selection expected nonnull physical silhouette")
        if _supplier_eye_circle(adapter, front, eye, finished_configuration) is None:
            raise RuntimeError(
                "counter eye ID final selection lost its exact physical source contour; "
                f"expected physical ID={SUPPLIER_EYE_ID_MM} mm and mapped source Wire"
            )
        display = adapter.currentModel.AddDiameterDimension2(0.150, 0.241, 0.0)
    except Exception as error:
        failure = error
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


@dataclass(frozen=True)
class SupplierStockCapture:
    """Target-config model geometry and binding, without native geometry handles."""

    geometry: NativeSketchGeometry
    source_path: str
    configuration: str
    configuration_id: int

    def __post_init__(self):
        if (
            type(self.geometry) is not NativeSketchGeometry
            or type(self.source_path) is not str or not self.source_path
            or self.configuration != SUPPLIER_STOCK_CONFIGURATION
            or type(self.configuration_id) is not int
        ):
            raise RuntimeError("supplier nominal stock requires immutable geometry and source binding")


def _assert_supplier_stock_geometry(geometry: NativeSketchGeometry) -> None:
    """Match every actual source curve; an equal outer box is not identity."""
    label = "supplier nominal stock"
    if len(geometry.circle_offsets) != 3 or len(geometry.line_offsets) != 6:
        raise RuntimeError(
            f"{label}: expected exactly three circles and six lines; "
            f"actual circles={len(geometry.circle_offsets)}, lines={len(geometry.line_offsets)}"
        )

    def same(first, second):
        return all(abs(a - b) <= 1e-8 for a, b in zip(first, second, strict=True))

    circles = [
        ((0.0, 0.0, 0.0), SUPPLIER_NOMINAL_EYE_OD_MM / 2000.0),
        ((0.0, 0.0, 0.0), SUPPLIER_EYE_ID_MM / 2000.0),
        ((SUPPLIER_STOCK_WIRE_CENTER_MM[0] / 1000.0,
          SUPPLIER_STOCK_WIRE_CENTER_MM[1] / 1000.0, 0.0),
         SUPPLIER_NOMINAL_WIRE_MM / 2000.0),
    ]
    for offset in geometry.circle_offsets:
        center, xpoint, ypoint = geometry.model_points[offset:offset + 3]
        a = tuple(value - origin for value, origin in zip(xpoint, center, strict=True))
        b = tuple(value - origin for value, origin in zip(ypoint, center, strict=True))
        matches = [
            index for index, (wanted, radius) in enumerate(circles)
            if same(center, wanted)
            and abs(math.dist(center, xpoint) - radius) <= 1e-8
            and abs(math.dist(center, ypoint) - radius) <= 1e-8
            and abs(a[2]) <= 1e-8 and abs(b[2]) <= 1e-8
            and abs(sum(x * y for x, y in zip(a, b, strict=True))) <= 1e-12
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"{label}: native circle centre/radius/plane changed: "
                f"expected remaining centre/radius={circles!r}; "
                f"actual centre={center!r}, basis={a!r}/{b!r}, "
                f"radii={math.dist(center, xpoint)!r}/{math.dist(center, ypoint)!r}"
            )
        circles.pop(matches[0])
    outline = SUPPLIER_STOCK_SHANK_OUTLINE_MM
    pairs = [
        (outline[index], outline[(index + 1) % len(outline)])
        for index in range(len(outline))
    ] + list(zip(SUPPLIER_STOCK_AXIS_MM, SUPPLIER_STOCK_AXIS_MM[1:]))
    lines = [
        tuple((point[0] / 1000.0, point[1] / 1000.0, 0.0) for point in pair)
        for pair in pairs
    ]
    for offset in geometry.line_offsets:
        actual = geometry.model_points[offset:offset + 2]
        matches = [
            index for index, wanted in enumerate(lines)
            if (same(actual[0], wanted[0]) and same(actual[1], wanted[1]))
            or (same(actual[0], wanted[1]) and same(actual[1], wanted[0]))
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"{label}: native line inventory/endpoints changed: "
                f"expected one remaining pair={lines!r}; actual={actual!r}"
            )
        lines.pop(matches[0])


def _capture_supplier_stock(adapter, source_model, finished_configuration) -> SupplierStockCapture:
    """Capture solved stock while active, restoring the original source unsaved."""
    source_path = SOURCE.resolve().as_posix()
    source_type = int(source_model.GetType())
    actual_path = str(source_model.GetPathName()).replace("\\", "/")
    if source_type != 1 or actual_path.casefold() != source_path.casefold():
        raise RuntimeError(
            "supplier nominal stock capture requires the exact source part: "
            f"expected type=1 path={source_path!r}; actual type={source_type} path={actual_path!r}"
        )
    _verify_source_state(adapter, source_model, finished_configuration)
    raw_configuration = source_model.GetConfigurationByName(SUPPLIER_STOCK_CONFIGURATION)
    if raw_configuration is None:
        raise RuntimeError(f"supplier nominal stock configuration is missing: expected={SUPPLIER_STOCK_CONFIGURATION!r}")
    configuration = _early_bound(raw_configuration, "IConfiguration")
    configuration_name = str(configuration.Name)
    if configuration_name != SUPPLIER_STOCK_CONFIGURATION:
        raise RuntimeError(
            f"supplier nominal stock configuration expected={SUPPLIER_STOCK_CONFIGURATION!r}; "
            f"actual={configuration_name!r}"
        )
    configuration_id = int(configuration.GetID())

    def show(name):
        before = active_configuration_name(adapter, source_model)
        if before != name:
            result = source_model.ShowConfiguration2(name)
            if result is not True:
                raise RuntimeError(
                    f"cannot activate supplier source configuration: expected={name!r}; "
                    f"before={before!r}, ShowConfiguration2={result!r}"
                )
        actual = active_configuration_name(adapter, source_model)
        if actual != name:
            raise RuntimeError(f"supplier source configuration expected={name!r}; actual={actual!r}")
        result = source_model.EditRebuild3()
        if result is not True:
            raise RuntimeError(f"cannot rebuild supplier source configuration {name!r}: EditRebuild3={result!r}")
        actual = active_configuration_name(adapter, source_model)
        if actual != name:
            raise RuntimeError(f"supplier source rebuild configuration expected={name!r}; actual={actual!r}")

    primary = None
    try:
        show(SUPPLIER_STOCK_CONFIGURATION)
        part = _early_bound(source_model, "IPartDoc")
        counts = tuple(len(tuple(part.GetBodies2(kind, False) or ())) for kind in (0, 1))
        if counts != (0, 0):
            raise RuntimeError(
                f"supplier nominal stock must have zero solid/sheet bodies: "
                f"configuration={SUPPLIER_STOCK_CONFIGURATION!r}, expected=(0, 0), actual={counts!r}"
            )
        raw_feature = part.FeatureByName(SUPPLIER_STOCK_FEATURE)
        if raw_feature is None:
            raise RuntimeError(f"supplier nominal stock profile is missing: expected={SUPPLIER_STOCK_FEATURE!r}")
        feature = _early_bound(raw_feature, "IFeature")
        error = feature.GetErrorCode2()
        suppressed = tuple(feature.IsSuppressed2(3, bstr_array([SUPPLIER_STOCK_CONFIGURATION])) or ())
        owner_name, owner_type = str(feature.Name), str(feature.GetTypeName2())
        if owner_name != SUPPLIER_STOCK_FEATURE or owner_type != "ProfileFeature":
            raise RuntimeError(
                f"supplier nominal stock owner expected=({SUPPLIER_STOCK_FEATURE!r}, 'ProfileFeature'); "
                f"actual=({owner_name!r}, {owner_type!r})"
            )
        if len(suppressed) != 1 or suppressed[0] is not False:
            raise RuntimeError(
                f"supplier nominal stock owner suppression configuration={SUPPLIER_STOCK_CONFIGURATION!r}: "
                f"expected=(False,), actual={suppressed!r}"
            )
        # Warning is undefined when the returned error status is zero.
        if (
            not isinstance(error, (tuple, list)) or len(error) != 2
            or type(error[0]) is not int or error[0] != 0
        ):
            raise RuntimeError(
                f"supplier nominal stock owner expected integer GetErrorCode2 status=0; actual={error!r}"
            )
        expected = {
            "SupplierNominalEyeOD": SUPPLIER_NOMINAL_EYE_OD_MM,
            "SupplierNominalWire": SUPPLIER_NOMINAL_WIRE_MM,
            "SupplierStockShank": SUPPLIER_STOCK_SHANK_MM,
            "SupplierStockOverall": SUPPLIER_STOCK_OVERALL_MM,
        }
        found = []
        for raw in _feature_display_dimensions(feature):
            display = _early_bound(_bind(raw, "IDisplayDimension"), "IDisplayDimension")
            native = _early_bound(display.GetDimension2(0), "IDimension")
            owner = str(native.FullName).split("@")
            if owner[0] not in expected:
                continue
            if len(owner) < 2 or owner[1] != SUPPLIER_STOCK_FEATURE:
                raise RuntimeError(
                    f"supplier nominal stock dimension owner expected={SUPPLIER_STOCK_FEATURE!r}; "
                    f"actual FullName={str(native.FullName)!r}"
                )
            same = int(adapter.swApp.IsSame(native, feature.Parameter(owner[0])))
            if same != 1:
                raise RuntimeError(
                    f"{owner[0]}: supplier nominal stock source dimension expected IsSame=1; actual={same}"
                )
            _measured_supplier_value(
                display, label=f"{owner[0]} [{SUPPLIER_STOCK_CONFIGURATION}]", expected_mm=expected[owner[0]], expected_degrees=None,
                presentation="diameter" if owner[0].startswith("SupplierNominal") else "length",
                configuration=SUPPLIER_STOCK_CONFIGURATION,
            )
            found.append(owner[0])
        if sorted(found) != sorted(expected):
            raise RuntimeError(
                f"supplier nominal stock dimension inventory expected={sorted(expected)!r}; actual={found!r}"
            )
        geometry = capture_native_sketch_geometry(feature.GetSpecificFeature2(), label="supplier nominal stock")
        _assert_supplier_stock_geometry(geometry)
        actual_configuration = active_configuration_name(adapter, source_model)
        if actual_configuration != SUPPLIER_STOCK_CONFIGURATION:
            raise RuntimeError(
                f"supplier nominal stock capture configuration expected={SUPPLIER_STOCK_CONFIGURATION!r}; "
                f"actual={actual_configuration!r}"
            )
        return SupplierStockCapture(geometry, source_path, SUPPLIER_STOCK_CONFIGURATION, configuration_id)
    except BaseException as error:
        primary = error
        raise
    finally:
        restoration_errors = []
        try:
            show(finished_configuration)
        except BaseException as restore_error:
            restoration_errors.append(restore_error)
        try:
            part = _early_bound(source_model, "IPartDoc")
            changed = tuple(
                name for name in REFERENCE_SKETCHES
                if int(_early_bound(part.FeatureByName(name), "IFeature").Visible) != 1
            )
            if changed:
                blank_reference_sketches(adapter, changed)
            _verify_source_state(adapter, source_model, finished_configuration)
        except BaseException as restore_error:
            restoration_errors.append(restore_error)
        if restoration_errors:
            pending = primary if primary is not None else restoration_errors[0]
            for restore_error in restoration_errors:
                if restore_error is not pending:
                    pending.add_note(f"Supplier source restoration also failed: {restore_error}")
            if primary is None:
                raise pending


def _supplier_stock_bounds(adapter, stock, source_model, capture: SupplierStockCapture):
    """Measure full native stock ink only in the exact captured view binding."""
    if type(capture) is not SupplierStockCapture:
        raise RuntimeError("supplier nominal stock requires an immutable source capture")
    stock = _early_bound(stock, "IView")
    raw_source = stock.ReferencedDocument
    if raw_source is None:
        raise RuntimeError("supplier nominal stock view expected referenced source part; actual=None")
    same = int(adapter.swApp.IsSame(raw_source, source_model))
    if same != 1:
        raise RuntimeError(f"supplier nominal stock view source identity expected IsSame=1; actual={same}")
    source = _early_bound(raw_source, "IModelDoc2")
    for field, actual, expected in (
        ("source document type", int(source.GetType()), 1),
        ("capture source path", capture.source_path.casefold(), SOURCE.resolve().as_posix().casefold()),
        ("source document path", str(source.GetPathName()).replace("\\", "/").casefold(), capture.source_path.casefold()),
        ("view model path", str(stock.GetReferencedModelName()).replace("\\", "/").casefold(), capture.source_path.casefold()),
        ("capture configuration", capture.configuration, SUPPLIER_STOCK_CONFIGURATION),
        ("view configuration", str(stock.ReferencedConfiguration), capture.configuration),
    ):
        if actual != expected:
            raise RuntimeError(f"supplier nominal stock {field}: expected={expected!r}; actual={actual!r}")
    raw_configuration = source.GetConfigurationByName(capture.configuration)
    if raw_configuration is None:
        raise RuntimeError(f"supplier nominal stock configuration expected={capture.configuration!r}; actual=None")
    configuration = _early_bound(raw_configuration, "IConfiguration")
    for field, actual, expected in (
        ("configuration name", str(configuration.Name), capture.configuration),
        ("configuration ID", int(configuration.GetID()), capture.configuration_id),
    ):
        if actual != expected:
            raise RuntimeError(f"supplier nominal stock {field}: expected={expected!r}; actual={actual!r}")
    view_type = int(stock.Type)
    if view_type not in (6, 7):
        raise RuntimeError(f"supplier nominal stock full native view Type: expected=6 or 7; actual={view_type}")
    for field, actual, expected in (
        ("base view present", stock.GetBaseView() is not None, False),
        ("IsCropped", stock.IsCropped(), False),
        ("IsBroken", stock.IsBroken(), False),
        ("IsPerspectiveView", stock.IsPerspectiveView(), False),
        ("break count", len(tuple(stock.GetBreakLines() or ())), 0),
        ("broken-out section count", int(stock.GetBreakOutSectionCount()), 0),
        ("UseSheetScale", int(stock.UseSheetScale), 0),
        ("ScaleRatio", tuple(float(value) for value in stock.ScaleRatio), STOCK_SCALE),
        ("GetDisplayMode2", int(stock.GetDisplayMode2()), 2),
    ):
        if actual != expected or (type(expected) is bool and type(actual) is not bool):
            raise RuntimeError(
                f"supplier nominal stock full native view/scale {field}: expected={expected!r}; actual={actual!r}"
            )
    decimal = float(stock.ScaleDecimal)
    ratio = STOCK_SCALE[0] / STOCK_SCALE[1]
    if not math.isclose(decimal, ratio, rel_tol=0.0, abs_tol=1e-12):
        raise RuntimeError(f"supplier nominal stock native view/scale ScaleDecimal: expected={ratio}; actual={decimal!r}")
    raw_sketch = stock.GetSketch()
    if raw_sketch is None:
        raise RuntimeError("supplier nominal stock full view expected drawing sketch; actual=None")
    count = len(tuple(_early_bound(raw_sketch, "ISketch").GetSketchSegments() or ()))
    if count != 0:
        raise RuntimeError(f"supplier nominal stock full view drawing-sketch segment count: expected=0; actual={count}")
    stock.UpdateViewDisplayGeometry()
    bounds = native_sketch_view_bounds(adapter, stock, capture.geometry, label="supplier nominal stock")
    ratio = STOCK_SCALE[0] / STOCK_SCALE[1]
    expected_spans = (
        (SUPPLIER_STOCK_WIRE_CENTER_MM[0] + SUPPLIER_NOMINAL_WIRE_MM / 2.0
         + SUPPLIER_NOMINAL_EYE_OD_MM / 2.0) / 1000.0 * ratio,
        SUPPLIER_STOCK_OVERALL_MM / 1000.0 * ratio,
    )
    for axis, actual, expected in zip(
        ("x", "y"), (bounds[2] - bounds[0], bounds[3] - bounds[1]), expected_spans, strict=True,
    ):
        if not expected - 1e-7 <= actual <= expected + 2.0 * DEFAULT_BOUNDARY_ALLOWANCE_M:
            raise RuntimeError(
                f"revealed supplier diagram native ink does not cover its source profile: axis={axis}, "
                f"expected=[{expected - 1e-7!r}, {expected + 2.0 * DEFAULT_BOUNDARY_ALLOWANCE_M!r}], "
                f"actual={actual!r}, native bounds={bounds!r}"
            )
    return bounds


def _supplier_profile_curve(raw, label):
    """Read one actual construction curve without querying visual properties."""
    segment = _early_bound(raw, "ISketchSegment")
    kind = segment.GetType()
    construction = segment.ConstructionGeometry
    length = float(segment.GetLength())
    if (
        type(kind) is not int or kind not in (0, 1)
        or construction is not True or not math.isfinite(length) or length <= 0.0
    ):
        raise RuntimeError(f"{label}: expected a finite construction line or complete circle")

    def point(raw_point):
        if raw_point is None:
            raise RuntimeError(f"{label}: missing native profile point")
        native = _early_bound(raw_point, "ISketchPoint")
        xyz = (float(native.X), float(native.Y), float(native.Z))
        if not all(map(math.isfinite, xyz)):
            raise RuntimeError(f"{label}: nonfinite native profile point")
        return xyz

    if kind == 0:  # swSketchLINE
        line = _early_bound(raw, "ISketchLine")
        geometry = (*point(line.GetStartPoint2()), *point(line.GetEndPoint2()))
    else:  # swSketchARC, restricted to the three existing complete circles.
        circle = _early_bound(raw, "ISketchArc")
        complete = circle.IsCircle()
        radius = float(circle.GetRadius())
        if type(complete) is not int or complete != 1 or not math.isfinite(radius) or radius <= 0.0:
            raise RuntimeError(f"{label}: expected a complete native profile circle")
        geometry = (*point(circle.GetCenterPoint2()), radius)
    return kind, construction, length, geometry


def _supplier_profile_appearance(segment, label):
    """Snapshot only the supported DRAWING-instance properties we must preserve."""
    appearance = (segment.Width, segment.Style, segment.Layer)
    if (
        type(appearance[0]) is not int or type(appearance[1]) is not int
        or type(appearance[2]) is not str
    ):
        raise RuntimeError(f"{label}: unavailable drawing Width/Style/Layer")
    # LayerOverride is undefined for the normal empty layer; do not query it.
    return appearance


def _supplier_stock_profile_instances(adapter, stock, source_model, capture):
    """Resolve all nine exact source curves into this one proved stock view."""
    _supplier_stock_bounds(adapter, stock, source_model, capture)
    feature = _early_bound(
        _early_bound(source_model, "IPartDoc").FeatureByName(SUPPLIER_STOCK_FEATURE), "IFeature",
    )
    if feature is None or feature.Name != SUPPLIER_STOCK_FEATURE or feature.GetTypeName2() != "ProfileFeature":
        raise RuntimeError("supplier nominal stock profile owner changed")
    sketch = _early_bound(feature.GetSpecificFeature2(), "ISketch")
    # Re-read actual source geometry, without activating or saving that part.
    _assert_supplier_stock_geometry(
        capture_native_sketch_geometry(sketch, label="supplier nominal stock black profile")
    )
    sources = tuple(sketch.GetSketchSegments() or ())
    if len(sources) != 9:
        raise RuntimeError(f"supplier nominal stock source inventory expected=9 segments; actual={len(sources)}")
    instances = []
    app = _early_bound(adapter.swApp, "ISldWorks")
    for index, raw in enumerate(sources):
        label = f"supplier nominal stock profile segment {index}"
        source = _early_bound(raw, "ISketchSegment")
        curve = _supplier_profile_curve(source, label)
        mapped = stock.GetCorresponding(source)
        if mapped is None:
            raise RuntimeError(f"{label}: missing drawing correspondence")
        mapped = _early_bound(mapped, "ISketchSegment")
        if _supplier_native_same(app, source, mapped, label) != 0:
            raise RuntimeError(f"{label}: correspondence is the source, not a drawing instance")
        for previous_source, previous_mapped, _curve, _appearance in instances:
            if (
                _supplier_native_same(app, source, previous_source, label) != 0
                or _supplier_native_same(app, mapped, previous_mapped, label) != 0
            ):
                raise RuntimeError(f"{label}: duplicate native source or drawing instance")
        if _supplier_profile_curve(mapped, label) != curve:
            raise RuntimeError(f"{label}: drawing correspondence changed native curve geometry")
        instances.append((source, mapped, curve, _supplier_profile_appearance(mapped, label)))
    if sorted(curve[0] for _source, _mapped, curve, _appearance in instances) != [0] * 6 + [1] * 3:
        raise RuntimeError("supplier nominal stock requires exactly three circles and six lines")
    return tuple(instances)


def _report_supplier_selection_identity(
    adapter, draw, drawing, stock, source_model, capture, instances,
    index, selected, selection, data, select_result, count, kind, error,
):
    """Temporary, read-only failure receipt; remove after actual native root proof.

    Only the nine already acquired pairs are inspected. Raw IsSame results,
    ordered GetID pairs, names and geometry are observations, NEVER acceptance
    or alternate selection routes. GetID is sketch/kind-local, not persistent
    and not assumed to survive source-to-drawing correspondence.
    """
    selected_none = selected is None  # Capture before binding or calling selected.
    context, rows = {}, []

    def render(value, depth=0):
        if type(value) in (tuple, list) and depth < 4:
            items = [render(item, depth + 1) for item in value[:16]]
            return items + (["<truncated after 16 values>"] if len(value) > 16 else [])
        if type(value) is float and not math.isfinite(value):
            return repr(value)
        if value is None or type(value) in (bool, int, float, str):
            return value
        return repr(value)[:512]

    def probe(fields, name, getter, *required):
        try:
            if any(value is None for value in required):
                fields[name] = {
                    "value": None, "python_type": "builtins.NoneType",
                    "error": "not queried: null or unavailable prerequisite",
                }
                return None
            value = getter()
            value_type = f"{type(value).__module__}.{type(value).__qualname__}"
            fields[name] = {"value": render(value), "python_type": value_type, "error": None}
            return value
        except BaseException as failure:
            try:
                message = str(failure)
            except BaseException:
                message = "<exception text unavailable>"
            fields[name] = {
                "value": None, "python_type": "builtins.NoneType",
                "error": f"{type(failure).__name__}: {message}",
            }
            return None

    def bind(fields, name, raw, interface):
        return probe(fields, name, lambda: _early_bound(raw, interface), raw)

    probe(context, "selectedNone", lambda: selected_none)
    probe(context, "original_error", lambda: str(error))
    probe(context, "original_error_type", lambda: type(error).__name__)
    for name, value in (
        ("expected_index", index), ("Select4", select_result),
        ("selection_count", count), ("selection_type", kind),
        ("capture.source_path", capture.source_path),
        ("capture.configuration", capture.configuration),
        ("capture.configuration_id", capture.configuration_id),
        ("spec.source_path", SOURCE.resolve().as_posix()),
        ("spec.configuration", SUPPLIER_STOCK_CONFIGURATION),
    ):
        probe(context, name, lambda value=value: value)
    app = bind(context, "app", adapter.swApp, "ISldWorks")

    def same(fields, name, first, second):
        # Deliberately NOT _supplier_native_same: preserve raw 0/1/2/3/types.
        return probe(fields, name, lambda: app.IsSame(first, second), app, first, second)

    def both(fields, name, first, second):
        same(fields, f"{name}.forward", first, second)
        same(fields, f"{name}.reverse", second, first)

    source = bind(context, "source", source_model, "IModelDoc2")
    probe(context, "drawing.GetPathName", lambda: draw.GetPathName(), draw)
    probe(context, "source.GetPathName", lambda: source.GetPathName(), source)
    part = bind(context, "source.part", source_model, "IPartDoc")
    feature_raw = probe(
        context, "source.profile_feature",
        lambda: part.FeatureByName(SUPPLIER_STOCK_FEATURE), part,
    )
    feature = bind(context, "source.profile_feature.typed", feature_raw, "IFeature")
    sketch_raw = probe(
        context, "source.authoritative_sketch.raw",
        lambda: feature.GetSpecificFeature2(), feature,
    )
    authoritative = bind(context, "source.authoritative_sketch", sketch_raw, "ISketch")
    same(context, "source.authoritative_sketch.self", authoritative, authoritative)
    extension_raw = probe(context, "drawing.Extension", lambda: draw.Extension, draw)
    extension = bind(context, "drawing.Extension.typed", extension_raw, "IModelDocExtension")
    manager_raw = probe(context, "source.ConfigurationManager", lambda: source.ConfigurationManager, source)
    manager = bind(context, "source.ConfigurationManager.typed", manager_raw, "IConfigurationManager")
    active_raw = probe(context, "source.active_configuration.raw", lambda: manager.ActiveConfiguration, manager)
    expected_raw = probe(
        context, "source.expected_configuration.raw",
        lambda: source.GetConfigurationByName(capture.configuration), source,
    )
    for name, raw in (("active", active_raw), ("expected", expected_raw)):
        configuration = bind(context, f"source.{name}_configuration", raw, "IConfiguration")
        probe(context, f"source.{name}_configuration.Name", lambda: configuration.Name, configuration)
        probe(context, f"source.{name}_configuration.GetID", lambda: configuration.GetID(), configuration)
    both(context, "source.active_to_expected_configuration", active_raw, expected_raw)

    def view_control(name, raw):
        view = bind(context, name, raw, "IView")
        same(context, f"{name}.self", view, view)
        both(context, f"{name}.to_expected", view, stock)
        probe(context, f"{name}.GetName2", lambda: view.GetName2(), view)
        probe(context, f"{name}.GetReferencedModelName", lambda: view.GetReferencedModelName(), view)
        probe(context, f"{name}.ReferencedConfiguration", lambda: view.ReferencedConfiguration, view)
        referenced = probe(context, f"{name}.ReferencedDocument", lambda: view.ReferencedDocument, view)
        same(context, f"{name}.ReferencedDocument.self", referenced, referenced)
        both(context, f"{name}.ReferencedDocument.to_source", referenced, source_model)
        referenced_model = bind(context, f"{name}.ReferencedDocument.typed", referenced, "IModelDoc2")
        probe(
            context, f"{name}.ReferencedDocument.GetPathName",
            lambda: referenced_model.GetPathName(), referenced_model,
        )

    active_view = probe(context, "active_view.raw", lambda: drawing.ActiveDrawingView, drawing)
    data_view = probe(context, "data_view.raw", lambda: data.View, data)
    # A missing selected entity must not cause ANY selected-specific API call.
    selected_view = probe(
        context, "selected_view.raw",
        lambda: selection.GetSelectedObjectsDrawingView2(1, -1), selection, selected,
    )
    for name, raw in (
        ("stock_view", stock), ("active_view", active_view),
        ("data_view", data_view), ("selected_view", selected_view),
    ):
        view_control(name, raw)

    def owner_control(fields, name, segment, drawing_context):
        owner = probe(fields, f"{name}.GetSketch", lambda: segment.GetSketch(), segment)
        same(fields, f"{name}.owner.self", owner, owner)
        both(fields, f"{name}.owner.to_authoritative", owner, authoritative)
        if drawing_context:
            reverse = probe(
                fields, f"{name}.owner.GetCorresponding2",
                lambda: extension.GetCorresponding2(owner), extension, owner,
            )
            same(fields, f"{name}.owner.reverse.self", reverse, reverse)
            both(fields, f"{name}.owner.reverse.to_authoritative", reverse, authoritative)

    def segment_control(fields, name, segment, drawing_context):
        probe(fields, f"{name}.GetType", lambda: segment.GetType(), segment)
        pair = probe(fields, f"{name}.GetID", lambda: segment.GetID(), segment)
        for offset in (0, 1):
            probe(fields, f"{name}.GetID[{offset}]", lambda offset=offset: pair[offset], pair)
        same(fields, f"{name}.self", segment, segment)
        owner_control(fields, name, segment, drawing_context)

    typed_selected = bind(context, "selected.typed", selected, "ISketchSegment")
    segment_control(context, "selected.raw", selected, True)
    segment_control(context, "selected.typed", typed_selected, True)
    both(context, "selected.raw_to_typed", selected, typed_selected)
    for row_index, (source_segment, mapped, _curve, _appearance) in enumerate(instances):
        row = {}
        probe(row, "index", lambda: row_index)
        probe(row, "expected", lambda: row_index == index)
        segment_control(row, "source", source_segment, False)
        segment_control(row, "mapped", mapped, True)
        both(row, "source_to_mapped", source_segment, mapped)
        both(row, "selected.raw_to_source", selected, source_segment)
        both(row, "selected.raw_to_mapped", selected, mapped)
        both(row, "selected.typed_to_source", typed_selected, source_segment)
        both(row, "selected.typed_to_mapped", typed_selected, mapped)
        rows.append(row)

    def finite(fields, name, getter, *required):
        value = probe(fields, name, getter, *required)
        probe(fields, f"{name}.finite", lambda: math.isfinite(value), value)

    def geometry(name, segment, expected_kind):
        probe(context, f"{name}.ConstructionGeometry", lambda: segment.ConstructionGeometry, segment)
        finite(context, f"{name}.GetLength", lambda: segment.GetLength(), segment)
        interface = "ISketchLine" if expected_kind == 0 else "ISketchArc"
        native = bind(context, f"{name}.{interface}", segment, interface)
        if expected_kind == 0:
            points = (("start", "GetStartPoint2"), ("end", "GetEndPoint2"))
        else:
            probe(context, f"{name}.IsCircle", lambda: native.IsCircle(), native)
            finite(context, f"{name}.GetRadius", lambda: native.GetRadius(), native)
            points = (("center", "GetCenterPoint2"),)
        for point_name, getter in points:
            point_raw = probe(context, f"{name}.{getter}", lambda: getattr(native, getter)(), native)
            point = bind(context, f"{name}.{point_name}", point_raw, "ISketchPoint")
            for coordinate in ("X", "Y", "Z"):
                finite(
                    context, f"{name}.{point_name}.{coordinate}",
                    lambda coordinate=coordinate: getattr(point, coordinate), point,
                )

    source_segment, mapped, curve, _appearance = instances[index]
    probe(context, "candidate.acquired_curve", lambda: curve)
    for name, segment in (
        ("candidate.source", source_segment), ("candidate.mapped", mapped),
        ("candidate.selected.raw", selected), ("candidate.selected.typed", typed_selected),
    ):
        geometry(name, segment, curve[0])
    # Separate bounded lines keep all nine rows readable in the actual task log.
    for section, fields in (("context", context), *(("row", row) for row in rows)):
        try:
            _telemetry.warn(
                "supplier stock selection identity REPORTING ONLY / NO MUTATING PROBES: "
                + json.dumps({"section": section, "fields": fields})
            )
        except BaseException:
            pass  # Emission must never replace the original identity refusal.


def _blacken_supplier_stock_profile(adapter, stock, source_model, capture):
    """Change only the nine mapped STOCK-instance colors, before native save."""
    draw = _early_bound(adapter.currentModel, "IModelDoc2")
    drawing = _early_bound(draw, "IDrawingDoc")
    stock = _early_bound(stock, "IView")
    instances = _supplier_stock_profile_instances(adapter, stock, source_model, capture)
    app = _early_bound(adapter.swApp, "ISldWorks")
    if drawing.ActivateView(view_name(adapter, stock)) is not True:
        raise RuntimeError("cannot activate supplier stock view for its black profile")
    if _supplier_native_same(app, drawing.ActiveDrawingView, stock, "supplier stock active view") != 1:
        raise RuntimeError("supplier black profile activated a foreign drawing view")
    primary = None
    try:
        selection = _early_bound(draw.SelectionManager, "ISelectionMgr")
        for index, (_source, mapped, curve, appearance) in enumerate(instances):
            label = "supplier nominal stock black profile"
            draw.ClearSelection2(True)
            data = _early_bound(selection.CreateSelectData(), "ISelectData")
            data.View = stock
            if _supplier_native_same(app, data.View, stock, label) != 1:
                raise RuntimeError(f"{label}: selection data lost its exact drawing view")
            # ISketchSegment.Select4 applies to circles too; no point/type fallback.
            select_result = mapped.Select4(False, data)
            if select_result is not True:
                raise RuntimeError(f"{label}: native Select4 refused the mapped curve")
            count = selection.GetSelectedObjectCount2(-1)
            kind = selection.GetSelectedObjectType3(1, -1)
            if type(count) is not int or count != 1 or type(kind) is not int or kind != _SW_SEL_EXT_SKETCH_SEGS:
                raise RuntimeError(f"{label}: expected one native EXTSKETCHSEGMENT; count={count!r}, type={kind!r}")
            selected = selection.GetSelectedObject6(1, -1)
            try:
                if selected is None or _supplier_native_same(app, selected, mapped, label) != 1:
                    raise RuntimeError(f"{label}: selection is not the exact mapped native curve")
            except BaseException as identity_error:
                try:
                    _report_supplier_selection_identity(
                        adapter, draw, drawing, stock, source_model, capture, instances,
                        index, selected, selection, data, select_result, count, kind, identity_error,
                    )
                except BaseException:
                    pass  # A broken reporter must not mask this exact refusal.
                raise
            selected = _early_bound(selected, "ISketchSegment")
            if _supplier_profile_curve(selected, label) != curve or _supplier_profile_appearance(selected, label) != appearance:
                raise RuntimeError(f"{label}: selected native geometry or appearance changed")
            drawing.SetLineColor(_STOCK_PROFILE_BLACK)  # VOID: success is readback, not truthiness.
            color = selected.Color
            if type(color) is not int or color != _STOCK_PROFILE_BLACK:
                raise RuntimeError(f"{label}: drawing color expected=0; actual={color!r}")
            if _supplier_profile_curve(selected, label) != curve or _supplier_profile_appearance(selected, label) != appearance:
                raise RuntimeError(f"{label}: color operation changed native geometry or Width/Style/Layer")
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            draw.ClearSelection2(True)
        except BaseException as cleanup_error:
            if primary is None:
                raise
            primary.add_note(f"supplier black-profile selection cleanup also failed: {cleanup_error}")
    rebuilt = draw.EditRebuild3()
    if rebuilt is not True:
        raise RuntimeError(f"cannot rebuild the black supplier stock profile: EditRebuild3={rebuilt!r}")
    # Fresh source/mapped handles after the drawing rebuild, never after SaveAs3.
    current = _supplier_stock_profile_instances(adapter, stock, source_model, capture)
    for _source, mapped, curve, appearance in current:
        matches = [
            before for before in instances
            if _supplier_native_same(app, before[1], mapped, "settled supplier black profile") == 1
        ]
        if len(matches) != 1 or matches[0][2:] != (curve, appearance):
            raise RuntimeError("supplier black profile changed its native instance, geometry or Width/Style/Layer")
        color = mapped.Color
        if type(color) is not int or color != _STOCK_PROFILE_BLACK:
            raise RuntimeError(f"settled supplier black profile color expected=0; actual={color!r}")


def _supplier_stock_diagram(adapter: Any, source_model: Any, capture: SupplierStockCapture):
    """A separate zero-body source profile, never false-sized finished edges."""
    stock = _early_bound(
        place_view(adapter, str(SOURCE), "*Front", *STOCK_CENTER, scale=STOCK_SCALE),
        "IView",
    )
    stock.ReferencedConfiguration = SUPPLIER_STOCK_CONFIGURATION
    if str(stock.ReferencedConfiguration) != SUPPLIER_STOCK_CONFIGURATION:
        raise RuntimeError(
            f"supplier stock view configuration expected={SUPPLIER_STOCK_CONFIGURATION!r}; "
            f"actual={str(stock.ReferencedConfiguration)!r}"
        )
    set_hidden_lines_removed(adapter, stock)
    # Reveal the saved-hidden sketch before the first native projection/fit.
    shown = _show_hidden_owners(
        adapter, stock, (SUPPLIER_STOCK_FEATURE,),
        view_label="counter anchor source diagram before fitting",
    )
    if set(shown) != {SUPPLIER_STOCK_FEATURE}:
        raise RuntimeError(
            f"counter anchor source diagram shown owner expected={[SUPPLIER_STOCK_FEATURE]!r}; actual={shown!r}"
        )
    rebuilt = adapter.currentModel.EditRebuild3()
    if rebuilt is not True:
        raise RuntimeError(f"cannot rebuild the revealed supplier nominal stock view: EditRebuild3={rebuilt!r}")
    stock.UpdateViewDisplayGeometry()
    _supplier_stock_profile_instances(adapter, stock, source_model, capture)
    # Correspondence proves source membership, not visibility through an
    # invented IFeature.Visible receipt. Showing uses the established per-view
    # override above; actual target-config geometry was captured before drawing.
    _supplier_stock_bounds(adapter, stock, source_model, capture)
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
    rebuilt = adapter.currentModel.EditRebuild3()
    if rebuilt is not True:
        raise RuntimeError(f"cannot position the complete supplier stock envelope: EditRebuild3={rebuilt!r}")
    keep = STOCK_KEEP
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
        if name in ("SupplierNominalEyeOD", "SupplierStockShank"):
            raw_current = display.GetAnnotation()
            if raw_current is None:
                raise RuntimeError(f"{name}: complete native supplier annotation is missing")
            current = _early_bound(raw_current, "IAnnotation")
            position = tuple(float(value) for value in (current.GetPosition() or ()))
            if (
                len(position) != 3 or not all(map(math.isfinite, position))
                or math.dist(position[:2], STOCK_KEEP[name]) > 1e-5
            ):
                raise RuntimeError(f"{name}: complete native supplier annotation did not retain its placement")
    # Apply the instance-only presentation after centering and dimension curation
    # have rebuilt the drawing, then return to sheet context for the notes below.
    _blacken_supplier_stock_profile(adapter, stock, source_model, capture)
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
        notes.append((_early_bound(note, "INote"), text, text))
    return stock, refs, notes


@dataclass(frozen=True)
class SupplierReferenceSnapshot:
    """Strict pre-save native identities and metadata, never geometry proxies."""

    sheet_name: str
    expected_key: str
    label: str
    annotation: Any
    view: Any
    drawing_document: Any
    source_document: Any
    drawing_path: str
    view_name: str
    configuration: str
    source_path: str


def _supplier_native_same(app, first, second, label):
    if first is None or second is None:
        raise RuntimeError(f"{label}: missing native identity")
    same = app.IsSame(first, second)
    if type(same) is not int or same not in (0, 1):
        raise RuntimeError(f"{label}: unknown native IsSame={same!r}")
    return same


def _supplier_reference_source(view, configuration, label):
    if view.ReferencedConfiguration != configuration:
        raise RuntimeError(f"{label}: supplier source configuration changed")
    raw_source = view.ReferencedDocument
    if raw_source is None:
        raise RuntimeError(f"{label}: missing supplier source document")
    source = _early_bound(raw_source, "IModelDoc2")
    path = source.GetPathName()
    if (
        not isinstance(path, str)
        or path.replace("\\", "/").casefold() != SOURCE.resolve().as_posix().casefold()
    ):
        raise RuntimeError(f"{label}: supplier source path changed: {path!r}")
    return source, path


def _supplier_reference_owner(app, annotation, view, source, configuration, label):
    kind = annotation.GetType()
    if type(kind) is not int or kind != 4:  # swDisplayDimension
        raise RuntimeError(f"{label}: original annotation is not a display dimension")
    owner_type = annotation.OwnerType
    if type(owner_type) is not int or owner_type != 0:  # swAnnotationOwner_DrawingView
        raise RuntimeError(f"{label}: supplier annotation must have native drawing-view owner 0")
    raw_owner = annotation.Owner
    if raw_owner is None:
        raise RuntimeError(f"{label}: supplier annotation has no native view owner")
    owner = _early_bound(raw_owner, "IView")
    if _supplier_native_same(app, owner, view, f"{label} owner") != 1:
        raise RuntimeError(f"{label}: supplier annotation has a foreign native view owner")
    owner_source, _path = _supplier_reference_source(owner, configuration, label)
    if _supplier_native_same(app, owner_source, source, f"{label} owner source") != 1:
        raise RuntimeError(f"{label}: supplier annotation owner source identity changed")


def _capture_supplier_reference_identity(adapter, sheet_name, key, label, view, display):
    """Gate the immutable original identity only after complete strict checks."""
    app = _early_bound(adapter.swApp, "ISldWorks")
    document = _early_bound(adapter.currentModel, "IModelDoc2")
    drawing_path = document.GetPathName()
    if not isinstance(drawing_path, str):
        raise RuntimeError(f"{label}: native drawing path is unavailable")
    view = _early_bound(view, "IView")
    name = view_name(adapter, view)
    configuration = view.ReferencedConfiguration
    if not isinstance(name, str) or not name or not isinstance(configuration, str) or not configuration:
        raise RuntimeError(f"{label}: native supplier view metadata is unavailable")
    source, source_path = _supplier_reference_source(view, configuration, label)
    raw_annotation = display.GetAnnotation()
    if raw_annotation is None:
        raise RuntimeError(f"{label}: missing original supplier annotation")
    annotation = _early_bound(raw_annotation, "IAnnotation")
    _supplier_reference_owner(app, annotation, view, source, configuration, label)
    return SupplierReferenceSnapshot(
        sheet_name, key, label, annotation, view, document, source,
        drawing_path, name, configuration, source_path,
    )


def _capture_saved_supplier_references(adapter, refs_by_sheet, view_contracts, prior):
    """Capture exact current keys ONLY through unique original native annotations.

    This still-open observer does not prove save success or cold persistence.
    It never derives a name from the old key, reads captured geometry, refreshes
    views, or changes a source configuration. Any unavailable metadata refuses.
    """
    if prior is None:
        raise RuntimeError("counter anchor has no successfully verified original snapshot")
    expected = {
        (sheet, key): contract
        for sheet, refs in refs_by_sheet.items() for key, contract in refs
    }
    originals = {(item.sheet_name, item.expected_key): item for item in prior}
    if (
        len(expected) != 6 or len(originals) != 6 or len(prior) != 6
        or set(originals) != set(expected)
    ):
        raise RuntimeError("counter anchor saved capture requires all six original supplier identities")
    app = _early_bound(adapter.swApp, "ISldWorks")
    document = _early_bound(adapter.currentModel, "IModelDoc2")
    path = document.GetPathName()
    if (
        not isinstance(path, str)
        or path.replace("\\", "/").casefold() != OUTPUTS.slddrw.resolve().as_posix().casefold()
    ):
        raise RuntimeError(f"saved supplier drawing path is not the native output: {path!r}")
    drawing = _early_bound(document, "IDrawingDoc")
    captured = {}
    captured_keys = set()
    for sheet_name, refs in refs_by_sheet.items():
        if drawing.ActivateSheet(sheet_name) is not True:
            raise RuntimeError(f"cannot capture saved supplier references on {sheet_name}")
        names, configuration = view_contracts[sheet_name]
        views = tuple(_early_bound(raw, "IView") for raw in iter_views(adapter))
        matches = tuple(view for view in views if view_name(adapter, view) == names[0])
        if len(matches) != 1:
            raise RuntimeError(f"{sheet_name}: saved supplier view must be unique")
        view = matches[0]
        source, source_path = _supplier_reference_source(view, configuration, sheet_name)
        annotations = tuple(
            _early_bound(raw, "IAnnotation") for raw in (view.GetAnnotations() or ())
        )
        current_refs = []
        for key, contract in refs:
            original = originals[sheet_name, key]
            label = contract["label"]
            if (
                original.label != label or original.view_name != names[0]
                or original.configuration != configuration
                or original.source_path.replace("\\", "/").casefold()
                != source_path.replace("\\", "/").casefold()
            ):
                raise RuntimeError(f"{label}: saved supplier metadata differs from its original contract")
            for identity, before, current in (
                ("drawing", original.drawing_document, document),
                ("view", original.view, view),
                ("source", original.source_document, source),
            ):
                if _supplier_native_same(app, before, current, f"{label} {identity}") != 1:
                    raise RuntimeError(f"{label}: saved supplier {identity} identity changed")
            matches = tuple(
                annotation for annotation in annotations
                if _supplier_native_same(app, original.annotation, annotation, label) == 1
            )
            if len(matches) != 1:
                raise RuntimeError(
                    f"{label}: expected one current original supplier annotation; actual={len(matches)}"
                )
            annotation = matches[0]
            _supplier_reference_owner(app, annotation, view, source, configuration, label)
            raw_display = annotation.GetSpecificAnnotation()
            if raw_display is None:
                raise RuntimeError(f"{label}: original supplier display dimension is missing")
            display = _early_bound(raw_display, "IDisplayDimension")
            raw_returned = display.GetAnnotation()
            if raw_returned is None or _supplier_native_same(
                app, annotation, _early_bound(raw_returned, "IAnnotation"), f"{label} display annotation",
            ) != 1:
                raise RuntimeError(f"{label}: supplier display has a foreign native annotation")
            raw_native = display.GetDimension2(0)
            if raw_native is None:
                raise RuntimeError(f"{label}: original supplier native dimension is missing")
            current_key = _early_bound(raw_native, "IDimension").FullName
            if not isinstance(current_key, str) or not current_key or current_key in captured_keys:
                raise RuntimeError(f"{label}: saved supplier dimension key is empty or duplicate")
            captured_keys.add(current_key)
            current_refs.append((current_key, contract))
        captured[sheet_name] = current_refs
    return captured


def _verify_supplier_references(adapter, refs_by_sheet, view_contracts):
    """Read geometry and attachments without refreshing or repairing the views."""
    if sum(len(refs) for refs in refs_by_sheet.values()) != 6:
        raise RuntimeError("counter anchor must retain all six supplier dimensions")
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    identities = []
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
            identities.append((sheet_name, key, contract["label"], view, display))
    # No identity snapshot is accepted until every strict reference check passed.
    snapshots = tuple(
        _capture_supplier_reference_identity(adapter, *identity) for identity in identities
    )
    app = _early_bound(adapter.swApp, "ISldWorks")
    for index, original in enumerate(snapshots):
        names, configuration = view_contracts[original.sheet_name]
        if original.view_name != names[0] or original.configuration != configuration:
            raise RuntimeError(f"{original.label}: original supplier view metadata changed during verification")
        for other in snapshots[:index]:
            if _supplier_native_same(app, original.annotation, other.annotation, original.label) != 0:
                raise RuntimeError("supplier reference originals must be distinct native annotations")
    return snapshots


def _verify_supplier_layout(adapter, view_contracts, notes_by_sheet, source_model, stock_capture):
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
        notes = notes_by_sheet.get(sheet_name)
        expected_count = 5 if sheet_name == SHEET_NAMES[0] else 2
        if notes is None or len(notes) != expected_count:
            raise RuntimeError(
                f"{sheet_name}: expected {expected_count} sheet notes; "
                f"actual count={None if notes is None else len(notes)}"
            )
        for note, expected_link, expected_text in notes:
            if note is None:
                raise RuntimeError(f"{sheet_name}: missing sheet note {expected_link!r}")
            note = _early_bound(note, "INote")
            raw_annotation = note.GetAnnotation()
            if raw_annotation is None:
                raise RuntimeError(f"{sheet_name}: sheet note has no annotation: {expected_link!r}")
            annotation = _early_bound(raw_annotation, "IAnnotation")
            bounds = _box(note.GetExtent(), label=expected_link, kind="note")
            owner = int(annotation.OwnerType)
            link = str(note.PropertyLinkedText)
            text = str(note.GetText()).replace("\r\n", "\n")
            if (
                owner != 1 or not _inside(bounds, border)
                or link != expected_link
                or text != expected_text.replace("\r\n", "\n")
            ):
                raise RuntimeError(
                    f"{sheet_name}: sheet note changed or leaves the usable sheet: "
                    f"expected owner=1, link={expected_link!r}, text={expected_text!r}; "
                    f"actual owner={owner}, link={link!r}, text={text!r}, "
                    f"bounds={bounds}, border={border}"
                )
        views = {view_name(adapter, raw): _early_bound(raw, "IView") for raw in iter_views(adapter)}
        for name in names:
            if name not in views:
                raise RuntimeError(f"{sheet_name}: supplier dimension view disappeared")
            view = views[name]
            if sheet_name == SHEET_NAMES[1]:
                bounds = _supplier_stock_bounds(adapter, view, source_model, stock_capture)
                if not _inside(bounds, cell):
                    raise RuntimeError(f"counter anchor {sheet_name}: native source ink leaves its cell: {bounds!r}")
                assert_supplier_annotations_fit(adapter, view, cell, label=f"counter anchor {sheet_name}")
            else:
                view.UpdateViewDisplayGeometry()
                assert_supplier_view_fits(adapter, view, cell, label=f"counter anchor {sheet_name}")


def _verify_source_state(adapter, source_model, finished_configuration):
    actual = active_configuration_name(adapter, source_model)
    if actual != finished_configuration:
        raise RuntimeError(
            f"supplier drawing source active configuration expected={finished_configuration!r}; actual={actual!r}"
        )
    part = _early_bound(source_model, "IPartDoc")
    for name in REFERENCE_SKETCHES:
        feature = part.FeatureByName(name)
        state = None if feature is None else int(_early_bound(feature, "IFeature").Visible)
        if state != 1:
            raise RuntimeError(f"{name}: saved-hidden source visibility expected=1; actual={state!r}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open modified anchor", await adapter.open_model(str(SOURCE)))
    source_model = _early_bound(adapter.currentModel, "IModelDoc2")
    finished_configuration = active_configuration_name(adapter, source_model)
    if not finished_configuration or finished_configuration == SUPPLIER_STOCK_CONFIGURATION:
        raise RuntimeError("source counter anchor is not saved in its finished configuration")
    stock_capture = _capture_supplier_stock(adapter, source_model, finished_configuration)
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
    required_properties = read_required_properties(
        adapter.currentModel, required, required=required,
    )
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
    drawing.ActivateView("")  # False is documented for sheet context.
    if drawing.GetEditSheet() is not True or drawing.ActiveDrawingView is not None:
        raise RuntimeError("cannot enter finished counter anchor sheet context for notes")
    finished_notes = []
    for name, x, y, height in (
        ("Supplier", 0.016, 0.060, 0.003),
        ("Supplier SKUs", 0.080, 0.060, 0.003),
        ("Stock Name", 0.016, 0.049, 0.003),
        ("Isometric View Note", 0.275, 0.163, None),
        ("Manufacturing Notes", 0.016, NOTES_Y, 0.003),
    ):
        note = add_property_linked_note(adapter, name, x, y, char_height=height)
        if note is None:
            raise RuntimeError(f"cannot create finished counter anchor note {name!r}")
        finished_notes.append((
            _early_bound(note, "INote"), property_link(name), required_properties[name],
        ))
    # Re-assert after annotating: a real mode change regenerates the edge set.
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)
    if drawing.ActivateSheet(SHEET_NAMES[1]) is not True:
        raise RuntimeError("cannot activate counter anchor supplier stock sheet")
    stock, stock_refs, stock_notes = _supplier_stock_diagram(adapter, source_model, stock_capture)
    set_hidden_lines_removed(adapter, stock)
    view_contracts = {
        SHEET_NAMES[0]: ((view_name(adapter, front), view_name(adapter, iso)), finished_configuration),
        SHEET_NAMES[1]: ((view_name(adapter, stock),), SUPPLIER_STOCK_CONFIGURATION),
    }
    refs_by_sheet = {SHEET_NAMES[0]: refs, SHEET_NAMES[1]: stock_refs}
    notes_by_sheet = {SHEET_NAMES[0]: finished_notes, SHEET_NAMES[1]: stock_notes}
    settled_reference_identities = None
    saved_supplier_references = None

    def verify_settled_supplier_references():
        nonlocal settled_reference_identities
        settled_reference_identities = _verify_supplier_references(
            adapter, refs_by_sheet, view_contracts,
        )

    def verify_after_native_save(event):
        nonlocal saved_supplier_references
        if event not in ("after_drawing_save", "after_pdf_save", "before_drawing_close"):
            return
        entry_sheet = entry_title = None
        primary_error = None
        try:
            if event == "before_drawing_close":
                entry_model = _early_bound(adapter.currentModel, "IModelDoc2")
                entry_drawing = _early_bound(entry_model, "IDrawingDoc")
                sheet = _early_bound(entry_drawing.GetCurrentSheet(), "ISheet")
                name = sheet.GetName()
                if not isinstance(name, str) or not name:
                    raise RuntimeError("cannot read the native drawing close-entry sheet")
                entry_sheet = name
                entry_title = entry_model.GetTitle()
                if not isinstance(entry_title, str) or not entry_title:
                    raise RuntimeError("cannot read the opaque native drawing close-entry title")
            # Callbacks also observe failed operations; they never assert save success.
            observed = _capture_saved_supplier_references(
                adapter, refs_by_sheet, view_contracts, settled_reference_identities,
            )
            if event == "after_drawing_save":
                _verify_supplier_references(adapter, observed, view_contracts)
                saved_supplier_references = observed
            else:
                if saved_supplier_references is None or observed != saved_supplier_references:
                    raise RuntimeError("supplier exact saved dimension keys changed after native drawing save")
                _verify_supplier_references(adapter, saved_supplier_references, view_contracts)
            if event != "before_drawing_close" and drawing.ActivateSheet(SHEET_NAMES[0]) is not True:
                raise RuntimeError("cannot restore finished counter anchor sheet after saved-eye inspection")
        except BaseException as exc:
            primary_error = exc
            raise
        finally:
            if entry_sheet is not None:
                try:
                    # Common has already captured its opaque CloseDoc title.
                    # Restore the exact entry context, not a chosen UI sheet.
                    if entry_drawing.ActivateSheet(entry_sheet) is not True:
                        raise RuntimeError("cannot restore the native drawing close-entry sheet")
                    restored = _early_bound(entry_drawing.GetCurrentSheet(), "ISheet")
                    if restored.GetName() != entry_sheet:
                        raise RuntimeError("native drawing close-entry sheet restoration changed sheets")
                    if entry_model.GetTitle() != entry_title:
                        raise RuntimeError("opaque native drawing title changed during the close checkpoint")
                except BaseException as restoration_error:
                    if primary_error is None:
                        raise
                    primary_error.add_note(
                        "before_drawing_close entry-context restoration also failed: "
                        f"{type(restoration_error).__name__}: {restoration_error}"
                    )

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
            lambda: _verify_supplier_layout(
                adapter, view_contracts, notes_by_sheet, source_model, stock_capture,
            ),
            verify_settled_supplier_references,
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
