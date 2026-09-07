from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from diagnostics import _silhouette_attachment_witness as witness


@pytest.fixture(autouse=True)
def early_bound(monkeypatch):
    monkeypatch.setattr(witness, "_early_bound", lambda obj, interface: obj)


def fixture():
    view = object()
    surface = NS(Identity=lambda: 4002, CylinderParams=(0, 0, 0, 0, 0, 1, .003))
    face = NS(GetSurface=lambda: surface)
    curve = NS(IsLine=lambda: True, IsCircle=lambda: False, LineParams=(.003, 0, 0, 0, 0, 1))
    entity = NS(
        GetView=lambda: view,
        GetFace=lambda: face,
        GetCurve=lambda: curve,
        GetStartPoint=lambda: NS(ArrayData=(.003, 0, 0)),
        GetEndPoint=lambda: NS(ArrayData=(.003, 0, .1)),
    )
    app = NS(IsSame=lambda left, right: int(left is right))
    return app, view, entity, face, surface, curve


def test_line_native_values_and_identity_are_retained():
    app, view, entity, face, surface, curve = fixture()
    evidence = {}
    result = witness.require_same(app, view, entity, entity, label="finish", evidence=evidence)
    assert result["start"] == (.003, 0, 0)
    assert result["end"] == (.003, 0, .1)
    assert result["face_surface"]["parameters"] == surface.CylinderParams
    assert result["curve_parameters"] == curve.LineParams
    assert evidence["expected"] == evidence["actual"] == result


@pytest.mark.parametrize("code", [0, -1, 2])
def test_equal_geometry_wrong_or_unknown_identity_rejected(code):
    app, view, entity, *_ = fixture()
    substitute = NS(**vars(entity))
    app.IsSame = lambda left, right: 1 if left is right else code
    evidence = {}
    with pytest.raises(RuntimeError, match="silhouette entity"):
        witness.require_same(app, view, entity, substitute, label="finish", evidence=evidence)
    assert evidence["expected"] == evidence["actual"]


def test_same_entity_but_substituted_equal_surface_face_rejected():
    app, view, entity, face, *_ = fixture()
    entity.GetFace = Mock(side_effect=[face, NS(**vars(face))])
    with pytest.raises(RuntimeError, match="silhouette face"):
        witness.require_same(app, view, entity, entity, label="finish", evidence={})


def test_wrong_view_rejected():
    app, _, entity, *_ = fixture()
    with pytest.raises(RuntimeError, match="owning view"):
        witness.snapshot(app, object(), entity)


@pytest.mark.parametrize("field", ["GetFace", "GetCurve", "GetStartPoint", "GetEndPoint"])
def test_null_native_objects_rejected(field):
    app, view, entity, *_ = fixture()
    setattr(entity, field, lambda: None)
    with pytest.raises(RuntimeError, match="null"):
        witness.snapshot(app, view, entity)


@pytest.mark.parametrize("raw", [None, (), (1, 2), (1, 2, 3, 4), (True, 0, 0), ("1", 0, 0), (float("nan"), 0, 0), (float("inf"), 0, 0)])
def test_bad_endpoint_array_rejected(raw):
    app, view, entity, *_ = fixture()
    entity.GetEndPoint = lambda: NS(ArrayData=raw)
    with pytest.raises(RuntimeError, match="native"):
        witness.snapshot(app, view, entity)


@pytest.mark.parametrize("field", ["LineParams", "CylinderParams"])
@pytest.mark.parametrize("raw", [None, (), (0,) * 8, (float("nan"),) * 7])
def test_successful_bad_parameter_arrays_rejected(field, raw):
    app, view, entity, _, surface, curve = fixture()
    setattr(curve if field == "LineParams" else surface, field, raw)
    with pytest.raises(RuntimeError, match="native"):
        witness.snapshot(app, view, entity)


def test_unsupported_surface_or_curve_is_not_silently_excluded():
    app, view, entity, _, surface, curve = fixture()
    surface.Identity = lambda: 4007
    with pytest.raises(RuntimeError, match="unsupported silhouette surface"):
        witness.snapshot(app, view, entity)
    surface.Identity = lambda: 4002
    curve.IsLine = lambda: False
    with pytest.raises(RuntimeError, match="unsupported.*curve"):
        witness.snapshot(app, view, entity)


def test_circle_and_plane_supported_without_inventing_arc_trim():
    app, view, entity, _, surface, curve = fixture()
    surface.Identity = lambda: 4001
    surface.PlaneParams = (0, 0, 1, 0, 0, 0)
    curve.IsLine = lambda: False
    curve.IsCircle = lambda: True
    curve.CircleParams = (0, 0, 0, 0, 0, 1, .003)
    entity.GetEndPoint = entity.GetStartPoint
    result, _ = witness.snapshot(app, view, entity)
    assert result["curve_kind"] == "circle"
    assert set(result) == {"curve_kind", "curve_parameters", "start", "end", "face_surface"}


def test_raw_arithmetic_change_is_enumerable_not_rounded_away():
    app, view, entity, *_ = fixture()
    entity.GetEndPoint = Mock(side_effect=[NS(ArrayData=(.003, 0, .1)), NS(ArrayData=(.003, 0, .10000000000000002))])
    evidence = {}
    with pytest.raises(RuntimeError, match="raw geometry changed"):
        witness.require_same(app, view, entity, entity, label="finish", evidence=evidence)
    assert evidence["expected"]["end"] != evidence["actual"]["end"]
