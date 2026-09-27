"""Offline contracts for sketch entities drawn in drawing views.

Every circle, line, centreline and point a drawing recipe sketches into a view
goes through ``_drawing_common.sketch_view_{circle,line,point}``: authored
direct-to-DB (sketch inference off), read back against the ask, and left
selected.  #857's post_mount_screw drew its Front tip mark at ~1.5 mm radius
on the cut end on one seat and at the asked 3.6 mm, 1 mm above, on another,
from docstring-only changes; top_frame's D-D section line was cut 4.29 degrees
oblique the same way.  The fake seat here SNAPS like inference does, so each
caller test fails against a recipe that sketches with inference on or never
reads its entity back.
"""

from __future__ import annotations

import ast
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import _drawing_common
import _stock_trim_drawing
import draw_arbor_pedestal
import draw_cylinder_gear
import draw_rocker_arm_support
import draw_top_frame

SCRIPTS = Path(__file__).resolve().parent
VIEW_ORIGIN = (0.100, 0.150)
VIEW_SCALE = 0.5  # sheet metres per view-local model metre (a 1:2 view)


def _values(array) -> tuple[float, ...]:
    return tuple(float(v) for v in getattr(array, "value", array))


class _MathPoint:
    def __init__(self, xyz) -> None:
        self.ArrayData = tuple(xyz)

    def MultiplyTransform(self, transform):
        return _MathPoint(transform(self.ArrayData))


class _SketchPoint:
    def __init__(self, seat: "_Seat", xyz) -> None:
        self.seat = seat
        self.X, self.Y, self.Z = (float(v) for v in xyz)

    def Select4(self, append: bool, data) -> bool:
        return self.seat.select(self, append, data)


class _Arc:
    """ISketchArc / ISketchSegment stand-in: what the seat actually made."""

    def __init__(self, seat: "_Seat", center, radius: float) -> None:
        self.seat = seat
        self.center = tuple(center)
        self.radius = radius

    def GetCenterPoint2(self):
        return _SketchPoint(self.seat, self.center)

    def GetRadius(self):
        return self.radius

    def Select4(self, append: bool, data) -> bool:
        return self.seat.select(self, append, data)


class _Line:
    """ISketchLine / ISketchSegment stand-in."""

    def __init__(self, seat: "_Seat", start, end, kind: str) -> None:
        self.seat = seat
        self.start = tuple(start)
        self.end = tuple(end)
        self.kind = kind
        self.Style = 0
        self.Color = -1

    def GetStartPoint2(self):
        return _SketchPoint(self.seat, self.start)

    def GetEndPoint2(self):
        return _SketchPoint(self.seat, self.end)

    def Select4(self, append: bool, data) -> bool:
        return self.seat.select(self, append, data)


class _View:
    """IView stand-in for a 1:2 view whose origin sits at ``VIEW_ORIGIN``."""

    def __init__(self, name: str) -> None:
        self.name = name

    def GetSketch(self):
        # Sheet metres -> view-local model metres.
        return SimpleNamespace(
            ModelToSketchTransform=lambda xyz: (
                (xyz[0] - VIEW_ORIGIN[0]) / VIEW_SCALE,
                (xyz[1] - VIEW_ORIGIN[1]) / VIEW_SCALE,
                0.0,
            )
        )

    # Model metres -> sheet metres (the Front's model XY is the view's XY).
    ModelToViewTransform = staticmethod(
        lambda xyz: (
            VIEW_ORIGIN[0] + xyz[0] * VIEW_SCALE,
            VIEW_ORIGIN[1] + xyz[1] * VIEW_SCALE,
            0.0,
        )
    )


class _Stop(Exception):
    """Raised by the fake once the call under test has been observed."""


