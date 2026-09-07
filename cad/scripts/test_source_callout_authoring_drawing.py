"""Owned source H0->H1 is deliberate; fresh drawings only read imported text."""

import json
import asyncio
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock
import sys

import pytest

import _common
import _drawing_build
import _drawing_common as common
from diagnostics import _source_callout_authoring as control
from diagnostics import _source_dimension_snapshot as source_snapshot
from diagnostics import _source_save_boundaries as boundaries
from diagnostics import _native_drawing_save_control as saves
from diagnostics import _owned_native_documents as owned
from diagnostics import probe_datum_policy_recipes as pilot
from test_datum_policy_recipes_drawing import fixture_sources
from test_lower_text_before_save_pilot_drawing import _recipe as historical_recipe
from test_owned_native_documents_drawing import Model, native as native


def verifier_recipe():
    """Explicit new-contract fixture: actual verifier, no retired setter alias."""
    return (
        historical_recipe()
        .replace("set_dimension_callouts", "verify_dimension_callouts")
        .replace(
            "    drawing_factory(adapter)",
            "    source_model = adapter.currentModel\n    drawing_factory(adapter)",
        )
        .replace(
            "location='below'",
            "feature_name='ArborBoreProfile', view=adapter.currentModel.front_view, source_model=source_model, location='below'",
        )
    )


@pytest.mark.parametrize("route", ["parent", "worker"])
def test_source_authoring_cli_forwards_explicit_factor_with_no_lower_control(
    monkeypatch, tmp_path, route
):
    monkeypatch.setattr(pilot, "require_owned_diagnostic_environment", lambda: None)
    monkeypatch.setattr(pilot.benchmark, "revision", lambda _: "frozen")
    monkeypatch.setattr(pilot.benchmark, "recipe_source", lambda *_: verifier_recipe())
    parent, observed = Mock(), []
    monkeypatch.setitem(sys.modules, "dodo", NS(_run=parent))

    async def run(*args, **kwargs):
        observed.append(kwargs)
        return 0

    monkeypatch.setattr(pilot, "pilot", run)
    monkeypatch.setattr(
        pilot, "run_copy_diagnostic", lambda callback: asyncio.run(callback(object()))
    )
    argv = [
        "--source-root",
        str(tmp_path),
        "--guard-root",
        str(tmp_path),
        "--target",
        "alignment_pinion",
        "--source-observation",
        "alignment_save",
        "--drawing-save",
        "legacy",
        "--source-callout-authoring",
        "alignment_fit",
    ]
    assert pilot.main([*argv, *(["--worker"] if route == "worker" else [])]) == 0
    if route == "worker":
        assert observed == [
            {
                "targets": ("alignment_pinion",),
                "source_callout_authoring": control.SourceCalloutAuthoring.ALIGNMENT_FIT,
                "drawing_save": saves.DrawingSave.LEGACY,
                "source_observation": boundaries.SourceObservation.ALIGNMENT_SAVE,
            }
        ]
        return
    command = parent.call_args.args[0]
    assert command[command.index("--source-callout-authoring") + 1] == "alignment_fit"
    assert "--callout-storage" not in command
    assert parent.call_args.kwargs["com"] is True


@pytest.mark.parametrize("mode", ["string", "lower", "save", "observation", "target"])
def test_source_authoring_selection_refuses_ambiguous_or_incomplete_scope(mode):
    from diagnostics._drawing_lower_text_control import CalloutStorage

    values = [
        control.SourceCalloutAuthoring.ALIGNMENT_FIT,
        None,
        boundaries.SourceObservation.ALIGNMENT_SAVE,
        saves.DrawingSave.LEGACY,
        ("alignment_pinion",),
    ]
    if mode == "string":
        values[0] = "alignment_fit"
    if mode == "lower":
        values[1] = CalloutStorage.LOWER_TEXT
    if mode == "save":
        values[3] = None
    if mode == "observation":
        values[2] = None
    if mode == "target":
        values[4] = ("rocker_arm",)
    with pytest.raises(ValueError, match="source callout authoring"):
        control.require_selection(*values)


