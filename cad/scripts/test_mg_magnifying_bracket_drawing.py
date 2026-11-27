"""Offline manufactured-interval and native-print contracts for the L bracket."""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

import build_mg_magnifying_bracket as part
import draw_mg_magnifying_bracket as drawing
import magnifying_bracket_joint_layout as mounting
import mg_lever_thread_joint as joint
import mg_magnifying_bracket_spec as spec
from _drawing_edges import ViewEdge, ViewEdges
from _layout_geometry import DrawableRegion, Segment, segment_box_overlap_length
from _inch_wall_limits import WALL_TARGET_MM
from _printed_tolerance import printed_band_mm


def test_foot_joins_flush_without_changing_mounting_grip_or_pattern() -> None:
    assert part.FLANGE_X[1] == joint.NECK_THICKNESS / 2.0
    assert part.FLANGE_X[0] < -joint.NECK_THICKNESS / 2.0
    assert part.FLANGE_Z[1] - part.FLANGE_Z[0] == pytest.approx(mounting.SIDE_PLATE_THICKNESS)
    assert mounting.BRACKET_HOLE_POINTS[1][0] - mounting.BRACKET_HOLE_POINTS[0][0] == pytest.approx(mounting.SCREW_MACHINE_X[1] - mounting.SCREW_MACHINE_X[0])
    assert printed_band_mm(spec.DRAWING_PRECISION["FlangeProfile"]["FlangeDepth"], unit=spec.UNIT) == mounting.FLANGE_THICKNESS_BAND
    assert all(
        point[1] == mounting.RECEIVER_ROW_Y and point[2] == part.FLANGE_Z[0]
        for point in mounting.BRACKET_HOLE_POINTS
    )
    assert mounting.SIDE_PLATE_X == (-48.0, 6.25)
    assert tuple(point[0] - part.FLANGE_X[0] for point in mounting.BRACKET_HOLE_POINTS) == (9.0, 22.7)
    assert part.FLANGE_Y == mounting.SIDE_PLATE_Y == (-joint.NOSE_R, joint.NOSE_R)
    assert part.FLANGE_Y == (-5.5, 5.5)
    assert part.FLANGE_X[1] - part.FLANGE_X[0] == pytest.approx(54.25)
    assert joint.NECK_THICKNESS == 12.5 and joint.NOSE_R == 5.5
    assert mounting.SIDE_PLATE_THICKNESS == mounting.GRIP == 3.175
    assert mounting.SCREW_MACHINE_X == (1.0, 14.7)
    assert mounting.RECEIVER_ROW_Y == pytest.approx(0.25)


def test_model_precision_and_functional_bands_have_one_authority() -> None:
    assert spec.DRAWING_PRECISION["Neck"]["NeckThickness"] == 2
    assert spec.DRAWING_PRECISION["FlangeProfile"] == {"FlangeWidth": 2, "FlangeDepth": 3}
    assert spec.DRAWING_PRECISION["Flange"]["FlangeHeight"] == 2
    assert "RootAndFootRounds" not in spec.DRAWING_DIMENSIONS
    assert "RootAndFootRounds" not in spec.DRAWING_PRECISION
    assert spec.INSIDE_ROOT_R == pytest.approx(2.0 * spec.FOOT_CORNER_R)
    assert spec.INSIDE_ROOT_R == pytest.approx(spec.inside_corner_radius_mm(unit=spec.UNIT) / 2.0)
    assert joint.NECK_THICKNESS == 12.5
    # .49 +/-.01 over the 12.5 mm model: .48 is the thinnest accepted neck.
    assert joint.NECK_THICKNESS - joint.NECK_THICKNESS_TOL == pytest.approx(0.48 * 25.4)
    assert joint.NOSE_R_TOL == joint.HOLE_LOCATION_TOL == spec.HEAD_MATERIAL_TOL == 0.0508
    assert mounting.FLANGE_THICKNESS_BAND == spec.FOOT_GRIP_TOL == pytest.approx(0.127)


