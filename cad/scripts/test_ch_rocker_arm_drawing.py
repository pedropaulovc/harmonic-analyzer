"""Offline contracts for the rocker-arm drawing."""

from __future__ import annotations

import ast
import json
import math
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import ch_rocker_arm_notes
import ch_rocker_arm_spec
import draw_ch_rocker_arm as drawing
import build_ch_rocker_arm as arm
from _drawing_layout_check import DrawableRegion
from _layout_geometry import AnnotationGeometry, Box, Segment, segment_box_distance, text_overlap
from _drawing_registry import DRAWINGS_BY_NAME
from dt_cone_pivot_post_installation import MECHANISM_X_SHIFT
from _hole_spec import blind_cut_dia_mm


def _front_xy(mx: float, my: float) -> tuple[float, float]:
    """Offline projection fixture, never production or native layout evidence."""
    scale = drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1] / 1000.0
    return (drawing.FRONT_CENTER[0] + mx * scale,
            drawing.FRONT_CENTER[1] + (my - drawing.TOP_END_Y / 2.0) * scale)


def _end_xy(mx: float, my: float) -> tuple[float, float]:
    scale = drawing.END_SCALE[0] / drawing.END_SCALE[1] / 1000.0
    cx = (drawing.BOT_END_X + drawing.ROD_TIP_X) / 2.0
    cy = (drawing._BOT_END_Y + drawing.TOP_END_Y) / 2.0
    return (drawing.END_CENTER[0] + (mx - cx) * scale,
            drawing.END_CENTER[1] + (my - cy) * scale)


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-rocker-arm.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-rocker-arm.pdf")
    assert drawing.PNG.as_posix().endswith("/png/ch-rocker-arm_drawing.png")
    assert DRAWINGS_BY_NAME["ch_rocker_arm"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: build marks exactly the spec's map, the drawing keeps
    # exactly its union across the per-view keep-maps.
    assert arm.DRAWING_DIMENSIONS is ch_rocker_arm_notes.DRAWING_DIMENSIONS
    marked = set().union(*ch_rocker_arm_notes.DRAWING_DIMENSIONS.values())
    keeps = (drawing.FRONT_KEEP, drawing.HUB_KEEP, drawing.END_KEEP, drawing.RIGHT_KEEP)
    kept = set().union(*keeps)
    assert kept == marked
    assert sum(map(len, keeps)) == len(marked)
    assert not hasattr(drawing, "TOP_KEEP")


def test_draw_view_math_matches_the_spec() -> None:
    # The drawing's view math reads the spec's nominal spans, not a divergent
    # copy; the spec's geometry must match the part the build actually builds.
    assert (drawing.ROD_HOLE_X, drawing.TOP_END_Y) == (
        ch_rocker_arm_spec.ROD_HOLE_X,
        ch_rocker_arm_spec.TOP_END_Y,
    )
    assert ch_rocker_arm_spec.CURVE_RADIUS == arm.CURVE_RADIUS
    assert ch_rocker_arm_spec.ARM_DEPTH == arm.ARM_DEPTH
    assert ch_rocker_arm_spec.ARM_THICKNESS == arm.ARM_THICKNESS
    assert ch_rocker_arm_spec.TOP_ARC_LEN == arm.TOP_ARC_LEN
    assert ch_rocker_arm_spec.BOT_ARC_LEN == arm.BOT_ARC_LEN
    assert ch_rocker_arm_spec.TIP_FACE == arm.TIP_FACE
    assert ch_rocker_arm_spec.ROD_HOLE_X == arm.ROD_HOLE_X
    assert arm.ROD_HOLE_SPEC is ch_rocker_arm_spec.ROD_HOLE_SPEC
    assert drawing._ROD_HOLE_DIA == blind_cut_dia_mm(ch_rocker_arm_spec.ROD_HOLE_SPEC)


def test_rod_pin_follows_the_recentered_cam_and_recloses_neutral_y() -> None:
    assert math.isclose(
        ch_rocker_arm_spec.ROD_HOLE_X,
        127.3738 - MECHANISM_X_SHIFT,
        abs_tol=1e-12,
    )
    assert math.isclose(ch_rocker_arm_spec.ROD_HOLE_Y, 16.456064115939025, abs_tol=1e-12)
    assert ch_rocker_arm_spec.ROD_HOLE_ABOVE_BOTTOM == arm.ROD_HOLE_ABOVE_BOTTOM
    assert ch_rocker_arm_spec.ROD_HOLE_Y == arm.ROD_HOLE_Y


def test_sheet_runs_at_1_to_2() -> None:
    assert drawing.SHEET_SCALE == (1.0, 2.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 2)" in source
    assert ch_rocker_arm_notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:4"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_are_functional_metric_and_not_title_block_duplicates() -> None:
    notes = ch_rocker_arm_notes.DRAWING_NOTES
    # Concentricity applies to nominal arcs, not independent profile deviations.
    assert "NOMINAL ARCS CONCENTRIC ON THAT PLANE." in notes
    assert "R800" not in notes
    assert "R816" not in notes
    # Processes and through conditions belong to the native size callouts.
    assert "(1X)" in notes
    assert "#47" not in notes
    assert "PIVOT HOLE: REAM" not in notes
    assert "16.00 REF" not in notes
    assert "ALL HOLES THRU" not in notes
    # Profile nominals print once, as native BASIC dimensions, not as prose.
    assert "808.00 REF FROM THE PIVOT" not in notes
    assert "INTEGRAL HUB DIA" not in notes
    assert "HUB LENGTH SETS THE PITCH" in " ".join(notes.split())
    assert "ARC LENGTHS" not in notes
    assert "EACH END:" not in notes
    assert re.findall(r"^(\d+)\.", notes, re.MULTILINE) == ["1", "2", "3", "4"]
    assert "UPPER ARC: AMPLITUDE-BAR CONTACT." in notes
    assert "LOWER ARC: MOVING STRAP ENVELOPE." in notes
    assert "ROD-PIN SETS CONNECTING-ROD GEOMETRY." in notes
    assert (
        f"HUB OD COAXIAL WITH PIVOT BORE WITHIN Ø{ch_rocker_arm_spec.HUB_COAXIALITY_DIA:.2f} (TURN HUB AND REAM BORE IN ONE SETUP)"
        in " ".join(line.strip() for line in notes.splitlines())
    )
    assert "11.5 IN" not in notes
    assert "0.22 IN" not in notes
    # General tolerances live in the title block ONLY.
    assert "LINEAR +/-" not in notes
    assert not re.search(r"\b(?:\d+\s*)?BA\b", notes)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert re.search(
        r'add_property_linked_note\(\s*adapter, "Manufacturing Notes"', source
    )


def test_native_gdt_and_finish_present() -> None:
    """Native print arguments retain the part-owned limit and A-B-C frame."""
    from _drawing_hole_callout import add_native_hole_callout

    assert drawing.add_native_hole_callout is add_native_hole_callout
    assert drawing.ROD_HOLE.fields["dia"][1] == (
        "ROD_HOLE_SPEC",
        ("_hole_spec", "NUMBER_DRILL_MM"),
        ("_drawing_hole_callout", "add_native_hole_callout"),
    )
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # A = pivot bore axis, B = broad face (right end view), C = rod-side tip
    # face; the rod-pin position frame references all three.
    assert source.count("add_datum_feature(") == 3
    # Datum A's leader runs oblique, 45 deg off both centre-mark axes.
    assert math.degrees(drawing.PIVOT_DATUM_ANGLE) % 90.0 == pytest.approx(45.0)
    assert 'label="pivot bore cylindrical datum feature"' in source
    assert source.count("shoulder=True") == 1
    tree = ast.parse(source)
    frames = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "add_feature_control_frame"
        and any(
            keyword.arg == "characteristic"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "position"
            for keyword in node.keywords
        )
    ]
    assert len(frames) == 1
    keywords = {keyword.arg: keyword.value for keyword in frames[0].keywords}
    # Evaluate the actual native print-call arguments without invoking COM.
    printed_datums = eval(
        compile(ast.Expression(keywords["datums"]), drawing.__file__, "eval"),
        vars(drawing),
    )
    assert printed_datums == ("A", "B", "C")
    printed_tolerance = eval(
        compile(ast.Expression(keywords["tolerance"]), drawing.__file__, "eval"),
        vars(drawing),
    )
    assert (
        printed_tolerance
        == ch_rocker_arm_spec.GEOMETRIC_TOLERANCES_MM["rod-pin hole position"]
    )
    assert drawing.ROD_HOLE.fields["position_dia"][0] == float(printed_tolerance)
    assert ast.unparse(keywords["diameter"]) == "True"
    assert 'characteristic="position"' in source
    assert "add_surface_finish(" in source
    assert "add_native_hole_callout(" in source
    # r743-p1s-B: both rod-pin annotations take the diameter-picked edge.
    assert "edge_xy=rod_rim" not in source
    assert source.count("edge=rod_hole_edge") == 1
    assert source.count("edge_entity=rod_hole_edge") == 1


def test_profile_nominals_are_kept_natively_without_note_only_duplicates() -> None:
    names = {"TopRadius", "BottomRadius", "TopAbovePivot"}
    assert drawing.BASIC_PROFILE_DIMENSIONS == names
    assert names <= drawing.FRONT_KEEP.keys()
    assert not hasattr(drawing, "NOTE_ONLY_DIMENSIONS")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    definitions = {
        node.name: node for node in ast.parse(source).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for caller, callee, arguments in (
        ("build", "_add_rocker_outline_dimensions", ("adapter", "front")),
        ("_add_rocker_outline_dimensions", "_basic_profile_dimensions", ("adapter", "annotations")),
    ):
        calls = [
            node for node in ast.walk(definitions[caller])
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == callee
        ]
        assert len(calls) == 1
        assert tuple(ast.unparse(arg) for arg in calls[0].args) == arguments
    assert "_add_arc_profiles(adapter, front)" in source


def test_basic_radius_text_positions_are_outside_their_parent_circles() -> None:
    """Inside-circle R800 placement retained a centre tail on the native sheet."""
    centre_model_y = (
        drawing.PIVOT_MID_Y + drawing.TOP_EDGE_ABOVE_PIVOT + drawing.R_TOP
    )
    centre = _front_xy(0.0, centre_model_y)
    for name, radius in (
        ("TopRadius", drawing.R_TOP),
        ("BottomRadius", drawing.R_BOTTOM),
    ):
        rendered_radius = math.dist(
            centre, _front_xy(0.0, centre_model_y + radius)
        )
        assert math.dist(centre, drawing.FRONT_KEEP[name]) > rendered_radius
    # Negative control: the former top label lay inside the same nominal circle.
    top_rendered_radius = math.dist(
        centre, _front_xy(0.0, centre_model_y + drawing.R_TOP)
    )
    assert math.dist(centre, (0.130, 0.218)) < top_rendered_radius


def test_radius_text_and_profile_requests_use_the_approved_clearance_corridors() -> None:
    """Source placement hypotheses, NOT current native clearance evidence."""
    assert drawing.FRONT_KEEP["TopRadius"] == (0.145, 0.136)
    assert drawing.FRONT_KEEP["BottomRadius"] == (0.170, 0.128)
    assert drawing.ARC_PROFILE_FRAME_XY == {
        "TopRadius": (0.130, 0.207), "BottomRadius": (0.020, 0.160),
    }
    assert drawing.ARC_PROFILE_PICK_X_MM == {"TopRadius": -130.0, "BottomRadius": -110.0}


class _ProfileDisplay:
    """Model COM property writes, including silently ignored setters."""

    def __init__(self, ignored: str | None = None) -> None:
        self.ignored = ignored
        self.writes: list[tuple[str, object]] = []
        object.__setattr__(self, "ShortenedRadius", True)
        object.__setattr__(self, "ArcExtensionLineOrOppositeSide", True)
        object.__setattr__(self, "ArrowSide", 0)
        object.__setattr__(self, "SolidLeader", True)

    def __setattr__(self, name: str, value: object) -> None:
        if name in {"ShortenedRadius", "ArcExtensionLineOrOppositeSide", "ArrowSide", "SolidLeader"}:
            self.writes.append((name, value))
            if name == self.ignored:
                return
        object.__setattr__(self, name, value)


def _profile_annotations(monkeypatch: pytest.MonkeyPatch, displays: dict) -> list:
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, ann: ann.name)
    return [
        SimpleNamespace(name=name, GetSpecificAnnotation=lambda display=display: display)
        for name, display in displays.items()
    ]


