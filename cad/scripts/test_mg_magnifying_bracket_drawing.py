"""Offline manufactured-interval and native-print contracts for the L bracket."""

from __future__ import annotations

import ast
import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import build_mg_magnifying_bracket as part
import draw_mg_magnifying_bracket as drawing
import magnifying_bracket_joint_layout as mounting
import mg_lever_thread_joint as joint
import mg_magnifying_bracket_spec as spec
from _drawing_edges import ViewEdge, ViewEdges
from _drawing_layout_check import DrawableRegion
from _layout_geometry import Box, Segment, segment_box_overlap_length
from _printed_tolerance import printed_band_mm


def test_foot_joins_flush_without_changing_mounting_grip_or_pattern() -> None:
    assert part.FLANGE_X[1] == joint.NECK_THICKNESS / 2.0
    assert part.FLANGE_X[0] < -joint.NECK_THICKNESS / 2.0
    assert part.FLANGE_Z[1] - part.FLANGE_Z[0] == pytest.approx(mounting.SIDE_PLATE_THICKNESS)
    assert mounting.BRACKET_HOLE_POINTS[1][0] - mounting.BRACKET_HOLE_POINTS[0][0] == pytest.approx(mounting.SCREW_MACHINE_X[1] - mounting.SCREW_MACHINE_X[0])
    assert printed_band_mm(spec.DRAWING_PRECISION["FlangeProfile"]["FlangeDepth"]) == mounting.FLANGE_THICKNESS_BAND
    assert all(
        point[1] == mounting.RECEIVER_ROW_Y and point[2] == part.FLANGE_Z[0]
        for point in mounting.BRACKET_HOLE_POINTS
    )
    assert mounting.SIDE_PLATE_X == (-48.0, 6.25)
    assert tuple(point[0] - part.FLANGE_X[0] for point in mounting.BRACKET_HOLE_POINTS) == (9.0, 22.7)
    # The two root arcs share the same tangent point, with no flat ledge.
    assert spec.ROOT_R + spec.FOOT_CORNER_R == pytest.approx(mounting.SIDE_PLATE_HEIGHT / 2.0 - joint.NOSE_R)
    assert spec.ROOT_R <= 1.0


def test_model_precision_and_functional_bands_have_one_authority() -> None:
    assert spec.DRAWING_PRECISION["Neck"]["NeckThickness"] == 1
    assert spec.DRAWING_PRECISION["FlangeProfile"] == {"FlangeWidth": 1, "FlangeDepth": 3}
    assert spec.DRAWING_PRECISION["Flange"]["FlangeHeight"] == 1
    assert joint.NECK_THICKNESS == 12.5
    assert joint.NECK_THICKNESS_TOL == printed_band_mm(1) == 0.8
    assert joint.NOSE_R_TOL == joint.HOLE_LOCATION_TOL == spec.HEAD_MATERIAL_TOL == 0.05
    assert mounting.FLANGE_THICKNESS_BAND == spec.FOOT_GRIP_TOL == 0.13
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    assert any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "set_dimension_symmetric_tolerance"
        and len(node.args) == 4
        and isinstance(node.args[1], ast.Constant) and node.args[1].value == "FlangeProfile"
        and isinstance(node.args[2], ast.Constant) and node.args[2].value == "FlangeDepth"
        and isinstance(node.args[3], ast.Name) and node.args[3].id == "FOOT_GRIP_TOL"
        for node in ast.walk(tree)
    )


def test_overall_precision_bands_do_not_loosen_receiver_or_move_nominal_geometry() -> None:
    assert mounting.SIDE_PLATE_MACHINE_X == (-8.0, 46.25)
    assert mounting.SIDE_PLATE_HEIGHT == 12.7
    assert mounting.SIDE_PLATE_LENGTH_DEVIATIONS == pytest.approx((-0.85, 0.75))
    assert mounting.SIDE_PLATE_HEIGHT_DEVIATIONS == pytest.approx((-0.8, 0.8))
    assert mounting.LINEAR_BAND == 0.51  # receiver/depth authority is unchanged
    assert mounting.COUNTERBORE_END_WALL_MIN == pytest.approx(7.0)
    assert mounting.COUNTERBORE_HEIGHT_WALL_MIN == pytest.approx(3.64)
    assert mounting.GRIP_MIN == pytest.approx(3.045)
    assert mounting.GRIP + mounting.GRIP_BAND == pytest.approx(3.305)


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
        assert spec.MOUNTING_MATE_FLAG == "[1]"
        assert spec.DIMENSION_CALLOUTS["MountingCoordinates"] == {
            name: "[1]" for name in ("MountingX0", "MountingX1", "MountingY0")
        }
        assert spec.MOUNTING_HOLE_PROCESS == "[1] MATES MHA-SM-03 TAPPED HOLES"


@pytest.mark.parametrize("fault", (None, "missing", "duplicate", "changed"))
@pytest.mark.parametrize("dimension", ("NoseR", "MountingX0", "MountingX1", "MountingY0"))
def test_drawing_only_reads_the_imported_structural_reasons(monkeypatch, fault, dimension) -> None:
    annotations = []
    for callouts in spec.DIMENSION_CALLOUTS.values():
        for name, text in callouts.items():
            if fault == "missing" and name == dimension:
                continue
            value = "changed source callout" if fault == "changed" and name == dimension else text.replace("\n", "\r\n")
            item = SimpleNamespace(name=name, GetText=lambda which, value=value: value if which == 4 else "")
            item.GetSpecificAnnotation = lambda item=item: item
            annotations.append(item)
    if fault == "duplicate":
        annotations.append(next(item for item in annotations if item.name == dimension))
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "dimension_name", lambda _a, item: item.name)
    if fault:
        with pytest.raises(RuntimeError, match="structural callout"):
            drawing._assert_dimension_callouts(object(), annotations)
    else:
        drawing._assert_dimension_callouts(object(), annotations)


