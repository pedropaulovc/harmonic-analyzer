"""Offline evidence/ownership contracts for the crank-arm-only native probe."""

import asyncio
from contextlib import asynccontextmanager
from enum import Enum
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import probe_crank_arm_entities as probe

# Reuse the existing actual-recipe composition fixture, not a second runner.
from test_crank_arm_candidate_drawing import candidate as candidate


class EvidenceKind(Enum):
    DIMENSION = "dimension"


@pytest.fixture
def native(monkeypatch, tmp_path):
    source = tmp_path / "crank-arm.SLDPRT"
    source.write_bytes(b"isolated source fixture")
    token = source.with_name(".crank-arm.execution")
    token.write_text(probe.sha(source), encoding="utf-8")
    directory = tmp_path / "evidence"
    directory.mkdir()
    model = SimpleNamespace(
        GetType=lambda: 1,
        GetPathName=lambda: str(source),
        GetSaveFlag=Mock(return_value=False),
    )
    app = SimpleNamespace(
        GetOpenDocumentByName=Mock(return_value=model),
        IsSame=Mock(side_effect=lambda left, right: int(left is right)),
        GetProcessID=lambda: 123,
        RevisionNumber=lambda: "34.3.0",
    )
    ownership = SimpleNamespace(
        register_directory=Mock(),
        register_source=Mock(),
        evidence=lambda: {"owned": []},
    )

    async def open_model(path):
        assert path == str(source)
        return SimpleNamespace(is_success=True, data=model)

    adapter = SimpleNamespace(
        currentModel=model, swApp=app, ownership=ownership, open_model=open_model
    )
    observed = {
        "configuration": "Default",
        "dimensions": {"Depth@Arm": {"raw": 0.008, "kind": EvidenceKind.DIMENSION}},
    }
    required = {
        "Depth@Arm": {"value_system": 0.008, "tolerance_type": EvidenceKind.DIMENSION}
    }
    snapshot = Mock(return_value=(observed, {}))
    dimensions = Mock(return_value=(required, {}))
    monkeypatch.setattr(probe, "SOURCE", source)
    monkeypatch.setattr(probe, "TOKEN", token)
    monkeypatch.setattr(probe, "EXPECTED_SOURCE_SHA", probe.sha(source), raising=False)
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    monkeypatch.setattr(probe, "revision", lambda path: f"revision:{Path(path).name}")
    monkeypatch.setattr(probe, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(probe, "dimension_snapshot", snapshot)
    monkeypatch.setattr(probe, "part_dimensions", dimensions)
    return SimpleNamespace(
        source=source,
        token=token,
        directory=directory,
        model=model,
        adapter=adapter,
        observed=observed,
        required=required,
        snapshot=snapshot,
        dimensions=dimensions,
    )


def test_source_snapshot_preserves_full_and_required_readbacks(native):
    result = probe.source_snapshot(native.adapter, native.source)
    assert result == {
        "dirty_before": False,
        "dirty_after": False,
        "observed_dimensions": native.observed,
        "required_dimensions": native.required,
    }
    native.snapshot.assert_called_once_with(
        native.adapter.swApp,
        native.model,
        native.source,
        required=probe.DRAWING_DIMENSIONS,
    )
    native.dimensions.assert_called_once_with(
        native.adapter, native.source, "Default", targets=probe.DRAWING_DIMENSIONS
    )


@pytest.mark.parametrize(
    "fault", ["document_type", "path", "different", "indeterminate"]
)
def test_source_snapshot_rejects_wrong_exact_owner_before_reading(native, fault):
    if fault == "document_type":
        native.model.GetType = lambda: 2
    if fault == "path":
        native.model.GetPathName = lambda: str(
            native.source.with_name("foreign.SLDPRT")
        )
    if fault in {"different", "indeterminate"}:
        native.adapter.swApp.IsSame.side_effect = None
        native.adapter.swApp.IsSame.return_value = 0 if fault == "different" else -1
    with pytest.raises(RuntimeError, match="wrong exact source owner"):
        probe.source_snapshot(native.adapter, native.source)
    native.snapshot.assert_not_called()
    native.dimensions.assert_not_called()
    native.model.GetSaveFlag.assert_not_called()


def test_provenance_requires_original_source_token_and_records_imports(native):
    record = probe.provenance()
    assert (
        record["source_sha256"] == record["execution_token"] == probe.sha(native.source)
    )
    assert record["source_size"] == native.source.stat().st_size
    assert Path(record["recipe_import"]).name == "draw_crank_arm.py"
    assert Path(record["adapter_import"]).name == "pywin32_adapter.py"
    assert record["root_commit"] and record["adapter_commit"]
    native.token.write_text("different identity", encoding="utf-8")
    with pytest.raises(RuntimeError, match="token"):
        probe.provenance()


def test_matching_replacement_source_and_token_cannot_replace_original_pin(native):
    native.source.write_bytes(b"different source even though its token matches")
    native.token.write_text(probe.sha(native.source), encoding="utf-8")
    with pytest.raises(RuntimeError):
        probe.provenance()


def test_capture_source_serializes_enum_evidence_without_losing_readbacks(native):
    result = asyncio.run(probe.capture_source(native.adapter, native.directory))
    report = json.loads(Path(result["report"]).read_text(encoding="utf-8"))
    assert report["status"] == "captured"
    assert (
        report["source_snapshot"]["observed_dimensions"]["dimensions"]["Depth@Arm"][
            "kind"
        ]
        == "dimension"
    )
    assert (
        report["source_snapshot"]["required_dimensions"]["Depth@Arm"]["tolerance_type"]
        == "dimension"
    )
    assert report["source_sha256_after"] == report["provenance"]["source_sha256"]
    assert report["execution_token_after"] == report["provenance"]["execution_token"]
    native.adapter.ownership.register_directory.assert_called_once_with(
        native.directory
    )
    native.adapter.ownership.register_source.assert_called_once_with(native.source)


def test_json_evidence_rejects_unsupported_values_instead_of_stringifying_them():
    with pytest.raises(TypeError, match="unsupported evidence type"):
        json.dumps({"opaque": object()}, default=probe.json_default)


def test_capture_source_records_failed_snapshot_and_reraises_original(native):
    failure = RuntimeError("raw dimension read failed")
    native.snapshot.side_effect = failure
    with pytest.raises(RuntimeError) as raised:
        asyncio.run(probe.capture_source(native.adapter, native.directory))
    assert raised.value is failure
    report = json.loads(
        (native.directory / "measurements.json").read_text(encoding="utf-8")
    )
    assert report["status"] == "failed" and report["error"] == repr(failure)
    assert report["provenance"]["source_sha256"] == report["source_sha256_after"]


def test_report_write_failure_does_not_replace_original_snapshot_error(
    native, monkeypatch
):
    failure = RuntimeError("original dimension read failure")
    native.snapshot.side_effect = failure
    original_write = Path.write_text

    def write(path, *args, **kwargs):
        if path.name == "measurements.json":
            raise OSError("report disk unavailable")
        return original_write(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", write)
    with pytest.raises(Exception) as raised:
        asyncio.run(probe.capture_source(native.adapter, native.directory))
    errors = getattr(raised.value, "exceptions", (raised.value,))
    assert errors[0] is failure, "report persistence must not hide the native failure"


@pytest.mark.parametrize(
    "snapshot_failure", [None, RuntimeError("attachment snapshot failed")]
)
def test_capture_drawing_uses_owned_copy_and_retains_partial_evidence(
    native, monkeypatch, snapshot_failure
):
    import draw_crank_arm as recipe
    from diagnostics import probe_drawing_attachments as attachments
    from diagnostics import probe_datum_shoulder as shoulder

    original = native.directory.parent / "baseline.SLDDRW"
    original.write_bytes(b"original drawing")
    monkeypatch.setattr(recipe, "OUTPUTS", SimpleNamespace(slddrw=original))
    drawing = object()
    opened = []

    @asynccontextmanager
    async def open_drawing(adapter, path):
        assert adapter is native.adapter
        assert path.parent == native.directory and path != original
        assert path.read_bytes() == original.read_bytes()
        opened.append(("open", path))
        try:
            yield drawing
        finally:
            opened.append(("close", path))

    def snapshot(model, *, app):
        assert model is drawing and app is native.adapter.swApp
        if snapshot_failure is not None:
            raise snapshot_failure
        return {"kind": EvidenceKind.DIMENSION}

    monkeypatch.setattr(attachments, "open_drawing", open_drawing)
    monkeypatch.setattr(attachments, "snapshot", snapshot)
    monkeypatch.setattr(attachments, "layout", lambda model: {"sheet_scale": [2, 1]})
    monkeypatch.setattr(
        shoulder, "all_annotation_layout", lambda adapter: ({"annotations": []}, {})
    )
    if snapshot_failure is None:
        asyncio.run(probe.capture_drawing(native.adapter, native.directory))
    if snapshot_failure is not None:
        with pytest.raises(RuntimeError) as raised:
            asyncio.run(probe.capture_drawing(native.adapter, native.directory))
        assert raised.value is snapshot_failure
    report = json.loads(
        (native.directory / "measurements.json").read_text(encoding="utf-8")
    )
    assert report["status"] == ("captured" if snapshot_failure is None else "failed")
    assert [operation for operation, _ in opened] == ["open", "close"]
    assert original.read_bytes() == b"original drawing"
    assert [
        call.args[0] for call in native.adapter.ownership.register_source.call_args_list
    ] == [native.source, original]
    if snapshot_failure is None:
        assert report["attachments"] == {"kind": "dimension"}
        assert report["source_snapshot"]["dirty_after"] is False
    if snapshot_failure is not None:
        assert report["error"] == repr(snapshot_failure)


def test_worker_dispatches_complete_source_capture_through_owned_runner(
    native, monkeypatch
):
    calls = []
    monkeypatch.setattr(probe, "require_owned_diagnostic_environment", lambda: None)
    monkeypatch.setenv("HARMONIC_COM_SEAT", "offline-parent-fixture")

    def runner(callback):
        calls.append("owned runner")
        return asyncio.run(callback(native.adapter))

    monkeypatch.setattr(probe, "run_copy_diagnostic", runner)
    result = probe.main(["source", "--worker"])
    assert calls == ["owned runner"]
    report_path = Path(result["report"])
    assert report_path.is_relative_to(probe.ROOT / "cad/out/reports")
    assert json.loads(report_path.read_text(encoding="utf-8"))["status"] == "captured"


# Independent native receipt values, including the measured float above nominal.
MANUFACTURING_DIMENSIONS = (
    ("arm-width overall", "Right", 0.016, 0, (0, 0)),
    ("shaft-to-handle-pivot location", "Front", 0.0750000001144, 1, (1, 1)),
    ("handle-pivot transverse location", "Front", 0.008, 1, (0, 1)),
    ("dimple transverse location from datum C", "Front", 0.008, 0, (0, 1)),
    ("cross-hole station from datum A", "Top", 0.004, 1, (0, 1)),
)


@pytest.fixture
def manufacturing(monkeypatch, tmp_path):
    """A complete 13-dimension native-shaped drawing; no cad/out receipts needed."""
    from diagnostics import probe_drawing_attachments as attachments

    monkeypatch.setattr(probe, "_early_bound", lambda obj, _kind: obj)
    monkeypatch.setattr(attachments, "_early_bound", lambda obj, _kind: obj)
    views, recorded, handles, annotations = {}, {}, {}, {}

    def add(
        label, view_name, value, basic=0, arcs=(0, 0), *, full_name=None, hole=False
    ):
        index = len(handles)
        annotation_name = f"Dimension{index}"
        key = f"{view_name}/{annotation_name}"
        tolerance = SimpleNamespace(
            Type=basic, GetMinValue=lambda: 0.0, GetMaxValue=lambda: 0.0
        )
        dimension = SimpleNamespace(
            FullName=full_name or f"D{index}@Drawing",
            Tolerance=tolerance,
            GetSystemValue2=Mock(return_value=value),
            GetSystemValue3=Mock(return_value=(value,)),
            GetArcEndCondition=Mock(side_effect=lambda endpoint: arcs[endpoint - 1]),
        )
        display = SimpleNamespace(
            GetDimension2=Mock(return_value=dimension),
            IsReferenceDim=Mock(return_value=full_name is None),
            IsHoleCallout=Mock(return_value=hole),
            ShowDimensionValue=True,
            GetPrimaryPrecision2=lambda: 3,
            GetPrimaryTolPrecision2=lambda: 2,
            GetText=Mock(return_value=""),
        )
        if hole:
            display.GetText.side_effect = AssertionError(
                "GetText does not support hole callouts"
            )
        annotation = SimpleNamespace(
            GetType=lambda: 4,
            GetName=lambda: annotation_name,
            GetSpecificAnnotation=lambda: display,
        )
        if view_name not in views:
            views[view_name] = SimpleNamespace(
                GetName2=lambda: view_name,
                GetUniqueName=lambda: f"Unique-{view_name}",
                GetAnnotations=Mock(return_value=[]),
                ReferencedConfiguration="Default",
            )
        views[view_name].GetAnnotations.return_value.append(annotation)
        recorded[label] = (view_name, annotation_name)
        handles[label] = SimpleNamespace(
            dimension=dimension, display=display, annotation=annotation
        )
        annotations[key] = {"semantic": {"texts": [{"text": "THRU"}] if hole else []}}

    for label, view, value, basic, arcs in MANUFACTURING_DIMENSIONS:
        add(label, view, value, basic, arcs)
    add("crank-arm cross-hole", "Top", 0.004623, hole=True)
    add("handle pivot hole", "Front", 0.005953125, hole=True)
    for feature, names in probe.DRAWING_DIMENSIONS.items():
        for name in sorted(names):
            add(
                name,
                "Right" if name == "Depth" else "Front",
                0.008,
                full_name=f"{name}@{feature}@crank-arm.Part",
            )
    # Non-dimension annotations must not be interpreted as IDisplayDimension.
    views["Front"].GetAnnotations.return_value.append(
        SimpleNamespace(GetType=lambda: 1)
    )
    sheet = SimpleNamespace(GetName2=lambda: "Sheet1")
    model = SimpleNamespace(GetViews=lambda: ((sheet, *views.values()),))
    receipt = {
        "status": "captured",
        "provenance": {"source_sha256": probe.EXPECTED_SOURCE_SHA},
        "attachments": {
            "dimensions": {
                f"Sheet1/{'/'.join(recorded[label])}/4": {
                    "components": [{"value_system": value}]
                }
                for label, value in (
                    ("arm-width overall", 0.016),
                    ("shaft-to-handle-pivot location", 0.075000000114),
                    ("handle-pivot transverse location", 0.008),
                    ("dimple transverse location from datum C", 0.008),
                    ("cross-hole station from datum A", 0.004),
                )
            }
        },
    }
    receipt_path = tmp_path / "native-baseline-receipt.json"

    def write_receipt():
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        monkeypatch.setattr(
            probe, "BASELINE_DRAWING_REPORT_SHA", probe.sha(receipt_path)
        )

    monkeypatch.setattr(probe, "BASELINE_DRAWING_REPORT", receipt_path)
    write_receipt()

    def collect():
        return {
            "dimensions": probe.drawing_dimensions(model),
            "annotations": annotations,
            "sheet": (0.4318, 0.2794, 2.0, 1.0),
        }

    return SimpleNamespace(
        model=model,
        views=views,
        recorded=recorded,
        handles=handles,
        collect=collect,
        receipt=receipt,
        receipt_path=receipt_path,
        write_receipt=write_receipt,
    )


def test_actual_dimension_collector_and_manufacturing_validator_share_native_keys(
    manufacturing,
):
    row = manufacturing.collect()
    assert len(row["dimensions"]) == 13
    assert row["dimensions"].keys() == row["annotations"].keys()
    assert all(
        not key.startswith("Sheet1/") and "Unique-" not in key
        for key in row["dimensions"]
    )
    probe.require_manufacturing(row, manufacturing.recorded)
    key = "/".join(manufacturing.recorded["shaft-to-handle-pivot location"])
    assert row["dimensions"][key]["value_system"] == 0.0750000001144
    for handle in manufacturing.handles.values():
        handle.display.GetDimension2.assert_called_once_with(0)
        if handle.display.IsReferenceDim.return_value:
            handle.dimension.GetSystemValue2.assert_called_once_with("")
            handle.dimension.GetSystemValue3.assert_not_called()
            continue
        handle.dimension.GetSystemValue3.assert_called_once_with(3, "Default")
        handle.dimension.GetSystemValue2.assert_not_called()


@pytest.mark.parametrize(
    "fault", ["basic", "tangent", "value", "nominal_instead_of_native", "hidden_value"]
)
def test_manufacturing_rejects_changed_native_dimension_meaning(manufacturing, fault):
    label = "shaft-to-handle-pivot location"
    handle = manufacturing.handles[label]
    if fault == "basic":
        handle.dimension.Tolerance.Type = 0
    if fault == "tangent":
        handle.dimension.GetArcEndCondition.side_effect = lambda _index: 0
    if fault == "value":
        # Two picometres exceeds the unchanged round(..., 12) receipt boundary.
        handle.dimension.GetSystemValue2.return_value += 0.000000000002
    if fault == "nominal_instead_of_native":
        handle.dimension.GetSystemValue2.return_value = 0.075
    if fault == "hidden_value":
        handle.display.ShowDimensionValue = False
    with pytest.raises(
        RuntimeError, match="native measurement/BASIC/arc meaning changed"
    ):
        probe.require_manufacturing(manufacturing.collect(), manufacturing.recorded)


@pytest.mark.parametrize("label", [item[0] for item in MANUFACTURING_DIMENSIONS])
def test_every_added_dimension_keeps_the_exact_twelve_place_native_boundary(
    manufacturing, label
):
    manufacturing.handles[
        label
    ].dimension.GetSystemValue2.return_value += 0.000000000002
    with pytest.raises(
        RuntimeError, match="native measurement/BASIC/arc meaning changed"
    ):
        probe.require_manufacturing(manufacturing.collect(), manufacturing.recorded)


@pytest.mark.parametrize(
    "label", ["arm-width overall", "dimple transverse location from datum C"]
)
def test_manufacturing_rejects_adding_basic_to_ordinary_dimensions(
    manufacturing, label
):
    manufacturing.handles[label].dimension.Tolerance.Type = 1
    with pytest.raises(
        RuntimeError, match="native measurement/BASIC/arc meaning changed"
    ):
        probe.require_manufacturing(manufacturing.collect(), manufacturing.recorded)


@pytest.mark.parametrize("label", ["crank-arm cross-hole", "handle pivot hole"])
@pytest.mark.parametrize("fault", ["missing_text", "fake_callout"])
def test_manufacturing_requires_native_hole_callouts_and_actual_text(
    manufacturing, label, fault
):
    row = manufacturing.collect()
    key = "/".join(manufacturing.recorded[label])
    if fault == "missing_text":
        row["annotations"][key]["semantic"]["texts"] = []
    if fault == "fake_callout":
        row["dimensions"][key]["hole_callout"] = False
    with pytest.raises(
        RuntimeError, match=r"native Hole Wizard callout|actual displayed hole text"
    ):
        probe.require_manufacturing(row, manufacturing.recorded)


@pytest.mark.parametrize("fault", ["missing_marked", "sheet_scale"])
def test_manufacturing_requires_complete_marked_union_and_sheet_scale(
    manufacturing, fault
):
    row = manufacturing.collect()
    if fault == "missing_marked":
        del row["dimensions"]["/".join(manufacturing.recorded["Depth"])]
    if fault == "sheet_scale":
        row["sheet"] = (0.4318, 0.2794, 1.0, 1.0)
    with pytest.raises(RuntimeError, match="marked dimension union or sheet scale"):
        probe.require_manufacturing(row, manufacturing.recorded)


@pytest.mark.parametrize("fault", ["receipt_sha", "wrong_source", "failed_receipt"])
def test_manufacturing_requires_pinned_successful_native_source_receipt(
    manufacturing, fault
):
    if fault == "receipt_sha":
        manufacturing.receipt_path.write_text("{}", encoding="utf-8")
    if fault == "wrong_source":
        manufacturing.receipt["provenance"]["source_sha256"] = "different source"
        manufacturing.write_receipt()
    if fault == "failed_receipt":
        manufacturing.receipt["status"] = "failed"
        manufacturing.write_receipt()
    with pytest.raises(
        RuntimeError, match=r"baseline receipt changed|baseline has the wrong source"
    ):
        probe.require_manufacturing(manufacturing.collect(), manufacturing.recorded)


def test_dimension_collector_rejects_duplicate_annotation_identity(manufacturing):
    view = manufacturing.views["Front"]
    view.GetAnnotations.return_value.append(view.GetAnnotations.return_value[0])
    with pytest.raises(
        RuntimeError, match="duplicate drawing dimension identity: Front/"
    ):
        manufacturing.collect()


def test_dimension_collector_rejects_nonfinite_readback(manufacturing):
    manufacturing.handles[
        "arm-width overall"
    ].dimension.GetSystemValue2.return_value = float("nan")
    with pytest.raises(RuntimeError, match="non-finite"):
        manufacturing.collect()


def test_details_render_vector_pdf_windows_without_changing_source(
    monkeypatch, tmp_path
):
    import pypdfium2 as pdfium
    from types import SimpleNamespace

    pdf = tmp_path / "native.pdf"
    pdf.write_bytes(b"read-only native PDF fixture")
    before = pdf.read_bytes()
    crops = []

    def render(**kwargs):
        crops.append(kwargs)
        return SimpleNamespace(
            to_pil=lambda: SimpleNamespace(
                save=lambda path, **kw: path.write_bytes(b"rendered")
            ),
            close=lambda: None,
        )

    page = SimpleNamespace(
        get_size=lambda: (17 * 72, 11 * 72), render=render, close=lambda: None
    )

    class Document:
        def __init__(self, path):
            assert path == str(pdf)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def __len__(self):
            return 1

        def __getitem__(self, index):
            assert index == 0
            return page

    monkeypatch.setattr(pdfium, "PdfDocument", Document)
    result = probe.render_details(pdf, tmp_path / "cold")
    assert len(result) == len(crops) == 6
    assert all(row["scale"] == 600 / 72 and min(row["crop"]) > 0 for row in crops)
    assert pdf.read_bytes() == before
    with pytest.raises(RuntimeError, match="already exists"):
        probe.render_details(pdf, tmp_path / "cold")


@pytest.mark.parametrize(
    "arguments",
    [
        ["bootstrap"],
        ["bootstrap", "--expected-source-sha", "0" * 64],
        ["source", "--expected-source-sha", "0" * 64],
        [
            "bootstrap",
            "--expected-source-sha",
            "wrong",
            "--builder-revision",
            "a" * 40,
            "--builder-trace",
            "0x" + "1" * 32,
        ],
    ],
)
def test_bootstrap_cli_rejects_incomplete_or_misapplied_request_before_runner(
    monkeypatch, arguments
):
    runner = Mock(side_effect=AssertionError("must reject before native runner"))
    monkeypatch.setattr(probe, "run_copy_diagnostic", runner)
    monkeypatch.setattr(probe, "require_owned_diagnostic_environment", lambda: None)
    with pytest.raises(SystemExit):
        probe.main(arguments)
    runner.assert_not_called()


def test_bootstrap_cli_forwards_explicit_request_through_locked_parent(monkeypatch):
    import dodo

    request = [
        "bootstrap",
        "--expected-source-sha",
        "0" * 64,
        "--builder-revision",
        "a" * 40,
        "--builder-trace",
        "0x" + "1" * 32,
        "--baseline-revision",
        "b" * 40,
    ]
    preflight = Mock(return_value={})
    run = Mock()
    monkeypatch.setattr(probe, "bootstrap_inputs", preflight)
    monkeypatch.setattr(probe, "require_owned_diagnostic_environment", lambda: None)
    monkeypatch.setattr(dodo, "_run", run)
    monkeypatch.setenv("HARMONIC_DIAGNOSTIC_SW_PID", "123")
    assert probe.main(request) == 0
    assert preflight.call_count == 1
    command = run.call_args.args[0]
    assert command[2:] == [*request, "--worker"]
    assert run.call_args.kwargs["com"] is True


@pytest.fixture
def bootstrap_files(tmp_path, monkeypatch):
    import os
    import sys
    from datetime import datetime, timezone
    import draw_crank_arm as recipe
    import solidworks_mcp.adapters.pywin32_adapter as adapter_module

    tmp_path = tmp_path / "checkout with spaces"
    tmp_path.mkdir()
    source = tmp_path / "cad/out/sldprt/crank-arm.SLDPRT"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"genuine local build fixture")
    token = source.with_name(".crank-arm.execution")
    token.write_text(probe.sha(source), encoding="utf-8")
    timestamp = datetime(2026, 9, 7, tzinfo=timezone.utc).timestamp()
    os.utime(source, (timestamp + 5, timestamp + 5))
    os.utime(token, (timestamp + 9, timestamp + 9))
    trace = "0x" + "1" * 32

    def row(name, start, end, span, parent, **attributes):
        return {
            "name": name,
            "context": {"trace_id": trace, "span_id": span},
            "parent_id": parent,
            "status": {"status_code": "OK"},
            "start_time": f"2026-09-07T00:00:{start:02d}Z",
            "end_time": f"2026-09-07T00:00:{end:02d}Z",
            "attributes": attributes,
        }

    rows = [
        row("part.build", 1, 8, "child", "parent", target="crank_arm"),
        row(
            "task part:crank_arm",
            0,
            10,
            "parent",
            None,
            label="part:crank_arm",
            cache="miss",
        ),
    ]
    traces = tmp_path / "cad/out/reports/telemetry/traces.jsonl"
    traces.parent.mkdir(parents=True)
    logs = traces.with_name("logs.jsonl")
    commands = [
        {
            "body": f">> part:crank_arm: {tmp_path / '.venv/Scripts/python.exe'} "
            f"{tmp_path / 'cad/scripts/build_crank_arm.py'}",
            "trace_id": trace,
            "span_id": "parent",
            "timestamp": "2026-09-07T00:00:00.500000Z",
            "attributes": {
                "code.file.path": str(tmp_path / "cad/scripts/_telemetry.py")
            },
        },
        {
            "body": f"artefact part: {source}",
            "trace_id": trace,
            "span_id": "parent",
            "timestamp": "2026-09-07T00:00:08.500000Z",
            "attributes": {
                "code.file.path": str(tmp_path / "cad/scripts/_telemetry.py")
            },
        },
    ]

    def write():
        traces.write_text(
            "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
        )
        logs.write_text(
            "\n".join(json.dumps(row) for row in commands) + "\n", encoding="utf-8"
        )

    write()
    git_calls = []

    def git(*args, directory=None):
        git_calls.append((args, directory))
        if args == ("status", "--porcelain=v1"):
            return ""
        if args == ("rev-parse", "HEAD"):
            return "c" * 40 if directory else "a" * 40
        if args == ("rev-parse", "HEAD:SolidworksMCP-python"):
            return "c" * 40
        if args == ("rev-parse", "--short", "a" * 40):
            return "a" * 8
        if args == ("rev-parse", "b" * 40 + "^{commit}"):
            return "b" * 40
        if args == ("rev-parse", "b" * 40 + ":SolidworksMCP-python"):
            return "c" * 40
        raise AssertionError(args)

    monkeypatch.setattr(probe, "ROOT", tmp_path)
    monkeypatch.setattr(probe, "SOURCE", source)
    monkeypatch.setattr(probe, "TOKEN", token)
    monkeypatch.setattr(probe, "_bootstrap_git", git)
    monkeypatch.setenv("HARMONIC_DIAGNOSTIC_SW_PID", "123")
    monkeypatch.setattr(sys, "executable", str(tmp_path / ".venv/Scripts/python.exe"))
    monkeypatch.setattr(
        recipe, "__file__", str(tmp_path / "cad/scripts/draw_crank_arm.py")
    )
    monkeypatch.setattr(
        adapter_module,
        "__file__",
        str(
            tmp_path
            / "SolidworksMCP-python/src/solidworks_mcp/adapters/pywin32_adapter.py"
        ),
    )
    request = probe.BootstrapRequest(probe.sha(source), "a" * 40, trace, "b" * 40)
    return SimpleNamespace(
        source=source,
        token=token,
        rows=rows,
        write=write,
        traces=traces,
        logs=logs,
        commands=commands,
        request=request,
        git=git,
        git_calls=git_calls,
    )


def test_bootstrap_inputs_require_actual_completed_local_builder_and_token(
    bootstrap_files,
):
    state = bootstrap_files
    row = probe.bootstrap_inputs(state.request)
    assert (
        row["source_sha256"]
        == row["execution_token"]
        == state.request.expected_source_sha
    )
    assert row["builder_spans"] == state.rows
    assert row["expected_generator"] == "harmonic-analyzer @ aaaaaaaa"
    assert row["builder_revision"] == "a" * 40
    assert row["baseline_revision"] == "b" * 40
    assert row["adapter_commit"] == "c" * 40
    assert probe.EXPECTED_SOURCE_SHA != row["source_sha256"]


def test_bootstrap_retains_exact_producer_records_with_windows_path_spaces(
    bootstrap_files,
):
    state = bootstrap_files
    row = probe.bootstrap_inputs(state.request)
    assert row["builder_logs"] == {"path": str(state.logs), "records": state.commands}
    assert "checkout with spaces" in state.commands[0]["body"]


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "duplicate",
        "foreign_python",
        "foreign_script",
        "foreign_output",
        "foreign_origin",
        "wrong_span",
        "wrong_trace",
        "late_command",
        "early_output",
        "quoted_command",
        "substring_command",
    ],
)
def test_bootstrap_rejects_unbound_producer_logs(bootstrap_files, fault):
    state = bootstrap_files
    if fault == "missing":
        state.commands.pop()
    elif fault == "duplicate":
        state.commands.append(dict(state.commands[0]))
    elif fault == "foreign_python":
        state.commands[0]["body"] = state.commands[0]["body"].replace(
            str(probe.ROOT / ".venv/Scripts/python.exe"), "C:\\other\\python.exe"
        )
    elif fault == "foreign_script":
        state.commands[0]["body"] = state.commands[0]["body"].replace(
            str(probe.ROOT / "cad/scripts/build_crank_arm.py"),
            "C:\\other\\build_crank_arm.py",
        )
    elif fault == "foreign_output":
        state.commands[1]["body"] = "artefact part: C:\\other\\crank-arm.SLDPRT"
    elif fault == "foreign_origin":
        state.commands[0]["attributes"]["code.file.path"] = "C:\\other\\_telemetry.py"
    elif fault == "wrong_span":
        state.commands[0]["span_id"] = "other-task"
    elif fault == "wrong_trace":
        state.commands[0]["trace_id"] = "0x" + "2" * 32
    elif fault == "late_command":
        state.commands[0]["timestamp"] = "2026-09-07T00:00:02Z"
    elif fault == "early_output":
        state.commands[1]["timestamp"] = "2026-09-07T00:00:07Z"
    elif fault == "quoted_command":
        state.commands[0]["body"] = state.commands[0]["body"].replace(
            str(probe.ROOT / ".venv/Scripts/python.exe"),
            '"' + str(probe.ROOT / ".venv/Scripts/python.exe") + '"',
        )
    else:
        state.commands[0]["body"] += " --foreign-option"
    state.write()
    with pytest.raises(RuntimeError, match="producer"):
        probe.bootstrap_inputs(state.request)


