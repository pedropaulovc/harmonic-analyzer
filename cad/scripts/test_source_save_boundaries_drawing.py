"""Bounded source reads preserve actual recipe writes and fail-closed pilot gates."""

from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from diagnostics import _source_save_boundaries as control
from diagnostics._model_dimension_coverage import SemanticCoverage
from diagnostics import probe_datum_policy_recipes as pilot


@pytest.fixture
def bank(tmp_path, monkeypatch):
    monkeypatch.setattr(control, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(
        "diagnostics._source_dimension_snapshot._early_bound", lambda value, _: value
    )
    path = tmp_path / "alignment-copy.SLDPRT"
    path.write_bytes(b"exact original")
    native_tol = NS(
        Type=2,
        GetMinValue2=lambda: (0, -0.00004),
        GetMaxValue2=lambda: (0, -0.00002),
    )
    dimension = NS(
        FullName="ArborBoreDia@ArborBoreProfile@alignment-copy.Part",
        Tolerance=native_tol,
        GetToleranceType=lambda: native_tol.Type,
        GetSystemValue3=Mock(return_value=(0.008000000001785,)),
    )
    state = NS(dirty=False, text="", precision=-2)
    display = NS(
        GetDimension2=lambda index: dimension,
        IsHoleCallout=lambda: False,
        Type2=6,
        GetPrimaryPrecision2=lambda: state.precision,
        GetPrimaryTolPrecision2=lambda: -3,
        GetText=lambda part: state.text if part in (4, 8) else "",
    )
    feature = NS(
        Name="ArborBoreProfile",
        GetFirstDisplayDimension=Mock(return_value=display),
        GetNextDisplayDimension=Mock(return_value=None),
    )
    source = NS(
        GetSaveFlag=lambda: state.dirty, FeatureByName=Mock(return_value=feature)
    )
    adapter = NS(
        swApp=NS(
            IsSame=lambda a, b: int(a is b), GetOpenDocumentByName=lambda _: source
        )
    )
    native = {
        "configuration": "Default",
        "dimensions": {
            control.DIMENSION: {
                "full_name": dimension.FullName,
                "value_system": 0.008000000002,
                "tolerance_type": 2,
                "designation": "other",
            }
        },
    }
    handles = {control.DIMENSION: dimension}
    reader = Mock(side_effect=lambda: (deepcopy(native), handles.copy()))
    events = []

    def callouts(actual, *args, **kwargs):
        assert actual is adapter
        events.append("callouts")
        state.text, state.dirty = "THRU - REAM\nPRESS FIT", True

    def precision(actual, *args, **kwargs):
        assert actual is adapter
        events.append("precision")
        state.precision = 2

    @contextmanager
    def artifact(kind, output):
        events.append(f"enter:{kind}")
        yield
        events.append(f"exit:{kind}")

    outputs = NS(slddrw=tmp_path / "owned.SLDDRW", pdf=tmp_path / "owned.pdf")

    def save(actual, native_path, *, pdf_path, artifact_context):
        assert actual is adapter
        assert native_path == str(outputs.slddrw)
        assert pdf_path == str(outputs.pdf)
        for kind, target in (("drawing", native_path), ("pdf", pdf_path)):
            with artifact_context(kind, target):
                events.append(f"save:{kind}")
                if kind == "drawing":
                    path.write_bytes(b"native referenced save")
                    state.dirty = False
                Path(target).write_bytes(kind.encode())
        return {"drawing": native_path, "pdf": pdf_path}

    monkeypatch.setattr(control.drawing, "set_dimension_callouts", callouts)
    monkeypatch.setattr(control.drawing, "set_dimension_precision", precision)
    monkeypatch.setattr(control.drawing, "save_drawing", save)
    module = NS(
        set_dimension_callouts=callouts,
        set_dimension_precision=precision,
        OUTPUTS=outputs,
    )
    trial = {"target": "alignment_pinion", "copy_source": str(path)}
    saved = []
    observer = control.SourceSaveBoundaries(
        adapter,
        module,
        trial,
        lambda: saved.append(deepcopy(trial)),
        source,
        deepcopy(native),
        handles.copy(),
        reader,
        callout_contract=control.CalloutContract.DRAWING_SETTER_V1,
    )
    return NS(**locals())


def test_all_nine_banks_preserve_native_operations_and_immutable_copy_gate(
    bank, monkeypatch
):
    before_hash = pilot.attachments.file_digest(bank.path)
    monkeypatch.setitem(pilot.EXPECTED_PART_HASHES, "alignment_pinion", before_hash)
    with bank.observer.observe():
        bank.module.set_dimension_callouts(bank.adapter, [], {})
        bank.module.set_dimension_precision(bank.adapter, [], {})
        control.drawing.save_drawing(
            bank.adapter,
            str(bank.outputs.slddrw),
            pdf_path=str(bank.outputs.pdf),
            artifact_context=bank.artifact,
        )
    bank.observer.require_used()
    rows = bank.trial["source_boundaries"]["banks"]
    assert [r["boundary"] for r in rows] == [
        "initial",
        *(
            f"{side}_{stage}"
            for stage in control.STAGES
            for side in ("before", "after")
        ),
    ]
    assert rows[1]["dirty_before_read"] is False
    assert rows[2]["dirty_before_read"] is True
    assert rows[2]["display"]["text"]["4"] == "THRU - REAM\nPRESS FIT"
    assert rows[4]["display"]["primary_precision"] == 2
    assert rows[5]["dirty_after_read"] is True
    assert rows[6]["dirty_after_read"] is False
    assert rows[5]["disk_sha256"] == before_hash
    assert rows[6]["disk_sha256"] != before_hash
    assert rows[7]["disk_sha256"] == rows[8]["disk_sha256"] == rows[6]["disk_sha256"]
    assert all(r["source"] == bank.native for r in rows)
    assert all(r["raw_system_values"] == (0.008000000001785,) for r in rows)
    assert bank.dimension.GetSystemValue3.call_count == 9
    assert bank.dimension.GetSystemValue3.call_args.args == (3, "Default")
    assert all(r["read_seconds"] >= 0 for r in rows)
    assert bank.events == [
        "callouts",
        "precision",
        "enter:drawing",
        "save:drawing",
        "exit:drawing",
        "enter:pdf",
        "save:pdf",
        "exit:pdf",
    ]
    assert bank.feature.GetFirstDisplayDimension.call_count == 1
    assert bank.feature.GetNextDisplayDimension.call_count == 1
    assert bank.reader.call_count == 9
    assert len(bank.saved[-1]["source_boundaries"]["banks"]) == 9
    assert control.drawing.save_drawing is bank.save
    assert bank.module.set_dimension_callouts is bank.callouts
    with pytest.raises(RuntimeError, match="no source save is authorized"):
        pilot.require_copy_hash(bank.trial, "after_recipe")


@pytest.mark.parametrize(
    "mode",
    [
        "missing",
        "duplicate",
        "cycle",
        "null_dimension",
        "wrong_identity",
        "wrong_feature",
    ],
)
def test_calibration_fails_before_recipe_write(bank, mode):
    if mode == "missing":
        bank.feature.GetFirstDisplayDimension.return_value = None
    if mode == "duplicate":
        bank.feature.GetNextDisplayDimension.side_effect = [
            NS(**vars(bank.display)),
            None,
        ]
    if mode == "cycle":
        bank.feature.GetNextDisplayDimension.return_value = bank.display
    if mode == "null_dimension":
        bank.display.GetDimension2 = lambda _: None
    if mode == "wrong_identity":
        bank.display.GetDimension2 = lambda _: NS(**vars(bank.dimension))
    if mode == "wrong_feature":
        bank.feature.Name = "Unrelated"
    with pytest.raises(RuntimeError):
        with bank.observer.observe():
            pytest.fail("recipe must not run")
    assert bank.events == []
    assert "error" in bank.saved[-1]["source_boundaries"]["banks"][-1]


@pytest.mark.parametrize(
    "mode",
    [
        "source",
        "value",
        "tolerance",
        "limits",
        "parameter",
        "display",
        "hole",
        "text",
        "precision",
        "nonfinite",
        "type",
        "nonfinite_value",
    ],
)
def test_post_read_rejects_semantic_identity_or_unsupported_read(bank, mode):
    bank.observer.capture("initial")
    if mode == "source":
        bank.adapter.swApp.GetOpenDocumentByName = lambda _: object()
    if mode == "value":
        bank.native["dimensions"][control.DIMENSION]["value_system"] += 0.001
    if mode == "tolerance":
        bank.native_tol.Type = 1
    if mode == "limits":
        bank.native_tol.GetMaxValue2 = lambda: (0, 0.0)
    if mode == "parameter":
        bank.handles[control.DIMENSION] = object()
    if mode == "display":
        bank.display.GetDimension2 = lambda _: object()
    if mode == "hole":
        bank.display.IsHoleCallout = lambda: True
    if mode == "text":
        bank.display.GetText = lambda _: 42
    if mode == "precision":
        bank.display.GetPrimaryPrecision2 = lambda: float("nan")
    if mode == "nonfinite":
        bank.native_tol.GetMinValue2 = lambda: (0, float("nan"))
    if mode == "type":
        bank.display.Type2 = 4
    if mode == "nonfinite_value":
        bank.native["dimensions"][control.DIMENSION]["value_system"] = float("inf")
    with pytest.raises(RuntimeError):
        bank.observer.capture("after_native_save")
    assert "error" in bank.saved[-1]["source_boundaries"]["banks"][-1]


def test_primary_operation_error_survives_failing_post_evidence(bank):
    primary = RuntimeError("native operation failed")
    with pytest.raises(RuntimeError, match="native operation failed") as caught:
        with bank.observer.observe():
            with bank.observer.boundary("callouts"):
                bank.display.GetText = Mock(side_effect=RuntimeError("getter broke"))
                raise primary
    assert caught.value is primary
    assert "getter broke" in primary.__notes__[0]
    assert (
        bank.saved[-1]["source_boundaries"]["operation_errors"][0]["boundary"]
        == "callouts"
    )
    assert "getter broke" in bank.saved[-1]["source_boundaries"]["banks"][-1]["error"]
    assert control.drawing.save_drawing is bank.save


@pytest.mark.parametrize(
    "raw",
    [
        None,
        (),
        (1.0, 2.0),
        (True,),
        ("0.008",),
        (float("nan"),),
        (float("inf"),),
        (0.008000000001786,),
    ],
)
def test_raw_dimension_shape_and_unrounded_change_reject(bank, raw):
    bank.observer.capture("initial")
    bank.dimension.GetSystemValue3.return_value = raw
    with pytest.raises(RuntimeError, match="raw"):
        bank.observer.capture("after_callouts")
    assert bank.saved[-1]["source_boundaries"]["banks"][-1]["raw_system_values"] == raw


def test_read_failure_survives_checkpoint_failure(bank):
    bank.reader.side_effect = RuntimeError("source read failed")
    bank.observer.checkpoint = Mock(side_effect=OSError("cannot write report"))
    with pytest.raises(RuntimeError, match="source read failed") as caught:
        bank.observer.capture("initial")
    assert "cannot write report" in caught.value.__notes__[0]


def test_getter_dirty_transition_is_recorded_and_rejected(bank):
    bank.source.GetSaveFlag = Mock(side_effect=[False, True])
    with pytest.raises(RuntimeError, match="getters changed"):
        bank.observer.capture("initial")
    assert bank.saved[-1]["source_boundaries"]["banks"][-1]["dirty_after_read"] is True


def test_optional_drawing_bank_skips_source_only_initial_and_records_text_loss(bank):
    drawing_reader = Mock(side_effect=[{"lower_text": "fit"}, {"lower_text": ""}])
    bank.observer.drawing_reader = drawing_reader
    bank.observer.capture("initial")
    drawing_reader.assert_not_called()
    bank.observer.capture("before_precision")
    bank.observer.capture("after_precision")
    rows = bank.saved[-1]["source_boundaries"]["banks"]
    assert "drawing" not in rows[0]
    assert rows[1]["drawing"] == {"lower_text": "fit"}
    assert rows[2]["drawing"] == {"lower_text": ""}
    assert drawing_reader.call_count == 2


def test_drawing_reader_dirtiness_is_inside_source_getter_guard(bank):
    def read():
        bank.state.dirty = True
        return {"lower_text": ""}

    bank.observer.drawing_reader = read
    with pytest.raises(RuntimeError, match="getters changed"):
        bank.observer.capture("before_precision")
    row = bank.saved[-1]["source_boundaries"]["banks"][-1]
    assert row["drawing"] == {"lower_text": ""}
    assert row["dirty_after_read"] is True


def test_drawing_reader_failure_is_checkpointed_without_losing_source_bank(bank):
    bank.observer.drawing_reader = Mock(side_effect=RuntimeError("drawing read failed"))
    with pytest.raises(RuntimeError, match="drawing read failed"):
        bank.observer.capture("before_precision")
    row = bank.saved[-1]["source_boundaries"]["banks"][-1]
    assert row["source"] == bank.native
    assert "drawing read failed" in row["error"]


def test_missing_or_out_of_order_operation_fails(bank):
    with pytest.raises(RuntimeError, match="all four"):
        bank.observer.require_used()
    with pytest.raises(RuntimeError, match="order/count"):
        with bank.observer.boundary("native_save"):
            pytest.fail("save must not run")


@pytest.mark.parametrize(
    "targets", [(), ("channel_lever",), ("alignment_pinion", "rocker_arm")]
)
def test_scope_fails_before_native_environment(monkeypatch, tmp_path, targets):
    environment = Mock(side_effect=AssertionError("must not attach"))
    monkeypatch.setattr(pilot, "require_owned_diagnostic_environment", environment)
    argv = [
        "--source-root",
        str(tmp_path),
        "--guard-root",
        str(tmp_path),
        "--source-observation",
        "alignment_save",
    ]
    for target in targets:
        argv.extend(("--target", target))
    with pytest.raises(ValueError, match="only alignment_pinion"):
        pilot.main(argv)
    environment.assert_not_called()


@pytest.mark.parametrize("route", ["parent", "worker"])
def test_explicit_cli_forwards_variant_without_changing_factory_or_guards(
    monkeypatch, tmp_path, route
):
    import asyncio
    import sys

    monkeypatch.setattr(pilot, "require_owned_diagnostic_environment", lambda: None)
    monkeypatch.setattr(pilot.benchmark, "revision", lambda _: "frozen")
    monkeypatch.setattr(
        pilot.benchmark,
        "recipe_source",
        lambda *_: "from _drawing_common import set_dimension_callouts",
    )
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
        "--source-root",
        str(tmp_path),
        "--guard-root",
        str(tmp_path),
        "--target",
        "alignment_pinion",
        "--source-observation",
        "alignment_save",
    ]
    if route == "worker":
        argv.append("--worker")
    assert pilot.main(argv) == 0
    if route == "worker":
        assert seen == [
            {
                "targets": ("alignment_pinion",),
                "source_observation": control.SourceObservation.ALIGNMENT_SAVE,
            }
        ]
        return
    command = parent.call_args.args[0]
    assert command[command.index("--source-observation") + 1] == "alignment_save"
    assert parent.call_args.kwargs["com"] is True


