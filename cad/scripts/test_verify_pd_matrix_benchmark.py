"""Offline consumer contracts for the isolated raw-matrix experiment.

Every native boundary is a Python fake. Import the probe only after replacing
its COM and telemetry dependencies; these tests never import a native API,
attach to a seat, or manufacture an exploded presentation control.
"""

from __future__ import annotations

import ast
import asyncio
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import weakref

import pytest


_MATRIX = (
    1.0,
    0.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
    1.0,
    0.25,
    -0.5,
    0.75,
    1.0,
    0.0,
    0.0,
    0.0,
)
_DOCUMENT_FIELDS = (
    "root_path",
    "root_title",
    "active_document",
    "opened_read_only",
    "needs_rebuild",
    "save_flag",
    "model_is_exploded",
    "extension_is_exploded",
    "active_exploded_view_owner",
    "enable_presentation",
    "active_configuration",
    "selection_count",
)


def _unexpected_native_boundary(*_args, **_kwargs):
    raise AssertionError("an unconfigured native boundary was reached")


@pytest.fixture
def probe(monkeypatch):
    telemetry = ModuleType("_telemetry")
    telemetry.traced = lambda *_args, **_kwargs: lambda function: function
    com = ModuleType("_com")
    for name in ("_early_bound", "_com_header", "_com_invoke"):
        setattr(com, name, _unexpected_native_boundary)
    monkeypatch.setitem(sys.modules, "_telemetry", telemetry)
    monkeypatch.setitem(sys.modules, "_com", com)
    for name in ("pythoncom", "pywintypes", "win32com", "solidworks_mcp"):
        monkeypatch.setitem(sys.modules, name, None)
    path = Path(__file__).with_name("_verify_pd_digest_probe.py")
    spec = importlib.util.spec_from_file_location(
        "_pd_matrix_benchmark_test_probe", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def _assert_primitives(value):
    if type(value) is dict:
        assert all(type(key) is str for key in value)
        for item in value.values():
            _assert_primitives(item)
    elif type(value) in (tuple, list):
        for item in value:
            _assert_primitives(item)
    else:
        assert value is None or type(value) in (str, bool, int, float)
    json.dumps(value, allow_nan=False)


def _changed_matrix(index, value, original=_MATRIX):
    values = list(original)
    values[index] = value
    return tuple(values)


class _IntSubclass(int):
    pass


class _FloatSubclass(float):
    pass


@pytest.mark.parametrize("container", [tuple, list])
def test_matrix_validation_returns_only_all_sixteen_builtin_floats(probe, container):
    source = container([1, -0.0, *range(2, 16)])
    result = probe._benchmark_matrix_values(source)
    assert type(result) is tuple
    assert len(result) == 16
    assert all(type(value) is float for value in result)
    assert result == tuple(float(value) for value in source)
    assert result[1].hex() == "-0x0.0p+0"
    assert result[15] == 15.0
    _assert_primitives(result)


@pytest.mark.parametrize("index", range(16))
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_matrix_validation_rejects_nonfinite_even_in_reserved_entries(
    probe, index, value
):
    with pytest.raises(RuntimeError):
        probe._benchmark_matrix_values(_changed_matrix(index, value))


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        "0",
        None,
        [0.0],
        (0.0,),
        {"value": 0.0},
        _IntSubclass(0),
        _FloatSubclass(0),
    ],
)
@pytest.mark.parametrize("index", [0, 15])
def test_matrix_validation_rejects_non_builtin_numeric_elements(probe, index, value):
    with pytest.raises(RuntimeError):
        probe._benchmark_matrix_values(_changed_matrix(index, value))


@pytest.mark.parametrize(
    "value",
    [
        None,
        0,
        "0" * 16,
        range(16),
        {index: 0.0 for index in range(16)},
        (),
        [0.0] * 15,
        [0.0] * 17,
        [[0.0] * 4 for _ in range(4)],
    ],
)
def test_matrix_validation_rejects_scalar_mapping_nested_and_wrongshape_arrays(
    probe, value
):
    with pytest.raises(RuntimeError):
        probe._benchmark_matrix_values(value)


class _Dispatch:
    """The only accepted raw receipt type; no pywin32 dependency."""

    def __init__(self, index):
        self.index = index

    def __getattr__(self, name):
        raise AssertionError(f"raw dispatch named-member access: {name}")


class _NativeReadError(RuntimeError):
    pass


class _InvalidElement:
    pass


@pytest.fixture
def reader(probe, monkeypatch):
    def install(*, failure=None, fail_index=0, matrices=(_MATRIX,)):
        references = []
        events = []

        def watch(value):
            references.append(weakref.ref(value))
            return value

        def assert_released():
            assert all(reference() is None for reference in references)

        def acquire(index, arm, include_presentation):
            assert include_presentation is True
            assert_released()
            events.append(("acquire", arm, index))
            raw = watch(_Dispatch(index))
            if failure == "acquire" and index == fail_index:
                raise _NativeReadError("native GetTotalTransform failed")
            return raw

        def array_data(raw):
            if failure == "array" and raw.index == fail_index:
                raise _NativeReadError("native ArrayData failed")
            values = list(matrices[raw.index])
            if failure == "validate" and raw.index == fail_index:
                values[15] = watch(_InvalidElement())
            return values

        class Component:
            def __init__(self, index):
                self.index = index

            def GetTotalTransform(self, include_presentation):
                return acquire(self.index, "A", include_presentation)

            def __getattr__(self, name):
                raise AssertionError(
                    f"unexpected component collection/name/state read: {name}"
                )

        class GeneratedTransform:
            def __init__(self, raw):
                self.raw = raw

            @property
            def ArrayData(self):
                return array_data(self.raw)

        def bound(raw, interface):
            assert events[-1][1] == "A", "raw arm must not bind its transform receipt"
            assert interface == "IMathTransform"
            assert isinstance(raw, _Dispatch)
            wrapped = watch(GeneratedTransform(raw))
            if failure == "bind" and raw.index == fail_index:
                raise _NativeReadError("native IMathTransform binding failed")
            return wrapped

        def invoke(value, interface, member, *args):
            if interface == "IComponent2" and member == "GetTotalTransform":
                assert len(args) == 1
                return acquire(value.index, "B", args[0])
            assert interface == "IMathTransform" and member == "ArrayData"
            assert args == () and isinstance(value, _Dispatch)
            return array_data(value)

        monkeypatch.setattr(probe, "_bound", bound)
        monkeypatch.setattr(probe, "_com_invoke", invoke)
        return SimpleNamespace(
            cohort=[Component(index) for index in range(len(matrices))],
            references=references,
            events=events,
            assert_released=assert_released,
        )

    return install


def _record_native_error(probe, error):
    report = {"errors": []}
    evidence = probe._error(report, "matrix-benchmark.fake-native-read", error)
    assert evidence["required"] is True
    assert evidence["type"] == "_NativeReadError"
    assert "_NativeReadError" in evidence["traceback"]
    assert str(error) in evidence["traceback"]
    assert type(evidence["traceback"]) is str
    _assert_primitives(report)
    return report


@pytest.mark.parametrize("arm", ["A", "B"])
def test_reads_reacquire_and_dispose_transforms_before_returning_primitives(
    probe, reader, arm
):
    fake = reader()
    for _ in range(2):
        result = probe._benchmark_read_matrix(fake.cohort[0], arm, _Dispatch)
        assert type(result) is tuple and result == _MATRIX
        assert all(type(value) is float for value in result)
        fake.assert_released()
    assert fake.events == [("acquire", arm, 0)] * 2
    assert len(fake.references) >= 2


@pytest.mark.parametrize(
    ("arm", "failure"),
    [("A", "acquire"), ("B", "acquire"), ("A", "array"), ("B", "array"), ("A", "bind")],
)
def test_native_read_errors_propagate_without_traceback_retaining_aliases(
    probe, reader, arm, failure
):
    fake = reader(failure=failure)
    with pytest.raises(_NativeReadError, match="native") as caught:
        probe._benchmark_read_matrix(fake.cohort[0], arm, _Dispatch)
    # Keep the exception and its traceback alive while checking the native
    # aliases: dropping pytest's exception holder must not be what releases them.
    fake.assert_released()
    _record_native_error(probe, caught.value)
    fake.assert_released()


@pytest.mark.parametrize("arm", ["A", "B"])
def test_validation_failure_disposes_transform_and_array_element_aliases(
    probe, reader, arm
):
    fake = reader(failure="validate")
    with pytest.raises(RuntimeError) as caught:
        probe._benchmark_read_matrix(fake.cohort[0], arm, _Dispatch)
    fake.assert_released()
    report = {"errors": []}
    probe._error(report, "matrix-benchmark.invalid-array", caught.value)
    _assert_primitives(report)
    fake.assert_released()


