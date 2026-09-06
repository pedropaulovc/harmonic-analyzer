"""COM-free controls for native layout collection, absolute movement and readback."""

from types import SimpleNamespace

import pytest

import _drawing_native_layout as native
from _drawing_view_packing import Axis, AxisOrder, Rect


class Annotation:
    def __init__(self, name, rectangle, *, owner=None, kind=6, attachments=()):
        self.name, self.rectangle, self.Owner, self.kind = name, rectangle, owner, kind
        self.OwnerType = 1 if owner is None else 0
        self.Visible = 1
        self.position = (rectangle.xmin, rectangle.ymax, 0.0)
        self.attachments = attachments
        self.entities = tuple(object() for _kind in attachments)
        self.text, self.font = "manufacturing value", "Native font"
        self.moves = []
        self.movement = "accept"

    def GetName(self):
        return self.name

    def GetType(self):
        return self.kind

    def GetAttachedEntityCount3(self):
        return len(self.attachments)

    def GetAttachedEntityTypes(self):
        return self.attachments

    def GetAttachedEntities3(self):
        return self.entities

    def GetPosition(self):
        return self.position

    def shift(self, dx, dy):
        self.rectangle = self.rectangle.translated((dx, dy))
        self.position = (self.position[0] + dx, self.position[1] + dy, self.position[2])

    def SetPosition2(self, x, y, z):
        self.moves.append((x, y, z))
        if self.movement == "reject":
            return False
        if self.movement == "accept":
            self.shift(x - self.position[0], y - self.position[1])
        return True


class View:
    def __init__(self, name, rectangle):
        self.name, self.rectangle = name, rectangle
        self._position = (
            (rectangle.xmin + rectangle.xmax) / 2,
            (rectangle.ymin + rectangle.ymax) / 2,
        )
        self.ScaleRatio = (1.0, 1.0)
        self.ReferencedConfiguration = "Default"
        self.reference = "C:/model.SLDPRT"
        self.annotations, self.children, self.moves = [], [], []
        self.base = self.next = None
        self.events = []
        self.movement = "accept"

    def GetName2(self):
        return self.name

    def GetOutline(self):
        return self.rectangle.bounds

    def GetReferencedModelName(self):
        return self.reference

    def GetBaseView(self):
        return self.base

    def GetNextView(self):
        return self.next

    def GetAnnotations(self):
        return self.annotations

    @property
    def Position(self):
        return self._position

    def shift(self, dx, dy):
        self._position = (self._position[0] + dx, self._position[1] + dy)
        self.rectangle = self.rectangle.translated((dx, dy))
        for annotation in self.annotations:
            annotation.shift(dx, dy)
        for child in self.children:
            child.shift(dx, dy)

    @Position.setter
    def Position(self, value):
        self.moves.append(value)
        self.events.append(self.name)
        if self.movement == "accept":
            self.shift(value[0] - self.Position[0], value[1] - self.Position[1])

    def SetViewPosition(self, value, move_children):
        assert move_children is True
        if self.movement == "reject":
            return False
        self.Position = value
        return True


def measure(_adapter, annotation):
    if annotation.kind == 17:
        raise ValueError("unsupported native annotation kind 17")
    return SimpleNamespace(
        name=annotation.name,
        kind=annotation.kind,
        envelope=annotation.rectangle,
        format_signature=(annotation.font, 0.0035),
        text_runs=(
            SimpleNamespace(
                value=annotation.text,
                height_m=0.0035,
                font=annotation.font,
                angle_rad=0.0,
                reference=1,
                inverted=0,
            ),
        ),
    )