@pytest.mark.parametrize(
    "mode", ["default", "incomplete", "passed", "wrong_path", "wrong_original"]
)
def test_h1_can_only_follow_complete_authoring_provenance(tmp_path, mode):
    trial = {"copy_source": str(tmp_path / "owned.SLDPRT")}
    authoring = {
        "status": "passed",
        "variant": "alignment_fit",
        "original_sha256": "H0",
        "baseline": {
            "path": str((tmp_path / "owned.SLDPRT").resolve()),
            "sha256": "H1",
        },
    }
    if mode != "default":
        trial["source_callout_authoring"] = authoring
    if mode == "incomplete":
        authoring["status"] = "failed"
    if mode == "wrong_path":
        authoring["baseline"]["path"] = "other.SLDPRT"
    if mode == "wrong_original":
        authoring["original_sha256"] = "other H0"
    if mode in ("wrong_path", "wrong_original"):
        with pytest.raises(RuntimeError, match="provenance"):
            control.expected_copy_hash(trial, "H0")
        return
    assert control.expected_copy_hash(trial, "H0") == (
        "H1" if mode == "passed" else "H0"
    )


def test_retired_source_authoring_invocation_rejects_before_native_or_disk(monkeypatch):
    read = Mock(side_effect=AssertionError("unsupported ABI must not read native/disk"))
    monkeypatch.setattr(control.attachments, "file_digest", read)
    with pytest.raises(ValueError, match="historical setter interception is retired"):
        control.SourceCalloutControl(
            object(),
            NS(set_dimension_callouts=common.set_dimension_callouts),
            {"target": "alignment_pinion"},
            read,
        )
    read.assert_not_called()


def test_production_verifier_error_propagates_without_false_success_and_restores_aliases(
    monkeypatch,
):
    primary = RuntimeError("native production verifier rejected source")
    original = Mock(side_effect=primary)
    monkeypatch.setattr(common, "verify_dimension_callouts", original)
    monkeypatch.setattr(control, "_early_bound", lambda value, _: value)
    adapter, view, source_model, annotation, model = (object() for _ in range(5))
    module = NS(verify_dimension_callouts=original)
    instance = object.__new__(control.SourceCalloutControl)
    instance.phase, instance.calls = control._Phase.AUTHORED, 0
    instance.adapter, instance.module = adapter, module
    instance.source_model, instance.handles, instance.report = source_model, {}, {}
    instance._owned = Mock(return_value=model)
    instance._same = Mock()
    instance._read_drawing = Mock(
        return_value=("front/bore", {"text": {"4": control.TEXT, "8": control.TEXT}})
    )
    with pytest.raises(RuntimeError) as caught:
        with instance.observe():
            module.verify_dimension_callouts(
                adapter,
                (annotation,),
                control.CALLOUT,
                feature_name="ArborBoreProfile",
                view=view,
                source_model=source_model,
            )
    assert caught.value is primary
    original.assert_called_once_with(
        adapter,
        (annotation,),
        control.CALLOUT,
        feature_name="ArborBoreProfile",
        view=view,
        source_model=source_model,
        location="below",
    )
    assert (
        module.verify_dimension_callouts is common.verify_dimension_callouts is original
    )
    assert "imported_request" in instance.report
    assert "import_verification" not in instance.report
    with pytest.raises(RuntimeError, match="exactly once"):
        instance.require_used()


