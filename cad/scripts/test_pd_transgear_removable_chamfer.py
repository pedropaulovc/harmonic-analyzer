"""SolidWorks-free geometry/equation contracts for the supplied tooth chamfers."""

from __future__ import annotations

import ast
import math
import re
from pathlib import Path

import pytest

import build_pd_transgear_removable as part
import pd_transgear_removable_spec as spec


_TEETH = [teeth for _name, teeth in spec.CONFIGS]


def _equation(expression: str, values: dict[str, float]) -> float:
    code = re.sub(r'"(\w+)"', r'_v["\1"]', expression)
    return eval(
        code,
        {"__builtins__": {}},
        {
            "_v": values,
            "sin": lambda angle: math.sin(math.radians(angle)),
            "cos": lambda angle: math.cos(math.radians(angle)),
            "tan": lambda angle: math.tan(math.radians(angle)),
        },
    )


def test_vendor_section_uses_face_angle_not_cone_semi_angle() -> None:
    assert spec.CHAMFER_RADIAL == pytest.approx(1.905)
    assert spec.CHAMFER_FACE_ANGLE_DEG == pytest.approx(16.172)
    axial = spec.CHAMFER_RADIAL * math.tan(math.radians(spec.CHAMFER_FACE_ANGLE_DEG))
    assert spec.CHAMFER_AXIAL == pytest.approx(axial)
    assert 0.55 < axial < 0.56
    # Both tempting dialect mistakes produce a different cone: radians in
    # SW's degree-based tan(), or the 73.828-degree semi-angle from the axis.
    assert not math.isclose(
        axial, spec.CHAMFER_RADIAL * math.tan(spec.CHAMFER_FACE_ANGLE_DEG)
    )
    assert not math.isclose(
        axial,
        spec.CHAMFER_RADIAL
        * math.tan(math.radians(90.0 - spec.CHAMFER_FACE_ANGLE_DEG)),
    )


def _assert_sections(points: dict[str, part.Point], teeth: int) -> None:
    radius = spec.outside_dia(teeth) / 2.0
    assert points["origin"] == (0.0, 0.0)
    assert points["axis_rear"] == (0.0, -spec.PLATE)
    for face, face_y, direction in (("front", 0.0, -1.0), ("rear", -spec.PLATE, 1.0)):
        inner, outer, tip = (
            points[f"{face}_{key}"] for key in ("inner", "outer", "tip")
        )
        assert inner == pytest.approx((radius - spec.CHAMFER_RADIAL, face_y))
        assert outer == pytest.approx((radius + spec.CHAMFER_RADIAL, face_y))
        assert tip[0] == outer[0]
        assert tip[1] == pytest.approx(face_y + direction * 2.0 * spec.CHAMFER_AXIAL)
        assert direction * (tip[1] - face_y) > 0.0
        at_od = inner[1] + (radius - inner[0]) / (tip[0] - inner[0]) * (
            tip[1] - inner[1]
        )
        assert at_od == pytest.approx(face_y + direction * spec.CHAMFER_AXIAL)
        assert math.degrees(
            math.atan(abs((tip[1] - inner[1]) / (tip[0] - inner[0])))
        ) == pytest.approx(spec.CHAMFER_FACE_ANGLE_DEG)
        assert inner[0] > spec.PIN_CIRCLE_RADIUS + spec.PIN_HOLE_DIA / 2.0
    # The overrun triangles themselves remain disjoint, not just their in-part portions.
    assert points["rear_tip"][1] < points["front_tip"][1]


@pytest.mark.parametrize("teeth", _TEETH)
def test_two_closed_sections_cut_inward_on_the_correct_faces(teeth: int) -> None:
    points = part.chamfer_points(teeth)
    _assert_sections(points, teeth)
    for face in ("Front", "Rear"):
        edges = [
            part.CHAMFER_ENTITIES[f"{face}{suffix}"]
            for suffix in ("Face", "Outer", "Cone")
        ]
        assert all(
            first[1] == second[0]
            for first, second in zip(edges, edges[1:] + edges[:1], strict=True)
        )
        assert len({endpoint for edge in edges for endpoint in edge}) == 3