@pytest.mark.parametrize("save_variant", [None, "legacy", "extension_silent"])
@pytest.mark.asyncio
async def test_pilot_wraps_real_recipe_and_retains_banks_before_hash_failure(
    tmp_path, monkeypatch, save_variant
):
    from diagnostics import _native_drawing_save_control as native_save
    from test_datum_policy_recipes_drawing import Adapter, fixture_sources
    from test_benchmark_drawing_recipes import recipe

    monkeypatch.setattr(pilot, "ORDER", ("alignment_pinion",))
    sources, guards = fixture_sources(tmp_path, monkeypatch)
    monkeypatch.setitem(
        pilot.TARGETS,
        "alignment_pinion",
        NS(view_roles={}, entity_labels=(), coverage=SemanticCoverage.GEOMETRY),
    )
    monkeypatch.setattr(
        pilot.benchmark,
        "recipe_source",
        lambda *_: (
            recipe(Path("unused.SLDPRT"))
            + "\nfrom _drawing_common import set_dimension_callouts\n"
        ),
    )
    monkeypatch.setattr(pilot.benchmark, "revision", lambda _: "frozen")
    monkeypatch.setattr(pilot, "helper_fingerprints", lambda: {"helper": "frozen"})
    monkeypatch.setattr(pilot, "adapter_fingerprints", lambda: {"adapter": "frozen"})
    handle = object()
    monkeypatch.setattr(
        pilot,
        "source_dimensions",
        lambda *_: ({"configuration": "Default", "dimensions": {}}, {"one": handle}),
    )
    events = []

    @contextmanager
    def save_control(actual_adapter, variant, *, records):
        assert actual_adapter is adapter
        assert variant is native_save.DrawingSave(save_variant)
        assert records == []
        events.append("save_enter")
        yield
        events.append("save_exit")

    monkeypatch.setattr(native_save, "native_drawing_save_control", save_control)

    class Observer:
        def __init__(
            self,
            adapter,
            module,
            trial,
            checkpoint,
            source,
            before,
            handles,
            reader,
            *,
            callout_contract,
        ):
            assert callout_contract is control.CalloutContract.DRAWING_SETTER_V1
            assert source == adapter.currentModel == trial["copy_source"]
            assert handles == {"one": handle}
            assert reader()[0] == before
            self.trial, self.checkpoint = trial, checkpoint

        @contextmanager
        def observe(self):
            events.append("enter")
            yield
            self.trial["source_boundaries"] = {"banks": ["retained"]}
            self.checkpoint()
            events.append("exit")

        def require_used(self):
            events.append("checked")

    monkeypatch.setattr(control, "SourceSaveBoundaries", Observer)
    adapter = Adapter("source_drift")
    with pytest.raises(RuntimeError, match="no source save is authorized"):
        await pilot.pilot(
            adapter,
            "frozen",
            sources,
            guards,
            tmp_path / "reports",
            targets=("alignment_pinion",),
            source_observation=control.SourceObservation.ALIGNMENT_SAVE,
            drawing_save=(
                native_save.DrawingSave(save_variant) if save_variant else None
            ),
        )
    import json

    (path,) = (tmp_path / "reports").glob("*/pilot.json")
    result = json.loads(path.read_text())
    assert result["status"] == "failed"
    assert result["trials"][0]["source_boundaries"]["banks"] == ["retained"]
    assert result["sources_before"] == result["sources_after"]
    assert result["runtime_final_guard_errors"] == [
        "RuntimeError('final owned source copy changed on disk')"
    ]
    expected = ["enter", "exit", "checked"]
    if save_variant is not None:
        expected = ["save_enter", "enter", "exit", "save_exit", "checked"]
        assert result["trials"][0]["drawing_save"] == save_variant
        assert result["trials"][0]["native_save_calls"] == []
    assert events == expected