def test_basic_profile_dimensions_converts_all_three_and_trims_only_radius_leaders(
    bound: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = object()
    displays = {
        name: _ProfileDisplay()
        for name in ("TopRadius", "BottomRadius", "TopAbovePivot", "PivotDia")
    }
    annotations = _profile_annotations(monkeypatch, displays)
    calls = []
    monkeypatch.setattr(
        drawing, "set_basic_dimension",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    drawing._basic_profile_dimensions(adapter, annotations)
    assert calls == [
        ((adapter, displays[name]), {"label": f"arc-system {name}"})
        for name in ("TopRadius", "BottomRadius", "TopAbovePivot")
    ]
    for name in ("TopRadius", "BottomRadius"):
        assert displays[name].writes == [
            ("ShortenedRadius", False),
            ("ArcExtensionLineOrOppositeSide", False),
            ("ArrowSide", 1),
            ("SolidLeader", False),
        ]
        assert displays[name].ShortenedRadius is False
        assert displays[name].ArcExtensionLineOrOppositeSide is False
        assert displays[name].ArrowSide == 1
        assert displays[name].SolidLeader is False
    assert displays["TopAbovePivot"].writes == []
    assert displays["PivotDia"].writes == []


@pytest.mark.parametrize("missing", ["TopRadius", "BottomRadius", "TopAbovePivot"])
def test_basic_profile_dimensions_rejects_each_missing_nominal(
    bound: None, monkeypatch: pytest.MonkeyPatch, missing: str,
) -> None:
    displays = {
        name: _ProfileDisplay()
        for name in ("TopRadius", "BottomRadius", "TopAbovePivot")
        if name != missing
    }
    annotations = _profile_annotations(monkeypatch, displays)
    monkeypatch.setattr(drawing, "set_basic_dimension", lambda *_args, **_kwargs: None)
    with pytest.raises(RuntimeError, match=f"BASIC dimensions missing:.*{missing}"):
        drawing._basic_profile_dimensions(object(), annotations)


@pytest.mark.parametrize("radius", ["TopRadius", "BottomRadius"])
@pytest.mark.parametrize("ignored", [
    "ShortenedRadius", "ArcExtensionLineOrOppositeSide", "ArrowSide", "SolidLeader",
])
def test_basic_profile_dimensions_rejects_ignored_radius_flags(
    bound: None, monkeypatch: pytest.MonkeyPatch, radius: str, ignored: str,
) -> None:
    displays = {
        name: _ProfileDisplay(ignored if name == radius else None)
        for name in ("TopRadius", "BottomRadius", "TopAbovePivot")
    }
    annotations = _profile_annotations(monkeypatch, displays)
    monkeypatch.setattr(drawing, "set_basic_dimension", lambda *_args, **_kwargs: None)
    with pytest.raises(RuntimeError, match=f"{radius} retained its centre-directed radius leader"):
        drawing._basic_profile_dimensions(object(), annotations)


def test_arc_profiles_attach_two_native_frames_to_nominal_circle_edges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, front = object(), object()
    monkeypatch.setattr(drawing, "_project", lambda _adapter, _view, points, **_kwargs: [
        _front_xy(x * 1000.0, y * 1000.0) for x, y, _z in points
    ])
    edges = {1600.0: object(), 1632.0: object()}
    picks, frames = [], []

    def circle_edge(actual_adapter, actual_view, diameter):
        assert actual_adapter is adapter
        assert actual_view is front
        picks.append(diameter)
        return edges[diameter]

    monkeypatch.setattr(drawing, "visible_circle_edge", circle_edge)
    native_frames = {"TopRadius": object(), "BottomRadius": object()}

    def add_frame(*args, **kwargs):
        frames.append((args, kwargs))
        return native_frames[("TopRadius", "BottomRadius")[len(frames) - 1]]

    monkeypatch.setattr(drawing, "add_feature_control_frame", add_frame)
    assert drawing._add_arc_profiles(adapter, front) == native_frames
    assert picks == [1600.0, 1632.0]
    assert len(frames) == 2
    scale = drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1] / 1000.0
    for (args, kwargs), name, radius, model_x, frame_xy, outside in zip(
        frames,
        ("TopRadius", "BottomRadius"),
        (800.0, 816.0),
        (-130.0, -110.0),
        ((0.130, 0.207), (0.020, 0.160)),
        ("0.5", "0"),
    ):
        assert args == (adapter, front)
        assert kwargs["edge_entity"] is edges[2.0 * radius]
        assert kwargs["characteristic"] == "profile_surface"
        assert kwargs["tolerance"] == "0.5"
        assert kwargs["outside_disposition"] == outside
        assert kwargs["datums"] == ("A", "B", "C")
        assert not kwargs.get("diameter", False)
        assert not kwargs.get("all_around", False)
        assert "edge_xy" not in kwargs
        assert kwargs["label"] == f"arc-system {name} profile"
        assert kwargs["frame_xy"] == frame_xy
        sheet_x, sheet_y = kwargs["leader_attach_xy"]
        x = (sheet_x - drawing.FRONT_CENTER[0]) / scale
        y = (sheet_y - drawing.FRONT_CENTER[1]) / scale + drawing.TOP_END_Y / 2.0
        assert x == pytest.approx(model_x)
        assert y < ch_rocker_arm_spec.CENTER_Y
        assert math.hypot(x, y - ch_rocker_arm_spec.CENTER_Y) == pytest.approx(radius)


_REAM_ROW = Box(0.1040, 0.1444, 0.1561, 0.1480)
_R816_ROW = Box(0.0815, 0.1512, 0.1032, 0.1547)
# R8 native readbacks at the former (20,134) request, not a frame-width guess.
_R8_LOWER_FRAME_WIDTH_M = 0.047339
_R8_RIGHT_SHOULDER_M = 0.006350
_R8_LOWER_LANDING = (0.130000, 0.170752)


@pytest.mark.parametrize("junction", [(0.1056, 0.1185), (0.0937, 0.1015)])
def test_observed_r6_r7_profile_junctions_intersect_ream_row(junction) -> None:
    """Recorded native junctions, not a side inferred from the frame request."""
    segment = Segment(*junction, 0.1300, 0.1708, "leader")
    target = AnnotationGeometry("REAM +0.03", "hole-callout", "front")
    assert segment_box_distance(segment, _REAM_ROW) == 0.0
    penetration, _span = text_overlap(segment, target, _REAM_ROW)
    assert penetration > 0.0036


def test_r7_cannot_be_proved_clear_from_a_guessed_left_junction() -> None:
    guessed = Segment(0.040 - 0.0064, 0.105 - 0.0035, 0.130, 0.1708, "leader")
    observed = Segment(0.0937, 0.1015, 0.130, 0.1708, "leader")
    assert segment_box_distance(guessed, _REAM_ROW) > drawing.ARC_PROFILE_TEXT_CLEARANCE_M
    assert segment_box_distance(observed, _REAM_ROW) == 0.0


def test_observed_r8_profile_route_intersects_actual_basic_r816_row() -> None:
    observed = Segment(0.073689, 0.130500, *_R8_LOWER_LANDING, "leader")
    target = AnnotationGeometry("BASIC R816", "dim", "front")
    assert segment_box_distance(observed, _R816_ROW) == 0.0
    penetration, _span = text_overlap(observed, target, _R816_ROW)
    assert penetration > 0.0
    assert segment_box_distance(observed, _REAM_ROW) > drawing.ARC_PROFILE_TEXT_CLEARANCE_M


def test_historical_r9_prediction_clears_both_r8_rows_independent_of_r10() -> None:
    """Historical observed-algorithm regression, not proof of current placement."""
    assert drawing.ARC_PROFILE_TEXT_CLEARANCE_M == 0.001
    frame_x, frame_y = (0.020, 0.129)
    head = (frame_x + _R8_LOWER_FRAME_WIDTH_M, frame_y - 0.0035)
    elbow = (head[0] + _R8_RIGHT_SHOULDER_M, head[1])
    assert head == pytest.approx((0.067339, 0.125500))
    assert elbow == pytest.approx((0.073689, 0.125500))
    predicted = (Segment(*head, *elbow, "leader"), Segment(*elbow, *_R8_LOWER_LANDING, "leader"))
    for box, predicted_gap_mm in ((_REAM_ROW, 1.448), (_R816_ROW, 1.547)):
        distance = min(segment_box_distance(segment, box) for segment in predicted)
        assert distance >= drawing.ARC_PROFILE_TEXT_CLEARANCE_M
        assert distance * 1000.0 == pytest.approx(predicted_gap_mm, abs=0.002)


def _native_line(x0, y0, x1, y1):
    return [0, 0, 0, 0, x0, y0, 0, x1, y1, 0]


class _ClearanceDisplayData:
    """Method-shaped native reads; the real dump/parser are NOT replaced."""

    def __init__(self, texts, lines):
        self.texts, self.lines = texts, lines

    def GetLineCount(self):  # noqa: N802
        return len(self.lines)

    def GetLineAtIndex3(self, index):  # noqa: N802
        return self.lines[index]

    def GetTextCount(self):  # noqa: N802
        return len(self.texts)

    def GetTextAtIndex(self, index):  # noqa: N802
        return self.texts[index]["t"]

    def GetTextPositionAtIndex(self, index):  # noqa: N802
        return self.texts[index]["pos"]

    def GetTextHeightAtIndex(self, index):  # noqa: N802
        return self.texts[index]["h"]

    def GetTextRefPositionAtIndex(self, index):  # noqa: N802
        return self.texts[index].get("ref", 1)

    def GetTextAngleAtIndex(self, index):  # noqa: N802
        return self.texts[index].get("ang", 0.0)

    def GetTextFontAtIndex(self, index):  # noqa: N802
        return "Arial"

    def GetTextLineSpacingAtIndex(self, index):  # noqa: N802
        return 0.0

    def GetTextInBoxWidthAtIndex(self, index):  # noqa: N802
        return 0.0

    def __getattr__(self, name):
        # Unused primitive classes have an authoritative zero count, not None.
        if name in {
            "GetArcCount", "GetArrowHeadCount", "GetPolyLineCount",
            "GetPolygonCount", "GetTriangleCount", "GetEllipseCount",
        }:
            return lambda: 0
        raise AttributeError(name)


class _ClearanceAnnotation:
    OwnerType, Visible, Layer = 0, 1, ""

    def __init__(self, name, position, data, *, leaders=(), kind=5, hole_callout=True):
        self.name, self.position, self.data = name, position, data
        self.leaders, self.kind = list(leaders), kind
        self.hole_callout = hole_callout

    def GetName(self):  # noqa: N802
        return self.name

    def GetType(self):  # noqa: N802
        return self.kind

    def GetPosition(self):  # noqa: N802
        return self.position

    def GetDisplayData(self):  # noqa: N802
        return self.data

    def GetLeaderCount(self):  # noqa: N802
        return len(self.leaders)

    def GetLeaderPointsAtIndex(self, index):  # noqa: N802
        return self.leaders[index]

    def GetSpecificAnnotation(self):  # noqa: N802
        return SimpleNamespace(IsHoleCallout=lambda: self.hole_callout)


@pytest.fixture
def native_profile_clearance(monkeypatch):
    # Historical native records intentionally stay independent of R10 anchors.
    import _drawing_layout_audit

    monkeypatch.setattr(_drawing_layout_audit, "_early_bound", lambda obj, _iface: obj)
    logs = []
    monkeypatch.setattr(drawing._telemetry, "info", logs.append)

    def frame(name, xy, points, width):
        x, y = xy
        corners = [(x, y), (x + width, y), (x + width, y - 0.007), (x, y - 0.007)]
        lines = [_native_line(*a, *b) for a, b in zip(corners, corners[1:] + corners[:1])]
        data = _ClearanceDisplayData(
            [{"t": "PROFILE", "pos": [x + 0.001, y - 0.004, 0.0], "h": 0.002}],
            lines,
        )
        return _ClearanceAnnotation(name, (*xy, 0.00125), data, leaders=[points])

    top = frame(
        "DetailTop", (0.114, 0.228),
        [0.114, 0.2245, 0.00125, 0.10765, 0.2245, 0.00125, 0.125, 0.179476, 0.000625],
        width=0.0512,
    )
    bottom = frame(
        "DetailBottom", (0.020, 0.129),
        [0.067339, 0.1255, 0.00125, 0.073689, 0.1255, 0.00125, *_R8_LOWER_LANDING, 0.000625],
        width=_R8_LOWER_FRAME_WIDTH_M,
    )
    ream = _ClearanceAnnotation(
        "PivotReam", (0.13005, 0.1462, 0),
        _ClearanceDisplayData(
            [{"t": "REAM +0.03", "pos": [0.104, 0.1444, 0], "h": 0.0036}],
            [_native_line(0.104, 0.1444, 0.1561, 0.1444)],
        ),
        kind=4,
    )
    # Synthetic native text runs reproduce R8's actual row bbox. Individual
    # run origins are fake data, not additional observations from the seat.
    r816 = _ClearanceAnnotation(
        "BasicR816", (0.0815, 0.1512, 0.00125),
        _ClearanceDisplayData(
            [
                {"t": "R", "pos": [0.0815, 0.1512, 0.00125], "h": 0.0035},
                {"t": "816.00", "pos": [0.09018, 0.1512, 0.00125], "h": 0.0035},
            ],
            [],
        ),
        kind=4, hole_callout=False,
    )
    annotations = [top, bottom, ream, r816]
    front = SimpleNamespace(GetAnnotations=lambda: annotations)
    profiles = {
        "TopRadius": SimpleNamespace(GetAnnotation=lambda: top),
        "BottomRadius": SimpleNamespace(GetAnnotation=lambda: bottom),
    }
    return SimpleNamespace(
        adapter=object(), front=front, profiles=profiles, top=top, bottom=bottom,
        ream=ream, r816=r816, annotations=annotations, logs=logs,
    )


def test_native_profile_guard_logs_actual_position_frame_and_leaders(native_profile_clearance):
    case = native_profile_clearance
    case.bottom.position = (0.021, 0.130, 0.00125)  # request != native readback
    drawing._require_arc_profile_clearance(case.adapter, case.front, case.profiles)
    text = "\n".join(case.logs)
    assert "requested_frame_mm=(20.0, 160.0)" in text
    assert "actual_GetPosition_mm=(21.0, 130.0, 1.25)" in text
    assert "native_frame_ink_bbox_mm=" in text
    assert "native_leader_points_mm=" in text
    assert "landing_mm=[(130.0, 170.752, 0.625)]" in text
    assert "minimum_clearance_mm=" in text
    assert "required_clearance_mm=1.000" in text
    assert "PivotReam" in text


@pytest.mark.parametrize("frame_request,junction", [
    ((0.112, 0.122), (0.1056, 0.1185)),
    ((0.040, 0.105), (0.0937, 0.1015)),
])
def test_native_profile_guard_refuses_observed_crossings(
    native_profile_clearance, monkeypatch, frame_request, junction,
):
    case = native_profile_clearance
    monkeypatch.setitem(drawing.ARC_PROFILE_FRAME_XY, "BottomRadius", frame_request)
    case.bottom.position = (*frame_request, 0)
    case.bottom.leaders = [[
        junction[0] - 0.003, junction[1], 0, *junction, 0, 0.130, 0.1708, 0,
    ]]
    with pytest.raises(RuntimeError) as exc:
        drawing._require_arc_profile_clearance(case.adapter, case.front, case.profiles)
    message = str(exc.value)
    for evidence in (
        "BottomRadius", "PivotReam", "requested_frame_mm=", "actual_GetPosition_mm=",
        "native_leader_points_mm=", "bbox_mm=[104.0,144.4]..[156.1,148.0]mm",
        "minimum_clearance_mm=0.000", "penetration_mm=", "native_segment=",
    ):
        assert evidence in message
    assert any("native_frame_ink_bbox_mm=" in log for log in case.logs)


def test_native_profile_guard_refuses_r8_basic_radius_crossing(
    native_profile_clearance, monkeypatch,
):
    case = native_profile_clearance
    monkeypatch.setitem(drawing.ARC_PROFILE_FRAME_XY, "BottomRadius", (0.020, 0.134))
    case.bottom.position = (0.020, 0.134, 0.00125)
    case.bottom.leaders = [[
        0.067339, 0.1305, 0.00125, 0.073689, 0.1305, 0.00125,
        *_R8_LOWER_LANDING, 0.000625,
    ]]
    for line in case.bottom.data.lines:
        line[5] += 0.005
        line[8] += 0.005
    case.bottom.data.texts[0]["pos"][1] += 0.005
    with pytest.raises(RuntimeError) as exc:
        drawing._require_arc_profile_clearance(case.adapter, case.front, case.profiles)
    message = str(exc.value)
    for evidence in (
        "requested_frame_mm=(20.0, 134.0)", "actual_GetPosition_mm=(20.0, 134.0, 1.25)",
        "BasicR816", "bbox_mm=[81.5,151.2]..[103.2,154.7]mm",
        "minimum_clearance_mm=0.000", "penetration_mm=",
        "native_frame_ink_bbox_mm=[20.0,127.0]..[67.3,134.0]mm",
    ):
        assert evidence in message


@pytest.mark.parametrize("gap,passes", [(0.001, True), (0.000999, False), (0.001001, True)])
def test_native_profile_guard_enforces_one_mm_minimum(native_profile_clearance, gap, passes):
    case = native_profile_clearance
    # Horizontal native route below a real foreign callout: no intersection.
    y = 0.1444 - gap
    case.bottom.leaders = [[0.100, y, 0, 0.103, y, 0, 0.160, y, 0]]
    if passes:
        drawing._require_arc_profile_clearance(case.adapter, case.front, case.profiles)
    else:
        with pytest.raises(RuntimeError, match="minimum_clearance_mm=0.999"):
            drawing._require_arc_profile_clearance(case.adapter, case.front, case.profiles)
    assert any("penetration_mm=0.000" in log for log in case.logs)


def test_native_profile_guard_checks_non_ream_foreign_callout(native_profile_clearance):
    case = native_profile_clearance
    case.ream.name = "NativeRodCallout"
    case.ream.data.texts = [{"t": "DRILL", "pos": [0.108, 0.156, 0], "h": 0.003}]
    case.ream.data.lines = [_native_line(0.108, 0.156, 0.125, 0.156)]
    with pytest.raises(RuntimeError, match="NativeRodCallout"):
        drawing._require_arc_profile_clearance(case.adapter, case.front, case.profiles)


@pytest.mark.parametrize("defect", [
    "missing-frame", "missing-annotation", "empty-view", "refused-view",
    "missing-leader", "refused-leader", "short-leader", "nonfinite-leader",
    "zero-segment", "missing-position", "invalid-position", "missing-frame-lines",
    "missing-other-text", "invalid-other-height", "invalid-other-position",
    "unknown-other-anchor", "invalid-other-line", "refused-other-display",
    "refused-position", "wrong-frame-kind", "wrong-frame-owner", "hidden-frame",
    "duplicate-frame-name", "zero-frame-lines",
])
def test_native_profile_guard_fails_closed(native_profile_clearance, defect):
    case = native_profile_clearance
    if defect == "missing-frame":
        del case.profiles["BottomRadius"]
    elif defect == "missing-annotation":
        case.profiles["BottomRadius"].GetAnnotation = lambda: None
    elif defect == "empty-view":
        case.front.GetAnnotations = lambda: []
    elif defect == "refused-view":
        case.front.GetAnnotations = lambda: None
    elif defect == "missing-leader":
        case.bottom.leaders = []
    elif defect == "refused-leader":
        case.bottom.GetLeaderPointsAtIndex = lambda _index: None
    elif defect == "short-leader":
        case.bottom.leaders = [[0.02, 0.129, 0, 0.03]]
    elif defect == "nonfinite-leader":
        case.bottom.leaders[0][3] = float("nan")
    elif defect == "zero-segment":
        case.bottom.leaders[0][:3] = case.bottom.leaders[0][3:6]
    elif defect == "missing-position":
        case.bottom.position = None
    elif defect == "invalid-position":
        case.bottom.position = (float("inf"), 0.129, 0)
    elif defect == "missing-frame-lines":
        case.bottom.data.lines = []
    elif defect == "missing-other-text":
        case.ream.data.texts = []
    elif defect == "invalid-other-height":
        case.ream.data.texts[0]["h"] = 0.0
    elif defect == "invalid-other-position":
        case.ream.data.texts[0]["pos"] = [float("nan"), 0.1444, 0]
    elif defect == "unknown-other-anchor":
        case.ream.data.texts[0]["ref"] = -1
    elif defect == "invalid-other-line":
        case.ream.data.lines = [[1, 2]]
    elif defect == "refused-other-display":
        case.ream.GetDisplayData = lambda: None
    elif defect == "refused-position":
        def refused_position():
            raise RuntimeError("native COM refused GetPosition")
        case.bottom.GetPosition = refused_position
    elif defect == "wrong-frame-kind":
        case.bottom.kind = 7
    elif defect == "wrong-frame-owner":
        case.bottom.OwnerType = 1
    elif defect == "hidden-frame":
        case.bottom.Visible = 3
    elif defect == "duplicate-frame-name":
        case.bottom.name = case.top.name
    elif defect == "zero-frame-lines":
        case.bottom.data.lines = [_native_line(0.020, 0.129, 0.020, 0.129)]
    with pytest.raises(RuntimeError, match="rocker arc-profile native clearance failed") as exc:
        drawing._require_arc_profile_clearance(case.adapter, case.front, case.profiles)
    assert "BottomRadius" in str(exc.value)
    assert case.logs or defect in ("empty-view", "refused-view")


def test_native_profile_guard_excludes_only_its_own_frame_text(native_profile_clearance):
    case = native_profile_clearance
    case.bottom.data.texts[0]["pos"] = [0.067339, 0.1255, 0]
    drawing._require_arc_profile_clearance(case.adapter, case.front, case.profiles)
    case.bottom.leaders = [[0.110, 0.224, 0, 0.113, 0.224, 0, 0.130, 0.224, 0]]
    with pytest.raises(RuntimeError, match="DetailTop"):
        drawing._require_arc_profile_clearance(case.adapter, case.front, case.profiles)


@pytest.mark.parametrize("read,answer", [
    ("GetName", ""),
    ("GetName", lambda: "method-shaped answer"),
    ("GetPosition", [0.02, 0.129]),
    ("GetLeaderCount", -1),
])
def test_native_profile_guard_refuses_invalid_native_scalar_contracts(
    native_profile_clearance, read, answer,
):
    case = native_profile_clearance
    setattr(case.bottom, read, lambda: answer)
    with pytest.raises(RuntimeError, match="rocker arc-profile native clearance failed"):
        drawing._require_arc_profile_clearance(case.adapter, case.front, case.profiles)


def test_native_profile_guard_is_after_rebuild_and_before_export() -> None:
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "build")
    calls = [
        (node.func.id, node.lineno)
        for node in ast.walk(build)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    guard = next(line for name, line in calls if name == "_require_arc_profile_clearance")
    layout = next(line for name, line in calls if name == "check_drawing_layout")
    export = next(line for name, line in calls if name == "finalize_drawing")
    assert max(line for name, line in calls if name == "rebuild_drawing") < guard < layout < export


def test_profile_zone_mirror_station_envelopes_and_template_aim() -> None:
    """Only at the mirror station is the arc normal vertical. These limits
    do not assert a rigid vertical offset of the curve at its ends."""
    centre = ch_rocker_arm_spec.CENTER_Y
    assert (ch_rocker_arm_spec.R_TOP, ch_rocker_arm_spec.R_BOTTOM) == (800.0, 816.0)
    nominal_top = centre - ch_rocker_arm_spec.R_TOP - ch_rocker_arm_spec.PIVOT_MID_Y
    nominal_bottom = centre - ch_rocker_arm_spec.R_BOTTOM
    assert nominal_top == pytest.approx(8.0)
    assert nominal_bottom == pytest.approx(0.0)
    assert drawing.TOP_EDGE_BAND is ch_rocker_arm_spec.TOP_EDGE_BAND
    assert drawing.ARC_PROFILE_ZONE_MM == f"{ch_rocker_arm_spec.TOP_EDGE_BAND[0]:g}"
    assert drawing.ARC_PROFILE_OUTSIDE_MM == {
        "TopRadius": drawing.ARC_PROFILE_ZONE_MM,
        "BottomRadius": f"{ch_rocker_arm_spec.TOP_EDGE_BAND[1]:g}",
    }
    zone = float(drawing.ARC_PROFILE_ZONE_MM)
    top_outside = float(drawing.ARC_PROFILE_OUTSIDE_MM["TopRadius"])
    bottom_inside = zone - float(drawing.ARC_PROFILE_OUTSIDE_MM["BottomRadius"])
    assert zone == top_outside == bottom_inside == 0.5
    assert (nominal_top, nominal_top + top_outside) == pytest.approx((8.0, 8.5))
    assert (nominal_bottom, nominal_bottom + bottom_inside) == pytest.approx((0.0, 0.5))
    template_aim = nominal_top + zone / 2.0
    assert template_aim == pytest.approx(8.25)
    # The template's own ±0.03 inspection band is not the part's total zone.
    assert (template_aim - 0.03, template_aim + 0.03) == pytest.approx((8.22, 8.28))



def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(arm.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("ch-rocker-arm")
    assert spec["material_specification"] == "LOW-CARBON STEEL OR GRAY IRON"
    assert spec["finish"] == "matte black oxide"
    assert int(spec["quantity"]) == 20


def test_surface_finish_is_part_owned_authored_and_consumed() -> None:
    (control,) = ch_rocker_arm_spec.SURFACE_FINISHES
    assert control.key == "pivot_bore"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == ch_rocker_arm_spec.PIVOT_HOLE_DIA
    assert arm.PIVOT_HOLE_DIA == ch_rocker_arm_spec.PIVOT_HOLE_DIA
    part_source = "".join(Path(arm.__file__).read_text(encoding="utf-8").split())
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    sheet_source = "".join(Path(drawing.__file__).read_text(encoding="utf-8").split())
    assert (
        'control=surface_finish_by_key(SURFACE_FINISHES,"pivot_bore")' in sheet_source
    )
    assert "roughness_ra=" not in sheet_source


def test_every_view_keep_map_is_curated_on_its_own_view() -> None:
    """Codex #936 (PRRT_kwDOPHDy386mRk__): RIGHT_KEEP promised HubLength but
    build() curated only the front view, so the hub length never printed. Each
    non-empty <VIEW>_KEEP must be curated on that view, and curation fails
    loud on a missing kept dimension, so the print carries every one."""

    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    curated = {}
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "curate_view_dimensions"
        ):
            continue
        keywords = {k.arg: ast.unparse(k.value) for k in node.keywords}
        curated[keywords["keep"]] = (ast.unparse(node.args[1]), keywords)
    for keep_name, view in (
        ("FRONT_KEEP", "front"),
        ("RIGHT_KEEP", "right"),
        ("HUB_KEEP", "hub"),
        ("END_KEEP", "end"),
    ):
        if not getattr(drawing, keep_name):
            continue
        assert keep_name in curated, keep_name
        assert curated[keep_name][0] == view
    # Both views import by feature: only Hub's dimensions arrive in the end
    # view, only the pivot bore's in the front (r743-3: the front's
    # entire-model fallback warned on the leaf).
    assert curated["RIGHT_KEEP"][1]["dimensions_by_feature"] == "DRAWING_DIMENSIONS"
    assert curated["FRONT_KEEP"][1]["dimensions_by_feature"] == "DRAWING_DIMENSIONS"
    assert drawing.DRAWING_DIMENSIONS is ch_rocker_arm_notes.DRAWING_DIMENSIONS


def test_hub_length_prints_its_one_sided_band() -> None:
    """#743 PR2: the hubs are a solid stack whose north end is the rocker
    bank's datum, so each hub may only come out long and the print says so
    natively; rocker_bank_layout's L20 acceptance caps the sum."""
    from _drawing_contract import model_toleranced_dimensions

    assert ch_rocker_arm_notes.DRAWING_DIMENSIONS["Hub"] == {"HubLength"}
    assert "HubLength" in drawing.RIGHT_KEEP
    assert model_toleranced_dimensions(arm)[("Hub", "HubLength")] == (
        "*deviations(HUB_LENGTH_BAND)"
    )
    assert ch_rocker_arm_spec.HUB_LENGTH_BAND == (0.05, 0.0)
    assert f"{ch_rocker_arm_spec.HUB_LENGTH:.2f}" not in ch_rocker_arm_notes.DRAWING_NOTES


def test_strap_thickness_prints_its_band_natively() -> None:
    """Main ruling 2026-10, option b: each inter-arm gap holds one tine of
    each neighbouring rod fork, so the strap prints 2.500 +/-0.025 at three
    places on the Strap extrude's own depth (drawing-simplicity-policy.md `How the repository implements the guidelines`), selected by
    feature and dimension name in the end view, and no note repeats it."""
    from _drawing_contract import model_toleranced_dimensions

    assert ch_rocker_arm_spec.ARM_THICKNESS_BAND == (0.025, -0.025)
    assert ch_rocker_arm_notes.DRAWING_DIMENSIONS["Strap"] == {"StrapThickness"}
    assert ch_rocker_arm_notes.DRAWING_PRECISION["Strap"]["StrapThickness"] == 3
    assert "StrapThickness" in drawing.RIGHT_KEEP
    assert "StrapThickness" not in drawing.FRONT_KEEP
    assert model_toleranced_dimensions(arm)[("Strap", "StrapThickness")] == "strap_upper"
    build = "".join(Path(arm.__file__).read_text(encoding="utf-8").split())
    assert 'name_dimensions(adapter,"Strap",["StrapThickness"])' in build
    assert "strap_lower,strap_upper=deviations(ARM_THICKNESS_BAND)" in build
    assert "(strap_thickness_dim[0],'\"ArmThickness\"')" in build
    joined = " ".join(
        line.strip() for line in ch_rocker_arm_notes.DRAWING_NOTES.splitlines()
    )
    assert "ALL HOLES THRU" not in joined
    assert "STRAP 2.50" not in joined
    assert "THICK" not in joined
    assert "GROUND" not in joined  # the strap faces are milled (plan op 20)


def test_strap_thickness_text_clears_datum_b_the_frame_and_the_iso_caption() -> None:
    x, y = drawing.STRAP_THICKNESS_TEXT_XY
    # Right of the end view's strap and its hub (1:1).
    assert x - drawing.RIGHT_CENTER[0] > ch_rocker_arm_spec.HUB_LENGTH / 2000.0 + 0.010
    # Its line runs above datum B's attachment on the broad face ...
    datum_b_y = drawing.RIGHT_CENTER[1] + (
        ch_rocker_arm_spec.ARM_DEPTH - 1.0 - drawing.PIVOT_MID_Y
    ) / 1000.0
    assert y >= datum_b_y + 0.003
    # ... and inside the strap's height above the hub, so it crosses no hub line.
    view_top = drawing.RIGHT_CENTER[1] + ch_rocker_arm_spec.TOP_END_Y / 2000.0
    assert y < view_top
    # Under the iso caption and the rod-pin frame.
    assert y < drawing.ISO_CAPTION_XY[1] - 0.006
    assert y < drawing.ISO_CENTER[1]


def test_top_edge_model_band_is_unchanged_by_the_basic_drawing_override() -> None:
    """The source keeps its existing height band and centre equation; the
    drawing's imported height is BASIC and governed by surface profile."""
    from _drawing_contract import model_toleranced_dimensions

    upper, lower = ch_rocker_arm_spec.TOP_EDGE_BAND
    assert lower == 0.0 < upper == 0.50
    assert ch_rocker_arm_spec.TOP_EDGE_ABOVE_PIVOT == pytest.approx(8.0)
    assert not hasattr(ch_rocker_arm_notes, "TOP_EDGE_BAND")
    assert ch_rocker_arm_notes.DRAWING_DIMENSIONS["TopEdgeReference"] == {"TopAbovePivot"}
    assert model_toleranced_dimensions(arm)[("TopEdgeReference", "TopAbovePivot")] == (
        "*deviations(TOP_EDGE_BAND)"
    )
    assert "TopAbovePivot" in drawing.FRONT_KEEP
    joined = " ".join(
        line.strip() for line in ch_rocker_arm_notes.DRAWING_NOTES.splitlines()
    )
    assert "ABOVE THE PIVOT" not in joined
    assert f"+{upper:.2f}/0" not in joined
    build = Path(arm.__file__).read_text(encoding="utf-8")
    # The source centre remains an equation of the model height; the drawing
    # override changes presentation, not the source geometry or its band.
    assert '"ArmDepth" / 2 + "TopAbovePivot" + "CurveRadius"' in build
    assert ch_rocker_arm_notes.DRAWING_PRECISION["TopEdgeReference"]["TopAbovePivot"] == 2


def test_pivot_bore_ream_band_rides_its_diameter_not_a_note() -> None:
    """Codex #936 sweep (drawing-guidelines.md rule 3 (decimal places carry the tolerance)): note 6 printed "REAM +0.03/0, Ra
    1.6" while the O6.50 printed bare. The band is now native on PivotDia and
    the Ra is the bore's own symbol; the note keeps only REAM."""
    from _drawing_contract import model_toleranced_dimensions

    assert model_toleranced_dimensions(arm)[("PivotHoleProfile", "PivotDia")] == (
        "*deviations(PIVOT_HOLE_BAND)"
    )
    assert "PivotDia" in drawing.HUB_KEEP
    joined = " ".join(
        line.strip() for line in ch_rocker_arm_notes.DRAWING_NOTES.splitlines()
    )
    assert "+0.03" not in joined
    assert "Ra 1.6" not in joined
    assert any(
        control.key == "pivot_bore" for control in ch_rocker_arm_spec.SURFACE_FINISHES
    )


def test_no_rocker_note_carries_a_tolerance_band() -> None:
    """No size/profile band is duplicated in prose. Hub coaxiality remains
    a plain note by Main's ruling (2026-09-26)."""
    for line in ch_rocker_arm_notes.DRAWING_NOTES.splitlines():
        if "COAXIAL" in line or "WITHIN" in line:
            continue
        assert not re.search(r"\+\d|[-+]0\.\d+/|±|\+/-", line), line


def test_top_edge_reference_is_saved_hidden_and_imported_per_view() -> None:
    # #880 / #950: a reference sketch owns a printed dimension but no
    # geometry, so the part saves it hidden (no assembly instance renders it)
    # and the drawing shows it per view through _drawing_hidden_sketches.
    build = Path(arm.__file__).read_text(encoding="utf-8")
    blank = 'blank_sketch(adapter, "TopEdgeReference")'
    assert blank in build
    assert build.index(blank) < build.rindex("save_part_and_images(adapter, PART_NAME)")
    source = Path(drawing.__file__).read_text(encoding="utf-8").replace("\r\n", "\n")
    assert "from _drawing_hidden_sketches import curate_view_dimensions" in source
    assert "    curate_view_dimensions,\n" not in source


def test_top_basic_height_is_off_the_pin_x_witness() -> None:
    assert drawing.FRONT_KEEP["TopAbovePivot"] == (0.165, 0.191)
    assert drawing.FRONT_KEEP["TopAbovePivot"][0] != drawing.FRONT_CENTER[0]
    assert drawing.PIN_X_TEXT_XY[1] == 0.197
    assert drawing.TAPER_INTERSECTION_TEXT_XY[1] == 0.132
    assert drawing.OVERALL_WIDTH_TEXT_XY[1] == 0.215


_PIVOT_CENTRE = drawing.HUB_CENTER
_DETAIL_BORE_R = ch_rocker_arm_spec.PIVOT_HOLE_DIA / 2000.0 * (
    drawing.HUB_SCALE[0] / drawing.HUB_SCALE[1]
)


class _Tag:
    def __init__(self, attached: tuple, dangling: bool = False) -> None:
        self.annotation = SimpleNamespace(
            GetAttachedEntities3=lambda: attached,
            IsDangling=lambda: dangling,
        )

    def GetAnnotation(self) -> SimpleNamespace:
        return self.annotation


_BORE, _HUB = object(), object()
_APP = SimpleNamespace(IsSame=lambda a, b: 1 if a is b else 0)


@pytest.fixture
def bound(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bypass native wrapping for offline logic only, not native-binding proof."""
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    import _drawing_layout_audit

    monkeypatch.setattr(_drawing_layout_audit, "_early_bound", lambda obj, _interface: obj)
    # Caption refusals must never probe this host's real seat in an offline test.
    def capture(_adapter, _label, _message, *, exception, **_context):
        raise exception
    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", capture)


class _PrecisionAdapter:
    @staticmethod
    def _attempt(operation, default=None):
        try:
            return operation()
        except Exception:
            return default

    def _get_attr_or_call(self, obj, name):
        member = self._attempt(lambda: getattr(obj, name))
        return self._attempt(member) if callable(member) else member


class _PrecisionDisplay:
    def __init__(self, primary, name="PivotDia") -> None:
        self.primary = primary
        self.dimension = SimpleNamespace(Name=name)

    def GetDimension(self):
        return self.dimension

    def GetPrimaryPrecision2(self):
        return self.primary


class _PrecisionAnnotation:
    def __init__(self, display) -> None:
        self.display = display

    def GetSpecificAnnotation(self):
        return self.display


class _PrecisionExtension:
    def __init__(self, precision) -> None:
        self.precision = precision
        self.calls: list[tuple[int, int]] = []

    def GetUserPreferenceInteger(self, preference: int, option: int):
        self.calls.append((preference, option))
        return self.precision


def _pivot_precision_case(primary, document_precision=2, name="PivotDia"):
    """Method-shaped scalar getters model the typelib, not a live COM binding."""
    display = _PrecisionDisplay(primary, name)
    annotation = _PrecisionAnnotation(display)
    extension = _PrecisionExtension(document_precision)
    model = SimpleNamespace(Extension=extension)
    return _PrecisionAdapter(), model, annotation, extension


@pytest.mark.parametrize("primary", [2, -2], ids=["explicit", "inherited"])
def test_pivot_precision_matching_two_places_passes(bound: None, primary) -> None:
    adapter, model, annotation, extension = _pivot_precision_case(primary)
    drawing._assert_pivot_precision(adapter, model, [annotation])
    assert extension.calls == ([(24, 204)] if primary == -2 else [])


@pytest.mark.parametrize("primary", [3, -2], ids=["explicit", "inherited"])
def test_pivot_precision_three_places_fails(bound: None, primary) -> None:
    adapter, model, annotation, extension = _pivot_precision_case(primary, 3)
    with pytest.raises(RuntimeError, match="PivotDia.*expected 2.*effective 3"):
        drawing._assert_pivot_precision(adapter, model, [annotation])
    assert extension.calls == ([(24, 204)] if primary == -2 else [])


@pytest.mark.parametrize(
    ("primary", "document_precision", "calls"),
    [
        (None, 2, []),
        (-2, None, [(24, 204)]),
        (-2, -2, [(24, 204)]),
    ],
    ids=["raw-missing", "document-missing", "document-still-sentinel"],
)
def test_pivot_precision_missing_readback_fails(
    bound: None, primary, document_precision, calls
) -> None:
    adapter, model, annotation, extension = _pivot_precision_case(
        primary, document_precision
    )
    with pytest.raises(RuntimeError, match="PivotDia.*expected 2.*unreadable"):
        drawing._assert_pivot_precision(adapter, model, [annotation])
    assert extension.calls == calls


@pytest.mark.parametrize("inherited", [False, True], ids=["raw", "document"])
@pytest.mark.parametrize(
    "unreadable",
    [True, 2.0, "2", Mock(), _PrecisionDisplay(2).GetPrimaryPrecision2],
    ids=["bool", "float", "string", "mock", "bound-method"],
)
def test_pivot_precision_never_coerces_unreadable_values(
    bound: None, inherited: bool, unreadable
) -> None:
    adapter, model, annotation, extension = _pivot_precision_case(
        -2 if inherited else unreadable, unreadable
    )
    with pytest.raises(RuntimeError, match="PivotDia.*expected 2.*unreadable"):
        drawing._assert_pivot_precision(adapter, model, [annotation])
    assert extension.calls == ([(24, 204)] if inherited else [])


@pytest.mark.parametrize("empty", [True, False], ids=["empty", "other-dimension"])
def test_pivot_precision_missing_dimension_fails(bound: None, empty: bool) -> None:
    adapter, model, annotation, extension = _pivot_precision_case(
        2, name="TopAbovePivot"
    )
    with pytest.raises(RuntimeError, match="PivotDia.*expected 2.*missing dimension"):
        drawing._assert_pivot_precision(adapter, model, [] if empty else [annotation])
    assert extension.calls == []


@pytest.mark.parametrize("stage", ["annotation", "dimension", "primary", "document"])
def test_pivot_precision_getter_exceptions_fail_closed(
    bound: None, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    adapter, model, annotation, extension = _pivot_precision_case(-2)

    def fail(*_args):
        raise RuntimeError("native getter failed")

    target, member = {
        "annotation": (annotation, "GetSpecificAnnotation"),
        "dimension": (annotation.display, "GetDimension"),
        "primary": (annotation.display, "GetPrimaryPrecision2"),
        "document": (extension, "GetUserPreferenceInteger"),
    }[stage]
    monkeypatch.setattr(target, member, fail)
    with pytest.raises(RuntimeError, match="PivotDia.*expected 2.*unreadable"):
        drawing._assert_pivot_precision(adapter, model, [annotation])


@pytest.mark.parametrize("stage", ["display", "dimension", "name", "extension"])
def test_pivot_precision_unavailable_native_state_fails_closed(
    bound: None, stage: str
) -> None:
    adapter, model, annotation, extension = _pivot_precision_case(-2)
    if stage == "display":
        annotation.display = None
    elif stage == "dimension":
        annotation.display.dimension = None
    elif stage == "name":
        annotation.display.dimension.Name = None
    else:
        model.Extension = None
    with pytest.raises(RuntimeError, match="PivotDia.*expected 2.*unreadable"):
        drawing._assert_pivot_precision(adapter, model, [annotation])
    assert extension.calls == []


@pytest.mark.parametrize(
    "interface",
    ["IAnnotation", "IDisplayDimension", "IModelDoc2", "IModelDocExtension"],
)
def test_pivot_precision_binding_failures_fail_closed(
    monkeypatch: pytest.MonkeyPatch, interface: str
) -> None:
    adapter, model, annotation, _extension = _pivot_precision_case(-2)

    def bind(obj, requested):
        if requested == interface:
            raise RuntimeError("native binding unavailable")
        return obj

    monkeypatch.setattr(drawing, "_early_bound", bind)
    with pytest.raises(RuntimeError, match="PivotDia.*expected 2.*unreadable"):
        drawing._assert_pivot_precision(adapter, model, [annotation])


def test_build_keeps_pivot_out_of_strict_part_precision() -> None:
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    strict_call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "assert_imported_precision"
    )
    assert {ast.literal_eval(key) for key in strict_call.args[2].keys} == {
        "TopAbovePivot",
        "HubLength",
        "StrapThickness",
    }


def test_datum_a_attached_to_the_bore_passes(bound: None) -> None:
    drawing._require_datum_on_bore(_APP, _Tag((_BORE,)), _BORE)


def test_datum_a_refuses_null_native_annotation(bound: None) -> None:
    tag = _Tag((_BORE,))
    tag.annotation = None
    with pytest.raises(RuntimeError, match="datum A has no native annotation"):
        drawing._require_datum_on_bore(_APP, tag, _BORE)


@pytest.mark.parametrize(
    ("attached", "dangling", "match"),
    [
        ((_HUB,), False, "other than the O6.5 pivot bore"),
        ((), False, "has 0"),
        ((_BORE, _HUB), False, "has 2"),
        ((_BORE,), True, "dangling"),
    ],
)
def test_datum_a_off_the_bore_fails(
    bound: None, attached: tuple, dangling: bool, match: str
) -> None:
    """r743-4D: the rim pick attached datum A to the concentric O10 hub,
    which changes what the A-B-C frame controls."""
    with pytest.raises(RuntimeError, match=match):
        drawing._require_datum_on_bore(_APP, _Tag(attached, dangling), _BORE)


def _picker(monkeypatch: pytest.MonkeyPatch, resolve) -> list:
    """Route each EDGE pick through ``resolve(fraction of the bore radius)``."""
    picks: list = []

    def select(_adapter, _view, entity_type, xy, *, label):
        assert entity_type == "EDGE" and xy is not None
        fraction = round(math.dist(xy, _PIVOT_CENTRE) / _DETAIL_BORE_R, 6)
        picks.append((fraction, xy))
        return resolve(fraction)

    monkeypatch.setattr(drawing, "_select_view_entity", select)
    return picks


_ADAPTER = SimpleNamespace(
    swApp=_APP, currentModel=SimpleNamespace(ClearSelection2=lambda _all: True)
)


def test_pivot_pick_takes_the_bore_rim_on_the_datum_ray(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    picks = _picker(monkeypatch, lambda _fraction: _BORE)
    xy = drawing._pick_pivot_bore(_ADAPTER, object(), _BORE, _PIVOT_CENTRE, _DETAIL_BORE_R)
    assert [fraction for fraction, _ in picks] == [1.0]
    bearing = math.atan2(xy[1] - _PIVOT_CENTRE[1], xy[0] - _PIVOT_CENTRE[0])
    assert bearing == pytest.approx(drawing.PIVOT_DATUM_ANGLE)
    assert math.dist(xy, _PIVOT_CENTRE) == pytest.approx(_DETAIL_BORE_R)


def test_pivot_pick_moves_inward_when_the_rim_resolves_to_the_hub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    picks = _picker(monkeypatch, lambda fraction: _HUB if fraction == 1.0 else _BORE)
    xy = drawing._pick_pivot_bore(_ADAPTER, object(), _BORE, _PIVOT_CENTRE, _DETAIL_BORE_R)
    assert [fraction for fraction, _ in picks] == list(drawing.PIVOT_PICK_FRACTIONS)
    assert xy == picks[-1][1]
    # Inward points stay inside the bore, further from the hub rim.
    assert all(0.0 < f <= 1.0 for f in drawing.PIVOT_PICK_FRACTIONS)


def test_pivot_pick_that_never_finds_the_bore_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def resolve(fraction: float) -> object:
        if fraction == 1.0:
            return _HUB
        raise RuntimeError("failed to select pivot bore datum pick edge")

    _picker(monkeypatch, resolve)
    with pytest.raises(RuntimeError, match="no pick on datum A's ray"):
        drawing._pick_pivot_bore(_ADAPTER, object(), _BORE, _PIVOT_CENTRE, _DETAIL_BORE_R)




def test_detail_d_leaders_use_four_separate_quadrants(bound, monkeypatch) -> None:
    def project(_adapter, _view, points, **_kwargs):
        return [(drawing.HUB_CENTER[0] + x * 4.0,
                 drawing.HUB_CENTER[1] + (y - drawing.PIVOT_MID_Y / 1000.0) * 4.0)
                for x, y, _z in points]

    monkeypatch.setattr(drawing, "_project", project)
    rim, symbol = drawing._pivot_finish_placement(object(), object())
    datum = drawing._pivot_datum_request(_PIVOT_CENTRE, _DETAIL_BORE_R)
    points = [drawing.HUB_KEEP["HubDia"], datum, drawing.HUB_KEEP["PivotDia"], symbol]
    quadrants = [
        int((math.atan2(y - _PIVOT_CENTRE[1], x - _PIVOT_CENTRE[0]) % math.tau) // (math.pi / 2.0))
        for x, y in points
    ]
    assert quadrants == [0, 1, 2, 3]
    assert math.dist(rim, _PIVOT_CENTRE) == pytest.approx(_DETAIL_BORE_R)
    assert symbol[0] > rim[0] and symbol[1] < rim[1]
    assert drawing.HUB_KEEP["PivotDia"] == (0.120, 0.086)
    assert drawing.HUB_KEEP["HubDia"] == (0.210, 0.122)


def test_both_bores_are_picked_by_diameter_not_by_a_rim_coordinate() -> None:
    """r743-p1s-B: a coordinate pick on the #47 rod-hole rim resolved to the
    strap's tapered end-face line, so AddHoleCallout2 returned None. Every
    annotation on the rod-pin hole takes the diameter-picked edge."""

    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    picks = {}
    uses = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            call = node.value
            if (
                isinstance(call.func, ast.Name)
                and call.func.id == "visible_circle_edge"
            ):
                picks[node.targets[0].id] = ast.unparse(call.args[2])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            keywords = {k.arg: ast.unparse(k.value) for k in node.keywords}
            if (
                node.func.id in {"add_native_hole_callout", "add_edge_dimension", "add_feature_control_frame"}
                and ("rod_hole_edge" in keywords.get("edge", "")
                     or "rod_hole_edge" in keywords.get("edge_entity", "")
                     or "rod_hole_edge" in keywords.get("entities", ""))
            ):
                uses.append((node.func.id, keywords))
    assert picks["rod_hole_edge"] == "_ROD_HOLE_DIA"
    assert picks["pivot_bore_edge"] == "PIVOT_HOLE_DIA"
    kinds = {name for name, _ in uses}
    assert kinds == {
        "add_native_hole_callout",
        "add_edge_dimension",
        "add_feature_control_frame",
    }
    for name, keywords in uses:
        assert "edge_xy" not in keywords, name
        if name == "add_native_hole_callout":
            assert keywords["edge"] == "rod_hole_edge"
        elif name == "add_edge_dimension":
            assert keywords["entities"] == "(pivot_bore_edge, rod_hole_edge)"
        else:
            assert keywords["edge_entity"] == "rod_hole_edge"


# Measured on the r743-p1s-B2 render (5100x3300 px on 431.8x279.4 mm): the
# drawable region ends 12.7 mm above the sheet's bottom edge, the linked
# notes pitch ~4.14 mm a line, and the iso caption runs ~2.5 mm a character.
BORDER_BOTTOM = 0.0127
NOTE_LINE_PITCH = 0.0042
CAPTION_CHAR_WIDTH = 0.0026
RIGHT_BORDER = 0.415
DRAWABLE = DrawableRegion(0.0127, BORDER_BOTTOM, 0.4191, 0.2667)


class _FakeAnnotation:
    def __init__(self, position: tuple[float, float]) -> None:
        self.position = position

    def GetPosition(self) -> tuple[float, float, float]:
        return (*self.position, 0.0)

    def SetPosition(self, x: float, y: float, _z: float) -> bool:
        self.position = (x, y)
        return True


class _FakeNote:
    """A top-left-anchored text block whose box sits off its insertion point
    and follows a move only ``tracking`` of the way, as SolidWorks' does."""

    def __init__(
        self, anchor: tuple[float, float], height: float, tracking: float = 1.0
    ) -> None:
        self.annotation = _FakeAnnotation(anchor)
        self.anchor = anchor
        self.height = height
        self.tracking = tracking

    def GetAnnotation(self) -> _FakeAnnotation:
        return self.annotation

    def GetExtent(self) -> tuple[float, ...]:
        x, y = (
            a + (p - a) * self.tracking
            for a, p in zip(self.anchor, self.annotation.position)
        )
        x0, y1 = x + 0.0008, y - 0.0011
        return (x0, y1 - self.height, 0.0, x0 + 0.180, y1, 0.0)


def _seat(monkeypatch: pytest.MonkeyPatch, note: _FakeNote) -> tuple[float, ...]:
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(GraphicsRedraw2=lambda: None)
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(
        drawing, "sheet_drawable_region", lambda *_args, **_kwargs: DRAWABLE
    )
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_args, **_kwargs: None)
    return drawing._seat_notes_on_border(adapter, note, sheet=object())


@pytest.mark.parametrize("tracking", [1.0, 0.8])
def test_general_notes_bottom_is_seated_inside_the_frame(
    monkeypatch: pytest.MonkeyPatch, tracking: float
) -> None:
    """r743-p1s-B2: anchored by its top at 0.082, the 18-line block ran two
    lines past the bottom border. Seated from its measured extent, its bottom
    lands on the drawable region's clearance line and its left on NOTES_LEFT,
    whatever the insertion point's offset from the rendered box."""
    lines = len(ch_rocker_arm_notes.DRAWING_NOTES.splitlines())
    note = _FakeNote(
        (drawing.NOTES_LEFT, drawing.NOTES_CEILING),
        lines * NOTE_LINE_PITCH,
        tracking,
    )
    x0, y0, _x1, y1 = _seat(monkeypatch, note)
    assert y0 >= DRAWABLE.ymin
    assert y0 == pytest.approx(
        DRAWABLE.ymin + drawing.NOTES_BORDER_CLEARANCE,
        abs=0.0005,
    )
    assert x0 == pytest.approx(drawing.NOTES_LEFT, abs=0.0005)
    assert y1 < drawing.NOTES_CEILING
    # The shorter notes need no historical line-count overflow assumption:
    # the rendered extent, not an old insertion point, governs seating.


# r743-3 (4ca562169, w4): the 21-line block rendered 16.06..110.76 mm, i.e.
# 94.70 mm tall, 0.76 over NOTES_CEILING -- ~4.51 mm a line of rendered
# extent (box margins included), well above the 4.14 line pitch B2 measured.
R743_3_RENDERED_PITCH = 0.09470 / 21


def test_general_notes_leave_a_full_line_of_headroom() -> None:
    """Main (r743-3): the line estimate undercounted, so the block must fit
    the band with one full rendered line to spare at the measured pitch."""
    lines = len(ch_rocker_arm_notes.DRAWING_NOTES.splitlines())
    band = drawing.NOTES_CEILING - DRAWABLE.ymin - drawing.NOTES_BORDER_CLEARANCE
    assert (lines + 1) * R743_3_RENDERED_PITCH <= band
    # Every line stays within the widest line r743-2R already rendered
    # clear of the front view.
    assert max(len(line) for line in ch_rocker_arm_notes.DRAWING_NOTES.splitlines()) <= 42


def test_general_notes_too_tall_for_the_band_fail_the_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    band = drawing.NOTES_CEILING - DRAWABLE.ymin - drawing.NOTES_BORDER_CLEARANCE
    note = _FakeNote((drawing.NOTES_LEFT, drawing.NOTES_CEILING), band + 0.002)
    with pytest.raises(RuntimeError, match="do not fit"):
        _seat(monkeypatch, note)


def test_an_unresolved_notes_link_fails_instead_of_seating_one_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The extent of an unresolved property link is one line of token text;
    seating that box would put the real block's bottom through the border."""
    note = _FakeNote((drawing.NOTES_LEFT, drawing.NOTES_CEILING), NOTE_LINE_PITCH)
    with pytest.raises(RuntimeError, match="has not resolved"):
        _seat(monkeypatch, note)


def test_iso_caption_sits_under_the_iso_clear_of_the_frame_and_end_view() -> None:
    caption = ch_rocker_arm_notes.ISOMETRIC_VIEW_NOTE
    left, top = drawing.ISO_CAPTION_XY
    right = left + len(caption) * CAPTION_CHAR_WIDTH
    assert top < drawing.ISO_CENTER[1] - 0.003
    assert left > drawing.RIGHT_CENTER[0] + 0.015  # the end view and its +0.05
    assert right < RIGHT_BORDER - 0.005
    # Under the iso: the caption's span overlaps the iso's.
    assert left < drawing.ISO_CENTER[0] < right




def test_land_and_hub_sizes_are_marked_model_dimensions_at_normal_precision() -> None:
    assert ch_rocker_arm_notes.DRAWING_DIMENSIONS["StrapProfile"] == {
        "TopRadius", "BottomRadius", "RodTipLen",
    }
    assert ch_rocker_arm_notes.DRAWING_DIMENSIONS["HubProfile"] == {"HubDia"}
    assert set(drawing.END_KEEP) == {"RodTipLen"}
    assert set(drawing.HUB_KEEP) == {"PivotDia", "HubDia"}
    assert not {"RodTipLen", "HubDia"} & set(drawing.FRONT_KEEP)
    assert ch_rocker_arm_notes.DRAWING_PRECISION["HubProfile"]["HubDia"] == 2
    assert ch_rocker_arm_notes.DEFAULT_DRAWING_PRECISION == 2
    assert ch_rocker_arm_spec.LINEAR_2PL == pytest.approx(0.508)
    assert ch_rocker_arm_spec.STRAP_HUB_SYMMETRY == pytest.approx(0.10)
    joined = " ".join(ch_rocker_arm_notes.DRAWING_NOTES.split())
    assert "STRAP SYMMETRIC TO HUB WITHIN 0.10" in joined


def test_new_measured_quantities_follow_the_source_geometry_equations() -> None:
    spec = ch_rocker_arm_spec
    alpha = spec.TOP_ARC_LEN / (2.0 * spec.CURVE_RADIUS)
    assert spec._ALPHA_TOP == pytest.approx(alpha)
    assert 2.0 * spec.ROD_TIP_X == pytest.approx(
        2.0 * (spec.CURVE_RADIUS + spec.TIP_FACE) * math.sin(alpha),
    )
    assert spec.BOT_END_X == pytest.approx(
        (spec.CURVE_RADIUS + spec.ARM_DEPTH)
        * math.sin(spec.BOT_ARC_LEN / (2.0 * (spec.CURVE_RADIUS + spec.ARM_DEPTH))),
    )
    assert spec.TIP_FACE == pytest.approx(5.588)
    assert spec.HUB_DIA == pytest.approx(10.2)
    assert (spec.HUB_LENGTH - spec.ARM_THICKNESS) / 2.0 == pytest.approx(2.27825)


@pytest.mark.parametrize("ignored_part", [None, 1, 2])
def test_native_reference_parentheses_never_replace_the_measured_nominal(
    monkeypatch: pytest.MonkeyPatch, ignored_part: int | None,
) -> None:
    import _drawing_dimensions
    from solidworks_mcp.adapters import sw_type_info

    text = {1: "", 2: ""}
    writes = []
    model = SimpleNamespace(SystemValue=0.00227825)

    def set_text(part, value):
        writes.append((part, value))
        if part != ignored_part:
            text[part] = value

    display = SimpleNamespace(
        SetText=set_text, GetText=lambda part: text[part],
        GetDimension2=lambda _index: model,
    )
    annotation = SimpleNamespace(GetSpecificAnnotation=lambda: display)
    adapter = SimpleNamespace(_attempt=lambda fn: fn())
    monkeypatch.setattr(sw_type_info, "early_bound_or_flag", lambda obj, *_: obj)
    monkeypatch.setattr(_drawing_dimensions, "rebuild_drawing", lambda *_a, **_k: None)
    if ignored_part is None:
        assert _drawing_dimensions.set_reference_dimension(
            adapter, annotation, label="strap offset",
        ) is display
        assert text == {1: "(", 2: ")"}
    else:
        with pytest.raises(RuntimeError, match="failed to parenthesize"):
            _drawing_dimensions.set_reference_dimension(
                adapter, annotation, label="strap offset",
            )
    assert writes == [(1, "("), (2, ")")]
    assert model.SystemValue == 0.00227825


def test_rod_drill_identifier_and_native_callout_process_share_the_hole_spec() -> None:
    from _hole_spec import drill_process

    assert ch_rocker_arm_spec.ROD_HOLE_SPEC.kind == "drilled_number"
    assert ch_rocker_arm_spec.ROD_HOLE_SPEC.size == "#47"
    assert drill_process(ch_rocker_arm_spec.ROD_HOLE_SPEC) == "#47 DRILL"
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "add_native_hole_callout"
    ]
    assert len(calls) == 1
    keywords = {keyword.arg: ast.unparse(keyword.value) for keyword in calls[0].keywords}
    assert keywords["process"] == "drill_process(ROD_HOLE_SPEC) + '\\n'"
    assert drawing.ROD_HOLE_SPEC is ch_rocker_arm_spec.ROD_HOLE_SPEC