def test_only_clearance_row_moves_with_the_matching_plate_taps() -> None:
    assert mounting.RECEIVER_ROW_Y == pytest.approx(-0.71)
    assert mounting.SIDE_PLATE_Y == (-6.35, 6.35)
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
        assert pilot[0] + mounting.LEVER_ORIGIN_X == pytest.approx(screw[0])
        assert clearance[1] == pilot[1] == mounting.RECEIVER_ROW_Y
        assert clearance[1] + mounting.BRACKET_ORIGIN[1] == pytest.approx(screw[1])
        assert clearance[2] + mounting.BRACKET_ORIGIN[2] == pytest.approx(screw[2])


def test_layout_retains_four_views_of_the_current_l_bracket() -> None:
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "build"
    )
    calls = [node for node in ast.walk(build) if isinstance(node, ast.Call)]
    placed = [
        call for call in calls
        if isinstance(call.func, ast.Name) and call.func.id == "place_view"
    ]
    assert len(placed) == 4
    assert {ast.literal_eval(call.args[2]) for call in placed} == {
        "*Top", "*Front", "*Right", "*Isometric",
    }




def test_mounting_callout_selects_the_visible_exit_not_the_hidden_entry(monkeypatch) -> None:
    visible = ViewEdges(
        label="front HLR mounting face",
        edges=tuple(
            ViewEdge(edge=object(), line=None, circle=(point[0], point[1], mounting.SIDE_PLATE_Z[1], 0.0, 0.0, 1.0, mounting.CLEARANCE_DIA / 2.0), vertices=None)
            for point in mounting.BRACKET_HOLE_POINTS
        ),
    )
    monkeypatch.setattr(drawing, "scan_view_edges", lambda _view, *, label: visible)
    assert drawing._mounting_rims(object()) == visible.edges
    # Mutation/pre-fix control: the real visible-edge matcher rejects an entry
    # rim even though its XY position, radius and normal all match.
    with pytest.raises(RuntimeError):
        visible.circle_at(mounting.BRACKET_HOLE_POINTS[1], mounting.CLEARANCE_DIA / 2.0, axis=(0.0, 0.0, 1.0), label="hidden entry")
    centered = ViewEdges(
        label="obsolete centered mounting row",
        edges=tuple(
            ViewEdge(
                edge=object(), line=None,
                circle=(point[0], 0.0, mounting.SIDE_PLATE_Z[1], 0.0, 0.0, 1.0, mounting.CLEARANCE_DIA / 2.0),
                vertices=None,
            )
            for point in mounting.BRACKET_HOLE_POINTS
        ),
    )
    monkeypatch.setattr(drawing, "scan_view_edges", lambda _view, *, label: centered)
    with pytest.raises(RuntimeError):
        drawing._mounting_rims(object())


def _placement_adapter(monkeypatch, statuses):
    reads = []
    features = {}
    for name, status in statuses.items():
        def native_status(name=name, status=status):
            reads.append(name)
            if isinstance(status, Exception):
                raise status
            return status

        sketch = SimpleNamespace(
            GetSketchPoints2=lambda: (object(),),
            GetSketchSegments=lambda: (),
            GetConstrainedStatus=native_status,
        )
        profile = SimpleNamespace(
            Name=f"{name}Placement",
            GetTypeName2=lambda: "ProfileFeature",
            GetSpecificFeature2=lambda sketch=sketch: sketch,
            GetNextSubFeature=lambda: None,
        )
        features[name] = SimpleNamespace(GetFirstSubFeature=lambda profile=profile: profile)
    model = SimpleNamespace(FeatureByName=features.get)
    bindings = []

    def bind(value, interface):
        bindings.append(interface)
        if value is model:
            assert interface == "IPartDoc"
        return value

    def lossy_named_status(*_args):
        raise AssertionError("must read the retained ISketch, not named SDK status")

    monkeypatch.setattr(part, "_early_bound", bind)
    return SimpleNamespace(currentModel=model, check_sketch_fully_defined=lossy_named_status), reads, bindings


def test_closed_native_wizard_placement_status_is_read_for_both_holes(monkeypatch) -> None:
    adapter, reads, bindings = _placement_adapter(monkeypatch, {"MountingHoles": 3, "LeverTap": 3})
    part._assert_placement_sketches_fully_defined(adapter)
    assert reads == ["MountingHoles", "LeverTap"]
    assert bindings[0] == "IPartDoc" and bindings.count("ISketch") == 2


@pytest.mark.parametrize("status", (None, "unknown", "3", True, 0, 1, 2, 4, RuntimeError("native read unavailable")))
@pytest.mark.parametrize("feature", ("MountingHoles", "LeverTap"))
def test_native_wizard_placement_refuses_every_non_fully_defined_result(monkeypatch, feature, status) -> None:
    states = {"MountingHoles": 3, "LeverTap": 3}
    states[feature] = status
    adapter, reads, _bindings = _placement_adapter(monkeypatch, states)
    with pytest.raises(RuntimeError):
        part._assert_placement_sketches_fully_defined(adapter)
    assert reads[-1] == feature


