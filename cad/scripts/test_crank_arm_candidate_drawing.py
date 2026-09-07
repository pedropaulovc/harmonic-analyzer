"""Offline composed callback tests; native geometry/layout remain separate gates.

The real loader, recipe build, role observers, attachment checks and reopen flow
run here. Only native boundaries and separately tested measurement readers are
faked. No SolidWorks connection or production output is used.
"""

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import sys

import pytest

import _drawing_common as drawing
import _drawing_entities as entities
import draw_crank_arm as recipe
from diagnostics import benchmark_drawing_recipes as benchmark
from diagnostics import probe_crank_arm_entities as probe
from diagnostics import probe_drawing_attachments as attachments
from diagnostics import _owned_native_documents as owned
from diagnostics import _recipe_template_factory as factories
from diagnostics import _reopen_annotation_comparison as comparisons
from diagnostics import probe_datum_shoulder as shoulder
from diagnostics import probe_retained_drawing_export as exports


class Document:
    def __init__(self, path, kind):
        self.path = Path(path)
        self.kind = kind
        self.alive = True
        self.handles = {}
        self.views = {}
        self.selected = []
        self.save_action = None
        self.ConfigurationManager = SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(Name="Default")
        )
        self.SelectionManager = SimpleNamespace(
            GetSelectedObject6=lambda index, mark: self.selected[index - 1][0],
            GetSelectedObjectCount2=lambda mark: len(self.selected),
            GetSelectedObjectsDrawingView2=lambda index, mark: self.selected[index - 1][
                1
            ],
        )

    def GetType(self):
        return self.kind

    def GetPathName(self):
        return str(self.path)

    def GetConfigurationNames(self):
        return ("Default",)

    def ClearSelection2(self, all_marks):
        self.selected.clear()

    def GetCurrentSheet(self):
        return SimpleNamespace(GetProperties2=lambda: (0, 0, 2, 1))

    def EditRebuild3(self):
        assert self.alive
        return True

    def Save3(self, options, errors, warnings):
        assert self.alive and self.save_action is not None
        return self.save_action(options, errors, warnings)


class View:
    def __init__(self, draw, source, name):
        self.draw = draw
        self.ReferencedDocument = source
        self.ReferencedConfiguration = "Default"
        self.name = name
        self.annotations = []

    def GetName2(self):
        return self.name

    def GetAnnotations(self):
        return self.annotations

    def SelectEntity(self, entity, append):
        assert entity.model.alive, "closed-lifetime entity selected"
        if not append:
            self.draw.selected.clear()
        self.draw.selected.append((entity, self))
        return True


class Annotation:
    def __init__(self, view, label, handles):
        self.Owner = view
        self.OwnerType = 0
        self.label = label
        self.handles = tuple(handles)
        self.position = (0.123, 0.456, 0.0042)

    def GetName(self):
        return self.label

    def GetAnnotation(self):
        return self

    def GetPosition(self):
        return self.position

    def SetPosition2(self, x, y, z):
        assert z == self.position[2]
        self.position = (x, y, z)
        return True

    def GetAttachedEntities3(self):
        return self.handles

    def GetAttachedEntityTypes(self):
        return (1,) * len(self.handles)

    def GetAttachedEntityCount3(self):
        return len(self.handles)

    def IsDangling(self):
        return False


