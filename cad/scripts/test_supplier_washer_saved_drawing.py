"""Offline saved-roundtrip controls; these doubles are not native farm evidence.

Only COM transport, the visible-edge enumeration and source-dimension lookup are
substituted. The saved reader and strict body/rim/value/band/presentation/source
attachment assertions execute unchanged against independently seeded surfaces.
"""

from __future__ import annotations

import asyncio
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
import weakref

import pytest

import _drawing_attachment as attachment
import _drawing_edges as edges
import _supplier_dimensions as supplier
import _supplier_washer_drawing as washer
import _supplier_washer_model as source


ORIENTATIONS = ("*Front", "*Top", "*Right", "*Isometric")
VALUES = {source.OUTER_DIAMETER: 10.0, source.BORE_DIAMETER: 4.0, source.THICKNESS: 0.91}


class _ReadSurface:
    """Fault injection is allowed before open; even same-value writes then fail."""

    def __init__(self, **members):
        self.__dict__.update(members)

    def __setattr__(self, name, value):
        if self.__dict__.get("_saved_read", False):
            raise AssertionError(f"saved reader wrote native property {name}")
        object.__setattr__(self, name, value)


class _Part(_ReadSurface):
    def __getattribute__(self, name):
        if name in {
            "GetPathName", "GetType", "IsOpenedReadOnly", "GetSaveFlag", "GetBodies2", "FeatureByName",
        } and not object.__getattribute__(self, "__dict__").get("_alive", True):
            raise AssertionError("stale unloaded source IModelDoc2 used")
        return object.__getattribute__(self, name)


class _Point:
    def __init__(self, coordinates):
        self.ArrayData = tuple(coordinates)

    def MultiplyTransform(self, top):
        x, y, z = self.ArrayData
        return _Point((x, z, -y) if top else (x, y, z))


class _View(_ReadSurface):
    def __init__(self, orientation, model, configuration):
        self.alive = True
        self.orientation = orientation
        self.ReferencedDocument = model
        self.ReferencedConfiguration = configuration
        self.model_name = model.GetPathName()
        self.displays = []
        self.edges = []

    def __getattribute__(self, name):
        if name in {
            "GetOrientationName", "ReferencedDocument", "ReferencedConfiguration",
            "GetReferencedModelName", "GetFirstDisplayDimension5", "GetOutline",
        } and not object.__getattribute__(self, "alive"):
            raise AssertionError("stale authoring IView used after close")
        return object.__getattribute__(self, name)

    def GetOrientationName(self):
        return self.orientation

    def GetReferencedModelName(self):
        return self.model_name

    def GetFirstDisplayDimension5(self):
        return self.displays[0] if self.displays else None

    def GetOutline(self):
        return (0.02, 0.02, 0.04, 0.04)


class _Display(_ReadSurface):
    def __init__(self, label, native, view, attached, *, units, precision):
        self.view = view
        self.native = native
        self.selection_name = f"{label}@saved-washer-view"
        self.Type2 = 11 if label == source.THICKNESS else 6
        self.ShowParenthesis = False
        self.ShowDimensionValue = True
        self.use_document = False
        self.units = units
        self.precision = precision
        self.tolerance_precision = precision
        self.fraction = 1
        self.fraction_value = 0
        self.round_to_fraction = False
        self.override = False
        self.text = {1: "(" if label == source.THICKNESS else "(<MOD-DIAM>", 2: " mm)", 4: ""}
        self.annotation = _ReadSurface(
            Owner=view, OwnerType=0, Visible=1, attached=tuple(attached), dangling=False,
        )
        annotation = self.annotation
        annotation.IsDangling = lambda: annotation.dangling
        annotation.GetAttachedEntities3 = lambda: annotation.attached
        annotation.GetAttachedEntityCount3 = lambda: len(annotation.attached)
        annotation.GetAttachedEntityTypes = lambda: (11,) * len(annotation.attached)

    def __getattribute__(self, name):
        if name.startswith("Get") or name in ("Type2", "ShowParenthesis", "ShowDimensionValue"):
            view = object.__getattribute__(self, "view")
            if view is not None and not view.alive:
                raise AssertionError("stale authoring IDisplayDimension used after close")
        return object.__getattribute__(self, name)

    def GetNameForSelection(self):
        return self.selection_name

    def GetDimension2(self, _index):
        return self.native

    def GetAnnotation(self):
        return self.annotation

    def GetNext5(self):
        index = self.view.displays.index(self) + 1
        return self.view.displays[index] if index < len(self.view.displays) else None

    def GetUseDocUnits(self):
        return self.use_document

    def GetUnits(self):
        return self.units

    def GetPrimaryPrecision2(self):
        return self.precision

    def GetPrimaryTolPrecision2(self):
        return self.tolerance_precision

    def GetFractionBase(self):
        return self.fraction

    def GetFractionValue(self):
        return self.fraction_value

    def GetRoundToFraction(self):
        return self.round_to_fraction

    def SetUnits2(self, use_document, units, base, denominator, rounding, _decimal_rounding):
        self.use_document = use_document
        self.units = units
        self.fraction = base
        self.fraction_value = denominator
        self.round_to_fraction = rounding
        return 0

    def GetOverride(self):
        return self.override

    def GetText(self, part):
        return self.text[part]


class _Drawing(_ReadSurface):
    def __init__(self, path, views):
        self.path = path
        self.kind = 3
        self.read_only = True
        self.title = path.name
        # GetViews includes one sheet-format IView before the four model views.
        self.sheets = [(object(), *views.values())]

    def GetPathName(self):
        return str(self.path)

    def GetType(self):
        return self.kind

    def IsOpenedReadOnly(self):
        return self.read_only

    def GetTitle(self):
        return self.title

    def GetViews(self):
        return self.sheets

    def __getattr__(self, name):
        raise AssertionError(f"saved reader called unsupported/mutating document API {name}")


