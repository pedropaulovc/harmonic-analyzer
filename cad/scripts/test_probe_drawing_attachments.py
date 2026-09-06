"""Offline controls for the drawing attachment stability diagnostic."""

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import probe_drawing_attachments as probe


class Annotation:
    def __init__(
        self, name="dimension", kind=4, entities=None, kinds=(3,), state="attached"
    ):
        self.name, self.kind, self.kinds, self.state = name, kind, kinds, state
        self.entities = (
            (SimpleNamespace(GetPoint=lambda: (0.01, 0.02, 0.03)),)
            if entities is None
            else entities
        )

    def GetName(self):
        return self.name

    def GetType(self):
        return self.kind

    def IsDangling(self):
        return self.state == "dangling"

    def GetAttachedEntities3(self):
        return self.entities

    def GetAttachedEntityTypes(self):
        return self.kinds


class View:
    def __init__(self, name, source, annotations=(), mode="normal"):
        self.name, self.source, self.annotations, self.mode = (
            name,
            source,
            annotations,
            mode,
        )
        self.ReferencedConfiguration = "Default"
        self.Position = (0.1, 0.2)
        self._scale = 1.0

    def GetName2(self):
        return self.name

    def GetUniqueName(self):
        return self.name

    @property
    def ReferencedDocument(self):
        return SimpleNamespace(GetPathName=lambda: str(self.source))

    def GetAnnotations(self):
        return self.annotations

    def RemoveAlignment(self):
        pass

    @property
    def ScaleDecimal(self):
        return self._scale

    @ScaleDecimal.setter
    def ScaleDecimal(self, value):
        if self.mode != "ignored_scale":
            self._scale = value

    def SetViewPosition(self, position, move_children):
        assert move_children is False
        if self.mode == "rejected_move":
            return False
        if self.mode != "ignored_move":
            self.Position = tuple(position)
        return True