@pytest.fixture
def candidate(tmp_path, monkeypatch):
    original = tmp_path / "original.SLDPRT"
    original.write_bytes(b"closed native source fixture")
    token = tmp_path / ".original.execution"
    digest = probe.sha(original)
    token.write_text(digest, encoding="utf-8")
    directory = tmp_path / "trial"
    directory.mkdir()
    state = SimpleNamespace(
        directory=directory,
        original=original,
        token=token,
        digest=digest,
        events=[],
        documents={},
        resolutions=[],
        insertions=[],
        saved=[],
        exports=[],
        scene_sources=[],
        layout="initial",
        fault=None,
        guard_errors=[],
        fail_evidence=False,
        module=None,
        build_function=None,
    )
    adapter = SimpleNamespace(currentModel=None)
    state.adapter = adapter

    def is_same(a, b):
        for value in (a, b):
            owner = getattr(value, "model", value)
            assert getattr(owner, "alive", True), "closed lifetime compared"
        return int(a is b and a is not None)

    adapter.swApp = SimpleNamespace(
        ActiveDoc=None,
        IsSame=is_same,
        GetOpenDocumentByName=lambda path: state.documents.get(Path(path)),
    )

    def assert_owned():
        assert adapter.currentModel is not None and adapter.currentModel.alive
        assert adapter.currentModel.path.parent == directory

    @contextmanager
    def creating(kind, path):
        assert kind == owned.DocumentKind.DRAWING
        assert Path(path).parent == directory
        state.events.append("create-enter")
        try:
            yield
        finally:
            state.events.append("create-exit")

    adapter.ownership = SimpleNamespace(
        register_directory=lambda path: state.events.append(("directory", path)),
        register_source=lambda path: state.events.append(("source", path)),
        assert_current_owned=assert_owned,
        creating_document=creating,
    )

    async def open_model(path):
        path = Path(path)
        assert path.parent == directory and path != original
        state.events.append(("open", path))
        if path not in state.documents:
            model = Document(path, 1 if path.suffix == ".SLDPRT" else 3)
            state.documents[path] = model
            if model.kind == 3:
                model.save_action = save_in_place
                source = state.documents[state.module.SOURCE]
                for name, labels in state.saved:
                    view = View(model, source, name)
                    model.views[name] = view
                    for label in labels:
                        view.annotations.append(
                            Annotation(
                                view,
                                label,
                                [
                                    source.handles[role]
                                    for role in probe.CALLOUT_ROLES[label]
                                ],
                            )
                        )
        model = state.documents[path]
        adapter.currentModel = adapter.swApp.ActiveDoc = model
        if state.fault == "source":
            model.path = original
        return SimpleNamespace(is_success=True, data=model)

    async def close_owned():
        state.events.append("close")
        for model in state.documents.values():
            model.alive = False
        state.documents.clear()
        adapter.currentModel = adapter.swApp.ActiveDoc = None

    adapter.open_model = open_model
    adapter.close_owned_documents = close_owned

    class Resolver:
        def __init__(self, model):
            assert model.alive
            self.model = model

        def resolve(self, requests):
            state.resolutions.append(self.model)
            if state.fault == "resolve" or (
                state.fault == "cold-resolve" and len(state.resolutions) == 3
            ):
                raise RuntimeError("role resolution failed")
            for name in requests:
                self.model.handles.setdefault(
                    name, SimpleNamespace(model=self.model, role=name)
                )
            return {name: self.model.handles[name] for name in requests}

    def native_insert(actual_adapter, view, **kwargs):
        assert actual_adapter is adapter
        assert_owned()
        handles = kwargs.get("entities") or (kwargs.get("entity") or kwargs["edge"],)
        annotation = Annotation(view, kwargs["label"], handles)
        view.annotations.append(annotation)
        state.insertions.append(kwargs["label"])
        return annotation

    def save(actual_adapter, path):
        assert actual_adapter is adapter
        assert_owned()
        assert Path(path) == state.module.OUTPUTS.slddrw
        state.events.append("save")
        if state.fault == "save":
            raise RuntimeError("primary save failure")
        state.saved = [
            (v.name, [a.label for a in v.annotations])
            for v in adapter.currentModel.views.values()
        ]
        Path(path).write_bytes(b"built native drawing fixture")

    def save_in_place(options, errors, warnings):
        assert (options, errors, warnings) == (1, 0, 0)
        assert_owned()
        state.events.append("save3")
        if state.fault == "moved-save":
            raise RuntimeError("primary save failure")
        state.saved = [
            (v.name, [a.label for a in v.annotations])
            for v in adapter.currentModel.views.values()
        ]
        adapter.currentModel.path.write_bytes(b"moved native drawing fixture")
        return True, 0, 0

    def export(actual_adapter, path):
        assert actual_adapter is adapter
        assert_owned()
        assert Path(path).parent == directory
        state.exports.append(Path(path).name)
        if (
            state.fault == "export"
            or state.fail_evidence
            or (state.fault == "cold-export" and Path(path).name == "cold.pdf")
        ):
            raise RuntimeError("export failure")

    async def finalize(actual_adapter, outputs, **kwargs):
        assert outputs is state.module.OUTPUTS
        drawing.save_drawing(actual_adapter, str(outputs.slddrw))
        export(actual_adapter, outputs.pdf)
        return {"slddrw": str(outputs.slddrw)}

    def place(actual_adapter, path, name, *xy, **kwargs):
        assert actual_adapter is adapter and Path(path) == state.module.SOURCE
        view = View(adapter.currentModel, state.documents[Path(path)], name)
        if state.fault == "view":
            view.ReferencedDocument = Document(original, 1)
        if state.fault == "configuration":
            view.ReferencedConfiguration = "Other"
        adapter.currentModel.views[name] = view
        return view

    class Controller:
        def __init__(self, variant):
            assert variant == factories.DrawingFactory.PREPARED
            self.used = False
            self.guards = {"helpers": "unchanged", "owned_cleanup": "passed"}

        async def configure(self, actual_adapter, module, report, output_directory):
            assert actual_adapter is adapter and output_directory == directory
            assert module.SOURCE == directory / "trial-part.SLDPRT"
            assert all(
                Path(path).parent == directory
                for path in (module.SLDDRW, module.PDF, module.PNG)
            )
            state.module = module
            state.build_function = module.build
            state.events.append("configure")
            monkeypatch.setattr(module, "_early_bound", lambda obj, kind: obj)
            for name in (
                "add_entity_dimension",
                "add_datum_feature",
                "add_feature_control_frame",
                "add_native_hole_callout",
                "add_surface_finish",
            ):
                monkeypatch.setattr(module, name, native_insert)
            for name in (
                "read_required_properties",
                "stamp_drawing_summary",
                "set_hidden_lines_removed",
                "set_hidden_lines_visible",
                "verify_dimension_callouts",
                "set_dimension_precision",
                "set_arc_endpoints_to_center",
                "set_basic_dimension",
                "add_property_linked_note",
            ):
                monkeypatch.setattr(module, name, lambda *args, **kwargs: None)
            monkeypatch.setattr(
                module, "curate_view_dimensions", lambda *args, **kwargs: []
            )
            monkeypatch.setattr(
                module, "auto_center_marks", lambda *args, **kwargs: True
            )
            monkeypatch.setattr(module, "place_view", place)
            monkeypatch.setattr(module, "finalize_drawing", finalize)

            def factory(actual_adapter, **kwargs):
                assert actual_adapter is adapter and "create-enter" in state.events
                self.used = True
                state.events.append("factory")
                model = Document(module.OUTPUTS.slddrw, 3)
                model.save_action = save_in_place
                state.documents[model.path] = model
                adapter.currentModel = adapter.swApp.ActiveDoc = model
                return model, model.GetCurrentSheet()

            return factory

        def require_used(self):
            assert self.used
            state.events.append("require_used")

        def final_guards(self):
            state.events.append("final_guards")
            return state.guard_errors

    def snapshot(actual_adapter, path):
        assert actual_adapter.currentModel.path == path
        assert actual_adapter.currentModel.alive
        state.scene_sources.append(actual_adapter.currentModel)
        return {
            "dirty_before": False,
            "dirty_after": False,
            "required_dimensions": {},
            "observed_dimensions": {},
        }

    monkeypatch.setattr(probe, "SOURCE", original)
    monkeypatch.setattr(probe, "TOKEN", token)
    monkeypatch.setattr(probe, "EXPECTED_SOURCE_SHA", digest)
    monkeypatch.setattr(probe, "provenance", lambda: {"source_sha256": digest})
    monkeypatch.setattr(probe, "revision", lambda root: "offline-current-recipe")
    monkeypatch.setattr(probe, "_early_bound", lambda obj, kind: obj)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, kind: obj)
    monkeypatch.setattr(probe, "source_snapshot", snapshot)
    monkeypatch.setattr(probe, "require_source_unchanged", lambda before, after: None)
    monkeypatch.setattr(probe, "drawing_dimensions", lambda model: {})
    # Exact dimension tolerances are tested separately; this suite covers callback orchestration.
    monkeypatch.setattr(probe, "require_manufacturing", Mock())
    monkeypatch.setattr(
        benchmark,
        "recipe_source",
        lambda commit, target: Path(recipe.__file__).read_text(encoding="utf-8"),
    )
    monkeypatch.setattr(entities, "ModelEntities", Resolver)
    monkeypatch.setattr(factories, "RecipeTemplateFactory", Controller)
    monkeypatch.setattr(owned, "save_drawing", save)
    monkeypatch.setattr(exports, "export_pdf_only", export)
    monkeypatch.setattr(drawing, "render_pdf_png", lambda *args: None)
    monkeypatch.setattr(probe, "render_details", lambda *args: {})
    monkeypatch.setattr(
        drawing, "_drawing_entity_in_source", lambda view, entity, **kwargs: entity
    )
    monkeypatch.setattr(
        attachments, "geometry", lambda entity, kind: (entity.role, kind)
    )
    monkeypatch.setattr(attachments, "views", lambda model: model.views)
    monkeypatch.setattr(
        attachments, "snapshot", lambda model, **kwargs: {"dimensions_excluded": []}
    )
    monkeypatch.setattr(attachments, "layout", lambda model: state.layout)
    monkeypatch.setattr(attachments, "compare", lambda before, after, phase: None)
    monkeypatch.setattr(attachments, "check_layout", lambda before, after, phase: None)
    monkeypatch.setattr(
        attachments, "move_and_scale", lambda model: {"requested": "initial"}
    )
    monkeypatch.setattr(
        shoulder, "all_annotation_layout", lambda actual_adapter: ({}, None)
    )
    monkeypatch.setattr(
        comparisons,
        "compare_reopened_annotations",
        lambda before, after: {"status": "passed"},
    )
    yield state
    if state.module is not None:
        sys.modules.pop(state.module.__name__, None)


