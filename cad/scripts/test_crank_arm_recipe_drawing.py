"""Execute the crank recipe offline, with separate source/drawing/view identities."""

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import crank_arm_spec as spec
import draw_crank_arm as recipe
import _drawing_entities as native


def forbidden(*_args, **_kwargs):
    pytest.fail("sheet-coordinate feature selection is forbidden")


@pytest.fixture
def scene(monkeypatch, tmp_path):
    path = tmp_path / "crank-arm.SLDPRT"
    path.touch()
    monkeypatch.setattr(recipe, "SOURCE", path)
    monkeypatch.setattr(recipe, "_early_bound", lambda obj, _kind: obj)
    source = SimpleNamespace(
        GetType=Mock(return_value=1),
        GetPathName=Mock(return_value=str(path)),
        GetConfigurationNames=Mock(return_value=("Default",)),
        ConfigurationManager=SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(Name="Default")
        ),
        Extension=SimpleNamespace(SelectByID2=forbidden),
    )
    drawing = SimpleNamespace(Extension=SimpleNamespace(SelectByID2=forbidden))
    app = SimpleNamespace(
        ActiveDoc=None,
        IsSame=Mock(side_effect=lambda left, right: int(left is right)),
        GetOpenDocumentByName=Mock(return_value=source),
    )
    adapter = SimpleNamespace(swApp=app, currentModel=None)
    state = SimpleNamespace(
        source=source, drawing=drawing, adapter=adapter, app=app,
        events=[], banks=[], views={}, hooks={}, dimensions=[], calls={},
    )

    def hook(phase):
        if phase in state.hooks:
            state.hooks[phase]()

    annotation = SimpleNamespace(
        GetPosition=Mock(return_value=(0.12, 0.13, 0.0042)),
        SetPosition2=Mock(return_value=True),
    )
    state.finish_annotation = annotation
    state.finish = SimpleNamespace(GetAnnotation=Mock(return_value=annotation))
    drawing.EditRebuild3 = Mock(return_value=True)

    def native_event(name, method):
        def invoke(*_args):
            state.events.append(name)
            hook(name)
            return method.return_value
        method.side_effect = invoke

    native_event("finish.GetAnnotation", state.finish.GetAnnotation)
    native_event("finish.GetPosition", annotation.GetPosition)
    native_event("finish.SetPosition2", annotation.SetPosition2)
    native_event("drawing.EditRebuild3", drawing.EditRebuild3)

    async def open_model(filename):
        assert filename == str(path)
        adapter.currentModel = source
        app.ActiveDoc = source
        state.events.append("open")
        hook("open")
        return SimpleNamespace(is_success=True, data=source)

    adapter.open_model = open_model

    def factory(actual_adapter, **kwargs):
        assert actual_adapter is adapter
        assert kwargs == {"property_view": recipe.PART_STEM, "scale": (2, 1)}
        state.events.append("factory")
        adapter.currentModel = drawing
        app.ActiveDoc = drawing
        return drawing, object()

    def resolve(roles):
        assert roles is recipe.ENTITY_ROLES
        state.events.append("resolve")
        hook("resolve")
        bank = {role: object() for role in roles}
        state.banks.append(bank)
        return bank

    def model_entities(model):
        assert model is source
        state.events.append("ModelEntities")
        return SimpleNamespace(resolve=resolve)

    monkeypatch.setattr(recipe, "ModelEntities", model_entities)

    def place_view(actual_adapter, filename, orientation, x, y, *, scale):
        assert actual_adapter is adapter
        assert filename == str(path)
        view = SimpleNamespace(
            ReferencedDocument=source, ReferencedConfiguration="Default",
            orientation=orientation, position=(x, y), scale=scale,
        )
        state.views[orientation] = view
        state.events.append("view")
        hook("view")
        return view

    monkeypatch.setattr(recipe, "place_view", place_view)

    def record(name):
        def call(*args, **kwargs):
            state.events.append(name)
            state.calls.setdefault(name, []).append((args, kwargs))
            assert not {"edge_xy", "p0", "p1", "selection_point_xy"} & kwargs.keys()
            for entity in kwargs.get("entities", ()):
                assert any(entity is handle for handle in state.banks[-1].values())
            for key in ("entity", "edge"):
                if key in kwargs:
                    assert any(kwargs[key] is handle for handle in state.banks[-1].values())
            hook(name)
            if name == "add_entity_dimension":
                dimension = SimpleNamespace(label=kwargs["label"])
                state.dimensions.append(dimension)
                return dimension
            if name == "curate_view_dimensions":
                return [SimpleNamespace(name=name) for name in kwargs["keep"]]
            if name == "auto_center_marks":
                return True
            if name == "add_surface_finish":
                return state.finish
            return None
        return call

    for name in (
        "read_required_properties", "stamp_drawing_summary",
        "set_hidden_lines_removed", "set_hidden_lines_visible",
        "curate_view_dimensions", "verify_dimension_callouts",
        "set_dimension_precision", "add_entity_dimension", "auto_center_marks",
        "set_arc_endpoints_to_center", "set_basic_dimension",
        "add_feature_control_frame", "add_native_hole_callout",
        "add_datum_feature", "add_surface_finish", "add_property_linked_note",
        "_validate_explicit_annotation_attachment",
    ):
        monkeypatch.setattr(recipe, name, record(name))
    for name in ("add_edge_dimension", "find_edge_near", "_select_view_entity"):
        monkeypatch.setattr(recipe, name, forbidden, raising=False)

    async def finalize(actual_adapter, outputs, **kwargs):
        assert actual_adapter is adapter
        assert outputs is recipe.OUTPUTS
        assert kwargs == {
            "pdf_title": "Crank Arm Manufacturing Drawing", "scale": (2, 1)
        }
        state.events.append("finalize")
        return {"offline": "no native outputs written"}

    monkeypatch.setattr(recipe, "finalize_drawing", finalize)
    state.run = lambda: asyncio.run(recipe.build(adapter, drawing_factory=factory))
    return state