def test_bootstrap_ignores_other_traces_but_rejects_shared_trace_foreign_producer(
    bootstrap_files,
):
    state = bootstrap_files
    foreign = dict(
        state.commands[0],
        trace_id="0x" + "2" * 32,
        body=">> part:crank_arm: C:\\other\\python.exe C:\\other\\build_crank_arm.py",
    )
    state.commands.append(foreign)
    state.write()
    row = probe.bootstrap_inputs(state.request)
    assert row["builder_logs"]["records"] == state.commands[:2]
    foreign["trace_id"] = state.request.builder_trace
    state.write()
    with pytest.raises(RuntimeError, match="producer"):
        probe.bootstrap_inputs(state.request)


@pytest.mark.parametrize(
    "fault",
    [
        "wrong_token",
        "wrong_sha",
        "failed",
        "cache_hit",
        "no_child",
        "wrong_parent",
        "wrong_target",
        "source_mtime",
        "token_mtime",
        "duplicate",
        "later_build",
        "dirty",
        "wrong_head",
        "wrong_adapter",
    ],
)
def test_bootstrap_inputs_fail_closed_on_unproven_build(
    bootstrap_files, monkeypatch, fault
):
    import os

    state = bootstrap_files
    if fault == "wrong_token":
        state.token.write_text("0" * 64, encoding="utf-8")
    if fault == "wrong_sha":
        state.source.write_bytes(b"replacement with no builder")
    if fault == "failed":
        state.rows[0]["status"]["status_code"] = "ERROR"
    if fault == "cache_hit":
        state.rows[1]["attributes"]["cache"] = "hit"
    if fault == "no_child":
        state.rows.pop(0)
    if fault == "wrong_parent":
        state.rows[0]["parent_id"] = "other"
    if fault == "wrong_target":
        state.rows[0]["attributes"]["target"] = "other"
    if fault in {"source_mtime", "token_mtime"}:
        os.utime(state.source if fault == "source_mtime" else state.token, (0, 0))
    if fault == "duplicate":
        state.rows.append(state.rows[1])
    if fault == "later_build":
        from copy import deepcopy

        later = deepcopy(state.rows[1])
        later["context"]["trace_id"] = "0x" + "2" * 32
        later["start_time"], later["end_time"] = (
            "2026-09-07T01:00:00Z",
            "2026-09-07T01:01:00Z",
        )
        state.rows.append(later)
    if fault in {"dirty", "wrong_head", "wrong_adapter"}:

        def git(*args, directory=None):
            if fault == "dirty" and args == ("status", "--porcelain=v1"):
                return " M source.py"
            if (
                fault == "wrong_head"
                and args == ("rev-parse", "HEAD")
                and directory is None
            ):
                return "d" * 40
            if (
                fault == "wrong_adapter"
                and args == ("rev-parse", "HEAD")
                and directory is not None
            ):
                return "d" * 40
            return state.git(*args, directory=directory)

        monkeypatch.setattr(probe, "_bootstrap_git", git)
    state.write()
    with pytest.raises((RuntimeError, ValueError)):
        probe.bootstrap_inputs(state.request)