def report(state):
    import json

    return json.loads(
        (state.directory / "measurements.json").read_text(encoding="utf-8")
    )


@pytest.mark.asyncio
async def test_candidate_executes_loaded_recipe_and_both_fresh_reopens(candidate):
    state = candidate
    result = await probe.candidate_control(state.adapter, state.directory)
    row = report(state)
    assert result == {"report": str(state.directory / "measurements.json")}
    assert state.module.build is state.build_function
    assert (
        Path(state.build_function.__code__.co_filename)
        == state.directory / "recipe-source.py"
    )
    assert set(state.insertions) == set(probe.CALLOUT_ROLES)
    assert len(state.insertions) == 14
    assert state.events.count("close") == 2
    # Initial diagnostic and recipe resolutions share one live document; each
    # cold-open resolution must instead own a distinct new native lifetime.
    first, recipe_model, cold, moved_cold = state.resolutions
    assert first is recipe_model and first is not cold and cold is not moved_cold
    assert not first.alive and not cold.alive and moved_cold.alive
    assert first.handles["shaft"] is not cold.handles["shaft"]
    assert cold.handles["shaft"] is not moved_cold.handles["shaft"]
    assert state.events.index("configure") < state.events.index("factory")
    assert state.events.index("create-exit") < state.events.index("require_used")
    assert state.events[-1] == "final_guards"
    assert row["status"] == "passed"
    assert set(row["phases"]) == {"built", "reopened", "moved_scaled", "moved_reopened"}
    assert all(len(phase["explicit_roles"]) == 14 for phase in row["phases"].values())
    assert all(obs["status"] == "passed" for obs in row["observations"])
    assert (
        row["source_original"]
        == row["source_copy"]
        == row["execution_token"]
        == state.digest
    )
    assert row["template_guards"] == "passed"
    assert row["template_guard_details"] == {
        "helpers": "unchanged",
        "owned_cleanup": "passed",
    }
    assert row["moved_save"] == [True, 0, 0]
    assert state.events.count("save") == state.events.count("save3") == 1
    assert (
        state.directory / "built.SLDDRW"
    ).read_bytes() == b"built native drawing fixture"
    assert state.module.OUTPUTS.slddrw.read_bytes() == b"moved native drawing fixture"
    assert state.original.read_bytes() == b"closed native source fixture"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fault, message",
    [
        ("source", "exact source part"),
        ("view", "wrong drawing/view/source context"),
        ("configuration", "wrong drawing/view/source context"),
        ("resolve", "role resolution failed"),
    ],
)
async def test_candidate_rejects_wrong_context_before_insertion(
    candidate, fault, message
):
    candidate.fault = fault
    with pytest.raises(RuntimeError, match=message):
        await probe.candidate_control(candidate.adapter, candidate.directory)
    row = report(candidate)
    assert row["status"] == "failed"
    assert not candidate.insertions
    assert row["observations"] == []
    assert "require_used" not in candidate.events
    assert candidate.events[-1] == "final_guards"
    assert row["source_original"] == row["source_copy"] == candidate.digest


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fault, message", [("save", "primary save failure"), ("export", "export failure")]
)
async def test_candidate_preserves_primary_failure_and_final_hash_evidence(
    candidate, fault, message
):
    candidate.fault = fault
    candidate.fail_evidence = True
    with pytest.raises(RuntimeError, match=message):
        await probe.candidate_control(candidate.adapter, candidate.directory)
    row = report(candidate)
    assert row["status"] == "failed" and message in row["error"]
    assert "export failure" in row["partial_evidence_error"]
    assert "partial_annotations" in row and "partial_attachments" in row
    assert "create-exit" in candidate.events
    assert candidate.events[-1] == "final_guards"
    assert row["template_guards"] == "passed"
    assert (
        row["source_original"]
        == row["source_copy"]
        == row["execution_token"]
        == candidate.digest
    )
    assert "failure.pdf" in candidate.exports