@pytest.mark.parametrize("quantity,expected", [
    ("overall", 2.0 * ch_rocker_arm_spec.ROD_TIP_X),
    ("land", ch_rocker_arm_spec.TIP_FACE),
    ("taper", ch_rocker_arm_spec.BOT_END_X),
    ("hub", ch_rocker_arm_spec.HUB_DIA),
    ("offset", (ch_rocker_arm_spec.HUB_LENGTH - ch_rocker_arm_spec.ARM_THICKNESS) / 2.0),
])
@pytest.mark.parametrize("defect", [
    None, "wrong", "missing", "neighbour", "dangling", "nan", "inf", "no_value",
])
def test_native_linear_measurement_reads_the_model_and_named_attachments(
    monkeypatch: pytest.MonkeyPatch, quantity: str, expected: float, defect: str | None,
) -> None:
    import _drawing_edge_dimensions
    from solidworks_mcp.adapters import sw_type_info

    first, second, neighbour = object(), object(), object()
    model = None if defect == "missing" else SimpleNamespace(
        SystemValue=(expected + (0.1 if defect == "wrong" else 0.0)) / 1000.0,
    )
    if defect in {"nan", "inf", "no_value"}:
        model.SystemValue = None if defect == "no_value" else float(defect)
    attached = (first, neighbour if defect == "neighbour" else second)
    annotation = SimpleNamespace(
        GetAttachedEntities3=lambda: attached,
        GetAttachedEntityTypes=lambda: (1, 1),
        IsDangling=lambda: defect == "dangling",
    )
    display = SimpleNamespace(
        GetDimension2=lambda _index: model, GetAnnotation=lambda: annotation,
    )
    adapter = SimpleNamespace(swApp=_APP)
    monkeypatch.setattr(_drawing_edge_dimensions, "_early_bound", lambda obj, *_: obj)
    monkeypatch.setattr(sw_type_info, "early_bound_or_flag", lambda obj, *_: obj)
    monkeypatch.setattr(
        _drawing_edge_dimensions, "_is_same_attachment",
        lambda _adapter, actual, wanted, _kind: actual is wanted,
    )
    kwargs = dict(expected_mm=expected, label=quantity, entities=(first, second))
    if defect is None:
        assert _drawing_edge_dimensions.assert_dimension_measures(
            adapter, display, **kwargs,
        ) == pytest.approx(expected)
    else:
        with pytest.raises((RuntimeError, AttributeError)):
            _drawing_edge_dimensions.assert_dimension_measures(adapter, display, **kwargs)


