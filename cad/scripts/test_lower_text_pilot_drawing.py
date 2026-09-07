"""The lower-text experiment keeps the owned pilot's source and cold gates."""

from contextlib import contextmanager
import asyncio
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from diagnostics import probe_datum_policy_recipes as pilot
from diagnostics import _drawing_lower_text_control as lower
from diagnostics import _source_save_boundaries as source
from diagnostics._native_drawing_save_control import DrawingSave


@pytest.mark.parametrize("route", ["parent", "worker"])
@pytest.mark.parametrize("save", tuple(DrawingSave))
def test_explicit_field_and_save_factors_are_forwarded(monkeypatch, tmp_path, route, save):
    monkeypatch.setattr(pilot, "require_owned_diagnostic_environment", lambda: None)
    monkeypatch.setattr(pilot.benchmark, "revision", lambda _: "frozen")
    parent, seen = Mock(), []
    monkeypatch.setitem(sys.modules, "dodo", NS(_run=parent))

    async def run(*args, **kwargs):
        seen.append(kwargs)
        return 0

    monkeypatch.setattr(pilot, "pilot", run)
    monkeypatch.setattr(
        pilot, "run_copy_diagnostic", lambda callback: asyncio.run(callback(object()))
    )
    argv = [
        "--source-root", str(tmp_path), "--guard-root", str(tmp_path),
        "--target", "alignment_pinion", "--source-observation", "alignment_save",
        "--drawing-save", save.value, "--callout-storage", "lower_text",
    ]
    if route == "worker":
        argv.append("--worker")
    assert pilot.main(argv) == 0
    if route == "worker":
        assert seen == [{
            "targets": ("alignment_pinion",),
            "source_observation": source.SourceObservation.ALIGNMENT_SAVE,
            "drawing_save": save,
            "callout_storage": lower.CalloutStorage.LOWER_TEXT,
        }]
        return
    command = parent.call_args.args[0]
    assert command[command.index("--callout-storage") + 1] == "lower_text"
    assert command[command.index("--drawing-save") + 1] == save.value
    assert parent.call_args.kwargs["com"] is True


@pytest.mark.parametrize("extra", [[], ["--source-observation", "alignment_save"]])
def test_lower_text_requires_banks_and_explicit_save_before_environment(
    monkeypatch, tmp_path, extra
):
    environment = Mock(side_effect=AssertionError("must not attach"))
    monkeypatch.setattr(pilot, "require_owned_diagnostic_environment", environment)
    with pytest.raises(ValueError, match="callout-storage control"):
        pilot.main([
            "--source-root", str(tmp_path), "--guard-root", str(tmp_path),
            "--target", "alignment_pinion", "--callout-storage", "lower_text", *extra,
        ])
    environment.assert_not_called()