def test_recipe_resolves_once_before_insertion_and_uses_fresh_bank(scene):
    assert scene.run() == {"offline": "no native outputs written"}
    assert scene.events[:4] == ["open", "ModelEntities", "resolve", "read_required_properties"]
    assert scene.events.count("ModelEntities") == scene.events.count("resolve") == 1
    assert scene.events.index("resolve") < scene.events.index("factory")
    assert scene.events[-1] == "finalize"
    assert len({id(scene.source), id(scene.drawing), *map(id, scene.views.values())}) == 6
    scene.run()
    assert len(scene.banks) == 2
    assert all(scene.banks[0][role] is not scene.banks[1][role] for role in recipe.ENTITY_ROLES)


def test_recipe_keeps_all_six_marked_dimensions_and_source_callout_context(scene):
    scene.run()
    curated = scene.calls["curate_view_dimensions"]
    assert [(args[1].orientation, set(kw["keep"])) for args, kw in curated] == [
        ("*Front", {"ArmEndX", "DimpleX", "BossRadius", "ShaftBoreDia", "DimpleDia"}),
        ("*Right", {"Depth"}), ("*Top", set()),
    ]
    assert set().union(*(set(kw["keep"]) for _, kw in curated)) == set().union(
        *spec.DRAWING_DIMENSIONS.values()
    )
    verifiers = scene.calls["verify_dimension_callouts"]
    assert len(verifiers) == 2
    for (args, kw), (dimension, feature) in zip(verifiers, [
        ("ShaftBoreDia", "ShaftBoreProfile"), ("DimpleDia", "DimpleProfile")
    ], strict=True):
        assert kw == {"feature_name": feature, "view": scene.views["*Front"],
                      "source_model": scene.source}
        assert args[2] == {dimension: spec.DIMENSION_CALLOUTS[dimension]}
        assert {annotation.name for annotation in args[1]} == {
            "ArmEndX", "DimpleX", "BossRadius", "ShaftBoreDia", "DimpleDia", "Depth"
        }
    assert scene.calls["set_dimension_precision"][0][0][2] == {"ShaftBoreDia": 3}
    assert [view.scale for view in scene.views.values()] == [(2, 1), (2, 1), (2, 1), (1, 1)]


