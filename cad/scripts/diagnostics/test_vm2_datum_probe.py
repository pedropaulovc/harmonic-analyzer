"""Offline execution of diagnostic guards; fakes never attach to SolidWorks."""

import asyncio
from contextlib import nullcontext
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


class Document:
    def __init__(self, path, title, kind):
        self.path, self.title, self.kind = str(path), title, kind
        self.closed = False
        self.views = []
        self.save_result = 0
        self.write_export = True

    def check_live(self):
        if self.closed:
            raise AssertionError("stale document proxy dereferenced")

    def GetPathName(self):
        self.check_live()
        return self.path

    def GetTitle(self):
        self.check_live()
        return self.title

    def GetType(self):
        self.check_live()
        return self.kind

    def GetSaveFlag(self):
        return False

    def GetFirstView(self):
        return self.views[0]

    def ClearSelection2(self, _all):
        pass

    def EditRebuild3(self):
        return True

    def SaveAs3(self, path, _version, _options):
        if self.write_export:
            Path(path).write_bytes(b"fake diagnostic export")
        if Path(path).suffix == ".SLDDRW":
            self.path = path
        return self.save_result


class View:
    Position = (0.055, 0.205)
    ScaleRatio = (2, 1)

    def __init__(self, name, reference=None):
        self.name, self.ReferencedDocument = name, reference
        self.next_view = None
        self.annotations, self.tags = [], []

    def GetName2(self):
        return self.name

    def GetReferencedModelName(self):
        return self.ReferencedDocument.path if self.ReferencedDocument else ""

    def GetNextView(self):
        return self.next_view

    def GetAnnotations(self):
        return self.annotations

    def GetDatumTags(self):
        return self.tags


class Application:
    ActiveDoc = None

    def __init__(self):
        self.documents, self.closed_titles = [], []
        self.closure_mode = "individual"
        self.on_close = lambda: None

    def GetDocuments(self):
        return list(self.documents)

    def GetProcessID(self):
        return 123

    def RevisionNumber(self):
        return "34.3.0"

    def IsSame(self, left, right):
        return int(left is right)

    def CloseDoc(self, title):
        self.closed_titles.append(title)
        targets = list(self.documents)
        if self.closure_mode == "individual":
            targets = [doc for doc in targets if doc.title == title]
        for doc in targets:
            doc.closed = True
            self.documents.remove(doc)
        self.on_close()


