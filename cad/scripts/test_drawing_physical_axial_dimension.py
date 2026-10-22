"""Offline native-boundary fakes; the actual spatial and shared edge/value proofs run.

These invented dimensions/transforms deliberately are not native receipt fixtures.
Selection and factory calls below are isolated fakes, never live COM.  No setters
of dimension type/value, rebuilds, or saves are used by this test module.
"""

from __future__ import annotations

from collections import Counter
import math
from types import SimpleNamespace

import pytest

import _drawing_physical_axial_dimension as proof


_DEFAULT = object()


class _Native:
    def __init__(self, state):
        self.state = state

    def read(self, key, value=None):
        self.state.reads[key] += 1
        failure = self.state.failures.get(key)
        if failure is not None:
            raise failure
        delayed = self.state.fail_on.get(key)
        if delayed is not None and self.state.reads[key] == delayed[0]:
            raise delayed[1]
        return value


class _Edge(_Native):
    def __init__(self, state, index):
        super().__init__(state)
        self.index = index

    def GetClosestPointOn(self, x, y, z):
        self.state.operations.append(("closest", self, (x, y, z)))
        result = self.state.closest_overrides.get(
            self.index, (*self.state.points_m[self.index], 0.0, None)
        )
        return self.read(f"closest_point_{self.index}", result)

    def Select4(self, *_args):
        raise AssertionError("stock model edges must be selected through IView.SelectEntity")


class _View(_Native):
    @property
    def ScaleDecimal(self):
        return self.read("scale_decimal", self.state.scale)

    def SelectEntity(self, entity, append):
        index = 2 if append else 1
        self.state.operations.append(("select_entity", entity, append))
        result = self.read(f"select_edge_{index}", self.state.select_results[index - 1])
        if result is True:
            if not append:
                self.state.selection.clear()
            self.state.selection.append(entity)
        return result


class _SelectionManager(_Native):
    def GetSelectedObjectCount2(self, mark):
        assert mark == -1
        ordinal = self.state.reads["selection_count"] + 1
        value = self.state.count_overrides.get(ordinal, len(self.state.selection))
        return self.read("selection_count", value)

    def GetSelectedObjectType3(self, index, mark):
        assert index in (1, 2) and mark == -1
        return self.read(f"selection_kind_{index}", self.state.selected_kinds[index - 1])

    def GetSelectedObject6(self, index, mark):
        assert index in (1, 2) and mark == -1
        value = self.state.selected_overrides.get(index, self.state.selection[index - 1])
        return self.read(f"selected_object_{index}", value)

    def SetSelectionPoint2(self, index, mark, x, y, z):
        assert index in (1, 2) and mark == -1
        self.state.operations.append(("set_point", index, (x, y, z)))
        result = self.read(f"set_point_{index}", self.state.set_point_results[index - 1])
        if result is True:
            self.state.selection_points[index] = (x, y, z)
        if self.state.after_set_point is not None:
            self.state.after_set_point(index)
        return result

    def GetSelectionPoint2(self, index, mark):
        assert index in (1, 2) and mark == -1
        self.state.operations.append(("read_point", index))
        value = self.state.point_overrides.get(index, self.state.selection_points[index])
        return self.read(f"read_point_{index}", value)


class _Model(_Native):
    @property
    def SelectionManager(self):
        return self.read("selection_manager", self.state.manager)

    def ActivateView(self, name):
        self.state.operations.append(("activate", name))
        return self.read("activate_view", self.state.activate_result)

    def ClearSelection2(self, all_selections):
        assert all_selections is True
        self.state.operations.append(("clear",))
        self.read("clear_selection")
        self.state.selection.clear()
        self.state.selection_points.clear()

    def AddVerticalDimension2(self, x, y, z):
        self.state.operations.append(("create", (x, y, z)))
        self.state.created_selection = tuple(self.state.selection)
        self.state.created_points = dict(self.state.selection_points)
        display = self.state.display if self.state.creation_display is _DEFAULT else self.state.creation_display
        return self.read("create_dimension", display)


class _Application(_Native):
    def IsSame(self, left, right):
        if right is self.state.view:
            result = int(left is right) if self.state.owner_same is None else self.state.owner_same
            return self.read("owner_same", result)
        result = int(left is right) if self.state.edge_same is None else self.state.edge_same
        return self.read("edge_same", result)


class _Dimension(_Native):
    @property
    def SystemValue(self):
        return self.read("system_value", self.state.value_m)


class _Display(_Native):
    @property
    def Type2(self):
        return self.read("type2", self.state.type2)

    def GetAnnotation(self):
        return self.read("annotation", self.state.annotation)

    def GetDimension2(self, index):
        assert index == 0
        return self.read("native_dimension", self.state.dimension)


class _Annotation(_Native):
    @property
    def OwnerType(self):
        return self.read("owner_type", self.state.owner_type)

    @property
    def Owner(self):
        return self.read("owner", self.state.owner)

    def GetAttachedEntityCount3(self):
        return self.read("attached_count", self.state.attached_count)

    def GetAttachedEntities3(self):
        return self.read("attached_entities", self.state.attached)

    def GetAttachedEntityTypes(self):
        return self.read("attached_types", self.state.kinds)

    def IsDangling(self):
        return self.read("dangling", self.state.dangling)

    def GetDisplayData(self):
        return self.read("display_data", self.state.data)


class _DisplayData(_Native):
    def GetArrowHeadCount(self):
        return self.read("arrow_count", self.state.arrow_count)

    def GetArrowHeadAtIndex2(self, index):
        assert index in (0, 1), "only the exact two documented records may be read"
        return self.read(f"arrow_head_{index}", self.state.arrows[index])