class _InvokeTypesImpostor:
    def InvokeTypes(self, *_args):
        raise AssertionError("InvokeTypes duck typing must not authenticate a receipt")


@pytest.mark.parametrize(
    "receipt_factory",
    [
        lambda: None,
        object,
        lambda: {},
        lambda: tuple(_MATRIX),
        _InvokeTypesImpostor,
        lambda: type("PyIDispatch", (), {})(),
        lambda: SimpleNamespace(_oleobj_=_Dispatch(0)),
    ],
)
def test_raw_arm_rejects_non_dispatch_receipts_before_array_read(
    probe, monkeypatch, receipt_factory
):
    component = object()
    calls = []

    def invoke(value, interface, member, *args):
        calls.append((interface, member))
        assert value is component
        assert (interface, member, args) == (
            "IComponent2",
            "GetTotalTransform",
            (True,),
        )
        return receipt_factory()

    monkeypatch.setattr(probe, "_com_invoke", invoke)
    monkeypatch.setattr(probe, "_bound", _unexpected_native_boundary)
    with pytest.raises(RuntimeError):
        probe._benchmark_read_matrix(component, "B", _Dispatch)
    assert calls == [("IComponent2", "GetTotalTransform")]


def _install_clock(probe, monkeypatch, fake, record):
    ticks = iter((100, 173))
    calls = []

    def clock():
        # The record and hex evidence must be built outside both timer edges.
        assert record == {}
        fake.assert_released()
        calls.append(next(ticks))
        return calls[-1]

    monkeypatch.setattr(probe, "time", SimpleNamespace(perf_counter_ns=clock))
    return calls


@pytest.mark.parametrize("arm", ["A", "B"])
def test_pass_times_full_ordered_sweep_through_release_before_evidence(
    probe, reader, monkeypatch, arm
):
    matrices = tuple(_changed_matrix(9, float(index)) for index in range(3))
    fake = reader(matrices=matrices)
    record = {}
    clock_calls = _install_clock(probe, monkeypatch, fake, record)
    result = probe._benchmark_pass(fake.cohort, arm, _Dispatch, record)
    assert type(result) is list and result == list(matrices)
    assert fake.events == [("acquire", arm, index) for index in range(3)]
    assert clock_calls == [100, 173]
    assert record["status"] == "complete"
    assert record["attempted_reads"] == record["completed_reads"] == 3
    assert record["elapsed_ns"] == 73
    fake.assert_released()
    _assert_primitives(record)
    _assert_primitives(result)


@pytest.mark.parametrize("arm", ["A", "B"])
@pytest.mark.parametrize("fail_index", [0, 1, 2])
@pytest.mark.parametrize("failure", ["acquire", "array", "validate"])
def test_failed_pass_retains_exact_partial_counts_and_primitive_matrices(
    probe,
    reader,
    monkeypatch,
    arm,
    fail_index,
    failure,
):
    matrices = tuple(_changed_matrix(9, float(index)) for index in range(3))
    fake = reader(matrices=matrices, failure=failure, fail_index=fail_index)
    record = {}
    clock_calls = _install_clock(probe, monkeypatch, fake, record)
    with pytest.raises(RuntimeError) as caught:
        probe._benchmark_pass(fake.cohort, arm, _Dispatch, record)
    assert clock_calls == [100, 173]
    assert record["status"] == "failed"
    assert record["attempted_reads"] == fail_index + 1
    assert record["completed_reads"] == fail_index
    assert record["elapsed_ns"] == 73
    assert fake.events == [("acquire", arm, index) for index in range(fail_index + 1)]
    partial = record["partial_matrices"]
    assert len(partial) == fail_index
    for expected, evidence in zip(matrices[:fail_index], partial, strict=True):
        assert evidence["values"] == list(expected)
        assert evidence["hex"] == [value.hex() for value in expected]
    _assert_primitives(record)
    fake.assert_released()
    if isinstance(caught.value, _NativeReadError):
        _record_native_error(probe, caught.value)
        fake.assert_released()


def _raise_chained_native_error(chain, errors, operation, *arguments):
    """Keep native aliases in clearable frame locals, not traceback-held closures."""
    try:
        operation(*arguments)
    except _NativeReadError as inner:
        outer = _NativeReadError("outer native acquisition/property/binding failed")
        errors.update(outer=outer, inner=inner)
        if chain == "cause":
            raise outer from inner
        assert chain == "context"
        raise outer
    raise AssertionError("the failing native operation unexpectedly succeeded")


def _assert_native_error_chain(errors, chain):
    outer, inner = errors["outer"], errors["inner"]
    assert outer is not inner
    assert str(outer) == "outer native acquisition/property/binding failed"
    assert str(inner).startswith("inner native ")
    assert outer.__context__ is inner
    if chain == "cause":
        assert outer.__cause__ is inner and outer.__suppress_context__ is True
    else:
        assert outer.__cause__ is None and outer.__suppress_context__ is False
    assert outer.__traceback__ is not None and inner.__traceback__ is not None


@pytest.fixture
def chained_reader(probe, monkeypatch):
    def install(*, failure, chain):
        references, errors = [], {}

        def watch(value):
            references.append(weakref.ref(value))
            return value

        class PartialWrapper:
            def __init__(self, raw):
                self.raw = raw

        def fail_acquisition():
            raw = watch(_Dispatch(0))
            _partial = watch(PartialWrapper(raw))
            raise _NativeReadError("inner native acquisition failed")

        def fail_property(raw):
            _partial = watch(PartialWrapper(raw))
            raise _NativeReadError("inner native property failed")

        class GeneratedTransform:
            def __init__(self, raw):
                self.raw = raw
                watch(self)
                if failure == "constructor":
                    raise _NativeReadError("inner native constructor failed")

            @property
            def ArrayData(self):
                assert failure == "property"
                return _raise_chained_native_error(
                    chain, errors, fail_property, self.raw
                )

        def acquire(include_presentation):
            assert include_presentation is True
            if failure == "acquire":
                return _raise_chained_native_error(chain, errors, fail_acquisition)
            return watch(_Dispatch(0))

        class Component:
            def GetTotalTransform(self, include_presentation):
                return acquire(include_presentation)

        def bound(raw, interface):
            assert interface == "IMathTransform" and isinstance(raw, _Dispatch)
            if failure == "constructor":
                return _raise_chained_native_error(
                    chain, errors, GeneratedTransform, raw
                )
            return GeneratedTransform(raw)

        def invoke(value, interface, member, *args):
            if (interface, member) == ("IComponent2", "GetTotalTransform"):
                assert isinstance(value, Component) and args == (True,)
                return acquire(args[0])
            assert (interface, member, args) == ("IMathTransform", "ArrayData", ())
            assert isinstance(value, _Dispatch) and failure == "property"
            return _raise_chained_native_error(chain, errors, fail_property, value)

        def assert_released():
            assert references and all(reference() is None for reference in references)

        monkeypatch.setattr(probe, "_bound", bound)
        monkeypatch.setattr(probe, "_com_invoke", invoke)
        return SimpleNamespace(
            cohort=[Component()],
            references=references,
            errors=errors,
            assert_released=assert_released,
        )

    return install


@pytest.mark.parametrize("chain", ["cause", "context"])
@pytest.mark.parametrize(
    ("arm", "failure"),
    [
        ("A", "constructor"),
        ("A", "property"),
        ("A", "acquire"),
        ("B", "property"),
        ("B", "acquire"),
    ],
)
def test_chained_failure_releases_nested_frame_aliases_before_pass_timer_stop(
    probe,
    chained_reader,
    monkeypatch,
    arm,
    failure,
    chain,
):
    fake = chained_reader(failure=failure, chain=chain)
    record, timer_edges = {}, []

    def clock():
        assert record == {}, "failure evidence must remain outside the timed interval"
        if timer_edges:
            # These holders deliberately keep both exceptions and tracebacks
            # alive. The partial wrapper exists only in a cause/context frame,
            # so clearing the outer traceback alone cannot satisfy this edge.
            _assert_native_error_chain(fake.errors, chain)
            assert len(fake.references) >= 2
            fake.assert_released()
        else:
            assert fake.references == [] and fake.errors == {}
        timer_edges.append(100 + 73 * len(timer_edges))
        return timer_edges[-1]

    monkeypatch.setattr(probe, "time", SimpleNamespace(perf_counter_ns=clock))
    with pytest.raises(_NativeReadError) as caught:
        probe._benchmark_pass(fake.cohort, arm, _Dispatch, record)
    assert caught.value is fake.errors["outer"]
    _assert_native_error_chain(fake.errors, chain)
    assert timer_edges == [100, 173]
    assert record == {
        "status": "failed",
        "attempted_reads": 1,
        "completed_reads": 0,
        "elapsed_ns": 73,
        "partial_matrices": [],
    }
    evidence = _record_native_error(probe, caught.value)["errors"][0]
    assert str(fake.errors["inner"]) in evidence["traceback"]
    fake.assert_released()
    _assert_primitives(record)