@pytest.mark.parametrize(
    "kind, actual_path", [(1, "owned.SLDDRW"), (3, "other.SLDDRW")]
)
def test_moved_save_rejects_wrong_type_or_path_before_native_call(
    tmp_path, monkeypatch, kind, actual_path
):
    model = Document(tmp_path / actual_path, kind)
    native_save = Mock(return_value=(True, 0, 0))
    model.save_action = native_save
    ownership_check = Mock()
    adapter = SimpleNamespace(
        currentModel=model,
        ownership=SimpleNamespace(assert_current_owned=ownership_check),
    )
    monkeypatch.setattr(probe, "_early_bound", lambda obj, interface: obj)
    with pytest.raises(RuntimeError, match="exact owned drawing"):
        probe.save_moved_drawing(adapter, tmp_path / "owned.SLDDRW")
    ownership_check.assert_called_once_with()
    native_save.assert_not_called()


@pytest.mark.parametrize(
    "result, message",
    [
        (False, "Save3 failed"),
        ((False, 0, 0), "Save3 failed"),
        ((True, 1, 0), "Save3 returned errors"),
    ],
)
def test_moved_save_rejects_native_failure_returns(
    tmp_path, monkeypatch, result, message
):
    model = Document(tmp_path / "owned.SLDDRW", 3)
    native_save = Mock(return_value=result)
    model.save_action = native_save
    adapter = SimpleNamespace(
        currentModel=model, ownership=SimpleNamespace(assert_current_owned=Mock())
    )
    monkeypatch.setattr(probe, "_early_bound", lambda obj, interface: obj)
    with pytest.raises(RuntimeError, match=message):
        probe.save_moved_drawing(adapter, model.path)
    native_save.assert_called_once_with(1, 0, 0)