class _Harness:
    def __init__(self, monkeypatch):
        self.reads = Counter()
        self.failures = {}
        self.fail_on = {}
        self.events = []
        self.expected_mm = 7.25
        self.points_m = ((-0.002, 0.0412, 0.003), (0.001, 0.04845, -0.002))
        self.entities = (_Edge(self, 0), _Edge(self, 1))
        self.type2 = 2
        self.attached_count = 2
        self.attached = self.entities
        self.kinds = (1, 1)
        self.dangling = False
        self.owner_type = 0
        self.owner_same = None
        self.edge_same = None
        self.value_m = self.expected_mm / 1000
        self.scale = 3.2
        # The transform and ScaleDecimal are separate native readbacks. Changing
        # only the latter must not silently move the fake projected geometry.
        self.transform_scale = 3.2
        self.offset = (0.13, 0.07)
        self.projected_override = _DEFAULT
        self.projections = []
        self.view = _View(self)
        self.owner = self.view
        self.application = _Application(self)
        self.operations = []
        self.closest_overrides = {}
        self.selection = []
        self.selection_points = {}
        self.count_overrides = {}
        self.selected_kinds = [1, 1]
        self.selected_overrides = {}
        self.point_overrides = {}
        self.select_results = [True, True]
        self.set_point_results = [True, True]
        self.after_set_point = None
        self.activate_result = True
        self.creation_display = _DEFAULT
        self.created_selection = None
        self.created_points = None
        self.manager = _SelectionManager(self)
        self.model = _Model(self)
        self.adapter = SimpleNamespace(swApp=self.application, currentModel=self.model)
        self.dimension = _Dimension(self)
        self.annotation = _Annotation(self)
        self.display = _Display(self)
        self.data = _DisplayData(self)
        self.arrow_count = 2
        ys = [self.offset[1] + point[1] * self.transform_scale for point in self.points_m]
        self.arrows = [
            [0.22, ys[0], 0.0, 0.0, -3.0, 0.0, 0.002, 0.001, 0.0, 0.0, 0.0, 1.0],
            [0.22, ys[1], 0.0, 0.0, 7.0, 0.0, 0.002, 0.001, 0.0, 0.0, 0.0, 1.0],
        ]
        monkeypatch.setattr(proof, "_early_bound", self.bind)
        monkeypatch.setattr(proof, "model_points_in_view", self.project)
        monkeypatch.setattr(proof._telemetry, "event", self.event)
        monkeypatch.setattr(proof, "view_name", lambda _adapter, _view: "InventedStockFront")

    def bind(self, value, interface):
        _Native(self).read(f"bind_{interface}")
        return value

    def project(self, adapter, view, points, *, label):
        assert adapter is self.adapter and view is self.view
        _Native(self).read("station_projection")
        self.projections.append((points, label))
        if self.projected_override is not _DEFAULT:
            return self.projected_override
        return [
            (self.offset[0] + x * self.transform_scale,
             self.offset[1] + y * self.transform_scale)
            for x, y, _z in points
        ]

    def event(self, name, **fields):
        self.events.append((name, fields))

    def prove(self, **changes):
        arguments = dict(
            entities=self.entities, points_m=self.points_m, expected_mm=self.expected_mm,
            label="InventedAxialDimension",
        )
        arguments.update(changes)
        return proof.assert_native_physical_axial_dimension(
            self.adapter, self.view, self.display, **arguments
        )

    def refuse(self, match, **changes):
        with pytest.raises(RuntimeError, match=match) as caught:
            self.prove(**changes)
        name, fields = self.events[-1]
        assert name == "drawing.physical_axial_dimension_native_refusal"
        assert fields["label"] == changes.get("label", "InventedAxialDimension")
        assert fields["phase"] == changes.get("phase", "settled")
        assert fields["failure_error_type"] == type(caught.value.__cause__).__name__
        assert fields["failure_error"] == str(caught.value.__cause__)[:500]
        return caught.value, fields

    def create(self, **changes):
        arguments = dict(
            entities=self.entities, points_m=self.points_m, expected_mm=self.expected_mm,
            text_xy=(0.22, 0.18), label="InventedStockLength",
        )
        arguments.update(changes)
        return proof.add_native_physical_axial_dimension(self.adapter, self.view, **arguments)

    def refuse_creation(self, match, **changes):
        with pytest.raises(RuntimeError, match=match) as caught:
            self.create(**changes)
        name, fields = self.events[-1]
        assert name == "drawing.physical_axial_dimension_native_refusal"
        assert fields["label"] == changes.get("label", "InventedStockLength")
        assert fields["phase"] == "creation"
        assert fields["failure_error_type"] == type(caught.value.__cause__).__name__
        assert fields["failure_error"] == str(caught.value.__cause__)[:500]
        assert self.selection == [] and self.selection_points == {}
        assert self.operations[-1] == ("clear",)
        return caught.value, fields


@pytest.fixture
def native(monkeypatch):
    return _Harness(monkeypatch)


@pytest.mark.parametrize("reorder", [False, True])
@pytest.mark.parametrize("negative_value", [False, True])
def test_exact_linear_native_vertical_geometry_runs_real_shared_proofs(native, reorder, negative_value):
    if reorder:
        native.attached = native.entities[::-1]
        native.arrows.reverse()
        native.projected_override = native.project(native.adapter, native.view, native.points_m, label="fixture")[::-1]
        native.projections.clear()
    if negative_value:
        native.value_m *= -1  # The unchanged shared guard measures magnitude.
    assert native.prove(label="InventedHeight") == pytest.approx(native.expected_mm)
    name, fields = native.events[-1]
    assert name == "drawing.physical_axial_dimension_native_proof"
    assert fields["label"] == "InventedHeight" and fields["phase"] == "settled"
    assert fields["type2"] == 2
    assert fields["measured_mm"] == pytest.approx(native.expected_mm)
    assert fields["points_m"] == native.points_m
    assert fields["scale_decimal"] == native.scale
    assert fields["span_m"] == pytest.approx(native.expected_mm / 1000 * native.scale)
    assert fields["projected_station_ys"] == tuple(sorted(arrow[1] for arrow in native.arrows))
    assert fields["arrow_heads"] == [tuple(arrow) for arrow in native.arrows]
    assert fields["arrow_tips"] == tuple(tuple(arrow[:3]) for arrow in native.arrows)
    assert fields["arrow_directions"] == (
        ((0.0, 1.0, 0.0), (0.0, -1.0, 0.0)) if reorder
        else ((0.0, -1.0, 0.0), (0.0, 1.0, 0.0))
    )
    assert native.projections == [(native.points_m, "InventedHeight")]
    # The real unchanged shared assertion re-reads attachments/dangling and the
    # native value. Neither it nor the public helper is replaced by a stub.
    assert native.reads["attached_entities"] == 2
    assert native.reads["attached_types"] == 2
    assert native.reads["dangling"] == 2
    assert native.reads["edge_same"] >= 2
    assert native.reads["system_value"] == 1
    assert native.reads["arrow_head_0"] == native.reads["arrow_head_1"] == 1