class Model:
    def __init__(self, drawing_views):
        self.drawing_views = drawing_views

    def GetViews(self):
        sheet = SimpleNamespace(GetName2=lambda: "Sheet1")
        return ((sheet, *self.drawing_views),)

    def EditRebuild3(self):
        return True


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(probe, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(probe, "double_array", tuple)


@pytest.fixture
def source_model(tmp_path):
    path = tmp_path / "part.SLDPRT"
    path.write_bytes(b"source part")
    return path


def test_snapshot_separates_checked_geometry_and_exclusions(source_model):
    annotations = (
        Annotation(),
        Annotation("origin", entities=(None,), kinds=(0,)),
        Annotation("free", entities=(), kinds=()),
        Annotation("note", kind=6),
    )
    result = probe.snapshot(Model([View("Front", source_model, annotations)]))
    assert tuple(result["checked"]) == ("Sheet1/Front/dimension/4",)
    assert len(result["excluded"]) == 3
    assert (
        result["excluded"]["Sheet1/Front/origin/4"]["reason"]
        == "attachment kind not checked"
    )
    assert (
        result["excluded"]["Sheet1/Front/free/4"]["reason"]
        == "no model-geometry attachments"
    )
    assert (
        result["excluded"]["Sheet1/Front/note/6"]["reason"]
        == "annotation type not checked"
    )
    assert result["models"]["Sheet1/Front"] == {
        "path": str(source_model),
        "configuration": "Default",
    }


@pytest.mark.parametrize("kinds", [(0,), (3,), ()])
def test_dangling_annotation_cannot_be_excluded_as_unsupported(source_model, kinds):
    item = Annotation(
        entities=tuple(None for _ in kinds), kinds=kinds, state="dangling"
    )
    with pytest.raises(RuntimeError, match="annotation is dangling"):
        probe.snapshot(Model([View("Front", source_model, (item,))]))


def test_null_supported_entity_still_fails_in_mixed_unsupported_array(source_model):
    item = Annotation(entities=(None, None), kinds=(0, 3))
    with pytest.raises(RuntimeError, match="supported attachment is null"):
        probe.snapshot(Model([View("Front", source_model, (item,))]))


def test_attachment_array_length_mismatch_fails(source_model):
    item = Annotation(entities=(), kinds=(3,))
    with pytest.raises(RuntimeError, match="different lengths"):
        probe.snapshot(Model([View("Front", source_model, (item,))]))


@pytest.mark.parametrize("shape", ["spline_edge", "spline_face"])
def test_geometry_without_signature_is_excluded(source_model, monkeypatch, shape):
    curve = SimpleNamespace(IsCircle=lambda: False, IsLine=lambda: False)
    entity = SimpleNamespace(GetCurve=lambda: curve)
    kind = 1
    if shape == "spline_face":
        kind = 2
        monkeypatch.setattr(
            probe, "_face_geometry", lambda _: SimpleNamespace(identity=4010)
        )
    item = Annotation(entities=(entity,), kinds=(kind,))
    result = probe.snapshot(Model([View("Front", source_model, (item,))]))
    assert result["checked"] == {}
    assert len(result["excluded"]) == 1


def test_circle_signature_distinguishes_trimmed_arcs():
    curve = SimpleNamespace(
        IsCircle=lambda: True, CircleParams=(0, 0, 0, 0, 0, 1, 0.01)
    )
    trim = SimpleNamespace(
        UMinValue=0.0, UMaxValue=1.0, StartPoint=(1, 0, 0), EndPoint=(0, 1, 0)
    )
    edge = SimpleNamespace(GetCurve=lambda: curve, GetCurveParams3=lambda: trim)
    first = probe.geometry(edge, 1)
    trim.UMaxValue = 2.0
    assert probe.geometry(edge, 1) != first


def test_face_signature_distinguishes_opposite_outward_normals(monkeypatch):
    face = SimpleNamespace(
        identity=4001,
        parameters=(0, 0, 1, 0, 0, 0),
        box=(0, 0, 0, 1, 1, 0),
        outward_normal=(0, 0, 1),
    )
    monkeypatch.setattr(probe, "_face_geometry", lambda _: face)
    before = probe.geometry(object(), 2)
    face.outward_normal = (0, 0, -1)
    assert probe.geometry(object(), 2) != before


@pytest.mark.parametrize("section", ["checked", "excluded", "models"])
def test_comparison_detects_changed_inventory_and_model_reference(section):
    before = {
        "checked": {"A": ("vertex", (0, 0, 0))},
        "excluded": {},
        "models": {"view": "part"},
    }
    after = deepcopy(before)
    after[section]["changed"] = "different"
    with pytest.raises(RuntimeError, match="attachment snapshot changed"):
        probe.compare(before, after, "reopen")


def test_view_order_does_not_change_snapshot(source_model):
    model = Model(
        [View("Front", source_model, (Annotation(),)), View("Side", source_model)]
    )
    before = probe.snapshot(model)
    model.drawing_views.reverse()
    probe.compare(before, probe.snapshot(model), "reordered views")


@pytest.mark.parametrize("mode", ["ignored_move", "ignored_scale", "rejected_move"])
def test_every_view_must_move_and_scale(source_model, mode):
    model = Model([View("Front", source_model), View("Side", source_model, mode=mode)])
    with pytest.raises(RuntimeError, match="Side.*(layout mismatch|SetViewPosition)"):
        probe.move_and_scale(model)


def test_rebuild_readback_detects_reverted_layout(source_model):
    view = View("Front", source_model)
    model = Model([view])

    def rebuild():
        view.Position = (0.1, 0.2)
        return True

    model.EditRebuild3 = rebuild
    with pytest.raises(RuntimeError, match="layout mismatch"):
        probe.move_and_scale(model)


class Adapter:
    """Allocate a fresh drawing on each open and retain only saved layout."""

    def __init__(self, source_model, mode="normal"):
        self.source_model, self.mode = source_model, mode
        self.currentModel = None
        self.saved = {}
        self.opened, self.closed = [], []

    async def open_model(self, path):
        self.opened.append(path)
        view = View("Front", self.source_model, (Annotation(),))
        if self.mode == "no_supported":
            view.annotations = (Annotation(kind=6),)
        if path in self.saved and self.mode != "lost_layout":
            view.Position, view._scale = self.saved[path]
        if path in self.saved and self.mode == "wrong_model_config":
            view.ReferencedConfiguration = "Other"
        model = Model([view])
        model.GetPathName = lambda: path

        def save(*_):
            self.saved[path] = (view.Position, view.ScaleDecimal)
            Path(path).write_bytes(b"saved drawing copy")
            return (True, 0, 0)

        model.Save3 = save
        self.currentModel = model
        return SimpleNamespace(is_success=True, data=None)

    async def close_model(self):
        self.closed.append(self.currentModel.GetPathName())
        self.currentModel = None
        return SimpleNamespace(is_success=True, data=None)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["normal", "lost_layout", "wrong_model_config"])
async def test_source_copy_change_reopen_workflow(tmp_path, source_model, mode):
    drawing = tmp_path / "source.SLDDRW"
    drawing.write_bytes(b"original drawing")
    reports = tmp_path / "reports"
    adapter = Adapter(source_model, mode)
    if mode == "normal":
        result = await probe.probe(adapter, drawing, reports)
        result_path = Path(result["probe"])
    else:
        with pytest.raises(RuntimeError, match="saved and reopened"):
            await probe.probe(adapter, drawing, reports)
        (result_path,) = reports.glob("*/attachments.json")
    report = json.loads(result_path.read_text())
    assert report["status"] == ("passed" if mode == "normal" else "failed")
    assert report["source"] == str(drawing)
    assert set(report["snapshots"]) == {"source", "copy", "moved_scaled", "reopened"}
    assert Path(report["copy"]).name != drawing.name
    assert adapter.opened == [str(drawing), report["copy"], report["copy"]]
    assert adapter.closed == adapter.opened
    assert drawing.read_bytes() == b"original drawing"
    assert source_model.read_bytes() == b"source part"
    assert adapter.currentModel is None


