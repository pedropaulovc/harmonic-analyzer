"""Physical hex references and an honest nominal-thread carrier for purchased nuts.

Across flats and height measure the unchanged solid. The plain bore is checked
against its original recipe, never labelled as a manufactured thread. A hidden
model-owned construction chord carries the independent nominal major size and
its below-value thread designation through the shared supplier importer.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from _com import _bind, _early_bound
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import ViewEdge, scan_view_edges
from _drawing_precision import _named_dimensions
from _drawing_projection import model_points_in_view
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
from _supplier_reference_text import shelve_reference_text
from _supplier_screw_dimensions import (
    _assert_dimension_source,
    _attachment_correspondence,
    annotate_supplier_screw,
)
from _supplier_screw_reference_names import FEATURE_BY_PLANE
import _telemetry


_NOMINAL_MAJOR = "ThreadNominalMajor"


def _reference_between_edges(
    adapter: Any,
    view: Any,
    edges: tuple[ViewEdge, ViewEdge],
    *,
    text_xy: tuple[float, float],
    expected_mm: float,
    precision: int,
    label: str,
    fraction_denominator: int | None = None,
    callout: str | None = None,
) -> str:
    picks = model_points_in_view(
        adapter,
        view,
        [tuple(value / 1000.0 for value in edge.midpoint_mm) for edge in edges],
        label=label,
    )
    entities = (edges[0].edge, edges[1].edge)
    display = add_edge_dimension(
        adapter,
        view,
        p0=picks[0],
        p1=picks[1],
        text_xy=text_xy,
        label=label,
        orientation="horizontal",
        entities=entities,
    )
    supplier_reference_dimension(
        adapter,
        display,
        label=label,
        units="in",
        precision=precision,
        expected_mm=expected_mm,
        fraction_denominator=fraction_denominator,
        callout=callout,
    )
    assert_dimension_measures(
        adapter,
        display,
        expected_mm=expected_mm,
        label=label,
        entities=entities,
    )
    return str(_early_bound(display.GetDimension2(0), "IDimension").FullName)


def _physical_edges(
    front: Any,
    right: Any,
    *,
    across_flats_mm: float,
    thickness_mm: float,
    bore_diameter_mm: float,
) -> tuple[tuple[ViewEdge, ViewEdge], tuple[ViewEdge, ViewEdge]]:
    front_edges = scan_view_edges(front, label="supplier nut front")
    right_edges = scan_view_edges(right, label="supplier nut right")
    half_width = across_flats_mm / 2.0
    flats = tuple(
        front_edges.exact_line_through(
            (x, 0.0, thickness_mm), label="supplier nut opposing flat"
        )
        for x in (-half_width, half_width)
    )
    ends = tuple(
        right_edges.exact_line_through(
            (half_width, 0.0, z), label="supplier nut end face"
        )
        for z in (0.0, thickness_mm)
    )
    # This independent solid check deliberately uses the original bore size,
    # which can differ from the exact customary nominal-major reference.
    front_edges.circle_at(
        (0.0, 0.0, thickness_mm),
        bore_diameter_mm / 2.0,
        axis=(0.0, 0.0, 1.0),
        label="supplier nut unchanged plain bore",
        center_tol_mm=1e-6,
        radius_tol_mm=1e-6,
    )
    return flats, ends


def _assert_nominal_carrier(
    adapter: Any, front: Any, display: Any, nominal_major_mm: float
) -> dict[str, Any]:
    """Prove the exact source chord and both distinct view-mapped endpoints."""
    model = _early_bound(front, "IView").ReferencedDocument
    if model is None:
        raise RuntimeError("supplier nut has no referenced source part")
    feature_name = FEATURE_BY_PLANE["Front"]
    raw = _early_bound(model, "IPartDoc").FeatureByName(feature_name)
    if raw is None:
        raise RuntimeError("supplier nut nominal-major source sketch is missing")
    feature = _early_bound(raw, "IFeature")
    sketch = _early_bound(feature.GetSpecificFeature2(), "ISketch")
    source_display, source_native = _named_dimensions(
        adapter, feature_name, {_NOMINAL_MAJOR}, feature=feature
    )[_NOMINAL_MAJOR]
    native = _early_bound(display.GetDimension2(0), "IDimension")
    owner = native.GetFeatureOwner()
    if (
        str(native.FullName).split("@")[:2] != [_NOMINAL_MAJOR, feature_name]
        or str(source_native.FullName).split("@")[:2] != [_NOMINAL_MAJOR, feature_name]
        or owner is None
        or int(adapter.swApp.IsSame(owner, feature)) != 1
        or int(display.Type2) != int(source_display.Type2)
        or int(display.Type2) not in (2, 11, 12)
        or int(_early_bound(native.Tolerance, "IDimensionTolerance").Type) != 0
    ):
        raise RuntimeError("supplier nut nominal-major dimension lost its native source owner")
    segments = tuple(sketch.GetSketchSegments() or ())
    if len(segments) != 1:
        raise RuntimeError("supplier nut nominal-major source must contain one chord")
    segment = _early_bound(segments[0], "ISketchSegment")
    if int(segment.GetType()) != 0 or segment.ConstructionGeometry is not True:
        raise RuntimeError("supplier nut nominal-major carrier is not a construction line")
    line = _early_bound(segment, "ISketchLine")
    points = (line.GetStartPoint2(), line.GetEndPoint2())
    for raw_point, x in zip(points, (-nominal_major_mm / 2000.0, nominal_major_mm / 2000.0), strict=True):
        if raw_point is None:
            raise RuntimeError("supplier nut nominal-major chord has no endpoint")
        point = _early_bound(raw_point, "ISketchPoint")
        if not all(
            math.isclose(float(getattr(point, axis)), expected, rel_tol=0.0, abs_tol=1e-10)
            for axis, expected in zip(("X", "Y", "Z"), (x, 0.0, 0.0), strict=True)
        ):
            raise RuntimeError("supplier nut nominal-major chord differs from its exact source")
    # Compare chord endpoints with the inventory in model context only. The
    # drawing attachments are different objects; compare those with the complete
    # view-mapped inventory using the importer's positive and negative controls.
    source_points = list(sketch.GetSketchPoints2() or ())
    for point in points:
        matches = [index for index, entity in enumerate(source_points)
                   if entity is not None and int(adapter.swApp.IsSame(entity, point)) == 1]
        if len(matches) != 1:
            raise RuntimeError("supplier nut nominal-major source inventory lost a chord endpoint")
        source_points.pop(matches[0])
    if source_points:
        raise RuntimeError("supplier nut nominal-major source has unexpected sketch points")
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    attached = tuple(annotation.GetAttachedEntities3() or ())
    types = tuple(int(kind) for kind in (annotation.GetAttachedEntityTypes() or ()))
    if len(attached) != 2 or types != (11, 11):  # swSelSKETCHPOINTS
        raise RuntimeError("supplier nut nominal-major carrier requires both endpoint attachments")
    correspondence = _attachment_correspondence(
        adapter, _early_bound(front, "IView"),
        source_sketch=sketch, entities=attached, types=types,
    )
    if not correspondence["proven"]:
        raise RuntimeError(
            "supplier nut nominal-major attachment is not its view-mapped source endpoint: "
            + json.dumps(correspondence, sort_keys=True)
        )
    return correspondence


@_telemetry.traced("drawing.supplier_nut_saved_readback")
def assert_saved_supplier_nut_nominal(
    adapter: Any,
    drawing_path: Path,
    *,
    nominal_major_mm: float,
    source_path: Path,
    configuration: str,
) -> None:
    """Cold-read the saved drawing without saving or changing its source binding.

    ``configuration`` is captured from the original authoring Front view and
    preserved by the purchased wrapper's settled binding check. It proves
    persistence of that binding, not an independent catalogue configuration.
    """
    drawing_path = Path(drawing_path).resolve()
    source_path = Path(source_path).resolve()
    if drawing_path.suffix.lower() != ".slddrw" or not drawing_path.is_file():
        raise ValueError("supplier nut saved readback requires an existing SLDDRW")
    if not isinstance(configuration, str) or not configuration.strip():
        raise ValueError("supplier nut saved readback requires the original configuration")
    app = _early_bound(adapter.swApp, "ISldWorks")
    if app.GetOpenDocumentByName(str(drawing_path)) is not None:
        raise RuntimeError("supplier nut saved drawing must be closed before readback")
    with drawing_path.open("rb") as stream:
        before_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    primary: BaseException | None = None
    acquired: Any = None
    try:
        adapter.currentModel = None  # Release the finalizer's closed drawing handle.
        # Strict _early_bound guarantees makepy: [out] I4 values ride the return
        # tuple. Explicit BYREF VARIANTs would remain unwritten in this binding.
        opened = app.OpenDoc6(str(drawing_path), 3, 1 | 2, "", 0, 0)
        if not isinstance(opened, tuple) or len(opened) != 3:
            raise RuntimeError("supplier nut saved drawing open returned unreadable status")
        raw, errors, warnings = opened
        acquired = raw
        if type(errors) is not int or type(warnings) is not int:
            raise RuntimeError("supplier nut saved drawing open status is not native integer")
        if raw is None or errors != 0:
            raise RuntimeError(f"supplier nut saved drawing open failed ({errors=}, {warnings=})")
        draw = _early_bound(raw, "IModelDoc2")
        drawing_kind = draw.GetType()
        if (
            type(drawing_kind) is not int or drawing_kind != 3
            or Path(draw.GetPathName()).resolve() != drawing_path
            or draw.IsOpenedReadOnly() is not True
        ):
            raise RuntimeError("supplier nut saved readback acquired the wrong drawing")
        loaded = app.GetOpenDocumentByName(str(drawing_path))
        identity = None if loaded is None else app.IsSame(draw, loaded)
        if type(identity) is not int or identity != 1:
            raise RuntimeError("supplier nut saved drawing lost its loaded native identity")
        adapter.currentModel = draw
        # Closing a drawing can release hidden references; reopen before lookup.
        source = app.GetOpenDocumentByName(str(source_path))
        if source is None:
            raise RuntimeError("supplier nut saved readback lost its immutable source part")
        source = _early_bound(source, "IModelDoc2")
        source_kind = source.GetType()
        if (
            type(source_kind) is not int or source_kind != 1
            or Path(source.GetPathName()).resolve() != source_path
            or source.IsOpenedReadOnly() is not True
        ):
            raise RuntimeError("supplier nut saved readback has the wrong source part")
        sheets = tuple(_early_bound(draw, "IDrawingDoc").GetViews() or ())
        if len(sheets) != 1:
            raise RuntimeError("supplier nut saved drawing must have one sheet")
        views = [_early_bound(view, "IView") for view in tuple(sheets[0])[1:]]
        fronts = [view for view in views if str(view.GetOrientationName()) == "*Front"]
        if len(fronts) != 1:
            raise RuntimeError("supplier nut saved drawing must have one Front view")
        front = fronts[0]
        referenced = front.ReferencedDocument
        source_identity = None if referenced is None else app.IsSame(referenced, source)
        if (
            Path(front.GetReferencedModelName()).resolve() != source_path
            or str(front.ReferencedConfiguration) != configuration
            or type(source_identity) is not int
            or source_identity != 1
        ):
            raise RuntimeError("supplier nut saved Front changed its source/configuration binding")
        displays = []
        for raw_annotation in front.GetAnnotations() or ():
            annotation = _early_bound(raw_annotation, "IAnnotation")
            if int(annotation.GetType()) != 4:  # swDisplayDimension
                continue
            display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
            native = _early_bound(display.GetDimension2(0), "IDimension")
            if str(native.FullName).split("@")[:2] == [_NOMINAL_MAJOR, FEATURE_BY_PLANE["Front"]]:
                if int(annotation.Visible) != 1:
                    raise RuntimeError("supplier nut saved nominal-major dimension is hidden")
                displays.append(display)
        if len(displays) != 1:
            raise RuntimeError("supplier nut saved drawing lost its unique nominal-major dimension")
        display = displays[0]
        _assert_dimension_source(
            adapter, front, display, name=_NOMINAL_MAJOR, feature=FEATURE_BY_PLANE["Front"],
        )
        correspondence = _assert_nominal_carrier(adapter, front, display, nominal_major_mm)
        value = float(_early_bound(display.GetDimension2(0), "IDimension").SystemValue)
        if not math.isclose(value, nominal_major_mm / 1000.0, rel_tol=0.0, abs_tol=1e-10):
            raise RuntimeError("supplier nut saved nominal-major value changed")
        evidence = {
            "drawing_path": str(drawing_path),
            "source_path": str(source_path),
            "configuration": configuration,
            "nominal_major_mm": value * 1000.0,
            "drawing_sha256": before_hash,
            "open_error_raw": errors,
            "open_warning_raw": warnings,
            "attachment_correspondence": correspondence,
        }
    except BaseException as error:
        primary = error
        raise
    finally:
        cleanup_errors: list[BaseException] = []
        try:
            # Only the previously closed target may be ours, including a failed
            # OpenDoc6 that nevertheless loaded it. Never close a foreign model.
            loaded = app.GetOpenDocumentByName(str(drawing_path))
            if loaded is not None:
                loaded = _early_bound(loaded, "IModelDoc2")
                loaded_kind = loaded.GetType()
                if (
                    type(loaded_kind) is not int or loaded_kind != 3
                    or Path(loaded.GetPathName()).resolve() != drawing_path
                ):
                    raise RuntimeError("supplier nut saved readback refuses to close a foreign document")
                identity = 1 if acquired is None else app.IsSame(acquired, loaded)
                if type(identity) is not int or identity != 1:
                    raise RuntimeError("supplier nut saved readback refuses to close a foreign native identity")
                title = loaded.GetTitle()
                if not isinstance(title, str) or not title:
                    raise RuntimeError("supplier nut saved drawing has no closeable title")
                app.CloseDoc(title)  # VT_VOID; never save the readback document.
                if app.GetOpenDocumentByName(str(drawing_path)) is not None:
                    raise RuntimeError("supplier nut saved readback drawing did not close")
        except BaseException as error:
            cleanup_errors.append(error)
        adapter.currentModel = None  # Clear even when native close itself fails.
        try:
            with drawing_path.open("rb") as stream:
                after_hash = hashlib.file_digest(stream, "sha256").hexdigest()
            if after_hash != before_hash:
                raise RuntimeError("supplier nut saved drawing bytes changed during readback")
        except BaseException as error:
            cleanup_errors.append(error)
        if cleanup_errors:
            failure = primary if primary is not None else cleanup_errors[0]
            for error in cleanup_errors:
                if error is not failure:
                    failure.add_note(f"supplier nut saved readback cleanup also failed: {error!r}")
            if primary is None:
                raise failure
    _telemetry.info("supplier_nut_saved_readback_proof " + json.dumps(evidence, sort_keys=True))


@_telemetry.traced("drawing.supplier_nut_dimensions")
def add_supplier_nut_dimensions(
    adapter: Any,
    views_by_orientation: Mapping[str, Any],
    *,
    across_flats_mm: float,
    thickness_mm: float,
    bore_diameter_mm: float,
    thread: str,
    precision: Mapping[str, int],
    fraction_denominator: int,
    reference_dimensions: Sequence[tuple[str, float, str]],
    reference_starts: Mapping[str, tuple[float, float]],
) -> Callable[[], None]:
    """Author AF/height and import the source-owned nominal thread-size carrier.

    Offset each complete native text block beyond its measured arrow tails,
    without moving the physical dimension/witness stations. Return one
    read-only settled proof after the wrapper's final rebuild.
    """
    if len(reference_dimensions) != 1:
        raise ValueError("supplier nut requires one nominal-major source dimension")
    name, nominal_major_mm, orientation = reference_dimensions[0]
    if (
        name != _NOMINAL_MAJOR or orientation != "horizontal"
        or not math.isfinite(nominal_major_mm) or nominal_major_mm <= 0.0
        or dict(reference_starts) != {name: (-nominal_major_mm / 2.0, 0.0)}
    ):
        raise ValueError("supplier nut nominal-major source must be a centred Front chord")
    front = views_by_orientation["*Front"]
    right = views_by_orientation["*Right"]
    front_box = tuple(float(value) for value in front.GetOutline())
    right_box = tuple(float(value) for value in right.GetOutline())
    flats, ends = _physical_edges(
        front, right, across_flats_mm=across_flats_mm,
        thickness_mm=thickness_mm, bore_diameter_mm=bore_diameter_mm,
    )
    nominal_checks: list[Callable[[], None]] = []
    displays = annotate_supplier_screw(
        adapter,
        views_by_orientation,
        dimensions=reference_dimensions,
        starts=reference_starts,
        formats={name: (precision[name], "diameter", None,
                        f"{thread.removeprefix('#')} THREAD\nNOMINAL MAJOR")},
        sides={name: "bottom"},
        settled_checks=nominal_checks,
    )
    nominal_display = displays[name]
    _assert_nominal_carrier(adapter, front, nominal_display, nominal_major_mm)
    nominal_name = str(_early_bound(nominal_display.GetDimension2(0), "IDimension").FullName)
    width_name = _reference_between_edges(
        adapter, front, flats,
        text_xy=((front_box[0] + front_box[2]) / 2.0, front_box[3] + 0.008),
        expected_mm=across_flats_mm,
        precision=precision["AcrossFlats"],
        label="supplier nut across flats",
        fraction_denominator=fraction_denominator,
        callout="ACROSS FLATS",
    )
    height_name = _reference_between_edges(
        adapter, right, ends,
        text_xy=((right_box[0] + right_box[2]) / 2.0, right_box[1] - 0.008),
        expected_mm=thickness_mm,
        precision=precision["Height"],
        label="supplier nut height",
    )
    expected_names = {"*Front": {width_name, nominal_name}, "*Right": {height_name}}
    axes = {native_name: 0 for native_name in (nominal_name, width_name, height_name)}
    if len(axes) != 3:
        raise RuntimeError("supplier nut requires three distinct native dimensions")
    if len(nominal_checks) != 1:
        raise RuntimeError("supplier nut nominal-major proof must be authored exactly once")

    def reacquire() -> dict[str, Any]:
        current: dict[str, Any] = {}
        for orientation, view in views_by_orientation.items():
            names = []
            for raw in _early_bound(view, "IView").GetAnnotations() or ():
                annotation = _early_bound(raw, "IAnnotation")
                if int(annotation.GetType()) != 4:  # swDisplayDimension
                    continue
                if int(annotation.Visible) != 1:  # swAnnotationVisible
                    raise RuntimeError(f"{orientation}: supplier nut dimension is hidden")
                display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
                native_name = str(_early_bound(display.GetDimension2(0), "IDimension").FullName)
                names.append(native_name)
                current[native_name] = display
            required = expected_names.get(orientation, set())
            if len(names) != len(required) or set(names) != required:
                raise RuntimeError(f"{orientation}: supplier nut native dimension inventory changed")
        nominal_checks[0]()
        _assert_nominal_carrier(adapter, front, current[nominal_name], nominal_major_mm)
        settled_flats, settled_ends = _physical_edges(
            front, right, across_flats_mm=across_flats_mm,
            thickness_mm=thickness_mm, bore_diameter_mm=bore_diameter_mm,
        )
        for native_name, edges, expected, places, denominator, callout, label in (
            (width_name, settled_flats, across_flats_mm, precision["AcrossFlats"],
             fraction_denominator, "ACROSS FLATS", "supplier nut across flats"),
            (height_name, settled_ends, thickness_mm, precision["Height"],
             None, None, "supplier nut height"),
        ):
            display = current[native_name]
            assert_supplier_reference_dimension(
                adapter, display, label=label, units="in", precision=places,
                expected_mm=expected, fraction_denominator=denominator, callout=callout,
            )
            assert_dimension_measures(
                adapter, display, expected_mm=expected, label=label,
                entities=(edges[0].edge, edges[1].edge),
            )
        return current

    check_shelves = shelve_reference_text(
        adapter, reacquire=reacquire, axes=axes,
        label="supplier nut reference text", force=axes.keys(),
    )

    @_telemetry.traced("drawing.supplier_nut_settled")
    def assert_settled() -> None:
        check_shelves()

    return assert_settled