@pytest.fixture
def bootstrap_callback(candidate, monkeypatch):
    state = candidate
    state.request = probe.BootstrapRequest(
        state.digest, "a" * 40, "0x" + "1" * 32, "b" * 40
    )
    state.inputs = {
        "source_sha256": state.digest,
        "execution_token": state.digest,
        "expected_generator": "harmonic-analyzer @ aaaaaaaa",
        "expected_pid": 123,
    }
    monkeypatch.setattr(probe, "bootstrap_inputs", lambda request: dict(state.inputs))
    state.adapter.swApp.GetProcessID = lambda: 123
    state.adapter.swApp.RevisionNumber = lambda: "34.3.0"
    original_open = state.adapter.open_model

    async def open_model(path):
        result = await original_open(path)
        model = state.adapter.currentModel
        model.GetSaveFlag = lambda: state.fault == "dirty-source" and model.kind == 1
        model.GetCustomInfoValue = lambda configuration, name: (
            "wrong"
            if state.fault == "generator"
            else state.inputs["expected_generator"]
        )
        return result

    state.adapter.open_model = open_model
    source_snapshot = probe.source_snapshot

    def read(adapter, path):
        row = source_snapshot(adapter, path)
        row["observed_dimensions"] = {
            "configuration": "Default",
            "features": [],
            "dimensions": {},
        }
        if state.fault == "raw-drift" and state.insertions:
            row["required_dimensions"] = {"unexpected": 1}
        return row, {}

    monkeypatch.setattr(probe, "_source_snapshot_with_handles", read)

    def require(before, after):
        assert before == after, "source changed"

    monkeypatch.setattr(probe, "require_source_unchanged", require)
    return state