@pytest.mark.parametrize("teeth", _TEETH)
def test_every_chamfer_dimension_equation_matches_its_native_section(
    teeth: int,
) -> None:
    values: dict[str, float] = {}
    for name, expression, expected in part.gap_globals(teeth) + part.chamfer_globals():
        values[name] = _equation(expression, values)
        assert values[name] == pytest.approx(expected, rel=1e-9, abs=1e-12), name
    values["Plate"] = spec.PLATE / part.IN
    points = part.chamfer_points(teeth)
    dimension_names = set()
    for name, kind, first, second, expression in part.CHAMFER_DIMENSIONS:
        assert name not in dimension_names
        dimension_names.add(name)
        coordinate = {"horizontal_distance": 0, "vertical_distance": 1}[kind]
        measured = abs(
            part.chamfer_point(points, first)[coordinate]
            - part.chamfer_point(points, second)[coordinate]
        )
        assert _equation(expression, values) * part.IN == pytest.approx(
            measured, rel=1e-9, abs=1e-10
        ), name
    assert len(dimension_names) == 8
    assert {name for name in dimension_names if name.startswith("Front")} == {
        "FrontChamferRadius",
        "FrontChamferWidth",
        "FrontChamferDepth",
    }
    assert {name for name in dimension_names if name.startswith("Rear")} == {
        "RearChamferRadius",
        "RearChamferOffset",
        "RearChamferWidth",
        "RearChamferDepth",
    }


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_rear",
        "outward_front",
        "outward_rear",
        "wrong_face",
        "wrong_angle",
        "stale_radius",
    ],
)
def test_section_contract_rejects_geometry_negative_controls(mutation: str) -> None:
    teeth = 12
    points = part.chamfer_points(teeth).copy()
    if mutation == "missing_rear":
        del points["rear_tip"]
    elif mutation == "outward_front":
        x, y = points["front_tip"]
        points["front_tip"] = (x, -y)
    elif mutation == "outward_rear":
        x, y = points["rear_tip"]
        points["rear_tip"] = (x, -2.0 * spec.PLATE - y)
    elif mutation == "wrong_face":
        x, _y = points["rear_inner"]
        points["rear_inner"] = (x, 0.0)
    elif mutation == "wrong_angle":
        x, y = points["front_tip"]
        points["front_tip"] = (x, y * 1.1)
    else:
        points = part.chamfer_points(24)
    with pytest.raises((AssertionError, KeyError)):
        _assert_sections(points, teeth)


def _gap_boundary(teeth: int, samples: int = 600) -> list[part.Point]:
    """Trace the native in-disc gap boundary, closing on the actual OD arc."""
    points = part.gap_points(teeth)
    remaining = [
        name
        for name in part.GAP_ENTITIES
        if name not in (part.GAP_AXIS, "ClearLower", "ClearUpper")
    ]
    at = "k_u"
    boundary: list[part.Point] = []
    while remaining:
        name = next(name for name in remaining if at in part.GAP_ENTITIES[name][1:])
        remaining.remove(name)
        centre, start, end = part.GAP_ENTITIES[name]
        first, last = points[start], points[end]
        if centre is None:
            trace = [
                (
                    first[0] + k / samples * (last[0] - first[0]),
                    first[1] + k / samples * (last[1] - first[1]),
                )
                for k in range(samples + 1)
            ]
        else:
            cx, cy = points[centre]
            radius = math.dist(points[centre], first)
            begin = math.atan2(first[1] - cy, first[0] - cx)
            finish = math.atan2(last[1] - cy, last[0] - cx)
            sweep = (finish - begin) % math.tau
            trace = [
                (
                    cx + radius * math.cos(begin + k / samples * sweep),
                    cy + radius * math.sin(begin + k / samples * sweep),
                )
                for k in range(samples + 1)
            ]
        boundary.extend((trace if start == at else trace[::-1])[:-1])
        at = end if start == at else start
    assert at == "k_l"
    first, last = points["k_l"], points["k_u"]
    radius = spec.outside_dia(teeth) / 2.0
    begin, finish = math.atan2(first[1], first[0]), math.atan2(last[1], last[0])
    sweep = (finish - begin) % math.tau
    assert 0.0 < sweep < math.tau / teeth
    boundary.extend(
        [
            (
                radius * math.cos(begin + k / samples * sweep),
                radius * math.sin(begin + k / samples * sweep),
            )
            for k in range(samples)
        ]
    )
    return boundary


