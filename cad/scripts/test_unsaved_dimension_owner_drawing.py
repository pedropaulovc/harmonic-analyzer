"""Retained Draw90 owner failure, corrected only with native owner evidence."""

from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from diagnostics import probe_drawing_attachments as probe
from test_probe_drawing_attachments import (
    Annotation,
    Model,
    View,
    dimension,
    display_dimension,
)


@pytest.fixture
def context(monkeypatch, tmp_path):
    monkeypatch.setattr(probe, "_early_bound", lambda value, _: value)
    source = tmp_path / "part.SLDPRT"
    source.write_bytes(b"test-only part")
    param = dimension("RD1", "RD1@Drawing View1@Draw90.Drawing", 0.127, 1)
    annotation = Annotation(entities=(), kinds=())
    annotation.display = display_dimension(param, reference="drawing")
    annotation.display.GetAnnotation = lambda: annotation
    view = View("Drawing View1", source, (annotation,))
    annotation.OwnerType, annotation.Owner = 0, view
    model = Model([view])
    model.GetPathName = lambda: ""
    model.GetTitle = lambda: "Draw90 - Sheet1"
    model.GetType = lambda: 3
    model.GetCurrentSheet = lambda: NS(GetName=lambda: "Sheet1")
    app = NS(ActiveDoc=model, IsSame=lambda a, b: int(a is b))
    return NS(
        source=source,
        param=param,
        annotation=annotation,
        view=view,
        model=model,
        app=app,
    )


@pytest.mark.parametrize(
    "title", ["Draw90", "Draw90 - Sheet1", "Draw90.SLDDRW", "Draw90.SLDDRW - Sheet1"]
)
def test_unsaved_reference_uses_native_title_and_exact_current_owner(context, title):
    c = context
    c.model.GetTitle = lambda: title
    result = probe.snapshot(c.model, app=c.app)
    key = "Sheet1/Drawing View1/dimension/4"
    component = result["dimensions"][key]["components"][0]
    assert component["qualified_name"] == "RD1@Drawing View1@<drawing>"
    assert component["value_system"] == 0.127
    assert component["tolerance_type"] == 1
    observed = result["dimension_observations"][key][0]
    assert observed["full_name"] == "RD1@Drawing View1@Draw90.Drawing"
    assert observed["unsaved_owner"] == {
        "title": title,
        "sheet": "Sheet1",
        "owner": "Draw90",
        "view": "Drawing View1",
    }


@pytest.mark.parametrize(
    "fault",
    [
        "wrong_title",
        "wrong_sheet_suffix",
        "wrong_sheet",
        "empty_title",
        "null_title",
        "source_suffix",
        "wrong_view_name",
        "wrong_native_owner",
        "missing_native_owner",
        "sheet_owner",
        "wrong_display",
        "missing_display",
        "wrong_active",
        "missing_active",
        "unknown_identity",
        "wrong_kind",
    ],
)
def test_unsaved_owner_never_uses_arbitrary_suffix_fallback(context, fault):
    c = context
    if fault == "wrong_title":
        c.model.GetTitle = lambda: "Other - Sheet1"
    if fault == "wrong_sheet_suffix":
        c.model.GetTitle = lambda: "Draw90 - Other"
    if fault == "wrong_sheet":
        c.model.GetCurrentSheet = lambda: NS(GetName=lambda: "Other")
    if fault == "empty_title":
        c.model.GetTitle = lambda: ""
    if fault == "null_title":
        c.model.GetTitle = lambda: None
    if fault == "source_suffix":
        c.param.FullName = "RD1@Drawing View1@part.Part"
    if fault == "wrong_view_name":
        c.param.FullName = "RD1@Other View@Draw90.Drawing"
    if fault == "wrong_native_owner":
        c.annotation.Owner = View("Drawing View1", c.source)
    if fault == "missing_native_owner":
        c.annotation.Owner = None
    if fault == "sheet_owner":
        c.annotation.OwnerType = 1
    if fault == "wrong_display":
        c.annotation.display.GetAnnotation = lambda: Annotation()
    if fault == "missing_display":
        c.annotation.display.GetAnnotation = lambda: None
    if fault == "wrong_active":
        c.app.ActiveDoc = Model([c.view])
    if fault == "missing_active":
        c.app.ActiveDoc = None
    if fault == "unknown_identity":
        c.app.IsSame = lambda *_: -1
    if fault == "wrong_kind":
        c.model.GetType = lambda: 1
    with pytest.raises(RuntimeError):
        probe.snapshot(c.model, app=c.app)


def test_missing_current_sheet_and_owner_evidence_reject(context):
    c = context
    c.model.GetCurrentSheet = lambda: None
    with pytest.raises(RuntimeError, match="sheet"):
        probe.snapshot(c.model, app=c.app)
    with pytest.raises(RuntimeError, match="native owner evidence"):
        probe.dimension_semantics(
            c.annotation, c.model, {"configuration": "Default", "path": str(c.source)}
        )


def test_saved_drawing_still_uses_path_not_title_or_new_owner_branch(context):
    c = context
    c.model.GetPathName = lambda: "saved.SLDDRW"
    c.param.FullName = "RD1@Drawing View1@saved.Drawing"
    c.model.GetTitle = Mock(side_effect=AssertionError("saved path must not use title"))
    c.app.ActiveDoc = None
    before = probe.snapshot(c.model, app=c.app)
    c.param.FullName = "RD1@Drawing View1@Draw90.Drawing"
    with pytest.raises(RuntimeError, match=r"does not match.*owner"):
        probe.snapshot(c.model, app=c.app)
    assert before["dimensions"]
    c.model.GetTitle.assert_not_called()


def test_source_dimension_in_unsaved_drawing_keeps_exact_part_owner(context):
    c = context
    c.param.Name, c.param.FullName = "Length", "Length@Sketch@part.Part"
    c.annotation.display.IsReferenceDim = lambda: False
    c.model.GetTitle = Mock(
        side_effect=AssertionError("source owner must not use drawing title")
    )
    result = probe.snapshot(c.model, app=c.app)
    key = "Sheet1/Drawing View1/dimension/4"
    assert (
        result["dimensions"][key]["components"][0]["qualified_name"] == c.param.FullName
    )
    c.param.FullName = "Length@Sketch@Draw90.Drawing"
    with pytest.raises(RuntimeError, match=r"does not match.*owner"):
        probe.snapshot(c.model, app=c.app)
    c.model.GetTitle.assert_not_called()


def test_unsaved_to_saved_normalization_preserves_exact_content_and_view(context):
    c = context
    before = probe.snapshot(c.model, app=c.app)
    c.model.GetPathName = lambda: "copy.SLDDRW"
    c.param.FullName = "RD1@Drawing View1@copy.Drawing"
    after = probe.snapshot(c.model, app=c.app)
    probe.compare(before, after, "save")
    assert before["dimension_observations"] != after["dimension_observations"]
    c.param.FullName = "RD1@Wrong View@copy.Drawing"
    with pytest.raises(RuntimeError, match="attachment snapshot changed"):
        probe.compare(after, probe.snapshot(c.model, app=c.app), "wrong saved view")
