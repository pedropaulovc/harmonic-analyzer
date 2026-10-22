"""Offline native-boundary fakes; the actual spatial and shared edge/value proofs run.

These invented dimensions/transforms deliberately are not native receipt fixtures.
No COM, selection, setters, rebuilds, or saves are used by this test module.
"""

from __future__ import annotations

from collections import Counter
import math
from types import SimpleNamespace

import pytest

import _drawing_physical_head_height as proof


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


class _View(_Native):
    @property
    def ScaleDecimal(self):
        return self.read("scale_decimal", self.state.scale)


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
        self.entities = (object(), object())
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
        self.adapter = SimpleNamespace(swApp=self.application)
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
            entities=self.entities, points_m=self.points_m, expected_mm=self.expected_mm
        )
        arguments.update(changes)
        return proof.assert_native_physical_head_height(
            self.adapter, self.view, self.display, **arguments
        )

    def refuse(self, match, stage=None, **changes):
        with pytest.raises(RuntimeError, match=match) as caught:
            self.prove(**changes)
        assert "native_snapshot={" in str(caught.value)
        name, fields = self.events[-1]
        assert name == "drawing.physical_head_height_native_refusal"
        assert fields["failure_error_type"] == type(caught.value.__cause__).__name__
        assert fields["failure_error"] == str(caught.value.__cause__)[:500]
        if stage is not None:
            assert fields["failure_stage"] == stage
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
    assert name == "drawing.physical_head_height_native_proof"
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
    _error, fields = native.refuse("expected linear dimension Type2=2", "metadata_predicates")
    assert fields["type2"] == dimension_type
    assert fields["owner_same"] == 1
    assert fields["attached_count"] == fields["attached_length"] == fields["kinds_length"] == 2
    assert fields["kinds"] == (1, 1) and fields["attached_nulls"] == (False, False)
    assert fields["dangling"] is False and fields["owner_null"] is False
    assert fields["owner_type"] == 0
    assert native.reads["type2"] == native.reads["owner_same"] == 1
    assert native.reads["display_data"] == native.reads["native_dimension"] == 0


@pytest.mark.parametrize("field,stage", [
    ("type2", "type2"), ("attached_count", "attached_count"),
    ("arrow_count", "arrow_count"), ("owner_type", "owner_type"),
    ("owner_same", "owner_same"),
])
@pytest.mark.parametrize("value", [None, "2", 2.0, 2.5, True, False, math.nan, math.inf])
def test_malformed_integer_getters_are_not_coerced_or_truncated(native, field, stage, value):
    # None means identity-based native equality in this fixture, so explicitly
    # return None through the application's getter for that one malformed case.
    if field == "owner_same" and value is None:
        native.application.IsSame = lambda _left, _right: None
    else:
        setattr(native, field, value)
    native.refuse("must be a native integer", stage)


@pytest.mark.parametrize("count", [-2, 0, 1, 3, 10000])
def test_attachment_count_must_be_exactly_two(native, count):
    native.attached_count = count
    native.refuse("expected two nonnull actual edge attachments", "metadata_predicates")


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
    native.refuse("expected two nonnull actual edge attachments", "metadata_predicates")


@pytest.mark.parametrize("value", [1.5, "1", None, True])
def test_malformed_attachment_kind_is_not_coerced(native, value):
    native.kinds = (1, value)
    native.refuse("attachment type 1 must be a native integer", "attached_types")


@pytest.mark.parametrize("value", [None, 0, 1, "false"])
def test_missing_or_malformed_dangling_result_is_not_false_success(native, value):
    native.dangling = value
    native.refuse("IsDangling must return a native boolean", "dangling")


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
    native.refuse("expected exact front-view owner", "metadata_predicates")


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
    native.refuse("not the dimension between its named entities", "physical_measurement")
    assert native.reads["system_value"] == 0


@pytest.mark.parametrize("fault,match,stage", [
    ("display", "native display dimension is null", "display"),
    ("annotation", "native dimension has no annotation", "annotation"),
    ("dimension", "no native model dimension", "physical_measurement"),
    ("value_m", "no measured native value", "physical_measurement"),
    ("data", "native annotation has no display data", "display_data"),
])
def test_null_native_objects_and_value_keep_precise_refusal(native, fault, match, stage):
    setattr(native, fault, None)
    native.refuse(match, stage)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, 0.0, 0.0073])
def test_actual_shared_assertion_rejects_wrong_or_nonfinite_value(native, value):
    native.value_m = value
    native.refuse("measures", "physical_measurement")


