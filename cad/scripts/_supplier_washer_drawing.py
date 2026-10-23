"""Import model-owned washer supplier bands; add only unbanded rim refs.

The part owns every banded dimension's native value, tolerance and supplier
presentation. Imports retain the source's explicit display units; precision,
reference ink and bands are never rewritten.

Source attachments are proved from independent part geometry in the actual owning
view; native feature/entity correspondence, not names or values, proves membership.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hashlib
import json
from math import dist, isfinite
from pathlib import Path
from typing import Any, Literal

from solidworks_mcp.adapters.solidworks.drawing import dimension_name, view_name

from _com import _early_bound
from _drawing_attachment import _is_same_attachment
from _drawing_annotation_extent import CLEAR_GAP_M, PLACE_SETTLE_M
from _drawing_common import rebuild_drawing
from _drawing_edges import ViewEdges, scan_view_edges
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_precision import _named_dimensions
from _drawing_layout_audit import annotation_display
from _drawing_leaders import set_near_side_diameter
from _layout_audit import annotation_geometry, calibrate_sheet_advance
from _layout_geometry import segment_box_distance, segment_box_overlap_length
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
from _supplier_reference_text import (
    assert_reference_text_stations,
    measure_reference_text,
    measured_native_text_bounds,
    shelve_reference_text,
)
from _supplier_washer_model import (
    BORE_DIAMETER,
    OUTER_DIAMETER,
    SOURCE_DIMENSIONS,
    THICKNESS,
    _assert_supplier_washer_presentation,
    assert_supplier_washer_band,
    assert_supplier_washer_body,
    assert_supplier_washer_source_attachment,
)
import _telemetry


@dataclass(frozen=True)
class _WasherReference:
    view: Any
    selection_name: str
    full_name: str
    label: str
    expected_mm: float
    presentation: Literal["length", "diameter"]
    imported: bool
    callout: str | None = None


@dataclass(frozen=True)
class SupplierWasherProof:
    """Keep the live finalizer check callable; audit saved bytes separately."""

    settled_check: Callable[[], None]
    saved_check: Callable[[Any, Path], None]

    def __call__(self) -> None:
        self.settled_check()


def _persist_imported_units(
    adapter: Any, view: Any, display: Any, *, label: str,
    units: Literal["in", "mm"], precision: int, expected_mm: float,
    callout: str | None,
) -> None:
    """Transfer only unit-display ownership lost by native model-item import."""
    model = _early_bound(view, "IView").ReferencedDocument
    if model is None:
        raise RuntimeError(f"{label}: imported supplier dimension has no source part")
    feature_name, name = SOURCE_DIMENSIONS[label]
    feature = _early_bound(model, "IPartDoc").FeatureByName(feature_name)
    if feature is None:
        raise RuntimeError(f"{label}: imported supplier source feature is missing")
    source, native = _named_dimensions(adapter, feature_name, {name}, feature=feature)[name]
    try:
        _assert_supplier_washer_presentation(
            source, label=label, units=units, precision=precision,
            expected_mm=expected_mm, callout=callout,
        )
        identity = adapter.swApp.IsSame(display.GetDimension2(0), native)
        if type(identity) is not int or identity != 1:
            raise RuntimeError(f"{label}: imported supplier dimension is not its native source")
        # Import selects drawing-document units even when the source display has
        # explicit units. SDK GetUnits/GetFractionBase then return -1, not the
        # supplier settings. FractDenom is meaningful only for fractional inches;
        # transfer the source getter unchanged rather than inventing a denominator.
        # HalfAway=0 is the source author's documented decimal-rounding choice.
        status = display.SetUnits2(
            False, source.GetUnits(), source.GetFractionBase(),
            source.GetFractionValue(), source.GetRoundToFraction(), 0,
        )
        if type(status) is not int or status != 0:
            raise RuntimeError(f"{label}: imported supplier units were rejected ({status!r})")
        assert_supplier_reference_dimension(
            adapter, display, label=label, units=units, precision=precision,
            expected_mm=expected_mm, presentation="length" if label == THICKNESS else "diameter",
            callout=callout,
        )
    except Exception as error:
        error.add_note("supplier washer source/import readback: " + json.dumps(
            {"source": _saved_display_readback(source), "imported": _saved_display_readback(display)},
            sort_keys=True, default=repr,
        ))
        raise


def _rim(
    edges: ViewEdges, *, axis: Literal["y", "z"], station_mm: float,
    diameter_mm: float, label: str,
) -> Any:
    center = (0.0, station_mm, 0.0) if axis == "y" else (0.0, 0.0, station_mm)
    normal = (0.0, 1.0, 0.0) if axis == "y" else (0.0, 0.0, 1.0)
    return edges.circle_at(
        center, diameter_mm / 2.0, axis=normal, label=label,
        center_tol_mm=1e-6, radius_tol_mm=1e-6,
    ).edge


def _assert_rim(adapter: Any, display: Any, rim: Any, *, label: str) -> None:
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    attached = list(annotation.GetAttachedEntities3() or ())
    if (
        len(attached) != 1 or attached[0] is None
        or not _is_same_attachment(adapter, attached[0], rim, "EDGE")
        or annotation.IsDangling() or int(annotation.Visible) != 1
    ):
        raise RuntimeError(f"{label}: native unbanded diameter lost its exact physical rim")


def _native_diameter(
    adapter: Any, view: Any, rim: Any, *, text_xy: tuple[float, float], label: str,
) -> Any:
    """The policy exception: an unbanded reference on an actual solid rim."""
    draw = adapter.currentModel
    if not _early_bound(draw, "IDrawingDoc").ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"{label}: failed to activate drawing view")
    draw.ClearSelection2(True)
    manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    data = manager.CreateSelectData()
    data.View = view
    if _early_bound(rim, "IEntity").Select4(False, data) is not True:
        raise RuntimeError(f"{label}: failed to select physical rim")
    if (
        int(manager.GetSelectedObjectCount2(-1)) != 1
        or int(adapter.swApp.IsSame(manager.GetSelectedObject6(1, -1), rim)) != 1
    ):
        raise RuntimeError(f"{label}: selection is not the intended physical rim")
    display, status = _early_bound(draw.Extension, "IModelDocExtension").AddSpecificDimension(
        text_xy[0], text_xy[1], 0.0, 6, 0  # swDiameterDimension
    )
    draw.ClearSelection2(True)
    if display is None or int(status) != 0:
        raise RuntimeError(f"{label}: native diameter failed ({status})")
    display = _early_bound(display, "IDisplayDimension")
    _assert_rim(adapter, display, rim, label=label)
    return display


def _reference(
    display: Any, view: Any, label: str, expected_mm: float, *,
    imported: bool, callout: str | None = None,
) -> _WasherReference:
    selection_name = str(display.GetNameForSelection() or "")
    full_name = str(_early_bound(display.GetDimension2(0), "IDimension").FullName or "")
    if not selection_name or not full_name:
        raise RuntimeError(f"{label}: native dimension has no stable selection/full name")
    return _WasherReference(view, selection_name, full_name, label, expected_mm,
                            "length" if label == THICKNESS else "diameter", imported, callout)


def _visible_dimensions(view: Any) -> list[Any]:
    visible = []
    raw = _early_bound(view, "IView").GetFirstDisplayDimension5()
    while raw is not None:
        display = _early_bound(raw, "IDisplayDimension")
        if int(_early_bound(display.GetAnnotation(), "IAnnotation").Visible) == 1:
            visible.append(display)
        raw = display.GetNext5()
    return visible


@_telemetry.traced("drawing.assert_supplier_washer_dimensions")
def assert_supplier_washer_dimensions(
    adapter: Any, views: dict[str, Any], references: tuple[_WasherReference, ...], *,
    axis: Literal["y", "z"], bore_mm: float, outer_mm: float, thickness_mm: float,
    units: Literal["in", "mm"], precision: Mapping[str, int],
    bands: Mapping[str, tuple[float, float, str]],
) -> dict[str, Any]:
    """Reacquire displays, source entities and final solid rims after rebuild."""
    if len(references) != 3 or {reference.label for reference in references} != {
        OUTER_DIAMETER, BORE_DIAMETER, THICKNESS,
    }:
        raise RuntimeError("supplier washer must export exactly OD, bore and thickness")
    face = views["*Top" if axis == "y" else "*Front"]
    side = views["*Front" if axis == "y" else "*Top"]
    model = _early_bound(face, "IView").ReferencedDocument
    if model is None:
        raise RuntimeError("supplier washer drawing has no referenced source part")
    assert_supplier_washer_body(model, axis=axis, bore_mm=bore_mm,
                               outer_mm=outer_mm, thickness_mm=thickness_mm)
    face_edges = scan_view_edges(face, label="settled supplier washer face rims")
    side_edges = scan_view_edges(side, label="settled supplier washer axial rims")
    # Body-backed proof remains independent of construction-sketch attachments.
    face_rims = {
        label: _rim(face_edges, axis=axis, station_mm=thickness_mm,
                    diameter_mm=diameter, label=label)
        for label, diameter in ((OUTER_DIAMETER, outer_mm), (BORE_DIAMETER, bore_mm))
    }
    for station in (0.0, thickness_mm):
        _rim(side_edges, axis=axis, station_mm=station, diameter_mm=outer_mm, label=THICKNESS)
    current: dict[str, Any] = {}
    for orientation, view in views.items():
        expected = [reference for reference in references
                    if int(adapter.swApp.IsSame(reference.view, view)) == 1]
        visible = _visible_dimensions(view)
        required_count = 2 if orientation == ("*Top" if axis == "y" else "*Front") else (
            1 if orientation == ("*Front" if axis == "y" else "*Top") else 0
        )
        if len(expected) != required_count or len(visible) != required_count:
            raise RuntimeError(f"supplier washer {orientation} exports {len(visible)} dimensions, expected {required_count}")
        for reference in expected:
            matches = [display for display in visible
                       if str(display.GetNameForSelection() or "") == reference.selection_name]
            if len(matches) != 1:
                raise RuntimeError(f"{reference.label}: settled native display census failed")
            display = matches[0]
            native = _early_bound(display.GetDimension2(0), "IDimension")
            if str(native.FullName or "") != reference.full_name:
                raise RuntimeError(f"{reference.label}: settled display resolves to another native dimension")
            current[reference.label] = display
    for reference in references:
        display = current[reference.label]
        assert_supplier_reference_dimension(
            adapter, display, label=reference.label, units=units,
            precision=precision[reference.label], expected_mm=reference.expected_mm,
            presentation=reference.presentation, callout=reference.callout,
        )
        if reference.imported:
            feature_name, source_name = SOURCE_DIMENSIONS[reference.label]
            feature = _early_bound(model, "IPartDoc").FeatureByName(feature_name)
            if feature is None:
                raise RuntimeError(f"{reference.label}: supplier source feature is missing")
            source_display, source_native = _named_dimensions(
                adapter, feature_name, {source_name}, feature=feature,
            )[source_name]
            _assert_supplier_washer_presentation(
                source_display, label=reference.label, units=units,
                precision=precision[reference.label], expected_mm=reference.expected_mm,
                callout=reference.callout,
            )
            identity = adapter.swApp.IsSame(display.GetDimension2(0), source_native)
            if type(identity) is not int or identity != 1:
                raise RuntimeError(f"{reference.label}: imported dimension is not its actual native source")
            assert_supplier_washer_source_attachment(
                adapter, model, display, label=reference.label, axis=axis,
                bore_mm=bore_mm, outer_mm=outer_mm, thickness_mm=thickness_mm,
                visible=True, view=reference.view,
            )
        else:
            _assert_rim(adapter, display, face_rims[reference.label], label=reference.label)
        assert_supplier_washer_band(
            display, nominal_mm=reference.expected_mm, band=bands.get(reference.label),
            precision=precision[reference.label], label=reference.label,
        )
    return current


_PLACEMENT_TOLERANCE_M = 1e-5


@dataclass(frozen=True)
class _WasherPlacement:
    """Only immutable sheet-space scalars cross the saved-document boundary."""

    tips: tuple[tuple[float, ...], ...]
    witnesses: tuple[tuple[float, ...], ...]
    thickness_x: float
    face_outline: tuple[float, ...]
    diameter_positions: tuple[tuple[str, tuple[float, ...]], ...]


def _placement_position(annotation: Any, *, label: str) -> tuple[float, ...]:
    position = tuple(float(value) for value in annotation.GetPosition())
    if len(position) != 3 or not all(map(isfinite, position)):
        raise RuntimeError(f"{label}: unreadable washer annotation position")
    return position


def _face_outline(view: Any) -> tuple[float, ...]:
    outline = tuple(float(value) for value in _early_bound(view, "IView").GetOutline())
    if (
        len(outline) != 4 or not all(map(isfinite, outline))
        or outline[0] >= outline[2] or outline[1] >= outline[3]
    ):
        raise RuntimeError("supplier washer face has unreadable native outline")
    return outline


def _diameter_caption(adapter: Any, display: Any, *, label: str) -> tuple[Any, tuple[Any, ...], Any]:
    """Measure every native caption fragment, including Ø, limits and below text.

    Reuse the shared SDK-anchor bounds reader; never estimate missing widths
    or use the numeric annotation anchor as ink.
    """
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    data, errors = annotation_display(adapter, annotation)
    if errors:
        raise RuntimeError(f"{label}: refused washer caption display reads: {errors!r}")
    text, fragments = measured_native_text_bounds(
        data.get("texts", ()), label=f"{label}: washer caption",
    )
    for kind, rows in data.items():
        if kind != "texts" and any(
            not row or not all(isfinite(float(value)) for value in row) for row in rows
        ):
            raise RuntimeError(f"{label}: non-finite native washer caption graphics ({kind})")
    if (
        not data.get("lines") or any(len(row) < 10 for row in data["lines"])
        or len(data.get("arrows", ())) != 1
        or any(
            len(row) < 8 or row[6] <= 0.0 or row[7] <= 0.0 or row[3] ** 2 + row[4] ** 2 == 0.0
            for row in data["arrows"]
        )
    ):
        raise RuntimeError(f"{label}: washer diameter lost its native single-arrow leader graphics")
    record = {"type": 4, "display": data, "dim": {"hole_callout": False}}
    geometry = annotation_geometry(
        record, owner=label, advance=calibrate_sheet_advance((record,)),
    )
    if geometry is None or not geometry.segments or any(
        not all(map(isfinite, (run.x0, run.y0, run.x1, run.y1)))
        for run in geometry.segments
    ):
        raise RuntimeError(f"{label}: unreadable native washer caption leader")
    return text, fragments, geometry


def _assert_diameter_placement(adapter: Any, display: Any, view: Any, *, label: str) -> None:
    # Read back the documented near-side diameter style, not just setter status.
    if (
        display.Diametric is not True or type(display.ArrowSide) is not int or display.ArrowSide != 1
        or display.SolidLeader is not False or display.GetUseDocBrokenLeader() is not False
        or type(display.GetBrokenLeader2()) is not int or display.GetBrokenLeader2() != 2
        or display.GetUseDocSecondArrow() is not False or display.GetSecondArrow() is not False
    ):
        raise RuntimeError(f"{label}: washer native diameter leader style changed")
    text, fragments, geometry = _diameter_caption(adapter, display, label=label)
    if text.xmin < _face_outline(view)[2] + CLEAR_GAP_M:
        raise RuntimeError(f"{label}: complete washer caption crowds the native face outline")
    for segment in geometry.segments:
        for fragment in fragments:
            if segment.role == "arrow":
                if segment_box_distance(segment, fragment) < CLEAR_GAP_M:
                    raise RuntimeError(f"{label}: native washer arrow crowds its caption")
            elif segment_box_overlap_length(segment, fragment) > 0.0:
                raise RuntimeError(f"{label}: native washer leader crosses its caption")


def _assert_washer_placement(
    adapter: Any, current: Mapping[str, Any], face: Any, expected: _WasherPlacement,
) -> None:
    display = _early_bound(current[THICKNESS], "IDisplayDimension")
    actual = measure_reference_text(adapter, display, axis=1, label=THICKNESS)
    assert_reference_text_stations(
        {"tips": expected.tips, "witnesses": expected.witnesses}, actual, label=THICKNESS,
    )
    if display.OffsetText is not True or actual["text"].ymin < actual["reach"] + CLEAR_GAP_M:
        raise RuntimeError("washer thickness text crowds its native line")
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    if abs(_placement_position(annotation, label=THICKNESS)[0] - expected.thickness_x) > _PLACEMENT_TOLERANCE_M:
        raise RuntimeError("washer thickness transverse position moved")
    if dist(_face_outline(face), expected.face_outline) > _PLACEMENT_TOLERANCE_M:
        raise RuntimeError("washer face outline moved after native caption placement")
    for label, position in expected.diameter_positions:
        display = _early_bound(current[label], "IDisplayDimension")
        _assert_diameter_placement(adapter, display, face, label=label)
        if dist(
            _placement_position(_early_bound(display.GetAnnotation(), "IAnnotation"), label=label),
            position,
        ) > _PLACEMENT_TOLERANCE_M:
            raise RuntimeError(f"{label}: native washer caption position moved")


_WASHER_ORIENTATIONS = frozenset(("*Front", "*Top", "*Right", "*Isometric"))


def _native_path(value: Any, *, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"{label}: native document path is missing")
    return Path(value).resolve()


def _saved_washer_identity(model: Any, path: Path) -> Any:
    model = _early_bound(model, "IModelDoc2")
    if _native_path(model.GetPathName(), label="saved washer drawing") != path:
        raise RuntimeError("saved washer drawing resolved to another document path")
    if type(kind := model.GetType()) is not int or kind != 3:  # swDocDRAWING
        raise RuntimeError("saved washer drawing is not a native drawing document")
    return model


def _saved_display_readback(display: Any) -> dict[str, Any]:
    """Read telemetry independently of strict predicates; never repair a field."""
    result: dict[str, Any] = {"source_native_identity": None}
    native = annotation = tolerance = None
    try:
        native = _early_bound(display.GetDimension2(0), "IDimension")
    except Exception as error:
        result["native_dimension_read_error"] = f"{type(error).__name__}: {error}"
    try:
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    except Exception as error:
        result["annotation_read_error"] = f"{type(error).__name__}: {error}"
    try:
        tolerance = _early_bound(native.Tolerance, "IDimensionTolerance")
    except Exception as error:
        result["tolerance_read_error"] = f"{type(error).__name__}: {error}"
    for field, read in (
        ("selection_name", lambda: display.GetNameForSelection()),
        ("full_name", lambda: native.FullName),
        ("system_value", lambda: native.SystemValue),
        ("units", lambda: display.GetUnits()),
        ("precision", lambda: display.GetPrimaryPrecision2()),
        ("tolerance_precision", lambda: display.GetPrimaryTolPrecision2()),
        ("prefix", lambda: display.GetText(1)),
        ("suffix", lambda: display.GetText(2)),
        ("below", lambda: display.GetText(4)),
        ("use_document_units", lambda: display.GetUseDocUnits()),
        ("fraction_base", lambda: display.GetFractionBase()),
        ("fraction_value", lambda: display.GetFractionValue()),
        ("round_to_fraction", lambda: display.GetRoundToFraction()),
        ("parentheses", lambda: display.ShowParenthesis),
        ("override", lambda: display.GetOverride()),
        ("show_value", lambda: display.ShowDimensionValue),
        ("attachment_count", lambda: annotation.GetAttachedEntityCount3()),
        ("attachment_types", lambda: list(annotation.GetAttachedEntityTypes() or ())),
        ("dangling", lambda: annotation.IsDangling()),
        ("annotation_position", lambda: annotation.GetPosition()),
        ("native_display", lambda: annotation_display(None, annotation)),
        ("offset_text", lambda: display.OffsetText if display.Type2 in (2, 11, 12) else None),
        ("diametric", lambda: display.Diametric if display.Type2 == 6 else None),
        ("arrow_side", lambda: display.ArrowSide if display.Type2 == 6 else None),
        ("solid_leader", lambda: display.SolidLeader if display.Type2 == 6 else None),
        ("use_document_broken_leader", lambda: display.GetUseDocBrokenLeader() if display.Type2 == 6 else None),
        ("broken_leader", lambda: display.GetBrokenLeader2() if display.Type2 == 6 else None),
        ("use_document_second_arrow", lambda: display.GetUseDocSecondArrow() if display.Type2 == 6 else None),
        ("second_arrow", lambda: display.GetSecondArrow() if display.Type2 == 6 else None),
        ("tolerance_type", lambda: tolerance.Type),
        ("tolerance_min", lambda: tolerance.GetMinValue() if tolerance.Type else None),
        ("tolerance_max", lambda: tolerance.GetMaxValue() if tolerance.Type else None),
    ):
        try:
            result[field] = read()
        except Exception as error:
            result[field] = {"read_error": f"{type(error).__name__}: {error}"}
    return result


def _supplier_washer_proof(
    adapter: Any, views: dict[str, Any], references: tuple[_WasherReference, ...], *,
    axis: Literal["y", "z"], bore_mm: float, outer_mm: float, thickness_mm: float,
    units: Literal["in", "mm"], precision: Mapping[str, int],
    bands: Mapping[str, tuple[float, float, str]],
) -> SupplierWasherProof:
    """Capture source path/configurations before the authoring views close.

    The saved reader never activates, rebuilds, dresses or saves a document.
    Only the drawing it opens is closed; the builder owns source preservation.
    """
    if set(views) != _WASHER_ORIENTATIONS:
        raise RuntimeError("supplier washer proof requires exactly four standard views")
    source = _early_bound(views["*Front"], "IView").ReferencedDocument
    if source is None:
        raise RuntimeError("supplier washer proof has no authoring source part")
    source = _early_bound(source, "IModelDoc2")
    source_path = _native_path(source.GetPathName(), label="authoring washer source")
    if type(kind := source.GetType()) is not int or kind != 1:  # swDocPART
        raise RuntimeError("supplier washer proof source is not a native part")
    configurations: dict[str, str] = {}
    for orientation, raw in views.items():
        view = _early_bound(raw, "IView")
        model = view.ReferencedDocument
        configuration = view.ReferencedConfiguration
        identity = None if model is None else adapter.swApp.IsSame(model, source)
        if (
            view.GetOrientationName() != orientation
            or type(identity) is not int or identity != 1
            or _native_path(view.GetReferencedModelName(), label=orientation) != source_path
            or not isinstance(configuration, str) or not configuration.strip()
        ):
            raise RuntimeError(f"{orientation}: authoring washer source/view identity differs")
        configurations[orientation] = configuration
    # The saved callback retains only scalar reference expectations, never an
    # authoring IView or source COM handle that closing the drawing may unload.
    saved_references = tuple(
        (_early_bound(reference.view, "IView").GetOrientationName(),
         reference.label, reference.expected_mm, reference.imported, reference.callout,
         reference.full_name if reference.imported else None)
        for reference in references
    )
    if any(reference[0] not in configurations for reference in saved_references):
        raise RuntimeError("supplier washer reference has no captured standard orientation")
    # Freeze expectations independently of both caller mappings and reopened state.
    precision, bands = dict(precision), dict(bands)

    def reacquire() -> dict[str, Any]:
        # Every core phase first repeats the original complete three-reference
        # source/body/rim/value/band/presentation proof against captured context.
        if set(views) != _WASHER_ORIENTATIONS:
            raise RuntimeError("authoring washer standard view census changed during placement")
        if (
            _native_path(source.GetPathName(), label="authoring washer source") != source_path
            or type(source.GetType()) is not int or source.GetType() != 1
        ):
            raise RuntimeError("authoring washer source path/type changed during placement")
        for orientation, raw in views.items():
            view = _early_bound(raw, "IView")
            model = view.ReferencedDocument
            identity = None if model is None else adapter.swApp.IsSame(model, source)
            if (
                view.GetOrientationName() != orientation
                or type(identity) is not int or identity != 1
                or _native_path(view.GetReferencedModelName(), label=orientation) != source_path
                or view.ReferencedConfiguration != configurations[orientation]
            ):
                raise RuntimeError(f"{orientation}: authoring washer source/view identity changed during placement")
        return assert_supplier_washer_dimensions(
            adapter, views, references, axis=axis, bore_mm=bore_mm,
            outer_mm=outer_mm, thickness_mm=thickness_mm, units=units,
            precision=precision, bands=bands,
        )

    reacquire()
    thickness_name = next(reference.full_name for reference in references if reference.label == THICKNESS)

    def reacquire_thickness() -> dict[str, Any]:
        return {thickness_name: reacquire()[THICKNESS]}

    shelf_check = shelve_reference_text(
        adapter, reacquire=reacquire_thickness, axes={thickness_name: 1},
        label="supplier washer thickness", force=(thickness_name,),
    )
    face_orientation = "*Top" if axis == "y" else "*Front"
    face = views[face_orientation]
    current = reacquire()
    for label in (OUTER_DIAMETER, BORE_DIAMETER):
        set_near_side_diameter(current[label].GetAnnotation(), label)
    rebuild_drawing(adapter, label="supplier washer native diameter leaders")
    current = reacquire()
    right = _face_outline(face)[2]
    moved = False
    for label in (OUTER_DIAMETER, BORE_DIAMETER):
        display = _early_bound(current[label], "IDisplayDimension")
        text, _fragments, geometry = _diameter_caption(adapter, display, label=label)
        arrow_right = max(
            coordinate for segment in geometry.segments if segment.role == "arrow"
            for coordinate in (segment.x0, segment.x1)
        )
        dx = max(0.0, max(right, arrow_right) + CLEAR_GAP_M + PLACE_SETTLE_M - text.xmin)
        if dx:
            annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
            x, y, z = _placement_position(annotation, label=label)
            if annotation.SetPosition2(x + dx, y, z) is not True:
                raise RuntimeError(f"{label}: native washer caption move was rejected")
            moved = True
    if moved:
        rebuild_drawing(adapter, label="supplier washer complete diameter captions")
    current = reacquire()
    shelf_check()
    thickness = measure_reference_text(adapter, current[THICKNESS], axis=1, label=THICKNESS)
    placement = _WasherPlacement(
        tips=tuple(tuple(map(float, tip)) for tip in thickness["tips"]),
        witnesses=tuple(tuple(map(float, witness)) for witness in thickness["witnesses"]),
        thickness_x=_placement_position(
            _early_bound(current[THICKNESS].GetAnnotation(), "IAnnotation"), label=THICKNESS,
        )[0],
        face_outline=_face_outline(face),
        diameter_positions=tuple(
            (label, _placement_position(
                _early_bound(current[label].GetAnnotation(), "IAnnotation"), label=label,
            )) for label in (OUTER_DIAMETER, BORE_DIAMETER)
        ),
    )
    _assert_washer_placement(adapter, current, face, placement)

    def settled_check() -> None:
        current = reacquire()
        shelf_check()
        _assert_washer_placement(adapter, current, face, placement)

    @_telemetry.traced("drawing.saved_supplier_washer_dimensions")
    def saved_check(saved_adapter: Any, path: Path) -> None:
        saved_path = Path(path).resolve()
        if saved_path.suffix.lower() != ".slddrw" or not saved_path.is_file():
            raise ValueError("saved washer proof requires an existing native SLDDRW")
        app = _early_bound(saved_adapter.swApp, "ISldWorks")
        path_string = str(saved_path)
        if app.GetOpenDocumentByName(path_string) is not None:
            raise RuntimeError("finalize and close the washer drawing before saved proof")
        # The finalizer has closed this drawing. Drop its adapter-held wrapper
        # before OpenDoc6 so a stale document cannot survive the saved reopen.
        saved_adapter.currentModel = None
        with saved_path.open("rb") as saved_file:
            before = hashlib.file_digest(saved_file, "sha256").hexdigest()
        opened_model = None
        primary: BaseException | None = None
        receipt: dict[str, Any] = dict(
            drawing_path=str(saved_path), sha256=before,
        )
        try:
            try:
                receipt["source_resident_before_open"] = app.GetOpenDocumentByName(str(source_path)) is not None
            except Exception as error:
                receipt["source_resident_before_open"] = {"read_error": f"{type(error).__name__}: {error}"}
                raise
            # Generated OpenDoc6 appends the two native [out] LONGs. No BYREF
            # variants, ViewOnly/detailing mode, activation or fresh adapter model.
            opened = app.OpenDoc6(path_string, 3, 1 | 2, "", 0, 0)
            if not isinstance(opened, tuple) or len(opened) != 3:
                raise RuntimeError("saved washer OpenDoc6 did not return (model, errors, warnings)")
            opened_model, errors, warnings = opened
            receipt.update(open_errors=errors, open_warnings=warnings)
            if type(errors) is not int or type(warnings) is not int:
                raise RuntimeError("saved washer OpenDoc6 returned non-native error/warning codes")
            if opened_model is None or errors != 0:
                raise RuntimeError(f"saved washer native open failed ({errors=}, {warnings=})")
            model = _saved_washer_identity(opened_model, saved_path)
            read_only = model.IsOpenedReadOnly()
            receipt["read_only"] = read_only
            if read_only is not True:
                raise RuntimeError("saved washer drawing did not open read-only")
            # Closing the finalizer's drawing can unload its hidden source.
            # The saved drawing autoloads that source; reacquire its live model
            # from the captured path, never from a view or an old COM handle.
            try:
                loaded_source = app.GetOpenDocumentByName(str(source_path))
            except Exception as error:
                receipt["source_context_read_error"] = f"{type(error).__name__}: {error}"
                raise
            if loaded_source is None:
                raise RuntimeError("saved washer source context was not loaded by the drawing")
            loaded_source = _early_bound(loaded_source, "IModelDoc2")
            try:
                receipt["source_path"] = loaded_source.GetPathName()
            except Exception as error:
                receipt["source_path"] = {"read_error": f"{type(error).__name__}: {error}"}
                raise
            if _native_path(receipt["source_path"], label="saved washer source") != source_path:
                raise RuntimeError("saved washer source path changed")
            try:
                receipt["source_type"] = kind = loaded_source.GetType()
            except Exception as error:
                receipt["source_type"] = {"read_error": f"{type(error).__name__}: {error}"}
                raise
            if type(kind) is not int or kind != 1:
                raise RuntimeError("saved washer source context is not a native part")
            try:
                receipt["source_read_only"] = loaded_source.IsOpenedReadOnly()
            except Exception as error:
                receipt["source_read_only"] = {"read_error": f"{type(error).__name__}: {error}"}
                raise
            if receipt["source_read_only"] is not True:
                raise RuntimeError("saved washer source context is not read-only")
            try:
                receipt["source_save_flag"] = loaded_source.GetSaveFlag()
            except Exception as error:
                receipt["source_save_flag"] = {"read_error": f"{type(error).__name__}: {error}"}
                raise
            if receipt["source_save_flag"] is not False:
                raise RuntimeError("saved washer source context is dirty or has an unreadable save flag")
            # MaterialIdName describes the currently active source configuration.
            # Record the actual freshly reacquired native value, never the
            # catalogue input or apply_material's returned input echo.
            try:
                with source_path.open("rb") as source_file:
                    receipt["source_sha256"] = hashlib.file_digest(source_file, "sha256").hexdigest()
            except Exception as error:
                receipt["source_sha256"] = {"read_error": f"{type(error).__name__}: {error}"}
                raise
            receipt["source_active_configuration_member"] = (
                "IModelDoc2.ConfigurationManager.ActiveConfiguration.Name"
            )
            try:
                manager = _early_bound(loaded_source.ConfigurationManager, "IConfigurationManager")
                configuration = _early_bound(manager.ActiveConfiguration, "IConfiguration")
                receipt["source_active_configuration"] = configuration.Name
            except Exception as error:
                receipt["source_active_configuration"] = {"read_error": f"{type(error).__name__}: {error}"}
                raise
            if (
                not isinstance(receipt["source_active_configuration"], str)
                or not receipt["source_active_configuration"].strip()
            ):
                raise RuntimeError("saved washer source active configuration name is missing or non-string")
            receipt["source_material_member"] = "IPartDoc.MaterialIdName"
            try:
                material = _early_bound(loaded_source, "IPartDoc").MaterialIdName
            except Exception as error:
                receipt["source_material_read_error"] = f"{type(error).__name__}: {error}"
                raise
            receipt["source_material_raw"] = material
            receipt["source_material_return_type"] = f"{type(material).__module__}.{type(material).__qualname__}"
            if not isinstance(material, str) or not material.strip():
                raise RuntimeError("saved washer native material readback is missing, empty or non-string")
            sheets = tuple(_early_bound(model, "IDrawingDoc").GetViews() or ())
            if len(sheets) != 1:
                raise RuntimeError("saved washer drawing must contain exactly one sheet")
            sheet_views = tuple(sheets[0] or ())
            if len(sheet_views) != 5:  # first IView is the sheet, not a model view
                raise RuntimeError("saved washer drawing must contain exactly four model views")
            fresh: dict[str, Any] = {}
            view_receipts = []
            for raw in sheet_views[1:]:
                view = _early_bound(raw, "IView")
                orientation = view.GetOrientationName()
                if orientation not in configurations or orientation in fresh:
                    raise RuntimeError("saved washer view orientation is unexpected or duplicated")
                referenced = view.ReferencedDocument
                identity = None if referenced is None else app.IsSame(referenced, loaded_source)
                if type(identity) is not int or identity != 1:
                    raise RuntimeError(f"{orientation}: saved washer references another source identity")
                actual_path = _native_path(
                    _early_bound(referenced, "IModelDoc2").GetPathName(), label=orientation,
                )
                named_path = _native_path(view.GetReferencedModelName(), label=orientation)
                configuration = view.ReferencedConfiguration
                if actual_path != source_path or named_path != source_path:
                    raise RuntimeError(f"{orientation}: saved washer references another source path")
                if configuration != configurations[orientation]:
                    raise RuntimeError(f"{orientation}: saved washer source configuration changed")
                fresh[orientation] = view
                view_receipts.append(dict(
                    orientation=orientation, source_path=str(actual_path),
                    configuration=configuration, source_native_identity=identity,
                ))
            if set(fresh) != _WASHER_ORIENTATIONS:
                raise RuntimeError("saved washer standard view census differs")
            # SaveAs can rename a drawing-owned dimension's model component.
            # Rebind by source semantics or exact physical attachment, never by
            # the old document's names, displayed value or presentation text.
            displays = {orientation: _visible_dimensions(view)
                        for orientation, view in fresh.items()}
            receipt["views"] = view_receipts
            receipt["dimensions"] = []
            readbacks = {}
            for orientation, visible in displays.items():
                for display in visible:
                    row = _saved_display_readback(display)
                    row["orientation"] = orientation
                    receipt["dimensions"].append(row)
                    readbacks[id(display)] = row  # Telemetry index, not native identity proof.
            rim_scans: dict[str, ViewEdges] = {}
            fresh_references = []
            for orientation, label, expected_mm, imported, callout, source_full_name in saved_references:
                view = fresh[orientation]
                matches = []
                if imported:
                    feature_name, source_name = SOURCE_DIMENSIONS[label]
                    feature = _early_bound(loaded_source, "IPartDoc").FeatureByName(feature_name)
                    if feature is None:
                        raise RuntimeError(f"{label}: saved supplier source feature is missing")
                    source_display, source_native = _named_dimensions(
                        saved_adapter, feature_name, {source_name}, feature=feature,
                    )[source_name]
                    source_row = _saved_display_readback(source_display)
                    source_row["label"] = label
                    receipt.setdefault("source_dimensions", []).append(source_row)
                    _assert_supplier_washer_presentation(
                        source_display, label=label, units=units, precision=precision[label],
                        expected_mm=expected_mm, callout=callout,
                    )
                    if str(source_native.FullName or "") != source_full_name:
                        raise RuntimeError(f"{label}: saved supplier native source full name changed")
                    for display in displays[orientation]:
                        raw = display.GetDimension2(0)
                        if raw is not None and str(
                            _early_bound(raw, "IDimension").FullName or ""
                        ).split("@")[:2] == [source_name, feature_name]:
                            native_identity = app.IsSame(raw, source_native)
                            readbacks[id(display)]["source_native_identity"] = native_identity
                            if type(native_identity) is not int or native_identity != 1:
                                raise RuntimeError(
                                    f"{label}: saved imported dimension is not its actual native source"
                                )
                            matches.append(display)
                else:
                    if orientation not in rim_scans:
                        rim_scans[orientation] = scan_view_edges(
                            view, label="saved supplier washer semantic rim lookup",
                        )
                    rim = _rim(
                        rim_scans[orientation], axis=axis, station_mm=thickness_mm,
                        diameter_mm=expected_mm, label=label,
                    )
                    for display in displays[orientation]:
                        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
                        attached = tuple(annotation.GetAttachedEntities3() or ())
                        if (
                            len(attached) == 1 and attached[0] is not None
                            and _is_same_attachment(saved_adapter, attached[0], rim, "EDGE")
                        ):
                            matches.append(display)
                if len(matches) != 1:
                    raise RuntimeError(
                        f"{label}: saved semantic native display census failed "
                        f"(found {len(matches)}, expected one)"
                    )
                fresh_reference = _reference(
                    matches[0], view, label, expected_mm,
                    imported=imported, callout=callout,
                )
                fresh_references.append(fresh_reference)
            current = assert_supplier_washer_dimensions(
                saved_adapter, fresh, tuple(fresh_references), axis=axis, bore_mm=bore_mm,
                outer_mm=outer_mm, thickness_mm=thickness_mm, units=units,
                precision=precision, bands=bands,
            )
            _assert_washer_placement(saved_adapter, current, fresh[face_orientation], placement)
        except BaseException as error:
            primary = error
            raise
        finally:
            cleanup_errors = []
            try:
                loaded = app.GetOpenDocumentByName(path_string)
                if loaded is not None:
                    loaded = _saved_washer_identity(loaded, saved_path)
                    identity = None if opened_model is None else app.IsSame(loaded, opened_model)
                    if opened_model is not None and (type(identity) is not int or identity != 1):
                        raise RuntimeError("saved washer cleanup refuses a different loaded identity")
                    title = loaded.GetTitle()
                    if not isinstance(title, str) or not title.strip():
                        raise RuntimeError("saved washer cleanup refuses an empty document title")
                    app.CloseDoc(title)  # VT_VOID, closes only this invocation's target
                    if app.GetOpenDocumentByName(path_string) is not None:
                        raise RuntimeError("saved washer proof document did not close")
            except Exception as error:
                cleanup_errors.append(error)
            try:
                with saved_path.open("rb") as saved_file:
                    after = hashlib.file_digest(saved_file, "sha256").hexdigest()
                receipt["sha256_after"] = after
                if after != before:
                    raise RuntimeError("saved washer proof changed the native drawing bytes")
            except Exception as error:
                cleanup_errors.append(error)
            if primary is not None:
                primary.add_note("saved washer native readback: " + json.dumps(
                    receipt, sort_keys=True, default=repr,
                ))
            if cleanup_errors:
                if primary is not None:
                    for error in cleanup_errors:
                        primary.add_note(f"saved washer cleanup: {type(error).__name__}: {error}")
                else:
                    error = cleanup_errors[0]
                    for extra in cleanup_errors[1:]:
                        error.add_note(f"saved washer cleanup: {type(extra).__name__}: {extra}")
                    error.add_note("saved washer native readback: " + json.dumps(
                        receipt, sort_keys=True, default=repr,
                    ))
                    raise error
        _telemetry.info("supplier washer saved native proof: " + json.dumps(
            receipt, sort_keys=True, default=repr,
        ))

    return SupplierWasherProof(settled_check, saved_check)


@_telemetry.traced("drawing.supplier_washer_dimensions")
def supplier_washer_dimensions(
    adapter: Any, views: dict[str, Any], *, axis: Literal["y", "z"],
    bore_mm: float, outer_mm: float, thickness_mm: float, units: Literal["in", "mm"],
    precision: Mapping[str, int], bands: Mapping[str, tuple[float, float, str]],
    bore_callout: str | None = None,
) -> SupplierWasherProof:
    """Import every banded size; author only bandless OD/ID physical refs."""
    if set(bands) not in ({THICKNESS}, {OUTER_DIAMETER, BORE_DIAMETER, THICKNESS}):
        raise ValueError("unsupported washer supplier band coverage")
    face = views["*Top" if axis == "y" else "*Front"]
    side = views["*Front" if axis == "y" else "*Top"]
    bounds = tuple(float(value) for value in face.GetOutline())
    center_y = (bounds[1] + bounds[3]) / 2.0
    positions = {
        OUTER_DIAMETER: (bounds[2] + 0.012, center_y + 0.012),
        BORE_DIAMETER: (bounds[2] + 0.012, center_y - 0.012),
    }
    side_bounds = tuple(float(value) for value in side.GetOutline())
    positions[THICKNESS] = (side_bounds[2] + 0.014, (side_bounds[1] + side_bounds[3]) / 2.0)
    values = {OUTER_DIAMETER: outer_mm, BORE_DIAMETER: bore_mm, THICKNESS: thickness_mm}
    references: list[_WasherReference] = []
    for view, labels in ((face, (OUTER_DIAMETER, BORE_DIAMETER)), (side, (THICKNESS,))):
        imported_labels = tuple(label for label in labels if label in bands)
        if not imported_labels:
            continue
        annotations = curate_view_dimensions(
            adapter, view,
            keep={SOURCE_DIMENSIONS[label][1]: positions[label] for label in imported_labels},
            view_label="supplier washer face" if view is face else "supplier washer thickness",
            dimensions_by_feature={
                SOURCE_DIMENSIONS[label][0]: tuple(SOURCE_DIMENSIONS[item][1]
                                                  for item in imported_labels
                                                  if SOURCE_DIMENSIONS[item][0] == SOURCE_DIMENSIONS[label][0])
                for label in imported_labels
            },
        )
        named = {dimension_name(adapter, annotation): annotation for annotation in annotations}
        for label in imported_labels:
            annotation = named[SOURCE_DIMENSIONS[label][1]]
            display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
            _persist_imported_units(
                adapter, view, display, label=label, units=units,
                precision=precision[label], expected_mm=values[label],
                callout=bore_callout if label == BORE_DIAMETER else None,
            )
            references.append(_reference(display, view, label, values[label], imported=True,
                                         callout=bore_callout if label == BORE_DIAMETER else None))
    unbanded = tuple(label for label in (OUTER_DIAMETER, BORE_DIAMETER) if label not in bands)
    if unbanded:
        edges = scan_view_edges(face, label="supplier washer unbanded face rims")
        for label in unbanded:
            rim = _rim(edges, axis=axis, station_mm=thickness_mm,
                       diameter_mm=values[label], label=label)
            display = _native_diameter(adapter, face, rim, text_xy=positions[label], label=label)
            display = supplier_reference_dimension(
                adapter, display, label=label, units=units, precision=precision[label],
                expected_mm=values[label], presentation="diameter",
                callout=bore_callout if label == BORE_DIAMETER else None,
            )
            references.append(_reference(display, face, label, values[label], imported=False,
                                         callout=bore_callout if label == BORE_DIAMETER else None))

    return _supplier_washer_proof(
        adapter, views, tuple(references), axis=axis, bore_mm=bore_mm,
        outer_mm=outer_mm, thickness_mm=thickness_mm, units=units,
        precision=precision, bands=bands,
    )