class _Seat:
    """Adapter + drawing doc + sketch manager + selection manager in one.

    ``snap`` is inference: ``(dx, dy, radius factor)`` in sketch space, applied
    whenever the entity is NOT authored direct-to-DB -- or always, when
    ``honours_add_to_db`` is off (a seat that declines the preference fails
    silently, which is what the read-back is for).  Like SolidWorks, an
    inferred draw leaves the new entity selected and a direct-to-DB one does
    not.
    """

    def __init__(self) -> None:
        self.currentModel = self
        self.SketchManager = self
        self.SelectionManager = self
        self.swApp = self
        self.AddToDB = False
        self.DisplayWhenAdded = False
        self.snap: tuple[float, float, float] | None = None
        self.honours_add_to_db = True
        self.made: list[tuple[str, bool]] = []
        self.selected: list[object] = []
        self.detail_fence: object | None = None

    # adapter ------------------------------------------------------------
    def GetMathUtility(self):
        return SimpleNamespace(CreatePoint=lambda array: _MathPoint(_values(array)))

    def _get_attr_or_call(self, obj, name):
        value = getattr(obj, name, None)
        return value() if callable(value) else value

    # drawing doc ----------------------------------------------------------
    def ActivateView(self, name: str) -> bool:
        self.active = name
        return True

    def ClearSelection2(self, _all: bool) -> bool:
        self.selected = []
        return True

    def EditRebuild3(self) -> bool:
        return True

    def CreateDetailViewAt4(self, *args):
        (fence,) = self.selected
        self.detail_fence = fence
        raise _Stop

    # selection manager ----------------------------------------------------
    def CreateSelectData(self):
        return SimpleNamespace(View=None)

    def select(self, entity, append: bool, _data) -> bool:
        self.selected = [*self.selected, entity] if append else [entity]
        return True

    def GetSelectedObjectCount2(self, _mark: int) -> int:
        return len(self.selected)

    # sketch manager -------------------------------------------------------
    def _inferred(self) -> bool:
        return not (self.AddToDB and self.honours_add_to_db)

    def _made(self, kind: str, entity):
        self.made.append((kind, bool(self.AddToDB)))
        if not self.AddToDB:
            self.selected = [entity]
        return entity

    def CreateCircle(self, cx, cy, cz, px, py, _pz):
        radius = math.dist((cx, cy), (px, py))
        if self.snap is not None and self._inferred():
            dx, dy, factor = self.snap
            cx, cy, radius = cx + dx, cy + dy, radius * factor
        return self._made("circle", _Arc(self, (cx, cy, cz), radius))

    def _segment(self, kind, x0, y0, z0, x1, y1, z1):
        if self.snap is not None and self._inferred():
            dx, dy, _factor = self.snap
            x1, y1 = x1 + dx, y1 + dy
        return self._made(kind, _Line(self, (x0, y0, z0), (x1, y1, z1), kind))

    def CreateLine(self, *xyz):
        return self._segment("line", *xyz)

    def CreateCenterLine(self, *xyz):
        return self._segment("centerline", *xyz)

    def CreatePoint(self, x, y, z):
        if self.snap is not None and self._inferred():
            dx, dy, _factor = self.snap
            x, y = x + dx, y + dy
        return self._made("point", _SketchPoint(self, (x, y, z)))


@pytest.fixture
def seat(monkeypatch) -> _Seat:
    identity = lambda obj, *_: obj  # noqa: E731 - the fakes ARE the interfaces
    for module in (
        _drawing_common,
        _stock_trim_drawing,
        draw_arbor_pedestal,
        draw_cylinder_gear,
        draw_rocker_arm_support,
        draw_top_frame,
    ):
        monkeypatch.setattr(module, "_early_bound", identity, raising=False)
        monkeypatch.setattr(module, "view_name", lambda _a, view: view.name, raising=False)
    monkeypatch.setattr(_drawing_common._sw_type_info, "early_bound_or_flag", identity)
    monkeypatch.setattr(_drawing_common, "rebuild_drawing", lambda *_a, **_k: None)
    monkeypatch.setattr(draw_top_frame, "rebuild_drawing", lambda *_a, **_k: None)
    return _Seat()


# -- circle: the detail fence decides what a detail view shows -----------------