def scene(monkeypatch, views, sheet_annotations=()):
    monkeypatch.setattr(native, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(native, "double_array", tuple)
    sheet_view = View("sheet", Rect(0, 0, 10, 10))
    sheet_view.annotations = list(sheet_annotations)
    events = []
    ordered = [sheet_view, *views.values()]
    for index, view in enumerate(ordered):
        view.events = events
        view.next = ordered[index + 1] if index + 1 < len(ordered) else None
    sheet = SimpleNamespace(
        GetProperties2=lambda: (0.0, 0.0, 1.0, 1.0, 0.0, 10.0, 10.0, 0.0),
        GetZoneMargin=lambda _index: 0.0,
    )
    model = SimpleNamespace(
        GetType=lambda: 3,
        GetCurrentSheet=lambda: sheet,
        GetFirstView=lambda: sheet_view,
        EditRebuild3=lambda: True,
    )
    adapter = SimpleNamespace(
        currentModel=model, swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b))
    )
    options = dict(
        views=views,
        title_block=Rect(8, 0, 10, 1),
        measure_annotation=measure,
        gap_m=0.1,
    )
    return adapter, options, events


def test_already_fitting_layout_has_no_native_writes(monkeypatch):
    front = View("front", Rect(1, 2, 3, 4))
    adapter, options, _events = scene(monkeypatch, {"front": front})
    result = native.repair_native_layout(adapter, **options)
    assert result.status is native.NativeLayoutStatus.UNCHANGED
    assert front.moves == []
    assert result.before_outlines == result.after_outlines


def test_hidden_sheet_symbol_has_no_footprint_but_remains_in_manifest(monkeypatch):
    front = View("front", Rect(1, 2, 3, 4))
    hidden = Annotation("hidden-sf", Rect(-1, -1, 1, 1), kind=7)
    hidden.Visible = 3
    adapter, options, _ = scene(monkeypatch, {"front": front}, [hidden])
    result = native.repair_native_layout(adapter, **options)
    assert result.status is native.NativeLayoutStatus.UNCHANGED
    assert list(result.footprint_exclusions) == ["('sheet', 'hidden-sf', 7)"]
    assert hidden.Visible == 3
    assert hidden.moves == []


@pytest.mark.parametrize("visibility", [0, 1, 2])
def test_unknown_visible_and_half_hidden_symbols_are_not_silently_excluded(
    monkeypatch, visibility
):
    front = View("front", Rect(1, 2, 3, 4))
    annotation = Annotation("sf", Rect(-1, -1, 1, 1), kind=7)
    annotation.Visible = visibility
    adapter, options, _ = scene(monkeypatch, {"front": front}, [annotation])
    result = native.repair_native_layout(adapter, **options)
    assert result.status is native.NativeLayoutStatus.NO_FIT
    assert result.footprint_exclusions == {}


def test_hidden_symbol_becoming_visible_during_move_fails_readback(monkeypatch):
    front = View("front", Rect(-1, 2, 1, 4))
    hidden = Annotation("hidden-sf", Rect(-1, -1, 1, 1), kind=7)
    hidden.Visible = 3
    adapter, options, _ = scene(monkeypatch, {"front": front}, [hidden])

    def reveal():
        hidden.Visible = 1
        return True

    adapter.currentModel.EditRebuild3 = reveal
    with pytest.raises(RuntimeError, match="annotation inventory"):
        native.repair_native_layout(adapter, **options)


def test_declared_layout_note_must_not_be_hidden(monkeypatch):
    front = View("front", Rect(1, 2, 3, 4))
    note = Annotation("manufacturing", Rect(1, 5, 3, 6))
    note.Visible = 3
    adapter, options, _ = scene(monkeypatch, {"front": front}, [note])
    with pytest.raises(ValueError, match="declared layout note is hidden"):
        native.repair_native_layout(
            adapter, **options, notes=(native.LayoutNote("notes", note),)
        )


