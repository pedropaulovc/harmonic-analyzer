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


def _nut_carrier(monkeypatch, *, defect=None):
    import _supplier_nut_drawing as nuts
    import _supplier_screw_dimensions as screws

    monkeypatch.setattr(nuts, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(screws, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(screws, "_bind", lambda value, _interface: value)
    source_points = tuple(
        SimpleNamespace(X=x, Y=0.0, Z=0.0) for x in (-0.003175, 0.003175)
    )
    # Same coordinates, deliberately different native identity namespaces.
    view_points = tuple(SimpleNamespace(**vars(point)) for point in source_points)
    foreign_point = SimpleNamespace(**vars(view_points[0]))
    attachments = list(view_points)
    if defect == "source_geometry":
        source_points[0].Y = 0.001
    elif defect == "raw_source_attachment":
        attachments = list(source_points)
    elif defect == "foreign_attachment":
        attachments[0] = foreign_point
    elif defect == "duplicate_attachment":
        attachments[1] = attachments[0]
    elif defect == "extra_attachment":
        attachments.append(foreign_point)
    elif defect == "duplicate_mapping":
        view_points = (view_points[0], view_points[0])

    segment = SimpleNamespace(
        GetType=lambda: 0, ConstructionGeometry=True,
        GetStartPoint2=lambda: source_points[0], GetEndPoint2=lambda: source_points[1],
    )
    sketch = SimpleNamespace(
        GetSketchSegments=lambda: (segment,), GetSketchPoints2=lambda: source_points,
    )
    feature = SimpleNamespace(GetSpecificFeature2=lambda: sketch)
    owner = object() if defect == "source_owner" else feature
    native = SimpleNamespace(
        FullName="ThreadNominalMajor@SupplierReference@part",
        GetFeatureOwner=lambda: owner, Tolerance=SimpleNamespace(Type=0),
    )
    source_native = SimpleNamespace(FullName=native.FullName)
    source_display = SimpleNamespace(Type2=2)
    monkeypatch.setattr(nuts, "_named_dimensions", lambda *_args, **_kwargs: {
        "ThreadNominalMajor": (source_display, source_native),
    })
    model = SimpleNamespace(FeatureByName=lambda _name: feature)

    def corresponding(point):
        for index, source_point in enumerate(source_points):
            if point is source_point:
                return None if defect == "missing_mapping" else view_points[index]
        raise AssertionError("mapping input is not an actual source endpoint")

    view = SimpleNamespace(ReferencedDocument=model, GetCorresponding=corresponding)
    annotation = SimpleNamespace(
        GetAttachedEntities3=lambda: tuple(attachments),
        GetAttachedEntityTypes=lambda: (11,) * len(attachments),
    )
    display = SimpleNamespace(
        Type2=2, GetDimension2=lambda _index: native, GetAnnotation=lambda: annotation,
    )
    adapter = SimpleNamespace(swApp=SimpleNamespace(IsSame=lambda left, right: int(left is right)))
    return nuts, adapter, view, display


def test_nut_carrier_accepts_exact_view_correspondence_not_raw_part_identity(monkeypatch):
    nuts, adapter, view, display = _nut_carrier(monkeypatch)
    proof = nuts._assert_nominal_carrier(adapter, view, display, 6.35)
    assert proof["proven"] is True
    source, = proof["sources"]
    assert source["inventory_complete"] is True
    assert source["source_member_count"] == source["mapped_member_count"] == 2
    assert source["mapping_complete"] is True
    assert [(member["self"], member["forward_self"]) for member in source["members"]] == [
        (1, 1), (1, 1),
    ]
    assert source["distinctness"] == [
        {"left_index": 0, "right_index": 1, "source_is_same": 0, "forward_is_same": 0},
    ]
    assert [attachment["view_source_entity_is_same"] for attachment in proof["attachments"]] == [
        [1, 0], [0, 1],
    ]


@pytest.mark.parametrize("defect,error", [
    ("source_geometry", "chord differs from its exact source"),
    ("source_owner", "dimension lost its native source owner"),
    ("raw_source_attachment", "attachment is not its view-mapped source endpoint"),
    ("foreign_attachment", "attachment is not its view-mapped source endpoint"),
    ("duplicate_attachment", "attachment is not its view-mapped source endpoint"),
    ("extra_attachment", "carrier requires both endpoint attachments"),
    ("duplicate_mapping", "attachment is not its view-mapped source endpoint"),
    ("missing_mapping", "attachment is not its view-mapped source endpoint"),
])
def test_nut_carrier_refuses_wrong_geometry_owner_or_view_endpoint(monkeypatch, defect, error):
    import json

    nuts, adapter, view, display = _nut_carrier(monkeypatch, defect=defect)
    with pytest.raises(RuntimeError, match=error) as refused:
        nuts._assert_nominal_carrier(adapter, view, display, 6.35)
    if defect in {"source_geometry", "source_owner", "extra_attachment"}:
        return
    proof = json.loads(str(refused.value).split(": ", 1)[1])
    assert proof["proven"] is False
    source, = proof["sources"]
    assert source["inventory_complete"] is True
    assert source["source_member_count"] == 2
    assert [member["native"] for member in source["members"]] == [
        {"present": True}, {"present": True},
    ]
    assert [member["forward"] for member in source["members"]] == [
        {"present": defect != "missing_mapping"},
        {"present": defect != "missing_mapping"},
    ]
    assert [member["self"] for member in source["members"]] == [1, 1]
    assert [member["forward_self"] for member in source["members"]] == (
        [None, None] if defect == "missing_mapping" else [1, 1]
    )
    assert source["mapped_member_count"] == (0 if defect == "missing_mapping" else 2)
    assert source["mapping_complete"] is (defect not in {"duplicate_mapping", "missing_mapping"})
    assert source["distinctness"] == [{
        "left_index": 0, "right_index": 1, "source_is_same": 0,
        "forward_is_same": (
            None if defect == "missing_mapping" else int(defect == "duplicate_mapping")
        ),
    }]
    expected_comparisons = {
        "raw_source_attachment": [[0, 0], [0, 0]],
        "foreign_attachment": [[0, 0], [0, 1]],
        "duplicate_attachment": [[1, 0], [1, 0]],
        "duplicate_mapping": [[1, 1], [0, 0]],
        "missing_mapping": [[None, None], [None, None]],
    }
    assert [attachment["self"] for attachment in proof["attachments"]] == [1, 1]
    assert [attachment["view_source_entity_is_same"] for attachment in proof["attachments"]] == (
        expected_comparisons[defect]
    )
    if defect == "duplicate_attachment":
        assert all(attachment["duplicate_mapped_member"] for attachment in proof["attachments"])


@pytest.mark.parametrize("field,bad", [
    ("use_document_units", True), ("units", 0), ("fraction_base", 2),
    ("primary_precision", 1), ("show_parentheses", True), ("override", True),
    ("show_native_value", False), ("prefix", "("), ("suffix", ")"),
    ("below_callout", "WRONG"),
])
def test_pin_presentation_refusal_names_first_actual_field_without_reading_later(
    monkeypatch, field, bad,
):
    import _supplier_pin_model as pins

    source = SimpleNamespace(
        sku="supplier-pin", units="in", diameter_mm=2.38125, diameter_precision=3,
        diameter_band=(-0.01, 0.01), diameter_uses_limits=False,
        diameter_deviations_mm=(-0.01, 0.01),
    )
    native = SimpleNamespace(SystemValue=source.diameter_mm / 1000.0)
    fields = {
        "use_document_units": False, "units": 3, "fraction_base": 1,
        "primary_precision": 3, "show_parentheses": False, "override": False,
        "show_native_value": True, "prefix": "(<MOD-DIAM>", "suffix": " in)",
        "below_callout": "",
    }
    getters = {
        "GetUseDocUnits": "use_document_units", "GetUnits": "units",
        "GetFractionBase": "fraction_base", "GetPrimaryPrecision2": "primary_precision",
        "GetOverride": "override",
    }
    properties = {
        "ShowParenthesis": "show_parentheses", "ShowDimensionValue": "show_native_value",
    }
    order = tuple(fields)

    def read(name):
        if order.index(name) > order.index(field):
            raise AssertionError("a later native reader masked the original refusal")
        return bad if name == field else fields[name]

    class Display:
        Type2 = 6

        def GetDimension2(self, _index):
            return native

        def GetText(self, index):
            return read({1: "prefix", 2: "suffix", 4: "below_callout"}[index])

        def __getattr__(self, name):
            if name in getters:
                return lambda: read(getters[name])
            if name in properties:
                return read(properties[name])
            raise AttributeError(name)

    feature = object()
    model = SimpleNamespace(FeatureByName=lambda _name: feature)
    monkeypatch.setattr(pins, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(pins, "_named_dimensions", lambda *_args, **_kwargs: {
        pins.DIAMETER_DIMENSION: (None, native),
    })
    with pytest.raises(RuntimeError, match=rf"native source value/presentation changed \({field}:"):
        pins.assert_supplier_pin_model_reference(
            None, model, Display(), pins.DIAMETER_FEATURE, source, view=None,
        )