@pytest.mark.parametrize("dimension_type", [value for value in range(17) if value != 2])
def test_only_exact_type2_linear_is_accepted(native, dimension_type):
    native.type2 = dimension_type
    _error, fields = native.refuse("expected linear dimension Type2=2")
    assert fields["type2"] == dimension_type
    assert fields["owner_same"] == 1
    assert fields["attached_count"] == fields["attached_length"] == fields["kinds_length"] == 2
    assert fields["kinds"] == (1, 1) and fields["attached_nulls"] == (False, False)
    assert fields["dangling"] is False and fields["owner_null"] is False
    assert fields["owner_type"] == 0
    assert native.reads["type2"] == native.reads["owner_same"] == 1
    assert native.reads["display_data"] == native.reads["native_dimension"] == 0


@pytest.mark.parametrize("field", [
    "type2", "attached_count", "arrow_count", "owner_type", "owner_same",
])
@pytest.mark.parametrize("value", [None, "2", 2.0, 2.5, True, False, math.nan, math.inf])
def test_malformed_integer_getters_are_not_coerced_or_truncated(native, field, value):
    # None means identity-based native equality in this fixture, so explicitly
    # return None through the application's getter for that one malformed case.
    if field == "owner_same" and value is None:
        native.application.IsSame = lambda _left, _right: None
    else:
        setattr(native, field, value)
    native.refuse("must be a native integer")


@pytest.mark.parametrize("count", [-2, 0, 1, 3, 10000])
def test_attachment_count_must_be_exactly_two(native, count):
    native.attached_count = count
    native.refuse("expected two nonnull actual edge attachments")


@pytest.mark.parametrize("fault", [
    "null-array", "empty-array", "short-array", "long-array", "null-first", "null-second",
    "null-kinds", "empty-kinds", "short-kinds", "long-kinds", "silhouette", "vertex", "dangling",
])
def test_metadata_requires_matching_exact_edge_arrays_without_nulls(native, fault):
    if fault == "null-array":
        native.attached = None
    elif fault == "empty-array":
        native.attached = ()
    elif fault == "short-array":
        native.attached = native.entities[:1]
    elif fault == "long-array":
        native.attached = (*native.entities, object())
    elif fault == "null-first":
        native.attached = (None, native.entities[1])
    elif fault == "null-second":
        native.attached = (native.entities[0], None)
    elif fault == "null-kinds":
        native.kinds = None
    elif fault == "empty-kinds":
        native.kinds = ()
    elif fault == "short-kinds":
        native.kinds = (1,)
    elif fault == "long-kinds":
        native.kinds = (1, 1, 1)
    elif fault == "silhouette":
        native.kinds = (1, 46)
    elif fault == "vertex":
        native.kinds = (3, 1)
    else:
        native.dangling = True
    native.refuse("expected two nonnull actual edge attachments")


@pytest.mark.parametrize("value", [1.5, "1", None, True])
def test_malformed_attachment_kind_is_not_coerced(native, value):
    native.kinds = (1, value)
    error, fields = native.refuse("attachment type 1 must be a native integer")
    assert isinstance(error.__cause__, TypeError)
    assert fields["kinds_length"] == 2
    assert fields["kinds"][0] == 1
    if isinstance(value, str):
        assert isinstance(fields["kinds"][1], str)
        assert len(fields["kinds"][1]) <= 120
    else:
        assert fields["kinds"][1] == value
    assert native.reads["attached_types"] == 1
    assert native.reads["dangling"] == native.reads["owner"] == 0


@pytest.mark.parametrize("value", [None, 0, 1, "false"])
def test_missing_or_malformed_dangling_result_is_not_false_success(native, value):
    native.dangling = value
    native.refuse("IsDangling must return a native boolean")


@pytest.mark.parametrize("fault", ["null", "different", "sheet", "unknown-equality", "different-equality"])
def test_exact_view_owner_is_required(native, fault):
    if fault == "null":
        native.owner = None
    elif fault == "different":
        native.owner = object()
    elif fault == "sheet":
        native.owner_type = 1
    elif fault == "unknown-equality":
        native.owner_same = 2
    else:
        native.owner_same = 0
    native.refuse("expected exact front-view owner")


@pytest.mark.parametrize("fault", ["wrong-first", "wrong-second", "duplicate", "unknown-equality"])
def test_actual_shared_assertion_requires_unordered_exact_edge_bijection(native, fault):
    if fault == "wrong-first":
        native.attached = (object(), native.entities[1])
    elif fault == "wrong-second":
        native.attached = (native.entities[0], object())
    elif fault == "duplicate":
        native.attached = (native.entities[0], native.entities[0])
    else:
        native.edge_same = 2
    native.refuse("not the dimension between its named entities")
    assert native.reads["system_value"] == 0


@pytest.mark.parametrize("fault,match", [
    ("display", "native display dimension is null"),
    ("annotation", "native dimension has no annotation"),
    ("dimension", "no native model dimension"),
    ("value_m", "no measured native value"),
    ("data", "native annotation has no display data"),
])
def test_null_native_objects_and_value_keep_precise_refusal(native, fault, match):
    setattr(native, fault, None)
    native.refuse(match)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, 0.0, 0.0073])
def test_actual_shared_assertion_rejects_wrong_or_nonfinite_value(native, value):
    native.value_m = value
    native.refuse("measures")


def test_native_model_value_precision_is_not_relaxed_to_sheet_scale(native):
    native.value_m += 0.5e-5 / 1000
    assert native.prove() == pytest.approx(abs(native.value_m) * 1000)
    native.value_m += 1.5e-5 / 1000
    native.refuse("measures")


@pytest.mark.parametrize("count", [-1, 0, 1, 3, 10000])
def test_arrow_count_is_exact_and_not_a_truncated_acceptance(native, count):
    native.arrow_count = count
    native.refuse("expected exactly two native arrow heads")
    assert native.reads["arrow_head_0"] == native.reads["arrow_head_1"] == 0


def test_missing_display_data_method_is_not_an_orientation_fallback(native, monkeypatch):
    monkeypatch.delattr(_Annotation, "GetDisplayData")
    error, fields = native.refuse("GetDisplayData")
    assert isinstance(error.__cause__, AttributeError)
    assert fields["type2"] == 2