def test_native_wizard_placement_refuses_a_missing_feature(monkeypatch) -> None:
    adapter, _reads, _bindings = _placement_adapter(monkeypatch, {"MountingHoles": 3})
    with pytest.raises(RuntimeError, match="LeverTap: native part feature not found"):
        part._assert_placement_sketches_fully_defined(adapter)


_R8_REGION = DrawableRegion(0.0127, 0.0127, 0.4191, 0.2667)


def _native_text(text, x, y, width, *, height=0.0035):
    return {"t": text, "pos": (x, y, 0.0), "h": height, "w": width, "ref": 1, "ang": 0.0}


def _native_line(x0, y0, x1, y1):
    return (0.0, 0.0, 0.0, 0.0, x0, y0, 0.0, x1, y1, 0.0)


@pytest.mark.parametrize("fault", ("missing_width", "nan_width", "missing_lines", "read_error"))
def test_native_text_layout_never_substitutes_nominal_boxes_for_missing_readbacks(monkeypatch, fault):
    adapter, annotation = object(), object()
    display = {"texts": [_native_text("12.50", 0.100, 0.200, 0.010)], "lines": [_native_line(0.100, 0.200, 0.110, 0.200)]}
    errors = {}
    if fault == "missing_width":
        display["texts"][-1].pop("w")
    elif fault == "nan_width":
        display["texts"][-1]["w"] = math.nan
    elif fault == "missing_lines":
        display.pop("lines")
    else:
        errors["GetTextPositionAtIndex"] = 1
    monkeypatch.setattr(drawing, "annotation_display", lambda *_a: (display, errors))
    with pytest.raises(RuntimeError, match="native"):
        drawing._dimension_layout_ink(adapter, annotation, label="mouth")


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


def _tap_name_adapter(monkeypatch, *, count=1, fault=None, definition=None, resolved=None, native_class=" - 2B"):
    """Model distinct returned dispatch metadata and concrete string interfaces."""
    from win32com.client import dynamic

    state = SimpleNamespace(selected=None, notes=[], deleted=[])

    def clear(_all):
        state.selected = None

    def delete():
        if fault != "deletion_ignored":
            state.notes.remove(state.selected)
            state.deleted.append(state.selected)
        # IModelDoc2.EditDelete returns void.

    def note(text):
        native = SimpleNamespace(GetText=lambda: text)

        def select(append, mark):
            assert append is False and mark == 0
            state.selected = native
            return fault != "selection_refused"

        native.GetAnnotation = lambda: SimpleNamespace(Select2=select)
        return native

    state.notes = [note(f"{joint.THREAD} Tapped Hole") for _ in range(count)]
    required = (note("MATES MHA-MG-03 LEVER"),)
    state.notes.extend(required)
    view = SimpleNamespace(GetNotes=lambda: tuple(state.notes))
    adapter = SimpleNamespace(currentModel=SimpleNamespace(ClearSelection2=clear, EditDelete=delete))
    native_definition = "THRU\nMATES MHA-MG-03 LEVER <hw-threaddesc> <hw-threadclass> <hw-thru>" if definition is None else definition
    state.definition = native_definition
    state.native_class = SimpleNamespace(VariableName="hw-threadclass", Type=3, String=native_class)
    state.native_description = SimpleNamespace(VariableName="hw-threaddesc", Type=3, String=f"{joint.THREAD} UNC")
    state.set_text = []

    def get_text(location):
        if location == 5:
            return state.definition
        if location != 1:
            return ""
        if resolved is not None:
            return resolved
        text = state.definition.replace("<hw-threaddesc>", state.native_description.String)
        text = text.replace("<hw-threadclass>", state.native_class.String).replace("<hw-thru>", "THRU")
        if fault == "stale_resolved_class" and state.set_text:
            return text + " 2B"
        if fault == "lost_resolved_size" and state.set_text:
            return ""
        return text

    def set_text(location, text):
        assert location == 1
        state.set_text.append(text)
        if fault != "class_definition_ignored":
            state.definition = text
        if fault == "native_class_changed":
            state.native_class.String = "3B"
        # IDisplayDimension.SetText returns void.

    variables = (state.native_description, state.native_class)
    if fault == "missing_class_variable":
        variables = (state.native_description,)
    elif fault == "duplicate_class_variable":
        variables = (*variables, state.native_class)
    elif fault == "non_string_class":
        state.native_class.Type = 1
    native_by_dispatch, native_by_wrapper = {}, {}
    state.metadata_reads, state.variable_bindings = [], []
    returned = []
    for variable in variables:
        pointer = object()
        wrapper = SimpleNamespace(_oleobj_=pointer)
        native_by_dispatch[pointer] = variable
        native_by_wrapper[id(wrapper)] = variable
        returned.append(wrapper)

    def dispatch(pointer):
        variable = native_by_dispatch[pointer]
        state.metadata_reads.append(variable.VariableName)
        return variable

    original_bind = drawing._early_bound

    def bind(value, interface):
        if id(value) in native_by_wrapper:
            # R7: merely relabelling this concrete dispatch as the base
            # interface invokes an incompatible VariableName DISPID.
            assert interface == "ICalloutStringVariable", "unsafe base-interface DISPID on returned variable dispatch"
            state.variable_bindings.append(interface)
            return native_by_wrapper[id(value)]
        return original_bind(value, interface)

    monkeypatch.setattr(dynamic, "Dispatch", dispatch)
    monkeypatch.setattr(drawing, "_early_bound", bind)
    callout = SimpleNamespace(
        GetText=get_text, SetText=set_text, IsHoleCallout=lambda: True,
        GetHoleCalloutVariables=lambda: tuple(returned),
    )
    return adapter, view, callout, state, required