@pytest.mark.parametrize("result", [True, (True, 0, 0), (True, 0, 4)])
def test_moved_save_retains_success_return_and_warning_evidence(
    tmp_path, monkeypatch, result
):
    model = Document(tmp_path / "owned.SLDDRW", 3)
    native_save = Mock(return_value=result)
    model.save_action = native_save
    adapter = SimpleNamespace(
        currentModel=model, ownership=SimpleNamespace(assert_current_owned=Mock())
    )
    monkeypatch.setattr(probe, "_early_bound", lambda obj, interface: obj)
    assert probe.save_moved_drawing(adapter, model.path) == result
    native_save.assert_called_once_with(1, 0, 0)


@pytest.mark.asyncio
async def test_candidate_keeps_primary_and_cleanup_guard_errors(candidate):
    candidate.fault = "save"
    cleanup_error = RuntimeError("template cleanup guard failed")
    candidate.guard_errors = [cleanup_error]
    with pytest.raises(ExceptionGroup) as caught:
        await probe.candidate_control(candidate.adapter, candidate.directory)
    assert str(caught.value.exceptions[0]) == "primary save failure"
    assert caught.value.exceptions[1].exceptions == (cleanup_error,)
    row = report(candidate)
    assert "primary save failure" in row["error"]
    assert "template cleanup guard failed" in row["template_guards"]["error"]
    assert (
        row["source_original"]
        == row["source_copy"]
        == row["execution_token"]
        == candidate.digest
    )