def test_foot_grip_dimension_sits_on_the_free_end_not_the_upright_face(monkeypatch) -> None:

    import _sketch
    import _sketch_chains

    spans, anchors = [], []

    def dimension_between(_adapter, ref1, ref2, kind, value, _label):
        spans.append((ref1, ref2, kind, value))

    def anchor_point_to_origin(_adapter, ref, x, y, _label):
        anchors.append((ref, x, y))

    def add_sketch_constraint(*_args):
        return SimpleNamespace(is_success=True, data=None)

    monkeypatch.setattr(_sketch_chains, "dimension_between", dimension_between)
    monkeypatch.setattr(_sketch_chains, "anchor_point_to_origin", anchor_point_to_origin)
    monkeypatch.setattr(_sketch_chains._telemetry, "success", lambda *_a, **_k: None)
    points = list(part.FOOT_PROFILE)
    lines = [f"L{index}" for index in range(len(points))]
    dims = _sketch.SketchDims()
    _sketch_chains.define_rectilinear_chain(
        SimpleNamespace(add_sketch_constraint=add_sketch_constraint), lines, points,
        anchor=part.FOOT_PROFILE_ANCHOR, label="foot", dims=dims, names=list(part.FOOT_PROFILE_DIMENSIONS),
    )
    names = [name for name, _drive in dims._rows]
    vertex = {f"{line}.start": points[index] for index, line in enumerate(lines)}
    vertex |= {f"{line}.end": points[(index + 1) % len(points)] for index, line in enumerate(lines)}
    segments = {name: [vertex[ref1], vertex[ref2]] for name, (ref1, ref2, *_rest) in zip(names[:2], spans, strict=True)}
    # Sketch y is -model Z. FlangeDepth spans the free -X end, top to seat,
    # so its drawing witnesses leave real corners, not the shared +X face.
    assert segments["FlangeDepth"] == [(part.FLANGE_X[0], -part.FLANGE_Z[0]), (part.FLANGE_X[0], -part.FLANGE_Z[1])]
    assert spans[names.index("FlangeDepth")][2:] == ("vertical_distance", pytest.approx(mounting.SIDE_PLATE_THICKNESS))
    assert segments["FlangeWidth"] == [(part.FLANGE_X[0], -part.FLANGE_Z[1]), (part.FLANGE_X[1], -part.FLANGE_Z[1])]
    assert anchors == [("L1.start", part.FLANGE_X[0], -part.FLANGE_Z[1])]
    assert names[2:] == ["FlangeCornerX", "FlangeCornerZ"]


def test_overall_precision_bands_do_not_loosen_receiver_or_move_nominal_geometry() -> None:
    assert mounting.SIDE_PLATE_MACHINE_X == (-8.0, 46.25)
    assert mounting.SIDE_PLATE_HEIGHT == 11.0
    assert mounting.COUNTERBORE_END_WALL_MIN >= WALL_TARGET_MM
    assert mounting.COUNTERBORE_HEIGHT_WALL_MIN >= WALL_TARGET_MM
    # The .125 +/-.005 foot grip.
    assert mounting.GRIP_MIN == pytest.approx(0.120 * 25.4)
    assert mounting.GRIP + mounting.GRIP_BAND == pytest.approx(0.130 * 25.4)


@pytest.mark.parametrize("ignored", (False, True))
def test_structural_reasons_are_authored_on_native_source_dimensions(monkeypatch, ignored) -> None:
    writes, displays = [], {}
    expected = {
        (feature, name): text
        for feature, callouts in spec.DIMENSION_CALLOUTS.items()
        for name, text in callouts.items()
    }
    for key in expected:
        values = {}

        def set_text(which, text, *, key=key, values=values):
            writes.append((key, which, text))
            if not ignored:
                values[which] = text

        displays[key] = SimpleNamespace(SetText=set_text, GetText=lambda which, values=values: values.get(which, ""))
    monkeypatch.setattr(part, "_named_dimension", lambda _a, feature, name: (displays[feature, name], object()))
    if ignored:
        with pytest.raises(RuntimeError, match="did not persist"):
            part._author_dimension_callouts(object())
    else:
        part._author_dimension_callouts(object())
        assert writes == [(key, 4, text) for key, text in expected.items()]
        assert {
            key: text for key, text in expected.items()
            if key[0] in ("NeckProfile", "TapCoordinates")
        } == {
            ("NeckProfile", "NoseR"): "RETAINS TAP WALL",
            ("TapCoordinates", "TapFromTip"): "RETAINS TAP WALL",
            ("TapCoordinates", "TapFromSide"): "RETAINS TAP WALL",
        }
        assert expected["FlangeProfile", "FlangeDepth"] == "MHA-MG-VN-53\nSCREW GRIP"
        assert "MountingCoordinates" not in spec.DIMENSION_CALLOUTS


