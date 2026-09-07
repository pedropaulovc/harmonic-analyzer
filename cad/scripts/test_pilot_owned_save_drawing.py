"""The actual pilot composes owned saves before native/source controls."""

import json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

import _drawing_build
import _drawing_common as common
from diagnostics import _native_drawing_save_control as native_save
from diagnostics import _owned_native_documents as owned
from diagnostics import _source_save_boundaries as boundaries
from diagnostics import probe_datum_policy_recipes as pilot
from test_benchmark_drawing_recipes import recipe
from test_datum_policy_recipes_drawing import fixture_sources
from test_owned_native_documents_drawing import Model, native as native


@pytest.mark.asyncio
@pytest.mark.parametrize("variant", [None, *native_save.DrawingSave])
@pytest.mark.parametrize("outcome", ["passed", "native_failure"])
async def test_pilot_owned_save_reconciles_before_source_after_bank(
    native, tmp_path, monkeypatch, variant, outcome
):
    monkeypatch.setattr(pilot, "ORDER", ("alignment_pinion",))
    sources, guards = fixture_sources(tmp_path, monkeypatch)
    monkeypatch.setitem(
        pilot.TARGETS, "alignment_pinion", NS(view_roles={}, entity_labels=())
    )
    code = (
        recipe(Path("unused.SLDPRT"))
        .replace(
            "from _drawing_common import DrawingOutputs",
            "from _drawing_common import DrawingOutputs, set_dimension_callouts, set_dimension_precision",
        )
        .replace(
            "    return await adapter.draw(OUTPUTS, SOURCE)",
            "    set_dimension_callouts(adapter, [], {})\n"
            "    set_dimension_precision(adapter, [], {})\n"
            "    return await adapter.draw(OUTPUTS, SOURCE)",
        )
    )
    monkeypatch.setattr(pilot.benchmark, "recipe_source", lambda *_: code)
    monkeypatch.setattr(pilot.benchmark, "revision", lambda _: "frozen")
    monkeypatch.setattr(pilot, "helper_fingerprints", lambda: {"helper": "frozen"})
    monkeypatch.setattr(pilot, "adapter_fingerprints", lambda: {"adapter": "frozen"})
    monkeypatch.setattr(native_save, "_early_bound", lambda value, _: value)
    callouts, precision = Mock(), Mock()
    monkeypatch.setattr(common, "set_dimension_callouts", callouts)
    monkeypatch.setattr(common, "set_dimension_precision", precision)
    monkeypatch.setattr(
        pilot,
        "source_dimensions",
        lambda model, target, path: (
            {"configuration": "Default", "dimensions": {boundaries.DIMENSION: "same"}},
            {boundaries.DIMENSION: model},
        ),
    )
    monkeypatch.setattr(
        pilot, "drawing_witness", lambda adapter, **_: {"drawing": "same"}
    )
    monkeypatch.setattr(
        pilot,
        "compare_drawing_reopen",
        lambda before, after: {"status": "passed", "rejected": []},
    )
    # Other tests cover raw source fields; retain the real observer's alias,
    # operation-count, artifact-context and error composition here.
    observed = []

    def capture(self, label):
        if label in ("after_native_save", "before_pdf_export", "after_pdf_export"):
            record = self.adapter.ownership.assert_current_owned()
            assert record.handle is self.adapter.currentModel
            assert record.state["path"] == str(self.module.OUTPUTS.slddrw)
        observed.append(label)
        self.report["banks"].append({"boundary": label})
        self.checkpoint()

    monkeypatch.setattr(boundaries.SourceSaveBoundaries, "capture", capture)
    monkeypatch.setattr(pilot, "retain_failed_drawing", Mock())
    baseline = Model(None, title="User unsaved drawing", dirty=True)
    native.app.documents.append(baseline)
    native.app.ActiveDoc = baseline
    references, calls, records = {}, [], []
    original_open = native.adapter.open_model

    async def opening(path):
        result = await original_open(path)
        if Path(path).suffix.upper() == ".SLDDRW":
            part = Model(references[path], kind=1)
            native.app.documents.append(part)
            native.adapter.currentModel.references = [part]
        return result

    native.adapter.open_model = opening
    original_save = common.save_drawing

    class Setup:
        variant = NS(value="prepared")
        guards = {}

        async def configure(self, adapter, module, trial, directory):
            assert common.save_drawing is original_save
            assert adapter.ownership.creation is None
            assert adapter.currentModel is None
            self.factory = _drawing_build.normal_drawing_factory(
                adapter, module.TEMPLATE_SPEC
            )
            return self.factory

        def require_used(self):
            self.factory.require_used()

        def final_guards(self):
            assert common.save_drawing is original_save
            return []

    setup = Setup()

    async def callback(adapter):
        async def draw(outputs, source):
            part = native.app.GetOpenDocumentByName(str(source))
            part.dirty = True
            model = Model(None, title="Owned recipe drawing", dirty=True)
            model.references = [part]
            native.app.documents.append(model)
            native.app.ActiveDoc = model
            adapter.currentModel = model
            record = adapter.ownership.assert_current_owned()
            records.append(record)
            references[str(outputs.slddrw)] = str(source)

            def persist(path):
                Path(path).write_bytes(b"native output")
                if Path(path).suffix.upper() == ".SLDDRW":
                    model.path, model.title, model.dirty = path, Path(path).name, False
                    if outcome == "native_failure":
                        raise RuntimeError("native save failed after rename")

            def legacy(path, *args):
                calls.append(("legacy", Path(path).suffix, args))
                persist(path)
                return 0

            def modern(path, *args):
                calls.append(("modern", Path(path).suffix, args))
                persist(path)
                return True, 0, 2

            model.SaveAs3 = legacy
            model.Extension = NS(SaveAs3=modern)
            result = common.save_drawing(
                adapter, str(outputs.slddrw), pdf_path=str(outputs.pdf)
            )
            assert adapter.ownership.assert_current_owned() is record
            outputs.png.write_bytes(b"rendered PNG")
            return {**result, "png": str(outputs.png)}

        native.adapter.draw = draw
        return await pilot.pilot(
            adapter,
            "frozen",
            sources,
            guards,
            tmp_path / "reports",
            targets=("alignment_pinion",),
            setup_controller=setup,
            source_observation=boundaries.SourceObservation.ALIGNMENT_SAVE,
            drawing_save=variant,
        )

    if outcome == "passed":
        await owned.owned_callback(native.adapter, callback)
    else:
        with pytest.raises(
            RuntimeError, match="native save failed after rename"
        ) as caught:
            await owned.owned_callback(native.adapter, callback)
        assert not hasattr(caught.value, "__notes__")
    assert common.save_drawing is original_save
    assert common.set_dimension_callouts is callouts
    assert common.set_dimension_precision is precision
    assert native.app.documents == [baseline]
    assert baseline.dirty and baseline.Visible and not baseline.path
    assert len(records) == 1 and records[0].state["path"].endswith(".SLDDRW")
    assert "after_native_save" in observed
    expected_native = (
        ("modern", ".SLDDRW", (0, 1, None, None, 0, 0))
        if variant is native_save.DrawingSave.EXTENSION_SILENT
        else ("legacy", ".SLDDRW", (0, 0))
    )
    assert calls == [expected_native] + (
        [("legacy", ".pdf", (0, 0))] if outcome == "passed" else []
    )
    assert observed == ["initial"] + [
        f"{side}_{stage}"
        for stage in boundaries.STAGES[: 4 if outcome == "passed" else 3]
        for side in ("before", "after")
    ]
    (receipt,) = (tmp_path / "reports").glob("*/pilot.json")
    report = json.loads(receipt.read_text())
    assert report["status"] == ("passed" if outcome == "passed" else "failed")
    assert report["sources_before"] == report["sources_after"]
    assert report["runtime_final_guard_errors"] == []
    trial = report["trials"][0]
    assert trial["copy_final"] == pilot.EXPECTED_PART_HASHES["alignment_pinion"]
    if outcome == "native_failure":
        assert trial["source_boundaries"]["operation_errors"] == [
            {
                "boundary": "native_save",
                "error": "RuntimeError('native save failed after rename')",
            }
        ]