@pytest.mark.parametrize("member", ["GetArrowHeadCount", "GetArrowHeadAtIndex2"])
def test_missing_documented_arrow_api_is_not_silently_skipped(native, monkeypatch, member):
    monkeypatch.delattr(_DisplayData, member)
    error, _fields = native.refuse(member)
    assert isinstance(error.__cause__, AttributeError)


def test_missing_scale_getter_has_no_sheet_scale_fallback(native, monkeypatch):
    monkeypatch.delattr(_View, "ScaleDecimal")
    error, _fields = native.refuse("ScaleDecimal")
    assert isinstance(error.__cause__, AttributeError)


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize("record", [None, (), (0.0,) * 11, (0.0,) * 13, 42])
def test_each_arrow_record_must_have_exactly_twelve_doubles(native, index, record):
    native.arrows[index] = record
    match = "is null" if record is None else ("has no len" if record == 42 else "exactly 12 doubles")
    _error, fields = native.refuse(match)
    if record != 42:
        assert fields["arrow_lengths"][-1] == (None if record is None else len(record))
    assert all(len(arrow) <= 12 for arrow in fields["arrow_heads"])


@pytest.mark.parametrize("slot", range(12))
@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, None, "0.0", True])
def test_every_documented_arrow_double_must_be_present_numeric_and_finite(native, slot, value):
    native.arrows[1][slot] = value
    native.refuse("must be (?:a finite number|finite)")


@pytest.mark.parametrize("direction,match", [
    ((1.0, 0.0, 0.0), "not sheet-vertical"),
    ((1.0, 1.0, 0.0), "not sheet-vertical"),
    ((0.0, 1.0, 1.0), "not sheet-vertical"),
    ((0.0, 0.0, 1.0), "not sheet-vertical"),
    ((0.0, 0.0, 0.0), "finite and nonzero"),
    ((2e-9, 1.0, 0.0), "not sheet-vertical"),
    ((0.0, 1.0, 2e-9), "not sheet-vertical"),
    ((1.7e308, 1.7e308, 1.7e308), "finite and nonzero"),
])
def test_direction_requires_normalized_exact_vertical_axis(native, direction, match):
    native.arrows[1][3:6] = direction
    native.refuse(match)


@pytest.mark.parametrize("sign", [-1, 1])
def test_vertical_arrows_must_have_opposite_y_signs(native, sign):
    native.arrows[0][4] = sign * 3.0
    native.arrows[1][4] = sign * 7.0
    native.refuse("opposite Y signs")


def test_tiny_axis_roundoff_within_dimensionless_bound_is_accepted(native):
    native.arrows[0][3:6] = (0.5e-9 * 3, -3.0, -0.5e-9 * 3)
    native.arrows[1][3:6] = (-0.5e-9 * 7, 7.0, 0.5e-9 * 7)
    assert native.prove() == pytest.approx(native.expected_mm)


@pytest.mark.parametrize("fault,match", [
    ("different-x", "same sheet X"), ("off-plane", "sheet Z plane"),
    ("zero-span", "span must be finite and positive"),
    ("overflow-span", "span must be finite and positive"),
    ("translated", "do not match the projected physical station Ys"),
    ("one-translated", "do not match the projected physical station Ys"),
    ("shorter-span", "native arrow span disagrees"),
])
def test_native_tips_require_exact_plane_axis_stations_and_independent_span(native, fault, match):
    if fault == "different-x":
        native.arrows[1][0] += 2e-8
    elif fault == "off-plane":
        native.arrows[0][2] = -2e-8
    elif fault == "zero-span":
        native.arrows[1][1] = native.arrows[0][1]
    elif fault == "overflow-span":
        native.arrows[0][1], native.arrows[1][1] = -1.7e308, 1.7e308
    elif fault == "translated":
        for arrow in native.arrows:
            arrow[1] += 0.003  # Same span and verticality are insufficient.
    elif fault == "one-translated":
        native.arrows[1][1] += 0.003
    else:
        # Each tip individually is within tolerance, but their span is not.
        native.arrows[0][1] += 0.75e-8
        native.arrows[1][1] -= 0.75e-8
    native.refuse(match)


def test_inherited_sheet_position_tolerance_is_numeric_not_receipt_fitted(native):
    native.arrows[1][0] += 0.5e-8
    for arrow in native.arrows:
        arrow[1] += 0.25e-8
        arrow[2] = -0.5e-8
    assert native.prove() == pytest.approx(native.expected_mm)


@pytest.mark.parametrize("scale", [None, "3.2", True, math.nan, math.inf, -math.inf, 0.0, -3.2, 1.6, 5e-324])
def test_fresh_native_scale_must_be_numeric_finite_positive_and_match_projection(native, scale):
    native.scale = scale
    native.refuse("ScaleDecimal|scaled physical length")


def test_scaled_expected_height_must_not_overflow(native):
    native.scale = 1.7e308
    native.value_m = 2.0
    native.refuse("scaled physical length must be finite and positive", expected_mm=2000.0)


@pytest.mark.parametrize("projected", [
    None, [], [(0.0, 0.1)], [(0.0, 0.1)] * 3,
    [(0.0, 0.1, 0.0), (0.0, 0.2, 0.0)], [None, (0.0, 0.2)],
    [(math.nan, 0.1), (0.0, 0.2)], [(0.0, math.inf), (0.0, 0.2)],
    [(0.0, 0.1), (0.0, -math.inf)], [("0.0", 0.1), (0.0, 0.2)],
])
def test_projection_must_return_exactly_two_finite_sheet_xy_points(native, projected):
    native.projected_override = projected
    native.refuse("projected|has no len")


@pytest.mark.parametrize("fault,match", [
    ("collapsed", "projected physical station span must be finite and positive"),
    ("overflow", "projected physical station span must be finite and positive"),
    ("wrong-span", "projected physical station span disagrees"),
    ("translated", "do not match the projected physical station Ys"),
])
def test_projection_station_delta_and_absolute_locations_both_matter(native, fault, match):
    projected = native.project(native.adapter, native.view, native.points_m, label="fixture")
    if fault == "collapsed":
        projected[1] = (projected[1][0], projected[0][1])
    elif fault == "overflow":
        projected = [(0.0, -1.7e308), (0.0, 1.7e308)]
    elif fault == "wrong-span":
        projected[1] = (projected[1][0], projected[1][1] + 2e-8)
    else:
        projected = [(x, y + 0.004) for x, y in projected]
    native.projected_override = projected
    native.refuse(match)


