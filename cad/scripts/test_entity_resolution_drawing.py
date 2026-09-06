"""Semantic drawing attachments must survive layout changes and fail on ambiguity."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from _drawing_entities import CircleEdge, LineEdge, ModelEntities


def circle(center, radius, axis=(0.0, 0.0, 1.0)):
    curve = SimpleNamespace(
        IsCircle=lambda: True,
        IsLine=lambda: False,
        CircleParams=(*[v / 1000 for v in center], *axis, radius / 1000),
    )
    return SimpleNamespace(GetCurve=lambda: curve)


def line(start, end):
    curve = SimpleNamespace(IsCircle=lambda: False, IsLine=lambda: True)
    vertex = lambda point: SimpleNamespace(GetPoint=lambda: tuple(v / 1000 for v in point))
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