def _notch_fence_ask() -> tuple[tuple[float, float], float]:
    """The cylinder-gear notch fence in view-local model metres."""
    center = (
        draw_cylinder_gear.NOTCH_CENTER_X / 1000.0,
        (draw_cylinder_gear.TIP_RADIUS + draw_cylinder_gear.NOTCH_FLOOR_RADIUS)
        / 2000.0,
    )
    scale = draw_cylinder_gear.VIEW_SCALE
    radius = draw_cylinder_gear.NOTCH_DETAIL_RADIUS_MM * scale[0] / scale[1] / 1000.0
    return center, radius / VIEW_SCALE


def test_detail_fence_is_sketched_with_inference_off(seat) -> None:
    seat.snap = (0.0, -0.001, 0.4)
    with pytest.raises(_Stop):
        draw_cylinder_gear._notch_detail(seat, _View("Front"))
    assert seat.made == [("circle", True)]
    assert seat.AddToDB is False and seat.DisplayWhenAdded is False
    center, radius = _notch_fence_ask()
    fence = seat.detail_fence
    assert isinstance(fence, _Arc)
    assert fence.center[:2] == pytest.approx(center)
    assert fence.radius == pytest.approx(radius)


def test_a_detail_fence_the_seat_moved_raises(seat) -> None:
    seat.snap = (0.0, -0.001, 0.4)
    seat.honours_add_to_db = False
    with pytest.raises(RuntimeError, match="notch-detail fence: the circle's centre sits"):
        draw_cylinder_gear._notch_detail(seat, _View("Front"))
    assert seat.AddToDB is False
    assert seat.detail_fence is None


def test_stock_trim_cut_end_fence_is_read_back(seat) -> None:
    sheet = _stock_trim_drawing.TrimSheet(
        sheet_scale=(2.0, 1.0),
        detail_center=(0.2, 0.1),
        detail_scale=(10.0, 1.0),
        fence_radius_mm=3.6,
        cut_end_y_mm=40.0,
        detail_offset_mm=1.0,
        detail_label_xy=(0.2, 0.05),
        parent_letter_offset=(0.0, 0.0),
    )
    seat.snap = (0.0, -0.001, 0.4)
    with pytest.raises(_Stop):
        _stock_trim_drawing.end_detail(seat, _View("Front"), sheet)
    assert seat.made == [("circle", True)]
    assert seat.detail_fence.center[:2] == pytest.approx((0.0, 0.041))
    assert seat.detail_fence.radius == pytest.approx(0.0072 / VIEW_SCALE)
    seat.honours_add_to_db = False
    with pytest.raises(RuntimeError, match="cut-end detail fence: the circle's centre"):
        _stock_trim_drawing.end_detail(seat, _View("Front"), sheet)


def test_a_detail_fence_radius_the_seat_moved_raises(seat) -> None:
    seat.snap = (0.0, 0.0, 0.4)
    seat.honours_add_to_db = False
    with pytest.raises(RuntimeError, match="notch-detail fence: the circle's radius sits"):
        draw_cylinder_gear._notch_detail(seat, _View("Front"))


# -- line: hidden edges in view-local coordinates --------------------------------


def test_bore_hidden_lines_are_sketched_with_inference_off(seat) -> None:
    seat.snap = (0.0, 0.0004, 1.0)
    draw_arbor_pedestal._add_bore_hidden_lines(seat, _View("Top"))
    assert seat.made == [("line", True)] * 4
    assert seat.AddToDB is False and seat.DisplayWhenAdded is False


def test_a_bore_hidden_line_the_seat_moved_raises(seat) -> None:
    # 0.4 mm in view space is 0.2 mm on the 1:2 sheet: four times the bar.
    seat.snap = (0.0, 0.0004, 1.0)
    seat.honours_add_to_db = False
    with pytest.raises(
        RuntimeError, match=r"arbor bore hidden line .*end point sits 0\.2 mm"
    ):
        draw_arbor_pedestal._add_bore_hidden_lines(seat, _View("Top"))


# -- centreline: view-local and sheet coordinates ----------------------------------