@pytest.mark.asyncio
async def test_bootstrap_full_callback_captures_explicit_recipe_without_acceptance(
    bootstrap_callback,
):
    state = bootstrap_callback
    result = await probe.capture_bootstrap(
        state.adapter, state.directory, state.request
    )
    row = json.loads(Path(result["report"]).read_text(encoding="utf-8"))
    assert row["status"] == "captured"
    assert row["equivalence"] == "unproven"
    assert row["acceptance"] == "not_run"
    assert row["baseline_revision"] == state.request.baseline_revision
    assert len(state.insertions) == 14
    assert state.module.build is state.build_function
    assert state.events.count("save") == 1
    assert state.events.index("configure") < next(
        index
        for index, item in enumerate(state.events)
        if isinstance(item, tuple) and item[0] == "open"
    )
    assert "save3" not in state.events and "close" not in state.events
    assert (
        row["source_original"]
        == row["source_copy"]
        == row["execution_token"]
        == state.digest
    )
    assert row["source_before"] == row["source_after"]
    probe.require_manufacturing.assert_not_called()


@pytest.mark.parametrize("value", [None, "", "0", "-1", "1.2", "arbitrary"])
def test_bootstrap_requires_explicit_licensed_pid_before_native_runner(
    monkeypatch, value
):
    import dodo

    if value is None:
        monkeypatch.delenv("HARMONIC_DIAGNOSTIC_SW_PID", raising=False)
    if value is not None:
        monkeypatch.setenv("HARMONIC_DIAGNOSTIC_SW_PID", value)
    monkeypatch.setattr(probe, "bootstrap_inputs", Mock(return_value={}))
    monkeypatch.setattr(probe, "require_owned_diagnostic_environment", lambda: None)
    runner = Mock(side_effect=AssertionError("native runner must not start"))
    monkeypatch.setattr(probe, "run_copy_diagnostic", runner)
    monkeypatch.setattr(dodo, "_run", runner)
    with pytest.raises(RuntimeError, match="PID"):
        probe.main(
            [
                "bootstrap",
                "--expected-source-sha",
                "0" * 64,
                "--builder-revision",
                "a" * 40,
                "--builder-trace",
                "0x" + "1" * 32,
            ]
        )
    runner.assert_not_called()