def test_recipe_dimensions_use_exact_owned_role_pairs_and_basic_assignments(scene):
    scene.run()
    expected = [
        ("*Right", ("width_lo", "width_hi"), "arm-width overall", None),
        ("*Front", ("shaft", "pivot"), "shaft-to-handle-pivot location", None),
        ("*Front", ("side_c", "pivot"), "handle-pivot transverse location", "vertical"),
        ("*Front", ("side_c", "dimple"), "dimple transverse location from datum C", "vertical"),
        ("*Top", ("station_a", "pin"), "cross-hole station from datum A", "vertical"),
    ]
    for (args, kw), (view, roles, label, orientation) in zip(
        scene.calls["add_entity_dimension"], expected, strict=True
    ):
        assert args == (scene.adapter, scene.views[view])
        assert kw["entities"] == tuple(scene.banks[0][role] for role in roles)
        assert kw["label"] == label
        assert kw.get("orientation") == orientation
    dims = scene.dimensions
    assert [args[1] for args, _ in scene.calls["set_arc_endpoints_to_center"]] == dims[1:]
    assert [args[1] for args, _ in scene.calls["set_basic_dimension"]] == [dims[1], dims[2], dims[4]]
    # Preserve the native baseline station (z=0), without pretending datum A is z=0.
    assert recipe.ENTITY_ROLES["station_a"].edge.point_mm[2] == 0
    assert recipe.ENTITY_ROLES["datum_a"].edge.point_mm[2] == spec.ARM_THICKNESS


def test_recipe_annotations_use_owned_handles_and_model_finish_context(scene):
    scene.run()
    bank = scene.banks[0]
    datums = scene.calls["add_datum_feature"]
    assert [(args[1].orientation, kw["datum"], kw["entity"]) for args, kw in datums] == [
        ("*Right", "A", bank["datum_a"]), ("*Front", "B", bank["shaft"]),
        ("*Front", "C", bank["side_c"]),
    ]
    assert datums[1][1]["shoulder"] is True
    assert "symbol_xy" not in datums[1][1]
    frames = scene.calls["add_feature_control_frame"]
    assert [(args[1].orientation, kw["entity"], kw["characteristic"], kw["tolerance"],
             kw["datums"], kw.get("diameter", False)) for args, kw in frames] == [
        ("*Top", bank["pin"], "position", "0.20", ("A", "B"), True),
        ("*Front", bank["pivot"], "position", "0.20", ("A", "B", "C"), True),
        ("*Right", bank["opposite_a"], "parallelism", "0.10", ("A",), False),
    ]
    assert [(args[1].orientation, kw["edge"], kw["label"]) for args, kw in
            scene.calls["add_native_hole_callout"]] == [
        ("*Top", bank["pin"], "crank-arm cross-hole"),
        ("*Front", bank["pivot"], "handle pivot hole"),
    ]
    (args, kw), = scene.calls["add_surface_finish"]
    assert "symbol_xy" not in kw
    assert "leader_attach_xy" not in kw
    assert args == (scene.adapter, scene.views["*Front"])
    assert kw["entity"] is bank["shaft"]
    assert kw["entity_context"] is recipe.AnnotationEntityContext.MODEL
    assert kw["control"] == recipe.surface_finish_by_key(spec.SURFACE_FINISHES, "shaft_bore")
    assert [args[1] for args, _ in scene.calls["add_property_linked_note"]] == [
        "Manufacturing Notes", "Isometric View Note"
    ]