def test_parent_propagation_does_not_apply_child_translation_twice(monkeypatch):
    front, top = View("front", Rect(-1, 1, 1, 3)), View("top", Rect(-1, 4, 1, 6))
    front.children, top.base = [top], front
    originals = {"front": front.Position, "top": top.Position}
    adapter, options, events = scene(monkeypatch, {"top": top, "front": front})
    result = native.repair_native_layout(
        adapter,
        **options,
        parents={"top": "front"},
        alignments=(native.AxisLink(Axis.X, "front", "top"),),
        orderings=(AxisOrder(Axis.Y, "front", "top"),),
    )
    assert result.status is native.NativeLayoutStatus.APPLIED
    assert events == ["front", "top"]
    for name, view in options["views"].items():
        assert len(view.moves) == 1
        assert view.Position == pytest.approx(
            tuple(
                a + b
                for a, b in zip(originals[name], result.translations[f"view:{name}"])
            )
        )
    assert front.Position[0] == pytest.approx(top.Position[0])


def test_explicit_free_note_below_border_moves_without_changing_view_scale(monkeypatch):
    front = View("front", Rect(5, 5, 7, 7))
    note = Annotation("general", Rect(1, -2, 3, -1))
    adapter, options, _events = scene(monkeypatch, {"front": front}, [note])
    result = native.repair_native_layout(
        adapter, **options, notes=(native.LayoutNote("general", note),)
    )
    assert result.status is native.NativeLayoutStatus.APPLIED
    assert note.rectangle.ymin >= 0
    assert len(note.moves) == 1
    assert front.ScaleRatio == (1.0, 1.0)


def test_view_owned_free_note_is_not_double_counted_or_double_translated(monkeypatch):
    front = View("front", Rect(-1, 5, 1, 7))
    note = Annotation("general", Rect(1, -2, 3, -1), owner=front)
    front.annotations = [note]
    original = note.GetPosition()
    adapter, options, _events = scene(monkeypatch, {"front": front})
    result = native.repair_native_layout(
        adapter, **options, notes=(native.LayoutNote("general", note),)
    )
    assert result.status is native.NativeLayoutStatus.APPLIED
    assert result.before_bounds["view:front"] == Rect(-1, 5, 1, 7)
    assert result.before_bounds["note:general"] == Rect(1, -2, 3, -1)
    assert note.GetPosition()[:2] == pytest.approx(
        tuple(a + b for a, b in zip(original, result.translations["note:general"]))
    )
    assert len(note.moves) == 1


def test_sheet_owned_caption_uses_explicit_view_association(monkeypatch):
    front, iso = View("front", Rect(1, 4, 3, 6)), View("iso", Rect(10, 4, 11, 5))
    caption = Annotation("caption", Rect(7, 3, 8, 3.5))
    original = caption.GetPosition()
    adapter, options, _events = scene(
        monkeypatch, {"front": front, "iso": iso}, [caption]
    )
    result = native.repair_native_layout(
        adapter,
        **options,
        notes=(native.LayoutNote("caption", caption, follows_view="iso"),),
    )
    assert result.status is native.NativeLayoutStatus.APPLIED
    assert caption.GetPosition()[:2] == pytest.approx(
        tuple(a + b for a, b in zip(original, result.translations["view:iso"]))
    )
    assert "note:caption" not in result.translations


@pytest.mark.parametrize("kind", [6, 14])
def test_unlisted_sheet_notes_and_measured_tables_are_fixed_obstacles(
    monkeypatch, kind
):
    front = View("front", Rect(1, 1, 3, 3))
    fixed = Annotation("fixed", Rect(1, 1, 3, 3), kind=kind)
    original = fixed.rectangle
    adapter, options, _events = scene(monkeypatch, {"front": front}, [fixed])
    result = native.repair_native_layout(adapter, **options)
    assert result.status is native.NativeLayoutStatus.APPLIED
    assert fixed.rectangle == original
    assert fixed.moves == []


