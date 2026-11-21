"""Offline contracts for the etched nameplate's manufacturing drawing (#628)."""

from __future__ import annotations

import math
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

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
    # exactly their union.
    assert part.DRAWING_DIMENSIONS is print_spec.DRAWING_DIMENSIONS
    assert part.DRAWING_PRECISION is print_spec.DRAWING_PRECISION
    marked = set().union(*print_spec.DRAWING_DIMENSIONS.values())
    kept = [*drawing.FRONT_KEEP, *drawing.RIGHT_KEEP, *drawing.SECTION_KEEP]
    assert len(kept) == len(set(kept)) and set(kept) == marked
    assert set(print_spec.DRAWING_PRECISION_BY_NAME) == marked
    assert set(print_spec.DIMENSION_PREFIXES) <= marked
    assert drawing.SECTION_CALLOUTS is print_spec.SECTION_CALLOUTS
    assert set(print_spec.SECTION_CALLOUTS) == set(drawing.SECTION_KEEP)
    # The reference sketches carry exactly the marked names they own.
    for sketch in print_spec.REFERENCE_SKETCHES:
        assert sketch in print_spec.DRAWING_DIMENSIONS


def test_places_are_the_parts_and_the_sheet_sets_none() -> None:
    # Every dimension's places are authored on the part and read back on the
    # sheet; the sheet derives no dimension of its own.
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


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

    def create_sketch(self, plane: str) -> SimpleNamespace:
        self.sketch_planes.append(plane)
        return self._ok()

    def add_line(self, x0: float, y0: float, x1: float, y1: float) -> Any:
        line = f"Line{len(self.lines) + 1}"
        self.lines[line] = ((x0, y0), (x1, y1))
        self._sketch_entities[line] = _FakeSegment()
        return self._ok(line)

    def add_sketch_constraint(
        self, ref1: str, ref2: str | None, relation: str
    ) -> SimpleNamespace:
        self.relations.append((ref1, ref2, relation))
        return self._ok()

    def exit_sketch(self) -> SimpleNamespace:
        return self._ok()

    def create_plane(self, parameters: Any) -> SimpleNamespace:
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

    def dimension_between(
        _adapter: Any, ref1: str, ref2: str, kind: str, value: float, label: str
    ) -> str:
        (x0, y0), (x1, y1) = adapter.point(ref1), adapter.point(ref2)
        span = abs(x1 - x0) if kind == "horizontal_distance" else abs(y1 - y0)
        assert kind in {"horizontal_distance", "vertical_distance"}, label
        assert span == pytest.approx(value, abs=1e-9), label
        values.append(value)
        return label

    def anchor_point_to_origin(
        _adapter: Any, ref: str, x: float, y: float, label: str
    ) -> None:
        assert adapter.point(ref) == pytest.approx((x, y)), label
        assert (x == 0.0) != (y == 0.0), label  # one relation + one dim
        anchors.append(ref)
        values.append(x or y)

    def ensure_fully_defined(_adapter: Any, _label: str) -> None:
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
    recipe(adapter)

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


