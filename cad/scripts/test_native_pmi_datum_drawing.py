"""Typed PMI may keep a native datum position without accepting lost geometry."""

import ast
from pathlib import Path
from unittest.mock import Mock

import pytest

import _drawing_common as drawing
import draw_fulcrum_shaft
import draw_pivot_shaft
from _gtol_spec import PartDatum, CylinderFace, GeometricControl
from test_native_annotation_placement_drawing import native_context
from test_shaft_pmi_entities_drawing import cylinder


def projected_native_datum(monkeypatch):
    adapter, view, _entity, annotation = native_context(monkeypatch)
    entity = cylinder()
    view.GetName2 = lambda: "Front"
    adapter.currentModel.SelectionManager.GetSelectedObject6.return_value = entity
    annotation.GetAttachedEntities3.return_value = (entity,)
    annotation.GetAttachedEntityTypes.return_value = (2,)
    annotation.Owner, annotation.OwnerType = view, 0
    annotation.Visible = 1
    annotation.IsDangling.return_value = False
    datum = PartDatum("A", CylinderFace(6.35))
    annotation.GetName.return_value = datum.annotation_name
    placement = drawing.PmiDrawingPlacement(
        view=view, position=None, entity=entity, attachment_type="FACE"
    )

    def run():
        return drawing.project_part_pmi(
            adapter,
            placements={datum.key: placement},
            datums=(datum,),
            controls=(),
            label="native shaft",
        )

    return run, adapter, view, annotation


def test_typed_native_datum_never_sets_position_and_keeps_exact_entity_bank(
    monkeypatch,
):
    run, adapter, view, annotation = projected_native_datum(monkeypatch)
    guard = Mock(wraps=drawing._validate_explicit_annotation_attachment)
    monkeypatch.setattr(drawing, "_validate_explicit_annotation_attachment", guard)
    result = run()
    assert result == {"datum:A": annotation}
    annotation.SetPosition2.assert_not_called()
    adapter.currentModel.Extension.SelectByID2.assert_not_called()
    view.SelectEntity.assert_called_once()
    guard.assert_called_once()
    assert guard.call_args.kwargs["entity_type"] == "FACE"
    annotation.IsDangling.assert_called_once_with()


@pytest.mark.parametrize(
    "fault",
    [
        "outside",
        "half_hidden",
        "hidden",
        "unknown_visibility",
        "dangling",
        "nonfinite",
        "wrong_owner",
        "wrong_entity",
    ],
)
def test_complete_native_pmi_bank_rejects_bad_final_annotation(monkeypatch, fault):
    run, _adapter, _view, annotation = projected_native_datum(monkeypatch)
    if fault == "outside":
        annotation.GetPosition.return_value = (0.45, 0.18, 0)
    if fault in {"half_hidden", "hidden", "unknown_visibility"}:
        annotation.Visible = {"half_hidden": 2, "hidden": 3, "unknown_visibility": 0}[
            fault
        ]
    if fault == "dangling":
        annotation.IsDangling.return_value = True
    if fault == "nonfinite":
        annotation.GetPosition.return_value = (float("nan"), 0.18, 0)
    if fault == "wrong_owner":
        annotation.Owner = object()
    if fault == "wrong_entity":
        annotation.GetAttachedEntities3.return_value = (object(),)
    with pytest.raises(RuntimeError):
        run()
    annotation.SetPosition2.assert_not_called()


@pytest.mark.parametrize(
    "attachment", [{"attachment_xy": (0.1, 0.2)}, {"edge_entity": object()}]
)
def test_native_pmi_contract_requires_explicit_model_entity(attachment):
    with pytest.raises(ValueError, match="native.*entity"):
        drawing.PmiDrawingPlacement(view=object(), position=None, **attachment)


def test_native_pmi_contract_rejects_fixed_leader_endpoint():
    with pytest.raises(ValueError, match="native.*leader"):
        drawing.PmiDrawingPlacement(
            view=object(),
            position=None,
            entity=object(),
            leader_attachment_xy=(0.1, 0.2),
        )


def test_native_pmi_frame_keeps_xml_and_skips_only_explicit_position_assertion(
    monkeypatch,
):
    _run, adapter, view, annotation = projected_native_datum(monkeypatch)
    entity = adapter.currentModel.SelectionManager.GetSelectedObject6.return_value
    control = GeometricControl("form", "cylindricity", ".01", CylinderFace(6.35))
    annotation.GetName.return_value = control.annotation_name
    gtol = adapter.currentModel.InsertGtol.return_value
    gtol.GetFrame.return_value.GetSymbolXml.return_value = control.frame_xml
    result = drawing.project_part_pmi(
        adapter,
        placements={
            control.key: drawing.PmiDrawingPlacement(
                view=view, position=None, entity=entity, attachment_type="FACE"
            )
        },
        datums=(),
        controls=(control,),
        label="native frame",
    )
    assert result == {control.key: annotation}
    annotation.SetPosition2.assert_not_called()
    gtol.GetFrame.return_value.GetSymbolXml.assert_called()
    annotation.IsDangling.assert_called_once_with()


@pytest.mark.parametrize("recipe", [draw_fulcrum_shaft, draw_pivot_shaft])
def test_only_shaft_datum_seed_is_native_other_three_pmi_seeds_remain(recipe):
    tree = ast.parse(Path(recipe.__file__).read_text(encoding="utf-8"))
    project = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "project_part_pmi"
    )
    placements = next(kw.value for kw in project.keywords if kw.arg == "placements")
    assert len(placements.keys) == 4
    for key, call in zip(placements.keys, placements.values, strict=True):
        keywords = {kw.arg: kw.value for kw in call.keywords}
        assert "entity" in keywords
        if key.value == "datum:A":
            assert isinstance(keywords["position"], ast.Constant)
            assert keywords["position"].value is None
        else:
            assert not isinstance(keywords["position"], ast.Constant)
    assert (
        len(
            [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "add_surface_finish"
            ]
        )
        == 1
    )
