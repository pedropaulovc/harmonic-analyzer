"""Viewport-only template experiment, with real owned-document cleanup."""

import asyncio
from copy import deepcopy
import inspect
import json
import math
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

from diagnostics import _owned_native_documents as owned
from diagnostics import probe_prepared_viewport as probe
from test_owned_native_documents_drawing import Model, native  # noqa: F401


def _runtime_failure(message):
    return pytest.RaisesExc(RuntimeError, match=f"^{re.escape(message)}$")


def _viewport_failure(*messages):
    return pytest.RaisesGroup(
        *(_runtime_failure(message) for message in messages),
        match="^prepared viewport control failed$",
    )


def _fault_failure(fault):
    if fault == "source":
        return pytest.RaisesGroup(
            _viewport_failure(
                "pinned input/runtime bytes changed",
                "pinned input/runtime bytes changed",
            ),
            _runtime_failure("diagnostic source files changed; see ownership evidence"),
            match="^diagnostic failure with preserved cleanup/source evidence$",
        )
    messages = {
        "restore": ("prepared template raw defaults did not persist exactly",),
        "text": ("exact captured fields differ",),
        "identity": ("native blank annotation/view identity changed",),
        "export": ("injected PDF failure",) * 3,
        "open": ("injected create failure",),
        "vector": ("exact PDF vector geometry/inventory differs",) * 2,
        "active": ("native write requires the exact owned active document",),
        "clamp": ("native viewport scale assignment did not persist",),
        "pan_drift": (
            "prepared template raw defaults did not persist exactly",
            "exact captured fields differ",
        ),
        "translation_readback": ("native original Translation3 readback differs",),
        "null_vector": ("native CreateVector returned null",),
        "orientation": ("native Scale2 changed the original orientation",),
    }
    return _viewport_failure(*messages[fault])


@pytest.mark.parametrize(
    "test_name,arguments",
    [
        ("test_failure_retains_evidence_and_scoped_cleanup", {"fault": "restore"}),
        ("test_strict_a_a_extent_failure_does_not_discard_independent_pdf_verdict", {}),
        ("test_vector_failure_keeps_pdf_verdict_and_all_raw_arms", {}),
        (
            "test_supported_image_inventory_cannot_pass_without_exact_printed_appearance",
            {},
        ),
        ("test_zoom_only_pan_failure_remains_failed_without_translation_writes", {}),
        (
            "test_controlled_translation_rejects_failed_native_readback_before_measurement",
            {"fault": "null_vector"},
        ),
    ],
)
@pytest.mark.parametrize("replacement", ["assertion", "wrong_leaf", "wrong_owner"])
def test_failure_assertions_reject_unrelated_errors_despite_valid_failed_receipt(
    scene, monkeypatch, test_name, arguments, replacement
):
    run = scene.run

    def replace_failure(**kwargs):
        try:
            run(**kwargs)
        except ExceptionGroup as original:
            if replacement == "assertion":
                raise AssertionError("unrelated programming failure") from original
            if replacement == "wrong_leaf":
                raise ExceptionGroup(
                    original.message, [RuntimeError("unrelated runtime failure")]
                ) from original
            raise ExceptionGroup(
                "unrelated group owner", original.exceptions
            ) from original
        raise AssertionError("real fault did not execute")

    scene.run = replace_failure
    test = globals()[test_name]
    keywords = {"scene": scene, **arguments}
    if "monkeypatch" in inspect.signature(test).parameters:
        keywords["monkeypatch"] = monkeypatch
    with pytest.raises(
        pytest.fail.Exception, match="Raised exception group did not match"
    ):
        test(**keywords)