def test_native_model_value_precision_is_not_relaxed_to_sheet_scale(native):
    native.value_m += 0.5e-5 / 1000
    assert native.prove() == pytest.approx(abs(native.value_m) * 1000)
    native.value_m += 1.5e-5 / 1000
    native.refuse("measures", "physical_measurement")


@pytest.mark.parametrize("count", [-1, 0, 1, 3, 10000])
def test_arrow_count_is_exact_and_not_a_truncated_acceptance(native, count):
    native.arrow_count = count
    native.refuse("expected exactly two native arrow heads", "arrow_count")
    assert native.reads["arrow_head_0"] == native.reads["arrow_head_1"] == 0


def test_missing_display_data_method_is_not_an_orientation_fallback(native, monkeypatch):
    monkeypatch.delattr(_Annotation, "GetDisplayData")
    error, fields = native.refuse("GetDisplayData", "display_data")
    assert isinstance(error.__cause__, AttributeError)
    assert fields["type2"] == 2


@pytest.mark.parametrize("member,stage", [
    ("GetArrowHeadCount", "arrow_count"),
    ("GetArrowHeadAtIndex2", "arrow_head_0"),
])
def test_missing_documented_arrow_api_is_not_silently_skipped(native, monkeypatch, member, stage):
    monkeypatch.delattr(_DisplayData, member)
    error, _fields = native.refuse(member, stage)
    assert isinstance(error.__cause__, AttributeError)


def test_missing_scale_getter_has_no_sheet_scale_fallback(native, monkeypatch):
    monkeypatch.delattr(_View, "ScaleDecimal")
    error, _fields = native.refuse("ScaleDecimal", "scale_decimal")
    assert isinstance(error.__cause__, AttributeError)


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize("record", [None, (), (0.0,) * 11, (0.0,) * 13, 42])
def test_each_arrow_record_must_have_exactly_twelve_doubles(native, index, record):
    native.arrows[index] = record
    match = "is null" if record is None else ("has no len" if record == 42 else "exactly 12 doubles")
    _error, fields = native.refuse(match, f"arrow_head_{index}")
    if record != 42:
        assert fields["arrow_lengths"][-1] == (None if record is None else len(record))
    assert all(len(arrow) <= 12 for arrow in fields["arrow_heads"])


@pytest.mark.parametrize("slot", range(12))
@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, None, "0.0", True])
def test_every_documented_arrow_double_must_be_present_numeric_and_finite(native, slot, value):
    native.arrows[1][slot] = value
    native.refuse("must be (?:a finite number|finite)", "arrow_head_1")


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
    native.refuse(match, "arrow_direction_1")


@pytest.mark.parametrize("sign", [-1, 1])
def test_vertical_arrows_must_have_opposite_y_signs(native, sign):
    native.arrows[0][4] = sign * 3.0
    native.arrows[1][4] = sign * 7.0
    native.refuse("opposite Y signs", "arrow_geometry")


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
    stage = "arrow_geometry" if fault in {"different-x", "off-plane", "zero-span", "overflow-span"} else "station_geometry"
    native.refuse(match, stage)


def test_inherited_sheet_position_tolerance_is_numeric_not_receipt_fitted(native):
    native.arrows[1][0] += 0.5e-8
    for arrow in native.arrows:
        arrow[1] += 0.25e-8
        arrow[2] = -0.5e-8
    assert native.prove() == pytest.approx(native.expected_mm)


@pytest.mark.parametrize("scale", [None, "3.2", True, math.nan, math.inf, -math.inf, 0.0, -3.2, 1.6, 5e-324])
def test_fresh_native_scale_must_be_numeric_finite_positive_and_match_projection(native, scale):
    native.scale = scale
    stage = "station_geometry" if scale == 1.6 else "scale_decimal"
    native.refuse("ScaleDecimal|scaled physical height", stage)


def test_scaled_expected_height_must_not_overflow(native):
    native.scale = 1.7e308
    native.value_m = 2.0
    native.refuse("scaled physical height must be finite and positive", "scale_decimal", expected_mm=2000.0)


@pytest.mark.parametrize("projected", [
    None, [], [(0.0, 0.1)], [(0.0, 0.1)] * 3,
    [(0.0, 0.1, 0.0), (0.0, 0.2, 0.0)], [None, (0.0, 0.2)],
    [(math.nan, 0.1), (0.0, 0.2)], [(0.0, math.inf), (0.0, 0.2)],
    [(0.0, 0.1), (0.0, -math.inf)], [("0.0", 0.1), (0.0, 0.2)],
])
def test_projection_must_return_exactly_two_finite_sheet_xy_points(native, projected):
    native.projected_override = projected
    native.refuse("projected|has no len", "station_projection")


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
    native.refuse(match, "station_geometry")


