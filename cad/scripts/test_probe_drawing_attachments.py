"""Offline controls for the drawing attachment stability diagnostic."""

from copy import deepcopy
from functools import partial
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import probe_drawing_attachments as probe

APP = SimpleNamespace(IsSame=lambda a, b: int(a is b))
geometry_snapshot = partial(probe.snapshot, app=APP)


def dimension(
    name="Length", full_name="Length@Sketch@part.Part", value=0.03, tolerance_type=0
):
    return SimpleNamespace(
        Name=name,
        FullName=full_name,
        GetType=lambda: 0,
        GetSystemValue3=Mock(return_value=(value,)),
        GetSystemValue2=Mock(return_value=value),
        Tolerance=SimpleNamespace(Type=tolerance_type),
    )


def display_dimension(*dimensions, kind=2, reference="model"):
    return SimpleNamespace(
        Type2=kind,
        IsReferenceDim=lambda: reference == "drawing",
        GetDimension2=Mock(side_effect=lambda index: dimensions[index]),
    )


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
        self.display = display_dimension(dimension())

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

    def GetSpecificAnnotation(self):
        return self.display


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
    result = geometry_snapshot(Model([View("Front", source_model, annotations)]))
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
        geometry_snapshot(Model([View("Front", source_model, (item,))]))


def test_null_supported_entity_still_fails_in_mixed_unsupported_array(source_model):
    item = Annotation(entities=(None, None), kinds=(0, 3))
    with pytest.raises(RuntimeError, match="supported attachment is null"):
        geometry_snapshot(Model([View("Front", source_model, (item,))]))


def test_attachment_array_length_mismatch_fails(source_model):
    item = Annotation(entities=(), kinds=(3,))
    with pytest.raises(RuntimeError, match="different lengths"):
        geometry_snapshot(Model([View("Front", source_model, (item,))]))


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
    result = geometry_snapshot(Model([View("Front", source_model, (item,))]))
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


@pytest.mark.parametrize(
    "section",
    [
        "checked",
        "excluded",
        "models",
        "dimensions",
        "dimensions_excluded",
        "semantic_attachments",
    ],
)
def test_comparison_detects_changed_inventory_and_model_reference(section):
    before = {
        "checked": {"A": ("vertex", (0, 0, 0))},
        "excluded": {},
        "models": {"view": "part"},
        "dimensions": {},
        "dimensions_excluded": {},
        "semantic_attachments": {},
    }
    after = deepcopy(before)
    after[section]["changed"] = "different"
    with pytest.raises(RuntimeError, match="attachment snapshot changed"):
        probe.compare(before, after, "reopen")


@pytest.mark.parametrize("attachment", ["none", "sketch_segment", "sketch_point"])
def test_imported_dimensions_have_semantics_without_supported_geometry(
    source_model, attachment
):
    kinds = {"none": (), "sketch_segment": (10,), "sketch_point": (11,)}[attachment]
    annotation = Annotation(entities=tuple(object() for _ in kinds), kinds=kinds)
    actual = dimension("BoreDia", "BoreDia@Bore@part.Part", 0.009525)
    annotation.display = display_dimension(actual, kind=6)
    view = View("Front", source_model, (annotation,))
    view.ReferencedConfiguration = "FineBore"
    result = geometry_snapshot(Model([view]))
    key = "Sheet1/Front/dimension/4"
    assert result["checked"] == {}
    assert key in result["excluded"]
    assert result["dimensions"][key] == {
        "kind": "model_dimension",
        "display_type": 6,
        "view_configuration": "FineBore",
        "components": [
            {
                "name": "BoreDia",
                "qualified_name": "BoreDia@Bore@part.Part",
                "parameter_type": 0,
                "value_system": 0.009525,
                "value_api": "GetSystemValue3",
                "tolerance_type": 0,
                "designation": "other",
            }
        ],
    }
    assert result["dimension_observations"][key] == [{"full_name": actual.FullName}]
    actual.GetSystemValue3.assert_called_once_with(3, "FineBore")
    actual.GetSystemValue2.assert_not_called()


def circular_edge(center_x=0.0):
    curve = SimpleNamespace(
        IsCircle=lambda: True,
        CircleParams=(center_x, 0, 0, 0, 0, 1, 0.005),
    )
    trim = SimpleNamespace(
        UMinValue=0,
        UMaxValue=6.28318530718,
        StartPoint=(center_x + 0.005, 0, 0),
        EndPoint=(center_x + 0.005, 0, 0),
    )
    return SimpleNamespace(GetCurve=lambda: curve, GetCurveParams3=lambda: trim)


