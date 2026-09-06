"""No-setter retained exports must preserve source files and user documents."""

import ast
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import probe_retained_drawing_export as probe
from diagnostics import _owned_native_documents as owned
from test_owned_native_documents_drawing import Model, native  # noqa: F401


def test_pdf_only_uses_exact_existing_production_branch_once(tmp_path):
    path, pdf = tmp_path / "copy.SLDDRW", tmp_path / "export.pdf"
    calls = []

    def save(target, version, options):
        calls.append((target, version, options))
        Path(target).write_bytes(b"native PDF")
        return 0

    model = SimpleNamespace(GetPathName=lambda: str(path), SaveAs3=save)
    adapter = SimpleNamespace(
        currentModel=model,
        swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)),
        ownership=SimpleNamespace(assert_current_owned=Mock(), directories={tmp_path}),
    )
    assert probe.export_pdf_only(adapter, pdf) == {"pdf": str(pdf)}
    assert calls == [(str(pdf), 0, 0)]
    assert not path.exists()  # No native-drawing save was requested.
    assert adapter.ownership.assert_current_owned.call_count == 2


@pytest.mark.parametrize(
    "variant", ["existing", "outside", "native_suffix", "changed_path", "replaced"]
)
def test_export_refuses_overwrite_or_native_identity_change(
    tmp_path, monkeypatch, variant
):
    pdf = tmp_path / "export.pdf"
    paths = [str(tmp_path / "copy.SLDDRW")]
    model = SimpleNamespace(GetPathName=lambda: paths[0])
    adapter = SimpleNamespace(
        currentModel=model,
        swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)),
        ownership=SimpleNamespace(assert_current_owned=Mock(), directories={tmp_path}),
    )
    if variant == "existing":
        pdf.write_bytes(b"retained")
    if variant == "outside":
        adapter.ownership.directories.clear()
    if variant == "native_suffix":
        pdf = pdf.with_suffix(".SLDDRW")

    def save(_adapter, native_path, *, pdf_path):
        assert native_path == ""
        Path(pdf_path).write_bytes(b"newPDF")
        if variant == "changed_path":
            paths[0] = pdf_path
        if variant == "replaced":
            adapter.currentModel = object()
        return {"pdf": pdf_path}

    writer = Mock(side_effect=save)
    monkeypatch.setattr(probe, "native_save", writer)
    with pytest.raises(RuntimeError):
        probe.export_pdf_only(adapter, pdf)
    if variant in ("existing", "outside", "native_suffix"):
        writer.assert_not_called()


def test_title_fields_only_read_documented_standard_note_properties(monkeypatch):
    monkeypatch.setattr(probe, "_early_bound", lambda value, _: value)
    note = SimpleNamespace(
        GetText=lambda: "rocker-arm",
        PropertyLinkedText='$PRPSHEET:"Description"',
        GetTextJustification=lambda: 2,
        GetTextVerticalJustification=lambda: 1,
        LockPosition=False,
        GetExtent=lambda: (0.361, 0.040, 0.0, 0.398, 0.047, 0.0),
    )
    annotation = SimpleNamespace(
        GetName=lambda: "DetailItem245",
        GetType=lambda: 6,
        OwnerType=2,
        GetSpecificAnnotation=lambda: note,
        GetPosition=lambda: (0.379, 0.046, 0.0),
    )
    view = SimpleNamespace(
        GetName2=lambda: "Sheet1", GetAnnotations=lambda: (annotation,)
    )
    adapter = SimpleNamespace(currentModel=SimpleNamespace(GetViews=lambda: ((view,),)))
    result = probe.title_fields(adapter)
    assert result["linked_text"] == '$PRPSHEET:"Description"'
    assert result["horizontal_justification"] == 2
    assert result["vertical_justification"] == 1
    note.GetText = lambda: "wrong title"
    with pytest.raises(RuntimeError, match="content changed"):
        probe.title_fields(adapter)


def test_entrypoint_disables_autostart_before_parent_runner(tmp_path, monkeypatch):
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "1")
    with pytest.raises(RuntimeError, match="AUTOSTART=0"):
        probe.main(["--receipt", str(tmp_path / "missing.json")])


def test_no_layout_setter_or_rebuild_or_native_save_in_control_source():
    tree = ast.parse(Path(probe.__file__).read_text())
    forbidden = {
        "SetPosition2",
        "EditRebuild3",
        "ForceRebuild3",
        "SetText",
        "SetUserPreferenceDouble",
        "SetUserPreferenceToggle",
        "CloseAllDocuments",
        "Save3",
        "SaveAs3",
    }
    assert not [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr in forbidden
    ]


def test_png_delta_counts_pixels_not_channels_and_no_threshold(tmp_path):
    from PIL import Image

    before, after = tmp_path / "before.png", tmp_path / "after.png"
    image = Image.new("RGB", (3, 2), "white")
    image.save(before)
    image.putpixel((1, 0), (254, 255, 255))
    image.putpixel((2, 1), (0, 0, 0))
    image.save(after)
    result = probe.compare_png(before, after)
    assert result["changed_pixel_count"] == 2
    assert result["changed_pixel_bounds"] == (1, 0, 3, 2)
    assert result["max_channel_delta"] == 255


