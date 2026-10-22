"""Create the manufacturing drawing for the modified McMaster 9490T1 anchor."""

from __future__ import annotations

import argparse
import json
import math
import sys
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
from _drawing_layout_check import DEFAULT_BOUNDARY_ALLOWANCE_M
from _drawing_edges import visible_view_entities
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


def _supplier_eye_circle(
    adapter: Any, view: Any, raw: Any, *, readback: dict[str, Any] | None = None,
) -> tuple[float, ...] | None:
    """Read an exact model-XY circle on the authoritative physical eye torus."""
    if readback is not None:
        readback.update(dict.fromkeys((
            "curve_present", "is_circle", "circle_params_m", "circle_length7",
            "circle_finite7", "circle_center_matches", "circle_z_normal_matches",
            "view_present", "view_name", "expected_view_name", "view_name_matches",
            "document_present", "native_path", "source_resolved_path", "lexical_path_matches",
            "expected_feature_present", "face_present", "owner_present", "owner_same_as_expected",
            "surface_present", "is_torus", "torus_params_m", "torus_length8", "torus_finite8",
            "torus_center_matches", "torus_z_normal_matches", "torus_major_matches",
            "torus_minor_matches", "id_diameter_matches",
        ), "unobserved"))
        readback["first_rejection"] = None

    def mark(stage, **values):
        if readback is not None:
            readback.update(values)
            readback["stage"] = stage

    def reject(field):
        if readback is not None:
            readback["first_rejection"] = field
        return None

    mark("raw", raw_present=raw is not None)
    if raw is None:
        return reject("raw_present")
    mark("bind_silhouette")
    silhouette = _early_bound(raw, "ISilhouetteEdge")
    mark("GetCurve")
    raw_curve = silhouette.GetCurve()
    mark("GetCurve", curve_present=raw_curve is not None)
    if raw_curve is None:
        return reject("curve_present")
    mark("bind_curve")
    curve = _early_bound(raw_curve, "ICurve")
    mark("IsCircle")
    is_circle = curve.IsCircle()
    mark("IsCircle", is_circle=bool(is_circle))
    if not is_circle:
        return reject("is_circle")
    mark("CircleParams")
    circle = tuple(float(value) for value in curve.CircleParams)
    mark(
        "CircleParams",
        circle_params_m=[value if math.isfinite(value) else str(value) for value in circle],
        circle_length7=len(circle) == 7,
        circle_finite7=len(circle) == 7 and all(math.isfinite(value) for value in circle),
        circle_center_matches=len(circle) >= 3 and all(abs(value) < 1e-8 for value in circle[:3]),
        circle_z_normal_matches=len(circle) >= 6 and abs(abs(circle[5]) - 1.0) < 1e-8,
    )
    if not (
        len(circle) == 7
        and all(math.isfinite(value) for value in circle)
        and all(abs(value) < 1e-8 for value in circle[:3])
        and abs(abs(circle[5]) - 1.0) < 1e-8
    ):
        for field in ("circle_length7", "circle_finite7", "circle_center_matches", "circle_z_normal_matches"):
            if readback is not None and not readback[field]:
                return reject(field)
        return None
    mark("GetView")
    native_view = silhouette.GetView()
    mark("GetView", view_present=native_view is not None)
    if native_view is None:
        return reject("view_present")
    mark("native_view_name")
    native_name = view_name(adapter, native_view)
    mark("expected_view_name", view_name=native_name)
    expected_name = view_name(adapter, view)
    mark("view_name_matches", expected_view_name=expected_name, view_name_matches=native_name == expected_name)
    if native_name != expected_name:
        return reject("view_name_matches")
    mark("ReferencedDocument")
    raw_document = view.ReferencedDocument
    mark("ReferencedDocument", document_present=raw_document is not None)
    if raw_document is None:
        return reject("document_present")
    mark("bind_document")
    document = _early_bound(raw_document, "IModelDoc2")
    mark("GetPathName")
    native_path = str(document.GetPathName())
    mark("SOURCE.resolve", native_path=native_path)
    source_path = SOURCE.resolve().as_posix()
    path_matches = native_path.replace("\\", "/").casefold() == source_path.casefold()
    mark("lexical_path_matches", source_resolved_path=source_path, lexical_path_matches=path_matches)
    if not path_matches:
        return reject("lexical_path_matches")
    mark("FeatureByName")
    expected_feature = _early_bound(raw_document, "IPartDoc").FeatureByName(_SUPPLIER_EYE_FEATURE)
    mark("GetFace", expected_feature_present=expected_feature is not None)
    raw_face = silhouette.GetFace()
    mark("GetFace", face_present=raw_face is not None)
    if expected_feature is None or raw_face is None:
        return reject("expected_feature_present" if expected_feature is None else "face_present")
    mark("bind_face")
    face = _early_bound(raw_face, "IFace2")
    mark("GetFeature")
    owner = face.GetFeature()
    mark("GetFeature", owner_present=owner is not None)
    if owner is None:
        return reject("owner_present")
    mark("IsSame_owner_expected")
    owner_same = int(adapter.swApp.IsSame(owner, expected_feature))
    mark("IsSame_owner_expected", owner_same_as_expected=owner_same)
    if owner_same != 1:
        return reject("owner_same_as_expected")
    mark("GetSurface")
    raw_surface = face.GetSurface()
    mark("GetSurface", surface_present=raw_surface is not None)
    if raw_surface is None:
        return reject("surface_present")
    mark("bind_surface")
    surface = _early_bound(raw_surface, "ISurface")
    mark("IsTorus")
    is_torus = surface.IsTorus()
    mark("IsTorus", is_torus=bool(is_torus))
    if not is_torus:
        return reject("is_torus")
    mark("TorusParams")
    torus = tuple(float(value) for value in surface.TorusParams)
    mark(
        "TorusParams",
        torus_params_m=[value if math.isfinite(value) else str(value) for value in torus],
        torus_length8=len(torus) == 8,
        torus_finite8=len(torus) == 8 and all(math.isfinite(value) for value in torus),
        torus_center_matches=len(torus) >= 3 and all(abs(value) < 1e-8 for value in torus[:3]),
        torus_z_normal_matches=len(torus) >= 6 and abs(abs(torus[5]) - 1.0) < 1e-8,
        torus_major_matches=len(torus) >= 7 and abs(
            torus[6] * 2000.0 - 2.0 * _SUPPLIER_ANCHOR.eye_mean_radius_mm
        ) < 1e-5,
        torus_minor_matches=len(torus) >= 8 and abs(
            torus[7] * 2000.0 - _SUPPLIER_ANCHOR.wire_dia_mm
        ) < 1e-5,
    )
    if not (
        len(torus) == 8
        and all(math.isfinite(value) for value in torus)
        and all(abs(value) < 1e-8 for value in torus[:3])
        and abs(abs(torus[5]) - 1.0) < 1e-8
        and abs(torus[6] * 2000.0 - 2.0 * _SUPPLIER_ANCHOR.eye_mean_radius_mm) < 1e-5
        and abs(torus[7] * 2000.0 - _SUPPLIER_ANCHOR.wire_dia_mm) < 1e-5
    ):
        for field in (
            "torus_length8", "torus_finite8", "torus_center_matches",
            "torus_z_normal_matches", "torus_major_matches", "torus_minor_matches",
        ):
            if readback is not None and not readback[field]:
                return reject(field)
        return None
    mark("accepted_circle")
    return circle