@pytest.mark.parametrize("count", (0, 1, 2))
def test_automatic_tap_name_cleanup_keeps_the_associative_thread_and_required_notes(monkeypatch, count) -> None:
    adapter, view, callout, state, required = _tap_name_adapter(monkeypatch, count=count)
    definition = callout.GetText(5)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    assert drawing._curate_tap_callout(adapter, view, callout) == count
    assert tuple(state.notes) == required
    assert len(state.deleted) == count and state.selected is None
    assert callout.GetText(5) == definition.replace(" <hw-threadclass>", "")
    assert state.native_class.String == " - 2B"
    assert state.native_description.String == f"{joint.THREAD} UNC"
    assert "<hw-threaddesc>" in callout.GetText(5) and "<hw-thru>" in callout.GetText(5)
    assert "MATES MHA-MG-03 LEVER" in callout.GetText(1)
    assert joint.THREAD in callout.GetText(1) and "2B" not in callout.GetText(1)
    assert state.metadata_reads == ["hw-threaddesc", "hw-threadclass"]
    assert state.variable_bindings == ["ICalloutStringVariable"]


@pytest.mark.parametrize("missing", ("<hw-threaddesc>", "<hw-threadclass>", "<hw-thru>"))
def test_tap_name_is_not_removed_without_an_authoritative_native_thread_callout(monkeypatch, missing) -> None:
    adapter, view, callout, state, _required = _tap_name_adapter(monkeypatch)
    definition = callout.GetText(5).replace(missing, "")
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match="native thread description/class/extent"):
        drawing._curate_tap_callout(adapter, view, SimpleNamespace(GetText=lambda _location: definition))
    assert not state.deleted
    assert any(note.GetText() == f"{joint.THREAD} Tapped Hole" for note in state.notes)


@pytest.mark.parametrize("resolved", ("", "THRU MATES MHA-MG-03 LEVER", "10-32 UNF 2B THRU"))
def test_tap_name_cleanup_requires_the_actual_resolved_thread_size(monkeypatch, resolved) -> None:
    adapter, view, callout, state, _required = _tap_name_adapter(monkeypatch, resolved=resolved)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match="no resolved native thread size"):
        drawing._curate_tap_callout(adapter, view, callout)
    assert not state.deleted and not state.set_text


@pytest.mark.parametrize("fault, message", (
    ("missing_class_variable", "one native string thread-class"),
    ("duplicate_class_variable", "one native string thread-class"),
    ("non_string_class", "one native string thread-class"),
    ("class_definition_ignored", "kept its thread class"),
    ("native_class_changed", "changed its native variable"),
    ("stale_resolved_class", "still prints 2B"),
    ("lost_resolved_size", "lost its resolved thread size"),
))
def test_tap_curation_refuses_lost_or_modified_native_thread_metadata(monkeypatch, fault, message) -> None:
    adapter, view, callout, state, _required = _tap_name_adapter(monkeypatch, fault=fault)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match=message):
        drawing._curate_tap_callout(adapter, view, callout)
    assert not state.deleted


def test_tap_curation_preserves_a_nondefault_native_class_instead_of_hiding_it(monkeypatch) -> None:
    adapter, view, callout, state, _required = _tap_name_adapter(monkeypatch, native_class="3B")
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match="not the title-block default 2B"):
        drawing._curate_tap_callout(adapter, view, callout)
    assert not state.deleted and not state.set_text
    assert state.native_class.String == "3B"


@pytest.mark.parametrize("fault", ("selection_refused", "deletion_ignored"))
def test_tap_name_cleanup_requires_native_selection_and_actual_deletion(monkeypatch, fault) -> None:
    adapter, view, callout, state, _required = _tap_name_adapter(monkeypatch, fault=fault)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match="redundant tap feature-name note"):
        drawing._curate_tap_callout(adapter, view, callout)
    assert not state.deleted


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
    assert state.definition == "DRILL " + native_definition + "\n" + spec.MOUNTING_HOLE_PROCESS


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
        assert text.count("DRILL") == 1 and len(re.findall(r"\bTAP\b", text)) == int(tapped)
        assert text.count(mate) == 1
        assert "THRU" not in text.splitlines()  # No standalone literal repeat.


