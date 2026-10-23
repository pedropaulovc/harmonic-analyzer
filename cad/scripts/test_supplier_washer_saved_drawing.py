"""Offline saved-roundtrip controls; these doubles are not native farm evidence.

Only COM transport, visible-edge enumeration and feature-dimension enumeration
are substituted. Canonical Parameter lookup and context-specific dimension
wrappers are seeded independently of drawing imports. The saved reader and
strict body/rim/value/band/presentation/source assertions execute unchanged.
Physical-line controls rewrite raw native rows; only the real core constructs
and compares canonical support-line interval unions.
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
import gc
import hashlib
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
import weakref

import pytest

import _drawing_attachment as attachment
import _drawing_edges as edges
import _drawing_layout_audit as native_audit
import _supplier_reference_text as reference_text
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
            "MaterialIdName", "ConfigurationManager", "Parameter",
        } and not object.__getattribute__(self, "__dict__").get("_alive", True):
            raise AssertionError("stale unloaded source IModelDoc2 used")
        if name in object.__getattribute__(self, "__dict__").get("_read_errors", {}):
            raise object.__getattribute__(self, "__dict__")["_read_errors"][name]
        return object.__getattribute__(self, name)


class _Dimension(_ReadSurface):
    """One native dimension's physical state, with a wrapper-specific owner."""

    def __init__(self, state, owner):
        super().__init__(state=state, GetFeatureOwner=lambda: owner)

    @property
    def FullName(self):
        return self.state.FullName

    @FullName.setter
    def FullName(self, value):
        self.state.FullName = value

    @property
    def SystemValue(self):
        return self.state.SystemValue

    @SystemValue.setter
    def SystemValue(self, value):
        self.state.SystemValue = value

    @property
    def Tolerance(self):
        return self.state.Tolerance


def _native_clone(native):
    # Same metadata and even the same owner do not grant native identity.
    return _ReadSurface(
        FullName=native.FullName, SystemValue=native.SystemValue,
        Tolerance=native.Tolerance, GetFeatureOwner=native.GetFeatureOwner,
    )


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
        self.forward = {}

    def GetCorresponding(self, entity):
        if not self.alive:
            raise AssertionError("stale authoring correspondence used after close")
        return self.forward.get(id(entity))

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


class _DisplayData:
    """Native getter-shaped data, independently seeded in sheet metres."""

    def __init__(self, display):
        self.display = display

    def GetLineCount(self):
        return len(self.display.graphics()["lines"])

    def GetLineAtIndex3(self, index):
        return self.display.graphics()["lines"][index]

    def GetArrowHeadCount(self):
        return len(self.display.graphics()["arrows"])

    def GetArrowHeadAtIndex2(self, index):
        return self.display.graphics()["arrows"][index]

    def GetArcCount(self):
        return 0

    GetPolyLineCount = GetPolygonCount = GetTriangleCount = GetEllipseCount = GetArcCount

    def GetTextCount(self):
        return len(self.display.layout["texts"])

    def GetTextAtIndex(self, index):
        return self.display.layout["texts"][index]["t"]

    def GetTextPositionAtIndex(self, index):
        return self.display.layout["texts"][index]["pos"]

    def GetTextHeightAtIndex(self, index):
        return self.display.layout["texts"][index]["h"]

    def GetTextInBoxWidthAtIndex(self, index):
        return self.display.layout["texts"][index]["w"]

    def GetTextRefPositionAtIndex(self, index):
        return self.display.layout["texts"][index]["ref"]

    def GetTextAngleAtIndex(self, index):
        return self.display.layout["texts"][index]["ang"]

    def GetTextFontAtIndex(self, _index):
        return "Arial"

    def GetTextLineSpacingAtIndex(self, _index):
        return 1.0


class _Display(_ReadSurface):
    def __init__(self, label, native, view, attached, *, units, precision):
        self.view = view
        self.label = label
        self.native = native
        self.selection_name = f"{label}@saved-washer-view"
        self.Type2 = 2 if label == source.THICKNESS else 6
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
        annotation.GetAttachedEntityTypes = lambda: (
            (11 if label == source.THICKNESS else 10),
        ) * len(annotation.attached)
        annotation.GetName = lambda: self.selection_name
        annotation.GetType = lambda: 4
        annotation.GetLeaderCount = lambda: 0
        annotation.Layer = ""
        annotation.GetSpecificAnnotation = lambda: self
        annotation.GetPosition = lambda: self.layout["position"]
        annotation.GetDisplayData = lambda: _DisplayData(self)
        annotation.SetPosition2 = self.set_position
        self.seed_layout(saved=False)

    def seed_layout(self, *, saved):
        self._offset = saved if self.label == source.THICKNESS else False
        self.Diametric = True
        self.ArrowSide = 1
        self.SolidLeader = False
        self.broken = 2 if saved else 1
        self.use_doc_broken = False
        self.second_arrow = False
        self.use_doc_second_arrow = False
        self.placement_calls = []
        self.placement_defect = None
        if self.label == source.THICKNESS:
            delta = 0.01446 if saved else 0.0
            self.layout = dict(position=(0.055, 0.03 + delta, 0.0), texts=[
                dict(t="(1.01 mm)", pos=(0.049, 0.029 + delta, 0.0),
                     w=0.012, h=0.0035, ref=1, ang=0.0),
                dict(t="(0.81 mm)", pos=(0.049, 0.025 + delta, 0.0),
                     w=0.012, h=0.0035, ref=1, ang=0.0),
            ])
        else:
            delta = 0.007756 if saved else 0.0
            y = 0.048 if self.label == source.OUTER_DIAMETER else 0.024
            self.layout = dict(position=(0.052 + delta, y, 0.0), texts=[
                dict(t="(Ø", pos=(0.038 + delta, y, 0.0),
                     w=0.004, h=0.0035, ref=1, ang=0.0),
                dict(t="10.0 mm)" if self.label == source.OUTER_DIAMETER else "4.0 mm)",
                     pos=(0.050 + delta, y, 0.0), w=0.016, h=0.0035, ref=1, ang=0.0),
            ])

    @property
    def OffsetText(self):
        if self.label != source.THICKNESS:
            raise AssertionError("OffsetText is unavailable for native diameter dimensions")
        return self._offset

    @OffsetText.setter
    def OffsetText(self, value):
        if self.label != source.THICKNESS:
            raise AssertionError("OffsetText must never be set on a native diameter")
        self.placement_calls.append(("OffsetText", value))
        if self.placement_defect != "ignored-offset":
            self._offset = value

    def SetSecondArrow(self, use_doc, second):
        if self.__dict__.get("_saved_read", False):
            raise AssertionError("saved reader called native SetSecondArrow")
        self.placement_calls.append(("SetSecondArrow", use_doc, second))
        self.use_doc_second_arrow, self.second_arrow = use_doc, second

    def GetUseDocSecondArrow(self):
        return self.use_doc_second_arrow

    def GetSecondArrow(self):
        return self.second_arrow

    def SetBrokenLeader2(self, use_doc, broken):
        if self.__dict__.get("_saved_read", False):
            raise AssertionError("saved reader called native SetBrokenLeader2")
        self.placement_calls.append(("SetBrokenLeader2", use_doc, broken))
        if self.placement_defect == "rejected-leader":
            return -1
        if self.placement_defect != "ignored-leader":
            self.use_doc_broken, self.broken = use_doc, broken
        return 0

    def GetUseDocBrokenLeader(self):
        return self.use_doc_broken

    def GetBrokenLeader2(self):
        return self.broken

    def IsHoleCallout(self):
        return False

    def set_position(self, x, y, z):
        if self.__dict__.get("_saved_read", False):
            raise AssertionError("saved reader called native SetPosition2")
        self.placement_calls.append(("SetPosition2", x, y, z))
        phase = "seed"
        if self.label == source.THICKNESS and self._offset:
            # Enabling offset reapplies the settled seed anchor; only the
            # subsequent, distinct target is the final shelf move.
            phase = "enable" if (x, y, z) == self.layout["position"] else "shelf"
        if self.placement_defect == f"rejected-{phase}":
            return False
        if self.placement_defect == f"ignored-{phase}":
            return True
        old = self.layout["position"]
        dx, dy = x - old[0], y - old[1]
        for row in self.layout["texts"]:
            px, py, pz = row["pos"]
            row["pos"] = (px + dx, py + dy, pz)
        self.layout["position"] = (x, y, z)
        return True

    def graphics(self):
        if self.label == source.THICKNESS:
            lines = [
                [0, 0, 0, 0, 0.04, 0.03, 0, 0.056, 0.03, 0],
                [0, 0, 0, 0, 0.04, 0.03091, 0, 0.056, 0.03091, 0],
                [0, 0, 0, 0, 0.055, 0.03, 0, 0.055, 0.02365, 0],
                [0, 0, 0, 0, 0.055, 0.03091, 0, 0.055, 0.03726, 0],
            ]
            arrows = [
                [0.055, 0.03, 0, 0, -1, 0, 0.003556, 0.000762, 0, 0, 0, 1],
                [0.055, 0.03091, 0, 0, 1, 0, 0.003556, 0.000762, 0, 0, 0, 1],
            ]
        else:
            y = 0.048 if self.label == source.OUTER_DIAMETER else 0.024
            left = min(row["pos"][0] for row in self.layout["texts"])
            # Broken horizontal text has a shoulder below the caption, not a
            # through-caption chord. Its native tip remains on the exact rim.
            lines = [
                [0, 0, 0, 0, 0.04, y, 0, left - 0.001, y - 0.001, 0],
                [0, 0, 0, 0, left - 0.001, y - 0.001, 0, left + 0.028, y - 0.001, 0],
            ] if self.broken == 2 else [
                [0, 0, 0, 0, 0.04, y + 0.001, 0, left + 0.028, y + 0.001, 0],
            ]
            arrows = [[0.04, y, 0, 1, 0, 0, 0.003556, 0.000762, 0, 0, 0, 1]]
        return self.layout.get("graphics", dict(lines=lines, arrows=arrows))

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
        # Only deliberately seeded IDimension wrappers share native identity.
        # Metadata copies, feature clones and entity clones remain distinct.
        self.dimension_identities = {}

    def IsSame(self, first, second):
        if first is second:
            return 1
        first_entry = self.dimension_identities.get(id(first))
        second_entry = self.dimension_identities.get(id(second))
        return int(
            first_entry is not None and second_entry is not None
            and first_entry[0] is first and second_entry[0] is second
            and first_entry[1] is second_entry[1]
        )

    def GetOpenDocumentByName(self, path):
        return self.loaded.get(path)

    def OpenDoc6(self, *args):
        self.open_calls.append(args)
        self.loaded[str(self.drawing.path)] = self.drawing
        if self.on_open is not None:
            self.on_open()
        # Seal the freshly loaded document/view/display/native/annotation state.
        # Absent mutation methods and guarded properties refuse all reader writes.
        for native, _identity in self.dimension_identities.values():
            for surface in (native, native.state, native.Tolerance):
                object.__setattr__(surface, "_saved_read", True)
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
    return _saved_washer_case(request.param, tmp_path, monkeypatch)


def _saved_washer_case(parameters, tmp_path, monkeypatch, *, prepare_proof=True):
    axis, all_banded = parameters
    for module in (washer, source, supplier, edges, attachment, native_audit, reference_text):
        monkeypatch.setattr(module, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(source, "double_array", tuple)
    monkeypatch.setattr(edges, "visible_view_entities", lambda view, _kind, **_kw: view.edges)
    from _drawing_leaders import _sw_type_info
    monkeypatch.setattr(_sw_type_info, "early_bound_or_flag", lambda obj, *_args: obj)
    rebuilds = []
    transition = SimpleNamespace(on_rebuild=None)

    def rebuild(_adapter, *, label):
        rebuilds.append(label)
        if transition.on_rebuild is not None:
            transition.on_rebuild(label)

    monkeypatch.setattr(washer, "rebuild_drawing", rebuild)
    monkeypatch.setattr(reference_text, "rebuild_drawing", rebuild)
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
    canonical_parameters = {}
    parameter_queries = []

    def parameter(name):
        parameter_queries.append(name)
        return canonical_parameters.get(name)

    model = _Part(
        GetPathName=lambda: str(path_state.path), GetType=lambda: 1, IsOpenedReadOnly=lambda: True,
        GetSaveFlag=lambda: False, Extension=SimpleNamespace(reverse={}),
        GetBodies2=lambda _kind, _hidden: (body,), FeatureByName=lambda name: features.get(name),
        Parameter=parameter,
        MaterialIdName="Offline Native DB|Recorded Fixture Alloy|700",
        ConfigurationManager=_ReadSurface(ActiveConfiguration=_ReadSurface(Name="OfflineActiveSourceConfig")),
    )
    original = {name: _View(name, model, f"Authoring{name[1:]}Config") for name in ORIENTATIONS}
    fresh = {name: _View(name, model, original[name].ReferencedConfiguration) for name in ORIENTATIONS}
    drawing = _Drawing(drawing_path, fresh)
    app = _App(drawing, model)
    model.Extension.GetCorresponding2 = lambda entity: model.Extension.reverse.get(id(entity))
    # Native source coordinate conversion still executes _model_point and its
    # independent marshalled-coordinate check; only the math COM object is fake.
    app.GetMathUtility = lambda: SimpleNamespace(CreatePoint=lambda coords: _Point(coords))
    adapter = _Adapter(app)
    source_displays = {}
    source_natives = {}
    native_identities = {}
    source_entities = {}
    for label in VALUES:
        feature_name, native_name = source.SOURCE_DIMENSIONS[label]
        if feature_name not in features:
            top = (axis == "y") != (label == source.THICKNESS)
            sketch = SimpleNamespace(ModelToSketchTransform=SimpleNamespace(Inverse=lambda top=top: top))
            features[feature_name] = SimpleNamespace(
                Name=feature_name, dimensions={}, GetTypeName2=lambda: "ProfileFeature",
                GetSpecificFeature2=lambda sketch=sketch: sketch,
            )
        feature = features[feature_name]
        sketch = feature.GetSpecificFeature2()
        if label == source.THICKNESS:
            sign = 1.0 if axis == "y" else -1.0
            points = (_point(0.005, 0.0, 0.0), _point(0.005, sign * 0.00091, 0.0))
            segment = SimpleNamespace(
                ConstructionGeometry=True, GetType=lambda: 0,
                GetStartPoint2=lambda: points[0], GetEndPoint2=lambda: points[1],
            )
            for index, point in enumerate(points):
                point.GetSketch = lambda sketch=sketch: sketch
                point.GetID = lambda index=index: (index, index + 1)
            source_entities[label] = points
            feature.GetSpecificFeature2().GetSketchSegments = lambda: (segment,)
        else:
            diameter = VALUES[label]
            segment = SimpleNamespace(
                ConstructionGeometry=True, GetType=lambda: 1, IsCircle=lambda: 1,
                GetCenterPoint2=lambda: _point(0.0, 0.0, 0.0),
                GetRadius=lambda diameter=diameter: diameter / 2000.0,
            )
            segment.GetSketch = lambda sketch=sketch: sketch
            segment.GetID = lambda label=label: (0, 1 if label == source.OUTER_DIAMETER else 2)
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
        state = _ReadSurface(
            FullName=f"{native_name}@{feature_name}@washer.SLDPRT",
            SystemValue=value / 1000.0, Tolerance=tolerance,
        )
        native = _Dimension(state, features[feature_name])
        canonical = _Dimension(state, features[feature_name])
        identity = native_identities[label] = object()
        for wrapper in (native, canonical):
            app.dimension_identities[id(wrapper)] = (wrapper, identity)
        # Seed the exact part query before creating any imported wrapper.
        canonical_parameters[f"{native_name}@{feature_name}"] = canonical
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
    mapped_features = {}
    mapped_entities = {}
    imported_natives = {}
    for collection in (original, fresh):
        for view in collection.values():
            view.edges = list(body_edges)
            mapped_features[view] = {}
            mapped_entities[view] = {}
            imported_natives[view] = {}
            for name, feature in features.items():
                source_sketch = feature.GetSpecificFeature2()
                mapped_sketch = SimpleNamespace()
                mapped_feature = SimpleNamespace(
                    Name=name, GetTypeName2=lambda: "ProfileFeature",
                    GetSpecificFeature2=lambda sketch=mapped_sketch: sketch,
                )
                mapped_features[view][name] = mapped_feature
                view.forward[id(feature)] = mapped_feature
                model.Extension.reverse[id(mapped_feature)] = feature
                # Native generic sketch correspondence is NOT the specific
                # sketch obtained from the corresponding IFeature.
                view.forward[id(source_sketch)] = SimpleNamespace()
                for label, entities in source_entities.items():
                    if source.SOURCE_DIMENSIONS[label][0] != name:
                        continue
                    mapped = []
                    for entity in entities:
                        member = SimpleNamespace(**vars(entity))
                        member.GetSketch = lambda sketch=mapped_sketch: sketch
                        view.forward[id(entity)] = member
                        # Measured point inverse succeeds with native null.
                        model.Extension.reverse[id(member)] = (
                            None if label == source.THICKNESS else entity
                        )
                        mapped.append(member)
                    mapped_entities[view][label] = tuple(mapped)
            for label, native in source_natives.items():
                feature_name, _native_name = source.SOURCE_DIMENSIONS[label]
                owner = (mapped_features[view][feature_name] if label == source.THICKNESS
                         else features[feature_name])
                imported = _Dimension(native.state, owner)
                imported_natives[view][label] = imported
                app.dimension_identities[id(imported)] = (imported, native_identities[label])
        for label, value in VALUES.items():
            view = collection[side_orientation if label == source.THICKNESS else face_orientation]
            if label in bands:
                native, attached = imported_natives[view][label], mapped_entities[view][label]
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
            display = _Display(label, native, view, attached, units=0, precision=2)
            display.seed_layout(saved=collection is fresh)
            view.displays.append(display)
    # Source and canonical wrappers always retain their original part owner.
    # Imported thickness wrappers expose each actual view's mapped owner while
    # IsSame still identifies all deliberately seeded wrappers as one dimension.
    references = tuple(washer._reference(display, view, label, VALUES[label], imported=label in bands)
                       for label in VALUES for view in original.values() for display in view.displays
                       if display.selection_name == f"{label}@saved-washer-view")
    arguments = dict(axis=axis, bore_mm=4.0, outer_mm=10.0, thickness_mm=0.91,
                     units="mm", precision=precision, bands=bands)
    proof = (washer._supplier_washer_proof(adapter, original, references, **arguments)
             if prepare_proof else None)
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
        canonical_parameters=canonical_parameters, parameter_queries=parameter_queries,
        imported_natives=imported_natives,
        source_displays=source_displays, features=features, messages=messages,
        mapped_features=mapped_features, mapped_entities=mapped_entities,
        invalidate=invalidate, face=face_orientation, side=side_orientation,
        original_bytes=drawing_path.read_bytes(), source_bytes=source_path.read_bytes(),
        rebuilds=rebuilds, transition=transition,
    )