class _App:
    def __init__(self, drawing, model):
        self.drawing = drawing
        self.loaded = {model.GetPathName(): model}
        self.open_calls = []
        self.close_calls = []
        self.on_open = None
        self.on_close = None
        self.keep_open = False
        self.open_result = lambda: (self.drawing, 0, 0)

    def IsSame(self, first, second):
        return 1 if first is second else 0

    def GetOpenDocumentByName(self, path):
        return self.loaded.get(path)

    def OpenDoc6(self, *args):
        self.open_calls.append(args)
        self.loaded[str(self.drawing.path)] = self.drawing
        if self.on_open is not None:
            self.on_open()
        # Seal the freshly loaded document/view/display/native/annotation state.
        # Absent mutation methods and guarded properties refuse all reader writes.
        for view in self.drawing.sheets[0][1:]:
            for display in view.displays:
                for surface in (display, display.native, display.annotation, display.native.Tolerance):
                    object.__setattr__(surface, "_saved_read", True)
            object.__setattr__(view, "_saved_read", True)
        object.__setattr__(self.drawing, "_saved_read", True)
        return self.open_result()

    def CloseDoc(self, title):
        assert title == self.drawing.title
        self.close_calls.append(title)
        if self.on_close is not None:
            self.on_close()
        if not self.keep_open:
            self.loaded.pop(str(self.drawing.path), None)

    def __getattr__(self, name):
        raise AssertionError(f"saved reader called unsupported/mutating application API {name}")


class _Adapter:
    def __init__(self, app):
        self.swApp = app
        self.model_clear_calls = []
        self._closed_model = None

    @property
    def currentModel(self):
        raise AssertionError("saved washer proof must not depend on adapter.currentModel")

    @currentModel.setter
    def currentModel(self, value):
        if value is not None:
            raise AssertionError("saved washer proof must not assign a fresh or stale adapter model")
        self.model_clear_calls.append(value)
        self._closed_model = None


def _circle_edge(axis, station_mm, diameter_mm):
    center = (0.0, station_mm / 1000.0, 0.0) if axis == "y" else (0.0, 0.0, station_mm / 1000.0)
    normal = (0.0, 1.0, 0.0) if axis == "y" else (0.0, 0.0, 1.0)
    curve = SimpleNamespace(
        CircleParams=(*center, *normal, diameter_mm / 2000.0),
        IsCircle=lambda: True, IsLine=lambda: False,
    )
    return SimpleNamespace(GetCurve=lambda: curve)


def _point(x, y, z):
    return SimpleNamespace(X=x, Y=y, Z=z)


@pytest.fixture(params=(("y", True), ("z", True), ("y", False), ("z", False)),
                ids=("y-all-banded", "z-all-banded", "y-rim-refs", "z-rim-refs"))
