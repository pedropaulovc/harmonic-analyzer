"""Native-I/O doubles for supplier witness constraints; never start a COM seat."""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest


def _result(data=None, error=None):
    return SimpleNamespace(is_success=error is None, data=data, error=error)


class _Line:
    def __init__(self, start, end, statuses, sketch):
        self.points = tuple(
            SimpleNamespace(X=x / 1000.0, Y=y / 1000.0, Z=0.0, Status=status)
            for (x, y), status in zip((start, end), statuses, strict=True)
        )
        self.sketch = sketch
        self.ConstructionGeometry = False

    def GetStartPoint2(self):
        return self.points[0]

    def GetEndPoint2(self):
        return self.points[1]

    def GetSketch(self):
        return self.sketch


class _Angle:
    def __init__(self, value, *, refuses_driving=False):
        self.SystemValue = value
        self.refuses_driving = refuses_driving
        self._driven = 1

    @property
    def DrivenState(self):
        return self._driven

    @DrivenState.setter
    def DrivenState(self, value):
        if not self.refuses_driving:
            self._driven = value


class _WitnessAdapter:
    def __init__(self, *, statuses=(2, 2), defect=None):
        self.statuses = statuses
        self.defect = defect
        self._sketch_entities = {}
        self.selected = []
        self.angle = None
        self.text_point = None
        self.currentSketchManager = SimpleNamespace(AddToDB=False)
        self.sketch = SimpleNamespace(
            ModelToSketchTransform=SimpleNamespace(Inverse=lambda: self.to_model)
        )
        self.currentModel = SimpleNamespace(
            ClearSelection2=lambda _all: self.selected.clear(),
            Extension=SimpleNamespace(AddSpecificDimension=self.add_angle),
        )
        self.swApp = SimpleNamespace(
            GetMathUtility=lambda: SimpleNamespace(CreatePoint=self.math_point)
        )

    @staticmethod
    def _attempt(operation, default=None):
        try:
            return operation()
        except Exception:
            return default

    @staticmethod
    def to_model(point):
        x, y, z = point
        return (x + 0.01, z + 0.02, -y + 0.03)

    @staticmethod
    def math_point(coordinates):
        return SimpleNamespace(
            MultiplyTransform=lambda transform: SimpleNamespace(
                ArrayData=transform(coordinates)
            )
        )

    async def add_line(self, x0, y0, x1, y1):
        name = f"Line{len(self._sketch_entities) + 1}"
        if self.defect == "translated":
            x0, x1 = x0 + 0.1, x1 + 0.1
        self._sketch_entities[name] = _Line(
            (x0, y0), (x1, y1), self.statuses, self.sketch
        )
        return _result(name)

    def point(self, reference):
        name, endpoint = reference.split(".")
        return self._sketch_entities[name].points[endpoint == "end"]

    async def add_sketch_constraint(self, first, second, kind):
        if second == "origin" and kind == "coincident":
            point = self.point(first)
            if point.Status == 3:
                return _result(error="redundant anchor would over-constrain the witness")
            line = self._sketch_entities[first.split(".")[0]]
            for endpoint in line.points:
                endpoint.Status = 3
        elif second is not None and kind == "coincident":
            self.point(first).Status = self.point(second).Status
        return _result("relation")

    async def add_sketch_dimension(self, first, second, kind, value):
        # The old generic one-ray/vertex route does not create a control between
        # the two rays. The positive test must observe a real native angle.
        if kind == "angular":
            return _result("one-ray annotation")
        if kind in ("distance", "horizontal_distance", "vertical_distance") and second != "origin":
            first_point, second_point = self.point(first), self.point(second)
            if first_point.Status == 3 and second_point.Status == 2:
                second_point.Status = 3
            elif second_point.Status == 3 and first_point.Status == 2:
                first_point.Status = 3
        return _result("driving distance")

    def add_angle(self, x, y, z, kind, _error):
        if self.defect == "constructor-refused":
            return None, 1
        if len(self.selected) != 2 or kind != 3:
            return None, 1
        directions = [
            tuple(getattr(line.points[1], axis) - getattr(line.points[0], axis)
                  for axis in ("X", "Y", "Z"))
            for line in (self._sketch_entities[name] for name in self.selected)
        ]
        dot = sum(a * b for a, b in zip(*directions, strict=True))
        lengths = math.prod(math.sqrt(sum(v * v for v in row)) for row in directions)
        value = math.acos(dot / lengths)
        if self.defect == "wrong-angle":
            value = math.radians(42.0)
        self.angle = _Angle(value, refuses_driving=self.defect == "driven-only")
        self.text_point = (x, y, z)
        native_type = 2 if self.defect == "wrong-type" else 3
        return SimpleNamespace(Type2=native_type, GetDimension2=lambda _index: self.angle), 0


