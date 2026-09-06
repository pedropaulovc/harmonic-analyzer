"""Valid native cosmetic-thread ink is measured, never replaced by a face box."""

from types import SimpleNamespace

import pytest

import _drawing_annotation_bounds as bounds


def native_data(*, lines=(), arcs=(), polylines=()):
    rows = {
        "Line": (lines, "GetLineAtIndex3"),
        "Arc": (arcs, "GetArcAtIndex2"),
        "PolyLine": (polylines, "GetPolylineAtIndex2"),
    }
    methods = {
        f"Get{kind}Count": lambda: 0
        for kind in (
            "Text",
            "Ellipse",
            "Parabola",
            "Point",
            "Triangle",
            "ArrowHead",
            "Polygon",
        )
    }
    for kind, (values, getter) in rows.items():
        methods[f"Get{kind}Count"] = lambda values=values: len(values)
        methods[getter] = lambda index, values=values: values[index]
    return SimpleNamespace(**methods)


def annotation(data):
    return SimpleNamespace(
        Layer="",
        Width=0,
        GetType=lambda: 1,
        GetName=lambda: "Cosmetic Thread1",
        GetDisplayData=lambda: data,
        GetPosition=lambda: None,
        GetLeaderCount=lambda: 0,
    )


@pytest.mark.parametrize(
    "data,expected",
    [
        (
            native_data(
                lines=((0, 32, 1, 0, 0.17930152, 0.1652, 0, 0.17930152, 0.1172, 0),)
            ),
            (0.17921152, 0.11711, 0.17939152, 0.16529),
        ),
        (
            native_data(
                arcs=(
                    (
                        0,
                        32,
                        -1,
                        -1,
                        0.08069848,
                        0.15,
                        0,
                        0.08069848,
                        0.15,
                        0,
                        0.07,
                        0.15,
                        0,
                        0,
                        0,
                        1,
                        1,
                    ),
                )
            ),
            (0.05921152, 0.13921152, 0.08078848, 0.16078848),
        ),
        (
            # The native iso path carries depth as well as sheet XY. Projected
            # segments, not an invented 3-D circular/face box, bound the print.
            native_data(
                polylines=(
                    (
                        0,
                        0,
                        0,
                        32,
                        -1,
                        -1,
                        3,
                        0.37,
                        0.12,
                        -0.02,
                        0.38,
                        0.13,
                        -0.03,
                        0.39,
                        0.125,
                        -0.025,
                    ),
                )
            ),
            (0.36991, 0.11991, 0.39009, 0.13009),
        ),
    ],
)
def test_thread_lines_circle_and_projected_polyline_have_print_width(
    monkeypatch, data, expected
):
    monkeypatch.setattr(
        bounds, "_thread_line_width", lambda annotation, extension: 0.00018
    )
    snapshot = bounds._native_snapshot(annotation(data), object())
    result = bounds.bounds_from_snapshot(snapshot)
    assert result.body.bounds == pytest.approx(expected)
    assert result.envelope == result.body
    assert result.anchor == pytest.approx(
        ((expected[0] + expected[2]) / 2, (expected[1] + expected[3]) / 2)
    )
    assert all(line.width_m == 0.00018 for line in result.native_strokes)


def test_empty_thread_data_does_not_prove_zero_ink(monkeypatch):
    monkeypatch.setattr(
        bounds, "_thread_line_width", lambda annotation, extension: 0.00018
    )
    with pytest.raises(ValueError):
        bounds._native_snapshot(annotation(native_data()), object())


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
@pytest.mark.parametrize("coordinate", range(4, 10))
def test_thread_line_rejects_nonfinite_xyz_before_projection(
    monkeypatch, value, coordinate
):
    monkeypatch.setattr(
        bounds, "_thread_line_width", lambda annotation, extension: 0.00018
    )
    line = [0, 32, 1, 0, 0.1, 0.2, 0, 0.3, 0.4, 0]
    line[coordinate] = value
    with pytest.raises(ValueError, match="XYZ geometry must be finite"):
        bounds._native_snapshot(annotation(native_data(lines=(line,))), object())


@pytest.mark.parametrize("normal", [(float("nan"), 0, 1), (0, 0, 0)])
def test_thread_arc_requires_finite_nonzero_sheet_normal(monkeypatch, normal):
    monkeypatch.setattr(
        bounds, "_thread_line_width", lambda annotation, extension: 0.00018
    )
    arc = (0, 32, -1, -1, 0.08, 0.15, 0, 0.08, 0.15, 0, 0.07, 0.15, 0, *normal, 1)
    with pytest.raises(ValueError, match="normal geometry|drawing sheet plane"):
        bounds._native_snapshot(annotation(native_data(arcs=(arc,))), object())


