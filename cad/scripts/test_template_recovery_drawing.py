"""No-save recovery guard tests; fake calls are not a native recovery claim."""

from copy import deepcopy
import asyncio
import json
from types import SimpleNamespace

import pytest

from diagnostics import recover_template_abba_scene as probe


class Document:
    def __init__(self, row):
        self.row = deepcopy(row)

    def GetPathName(self):
        return self.row["path"]

    def GetTitle(self):
        return self.row["title"]

    def GetType(self):
        return self.row["kind"]

    def GetSaveFlag(self):
        return self.row["dirty"] == "dirty"

    @property
    def Visible(self):
        return self.row["visible"] == "visible"


class App:
    def __init__(self):
        self.documents = [Document(row) for row in probe.BASELINE + probe.DISCARDED]
        self.closed = []
        self.after_close = lambda: None

    def GetDocuments(self):
        return self.documents

    def IsSame(self, first, second):
        assert first in self.documents and second in self.documents, "stale wrapper"
        return int(first is second)

    def CloseDoc(self, title):
        self.closed.append(title)
        self.documents = [doc for doc in self.documents if doc.GetTitle() != title]
        self.after_close()


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(probe, "_early_bound", lambda obj, interface: obj)
    return App()


def receipt():
    return {
        "baseline_initial": deepcopy(probe.BASELINE),
        "final_inventory": deepcopy(probe.BASELINE + probe.DISCARDED),
        "source_hashes": {
            str(probe.SOURCE): {
                "before": probe.SOURCE_SHA,
                "after": probe.SOURCE_SHA,
                "unchanged": True,
            }
        },
        "events": [
            {
                "operation": "open",
                "path": str(probe.SOURCE),
                "ownership": "opened_read_only_source",
            }
        ],
    }


def test_receipt_requires_exact_baseline_scene_and_source_provenance():
    probe.validate_receipt(receipt())
    for section in ("baseline_initial", "final_inventory"):
        changed = receipt()
        changed[section][0]["title"] = "another document"
        with pytest.raises(RuntimeError):
            probe.validate_receipt(changed)
    changed = receipt()
    changed["events"] = []
    with pytest.raises(RuntimeError, match="diagnostic opened"):
        probe.validate_receipt(changed)
    changed = receipt()
    changed["source_hashes"][str(probe.SOURCE)]["after"] = "other"
    with pytest.raises(RuntimeError, match="exact SHA"):
        probe.validate_receipt(changed)


def test_closes_only_diagnostic_drawing_then_source_without_save(app):
    handles = probe.verify_scene(app, probe.BASELINE + probe.DISCARDED)
    report, checkpoints = {}, []
    probe.discard_reviewed_documents(
        app, handles, report, lambda: checkpoints.append(deepcopy(report))
    )
    assert app.closed == [probe.DRAWING_TITLE, "arbor-pedestal.SLDPRT"]
    assert probe.inventory(app)[0] == probe.keyed(probe.BASELINE)
    assert len(checkpoints) == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("visible", "hidden"),
        ("dirty", "dirty"),
        ("path", "C:/wrong.SLDPRT"),
        ("kind", 3),
    ],
)
def test_any_changed_baseline_field_blocks_first_close(app, field, value):
    handles = probe.verify_scene(app, probe.BASELINE + probe.DISCARDED)
    app.documents[0].row[field] = value
    with pytest.raises(RuntimeError, match="scene changed"):
        probe.discard_reviewed_documents(app, handles, {}, lambda: None)
    assert app.closed == []


def test_same_name_replaced_handle_is_not_identity(app):
    handles = probe.verify_scene(app, probe.BASELINE + probe.DISCARDED)
    # Keep the old handle alive in this fake IsSame to model a valid foreign doc.
    app.IsSame = lambda first, second: int(first is second)
    app.documents[3] = Document(probe.DISCARDED[1])
    with pytest.raises(RuntimeError, match="replaced"):
        probe.discard_reviewed_documents(app, handles, {}, lambda: None)
    assert app.closed == []


def test_new_hidden_document_after_first_close_blocks_second(app):
    handles = probe.verify_scene(app, probe.BASELINE + probe.DISCARDED)
    app.after_close = lambda: app.documents.append(
        Document({**probe.BASELINE[0], "title": "foreign", "visible": "hidden"})
    )
    with pytest.raises(RuntimeError, match="scene changed"):
        probe.discard_reviewed_documents(app, handles, {}, lambda: None)
    assert app.closed == [probe.DRAWING_TITLE]