@pytest.fixture
def witnesses(monkeypatch):
    import _supplier_screw_reference as source
    from solidworks_mcp.adapters import com_variant
    from solidworks_mcp.adapters.solidworks import sketch

    monkeypatch.setattr(source, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(com_variant, "double_array", lambda values: values)
    monkeypatch.setattr(
        sketch, "_select_sketch_entities",
        lambda adapter, names, _mark: adapter.selected.extend(names),
    )
    return source


@pytest.mark.asyncio
@pytest.mark.parametrize("statuses", [(3, 3), (2, 2), (3, 2)])
async def test_linear_witness_retains_exact_frame_without_redundant_anchor(witnesses, statuses):
    adapter = _WitnessAdapter(statuses=statuses)
    await witnesses._linear(adapter, witnesses.SketchDims(), "SupplierWidth", 6.35,
                            "horizontal", (0.0, 0.0))
    line = adapter._sketch_entities["Line1"]
    assert [(point.X, point.Y, point.Z) for point in line.points] == [
        (0.0, 0.0, 0.0), (0.00635, 0.0, 0.0)
    ]
    assert tuple(point.Status for point in line.points) == (3, 3)
    assert line.ConstructionGeometry is True
    assert adapter.currentSketchManager.AddToDB is False


@pytest.mark.asyncio
@pytest.mark.parametrize("statuses,defect,error", [
    ((None, 3), None, "status is unreadable"),
    ((3, 3), "translated", "final-frame coordinates"),
])
async def test_linear_witness_refuses_unknown_status_or_same_length_wrong_frame(
    witnesses, statuses, defect, error
):
    adapter = _WitnessAdapter(statuses=statuses, defect=defect)
    with pytest.raises(RuntimeError, match=error):
        await witnesses._linear(adapter, witnesses.SketchDims(), "SupplierWidth", 6.35,
                                "horizontal", (0.0, 0.0))


@pytest.mark.asyncio
async def test_supplier_angle_is_driving_between_actual_rays_in_the_owning_plane(witnesses):
    adapter = _WitnessAdapter()
    await witnesses._angle(adapter, witnesses.SketchDims(), "SupplierHeadAngle", 82.0, (2.0, -3.0))
    assert adapter.angle is not None
    assert math.degrees(adapter.angle.SystemValue) == pytest.approx(82.0)
    assert adapter.angle.DrivenState == 2
    expected = adapter.to_model((
        (2.0 + 0.5 * math.cos(math.radians(41.0))) / 1000.0,
        (-3.0 + 0.5 * math.sin(math.radians(41.0))) / 1000.0,
        0.0,
    ))
    assert adapter.text_point == pytest.approx(expected)
    assert adapter.selected == []
    assert adapter.currentSketchManager.AddToDB is False


@pytest.mark.asyncio
@pytest.mark.parametrize("defect,error", [
    ("constructor-refused", "AddSpecificDimension"),
    ("wrong-type", "not a native angular dimension"),
    ("wrong-angle", "not the specified"),
    ("driven-only", "not an exact driving control"),
])
async def test_supplier_angle_refuses_failed_or_non_driving_native_controls(witnesses, defect, error):
    adapter = _WitnessAdapter(defect=defect)
    with pytest.raises(RuntimeError, match=error):
        await witnesses._angle(adapter, witnesses.SketchDims(), "SupplierHeadAngle", 82.0, (0.0, 0.0))
    assert adapter.selected == []


def _refused_pin(monkeypatch, *, attachment_types=(1, 1), reader_interrupt=False, log_interrupt=False):
    import _supplier_pin_drawing as pins

    events = []
    monkeypatch.setattr(pins, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(pins, "model_points_in_view", lambda _adapter, _view, points, **_kw: [
        (0.1 + x, 0.1 + y) for x, y, _z in points
    ])
    annotation = SimpleNamespace(GetAttachedEntityTypes=lambda: attachment_types)

    def read_arc(index):
        if reader_interrupt and index == 1:
            raise SystemExit("diagnostic reader stopped")
        return 0

    native = SimpleNamespace(
        SetArcEndCondition=lambda _index, _condition: -4,
        GetArcEndCondition=read_arc, SystemValue=0.0047625,
    )
    display = SimpleNamespace(
        Type2=2, GetDimension2=lambda _index: native,
        GetAnnotation=lambda: annotation,
    )
    monkeypatch.setattr(pins, "add_edge_dimension", lambda *_args, **_kwargs: display)

    def log(_message, **fields):
        events.append(fields)
        if log_interrupt:
            raise KeyboardInterrupt("optional observer failed")

    monkeypatch.setattr(pins._telemetry, "info", log)
    circles = [SimpleNamespace(circle=(0.0, station, 0.0, 0.0, 1.0, 0.0, 1.0), edge=object())
               for station in (0.0, 4.7625)]
    view = SimpleNamespace(GetOutline=lambda: (0.09, 0.09, 0.11, 0.12))
    source = SimpleNamespace(sku="98381A433", length_mm=4.7625)
    with pytest.raises(RuntimeError, match="cannot center native end-rim endpoint 1"):
        pins._supplier_length(None, view, circles, source, axis=1, stations=(0.0, 4.7625))
    return events[0]


def test_pin_refusal_reports_actual_native_status_without_accepting_the_dimension(monkeypatch):
    fields = _refused_pin(monkeypatch)
    assert fields["setter_return"] == -4
    assert fields["arc_end_condition_1"] == 0
    assert fields["arc_end_condition_2"] == 0
    assert fields["display_dimension_type"] == 2
    assert fields["attached_entity_types"] == (1, 1)
    assert fields["native_value_m"] == 0.0047625


@pytest.mark.parametrize("attachment_types,state", [(None, "UNAVAILABLE_NULL"), ((), "OBSERVED")])
def test_pin_null_attachment_inventory_is_not_reported_as_measured_empty(monkeypatch, attachment_types, state):
    fields = _refused_pin(monkeypatch, attachment_types=attachment_types)
    assert fields["attached_entity_types"] == attachment_types
    assert fields["attached_entity_types_state"] == state


def test_pin_reader_interrupt_does_not_skip_independent_fields_or_replace_original_failure(monkeypatch):
    fields = _refused_pin(monkeypatch, reader_interrupt=True)
    assert fields["arc_end_condition_1_state"] == "UNAVAILABLE"
    assert fields["arc_end_condition_1_error_type"] == "SystemExit"
    assert fields["arc_end_condition_2_state"] == "OBSERVED"
    assert fields["attached_entity_types_state"] == "OBSERVED"


def test_pin_logging_interrupt_does_not_replace_original_failure(monkeypatch):
    _refused_pin(monkeypatch, log_interrupt=True)