def _display(case, label):
    return next(display for view in case.fresh.values() for display in view.displays
                if display.selection_name == f"{label}@saved-washer-view")

def _authoring_display(case, label):
    return next(display for view in case.original.values() for display in view.displays
                if display.label == label)


def _reset_authoring_layout(case):
    for view in case.original.values():
        for display in view.displays:
            display.seed_layout(saved=False)
    case.rebuilds.clear()


def _author_again(case):
    return washer._supplier_washer_proof(
        case.adapter, case.original, case.references, **case.arguments,
    )



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
    source_rows = {entry["label"]: entry for entry in receipt["source_dimensions"]}
    assert source_rows.keys() == case.arguments["bands"].keys()
    for label, entry in source_rows.items():
        assert entry["system_value"] == case.source_natives[label].SystemValue
        assert entry["units"] == case.source_displays[label].GetUnits()


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
        if first is _display(case, source.THICKNESS).native and second is native:
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
    _reset_authoring_layout(case)
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
        thickness.native = _native_clone(thickness.native)
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
        thickness.native.GetFeatureOwner = lambda: case.features[source.FACE_FEATURE]
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
    if fault in {"wrong-source-attachment", "wrong-native-owner"}:
        assert len(case.messages) == 1
        prefix = "supplier washer source attachment readback: "
        assert case.messages[0].startswith(prefix)
        assert json.loads(case.messages[0][len(prefix):])["label"] == source.THICKNESS
    else:
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
    with pytest.raises(RuntimeError, match="native source full name changed"):
        case.proof.saved_check(case.adapter, case.path)
    _assert_closed_unchanged(case)


def test_same_named_native_clone_cannot_impersonate_actual_source_dimension(saved_washer):
    case = saved_washer
    display = _display(case, source.THICKNESS)
    actual_source_native = case.source_natives[source.THICKNESS]
    display.native = _native_clone(actual_source_native)
    assert display.native is not actual_source_native
    assert display.native.FullName == actual_source_native.FullName
    assert display.native.GetFeatureOwner() is actual_source_native.GetFeatureOwner()
    assert display.annotation.attached == case.mapped_entities[display.view][source.THICKNESS]
    case.invalidate()
    with pytest.raises(RuntimeError, match="not its actual native source"):
        case.proof.saved_check(case.adapter, case.path)
    _assert_closed_unchanged(case)
    assert not case.messages


def _source_context(case, label=source.THICKNESS):
    view = case.original[case.side if label == source.THICKNESS else case.face]
    return view, _Display(
        label, case.imported_natives[view][label], view, case.mapped_entities[view][label],
        units=0, precision=2,
    )


def _check_source(case, display, label=source.THICKNESS, *, view):
    source.assert_supplier_washer_source_attachment(
        case.adapter, case.model, display, view=view, label=label, axis=case.arguments["axis"],
        bore_mm=4.0, outer_mm=10.0, thickness_mm=0.91,
    )


@pytest.mark.parametrize("label", tuple(VALUES))
@pytest.mark.parametrize("alternate_kind", (False, True))
def test_measured_view_source_context_accepts_complete_native_proof(saved_washer, label, alternate_kind):
    case = saved_washer
    view, display = _source_context(case, label)
    feature = case.features[source.SOURCE_DIMENSIONS[label][0]]
    mapped_feature = case.mapped_features[view][feature.Name]
    assert mapped_feature is not feature
    assert view.GetCorresponding(feature.GetSpecificFeature2()) is not mapped_feature.GetSpecificFeature2()
    assert display.annotation.Owner is view
    feature_name, dimension_name = source.SOURCE_DIMENSIONS[label]
    canonical = case.canonical_parameters[f"{dimension_name}@{feature_name}"]
    assert display.native is not case.source_natives[label]
    assert canonical is not case.source_natives[label] and canonical is not display.native
    assert case.app.IsSame(display.native, case.source_natives[label]) == 1
    assert case.app.IsSame(display.native, canonical) == 1
    assert case.source_natives[label].GetFeatureOwner() is feature
    assert canonical.GetFeatureOwner() is feature
    for original, mapped in zip(case.source_entities[label], display.annotation.attached, strict=True):
        assert original is not mapped
        assert original.GetSketch() is feature.GetSpecificFeature2()
        assert mapped.GetSketch() is mapped_feature.GetSpecificFeature2()
        assert original.GetID() == mapped.GetID()  # IDs are scoped, not authority.
        assert case.app.IsSame(original, mapped) == 0
        if label == source.THICKNESS:
            assert case.model.Extension.GetCorresponding2(mapped) is None
        else:
            assert case.model.Extension.GetCorresponding2(mapped) is original
            assert view.GetCorresponding(original) is mapped
    assert display.native.GetFeatureOwner() is (
        mapped_feature if label == source.THICKNESS else feature
    )
    if alternate_kind:
        display.annotation.GetAttachedEntityTypes = lambda: (
            (25 if label == source.THICKNESS else 24),
        ) * len(display.annotation.attached)
    query = f"{dimension_name}@{feature_name}"
    case.parameter_queries.clear()
    _check_source(case, display, label, view=view)
    assert case.parameter_queries == [query]
    assert case.source_path.read_bytes() == case.source_bytes
    assert case.path.read_bytes() == case.original_bytes


@pytest.mark.parametrize("fault", (
    "native-clone", "source-missing", "source-name", "source-type", "mapped-null",
    "mapped-name", "mapped-type", "owner-null", "owner-clone", "owner-name",
    "owner-type", "reverse-feature-null", "reverse-feature-clone",
    "source-sketch", "mapped-sketch", "mapped-sketch-generic", "mapped-specific-null",
    "forward-null", "forward-collapse", "forward-foreign", "source-collapse",
    "annotation-owner", "annotation-owner-type", "annotation-owner-null",
    "attachment-count", "attachment-count-bool", "attachment-types", "attachment-type-count",
    "attachment-extra", "attachment-duplicate", "attachment-null", "attachment-missing", "attachment-clone",
    "source-extra-segment", "source-not-construction", "source-wrong-endpoint",
    "source-wrong-plane", "view-document", "view-path", "origin-points",
))
@pytest.mark.parametrize("point_kind", (11, 25))
def test_view_source_context_refuses_incomplete_native_proof(saved_washer, fault, point_kind):
    case = saved_washer
    view, display = _source_context(case)
    feature = case.features[source.THICKNESS_FEATURE]
    sketch = feature.GetSpecificFeature2()
    mapped_feature = case.mapped_features[view][source.THICKNESS_FEATURE]
    originals = case.source_entities[source.THICKNESS]
    mapped = case.mapped_entities[view][source.THICKNESS]
    annotation = display.annotation
    annotation.GetAttachedEntityTypes = lambda: (point_kind,) * len(annotation.attached)
    if fault == "native-clone":
        display.native = _native_clone(display.native)
    elif fault == "source-missing":
        case.features.pop(source.THICKNESS_FEATURE)
    elif fault in {"source-name", "mapped-name"}:
        (feature if fault.startswith("source") else mapped_feature).Name = "OtherWitness"
    elif fault in {"source-type", "mapped-type"}:
        (feature if fault.startswith("source") else mapped_feature).GetTypeName2 = lambda: "RefPlane"
    elif fault == "mapped-null":
        view.forward[id(feature)] = None
    elif fault.startswith("owner-"):
        owner = None if fault == "owner-null" else SimpleNamespace(**vars(mapped_feature))
        if fault == "owner-name":
            owner.Name = "OtherWitness"
        elif fault == "owner-type":
            owner.GetTypeName2 = lambda: "RefPlane"
        display.native.GetFeatureOwner = lambda: owner
    elif fault.startswith("reverse-feature-"):
        case.model.Extension.reverse[id(mapped_feature)] = (
            None if fault.endswith("null") else SimpleNamespace(**vars(feature))
        )
    elif fault == "source-sketch":
        originals[0].GetSketch = lambda: SimpleNamespace()
    elif fault == "mapped-sketch":
        mapped[0].GetSketch = lambda: sketch
    elif fault == "mapped-sketch-generic":
        mapped[0].GetSketch = lambda: view.GetCorresponding(sketch)
    elif fault == "mapped-specific-null":
        mapped_feature.GetSpecificFeature2 = lambda: None
    elif fault == "forward-null":
        view.forward[id(originals[1])] = None
    elif fault == "forward-collapse":
        view.forward[id(originals[1])] = mapped[0]
    elif fault == "forward-foreign":
        view.forward[id(originals[1])] = SimpleNamespace(**vars(mapped[1]))
    elif fault == "source-collapse":
        sketch.GetSketchSegments()[0].GetEndPoint2 = lambda: originals[0]
    elif fault == "annotation-owner":
        annotation.Owner = case.original["*Right"]
    elif fault == "annotation-owner-type":
        annotation.OwnerType = 1
    elif fault == "annotation-owner-null":
        annotation.Owner = None
    elif fault == "attachment-count":
        annotation.GetAttachedEntityCount3 = lambda: 1
    elif fault == "attachment-count-bool":
        annotation.GetAttachedEntityCount3 = lambda: True
    elif fault == "attachment-types":
        annotation.GetAttachedEntityTypes = lambda: (10, 10)
    elif fault == "attachment-type-count":
        annotation.GetAttachedEntityTypes = lambda: (point_kind,)
    elif fault == "attachment-extra":
        annotation.attached = (*mapped, SimpleNamespace(**vars(mapped[0])))
    elif fault == "attachment-duplicate":
        annotation.attached = (mapped[0], mapped[0])
    elif fault == "attachment-null":
        annotation.attached = (mapped[0], None)
    elif fault == "attachment-missing":
        annotation.attached = mapped[:1]
    elif fault == "attachment-clone":
        annotation.attached = tuple(SimpleNamespace(**vars(point)) for point in mapped)
    elif fault == "origin-points":
        origin = _point(0.0, 0.0, 0.0)
        origin.GetSketch = mapped[0].GetSketch
        origin.GetID = mapped[0].GetID
        annotation.attached = (origin, mapped[1])
    elif fault == "source-extra-segment":
        segment = sketch.GetSketchSegments()[0]
        sketch.GetSketchSegments = lambda: (segment, segment)
    elif fault == "source-not-construction":
        sketch.GetSketchSegments()[0].ConstructionGeometry = False
    elif fault == "source-wrong-endpoint":
        originals[1].Y *= 2
    elif fault == "source-wrong-plane":
        sketch.ModelToSketchTransform.Inverse = lambda: case.arguments["axis"] == "y"
    elif fault == "view-document":
        view.ReferencedDocument = _Part(**vars(case.model))
    elif fault == "view-path":
        view.model_name = str(case.source_path.with_name("foreign.SLDPRT"))
    with pytest.raises(RuntimeError):
        _check_source(case, display, view=view)
    assert case.source_path.read_bytes() == case.source_bytes
    assert case.path.read_bytes() == case.original_bytes


@pytest.mark.parametrize("result", (False, True, 0.0, 1.0, 2, None, "1"),
                         ids=("false", "true", "float-zero", "float-one", "unsupported", "null", "string"))
@pytest.mark.parametrize("relation", (
    "native", "source-parameter", "imported-parameter", "feature", "reverse-feature",
    "source-self", "mapped-self", "owner-view",
))
def test_view_source_context_requires_real_integer_native_identity(saved_washer, result, relation):
    case = saved_washer
    view, display = _source_context(case)
    feature = case.features[source.THICKNESS_FEATURE]
    mapped_feature = case.mapped_features[view][source.THICKNESS_FEATURE]
    original = case.source_entities[source.THICKNESS][0]
    mapped = case.mapped_entities[view][source.THICKNESS][0]
    source_native = case.source_natives[source.THICKNESS]
    feature_name, dimension_name = source.SOURCE_DIMENSIONS[source.THICKNESS]
    canonical = case.canonical_parameters[f"{dimension_name}@{feature_name}"]
    first, second = {
        "native": (display.native, source_native),
        "source-parameter": (source_native, canonical),
        "imported-parameter": (display.native, canonical),
        "feature": (mapped_feature, mapped_feature),
        "reverse-feature": (feature, feature),
        "source-self": (original, original),
        "mapped-self": (mapped, mapped),
        "owner-view": (view, view),
    }[relation]
    actual_is_same = case.app.IsSame
    case.app.IsSame = lambda left, right: (
        result if left is first and right is second else actual_is_same(left, right)
    )
    with pytest.raises(RuntimeError):
        _check_source(case, display, view=view)


@pytest.mark.parametrize("inventory", ("source", "mapped", "attached"))
def test_view_source_inventory_requires_native_distinctness(saved_washer, inventory):
    case = saved_washer
    view, display = _source_context(case)
    members = (case.source_entities[source.THICKNESS] if inventory == "source"
               else case.mapped_entities[view][source.THICKNESS])
    actual_is_same = case.app.IsSame

    def same(first, second):
        if ((first is members[0] and second is members[1])
                or (first is members[1] and second is members[0])):
            return 1
        return actual_is_same(first, second)

    if inventory == "attached":
        display.annotation.attached = (members[0], members[0])
    else:
        case.app.IsSame = same
    with pytest.raises(RuntimeError):
        _check_source(case, display, view=view)