@pytest.mark.asyncio
@pytest.mark.parametrize("save_variant", tuple(saves.DrawingSave))
@pytest.mark.parametrize(
    "outcome",
    [
        "passed",
        "setter_failure",
        "part_save_failure",
        "part_cold_loss",
        "unrelated_change",
        "drawing_cold_loss",
        "hidden_print",
    ],
)
async def test_actual_owned_pilot_authors_only_copy_then_preserves_h1_and_print(
    native, tmp_path, monkeypatch, save_variant, outcome
):
    await owned_pilot_case(
        native, tmp_path, monkeypatch, save_variant, outcome, origin="diagnostic"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("save_variant", tuple(saves.DrawingSave))
@pytest.mark.parametrize("outcome", ["passed", "drawing_cold_loss"])
async def test_production_verifier_recipe_uses_real_nine_bank_observer_without_authoring(
    native, tmp_path, monkeypatch, save_variant, outcome
):
    await owned_pilot_case(
        native, tmp_path, monkeypatch, save_variant, outcome, origin="production"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [AssertionError, ValueError])
async def test_owned_negative_case_does_not_accept_unrelated_setter_exceptions(
    native, tmp_path, monkeypatch, error_type
):
    unexpected = error_type("unrelated test or programming failure")
    with pytest.raises(error_type) as caught:
        await owned_pilot_case(
            native,
            tmp_path,
            monkeypatch,
            saves.DrawingSave.LEGACY,
            "setter_failure",
            origin="diagnostic",
            setter_error=unexpected,
        )
    assert caught.value is unexpected


async def owned_pilot_case(
    native, tmp_path, monkeypatch, save_variant, outcome, *, origin, setter_error=None
):
    production = origin == "production"
    monkeypatch.setattr(pilot, "ORDER", ("alignment_pinion",))
    sources, guards = fixture_sources(tmp_path, monkeypatch)
    monkeypatch.setitem(
        pilot.TARGETS, "alignment_pinion", NS(view_roles={}, entity_labels=())
    )
    monkeypatch.setattr(pilot.benchmark, "recipe_source", lambda *_: verifier_recipe())
    monkeypatch.setattr(pilot.benchmark, "revision", lambda _: "frozen")
    monkeypatch.setattr(pilot, "helper_fingerprints", lambda: {"helper": "same"})
    monkeypatch.setattr(pilot, "adapter_fingerprints", lambda: {"adapter": "same"})
    monkeypatch.setattr(pilot, "retain_failed_drawing", Mock())
    native.adapter._attempt = lambda action: action()
    native.adapter._get_attr_or_call = lambda item, name: getattr(item, name)
    for module in (_common, common, control, source_snapshot, boundaries, saves):
        monkeypatch.setattr(module, "_early_bound", lambda value, _: value)
    monkeypatch.setattr("_drawing_marks._early_bound", lambda value, _: value)
    monkeypatch.setattr("_drawing_native_callouts._early_bound", lambda value, _: value)
    part_saved, drawing_saved, events, parts, drawings, modules = {}, {}, [], [], [], []
    primary = (
        setter_error
        if setter_error is not None
        else RuntimeError("source native setter failed")
    )
    raw = 0.008000000001785
    original_load = pilot.benchmark.load_recipe

    def load(*args, **kwargs):
        module = original_load(*args, **kwargs)
        modules.append(module)
        return module

    monkeypatch.setattr(pilot.benchmark, "load_recipe", load)

    def part_model(model):
        text = part_saved.get(model.path, control.TEXT if production else "")
        model.text = "" if outcome == "part_cold_loss" else text
        model.raw = raw
        model.ConfigurationManager = NS(ActiveConfiguration=NS(Name="Default"))
        model.parameter = NS(
            Name="ArborBoreDia",
            FullName=f"{control.DIMENSION}@{Path(model.path).stem}.Part",
            GetType=lambda: 0,
            GetSystemValue3=lambda *_: (model.raw,),
            GetToleranceType=lambda: 2,
            Tolerance=NS(
                Type=2,
                GetMinValue2=lambda: (0, -0.00004),
                GetMaxValue2=lambda: (0, -0.00002),
                # Factory save boundaries still use the scalar getters; the
                # separate top-stack consumer migration removes those calls.
                GetMinValue=lambda: -0.00004,
                GetMaxValue=lambda: -0.00002,
            ),
        )

        def set_text(index, text):
            assert index == 4 and text == control.TEXT
            events.append("part_setter")
            if outcome == "setter_failure":
                raise primary
            model.text, model.dirty = text, True
            if outcome == "unrelated_change":
                model.raw += 0.000001

        model.display = NS(
            GetDimension2=lambda _: model.parameter,
            Type2=6,
            IsReferenceDim=lambda: False,
            IsHoleCallout=lambda: False,
            MarkedForDrawing=True,
            GetPrimaryPrecision2=lambda: 2,
            GetPrimaryTolPrecision2=lambda: 5,
            GetText=lambda index: model.text if index in (4, 8) else "",
            SetText=Mock(side_effect=set_text),
            GetLowerText=Mock(side_effect=AssertionError("no part LowerText")),
        )
        feature = NS(
            Name="ArborBoreProfile",
            GetFirstDisplayDimension=lambda: model.display,
            GetNextDisplayDimension=lambda _: None,
            GetNextFeature=None,
        )
        model.FirstFeature = feature
        model.FeatureByName = lambda _: feature
        model.GraphicsRedraw2 = Mock(side_effect=lambda: events.append("part_redraw"))

        def save(*args):
            assert args == (1, 0, 0)
            events.append("part_save")
            if outcome == "part_save_failure":
                return False, 2, 0
            Path(model.path).write_bytes(b"deliberately authored fit")
            part_saved[model.path] = model.text
            model.dirty = False
            return True, 0, 0

        model.Save3 = Mock(side_effect=save)
        parts.append(model)
        return model

    def dimensions(model, target, path):
        assert target == "alignment_pinion" and Path(model.path) == path
        return {
            "configuration": "Default",
            "dimensions": {
                control.DIMENSION: {
                    "full_name": model.parameter.FullName,
                    "value_system": round(model.raw, 12),
                    "tolerance_type": 2,
                }
            },
        }, {control.DIMENSION: model.parameter}

    monkeypatch.setattr(pilot, "source_dimensions", dimensions)

    def drawing_model(model, part, text):
        view = NS(
            GetName2=lambda: "Drawing View1",
            ReferencedDocument=part,
            ReferencedConfiguration="Default",
        )
        entities = (object(), object())
        annotation = NS(
            GetName=lambda: "ArborBoreDia",
            GetType=lambda: 4,
            OwnerType=0,
            Owner=view,
            Visible=1,
            IsDangling=lambda: False,
            GetAttachedEntityCount3=lambda: 2,
            GetAttachedEntityTypes=lambda: (1, 1),
            GetAttachedEntities3=lambda: entities,
        )
        model.text = text
        model.display = NS(
            Type2=6,
            IsReferenceDim=lambda: False,
            IsHoleCallout=lambda: False,
            GetDimension2=lambda _: part.parameter,
            GetDimension=lambda: part.parameter,
            GetAnnotation=lambda: annotation,
            GetText=lambda index: model.text if index in (4, 8) else "",
            SetText=Mock(side_effect=AssertionError("no drawing SetText")),
            SetLowerText=Mock(side_effect=AssertionError("no drawing SetLowerText")),
        )
        annotation.GetSpecificAnnotation = lambda: model.display
        view.GetAnnotations = lambda: (annotation,)
        sheet_view = NS(GetAnnotations=lambda: ())
        model.GetViews = lambda: ((sheet_view, view),)
        model.annotations, model.references = (annotation,), [part]
        model.front_view = view
        drawings.append(model)
        return model

    original_open = native.adapter.open_model

    async def opening(path):
        result = await original_open(path)
        model = native.adapter.currentModel
        if model.kind == 1:
            part_model(model)
            return result
        part_path, text = drawing_saved[path]
        part = part_model(Model(part_path, kind=1))
        native.app.documents.append(part)
        drawing_model(model, part, "" if outcome == "drawing_cold_loss" else text)
        return result

    native.adapter.open_model = opening
    baseline = Model(None, title="User dirty drawing", dirty=True)
    native.app.documents.append(baseline)
    native.app.ActiveDoc = baseline

    def create(adapter, **kwargs):
        part = adapter.currentModel
        model = drawing_model(
            Model(None, title="Owned drawing", dirty=True), part, part.text
        )
        native.app.documents.append(model)
        native.app.ActiveDoc = model
        adapter.currentModel = model

        def persist(path):
            Path(path).write_bytes(b"drawing output")
            if Path(path).suffix.upper() == ".SLDDRW":
                drawing_saved[path] = part.path, model.text
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
    original_callouts = Mock(side_effect=AssertionError("no production drawing setter"))
    monkeypatch.setattr(common, "set_dimension_callouts", original_callouts)
    original_verifier = common.verify_dimension_callouts
    monkeypatch.setattr(common, "set_dimension_precision", Mock())
    originals = {}
    for name in dict.fromkeys(boundaries.DRAWING_OPERATIONS[:-1]):
        originals[name] = Mock()
        monkeypatch.setattr(common, name, originals[name], raising=False)

    async def finalize(adapter, *, outputs):
        result = common.save_drawing(
            adapter, str(outputs.slddrw), pdf_path=str(outputs.pdf)
        )
        outputs.png.write_bytes(b"rendered")
        return {**result, "png": str(outputs.png)}

    originals["finalize_drawing"] = finalize
    monkeypatch.setattr(common, "finalize_drawing", finalize)
    original_save = common.save_drawing

    def witness(adapter, **kwargs):
        text = "" if outcome == "hidden_print" else adapter.currentModel.text
        return {
            "annotations": {
                "Drawing View1/ArborBoreDia": {
                    "generic": {
                        "texts": [{"value": line} for line in text.splitlines()]
                    }
                }
            }
        }

    monkeypatch.setattr(pilot, "drawing_witness", witness)
    monkeypatch.setattr(
        pilot,
        "compare_drawing_reopen",
        lambda before, after: {
            "status": "passed" if before == after else "failed",
            "rejected": [],
        },
    )

    async def callback(adapter):
        return await pilot.pilot(
            adapter,
            "frozen",
            sources,
            guards,
            tmp_path / "reports",
            targets=("alignment_pinion",),
            drawing_save=save_variant,
            source_observation=boundaries.SourceObservation.ALIGNMENT_SAVE,
            **(
                {}
                if production
                else {
                    "source_callout_authoring": control.SourceCalloutAuthoring.ALIGNMENT_FIT
                }
            ),
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
    assert report["sources_before"] == report["sources_after"]
    assert report["status"] == ("passed" if outcome == "passed" else "failed")
    assert native.app.documents == [baseline] and baseline.dirty
    assert all(part.display.GetLowerText.call_count == 0 for part in parts)
    assert all(
        model.display.SetText.call_count == model.display.SetLowerText.call_count == 0
        for model in drawings
    )
    assert common.save_drawing is original_save
    assert (
        common.verify_dimension_callouts
        is modules[0].verify_dimension_callouts
        is original_verifier
    )
    assert not hasattr(modules[0], "set_dimension_callouts")
    assert common.set_dimension_callouts is original_callouts
    original_callouts.assert_not_called()
    assert all(
        getattr(modules[0], name) is original for name, original in originals.items()
    )
    if production:
        assert "source_callout_authoring" not in trial
        assert all(
            part.display.SetText.call_count == part.Save3.call_count == 0
            for part in parts
        )
        assert events == []
        assert (
            trial["copy_hashes"]["copied"]
            == trial["copy_final"]
            == pilot.EXPECTED_PART_HASHES["alignment_pinion"]
        )
        assert trial["source_boundaries"]["callout_contract"] == "source_verifier_v1"
        rows = trial["source_boundaries"]["banks"]
        assert len(rows) == 9
        assert all(row["disk_sha256"] == trial["copy_final"] for row in rows)
        assert all(row["raw_system_values"] == [raw] for row in rows)
        assert all(
            row["dirty_before_read"] is row["dirty_after_read"] is False for row in rows
        )
        assert all(
            row["display"]["text"]["4"] == row["display"]["text"]["8"] == control.TEXT
            for row in rows
        )
        assert report["runtime_final_guard_errors"] == []
        assert parts[-1].parameter is not parts[0].parameter
        if outcome == "passed":
            assert trial["built"] == trial["reopened"]
        return
    authored = trial["source_callout_authoring"]
    assert authored["original_sha256"] == pilot.EXPECTED_PART_HASHES["alignment_pinion"]
    parts[0].display.SetText.assert_called_once_with(4, control.TEXT)
    if outcome in (
        "setter_failure",
        "unrelated_change",
        "part_save_failure",
        "part_cold_loss",
    ):
        assert authored["status"] == "failed" and "baseline" not in authored
        assert not drawings
        if outcome == "setter_failure":
            assert authored["error"] == repr(primary)
            assert events == ["part_setter"]
        return
    assert authored["status"] == "passed"
    assert trial["callout_contract"] == "source_verifier_v1"
    assert trial["source_boundaries"]["callout_contract"] == "source_verifier_v1"
    assert (
        authored["baseline"]["sha256"]
        == trial["copy_final"]
        != authored["original_sha256"]
    )
    assert report["runtime_final_guard_errors"] == []
    rows = trial["source_boundaries"]["banks"]
    assert len(rows) == 25
    assert all(row["disk_sha256"] == trial["copy_final"] for row in rows)
    assert all(
        row["dirty_before_read"] is row["dirty_after_read"] is False for row in rows
    )
    assert all(row["raw_system_values"] == [raw] for row in rows)
    assert all(
        row["display"]["text"]["4"] == row["display"]["text"]["8"] == control.TEXT
        for row in rows
    )
    assert events == ["part_setter", "part_redraw", "part_save"]
    if outcome == "passed":
        assert trial["callout_storage_built"] == trial["callout_storage_reopened"]
        assert parts[-1].parameter is not parts[0].parameter
