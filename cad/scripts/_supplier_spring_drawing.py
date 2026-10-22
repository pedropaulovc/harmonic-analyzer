"""Nominal supplier diagram/installed-state layout, independent of the four-view builder.

View configurations are assigned before measuring/fitting. Supplier references
never dimension the installed span. The optional maximum view is a construction-only nominal gauge, not a callback inserted behind a four-view contract.
Nominal dimension diagrams are sketch-only configurations, never surrogate parts.
Their actual native curves are captured once before fitting, with the source
configuration restored before projection or annotation callbacks. Existing
view-qualified sketch showing and native dimension import provide presentation;
capture does not infer drawing visibility from a source feature's Visible state.
Unbroken, uncropped full views project the capture in their current frame;
installed pictorials retain their native outline and existing ink guards.
The source is opened read-only and clean. The explicit annotation phase permits
presentation-only dirty state; drawing finalization must preserve source bytes.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from math import isclose, isfinite
from pathlib import Path
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    iter_views,
    place_view,
    view_name,
)

from _com import _bind, _early_bound
import _config
import _telemetry
from _drawing_common import (
    DrawingOutputs,
    assert_asme_b_sheet,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_hidden_sketches import _show_hidden_owners, curate_view_dimensions
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWING_TEMPLATES, DrawingSpec
from _drawing_sheet_region import sheet_drawable_region
from _drawing_view_display import set_hidden_lines_removed
from _purchased_fastener_drawing import (
    _PROPERTIES,
    _SCALES,
    _box,
    _cell,
    _center_marks_without_lines,
    _fit_group,
    _inside,
    _literal_note,
    _open_supplier_source_read_only,
    _purchased_title_block,
    _rebuild,
    _source_file_sha256,
    add_purchased_footer,
    assert_supplier_annotations_fit,
    assert_supplier_view_fits,
    check_item,
    supplier_fit_cells,
    view_band_bottom,
)
from _purchased_part_variants import _suppressed
from _rebuild import active_configuration_name
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
from _supplier_extension_spring import (
    COIL_OD,
    DIMENSIONS_BY_FEATURE,
    FREE_LENGTH,
    MAX_LENGTH,
    SOURCE_FEATURES,
    WIRE_DIA,
)
from _supplier_spring_reference import (
    SUPPLIER_FREE_CONFIGURATION,
    SUPPLIER_MAX_CONFIGURATION,
)
from _supplier_reference_geometry import (
    NativeSketchGeometry,
    capture_native_sketch_geometry,
    native_sketch_view_bounds,
)
from _visibility import FeatureWalk, REFERENCE_FEATURE_KINDS


def reacquire_supplier_dimensions(
    adapter: Any,
    views: Mapping[str, Any],
    *,
    expected: Mapping[str, Mapping[str, str]],
    configurations: Mapping[str, str],
) -> dict[str, Any]:
    """Reacquire the entire native annotation inventory after the final rebuild.

    ``expected`` maps each view key to dimension-name/owner-sketch pairs,
    including empty installed pictorial inventories. No cached display object
    is accepted as proof of its continued presence on the rebuilt sheet.
    """
    rebuilt = {
        view_name(adapter, view): _early_bound(view, "IView")
        for view in iter_views(adapter)
    }
    if set(expected) != set(views):
        raise RuntimeError("supplier final annotation view inventory changed")
    found = {}
    for key, owners in expected.items():
        view = rebuilt.get(view_name(adapter, views[key]))
        if view is None or str(view.ReferencedConfiguration) != configurations[key]:
            raise RuntimeError(
                f"{key}: supplier final native view/configuration changed"
            )
        present = {}
        for raw in view.GetAnnotations() or ():
            annotation = _early_bound(raw, "IAnnotation")
            if int(annotation.GetType()) != 4:  # swDisplayDimension
                continue
            display = _early_bound(
                annotation.GetSpecificAnnotation(), "IDisplayDimension"
            )
            native = display.GetDimension2(0)
            if native is None:
                raise RuntimeError(
                    f"{key}: supplier native annotation lost its dimension"
                )
            identity = str(_early_bound(native, "IDimension").FullName).split("@")
            if (
                len(identity) < 2
                or identity[0] not in owners
                or owners[identity[0]] != identity[1]
            ):
                raise RuntimeError(
                    f"{key}: unexpected supplier dimension owner {identity!r}"
                )
            name = identity[0]
            if name in present or name in found:
                raise RuntimeError(f"{key}: duplicate supplier dimension {name}")
            present[name] = display
            found[name] = display
        if set(present) != set(owners) or int(view.GetDisplayDimensionCount()) != len(
            owners
        ):
            raise RuntimeError(f"{key}: supplier final annotation inventory changed")
    return found


def assert_supplier_configuration_value(
    display: Any,
    configuration: str,
    expected_mm: float,
    *,
    label: str,
) -> None:
    """Read the exact model-owned SI value in the dimension's drawing configuration."""
    native = _early_bound(display.GetDimension2(0), "IDimension")
    values = tuple(native.GetSystemValue3(3, configuration) or ())
    if len(values) != 1 or not isclose(
        float(values[0]),
        expected_mm / 1000.0,
        rel_tol=0.0,
        abs_tol=1e-11,
    ):
        raise RuntimeError(f"{label}: exact configured supplier dimension changed")


def prepare_extension_spring_diagrams(
    adapter: Any,
    views: Mapping[str, Any],
    *,
    reference_bounds: Callable[[str], tuple[float, float, float, float]],
) -> tuple[Callable[[], None], ...]:
    """Show only assigned construction gauges before native geometry fitting."""
    if set(views) != {*SOURCE_FEATURES, "installed_iso"}:
        raise RuntimeError(
            "extension spring diagram needs free, section, maximum and installed views"
        )
    for key, names in SOURCE_FEATURES.items():
        if set(_show_hidden_owners(adapter, views[key], names, view_label=key)) != set(
            names
        ):
            raise RuntimeError(f"{key}: nominal supplier gauges must be saved hidden")
    return ()