def test_section_reference_carries_the_etched_depth_on_the_cut_plane(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, dims = _run_reference_sketch(monkeypatch, part._section_reference)
    assert adapter.sketch_planes == [print_spec.SECTION_PLANE]
    assert print_spec.DRAWING_DIMENSIONS[print_spec.SECTION_REFERENCE] <= set(dims)
    assert dims["FieldDepth"] == print_spec.FIELD_DEPTH
    # Points only: a construction chord on a cut-face line printed grey
    # dashes over A-A's outline, read as hidden lines in a section (ENFORCE
    # review). Each point lies on the cut-face line A-A draws at its height:
    # the decorated face on the border, the field's floor (sketch v = -z).
    assert not adapter.lines
    assert len(adapter.points) == 2
    y = print_spec.SECTION_Y
    expected = {0.0: False, print_spec.FIELD_DEPTH: True}
    for x, v in adapter.points.values():
        assert _etched(x, y) == expected[v], x
        assert drawing.SECTION_CROP[0][0] < x < drawing.SECTION_CROP[1][0]


def _etched(x: float, y: float) -> bool:
    """A point of the decorated face lies in the etched field: an odd number
    of the field DXF's loops (the field, a letter, a counter) holds it."""
    rings = _rings(part.FIELD_DXF)
    return sum(dxf.point_in_ring(ring, (x, y)) for ring in rings) % 2 == 1


def test_the_one_model_band_is_the_owner_ruled_etch_depth() -> None:
    # No symmetric or bilateral band anywhere; the etched field's depth alone
    # prints its limits, .008-.012 (owner ruling 2026-11-20, #2313: "A").
    assert model_toleranced_dimensions(part) == {}
    low, high = print_spec.FIELD_DEPTH_LIMITS
    assert (low / 25.4, print_spec.FIELD_DEPTH / 25.4, high / 25.4) == pytest.approx(
        (0.008, 0.010, 0.012), abs=1e-12
    )
    import ast

    calls = [
        node
        for node in ast.walk(ast.parse(Path(part.__file__).read_text(encoding="utf-8")))
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "set_limits"
    ]
    assert len(calls) == 1
    (call,) = calls
    assert [ast.unparse(arg) for arg in call.args[1:]] == [
        "SECTION_REFERENCE",
        "'FieldDepth'",
    ]
    assert {keyword.arg: ast.unparse(keyword.value) for keyword in call.keywords}[
        "limits"
    ] == "FIELD_DEPTH_LIMITS"


def test_isometric_note_names_the_isometric_view_scale() -> None:
    scale = f"{drawing.ISO_SCALE[0]}:{drawing.ISO_SCALE[1]}"
    assert print_spec.ISOMETRIC_VIEW_NOTE == f"ISOMETRIC VIEW SCALE {scale}"
    assert drawing.SHEET_SCALE == (2.0, 1.0) and drawing.VIEW_SCALE == (2, 1)


def test_print_contract_matches_the_built_geometry() -> None:
    assert print_spec.SCREW_HOLE_DIA == part.SCREW_HOLE_DIA
    assert part.FIELD_DXF.name == print_spec.FIELD_DXF_NAME
    assert part.OUTLINE_DXF.name == print_spec.OUTLINE_DXF_NAME


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
    # A short partial plane: it starts off the outline, so that arrow and
    # letter print off the plate (r2 review C3), and stops on the etched field
    # just past what the cropped section shows (rule 9).
    outline = _rings(part.OUTLINE_DXF)[0]
    y = drawing.SECTION_Y
    assert drawing.SECTION_X_START < 0.0 < drawing.SECTION_CROP[1][0] < drawing.SECTION_X_END
    assert drawing.SECTION_X_END < 0.1 * spec.PLATE_WIDTH
    assert not dxf.point_in_ring(outline, (drawing.SECTION_X_START, y))
    # The only field loop the line meets is the field's edge, which spans
    # the plate; every letter and the ornament stand at least a millimetre
    # clear of it.
    field, *letters = _rings(part.FIELD_DXF)
    xs = [x for x, _ in field]
    assert min(xs) < drawing.SECTION_FIELD_X
    assert max(xs) > spec.PLATE_WIDTH - drawing.SECTION_FIELD_X
    for ring in letters:
        ys = [y_ for _, y_ in ring]
        assert min(abs(min(ys) - y), abs(max(ys) - y)) >= 1.0, ring[0]
        assert not min(ys) <= y <= max(ys), ring[0]


def test_section_a_crop_holds_the_border_and_the_etched_field() -> None:
    # The face point stands on the raised border, the field point and the
    # crop's right end on the etched field.
    outline = _rings(part.OUTLINE_DXF)[0]
    y = drawing.SECTION_Y
    assert dxf.point_in_ring(outline, (print_spec.SECTION_FACE_X, y))
    assert not _etched(print_spec.SECTION_FACE_X, y)
    assert _etched(drawing.SECTION_FIELD_X, y)
    # The crop holds the plate's left edge and the whole thickness, and ends
    # on the field floor.
    (x0, z0), (x1, z1) = drawing.SECTION_CROP
    assert x0 < 0.0 and z0 > 0.0 and z1 < -spec.PLATE_THICKNESS
    assert x1 > drawing.SECTION_FIELD_X
    assert _etched(x1, y)


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


def test_etched_field_depth_prints_its_declared_limits_above_the_face() -> None:
    # One depth from the decorated face point (z = 0) to the field floor,
    # its limits declared as fr-nameplate RV-07 (owner ruling 2026-11-20).
    from _paths import CAD_ROOT
    from machinist_exceptions import load_exceptions

    points = print_spec.SECTION_REFERENCE_POINTS
    assert set(points) == {"face", "field"}
    assert points["face"][1] == 0.0
    assert -points["field"][1] == print_spec.FIELD_DEPTH
    assert print_spec.DRAWING_PRECISION[print_spec.SECTION_REFERENCE] == {
        "FieldDepth": 3
    }
    rows = drawing.SECTION_CALLOUTS["FieldDepth"].split("\n")
    assert rows == ["ETCHED FIELD DEPTH"]
    declared = {
        entry.id: entry
        for entry in load_exceptions(CAD_ROOT / "config", "fr_nameplate", "part")
    }
    assert "ETCHED FIELD DEPTH" in declared["RV-07"].where
    assert ".008-.012" in declared["RV-07"].where
    # The block (two stacked limits and the callout row, 4.5 mm each) keeps
    # its leader shelf above the field's outside arrow, ~5.7 mm long on the
    # r4 render, at the decorated face.
    face_y = drawing._section_xy(print_spec.SECTION_FIELD_X, 0.0)[1]
    block_bottom = drawing.SECTION_KEEP["FieldDepth"][1] - 0.00225 * (2 + len(rows))
    assert block_bottom > face_y + 0.006


def test_section_a_texts_and_caption_clear_each_other() -> None:
    # Measured r2 text blocks (8:1): a two-row value and callout is about
    # 8 mm tall and its callout row about 2.85 mm a character wide; r4's
    # measured ~9 mm, so each row here takes 4.5 mm (the limits print two
    # stacked rows) and a block's width is its longest callout row's. Each
    # block is boxed left-aligned on its dimension line (as r2 printed),
    # right-aligned on it and centred on it, so no SOLIDWORKS placement can
    # collide.
    def boxes(pick: dict) -> list[tuple[float, float, float, float]]:
        x, y = pick["text_xy"]
        rows = pick["callout"].split("\n")
        width = 0.00285 * max(len(row) for row in rows)
        half = 0.00225 * (2 + len(rows))
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
        name: {"text_xy": xy, "callout": print_spec.SECTION_CALLOUTS[name]}
        for name, xy in drawing.SECTION_KEEP.items()
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


def test_floor_under_the_etched_field_at_the_printed_worst_case() -> None:
    floor = (
        spec.PLATE_THICKNESS
        - printed_band_mm(3, unit=spec.UNIT)
        - print_spec.FIELD_DEPTH_LIMITS[1]
    )
    assert math.isclose(print_spec.FIELD_FLOOR_MIN, floor)
    # .063 - .005 - .012 = .046, owner ruling 2026-11-20 (#2313).
    assert floor == pytest.approx(0.046 * 25.4)


def test_screw_full_thread_is_the_accepted_rule_20_shortfall() -> None:
    import fr_harmonic_base_fasteners as base_fasteners

    # Ruling B1: the #4-40 x 1/4 inch fillister, .020 short per ASME B18.6.3,
    # through the plate at .063 + .005, less 0.75 of the 40 TPI pitch at its tip.
    projection = 0.250 * 25.4 - 0.508 - (0.063 + 0.005) * 25.4 - 0.75 * 0.635
    assert projection == pytest.approx(3.6386, abs=5e-4)
    assert spec.SCREW_FULL_THREAD_MIN == pytest.approx(projection, abs=1e-9)
    # Codjiflo on #2127 (rule 18): only the overlap with the base's full female
    # thread counts, which starts past its .010 entrance break.
    worst = projection - 0.010 * 25.4
    installed = base_fasteners.NAMEPLATE_INSTALLED_FULL_THREAD_MIN
    assert installed == pytest.approx(worst, abs=1e-9)
    assert (
        0.0 < base_fasteners.NAMEPLATE_INSTALLED_FULL_THREAD_ACCEPTED <= round(worst, 4)
    )
    # Still short of 1.5D of the 2.8448 major (4.267): the ruling is live.
    assert worst < 1.5 * 2.8448
    assert worst / 2.8448 == pytest.approx(1.19, abs=5e-3)


def test_declared_exceptions_name_the_printed_minimums() -> None:
    # Each owner-ruled shortfall is declared for this package, names the
    # sheet text that states it, and that text prints the spec's worst case
    # rounded down to two places.
    from _paths import CAD_ROOT
    from machinist_exceptions import load_exceptions
    import fr_harmonic_base_fasteners as base_fasteners

    declared = {
        entry.id: entry
        for entry in load_exceptions(CAD_ROOT / "config", "fr_nameplate", "part")
    }
    assert {name: entry.kind for name, entry in declared.items()} == {
        "RV-01": "accept",
        "RV-03": "minor",
        "RV-05": "minor",
        "RV-07": "accept",
    }
    for entry in declared.values():
        assert entry.reason.endswith(("(owner-accepted)", "(owner-ruled shortfall)"))
    for name in ("RV-01", "RV-05", "RV-07"):
        assert 'Owner ruling 2026-11-20 (Pedro), #2313: "A"' in declared[name].reason
    floor, screws = print_spec.MINIMUM_NOTES.splitlines()
    assert floor in declared["RV-05"].where
    assert screws in declared["RV-03"].where
    # The sheet's rows state the same facts, the screws' naming its parts.
    assert floor in drawing.MINIMUM_NOTES and screws in drawing.MINIMUM_NOTES
    # Each states its worst case in inches, rounded down to three places.
    for note, worst in (
        (floor, print_spec.FIELD_FLOOR_MIN),
        (screws, base_fasteners.NAMEPLATE_INSTALLED_FULL_THREAD_MIN),
    ):
        stated = next(word for word in note.split() if word.startswith("."))
        assert float(stated) == math.floor(worst / 25.4 * 1000.0 + 1e-9) / 1000.0
    assert print_spec.MANUFACTURING_NOTES.splitlines()[0] in declared["RV-01"].where
    # The holes' wall to the corner radius meets rule 17's .080 target at the
    # printed worst case, so no shortfall is stated (RV-04 retired).
    assert print_spec.HOLE_LIGAMENT_WORST >= WALL_TARGET_MM


def test_notes_and_callouts_carry_no_numbers_and_stay_short() -> None:
    notes = print_spec.MANUFACTURING_NOTES.splitlines()
    # Rule 7 (#1564): the DXF rows and the two stated minimums together stay
    # within four lines.
    assert len(notes) + len(drawing.MINIMUM_NOTES.splitlines()) <= 4
    assert all(len(note) <= 60 for note in notes), notes
    texts = [*notes, *drawing.SECTION_CALLOUTS.values()]
    assert not any(re.search(r"\d", text) for text in texts), texts
    # The one shop artwork by the exact path cut_release stages it at.
    assert print_spec.MANUFACTURING_NOTES.splitlines()[0] == (
        f"OUTLINE AND ETCH RESIST PER {bundle_path(print_spec.RESIST_DXF_NAME)}"
    )


def test_texts_stand_inside_the_border_and_off_the_title_block() -> None:
    points = [
        *drawing.FRONT_KEEP.values(),
        *drawing.RIGHT_KEEP.values(),
        *drawing.SECTION_KEEP.values(),
        drawing.HOLE_CALLOUT_XY,
        drawing.NOTES_XY,
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
    # Dimension texts stand off the plate face, never on the artwork.
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


def test_hole_callout_names_the_transfer_route_under_the_native_size(monkeypatch) -> None:
    # Run 20261107T102146937Z (blocker, rule 19): the tapped mate's position
    # zone is far tighter than the plate's loose edge bands. MHA-FR-01's taps
    # are spotted through these holes (fr-harmonic-base RV-01), so the callout
    # names that route on its own row under the live format text.
    assert drawing.HOLE_CALLOUT_ROUTE == "MHA-FR-01 TAPS SPOTTED THROUGH AT ASSEMBLY"
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _iface: obj)
    texts = {5: "<NUM_INST>X <MOD-DIAM><hw-diam> THRU ALL"}

    def set_text(part: int, text: str) -> None:
        assert part == 1
        texts[5] = text

    display = SimpleNamespace(GetText=lambda part: texts.get(part, ""), SetText=set_text)
    drawing._append_hole_callout_row(display, drawing.HOLE_CALLOUT_ROUTE, label="holes")
    assert texts[5] == (
        "<NUM_INST>X <MOD-DIAM><hw-diam> THRU ALL\nMHA-FR-01 TAPS SPOTTED THROUGH AT ASSEMBLY"
    )
    with pytest.raises(RuntimeError, match="cannot take"):
        drawing._append_hole_callout_row(display, drawing.HOLE_CALLOUT_ROUTE, label="holes")
