"""Interrupted contact observations must not publish a successful receipt."""

from asyncio import CancelledError
from copy import deepcopy
import json
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest

from diagnostics import probe_spare_deck_contact as probe


@pytest.fixture
def context(monkeypatch, tmp_path):
    from solidworks_mcp.adapters import pywin32_adapter

    source = tmp_path / "cad/out/sldasm/harmonic-analyzer.SLDASM"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"unchanged saved top")
    sha = probe.digest(source)
    inputs = {str(source): {"status": "unchanged", "before": sha, "after": sha}}
    owner = NS(
        hashes={str(source): sha},
        open=AsyncMock(),
        close=AsyncMock(),
        inventory=Mock(return_value={}),
        input_evidence=Mock(return_value=inputs),
    )
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    monkeypatch.setattr(probe, "OwnedAssembly", Mock(return_value=owner))
    monkeypatch.setattr(probe, "document_state", Mock(return_value={"top": "clean"}))
    monkeypatch.setattr(probe, "contact", Mock())
    monkeypatch.setattr(probe.sys, "prefix", str(tmp_path / ".venv"))
    monkeypatch.setattr(
        pywin32_adapter, "__file__", str(tmp_path / "SolidworksMCP-python/adapter.py")
    )
    monkeypatch.setattr(probe.subprocess, "check_output", Mock(return_value="f" * 40))
    monkeypatch.setattr(probe, "time", NS(perf_counter=Mock(side_effect=[1.0, 2.0])))
    adapter = NS(swApp=NS(GetProcessID=lambda: 123, RevisionNumber=lambda: "34.3.0"))
    return NS(
        adapter=adapter,
        owner=owner,
        source=source,
        sha=sha,
        inputs=inputs,
        directory=tmp_path,
        path=tmp_path / "contact.json",
        report={},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("entry", ["measure", "probe"])
@pytest.mark.parametrize("interrupt", [CancelledError, KeyboardInterrupt])
@pytest.mark.parametrize(
    "boundary", ["open", "before", "contact", "after", "close", "inventory", "inputs"]
)
async def test_native_or_cleanup_interruption_retains_nonpass_receipt(
    context, entry, interrupt, boundary
):
    c = context
    primary = interrupt(f"interrupted {boundary}")
    if boundary in ("open", "close"):
        getattr(c.owner, boundary).side_effect = primary
    if boundary == "before":
        probe.document_state.side_effect = primary
    if boundary == "after":
        probe.document_state.side_effect = [{"top": "clean"}, primary]
    if boundary == "contact":
        probe.contact.side_effect = primary
    if boundary == "inventory":
        c.owner.inventory.side_effect = [{}, primary]
    if boundary == "inputs":
        c.owner.input_evidence.side_effect = primary

    with pytest.raises(interrupt) as caught:
        if entry == "measure":
            await probe.measure(c.adapter, c.report, c.path, c.sha)
        if entry == "probe":
            await probe.probe(c.adapter, c.directory, c.sha)

    assert caught.value is primary
    receipt = json.loads(c.path.read_text(encoding="utf-8"))
    assert receipt["status"] == "failed"
    assert repr(primary) in receipt["errors"]
    c.owner.close.assert_awaited_once()
    c.owner.input_evidence.assert_called_once()
    if boundary != "inputs":
        assert receipt["inputs"] == c.inputs
    assert probe.digest(c.source) == c.sha
    if boundary not in ("close", "inventory"):
        assert receipt["final_inventory"] == []
    if boundary in ("close", "inventory"):
        assert "final_inventory" not in receipt


@pytest.mark.asyncio
@pytest.mark.parametrize("interrupt", [CancelledError, KeyboardInterrupt])
async def test_interruption_survives_secondary_cleanup_hash_and_timing_errors(
    context, interrupt
):
    c = context
    primary = interrupt("contact interrupted")
    cleanup = RuntimeError("close refused")
    timing = OSError("clock failed")
    probe.contact.side_effect = primary
    c.owner.close.side_effect = cleanup
    c.owner.input_evidence.return_value = {str(c.source): {"status": "unreadable"}}
    probe.time.perf_counter.side_effect = [1.0, timing]

    with pytest.raises(interrupt) as caught:
        await probe.probe(c.adapter, c.directory, c.sha)

    assert caught.value is primary
    receipt = json.loads(c.path.read_text(encoding="utf-8"))
    assert receipt["status"] == "failed"
    assert receipt["inputs"][str(c.source)]["status"] == "unreadable"
    assert any("close refused" in error for error in receipt["errors"])
    assert any("clock failed" in error for error in receipt["errors"])
    assert any("saved input hashes" in error for error in receipt["errors"])
    assert any("close refused" in note for note in primary.__notes__)
    assert any("clock failed" in note for note in primary.__notes__)
    c.owner.close.assert_awaited_once()
    c.owner.input_evidence.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("interrupt", [CancelledError, KeyboardInterrupt])
@pytest.mark.parametrize("boundary", ["start", "end"])
async def test_timing_interruption_never_leaves_a_passed_receipt(
    context, interrupt, boundary
):
    c = context
    primary = interrupt("clock interrupted")
    probe.time.perf_counter.side_effect = (
        [primary] if boundary == "start" else [1.0, primary]
    )
    with pytest.raises(interrupt) as caught:
        await probe.probe(c.adapter, c.directory, c.sha)
    assert caught.value is primary
    receipt = json.loads(c.path.read_text(encoding="utf-8"))
    assert receipt["status"] == "failed"
    assert repr(primary) in receipt["errors"]
    assert "inspection_and_owned_cleanup_seconds" not in receipt
    if boundary == "start":
        c.owner.open.assert_not_awaited()
        c.owner.close.assert_not_awaited()
    if boundary == "end":
        assert receipt["inputs"] == c.inputs
        c.owner.close.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("interrupt", [CancelledError, KeyboardInterrupt])
@pytest.mark.parametrize("entry,checkpoint_index", [("measure", 3), ("probe", 4)])
@pytest.mark.parametrize("publication", ["before_write", "after_write"])
async def test_interrupted_final_checkpoint_records_failure_without_repeating_native_work(
    context, monkeypatch, interrupt, entry, checkpoint_index, publication
):
    c = context
    primary = interrupt("receipt interrupted")
    original = probe.checkpoint
    observations = []

    def checkpoint(path, report):
        observations.append(deepcopy(report))
        if len(observations) == checkpoint_index and publication == "before_write":
            raise primary
        original(path, report)
        if len(observations) == checkpoint_index and publication == "after_write":
            raise primary

    monkeypatch.setattr(probe, "checkpoint", checkpoint)
    with pytest.raises(interrupt) as caught:
        if entry == "measure":
            await probe.measure(c.adapter, c.report, c.path, c.sha)
        if entry == "probe":
            await probe.probe(c.adapter, c.directory, c.sha)
    assert caught.value is primary
    receipt = json.loads(c.path.read_text(encoding="utf-8"))
    assert receipt["status"] == "failed"
    assert repr(primary) in receipt["errors"]
    assert receipt["inputs"] == c.inputs
    assert receipt["final_inventory"] == []
    assert len(observations) == checkpoint_index + 1
    c.owner.close.assert_awaited_once()
    c.owner.open.assert_awaited_once()
    probe.contact.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("interrupt", [CancelledError, KeyboardInterrupt])
@pytest.mark.parametrize("boundary", ["cleanup", "timing"])
async def test_secondary_interruption_cannot_replace_the_first(
    context, interrupt, boundary
):
    c = context
    primary = interrupt("original interruption")
    secondary = (
        KeyboardInterrupt("second interruption")
        if interrupt is CancelledError
        else CancelledError("second interruption")
    )
    probe.contact.side_effect = primary
    if boundary == "cleanup":
        c.owner.close.side_effect = secondary
    if boundary == "timing":
        probe.time.perf_counter.side_effect = [1.0, secondary]

    with pytest.raises(interrupt) as caught:
        await probe.probe(c.adapter, c.directory, c.sha)

    assert caught.value is primary
    receipt = json.loads(c.path.read_text(encoding="utf-8"))
    assert receipt["status"] == "failed"
    assert receipt["inputs"] == c.inputs
    assert repr(primary) in receipt["errors"]
    assert repr(secondary) in receipt["errors"]
    assert any(repr(secondary) in note for note in primary.__notes__)
    c.owner.close.assert_awaited_once()
    c.owner.input_evidence.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("secondary_type", [OSError, KeyboardInterrupt])
async def test_failure_checkpoint_attempt_is_bounded_and_preserves_both_errors(
    context, monkeypatch, secondary_type
):
    c = context
    primary = CancelledError("first receipt interrupted")
    secondary = secondary_type("failure receipt unavailable")
    original = probe.checkpoint
    calls = []

    def checkpoint(path, report):
        calls.append(deepcopy(report))
        original(path, report)
        if len(calls) == 3:
            raise primary
        if len(calls) == 4:
            raise secondary

    monkeypatch.setattr(probe, "checkpoint", checkpoint)
    with pytest.raises(CancelledError) as caught:
        await probe.measure(c.adapter, c.report, c.path, c.sha)

    assert caught.value is primary
    assert c.report["status"] == "failed"
    assert c.report["errors"] == [repr(primary), repr(secondary)]
    assert any(repr(secondary) in note for note in primary.__notes__)
    assert json.loads(c.path.read_text(encoding="utf-8"))["status"] == "failed"
    assert len(calls) == 4
    c.owner.close.assert_awaited_once()
    c.owner.input_evidence.assert_called_once()