@pytest.mark.parametrize("fault", (
    "wrong-bore", "reverse-null", "reverse-clone", "reverse-bore", "roundtrip-null",
    "roundtrip-clone", "unselected-collapse", "unselected-null", "unselected-sketch",
    "source-duplicate", "partial-circle", "wrong-radius", "wrong-center",
))
def test_view_circle_proof_checks_complete_inventory_and_reverse_roundtrip(saved_washer, fault):
    case = saved_washer
    view, display = _source_context(case, source.OUTER_DIAMETER)
    outer = case.source_entities[source.OUTER_DIAMETER][0]
    bore = case.source_entities[source.BORE_DIAMETER][0]
    mapped_outer = case.mapped_entities[view][source.OUTER_DIAMETER][0]
    mapped_bore = case.mapped_entities[view][source.BORE_DIAMETER][0]
    if fault == "wrong-bore":
        display.annotation.attached = (mapped_bore,)
    elif fault.startswith("reverse-"):
        case.model.Extension.reverse[id(mapped_outer)] = {
            "reverse-null": None, "reverse-clone": SimpleNamespace(**vars(outer)),
            "reverse-bore": bore,
        }[fault]
    elif fault.startswith("roundtrip-"):
        def reverse(entity):
            if entity is mapped_outer:
                view.forward[id(outer)] = (
                    None if fault.endswith("null") else SimpleNamespace(**vars(mapped_outer))
                )
                return outer
            return case.model.Extension.reverse.get(id(entity))
        case.model.Extension.GetCorresponding2 = reverse
    elif fault == "unselected-collapse":
        view.forward[id(bore)] = mapped_outer
    elif fault == "unselected-null":
        view.forward[id(bore)] = None
    elif fault == "unselected-sketch":
        mapped_bore.GetSketch = lambda: outer.GetSketch()
    elif fault == "source-duplicate":
        outer.GetSketch().GetSketchSegments = lambda: (outer, outer)
    elif fault == "partial-circle":
        outer.IsCircle = lambda: 0
    elif fault == "wrong-radius":
        outer.GetRadius = lambda: 0.006
    elif fault == "wrong-center":
        outer.GetCenterPoint2 = lambda: _point(0.001, 0.0, 0.0)
    with pytest.raises(RuntimeError):
        _check_source(case, display, source.OUTER_DIAMETER, view=view)


@pytest.mark.parametrize("fault", ("none", "mapped-owner", "mapped-endpoints", "geometry", "construction"))
def test_part_only_source_guard_retains_direct_source_contract(saved_washer, fault):
    case = saved_washer
    display = case.source_displays[source.THICKNESS]
    feature = case.features[source.THICKNESS_FEATURE]
    if fault == "mapped-owner":
        display.native.GetFeatureOwner = lambda: case.mapped_features[
            case.original[case.side]
        ][source.THICKNESS_FEATURE]
    elif fault == "mapped-endpoints":
        display.annotation.attached = case.mapped_entities[case.original[case.side]][source.THICKNESS]
    elif fault == "geometry":
        case.source_entities[source.THICKNESS][1].Y *= 2
    elif fault == "construction":
        feature.GetSpecificFeature2().GetSketchSegments()[0].ConstructionGeometry = False
    if fault == "none":
        _check_source(case, display, view=None)
    else:
        with pytest.raises(RuntimeError):
            _check_source(case, display, view=None)


def test_source_attachment_refuses_an_omitted_required_view(saved_washer):
    case = saved_washer
    case.parameter_queries.clear()
    with pytest.raises(TypeError):
        source.assert_supplier_washer_source_attachment(
            case.adapter, case.model, case.source_displays[source.THICKNESS],
            label=source.THICKNESS, axis=case.arguments["axis"],
            bore_mm=4.0, outer_mm=10.0, thickness_mm=0.91,
        )
    assert not case.parameter_queries


def test_original_source_reference_check_uses_explicit_model_without_adapter_current_model(saved_washer):
    case = saved_washer
    case.parameter_queries.clear()
    source.assert_supplier_washer_references(case.adapter, case.model, **case.arguments)
    expected = [
        f"{source.SOURCE_DIMENSIONS[label][1]}@{source.SOURCE_DIMENSIONS[label][0]}"
        for label in case.arguments["bands"]
    ]
    assert case.parameter_queries == expected
    assert not case.app.open_calls
    assert not case.app.close_calls


@pytest.mark.parametrize("context", ("part", "view", "saved"))
@pytest.mark.parametrize("fault", ("missing", "metadata-clone", "other-dimension", "matching-source-import-clones"))
def test_canonical_part_parameter_is_independent_of_named_source_and_import(saved_washer, context, fault):
    case = saved_washer
    label = source.THICKNESS
    feature_name, dimension_name = source.SOURCE_DIMENSIONS[label]
    query = f"{dimension_name}@{feature_name}"
    canonical = case.canonical_parameters[query]
    view, display = _source_context(case)
    if context == "part":
        view, display = None, case.source_displays[label]
    elif context == "saved":
        view, display = case.fresh[case.side], _display(case, label)
    if fault == "missing":
        case.canonical_parameters.pop(query)
    elif fault == "metadata-clone":
        case.canonical_parameters[query] = _native_clone(canonical)
        assert case.canonical_parameters[query].FullName == canonical.FullName
        assert case.canonical_parameters[query].SystemValue == canonical.SystemValue
    elif fault == "other-dimension":
        feature, name = source.SOURCE_DIMENSIONS[source.BORE_DIAMETER]
        case.canonical_parameters[query] = case.canonical_parameters[f"{name}@{feature}"]
    else:
        # Enumeration and import can agree on the wrong native dimension. The
        # independently retained canonical part query must still disprove both.
        feature = case.features[feature_name]
        state = _ReadSurface(
            FullName=canonical.FullName, SystemValue=canonical.SystemValue,
            Tolerance=canonical.Tolerance,
        )
        wrong_source = _Dimension(state, feature)
        owner = feature if view is None else case.mapped_features[view][feature_name]
        wrong_import = _Dimension(state, owner)
        wrong_identity = object()
        for wrapper in (wrong_source, wrong_import):
            case.app.dimension_identities[id(wrapper)] = (wrapper, wrong_identity)
        wrong_display = _Display(
            label, wrong_source, None, case.source_entities[label], units=0, precision=2,
        )
        feature.dimensions[dimension_name] = (wrong_display, wrong_source)
        display.native = wrong_import
        assert case.app.IsSame(wrong_import, wrong_source) == 1
        assert case.app.IsSame(wrong_source, canonical) == 0
        assert case.canonical_parameters[query] is canonical
    case.parameter_queries.clear()
    with pytest.raises(RuntimeError):
        if context == "saved":
            case.invalidate()
            case.proof.saved_check(case.adapter, case.path)
        else:
            _check_source(case, display, view=view)
    assert case.parameter_queries.count(query) == 1
    if context == "saved":
        _assert_closed_unchanged(case)
    else:
        assert not case.app.open_calls
        assert not case.app.close_calls
        assert case.source_path.read_bytes() == case.source_bytes
        assert case.path.read_bytes() == case.original_bytes


@pytest.mark.parametrize("context", ("part", "view", "saved"))
def test_canonical_parameter_read_error_is_preserved_without_retry(saved_washer, context):
    case = saved_washer
    feature_name, dimension_name = source.SOURCE_DIMENSIONS[source.THICKNESS]
    query = f"{dimension_name}@{feature_name}"
    failure = RuntimeError("native Parameter canonical-read-sentinel")
    queries = []
    actual_parameter = case.model.Parameter

    def refuse(name):
        queries.append(name)
        if name == query:
            raise failure
        return actual_parameter(name)

    case.model.Parameter = refuse
    view, display = _source_context(case)
    if context == "part":
        view, display = None, case.source_displays[source.THICKNESS]
    with pytest.raises(RuntimeError) as caught:
        if context == "saved":
            case.invalidate()
            case.proof.saved_check(case.adapter, case.path)
        else:
            _check_source(case, display, view=view)
    assert caught.value is failure
    assert queries.count(query) == 1
    assert queries[-1] == query
    if context == "saved":
        _assert_closed_unchanged(case)
    else:
        assert queries == [query]
        assert not case.app.open_calls
        assert not case.app.close_calls


def test_saved_view_proof_reacquires_mapping_without_changing_native_source(saved_washer, monkeypatch):
    case = saved_washer
    calls = []
    actual_guard = washer.assert_supplier_washer_source_attachment

    def physical_state():
        features = tuple(
            (name, feature.Name, feature.GetTypeName2(), tuple(
                (segment, segment.ConstructionGeometry, segment.GetType())
                for segment in feature.GetSpecificFeature2().GetSketchSegments()
            ))
            for name, feature in case.features.items()
        )
        points = tuple((point, point.X, point.Y, point.Z)
                       for point in case.source_entities[source.THICKNESS])
        circles = tuple((circle, circle.GetRadius(), circle.GetCenterPoint2().__dict__.copy())
                        for label in (source.OUTER_DIAMETER, source.BORE_DIAMETER)
                        for circle in case.source_entities[label])
        dimensions = tuple(
            (label, native, native.FullName, native.SystemValue, native.Tolerance.Type,
             native.Tolerance.GetMinValue(), native.Tolerance.GetMaxValue(),
             native.GetFeatureOwner(), case.source_displays[label].annotation.attached,
             case.source_displays[label].annotation.IsDangling(),
             case.source_displays[label].GetUnits(),
             case.source_displays[label].GetPrimaryPrecision2(),
             tuple(sorted(case.source_displays[label].text.items())))
            for label, native in case.source_natives.items()
        )
        canonical = tuple(
            (name, native, native.GetFeatureOwner(), native.FullName, native.SystemValue)
            for name, native in case.canonical_parameters.items()
        )
        rims = tuple(edge.GetCurve().CircleParams for edge in case.body_edges)
        return features, points, circles, dimensions, canonical, rims

    def guard(adapter, model, display, **arguments):
        view = arguments["view"]
        label = arguments["label"]
        assert view in case.fresh.values()
        assert display.annotation.Owner is view
        assert display.annotation.attached == case.mapped_entities[view][label]
        assert all(view is not old for old in case.original.values())
        if label == source.THICKNESS:
            assert display.native.GetFeatureOwner() is case.mapped_features[view][source.THICKNESS_FEATURE]
        calls.append(label)
        return actual_guard(adapter, model, display, **arguments)

    before = physical_state()
    case.invalidate()
    monkeypatch.setattr(washer, "assert_supplier_washer_source_attachment", guard)
    case.proof.saved_check(case.adapter, case.path)
    assert sorted(calls) == sorted(case.arguments["bands"])
    assert physical_state() == before
    _assert_closed_unchanged(case)



@pytest.mark.parametrize("fault", ("authoring-points", "authoring-feature", "authoring-owner"))
def test_saved_view_source_context_refuses_stale_authoring_handles(saved_washer, fault):
    case = saved_washer
    saved = case.fresh[case.side]
    old = case.original[case.side]
    display = _display(case, source.THICKNESS)
    feature = case.features[source.THICKNESS_FEATURE]
    if fault == "authoring-points":
        display.annotation.attached = case.mapped_entities[old][source.THICKNESS]
    elif fault == "authoring-feature":
        saved.forward[id(feature)] = case.mapped_features[old][source.THICKNESS_FEATURE]
    else:
        display.annotation.Owner = old
    case.invalidate()
    with pytest.raises(RuntimeError):
        case.proof.saved_check(case.adapter, case.path)
    _assert_closed_unchanged(case)


def test_saved_reader_validates_actual_source_presentation_independently(saved_washer):
    case = saved_washer
    case.source_displays[source.THICKNESS].units = 3
    assert _display(case, source.THICKNESS).units == 0
    case.invalidate()
    with pytest.raises(RuntimeError, match="model supplier units/precision/reference ink changed") as caught:
        case.proof.saved_check(case.adapter, case.path)
    _assert_closed_unchanged(case)
    assert not case.messages
    receipt = _exception_receipt(caught.value)
    source_row = next(item for item in receipt["source_dimensions"]
                      if item["label"] == source.THICKNESS)
    selection_name = _display(case, source.THICKNESS).selection_name
    drawing_row = next(item for item in receipt["dimensions"]
                       if item["selection_name"] == selection_name)
    assert source_row["units"] == 3
    assert drawing_row["units"] == 0


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


def test_success_receipt_repr_serializes_diagnostic_only_decimal_denominator(saved_washer):
    """A serialization double, not a claim that COM returns this Python object."""
    case = saved_washer
    display = _display(case, source.THICKNESS)

    class DiagnosticOnlyDenominator:
        def __repr__(self):
            return "<diagnostic-only non-JSON decimal denominator>"

    observation = DiagnosticOnlyDenominator()
    display.fraction_value = observation
    before_value = display.native.SystemValue
    before_tolerance = display.native.Tolerance
    case.invalidate()
    assert case.proof.saved_check(case.adapter, case.path) is None
    _assert_closed_unchanged(case)
    assert display.GetFractionValue() is observation
    assert display.GetFractionBase() == 1
    assert display.native.SystemValue == before_value
    assert display.native.Tolerance is before_tolerance
    assert len(case.messages) == 1
    receipt = json.loads(case.messages[0].split(": ", 1)[1])
    drawing_row = next(item for item in receipt["dimensions"]
                       if item["selection_name"] == display.selection_name)
    source_row = next(item for item in receipt["source_dimensions"]
                      if item["label"] == source.THICKNESS)
    assert drawing_row["fraction_value"] == repr(observation)
    assert source_row["fraction_value"] == 0


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
        _reset_authoring_layout(case)
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


@pytest.fixture(params=(("y", True), ("z", True), ("y", False), ("z", False)),
                ids=("y-all-banded", "z-all-banded", "y-rim-refs", "z-rim-refs"))
def original_source_capture(request, tmp_path, monkeypatch):
    """Independent native-shaped handles, without executing the unrelated core."""
    case = _saved_washer_case(request.param, tmp_path, monkeypatch, prepare_proof=False)
    for label, native in case.source_natives.items():
        name = source.SOURCE_DIMENSIONS[label][1]
        native.Name = name
        query = f"{name}@{source.SOURCE_DIMENSIONS[label][0]}"
        case.canonical_parameters[query].Name = name
        for imported in case.imported_natives.values():
            imported[label].Name = name
    feature = case.features[source.THICKNESS_FEATURE]
    sketch = feature.GetSpecificFeature2()
    segment = sketch.GetSketchSegments()[0]
    segment.GetID = lambda: (71, 72)
    segment.GetSketch = lambda: sketch
    sketch.GetSketchPointsCount2 = lambda: 2
    feature.GetFirstDisplayDimension = lambda: case.source_displays[source.THICKNESS]
    original_annotation = case.source_displays[source.THICKNESS].annotation
    original_annotation.Owner = case.model
    original_annotation.OwnerType = 3
    mapped_sketches = {}
    for collection in (case.original, case.fresh):
        view = collection[case.side]
        mapped_feature = case.mapped_features[view][source.THICKNESS_FEATURE]
        mapped_sketch = mapped_feature.GetSpecificFeature2()
        endpoints = case.mapped_entities[view][source.THICKNESS]
        mapped_line = SimpleNamespace(
            GetType=lambda: 0, GetID=lambda: (81, 82),
            GetSketch=lambda mapped_sketch=mapped_sketch: mapped_sketch,
            ConstructionGeometry=True,
            GetStartPoint2=lambda endpoints=endpoints: endpoints[0],
            GetEndPoint2=lambda endpoints=endpoints: endpoints[1],
        )
        mapped_sketch.GetSketchSegments = lambda mapped_line=mapped_line: (mapped_line,)
        mapped_sketch.GetSketchPointsCount2 = lambda: 2
        view.forward[id(segment)] = mapped_line
        case.model.Extension.reverse[id(mapped_line)] = segment
        imported_annotation = next(display.annotation for display in view.displays
                                   if display.label == source.THICKNESS)
        view.forward[id(original_annotation)] = imported_annotation
        case.model.Extension.reverse[id(imported_annotation)] = original_annotation
        mapped_sketches[view] = mapped_sketch
    case.diagnostic_sketch = sketch
    case.diagnostic_mapped_sketches = mapped_sketches
    return case


