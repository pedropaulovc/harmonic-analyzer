"""Offline controls for native GTol arrangement experiments and their witnesses."""

import ast
import json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest

from diagnostics import probe_gtol_autoarrange as probe
from diagnostics import _owned_native_documents as owned
from diagnostics import probe_drawing_attachments as attachments


def context(monkeypatch):
    monkeypatch.setattr(probe, "_early_bound", lambda item, name: item)
    model, drawing = Mock(), Mock()
    rows = [
        {"view": "native-view", "name": str(kind), "kind": kind, "annotation": Mock()}
        for kind in (4, 5, 5)
    ]
    rows[0][
        "annotation"
    ].GetSpecificAnnotation.return_value.GetNameForSelection.return_value = (
        "Width@source@view"
    )
    model.Extension.AlignDimensions.return_value = True
    return model, drawing, rows


@pytest.mark.parametrize(
    ("kinds", "count", "gtols", "dimensions"),
    [
        ((5,), 2, 2, 0),
        ((4, 5), 3, 2, 1),
        ((4,), 1, 0, 1),
    ],
)
def test_banks_are_selected_exactly_then_one_native_call(
    monkeypatch, kinds, count, gtols, dimensions
):
    model, drawing, rows = context(monkeypatch)
    model.SelectionManager.GetSelectedObjectCount2.return_value = count
    result = probe.select_bank(model, drawing, rows, kinds)
    assert result["selected"] == count
    assert result["gtols"] == gtols
    assert result["dimensions"] == dimensions
    assert result["return"] is True
    model.Extension.AlignDimensions.assert_called_once_with(0, 0.001)
    if dimensions:
        model.Extension.SelectByID2.assert_called_once_with(
            "Width@source@view",
            "DIMENSION",
            0,
            0,
            0,
            True,
            0,
            None,
            0,
        )
    else:
        model.Extension.SelectByID2.assert_not_called()
    for row in rows[1:]:
        assert row["annotation"].Select2.call_count == bool(gtols)


def test_incorrect_bank_count_prevents_native_arrangement(monkeypatch):
    model, drawing, rows = context(monkeypatch)
    model.SelectionManager.GetSelectedObjectCount2.return_value = 1
    with pytest.raises(RuntimeError, match="selection count"):
        probe.select_bank(model, drawing, rows, (4, 5))
    model.Extension.AlignDimensions.assert_not_called()


def test_rejected_selection_prevents_native_arrangement(monkeypatch):
    model, drawing, rows = context(monkeypatch)
    rows[1]["annotation"].Select2.return_value = False
    with pytest.raises(RuntimeError, match="selection failed"):
        probe.select_bank(model, drawing, rows, (5,))
    model.Extension.AlignDimensions.assert_not_called()


def test_native_rejection_is_an_observation_not_a_fallback(monkeypatch):
    model, drawing, rows = context(monkeypatch)
    model.SelectionManager.GetSelectedObjectCount2.return_value = 2
    model.Extension.AlignDimensions.return_value = False
    assert probe.select_bank(model, drawing, rows, (5,))["return"] is False
    model.Extension.AlignDimensions.assert_called_once()


