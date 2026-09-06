"""Offline witnesses for the opt-in native part-PMI import positive control."""

import ast
import asyncio
from copy import deepcopy
import json
import math
from pathlib import Path
from unittest.mock import Mock

import pytest

from diagnostics import probe_native_model_pmi as probe


def valid_records():
    return [
        {
            "name": row.annotation_name,
            "type": 2 if row.key.startswith("datum:") else 5,
            "key": row.key,
            "view": "native-view",
            "is_dimxpert": False,
            "dangling": False,
            "visible": 1,
            "owner_identity": 1,
            "attachment_count": 1,
            "null_entities": 0,
            "attachment_types": (2,),
            "face_identity": 1,
            "face_spec_matches": True,
            "position_m": (0.1, 0.1, 0),
            "anchor_on_sheet": True,
        }
        for row in probe.ROWS
    ]


@pytest.mark.parametrize("stage", ["source", "initial", "reopened"])
def test_complete_attached_native_bank_passes(stage):
    assert probe.witness_failures(valid_records(), stage=stage) == []


@pytest.mark.parametrize("change", ["missing", "duplicate", "unknown"])
def test_coverage_cannot_be_satisfied_by_count_alone(change):
    records = valid_records()
    if change == "missing":
        records.pop()
    if change == "duplicate":
        records[-1] = deepcopy(records[0])
    if change == "unknown":
        records[-1]["key"] = None
    assert any(
        "coverage" in error
        for error in probe.witness_failures(records, stage="initial")
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("is_dimxpert", True),
        ("dangling", True),
        ("visible", 3),
        ("visible", 0),
        ("owner_identity", 0),
        ("owner_identity", -1),
        ("attachment_count", 0),
        ("attachment_count", 2),
        ("null_entities", 1),
        ("attachment_types", (0,)),
        ("attachment_types", (1,)),
        ("face_identity", 0),
        ("face_identity", -1),
        ("face_identity", None),
        ("face_spec_matches", False),
        ("face_spec_matches", None),
        ("position_m", (0.1, float("nan"), 0)),
        ("position_m", (0.1, 0.2)),
        ("anchor_on_sheet", False),
    ],
)
def test_failed_native_witness_is_not_hidden(field, value):
    records = valid_records()
    records[0][field] = value
    assert probe.witness_failures(records, stage="reopened")


def test_source_names_are_verified_but_native_drawing_names_are_observed():
    records = valid_records()
    records[0]["name"] = "Drawing-generated-name"
    assert probe.witness_failures(records, stage="initial") == []
    assert any(
        "source name" in error
        for error in probe.witness_failures(records, stage="source")
    )


def test_import_matches_official_example_and_has_exactly_two_native_calls():
    drawing = Mock()
    drawing.InsertModelAnnotations3.side_effect = [(object(), object()), (object(),)]
    result = probe.import_native_pmi(drawing)
    assert [item["returned_count"] for item in result] == [2, 1]
    assert [call.args for call in drawing.InsertModelAnnotations3.call_args_list] == [
        (0, 32, True, True, False, True),
        (0, 2, True, True, False, True),
    ]


def test_null_import_remains_a_zero_coverage_observation():
    drawing = Mock()
    drawing.InsertModelAnnotations3.return_value = None
    assert [row["returned_count"] for row in probe.import_native_pmi(drawing)] == [0, 0]
    assert len(probe.witness_failures([], stage="initial")) == 3


def test_import_com_exception_propagates_without_a_recreation_fallback():
    drawing = Mock()
    drawing.InsertModelAnnotations3.side_effect = RuntimeError("native rejection")
    with pytest.raises(RuntimeError, match="native rejection"):
        probe.import_native_pmi(drawing)
    assert drawing.InsertModelAnnotations3.call_count == 1


def test_import_string_is_not_treated_as_an_annotation_array():
    drawing = Mock()
    drawing.InsertModelAnnotations3.return_value = "error"
    with pytest.raises(RuntimeError, match="not annotations"):
        probe.import_native_pmi(drawing)


def test_plain_gtol_semantics_use_native_xml_and_reject_changed_format(monkeypatch):
    monkeypatch.setattr(probe, "_early_bound", lambda item, name: item)
    annotation = Mock()
    gtol = annotation.GetSpecificAnnotation.return_value
    gtol.GetFormat.return_value = 2
    gtol.GetFrameCount.return_value = 1
    row = probe.GEOMETRIC_CONTROLS[0]
    gtol.GetFrame.return_value.GetSymbolXml.return_value = row.frame_xml
    assert probe._signature(annotation, 5) == probe._expected_signature(row)
    gtol.GetFormat.return_value = 1
    with pytest.raises(RuntimeError, match="SW2022"):
        probe._signature(annotation, 5)