@pytest.mark.parametrize("fault", (None, "missing_edge", "ambiguous_edge", "wrong_attachment", "wrong_value", "basic", "precision"))
def test_neck_location_uses_straight_physical_faces_away_from_smooth_root(monkeypatch, fault):
    import _drawing_edge_dimensions as edge_dimensions

    neck_edge, foot_edge = object(), object()
    neck = ViewEdge(neck_edge, ((joint.NECK_HALF_X, -joint.NOSE_R, 0.0), (joint.NECK_HALF_X, -joint.NOSE_R, mounting.SIDE_PLATE_Z[0] - spec.ROOT_R)), None, None)
    foot = ViewEdge(foot_edge, ((joint.NECK_HALF_X - spec.FOOT_CORNER_R, mounting.SIDE_PLATE_Y[0], mounting.SIDE_PLATE_Z[0] + spec.FOOT_CORNER_R), (joint.NECK_HALF_X - spec.FOOT_CORNER_R, mounting.SIDE_PLATE_Y[0], mounting.SIDE_PLATE_Z[1])), None, None)
    edges = [neck] if fault == "missing_edge" else [neck, foot]
    if fault == "ambiguous_edge":
        edges.append(ViewEdge(object(), foot.line, None, None))
    attached = (neck_edge, object() if fault == "wrong_attachment" else foot_edge)
    annotation = SimpleNamespace(GetAttachedEntities3=lambda: attached, GetAttachedEntityTypes=lambda: (1, 1), IsDangling=lambda: False)
    expected = -joint.NOSE_R - mounting.SIDE_PLATE_Y[0]
    native = SimpleNamespace(Name="RD1", SystemValue=(expected + (0.1 if fault == "wrong_value" else 0.0)) / 1000.0, Tolerance=SimpleNamespace(Type=1 if fault == "basic" else 0))
    display = SimpleNamespace(GetAnnotation=lambda: annotation, GetDimension2=lambda _i: native, ShowParenthesis=True, precision=0)
    display.SetPrecision3 = lambda primary, *_rest: setattr(display, "precision", 0 if fault == "precision" else primary)
    display.GetPrimaryPrecision2 = lambda: display.precision
    selected = {}

    def insert(_adapter, _view, **kwargs):
        selected.update(kwargs)
        return display

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(edge_dimensions, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(edge_dimensions._sw_type_info, "early_bound_or_flag", lambda value, *_args: value)
    monkeypatch.setattr(drawing, "add_edge_dimension", insert)
    monkeypatch.setattr(drawing, "model_point_in_view", lambda _a, _v, p, **_kw: (0.228 - p[1], 0.2124488 - p[2]))
    adapter = SimpleNamespace(swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)))
    side = SimpleNamespace(GetOutline=lambda: (0.216062, 0.1064632, 0.239938, 0.2235368))
    if fault:
        with pytest.raises(RuntimeError):
            drawing._neck_to_foot_side(adapter, side, ViewEdges("physical side edges", tuple(edges)))
    else:
        assert drawing._neck_to_foot_side(adapter, side, ViewEdges("physical side edges", tuple(edges))) is annotation
        assert selected["entities"] == (neck_edge, foot_edge)
        assert selected["orientation"] == "horizontal"
        assert abs(selected["p0"][0] - selected["p1"][0]) * 1000.0 == pytest.approx(expected)
        assert native.Name == "NeckToFootSide" and native.Tolerance.Type == 0
        assert display.precision == 2 and display.ShowParenthesis is False
        # Witnesses land midway along actual straight faces, not on the root
        # arc, its vanished flat ledge, or an invented silhouette segment.
        assert selected["p0"][1] > .150 and selected["p1"][1] < .115


@pytest.mark.parametrize("fault", (None, "missing_seat", "wrong_nose_plane", "wrong_attachment", "arc_rejected", "centre_value", "banded", "precision", "reference_prefix"))
def test_overall_reference_measures_real_seat_to_arc_extreme_without_a_new_size_band(monkeypatch, fault):
    import _drawing_dimensions as dimension_text
    import _drawing_edge_dimensions as edge_dimensions

    seat_edge, nose_edge = object(), object()
    seat = ViewEdge(seat_edge, ((joint.NECK_HALF_X, -6.10, mounting.SIDE_PLATE_Z[1]), (joint.NECK_HALF_X, 6.10, mounting.SIDE_PLATE_Z[1])), None, None)
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
        assert native.SystemValue * 1000.0 == pytest.approx(105.89758778042652)
        assert condition == {1: 0, 2: 3}
        assert native.DrivenState == 1 and native.Tolerance.Type == 0
        assert text == {1: "(", 2: ")"}
        assert display.precision == 2
        assert position[-1][:2] == drawing.OVERALL_REFERENCE_XY


