"""Dimension-attached datums have an explicit native semantic witness."""

from types import SimpleNamespace
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
    monkeypatch.setattr(probe, "_early_bound", lambda value, _kind: value)
    source = tmp_path / "part.SLDPRT"
    source.write_bytes(b"native part")
    parameter = dimension("BoreCutDia", "BoreCutDia@BoreCut@part.Part", 0.009525, 1)
    display = display_dimension(parameter, kind=6)
    target = Annotation("BoreCutDia", entities=(), kinds=())
    target.display = display
    datum = Annotation("DatumA", kind=2, entities=(display,), kinds=(14,))
    tag = SimpleNamespace(
        GetLabel=lambda: "A", Shoulder=True, GetDisplayStyle=lambda: 0
    )
    datum.display = tag
    view = View("Front", source, (target, datum))
    source_model = SimpleNamespace(
        GetPathName=lambda: str(source), Parameter=Mock(return_value=parameter)
    )
    # A real drawing view exposes a stable referenced native part interface.
    view.__class__ = type(
        "NativeView", (View,), {"ReferencedDocument": property(lambda _: source_model)}
    )
    for annotation in (target, datum):
        annotation.OwnerType, annotation.Owner, annotation.Visible = 0, view, 1
        annotation.GetAttachedEntityCount3 = lambda annotation=annotation: len(
            annotation.entities
        )
    display.GetAnnotation = lambda: target
    app = SimpleNamespace(IsSame=lambda a, b: int(a is b))
    return SimpleNamespace(
        model=Model([view]),
        app=app,
        view=view,
        target=target,
        datum=datum,
        display=display,
        parameter=parameter,
        source=source,
        source_model=source_model,
        tag=tag,
    )


def test_type14_is_checked_as_semantics_not_fake_model_geometry(context):
    c = context
    actual = probe.snapshot(c.model, app=c.app)
    key = "Sheet1/Front/DatumA/2"
    assert key not in actual["checked"] and key not in actual["excluded"]
    witness = actual["semantic_attachments"][key]
    assert witness["kind"] == "datum_to_model_display_dimension"
    assert witness["target_annotation"] == "BoreCutDia"
    assert witness["owner_view"] == "Sheet1/Front"
    assert witness["source"] == {"path": str(c.source), "configuration": "Default"}
    assert witness["datum"] == {"label": "A", "shoulder": True, "display_style": 0}
    component = witness["dimension"]["components"][0]
    assert component["qualified_name"] == "BoreCutDia@BoreCut@part.Part"
    assert component["value_system"] == 0.009525
    assert component["tolerance_type"] == 1
    c.source_model.Parameter.assert_called_once_with("BoreCutDia@BoreCut")


@pytest.mark.parametrize(
    "change",
    [
        "datum_owner",
        "target_owner",
        "target_kind",
        "target_hidden",
        "target_dangling",
        "target_missing",
        "target_ambiguous",
        "roundtrip",
        "null",
        "multiple",
        "count",
        "source_parameter",
    ],
)
def test_type14_cannot_hide_wrong_owner_inventory_or_native_source_identity(
    context, change
):
    c = context
    if change == "datum_owner":
        c.datum.Owner = object()
    if change == "target_owner":
        c.target.Owner = object()
    if change == "target_kind":
        c.target.kind = 5
    if change == "target_hidden":
        c.target.Visible = 3
    if change == "target_dangling":
        c.target.state = "dangling"
    if change == "target_missing":
        c.view.annotations = (c.datum,)
    if change == "target_ambiguous":
        c.view.annotations = (c.target, c.target, c.datum)
    if change == "roundtrip":
        c.target.display = display_dimension(c.parameter, kind=6)
    if change == "null":
        c.datum.entities = (None,)
    if change == "multiple":
        c.datum.entities, c.datum.kinds = (c.display, c.display), (14, 14)
    if change == "count":
        c.datum.GetAttachedEntityCount3 = lambda: 2
    if change == "source_parameter":
        c.source_model.Parameter.return_value = dimension(
            "BoreCutDia", "BoreCutDia@BoreCut@part.Part", 0.009525, 1
        )
    with pytest.raises(RuntimeError):
        probe.snapshot(c.model, app=c.app)


@pytest.mark.parametrize(
    "change",
    [
        "dimension_name",
        "feature",
        "configuration",
        "value",
        "basic",
        "label",
        "shoulder",
    ],
)
def test_type14_comparison_preserves_original_dimension_and_datum_semantics(
    context, change
):
    c = context
    before = probe.snapshot(c.model, app=c.app)
    if change == "dimension_name":
        c.parameter.Name, c.parameter.FullName = (
            "OtherDia",
            "OtherDia@BoreCut@part.Part",
        )
    if change == "feature":
        c.parameter.FullName = "BoreCutDia@WrongFeature@part.Part"
    if change == "configuration":
        c.view.ReferencedConfiguration = "OtherConfiguration"
    if change == "value":
        c.parameter.GetSystemValue3.return_value = (0.010,)
    if change == "basic":
        c.parameter.Tolerance.Type = 0
    if change == "label":
        c.tag.GetLabel = lambda: "B"
    if change == "shoulder":
        c.tag.Shoulder = False
    with pytest.raises(RuntimeError, match="semantic_attachments.*DatumA"):
        probe.compare(
            before, probe.snapshot(c.model, app=c.app), "changed datum target"
        )


def test_type14_without_app_is_not_an_implicit_exclusion(context):
    with pytest.raises(TypeError, match="app"):
        probe.snapshot(context.model)
