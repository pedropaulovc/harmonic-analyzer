"""The trial reader uses the full reader's native parsers, without font work."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import _drawing_annotation_bounds as bounds


def native_annotation(monkeypatch):
    monkeypatch.setattr(bounds, "_early_bound", lambda value, _: value)
    circle = (
        -1,
        0,
        0,
        0,
        0.09175,
        0.15625,
        0,
        0.09175,
        0.15625,
        0,
        0.09,
        0.15625,
        0,
        0,
        0,
        1,
        1,
    )
    triangle = (0.15, 0.16, 0, 0.149, 0.159, 0, 0.149, 0.161, 0, 0, 0)
    arrow = (0.15, 0.16, 0, 1, 0, 0, 0.001, 0.002, 0, 0, 0, 0)
    polygon = (0, 0, 0, 0, 3, 0.15, 0.16, 0, 0.149, 0.159, 0, 0.149, 0.161, 0)
    data = SimpleNamespace(
        GetTextCount=Mock(return_value=0),
        GetLineCount=Mock(return_value=0),
        GetPolyLineCount=Mock(return_value=0),
        GetArcCount=lambda: 1,
        GetArcAtIndex2=lambda _: circle,
        GetTriangleCount=lambda: 1,
        GetTriangleAtIndex=lambda _: triangle,
        GetArrowHeadCount=lambda: 1,
        GetArrowHeadAtIndex2=lambda _: arrow,
        GetPolygonCount=lambda: 1,
        GetPolygonAtIndex=lambda _: polygon,
        GetEllipseCount=lambda: 0,
        GetParabolaCount=lambda: 0,
        GetPointCount=lambda: 0,
    )
    annotation = SimpleNamespace(
        GetType=lambda: 5,
        GetName=Mock(return_value="native-frame"),
        GetDisplayData=Mock(return_value=data),
        GetLeaderCount=lambda: 1,
        GetLeaderPointsAtIndex=lambda _: (
            0.1,
            0.15625,
            0,
            0.09,
            0.15625,
            0,
            0.15,
            0.16,
            0,
        ),
        GetLeaderAllAround=lambda: True,
        GetPosition=Mock(return_value=(0.1, 0.16, 0)),
        GetTextFormat=Mock(side_effect=AssertionError("trial measured font")),
    )
    return annotation, data


def test_narrow_reader_matches_full_native_geometry_and_skips_body_text(monkeypatch):
    annotation, data = native_annotation(monkeypatch)
    full = bounds._native_snapshot(annotation)
    for name in ("GetTextCount", "GetLineCount", "GetPolyLineCount"):
        getattr(data, name).reset_mock()
    annotation.GetPosition.reset_mock()
    annotation.GetDisplayData.reset_mock()
    result = bounds.annotation_leader_geometry(annotation)
    assert result.segments == full.leaders
    assert result.decorations == full.leader_boxes
    assert len(result.segments) == 2
    assert len(result.decorations) == 4
    for name in ("GetTextCount", "GetLineCount", "GetPolyLineCount"):
        getattr(data, name).assert_not_called()
    annotation.GetPosition.assert_not_called()
    annotation.GetTextFormat.assert_not_called()
    annotation.GetDisplayData.assert_called_once_with()


@pytest.mark.parametrize("reader", ["_native_snapshot", "annotation_leader_geometry"])
@pytest.mark.parametrize("count", [-1, 0.5, float("nan"), float("inf")])
def test_both_readers_reject_nonintegral_or_nonfinite_leader_counts(
    monkeypatch, reader, count
):
    annotation, _ = native_annotation(monkeypatch)
    annotation.GetLeaderCount = lambda: count
    with pytest.raises(ValueError, match="leader count"):
        getattr(bounds, reader)(annotation)


@pytest.mark.parametrize(
    "kind", ["Arc", "Triangle", "ArrowHead", "Polygon", "Ellipse", "Parabola", "Point"]
)
def test_trial_cannot_silently_drop_invalid_primitive_count(monkeypatch, kind):
    annotation, data = native_annotation(monkeypatch)
    setattr(data, f"Get{kind}Count", lambda: -0.5)
    with pytest.raises(ValueError, match="native primitive inventory"):
        bounds.annotation_leader_geometry(annotation)


@pytest.mark.parametrize("kind", ["Ellipse", "Parabola", "Point"])
def test_trial_rejects_unsupported_nonzero_primitives(monkeypatch, kind):
    annotation, data = native_annotation(monkeypatch)
    setattr(data, f"Get{kind}Count", lambda: 1)
    with pytest.raises(ValueError, match="native primitive inventory"):
        bounds.annotation_leader_geometry(annotation)


@pytest.mark.parametrize(
    "method,index",
    [
        ("GetArcAtIndex2", 4),
        ("GetTriangleAtIndex", 2),
        ("GetArrowHeadAtIndex2", 6),
        ("GetPolygonAtIndex", 7),
    ],
)
def test_trial_uses_same_finite_primitive_guards(monkeypatch, method, index):
    annotation, data = native_annotation(monkeypatch)
    values = list(getattr(data, method)(0))
    values[index] = float("nan")
    setattr(data, method, lambda _: values)
    with pytest.raises(ValueError):
        bounds.annotation_leader_geometry(annotation)


def test_trial_rejects_nonfinite_leader_xyz(monkeypatch):
    annotation, _ = native_annotation(monkeypatch)
    annotation.GetLeaderPointsAtIndex = lambda _: (
        0.1,
        0.15,
        0,
        0.2,
        0.15,
        float("nan"),
    )
    with pytest.raises(ValueError, match="leader XYZ"):
        bounds.annotation_leader_geometry(annotation)


@pytest.mark.parametrize("kind", [1, 2, 4, 6, 7, 13, 15])
def test_trial_reader_is_explicitly_scoped_to_native_gtols(monkeypatch, kind):
    annotation, _ = native_annotation(monkeypatch)
    annotation.GetType = lambda: kind
    with pytest.raises(ValueError, match="GTol"):
        bounds.annotation_leader_geometry(annotation)


def test_non_elbow_arc_is_not_reclassified_as_leader_decoration(monkeypatch):
    annotation, data = native_annotation(monkeypatch)
    before = bounds.annotation_leader_geometry(annotation)
    raw = list(data.GetArcAtIndex2(0))
    for index in (4, 7, 10):
        raw[index] += 0.01
    data.GetArcAtIndex2 = lambda _: raw
    after = bounds.annotation_leader_geometry(annotation)
    assert len(after.decorations) == len(before.decorations) - 1
    assert after.segments == before.segments