def test_only_clearance_row_moves_with_the_matching_plate_taps() -> None:
    assert mounting.RECEIVER_ROW_Y == pytest.approx(0.25)
    assert mounting.SIDE_PLATE_Y == (-5.5, 5.5)
    assert mounting.CLEARANCE_SPEC.kind == "clearance"
    assert mounting.CLEARANCE_SPEC.size == "#2"
    assert mounting.CLEARANCE_SPEC.fit == "normal"
    for clearance, pilot, screw in zip(
        mounting.BRACKET_HOLE_POINTS,
        mounting.LEVER_HOLE_POINTS,
        mounting.SCREW_POSITIONS,
        strict=True,
    ):
        assert clearance[0] + mounting.BRACKET_ORIGIN[0] == pytest.approx(screw[0])
        # The lever's tap sits at the nearest .001 in to the bracket station.
        assert math.hypot(
            pilot[0] + mounting.LEVER_ORIGIN_X - screw[0],
            pilot[1] - clearance[1],
        ) <= mounting.LEVER_STATION_OFFSET_MAX + 1e-9
        assert clearance[1] == mounting.RECEIVER_ROW_Y
        assert clearance[1] + mounting.BRACKET_ORIGIN[1] == pytest.approx(screw[1])
        assert clearance[2] + mounting.BRACKET_ORIGIN[2] == pytest.approx(screw[2])


_R8_REGION = DrawableRegion(0.0127, 0.0127, 0.4191, 0.2667)


def _native_text(text, x, y, width, *, height=0.0035):
    return {"t": text, "pos": (x, y, 0.0), "h": height, "w": width, "ref": 1, "ang": 0.0}


def _native_line(x0, y0, x1, y1):
    return (0.0, 0.0, 0.0, 0.0, x0, y0, 0.0, x1, y1, 0.0)


def test_native_below_text_keeps_real_glyph_runs_separate_from_interrow_whitespace() -> None:
    boxes = drawing._dimension_text_boxes({
        "texts": [
            _native_text("3.175 ±0.13", .100, .200, .027),
            _native_text("MHA-MG-VN-53", .100, .210, .032),
        ],
    }, label="source-owned grip callout")
    between_rows = Segment(.100, .207, .132, .207)
    combined = drawing.union_boxes(boxes)
    assert segment_box_overlap_length(between_rows, combined) > 0.0
    assert all(segment_box_overlap_length(between_rows, box) == 0.0 for box in boxes)