@pytest.mark.parametrize("value", [-1, 1.5, float("nan"), float("inf")])
@pytest.mark.parametrize(
    "kind",
    [
        "Text",
        "Line",
        "Arc",
        "PolyLine",
        "Triangle",
        "ArrowHead",
        "Polygon",
        "Ellipse",
        "Parabola",
        "Point",
    ],
)
def test_native_primitive_counts_cannot_silently_drop_records(monkeypatch, value, kind):
    monkeypatch.setattr(
        bounds, "_thread_line_width", lambda annotation, extension: 0.00018
    )
    data = native_data(lines=((0, 32, 1, 0, 0.1, 0.2, 0, 0.3, 0.4, 0),))
    setattr(data, f"Get{kind}Count", lambda: value)
    with pytest.raises(ValueError, match="invalid.*count"):
        bounds._native_snapshot(annotation(data), object())


@pytest.mark.parametrize("count", [2.5, -1, float("nan")])
def test_polyline_embedded_count_cannot_truncate(monkeypatch, count):
    monkeypatch.setattr(
        bounds, "_thread_line_width", lambda annotation, extension: 0.00018
    )
    polyline = (0, 0, 0, 32, -1, -1, count, 0.1, 0.2, 0, 0.3, 0.4, 0)
    with pytest.raises(ValueError, match="integral point count"):
        bounds._native_snapshot(
            annotation(native_data(polylines=(polyline,))), object()
        )


@pytest.mark.parametrize("weight", range(8))
def test_native_thread_weight_uses_actual_annotation_not_document_default(
    monkeypatch, weight
):
    monkeypatch.setattr(
        bounds, "_line_weight_preferences", lambda: tuple(range(100, 108))
    )
    calls = []

    def forbidden_default(*_args):
        pytest.fail("document cosmetic defaults do not establish annotation width")

    extension = SimpleNamespace(
        GetUserPreferenceInteger=forbidden_default,
        GetUserPreferenceDouble=lambda key, option: (
            calls.append((key, option)) or 0.00018
        ),
    )
    actual = SimpleNamespace(Layer="", Width=weight)
    assert bounds._thread_line_width(actual, extension) == 0.00018
    assert calls == [(100 + weight, 0)]


@pytest.mark.parametrize(
    "weight,width",
    [
        (9, 0.00018),
        (-1, 0.00018),
        (8, 0.00018),
        (10, 0.00018),
        (1.5, 0.00018),
        (0, 0),
        (0, float("nan")),
        (0, float("inf")),
    ],
)
def test_unknown_thread_weight_or_invalid_width_fails(monkeypatch, weight, width):
    monkeypatch.setattr(
        bounds, "_line_weight_preferences", lambda: tuple(range(100, 108))
    )
    extension = SimpleNamespace(
        GetUserPreferenceDouble=lambda key, option: width,
    )
    with pytest.raises(ValueError):
        bounds._thread_line_width(SimpleNamespace(Layer="", Width=weight), extension)


@pytest.mark.parametrize("weight", [0, 7, 9, 10])
def test_layered_thread_does_not_silently_inherit_document_width(weight):
    actual = SimpleNamespace(Layer="Heavy threads", Width=weight)
    with pytest.raises(ValueError, match="layer"):
        bounds._thread_line_width(actual, object())


def test_snapshot_uses_annotation_width_instead_of_raw_line_or_document_default(
    monkeypatch,
):
    monkeypatch.setattr(
        bounds, "_line_weight_preferences", lambda: tuple(range(100, 108))
    )
    actual = annotation(native_data(lines=((0, 32, 1, 0, 0.1, 0.2, 0, 0.1, 0.3, 0),)))
    actual.Width = 3
    calls = []
    extension = SimpleNamespace(
        GetUserPreferenceDouble=lambda key, option: (
            calls.append((key, option)) or 0.0006
        ),
    )
    result = bounds.bounds_from_snapshot(bounds._native_snapshot(actual, extension))
    assert result.body.bounds == pytest.approx((0.0997, 0.1997, 0.1003, 0.3003))
    assert calls == [(103, 0)]
    assert result.native_strokes[0].width_m == 0.0006