def _original_source_capture_reads(case, *, imported=True):
    error = RuntimeError("independent original-source gate refusal")
    washer._capture_original_washer_source_failure(
        error, case.adapter, case.model, case.original[case.side],
        phase="after_import" if imported else "before_import",
        imported=_authoring_display(case, source.THICKNESS) if imported else None,
    )
    prefix = "supplier washer source attachment readback: "
    notes = [note[len(prefix):] for note in error.__notes__ if note.startswith(prefix)]
    assert len(notes) == 1
    return json.loads(notes[0])["reads"]


class _OriginalCaptureDispatch:
    """Python dispatch transport: binding never retains the input wrapper."""

    def __init__(self, surface, dispatch):
        self._surface = surface
        self._oleobj_ = dispatch

    def __getattr__(self, name):
        return getattr(self._surface, name)


def _install_original_capture_rebinder(case, monkeypatch, *, check_lifetime=False):
    dispatches = {}
    wrappers = []
    counts = SimpleNamespace(bindings=0)

    def unwrap(value):
        return value._surface if isinstance(value, _OriginalCaptureDispatch) else value

    def wrap(value):
        if value is None:
            return None
        surface = unwrap(value)
        if check_lifetime:
            gc.collect()
            assert all(reference() is not None for reference in wrappers), (
                "a previously keyed raw/bound wrapper died during capture"
            )
        entry = dispatches.setdefault(id(surface), (surface, object()))
        result = _OriginalCaptureDispatch(surface, entry[1])
        wrappers.append(weakref.ref(result))
        return result

    def bind(value, _interface):
        result = wrap(value)
        assert result is not value, "this control must exercise real Python rebinding"
        counts.bindings += 1
        return result

    view = case.original[case.side]
    actual_forward = view.GetCorresponding
    actual_reverse = case.model.Extension.GetCorresponding2
    actual_same = case.app.IsSame
    monkeypatch.setattr(washer, "_early_bound", bind)
    monkeypatch.setattr(view, "GetCorresponding", lambda value: wrap(actual_forward(unwrap(value))))
    monkeypatch.setattr(case.model.Extension, "GetCorresponding2",
                        lambda value: wrap(actual_reverse(unwrap(value))))
    monkeypatch.setattr(case.app, "IsSame", lambda first, second: actual_same(unwrap(first), unwrap(second)))
    return SimpleNamespace(wrap=wrap, wrappers=wrappers, counts=counts)


def _bind_original_capture_import(monkeypatch):
    monkeypatch.setattr(washer, "curate_view_dimensions", lambda _adapter, view, **_kwargs: [
        SimpleNamespace(GetSpecificAnnotation=lambda display=display: display)
        for display in view.displays
    ])
    monkeypatch.setattr(washer, "dimension_name", lambda _adapter, annotation:
                        source.SOURCE_DIMENSIONS[annotation.GetSpecificAnnotation().label][1])


@pytest.mark.parametrize("phase", ("before_import", "after_import", "final_or_saved"))
@pytest.mark.parametrize("transport", ("capture", "getter", "note", "logging", "note-and-logging", "span"))
def test_original_source_capture_keeps_gate_exception_at_each_seam(
    original_source_capture, monkeypatch, phase, transport,
):
    case = original_source_capture
    _reset_authoring_layout(case)
    _bind_original_capture_import(monkeypatch)
    attempts = []

    class Refusal(RuntimeError):
        def add_note(self, note):
            attempts.append(("note", note))
            if transport in {"note", "note-and-logging"}:
                raise ValueError("independent note transport failure")
            super().add_note(note)

    original = Refusal("unchanged original source gate")
    gate_calls = []
    capture_calls = []
    actual_capture = washer._capture_original_washer_source_failure
    actual_guard = washer.assert_supplier_washer_references

    def gate(adapter, model, **kwargs):
        gate_calls.append((adapter, model, kwargs))
        if phase != "after_import" or len(gate_calls) == 2:
            raise original
        return actual_guard(adapter, model, **kwargs)

    def capture(error, adapter, model, view, **kwargs):
        capture_calls.append((error, adapter, model, view, kwargs))
        if transport == "capture":
            raise KeyboardInterrupt("diagnostic helper failure must not escape")
        return actual_capture(error, adapter, model, view, **kwargs)

    def fail_getter():
        attempts.append(("getter",))
        raise ValueError("independent first-display getter failure")

    def log(message):
        attempts.append(("logging", message))
        if transport in {"logging", "note-and-logging"}:
            raise ValueError("independent telemetry transport failure")

    if transport == "getter":
        case.features[source.THICKNESS_FEATURE].GetFirstDisplayDimension = fail_getter
    monkeypatch.setattr(washer, "assert_supplier_washer_references", gate)
    monkeypatch.setattr(washer, "_capture_original_washer_source_failure", capture)
    monkeypatch.setattr(washer._telemetry, "info", log)
    if transport == "span":
        actual_span = washer._telemetry.span

        def span(name, **kwargs):
            if name == "drawing.capture_original_supplier_washer_source_failure":
                attempts.append(("span", name))
                raise KeyboardInterrupt("diagnostic span entry failed")
            return actual_span(name, **kwargs)

        monkeypatch.setattr(washer._telemetry, "span", span)
    with pytest.raises(Refusal) as caught:
        if phase == "final_or_saved":
            washer.assert_supplier_washer_dimensions(
                case.adapter, case.original, case.references, **case.arguments,
            )
        else:
            washer.supplier_washer_dimensions(case.adapter, case.original, **case.arguments)
    assert caught.value is original
    assert len(gate_calls) == (2 if phase == "after_import" else 1)
    assert all(adapter is case.adapter and model is case.model
               and kwargs == {**case.arguments, "bore_callout": None}
               for adapter, model, kwargs in gate_calls)
    assert len(capture_calls) == 1
    error, adapter, model, view, kwargs = capture_calls[0]
    assert error is original and adapter is case.adapter and model is case.model
    assert view is case.original[case.side]
    assert kwargs["phase"] == phase
    assert kwargs["imported"] is (
        None if phase == "before_import" else _authoring_display(case, source.THICKNESS)
    )
    if transport not in {"capture", "span"}:
        assert any(attempt[0] == "note" for attempt in attempts)
        assert any(attempt[0] == "logging" for attempt in attempts)
    if transport == "getter":
        assert sum(attempt[0] == "getter" for attempt in attempts) == 1
        assert any("independent first-display getter failure" in attempt[1]
                   for attempt in attempts if attempt[0] == "note")
    if transport == "span":
        assert sum(attempt[0] == "span" for attempt in attempts) == 1
    assert not case.app.open_calls and not case.app.close_calls
    assert not case.rebuilds
    assert case.path.read_bytes() == case.original_bytes
    assert case.source_path.read_bytes() == case.source_bytes


def test_original_source_capture_healthy_paths_read_no_new_diagnostic_getters(
    original_source_capture, monkeypatch,
):
    case = original_source_capture

    def forbidden(*_args, **_kwargs):
        pytest.fail("healthy original-source gate reached a diagnostic getter")

    case.features[source.THICKNESS_FEATURE].GetFirstDisplayDimension = forbidden
    case.diagnostic_sketch.GetSketchPointsCount2 = forbidden
    for sketch in case.diagnostic_mapped_sketches.values():
        sketch.GetSketchPointsCount2 = forbidden
    monkeypatch.setattr(washer, "_capture_original_washer_source_failure", forbidden)
    washer.assert_supplier_washer_dimensions(
        case.adapter, case.original, case.references, **case.arguments,
    )
    _reset_authoring_layout(case)
    _bind_original_capture_import(monkeypatch)
    # This test stops after the two real public original-source guards; the
    # placement consumer has its own existing tests and is not a diagnostic.
    result = object()
    monkeypatch.setattr(washer, "_supplier_washer_proof", lambda *_args, **_kwargs: result)
    monkeypatch.setattr(washer, "_native_diameter", lambda _adapter, view, rim, **_kw:
                        next(display for display in view.displays
                             if display.annotation.attached == (rim,)))
    monkeypatch.setattr(washer, "supplier_reference_dimension", lambda _adapter, display, **_kw: display)
    assert washer.supplier_washer_dimensions(case.adapter, case.original, **case.arguments) is result


def test_original_source_capture_keeps_independent_fields_after_getter_errors(
    original_source_capture,
):
    case = original_source_capture
    calls = []
    annotation = case.source_displays[source.THICKNESS].annotation
    native = case.source_natives[source.THICKNESS]
    first_point = case.source_entities[source.THICKNESS][0]

    def fail(name):
        def getter():
            calls.append(name)
            raise ValueError("actual diagnostic " + name)
        return getter

    annotation.GetAttachedEntityCount3 = fail("annotation count")
    annotation.GetAttachedEntityTypes = lambda: (11, 25)
    native.GetFeatureOwner = fail("source dimension owner")
    first_point.GetID = fail("point ID")
    reads = _original_source_capture_reads(case)
    assert "diagnostic.capture_error" not in reads
    for field, name in (
        ("source.annotation.count", "annotation count"),
        ("source.dimension.owner", "source dimension owner"),
        ("source.point.0.id", "point ID"),
    ):
        assert reads[field] == {"error_type": "ValueError", "read_error": "actual diagnostic " + name}
        assert calls.count(name) == 1
    assert reads["source.annotation.types.slot.1"] == {"python_type": "int", "value": 25}
    assert reads["source.annotation.entities"]["count"] == 2
    assert reads["source.annotation.entities.inventory_state"]["value"] == "unexpected_count"
    assert reads["source.point.0.X"]["value"] == 0.005
    assert reads["source.point.0.Z"]["value"] == 0.0
    assert reads["imported.annotation.owner_type"]["value"] == 0
    assert reads["imported.annotation.owner_identity.owner.view"]["value"] == 1
    assert reads["parameter.dimension.full_name"]["value"].startswith("SupplierThickness@")


@pytest.mark.parametrize("raw", (0, -1, None, False, True, 1),
                         ids=("zero", "minus-one", "null", "false", "true", "one"))
def test_original_source_capture_retains_raw_identity_type_and_bidirectionality(
    original_source_capture, monkeypatch, raw,
):
    case = original_source_capture
    native = case.source_natives[source.THICKNESS]
    query = "SupplierThickness@SupplierWasherThicknessReference"
    parameter = case.canonical_parameters[query]
    imported = _authoring_display(case, source.THICKNESS).native
    actual_same = case.app.IsSame

    def same(first, second):
        if first is native and second is parameter:
            return raw
        if first is parameter and second is native:
            return -1
        return actual_same(first, second)

    monkeypatch.setattr(case.app, "IsSame", same)
    reads = _original_source_capture_reads(case)
    assert reads["dimension.identity.source.parameter"] == {
        "python_type": type(raw).__name__, "value": raw,
    }
    assert reads["dimension.identity.parameter.source"] == {"python_type": "int", "value": -1}
    assert reads["dimension.identity.imported.imported"]["value"] == 1
    assert reads["feature.identity.source_owner.source"]["value"] == 1
    assert reads["feature.identity.imported_owner.mapped"]["value"] == 1
    assert reads["source.annotation.owner_identity.owner.model"]["value"] == 1
    assert reads["source.annotation.owner_type"]["value"] == 3
    assert reads["display.identity.source.imported"]["value"] == 0
    assert reads["source.point.0.reverse"] == {"python_type": "NoneType", "value": None}
    assert reads["attachment.identity.source.attached.0.source.point.0"]["value"] == 1
    assert reads["attachment.identity.imported.attached.0.mapped.point.0"]["value"] == 1
    assert reads["source.attached.0.correspondence_identity.forward.mapped.point.0"]["value"] == 1
    assert reads["source.attached.0.correspondence_identity_reverse.mapped.point.0.forward"]["value"] == 1
    assert imported is not native and parameter is not native
    assert case.parameter_queries[-1] == query


@pytest.mark.parametrize("raw", (None, (), [], (None, None), (11, 25), ValueError("array getter")))
def test_original_source_capture_keeps_null_empty_slots_and_array_errors(
    original_source_capture, raw,
):
    case = original_source_capture
    annotation = case.source_displays[source.THICKNESS].annotation

    def getter():
        if isinstance(raw, Exception):
            raise raw
        return raw

    annotation.GetAttachedEntityTypes = getter
    reads = _original_source_capture_reads(case, imported=False)
    assert reads["diagnostic.imported_present"] == {"python_type": "bool", "value": False}
    assert reads["imported.display.unavailable"]["value"] == "null"
    if isinstance(raw, Exception):
        assert reads["source.annotation.types"] == {
            "error_type": "ValueError", "read_error": "array getter",
        }
    else:
        assert reads["source.annotation.types"]["python_type"] == type(raw).__name__
        if type(raw) in (tuple, list):
            assert reads["source.annotation.types"]["count"] == len(raw)
            for index, value in enumerate(raw):
                assert reads[f"source.annotation.types.slot.{index}"] == {
                    "python_type": type(value).__name__, "value": value,
                }
    assert reads["source.annotation.entities.slot.0"]["present"] is True
    assert reads["source.annotation.visible"]["value"] == 1


@pytest.mark.parametrize("inventory", ("segments", "attachments", "unknown-attachment"))
def test_original_source_capture_bounds_inventory_without_unknown_interface_walks(
    original_source_capture, monkeypatch, inventory,
):
    case = original_source_capture
    touched = []

    class Unknown:
        def __getattr__(self, name):
            touched.append(name)
            raise AssertionError("unknown COM interface was traversed")

        def __repr__(self):
            raise AssertionError("COM repr is not a diagnostic")

    unknown = Unknown()
    annotation = case.source_displays[source.THICKNESS].annotation
    if inventory == "segments":
        case.diagnostic_sketch.GetSketchSegments = lambda: (unknown,) * 7
    elif inventory == "attachments":
        annotation.GetAttachedEntityCount3 = lambda: 7
        annotation.GetAttachedEntities3 = lambda: (unknown,) * 7
        annotation.GetAttachedEntityTypes = lambda: [11] * 7
    else:
        annotation.GetAttachedEntities3 = lambda: (unknown, unknown)
    actual_binding = washer._early_bound

    def bind(value, interface):
        assert value is not unknown, "unknown attachment was duck-cast"
        return actual_binding(value, interface)

    monkeypatch.setattr(washer, "_early_bound", bind)
    reads = _original_source_capture_reads(case)
    assert not touched
    assert "diagnostic.capture_error" not in reads
    if inventory == "segments":
        assert reads["source.segments.overflow"]["value"] == 6
        assert reads["source.segments"]["count"] == 7
        assert "source.segment.interface" not in reads
    elif inventory == "attachments":
        assert reads["source.annotation.entities.overflow"]["value"] == 5
        assert reads["source.annotation.types.overflow"]["value"] == 5
        assert "source.annotation.entities.slot.2" not in reads
        assert "source.attached.0.interface" not in reads
    else:
        assert reads["source.attached.0.interface_unavailable"]["value"] == (
            "no_native_identity_to_known_endpoint"
        )


def test_original_source_capture_does_not_retry_failed_correspondence(
    original_source_capture, monkeypatch,
):
    case = original_source_capture
    view = case.original[case.side]
    first = case.source_entities[source.THICKNESS][0]
    actual_forward = view.GetCorresponding
    attempts = []

    def forward(value):
        if value is first:
            attempts.append(value)
            raise ValueError("known point forward failed")
        return actual_forward(value)

    monkeypatch.setattr(view, "GetCorresponding", forward)
    reads = _original_source_capture_reads(case)
    assert attempts == [first]
    assert reads["source.point.0.forward"] == {
        "error_type": "ValueError", "read_error": "known point forward failed",
    }
    assert reads["source.attached.0.forward.unavailable"]["value"] == (
        "prior_getter_failed:source.point.0.forward"
    )
    assert reads["imported.annotation.visible"]["value"] == 1