def test_exception_frame_disposal_handles_cyclic_shared_graph_without_rewriting_errors(
    probe,
):
    references = []

    def capture(message):
        def fail():
            raw = _Dispatch(0)
            references.append(weakref.ref(raw))
            raise _NativeReadError(message)

        try:
            fail()
        except _NativeReadError as error:
            return error

    outer = capture("outer graph error")
    cause = capture("cause graph error")
    context = capture("context graph error")
    outer.__cause__, outer.__context__ = cause, context
    cause.__context__ = outer
    context.__cause__, context.__context__ = cause, outer
    errors = (outer, cause, context)
    snapshots = []
    for error in errors:
        frames = []
        node = error.__traceback__
        while node is not None:
            frames.append(
                (node, node.tb_next, node.tb_frame, node.tb_lineno, node.tb_lasti)
            )
            node = node.tb_next
        snapshots.append(
            (
                error,
                error.args,
                str(error),
                error.__cause__,
                error.__context__,
                error.__suppress_context__,
                error.__traceback__,
                frames,
            )
        )
    assert all(reference() is not None for reference in references)

    probe._clear_exception_frames(outer)
    probe._clear_exception_frames(outer)  # Repeated disposal must also terminate.

    assert all(reference() is None for reference in references)
    for (
        error,
        args,
        message,
        saved_cause,
        saved_context,
        suppressed,
        tb,
        frames,
    ) in snapshots:
        assert any(error is original for original in errors)
        assert error.args == args and str(error) == message
        assert error.__cause__ is saved_cause and error.__context__ is saved_context
        assert error.__suppress_context__ is suppressed and error.__traceback__ is tb
        for node, next_node, frame, lineno, lasti in frames:
            assert node.tb_next is next_node and node.tb_frame is frame
            assert node.tb_lineno == lineno and node.tb_lasti == lasti


def test_matrix_comparison_records_complete_value_and_hex_equality(probe):
    evidence = {}
    matrices = [_MATRIX, _changed_matrix(15, 2.0)]
    assert (
        probe._benchmark_compare_matrices(
            matrices, deepcopy(matrices), ["one", "two"], evidence
        )
        is None
    )
    assert evidence["compared_components"] == 2
    assert evidence["values_equal"] is True and evidence["hex_equal"] is True
    assert evidence["mismatches"] == []
    _assert_primitives(evidence)


@pytest.mark.parametrize("index", range(16))
def test_matrix_comparison_rejects_drift_in_every_entry(probe, index):
    evidence = {}
    actual = [_changed_matrix(index, _MATRIX[index] + 0.125)]
    with pytest.raises(RuntimeError):
        probe._benchmark_compare_matrices([_MATRIX], actual, ["one"], evidence)
    assert evidence["values_equal"] is False
    assert evidence["hex_equal"] is False and evidence["mismatches"]
    _assert_primitives(evidence)


@pytest.mark.parametrize("index", [1, 15])
def test_matrix_comparison_rejects_signedzero_despite_numeric_equality(probe, index):
    evidence = {}
    actual = [_changed_matrix(index, -0.0)]
    assert actual == [_MATRIX]
    with pytest.raises(RuntimeError):
        probe._benchmark_compare_matrices([_MATRIX], actual, ["one"], evidence)
    assert evidence["values_equal"] is True
    assert evidence["hex_equal"] is False and evidence["mismatches"]
    _assert_primitives(evidence)


@pytest.mark.parametrize(
    ("reference", "actual", "names"),
    [
        ([_MATRIX, _MATRIX], [_MATRIX], ["one", "two"]),
        ([_MATRIX], [_MATRIX, _MATRIX], ["one", "two"]),
        ([_MATRIX], [_MATRIX], ["one", "two"]),
    ],
)
def test_matrix_comparison_refuses_incomplete_inventory(
    probe, reference, actual, names
):
    with pytest.raises(RuntimeError):
        probe._benchmark_compare_matrices(reference, actual, names, {})


@pytest.mark.parametrize("matrix", [_MATRIX[:15], (*_MATRIX, 0.0)])
def test_matrix_comparison_refuses_incomplete_or_oversized_rows(probe, matrix):
    with pytest.raises(RuntimeError):
        probe._benchmark_compare_matrices([matrix], [matrix], ["one"], {})


def test_rounds_keep_same_cohort_in_six_balanced_full_inventory_pairs(
    probe, monkeypatch
):
    cohort = [object(), object()]
    reference = [_MATRIX, _changed_matrix(9, 2.0)]
    calls = []

    def run_pass(components, arm, dispatch_type, record):
        assert components is cohort and dispatch_type is _Dispatch
        calls.append(arm)
        record.update(
            status="complete",
            attempted_reads=2,
            completed_reads=2,
            elapsed_ns=100 if arm == "A" else 70,
        )
        return list(reference)

    monkeypatch.setattr(probe, "_benchmark_pass", run_pass)
    benchmark = probe._benchmark_report()
    probe._benchmark_rounds(cohort, ["one", "two"], _Dispatch, reference, benchmark)
    assert calls == list("ABBAABBAABBA")
    assert len(benchmark["pairs"]) == 6
    for pair, order in zip(benchmark["pairs"], ("AB", "BA") * 3, strict=True):
        assert pair["order"] == order and pair["status"] == "complete"
        for arm in "AB":
            assert pair["arms"][arm]["completed_reads"] == 2
            assert pair["arms"][arm]["attempted_reads"] == 2
        for comparison in ("pair", "A_against_control", "B_against_control"):
            assert pair[comparison]["values_equal"] is True
            assert pair[comparison]["hex_equal"] is True
    assert benchmark["summary"]["all"]["pairs"] == 6
    assert benchmark["summary"]["AB"]["pairs"] == 3
    assert benchmark["summary"]["BA"]["pairs"] == 3
    _assert_primitives(benchmark)


@pytest.mark.parametrize("drift", [1.0, -0.0])
def test_rounds_reject_common_mode_drift_against_positive_control_reference(
    probe, monkeypatch, drift
):
    cohort = [object()]
    reference = [_MATRIX]
    drifted = [_changed_matrix(15, drift)]
    calls = []

    def run_pass(components, arm, dispatch_type, record):
        assert components is cohort and dispatch_type is _Dispatch
        calls.append(arm)
        record.update(
            status="complete", attempted_reads=1, completed_reads=1, elapsed_ns=10
        )
        return list(drifted)

    monkeypatch.setattr(probe, "_benchmark_pass", run_pass)
    benchmark = probe._benchmark_report()
    with pytest.raises(RuntimeError):
        probe._benchmark_rounds(cohort, ["one"], _Dispatch, reference, benchmark)
    assert calls == ["A", "B"]
    assert len(benchmark["pairs"]) == 1
    pair = benchmark["pairs"][0]
    assert pair["status"] == "failed"
    assert pair["pair"]["values_equal"] is True
    assert pair["pair"]["hex_equal"] is True
    assert pair["A_against_control"]["mismatches"]
    _assert_primitives(benchmark)


def test_controls_read_each_component_in_a1_a2_b_a3_order(probe, monkeypatch):
    cohort = [object(), object()]
    reference = [_MATRIX, _changed_matrix(9, 2.0)]
    calls = []

    def read(component, arm, dispatch_type):
        assert dispatch_type is _Dispatch
        index = next(index for index, item in enumerate(cohort) if item is component)
        calls.append((index, arm))
        return reference[index]

    monkeypatch.setattr(probe, "_benchmark_read_matrix", read)
    benchmark = probe._benchmark_report()
    result = probe._benchmark_controls(
        cohort, ["one", "two"], _Dispatch, reference, benchmark
    )
    assert result == reference
    assert calls == [(index, arm) for index in range(2) for arm in "AABA"]
    controls = benchmark["controls"]
    assert controls["status"] == "complete"
    assert controls["completed_reads"] == {"A": 6, "B": 2}
    assert controls["attempted_reads"] == {"A": 6, "B": 2}
    _assert_primitives(benchmark)


@pytest.mark.parametrize("bad_read", range(4))
def test_controls_refuse_drift_from_reference_in_any_of_four_reads(
    probe, monkeypatch, bad_read
):
    reads = []

    def read(_component, arm, _dispatch_type):
        index = len(reads)
        reads.append(arm)
        return _changed_matrix(15, 1.0) if index == bad_read else _MATRIX

    monkeypatch.setattr(probe, "_benchmark_read_matrix", read)
    benchmark = probe._benchmark_report()
    with pytest.raises(RuntimeError):
        probe._benchmark_controls([object()], ["one"], _Dispatch, [_MATRIX], benchmark)
    assert benchmark["controls"]["components"][0]["status"] == "failed"
    _assert_primitives(benchmark)


