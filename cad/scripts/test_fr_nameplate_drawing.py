"""Offline contracts for the engraved nameplate's manufacturing drawing (#628)."""

from __future__ import annotations

import asyncio
import math
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import _drawing_edge_dimensions
import _dxf_text as dxf
import build_fr_nameplate as part
import draw_fr_nameplate as drawing
import fr_nameplate_drawing_spec as print_spec
import fr_nameplate_spec as spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _inch_wall_limits import WALL_TARGET_MM
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
from _release_artwork import bundle_path
from sh_vn_brass_fillister_screw_spec import HEAD_DIA

# Sheet B landscape inner border and the title block's top-left corner (m).
_BORDER = (0.0127, 0.0127, 0.4191, 0.2667)
_TITLE_BLOCK = (0.216, 0.065)


def _rings(path: Path) -> list[dxf.Ring]:
    text = path.read_text(encoding="ascii")
    return [ring for ring, _ in dxf.read_lwpolylines(text[text.find("\nENTITIES\n") :])]


def test_registry_row_names_this_script_and_stem() -> None:
    row = DRAWINGS_BY_NAME["fr_nameplate"]
    assert row.part == "fr_nameplate"
    assert row.artifact_stem == part.PART_NAME
    assert row.script == Path(drawing.__file__).resolve()


def test_marked_set_is_exactly_what_the_sheet_keeps() -> None:
    # The build marks and gives places to DRAWING_DIMENSIONS; the sheet keeps
    # exactly their union, and its one sheet-derived reference has spec places.
    assert part.DRAWING_DIMENSIONS is print_spec.DRAWING_DIMENSIONS
    assert part.DRAWING_PRECISION is print_spec.DRAWING_PRECISION
    marked = set().union(*print_spec.DRAWING_DIMENSIONS.values())
    kept = [*drawing.FRONT_KEEP, *drawing.RIGHT_KEEP, *drawing.SECTION_KEEP]
    assert len(kept) == len(set(kept)) and set(kept) == marked
    assert set(print_spec.DRAWING_PRECISION_BY_NAME) == marked
    assert print_spec.DRAWING_REFERENCE_PRECISION == {drawing.FLOOR_REFERENCE_LABEL: 3}
    assert set(print_spec.DIMENSION_PREFIXES) <= marked
    assert set(print_spec.DIMENSION_CALLOUTS) <= marked
    assert set(print_spec.SECTION_CALLOUTS) == set(drawing.SECTION_KEEP)
    # The reference sketches carry exactly the marked names they own.
    for sketch in print_spec.REFERENCE_SKETCHES:
        assert sketch in print_spec.DRAWING_DIMENSIONS


def test_places_are_the_parts_and_the_sheet_sets_only_the_reference() -> None:
    # Every manufacturing dimension's places are authored on the part and read
    # back on the sheet; SetPrecision3 is reserved for the one reference, and
    # takes its places from the spec's DRAWING_REFERENCE_PRECISION.
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    calls = re.findall(r"SetPrecision3\(([^)]*)\)", source)
    assert calls == ["DRAWING_REFERENCE_PRECISION[label], -1, -1, -1"]
    assert "set_dimension_precision" not in source
    assert (
        "assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)"
        in source
    )
    build = Path(part.__file__).read_text(encoding="utf-8")
    order = [
        build.index("    await _face_reference(adapter)\n"),
        build.index("    await _section_reference(adapter)\n"),
        build.index("    apply_drawing_precision(adapter, DRAWING_PRECISION)\n"),
        build.index("    blank_reference_sketches(adapter, REFERENCE_SKETCHES)\n"),
        build.index("    return await save_part_and_images(adapter, PART_NAME)\n"),
    ]
    assert order == sorted(order)


class _FakeSegment:
    ConstructionGeometry = False


class _ReferenceSketchAdapter:
    """Records what the build's reference-sketch recipes ask SOLIDWORKS for."""

    def __init__(self) -> None:
        self.lines: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {}
        self.points: dict[str, tuple[float, float]] = {}
        self.relations: list[tuple[str, str | None, str]] = []
        self._sketch_entities: dict[str, _FakeSegment] = {}
        self.planes: list[Any] = []
        self.sketch_planes: list[str] = []

    @staticmethod
    def _ok(data: Any = None) -> SimpleNamespace:
        return SimpleNamespace(is_success=True, data=data, error=None)

    async def create_sketch(self, plane: str) -> SimpleNamespace:
        self.sketch_planes.append(plane)
        return self._ok()

    async def add_line(self, x0: float, y0: float, x1: float, y1: float) -> Any:
        line = f"Line{len(self.lines) + 1}"
        self.lines[line] = ((x0, y0), (x1, y1))
        self._sketch_entities[line] = _FakeSegment()
        return self._ok(line)

    async def add_sketch_constraint(
        self, ref1: str, ref2: str | None, relation: str
    ) -> SimpleNamespace:
        self.relations.append((ref1, ref2, relation))
        return self._ok()

    async def exit_sketch(self) -> SimpleNamespace:
        return self._ok()

    async def create_plane(self, parameters: Any) -> SimpleNamespace:
        self.planes.append(parameters)
        return self._ok()

    def point(self, ref: str) -> tuple[float, float]:
        if ref in self.points:
            return self.points[ref]
        line, end = ref.split(".")
        return self.lines[line][0 if end == "start" else 1]