@pytest.mark.parametrize("row_mm", (5.64, 6.35))
@pytest.mark.parametrize("fault", (None, "unsettled_modes", "ignored_move", "own_crossing", "neighbour_crossing", "lateral_name", "overall_name"))
def test_reviewed_linear_ink_is_placed_from_geometry_and_guards_actual_segments(monkeypatch, fault, row_mm):
    """R7 head ink plus historical foot witnesses; new moves are simulations.

    R2 did not capture MountingY0's final primitive. Its extra mode-created
    shoulder is a stale-geometry control, NOT its native trace. R7 did capture
    the head's real rows, tap leader and outward arrow flanks below.
    """
    rows = {
        "NeckThickness": [("12.5", .1070212, .185, .012)],
        "FlangeDepth": [
            ("3.175 ±0.13", .1667191, .123, .027),
            ("MHA-MG-VN-53", .1667191, .118, .032),
            ("SCREW GRIP", .1667191, .113, .025),
        ],
        "MountingX0": [("9.00 ±0.05", .0327281, .0532219, .0245438)],
        "MountingX1": [("22.70 ±0.05", .0464351, .0432219, .0271299)],
        "MountingY0": [(f"{row_mm:.2f} ±0.05", .0177281, .0772219, .0245438)],
        "SeatToAxis": [("100.40", .1875951, .1622219, .0168097)],
        "FlangeWidth": [("54.2", .0718882, .0952219, .0142236)],
        "NeckToFootSide": [("0.85", .247, .096, .010)],
        "NoseR": [
            ("R5.50 ±0.05", .2536042, .229, .0247917),
            ("RETAINS TAP WALL", .245683, .2234437, .040634),
        ],
        "TapFromTip": [
            ("5.50 ±0.05", .1747042, .226, .0219576),
            ("RETAINS TAP WALL", .165366, .2204437, .040634),
        ],
        "TapFromSide": [
            ("5.50 ±0.05", .2290212, .240, .0219576),
            ("RETAINS TAP WALL", .219683, .2344437, .040634),
        ],
        "OverallHeight": [("(105.90)", .162, .1822219, .022)],
        "LeverTapCallout": [
            ("DRILL ", .3200021, .2388049, .0129597),
            ("<MOD-DIAM>", .3329618, .2387514, .0052784),
            (" 5.11 THRU ALL", .3382403, .2388049, .0317576),
            ("TAP 1/4-20 UNC THRU ALL", .3167813, .2331951, .0564375),
            ("MATES MHA-MG-03 LEVER", .3160156, .2276389, .0579687),
        ],
    }
    lines = {
        "NeckThickness": [(.091125, .2114488, .091125, .1784438), (.103625, .2114488, .103625, .1784438), (.091125, .1794438, .1633882, .1794438)],
        "FlangeDepth": [(.104625, .1120512, .141, .1120512), (.104625, .1152262, .141, .1152262), (.2050757, .1174438, .140, .1174438), (.140, .1174438, .140, .1152262), (.140, .1120512, .140, .1057012)],
        "MountingX0": [(.054375, .07265, .054375, .0522219), (.058375, .07265, .058375, .0522219), (.0327281, .0532219, .064725, .0532219)],
        "MountingX1": [(.054375, .07265, .054375, .0422219), (.072075, .07265, .072075, .0422219), (.048025, .0432219, .078425, .0432219)],
        "MountingY0": [(.057375, .080 - row_mm / 1000.0, .029, .080 - row_mm / 1000.0), (.0535796, .080, .029, .080), (.030, .080 - row_mm / 1000.0, .030, .080 - 2.0 * row_mm / 1000.0), (.030, .080, .030, .080 + row_mm / 1000.0)],
        "SeatToAxis": [(.2215, .1120512, .195, .1120512), (.2340527, .2124488, .195, .2124488), (.196, .1120512, .196, .1622219), (.196, .2124488, .196, .1677781)],
        "FlangeWidth": [(.054375, .1110512, .054375, .0942219), (.103625, .1110512, .103625, .0942219), (.054375, .0952219, .103625, .0952219)],
        "NeckToFootSide": [(.2335, .110, .2335, .095), (.23435, .110, .23435, .095), (.2335, .096, .257, .096)],
        "OverallHeight": [(.228, .1120512, .173, .1120512), (.228, .2179488, .173, .2179488), (.174, .1120512, .174, .181), (.174, .2179488, .174, .189)],
        "NoseR": [
            (.2325415, .2155511, .2440955, .2234438),
            (.228, .2124488, .2325415, .2155511),
            (.2440955, .2234438, .286317, .2234438),
            (.2325415, .2155511, .2352629, .2178715),
            (.2352629, .2178715, .2356927, .2172423),
            (.2356927, .2172423, .2325415, .2155511),
        ],
        "TapFromTip": [
            (.2325, .2179488, .205, .2179488),
            (.2325, .2124488, .205, .2124488),
            (.165366, .2204438, .206, .2204438),
            (.206, .2204438, .206, .2179488),
            (.206, .2124488, .206, .2060988),
            (.206, .2179488, .205619, .2215048),
            (.205619, .2215048, .206381, .2215048),
            (.206381, .2215048, .206, .2179488),
            (.206, .2124488, .206381, .2088928),
            (.206381, .2088928, .205619, .2088928),
            (.205619, .2088928, .206, .2124488),
        ],
        "TapFromSide": [
            (.2335, .2134488, .2335, .2354438),
            (.228, .2185015, .228, .2354438),
            (.2335, .2344438, .260317, .2344438),
            (.2335, .2344438, .228, .2344438),
            (.228, .2344438, .22165, .2344438),
            (.2335, .2344438, .237056, .2348248),
            (.237056, .2348248, .237056, .2340628),
            (.237056, .2340628, .2335, .2344438),
            (.228, .2344438, .224444, .2340628),
            (.224444, .2340628, .224444, .2348248),
            (.224444, .2348248, .228, .2344438),
        ],
        "LeverTapCallout": [
            (.2305142, .2128907, .3144281, .2276389),
            (.2254858, .2120069, .2305142, .2128907),
            (.3144281, .2276389, .3739844, .2276389),
            (.2305142, .2128907, .2339506, .2138815),
            (.2339506, .2138815, .2340825, .213131),
            (.2340825, .213131, .2305142, .2128907),
        ],
    }
    items = {name: SimpleNamespace(name=name, dx=0.0, dy=0.0, CenterText=True, OffsetText=False) for name in rows}
    for item in items.values():
        item.GetSpecificAnnotation = lambda item=item: item
    items["NeckToFootSide"].GetDimension2 = lambda _index: SimpleNamespace(Name="D1" if fault == "lateral_name" else "NeckToFootSide")
    items["OverallHeight"].GetDimension2 = lambda _index: SimpleNamespace(Name="D1" if fault == "overall_name" else "OverallHeight")
    state = SimpleNamespace(modes_settled=False)
    mode_shoulder_y = .080 + row_mm / 1000.0 + .00445
    messages = []

    def rebuild(_adapter, *, label):
        if label == "settle bracket linear text modes" and fault != "unsettled_modes":
            assert all(items[name].OffsetText for name in ("NeckThickness", "FlangeDepth", "MountingY0", "TapFromTip", "TapFromSide"))
            state.modes_settled = True

    def native_display(_adapter, item):
        native_lines = list(lines[item.name])
        if item.name == "NeckThickness":
            native_lines = [(a, b, c, d + item.dy) if i < 2 else (a, b + item.dy, c, d + item.dy) for i, (a, b, c, d) in enumerate(native_lines)]
        elif item.name == "FlangeDepth":
            native_lines = [(a if i < 2 else a + item.dx, b, c + item.dx, d) for i, (a, b, c, d) in enumerate(native_lines)]
        elif item.name == "NoseR":
            native_lines = [
                (a, b, c + item.dx, d + item.dy) if i == 0 else
                (a + item.dx, b + item.dy, c + item.dx, d + item.dy) if i == 2 else (a, b, c, d)
                for i, (a, b, c, d) in enumerate(native_lines)
            ]
        elif item.name == "TapFromTip" and item.OffsetText and state.modes_settled:
            # New offset mode is a simulation, retaining R7's fixed witnesses
            # and complete outward-arrow triangles. Do not translate arrows.
            x, y = rows[item.name][1][1] + item.dx, rows[item.name][1][2] + item.dy
            native_lines = [
                *native_lines[:2], (.206, .2179488, .206, .2242988),
                native_lines[4], *native_lines[5:],
                (.206, .2151988, x, y), (x, y, x + .040634, y),
            ]
        elif item.name == "TapFromSide" and item.OffsetText and state.modes_settled:
            # R7 captured these settled mode coordinates before any text move.
            x, y = .2159433 + item.dx, .2458861 + item.dy
            native_lines = [
                (.2335, .2134488, .2335, .241), (.228, .2185015, .228, .241),
                (.2335, .240, .23985, .240), (.2335, .240, .228, .240),
                (.228, .240, .22165, .240), (.23075, .240, x, y),
                (x, y, x + .040634, y),
                (.2335, .240, .237056, .240381), (.237056, .240381, .237056, .239619),
                (.237056, .239619, .2335, .240),
                (.228, .240, .224444, .239619), (.224444, .239619, .224444, .240381),
                (.224444, .240381, .228, .240),
            ]
        if item.name == "MountingY0" and item.OffsetText and state.modes_settled:
            native_lines.extend((
                (.030, .080 + row_mm / 1000.0, rows[item.name][0][1] + item.dx, rows[item.name][0][2] + item.dy),
                (.030, mode_shoulder_y, .051, mode_shoulder_y),
            ))
        if fault == "own_crossing" and item.name == "MountingX1" and item.dx:
            x = rows[item.name][0][1] + item.dx + .010
            native_lines.append((x, .041, x, .050))
        if fault == "neighbour_crossing" and item.name == "FlangeWidth" and items["MountingX1"].dx:
            x = rows["MountingX1"][0][1] + items["MountingX1"].dx + .010
            native_lines.append((x, .041, x, .050))
        mode_dx, mode_dy = (-.0037397, .0114424) if item.name == "TapFromSide" and item.OffsetText and state.modes_settled else (0.0, 0.0)
        return {
            "texts": [_native_text(text, x + item.dx + mode_dx, y + item.dy + mode_dy, width) for text, x, y, width in rows[item.name]],
            "lines": [_native_line(*line) for line in native_lines],
        }, {}

    def move(_adapter, item, dx, dy, *, label):
        if fault != "ignored_move":
            item.dx += dx
            item.dy += dy
        # move_annotation rebuilds in production. This control makes a skipped
        # mode rebuild visible only after a move, reproducing stale targeting.
        state.modes_settled = True

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "annotation_display", native_display)
    # R32 created and measured this native edge dimension successfully, but
    # later model-item name discovery did not find it. Its retained handle
    # must still receive the same real ink and neighbour-clearance checks.
    monkeypatch.setattr(drawing, "dimension_name", lambda _a, item: "" if item.name in ("NeckToFootSide", "OverallHeight", "LeverTapCallout") else item.name)
    monkeypatch.setattr(drawing, "move_annotation", move)
    monkeypatch.setattr(drawing, "sheet_region", lambda _a: _R8_REGION)
    monkeypatch.setattr(drawing, "model_point_in_view", lambda _a, _v, p, **_kw: (.097375 + p[0], .080 + p[1]))
    monkeypatch.setattr(drawing, "rebuild_drawing", rebuild)
    monkeypatch.setattr(drawing._telemetry, "info", lambda message, **fields: messages.append((message, fields)))
    front = SimpleNamespace(GetOutline=lambda: (.048787, .1064632, .109213, .2235368))
    # Historical frozen witnesses cross both horizontal size text boxes and
    # the row text at Y80. The 5.64 case changes the actual measured Y span.
    for name, line in (("MountingX0", lines["MountingX0"][0]), ("MountingX1", lines["MountingX1"][0]), ("MountingY0", lines["MountingY0"][1]), ("TapFromSide", lines["TapFromSide"][0])):
        box = Box(*drawing._dimension_layout_ink(object(), items[name], label=name).text)
        assert segment_box_overlap_length(Segment(*line), box) > 0.0
    # Causal R7 controls: the through-tap diagonal crowds the radius's 2 mm
    # envelope, and the top outward arrow crosses TapFromTip's reason glyphs.
    nose = drawing._dimension_layout_ink(object(), items["NoseR"], label="NoseR").text
    expanded_nose = Box(nose[0] - .002, nose[1] - .002, nose[2] + .002, nose[3] + .002)
    assert segment_box_overlap_length(Segment(*lines["LeverTapCallout"][0]), expanded_nose) == pytest.approx(.0092782, abs=1e-7)
    tip_reason = Box(.165366 + .00015, .2204437 + .00015, .206 - .00015, .2239437 - .00015)
    assert segment_box_overlap_length(Segment(*lines["TapFromTip"][5]), tip_reason) > .0009
    if fault:
        message = "retained native dimension name" if fault in ("lateral_name", "overall_name") else ("did not settle" if fault == "ignored_move" else ("own native line" if fault in ("own_crossing", "unsettled_modes") else "neighbouring native line"))
        with pytest.raises(RuntimeError, match=message):
            drawing._layout_linear_annotations(object(), front, object(), [item for name, item in items.items() if name not in ("NeckToFootSide", "OverallHeight", "LeverTapCallout")], lateral_location=items["NeckToFootSide"], overall_reference=items["OverallHeight"], tap_callout=items["LeverTapCallout"])
    else:
        drawing._layout_linear_annotations(object(), front, object(), [item for name, item in items.items() if name not in ("NeckToFootSide", "OverallHeight", "LeverTapCallout")], lateral_location=items["NeckToFootSide"], overall_reference=items["OverallHeight"], tap_callout=items["LeverTapCallout"])
        ink = {name: drawing._dimension_layout_ink(object(), item, label=name) for name, item in items.items()}
        assert ink["NeckThickness"].text[0] == pytest.approx(.103625 + .004)
        assert items["NeckThickness"].OffsetText
        assert ink["NeckThickness"].text[1] > .2235368
        assert ink["FlangeDepth"].text[2] < .196
        # A real new overall line would cut the old 3.175 text station.
        # Its measured witness now bounds that lane too, not a fixed nudge.
        assert segment_box_overlap_length(Segment(.174, .1120512, .174, .181), Box(.1667191, .123, .1783566, .1265)) > 0.0
        assert ink["FlangeDepth"].text[2] <= .174 - .004 + 1e-8
        assert items["FlangeDepth"].OffsetText
        assert ink["FlangeDepth"].text[1] > max(max(line[1], line[3]) for line in lines["FlangeDepth"])
        assert ink["MountingX0"].text[2] < .054375
        assert ink["MountingX1"].text[0] > .072075
        assert ink["MountingY0"].text[1] == pytest.approx(mode_shoulder_y + .0022)
        # Causal stale-target control: deriving the lane from pre-mode lines
        # places this same shoulder through the text, for either row value.
        old_bottom = .080 + row_mm / 1000.0 + .0022
        stale_box = Box(ink["MountingY0"].text[0], old_bottom, ink["MountingY0"].text[2], old_bottom + .0035)
        assert segment_box_overlap_length(Segment(.030, mode_shoulder_y, .051, mode_shoulder_y), stale_box) > 0.0
        assert items["MountingY0"].OffsetText
        assert ink["TapFromSide"].text[0] > max(line[0] for line in lines["TapFromSide"][:2])
        # R35's X-only jog still failed its native own-ink check. Also clear
        # the real historical witnesses' Y band, without inventing its new jog.
        assert ink["TapFromSide"].text[1] > max(max(line[1], line[3]) for line in lines["TapFromSide"][:2])
        assert items["TapFromSide"].OffsetText
        assert ink["NoseR"].text[0] == pytest.approx(.245683)
        assert ink["NoseR"].text[1] == pytest.approx(.2276389 + .004)
        assert ink["TapFromTip"].text[2] == pytest.approx(.206 - .004)
        assert ink["TapFromTip"].text[1] == pytest.approx(.2242988 + .004)
        assert items["TapFromTip"].OffsetText
        assert items["LeverTapCallout"].dx == items["LeverTapCallout"].dy == 0.0
    if fault not in ("lateral_name", "overall_name", "ignored_move"):
        stages = [json.loads(fields["auditJSON"]) for _message, fields in messages if "auditJSON" in fields]
        assert [record["stage"] for record in stages] == ["before_text_modes", "settled_text_modes", "placed"]
        final = stages[-1]["dimensions"]
        assert "TapFromSide" in final and len(final) == len(items)
        actual = drawing._dimension_layout_ink(object(), items["MountingY0"], label="MountingY0")
        assert final["MountingY0"]["text_box"] == list(actual.text)
        assert final["MountingY0"]["segments"] == [[line.x0, line.y0, line.x1, line.y1] for line in actual.leader]
        assert final["MountingY0"]["native_display"]["texts"][0]["t"] == f"{row_mm:.2f} ±0.05"
        if fault == "unsettled_modes":
            inner = Box(actual.text[0] + .00015, actual.text[1] + .00015, actual.text[2] - .00015, actual.text[3] - .00015)
            assert segment_box_overlap_length(Segment(.030, mode_shoulder_y, .051, mode_shoulder_y), inner) > 0.0



