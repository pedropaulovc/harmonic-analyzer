"""Call-count and ownership contracts for one-shot semantic entity batches."""

from collections import Counter
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import _drawing_entities as entities
from _gtol_spec import CylinderFace, PlanarFace


def circle(center=(0, 0, 0), radius=4):
    curve = SimpleNamespace(
        IsCircle=Mock(return_value=True), IsLine=Mock(return_value=False),
        CircleParams=(*(value / 1000 for value in center), 0, 0, 1, radius / 1000),
    )
    return SimpleNamespace(GetCurve=Mock(return_value=curve))


def line(start=(0, -5, 0), end=(10, -5, 0)):
    curve = SimpleNamespace(IsCircle=Mock(return_value=False), IsLine=Mock(return_value=True))
    return SimpleNamespace(
        GetCurve=Mock(return_value=curve),
        GetStartVertex=Mock(return_value=SimpleNamespace(GetPoint=Mock(return_value=tuple(v / 1000 for v in start)))),
        GetEndVertex=Mock(return_value=SimpleNamespace(GetPoint=Mock(return_value=tuple(v / 1000 for v in end)))),
    )


def face(spec, edges=()):
    return SimpleNamespace(spec=spec, GetEdges=Mock(return_value=list(edges)))


@pytest.fixture
def topology(monkeypatch):
    monkeypatch.setattr(entities, "_early_bound", lambda obj, _kind: obj)

    def geometry(native_face):
        if getattr(native_face, "spec", None) is None:
            return None
        return SimpleNamespace(face=native_face, spec=native_face.spec)

    decode = Mock(side_effect=geometry)
    monkeypatch.setattr(entities, "_face_geometry", decode)
    monkeypatch.setattr(entities, "_face_matches", lambda geometry, spec: geometry.spec == spec)
    features = {}
    model = SimpleNamespace(
        FeatureByName=Mock(side_effect=features.get),
        GetBodies2=Mock(side_effect=AssertionError("scoped requests must not scan bodies")),
    )

    def feature(name, faces):
        result = SimpleNamespace(GetFaces=Mock(return_value=list(faces)))
        features[name] = result
        return result

    return SimpleNamespace(model=model, features=features, feature=feature, decode=decode)


def test_distinct_face_selectors_batch_one_geometry_decode_per_feature_face(topology):
    specs = (CylinderFace(8), PlanarFace((0, 0, 1), 8), PlanarFace((0, 0, -1), 0))
    faces = [face(spec) for spec in specs]
    feature = topology.feature("Arm", faces)
    selectors = [entities.FeatureFace("Arm", spec) for spec in specs]
    result = entities.ModelEntities(topology.model).resolve({
        "bore": selectors[0], "front": selectors[1], "back": selectors[2],
        "front_alias": entities.FeatureFace("Arm", specs[1]),
    })
    assert all(result[key] is expected for key, expected in zip(
        ("bore", "front", "back", "front_alias"), (*faces, faces[1]), strict=True
    ))
    topology.model.FeatureByName.assert_called_once_with("Arm")
    feature.GetFaces.assert_called_once_with()
    assert Counter(id(call.args[0]) for call in topology.decode.call_args_list) == Counter(map(id, faces))


@pytest.mark.parametrize("order", ["circle_first", "line_first"])
def test_mixed_boundaries_batch_one_face_scan_and_one_curve_read(topology, order):
    rim, second, straight, distractor = circle(), circle((10, 0, 0), 2), line(), circle((15, 10, 0))
    owned_face = face(PlanarFace((0, 0, 1), 0), [rim, second, straight, distractor])
    topology.feature("Plate", [owned_face])
    owned = entities.FeatureFace("Plate", owned_face.spec)
    requests = [
        ("rim", entities.FaceBoundary(owned, entities.CircleEdge(4, (0, 0, 0), (0, 0, 1)))),
        ("second", entities.FaceBoundary(owned, entities.CircleEdge(2, (10, 0, 0), (0, 0, 1)))),
        ("side", entities.FaceBoundary(owned, entities.LineEdge((5, -5, 0), (1, 0, 0)))),
    ]
    if order == "line_first":
        requests.reverse()
    result = entities.ModelEntities(topology.model).resolve(dict(requests))
    assert result["rim"] is rim and result["second"] is second and result["side"] is straight
    owned_face.GetEdges.assert_called_once_with()
    for edge in (rim, second, straight, distractor):
        edge.GetCurve.assert_called_once_with()
    straight.GetStartVertex.assert_called_once_with()
    straight.GetEndVertex.assert_called_once_with()


def test_adjacency_discovers_hidden_boundary_before_later_direct_roles(topology):
    rim = circle()
    cylinder, front = face(CylinderFace(8), [rim]), face(PlanarFace((0, 0, -1), 0))
    topology.feature("Bore", [cylinder])
    rim.GetTwoAdjacentFaces2 = Mock(return_value=[None, cylinder, front])
    owned = entities.FeatureFace("Bore", cylinder.spec)
    boundary = entities.FaceBoundary(owned, entities.CircleEdge(4, (0, 0, 0), (0, 0, 1)))
    adjacency = entities.EdgeAdjacentFace(boundary, front.spec)
    result = entities.ModelEntities(topology.model).resolve({
        "front": adjacency, "rim": boundary, "cylinder": owned, "front_alias": adjacency,
    })
    assert result["front"] is result["front_alias"] is front
    assert result["rim"] is rim and result["cylinder"] is cylinder
    cylinder.GetEdges.assert_called_once_with()
    rim.GetCurve.assert_called_once_with()
    rim.GetTwoAdjacentFaces2.assert_called_once_with()