def _run_reference_sketch(
    monkeypatch: pytest.MonkeyPatch, recipe: Any
) -> tuple[_ReferenceSketchAdapter, dict[str, float]]:
    """Run one reference-sketch recipe offline; prove each relation and dim
    holds on the drawn geometry and the sketch is exactly defined, and return
    the recorded dimension name -> value."""
    adapter = _ReferenceSketchAdapter()
    values: list[float] = []
    anchors: list[str] = []
    applied: list[list[str]] = []

    async def dimension_between(
        _adapter: Any, ref1: str, ref2: str, kind: str, value: float, label: str
    ) -> str:
        (x0, y0), (x1, y1) = adapter.point(ref1), adapter.point(ref2)
        span = abs(x1 - x0) if kind == "horizontal_distance" else abs(y1 - y0)
        assert kind in {"horizontal_distance", "vertical_distance"}, label
        assert span == pytest.approx(value, abs=1e-9), label
        values.append(value)
        return label

    async def anchor_point_to_origin(
        _adapter: Any, ref: str, x: float, y: float, label: str
    ) -> None:
        assert adapter.point(ref) == pytest.approx((x, y)), label
        assert (x == 0.0) != (y == 0.0), label  # one relation + one dim
        anchors.append(ref)
        values.append(x or y)

    async def ensure_fully_defined(_adapter: Any, _label: str) -> None:
        return None

    class Dims(part.SketchDims):
        def apply(self, _adapter: Any, _feature: str) -> list[tuple[str, str]]:
            applied.append([name for name, _drive in self._rows])
            return []

    monkeypatch.setattr(part, "dimension_between", dimension_between)
    monkeypatch.setattr(part, "anchor_point_to_origin", anchor_point_to_origin)
    monkeypatch.setattr(part, "ensure_fully_defined", ensure_fully_defined)
    monkeypatch.setattr(part, "SketchDims", Dims)

    def add_reference_point(_adapter: Any, uv: tuple[float, float], _label: str) -> str:
        point = f"Point{len(adapter.points) + 1}"
        adapter.points[point] = uv
        return point

    monkeypatch.setattr(part, "_add_reference_point", add_reference_point)
    monkeypatch.setattr(part, "set_sketch_direct_db", lambda _adapter, _on: None)
    monkeypatch.setattr(part, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(part, "name_last_feature", lambda _adapter, _name: None)
    monkeypatch.setattr(part, "_require_on_section_plane", lambda *_args: None)
    asyncio.run(recipe(adapter))

    (names,) = applied
    assert len(names) == len(values) == len(set(names))
    for segment in adapter._sketch_entities.values():
        assert segment.ConstructionGeometry
    for ref1, ref2, relation in adapter.relations:
        if relation in {"horizontal", "vertical"}:
            (x0, y0), (x1, y1) = adapter.lines[ref1]
            assert (y0 == y1) if relation == "horizontal" else (x0 == x1), ref1
        else:
            (x0, y0), (x1, y1) = adapter.point(ref1), adapter.point(ref2)
            assert relation in {"horizontal_points", "vertical_points"}
            assert (y0 == y1) if relation == "horizontal_points" else (x0 == x1)
    # Exactly defined: four DOF a line, two a point, one relation per anchor,
    # every dim.
    assert 4 * len(adapter.lines) + 2 * len(adapter.points) == len(
        adapter.relations
    ) + len(anchors) + len(values)
    return adapter, dict(zip(names, values, strict=True))


def test_face_reference_carries_the_outline_and_far_stations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, dims = _run_reference_sketch(monkeypatch, part._face_reference)
    assert adapter.sketch_planes == ["Front"]
    assert print_spec.DRAWING_DIMENSIONS[print_spec.FACE_REFERENCE] <= set(dims)
    assert dims["PlateWidth"] == spec.PLATE_WIDTH
    assert dims["PlateHeight"] == spec.PLATE_HEIGHT
    # Each far station is measured on a hole the spec's ligament check judges
    # (to the 0.0002 the traced stations differ by).
    for name, edge in (("RightHoleStation", "right"), ("TopHoleStation", "top")):
        assert dims[name] == pytest.approx(
            print_spec.HOLE_EDGE_STATIONS[edge], abs=1e-3
        )
    # Every chord lies on what the face view draws: an edge chord on the
    # outline's straight run, a hole chord inside its hole from the centre.
    outline = _rings(part.OUTLINE_DXF)[0]
    holes = 0
    for start, end in adapter.lines.values():
        if tuple(start) in {tuple(xy) for xy in spec.SCREW_XY}:
            holes += 1
            assert math.dist(start, end) < drawing.HOLE_R
            continue
        for point in (start, ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2), end):
            gap = min(
                _segment_distance(point, outline[i], outline[(i + 1) % len(outline)])
                for i in range(len(outline))
            )
            assert gap < 1e-6, (start, end, point, gap)
    assert holes == 2