@pytest.fixture
def harness(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    source = root / "cad/out/sldprt/pinion-lift-rod.SLDPRT"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"fake unchanged source")
    reports = root / "cad/out/reports/datum-placement"
    reports.mkdir(parents=True)
    monkeypatch.setattr(sys, "prefix", str(root / ".venv"))
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "0")
    monkeypatch.setenv("HARMONIC_DIAGNOSTIC_SW_PID", "123")
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "off")
    app = Application()
    part = Document(source, "pinion-lift-rod.SLDPRT", 1)
    drawing = Document("", "Diagnostic - Sheet1", 3)
    drawing.views = [View("Sheet1"), *(View(name, part) for name in ("Front", "Top", "Right"))]
    for current, following in zip(drawing.views, drawing.views[1:]):
        current.next_view = following
    adapter = SimpleNamespace(swApp=app, currentModel=drawing)
    curve = SimpleNamespace(IsCircle=lambda: True, CircleParams=(0, 0, 0, 0, 0, 1, 0.003175))
    edge = SimpleNamespace(GetCurve=lambda: curve)
    annotation = SimpleNamespace(
        GetPosition=lambda: (0.055, 0.229, 0),
        GetAttachedEntities3=lambda: (edge,), GetAttachedEntityTypes=lambda: (1,),
        GetLeaderCount=lambda: 0,
    )
    tag = SimpleNamespace(
        GetLabel=lambda: "A", GetAnnotation=lambda: annotation,
        Shoulder=False, ForcedShoulder=False,
    )
    drawing.views[1].tags = [tag]
    common = SimpleNamespace(
        __file__=__file__,
        dimension_name=lambda _adapter, item: item.name,
        render_pdf_png=lambda _pdf, png, **_kwargs: png.write_bytes(b"fake rendered PNG"),
    )
    recipe = SimpleNamespace(SOURCE=source, ROD_DIA=6.35, __file__=__file__)
    recipe.add_datum_feature = lambda *_args, **_kwargs: None

    async def build(_adapter):
        app.documents = [part, drawing]
        recipe.add_datum_feature(
            adapter, drawing.views[1], edge_xy=(0.055, 0.21135),
            symbol_xy=(0.055, 0.229), label="A", position_tolerance_m=0.000020,
        )

    recipe.build = build
    modules = {
        "_common": SimpleNamespace(_early_bound=lambda value, _kind: value),
        "_drawing_common": common,
        "_gear_drawing_entities": SimpleNamespace(visible_circle_edge=lambda *_args: edge),
        "_telemetry": SimpleNamespace(span=lambda *_args, **_kwargs: nullcontext()),
        "diagnostics._owned_native_session": SimpleNamespace(
            run_owned_diagnostic=lambda callback: asyncio.run(callback(adapter))
        ),
        "solidworks_mcp.adapters.com_variant": SimpleNamespace(null_callout=lambda: None),
        "draw_pinion_lift_rod": recipe,
    }
    for name, value in modules.items():
        monkeypatch.setitem(sys.modules, name, value)

    def load(stem):
        spec = importlib.util.spec_from_file_location(stem, Path(__file__).with_name(f"{stem}.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        monkeypatch.setattr(module, "ROOT", root)
        monkeypatch.setattr(module.subprocess, "check_output", lambda *_args, **_kwargs: "fake-head\n")
        return module

    def invoke(module, *arguments):
        monkeypatch.setattr(sys, "argv", [module.__file__, *(str(arg) for arg in arguments), "--worker"])
        return module.main()

    return SimpleNamespace(**locals())


def ownership_witnesses(h):
    module = h.load("probe_vm2_datum_ownership")
    h.app.documents = [h.part, h.drawing]
    inventory = h.reports / "inventory.json"
    h.invoke(module, inventory)
    witness = h.reports / "failed-probe.json"
    report = {
        "kind": "vm2-datum-one-variable-probe", "status": "failed",
        "pid": 123, "revision": "34.3.0", "source": str(h.source),
        "source_sha256_before": module.digest(h.source),
        "prepared_drawing": {"title": h.drawing.title, "path": "", "source": str(h.source)},
    }
    witness.write_text(json.dumps(report), encoding="utf-8")
    return module, inventory, witness, report


def test_conflicting_closure_modes_reject_before_runner(harness):
    h = harness
    module = h.load("probe_vm2_datum_ownership")
    h.monkeypatch.setattr(h.modules["diagnostics._owned_native_session"], "run_owned_diagnostic",
                          lambda _callback: pytest.fail("runner called before CLI rejection"))
    with pytest.raises(SystemExit) as error:
        h.invoke(module, h.reports / "result.json", "--close-owned-probe-from", "probe.json",
                 "--close-owned-failure-from", "old.json")
    assert error.value.code == 2
    assert h.app.closed_titles == []


@pytest.mark.parametrize("mutation, message", [
    ("missing_identity", "does not identify this unsaved drawing"),
    ("different_title", "does not identify this unsaved drawing"),
    ("pid", "seat identity changed"),
    ("source_hash", "source changed after failed probe"),
])
def test_failed_probe_witness_rejects_before_closure(harness, mutation, message):
    h = harness
    module, inventory, witness, report = ownership_witnesses(h)
    if mutation == "missing_identity":
        report.pop("prepared_drawing")
    if mutation == "different_title":
        report["prepared_drawing"]["title"] = "Another user's drawing"
    if mutation == "pid":
        report["pid"] = 999
    if mutation == "source_hash":
        report["source_sha256_before"] = "0" * 64
    witness.write_text(json.dumps(report), encoding="utf-8")
    output = h.reports / "closure.json"
    with pytest.raises(RuntimeError, match=message):
        h.invoke(module, output, "--close-owned-probe-from", witness, "--inventory-witness", inventory)
    assert h.app.closed_titles == []
    assert json.loads(output.read_text())["status"] == "failed"


def test_owned_probe_closure_skips_implicitly_closed_part(harness):
    h = harness
    module, inventory, witness, _report = ownership_witnesses(h)
    h.app.closure_mode = "implicit_all"
    output = h.reports / "closure.json"
    h.invoke(module, output, "--close-owned-probe-from", witness, "--inventory-witness", inventory)
    report = json.loads(output.read_text())
    assert report["status"] == "owned_probe_closed_without_save_bytes_unchanged"
    assert h.app.closed_titles == [h.drawing.title]
    assert len(report["closed_without_save"]) == 1
    assert h.part.closed


@pytest.mark.parametrize("mutation", ["none", "drawing_hash", "source_hash", "dirty", "foreign_path"])
def test_saved_export_failure_closure_retains_failure_and_checks_exact_evidence(harness, mutation):
    h = harness
    module = h.load("probe_vm2_datum_ownership")
    trial = h.reports / "failed-export"
    trial.mkdir()
    drawing_path = trial / "partial.SLDDRW"
    drawing_path.write_bytes(b"saved failed diagnostic")
    h.drawing.path = str(drawing_path)
    h.app.documents = [h.part, h.drawing]
    inventory = h.reports / "saved-inventory.json"
    if mutation == "dirty":
        h.part.GetSaveFlag = lambda: True
    h.invoke(module, inventory)
    witness = trial / "receipt.json"
    report = {
        "kind": "vm2-datum-one-variable-probe", "status": "failed",
        "pid": 123, "revision": "34.3.0", "source": str(h.source),
        "source_sha256_before": "0" * 64,
        "source_sha256_after": module.digest(h.source),
        "error": "RuntimeError('diagnostic export changed saved source bytes')",
        "exports": {"SLDDRW": {"path": str(drawing_path), "sha256": module.digest(drawing_path)}},
    }
    if mutation == "drawing_hash":
        report["exports"]["SLDDRW"]["sha256"] = "0" * 64
    if mutation == "source_hash":
        report["source_sha256_after"] = "0" * 64
    if mutation == "foreign_path":
        report["exports"]["SLDDRW"]["path"] = str(trial / "foreign.SLDDRW")
    witness.write_text(json.dumps(report), encoding="utf-8")
    output = h.reports / "saved-closure.json"
    arguments = (output, "--close-owned-probe-from", witness, "--inventory-witness", inventory)
    if mutation != "none":
        with pytest.raises(RuntimeError):
            h.invoke(module, *arguments)
        assert h.app.closed_titles == []
        return
    h.invoke(module, *arguments)
    result = json.loads(output.read_text())
    retained = result["retained_source_identity_failure"]
    assert retained["before_probe"] != retained["after_probe"]
    assert retained["acceptance"].startswith("failed;")
    assert result["status"] == "owned_probe_closed_without_save_bytes_unchanged"
    assert len(result["closed_without_save"]) == 2


def attachment_run(h, selection="edge"):
    module = h.load("probe_vm2_datum_attachment")
    output = h.reports / "attachment"
    h.invoke(module, "pinion_lift_rod", selection, "requested", output)
    return json.loads((output / "receipt.json").read_text())


def test_attachment_closure_skips_stale_part_and_hashes_final_evidence(harness):
    h = harness
    h.app.closure_mode = "implicit_all"
    report = attachment_run(h)
    assert report["status"] == "observed_and_closed"
    assert h.app.closed_titles == [h.drawing.title]
    assert report["source_sha256_after_close"] == report["source_sha256_before"]
    assert report["exports"]["png"]["sha256"]
    assert len(report["closed_without_save"]) == 1


@pytest.mark.parametrize("result, file_mode", [(False, "write"), (1, "write"), (0, "missing")])
def test_attachment_export_rejections(harness, result, file_mode):
    h = harness
    h.drawing.save_result = result
    h.drawing.write_export = file_mode == "write"
    with pytest.raises(RuntimeError, match="SaveAs3 rejected"):
        attachment_run(h)
    assert h.app.closed_titles == []


@pytest.mark.parametrize("position", [(float("nan"), 0, 0), (0, 0)])
def test_invalid_position_rejected(harness, position):
    h = harness
    h.annotation.GetPosition = lambda: position
    with pytest.raises(RuntimeError, match="invalid datum position"):
        attachment_run(h)
    assert h.app.closed_titles == []


def test_position_rejection_is_observation_not_acceptance(harness):
    h = harness

    def rejected(*_args, **_kwargs):
        raise RuntimeError("position did not persist: actual diagnostic rejection")

    h.recipe.add_datum_feature = rejected
    h.annotation.GetPosition = lambda: (0.055, 0.230, 0)
    report = attachment_run(h)
    assert report["production_helper"]["status"] == "rejected"
    assert report["within_original_xy_limit"] is False
    assert report["status"] == "observed_and_closed"
    assert h.recipe.add_datum_feature is rejected


def test_other_helper_error_propagates_and_restores_recipe(harness):
    h = harness

    def rejected(*_args, **_kwargs):
        raise RuntimeError("selection rejected")

    h.recipe.add_datum_feature = rejected
    with pytest.raises(RuntimeError, match="selection rejected"):
        attachment_run(h)
    assert h.recipe.add_datum_feature is rejected
    assert h.app.closed_titles == []


@pytest.mark.parametrize("count", [0, 2])
def test_dimension_resolution_requires_unique_dimension_and_skips_notes(harness, count):
    h = harness
    note = SimpleNamespace(GetType=lambda: 6)
    dimensions = [SimpleNamespace(GetType=lambda: 4, name="RodDia") for _ in range(count)]
    h.drawing.views[1].annotations = [note, *dimensions]
    # The note has no .name: passing it to dimension_name fails this test.
    with pytest.raises(RuntimeError, match="expected exactly one RodDia dimension"):
        attachment_run(h, "dimension")
    assert h.app.closed_titles == []


def test_post_close_source_drift_is_failure(harness):
    h = harness
    h.app.on_close = lambda: h.source.write_bytes(b"changed during fake closure")
    with pytest.raises(RuntimeError, match="probe closure changed source bytes"):
        attachment_run(h)
    report = json.loads((h.reports / "attachment/receipt.json").read_text())
    assert report["status"] == "failed"
    assert report["source_sha256_after_close"] != report["source_sha256_before"]
    assert len(report["closed_without_save"]) == 2


def test_partial_closure_failure_retains_completed_close_receipt(harness):
    h = harness
    close = h.app.CloseDoc

    def reject_part(title):
        if title == h.part.title:
            raise RuntimeError("part close failed")
        close(title)

    h.app.CloseDoc = reject_part
    with pytest.raises(RuntimeError, match="part close failed"):
        attachment_run(h)
    report = json.loads((h.reports / "attachment/receipt.json").read_text())
    assert report["status"] == "failed"
    assert [row["title"] for row in report["closed_without_save"]] == [h.drawing.title]
    assert h.part.closed is False


def test_new_foreign_document_stops_remaining_closure(harness):
    h = harness
    foreign = Document(h.root / "user-model.SLDPRT", "user-model.SLDPRT", 1)
    h.app.on_close = lambda: h.app.documents.append(foreign)
    with pytest.raises(RuntimeError, match="unexpected document appeared during closure"):
        attachment_run(h)
    assert h.app.closed_titles == [h.drawing.title]
    assert foreign.closed is False
    assert h.part.closed is False


def test_nonempty_initial_inventory_prevents_recipe_and_closure(harness):
    h = harness
    h.app.documents = [h.part]
    with pytest.raises(RuntimeError, match="requires an empty inventory"):
        attachment_run(h)
    assert h.app.closed_titles == []
    assert not (h.reports / "attachment").exists()