@pytest.mark.parametrize("expected", [None, "7.25", True, math.nan, math.inf, 0.0, -7.25])
def test_expected_height_cannot_disable_numeric_proof(native, expected):
    native.refuse("expected_mm", "physical_inputs", expected_mm=expected)


@pytest.mark.parametrize("points", [
    (), ((0.0, 0.0, 0.0),), ((0.0, 0.0), (0.0, 0.1)),
    ((0.0, math.nan, 0.0), (0.0, 0.1, 0.0)),
    ((0.0, 0.0, 0.0), (0.0, 0.1, math.inf)),
])
def test_exact_physical_model_stations_are_required_before_projection(native, points):
    native.refuse("physical (?:model XYZ stations|station)", "physical_inputs", points_m=points)
    assert native.reads["station_projection"] == 0


@pytest.mark.parametrize("entities", [None, (), (object(),), (None, object())])
def test_required_exact_edges_cannot_fall_into_shared_value_only_mode(native, entities):
    native.refuse("named physical edges|has no len", "physical_inputs", entities=entities)
    assert native.reads["system_value"] == 0


@pytest.mark.parametrize("key,stage", [
    ("bind_IDisplayDimension", "display_bind"), ("annotation", "annotation"),
    ("bind_IAnnotation", "annotation_bind"), ("bind_ISldWorks", "application_bind"),
    ("type2", "type2"), ("attached_count", "attached_count"),
    ("attached_entities", "attached_entities"), ("attached_types", "attached_types"),
    ("dangling", "dangling"), ("owner_type", "owner_type"), ("owner", "owner"),
    ("owner_same", "owner_same"), ("native_dimension", "physical_measurement"),
    ("system_value", "physical_measurement"), ("edge_same", "physical_measurement"),
    ("display_data", "display_data"), ("bind_IDisplayData", "display_data_bind"),
    ("arrow_count", "arrow_count"), ("arrow_head_0", "arrow_head_0"),
    ("arrow_head_1", "arrow_head_1"), ("bind_IView", "view_bind"),
    ("scale_decimal", "scale_decimal"), ("station_projection", "station_projection"),
])
def test_every_native_getter_binder_and_proof_failure_chains_original(native, key, stage):
    original = OSError(f"native refusal from {key}")
    native.failures[key] = original
    error, fields = native.refuse("native refusal", stage)
    assert error.__cause__ is original
    assert fields["failure_error_type"] == "OSError"
    assert fields["failure_error"] == str(original)
    assert not any(name == "drawing.physical_head_height_native_proof" for name, _ in native.events)


@pytest.mark.parametrize("key", ["annotation", "attached_entities", "attached_types", "dangling"])
def test_second_getter_failure_inside_unchanged_shared_proof_is_not_lost(native, key):
    original = OSError(f"second native {key} read failed")
    native.fail_on[key] = (2, original)
    error, _fields = native.refuse("second native", "physical_measurement")
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
    _error, fields = native.refuse("expected linear dimension Type2=2", "metadata_predicates")
    assert fields["attached_length"] == fields["kinds_length"] == 10000
    assert fields["attached_nulls"] == (False,) * 4
    assert fields["kinds"] == (1,) * 4
    assert native.attached.slots == native.kinds.slots == [0, 1, 2, 3]
    assert native.reads["attached_entities"] == native.reads["attached_types"] == 1
    assert "failure_probe_error" not in fields
    assert not {"count_api", "attached_len", "kinds_len", "owner_is_same"} & fields.keys()


def test_failure_error_text_is_bounded_but_original_exception_is_unchanged(native):
    original = OSError("x" * 2000)
    native.failures["scale_decimal"] = original
    error, fields = native.refuse("x{100}", "scale_decimal")
    assert len(fields["failure_error"]) == 500
    assert len(fields["reason"]) == 500
    assert error.__cause__ is original and len(str(original)) == 2000


@pytest.mark.parametrize("phase", ["settled", "saved"])
@pytest.mark.parametrize("fault", [
    "type2", "count", "owner", "attachments", "value", "arrows", "arrow_count", "scale", "projection",
])
def test_new_call_after_settled_or_saved_state_change_cannot_reuse_prior_success(native, phase, fault):
    assert native.prove(label=f"{phase} initial") == pytest.approx(native.expected_mm)
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
    native.refuse(".", label=f"{phase} fresh")
    assert native.reads["type2"] == 2
    assert native.events[-1][0] == "drawing.physical_head_height_native_refusal"


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