@pytest.mark.parametrize("expected", [None, "7.25", True, math.nan, math.inf, 0.0, -7.25])
def test_expected_height_cannot_disable_numeric_proof(native, expected):
    native.refuse("expected_mm", expected_mm=expected)


@pytest.mark.parametrize("points", [
    (), ((0.0, 0.0, 0.0),), ((0.0, 0.0), (0.0, 0.1)),
    ((0.0, math.nan, 0.0), (0.0, 0.1, 0.0)),
    ((0.0, 0.0, 0.0), (0.0, 0.1, math.inf)),
])
def test_exact_physical_model_stations_are_required_before_projection(native, points):
    native.refuse("physical (?:model XYZ stations|station)", points_m=points)
    assert native.reads["station_projection"] == 0


@pytest.mark.parametrize("entities", [None, (), (object(),), (None, object())])
def test_required_exact_edges_cannot_fall_into_shared_value_only_mode(native, entities):
    native.refuse("named physical edges|has no len", entities=entities)
    assert native.reads["system_value"] == 0


@pytest.mark.parametrize("key", [
    "bind_IDisplayDimension", "annotation", "bind_IAnnotation", "bind_ISldWorks",
    "type2", "attached_count", "attached_entities", "attached_types", "dangling",
    "owner_type", "owner", "owner_same", "native_dimension", "system_value", "edge_same",
    "display_data", "bind_IDisplayData", "arrow_count", "arrow_head_0", "arrow_head_1",
    "bind_IView", "scale_decimal", "station_projection",
])
def test_every_native_getter_binder_and_proof_failure_chains_original(native, key):
    original = OSError(f"native refusal from {key}")
    native.failures[key] = original
    error, fields = native.refuse("native refusal")
    assert error.__cause__ is original
    assert fields["failure_error_type"] == "OSError"
    assert fields["failure_error"] == str(original)
    assert not any(name == "drawing.physical_axial_dimension_native_proof" for name, _ in native.events)


@pytest.mark.parametrize("key", ["annotation", "attached_entities", "attached_types", "dangling"])
def test_second_getter_failure_inside_unchanged_shared_proof_is_not_lost(native, key):
    original = OSError(f"second native {key} read failed")
    native.fail_on[key] = (2, original)
    error, _fields = native.refuse("second native")
    assert error.__cause__ is original


class _BoundedMetadata:
    def __init__(self, item):
        self.item = item
        self.slots = []

    def __len__(self):
        return 10000

    def __getitem__(self, index):
        assert 0 <= index < 4, "failure diagnostics must never expand the full array"
        self.slots.append(index)
        return self.item


def test_failure_metadata_snapshot_has_true_lengths_and_only_first_four_slots(native):
    native.type2 = 12
    native.attached = _BoundedMetadata(object())
    native.kinds = _BoundedMetadata(1)
    _error, fields = native.refuse("expected linear dimension Type2=2")
    assert fields["attached_length"] == fields["kinds_length"] == 10000
    assert fields["attached_nulls"] == (False,) * 4
    assert fields["kinds"] == (1,) * 4
    assert native.attached.slots == native.kinds.slots == [0, 1, 2, 3]
    assert native.reads["attached_entities"] == native.reads["attached_types"] == 1
    assert "failure_probe_error" not in fields
    assert not {"count_api", "attached_len", "kinds_len", "owner_is_same"} & fields.keys()


def test_malformed_kind_preserves_all_bounded_raw_slots_before_validation(native):
    class MalformedKinds(_BoundedMetadata):
        def __getitem__(self, index):
            super().__getitem__(index)
            return (1, None, 46, 1)[index]

    native.kinds = MalformedKinds(None)
    _error, fields = native.refuse("attachment type 1 must be a native integer")
    assert fields["kinds_length"] == 10000
    assert fields["kinds"] == (1, None, 46, 1)
    assert native.kinds.slots == [0, 1, 2, 3]
    assert native.reads["attached_types"] == 1
    assert native.reads["dangling"] == 0


def test_malformed_kind_diagnostic_representation_is_bounded_without_coercion(native):
    value = "1" * 2000
    native.kinds = (1, value)
    error, fields = native.refuse("attachment type 1 must be a native integer")
    assert isinstance(error.__cause__, TypeError)
    assert fields["kinds_length"] == 2
    assert fields["kinds"][0] == 1
    assert isinstance(fields["kinds"][1], str)
    assert len(fields["kinds"][1]) <= 120


@pytest.mark.parametrize("field,read_key", [
    ("attached", "attached_entities"),
    ("kinds", "attached_types"),
])
def test_scalar_native_arrays_refuse_with_original_length_error(native, field, read_key):
    setattr(native, field, 7)
    error, fields = native.refuse("has no len")
    assert isinstance(error.__cause__, TypeError)
    assert fields["attached_count"] == 2
    assert native.reads[read_key] == 1
    assert native.reads["dangling"] == 0


def test_malformed_string_attachment_records_length_that_was_actually_read(native):
    native.attached = "bad"
    _error, fields = native.refuse("expected two nonnull actual edge attachments")
    assert fields["attached_length"] == 3
    assert fields["attached_nulls"] == (False, False, False)
    assert native.reads["attached_entities"] == 1


def test_failure_error_text_is_bounded_but_original_exception_is_unchanged(native):
    original = OSError("x" * 2000)
    native.failures["scale_decimal"] = original
    error, fields = native.refuse("x{100}")
    assert len(fields["failure_error"]) == 500
    assert len(fields["reason"]) == 500
    assert error.__cause__ is original and len(str(original)) == 2000


@pytest.mark.parametrize("phase", ["settled", "saved"])
@pytest.mark.parametrize("fault", [
    "type2", "count", "owner", "attachments", "value", "arrows", "arrow_count", "scale", "projection",
])
def test_new_call_after_settled_or_saved_state_change_cannot_reuse_prior_success(native, phase, fault):
    assert native.prove(label=f"{phase} initial", phase=phase) == pytest.approx(native.expected_mm)
    if fault == "type2":
        native.type2 = 12
    elif fault == "count":
        native.attached_count = 1
    elif fault == "owner":
        native.owner = object()
    elif fault == "attachments":
        native.attached = (object(), native.entities[1])
    elif fault == "value":
        native.value_m += 0.001
    elif fault == "arrows":
        native.arrows[0][3:6] = (1.0, 0.0, 0.0)
    elif fault == "arrow_count":
        native.arrow_count = 1
    elif fault == "scale":
        native.scale /= 2
    else:
        native.offset = (native.offset[0], native.offset[1] + 0.002)
    native.refuse(".", label=f"{phase} fresh", phase=phase)
    assert native.reads["type2"] == 2
    assert native.events[-1][0] == "drawing.physical_axial_dimension_native_refusal"