@pytest.mark.parametrize("fault", (None, "ignored_wrap", "leader_overshoot", "changed_template"))
def test_mounting_callout_reflows_native_size_clear_of_the_current_title_block(monkeypatch, fault):
    from dataclasses import replace

    edge, view = object(), object()
    native_definition = "2X <MOD-DIAM><hw-diam> <hw-thru>"
    state = SimpleNamespace(definition=native_definition, edge=None, view=None, value=mounting.CLEARANCE_DIA / 1000.0)
    display = SimpleNamespace(
        GetAnnotation=lambda: state, IsHoleCallout=lambda: True,
        GetText=lambda part: state.definition if part == 5 else "",
        SetText=lambda part, text: setattr(state, "definition", text),
    )
    template = drawing.DRAWING_TEMPLATES[drawing.SPEC.layout]
    if fault == "changed_template":
        template = replace(template, title_block_left_m=0.205)
        monkeypatch.setitem(drawing.DRAWING_TEMPLATES, drawing.SPEC.layout, template)

    def insert(_adapter, actual_view, *, edge, callout_xy, label):
        state.edge, state.view, state.position = edge, actual_view, callout_xy
        return display

    def native_ink(_adapter, annotation):
        assert annotation is state
        if fault == "ignored_wrap":
            # Exact R9 text runs and shoulder: the last native size row
            # reaches X226.2288 into the title block. No rerun needed.
            texts = [
                _native_text("2 HOLES THRU", 0.1507677, 0.0540267, 0.0304646),
                _native_text("MATES MHA-SM-03 TAPPED HOLES 2X ", 0.1057712, 0.0484705, 0.0834215),
                _native_text("<MOD-DIAM>", 0.1891927, 0.048417, 0.0052784),
                _native_text(" 2.59 THRU ALL", 0.1944712, 0.0484705, 0.0317576),
            ]
            left, right, shoulder = 0.1041837, 0.2262288, 0.048417
        else:
            # Simulated native process/mate reflow. Conservatively retain
            # the old mate+2X width; this is not new rendered glyph evidence.
            x, y = state.position
            texts = [
                _native_text("DRILL 2X <MOD-DIAM> 2.59 THRU ALL", x - 0.060 / 2.0, y, 0.060),
                _native_text(spec.MOUNTING_HOLE_PROCESS, x - 0.0834215 / 2.0, y - 0.0055295, 0.0834215),
            ]
            left = x - 0.0834215 / 2.0 - 0.0015875
            right = x + 0.0834215 / 2.0
            shoulder = 0.048417
            if fault == "leader_overshoot":
                right = 0.2262288
        return {"texts": texts, "lines": [
            _native_line(0.0729985, 0.0790916, left, shoulder),
            _native_line(0.0711515, 0.0809084, 0.0729985, 0.0790916),
            _native_line(left, shoulder, right, shoulder),
        ]}, {}

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "add_native_hole_callout", insert)
    monkeypatch.setattr(drawing, "annotation_display", native_ink)
    monkeypatch.setattr(drawing, "sheet_region", lambda _a: _R8_REGION)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    precision = []
    monkeypatch.setattr(drawing, "set_hole_callout_precision", lambda d, places, *, label: precision.append((d, places)))
    if fault is None:
        assert drawing._add_mounting_callout(object(), view, edge) is display
        ink = drawing._dimension_layout_ink(object(), state, label="mounting")
        assert ink.text[2] + 0.002 <= template.title_block_left_m
        assert all(max(line.x0, line.x1) + 0.002 <= template.title_block_left_m for line in ink.leader)
    else:
        target = "mounting-hole line/leader" if fault == "leader_overshoot" else "mounting-hole callout"
        with pytest.raises(RuntimeError, match=target + ".*crowds.*title block"):
            drawing._add_mounting_callout(object(), view, edge)
    # Process/mate rows preserve the selected edge and every native variable.
    assert state.edge is edge and state.view is view
    assert state.value == mounting.CLEARANCE_DIA / 1000.0
    assert state.position == (0.166, 0.054)
    assert state.definition == native_definition.replace("<hw-thru>", "DRILL <hw-thru>") + "\n" + spec.MOUNTING_HOLE_PROCESS
    assert precision == [(display, {"hw-diam": 3})]


@pytest.mark.parametrize("tapped", (False, True))
@pytest.mark.parametrize("fault", (None, "missing_diameter", "ignored_write"))
def test_native_process_rows_preserve_all_hole_variables_and_mate(monkeypatch, tapped, fault):
    import re

    # Established native callout slots: drill above, thread in prefix.
    drill_token = "<hw-thrutapdrldia>" if tapped else "<hw-diam>"
    definitions = {5: "<hw-threaddesc> <hw-thru>" if tapped else "", 6: "", 7: f"2X <MOD-DIAM>{drill_token} <hw-thru>", 8: ""}
    if fault == "missing_diameter":
        definitions[7] = definitions[7].replace(drill_token, "")
    original = dict(definitions)
    def set_text(part, text):
        if fault != "ignored_write":
            definitions[part + 4] = text
    display = SimpleNamespace(IsHoleCallout=lambda: True, GetText=definitions.get, SetText=set_text)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    mate = spec.TAP_PROCESS if tapped else spec.MOUNTING_HOLE_PROCESS
    if fault:
        with pytest.raises(RuntimeError):
            drawing._set_hole_process(display, mate=mate, tapped=tapped)
    else:
        drawing._set_hole_process(display, mate=mate, tapped=tapped)
        text = "\n".join(definitions.values())
        assert re.findall(r"<hw-[^>]+>", text) == re.findall(r"<hw-[^>]+>", "\n".join(original.values()))
        assert text.count("DRILL") == 1 and "DRILL <hw-thru>" in text and not re.findall(r"\bTAP\b", text)
        assert text.count(mate) == 1
        assert "THRU" not in text.splitlines()  # No standalone literal repeat.