def test_equal_geometry_under_different_feature_owners_stays_separate(topology):
    rims = [circle(), circle()]
    for name, rim in zip(("First", "Second"), rims, strict=True):
        topology.feature(name, [face(CylinderFace(8), [rim])])
    result = entities.ModelEntities(topology.model).resolve({
        name: entities.FaceBoundary(entities.FeatureFace(name, CylinderFace(8)),
            entities.CircleEdge(4, (0, 0, 0), (0, 0, 1)))
        for name in ("First", "Second")
    })
    assert result["First"] is rims[0] and result["Second"] is rims[1]
    topology.model.GetBodies2.assert_not_called()


@pytest.mark.parametrize("fault", ["missing_feature", "missing_face", "ambiguous_face", "missing_edge", "ambiguous_edge"])
def test_batched_ownership_failures_never_return_partial_results_or_fallback(topology, fault):
    owned_face = face(CylinderFace(8), [circle()])
    feature = topology.feature("Bore", [owned_face])
    topology.feature("Good", [face(PlanarFace((0, 1, 0), 4))])
    if fault == "missing_feature":
        del topology.features["Bore"]
    if fault == "missing_face":
        feature.GetFaces.return_value = []
    if fault == "ambiguous_face":
        feature.GetFaces.return_value.append(face(CylinderFace(8)))
    if fault == "missing_edge":
        owned_face.GetEdges.return_value = []
    if fault == "ambiguous_edge":
        owned_face.GetEdges.return_value.append(circle())
    with pytest.raises(RuntimeError, match="Bore|matched [02] edges"):
        entities.ModelEntities(topology.model).resolve({
            "good": entities.FeatureFace("Good", PlanarFace((0, 1, 0), 4)),
            "bad": entities.FaceBoundary(entities.FeatureFace("Bore", CylinderFace(8)),
                entities.CircleEdge(4, (0, 0, 0), (0, 0, 1))),
        })
    topology.model.GetBodies2.assert_not_called()


@pytest.mark.parametrize("count", [0, 2])
def test_adjacent_face_missing_or_ambiguous_stays_fail_loud(topology, count):
    rim = circle()
    cylinder = face(CylinderFace(8), [rim])
    topology.feature("Bore", [cylinder])
    plane = PlanarFace((0, 0, -1), 0)
    rim.GetTwoAdjacentFaces2 = Mock(return_value=[None, cylinder, *[face(plane) for _ in range(count)]])
    boundary = entities.FaceBoundary(entities.FeatureFace("Bore", cylinder.spec),
        entities.CircleEdge(4, (0, 0, 0), (0, 0, 1)))
    with pytest.raises(RuntimeError, match=f"matched {count} faces"):
        entities.ModelEntities(topology.model).resolve({"front": entities.EdgeAdjacentFace(boundary, plane)})


def test_unsupported_geometry_and_null_line_endpoint_do_not_become_matches(topology):
    rim, straight = circle(), line()
    unsupported = SimpleNamespace(GetCurve=Mock(return_value=SimpleNamespace(
        IsCircle=lambda: False, IsLine=lambda: False)))
    no_endpoint = line()
    no_endpoint.GetEndVertex.return_value = None
    owned_face = face(PlanarFace((0, 0, 1), 0), [unsupported, no_endpoint, rim, straight])
    topology.feature("Plate", [face(None), owned_face])
    owned = entities.FeatureFace("Plate", owned_face.spec)
    result = entities.ModelEntities(topology.model).resolve({
        "rim": entities.FaceBoundary(owned, entities.CircleEdge(4, (0, 0, 0), (0, 0, 1))),
        "side": entities.FaceBoundary(owned, entities.LineEdge((5, -5, 0), (1, 0, 0))),
    })
    assert result["rim"] is rim and result["side"] is straight


def test_native_geometry_error_is_not_swallowed_or_replaced_by_fallback(topology):
    failure = RuntimeError("native GetCurve failed")
    rim = circle()
    rim.GetCurve.side_effect = failure
    topology.feature("Bore", [face(CylinderFace(8), [rim])])
    with pytest.raises(RuntimeError) as raised:
        entities.ModelEntities(topology.model).resolve({
            "rim": entities.FaceBoundary(entities.FeatureFace("Bore", CylinderFace(8)),
                entities.CircleEdge(4, (0, 0, 0), (0, 0, 1))),
        })
    assert raised.value is failure
    topology.model.GetBodies2.assert_not_called()


@pytest.mark.parametrize("first_result", ["success", "failure"])
def test_each_resolve_call_discards_prior_handles_and_partial_error_state(topology, first_result):
    old_rim, old_line = circle(), line()
    spec = PlanarFace((0, 0, 1), 0)
    feature = topology.feature("Plate", [face(spec, [old_rim, old_line] if first_result == "success" else [old_rim])])
    resolver = entities.ModelEntities(topology.model)
    owned = entities.FeatureFace("Plate", spec)
    requests = {
        "rim": entities.FaceBoundary(owned, entities.CircleEdge(4, (0, 0, 0), (0, 0, 1))),
        "side": entities.FaceBoundary(owned, entities.LineEdge((5, -5, 0), (1, 0, 0))),
    }
    if first_result == "success":
        first = resolver.resolve(requests)
        assert first["rim"] is old_rim and first["side"] is old_line
    if first_result == "failure":
        with pytest.raises(RuntimeError, match="matched 0 edges"):
            resolver.resolve(requests)
    new_rim, new_line = circle(), line()
    feature.GetFaces.return_value = [face(spec, [new_rim, new_line])]
    second = resolver.resolve(requests)
    assert second["rim"] is new_rim and second["side"] is new_line
    assert feature.GetFaces.call_count == 2
    assert topology.model.FeatureByName.call_count == 2