@pytest.mark.parametrize(
    "rectangles",
    [
        [Rect(1, -2, 3, -1)],
        [Rect(8, 0, 9, 0.5)],
        [Rect(1, 1, 3, 3), Rect(2, 2, 4, 4)],
    ],
)
def test_invalid_fixed_content_cannot_be_reported_as_a_fitting_sheet(
    monkeypatch, rectangles
):
    front = View("front", Rect(5, 5, 7, 7))
    notes = [
        Annotation(str(index), rectangle) for index, rectangle in enumerate(rectangles)
    ]
    adapter, options, _events = scene(monkeypatch, {"front": front}, notes)
    result = native.repair_native_layout(adapter, **options)
    assert result.status is native.NativeLayoutStatus.NO_FIT
    assert "fixed" in result.reason
    assert front.moves == []


def test_native_zone_margin_not_a_copied_nominal_margin(monkeypatch):
    front = View("front", Rect(0.2, 2, 1.2, 3))
    adapter, options, _events = scene(monkeypatch, {"front": front})
    adapter.currentModel.GetCurrentSheet().GetZoneMargin = lambda index: (0, 0, 0, 1)[
        index
    ]
    result = native.repair_native_layout(adapter, **options)
    assert result.status is native.NativeLayoutStatus.APPLIED
    assert front.rectangle.xmin >= 1


def test_annotation_envelope_overflow_cannot_hide_behind_small_view_outline(
    monkeypatch,
):
    front = View("front", Rect(1, 2, 3, 4))
    front.annotations = [
        Annotation("huge-callout", Rect(-20, 2, 20, 3), owner=front, kind=5)
    ]
    adapter, options, _events = scene(monkeypatch, {"front": front})
    result = native.repair_native_layout(adapter, **options)
    assert result.status is native.NativeLayoutStatus.NO_FIT
    assert front.moves == []
    assert result.after_outlines == {}


def test_search_limit_returns_without_native_writes(monkeypatch):
    front, top = View("front", Rect(1, 2, 3, 4)), View("top", Rect(1, 2, 3, 4))
    adapter, options, _events = scene(monkeypatch, {"front": front, "top": top})
    result = native.repair_native_layout(adapter, **options, max_search_nodes=1)
    assert result.status is native.NativeLayoutStatus.SEARCH_LIMIT
    assert front.moves == top.moves == []


@pytest.mark.parametrize(
    "change",
    [
        "text",
        "font",
        "visibility",
        "attachments",
        "missing",
        "scale",
        "reference",
        "configuration",
        "envelope",
        "fixed",
    ],
)
def test_post_rebuild_changes_are_rejected(monkeypatch, change):
    front = View("front", Rect(-1, 2, 1, 4))
    annotation = Annotation(
        "size", Rect(-1, 2, 1, 3), owner=front, kind=4, attachments=(1, 1)
    )
    front.annotations = [annotation]
    fixed = Annotation("fixed", Rect(5, 5, 6, 6))
    adapter, options, _events = scene(monkeypatch, {"front": front}, [fixed])

    def rebuild():
        if change == "text":
            annotation.text = "wrong value"
        if change == "font":
            annotation.font = "changed font"
        if change == "visibility":
            annotation.Visible = 3
        if change == "attachments":
            annotation.attachments = (2, 2)
        if change == "missing":
            front.annotations.clear()
        if change == "scale":
            front.ScaleRatio = (2.0, 1.0)
        if change == "reference":
            front.reference = "C:/other.SLDPRT"
        if change == "configuration":
            front.ReferencedConfiguration = "Other"
        if change == "envelope":
            annotation.rectangle = Rect(-5, -5, 20, 20)
        if change == "fixed":
            fixed.shift(0.5, 0)
        return True

    adapter.currentModel.EditRebuild3 = rebuild
    with pytest.raises(
        RuntimeError, match="changed|moved fixed|remeasured native layout"
    ):
        native.repair_native_layout(adapter, **options)


