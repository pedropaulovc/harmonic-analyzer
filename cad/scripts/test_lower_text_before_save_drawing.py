"""One queued native field write after finalization, not a persistence promise."""

from contextlib import contextmanager
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from diagnostics import _drawing_lower_text_control as control
from test_lower_text_control_drawing import apply, scene as scene


@pytest.fixture
def queued(scene, tmp_path, monkeypatch):
    scene.module.OUTPUTS = NS(slddrw=tmp_path / "owned.SLDDRW")
    events = []

    def saver(adapter, path, *, artifact_context, pdf_path):
        assert adapter is scene.adapter
        assert path == str(scene.module.OUTPUTS.slddrw)
        for kind, target in (("drawing", path), ("pdf", pdf_path)):
            with artifact_context(kind, target):
                events.append((kind, scene.state.lower))
        return {"drawing": path, "pdf": pdf_path}

    original = Mock(side_effect=saver)
    monkeypatch.setattr(control.common, "save_drawing", original)
    instance = control.LowerTextControl(
        scene.adapter, scene.module, scene.trial, scene.handles,
        storage=control.CalloutStorage.LOWER_TEXT_BEFORE_SAVE,
    )
    return NS(**locals())


def save(queued, **kwargs):
    return control.common.save_drawing(
        queued.scene.adapter, str(queued.scene.module.OUTPUTS.slddrw),
        pdf_path="owned.pdf", **kwargs,
    )


def test_queued_request_does_no_write_and_applies_after_before_save_bank(queued):
    scene = queued.scene

    @contextmanager
    def observation(kind, path):
        queued.events.append(("before_" + kind, scene.state.lower))
        yield
        queued.events.append(("after_" + kind, scene.state.lower))

    with queued.instance.observe():
        apply(scene)
        scene.display.SetLowerText.assert_not_called()
        scene.model.EditRebuild3.assert_not_called()
        assert queued.instance.report["operation"]["status"] == "queued"
        result = save(queued, artifact_context=observation)
    queued.instance.require_used()
    assert result == {"drawing": str(scene.module.OUTPUTS.slddrw), "pdf": "owned.pdf"}
    assert queued.events == [
        ("before_drawing", ""), ("drawing", control.TEXT),
        ("after_drawing", control.TEXT), ("before_pdf", control.TEXT),
        ("pdf", control.TEXT), ("after_pdf", control.TEXT),
    ]
    scene.display.SetLowerText.assert_called_once_with(control.TEXT)
    scene.model.EditRebuild3.assert_called_once_with()
    scene.model.GetViews.assert_called_once_with()
    assert control.common.save_drawing is queued.original
    assert scene.module.set_dimension_callouts is scene.original


@pytest.mark.parametrize("mutation", ["value", "annotation", "entity", "active", "missing", "duplicate"])
def test_queued_original_witness_must_match_fresh_before_save_inventory(queued, mutation):
    scene = queued.scene
    with pytest.raises(RuntimeError):
        with queued.instance.observe():
            apply(scene)
            if mutation == "value":
                scene.dimension.GetSystemValue3.return_value = (0.008000000001786,)
            if mutation == "annotation":
                fresh = NS(**vars(scene.annotation))
                scene.view.GetAnnotations.return_value = (fresh,)
                scene.display.GetAnnotation = lambda: fresh
            if mutation == "entity":
                scene.annotation.GetAttachedEntities3 = lambda: (object(), scene.entities[1])
            if mutation == "active":
                scene.adapter.swApp.ActiveDoc = object()
            if mutation == "missing":
                scene.view.GetAnnotations.return_value = ()
            if mutation == "duplicate":
                scene.view.GetAnnotations.return_value = (scene.annotation,) * 2
            save(queued)
    scene.display.SetLowerText.assert_not_called()
    scene.model.EditRebuild3.assert_not_called()
    assert queued.events == []
    assert queued.instance.report["operation"]["status"] == "failed"
    assert control.common.save_drawing is queued.original


@pytest.mark.parametrize("failure", ["setter", "rebuild"])
def test_queued_setter_failure_is_retained_without_writer_or_retry(queued, failure):
    scene = queued.scene
    primary = RuntimeError("before-save native " + failure)
    if failure == "setter":
        scene.display.SetLowerText.side_effect = primary
    if failure == "rebuild":
        scene.model.EditRebuild3.side_effect = primary
    with pytest.raises(RuntimeError) as caught:
        with queued.instance.observe():
            apply(scene)
            save(queued)
    assert caught.value is primary
    assert queued.events == []
    assert queued.instance.report["operation"]["error"] == repr(primary)
    scene.display.SetLowerText.assert_called_once_with(control.TEXT)
    assert control.common.save_drawing is queued.original


def test_queued_but_unsaved_cannot_pass_and_second_native_write_is_rejected(queued):
    with queued.instance.observe():
        apply(queued.scene)
        with pytest.raises(RuntimeError, match="completed"):
            queued.instance.require_used()
        save(queued)
        with pytest.raises(RuntimeError, match="once"):
            save(queued)
    queued.scene.display.SetLowerText.assert_called_once()
    queued.scene.model.EditRebuild3.assert_called_once()


def test_queued_original_aliases_restore_when_recipe_fails_before_save(queued):
    with pytest.raises(RuntimeError, match="recipe failure"):
        with queued.instance.observe():
            apply(queued.scene)
            raise RuntimeError("recipe failure")
    queued.scene.display.SetLowerText.assert_not_called()
    assert control.common.save_drawing is queued.original
    assert queued.scene.module.set_dimension_callouts is queued.scene.original


def test_unqueued_save_cannot_write_and_expired_save_callback_cannot_read(queued):
    with queued.instance.observe():
        saved_callback = control.common.save_drawing
        with pytest.raises(RuntimeError, match="once"):
            save(queued)
    queued.original.reset_mock()
    with pytest.raises(RuntimeError, match="scope"):
        saved_callback(queued.scene.adapter, str(queued.scene.module.OUTPUTS.slddrw))
    queued.original.assert_not_called()
    queued.scene.model.GetViews.assert_not_called()
    queued.scene.display.SetLowerText.assert_not_called()


def test_other_native_output_is_rejected_before_setter_or_writer(queued):
    with queued.instance.observe():
        apply(queued.scene)
        with pytest.raises(RuntimeError, match="scope"):
            control.common.save_drawing(queued.scene.adapter, "different.SLDDRW")
    queued.original.assert_not_called()
    queued.scene.display.SetLowerText.assert_not_called()