def extension_spring_dimensions(
    adapter: Any,
    views: Mapping[str, Any],
    *,
    free_length_mm: float,
    reference_bounds: Callable[[str], tuple[float, float, float, float]],
    max_length_mm: float,
    coil_od_mm: float,
    wire_dia_mm: float,
    precision: Mapping[str, int],
    od_tolerance_mm: float | None = None,
    od_tolerance_precision: int | None = None,
) -> tuple[Callable[[], None], ...]:
    """Import source sizes and reacquire every native dimension after final rebuild."""
    rows_by_view = {
        "free_front": (
            (
                FREE_LENGTH,
                free_length_mm,
                "length",
                "STOCK FREE / INSIDE HOOKS OR LOOPS",
            ),
        ),
        "free_right": (
            (COIL_OD, coil_od_mm, "diameter", "NOMINAL STOCK COIL OD"),
            (WIRE_DIA, wire_dia_mm, "diameter", "NOMINAL STOCK WIRE SECTION"),
        ),
        "max_front": (
            (
                MAX_LENGTH,
                max_length_mm,
                "length",
                "STOCK MAXIMUM / INSIDE HOOKS OR LOOPS",
            ),
        ),
    }
    expected = {key: {} for key in views}
    configurations = {
        key: str(view.ReferencedConfiguration) for key, view in views.items()
    }
    required = {
        "free_front": SUPPLIER_FREE_CONFIGURATION,
        "free_right": SUPPLIER_FREE_CONFIGURATION,
        "max_front": SUPPLIER_MAX_CONFIGURATION,
    }
    for key, configuration in required.items():
        if configurations.get(key) != configuration:
            raise RuntimeError(f"{key}: nominal supplier gauge has wrong configuration")
    settings = {}
    for key, rows in rows_by_view.items():
        view = views[key]
        xmin, ymin, xmax, ymax = reference_bounds(key)
        positions = (
            {
                COIL_OD: (xmax + 0.006, ymax + 0.005),
                WIRE_DIA: (xmax + 0.006, ymin - 0.009),
            }
            if key == "free_right"
            else {rows[0][0]: ((xmin + xmax) / 2, ymax + 0.010)}
        )
        annotations = curate_view_dimensions(
            adapter,
            view,
            keep=positions,
            view_label=key,
            dimensions_by_feature=DIMENSIONS_BY_FEATURE,
        )
        by_name = {
            dimension_name(adapter, annotation): annotation
            for annotation in annotations
        }
        if len(annotations) != len(positions) or set(by_name) != set(positions):
            raise RuntimeError(
                f"{key}: supplier reference inventory differs from source"
            )
        for name, value, presentation, callout in rows:
            owner = next(
                feature
                for feature, names in DIMENSIONS_BY_FEATURE.items()
                if name in names
            )
            expected[key][name] = owner
            arguments = dict(
                label=name,
                units="in",
                precision=precision[name],
                expected_mm=value,
                presentation=presentation,
                callout=callout,
                configuration=configurations[key],
            )
            supplier_reference_dimension(
                adapter,
                _early_bound(
                    by_name[name].GetSpecificAnnotation(), "IDisplayDimension"
                ),
                **arguments,
            )
            settings[name] = (arguments, configurations[key])

    def settled() -> None:
        displays = reacquire_supplier_dimensions(
            adapter,
            views,
            expected=expected,
            configurations=configurations,
        )
        for name, (arguments, configuration) in settings.items():
            display = displays[name]
            # The shared assertion proves native dimension type before SI interpretation.
            assert_supplier_reference_dimension(adapter, display, **arguments)
            assert_supplier_configuration_value(
                display,
                configuration,
                arguments["expected_mm"],
                label=name,
            )
            native = _early_bound(display.GetDimension2(0), "IDimension")
            tolerance = _early_bound(native.Tolerance, "IDimensionTolerance")
            if name == COIL_OD and od_tolerance_mm is not None:
                if (
                    int(tolerance.Type) != 4
                    or abs(float(tolerance.GetMinValue()) + od_tolerance_mm / 1000)
                    > 1e-12
                    or abs(float(tolerance.GetMaxValue()) - od_tolerance_mm / 1000)
                    > 1e-12
                    or int(display.GetPrimaryTolPrecision2()) != od_tolerance_precision
                ):
                    raise RuntimeError(
                        "source supplier OD band changed after final rebuild"
                    )
            elif int(tolerance.Type) != 0:
                raise RuntimeError(f"{name}: unprovided supplier tolerance appeared")

    return (settled,)


def supplier_state_cells(caption_y: float, *, maximum: bool) -> tuple:
    """Reserve an annotation band around every fitted native view."""
    if not maximum:
        return (
            _cell("free_front", 0.028, caption_y + 0.020, 0.235, 0.166),
            _cell("free_top", 0.028, 0.207, 0.235, 0.247),
            _cell("free_right", 0.267, caption_y + 0.026, 0.406, 0.165),
            _cell("installed_iso", 0.325, 0.190, 0.406, 0.252),
        )
    return (
        _cell("free_front", 0.028, 0.166, 0.242, 0.206),
        _cell("free_top", 0.028, 0.230, 0.242, 0.250),
        _cell("free_right", 0.267, 0.205, 0.406, 0.252),
        _cell("installed_iso", 0.325, 0.142, 0.406, 0.175),
        _cell("max_front", 0.028, caption_y + 0.020, 0.403, 0.122),
    )


@contextmanager
def _preserve_reference_source_file(source: Path, expected_sha256: str, *, label: str):
    """Prove drawing finalization never persists presentation edits to the part."""
    primary: BaseException | None = None
    try:
        yield
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            if _source_file_sha256(source) != expected_sha256:
                raise RuntimeError(
                    f"{label}: supplier source part bytes changed during drawing finalization"
                )
        except BaseException as preservation_error:
            if primary is not None:
                primary.add_note(
                    f"{label}: supplier source file preservation also failed: {preservation_error!r}"
                )
            else:
                raise


@dataclass(frozen=True)
class _ReferenceSourceState:
    path: Path
    model: Any
    configuration: str
    configurations: tuple[str, ...]
    body_counts: tuple[int, int]
    read_only: bool


@dataclass(frozen=True)
class _CapturedReferenceView:
    source: _ReferenceSourceState
    view: Any
    name: str
    configuration: str
    features: tuple[str, ...]
    geometry: tuple[NativeSketchGeometry, ...]


