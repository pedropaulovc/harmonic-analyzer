"""Semantic drawing attachments must survive layout changes and fail on ambiguity."""

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from _drawing_entities import CircleEdge, EdgeAdjacentFace, FaceBoundary, FeatureFace, LineEdge, ModelEntities, ModelVertex
from _gtol_spec import CylinderFace, PlanarFace


@pytest.mark.parametrize("name", ["cone_pivot_screw", "cone_gear", "arbor_pedestal", "channel_lever", "rocker_arm", "pen_v_block", "pen_marker"])
def test_migrated_native_annotations_leave_placement_to_solidworks(name):
    tree = ast.parse(Path(__file__).with_name(f"draw_{name}.py").read_text(encoding="utf-8"))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name)
             and node.func.id in {"add_datum_feature", "add_feature_control_frame", "add_surface_finish"}]
    assert calls
    for call in calls:
        keywords = {keyword.arg for keyword in call.keywords}
        assert "entity" in keywords
        assert not keywords.intersection({"edge_xy", "symbol_xy", "frame_xy", "leader_attach_xy", "selection_point_xy", "position_tolerance_m"})


def circle(center, radius, axis=(0.0, 0.0, 1.0)):
    curve = SimpleNamespace(
        IsCircle=lambda: True,
        IsLine=lambda: False,
        CircleParams=(*[v / 1000 for v in center], *axis, radius / 1000),
    )
    return SimpleNamespace(GetCurve=lambda: curve)


def line(start, end):
    curve = SimpleNamespace(IsCircle=lambda: False, IsLine=lambda: True)
    def vertex(point):
        return SimpleNamespace(GetPoint=lambda: tuple(v / 1000 for v in point))
    return SimpleNamespace(
        GetCurve=lambda: curve,
        GetStartVertex=lambda: vertex(start),
        GetEndVertex=lambda: vertex(end),
    )


def resolver(monkeypatch, edges):
    monkeypatch.setattr("_drawing_entities._early_bound", lambda obj, _interface: obj)
    scan = Mock(return_value=edges)
    model = SimpleNamespace(GetBodies2=lambda *_args: (SimpleNamespace(GetEdges=scan),))
    return ModelEntities(model), scan


@pytest.mark.parametrize("position,scale", [((0.1, 0.2), 1), ((0.3, 0.07), 0.5), ((0.05, 0.08), 6)])
def test_bore_identity_is_independent_of_view_translation_and_scale(monkeypatch, position, scale):
    bore = circle((0, 0, 0), 4.7625)
    # Equal diameter elsewhere, back rim, and a coaxial gear outline are distractors.
    distractors = [circle((20, 0, 0), 4.7625), circle((0, 0, 6.5), 4.7625), circle((0, 0, 0), 31)]
    entities, _ = resolver(monkeypatch, [*distractors, bore])
    resolved = entities.resolve({"bore": CircleEdge(4.7625, (0, 0, 0), (0, 0, 1))})
    view = SimpleNamespace(Position=position, ScaleDecimal=scale, SelectEntity=Mock(return_value=True))
    assert view.SelectEntity(resolved["bore"], False)
    assert view.SelectEntity.call_args.args[0] is bore


def test_resolve_all_roles_with_one_model_topology_scan(monkeypatch):
    ends = [circle((0, y, 0), r, (0, 1, 0)) for y, r in [(0, 5), (-7, 3), (-12, 2)]]
    entities, scan = resolver(monkeypatch, ends)
    actual = entities.resolve({
        "head": CircleEdge(5, (0, 0, 0), (0, 1, 0)),
        "shoulder": CircleEdge(3, (0, -7, 0), (0, 1, 0)),
        "thread": CircleEdge(2, (0, -12, 0), (0, 1, 0)),
    })
    assert tuple(actual.values()) == tuple(ends)
    assert scan.call_count == 1


@pytest.mark.parametrize("edges", [[], [circle((0, 0, 0), 5)], [circle((0, 0, 0), 4), circle((0, 0, 0), 4)]])
def test_missing_wrong_and_ambiguous_edges_fail_instead_of_picking_nearest(monkeypatch, edges):
    entities, _ = resolver(monkeypatch, edges)
    with pytest.raises(RuntimeError, match="bore.*matched (0|2) edges"):
        entities.resolve({"bore": CircleEdge(4, (0, 0, 0), (0, 0, 1))})