@pytest.mark.parametrize("case", ["diameter", "c2c"])
def test_native_dimensions_keep_geometry_and_values_separate_across_drawing_copies(
    source_model, case
):
    edges = (
        (circular_edge(),)
        if case == "diameter"
        else (circular_edge(), circular_edge(0.02))
    )
    annotation = Annotation(entities=edges, kinds=tuple(1 for _ in edges))
    actual = dimension(
        "RD1", "RD1@Front@source.Drawing", 0.01 if case == "diameter" else 0.02
    )
    annotation.display = display_dimension(
        actual, kind=6 if case == "diameter" else 2, reference="drawing"
    )
    model = Model([View("Front", source_model, (annotation,))])
    model.GetPathName = lambda: "source.SLDDRW"
    before = geometry_snapshot(model)
    model.GetPathName = lambda: "copy.SLDDRW"
    actual.FullName = "RD1@Front@copy.Drawing"
    after = geometry_snapshot(model)
    probe.compare(before, after, "copy")
    key = "Sheet1/Front/dimension/4"
    assert len(after["checked"][key]) == len(edges)
    semantic = after["dimensions"][key]["components"][0]
    assert semantic["qualified_name"] == "RD1@Front@<drawing>"
    assert semantic["value_api"] == "GetSystemValue2"
    assert after["dimension_observations"][key][0]["full_name"] == actual.FullName
    assert before["dimension_observations"] != after["dimension_observations"]
    actual.GetSystemValue3.assert_not_called()
    assert actual.GetSystemValue2.call_args.args == ("",)
    actual.GetSystemValue2.return_value += 0.001
    with pytest.raises(RuntimeError, match="dimensions.*dimension/4"):
        probe.compare(before, geometry_snapshot(model), "value changed")


@pytest.mark.parametrize("mutation", ["name", "configuration", "value", "tolerance"])
def test_dimension_semantic_changes_fail_snapshot_comparison(source_model, mutation):
    annotation = Annotation(entities=(), kinds=())
    actual = annotation.display.GetDimension2(0)
    view = View("Front", source_model, (annotation,))
    model = Model([view])
    before = geometry_snapshot(model)
    if mutation == "name":
        actual.Name, actual.FullName = "Wrong", "Wrong@Sketch@part.Part"
    if mutation == "configuration":
        view.ReferencedConfiguration = "WrongConfiguration"
    if mutation == "value":
        actual.GetSystemValue3.return_value = (0.09,)
    if mutation == "tolerance":
        actual.Tolerance.Type = 1
    with pytest.raises(RuntimeError, match="dimensions.*dimension/4"):
        probe.compare(before, geometry_snapshot(model), "changed semantics")


@pytest.mark.parametrize("reference", ["model", "drawing"])
def test_basic_tolerance_loss_is_detected_even_when_value_geometry_are_unchanged(
    source_model, reference
):
    annotation = Annotation()
    full_name = (
        "RD1@Front@source.Drawing"
        if reference == "drawing"
        else "Length@Sketch@part.Part"
    )
    actual = dimension(
        "RD1" if reference == "drawing" else "Length", full_name, tolerance_type=1
    )
    annotation.display = display_dimension(actual, reference=reference)
    model = Model([View("Front", source_model, (annotation,))])
    model.GetPathName = lambda: "source.SLDDRW"
    before = geometry_snapshot(model)
    key = "Sheet1/Front/dimension/4"
    assert before["dimensions"][key]["components"][0]["designation"] == "basic"
    actual.Tolerance.Type = 0
    after = geometry_snapshot(model)
    assert before["checked"] == after["checked"]
    assert (
        before["dimensions"][key]["components"][0]["value_system"]
        == after["dimensions"][key]["components"][0]["value_system"]
    )
    with pytest.raises(RuntimeError, match="dimensions.*dimension/4"):
        probe.compare(before, after, "BASIC lost during save/reopen")


def test_missing_native_tolerance_cannot_silently_be_marked_nonbasic(source_model):
    annotation = Annotation()
    annotation.display.GetDimension2(0).Tolerance = None
    with pytest.raises(RuntimeError, match="no native tolerance"):
        geometry_snapshot(Model([View("Front", source_model, (annotation,))]))