@pytest.mark.asyncio
async def test_bootstrap_missing_created_copy_fails_final_guard(
    bootstrap_callback, monkeypatch
):
    state = bootstrap_callback
    original = probe.require_source_unchanged
    calls = []

    def remove_copy(before, after):
        calls.append(1)
        original(before, after)
        if len(calls) == 2:
            (state.directory / "trial-part.SLDPRT").unlink()

    monkeypatch.setattr(probe, "require_source_unchanged", remove_copy)
    with pytest.raises(ExceptionGroup, match="final evidence"):
        await probe.capture_bootstrap(state.adapter, state.directory, state.request)
    row = json.loads(
        (state.directory / "measurements.json").read_text(encoding="utf-8")
    )
    assert row["status"] == "failed" and "error" in row["source_copy"]
    assert row["source_original"] == row["execution_token"] == state.digest


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["source", "active", "pid"])
async def test_bootstrap_rejects_wrong_native_context_before_measurement(
    bootstrap_callback, monkeypatch, fault
):
    state = bootstrap_callback
    original = state.adapter.open_model

    async def wrong_context(path):
        if fault == "source":
            state.fault = "source"
        result = await original(path)
        if fault == "active":
            state.adapter.swApp.ActiveDoc = object()
        return result

    state.adapter.open_model = wrong_context
    if fault == "pid":
        state.adapter.swApp.GetProcessID = lambda: 999
    reads = Mock(side_effect=AssertionError("must not read geometry"))
    monkeypatch.setattr(probe, "_source_snapshot_with_handles", reads)
    with pytest.raises((RuntimeError, AssertionError)):
        await probe.capture_bootstrap(state.adapter, state.directory, state.request)
    reads.assert_not_called()
    assert not state.insertions and not state.saved
    row = json.loads(
        (state.directory / "measurements.json").read_text(encoding="utf-8")
    )
    assert row["status"] == "failed" and row["acceptance"] == "not_run"