def _reference_body_counts(model: Any) -> tuple[int, int]:
    part = _early_bound(model, "IPartDoc")
    return tuple(len(tuple(part.GetBodies2(kind, False) or ())) for kind in (0, 1))


def _reference_configuration_names(model: Any, *, label: str) -> tuple[str, ...]:
    names = tuple(model.GetConfigurationNames() or ())
    if (
        not names
        or any(type(name) is not str or not name for name in names)
        or len(set(names)) != len(names)
    ):
        raise RuntimeError(f"{label}: source configuration member names are unreadable")
    return tuple(sorted(names))


def _reference_rebuild_status(model: Any, *, label: str) -> int:
    status = _early_bound(model.Extension, "IModelDocExtension").NeedsRebuild2
    # swModelRebuildStatus_e is an integer bitmask, not a Boolean property.
    if type(status) is not int or status not in (0, 1, 2, 3):
        raise RuntimeError(f"{label}: invalid native source rebuild status {status!r}")
    return status


def _activate_reference_document(adapter: Any, model: Any, *, label: str) -> None:
    # Generated ActivateDoc3 declares Errors [in,out] (16387, 3), unlike the
    # OUT-only GetErrorCode2. Supply its scalar seed and consume the return tuple.
    # swDontRebuildActiveDoc=1: only the checked source transition may rebuild.
    result = adapter.swApp.ActivateDoc3(str(model.GetTitle()), False, 1, 0)
    if (
        not isinstance(result, tuple)
        or len(result) != 2
        or result[0] is None
        or type(result[1]) is not int
        or result[1] not in (0, 2)
    ):
        raise RuntimeError(f"{label}: document activation failed: {result!r}")
    activated = _early_bound(result[0], "IModelDoc2")
    active = adapter.swApp.ActiveDoc
    if (
        active is None
        or int(adapter.swApp.IsSame(activated, model)) != 1
        or int(adapter.swApp.IsSame(active, model)) != 1
    ):
        raise RuntimeError(f"{label}: document activation changed native identity")
    adapter.currentModel = activated


def _show_reference_configuration(
    adapter: Any, model: Any, name: str, *, label: str
) -> None:
    before = active_configuration_name(adapter, model)
    status = _reference_rebuild_status(model, label=label)
    _telemetry.info(
        f"{label}: source transition before: configuration={before!r}; "
        f"requested={name!r}; dirty={bool(model.GetSaveFlag())!r}; needs_rebuild={status!r}"
    )
    if before != name and model.ShowConfiguration2(name) is not True:
        raise RuntimeError(f"{label}: cannot activate source configuration {name!r}")
    if active_configuration_name(adapter, model) != name:
        raise RuntimeError(
            f"{label}: source configuration readback differs from {name!r}"
        )
    status = _reference_rebuild_status(model, label=label)
    if status != 0 and model.EditRebuild3() is not True:
        raise RuntimeError(f"{label}: cannot rebuild source configuration {name!r}")
    status = _reference_rebuild_status(model, label=label)
    after = active_configuration_name(adapter, model)
    _telemetry.info(
        f"{label}: source transition after: configuration={after!r}; "
        f"requested={name!r}; dirty={bool(model.GetSaveFlag())!r}; needs_rebuild={status!r}"
    )
    if after != name or status != 0:
        raise RuntimeError(
            f"{label}: source configuration {name!r} did not settle after rebuilding"
        )


def _assert_reference_source_restored(
    adapter: Any,
    state: _ReferenceSourceState,
    *,
    label: str,
    allow_presentation_dirty: bool = False,
) -> None:
    dirty = state.model.GetSaveFlag()
    if (
        Path(state.model.GetPathName()).resolve() != state.path
        or active_configuration_name(adapter, state.model) != state.configuration
        or type(dirty) is not bool
        or (dirty and not allow_presentation_dirty)
        or state.read_only is not True
        or state.model.IsOpenedReadOnly() is not True
        or _reference_configuration_names(state.model, label=label)
        != state.configurations
        or _reference_body_counts(state.model) != state.body_counts
    ):
        raise RuntimeError(
            f"{label}: supplier source path/configuration/dirty/read-only/member state changed"
        )


def _assert_reference_binding(
    adapter: Any,
    view: Any,
    *,
    source: Path,
    model: Any,
    configuration: str,
    label: str,
) -> None:
    referenced = view.ReferencedDocument
    if (
        referenced is None
        or int(adapter.swApp.IsSame(referenced, model)) != 1
        or Path(model.GetPathName()).resolve() != source
        or Path(view.GetReferencedModelName()).resolve() != source
        or str(view.ReferencedConfiguration) != configuration
    ):
        raise RuntimeError(
            f"{label}: supplier reference source document/path/configuration changed"
        )


def _assert_reference_view_ink(view: Any, *, label: str) -> None:
    drawing_sketch = _early_bound(_bind(view.GetSketch(), "ISketch"), "ISketch")
    if (
        drawing_sketch is None
        or tuple(drawing_sketch.GetSketchSegments() or ())
        or drawing_sketch.GetSketchBlockInstanceCount() != 0
        or tuple(drawing_sketch.GetSketchTextSegments() or ())
        or drawing_sketch.GetUserPointsCount() != 0
    ):
        raise RuntimeError(
            f"{label}: unexpected or unreadable additional drawing-sketch geometry"
        )


def _reference_features(model: Any, adapter: Any, *, label: str) -> dict[str, Any]:
    references: dict[str, Any] = {}
    for raw in FeatureWalk(model):
        feature = _early_bound(_bind(raw, "IFeature"), "IFeature")
        kind = str(feature.GetTypeName2())
        if kind not in REFERENCE_FEATURE_KINDS:
            continue
        name = str(feature.Name)
        if not name:
            raise RuntimeError(f"{label}: empty native reference identity")
        previous = references.get(name)
        if previous is not None:
            # FeatureWalk can revisit a shared subfeature. Only native identity,
            # together with the same name/type, distinguishes this from ambiguity.
            if (
                str(previous.GetTypeName2()) != kind
                or int(adapter.swApp.IsSame(previous, feature)) != 1
            ):
                raise RuntimeError(
                    f"{label}: ambiguous native reference identity {name!r}"
                )
            continue
        references[name] = feature
    return references