def test_line_requires_finite_segment_not_its_infinite_extension(monkeypatch):
    wanted = line((10, 5, 0), (20, 5, 0))
    entities, _ = resolver(monkeypatch, [line((-20, 5, 0), (-10, 5, 0)), wanted])
    assert entities.resolve({"flange": LineEdge((15, 5, 0), (1, 0, 0))})["flange"] is wanted


def test_axis_direction_is_unoriented_but_wrong_axis_is_rejected(monkeypatch):
    wanted = circle((0, 0, 0), 4, (0, 0, -1))
    entities, _ = resolver(monkeypatch, [circle((0, 0, 0), 4, (0, 1, 0)), wanted])
    assert entities.resolve({"bore": CircleEdge(4, (0, 0, 0), (0, 0, 1))})["bore"] is wanted


@pytest.mark.parametrize("points,count", [([(0, 0, 0), (0, 110, 0)], 1), ([(0, 1, 0)], 0), ([(0, 0, 0), (0, 0, 0)], 2)])
def test_apex_vertex_must_match_exactly_one_model_vertex(monkeypatch, points, count):
    monkeypatch.setattr("_drawing_entities._early_bound", lambda obj, _interface: obj)
    vertices = [SimpleNamespace(GetPoint=lambda point=point: tuple(v / 1000 for v in point)) for point in points]
    body = SimpleNamespace(GetVertices=Mock(return_value=vertices))
    entities = ModelEntities(SimpleNamespace(GetBodies2=lambda *_args: (body,)))
    if count != 1:
        with pytest.raises(RuntimeError, match=f"apex.*matched {count} vertices"):
            entities.resolve({"apex": ModelVertex((0, 0, 0))})
        return
    assert entities.resolve({"apex": ModelVertex((0, 0, 0))})["apex"] is vertices[0]
    body.GetVertices.assert_called_once_with()