def test_view_centerline_is_read_back(seat) -> None:
    seat.snap = (0.0003, 0.0, 1.0)
    seat.honours_add_to_db = False
    with pytest.raises(RuntimeError, match="front wall centerline: the centerline's end point"):
        draw_rocker_arm_support._create_view_centerline(
            seat, _View("Front"), start_xy=(-0.01, 0.0), end_xy=(0.01, 0.0),
            label="front wall",
        )


def test_view_centerline_lands_in_view_coordinates(seat) -> None:
    seat.snap = (0.0003, 0.0, 1.0)
    line = draw_rocker_arm_support._create_view_centerline(
        seat, _View("Front"), start_xy=(-0.01, 0.0), end_xy=(0.01, 0.0),
        label="front wall",
    )
    assert seat.made == [("centerline", True)]
    assert (line.start[:2], line.end[:2]) == ((-0.01, 0.0), (0.01, 0.0))


def test_owned_centerlines_map_sheet_points_into_the_view(seat, monkeypatch) -> None:
    monkeypatch.setattr(
        draw_top_frame, "model_point_in_view",
        lambda _a, view, xyz, **_k: view.ModelToViewTransform(xyz)[:2],
    )
    seat.snap = (0.0, 0.0002, 1.0)
    segments = draw_top_frame._add_view_centerlines(
        seat, _View("Section"), (((10.0, -5.0, 0.0), (10.0, 5.0, 0.0)),)
    )
    assert seat.made == [("centerline", True)]
    (segment,) = segments
    assert segment.start[:2] == pytest.approx((0.010, -0.005))
    assert segment.end[:2] == pytest.approx((0.010, 0.005))
    assert segment.Color == 0
    seat.honours_add_to_db = False
    with pytest.raises(RuntimeError, match="owned drawing centreline 0"):
        draw_top_frame._add_view_centerlines(
            seat, _View("Section"), (((10.0, -5.0, 0.0), (10.0, 5.0, 0.0)),)
        )


# -- point: a theoretical datum is held to exactness -------------------------------


def test_theoretical_datum_point_is_read_back_exactly(seat) -> None:
    seat.snap = (1e-6, 0.0, 1.0)
    point = _drawing_common.create_view_theoretical_datum(
        seat, _View("Front"), point_xy=(0.02, -0.01), label="corner"
    )
    assert seat.made == [("point", True)]
    assert (point.X, point.Y) == (0.02, -0.01)
    seat.honours_add_to_db = False
    # 1 um of drift would pass the presentation bar; a datum is exact.
    with pytest.raises(RuntimeError, match="corner theoretical datum: the point's position sits"):
        _drawing_common.create_view_theoretical_datum(
            seat, _View("Front"), point_xy=(0.02, -0.01), label="corner"
        )


# -- the helpers themselves ----------------------------------------------------------


def test_helpers_hand_the_seat_back_when_create_raises(seat) -> None:
    seat.AddToDB = True
    seat.DisplayWhenAdded = False

    def boom(*_args):
        raise RuntimeError("CreateCircle exploded")

    seat.CreateCircle = boom
    with pytest.raises(RuntimeError, match="exploded"):
        _drawing_common.sketch_view_circle(
            seat, _View("Front"), (0.1, 0.15), 0.01, coords="sheet", label="x"
        )
    assert seat.AddToDB is True and seat.DisplayWhenAdded is False


def test_sheet_tolerance_scales_with_the_view(seat) -> None:
    """0.05 mm on the sheet is 0.1 mm in a 1:2 view's own sketch."""
    seat.honours_add_to_db = False
    seat.snap = (0.00009, 0.0, 1.0)  # 0.045 mm on the sheet
    _drawing_common.sketch_view_point(
        seat, _View("Front"), (0.01, 0.01), coords="view", label="inside"
    )
    seat.snap = (0.00011, 0.0, 1.0)  # 0.055 mm on the sheet
    with pytest.raises(RuntimeError, match=r"outside: the point's position sits 0\.055 mm"):
        _drawing_common.sketch_view_point(
            seat, _View("Front"), (0.01, 0.01), coords="view", label="outside"
        )


