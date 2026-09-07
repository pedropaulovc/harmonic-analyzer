"""Viewport-only template experiment, with real owned-document cleanup."""

import asyncio
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from diagnostics import _owned_native_documents as owned
from diagnostics import probe_prepared_viewport as probe
from test_owned_native_documents_drawing import Model, native  # noqa: F401


@pytest.fixture
def scene(native, monkeypatch, tmp_path):  # noqa: F811
    for name, value in {
        "HARMONIC_SW_AUTOSTART": "0",
        "HARMONIC_REMOTE_CACHE_MODE": "off",
        "HARMONIC_DIAGNOSTIC_SW_PID": "123",
        "HARMONIC_COM_SEAT": "test",
    }.items():
        monkeypatch.setenv(name, value)
    template = tmp_path / "prepared.DRWDOT"
    template.write_bytes(b"immutable retained template")
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "saved_path": str(template),
                "status": "failed",
                "inputs": {"spec": {"scale": [1, 1], "decimals": 2}},
            }
        )
    )
    pins = probe.read_inputs(
        receipt,
        probe.base.prepared._sha(receipt),
        template,
        probe.base.prepared._sha(template),
    )
    baseline = Model(None, title="Existing dirty drawing", dirty=True)
    native.app.documents.append(baseline)
    native.app.ActiveDoc = baseline
    native.app.GetProcessID = lambda: 123
    calls, faults, created = [], {}, []

    class View:
        _scale = 1.0

        @property
        def Scale2(self):
            return self._scale

        @Scale2.setter
        def Scale2(self, value):
            calls.append(("scale", value))
            if faults.get("clamp") and value == 2:
                return
            self._scale = value

        @property
        def Transform(self):
            return SimpleNamespace(ArrayData=(1.0,) * 16)

        def GetVisibleBox(self):
            return (0, 0, 1200, 800)

    annotation = SimpleNamespace(GetName=lambda: "Note1", GetType=lambda: 6)
    sheet_view = SimpleNamespace(GetAnnotations=lambda: [annotation])

    class Drawing(Model):
        def __init__(self):
            super().__init__(None, title="Owned viewport blank")
            self.ActiveView = View()

        def GetViews(self):
            return ((sheet_view,),)

        def EditSheet(self):
            calls.append("edit_sheet")

        def ViewZoomtofit2(self):
            calls.append("fit")

        def GraphicsRedraw2(self):
            calls.append(("redraw", self.ActiveView.Scale2))

    def create(adapter, **kwargs):
        assert kwargs["template"] == str(template)
        if faults.get("open"):
            raise RuntimeError("injected create failure")
        model = Drawing()
        created.append(model)
        native.app.documents.append(model)
        native.app.ActiveDoc = model
        adapter.currentModel = model
        return model

    def snapshot(adapter, spec):
        scale = adapter.currentModel.ActiveView.Scale2
        calls.append(("snapshot", scale))
        extent = [0.1, 0.2, 0.0, 0.3, 0.4, 0.0]
        if scale == 2:
            extent[0] += 0.000044
        if faults.get("restore") and len([r for r in calls if r[0] == "redraw"]) == 3:
            extent[0] += 1e-12
        text = "CHANGED" if faults.get("text") and scale == 2 else "A"
        return {
            "sheet_notes": [
                {
                    "text": text,
                    "linked_text": "",
                    "extent": extent,
                    "measured": {
                        "anchor": [0.1, 0.2],
                        "body": {"xmin": extent[0]},
                        "envelope": {"xmin": extent[0]},
                        "text_runs": ["A"],
                    },
                }
            ],
            "sheet_surface_finishes": [],
        }

    def printed(adapter, directory):
        calls.append(("export", adapter.currentModel.ActiveView.Scale2))
        if faults.get("export"):
            raise RuntimeError("injected PDF failure")
        if faults.get("identity"):
            sheet_view.GetAnnotations = lambda: [
                SimpleNamespace(GetName=lambda: "Note1", GetType=lambda: 6)
            ]
        if faults.get("source"):
            template.write_bytes(b"changed immutable input")
        if faults.get("active"):
            native.app.ActiveDoc = baseline
        return {
            "glyphs": ["A"],
            "paths": [1],
            "page_size_pt": [100, 100],
            "vector_status": "failed"
            if faults.get("vector")
            else "supported_paths_and_object_inventory_captured",
            "objects": [{"type": 3, "matrix": [1, 0, 0, 1, 0, 0]}],
            "full_page_raster": {
                "pixel_sha256": "identical",
                "size": [100, 100],
                "mode": "RGB",
            },
        }

    monkeypatch.setattr(probe, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(probe.base, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(probe.base.common, "new_drawing", create)
    monkeypatch.setattr(probe, "snapshot_defaults", snapshot)
    monkeypatch.setattr(probe, "printed_snapshot", printed)
    monkeypatch.setattr(
        probe.base, "compare_printed", lambda a, b: {"changed_pixel_count": 0}
    )
    monkeypatch.setattr(probe, "runtime_inputs", lambda adapter, spec: {"frozen": 1})
    reports = tmp_path / "reports"

    def run():
        return asyncio.run(
            owned.owned_callback(
                native.adapter, lambda adapter: probe.probe(adapter, pins, reports, 123)
            )
        )

    def report():
        paths = list(reports.glob("*/measurements.json"))
        assert len(paths) == 1
        return json.loads(paths[0].read_text())

    return SimpleNamespace(**locals())


def test_one_blank_three_absolute_scales_no_save_preserves_dirty_baseline(scene):
    scene.run()
    report = scene.report()
    assert report["status"] == "passed"
    assert [row["variant"] for row in report["arms"]] == [
        "a_initial",
        "b_zoom",
        "a_restored",
    ]
    assert [c for c in scene.calls if c[0] == "redraw"] == [
        ("redraw", 1.0),
        ("redraw", 2.0),
        ("redraw", 1.0),
    ]
    assert len([c for c in scene.calls if c[0] == "export"]) == 3
    assert len([c for c in scene.calls if c[0] == "snapshot"]) == 6
    assert report["comparisons"]["a_b_strict_defaults"]["status"] == "different"
    assert report["comparisons"]["a_a_strict_defaults"]["status"] == "passed"
    assert report["comparisons"]["a_b_semantics"]["status"] == "passed"
    assert len(scene.created) == 1
    assert scene.native.app.closes == scene.created
    assert scene.native.app.documents == [scene.baseline]
    assert scene.baseline.dirty and scene.baseline.Visible
    assert scene.native.adapter.opens == []


@pytest.mark.parametrize(
    "fault",
    [
        "restore",
        "text",
        "identity",
        "source",
        "export",
        "open",
        "vector",
        "active",
        "clamp",
    ],
)
def test_failure_retains_evidence_and_scoped_cleanup(scene, fault):
    scene.faults[fault] = True
    with pytest.raises(Exception):
        scene.run()
    assert scene.report()["status"] == "failed"
    assert scene.native.app.documents == [scene.baseline]
    if fault in ("restore", "text", "export"):
        assert len(scene.report()["arms"]) == 3


def test_strict_a_a_extent_failure_does_not_discard_independent_pdf_verdict(scene):
    scene.faults["restore"] = True
    with pytest.raises(Exception):
        scene.run()
    comparisons = scene.report()["comparisons"]
    assert comparisons["a_a_strict_defaults"]["status"] == "failed"
    assert comparisons["a_a_printed"]["status"] == "passed"


def test_vector_failure_keeps_pdf_verdict_and_all_raw_arms(scene):
    scene.faults["vector"] = True
    with pytest.raises(Exception):
        scene.run()
    report = scene.report()
    assert len(report["arms"]) == 3
    assert report["comparisons"]["a_a_printed"]["status"] == "passed"
    assert (
        report["comparisons"]["a_a_supported_paths_and_inventory"]["status"] == "failed"
    )


def test_hash_mismatch_rejected_before_any_document_creation(scene):
    with pytest.raises(RuntimeError, match="SHA"):
        probe.read_inputs(
            scene.receipt,
            "0" * 64,
            scene.template,
            probe.base.prepared._sha(scene.template),
        )
    assert not scene.created


def test_semantic_alignment_rejects_duplicates_and_preserves_style():
    row = {
        "text": "A",
        "linked_text": "",
        "extent": [0] * 6,
        "horizontal_justification": 1,
        "measured": {"anchor": [1, 2], "body": {}, "envelope": {}},
    }
    before = {"sheet_notes": [row]}
    after = deepcopy(before)
    after["sheet_notes"][0]["horizontal_justification"] = 2
    assert probe.semantic_defaults(before) != probe.semantic_defaults(after)
    with pytest.raises(RuntimeError, match="ambiguous"):
        probe.semantic_defaults({"sheet_notes": [row, row]})


def test_viewport_rejects_invisible_doc_before_invalid_extent_api(scene):
    model = Model(None, visible=False)
    with pytest.raises(RuntimeError, match="visible"):
        probe.viewport(model)


def test_required_recipe_gate_enrolls_viewport_regressions():
    import dodo

    tasks = list(dodo.task_check())
    recipe = next(task for task in tasks if task["name"] == "recipe")
    assert Path(__file__).resolve() in {
        Path(path).resolve() for path in recipe["file_dep"]
    }


@pytest.mark.parametrize(
    "scale,transform,pixels",
    [
        (float("nan"), [1.0] * 16, [0, 0, 10, 10]),
        (0, [1.0] * 16, [0, 0, 10, 10]),
        (1, [float("inf")] * 16, [0, 0, 10, 10]),
        (1, [1.0] * 15, [0, 0, 10, 10]),
        (1, [1.0] * 16, [0, 0, 0, 10]),
        (1, [1.0] * 16, [0.0, 0.0, 10.0, 10.0]),
    ],
)
def test_invalid_native_viewport_is_not_coerced(scene, scale, transform, pixels):
    model = SimpleNamespace(
        Visible=True,
        ActiveView=SimpleNamespace(
            Scale2=scale,
            Transform=SimpleNamespace(ArrayData=transform),
            GetVisibleBox=lambda: pixels,
        ),
    )
    with pytest.raises(RuntimeError, match="invalid native viewport"):
        probe.viewport(model)


def test_parent_guard_runs_before_any_seat_or_worker_launch(scene, monkeypatch):
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "1")
    with pytest.raises(RuntimeError, match="AUTOSTART"):
        probe.main(
            [
                "--expected-pid",
                "123",
                "--receipt",
                str(scene.receipt),
                "--receipt-sha256",
                scene.pins["receipt"]["sha256"],
                "--template",
                str(scene.template),
                "--template-sha256",
                scene.pins["template"]["sha256"],
            ]
        )
    assert not scene.created


def test_runtime_fingerprint_includes_actual_probe_and_imported_helpers(monkeypatch):
    monkeypatch.setattr(probe.base, "runtime_inputs", lambda *args: {"pinned": 1})
    result = probe.runtime_inputs(None, None)["diagnostic_closure"]
    assert "cad/scripts/diagnostics/probe_prepared_viewport.py" in result
    assert "cad/scripts/diagnostics/probe_prepared_template_cache.py" in result
    assert "cad/scripts/diagnostics/_populated_template_symbols.py" in result


def test_vector_reader_rejection_preserves_existing_glyph_receipt(
    monkeypatch, tmp_path
):
    import pypdfium2 as pdfium
    import pypdfium2.raw as raw

    class Document:
        def __enter__(self):
            return [
                SimpleNamespace(
                    get_objects=lambda **kwargs: [
                        SimpleNamespace(
                            type=raw.FPDF_PAGEOBJ_FORM,
                            level=0,
                            get_matrix=lambda: SimpleNamespace(
                                get=lambda: (1, 0, 0, 1, 0, 0)
                            ),
                            get_bounds=lambda: (0, 0, 1, 1),
                        )
                    ]
                )
            ]

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(
        probe.base,
        "printed_witness",
        lambda *args: {
            "pdf": "retained.pdf",
            "glyphs": ["retained glyph"],
            "sha256": {"pdf": "hash"},
        },
    )
    monkeypatch.setattr(pdfium, "PdfDocument", lambda *args: Document())
    result = probe.printed_snapshot(None, tmp_path)
    assert result["vector_status"] == "failed"
    assert result["glyphs"] == ["retained glyph"]
    assert result["pdf"] == "retained.pdf"
    assert "unsupported PDF object" in result["vector_error"]


def test_supported_image_inventory_cannot_pass_without_exact_printed_appearance(
    scene, monkeypatch
):
    def fail(*args):
        raise RuntimeError("image appearance pixel comparison failed")

    monkeypatch.setattr(probe.base, "compare_printed", fail)
    with pytest.raises(Exception):
        scene.run()
    report = scene.report()
    assert (
        report["comparisons"]["a_a_supported_paths_and_inventory"]["status"] == "passed"
    )
    assert report["comparisons"]["a_a_printed"]["status"] == "failed"
    assert report["status"] == "failed"


def test_cropped_preview_cannot_hide_uncropped_bottom_row_change(monkeypatch):
    monkeypatch.setattr(
        probe.base, "compare_printed", lambda *args: {"changed_pixel_count": 0}
    )
    before = {"full_page_raster": {"pixel_sha256": "before", "size": [5100, 3301]}}
    after = deepcopy(before)
    after["full_page_raster"]["pixel_sha256"] = "changed last row"
    with pytest.raises(RuntimeError, match="uncropped"):
        probe.compare_appearance(before, after)
    with pytest.raises(RuntimeError, match="unavailable"):
        probe.compare_appearance(before, {})


def test_complete_supported_object_inventory_and_flat_paths_are_exact(
    monkeypatch, tmp_path
):
    import pypdfium2 as pdfium
    import pypdfium2.raw as raw

    def obj(kind):
        return SimpleNamespace(
            type=kind,
            level=0,
            get_matrix=lambda: SimpleNamespace(get=lambda: (1, 0, 0, 1, 0, 0)),
            get_bounds=lambda: (0, 0, 1, 1),
        )

    class Document:
        def __enter__(self):
            return [
                SimpleNamespace(
                    get_objects=lambda **kwargs: [
                        obj(raw.FPDF_PAGEOBJ_IMAGE),
                        obj(raw.FPDF_PAGEOBJ_PATH),
                        obj(raw.FPDF_PAGEOBJ_TEXT),
                    ]
                )
            ]

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(
        probe.base, "printed_witness", lambda *args: {"pdf": "retained.pdf"}
    )
    monkeypatch.setattr(probe.symbols, "path_snapshot", lambda obj: {"segments": [1]})
    monkeypatch.setattr(pdfium, "PdfDocument", lambda *args: Document())
    result = probe.printed_snapshot(None, tmp_path)
    assert result["vector_status"] == "supported_paths_and_object_inventory_captured"
    assert [obj["type"] for obj in result["objects"]] == [3, 2, 1]
    assert len(result["paths"]) == 1
    probe.compare_vectors(result, deepcopy(result))
    changed = deepcopy(result)
    changed["objects"][0]["bounds_pt"][0] += 1e-12
    with pytest.raises(RuntimeError, match="exact PDF"):
        probe.compare_vectors(result, changed)
    changed = deepcopy(result)
    changed["paths"][0]["segments"] = [2]
    with pytest.raises(RuntimeError, match="exact PDF"):
        probe.compare_vectors(result, changed)