def test_native_exception_is_recorded_with_its_exact_error():
    def reject():
        raise RuntimeError("COM call rejected")

    assert probe.observe(reject) == {"error": "RuntimeError('COM call rejected')"}


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["none", "activate", "selection", "align", "false"])
async def test_actual_probe_rejects_failed_alignment_after_retaining_all_trials(
    monkeypatch, tmp_path, fault
):
    source, part = tmp_path / "original.SLDDRW", tmp_path / "source.SLDPRT"
    source.write_bytes(b"drawing")
    part.write_bytes(b"part")
    selected = []
    extension = NS(AlignDimensions=Mock(return_value=fault != "false"))
    if fault == "align":
        extension.AlignDimensions.side_effect = RuntimeError("native alignment failed")

    def select(item):
        if fault == "selection":
            return False
        selected.append(item)
        return True

    annotations = {}
    for kind in (4, 5):
        entity = object()
        item = NS(position=(0.1, 0.1, 0.0))
        item.GetName = lambda kind=kind: f"annotation-{kind}"
        item.GetPosition = lambda item=item: item.position
        item.SetPosition2 = lambda *position, item=item: setattr(item, "position", position) or True
        item.GetAttachedEntities3 = lambda entity=entity: (entity,)
        item.GetAttachedEntityTypes = lambda: (2,)
        item.IsDangling = lambda: False
        item.Select2 = lambda *_args, item=item: select(item)
        item.GetSpecificAnnotation = lambda: NS(GetNameForSelection=lambda: "Width@source@view")
        annotations[kind] = item
    extension.SelectByID2 = lambda *_: select(annotations[4])
    view = NS(
        GetName2=lambda: "native-view",
        GetUniqueName=lambda: "native-view",
        ReferencedConfiguration="Default",
        GetAnnotationsByType=lambda kind: (annotations[kind],) if kind in annotations else (),
        ReferencedDocument=NS(GetPathName=lambda: str(part)),
    )
    model = NS(
        Extension=extension,
        SelectionManager=NS(GetSelectedObjectCount2=lambda _: len(selected)),
        ClearSelection2=lambda _: selected.clear(),
        ActivateView=lambda _: fault != "activate",
        GetViews=lambda: ((object(), view),),
    )
    adapter = NS(
        currentModel=model,
        swApp=NS(IsSame=lambda first, second: int(first is second)),
        ownership=NS(register_directory=Mock(), register_source=Mock()),
        close_owned_documents=AsyncMock(),
    )

    async def open_model(path):
        model.GetPathName = lambda: path
        return NS(is_success=True, data=None)

    adapter.open_model = open_model
    monkeypatch.setattr(probe, "_early_bound", lambda item, _: item)
    monkeypatch.setattr(attachments, "_early_bound", lambda item, _: item)
    monkeypatch.setattr(probe, "metrics", lambda item: {"position": item.position})
    save, render = Mock(), Mock()
    monkeypatch.setattr(owned, "save_drawing", save)
    monkeypatch.setattr(probe, "render_pdf_png", render)
    if fault == "none":
        result = await probe.probe(adapter, source, tmp_path)
        assert result == {"report": str(tmp_path / "autoarrange.json")}
    if fault != "none":
        with pytest.raises(RuntimeError, match="native AlignDimensions control failed"):
            await probe.probe(adapter, source, tmp_path)
    report = json.loads((tmp_path / "autoarrange.json").read_text(encoding="utf-8"))
    assert len(report["trials"]) == 3
    assert report["source_hashes"] == report["source_hashes_after"]
    assert report["failures"] == []
    for trial in report["trials"]:
        assert len(trial["annotations"]) == 2
        assert all(row["entity_identity"] == [1] for row in trial["annotations"])
        if fault in {"activate", "selection", "align"}:
            assert "error" in trial["align"]
        if fault == "false":
            assert trial["align"]["return"] is False
    assert save.call_count == render.call_count == 3
    assert adapter.close_owned_documents.await_count == 4
    assert extension.AlignDimensions.call_count == (0 if fault in {"activate", "selection"} else 3)


def valid_attachment():
    return {
        "view": "native-view",
        "name": "FCF",
        "kind": 5,
        "entity_count_before": 1,
        "entity_count_after": 1,
        "attachment_types_before": (2,),
        "attachment_types_after": (2,),
        "entity_identity": [1],
        "dangling": False,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("entity_count_after", 0),
        ("entity_count_after", 2),
        ("attachment_types_after", (1,)),
        ("entity_identity", [0]),
        ("entity_identity", [-1]),
        ("entity_identity", [None]),
        ("dangling", True),
    ],
)
def test_mutation_does_not_hide_attachment_regressions(field, value):
    record = valid_attachment()
    record[field] = value
    assert probe.attachment_failures([record])


def test_unchanged_native_attachment_passes():
    assert probe.attachment_failures([valid_attachment()]) == []


def test_diagnostic_does_not_recreate_gtols_or_select_geometry_by_coordinates(monkeypatch):
    original_read = Path.read_text
    reads = []

    def strict_read(path, *args, **kwargs):
        if path == Path(probe.__file__):
            assert kwargs.get("encoding") == "utf-8"
            reads.append(path)
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", strict_read)
    tree = ast.parse(Path(probe.__file__).read_text(encoding="utf-8"))
    assert reads == [Path(probe.__file__)]
    attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not attributes & {
        "InsertGtol",
        "SetAttachedEntities",
        "SelectByRay",
        "SelectEntity",
    }
    assert "AlignDimensions" in attributes
    assert "GetLineAtIndex3" in attributes
    assert "GetTextPositionAtIndex" in attributes
