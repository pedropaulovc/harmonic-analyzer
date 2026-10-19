"""Offline geometry and native rejection contracts for 97431A260 source refs."""

from __future__ import annotations

import asyncio
from collections import Counter
from types import SimpleNamespace

import pytest

import vn_transgear_retaining_ring_spec as ring
import vn_transgear_retaining_ring_supplier_refs as refs
import vn_transgear_retaining_ring_application_drawing as drawing


def test_application_profile_geometrically_carries_all_supplier_for_sizes() -> None:
    points = refs.application_profile()
    assert len(points) == 12
    assert all(a[0] == b[0] or a[1] == b[1] for a, b in zip(points, points[1:] + points[:1], strict=True))
    assert points[0][1] - points[10][1] == pytest.approx(5.0 / 32.0 * 25.4)
    assert points[2][1] - points[8][1] == pytest.approx(0.116 * 25.4)
    assert points[3][0] - points[1][0] == pytest.approx(0.029 * 25.4)
    assert points[0][1] - points[10][1] != pytest.approx(0.156 * 25.4, abs=1e-6)
    assert min(u for u, _ in points) > ring.OD / 2.0


def test_source_thickness_edge_rejects_groove_slant_and_shifted_faces(monkeypatch) -> None:
    monkeypatch.setattr(refs, "_early_bound", lambda obj, _: obj)

    class Edge:
        def __init__(self, a, b):
            self.a, self.b = a, b

        def GetCurve(self):
            return SimpleNamespace(IsLine=lambda: True)

        def GetStartVertex(self):
            return SimpleNamespace(GetPoint=lambda: tuple(value / 1000.0 for value in self.a))

        def GetEndVertex(self):
            return SimpleNamespace(GetPoint=lambda: tuple(value / 1000.0 for value in self.b))

    actual = Edge((0.0, 3.0, ring.THICKNESS), (0.0, 3.0, 0.0))
    groove = Edge((0.0, 3.0, 0.0), (0.0, 3.0, ring.GROOVE_WIDTH))
    slant = Edge((0.0, 3.0, 0.0), (0.1, 3.0, ring.THICKNESS))
    shifted = Edge((0.0, 3.0, 1.0), (0.0, 3.0, 1.0 + ring.THICKNESS))
    body = SimpleNamespace(GetEdges=lambda: (groove, slant, shifted, actual))
    model = SimpleNamespace(GetBodies2=lambda *_: (body,))
    assert refs._thickness_model_edge(model) is actual
    body.GetEdges = lambda: (groove, slant, shifted)
    with pytest.raises(RuntimeError, match="actual ring thickness"):
        refs._thickness_model_edge(model)


class Native:
    DrivenState = 0
    Name = "D1"

    def __init__(self, value_mm):
        self.value_mm = value_mm

    @property
    def SystemValue(self):
        return self.value_mm / 1000.0  # no setter: native refs never override a value


class Display:
    MarkedForDrawing = False

    def __init__(self, native, kind):
        self.native, self.Type2, self.tol_places = native, kind, None

    def GetDimension2(self, _index):
        return self.native

    def SetPrecision3(self, _primary, _dual, primary_tol, _dual_tol) -> int:
        self.tol_places = primary_tol
        return 0

    def GetPrimaryTolPrecision2(self):
        return self.tol_places


@pytest.mark.parametrize("value_mm,accepted", [(5.0 / 32.0 * 25.4, True), (0.156 * 25.4, False)])
def test_gauge_shaft_native_value_rejects_rounded_supplier_ink(monkeypatch, value_mm, accepted) -> None:
    monkeypatch.setattr(refs, "_early_bound", lambda obj, _: obj)
    display = Display(Native(value_mm), 12)
    if accepted:
        refs._driven(display, "ApplicationShaftOD", ring.SHAFT_DIA)
    else:
        with pytest.raises(RuntimeError, match="exact driven application gauge"):
            refs._driven(display, "ApplicationShaftOD", ring.SHAFT_DIA)