@pytest.mark.parametrize("owner_type", [0, 3])
def test_owner_identity_is_checked_against_actual_view_or_source_part(
    monkeypatch, owner_type
):
    monkeypatch.setattr(probe, "_early_bound", lambda item, name: item)
    monkeypatch.setattr(probe, "_face_geometry", lambda item: item)
    monkeypatch.setattr(probe, "_face_matches", lambda geometry, spec: True)
    app, annotation, model, view = Mock(), Mock(), Mock(), Mock()
    face = object()
    row = probe.PART_DATUMS[0]
    annotation.GetType.return_value = 2
    annotation.GetSpecificAnnotation.return_value.GetLabel.return_value = row.letter
    annotation.GetAttachedEntities3.return_value = (face,)
    annotation.GetAttachedEntityTypes.return_value = (2,)
    annotation.GetPosition.return_value = (0.1, 0.1, 0)
    annotation.GetName.return_value = row.annotation_name
    annotation.OwnerType = owner_type
    annotation.Visible = 1
    annotation.IsDimXpert.return_value = False
    annotation.IsDangling.return_value = False
    app.IsSame.return_value = 1
    record = probe._annotation_record(
        app, annotation, model, {row.key: face}, view=view, sheet_size=(0.3, 0.2)
    )
    assert app.IsSame.call_args_list[0].args == (
        annotation.Owner,
        view if owner_type == 0 else model,
    )
    assert record["face_identity"] == 1
    assert record["anchor_on_sheet"] is True


def test_probe_has_no_annotation_layout_or_recreation_calls():
    tree = ast.parse(Path(probe.__file__).read_text(encoding="utf-8"))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    attributes = {
        node.func.attr for node in calls if isinstance(node.func, ast.Attribute)
    }
    assert not attributes & {
        "SetPosition",
        "SetPosition2",
        "SetSelectionPoint2",
        "SetLeader3",
        "SetLeaderAttachmentPointAtIndex",
        "SetAttachedEntities",
        "InsertGtol",
        "InsertDatumTag2",
        "SelectByID2",
        "CreateDrawViewFromModelView3",
    }
    assert "Create3rdAngleViews2" in attributes
    seat_calls = [
        node
        for node in calls
        if isinstance(node.func, ast.Attribute) and node.func.attr == "_run"
    ]
    assert len(seat_calls) == 1
    assert any(
        keyword.arg == "com" and keyword.value.value is True
        for keyword in seat_calls[0].keywords
    )


def test_digest_identifies_source_changes(tmp_path):
    file = tmp_path / "copy.SLDPRT"
    file.write_bytes(b"one")
    before = probe.file_digest(file)
    file.write_bytes(b"two")
    assert probe.file_digest(file) != before


def test_native_frame_signatures_are_json_serializable():
    signatures = [probe._expected_signature(row) for row in probe.ROWS]
    assert len(json.loads(json.dumps(signatures))) == 3


@pytest.mark.parametrize("width_points", [792, 1224])
def test_native_pdf_render_accepts_different_sheet_sizes(tmp_path, width_points):
    from PIL import Image
    from pypdf import PdfWriter

    pdf, png = tmp_path / "native.pdf", tmp_path / "native.png"
    writer = PdfWriter()
    writer.add_blank_page(width=width_points, height=612)
    with pdf.open("wb") as stream:
        writer.write(stream)
    probe.render_pdf_png(pdf, png)
    with Image.open(png) as picture:
        assert picture.size == (math.ceil(width_points * (300 / 72)), 2550)


@pytest.mark.parametrize("outcome", ["passed", "failed"])
def test_worker_never_opens_original_and_exports_even_after_witness_failure(
    monkeypatch, tmp_path, outcome
):
    from solidworks_mcp.adapters.solidworks import drawing

    source = tmp_path / "original.SLDPRT"
    source.write_bytes(b"unchanged native source")
    directory = tmp_path / "unique"
    directory.mkdir()
    adapter, model = Mock(), Mock()
    adapter.swApp.CloseAllDocuments.return_value = True
    opened = []

    async def open_model(path):
        opened.append(Path(path))
        adapter.currentModel = model
        model.GetPathName.return_value = path
        return object()

    def create_drawing(adapter):
        adapter.currentModel = model

    def save_drawing(adapter, path, *, pdf_path):
        Path(path).write_bytes(b"new drawing")
        Path(pdf_path).write_bytes(b"new pdf")

    records = valid_records()
    if outcome == "failed":
        records[0]["face_identity"] = -1
    adapter.open_model = open_model
    monkeypatch.setattr(probe, "_early_bound", lambda item, name: item)
    monkeypatch.setattr(probe, "check", lambda label, result: None)
    monkeypatch.setattr(probe, "source_snapshot", lambda *args: valid_records())
    monkeypatch.setattr(
        probe, "drawing_snapshot", lambda *args: {"annotations": records}
    )
    monkeypatch.setattr(probe, "import_native_pmi", lambda drawing: [])
    monkeypatch.setattr(drawing, "new_drawing", create_drawing)
    monkeypatch.setattr(drawing, "save_drawing", save_drawing)
    monkeypatch.setattr(
        probe, "render_pdf_png", lambda pdf, png: png.write_bytes(b"new png")
    )
    if outcome == "failed":
        with pytest.raises(RuntimeError, match="face_identity=-1"):
            asyncio.run(probe.probe(adapter, source, directory))
    else:
        asyncio.run(probe.probe(adapter, source, directory))
    assert source not in opened
    assert len(opened) == 2
    assert all(path.parent == directory for path in opened)
    assert source.read_bytes() == b"unchanged native source"
    report = json.loads((directory / "observations.json").read_text())
    assert report["machine_witness"] == outcome
    assert report["visual_review"] == "pending"
    assert (
        report["sha256_before"]
        == report["source_sha256_after"]
        == report["copy_sha256_after"]
    )
    for stage in ("initial", "reopened"):
        assert all(Path(path).is_file() for path in report[stage]["exports"].values())