@pytest.mark.parametrize("retained", [True, False])
def test_native_reference_precision_reads_back_normal_two_places(
    monkeypatch: pytest.MonkeyPatch, retained: bool,
) -> None:
    import _drawing_dimensions
    from solidworks_mcp.adapters import sw_type_info

    state = {"precision": 3}
    calls = []

    def set_precision(primary, dual, tolerance, dual_tolerance):
        calls.append((primary, dual, tolerance, dual_tolerance))
        if retained:
            state["precision"] = primary
        return True

    display = SimpleNamespace(
        SetPrecision3=set_precision, GetPrimaryPrecision2=lambda: state["precision"],
    )
    annotation = SimpleNamespace(GetSpecificAnnotation=lambda: display)
    adapter = SimpleNamespace(_attempt=lambda fn: fn())
    monkeypatch.setattr(sw_type_info, "early_bound_or_flag", lambda obj, *_: obj)
    monkeypatch.setattr(_drawing_dimensions, "dimension_name", lambda *_: "offset")
    monkeypatch.setattr(_drawing_dimensions, "rebuild_drawing", lambda *_a, **_k: None)
    kwargs = {"offset": ch_rocker_arm_notes.DEFAULT_DRAWING_PRECISION}
    if retained:
        _drawing_dimensions.set_dimension_precision(adapter, [annotation], kwargs)
        assert state["precision"] == 2
    else:
        with pytest.raises(RuntimeError, match="did not take"):
            _drawing_dimensions.set_dimension_precision(adapter, [annotation], kwargs)
    assert calls == [(2, -1, -1, -1)]


def test_rocker_native_helpers_use_the_extracted_owners() -> None:
    import _drawing_edge_dimensions
    import _drawing_gdt
    import _drawing_hole_callout

    assert drawing.add_edge_dimension is _drawing_edge_dimensions.add_edge_dimension
    assert drawing.add_datum_feature is _drawing_gdt.add_datum_feature
    assert drawing.add_feature_control_frame is _drawing_gdt.add_feature_control_frame
    assert drawing.add_native_hole_callout is _drawing_hole_callout.add_native_hole_callout


@pytest.mark.parametrize("defect", [None, "one_place", "missing", "no_display"])
def test_imported_hub_diameter_cannot_lose_the_model_two_place_size_band(
    monkeypatch: pytest.MonkeyPatch, defect: str | None,
) -> None:
    import _drawing_dimensions
    from solidworks_mcp.adapters import sw_type_info

    display = SimpleNamespace(
        GetPrimaryPrecision2=lambda: 1 if defect == "one_place" else 2,
        SetPrecision3=lambda *_: pytest.fail("imported hub precision is part-owned"),
    )
    annotation = SimpleNamespace(
        GetSpecificAnnotation=lambda: None if defect == "no_display" else display,
    )
    adapter = SimpleNamespace(_attempt=lambda fn: fn())
    monkeypatch.setattr(sw_type_info, "early_bound_or_flag", lambda obj, *_: obj)
    monkeypatch.setattr(_drawing_dimensions, "dimension_name", lambda *_: "HubDia")
    annotations = [] if defect == "missing" else [annotation]
    precision = ch_rocker_arm_notes.DRAWING_PRECISION["HubProfile"]
    if defect is None:
        _drawing_dimensions.assert_imported_precision(adapter, annotations, precision)
    else:
        with pytest.raises(RuntimeError):
            _drawing_dimensions.assert_imported_precision(adapter, annotations, precision)


@pytest.mark.parametrize("defect", [None, "selection", "landing", "creation", "status", "missing-model", "driven"])
def test_native_angular_dimension_keeps_named_entities_and_explicit_pick_points(
    monkeypatch: pytest.MonkeyPatch, defect: str | None,
) -> None:
    import _drawing_edge_dimensions

    selected = []
    events = []
    view = object()
    class ModelDimension:
        __slots__ = ("state",)

        def __init__(self):
            self.state = 0

        @property
        def DrivenState(self):
            events.append(("driven-read", self.state))
            return self.state

        @DrivenState.setter
        def DrivenState(self, value):
            assert type(value) is int and value == 1
            events.append(("driven-set", value))
            if defect != "driven":
                self.state = value

    model = ModelDimension()
    def get_dimension(index):
        assert type(index) is int and index == 0
        return None if defect == "missing-model" else model
    display = SimpleNamespace(GetDimension2=get_dimension)

    def select(entity, append, data):
        assert data.View is view
        if not append:
            selected.clear()
        selected.append(entity)
        events.append(("select", entity))
        return defect != "selection"

    first = SimpleNamespace(Select4=lambda append, data: select("land", append, data))
    second = SimpleNamespace(Select4=lambda append, data: select("mirror", append, data))

    def landing(index, mark, x, y, z):
        events.append(("landing", index, mark, x, y, z))
        return defect != "landing"

    def create(x, y, z, kind, error):
        assert type(error) is int and error == 0
        events.append(("create", x, y, z, kind, error))
        return (None if defect == "creation" else display), (1 if defect == "status" else 0)

    draw = SimpleNamespace(
        ActivateView=lambda _name: True,
        ClearSelection2=lambda _all: selected.clear(),
        SelectionManager=SimpleNamespace(
            CreateSelectData=SimpleNamespace,
            GetSelectedObjectCount2=lambda _mark: len(selected),
            SetSelectionPoint2=landing,
        ),
        Extension=SimpleNamespace(
            AddSpecificDimension=create,
            SelectByID2=lambda *_: pytest.fail("native angle must not coordinate hit-test"),
        ),
    )
    monkeypatch.setattr(_drawing_edge_dimensions, "_early_bound", lambda obj, *_: obj)
    monkeypatch.setattr(_drawing_edge_dimensions, "view_name", lambda *_: "front")
    kwargs = dict(
        p0=(0.22, 0.2), p1=(0.13, 0.2), text_xy=(0.24, 0.21),
        entities=(first, second), orientation="angular", label="end-land angle",
    )
    if defect is None:
        assert _drawing_edge_dimensions.add_edge_dimension(
            SimpleNamespace(currentModel=draw), view, **kwargs,
        ) is display
        assert events[4:] == [
            ("create", 0.24, 0.21, 0.0, 3, 0),
            ("driven-set", 1), ("driven-read", 1),
        ]
        assert model.DrivenState == 1
        assert events[1] == ("landing", 1, -1, 0.22, 0.2, 0.0)
        assert events[3] == ("landing", 2, -1, 0.13, 0.2, 0.0)
    else:
        with pytest.raises(RuntimeError, match=r"angular dimension \(1\)" if defect == "status" else None):
            _drawing_edge_dimensions.add_edge_dimension(
                SimpleNamespace(currentModel=draw), view, **kwargs,
            )
        if defect in {"selection", "landing"}:
            assert not any(event[0] == "create" for event in events)
        if defect in {"creation", "status", "missing-model"}:
            assert not any(event[0].startswith("driven-") for event in events)


@pytest.mark.parametrize("defect", [
    None, "wrong", "degrees_as_radians", "supplementary", "wrong_type",
    "missing", "no_value", "nan", "inf",
])
def test_native_land_angle_measures_source_angle_in_radians_and_fails_closed(
    monkeypatch: pytest.MonkeyPatch, defect: str | None,
) -> None:
    expected = math.degrees(ch_rocker_arm_spec._ALPHA_TOP)
    radians = ch_rocker_arm_spec._ALPHA_TOP
    values = {
        "wrong": radians + math.radians(0.1),
        "degrees_as_radians": expected,
        "supplementary": math.pi - radians,
        "no_value": None,
        "nan": float("nan"),
        "inf": float("inf"),
    }
    model = SimpleNamespace(
        SystemValue=values.get(defect, radians),
        Type2=1 if defect == "wrong_type" else 3,
    )
    display = SimpleNamespace(
        Type2=1 if defect == "wrong_type" else 3,
        GetDimension2=lambda _index: None if defect == "missing" else model,
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, *_: obj)
    kwargs = dict(expected_degrees=expected, label="end-land angle")
    if defect is None:
        assert drawing._require_native_angle(display, **kwargs) == pytest.approx(expected)
    else:
        with pytest.raises(RuntimeError):
            drawing._require_native_angle(display, **kwargs)


@pytest.mark.parametrize("name", [
    "ROD_TIP_X", "TIP_FACE", "_ALPHA_TOP", "BOT_END_X", "HUB_DIA",
    "HUB_LENGTH", "ARM_THICKNESS",
])
def test_measured_dimension_expectations_import_the_geometry_source(name: str) -> None:
    assert getattr(drawing, name) == getattr(ch_rocker_arm_spec, name)


class _NativeQuantity:
    """A native display/model pair, retaining independent text and size bands."""

    def __init__(self, name: str, mm: float, *, precision: int = 2) -> None:
        self.name = name
        self.precision = precision
        self.text = {
            1: "<MOD-DIAM>" if name in {"PivotDia", "HubDia"} else "", 2: "",
            3: "<native-upper>", 4: "<native-lower>",
        }
        self.writes = []
        self.ignored_text = None
        self.ignored_precision = False
        self.ShowDimensionValue = True
        self.SolidLeader = True
        self.ArrowSide = 0
        self.second_arrow = (True, True)
        self.Type2 = 6 if name in {"PivotDia", "HubDia"} else 1
        self.band = tuple(v / 1000.0 for v in ch_rocker_arm_spec.PIVOT_HOLE_BAND)
        self.tolerance_type = 4 if name == "PivotDia" else 0
        self.attached = ()
        self.dangling = False
        self.arc_conditions = {1: 2, 2: 0}
        self.model = SimpleNamespace(
            SystemValue=mm / 1000.0,
            Type2=6 if name in {"PivotDia", "HubDia"} else 1,
            SetToleranceType=self._set_tolerance_type,
            GetToleranceType=lambda: self.tolerance_type,
            Tolerance=SimpleNamespace(
                GetMaxValue=lambda: self.band[0],
                GetMinValue=lambda: self.band[1],
            ),
            GetArcEndCondition=lambda index: self.arc_conditions[index],
            SetArcEndCondition=self._set_arc_condition,
        )

    def _set_tolerance_type(self, kind):
        self.tolerance_type = kind
        return True

    def GetSpecificAnnotation(self):
        return self

    def GetAnnotation(self):
        return self

    def GetDimension2(self, _index):
        return self.model

    def GetDimension(self):
        return self.model

    def _set_arc_condition(self, index, condition):
        self.arc_conditions[index] = condition
        return 0

    def GetAttachedEntities3(self):
        return self.attached

    def GetAttachedEntityTypes(self):
        return tuple(1 for _ in self.attached)

    def IsDangling(self):
        return self.dangling

    def GetText(self, part):
        return self.text[{5: 1, 6: 2, 7: 3, 8: 4}.get(part, part)]

    def SetText(self, part, value):
        self.writes.append((part, value))
        if part != self.ignored_text:
            self.text[part] = value

    def SetPrecision3(self, primary, _dual, _primary_tolerance, _dual_tolerance):
        if not self.ignored_precision:
            self.precision = primary
        return 0  # Native integer status, not VT_BOOL.

    def GetPrimaryPrecision2(self):
        return self.precision

    def SetSecondArrow(self, use_doc, enabled):
        self.second_arrow = (use_doc, enabled)

    def GetUseDocSecondArrow(self):
        return self.second_arrow[0]

    def GetSecondArrow(self):
        return self.second_arrow[1]


def _imported_native_quantities(monkeypatch: pytest.MonkeyPatch):
    from solidworks_mcp.adapters import sw_type_info
    import _drawing_dimensions
    import _drawing_edge_dimensions

    displays = {
        "PivotDia": _NativeQuantity("PivotDia", ch_rocker_arm_spec.PIVOT_HOLE_DIA),
        "RodTipLen": _NativeQuantity("RodTipLen", ch_rocker_arm_spec.TIP_FACE),
        "HubDia": _NativeQuantity("HubDia", ch_rocker_arm_spec.HUB_DIA),
    }
    adapter = SimpleNamespace(
        _attempt=lambda fn, **_kwargs: fn(), swApp=_APP,
        currentModel=SimpleNamespace(GraphicsRedraw2=lambda: None),
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, *_: obj)
    monkeypatch.setattr(_drawing_edge_dimensions, "_early_bound", lambda obj, *_: obj)
    monkeypatch.setattr(_drawing_dimensions, "_early_bound", lambda obj, *_: obj)
    monkeypatch.setattr(sw_type_info, "early_bound_or_flag", lambda obj, *_: obj)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, ann: ann.name)
    monkeypatch.setattr(_drawing_dimensions, "dimension_name", lambda _adapter, ann: ann.name)
    monkeypatch.setattr(_drawing_dimensions, "rebuild_drawing", lambda *_a, **_k: None)
    return adapter, displays