@pytest.mark.parametrize("first_kind", ("wrong-dimension", "null"))
def test_original_source_capture_labels_first_display_without_parameter_substitution(
    original_source_capture, first_kind,
):
    case = original_source_capture
    feature = case.features[source.THICKNESS_FEATURE]
    actual = case.source_displays[source.THICKNESS]
    calls = []
    other_native = _ReadSurface(
        FullName="UnexpectedDimension@UnexpectedSubfeature@washer.SLDPRT",
        Name="UnexpectedDimension", GetFeatureOwner=lambda: feature,
    )
    other_display = _ReadSurface(
        GetDimension2=lambda _index: other_native,
        GetNameForSelection=lambda: "UnexpectedDimension@FirstDisplay",
        GetAnnotation=actual.GetAnnotation, Type2=2,
    )

    def first():
        calls.append("first")
        return None if first_kind == "null" else other_display

    feature.GetFirstDisplayDimension = first
    reads = _original_source_capture_reads(case)
    assert calls == ["first"]
    assert reads["source.display_origin"]["value"] == "feature_first_display_not_named_enumeration"
    assert reads["parameter.dimension.full_name"]["value"].startswith("SupplierThickness@")
    if first_kind == "null":
        assert reads["source.first_display"] == {"python_type": "NoneType", "value": None}
        assert reads["source.first_display.unavailable"]["value"] == "null"
        assert "source.dimension.full_name" not in reads
        assert reads["imported.annotation.visible"]["value"] == 1
    else:
        assert reads["source.first_display.dimension_state"]["value"] == "unexpected_first_display"
        assert reads["source.dimension.full_name"]["value"] == other_native.FullName
        assert reads["source.dimension.name"]["value"] == "UnexpectedDimension"
        assert reads["dimension.identity.source.parameter"]["value"] == 0
    assert "diagnostic.capture_error" not in reads


def test_original_source_capture_identity_getter_failure_is_not_retried(
    original_source_capture, monkeypatch,
):
    case = original_source_capture
    feature = case.features[source.THICKNESS_FEATURE]
    actual_same = case.app.IsSame
    calls = []

    def same(first, second):
        if first is feature and second is feature:
            calls.append((first, second))
            raise ValueError("actual feature self identity failed")
        return actual_same(first, second)

    monkeypatch.setattr(case.app, "IsSame", same)
    reads = _original_source_capture_reads(case)
    assert len(calls) == 1
    assert reads["feature.identity.source.source.unavailable"]["value"].startswith(
        "prior_getter_failed:",
    )
    errors = [field for field in reads.values() if field.get("error_type") == "ValueError"]
    assert errors == [{
        "error_type": "ValueError", "read_error": "actual feature self identity failed",
    }]
    assert reads["source.annotation.visible"]["value"] == 1
    assert reads["imported.annotation.visible"]["value"] == 1


def test_original_source_capture_common_saved_boundary_uses_fresh_actual_view(
    original_source_capture, monkeypatch,
):
    case = original_source_capture
    view = case.fresh[case.side]
    display = _display(case, source.THICKNESS)
    references = tuple(
        washer._reference(
            fresh_display, fresh_view, fresh_display.label, VALUES[fresh_display.label],
            imported=fresh_display.label in case.arguments["bands"],
        )
        for fresh_view in case.fresh.values() for fresh_display in fresh_view.displays
    )
    original = RuntimeError("fresh saved-context original-source gate")
    actual_capture = washer._capture_original_washer_source_failure
    captured = []

    def refuse(*_args, **_kwargs):
        raise original

    def capture(error, adapter, model, owning_view, **kwargs):
        captured.append((owning_view, kwargs["imported"], kwargs["phase"]))
        return actual_capture(error, adapter, model, owning_view, **kwargs)

    monkeypatch.setattr(washer, "assert_supplier_washer_references", refuse)
    monkeypatch.setattr(washer, "_capture_original_washer_source_failure", capture)
    with pytest.raises(RuntimeError) as caught:
        washer.assert_supplier_washer_dimensions(
            case.adapter, case.fresh, references, **case.arguments,
        )
    assert caught.value is original
    assert captured == [(view, display, "final_or_saved")]
    assert captured[0][0] is not case.original[case.side]
    prefix = "supplier washer source attachment readback: "
    reads = json.loads(next(note[len(prefix):] for note in original.__notes__
                            if note.startswith(prefix)))["reads"]
    assert reads["view.configuration"]["value"] == view.ReferencedConfiguration
    assert reads["source.active_configuration.name"]["value"] == "OfflineActiveSourceConfig"
    assert reads["imported.annotation.owner_identity.owner.view"]["value"] == 1
    assert reads["feature.identity.imported_owner.mapped"]["value"] == 1
    assert not case.app.open_calls and not case.app.close_calls
    assert not case.rebuilds


@pytest.mark.parametrize("fault", ("forward", "reverse", "identity", "point", "mapped-point"))
def test_original_source_capture_rebound_aliases_do_not_retry_failed_reads(
    original_source_capture, monkeypatch, fault,
):
    case = original_source_capture
    feature = case.features[source.THICKNESS_FEATURE]
    view = case.original[case.side]
    mapped_feature = case.mapped_features[view][source.THICKNESS_FEATURE]
    first_point = case.source_entities[source.THICKNESS][0]
    attempts = []
    actual_forward = view.GetCorresponding
    actual_reverse = case.model.Extension.GetCorresponding2
    actual_same = case.app.IsSame

    def refuse():
        attempts.append(fault)
        raise ValueError("rebound native " + fault)

    if fault == "forward":
        monkeypatch.setattr(view, "GetCorresponding", lambda value:
                            refuse() if value is first_point else actual_forward(value))
    elif fault == "reverse":
        monkeypatch.setattr(case.model.Extension, "GetCorresponding2", lambda value:
                            refuse() if value is mapped_feature else actual_reverse(value))
    elif fault == "identity":
        monkeypatch.setattr(case.app, "IsSame", lambda first, second:
                            refuse() if first is feature and second is feature else actual_same(first, second))
    elif fault == "point":
        first_point.GetID = refuse
    else:
        case.mapped_entities[view][source.THICKNESS][0].GetID = refuse
    transport = _install_original_capture_rebinder(case, monkeypatch)
    annotation = case.source_displays[source.THICKNESS].annotation
    actual_entities = annotation.GetAttachedEntities3
    annotation.GetAttachedEntities3 = lambda: tuple(transport.wrap(value) for value in actual_entities())
    reads = _original_source_capture_reads(case)
    assert transport.counts.bindings > 10
    assert len(transport.wrappers) > transport.counts.bindings
    assert attempts == [fault]
    assert "diagnostic.capture_error" not in reads
    field = {
        "forward": "source.point.0.forward", "reverse": "feature.reverse",
        "identity": "feature.identity.source.source", "point": "source.point.0.id",
        "mapped-point": "forward.point.0.id",
    }[fault]
    assert reads[field] == {"error_type": "ValueError", "read_error": "rebound native " + fault}
    if fault in {"forward", "reverse"}:
        skipped = ("source.attached.0.forward.unavailable" if fault == "forward"
                   else "mapped.feature.reverse.unavailable")
        assert reads[skipped]["value"] == "prior_getter_failed:" + field
    elif fault == "point":
        assert reads["source.attached.0.details_from"]["value"] == "source.point.0"
    elif fault == "mapped-point":
        assert reads["mapped.point.0.details_from"]["value"] == "forward.point.0"
        assert reads["imported.attached.0.details_from"]["value"] == "forward.point.0"
    assert reads["source.annotation.visible"]["value"] == 1
    assert reads["imported.annotation.visible"]["value"] == 1


def test_original_source_capture_retains_raw_and_bound_wrapper_lifetimes(
    original_source_capture, monkeypatch,
):
    case = original_source_capture
    transport = _install_original_capture_rebinder(case, monkeypatch, check_lifetime=True)
    reads = _original_source_capture_reads(case)
    assert "diagnostic.capture_error" not in reads
    assert transport.counts.bindings > 10
    assert reads["source.point.0.id"]["count"] == 2
    assert reads["source.point.1.id"]["count"] == 2
    # The transport retains only weakrefs to wrapper instances; each bound
    # wrapper holds the stable surface/dispatch, not its original raw wrapper.
    gc.collect()
    assert all(reference() is None for reference in transport.wrappers)


def test_original_source_capture_native_equality_does_not_merge_owner_contexts(
    original_source_capture, monkeypatch,
):
    case = original_source_capture
    feature = case.features[source.THICKNESS_FEATURE]
    mapped = case.mapped_features[case.original[case.side]][source.THICKNESS_FEATURE]
    query = "SupplierThickness@SupplierWasherThicknessReference"
    dimensions = {
        "source": case.source_natives[source.THICKNESS],
        "parameter": case.canonical_parameters[query],
        "imported": _authoring_display(case, source.THICKNESS).native,
    }
    calls = {name: 0 for name in dimensions}

    def owner(name):
        calls[name] += 1
        return feature if name == "parameter" else mapped

    for name, native in dimensions.items():
        native.GetFeatureOwner = lambda name=name: owner(name)
    _install_original_capture_rebinder(case, monkeypatch)
    reads = _original_source_capture_reads(case)
    assert calls == {"source": 1, "parameter": 1, "imported": 1}
    assert reads["dimension.identity.source.parameter"]["value"] == 1
    assert reads["dimension.identity.source.imported"]["value"] == 1
    assert reads["feature.identity.source_owner.source"]["value"] == 0
    assert reads["feature.identity.source_owner.mapped"]["value"] == 1
    assert reads["feature.identity.parameter_owner.source"]["value"] == 1
    assert reads["feature.identity.imported_owner.mapped"]["value"] == 1
    assert "diagnostic.capture_error" not in reads


@pytest.mark.parametrize("context", ("source", "mapped"))
@pytest.mark.parametrize("fault", ("wrong-type", "type-error"))
def test_original_source_capture_requires_observed_profile_before_sketch_binding(
    original_source_capture, context, fault,
):
    case = original_source_capture
    feature = (case.features[source.THICKNESS_FEATURE] if context == "source" else
               case.mapped_features[case.original[case.side]][source.THICKNESS_FEATURE])
    calls = []

    def kind():
        calls.append("type")
        if fault == "type-error":
            raise ValueError("observed feature type unavailable")
        return "RefPlane"

    def forbidden_specific():
        calls.append("specific")
        pytest.fail("unknown specific-feature interface was requested")

    feature.GetTypeName2 = kind
    feature.GetSpecificFeature2 = forbidden_specific
    reads = _original_source_capture_reads(case)
    assert calls == ["type"]
    assert reads[f"{context}.sketch.unavailable"]["value"] == (
        "feature_type_getter_failed" if fault == "type-error" else "feature_type_not_ProfileFeature"
    )
    assert f"{context}.sketch.interface" not in reads
    assert f"{context}.segments" not in reads
    if fault == "type-error":
        assert reads[f"{context}.feature.type"] == {
            "error_type": "ValueError", "read_error": "observed feature type unavailable",
        }
    else:
        assert reads[f"{context}.feature.type"]["value"] == "RefPlane"
    assert reads["parameter.dimension.full_name"]["value"].startswith("SupplierThickness@")
    assert reads["source.annotation.count"]["value"] == 2
    assert reads["imported.annotation.count"]["value"] == 2
    assert "diagnostic.capture_error" not in reads


@pytest.mark.parametrize("count", (7, None, True, ValueError("sketch-wide point count unavailable")),
                         ids=("extra-point", "null-count", "boolean-count", "count-error"))
def test_original_source_capture_known_endpoints_survive_unrelated_point_count(
    original_source_capture, count,
):
    case = original_source_capture
    calls = []
    segment = case.diagnostic_sketch.GetSketchSegments()[0]
    actual_start, actual_end = segment.GetStartPoint2, segment.GetEndPoint2

    def count_getter():
        calls.append("count")
        if isinstance(count, Exception):
            raise count
        return count

    def endpoint(name, getter):
        calls.append(name)
        return getter()

    case.diagnostic_sketch.GetSketchPointsCount2 = count_getter
    segment.GetStartPoint2 = lambda: endpoint("start", actual_start)
    segment.GetEndPoint2 = lambda: endpoint("end", actual_end)
    reads = _original_source_capture_reads(case)
    assert calls == ["count", "start", "end"]
    if isinstance(count, Exception):
        assert reads["source.point_count"] == {
            "error_type": "ValueError", "read_error": "sketch-wide point count unavailable",
        }
    else:
        assert reads["source.point_count"] == {"python_type": type(count).__name__, "value": count}
    assert reads["source.expected_endpoint_count"]["value"] == 2
    assert reads["source.start"]["present"] is True
    assert reads["source.end"]["present"] is True
    assert reads["source.point.0.X"]["value"] == 0.005
    assert reads["source.point.1.id"]["count"] == 2
    assert reads["source.point.0.forward"]["present"] is True
    assert reads["attachment.identity.source.attached.0.source.point.0"]["value"] == 1
    assert "diagnostic.capture_error" not in reads


@pytest.mark.parametrize("endpoint", ("start", "end"))
@pytest.mark.parametrize("fault", ("null", "error"))
def test_original_source_capture_endpoint_null_and_error_leave_other_endpoint_intact(
    original_source_capture, endpoint, fault,
):
    case = original_source_capture
    segment = case.diagnostic_sketch.GetSketchSegments()[0]
    calls = []

    def getter():
        calls.append(endpoint)
        if fault == "error":
            raise ValueError("individual line endpoint unavailable")
        return None

    setattr(segment, "GetStartPoint2" if endpoint == "start" else "GetEndPoint2", getter)
    reads = _original_source_capture_reads(case)
    assert calls == [endpoint]
    assert reads[f"source.{endpoint}"] == (
        {"python_type": "NoneType", "value": None} if fault == "null" else
        {"error_type": "ValueError", "read_error": "individual line endpoint unavailable"}
    )
    other = "1" if endpoint == "start" else "0"
    assert reads[f"source.point.{other}.X"]["value"] == 0.005
    assert reads[f"source.point.{other}.id"]["count"] == 2
    assert reads["imported.annotation.visible"]["value"] == 1
    assert "diagnostic.capture_error" not in reads


@pytest.mark.parametrize("kind", (1, None, False))
def test_original_source_capture_unknown_segment_type_never_binds_line(
    original_source_capture, kind,
):
    case = original_source_capture
    segment = case.diagnostic_sketch.GetSketchSegments()[0]
    segment.GetType = lambda: kind
    segment.GetStartPoint2 = lambda: pytest.fail("unknown native segment was cast as line")
    segment.GetEndPoint2 = segment.GetStartPoint2
    reads = _original_source_capture_reads(case)
    assert reads["source.segment.type"] == {"python_type": type(kind).__name__, "value": kind}
    assert reads["source.endpoints.unavailable"]["value"] == "unexpected_segment_type"
    assert "source.line.interface" not in reads
    assert "source.start" not in reads
    assert reads["source.annotation.visible"]["value"] == 1
    assert "diagnostic.capture_error" not in reads


def test_original_source_capture_has_distinct_diagnostic_operation_span(
    original_source_capture, monkeypatch,
):
    calls = []
    actual_span = washer._telemetry.span

    def span(name, **kwargs):
        calls.append(name)
        return actual_span(name, **kwargs)

    monkeypatch.setattr(washer._telemetry, "span", span)
    _original_source_capture_reads(original_source_capture)
    assert calls == ["drawing.capture_original_supplier_washer_source_failure"]