@pytest.mark.parametrize("movement", ["reject", "clamp"])
def test_rejected_or_clamped_view_position_fails(monkeypatch, movement):
    front = View("front", Rect(-1, 2, 1, 4))
    front.movement = movement
    adapter, options, _events = scene(monkeypatch, {"front": front})
    with pytest.raises(
        RuntimeError,
        match="rejected layout target|did not reach absolute layout target",
    ):
        native.repair_native_layout(adapter, **options)


@pytest.mark.parametrize("movement", ["reject", "clamp"])
def test_rejected_or_clamped_free_note_movement_fails(monkeypatch, movement):
    front = View("front", Rect(5, 5, 7, 7))
    note = Annotation("general", Rect(1, -2, 3, -1))
    note.movement = movement
    adapter, options, _events = scene(monkeypatch, {"front": front}, [note])
    with pytest.raises(
        RuntimeError, match="movement was rejected|did not reach absolute layout target"
    ):
        native.repair_native_layout(
            adapter, **options, notes=(native.LayoutNote("general", note),)
        )


def test_unknown_annotation_kind_is_not_silently_discarded(monkeypatch):
    front = View("front", Rect(1, 2, 3, 4))
    front.annotations = [
        Annotation("unsupported", Rect(1, 2, 3, 3), owner=front, kind=17)
    ]
    adapter, options, _events = scene(monkeypatch, {"front": front})
    with pytest.raises(ValueError, match="unsupported native annotation"):
        native.repair_native_layout(adapter, **options)
    assert front.moves == []


def test_unplanned_native_view_is_not_ignored(monkeypatch):
    front, iso = View("front", Rect(1, 2, 3, 4)), View("iso", Rect(5, 5, 7, 7))
    adapter, options, _events = scene(monkeypatch, {"front": front, "iso": iso})
    options["views"] = {"front": front}
    with pytest.raises(RuntimeError, match="view inventory differs from plan"):
        native.repair_native_layout(adapter, **options)


def test_same_named_view_from_another_document_is_rejected(monkeypatch):
    front = View("front", Rect(1, 2, 3, 4))
    foreign = View("front", Rect(-1, 2, 1, 4))
    adapter, options, _events = scene(monkeypatch, {"front": front})
    options["views"] = {"front": foreign}
    with pytest.raises(RuntimeError, match="not the active sheet's native view"):
        native.repair_native_layout(adapter, **options)
    assert front.moves == foreign.moves == []


def test_same_named_annotation_owner_from_another_document_is_rejected(monkeypatch):
    front = View("front", Rect(1, 2, 3, 4))
    foreign = View("front", Rect(1, 2, 3, 4))
    front.annotations = [Annotation("frame", Rect(1, 2, 2, 3), owner=foreign, kind=5)]
    adapter, options, _events = scene(monkeypatch, {"front": front})
    with pytest.raises(RuntimeError, match="not the planned native view object"):
        native.repair_native_layout(adapter, **options)


@pytest.mark.parametrize("identity", ["annotation", "attachment"])
def test_rebuild_cannot_replace_native_identity_under_identical_labels(
    monkeypatch, identity
):
    front = View("front", Rect(-1, 2, 1, 4))
    annotation = Annotation(
        "frame", Rect(-1, 2, 0, 3), owner=front, kind=5, attachments=(1,)
    )
    front.annotations = [annotation]
    adapter, options, _events = scene(monkeypatch, {"front": front})

    def rebuild():
        if identity == "annotation":
            replacement = Annotation(
                "frame", annotation.rectangle, owner=front, kind=5, attachments=(1,)
            )
            replacement.entities = annotation.entities
            front.annotations = [replacement]
        if identity == "attachment":
            annotation.entities = (object(),)
        return True

    adapter.currentModel.EditRebuild3 = rebuild
    with pytest.raises(
        RuntimeError,
        match="replaced annotation identity|changed exact attachment identity",
    ):
        native.repair_native_layout(adapter, **options)


