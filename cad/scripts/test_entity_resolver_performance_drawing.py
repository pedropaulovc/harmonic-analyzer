"""The native profiler must observe calls without caching or hiding failures."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import probe_entity_resolver_performance as probe


def test_profiler_counts_property_reads_and_invocations_separately(monkeypatch):
    native = SimpleNamespace(Identity=Mock(return_value=4001), PlaneParams=(1, 2, 3))
    monkeypatch.setattr(probe, "_early_bound", lambda obj, interface: obj)
    reads = probe.NativeReads()
    proxy = reads.bind(native, "ISurface")
    assert proxy.Identity() == 4001
    assert proxy.PlaneParams == (1, 2, 3)
    assert proxy.PlaneParams == (1, 2, 3)
    assert reads.rows["call.ISurface.Identity"]["count"] == 1
    assert reads.rows["lookup.ISurface.PlaneParams"]["count"] == 2
    assert probe.unwrap(proxy) is native


def test_rebinding_unwraps_instrumented_handles(monkeypatch):
    binding = Mock(side_effect=lambda obj, interface: obj)
    monkeypatch.setattr(probe, "_early_bound", binding)
    native = object()
    reads = probe.NativeReads()
    first = reads.bind(native, "IFace2")
    second = reads.bind(first, "IFace2")
    assert probe.unwrap(second) is native
    assert all(call.args[0] is native for call in binding.call_args_list)


def test_profiler_rejects_another_thread_before_native_call(monkeypatch):
    reads = probe.NativeReads()
    monkeypatch.setattr(probe.threading, "get_ident", lambda: reads.thread + 1)
    operation = Mock()
    with pytest.raises(RuntimeError, match="invoking thread"):
        reads.call("native", operation)
    operation.assert_not_called()


def test_profiler_counts_failed_native_call():
    reads = probe.NativeReads()
    with pytest.raises(ValueError, match="native failure"):
        reads.call("native", Mock(side_effect=ValueError("native failure")))
    assert reads.rows["native"]["failures"] == 1
    assert reads.rows["native"]["count"] == 1
    assert reads.rows["native"]["seconds"] >= 0


def test_failed_resolution_retains_measurement_and_restores_bindings():
    import _part_pmi

    original = _part_pmi._early_bound
    module = SimpleNamespace(
        _early_bound=original,
        ModelEntities=Mock(return_value=SimpleNamespace(
            resolve=Mock(side_effect=RuntimeError("ambiguous role"))
        )),
    )
    row = {}
    with pytest.raises(RuntimeError, match="ambiguous role"):
        probe.resolve_sample(module, object(), {}, "reads", row)
    assert row["seconds"] >= 0
    assert row["instrumentation"] == "reads"
    assert module._early_bound is original
    assert _part_pmi._early_bound is original


def test_each_sample_constructs_a_fresh_resolver():
    factory = Mock(return_value=SimpleNamespace(resolve=Mock(return_value={})))
    module = SimpleNamespace(ModelEntities=factory)
    for _ in range(2):
        assert probe.resolve_sample(module, object(), {}, "none", {}) == {}
    assert factory.call_count == 2