def test_final_hash_receipt_survives_missing_file(tmp_path):
    missing = str(tmp_path / "missing.SLDPRT")
    assert "error" in probe.final_hashes((missing,))[missing]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode", ["normal", "export_failure", "part_saved", "drawing_saved"]
)
async def test_owned_copy_and_protected_references_preserve_baseline_on_all_exits(
    native,  # noqa: F811 - imported pytest fixture
    tmp_path,
    monkeypatch,
    mode,
):
    retained = tmp_path / "retained"
    retained.mkdir()
    part = retained / "exact-owned-original.SLDPRT"
    part.write_bytes(b"original part")
    artifacts = {
        key: retained / f"saved{suffix}"
        for key, suffix in (("drawing", ".SLDDRW"), ("pdf", ".pdf"), ("png", ".png"))
    }
    for path in artifacts.values():
        path.write_bytes(b"retained")
    source = {"configuration": "Default", "dimensions": {}}
    witness = {"semantics": {}, "annotations": {}, "layout": {}}
    trial = {
        "target": "rocker_arm",
        "copy_source": str(part),
        "copy_hashes": {"copied": probe.pilot.attachments.file_digest(part)},
        "artifacts": {key: str(path) for key, path in artifacts.items()},
        "source_before": source,
        "built": witness,
    }
    receipt = retained / "pilot.json"
    receipt.write_text(
        json.dumps(
            {
                "trials": [trial],
                "sources_before": {
                    str(native.source): probe.pilot.attachments.file_digest(
                        native.source
                    )
                },
            }
        )
    )
    monkeypatch.setattr(
        probe, "EXPECTED_RECEIPT_SHA256", probe.pilot.attachments.file_digest(receipt)
    )
    monkeypatch.setattr(
        probe,
        "EXPECTED_ARTIFACT_HASHES",
        {
            key: probe.pilot.attachments.file_digest(path)
            for key, path in artifacts.items()
        },
    )
    userpart, userdrawing = (
        Model(native.source, kind=1),
        Model(None, title="Draw2 - Sheet1", dirty=True),
    )
    native.app.documents.extend((userpart, userdrawing))
    native.app.ActiveDoc = userdrawing
    initial_open = native.adapter.open_model
    writes = []

    async def open_model(path):
        result = await initial_open(path)
        reference = Model(part, kind=1)
        native.app.documents.append(reference)
        native.adapter.currentModel.references = [reference]
        return result

    native.adapter.open_model = open_model
    monkeypatch.setattr(probe, "title_fields", lambda _: {"text": "rocker-arm"})
    monkeypatch.setattr(probe, "capture_drawing", lambda *_: (witness, {}))
    monkeypatch.setattr(
        probe.pilot, "source_dimensions", lambda model, *_: (source, {"native": model})
    )
    monkeypatch.setattr(probe.pilot.attachments, "compare", lambda *_: None)
    monkeypatch.setattr(probe.pilot.attachments, "check_layout", lambda *_: None)
    monkeypatch.setattr(probe, "pdf_title", lambda _: {"text": "rocker-arm", "x": 1.0})
    monkeypatch.setattr(
        probe, "render_pdf_png", lambda pdf, png: png.write_bytes(b"PNG")
    )
    monkeypatch.setattr(probe, "compare_png", lambda *_: {"changed_pixel_count": 0})

    def export(adapter, pdf):
        adapter.ownership.assert_current_owned()
        writes.append(pdf)
        if mode == "export_failure":
            raise RuntimeError("native PDF failed")
        pdf.write_bytes(b"PDF")
        if mode == "part_saved":
            part.write_bytes(b"unauthorized source save")
        if mode == "drawing_saved":
            Path(adapter.currentModel.GetPathName()).write_bytes(
                b"unauthorized drawing save"
            )

    monkeypatch.setattr(probe, "export_pdf_only", export)

    async def callback(adapter):
        return await probe.probe(adapter, receipt, tmp_path / "output")

    if mode == "normal":
        await owned.owned_callback(native.adapter, callback)
    else:
        with pytest.raises((RuntimeError, ExceptionGroup)):
            await owned.owned_callback(native.adapter, callback)
    assert len(writes) == 1
    assert native.app.documents == [userpart, userdrawing]
    assert not userpart.dirty and userdrawing.dirty
    assert all(model not in (userpart, userdrawing) for model in native.app.closes)
    assert artifacts["drawing"].read_bytes() == b"retained"
    (report_path,) = (tmp_path / "output").glob("*/retained-export.json")
    report = json.loads(report_path.read_text())
    assert report["status"] == ("observed" if mode == "normal" else "failed")
    if mode == "part_saved":
        assert report["inputs_before"][str(part)] != report["inputs_after"][str(part)]


def test_pdf_readback_records_actual_glyph_boxes_and_rejects_missing_title(tmp_path):
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=1224, height=792)
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {
                    NameObject("/F1"): DictionaryObject(
                        {
                            NameObject("/Type"): NameObject("/Font"),
                            NameObject("/Subtype"): NameObject("/Type1"),
                            NameObject("/BaseFont"): NameObject("/Helvetica"),
                        }
                    )
                }
            )
        }
    )
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 20 Tf 100 120 Td (rocker-arm) Tj ET")
    page.replace_contents(content)
    pdf = tmp_path / "title.pdf"
    with pdf.open("wb") as stream:
        writer.write(stream)
    result = probe.pdf_title(pdf)
    assert result["text"] == "rocker-arm"
    assert len(result["characters"]) == 10
    assert 99 < result["ink_box_pt"][0] < 102
    with pytest.raises(RuntimeError, match="one exact"):
        probe.pdf_title(pdf, "nonexistent")