@pytest.mark.parametrize("z", [0.0, 0.0042, -0.0021])
def test_finish_move_preserves_native_z_and_revalidates_exact_attachment(scene, z):
    scene.finish_annotation.GetPosition.return_value = (0.123, 0.456, z)
    scene.run()
    scene.finish.GetAnnotation.assert_called_once_with()
    scene.finish_annotation.GetPosition.assert_called_once_with()
    scene.finish_annotation.SetPosition2.assert_called_once_with(
        recipe._sheet_x(spec.SHAFT_BORE_DIA * 3.0**0.5 / 4.0),
        recipe.FRONT_CENTER[1] + spec.SHAFT_BORE_DIA * recipe.SHEET_SCALE[0] / 4000,
        z,
    )
    scene.drawing.EditRebuild3.assert_called_once_with()
    (args, kwargs), = scene.calls["_validate_explicit_annotation_attachment"]
    assert len(args) == 4
    assert all(actual is expected for actual, expected in zip(args, (
        scene.adapter, scene.finish_annotation, scene.views["*Front"], scene.banks[0]["shaft"]
    ), strict=True))
    assert kwargs == {"entity_type": "EDGE", "entity_context": recipe.AnnotationEntityContext.MODEL,
                      "label": "shaft bore finish"}
    start = scene.events.index("add_surface_finish")
    assert scene.events[start:start + 6] == [
        "add_surface_finish", "finish.GetAnnotation", "finish.GetPosition",
        "finish.SetPosition2", "drawing.EditRebuild3", "_validate_explicit_annotation_attachment",
    ]


@pytest.mark.parametrize("position", [None, (), (0.1, 0.2), (0.1, 0.2, 0.3, 0.4)])
def test_invalid_finish_position_fails_before_mutation_and_finalize(scene, position):
    scene.finish_annotation.GetPosition.return_value = position
    with pytest.raises(RuntimeError, match="invalid native symbol position"):
        scene.run()
    scene.finish_annotation.SetPosition2.assert_not_called()
    scene.drawing.EditRebuild3.assert_not_called()
    assert "_validate_explicit_annotation_attachment" not in scene.events
    assert "finalize" not in scene.events


@pytest.mark.parametrize("fault", ["source", "configuration", "view", "active_document"])
def test_finish_rechecks_source_context_immediately_before_position_mutation(scene, fault):
    def corrupt():
        if fault == "source":
            scene.app.GetOpenDocumentByName.return_value = object()
        if fault == "configuration":
            scene.source.ConfigurationManager.ActiveConfiguration.Name = "Other"
        if fault == "view":
            scene.views["*Front"].ReferencedDocument = object()
        if fault == "active_document":
            scene.app.ActiveDoc = scene.source
    scene.hooks["finish.GetPosition"] = corrupt
    with pytest.raises(RuntimeError, match=r"source|context"):
        scene.run()
    scene.finish_annotation.GetPosition.assert_called_once_with()
    scene.finish_annotation.SetPosition2.assert_not_called()
    scene.drawing.EditRebuild3.assert_not_called()
    assert "finalize" not in scene.events


def test_failed_finish_move_does_not_rebuild_validate_or_finalize(scene):
    scene.finish_annotation.SetPosition2.return_value = False
    with pytest.raises(RuntimeError, match="native symbol move failed"):
        scene.run()
    scene.finish_annotation.SetPosition2.assert_called_once()
    scene.drawing.EditRebuild3.assert_not_called()
    assert "_validate_explicit_annotation_attachment" not in scene.events
    assert "finalize" not in scene.events


@pytest.mark.parametrize("fault", ["source", "configuration", "view", "active_document"])
def test_finish_rechecks_context_after_move_before_rebuilding(scene, fault):
    def corrupt():
        if fault == "source":
            scene.app.GetOpenDocumentByName.return_value = object()
        if fault == "configuration":
            scene.source.ConfigurationManager.ActiveConfiguration.Name = "Other"
        if fault == "view":
            scene.views["*Front"].ReferencedDocument = object()
        if fault == "active_document":
            scene.app.ActiveDoc = scene.source
    scene.hooks["finish.SetPosition2"] = corrupt
    with pytest.raises(RuntimeError, match=r"source|context"):
        scene.run()
    scene.finish_annotation.SetPosition2.assert_called_once()
    scene.drawing.EditRebuild3.assert_not_called()
    assert "_validate_explicit_annotation_attachment" not in scene.events
    assert "finalize" not in scene.events