def _capture_reference_configuration(
    adapter: Any,
    views: Mapping[str, Any],
    *,
    state: _ReferenceSourceState,
    owners: Mapping[str, tuple[str, ...]],
    configuration: str,
    label: str,
) -> dict[str, _CapturedReferenceView]:
    """Keep all configuration-dependent native proxies local to one active pass."""
    model = state.model
    if active_configuration_name(adapter, model) != configuration:
        raise RuntimeError(f"{label}: source capture is not in {configuration!r}")
    counts = _reference_body_counts(model)
    if counts != (0, 0):
        raise RuntimeError(
            f"{label}: supplier source configuration {configuration!r} "
            f"has solid/sheet bodies {counts!r}, expected (0, 0)"
        )
    references = _reference_features(model, adapter, label=label)
    for key, names in owners.items():
        view = _early_bound(views[key], "IView")
        _assert_reference_binding(
            adapter,
            view,
            source=state.path,
            model=model,
            configuration=configuration,
            label=f"{label} {key}",
        )
        view.UpdateViewDisplayGeometry()
    geometry = {}
    for name in dict.fromkeys(name for names in owners.values() for name in names):
        feature = references.get(name)
        if feature is None:
            raise RuntimeError(f"{label}: expected source sketch {name!r} is missing")
        if str(feature.GetTypeName2()) != "ProfileFeature":
            raise RuntimeError(f"{label}: expected source sketch {name!r} is not a ProfileFeature")
        visibility = feature.Visible
        if type(visibility) is not int or visibility != 1:
            raise RuntimeError(f"{label}: expected source sketch {name!r} is not saved model-hidden")
        if _suppressed(feature):
            raise RuntimeError(f"{label}: expected source sketch {name!r} is suppressed")
        error = feature.GetErrorCode2()
        if (
            type(error) is not tuple
            or len(error) != 2
            or type(error[0]) is not int
            or error[0] != 0
        ):
            raise RuntimeError(f"{label}: source sketch {name!r} error state {error!r}")
        # IsWarning is undefined for code zero; never infer from it.
        sketch = _early_bound(
            _bind(feature.GetSpecificFeature2(), "ISketch"), "ISketch"
        )
        if sketch is None:
            raise RuntimeError(
                f"{label}: native reference sketch {name!r} is unavailable"
            )
        for raw in sketch.GetSketchSegments() or ():
            segment = _early_bound(_bind(raw, "ISketchSegment"), "ISketchSegment")
            for key, names in owners.items():
                if name in names and views[key].GetCorresponding(segment) is None:
                    raise RuntimeError(
                        f"{label} {key}: source segment has no drawing-view correspondence: {name}"
                    )
        geometry[name] = capture_native_sketch_geometry(sketch, label=f"{label} {name}")
    if active_configuration_name(adapter, model) != configuration:
        raise RuntimeError(
            f"{label}: geometry capture changed the requested source configuration"
        )
    return {
        key: _CapturedReferenceView(
            state,
            _early_bound(views[key], "IView"),
            view_name(adapter, views[key]),
            configuration,
            names,
            tuple(geometry[name] for name in names),
        )
        for key, names in owners.items()
    }


def _capture_reference_views(
    adapter: Any,
    draw: Any,
    views: Mapping[str, Any],
    *,
    source: Path,
    model: Any,
    features: Mapping[str, Sequence[str]],
    configurations: Mapping[str, str],
    label: str,
) -> dict[str, _CapturedReferenceView]:
    """Capture each actual cfg/owner once, restoring source and drawing before fit.

    No source feature or sketch proxy survives a configuration switch. Later
    staleness guards require a clean read-only source until the explicit
    annotation-presentation phase; the source file must remain byte-identical.
    """
    source = source.resolve()
    model = _early_bound(model, "IModelDoc2")
    owners = {key: tuple(names) for key, names in features.items()}
    if (
        not owners
        or not set(owners) <= set(views)
        or not set(views) <= set(configurations)
        or any(
            not names
            or len(set(names)) != len(names)
            or any(type(name) is not str or not name for name in names)
            for names in owners.values()
        )
    ):
        raise RuntimeError(
            f"{label}: expected distinct named supplier reference owners and configured views"
        )
    original = active_configuration_name(adapter, model)
    if not original or Path(model.GetPathName()).resolve() != source:
        raise RuntimeError(
            f"{label}: supplier source path/active configuration is unreadable"
        )
    was_dirty = bool(model.GetSaveFlag())
    if was_dirty:
        raise RuntimeError(
            f"{label}: supplier source must be clean before native reference capture"
        )
    if model.IsOpenedReadOnly() is not True:
        raise RuntimeError(
            f"{label}: supplier native reference capture requires a read-only source"
        )
    state = _ReferenceSourceState(
        source,
        model,
        original,
        _reference_configuration_names(model, label=label),
        _reference_body_counts(model),
        bool(model.IsOpenedReadOnly()),
    )
    drawing = _early_bound(draw, "IDrawingDoc")
    sheet_name = str(_early_bound(drawing.GetCurrentSheet(), "ISheet").GetName())
    previous = drawing.ActiveDrawingView
    previous_name = view_name(adapter, previous) if previous is not None else None
    if not sheet_name or drawing.GetEditSheet() is not True:
        raise RuntimeError(f"{label}: supplier capture requires drawing sheet context")
    for key, view in views.items():
        _assert_reference_binding(
            adapter,
            view,
            source=source,
            model=model,
            configuration=configurations[key],
            label=f"{label} {key}",
        )
    captures: dict[str, _CapturedReferenceView] = {}
    primary: BaseException | None = None
    try:
        _activate_reference_document(adapter, model, label=label)
        for configuration in dict.fromkeys(configurations[key] for key in owners):
            _show_reference_configuration(adapter, model, configuration, label=label)
            captures.update(
                _capture_reference_configuration(
                    adapter,
                    views,
                    state=state,
                    configuration=configuration,
                    owners={
                        key: names
                        for key, names in owners.items()
                        if configurations[key] == configuration
                    },
                    label=label,
                )
            )
    except BaseException as error:
        primary = error
        raise
    finally:
        restoration_errors: list[BaseException] = []
        try:
            active = adapter.swApp.ActiveDoc
            if active is None or int(adapter.swApp.IsSame(active, model)) != 1:
                _activate_reference_document(adapter, model, label=label)
            _show_reference_configuration(adapter, model, original, label=label)
            _assert_reference_source_restored(adapter, state, label=label)
        except BaseException as restore_error:
            restoration_errors.append(restore_error)
        try:
            _activate_reference_document(adapter, draw, label=label)
            restored = drawing.ActivateSheet(sheet_name)
            if previous_name is not None:
                restored = (
                    drawing.ActivateView(previous_name) is True and restored is True
                )
            active = drawing.ActiveDrawingView
            active_name = view_name(adapter, active) if active is not None else None
            if (
                restored is not True
                or active_name != previous_name
                or str(_early_bound(drawing.GetCurrentSheet(), "ISheet").GetName())
                != sheet_name
                or drawing.GetEditSheet() is not True
                or (
                    previous is not None
                    and int(adapter.swApp.IsSame(active, previous)) != 1
                )
            ):
                raise RuntimeError(
                    f"{label}: cannot restore supplier drawing sheet/view context"
                )
        except BaseException as restore_error:
            restoration_errors.append(restore_error)
        for key, view in views.items():
            try:
                _assert_reference_binding(
                    adapter,
                    view,
                    source=source,
                    model=model,
                    configuration=configurations[key],
                    label=f"{label} {key} restored",
                )
            except BaseException as restore_error:
                restoration_errors.append(restore_error)
        if restoration_errors:
            if primary is not None:
                for restore_error in restoration_errors:
                    primary.add_note(
                        f"{label}: supplier capture restoration also failed: {restore_error!r}"
                    )
            else:
                failure = restoration_errors[0]
                for restore_error in restoration_errors[1:]:
                    failure.add_note(
                        f"{label}: supplier capture restoration also failed: {restore_error!r}"
                    )
                raise failure
    return captures