def feature_context(monkeypatch, face_specs):
    monkeypatch.setattr("_drawing_entities._early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr("_drawing_entities._face_geometry", lambda face: SimpleNamespace(face=face, spec=face.spec))
    monkeypatch.setattr("_drawing_entities._face_matches", lambda geometry, spec: geometry.spec == spec)
    faces = [SimpleNamespace(spec=spec) for spec in face_specs]
    feature = SimpleNamespace(GetFaces=Mock(return_value=faces))
    model = SimpleNamespace(FeatureByName=Mock(return_value=feature))
    return model, faces, feature


def test_named_feature_bounds_lookup_and_shared_face_is_read_once(monkeypatch):
    cylinder, plane = CylinderFace(9.525), PlanarFace((0, 0, -1), 0)
    model, faces, feature = feature_context(monkeypatch, [cylinder])
    rim = circle((0, 0, 0), 9.525 / 2)
    front_face = SimpleNamespace(spec=plane)
    rim.GetTwoAdjacentFaces2 = Mock(return_value=[faces[0], front_face])
    faces[0].GetEdges = Mock(return_value=[rim, circle((0, 0, 6.5), 9.525 / 2)])
    owned = FeatureFace("BoreCut", cylinder)
    boundary = FaceBoundary(owned, CircleEdge(9.525 / 2, (0, 0, 0), (0, 0, 1)))
    resolved = ModelEntities(model).resolve({"bore": boundary, "front": EdgeAdjacentFace(boundary, plane), "bore_face": owned})
    assert resolved == {"bore": rim, "front": front_face, "bore_face": faces[0]}
    # A gear's body-wide topology is deliberately absent from the mock. The
    # bore cut owns one cylinder and the requested face bounds only two rims.
    model.FeatureByName.assert_called_once_with("BoreCut")
    feature.GetFaces.assert_called_once_with()
    faces[0].GetEdges.assert_called_once_with()
    rim.GetTwoAdjacentFaces2.assert_called_once_with()


@pytest.mark.parametrize("face_specs", [[], [CylinderFace(12)], [CylinderFace(9.525), CylinderFace(9.525)]])
def test_feature_face_rejects_missing_wrong_and_ambiguous_ownership(monkeypatch, face_specs):
    model, _, _ = feature_context(monkeypatch, face_specs)
    with pytest.raises(RuntimeError, match="BoreCut.*matched (0|2) faces"):
        ModelEntities(model).resolve({"bore": FeatureFace("BoreCut", CylinderFace(9.525))})


def test_missing_named_feature_does_not_fall_back_to_global_geometry(monkeypatch):
    model, _, _ = feature_context(monkeypatch, [])
    model.FeatureByName.return_value = None
    with pytest.raises(RuntimeError, match="BoreCut.*missing"):
        ModelEntities(model).resolve({"bore": FeatureFace("BoreCut", CylinderFace(9.525))})


@pytest.mark.parametrize("edge_count", [0, 2])
def test_face_boundary_rejects_missing_or_ambiguous_rims(monkeypatch, edge_count):
    model, faces, _ = feature_context(monkeypatch, [CylinderFace(8)])
    faces[0].GetEdges = Mock(return_value=[circle((0, 0, 0), 4) for _ in range(edge_count)])
    spec = FaceBoundary(FeatureFace("BoreCut", CylinderFace(8)), CircleEdge(4, (0, 0, 0), (0, 0, 1)))
    with pytest.raises(RuntimeError, match=f"matched {edge_count} edges"):
        ModelEntities(model).resolve({"bore": spec})


def test_adjacent_face_does_not_accept_wrong_side_plane(monkeypatch):
    model, faces, _ = feature_context(monkeypatch, [CylinderFace(8)])
    rim = circle((0, 0, 0), 4)
    rim.GetTwoAdjacentFaces2 = lambda: [faces[0], SimpleNamespace(spec=PlanarFace((0, 0, 1), 0))]
    faces[0].GetEdges = lambda: [rim]
    boundary = FaceBoundary(FeatureFace("BoreCut", CylinderFace(8)), CircleEdge(4, (0, 0, 0), (0, 0, 1)))
    with pytest.raises(RuntimeError, match="matched 0 faces"):
        ModelEntities(model).resolve({"front": EdgeAdjacentFace(boundary, PlanarFace((0, 0, -1), 0))})


def dimension_context(monkeypatch):
    import _drawing_common as drawing

    model = Mock()
    view = SimpleNamespace(SelectEntity=Mock(return_value=True))
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(drawing, "view_name", lambda *_args: "Machining view")
    return drawing, SimpleNamespace(currentModel=model), view


@pytest.mark.parametrize("orientation,method", [
    ("smart", "AddDimension2"),
    ("horizontal", "AddHorizontalDimension2"),
    ("vertical", "AddVerticalDimension2"),
])
def test_entity_dimension_uses_selected_view_order_and_explicit_measurement_direction(monkeypatch, orientation, method):
    drawing, adapter, view = dimension_context(monkeypatch)
    first, second = object(), object()
    result = drawing.add_entity_dimension(
        adapter, view, entities=(first, second), text_xy=(0.12, 0.18),
        label="hole station", orientation=orientation,
    )
    model = adapter.currentModel
    model.ActivateView.assert_called_once_with("Machining view")
    assert [call.args for call in view.SelectEntity.call_args_list] == [(first, False), (second, True)]
    creator = getattr(model, method)
    creator.assert_called_once_with(0.12, 0.18, 0.0)
    assert result is creator.return_value
    model.EditRebuild3.assert_called_once_with()
    model.Extension.SelectByID2.assert_not_called()


@pytest.mark.parametrize("failure", ["view", "first_entity", "second_entity", "dimension"])
def test_entity_dimension_rejects_lost_view_selection_and_creation(monkeypatch, failure):
    drawing, adapter, view = dimension_context(monkeypatch)
    model = adapter.currentModel
    if failure == "view":
        model.ActivateView.return_value = False
    if failure == "first_entity":
        view.SelectEntity.side_effect = [False]
    if failure == "second_entity":
        view.SelectEntity.side_effect = [True, False]
    if failure == "dimension":
        model.AddDimension2.return_value = None
    with pytest.raises(RuntimeError, match="hole station"):
        drawing.add_entity_dimension(
            adapter, view, entities=(object(), object()), text_xy=(0.12, 0.18),
            label="hole station",
        )
    if failure != "dimension":
        model.AddDimension2.assert_not_called()
    model.EditRebuild3.assert_not_called()
