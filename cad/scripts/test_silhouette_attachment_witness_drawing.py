from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from diagnostics import _silhouette_attachment_witness as witness


@pytest.fixture(autouse=True)
def early_bound(monkeypatch):
    monkeypatch.setattr(witness, "_early_bound", lambda obj, interface: obj)
    monkeypatch.setattr(witness.persistent, "_early_bound", lambda obj, interface: obj)
    monkeypatch.setattr(witness.persistent, "byte_variant", lambda value: value)


def fixture():
    view = object()
    surface = NS(Identity=lambda: 4002, CylinderParams=(0, 0, 0, 0, 0, 1, 0.003))
    face = NS(GetSurface=lambda: surface)
    curve = NS(
        IsLine=lambda: True, IsCircle=lambda: False, LineParams=(0.003, 0, 0, 0, 0, 1)
    )
    entity = NS(
        persistent_ref=(1, 2, 3),
        GetView=lambda: view,
        GetFace=lambda: face,
        GetCurve=lambda: curve,
        GetStartPoint=lambda: NS(ArrayData=(0.003, 0, 0)),
        GetEndPoint=lambda: NS(ArrayData=(0.003, 0, 0.1)),
    )
    app = NS(IsSame=lambda left, right: int(left is right))
    app.drawing = NS(GetType=lambda: 3, Extension=NS(
        GetPersistReference3=lambda item: memoryview(bytes(item.persistent_ref)),
        IsSamePersistentID=lambda first, second: int(first == second),
    ))
    return app, view, entity, face, surface, curve


def test_line_native_values_and_identity_are_retained():
    app, view, entity, face, surface, curve = fixture()
    evidence = {}
    result = witness.require_same(
        app, view, entity, entity, drawing=app.drawing, label="finish", evidence=evidence
    )
    assert result["start"] == (0.003, 0, 0)
    assert result["end"] == (0.003, 0, 0.1)
    assert result["face_surface"]["parameters"] == surface.CylinderParams
    assert result["curve_parameters"] == curve.LineParams
    assert evidence["expected"] == evidence["actual"] == result


def test_native_distinct_silhouette_handles_with_same_drawing_pid_are_accepted():
    app, view, entity, *_ = fixture()
    selected = NS(**vars(entity))
    assert app.IsSame(entity, selected) == 0
    evidence = {}
    witness.require_same(app, view, entity, selected, drawing=app.drawing,
                         label="finish", evidence=evidence)
    assert evidence["persistent_identity"]["native_result"] == 1
    assert evidence["expected"] == evidence["actual"]


@pytest.mark.parametrize("code", [0, -1, 2])
def test_equal_geometry_wrong_or_unknown_identity_rejected(code):
    app, view, entity, *_ = fixture()
    substitute = NS(**vars(entity))
    app.IsSame = lambda left, right: 1 if left is right else code
    app.drawing.Extension.IsSamePersistentID = lambda *_: code
    evidence = {}
    with pytest.raises(RuntimeError, match="silhouette entity"):
        witness.require_same(
            app, view, entity, substitute, drawing=app.drawing, label="finish", evidence=evidence
        )
    assert evidence["expected"] == evidence["actual"]


def test_same_entity_but_substituted_equal_surface_face_rejected():
    app, view, entity, face, *_ = fixture()
    entity.GetFace = Mock(side_effect=[face, NS(**vars(face))])
    with pytest.raises(RuntimeError, match="silhouette face"):
        witness.require_same(app, view, entity, entity, drawing=app.drawing, label="finish", evidence={})


def test_rejected_identity_records_self_and_face_positive_controls():
    app, view, entity, *_ = fixture()
    substitute = NS(**vars(entity))
    app.drawing.Extension.IsSamePersistentID = lambda *_: 0
    evidence = {}
    with pytest.raises(RuntimeError, match="silhouette entity.*returned 0"):
        witness.require_same(
            app, view, entity, substitute, drawing=app.drawing, label="finish", evidence=evidence
        )
    assert evidence["identity_controls"] == {
        "expected_self": {"result": 1},
        "actual_self": {"result": 1},
        "reverse_pair": {"result": 0},
        "expected_face_self": {"result": 1},
        "actual_face_self": {"result": 1},
        "face_pair": {"result": 1},
    }


def test_self_identity_rejection_is_evidence_not_acceptance():
    app, view, entity, *_ = fixture()
    app.IsSame = lambda left, right: 1 if left is view and right is view else 0
    app.drawing.Extension.IsSamePersistentID = lambda *_: 0
    evidence = {}
    with pytest.raises(RuntimeError, match="silhouette entity.*returned 0"):
        witness.require_same(
            app, view, entity, entity, drawing=app.drawing, label="finish", evidence=evidence
        )
    assert all(row == {"result": 0} for row in evidence["identity_controls"].values())


def test_control_capture_error_never_replaces_original_identity_failure():
    app, view, entity, face, *_ = fixture()
    substitute = NS(**vars(entity))
    app.drawing.Extension.IsSamePersistentID = lambda *_: 0

    def is_same(left, right):
        if left is entity and right is substitute:
            return 0
        if left is view and right is view:
            return 1
        if left is face and right is face:
            return 1
        raise RuntimeError("native control read failed")

    app.IsSame = is_same
    evidence = {}
    with pytest.raises(RuntimeError, match="silhouette entity.*returned 0"):
        witness.require_same(
            app, view, entity, substitute, drawing=app.drawing, label="finish", evidence=evidence
        )
    assert "native control read failed" in evidence["identity_controls"]["expected_self"]["error"]
    assert evidence["identity_controls"]["face_pair"] == {"result": 1}


def test_wrong_view_rejected():
    app, _, entity, *_ = fixture()
    with pytest.raises(RuntimeError, match="owning view"):
        witness.snapshot(app, object(), entity)


@pytest.mark.parametrize(
    "field", ["GetFace", "GetCurve", "GetStartPoint", "GetEndPoint"]
)
def test_null_native_objects_rejected(field):
    app, view, entity, *_ = fixture()
    setattr(entity, field, lambda: None)
    with pytest.raises(RuntimeError, match="null"):
        witness.snapshot(app, view, entity)


@pytest.mark.parametrize(
    "raw",
    [
        None,
        (),
        (1, 2),
        (1, 2, 3, 4),
        (True, 0, 0),
        ("1", 0, 0),
        (float("nan"), 0, 0),
        (float("inf"), 0, 0),
    ],
)
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
    curve.CircleParams = (0, 0, 0, 0, 0, 1, 0.003)
    entity.GetEndPoint = entity.GetStartPoint
    result, _ = witness.snapshot(app, view, entity)
    assert result["curve_kind"] == "circle"
    assert set(result) == {
        "curve_kind",
        "curve_parameters",
        "start",
        "end",
        "face_surface",
    }


def test_raw_arithmetic_change_is_enumerable_not_rounded_away():
    app, view, entity, *_ = fixture()
    entity.GetEndPoint = Mock(
        side_effect=[
            NS(ArrayData=(0.003, 0, 0.1)),
            NS(ArrayData=(0.003, 0, 0.10000000000000002)),
        ]
    )
    evidence = {}
    with pytest.raises(RuntimeError, match="raw geometry changed"):
        witness.require_same(
            app, view, entity, entity, drawing=app.drawing, label="finish", evidence=evidence
        )
    assert evidence["expected"]["end"] != evidence["actual"]["end"]
