"""The actual slotted-screw recipe must measure its complete sheet before export."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import draw_slotted_screw as drawing
from _drawing_view_packing import Axis, AxisOrder


@pytest.fixture
def recipe(monkeypatch, tmp_path):
    source = tmp_path / "slotted-screw.SLDPRT"
    source.write_bytes(b"mock source; no native CAD")
    monkeypatch.setattr(drawing, "SOURCE", source)
    events = []
    views = {key: object() for key in ("side", "end", "iso")}
    notes = {key: object() for key in ("Manufacturing Notes", "End View Note")}
    adapter = SimpleNamespace(
        currentModel=object(),
        open_model=AsyncMock(return_value=SimpleNamespace(is_success=True, data=None)),
    )
    monkeypatch.setattr(drawing, "read_required_properties", Mock())
    monkeypatch.setattr(drawing, "stamp_drawing_summary", Mock())
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", Mock())
    factory = Mock(return_value=(adapter.currentModel, object()))
    native_views = {"*Front": "side", "*Top": "end", "*Isometric": "iso"}

    def place(actual, path, orientation, *position, scale):
        assert actual is adapter and path == str(source)
        assert scale == (6, 1)
        return views[native_views[orientation]]

    def curate(actual, view, *, keep, view_label):
        events.append(("dimensions", view_label, dict(keep)))
        return [view]

    def note(actual, property_name, x, y):
        events.append(("note", property_name))
        return SimpleNamespace(GetAnnotation=lambda: notes[property_name])

    def arrange(actual, bank):
        assert actual is adapter
        events.append(("arrange", tuple(bank)))
        return 3

    def layout(actual, **options):
        assert actual is adapter
        events.append(("layout", options))

    async def finalize(actual, outputs, **options):
        assert actual is adapter and outputs is drawing.OUTPUTS
        assert options["scale"] == (6.0, 1.0)
        events.append(("export",))
        return {"slddrw": "mock result"}

    monkeypatch.setattr(drawing, "place_view", place)
    monkeypatch.setattr(drawing, "curate_view_dimensions", curate)
    monkeypatch.setattr(drawing, "set_dimension_callouts", Mock())
    monkeypatch.setattr(drawing, "add_property_linked_note", note)
    monkeypatch.setattr(drawing, "auto_arrange_view_dimensions", arrange)
    monkeypatch.setattr(drawing, "repair_project_drawing_layout", layout)
    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    return SimpleNamespace(
        adapter=adapter, factory=factory, views=views, notes=notes, events=events
    )


def test_complete_recipe_arranges_then_packs_all_views_and_linked_notes(recipe):
    result = asyncio.run(drawing.build(recipe.adapter, drawing_factory=recipe.factory))
    assert result == {"slddrw": "mock result"}
    kinds = [event[0] for event in recipe.events]
    assert kinds == ["dimensions", "dimensions", "note", "note", "arrange", "layout", "export"]
    assert recipe.events[0][2] == drawing.END_KEEP
    assert recipe.events[1][2] == drawing.SIDE_KEEP
    assert recipe.events[4][1] == tuple(recipe.views.values())
    options = recipe.events[5][1]
    assert options["views"] == recipe.views
    assert options["orderings"] == (
        AxisOrder(Axis.X, "end", "side"),
        AxisOrder(Axis.X, "side", "iso"),
    )
    assert {
        note.key: (note.annotation, note.follows_view) for note in options["notes"]
    } == {
        "manufacturing": (recipe.notes["Manufacturing Notes"], None),
        "end-caption": (recipe.notes["End View Note"], "end"),
    }


@pytest.mark.parametrize("stage", ["auto_arrange_view_dimensions", "repair_project_drawing_layout"])
def test_failed_native_layout_never_reaches_export(recipe, monkeypatch, stage):
    def rejected(*args, **kwargs):
        raise RuntimeError("native layout rejected")

    monkeypatch.setattr(drawing, stage, rejected)
    with pytest.raises(RuntimeError, match="native layout rejected"):
        asyncio.run(drawing.build(recipe.adapter, drawing_factory=recipe.factory))
    assert not any(event[0] == "export" for event in recipe.events)


def test_caption_identity_is_not_replaced_with_a_new_layout_note(recipe, monkeypatch):
    def missing_annotation(actual, property_name, x, y):
        return SimpleNamespace(GetAnnotation=lambda: None)

    def require_annotations(actual, **options):
        assert all(note.annotation is not None for note in options["notes"])

    monkeypatch.setattr(drawing, "add_property_linked_note", missing_annotation)
    monkeypatch.setattr(drawing, "repair_project_drawing_layout", require_annotations)
    with pytest.raises(AssertionError):
        asyncio.run(drawing.build(recipe.adapter, drawing_factory=recipe.factory))
    assert not any(event[0] == "export" for event in recipe.events)