def test_finish_attachment_validation_failure_stops_before_notes_or_finalize(scene):
    failure = RuntimeError("shaft bore finish: changed exact attachment")

    def reject():
        raise failure

    scene.hooks["_validate_explicit_annotation_attachment"] = reject
    with pytest.raises(RuntimeError) as raised:
        scene.run()
    assert raised.value is failure
    scene.finish_annotation.SetPosition2.assert_called_once()
    scene.drawing.EditRebuild3.assert_called_once()
    assert "add_property_linked_note" not in scene.events
    assert "finalize" not in scene.events


@pytest.mark.parametrize("fault", ["path", "kind", "configuration", "extra_configuration", "replaced", "inactive"])
def test_actual_recipe_rejects_wrong_source_before_resolution_or_insertion(scene, fault):
    def corrupt():
        if fault == "path":
            scene.source.GetPathName.return_value += ".wrong"
        if fault == "kind":
            scene.source.GetType.return_value = 2
        if fault == "configuration":
            scene.source.ConfigurationManager.ActiveConfiguration.Name = "Other"
        if fault == "extra_configuration":
            scene.source.GetConfigurationNames.return_value = ("Default", "Other")
        if fault == "replaced":
            scene.app.GetOpenDocumentByName.return_value = object()
        if fault == "inactive":
            scene.app.ActiveDoc = object()
    scene.hooks["open"] = corrupt
    with pytest.raises(RuntimeError, match="source"):
        scene.run()
    assert scene.events == ["open"]


@pytest.mark.parametrize("phase", ["resolve", "view"])
def test_recipe_rechecks_source_identity_after_resolution_and_view_creation(scene, phase):
    scene.hooks[phase] = lambda: setattr(scene.app.GetOpenDocumentByName, "return_value", object())
    with pytest.raises(RuntimeError, match="exact source part"):
        scene.run()
    assert "add_entity_dimension" not in scene.events
    if phase == "resolve":
        assert "factory" not in scene.events


@pytest.mark.parametrize("fault", ["view_source", "view_configuration", "current_document", "active_document"])
def test_recipe_rejects_wrong_drawing_or_view_before_annotations(scene, fault):
    def corrupt():
        view = list(scene.views.values())[-1]
        if fault == "view_source":
            view.ReferencedDocument = object()
        if fault == "view_configuration":
            view.ReferencedConfiguration = "Other"
        if fault == "current_document":
            scene.adapter.currentModel = scene.source
        if fault == "active_document":
            scene.app.ActiveDoc = scene.source
    scene.hooks["view"] = corrupt
    with pytest.raises(RuntimeError, match="wrong drawing/view/source context"):
        scene.run()
    assert "curate_view_dimensions" not in scene.events
    assert "add_entity_dimension" not in scene.events
    assert "finalize" not in scene.events


@pytest.mark.parametrize("fault", ["source_configuration", "source_replaced", "drawing_replaced"])
def test_recipe_revalidates_context_between_entity_insertions(scene, fault):
    def corrupt():
        if fault == "source_configuration":
            scene.source.ConfigurationManager.ActiveConfiguration.Name = "Other"
        if fault == "source_replaced":
            scene.app.GetOpenDocumentByName.return_value = object()
        if fault == "drawing_replaced":
            scene.app.ActiveDoc = object()
    scene.hooks["add_entity_dimension"] = corrupt
    with pytest.raises(RuntimeError, match=r"source|context"):
        scene.run()
    assert len(scene.calls["add_entity_dimension"]) == 1
    assert "add_datum_feature" not in scene.events
    assert "finalize" not in scene.events