@pytest.fixture
def document_state(probe, tmp_path):
    source = str(tmp_path / "paper-drive.SLDASM")
    source_key = probe._path_key(source)
    state = {
        "root_path": source,
        "root_title": "paper-drive.SLDASM",
        "active_document": {
            "path": source,
            "path_key": source_key,
            "title": "paper-drive.SLDASM",
        },
        "opened_read_only": True,
        "needs_rebuild": 0,
        "save_flag": False,
        "model_is_exploded": False,
        "extension_is_exploded": {"is_exploded": False, "view_name": ""},
        "active_exploded_view_owner": None,
        "enable_presentation": False,
        "active_configuration": "Default",
        "selection_count": 0,
    }
    return state, source_key


def test_document_state_projects_complete_collapsed_default_primitives(
    probe, document_state
):
    state, source_key = document_state
    result = probe._benchmark_document_state(state, source_key)
    assert all(key in result for key in _DOCUMENT_FIELDS)
    for key in _DOCUMENT_FIELDS:
        assert result[key] == state[key]
    _assert_primitives(result)


@pytest.mark.parametrize("field", _DOCUMENT_FIELDS)
def test_document_state_refuses_missing_required_reads(probe, document_state, field):
    state, source_key = document_state
    del state[field]
    with pytest.raises(RuntimeError):
        probe._benchmark_document_state(state, source_key)


@pytest.mark.parametrize("indicator", ["model", "extension"])
@pytest.mark.parametrize("value", [True, None, 0, (False,), "False"])
def test_document_state_requires_both_scalar_false_explode_indicators(
    probe, document_state, indicator, value
):
    state, source_key = document_state
    if indicator == "model":
        state["model_is_exploded"] = value
    else:
        state["extension_is_exploded"]["is_exploded"] = value
    with pytest.raises(RuntimeError):
        probe._benchmark_document_state(state, source_key)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("opened_read_only", False),
        ("needs_rebuild", 1),
        ("selection_count", 1),
        ("active_configuration", "Default Simplified"),
        ("active_document", None),
        ("extension_is_exploded", None),
        ("save_flag", None),
        ("enable_presentation", None),
        ("needs_rebuild", False),
        ("selection_count", 0.0),
    ],
)
def test_document_state_refuses_invalid_identity_configuration_or_cleanliness(
    probe, document_state, field, value
):
    state, source_key = document_state
    state[field] = value
    with pytest.raises(RuntimeError):
        probe._benchmark_document_state(state, source_key)


@pytest.mark.parametrize(
    ("container", "field"),
    [
        ("extension_is_exploded", "is_exploded"),
        ("extension_is_exploded", "view_name"),
        ("active_document", "path"),
        ("active_document", "title"),
    ],
)
def test_document_state_refuses_missing_nested_required_reads(
    probe, document_state, container, field
):
    state, source_key = document_state
    del state[container][field]
    with pytest.raises((RuntimeError, KeyError)):
        probe._benchmark_document_state(state, source_key)


def test_document_state_refuses_foreign_root_or_active_document(probe, document_state):
    state, source_key = document_state
    foreign = source_key + ".foreign.SLDASM"
    for field in ("root_path", "active_document"):
        changed = deepcopy(state)
        if field == "root_path":
            changed[field] = foreign
        else:
            changed[field]["path_key"] = foreign
        with pytest.raises(RuntimeError):
            probe._benchmark_document_state(changed, source_key)


def test_state_comparison_accepts_equal_fully_read_recursive_primitives(
    probe, document_state
):
    state, _source_key = document_state
    before = {
        "document": state,
        "components": [{"suppression": 2, "presentation_transform": None}],
    }
    evidence = {}
    assert probe._benchmark_require_equal(before, deepcopy(before), evidence) is None
    assert evidence["equal"] is True
    _assert_primitives(evidence)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("save_flag", True),
        ("enable_presentation", True),
        ("model_is_exploded", True),
        ("extension_is_exploded", {"is_exploded": True, "view_name": "ExplView1"}),
        ("active_exploded_view_owner", "Default"),
        ("selection_count", 1),
        ("needs_rebuild", 1),
        ("opened_read_only", False),
        ("active_configuration", "Default Simplified"),
        ("root_title", "other.SLDASM"),
    ],
)
def test_state_comparison_refuses_document_drift(probe, document_state, field, value):
    before, _source_key = document_state
    after = deepcopy(before)
    after[field] = value
    evidence = {}
    with pytest.raises(RuntimeError):
        probe._benchmark_require_equal(before, after, evidence)
    assert evidence["equal"] is False
    assert evidence["before"] == before and evidence["after"] == after
    _assert_primitives(evidence)


@pytest.mark.parametrize(
    ("field", "before_value", "after_value"),
    [
        ("suppression", 2, 0),
        ("referenced_configuration", "Default", "Other"),
        ("reference_path", "part.SLDPRT", "foreign.SLDPRT"),
        ("presentation_transform", None, {"values": list(_MATRIX)}),
        ("transform", list(_MATRIX), list(_changed_matrix(15, -0.0))),
        (
            "total_transform_with_presentation",
            list(_MATRIX),
            list(_changed_matrix(9, 2.0)),
        ),
        ("visible", 1, 0),
        ("fixed", True, False),
    ],
)
def test_state_comparison_refuses_component_suppression_presentation_and_matrix_drift(
    probe,
    field,
    before_value,
    after_value,
):
    before = {"components": [{"name": "one", field: before_value}]}
    after = {"components": [{"name": "one", field: after_value}]}
    evidence = {}
    with pytest.raises(RuntimeError):
        probe._benchmark_require_equal(before, after, evidence)
    assert evidence["equal"] is False
    assert evidence["before"] == before and evidence["after"] == after
    _assert_primitives(evidence)


@pytest.mark.parametrize(("before", "after"), [(False, 0), (0, 0.0), (0.0, -0.0)])
def test_state_comparison_is_type_and_float_hex_exact(probe, before, after):
    evidence = {}
    with pytest.raises(RuntimeError):
        probe._benchmark_require_equal(
            {"nested": [before]}, {"nested": [after]}, evidence
        )
    assert evidence["equal"] is False
    _assert_primitives(evidence)


def test_observation_refuses_new_required_native_read_failure_before_comparing_states(
    probe,
    monkeypatch,
    document_state,
):
    state, source_key = document_state
    report = {"errors": [], "raw_matrix_benchmark": probe._benchmark_report()}

    def read_state(_model, _extension, _assembly, _app, target_report, location):
        try:
            raise _NativeReadError("native save flag read failed")
        except _NativeReadError as error:
            probe._error(target_report, f"{location}.save_flag", error)
        result = deepcopy(state)
        result["save_flag"] = None
        return result

    monkeypatch.setattr(probe, "_state", read_state)
    with pytest.raises(RuntimeError):
        probe._benchmark_observe(
            object(), object(), object(), object(), source_key, report, "matrix.after"
        )
    assert len(report["errors"]) == 1
    assert "native save flag read failed" in report["errors"][0]["traceback"]
    observed = report["raw_matrix_benchmark"]["document_observations"]["matrix.after"]
    assert observed["save_flag"] is None
    assert observed["root_path"] == state["root_path"]
    _assert_primitives(report)


@pytest.fixture
def component_state(probe, monkeypatch, tmp_path):
    path = str(tmp_path / "part.SLDPRT")
    references = []

    def watch(value):
        references.append(weakref.ref(value))
        return value

    class LoadedModel:
        def GetPathName(self):
            return path

    class Transform:
        def __init__(self, values):
            self.ArrayData = values

    class Component:
        Name2 = "part-1"
        ReferencedConfiguration = "Default"
        Visible = 1
        suppression = 2
        presentation = None
        operational = _MATRIX
        total_without_presentation = _MATRIX
        total_with_presentation = _MATRIX

        def GetModelDoc2(self):
            return watch(LoadedModel())

        def GetPathName(self):
            return path

        def GetSuppression2(self):
            return self.suppression

        def IsFixed(self):
            return True

        @property
        def Transform2(self):
            return watch(Transform(self.operational))

        def GetTotalTransform(self, include_presentation):
            values = (
                self.total_with_presentation
                if include_presentation
                else self.total_without_presentation
            )
            return watch(Transform(values))

        @property
        def PresentationTransform(self):
            if self.presentation is None:
                return None
            return watch(Transform(self.presentation))

    def bound(value, interface):
        assert interface in ("IMathTransform", "IModelDoc2")
        assert value is not None
        return value

    monkeypatch.setattr(probe, "_bound", bound)
    return SimpleNamespace(
        component=Component(),
        allowed_parts={probe._path_key(path)},
        references=references,
        path=path,
    )