@pytest.mark.parametrize("reference", ["model", "drawing"])
def test_dimension_owner_identity_is_not_globally_stripped(source_model, reference):
    annotation = Annotation()
    actual = dimension(
        "D1",
        "D1@Front@foreign.Drawing"
        if reference == "drawing"
        else "D1@Sketch@foreign.Part",
    )
    annotation.display = display_dimension(actual, reference=reference)
    model = Model([View("Front", source_model, (annotation,))])
    model.GetPathName = lambda: "source.SLDDRW"
    with pytest.raises(RuntimeError, match="does not match.*owner"):
        geometry_snapshot(model)


def test_chamfer_semantics_read_both_underlying_dimensions(source_model):
    distance = dimension("ChamferLength", "ChamferLength@Chamfer@part.Part", 0.001)
    angle = dimension("ChamferAngle", "ChamferAngle@Chamfer@part.Part", 0.785398163397)
    angle.GetType = lambda: 1
    angle.Tolerance.Type = 1
    annotation = Annotation()
    annotation.display = display_dimension(distance, angle, kind=10)
    result = geometry_snapshot(Model([View("Front", source_model, (annotation,))]))
    items = result["dimensions"]["Sheet1/Front/dimension/4"]["components"]
    assert [row["parameter_type"] for row in items] == [0, 1]
    assert [row["value_system"] for row in items] == [0.001, 0.785398163397]
    assert [row["tolerance_type"] for row in items] == [0, 1]
    assert [call.args for call in annotation.display.GetDimension2.call_args_list] == [
        (0,),
        (1,),
    ]


@pytest.mark.parametrize(
    "failure", ["missing_dimension", "empty_value", "many_values", "nonfinite"]
)
def test_unreadable_model_dimensions_fail_loud(source_model, failure):
    annotation = Annotation()
    actual = annotation.display.GetDimension2(0)
    if failure == "missing_dimension":
        annotation.display.GetDimension2.side_effect = lambda _: None
    if failure == "empty_value":
        actual.GetSystemValue3.return_value = None
    if failure == "many_values":
        actual.GetSystemValue3.return_value = (1, 2)
    if failure == "nonfinite":
        actual.GetSystemValue3.return_value = (float("nan"),)
    with pytest.raises(RuntimeError, match="dimension|system value"):
        geometry_snapshot(Model([View("Front", source_model, (annotation,))]))


def test_pmi_only_dimension_semantics_are_explicitly_excluded(source_model):
    annotation = Annotation(entities=(), kinds=())
    annotation.display = None
    result = geometry_snapshot(Model([View("Front", source_model, (annotation,))]))
    key = "Sheet1/Front/dimension/4"
    assert not result["dimensions"]
    assert (
        result["dimensions_excluded"][key]["reason"]
        == "annotation has no concrete display dimension"
    )
    assert key in result["excluded"]


def test_api_capture_records_failed_current_shapes_without_using_them(source_model):
    annotation = Annotation()
    actual = dimension("RD1", "RD1@Front@source.Drawing", 0.012)
    actual.GetSystemValue3.return_value = None
    annotation.display = display_dimension(actual, reference="drawing")
    model = Model([View("Front", source_model, (annotation,))])
    model.GetPathName = lambda: "source.SLDDRW"
    result = geometry_snapshot(model, dimension_values="api-capture")
    key = "Sheet1/Front/dimension/4"
    assert result["dimensions"][key]["components"][0]["value_system"] == 0.012
    calls = result["dimension_observations"][key][0]["value_api_calls"]
    assert calls["GetSystemValue3(1,empty)"] == {"status": "returned", "value": None}
    assert calls["GetSystemValue3(3,view_configuration)"]["value"] is None
    assert calls["GetSystemValue3(1,None)"]["value"] is None
    assert calls["GetSystemValue2(empty)"]["value"] == 0.012
    assert [call.args for call in actual.GetSystemValue3.call_args_list] == [
        (1, ""),
        (3, "Default"),
        (1, None),
    ]