def test_front_native_process_keeps_the_nominal_token_and_model_bore_band(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, displays = _imported_native_quantities(monkeypatch)
    before = {name: display.model.SystemValue for name, display in displays.items()}
    drawing._dress_detail_dimensions(adapter, list(displays.values()), keep={**drawing.HUB_KEEP, **drawing.END_KEEP})
    pivot = displays["PivotDia"]
    assert pivot.text[1].startswith("REAM ")
    assert "<MOD-DIAM>" in pivot.text[1]
    assert pivot.text[2] == " THRU"
    assert not any(part == 0 for part, _text in pivot.writes)
    assert not any(nominal in text for _part, text in pivot.writes for nominal in (
        "6.50", "5.588", "10.20", "+0.03",
    ))
    assert {name: display.model.SystemValue for name, display in displays.items()} == before
    assert displays["HubDia"].precision == 2
    assert pivot.band == tuple(v / 1000.0 for v in ch_rocker_arm_spec.PIVOT_HOLE_BAND)
    assert pivot.model.GetToleranceType() == 4
    assert pivot.ShowDimensionValue is True
    assert (pivot.text[3], pivot.text[4]) == ("<native-upper>", "<native-lower>")


@pytest.mark.parametrize("name", ["PivotDia", "RodTipLen", "HubDia"])
@pytest.mark.parametrize("defect", ["missing", "wrong", "nan", "inf", "no_value"])
def test_imported_front_sizes_require_each_sourced_native_readback(
    monkeypatch: pytest.MonkeyPatch, name: str, defect: str,
) -> None:
    adapter, displays = _imported_native_quantities(monkeypatch)
    if defect == "missing":
        del displays[name]
    else:
        model = displays[name].model
        model.SystemValue = (
            model.SystemValue + 0.0001 if defect == "wrong"
            else None if defect == "no_value"
            else float(defect)
        )
    with pytest.raises(RuntimeError):
        drawing._dress_detail_dimensions(adapter, list(displays.values()), keep={**drawing.HUB_KEEP, **drawing.END_KEEP})


@pytest.mark.parametrize("ignored", ["prefix", "suffix", "hub_precision"])
def test_front_native_dressing_rejects_ignored_text_or_lost_hub_precision(
    monkeypatch: pytest.MonkeyPatch, ignored: str,
) -> None:
    adapter, displays = _imported_native_quantities(monkeypatch)
    if ignored == "hub_precision":
        displays["HubDia"].precision = 1
    else:
        displays["PivotDia"].ignored_text = 1 if ignored == "prefix" else 2
    with pytest.raises(RuntimeError):
        drawing._dress_detail_dimensions(adapter, list(displays.values()), keep=drawing.HUB_KEEP)


@pytest.fixture
def native_front(monkeypatch: pytest.MonkeyPatch):
    """CAD-owned endpoints feed fake creation; real selectors/readback stay live."""
    import _drawing_edge_dimensions
    from _drawing_edges import ViewEdge, ViewEdges

    adapter, imported = _imported_native_quantities(monkeypatch)
    vertex_points = {}
    rows = []
    for z in (-drawing.ARM_THICKNESS / 2.0, drawing.ARM_THICKNESS / 2.0):
        for sign in (-1, 1):
            upper = (sign * drawing.TOP_END_X, drawing.TOP_END_Y, z)
            outer = (sign * drawing.ROD_TIP_X, drawing._ROD_TIP_Y, z)
            lower = (sign * drawing.BOT_END_X, drawing._BOT_END_Y, z)
            vertices = [object() for _ in range(3)]
            vertex_points.update(zip(vertices, (upper, outer, lower)))
            rows.extend((
                ViewEdge(object(), (upper, outer), None, tuple(vertices[:2])),
                ViewEdge(object(), (outer, lower), None, tuple(vertices[1:])),
            ))
    scan = ViewEdges("front native CAD", tuple(rows))
    land = scan.exact_line_through(
        (drawing._TIP_FACE_MID_X, drawing._TIP_FACE_MID_Y, drawing.ARM_THICKNESS / 2.0),
        label="fixture front radial land",
    )
    pivot = object()
    state = SimpleNamespace(
        adapter=adapter, imported=imported, scan=scan, land=land,
        displays={}, calls=[], verticals=[], basic_calls=[],
        defect_label=None, defect=None,
    )

    def project(_adapter, _view, points, *, label):
        mapper = _end_xy if label.startswith("datum C") or label == "rod land angular endpoints" else _front_xy
        return [mapper(x * 1000.0, y * 1000.0) for x, y, _z in points]

    def vertical(_adapter, _front, points):
        entity = object()
        state.verticals.append((entity, points))
        return entity

    def create(_adapter, _front, **kwargs):
        state.calls.append(kwargs)
        label = kwargs["label"]
        entities = kwargs["entities"]
        if label == "rocker overall width":
            value_mm = abs(vertex_points[entities[1]][0] - vertex_points[entities[0]][0])
        elif label == "taper intersection X":
            value_mm = abs(vertex_points[entities[1]][0])
        elif label == "radial land angle to mirror axis":
            a, b = land.line
            radians = math.atan2(abs(a[0] - b[0]), abs(a[1] - b[1]))
            value_mm = radians * 1000.0
        else:
            pytest.fail(f"unowned native dimension {label}")
        display = _NativeQuantity(label, value_mm)
        display.attached = entities
        if kwargs["orientation"] == "angular":
            display.Type2 = 3
        if state.defect_label == label:
            if state.defect == "creation":
                raise RuntimeError(f"native dimension refused: {label}")
            if state.defect == "wrong":
                display.model.SystemValue += 0.0001
            elif state.defect in {"nan", "inf"}:
                display.model.SystemValue = float(state.defect)
            elif state.defect == "missing":
                display.model.SystemValue = None
            elif state.defect == "attachment":
                display.attached = (entities[0], object())
            elif state.defect == "null-attachment":
                display.attached = (None, entities[1])
            elif state.defect == "null-annotation":
                display.GetAnnotation = lambda: None
            elif state.defect == "basic":
                display.model.SetToleranceType = lambda _kind: True
            elif state.defect == "text":
                display.ignored_text = 4
        state.displays[label] = display
        return display

    monkeypatch.setattr(drawing, "curate_view_dimensions", lambda *_a, **_k: list(imported.values()))
    monkeypatch.setattr(
        drawing, "_basic_profile_dimensions",
        lambda _adapter, annotations: state.basic_calls.append(annotations),
    )
    monkeypatch.setattr(drawing, "scan_view_edges", lambda *_a, **_k: scan)
    monkeypatch.setattr(drawing, "model_points_in_view", project)
    monkeypatch.setattr(drawing, "_project", project)
    monkeypatch.setattr(drawing, "_land_vertical", vertical)
    monkeypatch.setattr(drawing, "visible_circle_edge", lambda *_: pivot)
    monkeypatch.setattr(drawing, "add_edge_dimension", create)
    monkeypatch.setattr(
        _drawing_edge_dimensions, "_is_same_attachment",
        lambda _adapter, actual, expected, _kind: actual is expected,
    )
    return state


def test_outline_dimensions_measure_real_endpoints_and_choose_exact_positive_z_land(
    native_front,
) -> None:
    state = native_front
    drawing._add_rocker_outline_dimensions(state.adapter, object())
    drawing._add_land_angle(state.adapter, object(), state.land)
    assert state.basic_calls
    assert all(point[2] == ch_rocker_arm_spec.ARM_THICKNESS / 2.0 for point in state.land.line)
    expected = {
        "rocker overall width": 2.0 * ch_rocker_arm_spec.ROD_TIP_X / 1000.0,
        "taper intersection X": ch_rocker_arm_spec.BOT_END_X / 1000.0,
        "radial land angle to mirror axis": ch_rocker_arm_spec._ALPHA_TOP,
    }
    assert {
        label: display.model.SystemValue for label, display in state.displays.items()
    } == pytest.approx(expected)
    width, taper, angle = state.calls
    assert width["entity_types"] == ("VERTEX", "VERTEX")
    assert "entity_type" not in width
    assert angle["entities"] == (state.land.edge, state.verticals[0][0])
    assert angle["entity_types"] == ("EDGE", "SKETCHSEGMENT")
    assert taper["entity_types"] == ("EDGE", "VERTEX")
    assert state.displays["taper intersection X"].arc_conditions[1] == 1
    vertical_points = state.verticals[0][1]
    assert vertical_points[0][0] == vertical_points[1][0]
    # Local ray stays on the sheet instead of reaching the off-sheet R800 centre.
    assert all(
        DRAWABLE.xmin <= x <= DRAWABLE.xmax and DRAWABLE.ymin <= y <= DRAWABLE.ymax
        for x, y in vertical_points
    )
    assert state.displays["radial land angle to mirror axis"].text[4] == "TO MIRROR PLANE"
    assert state.displays["radial land angle to mirror axis"].model.GetToleranceType() == 1
    assert state.displays["taper intersection X"].text[4] == "R816/TAPER"


@pytest.mark.parametrize("label", [
    "rocker overall width", "radial land angle to mirror axis", "taper intersection X",
])
@pytest.mark.parametrize("defect", ["creation", "wrong", "missing", "nan", "inf", "attachment"])
def test_each_new_outline_measurement_fails_closed(native_front, label, defect) -> None:
    native_front.defect_label = label
    native_front.defect = defect
    with pytest.raises(RuntimeError):
        if label == "radial land angle to mirror axis":
            drawing._add_land_angle(native_front.adapter, object(), native_front.land)
        else:
            drawing._add_rocker_outline_dimensions(native_front.adapter, object())


@pytest.mark.parametrize("source", ["ROD_TIP_X", "TIP_FACE", "_ALPHA_TOP", "BOT_END_X", "HUB_DIA"])
def test_source_geometry_change_invalidates_stale_front_measurements(
    native_front, monkeypatch: pytest.MonkeyPatch, source: str,
) -> None:
    monkeypatch.setattr(drawing, source, getattr(drawing, source) + 0.1)
    with pytest.raises(RuntimeError):
        if source == "TIP_FACE":
            drawing._add_land_datum(native_front.adapter, object(), native_front.land)
        elif source == "_ALPHA_TOP":
            drawing._add_land_angle(native_front.adapter, object(), native_front.land)
        elif source == "HUB_DIA":
            drawing._dress_detail_dimensions(native_front.adapter, list(native_front.imported.values()), keep=drawing.HUB_KEEP)
        else:
            drawing._add_rocker_outline_dimensions(native_front.adapter, object())


def test_datum_c_owns_the_named_positive_z_land_and_midpoint_landing(
    native_front, monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    tag = object()

    def insert(_adapter, _front, **kwargs):
        calls.append(kwargs)
        return tag

    monkeypatch.setattr(drawing, "add_datum_feature", insert)
    assert drawing._add_land_datum(
        native_front.adapter, object(), native_front.land,
    ) is tag
    (call,) = calls
    assert call["datum"] == "C"
    assert call["edge_entity"] is native_front.land.edge
    assert "edge_xy" not in call and "expected_entity" not in call
    a, b = native_front.land.line
    expected = _end_xy((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
    assert call["leader_attach_xy"] == pytest.approx(expected)
    assert math.dist(call["symbol_xy"], expected) == pytest.approx(drawing.LAND_DATUM_STANDOFF)
    assert call["symbol_xy"][0] > expected[0]


@pytest.mark.parametrize("defect", ["rear_face", "wrong_length", "not_a_line"])
def test_datum_c_refuses_a_nonland_owner_before_insertion(
    native_front, monkeypatch: pytest.MonkeyPatch, defect: str,
) -> None:
    from dataclasses import replace

    a, b = native_front.land.line
    if defect == "rear_face":
        line = ((a[0], a[1], -a[2]), (b[0], b[1], -b[2]))
    elif defect == "wrong_length":
        line = (a, (b[0] + 1.0, b[1], b[2]))
    else:
        line = None
    monkeypatch.setattr(
        drawing, "add_datum_feature", lambda *_a, **_k: pytest.fail("invalid C owner inserted"),
    )
    with pytest.raises(RuntimeError):
        drawing._add_land_datum(
            native_front.adapter, object(), replace(native_front.land, line=line),
        )


@pytest.fixture
def native_offset(monkeypatch: pytest.MonkeyPatch):
    import _drawing_edge_dimensions
    from _drawing_edges import ViewEdge, ViewEdges

    adapter, _imported = _imported_native_quantities(monkeypatch)
    a = (drawing.TOP_END_X, drawing.TOP_END_Y, drawing.ARM_THICKNESS / 2.0)
    b = (drawing.ROD_TIP_X, drawing._ROD_TIP_Y, drawing.ARM_THICKNESS / 2.0)
    strap = ViewEdge(object(), (a, b), None, (object(), object()))
    rear = ViewEdge(
        object(), ((a[0], a[1], -a[2]), (b[0], b[1], -b[2])), None,
        (object(), object()),
    )
    hub = ViewEdge(
        object(), None,
        (0.0, drawing.PIVOT_MID_Y, drawing.HUB_LENGTH / 2.0, 0.0, 0.0, 1.0, drawing.HUB_DIA / 2.0),
        None,
    )
    back_hub = ViewEdge(
        object(), None,
        (0.0, drawing.PIVOT_MID_Y, -drawing.HUB_LENGTH / 2.0, 0.0, 0.0, 1.0, drawing.HUB_DIA / 2.0),
        None,
    )
    scan = ViewEdges("right native CAD", (rear, back_hub, strap, hub))
    state = SimpleNamespace(adapter=adapter, scan=scan, strap=strap, hub=hub, display=None, defect=None)

    def create(_adapter, _view, **kwargs):
        assert kwargs["entities"] == (hub.edge, strap.edge)
        assert kwargs["orientation"] == "horizontal"
        mm = hub.circle[2] - strap.midpoint_mm[2]
        display = _NativeQuantity("offset", mm, precision=3)
        display.attached = kwargs["entities"]
        if state.defect == "creation":
            raise RuntimeError("offset native creation refused")
        if state.defect == "wrong":
            display.model.SystemValue += 0.0001
        elif state.defect in {"nan", "inf"}:
            display.model.SystemValue = float(state.defect)
        elif state.defect == "missing":
            display.model.SystemValue = None
        elif state.defect == "attachment":
            display.attached = (hub.edge, object())
        elif state.defect == "band":
            display.tolerance_type = 2
        elif state.defect == "precision":
            display.ignored_precision = True
        elif state.defect in {"prefix", "suffix"}:
            display.ignored_text = 1 if state.defect == "prefix" else 2
        state.display = display
        return display

    monkeypatch.setattr(drawing, "scan_view_edges", lambda *_a, **_k: scan)
    monkeypatch.setattr(
        drawing, "model_points_in_view",
        lambda _adapter, _view, points, **_kwargs: [
            (drawing.RIGHT_CENTER[0] - z, drawing.RIGHT_CENTER[1] + y)
            for _x, y, z in points
        ],
    )
    monkeypatch.setattr(drawing, "add_edge_dimension", create)
    monkeypatch.setattr(
        drawing, "set_arc_endpoints_to_center",
        lambda *_a, **_k: pytest.fail("projected hub end rim is not a circular endpoint"),
    )
    monkeypatch.setattr(
        _drawing_edge_dimensions, "_is_same_attachment",
        lambda _adapter, actual, wanted, _kind: actual is wanted,
    )
    return state


def test_offset_is_the_measured_hub_end_to_strap_face_reference(native_offset) -> None:
    display = drawing._add_strap_offset_dimension(native_offset.adapter, object())
    assert display is native_offset.display
    assert display.model.SystemValue * 1000.0 == pytest.approx(
        (ch_rocker_arm_spec.HUB_LENGTH - ch_rocker_arm_spec.ARM_THICKNESS) / 2.0,
    )
    assert display.model.GetToleranceType() == 0
    assert display.precision == 2
    assert display.text[1] == "(" and display.text[2] == ")"
    assert display.writes == [(1, "("), (2, ")")]
    assert ch_rocker_arm_spec.STRAP_HUB_SYMMETRY == 0.10


@pytest.mark.parametrize("defect", [
    "creation", "wrong", "missing", "nan", "inf", "attachment",
    "band", "precision", "prefix", "suffix",
])
def test_offset_cannot_ship_a_wrong_or_unchecked_reference(native_offset, defect) -> None:
    native_offset.defect = defect
    with pytest.raises(RuntimeError):
        drawing._add_strap_offset_dimension(native_offset.adapter, object())


@pytest.mark.parametrize("source,delta", [("HUB_LENGTH", 0.001), ("ARM_THICKNESS", 0.0001)])
def test_offset_formula_change_invalidates_stale_native_measurement(
    native_offset, monkeypatch: pytest.MonkeyPatch, source: str, delta: float,
) -> None:
    # Both changed picks remain within exact/circle selector tolerances; it is
    # the formula readback, not a missing entity, that must reject the stale CAD.
    monkeypatch.setattr(drawing, source, getattr(drawing, source) + delta)
    with pytest.raises(RuntimeError, match="strap offset from hub end measures"):
        drawing._add_strap_offset_dimension(native_offset.adapter, object())


def test_projection_barrier_is_void_and_precedes_native_math(bound, monkeypatch):
    events = []
    view = SimpleNamespace(UpdateViewDisplayGeometry=lambda: events.append("barrier"))
    def project(_adapter, actual, points, **_kwargs):
        assert actual is view and events == ["barrier"]
        return [(0.180, 0.095)]
    monkeypatch.setattr(drawing, "model_points_in_view", project)
    assert drawing._project(object(), view, [(0, 0, 0)], label="D physical centre") == [(0.180, 0.095)]


class _DetailCircle:
    """Native method-shaped labels, void setter, two out-double getter."""
    def __init__(self, label, *, ignored=False):
        self.label, self.ignored = label, ignored
        self.xy = (0.0, 0.0)

    def GetLabel(self):
        return self.label

    def SetLabelPosition(self, x, y):
        if not self.ignored:
            self.xy = (x, y)

    def GetLabelPosition(self):
        return self.xy


@pytest.mark.parametrize("labels", [("E", "D"), ("D",), ("D", "D"), ("D", "E", "F")])
def test_detail_letters_bind_by_exact_native_label_not_enumeration(bound, monkeypatch, labels):
    circles = [_DetailCircle(label) for label in labels]
    front = SimpleNamespace(GetDetailCircles=lambda: circles)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: None)
    if labels == ("E", "D"):
        drawing._place_detail_letters(object(), front)
        assert {circle.label: circle.xy for circle in circles} == drawing.DETAIL_LETTER_XY
    else:
        with pytest.raises(RuntimeError, match="exactly D/E"):
            drawing._place_detail_letters(object(), front)


def test_detail_letter_refuses_a_silently_ignored_void_setter(bound, monkeypatch):
    circles = [_DetailCircle("D"), _DetailCircle("E", ignored=True)]
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: None)
    with pytest.raises(RuntimeError, match="native letter stayed"):
        drawing._place_detail_letters(object(), SimpleNamespace(GetDetailCircles=lambda: circles))


class _DetailTransform:
    """Nonidentity native sketch transform; inverse maps back to sheet units."""
    __slots__ = ("scale", "translation", "bad_inverse", "bad_matrix", "inverse_calls")

    def __init__(self, scale=2.0, translation=(0.013, -0.007, 0.0)):
        self.scale, self.translation = scale, translation
        self.bad_inverse = self.bad_matrix = False
        self.inverse_calls = 0

    @property
    def ArrayData(self):
        return () if self.bad_matrix else (
            1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0,
            *self.translation, self.scale, 0.0, 0.0, 0.0,
        )

    def Inverse(self):
        self.inverse_calls += 1
        if self.bad_inverse:
            return None
        return _DetailTransform(1.0 / self.scale, tuple(-v / self.scale for v in self.translation))

    def IInverse(self):
        raise AssertionError("R11 IDispatch rejects IInverse; use the automation Inverse method")

    def apply(self, xyz):
        return tuple(xyz[i] * self.scale + self.translation[i] for i in range(3))


class _DetailMathPoint:
    __slots__ = ("_coordinates",)

    def __init__(self, values):
        self._coordinates = tuple(values.value)  # VARIANT input, native tuple getter.
        assert len(self._coordinates) == 3

    @property
    def ArrayData(self):
        return self._coordinates

    def MultiplyTransform(self, transform):
        point = object.__new__(_DetailMathPoint)
        point._coordinates = transform.apply(self._coordinates)
        return point


class _DetailParent:
    __slots__ = ("transform", "ScaleRatio", "projection_scale")

    def __init__(self):
        self.transform = _DetailTransform()
        self.ScaleRatio = (1.0, 2.0)
        self.projection_scale = 0.5

    def GetSketch(self):
        return SimpleNamespace(ModelToSketchTransform=self.transform)

    def UpdateViewDisplayGeometry(self):
        return None

    def project(self, xyz):
        return (0.180 + xyz[0] * self.projection_scale,
                0.175 + xyz[1] * self.projection_scale)


class _DetailProfile:
    __slots__ = ("centre", "radius", "sketch", "complete", "segment_type", "selectable")

    def __init__(self, centre, radius, sketch):
        self.centre, self.radius, self.sketch = centre, radius, sketch
        self.complete, self.segment_type, self.selectable = 1, 1, True

    def GetType(self):
        return self.segment_type

    def IsCircle(self):
        return self.complete  # Native INT 1/0.

    def GetCenterPoint2(self):
        if self.centre is None:
            return None
        return SimpleNamespace(X=self.centre[0], Y=self.centre[1], Z=self.centre[2])

    def GetRadius(self):
        return self.radius

    def GetSketch(self):
        return self.sketch

    def Select4(self, _append, _data):
        return self.selectable


class _DetailCropCircle:
    __slots__ = ("label", "profiles", "NoOutline", "JaggedOutline", "full", "display")

    def __init__(self, label, profile):
        self.label, self.profiles = label, (profile,)
        self.NoOutline, self.JaggedOutline, self.full, self.display = False, False, True, 1

    def GetLabel(self):
        return self.label

    def GetDisplay(self):
        return self.display

    def HasFullOutline(self):
        return self.full

    def GetProfileItems(self):
        return self.profiles


class _DetailView:
    """Native bbox padding/offset is independent of the persisted crop circle."""
    __slots__ = ("parent", "radius", "defect", "_position", "physical",
                 "_scale_ratio", "UseParentScale", "UseSheetScale", "events",
                 "crop_circle", "padding", "bbox_offset", "model_centre", "notes", "annotations")

    def __init__(self, parent, *, label="D", defect=None, padding=0.01096794, bbox_offset=(0.0, 0.005)):
        self.parent, self.defect = parent, defect
        self.model_centre, radius_mm = drawing._detail_fence(label)
        ratio = drawing.HUB_SCALE if label == "D" else drawing.END_SCALE
        self.radius = radius_mm / 1000.0 * ratio[0] / ratio[1]
        self.Position = (0.210, 0.110)
        self.physical = self._position
        self._scale_ratio = ratio
        self.UseParentScale = False
        self.UseSheetScale = 0
        self.events = []
        self.crop_circle = None
        self.padding, self.bbox_offset = padding, bbox_offset
        self.notes, self.annotations = [], []

    @property
    def Position(self):
        return None if self.defect == "missing-position" else self._position

    @Position.setter
    def Position(self, value):
        self._position = tuple(value)
        assert len(self._position) == 2

    @property
    def ScaleRatio(self):
        return self._scale_ratio

    @ScaleRatio.setter
    def ScaleRatio(self, value):
        # Native property puts receive VARIANT; getters expose a SAFEARRAY tuple.
        ratio = tuple(value.value)
        assert len(ratio) == 2
        self._scale_ratio = (1.0, 2.0) if self.defect == "scale" else ratio

    def GetBaseView(self):
        return object() if self.defect == "parent" else self.parent

    def GetDetail(self):
        return self.crop_circle

    def GetNotes(self):
        return tuple(self.notes)

    def GetAnnotations(self):
        return tuple(self.annotations)

    def project(self, xyz):
        assert self.events[-1] == "barrier"
        scale = self._scale_ratio[0] / self._scale_ratio[1]
        return tuple(self.physical[i] + (xyz[i] - self.model_centre[i]) * scale for i in range(2))

    def GetOutline(self):
        if self.defect == "invalid-bbox":
            return (0.0, 0.0, float("nan"), 1.0)
        x, y = (self._position[i] + self.bbox_offset[i] for i in range(2))
        radius = self.radius + self.padding
        return (x - radius, y - radius, x + radius, y + radius)

    def SetViewPosition(self, xy, _children):
        position = tuple(xy.value)
        assert len(position) == 2
        self.events.append("move")
        if self.defect == "move":
            return False
        if self.defect != "ignored-move":
            self.Position = position
        return True

    def UpdateViewDisplayGeometry(self):
        self.events.append("barrier")
        if self.defect != "stale":
            self.physical = self._position


@pytest.mark.parametrize("defect", [None, "activation", "parent", "scale", "move", "ignored-move", "stale", "missing-position", "fence", "selection", "creation", "source-radius", "source-centre", "profile-radius", "profile-centre", "near-profile-centre", "partial", "missing-profile", "outline-flags", "projection-scale"])
def test_native_detail_fences_parent_links_scale_and_settled_projection(bound, monkeypatch, defect):
    parent = _DetailParent()
    if defect == "projection-scale":
        parent.projection_scale = 0.7
    detail = _DetailView(parent, defect=defect)
    created = []
    class Manager:
        __slots__ = ("AddToDB",)
        def __init__(self):
            self.AddToDB = False
        def CreateCircle(self, *args):
            centre, rim = tuple(args[:3]), tuple(args[3:])
            circle = _DetailProfile(centre, math.dist(centre, rim), parent.GetSketch())
            circle.selectable = defect != "selection"
            if defect == "source-radius":
                circle.radius *= 1.5
            elif defect == "source-centre":
                circle.centre = (centre[0] + 0.01, centre[1], centre[2])
            created.append(circle)
            return None if defect == "fence" else circle
    class SelectData:
        __slots__ = ("View",)
    manager = Manager()
    calls = []
    def create(*args):
        calls.append(args)
        source = created[0]
        profile = _DetailProfile(source.centre, source.radius, source.sketch)
        if defect == "profile-radius":
            profile.radius *= 1.5
        elif defect == "profile-centre":
            profile.centre = (profile.centre[0] + 0.01, profile.centre[1], profile.centre[2])
        elif defect == "near-profile-centre":
            profile.centre = (profile.centre[0] + 0.00002, profile.centre[1], profile.centre[2])
        elif defect == "partial":
            profile.complete = 0
        detail.crop_circle = _DetailCropCircle("D", profile)
        if defect == "missing-profile":
            detail.crop_circle.profiles = ()
        elif defect == "outline-flags":
            detail.crop_circle.full = False
        return None if defect == "creation" else detail
    doc = SimpleNamespace(
        ActivateView=lambda _name: defect != "activation", ClearSelection2=lambda _all: None,
        SketchManager=manager,
        SelectionManager=SimpleNamespace(CreateSelectData=SelectData),
        CreateDetailViewAt4=create,
    )
    adapter = SimpleNamespace(
        currentModel=doc, swApp=SimpleNamespace(
            IsSame=_APP.IsSame, GetMathUtility=lambda: SimpleNamespace(CreatePoint=_DetailMathPoint),
        ),
    )
    monkeypatch.setattr(drawing, "model_points_in_view",
                        lambda _adapter, view, points, **_kwargs: [view.project(point) for point in points])
    monkeypatch.setattr(drawing, "view_name", lambda *_a: "front")
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", lambda *_a: None)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: None)
    kwargs = dict(centre=(0.0, drawing.PIVOT_MID_Y / 1000.0, 0.0),
                  radius_mm=drawing.HUB_DIA / 2 + drawing.PIVOT_HOLE_DIA / 4,
                  target=drawing.HUB_CENTER, scale=drawing.HUB_SCALE, label="D")
    if defect is None:
        assert drawing._create_detail(adapter, parent, **kwargs) is detail
        assert detail.Position == pytest.approx(drawing.HUB_CENTER, rel=0.0, abs=1e-12)
        assert detail.physical == pytest.approx(drawing.HUB_CENTER, rel=0.0, abs=1e-12)
        assert tuple(detail.ScaleRatio) == drawing.HUB_SCALE
        assert detail.events.count("move") == 1
        assert detail.events.count("barrier") >= 4
        assert detail.GetOutline()[3] > drawing.HUB_CENTER[1] + detail.radius
        assert created[0].radius == pytest.approx(0.006725)  # Nonidentity sketch scale 2.
        assert parent.transform.inverse_calls >= 2
        assert calls[0][7:] == (1, True, False, False, 5)
    else:
        with pytest.raises(RuntimeError):
            drawing._create_detail(adapter, parent, **kwargs)
    assert manager.AddToDB is False


def _native_crop_fixture(monkeypatch, label, *, centre=None, defect=None):
    """Readback fixture, including persisted geometry and a padded native bbox."""
    parent = _DetailParent()
    view = _DetailView(parent, label=label, defect=defect)
    view.Position = centre or (drawing.HUB_CENTER if label == "D" else drawing.END_CENTER)
    view.physical = view.Position
    source_centre, source_radius = drawing._detail_fence(label)
    xy = parent.project(source_centre)
    profile = _DetailProfile(
        parent.transform.apply((*xy, 0.0)),
        source_radius / 1000.0 * 0.5 * parent.transform.scale,
        parent.GetSketch(),
    )
    view.crop_circle = _DetailCropCircle(label, profile)
    adapter = SimpleNamespace(
        swApp=SimpleNamespace(GetMathUtility=lambda: SimpleNamespace(CreatePoint=_DetailMathPoint)),
        currentModel=SimpleNamespace(GraphicsRedraw2=lambda: None),
    )
    monkeypatch.setattr(drawing, "model_points_in_view",
                        lambda _adapter, native, points, **_kwargs: [native.project(p) for p in points])
    return adapter, view


def test_detail_transform_fake_refuses_native_inverse_but_supports_automation():
    transform = _DetailTransform()
    with pytest.raises(AssertionError, match="IDispatch rejects IInverse"):
        transform.IInverse()
    inverse = transform.Inverse()
    assert inverse is not None
    assert inverse.apply(transform.apply((0.180, 0.175, 0.0))) == pytest.approx((0.180, 0.175, 0.0))
    assert transform.inverse_calls == 1
    transform.bad_inverse = True
    assert transform.Inverse() is None


@pytest.mark.parametrize("label", ["D", "E"])
def test_crop_reads_persisted_circle_not_padded_or_offset_native_view_bbox(bound, monkeypatch, label):
    adapter, view = _native_crop_fixture(monkeypatch, label)
    crop = drawing._detail_crop(adapter, view, label=label)
    x, y = view.physical
    assert crop == pytest.approx((x - view.radius, y - view.radius, x + view.radius, y + view.radius))
    bbox = view.GetOutline()
    assert bbox[2] - bbox[0] > crop[2] - crop[0] + 0.020
    assert (bbox[1] + bbox[3]) / 2.0 == pytest.approx(y + 0.005)
    assert view.crop_circle.profiles[0].GetRadius() != pytest.approx(view.radius)
    assert view.parent.ScaleRatio == (1.0, 2.0)  # Parent .5, native D 4 / E 2.
    assert view.parent.transform.inverse_calls == 1


def test_crop_preserves_actual_native_geometry_within_readback_tolerance(bound, monkeypatch):
    adapter, view = _native_crop_fixture(monkeypatch, "D")
    profile = view.crop_circle.profiles[0]
    profile.centre = (profile.centre[0] + 0.00002, *profile.centre[1:])
    profile.radius += 0.00002
    # Inverse sketch scale 2, then detail/parent magnification 8: 80 um on sheet.
    crop = drawing._detail_crop(adapter, view, label="D")
    x, y = view.physical[0] + 0.00008, view.physical[1]
    radius = view.radius + 0.00008
    assert crop == pytest.approx((x - radius, y - radius, x + radius, y + radius), abs=1e-12)
    assert (crop[0] + crop[2]) / 2.0 != pytest.approx(view.physical[0], abs=1e-6)
    assert (crop[2] - crop[0]) / 2.0 != pytest.approx(view.radius, abs=1e-6)


@pytest.mark.parametrize("defect", [
    "radius", "nan-radius", "zero-radius", "centre", "off-sheet-plane", "missing-centre", "partial", "segment",
    "empty", "missing-items", "multiple", "missing-segment",
    "missing-circle", "missing-parent", "no-outline", "jagged", "full-outline", "display", "label",
    "inverse", "matrix", "missing-sketch", "missing-transform", "missing-utility", "parent-scale", "parent-scale-shape", "projection-scale",
    "detail-scale", "detail-scale-shape", "parent-scale-link", "sheet-scale-link", "invalid-bbox",
])
def test_native_crop_refuses_wrong_persisted_geometry_flags_or_coordinate_frame(bound, monkeypatch, defect):
    adapter, view = _native_crop_fixture(monkeypatch, "D")
    circle, parent = view.crop_circle, view.parent
    profile = circle.profiles[0]
    if defect == "radius":
        profile.radius *= 1.5
    elif defect == "nan-radius":
        profile.radius = float("nan")
    elif defect == "zero-radius":
        profile.radius = 0.0
    elif defect == "centre":
        profile.centre = (profile.centre[0] + 0.01, *profile.centre[1:])
    elif defect == "off-sheet-plane":
        profile.centre = (*profile.centre[:2], 0.01)
    elif defect == "missing-centre":
        profile.centre = None
    elif defect == "partial":
        profile.complete = 0
    elif defect == "segment":
        profile.segment_type = 0
    elif defect in ("empty", "missing-items", "multiple"):
        circle.profiles = {"empty": (), "missing-items": None, "multiple": (profile, profile)}[defect]
    elif defect == "missing-segment":
        circle.profiles = (None,)
    elif defect == "missing-circle":
        view.crop_circle = None
    elif defect == "missing-parent":
        view.parent = None
    elif defect == "no-outline":
        circle.NoOutline = True
    elif defect == "jagged":
        circle.JaggedOutline = True
    elif defect == "full-outline":
        circle.full = False
    elif defect == "display":
        circle.display = 0
    elif defect == "label":
        circle.label = "X"
    elif defect == "inverse":
        parent.transform.bad_inverse = True
    elif defect == "matrix":
        parent.transform.bad_matrix = True
    elif defect == "missing-sketch":
        profile.sketch = None
    elif defect == "missing-transform":
        profile.sketch.ModelToSketchTransform = None
    elif defect == "missing-utility":
        adapter.swApp.GetMathUtility = lambda: None
    elif defect == "parent-scale":
        parent.ScaleRatio = (1.0, 1.0)
    elif defect == "parent-scale-shape":
        parent.ScaleRatio = None
    elif defect == "projection-scale":
        parent.projection_scale = 0.7
    elif defect == "detail-scale":
        view._scale_ratio = (1.0, 2.0)
    elif defect == "detail-scale-shape":
        view._scale_ratio = None
    elif defect == "parent-scale-link":
        view.UseParentScale = True
    elif defect == "sheet-scale-link":
        view.UseSheetScale = 1
    elif defect == "invalid-bbox":
        view.defect = "invalid-bbox"
    with pytest.raises(RuntimeError):
        drawing._detail_crop(adapter, view, label="D")


def _native_sheet(*, top=0.066, scale_retained=True, rule=True, missing_endpoint=None):
    template = drawing.DRAWING_TEMPLATES[drawing.SPEC.layout]
    def line(y):
        return SimpleNamespace(
            GetType=lambda: 0,
            GetStartPoint2=lambda: None if missing_endpoint == "start" else SimpleNamespace(X=template.title_block_left_m, Y=y),
            GetEndPoint2=lambda: None if missing_endpoint == "end" else SimpleNamespace(X=template.width_m - 0.0127, Y=y),
        )
    state = {"scale": (1.0, 1.0)}
    def set_scale(numerator, denominator, _position, _text):
        if scale_retained:
            state["scale"] = (numerator, denominator)
        return True
    return SimpleNamespace(
        SetScale=set_scale,
        GetProperties2=lambda: (0, 0, *state["scale"], 0, 0.4318, 0.2794, 0),
        GetTemplateSketch=lambda: SimpleNamespace(GetSketchSegments=lambda: [line(top), line(top / 2)] if rule else []),
    )


@pytest.mark.parametrize("endpoint", ["start", "end"])
def test_title_block_rule_refuses_null_native_endpoint(bound, endpoint):
    with pytest.raises(RuntimeError, match="native title-block rule endpoint unavailable"):
        drawing._title_block_top(SimpleNamespace(), _native_sheet(missing_endpoint=endpoint))


class _CaptionTextFormat:
    """Read-only test surface for the native properties the probe reads."""

    CharHeight = property(lambda self: 0.0035)
    CharHeightInPts = property(lambda self: 10)
    TypeFaceName = property(lambda self: "Arial")
    LineSpacing = property(lambda self: 1.0)

    def IsHeightSpecifiedInPts(self):
        return False


class _CaptionNote(_FakeNote):
    def __init__(self, label, *, height=0.007):
        super().__init__((0.16 if label == "D" else 0.30, 0.07), height)
        self.label = label
        self._linked = "<VLNAME> <VLLABEL>\r\nSCALE <VLSCALE>"
        self.annotation.SetPosition2 = self.annotation.SetPosition
        self.annotation.GetTextFormatCount = lambda: 1
        self.annotation.GetTextFormat = lambda index: _CaptionTextFormat() if index == 0 else None
        self.annotation.GetUseDocTextFormat = lambda index: index == 0
        self.data = _ClearanceDisplayData([
            {"t": f"DETAIL {label}", "pos": [0.30, 0.07, 0.0], "h": 0.0035},
            {"t": "SCALE 2:1", "pos": [0.30, 0.065, 0.0], "h": 0.0035},
        ], [])
        self.annotation.GetDisplayData = lambda: self.data

    PropertyLinkedText = property(lambda self: self._linked, lambda self, value: setattr(self, "_linked", value))
    HasMultipleFonts = property(lambda self: False)

    def GetText(self):
        return f"DETAIL {self.label}\r\nSCALE 2:1"

    def GetHeight(self):
        return 0.0035

    def GetHeightInPoints(self):
        return 10

    def GetExtent(self):
        extent = list(super().GetExtent())
        extent[3] = extent[0] + 0.03145
        return tuple(extent)


def test_both_caption_diagnostics_log_native_text_formats_and_display_geometry(bound, monkeypatch):
    redraws = []
    adapter = SimpleNamespace(currentModel=SimpleNamespace(GraphicsRedraw2=lambda: redraws.append("redraw")))
    sheet = _native_sheet()
    logs = []
    monkeypatch.setattr(drawing._telemetry, "info", logs.append)
    for label in ("D", "E"):
        note = _CaptionNote(label)
        view = SimpleNamespace(GetNotes=lambda: (note,))
        drawing._record_detail_caption(adapter, view, sheet, label=label, stage="before guards")
    assert len(logs) == 2
    assert redraws == []
    for label, log in zip(("D", "E"), logs, strict=True):
        report = json.loads(log.split("native diagnostics: ", 1)[1])
        assert report["label"] == label and report["native_note_count"] == 1
        assert report["native_title_rule_top_m"] == 0.066
        assert report["native_read_errors"] == {}
        (note,) = report["notes"]
        assert note["native_property_linked_text"] == "<VLNAME> <VLLABEL>\r\nSCALE <VLSCALE>"
        assert note["native_get_text"] == f"DETAIL {label}\r\nSCALE 2:1"
        assert note["resolved_line_count"] == 2
        assert note["native_has_multiple_fonts"] is False
        assert note["native_text_format_count"] == 1
        assert note["native_text_formats"] == [{
            "index": 0, "use_doc_text_format": True, "char_height_m": 0.0035,
            "char_height_pts": 10, "is_height_specified_in_pts": False, "type_face_name": "Arial",
            "line_spacing": 1.0,
        }]
        assert len(note["native_note_get_extent"]) == 6
        assert note["native_note_get_height"] == 0.0035
        assert note["native_note_get_height_in_points"] == 10
        assert note["display_fragment_count"] == 2
        assert note["native_display_fragment_positions"] == [[0.30, 0.07, 0.0], [0.30, 0.065, 0.0]]
        assert [fragment["h"] for fragment in note["native_display_data"]["texts"]] == [0.0035, 0.0035]
        assert [fragment["font"] for fragment in note["native_display_data"]["texts"]] == ["Arial", "Arial"]
        assert note["display_decoder_estimate"]["extent_m"] is not None
        assert "not printed glyph ink" in note["display_decoder_estimate"]["coordinate_basis"]


@pytest.mark.parametrize("accessor,field", [
    ("GetTextHeightAtIndex", "h"), ("GetTextFontAtIndex", "font"),
    ("GetTextLineSpacingAtIndex", "ls"),
])
def test_caption_probe_never_reports_reader_defaults_as_native_fields(bound, monkeypatch, accessor, field):
    note = _CaptionNote("E")
    setattr(note.data, accessor, lambda _index: None)
    adapter, view = _native_crop_fixture(monkeypatch, "E")
    view.Position = view.physical = (0.330, 0.084 + view.radius)
    view.notes = [note]
    logs, captures = [], []
    monkeypatch.setattr(drawing._telemetry, "info", logs.append)
    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", lambda *args, **kwargs: captures.append((args, kwargs)))
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: None)
    drawing._seat_detail_caption(adapter, view, _native_sheet(), label="E")
    assert captures == []  # A diagnostic refusal cannot fail a valid native box.
    report = json.loads(next(log for log in logs if "native diagnostics: " in log).split("native diagnostics: ", 1)[1])
    (entry,) = report["notes"]
    assert entry["native_display_read_errors"][accessor] > 0
    assert all(fragment[field] is None for fragment in entry["native_display_data"]["texts"])
    assert entry["display_decoder_estimate"]["extent_m"] is None


def test_both_caption_probes_precede_the_first_caption_guard_in_build():
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "build")
    calls = [node for node in ast.walk(build) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
    probes = [node for node in calls if node.func.id == "_record_detail_caption"]
    seats = [node for node in calls if node.func.id == "_seat_detail_caption"]
    assert len(probes) == len(seats) == 2
    assert [next(k.value.value for k in node.keywords if k.arg == "label") for node in probes] == ["D", "E"]
    assert max(node.lineno for node in probes) < min(node.lineno for node in seats)


@pytest.mark.parametrize("capture_fails", [False, True])
def test_caption_failure_retains_original_exception_and_captures_before_close(bound, monkeypatch, capture_fails):
    adapter, view = _native_crop_fixture(monkeypatch, "E")
    view.Position = view.physical = (0.330, 0.084 + view.radius)
    view.notes = [_CaptionNote("E")]
    original = RuntimeError("native extent refused")
    events, warnings = [], []
    def extent(*_args, **_kwargs):
        events.append("guard")
        raise original
    def capture(current_adapter, label, message, **context):
        events.append("capture")
        assert current_adapter is adapter
        assert label == "ch-rocker-arm-detail-E-caption"
        assert message == str(original) and context["exception"] is original
        assert context["sheet_png"] is True
        if capture_fails:
            raise OSError("forensic disk refused")
        raise original
    monkeypatch.setattr(drawing, "_note_extent", extent)
    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", capture)
    monkeypatch.setattr(drawing._telemetry, "warn", warnings.append)
    with pytest.raises(RuntimeError) as caught:
        try:
            drawing._seat_detail_caption(adapter, view, _native_sheet(), label="E")
        finally:
            events.append("seat-close")
    assert caught.value is original
    assert events == ["guard", "capture", "seat-close"]
    assert bool(warnings) is capture_fails
    if capture_fails:
        assert "secondary capture failure" in warnings[0]


def test_valid_caption_never_captures_failure(bound, monkeypatch):
    adapter, view = _native_crop_fixture(monkeypatch, "E")
    view.Position = view.physical = (0.330, 0.084 + view.radius)
    view.notes = [_CaptionNote("E")]
    captures = []
    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", lambda *args, **kwargs: captures.append((args, kwargs)))
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: None)
    drawing._seat_detail_caption(adapter, view, _native_sheet(), label="E")
    assert captures == []


