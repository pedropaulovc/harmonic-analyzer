"""Offline behavior of native construction ink; no outline or nominal-box oracle."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import math
from types import SimpleNamespace

import pytest

import _drawing_projection
from _supplier_reference_geometry import (
    NativeSketchGeometry,
    capture_native_sketch_geometry,
    native_sketch_view_bounds,
)


_IDENTITY = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
_LABEL = "supplier source ink"


class _Transform:
    def __init__(self, matrix=_IDENTITY, translation=(0.0, 0.0, 0.0), *, scale=1.0):
        self.matrix = matrix
        self.translation = translation
        self.scale = scale
        self.inverse = self
        self.inverse_calls = 0
        self.array_reads = 0

    @property
    def ArrayData(self):
        self.array_reads += 1
        # The fake applies column-vector math below; native ArrayData stores
        # the transpose for SOLIDWORKS row vectors, then translation and scale.
        rotation = tuple(
            self.matrix[axis][row] for row in range(3) for axis in range(3)
        )
        return rotation + tuple(self.translation) + (self.scale, 0.0, 0.0, 0.0)

    def Inverse(self):
        self.inverse_calls += 1
        return self.inverse

    def apply(self, xyz):
        return tuple(
            self.scale
            * sum(coefficient * value for coefficient, value in zip(row, xyz))
            + offset
            for row, offset in zip(self.matrix, self.translation)
        )


class _MathPoint:
    def __init__(self, xyz, utility):
        self.ArrayData = tuple(xyz)
        self.utility = utility

    def MultiplyTransform(self, transform):
        self.utility.products.append((self.ArrayData, transform))
        return _MathPoint(transform.apply(self.ArrayData), self.utility)


class _MathUtility:
    def __init__(self):
        self.products = []

    def CreatePoint(self, values):
        assert len(values) == 3
        return _MathPoint(values, self)


class _Sketch:
    def __init__(self, segments, transform):
        self.segments = segments
        self.ModelToSketchTransform = transform
        self.is_3d = False
        self.blocks = 0
        self.text = ()
        self.user_points = 0

    def GetSketchBlockInstanceCount(self):
        return self.blocks

    def GetSketchTextSegments(self):
        return self.text

    def GetUserPointsCount(self):
        return self.user_points

    def Is3D(self):
        return self.is_3d

    def GetSketchSegments(self):
        return self.segments


class _Line:
    ConstructionGeometry = True

    def __init__(self, start, end):
        self.start = _point(start)
        self.end = _point(end)

    def GetType(self):
        return 0  # swSketchLINE

    def GetStartPoint2(self):
        return self.start

    def GetEndPoint2(self):
        return self.end


class _Circle:
    ConstructionGeometry = True

    def __init__(self, center, radius):
        self.center = _point(center)
        self.radius = radius

    def GetType(self):
        return 1  # swSketchARC includes complete circles.

    def GetCenterPoint2(self):
        return self.center

    def GetRadius(self):
        return self.radius

    def IsCircle(self):
        return 1  # Native INT, not BOOL.

    def GetStartPoint2(self):
        pytest.fail("complete-circle bounds must not read endpoints")

    def GetEndPoint2(self):
        pytest.fail("complete-circle bounds must not read endpoints")

    def GetRotationDir(self):
        pytest.fail("complete-circle bounds must not read arc direction")


def _point(xyz):
    return SimpleNamespace(X=xyz[0], Y=xyz[1], Z=xyz[2])


def _unreadable(*_args):
    raise RuntimeError("native data unreadable")


@pytest.fixture
def scene(monkeypatch):
    # Replace only the COM SAFEARRAY boundary. The real native reader and
    # model_points_in_view perform every geometric step.
    monkeypatch.setattr(_drawing_projection, "double_array", tuple)

    def make(segments, *, source=None, projection=None):
        utility = _MathUtility()
        adapter = SimpleNamespace(swApp=SimpleNamespace(GetMathUtility=lambda: utility))
        sketch = _Sketch(segments, source if source is not None else _Transform())
        # Intentionally no GetOutline, Position, scale, configuration or cells.
        view = SimpleNamespace(
            ModelToViewTransform=projection if projection is not None else _Transform()
        )
        return SimpleNamespace(
            adapter=adapter, view=view, sketch=sketch, utility=utility
        )

    return make


def _bounds(scene):
    geometry = capture_native_sketch_geometry(scene.sketch, label=_LABEL)
    return native_sketch_view_bounds(scene.adapter, scene.view, geometry, label=_LABEL)


def _source_frame():
    # Model -> sketch is NOT sketch -> model, and neither is the view transform.
    forward = _Transform(
        ((0.0, 1.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
        (0.002, 0.004, -0.003),
    )
    inverse = _Transform(
        ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
        (0.004, -0.002, 0.003),
    )
    forward.inverse = inverse
    inverse.inverse = forward
    return forward


def _oblique_view():
    return _Transform(
        ((2.0, 1.0, 0.5), (-1.0, 3.0, -2.0), (0.0, 0.0, 1.0)),
        (0.1, -0.2, 0.0),
    )


@pytest.mark.parametrize(
    "view_scale,expected",
    [
        (1.0, (0.1045, -0.211, 0.1185, -0.204)),
        (2.0, (0.109, -0.222, 0.137, -0.208)),
    ],
)
def test_native_line_uses_source_inverse_then_distinct_view_transform(
    scene, view_scale, expected
):
    source, projection = _source_frame(), _oblique_view()
    projection.scale = view_scale
    native = scene(
        [_Line((0.001, 0.002, 0.0), (0.005, -0.003, 0.0))],
        source=source,
        projection=projection,
    )

    assert _bounds(native) == pytest.approx(expected)
    assert source.inverse_calls == 1
    assert source.inverse.array_reads == 1
    assert source.array_reads == 0
    model_inputs = [
        xyz for xyz, frame in native.utility.products if frame is projection
    ]
    assert len(model_inputs) == 2
    assert model_inputs[0] == pytest.approx((0.002, -0.001, 0.003))
    assert model_inputs[1] == pytest.approx((0.007, 0.003, 0.003))
    assert all(frame is projection for _, frame in native.utility.products)


@pytest.mark.parametrize("outline", ["absent", "forbidden", "stale", "padded"])
def test_native_circle_exact_ellipse_extrema_ignore_view_outline(scene, outline):
    native = scene(
        [_Circle((0.003, -0.002, 0.0), 0.004)],
        source=_source_frame(),
        projection=_oblique_view(),
    )
    outline_calls = []

    def get_outline():
        outline_calls.append(True)
        if outline == "forbidden":
            pytest.fail("construction ink must not consult GetOutline")
        return (
            (0.0, 0.0, 0.001, 0.001) if outline == "stale" else (-2.0, -3.0, 4.0, 5.0)
        )

    if outline != "absent":
        native.view.GetOutline = get_outline
    # Combined projection: x=cx+r(cos(t)-2sin(t)),
    # y=cy+r(3cos(t)+sin(t)). Neither extremum is a cardinal point.
    rx, ry = 0.004 * math.sqrt(5.0), 0.004 * math.sqrt(10.0)
    assert _bounds(native) == pytest.approx(
        (0.1145 - rx, -0.209 - ry, 0.1145 + rx, -0.209 + ry)
    )
    assert outline_calls == []


@pytest.mark.parametrize(
    "start,end,expected",
    [
        ((-0.003, 0.002, 0), (0.007, 0.002, 0), (-0.003, 0.002, 0.007, 0.002)),
        ((0.004, -0.006, 0), (0.004, 0.009, 0), (0.004, -0.006, 0.004, 0.009)),
    ],
    ids=["horizontal", "vertical"],
)
def test_native_line_accepts_visible_one_dimensional_span(scene, start, end, expected):
    assert _bounds(scene([_Line(start, end)])) == pytest.approx(expected)


@pytest.mark.parametrize("vertical", [False, True], ids=["horizontal", "vertical"])
def test_native_circle_projected_edge_on_retains_visible_span(scene, vertical):
    matrix = (
        ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
        if vertical
        else ((1.0, 0.0, 0.0), (0.0, 0.0, -1.0), (0.0, 1.0, 0.0))
    )
    native = scene(
        [_Circle((0.003, -0.002, 0.0), 0.004)],
        projection=_Transform(matrix, (0.1, 0.2, 0.0)),
    )
    expected = (0.1, 0.199, 0.1, 0.207) if vertical else (0.099, 0.2, 0.107, 0.2)
    assert _bounds(native) == pytest.approx(expected)


@pytest.mark.parametrize("reverse", [False, True])
def test_native_bounds_union_lines_and_complete_circles(scene, reverse):
    segments = [
        _Circle((0.003, -0.002, 0.0), 0.004),
        _Line((-0.010, 0.001, 0.0), (-0.002, 0.009, 0.0)),
        _Circle((0.008, -0.003, 0.0), 0.002),
    ]
    if reverse:
        segments.reverse()
    assert _bounds(scene(segments)) == pytest.approx((-0.010, -0.006, 0.010, 0.009))


@pytest.mark.parametrize("kind", [2, 3, 4, 5, 99])
def test_native_bounds_refuse_unsupported_segment_even_after_valid_ink(scene, kind):
    unsupported = SimpleNamespace(ConstructionGeometry=True, GetType=lambda: kind)
    native = scene([_Line((0, 0, 0), (0.01, 0.02, 0)), unsupported])
    with pytest.raises(RuntimeError, match="unsupported native sketch segment"):
        _bounds(native)


@pytest.mark.parametrize(
    "defect,match",
    [
        ("nonconstruction", "not construction"),
        ("missing-segment", "not construction"),
        ("3d", "2-D source sketch"),
        ("missing-sketch", "2-D source sketch"),
        ("empty", "no segments"),
        ("null-segments", "no segments"),
        ("missing-point", "point is missing"),
        ("zero-line", "zero length"),
        ("missing-transform", "transform is unavailable"),
        ("missing-inverse", "inverse is unavailable"),
        ("missing-utility", "CreatePoint"),
    ],
)
def test_native_bounds_fail_closed_for_invalid_source(scene, defect, match):
    line = _Line((0.001, 0.002, 0.0), (0.005, 0.006, 0.0))
    native = scene([line])
    if defect == "nonconstruction":
        line.ConstructionGeometry = False
    elif defect == "missing-segment":
        native.sketch.segments.append(None)
    elif defect == "3d":
        native.sketch.is_3d = True
    elif defect == "missing-sketch":
        native.sketch = None
    elif defect == "empty":
        native.sketch.segments = []
    elif defect == "null-segments":
        native.sketch.segments = None
    elif defect == "missing-point":
        line.end = None
    elif defect == "zero-line":
        line.end = line.start
    elif defect == "missing-transform":
        native.sketch.ModelToSketchTransform = None
    elif defect == "missing-inverse":
        native.sketch.ModelToSketchTransform.inverse = None
    elif defect == "missing-utility":
        native.adapter.swApp.GetMathUtility = lambda: None
    with pytest.raises(RuntimeError, match=match):
        _bounds(native)


@pytest.mark.parametrize("radius", [0.0, -0.004, math.nan, math.inf, -math.inf])
def test_native_circle_refuses_invalid_radius(scene, radius):
    with pytest.raises(RuntimeError, match="invalid native circular geometry"):
        _bounds(scene([_Circle((0.003, -0.002, 0.0), radius)]))


@pytest.mark.parametrize(
    "circle_flag",
    [0, 2, -1],
    ids=["partial-arc", "invalid-positive", "invalid-negative"],
)
def test_native_bounds_refuse_non_full_circle_before_reading_arc_geometry(
    scene, circle_flag
):
    unsupported = SimpleNamespace(
        ConstructionGeometry=True,
        GetType=lambda: 1,
        IsCircle=lambda: circle_flag,
        GetCenterPoint2=lambda: pytest.fail(
            "unsupported arc geometry must not be read"
        ),
        GetRadius=lambda: pytest.fail("unsupported arc radius must not be read"),
        GetStartPoint2=lambda: pytest.fail(
            "partial arcs have no supported endpoint path"
        ),
        GetEndPoint2=lambda: pytest.fail(
            "partial arcs have no supported endpoint path"
        ),
        GetRotationDir=lambda: pytest.fail(
            "partial arcs have no supported direction path"
        ),
    )
    native = scene([_Line((0, 0, 0), (0.01, 0.02, 0)), unsupported])
    with pytest.raises(RuntimeError, match="unsupported native partial arc"):
        _bounds(native)
    assert native.utility.products == []


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize(
    "stage", ["line-point", "circle-center", "source-transform", "view-transform"]
)
def test_native_bounds_refuse_nonfinite_native_and_projected_data(scene, stage, value):
    line = _Line((0.001, 0.002, 0), (0.005, 0.006, 0))
    circle = _Circle((0.003, -0.002, 0), 0.004)
    native = scene([line, circle])
    if stage == "line-point":
        line.start.X = value
    elif stage == "circle-center":
        circle.center.Y = value
    elif stage == "source-transform":
        native.sketch.ModelToSketchTransform.translation = (value, 0, 0)
    else:
        native.view.ModelToViewTransform.translation = (value, 0, 0)
    with pytest.raises(
        RuntimeError,
        match="nonfinite|invalid native source sketch inverse|invalid native construction projection",
    ):
        _bounds(native)


@pytest.mark.parametrize(
    "stage",
    [
        "sketch",
        "blocks",
        "text",
        "user-points",
        "segments",
        "inverse",
        "utility",
        "type",
        "line-start",
        "line-end",
        "center",
        "radius",
        "circle",
        "create-point",
        "view-product",
    ],
)
def test_native_bounds_propagate_unreadable_native_data_without_outline_fallback(
    scene, stage
):
    line = _Line((0.001, 0.002, 0), (0.005, 0.006, 0))
    circle = _Circle((0.003, -0.002, 0), 0.004)
    native = scene([line, circle])
    targets = {
        "sketch": (native.sketch, "Is3D"),
        "blocks": (native.sketch, "GetSketchBlockInstanceCount"),
        "text": (native.sketch, "GetSketchTextSegments"),
        "user-points": (native.sketch, "GetUserPointsCount"),
        "segments": (native.sketch, "GetSketchSegments"),
        "inverse": (native.sketch.ModelToSketchTransform, "Inverse"),
        "utility": (native.adapter.swApp, "GetMathUtility"),
        "type": (line, "GetType"),
        "line-start": (line, "GetStartPoint2"),
        "line-end": (line, "GetEndPoint2"),
        "center": (circle, "GetCenterPoint2"),
        "radius": (circle, "GetRadius"),
        "circle": (circle, "IsCircle"),
        "create-point": (native.utility, "CreatePoint"),
        "view-product": (native.view.ModelToViewTransform, "apply"),
    }
    target, member = targets[stage]
    setattr(target, member, _unreadable)
    outline_calls = []

    def get_outline():
        outline_calls.append(True)
        return (-1, -1, 1, 1)

    native.view.GetOutline = get_outline
    with pytest.raises(RuntimeError, match="native data unreadable"):
        _bounds(native)
    assert outline_calls == []


@pytest.mark.parametrize("stage", ["create", "multiply", "short-view-array"])
def test_native_bounds_refuse_missing_math_results(scene, stage):
    native = scene([_Line((0.001, 0.002, 0), (0.005, 0.006, 0))])
    if stage == "create":
        native.utility.CreatePoint = lambda _xyz: None
    elif stage == "multiply":
        native.utility.CreatePoint = lambda _xyz: SimpleNamespace(
            MultiplyTransform=lambda _frame: None
        )
    else:
        native.view.ModelToViewTransform.apply = lambda _xyz: (0.1,)
    with pytest.raises(
        RuntimeError,
        match="failed to create model point|failed to project model point|no sheet coordinates",
    ):
        _bounds(native)


def test_native_bounds_refuse_line_with_no_visible_span(scene):
    # A real nonzero source line becomes a point when viewed along its axis.
    projection = _Transform(
        ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0)),
        (0.1, 0.2, 0.0),
    )
    native = scene([_Line((0.001, 0.002, 0), (0.005, 0.002, 0))], projection=projection)
    with pytest.raises(RuntimeError, match="no finite visible span"):
        _bounds(native)


@pytest.mark.parametrize(
    "member,value,match",
    [
        ("blocks", 1, "sketch blocks"),
        ("text", (object(),), "sketch text"),
        ("user_points", 1, "sketch user points"),
    ],
)
def test_native_bounds_refuse_unsupported_sketch_ink_before_segment_projection(
    scene, member, value, match
):
    native = scene([_Line((0, 0, 0), (0.01, 0.02, 0))])
    setattr(native.sketch, member, value)
    with pytest.raises(RuntimeError, match=match):
        _bounds(native)
    assert native.sketch.ModelToSketchTransform.inverse_calls == 0
    assert native.utility.products == []


def test_native_bounds_allow_automatic_endpoints_and_circle_centers_without_user_points(
    scene,
):
    line = _Line((-0.010, 0.001, 0), (-0.002, 0.009, 0))
    circle = _Circle((0.003, -0.002, 0), 0.004)
    native = scene([line, circle])
    automatic = (line.start, line.end, circle.center)
    native.sketch.GetSketchPoints2 = lambda: automatic
    assert native.sketch.GetUserPointsCount() == 0
    before = tuple((point.X, point.Y, point.Z) for point in automatic)
    assert _bounds(native) == pytest.approx((-0.010, -0.006, 0.007, 0.009))
    assert tuple((point.X, point.Y, point.Z) for point in automatic) == before
    assert native.sketch.GetSketchSegments() == [line, circle]
    assert circle.radius == 0.004


@pytest.mark.parametrize(
    "defect", ["null", "short", "long", "nan", "infinite", "zero-scale"]
)
def test_native_bounds_refuse_invalid_source_inverse_array(scene, defect):
    native = scene([_Line((0, 0, 0), (0.01, 0.02, 0))])
    matrix = [
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
    ]
    if defect == "null":
        matrix = None
    elif defect == "short":
        matrix.pop()
    elif defect == "long":
        matrix.append(0.0)
    elif defect == "nan":
        matrix[0] = math.nan
    elif defect == "infinite":
        matrix[10] = math.inf
    elif defect == "zero-scale":
        matrix[12] = 0.0
    native.sketch.ModelToSketchTransform.inverse = SimpleNamespace(ArrayData=matrix)
    with pytest.raises(RuntimeError, match="invalid native source sketch inverse"):
        _bounds(native)
    assert native.utility.products == []


@pytest.mark.parametrize("scale", [0.5, 2.0, -1.0])
def test_native_bounds_refuse_nonunit_source_scale(scene, scale):
    source = _source_frame()
    source.inverse.scale = scale
    native = scene([_Line((0, 0, 0), (0.01, 0.02, 0))], source=source)
    with pytest.raises(RuntimeError, match="invalid native source sketch inverse"):
        _bounds(native)
    assert native.utility.products == []


def test_native_bounds_propagate_unreadable_source_inverse_array(scene):
    class UnreadableInverse:
        @property
        def ArrayData(self):
            raise RuntimeError("native inverse matrix unreadable")

    native = scene([_Line((0, 0, 0), (0.01, 0.02, 0))])
    native.sketch.ModelToSketchTransform.inverse = UnreadableInverse()
    with pytest.raises(RuntimeError, match="native inverse matrix unreadable"):
        _bounds(native)
    assert native.utility.products == []


def test_native_bounds_refuse_projection_below_visible_span_tolerance(scene):
    projection = _Transform(
        ((1e-8, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        (0.1, 0.2, 0.0),
    )
    native = scene([_Line((0.001, 0.002, 0), (0.005, 0.002, 0))], projection=projection)
    with pytest.raises(RuntimeError, match="no finite visible span"):
        _bounds(native)


def test_native_capture_contains_only_immutable_model_coordinates_and_curve_offsets(
    scene,
):
    native = scene(
        [
            _Line((0.001, 0.002, 0), (0.005, -0.003, 0)),
            _Circle((0.003, -0.002, 0), 0.004),
        ],
        source=_source_frame(),
    )
    geometry = capture_native_sketch_geometry(native.sketch, label=_LABEL)
    assert isinstance(geometry, NativeSketchGeometry)
    assert type(geometry.model_points) is tuple
    expected = (
        (0.002, -0.001, 0.003),
        (0.007, 0.003, 0.003),
        (0.006, 0.001, 0.003),
        (0.006, 0.005, 0.003),
        (0.002, 0.001, 0.003),
    )
    assert len(geometry.model_points) == len(expected)
    for actual, xyz in zip(geometry.model_points, expected, strict=True):
        assert type(actual) is tuple
        assert all(type(value) is float for value in actual)
        assert actual == pytest.approx(xyz)
    assert geometry.line_offsets == (0,)
    assert geometry.circle_offsets == (2,)
    assert native.utility.products == []  # Capture has no view/math-utility work.
    with pytest.raises(FrozenInstanceError):
        geometry.line_offsets = ()
    with pytest.raises(TypeError):
        geometry.model_points[0][0] = 4.0


def test_native_projection_uses_stable_capture_without_reading_changed_source(scene):
    line = _Line((0.001, 0.002, 0), (0.005, -0.003, 0))
    source = _source_frame()
    native = scene([line], source=source, projection=_oblique_view())
    geometry = capture_native_sketch_geometry(native.sketch, label=_LABEL)
    line.start.X = 400.0
    line.end.Y = -700.0
    native.sketch.segments.clear()
    for name in (
        "Is3D",
        "GetSketchBlockInstanceCount",
        "GetSketchTextSegments",
        "GetUserPointsCount",
        "GetSketchSegments",
    ):
        setattr(native.sketch, name, _unreadable)
    native.sketch.ModelToSketchTransform = None
    source.Inverse = _unreadable
    assert native_sketch_view_bounds(
        native.adapter, native.view, geometry, label=_LABEL
    ) == pytest.approx((0.1045, -0.211, 0.1185, -0.204))
    native.view.ModelToViewTransform.translation = (0.2, 0.1, 0.0)
    assert native_sketch_view_bounds(
        native.adapter, native.view, geometry, label=_LABEL
    ) == pytest.approx((0.2045, 0.089, 0.2185, 0.096))
    assert source.inverse_calls == 1
    assert source.inverse.array_reads == 1


def test_native_projection_refuses_live_sketch_instead_of_immutable_capture(scene):
    native = scene([_Line((0, 0, 0), (0.01, 0.02, 0))])
    with pytest.raises(
        RuntimeError, match=f"{_LABEL}: expected immutable NativeSketchGeometry capture"
    ):
        native_sketch_view_bounds(
            native.adapter, native.view, native.sketch, label=_LABEL
        )
    assert native.utility.products == []


@pytest.mark.parametrize("coordinate", [0, 1], ids=["late-x", "late-y"])
def test_native_projection_refuses_single_nonfirst_nan_before_bounds_reduction(
    scene, coordinate
):
    native = scene([_Line((0, 0, 0), (0.01, 0.02, 0))])
    geometry = capture_native_sketch_geometry(native.sketch, label=_LABEL)
    projection = native.view.ModelToViewTransform
    apply = projection.apply
    emitted = []

    def project_with_one_nan(xyz):
        point = list(apply(xyz))
        if len(emitted) == 1:
            point[coordinate] = math.nan
        emitted.append(tuple(point))
        return tuple(point)

    projection.apply = project_with_one_nan
    with pytest.raises(RuntimeError, match="invalid native construction projection"):
        native_sketch_view_bounds(native.adapter, native.view, geometry, label=_LABEL)
    assert len(emitted) == 2
    assert all(math.isfinite(value) for value in emitted[0])
    assert sum(math.isnan(value) for point in emitted for value in point) == 1
    assert len(native.utility.products) == 2


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param(
            {"model_points": [(0.0, 0.0, 0.0), (0.01, 0.02, 0.0)]},
            id="mutable-point-inventory",
        ),
        pytest.param(
            {"model_points": ([0.0, 0.0, 0.0], (0.01, 0.02, 0.0))}, id="mutable-point"
        ),
        pytest.param(
            {"model_points": ((0.0, 0.0), (0.01, 0.02, 0.0))}, id="short-point"
        ),
        pytest.param(
            {"model_points": ((0.0, 0.0, 0.0, 0.0), (0.01, 0.02, 0.0))}, id="long-point"
        ),
        pytest.param(
            {"model_points": ((0, 0.0, 0.0), (0.01, 0.02, 0.0))},
            id="non-float-coordinate",
        ),
        pytest.param(
            {"model_points": ((0.0, 0.0, 0.0), (math.nan, 0.02, 0.0))},
            id="nonfirst-nan-coordinate",
        ),
        pytest.param(
            {"model_points": ((0.0, 0.0, 0.0), (0.01, math.inf, 0.0))},
            id="infinite-coordinate",
        ),
        pytest.param({"line_offsets": [0]}, id="mutable-line-offsets"),
        pytest.param({"circle_offsets": []}, id="mutable-circle-offsets"),
        pytest.param({"line_offsets": (False,)}, id="bool-offset"),
        pytest.param({"line_offsets": (0.0,)}, id="float-offset"),
        pytest.param({"line_offsets": (-1,)}, id="negative-offset"),
        pytest.param({"line_offsets": (1,)}, id="line-overrun"),
        pytest.param({"line_offsets": (0, 0)}, id="duplicate-offset"),
        pytest.param(
            {
                "model_points": (
                    (0.0, 0.0, 0.0),
                    (0.01, 0.02, 0.0),
                    (0.03, 0.04, 0.0),
                    (0.05, 0.06, 0.0),
                ),
                "line_offsets": (2, 0),
            },
            id="unsorted-offsets",
        ),
        pytest.param(
            {
                "model_points": ((0.0, 0.0, 0.0), (0.01, 0.02, 0.0), (0.03, 0.04, 0.0)),
            },
            id="uncovered-point",
        ),
        pytest.param({"line_offsets": (), "circle_offsets": (0,)}, id="circle-overrun"),
        pytest.param(
            {
                "model_points": ((0.0, 0.0, 0.0), (0.01, 0.02, 0.0), (0.03, 0.04, 0.0)),
                "circle_offsets": (0,),
            },
            id="overlapping-line-and-circle",
        ),
        pytest.param({"line_offsets": ()}, id="no-curves"),
        pytest.param({"model_points": (), "line_offsets": ()}, id="empty-capture"),
    ],
)
def test_native_geometry_value_refuses_mutable_nonfinite_or_inconsistent_inventory(
    overrides,
):
    values = {
        "model_points": ((0.0, 0.0, 0.0), (0.01, 0.02, 0.0)),
        "line_offsets": (0,),
        "circle_offsets": (),
    }
    values.update(overrides)
    with pytest.raises(RuntimeError, match="captured native sketch geometry:"):
        NativeSketchGeometry(**values)