def test_each_success_rereads_all_geometry_even_when_native_objects_are_replaced(native):
    assert native.prove() == pytest.approx(native.expected_mm)
    native.display = _Display(native)
    native.annotation = _Annotation(native)
    native.dimension = _Dimension(native)
    native.data = _DisplayData(native)
    native.scale = native.transform_scale = 1.75
    native.offset = (0.11, -0.02)
    for arrow, point in zip(native.arrows, native.points_m, strict=True):
        arrow[1] = native.offset[1] + point[1] * native.transform_scale
    assert native.prove() == pytest.approx(native.expected_mm)
    for key in ("type2", "attached_count", "owner", "owner_same", "native_dimension", "system_value",
                "display_data", "arrow_count", "arrow_head_0", "arrow_head_1", "scale_decimal", "station_projection"):
        assert native.reads[key] == 2
    assert native.events[-1][1]["scale_decimal"] == 1.75
    assert len(native.projections) == 2


@pytest.mark.parametrize("phase", ["creation", "settled", "saved"])
def test_phase_is_explicit_evidence_not_a_different_acceptance_mode(native, phase):
    assert native.prove(label="InventedPhysicalLength", phase=phase) == pytest.approx(native.expected_mm)
    assert native.events[-1][1]["label"] == "InventedPhysicalLength"
    assert native.events[-1][1]["phase"] == phase
    native.type2 = 3
    native.refuse("expected linear dimension Type2=2", label="InventedPhysicalLength", phase=phase)
    assert native.events[-1][1]["type2"] == 3


def test_stock_creation_uses_view_entities_and_exact_drawing_selection_points(native):
    assert native.create() is native.display
    expected_points = {
        index: (native.offset[0] + point[0] * native.transform_scale,
                native.offset[1] + point[1] * native.transform_scale, 0.0)
        for index, point in enumerate(native.points_m, 1)
    }
    assert native.created_selection == native.entities
    assert native.created_points == expected_points
    assert native.selection == [] and native.selection_points == {}
    assert [entry for entry in native.operations if entry[0] == "closest"] == [
        ("closest", entity, point)
        for entity, point in zip(native.entities, native.points_m, strict=True)
    ]
    assert [entry for entry in native.operations if entry[0] == "activate"] == [
        ("activate", "InventedStockFront")
    ]
    assert [entry for entry in native.operations if entry[0] == "select_entity"] == [
        ("select_entity", native.entities[0], False),
        ("select_entity", native.entities[1], True),
    ]
    assert [entry for entry in native.operations if entry[0] == "set_point"] == [
        ("set_point", index, point) for index, point in expected_points.items()
    ]
    assert [entry for entry in native.operations if entry[0] == "read_point"] == [
        ("read_point", 1), ("read_point", 2)
    ]
    assert native.operations[-2:] == [("create", (0.22, 0.18, 0.0)), ("clear",)]
    assert native.reads["clear_selection"] == 2
    assert native.reads["selection_count"] == 3
    assert native.reads["selection_kind_1"] == native.reads["selection_kind_2"] == 2
    assert native.reads["selected_object_1"] == native.reads["selected_object_2"] == 2
    assert native.reads["read_point_1"] == native.reads["read_point_2"] == 1
    assert native.reads["create_dimension"] == 1
    # Neither the creator nor its strict creation proof is replaced by a stub.
    assert native.reads["type2"] == native.reads["system_value"] == 1
    assert native.reads["arrow_head_0"] == native.reads["arrow_head_1"] == 1
    assert native.projections == [
        (native.points_m, "InventedStockLength"), (native.points_m, "InventedStockLength")
    ]
    name, fields = native.events[-1]
    assert name == "drawing.physical_axial_dimension_native_proof"
    assert fields["label"] == "InventedStockLength" and fields["phase"] == "creation"
    assert fields["type2"] == 2 and fields["measured_mm"] == pytest.approx(native.expected_mm)


@pytest.mark.parametrize("entities", [None, (), (object(),), (None, object()), (object(),) * 3])
def test_stock_creation_requires_exactly_two_nonnull_physical_edges(native, entities):
    native.refuse_creation("named physical edges|has no len", entities=entities)
    assert native.reads["create_dimension"] == native.reads["activate_view"] == 0


def test_stock_creation_rejects_one_native_edge_used_for_both_stations(native):
    native.refuse_creation("physical edges are not provably distinct", entities=(native.entities[0],) * 2)
    assert native.reads["create_dimension"] == native.reads["closest_point_0"] == 0


@pytest.mark.parametrize("same", [1, 2, None, True, "0", 0.0])
def test_stock_input_edges_must_be_distinct_by_exact_native_equality(native, monkeypatch, same):
    monkeypatch.setattr(native.application, "IsSame", lambda _left, _right: same)
    native.refuse_creation("distinct|native integer")
    assert native.reads["create_dimension"] == native.reads["activate_view"] == 0


@pytest.mark.parametrize("points", [
    None, (), ((0.0, 0.0, 0.0),), ((0.0, 0.0), (0.0, 0.1)),
    ((0.0, math.nan, 0.0), (0.0, 0.1, 0.0)),
    ((0.0, 0.0, 0.0), (0.0, 0.1, math.inf)),
    ((True, 0.0, 0.0), (0.0, 0.1, 0.0)),
    (("0.0", 0.0, 0.0), (0.0, 0.1, 0.0)),
])
def test_stock_creation_requires_finite_model_stations_before_selecting(native, points):
    native.refuse_creation("physical|has no len", points_m=points)
    assert native.reads["create_dimension"] == native.reads["activate_view"] == 0


@pytest.mark.parametrize("expected", [None, "7.25", True, math.nan, math.inf, 0.0, -7.25])
def test_stock_creation_requires_finite_positive_expected_length(native, expected):
    native.refuse_creation("expected_mm", expected_mm=expected)
    assert native.reads["create_dimension"] == native.reads["activate_view"] == 0