def test_caption_probe_failures_are_explicit_and_cannot_replace_guard(bound, monkeypatch):
    note = _CaptionNote("E")
    note.GetText = lambda: None
    note.GetExtent = lambda: None
    note.annotation.GetDisplayData = lambda: None
    adapter, view = _native_crop_fixture(monkeypatch, "E")
    view.Position = view.physical = (0.330, 0.084 + view.radius)
    view.notes = [note]
    logs = []
    monkeypatch.setattr(drawing._telemetry, "info", logs.append)
    with pytest.raises(RuntimeError, match="detail E caption have no rendered extent"):
        drawing._seat_detail_caption(adapter, view, _native_sheet(), label="E")
    report = json.loads(next(log for log in logs if "native diagnostics: " in log).split("native diagnostics: ", 1)[1])
    assert {"GetText", "GetExtent", "GetDisplayData"} <= report["native_read_errors"].keys()
    (entry,) = report["notes"]
    assert entry["native_get_text"] is entry["native_note_get_extent"] is None
    assert entry["resolved_line_count"] is entry["display_fragment_count"] is None
    assert entry["display_decoder_estimate"]["extent_m"] is None


@pytest.mark.parametrize("top", [0.066, 0.070])
def test_end_caption_seats_actual_ink_between_crop_and_actual_title_rule(bound, monkeypatch, top):
    note = _FakeNote((0.30, 0.07), 0.007)
    note.PropertyLinkedText = "$PRPVIEW:DETAIL E SCALE"
    note.annotation.SetPosition2 = note.annotation.SetPosition
    adapter, view = _native_crop_fixture(monkeypatch, "E")
    view.Position = view.physical = (0.330, 0.084 + view.radius)
    view.notes = [note]
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: None)
    drawing._seat_detail_caption(adapter, view, _native_sheet(top=top), label="E")
    box = drawing._note_extent(adapter, note)
    assert box[3] <= 0.084 - 0.003
    assert box[1] >= top + 0.003
    assert (box[0] + box[2]) / 2 == pytest.approx(0.330)
    assert note.PropertyLinkedText == "$PRPVIEW:DETAIL E SCALE"