def test_bootstrap_worker_dispatches_actual_callback(bootstrap_callback, monkeypatch):
    state = bootstrap_callback
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "0")
    monkeypatch.setenv("HARMONIC_COM_SEAT", "test-owned-lock")
    monkeypatch.setenv("HARMONIC_DIAGNOSTIC_SW_PID", "123")
    monkeypatch.setattr(
        probe.tempfile, "mkdtemp", lambda **kwargs: str(state.directory)
    )
    monkeypatch.setattr(probe, "ROOT", state.directory.parent)
    calls = []

    def run(callback):
        calls.append(callback)
        result = asyncio.run(callback(state.adapter))
        assert Path(result["report"]).parent == state.directory
        return 0

    monkeypatch.setattr(probe, "run_copy_diagnostic", run)
    assert (
        probe.main(
            [
                "bootstrap",
                "--expected-source-sha",
                state.digest,
                "--builder-revision",
                "a" * 40,
                "--builder-trace",
                "0x" + "1" * 32,
                "--baseline-revision",
                "b" * 40,
                "--worker",
            ]
        )
        == 0
    )
    assert len(calls) == 1 and len(state.insertions) == 14
    row = json.loads(
        (state.directory / "measurements.json").read_text(encoding="utf-8")
    )
    assert row["status"] == "captured" and row["acceptance"] == "not_run"
    assert row["source_before"] == row["source_after"]
    assert row["generator"] == state.inputs["expected_generator"]
    assert "drawing" in row and "schema_gaps" in row
    probe.require_manufacturing.assert_not_called()
    assert probe.EXPECTED_SOURCE_SHA == state.digest  # fixture pin was not changed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fault, error",
    [
        ("generator", "Generator"),
        ("dirty-source", "dirty"),
        ("view", "context"),
        ("save", "primary save failure"),
        ("raw-drift", "source changed"),
    ],
)
async def test_bootstrap_callback_preserves_failed_evidence_and_never_accepts(
    bootstrap_callback, fault, error
):
    state = bootstrap_callback
    state.fault = fault
    with pytest.raises((RuntimeError, AssertionError), match=error):
        await probe.capture_bootstrap(state.adapter, state.directory, state.request)
    row = json.loads(
        (state.directory / "measurements.json").read_text(encoding="utf-8")
    )
    assert row["status"] == "failed" and error in row["error"]
    assert row["acceptance"] == "not_run" and row["equivalence"] == "unproven"
    assert (
        row["source_original"]
        == row["source_copy"]
        == row["execution_token"]
        == state.digest
    )
    if fault in {"generator", "dirty-source"}:
        assert state.insertions == [] and "factory" not in state.events