@pytest.mark.parametrize(
    "variant,order",
    [("lower_text", ("alignment_pinion",)),
     (lower.CalloutStorage.LOWER_TEXT, ("channel_lever",)),
     (lower.CalloutStorage.LOWER_TEXT, ("alignment_pinion", "rocker_arm"))],
)
def test_direct_selection_rejects_strings_or_wrong_scope(variant, order):
    with pytest.raises(ValueError, match="callout-storage control"):
        pilot.require_callout_storage(
            variant, source.SourceObservation.ALIGNMENT_SAVE, DrawingSave.LEGACY, order
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["normal", "source_drift", "cold_loss", "cold_raw_drift"])
async def test_pilot_field_observer_order_and_fresh_cold_handles(
    monkeypatch, tmp_path, mode
):
    from test_datum_policy_recipes_drawing import Adapter, fixture_sources
    from test_benchmark_drawing_recipes import recipe

    monkeypatch.setattr(pilot, "ORDER", ("alignment_pinion",))
    source_root, guard_root = fixture_sources(tmp_path, monkeypatch)
    monkeypatch.setitem(
        pilot.TARGETS, "alignment_pinion", NS(view_roles={}, entity_labels=())
    )
    monkeypatch.setattr(
        pilot.benchmark, "recipe_source", lambda *_: recipe(Path("unused.SLDPRT"))
    )
    monkeypatch.setattr(pilot.benchmark, "revision", lambda _: "frozen")
    monkeypatch.setattr(pilot, "helper_fingerprints", lambda: {"helper": "frozen"})
    monkeypatch.setattr(pilot, "adapter_fingerprints", lambda: {"adapter": "frozen"})
    monkeypatch.setattr(pilot, "retain_failed_drawing", Mock())
    warm, cold = object(), object()
    source_reads, events = [], []

    def dimensions(*args):
        source_reads.append(args)
        handle = warm if len(source_reads) <= 2 else cold
        return ({"configuration": "Default"}, {"bore": handle})

    monkeypatch.setattr(pilot, "source_dimensions", dimensions)

    class Boundaries:
        def __init__(self, *args, drawing_reader):
            assert drawing_reader.__self__.__class__ is Field
            assert drawing_reader.__func__ is Field.boundary_snapshot
            self.drawing_reader = drawing_reader

        @contextmanager
        def observe(self):
            events.append("source_enter")
            assert self.drawing_reader() == {"observed_lower_text": ""}
            yield
            events.append("source_exit")

        def require_used(self):
            events.append("source_checked")

    class Field:
        def __init__(self, actual_adapter, module, trial, handles):
            assert actual_adapter is adapter
            assert handles == {"bore": warm}

        @contextmanager
        def observe(self):
            events.append("field_enter")
            yield
            events.append("field_exit")

        def require_used(self):
            events.append("field_checked")

        def boundary_snapshot(self):
            return {"observed_lower_text": ""}

        def snapshot(self, actual_adapter, handles, *, phase, annotations):
            assert actual_adapter is adapter
            assert handles == {"bore": warm if phase == "built" else cold}
            assert annotations == {"observed": phase}
            events.append(phase)
            row = {"lower_text": "THRU - REAM\nPRESS FIT"}
            if mode == "cold_raw_drift":
                raw = 0.008000000001785
                row["parameters"] = (
                    ("ArborBoreDia", "ArborBoreDia@ArborBoreProfile@copy.Part", 0,
                     raw if phase == "built" else math.nextafter(raw, math.inf)),
                )
            return row

    monkeypatch.setattr(source, "SourceSaveBoundaries", Boundaries)
    monkeypatch.setattr(lower, "LowerTextControl", Field)
    drawing_reads = []

    def witness(*args, **kwargs):
        phase = "built" if not drawing_reads else "reopened"
        drawing_reads.append(phase)
        return {"annotations": {"observed": phase}}

    monkeypatch.setattr(pilot, "drawing_witness", witness)

    def compare(*args):
        events.append("cold_comparison")
        return {
            "status": "failed" if mode == "cold_loss" else "passed",
            "rejected": ["missing text"] if mode == "cold_loss" else [],
        }

    monkeypatch.setattr(pilot, "compare_drawing_reopen", compare)
    adapter = Adapter(mode)
    kwargs = dict(
        targets=("alignment_pinion",),
        source_observation=source.SourceObservation.ALIGNMENT_SAVE,
        drawing_save=DrawingSave.LEGACY,
        callout_storage=lower.CalloutStorage.LOWER_TEXT,
    )
    args = adapter, "frozen", source_root, guard_root, tmp_path / "reports"
    if mode == "normal":
        await pilot.pilot(*args, **kwargs)
    if mode != "normal":
        with pytest.raises(RuntimeError):
            await pilot.pilot(*args, **kwargs)
    (receipt,) = (tmp_path / "reports").glob("*/pilot.json")
    result = json.loads(receipt.read_text())
    assert events[:6] == [
        "field_enter", "source_enter", "source_exit", "field_exit",
        "source_checked", "field_checked",
    ]
    assert result["sources_before"] == result["sources_after"]
    assert result["status"] == ("passed" if mode == "normal" else "failed")
    if mode == "source_drift":
        assert events[6:] == []
        assert result["runtime_final_guard_errors"]
        return
    if mode == "cold_raw_drift":
        trial = result["trials"][0]
        before = trial["callout_storage_built"]["parameters"][0][-1]
        after = trial["callout_storage_reopened"]["parameters"][0][-1]
        assert before != after
        assert round(before, 12) == round(after, 12)
        assert events[6:] == ["built", "reopened"]
        assert "lower-text mapping changed" in result["error"]
        assert result["runtime_final_guard_errors"] == []
        return
    assert events[6:] == ["built", "reopened", "cold_comparison"]
    assert result["trials"][0]["callout_storage_built"] == {
        "lower_text": "THRU - REAM\nPRESS FIT"
    }
    assert result["trials"][0]["callout_storage_reopened"] == {
        "lower_text": "THRU - REAM\nPRESS FIT"
    }