@pytest.mark.asyncio
async def test_candidate_hash_read_failure_does_not_claim_unchanged_or_mask_primary(
    candidate, monkeypatch
):
    candidate.fault = "save"
    original_sha = probe.sha

    def locked_hash(path):
        if Path(path) == candidate.original and "save" in candidate.events:
            raise PermissionError("source hash locked")
        return original_sha(path)

    monkeypatch.setattr(probe, "sha", locked_hash)
    with pytest.raises(ExceptionGroup) as caught:
        await probe.candidate_control(candidate.adapter, candidate.directory)
    assert str(caught.value.exceptions[0]) == "primary save failure"
    assert isinstance(caught.value.exceptions[1], PermissionError)
    row = report(candidate)
    assert "primary save failure" in row["error"]
    assert row["source_original"] == {"error": "PermissionError('source hash locked')"}
    assert row["source_copy"] == row["execution_token"] == candidate.digest
    assert row["template_guards"] == "passed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fault, message, phases",
    [
        ("cold-resolve", "role resolution failed", {"built"}),
        ("cold-export", "export failure", {"built", "reopened"}),
        ("moved-save", "primary save failure", {"built", "reopened", "moved_scaled"}),
    ],
)
async def test_candidate_retains_completed_phases_after_cold_stage_failure(
    candidate, fault, message, phases
):
    candidate.fault = fault
    with pytest.raises(RuntimeError, match=message):
        await probe.candidate_control(candidate.adapter, candidate.directory)
    row = report(candidate)
    assert row["status"] == "failed" and message in row["error"]
    assert set(row["phases"]) == phases
    assert len(candidate.insertions) == 14
    assert candidate.events.count("close") == 1
    assert "require_used" in candidate.events
    assert (
        row["source_original"]
        == row["source_copy"]
        == row["execution_token"]
        == candidate.digest
    )
    assert row["template_guards"] == "passed"