@pytest.mark.parametrize("variant", ["legacy", "extension_silent"])
def test_save_cli_requires_source_banks_before_environment(
    monkeypatch, tmp_path, variant
):
    environment = Mock(side_effect=AssertionError("must not attach"))
    monkeypatch.setattr(pilot, "require_owned_diagnostic_environment", environment)
    with pytest.raises(ValueError, match="alignment_save observations"):
        pilot.main([
            "--source-root", str(tmp_path), "--guard-root", str(tmp_path),
            "--target", "alignment_pinion", "--drawing-save", variant,
        ])
    environment.assert_not_called()


@pytest.mark.parametrize("route", ["parent", "worker"])
@pytest.mark.parametrize("variant", ["legacy", "extension_silent"])
def test_save_cli_forwards_explicit_enum(monkeypatch, tmp_path, route, variant):
    import asyncio
    import sys
    from diagnostics._native_drawing_save_control import DrawingSave

    monkeypatch.setattr(pilot, "require_owned_diagnostic_environment", lambda: None)
    monkeypatch.setattr(pilot.benchmark, "revision", lambda _: "frozen")
    monkeypatch.setattr(
        pilot.benchmark,
        "recipe_source",
        lambda *_: "from _drawing_common import set_dimension_callouts",
    )
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
        "--drawing-save", variant,
    ]
    if route == "worker":
        argv.append("--worker")
    assert pilot.main(argv) == 0
    if route == "worker":
        assert seen == [{
            "targets": ("alignment_pinion",),
            "source_observation": control.SourceObservation.ALIGNMENT_SAVE,
            "drawing_save": DrawingSave(variant),
        }]
        return
    command = parent.call_args.args[0]
    assert command[command.index("--drawing-save") + 1] == variant
    assert command[command.index("--source-observation") + 1] == "alignment_save"
    assert parent.call_args.kwargs["com"] is True


def test_direct_save_selection_rejects_string_and_wrong_targets():
    from diagnostics._native_drawing_save_control import DrawingSave

    for variant, order in (
        ("extension_silent", ("alignment_pinion",)),
        (DrawingSave.EXTENSION_SILENT, ("channel_lever",)),
        (DrawingSave.LEGACY, ("alignment_pinion", "rocker_arm")),
    ):
        with pytest.raises(ValueError, match="drawing-save control"):
            pilot.require_drawing_save(
                variant, control.SourceObservation.ALIGNMENT_SAVE, order
            )
