"""The split lever layout changes presentation, never its manufacturing contract."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import draw_channel_lever as recipe
from channel_lever_spec import DRAWING_DIMENSIONS, SOURCE_BASIC_DIMENSIONS


@pytest.fixture
def built(monkeypatch, tmp_path):
    events = []
    views = []
    retained = {}
    created = {}
    entities = {
        name: object()
        for name in (
            "fulcrum",
            "bar_pin",
            "spring",
            "tip",
            "top_front",
            "top_back",
            "bottom_front",
            "broad_a",
            "broad_opposite",
        )
    }
    source = tmp_path / "owned-lever.SLDPRT"
    source.write_bytes(b"owned mock only")
    model = object()

    async def open_model(path):
        assert path == str(source)
        return {"status": "success"}

    adapter = SimpleNamespace(currentModel=model, open_model=open_model)
    monkeypatch.setattr(recipe, "check", lambda *args: None)
    monkeypatch.setattr(recipe, "read_required_properties", lambda *args, **kw: None)
    def drawing_factory(*args, **kw):
        return model, None
    monkeypatch.setattr(recipe, "stamp_drawing_summary", lambda *args: None)

    def place(adapter, path, orientation, x, y, *, scale):
        view = SimpleNamespace(
            orientation=orientation,
            center=(x, y),
            scale=scale,
            ReferencedDocument=model,
        )
        views.append(view)
        return view

    monkeypatch.setattr(recipe, "place_view", place)
    for name in ("set_hidden_lines_removed", "set_hidden_lines_visible"):
        monkeypatch.setattr(recipe, name, lambda *args: None)

    def retain(adapter, view, *, keep, view_label):
        events.append(("retain", view, tuple(keep), view_label))
        bank = [
            SimpleNamespace(name=name, GetSpecificAnnotation=lambda name=name: name)
            for name in keep
        ]
        retained[view_label] = {item.name: item for item in bank}
        return bank

    monkeypatch.setattr(recipe, "retain_view_dimensions", retain)
    monkeypatch.setattr(recipe, "dimension_name", lambda adapter, ann: ann.name)
    monkeypatch.setattr(
        recipe,
        "require_basic_dimension",
        lambda value, **kw: events.append(("source_basic", value)),
    )
    monkeypatch.setattr(recipe, "auto_center_marks", lambda *args, **kw: True)
    monkeypatch.setattr(
        recipe, "_model_entities", lambda actual: entities if actual is model else None
    )
    monkeypatch.setattr(recipe, "_add_tip_arc_center_mark", lambda *args: None)

    def dimension(adapter, view, **kw):
        events.append(("dimension", view, kw))
        annotation = object()
        display = SimpleNamespace(label=kw["label"], GetAnnotation=lambda: annotation)
        created[kw["label"]] = display
        return display

    monkeypatch.setattr(recipe, "add_entity_dimension", dimension)
    monkeypatch.setattr(
        recipe,
        "set_basic_dimension",
        lambda adapter, value, **kw: events.append(("basic", value.label)),
    )
    monkeypatch.setattr(recipe, "_force_dimension_black", lambda *args, **kw: None)
    for name, event in (
        ("add_native_hole_callout", "hole"),
        ("add_datum_feature", "datum"),
        ("add_feature_control_frame", "gtol"),
    ):
        monkeypatch.setattr(
            recipe,
            name,
            lambda adapter, view, _event=event, **kw: events.append((_event, view, kw)),
        )
    monkeypatch.setattr(
        recipe,
        "add_property_linked_note",
        lambda *args: SimpleNamespace(GetAnnotation=lambda: object()),
    )
    monkeypatch.setattr(
        recipe,
        "auto_arrange_view_dimensions",
        lambda adapter, bank, **kw: events.append(("arrange", bank, kw)),
    )
    monkeypatch.setattr(
        recipe,
        "align_channel_lever_basic_pairs",
        lambda adapter, **kw: events.append(("parallel", kw)),
    )

    def layout(adapter, **kw):
        events.append(("layout", kw))

    async def finalize(*args, **kw):
        events.append(("finalize", kw))
        return {"status": "success"}

    monkeypatch.setattr(recipe, "finalize_drawing", finalize)
    result = asyncio.run(
        recipe.build(
            adapter, drawing_factory=drawing_factory, source=source, layout=layout
        )
    )
    return SimpleNamespace(
        events=events,
        views=views,
        entities=entities,
        result=result,
        retained=retained,
        created=created,
    )


def test_parallel_spacing_receives_exact_created_retained_handles_before_layout(built):
    calls = [
        (index, row[1])
        for index, row in enumerate(built.events)
        if row[0] == "parallel"
    ]
    assert len(calls) == 1
    index, call = calls[0]
    assert call["front"] is built.views[0]
    assert call["holes"] is built.views[1]
    assert call["bar_length"] is built.retained["profile"]["BarLength"]
    assert call["tip_centre_x"] is built.retained["profile"]["TipCentreX"]
    assert (
        call["bar_pin_c2c"] is built.created["fulcrum-to-bar-pin c2c"].GetAnnotation()
    )
    assert call["spring_c2c"] is built.created["fulcrum-to-spring c2c"].GetAnnotation()
    assert built.events[index + 1][0] == "layout"


def test_five_views_split_exact_original_eleven_dimensions(built):
    assert [view.orientation for view in built.views] == [
        "*Front",
        "*Front",
        "*Right",
        "*Top",
        "*Isometric",
    ]
    rows = [row for row in built.events if row[0] == "retain"]
    bank = {row[3]: set(row[2]) for row in rows}
    assert bank == {
        "profile": {"BarLength", "TipCentreX", "NoseRadius", "TipRadius"},
        "holes": {"FulcrumDia"},
        "right": set(),
        "top": set(),
    }
    assert set.union(*bank.values()) == set.union(*DRAWING_DIMENSIONS.values())
    assert sum(map(len, bank.values())) == 5
    assert sum(row[0] == "dimension" for row in built.events) == 4
    assert sum(row[0] == "hole" for row in built.events) == 2
    assert {row[1] for row in built.events if row[0] == "source_basic"} == set.union(
        *SOURCE_BASIC_DIMENSIONS.values()
    )
    assert {row[1] for row in built.events if row[0] == "basic"} == {
        "fulcrum-to-bar-pin c2c",
        "fulcrum-to-spring c2c",
        "bar height",
    }


def test_native_arrangement_once_after_all_dimensions_before_all_datums_and_gtols(
    built,
):
    indices = [i for i, row in enumerate(built.events) if row[0] == "arrange"]
    assert len(indices) == 1
    index = indices[0]
    assert all(
        i < index
        for i, row in enumerate(built.events)
        if row[0] in {"retain", "dimension", "hole", "basic"}
    )
    assert all(
        i > index for i, row in enumerate(built.events) if row[0] in {"datum", "gtol"}
    )
    assert built.events[index][1] == tuple(built.views)
    assert built.events[index][2] == {"spacing_m": 0.003}


def test_split_roles_keep_original_exact_datum_and_gtol_entities(built):
    profile, holes, right, top, _ = built.views
    datum = {row[2]["datum"]: row for row in built.events if row[0] == "datum"}
    for name, view, entity in (
        ("A", right, "broad_a"),
        ("B", holes, "fulcrum"),
        ("C", top, "top_front"),
    ):
        assert datum[name][1] is view
        assert datum[name][2]["entity"] is built.entities[entity]
    gtols = {row[2]["label"]: row for row in built.events if row[0] == "gtol"}
    expected = {
        "outer perimeter profile": (
            profile,
            "top_front",
            "profile_surface",
            "0.50",
            ("A", "B", "C"),
        ),
        "fulcrum bore perpendicularity": (
            holes,
            "fulcrum",
            "perpendicularity",
            "0.05",
            ("A",),
        ),
        "opposite broad face parallelism": (
            right,
            "broad_opposite",
            "parallelism",
            "0.05",
            ("A",),
        ),
        "bar-pin hole position": (
            holes,
            "bar_pin",
            "position",
            "0.20",
            ("A", "B", "C"),
        ),
        "spring-eye hole position": (
            holes,
            "spring",
            "position",
            "0.20",
            ("A", "B", "C"),
        ),
    }
    assert gtols.keys() == expected.keys()
    for label, (view, entity, kind, tolerance, datums) in expected.items():
        row = gtols[label]
        assert row[1] is view
        assert row[2]["entity"] is built.entities[entity]
        assert (row[2]["characteristic"], row[2]["tolerance"], row[2]["datums"]) == (
            kind,
            tolerance,
            datums,
        )
    assert gtols["outer perimeter profile"][2]["all_around"] is True
    assert all(
        gtols[label][2]["diameter"] is True
        for label in (
            "fulcrum bore perpendicularity",
            "bar-pin hole position",
            "spring-eye hole position",
        )
    )


def test_profile_and_hole_dimensions_no_longer_share_a_view(built):
    profile, holes, _, top, _ = built.views
    expected = {
        "fulcrum-to-bar-pin c2c": (holes, ("fulcrum", "bar_pin")),
        "fulcrum-to-spring c2c": (holes, ("fulcrum", "spring")),
        "lever thickness": (top, ("top_front", "top_back")),
        "bar height": (profile, ("bottom_front", "top_front")),
    }
    for _, view, kw in (row for row in built.events if row[0] == "dimension"):
        owner, entities = expected[kw["label"]]
        assert view is owner
        assert all(
            actual is built.entities[role]
            for actual, role in zip(kw["entities"], entities, strict=True)
        )
    assert all(row[1] is holes for row in built.events if row[0] == "hole")


def test_split_recipe_opt_in_keeps_final_dimension_crossing_gate(built):
    from _drawing_leader_clearance import validate_dimension_leader_clearance

    layout = next(row[1] for row in built.events if row[0] == "layout")
    assert (
        layout["additional_annotation_validation"]
        is validate_dimension_leader_clearance
    )
    assert set(layout["views"]) == {"front", "holes", "right", "top", "iso"}
    assert tuple(layout["views"].values()) == tuple(built.views)
    assert built.result == {"status": "success"}