@pytest.mark.asyncio
async def test_bootstrap_source_only_never_configures_factory_or_builds(
    bootstrap_callback,
):
    state = bootstrap_callback
    request = probe.BootstrapRequest(state.digest, "a" * 40, "0x" + "1" * 32)
    result = await probe.capture_bootstrap(state.adapter, state.directory, request)
    row = json.loads(Path(result["report"]).read_text(encoding="utf-8"))
    assert row["status"] == "captured" and "drawing" not in row
    assert state.insertions == [] and "configure" not in state.events
    assert not state.exports and not state.saved


@pytest.mark.asyncio
async def test_bootstrap_preserves_primary_with_independent_final_guard_failure(
    bootstrap_callback, monkeypatch
):
    state = bootstrap_callback
    state.fault = "save"
    calls = []

    def read(request):
        calls.append(request)
        if len(calls) > 1:
            raise RuntimeError("builder evidence changed")
        return state.inputs

    monkeypatch.setattr(probe, "bootstrap_inputs", read)
    with pytest.raises(ExceptionGroup) as raised:
        await probe.capture_bootstrap(state.adapter, state.directory, state.request)
    assert str(raised.value.exceptions[0]) == "primary save failure"
    assert str(raised.value.exceptions[1]) == "builder evidence changed"
    row = json.loads(
        (state.directory / "measurements.json").read_text(encoding="utf-8")
    )
    assert row["status"] == "failed" and "primary save failure" in row["error"]
    assert (
        row["source_original"]
        == row["source_copy"]
        == row["execution_token"]
        == state.digest
    )


@pytest.mark.asyncio
async def test_bootstrap_compares_fresh_native_parameter_identity(
    bootstrap_callback, monkeypatch
):
    state = bootstrap_callback
    original = probe._source_snapshot_with_handles
    handles = []

    def read(adapter, path):
        row, _ = original(adapter, path)
        row["observed_dimensions"]["dimensions"] = {
            "Width@ArmProfile": {"native": {"value": 0.016}, "displays": []}
        }
        handle = object()
        handles.append(handle)
        return row, {"Width@ArmProfile": handle}

    monkeypatch.setattr(probe, "_source_snapshot_with_handles", read)
    with pytest.raises(RuntimeError, match="source native dimension identity changed"):
        await probe.capture_bootstrap(state.adapter, state.directory, state.request)
    assert len(handles) == 2
    row = json.loads(
        (state.directory / "measurements.json").read_text(encoding="utf-8")
    )
    assert row["source_before"] == row["source_after"]
    assert row["status"] == "failed" and row["acceptance"] == "not_run"