def saved_washer(request, tmp_path, monkeypatch):
    axis, all_banded = request.param
    for module in (washer, source, supplier, edges, attachment):
        monkeypatch.setattr(module, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(source, "double_array", tuple)
    monkeypatch.setattr(edges, "visible_view_entities", lambda view, _kind, **_kw: view.edges)
    drawing_path = tmp_path / "washer.SLDDRW"
    drawing_path.write_bytes(b"independently seeded persisted drawing bytes")
    source_path = tmp_path / "washer.SLDPRT"
    source_path.write_bytes(b"source must never be saved or changed")
    path_state = SimpleNamespace(path=source_path)
    body_edges = [_circle_edge(axis, station, diameter)
                  for station in (0.0, VALUES[source.THICKNESS])
                  for diameter in (VALUES[source.OUTER_DIAMETER], VALUES[source.BORE_DIAMETER])]
    body = SimpleNamespace(GetEdges=lambda: body_edges)
    features = {}
    model = _Part(
        GetPathName=lambda: str(path_state.path), GetType=lambda: 1, IsOpenedReadOnly=lambda: True,
        GetSaveFlag=lambda: False,
        GetBodies2=lambda _kind, _hidden: (body,), FeatureByName=lambda name: features.get(name),
    )
    original = {name: _View(name, model, f"Authoring{name[1:]}Config") for name in ORIENTATIONS}
    fresh = {name: _View(name, model, original[name].ReferencedConfiguration) for name in ORIENTATIONS}
    drawing = _Drawing(drawing_path, fresh)
    app = _App(drawing, model)
    # Native source coordinate conversion still executes _model_point and its
    # independent marshalled-coordinate check; only the math COM object is fake.
    app.GetMathUtility = lambda: SimpleNamespace(CreatePoint=lambda coords: _Point(coords))
    adapter = _Adapter(app)
    source_displays = {}
    source_natives = {}
    source_entities = {}
    for label in VALUES:
        feature_name, native_name = source.SOURCE_DIMENSIONS[label]
        if feature_name not in features:
            top = (axis == "y") != (label == source.THICKNESS)
            sketch = SimpleNamespace(ModelToSketchTransform=SimpleNamespace(Inverse=lambda top=top: top))
            features[feature_name] = SimpleNamespace(
                Name=feature_name, dimensions={},
                GetSpecificFeature2=lambda sketch=sketch: sketch,
            )
        feature = features[feature_name]
        if label == source.THICKNESS:
            sign = 1.0 if axis == "y" else -1.0
            points = (_point(0.005, 0.0, 0.0), _point(0.005, sign * 0.00091, 0.0))
            segment = SimpleNamespace(
                ConstructionGeometry=True, GetType=lambda: 0,
                GetStartPoint2=lambda: points[0], GetEndPoint2=lambda: points[1],
            )
            source_entities[label] = points
            feature.GetSpecificFeature2().GetSketchSegments = lambda: (segment,)
        else:
            diameter = VALUES[label]
            segment = SimpleNamespace(
                ConstructionGeometry=True, GetType=lambda: 1, IsCircle=lambda: 1,
                GetCenterPoint2=lambda: _point(0.0, 0.0, 0.0),
                GetRadius=lambda diameter=diameter: diameter / 2000.0,
            )
            source_entities[label] = (segment,)
    face_segments = tuple(source_entities[label][0]
                          for label in (source.OUTER_DIAMETER, source.BORE_DIAMETER))
    features[source.FACE_FEATURE].GetSpecificFeature2().GetSketchSegments = lambda: face_segments
    bands = {label: (value - 0.1, value + 0.1, "limits") for label, value in VALUES.items()
             if all_banded or label == source.THICKNESS}
    precision = {label: 2 for label in VALUES}
    for label, value in VALUES.items():
        feature_name, native_name = source.SOURCE_DIMENSIONS[label]
        tolerance = _ReadSurface(Type=3 if label in bands else 0, minimum=-0.0001, maximum=0.0001)
        tolerance.GetMinValue = lambda tolerance=tolerance: tolerance.minimum
        tolerance.GetMaxValue = lambda tolerance=tolerance: tolerance.maximum
        native = _ReadSurface(
            FullName=f"{native_name}@{feature_name}@washer.SLDPRT", SystemValue=value / 1000.0,
            Tolerance=tolerance, GetFeatureOwner=lambda feature=features[feature_name]: feature,
        )
        source_natives[label] = native
        source_displays[label] = _Display(label, native, None, source_entities[label], units=0, precision=2)
        features[feature_name].dimensions[native_name] = (source_displays[label], native)

    def named_dimensions(_adapter, feature_name, names, *, feature):
        # Resolve from the explicitly supplied source model's feature, never
        # from a saved display or a global display-name-derived answer.
        assert feature.Name == feature_name
        if not names <= feature.dimensions.keys():
            raise RuntimeError(f"{feature_name}: independently seeded source dimension is missing")
        return {name: feature.dimensions[name] for name in names}

    monkeypatch.setattr(source, "_named_dimensions", named_dimensions)
    monkeypatch.setattr(washer, "_named_dimensions", named_dimensions)
    face_orientation = "*Top" if axis == "y" else "*Front"
    side_orientation = "*Front" if axis == "y" else "*Top"
    for collection in (original, fresh):
        for view in collection.values():
            view.edges = list(body_edges)
        for label, value in VALUES.items():
            view = collection[side_orientation if label == source.THICKNESS else face_orientation]
            if label in bands:
                native, attached = source_natives[label], source_entities[label]
            else:
                tolerance = _ReadSurface(Type=0)
                native_name = "D1" if label == source.OUTER_DIAMETER else "D2"
                model_name = "Drawing1.SLDDRW" if collection is original else drawing_path.name
                native = _ReadSurface(
                    FullName=f"{native_name}@DrawingView@{model_name}",
                    SystemValue=value / 1000.0, Tolerance=tolerance,
                )
                edge_index = 2 if label == source.OUTER_DIAMETER else 3
                attached = (body_edges[edge_index],)
            view.displays.append(_Display(label, native, view, attached, units=0, precision=2))
    references = tuple(washer._reference(display, view, label, VALUES[label], imported=label in bands)
                       for label in VALUES for view in original.values() for display in view.displays
                       if display.selection_name == f"{label}@saved-washer-view")
    arguments = dict(axis=axis, bore_mm=4.0, outer_mm=10.0, thickness_mm=0.91,
                     units="mm", precision=precision, bands=bands)
    proof = washer._supplier_washer_proof(adapter, original, references, **arguments)
    messages = []
    monkeypatch.setattr(washer._telemetry, "info", messages.append)

    def invalidate():
        for view in original.values():
            view.alive = False

    return SimpleNamespace(
        proof=proof, adapter=adapter, app=app, model=model, original=original, fresh=fresh,
        saved_source=model,
        references=references, arguments=arguments, drawing=drawing, path=drawing_path,
        source_path=source_path, path_state=path_state, body_edges=body_edges,
        source_entities=source_entities, source_natives=source_natives,
        source_displays=source_displays, features=features, messages=messages,
        invalidate=invalidate, face=face_orientation, side=side_orientation,
        original_bytes=drawing_path.read_bytes(), source_bytes=source_path.read_bytes(),
    )


def _display(case, label):
    return next(display for view in case.fresh.values() for display in view.displays
                if display.selection_name == f"{label}@saved-washer-view")


def _assert_closed_unchanged(case):
    assert case.app.GetOpenDocumentByName(str(case.path)) is None
    assert case.app.close_calls == [case.path.name]
    assert case.app.GetOpenDocumentByName(str(case.source_path)) is case.saved_source
    assert case.path.read_bytes() == case.original_bytes
    assert case.source_path.read_bytes() == case.source_bytes
    assert case.adapter.model_clear_calls == [None]


def test_callable_then_saved_roundtrip_uses_only_fresh_contexts(saved_washer):
    case = saved_washer
    assert isinstance(case.proof, washer.SupplierWasherProof)
    case.proof()  # The original settled-check callable contract still works.
    case.invalidate()
    case.proof.saved_check(case.adapter, case.path)
    assert case.app.open_calls == [(str(case.path), 3, 1 | 2, "", 0, 0)]
    _assert_closed_unchanged(case)
    assert len(case.messages) == 1
    receipt = json.loads(case.messages[0].split(": ", 1)[1])
    assert receipt["drawing_path"] == str(case.path)
    assert len(receipt["views"]) == 4
    assert {entry["orientation"] for entry in receipt["views"]} == set(ORIENTATIONS)
    assert {entry["source_path"] for entry in receipt["views"]} == {str(case.source_path)}
    assert sorted(entry["system_value"] for entry in receipt["dimensions"]) == pytest.approx([0.00091, 0.004, 0.01])
    assert {entry["suffix"] for entry in receipt["dimensions"]} == {" mm)"}
    assert receipt["read_only"] is True
    assert {entry["attachment_count"] for entry in receipt["dimensions"]} == {1, 2}
    assert all(not entry["dangling"] and not entry["override"] for entry in receipt["dimensions"])
    assert {entry["fraction_value"] for entry in receipt["dimensions"]} == {0}
    assert all(entry["round_to_fraction"] is False for entry in receipt["dimensions"])
    expected_identities = {1} if source.OUTER_DIAMETER in case.arguments["bands"] else {1, None}
    assert {entry["source_native_identity"] for entry in receipt["dimensions"]} == expected_identities
    assert receipt["source_resident_before_open"] is True
    assert receipt["source_save_flag"] is False


def test_unloaded_authoring_source_is_reacquired_from_drawing_autoload(saved_washer):
    case = saved_washer
    reloaded = _Part(**vars(case.model))
    case.app.loaded.pop(str(case.source_path))
    case.model._alive = False
    case.saved_source = reloaded
    case.invalidate()

    def autoload():
        case.app.loaded[str(case.source_path)] = reloaded
        for view in case.fresh.values():
            view.ReferencedDocument = reloaded

    case.app.on_open = autoload
    case.proof.saved_check(case.adapter, case.path)
    assert reloaded is not case.model
    assert case.app.open_calls == [(str(case.path), 3, 1 | 2, "", 0, 0)]
    _assert_closed_unchanged(case)
    receipt = json.loads(case.messages[0].split(": ", 1)[1])
    assert receipt["source_resident_before_open"] is False
    assert receipt["source_save_flag"] is False


@pytest.mark.parametrize("fault", ("missing", "wrong-path", "wrong-type", "writable", "unreadable-readonly"))
def test_saved_source_context_requires_captured_path_native_part_and_readonly(saved_washer, fault):
    case = saved_washer
    loaded = _Part(**vars(case.model))
    case.saved_source = loaded
    case.app.loaded[str(case.source_path)] = loaded
    for view in case.fresh.values():
        view.ReferencedDocument = loaded
    if fault == "missing":
        case.app.loaded.pop(str(case.source_path))
        case.saved_source = None
    elif fault == "wrong-path":
        loaded.GetPathName = lambda: str(case.path.with_name("other-source.SLDPRT"))
    elif fault == "wrong-type":
        loaded.GetType = lambda: 3
    else:
        loaded.IsOpenedReadOnly = lambda: False if fault == "writable" else None
    case.invalidate()
    with pytest.raises(RuntimeError, match="saved washer source (context|path)"):
        case.proof.saved_check(case.adapter, case.path)
    _assert_closed_unchanged(case)
    assert not case.messages


def _exception_receipt(error):
    receipts = []
    for note in getattr(error, "__notes__", ()):
        start = note.find("{")
        if start >= 0:
            try:
                receipts.append(json.loads(note[start:]))
            except json.JSONDecodeError:
                pass
    assert len(receipts) == 1, getattr(error, "__notes__", ())
    return receipts[0]


def _autoload_source(case, loaded):
    case.app.loaded.pop(str(case.source_path))
    case.model._alive = False
    case.saved_source = loaded

    def autoload():
        case.app.loaded[str(case.source_path)] = loaded
        for view in case.fresh.values():
            view.ReferencedDocument = loaded

    case.app.on_open = autoload


@pytest.mark.parametrize("resident", (True, False), ids=("resident", "autoload"))
@pytest.mark.parametrize("flag", (True, 0, 0.0, None, "False"),
                         ids=("dirty", "integer-zero", "float-zero", "missing", "string-false"))
def test_saved_source_requires_literal_clean_save_flag(saved_washer, resident, flag):
    case = saved_washer
    loaded = case.model if resident else _Part(**vars(case.model))
    loaded.GetSaveFlag = lambda: flag
    if not resident:
        _autoload_source(case, loaded)
    case.invalidate()
    with pytest.raises(RuntimeError) as caught:
        case.proof.saved_check(case.adapter, case.path)
    _assert_closed_unchanged(case)
    assert not case.messages
    receipt = _exception_receipt(caught.value)
    assert receipt["source_resident_before_open"] is resident
    assert type(receipt["source_save_flag"]) is type(flag)
    assert receipt["source_save_flag"] == flag


def test_native_source_identity_requires_integer_one_not_boolean_true(saved_washer):
    case = saved_washer
    native = case.source_natives[source.THICKNESS]
    original_is_same = case.app.IsSame

    def is_same(first, second):
        if first is native and second is native:
            return True
        return original_is_same(first, second)

    case.app.IsSame = is_same
    case.invalidate()
    with pytest.raises(RuntimeError) as caught:
        case.proof.saved_check(case.adapter, case.path)
    _assert_closed_unchanged(case)
    assert not case.messages
    receipt = _exception_receipt(caught.value)
    selection_name = _display(case, source.THICKNESS).selection_name
    entry = next(item for item in receipt["dimensions"] if item["selection_name"] == selection_name)
    assert entry["source_native_identity"] is True


@pytest.mark.parametrize("resident", (True, False), ids=("resident", "autoload"))
def test_source_save_flag_read_error_preserves_exception_and_actual_failed_field(
    saved_washer, resident,
):
    case = saved_washer
    loaded = case.model if resident else _Part(**vars(case.model))
    failure = RuntimeError("actual native GetSaveFlag read failed: source-state-sentinel")

    def refuse_read():
        raise failure

    loaded.GetSaveFlag = refuse_read
    if not resident:
        _autoload_source(case, loaded)
    case.invalidate()
    with pytest.raises(RuntimeError) as caught:
        case.proof.saved_check(case.adapter, case.path)
    assert caught.value is failure
    _assert_closed_unchanged(case)
    assert not case.messages
    receipt = _exception_receipt(caught.value)
    assert receipt["source_resident_before_open"] is resident
    field = receipt["source_save_flag"]
    assert isinstance(field, dict)
    assert str(failure) in field["read_error"]


@pytest.mark.parametrize("getter, field", (
    ("GetUnits", "units"), ("GetPrimaryPrecision2", "precision"),
))
def test_saved_display_getter_error_preserves_exception_and_actual_failed_field(
    saved_washer, getter, field,
):
    case = saved_washer
    display = _display(case, source.THICKNESS)
    failure = RuntimeError(f"actual native {getter} read failed: display-field-sentinel")

    def refuse_read():
        raise failure

    setattr(display, getter, refuse_read)
    case.invalidate()
    with pytest.raises(RuntimeError) as caught:
        case.proof.saved_check(case.adapter, case.path)
    assert caught.value is failure
    _assert_closed_unchanged(case)
    assert not case.messages
    receipt = _exception_receipt(caught.value)
    entry = next(item for item in receipt["dimensions"]
                 if item["selection_name"] == display.selection_name)
    assert isinstance(entry[field], dict)
    assert str(failure) in entry[field]["read_error"]


def test_failure_receipt_reports_wrong_saved_units_not_authored_source_echo(saved_washer):
    case = saved_washer
    display = _display(case, source.THICKNESS)
    display.units = 3
    assert case.source_displays[source.THICKNESS].units == 0
    case.invalidate()
    with pytest.raises(RuntimeError, match="native supplier presentation differs") as caught:
        case.proof.saved_check(case.adapter, case.path)
    _assert_closed_unchanged(case)
    assert not case.messages
    receipt = _exception_receipt(caught.value)
    entry = next(item for item in receipt["dimensions"]
                 if item["selection_name"] == display.selection_name)
    assert type(entry["units"]) is int
    assert entry["units"] == 3



def test_matching_late_authoring_config_cannot_replace_captured_expectation(saved_washer):
    case = saved_washer
    case.original["*Right"].ReferencedConfiguration = "LateWrongConfig"
    case.fresh["*Right"].ReferencedConfiguration = "LateWrongConfig"
    case.invalidate()
    with pytest.raises(RuntimeError, match="source configuration changed"):
        case.proof.saved_check(case.adapter, case.path)
    _assert_closed_unchanged(case)


@pytest.mark.parametrize("configuration", ("", None, 7))
def test_authoring_capture_refuses_unreadable_source_configuration(saved_washer, configuration):
    case = saved_washer
    case.original["*Right"].ReferencedConfiguration = configuration
    with pytest.raises(RuntimeError, match="authoring washer source/view identity differs"):
        washer._supplier_washer_proof(
            case.adapter, case.original, case.references, **case.arguments,
        )
    assert not case.app.open_calls
    assert not case.app.close_calls


def test_saved_reader_surfaces_are_write_traps(saved_washer, monkeypatch):
    case = saved_washer
    def write_instead_of_check(*_args, **_kwargs):
        # Even a same-value assignment must be refused rather than treated as
        # harmless presentation repair on a supposed read-only proof path.
        _display(case, source.THICKNESS).ShowParenthesis = False
    monkeypatch.setattr(washer, "assert_supplier_washer_dimensions", write_instead_of_check)
    with pytest.raises(AssertionError, match="saved reader wrote native property"):
        case.proof.saved_check(case.adapter, case.path)
    _assert_closed_unchanged(case)


def test_public_authoring_return_exposes_saved_proof(saved_washer, monkeypatch):
    case = saved_washer
    def curate(_adapter, view, **_kwargs):
        return [SimpleNamespace(GetSpecificAnnotation=lambda display=display: display)
                for display in view.displays]
    monkeypatch.setattr(washer, "curate_view_dimensions", curate)
    monkeypatch.setattr(washer, "dimension_name", lambda _adapter, annotation:
                        source.SOURCE_DIMENSIONS[next(label for label in VALUES
                            if annotation.GetSpecificAnnotation().selection_name == f"{label}@saved-washer-view")][1])
    # Isolate only authoring operations; saved validation below stays real for
    # both imported witnesses and the explicitly permitted physical-rim refs.
    monkeypatch.setattr(washer, "_native_diameter", lambda _adapter, view, rim, **_kw:
                        next(display for display in view.displays
                             if display.annotation.attached == (rim,)))
    monkeypatch.setattr(washer, "supplier_reference_dimension", lambda _adapter, display, **_kw: display)
    proof = washer.supplier_washer_dimensions(case.adapter, case.original, **case.arguments)
    assert isinstance(proof, washer.SupplierWasherProof)
    case.invalidate()
    proof.saved_check(case.adapter, case.path)
    _assert_closed_unchanged(case)


@pytest.mark.parametrize("fault", ("identity", "document-path", "view-path", "configuration"))
def test_saved_source_is_checked_against_captured_authoring_expectations(saved_washer, fault):
    case = saved_washer
    view = case.fresh["*Right"]
    if fault == "identity":
        # Same path, distinct model: matching reopened views cannot self-certify.
        other = SimpleNamespace(GetPathName=lambda: str(case.source_path))
        for saved_view in case.fresh.values():
            saved_view.ReferencedDocument = other
    elif fault == "document-path":
        case.path_state.path = case.path.with_name("another-source.SLDPRT")
    elif fault == "view-path":
        view.model_name = str(case.path.with_name("another-source.SLDPRT"))
    else:
        view.ReferencedConfiguration = "WrongConfiguration"
    case.invalidate()
    with pytest.raises(RuntimeError, match="source (identity|path|configuration)"):
        case.proof.saved_check(case.adapter, case.path)
    _assert_closed_unchanged(case)
    assert not case.messages


@pytest.mark.parametrize("fault", ("missing-view", "extra-view", "duplicate", "unknown", "extra-sheet"))
def test_saved_view_census_refuses_unexpected_native_views(saved_washer, fault):
    case = saved_washer
    sheet = list(case.drawing.sheets[0])
    if fault == "missing-view":
        sheet.pop()
    elif fault == "extra-view":
        sheet.append(case.fresh["*Right"])
    elif fault == "duplicate":
        case.fresh["*Right"].orientation = "*Front"
    elif fault == "unknown":
        case.fresh["*Right"].orientation = "*Back"
    else:
        case.drawing.sheets.append((object(),))
    case.drawing.sheets[0] = tuple(sheet)
    case.invalidate()
    with pytest.raises(RuntimeError, match="(four model views|orientation|one sheet)"):
        case.proof.saved_check(case.adapter, case.path)
    _assert_closed_unchanged(case)


@pytest.mark.parametrize("fault, message", (
    ("missing-dimension", "semantic native display census"), ("extra-dimension", "exports"),
    ("full-name", "semantic native display census"),
    ("wrong-value", "(native value|model supplier dimension differs)"), ("units", "native supplier presentation differs"),
    ("precision", "native supplier presentation differs"), ("prefix", "native supplier presentation differs"),
    ("override", "native supplier presentation differs"), ("dangling", "sound native attachment"),
    ("wrong-source-attachment", "independently resolved source entity"),
    ("wrong-native-owner", "named model witness"),
    ("band", "band/type/precision changed"), ("body", "four circular end rims"),
    ("visible-rim", "no visible circle"), ("wrong-view", "semantic native display census"),
))
def test_saved_corruption_is_refused_by_real_native_assertions(saved_washer, fault, message):
    case = saved_washer
    thickness = _display(case, source.THICKNESS)
    if fault == "missing-dimension":
        case.fresh[case.side].displays.clear()
    elif fault == "extra-dimension":
        case.fresh["*Right"].displays.append(thickness)
    elif fault == "full-name":
        thickness.native = _ReadSurface(**vars(thickness.native))
        thickness.native.FullName = "DifferentNative@OtherFeature@washer.SLDPRT"
    elif fault == "wrong-value":
        if source.OUTER_DIAMETER in case.arguments["bands"]:
            thickness.native.SystemValue = 0.00191
        else:
            _display(case, source.OUTER_DIAMETER).native.SystemValue = 0.011
    elif fault == "units":
        thickness.units = 3
    elif fault == "precision":
        thickness.precision = 7
    elif fault == "prefix":
        thickness.text[1] = "wrong reference prefix"
    elif fault == "override":
        thickness.override = True
    elif fault == "dangling":
        thickness.annotation.dangling = True
    elif fault == "wrong-source-attachment":
        thickness.annotation.attached = (object(), object())
    elif fault == "wrong-native-owner":
        thickness.native.GetFeatureOwner = lambda: object()
    elif fault == "band":
        thickness.native.Tolerance.minimum = -0.002
    elif fault == "body":
        case.body_edges.pop()
    elif fault == "visible-rim":
        case.fresh[case.face].edges = [case.body_edges[0], case.body_edges[1]]
    else:
        case.fresh[case.side].displays.remove(thickness)
        case.fresh["*Right"].displays.append(thickness)
        thickness.view = case.fresh["*Right"]
        thickness.annotation.Owner = case.fresh["*Right"]
    case.invalidate()
    with pytest.raises(RuntimeError, match=message):
        case.proof.saved_check(case.adapter, case.path)
    _assert_closed_unchanged(case)
    assert not case.messages


def test_diameter_requires_exact_source_circle_or_physical_rim(saved_washer):
    case = saved_washer
    _display(case, source.OUTER_DIAMETER).annotation.attached = (case.body_edges[0],)
    case.invalidate()
    message = ("independently resolved source entity" if source.OUTER_DIAMETER in case.arguments["bands"]
               else "semantic native display census")
    with pytest.raises(RuntimeError, match=message):
        case.proof.saved_check(case.adapter, case.path)
    _assert_closed_unchanged(case)


def test_wrong_named_source_is_not_self_certified_from_saved_names(saved_washer):
    case = saved_washer
    display = _display(case, source.THICKNESS)
    display.selection_name = "CorruptButConsistentSavedName"
    # Selection/full names are fresh lookup metadata, not authority to change
    # the captured label's required SOURCE_DIMENSIONS feature/dimension owner.
    display.native.FullName = "SupplierThickness@RenamedWitness@washer.SLDPRT"
    case.invalidate()
    with pytest.raises(RuntimeError, match="display census"):
        case.proof.saved_check(case.adapter, case.path)
    _assert_closed_unchanged(case)


def test_same_named_native_clone_cannot_impersonate_actual_source_dimension(saved_washer):
    case = saved_washer
    display = _display(case, source.THICKNESS)
    actual_source_native = case.source_natives[source.THICKNESS]
    display.native = _ReadSurface(**vars(actual_source_native))
    assert display.native is not actual_source_native
    assert display.native.FullName == actual_source_native.FullName
    assert display.native.GetFeatureOwner() is actual_source_native.GetFeatureOwner()
    assert display.annotation.attached == case.source_entities[source.THICKNESS]
    case.invalidate()
    with pytest.raises(RuntimeError, match="not its actual native source"):
        case.proof.saved_check(case.adapter, case.path)
    _assert_closed_unchanged(case)
    assert not case.messages


def test_saved_reader_validates_actual_source_presentation_independently(saved_washer):
    case = saved_washer
    case.source_displays[source.THICKNESS].units = 3
    assert _display(case, source.THICKNESS).units == 0
    case.invalidate()
    with pytest.raises(RuntimeError, match="model supplier units/precision/reference ink changed"):
        case.proof.saved_check(case.adapter, case.path)
    _assert_closed_unchanged(case)


def test_saved_source_dimension_lookup_requires_actual_named_feature(saved_washer):
    case = saved_washer
    case.features.pop(source.THICKNESS_FEATURE)
    case.invalidate()
    with pytest.raises(RuntimeError, match="saved supplier source feature is missing"):
        case.proof.saved_check(case.adapter, case.path)
    _assert_closed_unchanged(case)


def test_receipt_reads_fraction_getters_instead_of_echoing_authored_values(saved_washer):
    case = saved_washer
    display = _display(case, source.THICKNESS)
    display.fraction_value = 16
    display.round_to_fraction = True
    case.invalidate()
    case.proof.saved_check(case.adapter, case.path)
    receipt = json.loads(case.messages[0].split(": ", 1)[1])
    entry = next(item for item in receipt["dimensions"]
                 if item["selection_name"] == display.selection_name)
    assert entry["fraction_value"] == 16
    assert entry["round_to_fraction"] is True
    assert entry["source_native_identity"] == 1
    _assert_closed_unchanged(case)


def test_saved_selection_names_and_drawing_owned_full_names_can_change(saved_washer):
    case = saved_washer
    changed_drawing_names = 0
    for reference in case.references:
        display = _display(case, reference.label)
        display.selection_name = f"SavedLookupFor{reference.label}@washer.SLDDRW"
        if not reference.imported:
            assert reference.full_name.endswith("@Drawing1.SLDDRW")
            assert display.native.FullName.endswith("@washer.SLDDRW")
            assert display.native.FullName != reference.full_name
            changed_drawing_names += 1
    assert changed_drawing_names == (0 if source.OUTER_DIAMETER in case.arguments["bands"] else 2)
    case.invalidate()
    case.proof.saved_check(case.adapter, case.path)
    _assert_closed_unchanged(case)
    receipt = json.loads(case.messages[0].split(": ", 1)[1])
    assert all(entry["selection_name"].startswith("SavedLookupFor") for entry in receipt["dimensions"])


def test_duplicate_semantic_dimension_is_refused_without_using_values_or_text(saved_washer):
    case = saved_washer
    view = case.fresh[case.face]
    outer = _display(case, source.OUTER_DIAMETER)
    duplicate = _Display(
        source.OUTER_DIAMETER, outer.native, view, outer.annotation.attached,
        units=0, precision=2,
    )
    duplicate.selection_name = "DistinctLookupForDuplicate"
    # Keep the expected visible count while replacing the bore with another OD.
    view.displays = [outer, duplicate]
    case.invalidate()
    with pytest.raises(RuntimeError, match="semantic native display census"):
        case.proof.saved_check(case.adapter, case.path)
    _assert_closed_unchanged(case)


def test_precision_and_band_expectations_are_snapshotted(saved_washer):
    case = saved_washer
    case.arguments["precision"][source.THICKNESS] = 7
    case.arguments["bands"][source.THICKNESS] = (0.1, 1.9, "bilateral")
    case.invalidate()
    case.proof.saved_check(case.adapter, case.path)
    _assert_closed_unchanged(case)


def test_already_open_target_is_neither_reused_nor_closed(saved_washer):
    case = saved_washer
    case.app.loaded[str(case.path)] = case.drawing
    with pytest.raises(RuntimeError, match="finalize and close"):
        case.proof.saved_check(case.adapter, case.path)
    assert not case.app.open_calls
    assert not case.app.close_calls
    assert case.app.loaded[str(case.path)] is case.drawing
    assert case.path.read_bytes() == case.original_bytes


@pytest.mark.parametrize("read_only", (False, None, 1, "True"))
def test_open_requires_native_true_readonly_state(saved_washer, read_only):
    case = saved_washer
    case.drawing.read_only = read_only
    with pytest.raises(RuntimeError, match="did not open read-only"):
        case.proof.saved_check(case.adapter, case.path)
    _assert_closed_unchanged(case)


def test_readonly_getter_failure_is_not_accepted(saved_washer):
    case = saved_washer
    failure = RuntimeError("native readonly getter failed")
    def refuse():
        raise failure
    case.drawing.IsOpenedReadOnly = refuse
    with pytest.raises(RuntimeError) as caught:
        case.proof.saved_check(case.adapter, case.path)
    assert caught.value is failure
    _assert_closed_unchanged(case)


@pytest.mark.parametrize("result", ("model-only", "short-tuple", "list", "bool-error", "bad-warning", "load-error", "null-model"))
def test_open_requires_exact_generated_native_return(saved_washer, result):
    case = saved_washer
    results = {
        "model-only": case.drawing, "short-tuple": (case.drawing, 0),
        "list": [case.drawing, 0, 0], "bool-error": (case.drawing, False, 0),
        "bad-warning": (case.drawing, 0, "0"), "load-error": (case.drawing, 2, 4),
        "null-model": (None, 0, 0),
    }
    case.app.open_result = lambda: results[result]
    with pytest.raises(RuntimeError, match="(OpenDoc6|native open failed)"):
        case.proof.saved_check(case.adapter, case.path)
    _assert_closed_unchanged(case)


def test_native_warning_is_recorded_without_being_silently_zeroed(saved_washer):
    case = saved_washer
    case.app.open_result = lambda: (case.drawing, 0, 128)
    case.proof.saved_check(case.adapter, case.path)
    receipt = json.loads(case.messages[0].split(": ", 1)[1])
    assert receipt["open_warnings"] == 128
    _assert_closed_unchanged(case)


def test_open_exception_after_loading_still_closes_only_owned_target(saved_washer):
    case = saved_washer
    failure = RuntimeError("native open raised after loading")
    def refuse():
        raise failure
    case.app.on_open = refuse
    with pytest.raises(RuntimeError) as caught:
        case.proof.saved_check(case.adapter, case.path)
    assert caught.value is failure
    _assert_closed_unchanged(case)


@pytest.mark.parametrize("fault", ("path", "type", "title", "identity"))
def test_cleanup_refuses_to_close_unverified_document(saved_washer, fault):
    case = saved_washer
    if fault == "path":
        case.drawing.GetPathName = lambda: str(case.path.with_name("other.SLDDRW"))
    elif fault == "type":
        case.drawing.kind = 1
    elif fault == "title":
        case.drawing.title = ""
    else:
        returned = _Drawing(case.path, case.fresh)
        case.app.open_result = lambda: (returned, 0, 0)
    with pytest.raises(RuntimeError, match="(another document path|native drawing document|empty document title|different loaded identity)"):
        case.proof.saved_check(case.adapter, case.path)
    assert not case.app.close_calls
    assert case.app.loaded[str(case.path)] is case.drawing
    assert case.path.read_bytes() == case.original_bytes
    assert not case.messages


def test_cleanup_requires_target_lookup_to_be_empty(saved_washer):
    case = saved_washer
    case.app.keep_open = True
    with pytest.raises(RuntimeError, match="did not close"):
        case.proof.saved_check(case.adapter, case.path)
    assert case.app.close_calls == [case.path.name]
    assert not case.messages


def test_hash_invariance_is_checked_after_close(saved_washer):
    case = saved_washer
    case.app.on_close = lambda: case.path.write_bytes(b"injected unexpected persisted mutation")
    with pytest.raises(RuntimeError, match="changed the native drawing bytes"):
        case.proof.saved_check(case.adapter, case.path)
    assert case.app.GetOpenDocumentByName(str(case.path)) is None
    assert not case.messages


def test_primary_strict_failure_survives_cleanup_and_hash_failures(saved_washer):
    case = saved_washer
    _display(case, source.THICKNESS).units = 3
    failure = RuntimeError("injected CloseDoc failure")
    def refuse_close():
        case.path.write_bytes(b"injected simultaneous hash change")
        raise failure
    case.app.on_close = refuse_close
    with pytest.raises(RuntimeError, match="native supplier presentation differs") as caught:
        case.proof.saved_check(case.adapter, case.path)
    assert caught.value is not failure
    notes = "\n".join(caught.value.__notes__)
    assert "injected CloseDoc failure" in notes
    assert "changed the native drawing bytes" in notes
    assert not case.messages


@pytest.mark.parametrize("missing", (False, True), ids=("wrong-extension", "missing-file"))
def test_reader_requires_existing_native_drawing(saved_washer, missing):
    case = saved_washer
    path = case.path.with_name("missing.SLDDRW" if missing else "not-native.pdf")
    if not missing:
        path.write_bytes(b"not a native drawing")
    with pytest.raises(ValueError, match="existing native SLDDRW"):
        case.proof.saved_check(case.adapter, path)
    assert not case.app.open_calls
    assert not case.app.close_calls


RECIPES = (
    "draw_mg_vn_wheel_axle_back_washer", "draw_mg_vn_wheel_axle_front_washer",
    "draw_ch_rocker_arm_tl_vn_oblique_lever_washer", "draw_ch_rocker_arm_tl_vn_oblique_block_washer",
    "draw_pd_vn_transgear_pivot_shim", "draw_ch_vn_rocker_thrust_washer", "draw_sm_vn_knife_hanger_washer",
)


@pytest.mark.parametrize("recipe_name", RECIPES)
def test_each_recipe_binds_post_finalize_saved_keyword(monkeypatch, tmp_path, recipe_name):
    recipe = importlib.import_module(recipe_name)
    adapter, views = object(), {"authoring": object()}
    saved_adapter = object()
    path = tmp_path / "finalized.SLDDRW"
    calls = []
    proof = washer.SupplierWasherProof(
        lambda: calls.append(("settled",)),
        lambda actual_adapter, actual_path: calls.append(("saved", actual_adapter, actual_path)),
    )
    def author(actual_adapter, actual_views, **_kwargs):
        assert actual_adapter is adapter
        assert actual_views is views
        calls.append(("authored",))
        return proof
    async def builder(actual_adapter, _spec, *, supplier_dimensions, settled_checks, saved_check, **_kwargs):
        assert actual_adapter is adapter
        supplier_dimensions(adapter, views)
        for check in settled_checks:
            check()
        calls.append(("finalized-and-closed",))
        assert saved_check(saved_adapter, path) is None
        return {"slddrw": str(path)}
    monkeypatch.setattr(recipe, "supplier_washer_dimensions", author)
    monkeypatch.setattr(recipe, "build_purchased_fastener_drawing", builder)
    assert asyncio.run(recipe.build(adapter)) == {"slddrw": str(path)}
    assert calls == [("authored",), ("settled",), ("finalized-and-closed",), ("saved", saved_adapter, path)]


@pytest.mark.parametrize("recipe_name", RECIPES)
@pytest.mark.parametrize("count", (0, 2))
def test_recipe_exactly_once_guard_precedes_saved_reader(monkeypatch, recipe_name, count):
    recipe = importlib.import_module(recipe_name)
    proof = washer.SupplierWasherProof(
        lambda: pytest.fail("invalid authored count reached settled proof"),
        lambda *_args: pytest.fail("invalid authored count reached saved proof"),
    )
    monkeypatch.setattr(recipe, "supplier_washer_dimensions", lambda *_args, **_kwargs: proof)
    async def builder(adapter, _spec, *, supplier_dimensions, settled_checks, saved_check, **_kwargs):
        for _ in range(count):
            supplier_dimensions(adapter, {})
        for check in settled_checks:
            check()
        saved_check(adapter, Path("must-not-reach.SLDDRW"))
    monkeypatch.setattr(recipe, "build_purchased_fastener_drawing", builder)
    with pytest.raises(RuntimeError, match="authored exactly once"):
        asyncio.run(recipe.build(object()))


@pytest.mark.parametrize("recipe_name", RECIPES)
def test_recipe_releases_authored_proof_and_closed_adapter_handle_before_open(
    saved_washer, monkeypatch, recipe_name,
):
    case = saved_washer
    recipe = importlib.import_module(recipe_name)
    references = {}

    def author(adapter, views, **_kwargs):
        assert adapter is case.adapter
        assert views is case.original
        result = washer._supplier_washer_proof(
            adapter, views, case.references, **case.arguments,
        )
        references["proof"] = weakref.ref(result)
        references["settled"] = weakref.ref(result.settled_check)
        return result

    async def builder(adapter, _spec, *, supplier_dimensions, settled_checks, saved_check, **_kwargs):
        supplier_dimensions(adapter, case.original)
        for check in settled_checks:
            check()
        # Model the finalizer's leftover wrapper without any other strong owner.
        adapter._closed_model = _ReadSurface()
        closed_handle = weakref.ref(adapter._closed_model)
        case.invalidate()

        def on_open():
            assert references["proof"]() is None
            assert references["settled"]() is None
            assert closed_handle() is None
            assert adapter.model_clear_calls == [None]

        case.app.on_open = on_open
        assert saved_check(adapter, case.path) is None
        # The callback consumes its one proof before opening; it cannot rerun a
        # stale settled closure or silently reuse the previous authoring list.
        with pytest.raises(RuntimeError, match="authored exactly once"):
            saved_check(adapter, case.path)
        return {"slddrw": str(case.path)}

    monkeypatch.setattr(recipe, "supplier_washer_dimensions", author)
    monkeypatch.setattr(recipe, "build_purchased_fastener_drawing", builder)
    assert asyncio.run(recipe.build(case.adapter)) == {"slddrw": str(case.path)}
    assert case.app.open_calls == [(str(case.path), 3, 1 | 2, "", 0, 0)]
    _assert_closed_unchanged(case)


@pytest.mark.parametrize("recipe_name", RECIPES)
@pytest.mark.parametrize("count", (0, 2))
def test_saved_recipe_callback_independently_requires_exactly_one_proof(
    monkeypatch, recipe_name, count,
):
    recipe = importlib.import_module(recipe_name)
    proof = washer.SupplierWasherProof(
        lambda: None, lambda *_args: pytest.fail("invalid count reached saved reader"),
    )
    monkeypatch.setattr(recipe, "supplier_washer_dimensions", lambda *_args, **_kwargs: proof)

    async def builder(adapter, _spec, *, supplier_dimensions, saved_check, **_kwargs):
        for _ in range(count):
            supplier_dimensions(adapter, {})
        saved_check(adapter, Path("must-not-open.SLDDRW"))

    monkeypatch.setattr(recipe, "build_purchased_fastener_drawing", builder)
    with pytest.raises(RuntimeError, match="authored exactly once"):
        asyncio.run(recipe.build(object()))