@pytest.mark.parametrize(
    "field",
    [
        "saved_path",
        "status",
        "inputs",
        "inputs.spec",
        "inputs.spec.scale",
        "inputs.spec.decimals",
    ],
)
def test_incomplete_retained_receipt_names_missing_field_before_native_work(
    tmp_path, field
):
    template = tmp_path / "prepared.DRWDOT"
    template.write_bytes(b"retained failed preparation")
    data = {
        "saved_path": str(template),
        "status": "failed",
        "inputs": {"spec": {"scale": [1, 1], "decimals": 2}},
    }
    parent = data
    *ancestors, leaf = field.split(".")
    for key in ancestors:
        parent = parent[key]
    del parent[leaf]
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps(data), encoding="utf-8")
    before = receipt.read_bytes(), template.read_bytes()
    with pytest.raises(RuntimeError) as caught:
        probe.read_inputs(
            receipt,
            probe.base.prepared._sha(receipt),
            template,
            probe.base.prepared._sha(template),
        )
    assert str(receipt.resolve()) in str(caught.value)
    assert field in str(caught.value)
    assert (receipt.read_bytes(), template.read_bytes()) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("receipt", []),
        ("saved_path", None),
        ("saved_path", " "),
        ("status", False),
        ("status", ""),
        ("inputs", []),
        ("inputs.spec", None),
        ("inputs.spec.scale", None),
        ("inputs.spec.scale", [1]),
        ("inputs.spec.scale", [True, 1]),
        ("inputs.spec.scale", ["1", 1]),
        ("inputs.spec.decimals", True),
        ("inputs.spec.decimals", 4),
    ],
)
def test_malformed_retained_receipt_has_actionable_input_error(tmp_path, field, value):
    template = tmp_path / "prepared.DRWDOT"
    template.write_bytes(b"retained failed preparation")
    data = {
        "saved_path": str(template),
        "status": "failed",
        "inputs": {"spec": {"scale": [1, 1], "decimals": 2}},
    }
    if field == "receipt":
        data = value
    if field != "receipt":
        parent = data
        *ancestors, leaf = field.split(".")
        for key in ancestors:
            parent = parent[key]
        parent[leaf] = value
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(RuntimeError) as caught:
        probe.read_inputs(
            receipt,
            probe.base.prepared._sha(receipt),
            template,
            probe.base.prepared._sha(template),
        )
    assert str(receipt.resolve()) in str(caught.value)
    assert "retained receipt" in str(caught.value)


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
    calls, faults, created, vectors = [], {}, [], []

    class View:
        _scale = 1.0

        def __init__(self):
            self._translation = [0.012, -0.005, 0.0]

        @property
        def Scale2(self):
            return self._scale

        @Scale2.setter
        def Scale2(self, value):
            calls.append(("scale", value))
            if faults.get("clamp") and value == 2:
                return
            self._scale = value
            if faults.get("pan_drift"):
                self._translation[0] += 0.01

        @property
        def Transform(self):
            matrix = [1.0] * 16
            matrix[9:12] = self._translation
            matrix[12] = self._scale
            return SimpleNamespace(ArrayData=matrix)

        @property
        def Translation3(self):
            return SimpleNamespace(ArrayData=tuple(self._translation))

        @Translation3.setter
        def Translation3(self, vector):
            calls.append(("translation", vector))
            self._translation = list(vector.ArrayData)
            if faults.get("translation_readback"):
                self._translation[0] += 1e-12

        @property
        def Orientation3(self):
            matrix = [1.0] * 16
            if faults.get("orientation") and self._scale == 2:
                matrix[0] += 1e-12
            return SimpleNamespace(ArrayData=matrix)

        def GetVisibleBox(self):
            return (0, 0, 1200, 800)

    def create_vector(values):
        calls.append(("create_vector", values))
        if faults.get("null_vector"):
            return None
        vector = SimpleNamespace(
            ArrayData=tuple(values.value if hasattr(values, "value") else values)
        )
        vectors.append(vector)
        return vector

    native.app.GetMathUtility = lambda: SimpleNamespace(CreateVector=create_vector)

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
        extent[0] += adapter.currentModel.ActiveView._translation[0]
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
    monkeypatch.setattr(probe.viewports, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(probe.base, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(probe.base.sheet_setup, "new_drawing", create)
    monkeypatch.setattr(probe, "snapshot_defaults", snapshot)
    monkeypatch.setattr(probe, "printed_snapshot", printed)
    monkeypatch.setattr(
        probe.base, "compare_printed", lambda a, b: {"changed_pixel_count": 0}
    )
    monkeypatch.setattr(probe, "runtime_inputs", lambda adapter, spec: {"frozen": 1})
    reports = tmp_path / "reports"

    def run(**kwargs):
        return asyncio.run(
            owned.owned_callback(
                native.adapter,
                lambda adapter: probe.probe(adapter, pins, reports, 123, **kwargs),
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
    with _fault_failure(fault):
        scene.run()
    assert scene.report()["status"] == "failed"
    assert scene.native.app.documents == [scene.baseline]
    if fault in ("restore", "text", "export"):
        assert len(scene.report()["arms"]) == 3


def test_strict_a_a_extent_failure_does_not_discard_independent_pdf_verdict(scene):
    scene.faults["restore"] = True
    with _fault_failure("restore"):
        scene.run()
    comparisons = scene.report()["comparisons"]
    assert comparisons["a_a_strict_defaults"]["status"] == "failed"
    assert comparisons["a_a_printed"]["status"] == "passed"


def test_vector_failure_keeps_pdf_verdict_and_all_raw_arms(scene):
    scene.faults["vector"] = True
    with _fault_failure("vector"):
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
            Translation3=SimpleNamespace(ArrayData=(0.0, 0.0, 0.0)),
            Orientation3=SimpleNamespace(ArrayData=(1.0,) * 16),
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
    with _viewport_failure(*("image appearance pixel comparison failed",) * 2):
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


def test_original_translation_controls_scale_setter_pan_drift(scene):
    scene.faults["pan_drift"] = True
    scene.run(translation=probe.Translation.ORIGINAL)
    report = scene.report()
    assert report["status"] == "passed"
    assert report["translation"] == "original"
    assert len(scene.vectors) == 3
    assert len({id(vector) for vector in scene.vectors}) == 3
    requests = [item[1] for item in scene.calls if item[0] == "create_vector"]
    for request in requests:
        if hasattr(request, "varianttype"):
            assert request.varianttype == 8197  # VT_ARRAY | VT_R8
    original = report["initial_viewport"]["translation3"]
    for arm in report["arms"]:
        assert arm["after_scale_viewport"]["translation3"] != original
        assert arm["viewport"]["translation3"] == original
        assert (
            arm["viewport"]["orientation3"]
            == report["initial_viewport"]["orientation3"]
        )
    assert report["comparisons"]["a_a_strict_defaults"]["status"] == "passed"


def test_zoom_only_pan_failure_remains_failed_without_translation_writes(scene):
    scene.faults["pan_drift"] = True
    with _fault_failure("pan_drift"):
        scene.run()
    report = scene.report()
    assert report["translation"] == "native"
    assert report["comparisons"]["a_a_strict_defaults"]["status"] == "failed"
    assert report["comparisons"]["a_a_viewport"]["status"] == "failed"
    assert not scene.vectors
    assert not [call for call in scene.calls if call[0] == "translation"]


@pytest.mark.parametrize(
    "fault", ["translation_readback", "null_vector", "orientation"]
)
def test_controlled_translation_rejects_failed_native_readback_before_measurement(
    scene, fault
):
    scene.faults[fault] = True
    with _fault_failure(fault):
        scene.run(translation=probe.Translation.ORIGINAL)
    report = scene.report()
    assert report["status"] == "failed"
    assert "defaults" not in report["arms"][-1]
    assert scene.native.app.documents == [scene.baseline]


def test_controlled_translation_cli_forwards_same_policy_to_owned_worker(
    scene, monkeypatch
):
    import dodo

    calls = []
    monkeypatch.setattr(dodo, "_run", lambda argv, *a, **k: calls.append(argv))
    args = [
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
        "--translation",
        "original",
    ]
    assert probe.main(args) == 0
    assert calls[0][calls[0].index("--translation") + 1] == "original"
    observed = []

    async def worker(*args, **kwargs):
        observed.append(kwargs["translation"])
        return 0

    monkeypatch.setattr(probe, "probe", worker)
    monkeypatch.setattr(
        probe.owned, "run_copy_diagnostic", lambda callback: asyncio.run(callback(None))
    )
    assert probe.main([*args, "--worker"]) == 0
    assert observed == [probe.Translation.ORIGINAL]


@pytest.mark.parametrize(
    "fault", ["active", "pixel_box", "orientation", "translation_readback"]
)
def test_shared_restore_preserves_failed_native_context_observations(scene, fault):
    model = scene.Drawing()
    scene.native.app.ActiveDoc = model
    target = probe.viewports.capture(model)
    observation = {}
    if fault == "active":
        scene.native.app.ActiveDoc = scene.baseline
    if fault == "pixel_box":
        model.ActiveView.GetVisibleBox = lambda: (0, 0, 1201, 800)
    if fault == "orientation":
        scene.faults["orientation"] = True
        model.ActiveView._scale = 2
    if fault == "translation_readback":
        scene.faults["translation_readback"] = True
    with pytest.raises(RuntimeError):
        probe.viewports.restore(scene.native.app, model, target, observation)
    assert observation["status"] == "failed" and observation["target"] == target
    assert "error" in observation
    if fault in ("active", "pixel_box", "orientation"):
        assert scene.calls == []
    if fault == "translation_readback":
        assert observation["after"]["translation3"] != target["translation3"]


@pytest.mark.parametrize(
    "readback",
    [1.0, 1.5, math.nextafter(2.0, 0.0)],
    ids=["ignored", "clamped", "one_ulp_low"],
)
def test_shared_restore_rejected_scale_stops_before_translation_and_redraw(
    scene, monkeypatch, readback
):
    model = scene.Drawing()
    scene.native.app.ActiveDoc = model
    view = model.ActiveView
    view._scale = 2.0
    target = probe.viewports.capture(model)
    view._scale = 1.0
    view._translation[0] += 0.02
    before = probe.viewports.capture(model)

    def rejected_scale(native_view, value):
        scene.calls.append(("scale", value))
        native_view._scale = readback

    monkeypatch.setattr(scene.View, "Scale2", scene.View.Scale2.setter(rejected_scale))
    observation = {}
    with pytest.raises(RuntimeError) as caught:
        probe.viewports.restore(scene.native.app, model, target, observation)

    assert observation["status"] == "failed"
    assert observation["target"] == target
    assert observation["before"] == before
    assert observation["after_scale"]["scale2"] == readback
    assert observation["after_scale"]["scale2"] != target["scale2"]
    assert observation["after_scale"]["orientation3"] == target["orientation3"]
    # Rejected scale readback stops before translation, vector creation or redraw.
    assert scene.calls == [("scale", 2.0)]
    assert scene.vectors == []
    assert view._translation == before["translation3"]
    assert "after" not in observation
    assert str(caught.value) == "native viewport scale assignment did not persist"
    assert observation["error"] == repr(caught.value)


def test_shared_restore_accepted_scale_keeps_exact_translation_and_redraw_sequence(
    scene,
):
    model = scene.Drawing()
    scene.native.app.ActiveDoc = model
    view = model.ActiveView
    view._scale = 2.0
    target = probe.viewports.capture(model)
    view._scale = 1.0
    view._translation[0] += 0.02
    scene.faults["pan_drift"] = True
    observation = {}

    probe.viewports.restore(scene.native.app, model, target, observation)

    assert observation["status"] == "passed"
    assert observation["after_scale"]["scale2"] == target["scale2"]
    assert observation["after_scale"]["translation3"] != target["translation3"]
    assert observation["after"] == target
    assert [call[0] for call in scene.calls] == [
        "scale",
        "create_vector",
        "translation",
        "redraw",
    ]
    assert len(scene.vectors) == 1
    assert scene.calls[0] == ("scale", 2.0)
    assert scene.calls[2][1] is scene.vectors[0]
    assert scene.calls[3] == ("redraw", 2.0)


def test_shared_viewport_module_has_no_diagnostic_dependency():
    from _buildgraph import module_deps_of

    assert not any(
        "diagnostics" in Path(path).parts
        for path in module_deps_of(Path(probe.viewports.__file__))
    )


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