def test_component_state_captures_suppression_identity_and_legitimate_absent_presentation(
    probe,
    component_state,
):
    fake = component_state
    row = probe._benchmark_component_state(fake.component, fake.allowed_parts)
    assert row["name"] == "part-1"
    assert row["reference_path"] == fake.path
    assert row["referenced_configuration"] == "Default"
    assert row["suppression"] == 2 and row["fixed"] is True and row["visible"] == 1
    assert row["loaded_model"]["authenticated"] is True
    assert row["loaded_model"]["path_key"] in fake.allowed_parts
    assert row["presentation_transform"] == {
        "status": "absent",
        "values": None,
        "hex": None,
    }
    for field in (
        "transform",
        "total_transform_without_presentation",
        "total_transform_with_presentation",
    ):
        assert row[field]["values"] == list(_MATRIX)
        assert row[field]["hex"] == [value.hex() for value in _MATRIX]
    assert fake.references and all(reference() is None for reference in fake.references)
    _assert_primitives(row)


@pytest.mark.parametrize(
    ("attribute", "value", "field"),
    [
        ("suppression", 0, "suppression"),
        ("ReferencedConfiguration", "Other", "referenced_configuration"),
        ("presentation", _MATRIX, "presentation_transform"),
        ("operational", _changed_matrix(15, -0.0), "transform"),
        (
            "total_without_presentation",
            _changed_matrix(9, 2.0),
            "total_transform_without_presentation",
        ),
        (
            "total_with_presentation",
            _changed_matrix(9, 2.0),
            "total_transform_with_presentation",
        ),
    ],
)
def test_captured_component_drift_is_refused_after_full_before_and_after_reads(
    probe,
    component_state,
    attribute,
    value,
    field,
):
    fake = component_state
    before = probe._benchmark_component_state(fake.component, fake.allowed_parts)
    setattr(fake.component, attribute, value)
    after = probe._benchmark_component_state(fake.component, fake.allowed_parts)
    evidence = {}
    with pytest.raises(RuntimeError, match="state changed"):
        probe._benchmark_require_equal([before], [after], evidence)
    assert evidence["equal"] is False
    assert evidence["before"][0][field] == before[field]
    assert evidence["after"][0][field] == after[field]
    assert all(reference() is None for reference in fake.references)
    _assert_primitives(evidence)


@pytest.fixture
def full_benchmark(probe, monkeypatch, tmp_path):
    """Keep admission/state/ownership real; replace only native and file boundaries."""

    def install(
        *, acquisition_failure=None, chain="cause", poststate_failure="document"
    ):
        source = str(tmp_path / "paper-drive.SLDASM")
        parts = [str(tmp_path / f"part-{index}.SLDPRT") for index in range(43)]
        allowed_parts = {probe._path_key(path) for path in parts}
        report = {
            "errors": [],
            "historical_digest": {"historical_digest_reproduced": True},
            "authentication": {"complete": True},
            "files_before": {f"authenticated-file-{index}": {} for index in range(91)},
            "raw_matrix_benchmark": probe._benchmark_report(),
        }
        benchmark = report["raw_matrix_benchmark"]
        state = SimpleNamespace(phase="default", save_reads=0, poststate_started=False)
        cohort_references = {
            phase: {"dispatches": [], "wrappers": []} for phase in ("default", "run")
        }
        transient_references, reads, timer_edges, events = [], [], [], []
        acquisition_errors, poststate_errors = {}, {}

        def watch(value, references=transient_references):
            references.append(weakref.ref(value))
            return value

        def assert_transients_released():
            assert transient_references
            assert all(reference() is None for reference in transient_references)

        def assert_cohort_released():
            for phase in cohort_references.values():
                for references in phase.values():
                    assert len(references) == 145
                    assert all(reference() is None for reference in references)
            assert_transients_released()

        class ComponentDispatch(_Dispatch):
            pass

        class TransformDispatch(_Dispatch):
            pass

        class GeneratedTransform:
            def __init__(self, raw):
                self.raw = raw

            @property
            def ArrayData(self):
                return list(_MATRIX)

        def transform(index):
            return watch(TransformDispatch(index))

        def fail_acquisition(component):
            # Only this inner traceback owns the partial wrapper, and it also
            # retains a cohort member after all direct acquisition aliases go.
            raw = transform(component.index)
            _partial = watch(GeneratedTransform(raw))
            raise _NativeReadError("inner native measured acquisition failed")

        def acquire(component, arm, include_presentation):
            assert type(include_presentation) is bool
            in_benchmark = (
                state.phase == "run"
                and not state.poststate_started
                and benchmark["controls"]["status"] != "not_started"
            )
            if in_benchmark:
                assert include_presentation is True
                reads.append((arm, component.index))
                if (
                    acquisition_failure == arm
                    and benchmark["pairs"]
                    and component.index == 1
                    and not acquisition_errors
                ):
                    return _raise_chained_native_error(
                        chain, acquisition_errors, fail_acquisition, component
                    )
            return transform(component.index)

        def fail_poststate(component):
            raw = component._oleobj_
            _partial = watch(GeneratedTransform(raw))
            raise _NativeReadError("inner native poststate visibility unreadable")

        class LoadedModel:
            _interface = "IModelDoc2"

            def __init__(self, index):
                self.path = parts[index % len(parts)]

            def GetPathName(self):
                return self.path

        class GeneratedComponent:
            ReferencedConfiguration = "Default"

            def __init__(self, raw):
                self._oleobj_ = raw
                self.index = raw.index

            @property
            def Name2(self):
                return f"part-{self.index}"

            @property
            def Visible(self):
                if (
                    state.poststate_started
                    and poststate_failure == "component"
                    and self.index == 1
                ):
                    return _raise_chained_native_error(
                        chain, poststate_errors, fail_poststate, self
                    )
                return 1

            def GetModelDoc2(self):
                return watch(LoadedModel(self.index))

            def GetPathName(self):
                return parts[self.index % len(parts)]

            def GetSuppression2(self):
                return 2

            def IsFixed(self):
                return True

            @property
            def Transform2(self):
                return transform(self.index)

            def GetTotalTransform(self, include_presentation):
                return acquire(self, "A", include_presentation)

            @property
            def PresentationTransform(self):
                return None

        class Configuration:
            _interface = "IConfiguration"
            Name = "Default"

            def GetDisplayStates(self):
                return ["Display State-1"]

        class Selection:
            _interface = "ISelectionMgr"

            def GetSelectedObjectCount2(self, mark):
                assert mark == -1
                return 0

        class Model:
            _interface = "IModelDoc2"
            ConfigurationManager = SimpleNamespace(
                _interface="IConfigurationManager", ActiveConfiguration=Configuration()
            )
            SelectionManager = Selection()

            def GetPathName(self):
                return source

            def GetTitle(self):
                return "paper-drive.SLDASM"

            def IsOpenedReadOnly(self):
                return True

            def GetSaveFlag(self):
                state.save_reads += 1
                if state.save_reads == 3:
                    state.poststate_started = True
                    events.append("poststate")
                    assert_transients_released()
                    for references in cohort_references["run"].values():
                        assert len(references) == 145
                        assert all(reference() is not None for reference in references)
                    if acquisition_errors:
                        _assert_native_error_chain(acquisition_errors, chain)
                    if poststate_failure == "document":
                        raise _NativeReadError("native poststate save flag unreadable")
                return False

            def IsExploded(self):
                return False

        class Extension:
            NeedsRebuild2 = 0

            def IsExploded(self):
                return False, ""

        class Assembly:
            EnablePresentation = False

            def GetComponents(self, top_level_only):
                assert top_level_only is True
                events.append(f"enumerate.{state.phase}")
                return tuple(
                    watch(
                        ComponentDispatch(index),
                        cohort_references[state.phase]["dispatches"],
                    )
                    for index in range(145)
                )

        def early_bound(value, interface):
            if interface == "IComponent2":
                assert isinstance(value, ComponentDispatch)
                return watch(
                    GeneratedComponent(value),
                    cohort_references[state.phase]["wrappers"],
                )
            if interface == "IMathTransform":
                assert isinstance(value, TransformDispatch)
                return watch(GeneratedTransform(value))
            assert getattr(value, "_interface", None) == interface
            return value

        def invoke(value, interface, member, *args):
            if (interface, member) == ("IComponent2", "GetTotalTransform"):
                assert isinstance(value, GeneratedComponent) and args == (True,)
                return acquire(value, "B", args[0])
            assert (interface, member, args) == ("IMathTransform", "ArrayData", ())
            assert isinstance(value, TransformDispatch)
            return list(_MATRIX)

        headers = {
            ("IComponent2", "GetTotalTransform"): (77, 0, 1, (9, 0), ((11, 1),)),
            ("IMathTransform", "ArrayData"): (3, 0, 2, (12, 0), ()),
        }

        def clock():
            assert_transients_released()
            for references in cohort_references["run"].values():
                assert len(references) == 145
                assert all(reference() is not None for reference in references)
            if acquisition_errors:
                _assert_native_error_chain(acquisition_errors, chain)
            timer_edges.append(100 * (len(timer_edges) + 1))
            return timer_edges[-1]

        # Neither import may fall through to an installed package or pywin32.
        pythoncom = ModuleType("pythoncom")
        pythoncom.__file__ = str(tmp_path / "fake-pythoncom.pyd")
        pythoncom.IID_IDispatch = object()
        pythoncom.TypeIIDs = {pythoncom.IID_IDispatch: _Dispatch}
        package = ModuleType("solidworks_mcp")
        package.__path__ = []
        adapters = ModuleType("solidworks_mcp.adapters")
        adapters.__path__ = []
        type_info = ModuleType("solidworks_mcp.adapters.sw_type_info")
        type_info.__file__ = str(tmp_path / "fake-sdk" / "adapters" / "sw_type_info.py")
        type_info.is_early_bound = lambda value, interface: (
            interface == "IComponent2" and isinstance(value, GeneratedComponent)
        )
        package.adapters = adapters
        adapters.sw_type_info = type_info
        for name, module in (
            ("pythoncom", pythoncom),
            ("solidworks_mcp", package),
            ("solidworks_mcp.adapters", adapters),
            ("solidworks_mcp.adapters.sw_type_info", type_info),
        ):
            monkeypatch.setitem(sys.modules, name, module)
        com = sys.modules["_com"]
        monkeypatch.setattr(
            com, "__file__", str(tmp_path / "fake-_com.py"), raising=False
        )
        early_bound.__module__ = "_com"
        monkeypatch.setattr(probe, "_early_bound", early_bound)
        monkeypatch.setattr(probe, "_com_invoke", invoke)
        monkeypatch.setattr(
            probe, "_com_header", lambda interface, member: headers[interface, member]
        )
        monkeypatch.setattr(probe, "time", SimpleNamespace(perf_counter_ns=clock))
        monkeypatch.setattr(probe, "__file__", str(tmp_path / "fake-probe.py"))

        def package_version(name):
            assert name == "pywin32"
            return "offline-fake-pywin32"

        monkeypatch.setattr(probe, "metadata", SimpleNamespace(version=package_version))
        source_paths = {
            str(Path(probe.__file__).resolve()),
            str(Path(com.__file__).resolve()),
            str(Path(type_info.__file__).resolve()),
            str(
                Path(type_info.__file__).resolve().parent
                / "_generated/sldworks_2026.py"
            ),
        }
        source_reads = []

        class FakeSourcePath(type(Path())):
            def read_bytes(self):
                assert str(self) in source_paths
                source_reads.append(str(self))
                return b"offline fake source identity\n"

        monkeypatch.setattr(probe, "Path", FakeSourcePath)
        model, extension, assembly = Model(), Extension(), Assembly()
        app = SimpleNamespace(ActiveDoc=model)
        source_key = probe._path_key(source)

        def capture_default():
            after = probe._state(
                model, extension, assembly, app, report, "default.after"
            )
            instances = []
            for raw in assembly.GetComponents(True):
                component = probe._bound(raw, "IComponent2")
                instances.append(
                    probe._benchmark_component_state(component, allowed_parts)
                )
            return {"after": after, "components": {"instances": instances}}

        default = capture_default()
        assert (
            len(allowed_parts) == 43 and len(default["components"]["instances"]) == 145
        )
        assert report["errors"] == []
        assert_transients_released()
        for references in cohort_references["default"].values():
            assert len(references) == 145 and all(
                reference() is None for reference in references
            )
        state.phase = "run"
        return SimpleNamespace(
            arguments=(
                model,
                extension,
                assembly,
                app,
                source_key,
                allowed_parts,
                default,
                report,
            ),
            report=report,
            benchmark=benchmark,
            state=state,
            reads=reads,
            timer_edges=timer_edges,
            events=events,
            source_reads=source_reads,
            source_paths=source_paths,
            acquisition_errors=acquisition_errors,
            poststate_errors=poststate_errors,
            assert_cohort_released=assert_cohort_released,
        )

    return install