def _assert_reference_capture_binding(
    adapter: Any, view: Any, *, capture: _CapturedReferenceView, source: Path,
    model: Any, features: Sequence[str], configuration: str, label: str,
) -> None:
    if (
        not isinstance(capture, _CapturedReferenceView)
        or capture.source.path != source
        or capture.configuration != configuration
        or capture.features != tuple(features)
        or not capture.geometry
        or len(capture.geometry) != len(capture.features)
        or int(adapter.swApp.IsSame(capture.source.model, model)) != 1
        or int(adapter.swApp.IsSame(capture.view, view)) != 1
        or not capture.name
        or capture.name != view_name(adapter, view)
    ):
        raise RuntimeError(f"{label}: foreign or incomplete supplier native capture")
    _assert_reference_binding(
        adapter, view, source=source, model=model, configuration=configuration, label=label,
    )


def _reference_view_bounds(
    adapter: Any,
    view: Any,
    *,
    capture: _CapturedReferenceView,
    source: Path,
    model: Any,
    features: Sequence[str],
    configuration: str,
    label: str,
    allow_presentation_dirty: bool = False,
) -> tuple[float, float, float, float]:
    """Project caller-bound immutable floats; never switch or reread source ink."""
    view = _early_bound(view, "IView")
    source = source.resolve()
    _assert_reference_capture_binding(
        adapter, view, capture=capture, source=source, model=model,
        features=features, configuration=configuration, label=label,
    )
    _assert_reference_source_restored(
        adapter,
        capture.source,
        label=label,
        allow_presentation_dirty=allow_presentation_dirty,
    )
    view.UpdateViewDisplayGeometry()
    _assert_reference_view_ink(view, label=label)
    boxes = tuple(
        native_sketch_view_bounds(adapter, view, geometry, label=f"{label} {name}")
        for name, geometry in zip(capture.features, capture.geometry, strict=True)
    )
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _record_supplier_fit_candidates(
    adapter: Any,
    draw: Any,
    members: list[tuple[Any, tuple]],
    *,
    read_bounds: Callable[[Any, str], tuple[float, float, float, float]] | None = None,
) -> None:
    """Replay the same actual bounds reader; diagnostics never select a fallback."""
    previous = [
        (view, tuple(view.ScaleRatio), view.UseSheetScale) for view, _ in members
    ]
    try:
        for scale in _SCALES:
            for view, _ in members:
                view.UseSheetScale = 0
                view.ScaleRatio = double_array([float(scale[0]), float(scale[1])])
            _rebuild(draw, phase="diagnose supplier view scale")
            for view, (key, center, cell) in members:
                raw_outline = None
                outline_error = None
                try:
                    raw_outline = view.GetOutline()
                    outline = (
                        tuple(float(value) for value in raw_outline)
                        if raw_outline is not None
                        else ()
                    )
                except Exception as reader_error:
                    outline = ()
                    outline_error = repr(reader_error)
                size = (
                    (outline[2] - outline[0], outline[3] - outline[1])
                    if len(outline) == 4
                    else None
                )
                if len(outline) != 4:
                    outline_status = "missing-or-malformed"
                elif not all(map(isfinite, outline)):
                    outline_status = "nonfinite"
                elif size[0] <= 0.0 or size[1] <= 0.0:
                    outline_status = "nonpositive"
                else:
                    outline_status = "finite-positive"
                cell_size = (cell[2] - cell[0], cell[3] - cell[1])
                excess = (
                    tuple(size[index] - cell_size[index] for index in range(2))
                    if size
                    else None
                )
                bounds = bounds_size = bounds_excess = None
                bounds_error = None
                try:
                    bounds = (
                        read_bounds(view, key)
                        if read_bounds is not None
                        else _box(raw_outline, label=key)
                    )
                    bounds_size = (bounds[2] - bounds[0], bounds[3] - bounds[1])
                    bounds_excess = tuple(
                        bounds_size[index] - cell_size[index] for index in range(2)
                    )
                except Exception as reader_error:
                    # One bad projection must not hide another view's actual
                    # replay or replace the original fitter failure.
                    bounds_error = repr(reader_error)
                _telemetry.info(
                    f"supplier fit diagnostic: key={key!r}; view={view_name(adapter, view)!r}; "
                    f"configuration={str(view.ReferencedConfiguration)!r}; "
                    f"orientation={str(view.GetOrientationName())!r}; "
                    f"requested_scale={scale!r}; actual_scale={tuple(view.ScaleRatio)!r}; "
                    f"use_sheet_scale={view.UseSheetScale!r}; position_m={tuple(view.Position)!r}; "
                    f"raw_outline_m={raw_outline!r}; outline_status={outline_status!r}; "
                    f"outline_m={outline!r}; outline_error={outline_error!r}; "
                    f"outline_size_m={size!r}; outline_size_excess_m={excess!r}; "
                    f"bounds_source={'captured-native' if read_bounds is not None else 'native-outline'!r}; "
                    f"bounds_m={bounds!r}; bounds_size_m={bounds_size!r}; "
                    f"bounds_size_excess_m={bounds_excess!r}; bounds_reader_error={bounds_error!r}; "
                    f"cell_m={cell!r}; cell_center_m={center!r}"
                )
    finally:
        for view, ratio, use_sheet_scale in previous:
            view.ScaleRatio = double_array([float(value) for value in ratio])
            view.UseSheetScale = use_sheet_scale
        _rebuild(draw, phase="restore failed supplier view scale")