def test_original_source_capture_internal_error_receipt_preserves_captured_exception(
    original_source_capture, monkeypatch,
):
    class RefusedMetadata:
        def __getitem__(self, _label):
            raise ValueError("diagnostic inventory metadata failure")

    monkeypatch.setattr(washer, "SOURCE_DIMENSIONS", RefusedMetadata())
    reads = _original_source_capture_reads(original_source_capture)
    assert reads["diagnostic.capture_error"] == {
        "python_type": "tuple", "count": 2, "items": [
            {"python_type": "str", "value": "ValueError"},
            {"python_type": "str", "value": "diagnostic inventory metadata failure"},
        ],
    }
    assert reads["source.document_type"]["value"] == 1
    assert reads["view.configuration"]["value"] == original_source_capture.original[
        original_source_capture.side
    ].ReferencedConfiguration


@pytest.mark.parametrize("failure_stage", ("none", "logging", "note"))
@pytest.mark.parametrize("label", (source.THICKNESS, source.OUTER_DIAMETER))
def test_source_attachment_diagnostic_preserves_original_exception(
    saved_washer, monkeypatch, failure_stage, label,
):
    """Exercise the real settled caller; receipts here are offline transport only."""
    case = saved_washer
    if label not in case.arguments["bands"]:
        pytest.skip("this fixture deliberately uses a physical rim rather than an imported OD")

    class NoteFailure(RuntimeError):
        def add_note(self, note):
            raise ValueError("diagnostic note transport failed")

    original = (NoteFailure if failure_stage == "note" else RuntimeError)(
        "original named-owner or attachment refusal"
    )
    if failure_stage != "note":
        original.add_note("original native refusal detail")
    calls = []
    original_guard = washer.assert_supplier_washer_source_attachment

    def fail_guard(adapter, model, display, **arguments):
        if arguments["label"] != label:
            return original_guard(adapter, model, display, **arguments)
        calls.append(("guard", adapter, model, display, arguments))
        raise original

    # Deliberately do not replace a private receipt/snapshot implementation.
    # Failure reporting may change shape; it must never replace the refusal.

    def log(message):
        calls.append(("log", message))
        if failure_stage == "logging":
            raise ValueError("diagnostic logging failed")

    monkeypatch.setattr(washer, "assert_supplier_washer_source_attachment", fail_guard)
    monkeypatch.setattr(washer._telemetry, "info", log)
    with pytest.raises(RuntimeError) as caught:
        case.proof()
    assert caught.value is original
    guard = next(call for call in calls if call[0] == "guard")
    expected_view = case.original[case.side if label == source.THICKNESS else case.face]
    assert guard[4] == dict(label=label, axis=case.arguments["axis"], bore_mm=4.0,
                           outer_mm=10.0, thickness_mm=0.91, view=expected_view)
    assert sum(call[0] == "guard" for call in calls) == 1
    if failure_stage != "note":
        assert "original native refusal detail" in original.__notes__
    assert not case.app.open_calls
    assert not case.app.close_calls
    assert case.source_path.read_bytes() == case.source_bytes