def _assert_full_runner_failure_boundary(fake):
    # This is the consumer's boundary before any child activation or owned-doc
    # cleanup. Keep pytest's primary exception holder alive across this check.
    fake.assert_cohort_released()
    assert fake.state.save_reads == 3 and fake.state.poststate_started is True
    assert fake.events == ["enumerate.default", "enumerate.run", "poststate"]
    assert set(fake.source_reads) == fake.source_paths and len(fake.source_reads) == 4
    benchmark = fake.benchmark
    assert benchmark["status"] == "failed"
    assert benchmark["component_handles_released_before_child_activation"] is True
    assert benchmark["generated_component_dispatch_receipts"] == 145
    assert benchmark["component_order"] == [f"part-{index}" for index in range(145)]
    assert benchmark["default_document_matches"]["equal"] is True
    assert len(benchmark["default_component_matches"]) == 145
    assert all(
        item["equal"] is True
        for item in benchmark["default_component_matches"].values()
    )
    assert benchmark["controls"]["status"] == "complete"
    assert benchmark["controls"]["completed_reads"] == {"A": 435, "B": 145}
    assert benchmark["controls"]["attempted_reads"] == {"A": 435, "B": 145}
    assert benchmark["source_identity"]["pywin32_version"] == "offline-fake-pywin32"
    assert set(benchmark["source_identity"]["files"]) == {
        "probe",
        "com_helpers",
        "binding_helpers",
        "generated_wrapper",
    }
    assert len(benchmark["generated_headers"]) == 2
    assert benchmark["presentation_coverage"]["true_false_equal_count"] == 145
    _assert_primitives(fake.report)


@pytest.mark.parametrize(("arm", "chain"), [("A", "cause"), ("B", "context")])
def test_full_runner_preserves_primary_chain_when_required_poststate_is_unreadable(
    probe,
    full_benchmark,
    arm,
    chain,
):
    fake = full_benchmark(acquisition_failure=arm, chain=chain)
    with pytest.raises(_NativeReadError) as caught:
        probe._run_matrix_benchmark(*fake.arguments)
    assert caught.value is fake.acquisition_errors["outer"]
    _assert_native_error_chain(fake.acquisition_errors, chain)
    _assert_full_runner_failure_boundary(fake)

    controls = [(label, index) for index in range(145) for label in "AABA"]
    measured = [("A", index) for index in range(145)] if arm == "B" else []
    measured.extend((arm, index) for index in range(2))
    assert fake.reads == controls + measured
    assert len(fake.timer_edges) == (4 if arm == "B" else 2)
    assert len(fake.benchmark["pairs"]) == 1
    pair = fake.benchmark["pairs"][0]
    assert pair["status"] == "failed" and pair["order"] == "AB"
    assert pair["arms"][arm]["attempted_reads"] == 2
    assert pair["arms"][arm]["completed_reads"] == 1
    assert pair["arms"][arm]["partial_matrices"] == [
        {
            "values": list(_MATRIX),
            "hex": [value.hex() for value in _MATRIX],
        }
    ]
    assert fake.benchmark["measured_attempted_reads"] == (
        {"A": 145, "B": 2} if arm == "B" else {"A": 2, "B": 0}
    )
    assert fake.benchmark["measured_completed_reads"] == (
        {"A": 145, "B": 1} if arm == "B" else {"A": 1, "B": 0}
    )
    errors = {error["location"]: error for error in fake.report["errors"]}
    assert set(errors) == {
        "raw_matrix_benchmark",
        "benchmark.after.save_flag",
        "raw_matrix_benchmark.post_state",
    }
    assert all(error["required"] is True for error in errors.values())
    primary = errors["raw_matrix_benchmark"]
    assert primary["message"] == str(caught.value)
    assert str(fake.acquisition_errors["inner"]) in primary["traceback"]
    assert (
        errors["benchmark.after.save_flag"]["message"]
        == "native poststate save flag unreadable"
    )
    assert (
        errors["raw_matrix_benchmark.post_state"]["message"]
        == "benchmark required state read failed"
    )
    observed = fake.benchmark["document_observations"]["benchmark.after"]
    assert (
        observed["save_flag"] is None and observed["read_errors"][0]["required"] is True
    )
    assert "state_after" not in fake.benchmark
    fake.assert_cohort_released()