def test_section_reference_carries_both_depths_on_the_cut_plane(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, dims = _run_reference_sketch(monkeypatch, part._section_reference)
    assert adapter.sketch_planes == [print_spec.SECTION_PLANE]
    assert print_spec.DRAWING_DIMENSIONS[print_spec.SECTION_REFERENCE] <= set(dims)
    assert dims["FieldDepth"] == print_spec.FIELD_DEPTH == part.RECESS_DEPTH
    assert dims["EngravingDepth"] == print_spec.ENGRAVING_FLOOR_DEPTH
    # Points only: a construction chord on a cut-face line printed grey
    # dashes over A-A's outline, read as hidden lines in a section (ENFORCE
    # review). Each point lies on the cut-face line A-A draws at its height:
    # the decorated face, the groove's floor, the field's floor (sketch v = -z).
    assert not adapter.lines
    assert len(adapter.points) == 3
    field = _rings(part.FIELD_DXF)[0]
    engraving = _rings(part.ENGRAVING_DXF)
    y = print_spec.SECTION_Y

    def engraved(x: float) -> bool:
        return sum(dxf.point_in_ring(ring, (x, y)) for ring in engraving) % 2 == 1

    expected = {
        0.0: (False, False),
        print_spec.ENGRAVING_FLOOR_DEPTH: (False, True),
        print_spec.FIELD_DEPTH: (True, False),
    }
    for x, v in adapter.points.values():
        assert (dxf.point_in_ring(field, (x, y)), engraved(x)) == expected[v], x
        assert drawing.SECTION_CROP[0][0] < x < drawing.SECTION_CROP[1][0]


def test_section_plane_is_the_top_plane_carried_to_the_cut(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The +Y offset keeps the Top plane's (u, v) = model (X, -Z), the frame
    # SectionReference's points are drawn in.
    adapter = _ReferenceSketchAdapter()
    monkeypatch.setattr(part, "name_last_feature", lambda _adapter, _name: None)
    asyncio.run(part._section_plane(adapter))
    (plane,) = adapter.planes
    assert (plane.mode, plane.base_plane, plane.offset) == (
        "offset",
        "Top Plane",
        print_spec.SECTION_Y,
    )


class _PointSketchManager:
    def __init__(self, result: Any) -> None:
        self.AddToDB = False
        self.result = result
        self.calls: list[tuple[tuple[float, float, float], bool]] = []

    def CreatePoint(self, x: float, y: float, z: float) -> Any:  # noqa: N802
        self.calls.append(((x, y, z), self.AddToDB))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.mark.parametrize("result", [object(), None, RuntimeError("COM")])
def test_reference_point_goes_straight_to_the_db_and_restores_it(
    monkeypatch: pytest.MonkeyPatch, result: Any
) -> None:
    # The real helper: CreatePoint with AddToDB on (no inference snap), in
    # metres, registered for dimension refs, and AddToDB restored on every
    # path, a failed or raising CreatePoint included.
    monkeypatch.setattr(part, "_early_bound", lambda obj, _iface: obj)
    manager = _PointSketchManager(result)
    registered: list[tuple[str, Any]] = []

    def register(kind: str, entity: Any) -> str:
        registered.append((kind, entity))
        return f"{kind}1"

    adapter = SimpleNamespace(
        currentSketchManager=manager, _register_sketch_entity=register
    )
    if result is None or isinstance(result, Exception):
        with pytest.raises(RuntimeError):
            part._add_reference_point(adapter, (2.6, 0.7), "face")
        assert registered == []
    else:
        assert part._add_reference_point(adapter, (2.6, 0.7), "face") == "Point1"
        assert registered == [("Point", result)]
    ((point, add_to_db),) = manager.calls
    assert point == pytest.approx((0.0026, 0.0007, 0.0)) and add_to_db
    assert manager.AddToDB is False


def test_no_model_band_every_dimension_prints_the_title_block_grade() -> None:
    assert model_toleranced_dimensions(part) == {}


def test_isometric_note_names_the_isometric_view_scale() -> None:
    scale = f"{drawing.ISO_SCALE[0]}:{drawing.ISO_SCALE[1]}"
    assert print_spec.ISOMETRIC_VIEW_NOTE == f"ISOMETRIC VIEW SCALE {scale}"
    assert drawing.SHEET_SCALE == (2.0, 1.0) and drawing.VIEW_SCALE == (2, 1)


def test_print_contract_matches_the_built_geometry() -> None:
    assert print_spec.SCREW_HOLE_DIA == part.SCREW_HOLE_DIA
    assert print_spec.FIELD_DEPTH == part.RECESS_DEPTH
    assert print_spec.ENGRAVING_FLOOR_DEPTH == part.RECESS_DEPTH + part.ENGRAVE_DEPTH


def test_each_hole_prints_one_station_value_per_edge_pair() -> None:
    # "2X" stands for two holes whose stations print the same number.
    places = print_spec.DRAWING_PRECISION_BY_NAME
    bottom_left, bottom_right, top_left, top_right = spec.SCREW_XY
    assert round(bottom_left[0] / 25.4, places["S0X"]) == round(
        top_left[0] / 25.4, places["S0X"]
    )
    assert round(bottom_left[1] / 25.4, places["S0Z"]) == round(
        bottom_right[1] / 25.4, places["S0Z"]
    )
    right = [spec.PLATE_WIDTH - x for x in (bottom_right[0], top_right[0])]
    top = [spec.PLATE_HEIGHT - y for y in (top_left[1], top_right[1])]
    for values, name in ((right, "RightHoleStation"), (top, "TopHoleStation")):
        assert len({round(v / 25.4, places[name]) for v in values}) == 1, name
    assert (part.RIGHT_HOLE, part.TOP_HOLE) == (bottom_right, top_left)


def _segment_distance(
    p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = dx * dx + dy * dy
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length if length else 0.0
    t = max(0.0, min(1.0, t))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def test_section_a_crosses_the_plate_between_the_lettering_rows() -> None:
    # Both ends stand off the outline, so the arrows and letters print off
    # the plate (r2 review C3).
    outline = _rings(part.OUTLINE_DXF)[0]
    y = drawing.SECTION_Y
    assert drawing.SECTION_X_START < 0.0 < spec.PLATE_WIDTH < drawing.SECTION_X_END
    for x in (drawing.SECTION_X_START, drawing.SECTION_X_END):
        assert not dxf.point_in_ring(outline, (x, y))
    # The only engraved rings the line meets are the border's (pinstripe and
    # field edges, which span the plate); every letter and the ornament
    # stand at least a millimetre clear of it.
    for ring in _rings(part.ENGRAVING_DXF):
        xs = [x for x, _ in ring]
        ys = [y_ for _, y_ in ring]
        if min(ys) <= y <= max(ys):
            assert min(xs) < drawing.SECTION_FIELD_X, ring[0]
            assert max(xs) > spec.PLATE_WIDTH - drawing.SECTION_FIELD_X, ring[0]
        else:
            assert min(abs(min(ys) - y), abs(max(ys) - y)) >= 1.0, ring[0]


def test_section_a_crop_holds_the_border_the_groove_and_the_field() -> None:
    # The engraving DXF's closed rings nest: the pinstripe's outer edge, the
    # field ring (its inner edge), each letter and each letter's counter. A
    # point is cut to the engraving floor where an odd number of them holds it.
    outline = _rings(part.OUTLINE_DXF)[0]
    field = _rings(part.FIELD_DXF)[0]
    engraving = _rings(part.ENGRAVING_DXF)
    assert field in engraving
    y = drawing.SECTION_Y

    def engraved(x: float) -> bool:
        return sum(dxf.point_in_ring(ring, (x, y)) for ring in engraving) % 2 == 1

    face = (print_spec.SECTION_FACE_X, y)
    assert dxf.point_in_ring(outline, face) and not dxf.point_in_ring(field, face)
    assert not engraved(print_spec.SECTION_FACE_X)
    groove = (drawing.SECTION_GROOVE_X, y)
    assert not dxf.point_in_ring(field, groove) and engraved(drawing.SECTION_GROOVE_X)
    floor = (drawing.SECTION_FIELD_X, y)
    assert dxf.point_in_ring(field, floor) and not engraved(drawing.SECTION_FIELD_X)
    # The crop holds the plate's left edge and the whole thickness, and ends
    # on the field floor, not mid-groove.
    (x0, z0), (x1, z1) = drawing.SECTION_CROP
    assert x0 < 0.0 and z0 > 0.0 and z1 < -spec.PLATE_THICKNESS
    assert x1 > drawing.SECTION_FIELD_X
    end = (x1, y)
    assert dxf.point_in_ring(field, end) and not engraved(x1)


def test_section_a_break_line_closes_the_crops_open_end() -> None:
    # r4 review: the fragment's right end needs a break line. It stands on the
    # crop's right edge, from above the field floor to below the back face,
    # with one Z mid-thickness whose tips sit either side of that edge.
    (x0, z0), (x1, z1) = drawing.SECTION_CROP
    points = drawing.SECTION_BREAK
    assert points[0][0] == points[1][0] == points[-2][0] == points[-1][0] == x1
    assert points[0][1] > -print_spec.FIELD_DEPTH
    assert points[-1][1] < -spec.PLATE_THICKNESS
    assert z0 > points[0][1] and points[-1][1] > z1
    zs = [z for _x, z in points]
    assert zs == sorted(zs, reverse=True)
    tips = sorted(x for x, _z in points[2:4])
    assert tips[0] < x1 < tips[1]
    assert all(
        -spec.PLATE_THICKNESS < z < -print_spec.FIELD_DEPTH for _x, z in points[1:5]
    )
    # The break draws after the crop, once A-A sits on its centre.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    order = [
        source.index("    _crop_section(adapter, view)\n"),
        source.index("    _place_crop_on_center(adapter, view)\n"),
        source.index("    _sketch_section_break(adapter, view)\n"),
    ]
    assert order == sorted(order)


def test_section_a_dimensions_each_depth_on_its_own_line() -> None:
    # r2 review C2: the two depths shared one face arrow; each now stands on
    # its own station, both from the decorated face point (z = 0).
    points = print_spec.SECTION_REFERENCE_POINTS
    face, field, groove = points["face"], points["field"], points["groove"]
    assert face[1] == 0.0 and field[0] != groove[0]
    assert -field[1] == print_spec.FIELD_DEPTH
    assert -groove[1] == print_spec.ENGRAVING_FLOOR_DEPTH
    keep = drawing.SECTION_KEEP
    assert keep["FieldDepth"][0] != keep["EngravingDepth"][0]
    # B3: the floor under the engraving chains below the engraving depth as
    # a reference, plate thickness less the engraving floor depth.
    floor = drawing.FLOOR_REFERENCE
    assert floor["from"] == groove
    (_, z0), (_, z1) = floor["from"], floor["to"]
    assert math.isclose(z0 - z1, floor["expected_mm"])
    assert math.isclose(
        floor["expected_mm"], spec.PLATE_THICKNESS - print_spec.ENGRAVING_FLOOR_DEPTH
    )
    assert floor["callout"] == "FLOOR UNDER ENGRAVING"


def test_sunk_field_depth_names_why_it_holds_three_places() -> None:
    # PR #1468 r4 review: the field depth printed .XXX with no stated
    # function. The field must stay above the engraving's floor so the
    # lettering stays cut; .028 and .016 at .XXX (+-.005) leave .002, and at
    # .XX (+-.010) the field could cut below the engraving.
    assert (0.028 - 0.005) - (0.016 + 0.005) == pytest.approx(0.002)
    assert (0.028 - 0.005) - (0.016 + 0.010) < 0.0
    assert print_spec.ENGRAVING_BELOW_FIELD_MIN == pytest.approx(0.002 * 25.4)
    assert print_spec.DRAWING_PRECISION[print_spec.SECTION_REFERENCE] == {
        "FieldDepth": 3,
        "EngravingDepth": 3,
    }
    rows = print_spec.FIELD_DEPTH_CALLOUT.split("\n")
    assert rows == ["SUNK FIELD DEPTH", "ENGRAVING BELOW IT"]
    # The three-row block (value and two callout rows, 4.5 mm each) keeps its
    # leader shelf above the field's outside arrow, ~5.7 mm long on the r4
    # render, at the decorated face.
    face_y = drawing._section_xy(print_spec.SECTION_FIELD_X, 0.0)[1]
    block_bottom = drawing.SECTION_KEEP["FieldDepth"][1] - 0.00225 * (1 + len(rows))
    assert block_bottom > face_y + 0.006


class _FakeDisplay:
    def __init__(self) -> None:
        self.precision: tuple[int, ...] | None = None

    def SetPrecision3(self, *places: int) -> None:  # noqa: N802 -- COM name
        self.precision = places

    def GetPrimaryPrecision2(self) -> int:  # noqa: N802 -- COM name
        assert self.precision is not None
        return self.precision[0]

    def GetAnnotation(self) -> _FakeDisplay:  # noqa: N802 -- COM name
        return self


def test_floor_reference_measures_through_the_shared_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The sheet measures its one derived dimension with the shared
    # assert_dimension_measures (attachments checked, 1e-3 mm), not a copy,
    # and gives it the spec's reference places.
    assert (
        drawing.assert_dimension_measures
        is _drawing_edge_dimensions.assert_dimension_measures
    )
    display = _FakeDisplay()
    calls: dict[str, Any] = {}

    def cut_face_line(_edges: Any, *, x_mm: float, z_mm: float, label: str) -> Any:
        return f"edge@{z_mm}", (x_mm, print_spec.SECTION_Y, z_mm)

    def measures(_adapter: Any, dimension: Any, **kwargs: Any) -> float:
        calls["measures"] = (dimension, kwargs)
        return kwargs["expected_mm"]

    def add_edge_dimension(_adapter: Any, _view: Any, **kwargs: Any) -> Any:
        calls["add"] = kwargs
        return display

    monkeypatch.setattr(drawing, "scan_view_edges", lambda _view, label: label)
    monkeypatch.setattr(drawing, "_cut_face_line", cut_face_line)
    monkeypatch.setattr(
        drawing, "model_points_in_view", lambda _a, _v, points, label: points
    )
    monkeypatch.setattr(drawing, "add_edge_dimension", add_edge_dimension)
    monkeypatch.setattr(drawing, "assert_dimension_measures", measures)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(
        drawing,
        "set_reference_dimension",
        lambda _a, annotation, label: calls.setdefault("reference", label),
    )
    monkeypatch.setattr(
        drawing,
        "set_dimension_callouts",
        lambda _a, _annotations, callouts: calls.setdefault("callouts", callouts),
    )
    monkeypatch.setattr(drawing, "dimension_name", lambda _a, _annotation: "RD1")
    drawing._floor_reference(object(), object())

    floor = drawing.FLOOR_REFERENCE
    entities = (f"edge@{floor['from'][1]}", f"edge@{floor['to'][1]}")
    assert calls["add"]["entities"] == entities
    assert calls["measures"] == (
        display,
        {
            "expected_mm": floor["expected_mm"],
            "label": drawing.FLOOR_REFERENCE_LABEL,
            "entities": entities,
            "tolerance_mm": 1e-3,
        },
    )
    places = print_spec.DRAWING_REFERENCE_PRECISION[drawing.FLOOR_REFERENCE_LABEL]
    assert display.precision == (places, -1, -1, -1)
    assert calls["reference"] == drawing.FLOOR_REFERENCE_LABEL
    assert calls["callouts"] == {"RD1": print_spec.FLOOR_UNDER_ENGRAVING_CALLOUT}


def test_section_a_texts_and_caption_clear_each_other() -> None:
    # Measured r2 text blocks (8:1): a two-row value and callout is about
    # 8 mm tall and its callout row about 2.85 mm a character wide; r4's
    # measured ~9 mm, so each row here takes 4.5 mm and a block's width is
    # its longest callout row's. Each block is boxed left-aligned on its
    # dimension line (as r2 printed), right-aligned on it (as r4 printed the
    # floor reference) and centred on it, so no SOLIDWORKS placement can
    # collide.
    def boxes(pick: dict) -> list[tuple[float, float, float, float]]:
        x, y = pick["text_xy"]
        rows = pick["callout"].split("\n")
        width = 0.00285 * max(len(row) for row in rows)
        half = 0.00225 * (1 + len(rows))
        return [
            (x, y - half, x + width, y + half),
            (x - width, y - half, x, y + half),
            (x - width / 2.0, y - half, x + width / 2.0, y + half),
        ]

    def overlaps(a: tuple, b: tuple) -> bool:
        return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]

    caption_x, caption_top = drawing.SECTION_CAPTION_XY
    caption = (caption_x - 0.023, caption_top - 0.016, caption_x + 0.023, caption_top)
    crop_low = drawing._section_xy(*drawing.SECTION_CROP[1])
    crop_high = drawing._section_xy(*drawing.SECTION_CROP[0])
    crop = (crop_high[0], crop_low[1], crop_low[0], crop_high[1])
    texts = {
        **{
            name: {"text_xy": xy, "callout": print_spec.SECTION_CALLOUTS[name]}
            for name, xy in drawing.SECTION_KEEP.items()
        },
        drawing.FLOOR_REFERENCE_LABEL: drawing.FLOOR_REFERENCE,
    }
    placed = {name: boxes(pick) for name, pick in texts.items()}
    for name, candidates in placed.items():
        for box in candidates:
            assert box[2] < _BORDER[2] - 0.003, name
            assert not overlaps(box, caption), name
            assert not overlaps(box, crop), name
        for other, others in placed.items():
            clash = any(overlaps(a, b) for a in candidates for b in others)
            assert other == name or not clash, (name, other)
    assert not overlaps(caption, crop)
    assert caption[1] > _TITLE_BLOCK[1] + 0.003
    # Below the edge view, whose bottom is the face's bottom edge.
    assert caption[3] < drawing._BOTTOM - 0.005


def test_heads_stay_on_the_border_at_the_worst_printed_station() -> None:
    # The base is spotted through the plate, so the head follows the hole
    # wherever the shop drilled it inside the printed stations.
    outline = _rings(part.OUTLINE_DXF)[0]
    field = _rings(part.FIELD_DXF)[0]
    shift = math.hypot(
        print_spec.HOLE_STATION_SHIFT_MAX, print_spec.HOLE_STATION_SHIFT_MAX
    )
    reach = HEAD_DIA / 2.0 + shift
    for hx, hy in spec.SCREW_XY:
        for degrees in range(0, 360, 2):
            angle = math.radians(degrees)
            point = (hx + reach * math.cos(angle), hy + reach * math.sin(angle))
            assert dxf.point_in_ring(outline, point), (hx, hy, point)
            assert not dxf.point_in_ring(field, point), (hx, hy, point)


def _corner_worst_centres(
    stations: tuple[tuple[float, float], ...],
) -> list[tuple[float, float]]:
    # Each hole driven to the least printed station from BOTH of its corner's
    # edges at once: the sheet prints one .XX value per edge pair (2X), the
    # smallest of the pair's stations rounded, and accepts that value - .010.
    places = print_spec.DRAWING_PRECISION_BY_NAME["S0X"]
    assert places == 2
    width, height = spec.PLATE_WIDTH, spec.PLATE_HEIGHT
    left = min(x for x, _ in stations if x < width / 2.0)
    right = min(width - x for x, _ in stations if x > width / 2.0)
    bottom = min(y for _, y in stations if y < height / 2.0)
    top = min(height - y for _, y in stations if y > height / 2.0)
    least = {
        name: round(value / 25.4, places) * 25.4
        - printed_band_mm(places, unit=spec.UNIT)
        for name, value in (
            ("left", left),
            ("right", right),
            ("bottom", bottom),
            ("top", top),
        )
    }
    return [
        (
            least["left"] if x < width / 2.0 else width - least["right"],
            least["bottom"] if y < height / 2.0 else height - least["top"],
        )
        for x, y in stations
    ]


def _ring_of_ligament_holds(centre: tuple[float, float], radius: float) -> bool:
    outline = _rings(part.OUTLINE_DXF)[0]
    return all(
        dxf.point_in_ring(
            outline,
            (
                centre[0] + radius * math.cos(math.radians(degrees / 4.0)),
                centre[1] + radius * math.sin(math.radians(degrees / 4.0)),
            ),
        )
        for degrees in range(4 * 360)
    )


def test_hole_ligament_holds_with_each_hole_driven_into_its_rounded_corner() -> None:
    # PR #1468 r3: the corner arcs, not the straight edges, are nearest. A
    # drilled hole at .120 printed + .005 plus rule 17's .080 target must stay
    # inside the outline with every hole pushed toward its corner in X and Y.
    radius = (
        round(part.SCREW_HOLE_DIA / 25.4, 3) * 25.4
        + drilled_oversize_mm(unit=spec.UNIT)
    ) / 2.0 + WALL_TARGET_MM
    for centre in _corner_worst_centres(spec.SCREW_XY):
        assert _ring_of_ligament_holds(centre, radius), centre
    assert print_spec.HOLE_LIGAMENT_WORST >= print_spec.LIGAMENT_FLOOR


def test_engraving_floor_at_the_printed_worst_case() -> None:
    floor = (
        spec.PLATE_THICKNESS
        - printed_band_mm(3, unit=spec.UNIT)
        - (print_spec.ENGRAVING_FLOOR_DEPTH + printed_band_mm(3, unit=spec.UNIT))
    )
    assert math.isclose(print_spec.ENGRAVING_FLOOR_MIN, floor)
    # .063 - .005 - (.028 + .005) = .025.
    assert floor == pytest.approx(0.025 * 25.4)


def test_screw_full_thread_is_the_accepted_rule_20_shortfall() -> None:
    # Ruling B1: the #4-40 x 1/4 inch fillister, .020 short per ASME B18.6.3,
    # through the plate at .063 + .005, less 0.75 of the 40 TPI pitch at its tip.
    worst = 0.250 * 25.4 - 0.508 - (0.063 + 0.005) * 25.4 - 0.75 * 0.635
    assert worst == pytest.approx(3.6386, abs=5e-4)
    assert spec.SCREW_FULL_THREAD_MIN == pytest.approx(worst, abs=1e-9)
    assert 0.0 < spec.SCREW_FULL_THREAD_ACCEPTED <= round(worst, 4)
    # Still short of 1.5D of the 2.8448 major (4.267): the ruling is live.
    assert worst < 1.5 * 2.8448
    assert worst / 2.8448 == pytest.approx(1.28, abs=5e-3)


def test_declared_exceptions_name_the_printed_minimums() -> None:
    # Each owner-ruled shortfall is declared for this package, names the
    # sheet text that states it, and that text prints the spec's worst case
    # rounded down to two places.
    from _paths import CAD_ROOT
    from machinist_exceptions import load_exceptions

    declared = {
        entry.id: entry
        for entry in load_exceptions(CAD_ROOT / "config", "fr_nameplate", "part")
    }
    assert {name: entry.kind for name, entry in declared.items()} == {
        "RV-01": "accept",
        "RV-02": "minor",
        "RV-03": "minor",
    }
    for entry in declared.values():
        assert entry.reason.endswith(("(owner-accepted)", "(owner-ruled shortfall)"))
    floor, screws = print_spec.MINIMUM_NOTES.splitlines()
    assert floor in declared["RV-02"].where
    assert screws in declared["RV-03"].where
    # Each states its worst case in inches, rounded down to three places.
    for note, worst in (
        (floor, print_spec.ENGRAVING_FLOOR_MIN),
        (screws, spec.SCREW_FULL_THREAD_MIN),
    ):
        stated = next(word for word in note.split() if word.startswith("."))
        assert float(stated) == math.floor(worst / 25.4 * 1000.0 + 1e-9) / 1000.0
    for note in print_spec.MANUFACTURING_NOTES.splitlines()[:3]:
        assert note in declared["RV-01"].where
    # The holes' wall to the corner radius meets rule 17's .080 target at the
    # printed worst case, so no shortfall is stated (RV-04 retired).
    assert print_spec.HOLE_LIGAMENT_WORST >= WALL_TARGET_MM


def test_notes_and_callouts_carry_no_numbers_and_stay_short() -> None:
    notes = print_spec.MANUFACTURING_NOTES.splitlines()
    # The note block's rows fit the left half above the title band.
    assert 1 <= len(notes) <= 4
    assert all(len(note) <= 60 for note in notes), notes
    texts = [
        *notes,
        print_spec.FIELD_DEPTH_CALLOUT,
        print_spec.ENGRAVING_DEPTH_CALLOUT,
        print_spec.FLOOR_UNDER_ENGRAVING_CALLOUT,
        drawing.SCREW_HEAD_NOTE,
        *print_spec.DIMENSION_CALLOUTS.values(),
    ]
    assert not any(re.search(r"\d", text) for text in texts), texts
    # Each vendored contour by the exact path cut_release stages it at.
    for name in (part.OUTLINE_DXF, part.FIELD_DXF, part.ENGRAVING_DXF):
        assert f" PER {bundle_path(name.name)}" in print_spec.MANUFACTURING_NOTES


def test_texts_stand_inside_the_border_and_off_the_title_block() -> None:
    points = [
        *drawing.FRONT_KEEP.values(),
        *drawing.RIGHT_KEEP.values(),
        *drawing.SECTION_KEEP.values(),
        drawing.FLOOR_REFERENCE["text_xy"],
        drawing.HOLE_CALLOUT_XY,
        drawing.NOTES_XY,
        drawing.SCREW_HEAD_NOTE_XY,
        drawing.MINIMUM_NOTES_XY,
        drawing.ISO_NOTE_XY,
        drawing.SECTION_CENTER,
        drawing.SECTION_CAPTION_XY,
        drawing.ISO_CENTER,
    ]
    for x, y in points:
        assert _BORDER[0] + 0.005 < x < _BORDER[2] - 0.005, (x, y)
        assert _BORDER[1] < y < _BORDER[3] - 0.005, (x, y)
        assert not (x > _TITLE_BLOCK[0] and y < _TITLE_BLOCK[1] + 0.008), (x, y)
    # Dimension texts stand off the plate face, never on the engraving.
    left, bottom = drawing._front_xy(0.0, 0.0)
    right, top = drawing._front_xy(spec.PLATE_WIDTH, spec.PLATE_HEIGHT)
    for x, y in [
        *drawing.FRONT_KEEP.values(),
        drawing.HOLE_CALLOUT_XY,
    ]:
        assert not (
            left - 0.003 < x < right + 0.003 and bottom - 0.003 < y < top + 0.003
        )
    # r2 audit: the plate height's dimension line crossed both "2X" station
    # texts, which print 1.5..14.6 mm left of their own lines.
    height_line_x = drawing.FRONT_KEEP["PlateHeight"][0]
    for station_x, _ in (
        drawing.FRONT_KEEP["S0Z"],
        drawing.FRONT_KEEP["TopHoleStation"],
    ):
        assert height_line_x < station_x - 0.0146 - 0.002


def test_part_registry_row_carries_the_title_block_facts() -> None:
    import _config

    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-FR-04"
    assert "brass" in str(row["material_specification"]).lower()
    assert row["finish"]
    assert int(row["quantity"]) == 1