def test_the_sheet_sketch_takes_sheet_coordinates_as_they_are(seat) -> None:
    line = _drawing_common.sketch_view_line(
        seat, None, (0.2, 0.1), (0.2, 0.3), kind="centerline", coords="sheet",
        label="sheet axis",
    )
    assert (line.start[:2], line.end[:2]) == ((0.2, 0.1), (0.2, 0.3))
    assert seat.selected == [line]
    with pytest.raises(ValueError, match="sheet coordinates"):
        _drawing_common.sketch_view_line(
            seat, None, (0.2, 0.1), (0.2, 0.3), coords="view", label="bad"
        )


def test_the_new_entity_is_left_selected(seat) -> None:
    """Direct-to-DB leaves nothing selected; Crop2/CreateDetailViewAt4 need it."""
    circle = _drawing_common.sketch_view_circle(
        seat, _View("Front"), (0.12, 0.16), 0.005, coords="sheet", label="fence"
    )
    assert seat.selected == [circle]
    assert circle.center[:2] == pytest.approx((0.04, 0.02))
    assert circle.radius == pytest.approx(0.01)


# -- nothing sketches into a view outside the helpers ---------------------------------

_SKETCH_CREATORS = {"CreateCircle", "CreateLine", "CreateCenterLine"}
_HELPERS = {"sketch_view_circle", "sketch_view_line", "sketch_view_point"}


def _raw_sketch_calls(path: Path) -> list[str]:
    """Direct SketchManager ``Create*`` calls outside the guarded helpers.

    ``CreatePoint`` is ambiguous by name: ``IMathUtility.CreatePoint`` takes
    one ``double[]`` and is how every recipe maps a point through a transform;
    ``ISketchManager.CreatePoint`` takes ``x, y, z``.  Arity tells them apart
    whatever the receiver is called.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []

    def visit(node: ast.AST, owner: str | None) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            owner = node.name
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            name = node.func.attr
            creator = name in _SKETCH_CREATORS or (
                name == "CreatePoint" and len(node.args) + len(node.keywords) != 1
            )
            if creator and owner not in _HELPERS:
                found.append(f"{path.name}:{node.lineno} {owner} {name}")
        for child in ast.iter_child_nodes(node):
            visit(child, owner)

    visit(tree, None)
    return found


def _drawing_modules() -> list[Path]:
    """Every recipe or helper that drives a drawing sheet.

    ``draw_*`` recipes and ``_drawing*`` helpers by name, plus any other
    non-test module built on ``_drawing_common`` (``_stock_trim_drawing``'s
    cut-end fence is how a sweep of names alone missed one).
    """
    modules = []
    for path in sorted(SCRIPTS.glob("*.py")):
        if path.name.startswith("test_"):
            continue
        named = path.name.startswith(("draw_", "_drawing"))
        source = path.read_text(encoding="utf-8")
        if named or "_drawing_common" in source:
            modules.append(path)
    return modules


def test_drawing_recipes_sketch_only_through_the_guarded_helpers() -> None:
    modules = _drawing_modules()
    assert SCRIPTS / "_stock_trim_drawing.py" in modules
    assert len(modules) > 10
    offenders = [call for module in modules for call in _raw_sketch_calls(module)]
    assert offenders == [], (
        "sketch view entities through _drawing_common.sketch_view_circle/"
        f"_line/_point (direct-to-DB, read back): {offenders}"
    )


def test_the_guard_sees_a_raw_sketch_call(tmp_path) -> None:
    probe = tmp_path / "draw_probe.py"
    probe.write_text(
        "def fence(manager, utility, arr):\n"
        "    utility.CreatePoint(arr)\n"
        "    manager.CreatePoint(0.0, 0.0, 0.0)\n"
        "    return manager.CreateCircle(0, 0, 0, 1, 0, 0)\n",
        encoding="utf-8",
    )
    assert _raw_sketch_calls(probe) == [
        "draw_probe.py:3 fence CreatePoint",
        "draw_probe.py:4 fence CreateCircle",
    ]