@pytest.mark.parametrize("text_xy", [None, (), (0.1,), (0.1, 0.2, 0.3), (math.nan, 0.2), (0.1, True)])
def test_stock_creation_requires_finite_text_position_before_selecting(native, text_xy):
    native.refuse_creation("text|has no len", text_xy=text_xy)
    assert native.reads["create_dimension"] == native.reads["activate_view"] == 0


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize("closest", [None, (), (0.0,) * 4, (0.0,) * 6, 42])
def test_stock_creation_requires_documented_actual_edge_closest_point_record(native, index, closest):
    native.closest_overrides[index] = closest
    native.refuse_creation("closest point|has no len")
    assert native.reads["create_dimension"] == native.reads["activate_view"] == 0


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize("slot", range(4))
@pytest.mark.parametrize("value", [None, True, "0.0", math.nan, math.inf])
def test_stock_actual_edge_xyz_and_parameter_are_finite_without_coercion(native, index, slot, value):
    closest = [*native.points_m[index], 0.0, None]
    closest[slot] = value
    native.closest_overrides[index] = closest
    native.refuse_creation("closest point slot")
    assert native.reads["create_dimension"] == native.reads["activate_view"] == 0


@pytest.mark.parametrize("unused", [None, math.nan, math.inf, "unused"])
def test_stock_closest_point_ignores_only_sdk_documented_fifth_unused_slot(native, unused):
    native.closest_overrides[1] = (*native.points_m[1], 0.0, unused)
    assert native.create() is native.display


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize("axis", range(3))
def test_stock_underlying_curve_point_is_not_a_trimmed_edge_point(native, index, axis):
    closest = [*native.points_m[index], 0.0, None]
    closest[axis] += 2e-8
    native.closest_overrides[index] = closest
    native.refuse_creation("not on its actual trimmed edge")
    assert native.reads["create_dimension"] == native.reads["activate_view"] == 0


@pytest.mark.parametrize("projected", [
    None, [], [(0.0, 0.1)], [(0.0, 0.1)] * 3,
    [(0.0, 0.1, 0.0), (0.0, 0.2, 0.0)], [None, (0.0, 0.2)],
    [(math.nan, 0.1), (0.0, 0.2)], [(0.0, math.inf), (0.0, 0.2)],
    [(0.0, 0.1), ("0.0", 0.2)],
])
def test_stock_creation_requires_exact_finite_projected_sheet_points(native, projected):
    native.projected_override = projected
    native.refuse_creation("projected|has no len")
    assert native.reads["create_dimension"] == native.reads["activate_view"] == 0


@pytest.mark.parametrize("result", [False, None, 1, "true"])
def test_stock_creation_requires_exact_view_activation_success(native, result):
    native.activate_result = result
    native.refuse_creation("cannot activate exact")
    assert native.reads["select_edge_1"] == native.reads["create_dimension"] == 0


@pytest.mark.parametrize("name", [None, "", 42])
def test_stock_creation_never_activates_sheet_or_missing_view_name(native, monkeypatch, name):
    monkeypatch.setattr(proof, "view_name", lambda _adapter, _view: name)
    native.refuse_creation("cannot activate exact")
    assert native.reads["activate_view"] == native.reads["create_dimension"] == 0


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize("result", [False, None, 1])
def test_stock_view_selection_failure_has_no_coordinate_or_model_selection_fallback(native, index, result):
    native.select_results[index] = result
    native.refuse_creation("failed to select physical edge")
    assert native.reads["create_dimension"] == 0


@pytest.mark.parametrize("ordinal", [1, 2, 3])
@pytest.mark.parametrize("count", [-1, 0, 9, None, True, 2.0, "2"])
def test_stock_every_selection_count_readback_is_exact(native, ordinal, count):
    native.count_overrides[ordinal] = count
    native.refuse_creation("selection count|exactly two selected")
    assert native.reads["create_dimension"] == 0


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize("kind", [0, 2, 3, 46, None, True, 1.0, "1"])
def test_stock_selection_readback_requires_actual_native_edges(native, index, kind):
    native.selected_kinds[index] = kind
    native.refuse_creation("not an EDGE|selection type")
    assert native.reads["create_dimension"] == 0


@pytest.mark.parametrize("index", [1, 2])
@pytest.mark.parametrize("fault", ["null", "wrong", "swapped", "duplicate"])
def test_stock_selected_objects_must_match_exact_named_edges(native, index, fault):
    if fault == "null":
        value = None
    elif fault == "wrong":
        value = object()
    elif fault == "swapped":
        value = native.entities[2 - index]
    else:
        value = native.entities[0]
        if index == 1:
            value = native.entities[1]
    native.selected_overrides[index] = value
    native.refuse_creation("selected physical edge .* is null|wrong selected object")
    assert native.reads["create_dimension"] == 0


def test_stock_selection_pair_distinctness_is_native_not_python_identity(native, monkeypatch):
    first, second = native.entities
    original = native.application.IsSame

    def equality(left, right):
        if len(native.selection) == 2 and left is first and right is second:
            return 1
        return original(left, right)

    monkeypatch.setattr(native.application, "IsSame", equality)
    native.refuse_creation("selected physical edges are not provably distinct")
    assert native.reads["create_dimension"] == 0


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize("result", [False, None, 1])
def test_stock_selection_point_setter_must_succeed_for_each_station(native, index, result):
    native.set_point_results[index] = result
    native.refuse_creation("cannot set physical selection point")
    assert native.reads["create_dimension"] == 0


@pytest.mark.parametrize("index", [1, 2])
@pytest.mark.parametrize("point", [None, (), (0.0, 0.1), (0.0,) * 4, 42])
def test_stock_selection_point_readback_requires_exact_native_xyz(native, index, point):
    native.point_overrides[index] = point
    native.refuse_creation("selection point|has no len")
    assert native.reads["create_dimension"] == 0


@pytest.mark.parametrize("index", [1, 2])
@pytest.mark.parametrize("axis", range(3))
@pytest.mark.parametrize("value", [None, True, "0", math.nan, math.inf])
def test_stock_every_selection_point_coordinate_is_finite_and_native(native, index, axis, value):
    point = list(native.points_m[index - 1])
    point[axis] = value
    native.point_overrides[index] = point
    native.refuse_creation("selection point .* coordinate")
    assert native.reads["create_dimension"] == 0