def test_native_source_unload_never_reuses_stale_wrapper(app):
    handles = probe.verify_scene(app, probe.BASELINE + probe.DISCARDED)

    def unload_source():
        app.documents = [
            doc for doc in app.documents if doc.GetPathName() != str(probe.SOURCE)
        ]

    app.after_close = unload_source
    report = {}
    probe.discard_reviewed_documents(app, handles, report, lambda: None)
    assert app.closed == [probe.DRAWING_TITLE]
    assert report["source_close"] == "already unloaded by native drawing close"


def test_failed_native_close_is_not_success(app):
    handles = probe.verify_scene(app, probe.BASELINE + probe.DISCARDED)
    app.CloseDoc = lambda title: None
    with pytest.raises(RuntimeError, match="scene changed"):
        probe.discard_reviewed_documents(app, handles, {}, lambda: None)


def test_reference_gate_rejects_foreign_and_baseline_dependencies(app, monkeypatch):
    handles = probe.verify_scene(app, probe.BASELINE + probe.DISCARDED)
    source = handles["arbor-pedestal.SLDPRT"]
    view = SimpleNamespace(ReferencedDocument=source, ReferencedConfiguration="Default")
    monkeypatch.setattr(
        probe.attachments,
        "views",
        lambda doc: {"front": view} if doc.GetTitle() == probe.DRAWING_TITLE else {},
    )
    probe.verify_references(app, handles)
    view.ReferencedDocument = handles[probe.BASELINE[0]["title"]]
    with pytest.raises(RuntimeError, match="other than the exact arbor"):
        probe.verify_references(app, handles)
    view.ReferencedDocument = source
    monkeypatch.setattr(probe.attachments, "views", lambda doc: {"front": view})
    with pytest.raises(RuntimeError, match="protected Draw2 references"):
        probe.verify_references(app, handles)


def test_source_properties_are_cached_reads_without_config_switch(app, monkeypatch):
    calls = []

    class Props:
        def GetNames(self):
            return ["Description"]

        def Get6(self, name, cached):
            calls.append((name, cached))
            return (0, "value", "resolved", False, False)

    config = SimpleNamespace(Name="Default")
    model = SimpleNamespace(
        ConfigurationManager=SimpleNamespace(ActiveConfiguration=config),
        GetConfigurationNames=lambda: ("Default", "Other"),
        Parameter=lambda key: key,
        Extension=SimpleNamespace(CustomPropertyManager=lambda scope: Props()),
    )
    monkeypatch.setattr(
        probe, "dimension_row", lambda raw, configuration: (raw, configuration)
    )
    result = probe.source_capture(model)
    assert len(result["dimensions"]) == 5
    assert calls == [("Description", True), ("Description", True)]
    assert result["active_configuration"] == "Default"


def test_capture_exception_is_retained_not_labeled_geometry_success():
    def rejected():
        raise RuntimeError("unsupported native observation")

    assert probe.observed(rejected) == {
        "status": "error",
        "error": "RuntimeError('unsupported native observation')",
    }


@pytest.mark.parametrize("failure", ["different_hash", "unreadable"])
def test_source_hash_failure_after_capture_blocks_every_close(
    app, monkeypatch, tmp_path, failure
):
    receipt_path = tmp_path / "ownership.json"
    receipt_path.write_text(json.dumps(receipt()), encoding="utf-8")
    app.GetProcessID = lambda: probe.EXPECTED_PID
    monkeypatch.setattr(probe, "verify_references", lambda app, handles: {})
    monkeypatch.setattr(probe, "source_capture", lambda model: {})
    monkeypatch.setattr(probe, "drawing_capture", lambda model: {})
    calls = []

    def source_digest(path):
        if path != probe.SOURCE:
            return "receipt_sha"
        calls.append(path)
        if len(calls) == 1:
            return probe.SOURCE_SHA
        if failure == "unreadable":
            raise PermissionError("sharing denied")
        return "changed"

    monkeypatch.setattr(probe, "digest", source_digest)
    with pytest.raises(RuntimeError, match="before discard"):
        asyncio.run(probe.recover(SimpleNamespace(swApp=app), receipt_path, tmp_path))
    assert app.closed == []
    reports = list(tmp_path.glob("scene-recovery-*/recovery.json"))
    assert len(reports) == 1
    retained = json.loads(reports[0].read_text(encoding="utf-8"))
    assert retained["status"] == "failed"
    assert "source_sha_before_discard" in retained


def test_parent_refuses_before_seat_when_autostart_or_pid_missing(monkeypatch):
    monkeypatch.delenv("HARMONIC_SW_AUTOSTART", raising=False)
    with pytest.raises(RuntimeError, match="AUTOSTART"):
        probe.main([])
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "0")
    monkeypatch.delenv("HARMONIC_DIAGNOSTIC_SW_PID", raising=False)
    with pytest.raises(RuntimeError, match="PID=37136"):
        probe.main([])