@pytest.mark.parametrize("fault", (None, "missing_seat", "wrong_nose_plane", "wrong_attachment", "arc_rejected", "centre_value", "banded", "precision", "reference_prefix"))
def test_overall_reference_measures_real_seat_to_arc_extreme_without_a_new_size_band(monkeypatch, fault):
    import _drawing_dimensions as dimension_text
    import _drawing_edge_dimensions as edge_dimensions

    seat_edge, nose_edge = object(), object()
    seat = ViewEdge(seat_edge, ((joint.NECK_HALF_X, mounting.SIDE_PLATE_Y[0] + spec.FOOT_CORNER_R, mounting.SIDE_PLATE_Z[1]), (joint.NECK_HALF_X, mounting.SIDE_PLATE_Y[1] - spec.FOOT_CORNER_R, mounting.SIDE_PLATE_Z[1])), None, None)
    nose = ViewEdge(nose_edge, None, ((-1 if fault == "wrong_nose_plane" else 1) * joint.NECK_HALF_X, 0.0, 0.0, 1.0, 0.0, 0.0, joint.NOSE_R), None)
    edges = ViewEdges("visible physical seat and nose", tuple([nose] if fault == "missing_seat" else [seat, nose]))
    geometry = {seat_edge: seat, nose_edge: nose}
    selected = {}
    condition = {1: 0, 2: 1}  # The line has no arc; the arc initially uses its centre.
    text = {}
    position = []

    class NativeDimension:
        Name = "RD1"
        DrivenState = 1
        Tolerance = SimpleNamespace(Type=1 if fault == "banded" else 0)

        @property
        def SystemValue(self):
            first, second = (geometry[edge] for edge in selected["entities"])
            radius = second.circle[6] if condition[2] == 3 and fault != "centre_value" else 0.0
            return (first.midpoint_mm[2] - second.circle[2] + radius) / 1000.0

        def GetArcEndCondition(self, index):
            return condition[index]

        def SetArcEndCondition(self, index, value):
            if fault == "arc_rejected":
                return -1
            condition[index] = value
            return 0

    native = NativeDimension()
    annotation = SimpleNamespace(
        GetAttachedEntities3=lambda: (seat_edge, object() if fault == "wrong_attachment" else nose_edge),
        GetAttachedEntityTypes=lambda: (1, 1),
        IsDangling=lambda: False,
        SetPosition2=lambda *xyz: position.append(xyz) or True,
    )
    display = SimpleNamespace(
        GetDimension=lambda: native, GetDimension2=lambda _index: native,
        GetAnnotation=lambda: annotation, precision=0,
        GetText=lambda part: text.get(part, ""),
    )
    display.SetPrecision3 = lambda places, *_rest: setattr(display, "precision", 0 if fault == "precision" else places)
    display.GetPrimaryPrecision2 = lambda: display.precision
    display.SetText = lambda part, value: text.update({part: "" if fault == "reference_prefix" and part == 1 else value})
    annotation.GetSpecificAnnotation = lambda: display

    def insert(_adapter, _view, **kwargs):
        selected.update(kwargs)
        return display

    for module in (drawing, dimension_text, edge_dimensions):
        monkeypatch.setattr(module, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(dimension_text._sw_type_info, "early_bound_or_flag", lambda value, *_args: value)
    monkeypatch.setattr(dimension_text, "rebuild_drawing", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(drawing, "add_edge_dimension", insert)
    monkeypatch.setattr(drawing, "model_point_in_view", lambda _a, _v, p, **_kw: (.228 - p[1], .2124488 - p[2]))
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(GraphicsRedraw2=lambda: None),
        swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)),
        _attempt=lambda callback: callback(),
    )
    if fault:
        with pytest.raises(RuntimeError):
            drawing._overall_reference(adapter, object(), edges)
    else:
        assert drawing._overall_reference(adapter, object(), edges) is annotation
        # The native boundary now measures the physical arc extreme, not its
        # centre; no nominal text or SystemValue assignment can fake the span.
        assert selected["entities"] == (seat_edge, nose_edge)
        assert selected["orientation"] == "vertical"
        assert native.SystemValue * 1000.0 == pytest.approx(mounting.SIDE_PLATE_Z[1] + joint.NOSE_R)
        assert condition == {1: 0, 2: 3}
        assert native.DrivenState == 1 and native.Tolerance.Type == 0
        assert text == {1: "(", 2: ")"}
        assert display.precision == 2
        assert position[-1][:2] == drawing.OVERALL_REFERENCE_XY