def test_null_attachment_handle_is_not_accepted_as_unchanged_geometry(monkeypatch):
    front = View("front", Rect(1, 2, 3, 4))
    annotation = Annotation(
        "frame", Rect(1, 2, 2, 3), owner=front, kind=5, attachments=(1,)
    )
    annotation.entities = (None,)
    front.annotations = [annotation]
    adapter, options, _events = scene(monkeypatch, {"front": front})
    with pytest.raises(RuntimeError, match="null native handle"):
        native.repair_native_layout(adapter, **options)


def test_zero_attachment_model_dimension_has_explicit_identity_exclusion(monkeypatch):
    front = View("front", Rect(1, 2, 3, 4))
    front.annotations = [
        Annotation("imported-dimension", Rect(1, 2, 2, 3), owner=front, kind=4)
    ]
    adapter, options, _events = scene(monkeypatch, {"front": front})
    result = native.repair_native_layout(adapter, **options)
    assert len(result.attachment_identity_exclusions) == 1
    assert "geometry identity not checked" in next(
        iter(result.attachment_identity_exclusions.values())
    )


def test_rejected_rebuild_aborts_without_claiming_layout_success(monkeypatch):
    front = View("front", Rect(-1, 2, 1, 4))
    adapter, options, _events = scene(monkeypatch, {"front": front})
    adapter.currentModel.EditRebuild3 = lambda: False
    with pytest.raises(RuntimeError, match="rebuild failed"):
        native.repair_native_layout(adapter, **options)


def test_different_annotations_with_same_name_and_context_are_ambiguous(monkeypatch):
    front = View("front", Rect(1, 2, 3, 4))
    front.annotations = [
        Annotation("same", Rect(1, 2, 2, 3), owner=front) for _ in range(2)
    ]
    adapter, options, _events = scene(monkeypatch, {"front": front})
    with pytest.raises(RuntimeError, match="annotation identity is ambiguous"):
        native.repair_native_layout(adapter, **options)


def test_repeated_enumeration_of_same_native_annotation_is_deduplicated(monkeypatch):
    front = View("front", Rect(1, 2, 3, 4))
    annotation = Annotation("same", Rect(1, 2, 2, 3), owner=front)
    front.annotations = [annotation, annotation]
    adapter, options, _events = scene(monkeypatch, {"front": front})
    assert (
        native.repair_native_layout(adapter, **options).status
        is native.NativeLayoutStatus.UNCHANGED
    )


def test_native_parent_must_be_declared_and_logical_cycles_fail(monkeypatch):
    front, top = View("front", Rect(1, 2, 3, 4)), View("top", Rect(1, 5, 3, 7))
    adapter, options, _events = scene(monkeypatch, {"front": front, "top": top})
    top.base = front
    with pytest.raises(ValueError, match="declare its native base"):
        native.repair_native_layout(adapter, **options)
    with pytest.raises(ValueError, match="cycle"):
        native.repair_native_layout(
            adapter, **options, parents={"top": "front", "front": "top"}
        )


def test_template_annotations_are_explicitly_covered_by_supplied_keepout(monkeypatch):
    front = View("front", Rect(8, 0, 9, 0.5))
    template = Annotation("title", Rect(8, 0, 10, 1), kind=17)
    template.OwnerType = 2
    adapter, options, _events = scene(monkeypatch, {"front": front}, [template])
    result = native.repair_native_layout(adapter, **options)
    assert result.status is native.NativeLayoutStatus.APPLIED
    assert template.moves == []


def test_native_layout_sources_and_contract_are_enrolled_in_recipe_gate():
    from pathlib import Path
    from test_dodo_recipe import _load_dodo

    recipe = next(
        task for task in _load_dodo().task_check() if task["name"] == "recipe"
    )
    assert Path(__file__).name in {
        Path(item).name for item in recipe["actions"][0][1][0]
    }
    assert {"_drawing_native_layout.py", "_drawing_view_packing.py"} <= {
        Path(item).name for item in recipe["file_dep"]
    }
