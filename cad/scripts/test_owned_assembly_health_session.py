"""Offline attach-only contract for the retained assembly health repro."""

import asyncio
import sys
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest

from diagnostics import _owned_native_session as session


@pytest.fixture
def native_doubles(monkeypatch):
    original_documents = (object(), object())

    class ReadOnlyApp:
        __slots__ = ()

        def GetProcessID(self):
            return 37136

        def RevisionNumber(self):
            return "34.3.0"

        def GetDocuments(self):
            return original_documents

    app = ReadOnlyApp()
    adapter = NS(_initialize_com_apartment=Mock(), disconnect=AsyncMock())
    monkeypatch.setattr(session, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(session.win32com.client, "GetActiveObject", Mock(return_value=app))
    monkeypatch.setattr(session._watchdog, "start", Mock())
    monkeypatch.setattr(session._watchdog, "stop", Mock())
    monkeypatch.setenv("HARMONIC_DIAGNOSTIC_SW_PID", "37136")
    return adapter, app, original_documents


@pytest.mark.parametrize("outcome", ["success", "failure"])
def test_existing_documents_reach_callback_unchanged_and_disconnect(native_doubles, outcome):
    adapter, app, documents = native_doubles

    async def callback(actual):
        assert actual is adapter
        assert actual.swApp.GetDocuments() is documents
        if outcome == "failure":
            raise RuntimeError("original probe failure")
        return "finished"

    if outcome == "failure":
        with pytest.raises(RuntimeError, match="original probe failure"):
            asyncio.run(session.connected_probe(adapter, callback))
    else:
        assert asyncio.run(session.connected_probe(adapter, callback)) == "finished"
    assert app.GetDocuments() is documents
    adapter._initialize_com_apartment.assert_called_once_with()
    session.win32com.client.GetActiveObject.assert_called_once_with("SldWorks.Application")
    adapter.disconnect.assert_awaited_once_with()
    session._watchdog.start.assert_called_once_with()
    session._watchdog.stop.assert_called_once_with()


def test_absent_instance_never_launches_or_reaches_callback(native_doubles):
    adapter, _, _ = native_doubles
    session.win32com.client.GetActiveObject.side_effect = RuntimeError("no running instance")
    callback = AsyncMock()
    with pytest.raises(RuntimeError, match="no running instance"):
        asyncio.run(session.connected_probe(adapter, callback))
    callback.assert_not_awaited()
    adapter.disconnect.assert_awaited_once_with()
    session._watchdog.stop.assert_called_once_with()


def test_wrong_pid_never_reaches_callback(native_doubles, monkeypatch):
    adapter, _, _ = native_doubles
    monkeypatch.setenv("HARMONIC_DIAGNOSTIC_SW_PID", "1")
    callback = AsyncMock()
    with pytest.raises(RuntimeError, match="differs from expected"):
        asyncio.run(session.connected_probe(adapter, callback))
    callback.assert_not_awaited()
    adapter.disconnect.assert_awaited_once_with()


@pytest.mark.parametrize("autostart", [None, "1", "false", ""])
def test_parent_environment_rejects_before_seat_wrapper(monkeypatch, autostart):
    from diagnostics import probe_assembly_health_targets as probe

    monkeypatch.setattr("sys.argv", ["probe_assembly_health_targets.py", "channel"])
    monkeypatch.delenv("HARMONIC_SW_AUTOSTART", raising=False)
    if autostart is not None:
        monkeypatch.setenv("HARMONIC_SW_AUTOSTART", autostart)
    with pytest.raises(RuntimeError, match="HARMONIC_SW_AUTOSTART=0"):
        probe.main()


def test_worker_requires_machine_seat_before_adapter_construction(monkeypatch):
    constructor = Mock(side_effect=AssertionError("must not construct adapter"))
    monkeypatch.setitem(
        sys.modules, "solidworks_mcp.adapters.pywin32_adapter",
        NS(PyWin32Adapter=constructor),
    )
    monkeypatch.delenv("HARMONIC_COM_SEAT", raising=False)
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "0")
    with pytest.raises(RuntimeError, match="coordinated COM seat"):
        session.run_owned_diagnostic(AsyncMock())
    constructor.assert_not_called()


@pytest.mark.parametrize("requested", [False, True])
@pytest.mark.parametrize("variant_name,effective", [
    ("BASELINE", False), ("CANDIDATE", True),
])
def test_health_probe_preserves_pre_and_post_change_requests(requested, variant_name, effective):
    from diagnostics import probe_assembly_health_targets as probe

    rows = [object(), object()]
    native = NS(GetComponents=Mock(return_value=rows))
    calls = []
    observer = probe.AssemblyEnumeration(native, probe.Variant[variant_name], calls)

    assert observer.GetComponents(requested) is rows

    native.GetComponents.assert_called_once_with(effective)
    assert calls == [{
        "requested_top_level_only": requested,
        "effective_top_level_only": effective,
        "status": "returned", "components": 2,
    }]
    probe.require_one_enumeration(calls)


@pytest.mark.parametrize("requested", [None, 0, 1, 1.0, "True", "False"])
def test_health_probe_rejects_non_boolean_before_native_enumeration(requested):
    from diagnostics import probe_assembly_health_targets as probe

    native = NS(GetComponents=Mock())
    calls = []
    observer = probe.AssemblyEnumeration(native, probe.Variant.CANDIDATE, calls)

    with pytest.raises(RuntimeError, match="must request one boolean"):
        observer.GetComponents(requested)

    native.GetComponents.assert_not_called()
    assert calls == []


@pytest.mark.parametrize("variant_name", ["BASELINE", "CANDIDATE"])
def test_health_probe_preserves_native_failure_and_refuses_completed_trial(variant_name):
    from diagnostics import probe_assembly_health_targets as probe

    original = RuntimeError("native enumeration rejected")
    native = NS(GetComponents=Mock(side_effect=original))
    calls = []
    observer = probe.AssemblyEnumeration(native, probe.Variant[variant_name], calls)

    with pytest.raises(RuntimeError) as caught:
        observer.GetComponents(False)

    assert caught.value is original
    assert calls == [{
        "requested_top_level_only": False,
        "effective_top_level_only": variant_name == "CANDIDATE",
        "status": "failed", "error": repr(original),
    }]
    with pytest.raises(RuntimeError, match="exactly one completed"):
        probe.require_one_enumeration(calls)
