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
from _drawing_layout_check import DrawableRegion
from _layout_geometry import Box, Segment, segment_box_overlap_length
from _printed_tolerance import printed_band_mm


def test_foot_joins_flush_without_changing_mounting_grip_or_pattern() -> None:
    assert part.FLANGE_X[1] == joint.NECK_THICKNESS / 2.0
    assert part.FLANGE_X[0] < -joint.NECK_THICKNESS / 2.0
    assert part.FLANGE_Z[1] - part.FLANGE_Z[0] == pytest.approx(mounting.SIDE_PLATE_THICKNESS)
    assert mounting.BRACKET_HOLE_POINTS[1][0] - mounting.BRACKET_HOLE_POINTS[0][0] == pytest.approx(mounting.SCREW_MACHINE_X[1] - mounting.SCREW_MACHINE_X[0])
    assert printed_band_mm(spec.DRAWING_PRECISION["FlangeProfile"]["FlangeDepth"]) == mounting.FLANGE_THICKNESS_BAND
    assert all(point[1] == 0.0 and point[2] == part.FLANGE_Z[0] for point in mounting.BRACKET_HOLE_POINTS)
    assert mounting.SIDE_PLATE_X == (-48.0, 6.25)
    assert tuple(point[0] - part.FLANGE_X[0] for point in mounting.BRACKET_HOLE_POINTS) == (9.0, 22.7)
    # The two root arcs share the same tangent point, with no flat ledge.
    assert spec.ROOT_R + spec.FOOT_CORNER_R == pytest.approx(mounting.SIDE_PLATE_HEIGHT / 2.0 - joint.NOSE_R)
    assert spec.ROOT_R <= 1.0




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