async def build_supplier_spring_drawing(
    adapter: Any,
    spec: DrawingSpec,
    *,
    item: str,
    supplier_dimensions: Callable[..., Sequence[Callable[[], None]] | None],
    supplier_margins: Mapping[str, tuple[float, float, float, float]],
    supplier_reference_features: Mapping[str, Sequence[str]],
    maximum: bool = False,
    stock_configuration: str = SUPPLIER_FREE_CONFIGURATION,
    prepare_views: Callable[..., Sequence[Callable[[], None]] | None] | None = None,
    include_right: bool = True,
    include_top: bool = True,
    installed_configuration: str | None = None,
    installed_variants: Sequence[tuple[str, str]] = (),
    stock_caption: str = "SUPPLIER NOMINAL STOCK DIAGRAM — NOT PART SHAPE",
    installed_caption: str = "INSTALLED REPRESENTATION",
    right_caption: str = "SUPPLIER NOMINAL SECTIONS",
    cut_to_suit: bool = False,
    spring_metadata: bool = False,
    settled_checks: Sequence[Callable[[], None]] = (),
) -> dict[str, str]:
    source = spec.source
    if spec.source_kind != "part" or not source.is_file():
        raise FileNotFoundError(f"source purchased part is missing: {source}")
    source_sha256 = _source_file_sha256(source)
    model = _open_supplier_source_read_only(adapter, source, label=spec.artifact_stem)
    if model.GetSaveFlag() is not False:
        raise RuntimeError(
            f"{spec.artifact_stem}: supplier source must be clean before native reference capture"
        )
    installed = installed_configuration or active_configuration_name(adapter, model)
    available = set(model.GetConfigurationNames() or ())
    required = {stock_configuration}
    if maximum:
        required.add(SUPPLIER_MAX_CONFIGURATION)
    if (
        not installed
        or installed not in available
        or installed in required
        or not required <= available
    ):
        raise RuntimeError(
            f"{spec.artifact_stem}: installed/supplier configurations missing or ambiguous"
        )
    if spring_metadata:
        names = (
            *_PROPERTIES,
            "Material Specification",
            "Finish",
            "Manufacturing Notes",
        )
        properties = read_required_properties(model, names, required=names)
        material_property = "Material Specification"
        finish = properties["Finish"]
        notes = properties["Manufacturing Notes"]
        document_title = properties["Title"]
    else:
        properties = read_required_properties(model, _PROPERTIES, required=_PROPERTIES)
        registry = _config.parts(source.stem)
        expected = {
            "Number": str(registry["number"]),
            "Title": source.stem,
            "Material": str(registry["material"]),
            "Stock Name": str(registry["stock_name"]),
            "Supplier": str(registry["supplier"]),
            "Supplier SKUs": ", ".join(str(sku) for sku in registry["supplier_skus"]),
        }
        for name, value in expected.items():
            if properties[name] != value:
                raise RuntimeError(
                    f"{source.stem}: stale source {name}: {properties[name]!r} != {value!r}"
                )
        material_property = "Material"
        finish = registry["finish"]
        if not isinstance(finish, str) or not finish.strip():
            raise RuntimeError(f"{source.stem}: registered purchased finish is empty")
        notes = str(registry.get("installation_notes", ""))
        document_title = str(registry["title"])
    check_item(item, label=spec.artifact_stem)
    caption_y = view_band_bottom(notes, label=spec.artifact_stem)
    cells = tuple(
        cell
        for cell in supplier_state_cells(caption_y, maximum=maximum)
        if (include_right or cell[0] != "free_right")
        and (include_top or cell[0] != "free_top")
    )
    if not include_right and not maximum:
        cells = tuple(
            _cell("installed_iso", 0.267, caption_y + 0.026, 0.406, 0.252)
            if cell[0] == "installed_iso"
            else cell
            for cell in cells
        )
    if installed_variants:
        if (
            maximum
            or include_right
            or len(installed_variants) != 2
            or len({name for name, _label in installed_variants}) != 2
            or any(
                name not in available or name in required or not label.strip()
                for name, label in installed_variants
            )
        ):
            raise ValueError(
                "two installed variants require distinct original configs and include_right=False"
            )
        installed = installed_variants[0][0]
        cells = tuple(cell for cell in cells if cell[0] != "installed_iso") + (
            _cell("installed_iso", 0.267, caption_y + 0.026, 0.406, 0.165),
            _cell("installed_second_iso", 0.267, 0.190, 0.406, 0.252),
        )
    if any(key.startswith("installed_") for key in supplier_margins):
        raise ValueError(
            "installed isometric must retain its unannotated geometry cell"
        )
    reference_features = {
        key: tuple(names) for key, names in supplier_reference_features.items()
    }
    if set(reference_features) != {
        key for key, _, _ in cells if not key.startswith("installed_")
    } or any(
        not names
        or len(set(names)) != len(names)
        or any(not isinstance(name, str) or not name for name in names)
        for names in reference_features.values()
    ):
        raise ValueError(
            "supplier reference owners must exactly name every source-diagram view"
        )
    fit_cells = supplier_fit_cells(cells, supplier_margins, label=spec.artifact_stem)
    draw, sheet = new_project_drawing(adapter, layout=spec.layout)
    title_notes = _purchased_title_block(
        adapter,
        draw,
        material=properties[material_property],
        finish=finish,
        material_property=material_property,
    )
    title = f"{document_title} — Supplier and Installed Reference Drawing"
    stamp_drawing_summary(
        adapter,
        draw,
        {
            0: title,
            1: "Purchased identification only; supplier sizes are reference dimensions",
            2: "Harmonic Analyzer Project",
            3: f"{spec.artifact_stem}; {properties['Supplier']}; {properties['Supplier SKUs']}",
            4: f"{stock_caption}; installed pictorial; separate maximum state"
            if maximum
            else f"{stock_caption}; separate installed pictorial",
        },
    )
    orientations = {
        "free_front": "*Front",
        "free_top": "*Top",
        "free_right": "*Right",
        "installed_iso": "*Isometric",
        "max_front": "*Front",
    }
    configurations = {key: stock_configuration for key in orientations}
    configurations["installed_iso"] = installed
    configurations["max_front"] = SUPPLIER_MAX_CONFIGURATION
    if installed_variants:
        orientations["installed_second_iso"] = "*Isometric"
        configurations["installed_second_iso"] = installed_variants[1][0]
    views: dict[str, Any] = {}
    for key, center, _ in cells:
        view = _early_bound(
            place_view(adapter, str(source), orientations[key], *center, scale=(1, 1)),
            "IView",
        )
        view.ReferencedConfiguration = configurations[key]
        if str(view.ReferencedConfiguration) != configurations[key]:
            raise RuntimeError(
                f"{key}: supplier/installed configuration assignment failed"
            )
        set_hidden_lines_removed(adapter, view)
        views[key] = view
    for view in views.values():
        view.UseSheetScale = 0
        view.ScaleRatio = double_array([1.0, 1.0])
    captures: dict[str, _CapturedReferenceView] = {}
    allow_presentation_dirty = False

    def state_bounds(view: Any, key: str) -> tuple[float, float, float, float]:
        if key in reference_features:
            capture = captures.get(key)
            if capture is None:
                raise RuntimeError(
                    f"{spec.artifact_stem} {key}: supplier reference capture is not ready"
                )
            return _reference_view_bounds(
                adapter,
                view,
                capture=capture,
                source=source,
                model=model,
                features=reference_features[key],
                configuration=configurations[key],
                label=f"{spec.artifact_stem} {key}",
                allow_presentation_dirty=allow_presentation_dirty,
            )
        return _box(view.GetOutline(), label=key)

    def reference_bounds(key: str) -> tuple[float, float, float, float]:
        if key not in reference_features:
            raise RuntimeError(
                f"{spec.artifact_stem}: not a supplier reference view: {key!r}"
            )
        return state_bounds(views[key], key)

    preparation_checks = (
        prepare_views(adapter, views, reference_bounds=reference_bounds)
        if prepare_views
        else ()
    )
    _rebuild(draw, phase="supplier states before fitting")
    captures.update(
        _capture_reference_views(
            adapter,
            draw,
            views,
            source=source,
            model=model,
            features=reference_features,
            configurations=configurations,
            label=spec.artifact_stem,
        )
    )
    # Supplier circles can legitimately acquire native centre crosses. Remove
    # their template extension lines before fitting, not the useful crosses.
    _center_marks_without_lines(list(views.values()), cells)
    for prepared_check in preparation_checks or ():
        prepared_check()

    scales = {}
    for keys in (
        ("free_front", "free_top"),
        ("free_right",),
        ("installed_iso",),
        ("installed_second_iso",),
        ("max_front",),
    ):
        members = [(views[key], cell) for cell in fit_cells if (key := cell[0]) in keys]
        if members:
            read_bounds = (
                state_bounds
                if all(cell[0] in reference_features for _, cell in members)
                else None
            )
            try:
                scale = _fit_group(
                    draw,
                    members,
                    read_bounds=read_bounds,
                )
            except RuntimeError as error:
                try:
                    _record_supplier_fit_candidates(
                        adapter, draw, members, read_bounds=read_bounds
                    )
                except Exception as diagnostic_error:
                    error.add_note(
                        f"supplier fit diagnostics also failed: {diagnostic_error}"
                    )
                import _seat_forensics

                _seat_forensics.capture_com_failure(
                    adapter,
                    f"supplier-fit-{spec.artifact_stem}",
                    str(error),
                    exception=error,
                    sheet_png=True,
                    view_keys=tuple(cell[0] for _, cell in members),
                )
            scales.update({cell[0]: scale for _, cell in members})
    _center_marks_without_lines(list(views.values()), cells)
    for key in reference_features:
        _assert_reference_view_ink(views[key], label=f"{spec.artifact_stem} {key}")
    scale = scales["free_front"]
    values = tuple(adapter._get_attr_or_call(sheet, "GetProperties2"))
    if len(values) != 8:
        raise RuntimeError("supplier sheet has incomplete native properties")
    sheet.SetProperties2(
        int(values[0]),
        int(values[1]),
        float(scale[0]),
        float(scale[1]),
        False,
        float(values[5]),
        float(values[6]),
        False,
    )
    sheet.CustomPropertyView = view_name(adapter, views["installed_iso"])
    if not sheet.CustomPropertyView:
        raise RuntimeError("supplier sheet has no installed property-source view")
    assert_asme_b_sheet(
        adapter, sheet, layout=spec.layout, phase="supplier states", scale=scale
    )
    fitted_names = {key: view_name(adapter, view) for key, view in views.items()}
    fitted_origins = {}
    for key, view in views.items():
        view.UpdateViewDisplayGeometry()
        origin = model_point_in_view(
            adapter,
            view,
            (0.0, 0.0, 0.0),
            label=f"{spec.artifact_stem} {key} fitted origin",
        )
        if not all(map(isfinite, origin)):
            raise RuntimeError(f"{key}: fitted model origin is not finite")
        fitted_origins[key] = origin
    # Model-owned SetText changes may dirty this read-only source without
    # changing geometry. Admit that state only at the known annotation stage,
    # never during preparation/capture/fitting, and never as a new clean seal.
    _assert_reference_source_restored(
        adapter,
        next(iter(captures.values())).source,
        label=spec.artifact_stem,
    )
    _telemetry.info(
        f"{spec.artifact_stem}: entering read-only supplier annotation presentation phase; "
        f"source={str(source.resolve())!r}; source bytes must remain unchanged"
    )
    allow_presentation_dirty = True
    dimension_checks = (
        supplier_dimensions(adapter, views, reference_bounds=reference_bounds) or ()
    )
    ddoc = _early_bound(draw, "IDrawingDoc")
    ddoc.ActivateView("")
    if not ddoc.GetEditSheet() or ddoc.ActiveDrawingView is not None:
        raise RuntimeError("cannot restore supplier sheet context for captions/footer")
    captions = {
        "free_front": f"{stock_caption} — FRONT",
        "free_top": f"{stock_caption} — TOP",
        "free_right": right_caption,
        "installed_iso": installed_caption,
        "max_front": "SUPPLIER NOMINAL MAXIMUM EXTENSION — NOT INSTALLED",
        "installed_second_iso": installed_variants[1][1] if installed_variants else "",
    }
    if installed_variants:
        captions["installed_iso"] = installed_variants[0][1]
    placed = []
    for key, center, cell in cells:
        ratio = scales[key]
        text = f"{captions[key]}  {ratio[0]}:{ratio[1]}"
        y = cell[1] - (0.016 if key == "free_right" else 0.012)
        note = _literal_note(adapter, text, center[0], y)
        bounds = _box(note.GetExtent(), label=text, kind="note")
        annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
        if int(annotation.OwnerType) != 1:
            raise RuntimeError(f"{key}: state caption is not sheet-owned")
        x = center[0] - (bounds[2] - bounds[0]) / 2
        if not annotation.SetPosition(x, y, 0.0):
            raise RuntimeError(f"{key}: cannot center state caption")
        placed.append((note, text, text, (0.015, y - 0.008, 0.416, y + 0.001)))
    placed.extend(
        add_purchased_footer(
            adapter,
            draw,
            properties,
            item=item,
            notes=notes,
            cut_to_suit=cut_to_suit,
            label=spec.artifact_stem,
        )
    )
    _rebuild(draw, phase="supplier/installed annotations")
    actual = list(iter_views(adapter))
    if len(actual) != len(cells):
        raise RuntimeError(
            f"supplier sheet must have exactly {len(cells)} native views"
        )
    template = DRAWING_TEMPLATES[spec.layout]
    region = sheet_drawable_region(
        adapter, sheet, width=template.width_m, height=template.height_m
    )
    border = (region.xmin, region.ymin, region.xmax, region.ymax)
    for key, _, cell in cells:
        view = views[key]
        if (
            Path(view.GetReferencedModelName()).resolve() != source.resolve()
            or str(view.ReferencedConfiguration) != configurations[key]
            or str(view.GetOrientationName()) != orientations[key]
            or tuple(view.ScaleRatio) != scales[key]
            or not _inside(state_bounds(view, key), cell)
        ):
            raise RuntimeError(
                f"{key}: fitted native supplier-state view contract changed"
            )
    for note, linked, resolved in title_notes:
        if note.PropertyLinkedText != linked or note.GetText() != resolved:
            raise RuntimeError("supplier-state title-block property resolution changed")

    def sheet_note_contract() -> None:
        for note, linked, resolved, cell in placed:
            if (
                int(_early_bound(note.GetAnnotation(), "IAnnotation").OwnerType) != 1
                or note.PropertyLinkedText != linked
                or note.GetText().replace("\r\n", "\n") != resolved
                or not _inside(
                    _box(note.GetExtent(), label=resolved, kind="note"), cell
                )
                or not _inside(
                    _box(note.GetExtent(), label=resolved, kind="note"), border
                )
            ):
                raise RuntimeError(
                    f"supplier-state sheet note readback/owner/border contract failed: {resolved}"
                )

    sheet_note_contract()

    def settled_state_contract() -> None:
        rebuilt_views = {
            view_name(adapter, view): _early_bound(view, "IView")
            for view in iter_views(adapter)
        }
        if set(rebuilt_views) != set(fitted_names.values()):
            raise RuntimeError("final rebuilt supplier-state native view set changed")
        for key, _, cell in cells:
            view = rebuilt_views[fitted_names[key]]
            if (
                Path(view.GetReferencedModelName()).resolve() != source.resolve()
                or str(view.ReferencedConfiguration) != configurations[key]
                or str(view.GetOrientationName()) != orientations[key]
                or tuple(view.ScaleRatio) != scales[key]
                or not _inside(state_bounds(view, key), cell)
            ):
                raise RuntimeError(
                    f"{key}: final rebuilt supplier-state view contract changed"
                )
            view.UpdateViewDisplayGeometry()
            origin = model_point_in_view(
                adapter,
                view,
                (0.0, 0.0, 0.0),
                label=f"{spec.artifact_stem} {key} settled origin",
            )
            if not all(map(isfinite, origin)) or any(
                abs(actual - expected) > 1e-6
                for actual, expected in zip(origin, fitted_origins[key], strict=True)
            ):
                raise RuntimeError(f"{key}: final rebuilt supplier-state view moved")
            if (view.GetFirstDisplayDimension6() is not None) != (
                key in supplier_margins
            ):
                raise RuntimeError(
                    f"{key}: native dimensions do not match the reserved annotation cells"
                )
            if key in reference_features:
                assert_supplier_annotations_fit(
                    adapter,
                    view,
                    cell,
                    label=f"{spec.artifact_stem} {key}",
                )
            else:
                assert_supplier_view_fits(
                    adapter,
                    view,
                    cell,
                    label=f"{spec.artifact_stem} {key}",
                )
        sheet_note_contract()

    paths = spec.outputs
    with _preserve_reference_source_file(
        source, source_sha256, label=spec.artifact_stem
    ):
        return await finalize_drawing(
            adapter,
            DrawingOutputs(slddrw=paths["slddrw"], pdf=paths["pdf"], png=paths["png"]),
            layout=spec.layout,
            pdf_title=title,
            scale=scale,
            settled_checks=(*settled_checks, *dimension_checks, settled_state_contract),
        )