@pytest.mark.parametrize("label", ["D", "E"])
def test_native_caption_target_has_margin_for_r12_one_pixel_extents(bound, monkeypatch, label):
    # R12's last two GetExtent upper Y values differ by exactly this much;
    # the active display reported 2.098 px/mm. Fifty microns cannot settle it.
    pixel = 0.06535530434782608 - 0.06487873578595318
    assert pixel * 1000.0 == pytest.approx(1.0 / 2.098, abs=0.0001)
    assert drawing._DETAIL_CAPTION_TARGET_AIR_M == 0.004
    assert drawing._DETAIL_CAPTION_SETTLE_M >= pixel
    note = _FakeNote((0.16 if label == "D" else 0.30, 0.04), 0.007)
    note.PropertyLinkedText = f"$PRPVIEW:DETAIL {label} SCALE"
    note.annotation.SetPosition2 = note.annotation.SetPosition
    original_extent = note.GetExtent
    def quantized_extent():
        values = list(original_extent())
        values[3] = values[0] + 0.0324
        for index in (0, 1, 3, 4):
            values[index] = math.ceil(values[index] / pixel) * pixel
        return values
    note.GetExtent = quantized_extent
    adapter, view = _native_crop_fixture(monkeypatch, label)
    if label == "E":
        view.Position = view.physical = (0.330, 0.084 + view.radius)
    view.notes = [note]
    sheet = _native_sheet()
    sheet.GetZoneMargin = lambda _side: 0.0127
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: None)
    drawing._seat_detail_caption(adapter, view, sheet, label=label)
    box = drawing._note_extent(adapter, note)
    crop = drawing._detail_crop(adapter, view, label=label)
    assert crop[1] - box[3] >= 0.003
    floor = 0.0127 if label == "D" else 0.066
    assert box[1] - floor >= 0.003
    assert abs((box[0] + box[2] - crop[0] - crop[2]) / 2.0) <= pixel
    assert note.PropertyLinkedText == f"$PRPVIEW:DETAIL {label} SCALE"
    if label == "D":
        # The same causal native pixel grid rejects the old near-boundary
        # target / 50-micron convergence rule; do not fix it by weakening air.
        monkeypatch.setattr(drawing, "_DETAIL_CAPTION_TARGET_AIR_M", 0.00305)
        monkeypatch.setattr(drawing, "_DETAIL_CAPTION_SETTLE_M", 0.00005)
        with pytest.raises(RuntimeError, match="caption ink did not settle"):
            drawing._seat_detail_caption(adapter, view, sheet, label=label)


@pytest.mark.parametrize("defect", ["height", "title-rule", "scale", "missing", "multiple", "unlinked", "slot", "ignored-position", "refused-position", "nan", "missing-extent", "missing-position", "lost-links", "air"])
def test_end_caption_fails_closed_without_real_ink_and_three_mm_air(bound, monkeypatch, defect):
    note = _FakeNote((0.30, 0.07), 0.020 if defect == "height" else 0.007,
                     tracking=0.0 if defect == "ignored-position" else 1.0)
    note.PropertyLinkedText = "" if defect == "unlinked" else "$PRPVIEW:DETAIL E SCALE"
    note.annotation.SetPosition2 = note.annotation.SetPosition
    if defect == "nan":
        note.GetExtent = lambda: (float("nan"), 0.1, 0, 0.2, 0.11, 0)
    elif defect == "missing-extent":
        note.GetExtent = lambda: None
    elif defect == "missing-position":
        note.annotation.GetPosition = lambda: None
    elif defect == "refused-position":
        note.annotation.SetPosition2 = lambda *_args: False
    elif defect == "lost-links":
        def move_and_unlink(*args):
            result = note.annotation.SetPosition(*args)
            note.PropertyLinkedText = "lost link"
            return result
        note.annotation.SetPosition2 = move_and_unlink
    elif defect == "air":
        monkeypatch.setattr(drawing, "_DETAIL_CAPTION_TARGET_AIR_M", 0.0025)
    adapter, view = _native_crop_fixture(monkeypatch, "E")
    view.Position = view.physical = (0.330, 0.084 + view.radius)
    view.notes = [] if defect == "missing" else [note, note] if defect == "multiple" else [note]
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: None)
    captures = []
    def capture(current_adapter, _label, _message, **context):
        assert current_adapter is adapter and context["sheet_png"] is True
        captures.append(context["exception"])
        raise context["exception"]
    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", capture)
    with pytest.raises(RuntimeError) as caught:
        drawing._seat_detail_caption(
            adapter, view, _native_sheet(top=0.084 if defect == "slot" else 0.066, rule=defect != "title-rule", scale_retained=defect != "scale"), label="E",
        )
    assert captures == [caught.value]


@pytest.mark.parametrize("defect", [None, "missing", "duplicate", "wrong-owner"])
def test_actual_per_view_dimension_census_is_an_exact_marked_union(bound, monkeypatch, defect):
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, ann: ann)
    keeps = [drawing.FRONT_KEEP, drawing.HUB_KEEP, drawing.END_KEEP, drawing.RIGHT_KEEP]
    names = [list(keep) for keep in keeps]
    if defect == "missing":
        names[1].remove("PivotDia")
    elif defect == "duplicate":
        names[2].append("RodTipLen")
    elif defect == "wrong-owner":
        names[0].append(names[2].pop())
    views = [(str(i), SimpleNamespace(GetAnnotations=lambda row=row: row), keep)
             for i, (row, keep) in enumerate(zip(names, keeps))]
    if defect is None:
        drawing._require_dimension_census(object(), views)
    else:
        with pytest.raises(RuntimeError, match="native dimension owners"):
            drawing._require_dimension_census(object(), views)


@pytest.mark.parametrize("axis", ["X", "Y"])
@pytest.mark.parametrize("defect", [None, "wrong", "attachment", "uncentred", "basic", "text"])
def test_pin_coordinates_are_native_centred_basic_with_labels_after_boxing(monkeypatch, axis, defect):
    import _drawing_edge_dimensions
    adapter, _imported = _imported_native_quantities(monkeypatch)
    pivot, rod = object(), object()
    displays = {}
    monkeypatch.setattr(drawing, "_project", lambda *_a, **_k: [(0.18, 0.172), (0.246, 0.176)])
    monkeypatch.setattr(drawing, "visible_circle_edge", lambda _a, _v, diameter: pivot if diameter == drawing.PIVOT_HOLE_DIA else rod)
    monkeypatch.setattr(_drawing_edge_dimensions, "_is_same_attachment", lambda _a, actual, wanted, _kind: actual is wanted)
    def create(_adapter, _view, **kwargs):
        current_axis = "X" if kwargs["orientation"] == "horizontal" else "Y"
        mm = drawing.ROD_HOLE_X if current_axis == "X" else drawing.ROD_HOLE_Y - drawing.PIVOT_MID_Y
        display = _NativeQuantity(current_axis, mm)
        display.attached = (pivot, rod)
        display.arc_conditions = {1: 2, 2: 2}
        if current_axis == axis:
            if defect == "wrong":
                display.model.SystemValue += 0.0001
            elif defect == "attachment":
                display.attached = (pivot, object())
            elif defect == "uncentred":
                display.model.SetArcEndCondition = lambda *_a: 0
            elif defect == "basic":
                display.model.SetToleranceType = lambda _kind: True
            elif defect == "text":
                display.ignored_text = 4
        displays[current_axis] = display
        return display
    monkeypatch.setattr(drawing, "add_edge_dimension", create)
    if defect is None:
        drawing._add_pin_coordinates(adapter, object())
        for display in displays.values():
            assert display.arc_conditions == {1: 1, 2: 1}
            assert display.model.GetToleranceType() == 1
            assert display.text[4] == "PIN AXIS"
            assert display.writes[-2:] == [(4, ""), (4, "PIN AXIS")]
    else:
        with pytest.raises(RuntimeError):
            drawing._add_pin_coordinates(adapter, object())


@pytest.mark.parametrize("air,passes", [(0.001, True), (0.0009, False)])
def test_every_front_native_text_row_is_guarded_against_detail_crops(native_profile_clearance, bound, monkeypatch, air, passes):
    case = native_profile_clearance
    # Native records are historical detector inputs, not a current-coordinate proof.
    case.front.GetAnnotations = lambda: [case.r816]
    case.r816.data.texts = [{"t": "R816", "pos": [0.170, 0.128, 0], "h": 0.0035}]
    case.adapter, hub = _native_crop_fixture(monkeypatch, "D")
    hub.Position = hub.physical = (0.180, 0.128 - air - hub.radius)
    _adapter, end = _native_crop_fixture(monkeypatch, "E")
    if passes:
        drawing._require_front_detail_air(case.adapter, case.front, hub, end)
    else:
        with pytest.raises(RuntimeError, match="required_air_mm=1.000"):
            drawing._require_front_detail_air(case.adapter, case.front, hub, end)
    assert any("actual_air_mm=" in log for log in case.logs)


def test_native_profile_guard_diagnoses_actual_radius_leader_crossing(native_profile_clearance):
    case = native_profile_clearance
    case.r816.leaders = [[0.050, 0.143, 0, 0.080, 0.143, 0, 0.120, 0.143, 0]]
    with pytest.raises(RuntimeError, match="actual native leader crossing"):
        drawing._require_arc_profile_clearance(case.adapter, case.front, case.profiles)


@pytest.mark.parametrize("defect", [None, "activation", "missing-active", "wrong-active", "marks"])
def test_center_marks_activate_and_read_the_authoritative_native_view(bound, defect):
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "build")
    loops = [
        node for node in ast.walk(build) if isinstance(node, ast.For)
        and any(
            isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
            and call.func.id == "auto_center_marks" for call in ast.walk(node)
        )
    ]
    assert len(loops) == 1
    # Execute the actual local document binding, not a test-injected global:
    # otherwise a missing binding in build() passes this native-call fake.
    bindings = [
        node for node in ast.walk(build) if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "drawing" for target in node.targets)
        and node.lineno < loops[0].lineno
    ]
    assert len(bindings) == 1
    code = compile(
        ast.fix_missing_locations(ast.Module(body=[*bindings, *loops], type_ignores=[])),
        drawing.__file__, "exec",
    )
    views = tuple(object() for _ in range(3))
    names = dict(zip(views, ("front", "D", "E")))
    events = []

    class NativeDrawing:
        __slots__ = ("active",)

        def __init__(self):
            self.active = None

        def ActivateView(self, name):
            events.append(("activate", name))
            if defect == "activation":
                return False
            self.active = next(view for view in views if names[view] == name)
            return True

        @property
        def ActiveDrawingView(self):
            events.append(("active", self.active))
            if defect == "missing-active":
                return None
            return object() if defect == "wrong-active" else self.active

        @property
        def IActiveDrawingView(self):
            pytest.fail("center marks must use the documented Automation ActiveDrawingView")

    native = NativeDrawing()

    def same(actual, expected):
        assert actual is not None and expected is not None
        events.append(("same", actual, expected))
        return 1 if actual is expected else 0

    adapter = SimpleNamespace(currentModel=native, swApp=SimpleNamespace(IsSame=same))

    def marks(actual_adapter, view, *, holes, size):
        assert actual_adapter is adapter
        assert view is native.active and holes is True and size == 0.0025
        events.append(("marks", view))
        return defect != "marks"

    namespace = dict(
        adapter=adapter, front=views[0], hub=views[1], end=views[2],
        _early_bound=drawing._early_bound, view_name=lambda _adapter, view: names[view],
        auto_center_marks=marks,
    )
    if defect is None:
        exec(code, namespace)
        assert [event[0] for event in events] == ["activate", "active", "same", "marks"] * 3
        assert [event[1] for event in events if event[0] == "marks"] == list(views)
    else:
        with pytest.raises(RuntimeError):
            exec(code, namespace)
        assert len([event for event in events if event[0] == "marks"]) == (1 if defect == "marks" else 0)


def test_land_vertical_early_binds_view_and_refuses_null_native_sketch(monkeypatch):
    raw_view = object()
    native_view = SimpleNamespace(GetSketch=lambda: None)
    bindings = []
    def bind(obj, interface):
        bindings.append((obj, interface))
        return native_view if obj is raw_view and interface == "IView" else obj
    def name(_adapter, view):
        assert view is native_view
        return "E"
    draw = SimpleNamespace(ActivateView=lambda _name: True, ClearSelection2=lambda _all: None)
    monkeypatch.setattr(drawing, "_early_bound", bind)
    monkeypatch.setattr(drawing, "view_name", name)
    with pytest.raises(RuntimeError, match="land-angle detail has no native drawing sketch"):
        drawing._land_vertical(SimpleNamespace(currentModel=draw), raw_view, [])
    assert (raw_view, "IView") in bindings


def test_details_keep_native_scale_source_census_and_unclipped_overall_contract():
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    definitions = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    build_calls = [node for node in ast.walk(definitions["build"])
                   if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
    details = [node for node in build_calls if node.func.id == "_create_detail"]
    assert len(details) == 2
    assert [next(ast.unparse(k.value) for k in node.keywords if k.arg == "scale")
            for node in details] == ["HUB_SCALE", "END_SCALE"]
    assert drawing.HUB_SCALE == (4.0, 1.0) and drawing.END_SCALE == (2.0, 1.0)
    assert "create_detail_view" not in Path(drawing.__file__).read_text(encoding="utf-8")
    for required in ("_place_detail_letters", "_require_dimension_census", "_require_front_detail_air", "_require_radius_exterior"):
        assert sum(node.func.id == required for node in build_calls) == 1
    outline = ast.unparse(definitions["_add_rocker_outline_dimensions"])
    assert "MaxWitnessLineLength" not in outline
    assert not hasattr(drawing, "OVERALL_WITNESS_LENGTH")
    assert not hasattr(drawing, "PIVOT_PICK_ZOOM_HALF")
    assert set(drawing.FRONT_KEEP) == drawing.BASIC_PROFILE_DIMENSIONS
    assert not hasattr(drawing, "_sheet_xy")
    crop_calls = {"_seat_detail_caption": 1, "_require_ream_clearance": 1, "_require_front_detail_air": 2}
    for name, count in crop_calls.items():
        calls = [node for node in ast.walk(definitions[name]) if isinstance(node, ast.Call)]
        assert sum(isinstance(node.func, ast.Name) and node.func.id == "_detail_crop" for node in calls) == count
        assert not any(isinstance(node.func, ast.Attribute) and node.func.attr == "GetOutline" for node in calls)
    crop_attributes = {node.attr for node in ast.walk(definitions["_detail_crop"]) if isinstance(node, ast.Attribute)}
    build_attributes = {node.attr for node in ast.walk(definitions["build"]) if isinstance(node, ast.Attribute)}
    assert "GetText" not in build_attributes  # Hole callouts cannot use resolved text compartments.
    assert sum(node.func.id == "_require_rod_through_callout" for node in build_calls) == 1
    through_attributes = {node.attr for node in ast.walk(definitions["_require_rod_through_callout"]) if isinstance(node, ast.Attribute)}
    assert {"GetDisplayData", "GetTextCount", "GetTextAtIndex"} <= through_attributes
    assert "GetText" not in through_attributes
    assert {"GetDetail", "GetProfileItems", "Inverse", "ArrayData"} <= crop_attributes
    assert "IInverse" not in crop_attributes  # Generated presence does not prove IDispatch support.
    assert "ModelToViewTransform" not in crop_attributes  # Inverse sketch mapping already returns sheet.
    circle_attributes = {node.attr for node in ast.walk(definitions["_native_circle_geometry"]) if isinstance(node, ast.Attribute)}
    assert {"GetType", "GetRadius", "GetCenterPoint2", "IsCircle"} <= circle_attributes


def test_datum_landing_refuses_null_native_annotation(monkeypatch):
    import _drawing_gdt

    monkeypatch.setattr(_drawing_gdt, "_early_bound", lambda obj, *_: obj)
    tag = SimpleNamespace(GetAnnotation=lambda: None)
    with pytest.raises(RuntimeError, match="datum landing has no annotation.*rod-side radial land"):
        _drawing_gdt.assert_datum_landing(
            object(), tag, expected_xy=(0.21, 0.167), label="rod-side radial land",
        )


def test_land_angle_refuses_null_native_annotation(native_front):
    state = native_front
    state.defect_label = "radial land angle to mirror axis"
    state.defect = "null-annotation"
    with pytest.raises(RuntimeError, match="land angle has no native annotation"):
        drawing._add_land_angle(state.adapter, object(), state.land)


@pytest.mark.parametrize("missing_index", [0, 1])
def test_land_angle_refuses_null_native_attachment_before_identity_dispatch(native_front, monkeypatch, missing_index):
    state = native_front
    state.defect_label = "radial land angle to mirror axis"
    state.defect = "null-attachment"
    original_create = drawing.add_edge_dimension
    def create(*args, **kwargs):
        display = original_create(*args, **kwargs)
        attachments = list(kwargs["entities"])
        attachments[missing_index] = None
        display.attached = tuple(attachments)
        return display
    def same(actual, expected):
        if actual is None:
            pytest.fail("IsSame cannot receive a NULL native attachment")
        return 1 if actual is expected else 0
    monkeypatch.setattr(drawing, "add_edge_dimension", create)
    state.adapter.swApp = SimpleNamespace(IsSame=same)
    with pytest.raises(RuntimeError, match="exact land and local vertical"):
        drawing._add_land_angle(state.adapter, object(), state.land)


class _RenderedRodText:
    __slots__ = ("texts", "count", "reads")

    def __init__(self, texts):
        self.texts, self.count, self.reads = texts, len(texts), []

    def GetTextCount(self):
        return self.count

    def GetTextAtIndex(self, index):
        self.reads.append(index)
        return self.texts[index]


class _RenderedRodCallout:
    __slots__ = ("data",)

    def __init__(self, texts):
        self.data = _RenderedRodText(texts)

    def GetDisplayData(self):
        return self.data

    def GetText(self, _part):
        raise AssertionError("Hole callouts do not support GetText resolved compartments")


@pytest.mark.parametrize("texts", [
    ("#47 DRILL", "native diameter", "THRU"), ("#47 DRILL", "native diameter thru"), ("", "THRU"),
])
def test_rod_through_condition_reads_actual_rendered_callout_items(bound, texts):
    callout = _RenderedRodCallout(texts)
    drawing._require_rod_through_callout(callout)
    assert callout.data.reads == list(range(len(texts)))
    with pytest.raises(AssertionError, match="do not support GetText"):
        callout.GetText(1)


@pytest.mark.parametrize("defect", [
    "missing-data", "empty", "missing-count", "negative-count", "bool-count", "method-count",
    "missing-item", "method-item", "no-thru",
])
def test_rod_through_condition_cannot_pass_unreadable_or_non_through_native_ink(bound, defect):
    callout = _RenderedRodCallout(("#47 DRILL", "THRU"))
    if defect == "missing-data":
        callout.data = None
    elif defect == "empty":
        callout.data.count = 0
    elif defect == "missing-count":
        callout.data.count = None
    elif defect == "negative-count":
        callout.data.count = -1
    elif defect == "bool-count":
        callout.data.count = True
    elif defect == "method-count":
        callout.data.count = lambda: 2
    elif defect == "missing-item":
        callout.data.texts = ("#47 DRILL", None)
    elif defect == "method-item":
        callout.data.texts = ("#47 DRILL", lambda: "THRU")
    elif defect == "no-thru":
        callout.data.texts = ("#47 DRILL", "native diameter", "DEPTH")
        callout.data.count = len(callout.data.texts)
    with pytest.raises(RuntimeError):
        drawing._require_rod_through_callout(callout)


@pytest.mark.parametrize("defect", ["basic", "text"])
def test_end_clocking_refuses_lost_basicness_or_unretained_direction(native_front, defect):
    native_front.defect_label = "radial land angle to mirror axis"
    native_front.defect = defect
    with pytest.raises(RuntimeError):
        drawing._add_land_angle(native_front.adapter, object(), native_front.land)


def test_d_caption_uses_left_of_title_block_space_not_global_title_top(bound, monkeypatch):
    note = _FakeNote((0.16, 0.04), 0.007)
    note.PropertyLinkedText = "$PRPVIEW:DETAIL D SCALE"
    note.annotation.SetPosition2 = note.annotation.SetPosition
    original_extent = note.GetExtent
    def narrow_caption():
        values = list(original_extent())
        values[3] = values[0] + 0.035
        return values
    note.GetExtent = narrow_caption
    adapter, view = _native_crop_fixture(monkeypatch, "D")
    view.notes = [note]
    sheet = _native_sheet()
    sheet.GetZoneMargin = lambda _side: 0.0127
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: None)
    drawing._seat_detail_caption(adapter, view, sheet, label="D")
    box = drawing._note_extent(adapter, note)
    assert box[3] < 0.066
    assert box[2] < drawing.DRAWING_TEMPLATES[drawing.SPEC.layout].title_block_left_m - 0.003
    assert box[1] >= 0.0127 + 0.003


@pytest.mark.parametrize("defect", [None, "crop", "notes", "missing", "invalid-text"])
def test_ream_native_text_clears_actual_detail_and_seated_notes(native_profile_clearance, bound, monkeypatch, defect):
    case = native_profile_clearance
    case.ream.data.texts = [{"t": "REAM +0.03", "pos": [0.094, 0.082, 0], "h": 0.0036}]
    case.ream.position = (0.120, 0.086, 0)
    if defect == "invalid-text":
        case.ream.data.texts[0]["h"] = 0.0
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, ann: "PivotDia")
    case.adapter, hub = _native_crop_fixture(monkeypatch, "D")
    if defect == "crop":
        hub.Position = hub.physical = (0.110 + hub.radius, drawing.HUB_CENTER[1])
    hub.annotations = [] if defect == "missing" else [case.ream]
    notes = (0.020, 0.016, 0.150, 0.082 if defect == "notes" else 0.070)
    if defect is None:
        drawing._require_ream_clearance(case.adapter, hub, notes)
        assert any("required_air_mm=1.000" in log for log in case.logs)
    else:
        with pytest.raises((RuntimeError, ValueError)):
            drawing._require_ream_clearance(case.adapter, hub, notes)