def _r11c_foot_finish_display(*, shifted=False):
    """Portable DetailItem353 native R11c ink; shifted mode is simulation only."""
    display = {
        "lines": [
            [0., 0., 0., 0., .067875, .1040512, .1003976, .075475, .1040512, .1003976],
            [0., 0., 0., 0., .075475, .1040512, .1003976, .079125, .1120512, .0055],
            [0., 0., 0., 0., .069125, .1040512, 0., .06696, .1078012, 0.],
            [0., 0., 0., 0., .07129, .1078012, 0., .06696, .1078012, 0.],
            [0., 0., 0., 0., .069125, .1040512, 0., .0733385, .1111937, 0.],
            [0., 0., 0., 0., .0706555, .109663, 0., .0675945, .109663, 0.],
            [0., 0., 0., 0., .0733385, .1111937, 0., .0836564, .1111937, 0.],
        ],
        "arrows": [[.079125, .1120512, .0055, -.4150878, -.9097814, -0., .003556, .000762, 1., 0., 0., 1.]],
        "texts": [{
            "t": "Ra 3.2", "pos": [.074125, .1076225, 0.], "h": .0025,
            "ref": 1, "ang": 0., "font": "Century Gothic", "ls": .001, "w": .0098437,
        }],
    }
    if shifted:
        # Simulate moving the whole symbol/text 20 mm right, not its attached
        # tip. Recompute the arrow from the new shoulder to that same tip.
        for index, line in enumerate(display["lines"]):
            line[4] += .020
            if index != 1:
                line[7] += .020
        display["texts"][0]["pos"][0] += .020
        arrow = display["arrows"][0]
        shoulder = display["lines"][1][4:6]
        dx, dy = shoulder[0] - arrow[0], shoulder[1] - arrow[1]
        length = math.hypot(dx, dy)
        arrow[3:5] = [dx / length, dy / length]
    return display


@pytest.mark.parametrize("fault", (
    None, "native_crossing", "arrow_only", "stroke_only", "missing_lines", "missing_arrows",
    "short_line", "short_arrow", "nonfinite_line", "nonfinite_arrow",
    "zero_arrow_direction", "zero_arrow_size", "missing_text", "bad_text", "nonfinite_text",
))
def test_foot_finish_own_ink_guard_rejects_r11c_stroke_and_arrow_crossings(fault):
    display = _r11c_foot_finish_display(shifted=fault != "native_crossing")
    if fault == "arrow_only":
        # Preserve the exact R11c arrow and text, removing all crossing strokes.
        display = _r11c_foot_finish_display()
        display["lines"] = [_native_line(.020, .020, .030, .020)]
    elif fault == "stroke_only":
        display = _r11c_foot_finish_display()
        display["arrows"] = [[.020, .020, 0., 1., 0., 0., .003556, .000762]]
    elif fault == "missing_lines":
        display.pop("lines")
    elif fault == "missing_arrows":
        display.pop("arrows")
    elif fault == "short_line":
        display["lines"][0].pop()
    elif fault == "short_arrow":
        display["arrows"][0] = display["arrows"][0][:7]
    elif fault == "nonfinite_line":
        display["lines"][0][4] = math.nan
    elif fault == "nonfinite_arrow":
        display["arrows"][0][3] = math.inf
    elif fault == "zero_arrow_direction":
        display["arrows"][0][3:5] = [0., 0.]
    elif fault == "zero_arrow_size":
        display["arrows"][0][6] = 0.
    elif fault == "missing_text":
        display.pop("texts")
    elif fault == "bad_text":
        display["texts"][0].pop("w")
    elif fault == "nonfinite_text":
        display["texts"][0]["w"] = math.nan
    if fault:
        with pytest.raises(RuntimeError, match="native|crosses its text"):
            drawing._assert_foot_finish_text_clear(display)
    else:
        assert display["arrows"][0][:3] == [.079125, .1120512, .0055]
        drawing._assert_foot_finish_text_clear(display)


def test_foot_finish_guard_keeps_whitespace_between_native_text_runs():
    display = {
        "texts": [_native_text("Ra", .050, .050, .004, height=.0025),
                  _native_text("3.2", .060, .050, .005, height=.0025)],
        "lines": [_native_line(.057, .045, .057, .060)],
        "arrows": [[.020, .020, 0., 1., 0., 0., .003556, .000762]],
    }
    # The line crosses the union envelope, but neither measured run.
    drawing._assert_foot_finish_text_clear(display)
