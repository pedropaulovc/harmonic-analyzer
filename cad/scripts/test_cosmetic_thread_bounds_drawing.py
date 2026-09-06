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
    monkeypatch.setattr(bounds, "_thread_line_width", lambda extension: 0.00018)
    snapshot = bounds._native_snapshot(annotation(data), object())
    result = bounds.bounds_from_snapshot(snapshot)
    assert result.body.bounds == pytest.approx(expected)
    assert result.envelope == result.body
    assert result.anchor == pytest.approx(
        ((expected[0] + expected[2]) / 2, (expected[1] + expected[3]) / 2)
    )
    assert all(line.width_m == 0.00018 for line in result.native_strokes)


def test_empty_thread_data_does_not_prove_zero_ink(monkeypatch):
    monkeypatch.setattr(bounds, "_thread_line_width", lambda extension: 0.00018)
    with pytest.raises(ValueError):
        bounds._native_snapshot(annotation(native_data()), object())


@pytest.mark.parametrize("weight,preference", [(0, 100), (3, 103), (10, 901)])
def test_native_thread_weight_uses_actual_standard_or_custom_preference(
    monkeypatch, weight, preference
):
    monkeypatch.setattr(
        bounds,
        "_installed_swconst",
        lambda: SimpleNamespace(
            swLineFontCosmeticThreadThickness=900,
            swLineFontCosmeticThreadThicknessCustom=901,
        ),
    )
    monkeypatch.setattr(
        bounds, "_line_weight_preferences", lambda: tuple(range(100, 108))
    )
    calls = []
    extension = SimpleNamespace(
        GetUserPreferenceInteger=lambda key, option: weight,
        GetUserPreferenceDouble=lambda key, option: (
            calls.append((key, option)) or 0.00018
        ),
    )
    assert bounds._thread_line_width(extension) == 0.00018
    assert calls == [(preference, 0)]


@pytest.mark.parametrize(
    "weight,width", [(9, 0.00018), (-1, 0.00018), (0, 0), (0, float("nan"))]
)
def test_unknown_thread_weight_or_invalid_width_fails(monkeypatch, weight, width):
    monkeypatch.setattr(
        bounds,
        "_installed_swconst",
        lambda: SimpleNamespace(
            swLineFontCosmeticThreadThickness=900,
            swLineFontCosmeticThreadThicknessCustom=901,
        ),
    )
    monkeypatch.setattr(
        bounds, "_line_weight_preferences", lambda: tuple(range(100, 108))
    )
    extension = SimpleNamespace(
        GetUserPreferenceInteger=lambda key, option: weight,
        GetUserPreferenceDouble=lambda key, option: width,
    )
    with pytest.raises(ValueError):
        bounds._thread_line_width(extension)