@pytest.mark.parametrize("poststate_failure", ["document", "component"])
@pytest.mark.parametrize("chain", ["cause", "context"])
def test_full_runner_raises_unreadable_poststate_after_successful_real_controls_and_rounds(
    probe,
    full_benchmark,
    poststate_failure,
    chain,
):
    fake = full_benchmark(chain=chain, poststate_failure=poststate_failure)
    with pytest.raises(RuntimeError) as caught:
        probe._run_matrix_benchmark(*fake.arguments)
    assert fake.acquisition_errors == {}
    if poststate_failure == "component":
        assert caught.value is fake.poststate_errors["outer"]
        _assert_native_error_chain(fake.poststate_errors, chain)
    else:
        assert type(caught.value) is RuntimeError
        assert str(caught.value) == "benchmark required state read failed"
    _assert_full_runner_failure_boundary(fake)
    controls = [(label, index) for index in range(145) for label in "AABA"]
    measured = [
        (arm, index)
        for order in ("AB", "BA") * 3
        for arm in order
        for index in range(145)
    ]
    assert fake.reads == controls + measured
    assert len(fake.timer_edges) == 24
    assert len(fake.benchmark["pairs"]) == 6
    assert all(pair["status"] == "complete" for pair in fake.benchmark["pairs"])
    assert fake.benchmark["summary"]["all"]["pairs"] == 6
    assert fake.benchmark["measured_attempted_reads"] == {"A": 870, "B": 870}
    assert fake.benchmark["measured_completed_reads"] == {"A": 870, "B": 870}
    errors = {error["location"]: error for error in fake.report["errors"]}
    expected_locations = {"raw_matrix_benchmark.post_state"}
    if poststate_failure == "document":
        expected_locations.add("benchmark.after.save_flag")
    assert set(errors) == expected_locations
    assert all(error["required"] is True for error in errors.values())
    poststate = errors["raw_matrix_benchmark.post_state"]
    assert poststate["type"] == type(caught.value).__name__
    assert poststate["message"] == str(caught.value)
    if poststate_failure == "component":
        assert str(fake.poststate_errors["inner"]) in poststate["traceback"]
        assert len(fake.benchmark["state_after"]["components"]) == 1
    else:
        assert (
            fake.benchmark["document_observations"]["benchmark.after"]["save_flag"]
            is None
        )
    fake.assert_cohort_released()