@pytest.mark.parametrize("defect", ["empty-view", "invalid-crop", "invalid-text"])
def test_front_detail_text_guard_cannot_pass_missing_native_geometry(native_profile_clearance, bound, monkeypatch, defect):
    case = native_profile_clearance
    case.front.GetAnnotations = lambda: [] if defect == "empty-view" else [case.r816]
    if defect == "invalid-text":
        case.r816.data.texts[0]["pos"][1] = float("nan")
    case.adapter, hub = _native_crop_fixture(monkeypatch, "D", defect="invalid-bbox" if defect == "invalid-crop" else None)
    _adapter, end = _native_crop_fixture(monkeypatch, "E")
    with pytest.raises((RuntimeError, ValueError)):
        drawing._require_front_detail_air(case.adapter, case.front, hub, end)


@pytest.mark.parametrize("points", [[], [(0.18,)], [(0.18, float("nan"))], [(0.18, float("inf"))]])
def test_native_projection_fails_closed_on_missing_or_invalid_coordinates(bound, monkeypatch, points):
    events = []
    view = SimpleNamespace(UpdateViewDisplayGeometry=lambda: events.append("barrier"))
    monkeypatch.setattr(drawing, "model_points_in_view", lambda *_a, **_k: points)
    with pytest.raises(RuntimeError, match="invalid native projected points"):
        drawing._project(object(), view, [(0.0, 0.008, 0.0)], label="detail D pivot")
    assert events == ["barrier"]


@pytest.mark.parametrize("defect", [None, "inside-circle", "missing-radius", "zero-projection", "invalid-position"])
def test_basic_radius_ink_uses_native_parent_circle_projection(native_profile_clearance, bound, monkeypatch, defect):
    case = native_profile_clearance
    annotations = []
    for name in ("TopRadius", "BottomRadius"):
        xy = drawing.FRONT_KEEP[name]
        text = _ClearanceDisplayData([{"t": "R800" if name == "TopRadius" else "R816",
                                      "pos": [*xy, 0.0], "h": 0.0035}], [])
        annotations.append(_ClearanceAnnotation(name, (*xy, 0.0), text, kind=4, hole_callout=False))
    if defect == "inside-circle":
        annotations[0].data.texts[0]["pos"][:2] = [0.130, 0.218]
    elif defect == "missing-radius":
        annotations.pop(0)
    elif defect == "invalid-position":
        annotations[0].position = (float("nan"), 0.136, 0.0)
    case.front.GetAnnotations = lambda: annotations
    events = []
    case.front.UpdateViewDisplayGeometry = lambda: events.append("barrier")
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, ann: ann.name)
    def native_project(_adapter, _view, points, **_kwargs):
        assert events == ["barrier"]
        return [_front_xy(0.0 if defect == "zero-projection" else x * 1000.0, y * 1000.0)
                for x, y, _z in points]
    monkeypatch.setattr(drawing, "model_points_in_view", native_project)
    if defect is None:
        drawing._require_radius_exterior(case.adapter, case.front)
        logs = "\n".join(case.logs)
        assert "native_circle_radius_mm=400.000" in logs
        assert "native_circle_radius_mm=408.000" in logs
        assert logs.count("actual_exterior_air_mm=") == 2
    else:
        with pytest.raises((RuntimeError, ValueError)):
            drawing._require_radius_exterior(case.adapter, case.front)


@pytest.mark.parametrize("properties", [None, (), (0.0, 0.0, 1.0)])
def test_sheet_scale_cannot_claim_success_without_native_properties(bound, properties):
    sheet = SimpleNamespace(SetScale=lambda *_args: True, GetProperties2=lambda: properties)
    with pytest.raises(RuntimeError, match="sheet scale did not persist"):
        drawing._pin_sheet_scale(object(), sheet)


class _StyleTextFormat:
    """Native get/put properties; CharHeight switches authority to metres."""

    def __init__(self, height=0.00635, *, points=False):
        self._height, self.points = height, points

    CharHeight = property(
        lambda self: self._height,
        lambda self, value: (setattr(self, "_height", value), setattr(self, "points", False)),
    )
    CharHeightInPts = property(lambda self: 24)
    TypeFaceName = property(lambda self: "Arial")

    def IsHeightSpecifiedInPts(self):
        return self.points


class _StyleNote(_CaptionNote):
    """Two-step rich text, method-shaped format calls, linked native fields."""

    def __init__(self, label, *, ordinary_height=None):
        super().__init__(label, height=0.0166799)
        self.rich = ordinary_height is None
        self.use_doc = True
        self.font_height = 0.00635  # inherited format, NOT actual normal-note ink
        self.writes, self.events = [], []
        self.reset_result = self.write_result = True
        self.on_write = lambda: None
        self.readback_delta = 0.0
        self._linked = (
            "<VLNAME> <FONT size=3.5><VLLABEL>\r\n"
            "<VLSCALE><FONT size=6.35> <FONT size=3.5><VLSCALEV><FONT size=6.35>"
            if self.rich else '$PRPSHEET:"Manufacturing Notes"'
        )
        runs = [
            ("DETAIL ", 0.00635), (label + "\r\n", 0.0035),
            ("SCALE", 0.0035), (" ", 0.00635),
            ("4:1" if label == "D" else "2:1", 0.0035),
        ] if self.rich else [("1. TURN HUB\r\n", ordinary_height), ("2. REAM BORE", ordinary_height)]
        self.data = _ClearanceDisplayData([
            {"t": text, "h": height, "pos": [0.30, 0.07, 0.0]}
            for text, height in runs
        ], [])
        self.annotation.GetDisplayData = lambda: self.data
        self.annotation.GetTextFormat = self.get_format
        self.annotation.GetUseDocTextFormat = lambda _index: self.use_doc
        self.annotation.SetTextFormat = self.set_format

    HasMultipleFonts = property(lambda self: self.rich)

    def GetText(self):
        return " \r\n "  # Not resolved native view-field glyphs.

    def get_format(self, index):
        assert index == 0
        self.events.append("get-format")
        return _StyleTextFormat(self.font_height)

    def set_format(self, index, use_doc, text_format):
        assert index == 0
        self.writes.append((index, use_doc, None if text_format is None else text_format.CharHeight))
        self.events.append("reset" if use_doc else "local")
        result = self.reset_result if use_doc else self.write_result
        if result is not True:
            return result
        if use_doc:
            assert text_format is None
            self.rich, self.use_doc = False, True
            self._linked = re.sub(r"<FONT[^>]*>", "", self._linked)
        else:
            if self.rich:
                return False  # Official specific-format refusal for inline fonts.
            self.font_height, self.use_doc = text_format.CharHeight, False
            for fragment in self.data.texts:
                fragment["h"] = self.font_height + self.readback_delta
            self.height = self.font_height * 2.0
            self.on_write()
        return True


class _StyleCircle(_DetailCircle):
    """Local native circle formatting; a refused setter leaves format unmoved."""

    def __init__(self, label, front, view):
        super().__init__(label)
        self.xy = drawing.DETAIL_LETTER_XY[label]
        self.front, self.view = front, view
        self.font_height, self.use_doc, self.points = 0.00635, True, True
        self.result = True
        self.delta = self.display_delta = 0.0
        self.writes = []
        self.on_write = lambda: None

    def GetView(self):
        return self.front

    def GetDetailView(self):
        return self.view

    def GetTextFormat(self):
        return _StyleTextFormat(self.font_height, points=self.points)

    def GetUseDocTextFormat(self):
        return self.use_doc

    def SetTextFormat(self, use_doc, text_format):
        self.writes.append((use_doc, text_format.CharHeight))
        if self.result is True:
            self.font_height = text_format.CharHeight + self.delta
            self.use_doc, self.points = use_doc, text_format.IsHeightSpecifiedInPts()
            self.on_write()
        return self.result


@pytest.fixture
def native_caption_style(bound, monkeypatch):
    import _drawing_notes

    monkeypatch.setattr(_drawing_notes, "_early_bound", lambda obj, _interface: obj)
    front = SimpleNamespace()
    notes = {label: _StyleNote(label) for label in ("D", "E")}
    views = {
        label: SimpleNamespace(
            GetNotes=lambda label=label: [notes[label]], GetBaseView=lambda: front,
            Position=drawing.HUB_CENTER if label == "D" else drawing.END_CENTER,
            ScaleRatio=drawing.HUB_SCALE if label == "D" else drawing.END_SCALE,
            UseParentScale=False, UseSheetScale=0,
        ) for label in ("D", "E")
    }
    circles = {label: _StyleCircle(label, front, views[label]) for label in ("D", "E")}
    front.GetDetailCircles = lambda: [circles["E"], circles["D"]]

    def circle_info():
        # Deliberately different from GetDetailCircles enumeration. Position,
        # not unverified array order, binds the independent displayed height.
        values = [2.0]
        for label in ("D", "E"):
            circle = circles[label]
            values.extend([
                0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                *circle.xy, 0, circle.font_height + circle.display_delta, 0,
            ])
        return tuple(values)

    front.GetDetailCircleInfo2 = circle_info
    events, captures = [], []
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(GraphicsRedraw2=lambda: events.append("redraw")),
        swApp=_APP,
    )
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_args, **_kwargs: events.append("rebuild"))
    monkeypatch.setattr(
        drawing._seat_forensics, "capture_com_failure",
        lambda *_args, **context: captures.append(context["exception"]),
    )
    return SimpleNamespace(
        adapter=adapter, front=front, notes=notes, views=views, circles=circles,
        source=_StyleNote("source", ordinary_height=0.0035), events=events, captures=captures,
    )


def _normalize_style(case):
    drawing._normalize_detail_caption_styles(
        case.adapter, case.front, case.views["D"], case.views["E"], case.source,
    )


@pytest.mark.parametrize("height", [0.0035, 0.0042])
def test_normal_note_native_fragments_drive_both_captions_and_source_circle_fonts(native_caption_style, height):
    case = native_caption_style
    for fragment in case.source.data.texts:
        fragment["h"] = height
    _normalize_style(case)
    assert case.source.font_height == 0.00635  # Never adopt inherited source format.
    assert case.source.writes == []
    for label in ("D", "E"):
        note, circle, view = case.notes[label], case.circles[label], case.views[label]
        assert note.writes == [(0, True, None), (0, False, height)]
        assert note.events == ["reset", "get-format", "local"]
        assert re.findall(r"<VL[^>]*>", note.PropertyLinkedText) == list(drawing._CAPTION_FIELDS)
        assert "<FONT" not in note.PropertyLinkedText
        assert [fragment["h"] for fragment in note.data.texts] == [height] * 5
        assert circle.writes == [(False, height)]
        assert circle.GetLabel() == label and circle.xy == drawing.DETAIL_LETTER_XY[label]
        assert circle.font_height == height and circle.GetUseDocTextFormat() is False
        assert view.Position == (drawing.HUB_CENTER if label == "D" else drawing.END_CENTER)
    assert case.events.count("rebuild") == 4 and case.events.count("redraw") == 5
    assert case.captures == []


@pytest.mark.parametrize("char_height", [None, 0.0041])
def test_ordinary_linked_note_factory_keeps_no_height_and_single_write_paths(native_caption_style, monkeypatch, char_height):
    import _drawing_notes

    note = _StyleNote("ordinary", ordinary_height=0.0035)
    calls = []
    def add_note(adapter, text, x, y):
        calls.append((adapter, text, x, y))
        return note
    monkeypatch.setattr(_drawing_notes, "add_note", add_note)
    returned = _drawing_notes.add_property_linked_note(
        native_caption_style.adapter, "Manufacturing Notes", 0.02, 0.08, char_height=char_height,
    )
    assert returned is note
    assert calls == [(native_caption_style.adapter, '$PRPSHEET:"Manufacturing Notes"', 0.02, 0.08)]
    assert note.PropertyLinkedText == '$PRPSHEET:"Manufacturing Notes"'
    assert note.writes == ([] if char_height is None else [(0, False, char_height)])
    assert "reset" not in note.events


@pytest.mark.parametrize("defect", [
    "missing-display", "missing-annotation", "no-fragments", "blank-text", "mixed-height",
    "mixed-font", "zero", "nan", "infinite", "missing-height", "missing-font", "bad-count",
])
def test_unavailable_mixed_or_invalid_normal_note_height_is_fatal_and_captured(native_caption_style, defect):
    case = native_caption_style
    source = case.source
    if defect == "missing-display":
        source.annotation.GetDisplayData = lambda: None
    elif defect == "missing-annotation":
        source.GetAnnotation = lambda: None
    elif defect == "no-fragments":
        source.data.texts.clear()
    elif defect == "blank-text":
        for fragment in source.data.texts:
            fragment["t"] = " \r\n "
    elif defect == "mixed-height":
        source.data.texts[-1]["h"] = 0.00635
    elif defect == "mixed-font":
        source.data.GetTextFontAtIndex = lambda index: "Arial" if index == 0 else "Century Gothic"
    elif defect == "missing-font":
        source.data.GetTextFontAtIndex = lambda _index: None
    elif defect == "bad-count":
        source.data.GetTextCount = lambda: True
    else:
        source.data.texts[0]["h"] = {
            "zero": 0.0, "nan": float("nan"), "infinite": float("inf"), "missing-height": None,
        }[defect]
    with pytest.raises(RuntimeError) as caught:
        _normalize_style(case)
    assert case.captures == [caught.value]
    assert all(note.writes == [] for note in case.notes.values())


@pytest.mark.parametrize("target", ["reset", "caption", "circle"])
@pytest.mark.parametrize("result", [False, None, 1, "true"])
def test_native_font_setters_require_actual_true(native_caption_style, target, result):
    case = native_caption_style
    if target == "reset":
        case.notes["D"].reset_result = result
    elif target == "caption":
        case.notes["D"].write_result = result
    else:
        case.circles["D"].result = result
    with pytest.raises(RuntimeError, match="reset|text height|setter refused") as caught:
        _normalize_style(case)
    assert case.captures == [caught.value]


@pytest.mark.parametrize("defect", [
    "drop-name", "drop-label", "drop-scale", "drop-ratio", "reorder", "duplicate",
    "stale-height", "missing-fragment", "multiple-fonts", "mixed-font",
    "lost-owner", "moved-view", "scale-changed", "replaced-note",
])
def test_caption_reset_rejects_lost_fields_heights_fragments_and_native_ownership(native_caption_style, defect):
    case = native_caption_style
    note, view = case.notes["D"], case.views["D"]
    def mutate():
        if defect.startswith("drop-"):
            field = {
                "drop-name": "<VLNAME>", "drop-label": "<VLLABEL>",
                "drop-scale": "<VLSCALE>", "drop-ratio": "<VLSCALEV>",
            }[defect]
            note._linked = note._linked.replace(field, "")
        elif defect == "reorder":
            note._linked = "<VLLABEL><VLNAME><VLSCALE><VLSCALEV>"
        elif defect == "duplicate":
            note._linked += "<VLLABEL>"
        elif defect == "stale-height":
            note.data.texts[0]["h"] = 0.00635
        elif defect == "missing-fragment":
            note.data.texts.pop(1)
        elif defect == "multiple-fonts":
            note.rich = True
        elif defect == "mixed-font":
            note.data.GetTextFontAtIndex = lambda index: "Arial" if index == 0 else "Century Gothic"
        elif defect == "lost-owner":
            view.GetBaseView = lambda: object()
        elif defect == "moved-view":
            view.Position = (0.0, 0.0)
        elif defect == "scale-changed":
            view.ScaleRatio = (1.0, 1.0)
        elif defect == "replaced-note":
            view.GetNotes = lambda: [object()]
    note.on_write = mutate
    with pytest.raises(RuntimeError) as caught:
        _normalize_style(case)
    assert case.captures == [caught.value]


@pytest.mark.parametrize("label", ["D", "E"])
@pytest.mark.parametrize("defect", [
    "format-height", "display-height", "label", "position", "owner", "detail-owner",
    "doc-authority", "point-authority", "missing-info", "truncated-info", "invalid-info",
])
def test_source_circle_readbacks_are_independent_and_preserve_native_identity(native_caption_style, label, defect):
    case = native_caption_style
    circle = case.circles[label]
    if defect == "format-height":
        circle.delta = 0.001
    elif defect == "display-height":
        circle.display_delta = 0.001
    elif defect in {"missing-info", "truncated-info", "invalid-info"}:
        original = case.front.GetDetailCircleInfo2
        refused_info = (
            (lambda: None) if defect == "missing-info" else
            (lambda: original()[:-1]) if defect == "truncated-info" else
            (lambda: (float("nan"), *original()[1:]))
        )
        circle.on_write = lambda: setattr(case.front, "GetDetailCircleInfo2", refused_info)
    else:
        def mutate():
            if defect == "label":
                circle.label = "X"
            elif defect == "position":
                circle.xy = (0.0, 0.0)
            elif defect == "owner":
                circle.front = object()
            elif defect == "detail-owner":
                circle.view = object()
            elif defect == "doc-authority":
                circle.use_doc = True
            elif defect == "point-authority":
                circle.points = True
        circle.on_write = mutate
    with pytest.raises(RuntimeError) as caught:
        _normalize_style(case)
    assert case.captures == [caught.value]


@pytest.mark.parametrize("delta", [0.0, 0.00000005, 0.0002])
def test_native_font_quantization_is_small_not_a_pixel_or_point_fallback(native_caption_style, delta):
    case = native_caption_style
    for note in case.notes.values():
        note.readback_delta = delta
    for circle in case.circles.values():
        circle.delta = circle.display_delta = delta / 2
    if delta > drawing._NOTE_HEIGHT_READBACK_TOL_M:
        with pytest.raises(RuntimeError, match="readback mismatch"):
            _normalize_style(case)
    else:
        _normalize_style(case)
        assert case.captures == []


@pytest.mark.parametrize("phase", ["source", "caption", "circle"])
@pytest.mark.parametrize("capture_fails", [False, True])
def test_style_refusals_preserve_original_exception_and_forensics_before_seat_close(native_caption_style, monkeypatch, phase, capture_fails):
    case = native_caption_style
    events, warnings = [], []
    original = RuntimeError("native style read refused")
    def refuse(*_args, **_kwargs):
        events.append("refusal")
        raise original
    if phase == "source":
        case.source.annotation.GetDisplayData = refuse
    elif phase == "caption":
        case.notes["D"].annotation.SetTextFormat = refuse
    else:
        case.circles["D"].GetTextFormat = refuse
    def capture(adapter, _label, message, **context):
        events.append("capture")
        assert adapter is case.adapter and message == str(original)
        assert context["exception"] is original and context["sheet_png"] is True
        if capture_fails:
            raise OSError("disk refused")
        raise original
    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", capture)
    monkeypatch.setattr(drawing._telemetry, "warn", warnings.append)
    with pytest.raises(RuntimeError) as caught:
        try:
            _normalize_style(case)
        finally:
            events.append("seat-close")
    assert caught.value is original
    assert events == ["refusal", "capture", "seat-close"]
    assert bool(warnings) is capture_fails


def test_style_normalization_precedes_settled_link_capture_and_both_final_probes():
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "build")
    calls = [node for node in ast.walk(build) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
    (normalize,) = [node for node in calls if node.func.id == "_normalize_detail_caption_styles"]
    (letters,) = [node for node in calls if node.func.id == "_place_detail_letters"]
    probes = [node for node in calls if node.func.id == "_record_detail_caption"]
    seats = [node for node in calls if node.func.id == "_seat_detail_caption"]
    assert tuple(ast.unparse(arg) for arg in normalize.args) == ("adapter", "front", "hub", "end", "notes")
    assert letters.lineno < normalize.lineno < min(node.lineno for node in probes)
    assert max(node.lineno for node in probes) < min(node.lineno for node in seats)
    seat = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_seat_detail_caption")
    assert "note.PropertyLinkedText != linked" in ast.unparse(seat)
    assert drawing.END_CENTER[1] == 0.110
    assert drawing._DETAIL_CAPTION_TARGET_AIR_M == 0.004
    assert "crop[1] - 0.003" in ast.unparse(seat)
    assert "lower_boundary + 0.003" in ast.unparse(seat)


def test_native_rich_reset_may_merge_runs_without_detaching_fields(native_caption_style):
    case = native_caption_style
    for note in case.notes.values():
        def merge(note=note):
            text = "".join(fragment["t"] for fragment in note.data.texts)
            note.data.texts[:] = [{"t": text, "h": note.font_height, "pos": [0.30, 0.07, 0.0]}]
        note.on_write = merge
    _normalize_style(case)
    assert all(len(note.data.texts) == 1 for note in case.notes.values())
    assert all(drawing._caption_fields(note, label=label) == drawing._CAPTION_FIELDS
               for label, note in case.notes.items())


@pytest.mark.parametrize("label", ["D", "E"])
def test_dropped_fields_during_rebuild_are_fatal_before_seat_close(native_caption_style, monkeypatch, label):
    case = native_caption_style
    note = case.notes[label]
    def rebuild(_adapter, *, label: str):
        if label == f"normalize detail {note.label} caption font":
            note._linked = note._linked.replace("<VLSCALEV>", "")
    monkeypatch.setattr(drawing, "rebuild_drawing", rebuild)
    with pytest.raises(RuntimeError, match="field identities/order/counts") as caught:
        _normalize_style(case)
    assert case.captures == [caught.value]


@pytest.mark.parametrize("label", ["D", "E"])
def test_source_height_normalization_then_quantized_native_caption_seating_keeps_air(native_caption_style, monkeypatch, label):
    case = native_caption_style
    _normalize_style(case)
    note = case.notes[label]
    pixel = 0.06535530434782608 - 0.06487873578595318
    original_extent = note.GetExtent
    def quantized_extent():
        values = list(original_extent())
        for index in (0, 1, 3, 4):
            values[index] = round(values[index] / pixel) * pixel
        return tuple(values)
    note.GetExtent = quantized_extent
    crop = (0.14, 0.070, 0.22, 0.150) if label == "D" else (0.29, 0.084, 0.37, 0.164)
    monkeypatch.setattr(drawing, "_detail_crop", lambda *_args, **_kwargs: crop)
    sheet = _native_sheet()
    sheet.GetZoneMargin = lambda _index: BORDER_BOTTOM
    linked = note.PropertyLinkedText
    drawing._seat_detail_caption(case.adapter, case.views[label], sheet, label=label)
    box = drawing._note_extent(case.adapter, note)
    assert note.PropertyLinkedText == linked
    assert crop[1] - box[3] >= 0.003
    assert box[1] - (BORDER_BOTTOM if label == "D" else 0.066) >= 0.003
    assert case.views["E"].Position[1] == 0.110
    assert case.captures == []