def test_successful_source_attachment_never_emits_failure_diagnostic(saved_washer, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("failure-only diagnostic was emitted on the successful path")

    monkeypatch.setattr(washer._telemetry, "info", forbidden)
    saved_washer.proof()
    assert not saved_washer.messages


@pytest.mark.parametrize("failure_stage", ("none", "logging", "note", "both"))
@pytest.mark.parametrize("relation", ("native", "source-parameter", "imported-parameter"))
def test_native_source_context_error_survives_receipt_reporting_failures(
    saved_washer, monkeypatch, failure_stage, relation,
):
    case = saved_washer
    view, display = _source_context(case)
    note_attempts = []
    log_attempts = []

    class NoteFailure(RuntimeError):
        def add_note(self, note):
            note_attempts.append(note)
            raise ValueError("native refusal note reporting failed")

    failure = (NoteFailure if failure_stage in {"note", "both"} else RuntimeError)(
        "native IsSame refused the independent dimension identity read",
    )
    actual_is_same = case.app.IsSame
    native = case.source_natives[source.THICKNESS]
    feature_name, dimension_name = source.SOURCE_DIMENSIONS[source.THICKNESS]
    canonical = case.canonical_parameters[f"{dimension_name}@{feature_name}"]
    left, right = {
        "native": (display.native, native),
        "source-parameter": (native, canonical),
        "imported-parameter": (display.native, canonical),
    }[relation]

    def same(first, second):
        if first is left and second is right:
            raise failure
        return actual_is_same(first, second)

    def log(message):
        log_attempts.append(message)
        if failure_stage in {"logging", "both"}:
            raise ValueError("native refusal telemetry reporting failed")

    monkeypatch.setattr(case.app, "IsSame", same)
    monkeypatch.setattr(source._telemetry, "info", log)
    with pytest.raises(RuntimeError) as caught:
        _check_source(case, display, view=view)
    assert caught.value is failure
    if failure_stage in {"note", "both"}:
        assert note_attempts
    else:
        assert any("supplier washer source attachment readback:" in note
                   for note in failure.__notes__)
    if failure_stage == "logging":
        assert log_attempts
    assert case.source_path.read_bytes() == case.source_bytes
    assert case.path.read_bytes() == case.original_bytes


# Placement controls use the real washer consumer, strict three-reference proof,
# neutral shelf and native display-data reader. These are offline native-shaped
# inputs, not a claim that the changed source has passed native/MRC acceptance.
def _replace_authoring_displays(case):
    for view in case.original.values():
        replacement = []
        for old in view.displays:
            display = _Display(old.label, old.native, view, old.annotation.attached,
                               units=old.units, precision=old.precision)
            for name in ("selection_name", "layout", "_offset", "Diametric", "ArrowSide",
                         "SolidLeader", "broken", "use_doc_broken", "second_arrow",
                         "use_doc_second_arrow", "placement_defect", "text"):
                value = getattr(old, name)
                setattr(display, name, deepcopy(value) if name in {"layout", "text"} else value)
            replacement.append(display)
        view.displays = replacement


def test_washer_consumer_uses_only_actual_vertical_thickness_and_fresh_handles(
    saved_washer, monkeypatch,
):
    case = saved_washer
    _reset_authoring_layout(case)
    actual_shelf = washer.shelve_reference_text
    calls, inventories = [], []

    def shelf(adapter, *, reacquire, axes, label, force=()):
        calls.append((adapter, dict(axes), tuple(force)))

        def fresh():
            found = reacquire()
            inventories.append(dict(found))
            return found

        return actual_shelf(adapter, reacquire=fresh, axes=axes, label=label, force=force)

    monkeypatch.setattr(washer, "shelve_reference_text", shelf)
    case.transition.on_rebuild = lambda _label: _replace_authoring_displays(case)
    native = case.source_natives[source.THICKNESS]
    before_sources = tuple(
        (label, dim.SystemValue, dim.Tolerance.Type, dim.Tolerance.GetMinValue(),
         dim.Tolerance.GetMaxValue(), tuple(sorted(case.source_displays[label].text.items())))
        for label, dim in case.source_natives.items()
    )
    proof = _author_again(case)
    assert calls == [(case.adapter, {native.FullName: 1}, (native.FullName,))]
    assert len(inventories) >= 5
    assert all(set(found) == {native.FullName} for found in inventories)
    assert all(found[native.FullName].native is not native for found in inventories)
    assert all(case.app.IsSame(found[native.FullName].native, native) == 1 for found in inventories)
    assert len({id(found[native.FullName]) for found in inventories}) >= 4
    current = _authoring_display(case, source.THICKNESS)
    assert current.OffsetText is True
    geometry = reference_text.measure_reference_text(case.adapter, current, axis=1, label="thickness")
    assert geometry["text"].ymin == pytest.approx(0.03946)
    assert geometry["tips"] == ((0.055, 0.03), (0.055, 0.03091))
    assert geometry["witnesses"] == ((0.03, 0.04, 0.056), (0.03091, 0.04, 0.056))
    assert tuple(
        (label, dim.SystemValue, dim.Tolerance.Type, dim.Tolerance.GetMinValue(),
         dim.Tolerance.GetMaxValue(), tuple(sorted(case.source_displays[label].text.items())))
        for label, dim in case.source_natives.items()
    ) == before_sources
    count = len(case.rebuilds)
    writes = tuple(tuple(display.placement_calls) for view in case.original.values()
                   for display in view.displays)
    proof()
    assert len(case.rebuilds) == count
    assert tuple(tuple(display.placement_calls) for view in case.original.values()
                 for display in view.displays) == writes


_PLACEMENT_PHASES = (
    "reference text measured", "reference offset anchors", "reference native offset mode",
    "measured reference text shelves", "native diameter leaders", "complete diameter captions",
)


def _corrupt_original_source(case, fault):
    label = source.THICKNESS
    if fault == "original-owner":
        case.source_natives[label].GetFeatureOwner = lambda: case.mapped_features[
            case.original[case.side]
        ][source.THICKNESS_FEATURE]
    elif fault == "original-attachment":
        case.source_displays[label].annotation.attached = (case.source_entities[label][0],) * 2
    elif fault == "canonical-parameter":
        feature_name, dimension_name = source.SOURCE_DIMENSIONS[label]
        query = f"{dimension_name}@{feature_name}"
        case.canonical_parameters[query] = _native_clone(case.canonical_parameters[query])
    else:
        raise AssertionError(fault)


@pytest.mark.parametrize("stage", ("before-import", "after-import"))
@pytest.mark.parametrize("fault", ("original-owner", "original-attachment", "canonical-parameter"))
def test_public_authoring_rechecks_original_source_before_and_after_import(
    saved_washer, monkeypatch, stage, fault,
):
    case = saved_washer
    _reset_authoring_layout(case)
    imported_views = []
    if stage == "before-import":
        _corrupt_original_source(case, fault)

    def curate(_adapter, view, **_kwargs):
        assert stage == "after-import", "invalid original source reached native import"
        imported_views.append(view)
        if len(imported_views) == 1:
            _corrupt_original_source(case, fault)
        return [SimpleNamespace(GetSpecificAnnotation=lambda display=display: display)
                for display in view.displays]

    def forbidden_authoring(*_args, **_kwargs):
        pytest.fail("original-source refusal must precede rim authoring and placement proof")

    monkeypatch.setattr(washer, "curate_view_dimensions", curate)
    monkeypatch.setattr(washer, "dimension_name", lambda _adapter, annotation:
                        source.SOURCE_DIMENSIONS[annotation.GetSpecificAnnotation().label][1])
    # Downstream sentinels prove the boundary; no source checker or import
    # unit-transfer assertion is substituted.
    monkeypatch.setattr(washer, "_native_diameter", forbidden_authoring)
    monkeypatch.setattr(washer, "_supplier_washer_proof", forbidden_authoring)
    with pytest.raises(RuntimeError):
        washer.supplier_washer_dimensions(case.adapter, case.original, **case.arguments)
    expected_imports = 2 if source.OUTER_DIAMETER in case.arguments["bands"] else 1
    assert len(imported_views) == (0 if stage == "before-import" else expected_imports)
    assert not case.rebuilds
    assert all(not display.placement_calls for view in case.original.values() for display in view.displays)
    assert not case.app.open_calls
    assert not case.app.close_calls
    assert case.path.read_bytes() == case.original_bytes
    assert case.source_path.read_bytes() == case.source_bytes


@pytest.mark.parametrize("stage", ("settled", "saved"))
@pytest.mark.parametrize("fault", ("original-owner", "original-attachment", "canonical-parameter"))
def test_final_proofs_refuse_original_source_corruption_without_repair(saved_washer, stage, fault):
    case = saved_washer
    _corrupt_original_source(case, fault)
    collections = (case.original, case.fresh)
    writes = tuple(tuple(display.placement_calls) for collection in collections
                   for view in collection.values() for display in view.displays)
    count = len(case.rebuilds)
    with pytest.raises(RuntimeError):
        if stage == "saved":
            case.invalidate()
            case.proof.saved_check(case.adapter, case.path)
        else:
            case.proof()
    assert len(case.rebuilds) == count
    assert tuple(tuple(display.placement_calls) for collection in collections
                 for view in collection.values() for display in view.displays) == writes
    if stage == "saved":
        _assert_closed_unchanged(case)
    else:
        assert not case.app.open_calls
        assert not case.app.close_calls
        assert case.path.read_bytes() == case.original_bytes
        assert case.source_path.read_bytes() == case.source_bytes


def _corrupt_placement_source(case, fault):
    thickness = _authoring_display(case, source.THICKNESS)
    face = _authoring_display(case, source.BORE_DIAMETER)
    if fault == "source-format":
        case.source_displays[source.THICKNESS].text[2] = "wrong source unit suffix"
    elif fault in {"original-owner", "original-attachment", "canonical-parameter"}:
        _corrupt_original_source(case, fault)
    elif fault == "import-format":
        face.text[1] = "wrong diameter prefix"
    elif fault == "value":
        thickness.native.SystemValue += 0.001
    elif fault == "band":
        thickness.native.Tolerance.minimum = -0.005
    elif fault == "attachment":
        thickness.annotation.attached = (case.source_entities[source.THICKNESS][0],) * 2
    elif fault == "source-identity":
        other = _Part(**vars(case.model))
        for view in case.original.values():
            view.ReferencedDocument = other
    elif fault == "source-path":
        case.path_state.path = case.source_path.with_name("wrong-source.SLDPRT")
    elif fault == "configuration":
        case.original["*Isometric"].ReferencedConfiguration = "wrong late configuration"
    elif fault == "full-name":
        thickness.native.FullName = thickness.native.FullName.replace("washer.SLDPRT", "other.SLDPRT")
    elif fault == "native-identity":
        thickness.native = _native_clone(thickness.native)
    elif fault == "inventory":
        case.original[case.face].displays.pop()
    elif fault == "inventory-extra":
        view = case.original[case.face]
        view.displays.append(_Display(face.label, face.native, view, face.annotation.attached,
                                      units=face.units, precision=face.precision))
    elif fault == "view-inventory":
        case.original.pop("*Isometric")
    elif fault == "rim":
        case.body_edges.pop()
    else:
        raise AssertionError(fault)


@pytest.mark.parametrize("phase", _PLACEMENT_PHASES)
@pytest.mark.parametrize("fault", (
    "source-format", "import-format", "value", "band", "attachment", "source-identity",
    "source-path", "configuration", "full-name", "native-identity", "inventory",
    "inventory-extra", "view-inventory", "rim",
    "original-owner", "original-attachment", "canonical-parameter",
))
def test_every_native_placement_phase_repeats_complete_original_source_proof(
    saved_washer, phase, fault,
):
    case = saved_washer
    _reset_authoring_layout(case)
    reached = []

    def corrupt(label):
        if label.endswith(phase):
            reached.append(label)
            _corrupt_placement_source(case, fault)

    case.transition.on_rebuild = corrupt
    with pytest.raises(RuntimeError):
        _author_again(case)
    assert len(reached) == 1
    assert not case.app.open_calls
    assert case.path.read_bytes() == case.original_bytes
    assert case.source_path.read_bytes() == case.source_bytes


@pytest.mark.parametrize("fault", (
    "source-format", "import-format", "attachment", "inventory",
    "original-owner", "original-attachment", "canonical-parameter",
))
def test_bad_three_reference_input_is_refused_before_any_native_placement(saved_washer, fault):
    case = saved_washer
    _reset_authoring_layout(case)
    _corrupt_placement_source(case, fault)
    with pytest.raises(RuntimeError):
        _author_again(case)
    assert not case.rebuilds
    assert all(not display.placement_calls for view in case.original.values() for display in view.displays)


@pytest.mark.parametrize("defect, message", (
    ("rejected-seed", "seed"), ("ignored-seed", "anchor did not settle"),
    ("ignored-offset", "offset"), ("rejected-shelf", "shelf"),
    ("ignored-shelf", "crowds"),
))
def test_washer_linear_consumer_refuses_native_setter_failures_and_successful_noops(
    saved_washer, defect, message,
):
    case = saved_washer
    _reset_authoring_layout(case)
    display = _authoring_display(case, source.THICKNESS)
    # A distinct pre-seed text anchor makes an ignored seed observable; this
    # never changes the independently seeded physical stations.
    display.set_position(0.057, 0.03, 0.0)
    display.placement_calls.clear()
    display.placement_defect = defect
    with pytest.raises(RuntimeError, match=message):
        _author_again(case)
    assert not case.app.open_calls
    if defect in {"rejected-shelf", "ignored-shelf"}:
        moves = [call[1:] for call in display.placement_calls if call[0] == "SetPosition2"]
        assert len(moves) == 3
        assert moves[0] == moves[1]  # Seed, then successful offset enable.
        assert moves[2] != moves[1]  # The defect targets only the final shelf.
        assert display.OffsetText is True


@pytest.mark.parametrize("defect, message", (
    ("rejected-seed", "caption move was rejected"),
    ("ignored-seed", "caption crowds"),
    ("rejected-leader", "broken horizontal leader"),
    ("ignored-leader", "near-side single-arrow style did not persist"),
))
def test_washer_diameter_consumer_refuses_native_setter_failures_and_noops(
    saved_washer, defect, message,
):
    case = saved_washer
    _reset_authoring_layout(case)
    _authoring_display(case, source.BORE_DIAMETER).placement_defect = defect
    with pytest.raises(RuntimeError, match=message):
        _author_again(case)


@pytest.mark.parametrize("below_ref", (1, 2, 4))
def test_complete_bore_caption_not_numeric_anchor_drives_native_right_clearance(
    saved_washer, below_ref,
):
    case = saved_washer
    _reset_authoring_layout(case)
    display = _authoring_display(case, source.BORE_DIAMETER)
    callout = "FOR No. 10 SCREW SIZE"
    display.text[4] = callout
    case.source_displays[source.BORE_DIAMETER].text[4] = callout
    case.references = tuple(
        washer._reference(display, display.view, source.BORE_DIAMETER, 4.0,
                          imported=source.BORE_DIAMETER in case.arguments["bands"], callout=callout)
        if reference.label == source.BORE_DIAMETER else reference for reference in case.references
    )
    # Native below row is much farther left than both numeric and prefix rows.
    display.layout["texts"].append(dict(
        t=callout, pos=(0.034, 0.016, 0.0), w=0.036, h=0.0035, ref=below_ref, ang=0.0,
    ))
    initial = display.layout["position"]
    proof = _author_again(case)
    text, fragments, _geometry = washer._diameter_caption(case.adapter, display, label="bore")
    assert len(fragments) == 3
    assert text.xmin >= 0.04 + washer.CLEAR_GAP_M
    assert text.xmin == pytest.approx(0.043556 + washer.CLEAR_GAP_M + washer.PLACE_SETTLE_M)
    displacement = display.layout["position"][0] - initial[0]
    # Preserve the minimum full-caption move, allowing only subtraction roundoff.
    assert displacement >= 0.011756 or displacement == pytest.approx(
        0.011756, rel=0, abs=1e-17,
    )
    assert display.text[4] == callout
    assert case.source_displays[source.BORE_DIAMETER].text[4] == callout
    proof()


@pytest.mark.parametrize("label", (source.THICKNESS, source.OUTER_DIAMETER, source.BORE_DIAMETER))
@pytest.mark.parametrize("fault", ("width-zero", "width-missing", "height-nan", "position-nan", "angle-nan"))
def test_consumer_rejects_every_unmeasurable_native_fragment(saved_washer, label, fault):
    case = saved_washer
    _reset_authoring_layout(case)
    fragment = _authoring_display(case, label).layout["texts"][0]
    if fault == "width-zero":
        fragment["w"] = 0.0
    elif fault == "width-missing":
        del fragment["w"]
    elif fault == "height-nan":
        fragment["h"] = float("nan")
    elif fault == "position-nan":
        fragment["pos"] = (float("nan"), fragment["pos"][1], 0.0)
    else:
        fragment["ang"] = float("nan")
    with pytest.raises(RuntimeError, match="unreadable|measured native size|native position"):
        _author_again(case)


def _strike_caption(display, *, arrow=False):
    graphics = deepcopy(display.graphics())
    row = display.layout["texts"][0]  # The Ø/parenthesis fragment, not numeric anchor.
    x, y, z = row["pos"]
    if arrow:
        graphics["arrows"][0][:3] = (x, y + row["h"] / 2, z)
    else:
        graphics["lines"].append(
            [0, 0, 0, 0, x - 0.001, y + row["h"] / 2, z,
             x + row["w"] + 0.001, y + row["h"] / 2, z],
        )
    display.layout["graphics"] = graphics


@pytest.mark.parametrize("arrow", (False, True), ids=("leader-through-prefix", "arrow-at-prefix"))
def test_actual_post_rebuild_caption_graphics_are_proved_not_only_move_success(
    saved_washer, arrow,
):
    case = saved_washer
    _reset_authoring_layout(case)
    reached = []

    def strike(label):
        if label.endswith("complete diameter captions"):
            reached.append(label)
            _strike_caption(_authoring_display(case, source.OUTER_DIAMETER), arrow=arrow)

    case.transition.on_rebuild = strike
    with pytest.raises(RuntimeError, match="arrow crowds|leader crosses"):
        _author_again(case)
    assert len(reached) == 1


@pytest.mark.parametrize("fault", (
    "offset", "thickness-text", "tips", "witnesses", "transverse", "diameter-position",
    "diameter-prefix", "diameter-below", "diameter-line", "diameter-arrow", "leader-style",
    "diameter-unmeasurable", "face-outline",
))
def test_saved_fresh_read_refuses_native_placement_regressions_without_repair(
    saved_washer, fault,
):
    case = saved_washer
    thickness = _display(case, source.THICKNESS)
    diameter = _display(case, source.OUTER_DIAMETER)
    if fault == "offset":
        thickness._offset = False
    elif fault == "thickness-text":
        thickness.layout["texts"][0]["pos"] = (0.049, 0.03, 0.0)
    elif fault in {"tips", "witnesses"}:
        graphics = deepcopy(thickness.graphics())
        if fault == "tips":
            graphics["arrows"][0][1] += 0.0001
        else:
            graphics["lines"][0][4] -= 0.0001
        thickness.layout["graphics"] = graphics
    elif fault == "transverse":
        x, y, z = thickness.layout["position"]
        thickness.layout["position"] = (x + 0.0001, y, z)
    elif fault == "diameter-position":
        x, y, z = diameter.layout["position"]
        diameter.layout["position"] = (x + 0.0001, y, z)
    elif fault == "diameter-prefix":
        diameter.layout["texts"][0]["pos"] = (0.039, 0.048, 0.0)
    elif fault == "diameter-below":
        diameter.layout["texts"].append(dict(
            t="FOR No. 10 SCREW SIZE", pos=(0.039, 0.018, 0.0),
            w=0.035, h=0.0035, ref=1, ang=0.0,
        ))
    elif fault in {"diameter-line", "diameter-arrow"}:
        _strike_caption(diameter, arrow=fault == "diameter-arrow")
    elif fault == "leader-style":
        diameter.broken = 1
    elif fault == "diameter-unmeasurable":
        diameter.layout["texts"][0]["w"] = float("nan")
    else:
        case.fresh[case.face].GetOutline = lambda: (0.02, 0.02, 0.041, 0.04)
    before = tuple(deepcopy(display.layout) for view in case.fresh.values() for display in view.displays)
    writes = tuple(tuple(display.placement_calls) for view in case.fresh.values() for display in view.displays)
    case.invalidate()
    count = len(case.rebuilds)
    with pytest.raises(RuntimeError) as caught:
        case.proof.saved_check(case.adapter, case.path)
    assert len(case.rebuilds) == count
    assert tuple(display.layout for view in case.fresh.values() for display in view.displays) == before
    assert tuple(tuple(display.placement_calls) for view in case.fresh.values()
                 for display in view.displays) == writes
    receipt = _exception_receipt(caught.value)
    assert all("annotation_position" in row and "native_display" in row for row in receipt["dimensions"])
    _assert_closed_unchanged(case)


def test_saved_layout_expectations_are_immutable_not_late_authoring_echo(saved_washer):
    case = saved_washer
    for collection in (case.original, case.fresh):
        display = next(display for view in collection.values() for display in view.displays
                       if display.label == source.THICKNESS)
        x, y, z = display.layout["position"]
        display.layout["position"] = (x + 0.001, y, z)
    case.invalidate()
    with pytest.raises(RuntimeError, match="transverse position moved"):
        case.proof.saved_check(case.adapter, case.path)
    _assert_closed_unchanged(case)


@pytest.mark.parametrize("fault", ("offset", "thickness-text", "diameter-prefix", "diameter-line"))
def test_final_settled_proof_is_readonly_and_rejects_late_native_regression(saved_washer, fault):
    case = saved_washer
    thickness = _authoring_display(case, source.THICKNESS)
    diameter = _authoring_display(case, source.OUTER_DIAMETER)
    if fault == "offset":
        thickness._offset = False
    elif fault == "thickness-text":
        thickness.layout["texts"][0]["pos"] = (0.049, 0.03, 0.0)
    elif fault == "diameter-prefix":
        diameter.layout["texts"][0]["pos"] = (0.039, 0.048, 0.0)
    else:
        _strike_caption(diameter)
    count = len(case.rebuilds)
    writes = tuple(tuple(display.placement_calls) for view in case.original.values()
                   for display in view.displays)
    with pytest.raises(RuntimeError):
        case.proof()
    assert len(case.rebuilds) == count
    assert tuple(tuple(display.placement_calls) for view in case.original.values()
                 for display in view.displays) == writes


@pytest.mark.parametrize("getter, field", (
    ("GetPosition", "annotation_position"), ("GetDisplayData", "native_display"),
))
def test_saved_placement_getter_errors_keep_distinct_actual_field_readback(
    saved_washer, getter, field,
):
    case = saved_washer
    display = _display(case, source.OUTER_DIAMETER)

    def refuse():
        raise RuntimeError(f"native {getter} placement-read-sentinel")

    setattr(display.annotation, getter, refuse)
    case.invalidate()
    with pytest.raises(RuntimeError) as caught:
        case.proof.saved_check(case.adapter, case.path)
    receipt = _exception_receipt(caught.value)
    row = next(row for row in receipt["dimensions"] if row["selection_name"] == display.selection_name)
    if getter == "GetDisplayData":
        assert row[field][1] == {"GetDisplayData": 1}
    else:
        assert "placement-read-sentinel" in row[field]["read_error"]
    _assert_closed_unchanged(case)


def test_recorded_mg_back_bore_measures_below_and_diameter_prefix_native_fragments(saved_washer):
    """464f6ea68 actual MG-back RD2 native display rows, not after-fix evidence."""
    case = saved_washer
    display = _display(case, source.BORE_DIAMETER)
    z = -0.002275
    display.layout["texts"] = [
        dict(t="(", pos=(0.1276871, 0.1202767, z), h=0.0035, w=0.0017208, ref=1, ang=0.0),
        dict(t="<MOD-DIAM>", pos=(0.129408, 0.1202233, z), h=0.0035, w=0.0052784, ref=1, ang=0.0),
        dict(t="0.200 in)", pos=(0.1346864, 0.1202767, z), h=0.0035, w=0.0184285, ref=1, ang=0.0),
        dict(t="FOR No. 10 SCREW SIZE", pos=(0.1147246, 0.114667, z),
             h=0.0035, w=0.0513528, ref=1, ang=0.0),
    ]
    display.layout["graphics"] = dict(
        lines=[
            [0, 0, 0, 0, 0.1041185, 0.1234101, z, 0.1131371, 0.114667, z],
            [0, 0, 0, 0, 0.0858815, 0.1410899, z, 0.1041185, 0.1234101, z],
            [0, 0, 0, 0, 0.1131371, 0.114667, z, 0.1660774, 0.114667, z],
        ],
        arrows=[[0.1041185, 0.1234101, z, 0.7179897, -0.6960538, 0,
                 0.003556, 0.000762, 0, 0, 0, -1]],
    )
    text, fragments, _geometry = washer._diameter_caption(case.adapter, display, label="actual MG-back RD2")
    assert len(fragments) == 4
    assert (text.xmin, text.ymin, text.xmax, text.ymax) == pytest.approx(
        (0.1147246, 0.114667, 0.1660774, 0.1237767),
    )
    assert fragments[1].xmin == pytest.approx(0.129408)  # The measured Ø glyph row survives.
    assert text.xmin < 0.1228 < fragments[0].xmin
    assert not display.placement_calls


def test_recorded_thrust_od_native_leader_strike_is_not_hidden_by_style_getters(saved_washer):
    """Retain the actual old OD stroke/prefix relationship; this is not a render."""
    case = saved_washer
    display = _display(case, source.OUTER_DIAMETER)
    z = -0.0019651
    display.layout["texts"] = [
        dict(t=" (", pos=(0.1146474, 0.1427486, z), h=0.0035, w=0.0030139, ref=1, ang=0.0),
        dict(t="<MOD-DIAM>", pos=(0.1176613, 0.1426951, z), h=0.0035, w=0.0052784, ref=1, ang=0.0),
        dict(t="0.375 ±0.002 in) ", pos=(0.1229397, 0.1427486, z),
             h=0.0035, w=0.0352139, ref=1, ang=0.0),
    ]
    display.layout["graphics"] = dict(
        lines=[
            [0, 0, 0, 0, 0.1162203, 0.1443043, z, 0.1130599, 0.1426951, z],
            [0, 0, 0, 0, 0.0737797, 0.1226957, z, 0.1162203, 0.1443043, z],
        ],
        arrows=[[0.1162203, 0.1443043, z, 0.8911429, 0.4537227, 0,
                 0.003556, 0.000762, 0, 0, 0, -1]],
    )
    # The small fixture outline only isolates the own-caption predicate. This
    # does not claim that the old actual thrust body cleared its caption.
    with pytest.raises(RuntimeError, match="leader crosses|arrow crowds"):
        washer._assert_diameter_placement(case.adapter, display, case.fresh[case.face], label="actual thrust OD")
    assert not display.placement_calls


def _rewrite_thickness_physical_lines(display, change):
    """Change only native line rows, never tips, witness runs or numeric ink."""
    graphics = deepcopy(display.graphics())
    lines = graphics["lines"]
    if change == "free-tail":
        # Shorten the lower free tail by 100 um. The other tail still defines
        # maximum reach, so this is not an incidental caption-clearance fault.
        lines[2][8] += 0.0001
    elif change == "interior-gap":
        near, far = list(lines[2]), list(lines[2])
        near[8], far[5] = 0.02705, 0.02695
        lines[2:3] = [near, far]
    elif change == "normal-component":
        # Retain both original axial extrema and the tip-incident stub, but
        # move only the interior physical component 100 um transversely.
        near, middle, far = (list(lines[2]) for _ in range(3))
        near[8] = middle[5] = 0.028
        middle[8] = far[5] = 0.026
        middle[4] += 0.0001
        middle[7] += 0.0001
        lines[2:3] = [near, middle, far]
    elif change in {"split", "reordered", "reversed", "split-reordered-reversed"}:
        if change in {"split", "split-reordered-reversed"}:
            fragments = []
            for row in lines[2:]:
                near, far = list(row), list(row)
                near[8] = far[5] = (row[5] + row[8]) / 2
                fragments.extend((near, far))
            lines[2:] = fragments
        if change in {"reordered", "split-reordered-reversed"}:
            lines.reverse()
        if change in {"reversed", "split-reordered-reversed"}:
            for row in lines:
                row[4:7], row[7:10] = row[7:10], row[4:7]
    else:
        raise AssertionError(change)
    display.layout["graphics"] = graphics


@pytest.mark.parametrize("phase", _PLACEMENT_PHASES[1:])
@pytest.mark.parametrize("fault", ("free-tail", "interior-gap", "normal-component"))
def test_linear_consumer_rejects_physical_line_union_changes_after_each_transition(
    saved_washer, phase, fault,
):
    case = saved_washer
    _reset_authoring_layout(case)
    display = _authoring_display(case, source.THICKNESS)
    before = reference_text.measure_reference_text(case.adapter, display, axis=1, label="before line mutation")
    numeric = (display.native.FullName, display.native.SystemValue, deepcopy(display.text))
    reached = []

    def corrupt(label):
        if label.endswith(phase):
            reached.append(label)
            _rewrite_thickness_physical_lines(display, fault)
            after = reference_text.measure_reference_text(
                case.adapter, display, axis=1, label="after line mutation",
            )
            assert after["tips"] == before["tips"]
            assert after["witnesses"] == before["witnesses"]
            assert after["physical_lines"] != before["physical_lines"]
            old_lines, new_lines = before["physical_lines"], after["physical_lines"]
            assert max(row[3] for row in new_lines) == max(row[3] for row in old_lines)
            if fault == "free-tail":
                assert min(row[2] for row in new_lines) == pytest.approx(
                    min(row[2] for row in old_lines) + 0.0001,
                )
            else:
                # The 100 um shifted middle is off-support, not a larger
                # physical normal envelope; its missing interval must survive.
                assert any(row[2] < 0.027 < row[3] for row in old_lines)
                assert not any(row[2] < 0.027 < row[3] for row in new_lines)
            assert (display.native.FullName, display.native.SystemValue, display.text) == numeric

    case.transition.on_rebuild = corrupt
    with pytest.raises(RuntimeError):
        _author_again(case)
    assert len(reached) == 1
    assert not case.app.open_calls
    assert not case.app.close_calls
    assert case.path.read_bytes() == case.original_bytes
    assert case.source_path.read_bytes() == case.source_bytes


@pytest.mark.parametrize("stage", ("settled", "saved", "saved-matching-authoring"))
@pytest.mark.parametrize("fault", ("free-tail", "interior-gap", "normal-component"))
def test_final_and_saved_proofs_refuse_physical_line_union_changes_without_repair(
    saved_washer, stage, fault,
):
    case = saved_washer
    display = (_authoring_display(case, source.THICKNESS) if stage == "settled"
               else _display(case, source.THICKNESS))
    before = reference_text.measure_reference_text(case.adapter, display, axis=1, label="captured line union")
    numeric = (display.native.FullName, display.native.SystemValue, deepcopy(display.text))
    _rewrite_thickness_physical_lines(display, fault)
    if stage == "saved-matching-authoring":
        # The reopened drawing cannot self-certify by agreeing with a late
        # mutation of the old authoring view instead of its captured union.
        _rewrite_thickness_physical_lines(_authoring_display(case, source.THICKNESS), fault)
    after = reference_text.measure_reference_text(case.adapter, display, axis=1, label="changed line union")
    assert after["tips"] == before["tips"]
    assert after["witnesses"] == before["witnesses"]
    assert after["physical_lines"] != before["physical_lines"]
    old_lines, new_lines = before["physical_lines"], after["physical_lines"]
    assert max(row[3] for row in new_lines) == max(row[3] for row in old_lines)
    if fault == "free-tail":
        assert min(row[2] for row in new_lines) == pytest.approx(
            min(row[2] for row in old_lines) + 0.0001,
        )
    else:
        # Off-support shifted ink is excluded by the real core classifier,
        # leaving a physical gap just as the explicit missing-middle case does.
        assert any(row[2] < 0.027 < row[3] for row in old_lines)
        assert not any(row[2] < 0.027 < row[3] for row in new_lines)
    assert (display.native.FullName, display.native.SystemValue, display.text) == numeric
    layout = deepcopy(display.layout)
    writes = tuple(display.placement_calls)
    count = len(case.rebuilds)
    with pytest.raises(RuntimeError):
        if stage == "settled":
            case.proof()
        else:
            case.invalidate()
            case.proof.saved_check(case.adapter, case.path)
    assert len(case.rebuilds) == count
    assert display.layout == layout
    assert tuple(display.placement_calls) == writes
    if stage == "settled":
        assert not case.app.open_calls
        assert not case.app.close_calls
        assert case.path.read_bytes() == case.original_bytes
        assert case.source_path.read_bytes() == case.source_bytes
    else:
        _assert_closed_unchanged(case)


@pytest.mark.parametrize("phase", _PLACEMENT_PHASES[1:])
@pytest.mark.parametrize("change", ("split", "reordered", "reversed", "split-reordered-reversed"))
def test_equivalent_physical_line_fragments_survive_each_transition(saved_washer, phase, change):
    case = saved_washer
    _reset_authoring_layout(case)
    display = _authoring_display(case, source.THICKNESS)
    before = reference_text.measure_reference_text(case.adapter, display, axis=1, label="original native rows")
    numeric = (display.native.FullName, display.native.SystemValue, deepcopy(display.text))
    reached = []

    def rewrite(label):
        if label.endswith(phase):
            reached.append(label)
            _rewrite_thickness_physical_lines(display, change)
            after = reference_text.measure_reference_text(
                case.adapter, display, axis=1, label="equivalent native fragments",
            )
            assert after["tips"] == before["tips"]
            assert after["witnesses"] == before["witnesses"]
            assert after["physical_lines"] == before["physical_lines"]
            assert (display.native.FullName, display.native.SystemValue, display.text) == numeric

    case.transition.on_rebuild = rewrite
    proof = _author_again(case)
    assert len(reached) == 1
    count = len(case.rebuilds)
    writes = tuple(display.placement_calls)
    proof()
    assert len(case.rebuilds) == count
    assert tuple(display.placement_calls) == writes
    assert not case.app.open_calls
    assert not case.app.close_calls
    assert case.path.read_bytes() == case.original_bytes
    assert case.source_path.read_bytes() == case.source_bytes


@pytest.mark.parametrize("stage", ("settled", "saved"))
@pytest.mark.parametrize("change", ("split", "reordered", "reversed", "split-reordered-reversed"))
def test_equivalent_physical_line_fragments_survive_final_and_saved_proofs(saved_washer, stage, change):
    case = saved_washer
    display = (_authoring_display(case, source.THICKNESS) if stage == "settled"
               else _display(case, source.THICKNESS))
    before = reference_text.measure_reference_text(case.adapter, display, axis=1, label="original line union")
    numeric = (display.native.FullName, display.native.SystemValue, deepcopy(display.text))
    original_rows = deepcopy(display.graphics()["lines"])
    _rewrite_thickness_physical_lines(display, change)
    assert display.graphics()["lines"] != original_rows
    after = reference_text.measure_reference_text(case.adapter, display, axis=1, label="equivalent line union")
    assert after["tips"] == before["tips"]
    assert after["witnesses"] == before["witnesses"]
    assert after["physical_lines"] == before["physical_lines"]
    assert (display.native.FullName, display.native.SystemValue, display.text) == numeric
    layout = deepcopy(display.layout)
    writes = tuple(display.placement_calls)
    count = len(case.rebuilds)
    if stage == "settled":
        case.proof()
    else:
        case.invalidate()
        case.proof.saved_check(case.adapter, case.path)
    assert len(case.rebuilds) == count
    assert display.layout == layout
    assert tuple(display.placement_calls) == writes
    if stage == "settled":
        assert not case.app.open_calls
        assert not case.app.close_calls
        assert case.path.read_bytes() == case.original_bytes
        assert case.source_path.read_bytes() == case.source_bytes
    else:
        _assert_closed_unchanged(case)


@pytest.mark.parametrize("phase", _PLACEMENT_PHASES[1:4])
@pytest.mark.parametrize("fault", ("tips", "witnesses"))
def test_linear_consumer_rejects_native_station_changes_after_each_transition(
    saved_washer, phase, fault,
):
    case = saved_washer
    _reset_authoring_layout(case)
    reached = []

    def corrupt(label):
        if label.endswith(phase):
            reached.append(label)
            display = _authoring_display(case, source.THICKNESS)
            graphics = deepcopy(display.graphics())
            if fault == "tips":
                graphics["arrows"][0][1] += 0.0001
            else:
                graphics["lines"][0][4] -= 0.0001
            display.layout["graphics"] = graphics

    case.transition.on_rebuild = corrupt
    with pytest.raises(RuntimeError, match="moved|native witness"):
        _author_again(case)
    assert len(reached) == 1


@pytest.mark.parametrize("resident", (True, False), ids=("resident", "drawing-autoload"))
def test_saved_material_receipt_captures_actual_raw_type_configuration_and_source_hash(
    saved_washer, resident,
):
    """Offline native getters, deliberately not the catalogue/assignment input."""
    case = saved_washer
    raw = "Unanticipated Observed DB|Not The Catalogue Material|701"
    active_name = "Actually Active Source Configuration"
    loaded = case.model if resident else _Part(**vars(case.model))
    loaded.MaterialIdName = raw
    loaded.ConfigurationManager = _ReadSurface(
        ActiveConfiguration=_ReadSurface(Name=active_name),
    )
    if not resident:
        case.model.MaterialIdName = "Old Authoring DB|Input Echo Must Not Survive|1"
        _autoload_source(case, loaded)
    # Source-side native property writes are traps, not merely unchanged bytes.
    for surface in (loaded, loaded.ConfigurationManager, loaded.ConfigurationManager.ActiveConfiguration):
        object.__setattr__(surface, "_saved_read", True)
    case.invalidate()
    case.proof.saved_check(case.adapter, case.path)
    receipt = json.loads(case.messages[0].split(": ", 1)[1])
    assert receipt["source_material_member"] == "IPartDoc.MaterialIdName"
    assert receipt["source_material_raw"] == raw
    assert receipt["source_material_return_type"] == "builtins.str"
    assert "source_material_read_error" not in receipt
    assert receipt["source_active_configuration_member"] == (
        "IModelDoc2.ConfigurationManager.ActiveConfiguration.Name"
    )
    assert receipt["source_active_configuration"] == active_name
    assert active_name not in {view.ReferencedConfiguration for view in case.fresh.values()}
    assert receipt["source_path"] == str(case.source_path)
    assert type(receipt["source_type"]) is int and receipt["source_type"] == 1
    assert receipt["source_read_only"] is True
    assert receipt["source_save_flag"] is False
    assert receipt["source_resident_before_open"] is resident
    assert receipt["source_sha256"] == hashlib.sha256(case.source_bytes).hexdigest()
    # The raw observation is not a catalogue comparison or a material verdict.
    assert {key for key in receipt if key.startswith("source_material_")} == {
        "source_material_member", "source_material_raw", "source_material_return_type",
    }
    _assert_closed_unchanged(case)


@pytest.mark.parametrize("raw", (None, "", " \t ", 91, False, 1.5, ["DB", "Alloy", "91"]),
                         ids=("null", "empty", "whitespace", "integer", "boolean", "float", "list"))
def test_saved_material_null_empty_or_nonstring_is_retained_but_refused(saved_washer, raw):
    case = saved_washer
    case.model.MaterialIdName = raw
    case.invalidate()
    with pytest.raises(RuntimeError, match="native material readback") as caught:
        case.proof.saved_check(case.adapter, case.path)
    receipt = _exception_receipt(caught.value)
    assert receipt["source_material_member"] == "IPartDoc.MaterialIdName"
    assert receipt["source_material_raw"] == raw
    assert type(receipt["source_material_raw"]) is type(raw)
    assert receipt["source_material_return_type"] == f"{type(raw).__module__}.{type(raw).__qualname__}"
    assert "source_material_read_error" not in receipt
    assert receipt["source_active_configuration"] == "OfflineActiveSourceConfig"
    assert receipt["source_sha256"] == hashlib.sha256(case.source_bytes).hexdigest()
    assert not case.messages
    _assert_closed_unchanged(case)


def test_saved_material_getter_exception_is_not_null_or_an_input_echo(saved_washer):
    case = saved_washer
    failure = RuntimeError("native MaterialIdName getter material-read-sentinel")
    case.model._read_errors = {"MaterialIdName": failure}
    case.invalidate()
    with pytest.raises(RuntimeError) as caught:
        case.proof.saved_check(case.adapter, case.path)
    assert caught.value is failure
    receipt = _exception_receipt(caught.value)
    assert receipt["source_material_member"] == "IPartDoc.MaterialIdName"
    assert receipt["source_material_read_error"] == f"RuntimeError: {failure}"
    assert "source_material_raw" not in receipt
    assert "source_material_return_type" not in receipt
    assert receipt["source_sha256"] == hashlib.sha256(case.source_bytes).hexdigest()
    assert receipt["source_active_configuration"] == "OfflineActiveSourceConfig"
    assert not case.messages
    _assert_closed_unchanged(case)


@pytest.mark.parametrize("member", ("ConfigurationManager", "ActiveConfiguration", "Name"))
def test_saved_material_configuration_getter_error_is_distinct_and_preserves_exception(
    saved_washer, member,
):
    case = saved_washer
    failure = RuntimeError(f"native {member} configuration-read-sentinel")

    class FailedConfigurationMember:
        def __getattribute__(self, name):
            if name == member:
                raise failure
            raise AssertionError(f"unexpected configuration API {name}")

    if member == "ConfigurationManager":
        case.model._read_errors = {member: failure}
    elif member == "ActiveConfiguration":
        case.model.ConfigurationManager = FailedConfigurationMember()
    else:
        case.model.ConfigurationManager.ActiveConfiguration = FailedConfigurationMember()
    case.invalidate()
    with pytest.raises(RuntimeError) as caught:
        case.proof.saved_check(case.adapter, case.path)
    assert caught.value is failure
    receipt = _exception_receipt(caught.value)
    assert receipt["source_active_configuration"] == {"read_error": f"RuntimeError: {failure}"}
    assert receipt["source_sha256"] == hashlib.sha256(case.source_bytes).hexdigest()
    assert "source_material_raw" not in receipt
    assert "source_material_read_error" not in receipt
    assert not case.messages
    _assert_closed_unchanged(case)


@pytest.mark.parametrize("name", (None, "", " \t ", 7))
def test_saved_material_requires_actual_nonempty_active_configuration_name(saved_washer, name):
    case = saved_washer
    case.model.ConfigurationManager.ActiveConfiguration.Name = name
    case.invalidate()
    with pytest.raises(RuntimeError, match="active configuration name") as caught:
        case.proof.saved_check(case.adapter, case.path)
    receipt = _exception_receipt(caught.value)
    assert receipt["source_active_configuration"] == name
    assert type(receipt["source_active_configuration"]) is type(name)
    assert "source_material_raw" not in receipt
    assert "source_material_read_error" not in receipt
    _assert_closed_unchanged(case)


def test_saved_material_source_hash_error_is_distinct_and_preserves_exception(
    saved_washer, monkeypatch,
):
    case = saved_washer
    failure = OSError("native source file read source-hash-sentinel")
    original_open = Path.open

    def fail_source_read(path, *args, **kwargs):
        if path == case.source_path:
            raise failure
        return original_open(path, *args, **kwargs)

    case.invalidate()
    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", fail_source_read)
        with pytest.raises(OSError) as caught:
            case.proof.saved_check(case.adapter, case.path)
    assert caught.value is failure
    receipt = _exception_receipt(caught.value)
    assert receipt["source_sha256"] == {"read_error": f"OSError: {failure}"}
    assert receipt["source_path"] == str(case.source_path)
    assert "source_material_raw" not in receipt
    assert "source_material_read_error" not in receipt
    assert not case.messages
    _assert_closed_unchanged(case)


@pytest.mark.parametrize("member, field", (
    ("GetPathName", "source_path"), ("GetType", "source_type"),
    ("IsOpenedReadOnly", "source_read_only"),
))
def test_saved_material_source_checkpoint_errors_keep_the_actual_failed_field(
    saved_washer, member, field,
):
    case = saved_washer
    failure = RuntimeError(f"native {member} source-checkpoint-sentinel")
    case.model._read_errors = {member: failure}
    case.invalidate()
    with pytest.raises(RuntimeError) as caught:
        case.proof.saved_check(case.adapter, case.path)
    assert caught.value is failure
    receipt = _exception_receipt(caught.value)
    assert receipt[field] == {"read_error": f"RuntimeError: {failure}"}
    assert "source_material_raw" not in receipt
    assert "source_material_read_error" not in receipt
    assert not case.messages
    _assert_closed_unchanged(case)