@pytest.mark.asyncio
@pytest.mark.parametrize("reference_kind", ["direct", "section_base"])
async def test_probe_rejects_assembly_references_before_copy_or_movement(
    tmp_path, monkeypatch, reference_kind
):
    assembly = tmp_path / "assembly.SLDASM"
    assembly.write_bytes(b"source assembly")
    drawing = tmp_path / "source.SLDDRW"
    drawing.write_bytes(b"source drawing")
    adapter = Adapter(assembly)
    original_open = adapter.open_model

    async def open_model(path):
        result = await original_open(path)
        if reference_kind == "section_base":
            base = adapter.currentModel.drawing_views[0]
            adapter.currentModel.drawing_views = [
                SimpleNamespace(
                    GetUniqueName=lambda: "SectionA",
                    GetName2=lambda: "SectionA",
                    ReferencedConfiguration="Default",
                    ReferencedDocument=None,
                    GetBaseView=lambda: base,
                    GetAnnotations=base.GetAnnotations,
                    Position=base.Position,
                    ScaleDecimal=base.ScaleDecimal,
                )
            ]
        return result

    adapter.open_model = open_model
    copy = Mock(side_effect=AssertionError("assembly drawing must not be copied"))
    move = Mock(side_effect=AssertionError("assembly drawing must not be moved"))
    monkeypatch.setattr(probe.shutil, "copy2", copy)
    monkeypatch.setattr(probe, "move_and_scale", move)
    reports = tmp_path / "reports"
    with pytest.raises(ValueError, match="part drawings only.*assembly.SLDASM"):
        await probe.probe(adapter, drawing, reports)
    copy.assert_not_called()
    move.assert_not_called()
    assert adapter.closed == adapter.opened == [str(drawing)]
    (report_path,) = reports.glob("*/attachments.json")
    report = json.loads(report_path.read_text())
    assert report["status"] == "failed"
    assert not Path(report["copy"]).exists()
    assert drawing.read_bytes() == b"source drawing"
    assert assembly.read_bytes() == b"source assembly"


def test_section_base_part_reference_remains_supported(source_model):
    base = View("Front", source_model)
    section = SimpleNamespace(
        GetUniqueName=lambda: "SectionA",
        ReferencedConfiguration="SectionConfiguration",
        ReferencedDocument=None,
        GetBaseView=lambda: base,
    )
    assert probe.referenced_model(section) == {
        "path": str(source_model),
        "configuration": "SectionConfiguration",
    }


def test_cli_help_explains_part_only_scope(capsys):
    with pytest.raises(SystemExit) as result:
        probe.main(["--help"])
    assert result.value.code == 0
    help_text = capsys.readouterr().out
    assert "Only drawings referencing native parts" in help_text
    assert ".SLDPRT models" in help_text


def test_worker_requires_pipeline_seat_lock(tmp_path, monkeypatch):
    drawing = tmp_path / "source.SLDDRW"
    drawing.write_bytes(b"drawing")
    monkeypatch.delenv("HARMONIC_COM_SEAT", raising=False)
    with pytest.raises(RuntimeError, match="requires the pipeline COM seat lock"):
        probe.main([str(drawing), "--worker"])


@pytest.mark.asyncio
async def test_probe_cannot_pass_without_supported_attachments(tmp_path, source_model):
    drawing = tmp_path / "source.SLDDRW"
    drawing.write_bytes(b"source")
    adapter = Adapter(source_model, "no_supported")
    reports = tmp_path / "reports"
    with pytest.raises(RuntimeError, match="no supported model-geometry attachments"):
        await probe.probe(adapter, drawing, reports)
    (result_path,) = reports.glob("*/attachments.json")
    report = json.loads(result_path.read_text())
    assert report["status"] == "failed"
    assert report["snapshots"]["source"]["checked"] == {}
    assert len(report["snapshots"]["source"]["excluded"]) == 1
    assert adapter.currentModel is None


def test_parent_uses_pipeline_lock_for_the_worker(tmp_path, monkeypatch):
    drawing = tmp_path / "source.SLDDRW"
    drawing.write_bytes(b"source")
    launch = Mock()
    monkeypatch.setitem(probe.sys.modules, "dodo", SimpleNamespace(_run=launch))
    assert probe.main([str(drawing)]) == 0
    command = launch.call_args.args[0]
    assert command[-1] == "--worker"
    assert str(drawing) in command
    assert launch.call_args.kwargs["com"] is True