def _section_toothed_volume(teeth: int, faces: int = 2) -> float:
    """Independent polar Green integral of native tooth arcs and cone sections.

    If retained thickness is h(r), F(r) = integral_0^r h(s)*s ds. Then
    volume is the contour integral F(r)/r^2 * (x dy - y dx). Subtract the
    in-disc gaps from the disc; no spec volume helper supplies this result.
    """
    points = part.chamfer_points(teeth)
    inner = points["front_inner"][0]
    tip = points["front_tip"]
    slope = abs(tip[1]) / (tip[0] - inner) * faces

    def primitive(radius: float) -> float:
        full = spec.PLATE * radius * radius / 2.0
        if radius <= inner:
            return full
        return full - slope * (
            radius**3 / 3.0 - inner * radius**2 / 2.0 + inner**3 / 6.0
        )

    boundary = _gap_boundary(teeth)
    gap = 0.0
    for first, last in zip(boundary, boundary[1:] + boundary[:1], strict=True):
        radius = math.hypot((first[0] + last[0]) / 2.0, (first[1] + last[1]) / 2.0)
        gap += primitive(radius) / radius**2 * (first[0] * last[1] - first[1] * last[0])
    return math.tau * primitive(spec.outside_dia(teeth) / 2.0) - teeth * abs(gap)


@pytest.mark.parametrize("teeth", _TEETH)
def test_native_sections_and_teeth_match_both_volume_gates(teeth: int) -> None:
    native = _section_toothed_volume(teeth)
    assert native == pytest.approx(spec.toothed_volume(teeth), rel=2e-5, abs=0.005)
    holes = math.pi / 4.0 * (spec.BORE_DIA**2 + 2.0 * spec.PIN_HOLE_DIA**2) * spec.PLATE
    assert native - holes == pytest.approx(spec.part_volume(teeth), rel=2e-5, abs=0.005)
    assert spec.blank_volume(teeth) == pytest.approx(
        math.pi * (spec.outside_dia(teeth) / 2.0) ** 2 * spec.PLATE
    )
    assert (
        native
        < _section_toothed_volume(teeth, faces=1)
        < _section_toothed_volume(teeth, faces=0)
    )
    # The offline gate must detect a missing face, not accept a plausible disc.
    assert not math.isclose(
        _section_toothed_volume(teeth, faces=1),
        spec.toothed_volume(teeth),
        rel_tol=2e-5,
        abs_tol=0.005,
    )
    for expected in (spec.toothed_volume(teeth), spec.part_volume(teeth)):
        tolerance = part.chamfer_volume_tolerance(teeth, expected)
        assert tolerance == pytest.approx(
            min(0.01 * expected, spec.chamfer_volume(teeth) / 4.0)
        )
        assert 0.0 < tolerance < spec.chamfer_volume(teeth) / 2.0
        assert abs(native - spec.toothed_volume(teeth)) < tolerance
        assert (
            abs(_section_toothed_volume(teeth, faces=1) - spec.toothed_volume(teeth))
            > tolerance
        )
        assert (
            abs(_section_toothed_volume(teeth, faces=0) - spec.toothed_volume(teeth))
            > tolerance
        )


def test_native_cut_is_after_pattern_before_toothed_gate_and_mounting_ops() -> None:
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    build = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "build"
    )
    nodes = list(ast.walk(build))
    calls = [node for node in nodes if isinstance(node, ast.Call)]
    named_features = {
        node.args[1].value: node.lineno
        for node in calls
        if isinstance(node.func, ast.Name)
        and node.func.id == "name_last_feature"
        and len(node.args) > 1
        and isinstance(node.args[1], ast.Constant)
    }
    cuts = [
        node
        for node in calls
        if isinstance(node.func, ast.Name)
        and node.func.id == "RevolveParameters"
        and any(
            keyword.arg == "is_cut"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in node.keywords
        )
    ]
    assert len(cuts) == 1
    assert any(
        keyword.arg == "angle"
        and isinstance(keyword.value, ast.Constant)
        and keyword.value.value == 360.0
        for keyword in cuts[0].keywords
    )
    toothed_gate = next(
        node.lineno
        for node in calls
        if isinstance(node.func, ast.Attribute) and node.func.attr == "toothed_volume"
    )
    assert (
        named_features["ToothGapPattern"]
        < named_features["ToothChamferProfile"]
        < cuts[0].lineno
        < named_features["ToothSideChamfers"]
        < toothed_gate
        < named_features["BorePinsCut"]
    )
    assert part.MATERIAL == "Plain Carbon Steel"
