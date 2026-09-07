"""Real pilot/field/source/save/ownership composition, with native leaves doubled."""

import json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

import _drawing_build
import _drawing_common as common
from diagnostics import _drawing_lower_text_control as lower
from diagnostics import _native_drawing_save_control as native_save
from diagnostics import _owned_native_documents as owned
from diagnostics import _source_save_boundaries as boundaries
from diagnostics import probe_datum_policy_recipes as pilot
from test_benchmark_drawing_recipes import recipe
from test_datum_policy_recipes_drawing import fixture_sources
from test_owned_native_documents_drawing import Model, native as native


def _recipe():
    code = recipe(Path("unused.SLDPRT"))
    names = ("set_dimension_callouts", "set_dimension_precision", *dict.fromkeys(boundaries.DRAWING_OPERATIONS))
    code = code.replace(
        "from _drawing_common import DrawingOutputs",
        "from _drawing_common import DrawingOutputs, " + ", ".join(names),
    )
    return code.replace(
        "    return await adapter.draw(OUTPUTS, SOURCE)",
        "    annotations = adapter.currentModel.annotations\n"
        "    set_dimension_callouts(adapter, annotations, {'ArborBoreDia': 'THRU - REAM\\nPRESS FIT'}, location='below')\n"
        "    set_dimension_precision(adapter, annotations, {'ArborBoreDia': 2})\n"
        + "".join(f"    {name}(adapter)\n" for name in boundaries.DRAWING_OPERATIONS[:-1])
        + "    return await finalize_drawing(adapter, outputs=OUTPUTS)\n",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("save_variant", tuple(native_save.DrawingSave))
@pytest.mark.parametrize("outcome", ["passed", "original_timing", "setter_failure", "cold_loss", "hidden_print"])
async def test_real_pilot_queued_field_with_25_banks_owned_rename_and_cold_gates(
    native, tmp_path, monkeypatch, save_variant, outcome
):
    monkeypatch.setattr(pilot, "ORDER", ("alignment_pinion",))
    sources, guards = fixture_sources(tmp_path, monkeypatch)
    monkeypatch.setitem(pilot.TARGETS, "alignment_pinion", NS(view_roles={}, entity_labels=()))
    monkeypatch.setattr(pilot.benchmark, "recipe_source", lambda *_: _recipe())
    monkeypatch.setattr(pilot.benchmark, "revision", lambda _: "frozen")
    monkeypatch.setattr(pilot, "helper_fingerprints", lambda: {"helper": "frozen"})
    monkeypatch.setattr(pilot, "adapter_fingerprints", lambda: {"adapter": "frozen"})
    monkeypatch.setattr(pilot, "retain_failed_drawing", Mock())
    for module in (lower, native_save, boundaries):
        monkeypatch.setattr(module, "_early_bound", lambda value, _: value)
    monkeypatch.setattr("_drawing_native_callouts._early_bound", lambda value, _: value)
    monkeypatch.setattr("diagnostics._source_dimension_snapshot._early_bound", lambda value, _: value)
    events, drawing_models, part_models, persisted, loaded_modules = [], [], [], {}, []
    raw_value = 0.008000000001785
    original_load = pilot.benchmark.load_recipe

    def load(*args, **kwargs):
        module = original_load(*args, **kwargs)
        loaded_modules.append(module)
        return module

    monkeypatch.setattr(pilot.benchmark, "load_recipe", load)

    def prepare_part(part):
        tol = NS(Type=2, GetMinValue=lambda: -0.00004, GetMaxValue=lambda: -0.00002)
        part.parameter = NS(
            Name=lower.DIMENSION, FullName=f"{lower.DIMENSION}@{Path(part.path).stem}.Part",
            GetType=lambda: 0, GetSystemValue3=lambda *args: (raw_value,),
            Tolerance=tol, GetToleranceType=lambda: 2,
        )
        source_display = NS(
            GetDimension2=lambda _: part.parameter, IsHoleCallout=lambda: False,
            Type2=6, GetPrimaryPrecision2=lambda: 2,
            GetPrimaryTolPrecision2=lambda: -3, GetText=lambda _: "",
        )
        part.FeatureByName = lambda _: NS(
            Name="ArborBoreProfile", GetFirstDisplayDimension=lambda: source_display,
            GetNextDisplayDimension=lambda _: None,
        )
        part_models.append(part)
        return part

    def dimensions(model, target, path):
        assert target == "alignment_pinion" and model.GetType() == 1
        assert Path(model.GetPathName()) == path
        return ({"configuration": "Default", "dimensions": {lower.DIMENSION: {
            "full_name": model.parameter.FullName, "value_system": round(raw_value, 12),
            "tolerance_type": 2,
        }}}, {lower.DIMENSION: model.parameter})

    monkeypatch.setattr(pilot, "source_dimensions", dimensions)
    primary = RuntimeError("native before-save SetLowerText failed")

    def prepare_drawing(model, part, text):
        model.lower = text
        view = NS(
            GetName2=lambda: "Drawing View1", ReferencedDocument=part,
            ReferencedConfiguration="Default",
        )
        entities = (object(), object())
        annotation = NS(
            GetName=lambda: "ArborBoreDia", GetType=lambda: 4, OwnerType=0,
            Owner=view, Visible=1, IsDangling=lambda: False,
            GetAttachedEntityCount3=lambda: 2, GetAttachedEntities3=lambda: entities,
            GetAttachedEntityTypes=lambda: (1, 1),
        )

        def set_lower(text):
            assert text == lower.TEXT
            events.append("setter")
            if outcome == "setter_failure":
                raise primary
            model.lower = text

        display = NS(
            Type2=6, IsReferenceDim=lambda: False, IsHoleCallout=lambda: False,
            GetDimension2=lambda _: part.parameter, GetAnnotation=lambda: annotation,
            GetLowerText=lambda: model.lower, SetLowerText=Mock(side_effect=set_lower),
        )
        annotation.GetSpecificAnnotation = lambda: display
        view.GetAnnotations = lambda: (annotation,)
        model.annotations = (annotation,)
        sheet_view = NS(GetAnnotations=lambda: ())
        model.GetViews = lambda: ((sheet_view, view),)
        model.EditRebuild3 = Mock(side_effect=lambda: events.append("rebuild"))
        model.references = [part]
        drawing_models.append(model)
        return model

    original_open = native.adapter.open_model

    async def opening(path):
        result = await original_open(path)
        model = native.adapter.currentModel
        if model.GetType() == 1:
            prepare_part(model)
            return result
        part_path, text = persisted[path]
        part = prepare_part(Model(part_path, kind=1))
        native.app.documents.append(part)
        prepare_drawing(model, part, "" if outcome == "cold_loss" else text)
        return result

    native.adapter.open_model = opening
    baseline = Model(None, title="Unrelated dirty drawing", dirty=True)
    native.app.documents.append(baseline)
    native.app.ActiveDoc = baseline

    def create(adapter, **kwargs):
        part = adapter.currentModel
        model = prepare_drawing(Model(None, title="Owned recipe drawing", dirty=True), part, "")
        native.app.documents.append(model)
        native.app.ActiveDoc = model
        adapter.currentModel = model

        def persist(path):
            events.append("native_save" if Path(path).suffix.upper() == ".SLDDRW" else "pdf")
            Path(path).write_bytes(b"native artifact")
            if Path(path).suffix.upper() == ".SLDDRW":
                persisted[path] = part.path, model.lower
                model.path, model.title, model.dirty = path, Path(path).name, False

        def legacy(path, *args):
            assert args == (0, 0)
            persist(path)
            return 0

        def modern(path, *args):
            assert args == (0, 1, None, None, 0, 0)
            persist(path)
            return True, 0, 0

        model.SaveAs3 = legacy
        model.Extension = NS(SaveAs3=modern)

    monkeypatch.setattr(_drawing_build.sheet_setup, "new_project_drawing", create)
    callouts = Mock(side_effect=AssertionError("no legacy SetText"))
    precision = Mock()
    monkeypatch.setattr(common, "set_dimension_callouts", callouts)
    monkeypatch.setattr(common, "set_dimension_precision", precision)
    originals = {}
    for name in dict.fromkeys(boundaries.DRAWING_OPERATIONS[:-1]):
        originals[name] = Mock()
        monkeypatch.setattr(common, name, originals[name], raising=False)

    async def finalize(adapter, *, outputs):
        # The retained native receipt localizes loss only to this group. This
        # double models that observation; it does not blame a specific setter.
        events.append("finalization")
        adapter.currentModel.lower = ""
        result = common.save_drawing(adapter, str(outputs.slddrw), pdf_path=str(outputs.pdf))
        outputs.png.write_bytes(b"rendered PNG")
        return {**result, "png": str(outputs.png)}

    originals["finalize_drawing"] = finalize
    monkeypatch.setattr(common, "finalize_drawing", finalize)
    original_save = common.save_drawing

    def witness(adapter, **kwargs):
        text = adapter.currentModel.lower
        return {"annotations": {"Drawing View1/ArborBoreDia": {"generic": {
            "texts": [{"value": line} for line in ("" if outcome == "hidden_print" else text).splitlines()]
        }}}}

    monkeypatch.setattr(pilot, "drawing_witness", witness)

    def compare(before, after):
        assert before == after
        return {"status": "passed", "rejected": []}

    monkeypatch.setattr(pilot, "compare_drawing_reopen", compare)
    variant = lower.CalloutStorage.LOWER_TEXT_BEFORE_SAVE
    if outcome == "original_timing":
        variant = lower.CalloutStorage.LOWER_TEXT

    async def callback(adapter):
        return await pilot.pilot(
            adapter, "frozen", sources, guards, tmp_path / "reports",
            targets=("alignment_pinion",), drawing_save=save_variant,
            source_observation=boundaries.SourceObservation.ALIGNMENT_SAVE,
            callout_storage=variant,
        )

    if outcome == "passed":
        await owned.owned_callback(native.adapter, callback)
    else:
        with pytest.raises(RuntimeError) as caught:
            await owned.owned_callback(native.adapter, callback)
        if outcome == "setter_failure":
            assert caught.value is primary
    (receipt,) = (tmp_path / "reports").glob("*/pilot.json")
    report = json.loads(receipt.read_text())
    trial = report["trials"][0]
    assert report["status"] == ("passed" if outcome == "passed" else "failed")
    assert report["sources_before"] == report["sources_after"]
    assert report["runtime_final_guard_errors"] == []
    assert trial["copy_final"] == pilot.EXPECTED_PART_HASHES["alignment_pinion"]
    assert native.app.documents == [baseline]
    assert baseline.dirty and baseline.Visible and not baseline.path
    assert all(part.dirty is False for part in part_models)
    rows = trial["source_boundaries"]["banks"]
    assert all(row["raw_system_values"] == [raw_value] for row in rows)
    assert all(row["dirty_before_read"] is row["dirty_after_read"] is False for row in rows)
    assert all(row["disk_sha256"] == trial["copy_final"] for row in rows)
    by_label = {row["boundary"]: row for row in rows}
    assert len(rows) == (23 if outcome == "setter_failure" else 25)
    key = "Drawing View1/ArborBoreDia"
    assert by_label["before_native_save"]["drawing"][key]["lower_text"] == ""
    assert by_label["after_native_save"]["drawing"][key]["lower_text"] == (
        "" if outcome in ("setter_failure", "original_timing") else lower.TEXT
    )
    first = drawing_models[0]
    first.annotations[0].GetSpecificAnnotation().SetLowerText.assert_called_once_with(lower.TEXT)
    assert first.EditRebuild3.call_count == (0 if outcome == "setter_failure" else 1)
    if outcome != "original_timing":
        assert events[:2] == ["finalization", "setter"]
    if outcome == "passed":
        assert events == ["finalization", "setter", "rebuild", "native_save", "pdf"]
        assert trial["callout_storage_built"] == trial["callout_storage_reopened"]
        assert drawing_models[1].annotations[0] is not first.annotations[0]
        assert part_models[1].parameter is not part_models[0].parameter
    if outcome == "setter_failure":
        assert events == ["finalization", "setter"]
        assert trial["lower_text_control"]["operation"]["error"] == repr(primary)
        assert trial["source_boundaries"]["operation_errors"][0]["boundary"] == "native_save"
    assert common.save_drawing is original_save
    assert common.set_dimension_callouts is loaded_modules[0].set_dimension_callouts is callouts
    assert loaded_modules[0].set_dimension_precision is precision
    assert all(getattr(loaded_modules[0], name) is value for name, value in originals.items())
