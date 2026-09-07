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
        RuntimeError, match="native Hole Wizard callout|actual displayed hole text"
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
        RuntimeError, match="baseline receipt changed|baseline has the wrong source"
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