def test_view_order_does_not_change_snapshot(source_model):
    model = Model(
        [View("Front", source_model, (Annotation(),)), View("Side", source_model)]
    )
    before = geometry_snapshot(model)
    model.drawing_views.reverse()
    probe.compare(before, geometry_snapshot(model), "reordered views")


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
        self.swApp = APP
        self.saved = {}
        self.opened, self.closed = [], []
        self.ownership = SimpleNamespace(
            register_directory=Mock(),
            register_source=Mock(),
            assert_current_owned=Mock(),
        )

    async def open_model(self, path):
        self.opened.append(path)
        view = View("Front", self.source_model, (Annotation(),))
        if self.mode == "no_supported":
            view.annotations = (Annotation(kind=6),)
        if self.mode == "dimension_only":
            view.annotations = (Annotation(entities=(), kinds=()),)
        if self.mode in {"native_dimension", "native_wrong_value"}:
            value = (
                0.09
                if path in self.saved and self.mode == "native_wrong_value"
                else 0.02
            )
            native = dimension("RD1", f"RD1@Front@{Path(path).stem}.Drawing", value)
            annotation = Annotation(
                entities=(circular_edge(), circular_edge(0.02)), kinds=(1, 1)
            )
            annotation.display = display_dimension(native, reference="drawing")
            view.annotations = (annotation,)
        if path in self.saved and self.mode != "lost_layout":
            view.Position, view._scale = self.saved[path]
        if path in self.saved and self.mode == "wrong_model_config":
            view.ReferencedConfiguration = "Other"
        if path in self.saved and self.mode == "wrong_dimension_value":
            view.annotations[0].display.GetDimension2(
                0
            ).GetSystemValue3.return_value = (0.09,)
        if self.mode == "lost_basic":
            view.annotations[0].display.GetDimension2(0).Tolerance.Type = (
                0 if path in self.saved else 1
            )
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
@pytest.mark.parametrize(
    "mode",
    [
        "normal",
        "lost_layout",
        "wrong_model_config",
        "wrong_dimension_value",
        "lost_basic",
    ],
)
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
async def test_value_only_probe_reports_zero_geometry_coverage(tmp_path, source_model):
    drawing = tmp_path / "source.SLDDRW"
    drawing.write_bytes(b"original drawing")
    adapter = Adapter(source_model, "dimension_only")
    result = await probe.probe(adapter, drawing, tmp_path / "reports")
    report = json.loads(Path(result["probe"]).read_text())
    assert report["status"] == "passed"
    assert report["coverage"] == {
        "geometry_annotations_checked": 0,
        "geometry_annotations_excluded": 1,
        "dimension_annotations_checked": 1,
        "dimension_annotations_excluded": 0,
        "semantic_attachments_checked": 0,
    }
    assert len(adapter.opened) == 3
    assert (
        report["snapshots"]["source"]["dimensions"]
        == report["snapshots"]["reopened"]["dimensions"]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["native_dimension", "native_wrong_value"])
async def test_native_two_entity_dimension_values_are_checked_after_reopen(
    tmp_path, source_model, mode
):
    drawing = tmp_path / "source.SLDDRW"
    drawing.write_bytes(b"original drawing")
    adapter = Adapter(source_model, mode)
    reports = tmp_path / "reports"
    if mode == "native_wrong_value":
        with pytest.raises(RuntimeError, match="saved and reopened.*dimensions"):
            await probe.probe(adapter, drawing, reports)
    if mode == "native_dimension":
        await probe.probe(adapter, drawing, reports)
    (report_path,) = reports.glob("*/attachments.json")
    report = json.loads(report_path.read_text())
    assert report["status"] == ("passed" if mode == "native_dimension" else "failed")
    assert report["coverage"]["geometry_annotations_checked"] == 1
    assert report["coverage"]["dimension_annotations_checked"] == 1
    assert len(adapter.opened) == len(adapter.closed) == 3


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


@pytest.mark.parametrize("dimension_values", ["system", "api-capture"])
def test_parent_uses_pipeline_lock_for_the_worker(
    tmp_path, monkeypatch, dimension_values
):
    drawing = tmp_path / "source.SLDDRW"
    drawing.write_bytes(b"source")
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "0")
    launch = Mock()
    monkeypatch.setitem(probe.sys.modules, "dodo", SimpleNamespace(_run=launch))
    assert probe.main([str(drawing), "--dimension-values", dimension_values]) == 0
    command = launch.call_args.args[0]
    assert command[-1] == "--worker"
    assert str(drawing) in command
    assert command[command.index("--dimension-values") + 1] == dimension_values
    assert launch.call_args.kwargs["com"] is True


def test_parent_refuses_autostart_before_pipeline_preflight(tmp_path, monkeypatch):
    drawing = tmp_path / "source.SLDDRW"
    drawing.write_bytes(b"source")
    launch = Mock()
    monkeypatch.setitem(probe.sys.modules, "dodo", SimpleNamespace(_run=launch))
    monkeypatch.delenv("HARMONIC_SW_AUTOSTART", raising=False)
    with pytest.raises(RuntimeError, match="HARMONIC_SW_AUTOSTART=0"):
        probe.main([str(drawing)])
    launch.assert_not_called()
