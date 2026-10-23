"""Create the manufacturing drawing for the modified McMaster 9489T111 anchor.

The anchor is purchased by SKU but is NOT installed as supplied: the captive
hex nut is discarded (the MHA-CH-14 round jam nut locks it) and the shank is cut to
cross the summing-lever plate and carry that nut, so the sheet carries the
same two cutting controls as the counter anchor (``draw_boss_hook``) -- the
finished overall length to the eye crown and the restored 45 deg deburr at the
new end. The length band is the title block's; ``ch_vn_spring_hook_spec`` shows
the shortest in-band part still keeps two full threads past the nut.

Run with SolidWorks open::

    uv run python cad\\scripts\\draw_ch_vn_spring_hook.py ch-vn-spring-hook
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from pathlib import Path
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
from _drawing_edges import visible_view_entities
from _drawing_hidden_sketches import (
    _show_hidden_owners, curate_view_dimensions as curate_stock_dimensions,
)
from _drawing_notes import add_property_linked_note, property_link
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
from stock_anchor_geom import ANCHOR_9489T111 as _SUPPLIER_ANCHOR
from ch_vn_spring_hook_spec import (
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
    SUPPLIER_EYE_MM,
    SUPPLIER_REFERENCE_PRECISION,
    SUPPLIER_THREAD,
    SUPPLIER_THREAD_MAJOR_MM,
    SUPPLIER_THREAD_DIMENSIONS,
    SUPPLIER_THREAD_FEATURE,
    SUPPLIER_STOCK_AXIS_MM,
    SUPPLIER_STOCK_CONFIGURATION,
    SUPPLIER_STOCK_DIMENSIONS,
    SUPPLIER_STOCK_FEATURE,
    SUPPLIER_STOCK_MM,
)

SPEC = DRAWINGS_BY_NAME["ch_vn_spring_hook"]
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(**SPEC.outputs)
# diag_build_9489T111 names the merged circular-profile eye sweep "Wire".
_SUPPLIER_EYE_FEATURE = "Wire"
# The finished part is 31.3 x 12.7 mm since its shank carries the MHA-CH-14
# jam nut under the coefficient plate: 5:1 keeps the front view inside the
# counter anchor's 4:1 sheet band, raised so the cut end's deburr dimensions clear
# the notes.  The deburr is dimensioned on the front view itself, as on the
# counter anchor: machinist review r7 found a 20:1 detail for a plain end
# chamfer added nothing a machinist needs.
SHEET_SCALE = (5.0, 1.0)
ISO_SCALE = (3.0, 1.0)
# The actual 5:1 stock outline is 171.903 mm tall in the unchanged 163.7 mm
# cell, so translation cannot fit it. Main approved catalogue scale 4:1 for
# this stock primary only; its actual native bounds and readability still
# require qualification, never a proportionally reduced 5:1 outline.
STOCK_SCALE = (4.0, 1.0)
SHEET_NAMES = ("FINISHED", "SUPPLIER-STOCK")
STOCK_CENTER = (0.150, 0.1755)
# a269's settled GetOutline exceeded the unchanged FINISHED cell top by
# 4.3690642237152 mm, with 36.33093577628477 mm of bottom slack. Lower only
# this view 5 mm: the smallest whole-mm translation containing that recorded
# native box. GetOutline does not guarantee a tight physical-edge envelope;
# the translated placement still needs native qualification. Text anchors stay put.
FRONT_CENTER = (0.100, 0.18125)
# a06's FINISHED isometric GetOutline exceeds the unchanged cell top by
# 0.6277812843747 mm, with 93.57221871562523 mm of bottom slack. Lower only
# that pictorial 1 mm, the smallest whole-mm shift: top/bottom clearance becomes
# 0.3722187156253/92.57221871562523 mm. Its padded outline is not physical ink;
# the retained v44 PDF's opaque pictorial-to-caption gap predicts 7.381 mm
# after this shift, not native/printed acceptance of the new output.
FINISHED_ISO_CENTER = (0.310, 0.212)
# c12's actual STOCK isometric exceeded its unchanged cell top by
# 9.6277812843747 mm. Lower this pictorial and only its caption 10 mm:
# the minimum whole-mm translation leaves 0.3722187156253 mm top clearance.
# This preserves their relative composition, not a new native/printed ink proof.
STOCK_ISO_CENTER = (0.310, 0.203)
STOCK_ISO_CAPTION = (0.275, 0.153)
# The deburr's value and callout hang right of the shank, clear of their own
# extension lines (review r8: centred under the 2.3 mm leg they were struck)
# and above the notes.
FRONT_KEEP = {
    "FinishedOverall": (0.042, 0.18625),
    "ChamferWidth": (0.168, 0.100),
    "ChamferAngle": (0.124, 0.117),
}
# The deburr band is tighter than the title block on both sides (review r8
# read it as a plain lead-in): its minimum leg brings the cut end under the
# #6-32 tap drill so the cut thread starts in the lever's tap, and its
# maximum, at the steepest angle, is charged to the full threads the shank
# keeps past the jam nut.  The callout names both mates.
CHAMFER_CALLOUT = {
    "ChamferWidth": (
        "MIN: CUT END STARTS IN MHA-SM-03 TAP\nMAX: KEEPS FULL THREAD PAST MHA-CH-14"
    )
}
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


def _native_equality(app, left, right):
    """Refuse unknown COM equality states instead of coercing them to true."""
    if left is None or right is None:
        raise RuntimeError("supplier reference native identity is missing")
    value = app.IsSame(left, right)
    if type(value) is not int or value not in (0, 1):
        raise RuntimeError(f"supplier reference has unknown native IsSame state {value!r}")
    return value


def _native_path(value, *, label):
    if not isinstance(value, str) or not value or not Path(value).is_absolute():
        raise RuntimeError(f"{label}: native document path is missing or not absolute")
    return value.replace("\\", "/").casefold()


@dataclass(frozen=True)
class _SupplierViewIdentity:
    name: str
    configuration: str
    source_path: str
    view: Any
    source: Any


@dataclass(frozen=True)
class _SupplierReferenceSnapshot:
    sheet: str
    key: str
    contract: tuple[tuple[str, Any], ...]
    annotation: Any
    owner: Any
    drawing: Any
    drawing_path: str
    views: tuple[_SupplierViewIdentity, ...]


def _supplier_views(adapter, names, configuration):
    views = {}
    for raw in iter_views(adapter):
        view = _early_bound(raw, "IView")
        name = view_name(adapter, view)
        if not isinstance(name, str) or not name or name in views:
            raise RuntimeError("supplier view names are missing or duplicate")
        views[name] = view
    identities = []
    for name in names:
        if name not in views:
            raise RuntimeError(f"{name}: supplier view disappeared")
        view = views[name]
        if view.ReferencedConfiguration != configuration:
            raise RuntimeError(f"{name}: supplier view lost its source configuration")
        raw_source = view.ReferencedDocument
        if raw_source is None:
            raise RuntimeError(f"{name}: supplier view lost its source document")
        source = _early_bound(raw_source, "IModelDoc2")
        path = _native_path(source.GetPathName(), label=name)
        if path != SOURCE.resolve().as_posix().casefold():
            raise RuntimeError(f"{name}: supplier view source path changed")
        identities.append(_SupplierViewIdentity(name, configuration, path, view, source))
    return tuple(identities)


def _supplier_displays(view):
    displays = {}
    raw = view.GetFirstDisplayDimension6()
    while raw is not None:
        display = _early_bound(raw, "IDisplayDimension")
        native = _early_bound(display.GetDimension2(0), "IDimension")
        key = native.FullName
        if not isinstance(key, str) or not key or key in displays:
            raise RuntimeError(f"duplicate or missing native supplier dimension {key!r}")
        displays[key] = display
        raw = display.GetNext5()
    return displays


def _supplier_annotation(app, display, view):
    raw_annotation = display.GetAnnotation()
    if raw_annotation is None:
        raise RuntimeError("supplier dimension has no native annotation")
    annotation = _early_bound(raw_annotation, "IAnnotation")
    kind, owner_type = annotation.GetType(), annotation.OwnerType
    raw_owner = annotation.Owner
    if type(kind) is not int or kind != 4 or type(owner_type) is not int or owner_type != 0 or raw_owner is None:
        raise RuntimeError("supplier dimension must be a typed view-owned display dimension")
    owner = _early_bound(raw_owner, "IView")
    raw_specific = annotation.GetSpecificAnnotation()
    if raw_specific is None:
        raise RuntimeError("supplier annotation has no typed display dimension")
    specific = _early_bound(raw_specific, "IDisplayDimension")
    if (
        _native_equality(app, owner, view) != 1
        or _native_equality(app, specific, display) != 1
    ):
        raise RuntimeError("supplier annotation lost its exact native display or view owner")
    raw_source, raw_owner_source = view.ReferencedDocument, owner.ReferencedDocument
    if (
        owner.ReferencedConfiguration != view.ReferencedConfiguration
        or raw_source is None or raw_owner_source is None
    ):
        raise RuntimeError("supplier annotation owner source configuration changed")
    owner_source = _early_bound(raw_owner_source, "IModelDoc2")
    if (
        _native_path(owner_source.GetPathName(), label="supplier owner")
        != SOURCE.resolve().as_posix().casefold()
        or _native_equality(app, owner_source, _early_bound(raw_source, "IModelDoc2")) != 1
    ):
        raise RuntimeError("supplier annotation owner source binding changed")
    return annotation, owner


def _supplier_eye_circle(
    adapter: Any, view: Any, raw: Any,
) -> tuple[float, ...] | None:
    """Read an exact model-XY circle on the authoritative source eye torus."""
    if raw is None:
        return None
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
        and all(abs(value) <= 1e-8 for value in circle[:3])
        and abs(abs(circle[5]) - 1.0) <= 1e-8
    ):
        return None
    native_view = silhouette.GetView()
    app = _early_bound(adapter.swApp, "ISldWorks")
    if native_view is None or _native_equality(app, _early_bound(native_view, "IView"), view) != 1:
        return None
    raw_document = view.ReferencedDocument
    if raw_document is None:
        return None
    document = _early_bound(raw_document, "IModelDoc2")
    native_path = str(document.GetPathName())
    if native_path.replace("\\", "/").casefold() != SOURCE.resolve().as_posix().casefold():
        return None
    expected_feature = _early_bound(raw_document, "IPartDoc").FeatureByName(_SUPPLIER_EYE_FEATURE)
    raw_face = silhouette.GetFace()
    if expected_feature is None or raw_face is None:
        return None
    raw_extension = document.Extension
    if raw_extension is None:
        return None
    # A drawing face's feature is a different native object from its source
    # owner. Map every face into this source part before comparing identity or
    # reading the torus; neither names nor drawing-context equality prove it.
    extension = _early_bound(raw_extension, "IModelDocExtension")
    raw_source_face = extension.GetCorrespondingEntity2(_early_bound(raw_face, "IFace2"))
    if raw_source_face is None:
        return None
    face = _early_bound(raw_source_face, "IFace2")
    owner = face.GetFeature()
    if owner is None or _native_equality(app, owner, expected_feature) != 1:
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
        and all(abs(value) <= 1e-8 for value in torus[:3])
        and abs(abs(torus[5]) - 1.0) <= 1e-8
        and abs(torus[6] * 2000.0 - 2.0 * _SUPPLIER_ANCHOR.eye_mean_radius_mm) < 1e-5
        and abs(torus[7] * 2000.0 - _SUPPLIER_ANCHOR.wire_dia_mm) < 1e-5
    ):
        return None
    return circle


def _supplier_references(adapter: Any, front: Any) -> list[tuple[str, dict[str, Any]]]:
    """Physical unchanged eye sizes plus an associative nominal-major carrier."""
    eye = {}
    refs = []
    visible = visible_view_entities(front, 4, label="spring anchor supplier contours")
    for raw in visible:
        circle = _supplier_eye_circle(adapter, front, raw)
        if circle is None:
            continue
        for name, diameter in SUPPLIER_EYE_MM.items():
            if abs(circle[6] * 2000.0 - diameter) < 1e-5:
                eye.setdefault(name, raw)
    for name, text_xy in (
        ("EyeOD", (0.169, 0.255)),
        ("EyeID", (0.165, 0.228)),
    ):
        if name not in eye:
            raise RuntimeError(f"{name}: unchanged spring eye has no circular silhouette")
        try:
            _select_view_entity(
                adapter, front, "SILHOUETTE", None, label=name, entity=eye[name]
            )
            display = adapter.currentModel.AddDiameterDimension2(*text_xy, 0.0)
        finally:
            adapter.currentModel.ClearSelection2(True)
        if display is None:
            raise RuntimeError(f"{name}: cannot dimension the spring eye silhouette")
        contract = dict(
            label=name, expected_mm=SUPPLIER_EYE_MM[name], units="in",
            precision=SUPPLIER_REFERENCE_PRECISION[name], presentation="diameter",
        )
        display = supplier_reference_dimension(adapter, display, **contract)
        refs.append((str(_early_bound(display.GetDimension2(0), "IDimension").FullName), contract))
    annotations = curate_stock_dimensions(
        adapter, front, keep={"SupplierThreadMajor": (0.166, 0.175)},
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


def _supplier_stock_sheet(adapter):
    """Dimension the actual restored original bolt body, not its finished cut."""
    stock = _early_bound(
        place_view(adapter, str(SOURCE), "*Front", *STOCK_CENTER, scale=STOCK_SCALE),
        "IView",
    )
    iso = _early_bound(
        place_view(adapter, str(SOURCE), "*Isometric", *STOCK_ISO_CENTER, scale=ISO_SCALE),
        "IView",
    )
    for view in (stock, iso):
        view.ReferencedConfiguration = SUPPLIER_STOCK_CONFIGURATION
        if str(view.ReferencedConfiguration) != SUPPLIER_STOCK_CONFIGURATION:
            raise RuntimeError("as-supplied spring anchor view references the finished cut")
        set_hidden_lines_removed(adapter, view)
    shown = _show_hidden_owners(
        adapter, stock, (SUPPLIER_STOCK_FEATURE,),
        view_label="spring anchor original source axis before centering",
    )
    if set(shown) != {SUPPLIER_STOCK_FEATURE}:
        raise RuntimeError("spring anchor original source axis is not saved hidden")
    if adapter.currentModel.EditRebuild3() is not True:
        raise RuntimeError("cannot rebuild the as-supplied spring anchor views")
    stock.UpdateViewDisplayGeometry()
    midpoint = (
        0.0,
        (SUPPLIER_STOCK_AXIS_MM[0][1] + SUPPLIER_STOCK_AXIS_MM[-1][1]) / 2000.0,
        0.0,
    )
    projected = model_points_in_view(
        adapter, stock, [midpoint], label="original stock bolt centre"
    )[0]
    before = tuple(float(value) for value in stock.Position)
    stock.Position = double_array([
        before[0] + STOCK_CENTER[0] - projected[0],
        before[1] + STOCK_CENTER[1] - projected[1],
    ])
    if adapter.currentModel.EditRebuild3() is not True:
        raise RuntimeError("cannot centre the full original stock bolt")
    keep = {
        "SupplierStockShank": (0.105, 0.150),
        "SupplierStockThread": (0.210, 0.140),
        "SupplierStockOverall": (0.065, STOCK_CENTER[1]),
    }
    annotations = curate_stock_dimensions(
        adapter, stock, keep=keep, view_label="as-supplied original bolt dimensions",
        dimensions_by_feature=SUPPLIER_STOCK_DIMENSIONS,
    )
    refs = []
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        contract = dict(
            label=name, expected_mm=SUPPLIER_STOCK_MM[name], units="in",
            precision=SUPPLIER_REFERENCE_PRECISION[name],
            callout={
                "SupplierStockShank": "AS-SUPPLIED SHANK",
                "SupplierStockThread": "AS-SUPPLIED THREAD LENGTH",
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
        raise RuntimeError("cannot enter original stock sheet context for labels")
    sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
    properties = tuple(sheet.GetProperties2())
    region = sheet_drawable_region(
        adapter, sheet, width=float(properties[5]), height=float(properties[6])
    )
    notes = []
    for text, x, y in (
        (
            "AS-SUPPLIED EYEBOLT BODY — SUPPLIER REFERENCE",
            region.xmin + 0.0033, region.ymax - 0.004,
        ),
        (
            "SUPPLIED HEX NUT OMITTED FROM THIS BODY VIEW\n"
            "STOCK REFERENCES ONLY — FINISHED CUTTING CONTROLS: SHEET 1",
            0.016, 0.089,
        ),
        (f"ISOMETRIC VIEW SCALE {ISO_SCALE[0]:g}:{ISO_SCALE[1]:g}", *STOCK_ISO_CAPTION),
    ):
        note = add_note(adapter, text, x, y)
        if note is None:
            raise RuntimeError("cannot label the original supplier stock body")
        notes.append((_early_bound(note, "INote"), text, text))
    for view in (stock, iso):
        set_hidden_lines_removed(adapter, view)
    return stock, iso, refs, notes


def _verify_supplier_references(adapter, refs_by_sheet, view_contracts):
    """Strictly prove current exact keys, then freeze only native identities."""
    if sum(len(refs) for refs in refs_by_sheet.values()) != 6 or set(refs_by_sheet) != set(view_contracts):
        raise RuntimeError("spring anchor must retain all six supplier dimensions")
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    drawing_path = model.GetPathName()
    document_type = model.GetType()
    if not isinstance(drawing_path, str) or type(document_type) is not int or document_type != 3:
        raise RuntimeError("supplier references require the current native drawing")
    app = _early_bound(adapter.swApp, "ISldWorks")
    drawing = _early_bound(model, "IDrawingDoc")
    verified = []
    for sheet_name, refs in refs_by_sheet.items():
        if drawing.ActivateSheet(sheet_name) is not True:
            raise RuntimeError(f"cannot inspect settled references on {sheet_name}")
        names, configuration = view_contracts[sheet_name]
        identities = _supplier_views(adapter, names, configuration)
        view = identities[0].view
        displays = _supplier_displays(view)
        expected_count = len(refs) + (len(FRONT_KEEP) if sheet_name == SHEET_NAMES[0] else 0)
        if len(displays) != expected_count or len({key for key, _contract in refs}) != len(refs):
            raise RuntimeError(f"{sheet_name}: settled native dimension coverage changed")
        for key, contract in refs:
            if key not in displays:
                raise RuntimeError(f"{contract['label']}: settled supplier dimension disappeared")
            display = displays[key]
            annotation, owner = _supplier_annotation(app, display, view)
            assert_supplier_reference_dimension(adapter, display, **contract)
            native = _early_bound(display.GetDimension2(0), "IDimension")
            if int(_early_bound(native.Tolerance, "IDimensionTolerance").Type) != 0:
                raise RuntimeError(f"{contract['label']}: supplier reference acquired a tolerance band")
            if contract["label"] not in SUPPLIER_EYE_MM:
                feature = (
                    SUPPLIER_THREAD_FEATURE
                    if contract["label"] == "SupplierThreadMajor" else SUPPLIER_STOCK_FEATURE
                )
                if str(native.FullName).split("@")[:2] != [contract["label"], feature]:
                    raise RuntimeError(f"{contract['label']}: nominal model attachment changed")
                if contract["label"] in ("SupplierStockShank", "SupplierStockOverall") and int(native.DrivenState) != 1:
                    raise RuntimeError(f"{contract['label']}: source station span is no longer driven")
            else:
                # Never retain the silhouette or mapped face beyond this read.
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
                        f"{contract['label']}: supplier eye must retain one live physical "
                        f"silhouette; entities={len(entities)}, kinds={kinds}"
                    )
                circle = _supplier_eye_circle(adapter, view, entities[0])
                diameter = SUPPLIER_EYE_MM[contract["label"]]
                if circle is None or abs(circle[6] * 2000.0 - diameter) >= 1e-5:
                    raise RuntimeError(
                        f"{contract['label']}: supplier eye lost its exact physical source contour; "
                        f"circle={circle!r}, expected_diameter_mm={diameter}"
                    )
            verified.append((
                sheet_name, key, tuple(contract.items()), annotation, owner,
                model, drawing_path, identities,
            ))
    # Publish no frozen snapshot until every sheet's strict geometry passed.
    snapshots = tuple(_SupplierReferenceSnapshot(*identity) for identity in verified)
    for index, original in enumerate(snapshots):
        for other in snapshots[:index]:
            if _native_equality(app, original.annotation, other.annotation) != 0:
                raise RuntimeError("supplier original annotations must be provably distinct")
    return snapshots


def _capture_saved_supplier_references(adapter, refs_by_sheet, view_contracts, prior):
    """Capture actual saved keys ONLY through the original native annotations.

    This is a still-open identity observation, not a save-success receipt or
    cold persistence proof. Metadata failures refuse; names never supply aliases.
    """
    expected = tuple(
        (sheet, key, tuple(contract.items()))
        for sheet, refs in refs_by_sheet.items() for key, contract in refs
    )
    if (
        not prior or len(prior) != 6
        or tuple((item.sheet, item.key, item.contract) for item in prior) != expected
        or set(refs_by_sheet) != set(view_contracts)
    ):
        raise RuntimeError("saved supplier capture requires the complete verified original references")
    if adapter.currentModel is None:
        raise RuntimeError("saved supplier current native drawing is missing")
    app = _early_bound(adapter.swApp, "ISldWorks")
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    drawing = _early_bound(model, "IDrawingDoc")
    document_type = model.GetType()
    if (
        type(document_type) is not int or document_type != 3
        or _native_path(model.GetPathName(), label="saved supplier drawing")
        != OUTPUTS.slddrw.resolve().as_posix().casefold()
    ):
        raise RuntimeError("saved supplier drawing is not the actual native output path")
    for raw in (app.ActiveDoc, app.GetOpenDocumentByName(str(OUTPUTS.slddrw.resolve()))):
        if raw is None or _native_equality(app, _early_bound(raw, "IModelDoc2"), model) != 1:
            raise RuntimeError("saved supplier output is not the current native drawing")
    captured = {}
    captured_keys = set()
    for sheet, refs in refs_by_sheet.items():
        if drawing.ActivateSheet(sheet) is not True:
            raise RuntimeError(f"{sheet}: cannot inspect saved supplier identities")
        names, configuration = view_contracts[sheet]
        current_views = _supplier_views(adapter, names, configuration)
        view = current_views[0].view
        raw_annotations = view.GetAnnotations()
        if not isinstance(raw_annotations, (tuple, list)):
            raise RuntimeError(f"{sheet}: saved supplier annotation census is unavailable")
        candidates = tuple(_early_bound(raw, "IAnnotation") for raw in raw_annotations)
        saved_refs = []
        for original in (item for item in prior if item.sheet == sheet):
            if _native_equality(app, model, original.drawing) != 1 or len(current_views) != len(original.views):
                raise RuntimeError(f"{sheet}: original native drawing or view census changed")
            for actual, old in zip(current_views, original.views):
                if (
                    (actual.name, actual.configuration, actual.source_path)
                    != (old.name, old.configuration, old.source_path)
                    or _native_equality(app, actual.view, old.view) != 1
                    or _native_equality(app, actual.source, old.source) != 1
                ):
                    raise RuntimeError(f"{sheet}: original supplier view/source binding changed")
            matches = [
                annotation for annotation in candidates
                if _native_equality(app, annotation, original.annotation) == 1
            ]
            if len(matches) != 1:
                raise RuntimeError(f"{dict(original.contract)['label']}: original annotation census must be exactly one")
            annotation = matches[0]
            raw_display = annotation.GetSpecificAnnotation()
            if raw_display is None:
                raise RuntimeError(f"{sheet}: original supplier display dimension is missing")
            display = _early_bound(raw_display, "IDisplayDimension")
            returned, owner = _supplier_annotation(app, display, view)
            if _native_equality(app, returned, annotation) != 1:
                raise RuntimeError(f"{sheet}: original supplier display annotation changed")
            raw_native = display.GetDimension2(0)
            if raw_native is None:
                raise RuntimeError(f"{sheet}: original supplier native dimension is missing")
            key = _early_bound(raw_native, "IDimension").FullName
            if not isinstance(key, str) or not key or key in captured_keys:
                raise RuntimeError(f"{sheet}: saved supplier native key is missing or duplicate")
            original_annotation = _early_bound(original.annotation, "IAnnotation")
            original_owner_type = original_annotation.OwnerType
            original_owner = original_annotation.Owner
            if (
                type(original_owner_type) is not int or original_owner_type != 0
                or original_owner is None
                or _native_equality(app, _early_bound(original_owner, "IView"), original.owner) != 1
                or _native_equality(app, owner, original.owner) != 1
                or _native_equality(app, original.owner, view) != 1
            ):
                raise RuntimeError(f"{sheet}: original supplier annotation owner changed")
            captured_keys.add(key)
            saved_refs.append((key, dict(original.contract)))
        if len(saved_refs) != len(refs) or len({key for key, _contract in saved_refs}) != len(refs):
            raise RuntimeError(f"{sheet}: saved supplier annotation coverage changed")
        captured[sheet] = saved_refs
    return captured


def _verify_supplier_layout(adapter, view_contracts, notes_by_sheet):
    """Inspect every view's settled native ink and sheet-owned source labels."""
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
        expected_count = 5 if sheet_name == SHEET_NAMES[0] else 3
        if notes is None or len(notes) != expected_count:
            raise RuntimeError(
                f"{sheet_name}: expected {expected_count} sheet notes; "
                f"actual count={None if notes is None else len(notes)}"
            )
        for note, expected_link, expected_text in notes:
            if note is None:
                raise RuntimeError(f"{sheet_name}: source label is missing: {expected_link}")
            raw_annotation = note.GetAnnotation()
            if raw_annotation is None:
                raise RuntimeError(f"{sheet_name}: source label has no annotation: {expected_link}")
            annotation = _early_bound(raw_annotation, "IAnnotation")
            bounds = _box(note.GetExtent(), label=expected_link, kind="note")
            owner = int(annotation.OwnerType)
            linked = str(note.PropertyLinkedText)
            resolved = str(note.GetText()).replace("\r\n", "\n")
            expected_text = expected_text.replace("\r\n", "\n")
            if (
                owner != 1 or not _inside(bounds, border)
                or linked != expected_link
                or resolved != expected_text
            ):
                raise RuntimeError(
                    f"{sheet_name}: source label changed or leaves the usable sheet: "
                    f"expected owner=1, link={expected_link!r}, text={expected_text!r}; "
                    f"actual owner={owner}, link={linked!r}, text={resolved!r}, "
                    f"bounds={bounds}, border={border}"
                )
        views = {view_name(adapter, raw): _early_bound(raw, "IView") for raw in iter_views(adapter)}
        for name in names:
            if name not in views:
                raise RuntimeError(f"{sheet_name}: supplier dimension view disappeared")
            view = views[name]
            view.UpdateViewDisplayGeometry()
            assert_supplier_view_fits(
                adapter, view, cell,
                label=(
                    f"spring anchor {sheet_name} view={name!r} "
                    f"configuration={str(view.ReferencedConfiguration)!r} cell={cell!r}"
                ),
            )


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
        raise RuntimeError("source spring anchor is not saved in its finished configuration")
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
    source_properties = read_required_properties(adapter.currentModel, required, required=required)
    draw, _sheet = new_project_drawing(
        adapter, property_view=SPEC.artifact_stem, scale=SHEET_SCALE, layout=SPEC.layout
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="spring anchor stock package")
    drawing = _early_bound(draw, "IDrawingDoc")
    if drawing.ActivateSheet(SHEET_NAMES[0]) is not True:
        raise RuntimeError("cannot activate finished spring anchor sheet")
    stamp_drawing_summary(
        adapter,
        draw,
        {
            0: "Channel Spring Anchor — Modified Stock Drawing",
            1: "Manufacturing controls for modified purchased stock",
            2: "Harmonic Analyzer Project",
            3: "MHA-CH-VN-51; McMaster-Carr 9489T111",
            4: "Native dimension-driven trim and end deburr",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *FINISHED_ISO_CENTER, scale=ISO_SCALE)
    for view in (front, iso):
        view = _early_bound(view, "IView")
        view.ReferencedConfiguration = finished_configuration
    # Hidden lines removed: the helix's back side, dashed, told the machinist
    # nothing about a purchased thread and cluttered the cut end (review r7).
    set_hidden_lines_removed(adapter, front)
    annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="finished overall and cut end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_precision(adapter, annotations, DIMENSION_PRECISION)
    set_dimension_callouts(adapter, annotations, CHAMFER_CALLOUT)
    _verify_controls(adapter, annotations)
    refs = _supplier_references(adapter, front)
    drawing.ActivateView("")  # False is documented for sheet context.
    if drawing.GetEditSheet() is not True or drawing.ActiveDrawingView is not None:
        raise RuntimeError("cannot enter finished spring anchor sheet context for labels")
    finished_notes = []
    for name, x, y, char_height in (
        ("Supplier", 0.016, 0.060, 0.003),
        ("Supplier SKUs", 0.080, 0.060, 0.003),
        ("Stock Name", 0.016, 0.049, 0.003),
        ("Isometric View Note", 0.275, 0.163, None),
        ("Manufacturing Notes", 0.016, 0.083, 0.003),
    ):
        note = add_property_linked_note(adapter, name, x, y, char_height=char_height)
        if note is None:
            raise RuntimeError(f"cannot create finished spring anchor source label: {name}")
        finished_notes.append(
            (_early_bound(note, "INote"), property_link(name), source_properties[name])
        )
    # Re-assert after annotating: a real mode change regenerates the edge set.
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)
    if drawing.ActivateSheet(SHEET_NAMES[1]) is not True:
        raise RuntimeError("cannot activate spring anchor supplier stock sheet")
    stock, stock_iso, stock_refs, stock_notes = _supplier_stock_sheet(adapter)
    view_contracts = {
        SHEET_NAMES[0]: ((view_name(adapter, front), view_name(adapter, iso)), finished_configuration),
        SHEET_NAMES[1]: ((view_name(adapter, stock), view_name(adapter, stock_iso)), SUPPLIER_STOCK_CONFIGURATION),
    }
    refs_by_sheet = {SHEET_NAMES[0]: refs, SHEET_NAMES[1]: stock_refs}
    notes_by_sheet = {SHEET_NAMES[0]: finished_notes, SHEET_NAMES[1]: stock_notes}
    pre_save_identities = None
    saved_refs_by_sheet = None

    def verify_settled_references():
        nonlocal pre_save_identities
        _verify_source_state(adapter, source_model, finished_configuration)
        pre_save_identities = _verify_supplier_references(adapter, refs_by_sheet, view_contracts)

    def verify_after_native_save(event):
        nonlocal saved_refs_by_sheet
        if event not in ("after_drawing_save", "after_pdf_save", "before_drawing_close"):
            return
        # Checkpoints also run on failed operations: this neither asserts save
        # success nor replaces the shared finalizer's original save exception.
        current_refs = _capture_saved_supplier_references(
            adapter, refs_by_sheet, view_contracts, pre_save_identities,
        )
        if event == "after_drawing_save":
            if saved_refs_by_sheet is not None:
                raise RuntimeError("supplier native-save identities were already captured")
        elif saved_refs_by_sheet is None or current_refs != saved_refs_by_sheet:
            raise RuntimeError("saved supplier exact native keys changed after the drawing save")
        _verify_supplier_references(
            adapter,
            current_refs if event == "after_drawing_save" else saved_refs_by_sheet,
            view_contracts,
        )
        if event == "after_drawing_save":
            saved_refs_by_sheet = current_refs
        if drawing.ActivateSheet(SHEET_NAMES[0]) is not True:
            raise RuntimeError("cannot restore finished spring anchor sheet after saved-eye inspection")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Channel Spring Anchor — Modified Stock Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        sheet_scales={SHEET_NAMES[0]: SHEET_SCALE, SHEET_NAMES[1]: STOCK_SCALE},
        settled_checks=(
            lambda: _verify_controls(adapter, annotations),
            # The existing layout check refreshes every view before the final
            # attachment readback; the shared verifier stays geometry-read-only.
            lambda: _verify_supplier_layout(adapter, view_contracts, notes_by_sheet),
            verify_settled_references,
        ),
        checkpoint=verify_after_native_save,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