@pytest.mark.parametrize("fault", (None, "ignored_move", "own_crossing", "neighbour_crossing", "lateral_name"))
def test_reviewed_linear_ink_is_placed_from_geometry_and_guards_actual_segments(monkeypatch, fault):
    """Historical native ink stations with updated labels and simulated moves."""
    rows = {
        "NeckThickness": [("12.50", .1070212, .185, .0142236)],
        "FlangeDepth": [("3.175", .1667191, .123, .0116375)],
        "MountingX0": [("9.00 ±0.05", .0327281, .0532219, .0245438)],
        "MountingX1": [("22.70 ±0.05", .0464351, .0432219, .0271299)],
        "MountingY0": [("6.35 ±0.05", .0177281, .0772219, .0245438)],
        "SeatToAxis": [("100.40", .1875951, .1622219, .0168097)],
        "FlangeWidth": [("49.25", .0718882, .0952219, .0142236)],
        "NeckToFootSide": [("0.85", .247, .096, .010)],
        "TapFromSide": [("5.50 ±0.05", .2277281, .2372219, .0245438)],
    }
    lines = {
        "NeckThickness": [(.091125, .2114488, .091125, .1784438), (.103625, .2114488, .103625, .1784438), (.091125, .1794438, .1633882, .1794438)],
        "FlangeDepth": [(.104625, .1120512, .141, .1120512), (.104625, .1152262, .141, .1152262), (.2050757, .1174438, .140, .1174438), (.140, .1174438, .140, .1152262), (.140, .1120512, .140, .1057012)],
        "MountingX0": [(.054375, .07265, .054375, .0522219), (.058375, .07265, .058375, .0522219), (.0327281, .0532219, .064725, .0532219)],
        "MountingX1": [(.054375, .07265, .054375, .0422219), (.072075, .07265, .072075, .0422219), (.048025, .0432219, .078425, .0432219)],
        "MountingY0": [(.057375, .07365, .029, .07365), (.0535796, .080, .029, .080), (.030, .07365, .030, .0673), (.030, .080, .030, .08635)],
        "SeatToAxis": [(.2215, .1120512, .195, .1120512), (.2340527, .2124488, .195, .2124488), (.196, .1120512, .196, .1622219), (.196, .2124488, .196, .1677781)],
        "FlangeWidth": [(.054375, .1110512, .054375, .0942219), (.103625, .1110512, .103625, .0942219), (.054375, .0952219, .103625, .0952219)],
        "NeckToFootSide": [(.2335, .110, .2335, .095), (.23435, .110, .23435, .095), (.2335, .096, .257, .096)],
        "TapFromSide": [
            (.2335, .2134488, .2335, .2382219),
            (.228, .2185015, .228, .2382219),
            (.2335, .2372219, .2522719, .2372219),
            (.2335, .2372219, .228, .2372219),
            (.228, .2372219, .22165, .2372219),
        ],
    }
    items = {name: SimpleNamespace(name=name, dx=0.0, dy=0.0, CenterText=True, OffsetText=False) for name in rows}
    for item in items.values():
        item.GetSpecificAnnotation = lambda item=item: item
    items["NeckToFootSide"].GetDimension2 = lambda _index: SimpleNamespace(Name="D1" if fault == "lateral_name" else "NeckToFootSide")

    def native_display(_adapter, item):
        native_lines = list(lines[item.name])
        if item.name == "NeckThickness":
            native_lines = [(a, b, c, d + item.dy) if i < 2 else (a, b + item.dy, c, d + item.dy) for i, (a, b, c, d) in enumerate(native_lines)]
        elif item.name == "FlangeDepth":
            native_lines = [(a if i < 2 else a + item.dx, b, c + item.dx, d) for i, (a, b, c, d) in enumerate(native_lines)]
        if item.name == "MountingY0" and item.OffsetText:
            native_lines.append((.030, .08635, rows[item.name][0][1] + item.dx, rows[item.name][0][2] + item.dy))
        if fault == "own_crossing" and item.name == "MountingX1" and item.dx:
            x = rows[item.name][0][1] + item.dx + .010
            native_lines.append((x, .041, x, .050))
        if fault == "neighbour_crossing" and item.name == "FlangeWidth" and items["MountingX1"].dx:
            x = rows["MountingX1"][0][1] + items["MountingX1"].dx + .010
            native_lines.append((x, .041, x, .050))
        return {
            "texts": [_native_text(text, x + item.dx, y + item.dy, width) for text, x, y, width in rows[item.name]],
            "lines": [_native_line(*line) for line in native_lines],
        }, {}

    def move(_adapter, item, dx, dy, *, label):
        if fault != "ignored_move":
            item.dx += dx
            item.dy += dy

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "annotation_display", native_display)
    # R32 created and measured this native edge dimension successfully, but
    # later model-item name discovery did not find it. Its retained handle
    # must still receive the same real ink and neighbour-clearance checks.
    monkeypatch.setattr(drawing, "dimension_name", lambda _a, item: "" if item is items["NeckToFootSide"] else item.name)
    monkeypatch.setattr(drawing, "move_annotation", move)
    monkeypatch.setattr(drawing, "sheet_region", lambda _a: _R8_REGION)
    monkeypatch.setattr(drawing, "model_point_in_view", lambda _a, _v, p, **_kw: (.097375 + p[0], .080 + p[1]))
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    front = SimpleNamespace(GetOutline=lambda: (.048787, .1064632, .109213, .2235368))
    # Causal controls: actual frozen witnesses cross both horizontal size
    # text boxes, and the 6.35 row is struck at Y80 before placement.
    for name, line in (("MountingX0", lines["MountingX0"][0]), ("MountingX1", lines["MountingX1"][0]), ("MountingY0", lines["MountingY0"][1]), ("TapFromSide", lines["TapFromSide"][0])):
        box = Box(*drawing._dimension_layout_ink(object(), items[name], label=name).text)
        assert segment_box_overlap_length(Segment(*line), box) > 0.0
    if fault:
        message = "retained native dimension name" if fault == "lateral_name" else ("did not settle" if fault == "ignored_move" else ("own native line" if fault == "own_crossing" else "neighbouring native line"))
        with pytest.raises(RuntimeError, match=message):
            drawing._layout_linear_annotations(object(), front, object(), [item for name, item in items.items() if name != "NeckToFootSide"], lateral_location=items["NeckToFootSide"])
    else:
        drawing._layout_linear_annotations(object(), front, object(), [item for name, item in items.items() if name != "NeckToFootSide"], lateral_location=items["NeckToFootSide"])
        ink = {name: drawing._dimension_layout_ink(object(), item, label=name) for name, item in items.items()}
        assert ink["NeckThickness"].text[0] == pytest.approx(.103625 + .004)
        assert items["NeckThickness"].OffsetText
        assert ink["NeckThickness"].text[1] > .2235368
        assert ink["FlangeDepth"].text[2] < .196
        assert ink["MountingX0"].text[2] < .054375
        assert ink["MountingX1"].text[0] > .072075
        assert ink["MountingY0"].text[1] > .08635
        assert items["MountingY0"].OffsetText
        assert ink["TapFromSide"].text[0] > max(line[0] for line in lines["TapFromSide"][:2])
        # R35's X-only jog still failed its native own-ink check. Also clear
        # the real historical witnesses' Y band, without inventing its new jog.
        assert ink["TapFromSide"].text[1] > max(max(line[1], line[3]) for line in lines["TapFromSide"][:2])
        assert items["TapFromSide"].OffsetText