def _supplier_eye_failure_readback(adapter: Any, view: Any, visible: Any) -> dict[str, Any]:
    """Observe the failed inventory, never select, regenerate, or relax it."""
    packet: dict[str, Any] = {
        "diagnostic": "counter-eye-missing-id",
        "observation_only": True,
        "thresholds": {
            "circle_center_abs_m_lt": 1e-8,
            "circle_abs_axis_z_minus_one_lt": 1e-8,
            "diameter_error_mm_lt": 1e-5,
            "id_mm": SUPPLIER_EYE_ID_MM,
            "od_mm_observation_only": _SUPPLIER_ANCHOR.eye_od_mm,
            "torus_center_abs_m_lt": 1e-8,
            "torus_abs_axis_z_minus_one_lt": 1e-8,
            "torus_major_radius_mm": _SUPPLIER_ANCHOR.eye_mean_radius_mm,
            "torus_wire_diameter_mm": _SUPPLIER_ANCHOR.wire_dia_mm,
            "torus_order": "centerXYZ_m,axisXYZ,major_radius_m,minor_radius_m",
        },
    }

    def capture(row, field, getter, *, describe=None):
        try:
            value = getter()
            row[field] = value if describe is None else describe(value)
            return value
        except Exception as exc:
            row[field] = None
            row.setdefault("errors", {})[field] = {
                "type": type(exc).__name__, "message": str(exc),
            }
            return None

    def entity(row, field, getter, kind):
        raw = capture(row, field + "_present", getter, describe=lambda value: value is not None)
        return capture(
            row, field + "_bound",
            lambda: _early_bound(raw, kind) if raw is not None else None,
            describe=lambda value: value is not None,
        )

    def same(row, field, first, second):
        capture(
            row, field,
            lambda: int(adapter.swApp.IsSame(first, second))
            if first is not None and second is not None else None,
        )

    def feature_readback(feature):
        row = {"present": feature is not None}
        for field, getter in (
            ("name", lambda: str(feature.Name)),
            ("type", lambda: str(feature.GetTypeName2())),
            ("id", lambda: int(feature.GetID())),
        ):
            capture(row, field, lambda getter=getter: getter() if feature is not None else None)
        same(row, "self_is_same", feature, feature)
        return row

    context: dict[str, Any] = {}
    packet["source"] = context
    expected_name = capture(context, "view_name", lambda: view_name(adapter, view))
    referenced_configuration = capture(
        context, "referenced_configuration", lambda: str(view.ReferencedConfiguration),
    )
    capture(context, "display_mode", lambda: int(view.GetDisplayMode2()))
    capture(
        context, "model_to_view_transform",
        lambda: tuple(float(value) for value in view.ModelToViewTransform.ArrayData),
    )
    same(context, "view_self_is_same", view, view)
    document = entity(context, "document", lambda: view.ReferencedDocument, "IModelDoc2")
    path = capture(
        context, "native_path",
        lambda: str(document.GetPathName()) if document is not None else None,
    )
    capture(context, "source_raw_path", lambda: str(SOURCE))
    source_resolved = capture(context, "source_resolved_path", lambda: SOURCE.resolve().as_posix())
    capture(
        context, "lexical_path_matches",
        lambda: path.replace("\\", "/").casefold() == source_resolved.casefold()
        if path is not None and source_resolved is not None else None,
    )
    capture(
        context, "native_canonical_path",
        lambda: Path(path).resolve().as_posix() if path else None,
    )
    capture(context, "source_canonical_path", lambda: SOURCE.resolve().as_posix())
    capture(
        context, "physical_samefile",
        lambda: SOURCE.samefile(path) if path else None,
    )
    for field, candidate_path in (("source_file_id", SOURCE), ("native_file_id", path)):
        capture(
            context, field,
            lambda candidate_path=candidate_path: (
                (lambda stat: {"dev": stat.st_dev, "ino": stat.st_ino})(Path(candidate_path).stat())
                if candidate_path else None
            ),
        )
    capture(context, "document_type", lambda: int(document.GetType()) if document is not None else None)
    capture(context, "document_title", lambda: str(document.GetTitle()) if document is not None else None)
    manager = entity(
        context, "configuration_manager",
        lambda: document.ConfigurationManager if document is not None else None,
        "IConfigurationManager",
    )
    for field, getter in (
        ("active_configuration", lambda: manager.ActiveConfiguration if manager is not None else None),
        ("referenced_configuration_object", lambda: document.GetConfigurationByName(referenced_configuration)
         if document is not None and referenced_configuration is not None else None),
    ):
        row: dict[str, Any] = {}
        context[field] = row
        configuration = entity(row, "configuration", getter, "IConfiguration")
        capture(row, "name", lambda: str(configuration.Name) if configuration is not None else None)
        capture(row, "id", lambda: int(configuration.GetID()) if configuration is not None else None)
    part = entity(context, "part", lambda: document, "IPartDoc")
    expected_feature = entity(
        context, "expected_feature",
        lambda: part.FeatureByName(_SUPPLIER_EYE_FEATURE) if part is not None else None,
        "IFeature",
    )
    context["expected_feature"] = feature_readback(expected_feature)
    extension = entity(
        context, "extension",
        lambda: document.Extension if document is not None else None, "IModelDocExtension",
    )
    view_feature = entity(
        context, "view_corresponding_feature",
        lambda: view.GetCorresponding(expected_feature) if expected_feature is not None else None,
        "IFeature",
    )
    context["view_corresponding_feature"] = feature_readback(view_feature)
    same(context, "view_feature_same_as_expected", view_feature, expected_feature)

    def face_readback(raw, *, frame):
        row: dict[str, Any] = {"coordinate_context": frame}
        face = entity(row, "face", lambda: raw, "IFace2")
        same(row, "self_is_same", face, face)
        owner = entity(
            row, "owner", lambda: face.GetFeature() if face is not None else None, "IFeature",
        )
        row["owner"] = feature_readback(owner)
        same(row, "owner_same_as_expected", owner, expected_feature)
        row["owner_matches_expected"] = (
            row["owner_same_as_expected"] == 1 if row["owner_same_as_expected"] is not None else None
        )
        surface = entity(
            row, "surface", lambda: face.GetSurface() if face is not None else None, "ISurface",
        )
        capture(row, "surface_identity", lambda: int(surface.Identity()) if surface is not None else None)
        is_torus = capture(row, "is_torus", lambda: bool(surface.IsTorus()) if surface is not None else None)
        torus = capture(
            row, "torus_params_m",
            lambda: tuple(float(value) for value in surface.TorusParams) if is_torus else None,
        )
        for field, predicate in (
            ("torus_length8", lambda: len(torus) == 8),
            ("torus_finite8", lambda: len(torus) == 8 and all(math.isfinite(value) for value in torus)),
            ("torus_center_matches", lambda: len(torus) >= 3 and all(abs(value) < 1e-8 for value in torus[:3])),
            ("torus_z_normal_matches", lambda: len(torus) >= 6 and abs(abs(torus[5]) - 1.0) < 1e-8),
            ("torus_major_matches", lambda: len(torus) >= 7 and abs(
                torus[6] * 2000.0 - 2.0 * _SUPPLIER_ANCHOR.eye_mean_radius_mm
            ) < 1e-5),
            ("torus_minor_matches", lambda: len(torus) >= 8 and abs(
                torus[7] * 2000.0 - _SUPPLIER_ANCHOR.wire_dia_mm
            ) < 1e-5),
        ):
            capture(row, field, lambda predicate=predicate: predicate() if torus is not None else None)
        row["eye_torus_relevant"] = is_torus is True and (
            row["torus_center_matches"] is True or row["torus_major_matches"] is True
        )
        if frame == "source_part" and row["eye_torus_relevant"] and torus is not None and len(torus) >= 3:
            capture(
                row, "center_sheet_xy_m",
                lambda: model_points_in_view(
                    adapter, view, [torus[:3]], label="counter eye failure source torus centre",
                )[0],
            )
        return row, face

    source_faces = capture(
        context, "wire_face_count",
        lambda: tuple(expected_feature.GetFaces() or ()) if expected_feature is not None else None,
        describe=lambda faces: len(faces) if faces is not None else None,
    )
    context["wire_faces"] = []
    native_source_faces = []
    for index, raw in enumerate(source_faces or ()):
        row, face = face_readback(raw, frame="source_part")
        row["index"] = index
        context["wire_faces"].append(row)
        native_source_faces.append(face)

    def curve_readback(row, curve):
        capture(row, "curve_identity", lambda: int(curve.Identity()) if curve is not None else None)
        is_circle = capture(row, "is_circle", lambda: bool(curve.IsCircle()) if curve is not None else None)
        circle = capture(
            row, "circle_params_m",
            lambda: tuple(float(value) for value in curve.CircleParams) if is_circle else None,
        )
        for field, predicate in (
            ("circle_length7", lambda: len(circle) == 7),
            ("circle_finite7", lambda: len(circle) == 7 and all(math.isfinite(value) for value in circle)),
            ("circle_center_matches", lambda: len(circle) >= 3 and all(abs(value) < 1e-8 for value in circle[:3])),
            ("circle_z_normal_matches", lambda: len(circle) >= 6 and abs(abs(circle[5]) - 1.0) < 1e-8),
            ("id_diameter_matches", lambda: len(circle) >= 7 and abs(circle[6] * 2000.0 - SUPPLIER_EYE_ID_MM) < 1e-5),
            ("od_diameter_matches_observation_only", lambda: len(circle) >= 7 and abs(
                circle[6] * 2000.0 - _SUPPLIER_ANCHOR.eye_od_mm
            ) < 1e-5),
        ):
            capture(row, field, lambda predicate=predicate: predicate() if circle is not None else None)
        return is_circle

    def sample_non_circle(row, curve):
        is_line = capture(row, "is_line", lambda: bool(curve.IsLine()))
        if is_line:
            capture(row, "line_params_m", lambda: tuple(float(value) for value in curve.LineParams))
        # Generated ICurve wrapper: bool retval followed by Start, End, IsClosed,
        # IsPeriodic OUTs. Infinite lines are summarized, never evaluated.
        ends = capture(row, "end_params", lambda: tuple(curve.GetEndParams()))
        valid = capture(
            row, "sample_range_valid",
            lambda: len(ends) == 5 and bool(ends[0]) and is_line is False
            and all(math.isfinite(float(value)) and abs(float(value)) < 1e100 for value in ends[1:3])
            and float(ends[1]) < float(ends[2])
            if ends is not None else None,
        )
        row["samples"] = []
        if not valid:
            return
        start, end = float(ends[1]), float(ends[2])
        for index in range(9):
            parameter = start + (end - start) * index / 8.0
            sample = {"parameter": parameter}
            capture(sample, "xyz_m", lambda: tuple(float(value) for value in curve.Evaluate2(parameter, 0)[:3]))
            row["samples"].append(sample)

    candidates = []
    packet["kind4"] = candidates
    for index, raw in enumerate(visible):
        row = {"index": index, "raw_present": raw is not None}
        candidates.append(row)
        silhouette = entity(row, "silhouette", lambda: raw, "ISilhouetteEdge")
        curve = entity(
            row, "curve", lambda: silhouette.GetCurve() if silhouette is not None else None, "ICurve",
        )
        is_circle = curve_readback(row, curve)
        native_view = entity(
            row, "view", lambda: silhouette.GetView() if silhouette is not None else None, "IView",
        )
        name = capture(row, "view_name", lambda: view_name(adapter, native_view) if native_view is not None else None)
        row["expected_view_name"] = expected_name
        row["view_name_matches"] = name == expected_name if name is not None and expected_name is not None else None
        same(row, "view_self_is_same", native_view, native_view)
        same(row, "view_same_as_front", native_view, view)
        row["source_lexical_path_matches"] = context["lexical_path_matches"]
        raw_face = capture(
            row, "face_present", lambda: silhouette.GetFace() if silhouette is not None else None,
            describe=lambda value: value is not None,
        )
        face_row, face = face_readback(raw_face, frame="silhouette_GetFace_context_undocumented")
        row["face"] = face_row
        row["same_as_source_wire_faces"] = []
        if face_row["eye_torus_relevant"]:
            for source_index, source_face in enumerate(native_source_faces):
                equality = {"source_face_index": source_index}
                same(equality, "is_same", face, source_face)
                row["same_as_source_wire_faces"].append(equality)
            mapped = entity(
                row, "mapped_source_face",
                lambda: extension.GetCorrespondingEntity2(face) if extension is not None and face is not None else None,
                "IFace2",
            )
            row["mapped_source_face"], _ = face_readback(mapped, frame="source_part")
            roundtrip = entity(
                row, "roundtrip_face",
                lambda: view.GetCorrespondingEntity(mapped) if mapped is not None else None, "IFace2",
            )
            same(row, "roundtrip_self_is_same", roundtrip, roundtrip)
            same(row, "roundtrip_same_as_drawing_face", roundtrip, face)
        if curve is not None and is_circle is not True and face_row["eye_torus_relevant"]:
            sample_non_circle(row, curve)
        row["accepted_id_predicates"] = all(value is True for value in (
            row["raw_present"], row["curve_present"], is_circle,
            row["circle_finite7"], row["circle_center_matches"], row["circle_z_normal_matches"],
            row["id_diameter_matches"], row["view_present"], row["view_name_matches"],
            context["document_present"], row["source_lexical_path_matches"],
            context["expected_feature_present"], row["face_present"],
            face_row["owner_matches_expected"], face_row["surface_present"], face_row["is_torus"],
            face_row["torus_finite8"], face_row["torus_center_matches"], face_row["torus_z_normal_matches"],
            face_row["torus_major_matches"], face_row["torus_minor_matches"],
        ))
    packet["kind4_count"] = len(candidates)
    packet["raw_exact_circle_count"] = sum(
        row["is_circle"] is True and row["circle_finite7"] is True for row in candidates
    )
    packet["raw_origin_xy_id_circle_count"] = sum(
        all(row[field] is True for field in (
            "is_circle", "circle_finite7", "circle_center_matches",
            "circle_z_normal_matches", "id_diameter_matches",
        )) for row in candidates
    )
    packet["accepted_id_count"] = sum(row["accepted_id_predicates"] for row in candidates)
    edges = capture(
        packet, "kind1_count",
        lambda: visible_view_entities(view, 1, label="counter anchor missing-ID census edges"),
        describe=len,
    )
    packet["kind1"] = []
    packet["kind1_curve_identity_counts"] = {}
    for index, raw in enumerate(edges or ()):
        row = {"index": index, "raw_present": raw is not None}
        packet["kind1"].append(row)
        edge = entity(row, "edge", lambda: raw, "IEdge")
        curve = entity(row, "curve", lambda: edge.GetCurve() if edge is not None else None, "ICurve")
        is_circle = curve_readback(row, curve)
        identity = str(row["curve_identity"])
        counts = packet["kind1_curve_identity_counts"]
        counts[identity] = counts.get(identity, 0) + 1
        adjacent = capture(
            row, "adjacent_face_count",
            lambda: tuple(edge.GetTwoAdjacentFaces2() or ()) if edge is not None else (),
            describe=len,
        )
        row["adjacent_faces"] = []
        for face_index, raw_face in enumerate(adjacent or ()):
            face_row, _ = face_readback(raw_face, frame="kind1_adjacent_face_context")
            face_row["index"] = face_index
            row["adjacent_faces"].append(face_row)
        if curve is not None and is_circle is not True and any(
            face_row["eye_torus_relevant"] for face_row in row["adjacent_faces"]
        ):
            sample_non_circle(row, curve)

    def json_values(value):
        if isinstance(value, float) and not math.isfinite(value):
            return str(value)
        if isinstance(value, dict):
            return {key: json_values(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [json_values(item) for item in value]
        return value

    return json_values(packet)


def _supplier_references(adapter: Any, front: Any) -> list[tuple[str, dict[str, Any]]]:
    """Use the physical matching eye ID and an explicit nominal thread carrier."""
    # Imported controls can leave the edge set unregenerated. The existing
    # HLV-to-HLR transition regenerates it; Update alone only refreshes display.
    set_hidden_lines_removed(adapter, front)
    front.UpdateViewDisplayGeometry()
    eye = None
    visible = visible_view_entities(front, 4, label="counter anchor supplier contours")
    observations = []
    for index, raw in enumerate(visible):
        observation = {"index": index}
        observations.append(observation)
        try:
            circle = _supplier_eye_circle(adapter, front, raw, readback=observation)
        except Exception as error:
            observation["error"] = {"type": type(error).__name__, "message": str(error)}
            packet = _supplier_eye_failure_readback(adapter, front, visible)
            packet["predicate_time"] = observations
            error.add_note(json.dumps(packet, sort_keys=True, allow_nan=False))
            raise
        if circle is not None:
            observation["id_diameter_matches"] = abs(circle[6] * 2000.0 - SUPPLIER_EYE_ID_MM) < 1e-5
            if observation["id_diameter_matches"]:
                eye = raw
                break
            observation["first_rejection"] = "id_diameter_matches"
    if eye is None:
        error = RuntimeError("unchanged counter eye has no exact ID circular silhouette")
        packet = _supplier_eye_failure_readback(adapter, front, visible)
        packet["predicate_time"] = observations
        error.add_note(json.dumps(packet, sort_keys=True, allow_nan=False))
        raise error
    try:
        _select_view_entity(
            adapter, front, "SILHOUETTE", None, label="EyeID", entity=eye
        )
        display = adapter.currentModel.AddDiameterDimension2(0.150, 0.241, 0.0)
    finally:
        adapter.currentModel.ClearSelection2(True)
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
                circle = _supplier_eye_circle(adapter, view, entities[0])
                if circle is None or abs(circle[6] * 2000.0 - SUPPLIER_EYE_ID_MM) >= 1e-5:
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
    refs = _supplier_references(adapter, front)
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
