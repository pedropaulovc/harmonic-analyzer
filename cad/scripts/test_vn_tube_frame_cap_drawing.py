"""Offline contracts for exact 9275K141 supplier reference measurements."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import draw_vn_tube_frame_cap as drawing
import vn_tube_frame_cap_spec as cap
import vn_tube_frame_cap_supplier_refs as refs


class Line:
    def __init__(self, start, end):
        self.start, self.end = start, end

    def GetType(self):
        return 0

    def GetStartPoint2(self):
        return SimpleNamespace(
            **dict(zip(("X", "Y", "Z"), (v / 1000.0 for v in self.start)))
        )

    def GetEndPoint2(self):
        return SimpleNamespace(
            **dict(zip(("X", "Y", "Z"), (v / 1000.0 for v in self.end)))
        )


class CircleEdge:
    def __init__(self, diameter, station):
        self.diameter, self.station = diameter, station

    def GetCurve(self):
        return SimpleNamespace(
            IsCircle=lambda: True,
            CircleParams=(
                0.0,
                self.station / 1000.0,
                0.0,
                0.0,
                1.0,
                0.0,
                self.diameter / 2000.0,
            ),
        )


def test_depth_carrier_finds_actual_inside_roof_not_external_top(monkeypatch) -> None:
    monkeypatch.setattr(refs, "_early_bound", lambda obj, _: obj)
    roof_ends = (
        (0.0, cap.INSIDE_HEIGHT, 0.0),
        (cap.TOP_FLAT_RADIUS, cap.INSIDE_HEIGHT, 0.0),
    )
    roof = Line(*reversed(roof_ends))
    outer = Line(
        (0.0, cap.TOTAL_HEIGHT, 0.0), (cap.TOP_FLAT_RADIUS, cap.TOTAL_HEIGHT, 0.0)
    )
    assert refs._line_at((outer, roof), *roof_ends, label="inside roof") is roof
    with pytest.raises(RuntimeError, match="one exact source line"):
        refs._line_at((outer,), *roof_ends, label="inside roof")
    with pytest.raises(RuntimeError, match="one exact source line"):
        refs._line_at((roof, roof), *roof_ends, label="inside roof")


def test_bore_carrier_excludes_mouth_flare_and_outer_wall(monkeypatch) -> None:
    monkeypatch.setattr(refs, "_early_bound", lambda obj, _: obj)
    bore = CircleEdge(cap.INNER_DIAMETER, cap.FLARE_HEIGHT)
    mouth = CircleEdge(cap.MOUTH_INNER_DIAMETER, 0.0)
    outer = CircleEdge(cap.OUTER_DIAMETER, cap.FLARE_HEIGHT)
    model = SimpleNamespace(
        GetBodies2=lambda *_: (SimpleNamespace(GetEdges=lambda: (mouth, outer, bore)),)
    )
    assert refs._straight_bore_rim(model) is bore
    model.GetBodies2 = lambda *_: (SimpleNamespace(GetEdges=lambda: (mouth, outer)),)
    with pytest.raises(RuntimeError, match="one straight bore rim"):
        refs._straight_bore_rim(model)


@pytest.mark.parametrize(
    "value_mm,kind,accepted",
    [
        (cap.INSIDE_HEIGHT, 2, True),
        (cap.INSIDE_HEIGHT, 12, True),
        (0.719 * 25.4, 2, False),
        (cap.TOTAL_HEIGHT, 2, False),
        (cap.INSIDE_HEIGHT, 3, False),
    ],
)
def test_model_carrier_rejects_rounded_exterior_and_nonlength_measurements(
    monkeypatch, value_mm, kind, accepted
) -> None:
    monkeypatch.setattr(refs, "_early_bound", lambda obj, _: obj)

    class Native:
        DrivenState = 0
        Name = "D1"

        @property
        def SystemValue(self):
            return value_mm / 1000.0  # no setter: a reference must not drive geometry

    native = Native()
    display = SimpleNamespace(
        Type2=kind, GetDimension2=lambda _: native, MarkedForDrawing=False
    )
    if accepted:
        refs._reference(
            display,
            name="SupplierInsideDepth",
            expected_mm=cap.INSIDE_HEIGHT,
            kinds=(2, 12),
        )
    else:
        with pytest.raises(
            RuntimeError, match="wrong dimension type|exact native source measurement"
        ):
            refs._reference(
                display,
                name="SupplierInsideDepth",
                expected_mm=cap.INSIDE_HEIGHT,
                kinds=(2, 12),
            )


def test_cap_settled_guard_rejects_dimension_census_and_source_owner_drift(
    monkeypatch,
) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _: obj)

    class View:
        def __init__(self, count):
            self.count = count

        def GetDisplayDimensionCount(self):
            return self.count

        def GetOutline(self):
            return (0.08, 0.11, 0.14, 0.16)

    front, top = View(1), View(1)
    views = {"*Front": front, "*Top": top, "*Right": View(0), "*Isometric": View(0)}
    natives, annotations = [], {}
    for view, name, feature in (
        (front, "SupplierInsideDepth", "CapSupplierDepth"),
        (top, "SupplierTubeOD", "CapSupplierBore"),
    ):
        native = SimpleNamespace(
            DrivenState=1, Name=name, FullName=f"{name}@{feature}@Cap"
        )
        annotation = SimpleNamespace(Visible=1)
        display = SimpleNamespace(
            GetDimension2=lambda _, native=native: native,
            GetAnnotation=lambda annotation=annotation: annotation,
        )
        annotation.GetSpecificAnnotation = lambda display=display: display
        natives.append(native)
        annotations[view] = [annotation]

    monkeypatch.setattr(
        drawing,
        "curate_view_dimensions",
        lambda _adapter, view, **_kwargs: annotations[view],
    )
    monkeypatch.setattr(
        drawing, "supplier_reference_dimension", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        drawing, "assert_supplier_reference_dimension", lambda *_args, **_kwargs: None
    )
    settled = drawing.supplier_dimensions(None, views)
    settled()
    front.count = 2
    with pytest.raises(RuntimeError, match="expected 1 native references, got 2"):
        settled()
    front.count = 1
    natives[0].FullName = "SupplierInsideDepth@CapRevolve@Cap"
    with pytest.raises(RuntimeError, match="settled .* source reference"):
        settled()


def test_reference_author_measures_converted_inside_roof_and_actual_bore_geometry(
    monkeypatch,
) -> None:
    monkeypatch.setattr(refs, "_early_bound", lambda obj, _: obj)
    roof = Line(
        (0.0, cap.INSIDE_HEIGHT, 0.0), (cap.TOP_FLAT_RADIUS, cap.INSIDE_HEIGHT, 0.0)
    )
    mouth = Line(
        (cap.MOUTH_INNER_DIAMETER / 2.0, 0.0, 0.0),
        (cap.MAX_OUTER_DIAMETER / 2.0, 0.0, 0.0),
    )
    exterior_roof = Line(
        (0.0, cap.TOTAL_HEIGHT, 0.0), (cap.TOP_FLAT_RADIUS, cap.TOTAL_HEIGHT, 0.0)
    )
    bore = CircleEdge(cap.INNER_DIAMETER, cap.FLARE_HEIGHT)
    mouth_rim = CircleEdge(cap.MOUTH_INNER_DIAMETER, 0.0)
    selected, dimensions = [], []
    preferences = {10: True, 101: False, 102: False}
    monkeypatch.setattr(
        refs,
        "constant",
        {
            "swSketchOverdefiningDimsPromptToSetState": 101,
            "swSketchOverdefiningDimsSetDrivenByDefault": 102,
        }.__getitem__,
    )

    class Native:
        DrivenState = 0
        Name = "D1"

        def __init__(self, value_mm):
            self.value_mm = value_mm

        @property
        def SystemValue(self):
            return self.value_mm / 1000.0

    class CircleSegment:
        def __init__(self, source_edge):
            self.source = source_edge

        def GetType(self):
            return 1

    class Manager:
        plane = None
        segments = ()

        def SketchUseEdge3(self, chain, inner_loops):
            self.segments = tuple(
                Line(entity.start, entity.end)
                if isinstance(entity, Line)
                else CircleSegment(entity)
                for entity in selected
            )
            return True

    manager = Manager()

    def display(value_mm, kind):
        native = Native(value_mm)
        dimensions.append(native)
        return SimpleNamespace(
            Type2=kind, GetDimension2=lambda _: native, MarkedForDrawing=False
        )

    class Model:
        def FeatureByName(self, name):
            return SimpleNamespace(
                GetSpecificFeature2=lambda: SimpleNamespace(
                    GetSketchSegments=lambda: (exterior_roof, mouth, roof),
                )
            )

        def GetBodies2(self, *_):
            return (SimpleNamespace(GetEdges=lambda: (mouth_rim, bore)),)

        def ClearSelection2(self, _all):
            selected.clear()

        def GetActiveSketch2(self):
            return SimpleNamespace(GetSketchSegments=lambda: manager.segments)

        def AddVerticalDimension2(self, *_position):
            return display(abs(selected[0].start[1] - selected[1].start[1]), 12)

        def AddDiameterDimension2(self, *_position):
            return display(selected[0].source.diameter, 6)

    model = Model()

    class Adapter:
        currentModel = model
        currentSketchManager = manager
        swApp = SimpleNamespace(
            SetUserPreferenceToggle=lambda key, value: preferences.update({key: value}),
            GetUserPreferenceToggle=lambda key: preferences[key],
        )

        @staticmethod
        def _attempt(fn, *, default=None):
            return fn()

        async def create_sketch(self, plane):
            manager.plane, manager.segments = plane, ()
            return SimpleNamespace(is_success=True, data=None)

        async def exit_sketch(self):
            return SimpleNamespace(is_success=True, data=None)

    def select(_model, entities, *, sketch):
        selected[:] = entities

    monkeypatch.setattr(refs, "_select", select)
    monkeypatch.setattr(refs, "name_last_feature", lambda *_: None)
    monkeypatch.setattr(refs, "blank_reference_sketches", lambda *_: None)
    asyncio.run(refs.author_supplier_references(Adapter()))
    assert [native.SystemValue * 1000.0 for native in dimensions] == pytest.approx(
        [
            18.25625,
            25.4,
        ]
    )