@pytest.mark.parametrize("count", [0, 2])
def test_unresolved_or_ambiguous_bank_fails_before_drawing_insertion(scene, count):
    def reject():
        raise RuntimeError(f"shaft matched {count} edges")
    scene.hooks["resolve"] = reject
    with pytest.raises(RuntimeError, match=f"shaft matched {count} edges"):
        scene.run()
    assert "factory" not in scene.events


@pytest.fixture
def topology(monkeypatch):
    """Native-shaped topology exercises the actual resolver and recipe selectors."""
    monkeypatch.setattr(native, "_early_bound", lambda obj, _kind: obj)
    monkeypatch.setattr(native, "_face_geometry", lambda face: SimpleNamespace(face=face, spec=face.spec))
    monkeypatch.setattr(native, "_face_matches", lambda geometry, selector: geometry.spec == selector)
    faces, features, edges = {}, {}, {}
    for role, boundary in recipe.ENTITY_ROLES.items():
        assert isinstance(boundary, native.FaceBoundary)
        owned = boundary.face
        if owned not in faces:
            face = SimpleNamespace(spec=owned.face, GetEdges=Mock(return_value=[]))
            faces[owned] = face
            feature = features.setdefault(owned.feature_name, SimpleNamespace(GetFaces=Mock(return_value=[])))
            feature.GetFaces.return_value.append(face)
        selector = boundary.edge
        if isinstance(selector, native.CircleEdge):
            curve = SimpleNamespace(IsCircle=lambda: True, IsLine=lambda: False,
                CircleParams=(*(v / 1000 for v in selector.center_mm), *selector.axis, selector.radius_mm / 1000))
            edge = SimpleNamespace(GetCurve=lambda curve=curve: curve)
        else:
            assert isinstance(selector, native.LineEdge)
            curve = SimpleNamespace(IsCircle=lambda: False, IsLine=lambda: True)
            start = tuple((p - d) / 1000 for p, d in zip(selector.point_mm, selector.direction, strict=True))
            end = tuple((p + d) / 1000 for p, d in zip(selector.point_mm, selector.direction, strict=True))
            edge = SimpleNamespace(GetCurve=lambda curve=curve: curve,
                GetStartVertex=lambda point=start: SimpleNamespace(GetPoint=lambda: point),
                GetEndVertex=lambda point=end: SimpleNamespace(GetPoint=lambda: point))
        faces[owned].GetEdges.return_value.append(edge)
        edges[role] = edge
    model = SimpleNamespace(FeatureByName=Mock(side_effect=features.get), GetBodies2=forbidden)
    return SimpleNamespace(model=model, faces=faces, features=features, edges=edges)


def test_actual_role_map_resolves_exact_owned_edges_without_body_scan(topology):
    actual = native.ModelEntities(topology.model).resolve(recipe.ENTITY_ROLES)
    assert actual.keys() == topology.edges.keys()
    assert all(actual[role] is edge for role, edge in topology.edges.items())
    assert topology.model.FeatureByName.call_count == len(topology.features)
    for feature in topology.features.values():
        feature.GetFaces.assert_called_once_with()


@pytest.mark.parametrize("fault", ["missing_feature", "missing_face", "ambiguous_face", "missing_edge", "ambiguous_edge"])
def test_actual_recipe_roles_fail_on_missing_or_ambiguous_topology(topology, fault):
    feature = topology.features["ShaftBore"]
    face = topology.faces[recipe.ENTITY_ROLES["shaft"].face]
    if fault == "missing_feature":
        del topology.features["ShaftBore"]
    if fault == "missing_face":
        feature.GetFaces.return_value = []
    if fault == "ambiguous_face":
        feature.GetFaces.return_value *= 2
    if fault == "missing_edge":
        face.GetEdges.return_value = []
    if fault == "ambiguous_edge":
        face.GetEdges.return_value *= 2
    with pytest.raises(RuntimeError, match=r"ShaftBore|shaft"):
        native.ModelEntities(topology.model).resolve(recipe.ENTITY_ROLES)