@pytest.mark.parametrize("path_kind", ["measurements.json", "trial-part.SLDPRT"])
@pytest.mark.asyncio
async def test_bootstrap_never_overwrites_existing_evidence(
    bootstrap_callback, path_kind
):
    state = bootstrap_callback
    retained = state.directory / path_kind
    retained.write_bytes(b"historical evidence")
    with pytest.raises(RuntimeError, match="fresh evidence/output paths"):
        await probe.capture_bootstrap(state.adapter, state.directory, state.request)
    assert retained.read_bytes() == b"historical evidence"
    assert not state.documents and not state.insertions


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [asyncio.CancelledError, KeyboardInterrupt])
async def test_bootstrap_interruption_retains_failure_and_closes_only_owned_documents(
    bootstrap_callback, monkeypatch, error_type
):
    state = bootstrap_callback
    primary = error_type("interrupted native capture")

    def interrupt(*args):
        raise primary

    monkeypatch.setattr(probe, "_source_snapshot_with_handles", interrupt)
    checkpoint = Mock()
    state.adapter.ownership.checkpoint = checkpoint
    with pytest.raises(error_type) as raised:
        await probe.capture_bootstrap(state.adapter, state.directory, state.request)
    assert raised.value is primary
    assert state.events.count("close") == 1 and not state.documents
    checkpoint.assert_called_once_with()
    row = json.loads(
        (state.directory / "measurements.json").read_text(encoding="utf-8")
    )
    assert row["status"] == "failed" and "interrupted native capture" in row["error"]
    assert (
        row["source_original"]
        == row["source_copy"]
        == row["execution_token"]
        == state.digest
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [asyncio.CancelledError, KeyboardInterrupt])
@pytest.mark.parametrize("boundary", ["inputs", "hash", "write"])
async def test_bootstrap_finalizer_interruption_cleans_actual_outer_callback(
    bootstrap_callback, monkeypatch, error_type, boundary
):
    from diagnostics import _owned_native_documents as owned

    state = bootstrap_callback
    primary = error_type("interrupted final evidence")
    checkpoint = Mock()
    state.adapter.ownership.checkpoint = checkpoint
    monkeypatch.setattr(owned, "DiagnosticAdapter", lambda adapter: adapter)
    original_inputs = probe.bootstrap_inputs
    input_calls = []

    def inputs(request):
        input_calls.append(request)
        if boundary == "inputs" and len(input_calls) == 2:
            raise primary
        return original_inputs(request)

    monkeypatch.setattr(probe, "bootstrap_inputs", inputs)
    original_sha = probe.sha
    fired = []

    def sha(path):
        if boundary == "hash" and state.insertions and not fired:
            fired.append("hash")
            raise primary
        return original_sha(path)

    monkeypatch.setattr(probe, "sha", sha)
    original_write = Path.write_text

    def write(path, data, *args, **kwargs):
        if boundary == "write" and '"status": "captured"' in data and not fired:
            fired.append("write")
            raise primary
        return original_write(path, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", write)
    with pytest.raises(error_type) as raised:
        await owned.owned_callback(
            state.adapter,
            lambda adapter: probe.capture_bootstrap(
                adapter, state.directory, state.request
            ),
        )
    assert raised.value is primary
    assert len(state.insertions) == 14 and state.events.count("save") == 1
    assert state.events.count("close") == 1 and not state.documents
    checkpoint.assert_called_once_with()
    row = json.loads(
        (state.directory / "measurements.json").read_text(encoding="utf-8")
    )
    assert row["status"] == "failed" and "interrupted final evidence" in row["error"]
    assert row["acceptance"] == "not_run" and row["equivalence"] == "unproven"


@pytest.mark.asyncio
async def test_bootstrap_preserves_first_interruption_and_secondary_cleanup_errors(
    bootstrap_callback, monkeypatch
):
    state = bootstrap_callback
    primary = KeyboardInterrupt("first interruption")
    secondary = asyncio.CancelledError("final provenance interrupted")
    calls = []

    def inputs(request):
        calls.append(request)
        if len(calls) == 2:
            raise secondary
        return dict(state.inputs)

    def capture(*args):
        raise primary

    original_close = state.adapter.close_owned_documents

    async def close():
        await original_close()
        raise RuntimeError("cleanup read failed")

    monkeypatch.setattr(probe, "bootstrap_inputs", inputs)
    monkeypatch.setattr(probe, "_source_snapshot_with_handles", capture)
    state.adapter.close_owned_documents = close
    state.adapter.ownership.checkpoint = Mock(
        side_effect=RuntimeError("checkpoint failed")
    )
    with pytest.raises(KeyboardInterrupt) as raised:
        await probe.capture_bootstrap(state.adapter, state.directory, state.request)
    assert raised.value is primary
    assert state.events.count("close") == 1
    row = json.loads(
        (state.directory / "measurements.json").read_text(encoding="utf-8")
    )
    assert row["status"] == "failed" and "first interruption" in row["error"]
    assert "cleanup read failed" in row["interruption_cleanup_error"]
    assert "checkpoint failed" in row["interruption_checkpoint_error"]
    assert "final provenance interrupted" in row["interruption_final_error"]


@pytest.mark.asyncio
async def test_bootstrap_final_interruption_keeps_prior_capture_failure(
    bootstrap_callback, monkeypatch
):
    state = bootstrap_callback
    state.fault = "save"
    primary = KeyboardInterrupt("final read interrupted after save failure")
    calls = []

    def inputs(request):
        calls.append(request)
        if len(calls) == 2:
            raise primary
        return dict(state.inputs)

    monkeypatch.setattr(probe, "bootstrap_inputs", inputs)
    state.adapter.ownership.checkpoint = Mock()
    with pytest.raises(KeyboardInterrupt) as raised:
        await probe.capture_bootstrap(state.adapter, state.directory, state.request)
    assert raised.value is primary and state.events.count("close") == 1
    row = json.loads(
        (state.directory / "measurements.json").read_text(encoding="utf-8")
    )
    assert "primary save failure" in row["error"]
    assert "final read interrupted" in row["interruption"]
    assert any("primary save failure" in note for note in primary.__notes__)


@pytest.mark.asyncio
async def test_bootstrap_interrupted_emergency_report_write_preserves_original(
    bootstrap_callback, monkeypatch
):
    state = bootstrap_callback
    primary = KeyboardInterrupt("final provenance interrupted")
    calls = []
    original_write = Path.write_text

    def inputs(request):
        calls.append(request)
        if len(calls) == 2:
            raise primary
        return dict(state.inputs)

    def write(path, data, *args, **kwargs):
        if '"interruption"' in data:
            raise OSError("receipt storage unavailable")
        return original_write(path, data, *args, **kwargs)

    monkeypatch.setattr(probe, "bootstrap_inputs", inputs)
    monkeypatch.setattr(Path, "write_text", write)
    state.adapter.ownership.checkpoint = Mock()
    with pytest.raises(KeyboardInterrupt) as raised:
        await probe.capture_bootstrap(state.adapter, state.directory, state.request)
    assert raised.value is primary and state.events.count("close") == 1
    assert any("receipt storage unavailable" in note for note in primary.__notes__)