@pytest.mark.parametrize("index", [1, 2])
@pytest.mark.parametrize("axis", range(3))
def test_stock_selection_points_must_read_back_the_set_drawing_world_point(native, index, axis):
    physical = native.points_m[index - 1]
    point = [native.offset[0] + physical[0] * native.transform_scale,
             native.offset[1] + physical[1] * native.transform_scale, 0.0]
    point[axis] += 2e-8
    native.point_overrides[index] = point
    native.refuse_creation("differs from projected physical station")
    assert native.reads["create_dimension"] == 0


def test_stock_source_model_xyz_is_not_mistaken_for_drawing_selection_point(native):
    native.point_overrides[1] = native.points_m[0]
    native.refuse_creation("differs from projected physical station")
    assert native.reads["create_dimension"] == 0


@pytest.mark.parametrize("fault", ["count", "first-kind", "first-identity", "first-point", "distinct"])
def test_stock_rechecks_entire_selection_after_both_point_setters(native, monkeypatch, fault):
    first, second = native.entities
    original = native.application.IsSame

    def mutate(index):
        if index != 2:
            return
        if fault == "count":
            native.selection.append(object())
        elif fault == "first-kind":
            native.selected_kinds[0] = 46
        elif fault == "first-identity":
            native.selection[0] = object()
        elif fault == "first-point":
            native.selection_points[1] = (0.0, 0.0, 0.0)
        else:
            native.selection[1] = first

    def equality(left, right):
        if len(native.selection_points) == 2 and left is first and right is second:
            return 1
        return original(left, right)

    native.after_set_point = mutate
    if fault == "distinct":
        monkeypatch.setattr(native.application, "IsSame", equality)
    native.refuse_creation("selected|selection point")
    assert native.reads["create_dimension"] == 0


@pytest.mark.parametrize("target,member", [
    (_Edge, "GetClosestPointOn"), (_View, "SelectEntity"), (_Model, "ActivateView"),
    (_SelectionManager, "GetSelectedObjectCount2"), (_SelectionManager, "GetSelectedObjectType3"),
    (_SelectionManager, "GetSelectedObject6"), (_SelectionManager, "SetSelectionPoint2"),
    (_SelectionManager, "GetSelectionPoint2"), (_Model, "AddVerticalDimension2"),
])
def test_stock_missing_documented_native_api_is_a_refusal_not_a_fallback(native, monkeypatch, target, member):
    monkeypatch.delattr(target, member)
    error, _fields = native.refuse_creation(member)
    assert isinstance(error.__cause__, AttributeError)
    assert native.reads["create_dimension"] == 0


@pytest.mark.parametrize("key", [
    "bind_ISldWorks", "bind_IEdge", "closest_point_0", "closest_point_1",
    "station_projection", "bind_IView", "bind_IDrawingDoc", "selection_manager",
    "bind_ISelectionMgr", "activate_view", "select_edge_1", "select_edge_2",
    "selection_count", "selection_kind_1", "selection_kind_2",
    "selected_object_1", "selected_object_2", "edge_same",
    "set_point_1", "set_point_2", "read_point_1", "read_point_2", "create_dimension",
])
def test_stock_native_selection_and_factory_failures_keep_original_cause_and_clear(native, key):
    original = OSError(f"invented native stock refusal: {key}")
    native.failures[key] = original
    error, _fields = native.refuse_creation("invented native stock refusal")
    assert error.__cause__ is original
    assert not any(name == "drawing.physical_axial_dimension_native_proof" for name, _fields in native.events)


def test_stock_native_null_creation_is_never_replaced_or_type_coerced(native):
    native.creation_display = None
    _error, fields = native.refuse_creation("native vertical dimension creation returned null")
    assert fields["display_null"] is True
    assert native.reads["create_dimension"] == 1
    assert native.reads["type2"] == 0


@pytest.mark.parametrize("fault", [
    "angular", "horizontal", "diagonal", "same-arrow-sign", "wrong-stations",
    "different-x", "off-plane", "wrong-span", "scale", "value", "attachments", "owner",
])
def test_stock_created_dimension_immediately_runs_unchanged_strict_native_proof(native, fault):
    if fault == "angular":
        native.type2 = 3
    elif fault == "horizontal":
        native.arrows[0][3:6] = (1.0, 0.0, 0.0)
        native.arrows[1][3:6] = (-1.0, 0.0, 0.0)
    elif fault == "diagonal":
        native.arrows[0][3:6] = (1.0, 1.0, 0.0)
    elif fault == "same-arrow-sign":
        native.arrows[0][4] = 3.0
    elif fault == "wrong-stations":
        for arrow in native.arrows:
            arrow[1] += 0.002
    elif fault == "different-x":
        native.arrows[1][0] += 2e-8
    elif fault == "off-plane":
        native.arrows[1][2] = 2e-8
    elif fault == "wrong-span":
        native.arrows[1][1] += 2e-8
    elif fault == "scale":
        native.scale /= 2
    elif fault == "value":
        native.value_m += 0.001
    elif fault == "attachments":
        native.attached = (object(), native.entities[1])
    else:
        native.owner = object()
    native.refuse_creation(".")
    assert native.reads["create_dimension"] == 1
    assert native.reads["type2"] == 1
    assert not any(name == "drawing.physical_axial_dimension_native_proof" for name, _fields in native.events)


@pytest.mark.parametrize("result", [0, 2, None, True, "1", 1.0])
def test_stock_selected_edge_identity_requires_exact_native_same_state(native, monkeypatch, result):
    original = native.application.IsSame

    def equality(left, right):
        if native.selection and left is right and any(right is edge for edge in native.entities):
            return result
        return original(left, right)

    monkeypatch.setattr(native.application, "IsSame", equality)
    native.refuse_creation("wrong selected object|native integer")
    assert native.reads["create_dimension"] == 0


@pytest.mark.parametrize("result", [-1, 1, 2, None, True, "0", 0.0])
def test_stock_selected_pair_requires_exact_native_different_state(native, monkeypatch, result):
    first, second = native.entities
    original = native.application.IsSame

    def equality(left, right):
        if len(native.selection) == 2 and left is first and right is second:
            return result
        return original(left, right)

    monkeypatch.setattr(native.application, "IsSame", equality)
    native.refuse_creation("selected physical edges are not provably distinct|native integer")
    assert native.reads["create_dimension"] == 0