@pytest.fixture
def preserved_session(probe, monkeypatch, tmp_path):
    """Authenticate real temporary bytes without importing any native module."""
    worker = tmp_path / "worker"
    scripts = worker / "cad/scripts"
    scripts.mkdir(parents=True)
    monkeypatch.setattr(probe, "__file__", str(scripts / "_verify_pd_digest_probe.py"))
    assembly_dir = worker / "cad/out/sldasm"
    part_dir = worker / "cad/out/sldprt"
    assembly_dir.mkdir(parents=True)
    part_dir.mkdir(parents=True)
    source = assembly_dir / "pd-paper-drive.SLDASM"
    source.write_bytes(b"historical assembly fixture")
    root_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    monkeypatch.setattr(probe, "_ROOT_SHA256", root_hash)
    inputs = {}
    parts = []
    for index in range(43):
        part = part_dir / f"part-{index}.SLDPRT"
        part.write_bytes(f"historical part {index}".encode("ascii"))
        token = part.with_name(f".{part.stem}.execution")
        token.write_bytes(
            hashlib.sha256(part.read_bytes()).hexdigest().encode("ascii") + b"\r\n"
        )
        inputs[part.relative_to(worker).as_posix()] = "unused-native-recipe-digest"
        inputs[token.relative_to(worker).as_posix()] = hashlib.md5(
            token.read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest()
        parts.append(part)
    inputs.update({f"source-{index}": "source-digest" for index in range(207)})
    fixed = {
        ".pd-paper-drive.execution": (root_hash + "\r\n").encode("ascii"),
        ".pd-paper-drive.massprops.sha": (probe._MASS_TEXT + "\r\n").encode("ascii"),
        ".pd-paper-drive.inputs.json": json.dumps({"inputs": inputs}).encode("utf-8"),
        ".pd-paper-drive.dof.json": b'{"fixture": true}',
    }
    for name, data in fixed.items():
        (assembly_dir / name).write_bytes(data)
    for constant, name in (
        ("_MASS_BYTE_SHA256", ".pd-paper-drive.massprops.sha"),
        ("_LEDGER_SHA256", ".pd-paper-drive.inputs.json"),
        ("_DOF_SHA256", ".pd-paper-drive.dof.json"),
    ):
        monkeypatch.setattr(probe, constant, hashlib.sha256(fixed[name]).hexdigest())
    report_path = worker / "cad/out/reports/pd-paper-drive-digest-probe.json"
    events = []
    emitted = []
    hash_after = probe._hash_after

    def posthash(report):
        events.append("posthash")
        hash_after(report)

    def emit(data):
        events.append("emit")
        emitted.append(json.loads(data))

    monkeypatch.setattr(probe, "_hash_after", posthash)
    monkeypatch.setattr(probe, "_emit_report", emit)

    def checkpoint():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["probe_status"] == "not_started"
        assert report["outer_session"]["authentication"]["complete"] is True
        assert len(report["outer_session"]["files_before"]) == 91
        assert probe._OUTER_SESSION_ID == report["outer_session_id"]
        report["probe_status"] = "pending_outer_session"
        report.pop("outer_session")
        probe._write_report(report_path, report)
        events.append("probe_checkpoint")

    return SimpleNamespace(
        source=source,
        part=parts[0],
        report_path=report_path,
        checkpoint=checkpoint,
        events=events,
        emitted=emitted,
    )


def test_outer_session_authenticates_before_entry_and_emits_once_after_teardown(
    probe, preserved_session
):
    fake = preserved_session

    def session(build):
        assert build is _unexpected_native_boundary
        fake.events.append("connect")
        fake.checkpoint()
        fake.events.append("teardown")
        assert fake.emitted == []
        return 0

    assert probe.run_preserved_session(
        session, _unexpected_native_boundary, fake.source, fake.report_path
    ) == 0
    assert fake.events == ["connect", "probe_checkpoint", "teardown", "posthash", "emit"]
    assert len(fake.emitted) == 1
    report = fake.emitted[0]
    assert report == json.loads(fake.report_path.read_text(encoding="utf-8"))
    assert report["probe_status"] == report["outer_session"]["status"] == "complete"
    assert report["outer_session"]["preservation_complete"] is True
    assert len(report["outer_session"]["files_after"]) == 91
    assert probe._OUTER_SESSION_ID is None
    _assert_primitives(report)


@pytest.mark.parametrize("mutation", ["connect", "verification", "teardown"])
@pytest.mark.parametrize("return_code", [0, 7])
def test_outer_session_refuses_mutation_outside_the_inner_probe(
    probe, preserved_session, mutation, return_code
):
    fake = preserved_session

    def session(_build):
        # All phases occur after the real outer authentication checkpoint.
        if mutation == "connect":
            fake.part.write_bytes(b"changed by connection cleanup")
        fake.checkpoint()
        if mutation == "verification":
            fake.part.write_bytes(b"changed after helper's preservation boundary")
        fake.events.append("teardown")
        if mutation == "teardown":
            fake.part.write_bytes(b"changed by session teardown")
        return return_code

    assert probe.run_preserved_session(
        session, _unexpected_native_boundary, fake.source, fake.report_path
    ) == (return_code or 1)
    report = fake.emitted[0]
    assert len(fake.emitted) == 1
    assert report["probe_status"] == report["outer_session"]["status"] == "failed"
    outer = report["outer_session"]
    assert outer["session_return_code"] == return_code
    assert outer["preservation_complete"] is False
    assert outer["files_after"][str(fake.part)]["unchanged"] is False
    assert any(error["location"].startswith("preservation.") for error in outer["errors"])
    assert fake.events[-3:] == ["teardown", "posthash", "emit"]


@pytest.mark.parametrize("primary", [RuntimeError("session failed"), SystemExit(9)])
def test_outer_session_preserves_primary_exception_with_secondary_hash_failure(
    probe, preserved_session, primary
):
    fake = preserved_session

    def session(_build):
        fake.checkpoint()
        try:
            raise primary
        finally:
            fake.events.append("teardown")
            fake.part.write_bytes(b"teardown changed protected part")

    with pytest.raises(type(primary)) as caught:
        probe.run_preserved_session(
            session, _unexpected_native_boundary, fake.source, fake.report_path
        )
    assert caught.value is primary
    assert fake.emitted[0]["outer_session"]["preservation_complete"] is False
    assert fake.emitted[0]["probe_status"] == "failed"
    assert fake.events[-3:] == ["teardown", "posthash", "emit"]
    assert "preservation." in primary.__notes__[-1]
    assert probe._OUTER_SESSION_ID is None


def test_outer_authentication_failure_never_enters_session(probe, preserved_session):
    fake = preserved_session
    fake.part.write_bytes(b"not historical bytes")
    with pytest.raises(RuntimeError, match="native child authentication"):
        probe.run_preserved_session(
            _unexpected_native_boundary,
            _unexpected_native_boundary,
            fake.source,
            fake.report_path,
        )
    assert fake.emitted[0]["outer_session"]["session_entered"] is False
    assert fake.emitted[0]["probe_status"] == "failed"


@pytest.mark.parametrize("status", ["not_started", "complete"])
def test_outer_session_cannot_accept_stale_or_uncompleted_helper_report(
    probe, preserved_session, status
):
    fake = preserved_session

    def session(_build):
        report = json.loads(fake.report_path.read_text(encoding="utf-8"))
        report["probe_status"] = status
        if status == "complete":
            report["outer_session_id"] -= 1
        probe._write_report(fake.report_path, report)
        return 0

    assert probe.run_preserved_session(
        session, _unexpected_native_boundary, fake.source, fake.report_path
    ) == 1
    assert fake.emitted[0]["outer_session"]["status"] == "failed"
    assert any(
        error["location"] == "outer_session.required_probe_report"
        for error in fake.emitted[0]["outer_session"]["errors"]
    )


def test_inner_failure_does_not_emit_before_outer_posthash(probe, preserved_session):
    fake = preserved_session

    def session(_build):
        with pytest.raises(RuntimeError, match="ISldWorks dispatch was null"):
            asyncio.run(
                probe.inspect_saved_paper_drive(
                    SimpleNamespace(swApp=None), fake.source, fake.report_path
                )
            )
        assert fake.emitted == []
        fake.events.append("teardown")
        return 1

    assert probe.run_preserved_session(
        session, _unexpected_native_boundary, fake.source, fake.report_path
    ) == 1
    assert len(fake.emitted) == 1
    assert fake.emitted[0]["probe_status"] == "failed"
    assert fake.events == ["posthash", "teardown", "posthash", "emit"]


@pytest.mark.parametrize("channel", ["json", "log"])
@pytest.mark.parametrize("return_code", [0, 7])
def test_outer_publication_failure_cannot_turn_a_session_green(
    probe, preserved_session, monkeypatch, channel, return_code
):
    fake = preserved_session
    write_report = probe._write_report

    def session(_build):
        fake.checkpoint()
        fake.events.append("teardown")
        return return_code

    def write(path, report):
        if report.get("outer_session", {}).get("status") in ("complete", "failed"):
            raise OSError("final JSON publication failed")
        return write_report(path, report)

    def emit(_data):
        raise OSError("final task-log publication failed")

    if channel == "json":
        monkeypatch.setattr(probe, "_write_report", write)
    else:
        monkeypatch.setattr(probe, "_emit_report", emit)
    assert probe.run_preserved_session(
        session, _unexpected_native_boundary, fake.source, fake.report_path
    ) == (return_code or 1)
    if channel == "json":
        report = fake.emitted[0]
        assert report["probe_status"] == report["outer_session"]["status"] == "failed"
    else:
        report = json.loads(fake.report_path.read_text(encoding="utf-8"))
        assert report["probe_status"] == report["outer_session"]["status"] == "failed"


@pytest.mark.parametrize(
    ("suite", "names", "guarded"),
    [
        ("soundness", ["pd-paper-drive"], True),
        ("soundness", ["pd-paper-drive", "dt-drive-train"], True),
        ("soundness", ["dt-drive-train"], False),
        ("kinematics", ["pd-paper-drive"], False),
    ],
)
def test_verify_entrypoint_guards_only_sessions_containing_pd_soundness(
    monkeypatch, tmp_path, suite, names, guarded
):
    source = Path(__file__).with_name("verify.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    entrypoint = module.body[-1]
    assert isinstance(entrypoint, ast.If)
    args = SimpleNamespace(suite=suite, names=names, auto_repair=False)
    calls = []
    build = object()

    def run_build(actual_build):
        assert actual_build is build
        calls.append("ordinary")
        return 7

    def preserved(runner, actual_build, native_source, report_path):
        assert runner is run_build and actual_build is build
        assert native_source == tmp_path / "sldasm/pd-paper-drive.SLDASM"
        assert report_path == tmp_path / "reports/pd-paper-drive-digest-probe.json"
        calls.append("guarded")
        return 7

    helper = ModuleType("_verify_pd_digest_probe")
    helper.run_preserved_session = preserved
    monkeypatch.setitem(sys.modules, helper.__name__, helper)
    namespace = {
        "__name__": "__main__",
        "_parse_args": lambda: args,
        "_telemetry": SimpleNamespace(set_service=lambda _service: None),
        "sys": sys,
        "build": build,
        "run_build": run_build,
        "OUT_SLDASM": tmp_path / "sldasm",
        "REPORTS_DIR": tmp_path / "reports",
    }
    with pytest.raises(SystemExit) as caught:
        exec(
            compile(ast.Module(body=[entrypoint], type_ignores=[]), "verify.py", "exec"),
            namespace,
        )
    assert caught.value.code == 7
    assert calls == (["guarded"] if guarded else ["ordinary"])


@pytest.mark.parametrize("channel", ["json", "log"])
def test_outer_session_keeps_primary_system_exit_when_final_publication_fails(
    probe, preserved_session, monkeypatch, channel
):
    fake = preserved_session
    primary = SystemExit(11)
    write_report = probe._write_report

    def session(_build):
        fake.checkpoint()
        raise primary

    def write(path, report):
        if report.get("outer_session", {}).get("status") == "failed":
            raise OSError("secondary final JSON failure")
        return write_report(path, report)

    def emit(_data):
        raise OSError("secondary final task-log failure")

    if channel == "json":
        monkeypatch.setattr(probe, "_write_report", write)
    else:
        monkeypatch.setattr(probe, "_emit_report", emit)
    with pytest.raises(SystemExit) as caught:
        probe.run_preserved_session(
            session, _unexpected_native_boundary, fake.source, fake.report_path
        )
    assert caught.value is primary and caught.value.code == 11
    assert "publication" in primary.__notes__[-1]
    assert probe._OUTER_SESSION_ID is None


@pytest.mark.parametrize("code", [0, None, False, _IntSubclass(0)])
@pytest.mark.parametrize("secondary_failure", [None, "hash", "json", "log"])
def test_success_coded_system_exit_cannot_bypass_outer_failure(
    probe, preserved_session, monkeypatch, code, secondary_failure
):
    fake = preserved_session
    primary = SystemExit(code)
    write_report = probe._write_report

    def session(_build):
        fake.checkpoint()
        fake.events.append("teardown")
        if secondary_failure == "hash":
            fake.part.write_bytes(b"teardown changed a protected file")
        raise primary

    def write(path, report):
        if report.get("outer_session", {}).get("status") == "failed":
            raise OSError("secondary final JSON failure")
        return write_report(path, report)

    def emit(_data):
        raise OSError("secondary final task-log failure")

    if secondary_failure == "json":
        monkeypatch.setattr(probe, "_write_report", write)
    elif secondary_failure == "log":
        monkeypatch.setattr(probe, "_emit_report", emit)
    assert probe.run_preserved_session(
        session, _unexpected_native_boundary, fake.source, fake.report_path
    ) == 1
    assert primary.code is code
    assert "outer_session.execution" in primary.__notes__[-1]
    report = (
        json.loads(fake.report_path.read_text(encoding="utf-8"))
        if secondary_failure == "log"
        else fake.emitted[0]
    )
    outer = report["outer_session"]
    assert report["probe_status"] == outer["status"] == "failed"
    assert outer["success_coded_system_exit_refused"] is True
    assert outer["preservation_complete"] is (secondary_failure != "hash")
    execution = next(
        error for error in outer["errors"]
        if error["location"] == "outer_session.execution"
    )
    assert execution["type"] == "SystemExit" and execution["message"] == str(code)
    if secondary_failure == "hash":
        assert any(
            error["location"].startswith("preservation.")
            for error in outer["errors"]
        )
    elif secondary_failure in ("json", "log"):
        assert any("publication" in error["location"] for error in outer["errors"])
    assert probe._OUTER_SESSION_ID is None


class _ExitStatusEqualToZero:
    def __eq__(self, other):
        return other == 0

    def __str__(self):
        return "non-integer exit status"


@pytest.mark.parametrize(
    "code", [_ExitStatusEqualToZero(), 0.0, "0", True, _IntSubclass(9)]
)
def test_non_success_system_exit_status_is_preserved_without_equal_zero_coercion(
    probe, preserved_session, code
):
    fake = preserved_session
    primary = SystemExit(code)

    def session(_build):
        fake.checkpoint()
        raise primary

    with pytest.raises(SystemExit) as caught:
        probe.run_preserved_session(
            session, _unexpected_native_boundary, fake.source, fake.report_path
        )
    assert caught.value is primary and caught.value.code is code
    assert fake.emitted[0]["outer_session"]["success_coded_system_exit_refused"] is False
    assert fake.emitted[0]["probe_status"] == "failed"