def test_application_gauge_dimensions_measure_the_authored_section_flanks(monkeypatch) -> None:
    monkeypatch.setattr(refs, "_early_bound", lambda obj, _: obj)
    selected, segments, displays = [], [], []
    feature = object()
    preferences = {10: True, 101: False, 102: False}
    monkeypatch.setattr(refs, "constant", {
        "swSketchOverdefiningDimsPromptToSetState": 101,
        "swSketchOverdefiningDimsSetDrivenByDefault": 102,
    }.__getitem__)

    class Model:
        def ClearSelection2(self, _all):
            pass

        def FeatureByName(self, _name):
            return feature

        def AddVerticalDimension2(self, *_position):
            a, b = selected
            display = Display(Native(abs(segments[a][0][1] - segments[b][0][1])), 12)
            displays.append(display)
            return display

        def AddHorizontalDimension2(self, *_position):
            a, b = selected
            display = Display(Native(abs(segments[a][0][0] - segments[b][0][0])), 11)
            displays.append(display)
            return display

    class Adapter:
        currentModel = Model()
        swApp = SimpleNamespace(
            SetUserPreferenceToggle=lambda key, value: preferences.update({key: value}),
            GetUserPreferenceToggle=lambda key: preferences[key],
        )

        @staticmethod
        def _attempt(fn, *, default=None):
            return fn()

        async def create_sketch(self, _plane):
            return SimpleNamespace(is_success=True, data=None)

        async def exit_sketch(self):
            return SimpleNamespace(is_success=True, data=None)

    async def add_chain(_adapter, points, *, close):
        starts = points if close else points[:-1]
        ends = points[1:] + points[:1] if close else points[1:]
        segments[:] = list(zip(starts, ends, strict=True))
        return list(range(len(segments)))

    async def constrain(*_args, **_kwargs):
        pass

    def select(_adapter, _lines, indices):
        selected[:] = indices

    def named(_adapter, _feature_name, name):
        return next((display, display.native) for display in displays if display.native.Name == name)

    monkeypatch.setattr(refs, "add_line_chain", add_chain)
    monkeypatch.setattr(refs, "define_rectilinear_chain", constrain)
    monkeypatch.setattr(refs, "ensure_fully_defined", constrain)
    monkeypatch.setattr(refs, "_select_lines", select)
    monkeypatch.setattr(refs, "name_last_feature", lambda *_: None)
    monkeypatch.setattr(refs, "_feature_display_dimensions", lambda _: displays)
    monkeypatch.setattr(refs, "_named_dimension", named)
    monkeypatch.setattr(refs, "set_dimension_bilateral_tolerance", lambda *_: None)
    monkeypatch.setattr(refs, "supplier_reference_dimension", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(refs, "blank_reference_sketches", lambda *_: None)
    asyncio.run(refs.author_application_gauges(Adapter()))
    assert [display.native.SystemValue * 1000.0 for display in displays] == pytest.approx([
        5.0 / 32.0 * 25.4, 0.116 * 25.4, 0.029 * 25.4,
    ])
    assert set(Counter(point for segment in segments for point in segment).values()) == {2}


def test_application_settled_guard_rejects_attachment_tolerance_and_view_drift(monkeypatch) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _: obj)
    owner_sketch = object()
    feature = SimpleNamespace(Visible=1, GetSpecificFeature2=lambda: owner_sketch)
    gauge_box = (0.359, 0.114, 0.383, 0.146)
    monkeypatch.setattr(drawing, "_gauge_geometry", lambda *_: (feature, gauge_box))

    class View:
        Position = (0.315, 0.130)
        ScaleRatio = (8.0, 1.0)

        def ResetSketchVisibility(self):
            pass

        def GetOutline(self):
            return (0.311, 0.100, 0.319, 0.160)

    views = {name: View() for name in ("*Front", "*Top", "*Right", "*Isometric")}
    natives, annotations = [], []
    for name, value, upper in (
        ("ApplicationShaftOD", ring.SHAFT_DIA, None),
        ("ApplicationGrooveDiameter", ring.GROOVE_DIA, ring.GROOVE_DIA_BAND[0]),
        ("ApplicationGrooveWidth", ring.GROOVE_WIDTH, ring.GROOVE_WIDTH_BAND[0]),
    ):
        native = Native(value)
        native.DrivenState, native.Name = 1, name
        native.FullName = f"{name}@{ring.SUPPLIER_APPLICATION_SKETCH}@Ring"
        if upper is not None:
            native.Tolerance = SimpleNamespace(Type=2, GetMinValue=lambda: 0.0, GetMaxValue=lambda upper=upper: upper / 1000.0)
        display = Display(native, 12)
        display.tol_places = 3
        entity = SimpleNamespace(GetSketch=lambda: owner_sketch)
        annotation = SimpleNamespace(Visible=1, GetSpecificAnnotation=lambda display=display: display,
            GetAttachedEntities3=lambda entity=entity: (entity, entity), GetAttachedEntityTypes=lambda: (10, 10))
        display.GetAnnotation = lambda annotation=annotation: annotation
        natives.append(native)
        annotations.append(annotation)

    note = SimpleNamespace(GetText=lambda: "SUPPLIER APPLICATION GAUGES", GetExtent=lambda: (0.339, 0.165, 0.0, 0.389, 0.168, 0.0))
    monkeypatch.setattr(drawing, "curate_view_dimensions", lambda *_args, **_kwargs: annotations)
    monkeypatch.setattr(drawing, "supplier_reference_dimension", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(drawing, "assert_supplier_reference_dimension", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(drawing, "_literal_note", lambda *_: note)
    adapter = SimpleNamespace(swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)))
    settled = drawing.add_application_gauges(adapter, views)
    settled()
    annotations[0].GetAttachedEntityTypes = lambda: (1, 1)
    with pytest.raises(RuntimeError, match="purchased-body geometry"):
        settled()
    annotations[0].GetAttachedEntityTypes = lambda: (10, 10)
    natives[0].FullName = "ApplicationShaftOD@RingOutline@Ring"
    with pytest.raises(RuntimeError, match="separate visible source gauge"):
        settled()
    natives[0].FullName = f"ApplicationShaftOD@{ring.SUPPLIER_APPLICATION_SKETCH}@Ring"
    attachments = annotations[0].GetAttachedEntities3()
    attachments[0].GetSketch = lambda: object()
    with pytest.raises(RuntimeError, match="outside its source gauge sketch"):
        settled()
    attachments[0].GetSketch = lambda: owner_sketch
    views["*Front"].Position = (0.0, 0.0)
    with pytest.raises(RuntimeError, match="moved or rescaled"):
        settled()
    views["*Front"].Position = View.Position
    views["*Front"].GetOutline = lambda: (0.310, 0.100, 0.319, 0.160)
    with pytest.raises(RuntimeError, match="leaked outside its Right view"):
        settled()
    views["*Front"].GetOutline = lambda: (0.311, 0.100, 0.319, 0.160)
    natives[1].Tolerance.GetMaxValue = lambda: 0.0
    with pytest.raises(RuntimeError, match="native supplier gauge tolerance changed"):
        settled()
